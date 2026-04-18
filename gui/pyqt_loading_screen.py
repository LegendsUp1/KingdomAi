#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQt6-based Loading Screen for Kingdom AI

This module provides a PyQt6-compatible loading screen for Kingdom AI.
This replaces the Tkinter-based loading screen to avoid GUI toolkit conflicts.
"""

import os
import sys
import time
import threading
import logging
from typing import Optional, Any, List, Dict

try:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QSize
    from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QMovie, QBrush, QLinearGradient
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QApplication,
        QSplashScreen, QMainWindow
    )
    PYQT_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).error("PyQt6 not available, loading screen will not work")
    PYQT_AVAILABLE = False

# Import base component if available
try:
    from core.base_component import BaseComponent
    BASE_COMPONENT_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("BaseComponent not available, using standalone implementation")
    BASE_COMPONENT_AVAILABLE = False
    class BaseComponent:
        def __init__(self, name="", event_bus=None):
            self.name = name
            self.event_bus = event_bus

# Configure logger
logger = logging.getLogger(__name__)

class PyQtLoadingScreen(QWidget, BaseComponent if BASE_COMPONENT_AVAILABLE else object):
    """PyQt6-based loading screen for Kingdom AI"""
    
    # Define signals for updating the loading screen
    updateProgressSignal = pyqtSignal(int, str)
    closeSignal = pyqtSignal()
    
    def __init__(self, 
                 title: str = "Kingdom AI", 
                 icon_path: Optional[str] = None, 
                 event_bus: Optional[Any] = None,
                 width: int = 600, 
                 height: int = 400,
                 parent: Optional[QWidget] = None):
        """Initialize the PyQt6 loading screen
        
        Args:
            title: Title of the loading screen window
            icon_path: Path to the icon to be displayed
            event_bus: Event bus for communication
            width: Width of the loading screen
            height: Height of the loading screen
            parent: Parent widget (if any)
        """
        QWidget.__init__(self, parent)
        if BASE_COMPONENT_AVAILABLE:
            BaseComponent.__init__(self, name="loading_screen", event_bus=event_bus)
        else:
            self.name = "loading_screen"
            self.event_bus = event_bus
        
        self.title = title
        self.icon_path = icon_path
        self.width = width
        self.height = height
        self.is_destroyed = False
        self.stopped = False
        self.progress_value = 0
        
        self.logger = logging.getLogger(__name__)
        self.animation_thread = None
        self.stop_animation = False
        
        # Set up UI
        self._setup_ui()
        
        # Connect signals to slots
        self.updateProgressSignal.connect(self._update_progress_slot)
        self.closeSignal.connect(self._close_slot)
        
        # Start animation
        self._start_animation()
        
        self.logger.info("PyQt6 Loading Screen initialized")
    
    def _setup_ui(self):
        """Set up the UI elements"""
        # Configure window
        self.setWindowTitle(self.title)
        self.setFixedSize(self.width, self.height)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # Main layout
        self.layout = QVBoxLayout(self)
        
        # Title label
        self.title_label = QLabel(self.title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #FFFFFF;
            margin-bottom: 10px;
        """)
        
        # Logo/icon if provided
        if self.icon_path and os.path.exists(self.icon_path):
            self.logo_label = QLabel()
            pixmap = QPixmap(self.icon_path)
            if not pixmap.isNull():
                self.logo_label.setPixmap(pixmap.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio))
                self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.layout.addWidget(self.logo_label)
        
        # Add title
        self.layout.addWidget(self.title_label)
        
        # Progress bar
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
            }
            
            QProgressBar::chunk {
                background-color: #007BFF;
                width: 20px;
            }
        """)
        self.layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 14px;
            color: #FFFFFF;
            margin-top: 10px;
        """)
        self.layout.addWidget(self.status_label)
        
        # Set the overall styling
        self.setStyleSheet("""
            background-color: #212121;
            color: #FFFFFF;
        """)
    
    def _start_animation(self):
        """Start the background animation"""
        self.animation_thread = threading.Thread(target=self._run_animation)
        self.animation_thread.daemon = True
        self.animation_thread.start()
    
    def _run_animation(self):
        """Run the animation in a background thread"""
        try:
            while not self.stop_animation and not self.is_destroyed:
                if self.progress_value < 100:
                    # Auto-increment a little for animation effect
                    time.sleep(0.5)
                else:
                    time.sleep(0.2)
        except Exception as e:
            self.logger.error(f"Error in animation thread: {e}")
    
    @pyqtSlot(int, str)
    def _update_progress_slot(self, value: int, status_text: str):
        """Update the progress bar and status text
        
        Args:
            value: Progress value (0-100)
            status_text: Status text to display
        """
        if self.is_destroyed:
            return
            
        self.progress_value = value
        self.progress_bar.setValue(value)
        self.status_label.setText(status_text)
    
    @pyqtSlot()
    def _close_slot(self):
        """Close the loading screen"""
        if not self.is_destroyed:
            self.stop_animation = True
            self.is_destroyed = True
            self.close()
    
    def update_progress(self, value: int, status_text: str = ""):
        """Update the progress of the loading screen
        
        Args:
            value: Progress value (0-100)
            status_text: Status text to display
        """
        if not self.is_destroyed and not self.stopped:
            self.updateProgressSignal.emit(value, status_text)
    
    def close_screen(self):
        """Close the loading screen"""
        if not self.is_destroyed and not self.stopped:
            self.stopped = True
            self.closeSignal.emit()


# Standalone test function
def show_loading_screen():
    """Show the loading screen as a standalone application"""
    # Ensure QApplication exists
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    loading_screen = PyQtLoadingScreen(title="Kingdom AI System")
    loading_screen.show()
    
    # Demo updates
    def update_demo():
        for i in range(0, 101, 10):
            if loading_screen.is_destroyed:
                break
            loading_screen.update_progress(i, f"Initializing components... {i}%")
            time.sleep(0.5)
        
        # Close after completion
        if not loading_screen.is_destroyed:
            loading_screen.close_screen()
    
    # Start demo updates in thread
    threading.Thread(target=update_demo).start()
    
    # Start event loop
    return app.exec()


# Run standalone if this script is executed directly
if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(level=logging.INFO)
    
    # Show the loading screen
    sys.exit(show_loading_screen())
