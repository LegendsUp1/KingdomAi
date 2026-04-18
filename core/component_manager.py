"""Component manager for Kingdom AI system."""

import logging
import asyncio
import os
import importlib
import traceback
import threading
from typing import Dict, Any, Optional, TypeVar, List, Set

from core.event_bus import EventBus

T = TypeVar('T')

class ComponentManager:
    """Manages system components."""
    
    # Singleton instance
    _instance = None
    _instance_lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, event_bus: Optional[EventBus] = None) -> 'ComponentManager':
        """Get the singleton instance of ComponentManager.
        
        Args:
            event_bus: Optional event bus for component communication
            
        Returns:
            Singleton ComponentManager instance
        """
        with cls._instance_lock:
            if cls._instance is None:
                logger = logging.getLogger("ComponentManager")
                logger.info("Creating new ComponentManager instance via singleton")
                cls._instance = cls(event_bus)
            elif event_bus is not None and cls._instance.event_bus is None:
                logger = logging.getLogger("ComponentManager")
                logger.info("Setting event bus for existing ComponentManager instance")
                cls._instance.set_event_bus(event_bus)
            return cls._instance
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """Initialize component manager.
        
        Args:
            event_bus: Optional event bus for component communication
        """
        self.event_bus = event_bus
        self.logger = logging.getLogger("ComponentManager")
        self.components: Dict[str, Any] = {}
        self.initialized_components: Set[str] = set()
        self.shutdown_lock = threading.RLock()
        self.is_shutting_down = False
        self.is_running = True
        self._initialized = True
        self._event_handlers = {}
        self._tasks: List[asyncio.Task] = []
        
    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus for this component manager.
        
        Args:
            event_bus: Event bus for component communication
        """
        self.logger.info("Setting event bus for component manager")
        self.event_bus = event_bus
        
        # Also set the event bus for all registered components that support it
        for name, component in self.components.items():
            if hasattr(component, 'set_event_bus'):
                try:
                    component.set_event_bus(event_bus)
                    self.logger.info(f"Set event bus for component: {name}")
                except Exception as e:
                    self.logger.error(f"Error setting event bus for component {name}: {e}")

        
    def register(self, name: str, component: T) -> None:
        """Register a component.
        
        Args:
            name: Component name
            component: Component instance
        """
        try:
            if name in self.components:
                self.logger.warning(f"Component {name} already registered")
                return
                
            self.components[name] = component
            self.logger.info(f"Registered component: {name}")
            
        except Exception as e:
            self.logger.error(f"Error registering component {name}: {e}")
            raise
            
    def register_component(self, name: str, component: Any) -> None:
        """Alias for register method to maintain compatibility with existing code.
        
        Args:
            name: Component name
            component: Component instance
        """
        self.register(name, component)
            
    def get(self, name: str) -> Optional[Any]:
        """Get a registered component.
        
        Args:
            name: Component name
            
        Returns:
            Component instance or None if not found
        """
        return self.components.get(name)
        
    def get_component(self, name: str) -> Optional[Any]:
        """Alias for get() method to maintain compatibility with existing code.
        
        Args:
            name: Component name
            
        Returns:
            Component instance or None if not found
        """
        return self.get(name)
        
    def get_components(self) -> Dict[str, Any]:
        """Get all registered components.
        
        Returns:
            Dictionary of all component instances
        """
        return self.components
        
    async def discover_components(self) -> None:
        """Discover and initialize all components in the system.
        
        This method scans for available components and registers them with the system.
        It imports necessary modules and sets up the component hierarchy.
        """
        self.logger.info("Discovering components...")
        
        try:
            # Get the components directory path
            base_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(base_dir)
            components_dir = os.path.join(parent_dir, "components")
            
            if not os.path.exists(components_dir):
                self.logger.error(f"Components directory not found at: {components_dir}")
                return
                
            component_count = 0
            
            # Get a list of all Python files in the components directory
            component_files = [f for f in os.listdir(components_dir) 
                               if f.endswith('.py') and not f.startswith('__')]
            
            self.logger.info(f"Found {len(component_files)} component files")
            
            # Import each component
            for component_file in component_files:
                try:
                    # Convert filename to module name
                    module_name = os.path.splitext(component_file)[0]
                    full_module_name = f"components.{module_name}"
                    
                    # Import the module
                    self.logger.info(f"Importing component: {full_module_name}")
                    try:
                        module = importlib.import_module(full_module_name)
                        
                        # Look for component classes in the module
                        found_component = False
                        for name, obj in module.__dict__.items():
                            if isinstance(obj, type) and hasattr(obj, 'initialize'):
                                try:
                                    # Try to create an instance
                                    component_instance = obj()
                                    
                                    # Register the component
                                    component_name = f"{module_name}_{name.lower()}"
                                    self.register(component_name, component_instance)
                                    
                                    # Set event bus if available
                                    if hasattr(component_instance, 'set_event_bus') and self.event_bus:
                                        component_instance.set_event_bus(self.event_bus)
                                        
                                    component_count += 1
                                    self.logger.info(f"Registered component: {component_name}")
                                    found_component = True
                                    
                                except Exception as e:
                                    self.logger.error(f"Error instantiating component {name}: {e}")
                        
                        if not found_component:
                            # Try to import and initialize using a standard pattern
                            if hasattr(module, 'initialize_component'):
                                try:
                                    component = module.initialize_component(self.event_bus)
                                    if component:
                                        self.register(module_name, component)
                                        component_count += 1
                                        self.logger.info(f"Registered component via initialize_component: {module_name}")
                                except Exception as e:
                                    self.logger.error(f"Error initializing component {module_name}: {e}")
                    except Exception as e:
                        self.logger.error(f"Error importing module {full_module_name}: {e}")
                        
                except Exception as e:
                    self.logger.error(f"Error processing component {component_file}: {e}")
            
            self.logger.info(f"Discovered and registered {component_count} components")
            
        except Exception as e:
            self.logger.error(f"Error in discover_components: {e}")
            self.logger.error(traceback.format_exc())
    
    def _ensure_component_attributes(self, component, name):
        """Ensure the component has all required attributes for proper operation.
        
        Args:
            component: Component instance
            name: Component name
        """
        # Add standard methods/attributes if they don't exist
        if not hasattr(component, 'cleanup') and hasattr(component, '__dict__'):
            component.cleanup = lambda: None
            self.logger.debug(f"Added default cleanup method to component {name}")
            
        if not hasattr(component, 'is_running') and hasattr(component, '__dict__'):
            component.is_running = True
            self.logger.debug(f"Added is_running attribute to component {name}")
            
    async def initialize_all_components(self, config=None) -> bool:
        """Initialize all registered components.
        
        Args:
            config: Optional configuration dictionary
            
        Returns:
            True if all components initialized successfully
        """
        try:
            for name, component in self.components.items():
                self.logger.info(f"Initializing component: {name}")
                
                # Ensure the component has required attributes for cleanup
                self._ensure_component_attributes(component, name)
                
                if hasattr(component, 'initialize'):
                    # Some components might have async initialize methods
                    if asyncio.iscoroutinefunction(component.initialize):
                        result = await component.initialize()
                    else:
                        result = component.initialize()
                        
                    # Track successful initialization
                    if result is not False:  # Allow None or True as success
                        self.initialized_components.add(name)
                        
                    self.logger.info(f"Initialized component: {name}")
                else:
                    self.logger.info(f"Component {name} has no initialize method")
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing components: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def initialize(self, config=None, **kwargs) -> bool:
        """Initialize all registered components.
        
        Args:
            config: Optional configuration dictionary
            **kwargs: Additional keyword arguments to pass to component initialize methods
            
        Returns:
            True if all components initialized successfully
        """
        try:
            success = True
            self.logger.info(f"Initializing {len(self.components)} components")
            
            for name, component in self.components.items():
                try:
                    # Ensure the component has required attributes for cleanup
                    self._ensure_component_attributes(component, name)
                    
                    # Try different initialization methods
                    if hasattr(component, 'initialize') and callable(component.initialize):
                        self.logger.debug(f"Initializing component {name} with initialize() method")
                        if asyncio.iscoroutinefunction(component.initialize):
                            result = await component.initialize(config=config, **kwargs)
                        else:
                            result = component.initialize(config=config, **kwargs)
                            
                        # Track successful initialization
                        if result is not False:  # Allow None or True as success
                            self.initialized_components.add(name)
                            
                    elif hasattr(component, 'init') and callable(component.init):
                        self.logger.debug(f"Initializing component {name} with init() method")
                        if asyncio.iscoroutinefunction(component.init):
                            result = await component.init(config=config, **kwargs)
                        else:
                            result = component.init(config=config, **kwargs)
                            
                        # Track successful initialization
                        if result is not False:  # Allow None or True as success
                            self.initialized_components.add(name)
                    else:
                        self.logger.debug(f"Component {name} has no initialization method")
                        
                    self.logger.info(f"Initialized component: {name}")
                    
                except Exception as e:
                    self.logger.error(f"Error initializing component {name}: {e}")
                    success = False
                    
            return success
            
        except Exception as e:
            self.logger.error(f"Error in component initialization process: {e}")
            return False
