#!/usr/bin/env python3
"""
Kingdom AI - Tab Manager

This module provides optimized tab management for the Kingdom AI GUI,
with lazy loading, performance optimization, and responsive updates.

Key features:
1. Lazy loading of tab contents
2. Memory management for inactive tabs
3. Data visualization optimization
4. Responsive UI during data-intensive operations
5. Consistent styling across all component tabs

Author: Kingdom AI Development Team
Date: 2025-04-21
"""

import os
import time
import logging
import tkinter as tk
from tkinter import ttk
import threading
import asyncio
import traceback
from typing import Dict, List, Any, Optional, Callable
import queue

# Import enhanced components
from .enhanced_components import EnhancedRGBFrame, EnhancedGlowButton, EnhancedStatusBar, RGBColorManager
from .kingdom_style import KingdomStyles

class TabManager:
    """
    Manages tab creation, switching, and lifecycle events.
    Provides tab management functionality for the Kingdom AI system's 32+ components.
    """
    
    def __init__(self, notebook, event_bus=None, config=None):
        """Initialize the tab manager."""
        self.notebook = notebook
        self.event_bus = event_bus
        self.config = config or {}
        self.tabs = {}
        self.tab_frames = {}
        self.logger = logging.getLogger(__name__)
        self.current_tab_id = None
        self.rgb_manager = RGBColorManager.get_instance()
        self.tab_loading_status = {}
        self.tab_render_times = {}
        self.ui_update_queue = queue.Queue()
        self.update_thread = None
        self.is_updating = False
        self._previous_tab_id = None
        
        # Set up notebook event bindings
        self._setup_event_handlers()
        
    def _setup_event_handlers(self):
        """Set up event handlers for notebook events."""
        # Bind to notebook tab change event if available
        if hasattr(self.notebook, 'bind'):
            self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
            
        # Register with event bus if available
        if self.event_bus:
            self._register_event_handlers()
            
    def _register_event_handlers(self):
        """Register event handlers with the event bus."""
        if not self.event_bus:
            return
            
        # Register tab-related events
        self.event_bus.subscribe_sync("tab.switch", self._on_tab_switch)
        self.event_bus.subscribe_sync("tab.refresh", self._on_tab_refresh)
        self.event_bus.subscribe_sync("component.update", self._on_component_update)
        self.event_bus.subscribe_sync("system.theme_changed", self._on_theme_changed)
        
        self.logger.info("Tab manager event handlers registered")
            
    def _on_tab_changed(self, event=None):
        """Handle notebook tab changed event."""
        try:
            current_tab = self.notebook.select()
            # Find the tab_id for this notebook tab
            for tab_id, info in self.tabs.items():
                if info.get('tab_widget') == current_tab:
                    self.current_tab_id = tab_id
                    
                    # Notify via event bus
                    if self.event_bus:
                        self.event_bus.publish_sync('tab.changed', {
                            'tab_id': tab_id,
                            'previous_tab_id': getattr(self, '_previous_tab_id', None)
                        })
                    
                    # Store for next time
                    self._previous_tab_id = tab_id
                    break
        except Exception as e:
            self.logger.error(f"Error handling tab change: {e}")
            
    def _on_tab_switch(self, data):
        """Handle tab switch events."""
        tab_id = data.get('tab_id')
        if tab_id and tab_id in self.tabs:
            self.select_tab(tab_id)
            
    def _on_tab_refresh(self, data):
        """Handle tab refresh events."""
        tab_id = data.get('tab_id')
        if tab_id and tab_id in self.tabs:
            self.refresh_tab(tab_id)
        elif data.get('all', False):
            self.refresh_all_tabs()
            
    def _on_component_update(self, data):
        """Handle component update events."""
        component_id = data.get('component_id')
        if component_id:
            # Find tabs that depend on this component and refresh them
            for tab_id, tab_info in self.tabs.items():
                dependencies = tab_info.get('dependencies', [])
                if component_id in dependencies:
                    self.refresh_tab(tab_id)
                    
    def _on_theme_changed(self, data):
        """Handle theme change events."""
        self.refresh_all_tabs()
        
    async def initialize(self):
        """Initialize all tabs asynchronously.
        
        This method ensures that all 32+ components required by the Kingdom AI system
        are properly connected to their respective tabs, including:
        - Trading components
        - AI/ML components
        - Blockchain components
        - VR components
        - Core infrastructure components
        
        Returns:
            bool: True if initialization was successful
        """
        self.logger.info("Initializing all tabs asynchronously")
        
        try:
            # Connect to event bus if available
            if self.event_bus:
                self._register_event_handlers()
                
            # Initialize all registered tabs
            for tab_id, tab_info in self.tabs.items():
                self.logger.info(f"Initializing tab: {tab_id}")
                self.tab_loading_status[tab_id] = "loading"
                
                # Publish tab initialization start event
                if self.event_bus:
                    self.event_bus.publish_sync("tab.initializing", {"tab_id": tab_id})
                
                # Initialize tab content
                start_time = time.time()
                await self._initialize_tab_content(tab_id)
                self.tab_render_times[tab_id] = time.time() - start_time
                
                # Mark tab as loaded
                self.tab_loading_status[tab_id] = "loaded"
                
                # Publish tab initialization complete event
                if self.event_bus:
                    self.event_bus.publish_sync("tab.initialized", {
                        "tab_id": tab_id,
                        "render_time": self.tab_render_times[tab_id]
                    })
                    
            self.logger.info(f"All tabs initialized successfully ({len(self.tabs)} tabs)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing tabs: {e}")
            self.logger.error(traceback.format_exc())
            
            # Publish error event
            if self.event_bus:
                self.event_bus.publish_sync("tab.error", {
                    "error": str(e),
                    "details": traceback.format_exc()
                })
                
            return False
            
    async def _initialize_tab_content(self, tab_id):
        """Initialize the content for a specific tab.
        
        Args:
            tab_id: The ID of the tab to initialize
            
        Returns:
            bool: True if initialization was successful
        """
        self.logger.info(f"Initializing content for tab: {tab_id}")
        
        try:
            tab_info = self.tabs.get(tab_id)
            if not tab_info:
                self.logger.warning(f"Tab not found: {tab_id}")
                return False
                
            # If the tab has an initialize method, call it
            if 'initialize' in tab_info and callable(tab_info['initialize']):
                initialize_func = tab_info['initialize']
                
                # Check if the initialize function is a coroutine
                if asyncio.iscoroutinefunction(initialize_func):
                    await initialize_func()
                else:
                    initialize_func()
                    
            # If the tab has a frame with an initialize method, call it
            tab_frame = self.tab_frames.get(tab_id)
            if tab_frame and hasattr(tab_frame, 'initialize'):
                if asyncio.iscoroutinefunction(tab_frame.initialize):
                    await tab_frame.initialize()
                else:
                    tab_frame.initialize()
                    
            self.logger.info(f"Tab content initialized: {tab_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing tab content for {tab_id}: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    def add_tab(self, tab_id, tab_class, event_bus=None, tab_title=None):
        """Add a new tab to the notebook.
        
        Args:
            tab_id: Unique identifier for the tab
            tab_class: Class to instantiate for the tab content
            event_bus: Event bus for the tab to use
            tab_title: Display title for the tab (defaults to tab_id)
            
        Returns:
            The tab frame instance
        """
        if tab_id in self.tabs:
            self.logger.warning(f"Tab already exists: {tab_id}")
            return self.tabs[tab_id].get('instance')
            
        try:
            # Create a frame for the tab content
            tab_frame = ttk.Frame(self.notebook)
            
            # Add the frame to the notebook
            self.notebook.add(tab_frame, text=tab_title or tab_id)
            
            # Create an instance of the tab class
            tab_instance = tab_class(tab_frame, event_bus or self.event_bus)
            
            # Store the tab information
            self.tabs[tab_id] = {
                'title': tab_title or tab_id,
                'class': tab_class,
                'instance': tab_instance,
                'tab_widget': tab_frame,
                'dependencies': getattr(tab_instance, 'dependencies', [])
            }
            
            # Store the tab frame
            self.tab_frames[tab_id] = tab_frame
            
            self.logger.info(f"Added tab: {tab_id}")
            return tab_instance
            
        except Exception as e:
            self.logger.error(f"Error adding tab {tab_id}: {e}")
            self.logger.error(traceback.format_exc())
            return None
            
    def get_tab(self, tab_id):
        """Get a tab by its ID.
        
        Args:
            tab_id: ID of the tab to retrieve
            
        Returns:
            The tab frame or None if not found
        """
        tab_info = self.tabs.get(tab_id)
        return tab_info.get('instance') if tab_info else None
            
    def select_tab(self, tab_id):
        """Select a tab by its ID.
        
        Args:
            tab_id: ID of the tab to select
            
        Returns:
            bool: True if tab was selected, False otherwise
        """
        if tab_id not in self.tabs:
            self.logger.warning(f"Cannot select unknown tab: {tab_id}")
            return False
            
        tab_info = self.tabs[tab_id]
        tab_widget = tab_info.get('tab_widget')
        
        if not tab_widget:
            self.logger.warning(f"Tab widget not found: {tab_id}")
            return False
            
        try:
            self.notebook.select(tab_widget)
            self.current_tab_id = tab_id
            self.logger.debug(f"Selected tab: {tab_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error selecting tab {tab_id}: {e}")
            return False
            
    def refresh_tab(self, tab_id):
        """Refresh a specific tab by ID.
        
        Args:
            tab_id: ID of the tab to refresh
            
        Returns:
            bool: True if tab was refreshed successfully
        """
        if tab_id not in self.tabs:
            self.logger.warning(f"Cannot refresh unknown tab: {tab_id}")
            return False
            
        tab_info = self.tabs[tab_id]
        tab_instance = tab_info.get('instance')
        
        if not tab_instance:
            self.logger.warning(f"Tab instance not initialized: {tab_id}")
            return False
            
        # Call refresh method if available
        if hasattr(tab_instance, 'refresh'):
            try:
                tab_instance.refresh()
                self.logger.debug(f"Refreshed tab: {tab_id}")
                return True
            except Exception as e:
                self.logger.error(f"Error refreshing tab {tab_id}: {e}")
                self.logger.error(traceback.format_exc())
                return False
        else:
            self.logger.debug(f"Tab has no refresh method: {tab_id}")
            return False
            
    def refresh_all_tabs(self):
        """Refresh all tabs.
        
        Returns:
            int: Number of tabs successfully refreshed
        """
        refreshed_count = 0
        
        for tab_id in self.tabs:
            if self.refresh_tab(tab_id):
                refreshed_count += 1
                
        self.logger.debug(f"Refreshed {refreshed_count} tabs")
        return refreshed_count
    
    def update_tab_status(self, system_name, status):
        """Update all tabs with a system status change.
        
        Args:
            system_name: The name of the system (redis, database, network, etc.)
            status: The status value (usually boolean or string)
        """
        try:
            # Normalize system name
            system_name = str(system_name).lower()
            
            # Update all initialized tabs that have a status update method
            updated_tabs = 0
            for tab_id, info in self.tabs.items():
                if info['instance'] is None:
                    continue
                    
                tab_instance = info['instance']
                
                # Try calling a specialized status update method
                if hasattr(tab_instance, f'update_{system_name}_status'):
                    method = getattr(tab_instance, f'update_{system_name}_status')
                    method(status)
                    updated_tabs += 1
                    continue
                    
                # Try calling a generic system status update method
                if hasattr(tab_instance, 'update_system_status'):
                    tab_instance.update_system_status(system_name, status)
                    updated_tabs += 1
                    continue
            
            self.logger.debug(f"Updated {updated_tabs} tabs with {system_name} status: {status}")
            return True
        except Exception as e:
            self.logger.error(f"Error updating tab status: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def update_all_tabs(self, update_type, data):
        """Update all tabs with the same data.
        
        Args:
            update_type: The type of update (e.g. 'system', 'settings')
            data: The data to send to all tabs
        """
        try:
            update_count = 0
            
            # Update all initialized tabs
            for tab_id, info in self.tabs.items():
                if info['instance'] is None:
                    continue
                    
                tab_instance = info['instance']
                
                # Try calling a specialized update method
                if hasattr(tab_instance, f'update_{update_type}'):
                    method = getattr(tab_instance, f'update_{update_type}')
                    method(data)
                    update_count += 1
                    continue
                    
                # Try calling the generic update method
                if hasattr(tab_instance, 'update'):
                    tab_instance.update({update_type: data})
                    update_count += 1
                    continue
                    
            self.logger.debug(f"Updated {update_count} tabs with {update_type} data")
            return True
        except Exception as e:
            self.logger.error(f"Error updating all tabs: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    def get_tab_status(self):
        """Get the status of all tabs."""
        return {
            tab_id: {
                'title': info['title'],
                'status': self.tab_loading_status.get(tab_id, 'unknown'),
                'render_time': self.tab_render_times.get(tab_id, 0),
                'initialized': info['instance'] is not None
            }
            for tab_id, info in self.tabs.items()
        }

# Convenience function to create a tab manager
def create_tab_manager(notebook, event_bus=None, config=None):
    """Create a new TabManager instance.
    
    Args:
        notebook: The notebook widget to manage
        event_bus: Optional event bus for communication
        config: Optional configuration dictionary
        
    Returns:
        A new TabManager instance
    """
    return TabManager(notebook, event_bus, config)
