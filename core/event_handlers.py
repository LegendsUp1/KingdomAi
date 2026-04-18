"""
Event handlers for Kingdom AI system components.

This module provides base and tab-specific event handlers that enforce strict
Redis connection requirements and consistent event handling patterns.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Callable, TypeVar
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from functools import wraps

from core.redis_connector import RedisQuantumNexusConnector

T = TypeVar('T', bound='BaseEventHandler')

class EventHandlerError(Exception):
    """Base exception for event handler errors."""
    pass

class RedisConnectionError(EventHandlerError):
    """Raised when Redis connection fails."""
    pass

class BaseEventHandler(QObject):
    """
    Base event handler class that provides Redis connection management
    and event handling infrastructure.
    
    All tab-specific event handlers should inherit from this class.
    """
    # Signals
    status_update = pyqtSignal(str, str)  # message, level
    data_updated = pyqtSignal(str, object)  # data_type, data
    connection_state_changed = pyqtSignal(bool)  # connected
    
    # Strict Redis connection settings
    REDIS_PORT = 6380
    REDIS_PASSWORD = 'QuantumNexus2025'
    REDIS_HOST = 'localhost'
    
    def __init__(self, component_name: str, parent: Optional[QObject] = None):
        """Initialize the event handler.
        
        Args:
            component_name: Name of the component this handler manages
            parent: Parent QObject
        """
        super().__init__(parent)
        self.component_name = component_name
        self.logger = logging.getLogger(f"kingdom_ai.{component_name}.events")
        
        # Redis connection
        self.redis: Optional["RedisQuantumNexusConnector"] = None
        self._connected = False
        self._connection_retries = 0
        self._max_retries = 3
        
        # Event subscriptions
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._redis_subscriptions: Dict[str, Callable] = {}
        
        # Initialize connection
        self._init_redis_connection()
    
    def _init_redis_connection(self) -> None:
        """Initialize Redis connection with strict requirements."""
        try:
            self.logger.info("Initializing Redis connection...")
            
            # Create Redis connector with correct parameters (only event_bus is accepted)
            self.redis = RedisQuantumNexusConnector(
                event_bus=self  # For event publishing
            )
            self.logger.info(f"Redis connector created for {self.component_name}")
            
            # Test connection
            if not self.redis.health_check():
                raise RedisConnectionError("Redis health check failed")
                
            self._connected = True
            self.connection_state_changed.emit(True)
            self.logger.info("Redis connection established successfully")
            
        except Exception as e:
            self._handle_connection_error(e)
    
    def _handle_connection_error(self, error: Exception) -> None:
        """Handle Redis connection errors."""
        self._connected = False
        self.connection_state_changed.emit(False)
        
        error_msg = f"Redis connection error: {str(error)}"
        self.logger.warning(error_msg)
        self.status_update.emit(error_msg, "warning")
        
        # 2026 FIX: Do NOT force quit on Redis failure - continue in degraded mode
        # The system can function without Redis (caching disabled)
        self.logger.warning("⚠️ Redis unavailable - system will continue in degraded mode (caching disabled)")
        
    def initialize(self) -> bool:
        """Initialize the event handler.
        
        This method ensures all event handlers have an initialize method to prevent
        'no attribute initialize' errors. It should be called after initialization
        to set up any required resources and connections.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing {self.component_name} event handler")
        try:
            # Ensure Redis connection is established
            if not self._connected and self.redis:
                self.redis.initialize_redis_quantum()
                self._connected = True
                
            # Subscribe to relevant events
            self._subscribe_to_events()
            
            self.logger.info(f"{self.component_name} event handler initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize {self.component_name} event handler: {str(e)}")
            return False
    
    def _shutdown_on_failure(self, message: str) -> None:
        """Shut down the system due to a critical failure."""
        self.logger.critical(f"SYSTEM HALT: {message}")
        # Use QTimer to ensure UI thread processes the shutdown
        QTimer.singleShot(0, lambda: self._force_quit(message))
    
    def _force_quit(self, message: str) -> None:
        """Force quit the application."""
        from PyQt6.QtCore import QCoreApplication
        
        # Try to show error message if possible
        try:
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Critical Error")
            msg.setText("Kingdom AI - Fatal Error")
            msg.setInformativeText(
                f"A critical error has occurred and the system must shut down.\n\n"
                f"Error: {message}"
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.buttonClicked.connect(lambda: QCoreApplication.quit())
            msg.exec()
        except Exception as e:
            self.logger.error(f"Error showing shutdown message: {e}")
        
        # 2026 FIX: Log critical error but do NOT force exit
        # Let the application handle shutdown gracefully
        self.logger.critical(f"⚠️ Critical error occurred: {message}")
        self.logger.warning("System will attempt to continue - manual restart may be required")
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Callback function to handle the event
        """
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        self._subscriptions[event_type].append(handler)
        
        # If we have a Redis connection, subscribe to the channel
        if self.redis and event_type not in self._redis_subscriptions:
            def redis_handler(channel: str, message: str) -> None:
                try:
                    data = json.loads(message)
                    self._handle_event(event_type, data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to decode message: {e}")
            
            self.redis.subscribe(event_type, redis_handler)
            self._redis_subscriptions[event_type] = redis_handler
    
    def unsubscribe(self, event_type: str, handler: Optional[Callable] = None) -> None:
        """Unsubscribe from an event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Specific handler to remove, or None to remove all handlers
        """
        if event_type in self._subscriptions:
            if handler is None:
                del self._subscriptions[event_type]
            else:
                self._subscriptions[event_type] = [
                    h for h in self._subscriptions[event_type] if h != handler
                ]
        
        # Unsubscribe from Redis if no more handlers
        if event_type in self._redis_subscriptions and event_type not in self._subscriptions:
            if self.redis:
                self.redis.unsubscribe(event_type, self._redis_subscriptions[event_type])
            del self._redis_subscriptions[event_type]
    
    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish an event.
        
        Args:
            event_type: Type of event to publish
            data: Event data (must be JSON-serializable)
        """
        if not self.redis or not self._connected:
            self.logger.error(f"Cannot publish event {event_type}: Not connected to Redis")
            return
        
        try:
            message = json.dumps(data)
            self.redis.publish(event_type, message)
        except Exception as e:
            self.logger.error(f"Failed to publish event {event_type}: {e}")
    
    def _handle_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle an incoming event.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        if event_type in self._subscriptions:
            for handler in self._subscriptions[event_type]:
                try:
                    handler(data)
                except Exception as e:
                    self.logger.error(
                        f"Error in {event_type} handler {handler.__name__}: {e}"
                    )
    
    def cleanup(self) -> None:
        """Clean up resources."""
        # Unsubscribe from all events
        for event_type in list(self._subscriptions.keys()):
            self.unsubscribe(event_type)
        
        # Close Redis connection
        if self.redis:
            try:
                self.redis.shutdown()
            except Exception as e:
                self.logger.error(f"Error shutting down Redis: {e}")
        
        self._connected = False
        self.connection_state_changed.emit(False)


# Decorators for thread-safe event handling
def main_thread_only(method):
    """Decorator to ensure a method runs in the main thread."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if QCoreApplication.instance() and QThread.currentThread() != QCoreApplication.instance().thread():
            # Schedule the method to run in the main thread
            QMetaObject.invokeMethod(
                self,
                method.__name__,
                Qt.ConnectionType.QueuedConnection,
                QGenericReturnArgument(),
                *args,
                **kwargs
            )
        else:
            # Already in the main thread, call directly
            return method(self, *args, **kwargs)
    return wrapper


def handle_errors(default=None):
    """Decorator to handle errors in event handlers."""
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in {method.__name__}: {e}", exc_info=True)
                self.status_update.emit(
                    f"Error in {self.component_name}: {str(e)}", 
                    "error"
                )
                return default
        return wrapper
    return decorator
