#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Style Sheet Constants - State-of-the-Art 2025
Centralized QSS (Qt Style Sheets) for consistent styling across all tabs

This module provides reusable stylesheet templates with the cyberpunk theme.
All styles use the constants from ui_constants.py for consistency.

Usage:
    from gui.kingdom_style_constants import KingdomStyles
    
    widget.setStyleSheet(KingdomStyles.get_card_style(
        bg_color='#1A1A3E',
        border_color='#00FFFF'
    ))
"""

from gui.ui_constants import SPACING, SIZING

__all__ = ['KingdomStyles', 'CyberpunkColors']


class CyberpunkColors:
    """
    Cyberpunk theme color palette
    
    All colors are hex codes for consistency with the existing Kingdom AI theme.
    """
    
    # Primary colors
    PRIMARY_CYAN: str = "#00FFFF"
    PRIMARY_MAGENTA: str = "#FF00FF"
    PRIMARY_YELLOW: str = "#FFD700"
    PRIMARY_GREEN: str = "#00FF00"
    PRIMARY_RED: str = "#FF0000"
    PRIMARY_BLUE: str = "#0000FF"
    PRIMARY_ORANGE: str = "#FF6B35"
    
    # Background colors
    BG_DARK: str = "#0A0A2E"
    BG_MEDIUM: str = "#1A1A3E"
    BG_LIGHT: str = "#2A2A4E"
    BG_CARD: str = "#0D1B2A"
    BG_HOVER: str = "#1A2A3E"
    
    # Text colors
    TEXT_WHITE: str = "#FFFFFF"
    TEXT_LIGHT: str = "#E0E0E0"
    TEXT_GRAY: str = "#999999"
    TEXT_DARK: str = "#666666"
    
    # Status colors
    STATUS_SUCCESS: str = "#00FF00"
    STATUS_WARNING: str = "#FFD700"
    STATUS_ERROR: str = "#FF0000"
    STATUS_INFO: str = "#00FFFF"
    STATUS_DISABLED: str = "#666666"
    
    # Button colors
    BTN_PRIMARY_BG: str = "#00FFFF"
    BTN_PRIMARY_HOVER: str = "#00DDDD"
    BTN_SUCCESS_BG: str = "#28a745"
    BTN_SUCCESS_HOVER: str = "#218838"
    BTN_DANGER_BG: str = "#dc3545"
    BTN_DANGER_HOVER: str = "#c82333"
    BTN_WARNING_BG: str = "#FFD700"
    BTN_WARNING_HOVER: str = "#FFA500"


class KingdomStyles:
    """
    Reusable Qt Style Sheet templates for Kingdom AI
    
    All templates use f-string formatting for customization while
    maintaining consistent spacing and sizing from ui_constants.
    """
    
    # ============================================================
    # CARD STYLES
    # ============================================================
    
    CARD_BASE = """
        QWidget {{
            background-color: {bg_color};
            border: {border_width}px solid {border_color};
            border-radius: {border_radius}px;
            padding: {padding};
            margin: {margin};
        }}
    """
    
    CARD_HOVER = """
        QWidget {{
            background-color: {bg_color};
            border: {border_width}px solid {border_color};
            border-radius: {border_radius}px;
            padding: {padding};
        }}
        QWidget:hover {{
            background-color: {hover_color};
            border-color: {hover_border};
        }}
    """
    
    # ============================================================
    # BUTTON STYLES
    # ============================================================
    
    BUTTON_PRIMARY = """
        QPushButton {{
            background-color: {bg_color};
            color: {text_color};
            padding: {padding};
            border-radius: {border_radius}px;
            border: {border_width}px solid {border_color};
            min-height: {min_height}px;
            min-width: {min_width}px;
            font-weight: bold;
            font-size: {font_size}px;
        }}
        QPushButton:hover {{
            background-color: {hover_color};
        }}
        QPushButton:pressed {{
            background-color: {pressed_color};
        }}
        QPushButton:disabled {{
            background-color: #666666;
            color: #999999;
        }}
    """
    
    BUTTON_GRADIENT = """
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 {color1}, stop:1 {color2});
            color: {text_color};
            padding: {padding};
            border-radius: {border_radius}px;
            border: {border_width}px solid {border_color};
            min-height: {min_height}px;
            min-width: {min_width}px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 {hover_color1}, stop:1 {hover_color2});
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 {pressed_color1}, stop:1 {pressed_color2});
        }}
    """
    
    # ============================================================
    # LABEL STYLES
    # ============================================================
    
    LABEL_HEADER = """
        QLabel {{
            color: {color};
            background-color: {bg_color};
            padding: {padding};
            border: {border_width}px solid {border_color};
            border-radius: {border_radius}px;
            font-weight: bold;
            font-size: {font_size}px;
        }}
    """
    
    LABEL_DATA = """
        QLabel {{
            background-color: {bg_color};
            color: {text_color};
            padding: {padding};
            border: {border_width}px solid {border_color};
            border-radius: {border_radius}px;
            font-family: monospace;
            font-size: {font_size}px;
        }}
    """
    
    # ============================================================
    # GROUPBOX STYLES
    # ============================================================
    
    GROUPBOX = """
        QGroupBox {{
            background-color: {bg_color};
            border: {border_width}px solid {border_color};
            border-radius: {border_radius}px;
            margin-top: 10px;
            padding: {padding};
            font-weight: bold;
            color: {title_color};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}
    """
    
    # ============================================================
    # SCROLL AREA STYLES
    # ============================================================
    
    SCROLL_AREA = """
        QScrollArea {{
            border: {border_width}px solid {border_color};
            border-radius: {border_radius}px;
            background-color: {bg_color};
        }}
        QScrollBar:vertical {{
            border: none;
            background: {scrollbar_bg};
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {scrollbar_handle};
            min-height: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {scrollbar_hover};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """
    
    # ============================================================
    # TAB WIDGET STYLES
    # ============================================================
    
    TAB_WIDGET = """
        QTabWidget::pane {{
            border: {border_width}px solid {border_color};
            background-color: {bg_color};
        }}
        QTabBar::tab {{
            background-color: {tab_bg};
            color: {tab_text};
            padding: {padding};
            margin: 2px;
            border: 1px solid {border_color};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {tab_selected_bg};
            color: {tab_selected_text};
            border-color: {border_color};
        }}
        QTabBar::tab:hover {{
            background-color: {tab_hover_bg};
        }}
    """
    
    # ============================================================
    # STATIC METHODS FOR COMMON STYLES
    # ============================================================
    
    @staticmethod
    def get_card_style(bg_color: str, border_color: str,
                       padding: str = SPACING.CARD_PADDING,
                       margin: str = "5px",
                       border_width: int = 2,
                       border_radius: int = 6) -> str:
        """
        Get a styled card widget
        
        Args:
            bg_color: Background color (hex)
            border_color: Border color (hex)
            padding: Padding (default from constants)
            margin: Margin string (e.g. "5px")
            border_width: Border width in pixels
            border_radius: Border radius in pixels
            
        Returns:
            QSS stylesheet string
        """
        return KingdomStyles.CARD_BASE.format(
            bg_color=bg_color,
            border_color=border_color,
            padding=padding,
            margin=margin,
            border_width=border_width,
            border_radius=border_radius
        )
    
    @staticmethod
    def get_button_style(bg_color: str, text_color: str = CyberpunkColors.TEXT_WHITE,
                         hover_color: str = None, pressed_color: str = None,
                         border_color: str = None,
                         padding: str = SPACING.BUTTON_PADDING,
                         min_height: int = SIZING.BUTTON_MIN_HEIGHT,
                         min_width: int = SIZING.BUTTON_MIN_WIDTH,
                         border_width: int = 2,
                         border_radius: int = 4,
                         font_size: int = 12) -> str:
        """
        Get a styled button
        
        Args:
            bg_color: Background color
            text_color: Text color (default white)
            hover_color: Hover background (auto-generated if None)
            pressed_color: Pressed background (auto-generated if None)
            border_color: Border color (defaults to bg_color)
            padding: Button padding
            min_height: Minimum height (from constants)
            min_width: Minimum width (from constants)
            border_width: Border width in pixels
            border_radius: Border radius in pixels
            font_size: Font size in pixels
            
        Returns:
            QSS stylesheet string
        """
        if hover_color is None:
            hover_color = KingdomStyles._lighten_color(bg_color)
        if pressed_color is None:
            pressed_color = KingdomStyles._darken_color(bg_color)
        if border_color is None:
            border_color = bg_color
            
        return KingdomStyles.BUTTON_PRIMARY.format(
            bg_color=bg_color,
            text_color=text_color,
            hover_color=hover_color,
            pressed_color=pressed_color,
            border_color=border_color,
            padding=padding,
            min_height=min_height,
            min_width=min_width,
            border_width=border_width,
            border_radius=border_radius,
            font_size=font_size
        )
    
    @staticmethod
    def get_button_gradient_style(color1: str, color2: str,
                                   text_color: str = CyberpunkColors.TEXT_WHITE,
                                   border_color: str = None,
                                   padding: str = SPACING.BUTTON_PADDING,
                                   min_height: int = SIZING.BUTTON_MIN_HEIGHT,
                                   min_width: int = SIZING.BUTTON_MIN_WIDTH) -> str:
        """Get gradient button style"""
        hover1 = KingdomStyles._lighten_color(color1)
        hover2 = KingdomStyles._lighten_color(color2)
        pressed1 = KingdomStyles._darken_color(color1)
        pressed2 = KingdomStyles._darken_color(color2)
        
        if border_color is None:
            border_color = color1
            
        return KingdomStyles.BUTTON_GRADIENT.format(
            color1=color1,
            color2=color2,
            text_color=text_color,
            hover_color1=hover1,
            hover_color2=hover2,
            pressed_color1=pressed1,
            pressed_color2=pressed2,
            border_color=border_color,
            padding=padding,
            min_height=min_height,
            min_width=min_width,
            border_width=2,
            border_radius=4
        )
    
    @staticmethod
    def get_label_header_style(color: str, bg_color: str, border_color: str,
                                padding: str = SPACING.PADDING_LARGE,
                                border_width: int = 2,
                                border_radius: int = 6,
                                font_size: int = 11) -> str:
        """Get styled header label"""
        return KingdomStyles.LABEL_HEADER.format(
            color=color,
            bg_color=bg_color,
            border_color=border_color,
            padding=padding,
            border_width=border_width,
            border_radius=border_radius,
            font_size=font_size
        )
    
    @staticmethod
    def get_groupbox_style(bg_color: str, border_color: str, title_color: str,
                           padding: str = "15px",
                           border_width: int = 2,
                           border_radius: int = 8) -> str:
        """Get styled group box"""
        return KingdomStyles.GROUPBOX.format(
            bg_color=bg_color,
            border_color=border_color,
            title_color=title_color,
            padding=padding,
            border_width=border_width,
            border_radius=border_radius
        )
    
    @staticmethod
    def get_scroll_area_style(bg_color: str = CyberpunkColors.BG_DARK,
                              border_color: str = CyberpunkColors.PRIMARY_CYAN,
                              scrollbar_bg: str = "#1A1A3E",
                              scrollbar_handle: str = "#00FFFF",
                              scrollbar_hover: str = "#00DDDD") -> str:
        """Get styled scroll area"""
        return KingdomStyles.SCROLL_AREA.format(
            bg_color=bg_color,
            border_color=border_color,
            scrollbar_bg=scrollbar_bg,
            scrollbar_handle=scrollbar_handle,
            scrollbar_hover=scrollbar_hover,
            border_width=1,
            border_radius=4
        )
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    @staticmethod
    def _lighten_color(hex_color: str, amount: int = 20) -> str:
        """Lighten a hex color by amount (0-100)"""
        # Simple lightening - add to RGB values
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgb = tuple(min(255, c + amount) for c in rgb)
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    
    @staticmethod
    def _darken_color(hex_color: str, amount: int = 20) -> str:
        """Darken a hex color by amount (0-100)"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgb = tuple(max(0, c - amount) for c in rgb)
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


if __name__ == '__main__':
    # Example usage
    print("=" * 60)
    print("KINGDOM AI STYLE CONSTANTS")
    print("=" * 60)
    
    print("\n🎨 EXAMPLE CARD STYLE:")
    print(KingdomStyles.get_card_style(
        bg_color='#1A1A3E',
        border_color='#00FFFF'
    ))
    
    print("\n🎨 EXAMPLE BUTTON STYLE:")
    print(KingdomStyles.get_button_style(
        bg_color='#00FF00',
        text_color='#000000'
    ))
    
    print("\n✅ Style constants loaded successfully")
    print("=" * 60)
