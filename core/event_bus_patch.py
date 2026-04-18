# State-of-the-Art EventBus Patch for async/sync compatibility
# This module monkey-patches the EventBus class to make async methods
# work properly in both async and sync contexts

import asyncio
import logging
import functools
import inspect
from typing import Callable, Any, Dict

logger = logging.getLogger("KingdomAI.EventBus.Patch")

def apply_patches():
    """Apply patches to EventBus class to fix async/sync compatibility issues"""
    from core.event_bus import EventBus
    
    logger.info("Applying state-of-the-art EventBus patches for async/sync compatibility")
    
    # Store original methods
    original_subscribe = EventBus.subscribe
    original_unsubscribe = EventBus.unsubscribe
    
    # Define replacement methods that properly handle both async and sync contexts
    def sync_compatible_subscribe(self, event_type, callback):
        """
        Non-async replacement for EventBus.subscribe that works in both contexts
        """
        # Direct modification of subscribers dict for immediate effect
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
            
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)
            logger.debug(f"Subscribed to event: {event_type} (sync compatible)")
        return True
    
    def sync_compatible_unsubscribe(self, event_type, callback):
        """
        Non-async replacement for EventBus.unsubscribe that works in both contexts
        """
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            logger.debug(f"Unsubscribed from event: {event_type} (sync compatible)")
        return True
    
    # Apply replacements
    EventBus.subscribe = sync_compatible_subscribe
    EventBus.unsubscribe = sync_compatible_unsubscribe
    
    # Add compatibility aliases
    EventBus.subscribe_sync = sync_compatible_subscribe
    EventBus.unsubscribe_sync = sync_compatible_unsubscribe
    
    logger.info("✅ EventBus patched successfully")

# Apply patches when this module is imported
apply_patches()
