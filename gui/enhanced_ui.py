#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced UI components for the Kingdom AI GUI.
Provides custom-styled widgets with advanced visual effects.
"""

import logging
import math
import sys
import os
from typing import Optional

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import utils if available
try:
    from utils.logger import setup_logger
    setup_logger()
except ImportError:
    # Fallback logging setup
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Set up logging
logger = logging.getLogger(__name__)

# Import PyQt6 components - NO FALLBACKS as per system requirements
try:
    from PyQt6.QtWidgets import (
        QWidget, QFrame, QPushButton, QLabel, QVBoxLayout,
        QHBoxLayout, QGraphicsDropShadowEffect
    )
    from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint, QTimer
    from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient
    
    logger.info("PyQt6 components loaded successfully")
except ImportError:
    logger.critical("PyQt6 is required but not available - halting system")
    raise SystemExit("Critical dependency PyQt6 not available")
# PyQt6 Enhanced UI Components

class EnhancedFrame(QFrame):
    """
    Enhanced frame component with animated borders, shadows and advanced styling.
    """
    
    def __init__(self, parent: Optional[QWidget] = None, title: str = "", **kwargs):
        """
        Initialize the enhanced frame.
        
        Args:
            parent: Parent widget
            title: Title for the frame
            **kwargs: Additional styling parameters
        """
        super().__init__(parent)
        
        # Store parameters
        self.title = title
        self.kwargs = kwargs
        
        # Configure frame appearance
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setLineWidth(2)
        self.setMidLineWidth(1)
        
        # Apply shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)
        
        # Set up layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(5)
        
        # Add title if provided
        if title:
            self.title_label = QLabel(title)
            font = QFont()
            font.setBold(True)
            font.setPointSize(12)
            self.title_label.setFont(font)
            self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.title_label)
            
        # Setup animation for border color
        self.border_animation = None
        self._border_color = QColor(0, 120, 215)
        self.setupBorderAnimation()
        
    def setupBorderAnimation(self):
        """Setup animation for the border color."""
        # Only set up animation if requested
        if self.kwargs.get("animate_border", False):
            self.border_animation = QPropertyAnimation(self, b"border_color")
            self.border_animation.setDuration(2000)
            self.border_animation.setStartValue(QColor(0, 120, 215))  # Start with blue
            self.border_animation.setEndValue(QColor(0, 200, 83))     # End with green
            self.border_animation.setLoopCount(-1)  # Loop infinitely
            self.border_animation.start()
            
    def getBorderColor(self) -> QColor:
        """Get the current border color."""
        return self._border_color
    
    def setBorderColor(self, color: QColor):
        """Set the border color and trigger repaint."""
        self._border_color = color
        self.update()
    
    # Define the border_color property for animation
    border_color = pyqtProperty(QColor, getBorderColor, setBorderColor)
    
    def paintEvent(self, event):
        """Custom paint event to draw styled borders."""
        super().paintEvent(event)
        
        if self.kwargs.get("custom_border", True):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            pen = QPen(self._border_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 5, 5)
                
class GlowButton(QPushButton):
    """
    Button with glow effect and custom animation.
    """
    
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        """
        Initialize the glow button.
        
        Args:
            text: Button text
            parent: Parent widget
        """
        super().__init__(text, parent)
        
        # Configure appearance
        self.setMinimumHeight(40)
        font = QFont()
        font.setBold(True)
        self.setFont(font)
        
        # Initialize properties
        self._glow_radius = 0
        self._base_color = QColor(0, 120, 215)  # Default blue
        self._hover_color = QColor(0, 180, 250)  # Lighter blue
        self._pressed = False
        self._hovered = False
        
        # Setup animations
        self.glow_animation = QPropertyAnimation(self, b"glow_radius")
        self.glow_animation.setDuration(1000)
        self.glow_animation.setStartValue(0)
        self.glow_animation.setEndValue(10)
        self.glow_animation.setLoopCount(-1)
        self.glow_animation.start()
        
        # Enable mouse tracking for hover events
        self.setMouseTracking(True)
    def getGlowRadius(self) -> int:
        """Get current glow radius."""
        return self._glow_radius
    
    def setGlowRadius(self, radius: int):
        """Set glow radius and update."""
        self._glow_radius = radius
        self.update()
    
    # Define property for animation
    glow_radius = pyqtProperty(int, getGlowRadius, setGlowRadius)
    
    def enterEvent(self, event):
        """Handle mouse enter events."""
        self._hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave events."""
        self._hovered = False
        self.update()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        self._pressed = True
        self.update()
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)
    
    def paintEvent(self, event):
        """Custom paint event to draw the button with glow effect."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Determine button color based on state
        if self._pressed:
            color = self._base_color.darker(120)
        elif self._hovered:
            color = self._hover_color
        else:
            color = self._base_color
        
        # Draw glow if radius > 0
        if self._glow_radius > 0:
            glow_color = QColor(color)
            glow_color.setAlpha(100)
            shadow = QColor(glow_color)
            
            for i in range(self._glow_radius):
                shadow.setAlpha(100 - (i * 10))
                painter.setPen(QPen(shadow, i * 0.5))
                painter.drawRoundedRect(self.rect().adjusted(i, i, -i, -i), 5, 5)
        
        # Draw button background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 5, 5)
        
        # Draw text
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
    
class AnimatedLabel(QLabel):
    """
    Label with text animation effects.
    """
    
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        """
        Initialize animated label.
        
        Args:
            text: Label text
            parent: Parent widget
        """
        super().__init__(text, parent)
        
        # Initialize properties
        self._displayed_text = ""
        self._full_text = text
        self._char_index = 0
        self._animation_active = False
        
        # Setup timer for animation
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate_text)
        
    def setText(self, text: str):
        """Override setText to enable animation."""
        self._full_text = text
        if not self._animation_active:
            self._start_animation()
        
    def _start_animation(self):
        """Start the text animation."""
        self._animation_active = True
        self._displayed_text = ""
        self._char_index = 0
        self._timer.start(50)  # Update every 50ms
        
    def _animate_text(self):
        """Animate text by revealing one character at a time."""
        if self._char_index < len(self._full_text):
            self._displayed_text += self._full_text[self._char_index]
            super().setText(self._displayed_text)
            self._char_index += 1
        else:
            self._animation_active = False
            self._timer.stop()
    
# Enhanced UI components exported for use in other modules
__all__ = ['EnhancedFrame', 'GlowButton', 'AnimatedLabel']
