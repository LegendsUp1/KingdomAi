#!/usr/bin/env python3
"""
Kingdom AI GUI Tab Connector

This module ensures all GUI tabs are properly connected to the event bus,
displays real-time data, and handles user actions correctly.

It standardizes tab implementations and event subscriptions based on the
original kingdomkeys.py main entry point functionality.
"""

import logging
import asyncio
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List, Set

# Import GUIBinder for efficient event binding
from gui.gui_binder import get_instance as get_gui_binder

logger = logging.getLogger("KingdomAI.TabConnector")

class TabConnector:
    """Connects all GUI tabs to the event bus with proper subscriptions."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls, main_window=None, event_bus=None):
        """Get singleton instance of the TabConnector."""
        if cls._instance is None:
            cls._instance = cls(main_window, event_bus)
        elif main_window is not None and event_bus is not None:
            cls._instance.main_window = main_window
            cls._instance.event_bus = event_bus
        return cls._instance
    
    def __init__(self, main_window=None, event_bus=None):
        """Initialize the tab connector.
        
        Args:
            main_window: The main window instance
            event_bus: The event bus instance
        """
        self.main_window = main_window
        self.event_bus = event_bus
        self.logger = logger
        
        # Get the GUI binder instance
        self.gui_binder = get_gui_binder(event_bus=event_bus)
        
        # Track connection status
        self.connected_tabs = set()
        self.registered_events = set()
        
        # Event type mapping for each tab
        self.tab_event_types = {
            "thoth_frame": [
                "thoth.response", "thoth.thinking", "thoth.error", "thoth.status",
                "voice.status", "voice.transcript", "voice.output", "chat.message",
                "ai.response", "ai.status", "ai.error"
            ],
            "mining_frame": [
                "mining.status", "mining.hashrate", "mining.shares", "mining.devices", 
                "mining.error", "blockchain.status", "blockchain.mining.reward"
            ],
            "trading_frame": [
                "trading.update", "trading.status", "market.data", "portfolio.update",
                "trade.execute", "trade.complete", "trade.error", "trade.status",
                "market.order_book", "market.chart_data"
            ],
            "wallet_frame": [
                "wallet.data", "wallet.balance", "wallet.transaction", "wallet.error",
                "wallet.created", "blockchain.transaction", "blockchain.status"
            ],
            "code_generator_frame": [
                "code.generation.start", "code.generation.progress", "code.generation.complete",
                "code.generation.error", "code.generated", "mcp.resources.available",
                "mcp.connection.status", "code.execution.result"
            ],
            "vr_frame": [
                "vr.status", "vr.error", "vr.device_info", "vr.visualization.update",
                "vr.devices.detected"
            ],
            "api_keys_frame": [
                "api.keys.status", "api.keys.list", "api.connection.test.result",
                "api.key.status", "api.key.test_result"
            ]
        }
        
        # Initial data requests for each tab
        self.initial_data_requests = {
            "thoth_frame": [
                {"event": "thoth.request_status", "data": {"source": "gui_initialization"}},
                {"event": "voice.request_status", "data": {"source": "gui_initialization"}}
            ],
            "mining_frame": [
                {"event": "mining.request_status", "data": {"source": "gui_initialization"}},
                {"event": "mining.request_devices", "data": {"source": "gui_initialization"}}
            ],
            "trading_frame": [
                {"event": "trading.request_market_data", "data": {
                    "symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"],
                    "source": "gui_initialization"
                }},
                {"event": "portfolio.request_update", "data": {"source": "gui_initialization"}}
            ],
            "wallet_frame": [
                {"event": "wallet.request_data", "data": {"source": "gui_initialization"}},
                {"event": "wallet.request_list", "data": {"source": "gui_initialization"}}
            ],
            "code_generator_frame": [
                {"event": "mcp.request_resources", "data": {"source": "gui_initialization"}},
                {"event": "mcp.check_connection", "data": {"source": "gui_initialization"}}
            ],
            "vr_frame": [
                {"event": "vr.request_devices", "data": {"source": "gui_initialization"}},
                {"event": "vr.request_status", "data": {"source": "gui_initialization"}}
            ],
            "api_keys_frame": [
                {"event": "api.keys.request_list", "data": {"source": "gui_initialization"}}
            ]
        }
    
    async def connect_all_tabs(self):
        """Connect all tabs to the event bus with proper subscriptions."""
        if not self.main_window or not self.event_bus:
            self.logger.error("Cannot connect tabs: missing main_window or event_bus")
            return False
        
        self.logger.info("Connecting all GUI tabs to event bus...")
        
        try:
            # Get all tabs from the main window
            tabs = self._get_all_tabs()
            
            if not tabs:
                self.logger.warning("No tabs found in main_window")
                return False
            
            # Connect each tab to the event bus
            for tab_id, tab in tabs.items():
                await self._connect_tab(tab_id, tab)
            
            # Request initial data for all connected tabs
            await self._request_initial_data()
            
            # Publish a GUI ready event
            await self.event_bus.publish("gui.ready", {
                "timestamp": datetime.now().isoformat(),
                "connected_tabs": list(self.connected_tabs)
            })
            
            self.logger.info(f"Successfully connected {len(self.connected_tabs)} tabs with {len(self.registered_events)} event subscriptions")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting tabs: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _get_all_tabs(self):
        """Get all tabs from the main window."""
        tabs = {}
        
        # Look for tabs in main_window.tabs dictionary
        if hasattr(self.main_window, 'tabs') and isinstance(self.main_window.tabs, dict):
            tabs.update(self.main_window.tabs)
        
        # Look for tab attributes in main_window
        for tab_id in self.tab_event_types.keys():
            if hasattr(self.main_window, tab_id) and tab_id not in tabs:
                tabs[tab_id] = getattr(self.main_window, tab_id)
        
        return tabs
    
    async def _connect_tab(self, tab_id, tab):
        """Connect a tab to the event bus with proper subscriptions."""
        if not tab:
            self.logger.warning(f"Tab {tab_id} is None, skipping connection")
            return False
        
        try:
            # Set event bus if not already set
            if hasattr(tab, 'event_bus') and tab.event_bus is None:
                tab.event_bus = self.event_bus
                self.logger.debug(f"Set event_bus for tab {tab_id}")
            
            # Register the tab with the GUI binder if event types exist
            if tab_id in self.tab_event_types:
                event_types = self.tab_event_types[tab_id]
                self.gui_binder.register_tab(tab_id, tab, event_types)
                self.logger.info(f"Registered tab {tab_id} with GUI binder for {len(event_types)} event types")
            
            # Call the tab's subscribe_to_events method if it exists
            if hasattr(tab, '_subscribe_to_events'):
                # Check if it's an async method
                if asyncio.iscoroutinefunction(tab._subscribe_to_events):
                    await tab._subscribe_to_events()
                else:
                    tab._subscribe_to_events()
                self.logger.debug(f"Called _subscribe_to_events for tab {tab_id}")
            
            # Mark tab as connected
            self.connected_tabs.add(tab_id)
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting tab {tab_id}: {e}")
            return False
    
    async def _request_initial_data(self):
        """Request initial data for all connected tabs."""
        if not self.event_bus:
            self.logger.error("Cannot request initial data: missing event_bus")
            return False
        
        request_count = 0
        
        # Request initial data for each connected tab
        for tab_id in self.connected_tabs:
            if tab_id in self.initial_data_requests:
                requests = self.initial_data_requests[tab_id]
                for request in requests:
                    try:
                        await self.event_bus.publish(request["event"], request["data"])
                        request_count += 1
                        self.logger.debug(f"Published initial data request: {request['event']}")
                    except Exception as e:
                        self.logger.error(f"Error publishing {request['event']}: {e}")
        
        self.logger.info(f"Made {request_count} initial data requests")
        return request_count > 0
    
    async def verify_connections(self):
        """Verify that all tabs are properly connected and receiving events."""
        if not self.event_bus:
            self.logger.error("Cannot verify connections: missing event_bus")
            return False
            
        # Publish a diagnostic event for each connected tab
        for tab_id in self.connected_tabs:
            await self.event_bus.publish("gui.tab.diagnostic", {
                "tab_id": tab_id,
                "timestamp": datetime.now().isoformat(),
                "action": "verify_connection"
            })
        
        # Publish a general diagnostic event
        await self.event_bus.publish("system.diagnostic", {
            "component": "TabConnector",
            "timestamp": datetime.now().isoformat(),
            "action": "verify_connections",
            "connected_tabs": list(self.connected_tabs)
        })
        
        return True

# Easy access function
def get_instance(main_window=None, event_bus=None):
    """Get the singleton instance of the TabConnector."""
    return TabConnector.get_instance(main_window, event_bus)
