#!/usr/bin/env python3
"""
Kingdom AI - Component Initialization Helper

This module provides advanced component initialization with dependency management,
ordering, validation, and error recovery for the Kingdom AI system.

Key features:
1. Dependency graph management
2. Topological sorting for correct initialization order
3. Circular dependency detection
4. Component state validation
5. Initialization retries with backoff

Author: Kingdom AI Development Team
Date: 2025-04-21
"""

import logging
import asyncio
import inspect
from typing import Dict, List, Any, Optional, Union

class ComponentInitializationHelper:
    """
    Advanced component initialization with dependency management, ordering,
    validation, and error recovery for the Kingdom AI system.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the component initialization helper."""
        self.name = "component_helper"
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logging.getLogger("KingdomAI.ComponentHelper")
        self.initialized_components = set()
        self.component_instances = {}
        self.component_dependencies = {}
        self.component_dependents = {}
        self.initialization_attempts = {}
        self.max_retry_attempts = 3
        self.retry_delay = 1.0  # Initial delay in seconds
        
        # Status tracking
        self.total_components = 0
        self.successful_components = 0
        self.failed_components = 0
        
        self.logger.info("Component initialization helper initialized")
    
    def register_component(self, name: str, instance: Any):
        """Register a component instance."""
        self.component_instances[name] = instance
        self.logger.debug(f"Registered component: {name}")
    
    def register_dependency(self, component: str, depends_on: Union[str, List[str]]):
        """Register a dependency relationship between components."""
        if isinstance(depends_on, str):
            depends_on = [depends_on]
            
        if component not in self.component_dependencies:
            self.component_dependencies[component] = set()
            
        for dependency in depends_on:
            self.component_dependencies[component].add(dependency)
            
            if dependency not in self.component_dependents:
                self.component_dependents[dependency] = set()
                
            self.component_dependents[dependency].add(component)
            
        self.logger.debug(f"Registered dependencies for {component}: {depends_on}")
    
    def is_initialized(self, component_name: str) -> bool:
        """Check if a component is initialized."""
        if component_name not in self.component_instances:
            return False
            
        component = self.component_instances[component_name]
        return (hasattr(component, 'is_initialized') and component.is_initialized) or                (hasattr(component, 'initialized') and component.initialized)
    
    def detect_circular_dependencies(self) -> Optional[List[str]]:
        """Detect circular dependencies in the component graph."""
        visited = {}  # 0: not visited, 1: in progress, 2: done
        path = []
        result = []

        def visit(node):
            if node in visited:
                if visited[node] == 1:  # In progress - cycle detected
                    cycle_start = path.index(node)
                    result.append(path[cycle_start:] + [node])
                return visited[node] == 2  # Return True if already processed

            visited[node] = 1  # Mark as in progress
            path.append(node)

            # Visit dependencies
            if node in self.component_dependencies:
                for dep in self.component_dependencies[node]:
                    if dep not in visited:
                        if not visit(dep):
                            return False
                    elif visited[dep] == 1:  # Cycle detected
                        cycle_start = path.index(dep)
                        result.append(path[cycle_start:] + [dep])
                        return False

            # Mark as done and remove from path
            visited[node] = 2
            path.pop()
            return True

        for node in self.component_dependencies:
            if node not in visited:
                visit(node)

        return result if result else None
    
    def topological_sort(self) -> List[str]:
        """
        Sort components by dependencies using topological sort.
        Components with no dependencies go first.
        """
        # Check for circular dependencies
        cycles = self.detect_circular_dependencies()
        if cycles:
            for cycle in cycles:
                self.logger.warning(f"Circular dependency detected: {' -> '.join(cycle)}")
            self.logger.warning("Breaking circular dependencies by prioritizing infrastructure components")
        
        # Create a copy of dependencies to work with
        dependencies = {k: set(v) for k, v in self.component_dependencies.items()}
        
        # Ensure all components are in the dependency dict
        for component in self.component_instances:
            if component not in dependencies:
                dependencies[component] = set()
        
        # Track visited nodes and result
        visited = set()
        result = []
        
        # Start with infrastructure/core components that must be initialized first
        essential_components = [c for c in self.component_instances.keys() 
                              if c in ["event_bus", "config_manager", "logger_manager", 
                                      "redis_connector", "thoth_ai"]]
        
        for component in essential_components:
            if component in dependencies:
                dependencies[component] = set()  # Remove dependencies for essential components
        
        # Helper function for depth-first search
        def visit(node):
            if node in visited:
                return
            
            visited.add(node)
            
            # Visit all dependencies first
            if node in dependencies:
                for dep in list(dependencies[node]):
                    if dep not in visited:
                        visit(dep)
            
            result.append(node)
        
        # First visit all essential components
        for component in essential_components:
            if component not in visited:
                visit(component)
        
        # Then visit remaining components
        for component in list(dependencies.keys()):
            if component not in visited:
                visit(component)
        
        return result
    
    async def initialize_components_in_order(self, components_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize components in dependency order.
        
        Args:
            components_dict: Dictionary of component name to component instance
            
        Returns:
            Dictionary of initialized components
        """
        self.component_instances = components_dict
        self.total_components = len(components_dict)
        
        # Analyze component dependencies
        self.analyze_component_dependencies()
        
        # Get initialization order
        init_order = self.topological_sort()
        
        # Log initialization order
        self.logger.info(f"Component initialization order: {', '.join(init_order)}")
        
        # Initialize components in order
        initialized_components = {}
        
        for component_name in init_order:
            if component_name not in components_dict:
                self.logger.warning(f"Component {component_name} not found in components dictionary")
                continue
                
            component = components_dict[component_name]
            
            # Check if all dependencies are initialized
            dependencies_ok = True
            if component_name in self.component_dependencies:
                for dep_name in self.component_dependencies[component_name]:
                    if dep_name not in initialized_components:
                        self.logger.warning(f"Dependency {dep_name} for {component_name} not initialized")
                        dependencies_ok = False
            
            if not dependencies_ok:
                self.logger.warning(f"Skipping initialization of {component_name} due to unmet dependencies")
                continue
            
            # Initialize the component
            initialized = await self.initialize_component_with_retry(component_name, component)
            
            if initialized:
                initialized_components[component_name] = component
                self.initialized_components.add(component_name)
                self.successful_components += 1
                
                # Publish event via event bus
                if self.event_bus and hasattr(self.event_bus, 'publish'):
                    try:
                        await self.event_bus.publish(
                            "system.component.initialized", 
                            {"component": component_name, "success": True}
                        )
                    except Exception as e:
                        self.logger.error(f"Failed to publish initialization event: {str(e)}")
            else:
                self.failed_components += 1
                self.logger.error(f"Failed to initialize component: {component_name}")
                
                # Publish event via event bus
                if self.event_bus and hasattr(self.event_bus, 'publish'):
                    try:
                        await self.event_bus.publish(
                            "system.component.initialization_failed", 
                            {"component": component_name, "error": "Initialization failed"}
                        )
                    except Exception as e:
                        self.logger.error(f"Failed to publish initialization failure event: {str(e)}")
        
        # Log initialization summary
        self.logger.info(f"Component initialization complete: {self.successful_components}/{self.total_components} successful")
        
        if self.failed_components > 0:
            self.logger.warning(f"Failed to initialize {self.failed_components} components")
            for component_name in components_dict:
                if component_name not in initialized_components:
                    self.logger.warning(f"  - {component_name}")
        
        return initialized_components
    
    async def initialize_component_with_retry(self, component_name: str, component: Any) -> bool:
        """Initialize a component with retry mechanism."""
        if not hasattr(component, 'initialize') and not hasattr(component, 'initialize_sync'):
            self.logger.warning(f"Component {component_name} has no initialize method")
            return False
            
        if component_name not in self.initialization_attempts:
            self.initialization_attempts[component_name] = 0
            
        while self.initialization_attempts[component_name] < self.max_retry_attempts:
            try:
                self.logger.info(f"Initializing component: {component_name} (attempt {self.initialization_attempts[component_name] + 1})")
                
                if hasattr(component, 'initialize'):
                    if inspect.iscoroutinefunction(component.initialize):
                        await component.initialize()
                    else:
                        component.initialize()
                elif hasattr(component, 'initialize_sync'):
                    component.initialize_sync()
                
                # Verify initialization status
                if self.is_initialized(component_name):
                    self.logger.info(f"Component {component_name} initialized successfully")
                    return True
                else:
                    self.logger.warning(f"Component {component_name} initialize() method ran but is_initialized is False")
            except Exception as e:
                self.logger.error(f"Error initializing {component_name}: {str(e)}")
                
            # Increment attempt count and delay before retry
            self.initialization_attempts[component_name] += 1
            if self.initialization_attempts[component_name] < self.max_retry_attempts:
                delay = self.retry_delay * (2 ** (self.initialization_attempts[component_name] - 1))  # Exponential backoff
                self.logger.info(f"Retrying initialization of {component_name} in {delay:.1f} seconds")
                await asyncio.sleep(delay)
        
        self.logger.error(f"Failed to initialize {component_name} after {self.max_retry_attempts} attempts")
        return False
    
    def analyze_component_dependencies(self):
        """Analyze component dependencies based on initialization methods."""
        for component_name, component in self.component_instances.items():
            # Skip analysis if dependencies already defined
            if component_name in self.component_dependencies:
                continue
                
            # Initialize dependencies set
            self.component_dependencies[component_name] = set()
            
            # Check initialize method signature for dependencies
            initialize_method = None
            if hasattr(component, 'initialize'):
                initialize_method = component.initialize
            elif hasattr(component, 'initialize_sync'):
                initialize_method = component.initialize_sync
                
            if initialize_method:
                try:
                    # Inspect method signature
                    sig = inspect.signature(initialize_method)
                    
                    # Check for components passed as parameters
                    for param_name, param in sig.parameters.items():
                        if param_name not in ['self', 'cls', 'args', 'kwargs']:
                            # Parameter might indicate a dependency
                            for potential_dep in self.component_instances:
                                if potential_dep in param_name.lower():
                                    self.component_dependencies[component_name].add(potential_dep)
                                    self.logger.debug(f"Detected dependency: {component_name} -> {potential_dep}")
                except Exception as e:
                    self.logger.warning(f"Error analyzing dependencies for {component_name}: {str(e)}")
            
            # Check for explicit dependencies attribute
            if hasattr(component, 'dependencies'):
                deps = getattr(component, 'dependencies')
                if isinstance(deps, (list, tuple, set)):
                    for dep in deps:
                        if isinstance(dep, str):
                            self.component_dependencies[component_name].add(dep)
                            self.logger.debug(f"Found explicit dependency: {component_name} -> {dep}")
            
            # Check for references to other components in __init__
            if hasattr(component, '__init__'):
                try:
                    init_source = inspect.getsource(component.__init__)
                    for potential_dep in self.component_instances:
                        # Look for patterns like self.component_name or self._component_name
                        pattern = r'self[._]' + potential_dep
                        if re.search(pattern, init_source):
                            self.component_dependencies[component_name].add(potential_dep)
                            self.logger.debug(f"Detected init dependency: {component_name} -> {potential_dep}")
                except Exception:
                    pass  # Ignore errors in source inspection
    
    def initialize_component_sync(self, component_name: str, component: Any) -> bool:
        """Initialize a component synchronously."""
        if hasattr(component, 'initialize_sync'):
            try:
                component.initialize_sync()
                return True
            except Exception as e:
                self.logger.error(f"Error in synchronous initialization of {component_name}: {str(e)}")
                return False
        elif hasattr(component, 'initialize') and not inspect.iscoroutinefunction(component.initialize):
            try:
                component.initialize()
                return True
            except Exception as e:
                self.logger.error(f"Error in synchronous initialization of {component_name}: {str(e)}")
                return False
        else:
            self.logger.warning(f"Component {component_name} has no synchronous initialize method")
            return False
    
    def get_component_status(self) -> Dict[str, Any]:
        """Get the current status of component initialization."""
        return {
            "total": self.total_components,
            "successful": self.successful_components,
            "failed": self.failed_components,
            "initialized": list(self.initialized_components),
            "pending": [c for c in self.component_instances if c not in self.initialized_components]
        }

# Helper function to safely initialize components in order
async def initialize_components_with_dependencies(components_dict, event_bus=None, config=None):
    """
    Initialize components in the correct order based on their dependencies.
    
    Args:
        components_dict: Dictionary of component name to component instance
        event_bus: Event bus instance for component communication
        config: Configuration dictionary
        
    Returns:
        Dictionary of initialized components
    """
    helper = ComponentInitializationHelper(event_bus, config)
    return await helper.initialize_components_in_order(components_dict)

def create_dependency_graph(components_dict):
    """Create a dependency graph visualization for components."""
    try:
        import networkx as nx
        import matplotlib.pyplot as plt
        
        G = nx.DiGraph()
        
        # Add nodes
        for name in components_dict:
            G.add_node(name)
        
        # Add edges based on component dependencies
        helper = ComponentInitializationHelper()
        helper.component_instances = components_dict
        helper.analyze_component_dependencies()
        
        for component, deps in helper.component_dependencies.items():
            for dep in deps:
                if dep in components_dict:
                    G.add_edge(component, dep)
        
        # Create plot
        plt.figure(figsize=(12, 10))
        pos = nx.spring_layout(G, seed=42)
        nx.draw(G, pos, with_labels=True, node_color='lightblue', 
                node_size=1500, arrowsize=20, font_size=10)
        
        # Save visualization
        plt.savefig("component_dependencies.png")
        logging.info("Component dependency graph created at component_dependencies.png")
        
        return True
    except ImportError:
        logging.warning("networkx or matplotlib not available, skipping dependency graph visualization")
        return False
