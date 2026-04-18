#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MarketDataStreaming component for real-time market data.
"""

import os
import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Optional
import aiohttp
import websockets

from core.base_component import BaseComponent
from core.api_key_manager import APIKeyManager
from core.real_exchange_executor import RealExchangeExecutor
from core.exchange_universe import (
    build_real_exchange_api_keys,
    build_canonical_exchange_markets,
)

logger = logging.getLogger(__name__)

class MarketDataStreaming(BaseComponent):
    """
    Component for streaming real-time market data from exchanges via WebSockets.
    Handles connections to multiple exchanges and normalizes data formats.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the MarketDataStreaming component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        # Runtime compatibility: some legacy call sites pass args in wrong order.
        # Treat any non-event-bus object in first position as config payload.
        is_bus_like = bool(event_bus) and (hasattr(event_bus, "subscribe") or hasattr(event_bus, "subscribe_sync"))
        if not is_bus_like and event_bus is not None:
            first_config = dict(event_bus) if isinstance(event_bus, dict) else {}
            if config is not None and (hasattr(config, "subscribe") or hasattr(config, "subscribe_sync")):
                event_bus = config
                config = first_config or None
            else:
                event_bus = None
                if isinstance(config, dict):
                    merged = dict(first_config)
                    merged.update(config)
                    config = merged
                else:
                    config = first_config or config
        super().__init__(event_bus=event_bus, config=config)
        if self.event_bus is None:
            try:
                from core.event_bus import EventBus
                self.event_bus = EventBus.get_instance()
            except Exception:
                pass
        self.name = "MarketDataStreaming"
        self.description = "Streams real-time market data from exchanges"

        # Real exchange executor used for REST-based streaming when a
        # dedicated WebSocket integration is not available. This instance is
        # initialized from the same APIKeyManager + build_real_exchange_api_keys
        # pipeline used in the real_exchange_smoke_test so that we operate on
        # the exact same venues and credentials.
        self.real_exchange_executor: Optional[RealExchangeExecutor] = None

        # Exchange configurations
        # If the caller provided an explicit "exchanges" config, honor it as
        # an override. Otherwise, derive the canonical exchange/market list
        # from APIKeyManager + exchange_universe so the UI, executors, and
        # smoke tests all share the same enabled venues and symbols.
        self.exchanges = self.config.get("exchanges")
        if not self.exchanges:
            self.exchanges = self._build_exchanges_from_api_keys()
        
        # Streaming settings
        self.update_interval = self.config.get("update_interval", 1.0)  # In seconds
        self.reconnect_delay = self.config.get("reconnect_delay", 5.0)  # In seconds
        self.max_reconnect_attempts = self.config.get("max_reconnect_attempts", 10)
        
        # Data settings
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.cache_duration = self.config.get("cache_duration", 3600)  # 1 hour in seconds
        
        # Internal state
        self.connections = {}  # WebSocket connections
        self.connection_tasks = {}  # Connection tasks
        self.market_data = {}  # Current market data
        self.historical_data = {}  # Historical market data
        self.is_streaming = False
        self.last_updated = {}  # Last update timestamps
        self.subscriptions = set()  # Active market subscriptions
        self._exchange_suspend_until = {}
        self._error_log_last_ts = {}
        self._symbol_resolution_cache = {}
        self.auth_error_suspend_seconds = float(self.config.get("auth_error_suspend_seconds", 900.0))
        self.geo_error_suspend_seconds = float(self.config.get("geo_error_suspend_seconds", 3600.0))
        self.ws_outage_suspend_seconds = float(self.config.get("ws_outage_suspend_seconds", 180.0))

        # Optional Polygon/Massive shadow adapter (default ON)
        self.enable_polygon_shadow = bool(self.config.get("enable_polygon_shadow", True))
        self.polygon_api_key = (
            self.config.get("polygon_api_key")
            or os.environ.get("POLY_API_KEY")
            or os.environ.get("POLYGON_API_KEY")
            or os.environ.get("MASSIVE_API_KEY")
            or ""
        )
        if not self.polygon_api_key:
            self.polygon_api_key = self._resolve_polygon_api_key()
        self.finnhub_api_key = (
            self.config.get("finnhub_api_key")
            or os.environ.get("FINNHUB_API_KEY")
            or ""
        )
        if not self.finnhub_api_key:
            self.finnhub_api_key = self._resolve_finnhub_api_key()
        self.polygon_symbols = list(self.config.get("polygon_symbols", ["AAPL"]))
        self.polygon_poll_interval = float(self.config.get("polygon_poll_interval", max(self.update_interval, 2.0)))
        # Optional Polymarket shadow feed (public Gamma API) for prediction-market awareness.
        self.enable_polymarket_shadow = bool(self.config.get("enable_polymarket_shadow", True))
        self.polymarket_gamma_url = str(
            self.config.get("polymarket_gamma_url", "https://gamma-api.polymarket.com/markets")
        )
        self.polymarket_limit = int(self.config.get("polymarket_limit", 30) or 30)
        self.polymarket_poll_interval = float(self.config.get("polymarket_poll_interval", max(self.update_interval, 2.0)))
        self.market_stale_after_seconds = float(self.config.get("market_stale_after_seconds", 15.0))
        self.polygon_reauth_retry_seconds = float(self.config.get("polygon_reauth_retry_seconds", 600.0))
        self._polygon_disabled_until = 0.0
        self._register_runtime_event_handlers()

    def _register_runtime_event_handlers(self) -> None:
        """Best-effort event wiring at construction time.

        Some runtime paths register components without invoking initialize().
        This ensures API-key propagation still reaches market streaming.
        """
        if not self.event_bus:
            return
        events = (
            "api.keys.all.loaded",
            "api.key.added",
            "api.key.updated",
            "api.key.removed",
            "api.keys.reloaded",
        )
        for event_name in events:
            try:
                if hasattr(self.event_bus, "subscribe"):
                    self.event_bus.subscribe(event_name, self.on_api_keys_reloaded_sync)
                elif hasattr(self.event_bus, "subscribe_sync"):
                    self.event_bus.subscribe_sync(event_name, self.on_api_keys_reloaded_sync)
            except Exception:
                continue

    def _default_exchanges(self):
        """Return the legacy Binance/Coinbase configuration.

        Used only as a safety fallback when API keys are not available or
        canonical discovery fails. This does **not** introduce any simulated
        data; it simply limits streaming to the two WebSocket integrations
        already implemented in this component.
        """

        return {
            "binance": {
                "ws_url": "wss://stream.binance.com:9443/ws",
                "http_url": "https://api.binance.com/api",
                "enabled": True,
                "markets": ["BTC/USDT"],
            },
            "coinbase": {
                "ws_url": "wss://ws-feed.pro.coinbase.com",
                "http_url": "https://api.pro.coinbase.com",
                "enabled": True,
                "markets": ["BTC-USD"],
            },
        }

    def _resolve_polygon_api_key(self) -> str:
        """Resolve Massive/Polygon API key from APIKeyManager if env/config is empty."""
        try:
            km = APIKeyManager.get_instance()
            km.initialize_sync()
            all_keys = km.get_all_api_keys() if hasattr(km, "get_all_api_keys") else km.api_keys
            if not isinstance(all_keys, dict):
                return ""

            aliases = ("massive", "polygon_io", "polygon", "polygonio", "massive_com")
            for service in aliases:
                data = all_keys.get(service)
                if not isinstance(data, dict):
                    continue
                candidate = (
                    data.get("api_key")
                    or data.get("key")
                    or data.get("token")
                    or ""
                )
                if isinstance(candidate, str) and candidate.strip():
                    logger.info("Using %s API key from APIKeyManager for polygon shadow feed", service)
                    return candidate.strip()
        except Exception as e:
            logger.debug("Unable to resolve polygon API key from APIKeyManager: %s", e)
        return ""

    def _resolve_finnhub_api_key(self) -> str:
        """Resolve Finnhub API key for Massive fallback."""
        try:
            km = APIKeyManager.get_instance()
            km.initialize_sync()
            all_keys = km.get_all_api_keys() if hasattr(km, "get_all_api_keys") else km.api_keys
            if not isinstance(all_keys, dict):
                return ""
            aliases = ("finnhub", "finn_hub")
            for service in aliases:
                data = all_keys.get(service)
                if not isinstance(data, dict):
                    continue
                candidate = data.get("api_key") or data.get("key") or data.get("token") or ""
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        except Exception:
            return ""
        return ""

    def _classify_error(self, err) -> str:
        """Classify common external API/network failures for resilient handling."""
        msg = str(err).lower()
        if "restricted location" in msg or "http 451" in msg or " 451" in msg:
            return "geo_restricted"
        if any(x in msg for x in ["invalid api-key", "\"code\":-2015", "not authorized", "permission denied", "http 401", "http 403"]):
            return "auth_invalid"
        if "http 530" in msg or "server rejected websocket connection: http 530" in msg:
            return "ws_unavailable"
        if "\"code\":-1021" in msg or "timestamp for this request was" in msg:
            return "time_skew"
        if "does not have market symbol" in msg or "badsymbol" in msg:
            return "symbol_invalid"
        return "generic"

    def _throttled_log(self, key: str, level: str, message: str, *args, cooldown: float = 45.0) -> None:
        now = time.time()
        last = float(self._error_log_last_ts.get(key, 0.0) or 0.0)
        if (now - last) < cooldown:
            return
        self._error_log_last_ts[key] = now
        log_fn = getattr(logger, level, logger.warning)
        log_fn(message, *args)

    def _suspend_exchange(self, exchange_id: str, seconds: float, reason: str) -> None:
        until = time.time() + max(1.0, float(seconds))
        prev = float(self._exchange_suspend_until.get(exchange_id, 0.0) or 0.0)
        self._exchange_suspend_until[exchange_id] = max(prev, until)
        remaining = int(max(0.0, self._exchange_suspend_until[exchange_id] - time.time()))
        self._throttled_log(
            f"suspend:{exchange_id}:{reason}",
            "warning",
            "Temporarily suspending %s for %ss (%s)",
            exchange_id,
            remaining,
            reason,
            cooldown=10.0,
        )

    def _exchange_suspended_for(self, exchange_id: str) -> float:
        until = float(self._exchange_suspend_until.get(exchange_id, 0.0) or 0.0)
        return max(0.0, until - time.time())

    async def _resolve_symbol_for_exchange(self, exchange_id: str, ccxt_exchange, symbol: str) -> str:
        """Resolve symbol variants (e.g., swap suffixes) if canonical symbol fails."""
        cache_key = f"{exchange_id}:{symbol}"
        cached = self._symbol_resolution_cache.get(cache_key)
        if isinstance(cached, str) and cached:
            return cached

        resolved = symbol
        try:
            markets = getattr(ccxt_exchange, "markets", None) or {}
            if not isinstance(markets, dict) or not markets:
                markets = await asyncio.to_thread(ccxt_exchange.load_markets)
            market_keys = set(markets.keys()) if isinstance(markets, dict) else set()
            if not market_keys:
                self._symbol_resolution_cache[cache_key] = resolved
                return resolved
            if symbol in market_keys:
                self._symbol_resolution_cache[cache_key] = symbol
                return symbol

            if "/" in symbol:
                base, quote = symbol.split("/", 1)
                candidates = [
                    f"{base}/{quote}:{quote}",
                    f"{base}/{quote}:USDT",
                    f"{base}/{quote}:USD",
                    f"{base}/{quote}:USDC",
                    f"{base}/USDT",
                    f"{base}/USD",
                    f"{base}/USDC",
                ]
                for cand in candidates:
                    if cand in market_keys:
                        resolved = cand
                        break
        except Exception:
            resolved = symbol

        self._symbol_resolution_cache[cache_key] = resolved
        return resolved

    def _build_exchanges_from_api_keys(self):
        """Derive exchange/market list from API keys and canonical universe.

        This uses APIKeyManager + build_real_exchange_api_keys to instantiate
        a RealExchangeExecutor, then uses build_canonical_exchange_markets to
        decide which **symbols** to stream per enabled exchange.
        - Binance/Coinbase use existing WebSocket integrations.
        - All other ccxt exchanges are streamed via REST polling using the
          shared RealExchangeExecutor instance.
        """

        try:
            km = APIKeyManager.get_instance()
            km.initialize_sync()
            raw_keys = km.api_keys
            if not isinstance(raw_keys, dict) or not raw_keys:
                logger.warning(
                    "APIKeyManager.api_keys is empty; falling back to default Binance/Coinbase exchanges",
                )
                return self._default_exchanges()

            flat_keys = build_real_exchange_api_keys(raw_keys)
            if not flat_keys:
                logger.warning(
                    "build_real_exchange_api_keys returned no entries; falling back to default exchanges",
                )
                return self._default_exchanges()

            executor = None
            if self.event_bus is not None and hasattr(self.event_bus, "get_component"):
                try:
                    executor = self.event_bus.get_component(
                        "real_exchange_executor",
                        silent=True,
                    )
                except Exception:
                    executor = None

            if executor is None:
                executor = RealExchangeExecutor(api_keys=flat_keys, event_bus=self.event_bus)
                if self.event_bus is not None and hasattr(self.event_bus, "register_component"):
                    try:
                        self.event_bus.register_component("real_exchange_executor", executor)
                    except Exception:
                        pass

            self.real_exchange_executor = executor

            canonical_markets = build_canonical_exchange_markets(raw_keys)
            exchanges = {}

            # Start with all ccxt-based exchanges and add Oanda (native FX)
            # if its connector has been initialized in RealExchangeExecutor.
            names = set(self.real_exchange_executor.exchanges.keys())
            if "oanda" in self.real_exchange_executor.connectors:
                names.add("oanda")

            for name in sorted(names):
                symbol_info = canonical_markets.get(name)
                if not symbol_info:
                    continue
                symbol = symbol_info.get("symbol")
                if not symbol:
                    continue

                if name == "binance":
                    exchanges[name] = {
                        "ws_url": "wss://stream.binance.com:9443/ws",
                        "http_url": "https://api.binance.com/api",
                        "enabled": True,
                        "markets": [symbol],
                    }
                elif name == "coinbase":
                    # Coinbase WebSocket uses product_ids with "-" instead
                    # of "/". Keep streaming via WebSocket for this venue.
                    product = symbol.replace("/", "-")
                    exchanges[name] = {
                        "ws_url": "wss://ws-feed.pro.coinbase.com",
                        "http_url": "https://api.pro.coinbase.com",
                        "enabled": True,
                        "markets": [product],
                    }
                else:
                    exchanges[name] = {
                        "enabled": True,
                        "markets": [symbol],
                    }

            if not exchanges:
                logger.warning(
                    "RealExchangeExecutor reported no ccxt exchanges; falling back to default exchanges",
                )
                return self._default_exchanges()

            return exchanges
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to derive exchanges from API keys: %s", e)
            return self._default_exchanges()
        
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize the MarketDataStreaming component.
        
        Args:
            event_bus: Optional event bus to use (default: None, uses the one from constructor)
            config: Optional config to use (default: None, uses the one from constructor)
            
        Returns:
            bool: True if initialization is successful
        """
        logger.info("Initializing MarketDataStreaming component")
        
        # Update event_bus and config if provided
        if event_bus:
            self.event_bus = event_bus
        if self.event_bus is None:
            try:
                from core.event_bus import EventBus
                self.event_bus = EventBus.get_instance()
            except Exception:
                self.event_bus = None
        if config:
            self.config.update(config)
        if not self.polygon_api_key:
            self.polygon_api_key = self._resolve_polygon_api_key()
        
        # Subscribe to relevant events
        if self.event_bus:
            success_start = self.event_bus.subscribe_sync("market.streaming.start", self.on_streaming_start)
            success_stop = self.event_bus.subscribe_sync("market.streaming.stop", self.on_streaming_stop)
            success_data = self.event_bus.subscribe_sync("market.data.request", self.on_data_request)
            success_sub_add = self.event_bus.subscribe_sync("market.subscription.add", self.on_subscription_add)
            success_sub_remove = self.event_bus.subscribe_sync("market.subscription.remove", self.on_subscription_remove)
            success_shutdown = self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
            success_keys_all_loaded = self.event_bus.subscribe_sync("api.keys.all.loaded", self.on_api_keys_reloaded_sync)
            success_key_added = self.event_bus.subscribe_sync("api.key.added", self.on_api_keys_reloaded_sync)
            success_key_updated = self.event_bus.subscribe_sync("api.key.updated", self.on_api_keys_reloaded_sync)
            success_key_removed = self.event_bus.subscribe_sync("api.key.removed", self.on_api_keys_reloaded_sync)
            success_keys_reloaded = self.event_bus.subscribe_sync("api.keys.reloaded", self.on_api_keys_reloaded_sync)
            
            # Log subscription results
            if not all([
                success_start,
                success_stop,
                success_data,
                success_sub_add,
                success_sub_remove,
                success_shutdown,
                success_keys_all_loaded,
                success_key_added,
                success_key_updated,
                success_key_removed,
                success_keys_reloaded,
            ]):
                logger.warning("Some event subscriptions failed")
        else:
            logger.warning("No event_bus available, component will operate with limited functionality")
        
        # Load saved market data
        await self.load_market_data()
        
        # Start streaming if auto-start is enabled
        if self.config.get("auto_start", True):
            await self.start_streaming()
        
        logger.info("MarketDataStreaming component initialized")
        return True
        
    async def load_market_data(self):
        """Load saved market data from storage."""
        data_file = os.path.join(self.config.get("data_dir", "data"), "market_data.json")
        
        try:
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    
                # Load market data
                self.market_data = saved_data.get("current", {})
                
                # Check if historical data is not too old
                history = saved_data.get("historical", {})
                cutoff_time = (datetime.now() - timedelta(seconds=self.cache_duration)).isoformat()
                
                for market, data in history.items():
                    recent_data = [
                        entry for entry in data
                        if entry.get("timestamp", "0") >= cutoff_time
                    ]
                    if recent_data:
                        self.historical_data[market] = recent_data
                
                logger.info(f"Loaded market data for {len(self.market_data)} markets")
        except Exception as e:
            logger.error(f"Error loading market data: {str(e)}")
    
    async def save_market_data(self):
        """Save market data to storage."""
        data_file = os.path.join(self.config.get("data_dir", "data"), "market_data.json")
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(data_file), exist_ok=True)
            
            # Prepare data for saving
            save_data = {
                "current": self.market_data,
                "historical": self.historical_data,
                "last_saved": datetime.now().isoformat()
            }
            
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)
                
            logger.info(f"Saved market data for {len(self.market_data)} markets")
        except Exception as e:
            logger.error(f"Error saving market data: {str(e)}")
    
    async def start_streaming(self):
        """Start streaming market data."""
        if self.is_streaming:
            logger.warning("Market data streaming is already active")
            return
        
        logger.info("Starting market data streaming")
        self.is_streaming = True
        
        # Initialize subscriptions from configured markets
        for exchange_id, exchange_config in self.exchanges.items():
            if exchange_config.get("enabled", True):
                for market in exchange_config.get("markets", []):
                    self.subscriptions.add(f"{exchange_id}:{market}")
        
        # Start connections to exchanges
        for exchange_id, exchange_config in self.exchanges.items():
            if not exchange_config.get("enabled", True):
                continue

            # Binance/Coinbase keep using their dedicated WebSocket handlers.
            if exchange_id in ("binance", "coinbase"):
                self.connection_tasks[exchange_id] = asyncio.create_task(
                    self.connect_to_exchange(exchange_id, exchange_config),
                )
            else:
                # All other ccxt exchanges stream via REST polling through
                # RealExchangeExecutor, using the canonical symbol list.
                self.connection_tasks[exchange_id] = asyncio.create_task(
                    self._poll_exchange_markets(exchange_id, exchange_config),
                )

        # Start optional Polygon/Massive shadow feed in parallel without
        # impacting existing exchange pipelines.
        if self.enable_polygon_shadow:
            if not self.polygon_api_key:
                logger.warning("Polygon shadow feed enabled but API key is missing; skipping shadow task")
            else:
                self.connection_tasks["polygon_shadow"] = asyncio.create_task(
                    self._poll_polygon_shadow_markets(),
                )
        if self.enable_polymarket_shadow:
            self.connection_tasks["polymarket_shadow"] = asyncio.create_task(
                self._poll_polymarket_shadow_markets(),
            )
        
        # Publish streaming started event
        if self.event_bus:
            self.event_bus.publish_sync("market.streaming.started", {
                "exchanges": list(self.connection_tasks.keys()),
                "subscriptions": list(self.subscriptions),
                "timestamp": datetime.now().isoformat()
            })
    
    async def stop_streaming(self):
        """Stop streaming market data."""
        if not self.is_streaming:
            logger.warning("Market data streaming is not active")
            return
        
        logger.info("Stopping market data streaming")
        self.is_streaming = False
        
        # Cancel all connection tasks
        for exchange_id, task in self.connection_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for exchange_id, connection in self.connections.items():
            if hasattr(connection, "close") and callable(connection.close):
                try:
                    # Check if close is a coroutine function or regular function
                    if asyncio.iscoroutinefunction(connection.close):
                        await connection.close()
                    else:
                        # Call synchronous close function
                        connection.close()
                except Exception as e:
                    logger.error(f"Error closing connection to {exchange_id}: {str(e)}")
        
        # Clear connection data
        self.connections = {}
        self.connection_tasks = {}
        
        # Save final market data
        await self.save_market_data()
        
        # Publish streaming stopped event
        if self.event_bus:
            self.event_bus.publish_sync("market.streaming.stopped", {
                "timestamp": datetime.now().isoformat()
            })
    
    async def connect_to_exchange(self, exchange_id, exchange_config):
        """
        Connect to an exchange and maintain the connection.
        
        Args:
            exchange_id: Exchange identifier
            exchange_config: Exchange configuration
        """
        ws_url = exchange_config.get("ws_url")
        if not ws_url:
            logger.error(f"WebSocket URL not configured for exchange {exchange_id}")
            return
        
        reconnect_attempts = 0
        
        while self.is_streaming and reconnect_attempts < self.max_reconnect_attempts:
            suspended_for = self._exchange_suspended_for(exchange_id)
            if suspended_for > 0:
                await asyncio.sleep(min(max(1.0, suspended_for), 10.0))
                continue
            try:
                logger.info(f"Connecting to {exchange_id} at {ws_url}")
                
                # Connect to WebSocket
                if exchange_id == "binance":
                    await self.connect_binance(ws_url, exchange_config)
                elif exchange_id == "coinbase":
                    await self.connect_coinbase(ws_url, exchange_config)
                else:
                    logger.warning(f"Unsupported exchange: {exchange_id}")
                
                # Reset reconnect attempts on successful connection
                reconnect_attempts = 0
                
            except (websockets.exceptions.ConnectionClosed, 
                    aiohttp.ClientError, asyncio.CancelledError) as e:
                
                if isinstance(e, asyncio.CancelledError):
                    logger.info(f"Connection to {exchange_id} cancelled")
                    break
                    
                logger.error(f"Connection to {exchange_id} closed: {str(e)}")
                reconnect_attempts += 1
                
                # Exponential backoff for reconnection
                delay = min(self.reconnect_delay * (2 ** (reconnect_attempts - 1)), 60)
                logger.info(f"Reconnecting to {exchange_id} in {delay} seconds (attempt {reconnect_attempts})")
                await asyncio.sleep(delay)
                
            except Exception as e:
                category = self._classify_error(e)
                if category == "geo_restricted":
                    self._suspend_exchange(exchange_id, self.geo_error_suspend_seconds, "geo_restricted")
                elif category == "auth_invalid":
                    self._suspend_exchange(exchange_id, self.auth_error_suspend_seconds, "auth_invalid")
                elif category == "ws_unavailable":
                    self._suspend_exchange(exchange_id, self.ws_outage_suspend_seconds, "ws_unavailable")
                    # Safe fallback: keep venue alive via REST polling if WS is blocked.
                    try:
                        await self._poll_exchange_markets(exchange_id, exchange_config)
                        return
                    except Exception as fallback_err:
                        self._throttled_log(
                            f"ws_fallback:{exchange_id}",
                            "warning",
                            "REST fallback failed for %s: %s",
                            exchange_id,
                            fallback_err,
                        )
                self._throttled_log(
                    f"connect:{exchange_id}:{category}",
                    "warning",
                    "Error connecting to %s (%s): %s",
                    exchange_id,
                    category,
                    e,
                )
                reconnect_attempts += 1
                await asyncio.sleep(self.reconnect_delay)
        
        if reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Maximum reconnection attempts reached for {exchange_id}, giving up")
            
            # Publish connection error event
            if self.event_bus:
                self.event_bus.publish_sync("market.connection.error", {
                    "exchange": exchange_id,
                    "error": "Maximum reconnection attempts reached",
                    "timestamp": datetime.now().isoformat()
                })

    async def _poll_exchange_markets(self, exchange_id, exchange_config):
        """Poll real exchanges via RealExchangeExecutor/ccxt for live prices.

        This is used for all enabled exchanges that do not have a dedicated
        WebSocket handler in this component. It relies solely on REAL data
        returned by the underlying ccxt exchange instances managed by
        RealExchangeExecutor; no simulated or placeholder values are ever
        generated here. On failures, errors are logged and the offending
        symbol is skipped for that iteration.
        """

        rex = self.real_exchange_executor
        if not rex:
            logger.warning(
                "RealExchangeExecutor is not initialized; cannot poll markets for %s",
                exchange_id,
            )
            return

        ccxt_exchange = rex.exchanges.get(exchange_id)
        connector = rex.connectors.get(exchange_id)

        if ccxt_exchange is None and (exchange_id != "oanda" or connector is None):
            logger.warning(
                "Exchange %s has no supported connector in RealExchangeExecutor; polling not supported",
                exchange_id,
            )
            return

        markets = exchange_config.get("markets", []) or []
        if not markets:
            logger.info("No markets configured for %s; skipping polling", exchange_id)
            return

        logger.info("Starting REST polling for %s markets on %s", len(markets), exchange_id)

        parallelism = int(self.config.get("poll_parallelism", 6) or 6)
        if parallelism < 1:
            parallelism = 1
        semaphore = asyncio.Semaphore(parallelism)

        async def _fetch_one(symbol: str):
            async with semaphore:
                if self._exchange_suspended_for(exchange_id) > 0:
                    return None
                try:
                    if ccxt_exchange is not None:
                        resolved_symbol = await self._resolve_symbol_for_exchange(exchange_id, ccxt_exchange, symbol)
                        ticker = await asyncio.to_thread(ccxt_exchange.fetch_ticker, resolved_symbol)
                    elif exchange_id == "oanda" and connector is not None:
                        resolved_symbol = symbol
                        ticker = await connector.fetch_ticker(symbol)  # type: ignore[attr-defined]
                    else:
                        return None
                except Exception as e:  # noqa: BLE001
                    category = self._classify_error(e)
                    if category == "geo_restricted":
                        self._suspend_exchange(exchange_id, self.geo_error_suspend_seconds, "geo_restricted")
                    elif category == "auth_invalid":
                        self._suspend_exchange(exchange_id, self.auth_error_suspend_seconds, "auth_invalid")
                    elif category == "time_skew":
                        self._suspend_exchange(exchange_id, 30.0, "time_skew")
                    self._throttled_log(
                        f"ticker:{exchange_id}:{symbol}:{category}",
                        "warning",
                        "Ticker fetch failed for %s %s (%s): %s",
                        exchange_id,
                        symbol,
                        category,
                        e,
                    )
                    return None
                if not isinstance(ticker, dict):
                    return None
                return (resolved_symbol if "resolved_symbol" in locals() else symbol), ticker

        while self.is_streaming:
            loop_start = time.time()
            fetch_tasks = [_fetch_one(market) for market in markets]
            fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            for item in fetch_results:
                if isinstance(item, BaseException) or item is None:
                    continue
                if not isinstance(item, tuple) or len(item) != 2:
                    continue
                symbol, ticker = item

                raw_price = (
                    ticker.get("last")
                    or ticker.get("close")
                    or ticker.get("ask")
                    or ticker.get("bid")
                )
                try:
                    price = float(raw_price) if raw_price is not None else 0.0
                except (TypeError, ValueError):
                    price = 0.0

                if not price:
                    # No usable price, skip without fabricating anything.
                    continue

                def _to_float(value) -> float:
                    try:
                        return float(value) if value is not None else 0.0
                    except (TypeError, ValueError):
                        return 0.0

                ts = ticker.get("timestamp")
                if ts is not None:
                    try:
                        ts_iso = datetime.fromtimestamp(float(ts) / 1000.0).isoformat()
                    except Exception:  # noqa: BLE001
                        ts_iso = datetime.now().isoformat()
                else:
                    ts_iso = datetime.now().isoformat()

                normalized_data = {
                    "exchange": exchange_id,
                    "market": symbol,
                    "price": price,
                    "bid": _to_float(ticker.get("bid")),
                    "ask": _to_float(ticker.get("ask")),
                    "volume_24h": _to_float(ticker.get("baseVolume")),
                    "timestamp": ts_iso,
                    "high_24h": _to_float(ticker.get("high")),
                    "low_24h": _to_float(ticker.get("low")),
                    "change_24h": _to_float(ticker.get("change")),
                    "change_percent_24h": _to_float(ticker.get("percentage")),
                }

                market_key = f"{exchange_id}:{symbol}"
                self.market_data[market_key] = normalized_data
                self.last_updated[market_key] = time.time()

                if self.cache_enabled:
                    self.store_historical_data(market_key, normalized_data)

                if self.event_bus:
                    self.event_bus.publish_sync(
                        "market.data.update",
                        {
                            "exchange": exchange_id,
                            "market": symbol,
                            "data": normalized_data,
                        },
                    )

            elapsed = time.time() - loop_start
            # Aim for approximately update_interval seconds between full
            # polling cycles per exchange.
            sleep_for = max(self.update_interval - elapsed, 0.0)
            if sleep_for <= 0:
                sleep_for = self.update_interval
            await asyncio.sleep(sleep_for)

    async def _poll_polygon_shadow_markets(self):
        """Poll Polygon/Massive REST snapshots and publish canonical market events.

        This runs in shadow mode and does not replace existing exchange feeds.
        """
        if not self.polygon_api_key:
            return

        symbols = [str(s).strip().upper() for s in self.polygon_symbols if str(s).strip()]
        if not symbols:
            logger.warning("Polygon shadow feed has no symbols configured")
            return

        logger.info("Starting Polygon shadow feed for symbols: %s", symbols)
        timeout = aiohttp.ClientTimeout(total=15)
        base_url = "https://api.massive.com"
        use_finnhub_fallback = False

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while self.is_streaming:
                # If recently unauthorized, wait then retry key resolution.
                if self._polygon_disabled_until > time.time():
                    await asyncio.sleep(min(max(1.0, self._polygon_disabled_until - time.time()), 10.0))
                    continue
                if not self.polygon_api_key:
                    self.polygon_api_key = self._resolve_polygon_api_key()
                    if not self.polygon_api_key:
                        await asyncio.sleep(self.polygon_poll_interval)
                        continue
                cycle_start = time.time()
                for symbol in symbols:
                    try:
                        if use_finnhub_fallback and self.finnhub_api_key:
                            url = "https://finnhub.io/api/v1/quote"
                            params = {"symbol": symbol, "token": self.finnhub_api_key}
                            async with session.get(url, params=params) as resp:
                                if resp.status in (401, 403):
                                    self._throttled_log(
                                        "finnhub:auth",
                                        "warning",
                                        "Finnhub fallback unauthorized (HTTP %s).",
                                        resp.status,
                                        cooldown=30.0,
                                    )
                                    continue
                                if resp.status != 200:
                                    self._throttled_log(
                                        f"finnhub:{symbol}:http",
                                        "warning",
                                        "Finnhub quote %s failed with HTTP %s",
                                        symbol,
                                        resp.status,
                                        cooldown=30.0,
                                    )
                                    continue
                                quote = await resp.json()
                                data = {
                                    "ticker": {
                                        "min": {"c": quote.get("c"), "t": quote.get("t")},
                                        "day": {"h": quote.get("h"), "l": quote.get("l")},
                                        "todaysChange": (float(quote.get("c") or 0.0) - float(quote.get("pc") or 0.0)),
                                        "todaysChangePerc": (
                                            ((float(quote.get("c") or 0.0) - float(quote.get("pc") or 0.0)) / float(quote.get("pc") or 1.0)) * 100.0
                                            if float(quote.get("pc") or 0.0) > 0 else 0.0
                                        ),
                                        "updated": quote.get("t"),
                                    }
                                }
                        else:
                            url = f"{base_url}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
                            params = {"apiKey": self.polygon_api_key}
                            async with session.get(url, params=params) as resp:
                                if resp.status in (401, 403):
                                    # Massive token rejected: keep feed alive with legal fallback.
                                    if self.finnhub_api_key:
                                        use_finnhub_fallback = True
                                        self._throttled_log(
                                            "polygon:auth:fallback",
                                            "warning",
                                            "Polygon/Massive unauthorized (HTTP %s). Switching to Finnhub fallback.",
                                            resp.status,
                                            cooldown=30.0,
                                        )
                                        continue
                                    self._polygon_disabled_until = time.time() + max(60.0, self.polygon_reauth_retry_seconds)
                                    self._throttled_log(
                                        "polygon:auth",
                                        "warning",
                                        "Polygon/Massive unauthorized (HTTP %s). Pausing feed and will auto-retry key resolution.",
                                        resp.status,
                                        cooldown=30.0,
                                    )
                                    self.polygon_api_key = ""
                                    break
                                if resp.status != 200:
                                    logger.warning("Polygon snapshot %s failed with HTTP %s", symbol, resp.status)
                                    continue
                                data = await resp.json()
                    except Exception as e:
                        self._throttled_log(
                            f"polygon:{symbol}:poll_error",
                            "warning",
                            "Polygon snapshot poll failed for %s: %s",
                            symbol,
                            e,
                            cooldown=30.0,
                        )
                        continue

                    ticker = data.get("ticker") if isinstance(data, dict) else None
                    if not isinstance(ticker, dict):
                        continue

                    min_bar = ticker.get("min") if isinstance(ticker.get("min"), dict) else {}
                    last_trade = ticker.get("lastTrade") if isinstance(ticker.get("lastTrade"), dict) else {}
                    day_bar = ticker.get("day") if isinstance(ticker.get("day"), dict) else {}

                    def _to_float(v):
                        try:
                            return float(v) if v is not None else 0.0
                        except (TypeError, ValueError):
                            return 0.0

                    updated_raw = ticker.get("updated") or min_bar.get("t") or last_trade.get("t")
                    now_ts = time.time()
                    updated_ts = now_ts
                    if updated_raw is not None:
                        try:
                            # massive snapshot timestamps are generally ns or ms.
                            updated_num = float(updated_raw)
                            if updated_num > 1e15:  # ns
                                updated_ts = updated_num / 1_000_000_000.0
                            elif updated_num > 1e12:  # ms
                                updated_ts = updated_num / 1000.0
                            else:
                                updated_ts = updated_num
                        except Exception:
                            updated_ts = now_ts

                    age_seconds = max(0.0, now_ts - updated_ts)
                    normalized_data = {
                        "exchange": "polygon",
                        "market": f"{symbol}/USD",
                        "symbol": symbol,
                        "price": _to_float(min_bar.get("c")) or _to_float(last_trade.get("p")),
                        "bid": _to_float(ticker.get("lastQuote", {}).get("p")) if isinstance(ticker.get("lastQuote"), dict) else 0.0,
                        "ask": _to_float(ticker.get("lastQuote", {}).get("P")) if isinstance(ticker.get("lastQuote"), dict) else 0.0,
                        "volume_24h": _to_float(day_bar.get("v")),
                        "high_24h": _to_float(day_bar.get("h")),
                        "low_24h": _to_float(day_bar.get("l")),
                        "change_24h": _to_float(ticker.get("todaysChange")),
                        "change_percent_24h": _to_float(ticker.get("todaysChangePerc")),
                        "timestamp": datetime.fromtimestamp(updated_ts).isoformat(),
                        "provider": "polygon_shadow",
                        "source_provider": "finnhub_fallback" if use_finnhub_fallback else "polygon_massive",
                        "ingested_at": datetime.now().isoformat(),
                        "data_age_seconds": age_seconds,
                        "is_stale": age_seconds > self.market_stale_after_seconds,
                    }

                    market_key = f"polygon:{symbol}/USD"
                    self.market_data[market_key] = normalized_data
                    self.last_updated[market_key] = now_ts
                    if self.cache_enabled:
                        self.store_historical_data(market_key, normalized_data)

                    if self.event_bus:
                        payload = {
                            "exchange": "polygon",
                            "market": f"{symbol}/USD",
                            "data": normalized_data,
                        }
                        self.event_bus.publish_sync("market.data.update", payload)
                        # Preserve downstream compatibility for trading listeners
                        self.event_bus.publish_sync("trading.market_data_update", payload)

                elapsed = time.time() - cycle_start
                sleep_for = max(self.polygon_poll_interval - elapsed, 0.25)
                await asyncio.sleep(sleep_for)

    async def _poll_polymarket_shadow_markets(self):
        """Poll Polymarket Gamma API (shadow mode) for prediction-market context.

        This augments market awareness and AI learning without replacing
        existing exchange execution/routing paths.
        """
        logger.info("Starting Polymarket shadow feed (Gamma API)")
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while self.is_streaming:
                cycle_start = time.time()
                try:
                    params = {"limit": str(max(1, self.polymarket_limit))}
                    async with session.get(self.polymarket_gamma_url, params=params) as resp:
                        if resp.status != 200:
                            logger.warning("Polymarket Gamma poll failed with HTTP %s", resp.status)
                            await asyncio.sleep(self.polymarket_poll_interval)
                            continue
                        data = await resp.json()
                except Exception as e:
                    logger.warning("Polymarket Gamma poll error: %s", e)
                    await asyncio.sleep(self.polymarket_poll_interval)
                    continue

                markets = data if isinstance(data, list) else []
                now_ts = time.time()

                def _to_float(v):
                    try:
                        return float(v) if v is not None else 0.0
                    except (TypeError, ValueError):
                        return 0.0

                for m in markets:
                    if not isinstance(m, dict):
                        continue
                    market_id = str(m.get("id") or m.get("questionID") or m.get("slug") or "").strip()
                    if not market_id:
                        continue
                    question = str(m.get("question") or m.get("title") or market_id)
                    price = 0.0
                    outcome_prices = m.get("outcomePrices")
                    if isinstance(outcome_prices, list) and outcome_prices:
                        # Binary markets: use YES probability as primary reference price.
                        price = _to_float(outcome_prices[0])
                    if price <= 0.0:
                        price = _to_float(m.get("price") or m.get("lastPrice"))

                    normalized_data = {
                        "exchange": "polymarket",
                        "market": market_id,
                        "symbol": market_id,
                        "question": question,
                        "price": price,
                        "bid": _to_float(m.get("bestBid")),
                        "ask": _to_float(m.get("bestAsk")),
                        "volume_24h": _to_float(m.get("volume24hr") or m.get("volume")),
                        "liquidity": _to_float(m.get("liquidity")),
                        "timestamp": datetime.now().isoformat(),
                        "provider": "polymarket_shadow",
                    }

                    market_key = f"polymarket:{market_id}"
                    self.market_data[market_key] = normalized_data
                    self.last_updated[market_key] = now_ts
                    if self.cache_enabled:
                        self.store_historical_data(market_key, normalized_data)

                    if self.event_bus:
                        payload = {
                            "exchange": "polymarket",
                            "market": market_id,
                            "data": normalized_data,
                        }
                        self.event_bus.publish_sync("market.data.update", payload)
                        self.event_bus.publish_sync("trading.market_data_update", payload)

                elapsed = time.time() - cycle_start
                sleep_for = max(self.polymarket_poll_interval - elapsed, 0.5)
                await asyncio.sleep(sleep_for)
    
    async def connect_binance(self, ws_url, config):
        """
        Connect to Binance WebSocket.
        
        Args:
            ws_url: WebSocket URL
            config: Exchange configuration
        """
        # Get market symbols for subscription
        markets = config.get("markets", [])
        streams = []
        
        for market in markets:
            # Convert market format (BTC/USDT -> btcusdt)
            symbol = market.replace("/", "").lower()
            streams.append(f"{symbol}@ticker")
        
        # Create combined stream URL
        combined_url = f"{ws_url}/stream?streams={'/'.join(streams)}"
        
        async with websockets.connect(combined_url) as websocket:
            self.connections["binance"] = websocket
            
            # Publish connection status
            if self.event_bus:
                self.event_bus.publish_sync("market.connection.status", {
                    "exchange": "binance",
                    "status": "connected",
                    "subscriptions": streams,
                    "timestamp": datetime.now().isoformat()
                })
            
            while self.is_streaming:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Process the data
                    await self.process_binance_data(data)
                    
                except (websockets.exceptions.ConnectionClosed, json.JSONDecodeError) as e:
                    logger.error(f"Binance connection error: {str(e)}")
                    break
    
    async def connect_coinbase(self, ws_url, config):
        """
        Connect to Coinbase WebSocket.
        
        Args:
            ws_url: WebSocket URL
            config: Exchange configuration
        """
        # Get market symbols for subscription
        markets = config.get("markets", [])
        
        async with websockets.connect(ws_url) as websocket:
            self.connections["coinbase"] = websocket
            
            # Subscribe to ticker channel
            subscribe_msg = {
                "type": "subscribe",
                "channels": ["ticker"],
                "product_ids": markets
            }
            
            await websocket.send(json.dumps(subscribe_msg))
            
            # Publish connection status
            if self.event_bus:
                self.event_bus.publish_sync("market.connection.status", {
                    "exchange": "coinbase",
                    "status": "connected",
                    "subscriptions": markets,
                    "timestamp": datetime.now().isoformat()
                })
            
            while self.is_streaming:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Process the data
                    await self.process_coinbase_data(data)
                    
                except (websockets.exceptions.ConnectionClosed, json.JSONDecodeError) as e:
                    logger.error(f"Coinbase connection error: {str(e)}")
                    break
    
    async def process_binance_data(self, data):
        """
        Process data from Binance WebSocket.
        
        Args:
            data: Data from WebSocket
        """
        try:
            # Extract stream data
            stream = data.get("stream", "")
            stream_data = data.get("data", {})
            
            if not stream or not stream_data:
                return
            
            # Parse stream name to get symbol
            parts = stream.split("@")
            if len(parts) != 2 or parts[1] != "ticker":
                return
                
            symbol = parts[0].upper()
            
            # Convert to standard format
            base_quote = self.split_symbol_to_base_quote(symbol)
            market = f"{base_quote[0]}/{base_quote[1]}"
            exchange = "binance"
            market_key = f"{exchange}:{market}"
            
            # Skip if not subscribed
            if market_key not in self.subscriptions:
                return
            
            # Normalize data
            normalized_data = {
                "exchange": exchange,
                "market": market,
                "price": float(stream_data.get("c", 0)),
                "bid": float(stream_data.get("b", 0)),
                "ask": float(stream_data.get("a", 0)),
                "volume_24h": float(stream_data.get("v", 0)),
                "timestamp": datetime.now().isoformat(),
                "change_24h": float(stream_data.get("p", 0)),
                "change_percent_24h": float(stream_data.get("P", 0)),
                "high_24h": float(stream_data.get("h", 0)),
                "low_24h": float(stream_data.get("l", 0))
            }
            
            # Update market data
            self.market_data[market_key] = normalized_data
            self.last_updated[market_key] = time.time()
            
            # Store historical data if caching is enabled
            if self.cache_enabled:
                self.store_historical_data(market_key, normalized_data)
            
            # Publish market update
            if self.event_bus:
                self.event_bus.publish_sync("market.data.update", {
                    "exchange": exchange,
                    "market": market,
                    "data": normalized_data
                })
            
        except Exception as e:
            logger.error(f"Error processing Binance data: {str(e)}")
    
    async def process_coinbase_data(self, data):
        """
        Process data from Coinbase WebSocket.
        
        Args:
            data: Data from WebSocket
        """
        try:
            # Check if it's a ticker message
            if data.get("type") != "ticker":
                return
            
            # Extract market data
            product_id = data.get("product_id", "")
            if not product_id:
                return
            
            # Convert to standard format
            base_quote = product_id.split("-")
            if len(base_quote) != 2:
                return
                
            market = f"{base_quote[0]}/{base_quote[1]}"
            exchange = "coinbase"
            market_key = f"{exchange}:{market}"
            
            # Skip if not subscribed
            if market_key not in self.subscriptions:
                return
            
            # Extract price and other fields
            price = data.get("price")
            if not price:
                return
                
            # Normalize data
            normalized_data = {
                "exchange": exchange,
                "market": market,
                "price": float(price),
                "bid": float(data.get("best_bid", 0)),
                "ask": float(data.get("best_ask", 0)),
                "volume_24h": float(data.get("volume_24h", 0)),
                "timestamp": data.get("time", datetime.now().isoformat()),
                "high_24h": float(data.get("high_24h", 0)),
                "low_24h": float(data.get("low_24h", 0)),
                "change_24h": 0,  # Not provided directly
                "change_percent_24h": float(data.get("price_change_percent_24h", 0))
            }
            
            # Update market data
            self.market_data[market_key] = normalized_data
            self.last_updated[market_key] = time.time()
            
            # Store historical data if caching is enabled
            if self.cache_enabled:
                self.store_historical_data(market_key, normalized_data)
            
            # Publish market update
            if self.event_bus:
                self.event_bus.publish_sync("market.data.update", {
                    "exchange": exchange,
                    "market": market,
                    "data": normalized_data
                })
            
        except Exception as e:
            logger.error(f"Error processing Coinbase data: {str(e)}")
    
    def split_symbol_to_base_quote(self, symbol):
        """
        Split a combined symbol into base and quote currencies.
        
        Args:
            symbol: Combined symbol (e.g., BTCUSDT)
            
        Returns:
            tuple: Base and quote currencies (e.g., (BTC, USDT))
        """
        # Common quote currencies
        quote_currencies = ["USDT", "BUSD", "USDC", "USD", "BTC", "ETH", "BNB"]
        
        for quote in quote_currencies:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return (base, quote)
        
        # Default fallback - guess the split at 3 or 4 characters from the end
        if len(symbol) > 6:
            base = symbol[:-4]
            quote = symbol[-4:]
        else:
            base = symbol[:-3]
            quote = symbol[-3:]
            
        return (base, quote)
    
    def store_historical_data(self, market_key, data):
        """
        Store historical market data.
        
        Args:
            market_key: Market identifier
            data: Market data
        """
        if market_key not in self.historical_data:
            self.historical_data[market_key] = []
            
        # Add data to history
        self.historical_data[market_key].append(data)
        
        # Limit history size based on cache duration
        cutoff_time = (datetime.now() - timedelta(seconds=self.cache_duration)).isoformat()
        self.historical_data[market_key] = [
            entry for entry in self.historical_data[market_key]
            if entry.get("timestamp", "0") >= cutoff_time
        ]
    
    async def subscribe_to_market(self, exchange, market):
        """
        Subscribe to a market.
        
        Args:
            exchange: Exchange name
            market: Market symbol
            
        Returns:
            bool: Success status
        """
        market_key = f"{exchange}:{market}"
        
        # Check if already subscribed
        if market_key in self.subscriptions:
            logger.info(f"Already subscribed to {market_key}")
            return True
        
        # Check if exchange is configured
        if exchange not in self.exchanges:
            logger.error(f"Exchange {exchange} is not configured")
            return False
        
        # Add to subscriptions
        self.subscriptions.add(market_key)
        
        # Add to exchange config if not present
        if market not in self.exchanges[exchange].get("markets", []):
            self.exchanges[exchange].setdefault("markets", []).append(market)
        
        # If already streaming, need to reconnect to apply new subscription
        if self.is_streaming and exchange in self.connection_tasks:
            # Cancel existing connection
            self.connection_tasks[exchange].cancel()
            try:
                await self.connection_tasks[exchange]
            except asyncio.CancelledError:
                pass
            
            # Create new connection with updated subscriptions
            self.connection_tasks[exchange] = asyncio.create_task(
                self.connect_to_exchange(exchange, self.exchanges[exchange])
            )
        
        logger.info(f"Subscribed to {market_key}")
        return True
    
    async def unsubscribe_from_market(self, exchange, market):
        """
        Unsubscribe from a market.
        
        Args:
            exchange: Exchange name
            market: Market symbol
            
        Returns:
            bool: Success status
        """
        market_key = f"{exchange}:{market}"
        
        # Check if subscribed
        if market_key not in self.subscriptions:
            logger.info(f"Not subscribed to {market_key}")
            return True
        
        # Remove from subscriptions
        self.subscriptions.remove(market_key)
        
        # Remove from exchange config
        if exchange in self.exchanges and market in self.exchanges[exchange].get("markets", []):
            self.exchanges[exchange]["markets"].remove(market)
        
        # If already streaming, need to reconnect to apply removed subscription
        if self.is_streaming and exchange in self.connection_tasks:
            # Cancel existing connection
            self.connection_tasks[exchange].cancel()
            try:
                await self.connection_tasks[exchange]
            except asyncio.CancelledError:
                pass
            
            # Create new connection with updated subscriptions
            self.connection_tasks[exchange] = asyncio.create_task(
                self.connect_to_exchange(exchange, self.exchanges[exchange])
            )
        
        logger.info(f"Unsubscribed from {market_key}")
        return True
    
    async def get_market_data(self, exchange=None, market=None):
        """
        Get current market data.
        
        Args:
            exchange: Optional exchange filter
            market: Optional market filter
            
        Returns:
            dict: Market data
        """
        if exchange and market:
            # Return specific market data
            market_key = f"{exchange}:{market}"
            return {market_key: self.market_data.get(market_key)}
        elif exchange:
            # Return all markets for an exchange
            return {k: v for k, v in self.market_data.items() if k.startswith(f"{exchange}:")}
        elif market:
            # Return market data across all exchanges
            result = {}
            for key, data in self.market_data.items():
                _, market_name = key.split(":", 1)
                if market_name == market:
                    result[key] = data
            return result
        else:
            # Return all market data
            return self.market_data
    
    async def get_historical_data(self, exchange, market, limit=100):
        """
        Get historical market data.
        
        Args:
            exchange: Exchange name
            market: Market symbol
            limit: Maximum number of data points
            
        Returns:
            list: Historical market data
        """
        market_key = f"{exchange}:{market}"
        
        if market_key not in self.historical_data:
            return []
        
        # Return recent data points up to limit
        return self.historical_data[market_key][-limit:]
    
    async def on_streaming_start(self, _):
        """Handle streaming start event."""
        await self.start_streaming()
    
    async def on_streaming_stop(self, _):
        """Handle streaming stop event."""
        await self.stop_streaming()
    
    async def on_data_request(self, data):
        """
        Handle market data request event.
        
        Args:
            data: Request data
        """
        request_id = data.get("request_id")
        exchange = data.get("exchange")
        market = data.get("market")
        historical = data.get("historical", False)
        limit = data.get("limit", 100)
        
        if historical:
            # Historical data request
            if exchange and market:
                result = await self.get_historical_data(exchange, market, limit)
            else:
                result = {"error": "Both exchange and market must be specified for historical data"}
        else:
            # Current data request
            result = await self.get_market_data(exchange, market)
        
        # Publish response
        if self.event_bus:
            self.event_bus.publish_sync("market.data.response", {
                "request_id": request_id,
                "data": result,
                "timestamp": datetime.now().isoformat()
            })
    
    async def on_subscription_add(self, data):
        """
        Handle subscription add event.
        
        Args:
            data: Subscription data
        """
        request_id = data.get("request_id")
        exchange = data.get("exchange")
        market = data.get("market")
        
        if not exchange or not market:
            logger.error("Subscription add request missing exchange or market")
            result = {"success": False, "error": "Missing exchange or market"}
        else:
            success = await self.subscribe_to_market(exchange, market)
            result = {"success": success, "exchange": exchange, "market": market}
            
        # Publish response
        if self.event_bus:
            self.event_bus.publish_sync("market.subscription.add.result", {
                "request_id": request_id,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
    
    async def on_subscription_remove(self, data):
        """
        Handle subscription remove event.
        
        Args:
            data: Subscription data
        """
        request_id = data.get("request_id")
        exchange = data.get("exchange")
        market = data.get("market")
        
        if not exchange or not market:
            logger.error("Subscription remove request missing exchange or market")
            result = {"success": False, "error": "Missing exchange or market"}
        else:
            success = await self.unsubscribe_from_market(exchange, market)
            result = {"success": success, "exchange": exchange, "market": market}
            
        # Publish response
        if self.event_bus:
            self.event_bus.publish_sync("market.subscription.remove.result", {
                "request_id": request_id,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })

    def on_api_keys_reloaded_sync(self, data):
        """Sync bridge for API-key reload events -> async refresh logic."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.on_api_keys_reloaded(data))
            else:
                loop.run_until_complete(self.on_api_keys_reloaded(data))
        except Exception as e:
            logger.warning("API key reload sync bridge failed: %s", e)

    async def on_api_keys_reloaded(self, data):
        """React to API key changes and propagate updates across market streaming.

        This keeps MarketDataStreaming in sync with APIKeyManager updates
        immediately (same event family used by TradingComponent).
        """
        try:
            payload = data if isinstance(data, dict) else {}
            source = str(payload.get("source") or "unknown")

            # Immediate re-resolve for Massive/Polygon key and clear temporary
            # suspension so fixed credentials take effect right away.
            self.polygon_api_key = self._resolve_polygon_api_key()
            self.finnhub_api_key = self._resolve_finnhub_api_key() or self.finnhub_api_key
            self._polygon_disabled_until = 0.0

            # Reset transient exchange error/suspension state after key updates.
            self._exchange_suspend_until.clear()
            self._symbol_resolution_cache.clear()

            # Rebuild exchange map + executor from latest APIKeyManager state.
            refreshed_exchanges = self._build_exchanges_from_api_keys()
            if isinstance(refreshed_exchanges, dict) and refreshed_exchanges:
                self.exchanges = refreshed_exchanges

            logger.info(
                "MarketDataStreaming refreshed from API key update (source=%s, hot_reload_applied=%s, polygon_key_present=%s)",
                source,
                True,
                bool(self.polygon_api_key),
            )
            if self.event_bus:
                self.event_bus.publish_sync(
                    "market.api_keys.reloaded.result",
                    {
                        "source": source,
                        "hot_reload_applied": True,
                        "streaming_restarted": False,
                        "polygon_key_present": bool(self.polygon_api_key),
                        "timestamp": datetime.now().isoformat(),
                    },
                )
        except Exception as e:
            logger.error("Failed to refresh MarketDataStreaming after API key update: %s", e)
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the MarketDataStreaming component."""
        logger.info("Shutting down MarketDataStreaming component")
        
        # Stop streaming
        if self.is_streaming:
            await self.stop_streaming()
        
        # Save data
        await self.save_market_data()
        
        logger.info("MarketDataStreaming component shut down successfully")
