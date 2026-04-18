from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Kingdom AI Loading Screen - PyQt6 Version
# This module provides a loading screen with progress bar for the Kingdom AI system

import os
import sys
import time
import logging
import math
import threading
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QProgressBar, 
                           QVBoxLayout, QHBoxLayout, QFrame, QSplashScreen)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QFont, QPixmap, QColor, QPainter
from typing import Optional, Callable, Dict, Any, Union, List

# Configure logger
logger = logging.getLogger(__name__)

class LoadingScreen(QObject):
    """Loading screen for Kingdom AI with progress bar and status messages."""
    
    # Define signals for thread-safe updates
    progress_updated = pyqtSignal(float)
    status_updated = pyqtSignal(str)
    transition_signal = pyqtSignal()
    
    def __init__(self, title: str = "Kingdom AI", icon_path: Optional[str] = None, event_bus=None, width: int = 600, height: int = 400):
        """Initialize the loading screen.
        
        Args:
            title: Window title
            icon_path: Path to icon file
            event_bus: Event bus instance
            width: Width of the loading screen
            height: Height of the loading screen
        """
        super().__init__()
        
        self.title = title
        self.icon_path = icon_path
        self.width = width
        self.height = height
        self.app = None  # QApplication instance
        self.window = None  # Main window
        self.progress_bar = None
        self.status_label = None
        self.progress_label = None
        self.is_destroyed = False
        self.logger = logging.getLogger(__name__)
        self.animation_thread = None
        self.stop_animation = False
        self.event_bus = event_bus
        self.bg_color = "#212121"  # Dark background
        
        # Animation settings
        self.animation_active = False
        self.animation_timer = None
        self.current_dot = 0
        self.dots = []
        
        # Component initialization tracking
        self.components_total = 32  # Total expected components
        self.components_initialized = 0
        self.components_started = 0
        
        # Connect signals to slots
        self.progress_updated.connect(self._update_progress_ui)
        self.status_updated.connect(self._update_status_ui)
        self.transition_signal.connect(self._handle_transition)
        
    def create_gui(self, parent=None):
        """Create the GUI elements for the loading screen."""
        try:
            # Check if we need to create a QApplication
            if QApplication.instance() is None:
                self.app = QApplication(sys.argv)
            else:
                self.app = QApplication.instance()
            
            # Create main window
            self.window = QMainWindow()
            self.window.setWindowTitle(self.title)
            self.window.setFixedSize(self.width, self.height)
            self.window.setStyleSheet(f"background-color: {self.bg_color};")
            
            # Try to set icon
            if self.icon_path and os.path.exists(self.icon_path):
                try:
                    icon = QPixmap(self.icon_path)
                    self.window.setWindowIcon(icon)
                except Exception as e:
                    self.logger.warning(f"Failed to load icon: {e}")
            
            # Create central widget and main layout
            central_widget = QWidget()
            self.window.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(20, 20, 20, 20)
            
            # Create title label
            title_label = QLabel(self.title)
            title_label.setFont(QFont("Helvetica", 24, QFont.Weight.Bold))
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("color: white;")
            main_layout.addWidget(title_label)
            main_layout.addSpacing(30)
            
            # Create progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid grey;
                    border-radius: 5px;
                    text-align: center;
                    height: 25px;
                    background-color: #333333;
                    color: white;
                }
                
                QProgressBar::chunk {
                    background-color: #4CAF50;
                    width: 10px;
                    margin: 0px;
                }
            """)
            main_layout.addWidget(self.progress_bar)
            
            # Create status label
            self.status_label = QLabel("Initializing...")
            self.status_label.setStyleSheet("color: white;")
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.status_label.setWordWrap(True)
            main_layout.addWidget(self.status_label)
            
            # Create progress percentage label
            self.progress_label = QLabel("0%")
            self.progress_label.setStyleSheet("color: white;")
            self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(self.progress_label)
            
            # Create dots area for animation
            dots_frame = QFrame()
            dots_layout = QHBoxLayout(dots_frame)
            dots_layout.setContentsMargins(0, 20, 0, 0)
            
            # Create animation dots
            for i in range(5):
                dot = QLabel("•")
                dot.setStyleSheet("color: grey; font-size: 24px;")
                dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
                dots_layout.addWidget(dot)
                self.dots.append(dot)
                
            main_layout.addWidget(dots_frame)
            main_layout.addStretch(1)
            
            # Center window on screen
            screen_geometry = self.app.primaryScreen().geometry()
            x = (screen_geometry.width() - self.width) // 2
            y = (screen_geometry.height() - self.height) // 2
            self.window.move(x, y)
            
            # Configure window to handle close events
            self.window.closeEvent = lambda event: self._on_close(event)
            
            self.logger.info("Loading screen GUI created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating loading screen GUI: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _start_animation(self):
        """Start the loading animation."""
        self.animation_active = True
        # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
        self._timer_manager = get_qt_timer_manager()
        self.animation_timer.timeout.connect(self._animate)
        self.animation_timer.start(300)  # Update every 300ms
        
    def _animate(self):
        """Animate the loading dots."""
        if not self.animation_active or not self.dots:
            return
            
        try:
            # Reset all dots to grey
            for dot in self.dots:
                dot.setStyleSheet("color: grey; font-size: 24px;")
                
            # Highlight the current dot
            self.dots[self.current_dot].setStyleSheet("color: white; font-size: 24px;")
            
            # Move to next dot
            self.current_dot = (self.current_dot + 1) % len(self.dots)
            
        except Exception as e:
            self.logger.error(f"Animation error: {e}")
    
    def show(self, parent=None):
        """Display the loading screen."""
        try:
            # Create GUI if not already created
            if not self.window:
                self.create_gui(parent)
                
            # Show the window
            self.window.show()
            
            # Start animation
            self._start_animation()
            
            # Process events to make window visible
            if self.app:
                self.app.processEvents()
                
            self.logger.info("Loading screen shown")
            return True
            
        except Exception as e:
            self.logger.error(f"Error showing loading screen: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def update_status(self, message: str):
        """Update the status message.
        
        Args:
            message: Status message to display
        """
        try:
            self.logger.debug(f"Status update: {message}")
            self.status_updated.emit(message)
            return True
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            return False
    
    def _update_status_ui(self, message: str):
        """Update the status UI element (thread-safe).
        
        Args:
            message: Status message to display
        """
        if self.status_label:
            self.status_label.setText(message)
            if self.app:
                self.app.processEvents()
    
    def update_progress(self, progress=None, status_message=None):
        """Update loading screen progress and status.
        
        Args:
            progress: Progress value (0-100)
            status_message: Optional status message to display
        """
        try:
            if progress is not None:
                # Ensure progress is between 0-100
                progress = max(0, min(100, progress))
                self.logger.debug(f"Progress update: {progress}%")
                self.progress_updated.emit(progress)
                
            if status_message is not None:
                self.update_status(status_message)
                
            # Process events to update UI
            if self.app:
                self.app.processEvents()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating progress: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _update_progress_ui(self, progress: float):
        """Update the progress UI elements (thread-safe).
        
        Args:
            progress: Progress value (0-100)
        """
        if self.progress_bar:
            self.progress_bar.setValue(int(progress))
            
        if self.progress_label:
            self.progress_label.setText(f"{int(progress)}%")
            
        if self.app:
            self.app.processEvents()
    
    def destroy(self):
        """Destroy the loading screen."""
        try:
            self.logger.info("Destroying loading screen")
            
            # Stop animation
            if self.animation_timer:
                self.animation_timer.stop()
                
            self.animation_active = False
            self.stop_animation = True
            
            # Close window
            if self.window:
                self.window.close()
                self.window = None
                
            self.is_destroyed = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error destroying loading screen: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def transition_to_main_window(self, callback: Optional[Callable] = None, delay: int = 0):
        """Transition from loading screen to main window.
        
        Args:
            callback: Function to call after transition
            delay: Delay in milliseconds before transition
        """
        try:
            self.logger.info(f"Preparing transition to main window (delay: {delay}ms)")
            
            # Store callback
            self._transition_callback = callback
            
            if delay > 0:
                # Use a timer for the delay
                QTimer.singleShot(delay, self.transition_signal.emit)
            else:
                # No delay, emit signal directly
                self.transition_signal.emit()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error during transition preparation: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _handle_transition(self):
        """Handle the actual transition (called via signal)."""
        try:
            # Hide the loading screen
            self.hide()
            
            # Execute the callback if one was provided
            if hasattr(self, '_transition_callback') and callable(self._transition_callback):
                self._transition_callback()
                
            self.logger.info("Transition to main window complete")
            
        except Exception as e:
            self.logger.error(f"Error during transition: {e}")
            self.logger.error(traceback.format_exc())
    
    def connect_event_bus(self, event_bus):
        """Connect the loading screen to the event bus.
        
        This method is called by the main application to connect the loading screen
        to the event bus, allowing it to receive status updates from components.
        
        Args:
            event_bus: The event bus instance to connect to
        """
        try:
            if not event_bus:
                self.logger.error("No event bus provided")
                return False
                
            self.event_bus = event_bus
            
            # Subscribe to relevant events
            self.event_bus.subscribe("component_initialized", self._handle_component_initialized)
            self.event_bus.subscribe("thoth_status", self._handle_thoth_status)
            self.event_bus.subscribe("redis_status", self._handle_redis_status)
            self.event_bus.subscribe("api_keys_status", self._handle_api_keys_status)
            
            self.logger.info("Loading screen connected to event bus")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to event bus: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _handle_component_initialized(self, event_data):
        """Handle component initialization status updates."""
        try:
            component_name = event_data.get("component", "Unknown component")
            self.logger.debug(f"Component initialized: {component_name}")
            
            # Increment initialized counter
            self.components_initialized += 1
            
            # Calculate progress as a percentage of total components
            progress = min(95, (self.components_initialized / self.components_total) * 100)
            
            # Update the progress and status message
            self.update_progress(
                progress=progress,
                status_message=f"Initializing: {component_name} ({self.components_initialized}/{self.components_total})"
            )
            
        except Exception as e:
            self.logger.error(f"Error handling component initialization: {e}")
    
    def _handle_thoth_status(self, event_data):
        """Handle ThothAI status updates."""
        try:
            status = event_data.get("status", "Unknown")
            self.logger.debug(f"ThothAI status update: {status}")
            
            # Update status message
            self.update_status(f"ThothAI: {status}")
            
        except Exception as e:
            self.logger.error(f"Error handling ThothAI status: {e}")
    
    def _handle_redis_status(self, event_data):
        """Handle Redis connection status updates."""
        try:
            status = event_data.get("status", "Unknown")
            self.logger.debug(f"Redis status update: {status}")
            
            # Update status message
            self.update_status(f"Redis: {status}")
            
        except Exception as e:
            self.logger.error(f"Error handling Redis status: {e}")
    
    def _handle_api_keys_status(self, event_data):
        """Handle API keys status updates."""
        try:
            status = event_data.get("status", "Unknown")
            self.logger.debug(f"API keys status update: {status}")
            
            # Update status message
            self.update_status(f"API Keys: {status}")
            
        except Exception as e:
            self.logger.error(f"Error handling API keys status: {e}")
    
    def _on_close(self, event=None):
        """Handle window close event."""
        self.logger.info("Loading screen close event detected")
        self.destroy()
    
    def hide(self):
        """Hide the loading screen."""
        if hasattr(self, "window") and self.window:
            # Hide the window
            self.window.hide()
            
            # Process events to ensure the window is hidden
            if self.app:
                self.app.processEvents()
                
            self.logger.info("Loading screen hidden")
            return True
        return False

def show_loading_screen(title="Kingdom AI"):
    """Create and show the loading screen.
    
    Args:
        title: Optional title for the loading screen window
        
    Returns:
        LoadingScreen: The loading screen instance
    """
    # Create a loading screen instance
    loading_screen = LoadingScreen(title=title)
    
    # Create the GUI elements
    loading_screen.create_gui()
    
    # Show the loading screen
    loading_screen.show()
    
    # Make loading_screen available in globals
    globals()['loading_screen'] = loading_screen
    
    # Initialize progress tracking variables
    globals()['components_initialized'] = 0
    globals()['total_components'] = 32  # Total number of expected components
    
    # Start with initial progress
    loading_screen.update_progress(0.5, "Initializing Kingdom AI system...")
    
    # Return the loading screen instance
    return loading_screen

def update_loading_progress(progress, message=None):
    """Update the loading screen progress from external modules.
    
    Args:
        progress: Progress value (0-100)
        message: Optional status message
        
    Returns:
        bool: Success status
    """
    try:
        # Check if loading_screen is in globals
        if 'loading_screen' in globals() and globals()['loading_screen']:
            # Update the progress
            globals()['loading_screen'].update_progress(progress, message)
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating loading progress: {e}")
        return False

def force_ui_refresh():
    """Force the UI to refresh and process events.
    
    This is useful during initialization to show progress updates
    while background processes are running.
    
    Returns:
        bool: Success status
    """
    try:
        # Check if we have a loading screen instance
        if 'loading_screen' in globals() and globals()['loading_screen']:
            # Process pending events
            app = QApplication.instance()
            if app:
                app.processEvents()
                return True
        return False
    except Exception as e:
        logger.error(f"Error during UI refresh: {e}")
        return False

def close_loading_screen():
    """Close the loading screen if it exists.
    
    This should be called when transitioning to the main application.
    
    Returns:
        bool: Success status
    """
    try:
        if 'loading_screen' in globals() and globals()['loading_screen']:
            if not globals()['loading_screen'].is_destroyed:
                # Destroy the loading screen
                globals()['loading_screen'].destroy()
                logger.info("Loading screen closed successfully")
                return True
        return False
    except Exception as e:
        logger.error(f"Error closing loading screen: {e}")
        return False

# If this module is run directly, show the loading screen
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Show loading screen
    loading_screen = show_loading_screen()
    
    # Simulate progress
    for i in range(0, 101, 10):
        time.sleep(0.5)
        loading_screen.update_progress(i, f"Initializing component {i//10} of 10...")
    
    # Transition to main window
    loading_screen.transition_to_main_window(lambda: print("Transition complete!"))
    
    # Keep main thread alive
    app = QApplication.instance()
    if app:
        sys.exit(app.exec())
