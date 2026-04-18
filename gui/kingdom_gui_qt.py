#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI GUI Qt Adapter
Provides a wrapper/adapter for existing KingdomGUI functionality using PyQt6.
This replaces the Tkinter-based kingdom_gui.py for the PyQt6 migration.
"""

import logging
import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QTimer

# Import the new PyQt6 main window
from gui.kingdom_main_window_qt import KingdomMainWindow

# Set up logger
logger = logging.getLogger("KingdomGUI")

class AsyncHelper(QObject):
    """Helper class to bridge between PyQt and asyncio event loops."""
    
    def __init__(self):
        super().__init__()
        self._event_loop = None
        self._tasks = set()
    
    def setup_event_loop(self):
        """Set up the asyncio event loop."""
        self._event_loop = asyncio.get_event_loop()
        if self._event_loop.is_closed():
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
        return self._event_loop
    
    def create_task(self, coro):
        """Create and track an asyncio task."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

class KingdomGUI:
    """
    Adapter/wrapper class for KingdomMainWindow to provide KingdomGUI functionality.
    This resolves compatibility issues with existing code expecting KingdomGUI methods.
    """
    
    def __init__(self, event_bus=None):
        """Initialize the KingdomGUI adapter with the underlying PyQt6 GUI."""
        # Store references to components and state
        self.event_bus = event_bus
        self.initialized = False
        self.main_window = None
        self.app = None
        
        # Set up asyncio helper
        self._async_helper = AsyncHelper()
        self._event_loop = self._async_helper.setup_event_loop()
        
        # Initialize logger
        self.logger = logging.getLogger("KingdomGUI")
        self.logger.info("KingdomGUI Qt adapter initialized")
    
    async def initialize(self):
        """Initialize the GUI components asynchronously."""
        self.logger.info("Initializing KingdomGUI Qt adapter")
        try:
            # Ensure we have a QApplication instance
            self.app = QApplication.instance()
            if not self.app:
                self.app = QApplication(sys.argv)
            
            # Create the main window
            self.main_window = KingdomMainWindow(event_bus=self.event_bus)
            
            # Initialize the main window
            initialization_result = self.main_window.initialize()
            
            if initialization_result:
                self.main_window.show()
                self.initialized = True
                self.logger.info("KingdomGUI Qt adapter initialization complete")
                return True
            else:
                self.logger.error("Failed to initialize KingdomMainWindow")
                return False
        except Exception as e:
            self.logger.critical(f"Failed to initialize KingdomGUI Qt adapter: {e}")
            return False
    
    def create_loading_screen(self):
        """Create a loading screen (transitional method)."""
        self.logger.info("Loading screen functionality delegated to KingdomMainWindow")
        # This functionality is now handled by KingdomMainWindow
        pass
    
    def update_loading_progress(self, progress, message=None):
        """Update the loading progress (transitional method)."""
        if self.initialized and self.main_window:
            # Delegate to main window
            if hasattr(self.main_window, 'update_progress'):
                self.main_window.update_progress(progress, message)
        else:
            self.logger.warning("Cannot update loading progress: GUI not initialized")
    
    def show_main_window(self):
        """Show the main window."""
        if self.initialized and self.main_window:
            self.main_window.show()
            self.logger.info("Main window displayed")
        else:
            self.logger.warning("Cannot show main window: GUI not initialized")
    
    def update_status(self, message):
        """Update the status bar message."""
        if self.initialized and self.main_window:
            # Delegate to main window
            if hasattr(self.main_window, 'status_label'):
                self.main_window.status_label.setText(message)
                self.logger.debug(f"Status updated: {message}")
        else:
            self.logger.warning(f"Cannot update status: GUI not initialized. Message was: {message}")
    
    def show_error(self, title, message):
        """Show an error dialog."""
        if self.initialized and self.main_window:
            # Delegate to main window
            if hasattr(self.main_window, 'show_error'):
                self.main_window.show_error(title, message)
            else:
                self.logger.error(f"Error: {title} - {message}")
        else:
            self.logger.error(f"Cannot show error dialog: GUI not initialized. Error was: {title} - {message}")
    
    def start_event_loop(self):
        """Start the PyQt event loop."""
        if self.app:
            self.logger.info("Starting PyQt event loop")
            sys.exit(self.app.exec())
        else:
            self.logger.error("Cannot start event loop: No QApplication instance")
    
    def run_async_task(self, coro):
        """Run an async task in the event loop."""
        if self._event_loop:
            return self._async_helper.create_task(coro)
        else:
            self.logger.error("Cannot run async task: No event loop")
            return None
