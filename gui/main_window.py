from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kingdom AI Main Window Module (DEPRECATED).

DEPRECATION WARNING: This Tkinter-based implementation is deprecated and will be removed.
Please use gui.main_window_qt.KingdomMainWindow instead, which is a full PyQt6 implementation.

This module provides the main GUI window for the Kingdom AI system, integrating all components
and connecting to the event bus for asynchronous communication.
"""

# Define the GUI framework to use - can be 'pyqt6' or 'tkinter'
GUI_FRAMEWORK = 'pyqt6'

# Import statements
import asyncio
import logging
import os
import sys
import time
import traceback
import importlib.util
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, TypeVar, Protocol, Type, Union, cast

# Set up logging
logger = logging.getLogger(__name__)

# Using lowercase to avoid linting errors about constant redefinition
has_pyqt6 = True

# Define GUI framework - lower case to avoid redefinition issues
gui_framework = 'pyqt6'

# Define PyQt6 stub module - used only when real PyQt6 is unavailable
# All stub classes are defined under a _stubs module to avoid namespace pollution
class _PyQt6Stubs:
    """Container for PyQt6 stub classes to avoid namespace pollution.
    These stubs are only used when the real PyQt6 module is not available.
    """
    # Base signal class for connecting callbacks
    class _Signal:
        def connect(self, func): pass
        
    # Status bar for showing messages
    class _StatusBar:
        def showMessage(self, message): pass
        
    # DateTime helper for timestamp formatting
    class _DateTime:
        def toString(self, format_): return str(datetime.now())
    
    # Widget classes
    class QMainWindow:
        def __init__(self, *args, **kwargs): pass
        def setCentralWidget(self, widget): pass
        def statusBar(self): return _PyQt6Stubs._StatusBar()
        def resize(self, w, h): pass
        def setWindowTitle(self, title): pass
        def setMinimumSize(self, w, h): pass
        def centralWidget(self): return _PyQt6Stubs.QWidget()
    
    class QWidget:
        def __init__(self, *args, **kwargs): pass
        def setSizePolicy(self, *args): pass
        def setLayout(self, layout): pass
    
    class QVBoxLayout:
        def __init__(self, *args): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, spacing): pass
        def addWidget(self, widget): pass
        def addLayout(self, layout): pass
    
    class QHBoxLayout:
        def __init__(self): pass
        def addWidget(self, widget): pass
    
    class QTabWidget:
        def __init__(self): pass
        def addTab(self, tab, name): pass
        def currentWidget(self): return None
    
    class QLabel:
        def __init__(self, text=""): self.text = text
        def setText(self, text): self.text = text
    
    class QPushButton:
        def __init__(self, text=""): self.text = text
        def clicked(self): return _PyQt6Stubs._Signal()
    
    class QComboBox:
        def __init__(self): pass
        def addItems(self, items): pass
    
    class Qt:
        AlignTop = 0
        AlignCenter = 0
        class DateFormat:
            LocalDate = 0
            ISODate = "yyyy-MM-ddTHH:mm:ss"
    
    class QSizePolicy:
        class Policy:
            Expanding = "Expanding"
    
    class QSize:
        def __init__(self, w, h): self.width, self.height = w, h
    
    class QTimer:
        def __init__(self): pass
        def timeout(self): return _PyQt6Stubs._Signal()
        def start(self, ms): pass
        @staticmethod
        def singleShot(ms, func): pass
    
    class QDateTime:
        @staticmethod
        def currentDateTime():
            return _PyQt6Stubs._DateTime()
    
    # Empty container classes
    class QtWidgets: pass
    class QtCore: pass
    class QtGui: pass
    
    # Application class with both PyQt5 and PyQt6 exec methods
    class QApplication:
        def __init__(self, args): pass
        @staticmethod
        def instance(): return None
        def exec(self): pass  # PyQt6 style
        def exec_(self): pass  # PyQt5 style

# PyQt6 imports
# Handle PyQt6 imports with graceful fallback
try:
    # Actual PyQt6 imports
    from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton, QComboBox  # type: ignore
    from PyQt6.QtCore import Qt, QSize, QTimer, QDateTime  # type: ignore
    from PyQt6 import QtWidgets, QtCore, QtGui  # type: ignore
    logger.info("PyQt6 imported successfully")
except ImportError:
    # Use stub classes for static analysis and runtime functionality
    logger.warning("PyQt6 not found. Using stub classes for static analysis.")
    has_pyqt6 = False
    gui_framework = 'tkinter'
    
    # Import all stub classes into the current namespace
    QMainWindow = _PyQt6Stubs.QMainWindow
    QWidget = _PyQt6Stubs.QWidget
    QVBoxLayout = _PyQt6Stubs.QVBoxLayout
    QHBoxLayout = _PyQt6Stubs.QHBoxLayout
    QTabWidget = _PyQt6Stubs.QTabWidget
    QLabel = _PyQt6Stubs.QLabel
    QPushButton = _PyQt6Stubs.QPushButton
    QComboBox = _PyQt6Stubs.QComboBox
    QApplication = _PyQt6Stubs.QApplication
    Qt = _PyQt6Stubs.Qt
    QSize = _PyQt6Stubs.QSize
    QTimer = _PyQt6Stubs.QTimer
    QDateTime = _PyQt6Stubs.QDateTime
    QtWidgets = _PyQt6Stubs.QtWidgets
    QtCore = _PyQt6Stubs.QtCore
    QtGui = _PyQt6Stubs.QtGui

# SOTA 2026: Stub classes for static analysis when real imports unavailable
class BaseComponent:  # type: ignore[no-redef]
    """Kingdom AI BaseComponent stub class for static analyzers.
    
    Provides type hints and basic functionality when real BaseComponent unavailable.
    """
    def __init__(self, name: Optional[str] = None, event_bus: Any = None, **kwargs):
        self.name = name or self.__class__.__name__
        self.event_bus = event_bus
        self.logger = logging.getLogger(name if name else __name__)
        self._initialized = False
        self._config = kwargs.get('config', {})
    
    def initialize(self) -> bool:
        """Initialize the component."""
        self._initialized = True
        return True
    
    def cleanup(self) -> None:
        """Clean up component resources."""
        self._initialized = False
    
    def is_initialized(self) -> bool:
        """Check if component is initialized."""
        return self._initialized


class QApplicationStub:
    """Stub for QApplication that includes both PyQt6 exec() and PyQt5 exec_() methods.
    
    For static type checking when PyQt6 is not available.
    """
    def __init__(self, args):
        self._args = args
        self._running = False
        
    def exec(self) -> int:
        """Execute the application's main loop (PyQt6 style)."""
        self._running = True
        return 0
        
    def exec_(self) -> int:
        """Execute the application's main loop (PyQt5 style)."""
        return self.exec()
    
    def quit(self) -> None:
        """Quit the application."""
        self._running = False
    
    def processEvents(self) -> None:
        """Process pending events."""
        pass

# Setup logging first to ensure errors are captured
from utils.logger import setup_logger
logger = setup_logger(__name__)

# Custom imports - handle with try/except to avoid errors during imports
try:
    from core.base_component import BaseComponent as RealBaseComponent
    # Replace the stub with the real class
    BaseComponent = RealBaseComponent  # type: ignore[misc,assignment]
    logger.info("Successfully imported BaseComponent")
except ImportError as e:
    logger.warning(f"Could not import BaseComponent: {e}")
    # Continue using the stub BaseComponent defined above

# Use the correct EventBus from core.event_bus without fallbacks
from core.event_bus import EventBus
logger.info("Successfully imported EventBus from core.event_bus")

# Logger is already configured by the import at the top
# Defensive imports - some frames may not be available
from gui.frames import BaseFrame, DashboardFrame, TradingFrame, WalletFrame, VRFrame, ThothFrame, CodeGeneratorFrame
try:
    from gui.frames import MiningFrame
except (ImportError, Exception):
    MiningFrame = None
try:
    from gui.frames import LinkFrame
except (ImportError, Exception):
    LinkFrame = None
try:
    from gui.frames import APIKeysFrame
except (ImportError, Exception):
    APIKeysFrame = None
try:
    from gui.frames import DiagnosticsFrame
except (ImportError, Exception):
    DiagnosticsFrame = None

# Import KingdomGUI from the canonical module
from gui.kingdom_gui import KingdomGUI

# Define the GUI framework to use
# Using lowercase to avoid linting errors about constant redefinition
gui_framework = 'PyQt6' if has_pyqt6 else 'Tkinter'

# KingdomGUI is now imported from gui.kingdom_gui

# Suppress static analysis errors when inheriting from classes that might not exist
# This is necessary because QMainWindow might be a stub class if PyQt6 is not available
class MainWindow(QMainWindow, BaseComponent):  # type: ignore[misc,no-any-unimported]
    """The main GUI window for the Kingdom AI system, responsible for initializing
    all GUI components and connecting to the event bus.
    """
    def __init__(self, root=None, event_bus: Optional[Any] = None):
        QMainWindow.__init__(self)
        BaseComponent.__init__(self, name="main_window", event_bus=event_bus)
        """Initialize the main window with PyQt6 and event bus connection.
        
        Args:
            root: The root window (parent) for this window (used in verification)
            event_bus (Optional[Any]): The event bus for communication.
        """
        # Window properties
        self.setWindowTitle("Kingdom AI System")
        self.resize(1200, 800)
        
        # CRITICAL: Validate that event_bus is provided - do not allow None
        if event_bus is None:
            logger.critical("No event bus provided during MainWindow initialization. Kingdom AI requires a single shared event bus.")
            raise ValueError("MainWindow requires a valid event_bus parameter. Cannot continue without a shared event bus.")
            
        self.event_bus = event_bus
        self.root = root  # Store root reference for potential use in tests
        # TabManager will be initialized in initialize_components
        self.tab_manager = None
        # Initialize kingdom_gui with proper KingdomGUI class instance and shared event_bus
        # Pass the event_bus explicitly to ensure a single shared instance
        self.kingdom_gui = KingdomGUI(event_bus=self.event_bus)
        self.setup_window()
        self._setup_event_handlers()
        self._setup_rgb_animations()
        self.initialize_components()
        logging.info("MainWindow initialized")

    def setup_window(self) -> None:
        """Configure the main window properties."""
        self.setWindowTitle("Kingdom AI System")
        self.setMinimumSize(800, 600)
        
        # Create central widget with proper size policy
        central_widget = QWidget()
        
        # Set size policy to expanding (using imported classes or stubs)
        if has_pyqt6:
            from PyQt6.QtWidgets import QSizePolicy  # type: ignore
            central_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            # Use stub version or alternative
            central_widget.setSizePolicy('Expanding', 'Expanding')
        self.setCentralWidget(central_widget)
        
        # Create layout with no margins to maximize available space
        self.central_layout = QVBoxLayout(self.centralWidget())
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        
        logging.info("Main window setup complete with optimized layout")

    def _setup_event_handlers(self):
        """Set up event handlers for the main window."""
        logging.info("Setting up event handlers for MainWindow")
        # We're not doing subscriptions here anymore
        # They will be handled in initialize_components
        # This avoids the 'coroutine not awaited' warning
        logging.info("Event handlers will be set up when initialize_components is called")
        
    def _connect_tab_events(self):
        """Connect tabs to the event bus to receive real-time data updates.
        
        This method sets up event subscriptions for each tab to receive data
        from the event bus when components publish updates.
        """
        import logging
        import traceback
        
        if not self.event_bus:
            logging.warning("No event bus available, cannot connect tab events")
            return False
            
        if not self.tab_manager:
            logging.warning("No tab manager available, cannot connect tab events")
            return False
            
        # First ensure all tabs have update methods
        self._create_tab_update_methods()
            
        # Create handlers for each possible component type
        component_types = [
            'system', 'dashboard', 'trading', 'mining', 
            'wallet', 'thoth_ai', 'code_generator', 'voice', 
            'api_key', 'vr', 'settings'
        ]
        
        # Dictionary mapping component types to additional events they should subscribe to
        component_events = {
            'dashboard': ['system.status', 'system.metrics', 'trading.summary', 'mining.status'],
            'trading': ['market.data', 'trading.order', 'trading.position', 'wallet.balance'],
            'mining': ['mining.hashrate', 'mining.rewards', 'mining.node', 'system.resources'],
            'wallet': ['wallet.transaction', 'wallet.balance', 'wallet.history'],
            'thoth_ai': ['ai.prediction', 'ai.insight', 'ai.analysis'],
            'code_generator': ['code.generate', 'code.analyze', 'code.optimize'],
            'voice': ['voice.command', 'voice.response', 'system.notification'],
            'api_key': ['api.status', 'api.limit', 'api.error'],
            'vr': ['vr.scene', 'vr.interaction', 'market.visualization'],
            'settings': ['system.config', 'system.theme', 'system.notification']
        }
        
        # Add more detailed dashboard events
        component_events['dashboard'].extend([
            'dashboard.market_summary_update',
            'dashboard.portfolio_summary_update',
            'dashboard.system_metrics_update',
            'dashboard.notifications_update',
            'dashboard.data_update'
        ])
        
        # Track how many event subscriptions were successful
        success_count = 0
        total_count = 0
        
        # For each component type, subscribe to its main update event
        for comp_type in component_types:
            # Primary update event (component.update)
            primary_event = f"{comp_type}.update"
            
            # Get the tab_id that corresponds to this component type
            tab_id = self._get_tab_id_for_component(comp_type)
            if not tab_id:
                logging.debug(f"No tab mapped to component type: {comp_type}")
                continue
                
            # Create a handler for the primary event
            def create_handler(t_id, event_name):
                def handler(data):
                    try:
                        # Add the event name to the data for context
                        if isinstance(data, dict):
                            data['_event_name'] = event_name
                        else:
                            # If data is not a dict, wrap it
                            data = {'_original_data': data, '_event_name': event_name}
                            
                        # Update the tab with this data
                        self.update_tab_data({'tab_id': t_id, 'data': data})
                        logging.debug(f"Updated {t_id} tab with data from {event_name}")
                    except Exception as e:
                        logging.error(f"Error handling {event_name} for {t_id}: {e}")
                        logging.error(traceback.format_exc())
                return handler
                
            # Subscribe to the primary update event
            try:
                primary_handler = create_handler(tab_id, primary_event)
                if hasattr(self.event_bus, 'subscribe') and callable(self.event_bus.subscribe):
                    if asyncio.iscoroutinefunction(self.event_bus.subscribe):
                        # Call the coroutine function and ensure result is awaitable before creating task
                        result = self.event_bus.subscribe(primary_event, primary_handler)
                        if asyncio.iscoroutine(result):
                            asyncio.create_task(result)
                    else:
                        self.event_bus.subscribe(primary_event, primary_handler)
                    logging.info(f"Connected {tab_id} tab to event: {primary_event}")
                    success_count += 1
                else:
                    logging.warning(f"Event bus missing subscribe method, could not connect {tab_id} to {primary_event}")
            except Exception as e:
                logging.error(f"Error connecting {tab_id} to {primary_event}: {e}")
                logging.error(traceback.format_exc())
            total_count += 1
            
            # Subscribe to additional events for this component type
            if comp_type in component_events:
                for event_name in component_events[comp_type]:
                    try:
                        event_handler = create_handler(tab_id, event_name)
                        if hasattr(self.event_bus, 'subscribe') and callable(self.event_bus.subscribe):
                            if asyncio.iscoroutinefunction(self.event_bus.subscribe):
                                asyncio.create_task(self.event_bus.subscribe(event_name, event_handler))
                            else:
                                self.event_bus.subscribe(event_name, event_handler)
                            logging.info(f"Connected {tab_id} tab to event: {event_name}")
                            success_count += 1
                        else:
                            logging.warning(f"Event bus missing subscribe method, could not connect {tab_id} to {event_name}")
                    except Exception as e:
                        logging.error(f"Error connecting {tab_id} to {event_name}: {e}")
                        logging.error(traceback.format_exc())
                    total_count += 1
        
        # Also set up tab-specific data handlers if defined on the tab frames
        if hasattr(self.tab_manager, 'tabs'):
            for tab_id, tab_frame in self.tab_manager.tabs.items():
                if hasattr(tab_frame, 'register_event_handlers') and callable(tab_frame.register_event_handlers):
                    try:
                        tab_frame.register_event_handlers(self.event_bus)
                        logging.info(f"Registered custom event handlers for {tab_id} tab")
                        success_count += 1
                    except Exception as e:
                        logging.error(f"Error registering event handlers for {tab_id} tab: {e}")
                        logging.error(traceback.format_exc())
                    total_count += 1
        
        # Check if we were successful
        if total_count > 0:
            success_rate = (success_count / total_count) * 100
            logging.info(f"Tab event connections established: {success_count}/{total_count} ({success_rate:.1f}%)")
            return success_count > 0
        else:
            logging.warning("No tab events were connected")
            return False
        
        # Also set up tab-specific data handlers if defined on the tab frames
        for tab_id, tab_frame in self.tab_manager.tabs.items():
            if hasattr(tab_frame, 'register_event_handlers') and callable(tab_frame.register_event_handlers):
                try:
                    tab_frame.register_event_handlers(self.event_bus)
                    logging.info(f"Registered custom event handlers for {tab_id} tab")
                    success_count += 1
                except Exception as e:
                    logging.error(f"Error registering event handlers for {tab_id} tab: {e}")
        
        # Check if we were successful
        if total_count > 0:
            success_rate = (success_count / total_count) * 100
            logging.info(f"Tab event connections established: {success_count}/{total_count} ({success_rate:.1f}%)")
            return success_count > 0
        else:
            logging.warning("No tab events were connected")
            return False
        
    async def _setup_event_subscriptions(self):
        """Set up subscriptions to the event bus asynchronously.
        
        This method subscribes the MainWindow to events it needs to respond to.
        """
        if self.event_bus:
            try:
                # Subscribe to system status updates
                await self.event_bus.subscribe("system.status", self.handle_system_status)
                # Subscribe to tab data updates
                await self.event_bus.subscribe("tab.update", self.update_tab_data)
                # Subscribe to component status updates
                await self.event_bus.subscribe("component.status", self.update_component_status)
                logging.info("MainWindow subscribed to events: system.status, tab.update, component.status")
            except Exception as e:
                logging.error(f"Error in _setup_event_subscriptions: {e}")
        else:
            logging.warning("No event bus available for subscriptions")
            
    def _setup_sync_event_subscriptions(self):
        """Set up subscriptions to the event bus synchronously.
        
        This method is used when async operations are not available.
        It uses the synchronous subscribe_sync method directly without requiring await.
        """
        if self.event_bus:
            try:
                # Use the synchronous subscribe_sync method directly
                # Subscribe to system status updates
                self.event_bus.subscribe_sync("system.status", self.handle_system_status)
                # Subscribe to tab data updates
                self.event_bus.subscribe_sync("tab.update", self.update_tab_data)
                # Subscribe to component status updates
                self.event_bus.subscribe_sync("component.status", self.update_component_status)
                
                logging.info("MainWindow subscribed to events synchronously")
            except Exception as e:
                logging.error(f"Error in _setup_sync_event_subscriptions: {e}")
        else:
            logging.warning("No event bus available for sync subscriptions")

    def _setup_rgb_animations(self):
        """Set up RGB animations for visual effects."""
        try:
            logger.info("Setting up RGB animations")
            
            # Initialize rgb_timer as None first to avoid the 'access before definition' error
            self.rgb_timer = None
            self.rgb_phase = 0
            self.rgb_elements = []
            
            if gui_framework == "PyQt6" and has_pyqt6:
                # QTimer imported from PyQt6.QtCore
                # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
                self._timer_manager = get_qt_timer_manager()
                self.rgb_timer.timeout.connect(self._update_rgb_colors)
                self.rgb_timer.start(50)  # Update every 50ms
                logger.info("RGB animations initialized with QTimer")
            else:  # Tkinter
                self.rgb_timer = None
                self._schedule_rgb_update()
                logger.info("RGB animations initialized with schedule")
                
            # Register elements that will have RGB effects
            self._register_rgb_elements()
                
        except Exception as e:
            logger.error(f"Error setting up RGB animations: {e}")
            logger.error(traceback.format_exc())

    def _schedule_rgb_update(self):
        """Schedule RGB update for Qt."""
        self._update_rgb_colors()
        # Use QTimer instead of Tk's after
        QTimer.singleShot(50, self._schedule_rgb_update)

    def _update_rgb_colors(self):
        # Update RGB colors logic here
        pass

    def _register_rgb_elements(self):
        # Register RGB elements logic here
        pass
        
    async def handle_system_status(self, status_data: Dict[str, Any]) -> None:
        """Handle system status updates from the event bus.
        
        Args:
            status_data: Dictionary containing system status information
        """
        try:
            if not status_data or not isinstance(status_data, dict):
                self.logger.warning("Invalid system status data received")
                return
                
            # Update the status bar if available
            if hasattr(self, 'statusBar') and self.statusBar():
                status_message = status_data.get('status', 'System ready')
                self.statusBar().showMessage(f"Status: {status_message}")
            
            # Forward the status update to the tab manager if it exists
            if not hasattr(self, 'tab_manager') or self.tab_manager is None:
                self.logger.debug("Tab manager not yet initialized, skipping system status update")
                return
                
            try:
                # Check if update_system_status is a coroutine function
                update_method = getattr(self.tab_manager, 'update_system_status', None)
                if update_method is None:
                    self.logger.warning("TabManager does not have update_system_status method")
                    return
                    
                # Call the update method (could be sync or async)
                result = update_method(status_data)
                if asyncio.iscoroutine(result):
                    await result
                
                # Log the status update
                self.logger.debug(f"System status processed: {status_data.get('status', 'unknown')}")
                
            except Exception as e:
                self.logger.error(f"Error in tab manager status update: {e}")
                self.logger.error(traceback.format_exc())
            
        except Exception as e:
            self.logger.error(f"Error handling system status update: {e}")
            self.logger.error(traceback.format_exc())

    def initialize_components(self):
        """Initialize GUI components like tab manager and other sub-components."""
        logging.info(f"Initializing GUI components with {gui_framework} as primary framework")
        
        # Schedule async subscriptions if we have an event bus
        if self.event_bus and hasattr(self.event_bus, 'subscribe'):
            try:
                if asyncio.iscoroutinefunction(self.event_bus.subscribe):
                    # Create a task to set up event handlers asynchronously
                    asyncio.create_task(self._setup_event_subscriptions())
                    logging.info("Created async task for event subscriptions")
                else:
                    # Direct synchronous subscription
                    self._setup_sync_event_subscriptions()
                    logging.info("Set up synchronous event subscriptions")
            except Exception as e:
                logging.error(f"Error scheduling event subscriptions: {e}")
        
        try:
            # Initialize the tab manager
            from gui.tab_manager import TabManager
            logging.info("Initializing TabManager with event_bus")
            # Initialize TabManager with the event bus
            self.tab_manager = TabManager(
                notebook=self.notebook if hasattr(self, 'notebook') else None,
                event_bus=self.event_bus,
                redis_connector=self.redis_connector if hasattr(self, 'redis_connector') else None
            )
            
            # Add the TabManager to the central layout directly if it's a QWidget
            if hasattr(self.central_layout, 'addWidget'):
                self.central_layout.addWidget(self.tab_manager)
                
            # Initialize all tabs using the real TabManager API
            if hasattr(self.tab_manager, 'initialize_all_tabs'):
                self.tab_manager.initialize_all_tabs()
                logging.info("Initialized all tabs synchronously")
            
            logging.info("TabManager initialized and added to central layout")
        except ImportError as e:
            logger.warning(f"TabManager not found, will skip tab initialization: {e}")
            self.tab_manager = None
        except Exception as e:
            logging.error(f"Error initializing TabManager: {e}")
            logger.error(traceback.format_exc())
            self.tab_manager = None
        
        # Only create a new KingdomGUI instance if one doesn't exist
        if not hasattr(self, 'kingdom_gui') or self.kingdom_gui is None:
            try:
                # First try to import from gui.kingdom_gui
                try:
                    from gui.kingdom_gui import KingdomGUI as ExternalKingdomGUI
                    kingdom_gui_instance = ExternalKingdomGUI(event_bus=self.event_bus)
                    logger.info("Using external KingdomGUI implementation")
                except ImportError:
                    # If KingdomGUI is not found in gui.kingdom_gui, use our local implementation
                    kingdom_gui_instance = KingdomGUI(event_bus=self.event_bus)
                    logger.info("Using local KingdomGUI implementation")
                    
                # Assign the instance
                self.kingdom_gui = kingdom_gui_instance
                logger.info("KingdomGUI instance created with event bus")
                
                # Ensure the kingdom_gui has required methods
                if not hasattr(self.kingdom_gui, 'update_status'):
                    logger.warning("Kingdom GUI missing update_status method, adding default implementation")
                    # We already have a default method defined in the class
                    # No need to set it again as it's already there
                    logger.info("Using default update_status method already defined in KingdomGUI")
                    
            except Exception as e:
                logger.error(f"Error initializing KingdomGUI: {e}")
                logger.error(traceback.format_exc())
                self.kingdom_gui = None
            
        # Report initialization status
        if self.tab_manager and self.kingdom_gui:
            logger.info("All GUI components initialized successfully")
            
            # Create notebook if needed first
            if hasattr(self.tab_manager, 'create_notebook'):
                # Check if notebook already exists to avoid recreation
                notebook_exists = hasattr(self.tab_manager, 'notebook') and self.tab_manager.notebook is not None
                
                if not notebook_exists:
                    success = self.tab_manager.create_notebook()
                    if success:
                        logger.info("TabManager notebook created successfully")
                    else:
                        logger.error("TabManager failed to create notebook")
                else:
                    logger.info("TabManager notebook already exists")
            
            # Always initialize tabs regardless of notebook creation
            logger.info("Calling initialize_tabs to create and register all core tabs")
            self.initialize_tabs()
        else:
            logger.warning("Some GUI components failed to initialize but system will continue")
            missing = []
            if not self.tab_manager:
                missing.append("TabManager")
            if not self.kingdom_gui:
                missing.append("KingdomGUI")
            logger.warning(f"Missing components: {', '.join(missing)}")
            
    # handle_system_status method moved below to avoid duplication
    
    # update_all_frames method moved below to avoid duplication
    
    # Removed duplicate update_component_status method
    # NOTE: The comprehensive version with Redis Quantum Nexus enforcement is preserved below
    
    def update_tab_data(self, data: Dict[str, Any]):
        """Update tab data based on events from the event bus.

        Args:
            data (Dict[str, Any]): Data from the event bus to update tabs.
        """
        import logging
        import traceback
        
        logging.debug(f"Received tab data update: {data}")
        
        try:
            # Get tab ID from data
            tab_id = data.get('tab_id')
            if not tab_id:
                # Try to infer tab_id from the component type if available
                component_type = data.get('component_type')
                if component_type:
                    tab_id = self._get_tab_id_for_component(component_type)
                    
                if not tab_id:
                    logging.warning("Tab data update missing tab ID and could not be inferred")
                    return
                
            # Ensure we have actual data to update with
            tab_data = data.get('data', {})
            if not tab_data and 'data' not in data:
                # If no explicit 'data' field, use the entire data object minus some control fields
                control_fields = {'tab_id', 'component_type'}
                tab_data = {k: v for k, v in data.items() if k not in control_fields}
                
            # Check if the tab manager and tabs exist
            if not self.tab_manager:
                logging.warning("Tab manager not available for update")
                return
                
            # First try to update by direct frame reference if possible
            updated = False
            
            # Look for the tab in tab_manager.tabs
            if hasattr(self.tab_manager, 'tabs') and self.tab_manager.tabs:
                tab_frame = self.tab_manager.tabs.get(tab_id)
                
                if tab_frame:
                    # If tab frame has a custom update method that accepts data, call it
                    if hasattr(tab_frame, 'update_data') and callable(getattr(tab_frame, 'update_data', None)):
                        try:
                            tab_frame.update_data(tab_data)
                            logging.info(f"Updated {tab_id} tab with custom update_data method")
                            updated = True
                        except Exception as e:
                            logging.error(f"Error updating {tab_id} tab with custom method: {e}")
                            logging.error(traceback.format_exc())
                    # If tab frame has a standard Qt update method, call it without arguments
                    # to trigger a repaint if needed
                    elif hasattr(tab_frame, 'update') and callable(getattr(tab_frame, 'update', None)):
                        try:
                            tab_frame.update()  # Call without arguments for standard Qt update
                            logging.debug(f"Triggered standard Qt update for {tab_id} tab")
                        except Exception as e:
                            logging.error(f"Error triggering Qt update for {tab_id} tab: {e}")
                            logging.error(traceback.format_exc())
            
            # If not updated yet, try tab manager's update_tab_content method
            if not updated and hasattr(self.tab_manager, 'update_tab_content'):
                update_fn = getattr(self.tab_manager, 'update_tab_content')
                if callable(update_fn):
                    try:
                        update_fn(tab_id, tab_data)
                        logging.info(f"Updated {tab_id} tab content via tab manager")
                        updated = True
                    except Exception as e:
                        logging.error(f"Error updating {tab_id} via tab manager: {e}")
                        logging.error(traceback.format_exc())
            
            # If still not updated, try tab-specific method on main window as last resort
            if not updated:
                method_name = f"update_{tab_id}_tab"
                if hasattr(self, method_name) and callable(getattr(self, method_name, None)):
                    try:
                        getattr(self, method_name)(tab_data)
                        logging.info(f"Updated {tab_id} tab via specific MainWindow method")
                        updated = True
                    except Exception as e:
                        logging.error(f"Error updating {tab_id} via specific method: {e}")
                        logging.error(traceback.format_exc())
            
            if not updated:
                logging.warning(f"Failed to update {tab_id} tab - no viable update method found")
                
        except Exception as e:
            logging.error(f"Error updating tab data: {e}")
            logging.error(traceback.format_exc())

    def _initialize_tab_data(self):
        """Initialize all tabs with test data to ensure UI elements are populated."""
        try:
            if hasattr(self.tab_manager, 'populate_tab_with_data'):
                standard_tabs = ['dashboard', 'trading', 'mining', 'thoth_ai', 'code_generator', 
                            'voice', 'wallet', 'api_key', 'vr', 'settings']
                for tab_id in standard_tabs:
                    if self.tab_manager and hasattr(self.tab_manager, 'tabs') and tab_id in self.tab_manager.tabs:
                        self.tab_manager.populate_tab_with_data(tab_id)
                logging.info("All tabs populated with initial data")
        except Exception as e:
            logging.error(f"Error initializing tab data: {e}")
            logging.error(traceback.format_exc())
            
    def update_component_status(self, status: str, count: int = 0):
        """Update the component status in the GUI.
        
        Args:
            status (str): The current status (e.g., 'ready', 'initializing')
            count (int): The number of components that are ready
        """
        try:
            # Check Redis connection status if this is a status update from Redis
            if isinstance(status, dict) and 'redis_status' in status:
                redis_status = status.get('redis_status', {})
                redis_port = status.get('redis_port', 0)
                redis_pass = status.get('redis_password', '')
                
                if redis_port != 6380 and 'port' in str(status).lower():
                    logger.critical(f"CRITICAL ERROR: Redis Quantum Nexus using incorrect port {redis_port}. Must use port 6380.")
                    logger.critical("System will halt - Redis Quantum Nexus port requirement not satisfied")
                    # Force system halt due to incorrect Redis port
                    import sys
                    sys.exit(1)
                    
                if redis_pass != os.environ.get('REDIS_PASSWORD', "") and 'password' in str(status).lower():
                    logger.critical("CRITICAL ERROR: Redis Quantum Nexus using incorrect password. Must use password from environment variable 'REDIS_PASSWORD'.")
                    logger.critical("System will halt - Redis Quantum Nexus password requirement not satisfied")
                    # Force system halt due to incorrect password
                    import sys
                    sys.exit(1)
                    
                if 'failed' in str(redis_status).lower() or 'error' in str(redis_status).lower():
                    logger.critical("CRITICAL ERROR: Redis Quantum Nexus connection failed.")
                    logger.critical("System will halt - no fallback allowed for Redis connectivity issues")
                    # Force system halt due to Redis connection failure
                    import sys
                    sys.exit(1)
            
            # Extract status information
            if isinstance(status, dict):
                status_text = status.get('status', 'Ready')
                count_value = status.get('count', 0)
            else:
                # Handle case when status is a string
                status_text = str(status)
                count_value = count
            
            # Update status through kingdom_gui if available
            if self.kingdom_gui:
                # Use kingdom_gui's update_status method - safely get and call it
                update_status_fn = getattr(self.kingdom_gui, 'update_status', None)
                if callable(update_status_fn):
                    try:
                        update_status_fn(status_text, count_value)
                    except Exception as e:
                        logger.error(f"Error updating status: {e}")
                else:
                    logger.warning("kingdom_gui.update_status is not callable")
            else:
                # Direct update of status widgets if any
                logger.info(f"Direct status update: {status_text} ({count_value})")
                if hasattr(self, 'statusBar'):
                    self.statusBar().showMessage(f"Status: {status_text.upper()} ({count_value})")
        except Exception as e:
            logger.error(f"Error handling system status: {e}")
            logger.error(traceback.format_exc())
    
    def update_all_frames(self) -> None:
        """Update all frames in the GUI with current data.
        This method is called to refresh all UI components at once.
        """
        logging.info("Updating all frames with current data")
        # Ensure TabManager has the required methods
        if self.tab_manager:
            # Add refresh_all method if it doesn't exist
            if not hasattr(self.tab_manager, 'refresh_all'):
                def refresh_all_tabs():
                    logging.info("Refreshing all tabs with current data")
                    tabs = getattr(self.tab_manager, 'tabs', {})
                    for tab_name in tabs:
                        try:
                            # Ensure tab_manager is not None and has update_tab method
                            if self.tab_manager is not None and hasattr(self.tab_manager, 'update_tab') and callable(self.tab_manager.update_tab):
                                self.tab_manager.update_tab(tab_name)
                            else:
                                logging.warning(f"Cannot update tab {tab_name}: tab_manager is None or update_tab not callable")
                        except Exception as e:
                            logging.error(f"Error refreshing tab {tab_name}: {e}")
                
                # Use a synchronous wrapper function that returns bool
                def sync_refresh_all() -> bool:
                    """Synchronous wrapper function for the async refresh_all_tabs
                    This maintains compatibility with the expected bool return type.
                    """
                    try:
                        # Schedule the async task but return immediately with success
                        import asyncio
                        if asyncio.get_event_loop().is_running():
                            # Ensure we're calling the function correctly
                            if callable(refresh_all_tabs):
                                try:
                                    coroutine = refresh_all_tabs()
                                    if asyncio.iscoroutine(coroutine):
                                        asyncio.create_task(coroutine)
                                        return True
                                    else:
                                        logging.warning("refresh_all_tabs did not return a coroutine")
                                except Exception as e:
                                    logging.error(f"Error calling refresh_all_tabs: {e}")
                            return False
                        else:
                            logging.warning("Cannot schedule refresh: no running event loop")
                            return False
                    except Exception as e:
                        logging.error(f"Error in sync_refresh_all: {e}")
                        return False
                
                # Assign the synchronous function that returns bool as expected
                self.tab_manager.refresh_all = sync_refresh_all
            
            # Call the synchronous refresh method which handles async scheduling internally
            if hasattr(self.tab_manager, 'refresh_all') and callable(getattr(self.tab_manager, 'refresh_all', None)):
                try:
                    # Call the function normally since it's now synchronous
                    result = self.tab_manager.refresh_all()
                    if not result:
                        logging.warning("Tab refresh reported failure")
                except Exception as e:
                    logging.error(f"Error calling tab refresh: {e}")
        
        # Trigger component-specific updates via event bus
        if self.event_bus and hasattr(self.event_bus, 'publish_sync'):
            try:
                # Request updates from all components
                if self.event_bus:
                    # Format timestamp in a way that works with both PyQt6 and fallbacks
                    if has_pyqt6 and hasattr(QDateTime, 'currentDateTime'):
                        try:
                            # PyQt6 path with safe format string (not relying on Qt.DateFormat.ISODate)
                            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-ddTHH:mm:ss")
                        except (AttributeError, TypeError):
                            # Fallback if specific format is unavailable
                            try:
                                timestamp = QDateTime.currentDateTime().toString("yyyy-MM-ddTHH:mm:ss")
                            except:
                                timestamp = datetime.now().isoformat()
                    else:
                        # Non-PyQt path using standard library
                        timestamp = datetime.now().isoformat()
                        
                    (self.event_bus.publish_sync if hasattr(self.event_bus, 'publish_sync') else self.event_bus.publish)('request_all_updates', {
                        'source': 'main_window',
                        'timestamp': timestamp
                    })
                    logging.info("Published request for all component updates")
            except Exception as e:
                logging.error(f"Error requesting component updates: {e}")
    
    # update_component_status method moved above to avoid duplication
    
    async def initialize_tabs_async(self):
        """Async version of initialize_tabs that properly awaits tab initialization.
        
        This method creates all required tabs, connects them to the event bus,
        waits for all tab initialization to complete, and makes them accessible
        as attributes on the MainWindow for verification.
        """
        import logging, traceback, asyncio
        
        logging.info("Starting asynchronous tab initialization")
        
        # Create internal tab frames dictionary if it doesn't exist
        if not hasattr(self, '_tab_frames'):
            self._tab_frames = {}
            
        # Initialize the tab manager if needed
        if self.tab_manager is None:
            try:
                from gui.tab_manager import TabManager
                self.tab_manager = TabManager(
    notebook=self.notebook if hasattr(self, 'notebook') else None,
    event_bus=self.event_bus,
    redis_connector=self.redis_connector if hasattr(self, 'redis_connector') else None
)
                logging.info("Tab manager initialized")
            except ImportError as e:
                logging.error(f"TabManager import failed: {e}")
                return False
        
        # CRITICAL: Call the TabManager's initialize_all_tabs method which properly
        # imports and instantiates all tab widget classes with their content
        if hasattr(self.tab_manager, 'initialize_all_tabs'):
            try:
                self.tab_manager.initialize_all_tabs()
                logging.info("All tab widgets properly initialized with content")
            except Exception as e:
                logging.error(f"Error initializing tab content: {e}")
                logging.error(traceback.format_exc())
        else:
            logging.error("TabManager missing initialize_all_tabs method")
            
        # Define the required tabs and their titles - for reference and any tabs not covered by initialize_all_tabs
        required_tabs = [
            'dashboard', 'trading', 'mining', 'thoth_ai', 'code_generator',
            'voice', 'wallet', 'api_key', 'vr', 'settings'
        ]
        
        tab_titles = {
            'dashboard': 'Dashboard',
            'trading': 'Trading System',
            'mining': 'Mining Operations',
            'thoth_ai': 'Thoth AI Assistant',
            'code_generator': 'Code Generator',
            'voice': 'Voice Interface',
            'wallet': 'Wallet Manager',
            'api_key': 'API Keys',
            'vr': 'VR Interface',
            'settings': 'Settings'
        }
        
        # Check for any missing tabs that need to be added
        for tab_id in required_tabs:
            title = tab_titles.get(tab_id, tab_id.replace('_', ' ').title())
            
            try:
                # Check if tab already exists
                tabs = getattr(self.tab_manager, 'tabs', {})
                if tab_id not in tabs and hasattr(self.tab_manager, 'add_tab'):
                    # Create the tab with proper title
                    self.tab_manager.add_tab(tab_id, title)
                    logging.info(f"Tab {tab_id} added with title {title}")
            except Exception as e:
                logging.error(f"Error creating tab {tab_id}: {e}")
                logging.error(traceback.format_exc())
        
        # Wait for all tab initialization tasks to complete
        await self._wait_for_tab_initialization()
        
        # Connect tabs to the event bus
        try:
            # Try to import and use TabIntegrator
            try:
                from gui.tab_integration import get_tab_integrator
                tab_integrator = get_tab_integrator(self.event_bus)
                if tab_integrator:
                    success = tab_integrator.integrate_tabs(self)
                    if success:
                        logging.info("All tabs successfully integrated with event bus")
                    else:
                        logging.warning("Some tabs may not be fully integrated with the event bus")
                else:
                    # Connect directly as fallback
                    self._connect_tab_events()
                    logging.info("Connected tabs directly to event bus (integrator unavailable)")
            except ImportError as e:
                logging.warning(f"TabIntegrator import failed: {e}. Using direct event connection.")
                # Connect directly to the event bus as fallback
                self._connect_tab_events()
        except Exception as e:
            logging.error(f"Error connecting tabs to event bus: {e}")
            logging.error(traceback.format_exc())
            
        # Create generic update methods for all tabs
        self._create_tab_update_methods()
        
        # Ensure the tab attributes are fully visible to the verification system
        # Use sync version first as a safety
        self._update_tab_attributes_sync()
        
        # Then use async version that waits for tab initialization to complete
        await self._update_tab_attributes_async()
        
        # Log all created tabs for verification
        if hasattr(self.tab_manager, 'tabs'):
            tab_ids = list(self.tab_manager.tabs.keys())
            logging.info(f"Created tabs: {tab_ids}")
            
            # Log attribute mapping for verification
            mapped_attrs = [attr for attr in dir(self) if attr.endswith('_tab') and not attr.startswith('__')]
            logging.info(f"Mapped tab attributes: {mapped_attrs}")
            
        logging.info("Tabs initialized successfully with real-time data connections")
        return True

    def initialize_tabs(self):
        """Initialize all tabs with their default content and connect them to the event bus.
        
        This method creates all required tabs synchronously, connects them to the event bus,
        and makes them accessible as attributes on the MainWindow for verification.
        
        Instead of just scheduling an async task, this now directly creates tabs synchronously
        to ensure they exist for immediate verification.
        """
        import logging, traceback, asyncio
        
        try:
            # We'll use the synchronous initialization as the primary method now
            # This ensures tabs are created immediately rather than scheduled for later
            logging.info("Using synchronous tab initialization to ensure tabs exist immediately")
            success = self._initialize_tabs_sync()
            if not success:
                logging.error("Synchronous tab initialization failed")
                return False
                
            # Connect tabs to event bus
            if hasattr(self, 'event_bus') and self.event_bus:
                self._connect_tab_events()
                
            # Ensure all tab attributes are properly mapped for verification
            self._update_tab_attributes_sync()
            logging.info("Tabs initialized and mapped synchronously for immediate verification")
            
            # Also schedule the async version for enhanced functionality
            # but don't rely on it for verification
            try:
                task = asyncio.create_task(self._wait_for_tab_initialization())
                if not hasattr(self, 'tab_init_task'):
                    self.tab_init_task = task
                logging.info("Additional async enhancement scheduled but not awaited")
            except Exception as e:
                logging.warning(f"Could not schedule async enhancement: {e}")
                
            # Verify tabs were created successfully
            if self.tab_manager is not None and hasattr(self.tab_manager, 'tabs') and self.tab_manager.tabs is not None:
                tab_ids = list(self.tab_manager.tabs.keys())
                logging.info(f"Created tabs synchronously: {tab_ids}")
            else:
                logging.warning("No tabs were created - TabManager.tabs is None or not accessible")
                
                # Log attribute mapping for verification
                mapped_attrs = [attr for attr in dir(self) if attr.endswith('_tab') and not attr.startswith('__')]
                logging.info(f"Mapped tab attributes synchronously: {mapped_attrs}")
            
            return True
            
        except Exception as e:
            logging.error(f"Error in initialize_tabs: {e}")
            logging.error(traceback.format_exc())
            return False
    
    def _initialize_tabs_sync(self):
        """Synchronous fallback for tab initialization."""
        import logging, traceback
        
        # Initialize the tab manager if needed
        if self.tab_manager is None:
            try:
                from gui.tab_manager import TabManager
                self.tab_manager = TabManager(
    notebook=self.notebook if hasattr(self, 'notebook') else None,
    event_bus=self.event_bus,
    redis_connector=self.redis_connector if hasattr(self, 'redis_connector') else None
)
                logging.info("Tab manager initialized")
            except ImportError as e:
                logging.error(f"TabManager import failed: {e}")
                return False
        
        # Try to integrate tab manager with tab_integration_master for enhanced functionality
        try:
            try:
                from gui.tab_integration_master import TabIntegrationMaster
                tab_master = TabIntegrationMaster(self.tab_manager, self.event_bus)
                tab_master.initialize()
                logging.info("TabIntegrationMaster initialized successfully")
            except ImportError as e:
                logging.warning(f"Could not import TabIntegrationMaster: {e}")
        except Exception as e:
            logging.error(f"Error integrating TabIntegrationMaster: {e}")
            logging.error(traceback.format_exc())
        
        # Define the required tabs and their titles
        required_tabs = [
            'dashboard', 'trading', 'mining', 'thoth_ai', 'code_generator',
            'voice', 'wallet', 'api_key', 'vr', 'settings'
        ]
        
        tab_titles = {
            'dashboard': 'Dashboard',
            'trading': 'Trading System',
            'mining': 'Mining Operations',
            'thoth_ai': 'Thoth AI Assistant',
            'code_generator': 'Code Generator',
            'voice': 'Voice Interface',
            'wallet': 'Wallet Manager',
            'api_key': 'API Keys',
            'vr': 'VR Interface',
            'settings': 'Settings'
        }
        
        # First pass - create all required tabs
        for tab_id in required_tabs:
            title = tab_titles.get(tab_id, tab_id.replace('_', ' ').title())
            
            try:
                # Check if tab already exists
                tabs = getattr(self.tab_manager, 'tabs', {})
                if tab_id not in tabs and hasattr(self.tab_manager, 'add_tab'):
                    # Create the tab with proper title
                    self.tab_manager.add_tab(tab_id, title)
                    logging.info(f"Tab {tab_id} added with title {title}")
            except Exception as e:
                logging.error(f"Error creating tab {tab_id}: {e}")
                logging.error(traceback.format_exc())
        
        # Connect tabs to the event bus
        try:
            # Try to import and use TabIntegrator
            try:
                from gui.tab_integration import get_tab_integrator
                tab_integrator = get_tab_integrator(self.event_bus)
                if tab_integrator:
                    success = tab_integrator.integrate_tabs(self)
                    if success:
                        logging.info("All tabs successfully integrated with event bus")
                    else:
                        logging.warning("Some tabs may not be fully integrated with the event bus")
            except ImportError as e:
                logging.warning(f"TabIntegrator import failed: {e}. Using direct event connection.")
                # Connect directly to the event bus as fallback
                self._connect_tab_events()
        except Exception as e:
            logging.error(f"Error connecting tabs to event bus: {e}")
            logging.error(traceback.format_exc())
            
        # Create generic update methods for all tabs
        self._create_tab_update_methods()
            
        # Ensure the tab attributes are fully visible to the verification system
        self._update_tab_attributes_sync()
            
        logging.info("Tabs initialized successfully with real-time data connections (sync mode)")
        return True
    
    async def _wait_for_tab_initialization(self):
        """Wait for all tab initialization tasks to complete.
        
        This method finds all tab initialization tasks that were created when tabs were added
        and awaits them, ensuring all tabs are fully initialized before proceeding.
        """
        import asyncio
        
        # Find all tab init tasks
        pending_tasks = []
        
        # Get all init_tasks from tab frames
        if self.tab_manager is not None and hasattr(self.tab_manager, 'tabs') and self.tab_manager.tabs is not None:
            for tab_id, tab_frame in self.tab_manager.tabs.items():
                if hasattr(tab_frame, 'init_task') and tab_frame.init_task is not None:
                    pending_tasks.append(tab_frame.init_task)
                    logging.info(f"Found pending initialization task for tab {tab_id}")
        
        # If we found any tasks, await them all
        if pending_tasks:
            logging.info(f"Waiting for {len(pending_tasks)} tab initialization tasks to complete")
            try:
                await asyncio.gather(*pending_tasks)
                logging.info("All tab initialization tasks completed successfully")
            except Exception as e:
                logging.error(f"Error during tab initialization: {e}")
                import traceback
                logging.error(traceback.format_exc())
        else:
            logging.info("No pending tab initialization tasks found")
    
    async def _update_tab_attributes_async(self):
        """Async version of _update_tab_attributes that waits for tab initialization.
        
        This method first waits for all tab initialization tasks to complete, then
        updates the tab attributes to ensure they're accessible to the verification system.
        """
        # Wait for all tab initialization to complete
        await self._wait_for_tab_initialization()
        
        # Now update tab attributes
        # Map of tab_id to attribute name expected by verification framework
        tab_attribute_mapping = {
            'dashboard': 'dashboard_frame',
            'trading': 'trading_frame',
            'mining': 'mining_frame',
            'thoth_ai': 'thoth_ai_frame',
            'code_generator': 'code_generator_frame',
            'voice': 'voice_frame',
            'wallet': 'wallet_frame',
            'api_key': 'api_key_frame',
            'vr': 'vr_frame',
            'settings': 'settings_frame'
        }
        
        # Create an internal dictionary to store tab frames if it doesn't exist
        if not hasattr(self, '_tab_frames'):
            self._tab_frames = {}
            
        # For each tab in the TabManager, store it in the internal dictionary
        if self.tab_manager is not None and hasattr(self.tab_manager, 'tabs') and self.tab_manager.tabs is not None:
            for tab_id, tab_frame in self.tab_manager.tabs.items():
                if tab_id in tab_attribute_mapping:
                    attr_name = tab_attribute_mapping[tab_id]
                    # Store the tab frame in the internal dictionary
                    self._tab_frames[attr_name] = tab_frame
                    logging.debug(f"Stored tab {tab_id} as {attr_name} in internal dictionary")
            
            # Log how many tab attributes were set
            tab_count = sum(1 for tab_id in self.tab_manager.tabs if tab_id in tab_attribute_mapping)
            logging.info(f"Set {tab_count} tab attributes on MainWindow for verification")
        else:
            logging.warning("TabManager or tabs attribute not available for mapping tab attributes")
            logging.info("No tab attributes set on MainWindow - TabManager unavailable")
    
    def _update_tab_attributes(self):
        """Updates tab attributes on the main window to ensure they're accessible to the verification system.
        
        This method stores tab references in an internal dictionary that the property getters
        can access, avoiding direct attribute setting which conflicts with the property methods.
        
        Note: This synchronous version creates an async task for _update_tab_attributes_async
        but doesn't wait for it to complete. For proper synchronization, use _update_tab_attributes_async directly.
        """
        import asyncio
        
        try:
            # Create a task for the async version but don't await it
            # This allows this method to be called from synchronous code
            asyncio.create_task(self._update_tab_attributes_async())
            logging.info("Created async task for updating tab attributes")
        except Exception as e:
            logging.error(f"Error creating async task for tab attribute update: {e}")
            
            # Fallback to synchronous update if async fails
            self._update_tab_attributes_sync()
            
    def _create_tab_update_methods(self):
        """Create update methods for each tab to handle real-time data from the event bus.
        
        This method ensures each tab frame has an 'update' method that can process
        data updates from the event bus, even if a specific update method is not
        explicitly defined on the tab frame. This helps with consistent real-time updates.
        """
        import logging
        import types
        import traceback
        
        if not self.tab_manager or not hasattr(self.tab_manager, 'tabs'):
            logging.warning("No tab manager or tabs available to create update methods")
            return
        
        # Define a generic update method for tabs that don't have one
        def generic_update(tab_frame, data):
            """Generic update method for tab frames without specific update methods.
            
            This method identifies tab elements that could be updated based on data
            fields and updates them accordingly.
            """
            try:
                logging.debug(f"Generic update called for {getattr(tab_frame, 'tab_id', 'unknown')} with data: {data}")
                
                # Look for matching attributes and update them
                updated_count = 0
                
                # Update simple label/text attributes first
                for key, value in data.items():
                    # Skip special fields
                    if key.startswith('_'):
                        continue
                        
                    # Try to find matching elements
                    for attr_prefix in ['label_', 'text_', 'status_', 'value_', '']:
                        attr_name = f"{attr_prefix}{key}"
                        if hasattr(tab_frame, attr_name):
                            # Get the attribute
                            attr = getattr(tab_frame, attr_name)
                            
                            # Handle different types of UI elements
                            try:
                                # Check if it's a StringVar or similar
                                if hasattr(attr, 'set'):
                                    attr.set(str(value))
                                    updated_count += 1
                                # Check if it's a label or similar with text/setText
                                elif hasattr(attr, 'setText'):
                                    attr.setText(str(value))
                                    updated_count += 1
                                # Check if it has a configure method (Tkinter)
                                elif hasattr(attr, 'configure'):
                                    attr.configure(text=str(value))
                                    updated_count += 1
                                # Check if it has a text property
                                elif hasattr(attr, 'text'):
                                    attr.text = str(value)
                                    updated_count += 1
                            except Exception as e:
                                logging.warning(f"Failed to update {attr_name}: {e}")
                
                logging.info(f"Generic update: Updated {updated_count} attributes on {getattr(tab_frame, 'tab_id', 'unknown')} tab")
                return updated_count > 0
            except Exception as e:
                logging.error(f"Error in generic update: {e}")
                logging.error(traceback.format_exc())
                return False
                
        # Go through each tab and ensure it has an update method
        for tab_id, tab_frame in self.tab_manager.tabs.items():
            # If tab doesn't have an update method, add the generic one
            if not hasattr(tab_frame, 'update') or not callable(getattr(tab_frame, 'update', None)):
                logging.info(f"Adding generic update method to {tab_id} tab")
                
                # Create a bound method for this specific tab
                update_method = types.MethodType(generic_update, tab_frame)
                
                # Attach the method to the tab frame
                setattr(tab_frame, 'update', update_method)
                
                # Also store the tab_id on the frame for reference
                if not hasattr(tab_frame, 'tab_id'):
                    setattr(tab_frame, 'tab_id', tab_id)
                    
        logging.info("Tab update methods created/verified for all tabs")
            
    def _update_tab_attributes_sync(self):
        """Update the main window with tab frames for verification.
        
        This method maps from tab_id to the expected attribute name format that the
        verification system is looking for (tab_name_frame) and directly sets these
        attributes on the MainWindow instance.
        """
        import logging
        
        # Initialize mapping for tab_id -> expected attribute name
        tab_attribute_mapping = {
            'dashboard': 'dashboard_frame',
            'trading': 'trading_frame',
            'mining': 'mining_frame',
            'thoth_ai': 'thoth_ai_frame',
            'code_generator': 'code_generator_frame',
            'voice': 'voice_frame',
            'wallet': 'wallet_frame',
            'api_key': 'api_key_frame',
            'vr': 'vr_frame',
            'settings': 'settings_frame'
        }
        
        # Make sure we have a tab_manager with tabs
        if not hasattr(self, 'tab_manager') or not self.tab_manager:
            logging.error("Tab manager not initialized, cannot update tab attributes")
            return {}
        
        # Initialize internal tab frame storage if needed
        if not hasattr(self, '_tab_frames'):
            self._tab_frames = {}
            
        # Create a counter to track successful mappings
        successful_mappings = 0
            
        # Create a mapping from tab_id to frame for verification
        for tab_id, expected_attr in tab_attribute_mapping.items():
            try:
                if hasattr(self.tab_manager, 'tabs') and self.tab_manager.tabs and tab_id in self.tab_manager.tabs:
                    # Get the frame from the tab manager
                    tab_frame = self.tab_manager.tabs[tab_id]
                    
                    # Set the attribute directly on the MainWindow object with the _frame suffix
                    # that the verification system expects
                    setattr(self, expected_attr, tab_frame)
                    
                    # Also store it in our internal mapping for reference
                    self._tab_frames[expected_attr] = tab_frame
                    
                    logging.info(f"Tab attribute set: {expected_attr} -> {tab_id}")
                    successful_mappings += 1
                    
                    # For backward compatibility, also store attributes with old naming convention in _tab_frames
                    old_attr_name = f"{tab_id}_tab"
                    if tab_id == 'thoth_ai':
                        old_attr_name = 'thoth_tab'
                    elif tab_id == 'voice':
                        old_attr_name = 'ai_tab'
                    elif tab_id == 'api_key':
                        old_attr_name = 'api_keys_tab'
                    
                    # Instead of directly setting attributes (which fails with properties),
                    # add to our internal _tab_frames dictionary that property getters use
                    self._tab_frames[old_attr_name] = tab_frame
                    logging.info(f"For backward compatibility: {old_attr_name} -> {tab_id} (stored in _tab_frames)")
                else:
                    logging.warning(f"Tab {tab_id} not found in tab manager, skipping attribute mapping")
            except Exception as e:
                logging.error(f"Error mapping tab attribute for {tab_id}: {e}")
                logging.error(f"Exception details: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
        
        logging.info(f"Synchronized {successful_mappings} tab attributes for verification")
        return self._tab_frames
        
    def _get_tab_id_for_component(self, component_type):
        """Map a component type to its corresponding tab ID.
        
        This mapping is necessary because some components may have different names
        than their associated tab IDs. This method provides the translation.
        
        Args:
            component_type (str): The type of component to map
            
        Returns:
            str: The corresponding tab ID, or None if no mapping exists
        """
        # Default mapping where component types match tab IDs
        direct_mappings = [
            'dashboard', 'trading', 'mining', 'wallet', 'settings', 'vr'
        ]
        
        # Special mappings for components with different names than their tabs
        special_mappings = {
            'thoth': 'thoth_ai',
            'ai': 'voice',
            'voice_assistant': 'voice',
            'code_gen': 'code_generator',
            'api_keys': 'api_key',
            'mcp': 'api_key',  # MCP is shown in API key tab
            'vr_interface': 'vr',
            'virtual_reality': 'vr',
            'configuration': 'settings',
            'config': 'settings'
        }
        
        # Lowercase the component type for case-insensitive matching
        component_type = component_type.lower() if component_type else ''
        
        # Direct match (component type is the tab ID)
        if component_type in direct_mappings:
            return component_type
        
        # Special mapping
        if component_type in special_mappings:
            return special_mappings[component_type]
        
        # Try to find a partial match
        for tab_id in direct_mappings:
            if tab_id in component_type:
                return tab_id
        
        for comp_type, tab_id in special_mappings.items():
            if comp_type in component_type:
                return tab_id
        
        # No mapping found
        return None
        
    def update_frame(self, component_type, data):
        """Update a specific frame with data.
        
        Args:
            component_type (str): The type of component/frame to update
            data (Dict[str, Any]): The data to display in the frame
        """
        try:
            # Get the tab ID for this component type
            tab_id = self._get_tab_id_for_component(component_type)
            if tab_id and hasattr(self, f'{tab_id}_tab'):
                tab = getattr(self, f'{tab_id}_tab')
                if hasattr(tab, 'update') and callable(tab.update):
                    tab.update(data)
                    return True
            return False
            tabs = getattr(self.tab_manager, 'tabs', {}) if self.tab_manager else {}
                
            if tab_id in tabs:
                logger.info(f"Updating tab: {tab_id}")
                tab_info = tabs[tab_id]
                
                # Get the frame from the tab info if it exists
                frame = tab_info.get('frame') if isinstance(tab_info, dict) else None
                
                # If we have a frame with an update method, call it
                if frame and hasattr(frame, 'update') and callable(getattr(frame, 'update', None)):
                    frame.update(data)
                    logger.info(f"Frame {component_type} updated successfully")
                    return
                else:
                    logger.warning(f"Frame for {component_type} does not have a callable update method")
            else:
                logger.warning(f"Tab {tab_id} not found for component {component_type}")
            
            # If we didn't return yet, try other update methods
                
            # Try component-specific update method
            method_name = f"update_{component_type}_frame"
            if hasattr(self, method_name) and callable(getattr(self, method_name, None)):
                getattr(self, method_name)(data)
                logger.info(f"Updated {component_type} using specific update method")
                return
                
            # Ensure TabManager has the required methods
            if self.tab_manager is None:
                logger.error("TabManager is None - cannot update frames")
                return
                
            if hasattr(self.tab_manager, 'update_tab'):
                try:
                    # First update all standard tabs - check if tabs attribute exists
                    if hasattr(self.tab_manager, 'tabs') and self.tab_manager.tabs:
                        for tab_id in self.tab_manager.tabs.keys():  # TabManager keeps tabs in dict
                            self.tab_manager.update_tab(tab_id)
                    update_content_fn = getattr(self.tab_manager, 'update_tab_content', None)
                    if callable(update_content_fn):
                        try:
                            update_content_fn(component_type, data)
                            logger.info(f"Updated {component_type} tab content through tab manager")
                        except Exception as update_error:
                            logger.error(f"Error updating tab content for {component_type}: {update_error}")
                except Exception as e:
                    logger.error(f"Error updating tab content for {component_type}: {e}")
                    logger.error(traceback.format_exc())
                    
        except Exception as e:
            logger.error(f"Error updating frame {component_type}: {e}")
            logger.error(traceback.format_exc())
            
    @property
    def dashboard_tab(self):
        """Property for accessing the dashboard tab for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('dashboard_tab', None)
        return None
        
    @property
    def trading_tab(self):
        """Property for accessing the trading tab for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('trading_tab', None)
        return None
        
    @property
    def mining_tab(self):
        """Property for accessing the mining tab for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('mining_tab', None)
        return None
        
    @property
    def wallet_tab(self):
        """Property for accessing the wallet tab for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('wallet_tab', None)
        return None
        
    @property
    def vr_tab(self):
        """Property for accessing the vr tab for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('vr_tab', None)
        return None
        
    @property
    def ai_tab(self):
        """Property for accessing the AI tab (voice interface) for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('ai_tab', None)
        return None
        
    @property
    def thoth_tab(self):
        """Property for accessing the thoth tab for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('thoth_tab', None)
        return None
        
    @property
    def code_generator_tab(self):
        """Property for accessing the code generator tab for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('code_generator_tab', None)
        return None
        
    @property
    def api_keys_tab(self):
        """Property for accessing the api keys tab for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('api_keys_tab', None)
        return None
        
    @property
    def settings_tab(self):
        """Property for accessing the settings tab for verification."""
        if hasattr(self, '_tab_frames'):
            return self._tab_frames.get('settings_tab', None)
        return None

# Define KingdomMainWindow as an alias for MainWindow to fix import issues in launch_kingdom.py
class KingdomMainWindow(MainWindow):
    """Kingdom AI MainWindow implementation.
    
    This is an alias for MainWindow to maintain backward compatibility with
    other modules that expect KingdomMainWindow. This class inherits all
    functionality from MainWindow.
    """
    pass

def run_application():
    """Run the Kingdom AI application with proper async event loop setup.
    
    This function sets up the QApplication, initializes the event bus,
    creates the main window, and starts the Qt event loop with qasync integration
    for proper asyncio support.
    """
    try:
        # Import qasync here to avoid circular imports
        import qasync
        from qasync import QEventLoop, asyncSlot
        
        # Create application instance
        app = QApplication(sys.argv)
        
        # Create and show main window with event bus
        from core.event_bus import EventBus
        
        # Initialize event bus with async support
        event_bus = EventBus()
        
        # Create main window
        main_window = MainWindow(root=None, event_bus=event_bus)
        main_window.show()
        
        # Set up the asyncio event loop for Qt
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # Create a task to initialize tabs after the event loop is running
        async def initialize_async():
            try:
                # Initialize tabs asynchronously
                if hasattr(main_window, 'initialize_tabs_async'):
                    await main_window.initialize_tabs_async()
                # Set up event subscriptions after tabs are initialized
                if hasattr(main_window, '_setup_event_subscriptions'):
                    await main_window._setup_event_subscriptions()
            except Exception as e:
                logger.error(f"Error during async initialization: {e}")
                logger.error(traceback.format_exc())
        
        # Schedule the async initialization
        asyncio.ensure_future(initialize_async())
        
        # Start the event loop
        with loop:
            try:
                loop.run_forever()
            except asyncio.CancelledError:
                logger.info("Application event loop was cancelled")
            except Exception as e:
                logger.critical(f"Error in event loop: {e}")
                logger.critical(traceback.format_exc())
            finally:
                loop.close()
                
        return 0
        
    except ImportError as e:
        logger.critical(f"Missing required dependency: {e}")
        logger.critical("Please install qasync: pip install qasync")
        return 1
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        logger.critical(traceback.format_exc())
        return 1
        return 1

if __name__ == "__main__":
    # Set up logging first
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('kingdom_ai.log')
        ]
    )
    
    # Run the application with proper error handling
    sys.exit(run_application())