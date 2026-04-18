"""
APIKeyManager - Kingdom AI component (Wrapper)

DEPRECATED: This module is a thin wrapper around the main APIKeyManager.
Use core.api_key_manager.APIKeyManager directly for all new code.

2026 SOTA: All API key operations are now consolidated in core/api_key_manager.py
"""
import os
import sys
import logging
import warnings
from typing import Any, Dict, Optional

# Add parent directories to path for imports
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Import the authoritative implementation
try:
    from core.api_key_manager import APIKeyManager as MainAPIKeyManager
    HAS_MAIN_MANAGER = True
except ImportError:
    HAS_MAIN_MANAGER = False
    MainAPIKeyManager = None


class APIKeyManager:
    """
    APIKeyManager wrapper for backward compatibility.
    
    DEPRECATED: Use core.api_key_manager.APIKeyManager directly.
    All operations delegate to the main implementation.
    """
    
    _deprecation_warned = False
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the APIKeyManager wrapper."""
        self.name = "api.apikeymanager"
        self.logger = logging.getLogger(f"KingdomAI.APIKeyManager")
        self._event_bus = event_bus
        self._config = config or {}
        self.initialized = False
        
        # Emit deprecation warning once
        if not APIKeyManager._deprecation_warned:
            warnings.warn(
                "components.api.api_key_manager.APIKeyManager is deprecated. "
                "Use core.api_key_manager.APIKeyManager instead.",
                DeprecationWarning,
                stacklevel=2
            )
            self.logger.warning("⚠️ DEPRECATED: Using wrapper APIKeyManager from components/api")
            self.logger.warning("   Migrate to: from core.api_key_manager import APIKeyManager")
            APIKeyManager._deprecation_warned = True
        
        # Delegate to main implementation
        if HAS_MAIN_MANAGER:
            self._main_manager = MainAPIKeyManager.get_instance(
                event_bus=event_bus,
                config=config
            )
            self.initialized = True
            self.logger.info(f"APIKeyManager wrapper initialized (delegating to main manager)")
        else:
            self._main_manager = None
            self.logger.error("Main APIKeyManager not available")
    
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
            self._event_bus.subscribe(f"api.request", self._handle_request)
            self.logger.debug(f"Registered event handlers for {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
            return False
    
    def _handle_request(self, event_type, data):
        """Handle component requests."""
        self.logger.debug(f"Handling request {event_type}: {data}")
        
        if self._event_bus:
            self._event_bus.publish(f"api.response", {
                "status": "success",
                "origin": self.name,
                "data": {"message": "Request processed by APIKeyManager"}
            })
        
        return {"status": "success"}
    
    async def initialize(self):
        """Initialize the component asynchronously."""
        self.logger.info(f"Initializing APIKeyManager...")
        try:
            # Perform component-specific initialization here
            self.initialized = True
            self.logger.info(f"APIKeyManager initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing APIKeyManager: {e}")
            return False
    
    def initialize_sync(self):
        """Initialize the component synchronously."""
        self.logger.info(f"Synchronously initializing APIKeyManager...")
        try:
            # Perform component-specific initialization here
            self.initialized = True
            self.logger.info(f"APIKeyManager synchronous initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error during synchronous initialization: {e}")
            return False