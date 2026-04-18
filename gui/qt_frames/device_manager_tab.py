#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Device Manager Tab for Kingdom AI - SOTA 2025/2026

Provides a comprehensive GUI for managing host system devices:
- USB/Serial devices, Bluetooth, Audio, Webcams, VR headsets
- Scan/Find controls, Connect/Disconnect actions
- Clean formatted device display with status indicators
- Real-time monitoring and event updates
"""

import logging
import subprocess
import os
import sys
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QSplitter, QFrame, QScrollArea,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QMessageBox,
    QToolButton, QMenu, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtGui import QIcon, QColor, QFont, QAction

logger = logging.getLogger("KingdomAI.DeviceManagerTab")


def _is_wsl() -> bool:
    """Detect WSL via /proc/version. Returns False on native Linux."""
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False


def _wsl_resolve_exe(name: str) -> str:
    """No-op on native Linux — returns name as-is."""
    return name

# Import device manager
try:
    from core.host_device_manager import (
        get_host_device_manager, HostDeviceManager, HostDevice,
        DeviceCategory, DeviceStatus, HostDeviceMCPTools
    )
    DEVICE_MANAGER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Host device manager not available: {e}")
    DEVICE_MANAGER_AVAILABLE = False

# Import device takeover system
try:
    from core.device_takeover_system import DeviceTakeover
    DEVICE_TAKEOVER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Device takeover system not available: {e}")
    DEVICE_TAKEOVER_AVAILABLE = False

# Import cyberpunk styling
try:
    from gui.cyberpunk_style import CYBERPUNK_THEME
except ImportError:
    CYBERPUNK_THEME = {
        'bg_primary': '#0a0a0f',
        'bg_secondary': '#12121a',
        'accent': '#00d4ff',
        'accent_secondary': '#ff00ff',
        'text_primary': '#ffffff',
        'text_secondary': '#888899',
        'success': '#00ff88',
        'warning': '#ffaa00',
        'error': '#ff4444',
        'border': '#2a2a3a'
    }

# Category icons and colors
CATEGORY_CONFIG = {
    "usb": {"icon": "🔌", "color": "#00d4ff", "label": "USB Devices"},
    "serial": {"icon": "📟", "color": "#ff9900", "label": "Serial/COM Ports"},
    "bluetooth": {"icon": "📶", "color": "#0066ff", "label": "Bluetooth"},
    "audio_input": {"icon": "🎤", "color": "#00ff88", "label": "Microphones"},
    "audio_output": {"icon": "🔊", "color": "#ff00ff", "label": "Speakers/Headphones"},
    "webcam": {"icon": "📷", "color": "#ffff00", "label": "Webcams"},
    "vr_headset": {"icon": "🥽", "color": "#ff4444", "label": "VR Headsets"},
    "controller": {"icon": "🎮", "color": "#aa00ff", "label": "Controllers"},
    "unknown": {"icon": "❓", "color": "#666666", "label": "Unknown"}
}

STATUS_CONFIG = {
    "connected": {"icon": "✅", "color": "#00ff88", "label": "Connected"},
    "disconnected": {"icon": "⚪", "color": "#666666", "label": "Disconnected"},
    "paired": {"icon": "🔗", "color": "#ffaa00", "label": "Paired"},
    "available": {"icon": "🟡", "color": "#ffff00", "label": "Available"},
    "active": {"icon": "🟢", "color": "#00ff00", "label": "Active"},
    "error": {"icon": "❌", "color": "#ff4444", "label": "Error"}
}


class DeviceScanWorker(QThread):
    """Background worker for device scanning"""
    scan_complete = pyqtSignal(dict)
    scan_error = pyqtSignal(str)
    
    def __init__(self, device_manager: HostDeviceManager):
        super().__init__()
        self.device_manager = device_manager
    
    def run(self):
        try:
            results = self.device_manager.scan_all_devices()
            self.scan_complete.emit(self.device_manager.get_summary())
        except Exception as e:
            self.scan_error.emit(str(e))


class DeviceActionWorker(QThread):
    action_complete = pyqtSignal(str, bool, str)

    def __init__(self, device_manager: HostDeviceManager, device_id: str, action: str):
        super().__init__()
        self.device_manager = device_manager
        self.device_id = device_id
        self.action = action

    def run(self):
        try:
            if self.action == "enable":
                ok = bool(self.device_manager.enable_device(self.device_id))
                self.action_complete.emit(self.device_id, ok, "enable")
                return

            if self.action == "disable":
                ok = bool(self.device_manager.disable_device(self.device_id))
                self.action_complete.emit(self.device_id, ok, "disable")
                return

            self.action_complete.emit(self.device_id, False, self.action)
        except Exception:
            self.action_complete.emit(self.device_id, False, self.action)


class DeviceManagerTab(QWidget):
    """Device Manager Tab - Comprehensive host device management interface"""
    
    # Signals
    device_selected = pyqtSignal(str)  # device_id
    device_action = pyqtSignal(str, str)  # device_id, action
    _device_event_signal = pyqtSignal(str)  # SEGFAULT FIX: thread-safe bridge for device events
    
    def __init__(self, event_bus=None, parent=None):
        super().__init__(parent)
        # SOTA 2026: Set logger FIRST to ensure it's always available for error handling
        self.logger = logging.getLogger("KingdomAI.DeviceManagerTab")
        self.event_bus = event_bus
        self.device_manager: Optional[HostDeviceManager] = None
        self.mcp_tools: Optional[HostDeviceMCPTools] = None
        self.selected_device_id: Optional[str] = None
        self._scan_worker: Optional[DeviceScanWorker] = None
        self._action_worker: Optional[DeviceActionWorker] = None
        
        # Initialize device manager
        if DEVICE_MANAGER_AVAILABLE:
            self.device_manager = get_host_device_manager(event_bus)
            self.mcp_tools = HostDeviceMCPTools(self.device_manager)
        
        # Initialize device takeover system
        self.device_takeover: Optional[DeviceTakeover] = None
        if DEVICE_TAKEOVER_AVAILABLE:
            try:
                self.device_takeover = DeviceTakeover()
                self.logger.info("✅ Device takeover system initialized")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize device takeover: {e}")
        
        # SEGFAULT FIX: Connect thread-safe signal for device event debouncing
        self._device_event_signal.connect(self._on_device_event_main_thread)
        
        self._setup_ui()
        self._connect_signals()
        self._apply_styling()
        
        # Initial scan
        QTimer.singleShot(500, self._scan_devices)
        
        logger.info("✅ DeviceManagerTab initialized")
    
    def _setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # === HEADER SECTION ===
        header = self._create_header()
        main_layout.addWidget(header)
        
        # === MAIN CONTENT SPLITTER ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Device tree by category
        left_panel = self._create_device_tree_panel()
        splitter.addWidget(left_panel)
        
        # Right panel: Device details and controls
        right_panel = self._create_device_details_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([350, 550])
        main_layout.addWidget(splitter, 1)
        
        # === DEVICE TAKEOVER CONTROLS ===
        takeover_panel = QGroupBox("🚀 Device Takeover Control")
        takeover_layout = QVBoxLayout(takeover_panel)
        
        # Takeover controls
        takeover_btn_layout = QHBoxLayout()
        
        self.find_devices_btn = QPushButton("🔍 Find All Devices")
        self.find_devices_btn.setToolTip("Scan for all takeover-capable devices")
        self.find_devices_btn.setMinimumWidth(150)
        takeover_btn_layout.addWidget(self.find_devices_btn)
        
        self.connect_device_btn = QPushButton("🔗 Connect Device")
        self.connect_device_btn.setToolTip("Connect to selected device for takeover")
        self.connect_device_btn.setMinimumWidth(150)
        self.connect_device_btn.setEnabled(False)
        takeover_btn_layout.addWidget(self.connect_device_btn)
        
        self.flash_firmware_btn = QPushButton("⚡ Flash Firmware")
        self.flash_firmware_btn.setToolTip("Flash firmware to connected device")
        self.flash_firmware_btn.setMinimumWidth(150)
        self.flash_firmware_btn.setEnabled(False)
        takeover_btn_layout.addWidget(self.flash_firmware_btn)
        
        takeover_btn_layout.addStretch()
        takeover_layout.addLayout(takeover_btn_layout)
        
        # Device command interface
        command_layout = QHBoxLayout()
        command_layout.addWidget(QLabel("Command:"))
        self.device_command_input = QLineEdit()
        self.device_command_input.setPlaceholderText("Enter device command (e.g., 'led on', 'read sensor')...")
        command_layout.addWidget(self.device_command_input)
        
        self.send_command_btn = QPushButton("📤 Send")
        self.send_command_btn.setToolTip("Send command to connected device")
        self.send_command_btn.setEnabled(False)
        command_layout.addWidget(self.send_command_btn)
        
        takeover_layout.addLayout(command_layout)
        
        # Takeover status
        self.takeover_status_label = QLabel("🟡 Device Takeover: Ready")
        self.takeover_status_label.setStyleSheet(f"color: {CYBERPUNK_THEME.get('warning', '#ffaa00')};")
        takeover_layout.addWidget(self.takeover_status_label)
        
        # Add takeover panel to main layout
        main_layout.addWidget(takeover_panel)
        
        # === STATUS BAR ===
        status_bar = self._create_status_bar()
        main_layout.addWidget(status_bar)
    
    def _create_header(self) -> QWidget:
        """Create the header with title and controls"""
        header = QFrame()
        header.setObjectName("deviceHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 8, 10, 8)
        
        # Title
        title = QLabel("🔌 Host Device Manager")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {CYBERPUNK_THEME.get('accent', '#00d4ff')};")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Filter dropdown
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All Devices", "all")
        self.filter_combo.addItem("🔌 USB", "usb")
        self.filter_combo.addItem("📟 Serial/COM", "serial")
        self.filter_combo.addItem("📶 Bluetooth", "bluetooth")
        self.filter_combo.addItem("🎤 Audio Input", "audio_input")
        self.filter_combo.addItem("🔊 Audio Output", "audio_output")
        self.filter_combo.addItem("📷 Webcams", "webcam")
        self.filter_combo.addItem("🥽 VR Headsets", "vr_headset")
        self.filter_combo.setMinimumWidth(150)
        layout.addWidget(QLabel("Filter:"))
        layout.addWidget(self.filter_combo)
        
        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search devices...")
        self.search_input.setMinimumWidth(200)
        layout.addWidget(self.search_input)
        
        # Scan button
        self.scan_btn = QPushButton("🔍 Scan Devices")
        self.scan_btn.setMinimumWidth(120)
        layout.addWidget(self.scan_btn)

        self.bt_pair_btn = QPushButton("📶 Bluetooth Pair/Scan")
        self.bt_pair_btn.setToolTip("Open Windows Bluetooth settings to pair/connect devices")
        self.bt_pair_btn.setMinimumWidth(160)
        layout.addWidget(self.bt_pair_btn)
        
        # Auto-refresh toggle
        self.auto_refresh_btn = QPushButton("🔄 Auto")
        self.auto_refresh_btn.setCheckable(True)
        self.auto_refresh_btn.setToolTip("Enable automatic device monitoring")
        layout.addWidget(self.auto_refresh_btn)
        
        return header
    
    def _create_device_tree_panel(self) -> QWidget:
        """Create the device tree panel"""
        panel = QGroupBox("Detected Devices")
        layout = QVBoxLayout(panel)
        
        # Device tree
        self.device_tree = QTreeWidget()
        self.device_tree.setHeaderLabels(["Device", "Status"])
        self.device_tree.setColumnWidth(0, 220)
        self.device_tree.setColumnWidth(1, 80)
        self.device_tree.setAlternatingRowColors(True)
        self.device_tree.setRootIsDecorated(True)
        self.device_tree.setAnimated(True)
        
        # Create category nodes
        self.category_nodes: Dict[str, QTreeWidgetItem] = {}
        for cat_id, config in CATEGORY_CONFIG.items():
            node = QTreeWidgetItem([f"{config['icon']} {config['label']}", ""])
            node.setData(0, Qt.ItemDataRole.UserRole, f"category:{cat_id}")
            node.setExpanded(True)
            font = node.font(0)
            font.setBold(True)
            node.setFont(0, font)
            self.device_tree.addTopLevelItem(node)
            self.category_nodes[cat_id] = node
        
        layout.addWidget(self.device_tree)
        
        # Quick stats
        self.stats_label = QLabel("Total: 0 devices")
        self.stats_label.setStyleSheet(f"color: {CYBERPUNK_THEME.get('text_secondary', '#888')};")
        layout.addWidget(self.stats_label)
        
        return panel
    
    def _create_device_details_panel(self) -> QWidget:
        """Create the device details and controls panel"""
        panel = QGroupBox("Device Details")
        layout = QVBoxLayout(panel)
        
        # Device info section
        info_frame = QFrame()
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(8)
        
        # Device name
        self.device_name_label = QLabel("Select a device")
        self.device_name_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.device_name_label.setStyleSheet(f"color: {CYBERPUNK_THEME.get('accent', '#00d4ff')};")
        info_layout.addWidget(self.device_name_label)
        
        # Device category/type
        self.device_type_label = QLabel("")
        self.device_type_label.setStyleSheet(f"color: {CYBERPUNK_THEME.get('text_secondary', '#888')};")
        info_layout.addWidget(self.device_type_label)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {CYBERPUNK_THEME.get('border', '#2a2a3a')};")
        info_layout.addWidget(sep)
        
        # Details table
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.details_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.details_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.details_table.setAlternatingRowColors(True)
        self.details_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.details_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.details_table.verticalHeader().setVisible(False)
        info_layout.addWidget(self.details_table)
        
        layout.addWidget(info_frame)
        
        # === CONTROL BUTTONS ===
        controls_group = QGroupBox("Device Controls")
        controls_layout = QHBoxLayout(controls_group)
        controls_layout.setSpacing(10)
        
        # Connect/Enable button
        self.connect_btn = QPushButton("🔗 Connect")
        self.connect_btn.setEnabled(False)
        self.connect_btn.setMinimumHeight(36)
        controls_layout.addWidget(self.connect_btn)

        self.pair_btn = QPushButton("📶 Pair")
        self.pair_btn.setEnabled(False)
        self.pair_btn.setMinimumHeight(36)
        controls_layout.addWidget(self.pair_btn)
        
        # Disconnect/Disable button
        self.disconnect_btn = QPushButton("🔌 Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setMinimumHeight(36)
        controls_layout.addWidget(self.disconnect_btn)
        
        # Refresh device
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setMinimumHeight(36)
        controls_layout.addWidget(self.refresh_btn)
        
        # More actions menu
        self.more_btn = QToolButton()
        self.more_btn.setText("⋯")
        self.more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_btn.setMinimumHeight(36)
        more_menu = QMenu()
        copy_id_action = more_menu.addAction("📋 Copy Device ID")
        copy_id_action.triggered.connect(self._copy_device_id)
        export_action = more_menu.addAction("📄 Export Details")
        export_action.triggered.connect(self._export_device_details)
        more_menu.addSeparator()
        configure_action = more_menu.addAction("⚙️ Configure")
        configure_action.triggered.connect(self._configure_device)
        self.more_btn.setMenu(more_menu)
        controls_layout.addWidget(self.more_btn)
        
        layout.addWidget(controls_group)
        
        # === CAPABILITIES SECTION ===
        caps_group = QGroupBox("Capabilities")
        caps_layout = QVBoxLayout(caps_group)
        
        self.capabilities_label = QLabel("No device selected")
        self.capabilities_label.setWordWrap(True)
        self.capabilities_label.setStyleSheet(f"color: {CYBERPUNK_THEME.get('text_secondary', '#888')};")
        caps_layout.addWidget(self.capabilities_label)
        
        layout.addWidget(caps_group)
        
        layout.addStretch()
        
        return panel
    
    def _create_status_bar(self) -> QWidget:
        """Create the status bar"""
        status = QFrame()
        status.setObjectName("statusBar")
        layout = QHBoxLayout(status)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Scan progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status message
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {CYBERPUNK_THEME.get('text_secondary', '#888')};")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Last scan time
        self.last_scan_label = QLabel("")
        self.last_scan_label.setStyleSheet(f"color: {CYBERPUNK_THEME.get('text_secondary', '#888')};")
        layout.addWidget(self.last_scan_label)
        
        return status
    
    def _connect_signals(self):
        """Connect widget signals"""
        self.scan_btn.clicked.connect(self._scan_devices)
        self.bt_pair_btn.clicked.connect(self._open_bluetooth_pairing)
        self.auto_refresh_btn.toggled.connect(self._toggle_auto_refresh)
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        self.search_input.textChanged.connect(self._apply_search)
        self.device_tree.itemClicked.connect(self._on_device_selected)
        self.connect_btn.clicked.connect(self._connect_device)
        self.pair_btn.clicked.connect(self._pair_device)
        self.disconnect_btn.clicked.connect(self._disconnect_device)
        self.refresh_btn.clicked.connect(self._refresh_selected_device)
        
        # === DEVICE TAKEOVER SIGNALS ===
        if self.device_takeover:
            self.find_devices_btn.clicked.connect(self._takeover_find_devices)
            self.connect_device_btn.clicked.connect(self._takeover_connect_device)
            self.flash_firmware_btn.clicked.connect(self._takeover_flash_firmware)
            self.send_command_btn.clicked.connect(self._takeover_send_command)
            self.device_command_input.returnPressed.connect(self._takeover_send_command)
        
        # Subscribe to device events from event bus (SOTA 2026 - real-time updates)
        if self.event_bus:
            self.event_bus.subscribe('device.connected', self._on_device_connected_event)
            self.event_bus.subscribe('device.disconnected', self._on_device_disconnected_event)
            self.event_bus.subscribe('ai.device.connected', self._on_device_connected_event)
            self.event_bus.subscribe('ai.device.disconnected', self._on_device_disconnected_event)
            # SOTA 2026: Wearable health device events from WearableHub + BLE manager
            self.event_bus.subscribe('health.device.connected', self._on_device_connected_event)
            self.event_bus.subscribe('health.device.disconnected', self._on_device_disconnected_event)
            self.event_bus.subscribe('health.ble.connected', self._on_device_connected_event)
            self.event_bus.subscribe('health.ble.disconnected', self._on_device_disconnected_event)
            self.event_bus.subscribe('health.ble.scan_results', self._on_ble_scan_results)
            # Mobile device link events
            self.event_bus.subscribe('mobile.device.linked', self._on_device_connected_event)
            self.logger.info("✅ Device Manager subscribed to device + health + mobile events")
    
    def _on_device_connected_event(self, event_data: dict):
        """Handle device connected events from event bus.
        
        SEGFAULT FIX: This handler may be called from a BACKGROUND THREAD
        (via event bus publish from DeviceScanWorker).  We emit a Qt signal
        to safely bridge to the main thread, then debounce there.
        """
        try:
            device_info = event_data if isinstance(event_data, dict) else {}
            device_name = device_info.get('name', device_info.get('device_name', 'Unknown'))
            # Emit signal (thread-safe) — actual work happens on main thread
            self._device_event_signal.emit(f"Device connected: {device_name}")
        except Exception as e:
            self.logger.error(f"Error handling device connected event: {e}")
    
    def _on_ble_scan_results(self, event_data: dict):
        """Handle BLE scan results from health BLE manager — show wearables in device tree."""
        try:
            devices = event_data.get('devices', []) if isinstance(event_data, dict) else []
            for d in devices:
                name = d.get('name', 'Unknown BLE')
                hr = d.get('has_heart_rate', False)
                suffix = " (HR)" if hr else ""
                self._device_event_signal.emit(f"BLE found: {name}{suffix}")
        except Exception as e:
            self.logger.error(f"Error handling BLE scan results: {e}")

    def _on_device_disconnected_event(self, event_data: dict):
        """Handle device disconnected events from event bus (thread-safe via signal)."""
        try:
            device_info = event_data if isinstance(event_data, dict) else {}
            device_name = device_info.get('name', device_info.get('device_name', 'Unknown'))
            self._device_event_signal.emit(f"Device disconnected: {device_name}")
        except Exception as e:
            self.logger.error(f"Error handling device disconnected event: {e}")
    
    @pyqtSlot(str)
    def _on_device_event_main_thread(self, status_msg: str):
        """Handle device event on the MAIN THREAD (connected via signal). Debounced."""
        self._pending_device_status = status_msg
        if not hasattr(self, '_device_debounce_timer') or self._device_debounce_timer is None:
            self._device_debounce_timer = QTimer(self)
            self._device_debounce_timer.setSingleShot(True)
            self._device_debounce_timer.timeout.connect(self._do_debounced_tree_update)
        # Restart timer — tree rebuilds 500ms after the LAST event
        self._device_debounce_timer.start(500)
    
    def _do_debounced_tree_update(self):
        """Actually rebuild the device tree (called once after event burst settles)."""
        try:
            self._populate_device_tree()
            status = getattr(self, '_pending_device_status', 'Devices updated')
            self._show_status(status)
        except Exception as e:
            self.logger.error(f"Error in debounced tree update: {e}")

    def _open_bluetooth_pairing(self):
        def _open():
            try:
                subprocess.run(['bluetoothctl', 'scan', 'on'],
                               capture_output=True, text=True, timeout=10)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True, name="BTPairing").start()
        self._show_status("Started Bluetooth scan (pair/connect), then click Scan Devices")
    
    def _apply_styling(self):
        """Apply cyberpunk styling"""
        self.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {CYBERPUNK_THEME.get('border', '#2a2a3a')};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: {CYBERPUNK_THEME.get('bg_secondary', '#12121a')};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {CYBERPUNK_THEME.get('accent', '#00d4ff')};
            }}
            QTreeWidget {{
                background-color: {CYBERPUNK_THEME.get('bg_primary', '#0a0a0f')};
                border: 1px solid {CYBERPUNK_THEME.get('border', '#2a2a3a')};
                border-radius: 4px;
                color: {CYBERPUNK_THEME.get('text_primary', '#fff')};
            }}
            QTreeWidget::item:selected {{
                background-color: {CYBERPUNK_THEME.get('accent', '#00d4ff')}40;
            }}
            QTreeWidget::item:hover {{
                background-color: {CYBERPUNK_THEME.get('accent', '#00d4ff')}20;
            }}
            QTableWidget {{
                background-color: {CYBERPUNK_THEME.get('bg_primary', '#0a0a0f')};
                border: 1px solid {CYBERPUNK_THEME.get('border', '#2a2a3a')};
                border-radius: 4px;
                gridline-color: {CYBERPUNK_THEME.get('border', '#2a2a3a')};
                color: {CYBERPUNK_THEME.get('text_primary', '#fff')};
            }}
            QTableWidget::item:selected {{
                background-color: {CYBERPUNK_THEME.get('accent', '#00d4ff')}40;
            }}
            QPushButton {{
                background-color: {CYBERPUNK_THEME.get('bg_secondary', '#12121a')};
                border: 1px solid {CYBERPUNK_THEME.get('accent', '#00d4ff')};
                border-radius: 6px;
                padding: 8px 16px;
                color: {CYBERPUNK_THEME.get('accent', '#00d4ff')};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {CYBERPUNK_THEME.get('accent', '#00d4ff')}30;
            }}
            QPushButton:pressed {{
                background-color: {CYBERPUNK_THEME.get('accent', '#00d4ff')}50;
            }}
            QPushButton:disabled {{
                border-color: {CYBERPUNK_THEME.get('border', '#2a2a3a')};
                color: {CYBERPUNK_THEME.get('text_secondary', '#888')};
            }}
            QComboBox {{
                background-color: {CYBERPUNK_THEME.get('bg_primary', '#0a0a0f')};
                border: 1px solid {CYBERPUNK_THEME.get('border', '#2a2a3a')};
                border-radius: 4px;
                padding: 5px 10px;
                color: {CYBERPUNK_THEME.get('text_primary', '#fff')};
            }}
            QLineEdit {{
                background-color: {CYBERPUNK_THEME.get('bg_primary', '#0a0a0f')};
                border: 1px solid {CYBERPUNK_THEME.get('border', '#2a2a3a')};
                border-radius: 4px;
                padding: 5px 10px;
                color: {CYBERPUNK_THEME.get('text_primary', '#fff')};
            }}
            QLineEdit:focus {{
                border-color: {CYBERPUNK_THEME.get('accent', '#00d4ff')};
            }}
            #deviceHeader {{
                background-color: {CYBERPUNK_THEME.get('bg_secondary', '#12121a')};
                border: 1px solid {CYBERPUNK_THEME.get('border', '#2a2a3a')};
                border-radius: 8px;
            }}
            #statusBar {{
                background-color: {CYBERPUNK_THEME.get('bg_secondary', '#12121a')};
                border: 1px solid {CYBERPUNK_THEME.get('border', '#2a2a3a')};
                border-radius: 4px;
            }}
            QProgressBar {{
                border: none;
                background-color: {CYBERPUNK_THEME.get('bg_primary', '#0a0a0f')};
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {CYBERPUNK_THEME.get('accent', '#00d4ff')};
                border-radius: 3px;
            }}
        """)
    
    # === DEVICE OPERATIONS ===
    
    def _scan_devices(self):
        """Scan for devices"""
        if not self.device_manager:
            self._show_status("Device manager not available", error=True)
            return
        
        self._show_status("Scanning devices...")
        self.scan_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        if hasattr(self, '_scan_worker') and self._scan_worker and self._scan_worker.isRunning():
            self._show_status("Scan already in progress...")
            self.scan_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            return
        self._scan_worker = DeviceScanWorker(self.device_manager)
        self._scan_worker.scan_complete.connect(self._on_scan_complete)
        self._scan_worker.scan_error.connect(self._on_scan_error)
        self._scan_worker.start()
    
    @pyqtSlot(dict)
    def _on_scan_complete(self, summary: dict):
        """Handle scan completion"""
        self.scan_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        total = summary.get('total_devices', 0)
        self._show_status(f"Scan complete: {total} devices found")
        self.last_scan_label.setText(f"Last scan: {datetime.now().strftime('%H:%M:%S')}")
        
        self._populate_device_tree()
        self._update_stats(summary)
    
    @pyqtSlot(str)
    def _on_scan_error(self, error: str):
        """Handle scan error"""
        self.scan_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._show_status(f"Scan error: {error}", error=True)
    
    def _populate_device_tree(self):
        """Populate the device tree with current devices"""
        if not self.device_manager:
            return
        
        # Clear existing device items (keep category nodes)
        for cat_id, node in self.category_nodes.items():
            while node.childCount() > 0:
                node.removeChild(node.child(0))
        
        # Add devices
        for device in self.device_manager.get_all_devices():
            cat_id = device.category.value
            if cat_id in self.category_nodes:
                parent = self.category_nodes[cat_id]
                
                # Get status config
                status_cfg = STATUS_CONFIG.get(device.status.value, STATUS_CONFIG["disconnected"])
                
                item = QTreeWidgetItem([
                    f"  {device.name}",
                    f"{status_cfg['icon']}"
                ])
                item.setData(0, Qt.ItemDataRole.UserRole, device.id)
                item.setToolTip(0, f"ID: {device.id}\nVendor: {device.vendor}")
                
                # Color based on status
                item.setForeground(1, QColor(status_cfg['color']))
                
                parent.addChild(item)
        
        # Update category counts
        for cat_id, node in self.category_nodes.items():
            count = node.childCount()
            config = CATEGORY_CONFIG.get(cat_id, CATEGORY_CONFIG['unknown'])
            node.setText(0, f"{config['icon']} {config['label']} ({count})")
    
    def _update_stats(self, summary: dict):
        """Update statistics display"""
        total = summary.get('total_devices', 0)
        categories = summary.get('categories', {})
        
        parts = [f"Total: {total}"]
        for cat, count in categories.items():
            if count > 0:
                config = CATEGORY_CONFIG.get(cat, {})
                icon = config.get('icon', '')
                parts.append(f"{icon} {count}")
        
        self.stats_label.setText(" | ".join(parts))
    
    def _on_device_selected(self, item: QTreeWidgetItem, column: int):
        """Handle device selection"""
        device_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not device_id or device_id.startswith("category:"):
            return
        
        self.selected_device_id = device_id
        self._update_device_details(device_id)
        self.device_selected.emit(device_id)
    
    def _update_device_details(self, device_id: str):
        """Update device details panel"""
        if not self.device_manager:
            return
        
        device = self.device_manager.get_device_by_id(device_id)
        if not device:
            return
        
        # Update name and type
        cat_cfg = CATEGORY_CONFIG.get(device.category.value, CATEGORY_CONFIG['unknown'])
        status_cfg = STATUS_CONFIG.get(device.status.value, STATUS_CONFIG['disconnected'])
        
        self.device_name_label.setText(f"{cat_cfg['icon']} {device.name}")
        self.device_type_label.setText(f"{cat_cfg['label']} • {status_cfg['icon']} {status_cfg['label']}")
        
        # Update details table
        details = [
            ("ID", device.id),
            ("Category", device.category.value),
            ("Status", device.status.value),
            ("Vendor", device.vendor or "N/A"),
            ("Product", device.product or "N/A"),
            ("Serial", device.serial or "N/A"),
            ("Port", device.port or "N/A"),
            ("Address", device.address or "N/A"),
            ("Driver", device.driver or "N/A"),
        ]
        
        self.details_table.setRowCount(len(details))
        for row, (prop, val) in enumerate(details):
            self.details_table.setItem(row, 0, QTableWidgetItem(prop))
            self.details_table.setItem(row, 1, QTableWidgetItem(str(val)))
        
        # Update capabilities
        caps = device.capabilities
        if caps:
            caps_text = "\n".join([f"• {k}: {v}" for k, v in caps.items()])
        else:
            caps_text = "No capabilities reported"
        self.capabilities_label.setText(caps_text)
        
        # Enable/disable control buttons based on status
        is_connected = device.status in [DeviceStatus.CONNECTED, DeviceStatus.ACTIVE]
        is_bluetooth = device.category == DeviceCategory.BLUETOOTH
        is_paired = device.status == DeviceStatus.PAIRED
        self.connect_btn.setEnabled(not is_connected)
        self.disconnect_btn.setEnabled(is_connected)
        self.pair_btn.setEnabled(is_bluetooth and (not is_connected) and (not is_paired))
        self.refresh_btn.setEnabled(True)
    
    def _connect_device(self):
        """Connect the selected device"""
        if not self.selected_device_id or not self.device_manager:
            return

        self._run_device_action(self.selected_device_id, "enable")

    def _pair_device(self):
        if not self.selected_device_id or not self.device_manager:
            return
        self._run_device_action(self.selected_device_id, "enable")
    
    def _disconnect_device(self):
        """Disconnect the selected device"""
        if not self.selected_device_id or not self.device_manager:
            return

        self._run_device_action(self.selected_device_id, "disable")

    def _run_device_action(self, device_id: str, action: str):
        if not self.device_manager:
            return

        if self._action_worker and self._action_worker.isRunning():
            self._show_status("Device action already running", error=True)
            return

        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        self.pair_btn.setEnabled(False)

        self._show_status("Working...")
        self._action_worker = DeviceActionWorker(self.device_manager, device_id, action)
        self._action_worker.action_complete.connect(self._on_device_action_complete)
        self._action_worker.start()

    @pyqtSlot(str, bool, str)
    def _on_device_action_complete(self, device_id: str, success: bool, action: str):
        if action == "enable":
            self._show_status("Device paired/connected" if success else "Failed to pair/connect device", error=not success)
        elif action == "disable":
            self._show_status("Device disconnected" if success else "Failed to disconnect device", error=not success)
        else:
            self._show_status("Device action complete" if success else "Device action failed", error=not success)

        if self.selected_device_id == device_id:
            self._update_device_details(device_id)

        self._scan_devices()
    
    def _refresh_selected_device(self):
        """Refresh the selected device"""
        if self.selected_device_id:
            self._scan_devices()
    
    def _copy_device_id(self):
        """Copy the selected device ID to clipboard."""
        try:
            if self.selected_device_id:
                from PyQt6.QtWidgets import QApplication
                clipboard = QApplication.clipboard()
                clipboard.setText(self.selected_device_id)
                self._show_status(f"Copied device ID: {self.selected_device_id}")
            else:
                self._show_status("No device selected")
        except Exception as e:
            self.logger.error(f"Error copying device ID: {e}")
            self._show_status(f"Failed to copy device ID: {e}")
    
    def _export_device_details(self):
        """Export selected device details to a file."""
        try:
            if not self.selected_device_id or not self.device_manager:
                self._show_status("No device selected")
                return
            
            device = self.device_manager.get_device_by_id(self.selected_device_id)
            if not device:
                self._show_status("Device not found")
                return
            
            from PyQt6.QtWidgets import QFileDialog
            import json
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Device Details", 
                f"device_{self.selected_device_id}.json",
                "JSON Files (*.json)"
            )
            
            if file_path:
                with open(file_path, 'w') as f:
                    json.dump(device, f, indent=2, default=str)
                self._show_status(f"Device details exported to {file_path}")
        except Exception as e:
            self.logger.error(f"Error exporting device details: {e}")
            self._show_status(f"Failed to export device details: {e}")
    
    def _configure_device(self):
        """Open device configuration dialog."""
        try:
            if not self.selected_device_id:
                self._show_status("No device selected")
                return
            
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Configure Device",
                f"Configuration options for device: {self.selected_device_id}\n\n"
                "Advanced device configuration is available through the device's native interface.\n"
                "Use Windows Device Manager for driver settings."
            )
        except Exception as e:
            self.logger.error(f"Error configuring device: {e}")
            self._show_status(f"Failed to configure device: {e}")
    
    def _toggle_auto_refresh(self, enabled: bool):
        """Toggle automatic device monitoring"""
        if not self.device_manager:
            return
        
        if enabled:
            self.device_manager.start_monitoring(interval=5.0)
            self._show_status("Auto-refresh enabled (5s interval)")
            # Set up timer to refresh UI
            if not hasattr(self, '_refresh_timer'):
                self._refresh_timer = QTimer(self)
                self._refresh_timer.timeout.connect(self._populate_device_tree)
            self._refresh_timer.start(5000)
        else:
            self.device_manager.stop_monitoring()
            self._show_status("Auto-refresh disabled")
            if hasattr(self, '_refresh_timer'):
                self._refresh_timer.stop()
    
    def _apply_filter(self):
        """Apply category filter"""
        filter_val = self.filter_combo.currentData()
        
        for cat_id, node in self.category_nodes.items():
            if filter_val == "all" or cat_id == filter_val:
                node.setHidden(False)
            else:
                node.setHidden(True)
    
    def _apply_search(self, text: str):
        """Apply search filter"""
        search_lower = text.lower()
        
        for cat_id, node in self.category_nodes.items():
            visible_children = 0
            for i in range(node.childCount()):
                child = node.child(i)
                if not text or search_lower in child.text(0).lower():
                    child.setHidden(False)
                    visible_children += 1
                else:
                    child.setHidden(True)
            
            # Hide category if no visible children (unless search is empty)
            if text and visible_children == 0:
                node.setHidden(True)
            else:
                node.setHidden(False)
    
    def _show_status(self, message: str, error: bool = False):
        """Show status message"""
        color = CYBERPUNK_THEME.get('error' if error else 'text_secondary', '#888')
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")
        logger.info(f"{'❌' if error else 'ℹ️'} {message}")
    
    # === DEVICE TAKEOVER METHODS ===
    
    def _takeover_find_devices(self):
        """Find all takeover-capable devices"""
        if not self.device_takeover:
            self._show_status("Device takeover not available", error=True)
            return
        
        try:
            self._show_status("🔍 Scanning for takeover devices...")
            self.find_devices_btn.setEnabled(False)
            self.takeover_status_label.setText("🟡 Scanning...")
            
            # Find devices using takeover system
            devices = self.device_takeover.find_all_devices()
            
            # Update UI with found devices
            device_count = len(devices) if devices else 0
            self._show_status(f"✅ Found {device_count} takeover-capable devices")
            self.takeover_status_label.setText(f"🟢 Found {device_count} devices")
            
            # Enable connect button if devices found
            self.connect_device_btn.setEnabled(device_count > 0)
            
            # Log found devices
            if devices:
                self.logger.info(f"🔍 Found takeover devices: {[d.get('id', 'unknown') for d in devices[:5]]}")
                if device_count > 5:
                    self.logger.info(f"   ... and {device_count - 5} more")
            
        except Exception as e:
            self._show_status(f"❌ Device scan failed: {e}", error=True)
            self.takeover_status_label.setText("🔴 Scan Failed")
            self.logger.error(f"Device takeover scan failed: {e}")
        finally:
            self.find_devices_btn.setEnabled(True)
    
    def _takeover_connect_device(self):
        """Connect to selected device for takeover"""
        if not self.device_takeover:
            self._show_status("Device takeover not available", error=True)
            return
        
        if not self.selected_device_id:
            self._show_status("No device selected", error=True)
            return
        
        try:
            self._show_status(f"🔗 Connecting to {self.selected_device_id}...")
            self.connect_device_btn.setEnabled(False)
            self.takeover_status_label.setText("🟡 Connecting...")
            
            # Connect to device
            result = self.device_takeover.connect_device(self.selected_device_id)
            
            if result:
                self._show_status(f"✅ Connected to {self.selected_device_id}")
                self.takeover_status_label.setText(f"🟢 Connected: {self.selected_device_id}")
                
                # Enable takeover controls
                self.flash_firmware_btn.setEnabled(True)
                self.send_command_btn.setEnabled(True)
                self.device_command_input.setEnabled(True)
                
                self.logger.info(f"🔗 Successfully connected to device: {self.selected_device_id}")
            else:
                self._show_status(f"❌ Failed to connect to {self.selected_device_id}", error=True)
                self.takeover_status_label.setText("🔴 Connection Failed")
                
        except Exception as e:
            self._show_status(f"❌ Connection failed: {e}", error=True)
            self.takeover_status_label.setText("🔴 Connection Error")
            self.logger.error(f"Device connection failed: {e}")
        finally:
            self.connect_device_btn.setEnabled(True)
    
    def _takeover_flash_firmware(self):
        """Flash firmware to connected device"""
        if not self.device_takeover:
            self._show_status("Device takeover not available", error=True)
            return
        
        if not self.selected_device_id:
            self._show_status("No device selected", error=True)
            return
        
        try:
            self._show_status(f"⚡ Flashing firmware to {self.selected_device_id}...")
            self.flash_firmware_btn.setEnabled(False)
            self.takeover_status_label.setText("🟡 Flashing...")
            
            # Flash firmware (using default firmware path or device-specific)
            device_info = {"id": self.selected_device_id}
            result = self.device_takeover.flash_particle_firmware(device_info)
            
            if result and result.get("success"):
                self._show_status(f"✅ Firmware flashed to {self.selected_device_id}")
                self.takeover_status_label.setText(f"🟢 Firmware Flashed")
                self.logger.info(f"⚡ Successfully flashed firmware to: {self.selected_device_id}")
            else:
                error_msg = result.get("error", "Unknown error") if result else "No response"
                self._show_status(f"❌ Flash failed: {error_msg}", error=True)
                self.takeover_status_label.setText("🔴 Flash Failed")
                
        except Exception as e:
            self._show_status(f"❌ Flash failed: {e}", error=True)
            self.takeover_status_label.setText("🔴 Flash Error")
            self.logger.error(f"Firmware flash failed: {e}")
        finally:
            self.flash_firmware_btn.setEnabled(True)
    
    def _takeover_send_command(self):
        """Send command to connected device"""
        if not self.device_takeover:
            self._show_status("Device takeover not available", error=True)
            return
        
        command = self.device_command_input.text().strip()
        if not command:
            self._show_status("Enter a command", error=True)
            return
        
        try:
            self._show_status(f"📤 Sending: {command}")
            self.send_command_btn.setEnabled(False)
            self.takeover_status_label.setText("🟡 Sending...")
            
            # Send command
            result = self.device_takeover.execute_command(command)
            
            if result and result.get("success"):
                response = result.get("response", "Command executed")
                self._show_status(f"✅ Command sent: {response}")
                self.takeover_status_label.setText(f"🟢 Command Sent")
                self.logger.info(f"📤 Command sent: {command} -> {response}")
                
                # Clear command input on success
                self.device_command_input.clear()
            else:
                error_msg = result.get("error", "Command failed") if result else "No response"
                self._show_status(f"❌ Command failed: {error_msg}", error=True)
                self.takeover_status_label.setText("🔴 Command Failed")
                
        except Exception as e:
            self._show_status(f"❌ Command failed: {e}", error=True)
            self.takeover_status_label.setText("🔴 Command Error")
            self.logger.error(f"Device command failed: {e}")
        finally:
            self.send_command_btn.setEnabled(True)
    
    # === MCP TOOL INTERFACE ===
    
    def get_mcp_tools(self) -> Optional[HostDeviceMCPTools]:
        """Get MCP tools instance for AI integration"""
        return self.mcp_tools
    
    def execute_mcp_tool(self, tool_name: str, parameters: dict) -> dict:
        """Execute an MCP tool (for AI integration)
        
        Args:
            tool_name: Name of the tool
            parameters: Tool parameters
            
        Returns:
            Tool result
        """
        if self.mcp_tools:
            return self.mcp_tools.execute_tool(tool_name, parameters)
        return {"success": False, "error": "MCP tools not available"}


# Export for import
__all__ = ['DeviceManagerTab', 'DEVICE_MANAGER_AVAILABLE']
