"""
Kingdom AI Code Generation Tab Initialization Module
This module provides the initialization method for the Code Generation tab in the Kingdom AI GUI.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import uuid

logger = logging.getLogger("KingdomAI.TabManager")

async def _init_codegen_tab(self, tab_frame):
    """Initialize the code generation tab with AI model capabilities.
    
    This method follows the 8-step lifecycle:
    1. Retrieval - Locate data sources
    2. Fetching - Active data retrieval
    3. Binding - Connect data to GUI elements
    4. Formatting - Present data in readable format
    5. Event Handling - Respond to user/system events
    6. Concurrency - Prevent UI blocking
    7. Error Handling - Graceful error management
    8. Debugging - Tools for diagnostics
    
    Args:
        tab_frame: The tab frame to populate
    """
    try:
        # STEP 1: RETRIEVAL - Identify data sources
        data_sources = {
            "models": "ai_models_repository",
            "code_history": "codegen_database",
            "language_support": "language_configs"
        }
        logger.info(f"Code Generation tab initializing with data sources: {list(data_sources.keys())}")
        
        # STEP 2: FETCHING - Set up infrastructure for data fetching
        # Will be triggered via event bus after UI elements are created
        
        if self.using_pyqt:
            from PyQt6.QtWidgets import (QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, 
                                         QComboBox, QTextEdit, QLineEdit, QSplitter)
            from PyQt6.QtCore import Qt, QSize
            
            # Main layout
            layout = tab_frame.layout()
            
            # Header with Title and Status
            header_widget = QFrame()
            header_layout = QHBoxLayout(header_widget)
            
            # Title
            title_label = QLabel("AI Code Generation")
            title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
            header_layout.addWidget(title_label, 1)
            
            # Connection Status
            self.codegen_status = QLabel("Status: Initializing...")
            header_layout.addWidget(self.codegen_status)
            
            layout.addWidget(header_widget)
            
            # Model Selection Section
            model_frame = QFrame()
            model_layout = QHBoxLayout(model_frame)
            
            model_label = QLabel("AI Model:")
            model_layout.addWidget(model_label)
            
            self.model_selector = QComboBox()
            self.model_selector.addItems(["GPT-4", "Claude 3", "Llama 3", "Gemini Pro", "Code Llama"])
            model_layout.addWidget(self.model_selector)
            
            language_label = QLabel("Language:")
            model_layout.addWidget(language_label)
            
            self.language_selector = QComboBox()
            self.language_selector.addItems(["Python", "JavaScript", "C++", "Java", "Go", "Rust", "SQL"])
            model_layout.addWidget(self.language_selector)
            
            layout.addWidget(model_frame)
            
            # Code Input/Output Section
            io_splitter = QSplitter(Qt.Orientation.Vertical)
            
            # Input Frame
            input_frame = QFrame()
            input_layout = QVBoxLayout(input_frame)
            
            input_header = QLabel("Input Prompt:")
            input_header.setStyleSheet("font-weight: bold;")
            input_layout.addWidget(input_header)
            
            self.code_input = QTextEdit()
            self.code_input.setPlaceholderText("Enter your code generation prompt here...")
            input_layout.addWidget(self.code_input)
            
            io_splitter.addWidget(input_frame)
            
            # Output Frame
            output_frame = QFrame()
            output_layout = QVBoxLayout(output_frame)
            
            output_header = QLabel("Generated Code:")
            output_header.setStyleSheet("font-weight: bold;")
            output_layout.addWidget(output_header)
            
            self.code_output = QTextEdit()
            self.code_output.setReadOnly(True)
            self.code_output.setPlaceholderText("Generated code will appear here...")
            output_layout.addWidget(self.code_output)
            
            io_splitter.addWidget(output_frame)
            io_splitter.setSizes([200, 300])  # Default size distribution
            
            layout.addWidget(io_splitter)
            
            # Actions Section
            actions_frame = QFrame()
            actions_layout = QHBoxLayout(actions_frame)
            
            # STEP 5: EVENT HANDLING - Connect buttons to actions
            generate_btn = QPushButton("Generate Code")
            generate_btn.clicked.connect(self.generate_code)
            actions_layout.addWidget(generate_btn)
            
            view_history_btn = QPushButton("View History")
            view_history_btn.clicked.connect(self.view_generated_code)
            actions_layout.addWidget(view_history_btn)
            
            save_btn = QPushButton("Save to File")
            save_btn.clicked.connect(lambda: self._save_generated_code())
            actions_layout.addWidget(save_btn)
            
            layout.addWidget(actions_frame)
            
            # STEP 3: BINDING - Register widgets for data updates
            if hasattr(self, 'widget_registry'):
                await self.widget_registry.register_widget("codegen_status", self.codegen_status)
                await self.widget_registry.register_widget("model_selector", self.model_selector)
                await self.widget_registry.register_widget("language_selector", self.language_selector)
                await self.widget_registry.register_widget("code_output", self.code_output)
                
        elif self.using_tkinter:
            import tkinter as tk
            from tkinter import ttk
            
            # Create frame structure
            title_frame = ttk.Frame(tab_frame)
            title_frame.pack(fill="x", padx=10, pady=5)
            
            title_label = ttk.Label(title_frame, text="AI Code Generation", font=("Helvetica", 14, "bold"))
            title_label.pack(side="left")
            
            self.codegen_status = ttk.Label(title_frame, text="Status: Initializing...")
            self.codegen_status.pack(side="right")
            
            # Model Selection Frame
            model_frame = ttk.Frame(tab_frame)
            model_frame.pack(fill="x", padx=10, pady=5)
            
            ttk.Label(model_frame, text="AI Model:").pack(side="left", padx=(0, 5))
            
            self.model_selector = ttk.Combobox(model_frame, values=["GPT-4", "Claude 3", "Llama 3", "Gemini Pro", "Code Llama"])
            self.model_selector.pack(side="left", padx=(0, 10))
            self.model_selector.current(0)
            
            ttk.Label(model_frame, text="Language:").pack(side="left", padx=(0, 5))
            
            self.language_selector = ttk.Combobox(model_frame, values=["Python", "JavaScript", "C++", "Java", "Go", "Rust", "SQL"])
            self.language_selector.pack(side="left")
            self.language_selector.current(0)
            
            # Input Frame
            input_frame = ttk.LabelFrame(tab_frame, text="Input Prompt")
            input_frame.pack(fill="both", expand=True, padx=10, pady=5)
            
            self.code_input = tk.Text(input_frame, wrap="word", height=6)
            self.code_input.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Output Frame
            output_frame = ttk.LabelFrame(tab_frame, text="Generated Code")
            output_frame.pack(fill="both", expand=True, padx=10, pady=5)
            
            self.code_output = tk.Text(output_frame, wrap="none", state="disabled", height=10)
            self.code_output.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Add scrollbars
            input_scroll = ttk.Scrollbar(self.code_input, orient="vertical", command=self.code_input.yview)
            self.code_input.configure(yscrollcommand=input_scroll.set)
            input_scroll.pack(side="right", fill="y")
            
            output_scroll = ttk.Scrollbar(self.code_output, orient="vertical", command=self.code_output.yview)
            self.code_output.configure(yscrollcommand=output_scroll.set)
            output_scroll.pack(side="right", fill="y")
            
            # Actions Frame
            actions_frame = ttk.Frame(tab_frame)
            actions_frame.pack(fill="x", padx=10, pady=10)
            
            # STEP 5: EVENT HANDLING - Connect buttons to actions
            generate_btn = ttk.Button(actions_frame, text="Generate Code", command=self.generate_code)
            generate_btn.pack(side="left", padx=5)
            
            view_history_btn = ttk.Button(actions_frame, text="View History", command=self.view_generated_code)
            view_history_btn.pack(side="left", padx=5)
            
            save_btn = ttk.Button(actions_frame, text="Save to File", command=lambda: self._save_generated_code())
            save_btn.pack(side="left", padx=5)
            
            # STEP 3: BINDING - Register widgets for data updates
            if hasattr(self, 'widget_registry'):
                await self.widget_registry.register_widget("codegen_status", self.codegen_status)
                await self.widget_registry.register_widget("model_selector", self.model_selector)
                await self.widget_registry.register_widget("language_selector", self.language_selector)
                await self.widget_registry.register_widget("code_output", self.code_output)
        
        # STEP 6: CONCURRENCY - Fetch initial data asynchronously
        if self.event_bus:
            # Request available models and generation history
            await self.request_codegen_status()
            
        # STEP 7: ERROR HANDLING - Done in the try/except block
        
        # STEP 8: DEBUGGING - Log completion
        logger.info("Code Generation tab initialized with AI models")
        
    except Exception as e:
        # Error handling
        logger.error(f"Error initializing code generation tab: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        
        # Display error in the UI if possible
        try:
            if hasattr(self, 'codegen_status'):
                if self.using_pyqt:
                    self.codegen_status.setText("Error: Failed to initialize code generation tab")
                    self.codegen_status.setStyleSheet("color: red;")
                else:
                    self.codegen_status.config(text="Error: Failed to initialize code generation tab", foreground="red")
        except Exception:
            # Last resort if even error display fails
            pass
            
    def _save_generated_code(self):
        """Save generated code to a file."""
        try:
            import os
            from datetime import datetime
            
            # Get the generated code
            if self.using_pyqt:
                code = self.code_output.toPlainText()
                language = self.language_selector.currentText()
            else:
                self.code_output.config(state="normal")
                code = self.code_output.get("1.0", "end-1c")
                self.code_output.config(state="disabled")
                language = self.language_selector.get()
                
            if not code or code == "Generated code will appear here...":
                logger.warning("No code to save")
                return
                
            # Create file extension based on language
            extension_map = {
                "Python": ".py",
                "JavaScript": ".js",
                "C++": ".cpp",
                "Java": ".java",
                "Go": ".go",
                "Rust": ".rs",
                "SQL": ".sql"
            }
            
            extension = extension_map.get(language, ".txt")
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_code_{timestamp}{extension}"
            
            # Save to file
            code_dir = os.path.join(os.path.expanduser("~"), "KingdomAI", "generated_code")
            os.makedirs(code_dir, exist_ok=True)
            
            file_path = os.path.join(code_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
                
            # Update status
            message = f"Code saved to {file_path}"
            logger.info(message)
            
            if self.using_pyqt:
                self.codegen_status.setText(message)
            else:
                self.codegen_status.config(text=message)
                
        except Exception as e:
            logger.error(f"Error saving generated code: {e}")
            
    # Handler for code generation updates
    async def update_code_generation(self, data: Dict[str, Any]) -> None:
        """Update code generation output with AI-generated code.
        
        Args:
            data: Dictionary containing code generation results from the event bus
        """
        try:
            logger.info(f"Received code generation update: {data}")
            if not data or not isinstance(data, dict):
                logger.warning("Received invalid code generation data")
                return
                
            # Update generated code if available
            if 'generated_code' in data and hasattr(self, 'code_output'):
                code = data.get('generated_code', '')
                
                if self.using_pyqt:
                    self.code_output.setText(code)
                    # Highlight syntax according to language if possible
                    try:
                        language = self.language_selector.currentText().lower()
                        # Apply syntax highlighting (hypothetical method)
                        if hasattr(self, 'apply_syntax_highlighting'):
                            await self.apply_syntax_highlighting(self.code_output, language)
                    except Exception as e:
                        logger.debug(f"Syntax highlighting error: {e}")
                else:
                    self.code_output.config(state="normal")
                    self.code_output.delete("1.0", "end")
                    self.code_output.insert("1.0", code)
                    self.code_output.config(state="disabled")
                    
            # Update status if available
            if 'status' in data and hasattr(self, 'codegen_status'):
                status = data.get('status', 'Unknown')
                
                if self.using_pyqt:
                    self.codegen_status.setText(f"Status: {status}")
                else:
                    self.codegen_status.config(text=f"Status: {status}")
                
            # Update model list if available
            if 'available_models' in data and hasattr(self, 'model_selector'):
                models = data.get('available_models', [])
                
                if models and len(models) > 0:
                    if self.using_pyqt:
                        self.model_selector.clear()
                        self.model_selector.addItems(models)
                    else:
                        self.model_selector['values'] = models
                        
        except Exception as e:
            logger.error(f"Error updating code generation: {e}")
