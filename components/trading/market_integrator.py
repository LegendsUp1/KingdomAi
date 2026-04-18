#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Market Integrator Module

This module connects the trading system with our multi-market components,
ensuring all asset classes and exchanges are properly supported.
"""

import os
import sys
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Union
import json

# Import core modules
from core.base_component import BaseComponent
from core.market_definitions import (
    AssetClass, MarketType, ExchangeType, OrderType,
    MarketRegistry, EXCHANGE_CAPABILITIES
)
from core.redis_quantum_manager import RedisQuantumNexus
from components.trading.exchange_connector import ExchangeConnector
from components.trading.trading_system import TradingSystem

class MarketIntegrator(BaseComponent):
    """
    Market Integrator for Kingdom AI Trading System.
    
    This component connects the trading system with all supported markets,
    enabling trading across stocks, bonds, forex, commodities, derivatives,
    cryptocurrencies, and all other tradable assets.
    
    It enforces strict Redis Quantum Nexus connection on port 6380 with
    password 'QuantumNexus2025', with no fallback allowed.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the market integrator."""
        super().__init__(event_bus=event_bus)
        
        # Initialize logger
        self.logger = logging.getLogger(f"KingdomAI.{self.__class__.__name__}")
        
        # Configuration parameters
        self.config = config or {}
        
        # Component status
        self.component_name = "market_integrator"
        self.status = "initializing"
        
        # Initialize core components
        self.redis_nexus = None
        self.market_registry = None
        self.exchange_connector = None
        self.trading_system = None
        
        # Track enabled asset classes and market types
        self.enabled_asset_classes = []
        self.enabled_market_types = []
        self.enabled_exchanges = []
        
        # Connection statuses
        self.redis_connected = False
        self.blockchain_connected = False
        self.websocket_connected = False
        self.api_key_manager_connected = False
        
        # Manager connection details by asset class
        self.connection_status = {
            asset_class.name: {
                'websocket': False,
                'blockchain': False,
                'api_key': False,
                'last_verified': None,
                'details': {}
            } for asset_class in AssetClass
        }
        
        self.logger.info("Market Integrator initialized")
    
    async def initialize(self, event_bus=None, config=None):
        """
        Initialize the Market Integrator component.
        
        Sets up Redis Quantum Nexus, market registry, and exchange connector.
        """
        if event_bus:
            self.event_bus = event_bus
        
        if config:
            self.config = config
        
        self.logger.info("Initializing Market Integrator...")
        
        # Initialize Redis Quantum Nexus with strict connection requirements
        self.redis_nexus = RedisQuantumNexus()
        connected = await self.redis_nexus.connect()
        
        # Enforce no fallback - system must halt if Redis connection fails
        if not connected:
            self.logger.critical("Redis Quantum Nexus connection failed. System halting as per requirement.")
            sys.exit(1)
        
        self.redis_connected = True
        self.logger.info("Redis Quantum Nexus connected successfully on port 6380")
        
        # Verify all manager connections
        await self.verify_all_connections()
        
        # Initialize market registry
        self.market_registry = MarketRegistry()
        await self._load_market_registry()
        
        # Initialize exchange connector
        self.exchange_connector = ExchangeConnector(
            event_bus=self.event_bus,
            redis_nexus=self.redis_nexus,
            market_registry=self.market_registry
        )
        await self.exchange_connector.initialize()
        
        # Connect to trading system
        self.trading_system = TradingSystem(event_bus=self.event_bus)
        
        # Set up event subscriptions
        self._setup_event_subscriptions()
        
        self.status = "ready"
        self.logger.info("Market Integrator initialized successfully")
        
        # Publish integration status
        await self._publish_integration_status()
        
        return True
    
    async def _load_market_registry(self):
        """Load market registry with all supported asset classes and exchanges."""
        # Enable all asset classes
        self.enabled_asset_classes = [asset_class for asset_class in AssetClass]
        self.enabled_market_types = [market_type for market_type in MarketType]
        self.enabled_exchanges = [exchange_type for exchange_type in ExchangeType]
        
        # Register all supported exchanges and market pairs
        for exchange_type in self.enabled_exchanges:
            exchange_info = EXCHANGE_CAPABILITIES.get(exchange_type, {})
            supported_assets = exchange_info.get("supported_assets", [])
            for asset_class in supported_assets:
                # Register exchange support for this asset class
                self.market_registry.register_exchange_for_asset(exchange_type, asset_class)
        
        self.logger.info(f"Market registry loaded with {len(self.enabled_exchanges)} exchanges " +
                        f"across {len(self.enabled_asset_classes)} asset classes")
    
    def _setup_event_subscriptions(self):
        """Set up subscriptions to relevant events on the event bus."""
        if not self.event_bus:
            self.logger.warning("No event bus available. Event subscriptions skipped.")
            return
        
        # Subscribe to market data events
        self.event_bus.subscribe("market_data_update", self._handle_market_data)
        
        # Subscribe to blockchain events
        self.event_bus.subscribe("blockchain_connection_status", self._handle_blockchain_status)
        
        # Subscribe to websocket events
        self.event_bus.subscribe("websocket_connection_status", self._handle_websocket_status)
        
        # Subscribe to API key manager events
        self.event_bus.subscribe("api_key_status", self._handle_api_key_status)
        
        # Subscribe to system events
        self.event_bus.subscribe("system_shutdown", self._handle_system_shutdown)
        
        self.logger.info("Event subscriptions set up")
    
    async def _handle_market_data(self, event_data):
        """Handle incoming market data events."""
        symbol = event_data.get("symbol")
        market_type = event_data.get("market_type")
        asset_class = event_data.get("asset_class")
        
        if not all([symbol, market_type, asset_class]):
            self.logger.warning(f"Incomplete market data received: {event_data}")
            return
        
        # Convert string values to enum types if needed
        if isinstance(market_type, str):
            market_type = MarketType[market_type]
        if isinstance(asset_class, str):
            asset_class = AssetClass[asset_class]
        
        # Store market data in Redis Quantum Nexus
        await self.redis_nexus.store_market_data(symbol, event_data)
        
        # Notify trading system of the update
        await self.trading_system.update_market_data(symbol, event_data)
    
    async def _handle_blockchain_status(self, event_data):
        """Handle blockchain connection status events."""
        status = event_data.get("status")
        self.blockchain_connected = (status == "connected")
        
        # Enforce system halt if blockchain connection is required but failed
        if self.config.get("require_blockchain", True) and not self.blockchain_connected:
            self.logger.critical("Blockchain connection failed. System halting as per requirement.")
            sys.exit(1)
    
    async def _handle_websocket_status(self, event_data):
        """Handle websocket connection status events."""
        status = event_data.get("status")
        self.websocket_connected = (status == "connected")
    
    async def _handle_api_key_status(self, event_data):
        """Handle API key manager status events."""
        status = event_data.get("status")
        self.api_key_manager_connected = (status == "connected")
    
    async def _handle_system_shutdown(self, event_data):
        """Handle system shutdown events."""
        self.logger.info("System shutdown received, cleaning up resources")
        await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources before shutdown."""
        if self.redis_nexus:
            await self.redis_nexus.disconnect()
        
        if self.exchange_connector:
            await self.exchange_connector.cleanup()
    
    async def _publish_integration_status(self):
        """Publish integration status to the event bus."""
        if not self.event_bus:
            return
        
        status = {
            "component": "market_integrator",
            "status": self.status,
            "redis_connected": self.redis_connected,
            "blockchain_connected": self.blockchain_connected,
            "websocket_connected": self.websocket_connected,
            "api_key_manager_connected": self.api_key_manager_connected,
            "enabled_asset_classes": [ac.name for ac in self.enabled_asset_classes],
            "enabled_market_types": [mt.name for mt in self.enabled_market_types],
            "enabled_exchanges": [ex.name for ex in self.enabled_exchanges],
            "timestamp": time.time()
        }
        
        await self.event_bus.publish("integration_status", status)
    
    async def get_market_status(self):
        """
        Get status of all integrated markets and exchanges.
        
        Returns:
            dict: Status information for all markets and exchanges
        """
        status = {
            "asset_classes": {ac.name: {"enabled": True} for ac in self.enabled_asset_classes},
            "market_types": {mt.name: {"enabled": True} for mt in self.enabled_market_types},
            "exchanges": {}
        }
        
        # Get status for each exchange
        for exchange_type in self.enabled_exchanges:
            exchange_status = await self.exchange_connector.get_exchange_status(exchange_type)
            status["exchanges"][exchange_type.name] = exchange_status
        
        return status
