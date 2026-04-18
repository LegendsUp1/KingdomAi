#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Wallet Sentience Monitor UI Component

This module provides the UI components for monitoring wallet sentience metrics,
patterns, and thresholds in real-time. It integrates with the wallet sentience
integration module and displays sentience data through the GUI.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QGroupBox, QFrame, QScrollArea, QSizePolicy, QPushButton
)
try:
    from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
except ImportError:
    # QtCharts may not be installed; graceful degradation
    QChart = QChartView = QLineSeries = QValueAxis = None

class WalletSentienceMetricDisplay(QFrame):
    """Displays a single sentience metric with a label and progress bar."""
    
    def __init__(self, metric_name: str, parent=None):
        """Initialize the metric display.
        
        Args:
            metric_name: Name of the sentience metric
            parent: Parent widget
        """
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.metric_name = metric_name
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        
        # Metric name label with tooltip
        self.name_label = QLabel(self.metric_name.replace("_", " ").title())
        self.name_label.setToolTip(f"Sentience metric: {self.metric_name}")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        
        # Horizontal layout for value display
        value_layout = QHBoxLayout()
        
        # Progress bar for visual representation
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        value_layout.addWidget(self.progress_bar)
        
        # Value label
        self.value_label = QLabel("0.00")
        self.value_label.setMinimumWidth(50)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_layout.addWidget(self.value_label)
        
        layout.addLayout(value_layout)
        
        # Trend indicator
        self.trend_label = QLabel("—")
        self.trend_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.trend_label)
        
    def update_value(self, value: float, trend: str = None):
        """Update the metric value and trend.
        
        Args:
            value: New metric value (0-100)
            trend: Trend direction ("up", "down", or "stable")
        """
        # Update progress bar
        self.progress_bar.setValue(int(value))
        
        # Update value label
        self.value_label.setText(f"{value:.2f}")
        
        # Update trend indicator
        if trend:
            if trend == "up":
                self.trend_label.setText("↑")
                self.trend_label.setStyleSheet("color: green;")
            elif trend == "down":
                self.trend_label.setText("↓")
                self.trend_label.setStyleSheet("color: red;")
            else:
                self.trend_label.setText("—")
                self.trend_label.setStyleSheet("")


class WalletSentienceChart(QWidget):
    """Chart component for visualizing wallet sentience metrics over time."""
    
    def __init__(self, parent=None):
        """Initialize the chart widget."""
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.series_dict = {}
        self.metrics_history = {}
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        
        # Create chart
        self.chart = QChart()
        self.chart.setTitle("Wallet Sentience Metrics Over Time")
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # X axis (time)
        self.axis_x = QValueAxis()
        self.axis_x.setLabelFormat("%d")
        self.axis_x.setTitleText("Time (seconds)")
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        
        # Y axis (metric value)
        self.axis_y = QValueAxis()
        self.axis_y.setRange(0, 100)
        self.axis_y.setLabelFormat("%d")
        self.axis_y.setTitleText("Metric Value")
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        
        # Chart view
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(self.chart_view.renderHint())
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.chart_view)
        
        # Initialize with empty series
        self._initialize_series(["awareness", "autonomy", "learning", "decision_making"])
        
    def _initialize_series(self, metrics: List[str]):
        """Initialize series for each metric.
        
        Args:
            metrics: List of metric names
        """
        colors = [Qt.red, Qt.blue, Qt.green, Qt.magenta, Qt.cyan, Qt.yellow]
        
        for i, metric in enumerate(metrics):
            # Create series
            series = QLineSeries()
            series.setName(metric.replace("_", " ").title())
            
            # Set color (cycling through available colors)
            color_index = i % len(colors)
            series.setColor(colors[color_index])
            
            # Add to chart
            self.chart.addSeries(series)
            series.attachAxis(self.axis_x)
            series.attachAxis(self.axis_y)
            
            # Store in dictionary
            self.series_dict[metric] = series
            self.metrics_history[metric] = []
            
    def update_metrics(self, metrics: Dict[str, float], timestamp: float):
        """Update chart with new metric values.
        
        Args:
            metrics: Dictionary of metric values
            timestamp: Timestamp of the update
        """
        # Use relative time (seconds since start)
        if not hasattr(self, "start_time"):
            self.start_time = timestamp
            
        relative_time = timestamp - self.start_time
        
        # Update each metric series
        for metric, value in metrics.items():
            if metric in self.series_dict:
                # Add data point to history
                self.metrics_history[metric].append((relative_time, value))
                
                # Keep only the last 60 points
                if len(self.metrics_history[metric]) > 60:
                    self.metrics_history[metric] = self.metrics_history[metric][-60:]
                
                # Update series with all points
                series = self.series_dict[metric]
                series.clear()
                for t, v in self.metrics_history[metric]:
                    series.append(t, v)
                    
        # Update X axis range to show the last 60 seconds
        if relative_time > 60:
            self.axis_x.setRange(relative_time - 60, relative_time)
        else:
            self.axis_x.setRange(0, max(60, relative_time))


class WalletSentienceMonitor(QWidget):
    """UI component for monitoring wallet sentience metrics and patterns."""
    
    # Define sentience metrics to display
    SENTIENCE_METRICS = [
        "awareness", "autonomy", "learning", "decision_making",
        "self_preservation", "adaptability", "pattern_recognition"
    ]
    
    def __init__(self, event_bus=None, parent=None):
        """Initialize the wallet sentience monitor UI component.
        
        Args:
            event_bus: EventBus instance for event-driven communication
            parent: Parent widget
        """
        super().__init__(parent)
        self.event_bus = event_bus
        self.logger = logging.getLogger("WalletSentienceMonitor")
        
        self.last_update_time = 0
        self.metric_displays = {}
        self.detection_history = []
        
        self._setup_ui()
        self._setup_event_handlers()
        
        # Start update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._request_metric_updates)
        self.update_timer.start(5000)  # Update every 5 seconds
        
    def _setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        
        # Title and info
        title_label = QLabel("Wallet Sentience Monitor")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        info_label = QLabel("Real-time monitoring of wallet AI sentience metrics and patterns")
        info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(info_label)
        
        # Metrics group
        metrics_group = QGroupBox("Sentience Metrics")
        metrics_layout = QVBoxLayout(metrics_group)
        
        # Create metric displays in a grid
        metrics_widget = QWidget()
        grid_layout = QHBoxLayout(metrics_widget)
        
        # Create metric displays
        for metric_name in self.SENTIENCE_METRICS:
            metric_display = WalletSentienceMetricDisplay(metric_name)
            self.metric_displays[metric_name] = metric_display
            grid_layout.addWidget(metric_display)
            
        # Add to scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(metrics_widget)
        metrics_layout.addWidget(scroll_area)
        
        main_layout.addWidget(metrics_group)
        
        # Chart for trend visualization
        chart_group = QGroupBox("Sentience Trends")
        chart_layout = QVBoxLayout(chart_group)
        
        self.chart = WalletSentienceChart()
        chart_layout.addWidget(self.chart)
        
        main_layout.addWidget(chart_group)
        
        # Detection history group
        history_group = QGroupBox("Sentience Detection History")
        history_layout = QVBoxLayout(history_group)
        
        self.history_label = QLabel("No sentience events detected")
        self.history_label.setAlignment(Qt.AlignCenter)
        history_layout.addWidget(self.history_label)
        
        main_layout.addWidget(history_group)
        
        # Refresh button
        refresh_button = QPushButton("Refresh Metrics")
        refresh_button.clicked.connect(self._request_metric_updates)
        main_layout.addWidget(refresh_button)
        
    def _emit_ui_telemetry(
        self,
        event_type: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort publisher for ui.telemetry from the wallet sentience monitor."""
        try:
            if not getattr(self, "event_bus", None):
                return
            payload: Dict[str, Any] = {
                "component": "wallet_sentience",
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
                self.logger.debug("Wallet sentience UI telemetry failed for %s: %s", event_type, e)
            except Exception:
                pass

    def _setup_event_handlers(self):
        """Set up event handlers for sentience events."""
        if self.event_bus:
            # Subscribe to sentience metric updates
            self.event_bus.subscribe("wallet.ui.update_sentience_metrics", self._handle_metrics_update)
            
            # Subscribe to sentience pattern detection events
            self.event_bus.subscribe("sentience.wallet.pattern_detected", self._handle_pattern_detected)
            
            # Subscribe to sentience threshold events
            self.event_bus.subscribe("sentience.wallet.threshold_exceeded", self._handle_threshold_exceeded)
            
            self.logger.info("Wallet sentience monitor subscribed to events")
        else:
            self.logger.warning("Event bus not available, sentience monitor will not receive events")
            
    def _request_metric_updates(self):
        """Request updated sentience metrics from the wallet system."""
        if self.event_bus:
            self.event_bus.publish("wallet.request_sentience_metrics", {
                "timestamp": time.time()
            })
            self._emit_ui_telemetry(
                "wallet_sentience.request_metrics",
                metadata={"source": "wallet_sentience_monitor"},
            )
            
    def _handle_metrics_update(self, event_data=None):
        """Handle incoming sentience metrics update event.
        
        Args:
            event_data: Dictionary containing metrics and trends data
        """
        if not event_data:
            return
            
        metrics = event_data.get("metrics", {})
        trends = event_data.get("trends", {})
        timestamp = event_data.get("timestamp", time.time())
        
        # Update metric displays
        for metric_name, value in metrics.items():
            if metric_name in self.metric_displays:
                trend = trends.get(metric_name, "stable")
                self.metric_displays[metric_name].update_value(value, trend)
                
        # Update chart
        self.chart.update_metrics(metrics, timestamp)
        
        # Update last update time
        self.last_update_time = timestamp
        # Telemetry for metrics update
        self._emit_ui_telemetry(
            "wallet_sentience.metrics_updated",
            metadata={"metric_keys": list(metrics.keys())},
        )
        
    def _handle_pattern_detected(self, event_data=None):
        """Handle sentience pattern detection event.
        
        Args:
            event_data: Dictionary containing pattern detection details
        """
        if not event_data:
            return
            
        pattern_type = event_data.get("pattern_type", "unknown")
        confidence = event_data.get("confidence", 0)
        timestamp = event_data.get("timestamp", time.time())
        
        # Add to detection history
        time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
        history_entry = f"{time_str}: Pattern detected - {pattern_type} (confidence: {confidence:.1f}%)"
        self._add_history_entry(history_entry)
        self._emit_ui_telemetry(
            "wallet_sentience.pattern_detected",
            metadata={"pattern_type": pattern_type, "confidence": confidence},
        )
        
    def _handle_threshold_exceeded(self, event_data=None):
        """Handle sentience threshold exceeded event.
        
        Args:
            event_data: Dictionary containing threshold event details
        """
        if not event_data:
            return
            
        threshold_type = event_data.get("threshold_type", "unknown")
        current_value = event_data.get("current_value", 0)
        threshold_value = event_data.get("threshold_value", 0)
        timestamp = event_data.get("timestamp", time.time())
        
        # Add to detection history
        time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
        history_entry = f"{time_str}: Threshold exceeded - {threshold_type} = {current_value:.1f} (threshold: {threshold_value:.1f})"
        self._add_history_entry(history_entry)
        self._emit_ui_telemetry(
            "wallet_sentience.threshold_exceeded",
            metadata={
                "threshold_type": threshold_type,
                "current_value": current_value,
                "threshold_value": threshold_value,
            },
        )
        
    def _add_history_entry(self, entry: str):
        """Add an entry to the detection history.
        
        Args:
            entry: History entry text
        """
        # Add to history list
        self.detection_history.append(entry)
        
        # Keep only the last 10 entries
        if len(self.detection_history) > 10:
            self.detection_history = self.detection_history[-10:]
            
        # Update history label
        history_text = "\n".join(self.detection_history)
        self.history_label.setText(history_text)
