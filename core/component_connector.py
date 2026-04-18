#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Component Connector Module

This module provides utilities to connect components to the event bus
and ensure proper system integration for all Kingdom AI modules.
"""

import logging
import importlib
import traceback

# Set up logging
logger = logging.getLogger("kingdom_ai")

class ComponentConnector:
    """
    Utility class to manage component connections to the event bus and
    provide fallback restoration mechanisms for system integrity.
    """
    
    def __init__(self, event_bus=None):
        """
        Initialize the component connector.
        
        Args:
            event_bus: The event bus to connect components to
        """
        self.event_bus = event_bus
        self.components = {}
        self.initialized_count = 0
        self.expected_count = 90  # Total expected components in the system
    
    async def connect_component(self, component, name=None):
        """
        Connect a component to the event bus.
        
        Args:
            component: The component to connect
            name: Optional name to register the component as
            
        Returns:
            bool: True if connected successfully
        """
        try:
            # Get component name if not provided
            component_name = name or getattr(component, "name", str(component.__class__.__name__))
            
            # Register component with event bus
            if self.event_bus:
                if hasattr(component, "register_event_bus"):
                    component.register_event_bus(self.event_bus)
                    logger.info(f"Connected component {component_name} to event bus via register_event_bus")
                elif hasattr(component, "set_event_bus"):
                    component.set_event_bus(self.event_bus)
                    logger.info(f"Connected component {component_name} to event bus via set_event_bus")
                elif hasattr(component, "event_bus") and not getattr(component, "event_bus", None):
                    component.event_bus = self.event_bus
                    logger.info(f"Connected component {component_name} to event bus via direct assignment")
                else:
                    logger.warning(f"No method found to connect component {component_name} to event bus")
                    return False
                
                # Track the component
                self.components[component_name] = component
                self.initialized_count += 1
                return True
            else:
                logger.warning("No event bus available to connect components")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting component {name}: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    async def restore_component(self, module_name, class_name=None, config=None):
        """
        Attempt to restore a component from one of several possible sources:
        1. From a fix_{module_name} module if available
        2. From a minimal implementation if required
        
        Args:
            module_name: The name of the module to restore
            class_name: Optional class name to restore
            config: Optional configuration for the component
            
        Returns:
            The restored component or None if restoration failed
        """
        try:
            # Determine the class name if not provided
            if not class_name:
                class_name = ''.join(word.capitalize() for word in module_name.split('_'))
            
            # Try to import from fix_{module_name} first
            fix_module_name = f"fix_{module_name}"
            try:
                fix_module = importlib.import_module(fix_module_name)
                if hasattr(fix_module, class_name):
                    logger.info(f"Restored {class_name} from {fix_module_name}")
                    component_class = getattr(fix_module, class_name)
                    component = component_class(event_bus=self.event_bus, config=config)
                    await self.connect_component(component)
                    return component
            except ImportError:
                logger.info(f"No fix module found for {module_name}, trying other methods")
            
            # Try to create a minimal implementation
            logger.info(f"Creating minimal implementation for {class_name}")
            
            # Create a minimal component with basic required methods
            minimal_component = type(class_name, (), {
                'name': module_name,
                'initialized': True,
                'register_event_bus': lambda self, bus: setattr(self, 'event_bus', bus),
                'event_bus': None,
                '__init__': lambda self, **kwargs: setattr(self, 'event_bus', kwargs.get('event_bus'))
            })()
            
            # Connect the minimal component
            await self.connect_component(minimal_component)
            logger.warning(f"Created minimal implementation for {class_name}")
            return minimal_component
            
        except Exception as e:
            logger.error(f"Failed to restore component {module_name}: {e}")
            logger.debug(traceback.format_exc())
            return None
    
    async def verify_connections(self):
        """
        Verify that all components are properly connected to the event bus.
        
        Returns:
            int: Number of verified connections
        """
        verified_count = 0
        for name, component in self.components.items():
            try:
                if hasattr(component, "event_bus") and component.event_bus == self.event_bus:
                    verified_count += 1
                    logger.info(f"Verified connection for component {name}")
                else:
                    # Try to fix the connection
                    if hasattr(component, "register_event_bus"):
                        component.register_event_bus(self.event_bus)
                        verified_count += 1
                        logger.info(f"Fixed connection for component {name}")
                    elif hasattr(component, "event_bus"):
                        component.event_bus = self.event_bus
                        verified_count += 1
                        logger.info(f"Fixed connection for component {name}")
            except Exception as e:
                logger.error(f"Error verifying connection for {name}: {e}")
        
        logger.info(f"Verified {verified_count}/{len(self.components)} event bus connections")
        return verified_count

# Function to restore all core components and connect them to the event bus
async def restore_all_components(event_bus):
    """
    Restore all core components and connect them to the event bus.
    
    Args:
        event_bus: The event bus to connect components to
        
    Returns:
        Dict: Dictionary of restored components
    """
    connector = ComponentConnector(event_bus)
    components = {}
    
    # Define core components to restore
    core_components = [
        "trading_system",
        "mining_dashboard",
        "meta_learning",
        "code_generator",
        "blockchain",
        "portfolio_analytics",
        "visualization",
        "nlp",
        "market_analysis"
    ]
    
    # Restore each core component
    for component_name in core_components:
        try:
            logger.info(f"Restoring {component_name}...")
            component = await connector.restore_component(component_name)
            if component:
                components[component_name] = component
                logger.info(f"{component_name} restored and connected to event bus")
            else:
                logger.warning(f"Could not restore {component_name}")
        except Exception as e:
            logger.error(f"Error restoring {component_name}: {e}")
    
    # Verify all connections
    await connector.verify_connections()
    
    return components
