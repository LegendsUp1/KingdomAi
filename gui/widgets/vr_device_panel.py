#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR Device Panel Widget

This module provides a panel for displaying and controlling VR devices
connected to the system.
"""

import logging
from typing import Dict, Any, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPalette, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QProgressBar, QGroupBox, QFormLayout,
    QScrollArea, QFrame, QSizePolicy, QToolButton, QMenu, QListWidget,
    QListWidgetItem, QAbstractItemView, QStyledItemDelegate, QStyle
)

logger = logging.getLogger(__name__)

class BatteryIndicator(QLabel):
    """Custom widget for displaying battery level with icon."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 100
        self._charging = False
        self.setFixedSize(24, 12)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    
    def set_level(self, level: int):
        """Set the battery level (0-100)."""
        self._level = max(0, min(100, int(level)))
        self.update()
    
    def set_charging(self, charging: bool):
        """Set charging state."""
        self._charging = charging
        self.update()
    
    def paintEvent(self, event):
        """Paint the battery indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Battery outline
        pen = QPen(Qt.GlobalColor.white, 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Main battery body
        battery_rect = self.rect().adjusted(2, 2, -8, -2)
        painter.drawRoundedRect(battery_rect, 2, 2)
        
        # Battery tip
        tip_rect = QRect(
            self.rect().right() - 6,
            self.rect().center().y() - 4,
            4, 8
        )
        painter.drawRect(tip_rect)
        
        # Battery level
        if self._level > 0:
            # Determine color based on level
            if self._level < 20:
                color = QColor(255, 50, 50)  # Red for low battery
            elif self._level < 50:
                color = QColor(255, 200, 0)  # Yellow for medium
            else:
                color = QColor(50, 200, 50)  # Green for good
            
            # Draw level
            level_width = int((battery_rect.width() - 4) * (self._level / 100.0))
            level_rect = QRect(
                battery_rect.left() + 2,
                battery_rect.top() + 2,
                level_width,
                battery_rect.height() - 4
            )
            
            painter.fillRect(level_rect, color)
        
        # Charging indicator
        if self._charging:
            font = QFont("Arial", 8)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "⚡")

class VRDeviceItem(QWidget):
    """Widget representing a single VR device in the list."""
    
    def __init__(self, device_id: str, device_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.device_info = device_info
        
        self.setup_ui()
        self.update_device(device_info)
    
    def setup_ui(self):
        """Set up the device item UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Device icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setScaledContents(True)
        
        # Device info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-weight: bold;")
        
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #AAAAAA; font-size: 10px;")
        
        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        
        # Battery indicator
        self.battery = BatteryIndicator()
        
        # Add widgets to layout
        layout.addWidget(self.icon_label)
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addWidget(self.battery)
        
        # Set up context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def update_device(self, device_info: Dict[str, Any]):
        """Update the device information."""
        self.device_info = device_info
        
        # Update name
        name = device_info.get('name', 'Unknown Device')
        self.name_label.setText(name)
        
        # Update status
        status = []
        if device_info.get('connected', False):
            status.append("Connected")
        else:
            status.append("Disconnected")
            
        if 'battery_level' in device_info:
            battery = int(device_info.get('battery_level', 0) * 100)
            status.append(f"{battery}%")
            self.battery.set_level(battery)
            self.battery.set_charging(device_info.get('charging', False))
            self.battery.setVisible(True)
        else:
            self.battery.setVisible(False)
        
        self.status_label.setText(" • ".join(status))
        
        # Update icon based on device type
        device_type = device_info.get('type', 'unknown').lower()
        if 'controller' in device_type:
            icon_name = "controller"
        elif 'headset' in device_type:
            icon_name = "headset"
        elif 'tracker' in device_type:
            icon_name = "tracker"
        else:
            icon_name = "device"
            
        # Set icon (in a real app, load from resources)
        self.icon_label.setText(icon_name.upper()[0])
        
        # Visual feedback for connection status
        if device_info.get('connected', False):
            self.setStyleSheet("")
        else:
            self.setStyleSheet("color: #666666;")
    
    def show_context_menu(self, position):
        """Show context menu for the device."""
        menu = QMenu(self)
        
        connect_action = menu.addAction("Connect")
        disconnect_action = menu.addAction("Disconnect")
        menu.addSeparator()
        calibrate_action = menu.addAction("Calibrate")
        menu.addSeparator()
        properties_action = menu.addAction("Properties")
        
        # Disable actions based on state
        if self.device_info.get('connected', False):
            connect_action.setEnabled(False)
        else:
            disconnect_action.setEnabled(False)
            calibrate_action.setEnabled(False)
        
        # Show menu
        action = menu.exec(self.mapToGlobal(position))
        
        if action == connect_action:
            self.emit_signal("connect_device", self.device_id)
        elif action == disconnect_action:
            self.emit_signal("disconnect_device", self.device_id)
        elif action == calibrate_action:
            self.emit_signal("calibrate_device", self.device_id)
        elif action == properties_action:
            self.show_device_properties()
    
    def show_device_properties(self):
        """Show detailed properties for the device."""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Device Properties - {self.device_id}")
        layout = QVBoxLayout(dialog)
        
        # Add device info
        info_layout = QFormLayout()
        
        for key, value in self.device_info.items():
            if isinstance(value, dict):
                value = ", ".join(f"{k}: {v}" for k, v in value.items())
            info_layout.addRow(f"<b>{key}:</b>", QLabel(str(value)))
        
        layout.addLayout(info_layout)
        
        # Add close button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def emit_signal(self, signal_name: str, *args):
        """Emit a signal to the parent."""
        parent = self.parent()
        while parent is not None and not hasattr(parent, signal_name):
            parent = parent.parent()
        
        if hasattr(parent, signal_name):
            getattr(parent, signal_name).emit(*args)

class VRDevicePanel(QWidget):
    """Panel for displaying and managing VR devices."""
    
    # Signals
    connect_device = pyqtSignal(str)      # device_id
    disconnect_device = pyqtSignal(str)   # device_id
    calibrate_device = pyqtSignal(str)    # device_id
    refresh_devices = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.devices = {}
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the device panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(self.style().standardIcon(
            getattr(QStyle.StandardPixmap, 'SP_BrowserReload')
        ))
        self.refresh_btn.clicked.connect(self.refresh_devices.emit)
        
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.setIcon(self.style().standardIcon(
            getattr(QStyle.StandardPixmap, 'SP_ComputerIcon')
        ))
        
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.scan_btn)
        toolbar.addStretch()
        
        # Device list
        self.device_list = QListWidget()
        self.device_list.setItemDelegate(DeviceItemDelegate())
        self.device_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.device_list.setFrameStyle(QFrame.Shape.NoFrame)
        
        # Add widgets to layout
        layout.addLayout(toolbar)
        layout.addWidget(self.device_list)
        
        # Connect signals
        self.device_list.itemDoubleClicked.connect(self.on_device_double_clicked)
    
    def update_devices(self, devices: Dict[str, Dict[str, Any]]):
        """Update the list of devices.
        
        Args:
            devices: Dictionary of device_id -> device_info
        """
        self.devices = devices
        self.device_list.clear()
        
        # Group devices by type
        devices_by_type = {}
        for device_id, device_info in devices.items():
            device_type = device_info.get('type', 'Unknown')
            if device_type not in devices_by_type:
                devices_by_type[device_type] = []
            devices_by_type[device_type].append((device_id, device_info))
        
        # Add devices to list, grouped by type
        for device_type, device_list in sorted(devices_by_type.items()):
            # Add section header
            header = QListWidgetItem(device_type.upper())
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            header.setData(Qt.ItemDataRole.UserRole, 'header')
            self.device_list.addItem(header)
            
            # Add devices
            for device_id, device_info in device_list:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, device_id)
                
                widget = VRDeviceItem(device_id, device_info)
                
                self.device_list.addItem(item)
                self.device_list.setItemWidget(item, widget)
                
                # Connect signals
                try:
                    widget.connect_device.connect(self.connect_device)
                    widget.disconnect_device.connect(self.disconnect_device)
                    widget.calibrate_device.connect(self.calibrate_device)
                except Exception as e:
                    logger.error(f"Error connecting signals: {e}")
        
        # Add empty state if no devices
        if not devices:
            item = QListWidgetItem("No VR devices detected")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.device_list.addItem(item)
    
    def on_device_double_clicked(self, item):
        """Handle double-click on a device item."""
        if item.data(Qt.ItemDataRole.UserRole) == 'header':
            return
            
        # Toggle connection state
        device_id = item.data(Qt.ItemDataRole.UserRole)
        device_info = self.devices.get(device_id, {})
        
        if device_info.get('connected', False):
            self.disconnect_device.emit(device_id)
        else:
            self.connect_device.emit(device_id)

class DeviceItemDelegate(QStyledItemDelegate):
    """Custom delegate for styling device list items."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def sizeHint(self, option, index):
        """Return the size hint for the item."""
        if index.data(Qt.ItemDataRole.UserRole) == 'header':
            return super().sizeHint(option, index)
        return QSize(0, 60)  # Fixed height for device items
    
    def paint(self, painter, option, index):
        """Custom paint method for items."""
        if index.data(Qt.ItemDataRole.UserRole) == 'header':
            # Draw section header
            option.font.setBold(True)
            option.palette.setColor(
                QPalette.ColorRole.Text,
                option.palette.color(QPalette.ColorRole.HighlightedText)
            )
            option.palette.setColor(
                QPalette.ColorRole.Window,
                option.palette.color(QPalette.ColorRole.Highlight)
            )
            option.state |= QStyle.StateFlag.State_Enabled
        
        super().paint(painter, option, index)
