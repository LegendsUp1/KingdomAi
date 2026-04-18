"""
Tooltip Manager for Kingdom AI GUI.

This module provides tooltip functionality for the Kingdom AI GUI components,
enhancing user experience by displaying helpful information when hovering over UI elements.
"""
import tkinter as tk
from typing import Dict, Any, Optional


class TooltipManager:
    """Manages tooltips for the Kingdom AI GUI components."""
    
    def __init__(self):
        """Initialize the tooltip manager."""
        self.tooltips = {}
        self.active_tooltip = None
        self.tooltip_window = None
        self.tooltip_delay = 500  # milliseconds
    
    def add_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Add a tooltip to a widget.
        
        Args:
            widget: The widget to add the tooltip to.
            text: The tooltip text.
        """
        widget.bind("<Enter>", lambda event, w=widget, t=text: self._show_tooltip(w, t))
        widget.bind("<Leave>", lambda event: self._hide_tooltip())
        widget.bind("<ButtonPress>", lambda event: self._hide_tooltip())
        
        # Store the tooltip text for this widget
        self.tooltips[widget] = text
    
    def _show_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Show a tooltip for a widget.
        
        Args:
            widget: The widget to show the tooltip for.
            text: The tooltip text.
        """
        # Cancel any pending tooltip
        self._hide_tooltip()
        
        # Schedule new tooltip
        self.active_tooltip = widget.after(
            self.tooltip_delay, 
            lambda: self._create_tooltip_window(widget, text)
        )
    
    def _create_tooltip_window(self, widget: tk.Widget, text: str) -> None:
        """Create the tooltip window.
        
        Args:
            widget: The widget to show the tooltip for.
            text: The tooltip text.
        """
        # Get the widget's position
        x, y, _, _ = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25
        
        # Create the tooltip window
        self.tooltip_window = tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)  # Remove window decorations
        tw.wm_geometry(f"+{x}+{y}")
        
        # Create the tooltip label
        label = tk.Label(
            tw, text=text, justify=tk.LEFT,
            background="#ffffe0", relief=tk.SOLID, borderwidth=1,
            font=("Segoe UI", 9)
        )
        label.pack(ipadx=4, ipady=2)
    
    def _hide_tooltip(self) -> None:
        """Hide the current tooltip."""
        # Cancel any pending tooltip
        if self.active_tooltip:
            try:
                if isinstance(self.active_tooltip, int):
                    # It's an after() ID
                    widget = next(iter(self.tooltips.keys()))
                    widget.after_cancel(self.active_tooltip)
            except (ValueError, IndexError, AttributeError):
                pass
            self.active_tooltip = None
        
        # Destroy the tooltip window if it exists
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    def update_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Update the tooltip text for a widget.
        
        Args:
            widget: The widget to update the tooltip for.
            text: The new tooltip text.
        """
        if widget in self.tooltips:
            self.tooltips[widget] = text


# Create a singleton instance
tooltips = TooltipManager()
