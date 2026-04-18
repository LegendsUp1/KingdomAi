#!/usr/bin/env python3
"""
Kingdom AI - Base Frame

This module provides the base frame for all Kingdom AI GUI components.
It implements futuristic styling with animated RGB borders and glowing elements.
"""

import os
import time
import logging
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import traceback
import asyncio
from ..kingdom_style import RGBBorderFrame, GlowButton, KingdomStyles, rgb_animation_manager
from typing import Any, Dict, Optional, Union, Callable
# TEMP FIX: event_bus_wrapper import hangs
try:
    from core.event_bus_wrapper import get_event_bus_wrapper, sync_method
except ImportError:
    # Fallback implementations
    def get_event_bus_wrapper():
        return None
    def sync_method(func):
        return func

class BaseFrame(tk.Frame):
    """Base class for all GUI frames in the Kingdom AI application.
    
    Provides common functionality for all frames including:
    - Event subscription management
    - Status updates
    - Logging
    - Real-time data updates
    - UI refresh controls
    """
    
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
        super().__init__(parent, bg=bg_color, **kwargs)
        # Don't use any geometry manager here - let child classes decide how to place themselves
        # This fixes issues with mixing grid and pack in the same container
        
        # Basic frame attributes
        self.parent = parent
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.api_key_connector = api_key_connector
        
        # Set frame name, defaulting to class name if not provided
        self.name = name if name else self.__class__.__name__.lower().replace("frame", "").strip()
        
        # Create animated RGB border frame as the main container
        self.rgb_frame = RGBBorderFrame(
            self, 
            border_width=border_width,
            corner_radius=corner_radius,
            bg=bg_color
        )
        self.rgb_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Set the inner content frame that child classes should use
        self.content_frame = self.rgb_frame.inner_frame
        
        # Set the border color based on component type
        self._set_component_color()
        
        # Set up logger
        if self.name:
            self.logger = logging.getLogger(f"gui.frames.{self.name}")
        else:
            self.logger = logging.getLogger("gui.frames.baseframe")
        
        # Status variables
        self.status_var = tk.StringVar(value="Initializing...")
        self.progress_var = tk.IntVar(value=0)  # Progress variable for progress bar
        self.last_update = time.time()
        self.last_update_time = time.time()
        
        # Data update tracking
        self.update_counts = {}
        self.data_cache = {}
        self.last_data_update = {}
        
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
            
            # Ensure event bus is connected
            if not self.event_bus:
                self.logger.warning(f"No event bus during initialization of {self.name}")
            else:
                # Subscribe to relevant events
                self._subscribe_to_events()
            
            # Create basic layout
            self._create_layout()
            
            # Ensure the frame is properly rendered
            if hasattr(self, 'update'):
                self.update()
                
            # Force update content frame if it exists
            if hasattr(self, 'content_frame') and hasattr(self.content_frame, 'update'):
                self.content_frame.update()
            
            # Update status
            self.status_var.set("Initialized")
            self.progress_var.set(100)
            
            # Register for additional events if needed by subclass
            self._register_frame_specific_events()
            
            self.initialized = True
            self.status = "Ready"
            
            # Publish initialization complete event
            if hasattr(self, 'event_bus') and self.event_bus is not None:
                await self.event_bus.publish(f"gui.{self.name.lower()}.initialized", {
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                })
            else:
                self.logger.error("Event bus not available in base frame, cannot publish initialized event")
            
            self.logger.info(f"{self.name} frame initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing {self.name} frame: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
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
            self.logger.warning(f"No event bus available for {self.name}. Event handling will be limited.")
            return
            
        try:
            # Use sync subscribe if available
            if hasattr(self.event_bus, 'subscribe_sync'):
                self.event_bus.subscribe_sync("system.status", self.handle_system_status)
                self.event_bus.subscribe_sync("gui.update", self.handle_gui_update)
                self.logger.info(f"Subscribed {self.name} to events via sync bus")
            # Fall back to regular subscribe for async event bus
            elif hasattr(self.event_bus, 'subscribe'):
                # Create an async wrapper to handle the subscription properly
                async def _register_async_handlers():
                    if self.event_bus:
                        await self.event_bus.subscribe("system.status", self.handle_system_status)
                        await self.event_bus.subscribe("gui.update", self.handle_gui_update)
                        self.logger.info(f"Subscribed {self.name} to events via async bus")
                    
                # Schedule the async registration
                asyncio.create_task(_register_async_handlers())
            else:
                self.logger.warning(f"Event bus for {self.name} has no subscribe method. Event handling will be limited.")
        except Exception as e:
                self.logger.error(f"Error subscribing to events: {str(e)}")
        
        # Data variables
        self.data = {}
        self.raw_data_var = tk.StringVar(value="")
        
        # UI components
        self.frame = self  # For backward compatibility
        
        # Create status bar at the bottom of the content frame
        self._create_status_bar()
        
        # Create status label with glowing effect
        self.status_label = tk.Label(
            self.content_frame, 
            textvariable=self.status_var,
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["primary"],
            font=("Arial", 9)
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)
        
        # Create log display for messages
        self.create_log_display()
        
        # Data storage for real-time updates
        self.data = {}
        
        # Flag to track initialization state
        self.initialized = False
        
        # Status tracking
        self.status = "Initializing"
        
        # Component-specific settings
        self.settings = {}
        
        self.logger.info(f"Created {self.name} frame")
    
    # Note: The initialize method has been merged with the previous implementation above
    
    def _subscribe_to_events(self):
        """Subscribe to events. To be overridden by subclasses."""
        if not self.event_bus:
            self.logger.warning(f"{self.name} frame has no event bus")
            return
            
        # Common event subscriptions
        self._safe_subscribe("system.status", self.handle_system_status)
        self._safe_subscribe("gui.update", self.handle_gui_update)
        
        self.logger.info(f"{self.name} frame subscribed to events")
        
    def _safe_subscribe(self, event_name: str, handler: Callable) -> None:
        """Safely subscribe to an event with error handling"""
        try:
            if hasattr(self, 'event_bus') and self.event_bus and hasattr(self.event_bus, 'subscribe'):
                if hasattr(self.event_bus, 'subscribe_sync'):
                    self.event_bus.subscribe_sync(event_name, handler)
                else:
                    self.event_bus.subscribe(event_name, handler)
                logging.debug(f"Subscribed to {event_name} in {self.__class__.__name__}")
            else:
                logging.warning(f"No event bus available for {event_name} in {self.__class__.__name__}")
        except Exception as e:
            logging.error(f"Error subscribing to {event_name} in {self.__class__.__name__}: {e}")
    
    def _create_layout(self):
        """Create the base frame layout. To be overridden by subclasses."""
        # Placeholder for subclasses to implement
        pass
        
    def _set_component_color(self):
        """Set the border color based on component type."""
        if not hasattr(self, 'rgb_frame') or not hasattr(self.rgb_frame, '_update_border_color'):
            return
            
        # Determine color based on frame name
        component_color = KingdomStyles.get_component_color(self.name)
        
        # Apply color to RGB border
        self.rgb_frame._update_border_color(component_color)
        
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
        
        # Use RGB glowing button instead of standard button
        glow_color = kwargs.pop('glow_color', KingdomStyles.COLORS["primary"])
        button = GlowButton(
            parent, 
            text=text, 
            command=command,
            glow_color=glow_color,
            **kwargs
        )
        return button
    
    def _create_status_bar(self):
        """Create status bar at the bottom of the frame."""
        status_frame = tk.Frame(
            self.content_frame, 
            bg=KingdomStyles.COLORS["panel_bg"],
            height=25
        )
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)
            
        # Create a label for the status
        self.status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            bg=KingdomStyles.COLORS["panel_bg"],
            fg=KingdomStyles.COLORS["primary"],
            font=("Arial", 9)
        )
        self.status_label.pack(side=tk.LEFT, padx=5)
            
    def show_error(self, message):
        """Show error message.
        
        Args:
            message: Error message to display
        """
        self.logger.error(message)
        self.update_status(f"Error: {message}")
        
        # Change status color to indicate error
        if hasattr(self, 'status_label'):
            self.status_label.config(fg=KingdomStyles.COLORS["danger"])
            
        # Flash the border in danger color
        if hasattr(self, 'rgb_frame') and hasattr(self.rgb_frame, '_update_border_color'):
            current_color = self.rgb_frame.current_rgb
            self.rgb_frame._update_border_color(KingdomStyles.COLORS["danger"])
            
            # Schedule restoration of original color
            self.after(2000, lambda: self.rgb_frame._update_border_color(current_color))
            
    def create_log_display(self):
        """Create log display frame."""
        # Create frame for log display with RGB border
        self.log_frame = RGBBorderFrame(
            self.content_frame,
            border_width=2,
            corner_radius=8,
            bg=KingdomStyles.COLORS["panel_bg"]
        )
        self.log_frame.pack(side=tk.BOTTOM, fill=tk.X, expand=False, padx=5, pady=5)
        
        # Create text widget with scrollbar
        self.log_display = tk.Text(self.log_frame.inner_frame, height=5, width=50, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(self.log_frame.inner_frame, command=self.log_display.yview)
        self.log_display.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
    def update_status(self, status_text, progress=None):
        """Update frame status.
        
        Args:
            status_text: Status text to display
            progress: Optional progress percentage (0-100)
        """
        try:
            # Update status variables
            self.status_var.set(status_text)
            
            # Update progress if provided
            if progress is not None:
                self.progress_var.set(progress)
            
            # Update last update time
            self.last_update = time.time()
            
            # Ensure status label has the correct color based on progress
            if progress is not None:
                try:
                    progress_val = float(progress)
                except (TypeError, ValueError):
                    progress_val = 0.0
                if progress_val >= 100:
                    self.status_label.config(fg=KingdomStyles.COLORS["success"])
                elif progress_val >= 50:
                    self.status_label.config(fg=KingdomStyles.COLORS["info"])
                else:
                    self.status_label.config(fg=KingdomStyles.COLORS["primary"])
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            
    def update_display(self, data):
        """Update display with new data.
        
        Args:
            data: Data to update display with
        """
        try:
            # Handle dict data
            if isinstance(data, dict):
                # Update data cache
                self.data_cache.update(data)
                
                # Update raw data variable
                if hasattr(self, 'raw_data_var') and isinstance(self.raw_data_var, tk.Variable):
                    self.raw_data_var.set(str(data))
            else:
                # Handle non-dict data
                if hasattr(self, 'raw_data_var') and isinstance(self.raw_data_var, tk.Variable):
                    self.raw_data_var.set(str(data))
            
            # Default implementation logs the data and triggers a refresh
            self.logger.debug(f"Received data update: {len(data) if isinstance(data, dict) else 'non-dict data'}")
            self.refresh()
            
            # Update the last data update timestamp
            self.last_update_time = time.time()
            return True
        except Exception as e:
            self.logger.error(f"Error updating display with data: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def refresh(self):
        """Force refresh of the frame."""
        try:
            # Update the frame
            if hasattr(self, 'update_idletasks'):
                self.update_idletasks()
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
            
        if 'status' in event_data:
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
