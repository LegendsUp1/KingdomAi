#!/usr/bin/env python3
"""Kingdom AI - Voice Frame

Full implementation of the Voice tab for Kingdom AI.
Provides real-time voice status, command history, and integration with
ThothAI for voice commands and responses. Connects to the event bus
for system-wide communication and uses Redis Quantum Nexus for data storage.
"""
from __future__ import annotations

import logging
import tkinter as tk
import asyncio
from datetime import datetime
from tkinter import ttk
from typing import Optional, List, Tuple, Dict, Any

from core.base_component import BaseComponent
from gui.frames.base_frame import BaseFrame
from gui.kingdom_style import KingdomStyles

# Set up logger
logger = logging.getLogger(__name__)

# Initialize audio_visualizer_available flag
audio_visualizer_available = False

# Create a simple placeholder for AudioVisualizer if import fails
class AudioVisualizerPlaceholder:
    """Placeholder for the AudioVisualizer when the real component is not available."""
    
    def __init__(self, master, **kwargs):
        """Create a simple placeholder frame."""
        self.frame = ttk.Frame(master)
        label = ttk.Label(self.frame, text="Audio Visualization Unavailable", 
                         foreground=KingdomStyles.COLORS["warning"])
        label.pack(pady=10)
        
    def get_frame(self) -> ttk.Frame:
        """Return the frame for packing in parent."""
        return self.frame
        
    def set_active(self, active: bool) -> None:
        """Set the active state of the audio visualizer."""
        try:
            self._active = active
            if hasattr(self, 'frame') and self.frame.winfo_exists():
                for child in self.frame.winfo_children():
                    if isinstance(child, ttk.Label):
                        status = "Listening..." if active else "Audio Visualization Unavailable"
                        color = KingdomStyles.COLORS.get("success", "#4CAF50") if active else KingdomStyles.COLORS.get("warning", "#FFC107")
                        child.configure(text=status, foreground=color)
                        break
        except Exception as e:
            logger.debug(f"AudioVisualizerPlaceholder.set_active error: {e}")
    
    def update(self, data: Any = None) -> None:
        """Update internal data buffers with new audio data."""
        try:
            if not hasattr(self, '_data_buffer'):
                self._data_buffer = []
            if data is not None:
                self._data_buffer.append(data)
                if len(self._data_buffer) > 100:
                    self._data_buffer = self._data_buffer[-100:]
            self._last_update = data
        except Exception as e:
            logger.debug(f"AudioVisualizerPlaceholder.update error: {e}")

# The real AudioVisualizer (thoth_frame_audio_visualizer) has an incompatible API
# (no .frame, .get_frame(), .set_active() methods). VoiceFrame requires these,
# so we intentionally use the placeholder which provides the correct interface.
AudioVisualizer = AudioVisualizerPlaceholder
audio_visualizer_available = False
logger.info("Using AudioVisualizer placeholder for voice UI (real visualizer has incompatible API)")

class VoiceFrame(BaseFrame):
    """Full implementation for the Voice tab with ThothAI integration."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        event_bus: Optional[object] = None,
        name: str = "VoiceFrame",
        **kwargs,
    ) -> None:
        # Ensure we forward event_bus so BaseFrame can register correctly
        super().__init__(parent, event_bus=event_bus, name=name, **kwargs)

        self.logger = logging.getLogger(name)
        
        # Initialize state variables
        self.voice_active = False
        self.listening = False
        self.speaking = False
        self.last_command = ""
        self.last_response = ""
        self.command_history = []
        self.max_history = 50
        
        # Redis connection status
        self.redis_connected = False
        self.redis_port = 6380  # Mandatory port for Redis Quantum Nexus
        
        # ThothAI integration status
        self.thoth_available = False
        
        # Audio visualization (will be initialized if available)
        self.audio_visualizer = None
        
        self.logger.info("VoiceFrame initialized with real functionality")
        
        # Build the UI components
        self._build_ui()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the Voice tab UI with ThothAI integration and Redis connection status."""
        # Main container with padding
        main_container = tk.Frame(self, bg=KingdomStyles.COLORS["frame_bg"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Header section with status indicators
        header_frame = tk.Frame(main_container, bg=KingdomStyles.COLORS["frame_bg"])
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Title and status section
        title_frame = tk.Frame(header_frame, bg=KingdomStyles.COLORS["frame_bg"])
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        title_label = tk.Label(
            title_frame,
            text="Kingdom AI Voice System",
            font=("Arial", 16, "bold"),
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["text"]
        )
        title_label.pack(side=tk.LEFT, pady=5)
        
        # Status indicators container
        status_frame = tk.Frame(header_frame, bg=KingdomStyles.COLORS["frame_bg"])
        status_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Redis status
        redis_frame = tk.Frame(status_frame, bg=KingdomStyles.COLORS["frame_bg"])
        redis_frame.pack(side=tk.LEFT, padx=5)
        
        redis_label = tk.Label(
            redis_frame,
            text="Redis Quantum Nexus:",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["text"]
        )
        redis_label.pack(side=tk.LEFT)
        
        self.redis_status = tk.Label(
            redis_frame,
            text="Disconnected",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["error"]
        )
        self.redis_status.pack(side=tk.LEFT, padx=5)
        
        # ThothAI status
        thoth_frame = tk.Frame(status_frame, bg=KingdomStyles.COLORS["frame_bg"])
        thoth_frame.pack(side=tk.LEFT, padx=5)
        
        thoth_label = tk.Label(
            thoth_frame,
            text="ThothAI Status:",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["text"]
        )
        thoth_label.pack(side=tk.LEFT)
        
        self.thoth_status = tk.Label(
            thoth_frame,
            text="Initializing...",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["warning"]
        )
        self.thoth_status.pack(side=tk.LEFT, padx=5)
        
        # Voice system status
        voice_status_frame = tk.Frame(status_frame, bg=KingdomStyles.COLORS["frame_bg"])
        voice_status_frame.pack(side=tk.LEFT, padx=5)
        
        voice_label = tk.Label(
            voice_status_frame,
            text="Voice System:",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["text"]
        )
        voice_label.pack(side=tk.LEFT)
        
        self.voice_status = tk.Label(
            voice_status_frame,
            text="Inactive",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["warning"]
        )
        self.voice_status.pack(side=tk.LEFT, padx=5)
        
        # Main content area - split into left and right panels
        content_frame = tk.Frame(main_container, bg=KingdomStyles.COLORS["frame_bg"])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Left panel - Voice controls and visualization
        left_panel = tk.Frame(content_frame, bg=KingdomStyles.COLORS["frame_bg"])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Voice control buttons
        controls_frame = tk.Frame(left_panel, bg=KingdomStyles.COLORS["frame_bg"])
        controls_frame.pack(fill=tk.X, pady=5)
        
        # Voice recognition toggle button
        self.toggle_button = tk.Button(
            controls_frame, 
            text="Start Voice Recognition", 
            command=lambda: self._toggle_voice_recognition(),
            bg=KingdomStyles.COLORS["button_bg"],
            fg=KingdomStyles.COLORS["button_text"],
            activebackground=KingdomStyles.COLORS["button_hover"],
            activeforeground=KingdomStyles.COLORS["button_text"],
            font=(KingdomStyles.FONT_FAMILY, 10)
        )
        self.toggle_button.pack(side=tk.LEFT, padx=5)
        
        # Audio visualization area
        viz_frame = tk.Frame(left_panel, bg=KingdomStyles.COLORS["dark"], height=150)
        
        # Set up audio visualizer if available
        self.audio_visualization_frame = ttk.Frame(left_panel)
        self.audio_visualization_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        try:
            # Initialize the AudioVisualizer (which is actually our placeholder)
            self.audio_visualizer = AudioVisualizer(self.audio_visualization_frame)
            # Access the frame attribute and pack it
            if hasattr(self.audio_visualizer, 'frame'):
                self.audio_visualizer.frame.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            self.logger.error(f"Error initializing AudioVisualizer: {e}")
            # Visual placeholder if AudioVisualizer fails
            ttk.Label(self.audio_visualization_frame, 
                     text="Audio Visualization Unavailable",
                     foreground=KingdomStyles.COLORS["warning"]).pack(pady=20)
        
        # Current status display
        status_display_frame = tk.Frame(left_panel, bg=KingdomStyles.COLORS["frame_bg"])
        status_display_frame.pack(fill=tk.X, pady=10)
        
        status_label = tk.Label(
            status_display_frame,
            text="Current Status:",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["text"],
            font=("Arial", 10, "bold")
        )
        status_label.pack(anchor="w")
        
        self.current_status_text = tk.Text(
            status_display_frame,
            height=3,
            width=30,
            bg=KingdomStyles.COLORS["input_bg"],
            fg=KingdomStyles.COLORS["text"],
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.current_status_text.pack(fill=tk.X, pady=(5, 0))
        
        # Right panel - Command history and responses
        right_panel = tk.Frame(content_frame, bg=KingdomStyles.COLORS["frame_bg"])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Command history section
        history_frame = tk.Frame(right_panel, bg=KingdomStyles.COLORS["frame_bg"])
        history_frame.pack(fill=tk.BOTH, expand=True)
        
        history_label = tk.Label(
            history_frame,
            text="Command History:",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["text"],
            font=("Arial", 10, "bold")
        )
        history_label.pack(anchor="w")
        
        self.command_history_text = scrolledtext.ScrolledText(
            history_frame,
            height=12,
            bg=KingdomStyles.COLORS["input_bg"],
            fg=KingdomStyles.COLORS["text"],
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.command_history_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Bottom controls and configuration
        bottom_frame = tk.Frame(main_container, bg=KingdomStyles.COLORS["frame_bg"])
        bottom_frame.pack(fill=tk.X, pady=10)
        
        # Settings section
        settings_label = tk.Label(
            bottom_frame,
            text="Voice System Settings",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["text"],
            font=("Arial", 10, "bold")
        )
        settings_label.pack(anchor="w")
        
        settings_container = tk.Frame(bottom_frame, bg=KingdomStyles.COLORS["frame_bg"])
        settings_container.pack(fill=tk.X, pady=5)
        
        # Wake word detection checkbox
        self.wake_word_var = tk.BooleanVar(value=True)
        self.wake_word_check = ttk.Checkbutton(
            settings_container, 
            text="Wake Word Detection", 
            variable=self.wake_word_var,
            command=lambda: self._update_wake_word_config()
        )
        self.wake_word_check.pack(side=tk.LEFT, padx=5)
        
        # Reset button
        self.reset_button = tk.Button(
            settings_container, 
            text="Reset Voice System",
            command=lambda: self._reset_voice_system(),
            bg=KingdomStyles.COLORS["button_bg"],
            fg=KingdomStyles.COLORS["button_text"],
            activebackground=KingdomStyles.COLORS["button_hover"],
            activeforeground=KingdomStyles.COLORS["button_text"],
            font=(KingdomStyles.FONT_FAMILY, 10)
        )
        self.reset_button.pack(side=tk.RIGHT, padx=5)
        
        # Port display for Redis Quantum Nexus
        redis_port_frame = tk.Frame(bottom_frame, bg=KingdomStyles.COLORS["frame_bg"])
        redis_port_frame.pack(fill=tk.X, pady=10)
        
        redis_port_label = tk.Label(
            redis_port_frame,
            text=f"Redis Quantum Nexus Port: {self.redis_port} (Required)",
            bg=KingdomStyles.COLORS["frame_bg"],
            fg=KingdomStyles.COLORS["accent"],
            font=("Arial", 9)
        )
        redis_port_label.pack(side=tk.LEFT)
        
        # Initialize UI state
        self._update_status_display("Voice system initialized. Ready for commands.")
        self._update_redis_status(False)  # Default to disconnected until we get status

    # ------------------------------------------------------------------
    # UI Helper Methods
    # ------------------------------------------------------------------
    
    def _update_status_display(self, message: str, error: bool = False, warning: bool = False) -> None:
        """Update the status display text widget with a new message.
        
        Args:
            message: Message to display in the status area
            error: If True, display as error (red text)
            warning: If True, display as warning (yellow text)
        """
        self.current_status_text.config(state=tk.NORMAL)
        self.current_status_text.delete(1.0, tk.END)
        
        tag = None
        if error:
            tag = "error"
        elif warning:
            tag = "warning"
        elif "success" in message.lower() or "connected" in message.lower() or "ready" in message.lower():
            tag = "success"
            
        if tag:
            self.current_status_text.insert(tk.END, message, tag)
        else:
            self.current_status_text.insert(tk.END, message)
            
        self.current_status_text.config(state=tk.DISABLED)
    
    def _update_redis_status(self, connected: bool) -> None:
        """Update the Redis connection status indicator.
        
        Args:
            connected: True if Redis is connected, False otherwise
        """
        self.redis_connected = connected
        if connected:
            self.redis_status.config(text="Connected", fg=KingdomStyles.COLORS["success"])
        else:
            self.redis_status.config(text="Disconnected", fg=KingdomStyles.COLORS["error"])
    def _update_thoth_status(self, available: bool) -> None:
        """Update the ThothAI status indicator.
        
        Args:
            available: True if ThothAI is available, False otherwise
        """
        self.thoth_available = available
        if available:
            self.thoth_status.config(text="Ready", fg=KingdomStyles.COLORS["success"])
        else:
            self.thoth_status.config(text="Unavailable", fg=KingdomStyles.COLORS["error"])
    
    def _update_voice_system_status(self, status: str) -> None:
        """Update the voice system status indicator.
        
        Args:
            status: Status string (e.g., "active", "inactive", "listening", "speaking")
        """
        status = status.lower()
        
        if status == "active":
            self.voice_status.config(text="Active", fg=KingdomStyles.COLORS["success"])
            self.voice_active = True
            self.toggle_button.config(text="Stop Voice Recognition")
        elif status == "inactive":
            self.voice_status.config(text="Inactive", fg=KingdomStyles.COLORS["warning"])
            self.voice_active = False
            self.toggle_button.config(text="Start Voice Recognition")
        elif status == "listening":
            self.voice_status.config(text="Listening", fg=KingdomStyles.COLORS["success"])
            self.listening = True
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                self.audio_visualizer.set_active(True)
        elif status == "speaking":
            self.voice_status.config(text="Speaking", fg=KingdomStyles.COLORS["primary"])
            self.speaking = True
        elif status == "error":
            self.voice_status.config(text="Error", fg=KingdomStyles.COLORS["error"])
            self.voice_active = False
            self.toggle_button.config(text="Start Voice Recognition")
    
    def _add_to_command_history(self, command: str, response: str = None) -> None:
        """Add a command-response pair to the command history.
        
        Args:
            command: The voice command that was processed
            response: The AI response to the command (optional)
        """
        try:
            self.command_history_text.config(state=tk.NORMAL)
            
            # Format timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Format and add command
            self.command_history_text.insert(tk.END, f"[{timestamp}] You: ")
            self.command_history_text.insert(tk.END, f"{command}\n", "command")
            
            # Add response if provided
            if response:
                self.command_history_text.insert(tk.END, f"AI: ")
                self.command_history_text.insert(tk.END, f"{response}\n\n", "response")
            
            # Apply tags/styling
            self.command_history_text.tag_config("command", foreground=KingdomStyles.COLORS["accent"])
            self.command_history_text.tag_config("response", foreground=KingdomStyles.COLORS["success"])
            
            # Scroll to bottom
            self.command_history_text.see(tk.END)
            self.command_history_text.config(state=tk.DISABLED)
            
            # Update instance variables
            self.last_command = command
            if response:
                self.last_response = response
                
            # Keep history within max limit
            self.command_history.append((command, response))
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
        except Exception as e:
            self.logger.error(f"Error updating command history: {e}")

    def on_show(self) -> None:
        """Called when this frame becomes visible."""
        # Note: BaseFrame may not have on_show method, so we don't call super() here
        self.logger.info("VoiceFrame is now visible")
        
        # Refresh status when tab becomes visible
        if hasattr(self, "event_bus") and self.event_bus is not None:
            try:
                # Make critical status checks for Redis Quantum Nexus on port 6380
                asyncio.create_task(self.event_bus.publish("redis.status.request", {
                    "source": "voice_frame",
                    "port": 6380  # MUST use port 6380 for Redis Quantum Nexus as per requirements
                }))
                
                # Check ThothAI and voice system status
                asyncio.create_task(self.event_bus.publish("thoth.status.request", {
                    "source": "voice_frame"
                }))
                
                asyncio.create_task(self.event_bus.publish("voice.status.request", {
                    "source": "voice_frame"
                }))
            except Exception as e:
                self.logger.error(f"Error refreshing status on show: {e}")

    # ------------------------------------------------------------------
    # Button Command Handlers
    # ------------------------------------------------------------------
    
    def _toggle_voice_recognition(self) -> None:
        """Toggle voice recognition on/off in response to button click."""
        if not self.voice_active:
            self._update_status_display("Starting voice recognition...")
            asyncio.create_task(self._publish_voice_toggle(True))
        else:
            self._update_status_display("Stopping voice recognition...")
            asyncio.create_task(self._publish_voice_toggle(False))
    
    def _update_wake_word_config(self) -> None:
        """Update wake word detection configuration based on checkbox."""
        wake_word_enabled = self.wake_word_var.get()
        config_update = {"wake_word_detection": wake_word_enabled}
        
        asyncio.create_task(self._publish_voice_config(config_update))
        status = "enabled" if wake_word_enabled else "disabled"
        self._update_status_display(f"Wake word detection {status}")
    
    def _reset_voice_system(self) -> None:
        """Reset the voice system by stopping and restarting it."""
        self._update_status_display("Resetting voice system...")
        
        async def reset_sequence():
            # Stop voice system
            if hasattr(self, "event_bus") and self.event_bus is not None:
                await self._publish_voice_toggle(False)
                await asyncio.sleep(1)  # Wait for system to stop
                
                # Reset ThothAI connection
                await self.event_bus.publish("thoth.reset", {"source": "voice_frame"})
                    
                # Wait a moment before restarting
                await asyncio.sleep(1)
                
                # Start voice system again if event bus is available
                await self._publish_voice_toggle(True)
                    
                # Update status
                self._update_status_display("Voice system reset complete")
            else:
                self._update_status_display("Could not reset voice system - no event bus available", warning=True)
        
        # Kick off the reset sequence
        asyncio.create_task(reset_sequence())
    
    # ------------------------------------------------------------------
    # Event publishing methods
    # ------------------------------------------------------------------
    
    async def _publish_voice_toggle(self, active: bool) -> None:
        """Publish voice.toggle event to activate/deactivate voice recognition.
        
        Args:
            active: True to activate, False to deactivate
        """
        if hasattr(self, "event_bus") and self.event_bus is not None:
            await self.event_bus.publish("voice.toggle", {
                "active": active,
                "source": "voice_frame"
            })
    
    async def _publish_voice_config(self, config_updates: dict) -> None:
        """Publish voice.configure event with config updates.
        
        Args:
            config_updates: Dictionary of config parameters to update
        """
        if hasattr(self, "event_bus") and self.event_bus is not None:
            await self.event_bus.publish("voice.configure", {
                "config": config_updates,
                "source": "voice_frame"
            })
    
    # ------------------------------------------------------------------
    # Event Handler Registration
    # ------------------------------------------------------------------
    
    def register_event_handlers(self) -> None:
        """Register event handlers for the event bus."""
        if not hasattr(self, "event_bus") or self.event_bus is None:
            self.logger.warning("No event bus available for VoiceFrame")
            return
        
        try:    
            handlers = [
                ("voice.status", self._handle_voice_status),
                ("voice.input", self._handle_voice_input),
                ("voice.response", self._handle_voice_response),
                ("voice.speaking.started", self._handle_voice_speaking),
                ("redis.status", self._handle_redis_status),
                ("thoth.status", self._handle_thoth_status),
            ]
            
            for topic, handler in handlers:
                self._safe_subscribe(topic, handler)
            
            self.logger.info("VoiceFrame event handlers registered")
            
            # Request initial status of Redis Quantum Nexus - MANDATORY on port 6380
            asyncio.create_task(self.event_bus.publish("redis.status.request", {
                "source": "voice_frame",
                "port": 6380  # MUST be port 6380 for Redis Quantum Nexus
            }))
            
            # Check ThothAI and voice system status
            asyncio.create_task(self.event_bus.publish("thoth.status.request", {
                "source": "voice_frame"
            }))
            
            asyncio.create_task(self.event_bus.publish("voice.status.request", {
                "source": "voice_frame"
            }))
        except Exception as e:
            self.logger.error(f"Error registering event handlers: {e}")

    # ------------------------------------------------------------------
    # Event handlers for event bus events
    # ------------------------------------------------------------------
    
    async def _handle_voice_status(self, event_data: dict) -> None:
        """Updates UI when voice-status changes.

        This is called, asynchronously, when the `voice.status` event is emitted.
        
        Args:
            event_data: Voice status event data containing the current status
        """
        try:
            status = event_data.get("status", "")
            self.logger.info(f"Voice status update: {status}")
            
            # Update UI based on status
            if status and self.master and hasattr(self.master, 'winfo_exists') and self.master.winfo_exists():
                # Switch to main thread for UI updates
                self.master.after(0, lambda: self._update_voice_system_status(status))
                self.master.after(0, lambda: self._update_status_display(f"Voice system {status}"))
        except Exception as e:
            self.logger.error(f"Error handling voice status update: {e}")
    
    async def _handle_voice_input(self, event_data: dict) -> None:
        """Update UI when voice input is received.
        
        Args:
            event_data: Voice input event data
        """
        try:
            text = event_data.get("text", "")
            if text and self.master and hasattr(self.master, 'winfo_exists') and self.master.winfo_exists():
                # Add to command history without response (yet)
                self.master.after(0, lambda: self._add_to_command_history(text))
                self.master.after(0, lambda: self._update_status_display(f"Voice command: {text}"))
                
                # Show listening animation if we have the audio visualizer
                if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                    self.audio_visualizer.set_active(True)
        except Exception as e:
            self.logger.error(f"Error handling voice input: {e}")
    
    async def _handle_voice_response(self, event_data: dict) -> None:
        """Update UI when voice response is received.
        
        Args:
            event_data: Voice response event data
        """
        try:
            command = event_data.get("original_command", "")
            response = event_data.get("response", "")
            
            if response and self.master and hasattr(self.master, 'winfo_exists') and self.master.winfo_exists():
                # Update with the response
                if command:
                    self.master.after(0, lambda: self._add_to_command_history(command, response))
                self.master.after(0, lambda: self._update_status_display(f"AI: {response}"))
        except Exception as e:
            self.logger.error(f"Error handling voice response: {e}")
    
    async def _handle_voice_speaking(self, event_data: dict) -> None:
        """Update UI when the system is speaking the response.
        
        Args:
            event_data: Voice speaking event data
        """
        try:
            is_speaking = event_data.get("speaking", False)
            if self.master and hasattr(self.master, 'winfo_exists') and self.master.winfo_exists():
                if is_speaking:
                    self.master.after(0, lambda: self._update_voice_system_status("speaking"))
                else:
                    self.master.after(0, lambda: self._update_voice_system_status("active"))
        except Exception as e:
            self.logger.error(f"Error handling voice speaking status: {e}")
    
    async def _handle_thoth_status(self, event_data: dict) -> None:
        """Handle ThothAI status updates.
        
        Args:
            event_data: ThothAI status event data
        """
        try:
            available = event_data.get("available", False)
            self.logger.info(f"ThothAI status: {'available' if available else 'unavailable'}")
            
            # Update UI on main thread
            if self.master and hasattr(self.master, 'winfo_exists') and self.master.winfo_exists():
                self.master.after(0, lambda: self._update_thoth_status(available))
                
                if available:
                    self.master.after(0, lambda: self._update_status_display("ThothAI connected and ready"))
                else:
                    self.master.after(0, lambda: self._update_status_display(
                        "ThothAI unavailable - voice commands may not work properly", 
                        warning=True
                    ))
        except Exception as e:
            self.logger.error(f"Error handling ThothAI status update: {e}")
    
    # ------------------------------------------------------------------
    # Event-bus integration
    # ------------------------------------------------------------------
    
    async def _handle_redis_status(self, event_data: dict) -> None:
        """Handle Redis Quantum Nexus connection status events.
        
        Args:
            event_data: Redis status event data
        """
        try:
            connected = event_data.get("connected", False)
            port = event_data.get("port", 0)
            
            # Verify this is for the Quantum Nexus (MUST be port 6380)
            if port == self.redis_port:
                self.logger.info(f"Redis Quantum Nexus status on port {port}: {'connected' if connected else 'disconnected'}")
                
                # Log critical information about Redis configuration
                if not connected:
                    self.logger.critical(f"Failed to connect to Redis Quantum Nexus on port {port}")
                    self.logger.critical("Redis Quantum Nexus connection is MANDATORY - no fallbacks permitted")
                    self.logger.critical("System may be unstable without Redis connection on port 6380")
                
                # Update UI on main thread
                if self.master and hasattr(self.master, 'winfo_exists') and self.master.winfo_exists():
                    self.master.after(0, lambda: self._update_redis_status(connected))
                    
                    if connected:
                        self.master.after(0, lambda: self._update_status_display(
                            "Redis Quantum Nexus connected on port 6380. System stable.",
                            error=False
                        ))
                    else:
                        # CRITICAL ERROR - System requires Redis connection
                        error_message = "CRITICAL ERROR: Redis Quantum Nexus disconnected on port 6380. System cannot function!"
                        self.logger.critical(error_message)
                        
                        # Update UI to show critical error
                        self.master.after(0, lambda: self._update_status_display(error_message, error=True))
                        
                        # Disable voice functionality as Redis is mandatory (no fallbacks permitted)
                        if self.voice_active and hasattr(self, "event_bus") and self.event_bus is not None:
                            asyncio.create_task(self._publish_voice_toggle(False))
        except Exception as e:
            self.logger.error(f"Error handling Redis status update: {e}")

    # ... (rest of the code remains the same)
    def _connect_events(self) -> None:  
        """Register all event handlers when the event bus is available.

        Must be called after `event_bus` is set.
        """
        if hasattr(self, "event_bus") and self.event_bus is not None:
            self.register_event_handlers()
            
            # CRITICAL: Immediately verify Redis Quantum Nexus connection
            # This is mandatory and must use port 6380
            asyncio.create_task(self.event_bus.publish("redis.status.request", {
                "source": "voice_frame",
                "port": 6380,  # MUST be port 6380 for Redis Quantum Nexus
                "critical": True
            }))
        else:
            self.logger.warning("No event bus available, skipping event registration")

    # ------------------------------------------------------------------
    # Public API (placeholder)
    # ------------------------------------------------------------------
    async def initialize(self):  # noqa: D401 – async API for consistency
        """Async initialisation hook for VoiceFrame.
        
        Performs initial setup and Redis Quantum Nexus connection check.
        """
        # Request Redis Quantum Nexus status on the mandatory port (6380)
        # This is CRITICAL - system must verify Redis connection on startup
        # Redis Quantum Nexus MUST use port 6380 without any fallbacks
        if hasattr(self, "event_bus") and self.event_bus is not None:
            try:
                self.logger.info("Checking Redis Quantum Nexus connection on port 6380...")
                
                # Request immediate status check for Redis Quantum Nexus
                # The Quantum Nexus MUST use port 6380 as per user requirements
                await self.event_bus.publish("redis.status.request", {
                    "source": "voice_frame", 
                    "port": 6380,  # MUST be port 6380 for Quantum Nexus - critical requirement
                    "critical": True,  # Mark as critical check
                    "password": "QuantumNexus2025"  # Use the default password
                })
                
                # Update UI to show we're checking Redis
                self._update_status_display("Verifying Redis Quantum Nexus connection on port 6380...")
                
                # Registration was successful
                return True
            except Exception as e:
                self.logger.error(f"Failed to initialize VoiceFrame: {e}")
                self._update_status_display("Failed to initialize voice system", error=True)
                return False
        else:
            self.logger.error("No event bus available, VoiceFrame initialization failed")
            self._update_status_display("Voice system initialization failed: No event bus", error=True)
            return False
