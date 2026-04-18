#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LED Indicator Widget Module for Kingdom AI

This module provides a custom LED indicator widget for visual status feedback
in the Kingdom AI GUI system.
"""

import sys
import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QSizePolicy, QMessageBox, QApplication
)
from PyQt6.QtGui import QPainter, QColor, QLinearGradient
from PyQt6.QtCore import Qt, QSize, QRect

# Configure logger
logger = logging.getLogger(__name__)

class QLedIndicator(QWidget):
    """Custom LED indicator widget with smooth gradients and animation support."""
    
    def __init__(self, parent=None, on_color=QColor('#00FF00'), off_color=QColor('#FF0000'),
                 size=16, shape='circle', initial_state=False):
        """Initialize the LED indicator.
        
        Args:
            parent: Parent widget
            on_color: Color when LED is on (default: green)
            off_color: Color when LED is off (default: red)
            size: Size of the LED in pixels
            shape: Shape of the LED ('circle' or 'square')
            initial_state: Initial state of the LED (True = on, False = off)
        """
        super().__init__(parent)
        self._on_color = on_color
        self._off_color = off_color
        self._size = size
        self._shape = shape.lower()  # 'circle' or 'square'
        self._state = initial_state
        self.setMinimumSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    
    def sizeHint(self):
        """Return the recommended size for the widget."""
        return QSize(self._size, self._size)
    
    def setState(self, state: bool) -> None:
        """Set the LED state (True = on, False = off)."""
        if self._state != state:
            self._state = state
            self.update()
    
    def getState(self) -> bool:
        """Get the current LED state."""
        return self._state
    
    def toggle(self) -> None:
        """Toggle the LED state between on and off."""
        self.setState(not self._state)
    
    def setOnColor(self, color: QColor) -> None:
        """Set the color for the 'on' state."""
        self._on_color = color
        if self._state:
            self.update()
    
    def setOffColor(self, color: QColor) -> None:
        """Set the color for the 'off' state."""
        self._off_color = color
        if not self._state:
            self.update()
    
    def paintEvent(self, event):
        """Handle paint events for the LED indicator."""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            rect = self.rect().adjusted(1, 1, -1, -1)
            
            # Draw background
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(40, 40, 40))
            painter.drawRoundedRect(rect, 3, 3)
            
            # Draw LED
            if self._state:
                # Create gradient using float coordinates
                gradient = QLinearGradient(
                    float(rect.left()), float(rect.top()),
                    float(rect.right()), float(rect.bottom())
                )
                gradient.setColorAt(0, self._on_color.lighter(150))
                gradient.setColorAt(1, self._on_color)
                
                # Set the gradient brush and draw the LED
                painter.setBrush(gradient)
                if self._shape == 'circle':
                    painter.drawEllipse(rect)
                else:
                    painter.drawRect(rect)
            else:
                # Draw off state
                painter.setBrush(self._off_color)
                if self._shape == 'circle':
                    painter.drawEllipse(rect)
                else:
                    painter.drawRect(rect)
        except Exception as e:
            logger.error(f"Error drawing LED: {e}")
            # Continue with minimal rendering even if there's an error

# Demo/test code
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    
    # Create a window with a few LED indicators
    window = QWidget()
    window.setWindowTitle("LED Indicators Demo")
    window.setGeometry(100, 100, 300, 200)
    
    # Create a green LED in 'on' state
    green_led = QLedIndicator(window, QColor('#00FF00'), QColor('#003300'), 
                              size=20, initial_state=True)
    green_led.move(50, 50)
    
    # Create a red LED in 'off' state
    red_led = QLedIndicator(window, QColor('#FF0000'), QColor('#330000'), 
                           size=20)
    red_led.move(100, 50)
    
    # Create a blue square LED
    blue_led = QLedIndicator(window, QColor('#0000FF'), QColor('#000033'), 
                            size=20, shape='square')
    blue_led.move(150, 50)
    
    window.show()
    sys.exit(app.exec())
