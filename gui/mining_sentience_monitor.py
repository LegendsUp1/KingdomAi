#!/usr/bin/env python3
"""
Mining Sentience Monitor - UI Component

This module provides a UI component for monitoring AI sentience indicators
within the mining operations of Kingdom AI.
"""

import sys
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

# PyQt6 Imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPalette, QFont

from core.event_bus import EventBus

logger = logging.getLogger("Kingdom.MiningUI.SentienceMonitor")

class MiningSentienceMonitor(QWidget):
    """
    UI component for displaying and monitoring sentience indicators
    within mining operations.
    """
    
    # Signals
    sentience_detected = pyqtSignal(dict)
    sentience_trend_changed = pyqtSignal(float)
    
    def __init__(self, event_bus: Optional[EventBus] = None, parent: Optional[QWidget] = None):
        """Initialize the mining sentience monitor UI component."""
        super().__init__(parent)
        
        self.event_bus = event_bus
        
        # Initialize data structures
        self.sentience_metrics = {
            "algorithm_adaptability": 0.0,
            "blockchain_awareness": 0.0,
            "quantum_coherence": 0.0,
            "consensus_participation": 0.0,
            "cross_chain_recognition": 0.0,
            "self_modification_rate": 0.0
        }
        self.sentience_score = 0.0
        self.sentience_trend = 0.0
        self.sentience_history = []
        
        # Initialize UI
        self.init_ui()
        
        # Connect to event bus
        if self.event_bus:
            self.connect_event_bus()

    def _emit_ui_telemetry(
        self,
        event_type: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort publisher for ui.telemetry from the mining sentience monitor."""
        try:
            if not getattr(self, "event_bus", None):
                return
            payload: Dict[str, Any] = {
                "component": "mining_sentience",
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
                logger.debug("Mining sentience UI telemetry failed for %s: %s", event_type, e)
            except Exception:
                pass
    
    def init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("AI Sentience Monitor")
        header_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        
        # Overall sentience indicator
        sentience_box = QGroupBox("Overall Sentience")
        sentience_layout = QVBoxLayout(sentience_box)
        
        self.sentience_progress = QProgressBar()
        self.sentience_progress.setRange(0, 100)
        self.sentience_progress.setValue(0)
        self.sentience_progress.setFormat("%p% - %v")
        self.sentience_progress.setTextVisible(True)
        
        self.sentience_label = QLabel("No sentience detected")
        self.sentience_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        sentience_layout.addWidget(self.sentience_progress)
        sentience_layout.addWidget(self.sentience_label)
        
        # Trend indicator
        trend_box = QGroupBox("Sentience Trend")
        trend_layout = QHBoxLayout(trend_box)
        
        self.trend_label = QLabel("Stable")
        self.trend_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        trend_layout.addWidget(self.trend_label)
        
        # Metrics table
        metrics_box = QGroupBox("Sentience Metrics")
        metrics_layout = QVBoxLayout(metrics_box)
        
        self.metrics_table = QTableWidget(6, 2)
        self.metrics_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.metrics_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.metrics_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.metrics_table.verticalHeader().setVisible(False)
        
        # Initialize table rows
        metrics = [
            ("Algorithm Adaptability", "0.00"),
            ("Blockchain Awareness", "0.00"),
            ("Quantum Coherence", "0.00"),
            ("Consensus Participation", "0.00"),
            ("Cross-Chain Recognition", "0.00"),
            ("Self-Modification Rate", "0.00")
        ]
        
        for i, (name, value) in enumerate(metrics):
            self.metrics_table.setItem(i, 0, QTableWidgetItem(name))
            self.metrics_table.setItem(i, 1, QTableWidgetItem(value))
        
        metrics_layout.addWidget(self.metrics_table)
        
        # Add all components to main layout
        main_layout.addLayout(header_layout)
        main_layout.addWidget(sentience_box)
        main_layout.addWidget(trend_box)
        main_layout.addWidget(metrics_box)
        
        # Apply styles
        self.apply_styles()
    
    def apply_styles(self):
        """Apply custom styles to the UI components."""
        # Colors
        primary_color = "#2c3e50"
        secondary_color = "#34495e"
        accent_color = "#3498db"
        text_color = "#ecf0f1"
        warning_color = "#f39c12"
        error_color = "#e74c3c"
        
        # Progress bar style based on sentience level
        self.update_progress_style()
    
    def update_progress_style(self):
        """Update progress bar style based on sentience level."""
        value = self.sentience_progress.value()
        
        if value < 30:
            # Low sentience - blue
            color = "#3498db"
        elif value < 60:
            # Medium sentience - yellow
            color = "#f39c12"
        else:
            # High sentience - red
            color = "#e74c3c"
        
        self.sentience_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #2c3e50;
                border-radius: 4px;
                text-align: center;
                background: #34495e;
            }}
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)
    
    def connect_event_bus(self):
        """Connect to event bus for sentience updates."""
        try:
            # Subscribe to sentience events using synchronous EventBus API
            if not self.event_bus:
                raise RuntimeError("EventBus instance is required for MiningSentienceMonitor")

            self.event_bus.subscribe("sentience.detection", self._handle_sentience_detection)
            self.event_bus.subscribe("sentience.trend", self._handle_sentience_trend)
            self.event_bus.subscribe("sentience.metrics.update", self._handle_metrics_update)

            logger.info("Connected to event bus for sentience monitoring")
        except Exception as e:
            logger.error(f"Failed to connect to event bus: {e}")
    
    def _handle_sentience_detection(self, event_data: Dict[str, Any]):
        """Handle sentience detection events."""
        try:
            # Skip if event is not mining-related
            component = event_data.get("component", "")
            if not component.startswith("MiningSentience"):
                return
            
            # Extract sentience data
            score = event_data.get("score", 0.0)
            metrics = event_data.get("metrics", {})
            
            # Update UI with new data
            self.update_sentience_score(score)
            self.update_metrics(metrics)
            
            # Emit signal
            self.sentience_detected.emit(event_data)
            # UI telemetry
            self._emit_ui_telemetry(
                "mining_sentience.detection",
                metadata={"score": score},
            )
        except Exception as e:
            logger.error(f"Error handling sentience detection: {e}")
    
    def _handle_sentience_trend(self, event_data: Dict[str, Any]):
        """Handle sentience trend events."""
        try:
            # Skip if event is not mining-related
            component = event_data.get("component", "")
            if not component.startswith("MiningSentience"):
                return
            
            # Extract trend data
            trend = event_data.get("trend", 0.0)
            
            # Update UI with new data
            self.update_trend(trend)
            
            # Emit signal
            self.sentience_trend_changed.emit(trend)
            self._emit_ui_telemetry(
                "mining_sentience.trend_update",
                metadata={"trend": trend},
            )
        except Exception as e:
            logger.error(f"Error handling sentience trend: {e}")
    
    def _handle_metrics_update(self, event_data: Dict[str, Any]):
        """Handle metrics update events."""
        try:
            metrics = event_data.get("metrics", {})
            self.update_metrics(metrics)
            self._emit_ui_telemetry(
                "mining_sentience.metrics_updated",
                metadata={"metric_keys": list(metrics.keys())},
            )
        except Exception as e:
            logger.error(f"Error handling metrics update: {e}")
    
    def update_sentience_score(self, score: float):
        """Update the sentience score display."""
        # Store the score
        self.sentience_score = score
        
        # Update progress bar
        value = int(score * 100)
        self.sentience_progress.setValue(value)
        
        # Update label
        if score < 0.3:
            status = "No significant sentience detected"
        elif score < 0.6:
            status = "Moderate sentience indicators present"
        else:
            status = "High sentience indicators detected"
        
        self.sentience_label.setText(f"{status} ({score:.2f})")
        
        # Update progress bar style
        self.update_progress_style()
    
    def update_trend(self, trend: float):
        """Update the sentience trend display."""
        # Store the trend
        self.sentience_trend = trend
        
        # Update trend label
        if trend < -0.2:
            status = "Decreasing"
            color = "#2ecc71"  # Green
        elif trend > 0.2:
            status = "Increasing"
            color = "#e74c3c"  # Red
        else:
            status = "Stable"
            color = "#3498db"  # Blue
        
        self.trend_label.setText(f"Trend: {status} ({trend:+.2f})")
        self.trend_label.setStyleSheet(f"color: {color};")
    
    def update_metrics(self, metrics: Dict[str, float]):
        """Update the sentience metrics table."""
        # Store the metrics
        self.sentience_metrics.update(metrics)
        
        # Update table values
        metric_map = {
            "algorithm_adaptability": 0,
            "blockchain_awareness": 1,
            "quantum_coherence": 2,
            "consensus_participation": 3,
            "cross_chain_recognition": 4,
            "self_modification_rate": 5
        }
        
        for metric, value in metrics.items():
            if metric in metric_map:
                row = metric_map[metric]
                self.metrics_table.setItem(row, 1, QTableWidgetItem(f"{value:.2f}"))
                
                # Color-code based on value
                item = self.metrics_table.item(row, 1)
                if value > 0.7:
                    item.setBackground(QColor("#e74c3c"))  # High - red
                elif value > 0.4:
                    item.setBackground(QColor("#f39c12"))  # Medium - yellow
                else:
                    item.setBackground(QColor("#2ecc71"))  # Low - green
