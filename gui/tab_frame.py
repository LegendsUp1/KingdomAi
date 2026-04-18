import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)

class TabFrame(ttk.Frame):
    """Extended Frame class that supports storing widget references"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widgets = {}
        
    def store_widget(self, name, widget):
        """Store a widget reference by name"""
        self.widgets[name] = widget
        return widget
        
    def get_widget(self, name):
        """Get a stored widget by name"""
        return self.widgets.get(name)
        
    def get_widgets(self):
        """Get all stored widgets"""
        return self.widgets
