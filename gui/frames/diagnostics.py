import tkinter as tk
from tkinter import ttk
from core.event_bus import EventBus
import logging
import asyncio
from typing import Optional, Dict, Any, Callable, Coroutine

logger = logging.getLogger("gui.frames.diagnostics")

class DiagnosticsFrame(ttk.Frame):
    def __init__(self, parent, event_bus: Optional[EventBus] = None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.logger = logging.getLogger("gui.frames.diagnostics")
        self._create_ui_components()
        
    def _create_ui_components(self):
        """Create UI components."""
        try:
            # Create main frame
            main_frame = ttk.Frame(self)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create status display
            self.status_display = tk.Text(main_frame, height=15, wrap=tk.WORD)
            self.status_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create log display
            self.log_display = tk.Text(main_frame, height=10, wrap=tk.WORD)
            self.log_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create metrics display
            self.metrics_display = tk.Text(main_frame, height=10, wrap=tk.WORD)
            self.metrics_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Subscribe to events
            if self.event_bus:
                self.event_bus.subscribe("status_update", self._handle_status_update)
                self.event_bus.subscribe("log_entry", self._handle_log_entry)
                self.event_bus.subscribe("metrics_update", self._handle_metrics_update)
                
        except Exception as e:
            self.logger.error(f"Error creating UI components: {e}")
            
    async def _handle_status_update(self, status: Dict[str, Any]):
        """Handle status updates."""
        try:
            self.status_display.insert(tk.END, f"Status: {status}\n")
            self.status_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error updating status display: {e}")
            
    async def _handle_log_entry(self, log_entry: Dict[str, Any]):
        """Handle log entries."""
        try:
            self.log_display.insert(tk.END, f"Log: {log_entry}\n")
            self.log_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error updating log display: {e}")
            
    async def _handle_metrics_update(self, metrics: Dict[str, Any]):
        """Handle metrics updates."""
        try:
            self.metrics_display.insert(tk.END, f"Metrics: {metrics}\n")
            self.metrics_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error updating metrics display: {e}")
