"""
Event Bus for Kingdom AI Component Communication

This module provides an event bus for component communication in the Kingdom AI system.
"""

import asyncio
import logging
import threading
import queue
from typing import Dict, Callable, List, Any

logger = logging.getLogger(__name__)

class EventBus:
    """
    Event Bus for Kingdom AI component communication.
    
    Provides a publish-subscribe pattern for components to communicate asynchronously.
    """
    
    def __init__(self):
        """Initialize the event bus."""
        self.subscribers = {}
        self.event_queue = queue.Queue()
        self.running = False
        self.thread = None
        logger.info("Event Bus initialized")
    
    def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to an event type.
        
        Args:
            event_type (str): Event type to subscribe to
            callback (Callable): Function to call when event occurs
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        self.subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to event: {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """
        Unsubscribe from an event type.
        
        Args:
            event_type (str): Event type to unsubscribe from
            callback (Callable): Function to remove from subscribers
        """
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            logger.debug(f"Unsubscribed from event: {event_type}")
    
    def publish(self, event_type: str, data: Any = None):
        """
        Publish an event to all subscribers.
        
        Args:
            event_type (str): Type of event to publish
            data (Any, optional): Data to pass to subscribers
        """
        self.event_queue.put((event_type, data))
        logger.debug(f"Published event: {event_type}")
    
    async def publish_async(self, event_type: str, data: Any = None):
        """
        Publish an event asynchronously.
        
        Args:
            event_type (str): Type of event to publish
            data (Any, optional): Data to pass to subscribers
        """
        self.publish(event_type, data)
    
    def _process_events(self):
        """Process events from the queue."""
        while self.running:
            try:
                # Get event with timeout to allow for clean shutdown
                event_type, data = self.event_queue.get(timeout=0.1)
                
                # Notify subscribers
                if event_type in self.subscribers:
                    for callback in self.subscribers[event_type]:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"Error in subscriber callback for {event_type}: {e}")
                
                self.event_queue.task_done()
            except queue.Empty:
                # Queue empty, continue waiting
                pass
            except Exception as e:
                logger.error(f"Error processing events: {e}")
    
    def start(self):
        """Start the event bus processing thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._process_events)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Event Bus started")
    
    def stop(self):
        """Stop the event bus."""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=1.0)
            logger.info("Event Bus stopped")

# Factory function
def get_event_bus():
    return EventBus()
