#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR Performance Monitor Widget

This module provides performance monitoring for the VR system,
including frame rate, latency, and system resource usage.
"""

import logging
import time

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None
from typing import Dict, Any, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, QSize, QRectF, QPointF, QLineF, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QFont,
    QFontMetrics, QPainterPath, QConicalGradient, QRadialGradient
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QCheckBox, QSlider, QGroupBox, QFormLayout, QScrollArea, QFrame,
    QSizePolicy, QToolButton, QMenu, QGridLayout, QSpacerItem, QGraphicsDropShadowEffect
)

logger = logging.getLogger(__name__)

class PerformanceGauge(QWidget):
    """Custom gauge widget for displaying performance metrics."""
    
    def __init__(self, title: str, min_value: float = 0, max_value: float = 100,
                 units: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.min_value = min_value
        self.max_value = max_value
        self.units = units
        self.value = min_value
        self.thresholds = [
            (0.7, QColor(0, 200, 0)),   # Green
            (0.9, QColor(255, 200, 0)), # Yellow
            (1.0, QColor(200, 0, 0))    # Red
        ]
        self.history = []
        self.max_history = 60  # Last 60 values for trend
        
        # Set fixed size
        self.setMinimumSize(120, 120)
        self.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding,
            QSizePolicy.Policy.MinimumExpanding
        )
        
        # Add shadow effect
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(3, 3)
        self.setGraphicsEffect(self.shadow)
    
    def set_value(self, value: float):
        """Set the current value and update the history."""
        self.value = max(self.min_value, min(self.max_value, value))
        self.history.append(self.value)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        self.update()
    
    def paintEvent(self, event):
        """Paint the gauge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(30, 30, 30, 200))
        
        # Calculate metrics
        size = min(self.width(), self.height())
        padding = 10
        radius = (size - 2 * padding) / 2
        center = self.rect().center()
        
        # Draw gauge background
        pen = QPen(QColor(60, 60, 60), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # 2025 STATE-OF-THE-ART: Use QPointF for proper PyQt6 type handling
        # 2025 FIX: Use QPointF and proper radius types for PyQt6
        painter.drawEllipse(QPointF(center.x(), center.y()), float(radius), float(radius))
        
        # Draw gauge arc with gradient
        gradient = QConicalGradient(QPointF(center.x(), center.y()), -90)
        for ratio, color in self.thresholds:
            gradient.setColorAt(1.0 - ratio, color)
        
        pen = QPen(gradient, 8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        start_angle = 45 * 16
        span_angle = 270 * 16
        rect = QRectF(
            center.x() - radius + padding,
            center.y() - radius + padding,
            (radius - padding) * 2,
            (radius - padding) * 2
        )
        painter.drawArc(rect, start_angle, span_angle)
        
        # Draw value arc
        value_ratio = (self.value - self.min_value) / (self.max_value - self.min_value)
        value_angle = int(270 * value_ratio)
        
        # Get color based on value ratio
        color = QColor(255, 255, 255)
        for threshold, threshold_color in self.thresholds:
            if value_ratio <= threshold:
                color = threshold_color
                break
        
        pen = QPen(color, 10)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, start_angle, -value_angle * 16)
        
        # Draw center text
        font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(Qt.GlobalColor.white)
        
        # Draw title
        title_rect = QRectF(0, center.y() + radius * 0.7, self.width(), 20)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.title)
        
        # Draw value
        value_str = f"{self.value:.1f}{self.units}"
        value_rect = QRectF(0, center.y() - 15, self.width(), 30)
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignCenter, value_str)
        
        # Draw history graph
        if len(self.history) > 1:
            self.draw_history_graph(painter, center, radius * 0.4)
    
    def draw_history_graph(self, painter, center, radius):
        """Draw a small history graph in the center of the gauge."""
        if len(self.history) < 2:
            return
            
        path = QPainterPath()
        points = []
        
        # Calculate points
        for i, value in enumerate(self.history):
            x = center.x() - radius + (2 * radius * i) / (len(self.history) - 1)
            ratio = (value - self.min_value) / (self.max_value - self.min_value)
            y = center.y() + radius - (2 * radius * ratio)
            points.append(QPointF(x, y))
        
        # Create path
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        
        # Draw graph
        pen = QPen(QColor(0, 200, 255), 1.5)
        painter.setPen(pen)
        painter.drawPath(path)

class PerformanceGraph(QWidget):
    """A scrolling performance graph."""
    
    def __init__(self, title: str, max_samples: int = 100, parent=None):
        super().__init__(parent)
        self.title = title
        self.max_samples = max_samples
        self.values = []
        self.timestamps = []
        self.min_value = 0
        self.max_value = 100
        self.auto_range = True
        self.line_color = QColor(0, 200, 255)
        self.background = QColor(30, 30, 30, 200)
        self.grid_color = QColor(50, 50, 50)
        self.text_color = QColor(200, 200, 200)
        
        self.setMinimumHeight(100)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding
        )
        
        # Add shadow effect
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(3, 3)
        self.setGraphicsEffect(self.shadow)
    
    def add_value(self, value: float, timestamp: float = None):
        """Add a new value to the graph."""
        if timestamp is None:
            timestamp = time.time()
        
        self.values.append(value)
        self.timestamps.append(timestamp)
        
        # Trim old values
        if len(self.values) > self.max_samples:
            self.values.pop(0)
            self.timestamps.pop(0)
        
        # Update range if auto-ranging
        if self.auto_range:
            self.min_value = min(self.values) * 0.95 if self.values else 0
            self.max_value = max(self.values) * 1.05 if self.values else 100
            
            # Ensure we don't have a zero range
            if abs(self.max_value - self.min_value) < 0.001:
                self.max_value = self.min_value + 0.001
        
        self.update()
    
    def paintEvent(self, event):
        """Paint the graph."""
        if not self.values:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), self.background)
        
        # Calculate metrics
        width = self.width()
        height = self.height()
        padding = 5
        graph_rect = QRectF(
            padding, padding,
            width - 2 * padding,
            height - 2 * padding
        )
        
        # Draw grid
        self.draw_grid(painter, graph_rect)
        
        # Draw graph line
        if len(self.values) > 1:
            self.draw_graph_line(painter, graph_rect)
        
        # Draw title
        font = QFont("Arial", 8)
        painter.setFont(font)
        painter.setPen(self.text_color)
        painter.drawText(10, 15, self.title)
        
        # Draw current value
        current_value = self.values[-1]
        value_text = f"{current_value:.1f}"
        metrics = QFontMetrics(font)
        text_width = metrics.boundingRect(value_text).width()
        painter.drawText(width - text_width - 10, 15, value_text)
    
    def draw_grid(self, painter, rect):
        """Draw the grid lines and labels."""
        pen = QPen(self.grid_color, 0.5, Qt.PenStyle.DotLine)
        painter.setPen(pen)
        
        # Horizontal grid lines
        for i in range(5):
            y = rect.bottom() - (i * rect.height() / 4)
            # 2025 STATE-OF-THE-ART: Convert float to int for PyQt6 compatibility
            # 2025 FIX: Convert float coordinates to int for PyQt6 compatibility
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
            
            # Label
            value = self.min_value + (i * (self.max_value - self.min_value) / 4)
            label = f"{value:.1f}"
            painter.drawText(5, int(y - 2), label)
        
        # Time markers (if we have timestamps)
        if len(self.timestamps) > 1:
            time_range = self.timestamps[-1] - self.timestamps[0]
            if time_range > 0:
                for i in range(5):
                    x = rect.left() + (i * rect.width() / 4)
                    # FIX: Cast to int for PyQt6 compatibility
                    painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
                    
                    # Time label
                    time_pos = self.timestamps[0] + (i * time_range / 4)
                    time_str = time.strftime('%H:%M:%S', time.localtime(time_pos))
                    text_rect = QRectF(x - 25, rect.bottom() + 2, 50, 15)
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, time_str)
    
    def draw_graph_line(self, painter, rect):
        """Draw the main graph line."""
        if len(self.values) < 2:
            return
            
        path = QPainterPath()
        
        # Calculate x scale and offset
        x_scale = rect.width() / (len(self.values) - 1) if len(self.values) > 1 else 1
        y_scale = rect.height() / (self.max_value - self.min_value)
        
        # Create path
        for i, value in enumerate(self.values):
            x = rect.left() + (i * x_scale)
            y = rect.bottom() - ((value - self.min_value) * y_scale)
            
            if i == 0:
                path.moveTo(x, y)
            else:
                # Create smooth curve
                prev_x = rect.left() + ((i - 1) * x_scale)
                prev_y = rect.bottom() - ((self.values[i-1] - self.min_value) * y_scale)
                
                # Control points for smooth curve
                ctrl_x1 = prev_x + (x - prev_x) * 0.5
                ctrl_x2 = x - (x - prev_x) * 0.5
                
                path.cubicTo(
                    ctrl_x1, prev_y,
                    ctrl_x2, y,
                    x, y
                )
        
        # Draw the path
        pen = QPen(self.line_color, 1.5)
        painter.setPen(pen)
        painter.drawPath(path)
        
        # Draw gradient under the curve
        gradient_path = QPainterPath(path)
        gradient_path.lineTo(rect.right(), rect.bottom())
        gradient_path.lineTo(rect.left(), rect.bottom())
        gradient_path.closeSubpath()
        
        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        gradient.setColorAt(0, QColor(0, 200, 255, 80))
        gradient.setColorAt(1, QColor(0, 200, 255, 20))
        
        painter.fillPath(gradient_path, gradient)

class VRPerformanceMonitor(QWidget):
    """Widget for monitoring VR system performance."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_timers()
        
        # Initial values
        self.frame_times = []
        self.last_frame_time = time.time()
    
    def setup_ui(self):
        """Set up the performance monitor UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # Top row - Gauges
        gauges_layout = QHBoxLayout()
        
        # FPS Gauge
        self.fps_gauge = PerformanceGauge("FPS", 0, 120, " FPS")
        self.fps_gauge.setMinimumWidth(120)
        gauges_layout.addWidget(self.fps_gauge)
        
        # Latency Gauge
        self.latency_gauge = PerformanceGauge("Latency", 0, 50, " ms")
        self.latency_gauge.setMinimumWidth(120)
        gauges_layout.addWidget(self.latency_gauge)
        
        # CPU Gauge
        self.cpu_gauge = PerformanceGauge("CPU", 0, 100, "%")
        self.cpu_gauge.setMinimumWidth(120)
        gauges_layout.addWidget(self.cpu_gauge)
        
        # GPU Gauge (simulated)
        self.gpu_gauge = PerformanceGauge("GPU", 0, 100, "%")
        self.gpu_gauge.setMinimumWidth(120)
        gauges_layout.addWidget(self.gpu_gauge)
        
        main_layout.addLayout(gauges_layout)
        
        # Graphs
        self.fps_graph = PerformanceGraph("FPS")
        self.latency_graph = PerformanceGraph("Latency (ms)")
        self.cpu_graph = PerformanceGraph("CPU Usage (%)")
        self.gpu_graph = PerformanceGraph("GPU Usage (%)")
        
        # Add graphs to layout
        graphs_layout = QVBoxLayout()
        graphs_layout.addWidget(self.fps_graph)
        graphs_layout.addWidget(self.latency_graph)
        graphs_layout.addWidget(self.cpu_graph)
        graphs_layout.addWidget(self.gpu_graph)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_widget.setLayout(graphs_layout)
        scroll.setWidget(scroll_widget)
        
        main_layout.addWidget(scroll)
        
        # Stats labels
        stats_layout = QHBoxLayout()
        
        self.stats_label = QLabel("FPS: -- | Latency: -- ms | CPU: --% | GPU: --%")
        self.stats_label.setStyleSheet("color: #AAAAAA;")
        stats_layout.addWidget(self.stats_label)
        
        main_layout.addLayout(stats_layout)
    
    def setup_timers(self):
        """Set up timers for periodic updates."""
        # Update system stats every second
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_system_stats)
        self.stats_timer.start(1000)  # 1 second
        
        # Update frame rate every 100ms for smoother updates
        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self.update_frame_stats)
        self.frame_timer.start(100)  # 100ms
    
    def update_frame_stats(self):
        """Update frame rate and latency statistics."""
        current_time = time.time()
        frame_time = (current_time - self.last_frame_time) * 1000  # in ms
        self.last_frame_time = current_time
        
        # Add to frame times
        self.frame_times.append(frame_time)
        if len(self.frame_times) > 60:  # Keep last 60 frames
            self.frame_times.pop(0)
        
        # Calculate FPS (average over last 10 frames)
        if len(self.frame_times) > 0:
            avg_frame_time = sum(self.frame_times[-10:]) / min(10, len(self.frame_times))
            fps = 1000.0 / avg_frame_time if avg_frame_time > 0 else 0
            
            # Update gauges
            self.fps_gauge.set_value(fps)
            self.latency_gauge.set_value(avg_frame_time)
            
            # Update graphs
            self.fps_graph.add_value(fps)
            self.latency_graph.add_value(avg_frame_time)
    
    def update_system_stats(self):
        """Update system statistics (CPU, GPU, etc.)."""
        # CPU usage
        cpu_percent = psutil.cpu_percent() if HAS_PSUTIL else 0.0
        self.cpu_gauge.set_value(cpu_percent)
        self.cpu_graph.add_value(cpu_percent)
        
        # GPU usage (simulated)
        # In a real application, you would query the GPU here
        gpu_percent = ((psutil.cpu_percent() if HAS_PSUTIL else 0.0) * 0.7) % 100
        self.gpu_gauge.set_value(gpu_percent)
        self.gpu_graph.add_value(gpu_percent)
        
        # Update stats label
        fps = self.fps_gauge.value
        latency = self.latency_gauge.value
        self.stats_label.setText(
            f"FPS: {fps:.1f} | "
            f"Latency: {latency:.1f} ms | "
            f"CPU: {cpu_percent:.1f}% | "
            f"GPU: {gpu_percent:.1f}%"
        )
    
    def update_vr_performance_metrics(self, metrics: Dict[str, float]):
        """Update performance metrics from VR system.
        
        Args:
            metrics: Dictionary containing performance metrics
        """
        if 'fps' in metrics:
            self.fps_gauge.set_value(metrics['fps'])
            self.fps_graph.add_value(metrics['fps'])
            
        if 'latency' in metrics:
            self.latency_gauge.set_value(metrics['latency'])
            self.latency_graph.add_value(metrics['latency'])
            
        if 'cpu_usage' in metrics:
            self.cpu_gauge.set_value(metrics['cpu_usage'])
            self.cpu_graph.add_value(metrics['cpu_usage'])
            
        if 'gpu_usage' in metrics:
            self.gpu_gauge.set_value(metrics['gpu_usage'])
            self.gpu_graph.add_value(metrics['gpu_usage'])
        
        # Update stats label
        self.stats_label.setText(
            f"FPS: {metrics.get('fps', 0):.1f} | "
            f"Latency: {metrics.get('latency', 0):.1f} ms | "
            f"CPU: {metrics.get('cpu_usage', 0):.1f}% | "
            f"GPU: {metrics.get('gpu_usage', 0):.1f}%"
        )

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Set dark theme
    app.setStyle("Fusion")
    
    window = VRPerformanceMonitor()
    window.setWindowTitle("VR Performance Monitor")
    window.resize(800, 600)
    window.show()
    
    sys.exit(app.exec())
