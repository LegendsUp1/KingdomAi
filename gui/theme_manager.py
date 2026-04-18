"""
Theme Manager for Kingdom AI GUI.

This module provides theming capabilities for the Kingdom AI GUI,
allowing consistent look and feel across all components.
"""
import tkinter as tk
from typing import Dict, Any, Optional


class ThemeManager:
    """Manages themes for the Kingdom AI GUI."""
    
    def __init__(self):
        """Initialize the theme manager."""
        self.current_theme = "default"
        self.themes = {
            "default": {
                "bg": "#1e1e1e",
                "fg": "#ffffff",
                "accent": "#007acc",
                "success": "#4CAF50",
                "warning": "#FFC107",
                "error": "#F44336",
                "font": ("Segoe UI", 10),
                "heading_font": ("Segoe UI", 12, "bold"),
            },
            "light": {
                "bg": "#f5f5f5",
                "fg": "#333333",
                "accent": "#0078d7",
                "success": "#4CAF50",
                "warning": "#FFC107",
                "error": "#F44336",
                "font": ("Segoe UI", 10),
                "heading_font": ("Segoe UI", 12, "bold"),
            }
        }
    
    def get_theme(self, theme_name: Optional[str] = None) -> Dict[str, Any]:
        """Get the specified theme or the current theme.
        
        Args:
            theme_name: Name of the theme to get. If None, returns the current theme.
            
        Returns:
            The theme dictionary.
        """
        if theme_name is None:
            theme_name = self.current_theme
        
        return self.themes.get(theme_name, self.themes["default"])
    
    def set_theme(self, theme_name: str) -> bool:
        """Set the current theme.
        
        Args:
            theme_name: Name of the theme to set.
            
        Returns:
            True if theme was set successfully, False otherwise.
        """
        if theme_name in self.themes:
            self.current_theme = theme_name
            return True
        return False
    
    def apply_theme_to_widget(self, widget: tk.Widget, theme_name: Optional[str] = None) -> None:
        """Apply the specified theme to a widget.
        
        Args:
            widget: The widget to apply the theme to.
            theme_name: Name of the theme to apply. If None, uses the current theme.
        """
        theme = self.get_theme(theme_name)
        
        try:
            widget.configure(bg=theme["bg"])
            widget.configure(fg=theme["fg"])
            if isinstance(widget, (tk.Button, tk.Entry, tk.Text)):
                widget.configure(font=theme["font"])
        except tk.TclError:
            # Some widgets might not support all configurations
            pass


# Create a singleton instance
theme_manager = ThemeManager()
