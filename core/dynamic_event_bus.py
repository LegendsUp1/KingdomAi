"""
Kingdom AI - Dynamic Event Bus

A dynamic event bus implementation that provides enhanced functionality
and compatibility with the asynchronous event system.
"""

import asyncio
import logging
import threading
from typing import Dict, Any, Callable, Optional

# Import the base EventBus class
from core.event_bus import EventBus

class DynamicEventBus(EventBus):
    """Dynamic event bus implementation with enhanced compatibility.
    
    This class extends the base EventBus with additional features:
    - Component registration and management
    - Compatibility aliases for various event method names
    - Both async and sync event handling capabilities
    """
    # Additional class documentation
    
    def __init__(self):
        """Initialize the DynamicEventBus."""
        super().__init__()
        self.logger = logging.getLogger("KingdomAI.DynamicEventBus")
        self.logger.info("DynamicEventBus initialized")
        
        # Additional properties for dynamic component registration
        self._components = {}
        self._component_lock = threading.RLock()
        
        # Ensure handlers dictionary exists for compatibility
        if not hasattr(self, 'handlers') and hasattr(self, '_handlers'):
            self.handlers = self._handlers
        elif not hasattr(self, 'handlers'):
            self.handlers = {}
            
        # Add start method if missing
        if not hasattr(self, 'start'):
            self.start = self.start_async
    
    async def register_component(self, component_id: str, component: Any) -> bool:
        """
        Register a component with the event bus.
        
        Args:
            component_id: Unique identifier for the component
            component: The component object
            
        Returns:
            bool: True if registered successfully
        """
        with self._component_lock:
            if component_id in self._components:
                self.logger.warning(f"Component {component_id} already registered")
                return False
                
            self._components[component_id] = component
            self.logger.info(f"Component {component_id} registered successfully")
            
            # Publish component registration event
            await self.publish("component:registered", {
                "component_id": component_id,
                "component": component
            })
            
            return True
    
    def register_component_sync(self, component_id: str, component: Any) -> bool:
        """
        Register a component with the event bus synchronously.
        
        Args:
            component_id: Unique identifier for the component
            component: The component object
            
        Returns:
            bool: True if registered successfully
        """
        with self._component_lock:
            if component_id in self._components:
                self.logger.warning(f"Component {component_id} already registered")
                return False
                
            self._components[component_id] = component
            self.logger.info(f"Component {component_id} registered successfully")
            
            # Use emit for async-compatible sync publish
            self.emit("component:registered", {
                "component_id": component_id,
                "component": component
            })
            
            return True
    
    def get_component(self, component_id: str) -> Optional[Any]:
        """
        Get a registered component by ID.
        
        Args:
            component_id: The component ID to retrieve
            
        Returns:
            The component or None if not found
        """
        return self._components.get(component_id)
    
    def get_all_components(self) -> Dict[str, Any]:
        """
        Get all registered components.
        
        Returns:
            Dict mapping component IDs to component objects
        """
        with self._component_lock:
            return self._components.copy()
    
    # Add compatibility aliases for different naming conventions
    # These ensure that the event bus works with components
    # that expect different method names
    
    def trigger(self, event_type: str, data: Any = None) -> bool:
        """Alias for publish_sync to support components that use trigger naming."""
        return self.publish_sync(event_type, data)
    
    def emit(self, event_type: str, data: Any = None) -> bool:
        """Alias for publish_sync to support components that use emit naming."""
        if hasattr(super(), 'emit'):
            # Use parent's emit if available
            return super().emit(event_type, data)
        else:
            # Handle async publish if needed
            try:
                if asyncio.iscoroutinefunction(self.publish):
                    # Handle async publish without returning coroutine
                    loop = asyncio.get_event_loop()
                    future = asyncio.run_coroutine_threadsafe(self.publish(event_type, data), loop)
                    # Don't wait for result, just acknowledge the event was sent
                    return True
                else:
                    return self.publish_sync(event_type, data)
            except RuntimeError:
                self.logger.error(f"No event loop available for emit({event_type})")
                return False
    
    def on(self, event_type: str, handler: Callable) -> bool:
        """Alias for subscribe to support components that use on naming."""
        # Handle both sync and async subscribe methods
        if asyncio.iscoroutinefunction(self.subscribe):
            try:
                loop = asyncio.get_event_loop()
                future = asyncio.run_coroutine_threadsafe(self.subscribe(event_type, handler), loop)
                # Don't wait for result, just acknowledge the event was subscribed
                return True
            except RuntimeError:
                self.logger.error(f"No event loop available for on({event_type})")
                return False
        return self.subscribe(event_type, handler) if callable(self.subscribe) else False
    
    def addEventListener(self, event_type: str, handler: Callable) -> bool:
        """Alias for subscribe to support components that use addEventListener naming."""
        # Use the same implementation as on() to avoid duplication
        return self.on(event_type, handler)
        
    async def start_async(self) -> bool:
        """Start the event bus asynchronously.
        
        Returns:
            bool: True indicating successful start
        """
        self.logger.info("Starting DynamicEventBus")
        return True
        
    def start_sync(self) -> bool:
        """Start the event bus synchronously.
        
        Returns:
            bool: True indicating successful start
        """
        self.logger.info("Starting DynamicEventBus (sync)")
        return True
        
    # Make the class callable for backward compatibility
    def __call__(self, *args, **kwargs):
        """Make the class instance callable, returning self for chaining.
        
        This allows backward compatibility with code that calls the event bus instance directly.
        """
        self.logger.warning("DynamicEventBus instance was called directly - this is deprecated")
        return self
