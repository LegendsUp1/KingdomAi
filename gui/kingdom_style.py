#!/usr/bin/env python3
"""Kingdom AI - Futuristic UI Style System

This module provides a unified styling system for the Kingdom AI application
with animated RGB borders, glowing effects, and futuristic aesthetics.

Features:
- RGB animated borders for all frames and components
- Glowing button effects with animated colors
- Modern, dark-themed futuristic aesthetics
- Consistent styling across all components
- High-performance animations that don't impact system function
- Support for loading screen, main window, and all tabs

This style system preserves all existing functionality while providing
a state-of-the-art visual experience for the Kingdom AI interface.
"""
import tkinter as tk
from tkinter import ttk, font
import time
import math
import threading
import colorsys
import random
from typing import Dict, Any, Optional, List, Tuple, Union, Callable

class RGBBorderManager:
    """Manages RGB border effects for UI elements."""
    
    def __init__(self, master=None, border_width=2, update_interval_ms=30):
        """Initialize the RGB border manager.
        
        Args:
            master: The master widget to apply border effects to
            border_width: Width of the border in pixels
            update_interval_ms: Update interval in milliseconds
        """
        self.master = master
        self.border_width = border_width
        self.update_interval = update_interval_ms
        self.running = False
        self.frames = []
        self.current_hue = 0.0
        self.hue_increment = 0.01
        self.after_id = None
        
    def add_frame(self, frame):
        """Add a frame to be managed with RGB borders."""
        if frame not in self.frames:
            self.frames.append(frame)
            # Configure frame with initial border
            if hasattr(frame, 'configure'):
                try:
                    frame.configure(highlightbackground="#000000", highlightthickness=self.border_width)
                except Exception as e:
                    print(f"Error configuring frame: {e}")
        return self
    
    def start(self):
        """Start the RGB animation."""
        if not self.running:
            self.running = True
            self._update_borders()
        return self
    
    def stop(self):
        """Stop the RGB animation."""
        self.running = False
        if self.after_id and self.master:
            try:
                self.master.after_cancel(self.after_id)
                self.after_id = None
            except Exception:
                pass  # Master might be destroyed
        return self
    
    def _update_borders(self):
        """Update the border colors for all managed frames."""
        if not self.running or not self.master:
            return
            
        try:
            # Calculate new color
            self.current_hue = (self.current_hue + self.hue_increment) % 1.0
            r, g, b = colorsys.hsv_to_rgb(self.current_hue, 1.0, 1.0)
            color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            
            # Update all frames
            for frame in self.frames:
                if frame and hasattr(frame, 'configure'):
                    try:
                        frame.configure(highlightbackground=color)
                    except Exception:
                        # Frame might be destroyed
                        if frame in self.frames:
                            self.frames.remove(frame)
            
            # Schedule next update
            if self.master:
                self.after_id = self.master.after(self.update_interval, self._update_borders)
        except Exception as e:
            print(f"Error in RGB border update: {e}")
            self.stop()


class RGBAnimationManager:
    """Manages RGB animations for UI elements."""
    
    def __init__(self, master=None, update_interval_ms=30):
        """Initialize the RGB animation manager.
        
        Args:
            master: The master widget to apply animations to
            update_interval_ms: Update interval in milliseconds
        """
        self.master = master
        self.update_interval = update_interval_ms
        self.running = False
        self.elements = []
        self.current_hue = 0.0
        self.hue_increment = 0.01
        self.after_id = None
        
    def add_element(self, element):
        """Add an element to be animated."""
        if element not in self.elements:
            self.elements.append(element)
        return self
    
    def start(self):
        """Start the RGB animation."""
        if not self.running:
            self.running = True
            self._update_colors()
        return self
    
    def stop(self):
        """Stop the RGB animation."""
        self.running = False
        if self.after_id and self.master:
            try:
                self.master.after_cancel(self.after_id)
                self.after_id = None
            except Exception:
                pass  # Master might be destroyed
        return self
    
    def _update_colors(self):
        """Update the colors for all managed elements."""
        if not self.running or not self.master:
            return
            
        try:
            # Calculate new color
            self.current_hue = (self.current_hue + self.hue_increment) % 1.0
            r, g, b = colorsys.hsv_to_rgb(self.current_hue, 1.0, 1.0)
            color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            
            # Update all elements
            for element in self.elements:
                if element and hasattr(element, 'configure'):
                    try:
                        element.configure(foreground=color)
                    except Exception:
                        # Element might be destroyed
                        if element in self.elements:
                            self.elements.remove(element)
            
            # Schedule next update
            if self.master:
                self.after_id = self.master.after(self.update_interval, self._update_colors)
        except Exception as e:
            print(f"Error in RGB animation update: {e}")
            self.stop()


class RGBAnimator:
    """Manages RGB color animations for UI elements."""
    
    def __init__(self, update_interval_ms=30):  # Faster updates for smoother animation
        """Initialize the RGB animator.
        
        Args:
            update_interval_ms: Update interval in milliseconds
        """
        self.update_interval = update_interval_ms
        self.animations = {}
        self.running = False
        self.animation_thread = None
        self._color_cycle_position = 0
        self.subscribers = []
        self.cycle_speed = 0.01  # RGB cycle speed
        self.saturation = 1.0   # Full saturation
        self.value = 1.0        # Full brightness
        self.root = None
    
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
        """Subscribe a callback function to RGB color updates.
        
        Args:
            callback: Function to call with RGB color values
        """
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            
        # Start animation if this is the first subscriber
        if len(self.subscribers) == 1:
            self.start()
    
    def unsubscribe(self, callback):
        """Unsubscribe a callback function.
        
        Args:
            callback: Function to remove from subscribers
        """
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            
        # Stop animation if no subscribers left
        if len(self.subscribers) == 0:
            self.stop()
    
    def _animation_loop(self):
        """Main animation loop that updates RGB colors."""
        while self.running:
            # Update color cycle position
            self._color_cycle_position = (self._color_cycle_position + self.cycle_speed) % 1.0
            
            # Generate RGB color from HSV (hue, saturation, value)
            r, g, b = colorsys.hsv_to_rgb(self._color_cycle_position, self.saturation, self.value)
            
            # Convert to hex color string
            hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            
            # Notify all subscribers
            for callback in list(self.subscribers):  # Use a copy to avoid modification during iteration
                try:
                    if hasattr(self.root, 'after_idle'):
                        self.root.after_idle(lambda cb=callback, color=hex_color: cb(color))
                    else:
                        callback(hex_color)
                except Exception as e:
                    print(f"Error in RGB animation callback: {e}")
            
            # Sleep for update interval
            time.sleep(self.update_interval / 1000.0)

    def set_animation_speed(self, speed_multiplier):
        """Set animation speed.
        
        Args:
            speed_multiplier: Speed multiplier (1.0 = normal, 2.0 = double, 0.5 = half)
        """
        self.cycle_speed = 0.01 * speed_multiplier

# Singleton RGB animator instance
rgb_animator = RGBAnimator()

# Alias for backward compatibility - will be overridden with proper class instance later
# Just a placeholder until the proper manager is created

class KingdomStyles:
    """Kingdom AI style manager for futuristic UI elements."""
    
    # Enhanced cyberpunk color schemes
    COLORS = {
        "primary": "#00a0ff",    # Bright blue
        "secondary": "#ff00aa",  # Neon pink
        "success": "#00ff7f",    # Neon green
        "warning": "#ffaa00",    # Amber
        "danger": "#ff3a3a",     # Bright red
        "info": "#00ffff",       # Cyan
        "dark": "#1a1a2e",       # Dark blue-black
        "neon_purple": "#b300ff", # Neon purple
        "neon_orange": "#ff6600", # Neon orange
        "electric_blue": "#0066ff", # Electric blue
        "cyber_green": "#3af33a",  # Cyber green
        "deep_purple": "#1a002e",  # Deep purple background
        "frame_bg": "#171923",   # Dark background for frames
        "panel_bg": "#0d1117",   # Even darker background for panels
        "thoth": "#8000ff",      # Purple for ThothAI
        "trading": "#ffd700",    # Gold for Trading
        "mining": "#3366ff",     # Cobalt for Mining
        "wallet": "#00ff7f",     # Lime for Wallet
        "vr": "#9400d3",         # Violet for VR
        "code": "#008080",       # Teal for Code Generator
        "api": "#dc143c",        # Crimson for API
        "dashboard": "#00aaff",  # Sky for Dashboard
        "text": "#ffffff",       # White text color
        "normal": "#cccccc",     # Light gray for normal text
        "accent": "#00ffcc",     # Accent color for highlights
    }
    
    # Component-specific colors with enhanced glow effects
    COMPONENT_COLORS = {
        "trading": "#00ff7f",     # Trading: Green
        "mining": "#ffaa00",      # Mining: Amber
        "wallet": "#00a0ff",      # Wallet: Blue
        "dashboard": "#ff00aa",   # Dashboard: Pink
        "settings": "#00ffff",    # Settings: Cyan
        "vr": "#b300ff",          # VR: Purple
        "code": "#ffd700",        # Code: Gold
        "system": "#ff3a3a",      # System: Red
        "ai": "#9900ff",          # AI: Purple
        "neural": "#ff00ff",      # Neural: Magenta
        "quantum": "#00ffcc",     # Quantum: Teal
        "thoth": "#ffcc00",       # Thoth: Gold
        "default": "#00a0ff"      # Default: Blue
    }
    
    # Glow effects for different components
    GLOW_EFFECTS = {
        "trading": "0 0 10px #00ff7f, 0 0 20px #00ff7f60",  # Trading green glow
        "mining": "0 0 10px #ffaa00, 0 0 20px #ffaa0060",   # Mining amber glow
        "wallet": "0 0 10px #00a0ff, 0 0 20px #00a0ff60",   # Wallet blue glow
        "dashboard": "0 0 10px #ff00aa, 0 0 20px #ff00aa60", # Dashboard pink glow
        "settings": "0 0 10px #00ffff, 0 0 20px #00ffff60",  # Settings cyan glow
        "vr": "0 0 10px #b300ff, 0 0 20px #b300ff60",       # VR purple glow
        "code": "0 0 10px #ffd700, 0 0 20px #ffd70060",      # Code gold glow
        "system": "0 0 10px #ff3a3a, 0 0 20px #ff3a3a60",    # System red glow
        "default": "0 0 10px #00a0ff, 0 0 20px #00a0ff60"    # Default blue glow
    }
    
    # Border styles for components
    BORDER_STYLES = {
        "standard": "solid",       # Standard solid border
        "animated": "double",      # Double border for animated elements
        "dashed": "dashed",       # Dashed border
        "glowing": "groove"       # Groove border for glowing elements
    }
    
    # Define hex colors for specific components
    COMPONENT_FRAME_COLORS = {
        "thoth_frame": "#8000ff",        # Purple for ThothAI
        "trading_frame": "#ffd700",      # Gold for Trading
        "mining_frame": "#3366ff",       # Cobalt for Mining
        "wallet_frame": "#00ff7f",       # Lime for Wallet
        "vr_frame": "#9400d3",           # Violet for VR
        "code_generator_frame": "#008080", # Teal for Code Generator
        "api_keys_frame": "#dc143c",     # Crimson for API
        "dashboard_frame": "#00aaff",    # Sky for Dashboard
    }
    
    # Font sizes and styles
    FONT_SIZES = {
        "xs": 8,            # Extra small
        "small": 10,        # Small
        "medium": 12,       # Medium
        "large": 14,        # Large
        "xl": 16,           # Extra large
        "xxl": 20,          # Double extra large
        "title": 24,        # Title
        "header": 36        # Header
    }
    
    # Futuristic fonts - use system fallbacks
    FONTS = {
        "main": ("Orbitron", "Arial", "sans-serif"),
        "display": ("Michroma", "Orbitron", "Arial", "sans-serif"),
        "monospace": ("JetBrains Mono", "Consolas", "monospace"),
        "title": ("Orbitron", "Impact", "Arial Black", "sans-serif")
    }
    
    # Animation durations
    ANIMATIONS = {
        "fast": 200,        # Fast animations (ms)
        "normal": 400,      # Normal animations (ms)
        "slow": 1000,       # Slow animations (ms)
        "ultra_slow": 2000  # Ultra slow animations (ms)
    }
    
    # Border radius styles
    BORDER_RADIUS = {
        "none": 0,
        "small": 5,
        "medium": 10,
        "large": 15,
    }
    
    # Font styles
    FONT_STYLES = {
        "heading": ("Orbitron", 16, "bold"),
        "subheading": ("Orbitron", 14, "bold"),
        "body": ("Segoe UI", 11),
        "code": ("Consolas", 10),
        "small": ("Segoe UI", 9),
    }
    
    # Box shadow definitions for glowing effects
    SHADOWS = {
        "sky": "0 0 10px 5px rgba(0, 170, 255, 0.7)",
        "amber": "0 0 10px 5px rgba(255, 170, 0, 0.7)",
        "lime": "0 0 10px 5px rgba(0, 255, 127, 0.7)",
        "cobalt": "0 0 10px 5px rgba(51, 102, 255, 0.7)",
        "gold": "0 0 10px 5px rgba(255, 215, 0, 0.7)",
        "violet": "0 0 10px 5px rgba(148, 0, 211, 0.7)",
        "teal": "0 0 10px 5px rgba(0, 128, 128, 0.7)",
        "crimson": "0 0 10px 5px rgba(220, 20, 60, 0.7)",
    }

    @staticmethod
    def get_component_color(component_name):
        """Get the color for a specific component.
        
        Args:
            component_name: Name of the component
            
        Returns:
            Hex color string
        """
        # Normalize component name
        normalized_name = component_name.lower().replace(" ", "_")
        
        # Check for exact match in COMPONENT_COLORS
        if normalized_name in KingdomStyles.COMPONENT_COLORS:
            return KingdomStyles.COMPONENT_COLORS[normalized_name]
        
        # Check for partial match
        for key, value in KingdomStyles.COMPONENT_COLORS.items():
            if key in normalized_name or normalized_name in key:
                return value
        
        # Default to primary color if no match found
        return KingdomStyles.COLORS["primary"]
    
    @staticmethod
    def setup_theme(root):
        """Set up the Kingdom AI theme for the application.
        
        Args:
            root: The root Tkinter window
            
        Returns:
            ttk.Style object configured with Kingdom AI theme
        """
        # Configure global font
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=11)
        
        # Create custom styles
        style = ttk.Style()
        
        # Background for all elements
        style.configure(".", 
                        background=KingdomStyles.COLORS["dark"],
                        foreground="white",
                        fieldbackground=KingdomStyles.COLORS["dark"])
        
        # Notebook style
        style.configure("TNotebook", 
                        background=KingdomStyles.COLORS["dark"],
                        tabmargins=[2, 5, 2, 0])
        
        style.configure("TNotebook.Tab", 
                        background=KingdomStyles.COLORS["panel_bg"],
                        foreground="white",
                        padding=[10, 5],
                        font=KingdomStyles.FONT_STYLES["body"])
        
        style.map("TNotebook.Tab",
                  background=[("selected", KingdomStyles.COLORS["primary"])],
                  foreground=[("selected", "white")],
                  expand=[("selected", [1, 1, 1, 0])])
        
        # Frame style
        style.configure("TFrame", 
                        background=KingdomStyles.COLORS["frame_bg"])
        
        # Button styles
        style.configure("TButton", 
                        background=KingdomStyles.COLORS["primary"],
                        foreground="white",
                        padding=[10, 5],
                        font=KingdomStyles.FONT_STYLES["body"])
        
        style.map("TButton",
                  background=[("active", KingdomStyles.COLORS["secondary"])],
                  relief=[("pressed", "sunken")])
        
        # Success button
        style.configure("Success.TButton", 
                        background=KingdomStyles.COLORS["success"],
                        foreground="white")
        
        style.map("Success.TButton",
                  background=[("active", "#00cc66")])
        
        # Danger button
        style.configure("Danger.TButton", 
                        background=KingdomStyles.COLORS["danger"],
                        foreground="white")
        
        style.map("Danger.TButton",
                  background=[("active", "#ff0000")])
        
        # Info button
        style.configure("Info.TButton", 
                        background=KingdomStyles.COLORS["info"],
                        foreground="black")
        
        style.map("Info.TButton",
                  background=[("active", "#00cccc")])
        
        # Label style
        style.configure("TLabel", 
                        background=KingdomStyles.COLORS["frame_bg"],
                        foreground="white",
                        font=KingdomStyles.FONT_STYLES["body"])
        
        # Entry style
        style.configure("TEntry", 
                        fieldbackground=KingdomStyles.COLORS["panel_bg"],
                        foreground="white",
                        padding=[5, 3])
        
        # Combobox style
        style.configure("TCombobox", 
                        fieldbackground=KingdomStyles.COLORS["panel_bg"],
                        background=KingdomStyles.COLORS["primary"],
                        foreground="white",
                        selectbackground=KingdomStyles.COLORS["primary"],
                        selectforeground="white",
                        padding=[5, 3])
        
        # Heading style
        style.configure("Heading.TLabel", 
                        font=KingdomStyles.FONT_STYLES["heading"],
                        foreground=KingdomStyles.COLORS["primary"])
        
        # Subheading style
        style.configure("Subheading.TLabel", 
                        font=KingdomStyles.FONT_STYLES["subheading"],
                        foreground=KingdomStyles.COLORS["secondary"])

        # Set root configuration
        root.configure(background=KingdomStyles.COLORS["dark"])
        
        return style

class RGBAnimationManager:
    """Centralized manager for all RGB animations across the application."""
    
    def __init__(self):
        """Initialize the RGB animation manager."""
        self.animator = rgb_animator
        self.animation_enabled = True
        self.animation_speed = 1.0  # Normal speed
        self.animation_elements = set()  # Track all animated elements
        
    def register_element(self, element):
        """Register an element for RGB animation.
        
        Args:
            element: Element to register
        """
        self.animation_elements.add(element)
        
    def unregister_element(self, element):
        """Unregister an element from RGB animation.
        
        Args:
            element: Element to unregister
        """
        if element in self.animation_elements:
            self.animation_elements.remove(element)
    
    def set_animation_speed(self, speed):
        """Set the global animation speed.
        
        Args:
            speed: Animation speed multiplier (0.5 = half speed, 2.0 = double speed)
        """
        self.animation_speed = max(0.1, min(5.0, speed))  # Clamp between 0.1 and 5.0
        self.animator.update_interval = int(50 / self.animation_speed)
    
    def toggle_animations(self, enabled=None):
        """Toggle all RGB animations on/off.
        
        Args:
            enabled: If provided, explicitly set animation state
        """
        if enabled is not None:
            self.animation_enabled = enabled
        else:
            self.animation_enabled = not self.animation_enabled
            
        if self.animation_enabled:
            self.animator.start()
        else:
            self.animator.stop()
            
        return self.animation_enabled

# Create singleton instance
rgb_animation_manager = RGBAnimationManager()

class RGBBorderFrame(tk.Frame):
    """Frame with animated RGB border and futuristic styling."""
    
    def __init__(self, parent, **kwargs):
        """Initialize RGB border frame.
        
        Args:
            parent: Parent widget
            **kwargs: Additional keyword arguments
        """
        # Extract and set default parameters
        self.border_width = kwargs.pop('border_width', 3)
        self.corner_radius = kwargs.pop('corner_radius', 10)
        self.inner_padding = kwargs.pop('inner_padding', 5)
        self.animate_shadow = kwargs.pop('animate_shadow', True)
        self.glow_intensity = kwargs.pop('glow_intensity', 1.0)
        self.current_rgb = KingdomStyles.COLORS["primary"]
        
        # Ensure background color is set
        if 'background' not in kwargs and 'bg' not in kwargs:
            kwargs['bg'] = KingdomStyles.COLORS["frame_bg"]
            
        # Initialize frame
        super().__init__(parent, **kwargs)
        
        # Create canvas for border drawing
        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            bg=kwargs.get('bg', KingdomStyles.COLORS["frame_bg"])
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Create inner frame for content
        self.inner_frame = tk.Frame(
            self.canvas,
            bg=kwargs.get('bg', KingdomStyles.COLORS["frame_bg"]),
            highlightthickness=0
        )
        
        # Initial border drawing
        self._draw_border()
        
        # Bind resize event
        self.bind("<Configure>", self._on_resize)
        
        # Subscribe to RGB animator
        rgb_animator.subscribe(self._update_border_color)
    
    def _draw_border(self):
        """Draw the border on the canvas."""
        width = self.winfo_width()
        height = self.winfo_height()
        
        if width <= 1 or height <= 1:
            # Not ready to draw yet
            return
        
        # Clear canvas
        self.canvas.delete("all")
        
        # Draw rounded rectangle border
        self.border_id = self.canvas.create_rectangle(
            self.border_width/2,
            self.border_width/2,
            width - self.border_width/2,
            height - self.border_width/2,
            outline=self.current_rgb,
            width=self.border_width,
            fill=KingdomStyles.COLORS["frame_bg"]
        )
        
        # Add inner frame as canvas window
        self.inner_window = self.canvas.create_window(
            self.border_width + self.inner_padding,
            self.border_width + self.inner_padding,
            window=self.inner_frame,
            anchor=tk.NW,
            width=width - 2*(self.border_width + self.inner_padding),
            height=height - 2*(self.border_width + self.inner_padding)
        )
    
    def _update_border_color(self, hex_color):
        """Update the border color.
        
        Args:
            hex_color: New RGB color in hex format
        """
        if hasattr(self, 'border_id') and self.canvas.winfo_exists():
            try:
                self.current_rgb = hex_color
                self.canvas.itemconfig(self.border_id, outline=hex_color)
                
                # Apply custom glow effect
                self.apply_glow_effect(hex_color)
            except Exception as e:
                # Silently handle any errors during animation
                pass
                
    def apply_glow_effect(self, hex_color):
        """Apply a glow effect to the border using the specified color.
        
        Args:
            hex_color: Hex color for the glow effect
        """
        try:
            # This is a simple implementation - platforms with better graphics
            # capabilities could override this with more sophisticated effects
            intensity = min(1.0, max(0.1, self.glow_intensity))
            # No actual effect in the base implementation
            pass
        except Exception:
            # Silently ignore errors in glow effect
            pass
    
    def _on_resize(self, event):
        """Handle resize event.
        
        Args:
            event: Resize event
        """
        self._draw_border()
    
    def add_widget(self, widget, **pack_args):
        """Add a widget to the inner frame.
        
        Args:
            widget: Widget to add
            **pack_args: Pack arguments
        """
        if 'fill' not in pack_args:
            pack_args['fill'] = tk.BOTH
        if 'expand' not in pack_args:
            pack_args['expand'] = True
        if 'padx' not in pack_args:
            pack_args['padx'] = 5
        if 'pady' not in pack_args:
            pack_args['pady'] = 5
            
        widget.pack(in_=self.inner_frame, **pack_args)
    
    def destroy(self):
        """Clean up resources before destroying the frame."""
        # Unsubscribe from animator
        rgb_animator.unsubscribe(self._update_border_color)
        super().destroy()

class GlowButton(tk.Button):
    """Button with glowing RGB effect."""
    
    def __init__(self, parent, **kwargs):
        """Initialize glowing button.
        
        Args:
            parent: Parent widget
            **kwargs: Additional keyword arguments for Button
        """
        # Extract custom arguments
        glow_color = kwargs.pop('glow_color', KingdomStyles.COLORS["primary"])
        glow_intensity = kwargs.pop('glow_intensity', 2)
        
        # Configure button appearance
        if 'background' not in kwargs and 'bg' not in kwargs:
            kwargs['bg'] = KingdomStyles.COLORS["dark"]
        if 'foreground' not in kwargs and 'fg' not in kwargs:
            kwargs['fg'] = 'white'
        if 'activebackground' not in kwargs:
            kwargs['activebackground'] = KingdomStyles.COLORS["primary"]
        if 'activeforeground' not in kwargs:
            kwargs['activeforeground'] = 'white'
        if 'font' not in kwargs:
            kwargs['font'] = KingdomStyles.FONT_STYLES["body"]
        if 'borderwidth' not in kwargs:
            kwargs['borderwidth'] = 0
        if 'relief' not in kwargs:
            kwargs['relief'] = tk.FLAT
        if 'padx' not in kwargs:
            kwargs['padx'] = 15
        if 'pady' not in kwargs:
            kwargs['pady'] = 8
            
        # Initialize button
        super().__init__(parent, **kwargs)
        
        # Store properties
        self.glow_intensity = glow_intensity
        self.current_glow_color = glow_color
        self.original_bg = kwargs.get('bg', KingdomStyles.COLORS["dark"])
        self.original_fg = kwargs.get('fg', 'white')
        
        # Bind events for hover effects
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
        # Subscribe to RGB animator
        rgb_animator.subscribe(self._update_glow_color)
    
    def _on_enter(self, event):
        """Handle mouse enter event.
        
        Args:
            event: Mouse event
        """
        self.config(bg=self.current_glow_color)
    
    def _on_leave(self, event):
        """Handle mouse leave event.
        
        Args:
            event: Mouse event
        """
        self.config(bg=self.original_bg)
    
    def _update_glow_color(self, hex_color):
        """Update the glow color.
        
        Args:
            hex_color: New RGB color in hex format
        """
        if self.winfo_exists():
            self.current_glow_color = hex_color
            
            # If mouse is over button, update color
            if self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery()) == self:
                self.config(bg=hex_color)
    
    def destroy(self):
        """Clean up resources before destroying the button."""
        # Unsubscribe from animator
        rgb_animator.unsubscribe(self._update_glow_color)
        super().destroy()

class FrameHeader(tk.Frame):
    """Stylized header for frames with title and optional controls."""
    
    def __init__(self, parent, title, **kwargs):
        """Initialize frame header.
        
        Args:
            parent: Parent widget
            title: Header title
            **kwargs: Additional keyword arguments for Frame
        """
        # Configure frame appearance
        if 'background' not in kwargs and 'bg' not in kwargs:
            kwargs['bg'] = KingdomStyles.COLORS["panel_bg"]
        if 'height' not in kwargs:
            kwargs['height'] = 40
            
        # Initialize frame
        super().__init__(parent, **kwargs)
        
        # Store title
        self.title = title
        
        # Create title label
        self.title_label = tk.Label(
            self,
            text=title.upper(),
            font=KingdomStyles.FONTS["heading"],
            bg=kwargs.get('bg', KingdomStyles.COLORS["panel_bg"]),
            fg=KingdomStyles.COLORS["primary"]
        )
        self.title_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Create controls frame
        self.controls_frame = tk.Frame(
            self,
            bg=kwargs.get('bg', KingdomStyles.COLORS["panel_bg"])
        )
        self.controls_frame.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Create separator
        self.separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        self.separator.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Subscribe to RGB animator
        rgb_animator.subscribe(self._update_title_color)
    
    def add_control(self, widget):
        """Add a control to the header.
        
        Args:
            widget: Widget to add as control
        """
        widget.pack(in_=self.controls_frame, side=tk.RIGHT, padx=2)
    
    def _update_title_color(self, hex_color):
        """Update the title color.
        
        Args:
            hex_color: New RGB color in hex format
        """
        if hasattr(self, 'title_label') and self.title_label.winfo_exists():
            self.title_label.config(fg=hex_color)
    
    def destroy(self):
        """Clean up resources before destroying the header."""
        # Unsubscribe from animator
        rgb_animator.unsubscribe(self._update_title_color)
        if hasattr(self, 'separator') and self.separator.winfo_exists():
            self.separator.destroy()
        super().destroy()

# Additional convenience functions

def create_themed_frame(parent, title=None, **kwargs):
    """Create a themed frame with RGB border and optional header.
    
    Args:
        parent: Parent widget
        title: Optional title for frame header
        **kwargs: Additional keyword arguments for RGBBorderFrame
        
    Returns:
        Tuple of (RGBBorderFrame, inner_frame)
    """
    frame = RGBBorderFrame(parent, **kwargs)
    
    if title:
        header = FrameHeader(frame.inner_frame, title)
        header.pack(fill=tk.X, expand=False, pady=(0, 5))
        
        # Create content frame
        content_frame = tk.Frame(
            frame.inner_frame,
            bg=kwargs.get('bg', KingdomStyles.COLORS["frame_bg"])
        )
        content_frame.pack(fill=tk.BOTH, expand=True)
        return frame, content_frame
    else:
        return frame, frame.inner_frame

def create_accent_label(parent, text, accent_color=None, **kwargs):
    """Create a label with accent color.
    
    Args:
        parent: Parent widget
        text: Label text
        accent_color: Optional accent color
        **kwargs: Additional keyword arguments for Label
        
    Returns:
        Label widget
    """
    if accent_color is None:
        accent_color = KingdomStyles.COLORS["primary"]
        
    if 'background' not in kwargs and 'bg' not in kwargs:
        kwargs['bg'] = KingdomStyles.COLORS["frame_bg"]
    if 'foreground' not in kwargs and 'fg' not in kwargs:
        kwargs['fg'] = accent_color
    if 'font' not in kwargs:
        kwargs['font'] = KingdomStyles.FONTS["body"]
        
    return tk.Label(parent, text=text, **kwargs)

class RGBLoadingScreen(tk.Frame):
    """Enhanced loading screen with RGB animated borders and modern aesthetics."""
    
    def __init__(self, parent, **kwargs):
        """Initialize the RGB loading screen.
        
        Args:
            parent: Parent widget
            **kwargs: Additional keyword arguments
        """
        # Extract specific arguments
        title = kwargs.pop('title', "Kingdom AI")
        width = kwargs.pop('width', 600)
        height = kwargs.pop('height', 400)
        
        # Set default background if not provided
        if 'bg' not in kwargs:
            kwargs['bg'] = KingdomStyles.COLORS["dark"]
            
        # Initialize frame
        super().__init__(parent, **kwargs)
        
        # Store properties
        self.title = title
        self.width = width
        self.height = height
        self.current_rgb = KingdomStyles.COLORS["primary"]
        self.progress_value = 0
        self.status_text = ""
        
        # Create UI elements
        self._create_ui()
        
        # Subscribe to RGB animator
        rgb_animator.subscribe(self._update_border_color)
        
    def _create_ui(self):
        """Create the UI elements for the loading screen."""
        # Create canvas for drawing
        self.canvas = tk.Canvas(
            self,
            width=self.width,
            height=self.height,
            bg=KingdomStyles.COLORS["dark"],
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Draw border
        self.border_id = self.canvas.create_rectangle(
            5, 5, self.width-5, self.height-5,
            outline=self.current_rgb,
            width=3
        )
        
        # Create title
        self.title_id = self.canvas.create_text(
            self.width//2, 50,
            text=self.title.upper(),
            font=("Orbitron", 24, "bold"),
            fill=self.current_rgb
        )
        
        # Create progress bar outline
        self.progress_outline_id = self.canvas.create_rectangle(
            50, self.height-100,
            self.width-50, self.height-70,
            outline=self.current_rgb,
            width=2
        )
        
        # Create progress bar fill
        self.progress_fill_id = self.canvas.create_rectangle(
            52, self.height-98,
            52, self.height-72,
            fill=self.current_rgb,
            outline=""
        )
        
        # Create status text
        self.status_id = self.canvas.create_text(
            self.width//2, self.height-40,
            text="Initializing...",
            font=("Orbitron", 12),
            fill="white"
        )
        
    def update_progress(self, progress_value, status_text=None):
        """Update the progress bar and status text.
        
        Args:
            progress_value: Progress value (0-100)
            status_text: Optional status text
        """
        self.progress_value = progress_value
        
        if status_text:
            self.status_text = status_text
            self.canvas.itemconfig(self.status_id, text=status_text)
        
        # Calculate progress width
        progress_width = int((self.width-104) * (progress_value/100))
        self.canvas.coords(
            self.progress_fill_id,
            52, self.height-98,
            52 + progress_width, self.height-72
        )
        
    def _update_border_color(self, hex_color):
        """Update the border color.
        
        Args:
            hex_color: New RGB color in hex format
        """
        try:
            if self.canvas.winfo_exists():
                self.current_rgb = hex_color
                self.canvas.itemconfig(self.border_id, outline=hex_color)
                self.canvas.itemconfig(self.title_id, fill=hex_color)
                self.canvas.itemconfig(self.progress_outline_id, outline=hex_color)
                self.canvas.itemconfig(self.progress_fill_id, fill=hex_color)
        except Exception:
            # Silently handle any errors during animation
            pass
    
    def destroy(self):
        """Clean up resources before destroying the frame."""
        # Unsubscribe from animator
        rgb_animator.unsubscribe(self._update_border_color)
        super().destroy()

class TabWithRGBBorder(ttk.Frame):
    """Tab frame with RGB animated border for use in TabManager."""
    
    def __init__(self, parent, tab_id, tab_title, **kwargs):
        """Initialize tab with RGB border.
        
        Args:
            parent: Parent notebook
            tab_id: Unique tab identifier
            tab_title: Display title for the tab
            **kwargs: Additional keyword arguments
        """
        super().__init__(parent, **kwargs)
        
        self.tab_id = tab_id
        self.tab_title = tab_title
        self.current_rgb = KingdomStyles.get_component_color(tab_id)
        
        # Create RGB border frame as container
        self.border_frame = RGBBorderFrame(
            self,
            border_width=3,
            corner_radius=10,
            bg=KingdomStyles.COLORS["frame_bg"]
        )
        self.border_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Content frame is accessed via border_frame.inner_frame
        self.content_frame = self.border_frame.inner_frame
        
    def get_content_frame(self):
        """Get the inner content frame for adding widgets.
        
        Returns:
            Inner frame for content
        """
        return self.content_frame
    
    def set_color(self, color_hex):
        """Set the border color manually.
        
        Args:
            color_hex: Hex color string
        """
        if hasattr(self.border_frame, '_update_border_color'):
            self.border_frame._update_border_color(color_hex)

def initialize_gui_styles(root):
    """Initialize all GUI styles for the application.
    
    Args:
        root: Root Tkinter window
        
    Returns:
        ttk.Style object
    """
    # Start RGB animator if not already running
    if not rgb_animator.running:
        rgb_animator.start()
    
    # Set up theme
    style = KingdomStyles.setup_theme(root)
    
    # Register with animation manager
    rgb_animation_manager.animator = rgb_animator
    
    return style

# ------------------------------------------------------------
# Provide simple theme aliases expected by other modules
# ------------------------------------------------------------

# Dark / light theme hex codes (simple aliases)
DARK_THEME: str = KingdomStyles.COLORS["dark"]
LIGHT_THEME: str = KingdomStyles.COLORS["frame_bg"]

# Explicit re-export list so `from gui.kingdom_style import *` behaves predictably
__all__ = [
    "KingdomStyles",
    "initialize_gui_styles",
    "DARK_THEME",
    "LIGHT_THEME",
]
