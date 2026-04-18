#!/usr/bin/env python3
"""
Kingdom AI - Enhanced UI Components

This module provides RGB animated borders and futuristic styling components
for the Kingdom AI GUI, ensuring a consistent visual experience across all
frames, tabs, and UI elements.
"""

import math
import time
import colorsys
import threading
from typing import Optional, List, Dict, Any, Callable, Tuple, Union

import tkinter as tk
from tkinter import ttk, font

class RGBColorManager:
    """Manages RGB color cycling for animated components."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of the RGBColorManager."""
        if cls._instance is None:
            cls._instance = RGBColorManager()
        return cls._instance
    
    def __init__(self):
        """Initialize the RGB color manager."""
        self.update_interval_ms = 50
        self.subscribers = []
        self._hue = 0
        self.running = False
        self.animation_thread = None
    
    def start(self):
        """Start the animation thread if not already running."""
        if not self.running:
            self.running = True
            self.animation_thread = threading.Thread(target=self._animation_loop, daemon=True)
            self.animation_thread.start()
    
    def stop(self):
        """Stop the animation thread."""
        self.running = False
        if self.animation_thread and self.animation_thread.is_alive():
            self.animation_thread.join(timeout=1.0)
    
    def subscribe(self, callback):
        """Subscribe a callback function to RGB color updates."""
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            
        # Start animation if this is the first subscriber
        if len(self.subscribers) == 1:
            self.start()
    
    def unsubscribe(self, callback):
        """Unsubscribe a callback function."""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            
        # Stop animation if no subscribers left
        if len(self.subscribers) == 0:
            self.stop()
    
    def _animation_loop(self):
        """Main animation loop that updates RGB colors."""
        while self.running:
            # Update color cycle position
            self._hue = (self._hue + 0.01) % 1.0
            
            # Generate RGB color from HSV (hue, saturation, value)
            r, g, b = colorsys.hsv_to_rgb(self._hue, 1.0, 1.0)
            
            # Convert to hex color string
            hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            
            # Notify all subscribers
            for callback in self.subscribers[:]:  # Copy list to avoid modification during iteration
                try:
                    callback(hex_color)
                except Exception as e:
                    print(f"Error in RGB animation callback: {e}")
            
            # Sleep for update interval
            time.sleep(self.update_interval_ms / 1000.0)

class EnhancedRGBFrame(tk.Frame):
    """Frame with animated RGB border effect."""
    
    def __init__(self, parent, border_width=3, corner_radius=10, bg_color="#1a1a2e", **kwargs):
        """Initialize the RGB border frame."""
        super().__init__(parent, bg=bg_color, highlightthickness=0, **kwargs)
        
        # Border properties
        self.border_width = border_width
        self.corner_radius = corner_radius
        self.bg_color = bg_color
        self._current_rgb = "#00a0ff"  # Default blue
        
        # Create canvas for drawing the border
        self.canvas = tk.Canvas(
            self, 
            bg=bg_color,
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Inner frame for content
        padding = border_width + 5
        self.inner_frame = tk.Frame(
            self.canvas,
            bg=bg_color,
            highlightthickness=0
        )
        
        # Create canvas window for inner frame
        self.canvas_window = self.canvas.create_window(
            padding, 
            padding, 
            anchor=tk.NW, 
            window=self.inner_frame
        )
        
        # Border ID for updating color
        self.border_id = None
        
        # Bind events for resizing
        self.bind("<Configure>", self._on_resize)
        
        # Subscribe to RGB color manager
        rgb_manager = RGBColorManager.get_instance()
        rgb_manager.subscribe(self._update_border_color)
        
        # Initial draw
        self._draw_border()
    
    def _on_resize(self, event):
        """Handle resize events to update border and inner frame."""
        width, height = event.width, event.height
        padding = self.border_width + 5
        
        # Update inner frame size
        inner_width = max(0, width - padding * 2)
        inner_height = max(0, height - padding * 2)
        self.canvas.itemconfig(
            self.canvas_window, 
            width=inner_width, 
            height=inner_height
        )
        
        # Redraw border
        self._draw_border()
    
    def _draw_border(self):
        """Draw the RGB animated border."""
        width, height = self.winfo_width(), self.winfo_height()
        
        # Clear previous border if it exists
        if self.border_id is not None:
            self.canvas.delete(self.border_id)
        
        # Draw rounded rectangle border
        x0, y0 = self.border_width / 2, self.border_width / 2
        x1, y1 = width - self.border_width / 2, height - self.border_width / 2
        
        self.border_id = self.canvas.create_rectangle(
            x0, y0, x1, y1,
            outline=self._current_rgb,
            width=self.border_width,
            tags=("border",)
        )
        
        # Bring inner frame to front
        self.canvas.tag_raise(self.canvas_window)
    
    def _update_border_color(self, hex_color):
        """Update the border color."""
        if not self.winfo_exists():
            # Widget no longer exists, unsubscribe from color manager
            try:
                rgb_manager = RGBColorManager.get_instance()
                rgb_manager.unsubscribe(self._update_border_color)
            except Exception:
                pass
            return
        
        try:
            self._current_rgb = hex_color
            if self.border_id is not None and self.canvas.winfo_exists():
                self.canvas.itemconfig(self.border_id, outline=hex_color)
        except tk.TclError:
            # Widget or canvas was destroyed, unsubscribe from color manager
            try:
                rgb_manager = RGBColorManager.get_instance()
                rgb_manager.unsubscribe(self._update_border_color)
            except Exception:
                pass
        except Exception:
            # Silently handle any other errors during animation
            pass
            
    def destroy(self):
        """Override destroy to properly clean up resources."""
        try:
            # Unsubscribe from color manager before destruction
            rgb_manager = RGBColorManager.get_instance()
            rgb_manager.unsubscribe(self._update_border_color)
        except Exception:
            pass
        
        # Call the parent class destroy method
        super().destroy()
    
    # The destroy method is now defined above with improved error handling

class EnhancedGlowButton(tk.Button):
    """Button with futuristic glowing effect."""
    
    def __init__(self, parent, text="", command=None, glow_color="#00a0ff", **kwargs):
        """Initialize the glowing button."""
        bg_color = kwargs.pop("bg", "#2d3748")
        fg_color = kwargs.pop("fg", "#e0f0ff")
        
        # Create button with custom styling
        super().__init__(
            parent, 
            text=text,
            command=command,
            bg=bg_color,
            fg=fg_color,
            activebackground="#364156",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            borderwidth=0,
            padx=15,
            pady=8,
            font=("Orbitron", 10, "bold"),
            **kwargs
        )
        
        # Store initial colors
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.glow_color = glow_color
        self._current_rgb = glow_color
        
        # Animation state
        self._animation_active = False
        self._animation_timer = None
        
        # Bind hover events
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
        # Subscribe to RGB color manager
        rgb_manager = RGBColorManager.get_instance()
        rgb_manager.subscribe(self._update_glow_color)
        
        # Draw border
        self._update_styling()
    
    def _on_enter(self, event):
        """Handle mouse enter event."""
        self._animation_active = True
        self._start_glow_animation()
    
    def _on_leave(self, event):
        """Handle mouse leave event."""
        self._animation_active = False
        self._stop_glow_animation()
        self.config(bg=self.bg_color)
    
    def _start_glow_animation(self):
        """Start the glow animation."""
        self._glow_step(0)
    
    def _stop_glow_animation(self):
        """Stop the glow animation."""
        if self._animation_timer is not None:
            self.after_cancel(self._animation_timer)
            self._animation_timer = None
    
    def _glow_step(self, step):
        """Perform one step of the glow animation."""
        if not self._animation_active or not self.winfo_exists():
            return
        
        # Calculate glow intensity using sine wave
        intensity = 0.5 + 0.5 * math.sin(step * 0.1)
        
        # Calculate color blend between background and glow color
        r1, g1, b1 = int(self.bg_color[1:3], 16), int(self.bg_color[3:5], 16), int(self.bg_color[5:7], 16)
        r2, g2, b2 = int(self._current_rgb[1:3], 16), int(self._current_rgb[3:5], 16), int(self._current_rgb[5:7], 16)
        
        blend_factor = 0.2 + 0.3 * intensity
        r = int(r1 * (1 - blend_factor) + r2 * blend_factor)
        g = int(g1 * (1 - blend_factor) + g2 * blend_factor)
        b = int(b1 * (1 - blend_factor) + b2 * blend_factor)
        
        glow_color = f"#{r:02x}{g:02x}{b:02x}"
        self.config(bg=glow_color)
        
        # Schedule next animation frame
        self._animation_timer = self.after(50, lambda: self._glow_step(step + 1))
    
    def _update_glow_color(self, hex_color):
        """Update the glow color."""
        if not self.winfo_exists():
            return
        
        try:
            self._current_rgb = hex_color
            self._update_styling()
        except Exception:
            # Silently handle any errors during animation
            pass
    
    def _update_styling(self):
        """Update button styling."""
        # Apply styling
        self.config(
            highlightbackground=self._current_rgb,
            highlightthickness=2,
            highlightcolor=self._current_rgb
        )
    
    def destroy(self):
        """Clean up resources before destroying the button."""
        self._stop_glow_animation()
        rgb_manager = RGBColorManager.get_instance()
        rgb_manager.unsubscribe(self._update_glow_color)
        super().destroy()

class EnhancedStatusBar(tk.Frame):
    """Status bar with futuristic styling and RGB animations."""
    
    def __init__(self, parent, bg_color="#1a1a2e", **kwargs):
        """Initialize the status bar."""
        super().__init__(parent, bg=bg_color, **kwargs)
        
        # Store initial colors
        self.bg_color = bg_color
        self._current_rgb = "#00a0ff"  # Default blue
        
        # Create layout for status elements
        self.status_label = tk.Label(
            self,
            text="SYSTEM READY",
            font=("Orbitron", 10),
            fg="#00ff7f",  # Bright green
            bg=bg_color
        )
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Spacer
        tk.Frame(self, bg=bg_color).pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        # Indicators dictionary
        self.indicators = {}
        
        # Subscribe to RGB color manager
        rgb_manager = RGBColorManager.get_instance()
        rgb_manager.subscribe(self._update_color)
    
    def add_indicator(self, name, default_text="", default_color="#00ffff"):
        """Add a status indicator."""
        indicator = tk.Label(
            self,
            text=default_text,
            font=("Orbitron", 10),
            fg=default_color,
            bg=self.bg_color
        )
        indicator.pack(side=tk.RIGHT, padx=10, pady=5)
        self.indicators[name.lower()] = indicator
        return indicator
    
    def update_status(self, text, color="#00ffff"):
        """Update the main status text."""
        self.status_label.config(text=text.upper(), fg=color)
        
    def update_indicator(self, name, text, color="#00ffff"):
        """Update a specific indicator."""
        name = name.lower()
        if name in self.indicators:
            self.indicators[name].config(text=text.upper(), fg=color)
            
            # Add flash effect
            current_bg = self.indicators[name].cget("bg")
            self.indicators[name].config(bg=color)
            self.after(100, lambda: self.indicators[name].config(bg=current_bg))
    
    def _update_color(self, hex_color):
        """Update RGB colors."""
        if not self.winfo_exists():
            return
        
        try:
            self._current_rgb = hex_color
            # Update border visuals if needed
        except Exception:
            # Silently handle any errors during animation
            pass
    
    def destroy(self):
        """Clean up resources before destroying the status bar."""
        rgb_manager = RGBColorManager.get_instance()
        rgb_manager.unsubscribe(self._update_color)
        super().destroy()

# Initialize the singleton RGB color manager
rgb_manager = RGBColorManager.get_instance()
if not rgb_manager.running:
    rgb_manager.start()
