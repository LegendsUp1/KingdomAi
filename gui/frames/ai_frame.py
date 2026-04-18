#!/usr/bin/env python3
"""
AI Frame for Kingdom AI GUI.
Provides the interface for ThothAI and other AI-related functionality.
"""

import tkinter as tk
from tkinter import ttk
import logging
import os
import sys
from datetime import datetime

from .base_frame import BaseFrame
from ..kingdom_style import KingdomStyles

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class AIFrame(BaseFrame):
    """AI frame for managing ThothAI and AI-related functionality in Kingdom AI."""
    
    def __init__(self, parent, event_bus=None, config_manager=None, api_key_connector=None, name="AIFrame", **kwargs):
        """Initialize the AI frame.
        
        Args:
            parent: The parent widget
            event_bus: The event bus for publishing/subscribing to events
            config_manager: Configuration manager for AI settings
            api_key_connector: Connector for accessing API keys
            name: Name of the frame
            **kwargs: Additional kwargs for the frame
        """
        # Initialize BaseFrame
        super().__init__(parent, event_bus, config_manager, name=name, api_key_connector=api_key_connector, **kwargs)
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # AI system status
        self.ai_status = {
            "thoth_connected": False,
            "last_query_time": None,
            "models_loaded": [],
            "active_model": None
        }
        
        # API keys for AI services
        self.ai_service_keys = {}
        
        # UI elements
        self.model_selector = None
        self.query_input = None
        self.response_text = None
        self.status_indicator = None
    
    async def initialize(self):
        """Initialize the AI frame."""
        self.logger.info("Initializing AI frame")
        
        try:
            # Call parent initialization
            await super().initialize()
            
            # Create AI-specific layout
            self._create_ai_layout()
            
            # Register for AI-specific events
            self._subscribe_to_events()
            
            # Update status
            self.update_status("AI Frame initialized", 100)
            
        except Exception as e:
            self.logger.error(f"Error initializing AI Frame: {e}")
            self.update_status(f"Initialization error: {e}", 0)
    
    def _subscribe_to_events(self):
        """Subscribe to AI-specific events."""
        try:
            if self.event_bus:
                self._safe_subscribe("ai.status", self._handle_ai_status)
                self._safe_subscribe("ai.response", self._handle_ai_response)
                self._safe_subscribe("ai.model.loaded", self._handle_model_loaded)
                self._safe_subscribe("thoth.status", self._handle_thoth_status)
        except Exception as e:
            self.logger.error(f"Error subscribing to events: {e}")
    
    def _create_ai_layout(self):
        """Create the AI layout with ThothAI interface and model controls."""
        try:
            # Create main container with tabs
            self.notebook = ttk.Notebook(self.content_frame)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Create Thoth AI tab
            self.thoth_tab = tk.Frame(self.notebook, bg=KingdomStyles.COLORS["frame_bg"])
            self.notebook.add(self.thoth_tab, text="ThothAI")
            
            # Create general AI tab
            self.ai_tab = tk.Frame(self.notebook, bg=KingdomStyles.COLORS["frame_bg"])
            self.notebook.add(self.ai_tab, text="AI Models")
            
            # Create model training tab
            self.training_tab = tk.Frame(self.notebook, bg=KingdomStyles.COLORS["frame_bg"])
            self.notebook.add(self.training_tab, text="Training")
            
            # Setup Thoth AI tab content
            self._setup_thoth_tab()
            
            # Setup AI Models tab content
            self._setup_ai_models_tab()
            
            # Setup Training tab content
            self._setup_training_tab()
            
            # Create status bar
            self._create_status_bar()
            
        except Exception as e:
            self.logger.error(f"Error creating AI layout: {e}")
    
    def _setup_thoth_tab(self):
        """Set up the Thoth AI tab."""
        try:
            # Create Thoth header
            header_frame = tk.Frame(self.thoth_tab, bg=KingdomStyles.COLORS["frame_bg"])
            header_frame.pack(fill=tk.X, padx=10, pady=5)
            
            header_label = tk.Label(
                header_frame, 
                text="ThothAI Interface",
                font=("Orbitron", 14, "bold"),
                fg=KingdomStyles.COLORS["thoth"],
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            header_label.pack(side=tk.LEFT, pady=5)
            
            self.status_indicator = tk.Label(
                header_frame,
                text="●",
                font=("Arial", 16),
                fg="#ff3a3a",  # Start with red (disconnected)
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            self.status_indicator.pack(side=tk.RIGHT, padx=10)
            
            # Create query input area
            input_frame = tk.Frame(self.thoth_tab, bg=KingdomStyles.COLORS["frame_bg"])
            input_frame.pack(fill=tk.X, padx=10, pady=5)
            
            query_label = tk.Label(
                input_frame,
                text="Query:",
                font=("Segoe UI", 10),
                fg=KingdomStyles.COLORS["text"],
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            query_label.pack(side=tk.LEFT, padx=5)
            
            self.query_input = tk.Entry(
                input_frame,
                font=("Consolas", 10),
                bg=KingdomStyles.COLORS["panel_bg"],
                fg=KingdomStyles.COLORS["text"],
                insertbackground=KingdomStyles.COLORS["text"]
            )
            self.query_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            send_button = self.create_button(
                text="Send",
                command=self._send_query,
                parent=input_frame
            )
            send_button.pack(side=tk.RIGHT, padx=5)
            
            # Create response area
            response_frame = tk.Frame(self.thoth_tab, bg=KingdomStyles.COLORS["frame_bg"])
            response_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            response_label = tk.Label(
                response_frame,
                text="Response:",
                font=("Segoe UI", 10),
                fg=KingdomStyles.COLORS["text"],
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            response_label.pack(side=tk.TOP, anchor=tk.W, padx=5, pady=2)
            
            # Add scrollbar for response text
            response_scroll = tk.Scrollbar(response_frame)
            response_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.response_text = tk.Text(
                response_frame,
                height=10,
                font=("Consolas", 9),
                bg=KingdomStyles.COLORS["panel_bg"],
                fg=KingdomStyles.COLORS["text"],
                wrap=tk.WORD,
                yscrollcommand=response_scroll.set
            )
            self.response_text.pack(fill=tk.BOTH, expand=True)
            response_scroll.config(command=self.response_text.yview)
            
            # Disable text widget (read-only)
            self.response_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.logger.error(f"Error setting up Thoth tab: {e}")
    
    def _setup_ai_models_tab(self):
        """Set up the AI Models tab."""
        try:
            # Create models header
            header_frame = tk.Frame(self.ai_tab, bg=KingdomStyles.COLORS["frame_bg"])
            header_frame.pack(fill=tk.X, padx=10, pady=5)
            
            header_label = tk.Label(
                header_frame, 
                text="AI Models",
                font=("Orbitron", 14, "bold"),
                fg=KingdomStyles.COLORS["primary"],
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            header_label.pack(side=tk.LEFT, pady=5)
            
            # Create model selection area
            model_frame = tk.Frame(self.ai_tab, bg=KingdomStyles.COLORS["frame_bg"])
            model_frame.pack(fill=tk.X, padx=10, pady=5)
            
            model_label = tk.Label(
                model_frame,
                text="Model:",
                font=("Segoe UI", 10),
                fg=KingdomStyles.COLORS["text"],
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            model_label.pack(side=tk.LEFT, padx=5)
            
            # Placeholder models
            models = ["GPT-3.5", "GPT-4", "Claude 2", "LLAMA 2", "Gemini"]
            
            self.model_selector = ttk.Combobox(
                model_frame,
                values=models,
                state="readonly"
            )
            self.model_selector.current(0)  # Default to first model
            self.model_selector.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            load_button = self.create_button(
                text="Load Model",
                command=self._load_model,
                parent=model_frame
            )
            load_button.pack(side=tk.RIGHT, padx=5)
            
            # Create model info area
            info_frame = tk.Frame(self.ai_tab, bg=KingdomStyles.COLORS["frame_bg"])
            info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            # Create model statistics
            stats_frame = tk.LabelFrame(
                info_frame,
                text="Model Statistics",
                font=("Segoe UI", 10, "bold"),
                fg=KingdomStyles.COLORS["text"],
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            stats_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # Add some placeholder stats
            stats = [
                ("Parameters", "175 Billion"),
                ("Context Length", "8,192 tokens"),
                ("Training Data", "Up to 2023"),
                ("Performance Score", "9.7/10")
            ]
            
            for i, (label, value) in enumerate(stats):
                tk.Label(
                    stats_frame,
                    text=label,
                    font=("Segoe UI", 9),
                    fg=KingdomStyles.COLORS["text"],
                    bg=KingdomStyles.COLORS["frame_bg"],
                    anchor=tk.W
                ).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
                
                tk.Label(
                    stats_frame,
                    text=value,
                    font=("Segoe UI", 9),
                    fg=KingdomStyles.COLORS["primary"],
                    bg=KingdomStyles.COLORS["frame_bg"],
                    anchor=tk.W
                ).grid(row=i, column=1, sticky=tk.W, padx=5, pady=2)
            
        except Exception as e:
            self.logger.error(f"Error setting up AI Models tab: {e}")
    
    def _setup_training_tab(self):
        """Set up the Training tab."""
        try:
            # Create training header
            header_frame = tk.Frame(self.training_tab, bg=KingdomStyles.COLORS["frame_bg"])
            header_frame.pack(fill=tk.X, padx=10, pady=5)
            
            header_label = tk.Label(
                header_frame, 
                text="Model Training",
                font=("Orbitron", 14, "bold"),
                fg=KingdomStyles.COLORS["success"],
                bg=KingdomStyles.COLORS["frame_bg"]
            )
            header_label.pack(side=tk.LEFT, pady=5)
            
            # Create placeholder content for training tab
            content = "Model training functionality will be implemented in a future update."
            
            placeholder = tk.Label(
                self.training_tab,
                text=content,
                font=("Segoe UI", 10),
                fg=KingdomStyles.COLORS["text"],
                bg=KingdomStyles.COLORS["frame_bg"],
                wraplength=400,
                justify=tk.CENTER
            )
            placeholder.pack(expand=True, pady=50)
            
        except Exception as e:
            self.logger.error(f"Error setting up Training tab: {e}")
    
    def _send_query(self):
        """Send a query to the Thoth AI system."""
        try:
            query = self.query_input.get().strip()
            
            if not query:
                self.show_error("Please enter a query")
                return
            
            # Clear input field
            self.query_input.delete(0, tk.END)
            
            # Update response area
            self.response_text.config(state=tk.NORMAL)
            self.response_text.insert(tk.END, f"\n> {query}\n\n")
            self.response_text.insert(tk.END, "Processing query...\n")
            self.response_text.see(tk.END)
            self.response_text.config(state=tk.DISABLED)
            
            # Record query time
            self.ai_status["last_query_time"] = datetime.now()
            
            # Publish query event
            if self.event_bus:
                self.event_bus.publish_sync("thoth.query", {
                    "query": query,
                    "timestamp": datetime.now().isoformat(),
                    "source": "ai_frame"
                })
            
            # Update status
            self.update_status(f"Query sent: {query[:30]}...", 50)
            
        except Exception as e:
            self.logger.error(f"Error sending query: {e}")
            self.show_error(f"Error sending query: {e}")
    
    def _load_model(self):
        """Load the selected AI model."""
        try:
            model = self.model_selector.get()
            
            if not model:
                self.show_error("Please select a model")
                return
            
            # Update status
            self.update_status(f"Loading model: {model}", 25)
            
            # Publish model load event
            if self.event_bus:
                self.event_bus.publish_sync("ai.model.load", {
                    "model": model,
                    "timestamp": datetime.now().isoformat(),
                    "source": "ai_frame"
                })
            
            # Update UI to show loading state
            self.model_selector.config(state="disabled")
            
        except Exception as e:
            self.logger.error(f"Error loading model: {e}")
            self.show_error(f"Error loading model: {e}")
    
    def _handle_ai_status(self, event_data):
        """Handle AI status events."""
        try:
            # Update local status
            self.ai_status.update(event_data)
            
            # Update UI based on status
            if "thoth_connected" in event_data:
                if event_data["thoth_connected"]:
                    self.status_indicator.config(fg="#00ff7f")  # Green
                else:
                    self.status_indicator.config(fg="#ff3a3a")  # Red
            
            # Log status update
            self.logger.info(f"AI status updated: {event_data}")
            
        except Exception as e:
            self.logger.error(f"Error handling AI status: {e}")
    
    def _handle_ai_response(self, event_data):
        """Handle AI response events."""
        try:
            if "response" in event_data:
                response = event_data["response"]
                
                # Update response area
                self.response_text.config(state=tk.NORMAL)
                self.response_text.insert(tk.END, f"{response}\n\n")
                self.response_text.see(tk.END)
                self.response_text.config(state=tk.DISABLED)
                
                # Update status
                self.update_status("Response received", 100)
                
        except Exception as e:
            self.logger.error(f"Error handling AI response: {e}")
    
    def _handle_model_loaded(self, event_data):
        """Handle model loaded events."""
        try:
            if "model" in event_data and "success" in event_data:
                model = event_data["model"]
                success = event_data["success"]
                
                if success:
                    # Update status
                    self.update_status(f"Model loaded: {model}", 100)
                    
                    # Update active model
                    self.ai_status["active_model"] = model
                    
                    # Add to loaded models if not already there
                    if model not in self.ai_status["models_loaded"]:
                        self.ai_status["models_loaded"].append(model)
                else:
                    # Update status
                    self.update_status(f"Failed to load model: {model}", 0)
                    
                    # Show error
                    error_message = event_data.get("error", "Unknown error")
                    self.show_error(f"Failed to load model: {error_message}")
                
                # Re-enable model selector
                self.model_selector.config(state="readonly")
                
        except Exception as e:
            self.logger.error(f"Error handling model loaded: {e}")
    
    def _handle_thoth_status(self, event_data):
        """Handle Thoth status events."""
        try:
            if "connected" in event_data:
                connected = event_data["connected"]
                
                # Update connection status
                self.ai_status["thoth_connected"] = connected
                
                # Update status indicator
                if connected:
                    self.status_indicator.config(fg="#00ff7f")  # Green
                    self.update_status("Connected to ThothAI", 100)
                else:
                    self.status_indicator.config(fg="#ff3a3a")  # Red
                    self.update_status("Disconnected from ThothAI", 0)
                
        except Exception as e:
            self.logger.error(f"Error handling Thoth status: {e}")
