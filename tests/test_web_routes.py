"""
Tests for web routes and API endpoints
"""
import pytest
import json
from app import db
from app.models.settings import Settings
from app.models.signal import Signal
from app.models.position import Position


class TestWebRoutes:
    """Test web routes."""
    
    def test_dashboard_route(self, client):
        """Test dashboard route."""
        response = client.get('/dashboard')
        assert response.status_code == 200
        assert b'Trading Bot Dashboard' in response.data
    
    def test_settings_route(self, client):
        """Test settings route."""
        response = client.get('/settings')
        assert response.status_code == 200
        assert b'Bot Ayarları' in response.data
    
    def test_positions_route(self, client):
        """Test positions route."""
        response = client.get('/positions')
        assert response.status_code == 200
        assert b'Açık Pozisyonlar' in response.data
    
    def test_signals_route(self, client):
        """Test signals route."""
        response = client.get('/signals')
        assert response.status_code == 200
        assert b'Sinyal Geçmişi' in response.data
    
    def test_trades_route(self, client):
        """Test trades route."""
        response = client.get('/trades')
        assert response.status_code == 200
        assert b'İşlem Geçmişi' in response.data
    
    def test_risk_management_route(self, client):
        """Test risk management route."""
        response = client.get('/risk_management')
        assert response.status_code == 200
        assert b'Risk Yönetimi' in response.data


class TestAPIEndpoints:
    """Test API endpoints."""
    
    def test_status_endpoint(self, client):
        """Test status API endpoint."""
        response = client.get('/api/status')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'status' in data
        assert 'timestamp' in data
        assert 'uptime' in data
    
    def test_binance_settings_endpoint(self, client, app):
        """Test Binance settings API endpoint."""
        with app.app_context():
            # Test POST request
            settings_data = {
                'api_key': 'test_api_key',
                'secret_key': 'test_secret_key',
                'testnet_mode': True
            }
            
            response = client.post('/api/settings/binance',
                                 data=json.dumps(settings_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Verify settings were saved
            settings = Settings.query.first()
            assert settings is not None
            assert settings.get_binance_api_key() == 'test_api_key'
            assert settings.testnet_mode is True
    
    def test_trading_settings_endpoint(self, client, app):
        """Test trading settings API endpoint."""
        with app.app_context():
            settings_data = {
                'default_leverage': 20,
                'max_concurrent_positions': 5,
                'position_sizing_method': 'percentage',
                'max_position_size_percent': 10.0,
                'max_position_size_usdt': 50.0
            }
            
            response = client.post('/api/settings/trading',
                                 data=json.dumps(settings_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Verify settings were saved
            settings = Settings.query.first()
            assert settings.default_leverage == 20
            assert settings.position_sizing_method == 'percentage'
    
    def test_risk_settings_endpoint(self, client, app):
        """Test risk settings API endpoint."""
        with app.app_context():
            risk_data = {
                'use_stop_loss': True,
                'use_take_profit': True,
                'trailing_stop_enabled': False,
                'trailing_stop_percent': 2.0,
                'daily_loss_limit': 200.0,
                'daily_loss_limit_enabled': True,
                'max_concurrent_positions': 4,
                'max_concurrent_positions_enabled': True
            }
            
            response = client.post('/api/settings/risk',
                                 data=json.dumps(risk_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Verify settings were saved
            settings = Settings.query.first()
            assert settings.use_stop_loss is True
            assert settings.daily_loss_limit_enabled is True
            assert settings.daily_loss_limit == 200.0
    
    def test_telegram_settings_endpoint(self, client, app):
        """Test Telegram settings API endpoint."""
        with app.app_context():
            telegram_data = {
                'telegram_bot_token': 'test_bot_token',
                'telegram_chat_id': '123456789',
                'telegram_notifications_enabled': True
            }
            
            response = client.post('/api/settings/telegram',
                                 data=json.dumps(telegram_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Verify settings were saved
            settings = Settings.query.first()
            assert settings.get_telegram_bot_token() == 'test_bot_token'
            assert settings.telegram_chat_id == '123456789'
    
    def test_symbols_settings_endpoint(self, client, app):
        """Test symbols settings API endpoint."""
        with app.app_context():
            symbols_data = {
                'allowed_symbols': 'BTCUSDT, ETHUSDT, ADAUSDT'
            }
            
            response = client.post('/api/settings/symbols',
                                 data=json.dumps(symbols_data),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Verify settings were saved
            settings = Settings.query.first()
            assert settings.allowed_symbols == 'BTCUSDT, ETHUSDT, ADAUSDT'
    
    def test_positions_api_endpoint(self, client, app, sample_position_data):
        """Test positions API endpoint."""
        with app.app_context():
            # Create test position
            position = Position(
                symbol=sample_position_data['symbol'],
                side=sample_position_data['side'],
                size=sample_position_data['size'],
                entry_price=sample_position_data['entry_price'],
                leverage=sample_position_data['leverage']
            )
            db.session.add(position)
            db.session.commit()
            
            response = client.get('/api/positions')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert len(data) == 1
            assert data[0]['symbol'] == 'BTCUSDT'
            assert data[0]['side'] == 'LONG'
    
    def test_signals_api_endpoint(self, client, app, sample_signal_data):
        """Test signals API endpoint."""
        with app.app_context():
            # Create test signal
            signal = Signal(
                symbol=sample_signal_data['symbol'],
                action=sample_signal_data['action'],
                price=sample_signal_data['price']
            )
            db.session.add(signal)
            db.session.commit()
            
            response = client.get('/api/signals')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert len(data) == 1
            assert data[0]['symbol'] == 'BTCUSDT'
            assert data[0]['action'] == 'buy'
    
    def test_invalid_json_request(self, client):
        """Test handling of invalid JSON requests."""
        response = client.post('/api/settings/binance',
                             data='invalid json',
                             content_type='application/json')
        
        assert response.status_code == 400
    
    def test_missing_required_fields(self, client):
        """Test handling of missing required fields."""
        incomplete_data = {
            'api_key': 'test_key'
            # missing secret_key
        }
        
        response = client.post('/api/settings/binance',
                             data=json.dumps(incomplete_data),
                             content_type='application/json')
        
        # Should still work, just with partial data
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling."""
    
    def test_404_error(self, client):
        """Test 404 error handling."""
        response = client.get('/nonexistent-route')
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client):
        """Test method not allowed error."""
        response = client.delete('/api/status')
        assert response.status_code == 405
    
    def test_database_error_handling(self, client, app):
        """Test database error handling."""
        with app.app_context():
            # This test would require more complex setup to simulate DB errors
            # For now, just test that the endpoint exists
            response = client.get('/api/status')
            assert response.status_code == 200


class TestAuthentication:
    """Test authentication and security."""
    
    def test_api_endpoints_accessible(self, client):
        """Test that API endpoints are accessible (no auth required for now)."""
        endpoints = [
            '/api/status',
            '/api/positions',
            '/api/signals',
            '/api/trades'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
    
    def test_web_routes_accessible(self, client):
        """Test that web routes are accessible."""
        routes = [
            '/dashboard',
            '/settings',
            '/positions',
            '/signals',
            '/trades',
            '/risk_management'
        ]
        
        for route in routes:
            response = client.get(route)
            assert response.status_code == 200