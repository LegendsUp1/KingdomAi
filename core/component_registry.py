"""
SOTA 2026: Central Component Registry for EventBus
Ensures all components are properly registered and discoverable.
"""

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ComponentRegistry:
    """
    Central registry for all Kingdom AI components.
    
    SOTA 2026: Implements singleton pattern with lazy initialization
    to ensure proper EventBus registration.
    
    SOTA 2026 CONCURRENCY FIX: Thread-safe with RLock for concurrent access.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.components: Dict[str, Any] = {}
            self.event_bus: Optional[Any] = None
            self._lock = threading.RLock()  # SOTA 2026 FIX: Thread-safe access
            self._initialized = True
            logger.info("✅ ComponentRegistry initialized (thread-safe)")
    
    def set_event_bus(self, event_bus):
        """Set the central event bus instance."""
        with self._lock:
            self.event_bus = event_bus
            logger.info(f"✅ EventBus registered (ID: {id(event_bus)})")
    
    def register(self, name: str, component: Any, force: bool = False):
        """
        Register a component in the registry.
        
        Args:
            name: Component identifier (e.g., 'voice_manager', 'thoth_ai')
            component: Component instance
            force: Override existing registration
        """
        with self._lock:  # SOTA 2026 FIX: Protect check-then-set race condition
            if name in self.components and not force:
                logger.warning(f"⚠️  Component '{name}' already registered")
                return False
            
            self.components[name] = component
            logger.info(f"✅ Registered component: {name}")
            
            # Auto-register on EventBus if available
            if self.event_bus and hasattr(self.event_bus, 'register_component'):
                try:
                    self.event_bus.register_component(name, component)
                    logger.info(f"✅ Component '{name}' registered on EventBus")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to register '{name}' on EventBus: {e}")
            
            return True
    
    def unregister(self, name: str):
        """Unregister a component."""
        with self._lock:
            if name in self.components:
                del self.components[name]
                logger.info(f"✅ Unregistered component: {name}")
                return True
            return False
    
    def get(self, name: str) -> Optional[Any]:
        """Get a registered component by name."""
        with self._lock:
            return self.components.get(name)
    
    def list_components(self) -> Dict[str, str]:
        """List all registered components."""
        with self._lock:
            return {
                name: type(comp).__name__
                for name, comp in self.components.items()
            }
    
    def ensure_registered(self, name: str, component: Any):
        """
        Ensure a component is registered, registering it if not already present.
        
        SOTA 2026: Used during component initialization to guarantee registration.
        """
        with self._lock:
            if name not in self.components:
                return self.register(name, component)
            return True


# Global singleton accessor
def get_registry() -> ComponentRegistry:
    """Get the global ComponentRegistry instance."""
    return ComponentRegistry()


def register_component(name: str, component: Any, force: bool = False):
    """Convenience function to register a component."""
    return get_registry().register(name, component, force)


def get_component(name: str) -> Optional[Any]:
    """Convenience function to get a component."""
    return get_registry().get(name)
