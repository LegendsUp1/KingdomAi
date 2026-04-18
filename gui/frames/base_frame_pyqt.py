#!/usr/bin/env python3
"""
Kingdom AI - PyQt6 Base Frame

This module provides the PyQt6 base frame for all Kingdom AI GUI components.
It implements futuristic styling with animated RGB borders and glowing elements.
"""

import os
import time
import logging
import traceback
import asyncio
from typing import Any, Dict, Optional, Union, Callable
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QTextEdit, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, pyqtSlot, QObject, QVariant
from PyQt6.QtGui import QColor, QPalette, QBrush, QLinearGradient
from ..kingdom_style_pyqt import RGBBorderFrame, GlowButton, KingdomStyles, rgb_animation_manager
from core.event_bus_wrapper import get_event_bus_wrapper, sync_method

class BaseFrame(QFrame):
    """Base class for all GUI frames in the Kingdom AI application using PyQt6.
    
    Provides common functionality for all frames including:
    - Event subscription management
    - Status updates
    - Logging
    - Real-time data updates
    - UI refresh controls
    """
    
    # Define signals for thread-safe GUI updates
    status_updated = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    error_occurred = pyqtSignal(str)
    data_received = pyqtSignal(object)
    
    def __init__(self, parent, event_bus=None, config_manager=None, name=None, api_key_connector=None, **kwargs):
        """Initialize base frame.
        
        Args:
            parent: The parent widget
            event_bus: The event bus for frame to communicate with other components
            config_manager: Configuration manager for frame settings
            name: Optional name for the frame
            api_key_connector: Connector for API keys management
        """
        # Extract style kwargs or use defaults
        bg_color = kwargs.pop('bg', KingdomStyles.COLORS["frame_bg"])
        border_width = kwargs.pop('border_width', 3)
        corner_radius = kwargs.pop('corner_radius', 10)
        
        # Initialize basic frame
        super().__init__(parent)
        
        # Set background color
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(bg_color))
        self.setPalette(palette)
        
        # Basic frame attributes
        self.parent = parent
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.api_key_connector = api_key_connector
        
        # Set frame name, defaulting to class name if not provided
        self.name = name if name else self.__class__.__name__.lower().replace("frame", "").strip()
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        
        # Create animated RGB border frame as the main container
        self.rgb_frame = RGBBorderFrame(
            self, 
            border_width=border_width,
            corner_radius=corner_radius,
            bg_color=bg_color
        )
        self.main_layout.addWidget(self.rgb_frame)
        
        # Set the inner content frame that child classes should use
        self.content_frame = self.rgb_frame.inner_frame
        
        # Set the border color based on component type
        self._set_component_color()
        
        # Set up logger
        if self.name:
            self.logger = logging.getLogger(f"gui.frames.{self.name}")
        else:
            self.logger = logging.getLogger("gui.frames.baseframe")
        
        # Status variables and widgets
        self.status_text = "Initializing..."
        self.progress_value = 0
        self._create_status_bar()  # Create the status bar with labels and progress bar
        
        # Data update tracking
        self.update_counts = {}
        self.data_cache = {}
        self.last_data_update = {}
        self.last_update_time = time.time()
        
        # Connect signals to slots
        self.status_updated.connect(self._on_status_updated)
        self.progress_updated.connect(self._on_progress_updated)
        self.error_occurred.connect(self._on_error_occurred)
        self.data_received.connect(self._on_data_received)
        
        # Initialize event handlers
        self.event_handlers = {}
        
        # Register for events if we have an event bus
        self._register_event_handlers()
    
    def set_event_bus(self, event_bus):
        """Set or update the event bus for this frame.
        
        Args:
            event_bus: The event bus to use
        """
        self.event_bus = event_bus
        self._register_event_handlers()
        self.logger.info(f"Event bus updated for {self.name} frame")
    
    async def initialize(self):
        """Initialize the frame asynchronously.
        
        This method ensures all frame components are properly loaded and rendered.
        It should be overridden by subclasses to initialize specific components.
        
        Returns:
            bool: Success status
        """
        try:
            self.logger.info(f"Initializing {self.name} frame")
            self.update_status("Initializing...")
            
            # Create the main layout - subclasses should override this
            self._create_layout()
            
            # Create log display if debug mode is enabled
            debug_mode = os.environ.get("KINGDOM_DEBUG", "False").lower() in ("true", "1", "yes")
            if debug_mode:
                self.create_log_display()
                
            # Register frame-specific events
            if self.event_bus:
                self._register_frame_specific_events()
                self._subscribe_to_events()
                
            # Call refresh to ensure all components are properly rendered
            self.refresh()
            
            # Update status to show initialization is complete
            self.update_status(f"{self.name.title()} ready", progress=100)
            
            # Try to run an asyncio task
            try:
                # Schedule this frame to be refreshed periodically
                if hasattr(self, '_schedule_periodic_refresh'):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self._schedule_periodic_refresh())
                    else:
                        # No running loop, create a separate refresh mechanism using QTimer
                        self._setup_refresh_timer()
            except Exception as refresh_err:
                self.logger.error(f"Error setting up refresh task: {refresh_err}")
                
            return True
        except Exception as e:
            self.logger.error(f"Error initializing {self.name} frame: {e}")
            self.logger.error(traceback.format_exc())
            self.update_status(f"Error: {str(e)}", progress=0)
            return False
            
    def _setup_refresh_timer(self):
        """Set up a QTimer for periodic refresh when asyncio is not available."""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
            
    def _register_frame_specific_events(self):
        """Register events specific to this frame type.
        Override this in subclasses to add frame-specific event subscriptions.
        """
        pass
        
    def _register_event_handlers(self):
        """Register all event handlers with the event bus.
        This is called during initialization and when the event bus is updated.
        """
        if not self.event_bus:
            self.logger.warning("No event bus available, skipping event handler registration")
            return
            
        try:
            # Common event handlers
            self._safe_subscribe("system.status", self.handle_system_status)
            self._safe_subscribe("gui.update", self.handle_gui_update)
            
            # Register dynamic event handlers based on frame name
            data_event = f"{self.name}.data"
            status_event = f"{self.name}.status"
            error_event = f"{self.name}.error"
            
            self._safe_subscribe(data_event, self.handle_event_data)
            self._safe_subscribe(status_event, self.update_status)
            self._safe_subscribe(error_event, self.show_error)
            
            # Register any additional async event handlers
            self._register_async_handlers()
            
            self.logger.debug(f"Registered event handlers for {self.name} frame")
            
        except Exception as e:
            self.logger.error(f"Error registering event handlers: {e}")
            self.logger.error(traceback.format_exc())
    
    def _register_async_handlers(self):
        """Register asynchronous event handlers."""
        # Override in subclasses if needed
        pass
    
    def _subscribe_to_events(self):
        """Subscribe to events. To be overridden by subclasses."""
        # This method should be overridden by subclasses to subscribe to specific events
        if not self.event_bus:
            self.logger.warning("No event bus available, skipping event subscription")
            return
            
        # Default implementation subscribes to general system events
        self._safe_subscribe("system.ready", self.handle_system_status)
        self._safe_subscribe("system.error", self.handle_system_status)
    
    def _safe_subscribe(self, event_name: str, handler: Callable):
        """Safely subscribe to an event with error handling"""
        try:
            if self.event_bus:
                # 2025 CRITICAL FIX: Proper async handling for EventBus.subscribe
                import asyncio
                
                def safe_async_subscribe():
                    """2025 pattern: Safe async subscription"""
                    try:
                        loop = asyncio.get_running_loop()
                        if loop and not loop.is_closed():
                            # Use sync_method if available to handle async/sync compatibility
                            wrapped_handler = sync_method(handler)
                            # 2025 FIX: Use synchronous subscription to prevent task conflicts
                            if hasattr(self.event_bus, 'subscribe_sync'):
                                self.event_bus.subscribe_sync(event_name, wrapped_handler)
                                self.logger.debug(f"Subscribed to {event_name} synchronously")
                            else:
                                # Store for deferred processing
                                if not hasattr(self, '_deferred_subscriptions'):
                                    self._deferred_subscriptions = []
                                self._deferred_subscriptions.append((event_name, wrapped_handler))
                                self.logger.debug(f"Deferred subscription to {event_name}")
                        else:
                            self.logger.warning(f"No event loop for subscription to {event_name}")
                    except RuntimeError:
                        self.logger.warning(f"No event loop available for {event_name} subscription")
                    except Exception as e:
                        self.logger.error(f"Error in async subscription to {event_name}: {e}")
                
                safe_async_subscribe()
        except Exception as e:
            self.logger.error(f"Failed to subscribe to {event_name}: {e}")
    
    def _create_layout(self):
        """Create the base frame layout. To be overridden by subclasses."""
        # Default implementation creates an empty layout
        layout = QVBoxLayout(self.content_frame)
        self.content_frame.setLayout(layout)
    
    def _set_component_color(self):
        """Set the border color based on component type."""
        # Different component types get different border colors
        if "mining" in self.name:
            self.rgb_frame.set_color_scheme("mining")
        elif "trading" in self.name:
            self.rgb_frame.set_color_scheme("trading")
        elif "wallet" in self.name:
            self.rgb_frame.set_color_scheme("wallet")
        elif "blockchain" in self.name:
            self.rgb_frame.set_color_scheme("blockchain")
    
    def create_button(self, text, command, parent=None, **kwargs):
        """Create a standard button with glowing effect.
        
        Args:
            text: Button text
            command: Button command
            parent: Parent widget (defaults to self.content_frame)
            **kwargs: Additional keyword arguments for the button
            
        Returns:
            Button widget with glowing effect
        """
        if parent is None:
            parent = self.content_frame
            
        # Extract style options
        glow_color = kwargs.pop("glow_color", KingdomStyles.COLORS["glow"])
        hover_color = kwargs.pop("hover_color", KingdomStyles.COLORS["hover"])
        
        # Create the glowing button
        button = GlowButton(
            parent,
            text=text,
            clicked_callback=command,
            glow_color=glow_color,
            hover_color=hover_color,
            **kwargs
        )
        
        return button
    
    def _create_status_bar(self):
        """Create status bar at the bottom of the frame."""
        # Status bar container
        self.status_bar = QFrame(self)
        self.status_bar.setObjectName("status_bar")
        self.status_bar.setMinimumHeight(30)
        self.status_bar.setMaximumHeight(30)
        
        # Status bar layout
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(5, 0, 5, 0)
        
        # Status label
        self.status_label = QLabel(self.status_text, self.status_bar)
        status_layout.addWidget(self.status_label, 1)
        
        # Progress bar
        self.progress_bar = QProgressBar(self.status_bar)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(self.progress_value)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMaximumWidth(200)
        status_layout.addWidget(self.progress_bar)
        
        # Add to main layout
        self.main_layout.addWidget(self.status_bar)
    
    def show_error(self, message):
        """Show error message.
        
        Args:
            message: Error message to display
        """
        if isinstance(message, dict) and 'message' in message:
            message = message['message']
            
        try:
            # Log the error
            self.logger.error(f"Error: {message}")
            
            # Update status to show error
            self.update_status(f"Error: {message}", progress=0)
            
            # Emit error signal for thread safety
            self.error_occurred.emit(str(message))
            
            return True
        except Exception as e:
            self.logger.error(f"Error showing error message: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    @pyqtSlot(str)
    def _on_error_occurred(self, message):
        """Handle error signal."""
        QMessageBox.critical(self, "Error", message)
    
    def create_log_display(self):
        """Create log display frame."""
        try:
            # Create a text edit for displaying logs
            self.log_display = QTextEdit(self.content_frame)
            self.log_display.setReadOnly(True)
            self.log_display.setMaximumHeight(100)
            
            # Get the layout
            layout = self.content_frame.layout()
            if layout is not None:
                layout.addWidget(self.log_display)
            
            # Method to add log entry
            def add_log_entry(message):
                self.log_display.append(f"{datetime.now().strftime('%H:%M:%S')} - {message}")
                # Scroll to bottom
                scrollbar = self.log_display.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            
            # Store the method for use elsewhere
            self.add_log_entry = add_log_entry
            
            self.logger.info("Log display created")
            return True
        except Exception as e:
            self.logger.error(f"Error creating log display: {e}")
            return False
    
    def update_status(self, status_text, progress=None):
        """Update frame status.
        
        Args:
            status_text: Status text to display
            progress: Optional progress percentage (0-100)
        """
        # Use signal for thread-safe updates
        if isinstance(status_text, dict):
            if 'status' in status_text:
                status_text = status_text['status']
            if 'progress' in status_text and progress is None:
                progress = status_text['progress']
        
        try:
            # Set current values
            self.status_text = str(status_text)
            
            # Emit signals for thread-safe updates
            self.status_updated.emit(self.status_text)
            
            if progress is not None:
                self.progress_value = int(progress)
                self.progress_updated.emit(self.progress_value)
            
            # Also log the status update
            self.logger.info(f"Status: {status_text} ({progress if progress is not None else 'N/A'}%)")
            
            # Add to log display if available
            if hasattr(self, 'add_log_entry') and callable(self.add_log_entry):
                self.add_log_entry(f"Status: {status_text}")
                
            return True
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    @pyqtSlot(str)
    def _on_status_updated(self, status_text):
        """Handle status update signal."""
        self.status_label.setText(status_text)
    
    @pyqtSlot(int)
    def _on_progress_updated(self, progress_value):
        """Handle progress update signal."""
        self.progress_bar.setValue(progress_value)
    
    def update_display(self, data):
        """Update display with new data.
        
        Args:
            data: Data to update display with
        """
        try:
            # Emit signal for thread-safe update
            self.data_received.emit(data)
            return True
        except Exception as e:
            self.logger.error(f"Error updating display with data: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    @pyqtSlot(object)
    def _on_data_received(self, data):
        """Handle data received signal."""
        try:
            # Handle dict data
            if isinstance(data, dict):
                # Update data cache
                self.data_cache.update(data)
                
            # Default implementation logs the data and triggers a refresh
            self.logger.debug(f"Received data update: {len(data) if isinstance(data, dict) else 'non-dict data'}")
            self.refresh()
            
            # Update the last data update timestamp
            self.last_update_time = time.time()
        except Exception as e:
            self.logger.error(f"Error processing received data: {e}")
            self.logger.error(traceback.format_exc())
    
    def refresh(self):
        """Force refresh of the frame."""
        try:
            # Update the frame
            self.repaint()
            return True
        except Exception as e:
            self.logger.error(f"Error refreshing frame: {e}")
            return False
            
    def handle_system_status(self, event_data):
        """Handle system status events.
        
        Args:
            event_data: Event data containing status information
        """
        if not event_data:
            return
            
        if isinstance(event_data, dict) and 'status' in event_data:
            status = event_data['status']
            self.update_status(f"System: {status}")
            
    def handle_gui_update(self, event_data):
        """Handle GUI update events.
        
        Args:
            event_data: Event data containing update information
        """
        if not isinstance(event_data, dict):
            return
            
        # Update status if provided
        if 'status' in event_data:
            self.update_status(event_data['status'])
            
        # Refresh the UI
        self.refresh()

    def handle_event_data(self, event_data):
        """Handle event data for real-time updates.
        
        This method can be overridden by subclasses for custom event handling.
        
        Args:
            event_data: Data from an event
            
        Returns:
            bool: True if handled successfully
        """
        try:
            # Default implementation updates display with event data
            self.update_display(event_data)
            return True
        except Exception as e:
            self.logger.error(f"Error handling event data: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def register_event_handlers(self) -> None:
        """
        Register event handlers for base frame events.
        """
        if not self.event_bus:
            self.logger.warning("No event bus available for registration")
            return
        
        # Register event handlers synchronously to avoid coroutine warnings
        event_handlers = [
            ("system.ready", self._handle_system_ready),
            ("system.error", self._handle_system_error),
        ]
        
        for event_name, handler in event_handlers:
            try:
                # Synchronous subscription without await
                if hasattr(self.event_bus, 'subscribe_sync'):
                    self.event_bus.subscribe_sync(event_name, handler)
                else:
                    self.event_bus.subscribe(event_name, handler)
            except Exception as e:
                self.logger.error(f"Error registering handler for {event_name}: {str(e)}")
    
    def _handle_system_ready(self, event_data=None):
        """Handle system ready event."""
        self.update_status("System ready", progress=100)
    
    def _handle_system_error(self, event_data=None):
        """Handle system error event."""
        if isinstance(event_data, dict) and 'message' in event_data:
            self.show_error(event_data['message'])
        else:
            self.show_error("System error occurred")
