#!/usr/bin/env python3
"""
Kingdom AI - Code Generator Frame

This module implements the Code Generator frame for the Kingdom AI GUI.
It integrates with the MCP connector to generate code and supports syntax
highlighting and real-time code execution.

"""

import sys
import os
import re
import json
import logging
import asyncio
import tkinter as tk
from tkinter import ttk, Text, END, NORMAL, DISABLED, StringVar, WORD, Frame, messagebox
import uuid
import importlib.util

try:
    import pyperclip
except ImportError:
    pyperclip = None
    
from utils.logger import get_logger

logger = get_logger(__name__)
from typing import Dict, Any, Optional, List, Tuple

from gui.frames.base_frame import BaseFrame

logger = logging.getLogger("KingdomAI.CodeGeneratorFrame")

class CodeGeneratorFrame(BaseFrame):
    """Frame for code generation and MCP connector integration.
    
    Implements code generation functionality with MCP connector integration.
    Works with Thoth AI for code generation without Redis dependency.
    """
    
    def __init__(self, parent, event_bus=None, api_key_connector=None, **kwargs):
        """Initialize the Code Generator frame.
        
        Args:
            parent: The parent widget
            event_bus: The application event bus
            api_key_connector: Optional API key connector
            **kwargs: Additional arguments for the frame
        """
        super().__init__(parent, event_bus=event_bus)
        # Use pack geometry manager consistently
        self.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Store API key connector
        self.api_key_connector = api_key_connector
        
        # Initialize state
        self.mcp_status = "Not Connected"
        self.generating = False
        self.available_resources = []
        self.executing = False
        self.injecting = False
        self.last_generated_code = ""
        self.current_language = "python"
        self.using_rag = False
        self.code_quality_score = None
        
        # Initialize request tracking
        self.current_request_id = None
        
        # Create model variable for dropdown
        self.model_var = tk.StringVar(value="deepseek-coder")
        
        # Create widgets
        self._create_widgets()
        
        # Set initial help text
        self._set_initial_help_text()
        
        # Subscribe to events if event bus is available
        if self.event_bus:
            self._setup_event_listeners()
        
    def _create_widgets(self):
        """Create widgets for the Code Generator frame."""
        # Set background and text colors for better visibility
        bg_color = "#1E1E1E"  # Dark background
        text_color = "#FFFFFF"  # White text
        accent_color = "#0078D7"  # Blue accent
        
        # Use ttk.Style to configure the frame
        style = ttk.Style()
        style.configure('CodeGen.TFrame', background=bg_color)
        style.configure('CodeGen.TButton', font=('Arial', 9))
        style.configure('Primary.TButton', background=accent_color)
        
        # Main layout - using pack manager consistently
        
        # Control area
        control_frame = ttk.Frame(self, style='CodeGen.TFrame')
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Title with enhanced visual
        title_label = ttk.Label(control_frame, text="Advanced Code Generator", 
                              font=("Arial", 14, "bold"), foreground="#00BFFF")
        title_label.pack(side=tk.LEFT, padx=5)
        
        # Status indicator frame
        self.status_frame = ttk.Frame(control_frame)
        self.status_frame.pack(side=tk.RIGHT, padx=10)
        
        # MCP Status indicator
        self.mcp_status_var = tk.StringVar(value="MCP: Not Connected")
        self.mcp_status_label = ttk.Label(self.status_frame, textvariable=self.mcp_status_var,
                                        foreground="#FF5252")
        self.mcp_status_label.pack(side=tk.TOP, anchor=tk.E)
        
        # Model selection
        model_frame = ttk.Frame(control_frame, style='CodeGen.TFrame')
        model_frame.pack(side=tk.LEFT, padx=15)
        
        model_label = ttk.Label(model_frame, text="Model:", foreground=text_color)
        model_label.pack(side=tk.LEFT, padx=2)
        
        # Updated 2025 state-of-the-art model list for code generation
        self.model_var = tk.StringVar(value="deepseek-coder-v2")
        self.model_dropdown = ttk.Combobox(model_frame, textvariable=self.model_var, width=20)
        self.model_dropdown['values'] = [
            "deepseek-coder-v2",    # DeepSeek Coder V2 - 2025 SOTA for code
            "codegemma-2",          # Google's CodeGemma 2 - 2025 version
            "starcoder-2-instruct", # StarCoder 2 Instruction-tuned model
            "claude-sonnet-3.7",    # Claude Sonnet 3.7 with enhanced code capabilities
            "gpt4-turbo-code",      # GPT-4 Turbo with specialized code focus
            "codellama-70b-instruct", # Upgraded CodeLlama with instruction tuning
            "thoth-code-expert",    # Thoth's specialized code generation model
            "llama3",         # General purpose with code capabilities
            "thoth-local"     # Local model if available
        ]
        self.model_dropdown.pack(side=tk.LEFT, padx=2)
        
        # Progress indicator with improved styling
        self.progress_frame = ttk.Frame(control_frame, style='CodeGen.TFrame')
        self.progress_frame.pack(side=tk.RIGHT, padx=10)
        
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            orient='horizontal', 
            length=150, 
            mode='determinate',
            variable=self.progress_var
        )
        self.progress_bar.pack(side=tk.TOP, fill=tk.X)
        
        self.progress_label = ttk.Label(self.progress_frame, text="", foreground="#9CCC65")
        self.progress_label.pack(side=tk.TOP, fill=tk.X)
        
        # Button Frame with improved layout
        button_frame = ttk.Frame(control_frame, style='CodeGen.TFrame')
        button_frame.pack(side=tk.RIGHT, padx=5)
        
        # Generate button with enhanced styling
        self.generate_button = ttk.Button(
            button_frame, 
            text="Generate Code", 
            command=self._on_generate_code,
            style='Primary.TButton'
        )
        self.generate_button.pack(side=tk.LEFT, padx=2)
        
        # Execute button
        self.execute_button = ttk.Button(
            button_frame, 
            text="Execute Code", 
            command=self._on_execute_code
        )
        self.execute_button.pack(side=tk.LEFT, padx=2)
        
        # NEW: Inject button for integrating code into the system
        self.inject_button = ttk.Button(
            button_frame, 
            text="Inject to System", 
            command=self._on_inject_code
        )
        self.inject_button.pack(side=tk.LEFT, padx=2)
        
        # Clear button
        clear_button = ttk.Button(
            button_frame, 
            text="Clear", 
            command=self._on_clear
        )
        clear_button.pack(side=tk.LEFT, padx=2)
        
        # Copy button
        copy_button = ttk.Button(
            button_frame, 
            text="Copy Output", 
            command=self._on_copy_output
        )
        copy_button.pack(side=tk.LEFT, padx=2)
        
        # Code area with paned window
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Input frame
        input_frame = ttk.LabelFrame(paned_window, text="Prompt / Input")
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)
        
        # Input text area
        self.input_text = scrolledtext.ScrolledText(
            input_frame,
            wrap=tk.WORD,
            background="#1e1e1e",
            foreground="#f0f0f0",
            font=("Consolas", 10)
        )
        self.input_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Output frame
        output_frame = ttk.LabelFrame(paned_window, text="Generated Code & Output")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        # Output text area
        self.output_text = scrolledtext.ScrolledText(
            output_frame, 
            wrap=tk.WORD,
            width=60,
            height=30,
            bg="#282C34",
            fg="white",
            insertbackground="white",
            state=tk.DISABLED,
            font=("Consolas", 10)  # Use monospace font for code
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add frames to paned window
        paned_window.add(input_frame, weight=1)
        paned_window.add(output_frame, weight=1)
        
        # Add initial help text
        
    def _set_initial_help_text(self):
        """Set initial help text in the input area."""
        help_text = (
            "# Advanced Code Generation Assistant\n\n"
            "Enter a description of the code you want to generate. For example:\n\n"
            "1. Write a Python function to sort a list of dictionaries by a specific key\n"
            "2. Create a class for managing blockchain transactions with error handling\n"
            "3. Write a regex pattern to extract cryptocurrency addresses from text\n\n"
            "4. Generate a data visualization dashboard for cryptocurrency portfolios\n\n"
            "You can specify language preferences like Python, JavaScript, TypeScript, etc.\n"
            "Add implementation details or specific requirements for more tailored results.\n\n"
            "Use the 'Inject to System' button to integrate generated code with Kingdom AI.\n"
        )
        
        # Initialize for Thoth AI integration
        self._setup_event_listeners()
    
    def _setup_event_listeners(self):
        """Set up event listeners for code generator events."""
        if not self.event_bus:
            logger.warning("No event bus available for subscription")
            return
                
        # Subscribe to code generation events
        self.event_bus.subscribe("code_generation_start", self._handle_code_generation_start)
        self.event_bus.subscribe("code_generation_progress", self._handle_code_generation_progress)
        self.event_bus.subscribe("code_generation_complete", self._handle_code_generation_complete)
        self.event_bus.subscribe("code_generation_error", self._handle_code_generation_error)
        self.event_bus.subscribe("code_generated", self._handle_code_generated)
        self.event_bus.subscribe("mcp_status", self._handle_mcp_status)
        self.event_bus.subscribe("mcp_resources", self._handle_mcp_resources)
        self.event_bus.subscribe("code_execution_result", self._handle_code_execution_result)
        self.event_bus.subscribe("code_injection_result", self._handle_code_injection_result)
        self.event_bus.subscribe("thoth_ai_status", self._handle_thoth_ai_status)
        
    def _handle_code_generation_start(self, event_data):
        """Handle code generation start event.
        
        Args:
            event_data: Event data containing request_id
        """
        if not event_data or not isinstance(event_data, dict):
            return
            
        request_id = event_data.get('request_id')
        if request_id != self.current_request_id:
            return  # Not our request
            
        self.generating = True
        self._update_ui_state()
        self._add_output_message("Starting code generation...\n")
        
    def _handle_code_generation_progress(self, event_data):
        """Handle code generation progress event.
        
        Args:
            event_data: Event data containing progress info
        """
        if not event_data or not isinstance(event_data, dict):
            return
            
        request_id = event_data.get('request_id')
        if request_id != self.current_request_id:
            return  # Not our request
            
        progress = event_data.get('progress', 0)
        message = event_data.get('message', '')
        
        if message:
            self._add_output_message(f"{message}\n")
    
    def _handle_code_generation_complete(self, event_data):
        """Handle code generation complete event.
        
        Args:
            event_data: Event data containing generation result
        """
        if not event_data or not isinstance(event_data, dict):
            return
            
        request_id = event_data.get('request_id')
        if request_id != self.current_request_id:
            return  # Not our request
            
        self.generating = False
        self._update_ui_state()
        self._add_output_message("Code generation complete.\n")
    
    def _handle_code_generation_error(self, event_data):
        """Handle code generation error event.
        
        Args:
            event_data: Event data containing error info
        """
        if not event_data or not isinstance(event_data, dict):
            return
            
        request_id = event_data.get('request_id')
        if request_id != self.current_request_id:
            return  # Not our request
            
        error = event_data.get('error', 'Unknown error')
        self._add_output_message(f"Error generating code: {error}\n", error=True)
        
        self.generating = False
        self._update_ui_state()
    
    def _handle_code_generated(self, event_data):
        """Handle code generated event.
        
        Args:
            event_data: Event data containing generated code
        """
        if not event_data or not isinstance(event_data, dict):
            return
            
        request_id = event_data.get('request_id')
        if request_id != self.current_request_id:
            return  # Not our request
            
        code = event_data.get('code', '')
        language = event_data.get('language', 'python')
        
        self.current_language = language
        self.last_generated_code = code
        
        # Display the generated code
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, code)
        self.output_text.config(state=tk.DISABLED)
        
        self.generating = False
        self._update_ui_state()
        
    def _handle_mcp_status(self, event_data):
        """Handle MCP status update event."""
        if 'status' in event_data:
            status = event_data['status']
            connected = status == "connected"
            
            # Update UI
            self.mcp_status = "Connected" if connected else "Not Connected"
            self.mcp_status_var.set(f"MCP: {self.mcp_status}")
            
            # Update button states
            self._update_ui_state()
    
    def _handle_mcp_resources(self, event_data):
        """Handle MCP resources event."""
        if 'resources' in event_data:
            self.available_resources = event_data['resources']
    
    def _handle_code_execution_result(self, event_data):
        """Handle code execution result event."""
        result = event_data.get('result', '')
        error = event_data.get('error', '')
        
        if error:
            self._add_output_message("\nExecution Error: " + error + "\n", error=True)
        else:
            self._add_output_message("\nExecution Result:\n" + result + "\n")
        
        self.executing = False
        self._update_ui_state()
    
    def _handle_code_injection_result(self, event_data):
        """Handle code injection result event."""
        success = event_data.get('success', False)
        message = event_data.get('message', '')
        
        if success:
            self._add_output_message("\nCode successfully injected: " + message + "\n")
        else:
            self._add_output_message("\nCode injection failed: " + message + "\n", error=True)
        
        self.injecting = False
        self._update_ui_state()
        
    def _handle_thoth_ai_status(self, data):
        """Handle Thoth AI status updates."""
        status = data.get("status", "Unknown")
        connected = data.get("connected", False)
        model = data.get("model", "")
            
        # Update status text and color
        status_text = f"ThothAI: {status}"
        if model and connected:
            status_text += f" ({model})"
                
        self.thoth_status_var.set(status_text)
        color = "#4CAF50" if connected else "#FF5252"
        self.thoth_status_label.config(foreground=color)
            
        # Update instance state
        self.thoth_status = status

    def _on_generate_code(self):
        """Handle generate button click."""
        prompt = self.input_text.get(1.0, tk.END).strip()
        if not prompt:
            self._add_output_message("Please enter a prompt before generating code.\n", error=True)
            return
            
        # Set state for UI updates
        self.generating = True
        self._update_ui_state()
        
        # Show progress indicators
        self.progress_var.set(0)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(10)
        self.progress_label.config(text="Generating code...")
        self.progress_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        # Generate a request ID for tracking
        request_id = str(uuid.uuid4())
        self.current_request_id = request_id
        
        # Get selected model
        model = self.model_var.get()
        
        # Emit event to generate code
        self.event_bus.emit("mcp.generate_code", {
            "prompt": prompt,
            "model": model,
            "request_id": request_id,
            "use_rag": self.using_rag
        })

    def _on_execute_code(self):
        """Handle execute button click."""
        # Get code to execute
        code = self.output_text.get(1.0, tk.END).strip()
        if not code:
            self._add_output_message("No code to execute.\n", error=True)
            return
            
        # Prepare execution request
        request_id = str(uuid.uuid4())
        execution_data = {
            "id": request_id,
            "code": code,
            "timestamp": datetime.now().isoformat()
        }
        
        # Emit execution request event
        self.event_bus.emit("thothAI.execute_request", execution_data)
        self._add_output_message("\nExecuting code...\n")
        
        # Disable button during execution
        self.execute_button.config(state=tk.DISABLED)

    def _on_inject_code(self):
        """Handle inject button click."""
        # Get code to inject
        code = self.output_text.get(1.0, tk.END).strip()
        if not code:
            self._add_output_message("No code to inject.\n", error=True)
            return
            
        # Ask for confirmation as this is a system-altering operation
        from tkinter import messagebox
        confirm = messagebox.askyesno(
            "Confirm Code Injection",
            "Are you sure you want to inject this code into the Kingdom AI system? " 
            "This operation can modify system behavior."
        )
        
        if not confirm:
            self._add_output_message("\nCode injection cancelled\n")
            return
            
        # Prepare injection request
        request_id = str(uuid.uuid4())
        injection_data = {
            "id": request_id,
            "code": code,
            "timestamp": datetime.now().isoformat(),
            "source": "CodeGeneratorFrame"
        }
        
        # Emit injection request event
        self.event_bus.emit("thothAI.inject_request", injection_data)
        self._add_output_message("\nInjecting code into system...\n")
        
        # Disable button during injection
        self.inject_button.config(state=tk.DISABLED)

    def _on_clear(self):
        """Handle clear button click."""
        self._set_output_text("")
        self.progress_var.set(0)
        self.progress_label.config(text="")
        self._add_output_message(self.DEFAULT_OUTPUT_MESSAGE)
        
        # Re-enable buttons
        self.generate_button.config(state=tk.NORMAL)
        self.execute_button.config(state=tk.DISABLED)
        self.inject_button.config(state=tk.DISABLED)
    
    def _on_copy_output(self):
        """Handle copy output button click."""
        output_text = self.output_text.get(1.0, tk.END).strip()
        
        if not output_text:
            self._add_output_message("\nNothing to copy\n")
            return
            
        # Try to copy to clipboard
        try:
            if pyperclip:
                pyperclip.copy(output_text)
                self._add_output_message("\nOutput copied to clipboard\n")
            else:
                # Fallback to tkinter clipboard
                self.clipboard_clear()
                self.clipboard_append(output_text)
                self._add_output_message("\nOutput copied to clipboard (tkinter fallback)\n")
        except Exception as e:
            self._add_output_message(f"\nERROR copying to clipboard: {str(e)}\n", error=True)

    def _update_ui_state(self):
        """Update UI elements based on current state."""
        # Update button states based on MCP status and generation state
        if self.mcp_status == "Connected" and not self.generating:
            self.generate_button.config(state=tk.NORMAL)
        else:
            self.generate_button.config(state=tk.DISABLED)
        
        # Enable execute and inject buttons only if we have generated code and not currently executing or injecting
        has_code = self.output_text.get(1.0, tk.END).strip() != ""
        if has_code and not self.generating and not self.executing and not self.injecting and self.mcp_status == "Connected":
            self.execute_button.config(state=tk.NORMAL)
            self.inject_button.config(state=tk.NORMAL)
        else:
            self.execute_button.config(state=tk.DISABLED)
            self.inject_button.config(state=tk.DISABLED)
    
    def _add_output_message(self, message, error=False):
        """Add a message to the output text area."""
        self.output_text.config(state=tk.NORMAL)
        
        # Determine tag
        tag = "error_message" if error else "message"
        
        # Insert with tag
        self.output_text.insert(tk.END, message, tag)
        
        # Configure tags with better contrasting colors
        if error:
            self.output_text.tag_configure("error_message", foreground="#FF5252", background="#303030")
        else:
            self.output_text.tag_configure("message", foreground="#9CCC65", background="#303030")
        
        # Scroll to end
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
    
    def _add_output_code(self, code):
        """Add code to the output text area with syntax highlighting."""
        self.output_text.config(state=tk.NORMAL)
        
        # Clear any existing content
        self.output_text.delete(1.0, tk.END)
        
        # Insert code with appropriate tag based on language
        self.output_text.insert(tk.END, code, f"code_{self.current_language}")
        
        # Configure code tag with language-specific highlighting
        if self.current_language == "python":
            self.output_text.tag_configure(f"code_{self.current_language}", foreground="#58D68D")
        elif self.current_language == "javascript" or self.current_language == "typescript":
            self.output_text.tag_configure(f"code_{self.current_language}", foreground="#FFD700")
        elif self.current_language == "java":
            self.output_text.tag_configure(f"code_{self.current_language}", foreground="#FF8C00")
        elif self.current_language == "cpp" or self.current_language == "c++":
            self.output_text.tag_configure(f"code_{self.current_language}", foreground="#00BFFF")
        else:
            # Default color for other languages
            self.output_text.tag_configure(f"code_{self.current_language}", foreground="#58D68D")
        
        # Scroll to start
        self.output_text.see(1.0)
        self.output_text.config(state=tk.DISABLED)
        
        # Enable execute and inject buttons since we now have code
        self.last_generated_code = code
        self._update_ui_state()
