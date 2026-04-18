#!/usr/bin/env python3
"""
Event Bus Retry Logic for Kingdom AI GUI.
Provides robust event subscription with automatic retries.
"""

import tkinter as tk
import logging
import asyncio
import traceback
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

class EventBusRetryMixin:
    """Mixin class providing robust event bus subscription with retry logic."""
    
    def __init__(self):
        """Initialize retry settings."""
        self.max_retries = 5
        self.retry_backoff_factor = 2  # for exponential backoff
    
    def _subscribe_with_retry(self, event_name: str, handler: Callable, retry_count: int = 0) -> bool:
        """
        Subscribe to an event with retry logic.
        
        Args:
            event_name: Name of the event to subscribe to
            handler: Event handler function
            retry_count: Current retry attempt count
            
        Returns:
            bool: Success status of the subscription
        """
        try:
            if not hasattr(self, 'event_bus') or self.event_bus is None:
                logger.warning(f"Cannot subscribe to {event_name}: event_bus is None")
                return False
                
            # Subscribe to the event
            if asyncio.iscoroutinefunction(self.event_bus.subscribe):
                # For async subscribe method
                if hasattr(self, 'after') and self.after:  
                    # If we're in a Tkinter widget with after method
                    async def async_subscribe():
                        try:
                            await self.event_bus.subscribe(event_name, handler)
                            logger.info(f"Successfully subscribed to {event_name}")
                            return True
                        except Exception as e:
                            logger.error(f"Error subscribing to {event_name}: {e}")
                            return False
                            
                    # Create a task to run the async subscription
                    asyncio.create_task(async_subscribe())
                else:
                    # If not in Tkinter context, try to get event loop
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(self.event_bus.subscribe(event_name, handler))
                        else:
                            loop.run_until_complete(self.event_bus.subscribe(event_name, handler))
                    except Exception as e:
                        logger.error(f"Error setting up async event subscription: {e}")
                        return self._retry_subscription(event_name, handler, retry_count)
            else:
                # For synchronous subscribe method
                self.event_bus.subscribe(event_name, handler)
                
            logger.info(f"Subscribed to event: {event_name}")
            return True
                
        except Exception as e:
            logger.error(f"Error subscribing to {event_name}: {e}")
            logger.debug(traceback.format_exc())
            return self._retry_subscription(event_name, handler, retry_count)
    
    def _retry_subscription(self, event_name: str, handler: Callable, retry_count: int) -> bool:
        """
        Retry a failed subscription with exponential backoff.
        
        Args:
            event_name: Name of the event to subscribe to
            handler: Event handler function
            retry_count: Current retry attempt count
            
        Returns:
            bool: Success status of the retry attempt
        """
        if retry_count >= self.max_retries:
            logger.error(f"Failed to subscribe to {event_name} after {self.max_retries} attempts")
            return False
            
        next_retry = retry_count + 1
        delay = self.retry_backoff_factor ** next_retry  # exponential backoff
        
        logger.info(f"Retrying subscription to {event_name} in {delay} seconds (attempt {next_retry}/{self.max_retries})")
        
        # Schedule retry using Tkinter's after if available
        if hasattr(self, 'after') and self.after:
            self.after(int(delay * 1000), lambda: self._subscribe_with_retry(event_name, handler, next_retry))
        else:
            # Use asyncio sleep for retry if not in Tkinter context
            async def delayed_retry():
                await asyncio.sleep(delay)
                self._subscribe_with_retry(event_name, handler, next_retry)
                
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(delayed_retry())
                else:
                    loop.run_until_complete(delayed_retry())
            except Exception as e:
                logger.error(f"Error scheduling retry: {e}")
                return False
                
        return True  # Return True to indicate retry was scheduled

    def safe_publish(self, event_name: str, data: Any = None) -> bool:
        """
        Safely publish an event to the event bus with error handling.
        
        Args:
            event_name: Name of the event to publish
            data: Event data to publish
            
        Returns:
            bool: Success status of the publish attempt
        """
        try:
            if not hasattr(self, 'event_bus') or self.event_bus is None:
                logger.warning(f"Cannot publish {event_name}: event_bus is None")
                return False
                
            # Handle async vs sync publish
            if asyncio.iscoroutinefunction(self.event_bus.publish):
                # Async publish
                if hasattr(self, 'after') and self.after:  
                    # If we're in a Tkinter widget with after method
                    async def async_publish():
                        try:
                            await self.event_bus.publish(event_name, data)
                            return True
                        except Exception as e:
                            logger.error(f"Error in async publish of {event_name}: {e}")
                            return False
                            
                    # Create a task to run the async publish
                    asyncio.create_task(async_publish())
                else:
                    # If not in Tkinter context, try to get event loop
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(self.event_bus.publish(event_name, data))
                        else:
                            loop.run_until_complete(self.event_bus.publish(event_name, data))
                    except Exception as e:
                        logger.error(f"Error setting up async event publishing: {e}")
                        return False
            else:
                # Synchronous publish
                self.event_bus.publish(event_name, data)
                
            logger.debug(f"Published event: {event_name}")
            return True
                
        except Exception as e:
            logger.error(f"Error publishing {event_name}: {e}")
            logger.debug(traceback.format_exc())
            return False
