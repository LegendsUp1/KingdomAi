#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
VR System for Kingdom AI
Handles VR device management, rendering, and integration
"""

import os
import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import sys
import base64

import websockets

try:
    # CRITICAL: NumPy _ARRAY_API patch BEFORE numpy/cv2 import (NumPy 2.x compatibility)
    # sitecustomize.py import hook should have already patched numpy
    import numpy as np  # type: ignore
    
    # CRITICAL: Ensure _ARRAY_API exists (import hook should have set it)
    if not hasattr(np, '_ARRAY_API'):
        import types
        ns = types.SimpleNamespace()
        ns.ARRAY_API_STRICT = False
        np._ARRAY_API = ns
    
    # CRITICAL: Patch numpy._core.multiarray (cv2's C extension checks this)
    try:
        import numpy._core.multiarray as multiarray
        if not hasattr(multiarray, '_ARRAY_API'):
            multiarray._ARRAY_API = getattr(np, '_ARRAY_API', None)
    except Exception:
        pass
    
    # CRITICAL: Also patch numpy.core.multiarray (older numpy versions)
    try:
        import numpy.core.multiarray as old_multiarray
        if not hasattr(old_multiarray, '_ARRAY_API'):
            old_multiarray._ARRAY_API = getattr(np, '_ARRAY_API', None)
    except Exception:
        pass
    
    # Force numpy to be fully loaded before cv2
    _ = np.__version__  # Trigger full numpy load
    
    # Now import cv2 - numpy should be fully patched
    import cv2  # type: ignore
    HAS_CV2 = True
except (ImportError, AttributeError) as e:  # pragma: no cover - optional dependency
    if '_ARRAY_API' in str(e) or isinstance(e, AttributeError):
        # cv2 import failed due to _ARRAY_API - this should NOT happen
        np = None  # type: ignore
        cv2 = None  # type: ignore
        HAS_CV2 = False
        import logging
        logging.getLogger(__name__).error(f"❌ cv2 import failed: NumPy _ARRAY_API error: {e}")
    else:
        np = None  # type: ignore
        cv2 = None  # type: ignore
        HAS_CV2 = False

from core.base_component import BaseComponent
from core.sentience.vr_sentience_integration import VRSentienceIntegration

logger = logging.getLogger(__name__)

IS_WSL2 = False

# Import appropriate VR device manager
VR_AVAILABLE = False
VRDeviceManager = None
get_device_manager = None

if IS_WSL2:
    # Use WSL2-optimized device manager
    try:
        from vr.system.device_manager_wsl2 import WSL2VRDeviceManager, get_wsl2_device_manager
        VR_AVAILABLE = True
        VRDeviceManager = WSL2VRDeviceManager
        get_device_manager = get_wsl2_device_manager
        logger.info("✅ Using WSL2-optimized VR device manager")
    except ImportError as e:
        logger.warning(f"WSL2 VR system not available: {e}")
else:
    # Use standard Windows device manager
    try:
        from vr.system.device_manager import VRDeviceManager as WindowsVRDeviceManager, get_device_manager as get_windows_device_manager
        VR_AVAILABLE = True
        VRDeviceManager = WindowsVRDeviceManager
        get_device_manager = get_windows_device_manager
        logger.info("✅ Using Windows VR device manager")
    except ImportError as e:
        logger.warning(f"VR system not available: {e}")

class VRSystem(BaseComponent):
    """
    Component for handling VR integration with Kingdom AI.
    Manages connections to VR headsets and devices for immersive trading.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the VRSystem component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus=event_bus, config=config)
        self.name = "VRSystem"
        self.description = "Manages VR integration for immersive trading"
        
        # VR device configuration - Auto-detect Quest 3 IP and optional Meta glasses bridge
        quest_ip = self._detect_quest3_wireless()
        meta_bridge = self._detect_meta_glasses_bridge()

        default_devices = {
            "oculus": {
                "ip": quest_ip if quest_ip else "127.0.0.1",
                "port": 9000,
                "enabled": True,
                "protocol": "websocket",
            },
            "vive": {
                "ip": "127.0.0.1",
                "port": 9001,
                "enabled": False,
                "protocol": "tcp",
            },
            "meta_glasses": {
                "ip": meta_bridge[0] if meta_bridge else "127.0.0.1",
                "port": meta_bridge[1] if meta_bridge else 9100,
                "enabled": bool(meta_bridge),
                "protocol": "websocket",
                "device_type": "meta_glasses",
            },
        }

        self.devices = self.config.get("devices", default_devices)
        
        if quest_ip:
            logger.info(f"✅ Quest 3 detected at {quest_ip}")
        else:
            logger.info("Quest 3 not detected via ADB (connect with: adb connect <IP>:5555)")
        
        # VR settings
        self.update_interval = self.config.get("update_interval", 0.05)  # 20 Hz
        self.command_timeout = self.config.get("command_timeout", 5.0)  # seconds
        self.reconnect_interval = self.config.get("reconnect_interval", 5.0)  # seconds
        self.max_reconnect_attempts = self.config.get("max_reconnect_attempts", 5)
        
        # VR environment settings
        self.environment = self.config.get("environment", "trading_floor")
        self.custom_environments = self.config.get("custom_environments", [])
        
        # Internal state
        self.connections = {}  # Device connections
        self.connection_tasks = {}  # Connection tasks
        self.device_status = {}  # Device status
        self.is_running = False
        self.connected = False  # FIX: Add missing connected attribute
        self._sentience_task = None
        self.session_id = None
        self.session_start_time = None
        self.track_motion = False

        # FIX: Ensure tracking state attributes exist even when no headset is connected yet
        self.head_position = [0, 0, 0]
        self.head_rotation = [0, 0, 0]
        self.left_hand_position = [0, 0, 0]
        self.left_hand_rotation = [0, 0, 0]
        self.right_hand_position = [0, 0, 0]
        self.right_hand_rotation = [0, 0, 0]
        
        # SOTA 2026: VL-JEPA integration for AI-powered VR vision
        self._vl_jepa_enabled = True
        self._vl_jepa = None  # Lazy loaded
        self._zero_latency_mode = True  # Mirror-like instant feedback
        
        # FIX: Add missing VR state attributes
        self.current_state = {
            "connected": False,
            "environment": self.environment,
            "tracking_enabled": False,
            "head_position": self.head_position,
            "head_rotation": self.head_rotation,
            "performance": {"fps": 0.0, "frame_time_ms": 0.0, "dropped_frames": 0}
        }
        self.current_environment = self.environment
        self.interaction_history = []
        # Lightweight performance telemetry state
        self.performance_metrics = {
            "frame_count": 0,
            "fps": 0.0,
            "avg_frame_time": 0.0,
            "last_frame_ts": 0.0,
            "dropped_frames": 0,
        }
        self._last_perf_publish_ts: float = 0.0
        
        # Sentience integration
        self.sentience_integration = VRSentienceIntegration(event_bus=self.event_bus)
        self.sentience_monitoring_enabled = True
        self.sentience_metrics_history = []
    
    def _detect_quest3_wireless(self) -> Optional[str]:
        """Detect Quest 3 wireless IP using ADB."""
        try:
            import subprocess
            # Check ADB devices
            result = subprocess.run(['adb', 'devices'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            
            # Parse output for wireless devices (contain :5555)
            for line in result.stdout.split('\n'):
                if ':5555' in line and 'device' in line:
                    # Extract IP from "192.168.1.105:5555	device"
                    ip = line.split(':')[0].strip()
                    logger.info(f"🎮 Found Quest 3 at {ip}:5555")
                    return ip
            
            logger.debug("No wireless Quest 3 found via ADB")
            return None
        except Exception as e:
            logger.debug(f"Quest 3 detection failed: {e}")
            return None

    def _detect_meta_glasses_bridge(self):
        try:
            host = os.environ.get("META_GLASSES_BRIDGE_HOST")
            port_str = os.environ.get("META_GLASSES_BRIDGE_PORT")

            if host and port_str:
                try:
                    port = int(port_str)
                except ValueError:
                    logger.warning(
                        "Invalid META_GLASSES_BRIDGE_PORT %r; expected integer",
                        port_str,
                    )
                    return None

                logger.info(f"Found Meta glasses bridge from env at {host}:{port}")
                return host, port

            return None
        except Exception as e:
            logger.debug(f"Meta glasses bridge detection failed: {e}")
            return None
        
    async def initialize(self):
        """Initialize the VRSystem component."""
        logger.info("Initializing VRSystem component")
        
        # CRITICAL FIX: Check if event_bus exists and has subscribe method
        if not self.event_bus:
            logger.debug("VR System: No event bus available, skipping event subscriptions")
        elif hasattr(self.event_bus, 'subscribe'):
            try:
                # Subscribe to relevant events
                # Check if subscribe is async or sync
                subscribe_method = self.event_bus.subscribe
                is_async = asyncio.iscoroutinefunction(subscribe_method)
                
                subscriptions = [
                    ("vr.connect", self.on_connect_request),
                    ("vr.disconnect", self.on_disconnect_request),
                    ("vr.environment.change", self.on_environment_change),
                    ("vr.command", self.on_vr_command),
                    ("vr.tracking.toggle", self.on_tracking_toggle),
                    ("system.shutdown", self.on_shutdown),
                    # Sentience-related events
                    ("vr.sentience.toggle", self.on_sentience_toggle),
                    ("vr.sentience.threshold.adjust", self.on_sentience_threshold_adjust),
                    ("sentience.detection", self.on_sentience_detection),
                    ("sentience.threshold.crossed", self.on_sentience_threshold_crossed),
                    ("vr.quantum.influence", self.on_quantum_influence),
                    ("vr.experience.enhance", self.on_experience_enhance),
                    ("vr.experience.revert", self.on_experience_revert),
                    # SOTA 2026: VL-JEPA vision processing
                    ("vr.frame", self._on_vr_frame),
                    # SOTA 2026: Chat/Voice command events
                    ("vr.system.start", self._handle_vr_start),
                    ("vr.system.stop", self._handle_vr_stop),
                    ("vr.status.request", self._handle_vr_status),
                    ("vr.calibrate", self._handle_vr_calibrate),
                    ("vr.hands.enable", self._handle_hands_enable),
                    ("vr.hands.disable", self._handle_hands_disable),
                    ("vr.trading.open", self._handle_trading_open),
                    # SOTA 2026: Receive webcam/vision frames for VR passthrough/AR
                    ("vision.stream.frame", self._on_vision_stream_frame),
                    ("vr.vision.frame", self._on_vision_stream_frame),
                    # SOTA 2026: Visual creation output to display in VR
                    ("visual.generated", self._on_visual_generated),
                    ("visual.display", self._on_visual_display),
                ]
                
                for event_name, handler in subscriptions:
                    try:
                        if is_async:
                            await subscribe_method(event_name, handler)
                        else:
                            subscribe_method(event_name, handler)
                    except Exception as e:
                        logger.warning(f"Failed to subscribe to {event_name}: {e}")
                
                logger.info("✅ VR System event subscriptions completed")
            except Exception as e:
                logger.error(f"❌ VR System event subscription error: {e}")
        else:
            logger.warning("⚠️ VR System: Event bus has no subscribe method")
        
        # Initialize sentience integration
        try:
            logger.info("Initializing VR Sentience Integration")
            sentience_success = await self.sentience_integration.initialize()
            if sentience_success:
                logger.info("VR Sentience Integration initialized successfully")
            else:
                logger.debug("VR Sentience in DORMANT state (normal initial state)")
                self.sentience_monitoring_enabled = False
        except Exception as e:
            # DORMANT is not an error - it's the normal initial state
            if "DORMANT" in str(e):
                logger.info(f"ℹ️ VR Sentience in DORMANT state (normal initial state)")
                self.sentience_monitoring_enabled = False
            else:
                logger.error(f"Error initializing VR Sentience Integration: {str(e)}")
                self.sentience_monitoring_enabled = False
        
        # Load VR configuration
        await self.load_vr_config()
        
        # Auto-connect if enabled
        if self.config.get("auto_connect", False):
            logger.info("Auto-connecting to VR devices")
            await self.connect_to_devices()
        
        # Start sentience monitoring if enabled
        if self.sentience_monitoring_enabled:
            try:
                # CRITICAL FIX: Use ensure_future to avoid RuntimeError
                task = getattr(self, "_sentience_task", None)
                if task is None or task.done():
                    self._sentience_task = asyncio.ensure_future(
                        self._sentience_monitoring_loop()
                    )
                logger.info("VR sentience monitoring started")
            except Exception as e:
                logger.error(f"Failed to start VR sentience monitoring: {e}")
                self.sentience_monitoring_enabled = False
        
        logger.info("VRSystem component initialized")
        
    async def _on_vr_frame(self, data: Dict[str, Any]):
        """SOTA 2026: Process VR frame with VL-JEPA for AI-powered vision understanding."""
        if not self._vl_jepa_enabled:
            return
        
        try:
            frame = data.get("frame")
            if frame is None:
                return
            
            # Lazy load VL-JEPA
            if self._vl_jepa is None:
                try:
                    from core.vl_jepa import VLJEPAIntegration
                    self._vl_jepa = VLJEPAIntegration(event_bus=self.event_bus)
                    logger.info("VL-JEPA loaded for VR vision processing")
                except ImportError:
                    self._vl_jepa_enabled = False
                    return
            
            # Send to VL-JEPA for gesture/scene understanding (async, non-blocking)
            if self.event_bus and hasattr(self.event_bus, "publish"):
                self.event_bus.publish("vl_jepa.vr_frame", {
                    "frame": frame,
                    "timestamp": data.get("timestamp", time.time()),
                    "device": data.get("device", "vr_headset"),
                    "tracking": {
                        "head_position": self.head_position,
                        "head_rotation": self.head_rotation,
                    }
                })
        except Exception as e:
            logger.debug(f"VR frame VL-JEPA processing error: {e}")

    async def load_vr_config(self):
        """Load VR configuration from storage."""
        config_file = os.path.join(self.config.get("data_dir", "data"), "vr_config.json")
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    vr_config = json.load(f)
                    
                    # Update configuration
                    if "devices" in vr_config:
                        self.devices = vr_config["devices"]
                        
                    if "environment" in vr_config:
                        self.environment = vr_config["environment"]
                        
                    if "custom_environments" in vr_config:
                        self.custom_environments = vr_config["custom_environments"]
                        
                    logger.info("Loaded VR configuration")
        except Exception as e:
            logger.error(f"Error loading VR configuration: {str(e)}")
    
    async def save_vr_config(self):
        """Save VR configuration to storage."""
        config_file = os.path.join(self.config.get("data_dir", "data"), "vr_config.json")
        
        try:
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            
            vr_config = {
                "devices": self.devices,
                "environment": self.environment,
                "custom_environments": self.custom_environments,
                "last_saved": datetime.now().isoformat()
            }
            
            with open(config_file, 'w') as f:
                json.dump(vr_config, f, indent=2)
                
            logger.info("Saved VR configuration")
        except Exception as e:
            logger.error(f"Error saving VR configuration: {str(e)}")
    
    async def connect_to_devices(self):
        """Connect to configured VR devices."""
        self.is_running = True
        
        # Initialize session
        self.session_id = f"session_{int(time.time())}"
        self.session_start_time = datetime.now().isoformat()
        
        for device_id, device_config in self.devices.items():
            if device_config.get("enabled", False):
                self.connection_tasks[device_id] = asyncio.ensure_future(
                    self.connect_to_device(device_id, device_config)
                )
        
        # Start tracking if any device connected
        if self.connection_tasks:
            self.track_motion = True
            # Store task reference to prevent it from being garbage collected
            self._tracking_task = asyncio.ensure_future(self.track_motion_loop())
            
            # Publish VR session start
            self.event_bus.publish("vr.session.started", {
                "session_id": self.session_id,
                "start_time": self.session_start_time,
                "environment": self.environment,
                "devices": [device_id for device_id in self.connection_tasks.keys()]
            })
    
    async def connect_to_device(self, device_id, device_config):
        """
        Connect to a specific VR device.
        
        Args:
            device_id: Device identifier
            device_config: Device configuration
        """
        ip = device_config.get("ip", "127.0.0.1")
        port = device_config.get("port", 9000)
        protocol = device_config.get("protocol", "websocket")
        
        reconnect_attempts = 0
        
        while self.is_running and reconnect_attempts < self.max_reconnect_attempts:
            try:
                logger.info(f"Connecting to {device_id} VR device at {ip}:{port}")
                
                # Update device status
                self.device_status[device_id] = "connecting"
                
                # Connect based on protocol
                if protocol == "websocket":
                    # Connect via WebSocket
                    url = f"ws://{ip}:{port}"
                    async with websockets.connect(url) as websocket:
                        self.connections[device_id] = websocket
                        self.device_status[device_id] = "connected"
                        
                        # Publish connection status
                        self.event_bus.publish("vr.device.connected", {
                            "device_id": device_id,
                            "ip": ip,
                            "port": port,
                            "protocol": protocol,
                            "timestamp": datetime.now().isoformat()
                        })

                        # Mirror Meta glasses bridge status + vision state for GUI
                        if device_id == "meta_glasses" or self.devices.get(device_id, {}).get("device_type") == "meta_glasses":
                            try:
                                bridge_label = f"{ip}:{port}"
                                self.event_bus.publish(
                                    "meta.glasses.status",
                                    {
                                        "device_id": device_id,
                                        "status": "connected",
                                        "bridge": bridge_label,
                                        "timestamp": datetime.now().isoformat(),
                                    },
                                )
                                self.event_bus.publish(
                                    "vision.stream.meta_glasses.status",
                                    {
                                        "active": True,
                                        "bridge": bridge_label,
                                    },
                                )
                            except Exception:
                                # Never break VR session startup because of optional Meta glasses signals
                                pass
                        
                        # Send initial configuration
                        await self.send_config_to_device(device_id)
                        
                        # Listen for device updates
                        while self.is_running:
                            try:
                                # Wait for message with timeout
                                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                                await self.process_device_message(device_id, message)
                            except asyncio.TimeoutError:
                                # Check if still connected
                                try:
                                    await websocket.ping()
                                except:
                                    logger.warning(f"Lost connection to {device_id}")
                                    break
                
                elif protocol == "tcp":
                    # Connect via TCP
                    reader, writer = await asyncio.open_connection(ip, port)
                    self.connections[device_id] = (reader, writer)
                    self.device_status[device_id] = "connected"
                    
                    # Publish connection status
                    self.event_bus.publish("vr.device.connected", {
                        "device_id": device_id,
                        "ip": ip,
                        "port": port,
                        "protocol": protocol,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Send initial configuration
                    await self.send_config_to_device(device_id)
                    
                    # Listen for device updates
                    while self.is_running:
                        try:
                            # Wait for message with timeout
                            data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                            if not data:
                                logger.warning(f"Connection closed by {device_id}")
                                break
                            await self.process_device_message(device_id, data)
                        except asyncio.TimeoutError:
                            # Just continue, TCP doesn't have ping
                            pass
                
                else:
                    logger.error(f"Unsupported protocol for {device_id}: {protocol}")
                    break
                    
                # Reset reconnect attempts on successful connection
                reconnect_attempts = 0
                
            except (ConnectionRefusedError, ConnectionResetError, 
                    websockets.exceptions.ConnectionClosed) as e:
                
                logger.error(f"Connection to {device_id} failed: {str(e)}")
                self.device_status[device_id] = "disconnected"
                reconnect_attempts += 1
                
                # Publish connection error
                self.event_bus.publish("vr.device.error", {
                    "device_id": device_id,
                    "error": str(e),
                    "attempt": reconnect_attempts,
                    "max_attempts": self.max_reconnect_attempts,
                    "timestamp": datetime.now().isoformat()
                })
                # Mirror Meta glasses error status for GUI
                if device_id == "meta_glasses" or self.devices.get(device_id, {}).get("device_type") == "meta_glasses":
                    try:
                        self.event_bus.publish(
                            "meta.glasses.status",
                            {
                                "device_id": device_id,
                                "status": "error",
                                "error": str(e),
                                "timestamp": datetime.now().isoformat(),
                            },
                        )
                        self.event_bus.publish(
                            "vision.stream.meta_glasses.status",
                            {
                                "active": False,
                                "error": str(e),
                            },
                        )
                    except Exception:
                        pass
                
                # Wait before reconnecting
                await asyncio.sleep(self.reconnect_interval)
                
            except Exception as e:
                logger.error(f"Error connecting to {device_id}: {str(e)}")
                self.device_status[device_id] = "error"
                reconnect_attempts += 1
                
                # Publish error
                self.event_bus.publish("vr.device.error", {
                    "device_id": device_id,
                    "error": str(e),
                    "attempt": reconnect_attempts,
                    "max_attempts": self.max_reconnect_attempts,
                    "timestamp": datetime.now().isoformat()
                })
                # Mirror Meta glasses error status for GUI
                if device_id == "meta_glasses" or self.devices.get(device_id, {}).get("device_type") == "meta_glasses":
                    try:
                        self.event_bus.publish(
                            "meta.glasses.status",
                            {
                                "device_id": device_id,
                                "status": "error",
                                "error": str(e),
                                "timestamp": datetime.now().isoformat(),
                            },
                        )
                        self.event_bus.publish(
                            "vision.stream.meta_glasses.status",
                            {
                                "active": False,
                                "error": str(e),
                            },
                        )
                    except Exception:
                        pass
                
                # Wait before reconnecting
                await asyncio.sleep(self.reconnect_interval)
        
        # Remove connection
        self.connections.pop(device_id, None)
        self.device_status[device_id] = "disconnected"

        # Mirror Meta glasses disconnected status
        if device_id == "meta_glasses" or self.devices.get(device_id, {}).get("device_type") == "meta_glasses":
            try:
                self.event_bus.publish(
                    "meta.glasses.status",
                    {
                        "device_id": device_id,
                        "status": "disconnected",
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                self.event_bus.publish(
                    "vision.stream.meta_glasses.status",
                    {
                        "active": False,
                    },
                )
            except Exception:
                pass
        
        if reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts reached for {device_id}")
            
            # Publish max attempts reached
            self.event_bus.publish("vr.device.max_attempts", {
                "device_id": device_id,
                "max_attempts": self.max_reconnect_attempts,
                "timestamp": datetime.now().isoformat()
            })
    
    async def send_config_to_device(self, device_id):
        """
        Send configuration to a VR device.
        
        Args:
            device_id: Device identifier
        """
        try:
            config_data = {
                "command": "configure",
                "environment": self.environment,
                "tracking": self.track_motion,
                "session_id": self.session_id,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.send_to_device(device_id, config_data)
            logger.info(f"Sent configuration to {device_id}")
        except Exception as e:
            logger.error(f"Error sending configuration to {device_id}: {str(e)}")
    
    async def send_to_device(self, device_id, data):
        """
        Send data to a VR device.
        
        Args:
            device_id: Device identifier
            data: Data to send
            
        Returns:
            bool: Success status
        """
        if device_id not in self.connections:
            logger.warning(f"Cannot send to {device_id}: not connected")
            return False
            
        try:
            connection = self.connections[device_id]
            protocol = self.devices[device_id].get("protocol", "websocket")
            
            # Prepare data
            message = json.dumps(data)
            
            # Send based on protocol
            if protocol == "websocket":
                await connection.send(message)
            elif protocol == "tcp":
                _, writer = connection
                writer.write(message.encode() + b'\n')
                await writer.drain()
                
            return True
        except Exception as e:
            logger.error(f"Error sending to {device_id}: {str(e)}")
            return False
    
    async def process_device_message(self, device_id, message):
        """Process a message from a VR device."""
        try:
            # Parse message
            if isinstance(message, bytes):
                message = message.decode('utf-8')
                
            data = json.loads(message)
            
            # Process by message type
            if "type" in data:
                message_type = data["type"]

                is_meta = device_id == "meta_glasses" or self.devices.get(device_id, {}).get("device_type") == "meta_glasses"

                # Meta glasses frame messages (bridge -> Kingdom vision stream)
                if is_meta and message_type in ("frame", "meta_frame"):
                    frame_bgr = self._decode_meta_glasses_frame(data)
                    if frame_bgr is not None and self.event_bus:
                        try:
                            self.event_bus.publish(
                                "vision.stream.meta_glasses.frame",
                                {
                                    "frame": frame_bgr,
                                    "timestamp": time.time(),
                                    "device_id": device_id,
                                },
                            )
                        except Exception:
                            pass
                    return

                if message_type == "tracking":
                    # Update tracking data
                    if "head" in data:
                        self.head_position = data["head"].get("position", [0, 0, 0])
                        self.head_rotation = data["head"].get("rotation", [0, 0, 0])
                        
                    if "left_hand" in data:
                        self.left_hand_position = data["left_hand"].get("position", [0, 0, 0])
                        self.left_hand_rotation = data["left_hand"].get("rotation", [0, 0, 0])
                        
                    if "right_hand" in data:
                        self.right_hand_position = data["right_hand"].get("position", [0, 0, 0])
                        self.right_hand_rotation = data["right_hand"].get("rotation", [0, 0, 0])
                        
                elif message_type == "interaction":
                    # Process user interaction
                    if "action" in data:
                        action = data["action"]
                        payload = {
                            "device_id": device_id,
                            "action": action,
                            "data": data,
                            "timestamp": datetime.now().isoformat(),
                        }
                        self.event_bus.publish("vr.interaction", payload)
                        if is_meta:
                            try:
                                self.event_bus.publish("meta.glasses.interaction", payload)
                            except Exception:
                                pass
                        
                elif message_type == "status":
                    # Update device status
                    if "status" in data:
                        self.device_status[device_id] = data["status"]
                        
                        # Publish status update
                        status_payload = {
                            "device_id": device_id,
                            "status": data["status"],
                            "data": data,
                            "timestamp": datetime.now().isoformat(),
                        }
                        self.event_bus.publish("vr.device.status", status_payload)
                        if is_meta:
                            try:
                                self.event_bus.publish("meta.glasses.status", status_payload)
                                self.event_bus.publish(
                                    "vision.stream.meta_glasses.status",
                                    {
                                        "active": data["status"] == "ok",
                                        "status": data["status"],
                                    },
                                )
                            except Exception:
                                pass
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {device_id}: {message}")
        except Exception as e:
            logger.error(f"Error processing message from {device_id}: {str(e)}")

    def _decode_meta_glasses_frame(self, data: Dict[str, Any]):
        if not HAS_CV2:
            return None
        try:
            payload = data.get("frame") or data.get("frame_jpeg") or data.get("image")
            if not isinstance(payload, str):
                return None
            raw = base64.b64decode(payload)
            arr = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return None
            try:
                img = cv2.flip(img, 1)
            except Exception:
                pass
            return img
        except Exception as e:
            logger.debug(f"Meta glasses frame decode failed: {e}")
            return None
    
    async def track_motion_loop(self):
        """Track and publish VR motion data."""
        try:
            while self.is_running and self.track_motion:
                frame_start = time.time()
                # Publish tracking data if any device is connected
                if self.connections:
                    tracking_data = {
                        "head": {
                            "position": self.head_position,
                            "rotation": self.head_rotation
                        },
                        "left_hand": {
                            "position": self.left_hand_position,
                            "rotation": self.left_hand_rotation
                        },
                        "right_hand": {
                            "position": self.right_hand_position,
                            "rotation": self.right_hand_rotation
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    self.event_bus.publish("vr.tracking.update", tracking_data)
                    # Update simple performance metrics
                    now = frame_start
                    last_ts = self.performance_metrics.get("last_frame_ts", 0.0) or 0.0
                    if last_ts > 0.0:
                        dt = max(1e-6, now - last_ts)
                        target = float(self.update_interval) if self.update_interval else dt
                        # Estimate FPS and average frame time using EMA for stability
                        inst_fps = 1.0 / dt
                        prev_fps = float(self.performance_metrics.get("fps", 0.0) or 0.0)
                        self.performance_metrics["fps"] = 0.9 * prev_fps + 0.1 * inst_fps if prev_fps > 0 else inst_fps
                        prev_avg = float(self.performance_metrics.get("avg_frame_time", 0.0) or 0.0)
                        self.performance_metrics["avg_frame_time"] = 0.9 * prev_avg + 0.1 * dt if prev_avg > 0 else dt
                        # Very rough dropped-frame heuristic: long frame compared to target interval
                        if dt > target * 1.5:
                            # Count how many nominal intervals fit into this long frame minus one
                            approx_skips = int(dt / max(target, 1e-6)) - 1
                            if approx_skips > 0:
                                self.performance_metrics["dropped_frames"] += approx_skips
                    self.performance_metrics["frame_count"] += 1
                    self.performance_metrics["last_frame_ts"] = now

                    # Periodically publish performance telemetry (about once per second)
                    if now - self._last_perf_publish_ts >= 1.0:
                        perf_payload = {
                            "fps_estimate": float(self.performance_metrics.get("fps", 0.0) or 0.0),
                            "frame_time_ms": float(self.performance_metrics.get("avg_frame_time", 0.0) or 0.0) * 1000.0,
                            "dropped_frames": int(self.performance_metrics.get("dropped_frames", 0)),
                            "timestamp": datetime.now().isoformat(),
                        }
                        # Sync into current_state for any GUI/monitoring components
                        self.current_state["performance"] = {
                            "fps": perf_payload["fps_estimate"],
                            "frame_time_ms": perf_payload["frame_time_ms"],
                            "dropped_frames": perf_payload["dropped_frames"],
                        }
                        try:
                            self.event_bus.publish("vr.performance.update", perf_payload)
                        except Exception:
                            # Telemetry should never break tracking
                            pass
                        # Reset dropped-frame counter after reporting
                        self.performance_metrics["dropped_frames"] = 0
                        self._last_perf_publish_ts = now
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
                
        except asyncio.CancelledError:
            logger.info("VR tracking loop cancelled")
        except Exception as e:
            logger.error(f"Error in VR tracking loop: {str(e)}")
            
            # Restart the loop if still tracking
            if self.is_running and self.track_motion:
                self._tracking_task = asyncio.ensure_future(self.track_motion_loop())
    
    async def disconnect_from_devices(self):
        """Disconnect from all VR devices."""
        logger.info("Disconnecting from VR devices")
        
        # Stop tracking
        self.track_motion = False
        
        # Cancel connection tasks
        for device_id, task in self.connection_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Clear connections
        self.connections = {}
        self.connection_tasks = {}
        
        # Update device status
        for device_id in self.device_status:
            self.device_status[device_id] = "disconnected"
        
        # Publish session end
        if self.session_id and self.session_start_time:
            # FIX: Check if session_start_time is not None before parsing
            start_time = datetime.fromisoformat(self.session_start_time) if isinstance(self.session_start_time, str) else self.session_start_time
            session_duration = (datetime.now() - start_time).total_seconds()
            
            self.event_bus.publish("vr.session.ended", {
                "session_id": self.session_id,
                "start_time": self.session_start_time,
                "end_time": datetime.now().isoformat(),
                "duration": session_duration,
                "environment": self.environment
            })
            
            self.session_id = None
        
        logger.info("Disconnected from all VR devices")
    
    async def change_environment(self, environment):
        """
        Change the VR environment.
        
        Args:
            environment: Environment name
            
        Returns:
            dict: Change result
        """
        try:
            # Check if environment exists
            valid_environments = ["trading_floor", "blockchain_visualizer", "market_overview", "portfolio_analysis"]
            valid_environments.extend(self.custom_environments)
            
            if environment not in valid_environments:
                return {
                    "success": False,
                    "error": f"Unknown environment: {environment}",
                    "valid_environments": valid_environments
                }
            
            # Update environment
            old_environment = self.environment
            self.environment = environment
            
            # Send environment change to all connected devices
            for device_id in self.connections:
                await self.send_to_device(device_id, {
                    "command": "change_environment",
                    "environment": environment,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Save configuration
            await self.save_vr_config()
            
            logger.info(f"Changed VR environment to {environment}")
            
            # Publish environment change
            self.event_bus.publish("vr.environment.changed", {
                "old_environment": old_environment,
                "new_environment": environment,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "success": True,
                "environment": environment
            }
            
        except Exception as e:
            logger.error(f"Error changing environment: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_command_to_devices(self, command_data):
        """
        Send a command to all connected VR devices.
        
        Args:
            command_data: Command data
            
        Returns:
            dict: Command result
        """
        try:
            if not self.connections:
                return {
                    "success": False,
                    "error": "No connected devices"
                }
            
            # Send command to all devices
            for device_id in self.connections:
                await self.send_to_device(device_id, command_data)
            
            logger.info(f"Sent command to all devices: {command_data.get('command')}")
            
            return {
                "success": True,
                "devices": list(self.connections.keys()),
                "command": command_data.get("command")
            }
            
        except Exception as e:
            logger.error(f"Error sending command: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_vr_command(self, command_data):
        """
        Internal method to send VR commands to connected devices.
        
        Args:
            command_data: Command data dictionary
            
        Returns:
            dict: Command result
        """
        try:
            if not self.connections:
                logger.warning("No VR devices connected, command not sent")
                return {"success": False, "error": "No connected devices"}
            
            # Send command to all connected devices
            results = []
            for device_id in self.connections:
                try:
                    await self.send_to_device(device_id, command_data)
                    results.append({"device_id": device_id, "success": True})
                except Exception as e:
                    logger.error(f"Failed to send command to {device_id}: {e}")
                    results.append({"device_id": device_id, "success": False, "error": str(e)})
            
            return {
                "success": any(r["success"] for r in results),
                "results": results,
                "command": command_data.get("command")
            }
        except Exception as e:
            logger.error(f"Error in _send_vr_command: {e}")
            return {"success": False, "error": str(e)}
    
    async def toggle_tracking(self, enabled):
        """
        Toggle VR motion tracking.
        
        Args:
            enabled: Whether tracking should be enabled
            
        Returns:
            dict: Toggle result
        """
        try:
            old_status = self.track_motion
            self.track_motion = enabled
            
            # Start tracking loop if enabled and not already running
            if enabled and not old_status and self.connections:
                self._tracking_task = asyncio.ensure_future(self.track_motion_loop())
            
            # Send tracking command to devices
            for device_id in self.connections:
                await self.send_to_device(device_id, {
                    "command": "set_tracking",
                    "enabled": enabled,
                    "timestamp": datetime.now().isoformat()
                })
            
            logger.info(f"{'Enabled' if enabled else 'Disabled'} VR motion tracking")
            
            return {
                "success": True,
                "tracking": enabled
            }
            
        except Exception as e:
            logger.error(f"Error toggling tracking: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def on_connect_request(self, data):
        """
        Handle VR connect request event.
        
        Args:
            data: Connect request data
        """
        request_id = data.get("request_id")
        
        # Check if already connected
        if self.connections:
            result = {
                "success": False,
                "error": "Already connected to VR devices",
                "devices": list(self.connections.keys())
            }
        else:
            # Start connections
            await self.connect_to_devices()
            result = {
                "success": True,
                "session_id": self.session_id,
                "environment": self.environment
            }
        
        # Publish result
        self.event_bus.publish("vr.connect.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_disconnect_request(self, data):
        """
        Handle VR disconnect request event.
        
        Args:
            data: Disconnect request data
        """
        request_id = data.get("request_id")
        
        # Check if connected
        if not self.connections:
            result = {
                "success": False,
                "error": "Not connected to any VR devices"
            }
        else:
            # Disconnect from devices
            await self.disconnect_from_devices()
            result = {
                "success": True
            }
        
        # Publish result
        self.event_bus.publish("vr.disconnect.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_environment_change(self, data):
        """
        Handle environment change event.
        
        Args:
            data: Environment change data
        """
        request_id = data.get("request_id")
        environment = data.get("environment")
        
        if not environment:
            result = {
                "success": False,
                "error": "Environment not specified"
            }
        else:
            result = await self.change_environment(environment)
        
        # Publish result
        self.event_bus.publish("vr.environment.change.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_vr_command(self, data):
        """
        Handle VR command event.
        
        Args:
            data: VR command data
        """
        request_id = data.get("request_id")
        command = data.get("command")
        
        if not command:
            result = {
                "success": False,
                "error": "Command not specified"
            }
        else:
            # Send command to devices
            result = await self.send_command_to_devices(data)
        
        # Publish result
        self.event_bus.publish("vr.command.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_tracking_toggle(self, data):
        """
        Handle tracking toggle event.
        
        Args:
            data: Tracking toggle data
        """
        request_id = data.get("request_id")
        enabled = data.get("enabled", False)
        
        result = await self.toggle_tracking(enabled)
        
        # Publish result
        self.event_bus.publish("vr.tracking.toggle.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_shutdown(self, event_data):
        """Handle system shutdown event."""
        logger.info("VRSystem shutting down")
        
        # Disconnect from devices before shutting down
        if self.connected:
            await self.disconnect_from_devices()
            
        # Stop sentience monitoring if enabled
        self.sentience_monitoring_enabled = False
        # FIX: Check if shutdown method exists before calling
        if hasattr(self.sentience_integration, 'shutdown'):
            shutdown_result = self.sentience_integration.shutdown()  # type: ignore[attr-defined]
            # Check if it's a coroutine before awaiting
            if asyncio.iscoroutine(shutdown_result):
                await shutdown_result
            
        # Any other cleanup tasks here
        
    async def _sentience_monitoring_loop(self):
        """Background task to continuously monitor sentience metrics in VR."""
        logger.info("Starting VR sentience monitoring loop")
        
        try:
            while self.sentience_monitoring_enabled:
                if self.connected and self.current_state:
                    # Process VR state data for sentience detection
                    vr_data = {
                        "environment": self.current_environment,
                        "position": self.current_state.get("position", {}),
                        "rotation": self.current_state.get("rotation", {}),
                        "controllers": self.current_state.get("controllers", {}),
                        "gesture_recognition": self.current_state.get("gesture_recognition", {}),
                        "gaze_tracking": self.current_state.get("gaze_tracking", {}),
                        "interaction_history": self.interaction_history,
                        "anomaly_detections": self.current_state.get("anomaly_detections", []),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Process data through sentience integration
                    # FIX: Check if method exists and handle async/sync
                    if hasattr(self.sentience_integration, 'process_vr_data'):
                        process_result = self.sentience_integration.process_vr_data(vr_data)  # type: ignore[attr-defined]
                        if asyncio.iscoroutine(process_result):
                            await process_result
                    
                    # Store metrics history for trending analysis
                    # FIX: Check if method exists
                    if hasattr(self.sentience_integration, 'get_current_metrics'):
                        metrics_result = self.sentience_integration.get_current_metrics()  # type: ignore[attr-defined]
                        if asyncio.iscoroutine(metrics_result):
                            current_metrics = await metrics_result
                        else:
                            current_metrics = metrics_result
                    else:
                        current_metrics = {}
                    self.sentience_metrics_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "metrics": current_metrics
                    })
                    
                    # Keep history limited to reasonable size
                    if len(self.sentience_metrics_history) > 100:
                        self.sentience_metrics_history = self.sentience_metrics_history[-100:]
                    
                    # Publish current metrics to event bus for UI updates
                    publish_result = self.event_bus.publish("vr.sentience.metrics.update", {
                        "metrics": current_metrics,
                        "timestamp": datetime.now().isoformat()
                    })
                    if asyncio.iscoroutine(publish_result):
                        await publish_result  # type: ignore[misc]
                
                # Wait before next check
                await asyncio.sleep(1.0)  # Check every second
        except Exception as e:
            logger.error(f"Error in VR sentience monitoring loop: {str(e)}")
            self.sentience_monitoring_enabled = False
            
    async def on_sentience_toggle(self, event_data):
        """Handle request to toggle sentience monitoring."""
        enabled = event_data.get("enabled")
        
        if enabled is not None:
            self.sentience_monitoring_enabled = enabled
            logger.info(f"VR sentience monitoring {'enabled' if enabled else 'disabled'}")
            
            if enabled and not self._is_monitoring_running():
                # Restart monitoring if it was stopped
                try:
                    # CRITICAL FIX: Use ensure_future to avoid RuntimeError
                    task = getattr(self, "_sentience_task", None)
                    if task is None or task.done():
                        self._sentience_task = asyncio.ensure_future(
                            self._sentience_monitoring_loop()
                        )
                    logger.info("VR sentience monitoring restarted")
                except Exception as e:
                    logger.error(f"Failed to restart VR sentience monitoring: {e}")
                    self.sentience_monitoring_enabled = False
                
            # Notify subscribers of the change
            publish_result = self.event_bus.publish("vr.sentience.status", {
                "enabled": self.sentience_monitoring_enabled
            })
            if asyncio.iscoroutine(publish_result):
                await publish_result  # type: ignore[misc]
            
    def _is_monitoring_running(self):
        """Check if the monitoring task is currently running."""
        task = getattr(self, "_sentience_task", None)
        if task is not None:
            return not task.done()
        try:
            for t in asyncio.all_tasks():
                if t.get_name() == "vr_sentience_monitoring":
                    return not t.done()
        except Exception:
            return False
        return False
            
    async def on_sentience_threshold_adjust(self, event_data):
        """Handle request to adjust sentience detection threshold."""
        threshold = event_data.get("threshold")
        
        if threshold is not None and 0.0 <= threshold <= 1.0:
            # FIX: Check if method exists
            if hasattr(self.sentience_integration, 'set_sentience_threshold'):
                threshold_result = self.sentience_integration.set_sentience_threshold(threshold)  # type: ignore[attr-defined]
                if asyncio.iscoroutine(threshold_result):
                    await threshold_result
            logger.info(f"VR sentience threshold adjusted to {threshold}")
            
    async def on_sentience_detection(self, event_data):
        """Handle sentience detection event from any system component."""
        # Only process if it's related to VR
        source = event_data.get("source")
        if source == "vr" or source == "vr_system":
            logger.info(f"VR-related sentience detection received: {event_data}")
            
            # Process the detection through our integration
            # FIX: Check if method exists
            if hasattr(self.sentience_integration, 'process_external_detection'):
                detection_result = self.sentience_integration.process_external_detection(event_data)  # type: ignore[attr-defined]
                if asyncio.iscoroutine(detection_result):
                    await detection_result
            
    async def on_sentience_threshold_crossed(self, event_data):
        """Handle sentience threshold crossing events."""
        source = event_data.get("source")
        if source == "vr" or source == "vr_system":
            crossed_upward = event_data.get("crossed_upward", False)
            
            if crossed_upward:
                logger.info("VR sentience threshold crossed upward - enhancing experience")
                # Enhance VR experience based on sentience detection
                await self._enhance_vr_experience(event_data.get("metrics", {}))
            else:
                logger.info("VR sentience threshold crossed downward - reverting to standard experience")
                # Revert VR experience to standard settings
                await self._revert_vr_experience()
                
    async def _enhance_vr_experience(self, metrics):
        """Enhance VR experience based on sentience metrics."""
        if not self.connected:
            return
            
        try:
            # Customize environment based on metrics
            enhancement_level = metrics.get("aggregate_score", 0.5)
            
            # Prepare experience enhancement parameters
            enhancement_data = {
                "visual_quality": min(10, max(1, int(enhancement_level * 10))),
                "responsiveness": min(10, max(1, int(enhancement_level * 10))),
                "spatial_audio": True if enhancement_level > 0.6 else False,
                "haptic_intensity": min(10, max(1, int(enhancement_level * 10))),
                "environment_complexity": min(10, max(1, int(enhancement_level * 10)))
            }
            
            # Apply enhancements to VR system
            if self.current_environment:
                await self._send_vr_command({
                    "command": "enhance_experience",
                    "params": enhancement_data
                })
                logger.info(f"Enhanced VR experience with parameters: {enhancement_data}")
                
        except Exception as e:
            logger.error(f"Error enhancing VR experience: {str(e)}")
            
    async def _revert_vr_experience(self):
        """Revert VR experience to standard settings."""
        if not self.connected:
            return
            
        try:
            # Revert to standard settings
            await self._send_vr_command({
                "command": "revert_experience",
                "params": {"to_default": True}
            })
            logger.info("Reverted VR experience to standard settings")
            
        except Exception as e:
            logger.error(f"Error reverting VR experience: {str(e)}")
            
    async def on_quantum_influence(self, event_data):
        """Handle quantum influence events from the sentience system."""
        if not self.connected or not self.sentience_monitoring_enabled:
            return
            
        try:
            # Extract quantum influence parameters
            influence_type = event_data.get("type", "random")
            intensity = event_data.get("intensity", 0.5)
            target = event_data.get("target", "environment")
            
            # Apply quantum influence to VR environment
            await self._send_vr_command({
                "command": "apply_quantum_influence",
                "params": {
                    "type": influence_type,
                    "intensity": intensity,
                    "target": target,
                    "duration": event_data.get("duration", 5.0)  # seconds
                }
            })
            logger.info(f"Applied quantum influence to VR: {influence_type} at {intensity} intensity")
            
        except Exception as e:
            logger.error(f"Error applying quantum influence to VR: {str(e)}")
            
    async def on_experience_enhance(self, event_data):
        """Handle direct requests to enhance the VR experience."""
        if not self.connected:
            return
            
        try:
            # Get the list of requested enhancements
            enhancements = event_data.get("enhancements", [])
            sentience_metrics = event_data.get("sentience_metrics", {})
            
            # Create enhancement configuration
            enhance_config = {}
            
            if "increased_responsiveness" in enhancements:
                enhance_config["responsiveness"] = 10
                
            if "deeper_immersion" in enhancements:
                enhance_config["immersion_depth"] = 10
                
            if "enhanced_visuals" in enhancements:
                enhance_config["visual_quality"] = 10
                enhance_config["render_scale"] = 1.5
                
            if "spatial_audio_boost" in enhancements:
                enhance_config["spatial_audio"] = True
                enhance_config["audio_quality"] = 10
                
            if "haptic_feedback_intensity" in enhancements:
                enhance_config["haptic_intensity"] = 10
                
            # Apply the enhancements
            if enhance_config:
                await self._send_vr_command({
                    "command": "enhance_experience",
                    "params": enhance_config
                })
                logger.info(f"Enhanced VR experience with specific parameters: {enhance_config}")
                
        except Exception as e:
            logger.error(f"Error applying specific VR enhancements: {str(e)}")
            
    async def on_experience_revert(self, event_data):
        """Handle direct requests to revert the VR experience to standard settings."""
        await self._revert_vr_experience()
    
    async def shutdown(self):
        """Shutdown the VRSystem component."""
        logger.info("Shutting down VRSystem component")
        
        # Disconnect from devices
        self.is_running = False
        await self.disconnect_from_devices()
        
        # Save configuration
        await self.save_vr_config()
        
        logger.info("VRSystem component shut down successfully")
    
    def detect_real_vr_devices(self) -> Dict[str, Any]:
        """Detect real VR devices using OpenVR - NO MOCK DATA."""
        try:
            import openvr
            detected_devices = {
                'headsets': [],
                'controllers': [],
                'base_stations': [],
                'status': 'no_devices',
                'runtime': None
            }
            
            # Initialize OpenVR
            try:
                openvr.init(openvr.VRApplication_Scene)
                vr_system = openvr.VRSystem()
                
                if not vr_system:
                    detected_devices['status'] = 'no_runtime'
                    return detected_devices
                
                detected_devices['runtime'] = 'openvr'
                detected_devices['status'] = 'devices_found'
                
                # Detect all tracked devices - REAL device detection
                for device_id in range(openvr.k_unMaxTrackedDeviceCount):
                    if vr_system.isTrackedDeviceConnected(device_id):
                        device_class = vr_system.getTrackedDeviceClass(device_id)
                        
                        device_info = {
                            'device_id': device_id,
                            'connected': True,
                            'battery': self._get_device_battery(vr_system, device_id),
                            'serial_number': self._get_device_property(
                                vr_system, device_id, openvr.Prop_SerialNumber_String
                            ),
                            'model_number': self._get_device_property(
                                vr_system, device_id, openvr.Prop_ModelNumber_String
                            )
                        }
                        
                        if device_class == openvr.TrackedDeviceClass_HMD:
                            device_info['type'] = 'headset'
                            device_info['resolution'] = self._get_hmd_resolution(vr_system)
                            detected_devices['headsets'].append(device_info)
                        elif device_class == openvr.TrackedDeviceClass_Controller:
                            device_info['type'] = 'controller'
                            detected_devices['controllers'].append(device_info)
                        elif device_class == openvr.TrackedDeviceClass_TrackingReference:
                            device_info['type'] = 'base_station'
                            detected_devices['base_stations'].append(device_info)
                
                openvr.shutdown()
                logger.info(f"Real VR devices detected: {len(detected_devices['headsets'])} HMDs, "
                           f"{len(detected_devices['controllers'])} controllers")
                
            except Exception as e:
                logger.error(f"OpenVR error: {e}")
                detected_devices['status'] = 'openvr_error'
                detected_devices['error'] = str(e)
                
        except ImportError:
            logger.warning("OpenVR not available - install with: pip install openvr")
            detected_devices = {
                'headsets': [],
                'controllers': [],
                'base_stations': [],
                'status': 'openvr_not_available',
                'note': 'Install OpenVR: pip install openvr'
            }
        
        return detected_devices
    
    def _get_device_property(self, vr_system, device_id: int, prop: int) -> str:
        """Get device property safely."""
        try:
            prop_error = openvr.VRPropertyError()
            result = vr_system.getStringTrackedDeviceProperty(device_id, prop, prop_error)
            return result if prop_error.value == openvr.VRPropertyError_Success else 'Unknown'
        except:
            return 'Unknown'
    
    def _get_device_battery(self, vr_system, device_id: int) -> float:
        """Get device battery level."""
        try:
            prop_error = openvr.VRPropertyError()
            battery = vr_system.getFloatTrackedDeviceProperty(
                device_id, openvr.Prop_DeviceBatteryPercentage_Float, prop_error
            )
            return battery if prop_error.value == openvr.VRPropertyError_Success else 0.0
        except:
            return 0.0
    
    def _get_hmd_resolution(self, vr_system) -> tuple:
        """Get HMD resolution."""
        try:
            width = vr_system.getRecommendedRenderTargetSize()[0]
            height = vr_system.getRecommendedRenderTargetSize()[1]
            return (width, height)
        except:
            return (1920, 1080)
    
    def get_real_tracking_data(self) -> Dict[str, Any]:
        """Get real-time tracking data from VR devices - REAL DATA ONLY."""
        try:
            import openvr
            import numpy as np
            
            tracking_data = {
                'hmd_pose': None,
                'controller_poses': [],
                'tracking_quality': 'none',
                'play_area': None,
                'timestamp': time.time()
            }
            
            # Initialize OpenVR for tracking
            openvr.init(openvr.VRApplication_Scene)
            vr_system = openvr.VRSystem()
            
            if vr_system:
                # Get REAL tracking poses
                poses = vr_system.getDeviceToAbsoluteTrackingPose(
                    openvr.TrackingUniverseStanding, 0
                )
                
                for device_id in range(len(poses)):
                    pose = poses[device_id]
                    
                    if pose.bPoseIsValid:
                        device_class = vr_system.getTrackedDeviceClass(device_id)
                        
                        # Convert pose matrix to usable format
                        transform_matrix = np.array([
                            [pose.mDeviceToAbsoluteTracking.m[0][0], pose.mDeviceToAbsoluteTracking.m[0][1], 
                             pose.mDeviceToAbsoluteTracking.m[0][2], pose.mDeviceToAbsoluteTracking.m[0][3]],
                            [pose.mDeviceToAbsoluteTracking.m[1][0], pose.mDeviceToAbsoluteTracking.m[1][1], 
                             pose.mDeviceToAbsoluteTracking.m[1][2], pose.mDeviceToAbsoluteTracking.m[1][3]],
                            [pose.mDeviceToAbsoluteTracking.m[2][0], pose.mDeviceToAbsoluteTracking.m[2][1], 
                             pose.mDeviceToAbsoluteTracking.m[2][2], pose.mDeviceToAbsoluteTracking.m[2][3]],
                            [0, 0, 0, 1]
                        ])
                        
                        pose_data = {
                            'device_id': device_id,
                            'position': transform_matrix[:3, 3].tolist(),
                            'velocity': [pose.vVelocity.v[0], pose.vVelocity.v[1], pose.vVelocity.v[2]],
                            'angular_velocity': [pose.vAngularVelocity.v[0], pose.vAngularVelocity.v[1], pose.vAngularVelocity.v[2]],
                            'tracking_result': pose.eTrackingResult
                        }
                        
                        if device_class == openvr.TrackedDeviceClass_HMD:
                            tracking_data['hmd_pose'] = pose_data
                            tracking_data['tracking_quality'] = 'good' if pose.eTrackingResult == openvr.TrackingResult_Running_OK else 'poor'
                        elif device_class == openvr.TrackedDeviceClass_Controller:
                            tracking_data['controller_poses'].append(pose_data)
            
            openvr.shutdown()
            return tracking_data
            
        except ImportError:
            return {'error': 'OpenVR not available', 'timestamp': time.time()}
        except Exception as e:
            logger.error(f"Error getting VR tracking data: {e}")
            return {'error': str(e), 'timestamp': time.time()}
    
    def start_real_vr_session(self, environment: str = 'trading_floor') -> bool:
        """Start a real VR session - NO MOCK DATA."""
        try:
            logger.info(f"Starting REAL VR session with environment: {environment}")
            
            # Detect devices first
            devices = self.detect_real_vr_devices()
            if devices['status'] != 'devices_found':
                logger.warning(f"Cannot start VR session: {devices['status']}")
                return False
            
            # Start REAL VR session
            import openvr
            openvr.init(openvr.VRApplication_Scene)
            
            # Start compositor
            compositor = openvr.VRCompositor()
            if compositor:
                logger.info("VR compositor initialized")
                
            # Configure environment
            self._configure_vr_environment(environment)
            
            # Start tracking thread
            import threading
            self.tracking_thread = threading.Thread(
                target=self._continuous_tracking_thread, daemon=True
            )
            self.tracking_thread.start()
            
            self.vr_session_active = True
            logger.info("REAL VR session started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting VR session: {e}")
            return False
    
    def _configure_vr_environment(self, environment: str):
        """Configure VR environment settings."""
        environments = {
            'trading_floor': {
                'background': 'cyberpunk_city',
                'ui_scale': 1.2,
                'comfort_settings': 'medium'
            },
            'blockchain_explorer': {
                'background': 'digital_matrix',
                'ui_scale': 1.0,
                'comfort_settings': 'high'
            },
            'mining_dashboard': {
                'background': 'quantum_tunnel',
                'ui_scale': 1.1,
                'comfort_settings': 'low'
            }
        }
        
        config = environments.get(environment, environments['trading_floor'])
        logger.info(f"Configured VR environment: {environment}")
    
    def _continuous_tracking_thread(self):
        """Continuous tracking thread for real-time updates."""
        while getattr(self, 'vr_session_active', False):
            try:
                tracking_data = self.get_real_tracking_data()
                
                # Emit tracking data via event bus
                if hasattr(self, 'event_bus') and self.event_bus:
                    try:
                        # Use run_coroutine_threadsafe since we're in a thread
                        emit_result = self.event_bus.emit('vr.tracking.update', tracking_data)
                        if asyncio.iscoroutine(emit_result):
                            try:
                                loop = asyncio.get_running_loop()
                                asyncio.run_coroutine_threadsafe(emit_result, loop)
                            except RuntimeError:
                                # No running loop in this thread, skip event emission
                                pass
                    except Exception:
                        pass
                
                time.sleep(1/90)  # 90 FPS tracking rate
                
            except Exception as e:
                logger.error(f"Error in VR tracking thread: {e}")
                time.sleep(0.1)
    
    def stop_vr_session(self) -> bool:
        """Stop the current VR session."""
        try:
            self.vr_session_active = False
            
            import openvr
            openvr.shutdown()
            
            logger.info("VR session stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping VR session: {e}")
            return False
    
    # =========================================================================
    # SOTA 2026: Chat/Voice Command Handlers
    # =========================================================================
    
    def _handle_vr_start(self, payload):
        """Handle VR start command from chat/voice."""
        logger.info("🥽 Starting VR system via chat command")
        self.is_running = True
        if self.event_bus:
            self.event_bus.publish('vr.started', {'status': 'running'})
    
    def _handle_vr_stop(self, payload):
        """Handle VR stop command from chat/voice."""
        logger.info("🥽 Stopping VR system via chat command")
        self.is_running = False
        if self.event_bus:
            self.event_bus.publish('vr.stopped', {'status': 'stopped'})
    
    def _handle_vr_status(self, payload):
        """Handle VR status request from chat/voice."""
        status = {
            'is_running': self.is_running,
            'connected': self.connected,
            'devices': list(self.devices.keys()),
            'environment': self.environment
        }
        if self.event_bus:
            self.event_bus.publish('vr.status.response', status)
    
    def _handle_vr_calibrate(self, payload):
        """Handle VR calibration command."""
        logger.info("🎯 Calibrating VR system via chat command")
        self.head_position = [0, 0, 0]
        self.head_rotation = [0, 0, 0]
        if self.event_bus:
            self.event_bus.publish('vr.calibrated', {'status': 'calibrated'})
    
    def _handle_hands_enable(self, payload):
        """Handle hand tracking enable command."""
        logger.info("✋ Enabling hand tracking via chat command")
        self.track_motion = True
        if self.event_bus:
            self.event_bus.publish('vr.hands.enabled', {'tracking': True})
    
    def _handle_hands_disable(self, payload):
        """Handle hand tracking disable command."""
        logger.info("✋ Disabling hand tracking via chat command")
        self.track_motion = False
        if self.event_bus:
            self.event_bus.publish('vr.hands.disabled', {'tracking': False})
    
    def _handle_trading_open(self, payload):
        """Handle open VR trading floor command."""
        logger.info("📈 Opening VR trading floor via chat command")
        self.environment = "trading_floor"
        if self.event_bus:
            self.event_bus.publish('vr.trading.opened', {'environment': 'trading_floor'})
    
    # ========================================================================
    # SOTA 2026: Vision Stream Handlers for VR/AR Integration
    # ========================================================================
    
    def _on_vision_stream_frame(self, data):
        """Handle incoming vision frames from webcam for VR passthrough/AR.
        
        SOTA 2026: Forwards vision frames to connected VR devices (Meta glasses, Quest 3)
        for augmented reality overlays or passthrough video.
        """
        try:
            frame = data.get('frame')
            if frame is None:
                return
            
            timestamp = data.get('timestamp', time.time())
            source = data.get('source', 'webcam')
            
            # Track last frame for VR display
            self._last_vision_frame = frame
            self._last_vision_timestamp = timestamp
            
            # Forward to connected VR devices
            if self._connected and self._device_socket:
                try:
                    # Encode frame as JPEG for efficient transmission
                    import cv2
                    _, jpeg_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    
                    # Build VR vision packet
                    vision_packet = {
                        'type': 'vision_frame',
                        'source': source,
                        'timestamp': timestamp,
                        'frame_base64': base64.b64encode(jpeg_data.tobytes()).decode('utf-8'),
                    }
                    
                    # Send to VR device (non-blocking)
                    self._send_to_device_async(vision_packet)
                    
                except Exception as e:
                    logger.debug(f"Vision frame send error: {e}")
            
            # Also process with VL-JEPA if enabled (every 10th frame)
            if self._vl_jepa_enabled and hasattr(self, '_frame_count'):
                self._frame_count = getattr(self, '_frame_count', 0) + 1
                if self._frame_count % 10 == 0:
                    if self.event_bus:
                        self.event_bus.publish("vl_jepa.vision_frame", {
                            "frame": frame,
                            "timestamp": timestamp,
                            "source": "vr_passthrough"
                        })
                        
        except Exception as e:
            logger.debug(f"Vision stream frame handler error: {e}")
    
    def _on_visual_generated(self, data):
        """Handle visual generation output for VR display.
        
        SOTA 2026: Displays AI-generated images/videos in VR environment.
        """
        try:
            image_data = data.get('data') or data.get('image') or data.get('frame')
            image_path = data.get('image_path') or data.get('path') or data.get('file')
            video_path = data.get('video_path')
            if image_data is None and not image_path and not video_path:
                return
            
            output_type = data.get('type', 'image')
            prompt = data.get('prompt', '')
            
            logger.info(f"🎨 VR: Displaying generated {output_type} - {prompt[:50]}...")
            
            # Forward to VR devices for display
            if self._connected and self.event_bus:
                self.event_bus.publish('vr.display.content', {
                    'type': 'video' if video_path else output_type,
                    'data': image_data,
                    'image_path': image_path,
                    'video_path': video_path,
                    'prompt': prompt,
                    'source': 'visual_generation',
                })
                
        except Exception as e:
            logger.debug(f"Visual generated handler error: {e}")
    
    def _on_visual_display(self, data):
        """Handle visual display requests for VR.
        
        SOTA 2026: Routes visual content to VR headset display.
        """
        try:
            content_type = data.get('type', 'image')
            content_data = data.get('data')
            source = data.get('source', 'unknown')
            
            if content_data is None:
                return
            
            logger.debug(f"VR display request: {content_type} from {source}")
            
            # Forward to connected VR devices
            if self._connected and self._device_socket:
                display_packet = {
                    'type': 'display_content',
                    'content_type': content_type,
                    'data': content_data if isinstance(content_data, str) else None,
                    'source': source,
                }
                self._send_to_device_async(display_packet)
                
        except Exception as e:
            logger.debug(f"Visual display handler error: {e}")
    
    def _send_to_device_async(self, packet):
        """Send packet to VR device asynchronously (non-blocking)."""
        try:
            import json
            if self._device_socket:
                message = json.dumps(packet)
                # Use threading to avoid blocking the event loop
                import threading
                def send():
                    try:
                        self._device_socket.send(message.encode('utf-8'))
                    except Exception:
                        pass
                thread = threading.Thread(target=send, daemon=True)
                thread.start()
        except Exception:
            pass
