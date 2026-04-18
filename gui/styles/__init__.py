#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI Styles Package

This package contains all style definitions for Kingdom AI GUI components.
"""

# Import main styles
try:
    from . import vr_styles
except ImportError:
    vr_styles = None

# Define theme constants
DARK_THEME = {
    "background": "#2D2D2D",
    "foreground": "#FFFFFF",
    "accent": "#007BFF",
    "secondary": "#6C757D",
    "success": "#28A745",
    "warning": "#FFC107",
    "danger": "#DC3545",
    "info": "#17A2B8",
    "button_bg": "#444444",
    "button_fg": "#FFFFFF",
    "entry_bg": "#3D3D3D",
    "entry_fg": "#FFFFFF",
    "border": "#555555",
    "highlight": "#007BFF"
}

def get_dark_theme():
    """Return the dark theme dictionary."""
    return DARK_THEME.copy()

def get_light_theme():
    """Return the light theme dictionary."""
    return {
        "background": "#F0F0F0",
        "foreground": "#000000",
        "accent": "#0069D9",
        "secondary": "#5A6268",
        "success": "#218838",
        "warning": "#E0A800",
        "danger": "#C82333",
        "info": "#138496",
        "button_bg": "#E2E2E2",
        "button_fg": "#000000",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#000000",
        "border": "#CCCCCC",
        "highlight": "#0069D9"
    }

# Light theme constant for compatibility
LIGHT_THEME = get_light_theme()

# Style constants for compatibility - CRITICAL: These are used by various GUI components
ACCENT_COLOR = DARK_THEME["accent"]
BACKGROUND_COLOR = DARK_THEME["background"]  # Used by WalletQt and others
FOREGROUND_COLOR = DARK_THEME["foreground"]
TEXT_COLOR = DARK_THEME["foreground"]
BUTTON_BG = DARK_THEME["button_bg"]
BUTTON_FG = DARK_THEME["button_fg"]
ENTRY_BG = DARK_THEME["entry_bg"]
ENTRY_FG = DARK_THEME["entry_fg"]
BORDER_COLOR = DARK_THEME["border"]
HIGHLIGHT_COLOR = DARK_THEME["highlight"]
SUCCESS_COLOR = DARK_THEME["success"]
WARNING_COLOR = DARK_THEME["warning"]
DANGER_COLOR = DARK_THEME["danger"]
INFO_COLOR = DARK_THEME["info"]
# Additional constants required by WalletQt and other components
CARD_COLOR = "#3D3D3D"  # Card background color
SECONDARY_TEXT = "#A0A0A0"  # Secondary text color
ERROR_COLOR = DARK_THEME["danger"]  # Alias for danger
HOVER_COLOR = "#4A4A4A"  # Hover state color

# Export all available styles
__all__ = [
    'vr_styles', 
    'DARK_THEME', 
    'LIGHT_THEME', 
    'ACCENT_COLOR',
    'BACKGROUND_COLOR',
    'FOREGROUND_COLOR',
    'TEXT_COLOR',
    'BUTTON_BG',
    'BUTTON_FG',
    'ENTRY_BG',
    'ENTRY_FG',
    'BORDER_COLOR',
    'HIGHLIGHT_COLOR',
    'SUCCESS_COLOR',
    'WARNING_COLOR',
    'DANGER_COLOR',
    'INFO_COLOR',
    'CARD_COLOR',
    'SECONDARY_TEXT',
    'ERROR_COLOR',
    'HOVER_COLOR',
    'get_dark_theme', 
    'get_light_theme', 
    'CyberpunkRGBBorderWidget', 
    'KingdomStyle', 
    'initialize_gui_styles'
]

try:
    from gui.cyberpunk_style import CyberpunkRGBBorderWidget
except Exception:
    CyberpunkRGBBorderWidget = None

try:
    from gui.kingdom_style import KingdomStyle
except Exception:
    KingdomStyle = None

try:
    from gui.gui_styles import initialize_gui_styles
except Exception:
    initialize_gui_styles = None
