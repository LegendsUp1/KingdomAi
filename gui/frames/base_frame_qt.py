"""
Base Frame for PyQt6

This module provides the base frame for all PyQt6 GUI components in the Kingdom AI application.
"""

import os
import sys
import logging
import asyncio
from typing import Any, Dict, Optional, Union, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPalette, QFont, QFontMetrics

from core.event_bus import EventBus
from utils.logger import get_logger

class BaseFrameQt(QFrame):
    """Base class for all PyQt6 frames in the Kingdom AI application.
    
    Provides common functionality for all frames including:
    - Event subscription management
    - Status updates
    - Logging
    - Real-time data updates
    - UI refresh controls
    """
    
    # Signal for status updates
    status_updated = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    
    def __init__(self, parent=None, event_bus: Optional[EventBus] = None, **kwargs):
        """Initialize the base frame.
        
        Args:
            parent: The parent widget
            event_bus: The event bus for inter-component communication
            **kwargs: Additional keyword arguments
        """
        super().__init__(parent)
        
        # Set frame properties
        self.setObjectName(self.__class__.__name__)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        
        # Store references
        self.parent_widget = parent
        self.event_bus = event_bus
        
        # Set up logger
        self.logger = get_logger(self.__class__.__name__)
        
        # Initialize state
        self.initialized = False
        self._status = "Initializing..."
        self._progress = 0
        
        # Initialize UI
        self.init_ui()
        
        # Initialize event handlers
        self._setup_event_handlers()
        
        # Mark as initialized
        self.initialized = True
        self.status = "Ready"
    
    def init_ui(self):
        """Initialize the user interface."""
        # Create main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # Create content frame (to be used by child classes)
        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("contentFrame")
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(5)
        
        self.main_layout.addWidget(self.content_frame)
    
    def _setup_event_handlers(self):
        """Set up event handlers."""
        if self.event_bus:
            # Connect to the event bus for updates
            pass  # Add event subscriptions as needed
    
    @property
    def status(self) -> str:
        """Get the current status."""
        return self._status
    
    @status.setter
    def status(self, value: str):
        """Set the status and emit the status_updated signal."""
        self._status = value
        self.status_updated.emit(value)
        self.logger.info(f"Status updated: {value}")
    
    @property
    def progress(self) -> int:
        """Get the current progress (0-100)."""
        return self._progress
    
    @progress.setter
    def progress(self, value: int):
        """Set the progress and emit the progress_updated signal."""
        self._progress = max(0, min(100, value))  # Clamp between 0-100
        self.progress_updated.emit(self._progress)
    
    def showEvent(self, event):
        """Handle show events."""
        super().showEvent(event)
        if not self.initialized:
            self.initialize_async()
    
    def initialize_async(self):
        """Initialize the frame asynchronously."""
        if not self.initialized:
            self.status = "Initializing..."
            asyncio.create_task(self._async_initialize())
    
    async def _async_initialize(self):
        """Perform asynchronous initialization tasks."""
        try:
            # Perform any async initialization here
            await asyncio.sleep(0.1)  # Simulate async work
            self.status = "Ready"
        except Exception as e:
            self.logger.error(f"Error during async initialization: {str(e)}")
            self.status = f"Error: {str(e)}"
    
    def cleanup(self):
        """Clean up resources."""
        self.logger.info("Cleaning up resources")
        # Add cleanup code as needed
    
    def closeEvent(self, event):
        """Handle close events."""
        self.cleanup()
        super().closeEvent(event)
