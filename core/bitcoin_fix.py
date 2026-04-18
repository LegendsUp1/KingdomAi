#!/usr/bin/env python3
"""Bitcoin Connection Fix for Kingdom AI

This module provides a fix for the bitcoin wallet connection issue
where 'str' object has no attribute 'get_config'
"""

import logging
import traceback

logger = logging.getLogger("KingdomAI.BitcoinFix")

class BitcoinConnectionWrapper:
    """
    Wrapper for Bitcoin connection that handles configuration properly
    """
    
    def __init__(self, connection_obj):
        """Initialize with a connection object."""
        self.name = "bitcoin_connection_wrapper"
        self.logger = logging.getLogger("KingdomAI.BitcoinConnection")
        self.original_connection = connection_obj
        
        # Create config dictionary
        self.config = {}
        
        # If the original has a config attribute, use it
        if hasattr(connection_obj, 'config'):
            if isinstance(connection_obj.config, dict):
                self.config = connection_obj.config
            elif isinstance(connection_obj.config, str):
                self.config = {"connection_string": connection_obj.config}
        elif isinstance(connection_obj, str):
            self.config = {"connection_string": connection_obj}
        elif isinstance(connection_obj, dict):
            self.config = connection_obj
        else:
            # Create default config
            self.config = {
                "host": "localhost",
                "port": 8332,
                "user": "bitcoin",
                "password": "bitcoin",
                "wallet": "kingdom_bitcoin_wallet"
            }
            self.logger.warning(f"Using default config for unknown connection type: {type(connection_obj)}")
    
    def get_config(self, key=None, default=None):
        """Get configuration value."""
        if key is None:
            return self.config
        return self.config.get(key, default)
    
    def set_config(self, key, value):
        """Set configuration value."""
        self.config[key] = value
        return True
    
    def __getattr__(self, name):
        """Delegate attribute access to original connection object."""
        if name == "get_config" or name == "set_config" or name == "config":
            return object.__getattribute__(self, name)
        
        # For all other attributes, delegate to the original connection
        try:
            return getattr(self.original_connection, name)
        except AttributeError:
            # If not found on original, raise AttributeError
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

# A global function to apply fixes to all bitcoin components in the system
def fix_bitcoin_components(component_dict):
    """Fix all bitcoin-related components in the component dictionary"""
    try:
        logger.info("Applying fixes to all bitcoin components...")
        fixed_count = 0
        
        # Special handling for bitcoin_connection
        if "bitcoin_connection" in component_dict:
            logger.info("Fixing bitcoin_connection component")
            component = component_dict["bitcoin_connection"]
            if not hasattr(component, 'get_config') or not callable(component.get_config):
                component_dict["bitcoin_connection"] = BitcoinConnectionWrapper(component)
                fixed_count += 1
                logger.info("Fixed bitcoin_connection component successfully")
        
        # For any component that contains 'bitcoin' in its name
        for name, component in list(component_dict.items()):
            if 'bitcoin' in name.lower() and name != "bitcoin_connection":
                logger.info(f"Checking component {name} for possible fix")
                
                # Bitcoin wallet needs config with get_config method
                if name == "bitcoin_wallet" and hasattr(component, 'connection'):
                    logger.info("Fixing bitcoin wallet connection")
                    if not hasattr(component.connection, 'get_config'):
                        try:
                            component.connection = BitcoinConnectionWrapper(component.connection)
                            fixed_count += 1
                            logger.info("Fixed bitcoin wallet connection successfully")
                        except Exception as e:
                            logger.error(f"Failed to fix bitcoin wallet connection: {e}")
                            logger.error(traceback.format_exc())
        
        logger.info(f"Bitcoin component fixes complete. Fixed {fixed_count} components.")
        return fixed_count > 0
    except Exception as e:
        logger.error(f"Error in fix_bitcoin_components: {e}")
        logger.error(traceback.format_exc())
        return False

# Function to directly fix a Bitcoin connection for use with bitcoin wallet
def fix_bitcoin_connection(bitcoin_connection):
    """Wrap a bitcoin connection object with proper config handling"""
    try:
        logger.info("Applying Bitcoin connection fix")
        
        # Check if already fixed
        if hasattr(bitcoin_connection, 'get_config') and callable(bitcoin_connection.get_config):
            logger.info("Bitcoin connection already has get_config method")
            return bitcoin_connection
        
        # Create wrapper
        wrapper = BitcoinConnectionWrapper(bitcoin_connection)
        logger.info("Created Bitcoin connection wrapper with proper config handling")
        return wrapper
    except Exception as e:
        logger.error(f"Failed to fix Bitcoin connection: {e}")
        logger.error(traceback.format_exc())
        # Return original to avoid breaking everything
        return bitcoin_connection
