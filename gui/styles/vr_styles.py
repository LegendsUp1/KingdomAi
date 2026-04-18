"""
VR Tab Styling for Kingdom AI

This module contains all the styling information for the VR tab components,
ensuring a consistent look and feel with the rest of the application.
"""

# Color palette
COLORS = {
    'background': '#1a1a2e',
    'primary': '#0f3460',
    'secondary': '#16213e',
    'accent': '#e94560',
    'text': '#ffffff',
    'text_secondary': '#b3b3b3',
    'success': '#4caf50',
    'warning': '#ff9800',
    'error': '#f44336',
    'highlight': '#00bcd4',
}

# Font settings
FONTS = {
    'title': 'Arial, 16pt, bold',
    'subtitle': 'Arial, 12pt, bold',
    'normal': 'Arial, 10pt',
    'small': 'Arial, 8pt',
}

# Border styles
BORDERS = {
    'frame': f'2px solid {COLORS["primary"]}',
    'button': f'1px solid {COLORS["accent"]}',
    'input': f'1px solid {COLORS["secondary"]}',
}

# Border radius
RADIUS = {
    'small': '4px',
    'medium': '8px',
    'large': '12px',
}

# Shadows
SHADOWS = {
    'light': '0 2px 4px rgba(0, 0, 0, 0.1)',
    'medium': '0 4px 8px rgba(0, 0, 0, 0.2)',
    'strong': '0 6px 12px rgba(0, 0, 0, 0.3)',
}

def get_tab_style():
    """Returns the base style for the VR tab."""
    return f"""
        QWidget#VRMainWidget {{
            background-color: {COLORS['background']};
            color: {COLORS['text']};
            font: {FONTS['normal']};
        }}
        
        QTabWidget::pane {{
            border: {BORDERS['frame']};
            border-radius: {RADIUS['medium']};
            background: {COLORS['secondary']};
        }}
        
        QTabBar::tab {{
            background: {COLORS['primary']};
            color: {COLORS['text']};
            padding: 8px 16px;
            border: none;
            border-top-left-radius: {RADIUS['small']};
            border-top-right-radius: {RADIUS['small']};
            margin-right: 2px;
        }}
        
        QTabBar::tab:selected, QTabBar::tab:hover {{
            background: {COLORS['accent']};
        }}
        
        QPushButton {{
            background-color: {COLORS['primary']};
            color: {COLORS['text']};
            border: {BORDERS['button']};
            border-radius: {RADIUS['small']};
            padding: 6px 12px;
            min-width: 80px;
        }}
        
        QPushButton:hover {{
            background-color: {COLORS['accent']};
        }}
        
        QPushButton:pressed {{
            background-color: {COLORS['highlight']};
        }}
        
        QPushButton:disabled {{
            background-color: #555555;
            color: #888888;
            border: 1px solid #444444;
        }}
        
        QLabel {{
            color: {COLORS['text']};
        }}
        
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {{
            background-color: {COLORS['secondary']};
            color: {COLORS['text']};
            border: {BORDERS['input']};
            border-radius: {RADIUS['small']};
            padding: 4px 8px;
        }}
        
        QProgressBar {{
            border: 1px solid {COLORS['primary']};
            border-radius: {RADIUS['small']};
            text-align: center;
            background: {COLORS['background']};
        }}
        
        QProgressBar::chunk {{
            background-color: {COLORS['accent']};
            width: 10px;
            margin: 0.5px;
        }}
        
        QToolBar {{
            background: {COLORS['primary']};
            border: none;
            padding: 2px;
        }}
        
        QStatusBar {{
            background: {COLORS['primary']};
            color: {COLORS['text']};
            padding: 4px;
        }}
        
        /* Custom VR Controls */
        .VRControlGroup {{
            border: {BORDERS['frame']};
            border-radius: {RADIUS['medium']};
            padding: 8px;
            margin: 4px;
            background: {COLORS['secondary']};
        }}
        
        .VRControlGroup QLabel {{
            font: {FONTS['subtitle']};
            color: {COLORS['highlight']};
            margin-bottom: 6px;
        }}
        
        /* 3D Viewer */
        #VR3DViewer {{
            border: 2px solid {COLORS['primary']};
            border-radius: {RADIUS['medium']};
            background: #000000;
        }}
        
        /* Device Panel */
        .DeviceStatus {{
            padding: 8px;
            margin: 4px 0;
            border-radius: {RADIUS['small']};
            background: rgba(255, 255, 255, 0.1);
        }}
        
        /* Performance Gauges */
        .GaugeWidget {{
            background: {COLORS['secondary']};
            border-radius: {RADIUS['medium']};
            padding: 8px;
        }}
        
        /* Environment Thumbnails */
        .EnvironmentThumbnail {{
            border: 2px solid {COLORS['primary']};
            border-radius: {RADIUS['small']};
        }}
        
        .EnvironmentThumbnail:selected {{
            border-color: {COLORS['accent']};
        }}
        
        /* Gesture Controls */
        .GestureButton {{
            min-width: 100px;
            min-height: 40px;
            margin: 4px;
            font-weight: bold;
        }}
        
        .GestureButton:checked {{
            background-color: {COLORS['accent']};
            border-color: {COLORS['highlight']};
        }}
    """

def get_button_style(color: str = 'primary', size: str = 'normal') -> str:
    """Returns a styled button CSS string.
    
    Args:
        color: One of 'primary', 'accent', 'success', 'warning', 'error'
        size: One of 'small', 'normal', 'large'
    """
    colors = {
        'primary': COLORS['primary'],
        'accent': COLORS['accent'],
        'success': COLORS['success'],
        'warning': COLORS['warning'],
        'error': COLORS['error'],
    }
    
    bg_color = colors.get(color, COLORS['primary'])
    hover_color = COLORS['highlight'] if color == 'primary' else f"{bg_color}cc"
    
    sizes = {
        'small': 'padding: 2px 6px; font-size: 10px;',
        'normal': 'padding: 4px 8px; font-size: 11px;',
        'large': 'padding: 8px 16px; font-size: 13px;',
    }
    size_style = sizes.get(size, sizes['normal'])
    
    return f"""
        QPushButton {{
            background-color: {bg_color};
            color: {COLORS['text']};
            border: 1px solid {bg_color};
            border-radius: {RADIUS['small']};
            {size_style}
            min-width: 60px;
        }}
        QPushButton:hover {{
            background-color: {hover_color};
            border-color: {hover_color};
        }}
        QPushButton:pressed {{
            background-color: {COLORS['highlight']};
            border-color: {COLORS['highlight']};
        }}
        QPushButton:disabled {{
            background-color: #444444;
            border-color: #333333;
            color: #888888;
        }}
    """

def get_slider_style() -> str:
    """Returns the style for slider controls."""
    return f"""
        QSlider::groove:horizontal {{
            border: 1px solid {COLORS['primary']};
            height: 8px;
            background: {COLORS['secondary']};
            margin: 2px 0;
            border-radius: 4px;
        }}
        
        QSlider::handle:horizontal {{
            background: {COLORS['accent']};
            border: 1px solid {COLORS['highlight']};
            width: 16px;
            margin: -4px 0;
            border-radius: 8px;
        }}
        
        QSlider::sub-page:horizontal {{
            background: {COLORS['accent']};
            border: 1px solid {COLORS['highlight']};
            border-radius: 4px;
        }}
    """

def get_label_style(color: str = 'text', size: str = 'normal') -> str:
    """Returns a styled label CSS string.
    
    Args:
        color: Color key from COLORS dict (default: 'text')
        size: Font size key from FONTS dict (default: 'normal')
        
    Returns:
        CSS string for the label style
    """
    return f"""
        QLabel {{
            color: {COLORS.get(color, COLORS['text'])};
            font: {FONTS.get(size, FONTS['normal'])};
            background-color: transparent;
            padding: 4px;
        }}
        QLabel:disabled {{
            color: {COLORS['text_secondary']};
        }}
    """

def get_font(font_type: str = 'normal') -> str:
    """Returns a font string for the given type.
    
    Args:
        font_type: Type of font (title, subtitle, normal, small)
        
    Returns:
        Font string
    """
    return FONTS.get(font_type, FONTS['normal'])

def get_tooltip_style() -> str:
    """Returns the style for tooltips."""
    return f"""
        QToolTip {{
            background-color: {COLORS['primary']};
            color: {COLORS['text']};
            border: 1px solid {COLORS['accent']};
            border-radius: {RADIUS['small']};
            padding: 4px 8px;
            opacity: 230;
        }}
    """

# Export common styles for easy access
COMMON_STYLES = {
    'primary_button': get_button_style('primary'),
    'accent_button': get_button_style('accent'),
    'success_button': get_button_style('success'),
    'warning_button': get_button_style('warning'),
    'error_button': get_button_style('error'),
    'slider': get_slider_style(),
    'tooltip': get_tooltip_style(),
}
