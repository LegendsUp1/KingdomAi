"""
Cyberpunk Base Widget Classes for Trading Interface

This module contains base widget classes that provide common functionality
for all trading widgets with advanced cyberpunk styling.
"""
from typing import Any, Dict, Optional, List, Union
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QRect, QEasingCurve, QSize
from PyQt6.QtGui import QColor, QPalette, QPainter, QBrush, QLinearGradient, QPen, QFont, QGradient
import logging
logger = logging.getLogger(__name__)
import time
import math
import random

# Import cyberpunk styling components if available
try:
    from gui.cyberpunk_style import (
        CyberpunkStyle, CyberpunkEffect, CyberpunkRGBBorderWidget,
        CyberpunkParticleSystem, CYBERPUNK_THEME
    )
    has_cyberpunk = True
except ImportError:
    logger.warning("Cyberpunk styling components not available - using fallback styling")
    has_cyberpunk = False
    # Define minimal fallback theme
    CYBERPUNK_THEME = {
        "background": "#0F111A",
        "foreground": "#00FFFF",
        "accent": "#FF00FF",
        "positive": "#00FF66",
        "negative": "#FF3366",
        "neutral": "#33CCFF",
        "rgb_cycle": ["#FF00FF", "#00FFFF", "#00FF66", "#FFFF00"]
    }
    
    # Minimal fallback classes if cyberpunk_style.py is not available
    class CyberpunkStyle:
        @staticmethod
        def apply_to_widget(widget, widget_type): pass
    
    class CyberpunkEffect:
        @staticmethod
        def create_glow_effect(color, intensity=5, spread=5): 
            effect = QGraphicsDropShadowEffect()
            effect.setColor(color)
            effect.setBlurRadius(spread)
            effect.setOffset(0, 0)
            return effect
    
    class CyberpunkRGBBorderWidget(QWidget):
        pass
    
    class CyberpunkParticleSystem:
        def __init__(self, max_particles=100): pass
        def emit(self, x, y, count): pass
        def update(self): pass
        def draw(self, painter): pass

# Connect to Redis Quantum Nexus - required with no fallbacks
def connect_to_redis():
    """Connect to Redis Quantum Nexus - required with no fallbacks"""
    try:
        import redis
        redis_client = redis.Redis(
            host="localhost", 
            port=6380,  # Required specific port
            password="QuantumNexus2025",  # Required password
            decode_responses=True
        )
        # Test connection - must succeed
        if not redis_client.ping():
            logger.critical("Failed to connect to Redis Quantum Nexus - connection unhealthy")
            raise ConnectionError("Redis Quantum Nexus connection unhealthy")
            
        logger.info("Successfully connected to Redis Quantum Nexus")
        return redis_client
    except Exception as e:
        logger.critical(f"Failed to connect to Redis Quantum Nexus: {e}")
        # No fallbacks allowed - must halt system
        raise ConnectionError(f"Redis Quantum Nexus connection failed: {e}")

# Global Redis client - enforced connection with no fallbacks
REDIS_CLIENT = connect_to_redis()  # This will raise exception if connection fails

class ResizableWidget(QWidget):
    """Base resizable widget with minimum size constraints and cyberpunk styling."""
    
    def __init__(self, parent=None, min_width=400, min_height=300):
        """Initialize the resizable widget.
        
        Args:
            parent: Parent widget
            min_width: Minimum width in pixels
            min_height: Minimum height in pixels
        """
        super().__init__(parent)
        self.setMinimumSize(min_width, min_height)
        
        # Apply cyberpunk styling if available
        if has_cyberpunk:
            CyberpunkStyle.apply_to_widget(self, "resizable_widget")

class BaseWidget(CyberpunkRGBBorderWidget if has_cyberpunk else QWidget):
    """
    Base class for all trading widgets with common cyberpunk functionality.
    Features animated RGB borders, glow effects, and particle animations.
    """
    # Signal emitted when data is updated
    data_updated = pyqtSignal(dict)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._initialized = False
        self._data = {}
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update_timeout)
        self._last_update_time = 0
        
        # Cyberpunk styling elements
        self._rgb_index = 0
        self._animations_enabled = True
        self._animation_interval_ms = 50
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._update_animation)
        self._sync_animation_timer()
        
        # Create particle system for animations
        self.particle_system = CyberpunkParticleSystem(max_particles=50) if has_cyberpunk else None
        
        # Redis client for data connectivity - required with no fallback
        self.redis_client = REDIS_CLIENT
        if not self.redis_client:
            logger.critical("Redis Quantum Nexus connection not available - critical error")
            # In production, the system would halt here
            
        self._init_ui()
        self._initialized = True
    
    def _init_ui(self) -> None:
        """Initialize the user interface components with cyberpunk styling."""
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(4, 4, 4, 4)  # Slightly larger margins for RGB border effect
        self.layout().setSpacing(4)
        
        # Apply cyberpunk base styling
        background_color = QColor(CYBERPUNK_THEME['background'])
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, background_color)
        palette.setColor(QPalette.ColorRole.WindowText, QColor(CYBERPUNK_THEME['foreground']))
        self.setPalette(palette)
        
        # Apply glow effect to widget if cyberpunk styling is available
        if has_cyberpunk:
            glow = CyberpunkEffect.create_glow_effect(
                QColor(CYBERPUNK_THEME['accent']), intensity=10, spread=5
            )
            self.setGraphicsEffect(glow)
            
        # Set cyberpunk font if available
        font = QFont("Orbitron", 9)  # Cyberpunk style font
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
    
    def _update_animation(self):
        """Update RGB animation for cyberpunk effects"""
        if has_cyberpunk:
            # Cycle through RGB colors
            colors = CYBERPUNK_THEME["rgb_cycle"]
            self._rgb_index = (self._rgb_index + 1) % len(colors)
            
            # Update particle animations if available
            if hasattr(self, "particle_system") and self.particle_system:
                self.particle_system.update()
            
            # Trigger repaint for animation effects
            self.update()

    def _should_animation_timer_run(self) -> bool:
        if not getattr(self, '_animations_enabled', True):
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

    def _sync_animation_timer(self) -> None:
        try:
            timer = getattr(self, '_animation_timer', None)
            if timer is None:
                return

            if has_cyberpunk and self._should_animation_timer_run():
                if not timer.isActive():
                    timer.start(getattr(self, '_animation_interval_ms', 50))
            else:
                if timer.isActive():
                    timer.stop()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_animation_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_animation_timer()

    def changeEvent(self, event):
        super().changeEvent(event)
        self._sync_animation_timer()
    
    def update_data(self, data: Dict[str, Any]) -> None:
        """
        Update the widget with new data and cyberpunk animation effects.
        
        Args:
            data: Dictionary containing the data to display
        """
        try:
            previous_data = self._data.copy() if self._data else {}
            self._data = data
            self._update_ui()
            self.data_updated.emit(data)
            self._last_update_time = time.time()
            
            # Add particle effect for data updates if cyberpunk styling is available
            if has_cyberpunk and hasattr(self, "particle_system") and self.particle_system:
                # Emit particles when data changes significantly
                if previous_data != data:
                    # Emit particles at widget center
                    self.particle_system.emit(
                        self.width() / 2, 
                        self.height() / 2, 
                        10  # Number of particles
                    )
                    
        except Exception as e:
            logger.error(f"Error updating widget data: {e}", exc_info=True)
            self._show_error(f"Failed to update data: {str(e)}")
    
    def _update_ui(self) -> None:
        """Update the UI components with current data."""
        raise NotImplementedError("Subclasses must implement _update_ui")
    
    def clear(self) -> None:
        """Clear all data from the widget with cyberpunk animation effect."""
        self._data = {}
        self._update_ui()
        
        # Add cyberpunk reset animation
        if has_cyberpunk and hasattr(self, "particle_system") and self.particle_system:
            # Emit particles in a circle pattern for reset effect
            for angle in range(0, 360, 30):  # 12 points around a circle
                radius = min(self.width(), self.height()) / 3
                x = self.width() / 2 + radius * math.cos(math.radians(angle))
                y = self.height() / 2 + radius * math.sin(math.radians(angle))
                self.particle_system.emit(x, y, 3)  # 3 particles per point
    
    def start_auto_update(self, interval_ms: int = 1000) -> None:
        """
        Start automatic updates at the specified interval.
        
        Args:
            interval_ms: Update interval in milliseconds
        """
        self._update_timer.start(interval_ms)
    
    def stop_auto_update(self) -> None:
        """Stop automatic updates."""
        self._update_timer.stop()
    
    def _on_update_timeout(self) -> None:
        """Handle update timer timeout."""
        if self._data:
            self.update_data(self._data)
    
    def _show_error(self, message: str) -> None:
        """Display an error message to the user with cyberpunk styling."""
        error_box = QMessageBox(self)
        error_box.setIcon(QMessageBox.Icon.Critical)
        error_box.setWindowTitle("System Error")
        error_box.setText(message)
        
        # Apply cyberpunk styling to error dialog
        error_box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {CYBERPUNK_THEME['background']};
                color: {CYBERPUNK_THEME['negative']};
                border: 2px solid {CYBERPUNK_THEME['negative']};
            }}
            QLabel {{
                color: {CYBERPUNK_THEME['negative']};
                font-family: 'Orbitron', monospace;
            }}
            QPushButton {{
                background-color: {CYBERPUNK_THEME['background']};
                color: {CYBERPUNK_THEME['accent']};
                border: 1px solid {CYBERPUNK_THEME['accent']};
                padding: 5px 15px;
                font-family: 'Orbitron', monospace;
            }}
            QPushButton:hover {{
                background-color: {CYBERPUNK_THEME['accent']};
                color: {CYBERPUNK_THEME['background']};
            }}
        """)
        
        # Log the error to Redis Quantum Nexus if connected
        if hasattr(self, "redis_client") and self.redis_client:
            try:
                self.redis_client.lpush("kingdom:errors", f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")
                self.redis_client.ltrim("kingdom:errors", 0, 999)  # Keep last 1000 errors
            except Exception as e:
                logger.error(f"Failed to log error to Redis: {e}")
                
        error_box.exec()
    
    def set_theme(self, theme: Dict[str, Any]) -> None:
        """
        Apply a cyberpunk theme to the widget with advanced styling effects.
        
        Args:
            theme: Dictionary containing theme properties
        """
        if not self._initialized:
            return
            
        try:
            # Merge provided theme with cyberpunk theme
            merged_theme = CYBERPUNK_THEME.copy()
            for key, value in theme.items():
                merged_theme[key] = value
                
            palette = self.palette()
            
            # Set background color with cyberpunk styling
            if 'background' in merged_theme:
                palette.setColor(QPalette.ColorRole.Window, QColor(merged_theme['background']))
            
            # Set text color with cyberpunk styling
            if 'foreground' in merged_theme:
                palette.setColor(QPalette.ColorRole.WindowText, QColor(merged_theme['foreground']))
                
            # Set other palette colors for cyberpunk style
            palette.setColor(QPalette.ColorRole.Base, QColor(merged_theme['background']).darker(110))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(merged_theme['background']).darker(120))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(merged_theme['accent']))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(merged_theme['background']))
            
            self.setPalette(palette)
            self.setAutoFillBackground(True)
            
            # Update glow effect with theme color
            if has_cyberpunk:
                glow = CyberpunkEffect.create_glow_effect(
                    QColor(merged_theme['accent']), intensity=10, spread=5
                )
                self.setGraphicsEffect(glow)
            
        except Exception as e:
            logger.error(f"Error applying cyberpunk theme: {e}", exc_info=True)
