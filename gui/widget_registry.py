"""Widget Registry module for managing GUI widgets."""

from typing import Dict, Any, Optional
import tkinter as tk
from tkinter import ttk

class WidgetRegistry:
    """Registry for managing GUI widgets and their states."""

    def __init__(self):
        """Initialize the widget registry."""
        self._widgets: Dict[str, Any] = {}
        self._states: Dict[str, Any] = {}

    def register(self, widget_id: str, widget: Any, initial_state: Any = None) -> None:
        """Register a widget with an optional initial state.
        
        Args:
            widget_id: Unique identifier for the widget
            widget: The widget instance to register
            initial_state: Optional initial state for the widget
        """
        self._widgets[widget_id] = widget
        if initial_state is not None:
            self._states[widget_id] = initial_state

    def get_widget(self, widget_id: str) -> Optional[Any]:
        """Get a widget by its ID.
        
        Args:
            widget_id: ID of the widget to retrieve
            
        Returns:
            The widget if found, None otherwise
        """
        return self._widgets.get(widget_id)

    def get_state(self, widget_id: str) -> Optional[Any]:
        """Get the state of a widget by its ID.
        
        Args:
            widget_id: ID of the widget whose state to retrieve
            
        Returns:
            The widget's state if found, None otherwise
        """
        return self._states.get(widget_id)

    def set_state(self, widget_id: str, state: Any) -> None:
        """Set the state for a widget.
        
        Args:
            widget_id: ID of the widget whose state to set
            state: New state value
        """
        if widget_id in self._widgets:
            self._states[widget_id] = state

    def update_widget(self, widget_id: str, **kwargs) -> None:
        """Update a widget's properties.
        
        Args:
            widget_id: ID of the widget to update
            **kwargs: Keyword arguments representing widget properties to update
        """
        widget = self.get_widget(widget_id)
        if widget:
            for key, value in kwargs.items():
                if hasattr(widget, key):
                    setattr(widget, key, value)
                elif isinstance(widget, (tk.Widget, ttk.Widget)):
                    widget.configure(**{key: value})

    def remove(self, widget_id: str) -> None:
        """Remove a widget and its state from the registry.
        
        Args:
            widget_id: ID of the widget to remove
        """
        self._widgets.pop(widget_id, None)
        self._states.pop(widget_id, None)

    def clear(self) -> None:
        """Clear all widgets and states from the registry."""
        self._widgets.clear()
        self._states.clear()

    def get_all_widgets(self) -> Dict[str, Any]:
        """Get all registered widgets.
        
        Returns:
            Dictionary mapping widget IDs to widget instances
        """
        return self._widgets.copy()

    def get_all_states(self) -> Dict[str, Any]:
        """Get all widget states.
        
        Returns:
            Dictionary mapping widget IDs to their states
        """
        return self._states.copy()
