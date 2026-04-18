#!/usr/bin/env python3
"""
Kingdom AI - Thoth AI Frame

This module implements the Thoth AI chat interface with voice system integration.
It handles sending and receiving messages to/from the Thoth AI system and 
integrates with the voice system for audio input/output with continuous listening
and Black Panther voice responses.

Features:
- Continuous voice listening with Black Panther voice responses
- Real-time sound wave visualization
- Synchronized text and voice responses
- Full integration with all Kingdom AI components
- Multi-model AI capabilities via Ollama integration
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, Canvas
import logging
import asyncio
import traceback
import random
import math
import time
import json
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List, Literal, Tuple, Union, Callable
import numpy as np
import speech_recognition as sr
import queue
import wave
import struct
import os
import tempfile

from config.windows_audio_devices import get_mic_device

from gui.frames.base_frame import BaseFrame

logger = logging.getLogger("KingdomAI.ThothFrame")

class ThothFrame(BaseFrame):
    """Frame for the Thoth AI chat interface with voice system integration.
    
    This frame serves as the central control hub for the Kingdom AI system,
    providing voice and chat interfaces for controlling all system components.
    
    Features:
    - Continuous voice listening with Black Panther voice responses
    - Real-time sound wave visualization
    - Synchronized text and voice responses
    - Full integration with all Kingdom AI components
    - Multi-model AI capabilities via Ollama integration
    """
    
    def __init__(self, parent, event_bus=None, api_key_connector=None, name="ThothFrame", **kwargs):
        """Initialize the Thoth AI frame.
        
        Args:
            parent: The parent widget
            event_bus: The application event bus
            api_key_connector: Connector for accessing API keys
            name: Name of the frame
            **kwargs: Additional keyword arguments
        """
        # Call parent constructor and store api_key_connector explicitly
        super().__init__(parent, event_bus=event_bus, name=name, **kwargs)
        # Use pack geometry manager to match the notebook container
        self.pack(fill=tk.BOTH, expand=True)
        self.api_key_connector = api_key_connector
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Created {name} frame")
        
        # Initialize state
        self.voice_enabled = False
        self.continuous_listening = False
        self.continuous_listening_var = tk.BooleanVar(value=False)
        self.thinking = False
        self.thoth_status = "Not Connected"
        self.voice_status = "Not Connected"
        self.current_voice = "black_panther"  # Default to Black Panther voice
        
        # Model selection
        self.model_var = tk.StringVar(value="llama2")
        self.available_models = []
        self.model_capabilities = {}
        self.brain_models = {}
        self.current_model = None
        self.model_status = {}
        self.model_refresh_interval = 60  # Refresh model list every 60 seconds
        self.last_model_refresh = 0
        
        # Sound visualization state
        self.wave_data = []
        self.wave_animation_active = False
        self.wave_animation_thread = None
        self.animation_lock = threading.RLock()
        self.wave_amplitude = 0.1
        self.wave_frequency = 1.0
        self.wave_phase = 0.0
        self.wave_decay = 0.95  # Decay factor for sound wave animation
        self.listening_active = False
        self.wave_points = 100  # Number of points in the sound wave
        self.wave_line = None  # Will be set when canvas is created
        
        # Voice recognition state
        self.recognizer = sr.Recognizer()
        self.microphone = None
        
        # Try to initialize microphone
        try:
            mic_index = None
            try:
                mic_index = get_mic_device()
            except Exception:
                mic_index = None
            self.microphone = sr.Microphone(device_index=mic_index) if mic_index is not None else sr.Microphone()
            self.logger.info("Microphone initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize microphone: {e}")
            
        # Audio processing queue for continuous listening
        self.audio_queue = queue.Queue()
        self.stop_listening = threading.Event()
        self.listen_thread = None
        self.speaking = False
        
        # Chat history
        self.chat_history = []
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300  # Adjusted for ambient noise
        self.recognizer.pause_threshold = 0.8  # Shorter pause for more responsive experience
        
        # Voice response state
        self.speaking = False
        self.last_response = ""
        self.streaming_response = ""
        self.response_chunks = []
        self.speak_thread = None
        
        # AI service API keys
        self.ai_service_keys = {}
        
        # Method for API key handling
        if not hasattr(self, 'get_api_key'):
            self.get_api_key = self._get_api_key
        
        # Initialize the UI components
        self._initialize_wave_data()
        self._create_widgets()
        
        # Setup event handlers
        self._setup_event_handlers()

    def _get_api_key(self, service_name):
        """Get API key for a service using the API key connector.
        
        Args:
            service_name: Name of the service
            
        Returns:
            API key string or None if not available
        """
        if self.api_key_connector:
            return self.api_key_connector.get_api_key(service_name)
        return self.ai_service_keys.get(service_name)

    def _initialize_wave_data(self):
        """Initialize sound wave data for visualization."""
        # Create initial wave data - smooth sine wave
        self.wave_data = []
        for i in range(self.wave_points):
            # Generate a smooth sine wave pattern
            x = i / self.wave_points * 2 * math.pi
            self.wave_data.append(math.sin(x) * 0.1)  # Small initial amplitude

    def _setup_event_handlers(self):
        """Set up event handlers for the event bus."""
        if self.event_bus:
            # Subscribe to thoth.response events
            self.event_bus.subscribe_sync("thoth.response", self._on_thoth_response)
            self.event_bus.subscribe_sync("thoth.status", self._on_thoth_status)
            self.event_bus.subscribe_sync("voice.status", self._on_voice_status)
            
            # Log successful subscription
            self.logger.info("Subscribed to Thoth AI and Voice System events")

    async def initialize(self):
        """Initialize the Thoth frame asynchronously.
        
        This method is called during component initialization and
        connects to the event bus, loads settings, and prepares
        the voice system for use.
        """
        self.logger.info("Initializing Thoth AI frame")
        
        # Initialize microphone if voice enabled
        try:
            # Try to get default microphone
            mic_index = None
            try:
                mic_index = get_mic_device()
            except Exception:
                mic_index = None
            self.microphone = sr.Microphone(device_index=mic_index) if mic_index is not None else sr.Microphone()
            self.logger.info("Microphone initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing microphone: {e}")
            self.microphone = None
        
        # Load saved settings if available
        self._load_settings()
        
        # Update status
        if self.event_bus:
            await self.event_bus.publish("thoth.status.request", {"source": "thoth_frame"})
            await self.event_bus.publish("voice.status.request", {"source": "thoth_frame"})
        
        self.logger.info("Thoth AI frame initialized")
        return True

    def sync_initialize(self):
        """Initialize the Thoth frame synchronously.
        
        This is a synchronous version of initialize() for use with
        systems that don't support async initialization.
        """
        self.logger.info("Synchronous initialization of Thoth AI frame")
        
        # Initialize microphone if voice enabled
        try:
            # Try to get default microphone
            mic_index = None
            try:
                mic_index = get_mic_device()
            except Exception:
                mic_index = None
            self.microphone = sr.Microphone(device_index=mic_index) if mic_index is not None else sr.Microphone()
            self.logger.info("Microphone initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing microphone: {e}")
            self.microphone = None
        
        # Load saved settings if available
        self._load_settings()
        
        # Update status
        if self.event_bus:
            self.event_bus.publish_sync("thoth.status.request", {"source": "thoth_frame"})
            self.event_bus.publish_sync("voice.status.request", {"source": "thoth_frame"})
        
        self.logger.info("Thoth AI frame initialized")
        return True
        
    async def _refresh_models(self):
        """Refresh the list of available models from Ollama."""
        try:
            if self.event_bus:
                await self.event_bus.publish("thoth.models.refresh", {
                    "source": "thoth_frame",
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error refreshing models: {e}")
            
    def _check_model_refresh(self):
        """Periodically check if models need to be refreshed."""
        current_time = time.time()
        if current_time - self.last_model_refresh > self.model_refresh_interval:
            asyncio.create_task(self._refresh_models())
            self.last_model_refresh = current_time
        self.after(1000, self._check_model_refresh)

    def _load_settings(self):
        settings_path = os.path.join("data", "thoth_frame_settings.json")
        try:
            if not os.path.exists(settings_path):
                return
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                model = data.get("current_model")
                if isinstance(model, str) and model:
                    self.current_model = model
                    try:
                        self.model_var.set(model)
                    except Exception:
                        pass
                voice_enabled = data.get("voice_enabled")
                if isinstance(voice_enabled, bool):
                    self.voice_enabled = voice_enabled
        except Exception:
            return

    def _on_clear_chat(self):
        try:
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.config(state=tk.DISABLED)
        except Exception:
            pass
        try:
            self.chat_history.clear()
        except Exception:
            self.chat_history = []

    def _on_send_message(self):
        try:
            text = self.input_field.get().strip()
        except Exception:
            return
        if not text:
            return
        try:
            self.input_field.delete(0, tk.END)
        except Exception:
            pass
        self._add_user_message(text)
        try:
            asyncio.create_task(self._process_command(text))
        except Exception:
            self._process_command_sync(text)
            
    def _get_best_model_for_task(self, command):
        """Get the best model for a specific task based on command content.
        
        Args:
            command (str): The command to analyze
            
        Returns:
            str: Name of the best model to handle the command
        """
        # Default to current model if available
        if self.current_model and self.current_model in self.available_models:
            return self.current_model
            
        # Check command for specific capabilities
        command_lower = command.lower()
        
        # Code generation tasks
        if any(kw in command_lower for kw in ["code", "program", "function", "class"]):
            for model in ["deepseek-coder:6.7b", "llama2:latest"]:
                if model in self.available_models:
                    return model
                    
        # Creative/chat tasks
        if any(kw in command_lower for kw in ["story", "creative", "imagine", "chat"]):
            for model in ["qwen2.5:7b", "llama2:latest"]:
                if model in self.available_models:
                    return model
                    
        # Technical/analytical tasks
        if any(kw in command_lower for kw in ["analyze", "explain", "technical", "math"]):
            for model in ["deepseek-r1:7b", "llama2:latest"]:
                if model in self.available_models:
                    return model
                    
        # Default to first available model
        if self.available_models:
            return self.available_models[0]
            
        # Fallback to llama2
        return "llama2:latest"
            
    def _create_widgets(self):
        """Create widgets for the Thoth AI frame."""
        # Set up model refresh timer
        self.after(1000, self._check_model_refresh)
        # Main frame structure with three main sections:
        # 1. Top control panel with buttons and model selection
        # 2. Middle chat display area
        # 3. Bottom input area with message entry and send button
        
        # Top control frame
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Left side - buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.X)
        
        # Create voice toggle button
        self.voice_button = ttk.Button(
            control_frame,
            text="🎤 Voice",
            command=self._on_toggle_voice
        )
        self.voice_button.pack(side=tk.LEFT, padx=5)
        
        # Create model refresh button
        self.refresh_button = ttk.Button(
            control_frame,
            text="🔄 Refresh Models",
            command=lambda: asyncio.create_task(self._refresh_models())
        )
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Continuous listening toggle
        self.continuous_listen_var = tk.BooleanVar(value=False)
        self.continuous_listen_check = ttk.Checkbutton(
            button_frame,
            text="Continuous Listening",
            variable=self.continuous_listen_var,
            command=self._toggle_continuous_listening
        )
        self.continuous_listen_check.pack(side=tk.LEFT, padx=5)
        
        # Clear chat button
        clear_button = ttk.Button(
            button_frame,
            text="Clear Chat",
            command=self._on_clear_chat
        )
        clear_button.pack(side=tk.LEFT, padx=5)
        
        # Right side - model selection
        model_frame = ttk.Frame(control_frame)
        model_frame.pack(side=tk.RIGHT, fill=tk.X)
        
        # Create model selection dropdown
        model_label = ttk.Label(control_frame, text="Model:")
        model_label.pack(side=tk.LEFT, padx=5)
        
        self.model_dropdown = ttk.Combobox(
            control_frame,
            textvariable=self.model_var,
            values=self.available_models,
            state="readonly",
            width=15
        )
        self.model_dropdown.pack(side=tk.LEFT, padx=5)
        self.model_dropdown.bind("<<ComboboxSelected>>", self._on_model_change)
        
        # Chat display
        chat_frame = ttk.Frame(self)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            background="#f0f0f0",
            font=("TkDefaultFont", 10),
            height=20
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Configure chat display tags
        self.chat_display.tag_configure("user", foreground="#007acc")
        self.chat_display.tag_configure("assistant", foreground="#008000")
        self.chat_display.tag_configure("error", foreground="#cc0000")
        self.chat_display.tag_configure("system", foreground="#666666")
        
        # Sound wave visualization canvas
        self.wave_canvas = Canvas(chat_frame, height=60, bg="#e0e0e0")
        self.wave_canvas.pack(fill=tk.X, pady=5)
        self._initialize_sound_wave_visualization()
        
        # Bottom input area
        input_frame = ttk.Frame(self)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Message entry field
        self.input_field = ttk.Entry(input_frame)
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.input_field.bind("<Return>", lambda e: self._on_send_message())
        
        # Send button
        send_button = ttk.Button(
            input_frame,
            text="Send",
            command=self._on_send_message
        )
        send_button.pack(side=tk.RIGHT, padx=5)
        
        # Status row
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=10, pady=2)
        
        # Thinking status indicator
        self.thinking_label = ttk.Label(status_frame, text="")
        self.thinking_label.pack(side=tk.LEFT, padx=5)
        
        # Voice status indicator
        self.voice_status_label = ttk.Label(status_frame, text="Voice: Not Connected")
        self.voice_status_label.pack(side=tk.RIGHT, padx=5)
        
        # Thoth status indicator
        self.thoth_status_label = ttk.Label(status_frame, text="Thoth AI: Not Connected")
        self.thoth_status_label.pack(side=tk.RIGHT, padx=5)
        
        # Add welcome message
        self._add_system_message("Welcome to Kingdom AI with Thoth AI integration!")
        self._add_system_message("Select a model and type a message to begin.")
        
        # Start wave animation
        self._animate_sound_wave()
        
    def _initialize_sound_wave_visualization(self):
        """Initialize sound wave visualization on the canvas."""
        # Create wave line on canvas
        canvas_width = self.wave_canvas.winfo_width() or 400  # Default if not yet rendered
        canvas_height = self.wave_canvas.winfo_height() or 60  # Default if not yet rendered
        
        # Create points for the wave line
        points = []
        for i in range(self.wave_points):
            x = i / self.wave_points * canvas_width
            y = canvas_height / 2 + self.wave_data[i] * canvas_height / 2
            points.append(x)
            points.append(y)
        
        # Create wave line with points
        self.wave_line = self.wave_canvas.create_line(
            points, fill="#0066cc", width=2, smooth=True
        )
        
    def _animate_sound_wave(self):
        """Animate the sound wave visualization in a separate thread."""
        # Stop any existing animation
        if self.wave_animation_thread and self.wave_animation_thread.is_alive():
            self.wave_animation_active = False
            self.wave_animation_thread.join(timeout=1.0)
        
        # Start new animation thread
        self.wave_animation_active = True
        self.wave_animation_thread = threading.Thread(
            target=self._wave_animation_worker,
            daemon=True
        )
        self.wave_animation_thread.start()
    
    def _wave_animation_worker(self):
        """Worker function for sound wave animation thread."""
        while self.wave_animation_active:
            try:
                # Update wave data
                with self.animation_lock:
                    self._update_wave_data()
                
                # Update canvas on main thread
                if self.winfo_exists():  # Check if widget still exists
                    self.after(0, self._update_wave_canvas)
                    
                # Animation frame rate - 30fps
                time.sleep(1/30)
            except Exception as e:
                self.logger.error(f"Error in wave animation: {e}")
                time.sleep(0.1)  # Prevent tight loop on error
    
    def _update_wave_data(self):
        """Update the sound wave data for visualization."""
        # Apply decay to amplitude
        self.wave_amplitude *= self.wave_decay
        
        # If listening or speaking, keep amplitude above minimum
        if self.listening_active or self.speaking:
            self.wave_amplitude = max(self.wave_amplitude, 0.3)
            
            # Add random fluctuation for more natural look
            self.wave_amplitude += random.uniform(-0.05, 0.1)
            self.wave_amplitude = min(max(self.wave_amplitude, 0.1), 0.8)
        else:
            # When inactive, let it decay to a minimum
            self.wave_amplitude = max(self.wave_amplitude, 0.05)
        
        # Update phase
        self.wave_phase += 0.1
        
        # Generate new wave data
        for i in range(self.wave_points):
            # Position in the wave (0 to 2π)
            x = (i / self.wave_points * 2 * math.pi) + self.wave_phase
            
            # Generate wave value with some randomness for natural look
            value = math.sin(x * self.wave_frequency) * self.wave_amplitude
            if self.listening_active or self.speaking:
                value += random.uniform(-0.05, 0.05)  # Add noise when active
            
            # Update wave data
            self.wave_data[i] = value
    
    def _update_wave_canvas(self):
        """Update the sound wave visualization on the canvas."""
        if not self.wave_line:
            return  # Canvas not initialized yet
            
        try:
            # Get canvas dimensions
            canvas_width = self.wave_canvas.winfo_width() or 400
            canvas_height = self.wave_canvas.winfo_height() or 60
            
            # Create points for the updated wave
            points = []
            for i in range(self.wave_points):
                x = i / self.wave_points * canvas_width
                y = canvas_height / 2 + self.wave_data[i] * canvas_height / 2
                points.append(x)
                points.append(y)
            
            # Update the line coordinates
            self.wave_canvas.coords(self.wave_line, *points)
            
            # Set line color based on state
            if self.speaking:
                self.wave_canvas.itemconfig(self.wave_line, fill="#009900")  # Green when speaking
            elif self.listening_active:
                self.wave_canvas.itemconfig(self.wave_line, fill="#cc0000")  # Red when listening
            else:
                self.wave_canvas.itemconfig(self.wave_line, fill="#0066cc")  # Blue when idle
        except Exception as e:
            self.logger.error(f"Error updating wave canvas: {e}")
    
    def _toggle_voice(self, enabled=None):
        """Toggle voice mode on/off.
        
        Args:
            enabled: Optional boolean to set specific state
        """
        if enabled is not None:
            self.voice_enabled = enabled
        else:
            self.voice_enabled = not self.voice_enabled
        
        # Update UI
        if self.voice_enabled:
            self.voice_button.config(text="🎤 Disable Voice")
            # Initialize microphone if needed
            if not self.microphone:
                try:
                    mic_index = None
                    try:
                        mic_index = get_mic_device()
                    except Exception:
                        mic_index = None
                    self.microphone = sr.Microphone(device_index=mic_index) if mic_index is not None else sr.Microphone()
                    self.logger.info("Microphone initialized")
                except Exception as e:
                    self.logger.error(f"Error initializing microphone: {e}")
                    self._add_system_message(f"Error initializing microphone: {e}", error=True)
                    self.voice_enabled = False
                    self.voice_button.config(text="🎤 Enable Voice")
                    return
        else:
            self.voice_button.config(text="🎤 Enable Voice")
            # Stop continuous listening if active
            if self.continuous_listening:
                self._toggle_continuous_listening(False)
                self.continuous_listen_var.set(False)
        
        # Notify the system of voice mode change
        if self.event_bus:
            self.event_bus.publish_sync("voice.toggle", {
                "enabled": self.voice_enabled,
                "source": "thoth_frame"
            })
        
        self._add_system_message(f"Voice {'enabled' if self.voice_enabled else 'disabled'}")
    
    def _on_toggle_voice(self):
        """Handle voice toggle button click."""
        self._toggle_voice()
    
    def _toggle_continuous_listening(self, enabled=None):
        """Toggle continuous voice listening mode on/off.
        
        Args:
            enabled: Optional boolean to set specific state
        """
        # Update from checkbox if not explicitly set
        if enabled is None:
            enabled = self.continuous_listen_var.get()
        
        # Don't enable if voice is disabled
        if enabled and not self.voice_enabled:
            self._add_system_message("Please enable voice first", error=True)
            self.continuous_listen_var.set(False)
            return
        
        # Set state
        self.continuous_listening = enabled
        self.continuous_listen_var.set(enabled)
        
        # Start or stop listening
        if self.continuous_listening:
            self._start_continuous_listening()
        else:
            self._stop_continuous_listening()
        
        # Notify the system of continuous listening mode change
        if self.event_bus:
            self.event_bus.publish_sync("voice.continuous_listening", {
                "enabled": self.continuous_listening,
                "source": "thoth_frame"
            })
        
        self._add_system_message(
            f"Continuous listening {'enabled' if self.continuous_listening else 'disabled'}"
        )
    
    def _update_thinking_status(self):
        """Update the UI to reflect the current thinking status."""
        if self.thinking:
            self.thinking_label.config(text="Thinking...", foreground="#cc0000")
            # Disable input while thinking
            self.input_field.config(state=tk.DISABLED)
        else:
            self.thinking_label.config(text="", foreground="#000000")
            # Re-enable input
            self.input_field.config(state=tk.NORMAL)
            
    def _start_continuous_listening(self):
        """Start continuous voice listening mode."""
        if not self.microphone:
            self._add_system_message("No microphone available", error=True)
            return
            
        # Stop any existing listening thread
        self._stop_continuous_listening()
        
        # Reset stop event
        self.stop_listening = threading.Event()
        
        # Start new listening thread
        self.listen_thread = threading.Thread(
            target=self._continuous_listening_worker,
            daemon=True
        )
        self.listen_thread.start()
        
        # Update UI
        self.listening_active = True
        
    def _stop_continuous_listening(self):
        """Stop continuous voice listening mode."""
        # Signal thread to stop
        if self.stop_listening:
            self.stop_listening.set()
        
        # Wait for thread to exit
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=1.0)
            self.listen_thread = None
        
        # Clear queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # Update UI
        self.listening_active = False
        
    def _continuous_listening_worker(self):
        """Worker thread for continuous voice listening."""
        # Check if microphone is available
        if not self.microphone:
            self.logger.error("No microphone available for continuous listening")
            return
            
        # Adjust recognizer settings for continuous listening
        self.recognizer.pause_threshold = 0.8
        self.recognizer.dynamic_energy_threshold = True
        
        # First adjust for ambient noise
        try:
            with self.microphone as source:
                self.logger.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                self.logger.info(f"Energy threshold set to {self.recognizer.energy_threshold}")
        except Exception as e:
            self.logger.error(f"Error adjusting for ambient noise: {e}")
        
        self.logger.info("Continuous listening started")
        
        # Main listening loop
        while not self.stop_listening.is_set() and self.continuous_listening:
            try:
                # Only proceed if microphone is available
                if self.microphone:
                    with self.microphone as source:
                        self.logger.debug("Listening...")
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                        
                        # Put audio in queue for processing in main thread
                        self.audio_queue.put(audio)
                        
                        # Use Tkinter's after method to process in main thread
                        if self.winfo_exists():  # Check if widget still exists
                            self.after(0, self._process_audio_queue)
                else:
                    # No microphone available, stop listening
                    self.logger.error("Microphone became unavailable during listening")
                    break
                        
            except sr.WaitTimeoutError:
                # No speech detected in timeout period, continue listening
                continue
            except Exception as e:
                self.logger.error(f"Error in continuous listening: {e}")
                # Short delay to prevent tight loop on error
                time.sleep(0.5)
        
        self.logger.info("Continuous listening stopped")
        
    def _process_audio_queue(self):
        """Process audio queue from continuous listening."""
        if self.audio_queue.empty():
            return
            
        # Get audio from queue
        try:
            audio = self.audio_queue.get_nowait()
        except queue.Empty:
            return
            
        # Process audio with speech recognition
        try:
            # First try Google's recognizer for best accuracy
            recognize_google = getattr(self.recognizer, "recognize_google", None)
            if callable(recognize_google):
                text = recognize_google(audio)
            else:
                raise AttributeError("recognize_google not available")
            if not isinstance(text, str):
                text = str(text)
            self.logger.info(f"Recognized: {text}")
            
            # Add to chat and process
            if text and text.strip():
                # Add to chat display
                self._add_user_message(text)
                
                # Send to Thoth AI
                self._process_command_sync(text)
                
        except sr.UnknownValueError:
            # Speech was unintelligible
            self.logger.debug("Could not understand audio")
        except sr.RequestError as e:
            # Could not request results from service
            self.logger.error(f"Error requesting results from speech recognition service: {e}")
        except Exception as e:
            self.logger.error(f"Error processing audio: {e}")
            
    def _add_system_message(self, message, error=False):
        """Add a system message to the chat display.
        
        Args:
            message: The message text
            error: Whether this is an error message
        """
        tag = "error" if error else "system"
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Enable editing
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp and message
        self.chat_display.insert(tk.END, f"[{timestamp}] SYSTEM: ", tag)
        self.chat_display.insert(tk.END, f"{message}\n", tag)
        
        # Scroll to end
        self.chat_display.see(tk.END)
        
        # Disable editing
        self.chat_display.config(state=tk.DISABLED)
        
    def _add_user_message(self, message):
        """Add a user message to the chat display.
        
        Args:
            message: The message text
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Enable editing
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp and message
        self.chat_display.insert(tk.END, f"[{timestamp}] YOU: ", "user")
        self.chat_display.insert(tk.END, f"{message}\n", "user")
        
        # Scroll to end
        self.chat_display.see(tk.END)
        
        # Disable editing
        
        # Add to chat history
        self.chat_history.append({"role": "user", "content": message})
        
    def _append_message(self, text, tag):
        """Append a message to the chat display with the given tag.
        
        Args:
            text: Message text to append
            tag: Tag to apply to the message
        """
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"{text}\n", tag)
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _get_best_model_for_task_legacy(self, task):
        if self.available_models:
            return self.available_models[0]
        return "llama2:latest"

    def _on_thoth_response_legacy(self, data):
        if not isinstance(data, dict):
            self.logger.error(f"Invalid Thoth response data: {data}")
            return
        response = data.get("response", "")
        if response:
            self._append_message(response, "assistant")
            
    async def _process_command(self, command):
        """Process a command or query.
        
        Args:
            command: The command or query text
        """
        # Set thinking state
        self.thinking = True
        self._update_thinking_status()
        
        try:
            # First check if event bus is available
            if not self.event_bus:
                self._add_system_message("Event bus not available. Command processing is limited.", error=True)
                return
            
            # Check for system commands first
            if command.lower().startswith("system:"):
                # Extract actual command
                system_cmd = command[7:].strip().lower()
                
                # Handle system commands
                if any(x in system_cmd for x in ["restart", "reboot", "reset"]):
                    self._add_system_message("System restart command received")
                    await self.event_bus.publish("system.restart", {"source": "thoth_frame"})
                    
                elif "status" in system_cmd:
                    self._add_system_message("Requesting system status...")
                    await self.event_bus.publish("system.status.request", {"source": "thoth_frame"})
                    
                elif "shutdown" in system_cmd or "exit" in system_cmd:
                    self._add_system_message("System shutdown command received")
                    await self.event_bus.publish("system.shutdown", {"source": "thoth_frame"})
                
                # Log management commands
                elif "logs" in system_cmd or "log" in system_cmd:
                    if "view" in system_cmd or "show" in system_cmd:
                        self._add_system_message("Retrieving log files...")
                        await self.event_bus.publish("system.logs.view", {"source": "thoth_frame", "log_type": "all"})
                    elif "clear" in system_cmd:
                        self._add_system_message("Clearing log files...")
                        await self.event_bus.publish("system.logs.clear", {"source": "thoth_frame"})
                    elif "error" in system_cmd:
                        self._add_system_message("Retrieving error logs...")
                        await self.event_bus.publish("system.logs.view", {"source": "thoth_frame", "log_type": "error"})
                
                # Performance commands
                elif "performance" in system_cmd or "stats" in system_cmd or "usage" in system_cmd:
                    self._add_system_message("Requesting system performance metrics...")
                    await self.event_bus.publish("system.performance.request", {"source": "thoth_frame"})
                
                # Update commands
                elif "update" in system_cmd or "upgrade" in system_cmd:
                    self._add_system_message("Checking for updates...")
                    await self.event_bus.publish("system.update.check", {"source": "thoth_frame"})
                    
                # Network commands
                elif "network" in system_cmd or "connection" in system_cmd:
                    self._add_system_message("Checking network status...")
                    await self.event_bus.publish("system.network.check", {"source": "thoth_frame"})
                    
                # Config commands
                elif "config" in system_cmd or "settings" in system_cmd:
                    self._add_system_message("Retrieving system configuration...")
                    await self.event_bus.publish("system.config.get", {"source": "thoth_frame"})
                
            # Check for component-specific commands
            elif command.lower().startswith("mining:") or "mining" in command.lower():
                # Mining system commands
                if any(x in command.lower() for x in ["start", "begin", "launch"]):
                    await self.event_bus.publish("mining.control", {"action": "start", "source": "thoth_ai"})
                    self._add_system_message("Command sent: Start mining operation")
                    
                elif any(x in command.lower() for x in ["stop", "disable", "turn off"]):
                    await self.event_bus.publish("mining.control", {"action": "stop", "source": "thoth_ai"})
                    self._add_system_message("Command sent: Stop mining operation")
                    
                elif "status" in command.lower():
                    await self.event_bus.publish("mining.request_status", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Request mining status")
                    
                # Advanced mining commands
                elif "hashrate" in command.lower():
                    await self.event_bus.publish("mining.get_hashrate", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Get mining hashrate")
                    
                elif "algorithm" in command.lower() or "algo" in command.lower():
                    # Extract algorithm if specified
                    algo = None
                    for known_algo in ["sha256", "ethash", "randomx", "kawpow"]:
                        if known_algo in command.lower():
                            algo = known_algo
                            break
                            
                    if algo:
                        await self.event_bus.publish("mining.set_algorithm", {
                            "source": "thoth_ai",
                            "algorithm": algo
                        })
                        self._add_system_message(f"Command sent: Set mining algorithm to {algo}")
                    else:
                        await self.event_bus.publish("mining.get_algorithm", {"source": "thoth_ai"})
                        self._add_system_message("Command sent: Get current mining algorithm")
                        
                elif "pool" in command.lower():
                    if "set" in command.lower() or "change" in command.lower():
                        self._add_system_message("Pool configuration requires specific details. Please use the Mining tab.")
                    else:
                        await self.event_bus.publish("mining.get_pool_info", {"source": "thoth_ai"})
                        self._add_system_message("Command sent: Get current mining pool information")
                    
            # Trading commands
            elif any(x in command.lower() for x in ["trading", "trade", "market", "crypto", "stock", "portfolio"]):
                if "buy" in command.lower() or "purchase" in command.lower():
                    # Extract symbol and amount if possible
                    self._add_system_message("Processing trade command. Please use the Trading tab for actual trades.")
                    await self.event_bus.publish("trading.request_status", {"source": "thoth_ai"})
                    
                elif "sell" in command.lower():
                    self._add_system_message("Processing trade command. Please use the Trading tab for actual trades.")
                    await self.event_bus.publish("trading.request_status", {"source": "thoth_ai"})
                    
                elif "status" in command.lower() or "portfolio" in command.lower():
                    await self.event_bus.publish("trading.request_status", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Request trading status")
                    
                elif "price" in command.lower() or "quote" in command.lower():
                    # Extract symbol if specified
                    symbols = []
                    common_symbols = ["btc", "eth", "xrp", "sol", "doge", "aapl", "msft", "googl", "amzn"]
                    for symbol in common_symbols:
                        if symbol in command.lower():
                            symbols.append(symbol.upper())
                            
                    if symbols:
                        await self.event_bus.publish("trading.get_price", {
                            "source": "thoth_ai",
                            "symbols": symbols
                        })
                        self._add_system_message(f"Command sent: Get price for {', '.join(symbols)}")
                    else:
                        self._add_system_message("Please specify a trading symbol (e.g., BTC, ETH, AAPL)")
                        
                elif "chart" in command.lower() or "graph" in command.lower():
                    # Extract symbol if specified
                    symbol = None
                    for s in ["btc", "eth", "xrp", "sol", "doge", "aapl", "msft", "googl", "amzn"]:
                        if s in command.lower():
                            symbol = s.upper()
                            break
                            
                    if symbol:
                        await self.event_bus.publish("trading.show_chart", {
                            "source": "thoth_ai",
                            "symbol": symbol
                        })
                        self._add_system_message(f"Command sent: Show chart for {symbol}")
                    else:
                        self._add_system_message("Please specify a trading symbol (e.g., BTC, ETH, AAPL)")
                    
            # Wallet commands
            elif any(x in command.lower() for x in ["wallet", "balance", "coin", "crypto", "transfer", "send"]):
                if "balance" in command.lower() or "status" in command.lower():
                    await self.event_bus.publish("wallet.get_balance", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Get wallet balance")
                    
                elif "address" in command.lower():
                    await self.event_bus.publish("wallet.get_address", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Get wallet address")
                    
                elif "send" in command.lower() or "transfer" in command.lower():
                    self._add_system_message("Send operations require specific details. Please use the Wallet tab.")
                    
                elif "history" in command.lower() or "transaction" in command.lower():
                    await self.event_bus.publish("wallet.get_transaction_history", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Get transaction history")
                    
            # VR commands
            elif "vr" in command.lower():
                if any(x in command.lower() for x in ["connect", "enable", "start"]):
                    await self.event_bus.publish("vr.connect", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Connect VR system")
                    
                elif any(x in command.lower() for x in ["disconnect", "disable", "stop"]):
                    await self.event_bus.publish("vr.disconnect", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Disconnect VR system")
                    
                elif "status" in command.lower():
                    await self.event_bus.publish("vr.request_status", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Request VR status")
                    
                # VR environment commands
                elif "environment" in command.lower() or "scene" in command.lower():
                    # Extract environment name if specified
                    envs = ["office", "space", "forest", "beach", "mountain", "city"]
                    env_name = None
                    for env in envs:
                        if env in command.lower():
                            env_name = env
                            break
                            
                    if env_name:
                        await self.event_bus.publish("vr.set_environment", {
                            "source": "thoth_ai", 
                            "environment": env_name
                        })
                        self._add_system_message(f"Command sent: Set VR environment to {env_name}")
                    else:
                        await self.event_bus.publish("vr.get_available_environments", {"source": "thoth_ai"})
                        self._add_system_message("Command sent: Get available VR environments")
            
            # Code Generator commands
            elif any(x in command.lower() for x in ["code", "generator", "generate", "script", "program"]):
                if "generate" in command.lower() or "create" in command.lower():
                    # Try to extract language and description
                    langs = ["python", "javascript", "java", "c++", "ruby", "go", "rust"]
                    lang = None
                    for l in langs:
                        if l in command.lower():
                            lang = l
                            break
                            
                    if lang:
                        # Extract description - everything after the language mention
                        lang_pos = command.lower().find(lang)
                        if lang_pos > -1:
                            desc = command[lang_pos + len(lang):].strip()
                            if desc:
                                await self.event_bus.publish("code_generator.generate", {
                                    "source": "thoth_ai",
                                    "language": lang,
                                    "description": desc
                                })
                                self._add_system_message(f"Command sent: Generate {lang} code for '{desc}'")
                                return
                                
                    # If we didn't find language/description or couldn't parse
                    self._add_system_message("Please specify a programming language and what you want to generate.")
                    
                elif "status" in command.lower():
                    await self.event_bus.publish("code_generator.get_status", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Get code generator status")
                    
                elif "templates" in command.lower() or "examples" in command.lower():
                    await self.event_bus.publish("code_generator.get_templates", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: Get code generator templates")
            
            # System-wide status
            elif "system status" in command.lower() or "system health" in command.lower():
                await self.event_bus.publish("system.request_status", 
                    {"source": "thoth_ai", "component": "all"}
                )
                self._add_system_message("Command sent: Request system-wide status")
                
            # API key commands
            elif "api" in command.lower() and "key" in command.lower():
                if "status" in command.lower() or "list" in command.lower():
                    await self.event_bus.publish("api_keys.list", {"source": "thoth_ai"})
                    self._add_system_message("Command sent: List API keys status")
                else:
                    self._add_system_message("API key management requires the API Keys tab for security.")
                
            # Voice commands
            elif any(x in command.lower() for x in ["voice", "speak", "listen", "microphone", "audio"]):
                if any(x in command.lower() for x in ["enable", "turn on", "activate", "start"]):
                    self._toggle_voice(True)
                    self._add_system_message("Voice enabled")
                    
                elif any(x in command.lower() for x in ["disable", "turn off", "deactivate", "stop"]):
                    self._toggle_voice(False)
                    self._add_system_message("Voice disabled")
                    
                elif "continuous" in command.lower() or "always" in command.lower():
                    if "enable" in command.lower() or "on" in command.lower() or "start" in command.lower():
                        self.continuous_listening = True
                        self.continuous_listening_var.set(True)
                        self._start_continuous_listening()
                        self._add_system_message("Continuous listening mode enabled")
                    elif "disable" in command.lower() or "off" in command.lower() or "stop" in command.lower():
                        self.continuous_listening = False
                        self.continuous_listening_var.set(False)
                        self._stop_continuous_listening()
                        self._add_system_message("Continuous listening mode disabled")
                        
                elif "voice" in command.lower() and "select" in command.lower():
                    if "black panther" in command.lower():
                        self.current_voice = "black_panther"
                        self._add_system_message("Voice set to Black Panther")
                    elif "jarvis" in command.lower():
                        self.current_voice = "jarvis"
                        self._add_system_message("Voice set to Jarvis")
                    elif "female" in command.lower() or "woman" in command.lower():
                        self.current_voice = "female"
                        self._add_system_message("Voice set to Female")
                    elif "male" in command.lower() or "man" in command.lower():
                        self.current_voice = "male"
                        self._add_system_message("Voice set to Male")
                    else:
                        self._add_system_message("Available voices: Black Panther, Jarvis, Female, Male")
                    
            # Model selection commands
            elif any(x in command.lower() for x in ["model", "ai", "switch", "change"]) and any(x in command.lower() for x in ["gpt", "llama", "claude", "gemini"]):
                model = None
                for m in self.available_models:
                    if m.lower() in command.lower():
                        model = m
                        break
                        
                if model:
                    self.model_var.set(model)
                    self._add_system_message(f"AI model switched to {model}")
                else:
                    models_list = ", ".join(self.available_models)
                    self._add_system_message(f"Available models: {models_list}")
                    
            # Navigation/GUI commands
            elif any(x in command.lower() for x in ["tab", "switch", "navigate", "show", "go to"]):
                tab_map = {
                    "dashboard": "dashboard",
                    "trading": "trading",
                    "mining": "mining",
                    "wallet": "wallet",
                    "vr": "vr",
                    "thoth": "thoth",
                    "ai": "thoth",
                    "code": "code_generator",
                    "generator": "code_generator",
                    "api": "api_keys",
                    "keys": "api_keys"
                }
                
                target_tab = None
                for keyword, tab_name in tab_map.items():
                    if keyword in command.lower():
                        target_tab = tab_name
                        break
                        
                if target_tab:
                    await self.event_bus.publish("ui.navigate", {
                        "source": "thoth_ai",
                        "tab": target_tab
                    })
                    self._add_system_message(f"Command sent: Navigate to {target_tab} tab")
                    
            # Chat history commands
            elif any(x in command.lower() for x in ["clear", "reset", "delete"]) and any(x in command.lower() for x in ["chat", "history", "conversation"]):
                self._on_clear_chat()
                
            # Help command
            elif "help" in command.lower() or "commands" in command.lower() or "what can you do" in command.lower():
                help_text = (
                    "Kingdom AI Command Categories:\n"
                    "- System: system status, restart, shutdown, logs, performance\n"
                    "- Mining: start/stop mining, hashrate, algorithm, pool info\n"
                    "- Trading: portfolio status, get price, charts\n"
                    "- Wallet: balance, address, transaction history\n"
                    "- VR: connect/disconnect, environments\n"
                    "- Code Generator: generate code, templates\n"
                    "- Voice: enable/disable, continuous listening\n"
                    "- Navigation: switch between tabs\n"
                    "- Models: switch AI models (GPT-4, Claude, etc.)\n"
                    "\nFor specific help, ask about any category."
                )
                self._add_system_message(help_text)
                    
            # Default handling - send to Thoth AI with multi-model support
            else:
                # Get best model for the task
                model = self._get_best_model_for_task(command)
                
                await self.event_bus.publish("thoth.query", {
                    "prompt": command,
                    "model": model,
                    "timestamp": datetime.now().isoformat(),
                    "source": "thoth_frame",
                    "capabilities": self.model_capabilities.get(model, [])
                })
                
        except Exception as e:
            self.logger.error(f"Error processing system command: {e}")
            self.logger.error(traceback.format_exc())
            self._add_system_message(f"Error processing command: {str(e)}", error=True)
            
        # Reset thinking state
        self.thinking = False
        self._update_thinking_status()
    
    def _process_command_sync(self, command):
        """Synchronous version of _process_command."""
        # Create and run a coroutine in the asyncio event loop
        asyncio.create_task(self._process_command(command))
    
    def _on_thoth_response(self, data):
        """Handle response from Thoth AI.
        
        Args:
            data: Response data dictionary
        """
        if not isinstance(data, dict):
            self.logger.error(f"Invalid Thoth response data: {data}")
            return
            
        # Extract response text
        response = data.get("response", "")
        if response:
            self._append_message(response, "assistant")
            
    async def _on_toggle_voice_async(self, event_data=None):
        self._toggle_voice()

    async def _toggle_continuous_listening_async(self, event_data=None):
        self._toggle_continuous_listening()
    
    def _on_speaking_done(self):
        """Called when speech output is done."""
        self.speaking = False
    
    def _on_thoth_status(self, data):
        """Handle status update from Thoth AI.
        
        Args:
            data: Status data dictionary
        """
        if not isinstance(data, dict):
            return
            
        # Update status label
        status = data.get("status", "Unknown")
        self.thoth_status = status
        self.thoth_status_label.config(text=f"Thoth AI: {status}")
        
        # Update model information
        if "models" in data:
            self.available_models = data["models"]
            self.model_capabilities = data.get("capabilities", {})
            
            # Update model dropdown
            self.model_dropdown["values"] = self.available_models
            
            # Set current model if none selected
            if not self.current_model and self.available_models:
                self.current_model = self.available_models[0]
                self.model_var.set(self.current_model)
                
    def _on_model_change(self, event):
        """Handle model selection change.
        
        Args:
            event: ComboboxSelected event
        """
        selected_model = self.model_var.get()
        if selected_model != self.current_model:
            self.current_model = selected_model
            
            # Notify about model change
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("thoth.model.change", {
                    "model": selected_model,
                    "source": "thoth_frame",
                    "timestamp": datetime.now().isoformat()
                }))
    
    def _on_voice_status(self, data):
        """Handle status update from Voice System.
        
        Args:
            data: Status data dictionary
        """
        if not isinstance(data, dict):
            return
            
        # Update status label
        status = data.get("status", "Unknown")
        self.voice_status = status
        self.voice_status_label.config(text=f"Voice: {status}")
        
        # Update voice enabled state if needed
        enabled = data.get("enabled", None)
        if enabled is not None and enabled != self.voice_enabled:
            self._toggle_voice(enabled)
