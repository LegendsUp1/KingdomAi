"""Real-time market data streaming system for Kingdom AI."""

import asyncio
import logging
import json
import time
from typing import Dict, Any, Optional, Set, List
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed
from decimal import Decimal

from .base_component import BaseComponent
from .event_bus import EventBus
from utils.thoth import Thoth


class MarketStream(BaseComponent):
    """Real-time market data streaming with multi-exchange support."""
    
    def __init__(
        self,
        event_bus: EventBus,
        thoth: Optional[Thoth] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize market stream component."""
        super().__init__("market_stream", event_bus, thoth, config)
        
        # Exchange connections
        self._connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self._subscriptions: Dict[str, Set[str]] = {}
        self._reconnect_tasks: Dict[str, asyncio.Task] = {}
        
        # Market data
        self._orderbooks: Dict[str, Dict[str, Any]] = {}
        self._tickers: Dict[str, Dict[str, Any]] = {}
        self._trades: Dict[str, List[Dict[str, Any]]] = {}
        
        # Stream state
        self._running = False
        self._last_update: Dict[str, float] = {}
        self._update_counters: Dict[str, int] = {}
        
    async def initialize(self) -> bool:
        """Initialize market stream component."""
        try:
            # Load exchange configurations
            exchanges_config = self.config.get("exchanges", {})
            
            # Initialize connections
            for exchange, config in exchanges_config.items():
                await self._initialize_exchange(exchange, config)
                
            # Register event handlers
            self.event_bus.subscribe_sync("market.subscribe", self._handle_subscribe)
            self.event_bus.subscribe_sync("market.unsubscribe", self._handle_unsubscribe)
            
            # Start monitoring task
            self._monitor_task = asyncio.create_task(self._monitor_connections())
            
            self._running = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize market stream: {str(e)}")
            return False
            
    def initialize_sync(self):
        """Synchronous version of initialize"""
        return True
            
    async def _initialize_exchange(self, exchange: str, config: Dict[str, Any]) -> None:
        """Initialize connection to an exchange.
        
        Args:
            exchange: Exchange name
            config: Exchange configuration
        """
        try:
            # Get exchange-specific configuration
            ws_url = config["websocket_url"]
            api_key = config["api_key"]
            api_secret = config["api_secret"]
            
            # Initialize data structures
            self._subscriptions[exchange] = set()
            self._orderbooks[exchange] = {}
            self._tickers[exchange] = {}
            self._trades[exchange] = {}
            
            # Create connection
            headers = self._get_auth_headers(exchange, api_key, api_secret)
            connection = await websockets.connect(ws_url, extra_headers=headers)
            self._connections[exchange] = connection
            
            # Start message handler
            self._reconnect_tasks[exchange] = asyncio.create_task(
                self._handle_messages(exchange, connection)
            )
            
            self.logger.info(f"Initialized connection to {exchange}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize {exchange}: {str(e)}")
            raise
            
    def _get_auth_headers(
        self,
        exchange: str,
        api_key: str,
        api_secret: str
    ) -> Dict[str, str]:
        """Get authentication headers for exchange.
        
        Args:
            exchange: Exchange name
            api_key: API key
            api_secret: API secret
            
        Returns:
            Dict with authentication headers
        """
        try:
            timestamp = str(int(time.time() * 1000))
            
            if exchange == "binance":
                signature = self._sign_request(
                    api_secret,
                    f"timestamp={timestamp}"
                )
                return {
                    "X-MBX-APIKEY": api_key,
                    "X-MBX-SIGNATURE": signature,
                    "X-MBX-TIMESTAMP": timestamp
                }
            elif exchange == "kucoin":
                token = self._get_kucoin_token(api_key, api_secret, timestamp)
                return {
                    "KC-API-KEY": api_key,
                    "KC-API-SIGN": token["signature"],
                    "KC-API-TIMESTAMP": timestamp,
                    "KC-API-PASSPHRASE": token["passphrase"]
                }
            elif exchange == "bybit":
                signature = self._sign_request(
                    api_secret,
                    f"GET/realtime{timestamp}"
                )
                return {
                    "api_key": api_key,
                    "sign": signature,
                    "timestamp": timestamp
                }
            else:
                raise ValueError(f"Unknown exchange: {exchange}")
                
        except Exception as e:
            self.logger.error(f"Failed to get auth headers for {exchange}: {str(e)}")
            raise
            
    async def _handle_messages(
        self,
        exchange: str,
        connection: websockets.WebSocketClientProtocol
    ) -> None:
        """Handle incoming websocket messages.
        
        Args:
            exchange: Exchange name
            connection: WebSocket connection
        """
        try:
            while True:
                try:
                    message = await connection.recv()
                    data = json.loads(message)
                    
                    # Update timestamp
                    self._last_update[exchange] = time.time()
                    self._update_counters[exchange] = self._update_counters.get(exchange, 0) + 1
                    
                    # Process message
                    await self._process_message(exchange, data)
                    
                except ConnectionClosed:
                    self.logger.warning(f"Connection closed for {exchange}, reconnecting...")
                    await self._reconnect_exchange(exchange)
                    break
                    
                except Exception as e:
                    self.logger.error(f"Error handling message from {exchange}: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"Fatal error in message handler for {exchange}: {str(e)}")
            
    async def _process_message(self, exchange: str, data: Dict[str, Any]) -> None:
        """Process incoming market data message.
        
        Args:
            exchange: Exchange name
            data: Message data
        """
        try:
            # Extract message type and symbol
            msg_type = data.get("type") or data.get("e")
            symbol = data.get("symbol") or data.get("s")
            
            if not msg_type or not symbol:
                return
                
            # Normalize data format
            normalized = self._normalize_data(exchange, msg_type, data)
            
            # Update internal state
            if msg_type == "orderbook":
                self._orderbooks[exchange][symbol] = normalized
            elif msg_type == "ticker":
                self._tickers[exchange][symbol] = normalized
            elif msg_type == "trade":
                self._trades[exchange].setdefault(symbol, []).append(normalized)
                
            # Publish update
            await self.event_bus.publish("market.update", {
                "exchange": exchange,
                "symbol": symbol,
                "type": msg_type,
                "data": normalized,
                "timestamp": datetime.now().isoformat()
            })
            
            # Update Thoth AI
            if self.thoth and msg_type in ["trade", "orderbook"]:
                await self.thoth.update_model({
                    "type": "market_data",
                    "exchange": exchange,
                    "symbol": symbol,
                    "data_type": msg_type,
                    "data": normalized
                })
                
        except Exception as e:
            self.logger.error(f"Error processing message from {exchange}: {str(e)}")
            
    def _normalize_data(
        self,
        exchange: str,
        msg_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize market data format across exchanges.
        
        Args:
            exchange: Exchange name
            msg_type: Message type
            data: Raw message data
            
        Returns:
            Normalized data dictionary
        """
        try:
            if msg_type == "orderbook":
                return {
                    "bids": [
                        [Decimal(str(price)), Decimal(str(amount))]
                        for price, amount in data.get("bids", [])
                    ],
                    "asks": [
                        [Decimal(str(price)), Decimal(str(amount))]
                        for price, amount in data.get("asks", [])
                    ],
                    "timestamp": data.get("timestamp", time.time() * 1000)
                }
            elif msg_type == "ticker":
                return {
                    "price": Decimal(str(data.get("price", 0))),
                    "volume": Decimal(str(data.get("volume", 0))),
                    "high": Decimal(str(data.get("high", 0))),
                    "low": Decimal(str(data.get("low", 0))),
                    "timestamp": data.get("timestamp", time.time() * 1000)
                }
            elif msg_type == "trade":
                return {
                    "price": Decimal(str(data.get("price", 0))),
                    "amount": Decimal(str(data.get("amount", 0))),
                    "side": data.get("side", "unknown"),
                    "timestamp": data.get("timestamp", time.time() * 1000)
                }
            else:
                return data
                
        except Exception as e:
            self.logger.error(f"Error normalizing data from {exchange}: {str(e)}")
            return data
            
    async def _monitor_connections(self) -> None:
        """Monitor connection health and reconnect if needed."""
        try:
            while self._running:
                current_time = time.time()
                
                for exchange in list(self._connections.keys()):
                    last_update = self._last_update.get(exchange, 0)
                    
                    # Check if connection is stale
                    if current_time - last_update > 30:  # 30 seconds timeout
                        self.logger.warning(f"Stale connection detected for {exchange}")
                        await self._reconnect_exchange(exchange)
                        
                await asyncio.sleep(5)  # Check every 5 seconds
                
        except Exception as e:
            self.logger.error(f"Error in connection monitor: {str(e)}")
            
    async def _reconnect_exchange(self, exchange: str) -> None:
        """Reconnect to an exchange.
        
        Args:
            exchange: Exchange name
        """
        try:
            # Close existing connection
            if exchange in self._connections:
                await self._connections[exchange].close()
                del self._connections[exchange]
                
            # Cancel existing tasks
            if exchange in self._reconnect_tasks:
                self._reconnect_tasks[exchange].cancel()
                del self._reconnect_tasks[exchange]
                
            # Get exchange config
            exchanges_config = self.config.get("exchanges", {})
            if exchange not in exchanges_config:
                return
                
            # Reinitialize connection
            await self._initialize_exchange(exchange, exchanges_config[exchange])
            
            # Resubscribe to channels
            if exchange in self._subscriptions:
                for channel in self._subscriptions[exchange]:
                    await self._subscribe(exchange, channel)
                    
        except Exception as e:
            self.logger.error(f"Failed to reconnect to {exchange}: {str(e)}")
            
    async def _handle_subscribe(self, event: Dict[str, Any]) -> None:
        """Handle market data subscription request."""
        try:
            exchange = event.get("exchange")
            symbol = event.get("symbol")
            channels = event.get("channels", [])
            
            if not all([exchange, symbol, channels]):
                return
                
            for channel in channels:
                subscription = f"{channel}:{symbol}"
                
                if subscription not in self._subscriptions.get(exchange, set()):
                    await self._subscribe(exchange, subscription)
                    
        except Exception as e:
            self.logger.error(f"Error handling subscription: {str(e)}")
            
    async def _handle_unsubscribe(self, event: Dict[str, Any]) -> None:
        """Handle market data unsubscription request."""
        try:
            exchange = event.get("exchange")
            symbol = event.get("symbol")
            channels = event.get("channels", [])
            
            if not all([exchange, symbol, channels]):
                return
                
            for channel in channels:
                subscription = f"{channel}:{symbol}"
                
                if subscription in self._subscriptions.get(exchange, set()):
                    await self._unsubscribe(exchange, subscription)
                    
        except Exception as e:
            self.logger.error(f"Error handling unsubscription: {str(e)}")
            
    async def shutdown(self) -> bool:
        """Shutdown market stream component."""
        try:
            self._running = False
            
            # Cancel monitor task
            if hasattr(self, '_monitor_task'):
                self._monitor_task.cancel()
                
            # Close all connections
            for exchange in list(self._connections.keys()):
                await self._connections[exchange].close()
                
            # Cancel all tasks
            for task in self._reconnect_tasks.values():
                task.cancel()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error shutting down market stream: {str(e)}")
            return False
