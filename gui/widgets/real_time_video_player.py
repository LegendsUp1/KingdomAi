"""
SOTA 2026 Real-Time Video Player Widget
Implements QMediaPlayer + QVideoSink architecture for continuous video playback
with AI frame processing integration and memory-efficient frame buffering.
"""

import logging
import collections
from pathlib import Path
from typing import Optional, Callable, Deque

logger = logging.getLogger("KingdomAI.RealTimeVideoPlayer")

# PyQt6 imports with graceful fallback
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QSlider, QStyle, QSizePolicy, QStackedWidget
    )
    from PyQt6.QtCore import (
        Qt, QUrl, QTimer, pyqtSignal, pyqtSlot, QSize
    )
    from PyQt6.QtGui import QImage, QPixmap
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False
    QWidget = object
    pyqtSignal = lambda *args: None

# PyQt6 Multimedia imports
try:
    from PyQt6.QtMultimedia import QMediaPlayer, QVideoSink, QVideoFrame, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAS_MULTIMEDIA = True
except ImportError:
    HAS_MULTIMEDIA = False
    QMediaPlayer = None
    QVideoSink = None
    QVideoFrame = type("QVideoFrame", (), {})  # Dummy class for decorator compatibility
    QAudioOutput = None
    QVideoWidget = None

# OpenCV for fallback frame extraction
try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    cv2 = None
    np = None


class FrameBuffer:
    """Memory-efficient frame buffer with automatic cleanup.
    
    SOTA 2026: Minimal buffer (max 3 frames) to prevent memory buildup.
    """
    
    def __init__(self, max_frames: int = 3):
        self.max_frames = max_frames
        self._frame_queue: Deque = collections.deque(maxlen=max_frames)
        self._timestamps: Deque[float] = collections.deque(maxlen=max_frames)
    
    def add_frame(self, frame, timestamp: float = 0.0):
        """Add frame with automatic cleanup of oldest frames."""
        # Deque automatically removes oldest when maxlen is exceeded
        self._frame_queue.append(frame)
        self._timestamps.append(timestamp)
    
    def get_latest(self):
        """Get the most recent frame."""
        if self._frame_queue:
            return self._frame_queue[-1]
        return None
    
    def clear(self):
        """Clear all frames and release memory."""
        self._frame_queue.clear()
        self._timestamps.clear()
    
    def __len__(self):
        return len(self._frame_queue)


class RealTimeVideoPlayer(QWidget if HAS_PYQT6 else object):
    """SOTA 2026 Real-Time Video Player with QMediaPlayer and QVideoSink.
    
    Features:
    - Hardware-accelerated video playback via QVideoWidget
    - Frame-by-frame access via QVideoSink for AI processing
    - Memory-efficient frame buffer (max 3 frames)
    - Playback controls (play/pause/stop/seek)
    - Event bus integration for frame publishing
    - Graceful fallback to OpenCV when QtMultimedia unavailable
    """
    
    if HAS_PYQT6:
        # Signals for external integration
        playback_started = pyqtSignal()
        playback_paused = pyqtSignal()
        playback_stopped = pyqtSignal()
        playback_finished = pyqtSignal()
        position_changed = pyqtSignal(int)  # Position in milliseconds
        duration_changed = pyqtSignal(int)  # Duration in milliseconds
        frame_ready = pyqtSignal(object)  # QVideoFrame or numpy array for AI processing
        error_occurred = pyqtSignal(str)  # Error message
    
    def __init__(self, parent=None, event_bus=None):
        if HAS_PYQT6:
            super().__init__(parent)
        
        self.event_bus = event_bus
        self._video_path: Optional[str] = None
        self._is_playing = False
        self._is_looping = False
        self._ai_processor: Optional[Callable] = None
        self._frame_buffer = FrameBuffer(max_frames=3)
        
        # Media components (initialized in _setup_multimedia)
        self._media_player: Optional[QMediaPlayer] = None
        self._video_widget: Optional[QVideoWidget] = None
        self._video_sink: Optional[QVideoSink] = None
        self._audio_output: Optional[QAudioOutput] = None
        
        # Fallback components
        self._fallback_label: Optional[QLabel] = None
        self._fallback_capture = None
        self._fallback_timer: Optional[QTimer] = None
        self._fallback_fps = 30
        
        # UI state
        self._controls_visible = True
        self._thumbnail_pixmap: Optional[QPixmap] = None
        
        if HAS_PYQT6:
            self._setup_ui()
    
    def _setup_ui(self):
        """Setup the video player UI."""
        self.setMinimumSize(320, 240)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Stacked widget for video/thumbnail switching
        self._stack = QStackedWidget()
        
        # Setup multimedia or fallback
        if HAS_MULTIMEDIA:
            self._setup_multimedia()
        else:
            logger.warning("PyQt6-Multimedia not available, using OpenCV fallback")
        
        # Fallback label (always available)
        self._fallback_label = QLabel()
        self._fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fallback_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: 1px solid #3d3d5c;
                border-radius: 4px;
            }
        """)
        self._fallback_label.setText("No video loaded")
        self._fallback_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Add widgets to stack
        if self._video_widget:
            self._stack.addWidget(self._video_widget)  # Index 0
        self._stack.addWidget(self._fallback_label)  # Index 1 (or 0 if no video widget)
        
        # Show fallback by default
        self._stack.setCurrentWidget(self._fallback_label)
        
        layout.addWidget(self._stack, stretch=1)
        
        # Controls container
        self._controls_widget = QWidget()
        self._setup_controls()
        layout.addWidget(self._controls_widget)
        
        # Setup fallback timer for OpenCV playback
        if HAS_OPENCV:
            self._fallback_timer = QTimer()
            self._fallback_timer.timeout.connect(self._fallback_frame_tick)
    
    def _setup_multimedia(self):
        """Setup QMediaPlayer and related components."""
        if not HAS_MULTIMEDIA:
            return
        
        try:
            # Create media player
            self._media_player = QMediaPlayer()
            
            # Create video output widget
            self._video_widget = QVideoWidget()
            self._video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            
            # Create audio output
            self._audio_output = QAudioOutput()
            self._media_player.setAudioOutput(self._audio_output)
            
            # Create video sink for frame-by-frame access
            self._video_sink = QVideoSink()
            
            # Connect media player to video widget
            self._media_player.setVideoOutput(self._video_widget)
            
            # Connect video sink for frame processing
            self._media_player.setVideoSink(self._video_sink)
            self._video_sink.videoFrameChanged.connect(self._on_video_frame)
            
            # Connect media player signals
            self._media_player.positionChanged.connect(self._on_position_changed)
            self._media_player.durationChanged.connect(self._on_duration_changed)
            self._media_player.playbackStateChanged.connect(self._on_playback_state_changed)
            self._media_player.errorOccurred.connect(self._on_error)
            self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)
            
            logger.info("✅ QtMultimedia initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize QtMultimedia: {e}")
            self._media_player = None
            self._video_widget = None
    
    def _setup_controls(self):
        """Setup playback control buttons and slider."""
        layout = QHBoxLayout(self._controls_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Play/Pause button
        self._play_btn = QPushButton()
        self._play_btn.setFixedSize(32, 32)
        self._play_btn.setToolTip("Play/Pause")
        self._play_btn.clicked.connect(self.toggle_playback)
        self._update_play_button_icon()
        layout.addWidget(self._play_btn)
        
        # Stop button
        self._stop_btn = QPushButton()
        self._stop_btn.setFixedSize(32, 32)
        self._stop_btn.setToolTip("Stop")
        self._stop_btn.clicked.connect(self.stop)
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d44;
                border: 1px solid #4a4a6a;
                border-radius: 4px;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #3d3d5c;
            }
        """)
        self._stop_btn.setText("⏹")
        layout.addWidget(self._stop_btn)
        
        # Position slider
        self._position_slider = QSlider(Qt.Orientation.Horizontal)
        self._position_slider.setRange(0, 0)
        self._position_slider.sliderMoved.connect(self._on_slider_moved)
        self._position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #2d2d44;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                margin: -4px 0;
                background: #9b59b6;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #9b59b6;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self._position_slider, stretch=1)
        
        # Time label
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        self._time_label.setFixedWidth(90)
        layout.addWidget(self._time_label)
        
        # Loop toggle button
        self._loop_btn = QPushButton("🔁")
        self._loop_btn.setFixedSize(32, 32)
        self._loop_btn.setToolTip("Toggle Loop")
        self._loop_btn.setCheckable(True)
        self._loop_btn.clicked.connect(self._on_loop_toggled)
        self._loop_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d44;
                border: 1px solid #4a4a6a;
                border-radius: 4px;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #3d3d5c;
            }
            QPushButton:checked {
                background-color: #9b59b6;
                border-color: #9b59b6;
            }
        """)
        layout.addWidget(self._loop_btn)
        
        # Volume slider (if audio available)
        if HAS_MULTIMEDIA and self._audio_output:
            self._volume_slider = QSlider(Qt.Orientation.Horizontal)
            self._volume_slider.setRange(0, 100)
            self._volume_slider.setValue(70)
            self._volume_slider.setFixedWidth(60)
            self._volume_slider.valueChanged.connect(self._on_volume_changed)
            self._volume_slider.setToolTip("Volume")
            self._volume_slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    height: 4px;
                    background: #2d2d44;
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    width: 10px;
                    margin: -3px 0;
                    background: #28a745;
                    border-radius: 5px;
                }
            """)
            layout.addWidget(self._volume_slider)
    
    def _update_play_button_icon(self):
        """Update play button icon based on playback state."""
        if self._is_playing:
            self._play_btn.setText("⏸")
            self._play_btn.setStyleSheet("""
                QPushButton {
                    background-color: #9b59b6;
                    border: 1px solid #9b59b6;
                    border-radius: 4px;
                    color: white;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #8e44ad;
                }
            """)
        else:
            self._play_btn.setText("▶")
            self._play_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    border: 1px solid #28a745;
                    border-radius: 4px;
                    color: white;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
            """)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────
    
    def load_video(self, path: str) -> bool:
        """Load a video file for playback.
        
        Args:
            path: Path to the video file (.mp4, .avi, .mkv, etc.)
            
        Returns:
            True if video loaded successfully, False otherwise
        """
        if not path or not Path(path).exists():
            logger.error(f"Video file not found: {path}")
            self.error_occurred.emit(f"Video file not found: {path}")
            return False
        
        self._video_path = path
        self._frame_buffer.clear()
        
        # Extract thumbnail for initial display
        self._extract_thumbnail()
        
        if HAS_MULTIMEDIA and self._media_player:
            try:
                # SOTA 2026: Use setSource() instead of deprecated setMedia()
                self._media_player.setSource(QUrl.fromLocalFile(path))
                logger.info(f"✅ Video loaded via QtMultimedia: {path}")
                return True
            except Exception as e:
                logger.error(f"QtMultimedia load failed: {e}, falling back to OpenCV")
        
        # Fallback to OpenCV
        if HAS_OPENCV:
            try:
                self._fallback_capture = cv2.VideoCapture(path)
                if self._fallback_capture.isOpened():
                    fps = self._fallback_capture.get(cv2.CAP_PROP_FPS)
                    self._fallback_fps = int(fps) if fps > 0 else 30
                    total_frames = int(self._fallback_capture.get(cv2.CAP_PROP_FRAME_COUNT))
                    duration_ms = int((total_frames / self._fallback_fps) * 1000) if self._fallback_fps > 0 else 0
                    self._position_slider.setRange(0, duration_ms)
                    self.duration_changed.emit(duration_ms)
                    logger.info(f"✅ Video loaded via OpenCV fallback: {path}")
                    return True
            except Exception as e:
                logger.error(f"OpenCV load failed: {e}")
        
        self._fallback_label.setText(f"Failed to load: {Path(path).name}")
        return False
    
    def play(self):
        """Start or resume video playback."""
        if not self._video_path:
            return
        
        if HAS_MULTIMEDIA and self._media_player:
            self._media_player.play()
            if self._video_widget:
                self._stack.setCurrentWidget(self._video_widget)
        elif HAS_OPENCV and self._fallback_capture:
            self._is_playing = True
            frame_interval = 1000 // self._fallback_fps
            self._fallback_timer.start(frame_interval)
            self._stack.setCurrentWidget(self._fallback_label)
            self.playback_started.emit()
        
        self._is_playing = True
        self._update_play_button_icon()
    
    def pause(self):
        """Pause video playback."""
        if HAS_MULTIMEDIA and self._media_player:
            self._media_player.pause()
        elif self._fallback_timer:
            self._fallback_timer.stop()
        
        self._is_playing = False
        self._update_play_button_icon()
        self.playback_paused.emit()
    
    def stop(self):
        """Stop video playback and return to thumbnail."""
        if HAS_MULTIMEDIA and self._media_player:
            self._media_player.stop()
        
        if self._fallback_timer:
            self._fallback_timer.stop()
        
        if self._fallback_capture:
            self._fallback_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        self._is_playing = False
        self._update_play_button_icon()
        self._position_slider.setValue(0)
        
        # Show thumbnail
        if self._thumbnail_pixmap:
            self._fallback_label.setPixmap(self._thumbnail_pixmap.scaled(
                self._fallback_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        self._stack.setCurrentWidget(self._fallback_label)
        
        self.playback_stopped.emit()
    
    def toggle_playback(self):
        """Toggle between play and pause states."""
        if self._is_playing:
            self.pause()
        else:
            self.play()
    
    def seek(self, position_ms: int):
        """Seek to a specific position in the video.
        
        Args:
            position_ms: Position in milliseconds
        """
        if HAS_MULTIMEDIA and self._media_player:
            self._media_player.setPosition(position_ms)
        elif HAS_OPENCV and self._fallback_capture:
            frame_num = int((position_ms / 1000) * self._fallback_fps)
            self._fallback_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    
    def set_loop(self, enabled: bool):
        """Enable or disable looping playback."""
        self._is_looping = enabled
        if HAS_MULTIMEDIA and self._media_player:
            # QMediaPlayer handles looping via mediaStatusChanged signal
            pass
        self._loop_btn.setChecked(enabled)
    
    def enable_ai_processing(self, processor: Callable):
        """Set a callback function for AI frame processing.
        
        Args:
            processor: Callable that takes a frame (QVideoFrame or numpy array)
                      and returns processed frame
        """
        self._ai_processor = processor
    
    def set_controls_visible(self, visible: bool):
        """Show or hide playback controls."""
        self._controls_visible = visible
        self._controls_widget.setVisible(visible)
    
    def get_thumbnail(self) -> Optional[QPixmap]:
        """Get the video thumbnail pixmap."""
        return self._thumbnail_pixmap
    
    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods - Frame Processing
    # ─────────────────────────────────────────────────────────────────────────
    
    def _extract_thumbnail(self):
        """Extract first frame as thumbnail."""
        if not self._video_path or not HAS_OPENCV:
            return
        
        try:
            cap = cv2.VideoCapture(self._video_path)
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                
                qimage = QImage(frame_rgb.tobytes(), w, h, bytes_per_line, QImage.Format.Format_RGB888)
                self._thumbnail_pixmap = QPixmap.fromImage(qimage)
                
                # Display thumbnail
                scaled = self._thumbnail_pixmap.scaled(
                    self._fallback_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._fallback_label.setPixmap(scaled)
                
        except Exception as e:
            logger.error(f"Failed to extract thumbnail: {e}")
    
    @pyqtSlot(QVideoFrame)
    def _on_video_frame(self, frame: QVideoFrame):
        """Handle incoming video frame from QVideoSink.
        
        SOTA 2026: Process frame immediately and release to prevent memory buildup.
        """
        if frame is None or not frame.isValid():
            return
        
        try:
            # Add to buffer (auto-cleanup of old frames)
            self._frame_buffer.add_frame(frame)
            
            # Emit for AI processing
            self.frame_ready.emit(frame)
            
            # Publish to event bus if available
            if self.event_bus:
                try:
                    self.event_bus.publish('video.playback.frame', {
                        'frame': frame,
                        'video_path': self._video_path,
                        'timestamp': frame.startTime() / 1000000 if frame.startTime() else 0  # Convert to seconds
                    })
                except Exception:
                    pass
            
            # Apply AI processing if enabled
            if self._ai_processor:
                try:
                    processed = self._ai_processor(frame)
                    # Processed frame would be displayed via custom rendering
                except Exception as e:
                    logger.error(f"AI frame processing error: {e}")
            
        except Exception as e:
            logger.error(f"Error processing video frame: {e}")
        finally:
            # CRITICAL: Release frame reference to free memory
            frame = None
    
    def _fallback_frame_tick(self):
        """Timer callback for OpenCV-based frame playback."""
        if not self._fallback_capture or not self._is_playing:
            return
        
        ret, frame = self._fallback_capture.read()
        
        if not ret:
            # End of video
            if self._is_looping:
                self._fallback_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                return
            else:
                self.stop()
                self.playback_finished.emit()
                return
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        
        # Create QImage and display
        qimage = QImage(frame_rgb.tobytes(), w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)
        
        scaled = pixmap.scaled(
            self._fallback_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        self._fallback_label.setPixmap(scaled)
        
        # Add to frame buffer
        self._frame_buffer.add_frame(frame)
        
        # Emit frame for AI processing
        self.frame_ready.emit(frame)
        
        # Publish to event bus
        if self.event_bus:
            try:
                current_frame = int(self._fallback_capture.get(cv2.CAP_PROP_POS_FRAMES))
                timestamp = current_frame / self._fallback_fps if self._fallback_fps > 0 else 0
                self.event_bus.publish('video.playback.frame', {
                    'frame': frame,
                    'video_path': self._video_path,
                    'timestamp': timestamp
                })
            except Exception:
                pass
        
        # Update position
        current_frame = int(self._fallback_capture.get(cv2.CAP_PROP_POS_FRAMES))
        position_ms = int((current_frame / self._fallback_fps) * 1000) if self._fallback_fps > 0 else 0
        self._position_slider.setValue(position_ms)
        self.position_changed.emit(position_ms)
        self._update_time_label(position_ms, self._position_slider.maximum())
    
    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods - Signal Handlers
    # ─────────────────────────────────────────────────────────────────────────
    
    def _on_position_changed(self, position: int):
        """Handle position change from QMediaPlayer."""
        self._position_slider.setValue(position)
        self.position_changed.emit(position)
        duration = self._media_player.duration() if self._media_player else 0
        self._update_time_label(position, duration)
    
    def _on_duration_changed(self, duration: int):
        """Handle duration change from QMediaPlayer."""
        self._position_slider.setRange(0, duration)
        self.duration_changed.emit(duration)
    
    def _on_playback_state_changed(self, state):
        """Handle playback state change from QMediaPlayer."""
        if HAS_MULTIMEDIA:
            from PyQt6.QtMultimedia import QMediaPlayer
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self._is_playing = True
                self.playback_started.emit()
            elif state == QMediaPlayer.PlaybackState.PausedState:
                self._is_playing = False
                self.playback_paused.emit()
            elif state == QMediaPlayer.PlaybackState.StoppedState:
                self._is_playing = False
                self.playback_stopped.emit()
        
        self._update_play_button_icon()
    
    def _on_media_status_changed(self, status):
        """Handle media status change from QMediaPlayer."""
        if HAS_MULTIMEDIA:
            from PyQt6.QtMultimedia import QMediaPlayer
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                if self._is_looping:
                    self._media_player.setPosition(0)
                    self._media_player.play()
                else:
                    self.playback_finished.emit()
    
    def _on_error(self, error, error_string: str):
        """Handle error from QMediaPlayer."""
        logger.error(f"Media player error: {error_string}")
        self.error_occurred.emit(error_string)
    
    def _on_slider_moved(self, position: int):
        """Handle user moving the position slider."""
        self.seek(position)
    
    def _on_loop_toggled(self, checked: bool):
        """Handle loop button toggle."""
        self._is_looping = checked
    
    def _on_volume_changed(self, value: int):
        """Handle volume slider change."""
        if HAS_MULTIMEDIA and self._audio_output:
            self._audio_output.setVolume(value / 100.0)
    
    def _update_time_label(self, position_ms: int, duration_ms: int):
        """Update the time display label."""
        def format_time(ms: int) -> str:
            seconds = ms // 1000
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        
        self._time_label.setText(f"{format_time(position_ms)} / {format_time(duration_ms)}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────────────────────────────────────────
    
    def cleanup(self):
        """Release all resources."""
        self.stop()
        
        if self._fallback_capture:
            self._fallback_capture.release()
            self._fallback_capture = None
        
        if self._fallback_timer:
            self._fallback_timer.stop()
        
        self._frame_buffer.clear()
        
        if self._media_player:
            self._media_player.setSource(QUrl())
        
        logger.info("RealTimeVideoPlayer cleaned up")
    
    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass
