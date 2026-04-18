#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI PyQt6 Style System
Provides styling for the Kingdom AI PyQt6 GUI components.
This replaces the Tkinter-based styles.py for the PyQt6 migration.
"""

import logging
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor

# Configure logger
logger = logging.getLogger("qt_styles")

# Define theme constants - matching the same colors from the original theme
DARK_THEME = {
    "background": "#2D2D2D",
    "foreground": "#FFFFFF",
    "accent": "#007BFF",
    "secondary": "#6C757D",
    "success": "#28A745",
    "warning": "#FFC107",
    "danger": "#DC3545",
    "info": "#17A2B8",
    "button_bg": "#444444",
    "button_fg": "#FFFFFF",
    "entry_bg": "#3D3D3D",
    "entry_fg": "#FFFFFF",
    "border": "#555555",
    "highlight": "#007BFF"
}

LIGHT_THEME = {
    "background": "#F0F0F0",
    "foreground": "#000000",
    "accent": "#0069D9",
    "secondary": "#5A6268",
    "success": "#218838",
    "warning": "#E0A800",
    "danger": "#C82333",
    "info": "#138496",
    "button_bg": "#E2E2E2",
    "button_fg": "#000000",
    "entry_bg": "#FFFFFF",
    "entry_fg": "#000000",
    "border": "#CCCCCC",
    "highlight": "#0069D9"
}

class KingdomQtStyle:
    """Style manager for Kingdom AI PyQt6 GUI components."""
    
    @staticmethod
    def apply_to_widget(widget, theme=None):
        """Apply Kingdom AI styling to a PyQt6 widget."""
        if theme is None:
            # Default to dark theme
            theme = DARK_THEME
        
        try:
            # Create a style sheet based on the theme
            style_sheet = f"""
                QWidget {{
                    background-color: {theme["background"]};
                    color: {theme["foreground"]};
                }}
                
                QPushButton {{
                    background-color: {theme["button_bg"]};
                    color: {theme["button_fg"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 4px;
                    padding: 5px;
                }}
                
                QPushButton:hover {{
                    background-color: {theme["accent"]};
                }}
                
                QPushButton:pressed {{
                    background-color: {theme["highlight"]};
                }}
                
                QLineEdit, QTextEdit, QPlainTextEdit {{
                    background-color: {theme["entry_bg"]};
                    color: {theme["entry_fg"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 2px;
                    padding: 2px;
                }}
                
                QTabWidget::pane {{
                    border: 1px solid {theme["border"]};
                    background-color: {theme["background"]};
                }}
                
                QTabBar::tab {{
                    background-color: {theme["button_bg"]};
                    color: {theme["button_fg"]};
                    border: 1px solid {theme["border"]};
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    padding: 5px 10px;
                }}
                
                QTabBar::tab:selected {{
                    background-color: {theme["accent"]};
                }}
                
                QTabBar::tab:hover {{
                    background-color: {theme["highlight"]};
                }}
                
                QStatusBar {{
                    background-color: {theme["secondary"]};
                    color: {theme["foreground"]};
                }}
                
                QProgressBar {{
                    border: 1px solid {theme["border"]};
                    border-radius: 2px;
                    text-align: center;
                }}
                
                QProgressBar::chunk {{
                    background-color: {theme["accent"]};
                }}
                
                QLabel {{
                    color: {theme["foreground"]};
                }}
                
                QTableView {{
                    border: 1px solid {theme["border"]};
                    gridline-color: {theme["border"]};
                }}
                
                QHeaderView::section {{
                    background-color: {theme["button_bg"]};
                    color: {theme["button_fg"]};
                    border: 1px solid {theme["border"]};
                }}
            """
            
            # Apply the style sheet
            widget.setStyleSheet(style_sheet)
            
            logger.debug("Applied PyQt6 style to widget")
            return True
        except Exception as e:
            logger.error(f"Error applying PyQt6 style: {e}")
            return False

    @staticmethod
    def dark_theme():
        """Return the dark theme palette for PyQt6."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(DARK_THEME["background"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(DARK_THEME["foreground"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(DARK_THEME["entry_bg"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(DARK_THEME["background"]))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(DARK_THEME["background"]))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(DARK_THEME["foreground"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(DARK_THEME["foreground"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(DARK_THEME["button_bg"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(DARK_THEME["button_fg"]))
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(DARK_THEME["accent"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(DARK_THEME["highlight"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(DARK_THEME["foreground"]))
        return palette

    @staticmethod
    def light_theme():
        """Return the light theme palette for PyQt6."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(LIGHT_THEME["background"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(LIGHT_THEME["foreground"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(LIGHT_THEME["entry_bg"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(LIGHT_THEME["background"]))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(LIGHT_THEME["background"]))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(LIGHT_THEME["foreground"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(LIGHT_THEME["foreground"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(LIGHT_THEME["button_bg"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(LIGHT_THEME["button_fg"]))
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(LIGHT_THEME["accent"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(LIGHT_THEME["highlight"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(LIGHT_THEME["foreground"]))
        return palette

    @staticmethod
    def apply_theme_to_app(app, dark=True):
        """Apply theme to the entire application."""
        try:
            if dark:
                app.setPalette(KingdomQtStyle.dark_theme())
            else:
                app.setPalette(KingdomQtStyle.light_theme())
            logger.info(f"Applied {'dark' if dark else 'light'} theme to application")
            return True
        except Exception as e:
            logger.error(f"Error applying theme to application: {e}")
            return False


def initialize_qt_styles(app=None):
    """Initialize PyQt6 styles for the Kingdom AI system."""
    try:
        logger.info("Initializing PyQt6 styles for Kingdom AI")
        if app is None:
            # Get the current application instance if one exists
            app = QApplication.instance()
            
        if app is not None:
            KingdomQtStyle.apply_theme_to_app(app, dark=True)
            logger.info("Applied dark theme to Kingdom AI application")
    except Exception as e:
        logger.error(f"Failed to initialize PyQt6 styles: {e}")


def get_style_sheet(component_type="default"):
    """Get the stylesheet for a specific component type.
    
    Args:
        component_type: The type of component to get stylesheet for
            (default, button, textbox, api_manager, etc.)
    
    Returns:
        str: The appropriate QSS stylesheet for the component
    """
    try:
        logger.info(f"Getting stylesheet for component type: {component_type}")
        
        # Base stylesheet for all components
        base_style = """
        QWidget {
            background-color: #2D2D2D;
            color: #FFFFFF;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QLabel {
            color: #FFFFFF;
        }
        QPushButton {
            background-color: #444444;
            color: #FFFFFF;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 5px 10px;
        }
        QPushButton:hover {
            background-color: #555555;
        }
        QPushButton:pressed {
            background-color: #007BFF;
        }
        QLineEdit, QTextEdit {
            background-color: #3D3D3D;
            color: #FFFFFF;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 5px;
        }
        QComboBox {
            background-color: #3D3D3D;
            color: #FFFFFF;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 5px;
        }
        """
        
        # Component-specific stylesheets
        component_styles = {
            "api_manager": base_style + """
            QTableWidget {
                background-color: #3D3D3D;
                color: #FFFFFF;
                border: 1px solid #555555;
                gridline-color: #555555;
            }
            QHeaderView::section {
                background-color: #444444;
                color: #FFFFFF;
                padding: 5px;
                border: 1px solid #555555;
            }
            QTableWidget::item:selected {
                background-color: #007BFF;
            }
            """,
            
            "code_generator": base_style + """
            QSplitter::handle {
                background-color: #555555;
            }
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
            }
            """,
            
            "dashboard": base_style + """
            QFrame {
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007BFF;
            }
            """,
            
            "trading": base_style + """
            QTabWidget::pane {
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #444444;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 5px 10px;
            }
            QTabBar::tab:selected {
                background-color: #2D2D2D;
                border-bottom: 1px solid #2D2D2D;
            }
            """
        }
        
        # Return component-specific style if available, otherwise return base style
        return component_styles.get(component_type, base_style)
        
    except Exception as e:
        logger.error(f"Error getting stylesheet for {component_type}: {e}")
        return "" # Return empty stylesheet on error
