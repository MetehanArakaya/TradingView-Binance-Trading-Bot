"""
Test configuration and fixtures
"""
import pytest
import tempfile
import os
from app import create_app, db
from app.models.settings import Settings
from app.models.signal import Signal
from app.models.position import Position
from app.models.trade import Trade
from config.settings import Config


class TestConfig(Config):
    """Test configuration."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Create a temporary file to serve as the database
    db_fd, db_path = tempfile.mkstemp()
    
    # Override database URI for testing
    TestConfig.SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
    
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        
        # Create default settings for tests
        settings = Settings()
        settings.binance_api_key = 'test_api_key'
        settings.binance_secret_key = 'test_secret_key'
        settings.default_leverage = 10
        settings.max_concurrent_positions = 3
        settings.position_sizing_method = 'fixed'
        settings.max_position_size_usdt = 10.0
        settings.use_stop_loss = True
        settings.use_take_profit = True
        settings.telegram_bot_token = 'test_bot_token'
        settings.telegram_chat_id = '123456789'
        settings.telegram_notifications_enabled = True
        settings.testnet_mode = True
        settings.daily_loss_limit_enabled = True
        settings.daily_loss_limit = 100.0
        settings.max_concurrent_positions_enabled = True
        
        db.session.add(settings)
        db.session.commit()
    
    yield app
    
    # Clean up
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


@pytest.fixture
def sample_signal_data():
    """Sample TradingView signal data for testing."""
    return {
        'symbol': 'BTCUSDT',
        'action': 'buy',
        'price': 45000.0,
        'stop_loss': 44000.0,
        'take_profit': 46000.0,
        'leverage': 10,
        'timestamp': '2024-01-01T12:00:00Z'
    }


@pytest.fixture
def sample_position_data():
    """Sample position data for testing."""
    return {
        'symbol': 'BTCUSDT',
        'side': 'LONG',
        'size': 0.001,
        'entry_price': 45000.0,
        'leverage': 10,
        'stop_loss': 44000.0,
        'take_profit': 46000.0,
        'status': 'OPEN'
    }


@pytest.fixture
def mock_binance_client():
    """Mock Binance client for testing."""
    class MockBinanceClient:
        def __init__(self):
            self._account_balance = [
                {'asset': 'USDT', 'balance': '1000.0', 'withdrawAvailable': '1000.0'}
            ]
            self._position_info = []
            self._create_order_response = {
                'orderId': 12345,
                'symbol': 'BTCUSDT',
                'status': 'FILLED',
                'executedQty': '0.001',
                'cummulativeQuoteQty': '45.0'
            }
        
        def futures_account_balance(self):
            return self._account_balance
        
        def futures_position_information(self, symbol=None):
            return self._position_info
        
        def futures_create_order(self, **kwargs):
            return self._create_order_response
        
        def futures_cancel_order(self, **kwargs):
            return {'orderId': kwargs.get('orderId'), 'status': 'CANCELED'}
        
        def futures_change_leverage(self, **kwargs):
            return {'leverage': kwargs.get('leverage'), 'symbol': kwargs.get('symbol')}
    
    return MockBinanceClient()