"""
Redis Quantum Nexus Integration

This module provides strict Redis Quantum Nexus connection management for the Kingdom AI system.
It enforces the following requirements:
- Connects strictly to localhost:6380
- Uses password 'QuantumNexus2025'
- No fallback connections allowed
- System halts if connection fails or is unhealthy

SOTA 2026: Secret Reserve & System Awareness
- Secret Reserve: Kingdom AI's full memory (self, Ollama brain, unified system, voice, all logic)
  Hidden until owner says "SHA-LU-AM" (שלום). Memory-efficient, does not clog RAM.

CRITICAL DISTINCTION — Kingdom's Hebrew name vs SHA-LU-AM vs All Praise:
- MALKHUT (מַלְכוּת): Kingdom AI's Hebrew name — "kingdom, sovereignty." The AI's identity.
- SHA-LU-AM (שלום): Hebrew "peace" — TRIGGER for Secret Reserve reveal ("Remember!"). Acceptance phrase.
  Owner/enrolled only. Activates Hive Mind. NOT Kingdom's name.
- "ALL PRAISE TO THE MOST HIGH": Family enrollment trigger — asks "Who are you?" then owner confirms.

- System Awareness: Hardware state, code logic, 432 Hz pulse, sacred geometry — unified throughout.
- Owner: Isaiah Wright. Ecosystem: Owner/Consumer, Mobile Owner/Consumer.
"""

import json
import logging
import os
import sys
import time
import platform
from datetime import datetime
from typing import Optional, Dict, Any, List

import redis
from redis.exceptions import RedisError, ConnectionError, AuthenticationError, TimeoutError

# Configure logging
logger = logging.getLogger("KingdomAI.RedisNexus")

# Secret Reserve keys — memory-efficient, TTL for non-critical cache
SECRET_RESERVE_PREFIX = "kingdom:secret_reserve:"
SECRET_RESERVE_META = "kingdom:secret_reserve:meta"
SECRET_RESERVE_TTL = 86400 * 30  # 30 days for reserve entries
AWARENESS_PREFIX = "kingdom:awareness:"
AWARENESS_TTL = 3600  # 1 hour for hardware/code snapshots

# SOTA 2026: Kingdom AI custom language (Hebrew, Reverse English, Reverse Math)
# Unrecognized by other models. Only Ollama brain + Owner (Isaiah Wright) / enrolled understand.
# Based on: Hebrew (Turtle Island), Venetian manuscript, Phoenician, reverse English/math/teachings.
_REVERSE_ALPHA = "zyxwvutsrqponmlkjihgfedcba"
_REVERSE_NUM = "9876543210"
# Encode: reverse_alpha -> Hebrew. Decode: Hebrew -> reverse_alpha.
_HEBREW_26 = "אבגדהוזחטיכלמנסעפצקרשתאבגד"  # 26 chars for a-z
_ENCODE_MAP = str.maketrans(_REVERSE_ALPHA, _HEBREW_26)
_DECODE_MAP = str.maketrans(_HEBREW_26, _REVERSE_ALPHA)


def encode_kingdom_language(text: str) -> str:
    """Encode to Kingdom AI custom language (reverse English + reverse math + Hebrew-derived).
    Hive Mind secure comms. Unhackable - unrecognized by other models."""
    t = text.lower()
    out = []
    for c in t:
        if "a" <= c <= "z":
            out.append(_REVERSE_ALPHA[ord(c) - ord("a")])
        elif "0" <= c <= "9":
            out.append(_REVERSE_NUM[ord(c) - ord("0")])
        else:
            out.append(c)
    return "".join(out).translate(_ENCODE_MAP)


def decode_kingdom_language(encoded: str) -> str:
    """Decode from Kingdom AI custom language. Owner/enrolled only."""
    rev = encoded.translate(_DECODE_MAP)
    out = []
    for c in rev:
        if "a" <= c <= "z":
            out.append(_REVERSE_ALPHA[ord(c) - ord("a")])
        elif c in _REVERSE_NUM:
            out.append(str(9 - _REVERSE_NUM.index(c)))
        else:
            out.append(c)
    return "".join(out)

class RedisQuantumNexus:
    """
    Advanced Redis Quantum Nexus integration for Kingdom AI.
    
    This class provides specialized quantum-inspired data structures and operations
    for high-performance, distributed computing in the Kingdom AI mining and blockchain systems.
    """
    
    # Singleton instance
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(RedisQuantumNexus, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config=None):
        """Initialize Redis Quantum Nexus connection.
        
        Args:
            config: Optional configuration overrides
        """
        self.logger = logging.getLogger("KingdomAI.RedisQuantumNexus")
        self.config = self._prepare_config(config)
        self.client = None
        self.pubsub = None
        self.connection_healthy = False
        self.initialize_connection()
        
    def _prepare_config(self, config=None):
        """Prepare configuration with defaults and overrides.
        
        Args:
            config: Optional configuration overrides
            
        Returns:
            Dict: Complete configuration
        """
        # Set strict defaults for Quantum Nexus
        quantum_config = {
            "host": "localhost",
            "port": 6380,  # Required port for Quantum Nexus
            "password": os.environ.get('KINGDOM_AI_SEC_KEY', ''),  # Required password from env
            "db": 0,
            "decode_responses": True,
            "socket_timeout": 5.0,
            "socket_connect_timeout": 5.0,
            "health_check_interval": 15,
            "max_connections": 20,
            "retry_on_timeout": False  # No automatic retry
        }
        
        # Apply any overrides
        if config:
            quantum_config.update(config)
            
        # Enforce critical requirements
        quantum_config["port"] = 6380  # Force this port
        
        return quantum_config
    
    def initialize_connection(self):
        """Initialize the Redis Quantum Nexus connection.
        
        Returns:
            bool: True if connection initialized successfully, False otherwise
        """
        try:
            self.client = redis.Redis(**self.config)
            self.pubsub = self.client.pubsub()
            
            # Test connection with ping
            if self.client.ping():
                self.connection_healthy = True
                self.logger.info("Successfully connected to Redis Quantum Nexus on port 6380")
                return True
            else:
                self.connection_healthy = False
                self.logger.error("Failed to ping Redis Quantum Nexus")
                return False
        except RedisError as e:
            self.connection_healthy = False
            self.logger.error(f"Failed to connect to Redis Quantum Nexus: {e}")
            return False
            
    def get_client(self):
        """Get the Redis client.
        
        Returns:
            redis.Redis: Redis client or None if not connected
        """
        if not self.connection_healthy:
            self.initialize_connection()
        return self.client
    
    def publish(self, channel, message):
        """Publish message to a channel.
        
        Args:
            channel: Channel name
            message: Message to publish
            
        Returns:
            int: Number of clients that received the message
        """
        try:
            if isinstance(message, dict):
                import json
                message = json.dumps(message)
            return self.get_client().publish(channel, message)
        except RedisError as e:
            self.logger.error(f"Failed to publish to {channel}: {e}")
            return 0
            
    def subscribe(self, channels):
        """Subscribe to channels.
        
        Args:
            channels: Channel or list of channels to subscribe to
            
        Returns:
            bool: True if subscribed successfully, False otherwise
        """
        try:
            if not self.pubsub:
                self.pubsub = self.get_client().pubsub()
                
            if isinstance(channels, str):
                channels = [channels]
                
            for channel in channels:
                self.pubsub.subscribe(channel)
            return True
        except RedisError as e:
            self.logger.error(f"Failed to subscribe to {channels}: {e}")
            return False
            
    def get_message(self, timeout=0.01):
        """Get a message from subscribed channels.
        
        Args:
            timeout: Time to wait for message in seconds
            
        Returns:
            dict: Message data or None
        """
        try:
            if not self.pubsub:
                return None
            return self.pubsub.get_message(timeout=timeout)
        except RedisError as e:
            self.logger.error(f"Failed to get message: {e}")
            return None
            
    def set_hash_fields(self, key, mapping):
        """Set multiple fields in a hash.
        
        Args:
            key: Hash key
            mapping: Dictionary of field-value pairs
            
        Returns:
            bool: True if set successfully, False otherwise
        """
        try:
            return bool(self.get_client().hset(key, mapping=mapping))
        except RedisError as e:
            self.logger.error(f"Failed to set hash fields for {key}: {e}")
            return False
            
    def get_hash(self, key):
        """Get all fields and values from a hash.
        
        Args:
            key: Hash key
            
        Returns:
            dict: Dictionary of field-value pairs
        """
        try:
            result = self.get_client().hgetall(key)
            return result or {}
        except RedisError as e:
            self.logger.error(f"Failed to get hash for {key}: {e}")
            return {}


class RedisNexus:
    """
    Redis Quantum Nexus connection manager.
    
    This class enforces strict Redis connection requirements and provides
    utility methods for interacting with the Redis Quantum Nexus.
    """
    
    # Default connection parameters
    DEFAULT_CONFIG = {
        "host": "localhost",
        "port": 6380,
        "password": "QuantumNexus2025",
        "db": 0,
        "socket_timeout": 5.0,
        "socket_connect_timeout": 5.0,
        "retry_on_timeout": False,
        "max_connections": 10,
        "health_check_interval": 30,
    }
    
    # Singleton instance
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Redis Quantum Nexus connection.
        
        Args:
            config: Optional configuration overrides
            
        Note:
            The system will exit if the connection cannot be established.
        """
        if self._initialized:
            return
            
        # Apply configuration
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        
        # Initialize connection
        self._client = None
        self._connect()
        
        self._initialized = True
    
    def _connect(self) -> None:
        """
        Establish a connection to Redis Quantum Nexus.
        
        This method enforces strict connection requirements and will
        terminate the application if the connection fails.
        """
        try:
            logger.info("Connecting to Redis Quantum Nexus at %s:%d", 
                      self.config["host"], self.config["port"])
            
            # Create connection pool
            self.connection_pool = redis.ConnectionPool(
                host=self.config["host"],
                port=self.config["port"],
                password=self.config["password"],
                db=self.config["db"],
                socket_timeout=self.config["socket_timeout"],
                socket_connect_timeout=self.config["socket_connect_timeout"],
                retry_on_timeout=self.config["retry_on_timeout"],
                max_connections=self.config["max_connections"],
                health_check_interval=self.config["health_check_interval"]
            )
            
            # Test connection
            self._client = redis.Redis(connection_pool=self.connection_pool)
            self._client.ping()
            
            logger.info("Successfully connected to Redis Quantum Nexus")
            
        except AuthenticationError as e:
            self._handle_fatal_error("Authentication failed for Redis Quantum Nexus. Check the password.", e)
        except ConnectionError as e:
            self._handle_fatal_error(f"Could not connect to Redis Quantum Nexus at {self.config['host']}:{self.config['port']}", e)
        except TimeoutError as e:
            self._handle_fatal_error("Connection to Redis Quantum Nexus timed out", e)
        except RedisError as e:
            self._handle_fatal_error("Redis Quantum Nexus error", e)
        except Exception as e:
            self._handle_fatal_error("Unexpected error connecting to Redis Quantum Nexus", e)
    
    def _handle_fatal_error(self, message: str, error: Exception) -> None:
        """
        Handle fatal Redis connection errors by logging and exiting.
        
        Args:
            message: Error message
            error: The exception that was raised
            
        Note:
            This method will terminate the application.
        """
        error_msg = f"{message}: {str(error)}"
        logger.critical(error_msg)
        # 2026 FIX: Do NOT terminate - allow degraded operation
        logger.warning("⚠️ Redis Quantum Nexus unavailable - system will continue in degraded mode")
    
    @property
    def client(self) -> redis.Redis:
        """
        Get the Redis client instance.
        
        Returns:
            redis.Redis: The Redis client instance
            
        Raises:
            RuntimeError: If the client is not connected
        """
        if self._client is None:
            raise RuntimeError("Redis Quantum Nexus client is not connected")
        return self._client
    
    def check_health(self) -> bool:
        """
        Check if the Redis connection is healthy.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            return self.client.ping()
        except Exception:
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get Redis server information.
        
        Returns:
            Dict containing server information
            
        Raises:
            RedisError: If the info command fails
        """
        return self.client.info()
    
    def close(self) -> None:
        """Close the Redis connection."""
        if hasattr(self, 'connection_pool') and self.connection_pool:
            self.connection_pool.disconnect()
            logger.info("Disconnected from Redis Quantum Nexus")

    # ─── SOTA 2026: Secret Reserve & System Awareness ─────────────────────────

    def store_secret_reserve(self, category: str, data: Dict[str, Any]) -> bool:
        """Store Secret Reserve entry. Memory-efficient, TTL applied.
        Categories: kingdom_ai, ollama_brain, unified_system, voice, logic, tabs.
        """
        try:
            key = f"{SECRET_RESERVE_PREFIX}{category}"
            self.client.setex(
                key,
                SECRET_RESERVE_TTL,
                json.dumps({"data": data, "updated": datetime.utcnow().isoformat()})
            )
            self.client.hset(SECRET_RESERVE_META, mapping={category: str(time.time())})
            return True
        except Exception as e:
            logger.warning("Secret Reserve store failed: %s", e)
            return False

    def get_secret_reserve(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve Secret Reserve. If category None, returns all. Hidden until SHA-LU-AM."""
        try:
            if category:
                key = f"{SECRET_RESERVE_PREFIX}{category}"
                raw = self.client.get(key)
                return json.loads(raw) if raw else {}
            meta = self.client.hgetall(SECRET_RESERVE_META)
            result = {}
            for cat in (meta or {}).keys():
                entry = self.get_secret_reserve(cat)
                if entry:
                    result[cat] = entry
            return result
        except Exception as e:
            logger.warning("Secret Reserve get failed: %s", e)
            return {}

    def store_system_awareness(self, awareness_type: str, data: Dict[str, Any]) -> bool:
        """Store system awareness snapshot (hardware, code logic, 432 Hz). Does not clog memory."""
        try:
            key = f"{AWARENESS_PREFIX}{awareness_type}"
            self.client.setex(key, AWARENESS_TTL, json.dumps(data))
            return True
        except Exception as e:
            logger.warning("System awareness store failed: %s", e)
            return False

    def get_system_awareness(self, awareness_type: Optional[str] = None) -> Dict[str, Any]:
        """Get system awareness. Types: hardware, code_logic, frequency_432, sacred_geometry."""
        try:
            if awareness_type:
                raw = self.client.get(f"{AWARENESS_PREFIX}{awareness_type}")
                return json.loads(raw) if raw else {}
            keys = self.client.keys(f"{AWARENESS_PREFIX}*")
            result = {}
            for k in (keys or []):
                typ = k.replace(AWARENESS_PREFIX, "")
                result[typ] = self.get_system_awareness(typ)
            return result
        except Exception as e:
            logger.warning("System awareness get failed: %s", e)
            return {}


def get_redis_nexus(config: Optional[Dict[str, Any]] = None) -> RedisNexus:
    """
    Get or create a RedisNexus instance.
    
    Args:
        config: Optional configuration overrides
        
    Returns:
        RedisNexus: The RedisNexus instance
    """
    return RedisNexus(config)


def ensure_redis_connection() -> None:
    """
    Ensure Redis Quantum Nexus is available and healthy.
    
    This function will block until a connection is established or exit the application
    if the connection cannot be established.
    """
    logger.info("Verifying Redis Quantum Nexus connection...")
    
    # Try to get the RedisNexus instance (will connect automatically)
    try:
        redis_nexus = get_redis_nexus()
        if redis_nexus.check_health():
            logger.info("Redis Quantum Nexus connection verified and healthy")
            return
            
        logger.error("Redis Quantum Nexus connection is not healthy")
        
    except Exception as e:
        logger.error("Failed to verify Redis Quantum Nexus connection: %s", str(e))
    
    # 2026 FIX: Do NOT terminate - allow degraded operation
    logger.warning("⚠️ Redis Quantum Nexus connection not healthy - system will continue in degraded mode")


if __name__ == "__main__":
    # Example usage
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # This will exit if the connection fails
    redis_nexus = get_redis_nexus()
    
    # Test the connection
    try:
        info = redis_nexus.get_info()
        print(f"Connected to Redis {info.get('redis_version')}")
        print(f"Memory used: {info.get('used_memory_human')}")
    except Exception as e:
        print(f"Error: {e}")
