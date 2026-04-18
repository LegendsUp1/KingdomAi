#!/usr/bin/env python3
"""
Kingdom AI - Event Bus Connector

This module provides robust event bus connection with retry logic
for Kingdom AI components, ensuring reliable communication even when
components start in different orders.
"""

import logging
import asyncio
import time
import random
import threading
import functools

logger = logging.getLogger("KingdomAI.EventBusConnector")

class EventBusConnector:
    """Provides robust event bus connections with retry logic."""
    
    def __init__(self, event_bus=None, component_name=None, max_retries=10, 
                 initial_retry_delay=1.0, max_retry_delay=60.0):
        """Initialize the event bus connector.
        
        Args:
            event_bus: The event bus instance
            component_name: Name of the component using this connector
            max_retries: Maximum number of retry attempts (-1 for infinite)
            initial_retry_delay: Initial delay between retries (seconds)
            max_retry_delay: Maximum delay between retries (seconds)
        """
        self.event_bus = event_bus
        self.component_name = component_name or "UnknownComponent"
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        
        # Track subscriptions for reconnection
        self.subscriptions = {}
        self.retry_counts = {}
        self.connection_status = {}
        self.connected = event_bus is not None
        self.last_reconnect_attempt = 0
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Task for monitoring connection
        self._monitor_task = None
    
    async def connect(self, event_bus):
        """Connect to the event bus.
        
        Args:
            event_bus: The event bus instance
            
        Returns:
            bool: True if connected successfully
        """
        with self._lock:
            self.event_bus = event_bus
            self.connected = event_bus is not None
            
            # Restart monitoring task
            if self.connected and not self._monitor_task:
                self._monitor_task = asyncio.create_task(self._monitor_connection())
            
            # Reestablish subscriptions
            if self.connected:
                await self._reestablish_subscriptions()
                logger.info(f"{self.component_name} connected to event bus")
                return True
            else:
                logger.warning(f"{self.component_name} failed to connect to event bus")
                return False
    
    async def disconnect(self):
        """Disconnect from the event bus."""
        with self._lock:
            # Cancel monitoring task
            if self._monitor_task:
                self._monitor_task.cancel()
                self._monitor_task = None
            
            self.connected = False
            self.event_bus = None
            logger.info(f"{self.component_name} disconnected from event bus")
    
    async def subscribe(self, event_type, handler, resubscribe=True):
        """Subscribe to an event with retry logic.
        
        Args:
            event_type: The event type to subscribe to
            handler: The handler function
            resubscribe: Whether to attempt resubscription on reconnect
            
        Returns:
            bool: True if subscribed successfully
        """
        # Store subscription for reconnection if needed
        if resubscribe:
            with self._lock:
                self.subscriptions[event_type] = handler
        
        # Attempt to subscribe
        return await self._subscribe_with_retry(event_type, handler)
    
    async def _subscribe_with_retry(self, event_type, handler, retry_count=0):
        """Subscribe to an event with retry logic.
        
        Args:
            event_type: The event type to subscribe to
            handler: The handler function
            retry_count: Current retry attempt
            
        Returns:
            bool: True if subscribed successfully
        """
        if not self.event_bus:
            logger.warning(f"{self.component_name} cannot subscribe to {event_type}: No event bus")
            return False
        
        try:
            # Attempt to subscribe
            success = await self.event_bus.subscribe(event_type, handler)
            
            if success:
                logger.debug(f"{self.component_name} subscribed to {event_type}")
                # Reset retry counter on success
                with self._lock:
                    self.retry_counts[event_type] = 0
                    self.connection_status[event_type] = True
                return True
            else:
                logger.warning(f"{self.component_name} failed to subscribe to {event_type}")
        except Exception as e:
            logger.error(f"{self.component_name} error subscribing to {event_type}: {e}")
            success = False
        
        # Handle retry if needed
        if not success and (self.max_retries < 0 or retry_count < self.max_retries):
            # Calculate exponential backoff with jitter
            delay = min(
                self.max_retry_delay,
                self.initial_retry_delay * (2 ** retry_count)
            )
            # Add jitter (±20%)
            delay = delay * (0.8 + 0.4 * random.random())
            
            logger.info(f"{self.component_name} will retry subscribing to {event_type} in {delay:.1f}s (attempt {retry_count+1})")
            
            # Track retry count
            with self._lock:
                self.retry_counts[event_type] = retry_count + 1
                self.connection_status[event_type] = False
            
            # Schedule retry
            asyncio.create_task(self._retry_subscribe(event_type, handler, retry_count + 1, delay))
            return False
        
        return success
    
    async def _retry_subscribe(self, event_type, handler, retry_count, delay):
        """Retry subscription after delay.
        
        Args:
            event_type: The event type to subscribe to
            handler: The handler function
            retry_count: Current retry attempt
            delay: Delay before retry (seconds)
        """
        await asyncio.sleep(delay)
        await self._subscribe_with_retry(event_type, handler, retry_count)
    
    async def publish(self, event_type, data=None, retry_count=0):
        """Publish an event with retry logic.
        
        Args:
            event_type: The event type to publish
            data: The event data
            retry_count: Current retry attempt
            
        Returns:
            bool: True if published successfully
        """
        if not self.event_bus:
            logger.warning(f"{self.component_name} cannot publish {event_type}: No event bus")
            return False
        
        try:
            # Attempt to publish
            success = await self.event_bus.publish(event_type, data or {})
            
            if success:
                return True
            else:
                logger.warning(f"{self.component_name} failed to publish {event_type}")
        except Exception as e:
            logger.error(f"{self.component_name} error publishing {event_type}: {e}")
            success = False
        
        # Handle retry if needed
        if not success and (self.max_retries < 0 or retry_count < self.max_retries):
            # Calculate exponential backoff with jitter
            delay = min(
                self.max_retry_delay,
                self.initial_retry_delay * (2 ** retry_count)
            )
            # Add jitter (±20%)
            delay = delay * (0.8 + 0.4 * random.random())
            
            logger.debug(f"{self.component_name} will retry publishing {event_type} in {delay:.1f}s (attempt {retry_count+1})")
            
            # Schedule retry
            asyncio.create_task(self._retry_publish(event_type, data, retry_count + 1, delay))
            return False
        
        return success
    
    async def _retry_publish(self, event_type, data, retry_count, delay):
        """Retry publication after delay.
        
        Args:
            event_type: The event type to publish
            data: The event data
            retry_count: Current retry attempt
            delay: Delay before retry (seconds)
        """
        await asyncio.sleep(delay)
        await self.publish(event_type, data, retry_count)
    
    async def _reestablish_subscriptions(self):
        """Reestablish all subscriptions after reconnect."""
        logger.info(f"{self.component_name} reestablishing {len(self.subscriptions)} event subscriptions")
        
        for event_type, handler in self.subscriptions.items():
            try:
                await self._subscribe_with_retry(event_type, handler)
            except Exception as e:
                logger.error(f"{self.component_name} error resubscribing to {event_type}: {e}")
    
    async def _monitor_connection(self):
        """Monitor the event bus connection and attempt reconnection if needed."""
        while True:
            try:
                # Check connection every 30 seconds
                await asyncio.sleep(30)
                
                # Skip if already connected or no event bus
                if not self.event_bus:
                    continue
                
                # Test connection with a simple ping
                try:
                    now = time.time()
                    ping_result = await self.event_bus.publish("system.ping", {
                        "component": self.component_name,
                        "timestamp": now
                    })
                    
                    if ping_result:
                        # Connection is good
                        self.connected = True
                    else:
                        # Connection might be lost
                        logger.warning(f"{self.component_name} detected possible event bus connection issue")
                        self.connected = False
                except Exception as e:
                    logger.error(f"{self.component_name} error checking event bus connection: {e}")
                    self.connected = False
                
                # Attempt to reconnect if disconnected
                if not self.connected and self.event_bus:
                    current_time = time.time()
                    # Only attempt reconnect if it's been at least 60 seconds since last attempt
                    if current_time - self.last_reconnect_attempt >= 60:
                        self.last_reconnect_attempt = current_time
                        logger.info(f"{self.component_name} attempting to reconnect to event bus")
                        await self._reestablish_subscriptions()
            except asyncio.CancelledError:
                # Task was cancelled, exit the loop
                break
            except Exception as e:
                logger.error(f"{self.component_name} error in connection monitor: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def get_connection_status(self):
        """Get the connection status.
        
        Returns:
            dict: Connection status information
        """
        with self._lock:
            return {
                "connected": self.connected,
                "component": self.component_name,
                "subscriptions": {
                    event_type: {
                        "connected": self.connection_status.get(event_type, False),
                        "retry_count": self.retry_counts.get(event_type, 0)
                    }
                    for event_type in self.subscriptions
                },
                "last_reconnect_attempt": self.last_reconnect_attempt
            }

def with_event_retry(max_retries=3, initial_delay=1.0, max_delay=30.0):
    """Decorator for functions that interact with the event bus.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        
    Returns:
        decorator: Function decorator
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            component_name = args[0].__class__.__name__ if args else "UnknownComponent"
            
            for retry in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    # Don't retry on the last attempt
                    if retry >= max_retries:
                        break
                    
                    # Calculate exponential backoff with jitter
                    delay = min(
                        max_delay,
                        initial_delay * (2 ** retry)
                    )
                    # Add jitter (±20%)
                    delay = delay * (0.8 + 0.4 * random.random())
                    
                    logger.warning(f"{component_name}.{func.__name__} failed, retrying in {delay:.1f}s (attempt {retry+1}/{max_retries}): {e}")
                    await asyncio.sleep(delay)
            
            # If we get here, all retries failed
            logger.error(f"{component_name}.{func.__name__} failed after {max_retries} retries: {last_error}")
            raise last_error
        
        return wrapper
    
    return decorator
