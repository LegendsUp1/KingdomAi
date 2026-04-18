#!/usr/bin/env python3
"""Kingdom AI Tab Integration Module (DEPRECATED).

DEPRECATION WARNING: This module is deprecated and will be removed.
Please use the PyQt6-based implementation in gui.main_window_qt which handles tab integration directly.

This module ensures all tab frames are properly connected to the event bus
and can display real-time data from their respective components.
"""

import logging
import importlib
import inspect
import traceback
import asyncio
from typing import Dict, Any, Optional, List, Callable, Set, Union
from concurrent.futures import ThreadPoolExecutor

from gui.frames.thoth_frame import ThothFrame

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
                # Blockchain connectivity and status events
                event_bus_wrapper.subscribe("blockchain.status", self._create_data_handler(frame, "blockchain_status"))
                event_bus_wrapper.subscribe("blockchain.connection.status", self._create_data_handler(frame, "blockchain_connection_status"))
                event_bus_wrapper.subscribe("blockchain.error", self._create_data_handler(frame, "blockchain_error"))
            
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
            
        success = True
        try:
            # Get all frames from main window
            frames = []
            
            # Add all tab frames if they exist
            tab_frames = {
                "dashboard_tab": getattr(main_window, "dashboard_tab", None),
                "trading_tab": getattr(main_window, "trading_tab", None),
                "mining_tab": getattr(main_window, "mining_tab", None),
                "wallet_tab": getattr(main_window, "wallet_tab", None),
                "vr_tab": getattr(main_window, "vr_tab", None),
                "ai_tab": getattr(main_window, "ai_tab", None),
                "thoth_tab": getattr(main_window, "thoth_tab", None),
                "code_generator_tab": getattr(main_window, "code_generator_tab", None),
                "api_keys_tab": getattr(main_window, "api_keys_tab", None),
                "diagnostics_tab": getattr(main_window, "diagnostics_tab", None),
                "settings_tab": getattr(main_window, "settings_tab", None)
            }
            
            # Add each tab frame to the list
            for tab_name, tab_frame in tab_frames.items():
                if tab_frame is not None:
                    frames.append((tab_name, tab_frame))
            
            # Integrate each frame
            for frame_name, frame in frames:
                frame_success = self.integrate_frame(frame, frame_name)
                if not frame_success:
                    self.logger.warning(f"Failed to integrate {frame_name}")
                    success = False
            
            self.logger.info("Tab integration complete")
            return success
        except Exception as e:
            self.logger.error(f"Error integrating tabs: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _create_data_handler(self, frame, event_type):
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
                # Try to call the handler method directly
                handler_name = f"_handle_{event_type}"
                handler = getattr(frame, handler_name, None)
                
                if handler is not None and callable(handler):
                    # Check if the handler is a coroutine function or regular function
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event_data)
                    else:
                        # Use thread pool for regular functions instead of asyncio.to_thread
                        # which might not be available in all Python versions
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(self.thread_pool, handler, event_data)
                else:
                    # Try to call a generic update method
                    update_method = getattr(frame, "update_data", None)
                    if update_method is not None and callable(update_method):
                        if asyncio.iscoroutinefunction(update_method):
                            await update_method(event_type, event_data)
                        else:
                            # Use thread pool for regular functions
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                self.thread_pool, 
                                lambda: update_method(event_type, event_data)
                            )
                    else:
                        self.logger.warning(f"No handler for {event_type} in {frame.__class__.__name__}")
            except Exception as e:
                self.logger.error(f"Error handling {event_type} event: {e}")
                self.logger.error(traceback.format_exc())
        
        return handle_event
    
    def get_component_requirements(self, frame_name: str) -> List[str]:
        """Get the list of components required by a frame.
        
        Args:
            frame_name: The name of the frame
            
        Returns:
            List[str]: List of component names required by the frame
        """
        # Strip frame suffix if present
        frame_type = frame_name.lower().replace("_frame", "").replace("frame", "").strip()
        frame_type = frame_type.replace("_tab", "").replace("tab", "").strip()
        
        # Get components required by this frame type
        return self.component_mapping.get(frame_type, [])
    
    def connect_components(self, frame, components: Dict[str, Any]) -> bool:
        """Connect components to a frame.
        
        Args:
            frame: The frame instance
            components: Dictionary of components {name: component_instance}
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if frame is None:
            self.logger.warning("Cannot connect components to None frame")
            return False
        
        try:
            frame_name = frame.__class__.__name__
            required_components = self.get_component_requirements(frame_name)
            connected = True
            
            for component_name in required_components:
                component = components.get(component_name)
                if component is not None:
                    # Try to call the setter method
                    setter_name = f"set_{component_name}"
                    setter = getattr(frame, setter_name, None)
                    
                    if setter is not None and callable(setter):
                        try:
                            setter(component)
                            self.logger.info(f"Connected {component_name} to {frame_name}")
                        except Exception as e:
                            self.logger.error(f"Error connecting {component_name} to {frame_name}: {e}")
                            self.logger.error(traceback.format_exc())
                            connected = False
                    else:
                        # Try to set attribute directly
                        try:
                            setattr(frame, component_name, component)
                            self.logger.info(f"Set {component_name} attribute on {frame_name}")
                        except Exception as e:
                            self.logger.error(f"Error setting {component_name} attribute on {frame_name}: {e}")
                            self.logger.error(traceback.format_exc())
                            connected = False
            
            return connected
        except Exception as e:
            self.logger.error(f"Error connecting components to {frame.__class__.__name__}: {e}")
            self.logger.error(traceback.format_exc())
            return False


# Singleton implementation
class TabIntegratorSingleton:
    """Singleton manager for TabIntegrator"""
    _instance = None
    
    @classmethod
    def get_instance(cls, event_bus=None):
        """Get the singleton TabIntegrator instance.
        
        Args:
            event_bus: Event bus for the TabIntegrator
            
        Returns:
            TabIntegrator: The singleton TabIntegrator instance
        """
        if cls._instance is None and event_bus is not None:
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
