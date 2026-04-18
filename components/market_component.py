#!/usr/bin/env python3
"""
Market Data Component for Kingdom AI

This component provides real-time market data for trading and dashboard displays.
"""

import logging
import asyncio
import os
import sys
import traceback

# Ensure market package is in path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Add market data provider class directly in this file to avoid import issues
class MarketDataProvider:
    """Market data provider that simulates real-time market data and publishes to the event bus."""
    
    def __init__(self, event_bus=None, config_manager=None):
        """Initialize the market data provider.
        
        Args:
            event_bus: The event bus to publish market data
            config_manager: The config manager for market data configuration
        """
        self.logger = logging.getLogger("KingdomAI.MarketDataProvider")
        self.event_bus = event_bus
        self.config_manager = config_manager

        # Caches now populated exclusively from live MarketDataStreaming events.
        self._prices = {}
        self._volumes = {}
        self._trends = {}
        self._24h_change = {}

        # We no longer run a local simulation loop; this flag is kept for
        # backwards compatibility but has no effect on real data.
        self._streaming = False
        self._streaming_task = None
        self._pending_historical_requests = {}

        self.logger.info("MarketDataProvider initialized (live bridge mode)")

    async def initialize(self):
        """Initialize the market data provider component."""
        try:
            self.logger.info("Initializing MarketDataProvider (live bridge)...")

            # Subscribe to request and system events
            if self.event_bus:
                # Use sync subscription for compatibility with GUI components
                if hasattr(self.event_bus, 'subscribe_sync'):
                    self.event_bus.subscribe_sync("market.request.data", self._handle_data_request)
                    self.event_bus.subscribe_sync("market.request.historical", self._handle_historical_request)
                    self.event_bus.subscribe_sync("system.ready", self._handle_system_ready)
                    # Bridge live MarketDataStreaming updates into legacy events
                    self.event_bus.subscribe_sync("market.data.update", self._handle_live_market_update)
                    self.event_bus.subscribe_sync("market.data.response", self._handle_market_data_response)
                elif hasattr(self.event_bus, 'subscribe'):
                    # Fallback to async subscription API (kingdom_integration_part1 style)
                    await self.event_bus.subscribe("market.request.data", self._handle_data_request)
                    await self.event_bus.subscribe("market.request.historical", self._handle_historical_request)
                    await self.event_bus.subscribe("system.ready", self._handle_system_ready)
                    await self.event_bus.subscribe("market.data.update", self._handle_live_market_update)
                    await self.event_bus.subscribe("market.data.response", self._handle_market_data_response_async)

                self.logger.info("Subscribed to market data and live streaming events")

                # No synthetic initial snapshot; if caches are empty, 
                # consumers simply see no data until live updates arrive.
                await self._publish_initial_data()
            
            self.logger.info("MarketDataProvider initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing MarketDataProvider: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _publish_initial_data(self):
        """Publish initial market data if any live data is already cached.

        This method will not fabricate prices; if no live data has been
        received yet, it simply returns without emitting fake snapshots.
        """
        try:
            if not self.event_bus:
                return

            if not self._prices:
                # No live data yet; nothing to publish.
                self.logger.info("No live market data cached yet; skipping initial publish")
                return

            payload = {
                "prices": self._prices,
                "volumes": self._volumes,
                "trends": self._trends,
                "24h_change": self._24h_change,
                "timestamp": self._get_timestamp(),
            }

            if hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync("market.data", payload)
            elif hasattr(self.event_bus, 'publish'):
                await self.event_bus.publish("market.data", payload)

            # Publish individual symbol updates for easy consumption by GUI components
            for symbol, price in self._prices.items():
                update = {
                    "symbol": symbol,
                    "price": price,
                    "volume": self._volumes.get(symbol, 0),
                    "trend": self._trends.get(symbol, "stable"),
                    "24h_change": self._24h_change.get(symbol, 0),
                    "timestamp": self._get_timestamp(),
                }
                if hasattr(self.event_bus, 'publish_sync'):
                    self.event_bus.publish_sync("market.update", update)
                    self.event_bus.publish_sync("market.prices_update", update)
                elif hasattr(self.event_bus, 'publish'):
                    await self.event_bus.publish("market.update", update)
                    await self.event_bus.publish("market.prices_update", update)

            self.logger.info("Published initial live market data from cache")
        except Exception as e:
            self.logger.error(f"Error publishing initial market data: {e}")
            self.logger.error(traceback.format_exc())
    
    def _get_timestamp(self):
        """Get current timestamp."""
        import time
        return time.time()
    
    def _start_streaming(self):
        """No-op in live mode; streaming is handled by MarketDataStreaming.

        Kept for backward compatibility so callers do not break.
        """
        self.logger.debug("_start_streaming called in live bridge mode; no local simulation started")

    def _stop_streaming(self):
        """No-op in live mode; streaming is handled by MarketDataStreaming."""
        self.logger.debug("_stop_streaming called in live bridge mode; nothing to stop")

    async def _handle_live_market_update(self, event_data):
        """Handle live market.data.update events from MarketDataStreaming.

        Expected payload shape from MarketDataStreaming:
            {
                "exchange": "binance" | "coinbase" | ...,
                "market": "BTC/USDT" | "ETH/USDT" | ...,
                "data": {
                    "exchange": ...,  # repeated
                    "market": ...,
                    "price": float,
                    "bid": float,
                    "ask": float,
                    "volume_24h": float,
                    "timestamp": iso8601,
                    "change_24h": float,
                    "change_percent_24h": float,
                    "high_24h": float,
                    "low_24h": float,
                }
            }

        This method converts those into the legacy symbol-level payloads
        consumed by existing GUI and backend code.
        """
        try:
            if not event_data:
                return

            data = event_data.get("data") or {}
            market = event_data.get("market") or data.get("market")
            if not market:
                return

            # Convert a market like "BTC/USDT" or "BTC-USD" into a display symbol (BTC, ETH, ...)
            base = market.split("/")[0].split("-")[0]
            symbol = base.upper()

            price = data.get("price")
            if price is None:
                return

            # Derive 24h percentage change and trend if available
            change_pct = data.get("change_percent_24h")
            trend = "stable"
            if isinstance(change_pct, (int, float)):
                if change_pct > 3:
                    trend = "bullish"
                elif change_pct < -3:
                    trend = "bearish"

            # Update caches
            self._prices[symbol] = float(price)
            self._volumes[symbol] = float(data.get("volume_24h", 0.0))
            self._trends[symbol] = trend
            # Use percentage change if present, otherwise fallback to 0.0
            self._24h_change[symbol] = float(change_pct) if change_pct is not None else 0.0

            update_payload = {
                "symbol": symbol,
                "price": self._prices[symbol],
                "volume": self._volumes.get(symbol, 0.0),
                "trend": self._trends.get(symbol, "stable"),
                "24h_change": self._24h_change.get(symbol, 0.0),
                "timestamp": data.get("timestamp") or self._get_timestamp(),
            }

            # Re-publish in legacy event topics used throughout the GUI
            if hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync("market.update", update_payload)
                self.event_bus.publish_sync("market.prices_update", update_payload)
            elif hasattr(self.event_bus, 'publish'):
                await self.event_bus.publish("market.update", update_payload)
                await self.event_bus.publish("market.prices_update", update_payload)

        except Exception as e:
            self.logger.error(f"Error handling live market.data.update: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_data_request(self, request_data):
        """Handle request for current market data."""
        try:
            self.logger.info(f"Received market data request: {request_data}")
            await self._publish_initial_data()
        except Exception as e:
            self.logger.error(f"Error handling market data request: {e}")
            self.logger.error(traceback.format_exc())
    
    def _handle_market_data_response(self, response):
        try:
            if not response:
                return
            request_id = response.get("request_id")
            if not request_id:
                return
            future = self._pending_historical_requests.pop(request_id, None)
            if future is not None and not future.done():
                future.set_result(response.get("data"))
        except Exception as e:
            self.logger.error(f"Error handling market.data.response: {e}")
            self.logger.error(traceback.format_exc())

    async def _handle_market_data_response_async(self, event_type, data):
        self._handle_market_data_response(data)

    async def _handle_historical_request(self, request_data):
        """Handle request for historical market data."""
        try:
            symbol = request_data.get("symbol", "BTC")
            days = request_data.get("days", 30)
            
            self.logger.info(f"Received historical data request for {symbol} ({days} days)")
            # In live mode, do not fabricate candles. If a dedicated historical
            # provider is present (e.g. MarketDataStreaming or MarketAPI), it
            # should answer `market.data.request` with historical=True. Here we
            # simply emit an empty dataset to avoid serving fake data.
            if not self.event_bus:
                return

            exchange = request_data.get("exchange")
            market = request_data.get("market")
            if not exchange:
                exchange = "binance"
            if not market:
                base_symbol = symbol.upper()
                if exchange == "coinbase":
                    market = f"{base_symbol}-USD"
                else:
                    market = f"{base_symbol}/USDT"

            limit = request_data.get("limit")
            if not isinstance(limit, int):
                try:
                    limit = int(days) * 24
                except Exception:
                    limit = 100
            if limit <= 0:
                limit = 100

            loop = asyncio.get_running_loop()
            request_id = f"hist_{symbol}_{int(loop.time() * 1000)}"
            future = loop.create_future()
            self._pending_historical_requests[request_id] = future

            payload = {
                "request_id": request_id,
                "exchange": exchange,
                "market": market,
                "historical": True,
                "limit": limit,
            }

            if hasattr(self.event_bus, "publish_sync"):
                self.event_bus.publish_sync("market.data.request", payload)
            elif hasattr(self.event_bus, "publish"):
                await self.event_bus.publish("market.data.request", payload)

            try:
                result = await asyncio.wait_for(future, timeout=5.0)
            except asyncio.TimeoutError:
                self._pending_historical_requests.pop(request_id, None)
                result = []

            data_list = []
            status = "no_cached_history"
            if isinstance(result, dict) and "error" in result:
                data_list = []
                status = "error"
            elif isinstance(result, list):
                data_list = result
                status = "ok" if data_list else "no_cached_history"
            elif result:
                data_list = result
                status = "ok"

            response = {
                "symbol": symbol,
                "data": data_list,
                "period": f"{days}d",
                "timestamp": self._get_timestamp(),
                "status": status,
                "exchange": exchange,
                "market": market,
            }

            if hasattr(self.event_bus, "publish_sync"):
                self.event_bus.publish_sync("market.historical_data", response)
            elif hasattr(self.event_bus, "publish"):
                await self.event_bus.publish("market.historical_data", response)
        except Exception as e:
            self.logger.error(f"Error handling historical data request: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_system_ready(self, data):
        """Handle system ready event."""
        self.logger.info("Received system ready event, ensuring data streaming is active")
        # Ensure data streaming is active
        self._start_streaming()
        
        # Publish initial data again to ensure all components have the latest
        await self._publish_initial_data()
    
    def cleanup(self):
        """Clean up resources."""
        self._stop_streaming()

# Component initialization function
def initialize_component(event_bus=None):
    """Initialize the market data component.
    
    Args:
        event_bus: Event bus for component communication
        
    Returns:
        Initialized MarketDataProvider instance
    """
    logger = logging.getLogger("KingdomAI.Components.Market")
    logger.info("Initializing Market Data Component")
    
    try:
        # Create the market data provider
        market_provider = MarketDataProvider(event_bus)
        
        # Schedule initialization (can't use await in this function)
        if event_bus:
            asyncio.create_task(market_provider.initialize())
            logger.info("Scheduled market data provider initialization")
        
        return market_provider
    except Exception as e:
        logger.error(f"Error initializing market data component: {e}")
        logger.error(traceback.format_exc())
        return None
