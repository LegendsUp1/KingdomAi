from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Loading Screen for Kingdom AI

This module provides a bridge to the PyQt6-based loading screen for the Kingdom AI system
that displays initialization progress and status updates with animated elements.

NOTE: This module eliminates all Tkinter dependencies and redirects all calls 
to the PyQt6-based implementation in loading_screen2_pyqt.py.

Features:
- Advanced cyberpunk styling with animated RGB effects
- Real-time component tracking via event bus
- Particle animations with visual feedback
- Seamless transition to main application after loading
- Strict enforcement of Redis Quantum Nexus connectivity (no fallbacks)
- Real-time update of ThothConnector, Redis Quantum Nexus, and API key loading status
"""

import os
import sys
import logging
import threading
import time
from datetime import datetime
import traceback
from typing import Optional, Dict, List, Any, Union, Callable

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the PyQt6 loading screen implementation
try:
    from gui.loading_screen2_pyqt import (
        create_loading_screen, update_loading_progress, update_system_status,
        update_redis_status, update_thoth_status, update_api_keys_status,
        register_component, initialize_component, start_component,
        transition_to_main_window, close_loading_screen, complete_loading
    )
    pyqt6_available = True
except ImportError:
    logger.error("PyQt6 loading screen not available. System halting.")
    raise ImportError("PyQt6 loading screen is required for Kingdom AI system.")

# Global loading screen instance - managed by loading_screen2_pyqt.py now
_active_loading_screen = None

# Bridge to PyQt6 implementation
def show_loading_screen(parent=None, title="Kingdom AI", width=700, height=500, event_bus=None):
    """Show loading screen for the Kingdom AI system
    
    Args:
        parent: Parent window
        title: Window title
        width: Window width
        height: Window height
        event_bus: Event bus for real-time updates
    
    Returns:
        Loading screen instance
    """
    try:
        global _active_loading_screen
        
        if _active_loading_screen is not None:
            logger.info("Reusing existing loading screen")
            return _active_loading_screen
            
        logger.info(f"Creating new PyQt6 loading screen: {title} ({width}x{height})")
        _active_loading_screen = create_loading_screen(
            title=title,
            width=width,
            height=height,
            event_bus=event_bus
        )
        
        return _active_loading_screen
    except Exception as e:
        logger.critical(f"Failed to create PyQt6 loading screen: {e}")
        logger.critical(traceback.format_exc())
        # No fallback to dummy implementation - system must halt on critical failure
        raise
    

        self.status_label = None
        self.progress_bar = None
        self.thoth_status_label = None
        self.redis_status_label = None
        self.api_status_label = None
        
        # Only create Tkinter elements if we're in a GUI environment
        if tkinter_available:
            try:
                # Create the root window if not provided
                if parent is None:
                    self.root = tk.Tk()
                    self.root.withdraw()  # Hide initially
                else:
                    self.root = tk.Toplevel(parent)
                    self.root.withdraw()  # Hide initially
                
                # Configure progress and status variables
                self.progress_var = progress_var if progress_var is not None else tk.DoubleVar(value=0.0)
                self.status_var = status_var if status_var is not None else tk.StringVar(value="Initializing...")
                
                # Component-specific status variables
                self.thoth_status_var = tk.StringVar(value="ThothAI: Waiting...")
                self.redis_status_var = tk.StringVar(value="Redis Nexus: Waiting...")
                self.api_keys_status_var = tk.StringVar(value="API Keys: Waiting...")
                
                # Configure the window
                self.root.title(title)
                self.root.protocol("WM_DELETE_WINDOW", self._on_close)  # Handle close button
                
                # Position window in center of screen
                self._center_on_screen()
                
                # Set up UI elements
                self._setup_ui()
                
                # Set up event handlers
                self._setup_event_handlers()
            except Exception as e:
                logger.error(f"Error configuring window: {e}")
                logger.error(traceback.format_exc())
                self.root = None
        else:
            # Use dummy variables for non-GUI environment
            self.progress_var = DummyVar(value=0.0)

def update_system_status(message):
    """Update the system status"""
    update_system_status(message)

def update_redis_status(status, message=""):
    """Update the Redis connection status"""
    update_redis_status(status, message)

def update_thoth_status(status, message=""):
    """Update the ThothConnector status"""
    update_thoth_status(status, message)

def update_api_keys_status(status, message=""):
    """Update the API keys loading status"""
    update_api_keys_status(status, message)

def register_component(component_name):
    """Register a component"""
    register_component(component_name)

def initialize_component(component_name):
    """Initialize a component"""
    initialize_component(component_name)

def start_component(component_name):
    """Start a component"""
    start_component(component_name)

def close_loading_screen():
    """Close the loading screen"""
    close_loading_screen()

def complete_loading():
    """Signal that loading is complete"""
    complete_loading()

def transition_to_main_window(callback=None, delay=7):
    """Transition from loading screen to main window with animation.
    
    Args:
        callback: Function to call after transition
        delay: Delay in seconds before transition
    """
    try:
        # In the new PyQt6 implementation, transition_to_main_window expects a window object
        # Here we maintain compatibility with older code that passes a callback function
        if callback:
            # Wrap the callback in a QTimer to ensure it's called after transition
            from PyQt6.QtCore import QTimer
            complete_loading()
            # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
            timer_manager = get_qt_timer_manager()
            timer.setSingleShot(True)
            timer.timeout.connect(callback)
            timer.start(delay * 1000)  # Convert to milliseconds
        else:
            complete_loading()
    except Exception as e:
        logger.critical(f"Error in transition to main window: {e}")
        logger.critical(traceback.format_exc())
        raise
