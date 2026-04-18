#!/usr/bin/env python3
"""
Global POA Chain Compatibility Patch for Kingdom AI
==================================================

This module monkey-patches Web3.py to automatically apply POA middleware
to ALL Web3 instances, regardless of how they're created in the system.
This ensures that POA chains with extended extraData are handled correctly.
"""

import logging
from web3 import Web3, AsyncWeb3
from web3.providers.base import BaseProvider

logger = logging.getLogger("kingdom_ai.global_poa_patch")

# Store original Web3 constructors
_original_web3_init = Web3.__init__
_original_async_web3_init = AsyncWeb3.__init__

def global_poa_middleware(make_request, web3):
    """
    Global POA middleware that handles all POA chains by truncating extraData.
    This is applied automatically to ALL Web3 instances.
    """
    def middleware(method, params):
        response = make_request(method, params)
        
        # For block requests, modify the response to be compatible with Web3.py validation
        if method in ['eth_getBlockByNumber', 'eth_getBlockByHash']:
            if isinstance(response, dict) and 'extraData' in response:
                # Store original extraData but truncate for Web3.py validation
                original_extra_data = response['extraData']
                # Truncate extraData to 32 bytes (66 chars with 0x prefix) for validation
                if len(str(original_extra_data)) > 66:
                    response['extraData'] = str(original_extra_data)[:66]
                    # Store original in a custom field if needed
                    response['_original_extraData'] = original_extra_data
                    logger.debug(f"Truncated extraData from {len(str(original_extra_data))} to 66 chars for POA compatibility")
        
        return response
    return middleware

def patched_web3_init(self, provider: BaseProvider = None, *args, **kwargs):
    """Patched Web3.__init__ that automatically applies POA middleware."""
    # Call original constructor
    _original_web3_init(self, provider, *args, **kwargs)
    
    try:
        # Automatically inject POA middleware at layer 0 for all instances
        self.middleware_onion.inject(global_poa_middleware, layer=0)
        logger.info("Global POA middleware automatically applied to Web3 instance")
    except Exception as e:
        logger.warning(f"Failed to apply global POA middleware to Web3 instance: {e}")

def patched_async_web3_init(self, provider: BaseProvider = None, *args, **kwargs):
    """Patched AsyncWeb3.__init__ that automatically applies POA middleware."""
    # Call original constructor
    _original_async_web3_init(self, provider, *args, **kwargs)
    
    try:
        # Automatically inject POA middleware at layer 0 for all instances
        self.middleware_onion.inject(global_poa_middleware, layer=0)
        logger.info("Global POA middleware automatically applied to AsyncWeb3 instance")
    except Exception as e:
        logger.warning(f"Failed to apply global POA middleware to AsyncWeb3 instance: {e}")

def apply_global_poa_patch():
    """
    Apply the global POA patch to Web3.py.
    This ensures ALL Web3 instances automatically handle POA chains.
    """
    try:
        # Monkey-patch Web3 constructors
        Web3.__init__ = patched_web3_init
        AsyncWeb3.__init__ = patched_async_web3_init
        
        logger.info("Global POA patch applied successfully - all Web3 instances will handle POA chains")
        return True
    except Exception as e:
        logger.error(f"Failed to apply global POA patch: {e}")
        return False

def remove_global_poa_patch():
    """Remove the global POA patch and restore original Web3 behavior."""
    try:
        # Restore original constructors
        Web3.__init__ = _original_web3_init
        AsyncWeb3.__init__ = _original_async_web3_init
        
        logger.info("Global POA patch removed - Web3 behavior restored to original")
        return True
    except Exception as e:
        logger.error(f"Failed to remove global POA patch: {e}")
        return False

# Auto-apply the patch when this module is imported
if __name__ != "__main__":
    apply_global_poa_patch()
