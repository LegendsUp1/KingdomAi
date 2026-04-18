"""
Typing indicator widget for chat interfaces.

This widget shows a visual indication that someone is typing a message.
"""

from typing import Optional
import time

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath

from ...core.styles import COLORS, FONTS

class TypingDots(QWidget):
    """Animated typing indicator dots."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # Animation properties
        self.dot_radius = 3
        self.dot_spacing = 8
        self.animation_offset = 0
        self.animation_speed = 0.5  # seconds per cycle
        
        # Set fixed size
        self.setFixedSize(50, 20)
        
        # Animation timer
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.setInterval(50)  # 20 FPS
        
        # Start animation
        self.animation_start_time = 0.0
        self.animation_running = False
        
        # Dot colors
        self.dot_colors = [
            QColor(COLORS['text_secondary']),
            QColor(COLORS['text_secondary']).darker(150),
            QColor(COLORS['text_secondary']).darker(200)
        ]
    
    def start_animation(self):
        """Start the typing animation."""
        if not self.animation_running:
            self.animation_start_time = time.monotonic()
            self.animation_running = True
            self.animation_timer.start()
    
    def stop_animation(self):
        """Stop the typing animation."""
        self.animation_running = False
        self.animation_timer.stop()
        self.update()
    
    def update_animation(self):
        """Update the animation state."""
        if not self.animation_running:
            return
            
        # Update animation offset based on time
        current_time = time.monotonic()
        
        # Calculate animation progress (0-1)
        elapsed = (current_time - self.animation_start_time) % self.animation_speed
        progress = elapsed / self.animation_speed
        
        # Update offset for smooth animation
        self.animation_offset = progress * 10  # Adjust multiplier for speed
        self.update()
    
    def paintEvent(self, event):
        """Paint the typing dots."""
        if not self.isVisible():
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw three dots with animation
        dot_centers = [
            (self.width() // 4, self.height() // 2),
            (self.width() // 2, self.height() // 2),
            (3 * self.width() // 4, self.height() // 2)
        ]
        
        for i, (x, y) in enumerate(dot_centers):
            # Calculate dot scale based on animation
            scale = 1.0
            if self.animation_running:
                # Each dot has a slight delay in animation
                dot_progress = (self.animation_offset + i * 0.2) % 1.0
                # Smooth scaling using sine wave
                scale = 0.5 + 0.5 * abs(2 * dot_progress - 1)
            
            # Set dot color with alpha based on scale
            color = self.dot_colors[i % len(self.dot_colors)]
            color.setAlphaF(0.7 + 0.3 * scale)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            
            # Draw dot with scaling
            radius = self.dot_radius * scale
            painter.drawEllipse(x - radius, y - radius, 
                             2 * radius, 2 * radius)


class TypingIndicator(QWidget):
    """A typing indicator widget that shows who is typing."""
    
    def __init__(self, sender: str, parent=None):
        """Initialize the typing indicator.
        
        Args:
            sender: Name of the person who is typing
            parent: Parent widget
        """
        super().__init__(parent)
        self.sender = sender
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)
        
        # Avatar/icon
        self.avatar = QLabel()
        self.avatar.setFixedSize(24, 24)
        self.avatar.setStyleSheet(
            f"""
            QLabel {{
                background-color: {COLORS['accent']};
                border-radius: 12px;
                color: white;
                font-weight: bold;
                font-size: 12px;
                qproperty-alignment: AlignCenter;
            }}
            """
        )
        self.avatar.setText(sender[0].upper() if sender else "?")
        
        # Text label
        self.text_label = QLabel(f"{sender} is typing" if sender else "Typing...")
        self.text_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-style: italic; font-size: 11px;"
        )
        
        # Typing dots
        self.dots = TypingDots()
        
        # Add widgets to layout
        layout.addWidget(self.avatar)
        layout.addWidget(self.text_label)
        layout.addWidget(self.dots)
        layout.addStretch()
        
        # Set up style
        self.setAutoFillBackground(True)
        self.update_style()
        
        # Start animation
        self.dots.start_animation()
    
    def update_style(self):
        """Update the widget's style."""
        # Set background color
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(COLORS['bg_secondary']).lighter(110))
        self.setPalette(palette)
    
    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        self.dots.start_animation()
    
    def hideEvent(self, event):
        """Handle hide event."""
        super().hideEvent(event)
        self.dots.stop_animation()
    
    def set_sender(self, sender: str):
        """Update the sender name.
        
        Args:
            sender: New sender name
        """
        self.sender = sender
        self.text_label.setText(f"{sender} is typing")
        self.avatar.setText(sender[0].upper() if sender else "?")
    
    def start_typing(self):
        """Start the typing animation."""
        self.dots.start_animation()
        self.show()
    
    def stop_typing(self):
        """Stop the typing animation."""
        self.dots.stop_animation()
        self.hide()
