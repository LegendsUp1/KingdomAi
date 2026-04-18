#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Redis Client Module
Provides a simplified client interface to the Redis Connector for component use.
"""

import logging
import json
from typing import Any, List, Optional, Union, Callable

# Import core Redis connector for delegation
from core.redis_connector import RedisQuantumNexusConnector, redis_import_successful


class RedisClient:
    """
    Redis client wrapper for Kingdom AI components.
    Provides a simplified interface to the Redis connector with proper error handling.
    """

    def __init__(self, name: str = "RedisClient", event_bus=None):
        """
        Initialize the Redis client.
        
        Args:
            name: Client name for logging
            event_bus: Optional event bus for publishing events
        """
        self.logger = logging.getLogger(f"core.redis_client.{name}")
        self.name = name
        self.event_bus = event_bus
        
        # Use the shared Redis connector instance
        self._connector = RedisQuantumNexusConnector(name=f"{name}_connector", event_bus=event_bus)
        
        if not redis_import_successful:
            self.logger.warning("Redis module not available. Some functionality will be limited.")
        
        self.logger.info(f"Redis client '{name}' initialized")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from Redis.
        
        Args:
            key: Redis key
            default: Default value if key doesn't exist
            
        Returns:
            The value or default
        """
        return self._connector.get_value(key, default)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in Redis.
        
        Args:
            key: Redis key
            value: Value to store
            ttl: Optional time-to-live in seconds
            
        Returns:
            Success status
        """
        return self._connector.set_value(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from Redis.
        
        Args:
            key: Redis key to delete
            
        Returns:
            True if key was deleted, False otherwise
        """
        try:
            result = self._connector.handle_redis_command("delete", key)
            return bool(result)
        except Exception as e:
            self.logger.error(f"Error deleting key '{key}': {str(e)}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in Redis.
        
        Args:
            key: Redis key to check
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            result = self._connector.handle_redis_command("exists", key)
            return bool(result)
        except Exception as e:
            self.logger.error(f"Error checking existence of key '{key}': {str(e)}")
            return False
    
    def publish(self, channel: str, message: Union[str, dict]) -> bool:
        """
        Publish a message to a Redis channel.
        
        Args:
            channel: Channel name
            message: Message to publish (string or dict, dict will be JSON serialized)
            
        Returns:
            Success status
        """
        try:
            # Convert dict to JSON string if needed
            if isinstance(message, dict):
                message = json.dumps(message)
                
            self._connector.publish(channel, message)
            return True
        except Exception as e:
            self.logger.error(f"Error publishing to channel '{channel}': {str(e)}")
            return False
    
    def subscribe(self, channel: str, callback: Callable[[str, Any], None]) -> bool:
        """
        Subscribe to a Redis channel.
        
        Args:
            channel: Channel name
            callback: Callback function that receives channel name and message
            
        Returns:
            Success status
        """
        try:
            if hasattr(self._connector, 'subscribe'):
                return self._connector.subscribe(channel, callback)
            self.logger.warning("Subscribe method not available in connector")
            return False
        except Exception as e:
            self.logger.error(f"Error subscribing to channel '{channel}': {str(e)}")
            return False
    
    def unsubscribe(self, channel: str) -> bool:
        """
        Unsubscribe from a Redis channel.
        
        Args:
            channel: Channel name
            
        Returns:
            Success status
        """
        try:
            if hasattr(self._connector, 'unsubscribe'):
                return self._connector.unsubscribe(channel)
            self.logger.warning("Unsubscribe method not available in connector")
            return False
        except Exception as e:
            self.logger.error(f"Error unsubscribing from channel '{channel}': {str(e)}")
            return False
    
    def keys(self, pattern: str) -> List[str]:
        """
        Get keys matching a pattern.
        
        Args:
            pattern: Key pattern to match
            
        Returns:
            List of matching keys
        """
        try:
            result = self._connector.handle_redis_command("keys", pattern)
            if result:
                return result
            return []
        except Exception as e:
            self.logger.error(f"Error getting keys with pattern '{pattern}': {str(e)}")
            return []
    
    def health_check(self) -> bool:
        """
        Check the health of the Redis connection.
        
        Returns:
            True if Redis is healthy, False otherwise
        """
        return self._connector.health_check()
    
    def flush(self) -> bool:
        """
        Flush all data from Redis.
        Warning: This will delete all data in the Redis database.
        
        Returns:
            Success status
        """
        try:
            result = self._connector.handle_redis_command("flushall")
            return bool(result)
        except Exception as e:
            self.logger.error(f"Error flushing Redis: {str(e)}")
            return False
    def ping(self) -> bool:
        # Ping Redis server to check connectivity
        try:
            if self._connector and hasattr(self._connector, 'redis_client'):
                return self._connector.redis_client.ping()
            return False
        except Exception as e:
            self.logger.error(f"Error pinging Redis: {str(e)}")
            return False
    
    def shutdown(self) -> None:
        """
        Clean up resources.
        """
        if self._connector:
            self._connector.shutdown()
            
    def __del__(self) -> None:
        """
        Clean up resources when object is garbage collected.
        """
        self.shutdown()
