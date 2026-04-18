"""
Status Bar for Kingdom AI GUI.

This module provides a status bar component for the Kingdom AI GUI,
displaying system status, notifications, and real-time information.
"""
import tkinter as tk
import time
from typing import Dict, Any, Optional, Callable, List, Tuple


class StatusBar(tk.Frame):
    """Status bar component for Kingdom AI GUI."""
    
    def __init__(self, master=None, **kwargs):
        """Initialize the status bar.
        
        Args:
            master: The parent widget.
            **kwargs: Additional keyword arguments for the Frame.
        """
        super().__init__(master, **kwargs)
        
        # Configure the frame
        self.configure(
            height=25,
            relief=tk.SUNKEN,
            borderwidth=1
        )
        
        # Create status message label
        self.status_message = tk.StringVar()
        self.status_message.set("Ready")
        
        self.status_label = tk.Label(
            self,
            textvariable=self.status_message,
            anchor=tk.W,
            padx=5
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Create component status indicators
        self.indicators = {}
        self.indicator_frame = tk.Frame(self)
        self.indicator_frame.pack(side=tk.RIGHT, padx=5)
        
        # Initialize with default indicators
        self._create_default_indicators()
        
        # Message queue for status updates
        self.message_queue = []
        self.current_message_id = None
        
        # Setup periodic refresh
        self._setup_refresh()
    
    def _create_default_indicators(self) -> None:
        """Create default system status indicators."""
        self.add_indicator("event_bus", "Event Bus", "gray")
        self.add_indicator("redis", "Redis", "gray")
        self.add_indicator("thoth", "ThothAI", "gray")
        self.add_indicator("trading", "Trading", "gray")
        self.add_indicator("blockchain", "Blockchain", "gray")
    
    def add_indicator(self, name: str, tooltip: str, color: str) -> None:
        """Add a status indicator to the status bar.
        
        Args:
            name: Unique name for the indicator.
            tooltip: Tooltip text for the indicator.
            color: Initial color for the indicator (green, yellow, red, gray).
        """
        indicator = tk.Canvas(self.indicator_frame, width=12, height=12, bd=0, highlightthickness=0)
        indicator.pack(side=tk.LEFT, padx=2)
        
        # Create the indicator circle
        circle_id = indicator.create_oval(2, 2, 10, 10, fill=color)
        
        # Store the indicator
        self.indicators[name] = {
            "widget": indicator,
            "circle_id": circle_id,
            "tooltip": tooltip,
            "color": color
        }
        
        # Add tooltip
        indicator.bind("<Enter>", lambda e, n=name: self._show_indicator_tooltip(n))
        indicator.bind("<Leave>", lambda e: self.status_message.set("Ready"))
    
    def _show_indicator_tooltip(self, name: str) -> None:
        """Show tooltip for an indicator.
        
        Args:
            name: Name of the indicator.
        """
        if name in self.indicators:
            tooltip = self.indicators[name]["tooltip"]
            color = self.indicators[name]["color"]
            status = "Unknown"
            
            if color == "green":
                status = "Connected"
            elif color == "yellow":
                status = "Connecting"
            elif color == "red":
                status = "Error"
            elif color == "gray":
                status = "Inactive"
            
            self.status_message.set(f"{tooltip}: {status}")
    
    def update_indicator(self, name: str, color: str, tooltip: Optional[str] = None) -> None:
        """Update a status indicator.
        
        Args:
            name: Name of the indicator to update.
            color: New color for the indicator.
            tooltip: Optional new tooltip text.
        """
        if name in self.indicators:
            indicator = self.indicators[name]
            indicator["color"] = color
            indicator["widget"].itemconfig(indicator["circle_id"], fill=color)
            
            if tooltip:
                indicator["tooltip"] = tooltip
    
    def set_status(self, message: str, duration: int = 5000) -> None:
        """Set the status message.
        
        Args:
            message: Status message to display.
            duration: Duration to display the message in milliseconds.
        """
        # Clear any existing message timer
        if self.current_message_id:
            self.after_cancel(self.current_message_id)
        
        # Set the new message
        self.status_message.set(message)
        
        # Set a timer to clear the message
        self.current_message_id = self.after(duration, self._reset_status)
    
    def _reset_status(self) -> None:
        """Reset the status message to default."""
        self.status_message.set("Ready")
        self.current_message_id = None
        
        # Show the next message in the queue if there is one
        if self.message_queue:
            next_message, duration = self.message_queue.pop(0)
            self.set_status(next_message, duration)
    
    def queue_status(self, message: str, duration: int = 5000) -> None:
        """Queue a status message to be displayed after the current one.
        
        Args:
            message: Status message to display.
            duration: Duration to display the message in milliseconds.
        """
        if not self.current_message_id:
            self.set_status(message, duration)
        else:
            self.message_queue.append((message, duration))
    
    def _setup_refresh(self) -> None:
        """Setup periodic refresh for the status bar."""
        self.after(1000, self._periodic_refresh)
    
    def _periodic_refresh(self) -> None:
        """Periodically refresh the status bar."""
        # Schedule the next refresh
        self.after(1000, self._periodic_refresh)


# Create a StatusBar instance (this will be used elsewhere)
status_bar = None


def create_status_bar(master) -> StatusBar:
    """Create a status bar instance.
    
    Args:
        master: The parent widget.
        
    Returns:
        The created StatusBar instance.
    """
    global status_bar
    status_bar = StatusBar(master)
    return status_bar


def get_status_bar() -> Optional[StatusBar]:
    """Get the current status bar instance.
    
    Returns:
        The current StatusBar instance or None if not created.
    """
    global status_bar
    return status_bar
