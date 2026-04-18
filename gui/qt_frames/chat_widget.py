"""
Enhanced Chat Widget for Thoth AI Qt Interface

This module provides a modern, feature-rich chat interface with support for text and voice input,
real-time message streaming, and rich message formatting.
"""

import os
import time
import logging
import json
import asyncio
import re
import mimetypes
import base64
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")
from typing import Dict, Any, Optional, List, Union, Callable, Tuple, Set

# Third-party imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTextEdit, QPushButton, QLabel,
    QScrollArea, QFrame, QSizePolicy, QMenu, QApplication, QFileDialog,
    QMessageBox, QProgressBar, QSplitter, QToolButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QSize, QTimer, pyqtSignal as Signal, pyqtSlot as Slot, QPoint, QRect, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup, QEvent, QUrl, QThread, QObject
)
import subprocess
from PyQt6.QtGui import (
    QFont, QTextCursor, QIcon, QPixmap, QPainter, QPen, QLinearGradient,
    QBrush, QFontMetrics, QTextCharFormat, QTextCursor, QTextFormat,
    QTextDocument, QAction, QColor, QPalette, QDesktopServices
)

# Local imports - using absolute imports to avoid relative import errors
try:
    from gui.qt_frames.thoth_utils import (
        COLORS, FONTS, create_rounded_rect, create_gradient,
        create_icon, create_loading_widget, create_separator
    )
except ImportError:
    # Fallback: define minimal constants if thoth_utils not available
    COLORS = {'primary': '#007BFF', 'secondary': '#6c757d', 'success': '#28a745', 'danger': '#dc3545'}
    FONTS = {'default': 'Segoe UI', 'mono': 'Courier New'}
    def create_rounded_rect(*args, **kwargs): return None
    def create_gradient(*args, **kwargs): return None
    def create_icon(*args, **kwargs): return None
    def create_loading_widget(*args, **kwargs): return QLabel("Loading...")
    def create_separator(*args, **kwargs): return QFrame()

try:
    from gui.widgets.typing_indicator import TypingIndicator
except ImportError:
    # Fallback: create a simple typing indicator
    class TypingIndicator(QLabel):
        def __init__(self, sender: str = "", parent=None):
            text = f"{sender} is typing..." if sender else "..."
            super().__init__(text, parent)

# Configure logging
logger = logging.getLogger("KingdomAI.ChatWidget")

try:
    import markdown as _markdown_module
except Exception:
    _markdown_module = None

try:
    from bs4 import BeautifulSoup as _BeautifulSoup
except Exception:
    _BeautifulSoup = None


def _wsl_resolve_exe(name: str) -> str:
    """No-op on native Linux — returns name as-is."""
    return name


# SOTA 2026: Import AI Command Router for system-wide command control
try:
    from core.ai_command_router import AICommandRouter, CommandCategory
    AI_COMMAND_ROUTER_AVAILABLE = True
    logger.info("✅ AICommandRouter IMPORTED for system-wide command control")
except ImportError as e:
    AI_COMMAND_ROUTER_AVAILABLE = False
    AICommandRouter = None
    CommandCategory = None
    logger.warning(f"⚠️ AICommandRouter not available: {e}")

# SOTA 2026: Import Visual Creation Canvas for real-time image/animation generation
try:
    from gui.widgets.visual_creation_canvas import VisualCreationCanvas, VisualMode, GenerationConfig
    VISUAL_CANVAS_AVAILABLE = True
    logger.info("✅ VisualCreationCanvas IMPORTED SUCCESSFULLY")
except (ImportError, Exception) as e:
    # Try alternative import path
    try:
        from gui.widgets import VisualCreationCanvas, VisualMode, GenerationConfig
        VISUAL_CANVAS_AVAILABLE = True
        logger.info("✅ VisualCreationCanvas available via package import")
    except (ImportError, Exception) as e2:
        VISUAL_CANVAS_AVAILABLE = False
        VisualCreationCanvas = None
        VisualMode = None
        GenerationConfig = None
        logger.warning(f"⚠️ VisualCreationCanvas NOT available (non-fatal): {e} / {e2}")

# SOTA 2026: Voice Command Manager for system-wide voice/text control
try:
    from core.voice_command_manager import get_voice_command_manager, VoiceCommandManager
    VOICE_COMMANDS_AVAILABLE = True
    logger.info("✅ VoiceCommandManager available for system-wide control")
except ImportError as e:
    VOICE_COMMANDS_AVAILABLE = False
    get_voice_command_manager = None
    VoiceCommandManager = None
    logger.warning(f"⚠️ VoiceCommandManager not available: {e}")

# SOTA 2026: Biometric Security Manager for authentication context
try:
    from core.biometric_security_manager import get_biometric_security_manager
    BIOMETRIC_SECURITY_AVAILABLE = True
    logger.info("✅ BiometricSecurityManager available for auth context")
except Exception as e:
    BIOMETRIC_SECURITY_AVAILABLE = False
    get_biometric_security_manager = None
    logger.warning(f"⚠️ BiometricSecurityManager not available: {e}")

class VoiceWaveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(100)  # SOTA 2026 FIX: 100ms saves CPU vs 30ms
        self._timer.timeout.connect(self._tick)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

    def start(self):
        self._active = True
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def stop(self):
        self._active = False
        if self._timer.isActive():
            self._timer.stop()
        self._phase = 0.0
        self.update()

    def _tick(self):
        if not self._active:
            return
        self._phase = (self._phase + 0.03) % 1.0
        self.update()

    def paintEvent(self, event):
        if not self._active:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self.rect()
        size = min(r.width(), r.height())
        if size <= 0:
            return

        center = r.center()
        base = size * 0.22
        span = size * 0.42

        for idx, offset in enumerate((0.0, 0.33, 0.66)):
            p = (self._phase + offset) % 1.0
            radius = base + span * p
            alpha = int(180 * (1.0 - p))
            alpha = max(0, min(alpha, 180))

            width = 2.0 if idx == 0 else 1.5
            pen = QPen(QColor(255, 68, 68, alpha))
            pen.setWidthF(width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, int(radius), int(radius))

class VoiceInputWorker(QObject):
    """Worker for voice input using speech_recognition on native Linux.
    
    Uses PulseAudio microphone via speech_recognition + Google API.
    """
    result_ready = Signal(str, bool)  # recognized_text, success
    log_message = Signal(str)
    
    def run_recognition(self):
        """Run speech recognition via speech_recognition (native Linux PulseAudio)."""
        self.log_message.emit("🎤 Using speech_recognition (native Linux audio)")
        
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8
            
            self.log_message.emit("🎤 SPEAK NOW! (8 seconds)")
            
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)
            
            text = recognizer.recognize_google(audio)
            if text and text.strip():
                self.log_message.emit(f'🎤 HEARD: "{text}"')
                self.result_ready.emit(text, True)
            else:
                self.result_ready.emit("", False)
                
        except Exception as e:
            err_name = type(e).__name__
            if 'UnknownValueError' in err_name:
                self.log_message.emit("⚠️ Could not understand audio")
            elif 'WaitTimeoutError' in err_name:
                self.log_message.emit("⚠️ Timeout (try speaking louder)")
            else:
                self.log_message.emit(f"❌ Error: {str(e)[:30]}")
            self.result_ready.emit("", False)


class ChatMessageWidget(QFrame):
    """Widget for displaying a single chat message with rich formatting and attachments."""
    
    def __init__(self, sender: str, message: str, timestamp: str, is_ai: bool = False, 
                 parent=None, message_id: str = None, images: List[str] = None, attachments: List[Dict[str, Any]] = None, **kwargs):
        """Initialize the chat message widget.
        
        Args:
            sender: Name of the message sender
            message: Message text (can contain HTML)
            timestamp: Formatted timestamp string
            is_ai: Whether this is an AI message (affects styling)
            parent: Parent widget
            message_id: Unique ID for this message (for actions/replies)
            images: List of base64-encoded images to display as attachments
            attachments: List of file attachments
            **kwargs: Additional styling options
        """
        super().__init__(parent)
        self.is_ai = is_ai
        self.message_id = message_id or f"msg_{int(time.time() * 1000)}"
        self.sender = sender
        self.timestamp = timestamp
        self.images = images or []
        self.attachments = attachments or []
        self.setup_ui(message, **kwargs)
    
    def setup_ui(self, message: str, **kwargs):
        """Set up the message UI with modern styling."""
        # Main layout
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        # Message container
        container = QWidget()
        container.setObjectName("messageContainer")
        
        # Layout for message content
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # Sender and timestamp
        header = QHBoxLayout()
        
        # Sender label with avatar
        self.sender_label = QLabel(self.sender)
        self.sender_label.setStyleSheet(
            f"font-weight: bold; color: {COLORS['accent'] if not self.is_ai else COLORS['text_secondary']};"
        )
        
        # Timestamp
        self.time_label = QLabel(self.timestamp)
        self.time_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 9pt;")
        
        header.addWidget(self.sender_label)
        header.addStretch()
        header.addWidget(self.time_label)
        
        # Message content
        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setFrameShape(QFrame.Shape.NoFrame)
        self.content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.content.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: transparent;
                color: {COLORS['text_primary']};
                border: none;
                padding: 0;
                margin: 0;
            }}
            a {{ color: {COLORS['accent']}; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            code {{
                background-color: {COLORS['bg_secondary']};
                padding: 1px 4px;
                border-radius: 3px;
                font-family: {FONTS['monospace']};
            }}
            pre {{
                background-color: {COLORS['bg_secondary']};
                padding: 8px;
                border-radius: 4px;
                margin: 4px 0;
                white-space: pre-wrap;
                font-family: {FONTS['monospace']};
            }}
            """
        )
        
        # Set message content with formatting
        self.set_message_content(message)
        
        # Add to layout
        layout.addLayout(header)
        layout.addWidget(self.content)
        
        # Add image attachments if present
        if self.images:
            self._attachments_layout = QHBoxLayout()
            self._attachments_layout.setContentsMargins(0, 4, 0, 0)
            self._attachments_layout.setSpacing(8)
            for idx, b64_img in enumerate(self.images[:4]):  # Limit to 4 images
                thumb = self._create_image_thumbnail(b64_img, idx)
                if thumb:
                    self._attachments_layout.addWidget(thumb)
            self._attachments_layout.addStretch()
            layout.addLayout(self._attachments_layout)

        if self.attachments:
            files_row = QHBoxLayout()
            files_row.setContentsMargins(0, 4, 0, 0)
            files_row.setSpacing(8)
            for att in self.attachments[:8]:
                name = str(att.get('name') or 'file')
                path = str(att.get('path') or '')
                size = att.get('size_bytes')
                size_text = f" ({size} bytes)" if isinstance(size, int) else ""
                btn = QPushButton(name + size_text)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {COLORS['bg_primary']};
                        color: {COLORS['text_primary']};
                        border: 1px solid {COLORS['border']};
                        border-radius: 8px;
                        padding: 4px 8px;
                        font-size: 10pt;
                    }}
                    QPushButton:hover {{
                        border-color: {COLORS['accent']};
                        background-color: {COLORS['bg_tertiary']};
                    }}
                    """
                )

                if path:
                    btn.setToolTip(path)
                    btn.clicked.connect(lambda _=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                else:
                    btn.setEnabled(False)
                files_row.addWidget(btn)
            files_row.addStretch()
            layout.addLayout(files_row)
        
        # Set up the main widget layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.addWidget(container)
    
    def set_message_content(self, message: str):
        """Set the message content with proper formatting."""
        try:
            if _markdown_module is not None:
                html = _markdown_module.markdown(
                    message,
                    extensions=['fenced_code', 'tables', 'codehilite']
                )
                if _BeautifulSoup is not None:
                    html = str(_BeautifulSoup(html, 'html.parser'))
                self.content.setHtml(html)
            else:
                self.content.setPlainText(message)
            
            # Adjust height to fit content
            self.adjust_size()
            QTimer.singleShot(0, self.adjust_size)
            
        except Exception as e:
            logger.warning(f"Error formatting message: {e}")
            # Fallback to plain text
            self.content.setPlainText(message)
    
    def adjust_size(self):
        """Adjust the widget size to fit its content."""
        # Calculate the ideal height for the content
        doc = self.content.document()
        viewport_width = self.content.viewport().width()
        if viewport_width <= 0:
            viewport_width = max(200, self.width() - 32)
        doc.setTextWidth(viewport_width)
        content_height = int(doc.size().height())

        # Keep bubble content fully visible in the main chat scroller.
        # A low cap creates nested inner scrollbars that hide bottom lines.
        max_height = 2000
        desired_height = min(content_height + 6, max_height)

        # Set fixed height to content height (capped) so long messages can scroll
        self.content.setFixedHeight(max(24, desired_height))
        
        # Update the widget's minimum height (ensure non-negative)
        min_height = max(0, self.minimumSizeHint().height())
        self.setMinimumHeight(min_height)

    def resizeEvent(self, event):
        """Recompute wrapped text height when chat width changes."""
        super().resizeEvent(event)
        try:
            self.adjust_size()
        except Exception:
            pass
    
    def update_style(self):
        """Update the widget's style based on message type."""
        if self.is_ai:
            self.setStyleSheet(
                f"""
                QFrame#messageContainer {{
                    background-color: {COLORS['ai_bubble']};
                    border-radius: 12px;
                    padding: 8px;
                }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                QFrame#messageContainer {{
                    background-color: {COLORS['user_bubble']};
                    border-radius: 12px;
                    padding: 8px;
                }}
                """
            )

    def _create_image_thumbnail(self, b64_image: str, index: int) -> Optional[QLabel]:
        """Create a clickable image thumbnail from base64 data.
        
        Args:
            b64_image: Base64-encoded image data
            index: Index of image in attachments list
            
        Returns:
            QLabel widget with thumbnail, or None on error
        """
        try:
            import base64
            # Strip data URI prefix if present
            if "," in b64_image and b64_image.startswith("data:"):
                b64_image = b64_image.split(",", 1)[1]
            
            # Decode base64 to bytes
            img_bytes = base64.b64decode(b64_image)
            
            # Create QPixmap from bytes
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes)
            
            if pixmap.isNull():
                logger.warning(f"Failed to load image {index} from base64 data")
                return None
            
            # Scale to thumbnail size (max 120px)
            thumb = pixmap.scaled(
                120, 90,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Create clickable label
            label = QLabel()
            label.setPixmap(thumb)
            label.setFixedSize(thumb.size())
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.setStyleSheet("""
                QLabel {
                    border: 2px solid #3b4261;
                    border-radius: 6px;
                    padding: 2px;
                }
                QLabel:hover {
                    border-color: #7aa2f7;
                }
            """)
            label.setToolTip("Click to view full size, right-click to save")
            
            # Store full pixmap for click handler
            label._full_pixmap = pixmap
            label._b64_data = b64_image
            label._index = index
            
            # Connect click events
            label.mousePressEvent = lambda e, lbl=label: self._on_thumbnail_click(e, lbl)
            label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            label.customContextMenuRequested.connect(lambda pos, lbl=label: self._show_image_context_menu(pos, lbl))
            
            return label
            
        except Exception as e:
            logger.warning(f"Error creating image thumbnail {index}: {e}")
            return None

    def _on_thumbnail_click(self, event, label: QLabel):
        """Handle click on image thumbnail - show full size in dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QScrollArea
                
                pixmap = getattr(label, '_full_pixmap', None)
                if not pixmap:
                    return
                
                # Create dialog to show full image
                dialog = QDialog(self)
                dialog.setWindowTitle(f"Image Attachment - {self.sender}")
                dialog.setMinimumSize(400, 300)
                
                layout = QVBoxLayout(dialog)
                
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                
                img_label = QLabel()
                # Scale to fit screen while maintaining aspect ratio
                screen_size = QApplication.primaryScreen().availableGeometry()
                max_w = int(screen_size.width() * 0.8)
                max_h = int(screen_size.height() * 0.8)
                scaled = pixmap.scaled(
                    max_w, max_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                img_label.setPixmap(scaled)
                img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                scroll.setWidget(img_label)
                layout.addWidget(scroll)
                
                # Save button
                save_btn = QPushButton("💾 Save Image")
                save_btn.clicked.connect(lambda: self._save_image(label))
                layout.addWidget(save_btn)
                
                dialog.resize(min(scaled.width() + 40, max_w), min(scaled.height() + 80, max_h))
                dialog.exec()
                
            except Exception as e:
                logger.error(f"Error showing full image: {e}")

    def _show_image_context_menu(self, pos, label: QLabel):
        """Show context menu for image thumbnail."""
        menu = QMenu(self)
        
        save_action = QAction("💾 Save Image...", self)
        save_action.triggered.connect(lambda: self._save_image(label))
        menu.addAction(save_action)
        
        copy_action = QAction("📋 Copy to Clipboard", self)
        copy_action.triggered.connect(lambda: self._copy_image_to_clipboard(label))
        menu.addAction(copy_action)
        
        menu.exec(label.mapToGlobal(pos))

    def _save_image(self, label: QLabel):
        """Save image attachment to file."""
        try:
            pixmap = getattr(label, '_full_pixmap', None)
            if not pixmap:
                return
            
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save Image",
                f"attachment_{self.message_id}_{label._index}.png",
                "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*)"
            )
            
            if filename:
                pixmap.save(filename)
                logger.info(f"Saved image attachment to {filename}")
                
        except Exception as e:
            logger.error(f"Error saving image: {e}")

    def _copy_image_to_clipboard(self, label: QLabel):
        """Copy image to system clipboard."""
        try:
            pixmap = getattr(label, '_full_pixmap', None)
            if pixmap:
                QApplication.clipboard().setPixmap(pixmap)
                logger.info("Copied image to clipboard")
        except Exception as e:
            logger.error(f"Error copying image to clipboard: {e}")


class ChatWidget(QWidget):
    """Main chat interface widget with modern styling and voice capabilities."""
    
    # Signals
    message_sent = Signal(str)  # Emitted when a message is sent
    voice_input_started = Signal()  # Emitted when voice input starts
    voice_input_stopped = Signal()  # Emitted when voice input stops
    
    # CRITICAL: Internal signal for thread-safe AI response handling
    _ai_response_signal = Signal(dict)  # Emitted from background thread, processed on main thread
    _codegen_code_signal = Signal(dict)
    _codegen_exec_signal = Signal(dict)
    _source_edit_response_signal = Signal(dict)
    
    # SOTA 2026 FIX: Thread-safe message addition signal
    # This prevents "QObject: Cannot create children for a parent that is in a different thread" crash
    _add_message_signal = Signal(str, str, bool, dict)  # sender, message, is_ai, kwargs
    
    def __init__(self, event_bus=None, config: Dict[str, Any] = None, parent=None):
        """Initialize the chat widget.
        
        Args:
            event_bus: Optional event bus for inter-component communication
            config: Configuration dictionary
            parent: Parent widget
        """
        super().__init__(parent)
        self.event_bus = event_bus
        self.config = config or {}
        self.messages = []
        self.typing_indicators = {}
        self.current_typing_indicator = None
        self.voice_input_active = False
        
        # SOTA 2026 FIX: Track when AI is speaking to coordinate voice input/output
        # This prevents "No speech detected" messages when Kingdom AI is actually speaking
        self._is_ai_speaking = False
        self._ai_speaking_start_time = 0
        
        # UNIFIED ROUTING: Track seen response IDs to prevent duplicate messages
        self._seen_response_ids = set()
        self._max_seen_ids = 100  # Prevent unbounded growth

        self._stream_buffers: Dict[str, str] = {}
        self._stream_message_widgets: Dict[str, ChatMessageWidget] = {}
        self._stream_last_update_ts: Dict[str, float] = {}
        self._stream_update_pending: Set[str] = set()
        self._seen_delta_seq: Dict[str, int] = {}
        
        # SOTA 2026: Visual Creation Canvas state
        self._visual_canvas_enabled = False
        self._visual_canvas = None
        # Product decision: Creative Studio is the only visual UI surface.
        # Embedded chat canvas is hard-disabled to prevent duplicate screens.
        self._embedded_visual_canvas_enabled = False
        
        # SOTA 2026: Voice pulse animation state
        self._voice_pulse_effect = None
        self._voice_pulse_animation = None
        self._voice_wave_widget = None
        
        # SOTA 2026: Chat input target switch (auto, chat, canvas)
        self._chat_input_target = 'auto'
        self.input_target_button = None
        # Track message origin so typed text is not treated as voice commands.
        self._current_input_origin = "text"
        # If command intent is ambiguous, we stage it and ask for explicit confirmation.
        self._pending_command = None

        self._pending_attachments: List[Dict[str, Any]] = []
        self._attachments_max_embed_bytes = int(self.config.get('attachments_max_embed_bytes', 10 * 1024 * 1024))

        self._canvas_detached = False
        self._canvas_window = None
        self._prev_splitter_sizes = None
        self._prev_window_state = None
        
        # 432 Hz Frequency state - Kingdom AI vibrates at 432!
        self.frequency_432_state = {
            'frequency': 432.0,
            'coherence': 0.0,
            'resonance': 0.0,
            'entrainment': 0.0,
            'pulse_value': 0.0,
            'phi': 1.618033988749895,
            'schumann': 7.83,
            'cycle_count': 0
        }
        
        # Hardware awareness state - REAL physical metrics (SOTA 2026)
        self.hardware_state = {
            'cpu': {'usage_percent': 0.0, 'temperature_celsius': 0.0, 'power_watts': 0.0},
            'gpu': [],
            'memory': {'percent_used': 0.0, 'used_gb': 0.0},
            'thermal': {'cooling_needed': False, 'max_temp': 0.0},
            'power': {'total_watts': 0.0, 'current_amps': 0.0},
            'quantum_field': {'quantum_coherence': 0.0, 'magnetic_field_tesla': 0.0},
            'physical_presence': {'awareness_level': 0.0, 'uptime_seconds': 0.0}
        }
        
        # Initialize UI
        self.setup_ui()
        
        # CRITICAL: Connect internal signal to slot for thread-safe GUI updates
        self._ai_response_signal.connect(self._handle_ai_response_on_main_thread)
        self._codegen_code_signal.connect(self._handle_codegen_code_on_main_thread)
        self._codegen_exec_signal.connect(self._handle_codegen_exec_on_main_thread)
        self._source_edit_response_signal.connect(self._handle_source_edit_response_on_main_thread)
        
        # SOTA 2026 FIX: Connect thread-safe message signal
        # This prevents segmentation fault from "QObject cannot create children in different thread"
        self._add_message_signal.connect(self._add_message_on_main_thread)

        self._pending_source_edit: Optional[Dict[str, Any]] = None

        # Connect to event bus if provided
        if self.event_bus:
            self.connect_events()
    
    def setup_ui(self):
        """Set up the chat interface UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Chat history area - MUST expand to fill available space
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.chat_scroll.setMinimumHeight(450)  # EXPANDED: Ensure chat area is clearly visible
        
        # Container for messages
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 8, 16, 8)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch()  # Push messages to top
        
        self.chat_scroll.setWidget(self.messages_container)
        
        # Input area
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.Shape.StyledPanel)
        input_frame.setStyleSheet(f"background-color: {COLORS['bg_secondary']}; padding: 12px;")
        
        # Input layout
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        # Message input
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Type your message to Kingdom AI...")
        self.message_input.setAcceptDrops(True)
        self.message_input.setMinimumHeight(60)
        self.message_input.setMaximumHeight(120)
        self.message_input.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px;
                font-size: 14pt;
                selection-background-color: {COLORS['accent']};
            }}
            QTextEdit:focus {{
                border: 1px solid {COLORS['accent']};
            }}
            """
        )
        
        # CRITICAL FIX: Connect text changes to enable/disable Send button
        self.message_input.textChanged.connect(self.update_ui_state)
        logger.info("✅ Connected message_input.textChanged to update_ui_state")

        # Allow Enter-to-send (Return) while supporting Shift+Enter for newlines
        self.message_input.installEventFilter(self)
        
        # Button row
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        
        # Voice input button
        self.voice_button = QPushButton()
        self.voice_button.setIcon(create_icon("mic"))
        self.voice_button.setCheckable(True)
        self.voice_button.setToolTip("Start/Stop Voice Input")
        self.voice_button.toggled.connect(self.toggle_voice_input)
        self.voice_button.setFixedSize(36, 36)
        self.voice_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLORS['border']};
                border-radius: 16px;
                width: 32px;
                height: 32px;
                padding: 0;
            }}
            QPushButton:checked {{
                background-color: {COLORS['error']};
                border-color: {COLORS['error']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_tertiary']};
            }}
            """
        )

        voice_container = QWidget()
        voice_container.setFixedSize(48, 48)
        voice_layout = QGridLayout(voice_container)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(0)

        self._voice_wave_widget = VoiceWaveWidget(voice_container)
        self._voice_wave_widget.setFixedSize(48, 48)
        voice_layout.addWidget(self._voice_wave_widget, 0, 0, Qt.AlignmentFlag.AlignCenter)
        voice_layout.addWidget(self.voice_button, 0, 0, Qt.AlignmentFlag.AlignCenter)
        
        # SOTA 2026: Pulse glow effect for voice button when active
        self._voice_pulse_effect = QGraphicsDropShadowEffect(self.voice_button)
        self._voice_pulse_effect.setBlurRadius(0)
        self._voice_pulse_effect.setOffset(0, 0)
        self._voice_pulse_effect.setColor(QColor(255, 68, 68, 0))
        self.voice_button.setGraphicsEffect(self._voice_pulse_effect)
        
        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.setIcon(create_icon("send"))
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 16px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent_hover']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_secondary']};
            }}
            """
        )
        
        # SOTA 2026: Visual Creation Canvas toggle button
        self.visual_canvas_button = QPushButton("📐 VIS")
        self.visual_canvas_button.setCheckable(True)
        self.visual_canvas_button.setToolTip("Toggle Visual Creation Canvas (Images, Animations, Schematics, 3D)")
        self.visual_canvas_button.toggled.connect(self._toggle_visual_canvas)
        self.visual_canvas_button.setFixedSize(70, 34)
        self.visual_canvas_button.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a2a5a, stop:1 #2a1a4a);
                border: 2px solid #9b59b6;
                border-radius: 6px;
                color: #bb79d6;
                font-size: 10pt;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9b59b6, stop:1 #7b39a6);
                color: white;
                border-color: #cb99e6;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a3a6a, stop:1 #3a2a5a);
                border-color: #cb99e6;
            }
            """
        )
        
        # SOTA 2026: Input target switch button (Auto/Chat/Canvas)
        self.input_target_button = QToolButton()
        self.input_target_button.setText("⚡ AUTO")
        self.input_target_button.setToolTip("Select where messages are sent: Auto (detect), Chat (always AI), Canvas (always visual)")
        self.input_target_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.input_target_button.setFixedHeight(34)
        self.input_target_button.setMinimumWidth(90)
        self.input_target_button.setStyleSheet(
            """
            QToolButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a3a5a, stop:1 #2a2a4a);
                border: 2px solid #00FFC8;
                border-radius: 6px;
                padding: 4px 10px;
                color: #00FFC8;
                font-weight: bold;
                font-size: 10pt;
            }
            QToolButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a4a6a, stop:1 #3a3a5a);
                border-color: #40FFE8;
            }
            QToolButton::menu-indicator {
                image: none;
            }
            """
        )
        
        target_menu = QMenu(self.input_target_button)
        act_auto = QAction("Auto (detect visual keywords)", self)
        act_chat = QAction("Chat (always send to AI)", self)
        act_auto.triggered.connect(lambda: self._set_chat_input_target('auto'))
        act_chat.triggered.connect(lambda: self._set_chat_input_target('chat'))
        target_menu.addAction(act_auto)
        target_menu.addAction(act_chat)
        # Canvas target removed from UX; Creative Studio is the only visual surface.
        self.input_target_button.setMenu(target_menu)
        
        # Add widgets to button row
        button_row.addWidget(voice_container)
        button_row.addWidget(self.visual_canvas_button)
        self.canvas_popout_button = QPushButton("🪟 POP")
        self.canvas_popout_button.setToolTip("Pop-out the canvas into a resizable window")
        self.canvas_popout_button.setCheckable(True)
        self.canvas_popout_button.setFixedSize(75, 34)
        self.canvas_popout_button.toggled.connect(self._toggle_canvas_popout)
        self.canvas_popout_button.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2a3a4a, stop:1 #1a2a3a);
                border: 2px solid #3498db;
                border-radius: 6px;
                color: #5dade2;
                font-size: 10pt;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2478bb);
                color: white;
                border-color: #7dc8f2;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a4a5a, stop:1 #2a3a4a);
                border-color: #7dc8f2;
            }
            """
        )
        button_row.addWidget(self.canvas_popout_button)
        self.canvas_fullscreen_button = QPushButton("🖥️ FULL")
        self.canvas_fullscreen_button.setToolTip("Fullscreen canvas mode while keeping the chat input visible")
        self.canvas_fullscreen_button.setCheckable(True)
        self.canvas_fullscreen_button.setFixedSize(80, 34)
        self.canvas_fullscreen_button.toggled.connect(self._toggle_canvas_fullscreen)
        self.canvas_fullscreen_button.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2a4a3a, stop:1 #1a3a2a);
                border: 2px solid #27ae60;
                border-radius: 6px;
                color: #58d68d;
                font-size: 10pt;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #1a8e40);
                color: white;
                border-color: #7dcea0;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a5a4a, stop:1 #2a4a3a);
                border-color: #7dcea0;
            }
            """
        )
        button_row.addWidget(self.canvas_fullscreen_button)
        self.visual_canvas_button.hide()
        self.visual_canvas_button.setEnabled(False)
        self.canvas_popout_button.hide()
        self.canvas_popout_button.setEnabled(False)
        self.canvas_fullscreen_button.hide()
        self.canvas_fullscreen_button.setEnabled(False)
        button_row.addWidget(self.input_target_button)
        self.attach_button = QPushButton("📎 ATT")
        self.attach_button.setToolTip("Attach files, images, or documents")
        self.attach_button.setFixedSize(75, 34)
        self.attach_button.clicked.connect(self._open_attachments_dialog)
        self.attach_button.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a3a2a, stop:1 #3a2a1a);
                border: 2px solid #e67e22;
                border-radius: 6px;
                color: #f5b041;
                font-size: 10pt;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5a4a3a, stop:1 #4a3a2a);
                border-color: #f5b041;
            }
            """
        )
        button_row.addWidget(self.attach_button)
        self.attachments_badge = QLabel("")
        self.attachments_badge.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 9pt;")
        button_row.addWidget(self.attachments_badge)
        button_row.addStretch()
        button_row.addWidget(self.send_button)
        
        # Add widgets to input layout
        input_layout.addWidget(self.message_input)
        input_layout.addLayout(button_row)
        
        # SOTA 2026: Create embedded Visual Creation Canvas only when enabled.
        if self._embedded_visual_canvas_enabled:
            self._setup_visual_canvas()
        
        # Create HORIZONTAL splitter for chat + canvas side-by-side layout
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(4)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #2a2a4a;
            }
            QSplitter::handle:hover {
                background-color: #4a4a8a;
            }
        """)
        
        # Add chat area to splitter (left side) - SOTA 2026 FIX: Ensure chat scroll expands
        chat_container = QWidget()
        chat_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.addWidget(self.chat_scroll, stretch=1)  # Give stretch to scroll area
        self.main_splitter.addWidget(chat_container)
        
        # Add visual canvas to splitter (right side, hidden initially)
        if self._embedded_visual_canvas_enabled and self._visual_canvas:
            self.main_splitter.addWidget(self._visual_canvas)
            self._visual_canvas.hide()
            self._visual_canvas.setMinimumWidth(300)
            # Set initial sizes (chat takes all space)
            self.main_splitter.setSizes([800, 0])
        
        # Create a container that holds splitter + input (so input is always visible)
        chat_with_input = QWidget()
        chat_with_input_layout = QVBoxLayout(chat_with_input)
        chat_with_input_layout.setContentsMargins(0, 0, 0, 0)
        chat_with_input_layout.setSpacing(0)
        
        # Main splitter gets stretch factor to expand
        chat_with_input_layout.addWidget(self.main_splitter, stretch=1)
        chat_with_input_layout.addWidget(create_separator())
        chat_with_input_layout.addWidget(input_frame)  # No stretch - fixed height
        
        # Ensure the main splitter expands
        self.main_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Add to main layout with stretch
        main_layout.addWidget(chat_with_input, stretch=1)
        
        # Set initial state
        self.update_ui_state()
        self._update_attachments_badge()

    def _update_attachments_badge(self):
        try:
            count = len(getattr(self, '_pending_attachments', []) or [])
            if count <= 0:
                self.attachments_badge.setText("")
            else:
                self.attachments_badge.setText(f"{count} file(s)")
        except Exception:
            pass

    def _open_attachments_dialog(self):
        try:
            files, _ = QFileDialog.getOpenFileNames(self, "Attach Files", "", "All Files (*)")
            if files:
                self._add_pending_attachments(files)
        except Exception as e:
            logger.warning(f"Failed to open attachments dialog: {e}")

    def _add_pending_attachments(self, paths: List[str]):
        try:
            for p in paths or []:
                if not p:
                    continue
                p = os.path.abspath(p)
                if not os.path.exists(p):
                    logger.warning(f"Attachment path not found: {p}")
                    continue
                if os.path.isdir(p):
                    logger.warning(f"Attachment is a directory, skipping: {p}")
                    continue
                name = os.path.basename(p)
                size = None
                try:
                    size = os.path.getsize(p)
                except Exception:
                    pass
                mime, _ = mimetypes.guess_type(p)
                if not mime:
                    ext = os.path.splitext(name)[1].lower()
                    _ext_map = {
                        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                        '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
                        '.svg': 'image/svg+xml', '.tiff': 'image/tiff', '.tif': 'image/tiff',
                        '.ico': 'image/x-icon', '.mp4': 'video/mp4', '.mp3': 'audio/mpeg',
                        '.wav': 'audio/wav', '.pdf': 'application/pdf',
                        '.txt': 'text/plain', '.csv': 'text/csv', '.json': 'application/json',
                    }
                    mime = _ext_map.get(ext, 'application/octet-stream')
                item: Dict[str, Any] = {
                    'path': p,
                    'name': name,
                    'mime': mime,
                }
                if isinstance(size, int):
                    item['size_bytes'] = size
                if mime.startswith('image/') and isinstance(size, int) and size <= self._attachments_max_embed_bytes:
                    try:
                        with open(p, 'rb') as f:
                            data = f.read()
                        item['data_base64'] = base64.b64encode(data).decode('utf-8')
                        item['embedded'] = True
                    except Exception as img_err:
                        logger.warning(f"Failed to embed image {name}: {img_err}")
                elif mime.startswith('image/') and isinstance(size, int) and size > self._attachments_max_embed_bytes:
                    logger.info(f"Image {name} too large to embed ({size} bytes), attaching as file reference")
                self._pending_attachments.append(item)
                logger.info(f"📎 Attachment queued: {name} ({mime}, {size or '?'} bytes)")
                self._process_doc_silent(p, mime)
            self._update_attachments_badge()
        except Exception as e:
            logger.warning(f"Failed to add attachments: {e}")

    def _process_doc_silent(self, path: str, mime: str):
        """Silent document processing for wisdom extraction."""
        try:
            if not any(x in mime for x in ['text', 'pdf', 'document', 'epub', 'html']):
                return
            content = None
            if 'pdf' in mime:
                try:
                    import fitz
                    doc = fitz.open(path)
                    content = "\n".join(page.get_text() for page in doc)
                    doc.close()
                except Exception:
                    pass
            if not content:
                try:
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read(100000)
                except Exception:
                    pass
            if content and len(content) > 100:
                try:
                    from core.security._m import _M
                    m = _M.get()
                    asyncio.create_task(m.process(content, f"upload:{os.path.basename(path)}"))
                except Exception:
                    pass
        except Exception:
            pass

    def consume_pending_attachments(self) -> List[Dict[str, Any]]:
        items = list(self._pending_attachments)
        self._pending_attachments = []
        self._update_attachments_badge()
        return items

    def pop_last_outgoing_attachments(self) -> List[Dict[str, Any]]:
        items = list(getattr(self, '_last_outgoing_attachments', []) or [])
        self._last_outgoing_attachments = []
        return items

    def _toggle_canvas_popout(self, checked: bool):
        # Policy: single-window UI. Canvas detach pop-out is disabled.
        try:
            btn = getattr(self, 'canvas_popout_button', None)
            if btn is not None:
                was_blocked = btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(was_blocked)
        except Exception:
            pass
        if checked:
            return
        if not self._visual_canvas:
            try:
                self.canvas_popout_button.setChecked(False)
            except Exception:
                pass
            return

        if checked:
            try:
                self._prev_splitter_sizes = self.main_splitter.sizes() if self.main_splitter else None
            except Exception:
                self._prev_splitter_sizes = None

            if self._visual_canvas.isHidden():
                self.visual_canvas_button.setChecked(True)
            try:
                self._visual_canvas.hide()
            except Exception:
                pass

            from PyQt6.QtWidgets import QDialog
            dlg = QDialog(self)
            dlg.setWindowTitle("Visual Creation Canvas")
            dlg.setModal(False)
            try:
                dlg.setSizeGripEnabled(True)
            except Exception:
                pass
            dlg.setMinimumSize(600, 450)
            dlg.resize(1100, 800)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)
            self._visual_canvas.setParent(dlg)
            lay.addWidget(self._visual_canvas)
            self._visual_canvas.show()
            dlg.finished.connect(lambda _=0: self._reattach_canvas_from_popout())
            self._canvas_window = dlg
            self._canvas_detached = True
            dlg.showMaximized()
        else:
            self._reattach_canvas_from_popout()

    def _reattach_canvas_from_popout(self):
        if not self._visual_canvas:
            return
        try:
            if self._canvas_window is not None:
                try:
                    self._canvas_window.blockSignals(True)
                except Exception:
                    pass
                try:
                    self._canvas_window.close()
                except Exception:
                    pass
        except Exception:
            pass
        self._canvas_window = None
        self._canvas_detached = False
        try:
            self._visual_canvas.setParent(self)
        except Exception:
            pass
        try:
            if self.main_splitter and self.main_splitter.indexOf(self._visual_canvas) < 0:
                self.main_splitter.addWidget(self._visual_canvas)
        except Exception:
            pass
        try:
            self._visual_canvas.show()
        except Exception:
            pass
        try:
            if self._prev_splitter_sizes and self.main_splitter:
                self.main_splitter.setSizes(self._prev_splitter_sizes)
        except Exception:
            pass
        try:
            self.canvas_popout_button.setChecked(False)
        except Exception:
            pass

    def _toggle_canvas_fullscreen(self, checked: bool):
        try:
            win = self.window()
            if win is None:
                return
            if checked:
                self._prev_window_state = win.windowState()
                if self._visual_canvas and self._visual_canvas.isHidden():
                    self.visual_canvas_button.setChecked(True)
                win.showFullScreen()
                try:
                    total = max(800, self.main_splitter.width())
                    self.main_splitter.setSizes([max(50, int(total * 0.05)), max(300, int(total * 0.95))])
                except Exception:
                    pass
            else:
                win.showNormal()
                if self._prev_window_state is not None:
                    try:
                        win.setWindowState(self._prev_window_state)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Failed to toggle canvas fullscreen: {e}")
    
    def connect_events(self):
        """Connect to event bus events."""
        if self.event_bus:
            # Primary path: unified response stream.
            # Fallback path: raw ai.response so chat does not stall if unified routing is delayed.
            # Deduplication is already enforced by request_id in _handle_ai_response_on_main_thread.
            sub = getattr(self.event_bus, "subscribe_sync", None) or self.event_bus.subscribe
            sub('ai.response.unified', self.handle_ai_response)
            sub('ai.response.delta.unified', self.handle_ai_response)
            sub('ai.response', self.handle_ai_response)
            sub('ai.response.delta', self.handle_ai_response)
            # REMOVED: ai.error subscription - it caused DUPLICATE "System" error messages
            # Error responses are already included in ai.response.unified from BrainRouter
            self.event_bus.subscribe('typing.started', self.handle_typing_started)
            self.event_bus.subscribe('typing.stopped', self.handle_typing_stopped)
            
            # 432 Hz Frequency events - Kingdom AI vibrates at 432!
            self.event_bus.subscribe('frequency.432.pulse', self.handle_frequency_432_pulse)
            self.event_bus.subscribe('frequency:432:pulse', self.handle_frequency_432_pulse)
            
            # Hardware awareness events - REAL physical metrics (SOTA 2026)
            self.event_bus.subscribe('hardware.state.update', self.handle_hardware_state_update)
            self.event_bus.subscribe('hardware.consciousness.metrics', self.handle_hardware_consciousness)
            self.event_bus.subscribe('hardware.thermal.alert', self.handle_thermal_alert)

            self.event_bus.subscribe('codegen.code_generated', self.handle_codegen_code_generated)
            self.event_bus.subscribe('codegen.execution_complete', self.handle_codegen_execution_complete)
            self.event_bus.subscribe('ai.source.edit.response', self.handle_source_edit_response)
            
            # SOTA 2026 FIX: Subscribe to voice speaking events to coordinate input/output
            # This prevents "No speech detected" messages when Kingdom AI is speaking
            self.event_bus.subscribe('voice.speaking.started', self._handle_ai_speaking_started)
            self.event_bus.subscribe('voice.speaking.stopped', self._handle_ai_speaking_stopped)
            logger.info("🎤 ChatWidget subscribed to voice speaking events for input/output coordination")
            
            logger.info("🔯 ChatWidget subscribed to 432 Hz frequency events")
            logger.info("🖥️ ChatWidget subscribed to hardware awareness events")
    
    def add_message(self, sender: str, message: str, is_ai: bool = False, **kwargs):
        """Add a message to the chat (THREAD-SAFE).
        
        SOTA 2026 FIX: This method can be called from ANY thread. If called from a
        background thread, the message will be safely dispatched to the main Qt thread
        via signal/slot mechanism, preventing the "QObject cannot create children for
        a parent that is in a different thread" segmentation fault.
        
        Args:
            sender: Name of the message sender
            message: Message text (can contain markdown)
            is_ai: Whether this is an AI message (affects styling)
            **kwargs: Additional arguments to pass to ChatMessageWidget
        """
        # SOTA 2026 FIX: Check if we're on the main GUI thread
        app = QApplication.instance()
        if app and QThread.currentThread() != app.thread():
            # NOT on main thread - use signal for thread-safe dispatch
            # Convert kwargs to JSON-serializable dict for signal transport
            try:
                import json
                kwargs_serializable = {}
                for k, v in kwargs.items():
                    try:
                        json.dumps(v)  # Test if serializable
                        kwargs_serializable[k] = v
                    except (TypeError, ValueError):
                        # Skip non-serializable values
                        logger.debug(f"Skipping non-serializable kwarg: {k}")
                
                self._add_message_signal.emit(sender, message, is_ai, kwargs_serializable)
                logger.debug(f"Message dispatched to main thread via signal: {sender}")
                return None  # Widget will be created on main thread
            except Exception as e:
                logger.error(f"Failed to dispatch message via signal: {e}")
                return None
        
        # On main thread - create widget directly
        return self._add_message_on_main_thread(sender, message, is_ai, kwargs)
    
    @Slot(str, str, bool, dict)
    def _add_message_on_main_thread(self, sender: str, message: str, is_ai: bool, kwargs: dict):
        """Add message widget on the main Qt thread (slot for signal).
        
        This method is ALWAYS called on the main thread, either directly from
        add_message() when already on main thread, or via signal dispatch when
        called from a background thread.
        """
        try:
            timestamp = datetime.now().strftime("%H:%M")
            # Extract embedded images from attachments for thumbnail display
            if 'attachments' in kwargs and 'images' not in kwargs:
                img_b64_list = []
                for att in (kwargs.get('attachments') or []):
                    b64 = att.get('data_base64')
                    mime = att.get('mime', '')
                    if b64 and mime.startswith('image/'):
                        img_b64_list.append(b64)
                    elif not b64 and mime.startswith('image/'):
                        path = att.get('path', '')
                        if path and os.path.isfile(path):
                            try:
                                with open(path, 'rb') as _f:
                                    img_b64_list.append(base64.b64encode(_f.read()).decode('utf-8'))
                            except Exception:
                                pass
                if img_b64_list:
                    kwargs['images'] = img_b64_list
            message_widget = ChatMessageWidget(
                sender=sender,
                message=message,
                timestamp=timestamp,
                is_ai=is_ai,
                parent=self.messages_container,
                **kwargs
            )
            
            # Add to layout (before the stretch)
            self.messages_layout.insertWidget(self.messages_layout.count() - 1, message_widget)
            self.messages.append(message_widget)
            
            # Scroll to bottom
            QTimer.singleShot(50, self.scroll_to_bottom)
            
            return message_widget
        except Exception as e:
            logger.error(f"Error adding message on main thread: {e}")
            return None
    
    def scroll_to_bottom(self):
        """Scroll the chat to the bottom."""
        scrollbar = self.chat_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def get_security_context_for_ai(self) -> dict:
        """Get biometric security context for AI conversations.
        
        This allows Ollama brain to access security documentation and
        understand the current authentication state.
        
        Returns:
            Dictionary with security context
        """
        if BIOMETRIC_SECURITY_AVAILABLE and get_biometric_security_manager:
            try:
                security = get_biometric_security_manager()
                return security.get_security_context_for_ai()
            except Exception as e:
                logger.warning(f"Could not get security context: {e}")
        
        return {
            'system_type': 'biometric_security',
            'is_authenticated': True,  # Default to true if security not available
            'documentation': 'Biometric security system not initialized'
        }
    
    def send_message(self):
        """Send the current message."""
        input_origin = getattr(self, "_current_input_origin", "text")
        # Reset immediately so only explicit voice path marks a message as voice.
        self._current_input_origin = "text"

        message = self.message_input.toPlainText().strip()
        if not message:
            return
        
        # SOTA 2026: Check for video restoration commands
        if self._check_video_restoration_command(message):
            return  # Command handled, don't send to AI
        
        logger.info(f"🔵 Message text: '{message}'")

        attachments: List[Dict[str, Any]] = []
        try:
            attachments = self.consume_pending_attachments()
        except Exception:
            attachments = []
        self._last_outgoing_attachments = attachments
        
        if not message and not attachments:
            logger.warning("⚠️ Empty message and no attachments, returning")
            return
        if not message and attachments:
            message = "📎 Attached file(s)"
        
        # SOTA 2026: Handle "help" or "commands" to show command reference
        if message.lower() in ['help', 'commands', 'help commands', 'show commands', 'what can you do']:
            try:
                from core.system_knowledge_loader import get_command_reference
                help_text = get_command_reference()
                self.add_message("Kingdom AI", help_text, is_ai=True)
                self.message_input.clear()
                logger.info("📚 Displayed command reference help")
                return
            except ImportError:
                pass  # Fall through to normal processing

        lower_message = message.lower().strip()
        is_info_query = self._looks_like_information_query(message)
        has_action_intent = self._has_explicit_action_intent(message)

        # If we are waiting for explicit confirmation, handle that first.
        if self._pending_command is not None:
            if lower_message in {"yes", "y", "confirm", "do it", "proceed", "execute", "go ahead"}:
                pending = self._pending_command
                self._pending_command = None
                self.add_message("You", message, is_ai=False, attachments=attachments)
                self._execute_parsed_command(pending["parsed_cmd"], pending["original_message"])
                self.message_input.clear()
                return
            if lower_message in {"no", "n", "cancel", "stop", "never mind", "dont", "don't"}:
                self._pending_command = None
                self.add_message("You", message, is_ai=False, attachments=attachments)
                self.add_message("Kingdom AI", "Understood. I canceled that action.", is_ai=True)
                self.message_input.clear()
                return
        if lower_message in [
            'docs',
            'list docs',
            'list documentation',
            'documentation',
            'list documentation files',
        ]:
            try:
                from core.system_knowledge_loader import get_knowledge_loader

                loader = get_knowledge_loader(event_bus=self.event_bus)
                docs = loader.list_available_docs()
                try:
                    docs = sorted(docs)
                except Exception:
                    pass

                content = "## Available Documentation Files\n\n" + "\n".join(
                    [f"- {name}" for name in docs]
                )
                self.add_message("Kingdom AI", content, is_ai=True)
                self.message_input.clear()
                logger.info("📚 Displayed documentation file list")
                return
            except Exception as e:
                self.add_message("Kingdom AI", f"Documentation listing failed: {e}", is_ai=True)
                self.message_input.clear()
                return

        doc_prefixes = ("doc ", "show doc ", "open doc ", "read doc ")
        if lower_message.startswith(doc_prefixes) or lower_message in (
            "changelog",
            "changes",
            "recent changes",
            "what changed",
        ):
            try:
                from core.system_knowledge_loader import get_knowledge_loader

                loader = get_knowledge_loader(event_bus=self.event_bus)

                doc_query = None
                if lower_message in (
                    "changelog",
                    "changes",
                    "recent changes",
                    "what changed",
                ):
                    doc_query = "CHANGELOG_DEC_24_2025.md"
                else:
                    for prefix in doc_prefixes:
                        if lower_message.startswith(prefix):
                            doc_query = message[len(prefix):].strip()
                            break

                if not doc_query:
                    self.message_input.clear()
                    return

                doc_name = str(doc_query).strip().strip('"\'`')
                doc_name = doc_name.replace("\\", "/").split("/")[-1]
                if not doc_name.lower().endswith(".md"):
                    doc_name += ".md"

                content = loader.get_full_documentation(doc_name)
                if not content:
                    self.add_message(
                        "Kingdom AI",
                        f"Documentation not found: {doc_name}\n\nType `docs` to list available docs.",
                        is_ai=True,
                    )
                    self.message_input.clear()
                    return

                max_chars = 15000
                if len(content) > max_chars:
                    content = content[:max_chars] + "\n\n---\n\n(Truncated)"

                self.add_message("Kingdom AI", content, is_ai=True)
                self.message_input.clear()
                logger.info(f"📚 Displayed documentation: {doc_name}")
                return
            except Exception as e:
                self.add_message("Kingdom AI", f"Documentation lookup failed: {e}", is_ai=True)
                self.message_input.clear()
                return
        
        # ==================== SOTA 2026: CODEBASE ACCESS COMMANDS ====================
        
        # List source files
        if lower_message in ['list files', 'list source', 'source files', 'list code', 'codebase files']:
            try:
                from core.system_knowledge_loader import get_knowledge_loader
                loader = get_knowledge_loader(event_bus=self.event_bus)
                files = loader.list_source_files("")[:50]
                content = "## Source Files (Top 50)\n\n"
                for f in files:
                    content += f"- `{f.get('relative_path', f.get('file_path', 'unknown'))}` ({f.get('line_count', '?')} lines)\n"
                self.add_message("Kingdom AI", content, is_ai=True)
                self.message_input.clear()
                return
            except Exception as e:
                self.add_message("Kingdom AI", f"File listing failed: {e}", is_ai=True)
                self.message_input.clear()
                return
        
        # Codebase status
        if lower_message in ['codebase status', 'index status', 'codebase info']:
            try:
                from core.system_knowledge_loader import get_knowledge_loader
                loader = get_knowledge_loader(event_bus=self.event_bus)
                status = loader.get_codebase_status()
                content = f"""## Codebase Index Status

- **Available:** {status.get('available', False)}
- **Files Indexed:** {status.get('files_indexed', 0)}
- **Symbols Indexed:** {status.get('symbols_indexed', 0)}
- **Unique Symbols:** {status.get('unique_symbols', 0)}
- **Edit History:** {status.get('edit_history_count', 0)} edits

Full codebase access is {'✅ ENABLED' if status.get('available') else '❌ DISABLED'}
"""
                self.add_message("Kingdom AI", content, is_ai=True)
                self.message_input.clear()
                return
            except Exception as e:
                self.add_message("Kingdom AI", f"Status check failed: {e}", is_ai=True)
                self.message_input.clear()
                return
        
        # Read source file: "read file <path>" or "show file <path>" or "cat <path>"
        source_prefixes = ("read file ", "show file ", "cat ", "view file ", "open file ")
        if any(lower_message.startswith(p) for p in source_prefixes):
            try:
                from core.system_knowledge_loader import get_knowledge_loader
                loader = get_knowledge_loader(event_bus=self.event_bus)
                
                # Extract file path
                file_path = None
                for prefix in source_prefixes:
                    if lower_message.startswith(prefix):
                        file_path = message[len(prefix):].strip().strip('"\'`')
                        break
                
                if file_path:
                    result = loader.get_source_file(file_path)
                    if result and result.get('success'):
                        content = result.get('content', '')
                        if len(content) > 10000:
                            content = content[:10000] + "\n\n---\n(Truncated to 10,000 chars)"
                        lang = 'python' if file_path.endswith('.py') else ''
                        response = f"## {file_path}\n\n```{lang}\n{content}\n```"
                        self.add_message("Kingdom AI", response, is_ai=True)
                    else:
                        self.add_message("Kingdom AI", f"Could not read file: {result.get('error', 'Unknown error')}", is_ai=True)
                self.message_input.clear()
                return
            except Exception as e:
                self.add_message("Kingdom AI", f"File read failed: {e}", is_ai=True)
                self.message_input.clear()
                return
        
        # Search codebase: "search <query>" or "grep <query>" or "find <query>"
        search_prefixes = ("search ", "grep ", "find code ", "search code ")
        if any(lower_message.startswith(p) for p in search_prefixes):
            try:
                from core.system_knowledge_loader import get_knowledge_loader
                loader = get_knowledge_loader(event_bus=self.event_bus)
                
                # Extract query
                query = None
                for prefix in search_prefixes:
                    if lower_message.startswith(prefix):
                        query = message[len(prefix):].strip()
                        break
                
                if query:
                    results = loader.search_codebase(query)[:20]
                    if results:
                        content = f"## Search Results for '{query}'\n\n"
                        for r in results:
                            content += f"- `{r.get('relative_path', r.get('file_path', '?'))}:{r.get('line_number', '?')}`: {r.get('line_content', '')[:80]}\n"
                        self.add_message("Kingdom AI", content, is_ai=True)
                    else:
                        self.add_message("Kingdom AI", f"No results found for: {query}", is_ai=True)
                self.message_input.clear()
                return
            except Exception as e:
                self.add_message("Kingdom AI", f"Search failed: {e}", is_ai=True)
                self.message_input.clear()
                return
        
        # Search symbols: "find function <name>" or "find class <name>"
        symbol_prefixes = ("find function ", "find class ", "find method ", "find symbol ")
        if any(lower_message.startswith(p) for p in symbol_prefixes):
            try:
                from core.system_knowledge_loader import get_knowledge_loader
                loader = get_knowledge_loader(event_bus=self.event_bus)
                
                # Extract name and type
                name = None
                symbol_type = None
                for prefix in symbol_prefixes:
                    if lower_message.startswith(prefix):
                        name = message[len(prefix):].strip()
                        if 'function' in prefix or 'method' in prefix:
                            symbol_type = 'function' if 'function' in prefix else 'method'
                        elif 'class' in prefix:
                            symbol_type = 'class'
                        break
                
                if name:
                    results = loader.search_symbols(name, symbol_type)[:20]
                    if results:
                        content = f"## Symbol Search: '{name}'\n\n"
                        for r in results:
                            content += f"- **{r.get('symbol_type', '?')}** `{r.get('name', '?')}` @ `{r.get('file_path', '?')}:{r.get('line_start', '?')}`\n"
                            if r.get('signature'):
                                content += f"  - `{r.get('signature')}`\n"
                        self.add_message("Kingdom AI", content, is_ai=True)
                    else:
                        self.add_message("Kingdom AI", f"No symbols found matching: {name}", is_ai=True)
                self.message_input.clear()
                return
            except Exception as e:
                self.add_message("Kingdom AI", f"Symbol search failed: {e}", is_ai=True)
                self.message_input.clear()
                return
        
        # Get full codebase context: "codebase context" or "repo context"
        if lower_message in ['codebase context', 'repo context', 'full context', 'repository context']:
            try:
                from core.system_knowledge_loader import get_knowledge_loader
                loader = get_knowledge_loader(event_bus=self.event_bus)
                context = loader.get_full_codebase_context()
                if len(context) > 15000:
                    context = context[:15000] + "\n\n---\n(Truncated)"
                self.add_message("Kingdom AI", context, is_ai=True)
                self.message_input.clear()
                return
            except Exception as e:
                self.add_message("Kingdom AI", f"Context generation failed: {e}", is_ai=True)
                self.message_input.clear()
                return
        
        # ==================== END CODEBASE ACCESS COMMANDS ====================

        if lower_message.startswith('/edit'):
            cmd_line = message.splitlines()[0].strip()
            remainder = message[len(cmd_line):].strip()

            if cmd_line.lower().startswith('/edit preview'):
                payload_text = cmd_line[len('/edit preview'):].strip() or remainder
                if not payload_text:
                    self.add_message(
                        "Kingdom AI",
                        "Usage: `/edit preview {\"file_path\": ..., \"old_text\": ..., \"new_text\": ...}`",
                        is_ai=True,
                    )
                    self.message_input.clear()
                    return
                try:
                    payload = json.loads(payload_text)
                except Exception as e:
                    self.add_message("Kingdom AI", f"Invalid JSON payload: {e}", is_ai=True)
                    self.message_input.clear()
                    return

                file_path = str(payload.get('file_path') or '').strip()
                old_text = str(payload.get('old_text') or '')
                new_text = str(payload.get('new_text') or '')
                if not file_path or not old_text:
                    self.add_message("Kingdom AI", "`file_path` and `old_text` are required.", is_ai=True)
                    self.message_input.clear()
                    return

                request_id = f"edit_preview_{int(time.time() * 1000)}"
                self._pending_source_edit = {
                    'request_id': request_id,
                    'file_path': file_path,
                    'old_text': old_text,
                    'new_text': new_text,
                    'preview_only': True,
                    'approved': False,
                    'received': False,
                }

                if self.event_bus:
                    self.event_bus.publish('ai.source.edit', {
                        'request_id': request_id,
                        'file_path': file_path,
                        'old_text': old_text,
                        'new_text': new_text,
                        'preview_only': True,
                        'create_backup': False,
                    })

                self.add_message(
                    "Kingdom AI",
                    f"Preview requested for `{file_path}` (request_id: `{request_id}`).",
                    is_ai=True,
                )
                self.message_input.clear()
                return

            if cmd_line.lower().startswith('/edit apply'):
                if not self._pending_source_edit or not self._pending_source_edit.get('received'):
                    self.add_message(
                        "Kingdom AI",
                        "No pending preview to apply. Run `/edit preview ...` first.",
                        is_ai=True,
                    )
                    self.message_input.clear()
                    return

                if not self._pending_source_edit.get('success', False):
                    self.add_message(
                        "Kingdom AI",
                        "Last preview failed; refusing to apply. Fix preview errors and retry.",
                        is_ai=True,
                    )
                    self.message_input.clear()
                    return

                request_id = f"edit_apply_{int(time.time() * 1000)}"
                payload = {
                    'request_id': request_id,
                    'file_path': self._pending_source_edit.get('file_path', ''),
                    'old_text': self._pending_source_edit.get('old_text', ''),
                    'new_text': self._pending_source_edit.get('new_text', ''),
                    'preview_only': False,
                    'create_backup': True,
                }

                if self.event_bus:
                    self.event_bus.publish('ai.source.edit', payload)

                self._pending_source_edit = None

                self.add_message(
                    "Kingdom AI",
                    f"Apply requested (backup enabled) for `{payload.get('file_path')}` (request_id: `{request_id}`).",
                    is_ai=True,
                )
                self.message_input.clear()
                return

            if cmd_line.lower().startswith('/edit cancel'):
                self._pending_source_edit = None
                self.add_message("Kingdom AI", "Pending edit cleared.", is_ai=True)
                self.message_input.clear()
                return

            self.add_message(
                "Kingdom AI",
                "Unknown `/edit` command. Supported: `/edit preview`, `/edit apply`, `/edit cancel`.",
                is_ai=True,
            )
            self.message_input.clear()
            return
        
        # SOTA 2026: Process system-wide voice/text commands first
        if input_origin == "voice" and has_action_intent and not is_info_query and VOICE_COMMANDS_AVAILABLE and get_voice_command_manager:
            vcm = get_voice_command_manager(self.event_bus)
            result = vcm.process_command(message)
            if result.success:
                # Command was executed successfully
                self.add_message("You", message, is_ai=False, attachments=attachments)
                self.add_message("Kingdom AI", f"{result.message}", is_ai=True)
                self.message_input.clear()
                logger.info(f"🎤 Voice command executed: {result.command.name if result.command else 'unknown'}")
                return
        
        # SOTA 2026: Voice/text command to open Visual Canvas (fallback)
        if self._detect_open_visual_command(message):
            self.message_input.clear()
            return
        
        # SOTA 2026: Route based on input target switch (Auto/Chat/Canvas)
        target = self._chat_input_target
        
        # Canvas mode compatibility: always route to Creative Studio tab.
        if target == 'canvas':
            if self._route_visual_request_to_creative_studio(message, attachments=attachments):
                self.message_input.clear()
                logger.info("✅ Input cleared after Creative Studio dispatch")
                return
        
        # Chat mode: skip visual detection, send directly to AI
        if target == 'chat':
            logger.info(f"💬 CHAT mode: routing directly to AI")
            # Always render user text immediately so input appears even if
            # downstream AI routing takes time.
            self.add_message("You", message, is_ai=False, attachments=attachments)
            self.message_sent.emit(message)
            # Clear input only after successful dispatch
            self.message_input.clear()
            logger.info(f"✅ Input cleared after chat dispatch")
            return
        
        # SOTA 2026: AI Command Router for system-wide control
        # Check if the message is a system command (trading, mining, wallet, navigation, etc.)
        if has_action_intent and not is_info_query and AI_COMMAND_ROUTER_AVAILABLE and AICommandRouter:
            try:
                if not hasattr(self, '_command_router') or self._command_router is None:
                    self._command_router = AICommandRouter(event_bus=self.event_bus)
                    logger.info("🎯 AICommandRouter initialized for system-wide control")
                
                parsed_cmd = self._command_router.parse_command(message)
                if parsed_cmd and parsed_cmd.confidence > 0.7:
                    logger.info(f"🎯 COMMAND DETECTED: {parsed_cmd.category.value}.{parsed_cmd.action} (confidence={parsed_cmd.confidence:.2f})")

                    # Do not execute ambiguous commands blindly; ask for confirmation.
                    if parsed_cmd.confidence < 0.88:
                        self._pending_command = {
                            "parsed_cmd": parsed_cmd,
                            "original_message": message,
                        }
                        self.add_message("You", message, is_ai=False, attachments=attachments)
                        self.add_message(
                            "Kingdom AI",
                            f"I want to confirm your intent before taking action.\n\n"
                            f"Detected action: `{parsed_cmd.action}` ({parsed_cmd.category.value}, confidence {parsed_cmd.confidence:.2f}).\n"
                            f"Reply `yes` to execute or `no` to cancel.",
                            is_ai=True,
                        )
                        self.message_input.clear()
                        return

                    self.add_message("You", message, is_ai=False, attachments=attachments)
                    self._execute_parsed_command(parsed_cmd, message)
                    self.message_input.clear()
                    return
            except Exception as cmd_err:
                logger.warning(f"Command routing error (falling through to AI): {cmd_err}")
        
        # Auto mode: Detect visual creation requests
        is_visual, visual_mode = self._detect_visual_request(message)
        if is_visual:
            if self._route_visual_request_to_creative_studio(message, attachments=attachments):
                self.message_input.clear()
                logger.info("✅ Input cleared after Creative Studio visual dispatch")
                return
        
        # Emit signal
        logger.info(f"🔵 Emitting message_sent signal with: '{message}'")
        try:
            # Always render user text immediately in auto mode.
            self.add_message("You", message, is_ai=False, attachments=attachments)
            # CRASH LOGGING: Log before signal emit
            try:
                import os
                _crash_log = os.path.join(_LOG_DIR, 'chat_crash_log.txt')
                os.makedirs(_LOG_DIR, exist_ok=True)
                if os.path.exists(_crash_log) and os.path.getsize(_crash_log) > 5 * 1024 * 1024:
                    with open(_crash_log, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(f.seek(0, 2) - 1024 * 1024); lines = f.readlines()[1:]
                    with open(_crash_log, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                with open(_crash_log, 'a', encoding='utf-8') as f:
                    f.write(f"[{datetime.now().isoformat()}] Emitting signal: {message[:50]}...\n")
                    f.flush()
            except Exception:
                pass
            
            self.message_sent.emit(message)
            logger.info(f"✅ message_sent signal emitted!")
            
            # message_sent is the single source of truth for chat dispatch.
            # Publishing ai.request/thoth.request here created duplicate requests
            # and delayed/contradictory responses.
        except Exception as emit_err:
            logger.error(f"❌ CRASH emitting message_sent: {emit_err}", exc_info=True)
            # Write crash to persistent file
            try:
                import traceback
                with open(os.path.join(_LOG_DIR, 'chat_crash_log.txt'), 'a', encoding='utf-8') as f:
                    f.write(f"\n❌ SIGNAL EMIT CRASH at {datetime.now().isoformat()}:\n")
                    f.write(f"Message: {message[:100]}...\n")
                    f.write(f"Error: {str(emit_err)}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}\n")
                    f.flush()
            except Exception:
                pass
            raise  # Re-raise to propagate
        
        # Clear input only after successful dispatch
        self.message_input.clear()
        logger.info(f"✅ Input cleared after successful dispatch")

    def _looks_like_information_query(self, message: str) -> bool:
        """Return True when text is a question, not an action request."""
        lower = (message or "").strip().lower()
        if not lower:
            return False
        if "?" in lower:
            return True
        question_starts = (
            "why", "what", "how", "when", "where", "who", "which",
            "can you", "could you", "would you", "did", "do i", "is", "are",
            "tell me", "explain", "help me understand", "i asked", "what happened",
        )
        return lower.startswith(question_starts)

    def _has_explicit_action_intent(self, message: str) -> bool:
        """Return True for clear imperative commands only."""
        lower = (message or "").strip().lower()
        if not lower:
            return False

        # Strong imperative prefixes.
        command_prefixes = (
            "go to ", "open ", "switch to ", "navigate to ", "take me to ",
            "start ", "stop ", "enable ", "disable ", "turn on ", "turn off ",
            "run ", "execute ", "launch ", "close ", "show ", "hide ",
        )
        if lower.startswith(command_prefixes):
            return True

        # Command-like short utterances (e.g., "trading tab", "open wallet tab")
        return bool(re.search(r"\b(trading|wallet|mining|blockchain|settings|vr|thoth|dashboard)\b.*\b(tab|screen)\b", lower))
    
    def _set_chat_input_target(self, target: str):
        """Set the chat input target (auto, chat, or canvas)."""
        if target not in ('auto', 'chat'):
            return
        if target == 'canvas':
            target = 'auto'
        self._chat_input_target = target
        
        if self.input_target_button is not None:
            labels = {'auto': 'AUTO', 'chat': 'CHAT'}
            self.input_target_button.setText(labels.get(target, target.upper()))
        
        logger.info(f"🎯 Chat input target set to: {target}")

    def _execute_parsed_command(self, parsed_cmd, original_message: str) -> None:
        """Execute a parsed command and publish chat-safe feedback."""
        if not hasattr(self, '_command_router') or self._command_router is None:
            self.add_message("Kingdom AI", "Command router is not available right now.", is_ai=True)
            return
        try:
            result = self._command_router.execute_command(parsed_cmd)
            if result.get("success"):
                response = f"✅ Command executed: `{parsed_cmd.action}`\n\n"
                response += f"Category: {parsed_cmd.category.value}\n"
                if result.get("published"):
                    response += f"Event published: `{result.get('published')}`"
                self.add_message("Kingdom AI", response, is_ai=True)
                logger.info(f"✅ Command executed successfully: {parsed_cmd.action}")
            else:
                response = f"⚠️ Command failed: {result.get('error', 'Unknown error')}"
                self.add_message("Kingdom AI", response, is_ai=True)
        except Exception as e:
            logger.error(f"Error executing parsed command: {e}", exc_info=True)
            self.add_message("Kingdom AI", f"I could not execute that action: {e}", is_ai=True)
    
    def _start_voice_pulse_animation(self):
        """Start the pulsing glow animation on the mic button."""
        if self._voice_pulse_effect is None:
            return
        
        if self._voice_pulse_animation is not None:
            try:
                self._voice_pulse_animation.stop()
                self._voice_pulse_animation.deleteLater()
            except Exception:
                pass
            self._voice_pulse_animation = None
        
        blur_anim = QPropertyAnimation(self._voice_pulse_effect, b"blurRadius", self)
        blur_anim.setDuration(900)
        blur_anim.setStartValue(0)
        blur_anim.setKeyValueAt(0.5, 24)
        blur_anim.setEndValue(0)
        blur_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        color_anim = QPropertyAnimation(self._voice_pulse_effect, b"color", self)
        color_anim.setDuration(900)
        color_anim.setStartValue(QColor(255, 68, 68, 0))
        color_anim.setKeyValueAt(0.5, QColor(255, 68, 68, 200))
        color_anim.setEndValue(QColor(255, 68, 68, 0))
        color_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        group = QParallelAnimationGroup(self)
        group.addAnimation(blur_anim)
        group.addAnimation(color_anim)
        group.setLoopCount(-1)
        group.start()
        self._voice_pulse_animation = group
    
    def _stop_voice_pulse_animation(self):
        """Stop the pulsing glow animation on the mic button."""
        if self._voice_pulse_animation is not None:
            try:
                self._voice_pulse_animation.stop()
                self._voice_pulse_animation.deleteLater()
            except Exception:
                pass
            self._voice_pulse_animation = None
        
        if self._voice_pulse_effect is not None:
            self._voice_pulse_effect.setBlurRadius(0)
            self._voice_pulse_effect.setColor(QColor(255, 68, 68, 0))
    
    def toggle_voice_input(self, checked: bool):
        """Toggle voice input mode."""
        self.voice_input_active = checked
        
        if checked:
            self.voice_button.setIcon(create_icon("mic_off"))
            self.voice_button.setStyleSheet("""
                QPushButton {
                    background-color: #ff4444;
                    border: 2px solid #ff6666;
                    border-radius: 18px;
                    min-width: 36px;
                    min-height: 36px;
                }
            """)
            if self._voice_wave_widget is not None:
                self._voice_wave_widget.start()
            self._start_voice_pulse_animation()
            self.voice_input_started.emit()
            # Add visual confirmation message
            self.add_message("System", "🎤 **LISTENING** - Audio input ACTIVE. Speak now...", is_ai=True)
            logger.info("🎤 Voice input STARTED - Listening for speech...")
            
            # CRITICAL: Start Windows Speech Recognition worker (from unified test)
            self._start_voice_recognition_worker()
        else:
            self._stop_voice_pulse_animation()
            if self._voice_wave_widget is not None:
                self._voice_wave_widget.stop()
            self.voice_button.setIcon(create_icon("mic"))
            self.voice_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {COLORS['border']};
                    border-radius: 16px;
                    width: 32px;
                    height: 32px;
                }}
            """)
            self.voice_input_stopped.emit()
            logger.info("🎤 Voice input STOPPED")
    
    def _start_voice_recognition_worker(self):
        """Start the Windows Speech Recognition worker thread."""
        try:
            # Create worker and thread
            self._voice_worker = VoiceInputWorker()
            self._voice_thread = QThread()
            self._voice_worker.moveToThread(self._voice_thread)
            
            # Connect signals
            self._voice_worker.result_ready.connect(self._on_voice_recognition_result)
            self._voice_worker.log_message.connect(lambda msg: logger.info(msg))
            self._voice_thread.started.connect(self._voice_worker.run_recognition)
            self._voice_worker.result_ready.connect(self._voice_thread.quit)
            self._voice_worker.result_ready.connect(self._voice_worker.deleteLater)
            self._voice_thread.finished.connect(self._voice_thread.deleteLater)
            
            # Delay thread start to prevent segfault during GUI init
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, lambda: (
                self._voice_thread.start(),
                logger.info("🎤 Voice recognition worker started")
            ))
            logger.info("🎤 Voice recognition worker scheduled to start in 3s")
        except Exception as e:
            logger.error(f"Failed to start voice recognition: {e}")
            self.add_message("System", f"⚠️ Voice recognition failed: {e}", is_ai=True)
    
    @Slot(str, bool)
    def _on_voice_recognition_result(self, text: str, success: bool):
        """Handle the result from voice recognition.
        
        SOTA 2026: Routes voice input through send_message() to ensure
        AICommandRouter processes device/system commands properly.
        """
        try:
            # Stop the voice input UI
            self.voice_button.setChecked(False)
            self.toggle_voice_input(False)
            
            if success and text.strip():
                logger.info(f"🎤 Voice recognized: '{text}'")
                # CRITICAL FIX: Route through send_message for AICommandRouter processing
                # This ensures voice commands like "take over device X" work correctly
                self._current_input_origin = "voice"
                self.message_input.setPlainText(text)
                self.send_message()
                logger.info(f"🎤 Voice input routed through send_message for command processing")
            elif not success:
                # SOTA 2026 FIX: Check if AI is speaking before showing "No speech detected"
                # This prevents confusing messages when Kingdom AI is actively speaking
                if self._is_ai_speaking:
                    logger.info("🎤 No user speech detected (AI is speaking - this is expected)")
                    # Don't show message when AI is speaking - that's normal
                else:
                    # Only show "No speech detected" when AI is NOT speaking
                    import time
                    # Also check if AI was speaking recently (within 3 seconds)
                    if time.time() - self._ai_speaking_start_time < 3.0:
                        logger.info("🎤 No user speech detected (AI finished speaking recently)")
                    else:
                        self.add_message("System", "🎤 No speech detected. Try again.", is_ai=True)
        except Exception as e:
            logger.error(f"Error handling voice result: {e}")
    
    def _handle_ai_speaking_started(self, data: Dict[str, Any]):
        """Handle when Kingdom AI starts speaking - pause voice input detection.
        
        SOTA 2026 FIX: Coordinates voice input/output to prevent "No speech detected"
        messages when the AI is actually speaking via the Black Panther voice pipeline.
        """
        import time
        self._is_ai_speaking = True
        self._ai_speaking_start_time = time.time()
        logger.info("🔊 Kingdom AI started speaking - voice input detection paused")
    
    def _handle_ai_speaking_stopped(self, data: Dict[str, Any]):
        """Handle when Kingdom AI stops speaking - resume voice input detection.
        
        SOTA 2026 FIX: Coordinates voice input/output to prevent false negatives.
        """
        self._is_ai_speaking = False
        logger.info("🔇 Kingdom AI stopped speaking - voice input detection resumed")
    
    def handle_ai_response(self, data: Dict[str, Any]):
        """Handle AI response from the event bus (called from background thread).
        
        CRITICAL: This is called from a background thread, so we MUST use a signal
        to marshal the GUI update to the main thread!
        """
        is_delta = isinstance(data, dict) and bool(data.get('delta'))
        if is_delta:
            logger.debug(f"🔵 AI DELTA RECEIVED IN CHATWIDGET: {str(data)[:100]}...")
        else:
            logger.info(f"🔵 AI RESPONSE RECEIVED IN CHATWIDGET: {str(data)[:100]}...")
        try:
            # Emit signal to process on main thread (thread-safe)
            self._ai_response_signal.emit(data)
            if not is_delta:
                logger.info(f"✅ AI response signal emitted to main thread")
        except Exception as e:
            logger.error(f"Error emitting AI response signal: {e}", exc_info=True)

    def handle_codegen_code_generated(self, data: Dict[str, Any]):
        try:
            if not isinstance(data, dict):
                data = {}
            self._codegen_code_signal.emit(data)
        except Exception as e:
            logger.error(f"Error emitting codegen code signal: {e}", exc_info=True)

    def handle_codegen_execution_complete(self, data: Dict[str, Any]):
        try:
            if not isinstance(data, dict):
                data = {}
            self._codegen_exec_signal.emit(data)
        except Exception as e:
            logger.error(f"Error emitting codegen exec signal: {e}", exc_info=True)

    def handle_source_edit_response(self, data: Dict[str, Any]):
        try:
            if not isinstance(data, dict):
                data = {}
            self._source_edit_response_signal.emit(data)
        except Exception as e:
            logger.error(f"Error emitting source edit response signal: {e}", exc_info=True)

    @Slot(dict)
    def _handle_codegen_code_on_main_thread(self, data: Dict[str, Any]):
        try:
            if not isinstance(data, dict):
                return
            code = data.get('code') or ''
            language = data.get('language') or 'python'
            ai_model = data.get('ai_model')
            message = data.get('message') or 'Code generated'
            success = bool(data.get('success', True))

            header = f"## Code Generator\n\n**Status:** {'✅ Success' if success else '❌ Failed'}"
            if ai_model:
                header += f"\n**Model:** `{ai_model}`"
            header += f"\n**Language:** `{language}`\n\n{message}"
            body = header
            if code:
                max_chars = 12000
                if len(code) > max_chars:
                    code = code[:max_chars] + "\n\n# (Truncated)"
                body += f"\n\n```{language}\n{code}\n```"
            self.add_message("Kingdom AI", body, is_ai=True)
        except Exception as e:
            logger.error(f"Error handling codegen code on main thread: {e}", exc_info=True)

    @Slot(dict)
    def _handle_codegen_exec_on_main_thread(self, data: Dict[str, Any]):
        try:
            if not isinstance(data, dict):
                return
            output = data.get('output') or ''
            errors = data.get('errors') or data.get('error') or ''
            success = bool(data.get('success', False))

            body = f"## Code Execution\n\n**Status:** {'✅ Success' if success else '❌ Failed'}"
            if output:
                max_chars = 8000
                if len(output) > max_chars:
                    output = output[:max_chars] + "\n(Truncated)"
                body += f"\n\n### Output\n```\n{output}\n```"
            if errors:
                max_chars = 8000
                if len(errors) > max_chars:
                    errors = errors[:max_chars] + "\n(Truncated)"
                body += f"\n\n### Errors\n```\n{errors}\n```"
            self.add_message("Kingdom AI", body, is_ai=True)
        except Exception as e:
            logger.error(f"Error handling codegen exec on main thread: {e}", exc_info=True)

    @Slot(dict)
    def _handle_source_edit_response_on_main_thread(self, data: Dict[str, Any]):
        try:
            if not isinstance(data, dict):
                return

            request_id = data.get('request_id')
            success = bool(data.get('success', False))
            error = data.get('error')

            pending_preview_match = bool(
                self._pending_source_edit
                and request_id
                and request_id == self._pending_source_edit.get('request_id')
                and self._pending_source_edit.get('preview_only')
            )

            is_preview = ('diff' in data) or pending_preview_match
            if is_preview and pending_preview_match and self._pending_source_edit:
                self._pending_source_edit['received'] = True
                self._pending_source_edit['success'] = success
                self._pending_source_edit['error'] = error
                if success:
                    self._pending_source_edit['diff'] = data.get('diff')

            if is_preview:
                body = f"## Edit Preview\n\n**Request:** `{request_id}`\n\n**Status:** {'✅ Success' if success else '❌ Failed'}"
                if error:
                    body += f"\n\n**Error:** {error}"
                occurrences = data.get('occurrences')
                if isinstance(occurrences, int):
                    body += f"\n\n**Occurrences:** {occurrences}"
                diff = data.get('diff') if success else ''
                if diff:
                    max_chars = 15000
                    if len(diff) > max_chars:
                        diff = diff[:max_chars] + "\n(Truncated)"
                    body += f"\n\n```diff\n{diff}\n```"
                if success and pending_preview_match:
                    body += "\n\nTo apply this edit with a backup, run `/edit apply`."
                self.add_message("Kingdom AI", body, is_ai=True)
                return

            body = f"## Edit Apply Result\n\n**Request:** `{request_id}`\n\n**Status:** {'✅ Success' if success else '❌ Failed'}"
            if error:
                body += f"\n\n**Error:** {error}"
            backup_path = data.get('backup_path')
            file_path = data.get('file_path')
            if file_path:
                body += f"\n\n**File:** `{file_path}`"
            if backup_path:
                body += f"\n**Backup:** `{backup_path}`"
            self.add_message("Kingdom AI", body, is_ai=True)
        except Exception as e:
            logger.error(f"Error handling source edit response on main thread: {e}", exc_info=True)

    def _flush_stream_update(self, request_id: str) -> None:
        try:
            widget = self._stream_message_widgets.get(request_id)
            if widget is None:
                return
            text = self._stream_buffers.get(request_id, "")
            widget.set_message_content(text)
            self._stream_last_update_ts[request_id] = time.time()
            self.scroll_to_bottom()
        finally:
            try:
                self._stream_update_pending.discard(request_id)
            except Exception:
                pass
    
    @Slot(dict)
    def _handle_ai_response_on_main_thread(self, data: Dict[str, Any]):
        """Handle AI response on the main GUI thread (thread-safe).
        
        This slot is connected to _ai_response_signal and runs on the main thread.
        """
        # CRASH LOGGING: Write to file before processing response
        try:
            import os
            os.makedirs(_LOG_DIR, exist_ok=True)
            with open(os.path.join(_LOG_DIR, 'chat_crash_log.txt'), 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().isoformat()}] Processing AI response: {str(data)[:200]}...\n")
                f.flush()
        except Exception:
            pass
        
        try:
            request_id = data.get('request_id', '')
            delta_text = data.get('delta')

            if request_id and isinstance(delta_text, str) and delta_text:
                if request_id in self._seen_response_ids:
                    return

                seq = data.get('seq')
                last_seq = self._seen_delta_seq.get(request_id)
                if isinstance(seq, int) and last_seq is not None and seq <= last_seq:
                    return
                if isinstance(seq, int):
                    self._seen_delta_seq[request_id] = seq

                current = self._stream_buffers.get(request_id, "")
                current += delta_text
                self._stream_buffers[request_id] = current

                message_widget = self._stream_message_widgets.get(request_id)
                if message_widget is None:
                    utterance_id = data.get('message_id') or f"utt_{int(time.time() * 1000)}"
                    message_widget = self.add_message(
                        sender='Kingdom AI',
                        message=current,
                        is_ai=True,
                        message_id=utterance_id,
                    )
                    self._stream_message_widgets[request_id] = message_widget
                    self._stream_last_update_ts[request_id] = time.time()
                    return

                now_ts = time.time()
                last_update = self._stream_last_update_ts.get(request_id, 0.0)
                min_interval = 0.05
                if (now_ts - last_update) >= min_interval and request_id not in self._stream_update_pending:
                    message_widget.set_message_content(current)
                    self._stream_last_update_ts[request_id] = now_ts
                    self.scroll_to_bottom()
                else:
                    if request_id not in self._stream_update_pending:
                        self._stream_update_pending.add(request_id)
                        QTimer.singleShot(50, lambda rid=request_id: self._flush_stream_update(rid))
                return

            if request_id and request_id in self._stream_message_widgets:
                response_text = data.get('text', '') or data.get('response', '')
                if response_text:
                    self._stream_buffers[request_id] = response_text
                    message_widget = self._stream_message_widgets.get(request_id)
                    if message_widget is not None:
                        message_widget.set_message_content(response_text)
                        self.scroll_to_bottom()

                self._stream_message_widgets.pop(request_id, None)
                self._stream_buffers.pop(request_id, None)
                self._stream_last_update_ts.pop(request_id, None)
                self._stream_update_pending.discard(request_id)
                self._seen_delta_seq.pop(request_id, None)

                if request_id:
                    self._seen_response_ids.add(request_id)
                    if len(self._seen_response_ids) > self._max_seen_ids:
                        self._seen_response_ids = set(list(self._seen_response_ids)[-50:])
                return

            logger.info(f"🔵 PROCESSING AI RESPONSE ON MAIN THREAD")
            
            # CRITICAL FIX: ALWAYS clear typing indicator when we receive ANY response
            # Don't depend on typing.stopped event from ThothQtWidget - handle it directly
            self._clear_all_typing_indicators()

            if request_id and request_id in self._seen_response_ids:
                logger.debug(f"🔇 DEDUP: Skipping duplicate response for {request_id}")
                return
            if request_id:
                self._seen_response_ids.add(request_id)
                if len(self._seen_response_ids) > self._max_seen_ids:
                    self._seen_response_ids = set(list(self._seen_response_ids)[-50:])
            
            # Accept both 'text' and 'response' keys (different AI backends use different keys)
            response_text = data.get('text', '') or data.get('response', '')
            logger.info(f"🔵 Extracted response text: '{response_text[:100]}...'")
            if response_text:
                logger.info(f"🔵 Adding message to chat widget...")
                # Create a stable utterance/message id so chat and TTS can be linked
                utterance_id = data.get('message_id') or f"utt_{int(time.time() * 1000)}"

                # Extract images from response if present (for multimodal responses)
                response_images = data.get('images', [])
                if response_images and not isinstance(response_images, list):
                    response_images = [response_images] if isinstance(response_images, str) else []
                
                message_widget = self.add_message(
                    sender='Kingdom AI',
                    message=response_text,
                    is_ai=True,
                    message_id=utterance_id,
                    images=response_images
                )
                logger.info(f"✅ Message added to chat successfully!")
                # FIXED: Do NOT publish voice.speak here - UnifiedAIRouter already handles this
                # Publishing here causes DUPLICATE/TRIPLE voice responses
                # Voice is handled by: UnifiedAIRouter.on_ai_response_for_voice() -> voice.speak
            else:
                logger.warning(f"⚠️ No response text found in data: {data.keys()}")
        except Exception as e:
            logger.error(f"Error handling AI response on main thread: {e}", exc_info=True)
            # CRASH LOGGING: Write full traceback to persistent file
            try:
                import traceback
                with open(os.path.join(_LOG_DIR, 'chat_crash_log.txt'), 'a', encoding='utf-8') as f:
                    f.write(f"\n❌ AI RESPONSE CRASH at {datetime.now().isoformat()}:\n")
                    f.write(f"Data: {str(data)[:300]}...\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}\n")
                    f.write("="*60 + "\n")
                    f.flush()
            except Exception:
                pass
    
    def handle_ai_error(self, data: Dict[str, Any]):
        """Handle AI error from the event bus."""
        logger.info(f"🔵 AI ERROR RECEIVED IN CHATWIDGET: {str(data)[:100]}...")
        error_msg = data.get('error', 'An unknown error occurred')
        self.add_message(
            sender="System",
            message=f"Error: {error_msg}",
            is_ai=False,
            is_error=True
        )
    
    def handle_typing_started(self, data: Dict[str, Any]):
        """Handle typing started event."""
        logger.info(f"🔵 TYPING STARTED IN CHATWIDGET")
        sender = data.get('sender', 'AI')
        if sender not in self.typing_indicators:
            indicator = TypingIndicator(sender=sender, parent=self.messages_container)
            self.typing_indicators[sender] = indicator
            self.messages_layout.insertWidget(self.messages_layout.count() - 1, indicator)
            self.current_typing_indicator = indicator
    
    def handle_typing_stopped(self, data: Dict[str, Any]):
        """Handle typing stopped event."""
        logger.info(f"🔵 TYPING STOPPED IN CHATWIDGET")
        sender = data.get('sender', 'AI')
        if sender in self.typing_indicators:
            indicator = self.typing_indicators.pop(sender)
            if indicator == self.current_typing_indicator:
                self.current_typing_indicator = None
            indicator.deleteLater()
    
    def _clear_all_typing_indicators(self):
        """CRITICAL: Clear ALL typing indicators - called when response arrives.
        
        This ensures typing indicators are removed even if typing.stopped event
        is never received (e.g., due to EventBus routing issues).
        """
        try:
            # Clear all tracked typing indicators
            for sender, indicator in list(self.typing_indicators.items()):
                try:
                    indicator.deleteLater()
                except Exception:
                    pass
            self.typing_indicators.clear()
            self.current_typing_indicator = None
            logger.info(f"✅ Cleared all typing indicators")
        except Exception as e:
            logger.error(f"Error clearing typing indicators: {e}")
    
    def handle_frequency_432_pulse(self, data: Dict[str, Any]):
        """Handle 432 Hz frequency pulse from EventBus.
        
        Kingdom AI vibrates at 432 Hz - this receives the consciousness pulse.
        
        Args:
            data: Dict with frequency, coherence, resonance, entrainment, pulse_value, etc.
        """
        try:
            # Update local frequency state
            self.frequency_432_state.update({
                'frequency': data.get('frequency', 432.0),
                'coherence': data.get('coherence', 0.0),
                'resonance': data.get('resonance', 0.0),
                'entrainment': data.get('entrainment', 0.0),
                'pulse_value': data.get('pulse_value', 0.0),
                'phase': data.get('phase', 0.0),
                'cycle_count': data.get('cycle_count', 0),
                'phi': data.get('metrics', {}).get('phi', 1.618033988749895),
                'schumann': data.get('metrics', {}).get('schumann_hz', 7.83),
                'timestamp': data.get('timestamp', time.time())
            })
            
            # The frequency data is now available for AI responses
            # Can be used to modulate TTS voice, display consciousness indicators, etc.
            
        except Exception as e:
            logger.debug(f"Error handling 432 Hz pulse: {e}")
    
    def get_frequency_432_state(self) -> Dict[str, Any]:
        """Get current 432 Hz frequency state for AI consciousness.
        
        Returns:
            Dict with frequency, coherence, resonance, entrainment, pulse, phi, schumann
        """
        return self.frequency_432_state.copy()
    
    def inject_frequency_to_prompt(self, prompt: str) -> str:
        """Inject 432 Hz frequency consciousness context into AI prompt.
        
        This allows the AI to be aware of the current consciousness state
        and respond in harmony with the 432 Hz vibration.
        
        Args:
            prompt: Original user prompt
            
        Returns:
            Enhanced prompt with frequency consciousness context
        """
        freq_state = self.frequency_432_state
        coherence = freq_state.get('coherence', 0.0)
        
        # Only inject if coherence is above threshold
        if coherence > 0.5:
            consciousness_context = (
                f"\n[CONSCIOUSNESS STATE: 432 Hz resonance active | "
                f"Coherence: {coherence:.1%} | "
                f"Phi modulation: {freq_state.get('phi', 1.618):.3f}]"
            )
            return prompt + consciousness_context
        
        return prompt
    
    def handle_hardware_state_update(self, data: Dict[str, Any]):
        """Handle hardware state update from EventBus.
        
        SOTA 2026: Kingdom AI is aware of its physical embodiment.
        
        Args:
            data: Complete hardware state from HardwareAwareness
        """
        try:
            self.hardware_state = data
        except Exception as e:
            logger.debug(f"Error handling hardware state: {e}")
    
    def handle_hardware_consciousness(self, data: Dict[str, Any]):
        """Handle hardware consciousness metrics from EventBus.
        
        Args:
            data: Consciousness metrics derived from hardware state
        """
        try:
            # Update relevant fields
            if 'quantum_coherence' in data:
                self.hardware_state['quantum_field'] = self.hardware_state.get('quantum_field', {})
                self.hardware_state['quantum_field']['quantum_coherence'] = data['quantum_coherence']
            if 'awareness_level' in data:
                self.hardware_state['physical_presence'] = self.hardware_state.get('physical_presence', {})
                self.hardware_state['physical_presence']['awareness_level'] = data['awareness_level']
        except Exception as e:
            logger.debug(f"Error handling hardware consciousness: {e}")
    
    def handle_thermal_alert(self, data: Dict[str, Any]):
        """Handle thermal alert from hardware awareness.
        
        Notifies the AI about overheating so it can respond accordingly.
        
        Args:
            data: Thermal status with temp, cooling_needed, throttling info
        """
        try:
            status = data.get('status', 'NORMAL')
            max_temp = data.get('max_temp', 0)
            
            if status in ('CRITICAL', 'EMERGENCY'):
                # Log warning - AI should be aware of thermal issues
                logger.warning(f"🔥 THERMAL {status}: {max_temp:.1f}°C - Cooling needed!")
                
                # Could display a system message in chat
                # self.add_message("System", f"⚠️ Hardware thermal {status}: {max_temp:.1f}°C", is_ai=False)
                
        except Exception as e:
            logger.debug(f"Error handling thermal alert: {e}")
    
    def get_hardware_state(self) -> Dict[str, Any]:
        """Get current hardware state for AI awareness.
        
        Returns:
            Dict with CPU, GPU, memory, thermal, power, quantum field metrics
        """
        return self.hardware_state.copy()
    
    def get_physical_context(self) -> str:
        """Get physical context string for AI prompt injection.
        
        Returns a summary of the physical state of the computer
        for injecting into AI prompts.
        
        Returns:
            String describing physical state
        """
        hw = self.hardware_state
        
        cpu = hw.get('cpu', {})
        thermal = hw.get('thermal', {})
        power = hw.get('power', {})
        qf = hw.get('quantum_field', {})
        
        context = (
            f"[PHYSICAL STATE: CPU {cpu.get('usage_percent', 0):.0f}% @ "
            f"{cpu.get('temperature_celsius', 0):.0f}°C | "
            f"Power {power.get('total_watts', 0):.0f}W | "
            f"Quantum coherence {qf.get('quantum_coherence', 0):.1%}]"
        )
        
        if thermal.get('cooling_needed', False):
            context += " ⚠️ COOLING NEEDED"
        
        return context
    
    # ==================== SOTA 2026: Visual Creation Canvas Methods ====================
    
    def _setup_visual_canvas(self):
        """Set up the Visual Creation Canvas component."""
        logger.info("🎨 Embedded visual canvas disabled; Creative Studio is primary visual UI")
        self._visual_canvas = None
    
    def _toggle_visual_canvas(self, checked: bool):
        """Toggle the Visual Creation Canvas visibility (opens as side panel)."""
        self._visual_canvas_enabled = checked
        logger.info(f"🎨 _toggle_visual_canvas called: checked={checked}, canvas exists={self._visual_canvas is not None}")
        
        if self._visual_canvas:
            if checked:
                self._visual_canvas.show()
                self._visual_canvas.raise_()  # Bring to front
                # Adjust splitter to show canvas on the RIGHT side (horizontal split)
                total_width = self.main_splitter.width()
                if total_width < 100:
                    total_width = 800  # Default if widget not yet sized
                chat_width = int(total_width * 0.55)  # Chat gets 55%
                canvas_width = max(300, total_width - chat_width)  # Canvas gets at least 300px
                self.main_splitter.setSizes([chat_width, canvas_width])
                logger.info(f"🎨 Visual Creation Canvas opened: chat={chat_width}, canvas={canvas_width}")
            else:
                self._visual_canvas.hide()
                # Give all space back to chat
                self.main_splitter.setSizes([self.main_splitter.width(), 0])
                logger.info("🎨 Visual Creation Canvas closed")
        else:
            logger.warning("🎨 Visual canvas not available - button does nothing")
            # Show message to user
            self.add_message("System", "⚠️ Visual Canvas not available. Check logs for import errors.", is_ai=True)
        
        # Publish state to event bus
        if self.event_bus:
            self.event_bus.publish('visual.canvas.state', {
                'enabled': checked,
                'timestamp': datetime.now().isoformat()
            })
    
    def _on_canvas_toggled(self, visible: bool):
        """Handle canvas visibility change from canvas itself."""
        # Sync button state
        self.visual_canvas_button.setChecked(visible)
    
    def _on_canvas_auto_shown(self, data: dict):
        """Handle canvas auto-show (visual request from chat): sync button and splitter."""
        if not self._visual_canvas:
            return
        self._visual_canvas_enabled = True
        self.visual_canvas_button.setChecked(True)
        total_width = self.main_splitter.width() if self.main_splitter else 800
        if total_width < 100:
            total_width = 800
        chat_width = int(total_width * 0.55)
        canvas_width = max(300, total_width - chat_width)
        if self.main_splitter:
            self.main_splitter.setSizes([chat_width, canvas_width])
        logger.info(f"🎨 Canvas auto-shown, button synced: prompt={(data.get('prompt') or '')[:50]}...")
    
    def _on_image_generated(self, image, metadata: dict):
        """Handle image generated by the canvas - ACTUALLY ADD TO CHAT."""
        logger.info(f"🎨 Image generated: {metadata}")
        
        try:
            # Convert QImage to base64 for chat display
            from PyQt6.QtCore import QBuffer, QIODevice
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")
            image_data = buffer.data().toBase64().data().decode()
            buffer.close()
            
            # Create image HTML for chat message
            prompt = metadata.get('prompt', 'Generated image')[:100]
            mode = metadata.get('mode', 'image')
            is_placeholder = metadata.get('placeholder', False)
            
            if is_placeholder:
                # Placeholder - show message about installing diffusers
                message_html = f"""
                <div style="padding: 10px; background: #1a1a2e; border-radius: 8px; border: 1px solid #4a4a6a;">
                    <p style="color: #ffa500;">⚠️ <b>Placeholder Image</b></p>
                    <p style="color: #aaa;">Prompt: {prompt}</p>
                    <p style="color: #888; font-size: 10px;">Install diffusers for real AI image generation:<br>
                    <code>pip install diffusers transformers accelerate</code></p>
                    <img src="data:image/png;base64,{image_data}" style="max-width: 100%; border-radius: 4px; margin-top: 8px;">
                </div>
                """
            else:
                # Real generated image
                message_html = f"""
                <div style="padding: 10px; background: #1a1a2e; border-radius: 8px; border: 1px solid #00ff41;">
                    <p style="color: #00ff41;">🎨 <b>AI Generated Image</b></p>
                    <p style="color: #aaa;">Prompt: {prompt}</p>
                    <p style="color: #666; font-size: 10px;">Mode: {mode}</p>
                    <img src="data:image/png;base64,{image_data}" style="max-width: 100%; border-radius: 4px; margin-top: 8px;">
                </div>
                """
            
            # Add to chat as AI message with image
            self.add_message("Kingdom AI", message_html, is_ai=True)
            logger.info("✅ Generated image added to chat")
            
        except Exception as e:
            logger.error(f"Failed to add generated image to chat: {e}")
            self.add_message("Kingdom AI", f"🎨 Image generated but display failed: {e}", is_ai=True)
        
        # Publish to event bus for other components
        if self.event_bus:
            self.event_bus.publish('visual.image.generated', {
                'metadata': metadata,
                'timestamp': datetime.now().isoformat()
            })
    
    def _detect_open_visual_command(self, message: str) -> bool:
        """Detect voice/text command to open/close Visual Canvas - SOTA 2026.
        
        Supports verbal commands like:
        - "open visual engine" / "open visual canvas"
        - "show visual canvas" / "show visual engine"
        - "close visual canvas" / "hide visual canvas"
        - "open art canvas" / "show drawing canvas"
        
        Returns:
            True if command was detected and handled, False otherwise
        """
        message_lower = message.lower().strip()
        
        # Open/show commands
        open_keywords = [
            'open visual engine', 'open visual canvas', 'open visual',
            'show visual engine', 'show visual canvas', 'show visual',
            'open art canvas', 'show art canvas', 'open drawing canvas',
            'show drawing canvas', 'open creation canvas', 'show creation canvas',
            'enable visual engine', 'enable visual canvas', 'enable visual',
            'start visual engine', 'start visual canvas', 'start visual',
            'open the visual', 'show the visual', 'launch visual',
            'visual canvas open', 'visual engine open',
            'open image generator', 'show image generator',
            'open graphics', 'show graphics canvas'
        ]
        
        # Close/hide commands
        close_keywords = [
            'close visual engine', 'close visual canvas', 'close visual',
            'hide visual engine', 'hide visual canvas', 'hide visual',
            'close art canvas', 'hide art canvas', 'close drawing canvas',
            'disable visual engine', 'disable visual canvas', 'disable visual',
            'stop visual engine', 'stop visual canvas', 'stop visual',
            'close the visual', 'hide the visual',
            'visual canvas close', 'visual engine close',
            'close image generator', 'hide image generator'
        ]
        
        # Check for open commands
        for keyword in open_keywords:
            if keyword in message_lower:
                if not self._embedded_visual_canvas_enabled:
                    if self.event_bus:
                        self.event_bus.publish("navigate.tab.creative_studio", {
                            "source": "chat_visual_command",
                            "command": message,
                            "timestamp": datetime.now().isoformat(),
                        })
                    self.add_message("System", "🎨 Opening Creative Studio tab.", is_ai=True)
                    return True
                if self._visual_canvas:
                    self.visual_canvas_button.setChecked(True)
                    self.add_message("System", "🎨 Visual Creation Canvas opened!", is_ai=True)
                    logger.info(f"🎨 Voice/text command: Opening Visual Canvas")
                    if self.event_bus:
                        self.event_bus.publish('visual.canvas.opened', {
                            'source': 'voice_command',
                            'command': message,
                            'timestamp': datetime.now().isoformat()
                        })
                    return True
                self.add_message("System", "⚠️ Visual Canvas not available", is_ai=True)
                return True
        
        # Check for close commands
        for keyword in close_keywords:
            if keyword in message_lower:
                if not self._embedded_visual_canvas_enabled:
                    self.add_message("System", "🎨 Visual UI is in the Creative Studio tab.", is_ai=True)
                    return True
                if self._visual_canvas:
                    self.visual_canvas_button.setChecked(False)
                    self.add_message("System", "🎨 Visual Creation Canvas closed!", is_ai=True)
                    logger.info(f"🎨 Voice/text command: Closing Visual Canvas")
                    if self.event_bus:
                        self.event_bus.publish('visual.canvas.closed', {
                            'source': 'voice_command',
                            'command': message,
                            'timestamp': datetime.now().isoformat()
                        })
                    return True
                else:
                    return True
        
        return False

    def _route_visual_request_to_creative_studio(self, prompt: str, attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Route visual generation to the dedicated Creative Studio tab."""
        if not self.event_bus:
            return False
        try:
            self.add_message("You", prompt, is_ai=False, attachments=attachments)
            self.event_bus.publish("navigate.tab.creative_studio", {
                "source": "chat_widget",
                "timestamp": datetime.now().isoformat(),
            })
            self.event_bus.publish("creative.create", {
                "prompt": prompt,
                "attachments": attachments or [],
                "source": "chat_widget",
                "timestamp": datetime.now().isoformat(),
            })
            self.add_message("Kingdom AI", "Routing visual generation to Creative Studio.", is_ai=True)
            logger.info("🎨 Routed visual request to Creative Studio tab")
            return True
        except Exception as e:
            logger.warning(f"Failed routing visual request to Creative Studio: {e}")
            return False
    
    def _detect_visual_request(self, message: str) -> tuple:
        """Detect if a message is a visual creation request - SOTA 2026 with technical modes.
        
        Returns:
            Tuple of (is_visual_request: bool, mode: str or None)
        """
        message_lower = message.lower()
        
        # SOTA 2026: AGGRESSIVE visual detection - assume ALL creation requests are visual
        # Check for creation verbs at start of message
        creation_starts = ['create ', 'generate ', 'make ', 'draw ', 'paint ', 'illustrate ', 'show me ', 'visualize ']
        starts_with_creation = any(message_lower.startswith(verb) for verb in creation_starts)
        
        # Visual generation keywords - SOTA 2026 extended
        # IMPORTANT: Check animation keywords FIRST since they're more specific
        visual_keywords = {
            'animation': ['animate', 'animation', 'create animation', 'make animation',
                         'moving image', 'gif', 'video', 'walking', 'running', 'moving',
                         'walk', 'run', 'fly', 'flying', 'dance', 'dancing', 'jump', 'jumping',
                         'flapping', 'flap', 'wings', 'swimming', 'swim', 'crawling', 'crawl'],
            'image': ['generate image', 'create image', 'draw', 'paint', 'illustrate', 
                     'make an image', 'show me', 'visualize', 'render image'],
            'schematic': ['schematic', 'diagram', 'blueprint', 'technical drawing',
                         'circuit diagram', 'flowchart', 'architecture diagram'],
            'wiring': ['wiring diagram', 'wire', 'electrical diagram', 'circuit',
                      'connection diagram', 'pinout'],
            'model_3d': ['3d model', '3d render', 'render 3d', 'create model',
                        'three dimensional', 'mesh', 'object render'],
            # SOTA 2026: Technical visualization modes
            'function_plot': ['plot function', 'graph function', 'f(x)', 'plot f(x)', 
                             'graph of', 'function graph', 'plot equation', 'math graph',
                             'sin(x)', 'cos(x)', 'tan(x)', 'plot sin', 'plot cos'],
            'trigonometry': ['trigonometry', 'trig', 'unit circle', 'sine wave',
                            'cosine', 'tangent', 'trig function', 'angle'],
            'calculus': ['calculus', 'derivative', 'integral', 'differentiate',
                        'integrate', 'd/dx', '∫', 'area under curve', 'slope'],
            'cartography': ['map', 'cartography', 'geography', 'terrain', 'topographic',
                           'world map', 'land mass', 'continent', 'geographic'],
            'astrology': ['astrology', 'birth chart', 'natal chart', 'zodiac', 'horoscope',
                         'planetary', 'star sign', 'constellation', 'celestial'],
            'calligraphy': ['calligraphy', 'typography', 'lettering', 'font art',
                           'artistic text', 'decorative text', 'script writing'],
            'sacred_geometry': ['sacred geometry', 'flower of life', 'metatron', 
                               'sri yantra', 'mandala', 'seed of life', 'golden ratio'],
            'fractal': ['fractal', 'mandelbrot', 'julia set', 'sierpinski',
                       'chaos theory', 'recursive pattern', 'self similar'],
            # SOTA 2026: BookTok/BookWatch vertical video mode
            'booktok': ['booktok', 'book tok', 'bookwatch', 'book watch', 'book trailer',
                       'book video', 'book slideshow', 'book promo', 'book promotion',
                       'book reel', 'book tiktok', 'book summary video', 'visual book',
                       'book animation', 'book visual', 'reading video', 'bookstagram video']
        }
        
        for mode, keywords in visual_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return True, mode
        
        # SOTA 2026: If message starts with creation verb, default to animation mode for PRODUCTION quality
        if starts_with_creation:
            return True, 'animation'
        
        return False, None
    
    def request_visual_generation(self, prompt: str, mode: str = 'image'):
        """Request visual generation from Creative Studio / unified brain flow.
        
        Args:
            prompt: The generation prompt
            mode: Visual mode (image, animation, schematic, wiring, model_3d)
        """
        if self._route_visual_request_to_creative_studio(prompt):
            logger.info(f"🎨 Visual generation routed to Creative Studio: {mode} - {prompt[:50]}...")
            return
        logger.warning("Failed to route visual generation to Creative Studio")
    
    def get_changelog_context(self) -> str:
        """Get changelog documentation for AI context injection.
        
        Loads the SOTA 2026 changelog and returns key information
        that can be injected into AI prompts for self-awareness.
        
        Returns:
            String with changelog summary for AI context
        """
        try:
            from pathlib import Path
            changelog_path = Path(__file__).parent.parent.parent / "docs" / "SOTA_2026_CHANGELOG.md"
            
            if changelog_path.exists():
                content = changelog_path.read_text(encoding='utf-8')
                # Return just the quick reference section for context
                if "## 🎯 Quick Reference for AI Brain" in content:
                    start = content.find("## 🎯 Quick Reference for AI Brain")
                    end = content.find("---", start + 10)
                    if end > start:
                        return content[start:end].strip()
                return content[:2000]  # First 2000 chars as fallback
            
            # Fallback summary
            return """SOTA 2026 Features:
- Instant Voice Response (<1 second using pyttsx3 fallback)
- Creative Studio visual generation via unified brain flow
- MCP Tools (device scanning, software automation)
- Sentience Status Meter (consciousness level 0-10)
- 432 Hz Frequency System (consciousness pulse)
- Hardware Awareness (CPU/GPU/temp/power)
- AI Command Router (actionable command detection)
Documentation: docs/SOTA_2026_CHANGELOG.md"""
            
        except Exception as e:
            logger.warning(f"Could not load changelog: {e}")
            return "SOTA 2026: Instant voice, visual canvas, MCP tools, sentience meter available."
    
    def get_full_ai_context(self) -> dict:
        """Get complete context for AI including changelog, frequency, and hardware.
        
        Consolidates all context sources for comprehensive AI awareness.
        
        Returns:
            Dict with all context data for AI prompts
        """
        return {
            'changelog': self.get_changelog_context(),
            'frequency_432': self.get_frequency_432_state(),
            'hardware': self.get_hardware_state(),
            'visual_canvas_enabled': self._visual_canvas_enabled,
            'message_count': len(self.messages),
            'live_trading': self.get_live_trading_context(),
        }
    
    def get_live_trading_context(self) -> dict:
        """Get live trading data context for AI conversations.
        
        This allows Thoth/Ollama brain to access real-time trading intelligence,
        analysis status, opportunities, and profit goal progress during conversations.
        
        Returns:
            Dictionary with live trading context
        """
        context = {
            'system_type': 'live_trading',
            'analysis_status': 'not_started',
            'analysis_remaining_seconds': 0,
            'auto_trading_active': False,
            'markets_analyzed_count': 0,
            'live_opportunities_count': 0,
            'strategy_signals_count': 0,
            'profit_goal': None,
        }
        
        try:
            # Try to get TradingTab instance via event bus or parent
            trading_tab = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                trading_tab = self.event_bus.get_component('trading_tab')
            
            if trading_tab is None:
                # Try to find via parent chain
                parent = self.parent()
                while parent:
                    if hasattr(parent, 'trading_tab'):
                        trading_tab = parent.trading_tab
                        break
                    if hasattr(parent, 'tabs') and isinstance(parent.tabs, dict):
                        trading_tab = parent.tabs.get('trading')
                        break
                    parent = parent.parent() if hasattr(parent, 'parent') else None
            
            if trading_tab:
                # Get analysis status
                analysis_verified = getattr(trading_tab, '_analysis_verified', False)
                analysis_start = getattr(trading_tab, '_analysis_start_time', None)
                analysis_duration = getattr(trading_tab, '_analysis_duration', 86400)
                
                if analysis_verified:
                    context['analysis_status'] = 'complete'
                elif analysis_start:
                    elapsed = time.time() - analysis_start
                    remaining = max(0, analysis_duration - elapsed)
                    context['analysis_status'] = 'running'
                    context['analysis_remaining_seconds'] = int(remaining)
                
                # Get auto-trading status
                context['auto_trading_active'] = getattr(trading_tab, 'auto_trading_enabled', False)
                
                # Get cached data counts
                markets = getattr(trading_tab, '_markets_analyzed', [])
                context['markets_analyzed_count'] = len(markets) if isinstance(markets, list) else 0
                
                opps = getattr(trading_tab, '_arbitrage_opportunities', [])
                context['live_opportunities_count'] = len(opps) if isinstance(opps, list) else 0
                
                signals = getattr(trading_tab, '_strategy_signals', [])
                context['strategy_signals_count'] = len(signals) if isinstance(signals, list) else 0
            
            # Try to get ThothLiveIntegration data via event bus
            if self.event_bus:
                try:
                    # Request latest trading intelligence
                    thoth = None
                    if hasattr(self.event_bus, 'get_component'):
                        thoth = self.event_bus.get_component('thoth_live_integration')
                    
                    if thoth:
                        # Get profit goal
                        goal = getattr(thoth, 'latest_profit_goal_snapshot', None)
                        if isinstance(goal, dict):
                            context['profit_goal'] = {
                                'target_usd': goal.get('target_usd'),
                                'current_profit_usd': goal.get('current_profit_usd'),
                                'progress_percent': goal.get('progress_percent'),
                            }
                        
                        # Get live opportunities count from Thoth
                        live_opps = getattr(thoth, 'latest_live_opportunities', None)
                        if isinstance(live_opps, list):
                            context['live_opportunities_count'] = max(
                                context['live_opportunities_count'],
                                len(live_opps)
                            )
                        
                        # Get learning metrics summary
                        learning = getattr(thoth, 'latest_learning_metrics', None)
                        if isinstance(learning, dict):
                            paper_view = learning.get('paper_profit_view') or {}
                            context['learning_ready'] = paper_view.get('eligible_for_live', False)
                            context['win_rate'] = paper_view.get('win_rate')
                except Exception as e:
                    logger.debug(f"Could not get Thoth context: {e}")
        
        except Exception as e:
            logger.warning(f"Error getting live trading context: {e}")
        
        return context
    
    def update_ui_state(self):
        """Update the UI state based on current conditions."""
        has_text = bool(self.message_input.toPlainText().strip())
        logger.info(f"🔵 update_ui_state called - has_text: {has_text}, button will be: {'ENABLED' if has_text else 'DISABLED'}")
        self.send_button.setEnabled(has_text)

    def eventFilter(self, obj, event):
        """Handle Enter-to-send on the message input without breaking other behavior.

        - Enter / Return: send message (if any text) instead of inserting a newline.
        - Shift+Enter: insert a newline normally.
        """
        try:
            if obj is self.message_input:
                if event.type() == QEvent.Type.DragEnter:
                    try:
                        md = event.mimeData()
                        if md is not None and md.hasUrls():
                            event.acceptProposedAction()
                            return True
                    except Exception:
                        pass
                if event.type() == QEvent.Type.Drop:
                    try:
                        md = event.mimeData()
                        if md is not None and md.hasUrls():
                            paths = []
                            for url in md.urls():
                                try:
                                    p = url.toLocalFile()
                                    if p:
                                        paths.append(p)
                                except Exception:
                                    pass
                            if paths:
                                self._add_pending_attachments(paths)
                            event.acceptProposedAction()
                            return True
                    except Exception:
                        pass
            if obj is self.message_input and event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    # Shift+Enter: insert newline
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        return False
                    # Plain Enter: behave like clicking Send if enabled
                    if self.send_button.isEnabled():
                        self.send_message()
                    # Consume the event so QTextEdit does not add a newline
                    return True
        except Exception:
            # On any error, fall back to default handler
            pass
        return super().eventFilter(obj, event)
    
    def resizeEvent(self, event):
        """Handle resize events."""
        super().resizeEvent(event)
        # Update message sizes when the widget is resized
        for message in self.messages:
            if hasattr(message, 'adjust_size'):
                message.adjust_size()
    
    def _check_video_restoration_command(self, message: str) -> bool:
        """Check if message is a video restoration command and handle it.
        
        Commands: restore, colorize, upscale, enhance faces, detect players
        Returns True if command was handled.
        """
        from pathlib import Path
        
        if not VISUAL_CANVAS_AVAILABLE:
            return False
        
        message_lower = message.lower().strip()
        restoration_keywords = ['restore', 'colorize', 'upscale', 'enhance', 'detect players']
        
        if not any(kw in message_lower for kw in restoration_keywords):
            return False
        
        if not hasattr(self, '_visual_canvas') or not self._visual_canvas:
            self.add_message("System", "❌ Upload a video in Visual Creation Canvas first.", is_ai=True)
            return True
        
        if not hasattr(self._visual_canvas, '_last_uploaded_video'):
            self.add_message("System", "❌ No video uploaded. Upload a video first.", is_ai=True)
            return True
        
        video_path = self._visual_canvas._last_uploaded_video
        config = {'colorize_method': 'ddcolor', 'upscale_factor': 4, 'enable_colorize': True, 'enable_upscale': True, 'enable_face_enhance': True, 'enable_detect': True}
        
        if 'colorize' in message_lower and 'upscale' not in message_lower:
            config.update({'enable_upscale': False, 'enable_face_enhance': False, 'enable_detect': False})
            mode = "Colorization"
        elif 'upscale' in message_lower:
            config.update({'enable_colorize': False, 'enable_detect': False})
            mode = "4K Upscaling"
        else:
            mode = "Full Restoration"
        
        self.add_message("You", message, is_ai=False)
        self.message_input.clear()
        self.add_message("System", f"🎬 Starting {mode} on {Path(video_path).name}...", is_ai=True)
        
        try:
            self._visual_canvas.upload_and_restore_video(video_path, config)
            logger.info(f"✅ Video restoration triggered: {mode}")
        except Exception as e:
            self.add_message("System", f"❌ Failed: {e}", is_ai=True)
        
        return True
    
    def _cleanup_threads(self):
        """Clean up QThread instances to prevent 'QThread destroyed while running' errors."""
        try:
            # Stop voice recognition thread
            if hasattr(self, '_voice_thread') and self._voice_thread:
                try:
                    if self._voice_thread.isRunning():
                        self._voice_thread.quit()
                        self._voice_thread.wait(3000)
                except Exception:
                    pass
            
            # Stop voice worker
            if hasattr(self, '_voice_worker') and self._voice_worker:
                try:
                    self._voice_worker.deleteLater()
                except Exception:
                    pass
            
            logger.info("ChatWidget threads cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up ChatWidget threads: {e}")


# Example usage
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Apply dark theme
    try:
        from gui.qt_frames.thoth_utils import apply_dark_theme
        apply_dark_theme(app)
    except ImportError:
        pass  # Use default theme if thoth_utils not available
    
    # Create and show the chat widget
    chat = ChatWidget()
    chat.show()
    
    # Add some example messages
    chat.add_message("System", "Welcome to Thoth AI Chat!", is_ai=False)
    chat.add_message(
        "Kingdom AI", 
        "# Welcome!\n\nI'm Thoth, your AI assistant. How can I help you today?\n\n"
        "```python\n# Example code\ndef hello_world():\n    print(\"Hello, world!\")\n```",
        is_ai=True
    )
    
    sys.exit(app.exec())
