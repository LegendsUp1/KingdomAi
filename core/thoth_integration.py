"""
Thoth Integration Module

This module provides utilities for integrating the separate handler modules
into the main thoth.py MCPConnector class. This avoids token limitations during
development while ensuring all components are properly connected to the event bus.
"""

import importlib.util
import inspect
import logging
import os
from typing import Dict, List


def integrate_handlers(connector_instance, module_paths: List[str]) -> Dict[str, bool]:
    """
    Integrate handler methods from external modules into an existing MCPConnector instance.
    
    Args:
        connector_instance: An instance of the MCPConnector class
        module_paths: List of paths to the handler modules to integrate
        
    Returns:
        Dict with module names as keys and success status as values
    """
    logger = logging.getLogger(__name__)
    results = {}
    
    for module_path in module_paths:
        module_name = os.path.basename(module_path).replace('.py', '')
        logger.info(f"Integrating handlers from module: {module_name}")
        
        try:
            # Import the module dynamically
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if not spec or not spec.loader:
                logger.error(f"Failed to load spec for module {module_name}")
                results[module_name] = False
                continue
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find all handler classes in the module
            handler_classes = []
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and not name.startswith('__'):
                    handler_classes.append(obj)
            
            if not handler_classes:
                logger.warning(f"No handler classes found in module {module_name}")
                results[module_name] = False
                continue
            
            # For each handler class, integrate its methods into the connector
            for handler_class in handler_classes:
                logger.info(f"Processing handler class: {handler_class.__name__}")
                
                # Get all methods from the handler class
                for name, method in inspect.getmembers(handler_class, inspect.isfunction):
                    if name.startswith('_') or not asyncio.iscoroutinefunction(method):
                        # Only process handler methods (usually start with _ and are async)
                        continue
                    
                    logger.info(f"Integrating method: {name}")
                    
                    # Create a new method bound to the connector instance
                    async def create_bound_method(method, connector):
                        async def bound_method(*args, **kwargs):
                            return await method(connector, *args, **kwargs)
                        return bound_method
                    
                    # Bind method to connector instance
                    bound_method = create_bound_method(method, connector_instance)
                    
                    # Set the method on the connector instance
                    setattr(connector_instance, name, bound_method)
                    
            results[module_name] = True
            
        except Exception as e:
            logger.error(f"Error integrating module {module_name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            results[module_name] = False
    
    return results


def check_event_handlers(connector_instance) -> Dict[str, List[str]]:
    """
    Check which event handlers are properly implemented in the connector.
    
    Args:
        connector_instance: An instance of the MCPConnector class
        
    Returns:
        Dict with handler categories and list of implemented handlers
    """
    # Define expected handlers by category
    expected_handlers = {
        "core": [
            "_handle_initialization_request",
            "_handle_status_check",
            "_handle_shutdown_request"
        ],
        "model": [
            "_handle_model_discovery",
            "_handle_capability_query",
            "_handle_add_model",
            "_handle_remove_model", 
            "_handle_select_model"
        ],
        "ai": [
            "_handle_chat_message",
            "_handle_code_generation",
            "_handle_code_repair",
            "_handle_data_analysis",
            "_handle_multi_model_consultation"
        ],
        "voice": [
            "_handle_voice_toggle",
            "_handle_voice_listen",
            "_handle_voice_command",
            "_handle_voice_speak",
            "_handle_speak_system_response"
        ]
    }
    
    # Check which handlers are implemented
    implemented_handlers = {}
    
    for category, handlers in expected_handlers.items():
        implemented = []
        for handler in handlers:
            if hasattr(connector_instance, handler) and callable(getattr(connector_instance, handler)):
                implemented.append(handler)
        
        implemented_handlers[category] = implemented
    
    return implemented_handlers


# Example usage:
"""
# Integrate handlers into connector
modules_to_integrate = [
    "path/to/thoth_voice_handlers.py",
    "path/to/thoth_ai_handlers.py"
]

results = integrate_handlers(connector, modules_to_integrate)
print("Integration results:", results)

# Check which handlers are now implemented
implemented = check_event_handlers(connector)
print("Implemented handlers:", implemented)
"""
