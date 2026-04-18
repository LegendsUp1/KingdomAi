#!/usr/bin/env python3
# Redis Quantum Manager for Kingdom AI

import logging
import asyncio
import redis
import json
import sys
import os
from typing import Dict, Any, Optional
import traceback

class RedisQuantumNexus:
    """
    RedisQuantumNexus manages the critical Redis connection for Kingdom AI.
    Enforces strict connection requirements with no fallback allowed.
    System will halt on connection failure.
    """
    
    def __init__(self):
        """Initialize the Redis Quantum Nexus manager."""
        self.logger = logging.getLogger("KingdomAI.RedisQuantumNexus")
        self.connection = None
        self.host = "localhost"
        self.port = 6380
        self.password = "QuantumNexus2025"
        self.db = 0
        self.ssl = False
        self.timeout = 30
        self.connected = False
        self.config_loaded = False
    
    async def load_config(self) -> None:
        """Load Redis configuration from config file."""
        try:
            config_path = os.path.join("config", "redis_config.json")
            if not os.path.exists(config_path):
                self.logger.warning(f"Redis config file not found: {config_path} - using defaults")
                
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.host = config.get("host", "localhost")
            
            # Strictly enforce port 6380
            config_port = config.get("port", 6380)
            if config_port != 6380:
                self.logger.warning(f"Incorrect Redis port in config: {config_port}. Enforcing mandatory port 6380.")
                config_port = 6380
            self.port = config_port
                
            self.password = config.get("password", "QuantumNexus2025")
            self.db = config.get("db", 0)
            self.ssl = config.get("ssl", False)
            self.timeout = config.get("health_check_interval", 30)
            
            # Verify no fallback mode is configured
            if config.get("fallback_mode", False) is True:
                self.logger.warning("Fallback mode detected in config but not allowed - disabling")
            
            self.config_loaded = True
            self.logger.info(f"Redis Quantum Nexus configuration loaded: {self.host}:{self.port}")
            
        except Exception as e:
            self.logger.warning(f"Failed to load Redis configuration: {str(e)} - using defaults")
            self.config_loaded = True
    
    async def connect(self) -> bool:
        """
        Establish connection to Redis Quantum Nexus.
        System will halt if connection fails.
        """
        if not self.config_loaded:
            await self.load_config()
            
        try:
            self.logger.info(f"Connecting to Redis Quantum Nexus at {self.host}:{self.port}")
            
            # Create Redis connection
            self.connection = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                ssl=self.ssl,
                socket_timeout=5,
                decode_responses=True
            )
            
            # Test connection
            if not self.connection.ping():
                self.logger.warning("⚠️ Redis Quantum Nexus connection failed - running in degraded mode")
                return False
                
            self.connected = True
            self.logger.info("Redis Quantum Nexus connection established successfully")
            
            # Start health check
            asyncio.create_task(self._health_check())
            
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to connect to Redis Quantum Nexus: {str(e)} - running in degraded mode")
            return False
    
    async def _health_check(self) -> None:
        """Periodically check Redis connection health."""
        while self.connected:
            try:
                await asyncio.sleep(self.timeout)
                if not self.connection.ping():
                    self.logger.warning("⚠️ Redis Quantum Nexus health check failed")
                    self.connected = False
                    break
            except Exception as e:
                self.logger.warning(f"⚠️ Redis Quantum Nexus health check error: {str(e)}")
                self.connected = False
                break
    
    async def get(self, key: str) -> Any:
        """Get value from Redis."""
        try:
            if not self.connected:
                self.logger.warning("Attempted Redis operation before connection established")
                return None
                
            return self.connection.get(key)
        except Exception as e:
            self.logger.warning(f"Redis get operation failed: {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, expiry: Optional[int] = None) -> None:
        """Set value in Redis."""
        try:
            if not self.connected:
                self.logger.warning("Attempted Redis operation before connection established")
                return
                
            if expiry:
                self.connection.setex(key, expiry, value)
            else:
                self.connection.set(key, value)
        except Exception as e:
            self.logger.warning(f"Redis set operation failed: {str(e)}")
            
    async def hash_set(self, name: str, mapping: Dict[str, Any]) -> None:
        """Set hash mapping in Redis."""
        try:
            if not self.connected:
                self.logger.warning("Attempted Redis operation before connection established")
                return
                
            self.connection.hset(name, mapping=mapping)
        except Exception as e:
            self.logger.warning(f"Redis hash set operation failed: {str(e)}")
    
    async def hash_get(self, name: str, key: Optional[str] = None) -> Any:
        """Get hash value(s) from Redis."""
        try:
            if not self.connected:
                self.logger.warning("Attempted Redis operation before connection established")
                return None
                
            if key:
                return self.connection.hget(name, key)
            else:
                return self.connection.hgetall(name)
        except Exception as e:
            self.logger.warning(f"Redis hash get operation failed: {str(e)}")
            return None
    
    async def publish(self, channel: str, message: str) -> None:
        """Publish message to Redis channel."""
        try:
            if not self.connected:
                self.logger.warning("Attempted Redis operation before connection established")
                return
                
            self.connection.publish(channel, message)
        except Exception as e:
            self.logger.warning(f"Redis publish operation failed: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        try:
            if self.connection:
                self.connected = False
                self.connection.close()
                self.logger.info("Redis Quantum Nexus connection closed")
        except Exception as e:
            self.logger.error(f"Error during Redis disconnect: {str(e)}")

# Global instance
redis_quantum_nexus = RedisQuantumNexus()
