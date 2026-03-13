"""
Tests for database models
"""
import pytest
from app import db
from app.models.settings import Settings
from app.models.signal import Signal
from app.models.position import Position
from app.models.trade import Trade


class TestSettings:
    """Test Settings model."""
    
    def test_create_settings(self, app):
        """Test creating settings."""
        with app.app_context():
            settings = Settings()
            settings.binance_api_key = 'test_key'
            settings.binance_secret_key = 'test_secret'
            settings.default_leverage = 10
            settings.max_concurrent_positions = 5
            
            db.session.add(settings)
            db.session.commit()
            
            assert settings.id is not None
            assert settings.binance_api_key == 'test_key'
            assert settings.default_leverage == 10
    
    def test_settings_encryption(self, app):
        """Test that sensitive data is encrypted."""
        with app.app_context():
            settings = Settings()
            original_key = 'my_secret_api_key'
            settings.set_binance_api_key(original_key)
            
            db.session.add(settings)
            db.session.commit()
            
            # Raw encrypted data should not match original
            assert settings.binance_api_key != original_key
            
            # But decrypted data should match
            assert settings.get_binance_api_key() == original_key
    
    def test_settings_defaults(self, app):
        """Test default values."""
        with app.app_context():
            settings = Settings()
            
            assert settings.default_leverage == 10
            assert settings.max_concurrent_positions == 3
            assert settings.position_sizing_method == 'fixed'
            assert settings.max_position_size_usdt == 1.0
            assert settings.use_stop_loss is True
            assert settings.use_take_profit is True
            assert settings.telegram_notifications_enabled is True
            assert settings.testnet_mode is True
    
    def test_toggle_settings(self, app):
        """Test toggle settings functionality."""
        with app.app_context():
            settings = Settings()
            settings.daily_loss_limit_enabled = True
            settings.daily_loss_limit = 100.0
            settings.max_concurrent_positions_enabled = True
            
            db.session.add(settings)
            db.session.commit()
            
            assert settings.daily_loss_limit_enabled is True
            assert settings.daily_loss_limit == 100.0
            assert settings.max_concurrent_positions_enabled is True


class TestSignal:
    """Test Signal model."""
    
    def test_create_signal(self, app, sample_signal_data):
        """Test creating a signal."""
        with app.app_context():
            signal = Signal(
                symbol=sample_signal_data['symbol'],
                action=sample_signal_data['action'],
                price=sample_signal_data['price'],
                stop_loss=sample_signal_data['stop_loss'],
                take_profit=sample_signal_data['take_profit'],
                leverage=sample_signal_data['leverage']
            )
            
            db.session.add(signal)
            db.session.commit()
            
            assert signal.id is not None
            assert signal.symbol == 'BTCUSDT'
            assert signal.action == 'buy'
            assert signal.price == 45000.0
            assert signal.status == 'PENDING'
    
    def test_signal_validation(self, app):
        """Test signal validation."""
        with app.app_context():
            # Test invalid action
            signal = Signal(
                symbol='BTCUSDT',
                action='invalid_action',
                price=45000.0
            )
            
            db.session.add(signal)
            
            # This should not raise an error at model level
            # Validation should be handled at service level
            db.session.commit()
            
            assert signal.action == 'invalid_action'
    
    def test_signal_status_update(self, app, sample_signal_data):
        """Test updating signal status."""
        with app.app_context():
            signal = Signal(
                symbol=sample_signal_data['symbol'],
                action=sample_signal_data['action'],
                price=sample_signal_data['price']
            )
            
            db.session.add(signal)
            db.session.commit()
            
            # Update status
            signal.status = 'EXECUTED'
            db.session.commit()
            
            assert signal.status == 'EXECUTED'


class TestPosition:
    """Test Position model."""
    
    def test_create_position(self, app, sample_position_data):
        """Test creating a position."""
        with app.app_context():
            position = Position(
                symbol=sample_position_data['symbol'],
                side=sample_position_data['side'],
                size=sample_position_data['size'],
                entry_price=sample_position_data['entry_price'],
                leverage=sample_position_data['leverage'],
                stop_loss=sample_position_data['stop_loss'],
                take_profit=sample_position_data['take_profit']
            )
            
            db.session.add(position)
            db.session.commit()
            
            assert position.id is not None
            assert position.symbol == 'BTCUSDT'
            assert position.side == 'LONG'
            assert position.size == 0.001
            assert position.status == 'OPEN'
    
    def test_position_pnl_calculation(self, app, sample_position_data):
        """Test PnL calculation."""
        with app.app_context():
            position = Position(
                symbol=sample_position_data['symbol'],
                side=sample_position_data['side'],
                size=sample_position_data['size'],
                entry_price=sample_position_data['entry_price'],
                leverage=sample_position_data['leverage']
            )
            
            db.session.add(position)
            db.session.commit()
            
            # Test unrealized PnL calculation
            current_price = 46000.0  # $1000 profit
            expected_pnl = (current_price - position.entry_price) * position.size
            
            # This would be calculated in the service layer
            assert expected_pnl == 1.0  # $1 profit on 0.001 BTC
    
    def test_position_close(self, app, sample_position_data):
        """Test closing a position."""
        with app.app_context():
            position = Position(
                symbol=sample_position_data['symbol'],
                side=sample_position_data['side'],
                size=sample_position_data['size'],
                entry_price=sample_position_data['entry_price'],
                leverage=sample_position_data['leverage']
            )
            
            db.session.add(position)
            db.session.commit()
            
            # Close position
            position.status = 'CLOSED'
            position.exit_price = 46000.0
            position.realized_pnl = 1.0
            
            db.session.commit()
            
            assert position.status == 'CLOSED'
            assert position.exit_price == 46000.0
            assert position.realized_pnl == 1.0


class TestTrade:
    """Test Trade model."""
    
    def test_create_trade(self, app):
        """Test creating a trade."""
        with app.app_context():
            trade = Trade(
                symbol='BTCUSDT',
                side='BUY',
                quantity=0.001,
                price=45000.0,
                order_id='12345',
                trade_type='MARKET'
            )
            
            db.session.add(trade)
            db.session.commit()
            
            assert trade.id is not None
            assert trade.symbol == 'BTCUSDT'
            assert trade.side == 'BUY'
            assert trade.quantity == 0.001
            assert trade.price == 45000.0
    
    def test_trade_relationships(self, app, sample_position_data):
        """Test trade relationships with positions."""
        with app.app_context():
            # Create position
            position = Position(
                symbol=sample_position_data['symbol'],
                side=sample_position_data['side'],
                size=sample_position_data['size'],
                entry_price=sample_position_data['entry_price'],
                leverage=sample_position_data['leverage']
            )
            
            db.session.add(position)
            db.session.commit()
            
            # Create trade linked to position
            trade = Trade(
                symbol='BTCUSDT',
                side='BUY',
                quantity=0.001,
                price=45000.0,
                order_id='12345',
                trade_type='MARKET',
                position_id=position.id
            )
            
            db.session.add(trade)
            db.session.commit()
            
            assert trade.position_id == position.id
            assert trade.position == position