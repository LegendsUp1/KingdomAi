#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Base Component Module.

This module provides the base component class that all other 
components in the Kingdom AI system inherit from.
"""

import asyncio
import logging
import inspect
from typing import Dict, Any, Optional, TYPE_CHECKING, Callable, Union
import time
import traceback

# Use conditional import to break circular dependency
if TYPE_CHECKING:
    from core.event_bus import EventBus

logger = logging.getLogger(__name__)

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

class BaseComponent:
    """Base component class that all Kingdom AI components inherit from."""
    
    # Standard event channels for API key and environment updates
    EVENT_API_KEY_UPDATE = "api_key_manager.key_updated"
    EVENT_API_KEY_STATUS = "api_key_manager.key_status"
    EVENT_ENVIRONMENT_UPDATE = "system.environment.update"
    
    def __init__(self, name: str = None, event_bus: Optional["EventBus"] = None, config: Any = None):
        """Initialize base component.
        
        Args:
            name: Component name for logging and identification
            event_bus: EventBus instance for event-driven communication
            config: Configuration dictionary or ConfigManager instance
        """
        self.name = name or self.__class__.__name__
        self.event_bus = event_bus
        self.config = config if config is not None else {}
        self._initialized = False
        # Track running state explicitly so start/stop and status handlers work
        self.is_running = False
        # Track whether this component has already wired its event subscriptions
        self._subscribed_to_events = False
        # Internal map of event_channel -> handler for unsubscribe/cleanup
        self._event_handlers: Dict[str, Callable] = {}

        self.logger = logging.getLogger(f"KingdomAI.{self.name}")
        
        # Make sure logger is properly initialized
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        # Stats for monitoring
        self.stats = {
            "start_time": time.time(),
            "event_count": 0,
            "error_count": 0,
            "last_event_time": None
        }
    
    @property
    def initialized(self) -> bool:
        """Check if the component is initialized."""
        return self._initialized
    
    def subscribe_sync(self, event_type: str, callback: Callable) -> bool:
        """Subscribe to an event with a synchronous callback.
        
        Args:
            event_type: Event type to subscribe to
            callback: Callback function
            
        Returns:
            bool: Success status
        """
        if self.event_bus is None:
            self.logger.warning(f"Cannot subscribe to {event_type}: No event bus available")
            return False
            
        # Make sure the event bus has the sync method
        if hasattr(self.event_bus, 'subscribe_sync'):
            self.event_bus.subscribe_sync(event_type, callback)
            self.logger.debug(f"Subscribed to {event_type} with sync callback {callback.__name__}")
            return True
        elif hasattr(self.event_bus, 'subscribe'):
            # Fallback to regular subscribe if subscribe_sync doesn't exist
            if asyncio.iscoroutinefunction(self.event_bus.subscribe):
                # Create an asyncio task for the subscription
                self.event_bus.subscribe(event_type, callback)
            else:
                self.event_bus.subscribe(event_type, callback)
            self.logger.debug(f"Subscribed to {event_type} with sync callback {callback.__name__} (fallback)")
            return True
        else:
            self.logger.warning(f"Cannot subscribe to {event_type}: Event bus doesn't support subscribe methods")
            return False
    
    def subscribe_async(self, event_type: str, callback: Callable) -> bool:
        """Subscribe to an event with an asynchronous callback.
        
        Args:
            event_type: Event type to subscribe to
            callback: Async callback function
            
        Returns:
            bool: Success status
        """
        if self.event_bus is None:
            self.logger.warning(f"Cannot subscribe to {event_type}: No event bus available")
            return False
            
        # Make sure the event bus has the async method
        if hasattr(self.event_bus, 'subscribe_async'):
            self.event_bus.subscribe_async(event_type, callback)
            self.logger.debug(f"Subscribed to {event_type} with async callback {callback.__name__}")
            return True
        elif hasattr(self.event_bus, 'subscribe'):
            # Fallback to regular subscribe if subscribe_async doesn't exist
            if asyncio.iscoroutinefunction(self.event_bus.subscribe):
                # Create an asyncio task for the subscription
                self.event_bus.subscribe(event_type, callback)
            else:
                self.event_bus.subscribe(event_type, callback)
            self.logger.debug(f"Subscribed to {event_type} with async callback {callback.__name__} (fallback)")
            return True
        else:
            self.logger.warning(f"Cannot subscribe to {event_type}: Event bus doesn't support subscribe methods")
            return False
            
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize the component.
        
        Args:
            event_bus: Optional EventBus instance to use for initialization
            config: Optional configuration to use for initialization
            
        Returns:
            bool: Success status
        """
        if self._initialized:
            self.logger.warning(f"{self.name} already initialized")
            return True
        
        # Set event_bus and config if provided
        if event_bus is not None:
            self.event_bus = event_bus
        if config is not None:
            self.config = config
            
        try:
            # Basic initialization logic
            self.logger.info(f"Initializing {self.name}...")
            
            # Set up event subscriptions if component implements the method
            if hasattr(self, 'subscribe_to_events') and callable(getattr(self, 'subscribe_to_events')):
                if asyncio.iscoroutinefunction(self.subscribe_to_events):
                    await self.subscribe_to_events()
                    self.logger.debug(f"Async event subscriptions set up for {self.name}")
                else:
                    self.subscribe_to_events()
                    self.logger.debug(f"Sync event subscriptions set up for {self.name}")
            
            self._initialized = True
            self.logger.info(f"{self.name} initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing {self.name}: {e}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def _register_with_event_bus_sync(self):
        """Register component with event bus synchronously.
        
        This is a fallback method for components that don't support async initialization.
        """
        if self.event_bus:
            logger.info(f"Registering {self.name} with event bus (sync)")
            try:
                # Use the synchronous connect method to avoid coroutine issues
                self.event_bus.connect_component_sync(self)
                
                # Subscribe to API key and environment updates if it's not the VR system
                # VR doesn't need API keys but does need environment data
                if self.name != "VRSystem":
                    self.event_bus.subscribe_sync(self.EVENT_API_KEY_UPDATE, self._handle_api_key_update)
                    self.event_bus.subscribe_sync(self.EVENT_API_KEY_STATUS, self._handle_api_key_status)
                
                # All components need environment data
                self.event_bus.subscribe_sync(self.EVENT_ENVIRONMENT_UPDATE, self._handle_environment_update)
                
                return True
            except Exception as e:
                logger.error(f"Failed to register {self.name} with event bus: {e}")
                return False
        return False
    
    async def register_with_event_bus(self):
        """Register component with event bus asynchronously.
        
        This is the preferred method for registering with the event bus.
        """
        if not self.event_bus:
            logger.warning(f"{self.name}: No event bus available for registration")
            return False
            
        if self._subscribed_to_events:
            logger.debug(f"{self.name}: Already registered with event bus")
            return True
            
        logger.info(f"Registering {self.name} with event bus (async)")
        try:
            # Use the async connect method
            result = await self.event_bus.connect_component(self)
            
            if result:
                # Subscribe to API key and environment updates if it's not the VR system
                # VR doesn't need API keys but does need environment data
                if self.name != "VRSystem":
                    await self.event_bus.subscribe(self.EVENT_API_KEY_UPDATE, self._handle_api_key_update)
                    await self.event_bus.subscribe(self.EVENT_API_KEY_STATUS, self._handle_api_key_status)
                
                # All components need environment data
                await self.event_bus.subscribe(self.EVENT_ENVIRONMENT_UPDATE, self._handle_environment_update)
                
                self._subscribed_to_events = True
                logger.info(f"{self.name} successfully registered with event bus")
                
            return result
        except Exception as e:
            logger.error(f"Failed to register {self.name} with event bus: {e}")
            return False
    
    async def _handle_system_status(self, event_data: Dict[str, Any]) -> None:
        """Handle system status events.
        
        Args:
            event_data: System status data
        """
        if event_data.get("status") == "shutting_down":
            await self.stop()
    
    async def _handle_system_shutdown(self, event_data: Dict[str, Any]) -> None:
        """Handle system shutdown events.
        
        Args:
            event_data: Shutdown event data
        """
        await self.cleanup()
    
    async def _handle_component_status(self, event_data: Dict[str, Any]) -> None:
        """Handle status requests for this component.
        
        Args:
            event_data: Status request data
        """
        status = {
            "component": self.name,
            "initialized": self.initialized,
            "running": self.is_running,
            "timestamp": time.time()
        }
        
        # Publish status back to the event bus
        if self.event_bus:
            if hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync(f"{EVENT_COMPONENT}.{self.name.lower()}.status.response", status)
            else:
                await self.event_bus.publish(f"{EVENT_COMPONENT}.{self.name.lower()}.status.response", status)
    
    async def _handle_component_command(self, event_data: Dict[str, Any]) -> None:
        """Handle commands sent to this component.
        
        Args:
            event_data: Command data
        """
        command = event_data.get("command")
        if not command:
            return
            
        if command == "start" and not self.is_running:
            await self.start()
        elif command == "stop" and self.is_running:
            await self.stop()
        elif command == "restart":
            if self.is_running:
                await self.stop()
            await self.start()
            
    async def subscribe_to_event(self, event_channel: str, handler: Callable) -> bool:
        """Subscribe to an event channel with proper async handling.
        
        Args:
            event_channel: Event channel to subscribe to
            handler: Event handler function
            
        Returns:
            bool: True if subscription was successful
        """
        if not self.event_bus:
            logger.warning(f"Cannot subscribe {self.name} to {event_channel}: No event bus provided")
            return False
            
        try:
            if asyncio.iscoroutinefunction(self.event_bus.subscribe):
                await self.event_bus.subscribe(event_channel, handler)
            else:
                self.event_bus.subscribe(event_channel, handler)
            self._event_handlers[event_channel] = handler
            logger.debug(f"{self.name} subscribed to {event_channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe {self.name} to {event_channel}: {e}")
            return False
            
    def subscribe_to_event_sync(self, event_channel: str, handler: Callable) -> bool:
        """Subscribe to an event channel synchronously.
        
        Args:
            event_channel: Event channel to subscribe to
            handler: Event handler function
            
        Returns:
            bool: True if subscription was successful
        """
        if not self.event_bus:
            logger.warning(f"Cannot subscribe {self.name} to {event_channel}: No event bus provided")
            return False
            
        try:
            if hasattr(self.event_bus, 'subscribe_sync'):
                self.event_bus.subscribe_sync(event_channel, handler)
            else:
                self.event_bus.subscribe(event_channel, handler)
            self._event_handlers[event_channel] = handler
            logger.debug(f"{self.name} subscribed to {event_channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe {self.name} to {event_channel}: {e}")
            return False
            
    async def unsubscribe_from_event(self, event_channel: str) -> bool:
        """Unsubscribe from an event channel asynchronously.
        
        Args:
            event_channel: Event channel to unsubscribe from
            
        Returns:
            bool: True if unsubscription was successful
        """
        if not self.event_bus:
            return False
            
        try:
            handler = self._event_handlers.get(event_channel)
            if handler:
                if asyncio.iscoroutinefunction(self.event_bus.unsubscribe):
                    await self.event_bus.unsubscribe(event_channel, handler)
                else:
                    self.event_bus.unsubscribe(event_channel, handler)
                del self._event_handlers[event_channel]
                logger.debug(f"{self.name} unsubscribed from {event_channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe {self.name} from {event_channel}: {e}")
            return False
            
    def unsubscribe_from_event_sync(self, event_channel: str) -> bool:
        """Unsubscribe from an event channel synchronously.
        
        Args:
            event_channel: Event channel to unsubscribe from
            
        Returns:
            bool: True if unsubscription was successful
        """
        if not self.event_bus:
            return False
            
        try:
            handler = self._event_handlers.get(event_channel)
            if handler:
                if asyncio.iscoroutinefunction(self.event_bus.unsubscribe):
                    # Create a new event loop if necessary
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    # Run async function in sync context
                    loop.run_until_complete(self.event_bus.unsubscribe(event_channel, handler))
                else:
                    self.event_bus.unsubscribe(event_channel, handler)
                del self._event_handlers[event_channel]
                logger.debug(f"{self.name} unsubscribed from {event_channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe {self.name} from {event_channel}: {e}")
            return False
            
    async def publish_event(self, event_channel: str, event_data: Dict[str, Any]) -> bool:
        """Publish an event to the event bus asynchronously.
        
        Args:
            event_channel: Event channel to publish to
            event_data: Event data to publish
            
        Returns:
            bool: True if publish was successful
        """
        if not self.event_bus:
            logger.warning(f"Cannot publish event to {event_channel}: No event bus provided")
            return False
            
        try:
            # Add standard metadata to event data
            if isinstance(event_data, dict):
                if "component" not in event_data:
                    event_data["component"] = self.name
                if "timestamp" not in event_data:
                    event_data["timestamp"] = time.time()
                    
            if hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync(event_channel, event_data)
            else:
                return await self.event_bus.publish(event_channel, event_data)
            return True
        except Exception as e:
            logger.error(f"Failed to publish event to {event_channel}: {e}")
            return False
    
    def set_config(self, config: Any) -> None:
        """Set or update configuration for this component.
        
        Args:
            config: Configuration dictionary or ConfigManager instance
        """
        try:
            if not config:
                logger.warning(f"Empty config provided for {self.name}")
                return
                
            # Merge new config with existing config
            if isinstance(config, dict):
                self.config.update(config)
            else:
                self.config = config
            logger.debug(f"Config updated for {self.name}")
        except Exception as e:
            logger.error(f"Failed to set config for {self.name}: {e}")
    
    def set_wallet(self, wallet) -> None:
        """Set wallet for this component.
        
        Args:
            wallet: Wallet instance
        """
        try:
            self._wallet = wallet
            logger.debug(f"Wallet set for {self.name}")
        except Exception as e:
            logger.error(f"Failed to set wallet for {self.name}: {e}")
    
    def set_market_api(self, market_api) -> None:
        """Set market API for this component.
        
        Args:
            market_api: MarketAPI instance
        """
        try:
            self._market_api = market_api
            logger.debug(f"Market API set for {self.name}")
        except Exception as e:
            logger.error(f"Failed to set market API for {self.name}: {e}")
    
    def set_blockchain(self, blockchain) -> None:
        """Set blockchain connector for this component.
        
        Args:
            blockchain: BlockchainConnector instance
        """
        try:
            self._blockchain = blockchain
            logger.debug(f"Blockchain connector set for {self.name}")
        except Exception as e:
            logger.error(f"Failed to set blockchain connector for {self.name}: {e}")
    
    def set_session_manager(self, session_manager) -> None:
        """Set session manager for this component.
        
        Args:
            session_manager: SessionManager instance
        """
        try:
            self._session_manager = session_manager
            logger.debug(f"Session manager set for {self.name}")
        except Exception as e:
            logger.error(f"Failed to set session manager for {self.name}: {e}")
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with a default fallback.
        
        Args:
            key: Configuration key
            default: Default value if key is not found
            
        Returns:
            Any: Configuration value or default
        """
        if isinstance(self.config, dict):
            return self.config.get(key, default)
        else:
            return self.config.get_value(key, default)
        
    async def start(self) -> bool:
        """Start the component.
        
        Returns:
            bool: True if the component started successfully
        """
        # SOTA 2026 FIX: Auto-initialize if not already initialized (prevents race conditions)
        if not self.initialized:
            logger.debug(f"{self.name} auto-initializing before start")
            try:
                await self.initialize()
            except Exception as e:
                logger.debug(f"{self.name} auto-init failed: {e}")
                # Continue anyway - component may still work
            
        try:
            self.is_running = True
            logger.info(f"{self.name} started")
            return True
        except Exception as e:
            logger.error(f"Failed to start {self.name}: {e}")
            return False
            
    async def stop(self) -> bool:
        """Stop the component.
        
        Returns:
            bool: True if the component stopped successfully
        """
        if not self.is_running:
            logger.info(f"{self.name} is not running")
            return True
            
        try:
            self.is_running = False
            logger.info(f"{self.name} stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop {self.name}: {e}")
            return False
            
    async def cleanup(self) -> bool:
        """Clean up resources asynchronously.
        
        Returns:
            bool: True if cleanup was successful
        """
        try:
            if self.is_running:
                await self.stop()
                
            # Unsubscribe from all events
            if self.event_bus:
                for event_channel, handler in list(self._event_handlers.items()):
                    await self.unsubscribe_from_event(event_channel)
                
                # Unregister system handlers
                if asyncio.iscoroutinefunction(self.event_bus.unsubscribe):
                    await self.event_bus.unsubscribe(f"{EVENT_SYSTEM}.status", self._handle_system_status)
                    await self.event_bus.unsubscribe(f"{EVENT_SYSTEM}.shutdown", self._handle_system_shutdown)
                else:
                    self.event_bus.unsubscribe(f"{EVENT_SYSTEM}.status", self._handle_system_status)
                    self.event_bus.unsubscribe(f"{EVENT_SYSTEM}.shutdown", self._handle_system_shutdown)
                
                # Unregister component handlers
                component_channel = f"{EVENT_COMPONENT}.{self.name.lower()}"
                if asyncio.iscoroutinefunction(self.event_bus.unsubscribe):
                    await self.event_bus.unsubscribe(f"{component_channel}.status", self._handle_component_status)
                    await self.event_bus.unsubscribe(f"{component_channel}.command", self._handle_component_command)
                else:
                    self.event_bus.unsubscribe(f"{component_channel}.status", self._handle_component_status)
                    self.event_bus.unsubscribe(f"{component_channel}.command", self._handle_component_command)
                
                # Notify the system registry
                if hasattr(self.event_bus, 'publish_sync'):
                    self.event_bus.publish_sync(f"{EVENT_SYSTEM}.registry.remove", {
                        "component": self.name,
                        "status": "unregistered",
                        "timestamp": time.time()
                    })
                else:
                    await self.event_bus.publish(f"{EVENT_SYSTEM}.registry.remove", {
                        "component": self.name,
                        "status": "unregistered",
                        "timestamp": time.time()
                    })
            
            logger.info(f"{self.name} cleaned up")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup {self.name}: {e}")
            return False
    
    def cleanup_sync(self) -> bool:
        """Clean up resources synchronously.
        
        Returns:
            bool: True if cleanup was successful
        """
        try:
            if self.is_running:
                # Create a new event loop if necessary
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(self.stop())
                
            # Unsubscribe from all events
            if self.event_bus:
                for event_channel, handler in list(self._event_handlers.items()):
                    self.unsubscribe_from_event_sync(event_channel)
                
                # Unregister system handlers
                if asyncio.iscoroutinefunction(self.event_bus.unsubscribe):
                    # Create a new event loop if necessary
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Run async function in sync context
                    loop.run_until_complete(self.event_bus.unsubscribe(f"{EVENT_SYSTEM}.status", self._handle_system_status))
                    loop.run_until_complete(self.event_bus.unsubscribe(f"{EVENT_SYSTEM}.shutdown", self._handle_system_shutdown))
                else:
                    self.event_bus.unsubscribe(f"{EVENT_SYSTEM}.status", self._handle_system_status)
                    self.event_bus.unsubscribe(f"{EVENT_SYSTEM}.shutdown", self._handle_system_shutdown)
                
                # Unregister component handlers
                component_channel = f"{EVENT_COMPONENT}.{self.name.lower()}"
                if asyncio.iscoroutinefunction(self.event_bus.unsubscribe):
                    loop.run_until_complete(self.event_bus.unsubscribe(f"{component_channel}.status", self._handle_component_status))
                    loop.run_until_complete(self.event_bus.unsubscribe(f"{component_channel}.command", self._handle_component_command))
                else:
                    self.event_bus.unsubscribe(f"{component_channel}.status", self._handle_component_status)
                    self.event_bus.unsubscribe(f"{component_channel}.command", self._handle_component_command)
                
                # Notify the system registry
                if hasattr(self.event_bus, 'publish_sync'):
                    self.event_bus.publish_sync(f"{EVENT_SYSTEM}.registry.remove", {
                        "component": self.name,
                        "status": "unregistered",
                        "timestamp": time.time()
                    })
                else:
                    loop.run_until_complete(self.event_bus.publish(f"{EVENT_SYSTEM}.registry.remove", {
                        "component": self.name,
                        "status": "unregistered",
                        "timestamp": time.time()
                    }))
            
            logger.info(f"{self.name} cleaned up")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup {self.name}: {e}")
            return False
    
    def initialize_sync(self):
        """Synchronous version of initialize"""
        return True

    @staticmethod
    def safe_call(func: Union[Callable, None], *args, **kwargs) -> Any:
        """Safely call a function if it exists.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Any: Function result or None if function doesn't exist
        """
        if func is None:
            return None
            
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error calling function {func.__name__}: {e}")
            return None
    
    async def safe_async_call(self, func: Union[Callable, None], *args, **kwargs) -> Any:
        """Safely call an async function if it exists.
        
        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Any: Function result or None if function doesn't exist
        """
        if func is None:
            return None
            
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error calling function {func.__name__}: {e}")
            return None
    
    async def _handle_api_key_update(self, event_data: Dict[str, Any]) -> None:
        """Handle API key update events.
        
        This method will be overridden by components that need to use specific API keys.
        The base implementation logs the event and updates component state if needed.
        
        Args:
            event_data: API key update event data
        """
        category = event_data.get("category")
        service = event_data.get("service")
        status = event_data.get("status")
        
        logger.debug(f"{self.name} received API key update for {category}.{service} (status: {status})")
        
        # Components should override this method to handle specific API key updates
        # For example, MarketAPI would update its exchange clients based on the updated keys
        
    async def _handle_api_key_status(self, event_data: Dict[str, Any]) -> None:
        """Handle API key status events.
        
        This method will be overridden by components that need to know about API key status changes.
        The base implementation just logs the event.
        
        Args:
            event_data: API key status event data
        """
        category = event_data.get("category")
        service = event_data.get("service")
        status = event_data.get("status")
        
        logger.debug(f"{self.name} received API key status update for {category}.{service}: {status}")
        
        # Components should override this method to handle specific status updates
        # For example, MarketAPI would enable/disable certain features based on key status
    
    async def _handle_environment_update(self, event_data: Dict[str, Any]) -> None:
        """Handle environment update events.
        
        This method will be overridden by components that need environment data.
        The base implementation just logs the event.
        
        Args:
            event_data: Environment update event data
        """
        environment_name = event_data.get("name")
        environment_type = event_data.get("type")
        
        logger.debug(f"{self.name} received environment update for {environment_name} ({environment_type})")
        
        # Components should override this method to handle specific environment updates
        # For example, TradingSystem might load different strategies based on environment
