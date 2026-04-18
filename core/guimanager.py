#!/usr/bin/env python3
"""
GUIManager for Kingdom AI
"""

import logging
from core.base_component import BaseComponent

logger = logging.getLogger("KingdomAI.GUIManager")

class GUIManager(BaseComponent):
    """
    GUIManager implementation
    """
    
    def __init__(self):
        super().__init__(name="GUIManager")
        self.initialized = False
        
    def initialize(self):
        """Initialize the GUIManager"""
        logger.info("GUIManager initializing...")
        self.initialized = True
        return True
        
    def subscribe_to_events(self):
        """Subscribe to events from the event bus"""
        if self.event_bus:
            self.event_bus.subscribe_sync('system.status', self.handle_system_status)
            self.event_bus.subscribe_sync('system.shutdown', self.cleanup)
    
    def handle_system_status(self, event_data=None):
        """Handle system status events"""
        logger.debug(f"Received system status: {event_data}")
        
    def cleanup(self, event_data=None):
        """Clean up resources"""
        logger.info("Cleaning up GUIManager...")
        self.initialized = False
