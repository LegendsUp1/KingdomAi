import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QSlider, QProgressBar, QCheckBox,
                            QGroupBox, QFrame, QComboBox, QGridLayout,
                            QSplitter, QTabWidget, QScrollArea)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QLinearGradient, QBrush

# Import EventBus for real-time updates
from core.event_bus import EventBus

logger = logging.getLogger(__name__)

class MetricProgressBar(QProgressBar):
    """Custom progress bar for displaying sentience metrics."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setValue(0)
        self.setTextVisible(True)
        self.setFormat("%v%")
        self.setStyleSheet("""
            QProgressBar {
                border: 2px solid #76797C;
                border-radius: 5px;
                text-align: center;
                height: 20px;
                background-color: #2D2D30;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1: 0, y1: 0.5, x2: 1, y2: 0.5, stop: 0 #5CACEE, stop: 1 #1874CD);
                width: 10px;
                margin: 0.5px;
            }
        """)
    
    def update_value(self, value: float):
        """Update progress bar with a float value between 0.0 and 1.0."""
        int_value = int(value * 100)
        self.setValue(int_value)
        
        # Change color based on value
        if value >= 0.8:
            self.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #76797C;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #2D2D30;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1: 0, y1: 0.5, x2: 1, y2: 0.5, stop: 0 #FF4500, stop: 1 #FF0000);
                    width: 10px;
                    margin: 0.5px;
                }
            """)
        elif value >= 0.6:
            self.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #76797C;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #2D2D30;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1: 0, y1: 0.5, x2: 1, y2: 0.5, stop: 0 #FFA500, stop: 1 #FF8C00);
                    width: 10px;
                    margin: 0.5px;
                }
            """)
        else:
            self.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #76797C;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #2D2D30;
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1: 0, y1: 0.5, x2: 1, y2: 0.5, stop: 0 #5CACEE, stop: 1 #1874CD);
                    width: 10px;
                    margin: 0.5px;
                }
            """)


class VRSentienceMonitor(QWidget):
    """
    VR Sentience Monitor GUI component for Kingdom AI.
    Displays and allows interaction with VR sentience detection metrics.
    """
    
    def __init__(self, event_bus: EventBus = None, parent=None):
        """Initialize the VR Sentience Monitor component."""
        super().__init__(parent)
        
        self.event_bus = event_bus
        self.metrics = {}
        self.history = []
        self.sentience_monitoring_enabled = True
        self.sentience_threshold = 0.7  # Default threshold
        
        self._init_ui()
        self._connect_signals()
        self._start_timer()
        
    def _init_ui(self):
        """Initialize the UI components."""
        self.setWindowTitle("VR Sentience Monitor")
        
        # Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Title
        title_label = QLabel("VR Sentience Monitoring")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #FFFFFF;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Status and controls
        status_layout = QHBoxLayout()
        
        # Status indicator
        self.status_group = QGroupBox("Monitoring Status")
        status_inner_layout = QVBoxLayout()
        self.status_label = QLabel("Active")
        self.status_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #00FF00;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        status_inner_layout.addWidget(self.status_label)
        self.status_group.setLayout(status_inner_layout)
        status_layout.addWidget(self.status_group)
        
        # Controls
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout()
        
        # Toggle monitoring button
        self.toggle_button = QPushButton("Disable Monitoring")
        self.toggle_button.setStyleSheet("background-color: #CD5555; font-weight: bold;")
        controls_layout.addWidget(self.toggle_button)
        
        # Threshold adjustment
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Sentience Threshold:"))
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setMinimum(0)
        self.threshold_slider.setMaximum(100)
        self.threshold_slider.setValue(int(self.sentience_threshold * 100))
        threshold_layout.addWidget(self.threshold_slider)
        self.threshold_value_label = QLabel(f"{self.sentience_threshold:.2f}")
        threshold_layout.addWidget(self.threshold_value_label)
        
        controls_layout.addLayout(threshold_layout)
        controls_group.setLayout(controls_layout)
        status_layout.addWidget(controls_group)
        
        main_layout.addLayout(status_layout)
        
        # Aggregate sentience score
        aggregate_group = QGroupBox("Aggregate Sentience Score")
        aggregate_layout = QVBoxLayout()
        self.aggregate_progress = MetricProgressBar()
        aggregate_layout.addWidget(self.aggregate_progress)
        aggregate_group.setLayout(aggregate_layout)
        main_layout.addWidget(aggregate_group)
        
        # Individual metrics
        metrics_group = QGroupBox("Sentience Metrics")
        metrics_layout = QGridLayout()
        
        # Create metric rows
        self.metric_bars = {}
        metric_names = [
            "spatial_cognition", "self_movement_recognition", 
            "environment_adaptation", "interaction_complexity",
            "immersion_depth", "presence_stability"
        ]
        
        metric_labels = {
            "spatial_cognition": "Spatial Cognition",
            "self_movement_recognition": "Self Movement Recognition",
            "environment_adaptation": "Environment Adaptation",
            "interaction_complexity": "Interaction Complexity",
            "immersion_depth": "Immersion Depth",
            "presence_stability": "Presence Stability"
        }
        
        for i, metric in enumerate(metric_names):
            row = i
            # Label
            metrics_layout.addWidget(QLabel(metric_labels[metric]), row, 0)
            
            # Progress bar
            progress_bar = MetricProgressBar()
            self.metric_bars[metric] = progress_bar
            metrics_layout.addWidget(progress_bar, row, 1)
        
        metrics_group.setLayout(metrics_layout)
        main_layout.addWidget(metrics_group)
        
        # Enhancement status
        enhancement_group = QGroupBox("Experience Enhancement Status")
        enhancement_layout = QHBoxLayout()
        self.enhancement_status = QLabel("Standard VR Experience")
        self.enhancement_status.setStyleSheet("font-size: 12pt;")
        self.enhancement_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        enhancement_layout.addWidget(self.enhancement_status)
        enhancement_group.setLayout(enhancement_layout)
        main_layout.addWidget(enhancement_group)

    def _emit_ui_telemetry(
        self,
        event_type: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort publisher for ui.telemetry from the VR sentience monitor."""
        try:
            if not getattr(self, "event_bus", None):
                return
            payload: Dict[str, Any] = {
                "component": "vr_sentience",
                "channel": "ui.telemetry",
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "success": success,
                "error": error,
                "metadata": metadata or {},
            }
            self.event_bus.publish("ui.telemetry", payload)
        except Exception as e:
            try:
                logger.debug("VR sentience UI telemetry failed for %s: %s", event_type, e)
            except Exception:
                pass
        
    def _connect_signals(self):
        """Connect signals to slots."""
        # Toggle button
        self.toggle_button.clicked.connect(self.toggle_monitoring)
        
        # Threshold slider
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        
        # Connect to event bus if available
        if hasattr(parent, 'event_bus') and parent.event_bus:
            self.event_bus = parent.event_bus
        else:
            self.event_bus = None
        
        # Connect to central ThothAI brain system
        self._connect_to_central_brain()
        
        # Start real-time VR sentience monitoring feeds
        self._start_real_time_sentience_feeds()
        
        # Connect to event bus signals
        if self.event_bus:
            self.event_bus.subscribe("vr.sentience.metrics.update", self._on_metrics_update)
            self.event_bus.subscribe("vr.sentience.status", self._on_status_update)
            self.event_bus.subscribe("vr.experience.enhance", self._on_experience_enhanced)
            self.event_bus.subscribe("vr.experience.revert", self._on_experience_reverted)
            
    def _start_timer(self):
        """Start the update timer for metrics monitoring."""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.request_metrics_update)
        self.update_timer.start(1000)  # Update every second
        
    def request_metrics_update(self):
        """Request updated metrics from the VR system."""
        if self.event_bus and self.sentience_monitoring_enabled:
            self.event_bus.publish("vr.sentience.metrics.request", {
                "timestamp": datetime.now().isoformat()
            })
            self._emit_ui_telemetry(
                "vr_sentience.request_metrics",
                metadata={"source": "vr_sentience_monitor"},
            )
            
    def toggle_monitoring(self):
        """Toggle sentience monitoring on/off."""
        self.sentience_monitoring_enabled = not self.sentience_monitoring_enabled
        
        if self.event_bus:
            self.event_bus.publish("vr.sentience.toggle", {
                "enabled": self.sentience_monitoring_enabled,
                "timestamp": datetime.now().isoformat()
            })
        
        # Update UI
        if self.sentience_monitoring_enabled:
            self.status_label.setText("Active")
            self.status_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #00FF00;")
            self.toggle_button.setText("Disable Monitoring")
            self.toggle_button.setStyleSheet("background-color: #CD5555; font-weight: bold;")
        else:
            self.status_label.setText("Disabled")
            self.status_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #FF0000;")
            self.toggle_button.setText("Enable Monitoring")
            self.toggle_button.setStyleSheet("background-color: #2E8B57; font-weight: bold;")
        self._emit_ui_telemetry(
            "vr_sentience.monitoring_toggled",
            metadata={"enabled": bool(self.sentience_monitoring_enabled)},
        )
            
    def update_threshold(self):
        """Update the sentience threshold based on slider value."""
        value = self.threshold_slider.value() / 100.0
        self.sentience_threshold = value
        self.threshold_value_label.setText(f"{value:.2f}")
        
        if self.event_bus:
            self.event_bus.publish("vr.sentience.threshold.adjust", {
                "threshold": value,
                "timestamp": datetime.now().isoformat()
            })
        self._emit_ui_telemetry(
            "vr_sentience.threshold_adjusted",
            metadata={"threshold": float(value)},
        )
            
    def _on_metrics_update(self, event_data):
        """Handle updated metrics from the VR system."""
        metrics = event_data.get("metrics", {})
        self.metrics = metrics
        
        # Update aggregate score
        aggregate_score = metrics.get("aggregate_score", 0.0)
        self.aggregate_progress.update_value(aggregate_score)
        
        # Update individual metrics
        for metric, bar in self.metric_bars.items():
            value = metrics.get(metric, 0.0)
            bar.update_value(value)
        self._emit_ui_telemetry(
            "vr_sentience.metrics_updated",
            metadata={"metric_keys": list(metrics.keys())},
        )
            
    def _on_status_update(self, event_data):
        """Handle status updates from the VR system."""
        enabled = event_data.get("enabled", self.sentience_monitoring_enabled)
        
        # Update only if different from current state
        if enabled != self.sentience_monitoring_enabled:
            self.sentience_monitoring_enabled = enabled
            
            # Update UI
            if self.sentience_monitoring_enabled:
                self.status_label.setText("Active")
                self.status_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #00FF00;")
                self.toggle_button.setText("Disable Monitoring")
                self.toggle_button.setStyleSheet("background-color: #CD5555; font-weight: bold;")
            else:
                self.status_label.setText("Disabled")
                self.status_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #FF0000;")
                self.toggle_button.setText("Enable Monitoring")
                self.toggle_button.setStyleSheet("background-color: #2E8B57; font-weight: bold;")
                
    def _on_experience_enhanced(self, event_data):
        """Handle experience enhancement events."""
        enhancements = event_data.get("enhancements", [])
        
        enhancement_text = "Enhanced VR Experience: "
        if "increased_responsiveness" in enhancements:
            enhancement_text += "Responsiveness↑ "
        if "deeper_immersion" in enhancements:
            enhancement_text += "Immersion↑ "
        if "enhanced_visuals" in enhancements:
            enhancement_text += "Visuals↑ "
        if "spatial_audio_boost" in enhancements:
            enhancement_text += "Audio↑ "
        if "haptic_feedback_intensity" in enhancements:
            enhancement_text += "Haptics↑"
            
        self.enhancement_status.setText(enhancement_text)
        self.enhancement_status.setStyleSheet("font-size: 12pt; font-weight: bold; color: #00BFFF;")
        
    def _on_experience_reverted(self, event_data):
        """Handle experience reversion events."""
        self.enhancement_status.setText("Standard VR Experience")
        self.enhancement_status.setStyleSheet("font-size: 12pt; color: #FFFFFF;")
