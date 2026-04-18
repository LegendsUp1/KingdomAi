#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Software Automation Tab for Kingdom AI - SOTA 2026

Provides a comprehensive GUI for Windows software automation:
- List and monitor all running Windows applications
- Connect/Disconnect to any software window
- Execute automation commands (click, type, invoke controls)
- Real-time window and control inspection
- MCP tool integration for AI-driven automation

Author: Kingdom AI Team
Version: 1.0.0 SOTA 2026
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QSplitter, QFrame, QScrollArea,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QMessageBox,
    QToolButton, QMenu, QSizePolicy, QTextEdit, QSpinBox,
    QTabWidget, QGridLayout, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtGui import QIcon, QColor, QFont, QAction

logger = logging.getLogger("KingdomAI.SoftwareAutomationTab")


# Import software automation manager
try:
    from core.software_automation_manager import (
        SoftwareAutomationManager, SoftwareAutomationMCPTools
    )
    SOFTWARE_AUTOMATION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Software automation manager not available: {e}")
    SOFTWARE_AUTOMATION_AVAILABLE = False
    SoftwareAutomationManager = None
    SoftwareAutomationMCPTools = None

# Import cyberpunk styling
try:
    from gui.cyberpunk_style import CYBERPUNK_THEME
except ImportError:
    CYBERPUNK_THEME = {}

# SOTA 2026 FIX: Ensure ALL required theme keys exist with sensible defaults
# Prevents KeyError regardless of which CYBERPUNK_THEME dict is resolved
_THEME_DEFAULTS = {
    'bg_primary': '#0a0a0f',
    'bg_secondary': '#12121a',
    'accent': '#00d4ff',
    'accent_secondary': '#ff00ff',
    'text_primary': '#ffffff',
    'text_secondary': '#888899',
    'success': '#00ff88',
    'warning': '#ffaa00',
    'error': '#ff4444',
    'info': '#00d4ff',
    'border': '#2a2a3a',
    'background': '#0A0E17',
    'background_alt': '#0F1620',
    'foreground': '#E6FFFF',
    'foreground_alt': '#99CCFF',
    'neon_blue': '#00d4ff',
    'neon_pink': '#ff00ff',
    'neon_purple': '#aa00ff',
    'neon_green': '#00ff88',
    'highlight': '#1a1a2e',
}
for _k, _v in _THEME_DEFAULTS.items():
    CYBERPUNK_THEME.setdefault(_k, _v)


# Control type icons and colors
CONTROL_TYPE_CONFIG = {
    "ControlType.Window": {"icon": "🪟", "color": "#00d4ff", "label": "Window"},
    "ControlType.Button": {"icon": "🔘", "color": "#ff00ff", "label": "Button"},
    "ControlType.Edit": {"icon": "📝", "color": "#00ff88", "label": "Text Input"},
    "ControlType.Document": {"icon": "📄", "color": "#ffaa00", "label": "Document"},
    "ControlType.List": {"icon": "📋", "color": "#0066ff", "label": "List"},
    "ControlType.ListItem": {"icon": "📌", "color": "#0088ff", "label": "List Item"},
    "ControlType.Menu": {"icon": "📁", "color": "#aa00ff", "label": "Menu"},
    "ControlType.MenuItem": {"icon": "📄", "color": "#aa44ff", "label": "Menu Item"},
    "ControlType.Tab": {"icon": "📑", "color": "#ff9900", "label": "Tab"},
    "ControlType.TabItem": {"icon": "📎", "color": "#ffaa33", "label": "Tab Item"},
    "ControlType.Tree": {"icon": "🌲", "color": "#00aa44", "label": "Tree"},
    "ControlType.TreeItem": {"icon": "🌿", "color": "#00cc55", "label": "Tree Item"},
    "ControlType.ComboBox": {"icon": "🔽", "color": "#ff6600", "label": "Combo Box"},
    "ControlType.CheckBox": {"icon": "☑️", "color": "#00ff00", "label": "Check Box"},
    "ControlType.RadioButton": {"icon": "⭕", "color": "#00ffff", "label": "Radio Button"},
    "ControlType.Text": {"icon": "📝", "color": "#ffffff", "label": "Text"},
    "ControlType.Pane": {"icon": "▢", "color": "#666666", "label": "Pane"},
    "ControlType.ToolBar": {"icon": "🔧", "color": "#888888", "label": "Toolbar"},
    "ControlType.Hyperlink": {"icon": "🔗", "color": "#0088ff", "label": "Hyperlink"},
    "ControlType.Slider": {"icon": "🎚️", "color": "#ffcc00", "label": "Slider"},
    "ControlType.ScrollBar": {"icon": "📜", "color": "#555555", "label": "Scrollbar"},
}


class WindowListWorker(QThread):
    """Background worker for listing windows"""
    list_complete = pyqtSignal(list)
    list_error = pyqtSignal(str)
    
    def __init__(self, automation_manager: "SoftwareAutomationManager"):
        super().__init__()
        self.automation_manager = automation_manager
    
    def run(self):
        try:
            result = self.automation_manager.execute({"action": "list_windows"})
            if result.get("success"):
                windows = result.get("windows", [])
                self.list_complete.emit(windows)
            else:
                self.list_error.emit(result.get("error", "Unknown error"))
        except Exception as e:
            self.list_error.emit(str(e))


class ControlListWorker(QThread):
    """Background worker for listing window controls"""
    list_complete = pyqtSignal(list)
    list_error = pyqtSignal(str)
    
    def __init__(self, automation_manager: "SoftwareAutomationManager", window_selector: Dict):
        super().__init__()
        self.automation_manager = automation_manager
        self.window_selector = window_selector
    
    def run(self):
        try:
            result = self.automation_manager.execute({
                "action": "list_controls",
                "window": self.window_selector,
                "max": 500
            })
            if result.get("success"):
                controls = result.get("controls", [])
                self.list_complete.emit(controls)
            else:
                self.list_error.emit(result.get("error", "Unknown error"))
        except Exception as e:
            self.list_error.emit(str(e))


class AutomationActionWorker(QThread):
    """Background worker for automation actions"""
    action_complete = pyqtSignal(dict)
    action_error = pyqtSignal(str)
    
    def __init__(self, automation_manager: "SoftwareAutomationManager", request: Dict):
        super().__init__()
        self.automation_manager = automation_manager
        self.request = request
    
    def run(self):
        try:
            result = self.automation_manager.execute(self.request)
            self.action_complete.emit(result)
        except Exception as e:
            self.action_error.emit(str(e))


class SoftwareAutomationTab(QWidget):
    """Software Automation Tab - Comprehensive Windows automation interface"""
    
    # Signals
    window_connected = pyqtSignal(dict)
    window_disconnected = pyqtSignal()
    automation_executed = pyqtSignal(str, dict)
    
    def __init__(self, event_bus=None, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.setObjectName("SoftwareAutomationTab")
        
        # State
        self.connected_window: Optional[Dict] = None
        self.windows_list: List[Dict] = []
        self.controls_list: List[Dict] = []
        self.selected_control: Optional[Dict] = None
        
        # Initialize automation manager and MCP tools
        self.automation_manager = None
        self.mcp_tools = None
        
        if SOFTWARE_AUTOMATION_AVAILABLE and SoftwareAutomationManager:
            try:
                self.automation_manager = SoftwareAutomationManager()
                self.mcp_tools = SoftwareAutomationMCPTools(self.automation_manager)
                logger.info("✅ Software automation manager initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize software automation: {e}")
        
        # Workers
        self._window_list_worker = None
        self._control_list_worker = None
        self._action_worker = None
        
        # Build UI
        self._setup_ui()
        self._apply_styling()
        self._setup_event_bus()
        
        # Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_windows)
        
        logger.info("✅ Software Automation Tab initialized")
    
    def _setup_ui(self):
        """Build the complete UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Main splitter - windows on left, controls/actions on right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Windows list
        left_panel = self._create_windows_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Controls and Actions
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter sizes (40% windows, 60% controls/actions)
        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter, 1)
        
        # Status bar
        status_bar = self._create_status_bar()
        main_layout.addWidget(status_bar)
    
    def _create_header(self) -> QWidget:
        """Create header with title and main controls"""
        header = QFrame()
        header.setObjectName("header_frame")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Title
        title_label = QLabel("🖥️ Software Automation Center")
        title_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {CYBERPUNK_THEME['accent']};
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Connection status
        self.connection_status_label = QLabel("⚪ Not Connected")
        self.connection_status_label.setStyleSheet(f"color: {CYBERPUNK_THEME['text_secondary']};")
        layout.addWidget(self.connection_status_label)
        
        # Refresh button
        self.refresh_btn = QPushButton("🔄 Refresh Windows")
        self.refresh_btn.clicked.connect(self._on_refresh_windows)
        layout.addWidget(self.refresh_btn)
        
        # Auto-refresh toggle
        self.auto_refresh_cb = QCheckBox("Auto-refresh")
        self.auto_refresh_cb.stateChanged.connect(self._on_auto_refresh_toggled)
        layout.addWidget(self.auto_refresh_cb)
        
        return header
    
    def _create_windows_panel(self) -> QWidget:
        """Create the windows list panel"""
        panel = QGroupBox("Running Windows")
        panel.setObjectName("windows_panel")
        layout = QVBoxLayout(panel)
        
        # Search filter
        search_layout = QHBoxLayout()
        self.window_search = QLineEdit()
        self.window_search.setPlaceholderText("🔍 Filter windows by name...")
        self.window_search.textChanged.connect(self._on_window_search_changed)
        search_layout.addWidget(self.window_search)
        layout.addLayout(search_layout)
        
        # Windows table
        self.windows_table = QTableWidget()
        self.windows_table.setColumnCount(4)
        self.windows_table.setHorizontalHeaderLabels(["Window Name", "Process ID", "Class", "Status"])
        self.windows_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.windows_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.windows_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.windows_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.windows_table.setColumnWidth(1, 80)
        self.windows_table.setColumnWidth(2, 120)
        self.windows_table.setColumnWidth(3, 80)
        self.windows_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.windows_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.windows_table.itemSelectionChanged.connect(self._on_window_selected)
        self.windows_table.itemDoubleClicked.connect(self._on_window_double_clicked)
        layout.addWidget(self.windows_table)
        
        # Window action buttons
        btn_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("🔗 Connect")
        self.connect_btn.clicked.connect(self._on_connect_window)
        self.connect_btn.setEnabled(False)
        btn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("⛓️‍💥 Disconnect")
        self.disconnect_btn.clicked.connect(self._on_disconnect_window)
        self.disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.disconnect_btn)
        
        self.focus_btn = QPushButton("🎯 Focus")
        self.focus_btn.clicked.connect(self._on_focus_window)
        self.focus_btn.setEnabled(False)
        btn_layout.addWidget(self.focus_btn)
        
        layout.addLayout(btn_layout)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """Create the right panel with controls and actions"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget for controls and actions
        tab_widget = QTabWidget()
        
        # Controls tab
        controls_tab = self._create_controls_tab()
        tab_widget.addTab(controls_tab, "🎛️ Controls")
        
        # Actions tab
        actions_tab = self._create_actions_tab()
        tab_widget.addTab(actions_tab, "⚡ Actions")
        
        # Command tab
        command_tab = self._create_command_tab()
        tab_widget.addTab(command_tab, "💻 Commands")
        
        # Log tab
        log_tab = self._create_log_tab()
        tab_widget.addTab(log_tab, "📋 Log")
        
        layout.addWidget(tab_widget)
        
        return panel
    
    def _create_controls_tab(self) -> QWidget:
        """Create the controls inspection tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Controls tree
        self.controls_tree = QTreeWidget()
        self.controls_tree.setColumnCount(4)
        self.controls_tree.setHeaderLabels(["Control", "Type", "Automation ID", "Bounds"])
        self.controls_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.controls_tree.itemClicked.connect(self._on_control_selected)
        self.controls_tree.itemDoubleClicked.connect(self._on_control_double_clicked)
        layout.addWidget(self.controls_tree)
        
        # Load controls button
        btn_layout = QHBoxLayout()
        
        self.load_controls_btn = QPushButton("📥 Load Controls")
        self.load_controls_btn.clicked.connect(self._on_load_controls)
        self.load_controls_btn.setEnabled(False)
        btn_layout.addWidget(self.load_controls_btn)
        
        self.controls_count_label = QLabel("0 controls")
        self.controls_count_label.setStyleSheet(f"color: {CYBERPUNK_THEME['text_secondary']};")
        btn_layout.addWidget(self.controls_count_label)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Control details
        details_group = QGroupBox("Selected Control Details")
        details_layout = QGridLayout(details_group)
        
        self.control_name_label = QLabel("-")
        self.control_type_label = QLabel("-")
        self.control_id_label = QLabel("-")
        self.control_bounds_label = QLabel("-")
        
        details_layout.addWidget(QLabel("Name:"), 0, 0)
        details_layout.addWidget(self.control_name_label, 0, 1)
        details_layout.addWidget(QLabel("Type:"), 1, 0)
        details_layout.addWidget(self.control_type_label, 1, 1)
        details_layout.addWidget(QLabel("Automation ID:"), 2, 0)
        details_layout.addWidget(self.control_id_label, 2, 1)
        details_layout.addWidget(QLabel("Bounds:"), 3, 0)
        details_layout.addWidget(self.control_bounds_label, 3, 1)
        
        layout.addWidget(details_group)
        
        return tab
    
    def _create_actions_tab(self) -> QWidget:
        """Create the quick actions tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Click action
        click_group = QGroupBox("🖱️ Click Actions")
        click_layout = QGridLayout(click_group)
        
        click_layout.addWidget(QLabel("X:"), 0, 0)
        self.click_x_spin = QSpinBox()
        self.click_x_spin.setRange(0, 10000)
        click_layout.addWidget(self.click_x_spin, 0, 1)
        
        click_layout.addWidget(QLabel("Y:"), 0, 2)
        self.click_y_spin = QSpinBox()
        self.click_y_spin.setRange(0, 10000)
        click_layout.addWidget(self.click_y_spin, 0, 3)
        
        self.click_left_btn = QPushButton("Left Click")
        self.click_left_btn.clicked.connect(lambda: self._on_click_at("left"))
        click_layout.addWidget(self.click_left_btn, 1, 0, 1, 2)
        
        self.click_right_btn = QPushButton("Right Click")
        self.click_right_btn.clicked.connect(lambda: self._on_click_at("right"))
        click_layout.addWidget(self.click_right_btn, 1, 2, 1, 2)
        
        self.invoke_control_btn = QPushButton("Invoke Selected Control")
        self.invoke_control_btn.clicked.connect(self._on_invoke_control)
        self.invoke_control_btn.setEnabled(False)
        click_layout.addWidget(self.invoke_control_btn, 2, 0, 1, 4)
        
        layout.addWidget(click_group)
        
        # Type action
        type_group = QGroupBox("⌨️ Keyboard Actions")
        type_layout = QVBoxLayout(type_group)
        
        self.keys_input = QLineEdit()
        self.keys_input.setPlaceholderText("Enter text or keys to send (use {ENTER}, {TAB}, etc.)...")
        type_layout.addWidget(self.keys_input)
        
        type_btn_layout = QHBoxLayout()
        
        self.send_keys_btn = QPushButton("Send Keys")
        self.send_keys_btn.clicked.connect(self._on_send_keys)
        type_btn_layout.addWidget(self.send_keys_btn)
        
        self.set_value_btn = QPushButton("Set Value (Selected Control)")
        self.set_value_btn.clicked.connect(self._on_set_value)
        self.set_value_btn.setEnabled(False)
        type_btn_layout.addWidget(self.set_value_btn)
        
        type_layout.addLayout(type_btn_layout)
        layout.addWidget(type_group)
        
        # Process actions
        process_group = QGroupBox("🚀 Process Actions")
        process_layout = QVBoxLayout(process_group)
        
        start_layout = QHBoxLayout()
        self.process_path_input = QLineEdit()
        self.process_path_input.setPlaceholderText("Path to executable...")
        start_layout.addWidget(self.process_path_input)
        
        self.start_process_btn = QPushButton("Start Process")
        self.start_process_btn.clicked.connect(self._on_start_process)
        start_layout.addWidget(self.start_process_btn)
        
        process_layout.addLayout(start_layout)
        layout.addWidget(process_group)
        
        layout.addStretch()
        
        return tab
    
    def _create_command_tab(self) -> QWidget:
        """Create the raw command tab for advanced users"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Command input
        layout.addWidget(QLabel("Raw Automation Command (JSON):"))
        
        self.command_input = QTextEdit()
        self.command_input.setPlaceholderText("""{
    "action": "list_windows"
}

Or:

{
    "action": "invoke_control",
    "window": {"name_contains": "Notepad"},
    "control": {"control_type": "button", "name_contains": "OK"}
}""")
        self.command_input.setFont(QFont("Consolas", 10))
        layout.addWidget(self.command_input)
        
        # Execute button
        btn_layout = QHBoxLayout()
        
        self.execute_cmd_btn = QPushButton("▶️ Execute Command")
        self.execute_cmd_btn.clicked.connect(self._on_execute_raw_command)
        btn_layout.addWidget(self.execute_cmd_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Result output
        layout.addWidget(QLabel("Result:"))
        
        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        self.result_output.setFont(QFont("Consolas", 10))
        layout.addWidget(self.result_output)
        
        return tab
    
    def _create_log_tab(self) -> QWidget:
        """Create the automation log tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_output)
        
        # Clear log button
        btn_layout = QHBoxLayout()
        
        clear_btn = QPushButton("🗑️ Clear Log")
        clear_btn.clicked.connect(lambda: self.log_output.clear())
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return tab
    
    def _create_status_bar(self) -> QWidget:
        """Create status bar"""
        status_bar = QFrame()
        status_bar.setObjectName("status_bar")
        layout = QHBoxLayout(status_bar)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {CYBERPUNK_THEME['text_secondary']};")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # MCP status
        mcp_status = "✅ MCP Ready" if self.mcp_tools else "❌ MCP Unavailable"
        mcp_color = CYBERPUNK_THEME['success'] if self.mcp_tools else CYBERPUNK_THEME['error']
        self.mcp_status_label = QLabel(mcp_status)
        self.mcp_status_label.setStyleSheet(f"color: {mcp_color};")
        layout.addWidget(self.mcp_status_label)
        
        return status_bar
    
    def _apply_styling(self):
        """Apply cyberpunk styling to the tab"""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {CYBERPUNK_THEME['bg_primary']};
                color: {CYBERPUNK_THEME['text_primary']};
            }}
            
            QGroupBox {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }}
            
            QGroupBox::title {{
                color: {CYBERPUNK_THEME['accent']};
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            
            QPushButton {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                color: {CYBERPUNK_THEME['accent']};
                border: 1px solid {CYBERPUNK_THEME['accent']};
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: {CYBERPUNK_THEME['accent']};
                color: {CYBERPUNK_THEME['bg_primary']};
            }}
            
            QPushButton:disabled {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                color: {CYBERPUNK_THEME['text_secondary']};
                border-color: {CYBERPUNK_THEME['text_secondary']};
            }}
            
            QLineEdit, QTextEdit, QSpinBox {{
                background-color: {CYBERPUNK_THEME['bg_primary']};
                color: {CYBERPUNK_THEME['text_primary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                border-radius: 3px;
                padding: 5px;
            }}
            
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {CYBERPUNK_THEME['accent']};
            }}
            
            QTableWidget, QTreeWidget {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                gridline-color: {CYBERPUNK_THEME['border']};
            }}
            
            QTableWidget::item, QTreeWidget::item {{
                padding: 5px;
            }}
            
            QTableWidget::item:selected, QTreeWidget::item:selected {{
                background-color: {CYBERPUNK_THEME['accent']};
                color: {CYBERPUNK_THEME['bg_primary']};
            }}
            
            QHeaderView::section {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                color: {CYBERPUNK_THEME['accent']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                padding: 5px;
                font-weight: bold;
            }}
            
            QTabWidget::pane {{
                border: 1px solid {CYBERPUNK_THEME['border']};
                background-color: {CYBERPUNK_THEME['bg_secondary']};
            }}
            
            QTabBar::tab {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                color: {CYBERPUNK_THEME['text_secondary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {CYBERPUNK_THEME['accent']};
                color: {CYBERPUNK_THEME['bg_primary']};
            }}
            
            QCheckBox {{
                color: {CYBERPUNK_THEME['text_primary']};
            }}
            
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {CYBERPUNK_THEME['accent']};
                border-radius: 3px;
                background-color: {CYBERPUNK_THEME['bg_secondary']};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {CYBERPUNK_THEME['accent']};
            }}
            
            QProgressBar {{
                border: 1px solid {CYBERPUNK_THEME['border']};
                border-radius: 3px;
                text-align: center;
            }}
            
            QProgressBar::chunk {{
                background-color: {CYBERPUNK_THEME['accent']};
            }}
            
            #header_frame {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                border-radius: 5px;
            }}
            
            #status_bar {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                border-radius: 3px;
            }}
        """)
    
    def _setup_event_bus(self):
        """Setup event bus subscriptions"""
        if not self.event_bus:
            return
        
        try:
            # Subscribe to automation-related events
            if hasattr(self.event_bus, 'subscribe'):
                self.event_bus.subscribe('software.automation.request', self._handle_automation_request)
                self.event_bus.subscribe('mcp.tool.execute', self._handle_mcp_tool_execute)
                logger.info("✅ Software automation event bus subscriptions registered")
        except Exception as e:
            logger.error(f"❌ Failed to setup event bus: {e}")
    
    def _log(self, message: str, level: str = "info"):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_colors = {
            "info": CYBERPUNK_THEME['text_primary'],
            "success": CYBERPUNK_THEME['success'],
            "warning": CYBERPUNK_THEME['warning'],
            "error": CYBERPUNK_THEME['error']
        }
        color = level_colors.get(level, CYBERPUNK_THEME['text_primary'])
        
        html = f'<span style="color: {CYBERPUNK_THEME["text_secondary"]}">[{timestamp}]</span> '
        html += f'<span style="color: {color}">{message}</span><br>'
        
        self.log_output.insertHtml(html)
        self.log_output.ensureCursorVisible()
    
    def _set_status(self, message: str, busy: bool = False):
        """Update status bar"""
        self.status_label.setText(message)
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setRange(0, 0)  # Indeterminate
        else:
            self.progress_bar.setRange(0, 100)
    
    # === Event Handlers ===
    
    def _on_refresh_windows(self):
        """Refresh the windows list"""
        if not self.automation_manager:
            QMessageBox.warning(self, "Error", "Software automation not available")
            return
        
        self._set_status("Refreshing windows...", True)
        self._log("Refreshing windows list...")
        
        self._window_list_worker = WindowListWorker(self.automation_manager)
        self._window_list_worker.list_complete.connect(self._on_windows_list_received)
        self._window_list_worker.list_error.connect(self._on_windows_list_error)
        self._window_list_worker.start()
    
    def _on_windows_list_received(self, windows: List[Dict]):
        """Handle received windows list"""
        self.windows_list = windows
        self._update_windows_table()
        self._set_status(f"Found {len(windows)} windows", False)
        self._log(f"Found {len(windows)} windows", "success")
    
    def _on_windows_list_error(self, error: str):
        """Handle windows list error"""
        self._set_status("Error listing windows", False)
        self._log(f"Error: {error}", "error")
    
    def _update_windows_table(self):
        """Update the windows table with current list"""
        filter_text = self.window_search.text().lower()
        
        # Filter windows
        filtered = [
            w for w in self.windows_list
            if not filter_text or filter_text in (w.get("name") or "").lower()
        ]
        
        self.windows_table.setRowCount(len(filtered))
        
        for row, window in enumerate(filtered):
            name = window.get("name", "")
            pid = str(window.get("process_id", ""))
            class_name = window.get("class_name", "")
            
            # Check if this is the connected window
            is_connected = (
                self.connected_window and 
                window.get("hwnd") == self.connected_window.get("hwnd")
            )
            status = "🟢 Connected" if is_connected else "⚪"
            
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, window)
            pid_item = QTableWidgetItem(pid)
            class_item = QTableWidgetItem(class_name)
            status_item = QTableWidgetItem(status)
            
            if is_connected:
                for item in [name_item, pid_item, class_item, status_item]:
                    item.setBackground(QColor(CYBERPUNK_THEME['success']).darker(200))
            
            self.windows_table.setItem(row, 0, name_item)
            self.windows_table.setItem(row, 1, pid_item)
            self.windows_table.setItem(row, 2, class_item)
            self.windows_table.setItem(row, 3, status_item)
    
    def _on_window_search_changed(self, text: str):
        """Handle window search filter change"""
        self._update_windows_table()
    
    def _on_window_selected(self):
        """Handle window selection"""
        selected = self.windows_table.selectedItems()
        if selected:
            self.connect_btn.setEnabled(True)
            self.focus_btn.setEnabled(True)
        else:
            self.connect_btn.setEnabled(False)
            self.focus_btn.setEnabled(False)
    
    def _on_window_double_clicked(self, item: QTableWidgetItem):
        """Handle window double-click (auto-connect)"""
        self._on_connect_window()
    
    def _get_selected_window(self) -> Optional[Dict]:
        """Get the currently selected window data"""
        selected = self.windows_table.selectedItems()
        if not selected:
            return None
        
        row = selected[0].row()
        item = self.windows_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None
    
    def _on_connect_window(self):
        """Connect to selected window"""
        window = self._get_selected_window()
        if not window:
            return
        
        self.connected_window = window
        
        # Update UI
        self.connection_status_label.setText(f"🟢 Connected: {window.get('name', 'Unknown')[:30]}")
        self.connection_status_label.setStyleSheet(f"color: {CYBERPUNK_THEME['success']};")
        self.disconnect_btn.setEnabled(True)
        self.load_controls_btn.setEnabled(True)
        
        self._update_windows_table()
        self._log(f"Connected to: {window.get('name', 'Unknown')}", "success")
        
        # Set active target in MCP tools
        if self.mcp_tools:
            self.mcp_tools.execute_tool("connect_software", {"window": {"hwnd": window.get("hwnd")}})
        
        # Emit signal
        self.window_connected.emit(window)
        
        # Auto-load controls
        self._on_load_controls()
    
    def _on_disconnect_window(self):
        """Disconnect from current window"""
        self.connected_window = None
        
        # Update UI
        self.connection_status_label.setText("⚪ Not Connected")
        self.connection_status_label.setStyleSheet(f"color: {CYBERPUNK_THEME['text_secondary']};")
        self.disconnect_btn.setEnabled(False)
        self.load_controls_btn.setEnabled(False)
        
        # Clear controls
        self.controls_tree.clear()
        self.controls_list = []
        self.selected_control = None
        self.controls_count_label.setText("0 controls")
        
        self._update_windows_table()
        self._log("Disconnected from window", "info")
        
        # Clear active target in MCP tools
        if self.mcp_tools:
            self.mcp_tools.execute_tool("disconnect_software", {})
        
        # Emit signal
        self.window_disconnected.emit()
    
    def _on_focus_window(self):
        """Focus the selected window"""
        window = self._get_selected_window() or self.connected_window
        if not window:
            return
        
        if not self.automation_manager:
            return
        
        result = self.automation_manager.execute({
            "action": "focus_window",
            "window": {"hwnd": window.get("hwnd")}
        })
        
        if result.get("success"):
            self._log(f"Focused: {window.get('name', 'Unknown')}", "success")
        else:
            self._log(f"Focus failed: {result.get('error', 'Unknown')}", "error")
    
    def _on_auto_refresh_toggled(self, state: int):
        """Toggle auto-refresh"""
        if state == Qt.CheckState.Checked.value:
            self._refresh_timer.start(5000)  # Refresh every 5 seconds
            self._log("Auto-refresh enabled (5s interval)", "info")
        else:
            self._refresh_timer.stop()
            self._log("Auto-refresh disabled", "info")
    
    def _on_load_controls(self):
        """Load controls for connected window"""
        if not self.connected_window or not self.automation_manager:
            return
        
        self._set_status("Loading controls...", True)
        self._log("Loading window controls...")
        
        self._control_list_worker = ControlListWorker(
            self.automation_manager, 
            {"hwnd": self.connected_window.get("hwnd")}
        )
        self._control_list_worker.list_complete.connect(self._on_controls_list_received)
        self._control_list_worker.list_error.connect(self._on_controls_list_error)
        self._control_list_worker.start()
    
    def _on_controls_list_received(self, controls: List[Dict]):
        """Handle received controls list"""
        self.controls_list = controls
        self._update_controls_tree()
        self._set_status(f"Loaded {len(controls)} controls", False)
        self._log(f"Loaded {len(controls)} controls", "success")
        self.controls_count_label.setText(f"{len(controls)} controls")
    
    def _on_controls_list_error(self, error: str):
        """Handle controls list error"""
        self._set_status("Error loading controls", False)
        self._log(f"Error: {error}", "error")
    
    def _update_controls_tree(self):
        """Update the controls tree"""
        self.controls_tree.clear()
        
        for control in self.controls_list:
            control_type = control.get("control_type", "Unknown")
            config = CONTROL_TYPE_CONFIG.get(control_type, {"icon": "❓", "label": "Unknown"})
            
            name = control.get("name", "") or control.get("automation_id", "") or "(unnamed)"
            display_name = f"{config['icon']} {name[:50]}"
            
            bounds = control.get("bounding", {})
            bounds_str = f"({bounds.get('x', 0)}, {bounds.get('y', 0)}) {bounds.get('width', 0)}x{bounds.get('height', 0)}"
            
            item = QTreeWidgetItem([
                display_name,
                config.get("label", control_type),
                control.get("automation_id", ""),
                bounds_str
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, control)
            
            self.controls_tree.addTopLevelItem(item)
    
    def _on_control_selected(self, item: QTreeWidgetItem, column: int):
        """Handle control selection"""
        control = item.data(0, Qt.ItemDataRole.UserRole)
        if control:
            self.selected_control = control
            
            # Update details
            self.control_name_label.setText(control.get("name", "-") or "-")
            self.control_type_label.setText(control.get("control_type", "-"))
            self.control_id_label.setText(control.get("automation_id", "-") or "-")
            
            bounds = control.get("bounding", {})
            self.control_bounds_label.setText(
                f"X: {bounds.get('x', 0)}, Y: {bounds.get('y', 0)}, "
                f"W: {bounds.get('width', 0)}, H: {bounds.get('height', 0)}"
            )
            
            # Set click coordinates to center of control
            if bounds:
                center_x = int(bounds.get('x', 0) + bounds.get('width', 0) / 2)
                center_y = int(bounds.get('y', 0) + bounds.get('height', 0) / 2)
                self.click_x_spin.setValue(center_x)
                self.click_y_spin.setValue(center_y)
            
            # Enable control actions
            self.invoke_control_btn.setEnabled(True)
            self.set_value_btn.setEnabled(True)
    
    def _on_control_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle control double-click (invoke)"""
        self._on_invoke_control()
    
    def _on_invoke_control(self):
        """Invoke the selected control"""
        if not self.selected_control or not self.connected_window or not self.automation_manager:
            return
        
        self._set_status("Invoking control...", True)
        
        result = self.automation_manager.execute({
            "action": "invoke_control",
            "window": {"hwnd": self.connected_window.get("hwnd")},
            "control": {
                "automation_id": self.selected_control.get("automation_id"),
                "name_contains": self.selected_control.get("name"),
                "control_type": self.selected_control.get("control_type", "").replace("ControlType.", "")
            }
        })
        
        self._set_status("Ready", False)
        
        if result.get("success"):
            self._log(f"Invoked: {self.selected_control.get('name', 'control')}", "success")
        else:
            self._log(f"Invoke failed: {result.get('error', 'Unknown')}", "error")
    
    def _on_click_at(self, button: str = "left"):
        """Click at coordinates"""
        if not self.connected_window or not self.automation_manager:
            return
        
        x = self.click_x_spin.value()
        y = self.click_y_spin.value()
        
        result = self.automation_manager.execute({
            "action": "click_at",
            "window": {"hwnd": self.connected_window.get("hwnd")},
            "x": x,
            "y": y,
            "button": button
        })
        
        if result.get("success"):
            self._log(f"Clicked at ({x}, {y}) - {button}", "success")
        else:
            self._log(f"Click failed: {result.get('error', 'Unknown')}", "error")
    
    def _on_send_keys(self):
        """Send keys to window"""
        if not self.connected_window or not self.automation_manager:
            QMessageBox.warning(self, "Error", "Not connected to a window")
            return
        
        keys = self.keys_input.text()
        if not keys:
            return
        
        result = self.automation_manager.execute({
            "action": "send_keys",
            "window": {"hwnd": self.connected_window.get("hwnd")},
            "keys": keys
        })
        
        if result.get("success"):
            self._log(f"Sent keys: {keys}", "success")
        else:
            self._log(f"Send keys failed: {result.get('error', 'Unknown')}", "error")
    
    def _on_set_value(self):
        """Set value on selected control"""
        if not self.selected_control or not self.connected_window or not self.automation_manager:
            return
        
        value = self.keys_input.text()
        if not value:
            return
        
        result = self.automation_manager.execute({
            "action": "set_value",
            "window": {"hwnd": self.connected_window.get("hwnd")},
            "control": {
                "automation_id": self.selected_control.get("automation_id"),
                "name_contains": self.selected_control.get("name")
            },
            "value": value
        })
        
        if result.get("success"):
            self._log(f"Set value: {value}", "success")
        else:
            self._log(f"Set value failed: {result.get('error', 'Unknown')}", "error")
    
    def _on_start_process(self):
        """Start a new process"""
        if not self.automation_manager:
            return
        
        path = self.process_path_input.text()
        if not path:
            QMessageBox.warning(self, "Error", "Please enter a process path")
            return
        
        result = self.automation_manager.execute({
            "action": "start_process",
            "path": path
        })
        
        if result.get("success"):
            pid = result.get("process_id", "unknown")
            self._log(f"Started process: {path} (PID: {pid})", "success")
            # Refresh windows list
            QTimer.singleShot(1000, self._on_refresh_windows)
        else:
            self._log(f"Start process failed: {result.get('error', 'Unknown')}", "error")
    
    def _on_execute_raw_command(self):
        """Execute raw automation command"""
        if not self.automation_manager:
            return
        
        try:
            command_text = self.command_input.toPlainText()
            command = json.loads(command_text)
        except json.JSONDecodeError as e:
            self.result_output.setPlainText(f"Invalid JSON: {e}")
            return
        
        result = self.automation_manager.execute(command)
        
        # Format result
        result_text = json.dumps(result, indent=2, default=str)
        self.result_output.setPlainText(result_text)
        
        if result.get("success"):
            self._log(f"Command executed: {command.get('action', 'unknown')}", "success")
        else:
            self._log(f"Command failed: {result.get('error', 'Unknown')}", "error")
    
    # === Event Bus Handlers ===
    
    def _handle_automation_request(self, data: Dict):
        """Handle automation request from event bus"""
        try:
            action = data.get("action")
            if action and self.mcp_tools:
                result = self.mcp_tools.execute_tool(action, data.get("parameters", {}))
                self._log(f"Event bus request: {action} -> {result.get('success')}", 
                         "success" if result.get("success") else "error")
        except Exception as e:
            self._log(f"Event bus error: {e}", "error")
    
    def _handle_mcp_tool_execute(self, data: Dict):
        """Handle MCP tool execution request"""
        tool_name = data.get("tool")
        if tool_name and tool_name.startswith("software_"):
            # Strip prefix and execute
            actual_tool = tool_name.replace("software_", "")
            if self.mcp_tools:
                result = self.mcp_tools.execute_tool(actual_tool, data.get("parameters", {}))
                # Publish result back
                if self.event_bus:
                    self.event_bus.publish("mcp.tool.result", {
                        "tool": tool_name,
                        "result": result
                    })
    
    # === Public API ===
    
    def get_mcp_tools(self) -> Optional["SoftwareAutomationMCPTools"]:
        """Get MCP tools for external access"""
        return self.mcp_tools
    
    def get_connected_window(self) -> Optional[Dict]:
        """Get currently connected window"""
        return self.connected_window
    
    def execute_automation(self, action: str, parameters: Dict) -> Dict:
        """Execute automation action programmatically"""
        if not self.mcp_tools:
            return {"success": False, "error": "MCP tools not available"}
        
        result = self.mcp_tools.execute_tool(action, parameters)
        self.automation_executed.emit(action, result)
        return result
