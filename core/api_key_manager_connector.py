#!/usr/bin/env python3
"""
Kingdom AI - API Key Manager Connector

This module provides a robust API key management connector with automatic
initialization and secure credential handling for Kingdom AI components.
"""

import logging
import asyncio
import time
import json
import os
import threading
import base64
import hashlib

logger = logging.getLogger("KingdomAI.APIKeyManagerConnector")

class APIKeyManagerConnector:
    """Provides immediate and reliable access to API credentials across components."""
    
    def __init__(self, event_bus=None, component_name=None, config=None):
        """Initialize the API Key Manager connector.
        
        Args:
            event_bus: The event bus instance for communication
            component_name: Name of the component using this connector
            config: Optional configuration dictionary
        """
        self.event_bus = event_bus
        self.component_name = component_name or "UnknownComponent"
        self.config = config or {}
        
        # API key cache
        self._api_keys = {}
        self._api_key_status = {}
        self._api_key_last_test = {}
        
        # Initialization tracking
        self._initialized = False
        self._initializing = False
        self._init_lock = threading.RLock()
        self._init_callbacks = []
        
        # Cache directory
        self._cache_dir = self.config.get("cache_dir", os.path.join(
            os.path.expanduser("~"), ".kingdom_ai", "cache"))
        self._cache_file = os.path.join(self._cache_dir, "api_keys.enc")
        
        # Create cache directory if it doesn't exist
        os.makedirs(self._cache_dir, exist_ok=True)
        
        # Background tasks
        self._monitor_task = None
        
        # Encryption key for local cache
        self._encryption_key = self._generate_encryption_key()
    
    async def initialize(self, event_bus=None):
        """Initialize the API Key Manager connector.
        
        This should be called during component initialization to ensure
        API keys are available as soon as possible.
        
        Args:
            event_bus: The event bus instance (if not provided at creation)
            
        Returns:
            bool: True if initialized successfully
        """
        # Update event bus if provided
        if event_bus and self.event_bus != event_bus:
            self.event_bus = event_bus
        
        # Check if already initialized or initializing
        with self._init_lock:
            if self._initialized:
                return True
            
            if self._initializing:
                # Another thread is already initializing
                # Set up a future to be notified when initialization completes
                future = asyncio.Future()
                self._init_callbacks.append(future)
                return await future
            
            # Mark as initializing
            self._initializing = True
        
        try:
            # Try to load cached API keys first
            self._load_cached_keys()
            
            # Subscribe to API key events (synchronous EventBus API)
            if self.event_bus:
                self.event_bus.subscribe("api.key.added", self._handle_api_key_added)
                self.event_bus.subscribe("api.key.updated", self._handle_api_key_updated)
                self.event_bus.subscribe("api.key.deleted", self._handle_api_key_deleted)
                self.event_bus.subscribe("api.key.status", self._handle_api_key_status)
            
            # Request all API keys from manager
            success = False
            if self.event_bus:
                try:
                    # Publish request for all API keys
                    logger.info(f"{self.component_name} requesting API keys")
                    self.event_bus.publish("api.keys.request", {
                        "component": self.component_name,
                        "timestamp": time.time()
                    })
                    
                    # Start a timeout check for response
                    asyncio.create_task(self._wait_for_initial_keys())
                    
                    success = True
                except Exception as e:
                    logger.error(f"{self.component_name} error requesting API keys: {e}")
            
            # If not using event bus or error, load from cache
            if not success and not self._api_keys:
                self._load_cached_keys()
            
            # Start monitor task
            if not self._monitor_task:
                self._monitor_task = asyncio.create_task(self._monitor_api_keys())
            
            # Mark as initialized
            with self._init_lock:
                self._initialized = True
                self._initializing = False
                
                # Notify any waiting callbacks
                for callback in self._init_callbacks:
                    callback.set_result(True)
                self._init_callbacks = []
            
            logger.info(f"{self.component_name} API Key Manager connector initialized")
            return True
            
        except Exception as e:
            logger.error(f"{self.component_name} error initializing API Key Manager connector: {e}")
            
            # Mark as not initializing
            with self._init_lock:
                self._initializing = False
                
                # Notify any waiting callbacks of failure
                for callback in self._init_callbacks:
                    callback.set_exception(e)
                self._init_callbacks = []
            
            return False
    
    async def get_api_key(self, service, wait=True, timeout=10.0):
        """Get an API key for a specific service.
        
        Args:
            service: The service to get the API key for
            wait: Whether to wait for initialization if not initialized
            timeout: Timeout for waiting (seconds)
            
        Returns:
            str: The API key if found, None otherwise
        """
        # Wait for initialization if needed
        if wait and not self._initialized and not self._initializing:
            await self.initialize()
        
        if wait and self._initializing:
            # Wait for initialization to complete with timeout
            try:
                future = asyncio.Future()
                with self._init_lock:
                    self._init_callbacks.append(future)
                
                # Wait with timeout
                await asyncio.wait_for(future, timeout)
            except asyncio.TimeoutError:
                logger.warning(f"{self.component_name} timed out waiting for API Key Manager initialization")
            except Exception as e:
                logger.error(f"{self.component_name} error waiting for API Key Manager initialization: {e}")
        
        # Normalize service name
        service = service.lower()
        
        # Check if we have the key in cache
        if service in self._api_keys:
            return self._api_keys[service]
        
        # Request the key if not in cache
        if self.event_bus and self._initialized:
            try:
                # Request a specific API key
                logger.debug(f"{self.component_name} requesting API key for {service}")
                self.event_bus.publish("api.key.request", {
                    "component": self.component_name,
                    "service": service,
                    "timestamp": time.time()
                })
                
                # Wait a bit for the response
                for _ in range(5):  # Wait up to 5*0.1 = 0.5 seconds
                    await asyncio.sleep(0.1)
                    if service in self._api_keys:
                        return self._api_keys[service]
            except Exception as e:
                logger.error(f"{self.component_name} error requesting API key for {service}: {e}")
        
        # Key not found
        logger.warning(f"{self.component_name} API key for {service} not found")
        return None
    
    async def get_all_api_keys(self):
        """Get all available API keys.
        
        Returns:
            dict: Dictionary of service -> API key
        """
        # Ensure initialized
        if not self._initialized and not self._initializing:
            await self.initialize()
        
        # Return a copy of the keys dictionary
        return dict(self._api_keys)
    
    async def get_api_key_status(self, service):
        """Get the status of an API key.
        
        Args:
            service: The service to check
            
        Returns:
            dict: Status information or None if not available
        """
        # Normalize service name
        service = service.lower()
        
        # Check if we have the status in cache
        if service in self._api_key_status:
            return self._api_key_status[service]
        
        # Request the status if not in cache
        if self.event_bus and self._initialized:
            try:
                # Request status for a specific API key
                logger.debug(f"{self.component_name} requesting API key status for {service}")
                self.event_bus.publish("api.key.status.request", {
                    "component": self.component_name,
                    "service": service,
                    "timestamp": time.time()
                })
                
                # Wait a bit for the response
                for _ in range(5):  # Wait up to 5*0.1 = 0.5 seconds
                    await asyncio.sleep(0.1)
                    if service in self._api_key_status:
                        return self._api_key_status[service]
            except Exception as e:
                logger.error(f"{self.component_name} error requesting API key status for {service}: {e}")
        
        # Status not found
        return None
    
    async def test_api_key(self, service):
        """Request a test of an API key.
        
        Args:
            service: The service to test
            
        Returns:
            bool: True if test request was sent successfully
        """
        # Normalize service name
        service = service.lower()
        
        # Track last test time
        self._api_key_last_test[service] = time.time()
        
        # Request the test
        if self.event_bus and self._initialized:
            try:
                # Request test for a specific API key
                logger.debug(f"{self.component_name} requesting API key test for {service}")
                self.event_bus.publish("api.key.test.request", {
                    "component": self.component_name,
                    "service": service,
                    "timestamp": time.time()
                })
                return True
            except Exception as e:
                logger.error(f"{self.component_name} error requesting API key test for {service}: {e}")
        
        return False
    
    def _handle_api_key_added(self, event_type, data):
        """Handle API key added event.
        
        Args:
            event_type: The event type
            data: The event data
        """
        service = data.get("service", "").lower()
        api_key = data.get("api_key")
        
        if service and api_key:
            logger.debug(f"{self.component_name} received API key for {service}")
            self._api_keys[service] = api_key
            
            # Update cache
            self._save_cached_keys()
    
    def _handle_api_key_updated(self, event_type, data):
        """Handle API key updated event.
        
        Args:
            event_type: The event type
            data: The event data
        """
        service = data.get("service", "").lower()
        api_key = data.get("api_key")
        
        if service and api_key:
            logger.debug(f"{self.component_name} received updated API key for {service}")
            self._api_keys[service] = api_key
            
            # Update cache
            self._save_cached_keys()
    
    def _handle_api_key_deleted(self, event_type, data):
        """Handle API key deleted event.
        
        Args:
            event_type: The event type
            data: The event data
        """
        service = data.get("service", "").lower()
        
        if service and service in self._api_keys:
            logger.debug(f"{self.component_name} removing API key for {service}")
            del self._api_keys[service]
            
            # Update cache
            self._save_cached_keys()
    
    def _handle_api_key_status(self, event_type, data):
        """Handle API key status event.
        
        Args:
            event_type: The event type
            data: The event data
        """
        service = data.get("service", "").lower()
        status = data.get("status")
        
        if service and status is not None:
            logger.debug(f"{self.component_name} received API key status for {service}: {status}")
            self._api_key_status[service] = status
    
    async def _wait_for_initial_keys(self):
        """Wait for initial API keys to be received."""
        # Wait for up to 5 seconds for keys to arrive
        for _ in range(50):  # 50 * 0.1 = 5 seconds
            await asyncio.sleep(0.1)
            if self._api_keys:
                # Keys received
                logger.debug(f"{self.component_name} received initial API keys")
                return
        
        # If no keys received, log warning
        logger.warning(f"{self.component_name} did not receive any API keys within timeout")
    
    async def _monitor_api_keys(self):
        """Monitor API keys and request updates if needed."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every 60 seconds
                
                # Skip if not initialized or no event bus
                if not self._initialized or not self.event_bus:
                    continue
                
                # Request status updates for all keys that haven't been tested recently
                current_time = time.time()
                for service in self._api_keys:
                    last_test = self._api_key_last_test.get(service, 0)
                    if current_time - last_test > 3600:  # 1 hour
                        # Request status update
                        try:
                            await self.test_api_key(service)
                        except Exception as e:
                            logger.error(f"{self.component_name} error testing API key for {service}: {e}")
            except asyncio.CancelledError:
                # Task was cancelled, exit
                break
            except Exception as e:
                logger.error(f"{self.component_name} error in API key monitor: {e}")
                await asyncio.sleep(300)  # Wait longer on error
    
    def _load_cached_keys(self):
        """Load API keys from cache file."""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, "rb") as f:
                    encrypted_data = f.read()
                
                # Decrypt data
                decrypted_data = self._decrypt_data(encrypted_data)
                if decrypted_data:
                    cached_keys = json.loads(decrypted_data)
                    
                    # Update keys cache
                    self._api_keys.update(cached_keys)
                    logger.info(f"{self.component_name} loaded {len(cached_keys)} API keys from cache")
                else:
                    logger.warning(f"{self.component_name} failed to decrypt API key cache")
        except Exception as e:
            logger.error(f"{self.component_name} error loading cached API keys: {e}")
    
    def _save_cached_keys(self):
        """Save API keys to cache file."""
        try:
            # Encrypt data
            encrypted_data = self._encrypt_data(json.dumps(self._api_keys))
            
            # Save to file
            with open(self._cache_file, "wb") as f:
                f.write(encrypted_data)
            
            logger.debug(f"{self.component_name} saved {len(self._api_keys)} API keys to cache")
        except Exception as e:
            logger.error(f"{self.component_name} error saving cached API keys: {e}")
    
    def _generate_encryption_key(self):
        """Generate an encryption key based on machine-specific information.
        
        Returns:
            bytes: Encryption key
        """
        # Create a consistent key based on:
        # 1. Username
        # 2. Machine name
        # 3. User home directory path
        username = os.environ.get("USERNAME", os.environ.get("USER", "unknown"))
        hostname = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown"))
        home_path = os.path.expanduser("~")
        
        # Combine and hash to create key
        seed = f"{username}:{hostname}:{home_path}:KingdomAI"
        return hashlib.sha256(seed.encode()).digest()
    
    def _encrypt_data(self, data):
        """Encrypt data using the encryption key.
        
        Args:
            data: String data to encrypt
            
        Returns:
            bytes: Encrypted data
        """
        # Simple XOR encryption for local cache
        # This isn't meant to be highly secure, just to obscure the keys
        data_bytes = data.encode("utf-8")
        key_bytes = self._encryption_key
        
        # XOR each byte with the key (cycling through key bytes)
        encrypted = bytearray()
        for i, b in enumerate(data_bytes):
            encrypted.append(b ^ key_bytes[i % len(key_bytes)])
        
        # Base64 encode for storage
        return base64.b64encode(encrypted)
    
    def _decrypt_data(self, encrypted_data):
        """Decrypt data using the encryption key.
        
        Args:
            encrypted_data: Encrypted bytes data
            
        Returns:
            str: Decrypted data or None if decryption failed
        """
        try:
            # Base64 decode
            data = base64.b64decode(encrypted_data)
            key_bytes = self._encryption_key
            
            # XOR each byte with the key (cycling through key bytes)
            decrypted = bytearray()
            for i, b in enumerate(data):
                decrypted.append(b ^ key_bytes[i % len(key_bytes)])
            
            # Decode to string
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"{self.component_name} error decrypting data: {e}")
            return None
