#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import time
import threading
import json
from typing import Dict, Any, Optional, Union

# State-of-the-art 2025 pattern: Declare constants before try/except to avoid Pyright errors
HAS_REDIS = False
REDIS_AVAILABLE = False
redis_import_successful = False
Redis = None  # type: ignore[misc]
RedisError = Exception  # type: ignore[misc]

try:
    import redis  # type: ignore[import]
    from redis import Redis  # type: ignore[import]
    from redis.exceptions import RedisError  # type: ignore[import]
    HAS_REDIS = True  # type: ignore[misc]
    REDIS_AVAILABLE = True  # type: ignore[misc]
    redis_import_successful = True  # type: ignore[misc]
except ImportError:
    # Redis package not available - graceful degradation (no auto-install)
    logging.getLogger("KingdomAI.RedisConnector").warning("⚠️ Redis package not installed - running in mock mode")


class RedisConnector:
    """Redis connection manager for Kingdom AI system."""

    def __init__(self, event_bus=None):
        self.logger = logging.getLogger("KingdomAI.RedisConnector")
        self.event_bus = event_bus
        self.redis_client = None
        self.is_connected = False
        self.use_mock = False
        self.config = {
            'host': '127.0.0.1',
            'port': 6380,  # Correct port for Kingdom AI Redis Quantum Nexus
            'password': 'QuantumNexus2025'
        }
        self._load_config()
        self._connect()
        self.running = True
        self._start_monitoring()

    def _load_config(self):
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "config", "redis_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.config.update(config)
        except Exception as e:
            self.logger.error(f"Error loading Redis configuration: {str(e)}")

    def _connect(self):
        if not HAS_REDIS:
            self.logger.error("Redis package not installed")
            return

        try:
            host = self.config.get('host', 'localhost')
            port = self.config.get('port', 6380)
            password = self.config.get('password', 'QuantumNexus2025')

            self.redis_client = Redis(
                host=host,
                port=port,
                password=password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # CRITICAL FIX: Catch MISCONF error and fix it
            try:
                ping_result = self.redis_client.ping()
                if not ping_result:
                    raise RedisError("Ping failed")
            except Exception as ping_err:
                if "MISCONF" in str(ping_err):
                    self.logger.warning("Redis MISCONF detected - fixing...")
                    # Use config_set which works even with MISCONF for CONFIG commands
                    try:
                        # CONFIG SET is allowed even when writes are disabled
                        import redis.client
                        # Create a new connection just for CONFIG
                        config_client = Redis(
                            host=host, port=port, password=password,
                            decode_responses=False  # Don't decode for CONFIG commands
                        )
                        config_client.config_set('stop-writes-on-bgsave-error', 'no')
                        self.logger.info("✅ Redis MISCONF fixed (stop-writes-on-bgsave-error=no)")
                        # Now retry ping with original client
                        ping_result = self.redis_client.ping()
                        if not ping_result:
                            raise RedisError("Ping failed after MISCONF fix")
                    except Exception as fix_err:
                        self.logger.error(f"Could not fix MISCONF: {fix_err}")
                        raise
                else:
                    raise

            self.is_connected = True
            self.use_mock = False
            self.logger.info("Redis Quantum Nexus connection established successfully on port 6380")
        except Exception as conn_err:
            # Try to auto-start Redis server
            self.logger.warning(f"Redis connection failed: {conn_err}")
            self.logger.info("🚀 Attempting to auto-start Redis server...")
            
            if self._try_start_redis():
                # Retry connection after starting
                try:
                    time.sleep(2)  # Wait for Redis to start
                    self.redis_client = Redis(
                        host=host, port=port, password=password,
                        decode_responses=True, socket_connect_timeout=5
                    )
                    # CRITICAL FIX: Set config BEFORE ping
                    try:
                        self.redis_client.execute_command('CONFIG', 'SET', 'stop-writes-on-bgsave-error', 'no')
                        self.logger.info("✅ Redis MISCONF protection enabled")
                    except Exception:
                        pass
                    
                    if self.redis_client.ping():
                        self.is_connected = True
                        self.use_mock = False
                        self.logger.info("✅ Redis auto-started and connected successfully")
                        return
                except Exception:
                    pass
            
            # GRACEFUL DEGRADATION: Use mock mode instead of hard-failing
            self.is_connected = False
            self.use_mock = True
            self.redis_client = None
            self.logger.warning("⚠️ Redis unavailable - running in mock mode (caching disabled)")
            self.logger.info("ℹ️ To enable Redis: docker run -d -p 6380:6379 redis:alpine --requirepass QuantumNexus2025")
    
    def _try_start_redis(self):
        """Attempt to start Redis server automatically."""
        import subprocess
        import platform
        
        try:
            system = platform.system().lower()
            
            if system == "windows":
                # Try to start Redis on Windows
                redis_paths = [
                    r"C:\Program Files\Redis\redis-server.exe",
                    r"C:\Redis\redis-server.exe",
                    os.path.expanduser(r"~\Redis\redis-server.exe"),
                ]
                for redis_path in redis_paths:
                    if os.path.exists(redis_path):
                        subprocess.Popen([redis_path, "--port", "6380", "--requirepass", "QuantumNexus2025"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        self.logger.info(f"✅ Started Redis from {redis_path}")
                        return True
                
                # Try docker
                try:
                    subprocess.run(["docker", "run", "-d", "--name", "kingdom-redis",
                                  "-p", "6380:6379", "redis:alpine", "--requirepass", "QuantumNexus2025"],
                                 capture_output=True, timeout=30)
                    self.logger.info("✅ Started Redis via Docker")
                    return True
                except Exception:
                    pass
            else:
                # Linux/Mac - try systemctl or docker
                try:
                    subprocess.run(["redis-server", "--port", "6380", "--requirepass", "QuantumNexus2025", "--daemonize", "yes"],
                                 capture_output=True, timeout=10)
                    self.logger.info("✅ Started Redis server")
                    return True
                except Exception:
                    pass
            
            return False
        except Exception as e:
            self.logger.debug(f"Could not auto-start Redis: {e}")
            return False

    def _start_monitoring(self):
        self.reconnect_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self.reconnect_thread.start()

    def _monitor_connection(self):
        while self.running:
            if not self.redis_client or self.use_mock:
                time.sleep(15)
                continue
            try:
                ping_result = self.redis_client.ping()
                if not ping_result:
                    self.is_connected = False
            except Exception:
                self.is_connected = False
            time.sleep(15)

    def set_event_bus(self, event_bus):
        self.event_bus = event_bus

    def _handle_shutdown(self, _):
        self.close()

    async def initialize(self):
        return self.is_connected

    def get(self, key):
        try:
            return self.redis_client.get(key)
        except Exception as e:
            self.logger.error(f"Error getting key {key}: {str(e)}")
            return None

    def set(self, key, value, ex=None):
        try:
            return self.redis_client.set(key, value, ex=ex)
        except Exception as e:
            self.logger.error(f"Error setting key {key}: {str(e)}")
            return False

    def delete(self, key):
        try:
            return self.redis_client.delete(key)
        except Exception as e:
            return 0

    def exists(self, key):
        try:
            return self.redis_client.exists(key)
        except Exception as e:
            return False

    def keys(self, pattern="*"):
        try:
            return self.redis_client.keys(pattern)
        except Exception as e:
            return []

    def hmset(self, key, mapping):
        try:
            return self.redis_client.hset(key, mapping=mapping)
        except Exception as e:
            return False

    def hgetall(self, key):
        try:
            return self.redis_client.hgetall(key)
        except Exception as e:
            return {}

    def json_set(self, key, value):
        """Set JSON value - uses standard Redis set with JSON serialization."""
        try:
            import json
            json_str = json.dumps(value)
            return self.redis_client.set(key, json_str)
        except Exception as e:
            self.logger.debug(f"json_set failed: {e}")
            return False

    def json_get(self, key):
        """Get JSON value - uses standard Redis get with JSON deserialization."""
        try:
            import json
            value = self.redis_client.get(key)
            if value:
                # Ensure value is string for json.loads
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                return json.loads(str(value))
            return None
        except Exception as e:
            self.logger.debug(f"json_get failed: {e}")
            return None

    def publish(self, channel, message):
        try:
            return self.redis_client.publish(channel, message)
        except Exception as e:
            return 0

    def ping(self):
        try:
            return self.redis_client.ping()
        except Exception as e:
            return False

    def health_check(self) -> bool:
        """Return True if Redis appears healthy.

        Uses the existing connection state and a lightweight ping to
        confirm connectivity. This method is used by higher-level
        components (e.g. TradingComponent) to gate startup on Redis.
        """
        if not self.is_connected or not self.redis_client:
            return False
        return bool(self.ping())

    def close(self):
        self.running = False
        if hasattr(self, 'reconnect_thread') and self.reconnect_thread and self.reconnect_thread.is_alive():
            self.reconnect_thread.join(timeout=1.0)
        if not self.use_mock and hasattr(self.redis_client, 'close'):
            try:
                self.redis_client.close()
            except Exception:
                pass
        self.is_connected = False

    def connect(self):
        return self._connect()

    def get_client(self):
        return self.redis_client


# Alias for backward compatibility
RedisQuantumNexusConnector = RedisConnector

# Create alias for compatibility  
RedisQuantumNexusConnector = RedisConnector

# Export list - PRODUCTION ONLY
__all__ = [
    'redis_import_successful',
    'REDIS_AVAILABLE', 
    'RedisConnector',
    'RedisQuantumNexusConnector',
    'Redis',
    'RedisError',
    'HAS_REDIS'
]
