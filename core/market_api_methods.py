"""
MarketAPI methods implementation module.

This module contains method implementations for the MarketAPI class
that should be imported into the main MarketAPI module to avoid
circular imports and implement missing functionality.
"""

import asyncio
import time
import random
import secrets
import logging

logger = logging.getLogger("KingdomAI.MarketAPI")

# Default implementation of enable_mock_mode
def enable_mock_mode(self):
    """Enable mock mode ONLY when API keys are missing (not as default)."""
    self.logger.warning("⚠️ MOCK MODE ENABLED - API keys missing or invalid. Real market data unavailable.")
    self.mock_mode = True
    
    # Initialize with realistic mock data (clearly labeled as mock)
    current_time = time.time()
    
    # Helper function to generate random float in range
    def get_random_float(min_val, max_val):
        return min_val + (secrets.random() * (max_val - min_val))
    
    # Ensure we have a consistent property for mock data
    self._ticker_data = {
        "BTCUSDT": {
            "symbol": "BTCUSDT",
            "price": 62500.0 + (get_random_float(-1000, 1000)),
            "volume": 10000.0 + get_random_float(0, 5000), 
            "timestamp": current_time,
            "bid": 62450.0 + (get_random_float(-500, 500)),
            "ask": 62550.0 + (get_random_float(-500, 500)),
            "high": 63200.0,
            "low": 61800.0,
            "trades": 15000,
            "exchange": "binance"
        },
        "ETHUSDT": {
            "symbol": "ETHUSDT",
            "price": 3050.0 + (get_random_float(-100, 100)),
            "volume": 25000.0 + get_random_float(0, 10000),
            "timestamp": current_time,
            "bid": 3045.0 + (get_random_float(-50, 50)),
            "ask": 3055.0 + (get_random_float(-50, 50)),
            "high": 3100.0,
            "low": 3000.0,
            "trades": 12000,
            "exchange": "binance"
        },
        "BNBUSDT": {
            "symbol": "BNBUSDT",
            "price": 570.0 + (get_random_float(-10, 10)),
            "volume": 15000.0 + get_random_float(0, 5000),
            "timestamp": current_time,
            "bid": 569.0 + (get_random_float(-5, 5)),
            "ask": 571.0 + (get_random_float(-5, 5)),
            "high": 580.0,
            "low": 560.0,
            "trades": 8000,
            "exchange": "binance"
        },
        "SOLUSDT": {
            "symbol": "SOLUSDT",
            "price": 150.0 + (get_random_float(-5, 5)),
            "volume": 12000.0 + get_random_float(0, 4000),
            "timestamp": current_time,
            "bid": 149.5 + (get_random_float(-2.5, 2.5)),
            "ask": 150.5 + (get_random_float(-2.5, 2.5)),
            "high": 155.0,
            "low": 145.0,
            "trades": 6000,
            "exchange": "binance"
        }
    }
    
    # Also store in market_data for backward compatibility
    self.market_data = self._ticker_data.copy()
    
    # Notify about mock mode via event bus if available
    if self.event_bus:
        asyncio.create_task(self.event_bus.publish(
            "market.status", 
            {"status": "mock_mode", "reason": "API keys missing or invalid", "symbols": list(self._ticker_data.keys())}
        ))
        
        # Also notify the API Key Manager about connection status
        asyncio.create_task(self.event_bus.publish(
            "api.connection.status",
            {"services": {
                self.service_name: {
                    "connected": False,
                    "last_check": time.time(),
                    "error": "API keys missing or invalid, using mock mode",
                    "mock_mode": True
                }
            }}
        ))

# Default implementation of ping API
async def ping_api(self):
    """Ping API to verify connection."""
    if not self.session:
        self.logger.error("HTTP session not initialized")
        return False
        
    try:
        endpoint = f"{self.base_url}/api/v3/ping"
        async with self.session.get(endpoint) as response:
            return response.status == 200
    except Exception as e:
        self.logger.error(f"Error pinging API: {e}")
        return False

# Default implementation of get_ticker
def get_ticker(self, symbol):
    """Get ticker information for symbol.
    
    Args:
        symbol: Trading pair symbol (e.g. 'BTCUSDT')
        
    Returns:
        dict: Ticker data including price, volume, etc.
    """
    # Ensure symbol is a string
    if symbol is None:
        symbol = "BTCUSDT"
        
    # Check if we have cached data
    if hasattr(self, 'market_data') and symbol in self.market_data:
        return self.market_data[symbol]
        
    # Check in _ticker_data if market_data not available
    if hasattr(self, '_ticker_data') and symbol in self._ticker_data:
        return self._ticker_data[symbol]
        
    # Return mock data if not available
    base_token = symbol[:3] if len(symbol) >= 6 else symbol
    
    # Set realistic prices for common tokens
    price_map = {
        'BTC': 40000 + random.uniform(-1000, 1000),
        'ETH': 2500 + random.uniform(-100, 100),
        'BNB': 300 + random.uniform(-10, 10),
        'SOL': 80 + random.uniform(-5, 5),
        'XRP': 0.5 + random.uniform(-0.02, 0.02),
        'ADA': 0.4 + random.uniform(-0.02, 0.02)
    }
    
    # Default price if token not in map
    price = price_map.get(base_token, 10 + random.uniform(-1, 1))
    
    # Create mock ticker data
    return {
        'symbol': symbol,
        'price': price,
        'bid': price * 0.999,
        'ask': price * 1.001,
        'volume': random.uniform(1000, 10000),
        'timestamp': time.time(),
        'high': price * 1.02,
        'low': price * 0.98
    }

# Implementation of get_market_data
def get_market_data(self, symbol=None, timeframe="1m", limit=100):
    """Get market data for specified symbol using real API calls.
    
    Args:
        symbol: Trading pair symbol (e.g. 'BTCUSDT'). If None, returns data for all active symbols.
        timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
        limit: Number of candles to retrieve
        
    Returns:
        dict: Market data including price, volume, candles
    """
    self.logger.info(f"Retrieving market data for {symbol if symbol else 'all symbols'}")
    
    try:
        # If in mock mode (API keys missing), return honest error
        if self.mock_mode:
            self.logger.warning("⚠️ Cannot retrieve real market data: API keys not configured")
            return {
                "error": "Market data unavailable - API keys not configured. Configure API keys to enable real data.",
                "mock_mode": True,
                "symbol": symbol
            }
        
        # Try to get real market data using urllib.request to CoinGecko or exchange APIs
        if not self.connected:
            # Try to connect first
            if hasattr(self, 'connect') and callable(self.connect):
                self.connect()
        
        if self.connected and hasattr(self, 'session') and self.session:
            # Use real API call via session
            try:
                import urllib.request
                import urllib.parse
                import json as json_lib
                
                # Try CoinGecko API (free, no API key needed)
                if symbol:
                    # Map symbol to CoinGecko ID
                    symbol_map = {
                        "BTCUSDT": "bitcoin",
                        "ETHUSDT": "ethereum",
                        "BNBUSDT": "binancecoin",
                        "SOLUSDT": "solana"
                    }
                    coin_id = symbol_map.get(symbol[:3] if len(symbol) >= 6 else symbol[:3].upper())
                    
                    if coin_id:
                        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true"
                        with urllib.request.urlopen(url, timeout=10) as response:
                            data = json_lib.loads(response.read())
                            if coin_id in data:
                                price_data = data[coin_id]
                                return {
                                    symbol: {
                                        'price': float(price_data.get('usd', 0.0)),
                                        'volume': float(price_data.get('usd_24h_vol', 0.0)),
                                        'change_24h': float(price_data.get('usd_24h_change', 0.0)),
                                        'last_update': time.time(),
                                        'source': 'coingecko'
                                    }
                                }
            except Exception as api_error:
                self.logger.debug(f"Real API call failed: {api_error}, falling back to error response")
        
        # If real API unavailable, return honest error (not mock data)
        return {
            "error": "Market data unavailable - API connection failed or not configured",
            "symbol": symbol,
            "suggestion": "Configure API keys or check internet connection"
        }
            
        # If symbol is None, return data for all active symbols
        symbols_to_query = [symbol] if symbol else self.active_symbols
        result = {}
        
        for sym in symbols_to_query:
            # Use ticker data as base
            ticker = self.get_ticker(sym)
            
            result[sym] = {
                'price': ticker.get('price', 0.0),
                'volume': ticker.get('volume', 0.0),
                'bid': ticker.get('bid', 0.0),
                'ask': ticker.get('ask', 0.0),
                'high': ticker.get('high', 0.0),
                'low': ticker.get('low', 0.0),
                'last_update': ticker.get('timestamp', time.time())
            }
            
        return result if symbol is None else result.get(symbol, {})
        
    except Exception as e:
        self.logger.error(f"Error getting market data: {e}")
        # Return mock data as fallback
        return self._fallback_market_data(symbol, timeframe, limit)

def _fallback_market_data(self, symbol=None, timeframe="1m", limit=100):
    """Return unavailable-state market data when live API fails."""
    symbols_list = [symbol] if symbol else getattr(self, 'active_symbols', ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"])
    result = {}
    
    for sym in symbols_list:
        result[sym] = {
            'price': None,
            'volume': None,
            'bid': None,
            'ask': None,
            'high': None,
            'low': None,
            'last_update': None,
            'status': 'unavailable',
            'error': 'Live market data temporarily unavailable'
        }
        
    return result if symbol is None else result.get(symbol, {})

# Implementation of load API keys
async def load_api_keys(self):
    """Load API keys from various sources."""
    # First try the API Key Manager if available
    if self.api_key_manager and self.event_bus:  # Both must be set
        try:
            # Request API keys through the event bus
            await self.event_bus.publish("api.key.request", {
                "service": self.service_name,
                "requester": id(self)
            })
            
            self.logger.info("Requested API keys through event bus")
            return True
        except Exception as e:
            self.logger.error(f"Error requesting API keys: {e}")
    
    # If API Key Manager not available or error occurred,
    # load from environment
    self.logger.info("Loading API keys from environment")
    
    # Load from environment variables
    env_key = self.config.get("api_key") or self.env.get(f"{self.service_name.upper()}_API_KEY")
    env_secret = self.config.get("api_secret") or self.env.get(f"{self.service_name.upper()}_API_SECRET")
    
    if env_key and env_secret:
        self.api_key = env_key
        self.api_secret = env_secret
        self.logger.info(f"Loaded API keys for {self.service_name} from environment variables or config")
        return True
    
    # If no keys available, enable mock mode (clearly labeled)
    if not self.api_key or not self.api_secret:
        self.logger.warning(f"⚠️ No API keys available for {self.service_name} - enabling MOCK MODE (real data unavailable)")
        self.enable_mock_mode()
        return False
    
    return bool(self.api_key and self.api_secret)
