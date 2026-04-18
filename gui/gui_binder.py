#!/usr/bin/env python3
"""
Kingdom AI GUI Binder Module

This module implements the central binding mechanism for connecting GUI components
to the event bus and handling state updates across the entire application.
"""

import logging
import traceback
from datetime import datetime
import threading
import time

logger = logging.getLogger("KingdomAI.GUIBinder")

class GUIBinder:
    """
    Central binding mechanism for GUI components and the event bus.
    
    This class manages the connections between GUI components and the event bus,
    ensuring that UI updates are handled in a thread-safe manner and that 
    events trigger the appropriate UI changes.
    """
    
    def __init__(self, event_bus=None, main_window=None):
        """Initialize the GUI binder"""
        self.event_bus = event_bus
        self.main_window = main_window
        self.components = {}
        self.tabs = {}
        self.update_queue = []
        self.update_lock = threading.Lock()
        self.update_thread = None
        self.running = False
        
        # Event handlers map from event_type to list of handler functions
        self.event_handlers = {}
        
        self.logger = logger
        self.logger.info("GUI Binder initialized")
    
    def start(self):
        """Start the GUI binder"""
        if self.running:
            return
        
        self.running = True
        
        # Register with the event bus
        if self.event_bus:
            self._register_event_handlers()
        
        # Start the update thread
        self.update_thread = threading.Thread(target=self._process_updates, daemon=True)
        self.update_thread.start()
        
        self.logger.info("GUI Binder started")
    
    def stop(self):
        """Stop the GUI binder"""
        self.running = False
        
        if self.update_thread:
            self.update_thread.join(timeout=2.0)
        
        self.logger.info("GUI Binder stopped")
    
    def register_component(self, component_id, component, event_types=None):
        """Register a component with the binder"""
        self.components[component_id] = {
            "component": component,
            "event_types": event_types or []
        }
        
        # For each event type, register a handler if component has update_from_event method
        if hasattr(component, "update_from_event") and event_types:
            for event_type in event_types:
                self._register_component_handler(component_id, event_type)
        
        self.logger.info(f"Registered component: {component_id}")
        
        # Return the component ID for reference
        return component_id
    
    def register_tab(self, tab_id, tab, event_types=None):
        """Register a tab with the binder"""
        self.tabs[tab_id] = {
            "tab": tab,
            "event_types": event_types or []
        }
        
        # For each event type, register a handler if tab has update_from_event method
        if hasattr(tab, "update_from_event") and event_types:
            for event_type in event_types:
                self._register_tab_handler(tab_id, event_type)
        
        self.logger.info(f"Registered tab: {tab_id}")
        
        # Return the tab ID for reference
        return tab_id
    
    def _register_component_handler(self, component_id, event_type):
        """Register an event handler for a component"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
            
            # Subscribe to the event type in the event bus
            if self.event_bus:
                self.event_bus.subscribe(event_type, self._handle_event)
        
        # Add component handler to the list for this event type
        handler = {
            "type": "component",
            "id": component_id
        }
        
        if handler not in self.event_handlers[event_type]:
            self.event_handlers[event_type].append(handler)
    
    def _register_tab_handler(self, tab_id, event_type):
        """Register an event handler for a tab"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
            
            # Subscribe to the event type in the event bus
            if self.event_bus:
                self.event_bus.subscribe(event_type, self._handle_event)
        
        # Add tab handler to the list for this event type
        handler = {
            "type": "tab",
            "id": tab_id
        }
        
        if handler not in self.event_handlers[event_type]:
            self.event_handlers[event_type].append(handler)
    
    def _register_event_handlers(self):
        """Register all event handlers with the event bus"""
        if not self.event_bus:
            self.logger.warning("Cannot register event handlers: No event bus available")
            return
        
        # Register handlers for all event types
        for event_type in self.event_handlers:
            self.event_bus.subscribe(event_type, self._handle_event)
        
        # Also subscribe to general system events
        self.event_bus.subscribe("system.status", self._handle_event)
        self.event_bus.subscribe("gui.update", self._handle_event)
        self.event_bus.subscribe("error", self._handle_event)
        
        self.logger.info(f"Registered event handlers for {len(self.event_handlers)} event types")
    
    def _handle_event(self, event_type, data):
        """Handle an event from the event bus"""
        try:
            # Queue the event for processing
            with self.update_lock:
                self.update_queue.append((event_type, data))
            
            self.logger.debug(f"Queued event: {event_type}")
        except Exception as e:
            self.logger.error(f"Error handling event {event_type}: {e}")
            self.logger.error(traceback.format_exc())
    
    def _process_updates(self):
        """Process updates in the update queue"""
        while self.running:
            updates_to_process = []
            
            # Get all queued updates
            with self.update_lock:
                if self.update_queue:
                    updates_to_process = self.update_queue.copy()
                    self.update_queue.clear()
            
            # Process the updates
            for event_type, data in updates_to_process:
                self._process_event(event_type, data)
            
            # Sleep a bit to avoid hogging the CPU
            time.sleep(0.05)
    
    def _process_event(self, event_type, data):
        """Process a single event"""
        try:
            # Get handlers for this event type
            handlers = self.event_handlers.get(event_type, [])
            
            # Handle general system events
            if event_type == "system.status" and self.main_window:
                # Update status bar or system indicators
                if hasattr(self.main_window, "update_status"):
                    self.main_window.update_status(data)
            
            # Handle GUI update events
            if event_type == "gui.update":
                component_id = data.get("component_id")
                if component_id and component_id in self.components:
                    component = self.components[component_id]["component"]
                    if hasattr(component, "update_from_event"):
                        component.update_from_event(event_type, data)
            
            # Handle error events
            if event_type == "error":
                self._handle_error(data)
            
            # Call handlers for the specific event type
            for handler in handlers:
                if handler["type"] == "component":
                    component_id = handler["id"]
                    if component_id in self.components:
                        component = self.components[component_id]["component"]
                        if hasattr(component, "update_from_event"):
                            component.update_from_event(event_type, data)
                
                elif handler["type"] == "tab":
                    tab_id = handler["id"]
                    if tab_id in self.tabs:
                        tab = self.tabs[tab_id]["tab"]
                        if hasattr(tab, "update_from_event"):
                            tab.update_from_event(event_type, data)
            
            self.logger.debug(f"Processed event: {event_type}")
        except Exception as e:
            self.logger.error(f"Error processing event {event_type}: {e}")
            self.logger.error(traceback.format_exc())
    
    def _handle_error(self, error_data):
        """Handle an error event"""
        error_type = error_data.get("type", "unknown")
        error_message = error_data.get("message", "Unknown error")
        component = error_data.get("component", "unknown")
        
        self.logger.error(f"Error in {component}: {error_type} - {error_message}")
        
        # If we have a main window with an error display method, show the error
        if self.main_window and hasattr(self.main_window, "display_error"):
            self.main_window.display_error(error_data)
    
    def publish_event(self, event_type, data=None):
        """Publish an event to the event bus"""
        if self.event_bus:
            self.event_bus.publish(event_type, data or {})
            self.logger.debug(f"Published event: {event_type}")
        else:
            self.logger.warning(f"Cannot publish event {event_type}: No event bus available")
    
    def update_component(self, component_id, data):
        """Directly update a component with data"""
        if component_id in self.components:
            component = self.components[component_id]["component"]
            if hasattr(component, "update"):
                component.update(data)
            elif hasattr(component, "update_from_event"):
                component.update_from_event("gui.update", data)
            
            self.logger.debug(f"Updated component: {component_id}")
        else:
            self.logger.warning(f"Cannot update component {component_id}: Not registered")
    
    def update_all_components(self, event_type=None):
        """
        Update all components, optionally filtering by event type
        
        This is useful for refreshing the UI state after a major system change
        """
        updated_count = 0
        
        # If event_type is specified, only update components that subscribe to it
        if event_type:
            handlers = self.event_handlers.get(event_type, [])
            for handler in handlers:
                if handler["type"] == "component":
                    component_id = handler["id"]
                    if component_id in self.components:
                        component = self.components[component_id]["component"]
                        if hasattr(component, "update_from_event"):
                            component.update_from_event(event_type, {})
                            updated_count += 1
        # Otherwise update all components with a refresh event
        else:
            for component_id, component_info in self.components.items():
                component = component_info["component"]
                if hasattr(component, "refresh"):
                    component.refresh()
                    updated_count += 1
                elif hasattr(component, "update_from_event"):
                    component.update_from_event("gui.refresh", {})
                    updated_count += 1
        
        self.logger.info(f"Updated {updated_count} components")

# Singleton instance for global access
_instance = None

def get_instance(event_bus=None, main_window=None):
    """Get the singleton instance of the GUI binder"""
    global _instance
    if _instance is None:
        _instance = GUIBinder(event_bus, main_window)
    return _instance
