from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
#!/usr/bin/env python3
"""
Kingdom AI - Enhanced Styles Module

This module provides futuristic UI components with RGB animated borders
and glowing effects for the Kingdom AI application. It works with PyQt6
and preserves all existing functionality while enhancing visual presentation.
"""

import sys
import time
import threading
import colorsys
from PyQt6.QtWidgets import (
    QFrame, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, 
    pyqtProperty, QRect, QPoint, QSize
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient,
    QFont, QPainterPath, QRadialGradient
)

# RGB color cycling
class RGBColorManager:
    """Manages RGB color cycling for animated components."""
    
    def __init__(self, update_interval_ms=30):
        """Initialize the RGB color manager.
        
        Args:
            update_interval_ms: Update interval in milliseconds
        """
        self.update_interval = update_interval_ms
        self.subscribers = []
        self._hue = 0
        self.running = False
        self.timer = None
        self.animation_thread = None
    
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
            self._hue = (self._hue + 0.01) % 1.0
            
            # Generate RGB color from HSV (hue, saturation, value)
            r, g, b = colorsys.hsv_to_rgb(self._hue, 1.0, 1.0)
            
            # Convert to QColor
            color = QColor(int(r*255), int(g*255), int(b*255))
            
            # Notify all subscribers
            for callback in self.subscribers:
                try:
                    callback(color)
                except Exception as e:
                    print(f"Error in RGB animation callback: {e}")
            
            # Sleep for update interval
            time.sleep(self.update_interval / 1000.0)

# Create global singleton instance
rgb_color_manager = RGBColorManager()

class AnimatedRGBBorderFrame(QFrame):
    """Frame with animated RGB border effect."""
    
    def __init__(self, parent=None, border_radius=15, border_width=3):
        """Initialize the RGB border frame.
        
        Args:
            parent: Parent widget
            border_radius: Radius of the corners
            border_width: Width of the glowing border
        """
        super().__init__(parent)
        self.parent = parent
        self.border_radius = border_radius
        self.border_width = border_width
        self._current_color = QColor(0, 160, 255)  # Default blue
        
        # Enable transparency
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create inner content widget
        self._setup_inner_frame()
        
        # Subscribe to RGB color updates
        rgb_color_manager.subscribe(self._update_border_color)
    
    def _setup_inner_frame(self):
        """Set up the inner frame for content."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(
            self.border_width + 5,
            self.border_width + 5, 
            self.border_width + 5,
            self.border_width + 5
        )
        
        # Create inner frame with dark background
        self.inner_frame = QFrame(self)
        self.inner_frame.setStyleSheet(
            f"background-color: rgba(20, 25, 35, 200); border-radius: {self.border_radius-5}px;"
        )
        
        self.layout.addWidget(self.inner_frame)
    
    def _update_border_color(self, color):
        """Update the border color.
        
        Args:
            color: QColor object for the new border color
        """
        self._current_color = color
        self.update()
    
    def paintEvent(self, event):
        """Override paint event to draw the animated border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create path for rounded rectangle
        rect = self.rect().adjusted(
            self.border_width//2,
            self.border_width//2,
            -self.border_width//2,
            -self.border_width//2
        )
        
        # Draw glowing border
        pen = QPen(self._current_color)
        pen.setWidth(self.border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, self.border_radius, self.border_radius)
        
        # Add glow effect
        glow = QPainterPath()
        glow.addRoundedRect(rect, self.border_radius, self.border_radius)
        gradient = QRadialGradient(rect.center(), rect.width()//2)
        
        # Create glow colors from current color
        glow_color = QColor(self._current_color)
        glow_color.setAlpha(80)
        transparent = QColor(self._current_color)
        transparent.setAlpha(0)
        
        gradient.setColorAt(0.8, transparent)
        gradient.setColorAt(0.9, glow_color)
        gradient.setColorAt(1.0, transparent)
        
        # Paint the glow
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawPath(glow)
    
    def add_widget(self, widget, stretch=0):
        """Add a widget to the inner frame.
        
        Args:
            widget: Widget to add
            stretch: Stretch factor
        """
        if hasattr(self.inner_frame, 'layout') and self.inner_frame.layout() is not None:
            self.inner_frame.layout().addWidget(widget, stretch)
        else:
            layout = QVBoxLayout(self.inner_frame)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.addWidget(widget, stretch)
    
    def add_layout(self, layout):
        """Add a layout to the inner frame.
        
        Args:
            layout: Layout to add
        """
        if hasattr(self.inner_frame, 'layout') and self.inner_frame.layout() is not None:
            old_layout = self.inner_frame.layout()
            # Transfer items from old layout to new layout
            while old_layout.count():
                item = old_layout.takeAt(0)
                layout.addItem(item)
            # Remove old layout
            QWidget().setLayout(old_layout)
            
        self.inner_frame.setLayout(layout)
        
    def destroy(self):
        """Clean up resources before destroying the frame."""
        rgb_color_manager.unsubscribe(self._update_border_color)
        super().destroy()


class GlowButton(QPushButton):
    """Button with animated glow effect."""
    
    def __init__(self, parent=None, text="", icon=None):
        """Initialize the glowing button.
        
        Args:
            parent: Parent widget
            text: Button text
            icon: Optional icon
        """
        super().__init__(text, parent)
        self._hovered = False
        self._animation_offset = 0.0
        self._glow_color = QColor(0, 160, 255)  # Default blue
        
        # Style button
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 40, 60, 200);
                color: #eef;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: rgba(40, 60, 90, 230);
            }
            
            QPushButton:pressed {
                background-color: rgba(20, 30, 50, 230);
            }
        """)
        
        if icon:
            self.setIcon(icon)
        
        # Setup animation timer
        # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
        self._timer_manager = get_qt_timer_manager()
        # Start thread-safe animation with 50ms interval
        self._animation_callback_id = "enhanced_animation_timer"
        start_timer_safe(self._animation_callback_id, 50, self._update_animation, single_shot=False)
        # Thread-safe timer already started above
        
        # Subscribe to RGB color manager
        rgb_color_manager.subscribe(self._update_glow_color)
    
    def _update_glow_color(self, color):
        """Update the glow color.
        
        Args:
            color: QColor object for the new glow color
        """
        self._glow_color = color
        self.update()
    
    def _update_animation(self):
        """Update animation state."""
        self._animation_offset = (self._animation_offset + 0.05) % (2 * 3.14159)
        self.update()
    
    def enterEvent(self, event):
        """Handle mouse enter event."""
        self._hovered = True
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave event."""
        self._hovered = False
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        """Override paint event to draw button with glow."""
        super().paintEvent(event)
        
        if self._hovered:
            # Add glow effect when hovered
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw glowing border
            glow_strength = (math.sin(self._animation_offset) + 1.5) * 0.4
            glow_color = QColor(self._glow_color)
            glow_color.setAlpha(int(120 * glow_strength))
            
            rect = self.rect().adjusted(2, 2, -2, -2)
            pen = QPen(glow_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 8, 8)
    
    def destroy(self):
        """Clean up resources before destroying the button."""
        # Stop thread-safe timer
        if hasattr(self, "_animation_callback_id"):
            stop_timer_safe(self._animation_callback_id)
        rgb_color_manager.unsubscribe(self._update_glow_color)
        super().destroy()


class StatusBar(AnimatedRGBBorderFrame):
    """Status bar with animated RGB border."""
    
    def __init__(self, parent=None, border_radius=8, border_width=2):
        """Initialize the status bar.
        
        Args:
            parent: Parent widget
            border_radius: Radius of the corners
            border_width: Width of the glowing border
        """
        super().__init__(parent, border_radius, border_width)
        
        # Create layout for status elements
        layout = QHBoxLayout(self.inner_frame)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Status label
        self.status_label = QLabel("System Ready", self.inner_frame)
        self.status_label.setStyleSheet("color: #00ffff; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # Add spacer
        layout.addStretch(1)
        
        # Additional status indicators can be added here
        self.indicators = {}
    
    def add_indicator(self, name, default_text="", default_color="#00ffff"):
        """Add a status indicator.
        
        Args:
            name: Unique name for the indicator
            default_text: Default indicator text
            default_color: Default indicator color
        """
        indicator = QLabel(default_text, self.inner_frame)
        indicator.setStyleSheet(f"color: {default_color}; font-weight: bold;")
        self.inner_frame.layout().insertWidget(
            self.inner_frame.layout().count() - 1,  # Insert before stretch
            indicator
        )
        self.indicators[name] = indicator
        return indicator
    
    def update_status(self, text, color="#00ffff"):
        """Update the main status text.
        
        Args:
            text: Status text
            color: Text color
        """
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        
    def update_indicator(self, name, text, color="#00ffff"):
        """Update a specific indicator.
        
        Args:
            name: Indicator name
            text: New indicator text
            color: Text color
        """
        if name in self.indicators:
            self.indicators[name].setText(text)
            self.indicators[name].setStyleSheet(f"color: {color}; font-weight: bold;")

# Start the color manager on module import
if not rgb_color_manager.running:
    rgb_color_manager.start()
