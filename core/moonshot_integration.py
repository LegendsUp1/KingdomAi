#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MoonshotIntegration component for integrating with Moonshot strategies and analysis.
"""

import os
import asyncio
import logging
from datetime import datetime
import aiohttp

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class MoonshotIntegration(BaseComponent):
    """
    Component for integrating with the Moonshot platform for advanced trading strategies and analysis.
    Connects to Moonshot API for signals and strategy implementation.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the MoonshotIntegration component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "MoonshotIntegration"
        self.description = "Integrates with Moonshot for advanced trading strategies"
        self.api_key = self.config.get("moonshot_api_key", os.environ.get("MOONSHOT_API_KEY", ""))
        self.api_url = self.config.get("moonshot_api_url", "https://api.moonshot.com/v1")
        self.session = None
        self.strategies = {}
        self.active_signals = []
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
    async def initialize(self):
        """Initialize the MoonshotIntegration component and connect to the API."""
        logger.info("Initializing MoonshotIntegration component")
        
        # Subscribe to relevant events
        self.event_bus and self.event_bus.subscribe_sync("market.data.update", self.on_market_data_update)
        self.event_bus and self.event_bus.subscribe_sync("trading.strategy.request", self.on_strategy_request)
        self.event_bus and self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        
        # Create HTTP session
        self.session = aiohttp.ClientSession()
        
        # Attempt to connect to the Moonshot API
        await self.connect_to_api()
        
        # Load available strategies
        await self.load_strategies()
        
        logger.info(f"MoonshotIntegration initialized. Connected: {self.is_connected}")
        
    async def connect_to_api(self):
        """Establish connection to the Moonshot API."""
        if not self.api_key:
            logger.warning("Moonshot API key not found. Operating in limited mode.")
            self.is_connected = False
            return
            
        try:
            async with self.session.get(
                f"{self.api_url}/status",
                headers={"Authorization": f"Bearer {self.api_key}"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.is_connected = data.get("status") == "operational"
                    logger.info(f"Connected to Moonshot API. Status: {data.get('status')}")
                    
                    # Reset reconnect attempts on successful connection
                    self.reconnect_attempts = 0
                else:
                    logger.error(f"Failed to connect to Moonshot API. Status: {response.status}")
                    self.is_connected = False
        except Exception as e:
            logger.error(f"Error connecting to Moonshot API: {str(e)}")
            self.is_connected = False
            
            # Attempt reconnection if max attempts not reached
            if self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                logger.info(f"Attempting to reconnect to Moonshot API. Attempt {self.reconnect_attempts}")
                await asyncio.sleep(5)  # Wait before retrying
                await self.connect_to_api()
            
    async def load_strategies(self):
        """Load available strategies from Moonshot API."""
        if not self.is_connected:
            logger.warning("Cannot load strategies: Not connected to Moonshot API")
            return
            
        try:
            async with self.session.get(
                f"{self.api_url}/strategies",
                headers={"Authorization": f"Bearer {self.api_key}"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.strategies = {strategy["id"]: strategy for strategy in data.get("strategies", [])}
                    logger.info(f"Loaded {len(self.strategies)} strategies from Moonshot")
                    
                    # Publish available strategies to the event bus
                    self.event_bus.publish("moonshot.strategies.loaded", {
                        "count": len(self.strategies),
                        "strategies": list(self.strategies.values())
                    })
                else:
                    logger.error(f"Failed to load strategies. Status: {response.status}")
        except Exception as e:
            logger.error(f"Error loading strategies: {str(e)}")
    
    async def get_signal(self, strategy_id, market_data):
        """
        Get trading signal from a specific strategy.
        
        Args:
            strategy_id: ID of the strategy to use
            market_data: Market data to analyze
            
        Returns:
            dict: Trading signal with recommendation and confidence
        """
        if not self.is_connected:
            logger.warning("Cannot get signal: Not connected to Moonshot API")
            return {"recommendation": "hold", "confidence": 0, "error": "Not connected"}
            
        if strategy_id not in self.strategies:
            logger.warning(f"Strategy {strategy_id} not found")
            return {"recommendation": "hold", "confidence": 0, "error": "Strategy not found"}
            
        try:
            async with self.session.post(
                f"{self.api_url}/signals",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "strategy_id": strategy_id,
                    "market_data": market_data
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    signal = data.get("signal", {})
                    
                    # Add signal to active signals
                    signal["timestamp"] = datetime.now().isoformat()
                    signal["strategy_id"] = strategy_id
                    self.active_signals.append(signal)
                    
                    # Publish signal to event bus
                    self.event_bus.publish("moonshot.signal.received", signal)
                    
                    return signal
                else:
                    error_data = await response.json()
                    logger.error(f"Failed to get signal. Status: {response.status}, Error: {error_data}")
                    return {"recommendation": "hold", "confidence": 0, "error": error_data.get("message", "API error")}
        except Exception as e:
            logger.error(f"Error getting signal: {str(e)}")
            return {"recommendation": "hold", "confidence": 0, "error": str(e)}
    
    async def on_market_data_update(self, data):
        """
        Handle market data updates.
        
        Args:
            data: Market data update
        """
        if not self.is_connected:
            return
            
        # Check if we need to generate signals based on market data
        if data.get("request_signals", False):
            for strategy_id in data.get("strategies", []):
                if strategy_id in self.strategies:
                    await self.get_signal(strategy_id, data.get("market_data", {}))
    
    async def on_strategy_request(self, data):
        """
        Handle strategy request events.
        
        Args:
            data: Strategy request data
        """
        strategy_id = data.get("strategy_id")
        market_data = data.get("market_data", {})
        
        if not strategy_id:
            logger.warning("Strategy request missing strategy_id")
            return
            
        signal = await self.get_signal(strategy_id, market_data)
        
        # Publish response to the event bus
        self.event_bus.publish("moonshot.strategy.response", {
            "request_id": data.get("request_id"),
            "strategy_id": strategy_id,
            "signal": signal
        })
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the MoonshotIntegration component."""
        logger.info("Shutting down MoonshotIntegration component")
        
        # Close HTTP session
        if self.session:
            await self.session.close()
            
        # Clear data
        self.strategies = {}
        self.active_signals = []
        self.is_connected = False
        
        logger.info("MoonshotIntegration component shut down successfully")
