from app import db
from datetime import datetime
from cryptography.fernet import Fernet
import os
import base64

class BotSettings(db.Model):
    __tablename__ = 'bot_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Bot Control
    bot_enabled = db.Column(db.Boolean, default=True)
    emergency_stop = db.Column(db.Boolean, default=False)
    
    # API Keys (encrypted)
    binance_api_key_encrypted = db.Column(db.Text)
    binance_secret_key_encrypted = db.Column(db.Text)
    telegram_bot_token_encrypted = db.Column(db.Text)
    telegram_chat_id = db.Column(db.String(50))
    testnet_mode = db.Column(db.Boolean, default=True)  # Testnet mode for safety
    
    # Risk Management Settings
    max_position_size_percent = db.Column(db.Float, default=5.0)  # % of portfolio
    max_position_size_usdt = db.Column(db.Float, default=1.0)  # Fixed USDT amount
    position_sizing_method = db.Column(db.String(20), default='percentage')  # 'percentage' or 'fixed'
    
    max_daily_loss_percent = db.Column(db.Float, default=10.0)
    max_daily_loss_usdt = db.Column(db.Float, default=5000.0)
    daily_loss_method = db.Column(db.String(20), default='percentage')
    daily_loss_limit = db.Column(db.Float, default=0.0)  # Daily loss limit in USDT (0 = unlimited)
    daily_loss_limit_enabled = db.Column(db.Boolean, default=False)  # Enable/disable daily loss limit
    
    max_concurrent_positions = db.Column(db.Integer, default=3)
    max_concurrent_positions_enabled = db.Column(db.Boolean, default=True)  # Enable/disable position limit
    default_leverage = db.Column(db.Integer, default=10)
    max_risk_percent = db.Column(db.Float, default=20.0)  # Maximum risk percentage
    
    # Stop Loss & Take Profit Settings
    use_stop_loss = db.Column(db.Boolean, default=True)
    use_take_profit = db.Column(db.Boolean, default=True)
    trailing_stop_enabled = db.Column(db.Boolean, default=False)
    trailing_stop_percent = db.Column(db.Float, default=2.0)
    
    # Percentage-based Stop Loss Settings
    percentage_sl_enabled = db.Column(db.Boolean, default=False)
    percentage_sl_percent = db.Column(db.Float, default=3.0)
    percentage_sl_portfolio_base = db.Column(db.Boolean, default=False)
    
    # ATR-based Dynamic Stop Loss Settings
    atr_sl_enabled = db.Column(db.Boolean, default=False)
    atr_sl_period = db.Column(db.Integer, default=14)
    atr_sl_multiplier = db.Column(db.Float, default=2.0)
    atr_sl_dynamic = db.Column(db.Boolean, default=False)
    
    # Breakeven Stop Loss Settings
    breakeven_sl_enabled = db.Column(db.Boolean, default=False)
    breakeven_sl_activation_percent = db.Column(db.Float, default=2.0)
    breakeven_sl_offset = db.Column(db.Float, default=0.1)
    
    # Advanced Stop Loss Features
    sl_partial_close = db.Column(db.Boolean, default=False)
    sl_partial_close_percent = db.Column(db.Float, default=50.0)
    sl_time_based_exit = db.Column(db.Boolean, default=False)
    sl_max_position_hours = db.Column(db.Integer, default=24)
    
    # Default SL/TP percentages if not provided in signal
    default_stop_loss_percent = db.Column(db.Float, default=3.0)
    default_take_profit_percent = db.Column(db.Float, default=6.0)
    
    # Advanced TP System Settings
    multiple_tp_enabled = db.Column(db.Boolean, default=False)
    tp1_percent = db.Column(db.Float, default=3.0)
    tp1_quantity_percent = db.Column(db.Float, default=33.33)
    tp2_percent = db.Column(db.Float, default=6.0)
    tp2_quantity_percent = db.Column(db.Float, default=33.33)
    tp3_percent = db.Column(db.Float, default=9.0)
    tp3_quantity_percent = db.Column(db.Float, default=33.34)
    trailing_tp_enabled = db.Column(db.Boolean, default=False)
    trailing_tp_activation_percent = db.Column(db.Float, default=5.0)
    trailing_tp_callback_percent = db.Column(db.Float, default=2.0)
    auto_move_sl_to_breakeven = db.Column(db.Boolean, default=False)
    risk_free_after_tp1 = db.Column(db.Boolean, default=False)
    scale_out_enabled = db.Column(db.Boolean, default=False)
    
    # Trading Settings
    allowed_symbols = db.Column(db.Text)  # Comma-separated list
    blacklisted_symbols = db.Column(db.Text)  # Comma-separated list
    trading_hours_start = db.Column(db.String(5), default='00:00')  # HH:MM
    trading_hours_end = db.Column(db.String(5), default='23:59')    # HH:MM
    trading_days = db.Column(db.String(20), default='1,2,3,4,5,6,7')  # 1=Monday, 7=Sunday
    
    # Notification Settings
    telegram_notifications_enabled = db.Column(db.Boolean, default=True)
    notify_on_trade_open = db.Column(db.Boolean, default=True)
    notify_on_trade_close = db.Column(db.Boolean, default=True)
    notify_on_error = db.Column(db.Boolean, default=True)
    notify_daily_summary = db.Column(db.Boolean, default=True)
    daily_summary_time = db.Column(db.String(5), default='23:00')
    
    # Webhook Security
    webhook_secret = db.Column(db.String(255))
    allowed_ips = db.Column(db.Text)  # Comma-separated list
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<BotSettings {self.id}: enabled={self.bot_enabled}>'
    
    @staticmethod
    def get_encryption_key():
        """Get or create encryption key"""
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            # Generate a new key if not exists
            key = Fernet.generate_key()
            # In production, this should be stored securely
            print(f"Generated new encryption key: {key.decode()}")
            print("Please set ENCRYPTION_KEY environment variable with this key")
        else:
            key = key.encode()
        return key
    
    def encrypt_field(self, value):
        """Encrypt a sensitive field"""
        if not value:
            return None
        key = self.get_encryption_key()
        f = Fernet(key)
        return f.encrypt(value.encode()).decode()
    
    def decrypt_field(self, encrypted_value):
        """Decrypt a sensitive field"""
        if not encrypted_value:
            return None
        try:
            key = self.get_encryption_key()
            f = Fernet(key)
            return f.decrypt(encrypted_value.encode()).decode()
        except Exception:
            return None
    
    def set_binance_api_key(self, api_key):
        """Set encrypted Binance API key"""
        self.binance_api_key_encrypted = self.encrypt_field(api_key)
    
    def get_binance_api_key(self):
        """Get decrypted Binance API key"""
        return self.decrypt_field(self.binance_api_key_encrypted)
    
    def set_binance_secret_key(self, secret_key):
        """Set encrypted Binance secret key"""
        self.binance_secret_key_encrypted = self.encrypt_field(secret_key)
    
    def get_binance_secret_key(self):
        """Get decrypted Binance secret key"""
        return self.decrypt_field(self.binance_secret_key_encrypted)
    
    def set_telegram_bot_token(self, token):
        """Set encrypted Telegram bot token"""
        self.telegram_bot_token_encrypted = self.encrypt_field(token)
    
    def get_telegram_bot_token(self):
        """Get decrypted Telegram bot token"""
        return self.decrypt_field(self.telegram_bot_token_encrypted)
    
    def get_allowed_symbols_list(self):
        """Get allowed symbols as list"""
        if not self.allowed_symbols:
            return []
        return [s.strip().upper() for s in self.allowed_symbols.split(',') if s.strip()]
    
    def get_blacklisted_symbols_list(self):
        """Get blacklisted symbols as list"""
        if not self.blacklisted_symbols:
            return []
        return [s.strip().upper() for s in self.blacklisted_symbols.split(',') if s.strip()]
    
    def get_allowed_ips_list(self):
        """Get allowed IPs as list"""
        if not self.allowed_ips:
            return []
        return [ip.strip() for ip in self.allowed_ips.split(',') if ip.strip()]
    
    def is_symbol_allowed(self, symbol):
        """Check if symbol is allowed for trading"""
        symbol = symbol.upper()
        
        # Check blacklist first
        if symbol in self.get_blacklisted_symbols_list():
            return False
        
        # If allowed list is empty, all symbols are allowed (except blacklisted)
        allowed = self.get_allowed_symbols_list()
        if not allowed:
            return True
        
        return symbol in allowed
    
    def to_dict(self):
        """Convert to dictionary (excluding sensitive data)"""
        return {
            'id': self.id,
            'bot_enabled': self.bot_enabled,
            'emergency_stop': self.emergency_stop,
            'max_position_size_percent': self.max_position_size_percent,
            'max_position_size_usdt': self.max_position_size_usdt,
            'position_sizing_method': self.position_sizing_method,
            'max_daily_loss_percent': self.max_daily_loss_percent,
            'max_daily_loss_usdt': self.max_daily_loss_usdt,
            'daily_loss_method': self.daily_loss_method,
            'daily_loss_limit': self.daily_loss_limit,
            'daily_loss_limit_enabled': self.daily_loss_limit_enabled,
            'max_concurrent_positions': self.max_concurrent_positions,
            'max_concurrent_positions_enabled': self.max_concurrent_positions_enabled,
            'default_leverage': self.default_leverage,
            'max_risk_percent': self.max_risk_percent,
            'use_stop_loss': self.use_stop_loss,
            'use_take_profit': self.use_take_profit,
            'trailing_stop_enabled': self.trailing_stop_enabled,
            'trailing_stop_percent': self.trailing_stop_percent,
            'percentage_sl_enabled': self.percentage_sl_enabled,
            'percentage_sl_percent': self.percentage_sl_percent,
            'percentage_sl_portfolio_base': self.percentage_sl_portfolio_base,
            'atr_sl_enabled': self.atr_sl_enabled,
            'atr_sl_period': self.atr_sl_period,
            'atr_sl_multiplier': self.atr_sl_multiplier,
            'atr_sl_dynamic': self.atr_sl_dynamic,
            'breakeven_sl_enabled': self.breakeven_sl_enabled,
            'breakeven_sl_activation_percent': self.breakeven_sl_activation_percent,
            'breakeven_sl_offset': self.breakeven_sl_offset,
            'sl_partial_close': self.sl_partial_close,
            'sl_partial_close_percent': self.sl_partial_close_percent,
            'sl_time_based_exit': self.sl_time_based_exit,
            'sl_max_position_hours': self.sl_max_position_hours,
            'default_stop_loss_percent': self.default_stop_loss_percent,
            'default_take_profit_percent': self.default_take_profit_percent,
            'allowed_symbols': self.allowed_symbols,
            'blacklisted_symbols': self.blacklisted_symbols,
            'trading_hours_start': self.trading_hours_start,
            'trading_hours_end': self.trading_hours_end,
            'trading_days': self.trading_days,
            'telegram_notifications_enabled': self.telegram_notifications_enabled,
            'notify_on_trade_open': self.notify_on_trade_open,
            'notify_on_trade_close': self.notify_on_trade_close,
            'notify_on_error': self.notify_on_error,
            'notify_daily_summary': self.notify_daily_summary,
            'daily_summary_time': self.daily_summary_time,
            'telegram_chat_id': self.telegram_chat_id,
            'testnet_mode': self.testnet_mode,
            'multiple_tp_enabled': self.multiple_tp_enabled,
            'tp1_percent': self.tp1_percent,
            'tp1_quantity_percent': self.tp1_quantity_percent,
            'tp2_percent': self.tp2_percent,
            'tp2_quantity_percent': self.tp2_quantity_percent,
            'tp3_percent': self.tp3_percent,
            'tp3_quantity_percent': self.tp3_quantity_percent,
            'trailing_tp_enabled': self.trailing_tp_enabled,
            'trailing_tp_activation_percent': self.trailing_tp_activation_percent,
            'trailing_tp_callback_percent': self.trailing_tp_callback_percent,
            'auto_move_sl_to_breakeven': self.auto_move_sl_to_breakeven,
            'risk_free_after_tp1': self.risk_free_after_tp1,
            'scale_out_enabled': self.scale_out_enabled,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_settings(cls):
        """Get current bot settings (create default if not exists)"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings