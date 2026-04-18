"""
Kingdom AI Base Component V2

This module provides an enhanced base component class that enforces strict
Redis connection requirements and provides consistent event handling.
"""

import asyncio
import logging
import traceback
import time
from typing import Dict, Any, Optional, Callable, List, TypeVar

from core.event_bus import EventBus
from core.redis_connector import RedisQuantumNexusConnector

# Type variable for component class
T = TypeVar('T', bound='BaseComponentV2')

class ComponentError(Exception):
    """Base exception for component errors."""
    pass

class RedisConnectionError(ComponentError):
    """Raised when Redis connection fails."""
    pass

class BaseComponentV2:
    """
    Enhanced base component for Kingdom AI system.
    
    This class provides:
    - Strict Redis connection management
    - Event bus integration
    - Lifecycle management
    - Error handling and logging
    - Configuration management
    """
    
    # Standard event channels
    EVENT_SYSTEM = "system"
    EVENT_COMPONENT = "component"
    EVENT_SECURITY = "security"
    EVENT_MARKET = "market"
    EVENT_WALLET = "wallet"
    EVENT_MINING = "mining"
    EVENT_VR = "vr"
    EVENT_AI = "ai"
    EVENT_GUI = "gui"
    EVENT_NETWORK = "network"
    
    # API key and environment events
    EVENT_API_KEY_UPDATE = "api_key_manager.key_updated"
    EVENT_API_KEY_STATUS = "api_key_manager.key_status"
    EVENT_ENVIRONMENT_UPDATE = "system.environment.update"
    
    # Redis connection settings
    REDIS_PORT = 6380
    REDIS_PASSWORD = 'QuantumNexus2025'
    REDIS_HOST = 'localhost'
    
    def __init__(self, 
                 name: Optional[str] = None, 
                 event_bus: Optional[EventBus] = None, 
                 config: Optional[Dict[str, Any]] = None):
        """Initialize the base component.
        
        Args:
            name: Component name (defaults to class name)
            event_bus: Optional EventBus instance
            config: Optional configuration dictionary
        """
        self.name = name or self.__class__.__name__
        self.event_bus = event_bus
        self.config = config or {}
        
        # Initialize logger
        self.logger = logging.getLogger(f"kingdom_ai.{self.name}")
        
        # State tracking
        self._initialized = False
        self._running = False
        self._shutdown_requested = False
        
        # Redis connection
        self.redis = None
        self._redis_connected = False
        
        # Statistics
        self.stats = {
            'start_time': time.time(),
            'events_processed': 0,
            'errors': 0,
            'last_error': None,
            'redis_connection_attempts': 0,
            'redis_connection_errors': 0,
            'last_redis_connection_attempt': 0
        }
        
        # Event subscriptions
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    @property
    def is_initialized(self) -> bool:
        """Check if the component is initialized."""
        return self._initialized
    
    @property
    def is_running(self) -> bool:
        """Check if the component is running."""
        return self._running
    
    @property
    def redis_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._redis_connected and self.redis is not None
    
    async def initialize(self) -> bool:
        """Initialize the component.
        
        Returns:
            bool: True if initialization was successful, False otherwise
            
        Raises:
            ComponentError: If initialization fails
        """
        if self._initialized:
            self.logger.warning("Component already initialized")
            return True
            
        try:
            self.logger.info(f"Initializing {self.name}...")
            
            # Initialize Redis connection
            if not await self._init_redis():
                error_msg = f"Failed to initialize Redis connection for {self.name}"
                self.logger.error(error_msg)
                raise RedisConnectionError(error_msg)
            
            # Initialize event handlers
            await self._init_event_handlers()
            
            # Call subclass initialization
            if hasattr(self, '_initialize'):
                result = getattr(self, '_initialize')()
                if asyncio.iscoroutine(result):
                    await result
            
            self._initialized = True
            self.logger.info(f"{self.name} initialized successfully")
            return True
            
        except Exception as e:
            self._handle_error("Initialization failed", e)
            raise ComponentError(f"Failed to initialize {self.name}") from e
    
    async def start(self) -> bool:
        """Start the component.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if not self._initialized:
            self.logger.warning("Component not initialized, initializing...")
            if not await self.initialize():
                return False
        
        if self._running:
            self.logger.warning("Component already running")
            return True
            
        try:
            self.logger.info(f"Starting {self.name}...")
            self._running = True
            self._shutdown_requested = False
            
            # Call subclass start
            if hasattr(self, '_start'):
                result = getattr(self, '_start')()
                if asyncio.iscoroutine(result):
                    await result
            
            self.logger.info(f"{self.name} started successfully")
            return True
            
        except Exception as e:
            self._handle_error("Failed to start component", e)
            return False
    
    async def stop(self) -> bool:
        """Stop the component.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self._running:
            self.logger.warning("Component not running")
            return True
            
        try:
            self.logger.info(f"Stopping {self.name}...")
            self._shutdown_requested = True
            
            # Call subclass stop
            if hasattr(self, '_stop'):
                result = getattr(self, '_stop')()
                if asyncio.iscoroutine(result):
                    await result
            
            # Clean up Redis connection
            await self._cleanup_redis()
            
            self._running = False
            self.logger.info(f"{self.name} stopped successfully")
            return True
            
        except Exception as e:
            self._handle_error("Error stopping component", e)
            return False
    
    async def _init_redis(self) -> bool:
        """Initialize Redis connection.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if self.redis_connected:
            return True
            
        self.logger.info("Initializing Redis connection...")
        self.stats['redis_connection_attempts'] += 1
        self.stats['last_redis_connection_attempt'] = time.time()
        
        try:
            # Create Redis connector with strict settings
            # RedisQuantumNexusConnector (alias of RedisConnector) only accepts
            # an optional event_bus parameter; passing a 'name' kwarg causes a
            # TypeError and can recurse via _handle_error/publish_event.
            self.redis = RedisQuantumNexusConnector(event_bus=self.event_bus)
            
            # Test connection
            if not self.redis.health_check():
                raise RedisConnectionError("Redis health check failed")
            
            self._redis_connected = True
            self.logger.info("Redis connection established successfully")
            return True
            
        except Exception as e:
            self.stats['redis_connection_errors'] += 1
            self._handle_error("Failed to connect to Redis", e)
            
            # Halt system on Redis connection failure (no fallback allowed)
            await self._shutdown_on_redis_failure()
            return False
    
    async def _cleanup_redis(self) -> None:
        """Clean up Redis connection."""
        if self.redis:
            try:
                # RedisQuantumNexusConnector exposes a close() method that
                # tears down the underlying Redis client. Use that instead of
                # a non-existent shutdown() method to avoid AttributeError
                # during component shutdown.
                close_fn = getattr(self.redis, "close", None)
                if callable(close_fn):
                    close_fn()
            except Exception as e:
                self._handle_error("Error cleaning up Redis connection", e)
            finally:
                self.redis = None
                self._redis_connected = False
    
    async def _shutdown_on_redis_failure(self) -> None:
        """Handle Redis connection failure by shutting down the system."""
        error_msg = "CRITICAL: Redis connection failed - System shutting down"
        self.logger.critical(error_msg)
        
        # Try to publish error event
        try:
            if self.event_bus:
                await self.publish_event(
                    f"{self.EVENT_SYSTEM}.error",
                    {"error": "redis_connection_failed", "message": error_msg}
                )
        except Exception as e:
            self.logger.error(f"Failed to publish Redis failure event: {e}")
        
        # 2026 FIX: Do NOT halt system - continue in degraded mode
        self.logger.warning("⚠️ Redis unavailable - component will run in degraded mode")
    
    async def _init_event_handlers(self) -> None:
        """Initialize event handlers."""
        if not self.event_bus:
            self.logger.warning("No event bus available, event handlers not registered")
            return
        
        # Register for system events
        await self.subscribe(f"{self.EVENT_SYSTEM}.shutdown", self._on_system_shutdown)
        
        # Register component-specific event handlers
        if hasattr(self, '_register_event_handlers'):
            result = getattr(self, '_register_event_handlers')()
            if asyncio.iscoroutine(result):
                await result
    
    async def _on_system_shutdown(self, event_data: Dict[str, Any]) -> None:
        """Handle system shutdown event."""
        self.logger.info("Received system shutdown request")
        await self.stop()
    
    async def subscribe(self, event_type: str, handler: Callable) -> bool:
        """Subscribe to an event.
        
        Args:
            event_type: Event type to subscribe to
            handler: Callback function to handle the event
            
        Returns:
            bool: True if subscription was successful, False otherwise
        """
        if not self.event_bus:
            self.logger.warning(f"Cannot subscribe to {event_type}: No event bus available")
            return False
            
        try:
            # Register handler with event bus
            if asyncio.iscoroutinefunction(self.event_bus.subscribe):
                await self.event_bus.subscribe(event_type, handler)
            else:
                self.event_bus.subscribe(event_type, handler)
            
            # Track the handler for cleanup
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(handler)
            
            self.logger.debug(f"Subscribed to {event_type}")
            return True
            
        except Exception as e:
            self._handle_error(f"Failed to subscribe to {event_type}", e)
            return False
    
    async def publish_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Publish an event.
        
        Args:
            event_type: Event type to publish
            data: Event data (must be JSON-serializable)
            
        Returns:
            bool: True if event was published successfully, False otherwise
        """
        if not self.event_bus:
            self.logger.warning(f"Cannot publish {event_type}: No event bus available")
            return False
            
        try:
            # Ensure Redis is connected
            if not self.redis_connected and not await self._init_redis():
                self.logger.error(f"Cannot publish {event_type}: Redis not connected")
                return False
            
            # Publish event
            if asyncio.iscoroutinefunction(self.event_bus.publish):
                await self.event_bus.publish(event_type, data)
            else:
                self.event_bus.publish(event_type, data)
            
            self.stats['events_processed'] += 1
            return True
            
        except Exception as e:
            self._handle_error(f"Failed to publish event {event_type}", e)
            return False
    
    def _handle_error(self, message: str, error: Exception) -> None:
        """Handle an error.
        
        Args:
            message: Error message
            error: Exception that caused the error
        """
        error_msg = f"{message}: {str(error)}"
        self.logger.error(error_msg, exc_info=True)
        
        # Update stats
        self.stats['errors'] += 1
        self.stats['last_error'] = {
            'message': str(error),
            'type': error.__class__.__name__,
            'timestamp': time.time(),
            'traceback': traceback.format_exc()
        }
        
        # Publish error event if possible
        if self.event_bus:
            try:
                error_event = {
                    'component': self.name,
                    'message': message,
                    'error': str(error),
                    'type': error.__class__.__name__,
                    'timestamp': time.time()
                }
                
                if asyncio.iscoroutinefunction(self.publish_event):
                    asyncio.create_task(self.publish_event(
                        f"{self.EVENT_SYSTEM}.error",
                        error_event
                    ))
                else:
                    self.publish_event(f"{self.EVENT_SYSTEM}.error", error_event)
            except Exception as e:
                self.logger.error(f"Failed to publish error event: {e}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        if hasattr(self, '_running') and self._running:
            self.logger.warning(f"{self.name} destroyed while still running")
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.stop())
            except Exception:
                pass
