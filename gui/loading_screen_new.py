#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Loading Screen for Kingdom AI

This module provides a loading screen for the Kingdom AI system
that displays initialization progress and status updates with animated elements.

Features:
- Graceful fallback to console when GUI isn't available
- Animated progress bar shows real-time initialization status with visual motion
- Particle animation provides visual feedback during long processing tasks
- Status messages display current initialization steps
- Smooth transition to main application after loading
"""

import os
import sys
import time
import math
import random
import secrets
import threading
import traceback
import logging
from typing import Optional, Union, Any, List, Dict, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Try to import tkinter, but fail gracefully if not available
try:
    import tkinter as tk
    from tkinter import ttk
    TKINTER_AVAILABLE = True
except ImportError:
    logger.warning("Tkinter not available. Falling back to console mode.")
    TKINTER_AVAILABLE = False

class AnimatedParticle:
    """A single animated particle for the loading screen animation."""
    
    def __init__(self, canvas, width, height):
        """Initialize a new particle.
        
        Args:
            canvas: The canvas to draw on
            width: The width of the canvas
            height: The height of the canvas
        """
        self.canvas = canvas
        self.width = width
        self.height = height
        
        # Random starting position
        self.x = secrets.randbelow(int(width) - int(0) + 1) + int(0)
        self.y = secrets.randbelow(int(height) - int(0) + 1) + int(0)
        
        # Random velocity
        self.vx = random.uniform(-1, 1)
        self.vy = random.uniform(-1, 1)
        
        # Random size
        self.size = secrets.randbelow(int(6) - int(2) + 1) + int(2)
        
        # Random color - use Kingdom AI color palette
        colors = ["#3498db", "#2980b9", "#1abc9c", "#16a085", "#2ecc71"]
        self.color = secrets.choice(colors)
        
        # Create the particle
        self.id = self.canvas.create_oval(
            self.x, self.y, 
            self.x + self.size, self.y + self.size,
            fill=self.color, outline="")
        
        # Random lifespan
        self.lifespan = secrets.randbelow(int(150) - int(50) + 1) + int(50)
        self.age = 0
    
    def update(self, progress):
        """Update the particle position and appearance.
        
        Args:
            progress: Current loading progress (0-1)
        
        Returns:
            bool: True if particle is still alive, False if expired
        """
        self.age += 1
        if self.age > self.lifespan:
            self.canvas.delete(self.id)
            return False
        
        # Calculate alpha (opacity) based on age
        alpha = 1.0
        if self.age < 10:
            alpha = self.age / 10
        elif self.age > self.lifespan - 10:
            alpha = (self.lifespan - self.age) / 10
        
        # Update velocity based on progress
        # Higher progress = more directed movement
        if progress > 0.5:
            # Move more horizontally as progress increases
            target_x = self.width * 0.8
            dx = target_x - self.x
            self.vx = self.vx * 0.9 + dx * 0.01 * progress
        
        # Update position
        self.x += self.vx
        self.y += self.vy
        
        # Bounce off edges
        if self.x < 0 or self.x > self.width:
            self.vx = -self.vx
        if self.y < 0 or self.y > self.height:
            self.vy = -self.vy
        
        # Move the particle
        self.canvas.moveto(self.id, self.x, self.y)
        
        # Adjust opacity if supported
        try:
            self.canvas.itemconfig(self.id, fill=self.color, stipple='gray25' if alpha < 0.9 else '')
        except:
            pass
            
        return True

class LoadingScreen:
    """Tkinter-based loading screen with animated progress indicators.
    
    The loading screen is a top-level window with an animated progress bar and
    particle effects to provide visual feedback during initialization.
    """
    
    def __init__(self, parent=None, title="Kingdom AI", width=600, height=400):
        """Initialize the loading screen.
        
        Args:
            parent: Parent window
            title: Window title
            width: Window width
            height: Window height
        """
        self.parent = parent
        self.title = title
        self.width = width
        self.height = height
        self.is_shown = False
        
        # Progress and status variables
        self.progress_value = 0.0
        self.status_text = "Initializing..."
        
        # Animation settings
        self.animation_active = False
        self.particles = []
        self.max_particles = 30
        self.animation_speed = 30  # ms between frames
        self.animation_timer = None
        self.last_update_time = 0
        self.last_progress = 0.0
        
        # Create the root window if not provided
        if parent is None:
            self.root = tk.Tk()
            self.root.withdraw()  # Hide initially
        else:
            self.root = tk.Toplevel(parent)
            self.root.withdraw()  # Hide initially
            
        # Configure the window
        self.root.title(title)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)  # Handle close button
        
        # Position window in center of screen
        self._center_on_screen()
        
        # Set up UI elements
        self._setup_ui()
    
    def _on_close(self):
        """Handle window close button click."""
        # Do nothing - prevent user from closing the loading screen
        pass
    
    def _setup_ui(self):
        """Set up the UI elements of the loading screen."""
        # Create a base frame
        self.main_frame = tk.Frame(self.root, padx=20, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Logo or title
        title_frame = tk.Frame(self.main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = tk.Label(
            title_frame, 
            text=self.title, 
            font=("Helvetica", 24, "bold")
        )
        title_label.pack()
        
        # Status text
        status_frame = tk.Frame(self.main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = tk.Label(
            status_frame, 
            text=self.status_text,
            font=("Helvetica", 10)
        )
        self.status_label.pack(anchor=tk.W)
        
        # Progress bar
        progress_frame = tk.Frame(self.main_frame)
        progress_frame.pack(fill=tk.X)
        
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode="determinate",
            length=self.width - 40  # Adjust for padding
        )
        self.progress_bar.pack(fill=tk.X)
        
        # Animation canvas
        animation_frame = tk.Frame(self.main_frame)
        animation_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.animation_canvas = tk.Canvas(
            animation_frame, 
            width=self.width - 40,
            height=80,
            bg="#f5f5f5",
            highlightthickness=0
        )
        self.animation_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Additional status details
        details_frame = tk.Frame(self.main_frame)
        details_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.details_label = tk.Label(
            details_frame, 
            text="",
            font=("Helvetica", 8)
        )
        self.details_label.pack(anchor=tk.W)
    
    def _center_on_screen(self):
        """Center the window on the screen."""
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate position
        x = (screen_width - self.width) // 2
        y = (screen_height - self.height) // 2
        
        # Set geometry
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
    
    def _animate(self):
        """Update the animation elements."""
        if not self.animation_active:
            return
        
        # Get current time for smooth animation
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time
        
        # Update progress bar
        self.progress_bar["value"] = self.progress_value * 100
        
        # Add new particles occasionally, scaled by progress
        if len(self.particles) < self.max_particles and secrets.random() < 0.3:
            particle = AnimatedParticle(
                self.animation_canvas,
                self.animation_canvas.winfo_width() or self.width - 40,
                self.animation_canvas.winfo_height() or 80
            )
            self.particles.append(particle)
        
        # Update existing particles
        self.particles = [p for p in self.particles if p.update(self.progress_value)]
        
        # Schedule next animation frame
        self.animation_timer = self.root.after(self.animation_speed, self._animate)
    
    def show(self):
        """Show the loading screen."""
        if self.is_shown:
            return
        
        try:
            # Configure window properties
            self.root.deiconify()  # Show window
            self.root.attributes("-topmost", True)  # Keep on top
            self.root.update()
            
            # Customize window appearance if supported
            try:
                self.root.attributes("-alpha", 0.95)  # Slight transparency
            except:
                pass
                
            try:
                self.root.attributes("-toolwindow", True)  # Remove window decorations
            except:
                pass
            
            # Start animation
            self.animation_active = True
            self.last_update_time = time.time()
            self._animate()
            
            self.is_shown = True
            self.root.update_idletasks()
        except Exception as e:
            logger.error(f"Error showing loading screen: {e}")
            logger.error(traceback.format_exc())
    
    def update_progress(self, progress, status=None):
        """Update the progress bar and status text.
        
        Args:
            progress (float): Progress value (0-1)
            status (str, optional): Status text to display
        """
        try:
            # Update progress with smooth animation
            self.progress_value = max(0.0, min(1.0, progress))  # Clamp between 0-1
            
            # Update status if provided
            if status is not None:
                self.status_text = status
                self.status_label.config(text=status)
            
            # Update progress percentage
            progress_pct = int(self.progress_value * 100)
            self.details_label.config(text=f"{progress_pct}% complete")
            
            # Update UI
            if self.is_shown:
                self.root.update()
        except Exception as e:
            logger.error(f"Error updating progress: {e}")
    
    def update_status(self, status):
        """Update just the status text.
        
        Args:
            status (str): Status text to display
        """
        self.status_text = status
        self.status_label.config(text=status)
        if self.is_shown:
            self.root.update()
    
    def close(self):
        """Close the loading screen."""
        if not self.is_shown:
            return
            
        try:
            # Stop animation
            self.animation_active = False
            if self.animation_timer:
                self.root.after_cancel(self.animation_timer)
                self.animation_timer = None
            
            # Destroy window
            self.root.destroy()
            self.is_shown = False
        except Exception as e:
            logger.error(f"Error closing loading screen: {e}")
    
    def update(self):
        """Update the UI.
        
        This is required for Tkinter compatibility.
        """
        if self.is_shown:
            try:
                self.root.update()
            except:
                pass
    
    def update_idletasks(self):
        """Update idle tasks.
        
        This is required for Tkinter compatibility.
        """
        if self.is_shown:
            try:
                self.root.update_idletasks()
            except:
                pass
    
    def destroy(self):
        """Alias for close()."""
        self.close()

class ConsoleLoadingScreen:
    """Text-based loading screen for console environments.
    
    This provides a loading screen interface for environments where
    a graphical UI is not available or desired.
    """
    
    def __init__(self):
        """Initialize the console loading screen."""
        self.progress = 0.0
        self.status = "Initializing..."
        self.is_shown = False
        self.last_update = 0
    
    def show(self):
        """Show the loading screen."""
        self.is_shown = True
        self._update_display()
    
    def update_progress(self, progress, status=None):
        """Update the progress and status.
        
        Args:
            progress (float): Progress value (0-1)
            status (str, optional): Status text to display
        """
        self.progress = max(0.0, min(1.0, progress))  # Clamp between 0-1
        if status is not None:
            self.status = status
        
        # Don't update too frequently to avoid console spam
        now = time.time()
        if now - self.last_update > 0.5:
            self._update_display()
            self.last_update = now
    
    def update_status(self, status):
        """Update status message.
        
        Args:
            status (str): Status text to display
        """
        self.status = status
        self._update_display()
    
    def _update_display(self):
        """Update the console display."""
        if not self.is_shown:
            return
            
        # Create progress bar
        bar_length = 30
        filled_length = int(bar_length * self.progress)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # Format and print
        percent = int(100 * self.progress)
        output = f"\r{self.status} [{bar}] {percent}%"
        
        # Output to console
        sys.stdout.write(output)
        sys.stdout.flush()
    
    def close(self):
        """Close the loading screen."""
        if self.is_shown:
            # Print new line after progress bar
            print()
            self.is_shown = False
    
    def destroy(self):
        """Alias for close()."""
        self.close()
    
    # SOTA 2026: Tkinter compatibility methods with Qt event processing
    def update(self):
        """Process pending Qt events - Tkinter compatibility method."""
        if self.app:
            self.app.processEvents()
        
    def update_idletasks(self):
        """Process pending Qt idle tasks - Tkinter compatibility method."""
        if self.app:
            from PyQt6.QtCore import QCoreApplication
            QCoreApplication.processEvents()

# Global reference to the active loading screen
_active_loading_screen = None

def show_loading_screen(title="Kingdom AI", width=600, height=400):
    """Show a loading screen with progress bar and status message.
    
    This function attempts to create a graphical loading screen first.
    If that fails, it falls back to a console-based loading screen.
    
    Args:
        title (str): Window title
        width (int): Window width
        height (int): Window height
        
    Returns:
        bool: True if loading screen shown successfully, False otherwise
    """
    global _active_loading_screen
    
    # If already shown, do nothing
    if _active_loading_screen is not None and _active_loading_screen.is_shown:
        return True
    
    # Close any existing loading screen
    if _active_loading_screen is not None:
        try:
            _active_loading_screen.close()
        except:
            pass
    
    # Try to create a graphical loading screen
    if TKINTER_AVAILABLE:
        try:
            logger.info("Creating graphical loading screen")
            _active_loading_screen = LoadingScreen(
                title=title,
                width=width,
                height=height
            )
            _active_loading_screen.show()
            return True
        except Exception as e:
            logger.error(f"Failed to create graphical loading screen: {e}")
            logger.error(traceback.format_exc())
    else:
        logger.warning("Tkinter not available, using console loading screen")
    
    # Fall back to console loading screen
    try:
        _active_loading_screen = ConsoleLoadingScreen()
        _active_loading_screen.show()
        return True
    except Exception as e:
        logger.error(f"Failed to create console loading screen: {e}")
        logger.error(traceback.format_exc())
    
    return False

def update_loading_progress(progress, status=None):
    """Update the loading screen progress and status.
    
    Args:
        progress (float): Progress value between 0.0 and 1.0
        status (str, optional): Status message to display
        
    Returns:
        bool: True if update successful, False otherwise
    """
    global _active_loading_screen
    
    # Check if loading screen exists
    if _active_loading_screen is None or not _active_loading_screen.is_shown:
        return False
    
    try:
        # Update loading screen
        _active_loading_screen.update_progress(progress, status)
        return True
    except Exception as e:
        logger.error(f"Failed to update loading screen: {e}")
        logger.error(traceback.format_exc())
        return False

def update_loading_status(message):
    """Update just the loading screen status message.
    
    Args:
        message (str): Status message to display
        
    Returns:
        bool: True if update successful, False otherwise
    """
    global _active_loading_screen
    
    # Check if loading screen exists
    if _active_loading_screen is None or not _active_loading_screen.is_shown:
        return False
    
    try:
        # Update loading screen status
        _active_loading_screen.update_status(message)
        return True
    except Exception as e:
        logger.error(f"Failed to update loading screen status: {e}")
        logger.error(traceback.format_exc())
        return False

def close_loading_screen():
    """Close the loading screen with proper transition.
    
    This function ensures the progress bar reaches 100% and properly transitions to 
    the main GUI window. It guarantees a smooth transition with a brief pause.
    
    Returns:
        bool: True if loading screen closed successfully, False otherwise
    """
    global _active_loading_screen
    
    # Check if loading screen exists
    if _active_loading_screen is None or not _active_loading_screen.is_shown:
        logger.warning("No active loading screen to close")
        return False
    
    try:
        # Ensure progress is at 100%
        update_loading_progress(1.0, "Initialization complete")
        
        # Brief pause before closing
        update_loading_status("Launching Kingdom AI...")
        time.sleep(0.5)
        
        # Close the loading screen
        _active_loading_screen.close()
        _active_loading_screen = None
        
        logger.info("Loading screen closed successfully")
        return True
    except Exception as e:
        logger.error(f"Error closing loading screen: {e}")
        logger.error(traceback.format_exc())
        
        # Emergency fallback - force close
        force_close_loading_screen()
        return True

def force_close_loading_screen():
    """Force close the loading screen immediately.
    
    This is an emergency function to ensure the loading screen is closed,
    even if the normal closing process fails.
    """
    global _active_loading_screen
    
    if _active_loading_screen is not None:
        try:
            _active_loading_screen.close()
        except:
            pass
        _active_loading_screen = None
        logger.info("Loading screen force closed")
