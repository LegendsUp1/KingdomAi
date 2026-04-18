#!/usr/bin/env python3
"""
Kingdom AI - Futuristic Theme System

This module extends the enhanced components with additional styling options
to ensure a consistent futuristic appearance across all frames, tabs, and
UI elements in the Kingdom AI system.
"""

import tkinter as tk
from tkinter import ttk, font

from .enhanced_components import EnhancedRGBFrame, EnhancedGlowButton, EnhancedStatusBar, RGBColorManager
from .kingdom_style import KingdomStyles

class FuturisticTheme:
    """Provides consistent futuristic styling for all Kingdom AI components."""
    
    @staticmethod
    def setup_notebook_style(style):
        """Configure notebook (tab) styling for a futuristic appearance.
        
        Args:
            style: ttk.Style instance
        """
        # Create custom notebook style
        style.configure(
            "Enhanced.TNotebook",
            background=KingdomStyles.COLORS["dark"],
            borderwidth=0,
            tabmargins=[5, 5, 5, 0],
        )
        
        # Configure tab appearance
        style.configure(
            "Enhanced.TNotebook.Tab",
            background=KingdomStyles.COLORS["frame_bg"],
            foreground=KingdomStyles.COLORS["text_secondary"],
            padding=[15, 5],
            borderwidth=0,
            font=("Orbitron", 10)
        )
        
        # Configure selected tab appearance
        style.map(
            "Enhanced.TNotebook.Tab",
            background=[("selected", KingdomStyles.COLORS["panel_bg"])],
            foreground=[("selected", KingdomStyles.COLORS["primary"])],
            expand=[("selected", [1, 1, 1, 0])]
        )
    
    @staticmethod
    def setup_button_style(style):
        """Configure button styling for a futuristic appearance.
        
        Args:
            style: ttk.Style instance
        """
        # Create custom button style
        style.configure(
            "Future.TButton",
            background=KingdomStyles.COLORS["button_bg"],
            foreground=KingdomStyles.COLORS["primary"],
            borderwidth=0,
            focusthickness=0,
            focuscolor="",
            lightcolor=KingdomStyles.COLORS["primary"],
            darkcolor=KingdomStyles.COLORS["primary_dark"],
            padding=[15, 8],
            font=("Orbitron", 9)
        )
        
        # Configure button states
        style.map(
            "Future.TButton",
            background=[
                ("active", KingdomStyles.COLORS["button_hover"]),
                ("pressed", KingdomStyles.COLORS["button_active"])
            ],
            foreground=[
                ("active", KingdomStyles.COLORS["text_bright"]),
                ("pressed", KingdomStyles.COLORS["primary_bright"])
            ]
        )
    
    @staticmethod
    def setup_entry_style(style):
        """Configure entry field styling for a futuristic appearance.
        
        Args:
            style: ttk.Style instance
        """
        # Create custom entry style
        style.configure(
            "Future.TEntry",
            fieldbackground=KingdomStyles.COLORS["input_bg"],
            foreground=KingdomStyles.COLORS["text_bright"],
            borderwidth=1,
            bordercolor=KingdomStyles.COLORS["primary"],
            lightcolor=KingdomStyles.COLORS["primary"],
            darkcolor=KingdomStyles.COLORS["primary_dark"],
            insertcolor=KingdomStyles.COLORS["primary"],
            selectbackground=KingdomStyles.COLORS["primary_dark"],
            selectforeground=KingdomStyles.COLORS["text_bright"],
            padding=[10, 6]
        )
    
    @staticmethod
    def create_rgb_frame(parent, title=None, **kwargs):
        """Create an RGB frame with optional title.
        
        Args:
            parent: Parent widget
            title: Optional title for the frame
            **kwargs: Additional arguments for EnhancedRGBFrame
            
        Returns:
            EnhancedRGBFrame instance
        """
        # Default styling
        border_width = kwargs.pop('border_width', 3)
        corner_radius = kwargs.pop('corner_radius', 10)
        bg_color = kwargs.pop('bg_color', KingdomStyles.COLORS["frame_bg"])
        
        # Create the frame
        frame = EnhancedRGBFrame(
            parent,
            border_width=border_width,
            corner_radius=corner_radius,
            bg_color=bg_color,
            **kwargs
        )
        
        # Add title if provided
        if title:
            title_label = tk.Label(
                frame.inner_frame,
                text=title.upper(),
                font=("Orbitron", 12, "bold"),
                fg=KingdomStyles.COLORS["primary"],
                bg=bg_color
            )
            title_label.pack(anchor="w", pady=(5, 10), padx=10)
        
        return frame

    @staticmethod
    def create_glow_button(parent, text, command=None, **kwargs):
        """Create a button with glowing effect.
        
        Args:
            parent: Parent widget
            text: Button text
            command: Button command
            **kwargs: Additional arguments for EnhancedGlowButton
            
        Returns:
            EnhancedGlowButton instance
        """
        # Default colors
        glow_color = kwargs.pop('glow_color', KingdomStyles.COLORS["primary"])
        
        # Create the button
        button = EnhancedGlowButton(
            parent,
            text=text,
            command=command,
            glow_color=glow_color,
            **kwargs
        )
        
        return button
    
    @staticmethod
    def create_status_bar(parent, **kwargs):
        """Create a status bar with futuristic styling.
        
        Args:
            parent: Parent widget
            **kwargs: Additional arguments for EnhancedStatusBar
            
        Returns:
            EnhancedStatusBar instance
        """
        # Default styling
        bg_color = kwargs.pop('bg_color', KingdomStyles.COLORS["frame_bg"])
        
        # Create the status bar
        status_bar = EnhancedStatusBar(
            parent,
            bg_color=bg_color,
            **kwargs
        )
        
        return status_bar
    
    @staticmethod
    def apply_theme(root):
        """Apply the futuristic theme to the entire application.
        
        Args:
            root: Root Tkinter window
            
        Returns:
            ttk.Style object
        """
        # Create style object
        style = ttk.Style(root)
        
        # Set up component styles
        FuturisticTheme.setup_notebook_style(style)
        FuturisticTheme.setup_button_style(style)
        FuturisticTheme.setup_entry_style(style)
        
        # Configure additional elements
        style.configure("TFrame", background=KingdomStyles.COLORS["frame_bg"])
        style.configure("TLabel", background=KingdomStyles.COLORS["frame_bg"], foreground=KingdomStyles.COLORS["text"])
        
        # Configure scrollbars
        style.configure("Future.Vertical.TScrollbar", 
                       gripcount=0,
                       background=KingdomStyles.COLORS["panel_bg"],
                       darkcolor=KingdomStyles.COLORS["primary_dark"],
                       lightcolor=KingdomStyles.COLORS["primary"],
                       troughcolor=KingdomStyles.COLORS["frame_bg"],
                       bordercolor=KingdomStyles.COLORS["frame_bg"],
                       arrowcolor=KingdomStyles.COLORS["primary"])
                       
        # Configure progressbar
        style.configure("Future.Horizontal.TProgressbar",
                       background=KingdomStyles.COLORS["primary"],
                       troughcolor=KingdomStyles.COLORS["panel_bg"],
                       bordercolor=KingdomStyles.COLORS["dark"],
                       lightcolor=KingdomStyles.COLORS["primary_bright"],
                       darkcolor=KingdomStyles.COLORS["primary_dark"])
        
        return style
