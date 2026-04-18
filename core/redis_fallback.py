
# core/redis_fallback.py
import logging
from collections import defaultdict

logger = logging.getLogger('KingdomAI')

class RedisFallbackManager:
    """Fallback in-memory store when Redis is unavailable."""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.data_store = defaultdict(dict)
        self.running = False
        logger.info("RedisFallbackManager initialized")
        
    async def initialize(self):
        """Initialize the fallback manager."""
        await self.event_bus.subscribe_sync("redis.get", self._handle_get)
        await self.event_bus.subscribe_sync("redis.set", self._handle_set)
        await self.event_bus.subscribe_sync("redis.delete", self._handle_delete)
        self.running = True
        logger.info("Redis fallback initialized and running")
        return True
        
    async def _handle_get(self, data):
        """Handle get requests."""
        if not data or 'key' not in data:
            return
            
        namespace = data.get('namespace', 'default')
        key = data['key']
        
        if key in self.data_store[namespace]:
            value = self.data_store[namespace][key]
            await self.event_bus.publish("redis.response", {
                "operation": "get",
                "success": True,
                "key": key,
                "value": value
            })
        else:
            await self.event_bus.publish("redis.response", {
                "operation": "get",
                "success": False,
                "key": key,
                "error": "Key not found"
            })
            
    async def _handle_set(self, data):
        """Handle set requests."""
        if not data or 'key' not in data or 'value' not in data:
            return
            
        namespace = data.get('namespace', 'default')
        key = data['key']
        value = data['value']
        
        self.data_store[namespace][key] = value
        await self.event_bus.publish("redis.response", {
            "operation": "set",
            "success": True,
            "key": key
        })
        
    async def _handle_delete(self, data):
        """Handle delete requests."""
        if not data or 'key' not in data:
            return
            
        namespace = data.get('namespace', 'default')
        key = data['key']
        
        if key in self.data_store[namespace]:
            del self.data_store[namespace][key]
            
        await self.event_bus.publish("redis.response", {
            "operation": "delete",
            "success": True,
            "key": key
        })
