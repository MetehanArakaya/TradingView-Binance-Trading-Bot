from flask import render_template, request, redirect, url_for, flash, jsonify
from app.web import bp
from app.models import BotSettings, Trade, Signal, Position
from app.models.trade import TradeStatus
from app.models.signal import SignalStatus
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func
import asyncio
import logging

logger = logging.getLogger(__name__)

@bp.route('/')
def index():
    """Redirect to dashboard"""
    return redirect(url_for('web.dashboard'))

@bp.route('/dashboard')
def dashboard():
    """Main dashboard"""
    try:
        settings = BotSettings.get_settings()
        
        # Get open positions
        positions = Position.get_open_positions()
        
        # Get today's trades
        today = datetime.now().date()
        daily_trades = Trade.query.filter(
            Trade.created_at >= today,
            Trade.status == TradeStatus.CLOSED
        ).all()
        
        # Calculate daily P&L
        daily_pnl = sum(trade.net_pnl or 0 for trade in daily_trades)
        
        # Calculate success rate
        winning_trades = len([t for t in daily_trades if (t.net_pnl or 0) > 0])
        total_trades = len(daily_trades)
        success_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Get recent trades (last 10)
        recent_trades = Trade.query.order_by(Trade.created_at.desc()).limit(10).all()
        
        # Get recent signals (last 5)
        recent_signals = Signal.query.order_by(Signal.created_at.desc()).limit(5).all()
        
        return render_template('dashboard.html',
            positions=positions,
            open_positions_count=len(positions),
            daily_pnl=daily_pnl,
            daily_trades_count=len(daily_trades),
            success_rate=success_rate,
            recent_trades=recent_trades,
            recent_signals=recent_signals,
            bot_enabled=settings.bot_enabled,
            emergency_stop=settings.emergency_stop,
            default_leverage=settings.default_leverage,
            max_concurrent_positions=settings.max_concurrent_positions
        )
        
    except Exception as e:
        flash(f'Dashboard yüklenirken hata oluştu: {str(e)}', 'error')
        return render_template('dashboard.html',
            positions=[],
            open_positions_count=0,
            daily_pnl=0,
            daily_trades_count=0,
            success_rate=0,
            recent_trades=[],
            recent_signals=[],
            bot_enabled=False,
            emergency_stop=True,
            default_leverage=10,
            max_concurrent_positions=3
        )

@bp.route('/settings')
def settings():
    """Bot settings page"""
    try:
        settings = BotSettings.get_settings()
        return render_template('settings.html', settings=settings)
    except Exception as e:
        flash(f'Ayarlar yüklenirken hata oluştu: {str(e)}', 'error')
        return render_template('settings.html', settings=BotSettings())

@bp.route('/trades')
def trades():
    """Trade history page"""
    try:
        # Get filter parameters
        date_range = request.args.get('dateRange', 'month')
        symbol_filter = request.args.get('symbol', '')
        type_filter = request.args.get('type', '')
        status_filter = request.args.get('status', '')
        
        # Build query
        query = Trade.query
        
        # Apply date filter
        if date_range == 'today':
            today = datetime.now().date()
            query = query.filter(Trade.created_at >= today)
        elif date_range == 'week':
            week_ago = datetime.now() - timedelta(days=7)
            query = query.filter(Trade.created_at >= week_ago)
        elif date_range == 'month':
            month_ago = datetime.now() - timedelta(days=30)
            query = query.filter(Trade.created_at >= month_ago)
        
        # Apply symbol filter
        if symbol_filter:
            query = query.filter(Trade.symbol == symbol_filter)
        
        # Apply type filter
        if type_filter:
            from app.models.trade import TradeType
            if type_filter == 'long':
                query = query.filter(Trade.trade_type == TradeType.LONG)
            elif type_filter == 'short':
                query = query.filter(Trade.trade_type == TradeType.SHORT)
        
        # Apply status filter
        if status_filter:
            if status_filter == 'open':
                query = query.filter(Trade.status == TradeStatus.OPEN)
            elif status_filter == 'closed':
                query = query.filter(Trade.status == TradeStatus.CLOSED)
            elif status_filter == 'error':
                query = query.filter(Trade.status == TradeStatus.ERROR)
        
        # Get trades ordered by creation date (newest first)
        trades = query.order_by(Trade.created_at.desc()).limit(200).all()
        
        # Calculate summary statistics
        profitable_count = len([t for t in trades if (t.net_pnl or 0) > 0])
        loss_count = len([t for t in trades if (t.net_pnl or 0) < 0])
        total_pnl = sum(t.net_pnl or 0 for t in trades)
        
        # Get unique symbols for filter dropdown
        symbols = db.session.query(Trade.symbol).distinct().all()
        symbols = [s[0] for s in symbols]
        
        return render_template('trades.html',
            trades=trades,
            profitable_count=profitable_count,
            loss_count=loss_count,
            total_pnl=total_pnl,
            symbols=symbols
        )
        
    except Exception as e:
        flash(f'İşlemler yüklenirken hata oluştu: {str(e)}', 'error')
        return render_template('trades.html',
            trades=[],
            profitable_count=0,
            loss_count=0,
            total_pnl=0,
            symbols=[]
        )

@bp.route('/positions')
def positions():
    """Active positions page"""
    try:
        # Get all open positions
        positions = Position.get_open_positions()
        
        # Calculate summary statistics
        long_count = len([p for p in positions if p.side.value == 'long'])
        short_count = len([p for p in positions if p.side.value == 'short'])
        total_pnl = sum(p.unrealized_pnl or 0 for p in positions)
        
        return render_template('positions.html',
            positions=positions,
            long_count=long_count,
            short_count=short_count,
            total_pnl=total_pnl
        )
        
    except Exception as e:
        flash(f'Pozisyonlar yüklenirken hata oluştu: {str(e)}', 'error')
        return render_template('positions.html',
            positions=[],
            long_count=0,
            short_count=0,
            total_pnl=0
        )

@bp.route('/signals')
def signals():
    """Signals page"""
    try:
        # Get all signals ordered by creation date (newest first)
        signals = Signal.query.order_by(Signal.created_at.desc()).limit(100).all()
        
        # Calculate summary statistics
        processed_count = len([s for s in signals if s.status == SignalStatus.PROCESSED])
        pending_count = len([s for s in signals if s.status == SignalStatus.RECEIVED])
        rejected_count = len([s for s in signals if s.status == SignalStatus.REJECTED])
        
        return render_template('signals.html',
            signals=signals,
            processed_count=processed_count,
            pending_count=pending_count,
            rejected_count=rejected_count
        )
        
    except Exception as e:
        flash(f'Sinyaller yüklenirken hata oluştu: {str(e)}', 'error')
        return render_template('signals.html',
            signals=[],
            processed_count=0,
            pending_count=0,
            rejected_count=0
        )

@bp.route('/risk_management')
def risk_management():
    """Risk management page"""
    try:
        settings = BotSettings.get_settings()
        
        # Get current risk metrics
        open_positions = Position.get_open_positions()
        total_exposure = sum(p.notional or 0 for p in open_positions)
        
        # Get today's trades for daily P&L
        today = datetime.now().date()
        daily_trades = Trade.query.filter(
            Trade.created_at >= today,
            Trade.status == TradeStatus.CLOSED
        ).all()
        daily_pnl = sum(trade.net_pnl or 0 for trade in daily_trades)
        
        # Get real account balance from Binance API
        account_balance = 1000.0  # Default fallback
        try:
            from app.api.trading_engine import trading_engine
            if trading_engine.binance_client:
                account_balance = trading_engine.binance_client.get_balance('USDT')
                if account_balance <= 0:
                    account_balance = 1000.0  # Fallback if balance is 0 or negative
        except Exception as e:
            logger.warning(f"Could not fetch real account balance: {e}")
            account_balance = 1000.0  # Fallback on error
        
        risk_percentage = (total_exposure / account_balance * 100) if account_balance > 0 else 0
        
        return render_template('risk_management.html',
            settings=settings,
            open_positions=open_positions,
            total_exposure=total_exposure,
            daily_pnl=daily_pnl,
            account_balance=account_balance,
            risk_percentage=risk_percentage
        )
        
    except Exception as e:
        flash(f'Risk yönetimi sayfası yüklenirken hata oluştu: {str(e)}', 'error')
        return render_template('risk_management.html',
            settings=BotSettings(),
            open_positions=[],
            total_exposure=0,
            daily_pnl=0,
            account_balance=0,
            risk_percentage=0
        )

@bp.route('/api/status')
def api_status():
    """API status endpoint"""
    settings = BotSettings.get_settings()
    return jsonify({
        "bot_enabled": settings.bot_enabled,
        "emergency_stop": settings.emergency_stop,
        "status": "running" if settings.bot_enabled and not settings.emergency_stop else "stopped"
    })

@bp.route('/api/start-bot', methods=['POST'])
def start_bot():
    """Start bot endpoint"""
    try:
        settings = BotSettings.get_settings()
        settings.bot_enabled = True
        settings.emergency_stop = False
        db.session.commit()
        
        return jsonify({"success": True, "message": "Bot başlatıldı"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/stop-bot', methods=['POST'])
def stop_bot():
    """Stop bot endpoint"""
    try:
        settings = BotSettings.get_settings()
        settings.bot_enabled = False
        db.session.commit()
        
        return jsonify({"success": True, "message": "Bot durduruldu"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/emergency-stop', methods=['POST'])
def emergency_stop():
    """Emergency stop endpoint"""
    try:
        # Import here to avoid circular imports
        from app.api.trading_engine import trading_engine
        
        success = trading_engine.emergency_stop_all()
        
        if success:
            return jsonify({"success": True, "message": "Acil durdurma aktif edildi"})
        else:
            return jsonify({"success": False, "error": "Acil durdurma sırasında hata oluştu"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/position/<int:position_id>')
def get_position(position_id):
    """Get position details"""
    try:
        position = Position.query.get_or_404(position_id)
        return jsonify({
            "success": True,
            "position": {
                "id": position.id,
                "symbol": position.symbol,
                "side": position.side.value,
                "size": float(position.size),
                "entry_price": float(position.entry_price),
                "mark_price": float(position.mark_price) if position.mark_price else None,
                "unrealized_pnl": float(position.unrealized_pnl) if position.unrealized_pnl else 0,
                "stop_loss_price": float(position.stop_loss_price) if position.stop_loss_price else None,
                "take_profit_price": float(position.take_profit_price) if position.take_profit_price else None,
                "trailing_stop_price": float(position.trailing_stop_price) if position.trailing_stop_price else None,
                "liquidation_price": float(position.liquidation_price) if position.liquidation_price else None,
                "leverage": position.leverage,
                "notional": float(position.notional) if position.notional else 0
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/close-position/<int:position_id>', methods=['POST'])
def close_position(position_id):
    """Close a specific position"""
    try:
        from app.api.trading_engine import trading_engine
        
        position = Position.query.get_or_404(position_id)
        success = trading_engine.close_position(position)
        
        if success:
            return jsonify({"success": True, "message": f"{position.symbol} pozisyonu kapatıldı"})
        else:
            return jsonify({"success": False, "error": "Pozisyon kapatılırken hata oluştu"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/close-all-positions', methods=['POST'])
def close_all_positions():
    """Close all open positions"""
    try:
        from app.api.trading_engine import trading_engine
        
        positions = Position.get_open_positions()
        closed_count = 0
        
        for position in positions:
            if trading_engine.close_position(position):
                closed_count += 1
        
        return jsonify({
            "success": True,
            "message": f"{closed_count} pozisyon kapatıldı",
            "closed_count": closed_count,
            "total_positions": len(positions)
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/update-position/<int:position_id>', methods=['POST'])
def update_position(position_id):
    """Update position stop loss and take profit"""
    try:
        from app.api.trading_engine import trading_engine
        
        position = Position.query.get_or_404(position_id)
        data = request.get_json()
        
        # Update stop loss
        if 'stop_loss' in data and data['stop_loss']:
            position.stop_loss_price = data['stop_loss']
            
        # Update take profit
        if 'take_profit' in data and data['take_profit']:
            position.take_profit_price = data['take_profit']
            
        # Update trailing stop
        if 'trailing_stop' in data:
            if data['trailing_stop']:
                # Enable trailing stop with current price as reference
                position.trailing_stop_price = position.mark_price or position.entry_price
            else:
                position.trailing_stop_price = None
        
        db.session.commit()
        
        # Try to update orders on Binance
        try:
            trading_engine.update_position_orders(position)
        except Exception as order_error:
            # Log the error but don't fail the update
            print(f"Order update error: {order_error}")
        
        return jsonify({"success": True, "message": "Pozisyon güncellendi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/signal/<int:signal_id>')
def get_signal(signal_id):
    """Get signal details"""
    try:
        signal = Signal.query.get_or_404(signal_id)
        return jsonify({
            "success": True,
            "signal": {
                "id": signal.id,
                "symbol": signal.symbol,
                "signal_type": signal.signal_type.value,
                "status": signal.status.value,
                "price": float(signal.price) if signal.price else None,
                "stop_loss": float(signal.stop_loss) if signal.stop_loss else None,
                "take_profit": float(signal.take_profit) if signal.take_profit else None,
                "created_at": signal.created_at.strftime('%d/%m/%Y %H:%M:%S') if signal.created_at else None,
                "updated_at": signal.updated_at.strftime('%d/%m/%Y %H:%M:%S') if signal.updated_at else None,
                "processed_at": signal.processed_at.strftime('%d/%m/%Y %H:%M:%S') if signal.processed_at else None,
                "error_message": signal.error_message,
                "raw_data": signal.raw_data
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/process-signal/<int:signal_id>', methods=['POST'])
def process_signal_api(signal_id):
    """Process a signal manually"""
    try:
        from app.api.trading_engine import trading_engine
        
        signal = Signal.query.get_or_404(signal_id)
        
        if signal.status != SignalStatus.VALIDATED:
            return jsonify({"success": False, "error": "Sinyal işlenebilir durumda değil"})
        
        success = trading_engine.process_signal(signal_id)
        
        if success:
            return jsonify({"success": True, "message": "Sinyal başarıyla işlendi"})
        else:
            return jsonify({"success": False, "error": "Sinyal işlenirken hata oluştu"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/reject-signal/<int:signal_id>', methods=['POST'])
def reject_signal_api(signal_id):
    """Reject a signal manually"""
    try:
        signal = Signal.query.get_or_404(signal_id)
        data = request.get_json() or {}
        reason = data.get('reason', 'Manuel olarak reddedildi')
        
        signal.mark_rejected(reason)
        db.session.commit()
        
        return jsonify({"success": True, "message": "Sinyal reddedildi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/signals')
def get_signals_api():
    """Get all signals API endpoint"""
    try:
        signals = Signal.query.order_by(Signal.created_at.desc()).limit(100).all()
        
        signals_data = []
        for signal in signals:
            signals_data.append({
                "id": signal.id,
                "symbol": signal.symbol,
                "signal_type": signal.signal_type.value,
                "status": signal.status.value,
                "price": float(signal.price) if signal.price else None,
                "stop_loss": float(signal.stop_loss) if signal.stop_loss else None,
                "take_profit": float(signal.take_profit) if signal.take_profit else None,
                "created_at": signal.created_at.strftime('%d/%m/%Y %H:%M:%S') if signal.created_at else None,
                "processed_at": signal.processed_at.strftime('%d/%m/%Y %H:%M:%S') if signal.processed_at else None,
                "error_message": signal.error_message,
                "source_ip": signal.source_ip
            })
        
        return jsonify({
            "success": True,
            "signals": signals_data,
            "count": len(signals_data)
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/settings/binance', methods=['POST'])
def update_binance_settings():
    """Update Binance API settings"""
    try:
        settings = BotSettings.get_settings()
        data = request.get_json()
        
        if data.get('api_key') and data['api_key'] != '***':
            settings.set_binance_api_key(data['api_key'])
        
        if data.get('secret_key') and data['secret_key'] != '***':
            settings.set_binance_secret_key(data['secret_key'])
        
        settings.testnet_mode = data.get('testnet_mode', True)
        
        db.session.commit()
        return jsonify({"success": True, "message": "Binance ayarları güncellendi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/settings/trading', methods=['POST'])
def update_trading_settings():
    """Update trading settings"""
    try:
        settings = BotSettings.get_settings()
        data = request.get_json()
        
        settings.default_leverage = data.get('default_leverage', 10)
        settings.position_sizing_method = data.get('position_sizing_method', 'percentage')
        settings.max_position_size_percent = data.get('max_position_size_percent', 10.0)
        settings.max_position_size_usdt = data.get('max_position_size_usdt', 100.0)
        
        db.session.commit()
        return jsonify({"success": True, "message": "İşlem ayarları güncellendi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/settings/risk', methods=['POST'])
def update_risk_settings():
    """Update risk management settings"""
    try:
        settings = BotSettings.get_settings()
        data = request.get_json()
        
        settings.use_take_profit = data.get('use_take_profit', True)
        settings.daily_loss_limit = data.get('daily_loss_limit', 0.0)
        settings.daily_loss_limit_enabled = data.get('daily_loss_limit_enabled', False)
        settings.max_concurrent_positions = data.get('max_concurrent_positions', 3)
        settings.max_concurrent_positions_enabled = data.get('max_concurrent_positions_enabled', True)
        
        db.session.commit()
        return jsonify({"success": True, "message": "Risk ayarları güncellendi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/settings/telegram', methods=['POST'])
def update_telegram_settings():
    """Update Telegram settings"""
    try:
        settings = BotSettings.get_settings()
        data = request.get_json()
        
        if data.get('telegram_bot_token') and data['telegram_bot_token'] != '***':
            settings.set_telegram_bot_token(data['telegram_bot_token'])
        
        settings.telegram_chat_id = data.get('telegram_chat_id', '')
        settings.telegram_notifications_enabled = data.get('telegram_notifications_enabled', True)
        
        db.session.commit()
        return jsonify({"success": True, "message": "Telegram ayarları güncellendi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/settings/symbols', methods=['POST'])
def update_symbols_settings():
    """Update allowed symbols settings"""
    try:
        settings = BotSettings.get_settings()
        data = request.get_json()
        
        settings.allowed_symbols = data.get('allowed_symbols', '')
        
        db.session.commit()
        return jsonify({"success": True, "message": "Sembol ayarları güncellendi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/settings/stop-loss-system', methods=['POST'])
def update_stop_loss_system_settings():
    """Update Stop Loss system settings"""
    try:
        settings = BotSettings.get_settings()
        data = request.get_json()
        
        # Basic Stop Loss settings
        settings.use_stop_loss = data.get('use_stop_loss', True)
        settings.trailing_stop_enabled = data.get('trailing_stop_enabled', False)
        settings.trailing_stop_percent = data.get('trailing_stop_percent', 2.0)
        
        # Percentage-based Stop Loss settings
        settings.percentage_sl_enabled = data.get('percentage_sl_enabled', False)
        settings.percentage_sl_percent = data.get('percentage_sl_percent', 3.0)
        settings.percentage_sl_portfolio_base = data.get('percentage_sl_portfolio_base', False)
        
        # ATR-based Dynamic Stop Loss settings
        settings.atr_sl_enabled = data.get('atr_sl_enabled', False)
        settings.atr_sl_period = data.get('atr_sl_period', 14)
        settings.atr_sl_multiplier = data.get('atr_sl_multiplier', 2.0)
        settings.atr_sl_dynamic = data.get('atr_sl_dynamic', False)
        
        # Breakeven Stop Loss settings
        settings.breakeven_sl_enabled = data.get('breakeven_sl_enabled', False)
        settings.breakeven_sl_activation_percent = data.get('breakeven_sl_activation_percent', 2.0)
        settings.breakeven_sl_offset = data.get('breakeven_sl_offset', 0.1)
        
        # Advanced Stop Loss features
        settings.sl_partial_close = data.get('sl_partial_close', False)
        settings.sl_partial_close_percent = data.get('sl_partial_close_percent', 50)
        settings.sl_time_based_exit = data.get('sl_time_based_exit', False)
        settings.sl_max_position_hours = data.get('sl_max_position_hours', 24)
        
        db.session.commit()
        return jsonify({"success": True, "message": "Stop Loss sistemi ayarları güncellendi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/settings/tp-system', methods=['POST'])
def update_tp_system_settings():
    """Update TP system settings"""
    try:
        settings = BotSettings.get_settings()
        data = request.get_json()
        
        # Multiple TP settings
        settings.multiple_tp_enabled = data.get('multiple_tp_enabled', False)
        settings.tp1_percent = data.get('tp1_percent', 3.0)
        settings.tp1_quantity_percent = data.get('tp1_quantity_percent', 33.33)
        settings.tp2_percent = data.get('tp2_percent', 6.0)
        settings.tp2_quantity_percent = data.get('tp2_quantity_percent', 33.33)
        settings.tp3_percent = data.get('tp3_percent', 9.0)
        settings.tp3_quantity_percent = data.get('tp3_quantity_percent', 33.34)
        
        # Trailing TP settings
        settings.trailing_tp_enabled = data.get('trailing_tp_enabled', False)
        settings.trailing_tp_activation_percent = data.get('trailing_tp_activation_percent', 5.0)
        settings.trailing_tp_callback_percent = data.get('trailing_tp_callback_percent', 2.0)
        
        # Risk management settings
        settings.auto_move_sl_to_breakeven = data.get('auto_move_sl_to_breakeven', False)
        settings.risk_free_after_tp1 = data.get('risk_free_after_tp1', False)
        settings.scale_out_enabled = data.get('scale_out_enabled', False)
        
        db.session.commit()
        return jsonify({"success": True, "message": "TP Sistemi ayarları güncellendi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/test-telegram', methods=['POST'])
def test_telegram():
    """Test Telegram bot"""
    try:
        from app.telegram.bot import telegram_notifier
        
        # Use the sync method instead of asyncio.run
        success = telegram_notifier.send_notification_sync("🤖 Test mesajı - Bot çalışıyor!")
        
        if success:
            return jsonify({"success": True, "message": "Test mesajı gönderildi"})
        else:
            return jsonify({"success": False, "error": "Test mesajı gönderilemedi"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/get-chat-id', methods=['GET', 'POST'])
def get_chat_id():
    """Get Chat ID automatically from Telegram Bot API"""
    try:
        settings = BotSettings.get_settings()
        bot_token = settings.get_telegram_bot_token()
        
        if not bot_token:
            return jsonify({
                "success": False,
                "error": "Telegram bot token yapılandırılmamış. Önce bot token'ını girin ve kaydedin."
            })
        
        # Telegram Bot API'den son mesajları çek
        import requests
        
        try:
            # getUpdates API'sini kullanarak son mesajları al
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('ok') and data.get('result'):
                    # Son mesajdan chat ID'yi al
                    updates = data['result']
                    if updates:
                        # En son mesajı al
                        last_update = updates[-1]
                        if 'message' in last_update:
                            chat_id = last_update['message']['chat']['id']
                            chat_type = last_update['message']['chat']['type']
                            
                            # Chat bilgilerini al
                            chat_info = {
                                'id': chat_id,
                                'type': chat_type
                            }
                            
                            if 'first_name' in last_update['message']['chat']:
                                chat_info['name'] = last_update['message']['chat']['first_name']
                            elif 'title' in last_update['message']['chat']:
                                chat_info['name'] = last_update['message']['chat']['title']
                            else:
                                chat_info['name'] = 'Bilinmeyen'
                            
                            return jsonify({
                                "success": True,
                                "chat_id": str(chat_id),
                                "chat_info": chat_info,
                                "message": f"Chat ID başarıyla alındı: {chat_id}"
                            })
                        else:
                            return jsonify({
                                "success": False,
                                "error": "Son mesajda chat bilgisi bulunamadı. Botunuza bir mesaj gönderin ve tekrar deneyin."
                            })
                    else:
                        return jsonify({
                            "success": False,
                            "error": "Henüz bot ile mesajlaşma geçmişi yok. Botunuza /start mesajı gönderin ve tekrar deneyin."
                        })
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Telegram API hatası: {data.get('description', 'Bilinmeyen hata')}"
                    })
            else:
                return jsonify({
                    "success": False,
                    "error": f"Telegram API'ye erişim hatası: {response.status_code}"
                })
                
        except requests.RequestException as e:
            return jsonify({
                "success": False,
                "error": f"Telegram API bağlantı hatası: {str(e)}"
            })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/trade/<int:trade_id>')
def get_trade(trade_id):
    """Get trade details"""
    try:
        trade = Trade.query.get_or_404(trade_id)
        return jsonify({
            "success": True,
            "trade": {
                "id": trade.id,
                "symbol": trade.symbol,
                "trade_type": trade.trade_type.value,
                "status": trade.status.value,
                "quantity": float(trade.quantity),
                "leverage": trade.leverage,
                "entry_price": float(trade.entry_price) if trade.entry_price else None,
                "exit_price": float(trade.exit_price) if trade.exit_price else None,
                "stop_loss": float(trade.stop_loss) if trade.stop_loss else None,
                "take_profit": float(trade.take_profit) if trade.take_profit else None,
                "net_pnl": float(trade.net_pnl) if trade.net_pnl else None,
                "pnl_percentage": float(trade.pnl_percentage) if trade.pnl_percentage else None,
                "commission": float(trade.commission) if trade.commission else None,
                "binance_order_id": trade.binance_order_id,
                "opened_at": trade.opened_at.strftime('%d/%m/%Y %H:%M:%S') if trade.opened_at else None,
                "closed_at": trade.closed_at.strftime('%d/%m/%Y %H:%M:%S') if trade.closed_at else None,
                "created_at": trade.created_at.strftime('%d/%m/%Y %H:%M:%S') if trade.created_at else None,
                "error_message": trade.error_message
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/close-trade/<int:trade_id>', methods=['POST'])
def close_trade_api(trade_id):
    """Close a specific trade"""
    try:
        from app.api.trading_engine import trading_engine
        
        trade = Trade.query.get_or_404(trade_id)
        
        if trade.status != TradeStatus.OPEN:
            return jsonify({"success": False, "error": "İşlem kapatılabilir durumda değil"})
        
        # Find associated position
        position = Position.query.filter_by(opening_trade_id=trade.id).first()
        if position:
            success = trading_engine.close_position(position)
        else:
            return jsonify({"success": False, "error": "İlişkili pozisyon bulunamadı"})
        
        if success:
            return jsonify({"success": True, "message": f"{trade.symbol} işlemi kapatıldı"})
        else:
            return jsonify({"success": False, "error": "İşlem kapatılırken hata oluştu"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/reduce-risk', methods=['POST'])
def reduce_risk():
    """Reduce risk by closing high-risk positions"""
    try:
        from app.api.trading_engine import trading_engine
        
        # Get all open positions
        positions = Position.get_open_positions()
        
        if not positions:
            return jsonify({"success": True, "message": "Kapatılacak pozisyon yok"})
        
        # Get real account balance from Binance API
        account_balance = 1000.0  # Default fallback
        try:
            from app.api.trading_engine import trading_engine
            if trading_engine.binance_client:
                account_balance = trading_engine.binance_client.get_balance('USDT')
                if account_balance <= 0:
                    account_balance = 1000.0  # Fallback if balance is 0 or negative
        except Exception as e:
            logger.warning(f"Could not fetch real account balance: {e}")
            account_balance = 1000.0  # Fallback on error
        
        # Find high-risk positions (>20% of account)
        high_risk_positions = []
        for position in positions:
            position_risk = (position.notional / account_balance * 100) if account_balance > 0 else 0
            if position_risk > 20:
                high_risk_positions.append(position)
        
        # Close high-risk positions
        closed_count = 0
        for position in high_risk_positions:
            if trading_engine.close_position(position):
                closed_count += 1
        
        if closed_count > 0:
            return jsonify({
                "success": True,
                "message": f"{closed_count} yüksek riskli pozisyon kapatıldı",
                "closed_count": closed_count
            })
        else:
            return jsonify({
                "success": True,
                "message": "Yüksek riskli pozisyon bulunamadı"
            })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/reduce-position-size/<int:position_id>', methods=['POST'])
def reduce_position_size(position_id):
    """Reduce position size by percentage"""
    try:
        from app.api.trading_engine import trading_engine
        
        position = Position.query.get_or_404(position_id)
        data = request.get_json()
        size_percentage = data.get('size_percentage', 50)  # Default 50%
        
        if size_percentage <= 0 or size_percentage >= 100:
            return jsonify({"success": False, "error": "Geçersiz boyut yüzdesi"})
        
        # Calculate new size
        reduction_amount = position.size * (size_percentage / 100)
        
        # Create a partial close trade
        from app.models.trade import Trade, TradeType, TradeStatus
        from binance.enums import SIDE_BUY, SIDE_SELL
        
        # Determine close direction (opposite of position)
        side = SIDE_SELL if position.side.value == 'long' else SIDE_BUY
        trade_type = TradeType.SHORT if position.side.value == 'long' else TradeType.LONG
        
        # Create trade record
        trade = Trade(
            symbol=position.symbol,
            trade_type=trade_type,
            status=TradeStatus.PENDING,
            quantity=reduction_amount,
            leverage=position.leverage
        )
        
        db.session.add(trade)
        db.session.commit()
        
        # Execute partial close order
        if trading_engine.binance_client:
            order = trading_engine.binance_client.place_market_order(
                symbol=position.symbol,
                side=side,
                quantity=reduction_amount,
                reduce_only=True
            )
            
            # Update trade
            trade.binance_order_id = str(order['orderId'])
            trade.exit_price = float(order.get('avgPrice', 0))
            trade.status = TradeStatus.CLOSED
            trade.opened_at = datetime.utcnow()
            trade.closed_at = datetime.utcnow()
            
            # Calculate commission and PnL
            trade.calculate_commission()
            trade.calculate_pnl()
            
            # Update position size
            position.size -= reduction_amount
            position.notional = position.entry_price * position.size
            
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": f"Pozisyon boyutu %{size_percentage} azaltıldı"
            })
        else:
            return jsonify({"success": False, "error": "Binance client mevcut değil"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route('/api/export-trades')
def export_trades():
    """Export trades to CSV"""
    try:
        # Get filter parameters
        date_range = request.args.get('dateRange', 'month')
        symbol_filter = request.args.get('symbol', '')
        type_filter = request.args.get('type', '')
        status_filter = request.args.get('status', '')
        
        # Build query (same logic as trades page)
        query = Trade.query
        
        if date_range == 'today':
            today = datetime.now().date()
            query = query.filter(Trade.created_at >= today)
        elif date_range == 'week':
            week_ago = datetime.now() - timedelta(days=7)
            query = query.filter(Trade.created_at >= week_ago)
        elif date_range == 'month':
            month_ago = datetime.now() - timedelta(days=30)
            query = query.filter(Trade.created_at >= month_ago)
        
        if symbol_filter:
            query = query.filter(Trade.symbol == symbol_filter)
        
        if type_filter:
            from app.models.trade import TradeType
            if type_filter == 'long':
                query = query.filter(Trade.trade_type == TradeType.LONG)
            elif type_filter == 'short':
                query = query.filter(Trade.trade_type == TradeType.SHORT)
        
        if status_filter:
            if status_filter == 'open':
                query = query.filter(Trade.status == TradeStatus.OPEN)
            elif status_filter == 'closed':
                query = query.filter(Trade.status == TradeStatus.CLOSED)
            elif status_filter == 'error':
                query = query.filter(Trade.status == TradeStatus.ERROR)
        
        trades = query.order_by(Trade.created_at.desc()).all()
        
        # Create CSV content
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Symbol', 'Type', 'Status', 'Quantity', 'Leverage',
            'Entry Price', 'Exit Price', 'Stop Loss', 'Take Profit',
            'Net PnL', 'PnL %', 'Commission', 'Opened At', 'Closed At'
        ])
        
        # Write data
        for trade in trades:
            writer.writerow([
                trade.id,
                trade.symbol,
                trade.trade_type.value,
                trade.status.value,
                trade.quantity,
                trade.leverage,
                trade.entry_price or '',
                trade.exit_price or '',
                trade.stop_loss or '',
                trade.take_profit or '',
                trade.net_pnl or '',
                trade.pnl_percentage or '',
                trade.commission or '',
                trade.opened_at.strftime('%Y-%m-%d %H:%M:%S') if trade.opened_at else '',
                trade.closed_at.strftime('%Y-%m-%d %H:%M:%S') if trade.closed_at else ''
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=trades_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
        )
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})