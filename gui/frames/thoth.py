import tkinter as tk
from tkinter import ttk
from core.event_bus import EventBus
import logging
import asyncio
from typing import Optional, Dict, Any, Callable, Coroutine

logger = logging.getLogger("gui.frames.thoth")

class ThothFrame(ttk.Frame):
    def __init__(self, parent, event_bus: Optional[EventBus] = None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.logger = logging.getLogger("gui.frames.thoth")
        self._setup_message_methods()
        self._create_ui_components()
        
    def _setup_message_methods(self):
        """Set up message handling methods."""
        self._handle_message = self._handle_message_impl
        self._handle_response = self._handle_response_impl
        self._handle_error = self._handle_error_impl
        
    async def _handle_message_impl(self, message: Dict[str, Any]):
        """Handle incoming messages."""
        try:
            self.logger.info(f"Received message: {message}")
            # Process message and update UI
            self._update_message_display(message)
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            
    async def _handle_response_impl(self, response: Dict[str, Any]):
        """Handle AI responses."""
        try:
            self.logger.info(f"Received AI response: {response}")
            # Process response and update UI
            self._update_response_display(response)
        except Exception as e:
            self.logger.error(f"Error handling response: {e}")
            
    async def _handle_error_impl(self, error: Dict[str, Any]):
        """Handle errors."""
        try:
            self.logger.error(f"Received error: {error}")
            # Update error display
            self._update_error_display(error)
        except Exception as e:
            self.logger.error(f"Error handling error: {e}")
            
    def _create_ui_components(self):
        """Create UI components."""
        try:
            # Create main frame
            main_frame = ttk.Frame(self)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create message display
            self.message_display = tk.Text(main_frame, height=10, wrap=tk.WORD)
            self.message_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create response display
            self.response_display = tk.Text(main_frame, height=10, wrap=tk.WORD)
            self.response_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create error display
            self.error_display = tk.Text(main_frame, height=5, wrap=tk.WORD, bg="red", fg="white")
            self.error_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Subscribe to events
            if self.event_bus:
                self.event_bus.subscribe("message", self._handle_message)
                self.event_bus.subscribe("response", self._handle_response)
                self.event_bus.subscribe("error", self._handle_error)
                
        except Exception as e:
            self.logger.error(f"Error creating UI components: {e}")
            
    def _update_message_display(self, message: Dict[str, Any]):
        """Update message display."""
        try:
            self.message_display.insert(tk.END, f"Message: {message}\n")
            self.message_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error updating message display: {e}")
            
    def _update_response_display(self, response: Dict[str, Any]):
        """Update response display."""
        try:
            self.response_display.insert(tk.END, f"Response: {response}\n")
            self.response_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error updating response display: {e}")
            
    def _update_error_display(self, error: Dict[str, Any]):
        """Update error display."""
        try:
            self.error_display.insert(tk.END, f"Error: {error}\n")
            self.error_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error updating error display: {e}")
