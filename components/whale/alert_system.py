"""
AlertSystem - Kingdom AI component
"""
import os
import logging
from typing import Any, Dict, Optional

class AlertSystem:
    """
    AlertSystem for Kingdom AI system.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the AlertSystem."""
        self.name = "whale.alertsystem"
        self.logger = logging.getLogger(f"KingdomAI.AlertSystem")
        self._event_bus = event_bus
        self._config = config or {}
        self.initialized = False
        self.logger.info(f"AlertSystem initialized")
    
    @property
    def event_bus(self):
        """Get the event bus."""
        return self._event_bus
    
    @event_bus.setter
    def event_bus(self, bus):
        """Set the event bus."""
        self._event_bus = bus
        if bus:
            self._register_event_handlers()
    
    def set_event_bus(self, bus):
        """Set the event bus and return success."""
        self.event_bus = bus
        return True
    
    def _register_event_handlers(self):
        """Register handlers with the event bus."""
        if not self._event_bus:
            return False
            
        try:
            self._event_bus.subscribe(f"whale.request", self._handle_request)
            self.logger.debug(f"Registered event handlers for {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
            return False
    
    def _handle_request(self, event_type, data):
        """Handle component requests."""
        self.logger.debug(f"Handling request {event_type}: {data}")
        
        if self._event_bus:
            self._event_bus.publish(f"whale.response", {
                "status": "success",
                "origin": self.name,
                "data": {"message": "Request processed by AlertSystem"}
            })
        
        return {"status": "success"}
    
    async def initialize(self):
        """Initialize the component asynchronously."""
        self.logger.info(f"Initializing AlertSystem...")
        try:
            # Perform component-specific initialization here
            self.initialized = True
            self.logger.info(f"AlertSystem initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing AlertSystem: {e}")
            return False
    
    def initialize_sync(self):
        """Initialize the component synchronously."""
        self.logger.info(f"Synchronously initializing AlertSystem...")
        try:
            # Perform component-specific initialization here
            self.initialized = True
            self.logger.info(f"AlertSystem synchronous initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error during synchronous initialization: {e}")
            return False