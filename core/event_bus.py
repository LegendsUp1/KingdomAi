"""
Kingdom AI - UNIFIED Event Bus (single entry point, no confusion).

All event bus types are combined into ONE system:
- SOTA 2026 (default): priority queues, backpressure, metrics, batching, GPU-ready.
- Legacy (fallback): full original implementation when SOTA import fails.
- DynamicEventBus: extends EventBus (trigger, on, etc.) - use EventBus directly.
- HFT: enable_hft_mode() wires 100ms/250ms timers from core.hft_communication.

Usage:
  from core.event_bus import EventBus, EventBusError
  bus = EventBus.get_instance()  # same singleton everywhere
  bus.subscribe('event.type', handler)
  bus.publish('event.type', data)
  bus.trigger('event.type', data)   # alias publish_sync
  bus.on('event.type', handler)     # alias subscribe

No data or behavior is lost: legacy implementation retained as _LegacyEventBus.
"""

import asyncio
import fnmatch
import time
import logging
import threading
import traceback
import inspect
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional

# Configure logger
logger = logging.getLogger(__name__)

# Import the new AsyncTaskManager
try:
    from .async_task_manager import AsyncTaskManager, get_global_task_manager
except ImportError:
    # Fallback if async_task_manager is not available
    logger.warning("AsyncTaskManager not available, using fallback")
    AsyncTaskManager = None
    get_global_task_manager = lambda: None


_QT_DISPATCHER = None
_QT_DISPATCHER_LOCK = threading.Lock()


def _get_qt_dispatcher():
    global _QT_DISPATCHER
    if _QT_DISPATCHER is not None:
        return _QT_DISPATCHER
    with _QT_DISPATCHER_LOCK:
        if _QT_DISPATCHER is not None:
            return _QT_DISPATCHER
        try:
            from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, Qt, QCoreApplication
        except Exception:
            return None
        app = QCoreApplication.instance()
        if app is None:
            return None

        class _QtDispatcher(QObject):
            invoke = pyqtSignal(object, object, object)

            def __init__(self):
                super().__init__()
                self.invoke.connect(self._run, Qt.ConnectionType.QueuedConnection)

            @pyqtSlot(object, object, object)
            def _run(self, fn, args, kwargs):
                try:
                    fn(*args, **kwargs)
                except Exception:
                    try:
                        logger.error("Error in Qt-dispatched handler")
                        logger.error(traceback.format_exc())
                    except Exception:
                        pass

        dispatcher = _QtDispatcher()
        try:
            dispatcher.moveToThread(app.thread())
        except Exception:
            pass
        _QT_DISPATCHER = dispatcher
        return dispatcher


class EventBusError(Exception):
    """Exception raised for errors in the EventBus operations.
    
    Attributes:
        message -- explanation of the error
        event_type -- the event type that caused the error (if applicable)
        data -- the event data that caused the error (if applicable)
    """
    
    def __init__(self, message: str, event_type: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        self.message = message
        self.event_type = event_type
        self.data = data
        super().__init__(self.message)


class _LegacyEventBus:
    """
    Legacy Event Bus (retained for fallback when SOTA 2026 is unavailable).
    All code should use the unified EventBus export below.
    """

    # Singleton instance
    _instance: Optional['_LegacyEventBus'] = None

    @classmethod
    def get_instance(cls) -> '_LegacyEventBus':
        """Get or create the singleton instance."""
        if cls._instance is None:
            logger.info("Creating new Legacy EventBus instance")
            cls._instance = _LegacyEventBus()
        return cls._instance


    @classmethod
    def class_emit(cls, event_type, data=None):
        """Class method alias for publish to ensure compatibility with components expecting class methods.
        This delegates to an instance method when called on an instance.

        Args:
            event_type: The event type to emit
            data: The data to pass to the handlers

        Returns:
            bool: True if published successfully (when called on instance)
                 False when called on class (indicates delegated to instance)
        """
        # When called as class method, log a warning but allow code to continue
        # This is expected to be later replaced by an instance method call
        logging.warning(
            f"Class-level EventBus.class_emit called for {event_type}. This is a compatibility shim."
        )
        return False

    def __init__(self):
        """Initialize the event bus with 2025 task management."""
        self.logger = logging.getLogger("KingdomAI.EventBus")
        # 2025: Updated to store subscription dictionaries instead of just callables
        self._handlers: Dict[str, List[Dict[str, Any]]] = {} 
        self._handler_lock = threading.RLock()
        self._registered_events = set()  # type: Set[str]
        
        # CRITICAL FIX: Add component registry to EventBus for proper data flow
        self._components: Dict[str, Any] = {}
        self._component_lock = threading.RLock()
        
        # Initialize task manager integration
        self._task_manager = get_global_task_manager() if get_global_task_manager else None
        if self._task_manager:
            self.logger.info("EventBus initialized with AsyncTaskManager integration")
        else:
            self.logger.warning("EventBus initialized without AsyncTaskManager (fallback mode)")

        self._owner_thread_ident = threading.get_ident()
        self._loop = None
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                self._loop = asyncio.get_event_loop()
            except Exception:
                self._loop = None

        self._active_tasks = set()
        self._shutting_down = False

        self._event_history_lock = threading.RLock()
        self._event_seq = 0
        self._event_history = deque(maxlen=5000)  # SOTA 2026: Reduced from 10K to save memory
        # SOTA 2026: Handler lookup cache - invalidated on subscribe/unsubscribe
        self._handler_cache: Dict[str, List[Any]] = {}
        self._handler_cache_valid = False

    # SOTA 2026: High-frequency events that should NOT be recorded to history
    _SKIP_HISTORY_PREFIXES = (
        "ai.response.delta", "ai.pipeline.telemetry", "voice.speak.delta",
        "mining.stats", "sentience", "learning.", "memory.store",
        "component.registered", "component_registered",
    )

    def _record_event(self, event_type: str, data: Any) -> None:
        try:
            # Skip high-frequency events from history to reduce lock contention
            if event_type.startswith(self._SKIP_HISTORY_PREFIXES):
                return
            with self._event_history_lock:
                self._event_seq += 1
                self._event_history.append({
                    "seq": self._event_seq,
                    "timestamp": time.time(),
                    "event_type": event_type,
                })
        except Exception:
            return

    def get_event_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            with self._event_history_lock:
                events = list(self._event_history)
            if isinstance(limit, int) and limit > 0:
                return events[-limit:]
            return events
        except Exception:
            return []

    def get_event_history_since(self, seq: int) -> List[Dict[str, Any]]:
        try:
            with self._event_history_lock:
                if not isinstance(seq, int) or seq <= 0:
                    return list(self._event_history)
                return [e for e in self._event_history if int(e.get("seq", 0)) > seq]
        except Exception:
            return []

    def clear_event_history(self) -> None:
        try:
            with self._event_history_lock:
                self._event_history.clear()
        except Exception:
            return

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._owner_thread_ident = threading.get_ident()

    def _log_task_exception(self, task: asyncio.Task, event_type: str, handler: Callable) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as e:
            handler_name = getattr(handler, "__name__", str(handler))
            self.logger.error(f"Async handler {handler_name} failed for event {event_type}: {e}")
            self.logger.error(traceback.format_exc())

    def _track_task(self, task: asyncio.Task, event_type: str, handler: Callable) -> None:
        try:
            self._active_tasks.add(task)

            def _done(t: asyncio.Task) -> None:
                try:
                    self._active_tasks.discard(t)
                finally:
                    self._log_task_exception(t, event_type, handler)

            task.add_done_callback(_done)
        except Exception:
            try:
                task.add_done_callback(lambda t: self._log_task_exception(t, event_type, handler))
            except Exception:
                pass

    def register_event(self, event_type: str) -> bool:
        """Register an event type in the system.

        Args:
            event_type: The event type to register

        Returns:
            bool: True if registered successfully, False if already registered
        """
        with self._handler_lock:
            if event_type in self._registered_events:
                return False

            self._registered_events.add(event_type)
            self._handlers[event_type] = []
            return True

    def _matches_event(self, pattern: str, event_type: str) -> bool:
        try:
            if pattern == event_type:
                return True
            if "*" not in pattern:
                return False
            return fnmatch.fnmatchcase(event_type, pattern)
        except Exception:
            return False

    def _collect_matching_subscriptions(self, event_type: str) -> List[Any]:
        subscriptions: List[Any] = []
        seen_callbacks: set[int] = set()

        def _add(subs: List[Any]) -> None:
            for sub in subs:
                callback = None
                if isinstance(sub, dict):
                    callback = sub.get("callback")
                else:
                    callback = sub
                if callback is None:
                    continue
                cb_id = id(callback)
                if cb_id in seen_callbacks:
                    continue
                seen_callbacks.add(cb_id)
                subscriptions.append(sub)

        try:
            direct = self._handlers.get(event_type)
            if isinstance(direct, list) and direct:
                _add(direct)

            for pattern, subs in self._handlers.items():
                if pattern == event_type:
                    continue
                if "*" not in pattern:
                    continue
                if not subs:
                    continue
                if self._matches_event(pattern, event_type):
                    _add(subs)
        except Exception:
            return subscriptions

        return subscriptions

    def subscribe(self, event_type: str, handler: Callable) -> bool:
        """2025 Subscribe to an event with proper async task management.
        
        FIXED: Changed from async to sync to avoid task nesting errors.
        This method is now safe to call from any context (sync or async).

        Args:
            event_type: The event type to subscribe to
            handler: The callback function to call when the event is published

        Returns:
            bool: True if subscribed successfully
        """
        # CRITICAL FIX: Make this a sync method to avoid "Cannot enter into task" errors
        try:
            if getattr(self, "_shutting_down", False):
                return False

            # Use task manager for async operations if available
            task_manager = get_global_task_manager() if get_global_task_manager else None
            
            with self._handler_lock:
                # Auto-register the event type if not already registered
                if event_type not in self._registered_events:
                    self.register_event(event_type)

                # Validate callback
                if not callable(handler):
                    raise ValueError(f"Handler must be callable, got {type(handler)}")

                # Create subscription info
                subscription = {
                    'callback': handler,
                    'is_async': asyncio.iscoroutinefunction(handler),
                    'task_manager': task_manager
                }

                # Add the handler if not already subscribed
                handler_list = self._handlers[event_type]
                if handler not in [sub['callback'] for sub in handler_list]:
                    handler_list.append(subscription)
                    self._handler_cache_valid = False  # Invalidate cache
                    self.logger.debug(
                        f"Handler {handler.__name__} subscribed to {event_type} (async: {subscription['is_async']})"
                    )

                return True
                
        except Exception as e:
            self.logger.error(f"Subscription failed for {event_type}: {e}")
            return False
            
    def subscribe_async(self, event_type: str, handler: Callable) -> bool:
        """Alias for subscribe method for backward compatibility.
        
        FIXED: Now just calls subscribe() directly since it's sync.
        This method exists to support legacy code that expects subscribe_async.
        
        Args:
            event_type: The event type to subscribe to
            handler: The callback function to call when the event is published
            
        Returns:
            bool: True if subscription was successful
        """
        self.logger.debug(f"Calling subscribe for {handler.__name__} to {event_type} via subscribe_async alias")
        # subscribe() is now sync, so just call it directly
        return self.subscribe(event_type, handler)

    def subscribe_sync(self, event_type: str, handler: Callable) -> bool:
        """Subscribe to an event synchronously.

        This is a non-async version of subscribe for components that need synchronous subscription.

        Args:
            event_type: The event type to subscribe to
            handler: The callback function to call when the event is published

        Returns:
            bool: True if subscribed successfully
        """
        with self._handler_lock:
            # Auto-register the event type if not already registered
            if event_type not in self._registered_events:
                self.register_event(event_type)

            # Create subscription info matching main subscribe() pattern
            subscription = {
                'callback': handler,
                'is_async': asyncio.iscoroutinefunction(handler),
                'task_manager': None
            }

            # Add the handler if not already subscribed
            handler_list = self._handlers[event_type]
            if handler not in [sub['callback'] for sub in handler_list]:
                handler_list.append(subscription)
                self._handler_cache_valid = False  # Invalidate cache
                self.logger.debug(
                    f"Handler {handler.__name__} subscribed to {event_type} (sync)"
                )

            return True

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """Unsubscribe a specific handler from an event.

        Args:
            event_type: The event type to unsubscribe from
            handler: The callback function to remove

        Returns:
            bool: True if unsubscribed successfully, False if not found
        """
        with self._handler_lock:
            if event_type not in self._handlers:
                return False

            # Find subscription with matching callback
            handler_list = self._handlers[event_type]
            for subscription in handler_list:
                if subscription['callback'] == handler:
                    handler_list.remove(subscription)
                    self.logger.debug(
                        f"Handler {handler.__name__} unsubscribed from {event_type}"
                    )
                    return True

            return False
            
    def unsubscribe_all(self, event_type: Optional[str] = None) -> bool:
        """Unsubscribe all handlers from an event or all events.
        
        Args:
            event_type: The event type to clear handlers from. If None, clears all handlers.
            
        Returns:
            bool: True if successful, False if event_type was specified but not found
        """
        with self._handler_lock:
            if event_type is not None:
                if event_type not in self._handlers:
                    return False
                self._handlers[event_type] = []
                self.logger.debug(f"Cleared all handlers for event: {event_type}")
            else:
                # Clear all handlers for all events
                for evt in self._handlers:
                    self._handlers[evt] = []
                self.logger.debug("Cleared all event handlers")
            return True

    def publish(self, event_type: str, data: Any = None) -> bool:
        """Publish an event to all subscribers.
        
        FIXED: Changed from async to sync to avoid task nesting errors.
        This method is now safe to call from any context (sync or async).

        Args:
            event_type: The event type to publish
            data: The data to pass to the handlers

        Returns:
            bool: True if published successfully
        """
        # CRITICAL FIX: Make this a sync method to avoid "Cannot enter into task" errors
        if getattr(self, "_shutting_down", False):
            return False
        self._record_event(event_type, data)

        # SOTA 2026: Collect handlers under lock, execute OUTSIDE lock.
        # Prevents slow handlers from blocking all other publish() calls.
        with self._handler_lock:
            if event_type not in self._handlers:
                self.register_event(event_type)
                self.logger.debug(f"Auto-registered event type: {event_type}")

            matching_subscriptions = list(self._collect_matching_subscriptions(event_type))

        if not matching_subscriptions:
            return True

        success = True
        is_owner_thread = threading.get_ident() == getattr(self, "_owner_thread_ident", None)
        loop = getattr(self, "_loop", None)
        for handler_info in matching_subscriptions:
            try:
                # Handle both dict-style and direct function handlers
                if isinstance(handler_info, dict):
                    handler = handler_info['callback']
                    is_async = handler_info.get('is_async', asyncio.iscoroutinefunction(handler))
                else:
                    handler = handler_info
                    is_async = asyncio.iscoroutinefunction(handler)

                # Handle both async and sync handlers
                if is_async:
                    if loop is None:
                        handler_name = getattr(handler, "__name__", str(handler))
                        self.logger.warning(f"Skipping async handler {handler_name} - no event loop")
                    else:
                        def _invoke_async_handler() -> None:
                            try:
                                result = handler(data)
                                if inspect.isawaitable(result):
                                    task = asyncio.ensure_future(result, loop=loop)
                                    self._track_task(task, event_type, handler)
                            except Exception as e:
                                handler_name = getattr(handler, "__name__", str(handler))
                                self.logger.error(f"Error scheduling async handler {handler_name} for event {event_type}: {e}")
                                self.logger.error(traceback.format_exc())

                        if is_owner_thread:
                            if loop.is_running():
                                loop.call_soon(_invoke_async_handler)
                            else:
                                _invoke_async_handler()
                        else:
                            if loop.is_running():
                                loop.call_soon_threadsafe(_invoke_async_handler)
                            else:
                                handler_name = getattr(handler, "__name__", str(handler))
                                self.logger.warning(f"Skipping async handler {handler_name} - event loop not running")
                else:
                    if is_owner_thread:
                        handler(data)
                    else:
                        if loop is not None and loop.is_running():
                            loop.call_soon_threadsafe(handler, data)
                        else:
                            dispatcher = _get_qt_dispatcher()
                            if dispatcher is not None:
                                try:
                                    dispatcher.invoke.emit(handler, (data,), {})
                                    continue
                                except Exception:
                                    pass
                            # CRITICAL FIX: Execute handler directly instead of skipping
                            # This is safe for most handlers and prevents flooding logs
                            try:
                                handler(data)
                            except Exception as e:
                                handler_name = getattr(handler, "__name__", str(handler))
                                self.logger.debug(f"Handler {handler_name} error from non-owner thread: {e}")
            except Exception as e:
                handler_name = getattr(handler, "__name__", str(handler)) if isinstance(handler_info, dict) else getattr(handler_info, "__name__", str(handler_info))
                self.logger.error(
                    f"Error in handler {handler_name} for event {event_type}: {e}"
                )
                self.logger.error(traceback.format_exc())
                success = False
                # Continue processing other handlers

        return success

    def publish_sync(self, event_type: str, data: Any = None) -> bool:
        """Publish an event to all subscribers synchronously.

        FIXED: Collect subscriptions under lock, execute OUTSIDE lock.
        Previous version held the lock during ALL handler execution, causing
        30fps vision frame handlers to block every other event in the system.
        """
        self._record_event(event_type, data)

        with self._handler_lock:
            if event_type not in self._handlers:
                self.register_event(event_type)
                self.logger.debug(f"Auto-registered event type: {event_type}")

            matching_subscriptions = list(self._collect_matching_subscriptions(event_type))

        if not matching_subscriptions:
            return True

        success = True
        is_owner_thread = threading.get_ident() == getattr(self, "_owner_thread_ident", None)
        loop = getattr(self, "_loop", None)
        for subscription in matching_subscriptions:
            handler = subscription['callback'] if isinstance(subscription, dict) else subscription
            try:
                if asyncio.iscoroutinefunction(handler):
                    if loop is None or (hasattr(loop, 'is_closed') and loop.is_closed()):
                        handler_name = getattr(handler, "__name__", str(handler))
                        self.logger.warning(f"Skipping async handler {handler_name} - no event loop or loop closed")
                    else:
                        def _invoke_async_handler() -> None:
                            try:
                                if loop.is_closed():
                                    return
                                result = handler(data)
                                if inspect.isawaitable(result):
                                    task = asyncio.ensure_future(result, loop=loop)
                                    self._track_task(task, event_type, handler)
                            except RuntimeError as re:
                                if "Event loop is closed" in str(re):
                                    return
                                handler_name = getattr(handler, "__name__", str(handler))
                                self.logger.error(f"Error scheduling async handler {handler_name} for event {event_type}: {re}")
                            except Exception as e:
                                handler_name = getattr(handler, "__name__", str(handler))
                                self.logger.error(f"Error scheduling async handler {handler_name} for event {event_type}: {e}")
                                self.logger.error(traceback.format_exc())

                        if is_owner_thread:
                            if loop.is_running() and not loop.is_closed():
                                loop.call_soon(_invoke_async_handler)
                            else:
                                _invoke_async_handler()
                        else:
                            if loop.is_running():
                                loop.call_soon_threadsafe(_invoke_async_handler)
                            else:
                                handler_name = getattr(handler, "__name__", str(handler))
                                self.logger.warning(f"Skipping async handler {handler_name} - event loop not running")
                else:
                    if is_owner_thread:
                        handler(data)
                    else:
                        if loop is not None and loop.is_running():
                            loop.call_soon_threadsafe(handler, data)
                        else:
                            dispatcher = _get_qt_dispatcher()
                            if dispatcher is not None:
                                try:
                                    dispatcher.invoke.emit(handler, (data,), {})
                                    continue
                                except Exception:
                                    pass
                            try:
                                handler(data)
                            except Exception as e:
                                handler_name = getattr(handler, "__name__", str(handler))
                                self.logger.debug(f"Handler {handler_name} error from non-owner thread: {e}")
            except Exception as e:
                handler_name = getattr(handler, "__name__", str(handler))
                self.logger.error(
                    f"Error in handler {handler_name} for event {event_type}: {e}"
                )
                self.logger.error(traceback.format_exc())
                success = False

        return success

    def emit(self, event_type: str, data: Any = None) -> bool:
        """Alias for publish method to ensure compatibility with components that call emit.

        Args:
            event_type: The event type to emit
            data: The data to pass to the handlers

        Returns:
            bool: True if published successfully
        """
        # Create a future and set the result as we can't await in a non-async method
        future = asyncio.Future()

        # STATE-OF-THE-ART: Enhanced asyncio task management with proper cleanup (2024/2025)
        try:
            # Get event loop with proper handling - check if closed
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    loop = asyncio.get_event_loop()
                    # Check if loop is closed
                    if loop.is_closed():
                        loop = None
                except RuntimeError:
                    loop = None
            
            # Advanced task management with cleanup tracking
            if not hasattr(self, '_active_tasks'):
                self._active_tasks = set()
                
            def create_managed_task():
                """Call sync publish and set result - NO TASK NEEDED"""
                # CRITICAL FIX: publish() is sync and returns bool, not coroutine
                # Just call it directly and set result - no async task needed
                try:
                    result = self.publish(event_type, data)
                    if not future.done():
                        future.set_result(result)
                except Exception as e:
                    self.logger.error(f"Error in emit({event_type}): {e}")
                    if not future.done():
                        future.set_result(False)
                return None
            
            # Thread-safe task creation with closed loop check
            if loop is not None and not loop.is_closed():
                if loop.is_running():
                    # Loop is running - use call_soon_threadsafe for thread safety
                    try:
                        loop.call_soon_threadsafe(create_managed_task)
                    except RuntimeError:
                        # Loop closed between check and call - run directly
                        create_managed_task()
                else:
                    # Loop not running - safe to create task directly
                    create_managed_task()
            else:
                # No valid loop - just call publish directly
                create_managed_task()
                
            return True
        except Exception as e:
            self.logger.error(f"Enhanced asyncio task management error in emit({event_type}): {e}")
            return False
    
    async def cleanup_pending_tasks(self):
        """STATE-OF-THE-ART: Clean up all pending tasks to prevent 'Task was destroyed but it is pending' errors"""
        if hasattr(self, '_active_tasks') and self._active_tasks:
            self.logger.info(f"Cleaning up {len(self._active_tasks)} pending tasks")
            
            # Cancel all active tasks
            for task in list(self._active_tasks):
                if not task.done():
                    task.cancel()
            
            # Wait for all tasks to complete with timeout
            if self._active_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*list(self._active_tasks), return_exceptions=True),
                        timeout=5.0  # 5 second timeout
                    )
                except asyncio.TimeoutError:
                    self.logger.warning("Some tasks did not complete within timeout during cleanup")
                except Exception as e:
                    self.logger.error(f"Error during task cleanup: {e}")
            
            self._active_tasks.clear()
            self.logger.info("Task cleanup completed")
    
    def shutdown(self):
        """Enhanced shutdown with proper task cleanup"""
        try:
            self._shutting_down = True
        except Exception:
            pass

        try:
            try:
                self.unsubscribe_all()
            except Exception:
                pass

            try:
                with self._component_lock:
                    self._components.clear()
            except Exception:
                pass

            # Run task cleanup if we have an event loop
            if hasattr(self, '_active_tasks') and self._active_tasks:
                try:
                    loop = asyncio.get_running_loop()
                    # Schedule cleanup task
                    cleanup_task = loop.create_task(self.cleanup_pending_tasks())
                    # Don't wait for it, just let it run
                except RuntimeError:
                    # No running loop, just clear tasks
                    if hasattr(self, '_active_tasks'):
                        for task in list(self._active_tasks):
                            if not task.done():
                                task.cancel()
                        self._active_tasks.clear()
                        
        except Exception as e:
            self.logger.error(f"Error during event bus shutdown: {e}")
        
        # Call parent shutdown if it exists
        try:
            from core.base_component import BaseComponent
            shutdown_fn = getattr(BaseComponent, "shutdown", None)
            if isinstance(self, BaseComponent) and callable(shutdown_fn):
                shutdown_fn(self)
        except Exception:
            pass

    def _schedule_async_handler(
        self, handler: Callable, event_type: str, data: Any
    ) -> None:
        """Schedule an async handler to run in the event loop.

        Args:
            handler: The async handler function
            event_type: The event type
            data: The event data
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            task = loop.create_task(handler(data))
            task.add_done_callback(self._handle_async_result)
        else:
            import threading
            def _run_in_thread():
                _loop = asyncio.new_event_loop()
                try:
                    _loop.run_until_complete(handler(data))
                except Exception as e:
                    self.logger.debug("Async handler error in thread: %s", e)
                finally:
                    _loop.close()
            threading.Thread(target=_run_in_thread, daemon=True, name="AsyncHandler").start()

    def _handle_async_result(self, task: asyncio.Task) -> None:
        """Handle the result of an async task.

        Args:
            task: The completed task
        """
        try:
            # Get the result to handle any exceptions
            task.result()
        except asyncio.CancelledError:
            # Task was cancelled, not an error
            pass
        except Exception as e:
            self.logger.error(f"Error in async event handler: {str(e)}")
            self.logger.debug(traceback.format_exc())

    def get_handlers(self, event_type: str) -> List[Callable]:
        """Get all handlers for an event type.

        Args:
            event_type: The event type

        Returns:
            List of handlers (callbacks) for the event type
        """
        with self._handler_lock:
            if event_type not in self._handlers:
                return []

            # Extract callbacks from subscription Dicts
            return [sub['callback'] for sub in self._handlers[event_type]]

    def get_event_types(self) -> List[str]:
        """Get all registered event types.

        Returns:
            List of registered event types
        """
        with self._handler_lock:
            return list(self._registered_events)

    async def initialize(self) -> bool:
        """Initialize the event bus.

        This method is required for compatibility with the component initialization system.

        Returns:
            bool: True indicating successful initialization
        """
        self.logger.info("Initializing EventBus")
        return True

    async def start(self) -> bool:
        """Start the event bus.

        This method is required for compatibility with the component lifecycle.

        Returns:
            bool: True indicating successful start
        """
        self.logger.info("Starting EventBus")
        return True

    async def stop(self) -> bool:
        """Stop the event bus.

        This method is required for compatibility with the component lifecycle.

        Returns:
            bool: True indicating successful stop
        """
        self.logger.info("Stopping EventBus")
        return True
    
    # ========================================================================
    # CRITICAL FIX: Component Registry Methods for Proper Data Flow
    # ========================================================================
    
    def register_component(self, name: str, component: Any) -> bool:
        """Register a component with the event bus for direct access.
        
        This allows GUI components to access backend systems via:
        trading_system = event_bus.get_component('trading_system')
        
        Args:
            name: Component name (e.g., 'trading_system', 'mining_system')
            component: Component instance
            
        Returns:
            bool: True if registered successfully
        """
        with self._component_lock:
            if name in self._components:
                self.logger.warning(f"Component '{name}' already registered, updating...")
            
            self._components[name] = component
            self.logger.info(f"✅ Registered component '{name}' on EventBus")
            
            # Publish component registration event - BOTH formats for compatibility
            # CyberpunkLoadingScreen subscribes to component.registered (with dot)
            # Legacy code may still use component_registered (underscore)
            self.publish('component.registered', {'name': name, 'component': component})
            self.publish('component_registered', {'name': name, 'component': component})
            return True
    
    def get_component(self, name: str, silent: bool = False) -> Optional[Any]:
        """Get a registered component by name.
        
        This is how GUI tabs access backend systems:
        trading_system = event_bus.get_component('trading_system')
        if trading_system:
            trading_system.execute_trade(...)
        
        Args:
            name: Component name
            silent: If True, don't log warning when component not found
            
        Returns:
            Component instance or None if not found
        """
        with self._component_lock:
            component = self._components.get(name)
            if component is None and not silent:
                # Only warn once per component to reduce log spam
                if not hasattr(self, '_warned_components'):
                    self._warned_components = set()
                if name not in self._warned_components:
                    self._warned_components.add(name)
                    self.logger.debug(f"Component '{name}' not yet registered. Available: {list(self._components.keys())}")
            return component
    
    def get_all_components(self) -> Dict[str, Any]:
        """Get all registered components.
        
        Returns:
            Dictionary of all registered components
        """
        with self._component_lock:
            return self._components.copy()
    
    def has_component(self, name: str) -> bool:
        """Check if a component is registered.
        
        Args:
            name: Component name
            
        Returns:
            bool: True if component is registered
        """
        with self._component_lock:
            return name in self._components
    
    def unregister_component(self, name: str) -> bool:
        """Unregister a component.
        
        Args:
            name: Component name
            
        Returns:
            bool: True if unregistered successfully
        """
        with self._component_lock:
            if name in self._components:
                del self._components[name]
                self.logger.info(f"Unregistered component '{name}'")
                # Publish both formats for compatibility
                self.publish('component.unregistered', {'name': name})
                self.publish('component_unregistered', {'name': name})
                return True
            return False

    # =========================================================================
    # SOTA 2025: HIGH-FREQUENCY TRADING INTEGRATION
    # =========================================================================
    
    def enable_hft_mode(self) -> bool:
        """
        Enable HIGH-FREQUENCY TRADING mode for the event bus.
        
        This integrates with the HFT Communication System for:
        - 100ms data polling (10 updates/second)
        - 250ms UI updates (4 updates/second)
        - Priority-based event processing
        - Non-blocking thread pool execution
        
        Returns:
            bool: True if HFT mode enabled successfully
        """
        try:
            from .hft_communication import (
                get_hft_manager, 
                get_hft_event_bus,
                HFTEventPriority,
                init_hft_system
            )
            
            # Initialize HFT system
            self._hft_manager = init_hft_system()
            self._hft_event_bus = get_hft_event_bus()
            self._hft_enabled = True
            
            self.logger.info("🚀 EventBus HFT MODE ENABLED")
            self.logger.info("   Data polling: 100ms (10/sec)")
            self.logger.info("   UI updates: 250ms (4/sec)")
            self.logger.info("   Event processing: 10ms priority queue")
            
            return True
            
        except ImportError as e:
            self.logger.warning(f"HFT mode not available: {e}")
            self._hft_enabled = False
            return False
        except Exception as e:
            self.logger.error(f"HFT mode initialization failed: {e}")
            self._hft_enabled = False
            return False
    
    def publish_hft(self, event_type: str, data: Any = None, 
                    priority: str = "normal") -> bool:
        """
        Publish an event through the HFT system (non-blocking, priority-based).
        
        Args:
            event_type: Event type to publish
            data: Event data
            priority: "critical", "high", "normal", or "low"
            
        Returns:
            bool: True if published successfully
        """
        if not getattr(self, '_hft_enabled', False):
            # Fallback to standard publish
            return self.publish(event_type, data)
        
        try:
            from .hft_communication import HFTEventPriority
            
            # Map string priority to enum
            priority_map = {
                "critical": HFTEventPriority.CRITICAL,
                "high": HFTEventPriority.HIGH,
                "normal": HFTEventPriority.NORMAL,
                "low": HFTEventPriority.LOW,
            }
            hft_priority = priority_map.get(priority.lower(), HFTEventPriority.NORMAL)
            
            return self._hft_event_bus.publish(event_type, data, hft_priority)
            
        except Exception as e:
            self.logger.error(f"HFT publish error: {e}")
            return self.publish(event_type, data)
    
    def get_hft_stats(self) -> Dict[str, Any]:
        """Get HFT system performance statistics."""
        if not getattr(self, '_hft_enabled', False):
            return {"hft_enabled": False}

        try:
            return self._hft_manager.get_stats()
        except Exception as e:
            return {"error": str(e)}


# =============================================================================
# UNIFIED EVENT BUS: Single entry point for entire codebase
# =============================================================================
# All event bus types (legacy, dynamic, HFT, SOTA 2026) are combined into one.
# - SOTA 2026: priority queues, backpressure, metrics, trigger/on, get_handlers,
#   get_event_types, HFT integration (100ms/250ms timers when enable_hft_mode).
# - Legacy implementation retained as _LegacyEventBus when SOTA import fails.
# =============================================================================

try:
    from core.event_bus_sota_2026 import EventBusSOTA2026, create_sota_2026_event_bus
    EventBus = EventBusSOTA2026
    create_sota_2026_event_bus = create_sota_2026_event_bus  # re-export for custom config
    logger.info("Unified EventBus: using SOTA 2026 (priority, backpressure, HFT-ready)")
except Exception as e:
    logger.warning("Unified EventBus: SOTA 2026 unavailable (%s), using legacy", e)
    EventBus = _LegacyEventBus
    create_sota_2026_event_bus = None  # not available in legacy mode
