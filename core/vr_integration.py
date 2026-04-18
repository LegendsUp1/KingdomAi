#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - VR Integration Component
Provides virtual reality integration for the Kingdom AI system.
"""

import asyncio
from core.base_component import BaseComponent
from core.event_bus import EventBus as AsyncEventBus
from core.vr_print_export import export_design_spec
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class VRSystem:
    """VR system integration."""
    
    def __init__(self, simulation_mode: bool = False, hardware_available: bool = False):
        """Initialize VR system.
        
        Args:
            simulation_mode: Run in simulation when no hardware detected
            hardware_available: Whether VR hardware is available
        """
        self.connected = False
        self.current_environment = "default"
        self.active_components = {}
        self.controller_tracking = {}
        self.display_settings = {}
        self.logger = logging.getLogger(__name__)
        self.simulation_mode = simulation_mode
        self.hardware_available = hardware_available
        
    async def connect(self, device_type: str) -> bool:
        """Connect to VR device."""
        try:
            self.logger.info(f"Connecting to VR device: {device_type}")
            # Simulation of connection
            await asyncio.sleep(1)
            self.connected = True
            self.logger.info(f"Connected to VR device: {device_type}")
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to VR device: {e}")
            return False

    async def ping(self) -> bool:
        """Basic responsiveness check."""
        try:
            # Simulate a quick operation
            await asyncio.sleep(0)
            return True
        except Exception:
            return False

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Return basic system metrics for VR health."""
        try:
            return {
                "connected": self.connected,
                "components": len(self.active_components),
                "simulation": self.simulation_mode,
                "env": self.current_environment,
                "timestamp": time.time(),
            }
        except Exception:
            return {"connected": False, "components": 0, "simulation": self.simulation_mode}
            
    async def disconnect(self) -> bool:
        """Disconnect from VR device."""
        try:
            self.logger.info("Disconnecting from VR device")
            # Simulation of disconnection
            self.connected = False
            self.logger.info("Disconnected from VR device")
            return True
        except Exception as e:
            self.logger.error(f"Error disconnecting from VR device: {e}")
            return False
    
    async def get_component_info(self, component_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a component."""
        if component_id in self.active_components:
            return self.active_components[component_id]
        return None
    
    async def change_environment(self, environment: str) -> bool:
        """Change the VR environment."""
        try:
            self.logger.info(f"Changing environment to: {environment}")
            self.current_environment = environment
            # Potentially load environment-specific components
            return True
        except Exception as e:
            self.logger.error(f"Error changing environment: {e}")
            return False
    
    async def reset_view(self) -> bool:
        """Reset the VR view to default position."""
        try:
            self.logger.info("Resetting VR view")
            return True
        except Exception as e:
            self.logger.error(f"Error resetting view: {e}")
            return False
    
    async def update_component(self, component_id: str, properties: Dict[str, Any]) -> bool:
        """Update a component's properties."""
        try:
            if component_id not in self.active_components:
                self.logger.warning(f"Component {component_id} not found for update")
                return False
                
            # Update properties
            if 'properties' not in self.active_components[component_id]:
                self.active_components[component_id]['properties'] = {}
                
            self.active_components[component_id]['properties'].update(properties)
            self.logger.debug(f"Updated component {component_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error updating component: {e}")
            return False
    
    async def create_component(self, component_id: str, component_type: str, properties: Dict[str, Any]) -> bool:
        """Create a new component."""
        try:
            if component_id in self.active_components:
                self.logger.warning(f"Component {component_id} already exists")
                return False
                
            position = properties.get('position', {'x': 0, 'y': 1.7, 'z': -2.0})
            
            self.active_components[component_id] = {
                'type': component_type,
                'properties': properties,
                'position': position,
                'visible': True,
                'created_at': time.time()
            }
            
            self.logger.info(f"Created component {component_id} of type {component_type}")
            return True
        except Exception as e:
            self.logger.error(f"Error creating component: {e}")
            return False
    
    async def toggle_component(self, component_id: str, properties: Dict[str, Any]) -> bool:
        """Toggle the visibility of a component."""
        try:
            if component_id not in self.active_components:
                self.logger.warning(f"Component {component_id} not found")
                return False
                
            current_visible = self.active_components[component_id].get('visible', True)
            self.active_components[component_id]['visible'] = not current_visible
            
            if properties:
                if 'properties' not in self.active_components[component_id]:
                    self.active_components[component_id]['properties'] = {}
                self.active_components[component_id]['properties'].update(properties)
            
            self.logger.debug(f"Toggled component {component_id}: visible={not current_visible}")
            return True
        except Exception as e:
            self.logger.error(f"Error toggling component: {e}")
            return False
    
    async def highlight_object(self, object_id: str, highlight: bool, intensity: float = 1.0) -> bool:
        """Highlight an object."""
        try:
            if object_id not in self.active_components:
                self.logger.warning(f"Object {object_id} not found")
                return False
                
            self.active_components[object_id]['highlighted'] = highlight
            self.active_components[object_id]['highlight_intensity'] = intensity
            return True
        except Exception as e:
            self.logger.error(f"Error highlighting object: {e}")
            return False
    
    async def delete_component(self, component_id: str) -> bool:
        """Delete a VR component."""
        try:
            if component_id not in self.active_components:
                self.logger.warning(f"Component {component_id} not found")
                return False
                
            self.logger.info(f"Deleting component {component_id}")
            del self.active_components[component_id]
            return True
        except Exception as e:
            self.logger.error(f"Error deleting component: {e}")
            return False
            
    async def set_object_state(self, object_id: str, state: str, hand: Optional[str] = None) -> bool:
        """Set the state of an object."""
        try:
            if object_id not in self.active_components:
                self.logger.warning(f"Object {object_id} not found")
                return False
                
            self.active_components[object_id]['state'] = state
            if hand:
                self.active_components[object_id]['hand'] = hand
            return True
        except Exception as e:
            self.logger.error(f"Error setting object state: {e}")
            return False
            
    async def show_tooltip(self, object_id: str, visible: bool) -> bool:
        """Show or hide a tooltip for an object."""
        try:
            if object_id not in self.active_components:
                self.logger.warning(f"Object {object_id} not found")
                return False
                
            self.active_components[object_id]['tooltip_visible'] = visible
            return True
        except Exception as e:
            self.logger.error(f"Error showing tooltip: {e}")
            return False
            
    async def show_notification(self, message: str, type_str: str, duration: float) -> bool:
        """Show a notification in VR."""
        try:
            # Simulate showing a notification
            self.logger.info(f"VR Notification: {message} ({type_str}, {duration}s)")
            return True
        except Exception as e:
            self.logger.error(f"Error showing notification: {e}")
            return False
            
    async def get_active_panel(self) -> Optional[str]:
        """Get the currently active panel."""
        try:
            # Find the active panel - in a real VR system this would query the actual state
            for panel_id, panel in self.active_components.items():
                if panel.get('type', '').endswith('_panel') and panel.get('visible', False):
                    if panel.get('focused', False):
                        return panel_id
                        
            # If no panel is focused, return the first visible panel
            for panel_id, panel in self.active_components.items():
                if panel.get('type', '').endswith('_panel') and panel.get('visible', False):
                    return panel_id
                    
            return None
        except Exception as e:
            self.logger.error(f"Error getting active panel: {e}")
            return None
            
    async def zoom_panel(self, panel_id: str, zoom_in: bool) -> bool:
        """Zoom in or out on a panel."""
        try:
            if panel_id not in self.active_components:
                self.logger.warning(f"Panel {panel_id} not found")
                return False
                
            # Simulate zooming by adjusting the panel's position
            current_position = self.active_components[panel_id].get('position', {'x': 0, 'y': 0, 'z': 0})
            if zoom_in:
                new_position = {'x': current_position['x'], 'y': current_position['y'], 'z': current_position['z'] + 0.1}
            else:
                new_position = {'x': current_position['x'], 'y': current_position['y'], 'z': current_position['z'] - 0.1}
                
            self.active_components[panel_id]['position'] = new_position
            return True
        except Exception as e:
            self.logger.error(f"Error zooming panel: {e}")
            return False
            
    async def spawn_object(self, object_id: str, position: Dict[str, float]) -> bool:
        """Spawn a VR object at the specified position."""
        try:
            self.logger.info(f"Spawning object {object_id} at position {position}")
            self.active_components[object_id] = {
                'position': position,
                'visible': True,
                'properties': {}
            }
            return True
        except Exception as e:
            self.logger.error(f"Error spawning object: {e}")
            return False
            
    async def show_object_details(self, object_id: str, details: Dict[str, Any]) -> bool:
        """Show details for an object."""
        try:
            if object_id not in self.active_components:
                self.logger.warning(f"Object {object_id} not found")
                return False
                
            # Create a detail panel near the object
            panel_id = f"{object_id}_details"
            object_position = self.active_components[object_id].get('position', {'x': 0, 'y': 1.7, 'z': -2.0})
            panel_position = {
                'x': object_position['x'] + 0.3,
                'y': object_position['y'],
                'z': object_position['z']
            }
            
            await self.create_component(
                panel_id, 
                "detail_panel", 
                {
                    'position': panel_position,
                    'details': details,
                    'linked_to': object_id,
                    'auto_hide': True,
                    'timeout': 5.0
                }
            )
            
            return True
        except Exception as e:
            self.logger.error(f"Error showing object details: {e}")
            return False

logger = logging.getLogger(__name__)

class VRIntegration(BaseComponent):
    """VR system integration for Kingdom AI."""
    
    def __init__(self, event_bus: Optional[AsyncEventBus] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize VR integration component.
        
        Args:
            event_bus: Event bus for communication
            config: Configuration for VR integration
        """
        super().__init__(name="vr_integration", event_bus=event_bus, config=config)
        self.config = config or {"hardware_check": True, "simulation_fallback": True}
        self.vr_system = None  # Will be initialized in initialize()
        self.visualized_components = set()
        self.active_controller = None
        self.controller_gestures = {}
        self.grabbed_components = {}  # Track components grabbed by each hand
        self.gesture_confidence_threshold = 0.75  # Minimum confidence to accept a gesture
        self.swipe_threshold = 0.5  # Minimum velocity for swipe gestures
        
        # Hardware status
        self.hardware_connected = False
        self.simulation_mode = False
        self.hardware_check_interval = 60  # seconds
        self.hardware_check_task = None
        
    async def initialize(self) -> bool:
        """Initialize VR integration component."""
        try:
            logger.info("Initializing VR Integration...")
            
            # Check VR hardware
            self.hardware_available = await self._check_vr_hardware()
            
            if self.hardware_available:
                logger.info("VR hardware detected")
                self.simulation_mode = False
            else:
                logger.warning("No VR hardware detected, using simulation mode")
                self.simulation_mode = True
                
            # Initialize VR system
            self.vr_system = VRSystem(
                simulation_mode=self.simulation_mode,
                hardware_available=self.hardware_available
            )
            
            # Initialize VR system
            success = await self.vr_system.connect("physical" if self.hardware_available else "simulation")
            if not success:
                logger.error("Failed to initialize VR system")
                return False
                
            # Set environment
            await self.vr_system.change_environment("default")
            
            # Setup event handlers
            if self.event_bus:
                await self._setup_event_handlers()
                
            # Start hardware monitoring
            if self.hardware_available:
                self.hardware_monitoring_task = asyncio.create_task(self._monitor_vr_hardware())
                
            # Publish initial status
            await self._publish_status_update()
            
            logger.info("VR Integration initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing VR integration: {e}")
            return False
            
    async def _setup_event_handlers(self) -> None:
        """Set up event handlers for VR integration."""
        if not self.event_bus:
            logger.warning("No event bus available for VR integration")
            return
            
        try:
            # Register for GUI events
            self.event_bus.subscribe_sync("gui.vr.reset_view", self._reset_view)
            self.event_bus.subscribe_sync("gui.vr.change_environment", self._change_environment)
            self.event_bus.subscribe_sync("gui.vr.toggle_menu", self._toggle_menu)
            self.event_bus.subscribe_sync("gui.vr.select_component", self._select_component)
            
            # Register for trading events
            self.event_bus.subscribe_sync("trading.order.created", self._visualize_order)
            self.event_bus.subscribe_sync("trading.order.updated", self._visualize_order)
            self.event_bus.subscribe_sync("trading.order.filled", self._visualize_order)
            self.event_bus.subscribe_sync("trading.order.cancelled", self._visualize_order)
            self.event_bus.subscribe_sync("trading.price.update", self._update_price_display)
            self.event_bus.subscribe_sync("trading.crypto.deposit", self._handle_crypto_deposit)
            self.event_bus.subscribe_sync("trading.crypto.trade", self._handle_crypto_trading)
            self.event_bus.subscribe_sync("trading.market.selected", self._select_market)
            
            # Register for mining events
            self.event_bus.subscribe_sync("mining.start", self._start_mining)
            self.event_bus.subscribe_sync("mining.stop", self._stop_mining)
            self.event_bus.subscribe_sync("mining.boost", self._boost_mining)
            self.event_bus.subscribe_sync("mining.status.update", self._visualize_mining)
            
            # Register for asset events
            self.event_bus.subscribe_sync("asset.selected", self._select_asset)
            
            # Register for AI events
            self.event_bus.subscribe_sync("ai.analysis.start", self._start_ai_analysis)
            self.event_bus.subscribe_sync("ai.analysis.stop", self._stop_ai_processing)
            self.event_bus.subscribe_sync("vr.brain.create_visual", self._brain_create_visual)
            self.event_bus.subscribe_sync("vr.brain.update_visual", self._brain_update_visual)
            self.event_bus.subscribe_sync("vr.brain.delete_visual", self._brain_delete_visual)
            self.event_bus.subscribe_sync("vr.brain.notification", self._brain_notification)
            self.event_bus.subscribe_sync("vr.brain.design_spec", self._brain_design_spec)
            self.event_bus.subscribe_sync("vr.media.generated", self._brain_media_generated)
            
            # Register for hardware events
            self.event_bus.subscribe_sync("system.hardware.check", self._check_vr_health)
            
            logger.info("VR integration event handlers setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up VR integration event handlers: {e}")
            
    async def _check_vr_hardware(self) -> bool:
        """Detect if VR hardware is available using real VR APIs."""
        try:
            # Try OpenVR (SteamVR) detection
            try:
                import openvr
                vr_system = openvr.init(openvr.VRApplication_Scene)
                if vr_system:
                    openvr.shutdown()
                    logger.info("VR hardware detected via OpenVR")
                    return True
            except ImportError:
                logger.debug("OpenVR not available")
            except Exception as e:
                logger.debug(f"OpenVR detection failed: {e}")
            
            # Try OpenXR detection
            try:
                import openxr
                instance = openxr.Instance(
                    application_info=openxr.ApplicationInfo("KingdomAI", 1),
                    enabled_extensions=[],
                )
                system_id = instance.system(openxr.FormFactor.HEAD_MOUNTED_DISPLAY)
                if system_id:
                    logger.info("VR hardware detected via OpenXR")
                    return True
            except ImportError:
                logger.debug("OpenXR not available")
            except Exception as e:
                logger.debug(f"OpenXR detection failed: {e}")
            
            # Check Windows Mixed Reality via registry/process check
            try:
                import subprocess
                import platform
                if platform.system() == "Windows":
                    # Check for WMR portal process
                    result = subprocess.run(
                        ['tasklist', '/FI', 'IMAGENAME eq MixedRealityPortal.exe'],
                        capture_output=True, timeout=2
                    )
                    if result.returncode == 0 and b'MixedRealityPortal.exe' in result.stdout:
                        logger.info("VR hardware detected via Windows Mixed Reality")
                        return True
            except Exception as e:
                logger.debug(f"WMR detection failed: {e}")
            
            # No VR hardware detected
            logger.info("No VR hardware detected - VR functionality unavailable")
            return False
        except Exception as e:
            logger.error(f"Error checking VR hardware: {e}")
            return False

    async def _monitor_vr_hardware(self) -> None:
        """Periodically monitor VR hardware status."""
        try:
            while True:
                # Check VR hardware connection status
                if self.hardware_available:
                    try:
                        # Try to verify hardware is still connected
                        hardware_still_available = await self._check_vr_hardware()
                        if not hardware_still_available and self.hardware_available:
                            logger.warning("VR hardware disconnected")
                            self.hardware_available = False
                            await self._publish_status_update()
                        elif hardware_still_available and not self.hardware_available:
                            logger.info("VR hardware reconnected")
                            self.hardware_available = True
                            await self._publish_status_update()
                    except Exception as e:
                        logger.error(f"Error checking VR hardware status: {e}")
                
                await asyncio.sleep(self.hardware_check_interval)
        except asyncio.CancelledError:
            logger.info("VR hardware monitoring task cancelled")
        except Exception as e:
            logger.error(f"Error in VR hardware monitor: {e}")

    async def _publish_status_update(self) -> None:
        """Publish a VR status update to the event bus."""
        try:
            status = {
                "status": "initialized" if self.vr_system and self.vr_system.connected else "not_connected",
                "simulation_mode": self.simulation_mode,
                "hardware_available": getattr(self, "hardware_available", False),
                "components": len(self.visualized_components),
                "timestamp": time.time()
            }
            if self.event_bus:
                self.event_bus.publish("vr.status", status)
        except Exception as e:
            logger.error(f"Failed to publish VR status: {e}")

    # ---- Event handler stubs to satisfy subscriptions ----
    async def _reset_view(self, event_type: str, event_data: Dict[str, Any]) -> None:
        try:
            if self.vr_system:
                await self.vr_system.reset_view()
        except Exception:
            pass

    async def _change_environment(self, event_type: str, event_data: Dict[str, Any]) -> None:
        try:
            env = (event_data or {}).get("environment", "default")
            if self.vr_system:
                await self.vr_system.change_environment(env)
        except Exception:
            pass

    async def _toggle_menu(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Toggle VR menu visibility."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot toggle menu")
                return
            
            menu_id = event_data.get("menu_id", "main_menu")
            visible = event_data.get("visible")
            
            # Toggle visibility if not explicitly set
            if visible is None:
                component = await self.vr_system.get_component_info(menu_id)
                visible = not component.get("visible", True) if component else True
            
            await self.vr_system.toggle_component(menu_id, {"visible": visible})
            logger.debug(f"Toggled VR menu {menu_id}: visible={visible}")
        except Exception as e:
            logger.error(f"Error toggling VR menu: {e}")

    async def _select_component(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Select a VR component."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot select component")
                return
            
            component_id = event_data.get("component_id")
            if not component_id:
                logger.warning("No component_id provided for selection")
                return
            
            # Highlight the selected component
            await self.vr_system.highlight_object(component_id, True, intensity=1.0)
            
            # Update active component tracking
            self.active_controller = component_id
            logger.debug(f"Selected VR component: {component_id}")
        except Exception as e:
            logger.error(f"Error selecting VR component: {e}")

    async def _visualize_order(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Visualize a trading order in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot visualize order")
                return
            
            order_id = event_data.get("order_id") or event_data.get("id")
            symbol = event_data.get("symbol", "UNKNOWN")
            side = event_data.get("side", "BUY")
            quantity = event_data.get("quantity", 0)
            price = event_data.get("price", 0)
            status = event_data.get("status", "pending")
            
            if not order_id:
                logger.warning("No order_id provided for visualization")
                return
            
            # Create or update order visualization component
            component_id = f"order_{order_id}"
            position = event_data.get("position", {"x": 0.0, "y": 1.5, "z": -2.0})
            
            properties = {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "status": status,
                "label": f"{side} {quantity} {symbol} @ {price}",
                "color": "#00FF00" if side == "BUY" else "#FF0000",
                "updated_at": time.time()
            }
            
            if component_id in self.visualized_components:
                await self.vr_system.update_component(component_id, properties)
            else:
                await self.vr_system.create_component(component_id, "order_panel", {
                    **properties,
                    "position": position
                })
                self.visualized_components.add(component_id)
            
            logger.debug(f"Visualized order {order_id} in VR")
        except Exception as e:
            logger.error(f"Error visualizing order in VR: {e}")

    async def _update_price_display(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Update price display panel in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot update price display")
                return
            
            symbol = event_data.get("symbol")
            price = event_data.get("price")
            change = event_data.get("change", 0)
            change_percent = event_data.get("change_percent", 0)
            
            if not symbol or price is None:
                logger.warning("Incomplete price data provided")
                return
            
            component_id = f"price_{symbol}"
            properties = {
                "symbol": symbol,
                "price": price,
                "change": change,
                "change_percent": change_percent,
                "label": f"{symbol}: ${price:.2f} ({change_percent:+.2f}%)",
                "color": "#00FF00" if change >= 0 else "#FF0000",
                "updated_at": time.time()
            }
            
            if component_id in self.visualized_components:
                await self.vr_system.update_component(component_id, properties)
            else:
                await self.vr_system.create_component(component_id, "price_panel", {
                    **properties,
                    "position": {"x": -0.5, "y": 1.8, "z": -2.0}
                })
                self.visualized_components.add(component_id)
            
            logger.debug(f"Updated price display for {symbol} in VR")
        except Exception as e:
            logger.error(f"Error updating price display in VR: {e}")

    async def _handle_crypto_deposit(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle crypto deposit visualization in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot visualize deposit")
                return
            
            amount = event_data.get("amount", 0)
            currency = event_data.get("currency", "BTC")
            tx_hash = event_data.get("tx_hash", "")
            
            # Show notification
            await self.vr_system.show_notification(
                f"Deposit: {amount} {currency}",
                "success",
                5.0
            )
            
            # Create deposit visualization component
            component_id = f"deposit_{int(time.time())}"
            await self.vr_system.create_component(component_id, "deposit_panel", {
                "amount": amount,
                "currency": currency,
                "tx_hash": tx_hash,
                "label": f"Deposit: {amount} {currency}",
                "position": {"x": 0.0, "y": 1.6, "z": -1.8}
            })
            self.visualized_components.add(component_id)
            
            logger.debug(f"Visualized deposit of {amount} {currency} in VR")
        except Exception as e:
            logger.error(f"Error visualizing deposit in VR: {e}")

    async def _handle_crypto_trading(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle crypto trading visualization in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot visualize trading")
                return
            
            # This is similar to order visualization but for completed trades
            trade_id = event_data.get("trade_id") or event_data.get("id")
            symbol = event_data.get("symbol", "UNKNOWN")
            side = event_data.get("side", "BUY")
            quantity = event_data.get("quantity", 0)
            price = event_data.get("price", 0)
            
            if not trade_id:
                logger.warning("No trade_id provided for visualization")
                return
            
            # Visualize as completed order
            await self._visualize_order(event_type, {
                **event_data,
                "order_id": trade_id,
                "status": "filled"
            })
            
            logger.debug(f"Visualized trade {trade_id} in VR")
        except Exception as e:
            logger.error(f"Error visualizing trade in VR: {e}")

    async def _select_market(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Select market in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot select market")
                return
            
            market = event_data.get("market") or event_data.get("symbol")
            if not market:
                logger.warning("No market provided for selection")
                return
            
            # Highlight market panel
            component_id = f"market_{market}"
            await self.vr_system.highlight_object(component_id, True, intensity=1.5)
            
            # Update active market
            if self.event_bus:
                self.event_bus.publish("vr.market.selected", {
                    "market": market,
                    "timestamp": time.time()
                })
            
            logger.debug(f"Selected market {market} in VR")
        except Exception as e:
            logger.error(f"Error selecting market in VR: {e}")

    async def _start_mining(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Start mining visualization in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot visualize mining")
                return
            
            miner_id = event_data.get("miner_id", "default")
            coin = event_data.get("coin", "BTC")
            hashrate = event_data.get("hashrate", 0)
            
            component_id = f"mining_{miner_id}_{int(time.time())}"
            position = event_data.get("position", {"x": 0.5, "y": 1.5, "z": -2.0})
            
            await self.vr_system.create_component(component_id, "mining_panel", {
                "miner_id": miner_id,
                "coin": coin,
                "hashrate": hashrate,
                "status": "active",
                "color": "#00FF00",
                "intensity": 0.8,
                "pulse_rate": 0.5,
                "label": f"Mining {coin}: {hashrate} H/s",
                "position": position
            })
            self.visualized_components.add(component_id)
            
            logger.debug(f"Started mining visualization for {miner_id} in VR")
        except Exception as e:
            logger.error(f"Error starting mining visualization in VR: {e}")

    async def _boost_mining(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Boost mining effect visualization in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot boost mining effect")
                return
            
            miner_id = event_data.get("miner_id", "default")
            boost_factor = event_data.get("boost_factor", 1.5)
            
            # Find mining components for this miner
            mining_ids = [cid for cid in self.visualized_components if cid.startswith(f"mining_{miner_id}_")]
            
            for mining_id in mining_ids:
                await self.vr_system.update_component(mining_id, {
                    "boost_factor": boost_factor,
                    "intensity": min(1.0, 0.8 * boost_factor),
                    "pulse_rate": min(1.0, 0.5 * boost_factor),
                    "color": "#FFFF00",  # Yellow for boosted
                    "updated_at": time.time()
                })
            
            # Create boost effect component
            effects_id = f"mining_effects_{miner_id}_{int(time.time())}"
            await self.vr_system.create_component(effects_id, "particle_effect", {
                "effect_type": "boost",
                "duration": 3.0,
                "position": {"x": 0.5, "y": 1.5, "z": -2.0}
            })
            self.visualized_components.add(effects_id)
            
            logger.debug(f"Boosted mining visualization for {miner_id} in VR")
        except Exception as e:
            logger.error(f"Error boosting mining visualization in VR: {e}")

    async def _select_asset(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Select an asset in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot select asset")
                return
            
            asset_id = event_data.get("asset_id") or event_data.get("symbol")
            if not asset_id:
                logger.warning("No asset_id provided for selection")
                return
            
            component_id = f"asset_{asset_id}"
            
            # Highlight the asset
            await self.vr_system.highlight_object(component_id, True, intensity=1.2)
            
            # Show asset details
            details = event_data.get("details", {})
            if details:
                await self.vr_system.show_object_details(component_id, details)
            
            logger.debug(f"Selected asset {asset_id} in VR")
        except Exception as e:
            logger.error(f"Error selecting asset in VR: {e}")

    async def _start_ai_analysis(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Start AI analysis visualization in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot visualize AI analysis")
                return
            
            analysis_id = event_data.get("analysis_id") or f"analysis_{int(time.time())}"
            analysis_type = event_data.get("type", "general")
            
            component_id = f"ai_analysis_{analysis_id}"
            position = event_data.get("position", {"x": -0.5, "y": 1.5, "z": -2.0})
            
            await self.vr_system.create_component(component_id, "ai_analysis_panel", {
                "analysis_id": analysis_id,
                "type": analysis_type,
                "status": "processing",
                "color": "#00FFFF",
                "intensity": 0.6,
                "pulse_rate": 0.3,
                "label": f"AI Analysis: {analysis_type}",
                "position": position
            })
            self.visualized_components.add(component_id)
            
            logger.debug(f"Started AI analysis visualization {analysis_id} in VR")
        except Exception as e:
            logger.error(f"Error starting AI analysis visualization in VR: {e}")

    async def _stop_ai_processing(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Stop AI processing visualization in VR."""
        try:
            if not self.vr_system or not self.hardware_available:
                logger.debug("VR hardware not available - cannot stop AI processing visualization")
                return
            
            analysis_id = event_data.get("analysis_id")
            if not analysis_id:
                # Find all AI analysis components
                analysis_ids = [cid for cid in self.visualized_components if cid.startswith("ai_analysis_")]
                for aid in analysis_ids:
                    await self.vr_system.update_component(aid, {
                        "status": "stopped",
                        "intensity": 0.1,
                        "pulse_rate": 0.0,
                        "updated_at": time.time()
                    })
            else:
                component_id = f"ai_analysis_{analysis_id}"
                if component_id in self.visualized_components:
                    await self.vr_system.update_component(component_id, {
                        "status": "stopped",
                        "intensity": 0.1,
                        "pulse_rate": 0.0,
                        "updated_at": time.time()
                    })
            
            logger.debug(f"Stopped AI processing visualization in VR")
        except Exception as e:
            logger.error(f"Error stopping AI processing visualization in VR: {e}")

    async def _brain_create_visual(self, event_type: str, event_data: Dict[str, Any]) -> None:
        try:
            if not self.vr_system:
                return
            component_id = event_data.get("component_id")
            if not component_id:
                component_id = f"brain_panel_{int(time.time() * 1000)}"
            component_type = event_data.get("component_type", "brain_panel")
            properties = event_data.get("properties", {})
            success = await self.vr_system.create_component(component_id, component_type, properties)
            if success:
                self.visualized_components.add(component_id)
        except Exception as e:
            logger.error(f"Error creating brain-driven VR visual: {e}")

    async def _brain_update_visual(self, event_type: str, event_data: Dict[str, Any]) -> None:
        try:
            if not self.vr_system:
                return
            component_id = event_data.get("component_id")
            if not component_id:
                return
            properties = event_data.get("properties", {})
            await self.vr_system.update_component(component_id, properties)
        except Exception as e:
            logger.error(f"Error updating brain-driven VR visual: {e}")

    async def _brain_delete_visual(self, event_type: str, event_data: Dict[str, Any]) -> None:
        try:
            if not self.vr_system:
                return
            component_id = event_data.get("component_id")
            if not component_id:
                return
            success = await self.vr_system.delete_component(component_id)
            if success and component_id in self.visualized_components:
                self.visualized_components.remove(component_id)
        except Exception as e:
            logger.error(f"Error deleting brain-driven VR visual: {e}")

    async def _brain_notification(self, event_type: str, event_data: Dict[str, Any]) -> None:
        try:
            if not self.vr_system:
                return
            message = event_data.get("message", "")
            if not message:
                return
            type_str = event_data.get("type", "info")
            duration = float(event_data.get("duration", 3.0))
            await self.vr_system.show_notification(message, type_str, duration)
        except Exception as e:
            logger.error(f"Error showing brain-driven VR notification: {e}")

    async def _brain_design_spec(self, event_type: str, event_data: Dict[str, Any]) -> None:
        try:
            if not self.vr_system:
                return
            design_spec = event_data.get("spec") or event_data.get("design") or {}
            if not isinstance(design_spec, dict) or not design_spec:
                return
            design_id = event_data.get("design_id") or design_spec.get("id")
            if not design_id:
                design_id = f"design_{int(time.time() * 1000)}"
            position = design_spec.get("position") or {"x": 0.0, "y": 1.7, "z": -2.0}
            await self.vr_system.spawn_object(design_id, position)
            properties = {
                "design_spec": design_spec,
                "label": design_spec.get("name", "Generated Design"),
                "updated_at": time.time()
            }
            await self.vr_system.update_component(design_id, properties)
            self.visualized_components.add(design_id)
            paths = export_design_spec(design_spec)
            if self.event_bus and isinstance(paths, dict):
                self.event_bus.publish("vr.print.exported", {
                    "design_id": design_id,
                    "paths": paths,
                    "timestamp": time.time()
                })
        except Exception as e:
            logger.error(f"Error handling brain design spec: {e}")

    async def _brain_media_generated(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Attach generated texture or video metadata to the relevant VR component.

        This does not perform any rendering itself; it only updates the
        component properties so the concrete VR runtime can bind textures or
        videos using the file paths/URLs.
        """
        try:
            if not self.vr_system:
                return
            design_id = event_data.get("component_id") or event_data.get("design_id")
            if not design_id:
                return
            media_type = event_data.get("media_type")
            media = event_data.get("media") or {}
            if not isinstance(media, dict) or not media_type:
                return

            props = {
                "media_type": media_type,
                "media": media,
                "media_updated_at": time.time(),
            }
            await self.vr_system.update_component(design_id, props)
        except Exception as e:
            logger.error(f"Error attaching brain media to VR component: {e}")

    async def _stop_mining(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle mining stop events in VR."""
        try:
            miner_id = event_data.get("miner_id", "")
            
            logger.info(f"Stopping mining for {miner_id}")
            
            # Update mining visualization to idle
            # Find the most recent mining component for this miner
            mining_ids = [cid for cid in self.visualized_components if cid.startswith(f"mining_{miner_id}_")]
            if mining_ids:
                mining_id = max(mining_ids, key=lambda x: int(x.split('_')[-1]))
                await self.vr_system.update_component(
                    mining_id, 
                    {
                        "status": "idle",
                        "color": "#A9A9A9",  # Gray
                        "intensity": 0.1,
                        "pulse_rate": 0.2,
                        "updated_at": time.time()
                    }
                )
                logger.debug(f"Updated mining component to idle: {mining_id}")
                
            # Remove mining effects
            effects_ids = [cid for cid in self.visualized_components if cid.startswith(f"mining_effects_{miner_id}_")]
            for effects_id in effects_ids:
                success = await self.vr_system.delete_component(effects_id)
                if success:
                    self.visualized_components.remove(effects_id)
                    logger.debug(f"Removed mining effects: {effects_id}")
                    
        except Exception as e:
            logger.error(f"Error stopping mining: {e}")
            
    async def _visualize_mining(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle mining visualization update events in VR."""
        try:
            if not self.vr_system:
                logger.warning("Cannot visualize mining: VR system not initialized")
                return
                
            miner_id = event_data.get("miner_id", "")
            hashrate = event_data.get("hashrate", 0)
            rewards = event_data.get("rewards", 0)
            efficiency = event_data.get("efficiency", 1.0)
            
            # Find the most recent mining component for this miner
            mining_ids = [cid for cid in self.visualized_components if cid.startswith(f"mining_{miner_id}_")]
            if mining_ids:
                mining_id = max(mining_ids, key=lambda x: int(x.split('_')[-1]))
                
                # Update the mining component
                await self.vr_system.update_component(
                    mining_id,
                    {
                        "hashrate": hashrate,
                        "rewards": rewards,
                        "efficiency": efficiency,
                        "text": f"Mining: {hashrate:.1f} H/s, Rewards: {rewards:.6f}",
                        "updated_at": time.time()
                    }
                )
                logger.debug(f"Updated mining visualization: {mining_id}")
            else:
                # No existing mining visualization, create one via _start_mining
                if self.event_bus:
                    self.event_bus.publish("mining.start", {
                        "miner_id": miner_id,
                        "hashrate": hashrate,
                        "coin": event_data.get("coin", "BTC")
                    })
                    
        except Exception as e:
            logger.error(f"Error updating mining visualization: {e}")
            
    async def _check_vr_health(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle VR health check requests."""
        try:
            logger.info("Performing VR system health check")
            
            # Check if VR system is initialized
            if not self.vr_system:
                logger.warning("VR system not initialized for health check")
                
                if self.event_bus:
                    self.event_bus.publish("vr.health.status", {
                        "status": "error",
                        "message": "VR system not initialized",
                        "timestamp": time.time()
                    })
                return
                
            # Check connection to VR hardware
            hardware_status = await self._check_vr_hardware()
            
            # Check VR system responsiveness
            system_responsive = await self.vr_system.ping()
            
            # Get system metrics
            metrics = await self.vr_system.get_system_metrics()
            
            # Compile health report
            health_report = {
                "status": "healthy" if (hardware_status and system_responsive) else "degraded",
                "hardware_connected": hardware_status,
                "system_responsive": system_responsive,
                "simulation_mode": self.simulation_mode,
                "metrics": metrics,
                "components_count": len(self.visualized_components),
                "timestamp": time.time()
            }
            
            # Log the health status
            if health_report["status"] == "healthy":
                logger.info(f"VR health check: System healthy, {len(self.visualized_components)} active components")
            else:
                logger.warning(f"VR health check: System degraded - HW:{hardware_status}, Responsive:{system_responsive}")
            
            # Publish health report
            if self.event_bus:
                self.event_bus.publish("vr.health.status", health_report)
                
        except Exception as e:
            logger.error(f"Error checking VR health: {e}")
            
            # Publish error report
            if self.event_bus:
                self.event_bus.publish("vr.health.status", {
                    "status": "error",
                    "message": str(e),
                    "timestamp": time.time()
                })
