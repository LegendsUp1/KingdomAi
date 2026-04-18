"""Loading screen methods - mixin for LoadingScreen class."""

import logging
import traceback
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import scrolledtext
    tkinter_available = True
except ImportError:
    tkinter_available = False

logger = logging.getLogger('KingdomAI.LoadingScreen')


class LoadingScreenMethods:
    """Mixin class providing loading screen event bus and logging methods."""

    def connect_event_bus(self, event_bus):
        """Connect to event bus after it has been initialized"""
        if self.event_bus is not None:
            logger.info("Loading screen already connected to event bus")
            return
            
        try:
            self.event_bus = event_bus
            self._setup_event_handlers()
            
            # Add logs and component lists to the UI for real-time feedback
            if tkinter_available and self.root is not None:
                try:
                    # Create a frame for component status
                    component_frame = tk.Frame(self.frame, bg=self.bg_color)
                    component_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
                    
                    # Add a label and scrolled text widget for component logs
                    component_label = tk.Label(component_frame, text="Component Initialization Status:", 
                                             fg="#ffffff", bg=self.bg_color, font=("Arial", 10, "bold"))
                    component_label.pack(anchor="w", pady=(5, 0))
                    
                    # Create scrolled text for component logs
                    self.component_log = scrolledtext.ScrolledText(component_frame, height=10, width=60,
                                                                 bg="#333333", fg="#ffffff", 
                                                                 font=("Courier", 9))
                    self.component_log.pack(fill=tk.BOTH, expand=True, pady=5)
                    self.component_log.config(state=tk.DISABLED)
                    
                    # Initial message
                    self.add_component_log("Component initialization starting...")
                except Exception as e:
                    logger.error(f"Error adding component tracking UI: {e}")
            
            logger.info("Loading screen connected to event bus successfully")
        except Exception as e:
            logger.error(f"Error connecting loading screen to event bus: {e}")
            logger.error(traceback.format_exc())
    
    def add_component_log(self, message):
        """Add a message to the component log widget"""
        if not tkinter_available or self.root is None or not hasattr(self, 'component_log'):
            return
            
        try:
            self.component_log.config(state=tk.NORMAL)
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.component_log.insert(tk.END, f"[{timestamp}] {message}\n")
            self.component_log.see(tk.END)
            self.component_log.config(state=tk.DISABLED)
            self.root.update_idletasks()
        except Exception as e:
            logger.error(f"Error adding to component log: {e}")
