"""ThothFrame Audio Visualizer Component

This module provides audio visualization functionality for the ThothFrame,
creating a circular waveform visualization that responds to audio input.
It integrates with the voice system to provide visual feedback when ThothAI is speaking.
"""
import tkinter as tk
from tkinter import Canvas
import math
import threading
import time
import numpy as np
import struct
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
import logging

logger = logging.getLogger("KingdomAI.ThothFrame.AudioVisualizer")

class AudioVisualizer:
    """Audio visualizer component for ThothFrame.
    
    This class handles the audio visualization for the ThothFrame,
    providing a circular waveform that responds to audio input.
    It can be used in both active mode (with actual audio input)
    or simulation mode (when PyAudio is not available).
    """
    
    def __init__(self, parent_frame):
        """Initialize the audio visualizer.
        
        Args:
            parent_frame: The parent ThothFrame that contains this visualizer
        """
        self.parent = parent_frame
        self.logger = logging.getLogger("KingdomAI.ThothFrame.AudioVisualizer")
        
        # Canvas for visualization
        self.canvas = None
        
        # Audio visualization state
        self.wave_data = []
        self.wave_points = 100
        self.wave_amplitude = 0.5
        self.wave_frequency = 2
        self.wave_phase = 0
        self.wave_animation_active = False
        self.animation_lock = threading.Lock()
        
        # PyAudio components
        self.audio_stream = None
        self.pyaudio_instance = None
        
        # Animation state
        self.is_speaking = False
        self.visualizer_active = False
        self.breathing_scale = 1.0
        self.breathing_direction = 1
        self.outer_circle_expansion = 0
        self.visualizer_thread = None
        
        # Audio visualization constants
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16 if PYAUDIO_AVAILABLE else None
        self.CHANNELS = 1
        self.RATE = 44100
        self.SMOOTHING_FACTOR = 0.8
        self.BREATHING_SCALE_MIN = 0.95
        self.BREATHING_SCALE_MAX = 1.05
        self.BREATHING_SPEED = 0.005
        self.OUTER_CIRCLE_BASE_RADIUS_RATIO = 0.8
        self.OUTER_CIRCLE_MAX_EXPANSION = 0.1
        self.INNER_SHAPE_BASE_RADIUS_RATIO = 0.25
        self.INNER_SHAPE_MAX_MODULATION = 0.5
        
        # Initialize data array
        self.wave_data = [0] * self.wave_points
        
    def create_canvas(self, parent_widget):
        """Create the canvas for visualization.
        
        Args:
            parent_widget: The parent widget to contain the canvas
        """
        self.canvas = Canvas(parent_widget, bg='#0d1117', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind('<Configure>', self._on_resize)
        return self.canvas
        
    def initialize(self):
        """Initialize the audio visualizer."""
        try:
            # Check if PyAudio is available
            if not PYAUDIO_AVAILABLE:
                self.logger.warning("PyAudio not available. Audio visualization will be simulated.")
                self.parent.add_system_message("Audio visualization will be simulated (PyAudio not installed)", error=False)
            else:
                # Initialize PyAudio
                self.pyaudio_instance = pyaudio.PyAudio()
            
            # Draw initial visualization
            if self.canvas:
                self._draw_initial_visualizer()
            
            self.logger.info("Audio visualizer initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing audio visualizer: {e}")
            if hasattr(self.parent, 'add_system_message'):
                self.parent.add_system_message(f"Audio visualization unavailable: {e}", error=True)
    
    def start_visualization(self):
        """Start the audio visualization."""
        if self.visualizer_active:
            return
            
        self.visualizer_active = True
        
        try:
            if PYAUDIO_AVAILABLE and self.pyaudio_instance:
                # Open audio stream for capturing
                self.audio_stream = self.pyaudio_instance.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    output=False,
                    frames_per_buffer=self.CHUNK,
                    stream_callback=self._audio_callback
                )
            
            # Start animation in a separate thread
            self.visualizer_thread = threading.Thread(
                target=self._animate_visualizer,
                daemon=True
            )
            self.visualizer_thread.start()
            
            self.logger.info("Audio visualizer started")
        except Exception as e:
            self.logger.error(f"Error starting audio visualizer: {e}")
            self.visualizer_active = False
    
    def stop_visualization(self):
        """Stop the audio visualization."""
        self.visualizer_active = False
        
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
                self.audio_stream = None
            except Exception as e:
                self.logger.error(f"Error stopping audio stream: {e}")
                
        # Reset visualizer to initial state
        self._draw_initial_visualizer()
    
    def set_speaking_state(self, is_speaking):
        """Set whether ThothAI is currently speaking.
        
        Args:
            is_speaking: Boolean indicating if ThothAI is speaking
        """
        self.is_speaking = is_speaking
        
        if is_speaking and not self.visualizer_active:
            self.start_visualization()
        elif not is_speaking and self.visualizer_active:
            # Delay stopping to allow for a smooth transition
            if hasattr(self.parent, 'after'):
                self.parent.after(1000, lambda: self.stop_visualization() if not self.is_speaking else None)
    
    def cleanup(self):
        """Clean up resources used by the visualizer."""
        self.stop_visualization()
        
        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
            except Exception as e:
                self.logger.error(f"Error terminating PyAudio: {e}")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Process audio data from the stream."""
        try:
            # Convert byte data to int array
            data = struct.unpack(f'{self.CHUNK}h', in_data)
            
            # Get max amplitude
            amplitude = max(abs(x) for x in data) / 32768.0  # Normalize to 0-1
            
            # Store data for visualization
            with self.animation_lock:
                # Update wave data (shift left and add new value)
                self.wave_data.pop(0)
                self.wave_data.append(amplitude)
        except Exception as e:
            self.logger.error(f"Error in audio callback: {e}")
            
        return (in_data, pyaudio.paContinue)
    
    def _animate_visualizer(self):
        """Animation loop for the audio visualizer."""
        try:
            while self.visualizer_active:
                # Update visualization on the main thread
                if hasattr(self.parent, 'after'):
                    self.parent.after(30, self._update_visualization)
                
                # Sleep to control frame rate
                time.sleep(0.03)
        except Exception as e:
            self.logger.error(f"Error in visualizer animation thread: {e}")
    
    def _update_visualization(self):
        """Update the visualization on the canvas."""
        if not self.visualizer_active or not self.canvas:
            return
            
        try:
            # Get canvas dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1 or canvas_height <= 1:
                return  # Canvas not ready
                
            center_x = canvas_width / 2
            center_y = canvas_height / 2
            
            # Clear canvas
            self.canvas.delete("all")
            
            # If we're not using PyAudio, simulate some data
            if not PYAUDIO_AVAILABLE or not self.audio_stream:
                # Simulate audio data for visualization
                with self.animation_lock:
                    for i in range(len(self.wave_data)):
                        # Generate a sine wave with some randomness
                        if self.is_speaking:
                            value = 0.3 + 0.2 * math.sin(self.wave_phase + i/5) + 0.1 * np.random.random()
                        else:
                            value = 0.05 + 0.03 * math.sin(self.wave_phase + i/10)
                        self.wave_data[i] = value
                    
                    # Update phase for animation
                    self.wave_phase += 0.1
            
            # Calculate average amplitude
            with self.animation_lock:
                avg_amplitude = sum(self.wave_data) / len(self.wave_data) if self.wave_data else 0
            
            # Breathing effect
            if avg_amplitude < 0.05:
                # Subtle breathing when quiet
                self.breathing_scale += self.breathing_direction * self.BREATHING_SPEED
                if self.breathing_scale >= self.BREATHING_SCALE_MAX:
                    self.breathing_scale = self.BREATHING_SCALE_MAX
                    self.breathing_direction = -1
                elif self.breathing_scale <= self.BREATHING_SCALE_MIN:
                    self.breathing_scale = self.BREATHING_SCALE_MIN
                    self.breathing_direction = 1
            else:
                # Scale up with sound
                self.breathing_scale = self.BREATHING_SCALE_MIN + \
                    (avg_amplitude * (self.BREATHING_SCALE_MAX - self.BREATHING_SCALE_MIN) * 1.5)
                self.breathing_scale = min(self.breathing_scale, self.BREATHING_SCALE_MAX + 0.1)
            
            # Outer circle movement with amplitude
            target_expansion = avg_amplitude * self.OUTER_CIRCLE_MAX_EXPANSION
            self.outer_circle_expansion += (target_expansion - self.outer_circle_expansion) * 0.3
            
            # Calculate base radius and apply breathing/expansion
            base_radius = min(canvas_width, canvas_height) * 0.4
            outer_radius = base_radius * (1 + self.outer_circle_expansion) * self.breathing_scale
            
            # Draw outer glowing circle
            glow_intensity = 0.5 + avg_amplitude * 0.5
            for i in range(3):
                glow_radius = outer_radius + (i * (5 + avg_amplitude * 10))
                opacity = (0.7 - (i * 0.2)) * glow_intensity
                glow_color = self._get_rgba_color(0, 255, 255, int(opacity * 255))
                
                self.canvas.create_oval(
                    center_x - glow_radius, center_y - glow_radius,
                    center_x + glow_radius, center_y + glow_radius,
                    outline=glow_color, width=2 + int(avg_amplitude * 3)
                )
            
            # Draw inner "quantum string" shape
            inner_radius = base_radius * self.INNER_SHAPE_BASE_RADIUS_RATIO * self.breathing_scale
            
            # Create points for the inner shape
            points = []
            for i in range(self.wave_points):
                # Get the data point (or 0 if not available)
                with self.animation_lock:
                    amplitude = self.wave_data[i % len(self.wave_data)] if self.wave_data else 0
                
                # Calculate angle and radius
                angle = i * (math.pi * 2) / self.wave_points
                radius = inner_radius * (1 + amplitude * self.INNER_SHAPE_MAX_MODULATION)
                
                # Calculate coordinates
                x = center_x + math.cos(angle) * radius
                y = center_y + math.sin(angle) * radius
                
                points.extend([x, y])
            
            # Draw the inner shape
            if points:
                self.canvas.create_polygon(
                    *points,
                    outline="#00ffff",
                    fill="",
                    width=2,
                    smooth=True
                )
            
            # Draw text indicating speaking status
            text = "ThothAI Speaking" if self.is_speaking else "ThothAI Voice"
            self.canvas.create_text(
                center_x, center_y,
                text=text,
                fill="#00ffff",
                font=("Inter", 14, "bold")
            )
            
        except Exception as e:
            self.logger.error(f"Error updating visualization: {e}")
    
    def _on_resize(self, event):
        """Handle canvas resize events."""
        if self.canvas:
            # Redraw visualizer elements
            self._draw_initial_visualizer()
    
    def _draw_initial_visualizer(self):
        """Draw the initial visualizer state."""
        if not self.canvas:
            return
            
        self.canvas.delete("all")
        
        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            # Canvas not ready yet
            if hasattr(self.parent, 'after'):
                self.parent.after(100, self._draw_initial_visualizer)
            return
            
        # Calculate center coordinates and radius
        center_x = canvas_width / 2
        center_y = canvas_height / 2
        radius = min(canvas_width, canvas_height) * 0.4  # 40% of the smaller dimension
        
        # Draw outer circle with glow effect
        # Create multiple circles with decreasing opacity for glow effect
        for i in range(3):
            glow_radius = radius + (i * 5)
            opacity = 0.7 - (i * 0.2)  # Decreasing opacity
            glow_color = self._get_rgba_color(0, 255, 255, int(opacity * 255))
            
            self.canvas.create_oval(
                center_x - glow_radius, center_y - glow_radius,
                center_x + glow_radius, center_y + glow_radius,
                outline=glow_color, width=2, tags="outer_circle"
            )
        
        # Draw inner circle
        inner_radius = radius * 0.6
        self.canvas.create_oval(
            center_x - inner_radius, center_y - inner_radius,
            center_x + inner_radius, center_y + inner_radius,
            outline="#00ffff", width=1, tags="inner_circle"
        )
        
        # Draw text
        self.canvas.create_text(
            center_x, center_y,
            text="ThothAI Voice",
            fill="#00ffff",
            font=("Inter", 14, "bold"),
            tags="visualizer_text"
        )
    
    def _get_rgba_color(self, r, g, b, a):
        """Convert RGBA color to hex format for Tkinter."""
        return f'#{r:02x}{g:02x}{b:02x}'
