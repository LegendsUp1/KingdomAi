#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Default configurations for Kingdom AI components.
Provides fallback configurations when component configs are not found.
"""

DEFAULT_CONFIGS = {
    "security": {
        "enable_encryption": True,
        "auth_timeout": 3600,
        "max_login_attempts": 5,
        "require_2fa": False
    },
    "thoth": {
        "model": "cogito:latest",
        "max_tokens": 2048,
        "temperature": 0.7,
        "top_p": 0.95,
        "context_window": 8192
    },
    "blockchain": {
        "node_url": "https://mainnet.infura.io/v3/your-api-key",
        "chain_id": 1,
        "gas_limit": 21000,
        "gas_price_strategy": "medium"
    },
    "mining": {
        "threads": 1,
        "target_hash_rate": 0.0,
        "pool_url": "",
        "pool_user": "",
        "pool_password": ""
    },
    "market_api": {
        "api_key": "",
        "api_secret": "",
        "base_url": "https://api.example.com/v1" 
    }
}

def get_default_config(component_name):
    """Get default configuration for a component.
    
    Args:
        component_name: Name of the component
        
    Returns:
        dict: Default configuration for the component or empty dict if not found
    """
    return DEFAULT_CONFIGS.get(component_name, {}).copy()
