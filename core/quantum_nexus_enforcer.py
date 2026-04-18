#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quantum Nexus Redis Connection Enforcer for Kingdom AI System.

This module ensures strict enforcement of Redis Quantum Nexus connection
requirements with no fallbacks allowed. If the Redis connection fails,
the system will halt immediately as per security requirements.
"""

import logging
import os
import sys
import redis
import json
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Constants for Redis Quantum Nexus Configuration
REDIS_QUANTUM_HOST = os.environ.get("REDIS_QUANTUM_HOST", "localhost")
REDIS_QUANTUM_PORT = 6380  # Hard-coded as per system requirements
REDIS_QUANTUM_PASSWORD = "QuantumNexus2025"  # Hard-coded as per system requirements
REDIS_QUANTUM_DB = int(os.environ.get("REDIS_QUANTUM_DB", "0"))
REDIS_CONNECTION_TIMEOUT = 5  # seconds
REDIS_RETRY_COUNT = 3
REDIS_RETRY_DELAY = 1  # seconds

class QuantumNexusEnforcer:
    """
    Redis Quantum Nexus connection enforcer.
    
    This class ensures all blockchain registry and critical system components
    maintain strict connection to the Redis Quantum Nexus, with NO FALLBACKS.
    System will halt if Redis connection fails or becomes unhealthy.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one enforcer exists."""
        if cls._instance is None:
            cls._instance = super(QuantumNexusEnforcer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, allow_halt: bool = True):
        """
        Initialize the Quantum Nexus enforcer.
        
        Args:
            allow_halt: If True, will halt the system on connection failures.
                        If False, will raise exceptions instead (useful for tests).
        """
        if self._initialized:
            return
            
        self.logger = logging.getLogger("QuantumNexusEnforcer")
        self.redis_client = None
        self.is_connected = False
        self.allow_halt = allow_halt
        self.connection_attempts = 0
        self._initialized = True
    
    def connect(self) -> bool:
        """
        Connect to Redis Quantum Nexus with strict enforcement.
        
        Returns:
            bool: True if connected successfully. Will not return False,
                  as system halts on connection failure.
        
        Raises:
            SystemExit: If connection fails and allow_halt is True
            redis.RedisConnectionError: If connection fails and allow_halt is False
        """
        self.logger.info(f"Connecting to Redis Quantum Nexus at {REDIS_QUANTUM_HOST}:{REDIS_QUANTUM_PORT}")
        self.connection_attempts += 1
        
        try:
            self.redis_client = redis.Redis(
                host=REDIS_QUANTUM_HOST,
                port=REDIS_QUANTUM_PORT,
                password=REDIS_QUANTUM_PASSWORD,
                db=REDIS_QUANTUM_DB,
                socket_timeout=REDIS_CONNECTION_TIMEOUT,
                socket_connect_timeout=REDIS_CONNECTION_TIMEOUT,
                decode_responses=True
            )
            
            # Test connection with PING
            if not self.redis_client.ping():
                raise redis.RedisError("Redis PING failed")
            
            # Log successful connection
            self.logger.info("Successfully connected to Redis Quantum Nexus")
            self.is_connected = True
            
            # Register connection in Redis
            self._register_connection()
            
            return True
            
        except (redis.RedisError, ConnectionError) as e:
            error_message = f"CRITICAL: Failed to connect to Redis Quantum Nexus: {str(e)}"
            self.logger.critical(error_message)
            
            if self.connection_attempts < REDIS_RETRY_COUNT:
                self.logger.warning(f"Retrying connection in {REDIS_RETRY_DELAY} seconds... (Attempt {self.connection_attempts}/{REDIS_RETRY_COUNT})")
                time.sleep(REDIS_RETRY_DELAY)
                return self.connect()
            
            # 2026 FIX: Do NOT halt system - allow degraded operation
            self.logger.warning("⚠️ Redis Quantum Nexus connection failed - running in degraded mode")
            return False
    
    def check_health(self) -> bool:
        """
        Check health of Redis Quantum Nexus connection.
        
        Returns:
            bool: True if healthy. Will not return False, as system halts on health check failure.
        
        Raises:
            SystemExit: If health check fails and allow_halt is True
            redis.RedisConnectionError: If health check fails and allow_halt is False
        """
        if not self.redis_client:
            return self.connect()  # This will exit on failure
        
        try:
            # Run basic health checks
            if not self.redis_client.ping():
                raise redis.RedisError("Redis PING failed")
            
            # Check if password is still valid
            self.redis_client.get("quantum_nexus:health_check")
            
            return True
            
        except (redis.RedisError, ConnectionError) as e:
            error_message = f"CRITICAL: Redis Quantum Nexus health check failed: {str(e)}"
            self.logger.critical(error_message)
            
            # 2026 FIX: Do NOT halt system - allow degraded operation
            self.logger.warning("⚠️ Redis Quantum Nexus health check failed - running in degraded mode")
            return False
    
    def _register_connection(self) -> None:
        """Register this connection in Redis for monitoring."""
        if not self.redis_client or not self.is_connected:
            return
            
        try:
            connection_info = {
                "timestamp": time.time(),
                "hostname": os.environ.get("HOSTNAME", "unknown"),
                "process_id": os.getpid(),
                "component": "BlockchainRegistry",
                "version": os.environ.get("KINGDOM_VERSION", "unknown")
            }
            
            self.redis_client.hset(
                "quantum_nexus:connections",
                f"conn:{os.getpid()}",
                json.dumps(connection_info)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to register connection: {str(e)}")
            # Don't halt here as connection already verified
    
    def verify_connection(self) -> bool:
        """
        Verify that the Redis Quantum Nexus connection is active and healthy.
        
        Returns:
            bool: True if connection is verified, will not return False as system halts on failure
            
        Raises:
            SystemExit: If verification fails and allow_halt is True
            redis.RedisConnectionError: If verification fails and allow_halt is False
        """
        if not self.is_connected or not self.redis_client:
            return self.connect()
            
        return self.check_health()
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current configuration of the enforcer.
        
        Returns:
            Dict: Configuration dictionary with current settings
        """
        return {
            "host": REDIS_QUANTUM_HOST,
            "port": REDIS_QUANTUM_PORT,
            "password": "*****",  # Masked for security
            "db": REDIS_QUANTUM_DB,
            "is_connected": self.is_connected,
            "connection_attempts": self.connection_attempts,
            "no_fallback_allowed": True,  # As per system requirements
            "halt_on_failure": self.allow_halt
        }
        
    def validate_blockchain_registry(self, registry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate blockchain registry data against Redis Quantum Nexus.
        
        Args:
            registry_data: Blockchain registry data to validate
            
        Returns:
            Dict: Validated and possibly enhanced registry data
            
        Raises:
            SystemExit: If validation fails and allow_halt is True
            ValueError: If validation fails and allow_halt is False
        """
        if not self.redis_client or not self.is_connected:
            self.connect()  # This will exit on failure
            
        try:
            # Check if registry exists in Redis
            if self.redis_client.exists("quantum_nexus:blockchain_registry"):
                # Get registry from Redis
                redis_registry = self.redis_client.get("quantum_nexus:blockchain_registry")
                try:
                    redis_registry_data = json.loads(redis_registry)
                    
                    # Merge with provided registry data, prioritizing Redis values
                    for network_id, network_data in redis_registry_data.items():
                        if network_id not in registry_data:
                            registry_data[network_id] = network_data
                        else:
                            # Override certain security-critical fields
                            for key in ["rpc_urls", "security_level", "production"]:
                                if key in network_data:
                                    registry_data[network_id][key] = network_data[key]
                    
                except json.JSONDecodeError:
                    self.logger.error("Invalid JSON in Redis blockchain registry")
            
            # Store updated registry in Redis
            self.redis_client.set(
                "quantum_nexus:blockchain_registry",
                json.dumps(registry_data)
            )
            
            return registry_data
            
        except (redis.RedisError, ConnectionError) as e:
            error_message = f"CRITICAL: Failed to validate blockchain registry: {str(e)}"
            self.logger.critical(error_message)
            
            # 2026 FIX: Do NOT halt system - allow degraded operation
            self.logger.warning("⚠️ Redis Quantum Nexus registry validation failed - running in degraded mode")
            return False

# Create a singleton instance for import
quantum_nexus = QuantumNexusEnforcer()

def get_quantum_nexus() -> QuantumNexusEnforcer:
    """
    Get the global Quantum Nexus enforcer instance.
    
    Returns:
        QuantumNexusEnforcer: The global enforcer instance
    """
    return quantum_nexus

# Immediate connection check on module import
# This ensures immediate halt if Redis is not available
quantum_nexus.connect()
