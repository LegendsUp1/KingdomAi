"""
Redis Manager for Kingdom AI Trading System

Handles all Redis Quantum Nexus connections and pub/sub functionality.
Enforces strict connection requirements (port 6380, no fallback).
Uses environment variable KINGDOM_AI_SEC_KEY for secure password handling.
"""

import logging
import json
import os
import time
import redis
from typing import Dict, Any, Optional, Callable, List
from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot

class RedisConnectionError(Exception):
    """Raised when Redis connection fails or is unhealthy."""
    pass

class RedisSignals(QObject):
    """Signals for Redis connection status and messages."""
    connected = pyqtSignal()
    disconnected = pyqtSignal(str)  # error message
    message_received = pyqtSignal(str, dict)  # channel, message

class RedisManager(QObject):
    """Manages Redis Quantum Nexus connection and pub/sub functionality."""
    
    def __init__(self, host: str = 'localhost', port: int = 6380, 
                 password: str = None, db: int = 0):
        """Initialize Redis manager with connection parameters.
        
        Args:
            host: Redis server host
            port: Redis server port (default: 6380)
            password: Redis authentication password
            db: Redis database number
        """
        super().__init__()
        self.host = host
        self.port = port
        
        # Use environment variable for password if not explicitly provided
        if password is None:
            self.password = os.environ.get('KINGDOM_AI_SEC_KEY', 'QuantumNexus2025')
            if self.password != 'QuantumNexus2025':
                logger = logging.getLogger("Kingdom.RedisManager")
                logger.info("Using custom Redis password from environment variable")
        else:
            self.password = password
            
        self.db = db
        self.redis_client = None
        self.pubsub = None
        self.running = False
        self.connected = False
        self.thread = None
        self.signals = RedisSignals()
        self.subscriptions = set()
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> bool:
        """Establish connection to Redis Quantum Nexus.
        
        Returns:
            bool: True if connection was successful, False otherwise
            
        Raises:
            RedisConnectionError: If connection fails or is unhealthy
        """
        try:
            self.logger.info(f"Connecting to Redis at {self.host}:{self.port}...")
            
            # Create Redis client with strict connection parameters
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
                decode_responses=True
            )
            
            # Test connection
            if not self.redis_client.ping():
                raise RedisConnectionError("Failed to ping Redis server")
            
            self.connected = True
            self.pubsub = self.redis_client.pubsub()
            self.logger.info("Successfully connected to Redis Quantum Nexus")
            self.signals.connected.emit()
            return True
            
        except redis.RedisError as e:
            error_msg = f"Redis connection failed: {str(e)}"
            self.logger.error(error_msg)
            self.signals.disconnected.emit(error_msg)
            self.connected = False
            raise RedisConnectionError(error_msg)
    
    def disconnect(self) -> None:
        """Disconnect from Redis server."""
        self.running = False
        
        # CRITICAL 2026 SOTA: Wait for QThread to stop before closing connections
        if self.thread and self.thread.isRunning():
            self.logger.info("Waiting for Redis listener thread to stop...")
            self.thread.quit()
            if not self.thread.wait(2000):  # Wait up to 2 seconds
                self.logger.warning("Redis listener thread did not stop in time, terminating...")
                self.thread.terminate()
                self.thread.wait(500)
            self.logger.info("Redis listener thread stopped")
        
        if self.pubsub:
            try:
                self.pubsub.close()
            except Exception as e:
                self.logger.error(f"Error closing pubsub: {e}")
        
        if self.redis_client:
            try:
                self.redis_client.close()
            except Exception as e:
                self.logger.error(f"Error closing Redis client: {e}")
        
        self.connected = False
        self.signals.disconnected.emit("Disconnected by user")
    
    def stop(self) -> None:
        """Alias for disconnect() - used by graceful shutdown."""
        self.disconnect()
    
    def subscribe(self, channels: List[str]) -> None:
        """Subscribe to one or more Redis channels.
        
        Args:
            channels: List of channel names to subscribe to
        """
        if not self.connected or not self.pubsub:
            raise RedisConnectionError("Not connected to Redis")
        
        # Add new channels to subscriptions
        new_channels = set(channels) - self.subscriptions
        if new_channels:
            self.pubsub.subscribe(*new_channels)
            self.subscriptions.update(new_channels)
            self.logger.debug(f"Subscribed to channels: {new_channels}")
            
            # Start listener thread if not already running
            if not self.running:
                self._start_listener()
    
    def unsubscribe(self, channels: List[str]) -> None:
        """Unsubscribe from one or more Redis channels.
        
        Args:
            channels: List of channel names to unsubscribe from
        """
        if not self.connected or not self.pubsub:
            return
            
        channels_to_unsubscribe = set(channels) & self.subscriptions
        if channels_to_unsubscribe:
            self.pubsub.unsubscribe(*channels_to_unsubscribe)
            self.subscriptions -= channels_to_unsubscribe
            self.logger.debug(f"Unsubscribed from channels: {channels_to_unsubscribe}")
    
    def publish(self, channel: str, message: Dict[str, Any]) -> None:
        """Publish a message to a Redis channel.
        
        Args:
            channel: Channel name
            message: Message to publish (will be JSON-serialized)
            
        Raises:
            RedisConnectionError: If not connected to Redis
        """
        if not self.connected or not self.redis_client:
            raise RedisConnectionError("Not connected to Redis")
            
        try:
            self.redis_client.publish(channel, json.dumps(message))
        except (redis.RedisError, TypeError) as e:
            self.logger.error(f"Failed to publish message: {e}")
            raise
    
    def _start_listener(self) -> None:
        """Start the Redis pub/sub listener in a separate thread."""
        if self.thread and self.thread.isRunning():
            return
            
        self.running = True
        self.thread = QThread()
        self.thread.run = self._run_listener
        self.thread.finished.connect(self._on_thread_finished)
        self.thread.start()
    
    def _run_listener(self) -> None:
        """Run the Redis pub/sub listener loop."""
        while self.running and self.connected and self.pubsub:
            try:
                message = self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        channel = message['channel']
                        data = json.loads(message['data'])
                        self.signals.message_received.emit(channel, data)
                    except (json.JSONDecodeError, KeyError) as e:
                        self.logger.error(f"Invalid message format: {e}")
                
                # Small sleep to prevent busy-waiting
                time.sleep(0.01)
                
            except redis.ConnectionError as e:
                self.logger.error(f"Redis connection error: {e}")
                self.connected = False
                self.signals.disconnected.emit(str(e))
                self.running = False
                break
            except Exception as e:
                self.logger.error(f"Error in Redis listener: {e}", exc_info=True)
                time.sleep(1)  # Prevent tight loop on errors
    
    @pyqtSlot()
    def _on_thread_finished(self) -> None:
        """Handle thread finished signal."""
        self.running = False
        self.connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to Redis.
        
        Returns:
            bool: True if connected, False otherwise
        """
        if not self.connected or not self.redis_client:
            return False
            
        try:
            return bool(self.redis_client.ping())
        except redis.RedisError:
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information.
        
        Returns:
            Dict with connection information
        """
        return {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'connected': self.connected,
            'subscriptions': list(self.subscriptions)
        }
