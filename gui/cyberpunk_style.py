#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Cyberpunk Style System
Provides advanced cyberpunk styling for the Kingdom AI PyQt6 GUI components.
Features animated RGB effects, glowing borders, and futuristic UI elements.
"""

import logging
import math
import random
from typing import Dict, List, Tuple, Optional, Union, Any

from PyQt6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QApplication
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QPoint, QRect, pyqtProperty, QObject, pyqtSignal, QThread, QEvent
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen, QBrush, QPainterPath, QFont

# Configure logger
logger = logging.getLogger("cyberpunk_style")

# Export all classes for proper imports
__all__ = [
    'CyberpunkStyle', 'CyberpunkEffect', 'CyberpunkParticleSystem', 
    'CyberpunkParticleEffect', 'CyberpunkRGBBorderWidget', 'CYBERPUNK_THEME'
]

# Define cyberpunk theme constants
CYBERPUNK_THEME = {
    "background": "#0A0E17",         # Dark navy/black
    "background_alt": "#0F1620",     # Slightly lighter dark background
    "foreground": "#E6FFFF",         # Bright cyan-white
    "foreground_alt": "#99CCFF",     # Muted cyan
    
    # Neon colors
    "neon_blue": "#00FFFF",         # Cyan
    "neon_pink": "#FF00FF",         # Magenta
    "neon_purple": "#BF00FF",       # Purple
    "neon_green": "#00FF66",        # Green
    "neon_yellow": "#FFFF00",       # Yellow
    "neon_orange": "#FF7F00",       # Orange
    "neon_red": "#FF0000",          # Red
    
    # Interface colors
    "accent": "#00FFFF",            # Default accent is cyan
    "accent_secondary": "#FF00FF",  # Secondary accent (magenta)
    "success": "#00FF66",           # Neon green
    "warning": "#FFFF00",           # Neon yellow
    "danger": "#FF1A1A",            # Bright red
    "error": "#FF4444",             # Error red (alias used by tabs)
    "info": "#00CCFF",              # Blue
    
    # Text colors (used by Software Automation, MCP Control Center, etc.)
    "text_primary": "#FFFFFF",       # White text
    "text_secondary": "#888899",     # Muted secondary text
    
    # Background aliases (used by tabs that reference bg_primary/bg_secondary)
    "bg_primary": "#0A0E17",         # Same as 'background'
    "bg_secondary": "#0F1620",       # Same as 'background_alt'
    
    # UI element colors
    "button_bg": "#1A1E2E",         # Dark blue-black
    "button_fg": "#E6FFFF",         # Bright cyan-white
    "entry_bg": "#1E2638",          # Dark navy blue
    "entry_fg": "#E6FFFF",          # Bright cyan-white
    "border": "#00FFFF",            # Cyan
    "highlight": "#FF00FF",         # Magenta
    
    # Glows
    "glow_intensity": 15,           # Higher = stronger glow
    "glow_spread": 8,               # Glow spread radius
    "glow_animations": True,        # Enable glow animations
    
    # RGB cycle colors (for animated effects)
    "rgb_cycle": [
        "#00FFFF",  # Cyan
        "#FF00FF",  # Magenta 
        "#00FF66",  # Neon green
        "#BF00FF",  # Purple
        "#FFFF00",  # Yellow
    ]
}

# RGB Animation settings
RGB_ANIMATION_SPEED = 2000  # milliseconds for one full cycle
RGB_ANIMATION_STEPS = 100   # number of color steps in the cycle

class CyberpunkEffect:
    """Effects that can be applied to widgets for cyberpunk styling"""
    
    @staticmethod
    def create_glow_effect(color: Union[str, QColor], intensity: int = 15, spread: int = 8) -> QGraphicsDropShadowEffect:
        """Create a neon glow effect
        
        Args:
            color: Color of the glow (hex string or QColor)
            intensity: Intensity of the glow (0-100)
            spread: Spread radius of the glow
            
        Returns:
            QGraphicsDropShadowEffect: The configured glow effect
        """
        if isinstance(color, str):
            qcolor = QColor(color)
        else:
            qcolor = color
            
        glow = QGraphicsDropShadowEffect()
        glow.setColor(qcolor)
        glow.setOffset(0, 0)
        glow.setBlurRadius(spread)
        glow.setEnabled(True)
        return glow
    
    @staticmethod
    def apply_neon_text(widget: QWidget, *args, **kwargs):
        """Apply neon text effect to a widget"""
        try:
            widget.setStyleSheet(f"color: {CYBERPUNK_THEME['neon_blue']}; font-weight: bold;")
        except Exception:
            pass
    
    @staticmethod
    def apply_glass_effect(widget: QWidget, alpha=120, *args, **kwargs):
        """Apply glass effect to a widget"""
        try:
            widget.setStyleSheet(f"background-color: rgba(10, 20, 30, {alpha/255});")
        except Exception:
            pass
    
    @staticmethod
    def apply_cyberpunk_style(widget: QWidget, *args, **kwargs):
        """Apply cyberpunk style to a widget"""
        try:
            CyberpunkStyle.apply_to_widget(widget, "default")
        except Exception:
            pass
    
    @staticmethod
    def apply_tab_style(widget: QWidget, *args, **kwargs):
        """Apply tab style to a widget"""
        try:
            widget.setStyleSheet(CyberpunkStyle.get_style_sheet("default"))
        except Exception:
            pass
    
    @staticmethod
    def apply_neon_effect(widget: QWidget, *args, **kwargs):
        """Apply neon effect to a widget"""
        try:
            glow = CyberpunkEffect.create_glow_effect(CYBERPUNK_THEME["neon_blue"])
            widget.setGraphicsEffect(glow)
        except Exception:
            pass
    
    @staticmethod
    def setup_rgb_animation(widget: QWidget, property_name: str = "color",
                           duration: int = RGB_ANIMATION_SPEED) -> QPropertyAnimation:
        """Set up an RGB color cycling animation
        
        Args:
            widget: The widget to animate
            property_name: The property to animate
            duration: Animation duration in milliseconds
            
        Returns:
            QPropertyAnimation: The configured animation object
        """
        animation = QPropertyAnimation(widget, property_name.encode())
        animation.setDuration(duration)
        animation.setLoopCount(-1)  # Infinite loop
        animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        # STATE-OF-THE-ART: Always set start and end values to prevent errors (2024 best practice)
        if property_name == "color":
            animation.setStartValue(QColor(255, 0, 0))    # Red
            animation.setEndValue(QColor(0, 255, 255))    # Cyan
        elif property_name == "geometry":
            current_geom = widget.geometry()
            animation.setStartValue(current_geom)
            animation.setEndValue(current_geom)  # Same as start for safety
        else:
            # Generic numeric property
            animation.setStartValue(0)
            animation.setEndValue(100)
            
        return animation

class ThreadSafePainter(QObject):
    """STATE-OF-THE-ART: Thread-safe painter using Qt Signals/Slots pattern (2024/2025)"""
    
    # Signals for thread-safe painting operations
    paint_requested = pyqtSignal(QWidget, object)  # widget, paint_function
    
    def __init__(self):
        super().__init__()
        # Connect signal to slot (runs in GUI thread)
        self.paint_requested.connect(self._safe_paint)
    
    def request_paint(self, widget: QWidget, paint_function):
        """Request painting from any thread - will be executed in GUI thread"""
        if QThread.currentThread() == QApplication.instance().thread():
            # Already in GUI thread, paint directly
            self._safe_paint(widget, paint_function)
        else:
            # Emit signal to ensure painting happens in GUI thread
            self.paint_requested.emit(widget, paint_function)
    
    def _safe_paint(self, widget: QWidget, paint_function):
        """Thread-safe painting method - always runs in GUI thread"""
        try:
            if widget and hasattr(widget, 'paintEvent'):
                painter = QPainter(widget)
                if painter.isActive():
                    try:
                        paint_function(painter, widget)
                    finally:
                        painter.end()
        except Exception as e:
            logger.error(f"Thread-safe painting error: {e}")

# Global thread-safe painter instance
_thread_safe_painter = ThreadSafePainter()

class CyberpunkStyle:
    """Advanced cyberpunk styling for Kingdom AI PyQt6 GUI"""
    
    @staticmethod
    def apply_to_widget(widget: QWidget, component_type: str = "default") -> None:
        """Apply cyberpunk styling to a PyQt6 widget
        
        Args:
            widget: The widget to style
            component_type: The type of component for specialized styling
        """
        try:
            # Apply base cyberpunk style
            widget.setStyleSheet(CyberpunkStyle.get_style_sheet(component_type))
            
            # Add glow effect to certain widgets
            if component_type in ["button", "frame", "card"]:
                glow = CyberpunkEffect.create_glow_effect(
                    CYBERPUNK_THEME["neon_blue"],
                    CYBERPUNK_THEME["glow_intensity"],
                    CYBERPUNK_THEME["glow_spread"]
                )
                widget.setGraphicsEffect(glow)
        except Exception as e:
            logger.error(f"Failed to apply cyberpunk style to {component_type} widget: {e}")
    
    @staticmethod
    def get_style_sheet(component_type: str = "default") -> str:
        """Get the cyberpunk stylesheet for a specific component type
        
        Args:
            component_type: The type of component to get stylesheet for
            
        Returns:
            str: The appropriate QSS stylesheet for the component
        """
        try:
            # Base cyberpunk stylesheet for all components
            base_style = f"""
            QWidget {{
                background-color: {CYBERPUNK_THEME["background"]};
                color: {CYBERPUNK_THEME["foreground"]};
                font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
                font-weight: 500;
            }}
            
            QLabel {{
                color: {CYBERPUNK_THEME["foreground"]};
            }}
            
            QPushButton {{
                background-color: {CYBERPUNK_THEME["button_bg"]};
                color: {CYBERPUNK_THEME["button_fg"]};
                border: 2px solid {CYBERPUNK_THEME["border"]};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: rgba(0, 255, 255, 0.2);
                border: 2px solid {CYBERPUNK_THEME["highlight"]};
            }}
            
            QPushButton:pressed {{
                background-color: rgba(255, 0, 255, 0.3);
                border: 2px solid {CYBERPUNK_THEME["neon_pink"]};
            }}
            
            QGroupBox {{
                background-color: {CYBERPUNK_THEME["background_alt"]};
                border: 2px solid {CYBERPUNK_THEME["border"]};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 14px;
                font-weight: bold;
                color: {CYBERPUNK_THEME["neon_blue"]};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                color: {CYBERPUNK_THEME["neon_blue"]};
                background-color: {CYBERPUNK_THEME["background"]};
                border: 1px solid {CYBERPUNK_THEME["border"]};
                border-radius: 3px;
            }}
            
            QLineEdit, QTextEdit {{
                background-color: {CYBERPUNK_THEME["entry_bg"]};
                color: {CYBERPUNK_THEME["foreground"]};
                border: 2px solid {CYBERPUNK_THEME["border"]};
                border-radius: 4px;
                padding: 5px;
                selection-background-color: {CYBERPUNK_THEME["neon_purple"]};
            }}
            
            QProgressBar {{
                border: 2px solid {CYBERPUNK_THEME["border"]};
                border-radius: 5px;
                text-align: center;
                color: {CYBERPUNK_THEME["foreground"]};
                background-color: {CYBERPUNK_THEME["background_alt"]};
                padding: 1px;
            }}
            
            QProgressBar::chunk {{
                background-color: {CYBERPUNK_THEME["accent"]};
                border-radius: 3px;
            }}
            
            QComboBox {{
                background-color: {CYBERPUNK_THEME["entry_bg"]};
                color: {CYBERPUNK_THEME["foreground"]};
                border: 2px solid {CYBERPUNK_THEME["border"]};
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 20px;
            }}
            
            QComboBox::drop-down {{
                border-left: 1px solid {CYBERPUNK_THEME["border"]};
                width: 24px;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {CYBERPUNK_THEME["background"]};
                color: {CYBERPUNK_THEME["foreground"]};
                border: 2px solid {CYBERPUNK_THEME["border"]};
                selection-background-color: rgba(0, 255, 255, 0.3);
                selection-color: {CYBERPUNK_THEME["neon_blue"]};
            }}
            
            QSpinBox {{
                background-color: {CYBERPUNK_THEME["entry_bg"]};
                color: {CYBERPUNK_THEME["foreground"]};
                border: 2px solid {CYBERPUNK_THEME["border"]};
                border-radius: 4px;
                padding: 4px;
            }}
            
            QTableWidget, QTableView {{
                background-color: {CYBERPUNK_THEME["background"]};
                color: {CYBERPUNK_THEME["foreground"]};
                gridline-color: {CYBERPUNK_THEME["border"]};
                border: 2px solid {CYBERPUNK_THEME["border"]};
                selection-background-color: rgba(0, 255, 255, 0.2);
                selection-color: {CYBERPUNK_THEME["neon_blue"]};
            }}
            
            QHeaderView::section {{
                background-color: {CYBERPUNK_THEME["background_alt"]};
                color: {CYBERPUNK_THEME["neon_blue"]};
                border: 1px solid {CYBERPUNK_THEME["border"]};
                padding: 4px;
                font-weight: bold;
            }}
            
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            
            QScrollBar:vertical {{
                background-color: {CYBERPUNK_THEME["background"]};
                width: 12px;
                border: none;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {CYBERPUNK_THEME["border"]};
                border-radius: 4px;
                min-height: 30px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {CYBERPUNK_THEME["neon_blue"]};
            }}
            
            QScrollBar:horizontal {{
                background-color: {CYBERPUNK_THEME["background"]};
                height: 12px;
                border: none;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {CYBERPUNK_THEME["border"]};
                border-radius: 4px;
                min-width: 30px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: {CYBERPUNK_THEME["neon_blue"]};
            }}
            
            QScrollBar::add-line, QScrollBar::sub-line {{
                height: 0px;
                width: 0px;
            }}
            
            QCheckBox {{
                color: {CYBERPUNK_THEME["foreground"]};
                spacing: 6px;
            }}
            
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {CYBERPUNK_THEME["border"]};
                border-radius: 3px;
                background-color: {CYBERPUNK_THEME["entry_bg"]};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {CYBERPUNK_THEME["accent"]};
                border-color: {CYBERPUNK_THEME["neon_blue"]};
            }}
            """
            
            # Component-specific stylesheets
            component_styles = {
                "loading_screen": base_style + f"""
                QLabel#title_label {{
                    font-size: 28px;
                    font-weight: bold;
                    color: {CYBERPUNK_THEME["neon_blue"]};
                }}
                
                QFrame#main_frame {{
                    background-color: {CYBERPUNK_THEME["background"]};
                    border: 2px solid {CYBERPUNK_THEME["border"]};
                    border-radius: 10px;
                }}
                
                QLabel#status_label {{
                    font-size: 16px;
                    color: {CYBERPUNK_THEME["neon_green"]};
                }}
                
                QProgressBar {{
                    height: 10px;
                    background-color: {CYBERPUNK_THEME["background_alt"]};
                    border: 2px solid {CYBERPUNK_THEME["border"]};
                    border-radius: 5px;
                }}
                
                QProgressBar::chunk {{
                    background-color: {CYBERPUNK_THEME["neon_blue"]};
                }}
                """,
                
                "dashboard": base_style + f"""
                QFrame#dashboard_card {{
                    background-color: {CYBERPUNK_THEME["background_alt"]};
                    border: 2px solid {CYBERPUNK_THEME["border"]};
                    border-radius: 6px;
                }}
                
                QLabel#section_header {{
                    font-size: 16px;
                    font-weight: bold;
                    color: {CYBERPUNK_THEME["neon_blue"]};
                }}
                
                QLabel#data_label {{
                    font-size: 22px;
                    color: {CYBERPUNK_THEME["neon_green"]};
                }}
                """,
                
                "trading": base_style + f"""
                QLabel#market_data_header {{
                    font-size: 18px;
                    font-weight: bold;
                    color: {CYBERPUNK_THEME["neon_yellow"]};
                }}
                
                QLabel#price_up {{
                    color: {CYBERPUNK_THEME["neon_green"]};
                    font-weight: bold;
                }}
                
                QLabel#price_down {{
                    color: {CYBERPUNK_THEME["neon_red"]};
                    font-weight: bold;
                }}
                
                QFrame#market_card {{
                    background-color: rgba(10, 30, 40, 0.7);
                    border: 2px solid {CYBERPUNK_THEME["neon_blue"]};
                    border-radius: 6px;
                }}
                """,
                
                "blockchain": base_style + f"""
                QLabel#blockchain_header {{
                    font-size: 18px;
                    font-weight: bold;
                    color: {CYBERPUNK_THEME["neon_purple"]};
                }}
                
                QLabel#hash_label {{
                    font-family: 'Consolas', 'Courier New', monospace;
                    color: {CYBERPUNK_THEME["neon_green"]};
                }}
                
                QLabel#address_label {{
                    font-family: 'Consolas', 'Courier New', monospace;
                    color: {CYBERPUNK_THEME["neon_blue"]};
                }}
                """,
                
                "thoth": base_style + f"""
                QLabel#ai_header {{
                    font-size: 18px;
                    font-weight: bold;
                    color: {CYBERPUNK_THEME["neon_purple"]};
                }}
                
                QTextEdit#ai_output {{
                    background-color: rgba(10, 20, 30, 0.8);
                    color: {CYBERPUNK_THEME["neon_green"]};
                    border: 2px solid {CYBERPUNK_THEME["border"]};
                    font-family: 'Consolas', 'Courier New', monospace;
                    padding: 10px;
                }}
                """,
                
                "mining": base_style + f"""
                QLabel#mining_header {{
                    font-size: 18px;
                    font-weight: bold;
                    color: {CYBERPUNK_THEME["neon_orange"]};
                }}
                
                QFrame#mining_card {{
                    background-color: rgba(10, 30, 40, 0.7);
                    border: 2px solid {CYBERPUNK_THEME["neon_orange"]};
                    border-radius: 6px;
                }}
                
                QProgressBar#hashrate_progress {{
                    height: 8px;
                    border-radius: 4px;
                }}
                
                QProgressBar#hashrate_progress::chunk {{
                    background-color: {CYBERPUNK_THEME["neon_orange"]};
                }}
                """,
                
                "tabs": base_style + f"""
                QTabWidget::pane {{
                    border: 2px solid {CYBERPUNK_THEME["border"]};
                    background-color: {CYBERPUNK_THEME["background"]};
                    border-radius: 6px;
                    margin-top: -1px;
                }}
                
                QTabBar {{
                    background: transparent;
                }}
                
                QTabBar::tab {{
                    background-color: {CYBERPUNK_THEME["background_alt"]};
                    color: {CYBERPUNK_THEME["foreground"]};
                    border: 2px solid {CYBERPUNK_THEME["border"]};
                    border-bottom: none;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                    padding: 8px 16px;
                    margin-right: 2px;
                    min-width: 80px;
                    font-weight: bold;
                }}
                
                QTabBar::tab:selected {{
                    background-color: {CYBERPUNK_THEME["background"]};
                    color: {CYBERPUNK_THEME["neon_blue"]};
                    border-bottom: 3px solid {CYBERPUNK_THEME["neon_blue"]};
                    margin-bottom: -2px;
                }}
                
                QTabBar::tab:hover:!selected {{
                    background-color: rgba(0, 255, 255, 0.1);
                    color: {CYBERPUNK_THEME["highlight"]};
                }}
                
                QTabBar::tab:!selected {{
                    margin-top: 2px;
                }}
                """,
                
                "tab_container": base_style + f"""
                QTabWidget {{
                    background-color: transparent;
                }}
                
                QTabWidget::pane {{
                    border: 2px solid {CYBERPUNK_THEME["border"]};
                    background-color: {CYBERPUNK_THEME["background"]};
                    border-radius: 6px;
                    padding: 5px;
                }}
                
                QTabBar {{
                    background: transparent;
                    qproperty-drawBase: 0;
                }}
                
                QTabBar::tab {{
                    background-color: {CYBERPUNK_THEME["background_alt"]};
                    color: {CYBERPUNK_THEME["foreground"]};
                    border: 2px solid {CYBERPUNK_THEME["border"]};
                    border-bottom: none;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                    padding: 10px 20px;
                    margin-right: 3px;
                    min-width: 100px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                
                QTabBar::tab:selected {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(0, 255, 255, 0.2),
                        stop:1 {CYBERPUNK_THEME["background"]});
                    color: {CYBERPUNK_THEME["neon_blue"]};
                    border: 2px solid {CYBERPUNK_THEME["neon_blue"]};
                    border-bottom: 3px solid {CYBERPUNK_THEME["neon_blue"]};
                }}
                
                QTabBar::tab:hover:!selected {{
                    background-color: rgba(0, 255, 255, 0.15);
                    color: {CYBERPUNK_THEME["highlight"]};
                    border: 2px solid {CYBERPUNK_THEME["highlight"]};
                    border-bottom: none;
                }}
                
                QTabBar::tab:!selected {{
                    margin-top: 3px;
                }}
                """
            }
            
            # Return component-specific style if available, otherwise return base style
            # BUG 2 FIX: Normalize to lowercase so "Dashboard" matches "dashboard"
            return component_styles.get(component_type.lower(), base_style)
            
        except Exception as e:
            logger.error(f"Error generating stylesheet for {component_type}: {e}")
            return ""  # Return empty stylesheet on error
    
    @staticmethod
    def apply_cyberpunk_style(widget: QWidget, *args, **kwargs):
        """Apply cyberpunk style to a widget"""
        try:
            CyberpunkStyle.apply_to_widget(widget, "default")
        except Exception:
            pass
    
    @staticmethod
    def apply_tab_style(widget: QWidget, *args, **kwargs):
        """Apply tab style to a widget"""
        try:
            widget.setStyleSheet(CyberpunkStyle.get_style_sheet("default"))
        except Exception:
            pass
    
    @staticmethod
    def apply_glass_effect(widget: QWidget, alpha=120, *args, **kwargs):
        """Apply glass effect to a widget"""
        try:
            widget.setStyleSheet(f"background-color: rgba(10, 20, 30, {alpha/255});")
        except Exception:
            pass
    
    @staticmethod
    def apply_neon_text(widget: QWidget, *args, **kwargs):
        """Apply neon text effect to a widget"""
        try:
            widget.setStyleSheet(f"color: {CYBERPUNK_THEME['neon_blue']}; font-weight: bold;")
        except Exception:
            pass
    
    @staticmethod
    def apply_neon_effect(widget: QWidget, *args, **kwargs):
        """Apply neon effect to a widget"""
        try:
            glow = CyberpunkEffect.create_glow_effect(CYBERPUNK_THEME["neon_blue"])
            widget.setGraphicsEffect(glow)
        except Exception:
            pass

class CyberpunkRGBBorderWidget(QWidget):
    """Widget with animated RGB border effect"""
    
    def __init__(self, parent=None, border_width=2, border_radius=6):
        super().__init__(parent)
        self.border_width = border_width
        self.border_radius = border_radius
        self.animation_step = 0
        self._border_color = QColor(CYBERPUNK_THEME["neon_blue"])
        self._rgb_border_enabled = True
        self._rgb_border_interval_ms = 30
        
        # Setup update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_animation)
        self._sync_update_timer()

    def _should_rgb_timer_run(self) -> bool:
        if not self._rgb_border_enabled:
            return False
        if not self.isVisible():
            return False
        try:
            window = self.window()
            if window is not None and window.isMinimized():
                return False
        except Exception:
            pass
        return True

    def _sync_update_timer(self):
        try:
            if self._should_rgb_timer_run():
                if not self.update_timer.isActive():
                    self.update_timer.start(self._rgb_border_interval_ms)
            else:
                if self.update_timer.isActive():
                    self.update_timer.stop()
        except Exception:
            pass
    
    def get_border_color(self):
        return self._border_color
        
    def set_border_color(self, color):
        self._border_color = color
        self.update()
        
    def set_rgb_border_enabled(self, enabled):
        """Enable/disable RGB border animation"""
        self._rgb_border_enabled = enabled
        self._sync_update_timer()
            
    def set_border_width(self, width):
        """Set border width"""
        self.border_width = width
        self.update()
        
    # Define the color property for animation
    border_color = pyqtProperty(QColor, get_border_color, set_border_color)
        
    def _update_animation(self):
        """Update the animation state and repaint"""
        self.animation_step = (self.animation_step + 1) % RGB_ANIMATION_STEPS
        
        # Calculate color based on animation step
        colors = CYBERPUNK_THEME["rgb_cycle"]
        num_colors = len(colors)
        
        # Calculate position in the cycle
        color_index_float = (self.animation_step / RGB_ANIMATION_STEPS) * num_colors
        color_index1 = int(color_index_float) % num_colors
        color_index2 = (color_index1 + 1) % num_colors
        
        # Interpolate between the two colors
        color_frac = color_index_float - int(color_index_float)
        color1 = QColor(colors[color_index1])
        color2 = QColor(colors[color_index2])
        
        # Linear interpolation between colors
        r = int(color1.red() * (1 - color_frac) + color2.red() * color_frac)
        g = int(color1.green() * (1 - color_frac) + color2.green() * color_frac)
        b = int(color1.blue() * (1 - color_frac) + color2.blue() * color_frac)
        
        # Update color and trigger repaint
        self._border_color = QColor(r, g, b)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_update_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_update_timer()

    def changeEvent(self, event):
        super().changeEvent(event)
        try:
            if event.type() == QEvent.Type.WindowStateChange:
                self._sync_update_timer()
        except Exception:
            pass
    
    def paintEvent(self, event):
        """Custom paint event to draw animated RGB border"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw the border
        pen = QPen(self._border_color)
        pen.setWidth(self.border_width)
        painter.setPen(pen)
        
        # Draw rounded rectangle border
        rect = self.rect().adjusted(self.border_width // 2, self.border_width // 2, 
                                  -self.border_width // 2, -self.border_width // 2)
        painter.drawRoundedRect(rect, self.border_radius, self.border_radius)

# Particle system for cyberpunk visual effects
class CyberpunkParticle:
    """Particle for cyberpunk visual effects"""
    def __init__(self, x, y, size=3, speed=1, color=None):
        self.x = x
        self.y = y
        self.size = size
        self.speed = speed
        self.color = color or QColor(random.choice(CYBERPUNK_THEME["rgb_cycle"]))
        self.life = 100
        self.decay = random.uniform(0.5, 1.0)
        self.direction = random.uniform(0, 2 * math.pi)
        
    def update(self):
        """Update particle position and life"""
        self.x += math.cos(self.direction) * self.speed
        self.y += math.sin(self.direction) * self.speed
        self.life -= self.decay
        
    def is_alive(self):
        """Check if the particle is still alive"""
        return self.life > 0

class CyberpunkParticleEffect:
    """SOTA 2026: Particle effect wrapper for CyberpunkParticleSystem.
    
    Provides a compatibility layer and additional effect presets.
    """
    
    def __init__(self, max_particles=50, effect_type="spark", *args, **kwargs):
        """Initialize particle effect.
        
        Args:
            max_particles: Maximum number of particles
            effect_type: Type of effect (spark, explosion, trail, glow)
        """
        self._system = None  # Lazy initialization
        self.max_particles = max_particles
        self.effect_type = effect_type
        self._active = False
        self._position = (0, 0)
        
        # Effect presets
        self._presets = {
            "spark": {"count": 5, "decay": 0.05, "speed_range": (1, 3)},
            "explosion": {"count": 20, "decay": 0.1, "speed_range": (3, 8)},
            "trail": {"count": 2, "decay": 0.02, "speed_range": (0.5, 1.5)},
            "glow": {"count": 3, "decay": 0.01, "speed_range": (0.2, 0.5)},
        }
    
    def _ensure_system(self):
        """Ensure particle system is initialized."""
        if self._system is None:
            self._system = CyberpunkParticleSystem(self.max_particles)
    
    def emit(self, x, y, count=None):
        """Emit particles at position.
        
        Args:
            x: X position
            y: Y position
            count: Number of particles (uses preset default if None)
        """
        self._ensure_system()
        preset = self._presets.get(self.effect_type, self._presets["spark"])
        emit_count = count if count is not None else preset["count"]
        self._system.emit(x, y, emit_count)
        self._position = (x, y)
        self._active = True
    
    def update(self):
        """Update all particles."""
        if self._system:
            self._system.update()
            self._active = len(self._system.particles) > 0
    
    def render(self, painter):
        """Render particles using a painter.
        
        Args:
            painter: QPainter or compatible drawing context
        """
        if self._system:
            self._system.render(painter)
    
    def clear(self):
        """Clear all particles."""
        if self._system:
            self._system.particles.clear()
        self._active = False
    
    def is_active(self):
        """Check if effect has active particles."""
        return self._active
    
    def get_particle_count(self):
        """Get current particle count."""
        return len(self._system.particles) if self._system else 0
    
    @staticmethod
    def create(effect_type="spark", max_particles=50, *args, **kwargs):
        """Factory method to create particle effect.
        
        Args:
            effect_type: Type of effect preset
            max_particles: Maximum particles
            
        Returns:
            CyberpunkParticleEffect instance
        """
        return CyberpunkParticleEffect(max_particles=max_particles, effect_type=effect_type)

class CyberpunkParticleSystem:
    """Particle system for cyberpunk visual effects"""
    def __init__(self, max_particles=50):
        self.particles = []
        self.max_particles = max_particles
    
    def emit(self, x, y, count=1):
        """Emit new particles at the specified position"""
        for _ in range(count):
            if len(self.particles) < self.max_particles:
                size = int(random.uniform(1, 5))
                speed = int(random.uniform(1, 3))  # Convert to int range
                self.particles.append(CyberpunkParticle(x, y, size, speed))
    
    def update(self):
        """Update all particles"""
        # Update existing particles
        for particle in self.particles[:]:
            particle.update()
            if not particle.is_alive():
                self.particles.remove(particle)
    
    def draw(self, painter):
        """Draw all particles"""
        for particle in self.particles:
            color = particle.color
            alpha = int(particle.life * 2.55)  # Convert life (0-100) to alpha (0-255)
            color.setAlpha(alpha)
            
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                int(particle.x - particle.size/2), 
                int(particle.y - particle.size/2),
                int(particle.size), 
                int(particle.size)
            )

def initialize_cyberpunk_styles(app=None):
    """Initialize cyberpunk styles for the Kingdom AI system
    
    Args:
        app: QApplication instance (optional)
    """
    try:
        logger.info("Initializing cyberpunk styles for Kingdom AI")
        
        if app is not None:
            # Set the global application stylesheet
            app.setStyleSheet(CyberpunkStyle.get_style_sheet("default"))
            logger.info("Applied cyberpunk theme to Kingdom AI application")
        
    except Exception as e:
        logger.error(f"Failed to initialize cyberpunk styles: {e}")

# Test function for the cyberpunk style
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QLabel, QFrame, QProgressBar
    
    app = QApplication(sys.argv)
    initialize_cyberpunk_styles(app)
    
    window = QMainWindow()
    window.setWindowTitle("Cyberpunk Style Test")
    window.resize(800, 600)
    
    main_widget = CyberpunkRGBBorderWidget(window)
    window.setCentralWidget(main_widget)
    
    layout = QVBoxLayout(main_widget)
    
    # Add a title
    title = QLabel("Kingdom AI Cyberpunk Style Test")
    title.setObjectName("title_label")
    layout.addWidget(title)
    
    # Add a progress bar
    progress = QProgressBar()
    progress.setValue(75)
    layout.addWidget(progress)
    
    # Add a button
    button = QPushButton("Execute Command")
    CyberpunkStyle.apply_to_widget(button, "button")
    layout.addWidget(button)
    
    # Add a frame
    frame = QFrame()
    frame.setObjectName("market_card")
    frame.setMinimumHeight(100)
    frame_layout = QVBoxLayout(frame)
    frame_layout.addWidget(QLabel("Cyberpunk Card Example"))
    CyberpunkStyle.apply_to_widget(frame, "trading")
    layout.addWidget(frame)
    
    window.show()
    sys.exit(app.exec())
