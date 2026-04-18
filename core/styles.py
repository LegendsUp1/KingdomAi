"""
Style definitions and theming for the Kingdom AI Qt interface.
"""

from typing import Optional
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import Qt, QEasingCurve

# Color palette - using a modern, dark theme
COLORS = {
    # Base colors
    'bg_primary': '#1a1b26',
    'bg_secondary': '#24283b',
    'bg_tertiary': '#2a2e43',
    'bg_quaternary': '#343b58',
    
    # Text colors
    'text_primary': '#a9b1d6',
    'text_secondary': '#7aa2f7',
    'text_tertiary': '#7dcfff',
    'text_disabled': '#565f89',
    'text_error': '#f7768e',
    'text_warning': '#e0af68',
    'text_success': '#9ece6a',
    'text_info': '#7aa2f7',
    
    # Accent colors
    'accent': '#7aa2f7',  # Blue
    'accent_hover': '#8ab4ff',
    'accent_pressed': '#5a7bc8',
    'accent_disabled': '#3b4261',
    
    # Status colors
    'success': '#9ece6a',  # Green
    'warning': '#e0af68',  # Orange
    'error': '#f7768e',    # Red
    'info': '#7aa2f7',     # Blue
    
    # UI elements
    'border': '#3b4261',
    'border_light': '#414868',
    'border_dark': '#1f2335',
    'divider': '#292e42',
    'shadow': 'rgba(0, 0, 0, 0.3)',
    'overlay': 'rgba(0, 0, 0, 0.7)',
    'highlight': 'rgba(122, 162, 247, 0.15)',
    'selection': 'rgba(122, 162, 247, 0.3)',
    
    # Message bubbles
    'user_bubble': '#2a5c8a',
    'ai_bubble': '#2a3a4a',
    'system_bubble': '#3b3b4f',
    'typing_indicator': '#4c566a',
    
    # Buttons
    'button_bg': '#2a2e43',
    'button_hover': '#343b58',
    'button_pressed': '#3b4261',
    'button_disabled': '#1f2335',
    
    # Inputs
    'input_bg': '#1e2030',
    'input_border': '#3b4261',
    'input_focus': '#7aa2f7',
    'input_placeholder': '#565f89',
    'input_text': '#a9b1d6',
    
    # Scrollbars
    'scroll_handle': '#3b4261',
    'scroll_track': '#1f2335',
    
    # Tabs
    'tab_bg': '#1f2335',
    'tab_hover': '#2a2e43',
    'tab_active': '#24283b',
    'tab_text': '#a9b1d6',
    'tab_text_active': '#7aa2f7',
    
    # Tooltips
    'tooltip_bg': '#24283b',
    'tooltip_text': '#a9b1d6',
    'tooltip_border': '#3b4261',
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
        'xxlarge': 20,
        'h1': 24,
        'h2': 20,
        'h3': 18,
        'h4': 16,
        'h5': 14,
        'h6': 12,
    },
    'weights': {
        'light': 300,
        'normal': 400,
        'medium': 500,
        'semibold': 600,
        'bold': 700,
    }
}

# Animation settings
ANIMATIONS = {
    'duration': {
        'fast': 150,    # ms
        'normal': 250,  # ms
        'slow': 350,    # ms
    },
    'easing': {
        'standard': QEasingCurve.Type.OutQuad,
        'deceleration': QEasingCurve.Type.OutCubic,
        'acceleration': QEasingCurve.Type.InOutQuad,
        'sharp': QEasingCurve.Type.OutQuart,
    }
}

def get_color(name: str, alpha: Optional[float] = None) -> str:
    """Get a color by name, optionally with alpha transparency.
    
    Args:
        name: Name of the color from the COLORS dictionary
        alpha: Optional alpha value (0.0-1.0)
        
    Returns:
        Hex color string (with alpha if specified)
    """
    if name not in COLORS:
        return '#000000'
    
    color = COLORS[name]
    if alpha is not None and 0 <= alpha <= 1:
        # Convert hex to RGB
        if color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            return f'rgba({r}, {g}, {b}, {alpha})'
        # Handle rgba() format
        elif color.startswith('rgba'):
            parts = color[5:-1].split(',')
            if len(parts) >= 3:
                return f'rgba({parts[0]}, {parts[1]}, {parts[2]}, {alpha})'
    
    return color

def get_font(size: str = 'normal', weight: str = 'normal', family: str = None) -> QFont:
    """Get a QFont with the specified properties.
    
    Args:
        size: Font size key from FONTS['sizes'] or exact size in points
        weight: Font weight key from FONTS['weights'] or exact weight
        family: Font family (defaults to FONTS['default'])
        
    Returns:
        Configured QFont
    """
    font = QFont()
    
    # Set font family
    if family is None:
        family = FONTS['default']
    font.setFamily(family)
    
    # Set font size
    if isinstance(size, str) and size in FONTS['sizes']:
        font.setPointSize(FONTS['sizes'][size])
    elif isinstance(size, (int, float)):
        font.setPointSizeF(float(size))
    
    # Set font weight
    if isinstance(weight, str) and weight in FONTS['weights']:
        font.setWeight(FONTS['weights'][weight])
    elif isinstance(weight, int):
        font.setWeight(weight)
    
    return font

def apply_dark_theme(app):
    """Apply a dark theme to a QApplication.
    
    Args:
        app: QApplication instance
    """
    # Set style
    app.setStyle('Fusion')
    
    # Create and set palette
    palette = QPalette()
    
    # Base colors
    palette.setColor(QPalette.Window, QColor(COLORS['bg_primary']))
    palette.setColor(QPalette.WindowText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Base, QColor(COLORS['bg_secondary']))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS['bg_tertiary']))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS['tooltip_bg']))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS['tooltip_text']))
    palette.setColor(QPalette.Text, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Button, QColor(COLORS['button_bg']))
    palette.setColor(QPalette.ButtonText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.BrightText, QColor(COLORS['accent']))
    palette.setColor(QPalette.Link, QColor(COLORS['accent']))
    palette.setColor(QPalette.Highlight, QColor(COLORS['accent']))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    
    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(COLORS['text_disabled']))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(COLORS['text_disabled']))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(COLORS['text_disabled']))
    palette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(COLORS['accent_disabled']))
    
    # Set the palette
    app.setPalette(palette)
    
    # Set style sheet for additional styling
    app.setStyleSheet(f"""
        /* Base styles */
        QWidget {{
            background-color: {COLORS['bg_primary']};
            color: {COLORS['text_primary']};
            selection-background-color: {COLORS['selection']};
            selection-color: white;
            border: none;
            outline: none;
        }}
        
        /* Buttons */
        QPushButton {{
            background-color: {COLORS['button_bg']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 6px 12px;
            min-width: 80px;
        }}
        
        QPushButton:hover {{
            background-color: {COLORS['button_hover']};
            border-color: {COLORS['accent']};
        }}
        
        QPushButton:pressed {{
            background-color: {COLORS['button_pressed']};
        }}
        
        QPushButton:disabled {{
            background-color: {COLORS['button_disabled']};
            color: {COLORS['text_disabled']};
            border-color: {COLORS['border_dark']};
        }}
        
        /* Text inputs */
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {COLORS['input_bg']};
            border: 1px solid {COLORS['input_border']};
            border-radius: 4px;
            padding: 6px;
            selection-background-color: {COLORS['selection']};
        }}
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, 
        QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {COLORS['input_focus']};
        }}
        
        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: {COLORS['scroll_track']};
            width: 10px;
            margin: 0px;
        }}
        
        QScrollBar::handle:vertical {{
            background: {COLORS['scroll_handle']};
            min-height: 20px;
            border-radius: 5px;
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        /* Tabs */
        QTabBar::tab {{
            background: {COLORS['tab_bg']};
            color: {COLORS['tab_text']};
            border: 1px solid {COLORS['border']};
            border-bottom: none;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        
        QTabBar::tab:selected, QTabBar::tab:hover {{
            background: {COLORS['tab_active']};
            color: {COLORS['tab_text_active']};
        }}
        
        QTabBar::tab:selected {{
            border-bottom: 2px solid {COLORS['accent']};
        }}
        
        QTabWidget::pane {{
            border: 1px solid {COLORS['border']};
            border-top: none;
            background: {COLORS['bg_primary']};
        }}
        
        /* Tooltips */
        QToolTip {{
            background-color: {COLORS['tooltip_bg']};
            color: {COLORS['tooltip_text']};
            border: 1px solid {COLORS['tooltip_border']};
            padding: 4px 8px;
            border-radius: 4px;
        }}
    """)
    
    # Set application font
    app.setFont(get_font('normal'))
    
    return app
