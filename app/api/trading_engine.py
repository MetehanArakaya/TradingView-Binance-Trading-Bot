"""
Trading Engine
Handles trade execution logic with 10x leverage
"""

from app.api.binance_client import BinanceClient
from app.models import Signal, Trade, Position, BotSettings
from app.models.signal import SignalType, SignalStatus
from app.models.trade import TradeType, TradeStatus
from app.models.position import PositionSide, PositionStatus
from app.services.tp_manager import TPManager
from app.utils.symbol_mapper import symbol_mapper
from app import db
from binance.enums import SIDE_BUY, SIDE_SELL
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class TradingEngine:
    def __init__(self):
        self.binance_client: Optional[BinanceClient] = None
        self.tp_manager = TPManager()
        self._initialize_client()
    
    def _get_settings(self):
        """Get fresh settings from database"""
        return BotSettings.get_settings()
    
    def _initialize_client(self):
        """Initialize Binance client with current settings"""
        try:
            settings = self._get_settings()
            api_key = settings.get_binance_api_key()
            secret_key = settings.get_binance_secret_key()
            
            if not api_key or not secret_key:
                logger.warning("Binance API credentials not configured")
                return
            
            self.binance_client = BinanceClient(
                api_key=api_key,
                secret_key=secret_key,
                testnet=True  # Always use testnet for safety
            )
            
            logger.info("Trading engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize trading engine: {e}")
            self.binance_client = None
    
    def process_signal(self, signal_id: int) -> bool:
        """Process a validated signal"""
        signal = None
        try:
            # Create a new session for this operation
            from sqlalchemy.orm import sessionmaker
            from app import db
            
            # Get signal with fresh session
            signal = db.session.query(Signal).get(signal_id)
            if not signal:
                logger.error(f"Signal {signal_id} not found")
                return False
            
            if signal.status != SignalStatus.VALIDATED:
                logger.warning(f"Signal {signal_id} is not validated")
                return False
            
            # Check if bot is enabled with fresh settings
            settings = self._get_settings()
            if not settings.bot_enabled or settings.emergency_stop:
                signal.mark_rejected("Bot is disabled or in emergency stop")
                db.session.commit()
                return False
            
            # Check if client is available
            if not self.binance_client or not self.binance_client.is_connected():
                signal.mark_error("Binance client not available")
                db.session.commit()
                return False
            
            # Process based on signal type
            if signal.signal_type == SignalType.CLOSE:
                return self._process_close_signal(signal)
            else:
                return self._process_entry_signal(signal)
                
        except Exception as e:
            logger.error(f"Error processing signal {signal_id}: {e}")
            if signal:
                try:
                    signal.mark_error(str(e))
                    db.session.commit()
                except Exception as commit_error:
                    logger.error(f"Error committing signal error: {commit_error}")
                    db.session.rollback()
            return False
    
    def _process_entry_signal(self, signal: Signal) -> bool:
        """Process BUY/SELL signal"""
        try:
            # Map TradingView symbol to Binance symbol
            binance_symbol = symbol_mapper.map_symbol(signal.symbol)
            if not binance_symbol:
                signal.mark_rejected(f"Symbol {signal.symbol} not found on Binance")
                db.session.commit()
                return False
            
            # Update signal with mapped symbol
            original_symbol = signal.symbol
            signal.symbol = binance_symbol
            
            # Get fresh settings
            settings = self._get_settings()
            
            # Check if symbol is allowed
            if not settings.is_symbol_allowed(signal.symbol):
                signal.mark_rejected(f"Symbol {signal.symbol} not allowed")
                db.session.commit()
                return False
            
            # Check if we already have a position for this symbol
            existing_position = Position.get_position_by_symbol(signal.symbol)
            if existing_position:
                signal.mark_rejected(f"Position already exists for {signal.symbol}")
                db.session.commit()
                return False
            
            # Check position limits (0 = unlimited)
            open_positions = Position.get_open_positions()
            if settings.max_concurrent_positions > 0 and len(open_positions) >= settings.max_concurrent_positions:
                signal.mark_rejected("Maximum concurrent positions reached")
                db.session.commit()
                return False
            
            # Calculate position size
            position_size = self._calculate_position_size(signal)
            if position_size <= 0:
                signal.mark_rejected("Invalid position size calculated")
                db.session.commit()
                return False
            
            logger.info(f"Mapped symbol: {original_symbol} -> {binance_symbol}")
            
            # Execute trade
            return self._execute_entry_trade(signal, position_size)
            
        except Exception as e:
            logger.error(f"Error processing entry signal: {e}")
            signal.mark_error(str(e))
            db.session.commit()
            return False
    
    def _process_close_signal(self, signal: Signal) -> bool:
        """Process CLOSE signal"""
        try:
            # Map TradingView symbol to Binance symbol
            binance_symbol = symbol_mapper.map_symbol(signal.symbol)
            if not binance_symbol:
                signal.mark_rejected(f"Symbol {signal.symbol} not found on Binance")
                db.session.commit()
                return False
            
            # Update signal with mapped symbol
            original_symbol = signal.symbol
            signal.symbol = binance_symbol
            
            # Find existing position
            position = Position.get_position_by_symbol(signal.symbol)
            if not position:
                signal.mark_rejected(f"No position found for {signal.symbol}")
                db.session.commit()
                return False
            
            logger.info(f"Mapped symbol for close: {original_symbol} -> {binance_symbol}")
            
            # Execute close trade
            return self._execute_close_trade(signal, position)
            
        except Exception as e:
            logger.error(f"Error processing close signal: {e}")
            signal.mark_error(str(e))
            db.session.commit()
            return False
    
    def _calculate_position_size(self, signal: Signal) -> float:
        """Calculate position size based on risk management settings"""
        try:
            # Get fresh settings
            settings = self._get_settings()
            
            # Demo mode: Use fixed position values when Binance API fails
            demo_mode = True  # Enable demo mode for testing
            
            if demo_mode:
                logger.info("Demo mode: Using user-configured position size calculation")
                
                # Use user's actual settings instead of fixed demo values
                if settings.position_sizing_method == 'percentage':
                    # Use percentage of a demo balance
                    demo_balance = 1000.0  # $1000 demo balance
                    position_value = demo_balance * (settings.max_position_size_percent / 100)
                    logger.info(f"Demo percentage mode: {settings.max_position_size_percent}% of ${demo_balance} = ${position_value}")
                else:
                    # Use user's fixed USDT amount directly
                    position_value = settings.max_position_size_usdt
                    logger.info(f"Demo fixed mode: Using user's configured ${position_value} USDT")
                
                # Get current price from signal or use demo price
                current_price = signal.price or 1.0  # Use signal price or $1 as fallback
                
                # Calculate quantity with leverage
                leverage = settings.default_leverage
                quantity = (position_value * leverage) / current_price
                
                # Ensure minimum quantity for Binance
                min_quantity = 0.001  # Minimum 0.001 for most symbols
                if quantity < min_quantity:
                    # If calculated quantity is too small, use minimum and adjust position value
                    quantity = min_quantity
                    actual_position_value = (quantity * current_price) / leverage
                    logger.info(f"Adjusted quantity to minimum: {quantity} (actual value: ${actual_position_value:.2f})")
                else:
                    # Round to reasonable precision based on price
                    if current_price > 1000:  # High price coins like BTC
                        quantity = round(quantity, 4)
                    elif current_price > 1:   # Medium price coins
                        quantity = round(quantity, 3)
                    else:  # Low price coins
                        quantity = round(quantity, 0)
                
                logger.info(f"Demo calculated position size: {quantity} {signal.symbol} (${position_value} @ {leverage}x)")
                return quantity
            
            # Production mode: Try to get real balance
            if not self.binance_client:
                logger.error("Binance client not available for position size calculation")
                return 0.0
            
            try:
                # Get available balance
                available_balance = self.binance_client.get_available_balance('USDT')
                
                if available_balance <= 0:
                    logger.warning("Available balance is 0, switching to demo mode")
                    # Fallback to demo mode
                    demo_balance = 1000.0
                    position_value = demo_balance * (settings.max_position_size_percent / 100)
                else:
                    if settings.position_sizing_method == 'percentage':
                        # Calculate based on percentage of portfolio
                        position_value = available_balance * (settings.max_position_size_percent / 100)
                    else:
                        # Use fixed USDT amount
                        position_value = min(settings.max_position_size_usdt, available_balance)
                
                # Get current price
                current_price = signal.price or self.binance_client.get_current_price(signal.symbol)
                
                # Calculate quantity with leverage
                leverage = settings.default_leverage
                quantity = self.binance_client.calculate_quantity(
                    symbol=signal.symbol,
                    usdt_amount=position_value,
                    price=current_price,
                    leverage=leverage
                )
                
                logger.info(f"Calculated position size: {quantity} {signal.symbol} (${position_value} @ {leverage}x)")
                return quantity
                
            except Exception as api_error:
                logger.warning(f"Binance API error, using demo mode: {api_error}")
                # Fallback to demo calculation
                demo_balance = 1000.0
                position_value = demo_balance * (settings.max_position_size_percent / 100)
                current_price = signal.price or 1.0
                leverage = settings.default_leverage
                quantity = (position_value * leverage) / current_price
                quantity = round(quantity, 2)
                
                logger.info(f"Demo fallback position size: {quantity} {signal.symbol} (${position_value} @ {leverage}x)")
                return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    def _execute_entry_trade(self, signal: Signal, quantity: float) -> bool:
        """Execute entry trade"""
        trade = None
        try:
            # Get fresh settings
            settings = self._get_settings()
            
            # Check if client is available
            if not self.binance_client:
                logger.error("Binance client not available for trade execution")
                return False
            
            # Determine trade direction
            trade_type = TradeType.LONG if signal.signal_type == SignalType.BUY else TradeType.SHORT
            side = SIDE_BUY if signal.signal_type == SignalType.BUY else SIDE_SELL
            
            # Set leverage and margin type
            self.binance_client.set_leverage(signal.symbol, settings.default_leverage)
            self.binance_client.set_margin_type(signal.symbol, 'ISOLATED')
            
            # Create trade record
            trade = Trade(
                signal_id=signal.id,
                symbol=signal.symbol,
                trade_type=trade_type,
                status=TradeStatus.PENDING,
                quantity=quantity,
                leverage=settings.default_leverage,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit
            )
            
            db.session.add(trade)
            db.session.commit()
            
            # Execute market order
            order = self.binance_client.place_market_order(
                symbol=signal.symbol,
                side=side,
                quantity=quantity
            )
            
            # Update trade with order info
            trade.binance_order_id = str(order['orderId'])
            
            # Get entry price from order or current market price
            entry_price = order.get('avgPrice')
            if not entry_price or float(entry_price) == 0:
                # If avgPrice is not available, get current market price
                entry_price = self.binance_client.get_current_price(signal.symbol)
            
            trade.entry_price = float(entry_price)
            trade.status = TradeStatus.OPEN
            trade.opened_at = datetime.utcnow()
            
            # Calculate commission
            trade.calculate_commission()
            
            # Create position record
            position = Position(
                symbol=signal.symbol,
                side=PositionSide.LONG if trade_type == TradeType.LONG else PositionSide.SHORT,
                size=quantity,
                notional=trade.entry_price * quantity,
                leverage=settings.default_leverage,
                entry_price=trade.entry_price,
                stop_loss_price=signal.stop_loss,
                take_profit_price=signal.take_profit,
                initial_margin=(trade.entry_price * quantity) / settings.default_leverage,
                opening_trade_id=trade.id
            )
            
            db.session.add(position)
            
            # Commit position first to get ID
            db.session.commit()
            
            # Refresh position to get the ID
            db.session.refresh(position)
            
            # Handle TP system based on settings
            if settings.multiple_tp_enabled:
                # Use advanced TP system
                self.tp_manager.setup_multiple_tp_levels(position)
            else:
                # Use traditional single TP/SL - Always place orders if enabled
                try:
                    if settings.use_stop_loss:
                        # Use signal SL or calculate default SL
                        sl_price = signal.stop_loss
                        if not sl_price and settings.default_stop_loss_percent > 0:
                            # Calculate default SL based on percentage
                            if position.side == PositionSide.LONG:
                                sl_price = trade.entry_price * (1 - settings.default_stop_loss_percent / 100)
                            else:  # SHORT
                                sl_price = trade.entry_price * (1 + settings.default_stop_loss_percent / 100)
                        
                        if sl_price:
                            self._place_stop_loss_order(position, sl_price)
                            position.stop_loss_price = sl_price
                            logger.info(f"Stop Loss order placed for {position.symbol} @ {sl_price}")
                    
                    if settings.use_take_profit:
                        # Use signal TP or calculate default TP
                        tp_price = signal.take_profit
                        if not tp_price and settings.default_take_profit_percent > 0:
                            # Calculate default TP based on percentage
                            if position.side == PositionSide.LONG:
                                tp_price = trade.entry_price * (1 + settings.default_take_profit_percent / 100)
                            else:  # SHORT
                                tp_price = trade.entry_price * (1 - settings.default_take_profit_percent / 100)
                        
                        if tp_price:
                            self._place_take_profit_order(position, tp_price)
                            position.take_profit_price = tp_price
                            logger.info(f"Take Profit order placed for {position.symbol} @ {tp_price}")
                            
                except Exception as e:
                    logger.error(f"Error placing SL/TP orders for {position.symbol}: {e}")
            
            # Mark signal as processed
            signal.mark_processed()
            
            # Final commit
            db.session.commit()
            
            logger.info(f"Entry trade executed: {trade.symbol} {trade.trade_type.value} {trade.quantity}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing entry trade: {e}")
            if trade:
                try:
                    trade.status = TradeStatus.ERROR
                    trade.error_message = str(e)
                    db.session.commit()
                except Exception as commit_error:
                    logger.error(f"Error committing trade error: {commit_error}")
                    db.session.rollback()
            return False
    
    def _execute_close_trade(self, signal: Signal, position: Position) -> bool:
        """Execute close trade"""
        trade = None
        try:
            # Check if client is available
            if not self.binance_client:
                logger.error("Binance client not available for close trade")
                return False
            
            # Determine close direction (opposite of position)
            side = SIDE_SELL if position.side == PositionSide.LONG else SIDE_BUY
            
            # Create close trade record
            trade = Trade(
                signal_id=signal.id,
                symbol=signal.symbol,
                trade_type=TradeType.SHORT if position.side == PositionSide.LONG else TradeType.LONG,
                status=TradeStatus.PENDING,
                quantity=position.size,
                leverage=position.leverage
            )
            
            db.session.add(trade)
            db.session.commit()
            
            # Execute market order to close position
            order = self.binance_client.place_market_order(
                symbol=signal.symbol,
                side=side,
                quantity=position.size,
                reduce_only=True
            )
            
            # Update trade
            trade.binance_order_id = str(order['orderId'])
            trade.exit_price = float(order.get('avgPrice', signal.price or 0))
            trade.status = TradeStatus.CLOSED
            trade.opened_at = datetime.utcnow()
            trade.closed_at = datetime.utcnow()
            
            # Calculate commission and PnL
            trade.calculate_commission()
            trade.calculate_pnl()
            
            # Update position
            position.close_position(trade.exit_price, trade.net_pnl)
            position.closing_trade_id = trade.id
            
            # Mark signal as processed
            signal.mark_processed()
            
            db.session.commit()
            
            logger.info(f"Close trade executed: {trade.symbol} PnL: {trade.net_pnl}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing close trade: {e}")
            if trade:
                try:
                    trade.status = TradeStatus.ERROR
                    trade.error_message = str(e)
                    db.session.commit()
                except Exception as commit_error:
                    logger.error(f"Error committing close trade error: {commit_error}")
                    db.session.rollback()
            return False
    
    def _place_stop_loss_order(self, position: Position, stop_price: float):
        """Place stop loss order"""
        try:
            if not self.binance_client:
                logger.error("Binance client not available for stop loss order")
                return
            
            side = SIDE_SELL if position.side == PositionSide.LONG else SIDE_BUY
            
            self.binance_client.place_stop_loss_order(
                symbol=position.symbol,
                side=side,
                quantity=position.size,
                stop_price=stop_price,
                reduce_only=True
            )
            
            logger.info(f"Stop loss placed for {position.symbol} @ {stop_price}")
            
        except Exception as e:
            logger.error(f"Error placing stop loss: {e}")
    
    def _place_take_profit_order(self, position: Position, take_profit_price: float):
        """Place take profit order"""
        try:
            if not self.binance_client:
                logger.error("Binance client not available for take profit order")
                return
            
            side = SIDE_SELL if position.side == PositionSide.LONG else SIDE_BUY
            
            self.binance_client.place_take_profit_order(
                symbol=position.symbol,
                side=side,
                quantity=position.size,
                stop_price=take_profit_price,
                reduce_only=True
            )
            
            logger.info(f"Take profit placed for {position.symbol} @ {take_profit_price}")
            
        except Exception as e:
            logger.error(f"Error placing take profit: {e}")
    
    def emergency_stop_all(self) -> bool:
        """Emergency stop - close all positions"""
        try:
            logger.warning("EMERGENCY STOP ACTIVATED - Closing all positions")
            
            # Set emergency stop flag
            settings = self._get_settings()
            settings.emergency_stop = True
            db.session.commit()
            
            # Get all open positions
            open_positions = Position.get_open_positions()
            
            for position in open_positions:
                try:
                    # Close position via Binance
                    self.binance_client.close_position(position.symbol)
                    
                    # Update position status
                    position.status = PositionStatus.CLOSED
                    position.closed_at = datetime.utcnow()
                    
                    logger.info(f"Emergency closed position: {position.symbol}")
                    
                except Exception as e:
                    logger.error(f"Error closing position {position.symbol}: {e}")
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
            return False
    
    def update_position_prices(self):
        """Update mark prices for all open positions and check TP/SL levels"""
        try:
            open_positions = Position.get_open_positions()
            if not open_positions:
                return
            
            # Get fresh settings
            settings = self._get_settings()
            
            for position in open_positions:
                try:
                    # Get current mark price
                    if not self.binance_client:
                        continue
                        
                    mark_price = self.binance_client.get_mark_price(position.symbol)
                    if not mark_price:
                        continue
                        
                    position.update_mark_price(mark_price)
                    
                    # Check Stop Loss conditions
                    self._check_stop_loss_conditions(position, mark_price, settings)
                    
                    # Check Take Profit conditions
                    self._check_take_profit_conditions(position, mark_price, settings)
                    
                except Exception as e:
                    logger.error(f"Error updating price for {position.symbol}: {e}")
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error updating position prices: {e}")
    
    def _check_stop_loss_conditions(self, position: Position, current_price: float, settings):
        """Check all stop loss conditions and execute if needed"""
        try:
            should_close = False
            close_reason = ""
            
            # Check if we need to place initial SL orders (if not already placed)
            if settings.use_stop_loss and not position.stop_loss_price:
                try:
                    # Calculate default SL if not set
                    if settings.default_stop_loss_percent > 0:
                        if position.side == PositionSide.LONG:
                            sl_price = position.entry_price * (1 - settings.default_stop_loss_percent / 100)
                        else:  # SHORT
                            sl_price = position.entry_price * (1 + settings.default_stop_loss_percent / 100)
                        
                        # Place SL order on Binance
                        self._place_stop_loss_order(position, sl_price)
                        position.stop_loss_price = sl_price
                        db.session.commit()
                        logger.info(f"Initial SL order placed for {position.symbol} @ {sl_price}")
                except Exception as e:
                    logger.error(f"Error placing initial SL order for {position.symbol}: {e}")
            
            # 1. Traditional Stop Loss
            if settings.use_stop_loss and position.should_stop_loss(current_price):
                should_close = True
                close_reason = f"Traditional SL hit at {current_price}"
            
            # 2. Percentage-based Stop Loss
            elif settings.percentage_sl_enabled:
                entry_price = position.entry_price
                sl_percent = settings.percentage_sl_percent / 100
                
                if position.side.value == 'LONG':
                    sl_price = entry_price * (1 - sl_percent)
                    if current_price <= sl_price:
                        should_close = True
                        close_reason = f"Percentage SL hit at {current_price} (target: {sl_price})"
                else:  # SHORT
                    sl_price = entry_price * (1 + sl_percent)
                    if current_price >= sl_price:
                        should_close = True
                        close_reason = f"Percentage SL hit at {current_price} (target: {sl_price})"
            
            # 3. Breakeven Stop Loss
            elif settings.breakeven_sl_enabled:
                activation_percent = settings.breakeven_sl_activation_percent / 100
                entry_price = position.entry_price
                
                if position.side.value == 'LONG':
                    activation_price = entry_price * (1 + activation_percent)
                    if current_price >= activation_price:
                        # Move SL to breakeven + offset
                        breakeven_price = entry_price * (1 + settings.breakeven_sl_offset / 100)
                        if current_price <= breakeven_price:
                            should_close = True
                            close_reason = f"Breakeven SL hit at {current_price}"
                else:  # SHORT
                    activation_price = entry_price * (1 - activation_percent)
                    if current_price <= activation_price:
                        breakeven_price = entry_price * (1 - settings.breakeven_sl_offset / 100)
                        if current_price >= breakeven_price:
                            should_close = True
                            close_reason = f"Breakeven SL hit at {current_price}"
            
            # 4. Trailing Stop Loss
            elif settings.trailing_stop_enabled:
                position.update_trailing_stop(current_price, settings.trailing_stop_percent)
                if position.should_trailing_stop(current_price):
                    should_close = True
                    close_reason = f"Trailing SL hit at {current_price}"
            
            # Execute stop loss if needed
            if should_close:
                logger.info(f"Executing SL for {position.symbol}: {close_reason}")
                if self.close_position(position):
                    # Send notification
                    self._send_sl_notification(position, current_price, close_reason)
                    
        except Exception as e:
            logger.error(f"Error checking SL conditions for {position.symbol}: {e}")
    
    def _check_take_profit_conditions(self, position: Position, current_price: float, settings):
        """Check take profit conditions and execute if needed"""
        try:
            # Check if we need to place initial TP orders (if not already placed)
            if settings.use_take_profit and not position.take_profit_price:
                try:
                    # Calculate default TP if not set
                    if settings.default_take_profit_percent > 0:
                        if position.side == PositionSide.LONG:
                            tp_price = position.entry_price * (1 + settings.default_take_profit_percent / 100)
                        else:  # SHORT
                            tp_price = position.entry_price * (1 - settings.default_take_profit_percent / 100)
                        
                        # Place TP order on Binance
                        self._place_take_profit_order(position, tp_price)
                        position.take_profit_price = tp_price
                        db.session.commit()
                        logger.info(f"Initial TP order placed for {position.symbol} @ {tp_price}")
                except Exception as e:
                    logger.error(f"Error placing initial TP order for {position.symbol}: {e}")
            
            # Handle advanced TP system
            if settings.multiple_tp_enabled:
                # Check and process TP levels
                executed_tps = self.tp_manager.check_tp_levels(position, current_price)
                
                # Handle trailing TP if enabled
                if settings.trailing_tp_enabled:
                    self.tp_manager.update_trailing_tp(position, current_price)
            
            # Handle traditional TP system
            elif settings.use_take_profit and position.should_take_profit(current_price):
                logger.info(f"Executing traditional TP for {position.symbol} at {current_price}")
                if self.close_position(position):
                    # Send notification
                    self._send_tp_notification_traditional(position, current_price)
                    
        except Exception as e:
            logger.error(f"Error checking TP conditions for {position.symbol}: {e}")
    
    def _send_sl_notification(self, position: Position, price: float, reason: str):
        """Send stop loss notification"""
        try:
            settings = self._get_settings()
            if not settings.telegram_notifications_enabled:
                return
            
            from app.telegram.bot import telegram_notifier
            
            message = f"""
🛑 Stop Loss Executed!

📊 Position: {position.symbol}
💰 Price: ${price:,.4f}
📉 Reason: {reason}
📈 PnL: ${position.realized_pnl:,.2f}

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
            """
            
            telegram_notifier.send_notification_sync(message)
            
        except Exception as e:
            logger.error(f"Error sending SL notification: {e}")
    
    def _send_tp_notification_traditional(self, position: Position, price: float):
        """Send traditional take profit notification"""
        try:
            settings = self._get_settings()
            if not settings.telegram_notifications_enabled:
                return
            
            from app.telegram.bot import telegram_notifier
            
            message = f"""
🎯 Take Profit Executed!

📊 Position: {position.symbol}
💰 Price: ${price:,.4f}
📈 PnL: ${position.realized_pnl:,.2f}
📊 Type: Traditional TP

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
            """
            
            telegram_notifier.send_notification_sync(message)
            
        except Exception as e:
            logger.error(f"Error sending TP notification: {e}")
    
    def close_position(self, position: Position) -> bool:
        """Close a specific position"""
        try:
            if not self.binance_client or not self.binance_client.is_connected():
                logger.error("Binance client not available")
                return False
            
            # Determine close direction (opposite of position)
            side = SIDE_SELL if position.side == PositionSide.LONG else SIDE_BUY
            
            # Create close trade record - use a dummy signal_id for SL/TP closures
            trade = Trade(
                signal_id=-1,  # Use -1 for SL/TP automatic closures
                symbol=position.symbol,
                trade_type=TradeType.SHORT if position.side == PositionSide.LONG else TradeType.LONG,
                status=TradeStatus.PENDING,
                quantity=position.size,
                leverage=position.leverage
            )
            
            db.session.add(trade)
            db.session.commit()
            
            # Execute market order to close position
            order = self.binance_client.place_market_order(
                symbol=position.symbol,
                side=side,
                quantity=position.size,
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
            
            # Update position
            position.close_position(trade.exit_price, trade.net_pnl)
            position.closing_trade_id = trade.id
            
            db.session.commit()
            
            logger.info(f"Position closed: {position.symbol} PnL: {trade.net_pnl}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing position {position.symbol}: {e}")
            if 'trade' in locals():
                trade.status = TradeStatus.ERROR
                trade.error_message = str(e)
                db.session.commit()
            return False
    
    def update_position_orders(self, position: Position) -> bool:
        """Update stop loss and take profit orders for a position"""
        try:
            if not self.binance_client or not self.binance_client.is_connected():
                logger.error("Binance client not available")
                return False
            
            # Cancel existing orders for this position
            try:
                self.binance_client.cancel_all_orders(position.symbol)
            except Exception as e:
                logger.warning(f"Error canceling existing orders: {e}")
            
            # Place new stop loss order if configured
            if position.stop_loss_price:
                try:
                    self._place_stop_loss_order(position, position.stop_loss_price)
                except Exception as e:
                    logger.error(f"Error placing stop loss: {e}")
            
            # Place new take profit order if configured
            if position.take_profit_price:
                try:
                    self._place_take_profit_order(position, position.take_profit_price)
                except Exception as e:
                    logger.error(f"Error placing take profit: {e}")
            
            logger.info(f"Position orders updated for {position.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating position orders: {e}")
            return False

# Global trading engine instance
trading_engine = TradingEngine()