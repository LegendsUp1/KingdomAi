#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
System Indicator Widget Module for Kingdom AI

This module provides system status indicator widgets for the Kingdom AI GUI system,
allowing real-time display of component status, connection state, and system health.
"""

import logging
from typing import Optional, Dict, Any, List, Union

try:
    from PyQt6.QtWidgets import (
        QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
        QSizePolicy, QFrame, QGridLayout, QToolTip
    )
    from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QMouseEvent
    from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
except ImportError:
    logging.warning("PyQt6 not available; SystemIndicator will have limited functionality")
    # Provide stub classes for type checking
    class QWidget:
        def __init__(self, *args, **kwargs): pass
    class QColor:
        def __init__(self, *args, **kwargs): pass
        def lighter(self, factor): return self
    class pyqtSignal:
        def __init__(self, *args, **kwargs): pass

# Try to import our LED indicator
try:
    from .led_indicator import QLedIndicator
except ImportError:
    logging.warning("LED indicator not available; will use simplified indicators")
    # Provide a stub class for QLedIndicator
    class QLedIndicator:
        def __init__(self, *args, **kwargs): pass
        def setState(self, state): pass

logger = logging.getLogger(__name__)

class SystemStatusIndicator(QWidget):
    """Widget that displays the current status of various system components using LEDs."""
    
    statusChanged = pyqtSignal(str, bool)  # Component name, status (True=online, False=offline)
    
    def __init__(self, parent=None):
        """Initialize the system indicator widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.indicators = {}  # Dictionary to store indicators by component name
        self.component_status = {}  # Dictionary to store component status
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        # Create layout
        self.layout = QGridLayout(self)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # Add title
        title_label = QLabel("System Status")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title_label, 0, 0, 1, 2)
        
        # Add default indicators
        self.add_indicator("Redis", "Redis connection status")
        self.add_indicator("Blockchain", "Blockchain connection status")
        self.add_indicator("API", "API connection status")
        self.add_indicator("Market Data", "Market data stream status")
        self.add_indicator("Trading", "Trading system status")
        self.add_indicator("AI", "AI subsystem status")
        
        # Set initial states (all offline)
        for component in self.indicators:
            self.set_status(component, False)
    
    def add_indicator(self, component_name: str, tooltip: str = ""):
        """Add a new indicator for a component.
        
        Args:
            component_name: Name of the component
            tooltip: Tooltip to display when hovering over the indicator
        """
        row = len(self.indicators) + 1  # +1 because row 0 is the title
        
        # Create label for component name
        label = QLabel(component_name)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if tooltip:
            label.setToolTip(tooltip)
        self.layout.addWidget(label, row, 0)
        
        # Create LED indicator
        led = QLedIndicator(
            self, 
            on_color=QColor("#00FF00"),  # Green for online
            off_color=QColor("#FF0000"),  # Red for offline
            size=12, 
            shape="circle"
        )
        # Add tooltip if QWidget implements it
        if hasattr(led, 'setToolTip'):
            led.setToolTip(tooltip)
        self.layout.addWidget(led, row, 1)
        
        # Store indicator reference
        self.indicators[component_name] = {
            "led": led,
            "label": label,
            "tooltip": tooltip
        }
    
    def set_status(self, component_name: str, status: bool) -> bool:
        """Set the status of a component.
        
        Args:
            component_name: Name of the component
            status: True if the component is online, False otherwise
            
        Returns:
            True if the status was set successfully, False otherwise
        """
        if component_name not in self.indicators:
            logger.warning(f"Cannot set status for unknown component: {component_name}")
            return False
        
        # Update LED indicator
        self.indicators[component_name]["led"].setState(status)
        
        # Update tooltip with status
        status_text = "Online" if status else "Offline"
        tooltip = f"{self.indicators[component_name]['tooltip']} - {status_text}"
        self.indicators[component_name]["led"].setToolTip(tooltip)
        
        # Store status
        self.component_status[component_name] = status
        
        # Emit status changed signal
        self.statusChanged.emit(component_name, status)
        
        return True
    
    def get_status(self, component_name: str) -> Optional[bool]:
        """Get the status of a component.
        
        Args:
            component_name: Name of the component
            
        Returns:
            True if the component is online, False if offline, None if unknown
        """
        return self.component_status.get(component_name)
    
    def update_from_status_data(self, status_data: Dict[str, Any]) -> None:
        """Update indicators based on a status data dictionary.
        
        Args:
            status_data: Dictionary containing component status information
        """
        for component, status in status_data.items():
            # Handle different status data formats
            if isinstance(status, bool):
                self.set_status(component, status)
            elif isinstance(status, dict) and "online" in status:
                self.set_status(component, status["online"])
            elif isinstance(status, str):
                self.set_status(component, status.lower() == "online" or status.lower() == "connected")

# For testing
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    indicator = SystemIndicator()
    indicator.show()
    
    # Simulate status updates
    indicator.set_status("Redis", True)
    indicator.set_status("Blockchain", False)
    indicator.set_status("API", True)
    
    sys.exit(app.exec())
