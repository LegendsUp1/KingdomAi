#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ConfigManager Proxy with compatibility methods
"""

from typing import Any

# Try different possible ConfigManager imports
try:
    from core.config_manager import ConfigManager as OriginalConfigManager
except ImportError:
    try:
        from system_core.config_manager import ConfigManager as OriginalConfigManager
    except ImportError:
        # Create a dummy class if we can't import the real one
        class OriginalConfigManager:
            def __init__(self, *args, **kwargs):
                self.config_data = {}
                
            def get(self, path, default=None):
                return default

class ConfigManager(OriginalConfigManager):
    """
    ConfigManager with additional compatibility methods
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def get_config(self, path: str, default: Any = None) -> Any:
        """
        Alias for get() method to maintain compatibility.
        
        Args:
            path: Dot-separated path to the configuration value
            default: Default value to return if path doesn't exist
            
        Returns:
            Configuration value or default
        """
        # Use get if it exists, otherwise fall back to default
        if hasattr(self, 'get'):
            return self.get(path, default)
        return default

# Standalone functions for easier usage
def get_config(path: str, default: Any = None) -> Any:
    """Get configuration using the proxy ConfigManager"""
    cm = ConfigManager()
    return cm.get_config(path, default)

def get(path: str, default: Any = None) -> Any:
    """Get configuration using the proxy ConfigManager"""
    cm = ConfigManager()
    return cm.get(path, default)

# Create instances for direct import - AFTER defining the functions
config_manager_proxy = ConfigManager()
get_config_proxy = get_config  # Now this will work because get_config is defined above
