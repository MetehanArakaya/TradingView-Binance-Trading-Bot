"""
Tests for webhook endpoints
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from app import db
from app.models.signal import Signal


class TestWebhookEndpoints:
    """Test webhook endpoints."""
    
    def test_tradingview_webhook_valid_signal(self, client, app, sample_signal_data):
        """Test TradingView webhook with valid signal."""
        with app.app_context():
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(sample_signal_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'message' in data
            
            # Verify signal was saved to database
            signal = Signal.query.first()
            assert signal is not None
            assert signal.symbol == sample_signal_data['symbol']
            assert signal.action == sample_signal_data['action']
            assert signal.price == sample_signal_data['price']
    
    def test_tradingview_webhook_invalid_json(self, client):
        """Test TradingView webhook with invalid JSON."""
        response = client.post('/webhook/tradingview',
                             data='invalid json',
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'error' in data
    
    def test_tradingview_webhook_missing_fields(self, client, app):
        """Test TradingView webhook with missing required fields."""
        with app.app_context():
            incomplete_signal = {
                'symbol': 'BTCUSDT',
                # missing action, price, etc.
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(incomplete_signal),
                                 content_type='application/json')
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'error' in data
    
    def test_tradingview_webhook_invalid_action(self, client, app):
        """Test TradingView webhook with invalid action."""
        with app.app_context():
            invalid_signal = {
                'symbol': 'BTCUSDT',
                'action': 'invalid_action',
                'price': 45000.0,
                'timestamp': '2024-01-01T12:00:00Z'
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(invalid_signal),
                                 content_type='application/json')
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'Invalid action' in data['error']
    
    def test_tradingview_webhook_invalid_symbol(self, client, app):
        """Test TradingView webhook with invalid symbol format."""
        with app.app_context():
            invalid_signal = {
                'symbol': 'INVALID',
                'action': 'buy',
                'price': 45000.0,
                'timestamp': '2024-01-01T12:00:00Z'
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(invalid_signal),
                                 content_type='application/json')
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'Invalid symbol' in data['error']
    
    def test_tradingview_webhook_symbol_filtering(self, client, app):
        """Test symbol filtering when allowed_symbols is set."""
        with app.app_context():
            # Set allowed symbols
            from app.models.settings import Settings
            settings = Settings.query.first()
            if not settings:
                settings = Settings()
                db.session.add(settings)
            
            settings.allowed_symbols = 'BTCUSDT, ETHUSDT'
            db.session.commit()
            
            # Test allowed symbol
            allowed_signal = {
                'symbol': 'BTCUSDT',
                'action': 'buy',
                'price': 45000.0,
                'timestamp': '2024-01-01T12:00:00Z'
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(allowed_signal),
                                 content_type='application/json')
            
            assert response.status_code == 200
            
            # Test disallowed symbol
            disallowed_signal = {
                'symbol': 'ADAUSDT',
                'action': 'buy',
                'price': 1.0,
                'timestamp': '2024-01-01T12:00:00Z'
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(disallowed_signal),
                                 content_type='application/json')
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert 'not in allowed symbols' in data['error']
    
    @patch('app.services.trading_service.TradingService.process_signal')
    def test_webhook_signal_processing(self, mock_process_signal, client, app, sample_signal_data):
        """Test that webhook properly triggers signal processing."""
        with app.app_context():
            mock_process_signal.return_value = True
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(sample_signal_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
            
            # Verify that signal processing was called
            mock_process_signal.assert_called_once()
            
            # Get the signal that was passed to the service
            call_args = mock_process_signal.call_args[0]
            signal = call_args[0]
            assert signal.symbol == sample_signal_data['symbol']
            assert signal.action == sample_signal_data['action']
    
    @patch('app.services.trading_service.TradingService.process_signal')
    def test_webhook_signal_processing_failure(self, mock_process_signal, client, app, sample_signal_data):
        """Test webhook handling when signal processing fails."""
        with app.app_context():
            mock_process_signal.side_effect = Exception("Processing failed")
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(sample_signal_data),
                                 content_type='application/json')
            
            # Should still return success for webhook reception
            assert response.status_code == 200
            
            # But signal should be marked as failed
            signal = Signal.query.first()
            assert signal is not None
            assert signal.status == 'FAILED'
    
    def test_webhook_rate_limiting(self, client, app, sample_signal_data):
        """Test webhook rate limiting (if implemented)."""
        with app.app_context():
            # Send multiple requests rapidly
            responses = []
            for i in range(10):
                response = client.post('/webhook/tradingview',
                                     data=json.dumps(sample_signal_data),
                                     content_type='application/json')
                responses.append(response)
            
            # All should succeed for now (rate limiting not implemented)
            for response in responses:
                assert response.status_code == 200
    
    def test_webhook_content_type_validation(self, client, sample_signal_data):
        """Test webhook content type validation."""
        # Test with wrong content type
        response = client.post('/webhook/tradingview',
                             data=json.dumps(sample_signal_data),
                             content_type='text/plain')
        
        # Should still work or return appropriate error
        assert response.status_code in [200, 400, 415]
    
    def test_webhook_method_validation(self, client):
        """Test that webhook only accepts POST requests."""
        response = client.get('/webhook/tradingview')
        assert response.status_code == 405  # Method Not Allowed
        
        response = client.put('/webhook/tradingview')
        assert response.status_code == 405
        
        response = client.delete('/webhook/tradingview')
        assert response.status_code == 405


class TestSignalValidation:
    """Test signal validation logic."""
    
    def test_valid_buy_signal(self, client, app):
        """Test valid buy signal."""
        with app.app_context():
            signal_data = {
                'symbol': 'BTCUSDT',
                'action': 'buy',
                'price': 45000.0,
                'stop_loss': 44000.0,
                'take_profit': 46000.0,
                'leverage': 10,
                'timestamp': '2024-01-01T12:00:00Z'
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(signal_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
    
    def test_valid_sell_signal(self, client, app):
        """Test valid sell signal."""
        with app.app_context():
            signal_data = {
                'symbol': 'BTCUSDT',
                'action': 'sell',
                'price': 45000.0,
                'stop_loss': 46000.0,
                'take_profit': 44000.0,
                'leverage': 10,
                'timestamp': '2024-01-01T12:00:00Z'
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(signal_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
    
    def test_close_signal(self, client, app):
        """Test close signal."""
        with app.app_context():
            signal_data = {
                'symbol': 'BTCUSDT',
                'action': 'close',
                'price': 45000.0,
                'timestamp': '2024-01-01T12:00:00Z'
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(signal_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
    
    def test_invalid_price_values(self, client, app):
        """Test invalid price values."""
        with app.app_context():
            # Negative price
            signal_data = {
                'symbol': 'BTCUSDT',
                'action': 'buy',
                'price': -45000.0,
                'timestamp': '2024-01-01T12:00:00Z'
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(signal_data),
                                 content_type='application/json')
            
            assert response.status_code == 400
            
            # Zero price
            signal_data['price'] = 0.0
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(signal_data),
                                 content_type='application/json')
            
            assert response.status_code == 400
    
    def test_invalid_leverage_values(self, client, app):
        """Test invalid leverage values."""
        with app.app_context():
            signal_data = {
                'symbol': 'BTCUSDT',
                'action': 'buy',
                'price': 45000.0,
                'leverage': 200,  # Too high
                'timestamp': '2024-01-01T12:00:00Z'
            }
            
            response = client.post('/webhook/tradingview',
                                 data=json.dumps(signal_data),
                                 content_type='application/json')
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert 'leverage' in data['error'].lower()