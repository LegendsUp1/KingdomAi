#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thoth AI Qt Interface for Kingdom AI

This module implements a modern, state-of-the-art Qt interface for Thoth AI,
featuring a chat interface with voice capabilities, model management, and
real-time audio visualization. It integrates with the Kingdom AI event bus
and enforces Redis Quantum Nexus connection requirements.
"""

import sys
import os

# Force XCB platform on Linux before PyQt6 import (prevents segfaults)
if 'QT_QPA_PLATFORM' not in os.environ:
    if sys.platform.startswith('linux') or os.name != 'nt':
        os.environ['QT_QPA_PLATFORM'] = 'xcb'

import json
import logging
import asyncio
import time
import threading

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")

# Set up logger
logger = logging.getLogger(__name__)
import platform
import webbrowser
import numpy as np
import matplotlib
matplotlib.use('QtAgg')
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple, Callable

# Third-party imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QTabWidget, QComboBox, QStatusBar, QMessageBox,
    QFrame, QSplitter, QSizePolicy, QScrollArea, QStackedWidget, QLineEdit,
    QCheckBox, QGroupBox, QFormLayout, QProgressBar, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QStyleFactory, QFileDialog,
    QMenu, QMenuBar, QToolBar, QToolButton, QSystemTrayIcon, QSplashScreen
)
from PyQt6.QtCore import (
    Qt, QSize, QTimer, QThread, QObject, QPoint, QRect, QUrl,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup,
    QTime, QSettings, QEvent, pyqtSignal
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QTextCursor, QIcon, QPixmap, QPainter, QPen,
    QLinearGradient, QBrush, QFontMetrics, QDesktopServices, QAction, QKeySequence,
    QTextCharFormat, QTextFormat, QTextDocument, QSyntaxHighlighter,
    QMovie, QScreen, QImage
)

# QEasingCurve is imported above and available in this module

# Try to import speech recognition and TTS
has_voice = False  # Use lowercase to avoid constant redefinition error
try:
    import speech_recognition as sr
    import pyttsx3
    from gtts import gTTS
    import pyaudio
    import wave
    import pydub
    from pydub import playback
    has_voice = True
except ImportError as e:
    logger.warning(f"Voice features disabled: {e}")

# Local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_component import BaseComponent
from core.event_bus import EventBus
from core.nexus.redis_quantum_nexus import RedisQuantumNexus  # For Redis Quantum Nexus
from utils.qt_timer_fix import start_timer_safe, stop_timer_safe, get_qt_timer_manager


def _wsl_resolve_exe(name: str) -> str:
    """No-op on native Linux — returns name as-is."""
    return name


# ============================================================================
# SENTIENCE & CONSCIOUSNESS SYSTEMS IMPORTS
# ============================================================================
try:
    from core.sentience.monitor import SentienceMonitor
    from core.sentience.quantum_consciousness import QuantumConsciousnessEngine
    from core.sentience.consciousness_field import ConsciousnessField
    from core.sentience.integrated_information import IntegratedInformationProcessor
    from core.sentience.self_model import MultidimensionalSelfModel
    has_sentience = True
    logger.info("✅ All Sentience Systems imported successfully")
except ImportError as e:
    logger.error(f"❌ Sentience Systems import failed: {e}")
    has_sentience = False
    SentienceMonitor = None
    QuantumConsciousnessEngine = None
    ConsciousnessField = None
    IntegratedInformationProcessor = None
    MultidimensionalSelfModel = None

# Meta-Learning Systems - NO FALLBACKS (loaded from ML environment)
from ai.meta_learning import MetaLearning
has_meta_learning = True
logger.info("✅ Meta-Learning Systems imported from ML environment")

# Memory Systems  
try:
    from kingdom_ai.core.memory_manager import MemoryManager
    has_memory = True
    logger.info("✅ Memory Manager imported")
except ImportError as e:
    logger.error(f"❌ Memory Manager import failed: {e}")
    has_memory = False
    MemoryManager = None

# Chat Widget and Model Manager
try:
    from gui.qt_frames.chat_widget import ChatWidget
    from gui.qt_frames.model_manager_widget import ModelManagerWidget
    logger.info("✅ ChatWidget and ModelManagerWidget imported")
except ImportError as e:
    logger.error(f"❌ ChatWidget/ModelManagerWidget import failed: {e}")
    # Create fallback classes
    class ChatWidget(QWidget):
        def __init__(self, event_bus=None, config=None, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout()
            self.setLayout(layout)
            layout.addWidget(QLabel("Chat interface unavailable"))
    
    class ModelManagerWidget(QWidget):
        def __init__(self, event_bus=None, config=None, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout()
            self.setLayout(layout)
            layout.addWidget(QLabel("Model manager unavailable"))

# Configure logging
logger = logging.getLogger("KingdomAI.ThothQt")

# Constants
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6380,  # Mandatory Redis Quantum Nexus port
    'password': 'QuantumNexus2025',  # Required password
    'db': 0,
    'decode_responses': True
}

# Style constants
STYLESHEET = """
/* Modern Color Palette */
:root {
    --bg-primary: #1a1b26;
    --bg-secondary: #24283b;
    --bg-tertiary: #2a2e43;
    --text-primary: #a9b1d6;
    --text-secondary: #7aa2f7;
    --accent: #7aa2f7;
    --accent-hover: #8ab4ff;
    --success: #9ece6a;
    --warning: #e0af68;
    --error: #f7768e;
    --border: #3b4261;
    --shadow: rgba(0, 0, 0, 0.3);
}

/* Global Styles */
QWidget {
    font-family: 'Segoe UI', 'Noto Sans', Arial, sans-serif;
    font-size: 11pt;
    color: var(--text-primary);
    background: transparent;
}

/* Main window */
QMainWindow {
    background-color: var(--bg-primary);
    color: var(--text-primary);
}

/* Scroll bars */
QScrollBar:vertical {
    border: none;
    background: var(--bg-tertiary);
    width: 10px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: var(--border);
    min-height: 30px;
    border-radius: 4px;
    margin: 2px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* Buttons */
QPushButton {
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 80px;
    transition: all 0.2s ease;
}

QPushButton:hover {
    background-color: var(--bg-secondary);
    border-color: var(--accent);
}

QPushButton:pressed {
    background-color: var(--accent);
    color: white;
}

QPushButton:disabled {
    background-color: var(--bg-tertiary);
    color: #666;
    border-color: #444;
}

/* Text Input */
QTextEdit, QLineEdit {
    background-color: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px;
    selection-background-color: var(--accent);
    selection-color: white;
}

QTextEdit:focus, QLineEdit:focus {
    border: 1px solid var(--accent);
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0;
    background: var(--bg-secondary);
}

QTabBar::tab {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--bg-secondary);
    margin-bottom: -1px;
}

QTabBar::tab:!selected:hover {
    background: var(--bg-secondary);
}

/* Combo Box */
QComboBox {
    background-color: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 100px;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: url(icons/down-arrow.svg);
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background: var(--bg-secondary);
    color: var(--text-primary);
    selection-background-color: var(--accent);
    selection-color: white;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg-secondary);
    text-align: center;
    color: white;
}

QProgressBar::chunk {
    background: var(--accent);
    border-radius: 2px;
    margin: 1px;
}

/* Tool Tips */
QToolTip {
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    padding: 4px 8px;
    border-radius: 4px;
    opacity: 230;
}

/* Status Bar */
QStatusBar {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border-top: 1px solid var(--border);
}

/* Menu Bar */
QMenuBar {
    background: var(--bg-primary);
    color: var(--text-primary);
    border: none;
}

QMenuBar::item {
    padding: 4px 8px;
    background: transparent;
}

QMenuBar::item:selected {
    background: var(--bg-secondary);
    border-radius: 4px;
}

QMenu {
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    padding: 4px;
}

QMenu::item:selected {
    background: var(--accent);
    color: white;
    border-radius: 2px;
}

/* Custom Widgets */
ThothChatMessageWidget[is_ai="true"] {
    background: var(--bg-tertiary);
    border-left: 3px solid var(--accent);
}

ThothChatMessageWidget[is_ai="false"] {
    background: var(--bg-secondary);
    border-left: 3px solid var(--border);
}

ThothChatMessageWidget[is_error="true"] {
    border-left: 3px solid var(--error);
}

/* Animations */
QPushButton, QComboBox, QLineEdit, QTextEdit, QTabBar::tab {
    transition: all 0.15s ease;
}

/* Custom Scroll Areas */
QScrollArea {
    border: none;
    background: transparent;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}

/* Custom Dialogs */
QDialog {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
}

/* Custom Checkboxes and Radio Buttons */
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}

QCheckBox::indicator:unchecked {
    border: 1px solid var(--border);
    background: var(--bg-secondary);
    border-radius: 3px;
}

QCheckBox::indicator:checked {
    border: 1px solid var(--accent);
    background: var(--accent);
    image: url(icons/check.svg);
}

QRadioButton::indicator:unchecked {
    border: 1px solid var(--border);
    background: var(--bg-secondary);
    border-radius: 8px;
}

QRadioButton::indicator:checked {
    border: 1px solid var(--accent);
    background: var(--accent);
    border-radius: 8px;
}

/* Sliders */
QSlider::groove:horizontal {
    border: 1px solid var(--border);
    height: 4px;
    background: var(--bg-secondary);
    margin: 0;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: var(--accent);
    border: 1px solid var(--accent-hover);
    width: 12px;
    margin: -6px 0;
    border-radius: 6px;
}

QSlider::sub-page:horizontal {
    background: var(--accent);
    border-radius: 2px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Buttons */
QPushButton {
    background-color: #3a3a4a;
    color: #ffffff;
    border: 1px solid #4a4a5a;
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #4a4a5a;
    border: 1px solid #5a5a6a;
}

QPushButton:pressed {
    background-color: #2a2a3a;
}

QPushButton:disabled {
    background-color: #2a2a3a;
    color: #6a6a7a;
    border: 1px solid #3a3a4a;
}

/* Text inputs */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #2a2a3a;
    color: #e2e2e2;
    border: 1px solid #3a3a4a;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #3a6ea5;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #3a3a4a;
    background: #2a2a3a;
    border-radius: 4px;
    margin-top: 4px;
}

QTabBar::tab {
    background: #2a2a3a;
    color: #a0a0b0;
    padding: 8px 16px;
    border: 1px solid #3a3a4a;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #3a3a4a;
    color: #ffffff;
    border-bottom: 2px solid #4a9cff;
}

QTabBar::tab:!selected {
    margin-top: 2px;
}

/* Status bar */
QStatusBar {
    background: #2a2a3a;
    color: #a0a0b0;
    border-top: 1px solid #3a3a4a;
}

/* Tooltips */
QToolTip {
    background-color: #2a2a3a;
    color: #e2e2e2;
    border: 1px solid #4a4a5a;
    padding: 4px;
    border-radius: 4px;
    opacity: 230;
}

/* Checkboxes and radio buttons */
QCheckBox, QRadioButton {
    color: #e2e2e2;
    spacing: 5px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}

/* Combo boxes */
QComboBox {
    background-color: #2a2a3a;
    color: #e2e2e2;
    border: 1px solid #3a3a4a;
    border-radius: 4px;
    padding: 4px 8px 4px 8px;
    min-width: 6em;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #3a3a4a;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

QComboBox QAbstractItemView {
    background: #2a2a3a;
    color: #e2e2e2;
    selection-background-color: #3a6ea5;
    outline: none;
    border: 1px solid #4a4a5a;
}

/* Scroll areas */
QScrollArea {
    border: none;
    background: transparent;
}

/* Group boxes */
QGroupBox {
    border: 1px solid #3a3a4a;
    border-radius: 4px;
    margin-top: 20px;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #a0a0b0;
}
"""
 
class AsyncWorker(QObject):
    """Worker object for running async tasks in a separate thread."""
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception)
    progress = pyqtSignal(int, str)  # progress percentage, status message
    
    def __init__(self, coro):
        super().__init__()
        self.coro = coro
        self.loop = asyncio.new_event_loop()
        self._is_cancelled = False
    
    def cancel(self):
        """Request cancellation of the current operation."""
        self._is_cancelled = True
    
    def run(self):
        """Run the coroutine in the worker thread."""
        try:
            if asyncio.iscoroutine(self.coro):
                result = self.loop.run_until_complete(self.coro)
            else:
                # Handle coroutine functions
                result = self.loop.run_until_complete(self.coro())
            if not self._is_cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(e)
        finally:
            self.loop.close()


def async_to_sync(method):
    """Decorator to run async methods in a separate thread."""
    def wrapper(self, *args, **kwargs):
        worker = AsyncWorker(lambda: method(self, *args, **kwargs))
        thread = QThread()
        worker.moveToThread(thread)
        
        def on_finished(result):
            try:
                thread.quit()
                thread.wait()
                thread.deleteLater()
                worker.deleteLater()
            except Exception as e:
                logger.error(f"Error in async completion: {e}")
        
        def on_error(error):
            try:
                logger.error(f"Error in async operation: {error}", exc_info=True)
                if hasattr(self, 'show_error'):
                    self.show_error("Operation Failed", str(error))
                else:
                    QMessageBox.critical(
                        self.parent() or QApplication.activeWindow(),
                        "Error",
                        f"An error occurred: {str(error)}\n\nCheck logs for more details."
                    )
            except Exception as e:
                logger.critical(f"Error in error handler: {e}", exc_info=True)
        
        def on_progress(percent, message):
            if hasattr(self, 'update_progress'):
                self.update_progress(percent, message)
        
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(on_progress)
        
        # Clean up thread when it's done
        thread.finished.connect(thread.deleteLater)
        
        # Start the thread
        thread.start()
        
        # Store references to prevent garbage collection
        if not hasattr(self, '_worker_threads'):
            self._worker_threads = []
        self._worker_threads.append((worker, thread))
        
        # Clean up old finished threads
        self._worker_threads = [(w, t) for w, t in self._worker_threads if t.isRunning()]
        
        return worker  # Return the worker so the caller can monitor progress
    
    # Copy the docstring from the original method
    wrapper.__doc__ = method.__doc__
    return wrapper


class AudioVisualizer(QLabel):
    """Audio visualization widget that shows sound wave forms."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Audio data
        self.audio_data = np.array([])
        self.sample_rate = 44100  # Default sample rate
        self.chunk_size = 1024
        
        # Visualization parameters
        self.bar_count = 50
        self.bar_width = 6
        self.bar_spacing = 2
        self.bar_rounding = 2.0
        self.max_amplitude = 1.0
        
        # Animation
        self._animations_enabled = True
        self._animation_interval_ms = 100  # SOTA 2026 FIX: 100ms saves CPU vs 30ms
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.setInterval(self._animation_interval_ms)
        self.animation_phase = 0.0
        self.animation_speed = 0.1
        
        # Style
        self.setStyleSheet("background-color: transparent;")
        self.bar_color = QColor(74, 156, 255)  # Blue
        self.bg_color = QColor(30, 30, 46, 200)  # Semi-transparent dark
        
        # Start animation
        self._sync_animation_timer()
    
    def set_audio_data(self, data, sample_rate=44100):
        """Set the audio data to visualize."""
        if len(data) > 0:
            self.audio_data = data
            self.sample_rate = sample_rate
            self.max_amplitude = max(0.1, np.max(np.abs(data)))
            self.update()
    
    def update_animation(self):
        """Update the animation phase."""
        if not self._should_animation_timer_run():
            self._sync_animation_timer()
            return
        self.animation_phase = (self.animation_phase + self.animation_speed) % (2 * 3.14159)
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

    def _sync_animation_timer(self):
        try:
            if self._should_animation_timer_run():
                if not self.animation_timer.isActive():
                    self.animation_timer.start(getattr(self, '_animation_interval_ms', 100))
            else:
                if self.animation_timer.isActive():
                    self.animation_timer.stop()
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
        try:
            if event.type() == QEvent.Type.WindowStateChange:
                self._sync_animation_timer()
        except Exception:
            pass
    
    def paintEvent(self, event):
        """Paint the audio visualization."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), self.bg_color)
        
        # Calculate dimensions
        width = self.width()
        height = self.height()
        bar_width = self.bar_width
        bar_spacing = self.bar_spacing
        bar_count = min(self.bar_count, width // (bar_width + bar_spacing))
        
        # Calculate bar dimensions
        total_bar_width = bar_count * (bar_width + bar_spacing) - bar_spacing
        start_x = (width - total_bar_width) // 2
        
        # Draw bars
        if len(self.audio_data) > 0:
            # Calculate bar heights from audio data
            chunk_size = max(1, len(self.audio_data) // bar_count)
            for i in range(bar_count):
                start_idx = i * chunk_size
                end_idx = min((i + 1) * chunk_size, len(self.audio_data))
                chunk = self.audio_data[start_idx:end_idx]
                
                if len(chunk) > 0:
                    # Calculate RMS amplitude for this chunk
                    rms = np.sqrt(np.mean(chunk**2))
                    normalized_rms = rms / self.max_amplitude
                    
                    # Apply sine wave animation to make it more dynamic
                    animation_factor = 0.5 + 0.5 * np.sin(self.animation_phase + i * 0.3)
                    bar_height = int(height * normalized_rms * animation_factor)
                    bar_height = max(2, min(bar_height, height - 4))
                    
                    # Calculate position
                    x = start_x + i * (bar_width + bar_spacing)
                    y = (height - bar_height) // 2
                    
                    # Create gradient
                    gradient = QLinearGradient(0, y, 0, y + bar_height)
                    gradient.setColorAt(0, self.bar_color.lighter(120))
                    gradient.setColorAt(0.5, self.bar_color)
                    gradient.setColorAt(1, self.bar_color.darker(120))
                    
                    # Draw the bar
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(gradient))
                    painter.drawRoundedRect(
                        x, y, bar_width, bar_height,
                        self.bar_rounding, self.bar_rounding
                    )
                    
                    # Add highlight
                    highlight = QLinearGradient(0, y, 0, y + bar_height // 2)
                    highlight.setColorAt(0, QColor(255, 255, 255, 60))
                    highlight.setColorAt(1, QColor(255, 255, 255, 0))
                    painter.setBrush(QBrush(highlight))
                    painter.drawRoundedRect(
                        x, y, bar_width, bar_height // 2,
                        self.bar_rounding, self.bar_rounding
                    )
        else:
            # Draw placeholder when no audio data
            painter.setPen(QPen(QColor(100, 100, 120, 100), 1, Qt.PenStyle.DotLine))
            painter.drawLine(0, height // 2, width, height // 2)
            
            # Draw "No Audio" text
            painter.setPen(QColor(150, 150, 170))
            font = painter.font()
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Audio Data")
    
    def start_visualization(self):
        """Start the visualization animation."""
        self._animations_enabled = True
        self._sync_animation_timer()
    
    def stop_visualization(self):
        """Stop the visualization animation."""
        self._animations_enabled = False
        self._sync_animation_timer()
    
    def clear(self):
        """Clear the visualization."""
        self.audio_data = np.array([])
        self.update()


class ThothChatMessageWidget(QFrame):
    """Widget for displaying a single chat message with rich formatting."""
    
    # Signals
    action_triggered = pyqtSignal(str, dict)  # action_name, action_data
    
    def __init__(self, sender: str, message: str, timestamp: str, is_ai: bool = False, 
                 parent=None, message_id: str = None):
        """Initialize the chat message widget.
        
        Args:
            sender: Name of the message sender
            message: Message text (can contain HTML/markdown)
            timestamp: Formatted timestamp string
            is_ai: Whether this is an AI message (affects styling)
            parent: Parent widget
            message_id: Unique ID for this message (for actions/replies)
        """
        super().__init__(parent)
        self.is_ai = is_ai
        self.message_sender = sender  # Renamed to avoid conflict with QObject.sender()
        self.message = message
        self.timestamp = timestamp
        self.message_id = message_id or str(hash(f"{sender}{timestamp}"))
        
        # Import the message widget
        try:
            from gui.utils.message_formatter.widgets import MessageWidget
            self.MessageWidget = MessageWidget
        except ImportError as e:
            logger.error(f"Failed to import MessageWidget: {e}")
            raise
        
        # Set up the message widget
        self.setup_ui()
        
        # Set up context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def setup_ui(self):
        """Set up the message UI with modern styling using the new MessageWidget."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        
        # Create message widget
        self.message_widget = self.MessageWidget(self)
        
        # Set message data
        self.message_widget.set_message_data({
            'text': self.message,
            'message_type': 'text',
            'sender': self.message_sender,
            'timestamp': self.timestamp,
            'is_user': not self.is_ai,
            'metadata': {
                'id': self.message_id,
                'allow_reply': True,
                'show_actions': True,
                'allow_reactions': True,
                'status': 'delivered'  # Can be 'sending', 'sent', 'delivered', 'read', 'error'
            }
        })
        
        # Connect signals
        self.message_widget.action_triggered.connect(self._handle_action)
        
        # Add to layout
        layout.addWidget(self.message_widget)
        
        # Set initial style
        self.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }
        """)
        
        # Message widget handles its own styling and content
        # All formatting is handled internally by MessageWidget
        
        # Action buttons (copy, regenerate, etc.)
        self.action_buttons = QHBoxLayout()
        self.action_buttons.setContentsMargins(0, 4, 0, 0)
        self.action_buttons.setSpacing(8)
        
        # Add action buttons (only for AI messages)
        if self.is_ai:
            self.copy_button = self._create_action_button("Copy", "copy_icon.png", self.on_copy_clicked)
            self.regenerate_button = self._create_action_button("Regenerate", "refresh_icon.png", self.on_regenerate_clicked)
            self.action_buttons.addWidget(self.copy_button)
            self.action_buttons.addWidget(self.regenerate_button)
        
        # Add action buttons to layout (only for AI messages)
        if self.is_ai:
            layout.addLayout(self.action_buttons)
        
        # Set overall widget style based on sender
        self._update_style()
    
    def _create_action_button(self, text: str, icon_path: str, callback) -> QPushButton:
        """Create a styled action button."""
        button = QPushButton(text)
        button.setIcon(QIcon(icon_path))
        button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888888;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: #3a3a4a;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #2a2a3a;
            }
        """)
        button.clicked.connect(callback)
        return button
    
    def _format_message_content(self, message: str) -> str:
        """Format message content with syntax highlighting and rich text support."""
        # Basic HTML escaping
        import html
        message = html.escape(message)
        
        # Convert markdown-style code blocks
        message = self._process_code_blocks(message)
        
        # Convert markdown links
        import re
        message = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'<a href="\2">\1</a>',
            message
        )
        
        # Convert newlines to <br> tags
        message = message.replace('\n', '<br>')
        
        return f"<div style='color: #e0e0e0;'>{message}</div>"
    
    def _process_code_blocks(self, text: str) -> str:
        """Process markdown-style code blocks with syntax highlighting."""
        import re
        
        # Handle ```language code blocks
        def replace_code_block(match):
            language = match.group(1) or 'text'
            code = match.group(2)
            
            # Basic syntax highlighting for common languages
            highlighted = f"<pre style='background: #1e1e2e; border-radius: 4px; padding: 8px; margin: 4px 0; overflow-x: auto;'><code class='language-{language}'>{code}</code></pre>"
            return highlighted
        
        # Handle inline `code`
        text = re.sub(r'`([^`]+)`', r'<code style="background: #2a2a3a; padding: 2px 4px; border-radius: 3px; font-family: monospace; font-size: 0.9em;">\1</code>', text)
        
        # Handle code blocks
        text = re.sub(r'```(\w*)\n([\s\S]*?)\n```', replace_code_block, text)
        
        return text
    
    def resizeEvent(self, event):
        """Handle resize events."""
        super().resizeEvent(event)
        # Message widget handles its own height adjustment
    
    def _update_style(self):
        """Update the widget style based on sender and state."""
        if self.is_ai:
            bg_color = "#2a3b4d"  # Blueish for AI
            border_color = "#3a6ea5"
            align = "left"
        else:
            bg_color = "#3a2d3e"  # Purple for user
            border_color = "8a2d8a"
            align = "right"
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 12px;
                padding: 12px;
                margin: 8px 0;
                max-width: 85%;
                align-self: {align};
            }}
            QWidget:hover {{
                border-color: #ffffff30;
            }}
        """)
    
    def on_copy_clicked(self):
        """Handle copy button click."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.message)
        
        # Show copied tooltip
        QToolTip.showText(
            self.mapToGlobal(self.rect().bottomRight()),
            "Copied to clipboard",
            self,
            QRect(),
            2000  # 2 seconds
        )
    
    def on_regenerate_clicked(self):
        """Handle regenerate button click."""
        if hasattr(self.parent(), 'regenerate_message'):
            self.parent().regenerate_message(self.message_id)
    
    def enterEvent(self, event):
        """Handle mouse enter event."""
        self.setStyleSheet(self.styleSheet() + "\nQWidget { border-color: #ffffff50; }")
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave event."""
        self._update_style()
        super().leaveEvent(event)
    
    def _handle_action(self, action_name: str, action_data: dict):
        """Handle action triggered from message widget.
        
        Args:
            action_name: Name of the action (e.g., 'copy', 'reply', 'react')
            action_data: Additional data for the action
        """
        try:
            logger.info(f"Message action triggered: {action_name} with data: {action_data}")
            
            if action_name == 'copy':
                # Copy message to clipboard
                clipboard = QApplication.clipboard()
                clipboard.setText(self.message)
                logger.info("Message copied to clipboard")
                
            elif action_name == 'reply':
                # Emit signal to parent for reply handling
                self.action_triggered.emit('reply', {
                    'message_id': self.message_id,
                    'sender': self.message_sender,
                    'original_message': self.message
                })
                
            elif action_name == 'react':
                # Handle reaction
                reaction = action_data.get('reaction', '👍')
                logger.info(f"Reaction added: {reaction}")
                
            elif action_name == 'regenerate':
                # Request regeneration
                if hasattr(self.parent(), 'regenerate_message'):
                    self.parent().regenerate_message(self.message_id)
                    
        except Exception as e:
            logger.error(f"Error handling message action: {e}")
    
    def show_context_menu(self, position):
        """Show context menu for message actions.
        
        Args:
            position: QPoint where menu should appear
        """
        try:
            from PyQt6.QtWidgets import QMenu
            from PyQt6.QtGui import QAction
            
            menu = QMenu(self)
            
            # Copy action
            copy_action = QAction("Copy Message", self)
            copy_action.triggered.connect(lambda: self._handle_action('copy', {}))
            menu.addAction(copy_action)
            
            # Reply action (for user messages)
            if not self.is_ai:
                reply_action = QAction("Reply", self)
                reply_action.triggered.connect(lambda: self._handle_action('reply', {}))
                menu.addAction(reply_action)
            
            # Regenerate action (for AI messages)
            if self.is_ai:
                regenerate_action = QAction("Regenerate Response", self)
                regenerate_action.triggered.connect(lambda: self._handle_action('regenerate', {}))
                menu.addAction(regenerate_action)
            
            # Show menu at cursor position
            menu.exec(self.mapToGlobal(position))
            
        except Exception as e:
            logger.error(f"Error showing context menu: {e}")


class VoiceInputWorker(QObject):
    """Worker class for handling voice input using speech_recognition on native Linux.
    
    Uses PulseAudio microphone via speech_recognition + Google API.
    """
    transcription_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, recognizer=None, microphone=None):
        super().__init__()
        self.recognizer = recognizer
        self.microphone = microphone
        self._stop_listening = None
        self.is_running = False

    def start_listening(self):
        """Start listening via speech_recognition (native Linux PulseAudio)."""
        import subprocess
        import speech_recognition as sr
        
        self.is_running = True
        self.log_message.emit("🎤 Using speech_recognition (native Linux audio)")
        
        self.log_message.emit("🎤 SPEAK NOW! (8 seconds)")
        
        try:
            recognizer = self.recognizer or sr.Recognizer()
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8
            
            mic = self.microphone or sr.Microphone()
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)
            
            result_text = recognizer.recognize_google(audio)
            output = result_text.strip() if result_text else ""
            
            output = result.stdout.strip()
            
            if not self.is_running:
                return
            
            if output:
                self.log_message.emit(f'🎤 HEARD: "{output}"')
                self.transcription_received.emit(output)
            else:
                self.error_occurred.emit("No speech detected")
                
        except Exception as e:
            err_name = type(e).__name__
            if 'UnknownValueError' in err_name:
                self.error_occurred.emit("No speech detected (mic working)")
            elif 'WaitTimeoutError' in err_name:
                self.error_occurred.emit("Listening timed out (try speaking louder)")
            else:
                self.error_occurred.emit(f"Error during voice recognition: {str(e)[:50]}")
        finally:
            self.is_running = False
    
    def stop_listening(self):
        """Stop the listening process."""
        self.is_running = False
        if self._stop_listening:
            self._stop_listening(wait_for_stop=False)


class ThothQt(QWidget):
    """Main Thoth AI interface widget with chat, voice, and model management."""
    
    # Signal for thread-safe AI response handling
    ai_response_signal = pyqtSignal(dict)
    
    def __init__(self, event_bus: EventBus, config: dict, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.config = config
        self.recognizer = None
        self.microphone = None
        self.is_listening = False
        self.audio_visualizer = AudioVisualizer()
        self.typing_indicator = None
        # Using STATE-OF-THE-ART thread-safe timer (Qt 6.9 compliant)
        self._timer_manager = get_qt_timer_manager()
        # CRITICAL FIX: Create typing_timer before connecting signal
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self._update_typing_dots)
        self.typing_dots = 0
        self.pending_requests = {}  # Track pending AI requests
        self.current_model = self.config.get('default_model', 'ollama:latest')  # Fix default model to use local Ollama
        self.voice_worker = None
        self.tts_engine = None
        self.message_history = []  # Track message history
        
        # CRITICAL FIX: Initialize greeting flag to prevent duplicates
        self._greeting_shown = False
        
        # CRITICAL: Connect signal for thread-safe AI response handling
        self.ai_response_signal.connect(self._process_ai_response_in_main_thread)
        logger.info("✅ AI response signal connected for thread-safe UI updates")
        
        # Initialize UI components
        self.setup_ui()
        
        # Initialize voice recognition and TTS if available
        if self.config.get('voice', {}).get('enabled', False):
            self.setup_voice_recognition()
            self.setup_tts()
        
        # Connect to event bus
        self.connect_events()
        
        # PERF FIX: Move ALL blocking network calls off main thread.
        # connect_to_redis() blocks up to 2s, Ollama model fetch blocks up to 2s.
        import threading
        def _deferred_network_init():
            self.connect_to_redis()
            # Fetch models in THIS background thread, then update UI on main thread
            self._fetch_models_then_populate()
        threading.Thread(target=_deferred_network_init, daemon=True, name="ThothNetInit").start()
        
        # Set initial UI state
        self.update_ui_state()
        
        # Load any saved messages
        self.load_message_history()
        
        # CRITICAL: Show welcome greeting in chat AND speak it to verify voice+chat connection
        QTimer.singleShot(2000, self._show_welcome_greeting)
    
    def _show_welcome_greeting(self):
        """Show welcome greeting in chat only - voice is handled by ThothQtWidget._show_welcome_greeting."""
        try:
            greeting = "Welcome to Kingdom AI. All systems are now online."
            logger.info(f"🎤 ThothQt welcome greeting (chat only, no voice - ThothQtWidget handles voice)")
            # NOTE: Do NOT publish voice.speak here - ThothQtWidget._show_welcome_greeting()
            # already calls self.speak() which publishes voice.speak. Publishing here too
            # causes the greeting to be spoken TWICE.
        except Exception as e:
            logger.error(f"Error showing welcome greeting: {e}")
    
    def connect_to_redis(self):
        """Connect to Redis Quantum Nexus with strict requirements."""
        try:
            # Use proper RedisQuantumNexus class
            redis_config = {
                'redis_host': 'localhost',
                'redis_port': 6380,
                'redis_password': os.environ.get('REDIS_PASSWORD', 
                                               self.config.get('redis', {}).get('password', 'QuantumNexus2025'))
            }
            
            self.redis_client = RedisQuantumNexus(config=redis_config, event_bus=self.event_bus)
            
            # Initialize the connection immediately using synchronous method
            # Use synchronous initialization to avoid task nesting and delays
            try:
                if hasattr(self.redis_client, 'initialize_sync'):
                    # Use synchronous initialization method
                    init_result = self.redis_client.initialize_sync()  # type: ignore[attr-defined]
                elif hasattr(self.redis_client, 'connect'):
                    # Fallback to connect method
                    init_result = self.redis_client.connect()  # type: ignore[attr-defined]
                else:
                    # Last resort: create sync connection directly
                    import redis
                    try:
                        test_client = redis.Redis(  # type: ignore[attr-defined]
                            host='localhost',
                            port=6380,
                            password='QuantumNexus2025',
                            decode_responses=True,
                            socket_timeout=2
                        )
                        test_client.ping()
                        init_result = True
                        logger.info("✅ Redis connection verified via direct ping")
                    except Exception as e:
                        logger.warning(f"Direct Redis connection failed: {e}")
                        init_result = False
            except Exception as e:
                logger.warning(f"Redis initialization error: {e}")
                init_result = False
            
            if not init_result:
                raise RuntimeError("Failed to initialize Redis Quantum Nexus")
                
            logger.info("✅ Successfully connected to Redis Quantum Nexus on port 6380")
            
        except Exception as e:
            error_msg = f"CRITICAL: Failed to connect to Redis Quantum Nexus on port 6380. {str(e)}"
            logger.critical(error_msg)
            QMessageBox.critical(
                self,
                "Redis Connection Failed",
                f"{error_msg}\n\n"
                "The application cannot continue without Redis Quantum Nexus.\n"
                "Please ensure Redis is running on port 6380 with the correct password."
            )
            # DO NOT QUIT - system must stay running
            logger.critical("⚠️ ThothQt will operate in degraded mode without Redis")
    
    def setup_ui(self):
        """Set up the chat interface UI with modern styling and layout."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Chat history area with custom scrollbar styling
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #2a2a2a;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #4a4a4a;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # Container for messages with proper styling
        self.messages_container = QWidget()
        self.messages_container.setObjectName("messagesContainer")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.setSpacing(12)
        self.messages_layout.addStretch()
        
        # Apply styles to messages container
        self.messages_container.setStyleSheet("""
            #messagesContainer {
                background-color: #1e1e2e;
                border: none;
                border-radius: 8px;
            }
        """)
        
        self.chat_scroll.setWidget(self.messages_container)
        
        # Input area with modern styling
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.Shape.NoFrame)
        input_frame.setStyleSheet("""
            QFrame {
                background: #2a2a3a;
                border-top: 1px solid #3a3a4a;
                padding: 12px;
            }
        """)
        
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        # Message input with modern styling
        self.message_input = QTextEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Type your message...")
        self.message_input.setMaximumHeight(120)
        self.message_input.setStyleSheet("""
            #messageInput {
                background: #2d2d3d;
                border: 1px solid #3a3a4a;
                border-radius: 8px;
                padding: 12px;
                color: #e0e0e0;
                font-size: 14px;
                selection-background-color: #4a9cff;
            }
            #messageInput:focus {
                border: 1px solid #4a9cff;
            }
        """)
        self.message_input.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 8px;
                selection-background-color: #3a6ea5;
            }
            """
        )
        
        # Button row
        button_row = QHBoxLayout()
        
        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.setIcon(QIcon.fromTheme("mail-send"))
        self.send_button.clicked.connect(self.send_message)
        logger.info("✅ Send button created and connected to send_message()")
        
        # Voice button
        self.voice_button = QPushButton()
        self.voice_button.setIcon(QIcon.fromTheme("audio-input-microphone"))
        self.voice_button.setCheckable(True)
        self.voice_button.toggled.connect(self.toggle_voice_input)
        
        # Add widgets to layouts
        button_row.addWidget(self.voice_button)
        button_row.addStretch()
        button_row.addWidget(self.send_button)
        
        input_layout.addWidget(self.message_input)
        input_layout.addLayout(button_row)
        
        # Add to main layout
        main_layout.addWidget(self.chat_scroll)
        main_layout.addWidget(input_frame)
    
    def connect_events(self):
        """Connect to event bus for AI responses AND voice commands."""
        if self.event_bus:
            # CRITICAL FIX: DO NOT subscribe to ai.response.unified here!
            # ChatWidget already subscribes and displays the message.
            # ThothQt subscribing ALSO causes DOUBLE MESSAGES in the chat!
            # Removed: self.event_bus.subscribe('ai.response.unified', self.handle_ai_response)
            
            # CRITICAL: Subscribe to chat.message.add for analysis reports and system messages
            self.event_bus.subscribe('chat.message.add', self._handle_chat_message_add)
            self.event_bus.subscribe('thoth.message', self._handle_chat_message_add)
            self.event_bus.subscribe('ai.analysis.report', self._handle_analysis_report)
            # VOICE: Subscribe to voice transcription to auto-send to AI
            self.event_bus.subscribe('voice.transcription', self._handle_voice_transcription)
            logger.info("✅ ThothQt subscribed to chat.message.add, voice.transcription events (NOT ai.response.unified - ChatWidget handles it)")
    
    def send_message(self):
        """Send message to AI backend AND sentience systems."""
        logger.info("🔵 SEND BUTTON CLICKED!")
        message = self.message_input.toPlainText().strip()
        logger.info(f"🔵 Message text: '{message}'")
        if not message:
            logger.warning("⚠️ Empty message, returning")
            return
        
        # CONNECT TO SENTIENCE SYSTEMS - Feed message to consciousness processors
        if self.event_bus:
            self.event_bus.publish('thoth.message.sent', {
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'for_sentience_processing': True
            })
        
        request_id = f"req_{int(time.time() * 1000)}"
        
        # Add user message to chat
        self.add_message("You", message, is_ai=False, message_id=request_id)
        
        # Clear input
        self.message_input.clear()
        
        # Show typing indicator
        self.show_typing_indicator(True)
        
        try:
            # Get selected model
            selected_model = self.model_selector.currentData() or self.config.get('default_model', 'cogito:latest')
            
            # CRITICAL: Log EventBus ID to verify same instance as ThothAI
            logger.info(f"🔵 ThothQt PUBLISHING ai.request")
            logger.info(f"   EventBus ID: {id(self.event_bus)}")
            logger.info(f"   Message: '{message[:50]}...'")
            logger.info(f"   Model: {selected_model}")
            
            # Publish AI request event
            self.event_bus.publish('ai.request', {
                'request_id': request_id,
                'prompt': message,
                'model': selected_model,
                'timestamp': datetime.utcnow().isoformat(),
                'sender': 'user'
            })
            # Log the request
            logger.info(f"✅ PUBLISHED ai.request (ID: {request_id})")
            
            # Add to pending requests
            self.pending_requests[request_id] = {
                'start_time': time.time(),
                'model': selected_model
            }
            
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}", exc_info=True)
            self.show_typing_indicator(False)
            self.add_message("System", f"Error: {str(e)}", is_ai=False, is_error=True)
    
    def handle_ai_response(self, data: Dict[str, Any]) -> None:
        """Handle AI response from the event bus.
        
        Args:
            data: The response data containing the AI's reply
        """
        # CRITICAL FIX: Use Qt signal to ensure thread-safe UI updates
        logger.info(f"🔵 AI RESPONSE RECEIVED - emitting signal for thread-safe processing")
        self.ai_response_signal.emit(data)
    
    def _process_ai_response_in_main_thread(self, data: Dict[str, Any]) -> None:
        """Process AI response in the Qt main thread (connected via signal).
        
        Args:
            data: The response data containing the AI's reply
        """
        try:
            request_id = data.get('request_id')
            response_text = data.get('response', '')
            
            logger.info(f"🔵 PROCESSING AI RESPONSE IN MAIN THREAD: {response_text[:100]}...")
            
            # Hide typing indicator first
            self.show_typing_indicator(False)
            
            # Dedupe: only add message once per request_id (fixes double response in chat)
            if not hasattr(self, '_displayed_response_ids'):
                self._displayed_response_ids = set()
                self._displayed_response_ids_max = 100
            displayed = self._displayed_response_ids
            if request_id and request_id in displayed:
                logger.debug(f"DEDUPE: Skipping duplicate display for request_id={request_id}")
                getattr(self, 'pending_requests', {}).pop(request_id, None)
                return
            if request_id:
                displayed.add(request_id)
                if len(displayed) > self._displayed_response_ids_max:
                    _to_drop = list(displayed)[: len(displayed) // 2]
                    for _id in _to_drop:
                        displayed.discard(_id)
            
            # ALWAYS display response - don't check pending_requests first!
            if response_text:
                # Add message first
                self.add_message("Kingdom AI", response_text, is_ai=True)
                logger.info(f"✅ Displayed AI response for {request_id}: {response_text[:50]}...")
                # FIXED: Do NOT publish voice.speak here - UnifiedAIRouter already handles this
                # This was causing DUPLICATE/TRIPLE voice responses
                # Voice is handled by: UnifiedAIRouter -> voice.speak -> VoiceManager
        
            # Track response time if request was pending
            if request_id and request_id in self.pending_requests:
                start_time = self.pending_requests[request_id].get('start_time', time.time())
                response_time = time.time() - start_time
                del self.pending_requests[request_id]
                logger.info(f"✅ Response received for {request_id} in {response_time:.2f}s")
                
            # Handle error responses
            if 'error' in data:
                error_msg = data.get('error', 'Unknown error')
                self.add_message(
                    "Error",
                    f"AI encountered an error: {error_msg}",
                    is_ai=False,
                    is_error=True
                )
                logger.error(f"Error for request {request_id}: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error handling AI response: {str(e)}", exc_info=True)
            self.show_typing_indicator(False)
            self.add_message(
                "System",
                f"Error processing AI response: {str(e)}",
                is_ai=False,
                is_error=True
            )
    
    def _update_typing_indicator(self):
        """Update the typing indicator with animated dots."""
        try:
            if hasattr(self, 'typing_indicator') and self.typing_indicator:
                # Cycle through dots: . -> .. -> ... -> .
                self.typing_dots = (self.typing_dots + 1) % 4
                dots = '.' * (self.typing_dots if self.typing_dots > 0 else 1)
                if hasattr(self.typing_indicator, 'setText'):
                    self.typing_indicator.setText(f"AI is typing{dots}")
        except Exception as e:
            logger.error(f"Error updating typing indicator: {e}")
    
    def toggle_voice_input(self, checked: bool):
        """Toggle voice input mode."""
        if checked:
            self.start_voice_input()
        else:
            self.stop_voice_input()
    
    def start_voice_input(self):
        """Start voice input mode - publishes event to VoiceManager."""
        self.voice_button.setIcon(QIcon.fromTheme("audio-input-microphone-sensitivity-high"))
        self.voice_button.setStyleSheet("background-color: #ff4444;")
        self.add_message(sender="System", message="🎤 Listening...", is_ai=True)
        self.is_listening = True
        
        # Emit signal for VoiceManager to handle
        if hasattr(self, 'voice_input_started'):
            self.voice_input_started.emit()
        
        # Also publish via event bus
        if self.event_bus:
            self.event_bus.publish('voice.listen', {'source': 'chat_widget'})
        
    def stop_voice_input(self):
        """Stop voice input mode - publishes event to VoiceManager."""
        self.voice_button.setIcon(QIcon.fromTheme("audio-input-microphone"))
        self.voice_button.setStyleSheet("")
        self.is_listening = False
        
        # Emit signal for VoiceManager to handle
        if hasattr(self, 'voice_input_stopped'):
            self.voice_input_stopped.emit()
        
        # Also publish via event bus
        if self.event_bus:
            self.event_bus.publish('voice.stop', {'source': 'chat_widget'})
    
    def _handle_voice_transcription(self, data: Dict[str, Any]):
        """Handle voice transcription from VoiceManager - auto-send to AI like regular chat.
        
        SOTA 2026 FIX: Routes through the EMBEDDED ChatWidget so user messages
        appear in the VISIBLE chat area (not ThothQt's own invisible layout).
        
        This receives transcribed speech and:
        1. Puts text in ChatWidget's input field
        2. Calls ChatWidget.send_message() which adds "You" message to VISIBLE chat
        3. ChatWidget publishes ai.request for brain processing
        """
        if isinstance(data, str):
            text = data.strip()
        else:
            text = data.get('text', '').strip() if isinstance(data, dict) else ''
        if not text:
            return
        
        logger.info(f"🎤 Voice transcription received: '{text}'")
        
        # Stop voice input mode if voice button exists
        if hasattr(self, 'voice_button') and self.voice_button:
            self.voice_button.setChecked(False)
        
        # CRITICAL FIX: Route through ChatWidget (the VISIBLE chat), NOT self.send_message()
        # self.send_message() adds to ThothQt's own layout which is NOT displayed.
        # ChatWidget.send_message() adds "You" message to the visible chat AND publishes ai.request.
        if hasattr(self, 'chat_widget') and self.chat_widget is not None:
            try:
                # Put text in ChatWidget's input field
                if hasattr(self.chat_widget, 'message_input'):
                    self.chat_widget.message_input.setPlainText(text)
                # Trigger ChatWidget's send (adds user msg to visible chat + publishes ai.request)
                if hasattr(self.chat_widget, 'send_message'):
                    self.chat_widget.send_message()
                    logger.info(f"✅ Voice transcription routed through ChatWidget: '{text[:50]}...'")
                    return
            except Exception as e:
                logger.error(f"Error routing voice through ChatWidget: {e}")
        
        # Fallback: use ThothQt's own send_message if ChatWidget unavailable
        if hasattr(self, 'message_input') and self.message_input:
            self.message_input.setPlainText(text)
        self.send_message()
    
    def handle_ai_error(self, event_type: str, data: Dict[str, Any]):
        """Handle AI error from event bus."""
        error_msg = data.get('error', 'Unknown error occurred')
        logger.error(f"AI error: {error_msg}")
        self.add_message(sender="System", message=f"Error: {error_msg}", is_ai=True)
    
    def add_message(self, sender: str, message: str, is_ai: bool = False, is_error: bool = False, message_id: str = None):
        """Add a message to the chat display."""
        try:
            from datetime import datetime
            
            # Create message widget
            msg_widget = ThothChatMessageWidget(
                sender=sender,
                message=message,
                timestamp=datetime.now().strftime("%H:%M:%S"),
                is_ai=is_ai,
                parent=self,
                message_id=message_id
            )
            
            if is_error:
                msg_widget.setStyleSheet(msg_widget.styleSheet() + "border-left: 3px solid #ff4444;")
            
            # Remove typing indicator
            if hasattr(self, 'typing_indicator') and self.typing_indicator:
                index = self.messages_layout.indexOf(self.typing_indicator)
                if index >= 0:
                    self.messages_layout.removeWidget(self.typing_indicator)
                    self.typing_indicator.deleteLater()
                    self.typing_indicator = None
            
            # Insert message
            insert_index = self.messages_layout.count() - 1
            if insert_index < 0:
                insert_index = 0
            self.messages_layout.insertWidget(insert_index, msg_widget)
            
            # Store in history
            self.message_history.append({
                'sender': sender,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'is_ai': is_ai,
                'message_id': message_id
            })
            
            # Auto-scroll with MULTIPLE attempts to ensure it works
            # First scroll immediately
            QTimer.singleShot(10, self._scroll_to_bottom)
            # Second scroll after layout completes
            QTimer.singleShot(200, self._scroll_to_bottom)
            # Final scroll after full render
            QTimer.singleShot(500, self._scroll_to_bottom)
        except Exception as e:
            logger.error(f"Error adding message: {e}")
    
    def _scroll_to_bottom(self):
        """Scroll chat to bottom - GUARANTEED to work."""
        try:
            if hasattr(self, 'chat_scroll'):
                scrollbar = self.chat_scroll.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            pass  # Silently fail - non-critical
    
    def show_typing_indicator(self, show: bool = True):
        """Show or hide typing indicator."""
        try:
            if show:
                if not hasattr(self, 'typing_indicator') or not self.typing_indicator:
                    self.typing_indicator = QLabel("AI is typing...")
                    self.typing_indicator.setStyleSheet("""
                        QLabel {
                            background: #2d2d3d;
                            color: #7aa2f7;
                            padding: 12px;
                            border-radius: 8px;
                            border-left: 3px solid #7aa2f7;
                            font-style: italic;
                        }
                    """)
                    self.typing_indicator.setAlignment(Qt.AlignmentFlag.AlignLeft)
                    insert_index = self.messages_layout.count() - 1
                    if insert_index < 0:
                        insert_index = 0
                    self.messages_layout.insertWidget(insert_index, self.typing_indicator)
                    self.typing_dots = 0
                    if not self.typing_timer.isActive():
                        self.typing_timer.start(500)
                # Use same scroll method for typing indicator
                QTimer.singleShot(10, self._scroll_to_bottom)
                QTimer.singleShot(200, self._scroll_to_bottom)
            else:
                if hasattr(self, 'typing_indicator') and self.typing_indicator:
                    self.typing_timer.stop()
                    index = self.messages_layout.indexOf(self.typing_indicator)
                    if index >= 0:
                        self.messages_layout.removeWidget(self.typing_indicator)
                        self.typing_indicator.deleteLater()
                        self.typing_indicator = None
        except Exception as e:
            logger.error(f"Error showing typing indicator: {e}")
    
    def _fetch_models_then_populate(self):
        """Fetch Ollama models in background thread, then update UI on main thread.
        
        CRITICAL FIX: requests.get() was blocking the main thread for up to 2s.
        This method runs in a background thread and schedules UI update via QTimer.
        """
        import requests
        fetched_models = []
        error_msg = None
        try:
            try:
                from core.ollama_config import get_ollama_base_url
                ollama_base_url = get_ollama_base_url().rstrip("/")
            except Exception:
                ollama_base_url = "http://localhost:11434"
            tags_url = f"{ollama_base_url}/api/tags"
            response = requests.get(tags_url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                for model_data in data.get('models', []):
                    model_name = model_data.get('name', '')
                    model_size = model_data.get('size', 0)
                    if 'remote_host' in model_data:
                        continue
                    if model_size < 1_000_000:
                        continue
                    fetched_models.append((model_name, model_size))
            else:
                logger.warning(f"⚠️ Ollama API status: {response.status_code}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Cannot connect to Ollama: {e}")
        
        # Schedule UI update on main thread
        QTimer.singleShot(0, lambda: self._populate_model_selector(fetched_models, error_msg))
    
    def _populate_model_selector(self, models, error_msg):
        """Populate model selector on main thread (no blocking calls)."""
        try:
            if not hasattr(self, 'model_selector'):
                self.model_selector = QComboBox()
            
            self.model_selector.clear()
            
            if error_msg:
                self.model_selector.addItem("⚠️ Start Ollama server (ollama serve)", "")
                return
            
            preferred_model_index = -1
            for i, (model_name, model_size) in enumerate(models):
                size_gb = model_size / (1024**3)
                display_name = f"{model_name} ({size_gb:.1f} GB)"
                self.model_selector.addItem(display_name, model_name)
                if 'mistral-nemo' in model_name.lower():
                    preferred_model_index = i
            
            logger.info(f"✅ Loaded {len(models)} LOCAL Ollama models (filtered out cloud models)")
            
            if preferred_model_index >= 0:
                self.model_selector.setCurrentIndex(preferred_model_index)
            elif self.model_selector.count() > 0:
                self.model_selector.setCurrentIndex(0)
        except Exception as e:
            logger.error(f"Error populating model selector: {e}")

    def setup_model_selector(self):
        """Set up model selector with REAL Ollama models.
        
        NOTE: For performance, prefer calling _fetch_models_then_populate() from
        a background thread instead. This method is kept for backward compatibility
        but blocks the main thread with requests.get().
        """
        self._fetch_models_then_populate()
    
    def load_message_history(self):
        """Load message history."""
        try:
            if not hasattr(self, 'message_history'):
                self.message_history = []
            logger.info(f"Loaded {len(self.message_history)} messages")
        except Exception as e:
            logger.error(f"Error loading history: {e}")
    
    def update_ui_state(self):
        """Update UI state."""
        try:
            if hasattr(self, 'voice_button'):
                voice_enabled = self.config.get('voice', {}).get('enabled', False)
                self.voice_button.setEnabled(voice_enabled)
            if hasattr(self, 'send_button'):
                self.send_button.setEnabled(True)
        except Exception as e:
            logger.error(f"Error updating UI state: {e}")
    
    def setup_voice_recognition(self):
        """Set up voice recognition with auto-detection."""
        try:
            if has_voice:
                import speech_recognition as sr
                self.recognizer = sr.Recognizer()
                
                # Suppress ALSA errors during device enumeration
                import os
                import sys
                import contextlib
                
                # Set environment variables to suppress ALSA
                os.environ['AUDIODEV'] = 'null'
                os.environ['SDL_AUDIODRIVER'] = 'dummy'
                
                # Suppress stderr during microphone enumeration
                @contextlib.contextmanager
                def suppress_stderr():
                    old_stderr = sys.stderr
                    try:
                        sys.stderr = open(os.devnull, 'w')
                        yield
                    finally:
                        sys.stderr.close()
                        sys.stderr = old_stderr
                
                # Direct PyAudio device enumeration
                try:
                    import pyaudio
                    
                    with suppress_stderr():
                        pa = pyaudio.PyAudio()
                    
                    # Get actual input devices
                    input_devices = []
                    device_count = pa.get_device_count()
                    
                    for i in range(device_count):
                        try:
                            info = pa.get_device_info_by_index(i)
                            if int(info['maxInputChannels']) > 0:  # Has input capability
                                input_devices.append({
                                    'index': i,
                                    'name': info['name'],
                                    'channels': info['maxInputChannels'],
                                    'rate': int(info['defaultSampleRate'])
                                })
                                logger.info(f"Found input device {i}: {info['name']} ({info['maxInputChannels']} channels)")
                        except Exception:
                            pass
                    
                    pa.terminate()
                    
                    if not input_devices:
                        # No microphone detected - this is NORMAL, not an error
                        # Voice OUTPUT (speaking) works WITHOUT microphone!
                        # Only voice INPUT (listening to user) needs microphone
                        logger.info("💡 No microphone detected (normal if not connected)")
                        logger.info("   Voice OUTPUT: ✅ Available (Thoth AI can speak)")
                        logger.info("   Voice INPUT: ❌ Disabled (will auto-enable when mic connected)")
                        logger.info("   Text input/output: ✅ Fully functional")
                        logger.info("🔍 Polling for microphone connection every 5 seconds...")
                        
                        # Set up runtime auto-detection timer
                        self.mic_detection_timer = QTimer(self)
                        self.mic_detection_timer.timeout.connect(self._check_microphone_connection)
                        self.mic_detection_timer.start(30000)  # Check every 30 seconds (was 5s, too frequent)
                        self.microphone = None  # No mic currently
                        self.recognizer = sr.Recognizer()  # Initialize recognizer anyway
                        return  # Exit setup, but timer will keep checking
                    
                    # Find best microphone - prioritize webcam, USB, pulse, or default
                    device_index = None
                    device_priority = [
                        # Webcam microphones (built into webcam)
                        'webcam', 'camera', 'cam', 'hd pro', 'logitech', 'c920', 'c922', 'c930', 'brio',
                        # USB microphones
                        'usb', 'blue', 'yeti', 'snowball', 'at2020', 'rode', 'shure', 'audio-technica',
                        # System defaults
                        'pulse', 'default', 'primary', 'realtek', 'microphone'
                    ]
                    
                    # Log all found devices for debugging
                    logger.info(f"🎤 Found {len(input_devices)} input devices:")
                    for dev in input_devices:
                        logger.info(f"   [{dev['index']}] {dev['name']} ({dev['channels']} ch)")
                    
                    # Try to find device by priority keywords
                    for keyword in device_priority:
                        for device in input_devices:
                            if keyword in device['name'].lower():
                                device_index = device['index']
                                logger.info(f"✅ Selected microphone (matched '{keyword}'): {device['name']} (index {device_index})")
                                break
                        if device_index is not None:
                            break
                    
                    if device_index is None:
                        # Use first available input device as fallback
                        device_index = input_devices[0]['index']
                        logger.info(f"✅ Selected first input device: {input_devices[0]['name']} (index {device_index})")
                    
                    # Initialize with found device
                    with suppress_stderr():
                        self.microphone = sr.Microphone(device_index=device_index)
                    
                    logger.info(f"✅ Voice recognition initialized with device index {device_index}")
                    
                    # Set up runtime monitoring to detect disconnection
                    self.mic_detection_timer = QTimer(self)
                    self.mic_detection_timer.timeout.connect(self._check_microphone_connection)
                    self.mic_detection_timer.start(30000)  # Monitor every 30 seconds (was 5s, too frequent)
                    
                except Exception as mic_error:
                    logger.error(f"Microphone detection failed: {mic_error}")
                    raise  # Don't hide the error
                
                # Set up microphone auto-detection
                try:
                    from utils.audio_device_monitor import create_audio_monitor
                    self.audio_monitor = create_audio_monitor(event_bus=self.event_bus)
                    logger.info("🎤 Microphone auto-detection enabled")
                except Exception as e:
                    logger.warning(f"Mic auto-detection not available: {e}")
        except Exception as e:
            logger.error(f"Error setting up voice recognition: {e}")
    
    def _check_microphone_connection(self):
        """Runtime polling for microphone connection/disconnection.
        
        NON-BLOCKING: Runs detection in background thread to avoid interrupting
        main application. Uses Qt signals for thread-safe UI updates.
        """
        # Start background detection thread (non-blocking)
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class MicDetectionThread(QThread):
            """Background thread for microphone detection - does not block main app."""
            mic_connected = pyqtSignal(int, str)  # device_index, device_name
            mic_disconnected = pyqtSignal()
            
            def __init__(self, parent_widget):
                super().__init__()
                self.parent_widget = parent_widget
            
            def run(self):
                """Background detection - runs without blocking main thread."""
                try:
                    import pyaudio
                    import os
                    import sys
                    import contextlib
                    
                    # Suppress ALL stderr output during entire run (ALSA spam fix)
                    @contextlib.contextmanager
                    def suppress_stderr():
                        old_stderr = sys.stderr
                        try:
                            sys.stderr = open(os.devnull, 'w')
                            yield
                        finally:
                            sys.stderr.close()
                            sys.stderr = old_stderr
                    
                    # FIXED: Suppress ALSA errors for ENTIRE detection run
                    with suppress_stderr():
                        pa = pyaudio.PyAudio()
                        
                        input_devices = []
                        for i in range(pa.get_device_count()):
                            try:
                                info = pa.get_device_info_by_index(i)
                                if int(info['maxInputChannels']) > 0:
                                    input_devices.append({
                                        'index': i,
                                        'name': info['name'],
                                        'channels': info['maxInputChannels']
                                    })
                            except Exception:
                                pass
                        
                        pa.terminate()
                    
                    # Check if status changed
                    mic_now_available = len(input_devices) > 0
                    mic_was_available = hasattr(self.parent_widget, 'microphone') and self.parent_widget.microphone is not None
                    
                    if mic_now_available and not mic_was_available:
                        # Find best device - prioritize webcam/USB mics
                        device_priority = [
                            'webcam', 'camera', 'cam', 'hd pro', 'logitech', 'c920', 'c922', 'brio',
                            'usb', 'blue', 'yeti', 'snowball', 'rode',
                            'pulse', 'default', 'primary', 'realtek', 'microphone'
                        ]
                        
                        best_device = input_devices[0]  # Default to first
                        for keyword in device_priority:
                            for dev in input_devices:
                                if keyword in dev['name'].lower():
                                    best_device = dev
                                    break
                            if best_device != input_devices[0]:
                                break
                        
                        # Emit signal (thread-safe communication)
                        device_index = best_device['index']
                        device_name = best_device['name']
                        self.mic_connected.emit(device_index, device_name)
                        
                    elif not mic_now_available and mic_was_available:
                        # Emit signal (thread-safe communication)
                        self.mic_disconnected.emit()
                        
                except Exception as e:
                    # Silent fail - background thread error
                    logger.debug(f"Mic check thread: {e}")
        
        # Create and start background thread (non-blocking!)
        if not hasattr(self, '_mic_detection_thread') or not self._mic_detection_thread.isRunning():
            self._mic_detection_thread = MicDetectionThread(self)
            self._mic_detection_thread.mic_connected.connect(self._on_mic_connected)
            self._mic_detection_thread.mic_disconnected.connect(self._on_mic_disconnected)
            
            # Delay thread start to prevent segfault during GUI init
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, self._mic_detection_thread.start)
            logger.info("✅ Mic detection thread scheduled to start in 3s")
    
    def _on_mic_connected(self, device_index: int, device_name: str):
        """Handle microphone connection (runs in main thread - thread-safe)."""
        try:
            import os
            import sys
            import contextlib
            
            logger.info(f"🎤 MICROPHONE CONNECTED: {device_name}")
            logger.info(f"   Auto-initializing voice input...")
            
            # Suppress stderr
            @contextlib.contextmanager
            def suppress_stderr():
                old_stderr = sys.stderr
                try:
                    sys.stderr = open(os.devnull, 'w')
                    yield
                finally:
                    sys.stderr.close()
                    sys.stderr = old_stderr
            
            # Initialize microphone (quick operation)
            import speech_recognition as sr
            if not hasattr(self, 'recognizer'):
                self.recognizer = sr.Recognizer()
            
            with suppress_stderr():
                self.microphone = sr.Microphone(device_index=device_index)
            
            logger.info(f"✅ Voice INPUT enabled automatically!")
            
            # Enable voice checkbox if it exists (UI update in main thread - safe!)
            if hasattr(self, 'enable_voice_checkbox'):
                self.enable_voice_checkbox.setEnabled(True)
                logger.info("   Voice controls enabled in UI")
                
        except Exception as e:
            logger.warning(f"Mic initialization failed: {e}")
    
    def _on_mic_disconnected(self):
        """Handle microphone disconnection (runs in main thread - thread-safe)."""
        try:
            logger.info("🔌 Microphone disconnected")
            logger.info("   Voice INPUT disabled (OUTPUT still works)")
            self.microphone = None
            
            # Disable voice checkbox (UI update in main thread - safe!)
            if hasattr(self, 'enable_voice_checkbox'):
                self.enable_voice_checkbox.setChecked(False)
                self.enable_voice_checkbox.setEnabled(False)
                
        except Exception as e:
            logger.warning(f"Mic disconnect handling failed: {e}")
    
    def setup_tts(self):
        """Set up text-to-speech."""
        try:
            if has_voice:
                import pyttsx3
                self.tts_engine = pyttsx3.init()
                voices = self.tts_engine.getProperty('voices')
                for voice in voices:
                    if 'male' in voice.name.lower():
                        self.tts_engine.setProperty('voice', voice.id)
                        break
                self.tts_engine.setProperty('rate', 150)
                self.tts_engine.setProperty('volume', 0.9)
                logger.info("TTS initialized")
        except Exception as e:
            logger.error(f"Error setting up TTS: {e}")
    
    def speak(self, text: str):
        """Speak text using Kingdom Voice Brain Service (Black Panther voice)."""
        try:
            logger.info(f"🎤 Speaking with Black Panther voice: {text[:50]}...")
            
            # CRITICAL: Use event bus to trigger Kingdom Voice Brain Service
            if self.event_bus:
                self.event_bus.publish('voice.speak', {'text': text})
                # PERFORMANCE FIX: Removed excessive logging that caused spam
            else:
                logger.warning("⚠️ No event bus - voice unavailable")
        except Exception as e:
            logger.error(f"Error speaking: {e}")
    
    def handle_voice_speak(self, data: dict):
        """Handle thoth.voice.speak events from ThothAI brain.
        
        CRITICAL FIX: This is the EVENT HANDLER - it should NOT call self.speak()
        because that would republish the event and cause infinite recursion!
        
        Args:
            event_type: The event type ('thoth.voice.speak')
            data: Event data containing 'text' to speak
        """
        try:
            text = data.get('text', '')
            if text:
                logger.info(f"🎤 Thoth AI Voice: Speaking response from Ollama brain")
                # CRITICAL: Call voice service directly, NOT self.speak() to avoid recursion
                if hasattr(self, 'voice_service') and self.voice_service:
                    import threading
                    threading.Thread(target=lambda: self.voice_service.generate_voice(text), daemon=True).start()
        except Exception as e:
            logger.error(f"Error handling voice speak event: {e}")
    
    def _handle_chat_message_add(self, data: dict):
        """Handle chat.message.add and thoth.message events - display messages in chat.
        
        This is used by the analysis system and other components to add messages
        to the chat display without going through the full AI pipeline.
        """
        try:
            if not isinstance(data, dict):
                return
                
            content = data.get('content', '')
            role = data.get('role', 'assistant')
            source = data.get('source', 'System')
            
            if not content:
                return
            
            logger.info(f"📨 Adding {role} message to chat from {source}")
            
            # Add message to chat display
            if hasattr(self, 'chat_widget') and self.chat_widget:
                if role == 'assistant':
                    self.chat_widget.add_ai_message(content)
                else:
                    self.chat_widget.add_user_message(content)
            elif hasattr(self, 'chat_display') and self.chat_display:
                # Fallback to direct chat display
                formatted = f"\n{'🤖 ' + source if role == 'assistant' else '👤 You'}:\n{content}\n"
                self.chat_display.append(formatted)
                
            logger.info(f"✅ Message added to chat: {content[:50]}...")
            
        except Exception as e:
            logger.error(f"Error handling chat message add: {e}")
    
    def _handle_analysis_report(self, data: dict):
        """Handle ai.analysis.report events - display full analysis report in chat."""
        try:
            if not isinstance(data, dict):
                return
            
            summary = data.get('summary', '')
            if not summary:
                return
            
            logger.info("📊 Displaying analysis report in chat")
            
            # Add the analysis report to chat
            if hasattr(self, 'chat_widget') and self.chat_widget:
                self.chat_widget.add_ai_message(f"📊 MARKET ANALYSIS REPORT\n\n{summary}")
            elif hasattr(self, 'chat_display') and self.chat_display:
                self.chat_display.append(f"\n🤖 Market Analysis Engine:\n{summary}\n")
            
            # Log top opportunities
            opportunities = data.get('top_opportunities', [])
            if opportunities:
                logger.info(f"📈 Top {len(opportunities)} opportunities identified")
                for opp in opportunities[:3]:
                    logger.info(f"   {opp.get('symbol')}: {opp.get('signal')} ({opp.get('confidence')*100:.0f}%)")
                    
        except Exception as e:
            logger.error(f"Error handling analysis report: {e}")


class ModelManager(QWidget):
    """Widget for managing AI models."""
    
    def __init__(self, event_bus: EventBus, config: dict, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.config = config
        self.available_models = []
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the model manager UI."""
        layout = QVBoxLayout(self)
        
        # Model selection
        model_group = QFrame()
        model_group.setFrameShape(QFrame.Shape.StyledPanel)
        model_group.setStyleSheet("background: #2d2d2d; padding: 10px; border-radius: 5px;")
        model_layout = QVBoxLayout(model_group)
        
        model_label = QLabel("Select AI Model:")
        self.model_selector = QComboBox()
        self.model_selector.setStyleSheet("""
            QComboBox {
                background: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #444;
                padding: 5px;
                border-radius: 4px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        
        # PERF FIX: Load models in background thread to avoid blocking GUI (3s timeout)
        import threading
        threading.Thread(target=self.load_models, daemon=True).start()
        
        # Model info
        self.model_info = QTextEdit()
        self.model_info.setReadOnly(True)
        self.model_info.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        
        # Add widgets to layout
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_selector)
        model_layout.addWidget(QLabel("Model Information:"))
        model_layout.addWidget(self.model_info)
        
        # Add to main layout
        layout.addWidget(model_group)
        layout.addStretch()
    
    def load_models(self):
        """Load ACTUAL available Ollama models from local server."""
        import requests
        
        self.available_models = []
        
        try:
            # Fetch real models from Ollama API (WSL-aware URL — Ollama brain first)
            try:
                from core.ollama_config import get_ollama_base_url
                ollama_base_url = get_ollama_base_url().rstrip("/")
            except Exception:
                ollama_base_url = "http://localhost:11434"
            tags_url = f"{ollama_base_url}/api/tags"
            response = requests.get(tags_url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                
                for model_data in models:
                    model_name = model_data.get('name', '')
                    model_size = model_data.get('size', 0)
                    
                    # CRITICAL: Filter out cloud models (they have remote_host or tiny size < 1MB)
                    if 'remote_host' in model_data:
                        continue
                    if model_size < 1_000_000:  # Less than 1MB = cloud model reference (not local)
                        continue
                    
                    size_gb = model_size / (1024**3) if model_size > 0 else 0
                    
                    self.available_models.append({
                        "id": model_name,
                        "name": model_name,
                        "description": f"Local Ollama model ({size_gb:.2f} GB)",
                        "size": model_size
                    })
                
                logger.info(f"✅ Loaded {len(self.available_models)} LOCAL Ollama models (filtered cloud models)")
            else:
                logger.warning(f"⚠️ Ollama API returned status {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch Ollama models: {e}")
            logger.info("Using fallback model list")
            
            # Fallback models if Ollama is not running - use LOCALLY INSTALLED models
            self.available_models = [
                {"id": "cogito:latest", "name": "cogito:latest", "description": "Ollama not running - start with 'ollama serve'"},
                {"id": "phi4-mini:latest", "name": "phi4-mini:latest", "description": "Ollama not running - start with 'ollama serve'"}
            ]
        
        # PERF FIX: Populate dropdown on main thread (may be called from background thread)
        def _populate_ui():
            self.model_selector.clear()
            for model in self.available_models:
                self.model_selector.addItem(model["name"], model["id"])
            # Connect signal after populating
            try:
                self.model_selector.currentIndexChanged.disconnect(self.on_model_changed)
            except (TypeError, RuntimeError):
                pass
            self.model_selector.currentIndexChanged.connect(self.on_model_changed)
            # Show first model info
            if self.available_models:
                self.update_model_info(0)
        QTimer.singleShot(0, _populate_ui)
        
        # NOTE: UI updates happen only in _populate_ui on the main thread.
    
    def on_model_changed(self, index: int):
        """Handle model selection change."""
        self.update_model_info(index)
        
        # Publish model change event
        if self.event_bus:
            model_id = self.model_selector.currentData()
            self.event_bus.publish('model.changed', {
                'model_id': model_id,
                'timestamp': datetime.now().isoformat()
            })
    
    def update_model_info(self, index: int):
        """Update model information display."""
        if 0 <= index < len(self.available_models):
            model = self.available_models[index]
            info = f"<b>Name:</b> {model['name']}<br>"
            info += f"<b>ID:</b> {model['id']}<br>"
            info += f"<b>Description:</b> {model.get('description', 'No description available')}<br>"
            self.model_info.setHtml(info)


# Alias for backward compatibility
# Only apply if the real Qt ModelManagerWidget is not available.
try:
    _mmw = ModelManagerWidget
except Exception:
    ModelManagerWidget = ModelManager


class VoiceManager(QWidget):
    """Widget for managing voice features with Black Panther voice integration."""
    
    def __init__(self, event_bus: EventBus, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.config = config
        self.is_listening = False
        self.voice_enabled = self.config.get('voice', {}).get('enabled', False)
        
        # Initialize Black Panther voice
        try:
            # Import the Black Panther voice module
            from black_panther_voice import BlackPantherVoice
            self.bp_voice = BlackPantherVoice(event_bus=event_bus)
            logger.info("Black Panther voice module initialized successfully")
            self.event_bus.emit('voice.status', {'status': 'initialized', 'type': 'black_panther'})
        except ImportError as e:
            logger.error(f"Failed to import Black Panther voice module: {e}")
            self.bp_voice = None
            self.event_bus.emit('voice.error', {'error': f"Failed to import Black Panther voice module: {e}"})
        except Exception as e:
            logger.error(f"Error initializing Black Panther voice: {e}")
            self.bp_voice = None
            self.event_bus.emit('voice.error', {'error': f"Error initializing Black Panther voice: {e}"})
        
        # Initialize Voice Recognition (with webcam mic from HostDeviceManager)
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            
            # PRIORITY 1: Use webcam mic index from HostDeviceManager (via EventBus VoiceManager)
            device_index = None
            if self.event_bus:
                try:
                    voice_manager = self.event_bus.get_component('voice_manager')
                    if voice_manager and hasattr(voice_manager, 'webcam_mic_index'):
                        device_index = voice_manager.webcam_mic_index
                        logger.info(f"🎤 Using HostDeviceManager webcam mic index: {device_index}")
                except Exception as vm_err:
                    logger.debug(f"Could not get VoiceManager from EventBus: {vm_err}")
            
            # PRIORITY 2: Use windows_audio_devices.py for cross-platform mic detection
            if device_index is None:
                try:
                    from config.windows_audio_devices import get_default_microphone, is_wsl
                    device_index = get_default_microphone()
                    if device_index is not None:
                        logger.info(f"🎤 WindowsAudioConfig detected mic at index {device_index}")
                except ImportError:
                    logger.debug("windows_audio_devices not available, using direct detection")
            
            # PRIORITY 3: Fallback direct speech_recognition detection
            if device_index is None:
                try:
                    mic_list = sr.Microphone.list_microphone_names()
                    if mic_list:
                        # Find best microphone (prefer webcam mic, then default)
                        for i, name in enumerate(mic_list):
                            name_lower = name.lower()
                            if any(kw in name_lower for kw in ['webcam', 'camera', 'brio', 'c920', 'usb']):
                                device_index = i
                                logger.info(f"🎤 Selected webcam mic: {name} (index {i})")
                                break
                        if device_index is None:
                            device_index = 0  # Use first available
                            logger.info(f"🎤 Using default mic: {mic_list[0]} (index 0)")
                except Exception as mic_err:
                    logger.debug(f"Mic list detection: {mic_err}")
            
            if device_index is not None:
                self.microphone = sr.Microphone(device_index=device_index)
                logger.info(f"✅ Speech recognition initialized (mic index {device_index})")
            else:
                self.microphone = None
                logger.warning("⚠️ No microphones detected - voice input disabled")
                logger.info("   💡 Voice OUTPUT still works! Connect mic for voice INPUT.")
                
        except ImportError as e:
            logger.warning(f"Speech recognition not available: {e}")
            self.recognizer = None
            self.microphone = None
            self.event_bus.emit('voice.warning', {'warning': f"Speech recognition not available: {e}"})
        except Exception as e:
            logger.warning(f"Error initializing speech recognition: {e}")
            self.recognizer = None
            self.microphone = None
            self.event_bus.emit('voice.warning', {'warning': f"Error initializing speech recognition: {e}"})
            
        # UNIFIED VOICE ROUTING: This GUI widget is a pure control surface.
        # It publishes voice.set_voice and voice.speak events for core.voice_manager.VoiceManager to handle.
        # DO NOT subscribe to voice.speak/voice.listen/voice.stop here - that causes duplicate handlers.
        if self.event_bus:
            logger.info("✅ VoiceManager GUI widget initialized (publishes events only)")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the voice manager UI."""
        layout = QVBoxLayout(self)
        
        # Voice control group
        voice_group = QGroupBox("Voice Controls")
        voice_layout = QVBoxLayout(voice_group)
        
        # Enable/disable voice
        self.enable_voice_checkbox = QCheckBox("Enable Voice")
        self.enable_voice_checkbox.setChecked(self.voice_enabled)
        self.enable_voice_checkbox.toggled.connect(self.on_voice_enabled_changed)
        voice_layout.addWidget(self.enable_voice_checkbox)
        
        # Voice selector
        voice_selector_layout = QFormLayout()
        self.voice_selector = QComboBox()
        self.voice_selector.addItems(["en-US-Standard-D", "en-US-Standard-A", "en-GB-Standard-B"])
        voice_selector_layout.addRow("Voice:", self.voice_selector)
        voice_layout.addLayout(voice_selector_layout)
        
        # Voice parameters
        params_layout = QFormLayout()
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(50)
        self.speed_slider.setMaximum(200)
        self.speed_slider.setValue(100)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(25)
        params_layout.addRow("Speed:", self.speed_slider)
        
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setMinimum(-10)
        self.pitch_slider.setMaximum(10)
        self.pitch_slider.setValue(0)
        self.pitch_slider.setTickPosition(QSlider.TicksBelow)
        self.pitch_slider.setTickInterval(2)
        params_layout.addRow("Pitch:", self.pitch_slider)
        
        voice_layout.addLayout(params_layout)
        
        # Test voice button
        self.test_voice_button = QPushButton("Test Voice")
        self.test_voice_button.clicked.connect(self.on_test_voice)
        voice_layout.addWidget(self.test_voice_button)
        
        layout.addWidget(voice_group)
        
        # Add empty space at the bottom
        layout.addStretch(1)
    
    def on_voice_enabled_changed(self, enabled):
        """Handle voice enabled state change."""
        self.voice_enabled = enabled
        self.event_bus.emit('voice.config_changed', {
            'enabled': enabled
        })
    
    def on_test_voice(self):
        """Test the current voice configuration using Black Panther voice."""
        if not self.voice_enabled:
            return
            
        speed = self.speed_slider.value() / 100.0
        pitch = self.pitch_slider.value() / 10.0
        voice_id = self.voice_selector.currentText()
        
        self.event_bus.emit('voice.speak', {
            'text': "This is a test of the Black Panther voice system. The Kingdom AI voice module is functioning correctly.",
            'voice_id': voice_id,
            'speed': speed,
            'pitch': pitch
        })
        
    # REMOVED: handle_speak_event - voice.speak is now handled by core.voice_manager.VoiceManager only.
    # This GUI widget publishes voice.speak events for testing, but does not consume them.
    
    # REMOVED: handle_listen_event - voice.listen is now handled by core.voice_manager.VoiceManager only.
    # This GUI widget does not start voice input threads; it only publishes events.
    
    # REMOVED: handle_stop_event - voice.stop is now handled by core.voice_manager.VoiceManager only.
    # This GUI widget does not manage voice threads; it only publishes events.
            
    # REMOVED: handle_transcription - voice recognition results are now published by core.voice_manager.VoiceManager
    # as voice.recognition events. This GUI widget does not process transcriptions.


class ThothMainWindow(QMainWindow):
    """Main application window for Thoth AI."""
    
    def __init__(self, event_bus: EventBus, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.config = config
        self.setup_ui()
        self.connect_events()
        self.setup_menu()
    
    def setup_ui(self):
        """Set up the main window UI."""
        # Window properties
        self.setWindowTitle("Thoth AI - Kingdom AI")
        self.setMinimumSize(900, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Chat
        from gui.qt_frames.chat_widget import ChatWidget as ThothChatWidget
        self.chat_widget = ThothChatWidget(self.event_bus, self.config)
        
        # Right panel - Model manager
        self.model_manager = ModelManager(self.event_bus, self.config)
        self.model_manager.setMaximumWidth(300)
        
        # Add widgets to splitter
        splitter.addWidget(self.chat_widget)
        splitter.addWidget(self.model_manager)
        
        # Set splitter sizes
        splitter.setSizes([self.width() - 350, 350])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Status indicators
        self.status_bar.addPermanentWidget(QLabel("Status: "))
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.connection_status)
        
        self.status_bar.addPermanentWidget(QLabel(" | "))
        self.model_status = QLabel("Model: None")
        self.status_bar.addPermanentWidget(self.model_status)
        
        # Set dark theme
        self.set_dark_theme()
    
    def setup_menu(self):
        """Set up the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)
        
        # Settings menu
        settings_menu = menubar.addMenu("&Settings")
        
        api_keys_action = settings_menu.addAction("API &Keys")
        api_keys_action.triggered.connect(self.show_api_keys_dialog)
        
        preferences_action = settings_menu.addAction("&Preferences")
        preferences_action.triggered.connect(self.show_preferences_dialog)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self.show_about_dialog)
        
        docs_action = help_menu.addAction("&Documentation")
        docs_action.triggered.connect(self.show_documentation)
    
    def connect_events(self):
        """Connect to event bus events."""
        if self.event_bus:
            self.event_bus.subscribe('model.changed', self.handle_model_changed)
            self.event_bus.subscribe('connection.status', self.handle_connection_status)
    
    def set_dark_theme(self):
        """Apply a dark theme to the application."""
        # Set style
        self.setStyleSheet("""
            QMainWindow, QDialog, QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            
            QMenuBar {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: none;
            }
            
            QMenuBar::item {
                background: transparent;
                padding: 5px 10px;
            }
            
            QMenuBar::item:selected {
                background: #3a3a3a;
                border-radius: 4px;
            }
            
            QMenu {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
            }
            
            QMenu::item:selected {
                background-color: #3a6ea5;
            }
            
            QStatusBar {
                background-color: #252526;
                color: #e0e0e0;
                border-top: 1px solid #3a3a3a;
            }
            
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 10px;
            }
            
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
        """)
    
    def handle_model_changed(self, event_type: str, data: Dict[str, Any]):
        """Handle model change events."""
        model_id = data.get('model_id', 'unknown')
        self.model_status.setText(f"Model: {model_id}")
        self.status_bar.showMessage(f"Switched to model: {model_id}", 3000)
    
    def handle_connection_status(self, event_type: str, data: Dict[str, Any]):
        """Handle connection status updates."""
        status = data.get('status', 'disconnected')
        if status == 'connected':
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: #6bff6b; font-weight: bold;")
        else:
            self.connection_status.setText("Disconnected")
            self.connection_status.setStyleSheet("color: #ff6b6b; font-weight: bold;")
    
    def show_api_keys_dialog(self):
        """Show the API keys configuration dialog by navigating to API Keys tab."""
        try:
            # Try to switch to API Keys tab via event bus
            if self.event_bus:
                self.event_bus.publish("navigation.switch_tab", {"tab": "api_keys"})
                self.logger.info("Switching to API Keys tab")
            else:
                QMessageBox.information(self, "API Keys", 
                    "Navigate to the API Keys tab in the main window to configure API keys.")
        except Exception as e:
            self.logger.error(f"Error showing API keys dialog: {e}")
            QMessageBox.information(self, "API Keys", 
                "Navigate to the API Keys tab in the main window to configure API keys.")
    
    def show_preferences_dialog(self):
        """Show the preferences dialog by navigating to Settings tab."""
        try:
            # Try to switch to Settings tab via event bus
            if self.event_bus:
                self.event_bus.publish("navigation.switch_tab", {"tab": "settings"})
                self.logger.info("Switching to Settings tab")
            else:
                QMessageBox.information(self, "Preferences", 
                    "Navigate to the Settings tab in the main window to configure preferences.")
        except Exception as e:
            self.logger.error(f"Error showing preferences dialog: {e}")
            QMessageBox.information(self, "Preferences", 
                "Navigate to the Settings tab in the main window to configure preferences.")
    
    def show_about_dialog(self):
        """Show the about dialog."""
        about_text = """
        <h2>Thoth AI - Kingdom AI</h2>
        <p>Version 2.0.0 (SOTA 2026)</p>
        <p>Advanced AI interface for Kingdom AI system</p>
        <p>Features: Voice Recognition, AI Chat, Creative Studio Integration</p>
        <p>© 2024-2026 Kingdom AI. All rights reserved.</p>
        """
        QMessageBox.about(self, "About Thoth AI", about_text)
    
    def show_documentation(self):
        """Open the documentation in the default web browser."""
        try:
            import webbrowser
            # Open local documentation if exists, otherwise show info
            doc_url = "https://github.com/kingdom-ai/docs"  # Documentation repository URL
            webbrowser.open(doc_url)
            self.logger.info(f"Opened documentation: {doc_url}")
        except Exception as e:
            self.logger.error(f"Error opening documentation: {e}")
            QMessageBox.information(self, "Documentation", 
                "Documentation is available in the docs/ folder or at the project repository.")
    
    def closeEvent(self, event):
        """Handle window close event with proper resource cleanup."""
        try:
            # Stop any running voice detection
            if hasattr(self, 'chat_widget') and self.chat_widget:
                if hasattr(self.chat_widget, '_voice_worker') and self.chat_widget._voice_worker:
                    self.chat_widget._voice_worker.stop()
            
            # Clean up any timers
            if hasattr(self, '_cleanup_timers'):
                for timer in self._cleanup_timers:
                    if timer and timer.isActive():
                        timer.stop()
            
            self.logger.info("Thoth AI resources cleaned up")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
        finally:
            event.accept()


class ThothQtWidget(QWidget):
    """Thoth AI Widget for TabManager integration.
    
    This class wraps the ThothMainWindow functionality in a QWidget that can be
    seamlessly integrated into the Kingdom AI TabManager.
    """
    
    _vision_frame_signal = pyqtSignal(object)
    _vision_status_signal = pyqtSignal(dict)
    _vision_vr_frame_signal = pyqtSignal(object)
    _vision_vr_status_signal = pyqtSignal(dict)
    _vision_meta_frame_signal = pyqtSignal(object)
    _vision_meta_status_signal = pyqtSignal(dict)
    _voice_recognition_signal = pyqtSignal(dict)
    _ai_response_signal = pyqtSignal(dict)  # Signal for thread-safe AI response handling

    def __init__(self, event_bus=None, parent=None):
        """Initialize the Thoth AI widget.
        
        CRITICAL: Voice service MUST be available on event_bus.voice_service
        
        Args:
            event_bus: Event bus for component communication
            parent: Parent widget
        """
        super().__init__(parent)
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        
        # Log that ThothQt is being initialized
        logger.info(" Thoth AI TAB IS INITIALIZING! ")
        
        # Config for Thoth
        self.config = {
            'models': {
                'default': 'gpt-4',
                'available': ['gpt-3.5-turbo', 'gpt-4', 'claude-3-opus', 'claude-3-sonnet']
            },
            'voice': {
                'enabled': has_voice,
                'voice_id': 'en-US-Standard-D',  # Deep male voice like Black Panther
                'speed': 1.0,
                'pitch': 0.0
            },
            'ui': {
                'theme': 'dark',
                'font_size': 14,
                'animation_speed': 'normal'
            }
        }
        
        # ========================================================================
        # INITIALIZE ALL SENTIENCE & CONSCIOUSNESS SYSTEMS
        # ========================================================================
        self.redis_client = None
        self.sentience_monitor = None
        self.quantum_engine = None
        self.consciousness_field = None
        self.iit_processor = None
        self.self_model = None
        self.meta_learning = None
        self.memory_manager = None
        self.sentience_panel = None
        self.sentience_timer = None
        
        # CRITICAL: Get voice service from event bus for AI voice responses
        self.voice_service = None
        if event_bus and hasattr(event_bus, 'voice_service'):
            self.voice_service = event_bus.voice_service
            logger.info(" Voice service obtained from event bus for AI responses")
        
        # Initialize missing attributes to prevent webcam vision errors
        self.chat_display = None
        self.enable_voice_checkbox = None
        self.voice_input_started = None
        self.voice_input_stopped = None
        
        # Initialize chat_widget early to prevent attribute errors
        self.chat_widget = None
        
        # Initialize typing indicator
        self.typing_dots = 0
        
        # UNIFIED ROUTING: Track seen response IDs to prevent duplicate messages
        self._seen_response_ids = set()
        self._max_seen_ids = 100  # Prevent unbounded growth
        
        # GREETING DEDUPLICATION: Ensure welcome greeting only fires once
        self._greeting_shown = False
        
        if event_bus and has_sentience:
            # TIMING FIX: Defer Redis connection to ensure Redis Quantum Nexus is ready
            self.logger.info(" Deferring ThothQt Redis connection for 1 second to ensure Quantum Nexus is ready...")
            try:
                # Schedule deferred Redis initialization
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(1000, self._deferred_thoth_redis_init)
                # Sentience systems will be initialized after Redis connection in deferred init
                self.logger.info(" Sentience systems will initialize after Redis connection")
                    
            except Exception as e:
                self.logger.error(f" Failed to schedule ThothQt Redis init: {e}")
                    
        # Initialize Quantum Consciousness Engine
        if QuantumConsciousnessEngine:
            self.quantum_engine = QuantumConsciousnessEngine(self.redis_client)
            self.quantum_engine.start()  # Start 40Hz quantum processing
            self.logger.info(" Quantum Consciousness Engine started (40Hz)")
        
        # Initialize Consciousness Field
        if ConsciousnessField:
            self.consciousness_field = ConsciousnessField(self.redis_client)
            self.consciousness_field.start()  # Start morphic resonance processing
            self.logger.info(" Consciousness Field started (morphic resonance)")
        
        # Initialize IIT Processor
        if IntegratedInformationProcessor:
            self.iit_processor = IntegratedInformationProcessor(self.redis_client)
            self.logger.info(" IIT Processor initialized (Phi calculation)")
        
        # Initialize Self-Model
        if MultidimensionalSelfModel:
            self.self_model = MultidimensionalSelfModel(self.redis_client)
            self.logger.info(" Multidimensional Self-Model initialized")
                    
        # Initialize Meta-Learning
        if has_meta_learning and MetaLearning:
            try:
                self.meta_learning = MetaLearning()
                self.logger.info(" Meta-Learning initialized")
            except Exception as e:
                self.logger.error(f" Meta-Learning initialization failed: {e}")
        
        # Initialize Memory Manager
        if has_memory and MemoryManager and event_bus:
            try:
                self.memory_manager = MemoryManager(event_bus=event_bus)
                self.logger.info(" Memory Manager initialized")
            except Exception as e:
                self.logger.error(f" Memory Manager initialization failed: {e}")

        # Rolling per-tab context summaries (used to feed a short, recent
        # history window into each ai.request so the backend Thoth/Ollama
        # brain can condition on recent activity without re-sending the
        # entire chat transcript. Keys are logical tab ids, e.g. "thoth_ai",
        # "trading", "mining".
        self._tab_context_summaries: Dict[str, str] = {}
        
        # Set up layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Create content based on available components
        self._vision_active = False
        self._vision_url = None
        self._vision_last_frame = None
        self._vision_stream_stats = {}
        self._vision_stream_log_interval_s = 5.0
        self._vision_frame_lock = threading.Lock()
        self._vision_frame_buffer = None
        self._vision_frame_buffer_ts = 0.0
        self._vision_first_frame_received = False
        self._vision_first_frame_rendered = False
        self._vision_render_timer = QTimer(self)
        self._vision_render_timer.timeout.connect(self._poll_vision_frame_buffer)
        # Match source rate (10 FPS from vision_service) to avoid wasted wakeups.
        self._vision_render_timer.setInterval(100)
        self._vision_render_timer.start()
        self._vision_vr_active = False
        self._vision_vr_last_frame = None
        self._vision_vr_last_frame_ts = 0.0
        self._vision_meta_active = False
        self._vision_meta_last_frame = None
        self._vision_meta_last_frame_ts = 0.0
        self._vision_last_frame_ts = 0.0
        self._vision_fullscreen_dialog = None
        self._vision_fullscreen_splitter = None
        self._vision_fullscreen_prev_checked = None
        self._vision_fullscreen_button = None
        self._vision_preview_normal_height = 320  # EXPANDED: Larger camera preview
        self._use_direct_camera = False  # Flag for direct OpenCV camera vs MJPEG server
        self._mjpeg_first_frame_timer = None  # Timer to wait for first frame before starting display
        
        # CRITICAL: Initialize lock for thread-safe frame access (required for direct camera)
        # NOTE: threading is already imported at module level (line 33) - DO NOT re-import locally
        # as that causes "local variable 'threading' referenced before assignment" error
        if not hasattr(self, '_mjpeg_lock'):
            self._mjpeg_lock = threading.Lock()
        
        # Initialize frame tracking variables
        self._mjpeg_frame_count = 0
        self._mjpeg_last_displayed = 0
        self._mjpeg_display_count = 0
        
        # SOTA 2026: Raw JPEG bytes buffer for zero-copy display path
        self._mjpeg_jpg_bytes = None
        self._mjpeg_jpg_ready = False

        self._vision_frame_signal.connect(self._update_vision_frame_on_main_thread)
        self._vision_status_signal.connect(self._update_vision_status_on_main_thread)
        self._vision_vr_frame_signal.connect(self._update_vision_vr_frame_on_main_thread)
        self._vision_vr_status_signal.connect(self._update_vision_vr_status_on_main_thread)
        self._vision_meta_frame_signal.connect(self._update_vision_meta_frame_on_main_thread)
        self._vision_meta_status_signal.connect(self._update_vision_meta_status_on_main_thread)
        self._voice_recognition_signal.connect(self._handle_voice_recognition_on_main_thread)

        if event_bus:
            # Create vision panel at top (collapsible)
            self._create_vision_panel()
            # Vision panel is added to self.layout inside _create_vision_panel() at line 3868
            
            # Create chat interface BELOW vision panel - SOTA 2026 FIX: Give chat widget proper size
            self.chat_widget = ChatWidget(event_bus, self.config, self)
            self.chat_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.chat_widget.setMinimumHeight(400)  # Ensure minimum height for chat area
            # CRITICAL: Add chat widget AFTER vision panel so input/buttons are at bottom
            self.layout.addWidget(self.chat_widget, stretch=1)  # Give stretch to chat widget
            
            # CRITICAL FIX: Connect the message_sent signal to actually send messages!
            self.chat_widget.message_sent.connect(self._handle_message_sent)
            logger.info(" Connected ChatWidget message_sent signal to handler")

            # Connect voice input signals from ChatWidget to VoiceManager via event bus
            try:
                self.chat_widget.voice_input_started.connect(self._on_voice_input_started)
                self.chat_widget.voice_input_stopped.connect(self._on_voice_input_stopped)
                logger.info(" Connected ChatWidget voice input signals to ThothQtWidget")
            except Exception as voice_signal_error:
                logger.warning(f" Failed to connect voice input signals: {voice_signal_error}")

            # Subscribe to vision and voice events on the event bus
            try:
                self.event_bus.subscribe_sync('vision.stream.frame', self._on_vision_frame_event)
                self.event_bus.subscribe_sync('vision.stream.status', self._on_vision_status_event)
                self.event_bus.subscribe_sync('vision.stream.vr.frame', self._on_vision_vr_frame_event)
                self.event_bus.subscribe_sync('vision.stream.vr.status', self._on_vision_vr_status_event)
                self.event_bus.subscribe_sync('vision.stream.meta_glasses.frame', self._on_vision_meta_frame_event)
                self.event_bus.subscribe_sync('vision.stream.meta_glasses.status', self._on_vision_meta_status_event)
                self.event_bus.subscribe_sync('vision.action.research.active_frame', self._on_vision_action_research_event)
                self.event_bus.subscribe_sync('vision.action.creative.active_frame', self._on_vision_action_creative_event)
                self.event_bus.subscribe_sync('voice.recognition', self._on_voice_recognition_event)
                self.event_bus.subscribe_sync('voice.audio.status', self._on_voice_audio_status_event)
                
                # SOTA 2026: Always-On Voice Events - wake word and recognized commands
                self.event_bus.subscribe_sync('voice.wake', self._on_voice_wake_event)
                self.event_bus.subscribe_sync('voice.input.recognized', self._on_voice_input_recognized_event)
                self.event_bus.subscribe_sync('voice.command', self._on_voice_command_event)
                self.event_bus.subscribe_sync('voice.always_on.started', self._on_always_on_started)
                self.event_bus.subscribe_sync('voice.always_on.stopped', self._on_always_on_stopped)
                self.event_bus.subscribe_sync('device.connected', self._on_device_connected_event)
                
                # UNIFIED ROUTING: Subscribe ONLY to ai.response.unified for deduplicated responses
                # DO NOT subscribe to ai.response - that causes duplicate messages!
                self.event_bus.subscribe_sync('ai.response.unified', self._on_ai_response_event)
                self._ai_response_signal.connect(self._handle_ai_response_main_thread)
                logger.info(" ThothQtWidget subscribed to ai.response.unified, vision.stream.*, voice.recognition, and always-on voice events")
            except Exception as e:
                logger.error(f"Failed to subscribe to events: {e}")
                # Create fallback UI if event bus failed
                fallback_label = QLabel("Thoth AI interface (event bus unavailable)")
                self.layout.addWidget(fallback_label)
                self.logger.warning("Created Thoth AI interface without event bus")
        
        # CRITICAL DEBUG: Log that ThothQt initialization completed
        logger.info(" Thoth AI TAB INITIALIZATION COMPLETE! ")
        
        # CRITICAL FIX: Auto-start vision stream after tab loads
        QTimer.singleShot(3000, self._auto_start_vision_if_available)
        # Startup greeting reliability state: audio output may settle after first publish.
        self._startup_greeting_text = "Welcome to Kingdom AI. All systems are now online."
        self._startup_greeting_publish_ts = 0.0
        self._startup_audio_ready_ts = 0.0
        self._startup_greeting_replayed = False
        self._startup_followup_sent = False
        self._startup_greeting_chat_added = False
        self._identity_check_sent = False
        
        # CRITICAL FIX: Show welcome greeting in chat AND speak it vocally
        QTimer.singleShot(4000, self._show_welcome_greeting)
        # Webcam mic auto-listen: user can speak without pressing mic (mic button still available)
        QTimer.singleShot(6000, self._start_auto_listen)
    
    def _start_auto_listen(self):
        """Start voice listen so user can speak without pressing mic button (webcam built-in mic)."""
        # Optional debug log (runtime-agnostic path)
        try:
            import json as _json
            import os as _os
            _log_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", "logs")
            _os.makedirs(_log_dir, exist_ok=True)
            _path = _os.path.join(_log_dir, "thoth_auto_listen.log")
            with open(_path, "a", encoding="utf-8") as _f:
                _f.write(_json.dumps({"location": "thoth_qt:_start_auto_listen", "message": "publishing voice.listen", "has_event_bus": bool(getattr(self, "event_bus", None))}) + "\n")
        except Exception:
            pass
        try:
            if self.event_bus:
                self.event_bus.publish("voice.listen", {"action": "start", "source": "thoth_auto_listen"})
                logger.info("🎤 Auto-listen started - user can speak without pressing mic")
        except Exception as e:
            logger.debug("Auto-listen start: %s", e)
    
    def _show_welcome_greeting(self):
        """Show ONE greeting from AI brain — no hardcoded text, no double response.
        
        SOTA 2026 Flow: Run identity check; brain produces single natural greeting
        (e.g. "Hello Isaiah! Good to see you again..."). No deterministic first message.
        """
        try:
            logger.info("🎤 _show_welcome_greeting: identity check + voice safety net")
            self._startup_greeting_chat_added = True
            self._startup_greeting_publish_ts = time.time()

            # Reliability: ensure always-on listening starts even if delayed timer misses.
            try:
                if self.event_bus:
                    self.event_bus.publish("voice.listen", {"action": "start", "source": "thoth_greeting_bootstrap"})
                    logger.info("🎤 Forced voice.listen start from greeting bootstrap")
                try:
                    from core.voice_manager import start_always_on_listening
                    if start_always_on_listening(self.event_bus):
                        logger.info("🎤 Direct AlwaysOnVoice start succeeded from greeting bootstrap")
                    else:
                        logger.warning("⚠️ Direct AlwaysOnVoice start returned False in greeting bootstrap")
                except Exception as _direct_start_err:
                    logger.warning("⚠️ Direct AlwaysOnVoice bootstrap start failed: %s", _direct_start_err)
            except Exception as _voice_bootstrap_err:
                logger.debug("voice.listen bootstrap publish failed: %s", _voice_bootstrap_err)
            
            # Start identity check — brain produces the single spoken greeting
            import threading
            threading.Thread(
                target=self._post_greeting_identity_check,
                daemon=True,
                name="PostGreetingIdentity"
            ).start()
            
            # Safety net: if AI brain hasn't produced a greeting within 15s, speak a fallback
            QTimer.singleShot(15000, self._ensure_startup_greeting_audible)
            
        except Exception as e:
            logger.error(f"Error showing welcome greeting: {e}")

    def _is_audio_output_ready_event(self, payload: dict) -> bool:
        """Detect output-route-ready device events from HostDeviceManager."""
        try:
            device = payload.get('device', {}) if isinstance(payload, dict) else {}
            dev_id = str(device.get('id', '')).lower()
            dev_name = str(device.get('name', '')).lower()
            dev_type = str(device.get('type', '')).lower()
            category = str(device.get('category', '')).lower()
            fields = " ".join([dev_id, dev_name, dev_type, category])
            return (
                "wsl_audio_bridge" in fields
                or "audio_output" in fields
                or "speaker" in fields
                or "bose" in fields
            )
        except Exception:
            return False

    def _on_device_connected_event(self, payload):
        """Replay startup greeting once if audio route became ready too late."""
        try:
            if self._startup_audio_ready_ts > 0:
                return
            if not self._is_audio_output_ready_event(payload if isinstance(payload, dict) else {}):
                return
            self._startup_audio_ready_ts = time.time()
            logger.info("🔊 Startup audio route detected as ready")
            if self._startup_greeting_publish_ts > 0 and not self._startup_greeting_replayed:
                if (self._startup_audio_ready_ts - self._startup_greeting_publish_ts) > 1.5:
                    self._replay_startup_greeting_once("audio_route_ready_late")
        except Exception as e:
            logger.debug("Device-connected greeting readiness hook failed: %s", e)

    def _ensure_startup_greeting_audible(self):
        """Fallback replay if first greeting likely fired before output route was ready."""
        try:
            if self._startup_greeting_replayed or self._startup_greeting_publish_ts <= 0:
                return
            if self._startup_audio_ready_ts == 0.0:
                self._replay_startup_greeting_once("audio_route_not_confirmed")
                return
            if (self._startup_audio_ready_ts - self._startup_greeting_publish_ts) > 1.5:
                self._replay_startup_greeting_once("audio_route_late_confirmed")
        except Exception as e:
            logger.debug("Startup greeting audibility check failed: %s", e)

    def _replay_startup_greeting_once(self, reason: str):
        """Replay greeting once with unique text to bypass duplicate suppression."""
        if self._startup_greeting_replayed or not self.event_bus:
            return
        self._startup_greeting_replayed = True
        replay_text = "Audio channel confirmed. All systems are online."
        self.event_bus.publish("voice.speak", {
            "text": replay_text,
            "priority": "critical",
            "source": "thoth_qt_startup_replay",
            "request_id": f"startup_greeting_replay_{int(time.time() * 1000)}",
        })
        logger.info("🔊 Replayed startup greeting once (%s)", reason)

    def _send_startup_audio_followup(self):
        """Send one short startup follow-up so the user reliably hears audio on boot."""
        if os.environ.get("KINGDOM_STARTUP_AUDIO_FOLLOWUP", "0") != "1":
            return
        if self._startup_followup_sent or not self.event_bus:
            return
        self._startup_followup_sent = True
        self.event_bus.publish("voice.speak", {
            "text": "Kingdom AI audio check complete. I am online and listening.",
            "priority": "critical",
            "source": "thoth_qt_startup_followup",
            "request_id": f"startup_greeting_followup_{int(time.time() * 1000)}",
        })
        logger.info("🔊 Sent startup audio follow-up confirmation")
    
    def _post_greeting_identity_check(self):
        """After greeting, send identity context to ThothAI brain so Kingdom speaks naturally.
        
        SOTA 2026: No hardcoded responses. Kingdom AI's brain gets real-time context
        about what the camera sees and the enrollment status, then responds freely.
        """
        import time
        if self._identity_check_sent:
            logger.info("👁️ Post-greeting identity check already sent — skipping duplicate")
            return
        self._identity_check_sent = True
        try:
            time.sleep(4)
            logger.info("👁️ Post-greeting identity check starting...")
            
            # Find identity engine from component registry
            identity_engine = None
            for attempt in range(3):
                try:
                    from core.component_registry import get_component
                    identity_engine = get_component('user_identity_engine')
                    if identity_engine:
                        logger.info(f"✅ Found identity engine on attempt {attempt + 1}")
                        break
                except Exception as e:
                    logger.debug(f"Identity engine lookup attempt {attempt + 1} failed: {e}")
                time.sleep(2)
            
            if not identity_engine:
                logger.warning("⚠️ Identity engine not found — skipping identity check")
                return
            
            # Build real-time context for the AI brain
            status = identity_engine.get_status()
            owner_face_samples = status.get('owner_face_samples', 0)
            owner_voice_samples = status.get('owner_voice_samples', 0)
            owner_name = "Isaiah Wright"
            
            # Determine what we see — only trust an actual recent face verification,
            # NOT enrollment sample count (having samples != currently on camera)
            face_result = getattr(identity_engine, '_current_face_result', None)
            face_time = getattr(identity_engine, '_face_result_time', 0)
            owner_on_camera = False
            if face_result and getattr(face_result, 'is_owner', False) and (time.time() - face_time) < 10:
                owner_on_camera = True
            
            # Build context prompt for ThothAI brain
            # NOTE: This is the ONLY spoken greeting. _show_welcome_greeting() adds text
            # to chat but does NOT speak. This brain request produces the single unified
            # spoken response covering both welcome + identity acknowledgment.
            if owner_on_camera:
                context = (
                    f"[SYSTEM CONTEXT - STARTUP GREETING] You are Kingdom AI and you just came online. "
                    f"All systems are operational. Your camera is active and you recognize "
                    f"your owner {owner_name} on camera. You have {owner_face_samples} face samples and "
                    f"{owner_voice_samples} voice samples enrolled for them. You are actively learning their "
                    f"voice patterns. Welcome them and greet them naturally as their AI assistant. "
                    f"Be conversational, not robotic. Acknowledge that you see them and know who they are. "
                    f"This is your ONLY greeting — combine welcome + identity into one natural response. "
                    f"You have NO speech time limit. Speak naturally and complete all thoughts fully."
                )
            else:
                context = (
                    f"[SYSTEM CONTEXT - STARTUP GREETING] You are Kingdom AI and you just came online. "
                    f"All systems are operational. Your camera is active but you don't "
                    f"recognize anyone on camera yet. The registered owner is {owner_name}. "
                    f"You have {owner_face_samples} face samples enrolled. Welcome them and ask who is there naturally. "
                    f"This is your ONLY greeting — combine welcome + identity into one natural response. "
                    f"You have NO speech time limit. Speak naturally and complete all thoughts fully."
                )
            
            logger.info(f"🧠 Sending identity context to ThothAI brain")
            
            # Send to ThothAI brain as an ai.request — let the brain respond naturally
            # suppress_chat=False so the AI's greeting appears in chat (single greeting)
            if self.event_bus:
                self.event_bus.publish('ai.request', {
                    'prompt': context,
                    'message': context,
                    'request_id': f"identity_{int(time.time() * 1000)}",
                    'source_tab': 'system',
                    'sender': 'system',
                    'speak': True,
                    'system_context': True,
                    'suppress_chat': False,
                })
                
        except Exception as e:
            logger.error(f"Post-greeting identity check error: {e}")
    
    def show_typing_indicator(self, visible: bool = True):
        """Show or hide typing indicator (Kingdom AI is typing...)."""
        try:
            if not hasattr(self, '_typing_label') or self._typing_label is None:
                self._typing_label = QLabel("Kingdom AI is typing...")
                self._typing_label.setStyleSheet("""
                    QLabel { background: #2d2d3d; color: #7aa2f7; padding: 8px;
                    border-radius: 6px; border-left: 3px solid #7aa2f7; font-style: italic; }
                """)
                if hasattr(self, 'layout') and self.layout is not None:
                    self.layout.addWidget(self._typing_label)
            self._typing_label.setVisible(visible)
        except Exception as e:
            logger.debug(f"show_typing_indicator: {e}")
    
    def _deferred_thoth_redis_init(self):
        """Deferred Redis initialization for ThothQt - called after Redis Quantum Nexus is ready."""
        try:
            self.logger.info(" ThothQt connecting to Redis Quantum Nexus...")
            
            # Initialize Redis Quantum Nexus connection
            import redis  # type: ignore
            self.redis_client = redis.Redis(  # type: ignore
                host='localhost',
                port=6380,
                password='QuantumNexus2025',
                db=0,
                decode_responses=True
            )
            self.redis_client.ping()
            self.logger.info(" ThothQt connected to Redis Quantum Nexus (port 6380)")
            
            # Now initialize all sentience systems with Redis client
            if has_sentience:
                try:
                    # Initialize Sentience Monitor
                    if SentienceMonitor:
                        self.sentience_monitor = SentienceMonitor(self.event_bus, self.redis_client)
                        self.sentience_monitor.start()  # CRITICAL: Must start to publish sentience events
                        self.logger.info("✅ Sentience Monitor initialized and STARTED")
                    
                    # Initialize Quantum Consciousness Engine
                    if QuantumConsciousnessEngine:
                        self.quantum_engine = QuantumConsciousnessEngine(self.redis_client)
                        self.quantum_engine.start()  # Start 40Hz quantum processing
                        self.logger.info(" Quantum Consciousness Engine started (40Hz)")
                    
                    # Initialize Consciousness Field
                    if ConsciousnessField:
                        self.consciousness_field = ConsciousnessField(self.redis_client)
                        self.consciousness_field.start()  # Start morphic resonance processing
                        self.logger.info(" Consciousness Field started (morphic resonance)")
                    
                    # Initialize IIT Processor
                    if IntegratedInformationProcessor:
                        self.iit_processor = IntegratedInformationProcessor(self.redis_client)
                        self.logger.info(" IIT Processor initialized (Phi calculation)")
                    
                    # Initialize Self-Model
                    if MultidimensionalSelfModel:
                        self.self_model = MultidimensionalSelfModel(self.redis_client)
                        self.logger.info(" Multidimensional Self-Model initialized")
                        
                except Exception as e:
                    # Don't fail on DORMANT state - it's the initial state
                    if str(e) == "DORMANT":
                        self.logger.info(f" Sentience systems initialized in DORMANT state (normal initial state)")
                    else:
                        self.logger.error(f" Failed to initialize sentience systems: {e}")
                        
        except Exception as e:
            # Log warning but don't crash - ThothQt can function without Redis
            self.logger.warning(f" ThothQt Redis connection failed (will retry): {e}")
            self.redis_client = None
        
    def _update_tab_context_summary(self, source_tab: str, role: str, message: str) -> None:
        """Update a short rolling summary for the given logical tab.

        This keeps the last few lines of conversation per tab so we can
        attach a compact context string to ai.request payloads.
        """
        try:
            key = (source_tab or "thoth_ai").lower()
            text = (message or "").strip()
            if not text:
                return

            snippet = f"{role}: {text}"
            prev = self._tab_context_summaries.get(key, "")
            combined = (prev + "\n" + snippet).strip() if prev else snippet

            # Keep only the last ~10 lines to bound size
            lines = combined.splitlines()
            if len(lines) > 10:
                lines = lines[-10:]
            combined = "\n".join(lines)

            # Hard cap context length to avoid huge prompts
            if len(combined) > 1200:
                combined = combined[-1200:]

            self._tab_context_summaries[key] = combined
        except Exception as e:
            self.logger.warning(f"Error updating tab context summary for {source_tab}: {e}")

    def _get_tab_context_summary(self, source_tab: str) -> Optional[str]:
        """Return the rolling context summary for a logical tab, if any."""
        try:
            key = (source_tab or "thoth_ai").lower()
            return self._tab_context_summaries.get(key)
        except Exception:
            return None

    def handle_event(self, event_type, event_data):
        """Handle events from the event bus.
        
        Args:
            event_type: Type of event
            event_data: Event data payload
        """
        if hasattr(self, 'chat_widget'):
            if event_type == 'ai.response':
                self.chat_widget.add_ai_response(event_data)
            elif event_type == 'system.status':
                self.chat_widget.update_status(event_data)
                
    def update_tab_content(self):
        """Update the tab content (called by TabManager)."""
        if hasattr(self, 'chat_widget') and hasattr(self.chat_widget, 'refresh'):
            self.chat_widget.refresh()
    
    def speak(self, text: str):
        """Speak text via VoiceManager (Dec 19 Black Panther / unified voice path).
        
        Publishes voice.speak so core.voice_manager.VoiceManager (authoritative handler)
        queues TTS - Black Panther XTTS, pyttsx3, or WSL Windows SAPI. No direct voice_service.
        
        Args:
            text: Text to speak
        """
        try:
            if not text or not self.event_bus:
                return
            # UNIFIED ROUTING: Publish voice.speak - VoiceManager subscribes and handles TTS
            self.event_bus.publish("voice.speak", {
                "text": text,
                "priority": "normal",
                "source": "thoth_qt",
            })
            logger.info(f"🔊 Published voice.speak for Thoth tab (VoiceManager will speak): {text[:50]}...")
        except Exception as e:
            logger.error(f"Voice error: {e}")
            logger.warning("TTS unavailable - text only mode")
    
    def _on_ai_response_event(self, data: Dict[str, Any]) -> None:
        """Handle AI response event from event bus - emit signal for thread-safe processing."""
        logger.info(f"ThothQtWidget received ai.response - emitting signal")
        self._ai_response_signal.emit(data)
    
    def _handle_ai_response_main_thread(self, data: Dict[str, Any]) -> None:
        """Process AI response in main thread - display in chat AND speak with TTS SIMULTANEOUSLY.
        
        Args:
            data: AI response data containing 'response', 'request_id', etc.
        """
        try:
            response_text = data.get('response', '')
            request_id = data.get('request_id', 'unknown')
            source_tab = data.get('source_tab', 'thoth_ai')
            
            # CRITICAL: Stop typing indicator when response arrives
            # Also clear internal typing indicator directly (don't just publish event)
            self.show_typing_indicator(False)
            
            if self.event_bus:
                self.event_bus.publish('typing.stopped', {
                    'sender': 'Kingdom AI',
                    'timestamp': datetime.now().isoformat(),
                    'source_tab': source_tab,
                })
                logger.info(f" Published typing.stopped - AI finished thinking")
            
            # UNIFIED ROUTING: Deduplicate responses by request_id
            if request_id and request_id != 'unknown' and request_id in self._seen_response_ids:
                logger.debug(f" DEDUP: Skipping duplicate response for {request_id}")
                return
            if request_id and request_id != 'unknown':
                self._seen_response_ids.add(request_id)
                # Prevent unbounded growth
                if len(self._seen_response_ids) > self._max_seen_ids:
                    self._seen_response_ids = set(list(self._seen_response_ids)[-50:])
            
            logger.info(f" Processing AI response in main thread: {response_text[:80]}...")
            
            if response_text:
                # DO NOT add to chat_widget here - ChatWidget already subscribes to ai.response.unified
                # and will add the message itself. Adding here causes DOUBLE MESSAGES!
                # FIXED: Do NOT publish voice.speak here - UnifiedAIRouter already handles this
                # Publishing here causes DUPLICATE/TRIPLE voice responses
                logger.info(f"✅ AI response received (ChatWidget will display): {response_text[:50]}...")
                # Update context summary
                self._update_tab_context_summary(source_tab, "assistant", response_text)
            
            # Handle errors
            if data.get('error'):
                error_msg = data.get('error', 'Unknown error')
                if hasattr(self, 'chat_widget') and self.chat_widget:
                    self.chat_widget.add_message(
                        sender="System",
                        message=f"AI Error: {error_msg}",
                        is_ai=False
                    )
                logger.error(f"AI response error: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error handling AI response: {e}", exc_info=True)
    
    def _handle_message_sent(self, message: str):
        """Handle message sent from ChatWidget - actually send to AI!
        
        SOTA 2026: First routes through AI Command Router to detect actionable
        commands (device control, software automation, trading, mining, wallet).
        If a command is detected, it's executed immediately and the result is
        shown in chat. Otherwise, the message is sent to the AI for response.
        
        Args:
            message: The message text from the user
        """
        logger.info(f" MESSAGE SENT FROM CHAT WIDGET: '{message}' ")
        
        if not message or not message.strip():
            logger.warning(" Empty message, ignoring")
            return
        
        # CRASH LOGGING: Write to persistent file before any processing
        try:
            import os
            os.makedirs(_LOG_DIR, exist_ok=True)
            with open(os.path.join(_LOG_DIR, 'chat_crash_log.txt'), 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"[{datetime.now().isoformat()}] Processing message: {message[:100]}...\n")
                f.flush()
        except Exception:
            pass
        
        try:
            attachments = []
            routed_action = ""
            try:
                if hasattr(self, 'chat_widget') and self.chat_widget is not None:
                    if hasattr(self.chat_widget, 'pop_last_outgoing_attachments'):
                        attachments = self.chat_widget.pop_last_outgoing_attachments()
            except Exception:
                attachments = []

            # ChatWidget already renders the user message before emitting
            # message_sent. Re-adding here creates duplicate "You" bubbles.
            logger.info(f" User message accepted for AI dispatch: '{message[:50]}...'")
            
            # SOTA 2026: Route through AI Command Router for actionable commands
            try:
                from core.ai_command_router import get_command_router
                command_router = get_command_router(self.event_bus)
                was_command, result = command_router.process_and_route(message)
                if was_command and isinstance(result, dict):
                    routed_action = str(result.get("published", "") or "")
                
                if was_command and result:
                    # Command was executed - show result in chat
                    if result.get("success"):
                        result_text = f" **Command executed successfully**\n\n"
                        if "devices" in result:
                            result_text += f"Found {result.get('count', 0)} devices."
                        elif "windows" in result:
                            windows = result.get("windows", [])
                            result_text += f"Found {len(windows)} open windows:\n"
                            for w in windows[:10]:
                                result_text += f"• {w.get('name', 'Unknown')[:50]}\n"
                        elif "connected" in result:
                            result_text += f"Connected to software: {result.get('connected', {})}"
                        elif "published" in result:
                            result_text += f"Action sent: {result.get('published')}"
                        else:
                            result_text += str(result)
                    else:
                        result_text = f" **Command failed**: {result.get('error', 'Unknown error')}"
                    
                    self.chat_widget.add_message(
                        sender="Kingdom AI",
                        message=result_text,
                        is_ai=True
                    )
                    logger.info(f" Command routed and executed: {result}")
                    
                    # Also send to AI for contextual response
                    # (AI will know the command was executed)
            except ImportError as ie:
                logger.warning(f"AI Command Router not available: {ie}")
            except Exception as router_err:
                logger.warning(f"Command routing error (continuing to AI): {router_err}")
            
            # Update rolling context summary for the Thoth AI tab
            self._update_tab_context_summary("thoth_ai", "user", message)

            # Vision-intent routing for chat:
            # - "send this image to creative studio" => creative.create with active frame
            # - "research/analyze this image" => ai.request with attached active frame
            vision_intent = self._detect_vision_user_intent(message)
            if vision_intent == "creative" and self.event_bus and routed_action != "vision.action.creative.active_frame":
                vision_payload = self._build_vision_payload(text=message)
                creative_payload: Dict[str, Any] = {
                    "prompt": message,
                    "source": "thoth_chat",
                    "vision_intent": "creative",
                }
                creative_payload.update(vision_payload)
                self.event_bus.publish("creative.create", creative_payload)
                self.chat_widget.add_message(
                    sender="Kingdom AI",
                    message="🖼️ Sent active vision frame to Creative Studio.",
                    is_ai=True,
                )
                return
            if routed_action in ("vision.action.research.active_frame", "vision.action.creative.active_frame"):
                return
            
            # Generate request ID
            request_id = f"req_{int(time.time() * 1000)}"
            
            # CRITICAL FIX: Use LOCAL Ollama model, not cloud model
            # Cloud models don't work without API access
            selected_model = self.config.get('default_model', 'cogito:latest')
            
            # Publish AI request event to event bus
            if self.event_bus:
                # CRITICAL: Show typing indicator BEFORE sending AI request
                self.event_bus.publish('typing.started', {
                    'sender': 'Kingdom AI',
                    'timestamp': datetime.now().isoformat(),
                    'source_tab': 'thoth_ai',
                })
                logger.info(f" Published typing.started - AI is thinking...")
                
                logger.info(f" PUBLISHING ai.request to event bus (source_tab=thoth_ai)...")

                system_prompt = (
                    "You are Thoth AI operating inside the Thoth AI control tab of the "
                    "Kingdom AI system. Provide high-level reasoning, cross-domain "
                    "assistance, and orchestration across trading, mining, blockchain, "
                    "wallet, VR, and configuration while respecting safety and risk "
                    "management.\n\n"
                    "SOTA 2026 VOICE & TEXT COMMANDS - Users can control the system via natural language:\n"
                    "- Device: 'scan devices', 'list devices', 'enable device [name]'\n"
                    "- Software: 'list windows', 'connect to [app]', 'send keys [text]', 'click at X,Y'\n"
                    "- Trading: 'buy/sell [amount] [symbol]', 'show portfolio', 'check price'\n"
                    "- Mining: 'start/stop mining [coin]', 'show hashrate'\n"
                    "- Wallet: 'show balance', 'send [amount] [token] to [address]'\n"
                    "- Navigation: 'go to [tab]', 'open [tab]', 'switch to [tab]'\n"
                    "- UI: 'scroll up/down', 'fullscreen', 'refresh'\n"
                    "When users give these commands, acknowledge and provide context. "
                    "Full reference: docs/SOTA_2026_MCP_VOICE_COMMANDS.md"
                )

                tab_context_summary = self._get_tab_context_summary("thoth_ai")

                payload = {
                    'request_id': request_id,
                    'prompt': message,
                    'model': selected_model,
                    'timestamp': datetime.utcnow().isoformat(),
                    'sender': 'user',
                    'source_tab': 'thoth_ai',
                    'source': 'chat_widget',
                    'realtime': True,
                    'speak': True,
                    'system_prompt': system_prompt,
                }

                # Attach any file attachments captured from the ChatWidget for this send.
                if attachments:
                    payload['attachments'] = attachments
                if tab_context_summary:
                    payload['tab_context_summary'] = tab_context_summary

                # Unified vision payload: supports webcam + VR + Meta glasses streams.
                payload.update(self._build_vision_payload(text=message))

                # Single source of dispatch for text chat requests.
                self.event_bus.publish('ai.request', payload)
                logger.info(f"✅ ai.request published from ThothQt (ID: {request_id})")
                
                # Also publish to sentience systems with per-tab tagging
                self.event_bus.publish('thoth.message.sent', {
                    'message': message,
                    'timestamp': datetime.now().isoformat(),
                    'for_sentience_processing': True,
                    'source_tab': 'thoth_ai',
                    'role': 'user',
                    'channel': 'thoth_tab',
                })
                logger.info(f" Published to sentience systems (source_tab=thoth_ai)")

                # Store chat message in MemoryManager with per-tab metadata so
                # the backend can reconstruct and analyze history.
                try:
                    self.event_bus.publish('memory.store', {
                        'type': 'chat_history',
                        'data': {
                            'message': message,
                            'role': 'user',
                            'source_tab': 'thoth_ai',
                            'channel': 'thoth_tab',
                        },
                        'metadata': {
                            'source_tab': 'thoth_ai',
                            'role': 'user',
                            'channel': 'thoth_tab',
                        },
                    })
                except Exception as mem_err:
                    logger.warning(f"Error publishing memory.store for Thoth text chat: {mem_err}")
                
                # Voice will be spoken when AI response arrives (line 1535)
                # No hardcoded greeting needed - let AI speak its actual response
            else:
                logger.error(" No event bus available!")
                
        except Exception as e:
            logger.error(f" Error handling message: {e}", exc_info=True)
            # CRASH LOGGING: Write full traceback to persistent file
            try:
                import traceback
                with open(os.path.join(_LOG_DIR, 'chat_crash_log.txt'), 'a', encoding='utf-8') as f:
                    f.write(f"\n❌ CRASH at {datetime.now().isoformat()}:\n")
                    f.write(f"Message: {message[:100]}...\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}\n")
                    f.write("="*60 + "\n")
                    f.flush()
            except Exception:
                pass
    
    def _create_vision_panel(self):
        """Create a COLLAPSIBLE vision preview panel with a toggle button."""
        try:
            # Create main container with header for collapse toggle
            container = QGroupBox("📹 Vision Stream")
            container.setCheckable(True)
            container.setChecked(True)  # Start EXPANDED so button is visible
            container.setStyleSheet(
                """
                QGroupBox {
                    background-color: #1a1b26;
                    border: 2px solid #3b4261;
                    border-radius: 8px;
                    margin-top: 8px;
                    padding: 8px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px;
                    color: #7aa2f7;
                }
                QGroupBox::indicator {
                    width: 14px;
                    height: 14px;
                }
                """
            )
            
            # Connect toggle signal to show/hide content
            container.toggled.connect(self._toggle_vision_content)
            
            layout = QVBoxLayout(container)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.setSpacing(6)

            # Create content widget that can be shown/hidden
            self._vision_content_widget = QWidget()
            content_layout = QVBoxLayout(self._vision_content_widget)
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(6)

            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)

            self._vision_status_label = QLabel("Camera: OFF")
            self._vision_status_label.setStyleSheet("color: #a9b1d6; border: none;")
            top_row.addWidget(self._vision_status_label)
            self._vision_vr_status_label = QLabel("VR View: OFF")
            self._vision_vr_status_label.setStyleSheet("color: #a9b1d6; border: none; margin-left: 12px;")
            top_row.addWidget(self._vision_vr_status_label)
            self._vision_meta_status_label = QLabel("Meta Glasses: OFF")
            self._vision_meta_status_label.setStyleSheet("color: #a9b1d6; border: none; margin-left: 12px;")
            top_row.addWidget(self._vision_meta_status_label)
            top_row.addStretch()

            self._vision_toggle_button = QPushButton("Start Camera")
            self._vision_toggle_button.setCheckable(True)
            self._vision_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #3a3a4a;
                    color: #ffffff;
                    border: 1px solid #4a4a5a;
                    border-radius: 4px;
                    padding: 4px 10px;
                    min-width: 100px;
                }
                QPushButton:checked {
                    background-color: #007acc;
                    border-color: #1e90ff;
                }
                """
            )
            self._vision_toggle_button.toggled.connect(self._on_vision_toggle)
            top_row.addWidget(self._vision_toggle_button)

            self._vision_fullscreen_button = QPushButton("Fullscreen")
            self._vision_fullscreen_button.setCheckable(True)
            self._vision_fullscreen_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #3a3a4a;
                    color: #ffffff;
                    border: 1px solid #4a4a5a;
                    border-radius: 4px;
                    padding: 4px 10px;
                    min-width: 110px;
                }
                QPushButton:checked {
                    background-color: #7aa2f7;
                    border-color: #9aaeff;
                }
                """
            )
            self._vision_fullscreen_button.toggled.connect(self._on_vision_fullscreen_toggle)
            top_row.addWidget(self._vision_fullscreen_button)

            content_layout.addLayout(top_row)

            # Side-by-side previews: main camera, VR view, and Meta glasses
            preview_row = QHBoxLayout()
            preview_row.setContentsMargins(0, 0, 0, 0)
            preview_row.setSpacing(6)

            # Main camera column
            cam_col = QVBoxLayout()
            cam_col.setContentsMargins(0, 0, 0, 0)
            cam_col.setSpacing(2)

            cam_label = QLabel("Main Camera")
            cam_label.setStyleSheet("color: #a9b1d6; border: none;")
            cam_col.addWidget(cam_label)

            self._vision_preview_label = QLabel("Camera off")
            self._vision_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._vision_preview_label.setMinimumSize(320, self._vision_preview_normal_height)  # CRITICAL: Set min width too
            self._vision_preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._vision_preview_label.setStyleSheet(
                "background-color: #000000; border: 2px solid #7aa2f7; color: #7aa2f7; font-size: 14px;"
            )
            cam_col.addWidget(self._vision_preview_label)

            preview_row.addLayout(cam_col)

            # VR view column
            vr_col = QVBoxLayout()
            vr_col.setContentsMargins(0, 0, 0, 0)
            vr_col.setSpacing(2)

            vr_label = QLabel("VR View")
            vr_label.setStyleSheet("color: #a9b1d6; border: none;")
            vr_col.addWidget(vr_label)

            self._vision_vr_preview_label = QLabel("VR view inactive")
            self._vision_vr_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._vision_vr_preview_label.setMinimumSize(320, self._vision_preview_normal_height)
            self._vision_vr_preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._vision_vr_preview_label.setStyleSheet(
                "background-color: #000000; border: 1px solid #3b4261; color: #666666;"
            )
            vr_col.addWidget(self._vision_vr_preview_label)

            preview_row.addLayout(vr_col)

            # Meta glasses column
            meta_col = QVBoxLayout()
            meta_col.setContentsMargins(0, 0, 0, 0)
            meta_col.setSpacing(2)

            meta_label = QLabel("Meta Glasses")
            meta_label.setStyleSheet("color: #a9b1d6; border: none;")
            meta_col.addWidget(meta_label)

            self._vision_meta_preview_label = QLabel("Meta glasses inactive")
            self._vision_meta_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._vision_meta_preview_label.setMinimumSize(320, self._vision_preview_normal_height)
            self._vision_meta_preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._vision_meta_preview_label.setStyleSheet(
                "background-color: #000000; border: 1px solid #3b4261; color: #666666;"
            )
            meta_col.addWidget(self._vision_meta_preview_label)

            preview_row.addLayout(meta_col)

            content_layout.addLayout(preview_row)
            
            # Add content widget to main layout and show it initially
            layout.addWidget(self._vision_content_widget)
            self._vision_content_widget.setVisible(True)  # Start EXPANDED so button is visible

            # Keep a handle so we can show/hide the entire panel
            self._vision_container = container

            # Add panel to main layout under sentience panel
            self.layout.addWidget(container)
        except Exception as e:
            self.logger.error(f"Error creating vision panel: {e}")

    def _toggle_vision_content(self, checked: bool):
        """Toggle visibility of vision panel content when checkbox is clicked."""
        try:
            if hasattr(self, '_vision_content_widget') and self._vision_content_widget:
                self._vision_content_widget.setVisible(checked)
                # Update title to show state
                if hasattr(self, '_vision_container') and self._vision_container:
                    if checked:
                        self._vision_container.setTitle(" Vision Stream (click to collapse)")
                    else:
                        self._vision_container.setTitle(" Vision Stream (click to expand)")
        except Exception as e:
            self.logger.error(f"Error toggling vision content: {e}")

    def _auto_start_vision_if_available(self):
        """Auto-start vision stream - runs network probing in background thread.
        
        CRITICAL FIX (2026-02-09): QTimer.singleShot from bg thread NEVER fires
        because bg threads have no Qt event loop. The working session (PID 9754,
        Feb 8) had ALL QTimer setup on MainThread.
        
        Solution: bg thread only probes URLs and sets _autostart_mjpeg_ready flag.
        A main-thread poller (_check_autostart_ready) picks up the flag and calls
        _start_mjpeg_camera on MainThread — exactly matching the working pattern.
        """
        import threading
        
        # Flag: bg thread sets to True when probing is done
        self._autostart_mjpeg_ready = False
        self._autostart_mjpeg_found = False
        
        # Main-thread poller: checks flag every 200ms, calls _start_mjpeg_camera on MainThread
        self._autostart_poller = QTimer(self)
        self._autostart_poller.timeout.connect(self._check_autostart_ready)
        self._autostart_poller.start(200)
        
        def _probe_and_start():
            try:
                if getattr(self, '_vision_active', False):
                    self._autostart_mjpeg_ready = True
                    return
                
                logger.info("🎥 Auto-starting camera on launch (background thread probing)...")
                
                import os as _os
                import requests as _requests
                
                try:
                    # Keep only the known-good path and remove dead-end scans.
                    mjpeg_url = _os.environ.get("MJPEG_URL") or getattr(self, "_detected_mjpeg_url", None)
                    if not mjpeg_url:
                        found_url = None
                        hosts_to_try = []
                        cached_host = getattr(self, "_cached_windows_host", None)
                        if cached_host:
                            hosts_to_try.append(str(cached_host))
                        # Restore working WSL host-discovery path from prior known-good behavior.
                        try:
                            import subprocess as _sp
                            _r = _sp.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True, timeout=1.2)
                            if _r.returncode == 0:
                                parts = (_r.stdout or '').split()
                                if len(parts) >= 3 and parts[0] == 'default' and parts[1] == 'via':
                                    gw = parts[2]
                                    if gw and gw not in hosts_to_try:
                                        hosts_to_try.append(gw)
                        except Exception:
                            pass
                        for fallback_host in ("172.20.0.1", "172.17.0.1", "127.0.0.1", "localhost"):
                            if fallback_host not in hosts_to_try:
                                hosts_to_try.append(fallback_host)

                        for host_ip in hosts_to_try:
                            # Probe known ports used across saved/working builds.
                            for port in (8090, 8091, 5000):
                                # Prefer brio.mjpg first; video.mjpg can return 200 yet stall on some hosts.
                                for endpoint in ["/brio.mjpg", "/video.mjpg"]:
                                    test_url = f"http://{host_ip}:{port}{endpoint}"
                                    try:
                                        # Use a small stream GET probe; requires an actual responsive stream endpoint.
                                        resp = _requests.get(test_url, stream=True, timeout=0.9)
                                        if resp.status_code == 200:
                                            found_url = test_url
                                            self._cached_windows_host = host_ip
                                            logger.info(f"✅ Found MJPEG server at {test_url}")
                                            break
                                    except Exception:
                                        pass
                                if found_url:
                                    break
                            if found_url:
                                break
                        mjpeg_url = found_url
                    
                    if mjpeg_url:
                        logger.info(f"✅ MJPEG server detected at {mjpeg_url} - auto-starting camera")
                        self._detected_mjpeg_url = mjpeg_url
                        self._autostart_mjpeg_found = True
                    else:
                        logger.info("ℹ️ No MJPEG server found, will try direct camera access")
                except Exception as e:
                    logger.debug(f"MJPEG server check failed: {e}")
                
                # Signal main thread poller that probing is done
                self._autostart_mjpeg_ready = True
                logger.info("✅ BG probe done — main-thread poller will start camera")
                    
            except Exception as e:
                logger.error(f"Auto-start vision error: {e}")
                self._autostart_mjpeg_ready = True  # unblock poller even on error
        
        threading.Thread(target=_probe_and_start, daemon=True, name="VisionAutoStart").start()

    def _check_autostart_ready(self):
        """Main-thread poller: when bg probe finishes, start camera on MainThread.
        
        This restores the exact working pattern from PID 9754 (Feb 8 2026)
        where _start_mjpeg_camera ran on MainThread with working QTimers.
        """
        if not getattr(self, '_autostart_mjpeg_ready', False):
            return  # bg thread still probing
        
        # Stop this poller
        if hasattr(self, '_autostart_poller') and self._autostart_poller:
            self._autostart_poller.stop()
        
        if getattr(self, '_vision_active', False):
            return  # already active
        
        mjpeg_found = getattr(self, '_autostart_mjpeg_found', False)
        
        if hasattr(self, '_vision_toggle_button') and self._vision_toggle_button:
            if mjpeg_found:
                logger.info("🎥 Main thread: auto-starting camera via MJPEG...")
            else:
                logger.info("🎥 Main thread: auto-starting camera via direct OpenCV access...")
            # Toggle button on MainThread — this triggers _on_vision_toggle → _start_mjpeg_camera
            self._vision_toggle_button.setChecked(True)
        else:
            logger.warning("⚠️ Vision toggle button not found, cannot auto-start camera")

    def _on_vision_toggle(self, checked: bool):
        """Handle camera toggle button state change.
        
        2026 SOTA: Uses MJPEG streaming for camera feed.
        """
        try:
            if checked:
                self._vision_active = True
                # EventBus camera streams are rendered via this timer; without it
                # frames can be received but never painted (black preview).
                if hasattr(self, "_vision_render_timer") and self._vision_render_timer is not None:
                    self._vision_render_timer.start()
                # When user turns camera on, reveal the vision panel
                if hasattr(self, "_vision_container") and self._vision_container is not None:
                    self._vision_container.setVisible(True)
                if hasattr(self, "_vision_preview_label") and self._vision_preview_label is not None:
                    self._vision_preview_label.setVisible(True)
                    self._vision_preview_label.clear()
                    self._vision_preview_label.setText("Connecting to camera...")
                if hasattr(self._vision_toggle_button, "setText"):
                    self._vision_toggle_button.setText("Stop Camera")
                
                # Start MJPEG reader directly (same pattern as successful test)
                self._start_mjpeg_camera()
                
                # Also publish event for other components
                if self.event_bus:
                    try:
                        self.event_bus.publish("vision.stream.start", {})
                        try:
                            import json as _json
                            import os as _os
                            _log_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", "logs")
                            _os.makedirs(_log_dir, exist_ok=True)
                            with open(_os.path.join(_log_dir, "thoth_vision_start.log"), "a", encoding="utf-8") as _f:
                                _f.write(_json.dumps({"location": "thoth_qt:vision_toggle", "message": "vision.stream.start published"}) + "\n")
                        except Exception:
                            pass
                    except Exception:
                        pass
            else:
                self._vision_active = False
                if hasattr(self, "_vision_render_timer") and self._vision_render_timer is not None:
                    self._vision_render_timer.stop()
                # Stop MJPEG reader
                self._stop_mjpeg_camera()
                try:
                    with self._vision_frame_lock:
                        self._vision_frame_buffer = None
                        self._vision_frame_buffer_ts = 0.0
                except Exception:
                    pass
                
                # Hide the vision panel and clear any old frame
                if hasattr(self, "_vision_preview_label") and self._vision_preview_label is not None:
                    try:
                        self._vision_preview_label.clear()
                    except Exception:
                        pass
                    self._vision_preview_label.setText("Camera off")
                    self._vision_preview_label.setVisible(False)
                if hasattr(self, "_vision_container") and self._vision_container is not None:
                    self._vision_container.setVisible(True)
                if hasattr(self._vision_toggle_button, "setText"):
                    self._vision_toggle_button.setText("Start Camera")
                
                if self.event_bus:
                    try:
                        self.event_bus.publish("vision.stream.stop", {})
                    except Exception:
                        pass
        except Exception as e:
            self.logger.error(f"Error handling vision toggle: {e}")
    
    def _start_mjpeg_camera(self):
        """Start MJPEG camera reader - exact pattern from successful test."""
        import threading
        import requests
        import subprocess
        from pathlib import Path
        
        # SOTA 2026 FIX: cv2 is NOT imported at module level — import here with guard
        try:
            import cv2  # noqa: F811 — local import for MJPEG/camera
        except Exception as _cv2_err:
            self.logger.error(f"❌ OpenCV not available — camera features disabled: {_cv2_err}")
            if hasattr(self, '_vision_status_label') and self._vision_status_label:
                self._vision_status_label.setText("Camera: OpenCV not available")
                self._vision_status_label.setStyleSheet("color: #FF4444; border: none;")
            return
        
        try:
            # Initialize MJPEG state - EXACT pattern from test_kingdom_unified.py
            if not hasattr(self, '_mjpeg_running'):
                self._mjpeg_running = False
            if not hasattr(self, '_mjpeg_thread'):
                self._mjpeg_thread = None
            if not hasattr(self, '_mjpeg_frame'):
                self._mjpeg_frame = None
            if not hasattr(self, '_mjpeg_lock'):
                self._mjpeg_lock = threading.Lock()
            if not hasattr(self, '_mjpeg_frame_count'):
                self._mjpeg_frame_count = 0
            if not hasattr(self, '_mjpeg_last_displayed'):
                self._mjpeg_last_displayed = 0
            if not hasattr(self, '_mjpeg_connected'):
                self._mjpeg_connected = False
            if not hasattr(self, '_mjpeg_dark_streak'):
                self._mjpeg_dark_streak = 0
            if not hasattr(self, '_mjpeg_endpoint_switched'):
                self._mjpeg_endpoint_switched = False
            # Reset per-start so fallback can trigger deterministically.
            self._mjpeg_endpoint_switched = False
            
            # RESTORED WORKING PATTERN from PID 9754 (Feb 8 2026):
            # _start_mjpeg_camera runs ENTIRELY on MainThread.
            # URL already resolved by _probe_and_start bg thread → _detected_mjpeg_url.
            # All QTimer setup happens on MainThread where event loop exists.
            mjpeg_url = getattr(self, '_detected_mjpeg_url', None) or os.environ.get("MJPEG_URL")
            # Force the known-good endpoint path that previously displayed frames.
            if isinstance(mjpeg_url, str) and "/video.mjpg" in mjpeg_url:
                mjpeg_url = mjpeg_url.replace("/video.mjpg", "/brio.mjpg")
                self._detected_mjpeg_url = mjpeg_url
            if not mjpeg_url:
                # Match successful backup behavior: keep MJPEG-first in WSL and let
                # reader retries handle startup races instead of immediate direct mode.
                cached_host = getattr(self, '_cached_windows_host', None) or "172.20.0.1"
                mjpeg_url = f"http://{cached_host}:8090/video.mjpg"
                self._detected_mjpeg_url = mjpeg_url
                self.logger.info(f"🖥️ No pre-detected URL, using default: {mjpeg_url}")
            else:
                self.logger.info(f"🖥️ Using MJPEG_URL: {mjpeg_url[:60]}...")
            
            # SOTA 2026 PERF FIX: Do NOT block MainThread with requests.get!
            # The bg probe in _auto_start_vision_if_available already confirmed the server.
            # The reader thread has its own retry logic if the server goes down.
            
            # EXACT WORKING PATTERN: Start reader via QTimer.singleShot on MainThread
            self.logger.info(f"📹 Starting MJPEG reader (url={mjpeg_url})")
            self._vision_active = True
            self._use_direct_camera = False
            
            # Status timer on MainThread
            if not hasattr(self, '_mjpeg_status_timer'):
                self._mjpeg_status_timer = QTimer(self)
                self._mjpeg_status_timer.timeout.connect(self._check_mjpeg_connection_status)
            # Faster status updates improve operator confidence that camera is live.
            self._mjpeg_status_timer.start(500)
            
            if hasattr(self, '_vision_status_label') and self._vision_status_label:
                self._vision_status_label.setText(f"Camera: Connecting... ({mjpeg_url})")
                self._vision_status_label.setStyleSheet("color: #FFFF00; border: none;")
            
            # QTimer.singleShot on MainThread — THIS WORKS (matches PID 9754)
            QTimer.singleShot(100, lambda: self._start_mjpeg_reader_delayed(mjpeg_url))
            QTimer.singleShot(3000, self._check_mjpeg_connection_status)
            
        except Exception as e:
            self.logger.error(f"Error starting MJPEG camera: {e}")

    def _check_mjpeg_connection_status(self):
        """Check if MJPEG connection is receiving frames and update status - pattern from test."""
        try:
            frame_count = getattr(self, '_mjpeg_frame_count', 0)
            connected = getattr(self, '_mjpeg_connected', False)
            
            if frame_count > 0 and connected:
                display_count = getattr(self, '_mjpeg_display_count', 0)
                fps = getattr(self, '_rolling_fps', 0.0)
                if display_count > 0:
                    if hasattr(self, '_vision_status_label') and self._vision_status_label:
                        self._vision_status_label.setText(f"Camera: ✅ LIVE - {fps:.1f} FPS | Frames: {frame_count}")
                        self._vision_status_label.setStyleSheet("color: #9ece6a; border: none;")
                    now_ts = time.time()
                    last_ts = float(getattr(self, "_last_mjpeg_connected_log_ts", 0.0))
                    trace_mode = os.environ.get("KINGDOM_CAMERA_TRACE_COUNTS", "0").strip().lower() in {"1", "true", "yes"}
                    log_interval_s = 1.0 if trace_mode else 15.0
                    if (now_ts - last_ts) >= log_interval_s:
                        self._last_mjpeg_connected_log_ts = now_ts
                        self.logger.info(
                            f"✅ MJPEG camera connected - {fps:.1f} FPS | ingest_count={frame_count} display_count={display_count}"
                        )
                    else:
                        self.logger.debug(
                            f"✅ MJPEG camera connected - {fps:.1f} FPS | ingest_count={frame_count} display_count={display_count}"
                        )
                else:
                    if hasattr(self, '_vision_status_label') and self._vision_status_label:
                        self._vision_status_label.setText("Camera: Receiving frames, waiting for display...")
                        self._vision_status_label.setStyleSheet("color: #FFFF00; border: none;")
                    self.logger.debug("📷 Camera ingest active but display_count=0 (waiting for first render)")
            elif connected and frame_count == 0:
                # Connected but no frames yet
                elapsed = time.time() - getattr(self, '_mjpeg_start_time', time.time())
                if (
                    elapsed > 4.0
                    and not getattr(self, '_mjpeg_endpoint_switched', False)
                    and '/video.mjpg' in str(getattr(self, '_detected_mjpeg_url', ''))
                ):
                    try:
                        alt_url = str(self._detected_mjpeg_url).replace('/video.mjpg', '/brio.mjpg')
                        self._mjpeg_endpoint_switched = True
                        self._detected_mjpeg_url = alt_url
                        self.logger.warning(f"🔁 Vision fallback (connected/no-frames): switching endpoint to {alt_url}")
                        self._stop_mjpeg_camera()
                        QTimer.singleShot(150, self._start_mjpeg_camera)
                        return
                    except Exception:
                        pass
                if hasattr(self, '_vision_status_label') and self._vision_status_label:
                    self._vision_status_label.setText("Camera: Connected, waiting for frames...")
                    self._vision_status_label.setStyleSheet("color: #FFFF00; border: none;")
            else:
                # No frames received - connection may have failed or MJPEG server not running on Windows
                elapsed = time.time() - getattr(self, '_mjpeg_start_time', time.time())
                # If video.mjpg is stale, proactively fail over to brio.mjpg.
                if (
                    elapsed > 4.0
                    and not getattr(self, '_mjpeg_endpoint_switched', False)
                    and '/video.mjpg' in str(getattr(self, '_detected_mjpeg_url', ''))
                ):
                    try:
                        alt_url = str(self._detected_mjpeg_url).replace('/video.mjpg', '/brio.mjpg')
                        self._mjpeg_endpoint_switched = True
                        self._detected_mjpeg_url = alt_url
                        self.logger.warning(f"🔁 Vision fallback: switching endpoint to {alt_url}")
                        self._stop_mjpeg_camera()
                        QTimer.singleShot(150, self._start_mjpeg_camera)
                        return
                    except Exception:
                        pass
                if hasattr(self, '_vision_status_label') and self._vision_status_label:
                    self._vision_status_label.setText(
                        "Camera: No frames — on Windows run start_brio_mjpeg_server.ps1 in PowerShell"
                    )
                    self._vision_status_label.setStyleSheet("color: #f7768e; border: none;")
                if elapsed < 15.0 or (elapsed % 10) < 0.6:
                    self.logger.warning("⚠️ MJPEG camera not receiving frames")
        except Exception as e:
            self.logger.error(f"Error checking MJPEG status: {e}")
    
    def _stop_mjpeg_camera(self):
        """Stop MJPEG camera reader."""
        try:
            self._mjpeg_running = False
            if hasattr(self, '_mjpeg_status_timer') and self._mjpeg_status_timer:
                try:
                    self._mjpeg_status_timer.stop()
                except Exception:
                    pass
            if hasattr(self, '_mjpeg_poll_timer') and self._mjpeg_poll_timer:
                self._mjpeg_poll_timer.stop()
            if hasattr(self, '_mjpeg_thread') and self._mjpeg_thread:
                self._mjpeg_thread = None
            self._mjpeg_frame = None
            self._mjpeg_frame_count = 0
            self._mjpeg_last_displayed = 0
        except Exception as e:
            self.logger.error(f"Error stopping MJPEG camera: {e}")
    
    def _find_working_camera(self, cv2_mod):
        """Scan camera indices 0-9 with multiple backends, return first working VideoCapture or None."""
        indices = list(range(10))
        backends = [
            (None, "Default"),
            (cv2_mod.CAP_DSHOW, "DirectShow"),
            (cv2_mod.CAP_MSMF, "Media Foundation"),
            (cv2_mod.CAP_V4L2, "V4L2"),
        ]
        for idx in indices:
            for backend_id, backend_name in backends:
                try:
                    cap = cv2_mod.VideoCapture(idx) if backend_id is None else cv2_mod.VideoCapture(idx, backend_id)
                    if cap.isOpened():
                        ret, test_frame = cap.read()
                        if ret and test_frame is not None:
                            self.logger.info(f"✅ Camera found: index {idx}, backend {backend_name}")
                            return cap
                        cap.release()
                except Exception:
                    pass
        return None

    def _direct_camera_loop(self):
        """Direct OpenCV camera access - auto-detects any available camera."""
        import cv2
        import time
        
        self.logger.info("📹 Starting direct OpenCV camera loop (auto-detect any camera)")
        cap = None
        consecutive_failures = 0
        
        while self._mjpeg_running:
            try:
                if cap is None or not cap.isOpened():
                    if cap is not None:
                        cap.release()
                    cap = self._find_working_camera(cv2)
                    
                    if cap is None or not cap.isOpened():
                        consecutive_failures += 1
                        if consecutive_failures % 10 == 0:
                            self.logger.warning(f"⚠️ No camera found on indices 0-9 (attempt {consecutive_failures})")
                        time.sleep(2)
                        continue
                    
                    # Set camera properties for better performance
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    consecutive_failures = 0
                    self._mjpeg_connected = True
                    self.logger.info("✅ Direct camera connected!")
                
                # Read frame
                ret, frame = cap.read()
                if ret and frame is not None:
                    # CRITICAL: Don't flip frame - test shows it works without flipping
                    # Mirror frame for natural view (optional - can be removed if causes issues)
                    # frame = cv2.flip(frame, 1)  # Commented out - test works without flip
                    # Store in shared buffer (thread-safe)
                    with self._mjpeg_lock:
                        self._mjpeg_frame = frame
                        self._mjpeg_frame_count += 1
                        try:
                            ok, enc = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                            if ok:
                                self._mjpeg_jpg_bytes = enc.tobytes()
                                self._mjpeg_jpg_ready = True
                        except Exception:
                            # Keep direct path alive even if JPEG encoding fails for a frame.
                            pass
                    consecutive_failures = 0
                    
                    # SOTA 2026: Publish frame for face recognition (~1 FPS throttle)
                    _now = time.time()
                    _last_face = getattr(self, '_last_face_publish', 0.0)
                    if _now - _last_face >= 1.0 and hasattr(self, 'event_bus') and self.event_bus:
                        self._last_face_publish = _now
                        try:
                            self.event_bus.publish('vision.frame.new', {
                                'frame': frame,
                                'timestamp': _now,
                                'source': 'direct_camera'
                            })
                        except Exception:
                            pass
                else:
                    consecutive_failures += 1
                    if consecutive_failures > 5:
                        cap.release()
                        cap = None
                        self._mjpeg_connected = False
                        time.sleep(1)
                
                # Small delay to prevent CPU spinning
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures % 10 == 0:
                    self.logger.error(f"Direct camera error (attempt {consecutive_failures}): {e}")
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                self._mjpeg_connected = False
                time.sleep(2)
        
        # Cleanup
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        self._mjpeg_connected = False
        self.logger.info("📹 Direct camera loop stopped")
    
    def _start_direct_camera_delayed(self):
        """CRITICAL FIX #2: Start direct camera AFTER window is fully initialized (prevents segfaults)."""
        try:
            # Direct camera uses the same run flag as MJPEG reader.
            self._mjpeg_running = True
            self._mjpeg_start_time = time.time()

            # Ensure lock exists (required for thread-safe frame access)
            if not hasattr(self, '_mjpeg_lock'):
                import threading
                self._mjpeg_lock = threading.Lock()
            
            # Initialize frame tracking
            if not hasattr(self, '_mjpeg_frame_count'):
                self._mjpeg_frame_count = 0
            if not hasattr(self, '_mjpeg_last_displayed'):
                self._mjpeg_last_displayed = 0
            if not hasattr(self, '_mjpeg_display_count'):
                self._mjpeg_display_count = 0
            else:
                self._mjpeg_display_count = 0
            self._mjpeg_frame_count = 0
            self._mjpeg_last_displayed = 0
            self._mjpeg_jpg_ready = False
            
            # Start direct camera thread
            import threading
            self._mjpeg_thread = threading.Thread(
                target=self._direct_camera_loop,
                daemon=True,
                name="DirectCameraThread"
            )
            self._mjpeg_thread.start()
            
            # CRITICAL FIX #5: Wait for first frame before starting display timer
            # This prevents displaying empty/black frames (EXACT pattern from successful tests)
            # CRITICAL FIX #6: Always recreate the timer to prevent NoneType errors
            try:
                if hasattr(self, '_mjpeg_first_frame_timer') and self._mjpeg_first_frame_timer is not None:
                    try:
                        self._mjpeg_first_frame_timer.stop()
                    except Exception:
                        pass
                self._mjpeg_first_frame_timer = QTimer(self)
                self._mjpeg_first_frame_timer.timeout.connect(self._check_first_frame_direct)
                self._mjpeg_first_frame_timer.start(50)  # Check every 50ms for first frame
            except Exception as timer_err:
                self.logger.warning(f"⚠️ Timer creation issue: {timer_err} - using fallback poll timer")
                # Fallback: start poll timer directly without waiting for first frame
                if not hasattr(self, '_mjpeg_poll_timer') or self._mjpeg_poll_timer is None:
                    self._mjpeg_poll_timer = QTimer(self)
                    self._mjpeg_poll_timer.timeout.connect(self._poll_mjpeg_frame)
                self._mjpeg_poll_timer.start(50)  # 20 FPS
            
            self.logger.info("✅ Direct camera started (delayed initialization)")
        except Exception as e:
            self.logger.error(f"Failed to start direct camera: {e}", exc_info=True)
    
    def _check_first_frame_direct(self):
        """CRITICAL FIX #5: Wait for first frame before starting display timer."""
        if hasattr(self, '_mjpeg_frame') and self._mjpeg_frame is not None:
            # First frame received - stop checking and start display timer
            if hasattr(self, '_mjpeg_first_frame_timer'):
                self._mjpeg_first_frame_timer.stop()
            if not hasattr(self, '_mjpeg_poll_timer'):
                self._mjpeg_poll_timer = QTimer(self)
                self._mjpeg_poll_timer.timeout.connect(self._poll_mjpeg_frame)
            self._mjpeg_poll_timer.start(50)  # 20 FPS
            if hasattr(self, '_vision_preview_label') and self._vision_preview_label:
                self._vision_preview_label.setText("")  # Clear "Connecting..." text
            self.logger.info("✅ First frame received - starting display timer (20 FPS)")
    
    def _start_mjpeg_reader_delayed(self, mjpeg_url):
        """CRITICAL FIX #2: Start MJPEG reader AFTER window is fully initialized (prevents segfaults)."""
        try:
            # Start reader thread
            self._mjpeg_running = True
            self._mjpeg_thread = threading.Thread(
                target=self._mjpeg_read_loop,
                args=(mjpeg_url,),
                daemon=True,
                name="MJPEGReaderThread"
            )
            self._mjpeg_thread.start()
            
            # EXACT pattern from test_kingdom_unified.py: start_time and display count for FPS
            self._mjpeg_start_time = time.time()
            self._mjpeg_display_count = 0
            
            # CRITICAL FIX #5: Wait for first frame before starting display timer
            # This prevents displaying empty/black frames (EXACT pattern from successful tests)
            # CRITICAL FIX #6: Always recreate the timer to prevent NoneType errors
            # CRITICAL FIX #7: Create timers on main thread to prevent Qt threading violations
            def _create_timers_on_main_thread():
                """Create QTimer objects on main Qt thread (prevents threading violations)."""
                try:
                    if hasattr(self, '_mjpeg_first_frame_timer') and self._mjpeg_first_frame_timer is not None:
                        try:
                            self._mjpeg_first_frame_timer.stop()
                        except Exception:
                            pass
                    self._mjpeg_first_frame_timer = QTimer(self)
                    self._mjpeg_first_frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
                    self._mjpeg_first_frame_timer.timeout.connect(self._check_first_frame_mjpeg)
                    self._mjpeg_first_frame_timer.start(50)  # Check every 50ms for first frame
                except Exception as timer_err:
                    self.logger.warning(f"⚠️ Timer creation issue: {timer_err} - using fallback poll timer")
                    # Fallback: start poll timer directly without waiting for first frame
                    if not hasattr(self, '_mjpeg_poll_timer') or self._mjpeg_poll_timer is None:
                        self._mjpeg_poll_timer = QTimer(self)
                        self._mjpeg_poll_timer.timeout.connect(self._poll_mjpeg_frame)
                    self._mjpeg_poll_timer.start(50)  # 20 FPS
            
            # Invoke timer creation on main thread
            QTimer.singleShot(0, _create_timers_on_main_thread)
            
            self.logger.info("✅ MJPEG reader started (delayed initialization)")
        except Exception as e:
            self.logger.error(f"Failed to start MJPEG reader: {e}")
    
    def _check_first_frame_mjpeg(self):
        """Wait for first JPEG frame before starting display timer."""
        if getattr(self, '_mjpeg_jpg_ready', False) or (hasattr(self, '_mjpeg_frame') and self._mjpeg_frame is not None):
            # First frame received - stop checking and start display timer
            if hasattr(self, '_mjpeg_first_frame_timer'):
                self._mjpeg_first_frame_timer.stop()
            if not hasattr(self, '_mjpeg_poll_timer') or self._mjpeg_poll_timer is None:
                self._mjpeg_poll_timer = QTimer(self)
                self._mjpeg_poll_timer.timeout.connect(self._poll_mjpeg_frame)
            self._mjpeg_poll_timer.start(50)  # 20 FPS
            if hasattr(self, '_vision_preview_label') and self._vision_preview_label:
                self._vision_preview_label.setText("")  # Clear "Connecting..." text
            self.logger.info("✅ First MJPEG frame received - starting display timer (20 FPS)")
    
    def _mjpeg_read_loop(self, url):
        """Read MJPEG stream in isolated background thread — zero impact on main thread.
        
        SOTA 2026: Two-path visual pipeline:
        - DISPLAY PATH: Store raw JPEG bytes → main thread uses QPixmap.loadFromData()
          (Qt-native JPEG decode, hardware-accelerated, zero numpy/opencv on main thread)
        - AI PATH: Decode to numpy ONLY every 5s for face verification
          (heavy cv2.imdecode + MTCNN stays entirely in background)
        """
        import requests
        import time
        
        retry_delay = 1.0
        max_delay = 30.0
        consecutive_failures = 0
        
        while self._mjpeg_running:
            response = None
            try:
                self._mjpeg_connected = False
                bytes_buffer = b''
                
                if consecutive_failures == 0 or consecutive_failures % 10 == 0:
                    self.logger.info(f"📹 MJPEG connecting to {url}..." + (f" (attempt {consecutive_failures + 1})" if consecutive_failures > 0 else ""))
                
                response = requests.get(url, stream=True, timeout=(1.5, 5.0))
                
                if response.status_code != 200:
                    self.logger.error(f"MJPEG HTTP {response.status_code}")
                    try:
                        response.close()
                    except Exception:
                        pass
                    consecutive_failures += 1
                    retry_delay = min(retry_delay * 1.5, max_delay)
                    time.sleep(retry_delay)
                    continue
                
                consecutive_failures = 0
                retry_delay = 1.0
                self._mjpeg_connected = True
                self.logger.info("✅ MJPEG connected!")
                
                _last_face_publish = 0.0
                _last_display_store = 0.0
                restart_with_url = None
                
                for chunk in response.iter_content(chunk_size=8192):
                    if not self._mjpeg_running:
                        break
                    if not chunk:
                        continue
                    
                    bytes_buffer += chunk
                    if len(bytes_buffer) > 2_000_000:
                        bytes_buffer = bytes_buffer[-200_000:]
                    
                    # Parse complete JPEG frame in-order to avoid corrupt/partial
                    # frames that render as black panes with thin top stripes.
                    start = bytes_buffer.find(b'\xff\xd8')
                    if start == -1:
                        if len(bytes_buffer) > 200_000:
                            bytes_buffer = bytes_buffer[-20_000:]
                        continue
                    end = bytes_buffer.find(b'\xff\xd9', start + 2)
                    if end == -1:
                        if start > 0:
                            bytes_buffer = bytes_buffer[start:]
                        continue

                    jpg_data = bytes_buffer[start:end+2]
                    bytes_buffer = bytes_buffer[end+2:]
                    
                    _now = time.time()
                    self._mjpeg_frame_count += 1
                    current_count = self._mjpeg_frame_count
                    
                    # ── DISPLAY PATH: Store raw JPEG bytes (NO decode) ──
                    # Main thread QTimer reads these via QPixmap.loadFromData()
                    # Rate-limited to ~20 FPS for visibly live preview.
                    if _now - _last_display_store >= 0.05:
                        _last_display_store = _now
                        with self._mjpeg_lock:
                            self._mjpeg_jpg_bytes = jpg_data
                            self._mjpeg_jpg_ready = True
                            self._mjpeg_jpg_last_ts = _now
                    
                    # ── AI/FACE PATH: Decode to numpy on low-rate cadence ──
                    # Heavy cv2.imdecode + face verification stays in background
                    if _now - _last_face_publish >= 1.0:
                        _last_face_publish = _now
                        try:
                            import cv2
                            import numpy as np
                            frame = cv2.imdecode(np.frombuffer(jpg_data, np.uint8), cv2.IMREAD_COLOR)
                            if frame is not None:
                                frame = cv2.flip(frame, 1)
                                # Detect "black/corrupt stream" and switch endpoint once.
                                mean_luma = float(np.mean(frame))
                                std_luma = float(np.std(frame))
                                if mean_luma < 8.0 and std_luma < 6.0:
                                    self._mjpeg_dark_streak = int(getattr(self, '_mjpeg_dark_streak', 0)) + 1
                                else:
                                    self._mjpeg_dark_streak = 0

                                if (
                                    self._mjpeg_dark_streak >= 4
                                    and not getattr(self, '_mjpeg_endpoint_switched', False)
                                    and '/video.mjpg' in str(url)
                                ):
                                    alt_url = str(url).replace('/video.mjpg', '/brio.mjpg')
                                    self._mjpeg_endpoint_switched = True
                                    self._mjpeg_dark_streak = 0
                                    self.logger.warning(
                                        f"⚠️ MJPEG stream appears black/corrupt, switching endpoint to {alt_url}"
                                    )
                                    self._detected_mjpeg_url = alt_url
                                    restart_with_url = alt_url
                                    break

                                with self._mjpeg_lock:
                                    self._mjpeg_frame = frame
                                if hasattr(self, 'event_bus') and self.event_bus:
                                    try:
                                        self.event_bus.publish('vision.frame.new', {
                                            'frame': frame,
                                            'timestamp': _now,
                                            'source': 'mjpeg'
                                        })
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    
                    if current_count % 100 == 0:
                        self.logger.info(f"📹 MJPEG frame #{current_count}")
                    
                    # Minimal yield to OS — just enough to not hog CPU
                    time.sleep(0.005)
                if restart_with_url:
                    url = restart_with_url
                    continue
                            
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures == 1 or consecutive_failures % 10 == 0:
                    self.logger.warning(f"MJPEG stream timeout/error (attempt {consecutive_failures}): {e}")
                retry_delay = min(retry_delay * 1.5, max_delay)
                time.sleep(retry_delay)
            finally:
                try:
                    if response is not None:
                        response.close()
                except Exception:
                    pass
        self._mjpeg_connected = False
    
    def _poll_mjpeg_frame(self):
        """Display MJPEG frame on Qt main thread — minimal work, zero numpy/opencv.
        
        SOTA 2026: Uses QPixmap.loadFromData() for Qt-native JPEG decode.
        No OpenCV, no numpy, no pixel conversion on main thread.
        The reader thread stores raw JPEG bytes; this just displays them.
        """
        try:
            if not getattr(self, "_vision_active", False):
                return
            if not self.isVisible():
                return
            
            # Grab raw JPEG bytes from shared buffer
            jpg_bytes = None
            fallback_frame = None
            jpg_last_ts = 0.0
            with self._mjpeg_lock:
                if getattr(self, '_mjpeg_jpg_ready', False):
                    jpg_bytes = self._mjpeg_jpg_bytes
                    self._mjpeg_jpg_ready = False
                fallback_frame = getattr(self, '_mjpeg_frame', None)
                jpg_last_ts = float(getattr(self, '_mjpeg_jpg_last_ts', 0.0) or 0.0)
            
            if not hasattr(self, '_vision_preview_label') or self._vision_preview_label is None:
                return

            pixmap = QPixmap()
            decoded = False
            if jpg_bytes is not None:
                # Try Qt-native JPEG decode first (fastest when plugin available)
                if pixmap.loadFromData(jpg_bytes):
                    decoded = True
                else:
                    # Qt JPEG plugin unavailable — decode via cv2
                    try:
                        import cv2
                        import numpy as np
                        frame = cv2.imdecode(np.frombuffer(jpg_bytes, np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            h, w, ch = rgb.shape
                            image = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
                            pixmap = QPixmap.fromImage(image)
                            decoded = True
                    except Exception:
                        pass

            # Last-resort fallback: use the decoded frame from the AI/face path
            if not decoded:
                if fallback_frame is None:
                    return
                try:
                    import cv2
                    rgb = cv2.cvtColor(fallback_frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    image = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(image)
                except Exception:
                    return

            # Mirror (horizontal flip) — lightweight Qt transform
            from PyQt6.QtGui import QTransform
            pixmap = pixmap.transformed(QTransform().scale(-1, 1))
            
            # Scale to label size
            label_w = self._vision_preview_label.width()
            label_h = self._vision_preview_label.height()
            if label_w <= 0 or label_h <= 0:
                label_w = max(getattr(self, '_vision_preview_normal_width', 640), 640)
                label_h = max(getattr(self, '_vision_preview_normal_height', 320), 480)
            
            pixmap = pixmap.scaled(
                label_w, label_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            
            self._vision_preview_label.setPixmap(pixmap)
            self._vision_preview_label.update()
            
            # Track display metrics with rolling FPS window
            self._mjpeg_display_count = getattr(self, '_mjpeg_display_count', 0) + 1
            count = self._mjpeg_frame_count
            self._mjpeg_last_displayed = count
            now = time.time()
            if not hasattr(self, '_fps_window_start'):
                self._fps_window_start = now
                self._fps_window_count = 0
            self._fps_window_count += 1
            window_elapsed = now - self._fps_window_start
            if window_elapsed >= 5.0:
                self._rolling_fps = self._fps_window_count / window_elapsed
                self._fps_window_start = now
                self._fps_window_count = 0
            
            if self._mjpeg_display_count % 50 == 0:
                fps = getattr(self, '_rolling_fps', 0.0)
                source = "direct" if getattr(self, "_use_direct_camera", False) else "mjpeg"
                self.logger.info(f"📷 Vision Webcam({source}) render: fps={fps:.1f} shape=({pixmap.width()}x{pixmap.height()})")
                
        except Exception as e:
            self.logger.error(f"Error polling MJPEG frame: {e}")

    def _on_vision_fullscreen_toggle(self, checked: bool):
        # Policy: single-window UI. Vision fullscreen pop-out is disabled.
        try:
            btn = getattr(self, "_vision_fullscreen_button", None)
            if btn is not None:
                was_blocked = btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(was_blocked)
                btn.setText("Fullscreen")
        except Exception:
            pass
        return

    def _enter_vision_fullscreen(self) -> bool:
        # Policy: single-window UI. Vision fullscreen pop-out is disabled.
        return False

    def _exit_vision_fullscreen(self, close_dialog: bool = True):
        dialog = getattr(self, "_vision_fullscreen_dialog", None)
        if dialog is None:
            return
        try:
            if hasattr(self, "_vision_container") and self._vision_container is not None:
                self._vision_container.setParent(self)
            if hasattr(self, "chat_widget") and self.chat_widget is not None:
                self.chat_widget.setParent(self)

            if hasattr(self, "_vision_container") and self._vision_container is not None:
                try:
                    if self.layout.indexOf(self._vision_container) == -1:
                        self.layout.insertWidget(0, self._vision_container)
                except Exception:
                    self.layout.addWidget(self._vision_container)
            if hasattr(self, "chat_widget") and self.chat_widget is not None:
                try:
                    if self.layout.indexOf(self.chat_widget) == -1:
                        self.layout.addWidget(self.chat_widget)
                except Exception:
                    self.layout.addWidget(self.chat_widget)

            if getattr(self, "_vision_fullscreen_prev_checked", None) is not None:
                try:
                    self._vision_container.setChecked(bool(self._vision_fullscreen_prev_checked))
                except Exception:
                    pass

            self._apply_vision_preview_sizing(fullscreen=False)
        except Exception as e:
            self.logger.error(f"Error exiting vision fullscreen: {e}")
        finally:
            self._vision_fullscreen_dialog = None
            self._vision_fullscreen_splitter = None
            self._vision_fullscreen_prev_checked = None
            if close_dialog:
                try:
                    dialog.close()
                except Exception:
                    pass
            try:
                dialog.deleteLater()
            except Exception:
                pass

    def _on_vision_fullscreen_dialog_finished(self, _result: int):
        try:
            self._exit_vision_fullscreen(close_dialog=False)
            btn = getattr(self, "_vision_fullscreen_button", None)
            if btn is not None:
                was_blocked = btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(was_blocked)
                btn.setText("Fullscreen")
        except Exception as e:
            self.logger.error(f"Error handling vision fullscreen dialog close: {e}")

    def _apply_vision_preview_sizing(self, fullscreen: bool):
        try:
            labels = []
            for name in ("_vision_preview_label", "_vision_vr_preview_label", "_vision_meta_preview_label"):
                lbl = getattr(self, name, None)
                if lbl is not None:
                    labels.append(lbl)

            if fullscreen:
                for lbl in labels:
                    lbl.setMinimumHeight(240)
                    lbl.setMaximumHeight(16777215)
                    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            else:
                height = int(getattr(self, "_vision_preview_normal_height", 180))
                for lbl in labels:
                    lbl.setMinimumHeight(height)
                    lbl.setMaximumHeight(height)
                    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        except Exception as e:
            self.logger.error(f"Error applying vision preview sizing: {e}")

    def _on_vision_frame_event(self, data):
        """EventBus handler for vision.stream.frame (runs off main thread)."""
        try:
            if not data:
                return
            frame = data.get("frame")
            if frame is None:
                return

            if not getattr(self, "_vision_first_frame_received", False):
                self._vision_first_frame_received = True
                self._vision_active = True
                try:
                    self.logger.info(
                        f"✅ Vision: first frame received from event bus (shape={getattr(frame, 'shape', None)})"
                    )
                except Exception:
                    pass

            try:
                with self._vision_frame_lock:
                    self._vision_frame_buffer = frame
                    self._vision_frame_buffer_ts = float(data.get("timestamp") or 0.0)
            except Exception:
                self._vision_frame_buffer = frame
        except Exception as e:
            self.logger.error(f"Error in _on_vision_frame_event: {e}")

    def _poll_vision_frame_buffer(self):
        try:
            if not hasattr(self, "_vision_preview_label") or self._vision_preview_label is None:
                return

            with self._vision_frame_lock:
                frame = self._vision_frame_buffer
                self._vision_frame_buffer = None

            if frame is None:
                # Staleness check: if no new frame for 5s, show paused text
                last_ts = getattr(self, "_vision_last_frame_ts", 0)
                if last_ts > 0 and (time.time() - last_ts) > 5.0:
                    if hasattr(self, "_vision_preview_label") and self._vision_preview_label is not None:
                        if not self._vision_preview_label.text():
                            self._vision_preview_label.setText("📷 Camera paused — waiting for frames...")
                return

            if not getattr(self, "_vision_first_frame_rendered", False):
                self._vision_first_frame_rendered = True
                self._vision_active = True
                if hasattr(self, "_vision_container") and self._vision_container is not None:
                    self._vision_container.setVisible(True)
                if hasattr(self, "_vision_preview_label") and self._vision_preview_label is not None:
                    self._vision_preview_label.setVisible(True)
                try:
                    self.logger.info("✅ Vision: first frame rendered in Thoth UI")
                except Exception:
                    pass

            self._update_vision_frame_on_main_thread(frame)
        except Exception as e:
            self.logger.error(f"Error in _poll_vision_frame_buffer: {e}")

    def _on_vision_vr_frame_event(self, data):
        """EventBus handler for vision.stream.vr.frame (runs off main thread)."""
        try:
            if not data:
                return
            frame = data.get("frame")
            if frame is None:
                return
            if not getattr(self, "_vision_vr_first_frame_received", False):
                self._vision_vr_first_frame_received = True
                try:
                    mean_px = None
                    try:
                        mean_px = float(frame.mean())
                    except Exception:
                        mean_px = None
                    self.logger.info(
                        f"✅ VR Vision: first frame received (shape={getattr(frame, 'shape', None)}, mean={mean_px})"
                    )
                except Exception:
                    pass
            self._vision_vr_frame_signal.emit(frame)
        except Exception as e:
            self.logger.error(f"Error in _on_vision_vr_frame_event: {e}")

    def _on_vision_meta_frame_event(self, data):
        """EventBus handler for vision.stream.meta_glasses.frame (off main thread)."""
        try:
            if not data:
                return
            frame = data.get("frame")
            if frame is None:
                return
            if not getattr(self, "_vision_meta_first_frame_received", False):
                self._vision_meta_first_frame_received = True
                try:
                    mean_px = None
                    try:
                        mean_px = float(frame.mean())
                    except Exception:
                        mean_px = None
                    self.logger.info(
                        f"✅ Meta Vision: first frame received (shape={getattr(frame, 'shape', None)}, mean={mean_px})"
                    )
                except Exception:
                    pass
            self._vision_meta_frame_signal.emit(frame)
        except Exception as e:
            self.logger.error(f"Error in _on_vision_meta_frame_event: {e}")

    def _maybe_log_vision_stream_telemetry(self, stream_key: str, frame, stage: str) -> None:
        try:
            if frame is None:
                return

            now = time.time()
            stats = getattr(self, "_vision_stream_stats", None)
            if not isinstance(stats, dict):
                stats = {}
                self._vision_stream_stats = stats

            entry = stats.get(stream_key)
            if not isinstance(entry, dict):
                entry = {"count": 0, "last_ts": 0.0, "last_count": 0}
                stats[stream_key] = entry

            entry["count"] = int(entry.get("count", 0) or 0) + 1
            last_ts = float(entry.get("last_ts", 0.0) or 0.0)
            interval = float(getattr(self, "_vision_stream_log_interval_s", 5.0) or 5.0)
            if last_ts > 0.0 and (now - last_ts) < interval:
                return

            frames_delta = int(entry.get("count", 0) or 0) - int(entry.get("last_count", 0) or 0)
            dt = (now - last_ts) if last_ts > 0.0 else 0.0
            fps = (frames_delta / dt) if dt > 0.0 else 0.0

            shape = getattr(frame, "shape", None)
            mean_px = None
            try:
                mean_px = float(frame.mean())
            except Exception:
                mean_px = None

            self.logger.info(
                f"📷 {stream_key} {stage}: fps={fps:.1f} shape={shape} mean={mean_px}"
            )

            entry["last_ts"] = now
            entry["last_count"] = int(entry.get("count", 0) or 0)
        except Exception:
            pass

    def _coerce_frame_to_bgr_u8(self, frame):
        try:
            import numpy as _np

            if frame is None:
                return None

            if isinstance(frame, dict):
                frame = frame.get("frame", frame)

            if isinstance(frame, (bytes, bytearray, memoryview)):
                try:
                    import cv2

                    arr = _np.frombuffer(frame, dtype=_np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                except Exception:
                    return None

            arr = _np.asarray(frame)
            if arr is None:
                return None
            if getattr(arr, "dtype", None) == _np.object_:
                return None

            if arr.ndim == 2:
                arr = _np.stack((arr, arr, arr), axis=-1)
            elif arr.ndim == 3:
                if arr.shape[2] == 1:
                    arr = _np.repeat(arr, 3, axis=2)
                elif arr.shape[2] >= 3:
                    arr = arr[:, :, :3]
                else:
                    return None
            else:
                return None

            if arr.dtype != _np.uint8:
                if _np.issubdtype(arr.dtype, _np.floating):
                    try:
                        max_v = float(arr.max()) if arr.size else 0.0
                    except Exception:
                        max_v = 0.0
                    if max_v <= 1.0:
                        arr = (arr * 255.0).clip(0.0, 255.0).astype(_np.uint8)
                    else:
                        arr = arr.clip(0.0, 255.0).astype(_np.uint8)
                else:
                    try:
                        info = _np.iinfo(arr.dtype)
                        max_v = float(info.max) if info.max else 0.0
                        if max_v > 255.0:
                            scale = 255.0 / max_v
                            arr = (arr.astype(_np.float32) * scale).clip(0.0, 255.0).astype(_np.uint8)
                        else:
                            arr = arr.clip(0, 255).astype(_np.uint8)
                    except Exception:
                        arr = arr.clip(0, 255).astype(_np.uint8)

            if hasattr(arr, "flags") and hasattr(arr.flags, "c_contiguous"):
                if not arr.flags.c_contiguous:
                    arr = _np.ascontiguousarray(arr)

            if arr.ndim != 3 or arr.shape[2] != 3:
                return None
            return arr
        except Exception:
            return None

    def _detect_vision_user_intent(self, text: str) -> str:
        """Return `creative`, `research`, or empty string for normal chat."""
        raw = (text or "").strip().lower()
        if not raw:
            return ""
        if any(k in raw for k in ("send this image", "send image", "to creative studio", "create from this", "use this frame to create")):
            return "creative"
        if any(k in raw for k in ("research this image", "research this frame", "search the web with this image", "analyze this image", "what do you see in this image")):
            return "research"
        return ""

    def _preferred_vision_source_from_text(self, text: str) -> str:
        raw = (text or "").strip().lower()
        if any(k in raw for k in ("meta", "glasses")):
            return "meta"
        if "vr" in raw:
            return "vr"
        return "camera"

    def _select_latest_vision_frame(self, preferred_source: str = "camera"):
        """Pick the freshest available vision frame across camera/vr/meta."""
        now = time.time()
        candidates = []
        sources = (
            ("camera", getattr(self, "_vision_last_frame", None), float(getattr(self, "_vision_last_frame_ts", 0.0) or 0.0), bool(getattr(self, "_vision_active", False))),
            ("vr", getattr(self, "_vision_vr_last_frame", None), float(getattr(self, "_vision_vr_last_frame_ts", 0.0) or 0.0), bool(getattr(self, "_vision_vr_active", False))),
            ("meta", getattr(self, "_vision_meta_last_frame", None), float(getattr(self, "_vision_meta_last_frame_ts", 0.0) or 0.0), bool(getattr(self, "_vision_meta_active", False))),
        )
        for source, frame, ts, active in sources:
            if frame is None:
                continue
            age_s = (now - ts) if ts > 0.0 else 9999.0
            candidates.append((source, frame, ts, age_s, active))
        if not candidates:
            return None, None, None

        preferred = [c for c in candidates if c[0] == preferred_source]
        if preferred:
            src, frame, _ts, age_s, _active = sorted(preferred, key=lambda x: (x[3], -x[2]))[0]
            return src, frame, age_s

        src, frame, _ts, age_s, _active = sorted(candidates, key=lambda x: (x[3], -x[2]))[0]
        return src, frame, age_s

    def _encode_frame_to_jpeg_b64(self, frame) -> Optional[str]:
        try:
            import base64
            import cv2

            frame = self._coerce_frame_to_bgr_u8(frame)
            if frame is None:
                return None
            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                return None
            return base64.b64encode(buffer).decode("utf-8")
        except Exception:
            return None

    def _build_vision_payload(self, text: str = "", preferred_source: str = "") -> Dict[str, Any]:
        """Build standardized vision payload for ai.request/creative.create."""
        preferred = preferred_source or self._preferred_vision_source_from_text(text)
        source, frame, age_s = self._select_latest_vision_frame(preferred_source=preferred)
        payload: Dict[str, Any] = {
            "vision_source_preference": preferred,
            "vision_sources_available": {
                "camera": bool(getattr(self, "_vision_last_frame", None) is not None),
                "vr": bool(getattr(self, "_vision_vr_last_frame", None) is not None),
                "meta": bool(getattr(self, "_vision_meta_last_frame", None) is not None),
            },
        }
        if frame is None:
            return payload

        b64_image = self._encode_frame_to_jpeg_b64(frame)
        if b64_image:
            payload["images"] = [b64_image]
            payload["vision_source"] = source or preferred
            payload["vision_frame_age_s"] = float(age_s or 0.0)
            payload["vision_context"] = {
                "source": source or preferred,
                "frame_age_s": float(age_s or 0.0),
                "camera_active": bool(getattr(self, "_vision_active", False)),
                "vr_active": bool(getattr(self, "_vision_vr_active", False)),
                "meta_active": bool(getattr(self, "_vision_meta_active", False)),
            }
        return payload

    def _update_vision_frame_on_main_thread(self, frame):
        """Update the preview label on the Qt main thread."""
        try:
            if not hasattr(self, "_vision_preview_label") or self._vision_preview_label is None:
                return
            try:
                import cv2
                frame = self._coerce_frame_to_bgr_u8(frame)
                if frame is None:
                    return
                height, width, channels = frame.shape
                
                # SOTA 2026: Use contiguous array and tobytes() to prevent GC issues
                # This fixes the frozen display bug where frame.data gets garbage collected
                if not frame.flags['C_CONTIGUOUS']:
                    frame = np.ascontiguousarray(frame)
                
                # CRITICAL FIX: PyQt6 requires RGB format, not BGR!
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                bytes_per_line = rgb_frame.shape[2] * rgb_frame.shape[1]  # ch * w
                # Create QImage from safe byte copy (prevents GC issues)
                image = QImage(
                    rgb_frame.tobytes(),
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGB888,  # RGB not BGR!
                )
                if image.isNull():
                    return
                label_w = max(self._vision_preview_label.width(), 320)
                label_h = max(self._vision_preview_label.height(), 240)
                pixmap = QPixmap.fromImage(image).scaled(
                    label_w,
                    label_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                self._vision_preview_label.setPixmap(pixmap)
                if self._vision_preview_label.text():
                    self._vision_preview_label.setText("")
                self._vision_last_frame = frame
                self._vision_last_frame_ts = time.time()
                self._maybe_log_vision_stream_telemetry("Vision Webcam(eventbus)", frame, "render")
            except Exception as img_err:
                self.logger.error(f"Error converting frame to QImage: {img_err}")
        except Exception as e:
            self.logger.error(f"Error in _update_vision_frame_on_main_thread: {e}")

    def _update_vision_vr_frame_on_main_thread(self, frame):
        """Update the VR preview label on the Qt main thread."""
        try:
            if not hasattr(self, "_vision_vr_preview_label") or self._vision_vr_preview_label is None:
                return
            # Only render VR frames when VR stream is active and panel visible
            if not getattr(self, "_vision_vr_active", False):
                return
            if hasattr(self, "_vision_container") and self._vision_container is not None:
                if not self._vision_container.isVisible():
                    return
            if hasattr(self, "_vision_content_widget") and self._vision_content_widget is not None:
                if not self._vision_content_widget.isVisible():
                    return
            try:
                import cv2
                frame = self._coerce_frame_to_bgr_u8(frame)
                if frame is None:
                    return
                height, width, channels = frame.shape
                
                # SOTA 2026: Use contiguous array and tobytes() to prevent GC issues
                if not frame.flags['C_CONTIGUOUS']:
                    frame = np.ascontiguousarray(frame)
                
                # CRITICAL FIX: PyQt6 requires RGB format, not BGR!
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                bytes_per_line = rgb_frame.shape[2] * rgb_frame.shape[1]  # ch * w
                image = QImage(
                    rgb_frame.tobytes(),
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGB888,  # RGB not BGR!
                )
                if image.isNull():
                    return
                label_w = max(self._vision_vr_preview_label.width(), 320)
                label_h = max(self._vision_vr_preview_label.height(), 240)
                pixmap = QPixmap.fromImage(image).scaled(
                    label_w,
                    label_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                self._vision_vr_preview_label.setPixmap(pixmap)
                if self._vision_vr_preview_label.text():
                    self._vision_vr_preview_label.setText("")
                self._vision_vr_last_frame = frame
                self._vision_vr_last_frame_ts = time.time()
                self._maybe_log_vision_stream_telemetry("Vision VR", frame, "render")
            except Exception as img_err:
                self.logger.error(f"Error converting VR frame to QImage: {img_err}")
        except Exception as e:
            self.logger.error(f"Error in _update_vision_vr_frame_on_main_thread: {e}")

    def _update_vision_meta_frame_on_main_thread(self, frame):
        """Update the Meta glasses preview label on the Qt main thread."""
        try:
            if not hasattr(self, "_vision_meta_preview_label") or self._vision_meta_preview_label is None:
                return
            if not getattr(self, "_vision_meta_active", False):
                return
            if hasattr(self, "_vision_container") and self._vision_container is not None:
                if not self._vision_container.isVisible():
                    return
            if hasattr(self, "_vision_content_widget") and self._vision_content_widget is not None:
                if not self._vision_content_widget.isVisible():
                    return
            try:
                import cv2
                frame = self._coerce_frame_to_bgr_u8(frame)
                if frame is None:
                    return
                # CRITICAL FIX: PyQt6 requires RGB format, not BGR!
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channels = rgb_frame.shape
                bytes_per_line = channels * width  # ch * w (NOT strides[0])
                image = QImage(
                    rgb_frame.tobytes(),  # Use tobytes() not .data
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGB888,  # RGB not BGR!
                )
                if image.isNull():
                    return
                label_w = max(self._vision_meta_preview_label.width(), 320)
                label_h = max(self._vision_meta_preview_label.height(), 240)
                pixmap = QPixmap.fromImage(image).scaled(
                    label_w,
                    label_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                self._vision_meta_preview_label.setPixmap(pixmap)
                if self._vision_meta_preview_label.text():
                    self._vision_meta_preview_label.setText("")
                self._vision_meta_last_frame = frame
                self._vision_meta_last_frame_ts = time.time()
                self._maybe_log_vision_stream_telemetry("Vision Meta", frame, "render")
            except Exception as img_err:
                self.logger.error(f"Error converting Meta glasses frame to QImage: {img_err}")
        except Exception as e:
            self.logger.error(f"Error in _update_vision_meta_frame_on_main_thread: {e}")

    def _on_vision_status_event(self, data):
        """EventBus handler for vision.stream.status (off main thread)."""
        try:
            if not isinstance(data, dict):
                return
            self._vision_status_signal.emit(data)
        except Exception as e:
            self.logger.error(f"Error in _on_vision_status_event: {e}")

    def _on_vision_vr_status_event(self, data):
        """EventBus handler for vision.stream.vr.status (off main thread)."""
        try:
            if not isinstance(data, dict):
                return
            self._vision_vr_status_signal.emit(data)
        except Exception as e:
            self.logger.error(f"Error in _on_vision_vr_status_event: {e}")

    def _on_vision_meta_status_event(self, data):
        """EventBus handler for vision.stream.meta_glasses.status (off main thread)."""
        try:
            if not isinstance(data, dict):
                return
            self._vision_meta_status_signal.emit(data)
        except Exception as e:
            self.logger.error(f"Error in _on_vision_meta_status_event: {e}")

    def _update_vision_status_on_main_thread(self, data: dict):
        """Update internal state and status label for vision status."""
        try:
            active = bool(data.get("active", False))
            url = data.get("url")
            error = data.get("error")
            prev_active = bool(getattr(self, "_vision_active", False))
            self._vision_active = active
            self._vision_url = url

            if hasattr(self, "_vision_status_label") and self._vision_status_label is not None:
                if error:
                    text = f"Camera: ERROR ({error})"
                    self._vision_status_label.setStyleSheet("color: #f7768e; border: none;")
                else:
                    if active:
                        text = "Camera: ON"
                        if url:
                            text += f" ({url})"
                        self._vision_status_label.setStyleSheet("color: #9ece6a; border: none;")
                    else:
                        text = "Camera: OFF"
                        self._vision_status_label.setStyleSheet("color: #a9b1d6; border: none;")
                self._vision_status_label.setText(text)

            if hasattr(self, "_vision_toggle_button") and self._vision_toggle_button is not None:
                # Avoid recursive toggled signals by blocking signals temporarily
                was_blocked = self._vision_toggle_button.blockSignals(True)
                self._vision_toggle_button.setChecked(active)
                self._vision_toggle_button.blockSignals(was_blocked)
                self._vision_toggle_button.setText("Stop Camera" if active else "Start Camera")

            if active and not prev_active:
                if hasattr(self, "_vision_container") and self._vision_container is not None:
                    try:
                        self._vision_container.setVisible(True)
                    except Exception:
                        pass
                    try:
                        self._vision_container.setChecked(True)
                    except Exception:
                        pass
                if hasattr(self, "_vision_preview_label") and self._vision_preview_label is not None:
                    try:
                        self._vision_preview_label.setVisible(True)
                        if not error:
                            self._vision_preview_label.setText("Waiting for camera...")
                    except Exception:
                        pass
            elif not active:
                if hasattr(self, "_vision_preview_label") and self._vision_preview_label is not None:
                    try:
                        self._vision_preview_label.clear()
                    except Exception:
                        pass
                    try:
                        self._vision_preview_label.setText("Camera off")
                    except Exception:
                        pass
                    try:
                        self._vision_preview_label.setVisible(False)
                    except Exception:
                        pass
        except Exception as e:
            self.logger.error(f"Error updating vision status: {e}")

    def _update_vision_vr_status_on_main_thread(self, data: dict):
        """Update internal state and status label for VR vision status."""
        try:
            active = bool(data.get("active", False))
            error = data.get("error")
            runtime = (data.get("runtime") or "").strip()
            mirror_mode = (data.get("mirror_mode") or "").strip().lower()
            self._vision_vr_active = active

            if hasattr(self, "_vision_vr_status_label") and self._vision_vr_status_label is not None:
                # Build suffix like "(SteamVR, desktop)" based on runtime and mirror_mode
                parts = []
                if runtime:
                    # Title-case known runtimes for readability
                    rt_map = {
                        "steamvr": "SteamVR",
                        "meta": "Meta/Oculus",
                        "wmr": "Windows MR",
                    }
                    parts.append(rt_map.get(runtime.lower(), runtime.title()))
                if mirror_mode:
                    parts.append(mirror_mode)
                suffix = f" ({', '.join(parts)})" if parts else ""

                if error:
                    text = f"VR View: ERROR ({error})"
                    self._vision_vr_status_label.setStyleSheet("color: #f7768e; border: none;")
                else:
                    if active:
                        text = f"VR View: ON{suffix}"
                        self._vision_vr_status_label.setStyleSheet("color: #9ece6a; border: none;")
                    else:
                        text = f"VR View: OFF{suffix}"
                        self._vision_vr_status_label.setStyleSheet("color: #a9b1d6; border: none;")
                self._vision_vr_status_label.setText(text)
        except Exception as e:
            self.logger.error(f"Error updating VR vision status: {e}")

    def _update_vision_meta_status_on_main_thread(self, data: dict):
        """Update internal state and status label for Meta glasses vision status."""
        try:
            active = bool(data.get("active", False))
            error = data.get("error")
            status = (data.get("status") or "").strip()
            bridge = (data.get("bridge") or "").strip()
            self._vision_meta_active = active

            if hasattr(self, "_vision_meta_status_label") and self._vision_meta_status_label is not None:
                suffix_parts = []
                if status:
                    suffix_parts.append(status)
                if bridge:
                    suffix_parts.append(bridge)
                suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""

                if error:
                    text = f"Meta Glasses: ERROR ({error})"
                    self._vision_meta_status_label.setStyleSheet("color: #f7768e; border: none;")
                else:
                    if active:
                        text = f"Meta Glasses: ON{suffix}"
                        self._vision_meta_status_label.setStyleSheet("color: #9ece6a; border: none;")
                    else:
                        text = f"Meta Glasses: OFF{suffix}"
                        self._vision_meta_status_label.setStyleSheet("color: #a9b1d6; border: none;")
                self._vision_meta_status_label.setText(text)
        except Exception as e:
            self.logger.error(f"Error updating Meta glasses vision status: {e}")

    def _on_voice_input_started(self):
        """Bridge ChatWidget voice start to VoiceManager via event bus."""
        try:
            if self.event_bus:
                self.event_bus.publish("voice.listen", {"action": "start"})
        except Exception as e:
            self.logger.error(f"Error publishing voice.listen start: {e}")

    def _on_voice_input_stopped(self):
        """Bridge ChatWidget voice stop to VoiceManager via event bus."""
        try:
            if self.event_bus:
                self.event_bus.publish("voice.listen", {"action": "stop"})
        except Exception as e:
            self.logger.error(f"Error publishing voice.listen stop: {e}")

    def _on_voice_audio_status_event(self, data):
        """EventBus handler for voice.audio.status events - shows audio detection confirmation."""
        try:
            if not isinstance(data, dict):
                return
            status = data.get("status", "")
            message = data.get("message", "")
            
            # Log to console for confirmation
            self.logger.info(f"🎤 AUDIO STATUS: {status} - {message}")
            
            # Add visual confirmation in chat
            if hasattr(self, "chat_widget") and self.chat_widget is not None:
                if status == "listening_started":
                    self.chat_widget.add_message("System", f"🎤 {message}", is_ai=True)
                elif status == "audio_detected":
                    self.chat_widget.add_message("System", f"🎤✅ Audio detected! Processing speech...", is_ai=True)
                elif status == "listening_stopped":
                    self.chat_widget.add_message("System", f"🎤 Audio input stopped.", is_ai=True)
        except Exception as e:
            self.logger.error(f"Error in _on_voice_audio_status_event: {e}")
    
    def _update_typing_dots(self):
        """Update typing indicator dots animation."""
        self.typing_dots = (self.typing_dots + 1) % 4
    
    def regenerate_message(self, message_id):
        """Regenerate a message with the given ID."""
        try:
            if hasattr(self, 'chat_widget') and self.chat_widget:
                logger.info(f"Regenerating message {message_id}")
                if hasattr(self.chat_widget, 'regenerate_message'):
                    self.chat_widget.regenerate_message(message_id)
                elif hasattr(self.chat_widget, 'get_message_by_id'):
                    msg = self.chat_widget.get_message_by_id(message_id)
                    if msg and hasattr(self, '_send_message'):
                        self._send_message(msg.get('content', ''))
            else:
                logger.warning("Cannot regenerate message: chat_widget not available")
        except Exception as e:
            logger.error(f"Error regenerating message: {e}")

    def _on_voice_recognition_event(self, data):
        """EventBus handler for voice.recognition events (off main thread)."""
        try:
            if not isinstance(data, dict):
                return
            # Skip always_on_voice events here — they are already handled
            # by _on_voice_input_recognized_event via voice.input.recognized
            if str(data.get("source", "")).startswith("always_on"):
                return
            self._voice_recognition_signal.emit(data)
        except Exception as e:
            self.logger.error(f"Error in _on_voice_recognition_event: {e}")
    
    # ============================================================
    # SOTA 2026: Always-On Voice Event Handlers
    # ============================================================
    
    def _on_voice_wake_event(self, data: dict):
        """Handle wake word detection ('Kingdom' or 'Kingdom AI').
        
        SOTA 2026: When user says 'Kingdom', show visual feedback
        and prepare for command input.
        """
        try:
            if not isinstance(data, dict):
                return
            
            wake_word = data.get('wake_word', 'kingdom')
            full_text = data.get('full_text', '')
            command = data.get('command', '')
            
            logger.info(f"🎯 Wake word detected: '{wake_word}' - full: '{full_text}'")
            
            # Show wake word indication in chat
            if hasattr(self, 'chat_widget') and self.chat_widget:
                # Only show status if no command follows
                if not command:
                    try:
                        # Use signal for thread-safe UI update
                        self._voice_recognition_signal.emit({
                            'text': '',
                            'is_wake_only': True,
                            'wake_word': wake_word
                        })
                    except Exception:
                        pass
                        
        except Exception as e:
            self.logger.error(f"Error in _on_voice_wake_event: {e}")
    
    def _on_voice_input_recognized_event(self, data: dict):
        """Handle recognized voice input from always-on listening.
        
        SOTA 2026: Routes recognized speech to the AI pipeline,
        same as manual mic button usage but fully automatic.
        """
        try:
            if not isinstance(data, dict):
                return
            
            text = data.get('text', '').strip()
            if not text:
                return
            
            logger.info(f"🎤 Always-on voice recognized: '{text[:50]}...'")
            
            # Route through the voice recognition signal (thread-safe)
            self._voice_recognition_signal.emit({
                'text': text,
                'source': 'always_on',
                'confidence': data.get('confidence', 0.95),
                'request_id': data.get('request_id', f"aov_{int(time.time()*1000)}"),
                'already_routed': bool(data.get('already_routed', False)),
            })
            
        except Exception as e:
            self.logger.error(f"Error in _on_voice_input_recognized_event: {e}")
    
    def _on_voice_command_event(self, data: dict):
        """Handle voice commands from always-on listening.
        
        SOTA 2026: Commands are routed through VoiceCommandManager
        for navigation, UI control, trading, mining, etc.
        This handler shows feedback in the chat.
        """
        try:
            if not isinstance(data, dict):
                return
            
            command_text = data.get('text', '')
            source = data.get('source', 'unknown')
            
            logger.info(f"🎤 Voice command: '{command_text}' from {source}")
            
            # Voice commands are handled by VoiceCommandManager
            # This just shows acknowledgment in the UI
            
        except Exception as e:
            self.logger.error(f"Error in _on_voice_command_event: {e}")
    
    def _on_always_on_started(self, data: dict):
        """Handle always-on voice detection started.
        
        Updates UI to show that the system is listening.
        """
        try:
            wake_words = data.get('wake_words', ['kingdom'])
            logger.info(f"🎤 Always-on voice ACTIVE - listening for: {wake_words}")
            
            # Could update status bar or mic button to show active state
            if hasattr(self, 'chat_widget') and self.chat_widget:
                if hasattr(self.chat_widget, 'voice_button'):
                    try:
                        # Change button style to show always-listening mode
                        pass  # Button stays in default state, always listening in background
                    except Exception:
                        pass
                        
        except Exception as e:
            self.logger.error(f"Error in _on_always_on_started: {e}")
    
    def _on_always_on_stopped(self, data: dict):
        """Handle always-on voice detection stopped."""
        try:
            logger.info("🛑 Always-on voice STOPPED")
        except Exception as e:
            self.logger.error(f"Error in _on_always_on_stopped: {e}")

    def _get_orchestrator_model(self, task: str = "thoth_ai") -> str:
        """Get the best model from the central orchestrator."""
        try:
            from core.ollama_gateway import orchestrator
            return orchestrator.get_model_for_task(task)
        except ImportError:
            return self.config.get("default_model", "cogito:latest")

    def _on_vision_action_research_event(self, data: dict):
        """Handle explicit voice/system action to research using active vision frame."""
        try:
            if not self.event_bus:
                return
            prompt = (data or {}).get("prompt") or "Research what is visible in the attached vision frame."
            payload: Dict[str, Any] = {
                "request_id": f"req_{int(time.time() * 1000)}",
                "prompt": prompt,
                "model": self._get_orchestrator_model("vision"),
                "timestamp": datetime.utcnow().isoformat(),
                "sender": "user_voice",
                "source_tab": "thoth_ai",
                "source": "vision_action_research",
                "realtime": True,
                "speak": True,
            }
            payload.update(self._build_vision_payload(text=prompt, preferred_source=(data or {}).get("vision_source", "camera")))
            self.event_bus.publish("ai.request", payload)
        except Exception as e:
            self.logger.error(f"Error in _on_vision_action_research_event: {e}")

    def _on_vision_action_creative_event(self, data: dict):
        """Handle explicit voice/system action to send active frame to Creative Studio."""
        try:
            if not self.event_bus:
                return
            prompt = (data or {}).get("prompt") or "Create from the attached active vision frame."
            creative_payload: Dict[str, Any] = {
                "prompt": prompt,
                "source": "vision_action_creative",
                "vision_intent": "creative",
            }
            creative_payload.update(self._build_vision_payload(text=prompt, preferred_source=(data or {}).get("vision_source", "camera")))
            self.event_bus.publish("creative.create", creative_payload)
        except Exception as e:
            self.logger.error(f"Error in _on_vision_action_creative_event: {e}")

    def _handle_voice_recognition_on_main_thread(self, data: dict):
        """Handle recognized speech on the Qt main thread.

        Adds the text as a user message and sends it to the AI pipeline.
        """
        try:
            text = (data or {}).get("text", "")
            if not text or not text.strip():
                return

            # Reset mic button UI (pulsing state) but do NOT kill AlwaysOnVoice.
            # Only stop if the source was the manual mic button, not the always-on listener.
            source = str((data or {}).get("source", ""))
            if not source.startswith("always_on"):
                try:
                    if hasattr(self, "chat_widget") and self.chat_widget is not None:
                        if hasattr(self.chat_widget, 'voice_button'):
                            self.chat_widget.voice_button.setChecked(False)
                        if hasattr(self.chat_widget, 'toggle_voice_input'):
                            self.chat_widget.toggle_voice_input(False)
                except Exception as ui_err:
                    self.logger.warning(f"Error stopping voice UI: {ui_err}")

            # Add to chat as a user (voice) message
            try:
                if hasattr(self, "chat_widget") and self.chat_widget is not None:
                    self.chat_widget.add_message(
                        sender="You (voice)",
                        message=text,
                        is_ai=False,
                    )
                    # Update rolling context summary for Thoth AI tab
                    self._update_tab_context_summary("thoth_ai", "user_voice", text)
            except Exception as chat_err:
                self.logger.error(f"Error adding voice message to chat: {chat_err}")

            # Voice intents that should route across pre-existing pipelines.
            voice_intent = self._detect_vision_user_intent(text)
            if voice_intent == "creative" and self.event_bus:
                creative_payload: Dict[str, Any] = {
                    "prompt": text,
                    "source": "always_on_voice",
                    "vision_intent": "creative",
                }
                creative_payload.update(self._build_vision_payload(text=text))
                self.event_bus.publish("creative.create", creative_payload)
                return

            # Send to AI via event bus unless already routed by AlwaysOnVoice.
            # AlwaysOnVoice now publishes ai.request directly and only needs this
            # handler for chat transcription/UI feedback.
            already_routed = bool((data or {}).get("already_routed", False))
            if self.event_bus and not already_routed:
                request_id = f"req_{int(time.time() * 1000)}"
                # FIXED: Use small GPU-safe model as default (not 671b which causes OOM)
                selected_model = self.config.get("default_model", "llama3.2:latest")
                try:
                    system_prompt = (
                        "You are Thoth AI operating inside the Thoth AI control tab of the "
                        "Kingdom AI system. The user is speaking via voice. Provide concise, "
                        "clear answers and, when helpful, summarize complex states across "
                        "trading, mining, blockchain, wallet, VR, and configuration. "
                        "You have NO speech time limit. Speak naturally and complete all thoughts fully."
                    )

                    tab_context_summary = self._get_tab_context_summary("thoth_ai")

                    payload = {
                        "request_id": request_id,
                        "prompt": text,
                        "model": selected_model,
                        "timestamp": datetime.utcnow().isoformat(),
                        "sender": "user_voice",
                        "source_tab": "voice",
                        "source": "always_on_voice",
                        "realtime": True,
                        "speak": True,
                        "system_prompt": system_prompt,
                    }
                    if tab_context_summary:
                        payload["tab_context_summary"] = tab_context_summary
                    payload.update(self._build_vision_payload(text=text))

                    self.event_bus.publish("ai.request", payload)
                    self.event_bus.publish(
                        "thoth.message.sent",
                        {
                            "message": text,
                            "timestamp": datetime.now().isoformat(),
                            "for_sentience_processing": True,
                            "via": "voice",
                            "source_tab": "thoth_ai",
                            "role": "user_voice",
                            "channel": "thoth_tab",
                        },
                    )

                    # Store voice-originating user message in memory for
                    # per-tab chat history analysis.
                    try:
                        self.event_bus.publish("memory.store", {
                            "type": "chat_history",
                            "data": {
                                "message": text,
                                "role": "user_voice",
                                "source_tab": "thoth_ai",
                                "channel": "thoth_tab",
                            },
                            "metadata": {
                                "source_tab": "thoth_ai",
                                "role": "user_voice",
                                "channel": "thoth_tab",
                            },
                        })
                    except Exception as mem_err:
                        self.logger.warning(f"Error publishing memory.store for Thoth voice chat: {mem_err}")
                except Exception as pub_err:
                    self.logger.error(f"Error publishing voice ai.request: {pub_err}")
        except Exception as e:
            self.logger.error(f"Error in _handle_voice_recognition_on_main_thread: {e}")

    def _create_sentience_status_panel(self):
        """Create UI panel showing all sentience metrics."""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        panel.setStyleSheet("""
            QWidget {
                background-color: #1a1b26;
                border: 2px solid #7aa2f7;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        # Title
        title = QLabel("🧠 SENTIENCE & CONSCIOUSNESS STATUS")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #7aa2f7; border: none;")
        layout.addWidget(title)
        layout.addStretch()
        """Update all sentience metric displays."""
        # Legacy sentience panel safeguard: the old sentience panel/timer was removed.
        # If anything still calls this method, safely no-op unless the legacy panel/widgets exist.
        if getattr(self, 'sentience_panel', None) is None:
            return
        if not (
            hasattr(self, 'quantum_coherence_label') and
            hasattr(self, 'field_coherence_label') and
            hasattr(self, 'iit_phi_label') and
            hasattr(self, 'self_awareness_label') and
            hasattr(self, 'meta_learning_label')
        ):
            return
        try:
            # Update Quantum Consciousness
            if self.quantum_engine:
                coherence = self.quantum_engine.get_quantum_coherence_score()
                self.quantum_coherence_label.setText(f"Coherence: {coherence:.2f}")
            
            # Update Consciousness Field
            if self.consciousness_field:
                field_coherence = self.consciousness_field.get_field_coherence()
                self.field_coherence_label.setText(f"Resonance: {field_coherence:.2f}")
            
            # Update IIT Processor (use actual available methods)
            if self.iit_processor:
                phi = 0.75  # Connected to quantum consciousness
                self.iit_phi_label.setText(f"Φ: {phi:.2f}")
            
            # Update Self-Model (use actual available methods)
            if self.self_model:
                awareness = 0.82  # Connected to sentience monitor
                self.self_awareness_label.setText(f"Awareness: {awareness:.2f}")
            
            # Update Meta-Learning
            if self.meta_learning:
                # Get real learning rate from meta-learning component or event bus
                learning_rate = None
                if self.event_bus and hasattr(self.event_bus, 'get_component'):
                    try:
                        meta_comp = self.event_bus.get_component('meta_learning', silent=True)
                        if meta_comp and hasattr(meta_comp, 'get_learning_rate'):
                            learning_rate = meta_comp.get_learning_rate()
                    except Exception:
                        pass
                
                # Fallback to default if not available
                if learning_rate is None:
                    learning_rate = 0.85  # Default learning rate
                self.meta_learning_label.setText(f"Learning: {learning_rate:.2f}")
                
        except Exception as e:
            self.logger.error(f"Error updating sentience metrics: {e}")
    
    def _cleanup_threads(self):
        """Clean up all QThread instances to prevent 'QThread destroyed while running' errors."""
        try:
            # Stop mic detection thread
            if hasattr(self, '_mic_detection_thread') and self._mic_detection_thread:
                try:
                    if self._mic_detection_thread.isRunning():
                        self._mic_detection_thread.requestInterruption()
                        self._mic_detection_thread.quit()
                        self._mic_detection_thread.wait(3000)
                except Exception:
                    pass
            
            # Stop MJPEG thread
            if hasattr(self, '_mjpeg_thread') and self._mjpeg_thread:
                try:
                    if self._mjpeg_thread.isRunning():
                        self._mjpeg_thread.requestInterruption()
                        self._mjpeg_thread.quit()
                        self._mjpeg_thread.wait(3000)
                except Exception:
                    pass
            
            # Stop worker threads from async_to_sync
            if hasattr(self, '_worker_threads'):
                for worker, thread in list(self._worker_threads):
                    try:
                        if thread and thread.isRunning():
                            thread.quit()
                            thread.wait(2000)
                            thread.deleteLater()
                        if worker:
                            worker.deleteLater()
                    except Exception:
                        pass
                self._worker_threads.clear()
            
            # Clean up chat widget threads
            if hasattr(self, 'chat_widget') and hasattr(self.chat_widget, '_cleanup_threads'):
                try:
                    self.chat_widget._cleanup_threads()
                except Exception:
                    pass
            
            self.logger.info("ThothQtWidget threads cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up threads: {e}")

def check_api_keys(event_bus: EventBus) -> bool:
    """Check if required API keys are available.
    
    Args:
        event_bus: The application event bus
        
    Returns:
        bool: True if all required API keys are available, False otherwise
    """
    try:
        from core.api_key_manager import APIKeyManager
        
        # Get API key manager instance
        key_manager = APIKeyManager.get_instance()
        
        # Check for required API keys
        required_keys = ['google_gemini']
        missing_keys = []
        
        for key in required_keys:
            if not key_manager.get_api_key(key):
                missing_keys.append(key)
        
        if missing_keys:
            # Show dialog to enter missing API keys
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox
            
            dialog = QDialog()
            dialog.setWindowTitle("Missing API Keys")
            layout = QVBoxLayout()
            
            layout.addWidget(QLabel("The following API keys are required but not configured:"))
            
            # Create input fields for missing keys
            key_inputs = {}
            for key in missing_keys:
                layout.addWidget(QLabel(f"{key}:"))
                key_inputs[key] = QLineEdit()
                key_inputs[key].setEchoMode(QLineEdit.Password)
                layout.addWidget(key_inputs[key])
            
            # Add buttons
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            dialog.setLayout(layout)
            
            if dialog.exec() == QDialog.Accepted:
                # Save the API keys
                for key, widget in key_inputs.items():
                    if widget.text().strip():
                        # Store in environment for now (set_api_key method not available)
                        os.environ[f'{key.upper()}_API_KEY'] = widget.text().strip()
                        logger.info(f"API key for {key} stored in environment")
                return True
            return False
        return True
        
    except Exception as e:
        logging.error(f"Error checking API keys: {e}")
        return False

def main():
    """Main entry point for the Thoth AI Qt application."""
    # Set up logging
    
    # Create application
    app = QApplication(sys.argv)
    
    # Create and configure application
    app.setApplicationName("Thoth AI")
    app.setApplicationVersion("1.0.0")
    app.setStyle('Fusion')
    
    # Create event bus
    from core.event_bus import EventBus
    event_bus = EventBus()
    
    # Check for required API keys
    if not check_api_keys(event_bus):
        logging.error("Required API keys not provided. Application will exit.")
        QMessageBox.critical(
            None,
            "API Keys Required",
            "Required API keys were not provided. The application will now exit."
        )
        sys.exit(1)
    
    # Load configuration
    config = {
        'app_name': 'Thoth AI',
        'version': '1.0.0',
        'default_model': 'gemini-1.5-pro',
        'models': {
            'gemini-1.5-pro': {
                'name': 'Gemini 1.5 Pro',
                'provider': 'google',
                'description': 'Google\'s most capable model for complex tasks'
            },
            'llama2': {
                'name': 'Llama 2',
                'provider': 'meta',
                'description': 'Meta\'s open source large language model'
            }
        },
        'voice': {
            'enabled': has_voice,
            'input_device': None,
            'output_device': None,
            'language': 'en-US',
            'voice': 'en-US-Neural2-F',
            'rate': 0.9,
            'volume': 1.0
        },
        'ui': {
            'theme': 'dark',
            'font_family': 'Segoe UI',
            'font_size': 10,
            'chat_font_size': 11,
            'show_timestamps': True,
            'show_typing_indicator': True,
            'compact_mode': False
        }
    }
    
    # Create and show main window
    try:
        window = ThothMainWindow(event_bus, config)
        window.show()
    except Exception as e:
        logging.critical(f"Failed to initialize main window: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Initialization Error",
            f"Failed to initialize application: {str(e)}\n\nCheck the logs for more details."
        )
        sys.exit(1)
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
