#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI UI Constants - State-of-the-Art 2025
Centralized spacing, sizing, and layout constants for consistent UI across all tabs

This module provides immutable constants for:
- Layout margins and spacing
- Widget padding
- Button and card sizing
- Consistent UI measurements

Usage:
    from gui.ui_constants import SPACING, SIZING
    
    layout.setContentsMargins(*SPACING.LAYOUT_MARGIN_MEDIUM)
    layout.setSpacing(SPACING.SPACING_MEDIUM)
    button.setMinimumHeight(SIZING.BUTTON_MIN_HEIGHT)
"""

from dataclasses import dataclass
from typing import Tuple

__all__ = ['SPACING', 'SIZING', 'UISpacing', 'UISizing']


@dataclass(frozen=True)
class UISpacing:
    """
    Spacing constants for layouts (immutable)
    
    All values are in pixels and follow Qt's left, top, right, bottom convention
    for margins.
    """
    
    # Layout Margins (left, top, right, bottom)
    LAYOUT_MARGIN_NONE: Tuple[int, int, int, int] = (0, 0, 0, 0)
    LAYOUT_MARGIN_TINY: Tuple[int, int, int, int] = (2, 2, 2, 2)
    LAYOUT_MARGIN_SMALL: Tuple[int, int, int, int] = (5, 5, 5, 5)
    LAYOUT_MARGIN_MEDIUM: Tuple[int, int, int, int] = (10, 10, 10, 10)
    LAYOUT_MARGIN_LARGE: Tuple[int, int, int, int] = (15, 15, 15, 15)
    LAYOUT_MARGIN_XLARGE: Tuple[int, int, int, int] = (20, 20, 20, 20)
    
    # Layout Spacing (between widgets in a layout)
    SPACING_NONE: int = 0
    SPACING_TINY: int = 2
    SPACING_SMALL: int = 5
    SPACING_MEDIUM: int = 10
    SPACING_LARGE: int = 15
    SPACING_XLARGE: int = 20
    SPACING_XXLARGE: int = 25
    
    # Widget Padding (internal spacing - for QSS)
    # These are strings because they're used in stylesheets
    PADDING_NONE: str = "0px"
    PADDING_TINY: str = "2px"
    PADDING_SMALL: str = "5px"
    PADDING_MEDIUM: str = "8px"
    PADDING_LARGE: str = "10px"
    PADDING_XLARGE: str = "15px"
    PADDING_XXLARGE: str = "20px"
    
    # Card/GroupBox specific spacing
    CARD_SPACING: int = 15
    CARD_MARGIN: Tuple[int, int, int, int] = (10, 5, 10, 5)
    CARD_PADDING: str = "10px"
    CARD_INTERNAL_SPACING: int = 8
    
    # Tab spacing
    TAB_SPACING: int = 5
    TAB_MARGIN: Tuple[int, int, int, int] = (5, 5, 5, 5)
    
    # Button spacing
    BUTTON_SPACING: int = 8
    BUTTON_MARGIN: str = "5px"
    BUTTON_PADDING: str = "8px 16px"  # vertical horizontal


@dataclass(frozen=True)
class UISizing:
    """
    Widget sizing constants
    
    Provides minimum, maximum, and preferred sizes for common widgets.
    """
    
    # Button sizes
    BUTTON_MIN_HEIGHT: int = 35
    BUTTON_MIN_WIDTH: int = 100
    BUTTON_PREFERRED_HEIGHT: int = 40
    BUTTON_LARGE_HEIGHT: int = 50
    BUTTON_ICON_SIZE: int = 24
    BUTTON_SMALL_ICON_SIZE: int = 16
    
    # Card/Widget sizes
    CARD_MIN_WIDTH: int = 280
    CARD_MAX_WIDTH: int = 400
    CARD_PREFERRED_WIDTH: int = 320
    CARD_MIN_HEIGHT: int = 200
    CARD_MAX_HEIGHT: int = 500
    
    # Intelligence Hub card sizes (for equal sizing)
    INTEL_CARD_MIN_WIDTH: int = 280
    INTEL_CARD_MAX_WIDTH: int = 350
    INTEL_CARD_FIXED_HEIGHT: int = 350  # Use for equal height cards
    
    # Tab/Panel sizes
    TAB_MIN_HEIGHT: int = 400
    TAB_PREFERRED_HEIGHT: int = 600
    PANEL_MIN_WIDTH: int = 250
    PANEL_PREFERRED_WIDTH: int = 300
    
    # List item sizes
    LIST_ITEM_HEIGHT: int = 40
    LIST_ITEM_MIN_HEIGHT: int = 30
    LIST_ITEM_ICON_SIZE: int = 20
    
    # Input field sizes
    INPUT_MIN_HEIGHT: int = 30
    INPUT_PREFERRED_HEIGHT: int = 35
    INPUT_MIN_WIDTH: int = 150
    
    # Scroll area sizes
    SCROLL_MIN_WIDTH: int = 200
    SCROLL_MIN_HEIGHT: int = 300
    
    # Status indicator sizes
    LED_INDICATOR_SIZE: int = 16
    STATUS_ICON_SIZE: int = 20


# Create singleton instances
SPACING = UISpacing()
SIZING = UISizing()


# Utility functions for common operations
def get_equal_stretch_factors(count: int) -> list:
    """
    Get equal stretch factors for QGridLayout columns
    
    Args:
        count: Number of columns
        
    Returns:
        List of (column_index, stretch_factor) tuples
        
    Example:
        for col, stretch in get_equal_stretch_factors(3):
            grid_layout.setColumnStretch(col, stretch)
    """
    return [(i, 1) for i in range(count)]


def apply_standard_margins(layout, margin_type: str = 'medium'):
    """
    Apply standard margins to a layout
    
    Args:
        layout: QLayout instance
        margin_type: 'none', 'tiny', 'small', 'medium', 'large', 'xlarge'
    """
    margin_map = {
        'none': SPACING.LAYOUT_MARGIN_NONE,
        'tiny': SPACING.LAYOUT_MARGIN_TINY,
        'small': SPACING.LAYOUT_MARGIN_SMALL,
        'medium': SPACING.LAYOUT_MARGIN_MEDIUM,
        'large': SPACING.LAYOUT_MARGIN_LARGE,
        'xlarge': SPACING.LAYOUT_MARGIN_XLARGE,
    }
    
    margins = margin_map.get(margin_type.lower(), SPACING.LAYOUT_MARGIN_MEDIUM)
    layout.setContentsMargins(*margins)


def apply_standard_spacing(layout, spacing_type: str = 'medium'):
    """
    Apply standard spacing to a layout
    
    Args:
        layout: QLayout instance
        spacing_type: 'none', 'tiny', 'small', 'medium', 'large', 'xlarge', 'xxlarge'
    """
    spacing_map = {
        'none': SPACING.SPACING_NONE,
        'tiny': SPACING.SPACING_TINY,
        'small': SPACING.SPACING_SMALL,
        'medium': SPACING.SPACING_MEDIUM,
        'large': SPACING.SPACING_LARGE,
        'xlarge': SPACING.SPACING_XLARGE,
        'xxlarge': SPACING.SPACING_XXLARGE,
    }
    
    spacing = spacing_map.get(spacing_type.lower(), SPACING.SPACING_MEDIUM)
    layout.setSpacing(spacing)


def configure_layout(layout, margin: str = 'medium', spacing: str = 'medium'):
    """
    Configure layout with standard margins and spacing
    
    Args:
        layout: QLayout instance
        margin: Margin type ('none', 'small', 'medium', 'large')
        spacing: Spacing type ('none', 'small', 'medium', 'large')
        
    Example:
        layout = QVBoxLayout()
        configure_layout(layout, margin='medium', spacing='large')
    """
    apply_standard_margins(layout, margin)
    apply_standard_spacing(layout, spacing)


if __name__ == '__main__':
    # Print all constants for reference
    print("=" * 60)
    print("KINGDOM AI UI CONSTANTS")
    print("=" * 60)
    
    print("\n📏 SPACING CONSTANTS:")
    print(f"  Layout Margins:")
    print(f"    NONE:   {SPACING.LAYOUT_MARGIN_NONE}")
    print(f"    SMALL:  {SPACING.LAYOUT_MARGIN_SMALL}")
    print(f"    MEDIUM: {SPACING.LAYOUT_MARGIN_MEDIUM}")
    print(f"    LARGE:  {SPACING.LAYOUT_MARGIN_LARGE}")
    
    print(f"\n  Widget Spacing:")
    print(f"    NONE:   {SPACING.SPACING_NONE}px")
    print(f"    SMALL:  {SPACING.SPACING_SMALL}px")
    print(f"    MEDIUM: {SPACING.SPACING_MEDIUM}px")
    print(f"    LARGE:  {SPACING.SPACING_LARGE}px")
    
    print(f"\n  Padding (for QSS):")
    print(f"    SMALL:  {SPACING.PADDING_SMALL}")
    print(f"    MEDIUM: {SPACING.PADDING_MEDIUM}")
    print(f"    LARGE:  {SPACING.PADDING_LARGE}")
    
    print("\n📐 SIZING CONSTANTS:")
    print(f"  Buttons:")
    print(f"    Min Height: {SIZING.BUTTON_MIN_HEIGHT}px")
    print(f"    Min Width:  {SIZING.BUTTON_MIN_WIDTH}px")
    
    print(f"\n  Cards:")
    print(f"    Min Width:  {SIZING.CARD_MIN_WIDTH}px")
    print(f"    Max Width:  {SIZING.CARD_MAX_WIDTH}px")
    print(f"    Preferred:  {SIZING.CARD_PREFERRED_WIDTH}px")
    
    print("\n" + "=" * 60)
    print("✅ All constants loaded successfully")
    print("=" * 60)
