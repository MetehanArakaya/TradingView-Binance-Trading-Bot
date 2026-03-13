import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
# Load .env from project root directory
project_root = os.path.join(basedir, '..')
load_dotenv(os.path.join(project_root, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, '..', 'trading_bot.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 30,
        'pool_timeout': 30,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'connect_args': {
            'timeout': 60,
            'check_same_thread': False
        }
    }
    
    # Binance API
    BINANCE_API_KEY = os.environ.get('BINANCE_API_KEY')
    BINANCE_SECRET_KEY = os.environ.get('BINANCE_SECRET_KEY')
    BINANCE_TESTNET = os.environ.get('BINANCE_TESTNET', 'True').lower() == 'true'
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
    
    # TradingView Webhook
    WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET') or 'webhook-secret-key'
    
    # Risk Management Defaults
    DEFAULT_LEVERAGE = 10
    MAX_POSITION_SIZE_PERCENT = 5.0  # % of portfolio
    MAX_DAILY_LOSS_PERCENT = 10.0    # % of portfolio
    MAX_CONCURRENT_POSITIONS = 3
    
    # Security
    RATE_LIMIT_PER_MINUTE = 60
    ALLOWED_IPS = os.environ.get('ALLOWED_IPS', '').split(',') if os.environ.get('ALLOWED_IPS') else []
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/trading_bot.log')

class DevelopmentConfig(Config):
    DEBUG = True
    BINANCE_TESTNET = True

class ProductionConfig(Config):
    DEBUG = False
    BINANCE_TESTNET = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    BINANCE_TESTNET = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}