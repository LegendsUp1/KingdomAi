#!/usr/bin/env python3
"""
LIVE Trades Feed - WebSocket Real-Time Trade Stream
Connects to exchange WebSocket APIs for real-time trade updates
NO MOCK DATA - 100% LIVE
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, cast
from datetime import datetime
from collections import deque
from core.event_bus import EventBus

logger = logging.getLogger(__name__)

try:
    import ccxt.pro as ccxtpro
    CCXT_PRO_AVAILABLE = True
except ImportError:
    CCXT_PRO_AVAILABLE = False
    logger.warning("CCXT Pro not available - Trades feed will use REST API fallback")


class LiveTradesFeed:
    """
    LIVE Trades Feed with WebSocket Streaming
    Provides real-time trade updates from exchanges
    """
    
    def __init__(self, exchange_name: str = 'binance', api_keys: Optional[Dict] = None, event_bus=None):
        """
        Initialize live trades feed.
        
        Args:
            exchange_name: Exchange to connect to
            api_keys: API keys for authenticated access (optional)
        """
        self.exchange_name = exchange_name
        self.api_keys: Dict[str, Any] = api_keys or {}
        self.exchange: Optional[ccxtpro.Exchange] = None
        self.trades_history: Dict[str, deque] = {}  # symbol -> deque of trades
        self.ws_tasks: Dict[str, asyncio.Task] = {}
        self.callbacks: List[Callable] = []
        self.running = False
        self.max_trades = 100  # Keep last 100 trades per symbol
        self.event_bus = event_bus
        try:
            if not self.event_bus:
                self.event_bus = EventBus.get_instance()
        except Exception:
            pass
        self.price_cache: Dict[str, float] = {}
        
        # Initialize exchange
        self._init_exchange()
        try:
            if self.event_bus:
                self.event_bus.subscribe('market:price_update', self._on_market_price_update)
                self.event_bus.subscribe('market.prices', self._on_market_prices_snapshot)
                self.event_bus.subscribe('trading:live_price', self._on_market_price_update)
        except Exception:
            pass
    
    def _init_exchange(self):
        """Initialize WebSocket exchange connection."""
        if not CCXT_PRO_AVAILABLE:
            logger.warning("CCXT Pro not available - using REST fallback")
            return
        
        try:
            exchange_class = getattr(ccxtpro, self.exchange_name)
            config = cast(Dict[str, Any], {
                'enableRateLimit': True,
                'newUpdates': True
            })
            
            # Add API keys if available
            if isinstance(self.api_keys, dict) and f'{self.exchange_name}' in self.api_keys:
                api_key_val = self.api_keys.get(f'{self.exchange_name}') or ""
                api_secret_val = self.api_keys.get(f'{self.exchange_name}_secret') or ""
                config['apiKey'] = str(api_key_val)
                config['secret'] = str(api_secret_val)
            
            self.exchange = exchange_class(config)
            logger.info(f"✅ Trades WebSocket exchange initialized: {self.exchange_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize trades WebSocket exchange: {e}")
            self.exchange = None
    
    async def watch_trades(self, symbol: str):
        """
        Watch trades for a symbol via WebSocket.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
        """
        if not self.exchange:
            logger.error("Exchange not initialized")
            return
        
        self.running = True
        
        # Initialize trade history for symbol
        if symbol not in self.trades_history:
            self.trades_history[symbol] = deque(maxlen=self.max_trades)
        
        logger.info(f"🔴 Starting LIVE trades stream for {symbol}")
        
        try:
            while self.running:
                # Fetch trades via WebSocket
                trades = await self.exchange.watch_trades(symbol)
                
                # Process each trade
                for trade in trades:
                    processed_trade = {
                        'id': trade.get('id'),
                        'symbol': symbol,
                        'timestamp': trade.get('timestamp'),
                        'datetime': trade.get('datetime'),
                        'price': trade.get('price'),
                        'amount': trade.get('amount'),
                        'cost': trade.get('cost', trade.get('price', 0) * trade.get('amount', 0)),
                        'side': trade.get('side'),  # 'buy' or 'sell'
                        'takerOrMaker': trade.get('takerOrMaker'),
                        'type': trade.get('type', 'market'),
                        'exchange': self.exchange_name
                    }
                    
                    # Add to history
                    self.trades_history[symbol].append(processed_trade)
                    
                    # Notify callbacks
                    for callback in self.callbacks:
                        try:
                            callback(processed_trade)
                        except Exception as e:
                            logger.error(f"Error in trades callback: {e}")
                
        except Exception as e:
            logger.error(f"Error watching trades for {symbol}: {e}")
            self.running = False
    
    async def start_streaming(self, symbols: List[str]):
        """
        Start streaming trades for multiple symbols.
        
        Args:
            symbols: List of trading pairs
        """
        if not self.exchange:
            logger.error("Cannot start streaming - exchange not initialized")
            return
        
        for symbol in symbols:
            if symbol not in self.ws_tasks:
                task = asyncio.create_task(self.watch_trades(symbol))
                self.ws_tasks[symbol] = task
                logger.info(f"✅ Started trades stream: {symbol}")
    
    def stop_streaming(self, symbol: Optional[str] = None):
        """
        Stop streaming trades.
        
        Args:
            symbol: Specific symbol to stop, or None to stop all
        """
        self.running = False
        
        if symbol and symbol in self.ws_tasks:
            self.ws_tasks[symbol].cancel()
            del self.ws_tasks[symbol]
            logger.info(f"Stopped trades stream: {symbol}")
        else:
            # Stop all streams
            for task in self.ws_tasks.values():
                task.cancel()
            self.ws_tasks.clear()
            logger.info("Stopped all trades streams")
    
    def register_callback(self, callback: Callable):
        """Register callback for trade updates."""
        self.callbacks.append(callback)
    
    def get_recent_trades(self, symbol: str, limit: int = 20) -> List[Dict]:
        """
        Get recent trades for symbol.
        
        Args:
            symbol: Trading pair
            limit: Number of trades to return
            
        Returns:
            List of recent trades
        """
        if symbol not in self.trades_history:
            return []
        
        trades_list = list(self.trades_history[symbol])
        return trades_list[-limit:] if len(trades_list) > limit else trades_list
    
    def get_last_price(self, symbol: str) -> Optional[float]:
        """Get last trade price for symbol."""
        trades = self.get_recent_trades(symbol, limit=1)
        if trades:
            return trades[0]['price']
        try:
            base = symbol.split('/')[0].upper()
            if base in self.price_cache:
                return float(self.price_cache[base])
        except Exception:
            pass
        return None

    def _on_market_price_update(self, price_data: Dict):
        try:
            symbol = price_data.get('symbol')
            price = float(price_data.get('price', 0) or 0)
            if not symbol or price <= 0:
                return
            base = symbol.split('/')[0].upper()
            self.price_cache[base] = price
        except Exception:
            pass

    def _on_market_prices_snapshot(self, event_data: Dict):
        try:
            prices = event_data.get('prices', {})
            if not isinstance(prices, dict):
                return
            for sym, pdata in prices.items():
                try:
                    base = str(sym).split('/')[0].upper()
                    p = 0.0
                    if isinstance(pdata, dict):
                        p = float(pdata.get('price', 0) or 0)
                    elif isinstance(pdata, (int, float)):
                        p = float(pdata)
                    if p > 0:
                        self.price_cache[base] = p
                except Exception:
                    continue
        except Exception:
            pass
    
    def get_volume_24h(self, symbol: str) -> float:
        """Calculate 24h volume from recent trades."""
        if symbol not in self.trades_history:
            return 0.0
        
        now = datetime.now().timestamp() * 1000
        day_ago = now - (24 * 60 * 60 * 1000)
        
        volume = 0.0
        for trade in self.trades_history[symbol]:
            if trade['timestamp'] >= day_ago:
                volume += trade['amount']
        
        return volume
    
    async def close(self):
        """Close WebSocket connections."""
        self.stop_streaming()
        if self.exchange:
            await self.exchange.close()
            logger.info("Trades WebSocket exchange closed")


class TradesFeedREST:
    """
    REST API Fallback for Trades Feed
    Used when WebSocket is not available
    """
    
    def __init__(self, exchange_name: str = 'binance', api_keys: Optional[Dict] = None):
        """Initialize REST trades feed."""
        import ccxt
        
        self.exchange_name = exchange_name
        self.api_keys: Dict[str, Any] = api_keys or {}
        
        try:
            exchange_class = getattr(ccxt, exchange_name)
            config = cast(Dict[str, Any], {'enableRateLimit': True})
            
            if isinstance(self.api_keys, dict) and f'{exchange_name}' in self.api_keys:
                api_key_val = self.api_keys.get(f'{exchange_name}') or ""
                api_secret_val = self.api_keys.get(f'{exchange_name}_secret') or ""
                config['apiKey'] = str(api_key_val)
                config['secret'] = str(api_secret_val)
            
            self.exchange = exchange_class(config)
            logger.info(f"✅ REST trades feed initialized: {exchange_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize REST trades feed: {e}")
            self.exchange = None
    
    async def fetch_trades(self, symbol: str, limit: int = 20) -> List[Dict]:
        """
        Fetch recent trades via REST API.
        
        Args:
            symbol: Trading pair
            limit: Number of trades
            
        Returns:
            List of recent trades
        """
        if not self.exchange:
            return []
        
        try:
            trades = await asyncio.to_thread(
                self.exchange.fetch_trades,
                symbol,
                limit=limit
            )
            
            return [{
                'id': trade.get('id'),
                'symbol': symbol,
                'timestamp': trade.get('timestamp'),
                'datetime': trade.get('datetime'),
                'price': trade.get('price'),
                'amount': trade.get('amount'),
                'cost': trade.get('cost'),
                'side': trade.get('side'),
                'takerOrMaker': trade.get('takerOrMaker'),
                'type': trade.get('type'),
                'exchange': self.exchange_name
            } for trade in trades]
            
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []
