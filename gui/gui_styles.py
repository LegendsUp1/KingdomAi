from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager
#!/usr/bin/env python3
"""Kingdom AI - Style System

This module provides the styling definitions for the Kingdom AI GUI.
It includes a modern, dark theme with futuristic styling suitable for
the high-tech interface of the application. Fully supports PyQt6 with tkinter fallback.
"""

import logging
import threading
import time
import colorsys
from typing import Dict, Any, Optional, Callable, List, Tuple, Union, Type

# PyQt6 imports for proper animation - 2025 MODERN APPROACH (no flags needed)
try:
    from PyQt6.QtCore import QPropertyAnimation, pyqtProperty, pyqtSignal, QTimer
    from PyQt6.QtGui import QPainter, QColor, QPen
    from PyQt6.QtWidgets import QFrame
except ImportError:
    # Graceful fallback - will be handled at class level
    pass

logger = logging.getLogger(__name__)

# Define constant color values used throughout the application
# These are defined only once to prevent redefinition errors
ACCENT_COLOR = '#00A0FF'      # Primary accent color
ACCENT_COLOR_DARK = '#0080CC' # Darker variant of accent color
ACCENT_COLOR_LIGHT = '#66C7FF' # Lighter variant of accent color
BACKGROUND_COLOR = '#121212'  # Dark background
CARD_COLOR = '#1E1E1E'        # Slightly lighter than background for cards/panels
TEXT_COLOR = '#FFFFFF'        # Primary text color
SECONDARY_TEXT = '#B0B0B0'    # Secondary/muted text
ERROR_COLOR = '#FF5252'       # Error messages
SUCCESS_COLOR = '#4CAF50'     # Success indicators
WARNING_COLOR = '#FFC107'     # Warning indicators
BORDER_COLOR = '#333333'      # Border color
HOVER_COLOR = '#2C2C2C'       # Hover state color

# Set up framework detection flags - must be defined before any conditional imports
pyqt6_available = False
tkinter_available = False

# Import PyQt6 modules - MANDATORY for Kingdom AI (strict requirement with no fallbacks)
try:
    from PyQt6.QtWidgets import QApplication, QStyleFactory, QFrame
    from PyQt6.QtGui import QPalette, QColor
    from PyQt6.QtCore import Qt, QTimer
    pyqt6_available = True
    logger.info("PyQt6 loaded successfully in styles module")
except ImportError as e:
    error_msg = f"PyQt6 import failed in styles module: {e} - Kingdom AI requires PyQt6"
    logger.critical(error_msg)
    # No fallbacks allowed for Kingdom AI - system must halt if PyQt6 is unavailable
    raise RuntimeError("PyQt6 is required for Kingdom AI GUI - system halting") from e

# Tkinter fallback has been removed - Kingdom AI enforces strict PyQt6 requirement
# This aligns with the system's policy of no fallbacks for critical components

# Define PyQt6 style functions
def get_pyqt_dark_theme():
    """Get PyQt6 dark theme palette and style settings."""
    if not pyqt6_available:
        logger.warning("Attempted to get PyQt6 theme while PyQt6 is not available")
        return None, ""

    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND_COLOR))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_COLOR))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(CARD_COLOR))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(TEXT_COLOR))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_COLOR))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_COLOR))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(BORDER_COLOR))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_COLOR))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(ACCENT_COLOR))
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT_COLOR))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_COLOR))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_COLOR))
    
    stylesheet = f"""
    QMainWindow {{ background-color: {BACKGROUND_COLOR}; }}
    QTabWidget::pane {{ border: 1px solid {BORDER_COLOR}; background-color: {CARD_COLOR}; }}
    QTabBar::tab {{ background-color: {BORDER_COLOR}; color: {TEXT_COLOR}; padding: 8px 15px; min-width: 100px; }}
    QTabBar::tab:selected {{ background-color: {ACCENT_COLOR}; }}
    QPushButton {{ background-color: {BORDER_COLOR}; color: {TEXT_COLOR}; padding: 5px 10px; border: none; border-radius: 3px; }}
    QPushButton:hover {{ background-color: {HOVER_COLOR}; }}
    QPushButton:pressed {{ background-color: {ACCENT_COLOR}; }}
    QLineEdit {{ background-color: {BORDER_COLOR}; color: {TEXT_COLOR}; padding: 5px; border: 1px solid {HOVER_COLOR}; border-radius: 3px; }}
    QTextEdit {{ background-color: {BORDER_COLOR}; color: {TEXT_COLOR}; border: 1px solid {HOVER_COLOR}; border-radius: 3px; }}
    QLabel {{ color: {TEXT_COLOR}; }}
    QComboBox {{ background-color: {BORDER_COLOR}; color: {TEXT_COLOR}; padding: 5px; border: 1px solid {HOVER_COLOR}; border-radius: 3px; }}
    """
    
    return dark_palette, stylesheet

# Define theme structures compatible with both PyQt6 and legacy code
DARK_THEME = {
    ".": {
        "configure": {
            "background": BACKGROUND_COLOR,
            "foreground": TEXT_COLOR
        }
    },
    "TFrame": {
        "configure": {
            "background": CARD_COLOR
        }
    },
    "TButton": {
        "configure": {
            "background": BORDER_COLOR,
            "foreground": TEXT_COLOR,
            "borderwidth": 1
        },
        "map": {
            "background": [("active", ACCENT_COLOR)],
            "foreground": [("active", TEXT_COLOR)]
        }
    },
    "TLabel": {
        "configure": {
            "background": CARD_COLOR,
            "foreground": TEXT_COLOR
        }
    },
    "TNotebook": {
        "configure": {
            "background": BACKGROUND_COLOR,
            "tabmargins": [2, 5, 2, 0]
        }
    },
    "TNotebook.Tab": {
        "configure": {
            "background": BORDER_COLOR,
            "foreground": TEXT_COLOR,
            "padding": [10, 2]
        },
        "map": {
            "background": [("selected", ACCENT_COLOR)],
            "foreground": [("selected", TEXT_COLOR)],
            "expand": [("selected", [1, 1, 1, 0])]
        }
    }
}

LIGHT_THEME = {
    ".": {
        "configure": {
            "background": '#FFFFFF',
            "foreground": '#000000'
        }
    },
    "TFrame": {
        "configure": {
            "background": '#F0F0F0'
        }
    },
    "TButton": {
        "configure": {
            "background": '#E0E0E0',
            "foreground": '#000000',
            "borderwidth": 1
        },
        "map": {
            "background": [("active", ACCENT_COLOR)],
            "foreground": [("active", '#FFFFFF')]
        }
    },
    "TLabel": {
        "configure": {
            "background": '#F0F0F0',
            "foreground": '#000000'
        }
    },
    "TNotebook": {
        "configure": {
            "background": '#FFFFFF',
            "tabmargins": [2, 5, 2, 0]
        }
    },
    "TNotebook.Tab": {
        "configure": {
            "background": '#E0E0E0',
            "foreground": '#000000',
            "padding": [10, 2]
        },
        "map": {
            "background": [("selected", ACCENT_COLOR)],
            "foreground": [("selected", '#FFFFFF')],
            "expand": [("selected", [1, 1, 1, 0])]
        }
    }
}

# Define RGB classes
class RGBColorManager:
    """RGB Color Manager for animating color effects.
    Works with both PyQt6 and tkinter environments."""
    
    def __init__(self, update_interval_ms=30):
        self.update_interval = update_interval_ms
        self.subscribers = []
        self._hue = 0
        self.running = False
        self.timer = None
        self.animation_thread = None
        logger.info("RGBColorManager initialized")
    
    def start(self):
        """Start the color animation."""
        if not self.running:
            self.running = True
            self.animation_thread = threading.Thread(target=self._animate, daemon=True)
            self.animation_thread.start()
            logger.info("RGB animation started")
    
    def stop(self):
        """Stop the color animation."""
        self.running = False
        if self.timer:
            self.timer = None
        if self.animation_thread and self.animation_thread.is_alive():
            self.animation_thread.join(timeout=1.0)
        logger.info("RGB animation stopped")
    
    def _animate(self):
        """Animation loop run in a separate thread."""
        while self.running:
            self._update_color()
            time.sleep(self.update_interval / 1000.0)
    
    def _update_color(self):
        """Update the color and notify subscribers."""
        self._hue = (self._hue + 0.005) % 1.0
        rgb = colorsys.hsv_to_rgb(self._hue, 0.8, 0.9)
        color = f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"
        
        # Notify all subscribers with the new color
        for callback in self.subscribers[:]:  # Use a copy in case callbacks modify the list
            try:
                callback(color)
            except Exception as e:
                logger.error(f"Error in RGB animation callback: {e}")
    
    def subscribe(self, callback):
        """Subscribe a callback function to color updates."""
        if callback not in self.subscribers:
            self.subscribers.append(callback)
    
    def unsubscribe(self, callback):
        """Unsubscribe a callback function from color updates."""
        if callback in self.subscribers:
            self.subscribers.remove(callback)

# Create a single instance to be used throughout the application
rgb_color_manager = RGBColorManager()

# Old RGBBorderFrame classes removed - using PyQt6 implementation below

# Ensure rgb_color_manager is started
if not rgb_color_manager.running:
    rgb_color_manager.start()

def initialize_gui_styles(root=None, app=None):
    """Initialize GUI styles with the DARK_THEME.
    
    Args:
        root: The root Tkinter window (for tkinter mode)
        app: QApplication instance (for PyQt6 mode)
            
    Returns:
        ttk.Style object configured with theme (tkinter) or None (PyQt6)
    """
    if pyqt6_available and app:
        logger.info("Initializing PyQt6 styles")
        app.setStyle(QStyleFactory.create("Fusion"))
        palette, stylesheet = get_pyqt_dark_theme()
        app.setPalette(palette)
        app.setStyleSheet(stylesheet)
        return None
    
    elif tkinter_available and root:
        logger.info("Initializing tkinter styles")
        style = ttk.Style()
        style.theme_use('default')  # Reset to default theme first
        
        # Apply our custom theme
        for widget, options in DARK_THEME.items():
            for option_group, settings in options.items():
                if option_group == "configure":
                    style.configure(widget, **settings)
                elif option_group == "map":
                    style.map(widget, **settings)
        return style
    
    logger.warning("No GUI framework available for style initialization")
    return None

# PyQt6-compatible styling system
try:
    from PyQt6.QtWidgets import QPushButton, QFrame, QLabel
    from PyQt6.QtCore import QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
    from PyQt6.QtGui import QColor, QPalette
    
    class GlowButton(QPushButton):
        """PyQt6 GlowButton with proper styling."""
        def __init__(self, text="", parent=None):
            super().__init__(text, parent)
            logger.info("Created PyQt6 GlowButton")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: 2px solid #1976D2;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                    border: 2px solid #0D47A1;
                }
                QPushButton:pressed {
                    background-color: #0D47A1;
                }
            """)

    class RGBAnimationManager:
        """PyQt6-compatible RGB Animation Manager."""
        def __init__(self):
            logger.info("Created PyQt6 RGBAnimationManager")
            self.animations = []
            # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
            self._timer_manager = get_qt_timer_manager()
            self.timer = QTimer()
            self.timer.timeout.connect(self._animate_elements)
            
        def register_element(self, element, *args, **kwargs):
            """Register element for RGB animation."""
            if hasattr(element, 'setStyleSheet'):
                self.animations.append(element)
                
        def unregister_element(self, element, *args, **kwargs):
            """Unregister element from RGB animation."""
            if element in self.animations:
                self.animations.remove(element)
                
        def set_animation_speed(self, speed_ms, *args, **kwargs):
            """Set animation speed."""
            if hasattr(self.timer, 'setInterval'):
                self.timer.setInterval(speed_ms)
                
        def toggle_animations(self, enabled=True, *args, **kwargs):
            """Toggle animations on/off."""
            if enabled and not self.timer.isActive():
                self.timer.start(100)
            elif not enabled and self.timer.isActive():
                self.timer.stop()
        
        def _animate_elements(self):
            """Animate registered RGB elements by cycling through RGB hues."""
            try:
                if not self.animations:
                    return

                hue = (time.time() * 0.1) % 1.0
                rgb = colorsys.hsv_to_rgb(hue, 0.8, 0.9)
                color = f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"

                for element in self.animations[:]:
                    try:
                        if hasattr(element, 'setStyleSheet') and not getattr(element, '_being_deleted', False):
                            current_style = element.styleSheet() or ""
                            element.setStyleSheet(
                                current_style.split("/*RGB*/")[0]
                                + f"/*RGB*/ border: 2px solid {color};"
                            )
                    except RuntimeError:
                        self.animations.remove(element)
                    except Exception as e:
                        logger.debug(f"RGB animation skip for element: {e}")
            except Exception as e:
                logger.error(f"Error in _animate_elements: {e}")

    class RGBBorderManager:
        """PyQt6 RGB border manager."""
        def __init__(self, *args, **kwargs):
            logger.info("Created PyQt6 RGBBorderManager")

    class RGBBorderFrame(QFrame):
        """RGB border frame with animated borders using proper PyQt6 QPropertyAnimation."""
        
        # 2025 CRITICAL FIX: Class-level signals MUST be defined before properties
        hueChanged = pyqtSignal(float)
        glowIntensityChanged = pyqtSignal(float)
        
        def __init__(self, parent=None, border_width=2, border_color="#00FF41"):
            super().__init__(parent)
            self.setObjectName("rgb_border_frame")
            self.border_width = border_width
            
            # Animation properties using proper Qt patterns
            self._hue = 0.0
            self._glow_intensity = 0.8
            self._being_deleted = False
            
            # Set basic styling
            self.setStyleSheet(f"""
                QFrame#rgb_border_frame {{
                    background-color: #1E1E1E;
                    border-radius: 4px;
                }}
            """)
            
            # Setup proper QPropertyAnimation - THE CORRECT WAY!
            self._setup_proper_rgb_animation()
            logger.info("Created PyQt6 RGBBorderFrame with proper QPropertyAnimation")
        
        def _setup_proper_rgb_animation(self):
            """Setup RGB animation using proper QPropertyAnimation - NO TIMERS!"""
            
            # Create QPropertyAnimation for hue cycling - PROPER WAY
            self.hue_animation = QPropertyAnimation(self, b"hue")
            self.hue_animation.setDuration(3000)  # 3 second RGB cycle
            self.hue_animation.setStartValue(0.0)
            self.hue_animation.setEndValue(360.0)
            self.hue_animation.setLoopCount(-1)  # Infinite loop
            self.hue_animation.start()
            
            # Create glow pulse animation
            self.glow_animation = QPropertyAnimation(self, b"glow_intensity")  
            self.glow_animation.setDuration(1500)  # 1.5 second pulse
            self.glow_animation.setStartValue(0.3)
            self.glow_animation.setEndValue(1.0)
            self.glow_animation.setLoopCount(-1)
            self.glow_animation.start()
        
        # 2025 CRITICAL FIX: Separate getter/setter methods for Qt meta-object system
        def getHue(self) -> float:
            """Get current hue value for animation."""
            return self._hue
        
        def setHue(self, value: float) -> None:
            """Set hue value and trigger repaint - THE CORRECT WAY!"""
            if self._hue != value:
                self._hue = value
                self.hueChanged.emit(value)
                self.update()  # Triggers paintEvent - NO DIRECT PAINTING!
        
        def getGlowIntensity(self) -> float:
            """Get current glow intensity for animation."""
            return self._glow_intensity
            
        def setGlowIntensity(self, value: float) -> None:
            """Set glow intensity and trigger repaint."""
            if self._glow_intensity != value:
                self._glow_intensity = value
                self.glowIntensityChanged.emit(value)
                self.update()  # Triggers paintEvent - PROPER Qt WAY!
        
        # 2025 MODERN APPROACH: Function-style properties that work with Qt meta-object
        hue = pyqtProperty(float, getHue, setHue, notify=hueChanged)
        glow_intensity = pyqtProperty(float, getGlowIntensity, setGlowIntensity, notify=glowIntensityChanged)
        
        def paintEvent(self, event):
            """ALL painting happens here - follows Qt rules with 2025 safety checks!"""
            if self._being_deleted:
                return
            
            # 2025 CRITICAL SAFETY: Check widget validity before painting
            if not self.isVisible() or self.size().isEmpty():
                return
                
            # 2025 CRITICAL SAFETY: Validate paint device before creating QPainter
            paint_device = self
            if hasattr(paint_device, 'paintEngine') and paint_device.paintEngine() is None:
                logger.warning("Paint engine is None - widget being deleted, skipping paint")
                return
                
            painter = QPainter(self)
            # 2025 CRITICAL SAFETY: Verify painter is valid
            if not painter.isActive():
                logger.warning("QPainter failed to initialize - device invalid")
                return
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Create RGB color from current hue
                from PyQt6.QtGui import QColor, QPen
                color = QColor.fromHsv(int(self._hue), 255, int(255 * self._glow_intensity))
                
                # Draw animated border - SAFE PAINTING IN PAINTEVENT!
                pen = QPen(color, self.border_width)
                painter.setPen(pen)
                painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
                
            finally:
                painter.end()  # Always end painter
        
        def closeEvent(self, event):
            """Properly cleanup animations when widget is closed."""
            self._being_deleted = True
            if hasattr(self, 'hue_animation'):
                self.hue_animation.stop()
            if hasattr(self, 'glow_animation'):
                self.glow_animation.stop()
            super().closeEvent(event)
        

    class KingdomStyles:
        """PyQt6 Kingdom styling system."""
        @staticmethod
        def setup_theme(app=None, *args, **kwargs):
            """Setup Kingdom AI theme for PyQt6."""
            if app:
                app.setStyleSheet("""
                    QMainWindow {
                        background-color: #121212;
                        color: #FFFFFF;
                    }
                    QTabWidget::pane {
                        border: 1px solid #333333;
                        background-color: #1E1E1E;
                    }
                    QTabBar::tab {
                        background-color: #2C2C2C;
                        color: #FFFFFF;
                        padding: 8px 16px;
                        margin: 2px;
                    }
                    QTabBar::tab:selected {
                        background-color: #00A0FF;
                    }
                    QMenuBar {
                        background-color: #1E1E1E;
                        color: #FFFFFF;
                    }
                    QMenuBar::item:selected {
                        background-color: #00A0FF;
                    }
                    QStatusBar {
                        background-color: #1E1E1E;
                        color: #FFFFFF;
                    }
                """)
                logger.info("Applied Kingdom AI PyQt6 theme")

    class FrameHeader(QLabel):
        """PyQt6 frame header."""
        def __init__(self, text="", parent=None):
            super().__init__(text, parent)
            self.setStyleSheet("""
                QLabel {
                    color: #00A0FF;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 4px;
                }
            """)

    def create_themed_frame(parent=None, *args, **kwargs):
        """Create PyQt6 themed frame."""
        frame = QFrame(parent)
        frame.setStyleSheet("""
            QFrame {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 4px;
            }
        """)
        return frame

    def create_accent_label(text="", parent=None, *args, **kwargs):
        """Create PyQt6 accent label."""
        label = QLabel(text, parent)
        label.setStyleSheet("""
            QLabel {
                color: #00A0FF;
                font-weight: bold;
            }
        """)
        return label
        
except ImportError as e:
    logger.critical(f"PyQt6 not available for styling: {e}")
    raise RuntimeError("PyQt6 is required for Kingdom AI styling") from e

# Create instances
rgb_animation_manager = RGBAnimationManager()

# Add theme getter functions that match what trading frames expect
def get_dark_theme():
    """
    Get dark theme color dictionary compatible with trading frames.
    
    Returns:
        dict: Dictionary with color key/values for dark theme
    """
    return {
        "background": BACKGROUND_COLOR,
        "text": TEXT_COLOR,
        "accent": ACCENT_COLOR,
        "border": BORDER_COLOR,
        "chart_background": CARD_COLOR,
        "up_color": "#26A69A",  # Green for up trends
        "down_color": "#EF5350",  # Red for down trends
        "grid_color": "#333333",
        "volume_up_color": "#2E7D32",
        "volume_down_color": "#C62828"
    }

def get_light_theme():
    """
    Get light theme color dictionary compatible with trading frames.
    
    Returns:
        dict: Dictionary with color key/values for light theme
    """
    return {
        "background": "#FFFFFF",
        "text": "#212121",
        "accent": "#1976D2",
        "border": "#BDBDBD",
        "chart_background": "#F5F5F5",
        "up_color": "#26A69A",  # Green for up trends
        "down_color": "#EF5350",  # Red for down trends
        "grid_color": "#E0E0E0",
        "volume_up_color": "#2E7D32",
        "volume_down_color": "#C62828"
    }

__all__ = [
    'pyqt6_available',
    'tkinter_available',
    'get_dark_theme',
    'get_light_theme',
    'rgb_color_manager',
    'RGBBorderFrame',
    'initialize_gui_styles',
    'DARK_THEME',
    'LIGHT_THEME',
    'ACCENT_COLOR',
    'ACCENT_COLOR_DARK',
    'ACCENT_COLOR_LIGHT',
    'BACKGROUND_COLOR',
    'CARD_COLOR',
    'TEXT_COLOR',
    'SECONDARY_TEXT',
    'ERROR_COLOR',
    'SUCCESS_COLOR',
    'WARNING_COLOR',
    'BORDER_COLOR',
    'HOVER_COLOR',
    'GlowButton',
    'RGBBorderManager',
    'KingdomStyles',
    'FrameHeader',
    'create_themed_frame',
    'create_accent_label',
    'rgb_animation_manager'
]

def cleanup_timer(self):
        """Properly cleanup RGB timer."""
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
            self.timer.deleteLater()
