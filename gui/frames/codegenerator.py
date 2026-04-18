import tkinter as tk
from tkinter import ttk
from core.event_bus import EventBus
import logging
import asyncio
from typing import Optional, Dict, Any, Callable, Coroutine

logger = logging.getLogger("gui.frames.codegenerator")

class CodeGeneratorFrame(ttk.Frame):
    def __init__(self, parent, event_bus: Optional[EventBus] = None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.logger = logging.getLogger("gui.frames.codegenerator")
        self._setup_event_handlers()
        self._create_ui_components()
        
    def _setup_event_handlers(self):
        """Set up event handlers."""
        self._handle_code_execution_result = self._handle_code_execution_result_impl
        self._handle_code_error = self._handle_code_error_impl
        
    async def _handle_code_execution_result_impl(self, result: Dict[str, Any]):
        """Handle code execution results."""
        try:
            self.logger.info(f"Received code execution result: {result}")
            self._update_result_display(result)
        except Exception as e:
            self.logger.error(f"Error handling code result: {e}")
            
    async def _handle_code_error_impl(self, error: Dict[str, Any]):
        """Handle code execution errors."""
        try:
            self.logger.error(f"Received code execution error: {error}")
            self._update_error_display(error)
        except Exception as e:
            self.logger.error(f"Error handling code error: {e}")
            
    def _create_ui_components(self):
        """Create UI components."""
        try:
            # Create main frame
            main_frame = ttk.Frame(self)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create code input
            self.code_input = tk.Text(main_frame, height=10, wrap=tk.WORD)
            self.code_input.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create execute button
            execute_button = ttk.Button(main_frame, text="Execute Code", command=self._execute_code)
            execute_button.pack(fill=tk.X, padx=5, pady=5)
            
            # Create result display
            self.result_display = tk.Text(main_frame, height=10, wrap=tk.WORD)
            self.result_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create error display
            self.error_display = tk.Text(main_frame, height=5, wrap=tk.WORD, bg="red", fg="white")
            self.error_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Subscribe to events
            if self.event_bus:
                self.event_bus.subscribe("code_execution_result", self._handle_code_execution_result)
                self.event_bus.subscribe("code_execution_error", self._handle_code_error)
                
        except Exception as e:
            self.logger.error(f"Error creating UI components: {e}")
            
    def _execute_code(self):
        """Execute the code in the input box."""
        try:
            code = self.code_input.get("1.0", tk.END).strip()
            if code:
                if self.event_bus:
                    self.event_bus.publish("execute_code", {"code": code})
        except Exception as e:
            self.logger.error(f"Error executing code: {e}")
            
    def _update_result_display(self, result: Dict[str, Any]):
        """Update result display."""
        try:
            self.result_display.insert(tk.END, f"Result: {result}\n")
            self.result_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error updating result display: {e}")
            
    def _update_error_display(self, error: Dict[str, Any]):
        """Update error display."""
        try:
            self.error_display.insert(tk.END, f"Error: {error}\n")
            self.error_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error updating error display: {e}")
