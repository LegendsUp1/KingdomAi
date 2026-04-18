#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Redis Manager for Kingdom AI

This module provides Redis connection management for the Kingdom AI system.
Integrates with Quantum Nexus for proper Redis server initialization.
"""

import redis
import logging
import asyncio
import os
import time
import subprocess
import traceback

# Import Quantum Nexus Initializer - using importlib to handle potential circular imports
try:
    from core.quantum_nexus_initializer import get_instance as get_quantum_nexus_instance
    from core.quantum_nexus_initializer import initialize as initialize_quantum_nexus
    from core.quantum_nexus_initializer import get_connection as get_quantum_nexus_connection
    has_quantum_nexus = True
except ImportError:
    has_quantum_nexus = False
    logging.getLogger("RedisManager").warning("Quantum Nexus Initializer not available, falling back to direct Redis connection")

class RedisManager:
    """Manager for Redis connection and operations."""
    
    def __init__(self, event_bus=None):
        """Initialize Redis manager."""
        self.event_bus = event_bus
        self.logger = logging.getLogger("RedisManager")
        self.redis_client = None
        self.is_connected = False
        self.is_initialized = False
        self.config = self._load_config()
        
        # Initialize Redis connection synchronously in constructor
        # (the async connect method will be called separately in initialize_kingdom_ai)
        try:
            self._connect_sync()
        except Exception as e:
            self.logger.warning(f"Failed to initialize Redis connection: {e}")
            
    def _connect_sync(self):
        """Connect to Redis server synchronously for use in __init__.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First, try to use Quantum Nexus if available
            if has_quantum_nexus:
                self.logger.info("Using Quantum Nexus Initializer to connect to Redis")
                # Initialize Quantum Nexus which will start Redis if needed
                nexus_initialized = initialize_quantum_nexus()
                if nexus_initialized:
                    # Get the connection from Quantum Nexus
                    self.redis_client = get_quantum_nexus_connection()
                    if self.redis_client:
                        self.is_connected = True
                        self.logger.info("Successfully connected to Redis via Quantum Nexus")
                        return True
                    else:
                        self.logger.warning("Quantum Nexus initialized but returned no connection, falling back to direct connection")
                else:
                    self.logger.warning("Failed to initialize Quantum Nexus, falling back to direct connection")
            
            # CRITICAL: RedisManager MUST use Quantum Nexus - no fallback allowed
            self.logger.error("Quantum Nexus is required but not available - system cannot continue")
            self.is_connected = False
            return False
        except redis.ConnectionError as e:
            self.logger.error(f"Redis connection error: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            self.logger.error(f"Redis error: {e}")
            self.is_connected = False
            return False
            
    def _get_redis_password(self):
        """Get Redis password from configuration or password file.
        
        Returns:
            str: Redis password if available, None otherwise
        """
        # First check if password is directly in config
        if self.config.get("password"):
            return self.config.get("password")
            
        # Then check for password file
        password_file = self.config.get("password_file")
        if password_file and os.path.exists(password_file):
            try:
                with open(password_file, 'r', encoding='utf-8') as f:
                    password = f.read().strip()
                    if password:
                        return password
            except Exception as e:
                self.logger.error(f"Error reading Redis password file: {e}")
                
        # Fall back to environment variable
        if os.environ.get("REDIS_PASSWORD"):
            return os.environ.get("REDIS_PASSWORD")
            
        # No password available
        self.logger.info("No Redis password found in config, using default Quantum Nexus password")
        return "QuantumNexus2025"  # Return the default Quantum Nexus password
        
    async def connect(self):
        """Connect to Redis server asynchronously.
        
        Returns:
            bool: True if successful, False otherwise
        """
        max_retries = 3
        retry_count = 0
        retry_delay = 1  # seconds
        
        while retry_count < max_retries:
            try:
                # Connect to Redis
                self.logger.info(f"Connecting to Redis (attempt {retry_count+1}/{max_retries})...")
                
                # CRITICAL: Use Quantum Nexus connection if available
                if has_quantum_nexus:
                    self.redis_client = get_quantum_nexus_connection()
                    if not self.redis_client:
                        self.logger.error("Quantum Nexus connection not available")
                        raise redis.ConnectionError("Quantum Nexus connection failed")
                else:
                    self.logger.error("Quantum Nexus is required but not available")
                    raise redis.ConnectionError("Quantum Nexus module not found")
                
                # Test connection
                self.redis_client.ping()
                self.is_connected = True
                self.logger.info("Successfully connected to Redis")
                
                # Attempt to publish status if event bus is available
                if self.event_bus:
                    try:
                        # Directly use event_bus.publish to avoid awaiting a non-awaitable
                        await self.event_bus.publish("redis.status", {
                            "status": "connected",
                            "timestamp": time.time(),
                            "config": {
                                "host": self.config.get("host", "localhost"),
                                "port": self.config.get("port", 6380),
                                "db": self.config.get("db", 0),
                                "has_password": password is not None
                            }
                        })
                    except Exception as e:
                        self.logger.warning(f"Failed to publish status: {e}")
                
                return True
            except redis.ConnectionError as e:
                self.logger.error(f"Redis connection error (attempt {retry_count+1}/{max_retries}): {e}")
                retry_count += 1
                if retry_count < max_retries:
                    self.logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    # Exponential backoff for retry delays
                    retry_delay *= 2
            except Exception as e:
                self.logger.error(f"Redis error: {e}")
                self.is_connected = False
                break
                    # If we've exhausted retries or encountered a non-connection error
        if not self.is_connected:
            # Try to start Redis server if available
            try:
                start_result = await self._try_start_redis()
                if start_result:
                    # If Redis was started, try connecting again with a fresh retry count
                    self.logger.info("Redis server started, attempting to connect again")
                    # Create a new connection attempt rather than recursively calling connect
                    # to avoid potential stack overflow
                    retry_count = 0
                    retry_delay = 1
                    await asyncio.sleep(2)  # Wait a bit for Redis to fully start
                    # Instead of using continue, start a fresh attempt
                    fresh_attempt = await self.connect()
                    return fresh_attempt
            except Exception as nested_error:
                self.logger.error(f"Error starting Redis: {nested_error}")
                
            # All Redis connection attempts failed
            self.logger.error("All Redis connection attempts failed")
            if self.event_bus:
                try:
                    # Create a direct publishing coroutine to avoid awaiting a function that returns a boolean
                    async def publish_status(event_bus):
                        if event_bus is not None:
                            await event_bus.publish("redis.status", {
                                "status": "disconnected",
                                "error": "Failed to connect after multiple attempts",
                                "timestamp": time.time()
                            })
                    # Run the coroutine directly
                    await publish_status(self.event_bus)
                except Exception as e:
                    self.logger.error(f"Error publishing redis status: {e}")
            return False
    
    async def _try_start_redis(self):
        """Try to start Redis server if not running.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if Redis is already running
        if self.is_redis_running():
            self.logger.info("Redis server is already running")
            return True
            
        self.logger.info("Attempting to start Redis server locally")
        
        # Common Redis server paths (Linux-first)
        redis_paths = [
            "/usr/bin/redis-server",
            "/usr/local/bin/redis-server",
            "/snap/bin/redis-server",
            "redis-server",
            "C:\\Program Files\\Redis\\redis-server.exe",
            "C:\\Redis\\redis-server.exe",
        ]
        
        redis_path = None
        
        # Find the first valid Redis path
        for path in redis_paths:
            if os.path.exists(path):
                redis_path = path
                break
                
        if not redis_path:
            self.logger.error("Redis server not found")
            return False
            
        try:
            # Start Redis server
            self.logger.info(f"Starting Redis server at {redis_path}")
            
            # Start Redis server as a background process
            # Each platform has different requirements for daemonization
            if os.name == 'nt':  # Windows
                # On Windows, use subprocess.CREATE_NO_WINDOW flag to hide console
                process = await asyncio.create_subprocess_exec(
                    redis_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:  # Unix/Linux/Mac
                # Use daemon option for Unix systems
                process = await asyncio.create_subprocess_exec(
                    redis_path, "--daemonize", "yes",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
            # Don't await the process itself as it runs continuously
            # Instead wait briefly then check if running
            await asyncio.sleep(2)  # Give Redis time to start
            
            if self.is_redis_running():
                self.logger.info("Redis server started successfully")
                return True
            else:
                self.logger.error("Redis server failed to start properly")
                return False
        except Exception as e:
            self.logger.error(f"Error starting Redis server: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def is_redis_running(self):
        """Check if Redis server is running.
        
        Returns:
            bool: True if Redis server is running, False otherwise
        """
        try:
            # Try to connect to Redis
            redis_client = redis.Redis(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 6380),  # Quantum Nexus uses port 6380
                db=self.config.get("db", 0),
                password=self._get_redis_password(),  # Add password for authentication
                decode_responses=self.config.get("decode_responses", True),
                socket_timeout=self.config.get("socket_timeout", 5),
                retry_on_timeout=self.config.get("retry_on_timeout", True)
            )
            redis_client.ping()
            return True
        except redis.ConnectionError:
            return False
        except Exception as e:
            self.logger.error(f"Error checking Redis status: {e}")
            return False
    
    async def safe_publish(self, event_name, event_data=None):
        """Safely publish an event with error handling"""
        if self.event_bus is None:
            self.logger.warning(f"Cannot publish event {event_name}: Event bus is None")
            return False
            
        try:
            await self.event_bus.publish(event_name, event_data)
            return True
        except Exception as e:
            self.logger.error(f"Error publishing event {event_name}: {str(e)}")
            return False
            
    def _load_config(self):
        """Load Redis configuration."""
        # Default configuration
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        password_file = os.path.join(config_dir, "redis_password.txt")
        
        # Create config dir if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        
        # Create password file if it doesn't exist
        if not os.path.exists(password_file):
            try:
                with open(password_file, 'w', encoding='utf-8') as f:
                    f.write("Quantumnexus2025")
                os.chmod(password_file, 0o600)  # Only owner can read/write
                self.logger.info(f"Created Redis password file at {password_file}")
            except Exception as e:
                self.logger.error(f"Error creating Redis password file: {e}")
        
        return {
            "host": "localhost",
            "port": 6380,  # Quantum Nexus uses port 6380
            "db": 0,
            "password": "Quantumnexus2025",
            "password_file": password_file,
            "decode_responses": True
        }
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            # First, try to use Quantum Nexus if available
            if has_quantum_nexus:
                self.logger.info("Using Quantum Nexus Initializer to connect to Redis")
                # Initialize Quantum Nexus which will start Redis if needed
                nexus_initialized = initialize_quantum_nexus()
                if nexus_initialized:
                    # Get the connection from Quantum Nexus
                    self.redis_client = get_quantum_nexus_connection()
                    if self.redis_client:
                        self.is_connected = True
                        self.logger.info("Successfully connected to Redis via Quantum Nexus")
                        
                        # Subscribe to events
                        if self.event_bus:
                            await self.event_bus.subscribe("system.test.redis", self._handle_test_redis)
                            await self.event_bus.subscribe("system.shutdown", self._handle_shutdown)
                        else:
                            self.logger.warning("Event bus not available, skipping event subscriptions")
                        
                        # Mark as initialized
                        self.is_initialized = True
                        
                        # Publish status
                        if self.event_bus:
                            await self.event_bus.publish("component.init.complete", {
                                "component": "redis",
                                "status": "success"
                            })
                        
                        return True
                    else:
                        self.logger.warning("Quantum Nexus initialized but returned no connection, falling back to direct connection")
                else:
                    self.logger.warning("Failed to initialize Quantum Nexus, falling back to direct connection")
            
            # Fall back to direct connection if Quantum Nexus is not available or failed
            self.logger.info("Connecting to Redis directly...")
            
            # Get password from file or config
            password = self._get_redis_password()
            
            # Use connection parameters from config
            self.redis_client = redis.Redis(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 6380),  # Quantum Nexus uses port 6380
                db=self.config.get("db", 0),
                password=password,  # Use the Quantum Nexus password
                decode_responses=self.config.get("decode_responses", True),
                socket_timeout=self.config.get("socket_timeout", 5),
                retry_on_timeout=self.config.get("retry_on_timeout", True)
            )
            
            # Test connection
            self.redis_client.ping()
            self.is_connected = True
            self.logger.info("Successfully connected to Redis")
            
            # Subscribe to events
            if self.event_bus:
                await self.event_bus.subscribe("system.test.redis", self._handle_test_redis)
                await self.event_bus.subscribe("system.shutdown", self._handle_shutdown)
            else:
                self.logger.warning("Event bus not available, skipping event subscriptions")
            
            # Mark as initialized
            self.is_initialized = True
            
            # Publish status
            if self.event_bus:
                await self.event_bus.publish("component.init.complete", {
                    "component": "redis",
                    "status": "success"
                })
            
            return True
        except redis.ConnectionError as e:
            self.logger.error(f"Redis connection error: {e}")
            self.is_connected = False
            if self.event_bus:
                await self.event_bus.publish("component.init.error", {
                "component": "redis",
                "error": str(e)
            })
            return False
        except Exception as e:
            self.logger.error(f"Error initializing Redis: {e}")
            self.is_connected = False
            if self.event_bus:
                await self.event_bus.publish("component.init.error", {
                "component": "redis",
                "error": str(e)
            })
            return False
    
    async def _handle_test_redis(self, data):
        """Handle a Redis test request."""
        try:
            if self.redis_client:
                # Attempt ping operation
                self.redis_client.ping()
                self.is_connected = True
                
                # Publish success event
                if self.event_bus:
                    await self.event_bus.publish("system.test.redis.result", {
                        "status": "success",
                        "message": "Redis connection successful"
                    })
            else:
                # No client exists
                if self.event_bus:
                    await self.event_bus.publish("system.test.redis.result", {
                        "status": "error",
                        "message": "Redis client not initialized"
                    })
        except Exception as e:
            self.logger.error(f"Redis test failed: {e}")
            self.is_connected = False
            
            # Publish error event
            if self.event_bus:
                await self.event_bus.publish("system.test.redis.result", {
                    "status": "error",
                    "message": f"Redis test failed: {str(e)}"
                })
    
    async def _handle_shutdown(self, data):
        """Handle system shutdown."""
        try:
            # Properly shutdown Quantum Nexus if we're using it
            if has_quantum_nexus:
                try:
                    self.logger.info("Shutting down Quantum Nexus...")
                    from core.quantum_nexus_initializer import shutdown as shutdown_quantum_nexus
                    shutdown_result = shutdown_quantum_nexus()
                    if shutdown_result:
                        self.logger.info("Quantum Nexus shutdown successful")
                    else:
                        self.logger.warning("Quantum Nexus shutdown may not have completed properly")
                except Exception as nexus_error:
                    self.logger.error(f"Error shutting down Quantum Nexus: {nexus_error}")
            
            # Also close our direct Redis client if we have one
            if self.redis_client:
                # Close Redis connection
                self.redis_client.close()
                self.logger.info("Redis connection closed")
        except Exception as e:
            self.logger.error(f"Error closing Redis connection: {e}")
