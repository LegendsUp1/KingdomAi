#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MarketAPI component for Kingdom AI.
Manages connections to cryptocurrency exchanges and market data streams.
"""

import os
import asyncio
import logging
import json
import time
import aiohttp
from datetime import datetime, timedelta
import ccxt.async_support as ccxt

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class MarketAPI(BaseComponent):
    """
    Component for managing cryptocurrency exchange connections and market data.
    Supports multiple exchanges through ccxt.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the MarketAPI component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "MarketAPI"
        self.description = "Cryptocurrency exchange connection manager"
        
        # Exchange configuration
        self.default_exchange = self.config.get("default_exchange", "binance")
        self.exchanges = {}
        self.api_keys = {}
        self.exchange_configs = self.config.get("exchanges", {})
        
        # Market data
        self.market_data = {}
        self.trading_pairs = {}
        self.websocket_connections = {}
        self.update_interval = self.config.get("update_interval", 60)  # seconds
        
        # Session
        self.session = None
        self.is_initialized = False
        self.updater_task = None
        
    async def initialize(self):
        """Initialize the MarketAPI component."""
        logger.info("Initializing MarketAPI")
        
        # Create HTTP session
        self.session = aiohttp.ClientSession()
        
        # Subscribe to events
        self.event_bus.subscribe("market.get_price", self.on_get_price)
        self.event_bus.subscribe("market.get_ticker", self.on_get_ticker)
        self.event_bus.subscribe("market.get_orderbook", self.on_get_orderbook)
        self.event_bus.subscribe("market.subscribe", self.on_market_subscribe)
        self.event_bus.subscribe("market.unsubscribe", self.on_market_unsubscribe)
        self.event_bus.subscribe("api.key.updated", self.on_api_key_updated)
        self.event_bus.subscribe("system.shutdown", self.on_shutdown)
        
        # Load API keys
        await self._load_api_keys()
        
        # Initialize exchanges
        await self._initialize_exchanges()
        
        # Start market data updater
        self.updater_task = asyncio.create_task(self._update_market_data_periodically())
        
        self.is_initialized = True
        logger.info("MarketAPI initialized")
        
    async def _load_api_keys(self):
        """Load API keys from configuration or environment."""
        logger.info("Loading API keys for exchanges")
        
        # First, check environment variables
        for exchange in ["binance", "kraken", "coinbase", "kucoin", "huobi"]:
            api_key_env = f"{exchange.upper()}_API_KEY"
            api_secret_env = f"{exchange.upper()}_API_SECRET"
            
            if api_key_env in os.environ and api_secret_env in os.environ:
                self.api_keys[exchange] = {
                    "apiKey": os.environ[api_key_env],
                    "secret": os.environ[api_secret_env]
                }
                logger.info(f"Loaded API keys for {exchange} from environment")
        
        # Then, load from configuration
        for exchange, config in self.exchange_configs.items():
            if "apiKey" in config and "secret" in config:
                self.api_keys[exchange] = {
                    "apiKey": config["apiKey"],
                    "secret": config["secret"]
                }
                logger.info(f"Loaded API keys for {exchange} from configuration")
        
        # Now try to load from api_keys.json if it exists
        api_keys_path = os.path.join(os.path.dirname(__file__), "..", "config", "api_keys.json")
        if os.path.exists(api_keys_path):
            try:
                with open(api_keys_path, "r") as f:
                    keys_data = json.load(f)
                
                for exchange, keys in keys_data.items():
                    if "apiKey" in keys and "secret" in keys:
                        self.api_keys[exchange] = keys
                        logger.info(f"Loaded API keys for {exchange} from api_keys.json")
            except Exception as e:
                logger.error(f"Error loading API keys from file: {e}")
        
        # Report on loaded keys
        logger.info(f"Loaded API keys for {len(self.api_keys)} exchanges: {', '.join(self.api_keys.keys())}")
    
    async def _initialize_exchanges(self):
        """Initialize exchange connections."""
        logger.info("Initializing exchange connections")
        
        # Initialize each exchange with API keys if available
        for exchange_id in list(self.api_keys.keys()) + ["binance", "kraken", "coinbase"]:
            # Skip duplicates
            if exchange_id in self.exchanges:
                continue
                
            try:
                # Get exchange class
                exchange_class = getattr(ccxt, exchange_id)
                
                # Initialize with API keys if available
                if exchange_id in self.api_keys:
                    exchange = exchange_class({
                        "apiKey": self.api_keys[exchange_id]["apiKey"],
                        "secret": self.api_keys[exchange_id]["secret"],
                        "enableRateLimit": True
                    })
                    logger.info(f"Initialized {exchange_id} with API keys")
                else:
                    exchange = exchange_class({"enableRateLimit": True})
                    logger.info(f"Initialized {exchange_id} without API keys (public API only)")
                
                # Store exchange instance
                self.exchanges[exchange_id] = exchange
                
                # Load markets
                await exchange.load_markets()
                self.trading_pairs[exchange_id] = list(exchange.markets.keys())
                
                # Publish exchange status
                self.event_bus.publish("market.exchange.status", {
                    "exchange": exchange_id,
                    "status": "connected",
                    "authenticated": exchange_id in self.api_keys,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error initializing exchange {exchange_id}: {e}")
                
                # Publish error
                self.event_bus.publish("market.exchange.status", {
                    "exchange": exchange_id,
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
        
        logger.info(f"Initialized {len(self.exchanges)} exchange connections")
    
    async def _update_market_data_periodically(self):
        """Update market data periodically."""
        try:
            while True:
                try:
                    await self._update_market_data()
                except Exception as e:
                    logger.error(f"Error updating market data: {e}")
                
                # Sleep until next update
                await asyncio.sleep(self.update_interval)
        except asyncio.CancelledError:
            logger.info("Market data updater task cancelled")
    
    async def _update_market_data(self):
        """Update market data for subscribed pairs."""
        if not self.market_data:
            # Nothing to update yet
            return
            
        logger.debug(f"Updating market data for {len(self.market_data)} pairs")
        
        update_start = time.time()
        updates = 0
        
        # Update each pair
        for exchange_id, pairs in self.market_data.items():
            if not pairs or exchange_id not in self.exchanges:
                continue
                
            try:
                exchange = self.exchanges[exchange_id]
                
                # Fetch tickers for all pairs at once if supported
                if len(pairs) > 1 and exchange.has['fetchTickers']:
                    tickers = await exchange.fetch_tickers(list(pairs.keys()))
                    
                    for symbol, ticker in tickers.items():
                        if symbol in pairs:
                            # Update ticker data
                            pairs[symbol].update({
                                "price": ticker["last"],
                                "bid": ticker["bid"],
                                "ask": ticker["ask"],
                                "volume": ticker["quoteVolume"],
                                "change": ticker["percentage"],
                                "updated": datetime.now().isoformat()
                            })
                            updates += 1
                            # Publish per-symbol update for UI/widgets (sync EventBus).
                            try:
                                if self.event_bus:
                                    payload = {"symbol": symbol, "exchange": exchange_id}
                                    payload.update(pairs[symbol])
                                    self.event_bus.publish("market:price_update", payload)
                                    self.event_bus.publish("trading.market_data", payload)
                            except Exception:
                                pass
                else:
                    # Fetch individual tickers
                    for symbol in pairs.keys():
                        ticker = await exchange.fetch_ticker(symbol)
                        
                        # Update ticker data
                        pairs[symbol].update({
                            "price": ticker["last"],
                            "bid": ticker["bid"],
                            "ask": ticker["ask"],
                            "volume": ticker["quoteVolume"],
                            "change": ticker["percentage"],
                            "updated": datetime.now().isoformat()
                        })
                        updates += 1
                        # Publish per-symbol update for UI/widgets (sync EventBus).
                        try:
                            if self.event_bus:
                                payload = {"symbol": symbol, "exchange": exchange_id}
                                payload.update(pairs[symbol])
                                self.event_bus.publish("market:price_update", payload)
                                self.event_bus.publish("trading.market_data", payload)
                        except Exception:
                            pass
                        
                        # Rate limiting
                        await asyncio.sleep(exchange.rateLimit / 1000)
            except Exception as e:
                logger.error(f"Error updating market data for {exchange_id}: {e}")
        
        update_time = time.time() - update_start
        logger.debug(f"Updated {updates} market data entries in {update_time:.2f} seconds")
        
        # Publish market update
        self.event_bus.publish("market.data.updated", {
            "updates": updates,
            "time": update_time,
            "timestamp": datetime.now().isoformat()
        })
    
    async def get_price(self, symbol, exchange=None):
        """
        Get the current price for a symbol.
        
        Args:
            symbol: Trading pair symbol
            exchange: Exchange ID (defaults to default_exchange)
            
        Returns:
            Current price or None on error
        """
        exchange = exchange or self.default_exchange
        
        # Check if we have the data in cache
        if exchange in self.market_data and symbol in self.market_data[exchange]:
            data = self.market_data[exchange][symbol]
            # Only use cached data if it's recent (within 5 minutes)
            if "updated" in data:
                updated = datetime.fromisoformat(data["updated"])
                if datetime.now() - updated < timedelta(minutes=5):
                    return data["price"]
        
        # Not in cache or too old, fetch from exchange
        try:
            if exchange not in self.exchanges:
                logger.warning(f"Exchange {exchange} not initialized")
                return None
                
            ticker = await self.exchanges[exchange].fetch_ticker(symbol)
            
            # Update cache
            if exchange not in self.market_data:
                self.market_data[exchange] = {}
            if symbol not in self.market_data[exchange]:
                self.market_data[exchange][symbol] = {}
                
            self.market_data[exchange][symbol].update({
                "price": ticker["last"],
                "bid": ticker["bid"],
                "ask": ticker["ask"],
                "volume": ticker["quoteVolume"],
                "change": ticker["percentage"],
                "updated": datetime.now().isoformat()
            })
            
            return ticker["last"]
        except Exception as e:
            logger.error(f"Error fetching price for {symbol} on {exchange}: {e}")
            return None
    
    async def get_ticker(self, symbol, exchange=None):
        """
        Get the full ticker for a symbol.
        
        Args:
            symbol: Trading pair symbol
            exchange: Exchange ID (defaults to default_exchange)
            
        Returns:
            Ticker data or None on error
        """
        exchange = exchange or self.default_exchange
        
        try:
            if exchange not in self.exchanges:
                logger.warning(f"Exchange {exchange} not initialized")
                return None
                
            ticker = await self.exchanges[exchange].fetch_ticker(symbol)
            
            # Update cache
            if exchange not in self.market_data:
                self.market_data[exchange] = {}
            if symbol not in self.market_data[exchange]:
                self.market_data[exchange][symbol] = {}
                
            self.market_data[exchange][symbol].update({
                "price": ticker["last"],
                "bid": ticker["bid"],
                "ask": ticker["ask"],
                "volume": ticker["quoteVolume"],
                "change": ticker["percentage"],
                "updated": datetime.now().isoformat()
            })
            
            return ticker
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol} on {exchange}: {e}")
            return None
    
    async def get_orderbook(self, symbol, exchange=None, limit=20):
        """
        Get the orderbook for a symbol.
        
        Args:
            symbol: Trading pair symbol
            exchange: Exchange ID (defaults to default_exchange)
            limit: Number of orders to fetch
            
        Returns:
            Orderbook data or None on error
        """
        exchange = exchange or self.default_exchange
        
        try:
            if exchange not in self.exchanges:
                logger.warning(f"Exchange {exchange} not initialized")
                return None
                
            orderbook = await self.exchanges[exchange].fetch_order_book(symbol, limit)
            return orderbook
        except Exception as e:
            logger.error(f"Error fetching orderbook for {symbol} on {exchange}: {e}")
            return None
    
    async def subscribe_market(self, symbol, exchange=None):
        """
        Subscribe to market data updates for a symbol.
        
        Args:
            symbol: Trading pair symbol
            exchange: Exchange ID (defaults to default_exchange)
            
        Returns:
            Success status
        """
        exchange = exchange or self.default_exchange
        
        try:
            if exchange not in self.exchanges:
                logger.warning(f"Exchange {exchange} not initialized")
                return False
                
            # Add to market data cache
            if exchange not in self.market_data:
                self.market_data[exchange] = {}
            if symbol not in self.market_data[exchange]:
                self.market_data[exchange][symbol] = {}
            
            # Fetch initial data
            ticker = await self.exchanges[exchange].fetch_ticker(symbol)
            
            self.market_data[exchange][symbol].update({
                "price": ticker["last"],
                "bid": ticker["bid"],
                "ask": ticker["ask"],
                "volume": ticker["quoteVolume"],
                "change": ticker["percentage"],
                "updated": datetime.now().isoformat()
            })
            
            logger.info(f"Subscribed to market data for {symbol} on {exchange}")
            return True
        except Exception as e:
            logger.error(f"Error subscribing to market data for {symbol} on {exchange}: {e}")
            return False
    
    async def unsubscribe_market(self, symbol, exchange=None):
        """
        Unsubscribe from market data updates for a symbol.
        
        Args:
            symbol: Trading pair symbol
            exchange: Exchange ID (defaults to default_exchange)
            
        Returns:
            Success status
        """
        exchange = exchange or self.default_exchange
        
        try:
            # Remove from market data cache
            if exchange in self.market_data and symbol in self.market_data[exchange]:
                del self.market_data[exchange][symbol]
                logger.info(f"Unsubscribed from market data for {symbol} on {exchange}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error unsubscribing from market data for {symbol} on {exchange}: {e}")
            return False
    
    async def get_balance(self, exchange=None):
        """
        Get account balance.
        
        Args:
            exchange: Exchange ID (defaults to default_exchange)
            
        Returns:
            Account balance or None on error
        """
        exchange = exchange or self.default_exchange
        
        try:
            if exchange not in self.exchanges:
                logger.warning(f"Exchange {exchange} not initialized")
                return None
                
            if exchange not in self.api_keys:
                logger.warning(f"No API keys for {exchange}")
                return None
                
            balance = await self.exchanges[exchange].fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"Error fetching balance for {exchange}: {e}")
            return None
    
    async def get_trading_pairs(self, exchange=None):
        """
        Get available trading pairs.
        
        Args:
            exchange: Exchange ID (defaults to default_exchange)
            
        Returns:
            List of trading pairs or empty list on error
        """
        exchange = exchange or self.default_exchange
        
        if exchange in self.trading_pairs:
            return self.trading_pairs[exchange]
            
        try:
            if exchange not in self.exchanges:
                logger.warning(f"Exchange {exchange} not initialized")
                return []
                
            await self.exchanges[exchange].load_markets()
            pairs = list(self.exchanges[exchange].markets.keys())
            self.trading_pairs[exchange] = pairs
            return pairs
        except Exception as e:
            logger.error(f"Error fetching trading pairs for {exchange}: {e}")
            return []
    
    async def save_api_key(self, exchange, api_key, api_secret):
        """
        Save API key for an exchange.
        
        Args:
            exchange: Exchange ID
            api_key: API key
            api_secret: API secret
            
        Returns:
            Success status
        """
        try:
            # Update in-memory API keys
            self.api_keys[exchange] = {
                "apiKey": api_key,
                "secret": api_secret
            }
            
            # Save to disk
            api_keys_path = os.path.join(os.path.dirname(__file__), "..", "config", "api_keys.json")
            os.makedirs(os.path.dirname(api_keys_path), exist_ok=True)
            
            # Load existing keys if file exists
            keys_data = {}
            if os.path.exists(api_keys_path):
                try:
                    with open(api_keys_path, "r") as f:
                        keys_data = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading API keys from file: {e}")
            
            # Update with new key
            keys_data[exchange] = {
                "apiKey": api_key,
                "secret": api_secret
            }
            
            # Save back to file
            with open(api_keys_path, "w") as f:
                json.dump(keys_data, f, indent=2)
            
            # Reinitialize exchange
            if exchange in self.exchanges:
                await self.exchanges[exchange].close()
                
            # Get exchange class
            exchange_class = getattr(ccxt, exchange)
            
            # Initialize with API keys
            self.exchanges[exchange] = exchange_class({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True
            })
            
            # Load markets
            await self.exchanges[exchange].load_markets()
            self.trading_pairs[exchange] = list(self.exchanges[exchange].markets.keys())
            
            logger.info(f"Saved and initialized API keys for {exchange}")
            
            # Publish exchange status
            self.event_bus.publish("market.exchange.status", {
                "exchange": exchange,
                "status": "connected",
                "authenticated": True,
                "timestamp": datetime.now().isoformat()
            })
            
            return True
        except Exception as e:
            logger.error(f"Error saving API key for {exchange}: {e}")
            
            # Publish error
            self.event_bus.publish("market.exchange.status", {
                "exchange": exchange,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            
            return False
    
    async def test_api_key(self, exchange):
        """
        Test API key for an exchange.
        
        Args:
            exchange: Exchange ID
            
        Returns:
            Test result
        """
        try:
            if exchange not in self.exchanges:
                logger.warning(f"Exchange {exchange} not initialized")
                return {"success": False, "error": f"Exchange {exchange} not initialized"}
                
            if exchange not in self.api_keys:
                logger.warning(f"No API keys for {exchange}")
                return {"success": False, "error": f"No API keys for {exchange}"}
                
            # Test by fetching balance
            balance = await self.exchanges[exchange].fetch_balance()
            
            return {
                "success": True,
                "balance": balance["total"],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error testing API key for {exchange}: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def on_get_price(self, data):
        """
        Handle get price event.
        
        Args:
            data: Event data with symbol and optional exchange
        """
        symbol = data.get("symbol")
        exchange = data.get("exchange", self.default_exchange)
        request_id = data.get("request_id", "unknown")
        
        if not symbol:
            logger.warning("Received empty symbol for price request")
            return
            
        price = await self.get_price(symbol, exchange)
        
        self.event_bus.publish("market.price.response", {
            "symbol": symbol,
            "exchange": exchange,
            "price": price,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_get_ticker(self, data):
        """
        Handle get ticker event.
        
        Args:
            data: Event data with symbol and optional exchange
        """
        symbol = data.get("symbol")
        exchange = data.get("exchange", self.default_exchange)
        request_id = data.get("request_id", "unknown")
        
        if not symbol:
            logger.warning("Received empty symbol for ticker request")
            return
            
        ticker = await self.get_ticker(symbol, exchange)
        
        self.event_bus.publish("market.ticker.response", {
            "symbol": symbol,
            "exchange": exchange,
            "ticker": ticker,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_get_orderbook(self, data):
        """
        Handle get orderbook event.
        
        Args:
            data: Event data with symbol, optional exchange, and optional limit
        """
        symbol = data.get("symbol")
        exchange = data.get("exchange", self.default_exchange)
        limit = data.get("limit", 20)
        request_id = data.get("request_id", "unknown")
        
        if not symbol:
            logger.warning("Received empty symbol for orderbook request")
            return
            
        orderbook = await self.get_orderbook(symbol, exchange, limit)
        
        self.event_bus.publish("market.orderbook.response", {
            "symbol": symbol,
            "exchange": exchange,
            "orderbook": orderbook,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_market_subscribe(self, data):
        """
        Handle market subscribe event.
        
        Args:
            data: Event data with symbol and optional exchange
        """
        symbol = data.get("symbol")
        exchange = data.get("exchange", self.default_exchange)
        request_id = data.get("request_id", "unknown")
        
        if not symbol:
            logger.warning("Received empty symbol for market subscribe request")
            return
            
        success = await self.subscribe_market(symbol, exchange)
        
        self.event_bus.publish("market.subscribe.response", {
            "symbol": symbol,
            "exchange": exchange,
            "success": success,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_market_unsubscribe(self, data):
        """
        Handle market unsubscribe event.
        
        Args:
            data: Event data with symbol and optional exchange
        """
        symbol = data.get("symbol")
        exchange = data.get("exchange", self.default_exchange)
        request_id = data.get("request_id", "unknown")
        
        if not symbol:
            logger.warning("Received empty symbol for market unsubscribe request")
            return
            
        success = await self.unsubscribe_market(symbol, exchange)
        
        self.event_bus.publish("market.unsubscribe.response", {
            "symbol": symbol,
            "exchange": exchange,
            "success": success,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_api_key_updated(self, data):
        """
        Handle API key updated event.
        
        Args:
            data: Event data with exchange, api_key, and api_secret
        """
        exchange = data.get("exchange")
        api_key = data.get("api_key")
        api_secret = data.get("api_secret")
        
        if not exchange or not api_key or not api_secret:
            logger.warning("Received incomplete API key update data")
            return
            
        await self.save_api_key(exchange, api_key, api_secret)
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the MarketAPI component."""
        logger.info("Shutting down MarketAPI")
        
        # Cancel updater task
        if self.updater_task:
            self.updater_task.cancel()
            try:
                await self.updater_task
            except asyncio.CancelledError:
                pass
        
        # Close exchange connections
        for exchange_id, exchange in self.exchanges.items():
            try:
                await exchange.close()
                logger.info(f"Closed connection to {exchange_id}")
            except Exception as e:
                logger.error(f"Error closing connection to {exchange_id}: {e}")
        
        # Close HTTP session
        if self.session:
            await self.session.close()
        
        logger.info("MarketAPI shut down successfully")
