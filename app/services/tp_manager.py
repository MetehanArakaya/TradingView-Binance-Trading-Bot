"""
Advanced Take Profit Management Service
"""
import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal, ROUND_DOWN
from app import db
from app.models.position import Position
from app.models.tp_level import TPLevel, TPHistory
from app.models.settings import BotSettings
from app.api.binance_client import BinanceClient
from app.telegram.bot import telegram_notifier

logger = logging.getLogger(__name__)

class TPManager:
    """Advanced Take Profit Manager"""
    
    def __init__(self):
        self.binance_client = None
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
            if api_key and secret_key:
                self.binance_client = BinanceClient(
                    api_key=api_key,
                    secret_key=secret_key,
                    testnet=settings.testnet_mode
                )
            else:
                self.binance_client = None
        except Exception as e:
            logger.error(f"Error initializing TP manager client: {e}")
            self.binance_client = None
    
    def create_tp_levels_for_position(self, position: Position) -> List[TPLevel]:
        """Create TP levels for a new position"""
        try:
            # Check if position has an ID (must be committed first)
            if not position.id:
                logger.error(f"Position must be committed to database before creating TP levels")
                return []
            
            settings = self._get_settings()
            if not settings.multiple_tp_enabled:
                # Use single TP if multiple TP is disabled
                return self._create_single_tp(position)
            
            tp_configs = self._calculate_tp_levels(position)
            tp_levels = TPLevel.create_tp_levels(position.id, tp_configs)
            
            # Log TP creation
            for tp_level in tp_levels:
                TPHistory.log_action(
                    position_id=position.id,
                    tp_level=tp_level.tp_level,
                    action='CREATED',
                    price=tp_level.target_price,
                    quantity=position.size * (tp_level.quantity_percent / 100),
                    notes=f'TP{tp_level.tp_level} created at {tp_level.target_price}'
                )
            
            logger.info(f"Created {len(tp_levels)} TP levels for position {position.id}")
            return tp_levels
            
        except Exception as e:
            logger.error(f"Error creating TP levels for position {position.id}: {e}")
            return []
    
    def _create_single_tp(self, position: Position) -> List[TPLevel]:
        """Create single TP level"""
        if not position.take_profit_price:
            return []
        
        tp_config = [{
            'level': 1,
            'price': position.take_profit_price,
            'quantity_percent': 100.0
        }]
        
        return TPLevel.create_tp_levels(position.id, tp_config)
    
    def _calculate_tp_levels(self, position: Position) -> List[Dict]:
        """Calculate TP levels based on settings and position"""
        tp_configs = []
        entry_price = position.entry_price
        settings = self._get_settings()
        
        # Determine direction multiplier
        multiplier = 1 if position.side == 'LONG' else -1
        
        # Calculate TP prices
        tp1_price = entry_price * (1 + multiplier * settings.tp1_percent / 100)
        tp2_price = entry_price * (1 + multiplier * settings.tp2_percent / 100)
        tp3_price = entry_price * (1 + multiplier * settings.tp3_percent / 100)
        
        # Use custom TP if provided in position
        if position.take_profit_price:
            # Adjust TP levels based on provided take profit
            tp_distance = abs(position.take_profit_price - entry_price)
            tp1_price = entry_price + multiplier * tp_distance * 0.33
            tp2_price = entry_price + multiplier * tp_distance * 0.66
            tp3_price = position.take_profit_price
        
        tp_configs = [
            {
                'level': 1,
                'price': round(tp1_price, 8),
                'quantity_percent': settings.tp1_quantity_percent
            },
            {
                'level': 2,
                'price': round(tp2_price, 8),
                'quantity_percent': settings.tp2_quantity_percent
            },
            {
                'level': 3,
                'price': round(tp3_price, 8),
                'quantity_percent': settings.tp3_quantity_percent
            }
        ]
        
        return tp_configs
    
    def check_tp_levels(self, position: Position, current_price: float) -> List[TPLevel]:
        """Check if any TP levels should be executed"""
        executed_tps = []
        pending_tps = TPLevel.get_pending_for_position(position.id)
        
        if not pending_tps:
            return executed_tps
        
        for tp_level in pending_tps:
            if self._should_execute_tp(position, tp_level, current_price):
                if self._execute_tp_level(position, tp_level, current_price):
                    executed_tps.append(tp_level)
        
        return executed_tps
    
    def _should_execute_tp(self, position: Position, tp_level: TPLevel, current_price: float) -> bool:
        """Check if TP level should be executed"""
        if position.side == 'LONG':
            return current_price >= tp_level.target_price
        else:
            return current_price <= tp_level.target_price
    
    def _execute_tp_level(self, position: Position, tp_level: TPLevel, current_price: float) -> bool:
        """Execute a TP level"""
        try:
            # Calculate quantity to close
            quantity_to_close = position.size * (tp_level.quantity_percent / 100)
            quantity_to_close = float(Decimal(str(quantity_to_close)).quantize(
                Decimal('0.00001'), rounding=ROUND_DOWN
            ))
            
            # Place market order to close partial position
            order_result = self._place_tp_order(position, quantity_to_close, current_price)
            
            if order_result:
                # Update TP level
                tp_level.execute(current_price, order_result.get('orderId'))
                
                # Update position size
                position.size -= quantity_to_close
                
                # Calculate PnL for this TP
                pnl = self._calculate_tp_pnl(position, quantity_to_close, current_price)
                position.realized_pnl = (position.realized_pnl or 0) + pnl
                
                # Log TP execution
                TPHistory.log_action(
                    position_id=position.id,
                    tp_level=tp_level.tp_level,
                    action='EXECUTED',
                    price=current_price,
                    quantity=quantity_to_close,
                    pnl=pnl,
                    notes=f'TP{tp_level.tp_level} executed at {current_price}'
                )
                
                # Check if position should be closed
                if position.size <= 0.001:  # Minimum size threshold
                    position.status = 'CLOSED'
                    position.exit_price = current_price
                
                db.session.commit()
                
                # Send notification
                self._send_tp_notification(position, tp_level, current_price, pnl)
                
                # Handle post-TP actions
                self._handle_post_tp_actions(position, tp_level)
                
                logger.info(f"TP{tp_level.tp_level} executed for position {position.id} at {current_price}")
                return True
            
        except Exception as e:
            logger.error(f"Error executing TP{tp_level.tp_level} for position {position.id}: {e}")
        
        return False
    
    def _place_tp_order(self, position: Position, quantity: float, price: float) -> Optional[Dict]:
        """Place TP order on Binance"""
        try:
            if not self.binance_client:
                return None
            
            # Ensure we don't try to close more than available position size
            # Use database position size as it's more reliable for partial closes
            if quantity > position.size:
                logger.warning(f"TP quantity {quantity} exceeds position size {position.size} for {position.symbol}")
                quantity = position.size
            
            # Minimum quantity check
            if quantity < 0.001:
                logger.warning(f"TP quantity too small: {quantity} for {position.symbol}")
                return None
            
            # Skip if quantity is too small
            if quantity <= 0.001:
                logger.warning(f"TP quantity too small: {quantity}")
                return None
                
            side = 'SELL' if position.side.value == 'LONG' else 'BUY'
            
            # Fix quantity precision before placing order
            quantity = self.binance_client._fix_quantity_precision(position.symbol, quantity)
            
            order = self.binance_client.place_market_order(
                symbol=position.symbol,
                side=side,
                quantity=quantity
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error placing TP order: {e}")
            return None
    
    def _calculate_tp_pnl(self, position: Position, quantity: float, exit_price: float) -> float:
        """Calculate PnL for TP execution"""
        if position.side == 'LONG':
            pnl = (exit_price - position.entry_price) * quantity
        else:
            pnl = (position.entry_price - exit_price) * quantity
        
        return pnl * position.leverage
    
    def _send_tp_notification(self, position: Position, tp_level: TPLevel, price: float, pnl: float):
        """Send TP execution notification"""
        settings = self._get_settings()
        if not settings.telegram_notifications_enabled:
            return
        
        message = f"""
🎯 Take Profit Executed!

📊 Position: {position.symbol}
🔢 TP Level: TP{tp_level.tp_level}
💰 Price: ${price:,.4f}
📈 PnL: ${pnl:,.2f}
📊 Quantity: {tp_level.quantity_percent}%

⏰ {tp_level.executed_at.strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        telegram_notifier.send_notification_sync(message)
    
    def _handle_post_tp_actions(self, position: Position, executed_tp: TPLevel):
        """Handle actions after TP execution"""
        try:
            settings = self._get_settings()
            # Move SL to breakeven after TP1
            if (executed_tp.tp_level == 1 and
                settings.auto_move_sl_to_breakeven and
                settings.risk_free_after_tp1):
                self._move_sl_to_breakeven(position)
            
            # Update trailing TP if enabled
            if settings.trailing_tp_enabled:
                self._update_trailing_tp(position)
                
        except Exception as e:
            logger.error(f"Error in post-TP actions for position {position.id}: {e}")
    
    def _move_sl_to_breakeven(self, position: Position):
        """Move stop loss to breakeven"""
        try:
            # Update position stop loss to entry price
            position.stop_loss_price = position.entry_price
            db.session.commit()
            
            logger.info(f"Moved SL to breakeven for position {position.id}")
            
            # Send notification
            settings = self._get_settings()
            if settings.telegram_notifications_enabled:
                message = f"""
🛡️ Stop Loss Moved to Breakeven

📊 Position: {position.symbol}
💰 New SL: ${position.entry_price:,.4f}
✅ Risk-free mode activated!
                """
                telegram_notifier.send_notification_sync(message)
                
        except Exception as e:
            logger.error(f"Error moving SL to breakeven for position {position.id}: {e}")
    
    def _update_trailing_tp(self, position: Position):
        """Update trailing take profit levels"""
        try:
            # Get current price
            if not self.binance_client:
                return
            current_price = self.binance_client.get_current_price(position.symbol)
            if not current_price:
                return
            
            # Check if trailing should be activated
            settings = self._get_settings()
            entry_price = position.entry_price
            activation_threshold = settings.trailing_tp_activation_percent / 100
            
            if position.side == 'LONG':
                activation_price = entry_price * (1 + activation_threshold)
                if current_price >= activation_price:
                    self._activate_trailing_tp(position, current_price)
            else:
                activation_price = entry_price * (1 - activation_threshold)
                if current_price <= activation_price:
                    self._activate_trailing_tp(position, current_price)
                    
        except Exception as e:
            logger.error(f"Error updating trailing TP for position {position.id}: {e}")
    
    def _activate_trailing_tp(self, position: Position, current_price: float):
        """Activate trailing take profit"""
        try:
            settings = self._get_settings()
            callback_percent = settings.trailing_tp_callback_percent / 100
            
            # Update remaining TP levels to trail
            pending_tps = TPLevel.get_pending_for_position(position.id)
            
            for tp_level in pending_tps:
                if position.side == 'LONG':
                    new_tp_price = current_price * (1 - callback_percent)
                else:
                    new_tp_price = current_price * (1 + callback_percent)
                
                # Only update if new price is better
                if ((position.side == 'LONG' and new_tp_price > tp_level.target_price) or
                    (position.side == 'SHORT' and new_tp_price < tp_level.target_price)):
                    
                    old_price = tp_level.target_price
                    tp_level.target_price = round(new_tp_price, 8)
                    tp_level.updated_at = db.func.now()
                    
                    # Log modification
                    TPHistory.log_action(
                        position_id=position.id,
                        tp_level=tp_level.tp_level,
                        action='MODIFIED',
                        price=new_tp_price,
                        quantity=position.size * (tp_level.quantity_percent / 100),
                        notes=f'Trailing TP updated from {old_price} to {new_tp_price}'
                    )
            
            db.session.commit()
            logger.info(f"Updated trailing TP for position {position.id}")
            
        except Exception as e:
            logger.error(f"Error activating trailing TP for position {position.id}: {e}")
    
    def get_tp_summary(self, position_id: int) -> Dict:
        """Get TP summary for a position"""
        try:
            pending_tps = TPLevel.get_pending_for_position(position_id)
            executed_tps = TPLevel.get_executed_for_position(position_id)
            tp_history = TPHistory.get_for_position(position_id)
            
            total_executed_pnl = sum([h.pnl for h in tp_history if h.pnl and h.action == 'EXECUTED'])
            
            return {
                'pending_tps': [tp.to_dict() for tp in pending_tps],
                'executed_tps': [tp.to_dict() for tp in executed_tps],
                'tp_history': [h.to_dict() for h in tp_history],
                'total_executed_pnl': total_executed_pnl,
                'total_tp_levels': len(pending_tps) + len(executed_tps),
                'executed_count': len(executed_tps)
            }
            
        except Exception as e:
            logger.error(f"Error getting TP summary for position {position_id}: {e}")
            return {}
    
    def setup_multiple_tp_levels(self, position):
        """Setup multiple TP levels for a new position (alias for create_tp_levels_for_position)"""
        return self.create_tp_levels_for_position(position)
    
    def update_trailing_tp(self, position, current_price):
        """Update trailing TP based on current price (alias for _update_trailing_tp)"""
        self._update_trailing_tp(position)
    
    def cancel_all_tp_levels(self, position_id: int) -> bool:
        """Cancel all pending TP levels for a position"""
        try:
            pending_tps = TPLevel.get_pending_for_position(position_id)
            
            for tp_level in pending_tps:
                tp_level.cancel()
                
                # Log cancellation
                TPHistory.log_action(
                    position_id=position_id,
                    tp_level=tp_level.tp_level,
                    action='CANCELLED',
                    price=tp_level.target_price,
                    quantity=0,
                    notes=f'TP{tp_level.tp_level} cancelled'
                )
            
            logger.info(f"Cancelled {len(pending_tps)} TP levels for position {position_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling TP levels for position {position_id}: {e}")
            return False