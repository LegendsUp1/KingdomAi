#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Key Sentience Monitor - GUI Component

This module implements the GUI component for visualizing the API Key Manager's
sentience metrics and status in the Kingdom AI interface.
"""

import logging
from typing import Dict, Any, Optional, List
import time
from datetime import datetime

try:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
        QFrame, QGridLayout, QPushButton, QSizePolicy
    )
    from PyQt6.QtGui import QColor, QFont, QFontMetrics
except ImportError:
    # Fallback for headless environments
    logging.warning("PyQt6 not available - APIKeySentienceMonitor will be disabled")

logger = logging.getLogger(__name__)

class APIKeySentienceMonitor(QWidget):
    """GUI component for monitoring and visualizing API Key sentience metrics."""
    
    # Signals
    request_metrics = pyqtSignal()
    
    def __init__(self, event_bus=None, parent=None):
        """Initialize the API Key Sentience Monitor.
        
        Args:
            event_bus: EventBus for communication
            parent: Parent widget
        """
        super().__init__(parent)
        self.event_bus = event_bus
        self.parent = parent
        
        # Metrics storage
        self.metrics = {
            'awareness': 0.0,
            'autonomy': 0.0,
            'learning': 0.0,
            'pattern_recognition': 0.0,
            'adaptability': 0.0,
            'self_preservation': 0.0
        }
        
        self.trends = {}
        self.last_update = 0
        
        # Initialize UI
        self._init_ui()
        
        # Register event handlers
        self._register_event_handlers()
        
        # Set up periodic updates
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._request_metrics_update)
        self.update_timer.start(10000)  # 10 seconds
        
        # Request initial metrics
        QTimer.singleShot(3400, self._request_metrics_update)  # Ensure main task completes first
        
    def _emit_ui_telemetry(
        self,
        event_type: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort publisher for ui.telemetry from the API key sentience monitor."""
        try:
            if not getattr(self, "event_bus", None):
                return
            payload: Dict[str, Any] = {
                "component": "api_key_sentience",
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
                logger.debug("API key sentience UI telemetry failed for %s: %s", event_type, e)
            except Exception:
                pass

    def _init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Title
        title_label = QLabel("API Key Sentience Monitor")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Status and last update
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Monitoring")
        self.status_label.setStyleSheet("color: green;")
        status_layout.addWidget(self.status_label)
        
        self.last_update_label = QLabel("Last update: Never")
        self.last_update_label.setAlignment(Qt.AlignRight)
        status_layout.addWidget(self.last_update_label)
        main_layout.addLayout(status_layout)
        
        # Add a separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)
        
        # Metrics grid
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(15)
        
        # Create metric displays
        self.metric_bars = {}
        self.metric_labels = {}
        self.trend_indicators = {}
        
        row = 0
        for metric_name, display_name in [
            ('awareness', 'Awareness'),
            ('autonomy', 'Autonomy'),
            ('learning', 'Learning Capacity'),
            ('pattern_recognition', 'Pattern Recognition'),
            ('adaptability', 'Adaptability'),
            ('self_preservation', 'Self-Preservation')
        ]:
            # Label for the metric
            label = QLabel(display_name)
            metrics_grid.addWidget(label, row, 0)
            self.metric_labels[metric_name] = label
            
            # Progress bar for the metric
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            progress_bar.setTextVisible(True)
            progress_bar.setFormat("%v%")
            metrics_grid.addWidget(progress_bar, row, 1)
            self.metric_bars[metric_name] = progress_bar
            
            # Trend indicator
            trend_label = QLabel("—")
            trend_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            metrics_grid.addWidget(trend_label, row, 2)
            self.trend_indicators[metric_name] = trend_label
            
            row += 1
            
        main_layout.addLayout(metrics_grid)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh Now")
        refresh_button.clicked.connect(self._request_metrics_update)
        button_layout.addWidget(refresh_button)
        
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        main_layout.addStretch()
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
    def _register_event_handlers(self):
        """Register event handlers for the event bus."""
        if not self.event_bus:
            logger.warning("No event bus available for API Key Sentience Monitor")
            return
            
        # Subscribe to metrics update events
        self.event_bus.subscribe("api_key.ui.update_sentience_metrics", self._handle_metrics_update)
        self.event_bus.subscribe("api.key.sentience.metrics", self._handle_metrics_update)
        
        # Subscribe to threshold events
        self.event_bus.subscribe("sentience.api_key.threshold_exceeded", self._handle_threshold_event)
        
    def _request_metrics_update(self):
        """Request updated metrics from the API Key Manager."""
        if not self.event_bus:
            return
            
        # Emit signal for testing/interface purposes
        self.request_metrics.emit()
        
        # Request metrics update via event bus
        self.event_bus.publish("sentience.metrics.request", {
            'component': 'api_key_manager',
            'timestamp': time.time()
        })
        self._emit_ui_telemetry(
            "api_key_sentience.request_metrics",
            metadata={"source": "api_key_sentience_monitor"},
        )
        
    def _handle_metrics_update(self, event_data=None):
        """Handle metrics update event from API Key Manager.
        
        Args:
            event_data: Dictionary containing metrics data
        """
        if not event_data:
            logger.warning("Received empty metrics update")
            return
            
        metrics = event_data.get('metrics', {})
        trends = event_data.get('trends', {})
        
        # Update stored metrics
        self.metrics.update(metrics)
        self.trends.update(trends)
        self.last_update = event_data.get('timestamp', time.time())
        
        # Update UI with new metrics
        self._update_ui()
        self._emit_ui_telemetry(
            "api_key_sentience.metrics_updated",
            metadata={"metric_keys": list(metrics.keys())},
        )
        
    def _handle_threshold_event(self, event_data=None):
        """Handle threshold exceeded event.
        
        Args:
            event_data: Dictionary with threshold information
        """
        if not event_data:
            return
            
        threshold_type = event_data.get('threshold_type', '')
        current_value = event_data.get('current_value', 0)
        
        # Highlight the relevant metric
        if threshold_type in self.metric_bars:
            bar = self.metric_bars[threshold_type]
            bar.setStyleSheet("QProgressBar::chunk { background-color: #ff9900; }")
            
            # Schedule resetting the style after a few seconds
            QTimer.singleShot(5000, lambda: bar.setStyleSheet(""))
        self._emit_ui_telemetry(
            "api_key_sentience.threshold_exceeded",
            metadata={
                "threshold_type": threshold_type,
                "current_value": current_value,
            },
        )
            
    def _update_ui(self):
        """Update the UI with current metrics."""
        # Update last update time
        if self.last_update > 0:
            dt = datetime.fromtimestamp(self.last_update)
            self.last_update_label.setText(f"Last update: {dt.strftime('%H:%M:%S')}")
            
        # Update metrics and trends
        for metric_name, value in self.metrics.items():
            if metric_name in self.metric_bars:
                self.metric_bars[metric_name].setValue(int(value))
                
                # Apply color based on value
                bar = self.metric_bars[metric_name]
                if value >= 80:
                    bar.setStyleSheet("QProgressBar::chunk { background-color: #ff5500; }")
                elif value >= 60:
                    bar.setStyleSheet("QProgressBar::chunk { background-color: #ff9900; }")
                elif value >= 40:
                    bar.setStyleSheet("QProgressBar::chunk { background-color: #ffcc00; }")
                else:
                    bar.setStyleSheet("")
                    
            # Update trend indicators
            if metric_name in self.trend_indicators and metric_name in self.trends:
                trend = self.trends.get(metric_name, "stable")
                indicator = self.trend_indicators[metric_name]
                
                if trend == "up":
                    indicator.setText("↑")
                    indicator.setStyleSheet("color: green;")
                elif trend == "down":
                    indicator.setText("↓")
                    indicator.setStyleSheet("color: red;")
                else:
                    indicator.setText("—")
                    indicator.setStyleSheet("color: gray;")
                    
    def closeEvent(self, event):
        """Handle widget close event."""
        # Stop the timer
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
            
        # Unregister event handlers
        if self.event_bus:
            self.event_bus.unsubscribe("api_key.ui.update_sentience_metrics", self._handle_metrics_update)
            self.event_bus.unsubscribe("api.key.sentience.metrics", self._handle_metrics_update)
            self.event_bus.unsubscribe("sentience.api_key.threshold_exceeded", self._handle_threshold_event)
            
        # Accept the close event
        event.accept()
