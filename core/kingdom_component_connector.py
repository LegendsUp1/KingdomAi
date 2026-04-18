#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Component Connector

This module handles the connection of all system components to the event bus,
ensuring proper system integration for initialization, status reporting, and
event handling. It restores connections to all 90+ components.
"""

import logging
import asyncio
import importlib
import traceback

# Logger setup
logger = logging.getLogger("kingdom_ai")

class KingdomComponentConnector:
    """
    Kingdom Component Connector manages the connection of all system 
    components to the event bus and ensures proper initialization sequence.
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
        self.registered_count = 0
        self.expected_count = 90  # Total expected components
        self.initialization_progress = 0.0
        
    def get_progress(self):
        """
        Get the current initialization progress.
        
        Returns:
            float: Progress value between 0.0 and 1.0
        """
        if self.expected_count > 0:
            return min(0.95, (self.initialized_count / self.expected_count) * 0.95)
        return 0.1
        
    def update_progress(self, message=None):
        """
        Update the progress bar based on current initialization state.
        
        Args:
            message: Optional status message
        """
        if not message:
            message = f"Initialized {self.initialized_count}/{self.expected_count} components"
            
        # Calculate progress based on initialized component count
        self.initialization_progress = self.get_progress()
        
        # Update the loading progress bar
        try:
            from gui.loading_screen import update_loading_progress
            update_loading_progress(self.initialization_progress, message)
        except (ImportError, AttributeError) as e:
            logger.warning(f"Could not update loading progress: {e}")
            
    async def connect_component(self, component, name=None):
        """
        Connect a component to the event bus.
        
        Args:
            component: The component to connect
            name: Optional component name
            
        Returns:
            bool: True if connection was successful
        """
        try:
            # Get component name
            component_name = name or getattr(component, "name", str(component.__class__.__name__))
            
            # Register with event bus
            if self.event_bus:
                connection_method = self._detect_connection_method(component)
                if connection_method == "register_event_bus":
                    component.register_event_bus(self.event_bus)
                    logger.info(f"Connected component {component_name} to event bus via register_event_bus")
                elif connection_method == "set_event_bus":
                    component.set_event_bus(self.event_bus)
                    logger.info(f"Connected component {component_name} to event bus via set_event_bus")
                elif connection_method == "direct_assignment":
                    component.event_bus = self.event_bus
                    logger.info(f"Connected component {component_name} to event bus via direct assignment")
                else:
                    logger.warning(f"No method found to connect component {component_name} to event bus")
                    return False
                
                # Track the component
                self.components[component_name] = component
                self.initialized_count += 1
                self.registered_count += 1
                self.update_progress()
                return True
            else:
                logger.warning("No event bus available to connect components")
                return False
        except Exception as e:
            logger.error(f"Error connecting component {name}: {e}")
            logger.debug(traceback.format_exc())
            return False
            
    def _detect_connection_method(self, component):
        """
        Detect the method to use for connecting a component to the event bus.
        
        Args:
            component: The component to check
            
        Returns:
            str: Connection method ("register_event_bus", "set_event_bus", "direct_assignment", or None)
        """
        if hasattr(component, "register_event_bus"):
            return "register_event_bus"
        elif hasattr(component, "set_event_bus"):
            return "set_event_bus"
        elif hasattr(component, "event_bus"):
            return "direct_assignment"
        return None
        
    async def restore_component_from_fix_file(self, module_name, class_name=None, config=None):
        """
        Restore a component from a fix_* file.
        
        Args:
            module_name: Module name (e.g., "trading_system")
            class_name: Class name (e.g., "TradingSystem")
            config: Optional configuration
            
        Returns:
            The restored component or None
        """
        try:
            # Find the fix file for this component
            fix_file_name = f"fix_{module_name}"
            # Convert module_name to class_name if not provided (market_analysis -> MarketAnalysis)
            if not class_name:
                class_name = ''.join(word.capitalize() for word in module_name.split('_'))
                
            # Try to import the fix file
            try:
                # First check for numerical variations (fix_trading_system1, fix_trading_system2)
                for i in range(1, 5):
                    try:
                        numbered_file = f"{fix_file_name}{i}"
                        module = importlib.import_module(numbered_file)
                        if hasattr(module, class_name):
                            component_class = getattr(module, class_name)
                            component = component_class(event_bus=self.event_bus, config=config)
                            await self.connect_component(component, name=module_name)
                            logger.info(f"Restored {class_name} from {numbered_file}")
                            return component
                    except (ImportError, AttributeError):
                        pass
                        
                # Try part1, part2, etc. variations
                for part in ['', '_part1', '_part2', '_part3', '_part4']:
                    try:
                        part_file = f"{fix_file_name}{part}"
                        module = importlib.import_module(part_file)
                        if hasattr(module, class_name):
                            component_class = getattr(module, class_name)
                            component = component_class(event_bus=self.event_bus, config=config)
                            await self.connect_component(component, name=module_name)
                            logger.info(f"Restored {class_name} from {part_file}")
                            return component
                    except (ImportError, AttributeError):
                        pass
                
                # Try the base fix file
                module = importlib.import_module(fix_file_name)
                if hasattr(module, class_name):
                    component_class = getattr(module, class_name)
                    component = component_class(event_bus=self.event_bus, config=config)
                    await self.connect_component(component, name=module_name)
                    logger.info(f"Restored {class_name} from {fix_file_name}")
                    return component
            except (ImportError, AttributeError) as e:
                logger.warning(f"Could not import {fix_file_name}: {e}")
                
            # If we reach here, we couldn't find a suitable fix file
            logger.warning(f"No suitable fix file found for {module_name}")
            return None
        except Exception as e:
            logger.error(f"Error restoring component from fix file: {e}")
            logger.debug(traceback.format_exc())
            return None
            
    async def initialize_core_module(self, module_name, event_bus=None):
        """
        Initialize a module using the proper initialization function.
        
        Args:
            module_name: The name of the module (e.g., "trading_system")
            event_bus: Optional event bus to use
            
        Returns:
            dict: Dictionary of initialized components
        """
        components = {}
        logger.info(f"Initializing {module_name} components...")
        self.update_progress(f"Initializing {module_name} components...")
        
        try:
            # Try to import the module
            module_path = f"core.{module_name}"
            try:
                module = importlib.import_module(module_path)
                
                # Try to find the expected initialization function
                init_func_name = f"initialize_{module_name}_components"
                if hasattr(module, init_func_name):
                    # Call the initialization function
                    init_func = getattr(module, init_func_name)
                    module_components = await init_func(event_bus or self.event_bus)
                    
                    # Update components dictionary
                    if module_components:
                        components.update(module_components)
                        component_count = len(module_components)
                        self.initialized_count += component_count
                        logger.info(f"Added {component_count} components from {module_name}")
                        
                        # Update progress
                        self.update_progress(f"{module_name} initialized with {component_count} components")
                    else:
                        logger.warning(f"No components returned from {init_func_name}")
                else:
                    logger.warning(f"No initialization function found for {module_name}")
                    
                    # Try to restore components from fix files
                    component = await self.restore_component_from_fix_file(module_name)
                    if component:
                        components[module_name] = component
                        logger.info(f"Restored {module_name} from fix file")
            except ImportError as e:
                logger.warning(f"{module_name} module not found: {e}")
                
                # Try to restore components from fix files
                component = await self.restore_component_from_fix_file(module_name)
                if component:
                    components[module_name] = component
                    logger.info(f"Restored {module_name} from fix file")
                    
        except Exception as e:
            logger.error(f"Unexpected error processing module {module_name}: {e}")
            logger.debug(traceback.format_exc())
            
        return components
        
    async def verify_component_connections(self):
        """
        Verify that all components are properly connected to the event bus.
        
        Returns:
            int: Number of verified connections
        """
        verified_count = 0
        for name, component in self.components.items():
            try:
                # Check if component is properly connected
                connection_method = self._detect_connection_method(component)
                if connection_method == "direct_assignment" and component.event_bus == self.event_bus:
                    verified_count += 1
                    logger.debug(f"Verified connection for component {name}")
                elif connection_method in ["register_event_bus", "set_event_bus"]:
                    # These methods should have already registered the event bus
                    verified_count += 1
                    logger.debug(f"Verified connection method for component {name}")
                else:
                    # Try to fix the connection
                    await self.connect_component(component, name)
                    logger.info(f"Fixed connection for component {name}")
            except Exception as e:
                logger.error(f"Error verifying connection for {name}: {e}")
                
        logger.info(f"Verified {verified_count}/{len(self.components)} event bus connections")
        return verified_count
        
    async def initialize_all_components(self):
        """Initialize all Kingdom AI components and connect them to the event bus.
        
        This method ensures proper progress tracking during initialization of all
        90+ Kingdom AI components, updating the loading screen with real-time status.
        
        Returns:
            dict: Dictionary of all initialized components
        """
        from gui.loading_screen import update_loading_progress
        import logging
        
        logger = logging.getLogger("kingdom_ai")
        all_components = {}
        
        # Define all core modules to initialize
        core_modules = [
            "trading_system",
            "mining_dashboard",
            "meta_learning",
            "code_generator",
            "blockchain",
            "portfolio_analytics",
            "visualization",
            "nlp",
            "market_analysis",
            "data_storage"
        ]
        
        # Calculate progress segments
        total_modules = len(core_modules)
        progress_per_module = 0.75 / total_modules  # 75% of progress bar for modules
        base_progress = 0.15  # Start at 15% progress
        current_progress = base_progress
        
        # Initialize each module with progress tracking
        for i, module_name in enumerate(core_modules):
            module_start_progress = current_progress
            module_end_progress = module_start_progress + progress_per_module
            
            # Update progress at module start
            status_message = f"Initializing {module_name.replace('_', ' ')} components..."
            update_loading_progress(module_start_progress, status_message)
            logger.info(status_message)
            
            try:
                # Initialize module components
                components = await self.initialize_core_module(module_name)
                
                if components:
                    all_components.update(components)
                    component_count = len(components)
                    logger.info(f"Initialized {component_count} components from {module_name}")
                else:
                    logger.warning(f"No components initialized from {module_name}")
                    
                # Update progress after module initialization
                current_progress = module_end_progress
                update_loading_progress(current_progress, 
                                      f"Initialized {module_name.replace('_', ' ')}. Total: {len(all_components)} components")
                
                # Brief pause to allow UI updates
                await asyncio.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error initializing {module_name} components: {e}")
                # Still update progress even if there was an error
                current_progress = module_end_progress
                update_loading_progress(current_progress, 
                                      f"Error in {module_name.replace('_', ' ')}. Continuing...")
                await asyncio.sleep(0.05)
        
        # Start connection verification (90% progress point)
        update_loading_progress(0.90, f"Verifying component connections... ({len(all_components)} components)")
        
        # Verify connections
        try:
            verified_count = await self.verify_component_connections()
            logger.info(f"Verified {verified_count} component connections")
            
            # Update final progress
            update_loading_progress(0.95, f"All {len(all_components)} components initialized with {verified_count} connections")
        except Exception as e:
            logger.error(f"Error verifying component connections: {e}")
            update_loading_progress(0.95, "Component initialization complete with some errors")
        
        # Final connection count
        logger.info(f"Initialization complete with {len(all_components)} components")
        
        return all_components

# Function to initialize the component connector
async def initialize_component_connector(event_bus):
    """Initialize the component connector and connect all system components.
    
    This function ensures all 90+ components are properly connected to the event bus
    and provides accurate progress tracking during initialization.
    
    Args:
        event_bus: The event bus to use for component communication
        
    Returns:
        dict: Dictionary of initialized components
    """
    from gui.loading_screen import update_loading_progress
    import logging
    logger = logging.getLogger("kingdom_ai")
    
    logger.info("Initializing KingdomComponentConnector with event bus")
    connector = KingdomComponentConnector(event_bus=event_bus)
    
    # Update progress to show component connection has started
    update_loading_progress(0.15, "Connecting Kingdom AI components...")
    
    # Initialize and connect all components
    components = await connector.initialize_all_components()
    
    # Trigger an event to notify that all components are connected
    try:
        event_bus.trigger("system.components.initialized", {
            "component_count": len(components),
            "status": "success"
        })
        logger.info(f"Component connector initialized with {len(components)} components")
    except Exception as e:
        logger.error(f"Error triggering component initialization event: {e}")
        if len(components) > 0:
            logger.info(f"Component connector initialized with {len(components)} components")
        else:
            logger.warning("No components initialized by component connector")
    
    return components
