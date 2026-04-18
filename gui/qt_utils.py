#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Qt Utilities

This module provides utility functions and classes for PyQt6-based GUI components
in the Kingdom AI system.
"""

import os
import sys
import logging
import functools
import asyncio
import traceback
from typing import Optional, List, Dict, Any, Callable, Union, TypeVar, cast

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QCheckBox, QComboBox, QDialog, QMessageBox,
    QFrame, QFormLayout, QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize, QObject
from PyQt6.QtGui import QIcon, QPixmap, QPalette, QColor

from gui.qt_styles import KingdomQtStyle

# Initialize logger
logger = logging.getLogger(__name__)

# Type variable for generic function return typing
T = TypeVar('T')

def async_slot(func: Callable[..., Any]) -> Callable[..., None]:
    """Decorator to allow async functions to be used as Qt slots.
    
    Args:
        func: The async function to be wrapped
        
    Returns:
        A synchronous function that schedules the async function
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(func(*args, **kwargs))
            else:
                loop.run_until_complete(func(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error in async_slot {func.__name__}: {e}")
            traceback.print_exc()
    return wrapper

def get_icon(name: str, size: int = 24) -> QIcon:
    """Get an icon from the resources directory.
    
    Args:
        name (str): Icon name (without extension)
        size (int): Icon size
        
    Returns:
        QIcon: Icon object
    """
    try:
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "resources",
            "icons",
            f"{name}.png"
        )
        
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        else:
            logger.warning(f"Icon not found: {icon_path}")
            return QIcon()
    except Exception as e:
        logger.error(f"Error loading icon {name}: {e}")
        return QIcon()

def create_button(text: str, icon: Optional[str] = None, size: QSize = QSize(80, 30)) -> QPushButton:
    """Create a styled button with text and optional icon.
    
    Args:
        text (str): Button text
        icon (Optional[str]): Icon name (without extension)
        size (QSize): Button size
        
    Returns:
        QPushButton: Styled button
    """
    button = QPushButton(text)
    
    if icon:
        button.setIcon(get_icon(icon))
    
    button.setMinimumSize(size)
    
    # Apply KingdomQtStyle to button
    style = KingdomQtStyle()
    button.setStyleSheet(style.get_button_style())
    
    return button

def show_message(parent: QWidget, title: str, message: str, icon: QMessageBox.Icon = QMessageBox.Icon.Information) -> None:
    """Show a message box with the specified title, message, and icon.
    
    Args:
        parent (QWidget): Parent widget
        title (str): Message box title
        message (str): Message box message
        icon (QMessageBox.Icon): Message box icon
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setIcon(icon)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    
    # Apply KingdomQtStyle to message box
    style = KingdomQtStyle()
    msg_box.setStyleSheet(style.get_dialog_style())
    
    msg_box.exec()

def show_error(parent: QWidget, title: str, message: str) -> None:
    """Show an error message box.
    
    Args:
        parent (QWidget): Parent widget
        title (str): Error message title
        message (str): Error message
    """
    show_message(parent, title, message, QMessageBox.Icon.Critical)

def show_warning(parent: QWidget, title: str, message: str) -> None:
    """Show a warning message box.
    
    Args:
        parent (QWidget): Parent widget
        title (str): Warning message title
        message (str): Warning message
    """
    show_message(parent, title, message, QMessageBox.Icon.Warning)

def show_info(parent: QWidget, title: str, message: str) -> None:
    """Show an information message box.
    
    Args:
        parent (QWidget): Parent widget
        title (str): Information message title
        message (str): Information message
    """
    show_message(parent, title, message, QMessageBox.Icon.Information)

def create_form_layout() -> QFormLayout:
    """Create a form layout with proper spacing.
    
    Returns:
        QFormLayout: Styled form layout
    """
    form = QFormLayout()
    form.setSpacing(10)
    form.setContentsMargins(10, 10, 10, 10)
    
    return form

def create_h_line() -> QFrame:
    """Create a horizontal line separator.
    
    Returns:
        QFrame: Horizontal line
    """
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    
    return line

def create_v_line() -> QFrame:
    """Create a vertical line separator.
    
    Returns:
        QFrame: Vertical line
    """
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    
    return line

def create_heading_label(text: str) -> QLabel:
    """Create a heading label with larger font.
    
    Args:
        text (str): Label text
        
    Returns:
        QLabel: Styled heading label
    """
    label = QLabel(text)
    
    # Apply KingdomQtStyle to label
    style = KingdomQtStyle()
    label.setStyleSheet(style.get_heading_style())
    
    return label

class IconButton(QPushButton):
    """Button with icon and optional text."""
    
    def __init__(self, icon_name: str, tooltip: str, text: str = "", parent: Optional[QWidget] = None):
        """Initialize the icon button.
        
        Args:
            icon_name (str): Icon name (without extension)
            tooltip (str): Button tooltip
            text (str, optional): Button text
            parent (QWidget, optional): Parent widget
        """
        super().__init__(text, parent)
        
        self.setIcon(get_icon(icon_name))
        self.setToolTip(tooltip)
        
        if not text:
            self.setIconSize(QSize(24, 24))
            self.setFixedSize(QSize(32, 32))
        
        # Apply KingdomQtStyle to button
        style = KingdomQtStyle()
        self.setStyleSheet(style.get_icon_button_style())
# Import QObject again to ensure it's available in this scope
from PyQt6.QtCore import QObject

class WorkerSignals(QObject):
    """Defines the signals available from a running worker thread.
    
    Supported signals:
    - finished: No data
    - error: tuple (exctype, value, traceback.format_exc())
    - result: object data returned from processing
    - progress: int indicating % progress or tuple with (int % progress, str status message)
    """
    finished = pyqtSignal()  # Signal when worker finishes with no return value
    error = pyqtSignal(tuple)  # Signal for error reporting with error details
    result = pyqtSignal(object)  # Signal with the worker result data
    progress = pyqtSignal(object)  # Signal for progress updates (int % or tuple with % and message)

class Worker(QObject):
    """Worker class for running tasks in a separate thread.
    
    This class is used for long-running operations in the GUI to prevent
    freezing the interface. It emits signals for progress updates and
    completion status.
    """
    
    # Define signals
    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the worker.
        
        Args:
            parent (QObject, optional): Parent object
        """
        super().__init__(parent)
        self._abort = False
        self._func = None
        self._args = None
        self._kwargs = None
        
    def set_task(self, func: Callable[..., Any], *args, **kwargs) -> None:
        """Set the task function and arguments.
        
        Args:
            func: Function to run
            *args: Function arguments
            **kwargs: Function keyword arguments
        """
        self._func = func
        self._args = args
        self._kwargs = kwargs
    
    def abort(self) -> None:
        """Abort the task."""
        self._abort = True
        
    @pyqtSlot()
    def run(self) -> None:
        """Run the task in the thread."""
        self._abort = False
        
        try:
            self.started.emit()
            
            if not self._func:
                raise ValueError("No task function set")
                
            result = self._func(*self._args, **self._kwargs)
            
            if not self._abort:
                self.result.emit(result)
                
        except Exception as e:
            if not self._abort:
                self.error.emit(str(e))
                logger.error(f"Worker error: {str(e)}")
                logger.error(traceback.format_exc())
        finally:
            if not self._abort:
                self.finished.emit()
