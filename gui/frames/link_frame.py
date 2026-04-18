from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Link Frame Module

Provides a state-of-the-art connection interface between Kingdom AI services.
Implements MVVM pattern, multithreading, and real-time data visualization.
"""

import logging
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Optional, Any, Dict, List, Union, Callable, Tuple

# Configure logger with proper naming to match other modules
logger = logging.getLogger(__name__)

# Add parent directories to path if needed
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Define flags to track PyQt6 module availability - MUST BE AT MODULE LEVEL
# Only define these flags once to avoid "is constant and cannot be redefined" errors
try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QFrame
    from PyQt6.QtWidgets import QScrollArea, QGridLayout, QSizePolicy
    # Import the original BaseFrame
    from .base_frame_pyqt import BaseFrame as BaseFrameOriginal
    BaseFrame = BaseFrameOriginal  # Use the original base frame as our base
    PYQT_AVAILABLE = True
except ImportError:
    # If PyQt6 is not available, we'll use the fallback BaseFrame
    from .base_frame import BaseFrame  # This is already the fallback BaseFrame
    PYQT_AVAILABLE = False

# Import PyQt6 with proper error handling
if PYQT_AVAILABLE:
    try:
        from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal, pyqtSlot
    except ImportError:
        logger.warning("Additional PyQt6 modules not available - some functionality may be limited")
    from .base_frame_pyqt import BaseFrame  # This is already the fallback BaseFrame

    # Import PyQt6 with proper error handling
    try:
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
            QLabel, QPushButton, QFrame, QGroupBox, QSplitter,
            QScrollArea, QTabWidget, QProgressBar, QSpacerItem,
            QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
            QComboBox, QStackedWidget, QApplication, QRadioButton
        )
        from PyQt6.QtCore import (
            Qt, pyqtSignal, pyqtSlot, QObject, QThread, 
            QMetaObject, QTimer, QSize, QRect, QPoint, Q_ARG
        )
        from PyQt6.QtGui import (
            QColor, QPalette, QFont, QIcon, QPixmap, 
            QLinearGradient, QBrush, QPainter, QPen, QFontMetrics
        )
        
        # Data Visualization module - only try to import if PyQt6 is available
        DATA_VIZ_AVAILABLE = False
        try:
            from gui.utils.qt_data_visualization import QtDataVisualization
            DATA_VIZ_AVAILABLE = True
            logger.info("PyQt6 Data Visualization loaded successfully")
        except ImportError:
            logger.info("PyQt6 Data Visualization not available - advanced visualizations disabled")

        # Qt Charts module - only try to import if PyQt6 is available
        CHARTS_AVAILABLE = False
        try:
            from gui.utils.qt_charts import QtCharts
            CHARTS_AVAILABLE = True
            logger.info("PyQt6 Charts loaded successfully")
        except ImportError:
            logger.info("PyQt6 Charts not available - advanced charts disabled")
            logger.info("QtCharts not available, using minimal chart implementation")
    except ImportError as e:
        logger.error(f"Failed to import PyQt6: {e}")
    # Don't redefine constants - they are already defined at module level


# ===============================================================
# ===============================================================
# MVVM Architecture Implementation
# ===============================================================

# Model: Handles data and business logic
class ConnectionModel(QObject if PYQT_AVAILABLE else object):
    """Model for managing connection data and states in the MVVM pattern."""
    
    # Signals for connection status changes
    status_changed = pyqtSignal(str, str)
    all_status_changed = pyqtSignal(dict)
    connection_error = pyqtSignal(str, str)
    connection_metrics_updated = pyqtSignal(str, dict)
    
    def __init__(self):
        """Initialize the connection model."""
        super().__init__()
        # Core services that Kingdom AI depends on
        self._services = {
            "Event Bus": {
                "status": "Disconnected",
                "color": "#FF5555",  # Red
                "last_updated": None,
                "metrics": {},
                "history": [],
                "priority": 1  # Highest priority
            },
            "Core Services": {
                "status": "Disconnected",
                "color": "#FF5555",
                "last_updated": None,
                "metrics": {},
                "history": [],
                "priority": 2
            },
            "AI System": {
                "status": "Disconnected",
                "color": "#FF5555",
                "last_updated": None,
                "metrics": {},
                "history": [],
                "priority": 3
            },
            "Blockchain": {
                "status": "Disconnected",
                "color": "#FF5555",
                "last_updated": None,
                "metrics": {},
                "history": [],
                "priority": 4
            },
            "Database": {
                "status": "Disconnected",
                "color": "#FF5555",
                "last_updated": None,
                "metrics": {},
                "history": [],
                "priority": 5
            }
        }
        self._connection_active = False
        self._last_refresh = None
    
    @property
    def services(self):
        """Get all services."""
        return self._services
    
    def update_service_status(self, service_name: str, status: str):
        """Update the status of a specific service.
        
        Args:
            service_name: Name of the service
            status: New status value
        """
        if service_name not in self._services:
            logger.warning(f"Attempted to update unknown service: {service_name}")
            return False
            
        # Update status
        self._services[service_name]["status"] = status
        
        # Update color based on status
        if status == "Connected":
            self._services[service_name]["color"] = "#55FF55"  # Green
        elif status == "Connecting":
            self._services[service_name]["color"] = "#FFCC44"  # Yellow
        elif status == "Error":
            self._services[service_name]["color"] = "#FF8888"  # Light red
        else:
            self._services[service_name]["color"] = "#FF5555"  # Red
            
        # Update timestamp
        self._services[service_name]["last_updated"] = datetime.now()
        
        # Add to history (keep last 100 entries)
        history_entry = {
            "timestamp": datetime.now(),
            "status": status
        }
        self._services[service_name]["history"].append(history_entry)
        if len(self._services[service_name]["history"]) > 100:
            self._services[service_name]["history"].pop(0)
        
        # Emit signal for this service
        self.status_changed.emit(service_name, status)
        
        # Notify all listeners that service statuses have been updated
        self.all_status_changed.emit(self._services)
        
        return True
    
    def update_service_metrics(self, service_name: str, metrics: dict):
        """Update service performance metrics.
        
        Args:
            service_name: Name of the service
            metrics: Dictionary of metrics
        """
        if service_name not in self._services:
            logger.warning(f"Attempted to update metrics for unknown service: {service_name}")
            return False
            
        self._services[service_name]["metrics"] = metrics
        self.connection_metrics_updated.emit(service_name, metrics)
        return True
    
    def connect_service(self, service_name: str):
        """Connect to a specific service.
        
        Args:
            service_name: Name of the service to connect
        """
        if service_name not in self._services:
            logger.warning(f"Attempted to connect unknown service: {service_name}")
            return False
            
        # Update to connecting state
        self.update_service_status(service_name, "Connecting")
        return True
    
    def connect_all_services(self):
        """Connect to all services."""
        for service_name in self._services:
            self.connect_service(service_name)
        self._connection_active = True
        self._last_refresh = datetime.now()
        return True
    
    def disconnect_service(self, service_name: str):
        """Disconnect from a specific service.
        
        Args:
            service_name: Name of the service to disconnect
        """
        if service_name not in self._services:
            logger.warning(f"Attempted to disconnect unknown service: {service_name}")
            return False
            
        # Update to disconnected state
        self.update_service_status(service_name, "Disconnected")
        return True
    
    def disconnect_all_services(self):
        """Disconnect from all services."""
        for service_name in self._services:
            self.disconnect_service(service_name)
        self._connection_active = False
        return True
    
    def refresh_service_status(self, service_name: str):
        """Refresh the status of a specific service.
        
        Args:
            service_name: Name of the service to refresh
        """
        if service_name not in self._services:
            logger.warning(f"Attempted to refresh unknown service: {service_name}")
            return False
            
        # Current status becomes pending briefly
        current_status = self._services[service_name]["status"]
        self.update_service_status(service_name, "Refreshing")
        
        # In a real implementation, this would trigger an actual refresh
        # For now, we'll just simulate it by going back to the previous status
        # after a delay (this would be handled by event bus in practice)
        return True
    
    def refresh_all_services(self):
        """Refresh the status of all services."""
        for service_name in self._services:
            self.refresh_service_status(service_name)
        self._last_refresh = datetime.now()
        return True


# ViewModel: Connects the Model to the View
class ConnectionViewModel(QObject if PYQT_AVAILABLE else object):
    """ViewModel for the MVVM pattern to connect the model with the view."""
    
    # Signals for communicating with the view
    view_update_required = pyqtSignal()
    service_status_update = pyqtSignal(str, str, str)  # service, status, color
    connection_progress = pyqtSignal(int)  # 0-100%
    connection_complete = pyqtSignal(bool)  # success/failure
    
    def __init__(self, model=None, event_bus=None):
        """Initialize the connection ViewModel.
        
        Args:
            model: The ConnectionModel instance
            event_bus: The event bus for system-wide communication
        """
        super().__init__()
        self._model = model or ConnectionModel()
        self._event_bus = event_bus
        
        # Connect model signals to handle state changes
        self._model.status_changed.connect(self._handle_status_change)
        self._model.all_status_changed.connect(self._handle_all_status_change)
        self._model.connection_metrics_updated.connect(self._handle_metrics_update)
        
        # Create timer for simulating async operations when no event bus is available
        # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
        self._timer_manager = get_qt_timer_manager()
        self._timer.timeout.connect(self._simulate_connection_progress)
        self._current_operation = None
        self._progress = 0
    
    def connect_to_event_bus(self, event_bus):
        """Connect to the application's event bus.
        
        Args:
            event_bus: Event bus instance for system communication
        """
        if not event_bus:
            logger.warning("No event bus provided to ConnectionViewModel")
            return False
            
        self._event_bus = event_bus
        
        # Subscribe to relevant event bus events
        if hasattr(event_bus, 'subscribe'):
            try:
                event_bus.subscribe("connection.status.update", self._on_connection_status_event)
                event_bus.subscribe("connection.metrics.update", self._on_connection_metrics_event)
                logger.info("ConnectionViewModel connected to event bus successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to subscribe to event bus: {e}")
                return False
        else:
            logger.warning("Event bus does not have a subscribe method")
            return False
    
    @property
    def services(self):
        """Get all services from the model."""
        return self._model.services
    
    def connect_service(self, service_name):
        """Connect to a specific service and notify the system.
        
        Args:
            service_name: Name of the service to connect
        """
        logger.info(f"Attempting to connect to {service_name}")
        
        # Use model to update local state
        result = self._model.connect_service(service_name)
        if not result:
            return False
        
        # Publish event to the event bus if available
        if self._event_bus and hasattr(self._event_bus, 'publish'):
            try:
                self._event_bus.publish("connection.request", {
                    "action": "connect",
                    "service": service_name
                })
            except Exception as e:
                logger.error(f"Error publishing connection request to event bus: {e}")
        else:
            # If no event bus, simulate the connection process
            self._current_operation = ("connect", service_name)
            self._progress = 0
            self._timer.start(100)  # Update every 100ms
        
        return True
    
    def connect_all(self):
        """Connect to all services."""
        logger.info("Attempting to connect to all services")
        
        # Use model to update local state
        result = self._model.connect_all_services()
        if not result:
            return False
            
        # Publish event to the event bus if available
        if self._event_bus and hasattr(self._event_bus, 'publish'):
            try:
                self._event_bus.publish("connection.request", {
                    "action": "connect_all"
                })
            except Exception as e:
                logger.error(f"Error publishing connection request to event bus: {e}")
        else:
            # If no event bus, simulate the connection process
            self._current_operation = ("connect_all", None)
            self._progress = 0
            self._timer.start(100)  # Update every 100ms
        
        return True
    
    def disconnect_service(self, service_name):
        """Disconnect from a specific service and notify the system.
        
        Args:
            service_name: Name of the service to disconnect
        """
        logger.info(f"Attempting to disconnect from {service_name}")
        
        # Use model to update local state
        result = self._model.disconnect_service(service_name)
        if not result:
            return False
            
        # Publish event to the event bus if available
        if self._event_bus and hasattr(self._event_bus, 'publish'):
            try:
                self._event_bus.publish("connection.request", {
                    "action": "disconnect",
                    "service": service_name
                })
            except Exception as e:
                logger.error(f"Error publishing disconnect request to event bus: {e}")
        
        return True
    
    def disconnect_all(self):
        """Disconnect from all services."""
        logger.info("Attempting to disconnect from all services")
        
        # Use model to update local state
        result = self._model.disconnect_all_services()
        if not result:
            return False
            
        # Publish event to the event bus if available
        if self._event_bus and hasattr(self._event_bus, 'publish'):
            try:
                self._event_bus.publish("connection.request", {
                    "action": "disconnect_all"
                })
            except Exception as e:
                logger.error(f"Error publishing disconnect request to event bus: {e}")
        
        return True
    
    def refresh_status(self, service_name=None):
        """Refresh the status of services.
        
        Args:
            service_name: Name of specific service to refresh, or None for all
        """
        if service_name:
            logger.info(f"Refreshing status of {service_name}")
            result = self._model.refresh_service_status(service_name)
        else:
            logger.info("Refreshing status of all services")
            result = self._model.refresh_all_services()
            
        if not result:
            return False
            
        # Publish event to the event bus if available
        if self._event_bus and hasattr(self._event_bus, 'publish'):
            try:
                payload = {"action": "refresh_status"}
                if service_name:
                    payload["service"] = service_name
                self._event_bus.publish("connection.request", payload)
            except Exception as e:
                logger.error(f"Error publishing refresh request to event bus: {e}")
        else:
            # If no event bus, simulate the refresh process
            self._current_operation = ("refresh", service_name)
            self._progress = 0
            self._timer.start(50)  # Update faster for refresh
        
        return True
    
    def _handle_status_change(self, service_name, status):
        """Handle status changes from the model.
        
        Args:
            service_name: Name of the service
            status: New status value
        """
        service_data = self._model.services.get(service_name, {})
        color = service_data.get("color", "#FF5555")
        self.service_status_update.emit(service_name, status, color)
        self.view_update_required.emit()
    
    def _handle_all_status_change(self, services):
        """Handle updates to all services.
        
        Args:
            services: Dictionary of all service data
        """
        # This could be used to batch-update the UI when many services change at once
        self.view_update_required.emit()
    
    def _handle_metrics_update(self, service_name, metrics):
        """Handle metrics updates from the model.
        
        Args:
            service_name: Name of the service
            metrics: New metrics data
        """
        try:
            if not isinstance(metrics, dict):
                return

            service_data = self._model.services.get(service_name, {})
            service_data["metrics"] = metrics
            service_data["last_metrics_update"] = time.time()

            latency = metrics.get("latency_ms", metrics.get("latency"))
            uptime = metrics.get("uptime_pct", metrics.get("uptime"))

            logger.debug(
                "Metrics update for %s: latency=%s, uptime=%s",
                service_name, latency, uptime
            )

            self.view_update_required.emit()
        except Exception as e:
            logger.error("Error handling metrics update for %s: %s", service_name, e)
    
    def _on_connection_status_event(self, data):
        """Handle connection status events from the event bus.
        
        Args:
            data: Event data containing service and status information
        """
        if not isinstance(data, dict):
            logger.warning(f"Received invalid connection status data: {data}")
            return
            
        service = data.get("service")
        status = data.get("status")
        
        if service and status:
            self._model.update_service_status(service, status)
    
    def _on_connection_metrics_event(self, data):
        """Handle connection metrics events from the event bus.
        
        Args:
            data: Event data containing service and metrics information
        """
        if not isinstance(data, dict):
            logger.warning(f"Received invalid metrics data: {data}")
            return
            
        service = data.get("service")
        metrics = data.get("metrics")
        
        if service and metrics and isinstance(metrics, dict):
            self._model.update_service_metrics(service, metrics)
    
    def _simulate_connection_progress(self):
        """Simulate connection progress when no event bus is available."""
        if not self._current_operation:
            self._timer.stop()
            return
            
        operation_type, service_name = self._current_operation
        
        # Update progress
        self._progress += 5
        self.connection_progress.emit(self._progress)
        
        if self._progress >= 100:
            self._timer.stop()
            
            # Complete the simulated operation
            if operation_type == "connect" or operation_type == "connect_all":
                if operation_type == "connect" and service_name:
                    self._model.update_service_status(service_name, "Connected")
                else:
                    # Connect all services with slight delays between them
                    for i, svc in enumerate(self._model.services.keys()):
                        # Simulate that some services connect faster than others
                        delay = i * 0.5
                        QTimer.singleShot(int(delay * 1000), lambda s=svc: 
                                        self._model.update_service_status(s, "Connected"))
            
            elif operation_type == "refresh":
                # For refresh operations, simulate getting real status updates
                services = list(self._model.services.keys())
                statuses = ["Connected", "Connected", "Connected", "Error", "Disconnected"]
                
                if service_name:
                    # Update the requested service with deterministic status based on service name hash
                    service_hash = hash(service_name) % len(statuses)
                    status = statuses[service_hash]
                    self._model.update_service_status(service_name, status)
                else:
                    # Update all services with deterministic statuses based on service name hash
                    for svc in services:
                        service_hash = hash(svc) % len(statuses)
                        status = statuses[service_hash]
                        # Deterministic delay based on service hash (0-1 seconds)
                        delay = (service_hash % 100) / 100.0
                        QTimer.singleShot(int(delay * 1000), lambda s=svc, st=status: 
                                        self._model.update_service_status(s, st))
            
            self._current_operation = None
            self.connection_complete.emit(True)


# Define LinkFrame class based on availability of PyQt6
if PYQT_AVAILABLE:
    class LinkFrame(BaseFrame):
        """Link Frame for connecting Kingdom AI components and services.
        
        This is a PyQt6-based implementation that matches the functionality of the
        original Tkinter implementation but is compatible with the main PyQt6 GUI.
        Note: BaseFrame already inherits from QFrame (a QWidget), so we only inherit from BaseFrame.
        """
        
        def __init__(self, parent=None, event_bus=None):
            """Initialize the Link Frame.
            
            Args:
                parent: Parent widget
                event_bus: Event bus for communication
            """
            # Initialize BaseFrame (which handles QFrame initialization)
            BaseFrame.__init__(self, parent, event_bus=event_bus)
            
            # Set frame name for component registration
            self.name = "link_frame"
            self.frame = self  # For compatibility with older code
            
            # Set up internal data structures
            self.connection_widgets = {}
            
            # Initialize UI
            self._setup_ui()
            self._connect_events()
            logger.info("LinkFrame initialized successfully with PyQt6")
            
        def setLayout(self, layout):
            """Override to properly set layout with QWidget method."""
            QWidget.setLayout(self, layout)
            
        def _setup_ui(self):
            """Set up the UI components for the PyQt6 implementation."""
            # Create main layout
            main_layout = QVBoxLayout()
            
            # Create status section
            status_layout = QGridLayout()
            main_layout.addLayout(status_layout)
            
            # Set the layout
            self.setLayout(main_layout)
            
        def _connect_events(self):
            """Connect to event bus and set up signal handling."""
            if self.event_bus:
                # Subscribe to events
                self.event_bus.subscribe("connection_status_update", self._handle_connection_status)
                
                # Additional event subscriptions can be added here
                logger.debug("LinkFrame connected to event bus")
            
            # Any additional PyQt6 signal connections go here
            
        def _handle_connection_status(self, data):
            """Handle connection status updates from the event bus."""
            if not isinstance(data, dict):
                logger.warning(f"Invalid connection status data: {data}")
                return
                
            # Process connection status update
            service_name = data.get('service')
            status = data.get('status')
            message = data.get('message', '')
            
            if service_name and status:
                logger.debug(f"Connection status update for {service_name}: {status}")
                # Update UI based on connection status
                # Implementation depends on specific UI components
            
            # Emit signals if needed for thread-safe UI updates
            
        def connect_all(self):
            """Attempt to connect all services."""
            if not PYQT_AVAILABLE or not self.event_bus:
                logger.error("Cannot connect services - PyQt6 or event_bus not available")
                return
                
            try:
                # Publish an event to request connections
                logger.info("Requesting connection of all services")
                self.event_bus.publish("connection.request", {"action": "connect_all"})
                
                # Update UI to show pending state
                for service, data in self.connections.items():
                    # Set to pending color (yellow)
                    pending_color = "#FFCC44"
                    
                    # Update widgets
                    if service in self.connection_widgets:
                        widgets = self.connection_widgets[service]
                        widgets["status_label"].setText("Connecting...")
                        widgets["status_label"].setStyleSheet(f"color: {pending_color};")
                        widgets["indicator"].setStyleSheet(f"background-color: {pending_color}; border: 1px solid #888888;")
            
            except Exception as e:
                logger.error(f"Failed to request connections: {e}")
        
        def disconnect_all(self):
            """Disconnect all services."""
            if not PYQT_AVAILABLE or not self.event_bus:
                logger.error("Cannot disconnect services - PyQt6 or event_bus not available")
                return
                
            try:
                # Publish an event to request disconnections
                logger.info("Requesting disconnection of all services")
                self.event_bus.publish("connection.request", {"action": "disconnect_all"})
                
                # Update UI immediately to show disconnected state
                for service, data in self.connections.items():
                    # Set to disconnected color (red)
                    disconnected_color = "#FF5555"
                    
                    # Update widgets
                    if service in self.connection_widgets:
                        widgets = self.connection_widgets[service]
                        widgets["status_label"].setText("Disconnected")
                        widgets["status_label"].setStyleSheet(f"color: {disconnected_color};")
                        widgets["indicator"].setStyleSheet(f"background-color: {disconnected_color}; border: 1px solid #888888;")
                
                    # Update data structure
                    self.connections[service]["status"] = "Disconnected"
                    self.connections[service]["color"] = disconnected_color
            
            except Exception as e:
                logger.error(f"Failed to request disconnections: {e}")
        
        def refresh_status(self):
            """Refresh the connection status of all services."""
            if not PYQT_AVAILABLE or not self.event_bus:
                logger.error("Cannot refresh status - PyQt6 or event_bus not available")
                return
                
            try:
                # Publish an event to request status refresh
                logger.info("Requesting refresh of all services' status")
                self.event_bus.publish("connection.request", {"action": "refresh_status"})
            
            except Exception as e:
                logger.error(f"Failed to request status refresh: {e}")
            
else:
    # Fallback implementation when PyQt6 is not available
    class LinkFrame(BaseFrame):
        """Link Frame for connecting Kingdom AI components and services.
        
        Fallback implementation when PyQt6 is not available.
        """
        
        def __init__(self, parent=None, event_bus=None):
            """Initialize the Link Frame.
            
            Args:
                parent: Parent widget
                event_bus: Event bus for communication
            """
            # Initialize BaseFrame
            super().__init__(parent, event_bus=event_bus)
            
            # Set frame name for component registration
            self.name = "link_frame"
            self.frame = self  # For compatibility with older code
            self.connection_widgets = {}
            
            # Define the connections we want to track
            self.connections = {
                "Event Bus": {"status": "Disconnected", "color": "#FF5555"},
                "Core Services": {"status": "Disconnected", "color": "#FF5555"},
                "AI System": {"status": "Disconnected", "color": "#FF5555"},
                "Blockchain": {"status": "Disconnected", "color": "#FF5555"},
                "Database": {"status": "Disconnected", "color": "#FF5555"}
            }
            
            # Initialize UI (will be minimal)
            self._setup_ui()
            self._connect_events()
            logger.warning("LinkFrame initialized in fallback mode (no PyQt6)")
            
        def setLayout(self, layout):
            """Stub method when PyQt6 is not available."""
            logger.warning("setLayout called but PyQt6 is not available")
            self.layout = layout
            
        def _setup_ui(self):
            """Set up minimal UI for fallback implementation."""
            logger.info("Setting up fallback UI for LinkFrame")
            try:
                # Main layout - simplified for fallback mode
                logger.info("Creating minimal fallback UI elements")
                
                # In fallback mode, we won't actually create real UI elements
                # We'll just set up the data structures needed for status tracking
                
            except Exception as e:
                logger.error(f"Failed to setup LinkFrame UI: {e}")
                logger.error(traceback.format_exc())
        
        def _connect_events(self):
            """Connect to event bus in fallback implementation."""
            if self.event_bus:
                try:
                    # Subscribe to necessary events
                    self.event_bus.subscribe("connection_status_update", self._handle_connection_status)
                    logger.debug("LinkFrame (fallback) connected to event bus")
                except Exception as e:
                    logger.error(f"Failed to connect LinkFrame events: {e}")
        
        def _handle_connection_status(self, data):
            """Handle connection status updates.
            
            Args:
                data (dict): Connection status data with service and status information
            """
            logger.debug(f"Received connection status update: {data}")
            try:
                service = data.get('service')
                status = data.get('status')
                
                if not service:
                    logger.warning("Received connection status update with no service name")
                    return
                
                # Update our tracking structure if service exists
                if service in self.connections:
                    self.connections[service]["status"] = status
                    self.connections[service]["color"] = "#55FF55" if status == "Connected" else "#FF5555"  # Green if connected, red otherwise
                    logger.info(f"Updated connection status for {service}: {status}")
                else:
                    logger.warning(f"Unknown service in connection status update: {service}")
            except Exception as e:
                logger.error(f"Error handling connection status update: {e}")
                logger.error(traceback.format_exc())
                
        def connect_all(self):
            """Attempt to connect all services."""
            logger.info("Attempting to connect all services")
            try:
                if self.event_bus:
                    self.event_bus.publish("connection.request", {"command": "connect_all"})
                    logger.info("Sent connect_all request to event bus")
            except Exception as e:
                logger.error(f"Failed to connect all services: {e}")
                
        def disconnect_all(self):
            """Disconnect all services."""
            logger.info("Attempting to disconnect all services")
            try:
                if self.event_bus:
                    self.event_bus.publish("connection.request", {"command": "disconnect_all"})
                    logger.info("Sent disconnect_all request to event bus")
            except Exception as e:
                logger.error(f"Failed to disconnect all services: {e}")
                
        def refresh_status(self):
            """Refresh the connection status of all services."""
            logger.info("Refreshing connection status")
            try:
                if self.event_bus:
                    self.event_bus.publish("connection.request", {"command": "refresh_status"})
                    logger.info("Sent refresh_status request to event bus")
            except Exception as e:
                logger.error(f"Failed to refresh connection status: {e}")
# End of the file
