from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Animation Fix for Kingdom AI

This module provides a comprehensive fix for the animation issues in the Kingdom AI GUI.
Implemented with PyQt6 for smooth animations and transitions with no Tkinter fallbacks.
"""

import os
import sys
import logging
import threading
import time
import traceback
from typing import Optional, Callable, Dict, Any, Union, List

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_qt_animation_environment():
    """
    Configure the PyQt6 environment for optimal animation performance.
    This function should be called before any GUI initialization.
    """
    logger.info("Setting up PyQt6 animation environment")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer, Qt
        
        # Enable Qt's built-in high-performance animation system
        if not QApplication.instance():
            # Apply optimal application attributes if no instance exists yet
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
            
            # Set style hints for smooth animations
            app = QApplication(sys.argv if not hasattr(sys, 'argv') or not sys.argv else sys.argv)
            app.setStyle('Fusion')  # Use Fusion style for consistent cross-platform animations
        else:
            # Get existing instance
            app = QApplication.instance()
        
        # Create animation manager class for the application
        class AnimationManager:
            def __init__(self):
                # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
                self._timer_manager = get_qt_timer_manager()
                self.animation_callbacks = []
                self.frame_rate = 60  # Default 60 FPS
                # Start animation timer using thread-safe timer
                start_timer_safe(
                    timer_id="animation_manager_timer",
                    interval_ms=1000 // self.frame_rate,
                    callback=self.update_animations,
                    single_shot=False
                )
                logger.info(f"Started PyQt6 animation timer at {self.frame_rate} FPS")
                
            def update_animations(self):
                """Process all registered animation callbacks"""
                try:
                    # Process application events
                    QApplication.processEvents()
                    
                    # Call any registered animation callbacks
                    for callback in list(self.animation_callbacks):
                        try:
                            callback()
                        except Exception as e:
                            logger.error(f"Error in animation callback: {e}")
                except Exception as e:
                    logger.error(f"Error in animation update loop: {e}")
                    logger.error(traceback.format_exc())
            
            def register_animation(self, callback):
                """Register an animation callback to be called every frame"""
                if callback not in self.animation_callbacks:
                    self.animation_callbacks.append(callback)
                    return True
                return False
                
            def unregister_animation(self, callback):
                """Unregister an animation callback"""
                if callback in self.animation_callbacks:
                    self.animation_callbacks.remove(callback)
                    return True
                return False
                
            def set_frame_rate(self, fps):
                """Set the animation frame rate"""
                self.frame_rate = max(1, min(120, fps))  # Clamp between 1-120 FPS
                # Stop old timer and start new one with updated interval
                stop_timer_safe("animation_manager_timer")
                start_timer_safe(
                    timer_id="animation_manager_timer",
                    interval_ms=1000 // self.frame_rate,
                    callback=self.update_animations,
                    single_shot=False
                )
                logger.info(f"Updated animation frame rate to {self.frame_rate} FPS")
        
        # Create a singleton instance and attach to the application
        if not hasattr(app, '_animation_manager'):
            app._animation_manager = AnimationManager()
        
        logger.info("✅ Successfully set up PyQt6 animation environment")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to set up PyQt6 animation environment: {e}")
        logger.error(traceback.format_exc())
        return False

def ensure_qt_event_loop_running(app=None):
    """
    Ensure the PyQt6 event loop is running in a non-blocking way.
    
    Args:
        app: Optional QApplication instance. If None, will try to use the existing instance or create one.
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("Ensuring PyQt6 event loop is running")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer, QEventLoop, QThread
        
        # Get or create QApplication instance
        if app is None:
            app = QApplication.instance()
            if app is None:
                logger.warning("No QApplication instance found, creating one")
                app = QApplication(sys.argv if hasattr(sys, 'argv') else [])
                app.setStyle('Fusion')  # Consistent cross-platform style
                app.setQuitOnLastWindowClosed(False)  # Don't quit when windows close
        
        # Check if event loop is already running
        is_running = app.property("_event_loop_running") or False
        if is_running:
            logger.info("PyQt6 event loop already running, nothing to do")
            return True
            
        # Start event loop in a separate thread if needed
        def run_event_loop():
            try:
                logger.info("Starting PyQt6 event loop in background thread")
                
                # Set flag to indicate event loop is running
                app.setProperty("_event_loop_running", True)
                
                # Create a timer to keep the event loop active
                # This ensures events are processed even with no windows
                # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
                start_timer_safe(
                    timer_id="keep_alive_timer",
                    interval_ms=100,
                    callback=lambda: None,  # No-op function
                    single_shot=False
                )
                
                # Run the event loop
                try:
                    # Check if we're in the main thread
                    if QThread.currentThread() is QApplication.instance().thread():
                        # We're in the main thread, use exec() directly
                        logger.info("Running event loop in main thread")
                        app.exec()
                    else:
                        # We're in a background thread, use a local event loop
                        logger.info("Running event loop in background thread")
                        loop = QEventLoop()
                        while app.property("_event_loop_running"):
                            loop.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 100)
                            time.sleep(0.01)  # Small sleep to prevent CPU overuse
                except Exception as e:
                    logger.warning(f"Event loop interrupted: {e}")
                
                # Clean up
                stop_timer_safe("keep_alive_timer")
                app.setProperty("_event_loop_running", False)
                logger.info("PyQt6 event loop has exited")
                
            except Exception as e:
                logger.error(f"Error in PyQt6 event loop thread: {e}")
                logger.error(traceback.format_exc())
                app.setProperty("_event_loop_running", False)
        
        # Check if we're in the main thread
        if QThread.currentThread() is QApplication.instance().thread():
            # In main thread, we can start the event loop directly using a timer
            # to avoid blocking this function call
            QTimer.singleShot(0, run_event_loop)
        else:
            # In a non-main thread, start a separate thread for the event loop
            event_loop_thread = threading.Thread(target=run_event_loop, daemon=True)
            event_loop_thread.start()
            # Store thread reference
            app.setProperty("_event_loop_thread", event_loop_thread)
            # Wait briefly to ensure thread starts
            time.sleep(0.1)
        
        logger.info("✅ PyQt6 event loop is now running")
        return True
        
    except Exception as e:
        logger.error(f"Error ensuring event loop is running: {e}")
        logger.error(f"❌ Failed to ensure mainloop running: {e}")
        logger.error(traceback.format_exc())
        return False

def setup_qt_loading_screen():
    """
    Configure PyQt6 loading screen with smooth animations and transitions.
    This should be called early in the application startup process.
    
    Returns:
        bool: True if successful, False otherwise
    """
    success = True
    
    # 1. Set up the PyQt6 animation environment
    qt_setup_success = setup_qt_animation_environment()
    success = success and qt_setup_success
    
    # 2. Apply loading screen specific enhancements
    try:
        # Import the loading screen module (which should now use PyQt6)
        try:
            from gui import qt_loading_screen
            logger.info("Using qt_loading_screen module (preferred)")
            module = qt_loading_screen
        except ImportError:
            # Fall back to loading_screen which should also be PyQt6-based now
            try:
                from gui import loading_screen
                logger.info("Falling back to loading_screen module")
                module = loading_screen
            except ImportError:
                logger.error("No compatible loading screen module found")
                return False
        
        # Get the QApplication instance
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app:
            logger.warning("No QApplication instance found, creating one")
            app = QApplication(sys.argv)
        
        # Register the animation manager for the loading screen if available
        if hasattr(module, 'LoadingScreen') and hasattr(app, '_animation_manager'):
            # Define enhanced animation method for PyQt6
            def enhanced_qt_animation(self, frame=None):
                """Enhanced PyQt6 animation method with proper error handling"""
                if not getattr(self, 'animation_active', False):
                    return
                    
                try:
                    # Call the actual animation update
                    if hasattr(self, '_update_animation_frame'):
                        self._update_animation_frame(frame)
                        
                    # Schedule next frame through the animation manager
                    if app._animation_manager and getattr(self, 'animation_active', False):
                        if not app._animation_manager.animation_callbacks or self._animate not in app._animation_manager.animation_callbacks:
                            app._animation_manager.register_animation(self._animate)
                except Exception as e:
                    logger.error(f"Error in PyQt6 animation: {e}")
            
            # Replace or add the animation method if it exists
            if hasattr(module.LoadingScreen, '_animate'):
                module.LoadingScreen._animate = enhanced_qt_animation
                logger.info("✅ Enhanced PyQt6 animation method with improved handling")
        
        # Make sure loading screen module uses the Qt event loop
        if not hasattr(module, 'ensure_event_loop_running'):
            module.ensure_event_loop_running = ensure_qt_event_loop_running
            logger.info("✅ Added ensure_qt_event_loop_running to loading screen module")
        
        logger.info("✅ Successfully configured PyQt6 loading screen")
    except Exception as e:
        logger.error(f"❌ Failed to configure PyQt6 loading screen: {e}")
        logger.error(traceback.format_exc())
        success = False
    
    return success

# Apply PyQt6 setup immediately when this module is imported
PYQT6_ANIMATION_SETUP_COMPLETE = setup_qt_loading_screen()

if __name__ == "__main__":
    # When run directly, display results
    print(f"PyQt6 animation setup complete: {PYQT6_ANIMATION_SETUP_COMPLETE}")
    
    # Test loading screen if possible
    try:
        print("Testing PyQt6 loading screen animation...")
        from gui import qt_loading_screen
        
        # Make sure event loop is running
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        ensure_qt_event_loop_running(app)
        
        # Show loading screen
        screen = qt_loading_screen.show_loading_screen()
        
        # Simulate progress updates
        for i in range(0, 101, 10):
            qt_loading_screen.update_loading_progress(i, f"PyQt6 test progress {i}%")
            time.sleep(0.5)
        
        print("PyQt6 loading screen test complete!")
    except Exception as e:
        print(f"Error testing PyQt6 loading screen: {e}")
        traceback.print_exc()
