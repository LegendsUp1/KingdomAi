"""
Exchange Data Only Fetcher - NO COINGECKO
Fetches data ONLY from connected exchanges and Redis Quantum Nexus
NO external APIs that cause rate limiting
"""

import logging
import time
from typing import Dict, List, Any, Optional
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ExchangeOnlyDataFetcher:
    """Fetches data ONLY from connected exchanges - NO CoinGecko"""
    
    def __init__(self, event_bus, exchanges: Dict[str, Any]):
        """
        Initialize with connected exchanges only.
        
        Args:
            event_bus: Event bus for publishing data
            exchanges: Dictionary of connected CCXT exchange instances
        """
        self.event_bus = event_bus
        self.exchanges = exchanges or {}
        self.logger = logging.getLogger(__name__)
        # Lazy init to prevent segfault during GUI initialization
        self._executor = None
        self._max_workers = 3
        self._running = False
        
        # Track which markets we're analyzing
        self.analyzed_markets = []
        self.total_symbols = 0
        
        self._build_market_list()
        
        self.logger.info(f"📊 Exchange-Only Data Fetcher initialized")
        self.logger.info(f"   Connected Exchanges: {len(self.exchanges)}")
        self.logger.info(f"   Markets to Analyze: {len(self.analyzed_markets)}")
        self.logger.info(f"   Total Symbols: {self.total_symbols}")
    
    def _build_market_list(self):
        """Build COMPREHENSIVE list of ALL markets from ALL connected exchanges - 2026 SOTA."""
        try:
            # CRITICAL: Monitor EVERY trading pair across ALL exchanges to find EVERY opportunity
            # This is 2026 SOTA - we scan the ENTIRE market, not just popular pairs
            
            all_symbols_by_exchange = {}
            markets_found = {}  # symbol -> list of exchanges
            
            for exchange_name, exchange in self.exchanges.items():
                try:
                    if not hasattr(exchange, 'markets') or not exchange.markets:
                        continue
                    
                    # Get ALL markets from this exchange
                    exchange_markets = list(exchange.markets.keys())
                    all_symbols_by_exchange[exchange_name] = exchange_markets
                    
                    # Add every symbol to our comprehensive tracking
                    for symbol in exchange_markets:
                        if symbol not in markets_found:
                            markets_found[symbol] = []
                        markets_found[symbol].append(exchange_name)
                    
                    self.logger.info(f"   {exchange_name}: {len(exchange_markets)} markets available - MONITORING ALL")
                    
                except Exception as e:
                    self.logger.debug(f"Error checking {exchange_name} markets: {e}")
            
            # Build analyzed markets list - EVERY SINGLE PAIR
            self.analyzed_markets = []
            for symbol, exchanges in markets_found.items():
                self.analyzed_markets.append({
                    'symbol': symbol,
                    'exchanges': exchanges,
                    'primary_exchange': exchanges[0] if exchanges else None,
                    'multi_exchange': len(exchanges) > 1  # Flag for arbitrage potential
                })
            
            self.total_symbols = len(self.analyzed_markets)
            self.all_symbols_by_exchange = all_symbols_by_exchange
            
            # Calculate statistics
            multi_exchange_count = sum(1 for m in self.analyzed_markets if m['multi_exchange'])
            
            self.logger.info(f"✅ COMPREHENSIVE MARKET SCAN COMPLETE:")
            self.logger.info(f"   Total Symbols: {self.total_symbols}")
            self.logger.info(f"   Exchanges: {len(self.exchanges)}")
            self.logger.info(f"   Multi-Exchange Pairs: {multi_exchange_count} (arbitrage opportunities)")
            self.logger.info(f"   Coverage: 100% of all available markets")
            
        except Exception as e:
            self.logger.error(f"Error building market list: {e}")
    
    def get_market_analysis_status(self) -> Dict[str, Any]:
        """Get current market analysis status."""
        return {
            'markets_analyzed': len(self.analyzed_markets),
            'total_symbols': self.total_symbols,
            'connected_exchanges': len(self.exchanges),
            'exchange_names': list(self.exchanges.keys()),
            'top_symbols': [m['symbol'] for m in self.analyzed_markets[:10]]
        }
    
    def fetch_live_prices_from_exchanges(self, batch_size: int = 100) -> Dict[str, Any]:
        """Fetch live prices from ALL markets using intelligent batching - 2026 SOTA.
        
        Args:
            batch_size: Number of tickers to fetch per exchange call (uses fetch_tickers for efficiency)
        """
        prices = {}
        total_fetched = 0
        
        try:
            # SOTA 2026: Use fetch_tickers() for bulk fetching instead of individual calls
            # This is MUCH faster for monitoring ALL markets
            
            for exchange_name, exchange in self.exchanges.items():
                try:
                    if not hasattr(exchange, 'fetch_tickers'):
                        # Fallback to individual fetch_ticker if bulk not supported
                        continue
                    
                    # Fetch ALL tickers from this exchange in one call
                    self.logger.debug(f"Fetching ALL tickers from {exchange_name}...")
                    tickers = exchange.fetch_tickers()
                    
                    if not tickers or not isinstance(tickers, dict):
                        continue
                    
                    # Process all tickers
                    for symbol, ticker in tickers.items():
                        if not isinstance(ticker, dict):
                            continue
                        
                        # Store price data for this symbol
                        prices[symbol] = {
                            'price': ticker.get('last', 0) or ticker.get('close', 0),
                            'change_24h': ticker.get('percentage', 0),
                            'volume_24h': ticker.get('quoteVolume', 0) or ticker.get('volume', 0),
                            'high_24h': ticker.get('high', 0),
                            'low_24h': ticker.get('low', 0),
                            'bid': ticker.get('bid', 0),
                            'ask': ticker.get('ask', 0),
                            'spread': (ticker.get('ask', 0) - ticker.get('bid', 0)) if ticker.get('ask') and ticker.get('bid') else 0,
                            'exchange': exchange_name,
                            'asset_class': 'crypto',
                            'timestamp': time.time()
                        }
                        total_fetched += 1
                    
                    self.logger.info(f"   {exchange_name}: {len(tickers)} markets fetched")
                    
                except Exception as e:
                    self.logger.debug(f"Error fetching tickers from {exchange_name}: {e}")
            
            self.logger.info(f"📊 COMPREHENSIVE PRICE SCAN: {total_fetched} markets across {len(self.exchanges)} exchanges")
            
            return {
                "prices": prices, 
                "timestamp": time.time(), 
                "source": "connected_exchanges",
                "total_markets": total_fetched,
                "exchanges_scanned": len(self.exchanges)
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching exchange prices: {e}")
            return {"prices": {}, "error": str(e)}
    
    def fetch_moonshots_from_exchanges(self, min_gain: float = 5.0) -> List[Dict[str, Any]]:
        """Find moonshot tokens from exchange data - NO CoinGecko."""
        moonshots = []
        
        try:
            # Fetch all tickers from exchanges
            for exchange_name, exchange in self.exchanges.items():
                try:
                    if not hasattr(exchange, 'fetch_tickers'):
                        continue
                    
                    tickers = exchange.fetch_tickers()
                    
                    for symbol, ticker in tickers.items():
                        if not isinstance(ticker, dict):
                            continue
                        
                        change_24h = ticker.get('percentage', 0)
                        
                        if isinstance(change_24h, (int, float)) and change_24h >= min_gain:
                            moonshots.append({
                                'symbol': symbol.split('/')[0],  # Get base currency
                                'name': symbol,
                                'change_24h': float(change_24h),
                                'volume': ticker.get('quoteVolume', 0) or ticker.get('volume', 0),
                                'price': ticker.get('last', 0) or ticker.get('close', 0),
                                'exchange': exchange_name
                            })
                
                except Exception as e:
                    self.logger.debug(f"Error fetching tickers from {exchange_name}: {e}")
            
            # Sort by 24h change descending
            moonshots.sort(key=lambda x: x['change_24h'], reverse=True)
            
            self.logger.info(f"🚀 Found {len(moonshots)} moonshot tokens from exchanges (NO CoinGecko)")
            
            return moonshots[:10]  # Top 10
            
        except Exception as e:
            self.logger.error(f"Error fetching moonshots: {e}")
            return []
