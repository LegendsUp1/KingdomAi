"""
Utility functions and constants for the Thoth AI Qt interface.
"""

from typing import Dict, Any, Optional, Tuple, List, Union
from PyQt6.QtGui import QColor, QPalette, QFont, QIcon, QPixmap, QLinearGradient, QBrush
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QWidget, QSizePolicy, QLabel, QVBoxLayout, QHBoxLayout, QFrame

# Color palette
COLORS = {
    'bg_primary': '#1a1b26',
    'bg_secondary': '#24283b',
    'bg_tertiary': '#2a2e43',
    'text_primary': '#a9b1d6',
    'text_secondary': '#7aa2f7',
    'accent': '#7aa2f7',
    'accent_hover': '#8ab4ff',
    'success': '#9ece6a',
    'warning': '#e0af68',
    'error': '#f7768e',
    'border': '#3b4261',
    'shadow': 'rgba(0, 0, 0, 0.3)',
    'user_bubble': '#2a5c8a',
    'ai_bubble': '#2a3a4a',
    'typing_indicator': '#4c566a',
}

# Font settings
FONTS = {
    'default': 'Segoe UI',
    'monospace': 'Consolas, Monaco, monospace',
    'sizes': {
        'small': 10,
        'normal': 11,
        'large': 13,
        'xlarge': 16,
    }
}

def create_rounded_rect(painter, rect, radius=8, color=None):
    """Draw a rounded rectangle with the given painter."""
    if color:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
    painter.drawRoundedRect(rect, radius, radius)

def create_gradient(color1: str, color2: str, start: Tuple[int, int], end: Tuple[int, int]):
    """Create a QLinearGradient between two colors."""
    gradient = QLinearGradient(*start, *end)
    gradient.setColorAt(0, QColor(color1))
    gradient.setColorAt(1, QColor(color2))
    return gradient

def create_icon(icon_name: str, color: str = COLORS['text_primary']) -> QIcon:
    """Create a QIcon with the specified color."""
    # This is a placeholder - in a real app, you'd load from theme or resources
    from PyQt6.QtGui import QPainter, QPixmap
    
    # Create a simple colored icon as fallback
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw a simple circle with the first letter
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size-4, size-4)
    
    # Add text
    if icon_name:
        painter.setPen(Qt.GlobalColor.white)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, icon_name[0].upper())
    
    painter.end()
    return QIcon(pixmap)

def create_loading_widget(parent=None) -> QWidget:
    """Create a loading animation widget."""
    container = QWidget(parent)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    
    # Create loading animation (simple dots for now)
    loading_label = QLabel("Loading...")
    loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    loading_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
    
    layout.addWidget(loading_label)
    return container

def create_separator(vertical: bool = False) -> QFrame:
    """Create a separator line."""
    line = QFrame()
    if vertical:
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedWidth(1)
    else:
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
    line.setStyleSheet(f"background: {COLORS['border']}; margin: 4px 0;")
    return line

def apply_dark_theme(app):
    """Apply a dark theme to the application."""
    app.setStyle("Fusion")
    
    # Set the palette
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(COLORS['bg_primary']))
    palette.setColor(QPalette.WindowText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Base, QColor(COLORS['bg_secondary']))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS['bg_tertiary']))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS['bg_secondary']))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Text, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Button, QColor(COLORS['bg_secondary']))
    palette.setColor(QPalette.ButtonText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.BrightText, QColor(COLORS['accent']))
    palette.setColor(QPalette.Link, QColor(COLORS['accent']))
    palette.setColor(QPalette.Highlight, QColor(COLORS['accent']))
    palette.setColor(QPalette.HighlightedText, Qt.GlobalColor.white)
    
    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(COLORS['text_secondary']))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(COLORS['text_secondary']))
    
    app.setPalette(palette)
    
    # Set style sheet
    app.setStyleSheet(f"""
        QWidget {{
            background-color: {COLORS['bg_primary']};
            color: {COLORS['text_primary']};
            selection-background-color: {COLORS['accent']};
            selection-color: white;
            border: none;
        }}
        
        QPushButton {{
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 5px 10px;
            min-width: 80px;
        }}
        
        QPushButton:hover {{
            background-color: {COLORS['bg_tertiary']};
            border-color: {COLORS['accent']};
        }}
        
        QPushButton:pressed {{
            background-color: {COLORS['accent']};
            color: white;
        }}
        
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 5px;
            selection-background-color: {COLORS['accent']};
        }}
        
        QScrollBar:vertical {{
            border: none;
            background: {COLORS['bg_secondary']};
            width: 10px;
            margin: 0px;
        }}
        
        QScrollBar::handle:vertical {{
            background: {COLORS['border']};
            min-height: 20px;
            border-radius: 5px;
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QScrollBar:horizontal {{
            border: none;
            background: {COLORS['bg_secondary']};
            height: 10px;
            margin: 0px;
        }}
        
        QScrollBar::handle:horizontal {{
            background: {COLORS['border']};
            min-width: 20px;
            border-radius: 5px;
        }}
    """)
    
    return app
