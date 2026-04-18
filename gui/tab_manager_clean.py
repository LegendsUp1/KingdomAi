"""
TabManager Module for Kingdom AI

This module provides tab management functionality for the Kingdom AI GUI system,
integrating with PyQt6 and the event bus system.
"""

import traceback
import logging
import asyncio
from typing import Dict, List, Optional, Union, Any, Callable

# Check for PyQt6 availability - required for Kingdom AI
try:
    from PyQt6.QtWidgets import QTabWidget, QWidget, QVBoxLayout
    has_pyqt6 = True
except ImportError:
    has_pyqt6 = False

# Local imports
from core.base_component import BaseComponent
from utils.async_support import AsyncSupport
from event_bus.event_bus import EventBus

class TabManager(BaseComponent):
    """
    TabManager handles the creation and management of tabs within the Kingdom AI GUI.
    
    This component requires PyQt6 and will halt the system if PyQt6 is unavailable,
    as per the strict requirements of Kingdom AI's GUI implementation.
    """
    
    def __init__(self, event_bus: EventBus, parent=None):
        """Initialize the TabManager with an event bus connection.
        
        Args:
            event_bus: The EventBus instance for communication
            parent: Optional parent component
        """
        super().__init__(name="TabManager", event_bus=event_bus)
        self.logger = logging.getLogger("Kingdom.GUI.TabManager")
        self.parent = parent
        self._widget = None
        self.notebook = None
        self.tabs = {}
        self.current_tab = None
        
        # Initialize with PyQt6 check
        if not has_pyqt6:
            self.logger.critical("PyQt6 is required for TabManager - Kingdom AI cannot function without it")
            raise RuntimeError("Critical dependency missing: PyQt6 required for GUI")
            
        # Set up event subscriptions
        self.subscribe_to_events()
        
    def subscribe_to_events(self):
        """Set up event bus subscriptions for tab-related events."""
        self.logger.info("Setting up event subscriptions for TabManager")
        
        # Wrap in QTimer to prevent task nesting during init
        from PyQt6.QtCore import QTimer
        import asyncio
        
        def subscribe_all():
            try:
                asyncio.ensure_future(self.event_bus.subscribe("create_tab", self.handle_create_tab))
                asyncio.ensure_future(self.event_bus.subscribe("switch_tab", self.handle_switch_tab))
                asyncio.ensure_future(self.event_bus.subscribe("close_tab", self.handle_close_tab))
                asyncio.ensure_future(self.event_bus.subscribe("gui_initialized", self.handle_gui_initialized))
                self.logger.info("TabManager event subscriptions completed")
            except Exception as e:
                self.logger.error(f"Error subscribing to events: {e}")
        
        QTimer.singleShot(4800, subscribe_all)  # 4.8 seconds delay
    
    def handle_gui_initialized(self, event_data=None):
        """Handle GUI initialization event to prepare tabs."""
        self.logger.info("Received GUI initialized event")
        self.initialize_tabs()
    
    def initialize_tabs(self):
        """Initialize default tabs after GUI is ready."""
        self.logger.info("Initializing default tabs")
        try:
            # Create the notebook widget first
            self.create_notebook()
            
            # Set up default tabs as required
            self.create_default_tabs()
        except Exception as e:
            self.logger.error(f"Failed to initialize tabs: {e}")
            self.logger.error(traceback.format_exc())
    
    def create_default_tabs(self):
        """Create the default set of tabs required by Kingdom AI."""
        self.logger.info("Creating default tabs")
        # Default tabs will be created here
        # These are critical components of the Kingdom AI interface
        pass
    
    def handle_create_tab(self, event_data):
        """Handle create_tab events from the event bus."""
        if AsyncSupport.is_coroutine_function(self.create_tab):
            AsyncSupport.schedule_coroutine(self.create_tab(event_data))
        else:
            self.create_tab(event_data)
    
    def handle_switch_tab(self, event_data):
        """Handle switch_tab events from the event bus."""
        if AsyncSupport.is_coroutine_function(self.switch_to_tab):
            AsyncSupport.schedule_coroutine(self.switch_to_tab(event_data))
        else:
            self.switch_to_tab(event_data)
    
    def handle_close_tab(self, event_data):
        """Handle close_tab events from the event bus."""
        if AsyncSupport.is_coroutine_function(self.close_tab):
            AsyncSupport.schedule_coroutine(self.close_tab(event_data))
        else:
            self.close_tab(event_data)

    def create_notebook(self):
        """Create the tab notebook widget for the TabManager UI.

        This method creates the main tabbed interface container when PyQt6 is available,
        or halts the system when PyQt6 is unavailable (mandatory dependency).
        """
        if has_pyqt6:
            self.logger.info("Creating QTabWidget for tabs")
            try:
                # Ensure any existing notebook is properly removed
                self.notebook = None
                
                # Create the tab notebook widget
                self.notebook = QTabWidget()
                
                # Configure the notebook
                if hasattr(self.notebook, 'setTabPosition') and hasattr(QTabWidget, 'TabPosition'):
                    self.notebook.setTabPosition(QTabWidget.TabPosition.North)
                
                # Make tabs look modern and attractive
                if hasattr(self.notebook, "setDocumentMode"):
                    self.notebook.setDocumentMode(True)
                
                # Allow tabs to be movable
                if hasattr(self.notebook, "setMovable"):
                    self.notebook.setMovable(True)
                
                # Create layout for the notebook if we have a widget
                if self._widget is not None and isinstance(self._widget, QWidget):
                    try:
                        layout = QVBoxLayout()
                        layout.addWidget(self.notebook)
                        self._widget.setLayout(layout)
                    except Exception as e:
                        self.logger.error(f"Error setting notebook layout: {e}")
                
                self.logger.info("Successfully created QTabWidget for tabs")
            except Exception as e:
                self.logger.error(f"Error creating QTabWidget: {e}")
                self.logger.error(traceback.format_exc())
                # Critical error - halt if QTabWidget creation fails
                self.logger.critical("Failed to create QTabWidget - Kingdom AI requires functioning GUI")
                raise RuntimeError("Failed to create QTabWidget - Kingdom AI requires functioning GUI")
        else:
            # PyQt6 is mandatory for Kingdom AI GUI - halt if unavailable
            self.logger.critical("PyQt6 is required for Kingdom AI GUI - halting application")
            raise RuntimeError("PyQt6 is required for Kingdom AI GUI")

    def setLayout(self, layout):
        """Set the layout for the TabManager's widget.
        
        Args:
            layout: The layout to set for the widget
        """
        if self._widget is not None:
            self._widget.setLayout(layout)
    
    def create_tab(self, tab_data):
        """Create a new tab with the provided data.
        
        Args:
            tab_data: Dictionary containing tab information
        """
        tab_id = tab_data.get('id')
        tab_title = tab_data.get('title', 'Untitled')
        tab_content = tab_data.get('content')
        
        if tab_id is None or tab_content is None:
            self.logger.error("Cannot create tab: missing id or content")
            return
        
        if tab_id in self.tabs:
            self.logger.warning(f"Tab with id {tab_id} already exists, switching to it")
            self.switch_to_tab({'id': tab_id})
            return
        
        # Create the tab
        self.logger.info(f"Creating new tab: {tab_title} ({tab_id})")
        
        try:
            if isinstance(tab_content, QWidget):
                widget = tab_content
            else:
                self.logger.error(f"Cannot create tab: content must be a QWidget, got {type(tab_content)}")
                return
            
            # Add the tab to the notebook
            if self.notebook is not None:
                tab_index = self.notebook.addTab(widget, tab_title)
                self.tabs[tab_id] = {
                    'widget': widget,
                    'title': tab_title,
                    'index': tab_index
                }
                
                # Switch to the new tab
                self.notebook.setCurrentIndex(tab_index)
                self.current_tab = tab_id
                
                # Publish event that tab was created
                self.event_bus.publish("tab_created", {
                    'id': tab_id,
                    'title': tab_title
                })
            else:
                self.logger.error("Cannot create tab: notebook not initialized")
        except Exception as e:
            self.logger.error(f"Error creating tab {tab_title}: {e}")
            self.logger.error(traceback.format_exc())
    
    def switch_to_tab(self, tab_data):
        """Switch to the specified tab.
        
        Args:
            tab_data: Dictionary containing tab id
        """
        tab_id = tab_data.get('id')
        
        if tab_id not in self.tabs:
            self.logger.warning(f"Cannot switch to tab {tab_id}: not found")
            return
        
        tab = self.tabs[tab_id]
        self.notebook.setCurrentIndex(tab['index'])
        self.current_tab = tab_id
        
        # Publish event that tab was switched
        self.event_bus.publish("tab_switched", {
            'id': tab_id,
            'title': tab['title']
        })
    
    def close_tab(self, tab_data):
        """Close the specified tab.
        
        Args:
            tab_data: Dictionary containing tab id
        """
        tab_id = tab_data.get('id')
        
        if tab_id not in self.tabs:
            self.logger.warning(f"Cannot close tab {tab_id}: not found")
            return
        
        tab = self.tabs[tab_id]
        
        # Remove the tab
        self.notebook.removeTab(tab['index'])
        
        # Adjust indices of other tabs
        for t_id, t_data in self.tabs.items():
            if t_data['index'] > tab['index']:
                t_data['index'] -= 1
        
        # Remove from tabs dictionary
        del self.tabs[tab_id]
        
        # Update current tab if needed
        if self.current_tab == tab_id:
            if self.tabs:
                # Switch to the first available tab
                first_tab_id = next(iter(self.tabs))
                self.switch_to_tab({'id': first_tab_id})
            else:
                self.current_tab = None
        
        # Publish event that tab was closed
        self.event_bus.publish("tab_closed", {
            'id': tab_id
        })
