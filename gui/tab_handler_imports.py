#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Tab Handler Imports Module
Imports and binds all event handler modules to the TabManager class
"""

import logging
import inspect
import importlib
import asyncio
from typing import Dict, Any, List, Callable, Optional, Union

logger = logging.getLogger("KingdomAI.TabHandlerImports")

# List of handler modules to import
HANDLER_MODULES = [
    'gui.system_handlers',
    'gui.trading_handlers',
    'gui.mining_handlers',
    'gui.thoth_handlers',
    'gui.voice_handlers',
    'gui.wallet_handlers',
    'gui.api_keys_handlers',
    'gui.vr_handlers',
    'gui.codegen_handlers'
]

def import_handler_modules():
    """Import all handler modules and return them in a dictionary.
    
    Returns:
        dict: Dictionary mapping module names to imported modules
    """
    modules = {}
    for module_name in HANDLER_MODULES:
        try:
            module = importlib.import_module(module_name)
            # Extract the short name (e.g., 'system_handlers' from 'gui.system_handlers')
            short_name = module_name.split('.')[-1]
            modules[short_name] = module
            logger.debug(f"Imported handler module: {module_name}")
        except ImportError as e:
            logger.error(f"Failed to import handler module {module_name}: {e}")
    
    return modules

def is_event_handler(obj):
    """Check if object is an event handler function.
    
    Args:
        obj: Object to check
        
    Returns:
        bool: True if object is an event handler function, False otherwise
    """
    # Check if it's a function/method and has the expected signature
    if not inspect.isfunction(obj):
        return False
        
    # Get signature
    sig = inspect.signature(obj)
    
    # Event handlers have self, event_type, and event_data parameters
    params = list(sig.parameters.keys())
    return len(params) >= 3 and params[0] == 'self' and 'event_type' in params and 'event_data' in params

def get_method_name(obj):
    """Get method name from function object.
    
    Args:
        obj: Function object
        
    Returns:
        str: Method name
    """
    return obj.__name__

def bind_handler_modules_to_tab_manager(tab_manager_class):
    """Bind all handler methods to the TabManager class.
    
    Args:
        tab_manager_class: The TabManager class to bind methods to
        
    Returns:
        None
    """
    modules = import_handler_modules()
    
    for module_name, module in modules.items():
        logger.debug(f"Processing module {module_name}")
        
        # Find all event handler methods
        for name, obj in inspect.getmembers(module):
            if is_event_handler(obj):
                # Bind method to TabManager class
                method_name = get_method_name(obj)
                setattr(tab_manager_class, method_name, obj)
                logger.debug(f"Bound handler method {method_name} to TabManager")
            
        # Find all tab-specific initialization methods
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and name not in ['is_event_handler', 'get_method_name']:
                # Check if it's not an event handler but still a valid function
                if not is_event_handler(obj) and 'self' in inspect.signature(obj).parameters:
                    # Bind method to TabManager class
                    method_name = get_method_name(obj)
                    setattr(tab_manager_class, method_name, obj)
                    logger.debug(f"Bound initialization method {method_name} to TabManager")
                    
    logger.info("Successfully bound all handler methods to TabManager")
