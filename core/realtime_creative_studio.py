"""
SOTA 2026 Real-Time Creative Studio
====================================
Complete integration of:
- Chat widget with Ollama brain control
- Live image/map creation and editing
- Webcam feed integration
- All creation engines (animation, cinema, map generation)
- Real-time video compositing
"""

import logging
import os
import threading
import time
import numpy as np
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("KingdomAI.RealtimeCreativeStudio")


def _unity_autolaunch_enabled() -> bool:
    """Gate Unity Hub auto-launch.  WSL2 can launch Windows .exe via interop."""
    if os.environ.get("KINGDOM_DISABLE_UNITY_AUTOLAUNCH", "0") == "1":
        return False
    return True

# PyQt6 imports - use TYPE_CHECKING for type hints while providing runtime stubs
HAS_PYQT6 = False
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QTextEdit, QSplitter, QFrame,
        QComboBox, QSlider, QProgressBar, QGroupBox, QScrollArea, QSizePolicy, QStackedWidget
    )
    from PyQt6.QtGui import QPixmap, QImage, QFont, QPainter, QColor, QPen, QMovie
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QDateTime, QUrl
    HAS_PYQT6 = True
except ImportError:
    logger.warning("PyQt6 not available - GUI features disabled")
    
    # Provide comprehensive stub classes for headless testing / type checking
    class _StubSignal:
        """Stub for PyQt signals."""
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, fn): pass
    
    class _StubWidget:
        """Stub base widget with common methods."""
        def __init__(self, *args, **kwargs): pass
        def setLayout(self, *args): pass
        def setStyleSheet(self, *args): pass
        def setMinimumSize(self, *args): pass
        def setMaximumSize(self, *args): pass
        def setMinimumHeight(self, *args): pass
        def setMaximumHeight(self, *args): pass
        def setMinimumWidth(self, *args): pass
        def setMaximumWidth(self, *args): pass
        def setWindowTitle(self, *args): pass
        def setObjectName(self, *args): pass
        def setAlignment(self, *args): pass
        def setText(self, *args): pass
        def text(self): return ""
        def clear(self): pass
        def show(self): pass
        def hide(self): pass
        def close(self): pass
        def setVisible(self, *args): pass
        def isVisible(self): return False
        def size(self): return _StubSize()
        def setPixmap(self, *args): pass
        def setMovie(self, *args): pass
        def pixmap(self): return None
        def setEnabled(self, *args): pass
        def isEnabled(self): return True
        def setToolTip(self, *args): pass
        def update(self): pass
        def repaint(self): pass
    
    class _StubLayout:
        """Stub for layout classes."""
        def __init__(self, *args, **kwargs): pass
        def addWidget(self, *args): pass
        def addLayout(self, *args): pass
        def addStretch(self, *args): pass
        def setSpacing(self, *args): pass
        def setContentsMargins(self, *args): pass
        def setAlignment(self, *args): pass
    
    class _StubSize:
        """Stub for QSize."""
        def __init__(self, *args): pass
        def width(self): return 0
        def height(self): return 0
    
    class QThread(_StubWidget):
        def start(self): pass
        def stop(self): pass
        def wait(self, *args): pass
        def isRunning(self): return False
        def quit(self): pass
    
    class QMainWindow(_StubWidget):
        def setCentralWidget(self, *args): pass
        def centralWidget(self): return None
        def menuBar(self): return None
        def statusBar(self): return None
    
    class QWidget(_StubWidget):
        pass
    
    class QVBoxLayout(_StubLayout):
        pass
    
    class QHBoxLayout(_StubLayout):
        pass
    
    class QLabel(_StubWidget):
        pass
    
    class QPushButton(_StubWidget):
        clicked = _StubSignal()
        def setCheckable(self, *args): pass
        def isChecked(self): return False
    
    class QLineEdit(_StubWidget):
        returnPressed = _StubSignal()
        def setPlaceholderText(self, *args): pass
        def setReadOnly(self, *args): pass
    
    class QTextEdit(_StubWidget):
        def setReadOnly(self, *args): pass
        def append(self, *args): pass
        def toPlainText(self): return ""
    
    class QSplitter(_StubWidget):
        pass
    
    class QFrame(_StubWidget):
        pass
    
    class QComboBox(_StubWidget):
        def addItems(self, *args): pass
        def currentText(self): return ""
        def currentIndex(self): return 0
        def setCurrentIndex(self, *args): pass
    
    class QSlider(_StubWidget):
        def setRange(self, *args): pass
        def setValue(self, *args): pass
        def value(self): return 0
    
    class QProgressBar(_StubWidget):
        def setValue(self, *args): pass
        def value(self): return 0
    
    class QGroupBox(_StubWidget):
        pass
    
    class QScrollArea(_StubWidget):
        pass

    class QStackedWidget(_StubWidget):
        def addWidget(self, *args): pass
        def setCurrentWidget(self, *args): pass
    
    class QSizePolicy:
        class Policy:
            Expanding = 0
            Fixed = 1
            Minimum = 2
            Maximum = 3
            Preferred = 4
    
    class QPixmap:
        def __init__(self, *args): pass
        def isNull(self): return True
        def width(self): return 0
        def height(self): return 0
        def scaled(self, *args, **kwargs): return self
        def save(self, *args): return False
        @staticmethod
        def fromImage(*args): return QPixmap()
    
    class QImage:
        class Format:
            Format_RGB888 = 0
        def __init__(self, *args): pass
    
    class QFont:
        def __init__(self, *args): pass
    
    class QPainter:
        def __init__(self, *args): pass
    
    class QColor:
        def __init__(self, *args): pass
    
    class QPen:
        def __init__(self, *args): pass
    
    class QSize(_StubSize):
        pass
    
    class Qt:
        class Orientation:
            Horizontal = 0
            Vertical = 1
        class AlignmentFlag:
            AlignCenter = 0
            AlignLeft = 1
            AlignRight = 2
        class AspectRatioMode:
            KeepAspectRatio = 0
        class TransformationMode:
            SmoothTransformation = 0
        Horizontal = 0
        Vertical = 1
        AlignCenter = 0
    
    class pyqtSignal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, fn): pass
    
    class QTimer:
        def __init__(self, *args): pass
        @property
        def timeout(self): return _StubSignal()
        def start(self, ms=0): pass
        def stop(self): pass
        def isActive(self): return False

    class QUrl:
        @staticmethod
        def fromLocalFile(path): return path

HAS_QT_MEDIA = False
QMediaPlayer = None
QAudioOutput = None
QVideoWidget = None
if HAS_PYQT6:
    try:
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        HAS_QT_MEDIA = True
    except Exception as e:
        logger.warning(f"Qt multimedia unavailable - video playback fallback active: {e}")

# OpenCV for webcam
try:
    import cv2
    HAS_OPENCV = True
except (ImportError, AttributeError) as e:
    HAS_OPENCV = False
    if 'ARRAY_API' in str(e):
        logger.warning(f"OpenCV not available - NumPy incompatibility: {e}")
    else:
        logger.warning("OpenCV not available - webcam features disabled")


class MJPEGReader:
    """Background thread that reads MJPEG frames into shared buffer.
    
    EXACT COPY from test_webcam_live_wsl2_v3.py - PROVEN WORKING.
    """
    
    def __init__(self, url: str):
        self.url = url
        self.latest_frame = None
        self.frame_count = 0
        self.is_running = False
        self.lock = threading.Lock()
        self.thread = None
        self.first_frame_ready = threading.Event()
    
    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.is_running = False
    
    def get_frame(self):
        """Get latest frame (thread-safe)."""
        with self.lock:
            return self.latest_frame, self.frame_count
    
    def wait_for_first_frame(self, timeout=3.0):
        return self.first_frame_ready.wait(timeout)
    
    def _read_loop(self):
        """Read MJPEG stream - OPTIMIZED for zero latency."""
        import requests
        import subprocess
        
        logger.info(f"📹 MJPEGReader connecting to {self.url}...")
        
        try:
            response = requests.get(self.url, stream=True, timeout=5)
            if response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}")
                return
            
            logger.info("✅ MJPEG Connected!")
            
            bytes_buffer = b''
            for chunk in response.iter_content(chunk_size=8192):
                if not self.is_running:
                    break
                
                bytes_buffer += chunk
                
                while True:
                    start = bytes_buffer.find(b'\xff\xd8')
                    if start == -1:
                        bytes_buffer = bytes_buffer[-2:] if len(bytes_buffer) > 2 else bytes_buffer
                        break
                    
                    end = bytes_buffer.find(b'\xff\xd9', start)
                    if end == -1:
                        break
                    
                    jpg_data = bytes_buffer[start:end+2]
                    bytes_buffer = bytes_buffer[end+2:]
                    
                    frame = cv2.imdecode(np.frombuffer(jpg_data, np.uint8), cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        frame = cv2.flip(frame, 1)  # Mirror
                        
                        with self.lock:
                            self.latest_frame = frame
                            self.frame_count += 1
                        
                        if not self.first_frame_ready.is_set():
                            self.first_frame_ready.set()
                            logger.info(f"🎬 First frame ready! Shape: {frame.shape}")
            
            response.close()
        except Exception as e:
            logger.error(f"❌ MJPEG stream error: {e}")


def _is_wsl_runtime() -> bool:
    """Check if running inside WSL."""
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
            pv = f.read().lower()
            return "microsoft" in pv or "wsl" in pv
    except Exception:
        return False

def _get_windows_host_ip() -> str:
    """Get Windows host IP for MJPEG webcam in WSL2. Returns localhost on native Linux."""
    if not _is_wsl_runtime():
        return "127.0.0.1"
    import subprocess
    try:
        result = subprocess.run(['ip', 'route', 'show', 'default'],
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            parts = result.stdout.split()
            if len(parts) >= 3 and parts[0] == 'default' and parts[1] == 'via':
                return parts[2]
    except Exception:
        pass
    try:
        with open('/etc/resolv.conf', 'r') as rf:
            for line in rf:
                if line.strip().startswith('nameserver'):
                    ip = line.strip().split()[1]
                    if not ip.startswith('127.'):
                        return ip
    except Exception:
        pass
    return "172.20.0.1"


class WebcamThread(QThread):  # type: ignore[misc]
    """MJPEG webcam capture using QTimer polling pattern.
    
    EXACT LOGIC from test_webcam_live_wsl2_v3.py - PROVEN WORKING at 120 FPS.
    """
    frame_ready = pyqtSignal(np.ndarray)
    status_update = pyqtSignal(str)
    
    def __init__(self, camera_id: int = 0, event_bus=None):
        super().__init__()
        self._running = False
        self._camera_id = camera_id
        self._reader = None
        
        # Build MJPEG URL
        host_ip = _get_windows_host_ip()
        self._mjpeg_url = f"http://{host_ip}:8090/brio.mjpg"
        logger.info(f"📹 MJPEG URL: {self._mjpeg_url}")
    
    def run(self):
        """Start MJPEG reader and emit frames."""
        self._running = True
        self.status_update.emit(f"📹 Connecting to {self._mjpeg_url}...")
        
        # Start MJPEG reader
        self._reader = MJPEGReader(self._mjpeg_url)
        self._reader.start()
        
        # Wait for first frame
        if self._reader.wait_for_first_frame(timeout=5.0):
            self.status_update.emit("✅ MJPEG Connected - Live!")
        else:
            self.status_update.emit("⚠️ Waiting for frames...")
        
        # Emit frames at ~30 FPS
        last_count = 0
        while self._running:
            frame, count = self._reader.get_frame()
            if frame is not None and count != last_count:
                last_count = count
                # Convert BGR to RGB for Qt
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frame_ready.emit(frame_rgb)
            time.sleep(0.033)  # ~30 FPS
    
    def stop(self):
        """Stop webcam capture."""
        self._running = False
        if self._reader:
            self._reader.stop()
        self.wait(2000)


class WebcamThreadDirect(QThread):  # type: ignore[misc]
    """Direct OpenCV webcam capture (fallback for non-WSL)."""
    frame_ready = pyqtSignal(np.ndarray)
    status_update = pyqtSignal(str)
    
    def __init__(self, camera_id: int = 0):
        super().__init__()
        self._running = False
        self._camera_id = camera_id
    
    def run(self):
        """Direct OpenCV webcam capture."""
        self.status_update.emit(f"Opening camera {self._camera_id}...")
        cap = cv2.VideoCapture(self._camera_id)
        
        if not cap.isOpened():
            self.status_update.emit("Failed to open camera")
            return
        
        self.status_update.emit("Camera opened!")
        while self._running:
            ret, frame = cap.read()
            if ret:
                self.frame_ready.emit(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            time.sleep(0.033)  # ~30 FPS
        
        cap.release()
    
    def stop(self):
        self._running = False
        self.wait(2000)


class OllamaWorker(QThread):  # type: ignore[misc]
    """Thread for Ollama AI responses."""
    response_ready = pyqtSignal(str)
    
    def __init__(self, prompt: str, model: str = ""):
        super().__init__()
        self.prompt = prompt
        self.model = model
    
    def run(self):
        try:
            import requests
            if not self.model:
                try:
                    from core.ollama_gateway import orchestrator
                    self.model = orchestrator.get_model_for_task("creative_studio")
                except ImportError:
                    self.model = "cogito:latest"
            try:
                from core.ollama_gateway import get_ollama_url
                base = get_ollama_url()
            except ImportError:
                try:
                    from core.ollama_config import get_ollama_base_url
                    base = get_ollama_base_url().rstrip("/")
                except Exception:
                    base = "http://localhost:11434"
            response = requests.post(
                f"{base}/api/generate",
                json={
                    "model": self.model,
                    "prompt": self.prompt,
                    "stream": False,
                    "keep_alive": -1,
                    "options": {"num_gpu": 999},
                },
                timeout=300
            )
            if response.status_code == 200:
                text = response.json().get("response", "")
                self.response_ready.emit(text)
            else:
                self.response_ready.emit(f"Error: {response.status_code}")
        except Exception as e:
            self.response_ready.emit(f"Error: {e}")


class RealtimeCreativeStudio(QMainWindow):  # type: ignore[misc]
    """
    SOTA 2026 Real-Time Creative Studio
    
    Features:
    - Live webcam feed with overlay
    - Chat interface with Ollama brain
    - Real-time map/image creation
    - Live editing with AI control
    - Video recording and compositing
    - Memory/learning integration for improved generation
    """
    
    def __init__(self, event_bus=None):
        super().__init__()
        self.event_bus = event_bus
        
        # State
        self._webcam_thread = None
        self._webcam_frame = None
        self._current_creation = None
        self._creation_history = []
        self._ollama_connected = False
        self._recording = False
        self._recorded_frames = []
        
        # Engines - use existing codebase architecture
        self._unified_engine = None
        self._animation_engine = None
        self._cinema_engine = None
        self._meta_learning = None
        self._ai_visual_engine = None  # SOTA 2026 AI image generation
        self._unity_runtime_bridge = None
        self._unity_hub_manager = None
        self._unity_mcp_tools = None
        
        # SOTA 2026 FIX: Initialize pending request tracking and timeout
        # This fixes "Waiting for Kingdom AI Brain to process..." staying stuck forever
        self._pending_visual_requests = {}
        self._visual_request_timeout = 120  # Longer default for heavy generation paths
        self._active_visual_request_id: Optional[str] = None
        self._last_completed_visual_request_id: Optional[str] = None
        
        # Initialize UI
        self._setup_ui()
        self._connect_engines()
        self._connect_meta_learning()
        self._check_ollama()
        self._load_creation_memory()
        
        # Start update timer
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_display)
        self._update_timer.start(33)  # 30 FPS
        
        logger.info("🎨 RealtimeCreativeStudio initialized")
    
    def _setup_ui(self):
        """Setup the complete UI."""
        self.setWindowTitle("🎨 Kingdom AI - Real-Time Creative Studio (SOTA 2026)")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet("""
            QMainWindow { background-color: #0a0a1a; }
            QWidget { color: white; }
            QGroupBox { 
                border: 2px solid #333; 
                border-radius: 8px; 
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title { 
                subcontrol-origin: margin;
                left: 10px;
                color: #00ff88;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1a3a, stop:1 #2a2a5a);
                border: 2px solid #444;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { border-color: #00ff88; }
            QPushButton:pressed { background: #00ff88; color: black; }
            QLineEdit, QTextEdit {
                background: #1a1a2e;
                border: 2px solid #333;
                border-radius: 4px;
                padding: 6px;
                color: white;
            }
            QComboBox {
                background: #1a1a2e;
                border: 2px solid #333;
                border-radius: 4px;
                padding: 6px;
                color: white;
            }
        """)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Left panel - Chat & Controls
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel, 1)
        
        # Center panel - Main Canvas
        center_panel = self._create_center_panel()
        main_layout.addWidget(center_panel, 2)
        
        # Right panel - Webcam & Tools
        right_panel = self._create_right_panel()
        main_layout.addWidget(right_panel, 1)
    
    def _create_left_panel(self) -> QWidget:
        """Create chat and control panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Status
        status_group = QGroupBox("🧠 AI Status")
        status_layout = QVBoxLayout(status_group)
        self.ollama_status = QLabel("Ollama: Checking...")
        self.ollama_status.setStyleSheet("color: #ffcc00;")
        status_layout.addWidget(self.ollama_status)
        layout.addWidget(status_group)
        
        # Chat interface
        chat_group = QGroupBox("💬 Chat with AI")
        chat_layout = QVBoxLayout(chat_group)
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(300)
        self.chat_display.setStyleSheet("background: #0a0a15; font-family: monospace;")
        chat_layout.addWidget(self.chat_display)
        
        # Input area
        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type command or describe what to create...")
        self.chat_input.returnPressed.connect(self._on_chat_send)
        input_layout.addWidget(self.chat_input)
        
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._on_chat_send)
        input_layout.addWidget(send_btn)
        chat_layout.addLayout(input_layout)
        
        layout.addWidget(chat_group)
        
        # Creation history (memory)
        history_group = QGroupBox("📚 Creation Memory")
        history_layout = QVBoxLayout(history_group)
        
        self.history_list = QTextEdit()
        self.history_list.setReadOnly(True)
        self.history_list.setMaximumHeight(150)
        self.history_list.setStyleSheet("background: #0a0a15; font-size: 10px;")
        history_layout.addWidget(self.history_list)
        
        layout.addWidget(history_group)
        
        layout.addStretch()
        return panel
    
    def _create_center_panel(self) -> QWidget:
        """Create main canvas panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Canvas header
        header = QHBoxLayout()
        self.canvas_title = QLabel("🎨 Creation Canvas")
        self.canvas_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff88;")
        header.addWidget(self.canvas_title)
        
        self.creation_info = QLabel("")
        self.creation_info.setStyleSheet("color: #888;")
        header.addWidget(self.creation_info)
        header.addStretch()
        layout.addLayout(header)
        
        # Main canvas
        self.canvas = QLabel()
        self.canvas.setMinimumSize(800, 600)
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setStyleSheet("background: #0a0a15; border: 2px solid #333; border-radius: 8px;")
        layout.addWidget(self.canvas)
        
        # Canvas controls
        controls = QHBoxLayout()
        
        self.btn_record = QPushButton("🔴 Record")
        self.btn_record.clicked.connect(self._toggle_recording)
        controls.addWidget(self.btn_record)
        
        btn_save = QPushButton("💾 Save")
        btn_save.clicked.connect(self._save_creation)
        controls.addWidget(btn_save)
        
        btn_export = QPushButton("📤 Export to Unity")
        btn_export.clicked.connect(self._export_to_unity)
        controls.addWidget(btn_export)
        
        btn_clear = QPushButton("🗑️ Clear")
        btn_clear.clicked.connect(self._clear_canvas)
        controls.addWidget(btn_clear)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar { border: 2px solid #333; border-radius: 5px; background: #1a1a2e; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00ff88, stop:1 #00ccff); }
        """)
        layout.addWidget(self.progress)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """Create webcam and tools panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Webcam preview
        webcam_group = QGroupBox("📹 Webcam Feed")
        webcam_layout = QVBoxLayout(webcam_group)
        
        self.webcam_preview = QLabel()
        self.webcam_preview.setMinimumSize(320, 240)
        self.webcam_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.webcam_preview.setStyleSheet("background: #0a0a15; border: 1px solid #333;")
        self.webcam_preview.setText("Webcam Off")
        webcam_layout.addWidget(self.webcam_preview)
        
        webcam_btns = QHBoxLayout()
        self.btn_webcam = QPushButton("📷 Start Webcam")
        self.btn_webcam.clicked.connect(self._toggle_webcam)
        webcam_btns.addWidget(self.btn_webcam)
        
        btn_overlay = QPushButton("🔗 Overlay")
        btn_overlay.clicked.connect(self._toggle_overlay)
        webcam_btns.addWidget(btn_overlay)
        webcam_layout.addLayout(webcam_btns)
        
        layout.addWidget(webcam_group)
        
        # Creation mode
        mode_group = QGroupBox("🎯 Creation Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "World Map Generation",
            "Dungeon Map Generation", 
            "City Map Generation",
            "Terrain Sculpting",
            "Live Video Compositing"
        ])
        mode_layout.addWidget(self.mode_combo)
        
        # Style selection
        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "Fantasy", "Sci-Fi", "Medieval", "Modern",
            "Cyberpunk", "Steampunk", "Realistic"
        ])
        mode_layout.addWidget(self.style_combo)
        
        layout.addWidget(mode_group)
        
        # Quality settings
        quality_group = QGroupBox("⚙️ Quality")
        quality_layout = QVBoxLayout(quality_group)
        
        quality_layout.addWidget(QLabel("Resolution:"))
        self.resolution_slider = QSlider(Qt.Orientation.Horizontal)
        self.resolution_slider.setRange(256, 1024)
        self.resolution_slider.setValue(512)
        quality_layout.addWidget(self.resolution_slider)
        
        quality_layout.addWidget(QLabel("Detail Level:"))
        self.detail_slider = QSlider(Qt.Orientation.Horizontal)
        self.detail_slider.setRange(1, 10)
        self.detail_slider.setValue(7)
        quality_layout.addWidget(self.detail_slider)
        
        layout.addWidget(quality_group)
        
        layout.addStretch()
        return panel
    
    def _connect_engines(self):
        """Connect to all creation engines."""
        # PRIORITY 1: AIVisualEngine (diffusers) for true AI image generation
        try:
            from core.ai_visual_engine import get_visual_engine
            self._ai_visual_engine = get_visual_engine(self.event_bus)
            logger.info("✅ Connected to AIVisualEngine (diffusers)")
        except Exception as e:
            logger.warning(f"Could not connect AIVisualEngine: {e}")
        
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                self._unified_engine = self.event_bus.get_component('unified_creative_engine', silent=True)
            if self._unified_engine is None:
                from core.unified_creative_engine import get_unified_creative_engine
                self._unified_engine = get_unified_creative_engine(self.event_bus)
                if self.event_bus and hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('unified_creative_engine', self._unified_engine)
            if self._unified_engine:
                logger.info("✅ Connected to UnifiedCreativeEngine")
        except Exception as e:
            logger.warning(f"Could not connect UnifiedCreativeEngine: {e}")

        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                self._unity_runtime_bridge = self.event_bus.get_component('unity_runtime_bridge', silent=True)
            if self._unity_runtime_bridge is None:
                from core.unity_runtime_bridge import get_unity_runtime_bridge
                self._unity_runtime_bridge = get_unity_runtime_bridge(event_bus=self.event_bus)
                if self.event_bus and hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('unity_runtime_bridge', self._unity_runtime_bridge)
            if self._unity_runtime_bridge:
                logger.info("✅ Connected to UnityRuntimeBridge")
                # AUTO-LAUNCH Unity if not already running
                if not self._unity_runtime_bridge.is_connected() and _unity_autolaunch_enabled():
                    self._auto_launch_unity()
        except Exception as e:
            logger.warning(f"Could not connect UnityRuntimeBridge: {e}")

        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                self._unity_hub_manager = self.event_bus.get_component('unity_hub_manager', silent=True)
                self._unity_mcp_tools = self.event_bus.get_component('unity_mcp_tools', silent=True)
            if self._unity_hub_manager is None:
                from core.unity_mcp_integration import get_unity_hub_manager, get_unity_mcp_tools
                self._unity_hub_manager = get_unity_hub_manager(event_bus=self.event_bus)
                self._unity_mcp_tools = get_unity_mcp_tools(event_bus=self.event_bus)
                if self.event_bus and hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('unity_hub_manager', self._unity_hub_manager)
                    self.event_bus.register_component('unity_mcp_tools', self._unity_mcp_tools)
            if self._unity_hub_manager:
                logger.info("✅ Connected to UnityHubManager")
        except Exception as e:
            logger.warning(f"Could not connect Unity MCP integration: {e}")
        
        try:
            from core.universal_animation_engine import get_animation_engine
            self._animation_engine = get_animation_engine(self.event_bus)
            logger.info("✅ Connected to AnimationEngine")
        except Exception as e:
            logger.warning(f"Could not connect AnimationEngine: {e}")
        
        try:
            from core.cinema_engine_sota_2026 import get_cinema_engine
            self._cinema_engine = get_cinema_engine(self.event_bus)
            logger.info("✅ Connected to CinemaEngine")
        except Exception as e:
            logger.warning(f"Could not connect CinemaEngine: {e}")
    
    def _connect_meta_learning(self):
        """Connect to existing meta learning system for improved generation over time."""
        try:
            from core.meta_learning import MetaLearning
            self._meta_learning = MetaLearning(event_bus=self.event_bus)
            logger.info("✅ Connected to MetaLearning system")
        except Exception as e:
            logger.warning(f"Could not connect MetaLearning: {e}")
    
    def _load_creation_memory(self):
        """Load creation history from memory for learning."""
        try:
            memory_path = Path(__file__).parent.parent / "data" / "learning" / "creation_memory.json"
            if memory_path.exists():
                import json
                with open(memory_path, 'r') as f:
                    self._creation_history = json.load(f)
                self._update_history_display()
                logger.info(f"📚 Loaded {len(self._creation_history)} creation memories")
        except Exception as e:
            logger.warning(f"Could not load creation memory: {e}")
    
    def _save_creation_memory(self):
        """Save creation history for learning."""
        try:
            memory_dir = Path(__file__).parent.parent / "data" / "learning"
            memory_dir.mkdir(parents=True, exist_ok=True)
            memory_path = memory_dir / "creation_memory.json"
            import json
            with open(memory_path, 'w') as f:
                json.dump(self._creation_history[-100:], f, indent=2)  # Keep last 100
            logger.info(f"💾 Saved {len(self._creation_history)} creation memories")
        except Exception as e:
            logger.warning(f"Could not save creation memory: {e}")
    
    def _record_creation(self, prompt: str, result: dict, success: bool):
        """Record a creation for learning."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "success": success,
            "type": result.get("type", "unknown"),
            "id": result.get("id", "")
        }
        self._creation_history.append(record)
        self._update_history_display()
        self._save_creation_memory()
        
        # Publish to meta learning if available
        if self.event_bus:
            try:
                self.event_bus.publish("meta.learn_interaction", {
                    "type": "creation",
                    "data": record
                })
            except Exception:
                pass
    
    def _update_history_display(self):
        """Update the history display with recent creations."""
        if hasattr(self, 'history_list'):
            self.history_list.clear()
            for record in self._creation_history[-10:]:
                status = "✅" if record.get("success") else "❌"
                self.history_list.append(f'{status} {record.get("prompt", "")[:40]}...')
    
    def _check_ollama(self):
        """Check Ollama connection. Uses WSL-aware URL (Ollama brain first)."""
        try:
            import requests
            try:
                from core.ollama_gateway import get_ollama_url
                base = get_ollama_url()
            except ImportError:
                try:
                    from core.ollama_config import get_ollama_base_url
                    base = get_ollama_base_url().rstrip("/")
                except Exception:
                    base = "http://localhost:11434"
            resp = requests.get(f"{base}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                self._ollama_connected = True
                self.ollama_status.setText(f"🟢 Ollama: Connected ({len(models)} models)")
                self.ollama_status.setStyleSheet("color: #00ff88;")
                self._add_chat_message("System", f"🧠 Ollama brain connected with {len(models)} models available!")
            else:
                self.ollama_status.setText("🔴 Ollama: Not responding")
                self.ollama_status.setStyleSheet("color: #ff4444;")
        except Exception:
            self._ollama_connected = False
            self.ollama_status.setText("🔴 Ollama: Offline")
            self.ollama_status.setStyleSheet("color: #ff4444;")
            self._add_chat_message("System", "⚠️ Ollama not available - basic mode active")
    
    def _add_chat_message(self, sender: str, message: str):
        """Add message to chat display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = "#00ff88" if sender == "AI" else "#88ccff" if sender == "You" else "#888"
        self.chat_display.append(f'<span style="color: {color};">[{timestamp}] {sender}:</span> {message}')
    
    def _on_chat_send(self):
        """Handle chat message send.

        Every prompt is routed through the UnifiedCreationOrchestrator so that
        ANY creation engine in the Kingdom AI registry (image, video, CAD,
        chemistry, PCB, fashion, music, code, world-gen, etc.) is reachable
        via natural language. Local UI-only commands (webcam/record/unity)
        still run directly for immediate feedback.
        """
        text = self.chat_input.text().strip()
        if not text:
            return

        self.chat_input.clear()
        self._add_chat_message("You", text)

        text_lower = text.lower()

        # Local UI-only side-effects (keep instant feedback)
        if "webcam" in text_lower or "camera" in text_lower:
            if "start" in text_lower or "on" in text_lower:
                self._toggle_webcam()
                return
            if "stop" in text_lower or "off" in text_lower:
                if getattr(self, "_webcam_thread", None):
                    self._toggle_webcam()
                    return
        if "record" in text_lower:
            self._toggle_recording()
            return
        if "export" in text_lower and "unity" in text_lower:
            self._export_to_unity()
            return
        if "unity" in text_lower and ("send" in text_lower or "runtime" in text_lower):
            self._send_terrain_to_unity_runtime()
            return

        # Route through the unified NL orchestrator so every creation engine
        # in the Kingdom registry is reachable (image, video, CAD, chemistry,
        # PCB, fashion, architecture, music, world-gen, code, ...).
        try:
            from core.unified_creation_orchestrator import (
                get_unified_creation_orchestrator,
            )
            uco = get_unified_creation_orchestrator(event_bus=self.event_bus)
            outcome = uco.handle_natural_language(text)
            if outcome and outcome.success:
                self._add_chat_message(
                    "System",
                    f"🧠 Routed to {outcome.primary}  "
                    f"({outcome.execution_time:.1f}s)"
                )
            else:
                errs = (outcome.errors[0] if outcome and outcome.errors
                        else "no engine could satisfy request")
                self._add_chat_message("System", f"⚠️ {errs}")
        except Exception as e:
            logger.debug("UnifiedCreationOrchestrator unavailable: %s", e)

        # Also drive the existing visual/edit pipelines so the canvas and
        # live preview stay populated. This is additive — the unified
        # orchestrator has already dispatched to the correct engine(s).
        if any(w in text_lower for w in
               ["create", "generate", "make", "build", "draw", "paint", "design"]):
            self._create_from_prompt(text)
        elif any(w in text_lower for w in
                 ["add", "remove", "edit", "change", "more"]):
            self._edit_from_prompt(text)
        else:
            self._create_from_prompt(text)
    
    def _ask_ollama(self, prompt: str):
        """Send query to Ollama."""
        self._add_chat_message("System", "🧠 Thinking...")
        
        full_prompt = f"""You are Kingdom AI creative assistant. The user said: "{prompt}"
        
Available commands you can suggest:
- Create world map/dungeon/city
- Add city/river/mountains to current creation
- Start/stop webcam
- Record creation
- Export to Unity

Respond helpfully in 2-3 sentences."""
        
        self._ollama_worker = OllamaWorker(full_prompt)
        self._ollama_worker.response_ready.connect(self._on_ollama_response)
        self._ollama_worker.start()
    
    def _on_ollama_response(self, response: str):
        """Handle Ollama response."""
        self._add_chat_message("AI", response)

    def _publish_visual_request_with_retry(
        self,
        request_payload: Dict[str, Any],
        max_attempts: int = 4,
        base_delay_s: float = 0.2,
    ) -> bool:
        """Publish visual.request with startup-contention retry."""
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            bus = getattr(self, "event_bus", None)
            if bus is None:
                last_error = RuntimeError("EventBus not ready")
            else:
                try:
                    bus.publish("visual.request", request_payload)
                    logger.info(
                        "🎨 visual.request published (attempt %d/%d): %s...",
                        attempt,
                        max_attempts,
                        str(request_payload.get("prompt", ""))[:50],
                    )
                    return True
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "⚠️ visual.request publish attempt %d/%d failed: %s",
                        attempt,
                        max_attempts,
                        e,
                    )
            if attempt < max_attempts:
                time.sleep(base_delay_s * attempt)
        logger.error("❌ visual.request publish failed after retries: %s", last_error)
        return False
    
    def _create_from_prompt(self, prompt: str, vision_payload: Optional[Dict[str, Any]] = None):
        """Create ANYTHING from prompt - UNLIMITED creation capability.
        
        SOTA 2026: Uses Unified Brain Flow (visual.request → BrainRouter → VisualCreationCanvas)
        This ensures ALL creation goes through the Kingdom AI brain for context awareness.
        """
        self._add_chat_message("System", f"🎨 Creating: {prompt[:50]}...")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        prompt_lower = prompt.lower()
        force_all_engines = any(
            key in prompt_lower
            for key in (
                "all engines",
                "all engine libraries",
                "unified multi engine",
                "system wide unified",
                "force orchestrator",
            )
        )
        
        # SOTA 2026: CRITICAL - Use Unified Brain Flow FIRST (visual.request → BrainRouter → VisualCreationCanvas)
        # This ensures the brain processes the request and VisualCreationCanvas generates the image
        if self.event_bus:
            try:
                # Publish visual.request to go through unified brain flow
                request_payload = {
                    "prompt": prompt,
                    "mode": "image",  # Default to image, can be overridden
                    "timestamp": time.time(),
                    "source": "CreativeStudio",
                    "force_orchestrator": force_all_engines,
                    "use_all_engine_libraries": force_all_engines,
                    "system_wide_unified_context": force_all_engines,
                    "engine_scope": "all" if force_all_engines else "auto",
                    "pipeline": "unified_multi_engine" if force_all_engines else "auto",
                    "orchestration_policy": "all_engines_primary" if force_all_engines else "auto",
                }
                if isinstance(vision_payload, dict):
                    images = vision_payload.get("images")
                    if isinstance(images, list) and images:
                        request_payload["images"] = images
                    for key in ("vision_source", "vision_frame_age_s", "vision_context", "vision_sources_available", "vision_source_preference"):
                        if key in vision_payload:
                            request_payload[key] = vision_payload.get(key)
                
                # Detect mode from prompt
                if any(word in prompt_lower for word in ["animate", "animation", "video", "movie", "moving", "motion"]):
                    request_payload["mode"] = "video"
                elif any(word in prompt_lower for word in ["map", "world", "terrain"]):
                    request_payload["mode"] = "image"  # Maps are still images
                
                request_id = request_payload.get("request_id", f"creative_studio_{int(time.time() * 1000)}")
                request_payload["request_id"] = request_id
                
                dispatched = self._publish_visual_request_with_retry(request_payload)
                if not dispatched:
                    raise RuntimeError("visual.request dispatch failed after retries")
                logger.info(f"🎨 Creative Studio published visual.request → BrainRouter → VisualCreationCanvas: {prompt[:50]}...")
                self._add_chat_message("System", "🧠 Processing through Kingdom AI Brain...")
                self.progress.setValue(10)
                
                self._pending_visual_requests[request_id] = {
                    "prompt": prompt,
                    "timestamp": time.time(),
                }
                
                return
            except Exception as e:
                logger.error(f"Failed to publish visual.request: {e}")
                self._add_chat_message("System", f"❌ Brain flow failed: {e}")
                if hasattr(self, "progress") and self.progress:
                    self.progress.setVisible(False)
                return
        
        # FALLBACK: Direct engine access if EventBus unavailable
        result = {"success": False}
        image_path = None
        ai_reason = None
        
        # ============================================================
        # PRIORITY 1: Try AIVisualEngine (diffusers) FIRST
        # ============================================================
        if self._ai_visual_engine:
            self._add_chat_message("System", "🤖 Using AI diffusers for generation...")
            self.progress.setValue(20)
            try:
                import asyncio
                
                async def generate_ai_image():
                    return await self._ai_visual_engine.generate_image(prompt)
                
                # Run async generation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    visual_result = loop.run_until_complete(generate_ai_image())
                finally:
                    loop.close()
                
                self.progress.setValue(60)
                
                if visual_result and visual_result.success:
                    # Save the generated image
                    if visual_result.image is not None:
                        from PIL import Image
                        export_dir = Path(__file__).parent.parent / "exports" / "ai_creations"
                        export_dir.mkdir(parents=True, exist_ok=True)
                        filename = f"ai_creation_{int(time.time())}.png"
                        filepath = export_dir / filename
                        
                        # Handle PIL Image or numpy array
                        if isinstance(visual_result.image, Image.Image):
                            visual_result.image.save(str(filepath))
                        else:
                            Image.fromarray(visual_result.image).save(str(filepath))
                        
                        image_path = str(filepath)
                        gen_method = visual_result.metadata.get('method', 'diffusers')
                        result = {
                            "success": True,
                            "id": filename.replace(".png", ""),
                            "image_path": image_path,
                            "type": "ai_diffusers",
                            "method": gen_method
                        }
                        self._add_chat_message("System", f"✨ AI generated using: {gen_method}")
                    else:
                        ai_reason = "AI returned no image data"
                else:
                    ai_reason = getattr(visual_result, 'error', 'AI generation failed') if visual_result else 'No result'
            except Exception as e:
                ai_reason = f"AI engine error: {str(e)[:100]}"
                logger.warning(f"AIVisualEngine failed: {e}")
        else:
            ai_reason = "AIVisualEngine not available"
        
        # ============================================================
        # PRIORITY 2: Domain-specific engines (if AI didn't succeed)
        # ============================================================
        if not result.get("success"):
            if ai_reason:
                self._add_chat_message("System", f"⚠️ AI fallback reason: {ai_reason}")
            
            # 2a. Map/terrain/world request
            if self._unified_engine and any(word in prompt_lower for word in 
                ["map", "world", "terrain", "dungeon", "city", "kingdom", "land", "forest", "mountain"]):
                self._add_chat_message("System", "🗺️ Using map engine...")
                result = self._unified_engine.create(prompt)
                self.progress.setValue(50)
                
                if result.get("success"):
                    map_id = result.get("id")
                    self._current_creation = map_id
                    render_result = self._unified_engine.render_map_to_image(str(map_id), show=False)
                    if render_result.get("success"):
                        image_path = render_result.get("image_path", "")
            
            # 2b. Cinema engine for scenes/videos
            elif self._cinema_engine and any(word in prompt_lower for word in 
                ["scene", "video", "movie", "cinematic"]):
                self._add_chat_message("System", "🎬 Using cinema engine...")
                try:
                    output_path = self._cinema_engine.generate_video_from_prompt(prompt)
                    if output_path:
                        result = {"success": True, "output_path": output_path}
                        image_path = output_path
                except Exception as e:
                    logger.warning(f"Cinema engine failed: {e}")
            
            # 2c. Animation engine for animated content
            elif self._animation_engine and any(word in prompt_lower for word in 
                ["animate", "character", "sprite", "motion"]):
                self._add_chat_message("System", "🎭 Using animation engine...")
                try:
                    output_path = self._animation_engine.animate_data(prompt, "text")
                    if output_path:
                        result = {"success": True, "output_path": output_path}
                        image_path = output_path
                except Exception as e:
                    logger.warning(f"Animation engine failed: {e}")
        
        # ============================================================
        # PRIORITY 3: Procedural fallback (last resort)
        # ============================================================
        if not result.get("success"):
            self._add_chat_message("System", "🎲 Using procedural generation (fallback)...")
            result = self._generate_procedural_image(prompt)
            if result.get("success"):
                image_path = result.get("image_path")
        
        self.progress.setValue(80)
        
        # Display result
        if result.get("success") and image_path:
            self._current_creation = result.get("id", f"creation_{int(time.time())}")
            self._add_chat_message("System", f"✅ Created: {self._current_creation}")
            self._record_creation(prompt, result, True)
            self._display_image(str(image_path))
            self._add_chat_message("System", "🖼️ Displayed on canvas!")
            self.progress.setValue(100)
        elif result.get("success"):
            self._add_chat_message("System", f"✅ Created but no visual output")
            self._record_creation(prompt, result, True)
        else:
            self._add_chat_message("System", f"❌ Failed: {result.get('error', 'Unknown error')}")
            self._record_creation(prompt, result, False)
        
        self.progress.setVisible(False)
    
    def _generate_procedural_image(self, prompt: str) -> Dict[str, Any]:
        """Generate a procedural image for ANY prompt - UNLIMITED creativity."""
        try:
            import numpy as np
            from PIL import Image, ImageDraw, ImageFont
            
            # Create base image
            width, height = 512, 512
            img = Image.new('RGB', (width, height), color='#1a1a2e')
            draw = ImageDraw.Draw(img)
            
            # Use Ollama to get creative parameters if available
            colors = self._get_colors_from_prompt(prompt)
            
            # Generate procedural art based on prompt
            np.random.seed(hash(prompt) % (2**32))
            
            # Draw procedural elements
            for i in range(50):
                x1 = np.random.randint(0, width)
                y1 = np.random.randint(0, height)
                x2 = x1 + np.random.randint(20, 100)
                y2 = y1 + np.random.randint(20, 100)
                color = colors[i % len(colors)]
                
                shape_type = np.random.choice(['ellipse', 'rectangle', 'line'])
                if shape_type == 'ellipse':
                    draw.ellipse([x1, y1, x2, y2], fill=color, outline=None)
                elif shape_type == 'rectangle':
                    draw.rectangle([x1, y1, x2, y2], fill=color, outline=None)
                else:
                    draw.line([x1, y1, x2, y2], fill=color, width=3)
            
            # Add title
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            except Exception:
                font = ImageFont.load_default()
            
            title = prompt[:30] + "..." if len(prompt) > 30 else prompt
            draw.text((20, 20), title, fill='white', font=font)
            
            # Save image
            export_dir = Path(__file__).parent.parent / "exports" / "creations"
            export_dir.mkdir(parents=True, exist_ok=True)
            filename = f"creation_{int(time.time())}.png"
            filepath = export_dir / filename
            img.save(str(filepath))
            
            return {
                "success": True,
                "id": filename.replace(".png", ""),
                "image_path": str(filepath),
                "type": "procedural"
            }
        except Exception as e:
            logger.error(f"Procedural generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_colors_from_prompt(self, prompt: str) -> List[str]:
        """Extract colors from prompt or generate appropriate palette."""
        prompt_lower = prompt.lower()
        
        # Color mappings based on common themes
        if any(w in prompt_lower for w in ["fire", "lava", "hot", "sun"]):
            return ['#ff4400', '#ff6600', '#ff8800', '#ffaa00', '#ffcc00']
        elif any(w in prompt_lower for w in ["water", "ocean", "sea", "ice", "cold"]):
            return ['#0044ff', '#0066ff', '#0088ff', '#00aaff', '#00ccff']
        elif any(w in prompt_lower for w in ["forest", "tree", "plant", "nature", "green"]):
            return ['#004400', '#006600', '#008800', '#00aa00', '#00cc00']
        elif any(w in prompt_lower for w in ["night", "dark", "shadow", "space"]):
            return ['#110022', '#220044', '#330066', '#440088', '#5500aa']
        elif any(w in prompt_lower for w in ["gold", "treasure", "rich"]):
            return ['#ffd700', '#ffcc00', '#ffaa00', '#ff8800', '#cc6600']
        else:
            # Default vibrant palette
            return ['#ff0066', '#00ff88', '#0088ff', '#ff8800', '#aa00ff']
    
    def _edit_from_prompt(self, prompt: str):
        """Edit current creation from prompt."""
        if not self._current_creation:
            self._add_chat_message("System", "⚠️ No creation to edit. Create something first!")
            return
        
        if not self._unified_engine:
            self._add_chat_message("System", "❌ Creation engine not available")
            return
        
        self._add_chat_message("System", f"✏️ Editing: {prompt[:50]}...")
        
        result = self._unified_engine.edit_live(str(self._current_creation), prompt)
        
        if result.get("success"):
            self._add_chat_message("System", f"✅ Applied {result.get('edits_applied', 0)} edits")
            
            # Re-render
            render_result = self._unified_engine.render_map_to_image(str(self._current_creation), show=False)
            if render_result.get("success"):
                image_path = render_result.get("image_path", "")
                if image_path:
                    self._display_image(str(image_path))
        else:
            self._add_chat_message("System", f"❌ Edit failed: {result.get('error')}")
    
    def _toggle_webcam(self):
        """Toggle webcam on/off."""
        if self._webcam_thread and self._webcam_thread.isRunning():
            self._webcam_thread.stop()
            self._webcam_thread = None
            self.btn_webcam.setText("📷 Start Webcam")
            self.webcam_preview.setText("Webcam Off")
            self._add_chat_message("System", "📷 Webcam stopped")
        else:
            if _is_wsl_runtime():
                self._webcam_thread = WebcamThread(event_bus=self.event_bus)
            else:
                self._webcam_thread = WebcamThreadDirect()
            self._webcam_thread.frame_ready.connect(self._on_webcam_frame)
            self._webcam_thread.status_update.connect(self._on_webcam_status)
            self._webcam_thread.start()
            self.btn_webcam.setText("⏹️ Stop Webcam")
            self._add_chat_message("System", "📷 Webcam started")
    
    def _on_webcam_frame(self, frame: np.ndarray):
        """Handle webcam frame."""
        self._webcam_frame = frame
        
        # Display in preview
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.webcam_preview.setPixmap(pixmap.scaled(320, 240, Qt.AspectRatioMode.KeepAspectRatio))
        
        # Record if recording
        if self._recording:
            self._recorded_frames.append(frame.copy())
    
    def _on_webcam_status(self, status: str):
        """Handle webcam status updates."""
        self._add_chat_message("Webcam", status)
        if "Error" in status:
            self.webcam_preview.setText(f"⚠️ {status}")
    
    def _toggle_overlay(self):
        """Toggle webcam overlay on canvas."""
        self._add_chat_message("System", "🔗 Overlay feature - composites webcam with creation")
    
    def _toggle_recording(self):
        """Toggle recording."""
        if self._recording:
            self._recording = False
            self.btn_record.setText("🔴 Record")
            self._add_chat_message("System", f"⏹️ Recording stopped - {len(self._recorded_frames)} frames captured")
        else:
            self._recording = True
            self._recorded_frames = []
            self.btn_record.setText("⏹️ Stop")
            self._add_chat_message("System", "🔴 Recording started...")
    
    def _save_creation(self):
        """Save current creation."""
        if not self._current_creation:
            self._add_chat_message("System", "⚠️ Nothing to save")
            return
        
        export_dir = Path(__file__).parent.parent / "exports" / "creations"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"creation_{self._current_creation}_{int(time.time())}.png"
        filepath = export_dir / filename
        
        pixmap = self.canvas.pixmap()
        if pixmap:
            pixmap.save(str(filepath))
            self._add_chat_message("System", f"💾 Saved: {filepath}")
    
    def _export_to_unity(self):
        """Export to Unity."""
        if not self._current_creation:
            self._add_chat_message("System", "⚠️ Nothing to export")
            return

        if not self._unified_engine:
            self._add_chat_message("System", "❌ Creation engine not available")
            return

        map_id = str(self._current_creation)
        maps = getattr(self._unified_engine, 'maps', None)
        if isinstance(maps, dict) and map_id not in maps:
            self._add_chat_message("System", "⚠️ Current creation is not a map. Create a map first!")
            return

        self._add_chat_message("System", "📤 Exporting to Unity...")
        
        try:
            result = self._unified_engine.export_to_unity(map_id)
        except Exception as e:
            result = {"success": False, "error": str(e)}

        if result.get("success"):
            exports = result.get("exports") or {}
            json_path = exports.get("json")
            raw_path = exports.get("raw_heightmap")
            if json_path or raw_path:
                self._add_chat_message("System", f"✅ Unity export ready\nJSON: {json_path}\nRAW: {raw_path}")
            else:
                self._add_chat_message("System", "✅ Exported to Unity!")
        else:
            self._add_chat_message("System", f"❌ Export failed: {result.get('error')}")

    def _send_terrain_to_unity_runtime(self):
        if not self._current_creation:
            self._add_chat_message("System", "⚠️ Nothing to send")
            return

        if not self._unified_engine:
            self._add_chat_message("System", "❌ Creation engine not available")
            return

        map_id = str(self._current_creation)
        maps = getattr(self._unified_engine, 'maps', None)
        if isinstance(maps, dict) and map_id not in maps:
            self._add_chat_message("System", "⚠️ Current creation is not a map. Create a map first!")
            return

        self._add_chat_message("System", "🎮 Sending terrain to Unity runtime...")

        try:
            result = self._unified_engine.send_terrain_to_unity_runtime(map_id)
        except Exception as e:
            result = {"success": False, "error": str(e)}

        if result.get("success"):
            sent_to = result.get("sent_to")
            if sent_to:
                self._add_chat_message("System", f"✅ Sent to Unity runtime: {sent_to}")
            else:
                self._add_chat_message("System", "✅ Sent to Unity runtime")
        else:
            self._add_chat_message("System", f"❌ Send failed: {result.get('error')}")
    
    def _clear_canvas(self):
        """Clear canvas."""
        self.canvas.clear()
        self.canvas.setText("Canvas Cleared")
        self._current_creation = None
        self._add_chat_message("System", "🗑️ Canvas cleared")
    
    def _update_display(self):
        """Update display timer callback — refreshes canvas viewport at ~30 FPS."""
        try:
            now = time.time()
            timed_out = [
                rid for rid, info in self._pending_visual_requests.items()
                if now - info.get("submitted_at", now) > self._visual_request_timeout
            ]
            for rid in timed_out:
                self._pending_visual_requests.pop(rid, None)
                if rid == self._active_visual_request_id:
                    self._active_visual_request_id = None
                self._add_chat_message(
                    "System",
                    f"Request {rid[:8]}... timed out after {self._visual_request_timeout}s"
                )

            if self._webcam_frame is not None and not self._current_creation:
                frame = self._webcam_frame
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                from PyQt6.QtGui import QImage, QPixmap
                from PyQt6.QtCore import Qt
                qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                self.canvas.setPixmap(
                    pixmap.scaled(
                        self.canvas.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            self.canvas.update()
        except Exception:
            pass
    
    def closeEvent(self, event):
        """Clean up on close."""
        if self._webcam_thread:
            self._webcam_thread.stop()
        self._update_timer.stop()
        super().closeEvent(event)


class CreativeStudioWidget(QWidget):  # type: ignore[misc]
    """
    Embeddable Creative Studio Widget for main GUI integration.
    
    Same functionality as RealtimeCreativeStudio but as a QWidget
    that can be added as a tab in KingdomMainWindow.
    
    SOTA 2026: Integrated into main application, no standalone window.
    """
    
    # Signals for parent communication
    creation_completed = pyqtSignal(dict)  # Emits creation result
    terrain_sent = pyqtSignal(dict)  # Emits when terrain sent to Unity
    status_updated = pyqtSignal(str)  # Status message updates
    
    def __init__(self, event_bus=None, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self._disable_fallback = os.environ.get("KINGDOM_CREATIVE_DISABLE_FALLBACK", "0").strip().lower() in ("1", "true", "yes", "on")
        self._active_movie = None
        self._media_player = None
        self._audio_output = None
        self._video_widget = None
        self._canvas_stack = None
        
        # State
        self._webcam_thread = None
        self._webcam_frame = None
        self._current_creation = None
        self._creation_history = []
        self._ollama_connected = False
        self._recording = False
        self._recorded_frames = []
        
        # Engines
        self._unified_engine = None
        self._animation_engine = None
        self._cinema_engine = None
        self._meta_learning = None
        self._ai_visual_engine = None
        self._unity_runtime_bridge = None
        
        # SOTA 2026 FIX: Initialize pending request tracking and timeout
        # This fixes "Waiting for Kingdom AI Brain to process..." staying stuck forever
        self._pending_visual_requests = {}
        self._visual_request_timeout = 120  # Longer default for heavy generation paths
        self._active_visual_request_id: Optional[str] = None
        self._last_completed_visual_request_id: Optional[str] = None
        
        # Initialize
        try:
            self._setup_ui()
            self._connect_engines()
            self._connect_event_bus()
            self._check_ollama()
            
            # Update timer
            self._update_timer = QTimer()
            self._update_timer.timeout.connect(self._update_display)
            self._update_timer.start(33)
            
            logger.info("🎨 CreativeStudioWidget initialized (embedded mode)")
        except Exception as e:
            logger.error(f"❌ CreativeStudioWidget initialization failed: {e}", exc_info=True)
            # Create minimal fallback UI so tab doesn't crash
            try:
                fallback_layout = QVBoxLayout(self)
                error_label = QLabel(f"Creative Studio initialization error: {e}")
                error_label.setStyleSheet("color: red; padding: 20px;")
                fallback_layout.addWidget(error_label)
            except Exception:
                pass
    
    def _setup_ui(self):
        """Setup the widget UI - optimized for embedding in tabs."""
        self.setStyleSheet("""
            QWidget { color: white; background: transparent; }
            QGroupBox { 
                border: 2px solid #333; 
                border-radius: 8px; 
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                background: rgba(10, 10, 26, 0.8);
            }
            QGroupBox::title { 
                subcontrol-origin: margin;
                left: 10px;
                color: #00ff88;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a1a3a, stop:1 #2a2a5a);
                border: 2px solid #444;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { border-color: #00ff88; }
            QPushButton:pressed { background: #00ff88; color: black; }
            QLineEdit, QTextEdit {
                background: #1a1a2e;
                border: 2px solid #333;
                border-radius: 4px;
                padding: 6px;
                color: white;
            }
            QComboBox {
                background: #1a1a2e;
                border: 2px solid #333;
                border-radius: 4px;
                padding: 6px;
                color: white;
            }
        """)
        
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Left panel - Chat & Controls
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel, 1)
        
        # Center panel - Main Canvas
        center_panel = self._create_center_panel()
        main_layout.addWidget(center_panel, 2)
        
        # Right panel - Tools & Settings
        right_panel = self._create_right_panel()
        main_layout.addWidget(right_panel, 1)
    
    def _create_left_panel(self) -> QWidget:
        """Create chat and control panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Status
        status_group = QGroupBox("🧠 AI Status")
        status_layout = QVBoxLayout(status_group)
        self.ollama_status = QLabel("Ollama: Checking...")
        self.ollama_status.setStyleSheet("color: #ffcc00;")
        status_layout.addWidget(self.ollama_status)
        
        self.unity_status = QLabel("Unity: Not connected")
        self.unity_status.setStyleSheet("color: #888;")
        status_layout.addWidget(self.unity_status)
        self.unity_connect_btn = QPushButton("Connect Unity")
        self.unity_connect_btn.setToolTip("Connect to Unity runtime (port 8080)")
        self.unity_connect_btn.clicked.connect(self._on_connect_unity_clicked)
        status_layout.addWidget(self.unity_connect_btn)
        layout.addWidget(status_group)
        
        # Chat interface
        chat_group = QGroupBox("💬 Creative Commands")
        chat_layout = QVBoxLayout(chat_group)
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(200)
        self.chat_display.setStyleSheet("background: #0a0a15; font-family: monospace;")
        chat_layout.addWidget(self.chat_display)
        
        # Input area
        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Create world map, add city, send to Unity...")
        self.chat_input.returnPressed.connect(self._on_chat_send)
        input_layout.addWidget(self.chat_input)
        
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._on_chat_send)
        input_layout.addWidget(send_btn)
        chat_layout.addLayout(input_layout)
        
        layout.addWidget(chat_group)
        layout.addStretch()
        return panel
    
    def _create_center_panel(self) -> QWidget:
        """Create main canvas panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Canvas header
        header = QHBoxLayout()
        self.canvas_title = QLabel("🎨 Creation Canvas")
        self.canvas_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00ff88;")
        header.addWidget(self.canvas_title)
        
        self.creation_info = QLabel("")
        self.creation_info.setStyleSheet("color: #888;")
        header.addWidget(self.creation_info)
        header.addStretch()
        layout.addLayout(header)
        
        # Main canvas - SOTA 2026: Properly sized for live image/video display
        self.canvas = QLabel()
        self.canvas.setMinimumSize(800, 600)  # Larger size for better visibility
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #1a1a2e, stop:1 #16213e);
                border: 3px solid #00ff88;
                border-radius: 10px;
                color: #888;
                font-size: 18px;
            }
        """)
        self.canvas.setText("🎨 Canvas Ready - Type 'create [something]' to generate images!")
        # CRITICAL FIX: Ensure QLabel can display pixmaps properly
        self.canvas.setScaledContents(False)  # We handle scaling in _display_image
        self.canvas.setWordWrap(False)  # Don't wrap text
        # SOTA 2026: Ensure canvas expands to fill available space
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._canvas_stack = QStackedWidget()
        self._canvas_stack.addWidget(self.canvas)

        if HAS_QT_MEDIA and QVideoWidget is not None:
            try:
                self._video_widget = QVideoWidget()
                self._video_widget.setMinimumSize(800, 600)
                self._canvas_stack.addWidget(self._video_widget)
            except Exception as e:
                logger.warning(f"Could not initialize QVideoWidget: {e}")
                self._video_widget = None

        layout.addWidget(self._canvas_stack)
        
        # Canvas controls
        controls = QHBoxLayout()
        
        btn_save = QPushButton("💾 Save")
        btn_save.clicked.connect(self._save_creation)
        controls.addWidget(btn_save)
        
        btn_export = QPushButton("📤 Export Unity")
        btn_export.clicked.connect(self._export_to_unity)
        controls.addWidget(btn_export)
        
        btn_runtime = QPushButton("🎮 Send to Unity Runtime")
        btn_runtime.clicked.connect(self._send_terrain_to_unity_runtime)
        btn_runtime.setStyleSheet("QPushButton { background: #2a4a2a; } QPushButton:hover { border-color: #00ff88; }")
        controls.addWidget(btn_runtime)
        
        # SOTA 2026: Unity Project Management Buttons (no more CLI-only!)
        btn_create_project = QPushButton("📁 New Unity Project")
        btn_create_project.clicked.connect(self._create_unity_project)
        btn_create_project.setStyleSheet("QPushButton { background: #2a2a4a; } QPushButton:hover { border-color: #ff00ff; }")
        controls.addWidget(btn_create_project)
        
        btn_build_project = QPushButton("🏗️ Build Project")
        btn_build_project.clicked.connect(self._build_unity_project)
        btn_build_project.setStyleSheet("QPushButton { background: #4a2a2a; } QPushButton:hover { border-color: #ff8800; }")
        controls.addWidget(btn_build_project)
        
        btn_clear = QPushButton("🗑️ Clear")
        btn_clear.clicked.connect(self._clear_canvas)
        controls.addWidget(btn_clear)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar { border: 2px solid #333; border-radius: 5px; background: #1a1a2e; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00ff88, stop:1 #00ccff); }
        """)
        layout.addWidget(self.progress)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """Create tools panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Creation mode
        mode_group = QGroupBox("🎯 Creation Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "World Map Generation",
            "Dungeon Map Generation", 
            "City Map Generation",
            "Terrain Sculpting",
        ])
        mode_layout.addWidget(self.mode_combo)
        
        # Style selection
        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "Fantasy", "Sci-Fi", "Medieval", "Modern",
            "Cyberpunk", "Steampunk", "Realistic"
        ])
        mode_layout.addWidget(self.style_combo)
        
        layout.addWidget(mode_group)
        
        # Quality settings
        quality_group = QGroupBox("⚙️ Quality")
        quality_layout = QVBoxLayout(quality_group)
        
        quality_layout.addWidget(QLabel("Resolution:"))
        self.resolution_slider = QSlider(Qt.Orientation.Horizontal)
        self.resolution_slider.setRange(256, 1024)
        self.resolution_slider.setValue(512)
        quality_layout.addWidget(self.resolution_slider)
        
        layout.addWidget(quality_group)
        
        # Quick actions
        actions_group = QGroupBox("⚡ Quick Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        btn_world = QPushButton("🌍 Create World Map")
        btn_world.clicked.connect(lambda: self._quick_create("create world map"))
        actions_layout.addWidget(btn_world)
        
        btn_dungeon = QPushButton("🏰 Create Dungeon")
        btn_dungeon.clicked.connect(lambda: self._quick_create("create dungeon map"))
        actions_layout.addWidget(btn_dungeon)
        
        btn_city = QPushButton("🏙️ Create City")
        btn_city.clicked.connect(lambda: self._quick_create("create city map"))
        actions_layout.addWidget(btn_city)
        
        layout.addWidget(actions_group)
        
        layout.addStretch()
        return panel
    
    def _connect_engines(self):
        """Connect to all creation engines."""
        try:
            from core.ai_visual_engine import get_visual_engine
            self._ai_visual_engine = get_visual_engine(self.event_bus)
            logger.info("✅ Connected to AIVisualEngine")
        except Exception as e:
            logger.warning(f"Could not connect AIVisualEngine: {e}")
        
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                self._unified_engine = self.event_bus.get_component('unified_creative_engine', silent=True)
            if self._unified_engine is None:
                from core.unified_creative_engine import get_unified_creative_engine
                self._unified_engine = get_unified_creative_engine(self.event_bus)
                if self.event_bus and hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('unified_creative_engine', self._unified_engine)
            if self._unified_engine:
                logger.info("✅ Connected to UnifiedCreativeEngine")
        except Exception as e:
            logger.warning(f"Could not connect UnifiedCreativeEngine: {e}")
        
        # Unity components for auto-launch
        self._unity_hub_manager = None
        self._unity_mcp_tools = None
        
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                self._unity_runtime_bridge = self.event_bus.get_component('unity_runtime_bridge', silent=True)
                self._unity_hub_manager = self.event_bus.get_component('unity_hub_manager', silent=True)
                self._unity_mcp_tools = self.event_bus.get_component('unity_mcp_tools', silent=True)
            if self._unity_runtime_bridge is None:
                from core.unity_runtime_bridge import get_unity_runtime_bridge
                self._unity_runtime_bridge = get_unity_runtime_bridge(event_bus=self.event_bus)
                if self.event_bus and hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('unity_runtime_bridge', self._unity_runtime_bridge)
            if self._unity_hub_manager is None:
                from core.unity_mcp_integration import get_unity_hub_manager, get_unity_mcp_tools
                self._unity_hub_manager = get_unity_hub_manager(event_bus=self.event_bus)
                self._unity_mcp_tools = get_unity_mcp_tools(event_bus=self.event_bus)
            if self._unity_runtime_bridge:
                logger.info("✅ Connected to UnityRuntimeBridge")
                if not self._unity_runtime_bridge.is_connected():
                    if self.event_bus:
                        self.event_bus.publish("unity.runtime.connect", {})
                    self._unity_runtime_bridge.connect()
                self._update_unity_status()
                if not self._unity_runtime_bridge.is_connected():
                    if _unity_autolaunch_enabled():
                        logger.info("🚀 Unity not connected, will attempt auto-launch after 1s delay...")
                        import threading
                        threading.Timer(1.0, self._auto_launch_unity).start()
                    else:
                        logger.info("ℹ️ Unity auto-launch disabled in WSL; use manual launch button when needed")
                else:
                    logger.info("✅ Unity already connected")
        except Exception as e:
            logger.warning(f"Could not connect Unity components: {e}")
    
    def _connect_event_bus(self):
        """Subscribe to relevant EventBus topics."""
        if not self.event_bus:
            logger.error("❌ CreativeStudioWidget: No event_bus available, cannot subscribe to events")
            return
        
        try:
            # Listen for terrain sent events
            self.event_bus.subscribe("unity.terrain.sent", self._on_terrain_sent)
            # Listen for creation requests from other components (Ollama/brain can publish this)
            self.event_bus.subscribe("creative.create", self._on_create_request)
            # Voice commands publish creative.voice.create - treat same as creative.create
            self.event_bus.subscribe("creative.voice.create", self._on_creative_voice_create)
            # When engine renders a map image, display it
            self.event_bus.subscribe("creative.map.rendered", self._on_creative_map_rendered)
            # Real AI image from Kingdom AI Ollama Unified Brain (VisualCreationCanvas → visual.generated)
            # CRITICAL FIX: Use subscribe_sync for immediate synchronous handling on Qt main thread
            # This ensures UI updates happen immediately without thread dispatch delays
            # SOTA 2026 FIX: Subscribe once (prefer subscribe_sync for immediate Qt handling)
            sub = getattr(self.event_bus, 'subscribe_sync', None) or self.event_bus.subscribe
            sub("visual.generated", self._on_visual_generated)
            sub("visual.generation.error", self._on_visual_generation_error)
            sub("visual.generation.progress", self._on_visual_generation_progress)
            sub("visual.generation.started", self._on_visual_generation_started)
            logger.info("✅ CreativeStudioWidget subscribed to visual.generated + started + error + progress (LIVE PREVIEW)")
            # Listen for Unity connection status
            self.event_bus.subscribe("unity.runtime.connected", self._on_unity_connected)
            self.event_bus.subscribe("unity.runtime.disconnected", self._on_unity_disconnected)
            
            # SOTA 2026: Subscribe to KingdomAIBrain progress events for real-time feedback
            self.event_bus.subscribe("brain.progress", self._on_brain_progress)
            self.event_bus.subscribe("brain.error", self._on_brain_error)
            self.event_bus.subscribe("brain.metrics", self._on_brain_metrics)
            
            logger.info("✅ CreativeStudioWidget subscribed to EventBus + KingdomAIBrain")
        except Exception as e:
            logger.error(f"❌ Could not subscribe to EventBus: {e}", exc_info=True)
    
    def _on_terrain_sent(self, data: dict):
        """Handle terrain sent event."""
        self._add_chat_message("System", f"✅ Terrain '{data.get('name')}' sent to Unity!")
        self.terrain_sent.emit(data)
    
    def _on_create_request(self, data: dict):
        """Handle creation request from other components (Unified Ollama Brain / voice / chat)."""
        prompt = data.get("prompt", data.get("text", ""))
        if prompt:
            self._create_from_prompt(prompt, vision_payload=data if isinstance(data, dict) else None)
    
    def _on_creative_voice_create(self, data: dict):
        """Handle creative.voice.create from Voice Command Manager (Unified Ollama Brain)."""
        prompt = (data.get("parameters") or {}).get("prompt") or data.get("prompt") or data.get("text", "")
        if prompt:
            self._create_from_prompt(prompt, vision_payload=data if isinstance(data, dict) else None)
    
    def _on_creative_map_rendered(self, data: dict):
        """Display image when engine publishes creative.map.rendered."""
        image_path = data.get("image_path")
        if image_path and Path(image_path).exists():
            self._display_image(str(image_path))
            self._add_chat_message("System", "🖼️ Displayed on canvas!")
    
    def _on_visual_generated(self, data: dict):
        """Display real AI image from Kingdom AI Ollama Unified Brain (visual.request → brain.visual.request → VisualCreationCanvas).
        
        CRITICAL: This handler is called from EventBus, which dispatches via Qt dispatcher if needed
        for thread safety. The handler runs on Qt main thread, so UI updates are safe.
        """
        logger.info(f"🎨 _on_visual_generated called with data keys: {list(data.keys())}")
        logger.info(f"🎨 Full event data: {data}")
        
        # Get request_id and clear timeout
        request_id = data.get("request_id", "")
        if request_id and request_id in self._pending_visual_requests:
            # Cancel timeout timer
            pending = self._pending_visual_requests.pop(request_id)
            if HAS_PYQT6 and "timer" in pending:
                pending["timer"].stop()
            logger.info(f"✅ Visual generation completed for request {request_id}")
        if request_id:
            self._last_completed_visual_request_id = request_id
            if self._active_visual_request_id == request_id:
                self._active_visual_request_id = None
        
        # Prefer encoded video artifact when present, then fallback to image path.
        media_path = (
            data.get("video_path")
            or data.get("image_path")
            or data.get("path")
            or data.get("file_path")
            or data.get("image")
        )
        if not media_path:
            logger.error(f"❌ _on_visual_generated: no output path in data. Full data: {data}")
            self._add_chat_message("System", "❌ No output path in generation result")
            self.progress.setVisible(False)
            return
        
        # CRITICAL FIX: Convert to absolute path (VisualCreationCanvas saves to exports/creations/)
        try:
            media_path = str(Path(media_path).resolve())
            logger.info(f"🎨 Resolved media path: {media_path}")
        except Exception as e:
            logger.error(f"❌ _on_visual_generated: failed to resolve path {media_path}: {e}")
            self._add_chat_message("System", f"❌ Invalid output path: {media_path}")
            self.progress.setVisible(False)
            return
        
        if not Path(media_path).exists():
            logger.error(f"❌ _on_visual_generated: output file does not exist: {media_path}")
            self._add_chat_message("System", f"❌ Output file not found: {media_path}")
            self.progress.setVisible(False)
            return
        
        logger.info(f"✅ _on_visual_generated: Output file exists, displaying: {media_path}")
        
        # CRITICAL: Display image IMMEDIATELY for user to see
        self._display_image(media_path)
        
        # Update UI
        self._add_chat_message("System", "🖼️ Kingdom AI Brain output displayed on canvas!")
        self._add_chat_message("System", "✅ Generation finished (100%)")
        if hasattr(self, 'progress') and self.progress:
            self.progress.setValue(100)
            self.progress.setVisible(False)
        
        # Update canvas title
        if hasattr(self, 'canvas_title') and self.canvas_title:
            self.canvas_title.setText(f"🎨 Creation Canvas - {Path(media_path).name}")
        
        # Integration: publish a normalized creation output event so downstream systems
        # (e.g., Unity runtime bridge, exporters, logs) can react to completed creations.
        try:
            if self.event_bus:
                payload = dict(data) if isinstance(data, dict) else {"data": data}
                payload.setdefault("image_path", str(media_path))
                payload.setdefault("timestamp", time.time())
                self.event_bus.publish("creation.output", payload)
        except Exception:
            # Non-critical: creation is already displayed locally.
            pass
        
    
    def _on_visual_generation_started(self, data: dict):
        """Handle visual generation started event - update UI with feedback.
        
        SOTA 2026 FIX: This replaces "Waiting for Kingdom AI Brain to process..."
        with actual feedback that the brain received the request.
        """
        try:
            request_id = data.get("request_id", "")
            if request_id:
                if request_id == self._last_completed_visual_request_id:
                    logger.debug("Ignoring started event for completed request: %s", request_id)
                    return
                if request_id not in self._pending_visual_requests:
                    logger.debug("Ignoring started event for non-pending request: %s", request_id)
                    return
                self._active_visual_request_id = request_id

            message = data.get("message", "🧠 Kingdom AI Brain is processing...")
            prompt_preview = data.get("prompt", "")[:50]
            
            # Update status label
            self._add_chat_message("System", f"✅ {message}")
            if prompt_preview:
                self._add_chat_message("System", f"📝 Processing: \"{prompt_preview}...\"")
            
            # Update progress bar
            if hasattr(self, 'progress') and self.progress:
                self.progress.setValue(15)
                self.progress.setVisible(True)
            
            # Update canvas title
            if hasattr(self, 'canvas_title') and self.canvas_title:
                self.canvas_title.setText("🎨 Generating...")
            
            logger.info(f"✅ Creative Studio received generation.started confirmation")
        except Exception as e:
            logger.error(f"Error handling generation started: {e}")
    
    def _on_brain_progress(self, data: dict):
        """Handle KingdomAIBrain progress events for real-time queue/processing feedback.
        
        SOTA 2026: Shows users their request status in the brain's priority queue.
        """
        try:
            request_id = data.get("request_id", "")
            stage = data.get("stage", "")
            
            # Only show progress for creative domain requests
            if "creative" in request_id.lower() or data.get("domain") == "creative":
                if stage == "queued":
                    position = data.get("position", 0)
                    priority = data.get("priority", "NORMAL")
                    self._add_chat_message("System", f"📋 Request queued (position {position}, priority: {priority})")
                elif stage == "processing":
                    worker = data.get("worker", 0)
                    self._add_chat_message("System", f"🧠 Brain worker {worker} processing...")
                    if hasattr(self, 'progress') and self.progress:
                        self.progress.setValue(25)
        except Exception as e:
            logger.debug(f"Error handling brain progress: {e}")
    
    def _on_brain_error(self, data: dict):
        """Handle KingdomAIBrain error events."""
        try:
            request_id = data.get("request_id", "")
            error = data.get("error", "Unknown error")
            
            # Only show errors for creative requests
            if "creative" in request_id.lower():
                self._add_chat_message("System", f"❌ Brain error: {error}")
                if hasattr(self, 'progress') and self.progress:
                    self.progress.setVisible(False)
        except Exception as e:
            logger.debug(f"Error handling brain error: {e}")
    
    def _on_brain_metrics(self, data: dict):
        """Handle KingdomAIBrain metrics for status display (optional).
        
        SOTA 2026: Can show brain health in UI if needed.
        """
        # Optional: Update a status indicator with brain health
        pass
    
    def _on_visual_generation_progress(self, data: dict):
        """Handle live generation progress updates - ALWAYS show preview to user.
        
        CRITICAL: Preview images are REQUIRED - user must see live generation progress.
        This is called for EVERY progress update during generation.
        """
        try:
            request_id = data.get("request_id", "")
            if request_id:
                if request_id == self._last_completed_visual_request_id:
                    logger.debug("Ignoring progress for completed request: %s", request_id)
                    return
                if request_id not in self._pending_visual_requests:
                    logger.debug("Ignoring progress for non-pending request: %s", request_id)
                    return

            progress = data.get("progress", 0)
            preview_path = data.get("preview_path")  # Preview image file path
            
            # CRITICAL: Update progress bar - USER MUST SEE PROGRESS
            if hasattr(self, 'progress') and self.progress:
                self.progress.setValue(progress)
                self.progress.setVisible(True)
            
            # CRITICAL: Update canvas title with progress - USER MUST SEE STATUS
            if hasattr(self, 'canvas_title') and self.canvas_title:
                self.canvas_title.setText(f"🎨 Creating... {progress}%")
            
            # CRITICAL: ALWAYS display preview image if available - USER MUST SEE LIVE PREVIEW
            if preview_path and Path(preview_path).exists():
                logger.info(f"📊 Live preview update: {progress}% (preview: {Path(preview_path).name})")
                # Display live preview during generation - THIS IS THE LIVE PREVIEW USER SEES!
                self._display_image(preview_path)
                # Update status - show live progress
                status_msg = f"🎨 Generating... {progress}%"
                # Only update chat every 10% to avoid spam
                if progress % 10 == 0 or progress >= 95:
                    self._add_chat_message("System", status_msg)
            else:
                # Even without preview, update progress bar and title
                logger.debug(f"📊 Progress update: {progress}% (no preview image yet)")
            
        except Exception as e:
            logger.error(f"Progress update error: {e}", exc_info=True)
    
    def _on_visual_generation_error(self, data: dict):
        """Handle visual generation error from worker (diffusers/backends failed)."""
        err = data.get("error", "Unknown error")
        request_id = data.get("request_id", "")
        
        # Clear timeout if request was pending
        if request_id and request_id in self._pending_visual_requests:
            pending = self._pending_visual_requests.pop(request_id)
            if HAS_PYQT6 and "timer" in pending:
                pending["timer"].stop()
        
        self._add_chat_message("System", f"❌ Generation failed: {err[:80]}")
        if hasattr(self, 'progress') and self.progress:
            self.progress.setVisible(False)
        logger.warning(f"Creative Studio: visual.generation.error received: {err}")
        
        self._add_chat_message("System", "❌ Unified pipeline error received; no silent downgrade path")
        return
    
    def _handle_visual_timeout(self, request_id: str):
        """No-op: timeouts disabled. Let the real pipeline finish."""
        return

    def _handle_visual_final_timeout(self, request_id: str):
        """No-op: timeouts disabled. Let the real pipeline finish."""
        return
    
    def _create_from_prompt_fallback(self, prompt: str):
        """Disabled: no fallbacks. The real pipeline handles everything."""
        logger.info("_create_from_prompt_fallback called but disabled — real pipeline runs without timeout")
        return
    
    def _on_connect_unity_clicked(self):
        """Launch Unity Hub when user clicks button."""
        try:
            # Try to launch Unity Hub
            import subprocess
            import os
            if os.name == 'nt':
                # Windows - launch Unity Hub
                unity_hub_paths = [
                    r"C:\Program Files\Unity Hub\Unity Hub.exe",
                    r"C:\Program Files (x86)\Unity Hub\Unity Hub.exe",
                    os.path.expanduser(r"~\AppData\Local\Programs\Unity Hub\Unity Hub.exe"),
                ]
                launched = False
                for path in unity_hub_paths:
                    if os.path.exists(path):
                        subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        self._add_chat_message("System", "🚀 Launching Unity Hub...")
                        self._unity_hub_launched = True  # Track that Hub was launched
                        launched = True
                        break
                if not launched:
                    self._add_chat_message("System", "⚠️ Unity Hub not found. Install from https://unity.com/download")
            QTimer.singleShot(3000, self._update_unity_status)
        except Exception as e:
            logger.warning(f"Unity launch: {e}")
            self._add_chat_message("System", f"⚠️ Unity launch: {e}")
    
    def _create_procedural_fallback(self, prompt: str) -> Dict[str, Any]:
        """Generate a procedural image when engine succeeds but returns no image_path."""
        try:
            from PIL import Image, ImageDraw
            export_dir = Path(__file__).parent.parent / "exports" / "creations"
            export_dir.mkdir(parents=True, exist_ok=True)
            width, height = 512, 512
            img = Image.new("RGB", (width, height), color="#1a1a2e")
            draw = ImageDraw.Draw(img)
            import random
            random.seed(hash(prompt) % (2**32))
            for _ in range(40):
                x1, y1 = random.randint(0, width - 80), random.randint(0, height - 80)
                x2, y2 = x1 + random.randint(20, 100), y1 + random.randint(20, 100)
                color = (random.randint(50, 200), random.randint(100, 255), random.randint(100, 200))
                draw.rectangle([x1, y1, x2, y2], fill=color, outline=(100, 150, 200))
            title = (prompt[:35] + "...") if len(prompt) > 35 else prompt
            draw.text((20, 20), title, fill="white")
            filename = f"creation_{int(time.time())}.png"
            filepath = export_dir / filename
            img.save(str(filepath))
            cid = filename.replace(".png", "")
            self._current_creation = cid
            return {"success": True, "image_path": str(filepath), "id": cid}
        except Exception as e:
            logger.debug(f"Procedural fallback failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_unity_status(self):
        """Update Unity connection status."""
        if self._unity_runtime_bridge:
            # Re-check Unity status
            if hasattr(self._unity_runtime_bridge, 'check_unity_running'):
                self._unity_runtime_bridge.check_unity_running()
            
            if self._unity_runtime_bridge.is_connected():
                self.unity_status.setText("Unity: Connected")
                self.unity_status.setStyleSheet("color: #00ff88;")
                if hasattr(self, "unity_connect_btn"):
                    self.unity_connect_btn.setText("✅ Connected")
                    self.unity_connect_btn.setEnabled(False)
            elif getattr(self, '_unity_hub_launched', False):
                # Unity Hub was launched but Editor not connected yet
                self.unity_status.setText("Unity Hub: Started (open project to connect)")
                self.unity_status.setStyleSheet("color: #88ff88;")
                if hasattr(self, "unity_connect_btn"):
                    self.unity_connect_btn.setText("Open Project")
                    self.unity_connect_btn.setEnabled(True)
            else:
                self.unity_status.setText("Unity: Not running")
                self.unity_status.setStyleSheet("color: #ffaa00;")
                if hasattr(self, "unity_connect_btn"):
                    self.unity_connect_btn.setText("Start Unity Hub")
                    self.unity_connect_btn.setEnabled(True)
        else:
            self.unity_status.setText("Unity: Not configured")
            self.unity_status.setStyleSheet("color: #888;")
            if hasattr(self, "unity_connect_btn"):
                self.unity_connect_btn.setText("Configure Unity")
    
    def _on_unity_connected(self, data: dict):
        """Handle Unity connected event."""
        self._update_unity_status()
    
    def _on_unity_disconnected(self, data: dict):
        """Handle Unity disconnected event."""
        self._update_unity_status()
    
    def _check_ollama(self):
        """Check Ollama connection. Uses WSL-aware URL (Ollama brain first).
        
        In WSL2, Ollama runs at localhost:11434.
        """
        try:
            import requests
            try:
                from core.ollama_gateway import get_ollama_url
                base = get_ollama_url()
            except ImportError:
                try:
                    from core.ollama_config import get_ollama_base_url
                    base = get_ollama_base_url().rstrip("/")
                except Exception:
                    base = "http://localhost:11434"
            
            logger.info(f"🔍 Checking Ollama at {base}...")
            resp = requests.get(f"{base}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                self._ollama_connected = True
                self.ollama_status.setText(f"🟢 Ollama: {len(models)} models")
                self.ollama_status.setStyleSheet("color: #00ff88;")
                logger.info(f"✅ Ollama connected with {len(models)} models at {base}")
            else:
                self._ollama_connected = False
                self.ollama_status.setText("🔴 Ollama: Not responding")
                self.ollama_status.setStyleSheet("color: #ff4444;")
                logger.warning(f"⚠️ Ollama not responding (HTTP {resp.status_code})")
        except requests.exceptions.ConnectionError:
            self._ollama_connected = False
            self.ollama_status.setText("🔴 Ollama: Not running")
            self.ollama_status.setStyleSheet("color: #ff4444;")
            logger.warning("⚠️ Ollama not running - start with 'ollama serve'")
        except requests.exceptions.Timeout:
            self._ollama_connected = False
            self.ollama_status.setText("🔴 Ollama: Timeout")
            self.ollama_status.setStyleSheet("color: #ff4444;")
            logger.warning("⚠️ Ollama connection timeout")
        except Exception as e:
            self._ollama_connected = False
            self.ollama_status.setText("🔴 Ollama: Offline")
            self.ollama_status.setStyleSheet("color: #ff4444;")
            logger.warning(f"⚠️ Ollama offline: {e}")
    
    def _add_chat_message(self, sender: str, message: str):
        """Add message to chat display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = "#00ff88" if sender == "AI" else "#88ccff" if sender == "You" else "#888"
        self.chat_display.append(f'<span style="color: {color};">[{timestamp}] {sender}:</span> {message}')
        self.status_updated.emit(f"{sender}: {message}")

    def _publish_visual_request_with_retry(
        self,
        request_payload: Dict[str, Any],
        max_attempts: int = 4,
        base_delay_s: float = 0.2,
    ) -> bool:
        """Publish visual.request with startup-contention retry."""
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            bus = getattr(self, "event_bus", None)
            if bus is None:
                last_error = RuntimeError("EventBus not ready")
            else:
                try:
                    bus.publish("visual.request", request_payload)
                    logger.info(
                        "🎨 CreativeStudioWidget visual.request published (attempt %d/%d): %s...",
                        attempt,
                        max_attempts,
                        str(request_payload.get("prompt", ""))[:50],
                    )
                    return True
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "⚠️ CreativeStudioWidget publish attempt %d/%d failed: %s",
                        attempt,
                        max_attempts,
                        e,
                    )
            if attempt < max_attempts:
                time.sleep(base_delay_s * attempt)
        logger.error("❌ CreativeStudioWidget visual.request publish failed after retries: %s", last_error)
        return False
    
    def _on_chat_send(self):
        """Handle chat message send.

        Routes through UnifiedCreationOrchestrator so every registered creation
        engine is reachable via natural language, then continues the existing
        visual pipeline for live canvas feedback.
        """
        text = self.chat_input.text().strip()
        if not text:
            return

        self.chat_input.clear()
        self._add_chat_message("You", text)

        text_lower = text.lower()

        # Immediate UI side-effects
        if "unity" in text_lower and ("send" in text_lower or "runtime" in text_lower):
            self._send_terrain_to_unity_runtime()
            return
        if "export" in text_lower and "unity" in text_lower:
            self._export_to_unity()
            return

        # Route through the unified NL orchestrator (covers every engine)
        try:
            from core.unified_creation_orchestrator import (
                get_unified_creation_orchestrator,
            )
            uco = get_unified_creation_orchestrator(event_bus=self.event_bus)
            outcome = uco.handle_natural_language(text)
            if outcome and outcome.success:
                self._add_chat_message(
                    "System",
                    f"🧠 Routed to {outcome.primary}  "
                    f"({outcome.execution_time:.1f}s)"
                )
            else:
                errs = (outcome.errors[0] if outcome and outcome.errors
                        else "no engine satisfied the request")
                self._add_chat_message("System", f"⚠️ {errs}")
        except Exception as e:
            logger.debug("UnifiedCreationOrchestrator unavailable: %s", e)

        # Keep the existing canvas pipeline running for visual feedback
        if any(w in text_lower for w in ["create", "generate", "make", "build"]):
            self._create_from_prompt(text)
        elif any(w in text_lower for w in ["add", "remove", "edit", "change"]):
            self._edit_from_prompt(text)
        else:
            self._create_from_prompt(text)

    def _create_from_prompt(self, prompt: str, vision_payload: Optional[Dict[str, Any]] = None):
        """Route prompt through unified brain flow used by runtime Creative Studio."""
        self._add_chat_message("System", f"🎨 Creating: {prompt[:50]}...")
        if hasattr(self, "progress") and self.progress:
            self.progress.setVisible(True)
            self.progress.setValue(5)

        prompt_lower = prompt.lower()
        force_all_engines = any(
            key in prompt_lower
            for key in (
                "all engines",
                "all engine libraries",
                "unified multi engine",
                "system wide unified",
                "force orchestrator",
            )
        )
        if self.event_bus:
            try:
                request_payload: Dict[str, Any] = {
                    "prompt": prompt,
                    "mode": "image",
                    "timestamp": time.time(),
                    "source": "CreativeStudioWidget",
                    "request_id": f"creative_studio_{int(time.time() * 1000)}",
                    "force_orchestrator": force_all_engines,
                    "use_all_engine_libraries": force_all_engines,
                    "system_wide_unified_context": force_all_engines,
                    "engine_scope": "all" if force_all_engines else "auto",
                    "pipeline": "unified_multi_engine" if force_all_engines else "auto",
                    "orchestration_policy": "all_engines_primary" if force_all_engines else "auto",
                }
                if isinstance(vision_payload, dict):
                    images = vision_payload.get("images")
                    if isinstance(images, list) and images:
                        request_payload["images"] = images
                    for key in (
                        "vision_source",
                        "vision_frame_age_s",
                        "vision_context",
                        "vision_sources_available",
                        "vision_source_preference",
                    ):
                        if key in vision_payload:
                            request_payload[key] = vision_payload.get(key)

                if any(word in prompt_lower for word in ["animate", "animation", "video", "movie", "cinematic", "moving", "motion"]):
                    request_payload["mode"] = "video"

                request_id = request_payload["request_id"]
                dispatched = self._publish_visual_request_with_retry(request_payload)
                if not dispatched:
                    raise RuntimeError("visual.request dispatch failed after retries")
                logger.info(
                    "🎨 CreativeStudioWidget published visual.request → BrainRouter → VisualCreationCanvas: %s...",
                    prompt[:50],
                )
                self._add_chat_message("System", "🧠 Processing through Kingdom AI Brain...")
                if hasattr(self, "progress") and self.progress:
                    self.progress.setValue(15)

                self._pending_visual_requests[request_id] = {
                    "prompt": prompt,
                    "timestamp": time.time(),
                }
                self._active_visual_request_id = request_id
                return
            except Exception as e:
                logger.error("CreativeStudioWidget brain publish failed: %s", e, exc_info=True)
                self._add_chat_message("System", f"❌ Brain routing failed: {e}")
                if hasattr(self, "progress") and self.progress:
                    self.progress.setVisible(False)
                return

        # Event bus unavailable or publish failed.
        self._add_chat_message("System", "❌ EventBus unavailable for unified pipeline dispatch")
        if hasattr(self, "progress") and self.progress:
            self.progress.setVisible(False)
        return
    
    def _quick_create(self, prompt: str):
        """Quick creation from button."""
        self.chat_input.setText(prompt)
        self._on_chat_send()
    
    def _edit_from_prompt(self, prompt: str):
        """Edit current creation."""
        if not self._current_creation:
            self._add_chat_message("System", "⚠️ Create something first!")
            return
        
        if not self._unified_engine:
            self._add_chat_message("System", "❌ Engine not available")
            return
        
        self._add_chat_message("System", f"✏️ Editing...")
        result = self._unified_engine.edit_live(str(self._current_creation), prompt)
        
        if result.get("success"):
            self._add_chat_message("System", f"✅ Applied edits")
            render_result = self._unified_engine.render_map_to_image(str(self._current_creation), show=False)
            if render_result.get("success"):
                self._display_image(str(render_result.get("image_path", "")))
        else:
            self._add_chat_message("System", f"❌ Edit failed")

    def _display_video(self, video_path: str):
        """Display encoded video on the canvas QLabel using OpenCV frame-by-frame rendering.

        QMediaPlayer + QVideoWidget requires GPU-accelerated compositing which is
        unavailable under WSL2 / X11-forwarded sessions, resulting in a black widget.
        This method reads frames with cv2.VideoCapture and paints them as QPixmaps
        onto the existing *self.canvas* QLabel via a QTimer, which works everywhere.
        """
        try:
            import cv2
        except ImportError:
            raise RuntimeError("OpenCV (cv2) is required for video playback")

        # Stop any previous playback resources.
        self._stop_cv_playback()
        if self._active_movie is not None:
            try:
                self._active_movie.stop()
            except Exception:
                pass
            self._active_movie = None
        if self._media_player is not None:
            try:
                self._media_player.stop()
            except Exception:
                pass

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"cv2.VideoCapture failed to open: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 24
        interval_ms = max(int(1000 / fps), 1)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Store on self so the timer callback can access them.
        self._cv_cap = cap
        self._cv_video_path = video_path
        self._cv_loop = True

        # Ensure the canvas (QLabel) is the visible widget in the stack.
        if self._canvas_stack is not None:
            self._canvas_stack.setCurrentWidget(self.canvas)

        # Create a QTimer to drive frame rendering.
        self._cv_timer = QTimer(self)
        self._cv_timer.setInterval(interval_ms)
        self._cv_timer.timeout.connect(self._cv_frame_tick)
        self._cv_timer.start()

        if hasattr(self, 'canvas_title') and self.canvas_title:
            self.canvas_title.setText(f"🎬 Creation Canvas - {Path(video_path).name}")
        if hasattr(self, 'creation_info') and self.creation_info:
            self.creation_info.setText(f"Video playback ({total_frames} frames @ {int(fps)} fps, looping)")

        logger.info(f"✅ CV2 video playback started on canvas: {video_path} ({total_frames} frames @ {int(fps)} fps)")

    def _cv_frame_tick(self):
        """Read the next frame from the OpenCV capture and paint it on the canvas."""
        try:
            import cv2
            cap = getattr(self, '_cv_cap', None)
            if cap is None or not cap.isOpened():
                self._stop_cv_playback()
                return

            ret, frame = cap.read()
            if not ret:
                if getattr(self, '_cv_loop', True):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                if not ret:
                    self._stop_cv_playback()
                    return

            # BGR → RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w

            from PyQt6.QtGui import QImage, QPixmap
            from PyQt6.QtCore import Qt
            qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            # Scale to canvas size keeping aspect ratio.
            canvas_size = self.canvas.size()
            if canvas_size.width() > 0 and canvas_size.height() > 0:
                pixmap = pixmap.scaled(
                    canvas_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self.canvas.setPixmap(pixmap)
        except Exception as exc:
            logger.error(f"CV2 frame tick error: {exc}")
            self._stop_cv_playback()

    def _stop_cv_playback(self):
        """Release OpenCV capture and stop the frame timer."""
        timer = getattr(self, '_cv_timer', None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
            self._cv_timer = None
        cap = getattr(self, '_cv_cap', None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
            self._cv_cap = None

    def _on_media_status_changed(self, status):
        """Fallback loop behavior for backends that ignore setLoops()."""
        try:
            if self._media_player is None:
                return
            end_status = getattr(QMediaPlayer.MediaStatus, "EndOfMedia", None)
            if end_status is not None and status == end_status:
                self._media_player.setPosition(0)
                self._media_player.play()
        except Exception:
            pass
    
    def _display_image(self, image_path: str):
        """Display image on canvas - RUNTIME GUI DISPLAY FOR USER."""
        logger.info(f"🎨 _display_image called with: {image_path}")
        # Stop any running CV2 video playback before switching to a new asset.
        self._stop_cv_playback()
        if not image_path:
            logger.warning("_display_image called with empty image_path")
            return
        if not Path(image_path).exists():
            logger.error(f"_display_image: file does not exist: {image_path}")
            self._add_chat_message("System", f"❌ Image file not found: {image_path}")
            return
        if not hasattr(self, 'canvas') or self.canvas is None:
            logger.error("_display_image: canvas widget does not exist")
            self._add_chat_message("System", "❌ Canvas widget not initialized")
            return
        
        # CRITICAL: Ensure canvas widget is visible and properly sized FOR USER TO SEE
        if not self.canvas.isVisible():
            logger.warning("Canvas was not visible, making it visible now")
            self.canvas.setVisible(True)
            self.canvas.show()  # Force show
        
        # CRITICAL: Ensure canvas parent is visible (tab might be hidden)
        parent = self.canvas.parent()
        while parent:
            if hasattr(parent, 'isVisible') and not parent.isVisible():
                logger.warning(f"Canvas parent {type(parent).__name__} is not visible - user may not see image!")
                # Try to make parent visible if it's a widget
                if hasattr(parent, 'show'):
                    parent.show()
            parent = getattr(parent, 'parent', None)
        
        # CRITICAL: Get canvas size BEFORE any operations - ensure it's visible to user
        canvas_size = self.canvas.size()
        logger.info(f"Canvas size: {canvas_size.width()}x{canvas_size.height()}")
        
        # If canvas not yet sized, use minimum size or default (USER MUST SEE IT)
        if canvas_size.width() <= 0 or canvas_size.height() <= 0:
            min_w = max(self.canvas.minimumWidth(), 800)  # Larger default for visibility
            min_h = max(self.canvas.minimumHeight(), 600)
            canvas_size = QSize(min_w, min_h)
            logger.info(f"Using default canvas size: {canvas_size.width()}x{canvas_size.height()}")
            # CRITICAL: Resize canvas if it has no size - USER MUST SEE IT
            try:
                self.canvas.resize(canvas_size)
                self.canvas.setMinimumSize(min_w, min_h)
            except Exception as e:
                logger.debug(f"Could not resize canvas: {e}")
        
        try:
            suffix = Path(image_path).suffix.lower()
            if suffix in (".mp4", ".mov", ".webm", ".mkv", ".avi"):
                try:
                    self._display_video(image_path)
                    self.canvas.repaint()
                    self.canvas.update()
                    return
                except Exception as e:
                    logger.warning(f"Video playback path unavailable, falling back to thumbnail mode: {e}")

            # Animated GIF path: use QMovie so motion renders on the Studio canvas.
            if suffix == ".gif" and HAS_PYQT6:
                if self._media_player is not None:
                    try:
                        self._media_player.stop()
                    except Exception:
                        pass
                if self._active_movie is not None:
                    try:
                        self._active_movie.stop()
                    except Exception:
                        pass
                    self._active_movie = None

                actual_size = self.canvas.size()
                if actual_size.width() <= 0 or actual_size.height() <= 0:
                    actual_size = canvas_size

                movie = QMovie(image_path)
                if movie.isValid():
                    movie.setScaledSize(actual_size)
                    self.canvas.clear()
                    self.canvas.setMovie(movie)
                    self._active_movie = movie
                    if self._canvas_stack is not None:
                        self._canvas_stack.setCurrentWidget(self.canvas)
                    movie.start()
                    if hasattr(self, 'canvas_title') and self.canvas_title:
                        self.canvas_title.setText(f"🎬 Creation Canvas - {Path(image_path).name}")
                    if hasattr(self, 'creation_info') and self.creation_info:
                        self.creation_info.setText("Animated GIF playback")
                    self.canvas.repaint()
                    self.canvas.update()
                    logger.info(f"✅ Animated GIF playback started on canvas: {image_path}")
                    return
                logger.warning(f"GIF was invalid for QMovie, falling back to static pixmap: {image_path}")

            # Static image path: ensure previous movie is stopped.
            if self._media_player is not None:
                try:
                    self._media_player.stop()
                except Exception:
                    pass
            if self._active_movie is not None:
                try:
                    self._active_movie.stop()
                except Exception:
                    pass
                self._active_movie = None
            if self._canvas_stack is not None:
                self._canvas_stack.setCurrentWidget(self.canvas)

            # Load pixmap
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                logger.error(f"_display_image: failed to load pixmap from {image_path}")
                self._add_chat_message("System", f"❌ Failed to load image: {image_path}")
                return
            
            logger.info(f"Loaded pixmap: {pixmap.width()}x{pixmap.height()}")
            
            # CRITICAL: Scale pixmap to fit canvas while maintaining aspect ratio
            # Use actual canvas size, not minimum size
            actual_size = self.canvas.size()
            if actual_size.width() <= 0 or actual_size.height() <= 0:
                actual_size = canvas_size
            scaled = pixmap.scaled(
                actual_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            logger.info(f"Scaled pixmap: {scaled.width()}x{scaled.height()} for canvas {actual_size.width()}x{actual_size.height()}")
            
            # CRITICAL: Clear text and set pixmap - USER MUST SEE THIS
            self.canvas.clear()  # This clears both text AND previous pixmap
            self.canvas.setPixmap(scaled)
            # CRITICAL: Ensure QLabel is in pixmap mode (not text mode)
            self.canvas.setScaledContents(False)  # We handle scaling ourselves
            
            # CRITICAL: Ensure canvas is enabled and visible - USER MUST SEE IT
            self.canvas.setEnabled(True)
            self.canvas.setVisible(True)
            self.canvas.show()  # Force show
            
            # CRITICAL: Update canvas title to show image info
            if hasattr(self, 'canvas_title') and self.canvas_title:
                self.canvas_title.setText(f"🎨 Creation Canvas - {Path(image_path).name} ({pixmap.width()}×{pixmap.height()})")
            
            # CRITICAL: PyQt6 best practice - repaint() directly on label, not parent
            # This is the KEY fix from web research - must call repaint() on the label itself
            self.canvas.repaint()  # CRITICAL: Direct repaint on label, not parent widget
            self.canvas.update()   # Also call update for good measure
            
            
            # Update info label
            if hasattr(self, 'creation_info') and self.creation_info:
                self.creation_info.setText(f"Size: {pixmap.width()}x{pixmap.height()}")
            
            # Track last displayed image for visual tests
            self._last_displayed_image = image_path
            
            logger.info(f"✅ Image displayed on canvas: {image_path} - USER SHOULD SEE IT NOW")
            self._add_chat_message("System", f"✅ Image displayed: {Path(image_path).name}")
            
            # SOTA 2026: Ensure canvas is visible and focused - USER MUST SEE IT
            self.canvas.setVisible(True)
            self.canvas.raise_()  # Bring to front
            self.canvas.update()
            
        except Exception as e:
            logger.error(f"_display_image error: {e}", exc_info=True)
            self._add_chat_message("System", f"❌ Display error: {e}")
    
    def _save_creation(self):
        """Save current creation."""
        if not self._current_creation:
            self._add_chat_message("System", "⚠️ Nothing to save")
            return
        
        export_dir = Path(__file__).parent.parent / "exports" / "creations"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"creation_{self._current_creation}_{int(time.time())}.png"
        filepath = export_dir / filename
        
        pixmap = self.canvas.pixmap()
        if pixmap:
            pixmap.save(str(filepath))
            self._add_chat_message("System", f"💾 Saved: {filepath.name}")
    
    def _export_to_unity(self):
        """Export to Unity files."""
        if not self._current_creation or not self._unified_engine:
            self._add_chat_message("System", "⚠️ Nothing to export")
            return
        
        self._add_chat_message("System", "📤 Exporting to Unity...")
        result = self._unified_engine.export_to_unity(str(self._current_creation))
        
        if result.get("success"):
            self._add_chat_message("System", "✅ Exported to Unity!")
        else:
            self._add_chat_message("System", f"❌ Export failed: {result.get('error')}")
    
    def _send_terrain_to_unity_runtime(self):
        """Send terrain to running Unity instance."""
        if not self._current_creation:
            self._add_chat_message("System", "⚠️ Nothing to send")
            return
        
        if not self._unified_engine:
            self._add_chat_message("System", "❌ Engine not available")
            return
        
        self._add_chat_message("System", "🎮 Sending terrain to Unity runtime...")
        
        try:
            result = self._unified_engine.send_terrain_to_unity_runtime(str(self._current_creation))
        except Exception as e:
            result = {"success": False, "error": str(e)}
        
        if result.get("success"):
            sent_to = result.get("sent_to", "Unity")
            heightmap = "with heightmap" if result.get("heightmap_included") else "metadata only"
            self._add_chat_message("System", f"✅ Sent to {sent_to} ({heightmap})")
            self._update_unity_status()
        else:
            self._add_chat_message("System", f"❌ Send failed: {result.get('error')}")
    
    def _clear_canvas(self):
        """Clear canvas."""
        if self._active_movie is not None:
            try:
                self._active_movie.stop()
            except Exception:
                pass
            self._active_movie = None
        self.canvas.clear()
        self.canvas.setText("Ready for creation...")
        self._current_creation = None
        self._add_chat_message("System", "🗑️ Cleared")
    
    def _create_unity_project(self):
        """SOTA 2026: Create a new Unity project with GUI - no more CLI required!"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QFileDialog, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New Unity Project")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)
        
        # Project name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Project Name:"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("MyAwesomeGame")
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)
        
        # Project path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Location:"))
        path_input = QLineEdit()
        path_input.setPlaceholderText("C:/UnityProjects")
        path_layout.addWidget(path_input)
        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(lambda: path_input.setText(
            QFileDialog.getExistingDirectory(dialog, "Select Project Location")
        ))
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        # Template selection
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Template:"))
        template_combo = QComboBox()
        template_combo.addItems([
            "3D (Core)",
            "2D (Core)", 
            "3D (URP)",
            "2D (URP)",
            "3D (HDRP)",
            "VR Core",
            "AR Core",
            "Empty"
        ])
        template_layout.addWidget(template_combo)
        layout.addLayout(template_layout)
        
        # Template mapping
        template_map = {
            "3D (Core)": "3d-core",
            "2D (Core)": "2d-core",
            "3D (URP)": "3d-urp",
            "2D (URP)": "2d-urp",
            "3D (HDRP)": "3d-hdrp",
            "VR Core": "vr-core",
            "AR Core": "ar-core",
            "Empty": "empty"
        }
        
        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            project_name = name_input.text().strip() or "NewUnityProject"
            project_path = path_input.text().strip() or "C:/UnityProjects"
            template = template_map.get(template_combo.currentText(), "3d-core")
            
            self._add_chat_message("System", f"📁 Creating Unity project: {project_name}...")
            
            try:
                # Use Unity MCP Tools if available
                if self._unity_mcp_tools:
                    result = self._unity_mcp_tools.execute_tool("unity_create_project", {
                        "name": project_name,
                        "path": project_path,
                        "template": template
                    })
                    
                    if result.get("success"):
                        self._add_chat_message("System", f"✅ Unity project '{project_name}' created at {project_path}")
                    else:
                        self._add_chat_message("System", f"❌ Failed: {result.get('error')}")
                else:
                    self._add_chat_message("System", "⚠️ Unity MCP Tools not available. Open MCP Control Center to access full Unity controls.")
            except Exception as e:
                self._add_chat_message("System", f"❌ Error: {e}")
    
    def _build_unity_project(self):
        """SOTA 2026: Build Unity project with GUI - no more CLI required!"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QFileDialog, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Build Unity Project")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)
        
        # Project path
        project_layout = QHBoxLayout()
        project_layout.addWidget(QLabel("Project:"))
        project_input = QLineEdit()
        project_input.setPlaceholderText("C:/UnityProjects/MyGame")
        project_layout.addWidget(project_input)
        browse_project_btn = QPushButton("📁 Browse")
        browse_project_btn.clicked.connect(lambda: project_input.setText(
            QFileDialog.getExistingDirectory(dialog, "Select Unity Project")
        ))
        project_layout.addWidget(browse_project_btn)
        layout.addLayout(project_layout)
        
        # Output path
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output:"))
        output_input = QLineEdit()
        output_input.setPlaceholderText("C:/Builds/MyGame")
        output_layout.addWidget(output_input)
        browse_output_btn = QPushButton("📁 Browse")
        browse_output_btn.clicked.connect(lambda: output_input.setText(
            QFileDialog.getExistingDirectory(dialog, "Select Build Output Location")
        ))
        output_layout.addWidget(browse_output_btn)
        layout.addLayout(output_layout)
        
        # Target platform
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Platform:"))
        target_combo = QComboBox()
        target_combo.addItems([
            "Windows 64-bit",
            "Windows 32-bit",
            "macOS",
            "Linux",
            "Android",
            "iOS",
            "WebGL",
            "PlayStation 5",
            "Xbox Series"
        ])
        target_layout.addWidget(target_combo)
        layout.addLayout(target_layout)
        
        # Target mapping
        target_map = {
            "Windows 64-bit": "StandaloneWindows64",
            "Windows 32-bit": "StandaloneWindows",
            "macOS": "StandaloneOSX",
            "Linux": "StandaloneLinux64",
            "Android": "Android",
            "iOS": "iOS",
            "WebGL": "WebGL",
            "PlayStation 5": "PS5",
            "Xbox Series": "XboxOne"
        }
        
        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            project_path = project_input.text().strip()
            output_path = output_input.text().strip()
            target = target_map.get(target_combo.currentText(), "StandaloneWindows64")
            
            if not project_path:
                self._add_chat_message("System", "⚠️ Please specify a project path")
                return
            
            self._add_chat_message("System", f"🏗️ Building project for {target_combo.currentText()}...")
            
            try:
                # Use Unity MCP Tools if available
                if self._unity_mcp_tools:
                    result = self._unity_mcp_tools.execute_tool("unity_build_project", {
                        "project_path": project_path,
                        "output_path": output_path or f"{project_path}/Builds",
                        "target": target
                    })
                    
                    if result.get("success"):
                        self._add_chat_message("System", f"✅ Build complete! Output: {output_path or 'project/Builds'}")
                    else:
                        self._add_chat_message("System", f"❌ Build failed: {result.get('error')}")
                else:
                    self._add_chat_message("System", "⚠️ Unity MCP Tools not available. Open MCP Control Center to access full Unity controls.")
            except Exception as e:
                self._add_chat_message("System", f"❌ Error: {e}")
    
    def _auto_launch_unity(self):
        """Auto-launch Unity using MCP control."""
        try:
            # Try to launch Unity Hub first
            if self._unity_hub_manager:
                logger.info("🚀 Auto-launching Unity Hub...")
                result = self._unity_hub_manager.launch_hub()
                if result.get('success'):
                    logger.info("✅ Unity Hub launched successfully")
                    self._unity_hub_launched = True  # Track that Hub was launched
                    self._add_chat_message("System", "🎮 Unity Hub launched - ready for projects")
                    # Update status after a delay to reflect the launch
                    QTimer.singleShot(1000, self._update_unity_status)
                else:
                    logger.warning(f"Could not launch Unity Hub: {result.get('error')}")
            else:
                logger.info("Unity Hub Manager not available, trying direct connection...")
                # Just try to connect to Unity if it's already running
                if self._unity_runtime_bridge:
                    self._unity_runtime_bridge.connect()
        except Exception as e:
            logger.warning(f"Could not auto-launch Unity: {e}")
    
    def _update_display(self):
        """Update display timer callback - SOTA 2026 real-time UI refresh."""
        try:
            # Update generation progress if active
            if hasattr(self, '_current_generation') and self._current_generation:
                progress = self._current_generation.get('progress', 0)
                if hasattr(self, '_progress_bar'):
                    self._progress_bar.setValue(int(progress))
            
            # Update preview if new content available
            if hasattr(self, '_pending_preview') and self._pending_preview:
                preview_data = self._pending_preview
                self._pending_preview = None
                
                if hasattr(self, '_preview_label') and preview_data:
                    # Update preview widget with new image/content
                    if self.event_bus:
                        self.event_bus.publish("creative.preview.updated", {
                            "preview_type": preview_data.get("type", "image"),
                            "timestamp": time.time()
                        })
            
            # Update status indicators
            if hasattr(self, '_status_label'):
                status_text = "Ready"
                if hasattr(self, '_is_generating') and self._is_generating:
                    status_text = "Generating..."
                elif hasattr(self, '_last_error') and self._last_error:
                    status_text = f"Error: {self._last_error}"
                self._status_label.setText(status_text)
            
            # Refresh memory/resource usage display
            if hasattr(self, '_memory_label'):
                try:
                    import psutil
                    mem = psutil.Process().memory_info().rss / (1024 * 1024)
                    self._memory_label.setText(f"Memory: {mem:.0f} MB")
                except Exception:
                    pass
                    
        except Exception as e:
            # Display updates should never crash the UI
            logger.debug(f"Display update error: {e}")
    
    def cleanup(self):
        """Cleanup resources."""
        self._stop_cv_playback()
        self._update_timer.stop()
        if hasattr(self, '_webcam_thread') and self._webcam_thread:
            self._webcam_thread.stop()


def get_creative_studio_widget(event_bus=None, parent=None) -> Optional['CreativeStudioWidget']:
    """Factory function to get the CreativeStudioWidget."""
    if not HAS_PYQT6:
        logger.error("PyQt6 required for CreativeStudioWidget")
        return None
    return CreativeStudioWidget(event_bus=event_bus, parent=parent)


def launch_creative_studio(event_bus=None):
    """Launch the Real-Time Creative Studio (standalone)."""
    import sys
    
    if not HAS_PYQT6:
        logger.error("PyQt6 required for Creative Studio")
        return None
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    studio = RealtimeCreativeStudio(event_bus)
    studio.show()
    
    return app.exec()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print(" KINGDOM AI - REAL-TIME CREATIVE STUDIO (SOTA 2026) ".center(70))
    print("="*70 + "\n")
    
    launch_creative_studio()
