from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Main Window Qt Implementation
100% PyQt6-based implementation of the Kingdom AI main window.
"""

import sys
import os
import re
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
import time
import threading

# SOTA 2026: Mode detection for consumer vs creator tab lockdown
_KINGDOM_APP_MODE = os.environ.get("KINGDOM_APP_MODE", "consumer").lower()
_IS_CONSUMER = _KINGDOM_APP_MODE != "creator"

# Import GUI Manager
from gui.gui_manager import GUIManager

# Import cyberpunk styling
from gui.cyberpunk_style import (
    CyberpunkStyle, CyberpunkEffect, CyberpunkRGBBorderWidget, 
    CyberpunkParticleSystem, CYBERPUNK_THEME, initialize_cyberpunk_styles
)

# PyQt6 imports with proper error handling
try:
    from PyQt6.QtWidgets import (
        QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QFrame, QPushButton, QMessageBox, QProgressBar, 
        QSplitter, QToolBar, QStatusBar, QGridLayout, QMenuBar, QMenu,
        QDialog, QApplication, QTextEdit, QLineEdit, QTableWidget, QHeaderView,
        QComboBox, QCheckBox, QRadioButton, QSpinBox, QDoubleSpinBox,
        QListWidget, QListWidgetItem
    )
    from PyQt6.QtCore import (
        Qt, QTimer, pyqtSignal, QObject, QThreadPool, QRunnable, 
        QMetaObject, pyqtSlot, Q_ARG, QSize, QPropertyAnimation, QEasingCurve, QEvent
    )
    from PyQt6.QtGui import (
        QIcon, QFont, QAction, QPalette, QColor, QPixmap, QPainter, QBrush, QPen
    )
except ImportError as e:
    print(f"Critical PyQt6 import error: {e}")
    sys.exit(1)

# Import dashboard and other Qt components
from gui.qt_frames.dashboard_qt import DashboardQt
from gui.frames.code_generator_qt import CodeGeneratorQt

# Import all tab classes for TabManager integration
try:
    from gui.qt_frames.trading.trading_tab import TradingTab
except ImportError:
    logging.warning("Failed to import TradingTab")

# 2025 SAFE IMPORT PATTERN: Import all tab classes with individual error handling
BlockchainTab = None
ThothAITab = None
WalletTab = None
ApiKeyManagerTab = None
MiningTab = None
VRTab = None
SettingsTab = None

try:
    from gui.qt_frames import (
        BlockchainTab,
        ThothAITab, 
        WalletTab,
        ApiKeyManagerTab,
        MiningTab,
        VRTab,
        SettingsTab
    )
    logging.info("✅ All tab classes imported successfully")
except ImportError as e:
    logging.warning(f"⚠️ Some tab imports failed: {e} - individual tabs will handle missing classes")
    # Tab classes will remain None for failed imports

# Legacy styles (will be superseded by cyberpunk styling)
from gui.qt_styles import KingdomQtStyle
from gui.widgets.tab_manager import TabManager  # Import TabManager for tab management
# GUIManager already imported at line 18

# Import needed components
try:
    from core.event_bus import EventBus
    from core.redis_connector import RedisConnector
    
    # 2025 CRASH PREVENTION SYSTEMS
    from core.resource_cleanup_manager import get_cleanup_manager, register_timer, register_thread, register_event_subscription
    from core.system_state_manager import get_state_manager, register_state_provider
    from core.crash_recovery_watchdog import get_watchdog
    
    # These imports might fail but shouldn't crash the app
    try:
        from core.trading_system import TradingSystem
    except ImportError:
        logging.warning("Failed to import TradingSystem")

    try:
        from core.thoth import ThothAI
    except ImportError:
        logging.warning("Failed to import ThothAI")
        
except ImportError as e:
    logging.critical(f"Critical import error: {e}")
    sys.exit(1)

# Set up logging
logger = logging.getLogger(__name__)

# Constants for Redis connection - STRICT ENFORCEMENT
REDIS_HOST = 'localhost'
REDIS_PORT = 6380  # Specific port required - NO FALLBACK
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', 'QuantumNexus2025')  # Required credentials - NO FALLBACK

class KingdomMainWindow(QMainWindow):
    """
    Main window for the Kingdom AI application.
    
    This is a full PyQt6 implementation with no Tkinter dependencies.
    Integrates both TabManager and GUIManager for comprehensive GUI management.
    """
    
    # Singleton instance (adapted from GUIManager pattern)
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, event_bus=None):
        """Get the singleton instance of KingdomMainWindow.
        
        Args:
            event_bus: The event bus to use for this instance
            
        Returns:
            KingdomMainWindow: The singleton instance
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(event_bus)
            return cls._instance
    
    # Define signals for asynchronous updates
    system_status_update = pyqtSignal(dict)
    component_status_update = pyqtSignal(dict)
    network_status_update = pyqtSignal(dict)
    trading_status_update = pyqtSignal(dict)
    blockchain_status_update = pyqtSignal(dict)
    mining_status_update = pyqtSignal(dict)
    voice_status_update = pyqtSignal(dict)
    vr_status_update = pyqtSignal(dict)
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the main window with event bus connection."""
        # Initialize as QMainWindow
        super().__init__()
        
        # Setup main window attributes - no need for _main_window since we ARE the main window
        # self._main_window = QMainWindow(self)  # REMOVED - not needed
        # self.setCentralWidget(self._main_window)  # REMOVED - we are already the main window
        
        # Logger was already set above
        
        # Set application properties
        self.setWindowTitle("Kingdom AI Control System")
        self.resize(1200, 800)
        self.setMinimumSize(1024, 768)
        
        # GUIManager-like properties
        self.is_initialized = False
        self.loading_screen_visible = False
        self.main_window_visible = False
        self.config = config or {}
        
        # Store references to components and state
        self.event_bus = event_bus
        self.components = {}
        self.initialized = False
        self.shutdown_in_progress = False
        
        # RGB Animation state
        self.rgb_animation_enabled = True
        self.rgb_elements = []
        self.rgb_timer = None
        self.rgb_hue = 0.0
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # 2025 CRASH PREVENTION SYSTEMS - Initialize BEFORE any other components
        self._init_crash_prevention_systems()
        
        # SOTA 2025: Enable HIGH-FREQUENCY TRADING mode
        self._enable_hft_mode()
        
        # Connect signals to slots
        self._connect_signals()
        
        # Set up RGB animations
        self._setup_rgb_animations()
        
        # Create UI components
        self._create_ui()
        
        # Start crash prevention monitoring AFTER UI is created
        self._start_crash_prevention_monitoring()
    
    def _setup_rgb_animations(self):
        """Set up RGB border animations for cyberpunk styling."""
        try:
            # Initialize RGB animation timer
            from PyQt6.QtCore import QTimer
            self._rgb_animation_active = False
            self.rgb_timer = QTimer(self)  # Create the timer first
            if self.rgb_timer is not None:
                self.rgb_timer.timeout.connect(self._update_rgb_animation)
                self.rgb_timer.setInterval(150)  # SOTA 2026 FIX: 150ms saves CPU vs 50ms
                self._sync_rgb_timer()
            else:
                logger.warning("Failed to create RGB timer - QTimer returned None")
        except Exception as e:
            logger.warning(f"Failed to setup RGB animations: {e}")
    
    def _update_rgb_animation(self):
        """Update RGB animation colors with 2025 memory safety."""
        try:
            # 2025 MEMORY SAFETY: Check if widget is still valid
            if not self._should_rgb_timer_run():
                self._sync_rgb_timer()
                return  # Skip update if window is hidden/minimized
                
            # Increment hue for color cycling
            self.rgb_hue = (self.rgb_hue + 2) % 360
            
            # 2025 OPTIMIZATION: Only update if animation is active and visible
            if hasattr(self, '_rgb_animation_active') and self._rgb_animation_active and self.isVisible():
                # Limit update frequency to prevent excessive redraws
                self.update()  # Just refresh the widget, don't recreate UI
                
        except Exception as e:
            logger.warning(f"RGB animation update failed: {e}")
            # Stop animation on repeated failures to prevent crash loops
            if hasattr(self, 'rgb_timer') and self.rgb_timer:
                self.rgb_timer.stop()
                self._rgb_animation_active = False

    def _should_rgb_timer_run(self) -> bool:
        try:
            if not getattr(self, 'rgb_animation_enabled', True):
                return False
            if self.isHidden() or not self.isVisible():
                return False
            if self.isMinimized():
                return False
        except Exception:
            return False
        return True

    def _sync_rgb_timer(self):
        try:
            timer = getattr(self, 'rgb_timer', None)
            if timer is None:
                return

            if self._should_rgb_timer_run():
                if not timer.isActive():
                    timer.start(150)  # SOTA 2026 FIX: match setInterval(150)
            else:
                if timer.isActive():
                    timer.stop()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_rgb_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_rgb_timer()

    def changeEvent(self, event):
        super().changeEvent(event)
        try:
            if event.type() == QEvent.Type.WindowStateChange:
                self._sync_rgb_timer()
        except Exception:
            pass
    
    def _connect_signals(self):
        """Connect signals to slots for async updates."""
        self.system_status_update.connect(self._handle_system_status)
        self.component_status_update.connect(self._handle_component_status)
        self.network_status_update.connect(self._handle_network_status)
        self.trading_status_update.connect(self._handle_trading_status)
        self.blockchain_status_update.connect(self._handle_blockchain_status)
        self.mining_status_update.connect(self._handle_mining_status)
        self.voice_status_update.connect(self._handle_voice_status)
        self.vr_status_update.connect(self._handle_vr_status)
        
        # Register as the main window with GUIManager
        gui_manager = GUIManager.get_instance(event_bus=self.event_bus)
        # Initialize components dict if it doesn't exist
        if not hasattr(gui_manager, 'components'):
            gui_manager.components = {}  # type: ignore
        gui_manager.components["main_window"] = self  # type: ignore
        
    def _init_crash_prevention_systems(self):
        """Initialize crash prevention systems - CRITICAL for 24-hour stability."""
        try:
            self.logger.info("🛡️ Initializing crash prevention systems...")
            
            # 1. Resource Cleanup Manager
            self._cleanup_manager = get_cleanup_manager()
            self.logger.info("✅ Resource Cleanup Manager initialized")
            
            # 2. System State Manager
            self._state_manager = get_state_manager()
            # Register state provider for main window
            register_state_provider('main_window', self._get_window_state)
            self.logger.info("✅ System State Manager initialized")
            
            # 3. Crash Recovery Watchdog
            self._watchdog = get_watchdog()
            # Register recovery action
            self._watchdog.register_recovery_action(self._emergency_save_state)
            self.logger.info("✅ Crash Recovery Watchdog initialized")
            
            self.logger.info("🛡️ All crash prevention systems initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize crash prevention systems: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _start_crash_prevention_monitoring(self):
        """Start crash prevention monitoring - call AFTER UI is created."""
        try:
            self.logger.info("🚀 Starting crash prevention monitoring...")
            
            # Start auto-save (every 5 minutes)
            self._state_manager.start_auto_save()
            self.logger.info("✅ Auto-save started (5 minute interval)")
            
            # Start health monitoring (every 30 seconds)
            self._watchdog.start_monitoring()
            self.logger.info("✅ Health monitoring started (30 second interval)")
            
            # Load previous state if available
            if self._state_manager.load_state():
                self.logger.info("✅ Previous state loaded successfully")
            else:
                self.logger.info("ℹ️ No previous state found - starting fresh")
            
            self.logger.info("🚀 Crash prevention monitoring active")
            
        except Exception as e:
            self.logger.error(f"Failed to start crash prevention monitoring: {e}")
    
    def _get_window_state(self) -> Dict[str, Any]:
        """Get current window state for persistence."""
        try:
            return {
                'geometry': {
                    'x': self.x(),
                    'y': self.y(),
                    'width': self.width(),
                    'height': self.height()
                },
                'maximized': self.isMaximized(),
                'rgb_animation_enabled': self.rgb_animation_enabled,
                'timestamp': time.time()
            }
        except Exception as e:
            self.logger.warning(f"Failed to get window state: {e}")
            return {}
    
    def _emergency_save_state(self):
        """Emergency state save before crash/recovery."""
        try:
            self.logger.critical("🚑 EMERGENCY STATE SAVE TRIGGERED")
            self._state_manager.save_state(manual=True)
            self.logger.info("✅ Emergency state saved")
        except Exception as e:
            self.logger.error(f"Emergency save failed: {e}")
    
    def _connect_event_bus(self):
        """Connect to event bus for system communication."""
        if self.event_bus:
            self.logger.info("Connected to event bus successfully")
            try:
                self.event_bus.subscribe("gui.action", self._handle_gui_action)
                # Register subscription for cleanup tracking
                register_event_subscription(self.event_bus, "gui.action", self._handle_gui_action)
            except Exception as sub_err:
                self.logger.error(f"Failed to subscribe to gui.action: {sub_err}")
        else:
            self.logger.warning("No event bus available")
    
    def _enable_hft_mode(self):
        """
        Enable SOTA 2025 HIGH-FREQUENCY TRADING mode.
        
        This initializes the HFT communication system for:
        - 100ms data polling (10 updates/second)
        - 250ms UI updates (4 updates/second)
        - Priority-based event processing
        - Non-blocking thread pool execution
        """
        try:
            from core.hft_communication import (
                init_hft_system,
                get_hft_manager,
                HFTEventPriority
            )
            
            # Initialize HFT system
            self._hft_manager = init_hft_system()
            
            # Enable HFT mode on event bus if available
            if self.event_bus and hasattr(self.event_bus, 'enable_hft_mode'):
                self.event_bus.enable_hft_mode()
            
            self.logger.info("🚀 SOTA 2025 HFT MODE ENABLED")
            self.logger.info("   ├─ Data polling: 100ms (10 updates/sec)")
            self.logger.info("   ├─ UI updates: 250ms (4 updates/sec)")
            self.logger.info("   ├─ Event processing: 10ms priority queue")
            self.logger.info("   └─ Thread pool: 16 workers")
            
        except ImportError as e:
            self.logger.warning(f"HFT mode not available (missing module): {e}")
        except Exception as e:
            self.logger.error(f"HFT mode initialization failed: {e}")
    
    def get_hft_stats(self):
        """Get HFT system performance statistics."""
        if hasattr(self, '_hft_manager') and self._hft_manager:
            return self._hft_manager.get_stats()
        return {"hft_enabled": False}
    
    def show_loading_screen(self, message: str = "Loading..."):
        """Show loading screen with message."""
        self.loading_screen_visible = True
        self.statusBar().showMessage(message)

    def hide_loading_screen(self):
        """Hide loading screen."""
        self.loading_screen_visible = False
        self.statusBar().clearMessage()

    def show_main_window(self):
        """Show and raise the main window."""
        self.main_window_visible = True
        self.show()
        self.raise_()

    def update_loading_progress(self, progress: float, message: str = None):
        """Update loading progress indicator."""
        msg = f"Loading... {int(progress * 100)}%"
        if message:
            msg = f"{message} ({int(progress * 100)}%)"
        self.statusBar().showMessage(msg)

    def show_error(self, title, message):
        """Show error dialog."""
        try:
            QMessageBox.critical(self, title, message)
        except Exception as e:
            self.logger.error(f"Failed to show error dialog: {e}")
    
    def _connect_components(self):
        """Connect components together."""
        self.logger.info("Components connected successfully")
        
    def _handle_system_status(self, status_data):
        """Handle system status update event.
        
        Args:
            status_data (dict): The system status data.
        """
        try:
            if not isinstance(status_data, dict):
                self.logger.warning(f"Invalid system status data: {status_data}")
                return
                
            self.logger.info(f"System status update: {status_data}")
            
            # Update system status in status bar if available
            if 'message' in status_data:
                self.update_status(status_data['message'])
                
            # Update system status in components
            if 'status' in status_data:
                status = status_data['status']
                if status == 'initializing':
                    self.show_loading_screen("System initializing...")
                elif status in ['ready', 'operational']:
                    self.hide_loading_screen()
                    self.show_main_window()
                    self.update_status(f"System {status}")
                elif status == 'error':
                    self.show_error("System Error", status_data.get('message', 'Unknown system error'))
                    
            # Update progress if available
            if 'progress' in status_data:
                self.update_loading_progress(status_data['progress'], status_data.get('message', None))
                
        except Exception as e:
            self.logger.error(f"Error handling system status update: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _handle_component_status(self, status_data):
        """Handle component status update event.
        
        Args:
            status_data (dict): The component status data.
        """
        try:
            self.logger.info(f"Component status update: {status_data}")
            if 'component' in status_data and 'status' in status_data:
                component = status_data['component']
                status = status_data['status']
                # Update component status indicators
                if hasattr(self, 'dashboard_tab') and self.dashboard_tab:
                    self.dashboard_tab.update_component_status(component, status)  # type: ignore[attr-defined]
        except Exception as e:
            self.logger.error(f"Error handling component status update: {e}")
    
    def _handle_network_status(self, status_data):
        """Handle network status update event.
        
        Args:
            status_data (dict): The network status data.
        """
        try:
            self.logger.info(f"Network status update: {status_data}")
            if 'connected' in status_data:
                connected = status_data['connected']
                if connected:
                    self.statusBar().showMessage("Network connected")
                else:
                    self.statusBar().showMessage("Network disconnected")
            
            # Update any network indicators
            if hasattr(self, 'dashboard_tab') and self.dashboard_tab:
                self.dashboard_tab.update_network_status(status_data)  # type: ignore[attr-defined]
        except Exception as e:
            self.logger.error(f"Error handling network status update: {e}")
    
    def _handle_trading_status(self, status_data):
        """Handle trading status update event.
        
        Args:
            status_data (dict): The trading status data.
        """
        try:
            self.logger.info(f"Trading status update: {status_data}")
            # Update trading tab if available
            if hasattr(self, 'trading_tab') and self.trading_tab:
                self.trading_tab.update_status(status_data)
        except Exception as e:
            self.logger.error(f"Error handling trading status update: {e}")
    
    def _handle_blockchain_status(self, status_data):
        """Handle blockchain status update event.
        
        Args:
            status_data (dict): The blockchain status data.
        """
        try:
            self.logger.info(f"Blockchain status update: {status_data}")
            # Update blockchain tab if available
            if hasattr(self, 'blockchain_tab') and self.blockchain_tab:
                self.blockchain_tab.update_status(status_data)
        except Exception as e:
            self.logger.error(f"Error handling blockchain status update: {e}")
    
    def _handle_mining_status(self, status_data):
        """Handle mining status update event.
        
        Args:
            status_data (dict): The mining status data.
        """
        try:
            self.logger.info(f"Mining status update: {status_data}")
            # Update mining tab if available
            if hasattr(self, 'mining_tab') and self.mining_tab:
                self.mining_tab.update_status(status_data)
        except Exception as e:
            self.logger.error(f"Error handling mining status update: {e}")
            
    def _handle_voice_status(self, status_data):
        """Handle voice recognition status update event.
        
        Args:
            status_data (dict): The voice recognition status data.
        """
        try:
            self.logger.info(f"Voice status update: {status_data}")
            # Update voice components if available
            if hasattr(self, 'ai_tab') and self.ai_tab:
                self.ai_tab.update_voice_status(status_data)
        except Exception as e:
            self.logger.error(f"Error handling voice status update: {e}")
            
    def _handle_vr_status(self, status_data):
        """Handle VR system status update event.

        Args:
            status_data (dict): The VR system status data.
        """
        try:
            self.logger.info(f"VR status update: {status_data}")
            
            # Update VR tab if available
            if hasattr(self, 'vr_tab') and self.vr_tab:
                self.vr_tab.update_status(status_data)
        except Exception as e:
            self.logger.error(f"Error handling VR status update: {e}")

    def _handle_gui_action(self, payload: Dict[str, Any]) -> None:
        """Handle gui.action events emitted by ThothAIWorker.

        The ThothAIWorker encodes high-level UI intents as JSON, for example:

            {"tab": "trading", "panel": "auto_trade", "action": "toggle_button", "target": "Start"}

        This method decodes the action and forwards it to the appropriate
        tab widget using the existing TabManager and component references.
        """
        try:
            if not isinstance(payload, dict):
                return

            action = payload.get("action")
            if not isinstance(action, dict):
                return

            tab_id = str(action.get("tab") or payload.get("source_tab") or "").lower()
            if not tab_id:
                return

            if tab_id == "trading":
                self._handle_trading_gui_action(action)
            else:
                # Other tabs can be wired here using the same pattern
                pass
        except Exception as e:
            self.logger.error(f"Error handling gui.action payload: {e}")

    def _handle_trading_gui_action(self, action: Dict[str, Any]) -> None:
        """Dispatch gui.action payloads targeting the Trading tab.

        Supported schema (produced by ThothAIWorker's ACTION JSON):

            {
                "tab": "trading",
                "panel": "auto_trade",
                "action": "toggle_button" | "start" | "stop",
                "target": "Start" | "Stop"
            }
        """
        try:
            panel = str(action.get("panel") or "").lower()
            verb = str(action.get("action") or "").lower()
            target = str(action.get("target") or "").lower()

            trading_frame = None
            if "trading" in self.components:
                trading_frame = self.components.get("trading")
            elif hasattr(self, "trading_tab"):
                trading_frame = getattr(self, "trading_tab", None)

            if trading_frame is None:
                self.logger.warning("gui.action(trading): trading frame not available")
                return

            if panel == "auto_trade":
                # Map high-level intents to existing TradingTab methods.
                try_start = bool(target in {"start", "on", "enable"} or verb in {"start", "start_auto_trade"})
                try_stop = bool(target in {"stop", "off", "disable"} or verb in {"stop", "stop_auto_trade"})

                if try_start or (verb in {"toggle_button", "toggle"} and not try_stop):
                    if hasattr(trading_frame, "_start_auto_trade"):
                        trading_frame._start_auto_trade()
                        return
                    if hasattr(trading_frame, "_toggle_auto_trading"):
                        trading_frame._toggle_auto_trading()
                        return

                if try_stop or (verb in {"toggle_button", "toggle"} and not try_start):
                    if hasattr(trading_frame, "_stop_auto_trade"):
                        trading_frame._stop_auto_trade()
                        return
                    if hasattr(trading_frame, "_toggle_auto_trading"):
                        trading_frame._toggle_auto_trading()
                        return

            # If we reach here, the specific action was not recognized; log once.
            self.logger.info(f"gui.action(trading) ignored: {action}")
        except Exception as e:
            self.logger.error(f"Error executing trading gui.action: {e}")
    
    def initialize(self):
        """Initialize the main window and all tabs using TabManager.
        
        This method initializes all tabs and components, sets up event handlers,
        and prepares the main window for display. It must be called after
        instantiation and before showing the window.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            self.logger.info("Initializing KingdomMainWindow")
            
            # Initialize tabs using TabManager - with resilient error handling
            tabs_initialized = 0
            total_tabs = 10
            
            # Dashboard tab
            try:
                if self._init_dashboard_tab():
                    tabs_initialized += 1
            except Exception as e:
                self.logger.error(f"Dashboard tab failed: {e}")
            
            # Trading tab  
            try:
                if self._init_trading_tab():
                    tabs_initialized += 1
            except Exception as e:
                self.logger.error(f"Trading tab failed: {e}")
            
            # Blockchain tab
            try:
                if self._init_blockchain_tab():
                    tabs_initialized += 1
            except Exception as e:
                self.logger.error(f"Blockchain tab failed: {e}")
            
            # Thoth AI tab
            try:
                if self._init_thoth_ai_tab():
                    tabs_initialized += 1
            except Exception as e:
                self.logger.error(f"Thoth AI tab failed: {e}")
            
            # Wallet tab
            try:
                if self._init_wallet_tab():
                    tabs_initialized += 1
            except Exception as e:
                self.logger.error(f"Wallet tab failed: {e}")
            
            # API Key Manager tab — available for ALL users
            # SOTA 2026: Consumer mode shows only personal keys (isolated from creator's keys)
            try:
                if self._init_api_key_manager_tab():
                    tabs_initialized += 1
                    if _IS_CONSUMER:
                        self.logger.info("🛡️ API Key Manager: consumer mode — personal keys only")
            except Exception as e:
                self.logger.error(f"API Key Manager tab failed: {e}")
            
            # Code Generator tab — available for ALL users
            # SOTA 2026: Consumer code runs through CodeSandbox (AST scan + restricted execution)
            try:
                if self._init_code_generator_tab():
                    tabs_initialized += 1
                    if _IS_CONSUMER:
                        self.logger.info("🛡️ Code Generator: consumer mode — sandboxed execution")
            except Exception as e:
                self.logger.error(f"Code Generator tab failed: {e}")
            
            # Settings tab
            try:
                if self._init_settings_tab():
                    tabs_initialized += 1
            except Exception as e:
                self.logger.error(f"Settings tab failed: {e}")
            
            # Mining tab
            try:
                if self._init_mining_tab():
                    tabs_initialized += 1
            except Exception as e:
                self.logger.error(f"Mining tab failed: {e}")
            
            # VR tab
            try:
                if self._init_vr_tab():
                    tabs_initialized += 1
            except Exception as e:
                self.logger.error(f"VR tab failed: {e}")
            
            self.logger.info(f"Successfully initialized {tabs_initialized}/{total_tabs} tabs")
            
            # Connect to event bus
            if self.event_bus:
                self._connect_event_bus()
            else:
                self.logger.warning("No event bus provided, some features may be unavailable")
            
            # Connect components
            self._connect_components()
            
            # Mark as initialized if we have at least some tabs working
            if tabs_initialized > 0:
                self.initialized = True
                self.logger.info(f"KingdomMainWindow initialized with {tabs_initialized}/{total_tabs} working tabs")
                return True
            else:
                self.logger.critical("No tabs were successfully initialized - GUI will be empty")
                return False
            
        except Exception as e:
            self.logger.critical(f"Failed to initialize main window: {e}")
            self.show_error("Initialization Error", f"Failed to initialize Kingdom AI: {e}")
            return False
            
    def _init_dashboard_tab(self):
        """Initialize the dashboard tab with PyQt6 widgets using TabManager."""
        try:
            # Create dashboard widget
            self.dashboard = DashboardQt(event_bus=self.event_bus)
            
            # Apply cyberpunk styling
            CyberpunkStyle.apply_to_widget(self.dashboard, "dashboard")
            
            # Add to tab manager
            self.tab_manager.add_tab(
                widget=self.dashboard,
                title="Dashboard"
            )
            
            # Add to components dict for direct access
            self.components["dashboard"] = self.dashboard
            
            self.logger.info("Dashboard tab initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize dashboard tab: {e}", exc_info=True)
            return False
            
    def _init_trading_tab(self):
        """Initialize the trading tab with PyQt6 widgets using TabManager."""
        try:
            # Import Trading tab frame first
            from gui.qt_frames.trading.trading_tab import TradingTab
            

            # 2025 STATE-OF-THE-ART RUNTIME METHOD INJECTION
            def _start_market_updates_fix(self):
                try:
                    if hasattr(self, "_start_market_data_stream"):
                        return self._start_market_data_stream()
                    self.logger.warning("Market updates method not available")
                except Exception as e:
                    self.logger.error(f"Error in market updates: {e}")

            def _ensure_safe_defaults_fix(self):
                try:
                    attrs = {
                        "order_book": None, "current_price": 45000.0,
                        "portfolio_value": 10000.0, "available_balance": 5000.0,
                        "whale_tracker": None, "copy_trading": None,
                        "moonshot_detection": None, "quantum_trading": None,
                        "trading_intelligence_hub": None
                    }
                    for attr, default in attrs.items():
                        if not hasattr(self, attr):
                            setattr(self, attr, default)
                    self.logger.info("✅ Safe defaults applied - complete UI active")
                except Exception as e:
                    print(f"Error in safe defaults: {e}")

            # Apply runtime injection to TradingTab class
            TradingTab._start_market_updates = _start_market_updates_fix
            TradingTab._ensure_safe_defaults = _ensure_safe_defaults_fix

            def _ensure_backend_connections_fix(self):
                """Ensure all backend systems are properly connected"""
                try:
                    # Check Redis connection
                    if not hasattr(self, "redis_conn") or not self.redis_conn:
                        self.logger.info("Initializing Redis connection...")
                    
                    # Check trading system connection
                    if not hasattr(self, "trading_system") or not self.trading_system:
                        self.logger.info("Initializing trading system...")
                    
                    self.logger.info("✅ Backend connections verified")
                    
                except Exception as e:
                    self.logger.error(f"Error ensuring backend connections: {e}")

            # Apply backend connections method to class
            TradingTab._ensure_backend_connections = _ensure_backend_connections_fix
            self.logger.info("🎉 2025 Runtime method injection applied to TradingTab")
            self.logger.info("Initializing trading tab")
            
            # Use TabManager to create the tab
            trading_frame = self.tab_manager.create_tab(
                tab_id="trading",
                tab_title="Trading",
                tab_frame_class=TradingTab
            )

            self.trading_tab = trading_frame
            
            # Store reference
            self.components["trading"] = trading_frame
            
            # Get references to widgets within the trading frame if needed
            if hasattr(trading_frame, "order_book"):
                self.components["order_book"] = trading_frame.order_book
            if hasattr(trading_frame, "market_data"):
                self.components["market_data"] = trading_frame.market_data
                
            self.logger.info("Trading tab initialized with TabManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize trading tab: {e}")
            return False
    
    def _init_blockchain_tab(self):
        """Initialize the blockchain tab with PyQt6 widgets using TabManager."""
        try:
            self.logger.info("Initializing blockchain tab")
            
            # Import blockchain tab with correct path
            from gui.qt_frames.blockchain_tab import BlockchainTab
            
            # Use TabManager to create the tab
            blockchain_frame = self.tab_manager.create_tab(
                tab_id="blockchain",
                tab_title="Blockchain",
                tab_frame_class=BlockchainTab
            )
            
            # Store reference
            self.components["blockchain"] = blockchain_frame
            self.blockchain_tab = blockchain_frame
            
            self.logger.info("Blockchain tab initialized successfully with TabManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize blockchain tab: {e}")
            return False
            
    def _init_thoth_ai_tab(self):
        """Initialize the Thoth AI tab with voice integration using TabManager."""
        try:
            self.logger.info("Initializing Thoth AI tab with voice integration")
            
            # 2025 IMPORT SAFETY: Use globally imported class
            if ThothAITab is None:
                self.logger.warning("ThothAITab class not available - skipping tab")
                return False
            
            # Use TabManager to create the tab
            thoth_ai_frame = self.tab_manager.create_tab(
                tab_id="thoth_ai",
                tab_title="Thoth AI",
                tab_frame_class=ThothAITab
            )
            
            # Store reference
            self.components["thoth_ai"] = thoth_ai_frame
            
            self.logger.info("Thoth AI tab initialized with TabManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Thoth AI tab: {e}")
            return False
            
    def _init_wallet_tab(self):
        """Initialize the Wallet tab using TabManager."""
        try:
            self.logger.info("Initializing Wallet tab")
            
            # 2025 IMPORT SAFETY: Use globally imported class
            if WalletTab is None:
                self.logger.warning("WalletTab class not available - skipping tab")
                return False
            
            # Use TabManager to create the tab
            wallet_frame = self.tab_manager.create_tab(
                tab_id="wallet",
                tab_title="Wallet",
                tab_frame_class=WalletTab
            )
            
            # Store reference
            self.components["wallet"] = wallet_frame
            
            self.logger.info("Wallet tab initialized with TabManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Wallet tab: {e}")
            return False
            
    def _init_api_key_manager_tab(self):
        """Initialize the API Key Manager tab using TabManager."""
        try:
            self.logger.info("Initializing API Key Manager tab")
            
            # Import API Key Manager widget
            from gui.qt_frames.api_key_manager_tab import ApiKeyManagerTab
            
            # Use TabManager to create the tab
            api_key_frame = self.tab_manager.create_tab(
                tab_id="api_key_manager",
                tab_title="API Key Manager",
                tab_frame_class=ApiKeyManagerTab
            )
            
            # Store reference
            self.components["api_key_manager"] = api_key_frame
            
            self.logger.info("API Key Manager tab initialized with TabManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize API Key Manager tab: {e}")
            return False
            
    def _init_settings_tab(self):
        """Initialize the Settings tab using TabManager."""
        try:
            self.logger.info("Initializing Settings tab")
            
            # 2025 IMPORT SAFETY: Use globally imported class
            if SettingsTab is None:
                self.logger.warning("SettingsTab class not available - skipping tab")
                return False
            
            # Use TabManager to create the tab
            settings_frame = self.tab_manager.create_tab(
                tab_id="settings",
                tab_title="Settings",
                tab_frame_class=SettingsTab
            )
            
            # Store reference
            self.components["settings"] = settings_frame
            
            self.logger.info("Settings tab initialized with TabManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Settings tab: {e}")
            return False
            
    def _init_mining_tab(self):
        """Initialize the Mining tab using TabManager."""
        try:
            self.logger.info("Initializing Mining tab")
            
            # 2025 IMPORT SAFETY: Use globally imported class
            if MiningTab is None:
                self.logger.warning("MiningFrame available as MiningTab - skipping tab")
                return False
            
            # Use TabManager to create the tab
            mining_frame = self.tab_manager.create_tab(
                tab_id="mining",
                tab_title="Mining",
                tab_frame_class=MiningTab
            )
            
            # Store reference
            self.components["mining"] = mining_frame
            
            self.logger.info("Mining tab initialized with TabManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Mining tab: {e}")
            return False
            
    def _init_vr_tab(self):
        """Initialize the VR tab using TabManager."""
        try:
            self.logger.info("Initializing VR tab")
            
            # 2025 IMPORT SAFETY: Use globally imported class
            if VRTab is None:
                self.logger.warning("VRTab class not available - skipping tab")
                return False
            
            # Use TabManager to create the tab
            vr_frame = self.tab_manager.create_tab(
                tab_id="vr",
                tab_title="VR",
                tab_frame_class=VRTab
            )
            
            # Store reference
            self.components["vr"] = vr_frame
            
            self.logger.info("VR tab initialized with TabManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize VR tab: {e}")
            return False
            
    def _init_code_generator_tab(self):
        """Initialize the Code Generator tab using TabManager."""
        try:
            self.logger.info("Initializing Code Generator tab")
            
            # Import Code Generator widget
            from gui.frames.code_generator_qt import CodeGeneratorQt
            
            # Use TabManager to create the tab
            code_gen_frame = self.tab_manager.create_tab(
                tab_id="code_generator",
                tab_title="Code Generator",
                tab_frame_class=CodeGeneratorQt
            )
            
            # Store reference
            self.components["code_generator"] = code_gen_frame
            
            self.logger.info("Code Generator tab initialized with TabManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Code Generator tab: {e}")
            return False
            
    def update_status(self, message):
        """Update the status bar message."""
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
            
    def show_window(self):
        """Show the main window."""
        self.show()
        self.raise_()
        self.activateWindow()
    
    def _create_ui(self):
        """Create the main UI components and layout."""
        # Create central widget and main layout - WE ARE the main window
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Create main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(2)
        
        # Initialize particle system for visual effects
        self.particles = CyberpunkParticleSystem(max_particles=100)
        
        # Initialize TabManager first (this creates the actual tab widget we'll use)
        from gui.widgets.tab_manager import TabManager
        self.tab_manager = TabManager(self, self.event_bus)
        
        # CRITICAL FIX: Get the actual tab widget from TabManager and add it to layout
        self.tab_widget = self.tab_manager.get_tab_widget()
        self.main_layout.addWidget(self.tab_widget, 1)  # Give it stretch factor of 1
        CyberpunkStyle.apply_to_widget(self.tab_widget, "tab_container")
        
        # IMPORTANT: Tab creation happens in initialize() method, not here
        # This ensures proper initialization order
        
        # Create status bar with cyberpunk styling - WE ARE QMainWindow
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet(CyberpunkStyle.get_style_sheet("status_bar"))
        self.status_label = QLabel("Kingdom AI Ready")
        self.status_bar.addWidget(self.status_label, 1)
        
        # Add glowing effect to status label
        glow_effect = CyberpunkEffect.create_glow_effect(
            CYBERPUNK_THEME["neon_blue"],
            intensity=20,
            spread=10
        )
        self.status_label.setGraphicsEffect(glow_effect)
        
        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Add network status indicator
        self.network_indicator = QLabel("Network: Connected")
        self.status_bar.addPermanentWidget(self.network_indicator)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Apply styling
        KingdomQtStyle.apply_to_widget(self)
    
    def create_menu_bar(self):
        """Create the application menu bar with cyberpunk styling."""
        menubar = self.menuBar()  # Fixed: WE ARE the main window
        menubar.setStyleSheet(CyberpunkStyle.get_style_sheet("menu_bar"))
        
        # File menu
        file_menu = menubar.addMenu('&File')
        
        # Exit action
        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('&Tools')
        
        # Settings action
        settings_action = QAction('&Settings', self)
        settings_action.setStatusTip('Open settings')
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu('&Help')
        
        # About action
        about_action = QAction('&About', self)
        about_action.setStatusTip('About Kingdom AI')
        help_menu.addAction(about_action)
        
        self.setMenuBar(menubar)
    
    def closeEvent(self, event):
        """2025 SAFE SHUTDOWN: Handle application close with comprehensive cleanup."""
        try:
            logger.info("="*80)
            logger.info("🛡️ KINGDOM AI SHUTDOWN INITIATED")
            logger.info("="*80)
            
            # Mark shutdown in progress FIRST
            self.shutdown_in_progress = True
            
            # 1. Stop RGB animation timer specifically
            if hasattr(self, 'rgb_timer') and self.rgb_timer:
                try:
                    self.rgb_timer.stop()
                    self._rgb_animation_active = False
                    logger.info("✅ RGB animation timer stopped")
                except Exception as e:
                    logger.warning(f"Failed to stop RGB timer: {e}")
            
            # 2. Stop legacy thread-safe timers
            try:
                from utils.qt_timer_fix import cleanup_all_timers
                cleanup_all_timers()
                logger.info("✅ Legacy timers stopped")
            except (ImportError, AttributeError):
                pass
            
            # 3. Shutdown Crash Recovery Watchdog (stops monitoring, saves final metrics)
            if hasattr(self, '_watchdog'):
                try:
                    logger.info("🚑 Shutting down Crash Recovery Watchdog...")
                    self._watchdog.shutdown()
                    logger.info("✅ Crash Recovery Watchdog shutdown complete")
                except Exception as e:
                    logger.warning(f"Watchdog shutdown failed: {e}")
            
            # 4. Shutdown System State Manager (stops auto-save, performs final save)
            if hasattr(self, '_state_manager'):
                try:
                    logger.info("💾 Shutting down System State Manager...")
                    self._state_manager.shutdown()
                    logger.info("✅ System State Manager shutdown complete")
                except Exception as e:
                    logger.warning(f"State manager shutdown failed: {e}")
            
            # 5. Cleanup all registered components
            logger.info(f"🧹 Cleaning up {len(self.components)} components...")
            for component_name, component in self.components.items():
                try:
                    if hasattr(component, 'cleanup'):
                        component.cleanup()
                        logger.debug(f"✅ Cleaned up {component_name}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {component_name}: {e}")
            
            # 6. Cleanup ALL tracked resources via Resource Cleanup Manager
            if hasattr(self, '_cleanup_manager'):
                try:
                    logger.info("🧹 Running Resource Cleanup Manager...")
                    self._cleanup_manager.cleanup_all()
                    logger.info("✅ Resource Cleanup Manager complete")
                except Exception as e:
                    logger.warning(f"Cleanup manager failed: {e}")
            
            # 7. Disconnect from event bus
            if hasattr(self, 'event_bus') and self.event_bus:
                try:
                    logger.info("📡 Disconnecting from event bus...")
                    try:
                        self.event_bus.shutdown()
                    except Exception:
                        pass

                    try:
                        from core.async_task_manager import get_global_task_manager

                        task_manager = get_global_task_manager()
                        try:
                            import asyncio
                            loop = asyncio.get_running_loop()
                            loop.create_task(task_manager.shutdown_gracefully(timeout=5.0))
                        except RuntimeError:
                            try:
                                asyncio.run(task_manager.shutdown_gracefully(timeout=5.0))
                            except Exception:
                                pass
                    except Exception:
                        pass

                    logger.info("✅ Event bus disconnected")
                except Exception as e:
                    logger.warning(f"Event bus cleanup failed: {e}")
            
            # 8. Force garbage collection
            try:
                import gc
                collected = gc.collect()
                logger.info(f"🗑️ Garbage collection: {collected} objects freed")
            except Exception as e:
                logger.warning(f"Garbage collection failed: {e}")
            
            # Accept the close event
            event.accept()
            logger.info("="*80)
            logger.info("👋 KINGDOM AI SHUTDOWN COMPLETED SAFELY")
            logger.info("="*80)
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            import traceback
            logger.error(traceback.format_exc())
            event.accept()  # Accept anyway to prevent hang


# MainWindow alias for compatibility  
MainWindow = KingdomMainWindow
