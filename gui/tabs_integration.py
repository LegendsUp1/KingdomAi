#!/usr/bin/env python3
"""
Kingdom AI - Tabs Integration

This module integrates all tabs into the Kingdom AI system and ensures
proper event bus connections, initialization, and functionality.
"""

import tkinter as tk
from tkinter import ttk
import logging
import asyncio
from typing import Dict, Any, Optional, List

# Import frames
from gui.frames.vr_frame import VRFrame
from gui.frames.code_generator_frame import CodeGeneratorFrame
from gui.frames.thoth_frame import ThothFrame

# Import tab manager
from gui.tab_manager import TabManager

logger = logging.getLogger("KingdomAI.TabsIntegration")

class TabsIntegration:
    """Class to integrate all tabs into the Kingdom AI system."""
    
    def __init__(self, notebook, event_bus, api_key_connector=None):
        """Initialize tabs integration.
        
        Args:
            notebook: The notebook widget to add tabs to
            event_bus: The event bus for communication
            api_key_connector: Connector for accessing API keys
        """
        self.notebook = notebook
        self.event_bus = event_bus
        self.api_key_connector = api_key_connector
        self.tab_manager = TabManager(notebook, event_bus)
        
        # Dictionary to store initialization status
        self.initialized_tabs = {}
        
    async def initialize_tabs(self):
        """Initialize all tabs and add them to the notebook."""
        logger.info("Initializing tabs")
        
        # Register all tabs with the tab manager
        self._register_tabs()
        
        # Ensure proper event connections
        self.tab_manager.ensure_tab_event_connections()
        
        # Select dashboard tab by default
        self.tab_manager.select_tab("Dashboard")
        
        # Subscribe to events for tab management
        await self._subscribe_to_events()
        
        logger.info("Tabs initialization complete")
        
    def _register_tabs(self):
        """Register all tabs with the tab manager."""
        try:
            # Register VR System tab
            self.tab_manager.register_tab(
                "VR System", 
                VRFrame, 
                event_bus=self.event_bus, 
                tab_title="VR System"
            )
            self.initialized_tabs["VR System"] = True
            logger.info("Registered VR System tab")
            
            # Register Code Generator tab
            self.tab_manager.register_tab(
                "Code Generator", 
                CodeGeneratorFrame, 
                event_bus=self.event_bus, 
                tab_title="Code Generator"
            )
            self.initialized_tabs["Code Generator"] = True
            logger.info("Registered Code Generator tab")
            
            # Register ThothAI tab
            self.tab_manager.register_tab(
                "ThothAI", 
                ThothFrame, 
                event_bus=self.event_bus, 
                tab_title="ThothAI"
            )
            self.initialized_tabs["ThothAI"] = True
            logger.info("Registered ThothAI tab")
            
        except Exception as e:
            logger.error(f"Error registering tabs: {e}")
            raise
            
    async def _subscribe_to_events(self):
        """Subscribe to events for tab management."""
        if self.event_bus:
            # Subscribe to component status events to update tabs
            self.event_bus.subscribe("component.status", self._handle_component_status)
            
            # Subscribe to tab management events
            self.event_bus.subscribe("tab.select", self._handle_tab_select)
            self.event_bus.subscribe("tab.update", self._handle_tab_update)
            
            # Subscribe to system events
            self.event_bus.subscribe("system.shutdown", self._handle_system_shutdown)
            
            logger.info("Subscribed to tab management events")
        else:
            logger.warning("No event bus available for tab management")
            
    def _handle_component_status(self, event_type, data):
        """Handle component status events.
        
        Args:
            event_type: The type of event
            data: The event data with component status
        """
        component_name = data.get("component", "")
        status = data.get("status", "unknown")
        
        logger.debug(f"Component status update: {component_name} -> {status}")
        
        # Update tabs that depend on this component
        self.tab_manager.update_tab_status(component_name, status)
        
    def _handle_tab_select(self, event_type, data):
        """Handle tab selection events.
        
        Args:
            event_type: The type of event
            data: The event data with tab ID
        """
        tab_id = data.get("tab_id", "")
        
        if tab_id:
            logger.debug(f"Selecting tab: {tab_id}")
            self.tab_manager.select_tab(tab_id)
        
    def _handle_tab_update(self, event_type, data):
        """Handle tab update events.
        
        Args:
            event_type: The type of event
            data: The event data with update info
        """
        tab_id = data.get("tab_id", "")
        update_type = data.get("update_type", "")
        update_data = data.get("data", {})
        
        if tab_id and update_type:
            logger.debug(f"Updating tab {tab_id} with {update_type}")
            self.tab_manager._update_tab(tab_id, update_type, update_data)
        elif update_type:
            logger.debug(f"Updating all tabs with {update_type}")
            self.tab_manager.update_all_tabs(update_type, update_data)
        
    def _handle_system_shutdown(self, event_type, data):
        """Handle system shutdown events.
        
        Args:
            event_type: The type of event
            data: The event data
        """
        logger.info("System shutdown event received, cleaning up tabs")
        
        # Clean up any resources held by tabs
        for tab_id in self.initialized_tabs:
            tab = self.tab_manager.get_tab(tab_id)
            if tab and hasattr(tab, "cleanup"):
                try:
                    tab.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up tab {tab_id}: {e}")

def initialize_kingdom_tabs(notebook, event_bus, api_key_connector=None):
    """Initialize all Kingdom AI tabs.
    
    Args:
        notebook: The notebook widget to add tabs to
        event_bus: The event bus for communication
        api_key_connector: Connector for accessing API keys
        
    Returns:
        TabsIntegration instance
    """
    tabs_integration = TabsIntegration(notebook, event_bus, api_key_connector)
    asyncio.create_task(tabs_integration.initialize_tabs())
    return tabs_integration
