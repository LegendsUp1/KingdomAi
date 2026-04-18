"""
Kingdom AI Event Handlers Fix Module
This module provides EVENT_HANDLERS for components that need them.
"""

# Standard EVENT_HANDLERS map
EVENT_HANDLERS = {
    "system_status": "on_system_status",
    "component_status": "on_component_status", 
    "system_error": "on_system_error",
    "gui_update": "on_gui_update",
    "system_shutdown": "on_shutdown",
    "trading_status": "_handle_trading_status",
    "loading_update": "_handle_loading_update"
}

def get_handlers():
    """Return the EVENT_HANDLERS dictionary."""
    return EVENT_HANDLERS

def build_handler_map(instance):
    """Build a handler map for an instance.
    
    Args:
        instance: Object with handler methods
        
    Returns:
        dict: Map of event types to bound methods
    """
    result = {}
    
    for event_type, handler_name in EVENT_HANDLERS.items():
        if hasattr(instance, handler_name):
            result[event_type] = getattr(instance, handler_name)
            
    return result

def subscribe_to_events(instance, event_bus):
    """Subscribe an instance's handlers to an event bus.
    
    Args:
        instance: Object with handler methods
        event_bus: Event bus to subscribe to
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not event_bus:
        return False
        
    try:
        handler_map = build_handler_map(instance)
        
        for event_type, handler in handler_map.items():
            event_bus.subscribe(event_type, handler)
            
        return True
    except Exception as e:
        print(f"Error subscribing to events: {e}")
        return False

def subscribe_instance_to_events(instance, event_bus):
    """Subscribe an instance's event handlers to an event bus.
    
    This function examines the instance for methods matching handler names in EVENT_HANDLERS
    and subscribes them to the corresponding event types in the event bus.
    
    Args:
        instance: The object instance containing handler methods
        event_bus: The event bus to subscribe to
        
    Returns:
        bool: True if subscription was successful, False otherwise
    """
    if not event_bus:
        return False
    
    success = True
    
    try:
        # Register each handler method that exists on the instance
        for event_type, handler_name in EVENT_HANDLERS.items():
            if hasattr(instance, handler_name):
                handler = getattr(instance, handler_name)
                try:
                    event_bus.subscribe(event_type, handler)
                except Exception as e:
                    print(f"Error subscribing {handler_name} to {event_type}: {e}")
                    success = False
    except Exception as e:
        print(f"Error in event subscription process: {e}")
        success = False
        
    return success
