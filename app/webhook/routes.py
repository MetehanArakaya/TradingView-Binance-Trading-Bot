from flask import request, jsonify, current_app
from app.webhook import bp
from app.models import Signal, BotSettings
from app.models.signal import SignalType, SignalStatus
from app import db
import json
import hmac
import hashlib
from datetime import datetime

@bp.route('/tradingview', methods=['POST'])
def tradingview_webhook():
    """
    TradingView webhook endpoint
    Receives signals from TradingView alerts
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
        
        # Get bot settings
        settings = BotSettings.get_settings()
        
        # Check if bot is enabled
        if not settings.bot_enabled or settings.emergency_stop:
            return jsonify({"error": "Bot is disabled or in emergency stop"}), 403
        
        # Verify webhook signature if configured
        if settings.webhook_secret:
            signature = request.headers.get('X-Signature')
            if not verify_signature(request.data, signature, settings.webhook_secret):
                return jsonify({"error": "Invalid signature"}), 401
        
        # Check IP whitelist if configured
        allowed_ips = settings.get_allowed_ips_list()
        if allowed_ips and request.remote_addr not in allowed_ips:
            return jsonify({"error": "IP not allowed"}), 403
        
        # Parse signal data
        signal_data = parse_tradingview_signal(data)
        if not signal_data:
            return jsonify({"error": "Invalid signal format"}), 400
        
        # Create signal record
        signal = Signal(
            symbol=signal_data['symbol'],
            signal_type=signal_data['signal_type'],
            price=signal_data.get('price'),
            stop_loss=signal_data.get('stop_loss'),
            take_profit=signal_data.get('take_profit'),
            raw_data=json.dumps(data),
            source_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
        
        # Validate signal
        if signal.is_valid():
            signal.status = SignalStatus.VALIDATED
            db.session.add(signal)
            db.session.commit()
            
            # Process signal using signal processor
            from app.services.signal_processor import process_signal_async
            
            # Process signal synchronously for now (can be moved to background task queue later)
            try:
                process_signal_async(signal.id)
            except Exception as e:
                current_app.logger.error(f"Signal processing error: {e}")
            
            current_app.logger.info(f"Signal received and queued for processing: {signal.id}")
            return jsonify({
                "status": "success",
                "signal_id": signal.id,
                "message": "Signal received and queued for processing"
            }), 200
        else:
            signal.status = SignalStatus.REJECTED
            signal.error_message = "Signal validation failed"
            db.session.add(signal)
            db.session.commit()
            
            return jsonify({"error": "Signal validation failed"}), 400
            
    except Exception as e:
        current_app.logger.error(f"Webhook error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

def verify_signature(payload, signature, secret):
    """Verify webhook signature"""
    if not signature:
        return False
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

def parse_tradingview_signal(data):
    """
    Parse TradingView signal data
    Expected format:
    {
        "symbol": "BTCUSDT",
        "action": "buy|sell|close",
        "price": 45000.0,
        "stop_loss": 43500.0,
        "take_profit": 47000.0
    }
    """
    try:
        symbol = data.get('symbol', '').upper()
        action = data.get('action', '').lower()
        
        if not symbol or not action:
            return None
        
        # Map action to signal type
        signal_type_map = {
            'buy': SignalType.BUY,
            'long': SignalType.BUY,
            'sell': SignalType.SELL,
            'short': SignalType.SELL,
            'close': SignalType.CLOSE,
            'exit': SignalType.CLOSE
        }
        
        signal_type = signal_type_map.get(action)
        if not signal_type:
            return None
        
        result = {
            'symbol': symbol,
            'signal_type': signal_type
        }
        
        # Optional fields
        if 'price' in data:
            result['price'] = float(data['price'])
        
        if 'stop_loss' in data:
            result['stop_loss'] = float(data['stop_loss'])
        
        if 'take_profit' in data:
            result['take_profit'] = float(data['take_profit'])
        
        return result
        
    except (ValueError, TypeError) as e:
        current_app.logger.error(f"Signal parsing error: {str(e)}")
        return None

@bp.route('/test', methods=['POST'])
def test_webhook():
    """Test webhook endpoint for development"""
    if not current_app.debug:
        return jsonify({"error": "Test endpoint only available in debug mode"}), 403
    
    data = request.get_json() or {}
    
    # Create test signal
    test_signal = {
        "symbol": data.get("symbol", "BTCUSDT"),
        "action": data.get("action", "buy"),
        "price": data.get("price", 45000.0),
        "stop_loss": data.get("stop_loss", 43500.0),
        "take_profit": data.get("take_profit", 47000.0)
    }
    
    return jsonify({
        "status": "test_success",
        "received_data": data,
        "test_signal": test_signal,
        "message": "Test webhook received successfully"
    })

@bp.route('/status')
def webhook_status():
    """Webhook status endpoint"""
    settings = BotSettings.get_settings()
    
    return jsonify({
        "webhook_enabled": settings.bot_enabled and not settings.emergency_stop,
        "bot_enabled": settings.bot_enabled,
        "emergency_stop": settings.emergency_stop,
        "webhook_secret_configured": bool(settings.webhook_secret),
        "ip_whitelist_enabled": bool(settings.get_allowed_ips_list()),
        "timestamp": datetime.utcnow().isoformat()
    })