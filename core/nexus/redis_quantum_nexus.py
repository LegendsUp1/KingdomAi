#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Redis Quantum Nexus for Kingdom AI.

This module provides connectivity to multiple Redis environments,
ensuring real-time data synchronization across the Kingdom AI system.
"""

# Type stub declarations for Pyright/IDE support
# Kingdom AI requires redis>=4.5.0 for proper asyncio support
# pyright: reportMissingImports=false

import asyncio
import logging
import traceback
import time
import json
from enum import Enum
from typing import Dict, List, Any, Optional, Union

# Import Redis directly - no fallbacks allowed
import redis.asyncio as redis_async

# Get Redis version correctly
def get_redis_version():
    try:
        # Try multiple methods to get the redis version
        import redis
        if hasattr(redis, '__version__'):
            return redis.__version__  # type: ignore[attr-defined]
        elif hasattr(redis, 'VERSION'):
            return '.'.join(map(str, redis.VERSION))  # type: ignore[attr-defined]
            
        # Try using pkg_resources
        try:
            import pkg_resources
            return pkg_resources.get_distribution('redis').version
        except (ImportError, pkg_resources.DistributionNotFound):
            pass
            
        # Last resort - check if redis package has version
        try:
            import redis
            if hasattr(redis, '__version__'):
                return redis.__version__  # type: ignore[attr-defined]
        except Exception:
            pass
            
        # If all else fails, assume a modern version
        return '5.0.0'  # Default to a version that meets requirements
    except Exception:
        return '5.0.0'  # Default to a version that meets requirements

redis_version = get_redis_version()
if redis_version < '4.5.0':
    error_msg = f"Redis version {redis_version} detected; Kingdom AI requires redis>=4.5.0 for async support"
    logging.critical(error_msg)
    raise ImportError(error_msg)

# Kingdom AI requires Redis - no fallbacks
REDIS_AVAILABLE = True
REDIS_VERSION = redis_version

# Replace redis global with redis_async for backwards compatibility    
redis = redis_async

logger = logging.getLogger(__name__)

class NexusEnvironment(Enum):
    """Redis Quantum Nexus environments."""
    CONFIG = 0      # System configuration
    MARKET = 1      # Market data
    TRADING = 2     # Trading operations
    MINING = 3      # Mining stats and blockchains
    WALLET = 4      # Wallet data
    SECURITY = 5    # Security and authentication
    ANALYTICS = 6   # Analytics and reporting
    VR = 7          # VR system data
    
    @classmethod
    def all(cls):
        """Return a list of all environment types as strings."""
        return [env.name for env in cls]
        
    @classmethod
    def from_string(cls, name: str):
        """Convert a string environment name to the corresponding enum value.
        
        Args:
            name: The environment name as a string
            
        Returns:
            NexusEnvironment: The corresponding enum value, or CONFIG if not found
        """
        try:
            return cls[name.upper()]
        except (KeyError, AttributeError):
            logger.warning(f"Unknown environment name: {name}, defaulting to CONFIG")
            return cls.CONFIG
            
    def __str__(self):
        """Return the environment name as a string."""
        return self.name


# Constants
EVENT_SYSTEM = "system"
EVENT_NEXUS = "nexus"
EVENT_REDIS = "redis"

class RedisQuantumNexus:
    """Redis Quantum Nexus for Kingdom AI with multiple environments."""
    
    def __init__(self, config=None, event_bus=None):
        self.config = config or {}
        self.event_bus = event_bus
        self.logger = logging.getLogger("KingdomAI.QuantumNexus")
        self.environments = {}
        self.default_host = self.config.get("redis_host", "localhost")
        self.default_port = self.config.get("redis_port", 6380)
        self.default_password = self.config.get("redis_password", "QuantumNexus2025")
        self.auto_reconnect = self.config.get("auto_reconnect", True)
        self.max_retries = self.config.get("max_retries", 10)
        self.initialized = False
        self.is_connected = False
        self.last_error = None
        self._lock = None  # Lazy initialization to avoid event loop context issues
        
        # Initialize class variables
        self.running = True
        self.connections = {}
        self.connection_pools = {}
        self.environment_status = {}
        self.environments_config = {}
        self.data_cache = {}
        self.package_data = {}
        self.package_registry = {}  # Package name -> {env_name -> version}
        self.monitor_thread = None
        self.redis = None
        self.connection_errors = {}
        self.retry_delay = self.config.get("retry_delay", 5)
        self.health_check_interval = int(self.config.get("health_check_interval", 60))
        self.is_initialized = False
        self.fallback_mode = self.config.get("fallback_mode", False)
        
        # Statistics
        self.stats = {
            "connections_attempted": 0,
            "connections_successful": 0,
            "connections_failed": 0,
            "operations_total": 0,
            "operations_successful": 0,
            "operations_failed": 0,
            "last_health_check": 0
        }
        
        logger.info("Redis Quantum Nexus instance created")
    
    @property
    def lock(self):
        """Lazy initialization of asyncio.Lock to ensure it's created in the right event loop context."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    async def initialize(self):
        """Initialize all Redis Quantum Nexus environments."""
        if self.is_initialized:
            self.logger.info("Redis Quantum Nexus already initialized")
            return True
            
        async with self.lock:
            if self.is_initialized:
                return True
                
            try:
                self.logger.info("Initializing Redis Quantum Nexus...")
            
                try:
                    import redis.asyncio as redis
                    self.redis = redis
                    # Store redis_async for creating async clients
                    self.redis_async = redis_async
                    self.logger.info("Redis module imported successfully")
                except ImportError as e:
                    self.logger.error(f"Failed to import Redis module: {e}")
                    self.logger.critical("Redis module import failed. System cannot continue without Redis.")
                    return False
                    
                env_configs = {}
            
                default_config = {
                "host": self.default_host,
                "port": self.default_port,
                "db": 0,
                "password": self.default_password,
                "decode_responses": False,  # Match working QuantumNexus pattern
                "socket_timeout": 2,  # Faster timeout
                "socket_connect_timeout": 2,  # Faster connect timeout
                "retry_on_timeout": False  # Don't retry - fail fast
                }
            
                if self.config.get("environments"):
                    self.logger.info("Using environment-specific Redis configurations")
                    env_configs = self.config.get("environments", {})
                else:
                    self.logger.info("Using default configuration for all environments")
                    for env in NexusEnvironment:
                        env_configs[env.name] = default_config.copy()
            
                # CRITICAL FIX: Only connect to CONFIG at startup - lazy load others
                # This prevents 30+ second blocking from connecting to 6+ environments
                config_env = NexusEnvironment.CONFIG
                config_env_config = env_configs.get(config_env.name, default_config).copy()
                
                try:
                    connect_success = await self.connect_environment(config_env)
                    if connect_success:
                        logger.info("✅ Redis Quantum Nexus CONFIG connected - other environments will connect on-demand")
                    else:
                        logger.warning("⚠️ Redis CONFIG connection failed - will retry on-demand")
                except Exception as e:
                    logger.warning(f"⚠️ Redis CONFIG connection error: {e} - will retry on-demand")
                
                # Mark other environments as pending (will connect lazily when accessed)
                for env in NexusEnvironment:
                    if env != config_env:
                        self.environment_status[env] = {"status": "pending", "message": "Will connect on-demand"}
            
                if not self.fallback_mode and self.health_check_interval > 0:
                    try:
                        # Use ensure_future instead of create_task to avoid nesting errors
                        self.monitor_task = asyncio.ensure_future(self._health_monitor())
                        self.logger.info(f"Health monitor started with interval {self.health_check_interval}s")
                    except Exception as e:
                        self.logger.error(f"Failed to start health monitor: {e}")
            
                self.is_initialized = True
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to initialize Redis Quantum Nexus: {e}")
                self.logger.error(traceback.format_exc())
                self.is_initialized = False
                self.logger.critical("Failed to initialize Redis Quantum Nexus. System cannot continue without Redis.")
                return False
    
    def check_connection(self, env_name=None):
        """Check if Redis connection is working."""
        try:
            if getattr(self, 'fallback_mode', False):
                return False
                
            if not self.redis:
                return False
                
            if env_name:
                try:
                    env = NexusEnvironment.from_string(env_name)
                    return self.environment_status.get(env, False)
                except Exception as e:
                    self.logger.error(f"Error checking {env_name} connection: {e}")
                    return False
                    
            if not self.environment_status:
                return False
                
            return any(self.environment_status.values())
            
        except Exception as e:
            self.logger.error(f"Error in check_connection: {e}")
            return False
    
    def test_connection(self, env_name=None):
        """Test if Redis connection is working."""
        self.logger.info(f"Testing Redis connection for environment: {env_name if env_name else 'all'}")
        return self.check_connection(env_name)
    
    async def connect_environment(self, environment) -> bool:
        """Connect to a specific nexus environment."""
        if isinstance(environment, str):
            try:
                env_enum = NexusEnvironment.from_string(environment)
                logger.info(f"Converting string environment '{environment}' to enum {env_enum}")
                environment = env_enum
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid environment name: {environment} - {e}")
                return False
                
        logger.info(f"Connecting to environment: {environment.name}")
        
        async with self.lock:
            if environment in self.connections and self.connections[environment]:
                try:
                    client = self.connections[environment]
                    await asyncio.wait_for(client.ping(), timeout=2.0)
                    logger.debug(f"Already connected to environment {environment}")
                    return True
                except Exception:
                    logger.debug(f"Connection to environment {environment} is stale, reconnecting")
                    await self.disconnect_environment(environment)
            
            env_config = self.environments_config.get(environment, {})
            
            host = env_config.get("host", self.default_host)
            port = env_config.get("port", self.default_port)
            password = env_config.get("password", self.default_password)
            db = env_config.get("db", 0)
            ssl = env_config.get("ssl", False)
            
            conn_timeout = env_config.get("connection_timeout", 3.0)
            socket_timeout = env_config.get("socket_timeout", 3.0)
            socket_connect_timeout = env_config.get("socket_connect_timeout", 3.0)
            
            try:
                # CRITICAL FIX: Use direct async Redis connection (no pool) - matches working QuantumNexus pattern
                # Skip connection pool overhead for faster, simpler connection
                client = redis_async.Redis(
                    host=host,
                    port=port,
                    password=password,
                    db=db,
                    socket_timeout=2.0,
                    socket_connect_timeout=2.0,
                    decode_responses=False,  # Match working QuantumNexus
                    retry_on_timeout=False  # Fail fast
                )
                
                try:
                    await asyncio.wait_for(client.ping(), timeout=5.0)
                    logger.info(f"✅ Redis Quantum Nexus {environment.name} connection verified")
                except asyncio.TimeoutError:
                    logger.warning(f"Redis Quantum Nexus {environment.name} connection timeout, will retry later")
                    self.environment_status[environment] = {
                        "status": "timeout",
                        "error": "Connection timeout",
                        "last_attempt": time.time()
                    }
                    return False
                except Exception as e:
                    logger.warning(f"Redis Quantum Nexus {environment.name} connection failed: {str(e)}, will retry later")
                    self.environment_status[environment] = {
                        "status": "error",
                        "error": str(e),
                        "last_attempt": time.time()
                    }
                    return False
                
                self.connections[environment] = client
                
                self.environment_status[environment] = {
                    "status": "online",
                    "connected_at": time.time(),
                    "last_used": time.time()
                }
                
                logger.info(f"Successfully connected to environment {environment}")
                return True
                
            except Exception as e:
                logger.warning(f"Error connecting to environment {environment}: {e}")
                self.environment_status[environment] = {
                    "status": "error",
                    "error": str(e),
                    "last_attempt": time.time()
                }
                return False
    
    async def disconnect_environment(self, environment) -> bool:
        """Disconnect from a specific nexus environment."""
        if isinstance(environment, str):
            try:
                env_enum = NexusEnvironment.from_string(environment)
                logger.info(f"Converting string environment '{environment}' to enum {env_enum}")
                environment = env_enum
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid environment name: {environment} - {e}")
                return False
                
        async with self.lock:
            logger.info(f"Disconnecting from environment: {environment.name}")
            
            if environment not in self.connections or not self.connections[environment]:
                logger.debug(f"Not connected to environment: {environment}")
                return True
            
            try:
                if environment in self.connection_pools:
                    self.connection_pools[environment].disconnect()
                
                del self.connections[environment]
                if environment in self.connection_pools:
                    del self.connection_pools[environment]
                
                self.environment_status[environment] = {
                    "connected": False,
                    "connected_at": None,
                    "last_checked": time.time(),
                    "status": "disconnected",
                    "retries": 0
                }
                
                logger.info(f"Disconnected from environment: {environment}")
                return True
                
            except Exception as e:
                logger.error(f"Error disconnecting from environment {environment}: {e}")
                return False
    
    async def _health_monitor(self):
        """Background task to monitor Redis health."""
        self.logger.info("Starting Redis health monitor task")
        
        if not hasattr(self, 'monitor_task'):
            self.monitor_task = None
            
        try:
            while self.running:
                try:
                    if not self.running:
                        self.logger.info("Health monitor shutting down (pre-check)")
                        break
                    
                    for env_name, conn in list(self.connections.items()):
                        try:
                            if not self.running:
                                self.logger.info("Health monitor shutting down (during checks)")
                                break
                                
                            env = env_name if isinstance(env_name, NexusEnvironment) else NexusEnvironment.from_string(env_name)
                            
                            ping_task = asyncio.create_task(conn.ping())
                            try:
                                await asyncio.wait_for(ping_task, timeout=0.5)
                            except asyncio.TimeoutError:
                                self.logger.warning(f"Ping to {env_name} environment timed out")
                                continue
                            
                        except asyncio.CancelledError:
                            self.logger.info("Health monitor cancelled (during ping)")
                            raise
                        except Exception as e:
                            if not self.running:
                                self.logger.info("Health monitor shutting down (during exception)")
                                break
                            self.logger.warning(f"Connection to {env_name} is down: {e}")
                    
                    if self.running:
                        self.stats["last_health_check"] = int(time.time())
                    
                except asyncio.CancelledError:
                    self.logger.info("Health monitor cancelled (during environment checks)")
                    raise
                except Exception as e:
                    self.logger.error(f"Error in health monitor: {e}")
                
                if not self.running:
                    self.logger.info("Health monitor shutting down (pre-sleep)")
                    break
                
                interval = int(self.health_check_interval)
                try:
                    for _ in range(min(interval, 10)):
                        if not self.running:
                            self.logger.info("Health monitor shutting down (during sleep)")
                            break
                        await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    self.logger.info("Health monitor sleep cancelled")
                    raise
        except asyncio.CancelledError:
            self.logger.info("Redis health monitor task cancelled")
            self.monitor_task = None
            return
        except Exception as e:
            self.logger.error(f"Redis health monitor task failed: {e}")
        finally:
            self.logger.info("Redis health monitor task stopped")
            self.monitor_task = None
    
    async def cleanup(self) -> bool:
        """Clean up all resources and connections."""
        logger.info("Cleaning up Redis Quantum Nexus")
        
        self.running = False
        logger.info("Set running flag to False for graceful task termination")
        
        lock_acquired = False
        try:
            try:
                lock_acquired = await asyncio.wait_for(self.lock.acquire(), timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("Lock acquisition timed out during cleanup, continuing without lock")
            except Exception as e:
                logger.error(f"Error acquiring lock: {e}")
        except Exception as e:
            logger.error(f"Unexpected cleanup error: {e}")
            return False
            
        try:
            if not self.is_initialized:
                logger.debug("Redis Quantum Nexus is not initialized, nothing to clean up")
                return True
                
            if hasattr(self, 'monitor_task') and self.monitor_task:
                if not self.monitor_task.done() and not self.monitor_task.cancelled():
                    try:
                        logger.info("Cancelling Redis health monitor task")
                        temp_task = self.monitor_task
                        self.monitor_task = None
                        
                        temp_task.cancel()
                        try:
                            await asyncio.wait_for(asyncio.shield(temp_task), timeout=0.5)
                            logger.debug("Monitor task cancellation completed within timeout")
                        except asyncio.TimeoutError:
                            logger.warning("Monitor task cancellation timed out, continuing cleanup")
                        except asyncio.CancelledError:
                            logger.debug("Monitor task successfully cancelled")
                        except Exception as e:
                            logger.error(f"Unexpected error waiting for task cancellation: {e}")
                    except Exception as e:
                        logger.error(f"Error cancelling monitor task: {e}")
                else:
                    logger.debug("Monitor task was already done or cancelled")
                    self.monitor_task = None
            
            environments_to_disconnect = list(self.connections.keys())
            start_time = time.time()
            max_disconnect_time = 3.0
            
            for environment in environments_to_disconnect:
                if time.time() - start_time > max_disconnect_time:
                    logger.warning("Maximum disconnect time exceeded, forcing cleanup")
                    self.connections.clear()
                    self.connection_pools.clear()
                    break
                    
                try:
                    remaining_time = max(0.1, max_disconnect_time - (time.time() - start_time))
                    disconnect_task = asyncio.create_task(self.disconnect_environment(environment))
                    try:
                        await asyncio.wait_for(disconnect_task, timeout=min(0.3, remaining_time))
                    except asyncio.TimeoutError:
                        logger.warning(f"Disconnect from {environment} timed out, continuing")
                        if environment in self.connections:
                            del self.connections[environment]
                        if environment in self.connection_pools:
                            del self.connection_pools[environment]
                except Exception as e:
                    logger.error(f"Error disconnecting from environment {environment}: {e}")
                    if environment in self.connections:
                        del self.connections[environment]
                    if environment in self.connection_pools:
                        del self.connection_pools[environment]
            
            self.monitor_task = None
            self.monitor_thread = None
            self.connections = {}
            self.connection_pools = {}
            self.environment_status = {}
            self.environments_config = {}
            self.data_cache = {}
            self.package_data = {}
            self.package_registry = {}
            self.running = False
            self.is_initialized = False
            
            logger.info("Redis Quantum Nexus cleaned up successfully")
            return True
        except Exception as e:
            logger.error(f"Error during Redis Quantum Nexus cleanup: {e}")
            return False
        finally:
            if lock_acquired:
                self.lock.release()
                logger.debug("Lock released during cleanup")
    
    async def shutdown(self):
        """Close all Redis connections and shut down the Nexus."""
        self.logger.info("Shutting down Redis Quantum Nexus")
        self.running = False
        
        if hasattr(self, 'monitor_task') and self.monitor_task:
            try:
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                self.logger.error(f"Error cancelling monitor task: {e}")
                
        for env_name, conn in list(self.connections.items()):
            try:
                await conn.close()
                self.logger.info(f"Closed connection to {env_name}")
            except Exception as e:
                self.logger.error(f"Error closing connection to {env_name}: {e}")
                
        self.connections = {}
        self.connection_pools = {}
        self.environment_status = {}
        self.is_connected = False
        self.is_initialized = False
        self.initialized = False
        
        self.logger.info("Redis Quantum Nexus shut down complete")
        return True
    
    async def load_package_registry(self) -> bool:
        """Load package registry from Redis."""
        try:
            if not self.connections or not any(self.connections.values()):
                self.logger.error("No Redis connections available to load package registry")
                return False
            
            # Get first available connection
            client = next(iter(self.connections.values()))
            
            # Load complete registry
            registry_data = await client.get("quantum_nexus:package_registry")
            if registry_data:
                self.package_registry = json.loads(registry_data)
                self.logger.info(f"✅ Loaded package registry: {len(self.package_registry.get('packages', {}))} packages")
                return True
            else:
                self.logger.warning("Package registry not found in Redis")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to load package registry: {e}")
            return False
    
    async def get_package_info(self, package_name: str) -> Optional[Dict[str, str]]:
        """Get package information (which environments have it).
        
        Args:
            package_name: Name of the package
            
        Returns:
            Dict mapping environment names to versions, or None if not found
        """
        try:
            if not self.connections or not any(self.connections.values()):
                self.logger.error("No Redis connections available")
                return None
            
            # Get first available connection
            client = next(iter(self.connections.values()))
            
            # Try to get from cache first
            if self.package_registry and "packages" in self.package_registry:
                if package_name in self.package_registry["packages"]:
                    return self.package_registry["packages"][package_name]
            
            # Load from Redis
            pkg_data = await client.get(f"quantum_nexus:package:{package_name}")
            if pkg_data:
                return json.loads(pkg_data)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get package info for {package_name}: {e}")
            return None
    
    async def find_package(self, package_name: str) -> Optional[str]:
        """Find which environment has the package.
        
        Args:
            package_name: Name of the package to find
            
        Returns:
            Environment name where package is available, or None
        """
        pkg_info = await self.get_package_info(package_name)
        if pkg_info:
            # Return first environment that has it
            return next(iter(pkg_info.keys()))
        return None
    
    async def get_all_packages(self) -> Dict[str, Dict[str, str]]:
        """Get complete package registry.
        
        Returns:
            Dict mapping package names to {environment -> version}
        """
        try:
            if not self.connections or not any(self.connections.values()):
                self.logger.error("No Redis connections available")
                return {}
            
            # Load from cache if available
            if self.package_registry and "packages" in self.package_registry:
                return self.package_registry["packages"]
            
            # Load from Redis
            if not await self.load_package_registry():
                return {}
            
            return self.package_registry.get("packages", {})
            
        except Exception as e:
            self.logger.error(f"Failed to get all packages: {e}")
            return {}
    
    async def get_package_stats(self) -> Dict[str, Any]:
        """Get package registry statistics.
        
        Returns:
            Dict with total_packages, total_environments, last_updated
        """
        try:
            if not self.connections or not any(self.connections.values()):
                return {"error": "No Redis connections"}
            
            client = next(iter(self.connections.values()))
            stats_data = await client.get("quantum_nexus:stats")
            
            if stats_data:
                return json.loads(stats_data)
            else:
                return {"error": "Stats not found"}
                
        except Exception as e:
            self.logger.error(f"Failed to get package stats: {e}")
            return {"error": str(e)}

    # =========================================================================
    # CRITICAL: Async API methods required by TradingIntelligence and other core systems
    # =========================================================================
    
    async def check_connection_async(self, env_name: str = None) -> bool:
        """Async version of check_connection for use in async contexts.
        
        Args:
            env_name: Environment name (TRADING, MINING, WALLET, etc.)
            
        Returns:
            bool: True if connection is active
        """
        try:
            if env_name:
                env = NexusEnvironment.from_string(env_name)
                if env in self.connections and self.connections[env]:
                    try:
                        await asyncio.wait_for(self.connections[env].ping(), timeout=2.0)
                        return True
                    except Exception:
                        return False
                return False
            
            # Check any connection
            for env, conn in self.connections.items():
                if conn:
                    try:
                        await asyncio.wait_for(conn.ping(), timeout=2.0)
                        return True
                    except Exception:
                        continue
            return False
            
        except Exception as e:
            self.logger.error(f"Error in check_connection_async: {e}")
            return False
    
    async def get_data(self, env_name: str, key: str) -> Any:
        """Get data from Redis for a specific environment.
        
        Args:
            env_name: Environment name (TRADING, MINING, WALLET, etc.)
            key: Redis key to retrieve
            
        Returns:
            Data from Redis (parsed from JSON if applicable), or None
        """
        try:
            env = NexusEnvironment.from_string(env_name)
            
            if env not in self.connections or not self.connections[env]:
                # Try to connect
                connected = await self.connect_environment(env)
                if not connected:
                    self.logger.error(f"Cannot get data: not connected to {env_name}")
                    return None
            
            client = self.connections[env]
            data = await client.get(key)
            
            if data is None:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return data
                
        except Exception as e:
            self.logger.error(f"Error getting data from {env_name}:{key}: {e}")
            return None
    
    async def set_data(self, env_name: str, key: str, value: Any, ex: int = None) -> bool:
        """Set data in Redis for a specific environment.
        
        Args:
            env_name: Environment name (TRADING, MINING, WALLET, etc.)
            key: Redis key to set
            value: Value to store (will be JSON-encoded if dict/list)
            ex: Optional expiration time in seconds
            
        Returns:
            bool: True if successful
        """
        try:
            env = NexusEnvironment.from_string(env_name)
            
            if env not in self.connections or not self.connections[env]:
                # Try to connect
                connected = await self.connect_environment(env)
                if not connected:
                    self.logger.error(f"Cannot set data: not connected to {env_name}")
                    return False
            
            client = self.connections[env]
            
            # JSON encode if necessary
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            if ex:
                await client.set(key, value, ex=ex)
            else:
                await client.set(key, value)
            
            return True
                
        except Exception as e:
            self.logger.error(f"Error setting data in {env_name}:{key}: {e}")
            return False
    
    async def get_data_async(self, env_name: str, key: str, fallback_allowed: bool = True) -> Any:
        """Async get data with fallback control (alias for get_data with extra param).
        
        Args:
            env_name: Environment name
            key: Redis key
            fallback_allowed: If False, raises exception on failure (ignored, kept for API compat)
            
        Returns:
            Data from Redis or None
        """
        return await self.get_data(env_name, key)
    
    async def set_data_async(self, env_name: str, key: str, value: Any, fallback_allowed: bool = True, ex: int = None) -> bool:
        """Async set data with fallback control (alias for set_data with extra param).
        
        Args:
            env_name: Environment name
            key: Redis key
            value: Value to store
            fallback_allowed: If False, raises exception on failure (ignored, kept for API compat)
            ex: Optional expiration in seconds
            
        Returns:
            bool: True if successful
        """
        return await self.set_data(env_name, key, value, ex=ex)
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            if hasattr(self, 'running'):
                self.running = False
                        
            if hasattr(self, 'connections'):
                self.connections = {}
                        
            if hasattr(self, 'connection_pools'):
                self.connection_pools = {}
                        
            if hasattr(self, 'monitor_task'):
                self.monitor_task = None
            if hasattr(self, 'monitor_thread'):
                self.monitor_thread = None
            if hasattr(self, 'environment_status'):
                self.environment_status = {}
            if hasattr(self, 'data_cache'):
                self.data_cache = {}
            
            if hasattr(self, 'is_initialized'):
                self.is_initialized = False
        except Exception:
            pass