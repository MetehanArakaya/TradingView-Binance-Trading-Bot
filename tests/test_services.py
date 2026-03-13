"""
Tests for service layer components
"""
import pytest
from unittest.mock import patch, MagicMock
from app import db
from app.models.settings import Settings
from app.models.signal import Signal
from app.models.position import Position
from app.services.trading_service import TradingService
from app.services.risk_manager import RiskManager


class TestTradingService:
    """Test TradingService."""
    
    @patch('app.services.binance_client.BinanceClient')
    def test_process_buy_signal(self, mock_binance_class, app, sample_signal_data, mock_binance_client):
        """Test processing a buy signal."""
        with app.app_context():
            mock_binance_class.return_value = mock_binance_client
            
            # Create signal
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
            
            # Process signal
            trading_service = TradingService()
            result = trading_service.process_signal(signal)
            
            assert result is True
            assert signal.status == 'EXECUTED'
    
    @patch('app.services.binance_client.BinanceClient')
    def test_process_sell_signal(self, mock_binance_class, app, mock_binance_client):
        """Test processing a sell signal."""
        with app.app_context():
            mock_binance_class.return_value = mock_binance_client
            
            signal = Signal(
                symbol='BTCUSDT',
                action='sell',
                price=45000.0,
                stop_loss=46000.0,
                take_profit=44000.0,
                leverage=10
            )
            db.session.add(signal)
            db.session.commit()
            
            trading_service = TradingService()
            result = trading_service.process_signal(signal)
            
            assert result is True
            assert signal.status == 'EXECUTED'
    
    @patch('app.services.binance_client.BinanceClient')
    def test_process_close_signal(self, mock_binance_class, app, mock_binance_client, sample_position_data):
        """Test processing a close signal."""
        with app.app_context():
            mock_binance_class.return_value = mock_binance_client
            
            # Create open position
            position = Position(
                symbol=sample_position_data['symbol'],
                side=sample_position_data['side'],
                size=sample_position_data['size'],
                entry_price=sample_position_data['entry_price'],
                leverage=sample_position_data['leverage']
            )
            db.session.add(position)
            db.session.commit()
            
            # Create close signal
            signal = Signal(
                symbol='BTCUSDT',
                action='close',
                price=46000.0
            )
            db.session.add(signal)
            db.session.commit()
            
            trading_service = TradingService()
            result = trading_service.process_signal(signal)
            
            assert result is True
            assert signal.status == 'EXECUTED'
    
    @patch('app.services.binance_client.BinanceClient')
    def test_position_sizing_fixed(self, mock_binance_class, app, mock_binance_client):
        """Test position sizing with fixed USDT amount."""
        with app.app_context():
            mock_binance_class.return_value = mock_binance_client
            
            # Set fixed position sizing
            settings = Settings.query.first()
            settings.position_sizing_method = 'fixed'
            settings.max_position_size_usdt = 50.0
            db.session.commit()
            
            signal = Signal(
                symbol='BTCUSDT',
                action='buy',
                price=50000.0,  # $50k per BTC
                leverage=10
            )
            db.session.add(signal)
            db.session.commit()
            
            trading_service = TradingService()
            position_size = trading_service._calculate_position_size(signal)
            
            # $50 / $50k = 0.001 BTC
            expected_size = 50.0 / 50000.0
            assert abs(position_size - expected_size) < 0.0001
    
    @patch('app.services.binance_client.BinanceClient')
    def test_position_sizing_percentage(self, mock_binance_class, app, mock_binance_client):
        """Test position sizing with percentage of balance."""
        with app.app_context():
            mock_binance_class.return_value = mock_binance_client
            
            # Mock account balance
            mock_binance_client._account_balance = [
                {'asset': 'USDT', 'balance': '1000.0', 'withdrawAvailable': '1000.0'}
            ]
            
            # Set percentage position sizing
            settings = Settings.query.first()
            settings.position_sizing_method = 'percentage'
            settings.max_position_size_percent = 5.0  # 5%
            db.session.commit()
            
            signal = Signal(
                symbol='BTCUSDT',
                action='buy',
                price=50000.0,
                leverage=10
            )
            db.session.add(signal)
            db.session.commit()
            
            trading_service = TradingService()
            position_size = trading_service._calculate_position_size(signal)
            
            # 5% of $1000 = $50, $50 / $50k = 0.001 BTC
            expected_size = (1000.0 * 0.05) / 50000.0
            assert abs(position_size - expected_size) < 0.0001
    
    @patch('app.services.binance_client.BinanceClient')
    def test_leverage_setting(self, mock_binance_class, app, mock_binance_client):
        """Test leverage setting."""
        with app.app_context():
            mock_binance_class.return_value = mock_binance_client
            
            signal = Signal(
                symbol='BTCUSDT',
                action='buy',
                price=45000.0,
                leverage=20
            )
            db.session.add(signal)
            db.session.commit()
            
            trading_service = TradingService()
            trading_service.process_signal(signal)
            
            # Verify leverage was set
            mock_binance_client.futures_change_leverage.assert_called_with(
                symbol='BTCUSDT',
                leverage=20
            )


class TestRiskManager:
    """Test RiskManager."""
    
    def test_check_daily_loss_limit_not_exceeded(self, app):
        """Test daily loss limit check when not exceeded."""
        with app.app_context():
            settings = Settings.query.first()
            settings.daily_loss_limit_enabled = True
            settings.daily_loss_limit = 100.0
            db.session.commit()
            
            risk_manager = RiskManager()
            
            # Mock daily loss calculation to return 50 (under limit)
            with patch.object(risk_manager, '_calculate_daily_loss', return_value=50.0):
                result = risk_manager.check_daily_loss_limit()
                assert result is True
    
    def test_check_daily_loss_limit_exceeded(self, app):
        """Test daily loss limit check when exceeded."""
        with app.app_context():
            settings = Settings.query.first()
            settings.daily_loss_limit_enabled = True
            settings.daily_loss_limit = 100.0
            db.session.commit()
            
            risk_manager = RiskManager()
            
            # Mock daily loss calculation to return 150 (over limit)
            with patch.object(risk_manager, '_calculate_daily_loss', return_value=150.0):
                result = risk_manager.check_daily_loss_limit()
                assert result is False
    
    def test_check_daily_loss_limit_disabled(self, app):
        """Test daily loss limit check when disabled."""
        with app.app_context():
            settings = Settings.query.first()
            settings.daily_loss_limit_enabled = False
            db.session.commit()
            
            risk_manager = RiskManager()
            result = risk_manager.check_daily_loss_limit()
            assert result is True
    
    def test_check_max_positions_not_exceeded(self, app):
        """Test max positions check when not exceeded."""
        with app.app_context():
            settings = Settings.query.first()
            settings.max_concurrent_positions_enabled = True
            settings.max_concurrent_positions = 3
            db.session.commit()
            
            # Create 2 open positions (under limit)
            for i in range(2):
                position = Position(
                    symbol=f'BTC{i}USDT',
                    side='LONG',
                    size=0.001,
                    entry_price=45000.0,
                    leverage=10,
                    status='OPEN'
                )
                db.session.add(position)
            db.session.commit()
            
            risk_manager = RiskManager()
            result = risk_manager.check_max_positions()
            assert result is True
    
    def test_check_max_positions_exceeded(self, app):
        """Test max positions check when exceeded."""
        with app.app_context():
            settings = Settings.query.first()
            settings.max_concurrent_positions_enabled = True
            settings.max_concurrent_positions = 2
            db.session.commit()
            
            # Create 3 open positions (over limit)
            for i in range(3):
                position = Position(
                    symbol=f'BTC{i}USDT',
                    side='LONG',
                    size=0.001,
                    entry_price=45000.0,
                    leverage=10,
                    status='OPEN'
                )
                db.session.add(position)
            db.session.commit()
            
            risk_manager = RiskManager()
            result = risk_manager.check_max_positions()
            assert result is False
    
    def test_check_max_positions_disabled(self, app):
        """Test max positions check when disabled."""
        with app.app_context():
            settings = Settings.query.first()
            settings.max_concurrent_positions_enabled = False
            db.session.commit()
            
            risk_manager = RiskManager()
            result = risk_manager.check_max_positions()
            assert result is True
    
    def test_validate_signal_valid(self, app, sample_signal_data):
        """Test signal validation with valid signal."""
        with app.app_context():
            signal = Signal(
                symbol=sample_signal_data['symbol'],
                action=sample_signal_data['action'],
                price=sample_signal_data['price'],
                stop_loss=sample_signal_data['stop_loss'],
                take_profit=sample_signal_data['take_profit'],
                leverage=sample_signal_data['leverage']
            )
            
            risk_manager = RiskManager()
            result = risk_manager.validate_signal(signal)
            assert result is True
    
    def test_validate_signal_invalid_price(self, app):
        """Test signal validation with invalid price."""
        with app.app_context():
            signal = Signal(
                symbol='BTCUSDT',
                action='buy',
                price=0.0,  # Invalid price
                leverage=10
            )
            
            risk_manager = RiskManager()
            result = risk_manager.validate_signal(signal)
            assert result is False
    
    def test_validate_signal_invalid_leverage(self, app):
        """Test signal validation with invalid leverage."""
        with app.app_context():
            signal = Signal(
                symbol='BTCUSDT',
                action='buy',
                price=45000.0,
                leverage=200  # Too high
            )
            
            risk_manager = RiskManager()
            result = risk_manager.validate_signal(signal)
            assert result is False
    
    def test_calculate_stop_loss_buy(self, app):
        """Test stop loss calculation for buy signal."""
        with app.app_context():
            signal = Signal(
                symbol='BTCUSDT',
                action='buy',
                price=45000.0,
                stop_loss=44000.0
            )
            
            risk_manager = RiskManager()
            stop_loss = risk_manager.calculate_stop_loss(signal)
            assert stop_loss == 44000.0
    
    def test_calculate_stop_loss_sell(self, app):
        """Test stop loss calculation for sell signal."""
        with app.app_context():
            signal = Signal(
                symbol='BTCUSDT',
                action='sell',
                price=45000.0,
                stop_loss=46000.0
            )
            
            risk_manager = RiskManager()
            stop_loss = risk_manager.calculate_stop_loss(signal)
            assert stop_loss == 46000.0
    
    def test_calculate_take_profit_buy(self, app):
        """Test take profit calculation for buy signal."""
        with app.app_context():
            signal = Signal(
                symbol='BTCUSDT',
                action='buy',
                price=45000.0,
                take_profit=46000.0
            )
            
            risk_manager = RiskManager()
            take_profit = risk_manager.calculate_take_profit(signal)
            assert take_profit == 46000.0
    
    def test_calculate_take_profit_sell(self, app):
        """Test take profit calculation for sell signal."""
        with app.app_context():
            signal = Signal(
                symbol='BTCUSDT',
                action='sell',
                price=45000.0,
                take_profit=44000.0
            )
            
            risk_manager = RiskManager()
            take_profit = risk_manager.calculate_take_profit(signal)
            assert take_profit == 44000.0


class TestIntegration:
    """Integration tests for services."""
    
    @patch('app.services.binance_client.BinanceClient')
    @patch('app.telegram.bot.send_notification')
    def test_full_signal_processing_flow(self, mock_telegram, mock_binance_class, app, mock_binance_client, sample_signal_data):
        """Test full signal processing flow."""
        with app.app_context():
            mock_binance_class.return_value = mock_binance_client
            mock_telegram.return_value = True
            
            # Create signal
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
            
            # Process signal through full flow
            trading_service = TradingService()
            result = trading_service.process_signal(signal)
            
            # Verify signal was processed
            assert result is True
            assert signal.status == 'EXECUTED'
            
            # Verify position was created
            position = Position.query.filter_by(symbol=signal.symbol).first()
            assert position is not None
            assert position.status == 'OPEN'
            
            # Verify Telegram notification was sent
            mock_telegram.assert_called()