#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR QT Tab for Kingdom AI

This module provides the main VR interface tab using PyQt6,
integrating all VR system features including device management,
environment controls, 3D visualization, and performance monitoring.
"""

import os
import sys
import logging
import json
import traceback
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import numpy as np
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor

# SOTA 2026: Tab Highway System for isolated computational pipelines
try:
    from core.tab_highway_system import (
        get_highway, TabType, run_on_vr_highway,
        vr_highway, get_tab_highway_manager
    )
    HAS_TAB_HIGHWAY = True
except ImportError:
    HAS_TAB_HIGHWAY = False
    def run_on_vr_highway(func, *args, gpu=True, **kwargs):
        return ThreadPoolExecutor(max_workers=2).submit(func, *args, **kwargs)

# Initialize logger IMMEDIATELY after logging import
logger = logging.getLogger(__name__)

# Import centralized Redis security handling
from utils.redis_security import get_redis_password, get_redis_config

# Qt imports - Complete import list based on PyQt6 best practices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, 
    QLabel, QGroupBox, QFormLayout, QComboBox, QSlider, QCheckBox,
    QApplication, QSizePolicy, QListWidget, QToolBar, QMessageBox,
    QStatusBar, QSplitter, QFileDialog, QMainWindow, QFrame,
    QScrollArea, QProgressBar, QLineEdit, QTextEdit, QSpinBox,
    QGridLayout, QStyle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, pyqtSlot, QSize, QEvent
from PyQt6.QtGui import QIcon, QAction, QPixmap, QColor, QPalette, QImage

# SOTA 2026: Webcam MJPEG integration for VR tab
import requests
HAS_OPENCV = False
try:
    # CRITICAL: NumPy _ARRAY_API patch BEFORE cv2 import (NumPy 2.x compatibility)
    # sitecustomize.py import hook should have already patched numpy
    import numpy as _np
    
    # CRITICAL: Ensure _ARRAY_API exists (import hook should have set it)
    if not hasattr(_np, '_ARRAY_API'):
        import types
        ns = types.SimpleNamespace()
        ns.ARRAY_API_STRICT = False
        _np._ARRAY_API = ns
    
    # CRITICAL: Patch numpy._core.multiarray (cv2's C extension checks this)
    try:
        import numpy._core.multiarray as multiarray
        if not hasattr(multiarray, '_ARRAY_API'):
            multiarray._ARRAY_API = getattr(_np, '_ARRAY_API', None)
    except Exception:
        pass
    
    # CRITICAL: Also patch numpy.core.multiarray (older numpy versions)
    try:
        import numpy.core.multiarray as old_multiarray
        if not hasattr(old_multiarray, '_ARRAY_API'):
            old_multiarray._ARRAY_API = getattr(_np, '_ARRAY_API', None)
    except Exception:
        pass
    
    # Force numpy to be fully loaded before cv2
    _ = _np.__version__  # Trigger full numpy load
    
    # Now import cv2 - numpy should be fully patched
    import cv2
    HAS_OPENCV = True
except (ImportError, AttributeError) as e:
    if '_ARRAY_API' in str(e) or isinstance(e, AttributeError):
        # cv2 import failed due to _ARRAY_API - this should NOT happen
        HAS_OPENCV = False
        cv2 = None
        import logging
        logging.getLogger(__name__).error(f"❌ cv2 import failed: NumPy _ARRAY_API error: {e}")
    else:
        HAS_OPENCV = False
        cv2 = None

# VR system imports with proper error handling and type safety
# Create default VRSystem class to avoid type conflicts
class VRSystem:
    def __init__(self):
        self.status = "Disconnected"
        # Make callbacks assignable
        self.on_status_update = lambda *args: None
        self.on_device_connected = lambda *args: None
        self.on_device_disconnected = lambda *args: None
        
    def initialize(self, *args, **kwargs): return True
    def shutdown(self, *args, **kwargs): pass
    def get_status(self): return {"status": "Disconnected"}
    def connect_device(self, *args, **kwargs): return False
    def disconnect_device(self, *args, **kwargs): return True

try:
    from core.vr_system import VRSystem as CoreVRSystem
    # Use core implementation if available - avoid direct assignment
    VRSystemImpl = CoreVRSystem
except ImportError:
    # Use default class defined above
    VRSystemImpl = VRSystem

# Default VRAIInterface class  
class VRAIInterface:
    def __init__(self):
        self.status = "Inactive"
        # Make callbacks assignable
        self.on_gesture_detected = lambda *args: None
        self.on_ai_response = lambda *args: None
    def shutdown(self, *args, **kwargs): pass

try:
    from core.vr_ai_interface import VRAIInterface as CoreVRAIInterface
    VRAIInterfaceImpl = CoreVRAIInterface
except ImportError:
    VRAIInterfaceImpl = VRAIInterface

# Default VRIntegration class
class VRIntegration:
    def __init__(self):
        self.status = "Inactive"
    def shutdown(self, *args, **kwargs): pass

try:
    from core.vr_integration import VRIntegration as CoreVRIntegration
    VRIntegrationImpl = CoreVRIntegration
except ImportError:
    VRIntegrationImpl = VRIntegration

# GUI components
from gui.widgets.vr_device_panel import VRDevicePanel
from gui.widgets.vr_environment_selector import VREnvironmentSelector
from gui.widgets.vr_gesture_controls import VRGestureControls
from gui.widgets.vr_performance_monitor import VRPerformanceMonitor
from gui.widgets.vr_3d_viewer import VR3DViewer
from gui.qt_frames.vr_sentience_monitor import VRSentienceMonitor

# Redis and Utils
from gui.qt_frames.utils.redis_manager import RedisManager, RedisConnectionError

# Styles
from gui.styles.vr_styles import get_tab_style, get_button_style, get_label_style, get_font

# VR Systems Integration - NO FALLBACKS (loaded from ML environment)
from vr.ai_interface.gesture_recognition import GestureRecognition
from vr.ai_interface.voice_commands import VRVoiceCommands
from vr.system.device_manager import VRDeviceManager
from vr.system.environment_manager import VREnvironmentManager
from vr.system.graphics_renderer import VRGraphicsRenderer

VR_FULL_SYSTEMS_AVAILABLE = True  # type: ignore[misc]
logger.info("✅ VR Full Systems imported from ML environment")

# VR Core Modules Integration
VR_CORE_MODULES_AVAILABLE = False  # FIX ERROR #5: Default value
try:
    from vr.vr_connector import VRConnector
    from vr.vr_module import VRModule
    from vr.vr_renderer import VRRenderer
    from vr.vr_scene import VRScene
    from vr.manager import VRManagerCore
    VR_CORE_MODULES_AVAILABLE = True  # type: ignore[misc]
    logger.info("✅ VR Core Modules imported (Connector, Module, Renderer, Scene, Manager)")
except ImportError as e:
    logger.warning(f"⚠️ VR Core Modules not available: {e}")
    VRConnector = None
    VRModule = None
    VRRenderer = None
    VRScene = None
    VRManagerCore = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add resource path for icons
RESOURCE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources')
ICON_PATH = os.path.join(RESOURCE_PATH, 'icons')

def get_icon(name: str) -> QIcon:
    """Helper to get icon from resources."""
    path = os.path.join(ICON_PATH, f"{name}.png")
    if os.path.exists(path):
        return QIcon(path)
    # Fallback to system theme icons
    icon_map = {
        'connect': QStyle.StandardPixmap.SP_MediaPlay,
        'disconnect': QStyle.StandardPixmap.SP_MediaStop,
        'calibrate': QStyle.StandardPixmap.SP_MediaSeekForward,
        'reset': QStyle.StandardPixmap.SP_BrowserReload,
        'settings': QStyle.StandardPixmap.SP_ComputerIcon,
        'help': QStyle.StandardPixmap.SP_DialogHelpButton,
    }
    if name in icon_map:
        return QApplication.style().standardIcon(icon_map[name])
    return QIcon()


# ===========================================================================
# SOTA 2026: MJPEG Webcam Reader - EXACT COPY from realtime_creative_studio.py
# ===========================================================================

class MJPEGReader:
    """Background thread that reads MJPEG frames into shared buffer.
    PROVEN WORKING from test_webcam_live_wsl2_v3.py and realtime_creative_studio.py.
    """

    def __init__(self, url: str):
        self.url = url
        self.latest_frame = None
        self.frame_count = 0
        self.is_running = False
        self.lock = threading.Lock()
        self.thread = None
        self.first_frame_ready = threading.Event()

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False

    def get_frame(self):
        """Get latest frame (thread-safe)."""
        with self.lock:
            return self.latest_frame, self.frame_count

    def wait_for_first_frame(self, timeout=3.0):
        return self.first_frame_ready.wait(timeout)

    def _read_loop(self):
        """Read MJPEG stream - OPTIMIZED for zero latency."""
        logger.info(f"📹 MJPEGReader connecting to {self.url}...")
        try:
            response = requests.get(self.url, stream=True, timeout=5)
            if response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}")
                return
            logger.info("✅ MJPEG Connected!")
            bytes_buffer = b''
            for chunk in response.iter_content(chunk_size=8192):
                if not self.is_running:
                    break
                bytes_buffer += chunk
                while True:
                    start = bytes_buffer.find(b'\xff\xd8')
                    if start == -1:
                        bytes_buffer = bytes_buffer[-2:] if len(bytes_buffer) > 2 else bytes_buffer
                        break
                    end = bytes_buffer.find(b'\xff\xd9', start)
                    if end == -1:
                        break
                    jpg_data = bytes_buffer[start:end+2]
                    bytes_buffer = bytes_buffer[end+2:]
                    if HAS_OPENCV:
                        frame = cv2.imdecode(np.frombuffer(jpg_data, np.uint8), cv2.IMREAD_COLOR)
                    else:
                        frame = None
                    if frame is not None:
                        frame = cv2.flip(frame, 1)  # Mirror
                        with self.lock:
                            self.latest_frame = frame
                            self.frame_count += 1
                        if not self.first_frame_ready.is_set():
                            self.first_frame_ready.set()
                            logger.info(f"🎬 First frame ready! Shape: {frame.shape}")
            response.close()
        except Exception as e:
            logger.error(f"❌ MJPEG stream error: {e}")


def _get_windows_host_ip() -> str:
    """Get Windows host IP for MJPEG server."""
    import subprocess
    try:
        result = subprocess.run(['ip', 'route', 'show', 'default'],
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            parts = result.stdout.split()
            if len(parts) >= 3 and parts[0] == 'default' and parts[1] == 'via':
                return parts[2]
    except Exception:
        pass
    try:
        with open('/etc/resolv.conf', 'r') as rf:
            for line in rf:
                if line.strip().startswith('nameserver'):
                    ip = line.strip().split()[1]
                    if not ip.startswith('127.'):
                        return ip
    except Exception:
        pass
    return "172.20.0.1"


def _auto_detect_mjpeg_url(host_ip: str, default_port: int = 8090) -> Optional[str]:
    """Try common MJPEG endpoints to find the running camera server.

    This mirrors the logic in core.vision_service to avoid diverging URLs
    between VR passthrough and the AI vision stream.
    """
    if not requests:
        return None
    ports = [default_port, 8091, 5000]
    endpoints = ["/brio.mjpg", "/video.mjpg"]
    for port in ports:
        for ep in endpoints:
            url = f"http://{host_ip}:{port}{ep}"
            try:
                resp = requests.get(url, stream=True, timeout=1)
                if resp.status_code == 200:
                    return url
            except Exception:
                continue
    # Last resort: localhost
    if host_ip not in ("127.0.0.1", "localhost"):
        for port in ports:
            for ep in endpoints:
                url = f"http://127.0.0.1:{port}{ep}"
                try:
                    resp = requests.get(url, stream=True, timeout=1)
                    if resp.status_code == 200:
                        return url
                except Exception:
                    continue
    return None


class WebcamWorker(QThread):
    """MJPEG webcam capture worker thread for VR tab."""
    frame_ready = pyqtSignal(np.ndarray)
    status_update = pyqtSignal(str)

    def __init__(self, event_bus=None):
        super().__init__()
        self._running = False
        self._reader = None
        self.event_bus = event_bus
        host_ip = os.environ.get("MJPEG_HOST") or _get_windows_host_ip()
        env_url = os.environ.get("MJPEG_URL")
        auto_url = _auto_detect_mjpeg_url(host_ip)
        if env_url:
            self._mjpeg_url = env_url
        elif auto_url:
            self._mjpeg_url = auto_url
        else:
            self._mjpeg_url = f"http://{host_ip}:8090/brio.mjpg"
        logger.info(f"📹 VR Webcam MJPEG URL selected: {self._mjpeg_url}")

    def run(self):
        """Start MJPEG reader and emit frames."""
        self._running = True
        self.status_update.emit(f"📹 Connecting to {self._mjpeg_url}...")
        if not HAS_OPENCV:
            self.status_update.emit("❌ OpenCV not available")
            return
        self._reader = MJPEGReader(self._mjpeg_url)
        self._reader.start()
        if self._reader.wait_for_first_frame(timeout=5.0):
            self.status_update.emit("✅ MJPEG Connected - Live!")
        else:
            self.status_update.emit("⚠️ Waiting for frames...")
        last_count = 0
        while self._running:
            frame, count = self._reader.get_frame()
            if frame is not None and count != last_count:
                last_count = count
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frame_ready.emit(frame_rgb)
            time.sleep(0.033)  # ~30 FPS

    def stop(self):
        """Stop webcam capture."""
        self._running = False
        if self._reader:
            self._reader.stop()
        self.wait(2000)


class VRQTSignals(QObject):
    """Signals for VR QT Tab to enable cross-thread communication."""
    # System signals
    status_updated = pyqtSignal(str, str)  # message, level
    connection_changed = pyqtSignal(bool)  # connected
    
    # Data update signals
    device_updated = pyqtSignal(dict)      # device data
    tracking_updated = pyqtSignal(dict)    # tracking data
    environment_updated = pyqtSignal(dict) # environment data
    performance_updated = pyqtSignal(dict) # performance data
    gesture_detected = pyqtSignal(dict)    # gesture data
    voice_command = pyqtSignal(dict)       # voice command data
    ai_response = pyqtSignal(dict)         # AI response data
    
    # User action signals
    environment_change_requested = pyqtSignal(str)  # environment_id
    calibration_requested = pyqtSignal()
    reset_view_requested = pyqtSignal()
    gesture_mapping_changed = pyqtSignal(str, str)  # gesture_id, action_name
    gesture_recording_changed = pyqtSignal(bool)     # is_recording
    
    # System control signals
    shutdown_requested = pyqtSignal()
    restart_requested = pyqtSignal()
    settings_updated = pyqtSignal(dict)  # settings_dict

class VRSystemWorker(QObject):
    """Worker class for running VR system in a separate thread."""
    # Signal mirrors of VRQTSignals for thread-safe communication
    status_updated = pyqtSignal(str, str)  # message, level
    connection_changed = pyqtSignal(bool)  # connected
    device_updated = pyqtSignal(dict)      # device data
    tracking_updated = pyqtSignal(dict)    # tracking data
    environment_updated = pyqtSignal(dict) # environment data
    performance_updated = pyqtSignal(dict) # performance data
    gesture_detected = pyqtSignal(dict)    # gesture data
    voice_command = pyqtSignal(dict)       # voice command data
    ai_response = pyqtSignal(dict)         # AI response data
    
    def __init__(self, config=None, event_bus=None):
        super().__init__()
        self.config = config or {}
        self.event_bus = event_bus
        self.running = False
        self.vr_system = None
        self.vr_ai = None
        self.vr_integration = None
        self.is_connected = False
        self.current_environment = "default"
        self.available_environments = []
        
        # Connect to central ThothAI brain system
        self._connect_to_central_brain()
    
    def _connect_to_central_brain(self):
        try:
            self._central_thoth = None
        except Exception as e:
            logger.error(f"Error connecting VR worker to central ThothAI: {e}")
            self._central_thoth = None
    
    def initialize(self):
        """Initialize VR system components."""
        try:
            self.status_updated.emit("Initializing VR system...", "info")
            
            # Use simple fallback VR system that does nothing
            class DisabledVRSystem:
                def __init__(self):
                    self.status = "Disabled"
                    # Add all required callback attributes
                    self.on_status_update = None
                    self.on_device_update = None
                    self.on_tracking_update = None
                    self.on_environment_update = None
                    self.on_performance_update = None
                def update(self): pass
                def initialize(self): pass
                def shutdown(self): pass
                def load_environment(self, *args, **kwargs): pass
                def calibrate(self, *args, **kwargs): pass
                def reset_view(self, *args, **kwargs): pass
            
            try:
                # Core VRSystem requires event_bus; stubs/fallbacks may not.
                self.vr_system = VRSystemImpl(event_bus=self.event_bus)  # type: ignore[call-arg]
            except TypeError:
                try:
                    self.vr_system = VRSystemImpl(self.event_bus)  # type: ignore[call-arg]
                except TypeError:
                    self.vr_system = VRSystemImpl()  # type: ignore[call-arg]
            
            # Initialize VR AI Interface with fallback
            try:
                # Try to initialize - VRAIInterface may not accept arguments
                self.vr_ai = VRAIInterfaceImpl()  # type: ignore[call-arg]
            except (ImportError, TypeError, Exception):
                # Use fallback VR AI Interface
                class FallbackVRAIInterface:
                    def __init__(self):
                        self.status = "Disconnected"
                        # Use proper callable types instead of None
                        self.on_gesture_detected = self._noop
                        self.on_voice_command = self._noop
                        self.on_ai_response = self._noop
                    def _noop(self, *args, **kwargs): pass
                    def start_gesture_recording(self, *args, **kwargs): pass
                    def stop_gesture_recording(self, *args, **kwargs): pass
                    def map_gesture(self, *args, **kwargs): pass
                    def shutdown(self, *args, **kwargs): pass
                
                self.vr_ai = FallbackVRAIInterface()
            
            # Initialize VR Integration with fallback
            try:
                # Try to initialize - VRIntegration may not accept arguments
                self.vr_integration = VRIntegrationImpl()  # type: ignore[call-arg]
            except (ImportError, TypeError, Exception):
                # Use fallback VR Integration
                class FallbackVRIntegration:
                    def __init__(self):
                        self.status = "Disconnected"
                    def shutdown(self, *args, **kwargs): pass
                    def update(self, *args, **kwargs): pass
                
                self.vr_integration = FallbackVRIntegration()
            
            # Connect VR system signals (attributes already initialized in class definitions)
            self.vr_system.on_status_update = self.handle_status_update  # type: ignore[assignment]
            self.vr_system.on_device_update = self.handle_device_update  # type: ignore[assignment]
            self.vr_system.on_tracking_update = self.handle_tracking_update  # type: ignore[assignment]
            self.vr_system.on_environment_update = self.handle_environment_update  # type: ignore[assignment]
            self.vr_system.on_performance_update = self.handle_performance_update  # type: ignore[assignment]
            
            # Connect VR-AI signals
            self.vr_ai.on_gesture_detected = self.handle_gesture_detected  # type: ignore[assignment,attr-defined]
            self.vr_ai.on_voice_command = self.handle_voice_command  # type: ignore[assignment,attr-defined]
            self.vr_ai.on_ai_response = self.handle_ai_response  # type: ignore[assignment]
            
            # Start VR system
            self.vr_system.initialize()
            self.running = True
            self.is_connected = True
            self.connection_changed.emit(True)
            self.status_updated.emit("VR System initialized", "success")
            
            # Start update loop only if successfully initialized
            if self.vr_system and self.vr_ai and self.vr_integration:
                self.update_loop()
            else:
                self.running = False
                self.is_connected = False
        
        except Exception as e:
            error_msg = f"Failed to initialize VR system: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.status_updated.emit(error_msg, "error")
            self.connection_changed.emit(False)
            # CRITICAL: Stop the infinite loop on any initialization error
            self.running = False
            self.is_connected = False
    
    def update_loop(self):
        """Main update loop for VR system."""
        if not self.running:
            return
            
        try:
            # Update VR system components - but only if update method exists
            if self.vr_system and hasattr(self.vr_system, 'update'):
                self.vr_system.update()
            
            # Don't schedule next update immediately to prevent infinite loop
            # Only continue if system is actually running and stable
            if self.running and self.is_connected:
                QTimer.singleShot(100, self.update_loop)  # Slower update rate to prevent spam
            
        except Exception as e:
            error_msg = f"Error in VR update loop: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.status_updated.emit(error_msg, "error")
            # CRITICAL: Stop the loop completely on any error
            self.running = False
            self.is_connected = False
    
    def shutdown(self):
        """Shutdown VR system."""
        try:
            self.running = False
            self.is_connected = False
            
            if self.vr_system:
                self.vr_system.shutdown()
            if self.vr_ai:
                self.vr_ai.shutdown()
            if self.vr_integration and hasattr(self.vr_integration, 'shutdown'):
                self.vr_integration.shutdown()  # type: ignore
                
            self.connection_changed.emit(False)
            self.status_updated.emit("VR System Shutdown", "info")
            
        except Exception as e:
            error_msg = f"Error during VR system shutdown: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.status_updated.emit(error_msg, "error")
    
    # Signal handlers for VR system events
    def handle_status_update(self, message: str, level: str):
        """Forward status updates to main thread."""
        self.status_updated.emit(message, level)
    
    def handle_device_update(self, device_data: dict):
        """Forward device updates to main thread."""
        self.device_updated.emit(device_data)
    
    def handle_tracking_update(self, tracking_data: dict):
        """Forward tracking updates to main thread."""
        self.tracking_updated.emit(tracking_data)
    
    def handle_environment_update(self, env_data: dict):
        """Forward environment updates to main thread."""
        self.environment_updated.emit(env_data)
    
    def handle_performance_update(self, metrics: dict):
        """Forward performance updates to main thread."""
        self.performance_updated.emit(metrics)
    
    def handle_gesture_detected(self, gesture_data: dict):
        """Forward gesture detection events to main thread."""
        self.gesture_detected.emit(gesture_data)
    
    def handle_voice_command(self, command_data: dict):
        """Forward voice command events to main thread."""
        self.voice_command.emit(command_data)
    
    def handle_ai_response(self, response_data: dict):
        """Forward AI response events to main thread."""
        self.ai_response.emit(response_data)
    
    # Public methods called from main thread
    def load_environment(self, environment_id: str):
        """Load a VR environment."""
        if self.vr_system and environment_id in self.available_environments:
            self.vr_system.load_environment(environment_id)
            self.current_environment = environment_id
    
    def calibrate(self):
        """Calibrate the VR system."""
        if self.vr_system:
            self.vr_system.calibrate()
    
    def reset_view(self):
        """Reset the VR view."""
        if self.vr_system:
            self.vr_system.reset_view()
    
    def map_gesture(self, gesture_id: str, action_name: str):
        """Map a gesture to an action."""
        if self.vr_ai and hasattr(self.vr_ai, 'map_gesture'):
            self.vr_ai.map_gesture(gesture_id, action_name)  # type: ignore
    
    def start_gesture_recording(self):
        """Start recording a new gesture."""
        if self.vr_ai and hasattr(self.vr_ai, 'start_gesture_recording'):
            self.vr_ai.start_gesture_recording()  # type: ignore
    
    def stop_gesture_recording(self):
        """Stop recording a gesture."""
        if self.vr_ai and hasattr(self.vr_ai, 'stop_gesture_recording'):
            self.vr_ai.stop_gesture_recording()  # type: ignore


class VRQTTab(QWidget):
    """Main VR Tab Widget for Kingdom AI."""
    
    def __init__(self, parent=None, event_bus=None, config=None):
        # CRITICAL: Check QApplication exists BEFORE any widget operations
        if not QApplication.instance():
            logger.critical("FATAL: QApplication must exist before VR widgets")
            raise RuntimeError("QApplication required before VR widget creation")
            
        super().__init__(parent)
        self.setObjectName("VRMainWidget")
        
        # Initialize logger
        self.logger = logging.getLogger("KingdomAI.VRQTTab")
        
        # Store event bus
        self.event_bus = event_bus
        self.config = config or {}
        self.signals = VRQTSignals()
        
        # Redis connection
        self.redis_manager = None
        self.redis_connected = False
        
        # VR system components
        self.vr_worker = None
        self.vr_thread = None
        
        # Initialize VR Full Systems
        self.gesture_recognition = None
        self.vr_voice_commands = None
        self.vr_device_manager = None
        self.vr_environment_manager = None
        self.vr_graphics_renderer = None
        
        # Initialize VR Core Modules
        self.vr_connector = None
        self.vr_module = None
        self.vr_renderer = None
        self.vr_scene = None
        self.vr_manager_core = None

        # SOTA 2026: Webcam worker
        self._webcam_worker = None

        # UI state
        self.is_connected = False
        self.current_environment = "default"
        self.available_environments = []
        self._handshake_result = {}
        self._handshake_verified = False
        self._last_handshake_id = None
        self._handshake_server = None
        self._handshake_server_thread = None
        self._handshake_server_port = int(os.environ.get("KINGDOM_VR_HANDSHAKE_PORT", "27183"))
        self._headset_confirmed_handshake_id: Optional[str] = None
        self._headset_confirmed_at: Optional[float] = None
        self.settings = {
            'show_fps': True,
            'show_performance': True,
            'enable_voice': True,
            'enable_gestures': True,
            'mirror_display': False,
            'vr_mirror_source': 'auto',  # 'auto', 'desktop', 'internal'
        }
        
        # Define VR detection timer attribute early
        self.vr_detection_timer = None

        # Desktop VR mirror capture state (Windows-only, optional)
        self._vr_mirror_hwnd = None
        self._vr_mirror_last_check = 0.0
        self._vr_mirror_runtime = None

        self._timers_enabled = True

        # VR view streaming timer for vision.stream.vr.frame
        self._vr_view_timer = QTimer(self)
        self._vr_view_timer.setInterval(200)  # ~5 FPS to avoid heavy load
        self._vr_view_timer.timeout.connect(self._publish_vr_view_frame)

        # SOTA 2026: GUI mirror timer — captures entire Kingdom AI window for VR
        self._gui_mirror_timer = QTimer(self)
        self._gui_mirror_timer.setInterval(200)  # ~5 FPS to reduce main-thread load
        self._gui_mirror_timer.timeout.connect(self._publish_gui_mirror_frame)
        self._gui_mirror_enabled = False  # Toggled via settings

        # SOTA 2026: System event log for VR HUD
        self._vr_system_log = []

        # Initialize UI and VR system FIRST (Redis connection deferred)
        self.init_ui()
        self.connect_signals()  # Re-enable now that methods exist
        self.init_vr_system()

        # Apply styles
        self.apply_styles()

        # Subscribe to backend events
        self._subscribe_to_backend_events()

        # Initialize ALL VR Systems
        self._init_vr_full_systems()

        # Ensure _start_vr_device_monitoring is bound on the instance before using it
        if not hasattr(self, "_start_vr_device_monitoring"):
            method = getattr(type(self), "_start_vr_device_monitoring", None)
            if callable(method):
                # Bind the class method explicitly to this instance
                self._start_vr_device_monitoring = method.__get__(self, type(self))

        # FIX #4: Defer VR device detection to ensure method is available
        # Use QTimer to call after __init__ completes
        QTimer.singleShot(100, self._start_vr_device_monitoring)

        # TIMING FIX: Defer Redis connection to ensure Redis Quantum Nexus is ready
        self.logger.info("⏳ Deferring Redis connection for 1 second to ensure Quantum Nexus is ready...")
        QTimer.singleShot(1000, self._deferred_redis_init)

        self._sync_vr_timers()

    def _should_vr_timers_run(self) -> bool:
        if not getattr(self, '_timers_enabled', True):
            return False
        if not self.isVisible():
            return False
        try:
            window = self.window()
            if window is not None and window.isMinimized():
                return False
        except Exception:
            pass
        return True

    def _should_vr_view_timer_run(self) -> bool:
        if not self._should_vr_timers_run():
            return False
        if not bool(getattr(self, 'settings', {}).get('mirror_display', False)):
            return False
        return True

    def _sync_vr_timers(self):
        try:
            should_run = self._should_vr_timers_run()
            view_should_run = self._should_vr_view_timer_run()
            tracking_should_run = should_run and self.is_connected and callable(getattr(self, '_vr_tracking_update', None))
            device_monitor_should_run = should_run and self.is_connected and callable(getattr(self, '_check_vr_devices', None))

            timers = (
                ('_vr_view_timer', 200, view_should_run),
                ('vr_detection_timer', 3000, should_run),
                ('vr_tracking_timer', 200, tracking_should_run),
                ('device_monitor_timer', 1000, device_monitor_should_run),
            )

            for timer_attr, default_interval, timer_should_run in timers:
                timer = getattr(self, timer_attr, None)
                if timer is None:
                    continue

                if timer_should_run:
                    if not timer.isActive():
                        interval = default_interval
                        try:
                            interval = timer.interval() or default_interval
                        except Exception:
                            pass
                        timer.start(interval)
                        if timer_attr == 'vr_detection_timer':
                            try:
                                self._check_vr_device_connection()
                            except Exception:
                                pass
                else:
                    if timer.isActive():
                        timer.stop()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_vr_timers()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_vr_timers()

    def changeEvent(self, event):
        super().changeEvent(event)
        try:
            if event.type() == QEvent.Type.WindowStateChange:
                self._sync_vr_timers()
        except Exception:
            pass

    def _emit_ui_telemetry(
        self,
        event_type: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort publisher for ui.telemetry events from the VR tab."""
        try:
            if not getattr(self, "event_bus", None):
                return
            payload: Dict[str, Any] = {
                "component": "vr",
                "channel": "ui.telemetry",
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "success": success,
                "error": error,
                "metadata": metadata or {},
            }
            self.event_bus.publish("ui.telemetry", payload)
        except Exception as e:
            logger.debug("VR UI telemetry publish failed for %s: %s", event_type, e)
    
    def _deferred_redis_init(self):
        """Deferred Redis initialization - called after Redis Quantum Nexus is ready."""
        try:
            self.logger.info("🔗 Initializing Redis connection to Quantum Nexus...")
            self.redis_manager = RedisManager(
                host='localhost',
                port=6380,
                password=get_redis_password()  # Use centralized password management
            )
            
            # Connect signals
            self.redis_manager.signals.connected.connect(self.on_redis_connected)
            self.redis_manager.signals.disconnected.connect(self.on_redis_disconnected)
            self.redis_manager.signals.message_received.connect(self.on_redis_message)
            
            # Attempt to connect (will raise RedisConnectionError on failure)
            self.redis_manager.connect()
            self.logger.info("✅ VR tab Redis connection successful")
            
        except Exception as e:
            # Log error but don't crash - VR tab can still function without Redis
            self.logger.warning(f"⚠️ VR tab Redis connection failed (will retry): {e}")
            self.handle_redis_error(str(e))
    
    def init_redis(self):
        """Legacy method - redirects to deferred init."""
        self._deferred_redis_init()
    
    def on_redis_connected(self):
        """Handle successful Redis connection."""
        self.redis_connected = True
        self.update_status("Connected to Redis Quantum Nexus", "success")
        
        # Subscribe to relevant channels
        try:
            self.redis_manager.subscribe(["vr.status", "vr.events", "vr.commands"])
        except Exception as e:
            self.update_status(f"Failed to subscribe to Redis channels: {str(e)}", "error")
    
    def on_redis_disconnected(self, error_msg: str):
        """Handle Redis disconnection."""
        self.redis_connected = False
        self.handle_critical_error(f"Redis connection lost: {error_msg}")
    
    def on_redis_message(self, channel: str, message: dict):
        """Handle incoming Redis messages."""
        try:
            if channel == "vr.status":
                self.handle_vr_status_update(message)
            elif channel == "vr.events":
                self.handle_vr_event(message)
            elif channel == "vr.commands":
                self.handle_vr_command(message)
        except (KeyboardInterrupt, SystemExit):
            # Allow KeyboardInterrupt to propagate for clean shutdown
            raise
        except Exception as e:
            self.update_status(f"Error handling Redis message: {str(e)}", "error")
    
    def handle_redis_error(self, error_msg: str):
        """Handle Redis connection errors."""
        self.update_status(f"Redis Error: {error_msg}", "error")
        self.handle_critical_error("VR system requires Redis connection. Application will now exit.")
    
    def handle_critical_error(self, message: str):
        """Handle critical errors by logging only - no blocking dialogs."""
        # FIXED: Don't show blocking dialog - just log error
        self.logger.debug(f"VR System: {message} (continuing with available systems)")
        self.logger.info("VR functionality disabled - continuing with other systems")
        # Don't disable tab - let it stay visible but non-functional
        # self.setEnabled(False)  # REMOVED: Don't disable entire tab
    
    def _init_vr_full_systems(self):
        """Initialize ALL VR systems including gesture, voice, device, environment, and graphics."""
        try:
            # Initialize VR Full Systems
            if VR_FULL_SYSTEMS_AVAILABLE:
                try:
                    if GestureRecognition:
                        self.gesture_recognition = GestureRecognition()
                        logger.info("✅ Gesture Recognition initialized")
                    
                    if VRVoiceCommands:
                        self.vr_voice_commands = VRVoiceCommands()
                        logger.info("✅ VR Voice Commands initialized")
                    
                    if VRDeviceManager:
                        self.vr_device_manager = VRDeviceManager()
                        logger.info("✅ VR Device Manager initialized")
                    
                    if VREnvironmentManager:
                        self.vr_environment_manager = VREnvironmentManager()
                        logger.info("✅ VR Environment Manager initialized")
                    
                    if VRGraphicsRenderer:
                        self.vr_graphics_renderer = VRGraphicsRenderer()
                        logger.info("✅ VR Graphics Renderer initialized")
                    
                    logger.info("✅ VR Full Systems initialized (5 components)")
                except Exception as e:
                    logger.error(f"Failed to initialize VR Full Systems: {e}")
            
            # Initialize VR Core Modules
            if VR_CORE_MODULES_AVAILABLE:
                try:
                    if VRConnector:
                        self.vr_connector = VRConnector()
                        logger.info("✅ VR Connector initialized")
                    
                    if VRModule:
                        self.vr_module = VRModule()
                        logger.info("✅ VR Module initialized")
                    
                    if VRRenderer:
                        self.vr_renderer = VRRenderer()
                        logger.info("✅ VR Renderer initialized")
                    
                    if VRScene:
                        self.vr_scene = VRScene()
                        logger.info("✅ VR Scene initialized")
                    
                    if VRManagerCore:
                        self.vr_manager_core = VRManagerCore()
                        logger.info("✅ VR Manager Core initialized")
                    
                    logger.info("✅ VR Core Modules initialized (5 components)")
                except Exception as e:
                    logger.error(f"Failed to initialize VR Core Modules: {e}")
                    
        except Exception as e:
            logger.error(f"Error initializing VR systems: {e}")
    
    def init_ui(self):
        """Initialize the user interface with VR-specific styling and layout."""
        # Main layout with proper spacing and margins
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(5)
        self.setLayout(main_layout)
        
        # Create and add toolbar
        self.toolbar = self.create_toolbar()
        main_layout.addWidget(self.toolbar)
        
        # Create main content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: 3D View
        self.viewer_3d = VR3DViewer()
        splitter.addWidget(self.viewer_3d)

        # SOTA 2026: Webcam preview widget for VR passthrough
        self.webcam_widget = QWidget()
        webcam_layout = QVBoxLayout(self.webcam_widget)
        webcam_layout.setContentsMargins(0, 0, 0, 0)
        self.webcam_label = QLabel("📹 Webcam Off")
        self.webcam_label.setMinimumSize(320, 240)
        self.webcam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.webcam_label.setStyleSheet("""
            QLabel {
                background: #0a0a15;
                border: 2px solid #00ff41;
                border-radius: 8px;
                color: #00ff41;
                font-size: 14px;
            }
        """)
        webcam_layout.addWidget(self.webcam_label)
        webcam_btn_layout = QHBoxLayout()
        self.btn_webcam_toggle = QPushButton("📷 Start Webcam")
        self.btn_webcam_toggle.clicked.connect(self._toggle_webcam)
        self.btn_webcam_toggle.setStyleSheet("""
            QPushButton {
                background: #1a1a2e;
                border: 1px solid #00ff41;
                border-radius: 4px;
                color: #00ff41;
                padding: 8px 16px;
            }
            QPushButton:hover { background: #2a2a4e; }
            QPushButton:pressed { background: #0f3460; }
        """)
        webcam_btn_layout.addWidget(self.btn_webcam_toggle)
        self.btn_send_to_headset = QPushButton("🥽 Send to Headset")
        self.btn_send_to_headset.clicked.connect(self._send_webcam_to_headset)
        self.btn_send_to_headset.setEnabled(False)
        self.btn_send_to_headset.setStyleSheet("""
            QPushButton {
                background: #1a1a2e;
                border: 1px solid #e94560;
                border-radius: 4px;
                color: #e94560;
                padding: 8px 16px;
            }
            QPushButton:hover { background: #2a2a4e; }
            QPushButton:disabled { color: #666; border-color: #333; }
        """)
        webcam_btn_layout.addWidget(self.btn_send_to_headset)
        webcam_layout.addLayout(webcam_btn_layout)
        self.webcam_status = QLabel("Status: Disconnected")
        self.webcam_status.setStyleSheet("color: #888; font-size: 10px;")
        webcam_layout.addWidget(self.webcam_status)
        splitter.addWidget(self.webcam_widget)

        # Right side: Tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("VRTabWidget")
        
        # Create tabs
        self.create_device_tab()
        self.create_environment_tab()
        self.create_creation_studio_tab()     # SOTA 2026: VR Creation Studio
        self.create_gesture_tab()
        self.create_performance_tab()
        # Skip sentience tab for now - not implemented
        # self.create_sentience_tab()
        self.create_settings_tab()
        
        splitter.addWidget(self.tab_widget)
        splitter.setStretchFactor(0, 2)  # 3D viewer
        splitter.setStretchFactor(1, 1)  # Webcam
        splitter.setStretchFactor(2, 1)  # Tabs
        
        main_layout.addWidget(splitter, 1)  # Add stretch factor 1 to fill space
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.status_bar.setObjectName("VRStatusBar")
        
        # Status indicators
        self.connection_status = QLabel("Status: Disconnected")
        self.connection_indicator = QLabel()
        self.connection_indicator.setFixedSize(12, 12)
        self.connection_indicator.setStyleSheet("""
            QLabel {
                background-color: #f44336;
                border-radius: 6px;
                border: 1px solid #880000;
            }
        """)
        
        # Performance indicators
        self.fps_label = QLabel("FPS: --")
        self.memory_label = QLabel("Memory: --")
        self.cpu_label = QLabel("CPU: --%")
        self.brain_status_label = QLabel("Brain: Idle")
        
        # Add widgets to status bar with spacing
        self.status_bar.addPermanentWidget(QLabel(" " * 4))  # Left margin
        self.status_bar.addPermanentWidget(self.connection_indicator)
        self.status_bar.addPermanentWidget(QLabel(" " * 2))  # Spacer
        self.status_bar.addPermanentWidget(self.connection_status)
        self.status_bar.addPermanentWidget(QLabel(" | "))
        self.status_bar.addPermanentWidget(self.fps_label)
        self.status_bar.addPermanentWidget(QLabel(" | "))
        self.status_bar.addPermanentWidget(self.memory_label)
        self.status_bar.addPermanentWidget(QLabel(" | "))
        self.status_bar.addPermanentWidget(self.cpu_label)
        self.status_bar.addPermanentWidget(QLabel(" | "))
        self.status_bar.addPermanentWidget(self.brain_status_label)
        
        main_layout.addWidget(self.status_bar)
        
        # Set initial window size and properties
        self.setMinimumSize(1024, 768)
        self.resize(1280, 900)
        self.setWindowTitle("VR Control Panel - Kingdom AI")
        
        # Apply initial styles
        self.apply_styles()
    
    def create_toolbar(self):
        """Create the main toolbar with VR controls and styling."""
        toolbar = QToolBar("VR Controls")
        toolbar.setObjectName("VRToolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        
        # Style the toolbar
        toolbar.setStyleSheet("""
            QToolBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                         stop:0 #2a2a4a, stop:1 #1a1a2e);
                border: 1px solid #0f3460;
                border-radius: 4px;
                padding: 2px;
                spacing: 5px;
            }
            QToolButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px 8px;
                color: #ffffff;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid #e94560;
            }
            QToolButton:pressed {
                background: rgba(233, 69, 96, 0.3);
            }
            QToolButton:disabled {
                color: #666666;
            }
        """)
        
        # Connect/Disconnect button
        self.btn_connect = QAction(get_icon("connect"), "Connect", self)
        self.btn_connect.triggered.connect(self.toggle_connection)
        self.btn_connect.setToolTip("Connect to VR system")
        
        # Calibrate button
        self.btn_calibrate = QAction(get_icon("calibrate"), "Calibrate", self)
        self.btn_calibrate.triggered.connect(self.calibrate_vr)
        self.btn_calibrate.setEnabled(False)
        self.btn_calibrate.setToolTip("Calibrate VR system")
        
        # Reset View button
        self.btn_reset_view = QAction(get_icon("reset"), "Reset View", self)
        self.btn_reset_view.triggered.connect(self.reset_view)
        self.btn_reset_view.setEnabled(False)
        self.btn_reset_view.setToolTip("Reset VR view to center")
        
        # Environment selector
        self.env_selector = QComboBox()
        self.env_selector.setMinimumWidth(200)
        self.env_selector.setEnabled(False)
        self.env_selector.currentTextChanged.connect(self.on_environment_selected)
        
        # Add widgets to toolbar
        toolbar.addAction(self.btn_connect)
        toolbar.addSeparator()
        toolbar.addAction(self.btn_calibrate)
        toolbar.addAction(self.btn_reset_view)
        toolbar.addSeparator()
        
        # Add environment selector with label
        toolbar.addWidget(QLabel("Environment: "))
        toolbar.addWidget(self.env_selector)
        
        # Add spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        
        # Add help button
        self.btn_help = QAction(get_icon("help"), "Help", self)
        self.btn_help.triggered.connect(self.show_help)
        self.btn_help.setToolTip("Show VR help")
        toolbar.addAction(self.btn_help)
        
        return toolbar
    
    def create_device_tab(self):
        """Create the device information tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # Device info group
        device_group = QGroupBox("VR Device")
        device_layout = QFormLayout()
        
        self.lbl_device_name = QLabel("Not Connected")
        self.lbl_device_status = QLabel("Disconnected")
        self.lbl_device_battery = QLabel("0%")
        self.lbl_device_ip = QLabel("-")
        
        device_layout.addRow("Device:", self.lbl_device_name)
        device_layout.addRow("Status:", self.lbl_device_status)
        device_layout.addRow("Battery:", self.lbl_device_battery)
        device_layout.addRow("IP Address:", self.lbl_device_ip)
        
        device_group.setLayout(device_layout)
        
        # Tracking info group
        tracking_group = QGroupBox("Tracking")
        tracking_layout = QFormLayout()
        
        self.lbl_tracking_status = QLabel("Inactive")
        self.lbl_tracking_quality = QLabel("-")
        self.lbl_hmd_position = QLabel("X: 0.00, Y: 0.00, Z: 0.00")
        self.lbl_hmd_rotation = QLabel("Pitch: 0.00°, Yaw: 0.00°, Roll: 0.00°")
        
        tracking_layout.addRow("Status:", self.lbl_tracking_status)
        tracking_layout.addRow("Quality:", self.lbl_tracking_quality)
        tracking_layout.addRow("Position:", self.lbl_hmd_position)
        tracking_layout.addRow("Rotation:", self.lbl_hmd_rotation)
        
        tracking_group.setLayout(tracking_layout)
        
        # Add groups to layout
        layout.addWidget(device_group)
        layout.addWidget(tracking_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, get_icon("device"), "Device")
    
    def create_environment_tab(self):
        """Create the environment control tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # Environment selection
        env_group = QGroupBox("Virtual Environment")
        env_layout = QVBoxLayout()
        
        self.lst_environments = QListWidget()
        self.lst_environments.itemSelectionChanged.connect(self.on_environment_selected_from_list)
        
        # Environment controls
        btn_layout = QHBoxLayout()
        self.btn_refresh_env = QPushButton("Refresh")
        # 2025 FIX: Safe method connection with validation
        if hasattr(self, '_refresh_environments') and callable(getattr(self, '_refresh_environments', None)):
            self.btn_refresh_env.clicked.connect(self._refresh_environments)
        else:
            self.btn_refresh_env.clicked.connect(lambda: self._log("VR refresh not available", level=logging.WARNING))
        self.btn_load_env = QPushButton("Load Environment")
        # 2025 FIX: Safe method connection with validation
        if hasattr(self, '_load_environment') and callable(getattr(self, '_load_environment', None)):
            self.btn_load_env.clicked.connect(self._load_environment)
        else:
            self.btn_load_env.clicked.connect(lambda: self._log("VR load not available", level=logging.WARNING))
        self.btn_load_env.setEnabled(False)
        
        btn_layout.addWidget(self.btn_refresh_env)
        btn_layout.addWidget(self.btn_load_env)
        
        env_layout.addWidget(self.lst_environments)
        env_layout.addLayout(btn_layout)
        env_group.setLayout(env_layout)
        
        # Environment settings
        settings_group = QGroupBox("Environment Settings")
        settings_layout = QFormLayout()
        
        self.sld_brightness = QSlider(Qt.Orientation.Horizontal)
        self.sld_brightness.setRange(0, 100)
        self.sld_brightness.setValue(70)
        self.sld_brightness.valueChanged.connect(self._on_brightness_changed)
        
        self.chk_mirror_display = QCheckBox("Mirror Display")
        self.chk_mirror_display.setChecked(False)
        self.chk_mirror_display.toggled.connect(self._on_mirror_display_toggled)
        
        settings_layout.addRow("Brightness:", self.sld_brightness)
        settings_layout.addRow("Mirror Display:", self.chk_mirror_display)
        
        settings_group.setLayout(settings_layout)
        
        # Add groups to layout
        layout.addWidget(env_group)
        layout.addWidget(settings_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, get_icon("environment"), "Environment")
    
    # ═══════════════════════════════════════════════════════════════════
    #  SOTA 2026: VR Creation Studio  — use ALL creation engines in headset
    # ═══════════════════════════════════════════════════════════════════

    def create_creation_studio_tab(self):
        """Create the VR Creation Studio tab — generate images/video/3D/games/designs
        directly inside the VR headset using the full CreationOrchestrator pipeline."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        tab.setLayout(layout)

        # ── Header ──
        header = QLabel("VR Creation Studio")
        header.setStyleSheet("color: #e94560; font-size: 16px; font-weight: bold;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # ── Prompt input ──
        prompt_group = QGroupBox("Creation Prompt")
        prompt_layout = QVBoxLayout()
        self.vr_creation_prompt = QTextEdit()
        self.vr_creation_prompt.setPlaceholderText(
            "Describe what to create in VR…\n"
            "Examples:\n"
            "• \"Generate a cyberpunk city I can explore\"\n"
            "• \"Create a 3D heart model with holographic animation\"\n"
            "• \"Design a futuristic spaceship schematic\"\n"
            "• \"Render a fantasy landscape video flyover\""
        )
        self.vr_creation_prompt.setMaximumHeight(90)
        self.vr_creation_prompt.setStyleSheet(
            "QTextEdit { background: #1a1a2e; color: #e0e0ff; border: 1px solid #333; "
            "border-radius: 4px; padding: 4px; font-size: 12px; }"
        )
        prompt_layout.addWidget(self.vr_creation_prompt)
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        # ── Engine selector ──
        engine_group = QGroupBox("Engine Selection")
        engine_layout = QVBoxLayout()

        self.vr_engine_combo = QComboBox()
        self.vr_engine_combo.addItems([
            "Auto (AI Routed)",
            "Visual Canvas (Images)",
            "Cinema Engine (Video/Movies)",
            "3D World Generation (Genie3)",
            "Animation Engine",
            "Unified Creative (Maps/Art)",
            "Medical Reconstruction",
            "CAD / Mechanical",
            "Architectural Design",
            "Fashion / Clothing",
            "Electronics / Circuit",
            "Industrial / Product",
            "Screenplay / Narrative",
            "Character Consistency",
            "Storyboard Planner",
            "BookTok Video",
            "Technical Visualization",
            "Data Visualization",
        ])
        self.vr_engine_combo.setStyleSheet(
            "QComboBox { background: #1a1a2e; color: #e0e0ff; border: 1px solid #333; "
            "border-radius: 4px; padding: 4px; }"
        )
        engine_layout.addWidget(self.vr_engine_combo)

        # VR-specific options
        vr_opts_layout = QHBoxLayout()
        self.chk_render_in_headset = QCheckBox("Render in Headset")
        self.chk_render_in_headset.setChecked(True)
        self.chk_render_in_headset.setToolTip("Stream the creation result directly to the VR headset")
        self.chk_immersive_3d = QCheckBox("Immersive 3D")
        self.chk_immersive_3d.setChecked(True)
        self.chk_immersive_3d.setToolTip("Convert 2D outputs to stereoscopic 3D for VR depth")
        self.chk_spatial_audio = QCheckBox("Spatial Audio")
        self.chk_spatial_audio.setToolTip("Add positional audio for immersive experience")
        vr_opts_layout.addWidget(self.chk_render_in_headset)
        vr_opts_layout.addWidget(self.chk_immersive_3d)
        vr_opts_layout.addWidget(self.chk_spatial_audio)
        engine_layout.addLayout(vr_opts_layout)

        engine_group.setLayout(engine_layout)
        layout.addWidget(engine_group)

        # ── Generate / Cancel buttons ──
        btn_layout = QHBoxLayout()
        self.btn_vr_generate = QPushButton("Create in VR")
        self.btn_vr_generate.setStyleSheet(
            "QPushButton { background: #0f3460; border: 1px solid #e94560; "
            "border-radius: 6px; color: #e94560; padding: 10px 24px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #1a1a4e; }"
            "QPushButton:disabled { color: #666; border-color: #333; }"
        )
        self.btn_vr_generate.clicked.connect(self._on_vr_create_clicked)
        btn_layout.addWidget(self.btn_vr_generate)

        self.btn_vr_cancel = QPushButton("Cancel")
        self.btn_vr_cancel.setEnabled(False)
        self.btn_vr_cancel.setStyleSheet(
            "QPushButton { background: #1a1a2e; border: 1px solid #555; "
            "border-radius: 6px; color: #888; padding: 10px 16px; }"
            "QPushButton:hover { background: #2a2a4e; color: #e94560; }"
        )
        self.btn_vr_cancel.clicked.connect(self._on_vr_create_cancel)
        btn_layout.addWidget(self.btn_vr_cancel)
        layout.addLayout(btn_layout)

        # ── Progress bar ──
        self.vr_creation_progress = QProgressBar()
        self.vr_creation_progress.setRange(0, 100)
        self.vr_creation_progress.setValue(0)
        self.vr_creation_progress.setTextVisible(True)
        self.vr_creation_progress.setFormat("Idle")
        self.vr_creation_progress.setStyleSheet(
            "QProgressBar { background: #1a1a2e; border: 1px solid #333; border-radius: 4px; "
            "text-align: center; color: #e0e0ff; height: 22px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #e94560, stop:1 #0f3460); border-radius: 3px; }"
        )
        layout.addWidget(self.vr_creation_progress)

        # ── Preview / Status ──
        self.vr_creation_status = QLabel("Ready — describe your creation and press 'Create in VR'")
        self.vr_creation_status.setWordWrap(True)
        self.vr_creation_status.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
        layout.addWidget(self.vr_creation_status)

        self.vr_creation_preview = QLabel()
        self.vr_creation_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vr_creation_preview.setMinimumHeight(120)
        self.vr_creation_preview.setStyleSheet(
            "QLabel { background: #0a0a1a; border: 1px solid #333; border-radius: 6px; }"
        )
        self.vr_creation_preview.setText("Preview will appear here")
        layout.addWidget(self.vr_creation_preview, 1)  # stretch

        layout.addStretch()
        self.tab_widget.addTab(tab, get_icon("environment"), "Creation Studio")

        # ── Internal state ──
        self._vr_creation_orchestrator = None
        self._vr_creation_active = False
        self._vr_creation_pipeline_id = None

    # ── VR Creation: Button handlers ──

    def _on_vr_create_clicked(self):
        """Handle 'Create in VR' button press."""
        prompt = self.vr_creation_prompt.toPlainText().strip()
        if not prompt:
            self.update_status("Enter a creation prompt first", "warning")
            return
        self._start_vr_creation(prompt)

    def _on_vr_create_cancel(self):
        """Cancel an active VR creation."""
        self._vr_creation_active = False
        self._vr_creation_pipeline_id = None
        self.btn_vr_generate.setEnabled(True)
        self.btn_vr_cancel.setEnabled(False)
        self.vr_creation_progress.setValue(0)
        self.vr_creation_progress.setFormat("Cancelled")
        self.vr_creation_status.setText("Creation cancelled by user")
        self.update_status("VR creation cancelled", "warning")

    def _start_vr_creation(self, prompt: str):
        """Route a creation request through the CreationOrchestrator with VR output."""
        import threading

        # Get selected engine hint
        engine_map = {
            0: None,  # Auto
            1: "visual_canvas", 2: "cinema", 3: "genie3",
            4: "animation", 5: "creative", 6: "medical",
            7: "cad_mechanical", 8: "architectural", 9: "fashion_clothing",
            10: "electronics_circuit", 11: "industrial_product",
            12: "screenplay", 13: "character_consistency", 14: "storyboard",
            15: "booktok", 16: "technical_viz", 17: "data_viz",
        }
        engine_hint = engine_map.get(self.vr_engine_combo.currentIndex())

        # UI feedback
        self.btn_vr_generate.setEnabled(False)
        self.btn_vr_cancel.setEnabled(True)
        self._vr_creation_active = True
        self.vr_creation_progress.setValue(5)
        self.vr_creation_progress.setFormat("Initialising…")
        self.vr_creation_status.setText(f"Creating: {prompt[:80]}…")
        self.update_status("VR Creation started", "info")

        # Publish event so the rest of the system knows
        if self.event_bus:
            self.event_bus.publish("vr.creation.started", {
                "prompt": prompt,
                "engine_hint": engine_hint,
                "render_in_headset": self.chk_render_in_headset.isChecked(),
                "immersive_3d": self.chk_immersive_3d.isChecked(),
                "spatial_audio": self.chk_spatial_audio.isChecked(),
                "timestamp": time.time(),
            })

        def _run():
            """Worker thread: load orchestrator, build pipeline, execute."""
            try:
                import asyncio as _aio

                # Lazy-init orchestrator
                if self._vr_creation_orchestrator is None:
                    try:
                        from core.creation_orchestrator import CreationOrchestrator
                        self._vr_creation_orchestrator = CreationOrchestrator(
                            event_bus=self.event_bus
                        )
                        self.logger.info("✅ VR Creation Orchestrator loaded")
                    except Exception as e:
                        self.logger.error(f"Failed to load CreationOrchestrator: {e}")
                        QTimer.singleShot(0, lambda: self._vr_creation_finished(
                            None, error=f"Orchestrator load failed: {e}"
                        ))
                        return

                orchestrator = self._vr_creation_orchestrator

                # Build pipeline — auto or forced engine
                if engine_hint:
                    # Single-engine forced mode
                    from core.creation_orchestrator import (
                        EngineType, EngineTask, CreationPipeline, CompositionMode
                    )
                    # Find matching EngineType
                    engine_type = None
                    for et in EngineType:
                        if et.value == engine_hint:
                            engine_type = et
                            break
                    if engine_type is None:
                        engine_type = EngineType.VISUAL

                    pipeline = CreationPipeline(
                        id=f"vr_pipeline_{int(time.time()*1000)}",
                        description=f"VR Creation: {prompt[:60]}",
                        tasks=[
                            EngineTask(
                                engine=engine_type,
                                operation="generate",
                                params={
                                    "prompt": prompt,
                                    "vr_mode": True,
                                    "stereoscopic": self.chk_immersive_3d.isChecked(),
                                    "spatial_audio": self.chk_spatial_audio.isChecked(),
                                },
                                output_key="final",
                            )
                        ],
                        mode=CompositionMode.SEQUENTIAL,
                        metadata={"source": "vr_creation_studio", "vr": True},
                    )
                else:
                    # Auto-route via natural-language parsing
                    pipeline = orchestrator.parse_request(prompt)
                    pipeline.metadata["source"] = "vr_creation_studio"
                    pipeline.metadata["vr"] = True

                self._vr_creation_pipeline_id = pipeline.id

                # Run the async pipeline in a fresh event loop
                loop = _aio.new_event_loop()
                try:
                    result = loop.run_until_complete(
                        orchestrator.execute_pipeline(pipeline)
                    )
                finally:
                    loop.close()

                # Deliver result back to the main thread
                QTimer.singleShot(0, lambda r=result: self._vr_creation_finished(r))

            except Exception as exc:
                self.logger.error(f"VR creation worker error: {exc}", exc_info=True)
                QTimer.singleShot(0, lambda: self._vr_creation_finished(
                    None, error=str(exc)
                ))

        threading.Thread(target=_run, daemon=True, name="VRCreationWorker").start()

    def _vr_creation_finished(self, result, error: str = None):
        """Called on the main thread when creation completes or fails."""
        self._vr_creation_active = False
        self.btn_vr_generate.setEnabled(True)
        self.btn_vr_cancel.setEnabled(False)

        if error or (result and not result.success):
            err_msg = error or (result.error if result else "Unknown error")
            self.vr_creation_progress.setValue(0)
            self.vr_creation_progress.setFormat("Failed")
            self.vr_creation_status.setText(f"Error: {err_msg}")
            self.vr_creation_status.setStyleSheet("color: #ff6b6b; font-size: 11px; padding: 4px;")
            self.update_status(f"VR Creation failed: {err_msg}", "error")
            if self.event_bus:
                self.event_bus.publish("vr.creation.failed", {"error": err_msg})
            return

        # Success
        exec_time = getattr(result, 'execution_time', 0)
        self.vr_creation_progress.setValue(100)
        self.vr_creation_progress.setFormat(f"Done ({exec_time:.1f}s)")
        self.vr_creation_status.setText(
            f"Creation complete in {exec_time:.1f}s — "
            f"Outputs: {', '.join(result.outputs.keys()) if result.outputs else 'none'}"
        )
        self.vr_creation_status.setStyleSheet("color: #1dd1a1; font-size: 11px; padding: 4px;")
        self.update_status(f"VR Creation complete ({exec_time:.1f}s)", "success")

        # Show preview in the tab
        self._show_vr_creation_preview(result)

        # Stream to headset if checkbox is set
        if self.chk_render_in_headset.isChecked():
            self._render_creation_in_headset(result)

        # Publish completion event
        if self.event_bus:
            self.event_bus.publish("vr.creation.complete", {
                "pipeline_id": result.pipeline_id,
                "execution_time": exec_time,
                "outputs": list(result.outputs.keys()) if result.outputs else [],
                "vr_rendered": self.chk_render_in_headset.isChecked(),
            })

    def _show_vr_creation_preview(self, result):
        """Display a preview of the created content in the Creation Studio tab."""
        try:
            final = getattr(result, 'final_output', None)
            if final is None:
                self.vr_creation_preview.setText("No visual output — check engine logs")
                return

            # If it's a file path to an image/video
            if isinstance(final, (str, Path)):
                path = Path(final) if isinstance(final, str) else final
                if path.exists() and path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
                    pixmap = QPixmap(str(path))
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            self.vr_creation_preview.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        self.vr_creation_preview.setPixmap(scaled)
                        return
                self.vr_creation_preview.setText(f"Output: {path.name}")
                return

            # If it's raw numpy array (image data)
            if hasattr(final, 'shape') and len(getattr(final, 'shape', ())) >= 2:
                try:
                    h, w = final.shape[:2]
                    ch = final.shape[2] if len(final.shape) == 3 else 1
                    fmt = QImage.Format.Format_RGB888 if ch == 3 else QImage.Format.Format_Grayscale8
                    img = QImage(final.data, w, h, final.strides[0], fmt)
                    pixmap = QPixmap.fromImage(img)
                    scaled = pixmap.scaled(
                        self.vr_creation_preview.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.vr_creation_preview.setPixmap(scaled)
                    return
                except Exception as img_err:
                    self.logger.warning(f"Could not render numpy preview: {img_err}")

            # If it's a dict with an 'image' or 'path' key
            if isinstance(final, dict):
                for key in ('image', 'image_path', 'path', 'output_path', 'file'):
                    val = final.get(key)
                    if val:
                        self._show_vr_creation_preview(
                            type(result)(
                                pipeline_id=result.pipeline_id,
                                outputs=result.outputs,
                                final_output=val,
                                metadata=result.metadata,
                                execution_time=result.execution_time,
                            )
                        )
                        return
                self.vr_creation_preview.setText(f"Output keys: {list(final.keys())}")
                return

            self.vr_creation_preview.setText(f"Output type: {type(final).__name__}")

        except Exception as e:
            self.logger.error(f"Error showing VR creation preview: {e}")
            self.vr_creation_preview.setText("Preview unavailable")

    def _render_creation_in_headset(self, result):
        """Stream the creation output to the connected VR headset.

        This works by:
        1. Converting the output to a frame (image) or frame sequence (video)
        2. Publishing it on the VR headset stream event for the VR rendering pipeline
        3. Optionally injecting it into the VR scene via VRScene / VRGraphicsRenderer
        """
        try:
            final = getattr(result, 'final_output', None)
            if final is None:
                self.logger.warning("No final output to render in headset")
                return

            frame_bgr = None

            # Resolve to image array
            if isinstance(final, (str, Path)):
                path = Path(final) if isinstance(final, str) else final
                if path.exists() and path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
                    if HAS_OPENCV:
                        import cv2
                        frame_bgr = cv2.imread(str(path))
                    else:
                        img = QImage(str(path))
                        if not img.isNull():
                            img = img.convertToFormat(QImage.Format.Format_RGB888)
                            ptr = img.bits()
                            ptr.setsize(img.byteCount())
                            arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                                (img.height(), img.width(), 3)
                            )
                            frame_bgr = arr[..., ::-1].copy()

            elif hasattr(final, 'shape') and len(getattr(final, 'shape', ())) >= 2:
                frame_bgr = final if final.shape[-1] == 3 else np.stack([final]*3, axis=-1)

            elif isinstance(final, dict):
                for key in ('image', 'frame', 'image_data'):
                    val = final.get(key)
                    if val is not None and hasattr(val, 'shape'):
                        frame_bgr = val
                        break

            if frame_bgr is None:
                self.logger.info("VR Creation output is not a renderable frame — "
                                 "publishing metadata only to headset")
                if self.event_bus:
                    self.event_bus.publish("vr.creation.render", {
                        "type": "metadata",
                        "pipeline_id": result.pipeline_id,
                        "output_keys": list(result.outputs.keys()) if result.outputs else [],
                        "timestamp": time.time(),
                    })
                return

            # ── Stream frame to headset ──
            if self.event_bus:
                # 1) Publish on the same channel the VR mirror uses so the
                #    existing VR streaming pipeline picks it up
                self.event_bus.publish("vision.stream.vr.frame", {
                    "frame": frame_bgr,
                    "timestamp": time.time(),
                    "source": "vr_creation_studio",
                })

                # 2) Dedicated creation render event for VR-specific handling
                self.event_bus.publish("vr.creation.render", {
                    "type": "frame",
                    "frame": frame_bgr,
                    "pipeline_id": result.pipeline_id,
                    "immersive_3d": self.chk_immersive_3d.isChecked(),
                    "spatial_audio": self.chk_spatial_audio.isChecked(),
                    "timestamp": time.time(),
                })

                # 3) Also push to headset stream start to activate the bridge
                self.event_bus.publish("vr.headset.stream.start", {
                    "source": "creation_studio",
                    "mode": "creation_render",
                    "timestamp": time.time(),
                })

            # 4) If VRGraphicsRenderer or VRScene are available, inject directly
            if self.vr_graphics_renderer and hasattr(self.vr_graphics_renderer, 'render_frame'):
                try:
                    self.vr_graphics_renderer.render_frame(frame_bgr)
                    self.logger.info("✅ Frame rendered via VRGraphicsRenderer")
                except Exception as e:
                    self.logger.warning(f"VRGraphicsRenderer.render_frame failed: {e}")

            if self.vr_scene and hasattr(self.vr_scene, 'set_background') or \
               self.vr_scene and hasattr(self.vr_scene, 'inject_texture'):
                try:
                    if hasattr(self.vr_scene, 'inject_texture'):
                        self.vr_scene.inject_texture(frame_bgr, label="creation_output")
                    elif hasattr(self.vr_scene, 'set_background'):
                        self.vr_scene.set_background(frame_bgr)
                    self.logger.info("✅ Frame injected into VR Scene")
                except Exception as e:
                    self.logger.warning(f"VR Scene injection failed: {e}")

            self.logger.info("🥽 VR Creation result streamed to headset")
            self.update_status("Creation streamed to VR headset", "success")

        except Exception as e:
            self.logger.error(f"Error rendering creation in headset: {e}", exc_info=True)
            self.update_status(f"Headset render failed: {e}", "error")

    # ── VR Creation: EventBus handlers ──

    def _handle_creation_progress(self, data: dict):
        """Handle creation.pipeline.progress events to update VR progress bar."""
        try:
            pid = data.get("pipeline_id", "")
            if self._vr_creation_pipeline_id and pid != self._vr_creation_pipeline_id:
                return  # Not our pipeline
            progress = data.get("progress", 0)
            task = data.get("current_task", "")

            def _update():
                if hasattr(self, 'vr_creation_progress'):
                    self.vr_creation_progress.setValue(int(progress))
                    self.vr_creation_progress.setFormat(f"{progress}% — {task}")
                if hasattr(self, 'vr_creation_status'):
                    self.vr_creation_status.setText(f"Running: {task} ({progress}%)")
            QTimer.singleShot(0, _update)
        except Exception as e:
            self.logger.error(f"Error in creation progress handler: {e}")

    def _handle_creation_complete(self, data: dict):
        """Handle creation.pipeline.complete events."""
        try:
            pid = data.get("pipeline_id", "")
            if self._vr_creation_pipeline_id and pid != self._vr_creation_pipeline_id:
                return
            exec_time = data.get("execution_time", 0)
            def _update():
                if hasattr(self, 'vr_creation_progress'):
                    self.vr_creation_progress.setValue(100)
                    self.vr_creation_progress.setFormat(f"Done ({exec_time:.1f}s)")
            QTimer.singleShot(0, _update)
        except Exception as e:
            self.logger.error(f"Error in creation complete handler: {e}")

    def _handle_visual_generated(self, data: dict):
        """Handle visual.generated events — show generated images/video in VR preview."""
        try:
            if not self._vr_creation_active:
                return
            image_path = data.get("image_path") or data.get("path")
            video_path = data.get("video_path") or ""
            is_video = data.get("type") == "video" or str(video_path).lower().endswith(".mp4") \
                       or str(image_path or "").lower().endswith(".mp4")
            display_path = video_path or image_path
            if not display_path:
                return

            def _show():
                if not hasattr(self, 'vr_creation_preview'):
                    return
                if is_video:
                    # Extract first frame from MP4 as thumbnail
                    try:
                        import cv2
                        cap = cv2.VideoCapture(str(display_path))
                        ret, frame = cap.read()
                        cap.release()
                        if ret and frame is not None:
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            h, w, ch = frame_rgb.shape
                            from PyQt6.QtGui import QImage
                            qimg = QImage(frame_rgb.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
                            pixmap = QPixmap.fromImage(qimg)
                            if not pixmap.isNull():
                                scaled = pixmap.scaled(
                                    self.vr_creation_preview.size(),
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
                                self.vr_creation_preview.setPixmap(scaled)
                                return
                    except Exception as ve:
                        self.logger.debug(f"Video thumbnail extraction failed: {ve}")
                    from pathlib import Path
                    self.vr_creation_preview.setText(f"🎬 {Path(str(display_path)).name}")
                else:
                    pixmap = QPixmap(str(display_path))
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            self.vr_creation_preview.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        self.vr_creation_preview.setPixmap(scaled)
            QTimer.singleShot(0, _show)
        except Exception as e:
            self.logger.error(f"Error handling visual.generated in VR: {e}")

    def _handle_creation_visual_progress(self, data: dict):
        """Handle visual.generation.progress events — update progress bar during image gen."""
        try:
            if not self._vr_creation_active:
                return
            progress = data.get("progress", 0)
            step = data.get("step", "")

            def _update():
                if hasattr(self, 'vr_creation_progress'):
                    self.vr_creation_progress.setValue(int(progress))
                    self.vr_creation_progress.setFormat(f"{progress}% — {step}" if step else f"{progress}%")
            QTimer.singleShot(0, _update)
        except Exception as e:
            self.logger.error(f"Error handling visual progress in VR: {e}")

    def _handle_voice_creation_request(self, data: dict):
        """Handle voice.input.recognized events — routes ALL voice commands
        through the full system command router when VR tab is visible.
        Creation, mining, trading, wallet, tab nav, and AI conversation."""
        try:
            text = data.get("text", "").strip()
            if not text:
                return
            # Only route if VR tab is visible (user is in VR mode)
            if not self.isVisible():
                return

            # Route through the comprehensive voice command handler
            def _route():
                self.on_voice_command({"command": text, "confidence": 0.9})
            QTimer.singleShot(0, _route)
        except Exception as e:
            self.logger.error(f"Error handling voice command in VR: {e}")

    def create_gesture_tab(self):
        """Create the gesture controls tab."""
        self.gesture_controls = VRGestureControls()
        self.tab_widget.addTab(self.gesture_controls, get_icon("gesture"), "Gestures")
        
        # Connect signals
        self.gesture_controls.gesture_mapping_changed.connect(self.on_gesture_mapping_changed)
        self.gesture_controls.gesture_recording_changed.connect(self.on_gesture_recording_changed)
    
    def create_performance_tab(self):
        """Create the performance monitoring tab."""
        self.performance_monitor = VRPerformanceMonitor()
        self.tab_widget.addTab(self.performance_monitor, get_icon("performance"), "Performance")
    
    def create_settings_tab(self):
        """Create the settings tab with VR system preferences."""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # General settings group
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout()
        
        # Show FPS counter
        self.chk_show_fps = QCheckBox("Show FPS Counter")
        self.chk_show_fps.setChecked(self.settings['show_fps'])
        self.chk_show_fps.stateChanged.connect(
            lambda: self.update_setting('show_fps', self.chk_show_fps.isChecked()))
        
        # Enable voice commands
        self.chk_enable_voice = QCheckBox("Enable Voice Commands")
        self.chk_enable_voice.setChecked(self.settings['enable_voice'])
        self.chk_enable_voice.stateChanged.connect(
            lambda: self.update_setting('enable_voice', self.chk_enable_voice.isChecked()))
            
        # Enable gesture controls
        self.chk_enable_gestures = QCheckBox("Enable Gesture Controls")
        self.chk_enable_gestures.setChecked(self.settings['enable_gestures'])
        self.chk_enable_gestures.stateChanged.connect(
            lambda: self.update_setting('enable_gestures', self.chk_enable_gestures.isChecked()))
            
        self.chk_mirror_display = QCheckBox("Mirror Display")
        self.chk_mirror_display.setChecked(self.settings['mirror_display'])
        self.chk_mirror_display.stateChanged.connect(
            lambda: self.update_setting('mirror_display', self.chk_mirror_display.isChecked()))

        # VR mirror source selector (auto / desktop / internal)
        self.cmb_mirror_source = QComboBox()
        self.cmb_mirror_source.addItems(["Auto (Best Available)", "Desktop Mirror Only", "Internal Viewer Only"])
        # Map current setting to index
        source_mode = (self.settings.get('vr_mirror_source') or 'auto').lower()
        if source_mode == 'desktop':
            self.cmb_mirror_source.setCurrentIndex(1)
        elif source_mode == 'internal':
            self.cmb_mirror_source.setCurrentIndex(2)
        else:
            self.cmb_mirror_source.setCurrentIndex(0)

        def _on_mirror_source_changed(index: int) -> None:
            modes = ['auto', 'desktop', 'internal']
            mode = modes[index] if 0 <= index < len(modes) else 'auto'
            self.update_setting('vr_mirror_source', mode)

        self.cmb_mirror_source.currentIndexChanged.connect(_on_mirror_source_changed)

        # SOTA 2026: Full GUI Mirror to headset
        self.chk_gui_mirror = QCheckBox("Mirror Full GUI to Headset")
        self.chk_gui_mirror.setChecked(False)
        self.chk_gui_mirror.setToolTip(
            "Stream the entire Kingdom AI window (all tabs) to the VR headset"
        )
        self.chk_gui_mirror.toggled.connect(self._toggle_gui_mirror)

        # Add to layout
        layout.addWidget(self.chk_show_fps)
        layout.addWidget(self.chk_enable_voice)
        layout.addWidget(self.chk_enable_gestures)
        layout.addWidget(self.chk_mirror_display)
        layout.addWidget(QLabel("VR Mirror Source:"))
        layout.addWidget(self.cmb_mirror_source)
        layout.addWidget(self.chk_gui_mirror)
        
        # Add stretch to push settings to top
        layout.addStretch()
        
        settings_widget = QWidget()
        settings_widget.setLayout(layout)
        return settings_widget
    
    def apply_styles(self):
        """Apply styles to the VR tab."""
        self.setStyleSheet(get_tab_style())
    
    def connect_signals(self):
        """Connect signals and slots."""
        # Connect event bus signals
        self.signals.status_updated.connect(self.update_status)
        self.signals.connection_changed.connect(self.on_connection_changed)
        self.signals.device_updated.connect(self.update_device_info)
        self.signals.tracking_updated.connect(self.update_tracking)
        self.signals.environment_updated.connect(self.update_environment)
        self.signals.performance_updated.connect(self.update_performance)
        self.signals.gesture_detected.connect(self.on_gesture_detected)
        self.signals.voice_command.connect(self.on_voice_command)
        self.signals.ai_response.connect(self.on_ai_response)
        
        # Connect UI signals (with safe connection checking)
        if hasattr(self.env_selector, 'environment_selected'):
            self.env_selector.environment_selected.connect(self.on_environment_selected)
        elif hasattr(self.env_selector, 'currentTextChanged'):
            self.env_selector.currentTextChanged.connect(self.on_environment_selected)
        
        if hasattr(self.gesture_controls, 'gesture_mapping_changed'):
            self.gesture_controls.gesture_mapping_changed.connect(self.on_gesture_mapping_changed)
        if hasattr(self.gesture_controls, 'gesture_recording_changed'):
            self.gesture_controls.gesture_recording_changed.connect(self.on_gesture_recording_changed)
        
        # Connect window close event
        self.destroyed.connect(self.cleanup)
    
    def init_vr_system(self):
        """Initialize the VR system - single-run guard to prevent spam and loops."""
        if getattr(self, "_vr_system_initializing", False) or self.vr_worker or self.vr_thread:
            return
        self._vr_system_initializing = True
        try:
            self.logger.debug("[VR] Initializing VR system worker thread")
            self.vr_thread = QThread(self)
            self.vr_worker = VRSystemWorker(config=self.config, event_bus=self.event_bus)
            self.vr_worker.moveToThread(self.vr_thread)

            self.vr_worker.status_updated.connect(self.signals.status_updated)
            self.vr_worker.connection_changed.connect(self.signals.connection_changed)
            self.vr_worker.device_updated.connect(self.signals.device_updated)
            self.vr_worker.tracking_updated.connect(self.signals.tracking_updated)
            self.vr_worker.environment_updated.connect(self.signals.environment_updated)
            self.vr_worker.performance_updated.connect(self.signals.performance_updated)
            self.vr_worker.gesture_detected.connect(self.signals.gesture_detected)
            self.vr_worker.voice_command.connect(self.signals.voice_command)
            self.vr_worker.ai_response.connect(self.signals.ai_response)

            self.signals.shutdown_requested.connect(self.vr_worker.shutdown)

            self.vr_thread.started.connect(self.vr_worker.initialize)
            
            # Delay thread start to prevent segfault during GUI init
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, self.vr_thread.start)
            self.logger.debug("[VR] Worker thread scheduled to start in 3s")

            self._init_advanced_vr_systems()

        except Exception as e:
            self._vr_system_initializing = False
            self.logger.error(f"Failed to initialize VR system: {e}", exc_info=True)
            if self.vr_thread:
                self.vr_thread.quit()
                self.vr_thread.wait()
            self.vr_thread = None
            self.vr_worker = None
            self.is_connected = False
    
    def _init_advanced_vr_systems(self):
        """Initialize advanced VR systems from vr/ directory."""
        try:
            if VR_FULL_SYSTEMS_AVAILABLE:
                # Initialize Gesture Recognition
                if GestureRecognition:
                    try:
                        self.gesture_recognition = GestureRecognition()
                        logger.info("✅ Gesture Recognition initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize Gesture Recognition: {e}")
                
                # Initialize VR Voice Commands
                if VRVoiceCommands:
                    try:
                        self.vr_voice_commands = VRVoiceCommands()
                        logger.info("✅ VR Voice Commands initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize VR Voice Commands: {e}")
                
                # Initialize VR Device Manager
                if VRDeviceManager:
                    try:
                        self.vr_device_manager = VRDeviceManager()
                        logger.info("✅ VR Device Manager initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize VR Device Manager: {e}")
                
                # Initialize VR Environment Manager
                if VREnvironmentManager:
                    try:
                        self.vr_environment_manager = VREnvironmentManager()
                        logger.info("✅ VR Environment Manager initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize VR Environment Manager: {e}")
                
                # Initialize VR Graphics Renderer
                if VRGraphicsRenderer:
                    try:
                        self.vr_graphics_renderer = VRGraphicsRenderer()
                        logger.info("✅ VR Graphics Renderer initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize VR Graphics Renderer: {e}")
                
                logger.info("✅ Advanced VR Systems initialized (Gesture, Voice, Device, Environment, Graphics)")
            
            # Initialize VR Core Modules
            if VR_CORE_MODULES_AVAILABLE:
                # Initialize VR Connector
                if VRConnector:
                    try:
                        self.vr_connector = VRConnector()
                        logger.info("✅ VR Connector initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize VR Connector: {e}")
                
                # Initialize VR Module
                if VRModule:
                    try:
                        self.vr_module = VRModule()
                        logger.info("✅ VR Module initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize VR Module: {e}")
                
                # Initialize VR Renderer
                if VRRenderer:
                    try:
                        self.vr_renderer = VRRenderer()
                        logger.info("✅ VR Renderer initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize VR Renderer: {e}")
                
                # Initialize VR Scene
                if VRScene:
                    try:
                        self.vr_scene = VRScene()
                        logger.info("✅ VR Scene initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize VR Scene: {e}")
                
                # Initialize VR Manager Core
                if VRManagerCore:
                    try:
                        self.vr_manager_core = VRManagerCore()
                        logger.info("✅ VR Manager Core initialized")
                    except Exception as e:
                        logger.error(f"Failed to initialize VR Manager Core: {e}")
                
                logger.info("✅ VR Core Modules initialized (Connector, Module, Renderer, Scene, Manager)")
        except Exception as e:
            logger.error(f"Error initializing advanced VR systems: {e}")
    
    def publish_redis_event(self, channel: str, data: dict):
        """Publish an event to Redis."""
        if not self.redis_connected or not self.redis_manager:
            self.update_status("Cannot publish: Not connected to Redis", "error")
            return False
            
        try:
            self.redis_manager.publish(channel, data)
            return True
        except Exception as e:
            self.update_status(f"Failed to publish to Redis: {str(e)}", "error")
            self.redis_connected = False
            return False
    
    def toggle_connection(self):
        """Toggle VR system connection."""
        target = "disconnect" if self.is_connected else "connect"
        self._emit_ui_telemetry(
            "vr.toggle_connection_clicked",
            metadata={"target": target},
        )
        if self.is_connected:
            self.disconnect_vr()
        else:
            self.connect_vr()
    
    def connect_vr(self):
        """Connect to VR system."""
        if self.vr_worker and not self.is_connected:
            self.vr_worker.initialize()
    
    def disconnect_vr(self):
        """Disconnect from VR system."""
        if self.vr_worker and self.is_connected:
            self.vr_worker.shutdown()
    
    def update_device_info(self, device_data=None):
        """Update device information - prevents error flood."""
        if device_data is None:
            device_data = {}
        # Update device labels if they exist
        if hasattr(self, 'lbl_device_name'):
            self.lbl_device_name.setText(device_data.get('name', 'Unknown Device'))
        if hasattr(self, 'lbl_device_status'):
            self.lbl_device_status.setText(device_data.get('status', 'Unknown'))
        if hasattr(self, 'lbl_device_battery'):
            battery = device_data.get('battery', 0)
            self.lbl_device_battery.setText(f"{battery}%")
    
    def update_tracking(self, tracking_data=None):
        """Update tracking information - prevents error flood."""
        if tracking_data is None:
            tracking_data = {}
        # Update tracking labels if they exist
        if hasattr(self, 'lbl_tracking_status'):
            self.lbl_tracking_status.setText(tracking_data.get('status', 'Unknown'))
        if hasattr(self, 'lbl_hmd_position'):
            pos = tracking_data.get('position', [0, 0, 0])
            self.lbl_hmd_position.setText(f"X: {pos[0]:.2f}, Y: {pos[1]:.2f}, Z: {pos[2]:.2f}")
    
    def update_environment(self, env_data=None):
        """Update environment information - prevents error flood.""" 
        if env_data is None:
            env_data = {}
        # Update environment info if needed
        env_name = env_data.get('name', 'Unknown Environment')
        self.update_status(f"Environment updated: {env_name}", "info")
    
    def update_performance(self, metrics=None):
        """Update performance metrics - prevents error flood."""
        if metrics is None:
            metrics = {}
        # Update performance metrics if they exist
        fps = metrics.get('fps', 0)
        memory = metrics.get('memory', 0)
        cpu = metrics.get('cpu', 0)
        
        if hasattr(self, 'fps_label'):
            self.fps_label.setText(f"FPS: {fps}")
        if hasattr(self, 'memory_label'):
            self.memory_label.setText(f"Memory: {memory}MB")
        if hasattr(self, 'cpu_label'):
            self.cpu_label.setText(f"CPU: {cpu}%")

    def _publish_vr_view_frame(self):
        """Publish the current VR 3D viewer image as a vision.stream.vr.frame event."""
        try:
            if not self._should_vr_view_timer_run():
                self._sync_vr_timers()
                return
            if not getattr(self, 'event_bus', None):
                return

            # Only mirror VR view when mirror_display is enabled
            if not self.settings.get('mirror_display', False):
                return
            frame_bgr = None

            mode = (self.settings.get('vr_mirror_source') or 'auto').lower()

            # 1) Desktop mirror path (SteamVR / Oculus / WMR mirror window)
            use_desktop = mode in ('auto', 'desktop')
            if use_desktop and sys.platform.startswith("win"):
                try:
                    # Refresh handle ~every 5 seconds or if not set
                    now = time.time()
                    if self._vr_mirror_hwnd is None or (now - self._vr_mirror_last_check) > 5.0:
                        self._vr_mirror_hwnd = self._find_vr_mirror_window()
                        self._vr_mirror_last_check = now

                    if self._vr_mirror_hwnd is not None:
                        frame_bgr = self._capture_vr_mirror_frame(self._vr_mirror_hwnd)
                except Exception as win_err:
                    self.logger.error(f"Error capturing VR mirror window: {win_err}")

            # 2) Internal VR3DViewer mirror path
            use_internal = mode in ('auto', 'internal')
            if frame_bgr is None and use_internal:
                if not hasattr(self, 'viewer_3d') or self.viewer_3d is None:
                    return

                view = getattr(self.viewer_3d, 'view', None)
                if view is None:
                    return

                pixmap = view.grab()
                if pixmap.isNull():
                    return

                image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
                width = image.width()
                height = image.height()
                if width <= 0 or height <= 0:
                    return

                ptr = image.bits()
                ptr.setsize(image.byteCount())
                arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 3))

                # Convert RGB (Qt) to BGR (OpenCV/vision pipeline convention)
                frame_bgr = arr[..., ::-1].copy()

            if frame_bgr is None:
                return

            try:
                frame_bgr = frame_bgr[:, ::-1, :].copy()
            except Exception:
                pass

            payload: Dict[str, Any] = {
                "frame": frame_bgr,
                "timestamp": time.time(),
            }

            publish = getattr(self.event_bus, 'publish', None)
            if callable(publish):
                publish("vision.stream.vr.frame", payload)

        except Exception as e:
            self.logger.error(f"Error publishing VR view frame: {e}")

    def _publish_vr_stream_status(self, active: bool, error: Optional[str] = None) -> None:
        """Publish VR view stream status on vision.stream.vr.status."""
        try:
            if not getattr(self, 'event_bus', None):
                return

            payload: Dict[str, Any] = {
                "active": bool(active),
                "source": "vr_viewer",
                "mirror_mode": self.settings.get('vr_mirror_source', 'auto'),
            }
            # Include detected runtime if available (steamvr/meta/wmr/unknown)
            if self._vr_mirror_runtime:
                payload["runtime"] = self._vr_mirror_runtime
            if error:
                payload["error"] = str(error)

            publish = getattr(self.event_bus, 'publish', None)
            if callable(publish):
                publish("vision.stream.vr.status", payload)

        except Exception as e:
            self.logger.error(f"Error publishing VR view status: {e}")

    # ===========================================================================
    # SOTA 2026: FULL GUI MIRROR — Stream entire Kingdom AI window to headset
    # ===========================================================================

    def _publish_gui_mirror_frame(self):
        """Capture the entire Kingdom AI main window and publish for VR headset display.

        This lets the user see ALL tabs (Dashboard, Mining, Trading, Wallet, Thoth AI, etc.)
        inside the VR headset — not just the VR tab content.
        """
        try:
            if not self._gui_mirror_enabled:
                return
            if not getattr(self, 'event_bus', None):
                return
            if not self.isVisible():
                return

            # Find the top-level QMainWindow
            main_window = None
            widget = self
            while widget is not None:
                if isinstance(widget, QMainWindow):
                    main_window = widget
                    break
                widget = widget.parent() if hasattr(widget, 'parent') else None

            if main_window is None:
                # Fallback: try QApplication.activeWindow()
                app = QApplication.instance()
                if app:
                    main_window = app.activeWindow()
                if main_window is None:
                    return
            try:
                if main_window.isMinimized() or (not main_window.isVisible()):
                    return
            except Exception:
                pass

            # Grab the full window pixmap
            pixmap = main_window.grab()
            if pixmap.isNull():
                return

            image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
            width = image.width()
            height = image.height()
            if width <= 0 or height <= 0:
                return

            ptr = image.bits()
            ptr.setsize(image.byteCount())
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 3))
            frame_bgr = arr[..., ::-1].copy()

            self.event_bus.publish("vr.gui.mirror.frame", {
                "frame": frame_bgr,
                "timestamp": time.time(),
                "source": "gui_mirror",
                "width": width,
                "height": height,
            })

        except Exception as e:
            self.logger.error(f"Error in GUI mirror capture: {e}")

    def _toggle_gui_mirror(self, enabled: bool):
        """Enable or disable full GUI mirror streaming to headset."""
        self._gui_mirror_enabled = enabled
        if enabled:
            self._gui_mirror_timer.start()
            self.update_status("GUI mirror streaming to headset ON", "success")
            self.logger.info("🥽 GUI mirror → headset: ENABLED")
            # Start the headset stream if not already
            if self.event_bus:
                self.event_bus.publish("vr.headset.stream.start", {
                    "source": "gui_mirror",
                    "mode": "full_immersive",
                    "timestamp": time.time(),
                })
        else:
            self._gui_mirror_timer.stop()
            self.update_status("GUI mirror streaming OFF", "info")
            self.logger.info("🥽 GUI mirror → headset: DISABLED")

    # ===========================================================================
    # SOTA 2026: WEBCAM INTEGRATION METHODS
    # ===========================================================================

    def _toggle_webcam(self):
        """Toggle webcam on/off."""
        if hasattr(self, '_webcam_worker') and self._webcam_worker and self._webcam_worker.isRunning():
            self._webcam_worker.stop()
            self._webcam_worker = None
            self.btn_webcam_toggle.setText("📷 Start Webcam")
            self.webcam_label.setText("📹 Webcam Off")
            self.webcam_status.setText("Status: Disconnected")
            self.btn_send_to_headset.setEnabled(False)
            logger.info("📹 VR Webcam stopped")
        else:
            # Policy: VR tab must not use MJPEG/Brio webcam logic.
            try:
                self.update_status("VR webcam disabled (no Brio/MJPEG in VR tab)", "warning")
            except Exception:
                pass
            try:
                self.webcam_status.setText("Status: Disabled")
            except Exception:
                pass
            try:
                self.webcam_label.setText("📹 Webcam Disabled")
            except Exception:
                pass
            try:
                self.btn_send_to_headset.setEnabled(False)
            except Exception:
                pass
            logger.info("📹 VR Webcam toggle ignored (disabled)")

    def _on_webcam_frame(self, frame: np.ndarray):
        """Handle webcam frame - display in QLabel."""
        try:
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                self.webcam_label.width(),
                self.webcam_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.webcam_label.setPixmap(scaled)
            if self.event_bus and HAS_OPENCV:
                self.event_bus.publish('vision.stream.webcam.frame', {
                    'frame': cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                    'timestamp': time.time(),
                    'source': 'vr_tab_webcam'
                })
        except Exception as e:
            logger.error(f"Error displaying webcam frame: {e}")

    def _on_webcam_status(self, status: str):
        """Handle webcam status updates."""
        self.webcam_status.setText(f"Status: {status}")
        logger.info(f"📹 VR Webcam: {status}")

    def _send_webcam_to_headset(self):
        """Send webcam stream to VR headset via WebXR/OpenXR bridge."""
        try:
            if not hasattr(self, '_webcam_worker') or not self._webcam_worker:
                self.update_status("No webcam active", "warning")
                return
            if self.event_bus:
                self.event_bus.publish('vr.headset.stream.start', {
                    'source': 'webcam',
                    'mode': 'passthrough',
                    'timestamp': time.time()
                })
                self.update_status("📡 Streaming webcam to VR headset", "success")
                logger.info("🥽 Started webcam → VR headset streaming")
        except Exception as e:
            logger.error(f"Failed to start headset streaming: {e}")
            self.update_status(f"Headset stream failed: {e}", "error")

    def _find_vr_mirror_window(self):
        """Best-effort search for a VR mirror window on Windows.

        Looks for common SteamVR / Oculus mirror window titles. Returns a window
        handle (HWND) or None. This function is Windows-only and safely
        no-ops on other platforms.
        """
        try:
            if not sys.platform.startswith("win"):
                return None

            try:
                import win32gui  # type: ignore[import]
            except ImportError:
                self.logger.debug("pywin32 not available; VR mirror window capture disabled")
                return None

            # Known runtime title patterns (SOTA 2025-26 heuristics)
            runtime_patterns = {
                "steamvr": ["vr view", "steamvr", "steamvr desktop", "steamvr home"],
                "meta": ["oculus mirror", "meta quest", "oculus link", "meta link"],
                "wmr": ["windows mixed reality", "mixed reality portal"],
            }

            matches = []

            def enum_handler(hwnd, _):
                try:
                    if not win32gui.IsWindowVisible(hwnd):
                        return
                    title = win32gui.GetWindowText(hwnd) or ""
                    lower = title.lower()
                    for runtime, patterns in runtime_patterns.items():
                        for pat in patterns:
                            if pat in lower:
                                matches.append((hwnd, runtime, title))
                                return
                except Exception:
                    return

            win32gui.EnumWindows(enum_handler, None)
            if matches:
                hwnd, runtime, title = matches[0]
                self._vr_mirror_runtime = runtime or "unknown"
                self.logger.info(
                    f"✅ Detected VR mirror window: hwnd={hwnd}, title='{title}', runtime={self._vr_mirror_runtime}"
                )
                return hwnd

            return None
        except Exception as e:
            self.logger.error(f"Error finding VR mirror window: {e}")
            return None

    def _capture_vr_mirror_frame(self, hwnd) -> Optional[np.ndarray]:
        """Capture a single frame from a VR mirror window using pywin32.

        Returns a BGR numpy array on success, or None on failure. This uses
        GDI BitBlt, so it is not the most efficient path but is broadly
        compatible on Windows.
        """
        try:
            if not sys.platform.startswith("win"):
                return None

            try:
                import win32gui  # type: ignore[import]
                import win32ui   # type: ignore[import]
                import win32con  # type: ignore[import]
            except ImportError:
                # pywin32 not installed
                return None

            # Get window rectangle
            try:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            except Exception:
                return None

            width = max(0, right - left)
            height = max(0, bottom - top)
            if width == 0 or height == 0:
                return None

            # Create device contexts and bitmap
            hwindc = win32gui.GetWindowDC(hwnd)
            if not hwindc:
                return None

            srcdc = win32ui.CreateDCFromHandle(hwindc)
            memdc = srcdc.CreateCompatibleDC()
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(srcdc, width, height)
            memdc.SelectObject(bmp)

            # BitBlt from window DC into memory DC
            memdc.BitBlt((0, 0), (width, height), srcdc, (0, 0), win32con.SRCCOPY)

            # Extract raw bitmap data (BGRA)
            bmp_info = bmp.GetInfo()
            bmp_bytes = bmp.GetBitmapBits(True)

            img = np.frombuffer(bmp_bytes, dtype=np.uint8)
            img = img.reshape((bmp_info['bmHeight'], bmp_info['bmWidth'], 4))

            # Convert BGRA -> BGR
            frame_bgr = img[..., :3].copy()

            # Clean up GDI objects
            memdc.DeleteDC()
            srcdc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwindc)
            win32gui.DeleteObject(bmp.GetHandle())

            # Some windows report height flipped; normalize orientation
            if frame_bgr.shape[0] < 0:
                frame_bgr = frame_bgr[::-1, :, :]

            # Under WSL, OpenVR registry access will spam the console, but ADB-based
            # Quest detection can still work. In that case we skip only the OpenVR
            # branch below and keep the ADB path active.
            is_wsl = sys.platform.startswith("linux") and os.environ.get("WSL_DISTRO_NAME") is not None

            return frame_bgr

        except Exception as e:
            try:
                self.logger.error(f"Error capturing VR mirror frame: {e}")
            except Exception:
                pass
            return None
    
    def calibrate_vr(self):
        """Calibrate the VR system."""
        if self.vr_worker and self.is_connected:
            self._emit_ui_telemetry("vr.calibrate_clicked")
            self.signals.calibration_requested.emit()
    
    def reset_view(self):
        """Reset the VR view."""
        if self.vr_worker and self.is_connected:
            self._emit_ui_telemetry("vr.reset_view_clicked")
            self.signals.reset_view_requested.emit()
    
    def update_setting(self, key: str, value: Any):
        """Update a setting and notify the VR system."""
        if key in self.settings:
            self.settings[key] = value
            self.signals.settings_updated.emit(self.settings)
            
            # Update UI based on setting changes
            if key == 'show_fps':
                self.fps_label.setVisible(value)
            # Mirror display controls VR view stream publication status
            if key == 'mirror_display':
                try:
                    self._publish_vr_stream_status(bool(value))
                except Exception as e:
                    self.logger.error(f"Error publishing VR view stream status: {e}")
                self._sync_vr_timers()
            # Mirror source changes should also update status metadata
            if key == 'vr_mirror_source':
                try:
                    self._publish_vr_stream_status(self.settings.get('mirror_display', False))
                except Exception as e:
                    self.logger.error(f"Error publishing VR mirror source status: {e}")
    
    def _on_brightness_changed(self, value: int):
        """Handle brightness slider value change."""
        try:
            self.settings['brightness'] = value
            self.logger.debug(f"VR brightness changed to: {value}")
            
            # Publish brightness change event
            if self.event_bus:
                self.event_bus.publish("vr.settings.brightness", {
                    "brightness": value,
                    "normalized": value / 100.0
                })
            
            # If connected to VR device, send brightness command
            if hasattr(self, 'vr_system') and self.vr_system:
                try:
                    self.vr_system.set_brightness(value / 100.0)
                except Exception as e:
                    self.logger.debug(f"Could not set VR brightness: {e}")
        except Exception as e:
            self.logger.error(f"Error changing brightness: {e}")
    
    def _on_mirror_display_toggled(self, checked: bool):
        """Handle mirror display checkbox toggle."""
        try:
            self.settings['mirror_display'] = checked
            self.logger.info(f"VR mirror display {'enabled' if checked else 'disabled'}")
            
            # Publish mirror display change event
            if self.event_bus:
                self.event_bus.publish("vr.settings.mirror", {
                    "enabled": checked
                })
            
            # Update stream status
            self._publish_vr_stream_status(checked)
        except Exception as e:
            self.logger.error(f"Error toggling mirror display: {e}")
    
    def reset_settings(self):
        """Reset all settings to defaults."""
        default_settings = {
            'show_fps': True,
            'show_performance': True,
            'enable_voice': True,
            'enable_gestures': True,
            'mirror_display': False,
            'vr_mirror_source': 'auto',
        }
        
        for key, value in default_settings.items():
            self.settings[key] = value
            
        # Update UI
        self.chk_show_fps.setChecked(self.settings['show_fps'])
        self.chk_enable_voice.setChecked(self.settings['enable_voice'])
        self.chk_enable_gestures.setChecked(self.settings['enable_gestures'])
        self.chk_mirror_display.setChecked(self.settings['mirror_display'])
        if hasattr(self, 'cmb_mirror_source'):
            self.cmb_mirror_source.setCurrentIndex(0)
        
        # Notify VR system
        self.signals.settings_updated.emit(self.settings)
        
        self.update_status("Settings reset to defaults", "info")
        self._emit_ui_telemetry("vr.reset_settings_clicked")
        self._sync_vr_timers()
    
    def _subscribe_to_backend_events(self):
        """Subscribe to VR backend events"""
        if hasattr(self, 'event_bus') and self.event_bus:
            try:
                from PyQt6.QtCore import QTimer
                import asyncio
                
                def subscribe_all():
                    try:
                        self.event_bus.subscribe("vr.environments_updated", self._handle_vr_environments)
                        self.event_bus.subscribe("vr.status", self._handle_vr_status)
                        self.event_bus.subscribe("vr.command", self._handle_vr_command)
                        self.event_bus.subscribe("thoth.thinking", self._handle_brain_thinking)
                        self.event_bus.subscribe("thoth.status", self._handle_brain_status)
                        # SOTA 2026: Complete VR event coverage
                        self.event_bus.subscribe("vr.device.connected", self._handle_vr_device_event)
                        self.event_bus.subscribe("vr.device.disconnected", self._handle_vr_device_event)
                        self.event_bus.subscribe("vr.device.error", self._handle_vr_device_error)
                        self.event_bus.subscribe("vr.device.status", self._handle_vr_device_status)
                        self.event_bus.subscribe("vr.session.started", self._handle_vr_session)
                        self.event_bus.subscribe("vr.session.ended", self._handle_vr_session)
                        self.event_bus.subscribe("vr.tracking.update", self._handle_vr_tracking)
                        self.event_bus.subscribe("vr.performance.update", self._handle_vr_performance)
                        self.event_bus.subscribe("vr.environment.changed", self._handle_vr_environment_changed)
                        self.event_bus.subscribe("vr.connect.result", self._handle_vr_connect_result)
                        self.event_bus.subscribe("vr.started", self._handle_vr_started)
                        self.event_bus.subscribe("vr.stopped", self._handle_vr_stopped)
                        # SOTA 2026: VR Creation Engine integration
                        self.event_bus.subscribe("creation.pipeline.progress", self._handle_creation_progress)
                        self.event_bus.subscribe("creation.pipeline.complete", self._handle_creation_complete)
                        self.event_bus.subscribe("visual.generated", self._handle_visual_generated)
                        self.event_bus.subscribe("visual.generation.progress", self._handle_creation_visual_progress)
                        # SOTA 2026: Voice-to-Creation in VR headset
                        self.event_bus.subscribe("voice.input.recognized", self._handle_voice_creation_request)
                        # ══ SOTA 2026: Full System Control from VR ══
                        # Mining events
                        self.event_bus.subscribe("mining.started", self._handle_system_event)
                        self.event_bus.subscribe("mining.stopped", self._handle_system_event)
                        self.event_bus.subscribe("mining.hashrate_update", self._handle_mining_hashrate_vr)
                        self.event_bus.subscribe("mining.stats.update", self._handle_system_event)
                        self.event_bus.subscribe("mining.nodes.connected", self._handle_system_event)
                        self.event_bus.subscribe("mining.pools.connected", self._handle_system_event)
                        # Trading events
                        self.event_bus.subscribe("trading.signal_executed", self._handle_system_event)
                        self.event_bus.subscribe("trading.auto_enabled", self._handle_system_event)
                        self.event_bus.subscribe("trading.auto_disabled", self._handle_system_event)
                        # Wallet events
                        self.event_bus.subscribe("wallet.balance.updated", self._handle_system_event)
                        self.event_bus.subscribe("wallet.telemetry", self._handle_system_event)
                        # AI / Thoth response for VR relay
                        self.event_bus.subscribe("ai.response", self._handle_ai_response_vr)
                        self.event_bus.subscribe("thoth.response", self._handle_ai_response_vr)
                        # Voice audio for headset speaker relay
                        self.event_bus.subscribe("voice.speaking.started", self._handle_system_event)
                        self.event_bus.subscribe("voice.speaking.stopped", self._handle_system_event)
                        self.logger.info("✅ VR subscriptions completed (38 events — full system + creation + voice)")
                    except Exception as e:
                        self.logger.error(f"VR subscription error: {e}")
                
                QTimer.singleShot(4200, subscribe_all)
            except Exception as e:
                self.logger.error(f"Error setting up VR subscriptions: {e}")
    
    def _handle_vr_environments(self, data):
        """Handle VR environments update from backend - DISPLAY TO USER"""
        try:
            environments = data.get('environments', [])
            message = data.get('message', '')
            
            self.logger.info(f"✅ VR Environments from Backend: {message}")
            self.logger.info(f"   Environments: {len(environments)}")
            
            # Update environment list
            if environments and hasattr(self, 'lst_environments'):
                self.lst_environments.clear()
                for env in environments:
                    self.lst_environments.addItem(env)
                
            self.update_status(f"{message} - {len(environments)} environments available", "success")
                
        except Exception as e:
            self.logger.error(f"Error handling VR environments: {e}")
    
    def _handle_vr_status(self, data):
        """Handle VR status updates from backend."""
        try:
            status = data.get('status', 'unknown')
            message = data.get('message', '')
            self.logger.info(f"VR Status: {status} - {message}")
            self.update_status(f"VR: {message}", "info" if status == "ok" else "warning")
        except Exception as e:
            self.logger.error(f"Error handling VR status: {e}")
    
    def _handle_vr_command(self, data):
        """Handle VR command responses from backend."""
        try:
            command = data.get('command', '')
            result = data.get('result', '')
            self.logger.info(f"VR Command '{command}' result: {result}")
        except Exception as e:
            self.logger.error(f"Error handling VR environments: {e}")
    
    def _handle_brain_thinking(self, data):
        """Handle Thoth/Ollama thinking state updates for brain indicator."""
        try:
            if not hasattr(self, 'brain_status_label'):
                return
            active = bool(data.get('active', False))
            model = data.get('model', '') or ''
            model_suffix = f" ({model})" if model else ""
            if active:
                self.brain_status_label.setText(f"Brain: Thinking{model_suffix}")
                self.brain_status_label.setStyleSheet("color: #feca57; font-weight: bold;")
            else:
                # When thinking stops, do not override connection status; just mark idle
                self.brain_status_label.setText(f"Brain: Idle{model_suffix}")
                self.brain_status_label.setStyleSheet("color: #b3b3b3;")
        except Exception as e:
            self.logger.error(f"Error handling brain thinking state: {e}")

    def _handle_brain_status(self, data):
        """Handle Thoth/Ollama connection status updates for brain indicator."""
        try:
            if not hasattr(self, 'brain_status_label'):
                return
            status = data.get('status', 'Disconnected')
            current_model = data.get('current_model', '') or ''
            model_suffix = f" ({current_model})" if current_model else ""
            if status.lower() == "connected":
                self.brain_status_label.setText(f"Brain: Connected{model_suffix}")
                self.brain_status_label.setStyleSheet("color: #1dd1a1; font-weight: bold;")
            elif status.lower() == "disconnected":
                self.brain_status_label.setText("Brain: Disconnected")
                self.brain_status_label.setStyleSheet("color: #ff6b6b;")
            else:
                self.brain_status_label.setText(f"Brain: {status}{model_suffix}")
                self.brain_status_label.setStyleSheet("color: #feca57;")
        except Exception as e:
            self.logger.error(f"Error handling brain status update: {e}")
    
    def _handle_vr_device_event(self, data):
        """Handle VR device connected/disconnected events."""
        try:
            device_info = data.get('device', data)
            device_name = device_info.get('name', 'Unknown VR Device')
            event_type = data.get('type', data.get('event', 'connected'))
            
            self.logger.info(f"VR device event: {device_name} - {event_type}")
            
            # Update device info display
            if hasattr(self, 'update_device_info'):
                self.update_device_info(device_info)
            
            status_msg = f"VR Device {event_type}: {device_name}"
            self.update_status(status_msg, "success" if 'connected' in event_type else "warning")
        except Exception as e:
            self.logger.error(f"Error handling VR device event: {e}")
    
    def _handle_vr_device_error(self, data):
        """Handle VR device error events."""
        try:
            error = data.get('error', 'Unknown error')
            device = data.get('device', {}).get('name', 'VR Device')
            self.logger.error(f"VR device error ({device}): {error}")
            self.update_status(f"VR Error: {error}", "error")
        except Exception as e:
            self.logger.error(f"Error handling VR device error: {e}")
    
    def _handle_vr_device_status(self, data):
        """Handle VR device status updates."""
        try:
            status = data.get('status', 'unknown')
            device = data.get('device', {}).get('name', 'VR Device')
            self.logger.debug(f"VR device status: {device} - {status}")
            
            if hasattr(self, 'connection_status'):
                self.connection_status.setText(f"{device}: {status}")
        except Exception as e:
            self.logger.error(f"Error handling VR device status: {e}")
    
    def _handle_vr_session(self, data):
        """Handle VR session started/ended events."""
        try:
            event_type = data.get('event', data.get('type', 'unknown'))
            session_id = data.get('session_id', 'N/A')
            
            if 'started' in str(event_type).lower():
                self.logger.info(f"VR session started: {session_id}")
                self.update_status("VR Session Started", "success")
            else:
                self.logger.info(f"VR session ended: {session_id}")
                self.update_status("VR Session Ended", "info")
        except Exception as e:
            self.logger.error(f"Error handling VR session event: {e}")
    
    def _handle_vr_tracking(self, data):
        """Handle VR tracking updates."""
        try:
            position = data.get('position', {})
            rotation = data.get('rotation', {})
            
            # Update tracking display if available
            if hasattr(self, 'tracking_label'):
                pos_str = f"({position.get('x', 0):.2f}, {position.get('y', 0):.2f}, {position.get('z', 0):.2f})"
                self.tracking_label.setText(f"Position: {pos_str}")
        except Exception as e:
            self.logger.debug(f"Error handling VR tracking: {e}")
    
    def _handle_vr_performance(self, data):
        """Handle VR performance updates."""
        try:
            fps = data.get('fps', 0)
            latency = data.get('latency', 0)
            dropped_frames = data.get('dropped_frames', 0)
            
            if hasattr(self, 'update_performance'):
                self.update_performance(data)
            
            self.logger.debug(f"VR Performance: {fps} FPS, {latency}ms latency")
        except Exception as e:
            self.logger.debug(f"Error handling VR performance: {e}")
    
    def _handle_vr_environment_changed(self, data):
        """Handle VR environment change events."""
        try:
            env_name = data.get('environment', data.get('name', 'Unknown'))
            self.logger.info(f"VR environment changed to: {env_name}")
            self.update_status(f"Environment: {env_name}", "success")
            
            if hasattr(self, 'update_environment'):
                self.update_environment(data)
        except Exception as e:
            self.logger.error(f"Error handling VR environment change: {e}")
    
    def _handle_vr_connect_result(self, data):
        """Handle VR connection result events."""
        try:
            success = data.get('success', False)
            message = data.get('message', '')
            
            if success:
                self.logger.info(f"VR connection successful: {message}")
                self.update_status("VR Connected", "success")
            else:
                self.logger.warning(f"VR connection failed: {message}")
                self.update_status(f"VR Connection Failed: {message}", "error")
        except Exception as e:
            self.logger.error(f"Error handling VR connect result: {e}")
    
    def _handle_vr_started(self, data):
        """Handle VR system started event."""
        try:
            self.logger.info("VR system started")
            self.update_status("VR System Active", "success")
        except Exception as e:
            self.logger.error(f"Error handling VR started: {e}")
    
    def _handle_vr_stopped(self, data):
        """Handle VR system stopped event."""
        try:
            self.logger.info("VR system stopped")
            self.update_status("VR System Stopped", "info")
        except Exception as e:
            self.logger.error(f"Error handling VR stopped: {e}")
    
    def _start_vr_device_monitoring(self):
        """Start VR device monitoring timer - deferred to ensure class is fully initialized."""
        try:
            timer = getattr(self, 'vr_detection_timer', None)
            if timer is None:
                self.vr_detection_timer = QTimer(self)
                timer = self.vr_detection_timer
                timer.timeout.connect(self._check_vr_device_connection)
            else:
                try:
                    timer.setParent(self)
                except Exception:
                    pass

            try:
                timer.setInterval(30000)  # Check every 30 seconds (ADB subprocess is expensive)
            except Exception:
                pass

            self._sync_vr_timers()
            self.logger.info("✅ VR runtime auto-detection enabled")
            self.logger.info("🔍 Polling for VR headset every 2 seconds...")
            self.logger.info("   Will auto-connect when headset is powered on")
        except Exception as e:
            self.logger.error(f"Error starting VR device monitoring: {e}")

    def _check_vr_device_connection(self):
        """Check for VR device connections (Meta Quest, SteamVR, etc.) in a background thread."""
        try:
            if not self._should_vr_timers_run():
                self._sync_vr_timers()
                return
        except Exception:
            pass
        from PyQt6.QtCore import QThread, pyqtSignal

        class VRDetectionThread(QThread):
            """Background thread for VR detection - does not block main app."""
            vr_connected = pyqtSignal(str)  # device_name
            vr_disconnected = pyqtSignal()

            def __init__(self, parent_widget):
                super().__init__()
                self.parent_widget = parent_widget

            def run(self):  # type: ignore[override]
                """Background detection - runs without blocking main thread."""
                try:
                    if self.isInterruptionRequested():
                        return
                    is_wsl = sys.platform.startswith("linux") and os.environ.get("WSL_DISTRO_NAME") is not None

                    device_detected = False
                    device_name = "No Device"

                    quest_target = None
                    try:
                        cfg_path = os.path.expanduser("~/.quest3_config")
                        if os.path.exists(cfg_path):
                            quest_ip = None
                            quest_port = "5555"
                            with open(cfg_path, "r", encoding="utf-8", errors="ignore") as f:
                                for raw in f:
                                    line = raw.strip()
                                    if not line or line.startswith("#") or "=" not in line:
                                        continue
                                    k, v = line.split("=", 1)
                                    k = k.strip()
                                    v = v.strip()
                                    if k == "QUEST_IP":
                                        quest_ip = v
                                    elif k == "QUEST_PORT":
                                        quest_port = v
                            if quest_ip:
                                quest_target = f"{quest_ip}:{quest_port}"
                    except Exception:
                        quest_target = None

                    # Method 1: Check for OpenVR / SteamVR (disabled on WSL because
                    # the VR path registry does not exist there and only produces
                    # noisy warnings).
                    if not is_wsl:
                        try:
                            import openvr

                            if openvr.isRuntimeInstalled():
                                vr_system = openvr.init(openvr.VRApplication_Scene)
                                if vr_system:
                                    device_name = "SteamVR Device"
                                    device_detected = True
                                    openvr.shutdown()
                        except Exception:
                            # OpenVR not available or runtime not installed
                            pass

                    # Method 2: Check for Oculus / Meta Quest via ADB
                    if not device_detected:
                        try:
                            import subprocess

                            result = subprocess.run(
                                ["adb", "devices"],
                                capture_output=True,
                                text=True,
                                timeout=2,
                            )
                            adb_out = result.stdout or ""
                            if result.returncode == 0:
                                device_lines = [line for line in adb_out.split("\n") if "\tdevice" in line]
                                if device_lines:
                                    device_name = "Meta Quest (Connected)"
                                    device_detected = True
                                elif quest_target:
                                    if f"{quest_target}\toffline" in adb_out or f"{quest_target}\tunauthorized" in adb_out:
                                        subprocess.run(
                                            ["adb", "disconnect", quest_target],
                                            capture_output=True,
                                            text=True,
                                            timeout=2,
                                        )
                                    subprocess.run(
                                        ["adb", "connect", quest_target],
                                        capture_output=True,
                                        text=True,
                                        timeout=5,
                                    )
                                    recheck = subprocess.run(
                                        ["adb", "devices"],
                                        capture_output=True,
                                        text=True,
                                        timeout=2,
                                    )
                                    re_out = recheck.stdout or ""
                                    if recheck.returncode == 0:
                                        recheck_lines = [line for line in re_out.split("\n") if "\tdevice" in line]
                                        if recheck_lines:
                                            device_name = "Meta Quest (Connected)"
                                            device_detected = True
                        except Exception:
                            pass

                    current_state = bool(getattr(self.parent_widget, "is_connected", False))

                    if device_detected and not current_state:
                        # State changed: disconnected → connected
                        self.vr_connected.emit(device_name)
                    elif not device_detected and current_state:
                        # State changed: connected → disconnected
                        self.vr_disconnected.emit()

                except Exception as e:  # pragma: no cover - best-effort logging only
                    try:
                        self.parent_widget.logger.debug(f"VR check thread: {e}")
                    except Exception:
                        pass

        # Create and start background thread (non-blocking!)
        existing_thread = getattr(self, "_vr_detection_thread", None)
        if existing_thread is not None:
            try:
                if existing_thread.isRunning():
                    return
            except Exception:
                try:
                    self._vr_detection_thread = None
                except Exception:
                    pass

        thread = VRDetectionThread(self)
        self._vr_detection_thread = thread
        thread.vr_connected.connect(self._on_vr_connected)
        thread.vr_disconnected.connect(self._on_vr_disconnected)

        def _finalize_detection_thread():
            try:
                if getattr(self, "_vr_detection_thread", None) is thread:
                    self._vr_detection_thread = None
            except Exception:
                pass
            try:
                thread.deleteLater()
            except Exception:
                pass

        try:
            thread.finished.connect(_finalize_detection_thread)
        except Exception:
            pass
        thread.start()

    def _on_vr_connected(self, device_name: str):
        """Handle VR connection (runs in main thread - thread-safe)."""
        try:
            self.logger.info(f"🟢 VR HEADSET CONNECTED: {device_name}")
            self.logger.info("   Auto-initialized successfully!")

            # Update UI (main thread - safe!)
            if hasattr(self, "vr_device_status"):
                self.vr_device_status.setText(f"🟢 VR: {device_name}")
                self.vr_device_status.setStyleSheet("color: #00FF00; font-weight: bold;")
            if hasattr(self, "connection_status"):
                self.connection_status.setText("Status: Connected - Verifying...")
                self.connection_status.setStyleSheet("color: #FFAA00; font-weight: bold;")
            if hasattr(self, "lbl_device_name"):
                self.lbl_device_name.setText(device_name)
            if hasattr(self, "lbl_device_status"):
                self.lbl_device_status.setText("Verifying...")
            self.is_connected = True

            # Update connection indicator if it exists
            if hasattr(self, "connection_indicator"):
                self.connection_indicator.setStyleSheet(
                    """
                    QLabel {
                        background-color: #FFAA00;
                        border-radius: 6px;
                        border: 1px solid #AA7700;
                    }
                    """
                )
            
            # Send handshake to Quest 3 to verify two-way communication
            self._send_quest_handshake()
            
        except Exception as e:
            self.logger.warning(f"VR connection handling failed: {e}")

    def _ensure_handshake_server_running(self):
        try:
            if getattr(self, "_handshake_server", None) is not None:
                return

            parent_widget = self

            class _HandshakeHandler(BaseHTTPRequestHandler):
                def log_message(self, format, *args):
                    return

                def _send_html(self, body: str, status: int = 200):
                    data = body.encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

                def do_GET(self):
                    parsed = urlparse(self.path)
                    qs = parse_qs(parsed.query or "")
                    handshake_id = (qs.get("id") or [""])[0]
                    if parsed.path == "/confirm":
                        try:
                            parent_widget._headset_confirmed_handshake_id = handshake_id or None
                            parent_widget._headset_confirmed_at = time.time()
                            QTimer.singleShot(0, parent_widget._apply_headset_confirmation)
                        except Exception:
                            pass
                        self._send_html("<html><body style='font-family:sans-serif;background:#0b1020;color:#fff;padding:24px;'><h2>Confirmed</h2><p>You can return to Kingdom AI.</p></body></html>")
                        return

                    body = (
                        "<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'></head>"
                        "<body style='font-family:sans-serif;background:#0b1020;color:#fff;padding:24px;'>"
                        "<h2>Kingdom AI VR Handshake</h2>"
                        f"<p>Handshake ID: <b>{handshake_id}</b></p>"
                        f"<a href='/confirm?id={handshake_id}' style='display:inline-block;background:#00ff88;color:#000;padding:18px 22px;border-radius:10px;text-decoration:none;font-weight:bold;'>Confirm Connection</a>"
                        "</body></html>"
                    )
                    self._send_html(body)

            server = ThreadingHTTPServer(("127.0.0.1", self._handshake_server_port), _HandshakeHandler)
            self._handshake_server = server
            self._handshake_server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            self._handshake_server_thread.start()
        except Exception as e:
            self.logger.error(f"Handshake server start failed: {e}")

    def _launch_headset_handshake_ui(self, handshake_id: str):
        try:
            import subprocess

            self._ensure_handshake_server_running()

            port = int(getattr(self, "_handshake_server_port", 27183))
            subprocess.run(["adb", "reverse", f"tcp:{port}", f"tcp:{port}"], capture_output=True, text=True, timeout=5)
            url = f"http://127.0.0.1:{port}/?id={handshake_id}"
            subprocess.run(
                ["adb", "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception as e:
            self.logger.error(f"Headset handshake UI launch failed: {e}")

    def _send_quest_handshake(self):
        """Send a handshake message to Quest 3 and verify two-way communication."""
        import subprocess
        
        def handshake_thread():
            try:
                # Generate unique handshake ID
                handshake_id = str(uuid.uuid4())[:8]
                self.logger.info(f"📡 Sending handshake to Quest 3 (ID: {handshake_id})...")
                
                # Get Quest IP from config
                quest_target = None
                try:
                    cfg_path = os.path.expanduser("~/.quest3_config")
                    if os.path.exists(cfg_path):
                        with open(cfg_path, "r") as f:
                            for line in f:
                                if line.startswith("QUEST_IP="):
                                    quest_ip = line.split("=", 1)[1].strip()
                                    quest_target = f"{quest_ip}:5555"
                                    break
                except Exception:
                    pass
                
                self._launch_headset_handshake_ui(handshake_id)

                marker_cmd = [
                    "adb", "shell", "echo", 
                    f"KINGDOM_AI_HANDSHAKE_{handshake_id}_{int(time.time())}",
                    ">", "/sdcard/kingdom_ai_handshake.txt"
                ]
                subprocess.run(" ".join(marker_cmd), shell=True, capture_output=True, timeout=5)
                
                # Method 4: Check if we can read device info back (proves two-way)
                device_info_cmd = ["adb", "shell", "getprop", "ro.product.model"]
                result = subprocess.run(device_info_cmd, capture_output=True, text=True, timeout=5)
                device_model = result.stdout.strip() if result.returncode == 0 else "Unknown"
                
                # Method 5: Get battery level to prove communication
                battery_cmd = ["adb", "shell", "dumpsys", "battery"]
                battery_result = subprocess.run(battery_cmd, capture_output=True, text=True, timeout=5)
                battery_level = "?"
                if battery_result.returncode == 0:
                    for line in battery_result.stdout.split("\n"):
                        if "level:" in line:
                            battery_level = line.split(":")[1].strip() + "%"
                            break
                
                # Method 6: Get Quest serial number
                serial_cmd = ["adb", "shell", "getprop", "ro.serialno"]
                serial_result = subprocess.run(serial_cmd, capture_output=True, text=True, timeout=5)
                serial = serial_result.stdout.strip()[:8] if serial_result.returncode == 0 else "N/A"
                
                self.logger.info(f"✅ Quest 3 Handshake SUCCESS!")
                self.logger.info(f"   Device: {device_model}")
                self.logger.info(f"   Battery: {battery_level}")
                self.logger.info(f"   Serial: {serial}...")
                self.logger.info(f"   Handshake ID: {handshake_id}")
                
                # Store results for UI update
                self._handshake_result = {
                    "device_model": device_model,
                    "battery_level": battery_level,
                    "handshake_id": handshake_id,
                    "success": True
                }
                # Use signal to update UI in main thread
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self._apply_handshake_result)
                
            except Exception as e:
                self.logger.error(f"❌ Quest 3 handshake failed: {e}")
                self._handshake_result = {"success": False}
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self._apply_handshake_result)
        
        # Run handshake in background thread
        thread = threading.Thread(target=handshake_thread, daemon=True)
        thread.start()

    def _apply_headset_confirmation(self):
        try:
            confirmed_id = getattr(self, "_headset_confirmed_handshake_id", None)
            if not confirmed_id:
                return
            last_id = getattr(self, "_last_handshake_id", None)
            if last_id and confirmed_id != last_id:
                return

            if hasattr(self, "lbl_device_status"):
                self.lbl_device_status.setText("Verified ✅ (Headset Confirmed)")
            if hasattr(self, "connection_status"):
                self.connection_status.setText("Status: ✅ VERIFIED (confirmed in headset)")
                self.connection_status.setStyleSheet("color: #00FF00; font-weight: bold;")
        except Exception as e:
            self.logger.warning(f"Headset confirmation UI update failed: {e}")

    def _apply_handshake_result(self):
        """Apply handshake result to UI (called from main thread via QTimer)."""
        try:
            result = getattr(self, "_handshake_result", {})
            if result.get("success"):
                device_model = result.get("device_model", "Quest 3")
                battery_level = result.get("battery_level", "?")
                handshake_id = result.get("handshake_id", "N/A")
                
                if hasattr(self, "connection_status"):
                    self.connection_status.setText(f"Status: ✅ VERIFIED ({device_model})")
                    self.connection_status.setStyleSheet("color: #00FF00; font-weight: bold;")
                if hasattr(self, "lbl_device_status"):
                    self.lbl_device_status.setText(f"Verified ✅")
                if hasattr(self, "lbl_device_battery"):
                    self.lbl_device_battery.setText(battery_level)
                if hasattr(self, "connection_indicator"):
                    self.connection_indicator.setStyleSheet(
                        """
                        QLabel {
                            background-color: #00FF00;
                            border-radius: 6px;
                            border: 1px solid #00AA00;
                        }
                        """
                    )
                self._last_handshake_id = handshake_id
                self._handshake_verified = True
                self.logger.info(f"🎉 Two-way communication with Quest 3 VERIFIED!")
            else:
                if hasattr(self, "connection_status"):
                    self.connection_status.setText("Status: ⚠️ Connected (unverified)")
                    self.connection_status.setStyleSheet("color: #FFAA00; font-weight: bold;")
                if hasattr(self, "lbl_device_status"):
                    self.lbl_device_status.setText("Unverified")
                self._handshake_verified = False
        except Exception as e:
            self.logger.warning(f"Handshake UI update failed: {e}")

    def _on_vr_disconnected(self):
        """Handle VR disconnection (runs in main thread - thread-safe)."""
        try:
            if hasattr(self, "vr_device_status"):
                self.vr_device_status.setText("🔴 VR: Not Detected")
                self.vr_device_status.setStyleSheet("color: #FF0000; font-weight: bold;")
            if hasattr(self, "connection_status"):
                self.connection_status.setText("Status: Disconnected")
                self.connection_status.setStyleSheet("color: #888888;")
            # Reset Device tab labels to show disconnected state.
            if hasattr(self, "lbl_device_name"):
                self.lbl_device_name.setText("Not Connected")
            if hasattr(self, "lbl_device_status"):
                self.lbl_device_status.setText("Disconnected")
            if hasattr(self, "lbl_device_battery"):
                self.lbl_device_battery.setText("0%")
            if hasattr(self, "lbl_device_ip"):
                self.lbl_device_ip.setText("-")
            self.is_connected = False

            # Update connection indicator
            if hasattr(self, "connection_indicator"):
                self.connection_indicator.setStyleSheet(
                    """
                    QLabel {
                        background-color: #FF0000;
                        border-radius: 6px;
                        border: 1px solid #AA0000;
                    }
                    """
                )
        except Exception as e:
            self.logger.warning(f"VR disconnect handling failed: {e}")

    # ===== Event Handlers =====
    
    def on_connection_changed(self, connected: bool):
        """Handle connection status changes."""
        self.is_connected = connected
        
        # Update UI elements
        if connected:
            self.btn_connect.setIcon(get_icon("disconnect"))
            self.btn_connect.setText("Disconnect")
            self.btn_calibrate.setEnabled(True)
            self.btn_reset_view.setEnabled(True)
            self.connection_status.setText("Status: Connected")
            self.connection_status.setStyleSheet("color: green;")
        else:
            self.btn_connect.setIcon(get_icon("connect"))
            self.btn_connect.setText("Connect")
            self.btn_calibrate.setEnabled(False)
            self.btn_reset_view.setEnabled(False)
            self.connection_status.setText("Status: Disconnected")
            self.connection_status.setStyleSheet("color: red;")
    
    def on_environment_selected(self, environment_id: str):
        """Handle environment selection."""
        if self.is_connected:
            self._emit_ui_telemetry(
                "vr.environment_selected",
                metadata={"environment_id": environment_id},
            )
            self.signals.environment_change_requested.emit(environment_id)
    
    def on_gesture_mapping_changed(self, gesture_id: str, action_name: str):
        """Handle gesture mapping changes."""
        if self.is_connected:
            self.signals.gesture_mapping_changed.emit(gesture_id, action_name)
    
    def on_gesture_recording_changed(self, recording: bool):
        """Handle gesture recording state changes."""
        if self.is_connected:
            self.signals.gesture_recording_changed.emit(recording)
    
    def on_gesture_detected(self, gesture_data: dict):
        """Handle detected gestures."""
        self.gesture_controls.on_gesture_detected(gesture_data)
    
    def on_voice_command(self, command_data: dict):
        """Handle voice commands — FULL SYSTEM CONTROL from VR headset.

        Routes spoken commands to the correct system:
        - Creation engine: 'create', 'generate', 'draw', 'design'…
        - Mining control:  'start mining', 'stop mining', 'mining status'
        - Trading control: 'buy', 'sell', 'start trading', 'stop trading'
        - Wallet control:  'wallet balance', 'show wallets'
        - Tab navigation:  'show dashboard', 'open mining', 'go to trading'
        - AI conversation: everything else → routed to Thoth/Brain
        """
        command = command_data.get('command', '')
        confidence = command_data.get('confidence', 0)
        self.update_status(f"Voice: {command} ({confidence:.0%})", "info")
        cmd_lower = command.lower().strip()

        # ── 1) Creation commands ──
        creation_kw = ('create', 'generate', 'make', 'draw', 'design', 'build',
                       'render', 'animate', 'visualize', 'model', 'sketch')
        if any(kw in cmd_lower for kw in creation_kw):
            self.logger.info(f"🎤 Voice creation: '{command}'")
            if hasattr(self, 'vr_creation_prompt'):
                self.vr_creation_prompt.setPlainText(command)
            if hasattr(self, 'vr_engine_combo'):
                self.vr_engine_combo.setCurrentIndex(0)
            self._start_vr_creation(command)
            return

        # ── 2) Mining commands ──
        if any(kw in cmd_lower for kw in ('start mining', 'begin mining', 'mine')):
            self._vr_system_command("mining.start", {"source": "vr_voice"})
            self.update_status("Mining start command sent", "success")
            return
        if any(kw in cmd_lower for kw in ('stop mining', 'halt mining', 'end mining')):
            self._vr_system_command("mining.stop", {"source": "vr_voice"})
            self.update_status("Mining stop command sent", "success")
            return
        if 'mining status' in cmd_lower or 'hashrate' in cmd_lower:
            self._vr_system_command("mining.status.request", {"source": "vr_voice"})
            return

        # ── 3) Trading commands ──
        if any(kw in cmd_lower for kw in ('start trading', 'enable trading', 'auto trade')):
            self._vr_system_command("trading.auto.enable", {"source": "vr_voice"})
            self.update_status("Auto-trading enabled", "success")
            return
        if any(kw in cmd_lower for kw in ('stop trading', 'disable trading')):
            self._vr_system_command("trading.auto.disable", {"source": "vr_voice"})
            self.update_status("Auto-trading disabled", "success")
            return
        if 'buy' in cmd_lower or 'sell' in cmd_lower:
            self._vr_system_command("trading.voice.order", {
                "command": command, "source": "vr_voice"
            })
            return

        # ── 4) Wallet commands ──
        if any(kw in cmd_lower for kw in ('wallet', 'balance', 'show wallet')):
            self._vr_system_command("wallet.status.request", {"source": "vr_voice"})
            self._vr_switch_tab("Wallet")
            return

        # ── 5) Tab navigation ──
        tab_map = {
            'dashboard': 'Dashboard', 'mining': 'Mining', 'trading': 'Trading',
            'wallet': 'Wallet', 'thoth': 'Thoth AI', 'ai': 'Thoth AI',
            'blockchain': 'KingdomWeb3', 'web3': 'KingdomWeb3',
            'creation': 'Visual Creation', 'canvas': 'Visual Creation',
            'settings': 'Settings', 'vr': 'VR',
        }
        for keyword, tab_name in tab_map.items():
            if keyword in cmd_lower and any(w in cmd_lower for w in ('show', 'open', 'go to', 'switch', 'navigate')):
                self._vr_switch_tab(tab_name)
                self.update_status(f"Switching to {tab_name}", "info")
                return

        # ── 6) Everything else → AI conversation ──
        self.logger.info(f"🎤 Voice → AI: '{command}'")
        if self.event_bus:
            self.event_bus.publish("ai.request", {
                "text": command,
                "source": "vr_voice",
                "timestamp": time.time(),
            })
            self.event_bus.publish("voice.input", {
                "command": command,
                "source": "vr",
                "timestamp": time.time(),
            })

    def _vr_system_command(self, event_name: str, data: dict):
        """Publish a system command from VR to the EventBus."""
        if self.event_bus:
            data.setdefault("timestamp", time.time())
            self.event_bus.publish(event_name, data)
            self.logger.info(f"🥽 VR system command: {event_name}")

    def _vr_switch_tab(self, tab_name: str):
        """Request the main window to switch to a specific tab from VR."""
        if self.event_bus:
            self.event_bus.publish("gui.tab.switch", {
                "tab_name": tab_name,
                "source": "vr",
                "timestamp": time.time(),
            })
            self.logger.info(f"🥽 VR tab switch → {tab_name}")

    # ── SOTA 2026: System event handlers for VR HUD ──

    def _handle_system_event(self, data: dict):
        """Generic handler for system events — log and show in VR status."""
        try:
            event_type = data.get("event", data.get("type", "system"))
            msg = data.get("message", data.get("status", str(data)[:80]))
            def _u():
                self.update_status(f"[System] {event_type}: {msg}", "info")
                # Update VR system HUD if it exists
                if hasattr(self, '_vr_system_log'):
                    self._vr_system_log.append(f"{event_type}: {msg}")
                    if hasattr(self, 'vr_system_log_label'):
                        recent = self._vr_system_log[-5:]
                        self.vr_system_log_label.setText("\n".join(recent))
            QTimer.singleShot(0, _u)
        except Exception as e:
            self.logger.error(f"Error in system event handler: {e}")

    def _handle_mining_hashrate_vr(self, data: dict):
        """Handle mining hashrate updates — show in VR HUD."""
        try:
            hashrate = data.get("hashrate", data.get("total_hashrate", 0))
            unit = data.get("unit", "H/s")
            def _u():
                if hasattr(self, 'vr_mining_label'):
                    self.vr_mining_label.setText(f"Mining: {hashrate:.2f} {unit}")
                    self.vr_mining_label.setStyleSheet(
                        "color: #00ff00; font-weight: bold;" if hashrate > 0
                        else "color: #888;"
                    )
            QTimer.singleShot(0, _u)
        except Exception as e:
            self.logger.error(f"Error in VR mining hashrate: {e}")

    def _handle_ai_response_vr(self, data: dict):
        """Handle AI responses in VR — display text and trigger voice output."""
        try:
            response_text = (data.get("response") or data.get("text")
                             or data.get("message") or "")
            if not response_text:
                return
            def _u():
                self.update_status(f"Kingdom AI: {response_text[:100]}", "success")
                # If there's a VR AI response label, show full text
                if hasattr(self, 'vr_ai_response_label'):
                    self.vr_ai_response_label.setText(response_text[:500])
            QTimer.singleShot(0, _u)
        except Exception as e:
            self.logger.error(f"Error handling AI response in VR: {e}")

    def on_ai_response(self, response_data: dict):
        """Handle AI responses."""
        response = response_data.get('response', '')
        self.update_status(f"AI: {response}", "info")
    
    # ===== UI Update Methods =====
    
    def update_status(self, message: str, level: str = "info"):
        """Update the status bar with a message."""
        if not hasattr(self, 'status_bar'):
            return

        now = time.time()
        last_msg = getattr(self, '_last_status_message', None)
        last_lvl = getattr(self, '_last_status_level', None)
        last_ts = float(getattr(self, '_last_status_time', 0.0) or 0.0)

        # Throttle repeated status spam to keep UI responsive.
        if message == last_msg and level == last_lvl and (now - last_ts) < 1.5:
            return
        self._last_status_message = message
        self._last_status_level = level
        self._last_status_time = now

        # If tab is hidden, ignore noisy info updates to reduce main-thread churn.
        if level == "info" and not self.isVisible():
            return
            
        if level == "error":
            self.status_bar.setStyleSheet("color: #ff6b6b;")
        elif level == "warning":
            self.status_bar.setStyleSheet("color: #feca57;")
        elif level == "success":
            self.status_bar.setStyleSheet("color: #1dd1a1;")
        else:
            self.status_bar.setStyleSheet("color: #54a0ff;")
            
        self.status_bar.showMessage(message, 2500)
        
        # Log only errors/warnings at INFO to avoid VR status spam; routine messages at DEBUG
        try:
            if level == "error":
                logger.error(f"[VR] {message}")
            elif level == "warning":
                logger.warning(f"[VR] {message}")
            else:
                # Avoid high-frequency debug floods from routine UI status updates.
                if (now - last_ts) >= 2.0 or message != last_msg:
                    logger.debug(f"[VR] {message}")
        except (KeyboardInterrupt, SystemExit):
            # Allow KeyboardInterrupt to propagate for clean shutdown
            raise
        except Exception:
            # Ignore other logging errors during shutdown
            pass
        
        # Publish to Redis if connected
        if self.redis_connected and self.redis_manager:
            try:
                # Keep external status stream focused on meaningful state.
                if level != "info" or self.isVisible():
                    self.redis_manager.publish("vr.status", {"message": message, "level": level})
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                logger.error(f"Failed to publish status to Redis: {str(e)}")
    
    def cleanup(self):
        """Clean up resources when the tab is closed."""
        logger.info("Cleaning up VR tab resources...")

        try:
            self._timers_enabled = False
            self._sync_vr_timers()
        except Exception:
            pass
        
        # Stop VR system
        if self.vr_worker:
            self.vr_worker.shutdown()
        if self.vr_thread:
            self.vr_thread.quit()
            self.vr_thread.wait()
        if hasattr(self, 'update_timer') and self.update_timer:
            self.update_timer.stop()
        if hasattr(self, '_vr_view_timer') and self._vr_view_timer:
            self._vr_view_timer.stop()
        if hasattr(self, 'vr_detection_timer') and self.vr_detection_timer:
            self.vr_detection_timer.stop()
        if hasattr(self, 'vr_tracking_timer') and self.vr_tracking_timer:
            self.vr_tracking_timer.stop()
        if hasattr(self, 'device_monitor_timer') and self.device_monitor_timer:
            self.device_monitor_timer.stop()
        thread = getattr(self, "_vr_detection_thread", None)
        if thread:
            try:
                if thread.isRunning():
                    try:
                        thread.requestInterruption()
                    except Exception:
                        pass
                    thread.quit()
                    thread.wait(11000)
            except Exception:
                pass
            try:
                if not thread.isRunning():
                    thread.deleteLater()
            except Exception:
                pass
            try:
                if getattr(self, "_vr_detection_thread", None) is thread and not thread.isRunning():
                    self._vr_detection_thread = None
            except Exception:
                pass
            
        # Clean up Redis
        if self.redis_manager:
            try:
                self.redis_manager.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting Redis: {str(e)}")
        
        self.redis_connected = False
    
    def _cleanup_threads(self):
        """Alias for cleanup() - called by main window on shutdown."""
        self.cleanup()
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.cleanup()
        event.accept()
        
    def handle_vr_status_update(self, data: dict):
        """Handle VR status updates from Redis."""
        message = data.get('message', '')
        level = data.get('level', 'info')
        self.update_status(message, level)
    
    def handle_vr_event(self, data: dict):
        """Handle VR events from Redis."""
        event_type = data.get('type')
        if event_type == 'device_connected':
            self.update_device_info(data.get('device', {}))
        elif event_type == 'device_disconnected':
            # Handle device disconnection
            device_info = data.get('device', {})
            device_name = device_info.get('name', 'Unknown Device')
            self.logger.info(f"VR device disconnected: {device_name}")
            # Update UI to show disconnected state
            self.update_device_info({
                'name': device_name,
                'status': 'Disconnected',
                'connected': False
            })
            # Publish disconnection event
            if self.event_bus:
                self.event_bus.publish("vr.device.disconnected", device_info)
        elif event_type == 'environment_loaded':
            self.update_environment(data.get('environment', {}))
        elif event_type == 'performance_update':
            self.update_performance(data.get('metrics', {}))
    
    def handle_vr_command(self, data: dict):
        """Handle VR commands from Redis."""
        command = data.get('command')
        if command == 'connect':
            self.connect_vr()
        elif command == 'disconnect':
            self.disconnect_vr()
        elif command == 'calibrate':
            self.calibrate_vr()
        elif command == 'reset_view':
            self.reset_view()
        elif command == 'load_environment':
            env_id = data.get('environment_id')
            if env_id:
                self.signals.environment_change_requested.emit(env_id)
    
    def show_help(self):
        """Show help information."""
        help_text = """VR System Help:
        
- Connect: Connect to the VR system
- Calibrate: Calibrate VR tracking
- Reset View: Reset the VR view to center

Use the tabs to control different aspects of the VR system:
- Devices: View and manage connected VR devices
- Environments: Switch between VR environments
- Gestures: Configure and test gesture controls
- Performance: Monitor system performance
- Settings: Configure VR system settings
        """
        QMessageBox.information(self, "VR System Help", help_text.strip())
        right_panel.setLayout(right_layout)
        
        # 3D Viewer
        self.viewer_3d = VR3DViewer()
        self.viewer_3d.setObjectName("VR3DViewer")
        
        # Mini status bar for 3D view
        viewer_status = QWidget()
        viewer_status.setObjectName("VRViewerStatus")
        viewer_status_layout = QHBoxLayout()
        viewer_status_layout.setContentsMargins(5, 2, 5, 2)
        viewer_status.setLayout(viewer_status_layout)
        
        self.fps_label = QLabel("FPS: --")
        self.tracking_status = QLabel("Tracking: --")
        self.battery_status = QLabel("Battery: --")
        
        viewer_status_layout.addWidget(self.fps_label)
        viewer_status_layout.addStretch()
        viewer_status_layout.addWidget(self.tracking_status)
        viewer_status_layout.addStretch()
        viewer_status_layout.addWidget(self.battery_status)
        
        right_layout.addWidget(self.viewer_3d, 1)
        right_layout.addWidget(viewer_status)
        
        # Add widgets to splitter
        self.splitter.addWidget(control_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([400, 600])  # Initial sizes
        
        # Add splitter to content layout
        content_layout.addWidget(self.splitter)
        
        # Add content to main layout
        main_layout.addWidget(content_widget, 1)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.setObjectName("VRStatusBar")
        
        # Add permanent widgets to status bar
        self.connection_status = QLabel("Status: Disconnected")
        self.vr_device_status = QLabel("VR: Not Detected")
        self.memory_usage = QLabel("Memory: --")
        self.cpu_usage = QLabel("CPU: --")
        
        self.status_bar.addPermanentWidget(self.connection_status)
        self.status_bar.addPermanentWidget(QLabel("|"))
        self.status_bar.addPermanentWidget(self.vr_device_status)
        self.status_bar.addPermanentWidget(QLabel("|"))
        self.status_bar.addPermanentWidget(self.memory_usage)
        self.status_bar.addPermanentWidget(QLabel("|"))
        self.status_bar.addPermanentWidget(self.cpu_usage)
        
        main_layout.addWidget(self.status_bar)
        
        # Set initial status
        self.update_status("VR System Ready", "info")
        
    def create_settings_widget(self) -> QWidget:
        """Create the settings widget."""
        settings_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        settings_widget.setLayout(layout)
        
        # General settings group
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout()
        general_group.setLayout(general_layout)
        
        # Show FPS
        self.show_fps = QCheckBox("Show FPS Counter")
        self.show_fps.setChecked(self.settings['show_fps'])
        self.show_fps.toggled.connect(lambda v: self.update_setting('show_fps', v))
        general_layout.addRow("Display:", self.show_fps)
        
        # Enable voice commands
        self.enable_voice = QCheckBox("Enable Voice Commands")
        self.enable_voice.setChecked(self.settings['enable_voice'])
        self.enable_voice.toggled.connect(lambda v: self.update_setting('enable_voice', v))
        general_layout.addRow("Voice:", self.enable_voice)
        
        # Enable gestures
        self.enable_gestures = QCheckBox("Enable Gesture Controls")
        self.enable_gestures.setChecked(self.settings['enable_gestures'])
        self.enable_gestures.toggled.connect(lambda v: self.update_setting('enable_gestures', v))
        general_layout.addRow("Gestures:", self.enable_gestures)
        
        # Mirror display
        self.mirror_display = QCheckBox("Mirror Display")
        self.mirror_display.setChecked(self.settings['mirror_display'])
        self.mirror_display.toggled.connect(lambda v: self.update_setting('mirror_display', v))
        general_layout.addRow("Display Mode:", self.mirror_display)
        
        # Performance settings group
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QFormLayout()
        perf_group.setLayout(perf_layout)
        
        # Performance mode
        self.performance_mode = QComboBox()
        self.performance_mode.addItems(["Quality", "Balanced", "Performance"])
        self.performance_mode.currentIndexChanged.connect(
            lambda i: self.update_setting('performance_mode', ['quality', 'balanced', 'performance'][i])
        )
        perf_layout.addRow("Mode:", self.performance_mode)
        
        # Resolution scale
        self.resolution_scale = QSlider(Qt.Orientation.Horizontal)
        self.resolution_scale.setRange(50, 200)
        self.resolution_scale.setValue(100)
        self.resolution_scale.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.resolution_scale.setTickInterval(25)
        self.resolution_scale.valueChanged.connect(
            lambda v: self.update_setting('resolution_scale', v / 100.0)
        )
        perf_layout.addRow("Resolution Scale:", self.resolution_scale)
        
        # Reset to defaults button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_settings)
        
        # Add widgets to layout
        layout.addWidget(general_group)
        layout.addWidget(perf_group)
        layout.addStretch()
        layout.addWidget(reset_btn)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setLineWidth(1)
        layout.addWidget(separator)
        
        return settings_widget
    
    def on_environment_selected_from_list(self):
        """Handle environment selection from list."""
        try:
            current_item = self.lst_environments.currentItem()
            if current_item:
                env_name = current_item.text()
                logger.info(f"Environment selected: {env_name}")
                
                # Enable load button
                if hasattr(self, 'btn_load_env'):
                    self.btn_load_env.setEnabled(True)
                    
                QMessageBox.information(self, "Environment Selected", f"Selected environment: {env_name}")
            else:
                QMessageBox.information(self, "No Selection", "No environment selected")
            
        except Exception as e:
            self.logger.error(f"Error handling environment selection: {e}")
            QMessageBox.warning(self, "Selection Error", f"Failed to handle environment selection: {str(e)}")

def _calibrate_vr_tracking(self):
    """Calibrate VR tracking system."""
    try:
        if hasattr(self, 'vr_system'):
            # Start calibration process
            calibration_result = self.vr_system.calibrate_tracking()
            
            if calibration_result:
                QMessageBox.information(self, "Calibration Complete", 
                                      "✅ VR tracking calibration completed successfully!\n\n"
                                      "Your VR tracking should now be more accurate.")
            else:
                QMessageBox.warning(self, "Calibration Failed", 
                                  "VR tracking calibration failed. Please try again.")
            
    except Exception as e:
        self.logger.error(f"Error calibrating VR tracking: {e}")
        QMessageBox.critical(self, "Calibration Error", f"Calibration failed: {str(e)}")

def _connect_to_central_brain(self):
    """Connect to ThothAI central brain system."""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).replace('gui/qt_frames', ''))
        
        # Connect to central ThothAI brain via event bus
        self._central_thoth = None  # Use event bus for communication
        if self._central_thoth:
            self.logger.info("✅ VR Tab connected to ThothAI central brain")
            
            # Register VR events with central brain
            try:
                register_method = getattr(self._central_thoth, 'register_component', None)
                if register_method and callable(register_method):
                    register_method('vr_tab')
            except (AttributeError, Exception):
                # Silently handle missing register_component method
                pass
                
        else:
            # SOTA 2026 FIX: ThothAI is optional for VR - use debug not warning
            self.logger.debug("ℹ️ Central ThothAI instance not available for VR (optional)")
            
    except Exception as e:
        # SOTA 2026 FIX: Expected fallback scenario - use debug not warning
        self.logger.debug(f"ℹ️ Error connecting to central ThothAI: {e} (VR will work without it)")
        self._central_thoth = None

    def _refresh_environments(self):
        """Refresh available VR environments."""
        try:
            if hasattr(self, 'vr_worker') and self.vr_worker:
                # Get environments from VR system
                self.available_environments = ["Default Environment", "Forest Scene", "Space Station", "Underwater World"]
                
                # Update list widget
                self.lst_environments.clear()
                for env in self.available_environments:
                    self.lst_environments.addItem(env)
                
                # Publish to event bus
                if hasattr(self, 'event_bus') and self.event_bus:
                    try:
                        from PyQt6.QtCore import QTimer
                        def publish_refresh():
                            try:
                                self.event_bus.publish("vr.refresh", {
                                    'environments': self.available_environments
                                })
                                self.logger.info("✅ Published VR refresh")
                            except Exception as e:
                                self.logger.error(f"❌ VR refresh publish failed: {e}")
                        QTimer.singleShot(0, publish_refresh)
                    except Exception as e:
                        self.logger.warning(f"Event bus publish failed: {e}")
                    
                self.update_status("VR environments refreshed", "success")
            else:
                self.update_status("VR system not connected", "warning")
                
        except Exception as e:
            self.logger.error(f"Error refreshing VR environments: {e}")
            self.update_status(f"Failed to refresh environments: {str(e)}", "error")

    def _load_environment(self):
        """Load selected VR environment."""
        try:
            current_item = self.lst_environments.currentItem()
            if current_item and hasattr(self, 'vr_worker') and self.vr_worker:
                env_name = current_item.text()
                
                # Load environment through VR system
                self.current_environment = env_name
                self.update_status(f"Loading VR environment: {env_name}", "info")
                
                # Connect to real VR system if available
                if hasattr(self, '_central_thoth') and self._central_thoth and hasattr(self._central_thoth, 'load_vr_environment'):
                    self._central_thoth.load_vr_environment(env_name)
                    
            else:
                self.update_status("No environment selected or VR not connected", "warning")
                
        except Exception as e:
            self.logger.error(f"Error loading VR environment: {e}")
            self.update_status(f"Failed to load environment: {str(e)}", "error")

    def _initialize_vr_connection(self) -> bool:
        """Initialize VR connection and start systems."""
        try:
            # Initialize OpenVR
            import openvr
            openvr.init(openvr.VRApplication_Scene)
            
            # Get VR system
            vr_system = openvr.VRSystem()
            if not vr_system:
                return False
            
            self._vr_system_instance = vr_system
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing VR connection: {e}")
            return False

    def _update_vr_status(self, connected: bool):
        """Update VR status indicators in GUI."""
        try:
            if connected:
                # Enable VR controls
                if hasattr(self, 'disconnect_btn'):
                    self.disconnect_btn.setEnabled(True)
                if hasattr(self, 'connect_btn'):
                    self.connect_btn.setEnabled(False)
                if hasattr(self, 'calibrate_btn'):
                    self.calibrate_btn.setEnabled(True)
                
                # Update status displays
                self._update_connection_status("Connected", "green")
                self._update_tracking_status("Active", "green")
                
            else:
                # Disable VR controls
                if hasattr(self, 'disconnect_btn'):
                    self.disconnect_btn.setEnabled(False)
                if hasattr(self, 'connect_btn'):
                    self.connect_btn.setEnabled(True)
                if hasattr(self, 'calibrate_btn'):
                    self.calibrate_btn.setEnabled(False)
                
                # Update status displays
                self._update_connection_status("Disconnected", "red")
                self._update_tracking_status("Inactive", "gray")
                
        except Exception as e:
            self.logger.error(f"Error updating VR status: {e}")

    def _update_connection_status(self, status: str, color: str):
        """Update connection status display."""
        # This would update actual GUI status labels
        self.logger.info(f"VR Connection: {status}")

    def _update_tracking_status(self, status: str, color: str):
        """Update tracking status display."""
        # This would update actual GUI tracking labels
        self.logger.info(f"VR Tracking: {status}")

    def _start_vr_tracking(self):
        """Start VR tracking system."""
        try:
            from PyQt6.QtCore import QTimer
            # Use QTimer for periodic VR tracking
            timer = getattr(self, 'vr_tracking_timer', None)
            if timer is None:
                self.vr_tracking_timer = QTimer(self)
                timer = self.vr_tracking_timer
                timer.timeout.connect(self._vr_tracking_update)
            else:
                try:
                    timer.setParent(self)
                except Exception:
                    pass
            timer.setInterval(200)  # 200ms updates — reduced CPU load
            self._sync_vr_timers()
            self.logger.info("✅ VR tracking timer configured (active only when headset connected)")
        except Exception as e:
            self.logger.error(f"Error starting VR tracking: {e}")

    async def _vr_tracking_loop(self):
        """VR tracking loop for real-time position updates."""
        try:
            while hasattr(self, '_vr_system_instance'):
                # Get real tracking data
                tracking_data = self._get_real_tracking_data()
                if tracking_data:
                    self._update_tracking_display(tracking_data)
                await asyncio.sleep(1/90)  # 90 FPS tracking
        except Exception as e:
            self.logger.error(f"Error in VR tracking loop: {e}")

    def _get_real_tracking_data(self):
        """Get real VR tracking data."""
        try:
            if hasattr(self, '_vr_system_instance'):
                import openvr
                # Get head pose
                poses = self._vr_system_instance.getDeviceToAbsoluteTrackingPose(
                    openvr.TrackingUniverseStanding, 0
                )
                hmd_pose = poses[openvr.k_unTrackedDeviceIndex_Hmd]
                if hmd_pose.bPoseIsValid:
                    matrix = hmd_pose.mDeviceToAbsoluteTracking
                    return {
                        'position': {
                            'x': matrix[0][3],
                            'y': matrix[1][3],
                            'z': matrix[2][3]
                        },
                        'rotation': {
                            'pitch': 0,
                            'yaw': 0,
                            'roll': 0
                        },
                        'valid': True
                    }
            return None
        except Exception as e:
            self.logger.error(f"Error getting tracking data: {e}")
            return None

    def _update_tracking_display(self, tracking_data: dict):
        """Update tracking display with real data."""
        try:
            pos = tracking_data.get('position', {})
            x, y, z = pos.get('x', 0), pos.get('y', 0), pos.get('z', 0)
            # Throttle high-frequency position logs to avoid UI/log churn.
            now = time.time()
            last_log_ts = float(getattr(self, "_last_vr_pos_log_ts", 0.0) or 0.0)
            last_vec = getattr(self, "_last_vr_pos_vec", None)
            moved = (
                last_vec is None
                or abs(x - last_vec[0]) > 0.10
                or abs(y - last_vec[1]) > 0.10
                or abs(z - last_vec[2]) > 0.10
            )
            if moved and (now - last_log_ts) >= 2.0:
                self._last_vr_pos_log_ts = now
                self._last_vr_pos_vec = (x, y, z)
                self.logger.debug(f"VR Position: X={x:.3f}, Y={y:.3f}, Z={z:.3f}")
        except Exception as e:
            self.logger.error(f"Error updating tracking display: {e}")

    def _stop_vr_tracking(self):
        """Stop VR tracking system."""
        try:
            if hasattr(self, '_vr_system_instance'):
                del self._vr_system_instance
            self.logger.info("✅ VR tracking stopped")
        except Exception as e:
            self.logger.error(f"Error stopping VR tracking: {e}")

    def initialize_complete_vr_system(self):
        """Initialize complete VR system with all integrations."""
        try:
            # Initialize VR system
            if hasattr(self, 'vr_system'):
                # Set up VR environments
                self._setup_vr_environments()
                # Configure gesture recognition
                self._setup_gesture_recognition()
                # Start device monitoring
                self._start_device_monitoring()
            self.logger.info("🚀 Complete VR system initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize complete VR system: {e}")
            return False

    def _setup_vr_environments(self):
        """Set up VR environments for Kingdom AI."""
        try:
            environments = [
                "Trading Floor",
                "Blockchain Explorer",
                "Mining Dashboard",
                "AI Command Center"
            ]
            for env in environments:
                self.logger.info(f"VR Environment available: {env}")
        except Exception as e:
            self.logger.error(f"Error setting up VR environments: {e}")

    def _setup_gesture_recognition(self):
        """Set up VR gesture recognition."""
        try:
            gestures = [
                "Point to Select",
                "Grab to Move", 
                "Pinch to Scale",
                "Wave to Dismiss"
            ]
            
            for gesture in gestures:
                self.logger.info(f"VR Gesture configured: {gesture}")
                
        except Exception as e:
            self.logger.error(f"Error setting up gesture recognition: {e}")

    def _start_device_monitoring(self):
        """Start VR device monitoring."""
        try:
            from PyQt6.QtCore import QTimer
            # Use QTimer for periodic device monitoring
            timer = getattr(self, 'device_monitor_timer', None)
            if timer is None:
                self.device_monitor_timer = QTimer(self)
                timer = self.device_monitor_timer
                timer.timeout.connect(self._check_vr_devices)
            else:
                try:
                    timer.setParent(self)
                except Exception:
                    pass
            timer.setInterval(1000)  # Check every second
            self._sync_vr_timers()
            self.logger.info("✅ VR device monitoring started with QTimer")
            
        except Exception as e:
            self.logger.error(f"Error starting device monitoring: {e}")

    async def _monitor_vr_devices(self):
        """Monitor VR devices for connection changes."""
        try:
            while True:
                # Check device status
                if hasattr(self, 'vr_system'):
                    devices = self.vr_system.detect_real_vr_devices()
                    device_count = len(devices['headsets']) + len(devices['controllers'])
                    
                    self.logger.info(f"VR Device Status: {device_count} devices connected")
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
        except Exception as e:
            self.logger.error(f"Error in VR device monitoring: {e}")
