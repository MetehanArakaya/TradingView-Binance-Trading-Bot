"""
Signal Processing Service
Handles processing of TradingView signals and executes trades
"""

import logging
from typing import Optional
from datetime import datetime
from app.models import Signal, BotSettings
from app.models.signal import SignalStatus
from app import db

logger = logging.getLogger(__name__)

class SignalProcessor:
    """Processes trading signals and executes trades"""
    
    def __init__(self):
        # Import here to avoid circular imports
        from app.api.trading_engine import trading_engine
        from app.telegram.bot import telegram_notifier
        
        self.trading_engine = trading_engine
        self.telegram_notifier = telegram_notifier
    
    def process_signal(self, signal_id: int) -> bool:
        """
        Process a signal and execute trade if valid
        
        Args:
            signal_id: ID of the signal to process
            
        Returns:
            bool: True if signal was processed successfully
        """
        try:
            # Get signal from database
            signal = Signal.query.get(signal_id)
            if not signal:
                logger.error(f"Signal {signal_id} not found")
                return False
            
            # Check if signal is already processed
            if signal.status != SignalStatus.VALIDATED:
                logger.warning(f"Signal {signal_id} is not in validated status: {signal.status}")
                return False
            
            # Use existing trading engine to process the signal
            success = self.trading_engine.process_signal(signal_id)
            
            if success:
                logger.info(f"Signal {signal_id} processed successfully")
                
                # Send success notification
                self._send_signal_notification(signal, "processed")
            else:
                logger.error(f"Signal {signal_id} processing failed")
                
                # Send error notification
                self._send_signal_notification(signal, "failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing signal {signal_id}: {e}")
            try:
                signal = Signal.query.get(signal_id)
                if signal:
                    signal.mark_error(str(e))
                    db.session.commit()
                    
                    # Send error notification
                    self._send_signal_notification(signal, "error")
            except:
                pass
            return False
    
    def _send_signal_notification(self, signal: Signal, status: str):
        """Send signal processing notification via Telegram"""
        try:
            settings = BotSettings.get_settings()
            if not settings.telegram_notifications_enabled:
                return
            
            status_emoji = {
                "processed": "✅",
                "failed": "❌", 
                "error": "⚠️"
            }.get(status, "❓")
            
            action_emoji = {
                "buy": "🟢",
                "sell": "🔴",
                "close": "⚪"
            }.get(signal.signal_type.value, "❓")
            
            message = f"""
{status_emoji} **Signal {status.upper()}**

{action_emoji} **{signal.symbol}** - {signal.signal_type.value.upper()}
• Price: ${signal.price:,.2f}" if signal.price else "Market Price"
• Time: {signal.created_at.strftime('%H:%M:%S')}
• Status: {status.title()}
            """
            
            if signal.error_message and status in ["failed", "error"]:
                message += f"\n• Error: {signal.error_message}"
            
            # Send notification using telegram notifier
            self.telegram_notifier.send_notification_sync(message)
            
        except Exception as e:
            logger.error(f"Error sending signal notification: {e}")

# Global signal processor instance
signal_processor = SignalProcessor()

def process_signal_async(signal_id: int):
    """
    Process signal asynchronously
    This function can be called from webhook or used with task queue
    """
    try:
        return signal_processor.process_signal(signal_id)
    except Exception as e:
        logger.error(f"Error in async signal processing: {e}")
        return False