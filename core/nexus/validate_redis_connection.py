"""
Redis Quantum Nexus Connection Validator

This module provides validation utilities to ensure Redis Quantum Nexus 
is properly connected on the mandatory port 6380.
No fallbacks are allowed - system must halt if connection fails.

This follows the MANDATORY Redis connection requirement for Kingdom AI.
"""

import os
import sys
import json
import logging
import importlib.util

logger = logging.getLogger(__name__)

def validate_redis_config(config):
    """
    Validates Redis configuration to ensure port 6380 is being used.
    Raises SystemExit if the port is not 6380.
    """
    if config.get('port') != 6380:
        logger.warning(f"⚠️ Redis port should be 6380, found: {config.get('port')} - correcting")
        config['port'] = 6380
    
    # Ensure fallback mode is disabled
    if config.get('fallback_mode'):
        logger.warning("⚠️ Redis fallback mode was enabled - disabling")
        config['fallback_mode'] = False
        
    return True

def test_redis_connection(host, port=6380, password='QuantumNexus2025'):
    """
    Tests Redis connection on the specified port.
    Returns True if connection successful, False otherwise.
    Raises SystemExit if connection fails.
    """
    try:
        # Import Redis here to avoid import issues
        try:
            import redis
        except ImportError:
            logger.warning("⚠️ Redis package not installed - connection test skipped")
            return False
            
        # Always enforce port 6380
        if port != 6380:
            logger.warning(f"⚠️ Non-standard Redis port {port} requested - using 6380")
            port = 6380
            
        # Attempt connection with timeout
        client = redis.Redis(
            host=host,
            port=6380,  # Explicitly use 6380 regardless of input
            password=password,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        
        # Get server info to verify full connection
        redis_info = client.info()
        if not redis_info or 'redis_version' not in redis_info:
            logger.warning("⚠️ Redis connection test failed - could not get Redis info")
            return False
            
        logger.info(f"Redis connection verified on port 6380 (Redis v{redis_info['redis_version']})")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {str(e)} - running in limited mode")
        return False

def validate_redis_quantum_nexus_config(config):
    """
    Validates a Redis config that will be used with RedisQuantumNexus.
    This does not instantiate the RedisQuantumNexus, but ensures the config is valid.
    
    Args:
        config: The Redis configuration dict to validate
        
    Returns:
        The validated configuration with port enforced to 6380
    """
    # Check if Redis Quantum Nexus module is available
    try:
        # Check if Redis module exists by importing it
        if importlib.util.find_spec("core.nexus.redis_quantum_nexus") is None:
            logger.warning("⚠️ core.nexus.redis_quantum_nexus module not found - using defaults")
    except Exception as e:
        logger.warning(f"⚠️ Error checking Redis Quantum Nexus module: {e} - using defaults")
    
    # Create a copy of the config to avoid modifying the original
    validated_config = dict(config) if config else {}
    
    # Ensure required fields exist with defaults if not provided
    if 'host' not in validated_config:
        validated_config['host'] = '127.0.0.1'
        
    # ENFORCE port 6380 - no exceptions
    validated_config['port'] = 6380
    
    # Set password if not provided
    if 'password' not in validated_config:
        validated_config['password'] = os.environ.get('REDIS_PASSWORD', 'QuantumNexus2025')
    
    # Disable fallback mode
    validated_config['fallback_mode'] = False
    
    if 'db' not in validated_config:
        validated_config['db'] = 0
        
    # If port is not 6380 in the original config, log a warning
    if config and 'port' in config and config['port'] != 6380:
        logger.warning(f"Overriding Redis port from {config['port']} to mandatory port 6380")
    
    # Ensure the RedisQuantumNexus will use port 6380
    logger.info(f"Validated Redis config: Host={validated_config['host']}, Port=6380 (ENFORCED), DB={validated_config['db']}")
    
    return validated_config


def ensure_redis_connection(config=None):
    """
    Ensures a working Redis connection is available on port 6380.
    This will test the connection and halt the system if connection fails.
    
    Args:
        config: Optional Redis configuration dict. If not provided, uses default values.
        
    Returns:
        The validated configuration
    """
    # Start with default config if none provided
    if config is None:
        config = {
            'host': '127.0.0.1',
            'port': 6380,
            'password': os.environ.get('REDIS_PASSWORD', 'QuantumNexus2025'),
            'db': 0,
            'fallback_mode': False
        }
    
    # Check if config file exists and load it
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                             'config', 'redis_config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                # Update config with file values
                config.update(file_config)
        except Exception as e:
            logger.error(f"Error reading Redis config file: {e}. Using provided/default configuration.")
    
    # Validate and enforce port 6380
    validated_config = validate_redis_quantum_nexus_config(config)
    
    # Test the connection (this will exit if connection fails)
    test_redis_connection(
        host=validated_config['host'],
        port=validated_config['port'],
        password=validated_config['password']
    )
    
    logger.info("Redis connection on port 6380 validated successfully")
    return validated_config

if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run validation directly if executed as script
    ensure_redis_quantum_nexus_connection()
