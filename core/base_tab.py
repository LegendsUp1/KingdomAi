"""
Base Tab class for all Kingdom AI tabs with thread-safe UI updates and event handling.
"""
from typing import Any, Optional, TypeVar, Callable
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QMetaObject, Qt, QThreadPool, QRunnable
from PyQt6.QtWidgets import QWidget, QMessageBox
import logging
from functools import wraps

T = TypeVar('T', bound='BaseTab')

class BaseTab(QWidget):
    """
    Base class for all tab widgets providing thread-safe UI updates and event handling.
    """
    # Class-level signals
    status_update = pyqtSignal(str, str)  # message, level (info/warning/error)
    data_updated = pyqtSignal(str, object)  # data_type, data
    
    def __init__(self, parent: Optional[QWidget] = None, 
                 event_bus: Optional[Any] = None,
                 redis_conn: Optional[Any] = None):
        super().__init__(parent)
        self._event_bus = event_bus
        self._redis_conn = redis_conn
        self._initialized = False
        self._event_handlers = {}
        self._thread_pool = QThreadPool.globalInstance()
        self._setup_connections()
    
    def _setup_connections(self) -> None:
        """Set up signal connections."""
        self.status_update.connect(self._handle_status_update)
    
    @pyqtSlot(str, str)
    def _handle_status_update(self, message: str, level: str = "info") -> None:
        """Handle status updates in a thread-safe manner."""
        if not self.isVisible():
            return
            
        try:
            if level.lower() == "error":
                QMessageBox.critical(self, "Error", message)
            elif level.lower() == "warning":
                QMessageBox.warning(self, "Warning", message)
            # Info messages can be logged without dialog
        except Exception as e:
            logging.error(f"Error in status update handler: {e}")
    
    def run_in_thread(self, func: Callable, callback: Optional[Callable] = None) -> None:
        """Run a function in a background thread."""
        class Worker(QRunnable):
            def __init__(self, task, on_complete=None):
                super().__init__()
                self.task = task
                self.on_complete = on_complete
            
            def run(self):
                try:
                    result = self.task()
                    if self.on_complete:
                        QMetaObject.invokeMethod(
                            self.on_complete[0], 
                            self.on_complete[1],
                            Qt.ConnectionType.QueuedConnection,
                            result
                        )
                except Exception as e:
                    logging.error(f"Error in worker thread: {e}")
                    self.tab.status_update.emit(f"Error in background task: {e}", "error")
        
        worker = Worker(func, (self, callback) if callback else None)
        self._thread_pool.start(worker)
    
    def update_ui_safely(self, callback: Callable, *args, **kwargs) -> None:
        """Update UI in a thread-safe manner."""
        if not self.isVisible():
            return
            
        QMetaObject.invokeMethod(
            self, 
            '_safe_ui_update',
            Qt.ConnectionType.QueuedConnection,
            (callback, args, kwargs)
        )
    
    @pyqtSlot(tuple)
    def _safe_ui_update(self, callback_data: tuple) -> None:
        """Execute a UI update callback safely."""
        try:
            callback, args, kwargs = callback_data
            callback(*args, **kwargs)
        except Exception as e:
            logging.error(f"UI update error: {e}")
            self.status_update.emit(f"UI update failed: {e}", "error")
    
    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """Register an event handler for a specific event type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        
        if self._event_bus:
            self._event_bus.subscribe(event_type, self._handle_event)
    
    def _handle_event(self, event_type: str, data: Any) -> None:
        """Handle an incoming event."""
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    self.update_ui_safely(handler, data)
                except Exception as e:
                    logging.error(f"Error in event handler for {event_type}: {e}")
    
    def showEvent(self, event) -> None:
        """Handle show event to initialize if needed."""
        if not self._initialized:
            self.initialize()
            self._initialized = True
        super().showEvent(event)
    
    def initialize(self) -> None:
        """Initialize the tab. Override in subclasses."""
        pass
    
    def cleanup(self) -> None:
        """Clean up resources. Override in subclasses."""
        if self._event_bus:
            for event_type in self._event_handlers:
                self._event_bus.unsubscribe(event_type, self._handle_event)
        self._event_handlers.clear()
    
    def closeEvent(self, event) -> None:
        """Handle close event to clean up resources."""
        self.cleanup()
        super().closeEvent(event)

def thread_safe(method):
    """Decorator to ensure a method runs in the main thread."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if QThreadPool.globalInstance().isRunning() and QThreadPool.globalInstance().activeThreadCount() > 0:
            self.update_ui_safely(method, *args, **kwargs)
        else:
            return method(self, *args, **kwargs)
    return wrapper
