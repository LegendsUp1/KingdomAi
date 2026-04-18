"""Market API module for Kingdom AI."""
from typing import Any, Dict, Optional
from core.base_component import BaseComponent
from core.event_bus import EventBus

class MarketAPI(BaseComponent):
    """Market API for cryptocurrency trading."""
    
    def __init__(self, event_bus: EventBus) -> None:
        """Initialize Market API.
        
        Args:
            event_bus: Event bus instance
        """
        super().__init__("MarketAPI", event_bus)
        self.api_key = None
        self.websockets = {}
        self._initialized = False
        self.logger = logging.getLogger("KingdomAI.MarketAPI")
        
    @property
    def initialized(self) -> bool:
        """Get initialization status."""
        return self._initialized
    
    @initialized.setter
    def initialized(self, value: bool) -> None:
        """Set initialization status."""
        self._initialized = value
        
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize market connections.
        
        Args:
            event_bus: Optional EventBus instance to use for initialization
            config: Optional configuration to use for initialization
            
        Returns:
            bool: Success status
        """
        # Call the parent initialize method first
        await super().initialize(event_bus, config)
        
        try:
            await self._load_api_keys()
            await self._init_websockets()
            self.initialized = True
            if self.event_bus:
                await self.event_bus.publish("market.status", {
                    "status": "initialized"
                })
            return True
        except Exception as e:
            if self.event_bus:
                await self.event_bus.publish("market.error", {
                    "error": str(e),
                    "source": "MarketAPI.initialize"
                })
            return False
            
    async def _load_api_keys(self) -> None:
        """Load API keys from secure storage via event_bus."""
        try:
            if self.event_bus:
                # Try to get API keys from API key manager via event_bus
                api_manager = self.event_bus.get_component("api_key_manager")
                if api_manager and hasattr(api_manager, "get_api_keys"):
                    keys = api_manager.get_api_keys("market_api")
                    if keys:
                        self.api_key = keys.get("api_key")
                        self.logger.info("Loaded API keys from API key manager")
                        return
                
                # Try to get from config via event_bus
                config_component = self.event_bus.get_component("config")
                if config_component:
                    market_config = config_component.get("market", {})
                    self.api_key = market_config.get("api_key")
                    if self.api_key:
                        self.logger.info("Loaded API keys from config")
                        return
        except Exception as e:
            self.logger.debug(f"Could not load API keys from event_bus: {e}")
        
        # Fallback: load from environment
        import os
        self.api_key = os.getenv("MARKET_API_KEY")
        if self.api_key:
            self.logger.info("Loaded API keys from environment")
        else:
            self.logger.warning("No API keys available - market data may be limited")
        
    async def _init_websockets(self) -> None:
        """Initialize WebSocket connections for real-time market data."""
        try:
            if self.event_bus:
                # Try to get WebSocket manager from event_bus
                ws_manager = self.event_bus.get_component("websocket_manager")
                if ws_manager and hasattr(ws_manager, "create_connection"):
                    # Create WebSocket connection for market data
                    self.websockets["market_data"] = await ws_manager.create_connection(
                        "wss://stream.binance.com:9443/ws/btcusdt@ticker"
                    )
                    self.logger.info("Initialized WebSocket connection via event_bus")
                    return
        except Exception as e:
            self.logger.debug(f"Could not initialize WebSocket via event_bus: {e}")
        
        # Fallback: initialize WebSocket directly if needed
        self.logger.info("WebSocket initialization deferred - will connect when market data subscription is requested")
        
    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get market data for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Market data if successful, None otherwise
        """
        try:
            if not self.initialized:
                await self.initialize()
            
            # Get real market data from event_bus or API
            data = None
            try:
                if self.event_bus:
                    # Try to get market data from market API component
                    market_api = self.event_bus.get_component("market_api")
                    if market_api and hasattr(market_api, "get_ticker"):
                        ticker = await market_api.get_ticker(symbol) if asyncio.iscoroutinefunction(market_api.get_ticker) else market_api.get_ticker(symbol)
                        if ticker:
                            data = {
                                "price": float(ticker.get("price", 0.0)),
                                "volume": float(ticker.get("volume", 0.0)),
                                "bid": float(ticker.get("bid", 0.0)),
                                "ask": float(ticker.get("ask", 0.0)),
                                "high": float(ticker.get("high", 0.0)),
                                "low": float(ticker.get("low", 0.0))
                            }
                
                # Fallback: request market data via event_bus
                if not data and self.event_bus:
                    await self.event_bus.publish("market.data.request", {"symbol": symbol})
                    # Wait briefly for response (in real implementation, would use proper async response handling)
                    await asyncio.sleep(0.1)
                
                # If still no data, return honest "no data available"
                if not data:
                    data = {"price": 0.0, "volume": 0.0, "error": "Market data not available"}
                    self.logger.warning(f"Market data not available for {symbol}")
            except Exception as e:
                self.logger.error(f"Error getting market data for {symbol}: {e}")
                data = {"price": 0.0, "volume": 0.0, "error": str(e)}
            
            if self.event_bus:
                await self.event_bus.publish("market.data", {
                    "symbol": symbol,
                    "data": data
                })
            return data
            
        except Exception as e:
            if self.event_bus:
                await self.event_bus.publish("market.error", {
                    "error": str(e),
                    "source": "MarketAPI.get_market_data",
                    "symbol": symbol
                })
            return None
            
    async def cleanup(self) -> bool:
        """Clean up resources.
        
        Returns:
            bool: Success status
        """
        try:
            # Close WebSocket connections
            for ws in self.websockets.values():
                if ws:
                    try:
                        if hasattr(ws, 'close'):
                            await ws.close()
                    except Exception as ws_error:
                        self.logger.warning(f"Error closing websocket: {ws_error}")
            
            # Clear all resources
            self.initialized = False
            if self.event_bus:
                await self.event_bus.publish("market.status", {
                    "status": "shutdown"
                })
            return True
        except Exception as e:
            if self.event_bus:
                await self.event_bus.publish("market.error", {
                    "error": str(e),
                    "source": "MarketAPI.cleanup"
                })
            return False
