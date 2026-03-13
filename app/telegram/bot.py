"""
Telegram Bot Integration
Handles notifications and bot commands
"""

import asyncio
import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from app.models import BotSettings, Trade, Position, Signal
from app.models.trade import TradeStatus
from app.models.position import PositionStatus
from datetime import datetime, timedelta
from typing import Optional
import threading
import time

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.application: Optional[Application] = None
        self.settings = BotSettings.get_settings()
        self._loop = None
        self._loop_thread = None
        self._last_message_time = 0
        self._message_cooldown = 1.0  # 1 saniye cooldown
        self._initialize_bot()
    
    def _initialize_bot(self):
        """Initialize Telegram bot - simplified version without Application"""
        try:
            token = self.settings.get_telegram_bot_token()
            if not token:
                logger.warning("Telegram bot token not configured")
                return
            
            # Create only the bot instance for sending messages
            self.bot = Bot(token=token)
            
            # Test the bot connection
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                me = loop.run_until_complete(self.bot.get_me())
                logger.info(f"Telegram bot initialized successfully: @{me.username}")
                loop.close()
            except Exception as test_error:
                logger.warning(f"Could not test bot connection: {test_error}")
            
            # Don't initialize Application to avoid Updater issues
            self.application = None
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self.bot = None
            self.application = None
    
    def _start_event_loop(self):
        """Start dedicated event loop for Telegram operations"""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        
        # Wait for loop to be ready
        while self._loop is None:
            time.sleep(0.1)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🤖 **Trading Bot Hoşgeldiniz!**

Bu bot TradingView sinyalleri ile Binance Futures üzerinde otomatik işlem yapar.

**Komutlar:**
/status - Bot durumu
/positions - Açık pozisyonlar
/trades - Son işlemler
/stop - Acil durdurma
/help - Yardım

⚠️ **Uyarı:** Bu bot gerçek para ile işlem yapar. Dikkatli kullanın!
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            settings = BotSettings.get_settings()
            
            status_emoji = "🟢" if settings.bot_enabled and not settings.emergency_stop else "🔴"
            emergency_emoji = "🚨" if settings.emergency_stop else "✅"
            
            message = f"""
{status_emoji} **Bot Durumu**

**Genel Durum:**
• Bot Aktif: {'✅ Evet' if settings.bot_enabled else '❌ Hayır'}
• Acil Durum: {emergency_emoji} {'Aktif' if settings.emergency_stop else 'Normal'}
• Kaldıraç: {settings.default_leverage}x

**Risk Yönetimi:**
• Max Pozisyon: %{settings.max_position_size_percent}
• Günlük Limit: %{settings.max_daily_loss_percent}
• Max Eş Zamanlı: {settings.max_concurrent_positions}

**Açık Pozisyonlar:** {len(Position.get_open_positions())}
            """
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text("❌ Durum bilgisi alınırken hata oluştu.")
    
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command"""
        try:
            positions = Position.get_open_positions()
            
            if not positions:
                await update.message.reply_text("📊 Açık pozisyon bulunmuyor.")
                return
            
            message = "📊 **Açık Pozisyonlar:**\n\n"
            
            for pos in positions:
                side_emoji = "🟢" if pos.side.value == "long" else "🔴"
                pnl_emoji = "💚" if pos.unrealized_pnl >= 0 else "❤️"
                
                message += f"""
{side_emoji} **{pos.symbol}** ({pos.side.value.upper()})
• Boyut: {pos.size}
• Giriş: ${pos.entry_price:,.2f}
• Güncel: ${pos.mark_price:,.2f} 
• PnL: {pnl_emoji} ${pos.unrealized_pnl:,.2f}
• Kaldıraç: {pos.leverage}x
---
                """
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in positions command: {e}")
            await update.message.reply_text("❌ Pozisyon bilgisi alınırken hata oluştu.")
    
    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command"""
        try:
            # Son 10 işlemi getir
            trades = Trade.query.order_by(Trade.created_at.desc()).limit(10).all()
            
            if not trades:
                await update.message.reply_text("📈 Henüz işlem bulunmuyor.")
                return
            
            message = "📈 **Son İşlemler:**\n\n"
            
            for trade in trades:
                status_emoji = {
                    TradeStatus.OPEN: "🟡",
                    TradeStatus.CLOSED: "✅",
                    TradeStatus.ERROR: "❌",
                    TradeStatus.CANCELLED: "⚪"
                }.get(trade.status, "❓")
                
                type_emoji = "🟢" if trade.trade_type.value == "long" else "🔴"
                
                message += f"""
{status_emoji} **{trade.symbol}** {type_emoji}
• Tip: {trade.trade_type.value.upper()}
• Miktar: {trade.quantity}
• Durum: {trade.status.value}
"""
                
                if trade.net_pnl:
                    pnl_emoji = "💚" if trade.net_pnl >= 0 else "❤️"
                    message += f"• PnL: {pnl_emoji} ${trade.net_pnl:,.2f}\n"
                
                message += "---\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in trades command: {e}")
            await update.message.reply_text("❌ İşlem geçmişi alınırken hata oluştu.")
    
    async def emergency_stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        try:
            # Import here to avoid circular imports
            from app.api.trading_engine import trading_engine
            
            success = trading_engine.emergency_stop_all()
            
            if success:
                message = """
🚨 **ACİL DURDURMA AKTİF!**

• Tüm pozisyonlar kapatılıyor
• Yeni sinyaller işlenmiyor
• Bot durduruldu

⚠️ Yeniden başlatmak için web panelini kullanın.
                """
            else:
                message = "❌ Acil durdurma sırasında hata oluştu!"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in emergency stop command: {e}")
            await update.message.reply_text("❌ Acil durdurma komutu çalıştırılırken hata oluştu.")
    
    async def get_chat_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /getchatid command"""
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            username = update.effective_user.username or "Bilinmiyor"
            first_name = update.effective_user.first_name or "Bilinmiyor"
            
            message = f"""
🆔 **Chat ID Bilgileri**

**Chat ID:** `{chat_id}`
**User ID:** `{user_id}`
**Kullanıcı Adı:** @{username}
**İsim:** {first_name}

📋 **Nasıl Kullanılır:**
1. Yukarıdaki Chat ID'yi kopyalayın
2. Web panelindeki Telegram ayarlarına gidin
3. Chat ID alanına yapıştırın
4. Ayarları kaydedin

✅ Bu Chat ID'yi web panelinde kullanarak bildirimler alabilirsiniz!
            """
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in get_chat_id command: {e}")
            await update.message.reply_text("❌ Chat ID alınırken hata oluştu.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
🤖 **Trading Bot Komutları**

**/start** - Bot'u başlat ve hoşgeldin mesajı
**/status** - Bot durumu ve ayarları
**/positions** - Açık pozisyonları göster
**/trades** - Son işlemleri göster
**/stop** - Acil durdurma (tüm pozisyonları kapat)
**/getchatid** - Chat ID'nizi öğrenin (ayarlar için gerekli)
**/help** - Bu yardım mesajı

**Bildirim Türleri:**
• 🟢 Pozisyon açılışı
• 🔴 Pozisyon kapanışı
• 💰 Kar/zarar bildirimleri
• ⚠️ Hata bildirimleri
• 📊 Günlük özet

**Destek:** Web paneli üzerinden ayarları değiştirebilirsiniz.
        """
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def send_notification(self, message: str, parse_mode: str = 'Markdown'):
        """Send notification to configured chat"""
        try:
            # Rate limiting check
            current_time = time.time()
            if current_time - self._last_message_time < self._message_cooldown:
                logger.warning("Rate limiting: Message skipped due to cooldown")
                return False
            
            # Her seferinde güncel ayarları al
            current_settings = BotSettings.get_settings()
            
            if not self.bot or not current_settings.telegram_chat_id:
                logger.warning("Telegram bot or chat ID not configured")
                return False
            
            # Check if notifications are enabled
            if not current_settings.telegram_notifications_enabled:
                logger.info("Telegram notifications are disabled")
                return False
            
            await self.bot.send_message(
                chat_id=current_settings.telegram_chat_id,
                text=message,
                parse_mode=parse_mode
            )
            
            self._last_message_time = current_time
            logger.info("Telegram notification sent successfully")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False
    
    def send_notification_sync(self, message: str, parse_mode: str = 'Markdown'):
        """Send notification synchronously using requests"""
        try:
            # Get current settings
            current_settings = BotSettings.get_settings()
            
            if not current_settings.telegram_chat_id:
                logger.warning("Telegram chat ID not configured")
                return False
            
            # Check if notifications are enabled
            if not current_settings.telegram_notifications_enabled:
                logger.info("Telegram notifications are disabled")
                return False
            
            # Get token
            token = current_settings.get_telegram_bot_token()
            if not token:
                logger.warning("Telegram bot token not configured")
                return False
            
            # Rate limiting check
            import time
            current_time = time.time()
            if current_time - self._last_message_time < self._message_cooldown:
                logger.warning("Rate limiting: Message skipped due to cooldown")
                return False
            
            # Send message using requests (synchronous)
            import requests
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                'chat_id': current_settings.telegram_chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    self._last_message_time = current_time
                    logger.info("Telegram notification sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {result.get('description', 'Unknown error')}")
                    return False
            else:
                logger.error(f"HTTP error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False
    
    def send_trade_notification(self, trade, action: str):
        """Send trade notification"""
        try:
            # Get current settings
            current_settings = BotSettings.get_settings()
            
            if not current_settings.notify_on_trade_open and action == "opened":
                return
            if not current_settings.notify_on_trade_close and action == "closed":
                return
            
            action_emoji = "🟢" if action == "opened" else "🔴"
            type_emoji = "📈" if trade.trade_type.value == "long" else "📉"
            
            message = f"""
{action_emoji} **Pozisyon {action.upper()}**

{type_emoji} **{trade.symbol}** - {trade.trade_type.value.upper()}
• Miktar: {trade.quantity}
• Fiyat: ${trade.entry_price or trade.exit_price:,.2f}
• Kaldıraç: {trade.leverage}x
            """
            
            if action == "closed" and trade.net_pnl is not None:
                pnl_emoji = "💚" if trade.net_pnl >= 0 else "❤️"
                message += f"\n• PnL: {pnl_emoji} ${trade.net_pnl:,.2f}"
            
            if trade.stop_loss:
                message += f"\n• Stop Loss: ${trade.stop_loss:,.2f}"
            
            if trade.take_profit:
                message += f"\n• Take Profit: ${trade.take_profit:,.2f}"
            
            message += f"\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"
            
            # Use sync method with dedicated event loop
            self.send_notification_sync(message)
            
        except Exception as e:
            logger.error(f"Error sending trade notification: {e}")
    
    def send_error_notification(self, error_message: str, context: str = ""):
        """Send error notification"""
        try:
            # Get current settings
            current_settings = BotSettings.get_settings()
            
            if not current_settings.notify_on_error:
                return
            
            message = f"""
⚠️ **HATA BİLDİRİMİ**

**Hata:** {error_message}
            """
            
            if context:
                message += f"\n**Bağlam:** {context}"
            
            message += f"\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"
            
            # Use sync method with dedicated event loop
            self.send_notification_sync(message)
            
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
    
    def send_daily_summary(self):
        """Send daily summary"""
        try:
            # Get current settings
            current_settings = BotSettings.get_settings()
            
            if not current_settings.notify_daily_summary:
                return
            
            # Get today's trades
            today = datetime.now().date()
            today_trades = Trade.query.filter(
                Trade.created_at >= today,
                Trade.status == TradeStatus.CLOSED
            ).all()
            
            total_pnl = sum(trade.net_pnl or 0 for trade in today_trades)
            winning_trades = len([t for t in today_trades if (t.net_pnl or 0) > 0])
            losing_trades = len([t for t in today_trades if (t.net_pnl or 0) < 0])
            
            pnl_emoji = "💚" if total_pnl >= 0 else "❤️"
            
            message = f"""
📊 **GÜNLÜK ÖZET**

**Bugünkü Performans:**
• Toplam İşlem: {len(today_trades)}
• Kazanan: {winning_trades} 🟢
• Kaybeden: {losing_trades} 🔴
• Net PnL: {pnl_emoji} ${total_pnl:,.2f}

**Açık Pozisyonlar:** {len(Position.get_open_positions())}

**Bot Durumu:** {'🟢 Aktif' if current_settings.bot_enabled and not current_settings.emergency_stop else '🔴 Durduruldu'}

⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}
            """
            
            # Use sync method with dedicated event loop
            self.send_notification_sync(message)
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
    
    def start_bot(self):
        """Start the Telegram bot"""
        try:
            if not self.application:
                logger.warning("Telegram application not initialized")
                return
            
            # Run in a separate thread with proper error handling
            def run_bot():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Initialize and start the application
                    loop.run_until_complete(self.application.initialize())
                    loop.run_until_complete(self.application.start())
                    
                    # Start polling
                    loop.run_until_complete(self.application.updater.start_polling())
                    
                    # Keep the loop running
                    loop.run_forever()
                    
                except Exception as e:
                    logger.error(f"Error in bot thread: {e}")
            
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            
            logger.info("Telegram bot started successfully")
            
        except Exception as e:
            logger.error(f"Error starting Telegram bot: {e}")

# Global telegram notifier instance
telegram_notifier = TelegramNotifier()