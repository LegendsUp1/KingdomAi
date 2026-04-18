"""
Base tab class for Kingdom AI system tabs.

This module provides a base class for all tab components that enforces
strict Redis connection requirements and provides consistent event handling.
"""

import logging
from typing import Any, Dict, Optional, Type, TypeVar, Callable
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMessageBox
from PyQt6.QtCore import Qt, QTimer, QCoreApplication, QMetaObject, QGenericReturnArgument
from PyQt6.QtGui import QIcon, QColor

from core.event_handlers import BaseEventHandler, EventHandlerError, RedisConnectionError
from core.redis_connector import RedisQuantumNexusConnector

T = TypeVar('T', bound='BaseTab')

class BaseTab(QWidget):
    """
    Base class for all tab components in the Kingdom AI system.
    
    This class provides:
    - Strict Redis connection management
    - Event handling infrastructure
    - Thread-safe UI updates
    - Status reporting
    - Error handling
    """
    
    # Signals
    status_update = pyqtSignal(str, str)  # message, level
    data_updated = pyqtSignal(str, object)  # data_type, data
    connection_state_changed = pyqtSignal(bool)  # connected
    
    def __init__(self, 
                 tab_name: str,
                 event_handler_class: Type[BaseEventHandler],
                 parent: Optional[QWidget] = None):
        """Initialize the base tab.
        
        Args:
            tab_name: Name of the tab (used for logging and identification)
            event_handler_class: Class that implements BaseEventHandler
            parent: Parent widget
        """
        super().__init__(parent)
        self.tab_name = tab_name
        self.logger = logging.getLogger(f"kingdom_ai.tabs.{tab_name}")
        
        # Initialize UI
        self._init_ui()
        
        # Initialize event handler
        try:
            self.event_handler = event_handler_class(f"{tab_name}_handler")
            self._connect_event_handler()
            self.logger.info(f"Initialized {tab_name} tab with {event_handler_class.__name__}")
        except Exception as e:
            self._handle_init_error(f"Failed to initialize {tab_name} tab: {e}")
    
    def _init_ui(self) -> None:
        """Initialize the user interface."""
        self.setObjectName(f"{self.tab_name}_tab")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        # Add a status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; color: #666;")
        self.layout.addWidget(self.status_label)
        
        # Add a stretch to push content to the top
        self.layout.addStretch()
    
    def _connect_event_handler(self) -> None:
        """Connect event handler signals to slots."""
        if not hasattr(self, 'event_handler'):
            return
            
        # Connect status updates
        self.event_handler.status_update.connect(self._handle_status_update)
        self.event_handler.data_updated.connect(self._handle_data_updated)
        self.event_handler.connection_state_changed.connect(self._handle_connection_state_changed)
        
        # Initial connection state
        self._handle_connection_state_changed(
            hasattr(self.event_handler, '_connected') and self.event_handler._connected
        )
    
    def _handle_init_error(self, error_message: str) -> None:
        """Handle initialization errors."""
        self.logger.critical(error_message)
        
        # Update UI to show error
        self.status_label.setText("Initialization Error")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Show error message box
        QMessageBox.critical(
            self,
            "Initialization Error",
            f"Failed to initialize {self.tab_name} tab.\n\n{error_message}\n\n"
            "The application will now exit.",
            QMessageBox.StandardButton.Ok
        )
        
        # Schedule application exit
        QTimer.singleShot(0, self._force_quit)
    
    def _force_quit(self) -> None:
        """Force the application to quit."""
        QCoreApplication.quit()
    
    @pyqtSlot(str, str)
    def _handle_status_update(self, message: str, level: str = "info") -> None:
        """Handle status updates from the event handler."""
        try:
            # Map level to color
            colors = {
                "info": "#007bff",    # Blue
                "success": "#28a745", # Green
                "warning": "#ffc107",  # Yellow
                "error": "#dc3545"     # Red
            }
            
            color = colors.get(level.lower(), "#666")
            
            # Update status label
            self.status_label.setText(message)
            self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            
            # Log the message
            log_level = getattr(logging, level.upper(), logging.INFO)
            self.logger.log(log_level, message)
            
        except Exception as e:
            self.logger.error(f"Error in status update handler: {e}")
    
    @pyqtSlot(str, object)
    def _handle_data_updated(self, data_type: str, data: Any) -> None:
        """Handle data updates from the event handler."""
        try:
            # This method should be overridden by subclasses to handle specific data types
            handler_name = f"_on_{data_type}_updated"
            if hasattr(self, handler_name):
                getattr(self, handler_name)(data)
            else:
                self.logger.debug(f"No handler for data type: {data_type}")
        except Exception as e:
            self.logger.error(f"Error handling data update ({data_type}): {e}")
    
    @pyqtSlot(bool)
    def _handle_connection_state_changed(self, connected: bool) -> None:
        """Handle connection state changes."""
        try:
            if connected:
                self.status_label.setText(f"{self.tab_name.capitalize()} Connected")
                self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
                self.on_connected()
            else:
                self.status_label.setText(f"{self.tab_name.capitalize()} Disconnected")
                self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
                self.on_disconnected()
        except Exception as e:
            self.logger.error(f"Error handling connection state change: {e}")
    
    def on_connected(self) -> None:
        """Called when the tab's connection is established."""
        pass
    
    def on_disconnected(self) -> None:
        """Called when the tab's connection is lost."""
        pass
    
    def showEvent(self, event) -> None:
        """Handle show events."""
        super().showEvent(event)
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.initialize()
    
    def initialize(self) -> None:
        """Initialize the tab. Override in subclasses."""
        pass
    
    def cleanup(self) -> None:
        """Clean up resources. Override in subclasses if needed."""
        if hasattr(self, 'event_handler'):
            try:
                self.event_handler.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up event handler: {e}")
    
    def closeEvent(self, event) -> None:
        """Handle close events."""
        self.cleanup()
        super().closeEvent(event)


# Decorators for tab methods
def main_thread_only(method):
    """Decorator to ensure a method runs in the main thread."""
    def wrapper(self, *args, **kwargs):
        if QCoreApplication.instance() and QThread.currentThread() != QCoreApplication.instance().thread():
            # Schedule the method to run in the main thread
            QMetaObject.invokeMethod(
                self,
                method.__name__,
                Qt.ConnectionType.QueuedConnection,
                QGenericReturnArgument(),
                *args,
                **kwargs
            )
        else:
            # Already in the main thread, call directly
            return method(self, *args, **kwargs)
    return wrapper


def handle_errors(default=None):
    """Decorator to handle errors in tab methods."""
    def decorator(method):
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in {method.__name__}: {e}", exc_info=True)
                self.status_update.emit(
                    f"Error in {self.tab_name}: {str(e)}", 
                    "error"
                )
                return default
        return wrapper
    return decorator
