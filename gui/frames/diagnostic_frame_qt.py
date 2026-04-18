#!/usr/bin/env python3
"""
Kingdom AI - Diagnostic Frame (PyQt6)

PyQt6 version of the diagnostic frame for system health monitoring.
"""

import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSlot

from gui.frames.base_frame_qt import BaseFrameQt
from core.event_bus import EventBus

logger = logging.getLogger("KingdomAI.DiagnosticFrame")

class DiagnosticsFrame(BaseFrameQt):
    """PyQt6 Frame for system diagnostics and health monitoring."""
    
    def __init__(self, parent=None, event_bus: Optional[EventBus] = None, api_key_connector=None, **kwargs):
        """Initialize the diagnostic frame."""
        super().__init__(parent, event_bus=event_bus, **kwargs)
        self.api_key_connector = api_key_connector
        
        # Initialize state
        self.component_statuses = {}
        self.event_counter = 0
        self.event_history = []
        self.max_event_history = 100
        
        # API keys status
        self.api_key_statuses = {}
        self.api_services = [
            'binance', 'coinbase', 'kraken', 'kucoin', 'bitfinex',
            'openai', 'claude', 'stability',
            'infura', 'alchemy',
            'alphavantage', 'finnhub',
            'ethermine', 'flypool', 'f2pool'
        ]
        
        # Create widgets
        self._create_widgets()
        
        # Subscribe to events
        self._subscribe_to_events()
    
    def _create_widgets(self):
        """Create widgets for the diagnostic frame."""
        layout = self.main_layout
        
        # Control area
        control_frame = QFrame()
        control_layout = QHBoxLayout(control_frame)
        
        title_label = QLabel("System Diagnostics")
        title_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        control_layout.addWidget(title_label)
        control_layout.addStretch()
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self._on_refresh)
        control_layout.addWidget(refresh_button)
        
        test_button = QPushButton("Test Event Bus")
        test_button.clicked.connect(self._on_test_event_bus)
        control_layout.addWidget(test_button)
        
        clear_button = QPushButton("Clear Events")
        clear_button.clicked.connect(self._on_clear_events)
        control_layout.addWidget(clear_button)
        
        layout.addWidget(control_frame)
        
        # Notebook for different diagnostic views
        self.notebook = QTabWidget()
        layout.addWidget(self.notebook)
        
        # Component status tab
        self.status_frame = QWidget()
        status_layout = QVBoxLayout(self.status_frame)
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(3)
        self.status_table.setHorizontalHeaderLabels(["Component", "Status", "Last Update"])
        self.status_table.horizontalHeader().setStretchLastSection(True)
        status_layout.addWidget(self.status_table)
        self.notebook.addTab(self.status_frame, "Component Status")
        
        # API keys tab
        self.api_keys_frame = QWidget()
        api_layout = QVBoxLayout(self.api_keys_frame)
        self.api_keys_tree = QTreeWidget()
        self.api_keys_tree.setHeaderLabels(["Service", "Status", "Key"])
        self.api_keys_tree.header().setStretchLastSection(True)
        api_layout.addWidget(self.api_keys_tree)
        self.notebook.addTab(self.api_keys_frame, "API Keys")
        
        # Event log tab
        self.event_frame = QWidget()
        event_layout = QVBoxLayout(self.event_frame)
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        event_layout.addWidget(self.event_log)
        self.notebook.addTab(self.event_frame, "Event Log")
    
    def _subscribe_to_events(self):
        """Subscribe to relevant events."""
        if self.event_bus:
            self.event_bus.subscribe("system.status", self._on_system_status)
            self.event_bus.subscribe("component.status", self._on_component_status)
            self.event_bus.subscribe("*", self._on_any_event)
    
    @pyqtSlot()
    def _on_refresh(self):
        """Refresh diagnostic information."""
        self._update_component_statuses()
        self._update_api_keys()
    
    @pyqtSlot()
    def _on_test_event_bus(self):
        """Test event bus functionality."""
        if self.event_bus:
            self.event_bus.publish("diagnostic.test", {"timestamp": datetime.now().isoformat()})
            self._log("Test event published", level=logging.INFO)
    
    @pyqtSlot()
    def _on_clear_events(self):
        """Clear event log."""
        self.event_log.clear()
        self.event_history.clear()
        self.event_counter = 0
    
    def _on_system_status(self, data: dict):
        """Handle system status updates."""
        self._update_component_statuses()
    
    def _on_component_status(self, data: dict):
        """Handle component status updates."""
        component = data.get("component", "unknown")
        status = data.get("status", "unknown")
        self.component_statuses[component] = {
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        self._update_component_statuses()
    
    def _on_any_event(self, event_type: str, data: dict):
        """Handle any event for logging."""
        self.event_counter += 1
        event_entry = f"[{datetime.now().strftime('%H:%M:%S')}] {event_type}: {data}"
        self.event_history.append(event_entry)
        if len(self.event_history) > self.max_event_history:
            self.event_history.pop(0)
        
        # Update log display
        if self.event_log:
            self.event_log.append(event_entry)
            # Auto-scroll to bottom
            scrollbar = self.event_log.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _update_component_statuses(self):
        """Update component status table."""
        if not hasattr(self, 'status_table'):
            return
        
        self.status_table.setRowCount(len(self.component_statuses))
        for row, (component, info) in enumerate(self.component_statuses.items()):
            self.status_table.setItem(row, 0, QTableWidgetItem(component))
            self.status_table.setItem(row, 1, QTableWidgetItem(info.get("status", "unknown")))
            self.status_table.setItem(row, 2, QTableWidgetItem(info.get("timestamp", "")))
    
    def _update_api_keys(self):
        """Update API keys tree."""
        if not hasattr(self, 'api_keys_tree') or not self.api_key_connector:
            return
        
        self.api_keys_tree.clear()
        for service in self.api_services:
            item = QTreeWidgetItem(self.api_keys_tree)
            item.setText(0, service)
            try:
                key = self.api_key_connector.get_api_key(service)
                if key:
                    item.setText(1, "✓ Configured")
                    item.setText(2, key[:8] + "..." if len(key) > 8 else key)
                else:
                    item.setText(1, "✗ Not configured")
            except Exception as e:
                item.setText(1, f"Error: {e}")

# Alias for compatibility
DiagnosticFrame = DiagnosticsFrame
