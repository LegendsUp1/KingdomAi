"""
Kingdom AI Initialization Tracker
Provides precise component initialization tracking with real-time progress reporting
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Callable

logger = logging.getLogger("KingdomAI.InitTracker")

class InitializationTracker:
    """
    Tracks the initialization progress of all Kingdom AI components.
    Provides accurate progress reporting and dependency management.
    """
    
    def __init__(self, total_components: int, progress_callback: Callable[[float, str], None]):
        """
        Initialize the tracker.
        
        Args:
            total_components: Total number of components to track
            progress_callback: Function to call to update progress (takes progress[0-1] and status message)
        """
        self.total_components = total_components
        self.component_weights = {}
        self.component_status = {}
        self.component_dependencies = {}
        self.progress_callback = progress_callback
        self.initialized_count = 0
        self.total_weight = 0.0
        self.completed_weight = 0.0
        self.start_time = time.time()
        logger.info(f"Initialization tracker created for {total_components} components")
        
    def register_component(self, name: str, weight: float = 1.0, dependencies: List[str] = None) -> bool:
        """
        Register a component to be tracked.
        
        Args:
            name: Component name
            weight: Component weight in progress calculation (higher means more impact)
            dependencies: List of component names this component depends on
            
        Returns:
            True if registered successfully
        """
        if name in self.component_status:
            logger.warning(f"Component {name} already registered")
            return False
        
        self.component_weights[name] = weight
        self.component_status[name] = {
            "initialized": False,
            "progress": 0.0,
            "start_time": None,
            "end_time": None,
            "error": None,
            "init_duration": None
        }
        self.component_dependencies[name] = dependencies or []
        self.total_weight += weight
        
        logger.info(f"Registered component: {name} (weight: {weight}, dependencies: {dependencies})")
        return True
        
    def update_component_progress(self, name: str, progress: float, status_message: str = None) -> None:
        """
        Update a component's initialization progress.
        
        Args:
            name: Component name
            progress: Progress percentage (0.0 to 1.0)
            status_message: Optional status message to display
        """
        if name not in self.component_status:
            logger.error(f"Cannot update progress for unregistered component: {name}")
            return
        
        component = self.component_status[name]
        
        # Record start time on first progress update
        if component["start_time"] is None:
            component["start_time"] = time.time()
            
        # Normalize progress value
        progress = max(0.0, min(1.0, progress))
        
        # Only update if new progress is higher
        if progress > component["progress"]:
            old_progress = component["progress"]
            component["progress"] = progress
            
            # Calculate how much weight to add to the total
            progress_delta = progress - old_progress
            weight_contribution = progress_delta * self.component_weights[name]
            self.completed_weight += weight_contribution
            
            # Calculate the overall progress percentage
            overall_progress = min(0.99, self.completed_weight / self.total_weight)
            
            # Call the progress callback with the updated progress
            message = status_message or f"Initializing {name}: {int(progress * 100)}%"
            self.progress_callback(overall_progress, message)
            
            logger.debug(f"Component {name} progress: {progress:.2f}, Overall: {overall_progress:.2f}")
    
    def mark_component_initialized(self, name: str, success: bool = True, error: str = None) -> None:
        """
        Mark a component as fully initialized.
        
        Args:
            name: Component name
            success: Whether initialization was successful
            error: Error message if initialization failed
        """
        if name not in self.component_status:
            logger.error(f"Cannot mark unregistered component as initialized: {name}")
            return
        
        component = self.component_status[name]
        
        # Skip if already marked as initialized
        if component["initialized"]:
            return
            
        # Record component status
        component["initialized"] = success
        component["end_time"] = time.time()
        component["error"] = error
        
        if component["start_time"]:
            component["init_duration"] = component["end_time"] - component["start_time"]
        
        # Update to 100% progress if successful
        if success:
            # Calculate the weight to add by taking the component from its current progress to 100%
            remaining_progress = 1.0 - component["progress"]
            weight_contribution = remaining_progress * self.component_weights[name]
            self.completed_weight += weight_contribution
            component["progress"] = 1.0
            
            self.initialized_count += 1
            logger.info(f"Component {name} initialized successfully in {component['init_duration']:.2f}s")
        else:
            logger.error(f"Component {name} initialization failed: {error}")
        
        # Calculate the overall progress percentage
        overall_progress = self.completed_weight / self.total_weight
        
        # Make sure we don't hit 100% until all components are initialized
        if self.initialized_count < self.total_components:
            overall_progress = min(0.99, overall_progress)
        else:
            overall_progress = 1.0
            
        # Call the progress callback with the updated progress
        message = f"Initialized {self.initialized_count}/{self.total_components} components"
        if error:
            message = f"Error initializing {name}: {error}"
            
        self.progress_callback(overall_progress, message)
    
    def get_component_status(self, name: str) -> Dict[str, Any]:
        """
        Get a component's current status.
        
        Args:
            name: Component name
            
        Returns:
            Status dict or None if component not found
        """
        return self.component_status.get(name)
    
    def check_dependencies_met(self, name: str) -> bool:
        """
        Check if all dependencies for a component are initialized.
        
        Args:
            name: Component name
            
        Returns:
            True if all dependencies are initialized
        """
        if name not in self.component_dependencies:
            return True
            
        for dependency in self.component_dependencies[name]:
            if dependency not in self.component_status:
                logger.warning(f"Component {name} depends on unknown component: {dependency}")
                return False
                
            if not self.component_status[dependency]["initialized"]:
                return False
                
        return True
    
    def all_components_initialized(self) -> bool:
        """
        Check if all components are initialized.
        
        Returns:
            True if all components are initialized
        """
        return self.initialized_count >= self.total_components
        
    def get_uninitialized_components(self) -> List[str]:
        """
        Get a list of components that haven't been initialized.
        
        Returns:
            List of component names
        """
        return [name for name, status in self.component_status.items() 
                if not status["initialized"]]
                
    def get_initialization_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the initialization process.
        
        Returns:
            Dictionary with initialization stats
        """
        end_time = time.time()
        total_duration = end_time - self.start_time
        
        return {
            "total_components": self.total_components,
            "initialized_components": self.initialized_count,
            "total_duration": total_duration,
            "overall_progress": self.completed_weight / self.total_weight,
            "component_details": self.component_status,
            "uninitialized_components": self.get_uninitialized_components()
        }

# Helper function for optimized initialization sequence
async def initialize_components_with_tracker(
    component_classes: Dict[str, Any],
    event_bus: Any,
    config: Dict[str, Any],
    tracker: InitializationTracker
) -> Dict[str, Any]:
    """
    Initialize components with dependency tracking and accurate progress reporting.
    
    Args:
        component_classes: Dictionary mapping component names to their classes
        event_bus: Event bus instance for component communication
        config: Configuration dictionary
        tracker: Initialization tracker instance
        
    Returns:
        Dictionary of initialized components
    """
    components = {}
    initialization_errors = []
    
    # First pass: Try to initialize components in order of dependencies
    for name, component_class in component_classes.items():
        if name in components:
            logger.debug(f"Component {name} already initialized, skipping")
            continue
            
        # Skip if dependencies aren't met yet
        if not tracker.check_dependencies_met(name):
            logger.debug(f"Dependencies not met for {name}, deferring initialization")
            continue
            
        try:
            logger.info(f"Initializing component: {name}")
            tracker.update_component_progress(name, 0.1, f"Creating {name}...")
            
            # Instantiate the component
            component = component_class(event_bus=event_bus, config=config)
            tracker.update_component_progress(name, 0.3, f"Instantiated {name}...")
            
            # Initialize if the component has an initialize method
            if hasattr(component, 'initialize'):
                tracker.update_component_progress(name, 0.5, f"Running {name}.initialize()...")
                await component.initialize()
                tracker.update_component_progress(name, 0.9, f"Completed {name}.initialize()...")
                
            # Add to components dictionary
            components[name] = component
            
            # Mark as fully initialized
            tracker.mark_component_initialized(name, True)
            
            # Check if any dependent components can now be initialized
            _check_dependent_components(component_classes, components, event_bus, config, tracker)
                
        except Exception as e:
            logger.error(f"Error initializing {name}: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            initialization_errors.append((name, str(e)))
            tracker.mark_component_initialized(name, False, str(e))
    
    # Second pass: Try to initialize any components that weren't initialized in the first pass
    # This handles circular dependencies and other edge cases
    remaining_components = [name for name in component_classes if name not in components]
    if remaining_components:
        logger.warning(f"Second pass initialization for {len(remaining_components)} components")
        for name in remaining_components:
            try:
                logger.info(f"Second pass initializing: {name}")
                tracker.update_component_progress(name, 0.1, f"Creating {name} (retry)...")
                
                # Instantiate the component
                component = component_classes[name](event_bus=event_bus, config=config)
                tracker.update_component_progress(name, 0.5, f"Instantiated {name} (retry)...")
                
                # Initialize if the component has an initialize method
                if hasattr(component, 'initialize'):
                    await component.initialize()
                    
                # Add to components dictionary
                components[name] = component
                
                # Mark as fully initialized
                tracker.mark_component_initialized(name, True)
                
            except Exception as e:
                logger.error(f"Error in second pass initialization of {name}: {e}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                initialization_errors.append((name, str(e)))
                tracker.mark_component_initialized(name, False, str(e))
    
    return components

def _check_dependent_components(
    component_classes: Dict[str, Any],
    components: Dict[str, Any],
    event_bus: Any,
    config: Dict[str, Any],
    tracker: InitializationTracker
) -> None:
    """
    Check and initialize components whose dependencies are now met.
    
    Args:
        component_classes: Component class dictionary
        components: Initialized components dictionary
        event_bus: Event bus instance
        config: Configuration dictionary
        tracker: Initialization tracker
    """
    for name, component_class in component_classes.items():
        # Skip already initialized components
        if name in components:
            continue
            
        # Check if dependencies are now met
        if tracker.check_dependencies_met(name):
            logger.info(f"Dependencies now met for {name}, scheduling initialization")
            
            # Schedule initialization in the event loop
            loop = asyncio.get_event_loop()
            asyncio.create_task(_initialize_component(
                name, component_class, event_bus, config, components, tracker
            ))

async def _initialize_component(
    name: str,
    component_class: Any,
    event_bus: Any,
    config: Dict[str, Any],
    components: Dict[str, Any],
    tracker: InitializationTracker
) -> None:
    """
    Initialize a single component asynchronously.
    
    Args:
        name: Component name
        component_class: Component class
        event_bus: Event bus instance
        config: Configuration dictionary
        components: Initialized components dictionary
        tracker: Initialization tracker
    """
    try:
        logger.info(f"Async initializing component: {name}")
        tracker.update_component_progress(name, 0.1, f"Creating {name}...")
        
        # Instantiate the component
        component = component_class(event_bus=event_bus, config=config)
        tracker.update_component_progress(name, 0.3, f"Instantiated {name}...")
        
        # Initialize if the component has an initialize method
        if hasattr(component, 'initialize'):
            tracker.update_component_progress(name, 0.5, f"Running {name}.initialize()...")
            await component.initialize()
            tracker.update_component_progress(name, 0.9, f"Completed {name}.initialize()...")
            
        # Add to components dictionary
        components[name] = component
        
        # Mark as fully initialized
        tracker.mark_component_initialized(name, True)
        
    except Exception as e:
        logger.error(f"Error in async initialization of {name}: {e}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        tracker.mark_component_initialized(name, False, str(e))
