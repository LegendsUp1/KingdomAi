#!/usr/bin/env python3
# core/redis_connection.py

import redis.asyncio as redis
import logging
import asyncio
import json
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KingdomAI.Redis")

class RedisConnection:
    def __init__(self, event_bus: Any = None, config: Optional[Dict[str, Any]] = None):
        self.event_bus = event_bus
        self.config = config or {}
        self._client: Optional[redis.Redis] = None
        # REDIS QUANTUM NEXUS - Port 6380, Password QuantumNexus2025
        self.host = self.config.get("redis_host", "127.0.0.1")
        self.port = self.config.get("redis_port", 6380)  # Quantum Nexus port
        self.password = self.config.get("redis_password", "QuantumNexus2025")
        self.db = self.config.get("redis_db", 0)
        self.is_connected = False
        logger.info(f"RedisConnection initialized with host={self.host}, port={self.port}")

    async def connect(self) -> bool:
        """Connect to Redis server with retry logic."""
        if self._client is not None:
            logger.warning("Redis connection already established or attempted")
            return True  # Already connected
        
        logger.info(f"Attempting to connect to Redis at {self.host}:{self.port} with DB {self.db}")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use redis.asyncio module correctly
                from redis.asyncio import Redis as AsyncRedis
                self._client = AsyncRedis(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    db=self.db,
                    decode_responses=True
                )
                # Test the connection
                await self._client.ping()
                self.is_connected = True
                logger.info("Redis connection established successfully")
                if self.event_bus:
                    await self.event_bus.publish("redis.connection.status", {"status": "connected", "message": "Redis connected successfully"})
                return True
            except Exception as e:
                self.is_connected = False
                self._client = None
                logger.error(f"Failed to connect to Redis (attempt {attempt+1}/{max_retries}): {e}")
                logger.error(f"Connection parameters used: host={self.host}, port={self.port}, db={self.db}")
                if self.event_bus:
                    await self.event_bus.publish("redis.connection.status", {"status": "error", "message": str(e)})
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)  # Wait before retrying
        logger.error("All retry attempts failed.")
        return False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self.is_connected = False
            logger.info("Redis connection closed")
            if self.event_bus:
                await self.event_bus.publish("redis.disconnected", {"status": "disconnected"})

    async def get(self, key: str) -> Optional[str]:
        if not self.is_connected:
            logger.error("Cannot get value: Redis is not connected")
            return None
        try:
            value = await self._client.get(key)
            logger.debug(f"Redis GET {key} -> {value}")
            return value
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, expire_seconds: Optional[int] = None) -> bool:
        if not self.is_connected:
            logger.error("Cannot set value: Redis is not connected")
            return False
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            await self._client.set(key, value)
            if expire_seconds:
                await self._client.expire(key, expire_seconds)
            logger.debug(f"Redis SET {key} <- {value}")
            return True
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        if not self.is_connected:
            logger.error("Cannot delete key: Redis is not connected")
            return False
        try:
            await self._client.delete(key)
            logger.debug(f"Redis DELETE {key}")
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False

    async def _handle_get_request(self, event_type: str, data: Dict[str, Any]) -> None:
        key = data.get("key")
        if not key:
            logger.error("Redis GET request missing key")
            return
        value = await self.get(key)
        if self.event_bus:
            await self.event_bus.publish("redis.get.response", {"key": key, "value": value, "request_id": data.get("request_id")})

    async def _handle_set_request(self, event_type: str, data: Dict[str, Any]) -> None:
        key = data.get("key")
        value = data.get("value")
        expire_seconds = data.get("expire_seconds")
        if not key:
            logger.error("Redis SET request missing key")
            return
        success = await self.set(key, value, expire_seconds)
        if self.event_bus:
            await self.event_bus.publish("redis.set.response", {"key": key, "success": success, "request_id": data.get("request_id")})

    async def _handle_delete_request(self, event_type: str, data: Dict[str, Any]) -> None:
        key = data.get("key")
        if not key:
            logger.error("Redis DELETE request missing key")
            return
        success = await self.delete(key)
        if self.event_bus:
            await self.event_bus.publish("redis.delete.response", {"key": key, "success": success, "request_id": data.get("request_id")})

    def subscribe_to_events(self) -> None:
        if not self.event_bus:
            logger.warning("Cannot subscribe to events: No event bus available")
            return
        self.event_bus.subscribe_async("redis.get", self._handle_get_request)
        self.event_bus.subscribe_async("redis.set", self._handle_set_request)
        self.event_bus.subscribe_async("redis.delete", self._handle_delete_request)
        logger.info("RedisConnection subscribed to event bus events")

# For testing
if __name__ == "__main__":
    async def test_redis():
        from core.event_bus import EventBus
        event_bus = EventBus()
        redis_conn = RedisConnection(event_bus)
        result = await redis_conn.connect()
        print(f"Redis connection result: {result}")
        return result
    
    asyncio.run(test_redis())
