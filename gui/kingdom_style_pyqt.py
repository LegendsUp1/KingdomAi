from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
#!/usr/bin/env python3
"""
Kingdom AI - PyQt6 Styling

This module provides custom styling elements for the Kingdom AI GUI using PyQt6.
It implements futuristic styling with animated RGB borders and glowing elements.
"""

import os
import time
import math
import random
from typing import Dict, Any, Optional, List, Tuple, Union

from PyQt6.QtWidgets import (
    QFrame, QPushButton, QLabel, QWidget, 
    QVBoxLayout, QHBoxLayout, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QObject, QTimer, QPropertyAnimation, 
    QEasingCurve, QSize, QPoint, QRect, pyqtSignal,
    pyqtProperty, QRectF
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, 
    QRadialGradient, QPainterPath, QBrush, 
    QFont, QPalette
)


class KingdomStyles:
    """Static style definitions for Kingdom AI UI."""
    
    # Color scheme
    COLORS = {
        "frame_bg": "#121212",
        "content_bg": "#1E1E1E",
        "glow": "#00AAFF",
        "hover": "#005599",
        "text": "#FFFFFF",
        "text_secondary": "#AAAAAA",
        "accent": "#00FFAA",
        "error": "#FF3366",
        "success": "#33FF99",
        "warning": "#FFAA33",
        "info": "#33AAFF",
        
        # Component-specific colors
        "trading": "#FF3366",
        "mining": "#33FF99",
        "wallet": "#FFAA33",
        "blockchain": "#33AAFF",
        "ai": "#AA33FF",
        "system": "#FFFFFF",
    }
    
    # Font settings
    FONTS = {
        "header": ("Roboto", 18, "bold"),
        "subheader": ("Roboto", 14, "bold"),
        "normal": ("Roboto", 12, "normal"),
        "small": ("Roboto", 10, "normal"),
        "button": ("Roboto", 12, "bold"),
        "code": ("Cascadia Code", 12, "normal"),
    }
    
    # Border settings
    BORDER = {
        "radius": 10,
        "width": 2,
    }
    
    # Animation settings
    ANIMATION = {
        "duration": 300,  # milliseconds
        "hover_duration": 150,  # milliseconds
    }
    
    @staticmethod
    def get_font(font_type: str = "normal") -> QFont:
        """Get a QFont for the specified font type."""
        font_family, size, weight = KingdomStyles.FONTS.get(
            font_type, KingdomStyles.FONTS["normal"]
        )
        font = QFont(font_family, size)
        if weight == "bold":
            font.setBold(True)
        return font


class RGBAnimation:
    """Animation manager for RGB border effects."""
    
    def __init__(self):
        # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
        self._timer_manager = get_qt_timer_manager()
        # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
        # Start thread-safe animation with 50ms interval
        self._animation_callback_id = "rgb_animation_timer"
        start_timer_safe(self._animation_callback_id, 50, self._update_animations, single_shot=False)
        # Animation callback already set up with start_timer_safe above
        # Thread-safe timer already started above
        
        self.animation_frames = []
        self.start_time = time.time()
    
    def _update_animations(self):
        """Update all active RGB animations."""
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Calculate color based on time
        r = int(127.5 + 127.5 * math.sin(elapsed * 1.1))
        g = int(127.5 + 127.5 * math.sin(elapsed * 1.3))
        b = int(127.5 + 127.5 * math.sin(elapsed * 1.7))
        
        # Update all animations
        for frame in self.animation_frames:
            if hasattr(frame, 'update_rgb_color'):
                frame.update_rgb_color(r, g, b)
    
    def register_frame(self, frame):
        """Register a frame for RGB animation."""
        if frame not in self.animation_frames:
            self.animation_frames.append(frame)
    
    def unregister_frame(self, frame):
        """Unregister a frame from RGB animation."""
        if frame in self.animation_frames:
            self.animation_frames.remove(frame)


# Singleton instance of the RGB animation manager
rgb_animation_manager = RGBAnimation()


class RGBBorderFrame(QFrame):
    """A QFrame with animated RGB border."""
    
    def __init__(self, parent, border_width=2, corner_radius=10, bg_color="#121212"):
        super().__init__(parent)
        
        # Frame properties
        self.border_width = border_width
        self.corner_radius = corner_radius
        self.bg_color = QColor(bg_color)
        self.border_color = QColor(255, 255, 255)  # Initial color, will be animated
        
        # Color scheme
        self.color_scheme = "system"
        self.color_offset = 0
        self.color_frequency = 1.0
        
        # Register with animation manager
        rgb_animation_manager.register_frame(self)
        
        # Create inner frame for content
        self.inner_frame = QFrame(self)
        
        # Layout setup
        layout = QVBoxLayout(self)
        layout.setContentsMargins(border_width, border_width, border_width, border_width)
        layout.addWidget(self.inner_frame)
        
        # Inner frame style
        self.inner_frame.setObjectName("inner_frame")
        self.inner_frame.setStyleSheet(
            f"""
            QFrame#inner_frame {{
                background-color: {bg_color};
                border-radius: {corner_radius - 2}px;
            }}
            """
        )
    
    def set_color_scheme(self, scheme: str):
        """Set the color scheme for the border animation."""
        self.color_scheme = scheme
        
        # Adjust color animation parameters based on scheme
        if scheme == "trading":
            self.color_offset = 0
            self.color_frequency = 1.2
        elif scheme == "mining":
            self.color_offset = 2
            self.color_frequency = 0.8
        elif scheme == "wallet":
            self.color_offset = 4
            self.color_frequency = 1.0
        elif scheme == "blockchain":
            self.color_offset = 6
            self.color_frequency = 1.5
        elif scheme == "ai":
            self.color_offset = 8
            self.color_frequency = 1.3
    
    def update_rgb_color(self, r, g, b):
        """Update the RGB border color based on the animation."""
        # Apply color scheme adjustments
        if self.color_scheme == "trading":
            r = min(255, r * 1.5)
            g = max(0, g * 0.5)
            b = max(0, b * 0.7)
        elif self.color_scheme == "mining":
            r = max(0, r * 0.5)
            g = min(255, g * 1.5)
            b = max(0, b * 0.7)
        elif self.color_scheme == "wallet":
            r = min(255, r * 1.2)
            g = min(255, g * 0.8)
            b = max(0, b * 0.4)
        elif self.color_scheme == "blockchain":
            r = max(0, r * 0.4)
            g = max(0, g * 0.8)
            b = min(255, b * 1.5)
        elif self.color_scheme == "ai":
            r = min(255, r * 0.7)
            g = max(0, g * 0.4)
            b = min(255, b * 1.5)
        
        self.border_color = QColor(r, g, b)
        self.update()  # Trigger repaint
    
    def paintEvent(self, event):
        """Custom paint event to draw the RGB border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw border
        path = QPainterPath()
        rect = QRectF(
            self.border_width / 2,
            self.border_width / 2,
            self.width() - self.border_width,
            self.height() - self.border_width
        )
        path.addRoundedRect(rect, self.corner_radius, self.corner_radius)
        
        pen = QPen(self.border_color)
        pen.setWidth(self.border_width)
        painter.setPen(pen)
        painter.drawPath(path)


class GlowButton(QPushButton):
    """A QPushButton with glowing effect on hover."""
    
    def __init__(self, parent, text="", clicked_callback=None, 
                 glow_color="#00AAFF", hover_color="#005599", **kwargs):
        super().__init__(text, parent)
        
        # Button properties
        self.glow_color = QColor(glow_color)
        self.hover_color = QColor(hover_color)
        self.is_hovering = False
        self.glow_strength = 0.0  # 0.0 to 1.0
        
        # Connect clicked signal if callback provided
        if clicked_callback:
            self.clicked.connect(clicked_callback)
        
        # Setup animations
        self.glow_animation = QPropertyAnimation(self, b"glowStrength")
        self.glow_animation.setDuration(200)
        self.glow_animation.setStartValue(0.0)
        self.glow_animation.setEndValue(1.0)
        
        # Apply styling
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(KingdomStyles.get_font("button"))
        
        # Setup style
        self._update_style()
    
    # Define property for animation
    @pyqtProperty(float)
    def glowStrength(self):
        return self.glow_strength
    
    @glowStrength.setter
    def glowStrength(self, value):
        self.glow_strength = value
        self._update_style()
        self.update()
    
    def enterEvent(self, event):
        """Handle mouse enter event."""
        self.is_hovering = True
        self.glow_animation.setDirection(QPropertyAnimation.Direction.Forward)
        self.glow_animation.start()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave event."""
        self.is_hovering = False
        self.glow_animation.setDirection(QPropertyAnimation.Direction.Backward)
        self.glow_animation.start()
        super().leaveEvent(event)
    
    def _update_style(self):
        """Update the button style based on current state."""
        # Interpolate between normal and hover colors based on glow strength
        bg_color = self._interpolate_color(
            QColor(KingdomStyles.COLORS["frame_bg"]),
            self.hover_color,
            self.glow_strength
        )
        
        # Set button style with current glow effect
        glow_radius = int(10 * self.glow_strength)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {bg_color.name()};
                color: {KingdomStyles.COLORS["text"]};
                border: 2px solid {self.glow_color.name()};
                border-radius: 5px;
                padding: 5px 15px;
            }}
            QPushButton:hover {{
                background-color: {self.hover_color.name()};
            }}
            QPushButton:pressed {{
                background-color: {self.glow_color.name()};
                color: #000000;
            }}
            """
        )
    
    def _interpolate_color(self, color1, color2, factor):
        """Interpolate between two colors based on a factor (0.0 to 1.0)."""
        r = int(color1.red() + (color2.red() - color1.red()) * factor)
        g = int(color1.green() + (color2.green() - color1.green()) * factor)
        b = int(color1.blue() + (color2.blue() - color1.blue()) * factor)
        return QColor(r, g, b)
    
    def paintEvent(self, event):
        """Custom paint event to add glow effect."""
        super().paintEvent(event)
        
        if self.glow_strength > 0.01:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Create glow effect
            glow_size = int(10 * self.glow_strength)
            if glow_size > 0:
                # Draw glow behind the button
                glow = QRadialGradient(
                    self.rect().center(),
                    self.width() / 2 + glow_size
                )
                glow_color = QColor(self.glow_color)
                glow_color.setAlpha(int(120 * self.glow_strength))
                glow.setColorAt(0, glow_color)
                glow_color.setAlpha(0)
                glow.setColorAt(1, glow_color)
                
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(glow)
                painter.drawRoundedRect(
                    self.rect().adjusted(-glow_size, -glow_size, glow_size, glow_size),
                    5 + glow_size,
                    5 + glow_size
                )


class FuturisticLabel(QLabel):
    """A QLabel with futuristic styling."""
    
    def __init__(self, parent=None, text="", accent_color=None, **kwargs):
        super().__init__(text, parent)
        
        # Default accent color if none provided
        if accent_color is None:
            accent_color = KingdomStyles.COLORS["accent"]
        self.accent_color = QColor(accent_color)
        
        # Apply styling
        self.setFont(KingdomStyles.get_font("normal"))
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {KingdomStyles.COLORS["text"]};
                padding: 2px;
                border-bottom: 1px solid {self.accent_color.name()};
            }}
            """
        )


def apply_kingdom_style_to_widget(widget, style_type="default"):
    """Apply Kingdom AI styling to any widget."""
    if style_type == "dark":
        widget.setStyleSheet(
            f"""
            QWidget {{
                background-color: {KingdomStyles.COLORS["frame_bg"]};
                color: {KingdomStyles.COLORS["text"]};
            }}
            QLabel {{
                color: {KingdomStyles.COLORS["text"]};
            }}
            QPushButton {{
                background-color: {KingdomStyles.COLORS["frame_bg"]};
                color: {KingdomStyles.COLORS["text"]};
                border: 1px solid {KingdomStyles.COLORS["glow"]};
                border-radius: 5px;
                padding: 5px 15px;
            }}
            QPushButton:hover {{
                background-color: {KingdomStyles.COLORS["hover"]};
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {KingdomStyles.COLORS["content_bg"]};
                color: {KingdomStyles.COLORS["text"]};
                border: 1px solid {KingdomStyles.COLORS["glow"]};
                border-radius: 3px;
                padding: 3px;
            }}
            QProgressBar {{
                border: 1px solid {KingdomStyles.COLORS["glow"]};
                border-radius: 5px;
                background-color: {KingdomStyles.COLORS["content_bg"]};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {KingdomStyles.COLORS["glow"]};
                width: 10px;
            }}
            """
        )
    elif style_type == "light":
        # Light theme styling
        pass  # Implement if needed
    else:
        # Default styling
        widget.setStyleSheet(
            f"""
            QWidget {{
                background-color: {KingdomStyles.COLORS["frame_bg"]};
                color: {KingdomStyles.COLORS["text"]};
            }}
            """
        )

    return widget
