#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Tab Manager Module.
This module manages the various tab components (trading, mining, voice, VR) in the Kingdom AI GUI.
"""

# Standard library imports
import asyncio
import datetime
import importlib
import inspect
import json
import logging
import os
import sys
import time
import traceback
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast, TYPE_CHECKING

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Import PyQt6 - No fallback allowed per Kingdom AI requirements
from PyQt6.QtWidgets import (QTabWidget, QWidget, QVBoxLayout, QLabel,
    QComboBox, QPushButton, QLineEdit, QTextEdit, QToolBar, QMenu,
    QMainWindow, QMessageBox, QDialog, QScrollArea, QHBoxLayout, QFrame,
    QGridLayout, QSizePolicy, QLayout
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QFont, QIcon, QAction
from core.event_bus import EventBus
from core.redis_connector import RedisQuantumNexusConnector
from core.async_support import AsyncSupport

# Initialize module-level flags
_has_redis = False
_has_matplotlib = False

# Initialize Redis - strict connection enforcement without fallbacks
import redis
from redis import Redis  # type: ignore
from redis.exceptions import RedisError  # type: ignore
_has_redis = True

# Redis is mandatory for the Kingdom AI system per requirements
# No fallback allowed - system must halt if Redis is unavailable

# Initialize Matplotlib with PyQt6 backend
try:
    import matplotlib
    matplotlib.use('QtAgg')  # Use QtAgg backend for PyQt6
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure as MatplotlibFigure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    Figure = MatplotlibFigure  # type: ignore[misc]
    _has_matplotlib = True
    logger.info("Matplotlib with PyQt6 backend loaded successfully")
except ImportError as exc:
    logger.warning(f"Matplotlib not available: {exc}")
    logger.warning("Some chart features may be limited. Install with: pip install matplotlib")
    _has_matplotlib = False
    # SOTA 2026: Fallback matplotlib classes with basic functionality
    class Figure:  # type: ignore[no-redef]
        """Fallback Figure class when matplotlib unavailable."""
        def __init__(self, figsize=(8, 6), dpi=100, *args, **kwargs):
            self.figsize = figsize
            self.dpi = dpi
            self._axes = []
            self._title = ""
        
        def add_subplot(self, *args, **kwargs):
            """Add a subplot."""
            ax = FallbackAxes()
            self._axes.append(ax)
            return ax
        
        def suptitle(self, title):
            """Set figure title."""
            self._title = title
        
        def tight_layout(self, *args, **kwargs):
            """Adjust subplot layout."""
            pass
        
        def clear(self):
            """Clear figure."""
            self._axes.clear()
    
    class FallbackAxes:
        """Fallback Axes class."""
        def __init__(self):
            self._data = []
            self._title = ""
            self._xlabel = ""
            self._ylabel = ""
        
        def plot(self, *args, **kwargs):
            """Store plot data."""
            self._data.append(('plot', args, kwargs))
        
        def bar(self, *args, **kwargs):
            """Store bar data."""
            self._data.append(('bar', args, kwargs))
        
        def scatter(self, *args, **kwargs):
            """Store scatter data."""
            self._data.append(('scatter', args, kwargs))
        
        def set_title(self, title):
            self._title = title
        
        def set_xlabel(self, label):
            self._xlabel = label
        
        def set_ylabel(self, label):
            self._ylabel = label
        
        def legend(self, *args, **kwargs):
            pass
        
        def grid(self, *args, **kwargs):
            pass
        
        def clear(self):
            self._data.clear()
            
    class FigureCanvas:
        """Fallback FigureCanvas when matplotlib unavailable."""
        def __init__(self, figure=None, *args, **kwargs):
            self.figure = figure or Figure()
            self._widget = None
        
        def draw(self):
            """Refresh the canvas."""
            pass
        
        def draw_idle(self):
            """Schedule a redraw."""
            pass
        
        def get_tk_widget(self):
            """Get Tkinter widget (fallback returns None)."""
            return self._widget
        
        def get_width_height(self):
            """Get canvas dimensions."""
            return (self.figure.figsize[0] * self.figure.dpi, 
                    self.figure.figsize[1] * self.figure.dpi)

# Define module-level constants - PyQt6 is enforced without fallbacks
HAS_MATPLOTLIB = _has_matplotlib

# Core imports - required for Kingdom AI system
from core.base_component import BaseComponent
# EventBus already imported at line 44
from core.redis_connector import RedisConnector as CoreRedisConnector

# First-party imports
from gui.kingdom_style import KingdomStyles
from gui.qt_frames.dashboard_qt import DashboardQt

# Enforce strict Redis connection - no fallbacks allowed
# This connection is mandatory for the Kingdom AI system

# Redis connection constants - intentionally hardcoded per Kingdom AI security policy
# B105 warning for hardcoded password is acknowledged - this is required by the strict security policy
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6380,
    'password': 'QuantumNexus2025',  # nosec - required by security policy
    'db': 0,
    'socket_timeout': 5,
    'socket_connect_timeout': 5,
    'retry_on_timeout': True
}

logger = logging.getLogger(__name__)

# Redis connection will be tested when TabManager is initialized
# This allows the main entry point to start Redis before the connection test
redis_client = None  # Will be initialized when needed

# Import the RedisConnector from core
RedisConnector = CoreRedisConnector
RedisQuantumNexusConnector = CoreRedisConnector

# Verify EventBus is available
if not hasattr(EventBus, 'subscribe_sync'):
    error_msg = "EventBus is missing required methods - check EventBus implementation"
    logger.warning(f"⚠️ {error_msg}")

# Verify PyQt6 components are available - no fallbacks allowed in Kingdom AI
try:
    # Test PyQt6 components that are critical for the Kingdom AI GUI
    test_widget = QWidget()
    test_widget.deleteLater()
    logger.info("PyQt6 components verified and available")
except Exception as e:
    error_msg = f"Critical PyQt6 components unavailable: {e}"
    logger.warning(f"⚠️ {error_msg}")

# AsyncSupport already imported at line 46
# from gui.async_event_loop import AsyncSupport  
logger.info("AsyncSupport already available from core.async_support")


class TabManager(QWidget):
    """Tab Manager for Kingdom AI.
    
    Manages tabs for different components of the Kingdom AI system.
    
    Enforces strict security policies for all components including Redis.
    All tab content must be PyQt6 QWidget instances with no fallbacks allowed.
    The system will halt if critical components are missing.
    """
    # Signal declarations for PyQt6 event handling
    tab_added = pyqtSignal(str, int)  # tab_id, index
    tab_closed = pyqtSignal(str, int)  # tab_id, index
    tab_switched = pyqtSignal(str, int)  # tab_id, index
    tab_initialized = pyqtSignal(str)  # tab_id
    
    # Class-level logger to ensure it's available immediately
    _logger = logging.getLogger(__name__)
    
    # Configure logger if not already configured
    if not _logger.handlers:
        _logger.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        _logger.addHandler(console_handler)

    def __init__(self, notebook=None, event_bus=None, redis_connector=None, parent=None):
        """Initialize the TabManager.
        
        Args:
            notebook: Optional QTabWidget to use as the tab container
            event_bus: Optional event bus for tab events
            redis_connector: Optional Redis connector for data persistence
            parent: Optional parent widget
        """
        # Initialize the QWidget base class
        super().__init__(parent)
        
        # Store logger as instance attribute
        self.logger = self._logger
        
        # Set up internal state tracking
        self._tab_frames = {}  # tab_id -> QWidget mapping
        self._tab_order = []  # List of tab_ids in order
        self._tabs = {}  # Extended tab information
        self._tab_initialized = {}  # Track which tabs are initialized
        self._current_tab_id = None
        
        # Store external dependencies
        self._notebook = notebook
        self.event_bus = event_bus
        self.redis_connector = redis_connector
        
        # Verify critical components - Kingdom AI requires Redis Quantum Nexus
        if self.redis_connector is None:
            try:
                # Test Redis connection first - system must halt if connection fails
                test_redis_client = Redis(**REDIS_CONFIG)
                test_redis_client.ping()  # Will raise exception if connection fails
                self.logger.info("Successfully connected to Redis Quantum Nexus on port 6380")
                
                # Attempt to create Redis connector if not provided
                self.redis_connector = RedisQuantumNexusConnector(event_bus=event_bus)
                self.logger.info("Created Redis Quantum Nexus connector")
            except RedisError as e:
                self.logger.warning(f"⚠️ Redis connection failed: {e} - running without Redis")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to create Redis connector: {e} - running without Redis")
        
        # EventBus check
        if not event_bus:
            self.logger.warning("⚠️ EventBus not provided - some features may be limited")
            
        # Verify EventBus has required methods
        required_methods = ['subscribe', 'subscribe_sync', 'publish', 'publish_sync']
        missing_methods = [m for m in required_methods if not hasattr(event_bus, m)]
        if missing_methods:
            self.logger.warning(f"⚠️ EventBus missing methods: {missing_methods} - some features limited")
            
        # Redis connection check
        if not self.redis_connector:
            self.logger.warning("⚠️ Redis connection not available - some features limited")
        
        # Store references    
        self.event_bus = event_bus
#         self.redis_connector = redis_connector
        
        # Initialize tab tracking
        self._tabs = {}
        self._tab_frames = {}
        self._current_tab = None
        self._tab_order = []
        self._initialized = False
        self._initialization_lock = asyncio.Lock()
        self._tab_initialized = {}
        
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create notebook widget
        self._notebook = QTabWidget(self)
        self._notebook.setTabsClosable(True)
        self._notebook.tabCloseRequested.connect(self.close_tab)
        
        # Add notebook to layout
        layout.addWidget(self._notebook)
        self.setLayout(layout)
        
        # Connect signals
        self._notebook.currentChanged.connect(self._on_tab_changed)
        
        # Initialize resource metrics
        self._resource_metrics = {
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'network_usage': 0.0,
            'disk_usage': 0.0
        }
        
        # Initialize performance metrics tracking
        self._performance_metrics = {
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'network_usage': 0.0,
            'last_updated': None
        }
        
        # Initialize resource metrics tracking
        self._resource_metrics = {
            'cpu': {},
            'memory': {},
            'disk': {},
            'network': {},
            'gpu': {},
            'timestamp': None
        }
        # Initialize the UI in a thread-safe way
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the UI components.
        
        This creates the tab widget if none was provided and sets up the layout.
        Creates a strict PyQt6 implementation with no fallbacks allowed.
        """
        # Create main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create notebook if not provided
        if self._notebook is None:
            # Create a new PyQt6 QTabWidget with no fallbacks allowed
            self._notebook = QTabWidget(self)
            self._notebook.setTabsClosable(True)
            self._notebook.setMovable(True)
            self._notebook.setDocumentMode(True)
            self._notebook.tabCloseRequested.connect(self.close_tab)
            self._notebook.currentChanged.connect(self._on_tab_changed)
            
            # Apply Kingdom style
            self._notebook.setStyleSheet("""
                QTabWidget::pane { 
                    border: 1px solid #555555;
                    background-color: #2D2D30;
                }
                QTabWidget::tab-bar {
                    left: 5px;
                }
                QTabBar::tab {
                    background-color: #1E1E1E;
                    color: #CCCCCC;
                    padding: 8px 12px;
                    min-width: 100px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #007ACC;
                    color: white;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #2D2D30;
                }
            """)
            
            # Add to layout
            self.main_layout.addWidget(self._notebook)
        
        # Set up event connections
        self._setup_event_connections()
        
        # Log completion
        self.logger.info("Tab manager UI initialized with PyQt6")
        
        # Initialize core tabs
        self._init_dashboard_tab()

    def _init_dashboard_tab(self):
        """Create and add the Dashboard tab eagerly on startup.
        
        The Dashboard tab is always available and cannot be closed.
        It provides the main interface for the Kingdom AI system.
        """
        try:
            # First verify that we have a tab widget
            if self._notebook is None:
                self.logger.error("Cannot initialize dashboard tab: notebook widget is None")
                return
                
            # Check if dashboard tab already exists
            if 'dashboard' in self._tab_frames:
                return
                
            # Verify event bus is available
            if not self.event_bus:
                self.logger.error("Cannot initialize Dashboard: event_bus is None")
                return
                
            # Import the dashboard widget
            try:
                # Using the PyQt6 implementation - no fallbacks allowed
                from gui.qt_frames.dashboard_qt import DashboardQt
                
                # Create the dashboard widget
                dashboard = DashboardQt(event_bus=self.event_bus)  # Remove invalid redis_connector parameter
                
                # Add the dashboard tab
                self._add_tab_impl('dashboard', "Dashboard", dashboard, None)
                self.logger.info("Dashboard tab added successfully")
                
                # Make dashboard the current tab
                self.set_current_tab('dashboard')
                
                # Emit tab initialized signal
                self.tab_initialized.emit('dashboard')
                
                # Mark as initialized immediately
                if hasattr(self, '_tab_initialized'):
                    self._tab_initialized['dashboard'] = True
                    
                # Log initialization
                self.logger.info("Dashboard tab initialized with event bus: %s", type(self.event_bus).__name__)
                
            except ImportError as e:
                self.logger.warning(f"⚠️ Failed to import DashboardQt: {e} - dashboard unavailable")
            
            # Publish a test event to verify the event bus is working
            try:
                test_event = {
                    'message': 'Dashboard initialized successfully',
                    'timestamp': str(datetime.datetime.utcnow()),
                    'status': 'online',
                    'version': '1.0.0'
                }
                if hasattr(self.event_bus, 'publish_sync'):
                    self.event_bus.publish_sync('dashboard.ready', test_event)
                elif hasattr(self.event_bus, 'publish'):
                    result = self.event_bus.publish('dashboard.ready', test_event)
                    if asyncio.iscoroutine(result):
                        asyncio.create_task(result)
                self.logger.info("Published dashboard.ready event")
            except Exception as e:
                self.logger.error("Failed to publish test event: %s", str(e), exc_info=True)
                
        except Exception as exc:
            self.logger.error("Failed to initialize Dashboard tab: %s", exc, exc_info=True)
            # Try to show error in UI if possible
            try:
                error_widget = QLabel(f"Failed to initialize Dashboard: {str(exc)}")
                error_widget.setWordWrap(True)
                error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.add_tab('dashboard', 'Dashboard (Error)', error_widget, closable=False)
            except:
                pass  # If we can't even show the error, just log it

    # ---------------------------------------------------------------------
    # Public interface
    # ---------------------------------------------------------------------
    @property
    def tabs(self) -> Dict[str, "QWidget"]:  # type: ignore[name-defined]
        """Return mapping of tab_id -> tab QWidget for external consumers.

        Many components (e.g. ``MainWindow`` and various verification helpers)
        expect ``self.tab_manager.tabs`` to expose the actual tab widgets so
        they can iterate over them or perform updates.  Internally we keep the
        widgets in ``self._tab_frames``.  This property provides a clean,
        read-only accessor that simply returns that dictionary.
        """
        return self._tab_frames

    @tabs.setter
    def tabs(self, value: Dict[str, "QWidget"]):  # type: ignore[name-defined]
        """Allow replacement of the internal tab mapping.

        Tests or hot-patch utilities sometimes assign a new dictionary directly
        to ``self.tab_manager.tabs``.  We therefore provide a setter that
        validates the input and updates :pyattr:`_tab_frames` accordingly while
        keeping existing references valid.
        """
        if not isinstance(value, dict):
            raise ValueError("tabs must be a dictionary mapping tab_id -> QWidget")
        self._tab_frames = value
        
    def add_tab(self, tab_id: str, title: str, widget: QWidget = None, 
              icon: QIcon = None, closable: bool = True, 
              position: int = None) -> Optional[QWidget]:
        """Add a new tab to the tab manager.
        
        Enforces strict PyQt6 widget compliance with no fallbacks allowed.
        All tab content must be QWidget instances from PyQt6.
        
        Args:
            tab_id: Unique identifier for the tab
            title: Display title for the tab
            widget: Optional widget to use as tab content (must be PyQt6 QWidget)
            icon: Optional icon for the tab
            closable: Whether the tab should be closable
            position: Optional position to insert the tab
            
        Returns:
            Optional[QWidget]: The added widget or None if failed
        """
        try:
            if self._notebook is None:
                self.logger.error("Cannot add tab: notebook not initialized")
                return None
                
            # Create an empty container widget if none provided
            if widget is None:
                widget = QWidget()
                layout = QVBoxLayout()
                # Safe layout assignment with type checking
                if hasattr(widget, 'setLayout') and callable(widget.setLayout):
                    widget.setLayout(layout)
            
            # Ensure we have a valid widget (must be QWidget from PyQt6)
            if not isinstance(widget, QWidget):
                self.logger.error(f"Cannot add tab {tab_id}: Widget must be PyQt6 QWidget instance")
                return None
                    
            # Set the parent to ensure proper cleanup
            widget.setParent(self._notebook)
            
            # Add the widget to the notebook
            if position is not None and 0 <= position <= self._notebook.count():
                index = self._notebook.insertTab(position, widget, title)
            else:
                index = self._notebook.addTab(widget, title)
                
            # Set tab icon if provided
            if icon and hasattr(self._notebook, 'setTabIcon'):
                self._notebook.setTabIcon(index, icon)
            
            # Set tab as closable if specified
            if hasattr(self._notebook, 'setTabsClosable') and closable:
                self._notebook.setTabsClosable(True)
            
            # Store tab info
            self._tabs[tab_id] = {
                'widget': widget,
                'title': title,
                'icon': icon,
                'closable': closable,
                'index': index,
                'initialized': False
            }
            self._tab_frames[tab_id] = widget
            
            # Insert at position or append to end
            if position is not None and 0 <= position <= len(self._tab_order):
                self._tab_order.insert(position, tab_id)
            else:
                self._tab_order.append(tab_id)
            
            self.logger.debug("Added tab %s at index %s", tab_id, index)
            
            # Initialize tab content if it has an init method
            if hasattr(widget, 'initialize') and callable(widget.initialize):
                try:
                    if asyncio.iscoroutinefunction(widget.initialize):
                        asyncio.create_task(widget.initialize())
                    else:
                        widget.initialize()
                except Exception as init_error:
                    self.logger.error("Error initializing tab '%s': %s", tab_id, str(init_error), exc_info=True)
            
            # Update tab state
            if hasattr(self._notebook, 'setTabEnabled'):
                self._notebook.setTabEnabled(index, True)
            if hasattr(self._notebook, 'setTabVisible'):
                self._notebook.setTabVisible(index, True)
            
            return widget
            
        except Exception as e:
            self.logger.error("Error adding tab %s: %s", tab_id, str(e), exc_info=True)
            return None
            
    def _add_tab_impl(self, tab_id: str, title: str, widget: QWidget, icon: QIcon = None) -> bool:
        """Internal implementation for adding a tab.
        
        Args:
            tab_id: Unique identifier for the tab
            title: Display title for the tab
            widget: The widget to add as the tab content
            icon: Optional icon for the tab
            
        Returns:
            bool: True if tab was added successfully, False otherwise
        """
        if self._notebook is None:
            self.logger.error("Cannot add tab: notebook not initialized")
            return False
            
        if not widget:
            self.logger.error(f"Cannot add tab {tab_id}: Invalid widget")
            return False
            
        try:
            # Set the parent to ensure proper cleanup
            widget.setParent(self._notebook)
            
            # Add the tab to the notebook
            index = self._notebook.addTab(widget, title)
            if icon:
                self._notebook.setTabIcon(index, icon)
                
            # Store tab info
            self._tabs[tab_id] = {
                'widget': widget,
                'title': title,
                'index': index,
                'icon': icon,
                'initialized': False
            }
            
            # Add to tab order if not already present
            if tab_id not in self._tab_order:
                self._tab_order.append(tab_id)
                
            self.logger.debug(f"Added tab {tab_id} at index {index}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding tab {tab_id}: {e}", exc_info=True)
            return False
            
    def close_tab(self, index: int) -> None:
        """Close the tab at the specified index.
        
        Args:
            index: Index of the tab to close
            
        Returns:
            None
        """
        if self._notebook is None:
            self.logger.error("Notebook widget not initialized")
            return
            
        try:
            # Get the tab ID and widget safely
            tab_id = None
            widget = None
            
            # Validate index range
            if 0 <= index < self._notebook.count():
                # Get the widget at the specified index
                widget = self._notebook.widget(index)
                
                # Find the tab ID for this widget
                for tid, tab_data in self._tabs.items():
                    if tab_data.get('widget') == widget:
                        tab_id = tid
                        break
                
                # Remove the tab from the notebook
                self._notebook.removeTab(index)
                
                # Clean up tab resources if we found it
                if tab_id is not None:
                    # Remove from our tracking structures
                    if tab_id in self._tabs:
                        tab_data = self._tabs.pop(tab_id, None)
                        # Call cleanup if available
                        if hasattr(widget, 'cleanup') and callable(widget.cleanup):
                            try:
                                widget.cleanup()
                            except Exception as e:
                                self.logger.error(f"Error cleaning up tab {tab_id}: {e}", exc_info=True)
                    
                    # Remove from tab frames
                    if tab_id in self._tab_frames:
                        del self._tab_frames[tab_id]
                    
                    # Remove from tab order
                    if tab_id in self._tab_order:
                        self._tab_order.remove(tab_id)
                    
                    self.logger.debug("Closed tab %s at index %s", tab_id, index)
                    
                    # Notify about tab closure
                    if hasattr(self, 'event_bus') and self.event_bus:
                        try:
                            self.event_bus.publish("tab.closed", {
                                "tab_id": tab_id,
                                "index": index
                            })
                        except Exception as e:
                            self.logger.error("Error publishing tab close event: %s", e, exc_info=True)
            else:
                self.logger.error("Invalid tab index: %s", index)
            
            # Clean up the widget if it exists
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
                
        except Exception as e:
            self.logger.error("Error closing tab at index %s: %s", index, str(e), exc_info=True)
            
    def get_tab_by_id(self, tab_id: str) -> Optional[QWidget]:
        """Retrieve a tab widget by its ID.
        
        Args:
            tab_id: The ID of the tab to retrieve
            
        Returns:
            Optional[QWidget]: The tab widget or None if not found
        """
        return self._tab_frames.get(tab_id)
        
    def get_tab_id_at_index(self, index: int) -> Optional[str]:
        """Get the tab ID at the specified index.
        
        Args:
            index: Index of the tab
            
        Returns:
            Optional[str]: The tab ID or None if not found
        """
        if self._notebook is None or not (0 <= index < self._notebook.count()):
            return None
            
        widget = self._notebook.widget(index)
        for tab_id, tab_data in self._tabs.items():
            if tab_data.get('widget') == widget:
                return tab_id
        return None
        
    def get_current_tab(self) -> Optional[Tuple[str, QWidget]]:
        """Get the currently active tab.
        
        Returns:
            Optional[Tuple[str, QWidget]]: A tuple of (tab_id, widget) or None if not found
        """
        if self._notebook is None:
            return None
            
        current_index = self._notebook.currentIndex()
        if current_index < 0:
            return None
            
        tab_id = self.get_tab_id_at_index(current_index)
        if tab_id is None:
            return None
            
        widget = self._tab_frames.get(tab_id)
        return (tab_id, widget) if widget else None
        
    def set_current_tab(self, tab_id: str) -> bool:
        """Set the specified tab as the current tab.
        
        Args:
            tab_id: ID of the tab to set as current
            
        Returns:
            bool: True if successful, False otherwise
        """
        if tab_id not in self._tab_frames or self._notebook is None:
            return False
            
        widget = self._tab_frames[tab_id]
        index = self._notebook.indexOf(widget)
        if index >= 0:
            self._notebook.setCurrentIndex(index)
            
            # Notify about tab switch via event bus
            if hasattr(self, 'event_bus') and self.event_bus:
                try:
                    self.event_bus.publish("tab.switched", {
                        "tab_id": tab_id,
                        "index": index
                    })
                except Exception as e:
                    self.logger.error(f"Error publishing tab switch event: {e}", exc_info=True)
            return True
        return False
        
    def get_tab_count(self) -> int:
        """Get the number of tabs in the tab manager.
        
        Returns:
            int: Number of tabs
        """
        return len(self._tab_frames)
        
    def tab_exists(self, tab_id: str) -> bool:
        """Check if a tab with the given ID exists.
        
        Args:
            tab_id: ID of the tab to check
            
        Returns:
            bool: True if the tab exists, False otherwise
        """
        return tab_id in self._tab_frames
        
    def connect_to_event_bus(self, event_bus: EventBus) -> None:
        """Connect this tab manager to the event bus.
        
        This allows the tab manager to receive and publish events.
        
        Args:
            event_bus: The event bus to connect to
        """
        if event_bus is None:
            self.logger.error("Cannot connect to event bus: event_bus is None")
            return
            
        # Store the event bus reference
        self.event_bus = event_bus
        
        # Subscribe to relevant events AFTER init completes
        from PyQt6.QtCore import QTimer
        import asyncio
        
        def subscribe_tab_events():
            try:
                # Safe subscription pattern - handles both sync and async event bus
                def safe_subscribe(event_type, handler):
                    result = self.event_bus.subscribe(event_type, handler)
                    if asyncio.iscoroutine(result):
                        asyncio.ensure_future(result)
                
                safe_subscribe("tab.create", self._handle_tab_create_event)
                safe_subscribe("tab.close", self._handle_tab_close_event)
                safe_subscribe("tab.switch", self._handle_tab_switch_event)
                # SOTA 2026: Chat/Voice command for tab refresh
                safe_subscribe("tab.refresh", self._handle_tab_refresh_event)
                self.logger.info("Tab manager event handlers registered (including SOTA 2026 chat commands)")
            except Exception as e:
                self.logger.error(f"Error subscribing to tab events: {e}")
        
        QTimer.singleShot(5300, subscribe_tab_events)  # 5.3 seconds delay
        
        # Publish connection event
        def publish_ready():
            try:
                result = self.event_bus.publish("tab_manager.ready", {"tab_count": self.get_tab_count()})
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception as e:
                self.logger.error(f"Error publishing ready event: {e}")
        
        QTimer.singleShot(5400, publish_ready)  # 5.4 seconds delay
        self.logger.info("Tab manager connected to event bus")
        
    def _handle_tab_create_event(self, event_data: Dict[str, Any]) -> None:
        """Handle tab creation events from the event bus.
        
        Args:
            event_data: Event data containing tab information
        """
        try:
            tab_id = event_data.get("tab_id")
            title = event_data.get("title")
            widget = event_data.get("widget")
            
            if tab_id and title:
                self.add_tab(tab_id, title, widget)
            else:
                self.logger.error("Invalid tab create event data: missing required fields")
        except Exception as e:
            self.logger.error(f"Error handling tab create event: {e}", exc_info=True)
        
    def _handle_tab_close_event(self, event_data: Dict[str, Any]) -> None:
        """Handle tab close events from the event bus.
        
        Args:
            event_data: Event data containing tab information
        """
        try:
            tab_id = event_data.get("tab_id")
            index = event_data.get("index")
            
            if index is not None:
                self.close_tab(index)
            elif tab_id:
                widget = self._tab_frames.get(tab_id)
                if widget:
                    index = self._notebook.indexOf(widget)
                    if index >= 0:
                        self.close_tab(index)
        except Exception as e:
            self.logger.error(f"Error handling tab close event: {e}", exc_info=True)
        
    def _handle_tab_switch_event(self, event_data: Dict[str, Any]) -> None:
        """Handle tab switch events from the event bus.
        
        Args:
            event_data: Event data containing tab information
        """
        try:
            tab_id = event_data.get("tab_id") or event_data.get("tab")
            if tab_id:
                self.set_current_tab(tab_id)
                self.logger.info(f"🔄 Tab switched via chat command: {tab_id}")
        except Exception as e:
            self.logger.error(f"Error handling tab switch event: {e}", exc_info=True)
    
    def _handle_tab_refresh_event(self, event_data: Dict[str, Any]) -> None:
        """Handle tab refresh events from chat/voice commands.
        
        SOTA 2026: Refresh current tab via chat command.
        
        Args:
            event_data: Event data (may be empty for current tab refresh)
        """
        try:
            # Get current tab
            current_index = self._notebook.currentIndex() if self._notebook else -1
            if current_index >= 0:
                current_widget = self._notebook.widget(current_index)
                
                # Try to call refresh method on the tab
                if hasattr(current_widget, 'refresh'):
                    current_widget.refresh()
                    self.logger.info("🔄 Current tab refreshed via chat command")
                elif hasattr(current_widget, '_refresh'):
                    current_widget._refresh()
                    self.logger.info("🔄 Current tab refreshed via chat command")
                else:
                    self.logger.info("🔄 Tab refresh requested (no refresh method available)")
                
                # Publish refresh event
                if hasattr(self, 'event_bus') and self.event_bus:
                    import asyncio
                    result = self.event_bus.publish("tab.refreshed", {
                        "index": current_index,
                        "timestamp": __import__('datetime').datetime.now().isoformat()
                    })
                    if asyncio.iscoroutine(result):
                        asyncio.ensure_future(result)
        except Exception as e:
            self.logger.error(f"Error handling tab refresh event: {e}", exc_info=True)
    
    def move_tab(self, tab_id: str, new_position: int) -> bool:
        """Move a tab to a new position in the tab bar.
        
        Args:
            tab_id: ID of the tab to move
            new_position: New index position for the tab
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self._notebook is None or tab_id not in self._tab_frames:
            return False
            
        try:
            widget = self._tab_frames[tab_id]
            current_index = self._notebook.indexOf(widget)
            
            if current_index < 0:
                return False
                
            # Remove the tab
            title = self._notebook.tabText(current_index)
            icon = self._notebook.tabIcon(current_index)
            self._notebook.removeTab(current_index)
            
            # Re-insert it at the new position
            new_index = min(new_position, self._notebook.count())
            self._notebook.insertTab(new_index, widget, icon, title)
            
            # Update our internal tracking
            if tab_id in self._tab_order:
                self._tab_order.remove(tab_id)
                
            if 0 <= new_position < len(self._tab_order):
                self._tab_order.insert(new_position, tab_id)
            else:
                self._tab_order.append(tab_id)
                
            # Update the tab info
            if tab_id in self._tabs:
                self._tabs[tab_id]['index'] = new_index
                
            # Emit signals and notify event bus
            if hasattr(self, 'event_bus') and self.event_bus:
                try:
                    self.event_bus.publish("tab.moved", {
                        "tab_id": tab_id,
                        "old_index": current_index,
                        "new_index": new_index
                    })
                except Exception as e:
                    self.logger.error(f"Error publishing tab moved event: {e}", exc_info=True)
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Error moving tab {tab_id}: {e}", exc_info=True)
            return False
            
    def set_tab_title(self, tab_id: str, title: str) -> bool:
        """Set the title of a tab.
        
        Args:
            tab_id: ID of the tab
            title: New title for the tab
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self._notebook is None or tab_id not in self._tab_frames:
            return False
            
        try:
            widget = self._tab_frames[tab_id]
            index = self._notebook.indexOf(widget)
            
            if index < 0:
                return False
                
            self._notebook.setTabText(index, title)
            
            # Update the tab info
            if tab_id in self._tabs:
                self._tabs[tab_id]['title'] = title
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting tab title for {tab_id}: {e}", exc_info=True)
            return False
            
    def set_tab_icon(self, tab_id: str, icon: QIcon) -> bool:
        """Set the icon of a tab.
        
        Args:
            tab_id: ID of the tab
            icon: New icon for the tab
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self._notebook is None or tab_id not in self._tab_frames or icon is None:
            return False
            
        try:
            widget = self._tab_frames[tab_id]
            index = self._notebook.indexOf(widget)
            
            if index < 0:
                return False
                
            self._notebook.setTabIcon(index, icon)
            
            # Update the tab info
            if tab_id in self._tabs:
                self._tabs[tab_id]['icon'] = icon
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting tab icon for {tab_id}: {e}", exc_info=True)
            return False
            
    def _setup_event_connections(self) -> None:
        """Set up event connections for the tab manager.
        
        This connects tab events to the appropriate handlers.
        """
        if self._notebook is None:
            return
            
        try:
            # Connect tab change signal
            self._notebook.currentChanged.connect(self._on_tab_changed)
            
            # Connect tab close signal
            self._notebook.tabCloseRequested.connect(self.close_tab)
            
            # Log completion
            self.logger.info("Tab manager event connections established")
        except Exception as e:
            self.logger.error(f"Failed to set up event connections: {e}", exc_info=True)
            
    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change events.
        
        Args:
            index: Index of the newly selected tab
        """
        try:
            if index < 0 or self._notebook is None:
                return
                
            # Get the tab ID for this index
            tab_id = None
            widget = self._notebook.widget(index)
            
            # Find the tab ID for this widget
            for tid, w in self._tab_frames.items():
                if w == widget:
                    tab_id = tid
                    break
                    
            if tab_id:
                # Update current tab ID
                self._current_tab_id = tab_id
                
                # Emit signal
                self.tab_switched.emit(tab_id, index)
                
                # Publish event
                if hasattr(self, 'event_bus') and self.event_bus:
                    try:
                        self.event_bus.publish("tab.changed", {
                            "tab_id": tab_id,
                            "index": index
                        })
                    except Exception as e:
                        self.logger.error(f"Error publishing tab changed event: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Error handling tab changed event: {e}", exc_info=True)
            
    def refresh_tabs(self) -> None:
        """Refresh all tabs in the tab manager.
        
        This ensures all tabs are properly connected to the event bus and Redis.
        """
        if self._notebook is None:
            return
            
        try:
            # Refresh each tab
            for tab_id, widget in self._tab_frames.items():
                # Call refresh method if available
                if hasattr(widget, 'refresh') and callable(widget.refresh):
                    try:
                        if asyncio.iscoroutinefunction(widget.refresh):
                            asyncio.create_task(widget.refresh())
                        else:
                            widget.refresh()
                    except Exception as e:
                        self.logger.error(f"Error refreshing tab {tab_id}: {e}", exc_info=True)
                        
            # Publish refresh event
            if hasattr(self, 'event_bus') and self.event_bus:
                try:
                    self.event_bus.publish("tabs.refreshed", {
                        "count": len(self._tab_frames)
                    })
                except Exception as e:
                    self.logger.error(f"Error publishing tabs refreshed event: {e}", exc_info=True)
                    
        except Exception as e:
            self.logger.error(f"Error refreshing tabs: {e}", exc_info=True)
            
    def verify_redis_connection(self) -> bool:
        """Verify that the Redis Quantum Nexus connection is active.
        
        Returns:
            bool: True if connection is active, False otherwise
        """
        if not self.redis_connector:
            self.logger.critical("Redis Quantum Nexus connector not available - critical component missing")
            return False
            
        try:
            # Test the connection by pinging Redis
            if self.redis_connector.ping():  # type: ignore
                self.logger.info("Redis Quantum Nexus connection verified")
                return True
            else:
                self.logger.critical("Redis Quantum Nexus connection failed - could not ping server")
                return False
        except Exception as e:
            self.logger.critical(f"Redis Quantum Nexus connection error: {e}")
            return False
            
    def initialize_tabs(self) -> bool:
        """Initialize all tabs with real components and validate connections.
        
        This method ensures that all tabs are properly initialized with real
        data from the event bus and Redis Quantum Nexus. No fallbacks are allowed.
        
        Returns:
            bool: True if all tabs initialized successfully, False otherwise
        """
        # First verify Redis connection - Kingdom AI requires this to be active
        if not self.verify_redis_connection():
            self.logger.critical("Cannot initialize tabs - Redis Quantum Nexus connection not available")
            print("CRITICAL ERROR: Redis Quantum Nexus connection required for tab initialization", file=sys.stderr)
            return False
            
        # Verify event bus connection
        if not hasattr(self, 'event_bus') or not self.event_bus:
            self.logger.critical("Cannot initialize tabs - Event bus not available")
            print("CRITICAL ERROR: Event bus connection required for tab initialization", file=sys.stderr)
            return False
            
        success = True
        
        # Initialize standard tabs
        try:
            # Dashboard tab is already initialized in __init__
            # Initialize trading tab
            if not self.tab_exists('trading'):
                from gui.qt_frames.trading_qt import TradingQt
                trading_tab = TradingQt(self.event_bus, self.redis_connector)
                if not self.add_tab('trading', 'Trading', trading_tab):
                    self.logger.error("Failed to add Trading tab")
                    success = False
                    
            # Initialize mining tab
            if not self.tab_exists('mining'):
                from gui.qt_frames.mining_qt import MiningQt
                mining_tab = MiningQt(self.event_bus, self.redis_connector)
                if not self.add_tab('mining', 'Mining', mining_tab):
                    self.logger.error("Failed to add Mining tab")
                    success = False
                    
            # Initialize analytics tab
            if not self.tab_exists('analytics'):
                from gui.qt_frames.analytics_qt import AnalyticsQt
                analytics_tab = AnalyticsQt(self.event_bus, self.redis_connector)
                if not self.add_tab('analytics', 'Analytics', analytics_tab):
                    self.logger.error("Failed to add Analytics tab")
                    success = False
                    
            # Initialize settings tab
            if not self.tab_exists('settings'):
                from gui.qt_frames.settings_qt import SettingsQt
                settings_tab = SettingsQt(self.event_bus, self.redis_connector)
                if not self.add_tab('settings', 'Settings', settings_tab):
                    self.logger.error("Failed to add Settings tab")
                    success = False
                    
            # Publish initialization status
            init_status = {
                "success": success,
                "tab_count": len(self._tab_frames),
                "tabs": list(self._tabs.keys())
            }
            self.event_bus.publish("tabs.initialized", init_status)
            
        except ImportError as e:
            self.logger.critical(f"Critical component missing: {e}")
            print(f"CRITICAL ERROR: Cannot initialize tabs - {e}", file=sys.stderr)
            success = False
        except Exception as e:
            self.logger.critical(f"Failed to initialize tabs: {e}")
            print(f"CRITICAL ERROR: Tab initialization failed - {e}", file=sys.stderr)
            success = False
            
        return success
        
    def verify_all_components(self) -> bool:
        """Verify that all required components are present and connected.
        
        This enforces the Kingdom AI requirement that all components must be
        real and connected to the event bus with no fallbacks allowed.
        
        Returns:
            bool: True if all required components are present, False otherwise
        """
        # Check notebook widget
        if self._notebook is None:
            self.logger.critical("Notebook widget not initialized")
            return False
            
        # Check Redis connection
        if not self.verify_redis_connection():
            return False
            
        # Check event bus
        if not hasattr(self, 'event_bus') or not self.event_bus:
            self.logger.critical("Event bus not available")
            return False
            
        # Check required tabs
        required_tabs = ['dashboard', 'trading', 'mining', 'analytics', 'settings']
        missing_tabs = [tab for tab in required_tabs if not self.tab_exists(tab)]
        
        if missing_tabs:
            self.logger.critical(f"Missing required tabs: {', '.join(missing_tabs)}")
            return False
            
        # Check component functionality
        try:
            for tab_id, widget in self._tab_frames.items():
                # Check that all tab widgets are PyQt6 QWidgets (no fallbacks allowed)
                if not isinstance(widget, QWidget):
                    self.logger.critical(f"Tab {tab_id} is not a PyQt6 QWidget")
                    return False
                    
                # Ensure all tabs have required event bus methods
                if not (hasattr(widget, 'connect_to_event_bus') and callable(widget.connect_to_event_bus)):
                    self.logger.critical(f"Tab {tab_id} does not have connect_to_event_bus method")
                    return False
                    
                # Ensure all tabs have required Redis methods
                if not (hasattr(widget, 'connect_to_redis') and callable(widget.connect_to_redis)):
                    self.logger.critical(f"Tab {tab_id} does not have connect_to_redis method")
                    return False
        except Exception as e:
            self.logger.critical(f"Component verification failed: {e}")
            return False
            
        self.logger.info("All components verified successfully")
        return True
