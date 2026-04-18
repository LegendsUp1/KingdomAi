"""
Live Price Fetcher for Trading Tab
Fetches REAL-TIME prices from multiple exchanges
"""

import asyncio
import logging
from typing import Dict, List, Any
import time

logger = logging.getLogger(__name__)

class LivePriceFetcher:
    """Live price fetcher with multiple exchange support"""
    
    # Alternative APIs that work globally (Binance replacement)
    PRICE_APIS = [
    {
        "name": "CryptoCompare",
        "url": "https://min-api.cryptocompare.com/data/pricemultifull",
        "priority": 1,
        "method": "cryptocompare"
    },
    {
        "name": "CoinGecko", 
        "url": "https://api.coingecko.com/api/v3/simple/price",
        "priority": 2,
        "method": "coingecko"
    },
    {
        "name": "Kraken",
        "url": "https://api.kraken.com/0/public/Ticker",
        "priority": 3,
        "method": "kraken"
    }
]

    """Fetches live prices from exchanges."""
    
    def __init__(self, event_bus, api_keys: Dict[str, str]):
        self.event_bus = event_bus
        self.api_keys = api_keys
        self.logger = logging.getLogger(__name__)
        self.running = False
        # Dynamic watchlist of base symbols (e.g., ["BTC","ETH"]) to fetch
        self.watch_symbols: List[str] = []

    def set_watch_symbols(self, symbols: List[str]) -> None:
        """Set the dynamic watchlist of symbols to fetch (base symbols only)."""
        try:
            if not symbols:
                self.watch_symbols = []
                return
            # Normalize: uppercase, dedupe, strip pairs if provided as "BTC/USDT"
            norm: List[str] = []
            for s in symbols:
                if not s:
                    continue
                base = s.split('/')[0].strip().upper()
                if base and base not in norm:
                    norm.append(base)
            self.watch_symbols = norm
            self.logger.info(f"🔭 Watchlist set to {len(self.watch_symbols)} symbols")
        except Exception as e:
            self.logger.error(f"Error setting watch symbols: {e}")
    
    # DISABLED (geo-blocked) - Binance price fetcher removed due to HTTP 451 restrictions
    
    async def fetch_coingecko_prices(self, ids: List[str] = None) -> Dict[str, Any]:
        """Fetch prices from CoinGecko API and convert to UI format."""
        if ids is None:
            ids = ['bitcoin', 'ethereum', 'solana', 'ripple', 'cardano']
        
        # Map CoinGecko IDs to trading symbols
        id_to_symbol = {
            'bitcoin': 'BTC/USDT',
            'ethereum': 'ETH/USDT',
            # DISABLED (geo-blocked): 'binancecoin': 'BNB/USDT',
            'solana': 'SOL/USDT',
            'ripple': 'XRP/USDT',
            'cardano': 'ADA/USDT'
        }
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                ids_str = ','.join(ids)
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
                
                # Add API key if available
                headers = {}
                if 'coingecko' in self.api_keys and self.api_keys['coingecko']:
                    headers['x-cg-pro-api-key'] = self.api_keys['coingecko']
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices = {}
                        
                        # Convert CoinGecko format to UI format
                        for coin_id, coin_data in data.items():
                            # Map to trading symbol (BTC/USDT format)
                            symbol = id_to_symbol.get(coin_id, coin_id.upper() + '/USDT')
                            
                            prices[symbol] = {
                                'price': coin_data.get('usd', 0),
                                'change_24h': coin_data.get('usd_24h_change', 0),
                                'volume': coin_data.get('usd_24h_vol', 0),
                                'exchange': 'coingecko'
                            }
                        
                        return prices
        except Exception as e:
            self.logger.error(f"Error fetching CoinGecko prices: {e}")
        
        return {}
    
    async def fetch_cryptocompare_prices(self, symbols: List[str] = None) -> Dict[str, Any]:
        """Fetch REAL live prices from CryptoCompare API (NO GEO-RESTRICTIONS)."""
        if symbols is None or len(symbols) == 0:
            # Broad, but safe default set
            symbols = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'AVAX', 'LINK', 'MATIC', 'LTC']
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                fsyms = ','.join(symbols)
                url = f"https://min-api.cryptocompare.com/data/pricemultifull?fsyms={fsyms}&tsyms=USD"
                
                # Add API key if available (optional for CryptoCompare)
                headers = {}
                api_key = self.api_keys.get('cryptocompare') or self.api_keys.get('CRYPTOCOMPARE_API_KEY')
                if api_key and api_key != 'your_cryptocompare_api_key_here':
                    headers['authorization'] = f'Apikey {api_key}'
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        prices = {}
                        
                        # Convert CryptoCompare format to UI format
                        if 'RAW' in data:
                            for symbol in symbols:
                                if symbol in data['RAW'] and 'USD' in data['RAW'][symbol]:
                                    coin_data = data['RAW'][symbol]['USD']
                                    
                                    prices[f'{symbol}/USDT'] = {
                                        'price': coin_data.get('PRICE', 0),
                                        'change_24h': coin_data.get('CHANGEPCT24HOUR', 0),
                                        'volume': coin_data.get('VOLUME24HOUR', 0),
                                        'exchange': 'cryptocompare'
                                    }
                        
                        self.logger.info(f"✅ CryptoCompare: Fetched {len(prices)} prices")
                        return prices
                    else:
                        self.logger.warning(f"⚠️ CryptoCompare returned status {response.status}")
        except Exception as e:
            self.logger.error(f"❌ Error fetching CryptoCompare prices: {e}")
        
        return {}
    
    def start_live_updates(self):
        """Start fetching live prices every 10 seconds."""
        self.running = True
        self.logger.info("🔴 Starting live price updates every 10 seconds")
        self._schedule_next_update()
    
    def _schedule_next_update(self):
        """Schedule next price update."""
        if not self.running:
            return
        
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10000, self._fetch_and_publish)
    
    def _fetch_and_publish(self):
        """Fetch prices and publish to event bus - Use thread for sync HTTP calls."""
        import threading
        
        def _threaded_fetch():
            """Run sync HTTP fetch in background thread."""
            try:
                import requests
                prices = {}
                
                # Fetch from CryptoCompare (sync, no event loop needed)
                symbols = self.watch_symbols or ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE']
                fsyms = ','.join(symbols)
                url = f"https://min-api.cryptocompare.com/data/pricemultifull?fsyms={fsyms}&tsyms=USD"
                
                headers = {}
                api_key = self.api_keys.get('cryptocompare') or self.api_keys.get('CRYPTOCOMPARE_API_KEY')
                if api_key and api_key != 'your_cryptocompare_api_key_here':
                    headers['authorization'] = f'Apikey {api_key}'
                
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'RAW' in data:
                        for symbol in symbols:
                            if symbol in data['RAW'] and 'USD' in data['RAW'][symbol]:
                                coin_data = data['RAW'][symbol]['USD']
                                prices[f'{symbol}/USDT'] = {
                                    'price': coin_data.get('PRICE', 0),
                                    'change_24h': coin_data.get('CHANGEPCT24HOUR', 0),
                                    'volume': coin_data.get('VOLUME24HOUR', 0),
                                    'exchange': 'cryptocompare'
                                }
                    
                    if prices:
                        self.logger.info(f"✅ CryptoCompare: {len(prices)} prices fetched")
                        # Publish to event bus (thread-safe)
                        if self.event_bus:
                            self.event_bus.publish('trading.live_prices', {'prices': prices})
                else:
                    self.logger.warning(f"⚠️ CryptoCompare returned status {response.status_code}")
                    
            except Exception as e:
                self.logger.error(f"❌ Error fetching prices: {e}")
            finally:
                # Schedule next update on main thread
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self._schedule_next_update)
        
        # Run in background thread to avoid blocking Qt event loop
        thread = threading.Thread(target=_threaded_fetch, daemon=True)
        thread.start()
    
    async def _async_fetch_and_publish(self):
        """Async fetch and publish REAL LIVE DATA with multiple fallbacks."""
        try:
            prices = None
            
            # Try CryptoCompare FIRST (NO GEO-RESTRICTIONS, most reliable)
            try:
                cryptocompare_prices = await self.fetch_cryptocompare_prices(self.watch_symbols)
                if cryptocompare_prices:
                    self.logger.info(f"✅ CryptoCompare: {len(cryptocompare_prices)} prices")
                    prices = cryptocompare_prices
            except Exception as e:
                self.logger.warning(f"⚠️ CryptoCompare failed: {e}")
            
            # CoinGecko fallback DISABLED to avoid 429 rate limiting
            # CryptoCompare is the primary and only price source now
            if not prices:
                self.logger.warning("⚠️ CryptoCompare unavailable - no fallback (CoinGecko disabled)")
            
            # DISABLED (geo-blocked) - Binance fallback removed due to HTTP 451 restrictions
            
            if prices:
                # Log actual prices to verify they're real
                for symbol, data in list(prices.items())[:3]:  # Log first 3 only
                    self.logger.info(f"   {symbol}: ${data['price']:,.2f} ({data.get('change_24h', 0):+.2f}%)")
                
                # Publish to event bus
                self.event_bus.publish('trading.live_prices', {'prices': prices})
                self.logger.info(f"📊 Published {len(prices)} REAL live prices to UI")
            else:
                self.logger.error("❌ NO PRICES FETCHED - All APIs failed!")
            
            # Schedule next update in 10 seconds
            self._schedule_next_update()
            
        except Exception as e:
            self.logger.error(f"❌ Error fetching REAL prices: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._schedule_next_update()
    
    def stop(self):
        """Stop live updates."""
        self.running = False
        self.logger.info("⏸️ Stopped live price updates")
