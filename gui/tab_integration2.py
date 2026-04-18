#!/usr/bin/env python3
"""Kingdom AI Tab Integration Module.

This module ensures all tab frames are properly connected to the event bus
and can display real-time data from their respective components."""

import logging
import importlib
import inspect
import traceback
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable, Set, Union
from concurrent.futures import ThreadPoolExecutor

# Import EventBusWrapper for synchronous event bus operations
from core.event_bus_wrapper import get_event_bus_wrapper, sync_method

# Import event handler integration
from gui.event_handler_integration import integrate_frame_event_handlers

logger = logging.getLogger("kingdom.tab_integration")


class TabIntegrator:
    """Integrates all tab frames with their components and ensures real-time data display.
    
    This class manages the connection between tab frames and their corresponding
    components, ensuring that real-time data flows correctly between them.
    """
    
    def __init__(self, event_bus):
        """Initialize the TabIntegrator.
        
        Args:
            event_bus: The event bus for inter-component communication
        """
        self.event_bus = event_bus
        self.integrated_frames = set()
        # Preserving original component mappings to ensure compatibility
        self.component_mapping = {
            "dashboard": ["market_data_provider", "system_monitor"],
            "trading": ["trading_system", "market_api"],
            "mining": ["mining_system", "blockchain_connector"],
            "wallet": ["wallet_manager", "blockchain_connector"],
            "vr": ["vr_system", "vr_connector"],
            "ai": ["thoth_ai_assistant", "continuous_response_generator"],
            "thoth": ["thoth_ai_assistant", "voice_manager"],
            "code_generator": ["code_generator", "thoth_ai_assistant"],
            "api_keys": ["api_key_manager"],
            "diagnostics": ["system_monitor", "error_resolution_system"],
            "settings": ["config_manager"]
        }
        
        self.logger = logging.getLogger("kingdom.tab_integration")
        self.logger.info("TabIntegrator initialized")
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
    
    def integrate_frame(self, frame, frame_name: Optional[str] = None) -> bool:
        """Integrate a frame with real-time data handlers.
        
        Args:
            frame: The frame to integrate
            frame_name: Optional name for the frame
            
        Returns:
            bool: True if integration was successful, False otherwise
        """
        if frame is None:
            self.logger.warning("Cannot integrate None frame")
            return False
            
        try:
            # Get frame name from class name if not provided
            if frame_name is None:
                frame_name = frame.__class__.__name__
                
            # Skip if already integrated
            if frame_name in self.integrated_frames:
                self.logger.debug(f"Frame {frame_name} already integrated")
                return True
                
            self.logger.info(f"Integrating frame: {frame_name}")
            
            # Add event handlers
            success = self._integrate_frame(frame_name, frame)
                
            if success:
                self.integrated_frames.add(frame_name)
                    
            return success
        except Exception as e:
            self.logger.error(f"Error integrating frame {frame_name if 'frame_name' in locals() else 'unknown'}: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _integrate_frame(self, frame_name: str, frame) -> bool:
        """Integrate a specific frame with real-time data handlers.
        
        Args:
            frame_name: Name of the frame
            frame: The frame instance
            
        Returns:
            bool: True if integration was successful, False otherwise
        """
        if frame is None:
            self.logger.warning(f"Cannot integrate {frame_name} because frame is None")
            return False
            
        try:
            # Determine frame type
            frame_type = frame_name.lower().replace("_frame", "").replace("frame", "").strip()
            
            # Get EventBusWrapper for synchronous event bus operations
            event_bus_wrapper = get_event_bus_wrapper(self.event_bus)
            
            self.logger.info(f"Integrating {frame_name} with real-time data handlers")
            
            # For Trading frame
            if frame_type == "trading":
                event_bus_wrapper.subscribe("trading.update", self._create_data_handler(frame, "trading_update"))
                event_bus_wrapper.subscribe("market.update", self._create_data_handler(frame, "market_update"))
                event_bus_wrapper.subscribe("price.update", self._create_data_handler(frame, "price_update"))
                event_bus_wrapper.subscribe("market.historical_data", self._create_data_handler(frame, "historical_data"))
                event_bus_wrapper.subscribe("trading.order", self._create_data_handler(frame, "order_update"))
                
            # For Mining frame
            elif frame_type == "mining":
                event_bus_wrapper.subscribe("mining.update", self._create_data_handler(frame, "mining_update"))
                event_bus_wrapper.subscribe("mining.status", self._create_data_handler(frame, "mining_status"))
                event_bus_wrapper.subscribe("blockchain.update", self._create_data_handler(frame, "blockchain_update"))
                event_bus_wrapper.subscribe("mining.hashrate", self._create_data_handler(frame, "mining_hashrate"))
                event_bus_wrapper.subscribe("mining.devices", self._create_data_handler(frame, "mining_devices"))
                
            # For Wallet frame
            elif frame_type == "wallet":
                event_bus_wrapper.subscribe("wallet.balance", self._create_data_handler(frame, "wallet_balance"))
                event_bus_wrapper.subscribe("wallet.transactions", self._create_data_handler(frame, "wallet_transaction"))
                event_bus_wrapper.subscribe("wallet.update", self._create_data_handler(frame, "wallet_update"))
                
            # For VR frame
            elif frame_type == "vr":
                event_bus_wrapper.subscribe("vr.status", self._create_data_handler(frame, "vr_status"))
                event_bus_wrapper.subscribe("vr.environment", self._create_data_handler(frame, "vr_environment"))
                
            # For AI/Thoth frame
            elif frame_type == "ai" or frame_type == "thoth":
                event_bus_wrapper.subscribe("ai.status", self._create_data_handler(frame, "ai_status"))
                event_bus_wrapper.subscribe("ai.response", self._create_data_handler(frame, "ai_response"))
                event_bus_wrapper.subscribe("code.templates", self._create_data_handler(frame, "code_templates"))
                event_bus_wrapper.subscribe("code.generated", self._create_data_handler(frame, "code_generated"))
                
            # For Code Generator frame
            elif frame_type == "code" or frame_type == "code_generator":
                event_bus_wrapper.subscribe("code.templates", self._create_data_handler(frame, "code_templates"))
                event_bus_wrapper.subscribe("code.generated", self._create_data_handler(frame, "code_generated"))
                
            # For API Keys frame
            elif frame_type == "api" or frame_type == "api_keys":
                event_bus_wrapper.subscribe("api_keys.updated", self._create_data_handler(frame, "api_key_update"))
                event_bus_wrapper.subscribe("api_keys.status", self._create_data_handler(frame, "api_key_status"))
                
            # For Diagnostics frame
            elif frame_type == "diagnostics":
                event_bus_wrapper.subscribe("system.diagnostics", self._create_data_handler(frame, "system_diagnostics"))
                event_bus_wrapper.subscribe("system.metrics", self._create_data_handler(frame, "system_metrics"))
            
            # For Dashboard, also subscribe to component status events
            elif frame_type == "dashboard":
                event_bus_wrapper.subscribe("component.status", self._create_data_handler(frame, "component_status"))
                event_bus_wrapper.subscribe("system.metrics", self._create_data_handler(frame, "system_metrics"))
                # Add market data subscription for dashboard
                event_bus_wrapper.subscribe("market.update", self._create_data_handler(frame, "market_update"))
                event_bus_wrapper.subscribe("market.data", self._create_data_handler(frame, "market_data"))
            
            # Default subscriptions for all other frame types
            else:
                # Register frame-specific data events using the wrapper for synchronous subscription
                event_bus_wrapper.subscribe(f"{frame_type}.update", self._create_data_handler(frame, "update"))
                event_bus_wrapper.subscribe(f"{frame_type}.status", self._create_data_handler(frame, "status"))
            
            self.logger.info(f"Integrated {frame_name} with real-time data handlers")
            return True
            
        except Exception as e:
            self.logger.error(f"Error integrating {frame_name} event handlers: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def integrate_tabs(self, main_window) -> bool:
        """Integrate all tabs from the main window with their real-time data handlers.
        
        Args:
            main_window: The main window containing all tabs
            
        Returns:
            bool: True if all tabs were integrated successfully, False otherwise
        """
        if main_window is None:
            self.logger.warning("Cannot integrate tabs from None main_window")
            return False
            
        try:
            self.logger.info("Integrating all tabs from main window")
            
            # Get the tabs dictionary from the main window
            tabs = main_window.get_all_tabs()
            
            if not tabs:
                self.logger.warning("No tabs found in main_window")
                return False
                
            success = True
            for tab_name, tab_frame in tabs.items():
                # Integrate each tab frame
                success = success and self.integrate_frame(tab_frame, tab_name)
                
            self.logger.info(f"All tabs integrated successfully: {success}")
            return success
        except Exception as e:
            self.logger.error(f"Error integrating tabs: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _create_data_handler(self, frame, event_type: str) -> Callable[[Dict[str, Any]], None]:
        """Create a data handler function for a specific event type.
        
        Args:
            frame: The frame instance
            event_type: The type of event to handle
            
        Returns:
            function: An async function that handles the event
        """
        async def handle_event(event_data):
            """Handle the event and update the frame."""
            try:
                # Check if frame has a method for handling this event type
                handler_name = f"handle_{event_type}"
                if hasattr(frame, handler_name) and callable(getattr(frame, handler_name)):
                    # Call the handler on the frame in the GUI thread
                    handler = getattr(frame, handler_name)
                    
                    # Check if handler is an async function
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event_data)
                    else:
                        # Schedule non-async handler to run in thread pool
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(self.thread_pool, handler, event_data)
                    
                    self.logger.debug(f"Called {handler_name} on {frame.__class__.__name__}")
                else:
                    # If no specific handler, call the generic handler if it exists
                    if hasattr(frame, "handle_event") and callable(getattr(frame, "handle_event")):
                        # Call the generic handler with event type and data
                        generic_handler = getattr(frame, "handle_event")
                        
                        # Check if handler is an async function
                        if asyncio.iscoroutinefunction(generic_handler):
                            await generic_handler(event_type, event_data)
                        else:
                            # Schedule non-async handler to run in thread pool
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(self.thread_pool, generic_handler, event_type, event_data)
                        
                        self.logger.debug(f"Called handle_event with {event_type} on {frame.__class__.__name__}")
                    else:
                        self.logger.debug(f"No handler for {event_type} on {frame.__class__.__name__}")
            except Exception as e:
                self.logger.error(f"Error handling event {event_type} on {frame.__class__.__name__}: {e}")
                self.logger.error(traceback.format_exc())
        
        return handle_event
    
    def get_component_requirements(self, frame_name: str) -> List[str]:
        """Get the list of components required by a frame.
        
        Args:
            frame_name: The name of the frame
            
        Returns:
            List[str]: List of component names required by the frame
        """
        # Normalize frame name to get frame type
        frame_type = frame_name.lower().replace("_frame", "").replace("frame", "").strip()
        
        # Check if frame type is in component mapping
        if frame_type in self.component_mapping:
            return self.component_mapping[frame_type]
        else:
            # If not in mapping, return empty list
            return []
    
    def connect_components(self, frame, components: Dict[str, Any]) -> bool:
        """Connect components to a frame.
        
        Args:
            frame: The frame instance
            components: Dictionary of components {name: component_instance}
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if frame is None or not components:
            self.logger.warning("Cannot connect components: frame is None or components is empty")
            return False
            
        try:
            # Get frame name
            frame_name = frame.__class__.__name__
            
            # Get required components for this frame
            required_components = self.get_component_requirements(frame_name)
            
            # For each required component, connect to frame if available
            for component_name in required_components:
                if component_name in components:
                    component = components[component_name]
                    
                    # Set component as attribute on frame
                    if hasattr(frame, "set_component") and callable(getattr(frame, "set_component")):
                        # Call set_component method if it exists
                        frame.set_component(component_name, component)
                    else:
                        # Set component directly as attribute
                        setattr(frame, component_name, component)
                    
                    self.logger.info(f"Connected {component_name} to {frame_name}")
                else:
                    self.logger.warning(f"Component {component_name} not available for {frame_name}")
            
            return True
        except Exception as e:
            self.logger.error(f"Error connecting components to {frame.__class__.__name__ if frame else 'None'}: {e}")
            self.logger.error(traceback.format_exc())
            return False


# Singleton implementation
class TabIntegratorSingleton:
    """Singleton manager for TabIntegrator"""
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, event_bus=None):
        """Get the singleton TabIntegrator instance.
        
        Args:
            event_bus: Event bus for the TabIntegrator
            
        Returns:
            TabIntegrator: The singleton TabIntegrator instance
        """
        with cls._lock:
            if cls._instance is None:
                if event_bus is None:
                    raise ValueError("EventBus must be provided to initialize TabIntegrator")
                cls._instance = TabIntegrator(event_bus)
            return cls._instance


def get_tab_integrator(event_bus=None):
    """Get the singleton TabIntegrator instance.
    
    Args:
        event_bus: Event bus for the TabIntegrator
        
    Returns:
        TabIntegrator: The singleton TabIntegrator instance
    """
    return TabIntegratorSingleton.get_instance(event_bus)
