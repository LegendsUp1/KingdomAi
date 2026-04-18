#!/usr/bin/env python3
"""
LIVE Order Book - WebSocket Real-Time Order Book Feed
Connects to exchange WebSocket APIs for real-time order book updates
NO MOCK DATA - 100% LIVE
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable
from collections import OrderedDict
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import ccxt.pro as ccxtpro
    CCXT_PRO_AVAILABLE = True
except ImportError:
    CCXT_PRO_AVAILABLE = False
    logger.warning("CCXT Pro not available - Order book will use REST API fallback")


class LiveOrderBook:
    """
    LIVE Order Book with WebSocket Streaming
    Provides real-time bid/ask updates from exchanges
    """
    
    def __init__(self, exchange_name: str = 'binance', api_keys: Optional[Dict] = None):
        """
        Initialize live order book.
        
        Args:
            exchange_name: Exchange to connect to
            api_keys: API keys for authenticated access (optional)
        """
        self.exchange_name = exchange_name
        self.api_keys = api_keys or {}
        self.exchange: Optional[ccxtpro.Exchange] = None
        self.order_books: Dict[str, Dict] = {}  # symbol -> order book data
        self.ws_tasks: Dict[str, asyncio.Task] = {}
        self.callbacks: List[Callable] = []
        self.running = False
        
        # Initialize exchange
        self._init_exchange()
    
    def _init_exchange(self):
        """Initialize WebSocket exchange connection."""
        if not CCXT_PRO_AVAILABLE:
            logger.warning("CCXT Pro not available - using REST fallback")
            return
        
        try:
            exchange_class = getattr(ccxtpro, self.exchange_name)
            config = {
                'enableRateLimit': True,
                'newUpdates': True  # Use incremental order book updates
            }
            
            # Add API keys if available
            if f'{self.exchange_name}' in self.api_keys:
                config['apiKey'] = self.api_keys.get(f'{self.exchange_name}')
                config['secret'] = self.api_keys.get(f'{self.exchange_name}_secret')
            
            self.exchange = exchange_class(config)
            logger.info(f"✅ WebSocket exchange initialized: {self.exchange_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket exchange: {e}")
            self.exchange = None
    
    async def watch_order_book(self, symbol: str, limit: int = 20):
        """
        Watch order book for a symbol via WebSocket.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            limit: Number of order book levels to fetch
        """
        if not self.exchange:
            logger.error("Exchange not initialized")
            return
        
        self.running = True
        logger.info(f"🔴 Starting LIVE order book stream for {symbol}")
        
        try:
            while self.running:
                # Fetch order book via WebSocket
                order_book = await self.exchange.watch_order_book(symbol, limit)
                
                # Process order book data
                processed_data = {
                    'symbol': symbol,
                    'bids': order_book['bids'][:limit],  # [[price, amount], ...]
                    'asks': order_book['asks'][:limit],
                    'timestamp': order_book.get('timestamp', datetime.now().timestamp() * 1000),
                    'datetime': order_book.get('datetime', datetime.now().isoformat())
                }
                
                # Store in memory
                self.order_books[symbol] = processed_data
                
                # Notify callbacks
                for callback in self.callbacks:
                    try:
                        callback(processed_data)
                    except Exception as e:
                        logger.error(f"Error in order book callback: {e}")
                
        except Exception as e:
            logger.error(f"Error watching order book for {symbol}: {e}")
            self.running = False
    
    async def start_streaming(self, symbols: List[str], limit: int = 20):
        """
        Start streaming order books for multiple symbols.
        
        Args:
            symbols: List of trading pairs
            limit: Number of levels per side
        """
        if not self.exchange:
            logger.error("Cannot start streaming - exchange not initialized")
            return
        
        for symbol in symbols:
            if symbol not in self.ws_tasks:
                task = asyncio.create_task(self.watch_order_book(symbol, limit))
                self.ws_tasks[symbol] = task
                logger.info(f"✅ Started order book stream: {symbol}")
    
    def stop_streaming(self, symbol: Optional[str] = None):
        """
        Stop streaming order books.
        
        Args:
            symbol: Specific symbol to stop, or None to stop all
        """
        self.running = False
        
        if symbol and symbol in self.ws_tasks:
            self.ws_tasks[symbol].cancel()
            del self.ws_tasks[symbol]
            logger.info(f"Stopped order book stream: {symbol}")
        else:
            # Stop all streams
            for task in self.ws_tasks.values():
                task.cancel()
            self.ws_tasks.clear()
            logger.info("Stopped all order book streams")
    
    def register_callback(self, callback: Callable):
        """Register callback for order book updates."""
        self.callbacks.append(callback)
    
    def get_order_book(self, symbol: str) -> Optional[Dict]:
        """Get latest order book for symbol."""
        return self.order_books.get(symbol)
    
    def get_best_bid(self, symbol: str) -> Optional[float]:
        """Get best bid price for symbol."""
        order_book = self.order_books.get(symbol)
        if order_book and order_book['bids']:
            return order_book['bids'][0][0]  # First bid price
        return None
    
    def get_best_ask(self, symbol: str) -> Optional[float]:
        """Get best ask price for symbol."""
        order_book = self.order_books.get(symbol)
        if order_book and order_book['asks']:
            return order_book['asks'][0][0]  # First ask price
        return None
    
    def get_spread(self, symbol: str) -> Optional[float]:
        """Get bid-ask spread for symbol."""
        best_bid = self.get_best_bid(symbol)
        best_ask = self.get_best_ask(symbol)
        
        if best_bid and best_ask:
            return best_ask - best_bid
        return None
    
    async def close(self):
        """Close WebSocket connections."""
        self.stop_streaming()
        if self.exchange:
            await self.exchange.close()
            logger.info("WebSocket exchange closed")


class OrderBookREST:
    """
    REST API Fallback for Order Book
    Used when WebSocket is not available
    """
    
    def __init__(self, exchange_name: str = 'binance', api_keys: Optional[Dict] = None):
        """Initialize REST order book."""
        import ccxt
        
        self.exchange_name = exchange_name
        self.api_keys = api_keys or {}
        
        try:
            exchange_class = getattr(ccxt, exchange_name)
            config = {'enableRateLimit': True}
            
            if f'{exchange_name}' in api_keys:
                config['apiKey'] = api_keys.get(f'{exchange_name}')
                config['secret'] = api_keys.get(f'{exchange_name}_secret')
            
            self.exchange = exchange_class(config)
            logger.info(f"✅ REST exchange initialized: {exchange_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize REST exchange: {e}")
            self.exchange = None
    
    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """
        Fetch order book via REST API.
        
        Args:
            symbol: Trading pair
            limit: Number of levels
            
        Returns:
            Order book data
        """
        if not self.exchange:
            return None
        
        try:
            order_book = await asyncio.to_thread(
                self.exchange.fetch_order_book,
                symbol,
                limit
            )
            
            return {
                'symbol': symbol,
                'bids': order_book['bids'][:limit],
                'asks': order_book['asks'][:limit],
                'timestamp': order_book.get('timestamp', datetime.now().timestamp() * 1000),
                'datetime': order_book.get('datetime', datetime.now().isoformat())
            }
            
        except Exception as e:
            logger.error(f"Error fetching order book: {e}")
            return None
