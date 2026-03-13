"""
Symbol Mapper Utility
Converts TradingView symbols to Binance symbols
"""

import logging
from typing import Optional, Dict, Set
import requests
import time

logger = logging.getLogger(__name__)

class SymbolMapper:
    """Maps TradingView symbols to Binance symbols"""
    
    def __init__(self):
        self._binance_symbols: Optional[Set[str]] = None
        self._symbol_cache: Dict[str, str] = {}
        self._last_update = 0
        self._update_interval = 3600  # Update every hour
    
    def _update_binance_symbols(self) -> bool:
        """Update list of available Binance symbols"""
        try:
            # Get symbols from Binance API
            response = requests.get('https://fapi.binance.com/fapi/v1/exchangeInfo', timeout=10)
            if response.status_code == 200:
                data = response.json()
                self._binance_symbols = {symbol['symbol'] for symbol in data['symbols'] if symbol['status'] == 'TRADING'}
                self._last_update = time.time()
                logger.info(f"Updated Binance symbols list: {len(self._binance_symbols)} symbols")
                return True
            else:
                logger.error(f"Failed to fetch Binance symbols: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error updating Binance symbols: {e}")
            return False
    
    def _should_update_symbols(self) -> bool:
        """Check if symbols list should be updated"""
        return (self._binance_symbols is None or 
                time.time() - self._last_update > self._update_interval)
    
    def map_symbol(self, tradingview_symbol: str) -> Optional[str]:
        """
        Map TradingView symbol to Binance symbol
        
        Args:
            tradingview_symbol: Symbol from TradingView (e.g., 'BTCUSDT.P', 'TAUSDT.P')
            
        Returns:
            Binance symbol or None if not found
        """
        try:
            # Check cache first
            if tradingview_symbol in self._symbol_cache:
                return self._symbol_cache[tradingview_symbol]
            
            # Update symbols list if needed
            if self._should_update_symbols():
                self._update_binance_symbols()
            
            if not self._binance_symbols:
                logger.error("Binance symbols list not available")
                return None
            
            # Clean the symbol (remove .P suffix and other TradingView conventions)
            cleaned_symbol = self._clean_symbol(tradingview_symbol)
            
            # Try different mapping strategies
            mapped_symbol = self._find_binance_symbol(cleaned_symbol)
            
            if mapped_symbol:
                # Cache the result
                self._symbol_cache[tradingview_symbol] = mapped_symbol
                logger.info(f"Mapped symbol: {tradingview_symbol} -> {mapped_symbol}")
                return mapped_symbol
            else:
                logger.warning(f"Could not map symbol: {tradingview_symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error mapping symbol {tradingview_symbol}: {e}")
            return None
    
    def _clean_symbol(self, symbol: str) -> str:
        """Clean TradingView symbol to base format"""
        # Remove .P suffix (perpetual contracts)
        if symbol.endswith('.P'):
            symbol = symbol[:-2]
        
        # Remove other common TradingView suffixes
        suffixes_to_remove = ['.PERP', '.FUT', '.SWAP']
        for suffix in suffixes_to_remove:
            if symbol.endswith(suffix):
                symbol = symbol[:-len(suffix)]
                break
        
        return symbol.upper()
    
    def _find_binance_symbol(self, cleaned_symbol: str) -> Optional[str]:
        """Find matching Binance symbol using different strategies"""
        
        if not self._binance_symbols:
            return None
        
        # Strategy 1: Direct match
        if cleaned_symbol in self._binance_symbols:
            return cleaned_symbol
        
        # Strategy 2: Try with USDT suffix if not present
        if not cleaned_symbol.endswith('USDT'):
            usdt_symbol = cleaned_symbol + 'USDT'
            if usdt_symbol in self._binance_symbols:
                return usdt_symbol
        
        # Strategy 3: Handle special cases and prefixes
        special_mappings = {
            # Common mappings for symbols that might have different names
            'TAUSDT': '1000TAUSDT',  # TAU might be 1000TAU on Binance
            'WHYUSDT': '1000WHYUSDT',  # WHY might be 1000WHY on Binance
            'JELLYJELLYUSDT': 'JELLYUSDT',  # Double name might be single
            'PIEVERSEUSDT': 'PIEUSDT',  # Might be shortened
            'UAIUSDT': None,  # Not available on testnet
            'BLUAIUSDT': None,  # Not available on testnet
            'PUFFERUSDT': None,  # Not available on testnet
            'CLOUSDT': None,  # Not available on testnet
            'XPINUSDT': None,  # Not available on testnet
            'AIAUSDT': None,  # Not available on testnet
            'CCUSDT': None,  # Not available on testnet
            'ALLOUSDT': None,  # Not available on testnet
            'CARVUSDT': None,  # Not available on testnet
            'LUNA2USDT': None,  # Not available on testnet
            'BIDUSDT': None,  # Not available on testnet
            'SENTUSDT': None,  # Not available on testnet
        }
        
        if cleaned_symbol in special_mappings:
            mapped = special_mappings[cleaned_symbol]
            if mapped is None:
                # Symbol is known to be unavailable
                logger.warning(f"Symbol {cleaned_symbol} is not available on Binance testnet")
                return None
            if mapped in self._binance_symbols:
                return mapped
        
        # Strategy 4: Try with 1000 prefix (common for small-value tokens)
        if not cleaned_symbol.startswith('1000'):
            prefixed_symbol = '1000' + cleaned_symbol
            if prefixed_symbol in self._binance_symbols:
                return prefixed_symbol
        
        # Strategy 5: Try removing 1000 prefix if present
        if cleaned_symbol.startswith('1000'):
            unprefixed_symbol = cleaned_symbol[4:]
            if unprefixed_symbol in self._binance_symbols:
                return unprefixed_symbol
        
        # Strategy 6: Fuzzy matching for similar symbols
        base_token = cleaned_symbol.replace('USDT', '').replace('BUSD', '').replace('USDC', '')
        for binance_symbol in self._binance_symbols:
            if binance_symbol.startswith(base_token) and binance_symbol.endswith('USDT'):
                return binance_symbol
        
        return None
    
    def is_valid_binance_symbol(self, symbol: str) -> bool:
        """Check if symbol exists on Binance"""
        if self._should_update_symbols():
            self._update_binance_symbols()
        
        return bool(self._binance_symbols and symbol in self._binance_symbols)
    
    def get_all_binance_symbols(self) -> Set[str]:
        """Get all available Binance symbols"""
        if self._should_update_symbols():
            self._update_binance_symbols()
        
        return self._binance_symbols or set()

# Global symbol mapper instance
symbol_mapper = SymbolMapper()