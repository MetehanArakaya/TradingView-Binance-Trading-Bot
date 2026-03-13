"""
Binance API Client for Futures Trading
Handles all interactions with Binance Futures API
"""

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.enums import *
import logging
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal, ROUND_DOWN
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class BinanceClient:
    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        """
        Initialize Binance client
        
        Args:
            api_key: Binance API key
            secret_key: Binance secret key
            testnet: Use testnet if True
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        
        try:
            self.client = Client(
                api_key=api_key,
                api_secret=secret_key,
                testnet=testnet
            )
            
            # Sync server time to avoid timestamp errors
            self._sync_server_time()
            
            # Test connection
            self.client.ping()
            logger.info(f"Binance client initialized successfully (testnet: {testnet})")
            
        except Exception as e:
            logger.error(f"Failed to initialize Binance client: {str(e)}")
            raise
    
    def _sync_server_time(self):
        """Sync local time with Binance server time"""
        try:
            # Get server time multiple times and use average
            server_times = []
            for _ in range(3):
                server_time = self.client.get_server_time()
                server_times.append(server_time['serverTime'])
                time.sleep(0.1)
            
            avg_server_time = sum(server_times) // len(server_times)
            local_time = int(time.time() * 1000)
            time_offset = avg_server_time - local_time
            
            # Set time offset for future requests with some buffer
            self.client.timestamp_offset = time_offset - 1000  # 1 second buffer
            logger.info(f"Time synchronized with Binance server (offset: {time_offset}ms, buffer: -1000ms)")
            
        except Exception as e:
            logger.warning(f"Could not sync server time: {e}")
            # Set a default offset if sync fails
            self.client.timestamp_offset = -5000  # 5 second buffer
    
    def get_account_info(self) -> Dict:
        """Get futures account information"""
        try:
            return self.client.futures_account()
        except BinanceAPIException as e:
            logger.error(f"Error getting account info: {e}")
            raise
    
    def get_balance(self, asset: str = 'USDT') -> float:
        """Get balance for specific asset"""
        try:
            account = self.get_account_info()
            for balance in account['assets']:
                if balance['asset'] == asset:
                    return float(balance['walletBalance'])
            return 0.0
        except Exception as e:
            logger.error(f"Error getting balance for {asset}: {e}")
            return 0.0
    
    def get_available_balance(self, asset: str = 'USDT') -> float:
        """Get available balance for trading"""
        try:
            account = self.get_account_info()
            for balance in account['assets']:
                if balance['asset'] == asset:
                    return float(balance['availableBalance'])
            return 0.0
        except Exception as e:
            logger.error(f"Error getting available balance for {asset}: {e}")
            return 0.0
    
    def get_symbol_info(self, symbol: str) -> Dict:
        """Get symbol information"""
        try:
            exchange_info = self.client.futures_exchange_info()
            for symbol_info in exchange_info['symbols']:
                if symbol_info['symbol'] == symbol:
                    return symbol_info
            raise ValueError(f"Symbol {symbol} not found")
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            raise
    
    def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            raise
    
    def get_mark_price(self, symbol: str) -> float:
        """Get mark price for symbol"""
        try:
            mark_price = self.client.futures_mark_price(symbol=symbol)
            return float(mark_price['markPrice'])
        except Exception as e:
            logger.error(f"Error getting mark price for {symbol}: {e}")
            raise
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for symbol"""
        try:
            result = self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            logger.info(f"Leverage set to {leverage}x for {symbol}")
            return True
        except BinanceAPIException as e:
            logger.error(f"Error setting leverage for {symbol}: {e}")
            return False
    
    def set_margin_type(self, symbol: str, margin_type: str = 'ISOLATED') -> bool:
        """Set margin type for symbol"""
        try:
            self.client.futures_change_margin_type(
                symbol=symbol,
                marginType=margin_type
            )
            logger.info(f"Margin type set to {margin_type} for {symbol}")
            return True
        except BinanceAPIException as e:
            # Margin type might already be set
            if e.code == -4046:
                logger.info(f"Margin type already set to {margin_type} for {symbol}")
                return True
            logger.error(f"Error setting margin type for {symbol}: {e}")
            return False
    
    def calculate_quantity(self, symbol: str, usdt_amount: float, price: float, leverage: int) -> float:
        """Calculate quantity based on USDT amount and leverage"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            
            # Find quantity precision
            quantity_precision = 0
            for filter_info in symbol_info['filters']:
                if filter_info['filterType'] == 'LOT_SIZE':
                    step_size = float(filter_info['stepSize'])
                    quantity_precision = len(str(step_size).split('.')[-1].rstrip('0'))
                    break
            
            # Calculate quantity with leverage
            notional = usdt_amount * leverage
            quantity = notional / price
            
            # Round down to symbol precision
            quantity = float(Decimal(str(quantity)).quantize(
                Decimal('0.' + '0' * quantity_precision), 
                rounding=ROUND_DOWN
            ))
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating quantity for {symbol}: {e}")
            raise
    
    def place_market_order(self, symbol: str, side: str, quantity: float,
                          reduce_only: bool = False) -> Dict:
        """Place market order"""
        try:
            # Fix quantity precision before placing order
            quantity = self._fix_quantity_precision(symbol, quantity)
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
                reduceOnly=reduce_only
            )
            
            logger.info(f"Market order placed: {symbol} {side} {quantity}")
            return order
            
        except BinanceOrderException as e:
            logger.error(f"Order error: {e}")
            raise
        except BinanceAPIException as e:
            logger.error(f"API error placing order: {e}")
            raise
    
    def place_limit_order(self, symbol: str, side: str, quantity: float,
                         price: float, time_in_force: str = TIME_IN_FORCE_GTC,
                         reduce_only: bool = False) -> Dict:
        """Place limit order"""
        try:
            # Fix quantity and price precision before placing order
            quantity = self._fix_quantity_precision(symbol, quantity)
            price = self._fix_price_precision(symbol, price)
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_LIMIT,
                quantity=quantity,
                price=price,
                timeInForce=time_in_force,
                reduceOnly=reduce_only
            )
            
            logger.info(f"Limit order placed: {symbol} {side} {quantity} @ {price}")
            return order
            
        except BinanceOrderException as e:
            logger.error(f"Order error: {e}")
            raise
        except BinanceAPIException as e:
            logger.error(f"API error placing order: {e}")
            raise
    
    def place_stop_loss_order(self, symbol: str, side: str, quantity: float,
                             stop_price: float, reduce_only: bool = True) -> Dict:
        """Place stop loss order using Binance Algo Trading API"""
        try:
            # Fix quantity and price precision before placing order
            quantity = self._fix_quantity_precision(symbol, quantity)
            stop_price = self._fix_price_precision(symbol, stop_price)
            
            # Use Algo Trading API for Stop Loss orders
            # This is the correct endpoint for SL/TP orders according to Binance API v4
            try:
                # Try using the new algo order endpoint
                response = self.client._request_futures_api(
                    'post',
                    'fapi/v1/algo/futures/newOrderVp',
                    signed=True,
                    data={
                        'symbol': symbol,
                        'side': side,
                        'type': 'STOP',
                        'quantity': quantity,
                        'stopPrice': stop_price,
                        'reduceOnly': reduce_only,
                        'timeInForce': 'GTC'
                    }
                )
                logger.info(f"Stop loss order placed via Algo API: {symbol} {side} {quantity} @ {stop_price}")
                return response
                
            except Exception as algo_error:
                logger.warning(f"Algo API failed, trying standard API: {algo_error}")
                
                # Fallback to standard API with different order type
                order_params = {
                    'symbol': symbol,
                    'side': side,
                    'type': 'STOP',  # Use STOP instead of STOP_MARKET
                    'quantity': quantity,
                    'price': stop_price,  # Use price instead of stopPrice for STOP orders
                    'timeInForce': 'GTC'
                }
                
                # Only add reduceOnly if position exists
                if reduce_only:
                    positions = self.get_position_info(symbol)
                    if positions and float(positions[0]['positionAmt']) != 0:
                        order_params['reduceOnly'] = True
                
                response = self.client.futures_create_order(**order_params)
                logger.info(f"Stop loss order placed via standard API: {symbol} {side} {quantity} @ {stop_price}")
                return response
            
        except BinanceOrderException as e:
            logger.error(f"Stop loss order error: {e}")
            raise
        except BinanceAPIException as e:
            logger.error(f"API error placing stop loss: {e}")
            raise
    
    def place_take_profit_order(self, symbol: str, side: str, quantity: float,
                               stop_price: float, reduce_only: bool = True) -> Dict:
        """Place take profit order using Binance Algo Trading API"""
        try:
            # Fix quantity and price precision before placing order
            quantity = self._fix_quantity_precision(symbol, quantity)
            stop_price = self._fix_price_precision(symbol, stop_price)
            
            # Use Algo Trading API for Take Profit orders
            # This is the correct endpoint for SL/TP orders according to Binance API v4
            try:
                # Try using the new algo order endpoint
                response = self.client._request_futures_api(
                    'post',
                    'fapi/v1/algo/futures/newOrderVp',
                    signed=True,
                    data={
                        'symbol': symbol,
                        'side': side,
                        'type': 'TAKE_PROFIT',
                        'quantity': quantity,
                        'stopPrice': stop_price,
                        'reduceOnly': reduce_only,
                        'timeInForce': 'GTC'
                    }
                )
                logger.info(f"Take profit order placed via Algo API: {symbol} {side} {quantity} @ {stop_price}")
                return response
                
            except Exception as algo_error:
                logger.warning(f"Algo API failed, trying standard API: {algo_error}")
                
                # Fallback to standard API with different order type
                order_params = {
                    'symbol': symbol,
                    'side': side,
                    'type': 'TAKE_PROFIT',  # Use TAKE_PROFIT instead of TAKE_PROFIT_MARKET
                    'quantity': quantity,
                    'price': stop_price,  # Use price instead of stopPrice for TAKE_PROFIT orders
                    'timeInForce': 'GTC'
                }
                
                # Only add reduceOnly if position exists
                if reduce_only:
                    positions = self.get_position_info(symbol)
                    if positions and float(positions[0]['positionAmt']) != 0:
                        order_params['reduceOnly'] = True
                
                response = self.client.futures_create_order(**order_params)
                logger.info(f"Take profit order placed via standard API: {symbol} {side} {quantity} @ {stop_price}")
                return response
            
        except BinanceOrderException as e:
            logger.error(f"Take profit order error: {e}")
            raise
        except BinanceAPIException as e:
            logger.error(f"API error placing take profit: {e}")
            raise
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel order"""
        try:
            result = self.client.futures_cancel_order(
                symbol=symbol,
                orderId=order_id
            )
            logger.info(f"Order cancelled: {symbol} {order_id}")
            return result
        except BinanceAPIException as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            raise
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """Cancel all open orders for symbol"""
        try:
            result = self.client.futures_cancel_all_open_orders(symbol=symbol)
            logger.info(f"All orders cancelled for {symbol}")
            return result
        except BinanceAPIException as e:
            logger.error(f"Error cancelling all orders for {symbol}: {e}")
            raise
    
    def get_order_status(self, symbol: str, order_id: int) -> Dict:
        """Get order status"""
        try:
            return self.client.futures_get_order(
                symbol=symbol,
                orderId=order_id
            )
        except BinanceAPIException as e:
            logger.error(f"Error getting order status {order_id}: {e}")
            raise
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open orders"""
        try:
            orders = self.client.futures_get_open_orders(symbol=symbol)
            return orders if isinstance(orders, list) else []
        except BinanceAPIException as e:
            logger.error(f"Error getting open orders: {e}")
            raise
    
    def get_position_info(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get position information"""
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            # Filter out positions with zero size
            if isinstance(positions, list):
                return [pos for pos in positions if float(pos['positionAmt']) != 0]
            return []
        except BinanceAPIException as e:
            logger.error(f"Error getting position info: {e}")
            raise
    
    def close_position(self, symbol: str) -> Dict:
        """Close entire position for symbol"""
        try:
            positions = self.get_position_info(symbol)
            if not positions:
                logger.info(f"No position to close for {symbol}")
                return {}
            
            position = positions[0]
            position_amt = float(position['positionAmt'])
            
            if position_amt == 0:
                logger.info(f"No position to close for {symbol}")
                return {}
            
            # Determine side for closing
            side = SIDE_SELL if position_amt > 0 else SIDE_BUY
            quantity = abs(position_amt)
            
            # Place market order to close position
            order = self.place_market_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                reduce_only=True
            )
            
            logger.info(f"Position closed for {symbol}: {quantity}")
            return order
            
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            raise
    
    def get_trade_history(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get trade history"""
        try:
            trades = self.client.futures_account_trades(symbol=symbol, limit=limit)
            return trades if isinstance(trades, list) else []
        except BinanceAPIException as e:
            logger.error(f"Error getting trade history: {e}")
            raise
    
    def _fix_quantity_precision(self, symbol: str, quantity: float) -> float:
        """Fix quantity precision according to symbol rules"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            
            # Find quantity precision from LOT_SIZE filter
            for filter_info in symbol_info['filters']:
                if filter_info['filterType'] == 'LOT_SIZE':
                    step_size = float(filter_info['stepSize'])
                    
                    # Calculate precision from step size
                    if step_size >= 1:
                        precision = 0
                    else:
                        precision = len(str(step_size).split('.')[-1].rstrip('0'))
                    
                    # Round down to symbol precision
                    fixed_quantity = float(Decimal(str(quantity)).quantize(
                        Decimal('0.' + '0' * precision),
                        rounding=ROUND_DOWN
                    ))
                    
                    return fixed_quantity
            
            # Default precision if not found
            return round(quantity, 3)
            
        except Exception as e:
            logger.warning(f"Could not fix quantity precision for {symbol}: {e}")
            return round(quantity, 3)
    
    def _fix_price_precision(self, symbol: str, price: float) -> float:
        """Fix price precision according to symbol rules"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            
            # Find price precision from PRICE_FILTER
            for filter_info in symbol_info['filters']:
                if filter_info['filterType'] == 'PRICE_FILTER':
                    tick_size = float(filter_info['tickSize'])
                    
                    # Calculate precision from tick size
                    if tick_size >= 1:
                        precision = 0
                    else:
                        precision = len(str(tick_size).split('.')[-1].rstrip('0'))
                    
                    # Round to symbol precision
                    fixed_price = float(Decimal(str(price)).quantize(
                        Decimal('0.' + '0' * precision),
                        rounding=ROUND_DOWN
                    ))
                    
                    return fixed_price
            
            # Default precision if not found
            return round(price, 4)
            
        except Exception as e:
            logger.warning(f"Could not fix price precision for {symbol}: {e}")
            return round(price, 4)

    def is_connected(self) -> bool:
        """Check if client is connected"""
        try:
            self.client.ping()
            return True
        except:
            return False