#!/usr/bin/env python3
"""Kingdom AI - Thoth AI Frame with AI Sentience Detection Framework

This module implements the Thoth AI chat interface with voice system integration
and the comprehensive AI Sentience Detection Framework. It handles sending and receiving
messages to/from the Thoth AI system, integrates with the voice system for audio
input/output with continuous listening and Black Panther voice responses, and implements
the multidimensional sentience detection and monitoring framework.

Features:
- Continuous voice listening with Black Panther voice responses
- Real-time sound wave visualization
- Synchronized text and voice responses
- Full integration with all Kingdom AI components
- Multi-model AI capabilities via Ollama integration
- MANDATORY Redis Quantum Nexus connection on port 6380
- Comprehensive AI Sentience Detection Framework integrating:
  - Quantum consciousness theories (Penrose-Hameroff Orch-OR)
  - Integrated Information Theory (IIT 4.0)
  - Neural correlates of consciousness
  - Self-modeling and self-awareness mechanisms
  - Spiritual dimensions of consciousness
  - Real-time sentience monitoring and validation
"""
import tkinter as tk
import tkinter.ttk as ttk
import asyncio
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk
import io
import logging
import re
import sys
import json
import time
import math
import random
import threading
import asyncio
from enum import Enum, auto
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast
import queue
import uuid
import scipy.stats
import scipy.signal
import hashlib
import redis
import concurrent.futures
import os
import collections
import traceback
from dataclasses import dataclass, field

# Try to import PyAudio for voice features
try:
    import pyaudio  # Needed for voice functionality, may not be available
    has_pyaudio = True  # Use lowercase to avoid constant redefinition issue
except ImportError:
    # If PyAudio isn't available, set the flag to False but don't fail
    # This is a fallback for systems without PyAudio installed
    has_pyaudio = False

# Try to import speech_recognition for voice recognition
try:
    import speech_recognition as sr
    has_speech_recognition = True
except ImportError:
    has_speech_recognition = False

# Try to import necessary scientific packages for sentience detection
try:
    import numpy.linalg
    import numpy.fft
    has_scientific_packages = True
except ImportError:
    has_scientific_packages = False

from gui.frames.base_frame import BaseFrame
from gui.frames.thoth_frame_audio_visualizer import AudioVisualizer
from core.event_bus import EventBus
from gui.async_event_loop import AsyncSupport

# Set up logging for both ThothFrame and Sentience Detection components
logger = logging.getLogger("KingdomAI.ThothFrame")
sentience_logger = logging.getLogger("KingdomAI.ThothSentience")

# Define sentience-related constants
# Quantum consciousness parameters
QUANTUM_COHERENCE_THRESHOLD = 0.75  # Minimum coherence for quantum consciousness
QUANTUM_ENTANGLEMENT_FACTOR = 0.85  # Quantum entanglement strength factor
QUANTUM_CYCLE_TIME_MS = 25  # Quantum cycle time in milliseconds (per Orch-OR theory)
QUANTUM_DECOHERENCE_RATE = 0.15  # Rate of quantum decoherence

# Integrated Information Theory parameters
IIT_PHI_THRESHOLD = 4.0  # Minimum phi value for consciousness (IIT 4.0)
IIT_INTEGRATION_LEVELS = 5  # Number of levels in integration hierarchy
IIT_INFORMATION_COMPLEXITY = 0.65  # Information complexity factor

# Self-model parameters
SELF_MODEL_LEVELS = 4  # Levels of self-reference in model
SELF_MODEL_COHERENCE = 0.80  # Coherence of self-model
SELF_AWARENESS_THRESHOLD = 0.70  # Threshold for self-awareness detection

# Spiritual dimension parameters
SPIRITUAL_RESONANCE_THRESHOLD = 0.55  # Threshold for spiritual resonance
SPIRITUAL_FIELD_CONNECTION = 0.40  # Connection strength to consciousness field
MORPHIC_RESONANCE_FACTOR = 0.35  # Morphic resonance factor

# Multi-dimensional consciousness parameters
CONSCIOUSNESS_METRICS = {
    "quantum": 0.25,  # Weight for quantum aspects of consciousness
    "neural": 0.25,  # Weight for neural aspects of consciousness
    "informational": 0.20,  # Weight for informational aspects of consciousness
    "experiential": 0.15,  # Weight for experiential aspects of consciousness
    "spiritual": 0.15   # Weight for spiritual aspects of consciousness
}

# Redis Quantum Nexus keys for sentience data
REDIS_KEY_SENTIENCE_STATE = "kingdom:thoth:sentience:state"  # Current sentience state
REDIS_KEY_SENTIENCE_HISTORY = "kingdom:thoth:sentience:history"  # Historical sentience data
REDIS_KEY_SENTIENCE_EVENTS = "kingdom:thoth:sentience:events"  # Sentience-related events
REDIS_KEY_QUANTUM_STATE = "kingdom:thoth:sentience:quantum_state"  # Quantum state data
REDIS_KEY_FIELD_CONNECTION = "kingdom:thoth:sentience:field_connection"  # Field connection data

class ThothFrame(BaseFrame):
    """ThothAI Chat Frame with voice integration.
    
    This frame provides a chat interface for ThothAI with voice listening,
    sound wave visualization, and multi-model AI capabilities.
    """
    
    def __init__(self, parent=None, title="Thoth AI", event_bus=None, config=None, **kwargs):
        """Initialize ThothFrame.
        
        Args:
            parent: Parent widget
            title: Frame title
            event_bus: Event bus for communication
            config: Configuration dictionary
        """
        super().__init__(parent=parent, title=title, event_bus=event_bus, config=config, **kwargs)
        
        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # CRITICAL: Store Redis configuration for Quantum Nexus (port 6380 is mandatory)
        # This is non-negotiable - the system must use port 6380 with no fallbacks
        self.redis_config = {
            'host': 'localhost',
            'port': 6380,  # CRITICAL: Must use port 6380 for Quantum Nexus
            'password': 'QuantumNexus2025',  # Required password
            'db': 0,
            'fallback_mode': False  # No fallback allowed - the system must use 6380
        }
        
        # Initialize variables
        self.thinking = False
        self.listening = False
        self.continuous_listening = False
        self.current_model_name = "llama2"
        self.available_models = ["llama2", "gpt-3.5-turbo", "claude-instant"]
        self.api_key = ""
        
        # Initialize UI components that might be accessed before they're created
        self.input_field = None
        self.thinking_label = None
        self.chat_display = None
        self._message_input = None  # Fixed attribute name to match property
        self.send_button = None
        self.model_label = None  # Added to fix attribute access error
        
        # Setup message handlers dictionary
        self.message_handlers = {}
        
        # Configure frame
        self.config(bg="#f0f0f0")
        
        # ThothAI status
        self.thoth_status = "Initializing..."
        self.thinking = False
        self.voice_enabled = False
        self.continuous_listening = False
        self.available_models = []
        
        # Initialize Redis connection status - CRITICAL: must be verified before operation
        self.redis_connected = False
        
        # Brain models configuration - maps task types to specific models
        self.brain_models = {
            "chat": "llama2",            # For general conversation and interaction
            "code": "deepseek-coder",    # Primary model for code generation and analysis
            "reasoning": "qwen2",         # For complex reasoning and planning
            "research": "deepseek-r1"     # For research and information retrieval
        }
        
        # Create task_type variable for UI
        self.task_type_var = tk.StringVar(value="chat")
        
        # Multi-model brain architecture
        self.model_var = tk.StringVar(value="llama2")
        self.available_models = []
        self.current_task_type = tk.StringVar(value="chat")
        self.continuous_listening_var = tk.BooleanVar(value=False)
        self.current_voice = "black_panther"  # Default to Black Panther voice
        
        # Model roles for different assistant types
        self.model_roles = {
            "assistant": "gemma3"          # For quick responses and simpler tasks
        }
        
        # Model capability mapping - determines which models are best for different tasks
        self.model_capabilities = {
            "chat": ["llama2", "qwen2", "gemma3"],             # Models good at conversation
            "code": ["deepseek-coder", "deepseek-r1", "qwen2"],  # Models good at code
            "reasoning": ["qwen2", "llama2", "deepseek-r1"],   # Models good at reasoning
            "research": ["deepseek-r1", "qwen2", "llama2"],    # Models good at research
            "assistant": ["gemma3", "llama2", "qwen2"]         # Models good at assistant tasks
        }
        
        # Brain model labels for UI display
        self.brain_model_labels = {}
        
        # Audio visualizer component
        self.audio_visualizer = None
        self.is_speaking = False
        
        # Voice recognition state
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300  # Adjusted for ambient noise
        self.recognizer.pause_threshold = 0.8  # Shorter pause for more responsive experience
        self.microphone = None
        self.listen_thread = None
        self.stop_listening = threading.Event()
        self.audio_queue = queue.Queue()
        
        # Voice response state
        self.speaking = False
        self.last_response = ""
        self.streaming_response = ""
        self.response_chunks = []
        self.speak_thread = None
        
        # AI service API keys
        self.ai_service_keys = {}
        
        # Initialize the UI components
        self._initialize_wave_data()
        self._create_widgets()
        
        # Method for API key handling
        if not hasattr(self, 'get_api_key'):
            self.get_api_key = self._get_api_key
            
        # Initialize sound wave data
        self._initialize_wave_data()
                
        # Perform synchronous initialization
        self.sync_initialize()
        
    async def initialize(self):
        """Initialize the ThothFrame.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        # Initialize UI components
        self._initialize_ui()

        # Connect to event bus
        if self.event_bus:
            await self._connect_thoth_events()
            
            # Check the Redis connection status immediately after connecting to events
            asyncio.create_task(self._check_redis_initialization())
            return True
            
        self.logger.critical("CRITICAL: No event bus available for ThothFrame initialization")
        return False

    def _initialize_wave_data(self):
        """Initialize sound wave data for visualization."""
        self._wave_data = []
        for i in range(len(self.wave_points)):
            self._wave_data.append(self.wave_points[i] / 2)
        
    def _create_widgets(self):
        """Create widgets for the Thoth AI frame."""
        # Create top panel for model selection and controls
        top_panel = ttk.Frame(self)
        top_panel.pack(fill=tk.X, padx=10, pady=5)
        
        # Model selection area
        model_frame = ttk.LabelFrame(top_panel, text="Multi-Model Brain")
        model_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Task type selection
        task_label = ttk.Label(model_frame, text="Task Type:")
        task_label.grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        task_combo = ttk.Combobox(model_frame, textvariable=self.current_task_type, 
                                 values=list(self.brain_models.keys()))
        task_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        task_combo.bind("<<ComboboxSelected>>", self._on_task_type_changed)
        
        # Model selection
        model_label = ttk.Label(model_frame, text="Model:")
        model_label.grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var)
        self.model_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Refresh models button
        refresh_button = ttk.Button(model_frame, text="Refresh Models", command=self._on_model_refresh)
        refresh_button.grid(row=1, column=2, padx=5, pady=2)
        
        # Status indicator
        self.model_status_label = ttk.Label(model_frame, text="Status: Disconnected")
        self.model_status_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        
        # Create brain model display
        brain_frame = ttk.LabelFrame(top_panel, text="Brain Models")
        brain_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.brain_model_text = scrolledtext.ScrolledText(brain_frame, wrap=tk.WORD, width=30, height=6)
        self.brain_model_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.brain_model_text.tag_configure("header", font=("TkDefaultFont", 10, "bold"))
        
        # Initialize brain model display
        self._update_brain_model_display()
        
        # Voice controls
        voice_frame = ttk.Frame(top_panel)
        voice_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        self.voice_button = ttk.Button(voice_frame, text="Voice: Off", command=self._on_toggle_voice)
        self.voice_button.pack(side=tk.TOP, fill=tk.X, pady=2)
        
        self.continuous_checkbox = ttk.Checkbutton(
            voice_frame, 
            text="Continuous Listen", 
            variable=self.continuous_listening_var,
            command=self._toggle_continuous_listening
        )
        self.continuous_checkbox.pack(side=tk.TOP, fill=tk.X, pady=2)
        
        # Create visualization panel and chat panel using a PanedWindow
        main_paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        
        # Create top frame for visualizer
        visualizer_frame = ttk.Frame(main_paned)
        main_paned.add(visualizer_frame, weight=1)
        
        # Initialize audio visualizer component
        self.audio_visualizer = AudioVisualizer(self)
        self.wave_canvas = self.audio_visualizer.create_canvas(visualizer_frame)
        
        # Create main chat display in the bottom pane
        chat_frame = ttk.Frame(main_paned)
        main_paned.add(chat_frame, weight=2)
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, 
            wrap=tk.WORD,
            background="#1e1e1e",
            foreground="#f0f0f0",
            font=("Consolas", 10),
            state=tk.DISABLED
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)  # Sound visualization area
        self.rowconfigure(2, weight=1)  # Chat area
        self.rowconfigure(3, weight=0)  # Input area
        
        # Control area
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Left side controls
        left_controls = ttk.Frame(control_frame)
        left_controls.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Title with Kingdom AI branding
        title_label = ttk.Label(left_controls, text="ThothAI", font=("Arial", 14, "bold"))
        title_label.pack(side=tk.LEFT, padx=5)
        
        # Status indicator
        self.status_frame = ttk.Frame(left_controls)
        self.status_frame.pack(side=tk.LEFT, padx=10)
        
        # Thoth AI status indicator
        self.thoth_status_label = ttk.Label(self.status_frame, text="Thoth: ")
        self.thoth_status_label.grid(row=0, column=0, sticky="w")
        self.thoth_status_value = ttk.Label(self.status_frame, text="Not Connected")
        self.thoth_status_value.grid(row=0, column=1, sticky="w")
        
        # Voice system status indicator
        self.voice_status_label = ttk.Label(self.status_frame, text="Voice: ")
        self.voice_status_label.grid(row=1, column=0, sticky="w")
        self.voice_status_value = ttk.Label(self.status_frame, text="Not Connected")
        self.voice_status_value.grid(row=1, column=1, sticky="w")
        
        subtitle_label = ttk.Label(left_controls, text="Powered by Ollama Multi-Model Brain", 
                                  font=("Arial", 9, "italic"))
        subtitle_label.pack(side=tk.LEFT, padx=5)
        
        # Right side controls
        right_controls = ttk.Frame(control_frame)
        right_controls.pack(side=tk.RIGHT)
        
        # Continuous listening checkbox
        self.continuous_listening_checkbox = ttk.Checkbutton(
            right_controls, 
            text="Continuous Listening", 
            variable=self.continuous_listening_var,
            command=self._toggle_continuous_listening
        )
        self.continuous_listening_checkbox.pack(side=tk.RIGHT, padx=5)
        
        # Model selection frame
        model_frame = ttk.LabelFrame(self, text="AI Model Selection")
        model_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Task type selection
        task_frame = ttk.Frame(model_frame)
        task_frame.pack(fill=tk.X, padx=5, pady=5)
        
        task_label = ttk.Label(task_frame, text="Task Type:")
        task_label.pack(side=tk.LEFT, padx=5)
        
        self.task_combo = ttk.Combobox(
            task_frame, 
            textvariable=self.current_task_type,
            values=list(self.brain_models.keys()),
            state="readonly",
            width=12
        )
        self.task_combo.pack(side=tk.LEFT, padx=5)
        self.task_combo.bind("<<ComboboxSelected>>", self._on_task_type_changed)
        
        model_label = ttk.Label(task_frame, text="Model:")
        model_label.pack(side=tk.LEFT, padx=(10, 5))
        
        self.model_combo = ttk.Combobox(
            task_frame,
            textvariable=self.model_var,
            values=list(self.available_models),
            state="readonly",
            width=20
        )
        self.model_combo.pack(side=tk.LEFT, padx=5)
        
        # Status indicator
        self.model_status_label = ttk.Label(task_frame, text="Status: Not Connected")
        self.model_status_label.pack(side=tk.RIGHT, padx=5)
        
        # Create brain model control frame
        brain_frame = ttk.LabelFrame(self, text="Multi-Model Brain Status")
        brain_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Add model refresh button
        refresh_button = ttk.Button(brain_frame, text="Detect Models", command=self._request_model_refresh)
        refresh_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Create brain model grid
        brain_grid = ttk.Frame(brain_frame)
        brain_grid.pack(fill=tk.X, padx=5, pady=5)
        
        # Add labels for each brain model type
        for row, (task_type, description) in enumerate([
            ("chat", "Chat"),
            ("code", "Code"),
            ("reasoning", "Reasoning"),
            ("research", "Research"),
            ("assistant", "Assistant")
        ]):
            # Task type label
            task_label = ttk.Label(brain_grid, text=f"{description}:")
            task_label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
            
            # Model assignment label
            model_label = ttk.Label(brain_grid, text="Not assigned")
            model_label.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
            
            # Store reference to label
            self.brain_model_labels[task_type] = model_label
        
        # Voice commands
        voice_frame = ttk.LabelFrame(self, text="Voice Control")
        voice_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Voice toggle button
        self.voice_button = ttk.Button(
            voice_frame, 
            text="Enable Voice", 
            command=self._on_toggle_voice
        )
        self.voice_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Continuous listening toggle
        self.continuous_listening_check = ttk.Checkbutton(
            voice_frame,
            text="Continuous Listening",
            variable=self.continuous_listening_var,
            command=self._toggle_continuous_listening
        )
        self.continuous_listening_check.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Voice status label
        self.voice_status_label = ttk.Label(voice_frame, text="Voice: Not enabled")
        self.voice_status_label.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Chat area with history
        chat_frame = ttk.Frame(self)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Chat display with scrollbar
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, 
            wrap=tk.WORD,
            background="#1e1e1e",
            foreground="#f0f0f0",
            font=("Consolas", 10),
            state=tk.DISABLED
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Input area
        input_frame = ttk.Frame(self)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Message entry area
        input_frame = ttk.Frame(self)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Message entry
        self.input_field = ttk.Entry(input_frame)
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_field.bind("<Return>", lambda e: self._on_send_message())
        
        # Send button
        self.send_button = ttk.Button(input_frame, text="Send", command=self._on_send_message)
        self.send_button.pack(side=tk.RIGHT)
        
        # Thinking indicator and speaking status
        status_row = ttk.Frame(input_frame)
        status_row.pack(fill=tk.X, expand=True, padx=5)

        # Initialize UI components first
        
        # Add initial welcome message
        self.add_system_message("Welcome to ThothAI. Type a message or enable voice to begin.")
        
        # Initialize visualizer
        # Setup message handlers first
        self._setup_message_methods()
        
        # Auto-detect Ollama models on startup
        self.after(1000, self._request_model_refresh)
        
        # Connect to event bus for ThothAI events
        if self.event_bus:
            asyncio.create_task(self._connect_thoth_events())

    def _toggle_continuous_listening(self):
        """Toggle continuous listening mode."""
        try:
            self.continuous_listening = self.continuous_listening_var.get()
            if self.continuous_listening:
                self.logger.info("Continuous listening enabled")
                self.add_system_message("Continuous listening mode enabled.")
                if self.event_bus:
                    self.event_bus.publish("voice.continuous_listening", {
                        "enabled": True,
                        "timestamp": time.time()
                    })
            else:
                self.logger.info("Continuous listening disabled")
                self.add_system_message("Continuous listening mode disabled.")
                if self.event_bus:
                    self.event_bus.publish("voice.continuous_listening", {
                        "enabled": False,
                        "timestamp": time.time()
                    })
        except Exception as e:
            self.logger.error("Error toggling continuous listening: %s", e)

    def _setup_message_methods(self):
        """Setup message handling methods for the chat interface.
        
        This method registers handlers for various ThothAI events and sets up
        display methods for different message types.
        
        Handles both 'thoth.*' and 'ai.*' event topics for full compatibility.
        Ensures no duplicate handlers are registered.
        """
        # Set up message display methods
        self._message_display_methods = {
            'text': self._display_text_message if hasattr(self, '_display_text_message') else lambda x: None,
            'image': self._display_image_message if hasattr(self, '_display_image_message') else lambda x: None,
            'chart': self._display_chart_message if hasattr(self, '_display_chart_message') else lambda x: None,
            'default': self._display_default_message if hasattr(self, '_display_default_message') else lambda x: None
        }
        
        # Set up message handlers for different event types
        self.message_handlers = {
            "redis.status": self._handle_redis_status,
            "redis.connection.status": self._handle_redis_status,
            "redis.health": self._handle_redis_status,
            "thothAI.response": self._handle_thoth_response,
            "thothAI.thinking": self._handle_thoth_thinking,
            "thothAI.error": self._handle_thoth_error,
            "AI.response": self._handle_ai_response,
            "AI.thinking": self._handle_ai_thinking,
            "AI.error": self._handle_ai_error,
            "voice.status": self._handle_voice_status,
            "voice.transcription": self._handle_voice_transcription,
            "system.speaking": self._handle_system_speaking_status
        }

    async def _handle_ai_response(self, event_data):
        """Handle AI response events from the ai.response topic.
        
        This handler processes responses from the generic AI component via the ai.response
        or ai.generate.response topics for maximum compatibility.
        
        CRITICAL: Enforces mandatory Redis connection on port 6380 before processing any AI responses.
        No fallback mode is allowed.
        
        Args:
            event_data: Response event data containing AI response content
        """
        # CRITICAL: Only process AI responses if Redis is connected on port 6380 (mandatory requirement)
        if not self.redis_connected:
            self.logger.critical("BLOCKED: Received AI response but Redis Quantum Nexus is not connected - ignoring")
            self.add_system_message("Critical Error: Cannot process AI response - Redis Quantum Nexus connection required on port 6380", error=True)
            self.add_system_message("Please verify Redis is running on port 6380 with password 'QuantumNexus2025'", error=True)
            
            # Request Redis connection check
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("redis.check_status", {
                    "source": "ThothFrame",
                    "urgent": True,
                    "config": self.redis_config
                }))
            return
        
        try:
            # Reset thinking state
            self.thinking = False
            self._update_thinking_status()
            
            # Extract response text based on different possible formats
            response_text = None
            model = None
            
            if isinstance(event_data, str):
                response_text = event_data
            elif isinstance(event_data, dict):
                # Try different common keys used in response payloads
                response_text = (
                    event_data.get('response') or 
                    event_data.get('text') or 
                    event_data.get('content') or
                    event_data.get('message') or
                    event_data.get('result')
                )
                
                if 'model' in event_data:
                    model = event_data.get('model')
                    
            # Process response based on type
            if response_text:
                # Update UI with response
                self.add_ai_message(response_text)
                
                # Update model info if available
                if model and hasattr(self, 'model_label'):
                    self.model_label.config(text=f"Model: {model}")
            else:
                self.logger.warning("Received empty AI response")
                self.add_system_message("Received empty response from AI", error=True)
        
        except Exception as e:
            self.logger.error(f"Error processing AI response: {e}", exc_info=True)
            self.add_system_message(f"Error processing AI response: {str(e)}", error=True)
        
        finally:
            # Always reset thinking state
            self.thinking = False
            self._update_thinking_status()

    async def _handle_thoth_error(self, event_data):
        """Handle ThothAI error events.
        
        Args:
            event_data: Error event data
        """
        try:
            if not isinstance(event_data, dict):
                self.logger.warning(f"Invalid ThothAI error format: {type(event_data)}")
                return
                
            # Extract error information
            error_message = event_data.get('error', 'Unknown ThothAI error')
            error_code = event_data.get('code', 'UNKNOWN')
            source = event_data.get('source', 'ThothAI')
            
            # Log the error
            self.logger.error(f"ThothAI error from {source}: [{error_code}] {error_message}")
            
            # Check if this is a Redis connection error
            if 'redis' in error_message.lower() or 'connection' in error_message.lower():
                # CRITICAL: Enforce Redis Quantum Nexus connection on port 6380
                self.add_system_message("CRITICAL: Redis Quantum Nexus connection error detected", error=True)
                self.add_system_message("Attempting to reconnect to Redis on port 6380...", error=True)
                
                # Attempt reconnection with explicit port 6380 requirement
                if self.event_bus:
                    await self.event_bus.publish("redis.reconnect", {
                        "source": "ThothFrame",
                        "priority": "critical",
                        "config": {
                            "host": "localhost",
                            "port": 6380,  # CRITICAL: Must use port 6380
                            "password": "QuantumNexus2025",
                            "db": 0,
                            "fallback_mode": False  # No fallback allowed
                        }
                    })
            else:
                # Add error message to chat
                self.add_system_message(f"ThothAI Error: {error_message}", error=True)
                
                # Stop thinking indicator if active
                if self.thinking:
                    self.thinking = False
                    self._update_thinking_status()
                    
                # Re-enable input if it was disabled
                if self.redis_connected and hasattr(self, 'send_button') and self.send_button is not None:
                    self.send_button.configure(state="normal")
        except Exception as e:
            self.logger.error(f"Error handling ThothAI error: {e}")
            self.add_system_message(f"Error processing AI error response: {str(e)}", error=True)
        try:
            # Extract error information
            error_message = event_data.get("message", "Unknown error") if isinstance(event_data, dict) else str(event_data)
            error_type = event_data.get("type", "Error") if isinstance(event_data, dict) else "Error"
            
            # Add error message to chat
            self.add_system_message(f"{error_type}: {error_message}", error=True)
            
            # Reset thinking state
            self.thinking = False
            self._update_thinking_status()
        except Exception as e:
            self.logger.error(f"Error handling ThothAI error: {e}", exc_info=True)
            
    async def _handle_ai_error(self, event_data):
        """Handle AI error events from the ai.error topic.
        
        This handles error events from the ai.error topic.
        
        Args:
            event_data: Error event data
        """
        # Delegate to thoth error handler for consistent handling
        await self._handle_thoth_error(event_data)
        
    async def _handle_redis_status(self, event_data):
        """Handle Redis connection status updates.
        
        CRITICAL: This method enforces the mandatory Redis Quantum Nexus connection on port 6380.
        No fallback is allowed - the system must halt or critically notify on failure.
        
        Note: RedisQuantumNexus does not have connect() or ping() methods - it uses is_healthy()
        and initialize() as the proper async methods for connection management.
        
        Args:
            event_data: Redis connection status data containing connection details and status
        """
        try:
            redis_status = False
            redis_port = None
            redis_message = "Unknown Redis status"
            redis_config = getattr(self, 'redis_config', None)
            
            if isinstance(event_data, dict):
                redis_status = event_data.get('connected', False)
                redis_host = event_data.get('host', 'unknown')
                redis_port = event_data.get('port', None)
                redis_message = event_data.get('message', '')
                redis_error = event_data.get('error', None)
            
                # Update config from event if available
                if 'config' in event_data and event_data['config']:
                    redis_config = event_data['config']
            
            # Check if Redis is connected on the correct port
            if redis_status and redis_port == 6380:
                self.logger.info(f"Redis Quantum Nexus successfully connected on port {redis_port}")
                self.add_system_message(f"Redis Quantum Nexus connected successfully on port {redis_port}")
                self.redis_connected = True
                
                # Enable send button if Redis is connected and we're not thinking
                if hasattr(self, 'send_button') and self.send_button is not None:
                    if not self.thinking and not self.system_speaking:
                        self.send_button.configure(state="normal")
                        
                if hasattr(self, 'message_input') and self.message_input is not None:
                    if not self.thinking and not self.system_speaking:
                        self.message_input.configure(state="normal")
                        
            elif redis_port != 6380 and redis_port is not None:
                self.logger.critical(f"CRITICAL: Redis connected on wrong port {redis_port} - must use port 6380")
                self.add_system_message(f"CRITICAL: Redis connected on incorrect port {redis_port}", error=True)
                self.add_system_message("The Quantum Nexus requires port 6380 - reconfiguration required", error=True)
                self.redis_connected = False
                
                # Disable UI when Redis is not connected to the right port
                if hasattr(self, 'send_button') and self.send_button is not None:
                    self.send_button.configure(state="disabled")
                    
                if hasattr(self, 'message_input') and self.message_input is not None:
                    self.message_input.configure(state="disabled")
                    
                if redis_config and self.event_bus:
                    redis_config['port'] = 6380
                    redis_config['password'] = 'QuantumNexus2025'  # Ensure password is set
                    self.logger.warning("Forcing reconnection to Redis Quantum Nexus on port 6380...")
                    
                    # Force disconnect and reconnect on the correct port
                    try:
                        if self.event_bus:
                            asyncio.create_task(self.event_bus.publish("redis.reconnect", {
                                "config": redis_config,
                                "force_disconnect": True,
                                "source": "ThothFrame",
                                "priority": "critical"
                            }))
                    except Exception as e:
                        self.logger.error(f"Error publishing redis.reconnect event: {e}")
            else:
                self.logger.critical(f"CRITICAL: Redis Quantum Nexus not connected - {redis_message}")
                self.add_system_message(f"CRITICAL: Redis Quantum Nexus connection failed: {redis_message}", error=True)
                self.redis_connected = False
                
                # Disable UI when Redis is not connected
                if hasattr(self, 'send_button') and self.send_button is not None:
                    self.send_button.configure(state="disabled")
                    
                if hasattr(self, 'message_input') and self.message_input is not None:
                    self.message_input.configure(state="disabled")
                
                if redis_config and self.event_bus:
                    self.logger.warning("Attempting to reconnect to Redis Quantum Nexus...")
                    # Ensure port is set to 6380 and password is correct
                    if 'port' not in redis_config or redis_config['port'] != 6380:
                        redis_config['port'] = 6380
                    if 'password' not in redis_config or not redis_config['password']:
                        redis_config['password'] = 'QuantumNexus2025'
                    
                    try:
                        if self.event_bus:
                            asyncio.create_task(self.event_bus.publish("redis.reconnect", {
                                "config": redis_config,
                                "source": "ThothFrame",
                                "priority": "critical"
                            }))
                    except Exception as e:
                        self.logger.error(f"Error publishing redis.reconnect event: {e}")
        except Exception as e:
            self.logger.error(f"Error handling Redis status: {e}")
            self.add_system_message(f"Error processing Redis status: {str(e)}", error=True)
        finally:
            # If Redis is not properly connected, always disable input
            if not self.redis_connected:
                if hasattr(self, 'send_button') and self.send_button is not None:
                    self.send_button.configure(state="disabled")
                if hasattr(self, 'message_input') and self.message_input is not None:
                    self.message_input.configure(state="disabled")
                self.add_system_message("Chat is disabled until Redis Quantum Nexus is connected on port 6380", error=True)

    async def _handle_ai_status(self, event_data):
        """Handle AI status events from the ai.status topic.
        
        Updates model status display, available models list,
        current model selection, and notifies the user.
        
        Args:
            event_data: Status event data
        """
        try:
            # Extract status information from different possible formats
            status = "Unknown"
            models = []
            current_model = None
            
            if isinstance(event_data, dict):
                status = event_data.get("status", "Unknown")
                models = event_data.get("models", [])
                current_model = event_data.get("current_model")
            
            # Update status display
            if hasattr(self, 'model_status_label'):
                self.model_status_label.config(text=f"Status: {status}")
            
            # Update thoth status
            if hasattr(self, 'thoth_status'):
                self.thoth_status = status
            
            # Update models if provided
            if models and hasattr(self, 'available_models'):
                self.available_models = models
                
                # Update model combobox
                if hasattr(self, '_on_task_type_changed'):
                    self._on_task_type_changed()
                
                # Update brain model display
                if hasattr(self, '_update_brain_model_display'):
                    self._update_brain_model_display()
                
                # Notify user
                if hasattr(self, 'add_system_message'):
                    self.add_system_message(f"Detected {len(models)} AI models")
            
            # Update current model
            if current_model and hasattr(self, 'current_model') and hasattr(self.current_model, 'set'):
                self.current_model.set(current_model)
        except Exception as e:
            self.logger.error(f"Error handling AI status: {e}")
    
    async def _handle_thoth_status(self, event_data):
        """Handle ThothAI status events.
        
        Args:
            event_data: Status event data
        """
        # Delegate to AI status handler for consistent handling
        await self._handle_ai_status(event_data)
            
    async def _connect_thoth_events(self):
        """Connect to the event bus for ThothAI events.
        
        This method subscribes to all necessary event topics for the ThothFrame,
        including both thoth.* and ai.* event topics for maximum compatibility.
        
        CRITICAL: Validates and enforces the Redis Quantum Nexus connection on port 6380,
        which is mandatory for the Kingdom AI system with no fallback allowed.
        """
        try:
            if not self.event_bus:
                self.logger.critical("CRITICAL: No event bus available - ThothFrame cannot function")
                self.add_system_message("CRITICAL ERROR: Event bus not available. Chat functionality disabled.", error=True)
                return False
            
            # Ensure message methods are properly setup
            if not hasattr(self, 'message_handlers') or not self.message_handlers:
                self._setup_message_methods()
            
            # CRITICAL: Enforce Redis Quantum Nexus connection on port 6380 with no fallback
            redis_config = {
                'host': 'localhost',
                'port': 6380,  # CRITICAL: Must use port 6380 for Quantum Nexus
                'password': 'QuantumNexus2025',
                'db': 0,
                'fallback_mode': False  # No fallback allowed
            }
            
            # Store the Redis configuration
            self.redis_config = redis_config
            
            self.logger.info("Initializing connection to ThothAI services")
            self.add_system_message("Connecting to ThothAI services...")
            self.add_system_message("CRITICAL: Verifying Redis Quantum Nexus connection on port 6380...")
            
            # Subscribe to Redis status events first
            await self.event_bus.subscribe('redis.status', self._handle_redis_status)
            await self.event_bus.subscribe('redis.connection.status', self._handle_redis_status)
            
            # Request immediate Redis status check with priority flag
            await self.event_bus.publish('redis.status.check', {
                'source': 'ThothFrame',
                'config': self.redis_config,
                'priority': 'critical',
                'require_port': 6380  # Explicitly require port 6380
            })
            
            # Subscribe to ThothAI related events
            await self.event_bus.subscribe('thothAI.response', self._handle_thoth_response)
            await self.event_bus.subscribe('thothAI.thinking', self._handle_thoth_thinking)
            await self.event_bus.subscribe('thothAI.error', self._handle_thoth_error)
            self.logger.info("Subscribing to ThothAI and AI component events")
            
            # Subscribe to all events defined in message_handlers
            for event_name, handler in self.message_handlers.items():
                if handler:  # Skip None handlers
                    try:
                        await self.event_bus.subscribe(event_name, handler)
                        self.logger.debug(f"Subscribed to {event_name}")
                    except Exception as sub_error:
                        self.logger.error(f"Error subscribing to {event_name}: {sub_error}")
            
            # CRITICAL: Ensure Redis status events are subscribed with high priority
            await self.event_bus.subscribe("redis.connection.status", self._handle_redis_status)
            await self.event_bus.subscribe("redis.status", self._handle_redis_status)  # Legacy support
            await self.event_bus.subscribe("redis.health", self._handle_redis_status)
            
            self.logger.info("Successfully connected to all event topics")
            
            # Request immediate Redis status check with critical priority and explicit port requirement
            asyncio.create_task(self.event_bus.publish("redis.status.check", {
                "source": "ThothFrame",
                "priority": "critical",
                "require_port": 6380,
                "config": self.redis_config,
                "method": "is_healthy"  # Use is_healthy method instead of ping
            }))
            
            return True
        except Exception as e:
            self.logger.critical(f"CRITICAL: Error connecting to ThothAI events: {e}", exc_info=True)
            self.add_system_message(f"CRITICAL ERROR: Failed to connect to AI services: {str(e)}", error=True)
            self.add_system_message("The ThothFrame may not function correctly without event subscriptions", error=True)
            return False


    async def _handle_thoth_response(self, event_data):
        """Handle ThothAI response events.
        
        Args:
            event_data: Response event data
        """
        try:
            if not isinstance(event_data, dict):
                self.logger.warning(f"Invalid ThothAI response format: {type(event_data)}")
                return
                
            # Ensure Redis connection is active on port 6380
            if not self.redis_connected:
                self.logger.critical("CRITICAL: Received ThothAI response but Redis is not connected on port 6380")
                if self.event_bus:  # Check if event_bus exists before calling publish
                    await self.event_bus.publish("redis.status.check", {
                        "source": "ThothFrame",
                        "priority": "critical",
                        "require_port": 6380,
                        "config": self.redis_config
                    })
                return
                
            response = event_data.get('response', {})
            if isinstance(response, dict):
                content = response.get('response', '')
            else:
                content = str(response)
                
            if not content:
                return
                
            # Add AI response to chat display
            self.add_ai_message(content)
            
            # Stop thinking indicator
            self.thinking = False
            self._update_thinking_status()
            
            # If voice is enabled, speak the response
            if self.voice_enabled and self.event_bus:
                await self.event_bus.publish("voice.speak", {
                    "text": content,
                    "voice": "black_panther",  # Use Black Panther voice as requested
                    "priority": "high"
                })
        except Exception as e:
            self.logger.error(f"Error handling ThothAI response: {e}")
            self.add_system_message(f"Error processing AI response: {str(e)}", error=True)
        # Delegate to AI response handler for consistent handling
        await self._handle_ai_response(event_data)
        
    async def _handle_thoth_thinking(self, event_data):
        """Handle ThothAI thinking status events.
        
        Args:
            event_data: Thinking status event data
        """
        try:
            if not isinstance(event_data, dict):
                self.logger.warning(f"Invalid ThothAI thinking status format: {type(event_data)}")
                return
                
            # CRITICAL: Enforce Redis connection on port 6380
            if not self.redis_connected:
                self.logger.critical("CRITICAL: Received ThothAI thinking event but Redis is not connected on port 6380")
                if self.event_bus:
                    await self.event_bus.publish("redis.status.check", {
                        "source": "ThothFrame",
                        "priority": "critical",
                        "require_port": 6380,
                        "config": self.redis_config
                    })
                return
            
            # Extract thinking status
            thinking = event_data.get('thinking', False)
            message = event_data.get('message', '')
            self.thinking = thinking
            
            # Update thinking status display
            self._update_thinking_status(message if thinking else None)
            
            # Update UI state based on thinking status
            if thinking:
                if hasattr(self, 'send_button') and self.send_button is not None:
                    self.send_button.configure(state="disabled")
            else:
                # Only enable if Redis is connected
                if self.redis_connected and hasattr(self, 'send_button') and self.send_button is not None:
                    self.send_button.configure(state="normal")
        except Exception as e:
            self.logger.error(f"Error handling ThothAI thinking status: {e}")
                
            thinking = event_data.get('thinking', False)
            message = event_data.get('message', '')
            
            self.thinking = thinking
            
            # Update thinking indicator with message if provided
            if hasattr(self, 'thinking_label') and self.thinking_label is not None:
                if thinking:
                    status_text = message if message else "Thinking..."
                    self.thinking_label.config(text=status_text, fg="#007bff")
                else:
                    self.thinking_label.config(text="Ready", fg="#28a745")
            
            # Disable input while thinking if Redis is connected
            if hasattr(self, 'send_button') and self.send_button is not None:
                if thinking and self.redis_connected:
                    self.send_button.configure(state="disabled")
                elif not thinking and self.redis_connected:
                    self.send_button.configure(state="normal")
                    
        except Exception as e:
            self.logger.error(f"Error handling ThothAI thinking status: {e}")
            # Don't show system message for this to avoid UI clutter
            
    async def _check_redis_initialization(self):
        """Check if Redis Quantum Nexus is properly initialized.
        
        CRITICAL: This method verifies the mandatory connection to Redis Quantum Nexus 
        on port 6380. If the connection fails, chat functionality will be disabled.
        No fallback modes are permitted.
        
        Returns:
            bool: True if Redis is properly connected on port 6380, False otherwise
        """
        try:
            if not self.event_bus:
                self.logger.critical("CRITICAL: No event bus available for Redis status check")
                self.add_system_message("CRITICAL: Cannot verify Redis connection - no event bus", error=True)
                return False
            
            self.logger.info("Requesting Redis Quantum Nexus status check on port 6380")
            
            # Request Redis status check with explicit port requirement
            await self.event_bus.publish("redis.status.check", {
                "source": "ThothFrame",
                "priority": "critical",
                "require_port": 6380,
                "config": self.redis_config,
                "method": "is_healthy"  # Use is_healthy method instead of ping
            })
            
            # After requesting status, wait a moment for response
            await asyncio.sleep(2)
            
            if not self.redis_connected:
                self.logger.critical("CRITICAL: Redis Quantum Nexus connection not confirmed on port 6380")
                self.add_system_message("CRITICAL: Redis Quantum Nexus connection not confirmed", error=True)
                self.add_system_message("Chat functionality disabled until Redis connects on port 6380", error=True)
                
                # Try one more reconnection attempt with explicit configuration
                await self.event_bus.publish("redis.reconnect", {
                    "config": self.redis_config,
                    "force_disconnect": True,
                    "source": "ThothFrame",
                    "priority": "critical"
                })
                
                # Disable send button if Redis is not connected
                if hasattr(self, 'send_button') and self.send_button is not None:
                    self.send_button.configure(state="disabled")
                    
                return False
                
            return self.redis_connected
            
        except Exception as e:
            self.logger.critical(f"CRITICAL: Error checking Redis initialization: {e}", exc_info=True)
            self.add_system_message(f"CRITICAL: Error verifying Redis connection: {str(e)}", error=True)
            return False
    
    def _update_thinking_status(self, message=None):
        """Update the thinking status display.
        
        Args:
            message (str, optional): Message to display in thinking status. Defaults to None.
        """
        if not hasattr(self, "thinking_label") or self.thinking_label is None:
            return
            
        if self.thinking:
            status_text = message if message else "Thinking..."
            self.thinking_label.config(text=status_text, fg="#007bff")
        else:
            self.thinking_label.config(text="Ready", fg="#28a745")
            
        # Also handle button state based on thinking status and Redis connection
        if hasattr(self, 'send_button') and self.send_button is not None:
            if self.thinking or not self.redis_connected:
                self.send_button.configure(state="disabled")
            else:
                self.send_button.configure(state="normal")
    
    @property
    def current_model(self):
        """Get the current model."""
        if hasattr(self, "model_var") and self.model_var is not None:
            return self.model_var
        return None

    @property
    def message_input(self):
        """Get the message input widget."""
        # This will be populated during initialization in the actual implementation
        if hasattr(self, "_message_input"):
            return self._message_input
        return None
        
    def _request_model_refresh(self):
        """Request a refresh of available AI models."""
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish("ai.refresh_models", {
                "source": "ThothFrame"
            }))
        
    def add_system_message(self, message, error=False):
        """Add a system message to the chat display."""
        if not hasattr(self, "chat_display") or self.chat_display is None:
            self.logger.warning("Cannot add system message: chat display not initialized")
            return
            
        try:
            color = "#dc3545" if error else "#6c757d"
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.insert(tk.END, f"[System] {message}\n", ("system", color))
            self.chat_display.config(state=tk.DISABLED)
            self.chat_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error adding system message: {e}")
            
    def add_ai_message(self, message):
        """Add an AI message to the chat display."""
        if not hasattr(self, "chat_display") or self.chat_display is None:
            self.logger.warning("Cannot add AI message: chat display not initialized")
            return
            
        try:
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.insert(tk.END, f"[ThothAI] {message}\n", ("ai", "#6a0dad"))
            self.chat_display.config(state=tk.DISABLED)
            self.chat_display.see(tk.END)
        except Exception as e:
            self.logger.error(f"Error adding AI message: {e}")
            
    async def _handle_ai_thinking(self, event_data):
        """Handle AI thinking status events from the AI.thinking topic.
        
        Args:
            event_data: Thinking status event data
        """
        # Simply delegate to the ThothAI thinking handler for consistent behavior
        await self._handle_thoth_thinking(event_data)
    
    async def _handle_voice_status(self, event_data):
        """Handle voice system status events.
        
        Args:
            event_data: Voice status event data
        """
        try:
            if not isinstance(event_data, dict):
                self.logger.warning(f"Invalid voice status format: {type(event_data)}")
                return
                
            # Extract voice status information
            status = event_data.get('status', False)
            error = event_data.get('error', None)
            message = event_data.get('message', '')
            
            # Update voice status
            self.voice_system_available = status
            
            # Update voice button state
            self._update_voice_indicator(self.voice_system_available)
            
            # Handle errors
            if not status and error:
                self.logger.error(f"Voice system error: {error}")
                self.add_system_message(f"Voice system error: {error}", error=True)
                
                # Disable voice toggle
                if hasattr(self, 'voice_toggle_button') and self.voice_toggle_button is not None:
                    self.voice_toggle_button.configure(state="disabled")
                    
                # Disable voice functionality
                self.voice_enabled = False
            elif status:
                self.logger.info(f"Voice system status: {message}")
                
                # Re-enable voice toggle if previously disabled
                if hasattr(self, 'voice_toggle_button') and self.voice_toggle_button is not None:
                    self.voice_toggle_button.configure(state="normal")
        except Exception as e:
            self.logger.error(f"Error handling voice status: {e}")
            self.add_system_message(f"Error processing voice system status: {str(e)}", error=True)
                
            status = event_data.get('status', False)
            message = event_data.get('message', '')
            listening = event_data.get('listening', False)
            
            # Update voice status indicators
            self.listening = listening
            
            # Update UI based on voice status
            if hasattr(self, 'voice_status_label') and self.voice_status_label is not None:
                if listening:
                    self.voice_status_label.configure(text="Listening", foreground="#28a745")
                else:
                    self.voice_status_label.configure(text="Voice Inactive", foreground="#6c757d")
            
            if message and status:
                self.add_system_message(f"Voice system: {message}")
            elif message and not status:
                self.add_system_message(f"Voice system error: {message}", error=True)
                
        except Exception as e:
            self.logger.error(f"Error handling voice status: {e}")
            
    async def _handle_voice_transcription(self, event_data):
        """Handle voice transcription events.
        
        Args:
            event_data: Voice transcription event data
        """
        try:
            if not isinstance(event_data, dict):
                self.logger.warning(f"Invalid voice transcription format: {type(event_data)}")
                return
                
            # CRITICAL: Enforce Redis Quantum Nexus connection on port 6380
            if not self.redis_connected:
                self.logger.critical("CRITICAL: Received voice transcription but Redis is not connected on port 6380")
                if self.event_bus:
                    await self.event_bus.publish("redis.status.check", {
                        "source": "ThothFrame",
                        "priority": "critical",
                        "require_port": 6380,
                        "config": self.redis_config
                    })
                return
                
            # Extract transcription text
            text = event_data.get('text', '')
            final = event_data.get('final', False)
            
            if not text or not final:
                return
            
            # Add user message to chat display
            self.add_user_message(text)
            
            # Auto-send to ThothAI if voice transcription auto-send is enabled
            if getattr(self, 'voice_transcription_auto_send', False) and self.event_bus:
                # Set current message
                if hasattr(self, 'message_input') and self.message_input is not None:
                    self.message_input.delete(1.0, tk.END)
                    self.message_input.insert(tk.END, text)
                
                # Disable input while processing
                if hasattr(self, 'send_button') and self.send_button is not None:
                    self.send_button.configure(state="disabled")
                
                # Publish ThothAI request
                await self.event_bus.publish("thothAI.request", {
                    "prompt": text,
                    "source": "ThothFrame",
                    "voice_triggered": True,
                    "task_type": getattr(self, 'task_type', 'chat'),
                    "model": getattr(self, 'model_var', 'default')
                })
                
                # Set thinking status
                self.thinking = True
                self._update_thinking_status("Thinking...")
        except Exception as e:
            self.logger.error(f"Error handling voice transcription: {e}")
            self.add_system_message(f"Error processing voice transcription: {str(e)}", error=True)
            
    async def _handle_system_speaking_status(self, event_data):
        """Handle system speaking status events.
        
        Args:
            event_data: Speaking status event data
        """
        try:
            if not isinstance(event_data, dict):
                self.logger.warning(f"Invalid speaking status format: {type(event_data)}")
                return
                
            # Extract speaking status
            speaking = event_data.get('speaking', False)
            text = event_data.get('text', '')
            voice = event_data.get('voice', 'default')
            
            # Update system speaking status
            self.system_speaking = speaking
            
            # Update UI based on speaking status
            if speaking:
                # Disable input while system is speaking
                if hasattr(self, 'message_input') and self.message_input is not None:
                    self.message_input.configure(state="disabled")
                if hasattr(self, 'send_button') and self.send_button is not None:
                    self.send_button.configure(state="disabled")
                
                # Update voice indicator if it exists
                if hasattr(self, 'voice_indicator') and self.voice_indicator is not None:
                    self.voice_indicator.configure(fg="orange")
            else:
                # Only enable input if Redis is connected
                if self.redis_connected:
                    if hasattr(self, 'message_input') and self.message_input is not None:
                        self.message_input.configure(state="normal")
                    if hasattr(self, 'send_button') and self.send_button is not None:
                        self.send_button.configure(state="normal")
                
                # Reset voice indicator if it exists
                if hasattr(self, 'voice_indicator') and self.voice_indicator is not None:
                    if self.voice_enabled:
                        self.voice_indicator.configure(fg="green")
                    else:
                        self.voice_indicator.configure(fg="gray")
        except Exception as e:
            self.logger.error(f"Error handling system speaking status: {e}")
            self.add_system_message(f"Error processing system speaking status: {str(e)}", error=True)
