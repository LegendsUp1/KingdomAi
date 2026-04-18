"""
Kingdom AI - Event Bus Wrapper
Provides compatibility between synchronous code and the async EventBus.
"""

"""Kingdom AI - Event Bus Wrapper
Provides compatibility between synchronous code and the async EventBus.
"""

import asyncio
import logging
import traceback
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Coroutine, TypeVar

# Import the original EventBus
from core.event_bus import EventBus

T = TypeVar('T')

class EventBusWrapper:
    """
    Wrapper around EventBus to provide a synchronous interface 
    while handling async operations correctly.
    
    This wrapper ensures that coroutines are properly awaited and
    executed in the event loop, preventing 'coroutine not awaited' warnings.
    """
    
    def __init__(self, event_bus = None):
        """
        Initialize the EventBusWrapper with an EventBus instance.
        
        Args:
            event_bus: The EventBus instance to wrap, or None to create a new one
        """
        self._event_bus = event_bus
        self.logger = logging.getLogger("KingdomAI.EventBusWrapper")
        
    @property
    def event_bus(self):
        """
        Get the wrapped EventBus instance.
        
        Returns:
            The wrapped EventBus instance
        """
        return self._event_bus
        
    def subscribe(self, event_type: str, handler: Callable) -> bool:
        """
        Subscribe to an event.
        
        Args:
            event_type: The event type to subscribe to
            handler: The callback function to call when the event is triggered
            
        Returns:
            bool: True if subscribed successfully
        """
        try:
            # Check if the event bus has a synchronous method
            if hasattr(self._event_bus, 'subscribe_sync'):
                # Use the synchronous version from EventBus
                return self._event_bus.subscribe_sync(event_type, handler)
            elif hasattr(self._event_bus, 'subscribe'):
                # Handle async subscription safely
                if asyncio.iscoroutinefunction(self._event_bus.subscribe):
                    return self._run_coroutine_safely(self._event_bus.subscribe(event_type, handler))
                else:
                    return self._event_bus.subscribe(event_type, handler)
            # Default fallback
            return False
        except Exception as e:
            self.logger.error(f"Error subscribing to {event_type}: {e}")
            return False
        
    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """
        Unsubscribe from an event.
        
        Args:
            event_type: The event type to unsubscribe from
            handler: The callback function to remove
            
        Returns:
            bool: True if unsubscribed successfully
        """
        try:
            if hasattr(self._event_bus, 'unsubscribe_sync'):
                return self._event_bus.unsubscribe_sync(event_type, handler)
            elif hasattr(self._event_bus, 'unsubscribe'):
                if asyncio.iscoroutinefunction(self._event_bus.unsubscribe):
                    return self._run_coroutine_safely(self._event_bus.unsubscribe(event_type, handler))
                else:
                    return self._event_bus.unsubscribe(event_type, handler)
            return False
        except Exception as e:
            self.logger.error(f"Error unsubscribing from {event_type}: {e}")
            return False
        
    def publish(self, event_type: str, data: Any = None) -> None:
        """Publish an event to subscribers.
        
        Args:
            event_type: The event type to publish
            data: The data to pass to handlers
        """
        try:
            # Check if the event bus has a synchronous method
            if hasattr(self._event_bus, 'publish_sync'):
                # Use the synchronous version from EventBus
                self._event_bus.publish_sync(event_type, data)
            elif hasattr(self._event_bus, 'publish'):
                # Handle async publish safely
                if asyncio.iscoroutinefunction(self._event_bus.publish):
                    self._run_coroutine_safely(self._event_bus.publish(event_type, data))
                else:
                    self._event_bus.publish(event_type, data)
        except Exception as e:
            self.logger.error(f"Error publishing event {event_type}: {e}")
            
    def get_subscribers(self, event_type: str = None) -> Dict[str, List[Callable]]:
        """Get all subscribers for an event type or all event types.
        
        Args:
            event_type: The event type to get subscribers for, or None for all
            
        Returns:
            A dictionary mapping event types to lists of handlers
        """
        if hasattr(self._event_bus, 'get_subscribers'):
            if asyncio.iscoroutinefunction(self._event_bus.get_subscribers):
                try:
                    result = self._run_coroutine_safely(self._event_bus.get_subscribers(event_type))
                    if isinstance(result, dict):
                        return result
                    return {}
                except Exception as e:
                    self.logger.error(f"Error in get_subscribers: {e}")
                    return {}
            else:
                return self._event_bus.get_subscribers(event_type)
        else:
            self.logger.warning("get_subscribers not supported by the event bus implementation")
            return {}
        
    def wait_for(self, event_type: str, timeout: float = None) -> Any:
        """Wait for an event to be published.
        
        Args:
            event_type: The event type to wait for
            timeout: Maximum time to wait in seconds
            
        Returns:
            The event data or None if timed out
        """
        if hasattr(self._event_bus, 'wait_for'):
            if asyncio.iscoroutinefunction(self._event_bus.wait_for):
                try:
                    return self._run_coroutine_safely(self._event_bus.wait_for(event_type, timeout))
                except Exception as e:
                    self.logger.error(f"Error in wait_for({event_type}): {e}")
                    return None
            else:
                return self._event_bus.wait_for(event_type, timeout)
        else:
            self.logger.warning("wait_for not supported by the event bus implementation")
            return None
            
    def _run_coroutine_safely(self, coro: Coroutine) -> bool:
        """Safely run a coroutine in the current event loop or a new one.
        
        Args:
            coro: The coroutine to run
            
        Returns:
            True if the coroutine was scheduled or executed, False on error
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If the loop is running, create a future and schedule the coroutine
                asyncio.run_coroutine_threadsafe(coro, loop)
                # Return a default True value since we can't wait for the future in a running loop
                return True
            else:
                # If the loop is not running, run the coroutine to completion
                result = loop.run_until_complete(coro)
                return True if result is None else bool(result)
        except RuntimeError:
            # If no event loop exists in this thread, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro)
                return True if result is None else bool(result)
            finally:
                loop.close()
        

            
    def publish_sync(self, event_type: str, data: Any = None) -> None:
        """Publish an event synchronously.
        
        This method is guaranteed to complete before returning.
        
        Args:
            event_type: The event type to publish
            data: The data to pass to handlers
        """
        try:
            if hasattr(self._event_bus, 'publish_sync'):
                self._event_bus.publish_sync(event_type, data)
            else:
                # Create a new loop if needed and run the coroutine to completion
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._event_bus.publish(event_type, data))
                finally:
                    loop.close()
        except Exception as e:
            self.logger.error(f"Error in sync publish for event {event_type}: {e}")

    # Add a compatibility method for components expecting an "emit" method
    def emit(self, event_type: str, data: Any = None) -> None:
        """
        Alias for publish for compatibility with components expecting emit.
        """
        return self.publish(event_type, data)
        
    def register_event(self, event_type: str) -> bool:
        """
        Register an event type in the system.
        
        Args:
            event_type: The event type to register
            
        Returns:
            bool: True if registered successfully, False if already registered
        """
        # Register is already synchronous
        return self._event_bus.register_event(event_type)

    # This was a duplicate emit method and has been removed
    # The emit method is already defined above

# Global singleton for the wrapper
_event_bus_wrapper = None

def get_event_bus_wrapper(event_bus: Optional[EventBus] = None) -> EventBusWrapper:
    """
    Get the global EventBusWrapper instance.
    
    Args:
        event_bus: Optional existing EventBus instance to wrap
        
    Returns:
        EventBusWrapper: The global EventBusWrapper instance
    """
    global _event_bus_wrapper
    if _event_bus_wrapper is None:
        if event_bus is None:
            # Get the global EventBus instance
            # Import the function at usage time to avoid circular imports
            try:
                from core.event_bus import get_event_bus
                event_bus = get_event_bus()
            except (ImportError, AttributeError):
                logger.error("Failed to import get_event_bus from core.event_bus. Creating a new EventBus instance.")
                event_bus = EventBus()
        _event_bus_wrapper = EventBusWrapper(event_bus)
    return _event_bus_wrapper

# Decorator to make async methods usable in synchronous code
def sync_method(func):
    """
    Decorator to make async methods usable in synchronous code.
    
    Example usage:
        @sync_method
        async def my_async_method(self, arg1, arg2):
            await asyncio.sleep(1)
            return arg1 + arg2
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Try to get the current event loop
            try:
                loop = asyncio.get_event_loop()
                is_new_loop = False
            except RuntimeError:
                # If no event loop exists in this thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                is_new_loop = True

            # Check if the loop is running
            if loop.is_running():
                # For already running loops, we'll create a future and ensure it completes
                future = asyncio.run_coroutine_threadsafe(func(*args, **kwargs), loop)
                return future.result()
            else:
                # If loop is not running, run the coroutine until complete
                result = loop.run_until_complete(func(*args, **kwargs))
                return result
                
        except Exception as e:
            logger.error(f"Error in sync_method {func.__name__}: {e}")
            traceback.print_exc()
            raise
        finally:
            # Only close the loop if we created it
            if 'is_new_loop' in locals() and is_new_loop and 'loop' in locals():
                loop.close()

    return wrapper
