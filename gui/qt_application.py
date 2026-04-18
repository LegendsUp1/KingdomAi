from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
"""
Qt Application Manager for Kingdom AI

This module handles Qt application initialization, event loop integration with asyncio,
and proper cleanup of Qt resources.
"""

import sys
import asyncio
import logging
import traceback
from typing import Optional, Callable, Any, Coroutine

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt, QObject, pyqtSignal

logger = logging.getLogger("kingdom.qt_application")

class QtApplicationManager(QObject):
    """Manages Qt application lifecycle and asyncio integration."""
    
    def __init__(self, app_name: str = "Kingdom AI"):
        super().__init__()
        self.app_name = app_name
        self.app: Optional[QApplication] = None
        self.loop = asyncio.get_event_loop()
        self._cleanup_handlers = []
        
    def initialize(self) -> bool:
        """Initialize the Qt application."""
        try:
            # Check if QApplication already exists
            from PyQt6.QtWidgets import QApplication
            
            if QApplication.instance() is not None:
                logger.warning("QApplication already exists, reusing existing instance")
                self.app = QApplication.instance()
                return True
                
            # Set up Qt application attributes before creating QApplication
            from PyQt6.QtCore import QCoreApplication, Qt
            
            # Only set attributes if they haven't been set yet
            if not QCoreApplication.testAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts):
                QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
            if not QCoreApplication.testAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL):
                QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL)
            if not QCoreApplication.testAttribute(Qt.ApplicationAttribute.AA_UseStyleSheetPropagationInWidgetStyles):
                QCoreApplication.setAttribute(
                    Qt.ApplicationAttribute.AA_UseStyleSheetPropagationInWidgetStyles, 
                    True
                )
            
            # Create the application instance
            self.app = QApplication(sys.argv)
            self.app.setApplicationName(self.app_name)
            self.app.setQuitOnLastWindowClosed(True)
            
            # Set up cleanup on exit
            self.app.aboutToQuit.connect(self.cleanup)
            
            # Set up timer to process asyncio events
            # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
            self._timer_manager = get_qt_timer_manager()
            self.timer.timeout.connect(self._process_asyncio_events)
            self.timer.start(100)  # SOTA 2026 FIX: 100ms saves CPU vs 50ms
            
            logger.info("Qt application initialized successfully")
            return True
            
        except Exception as e:
            logger.critical(f"Failed to initialize Qt application: {e}")
            return False
    
    def _process_asyncio_events(self):
        """Process asyncio events in the Qt event loop."""
        try:
            self.loop.stop()
            self.loop.run_forever()
        except Exception as e:
            logger.error(f"Error processing asyncio events: {e}")
    
    def add_cleanup_handler(self, handler: Callable[[], None]) -> None:
        """Add a cleanup handler to be called on application exit."""
        self._cleanup_handlers.append(handler)
    
    def cleanup(self) -> None:
        """Clean up Qt resources and call registered cleanup handlers."""
        logger.info("Cleaning up Qt resources...")
        
        try:
            # Process any pending events first
            if self.app:
                self.app.sendPostedEvents(None, 0)  # Process all pending events
                self.app.processEvents()
                
                # Close all windows
                for widget in self.app.topLevelWidgets():
                    try:
                        widget.close()
                        widget.deleteLater()
                    except Exception as e:
                        logger.warning(f"Error closing widget: {e}")
                
                # Process events again after closing windows
                self.app.sendPostedEvents(None, 0)
                self.app.processEvents()
            
            # Call all registered cleanup handlers
            for handler in self._cleanup_handlers:
                try:
                    handler()
                except Exception as e:
                    logger.error(f"Error in cleanup handler: {e}")
            
            # Stop the asyncio event loop timer
            if hasattr(self, 'timer') and self.timer.isActive():
                self.timer.stop()
            
            # Force garbage collection to clean up Qt objects
            import gc
            gc.collect()
            
            # One final process events
            if self.app:
                self.app.sendPostedEvents(None, 0)
                self.app.processEvents()
            
            logger.info("Qt cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during Qt cleanup: {e}", exc_info=True)
    
    def exec(self) -> int:
        """Start the application event loop."""
        if not self.app:
            logger.error("Cannot execute: Qt application not initialized")
            return 1
            
        try:
            logger.info("Starting Qt application event loop")
            return self.app.exec()
        except Exception as e:
            logger.critical(f"Fatal error in Qt application: {e}")
            return 1
        finally:
            self.cleanup()

async def run_qt_async_internal(main_coroutine: Coroutine[Any, Any, int]) -> int:
    """Internal function to run the main coroutine and handle its result."""
    try:
        return await main_coroutine
    except Exception as e:
        logger.error(f"Error in main coroutine: {e}")
        logger.error(traceback.format_exc())
        return 1

def run_qt_async(main_coroutine: Coroutine[Any, Any, int]) -> int:
    """
    Run a Qt application with asyncio integration.
    
    Args:
        main_coroutine: The main coroutine to run (should return an int exit code)
        
    Returns:
        int: Application exit code
    """
    # Set up the Qt application
    qt_app = QtApplicationManager("Kingdom AI")
    if not qt_app.initialize():
        return 1
    
    # Create an event to signal when the main coroutine is done
    done = asyncio.Event()
    result = None
    
    async def run_coroutine():
        nonlocal result
        try:
            result = await run_qt_async_internal(main_coroutine)
        finally:
            done.set()
    
    # Schedule the main coroutine
    asyncio.ensure_future(run_coroutine())
    
    # Run the application
    exit_code = qt_app.exec()
    
    # If the application exited but the coroutine is still running,
    # wait for it to complete with a timeout
    if not done.is_set():
        try:
            asyncio.get_event_loop().run_until_complete(asyncio.wait_for(done.wait(), timeout=5.0))
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for main coroutine to complete")
    
    # Return the coroutine result if available, otherwise the Qt exit code
    return result if result is not None else exit_code
