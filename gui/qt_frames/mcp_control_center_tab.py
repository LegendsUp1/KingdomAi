#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Control Center Tab for Kingdom AI - SOTA 2026

SOLVES THE "TOWER OF BABEL" PROBLEM:
- Unified interface for ALL MCP tools across all systems
- Visual tool discovery - users can see all available capabilities
- One-click tool execution with parameter forms
- Real-time system status monitoring
- No more hidden features or CLI-only access

This tab exposes:
- Device Takeover MCP (microcontroller control)
- Software Automation MCP (Windows app control)
- Unity MCP (game engine control)
- Thoth AI MCP (AI model control)
- All other integrated MCP tools

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
    QTabWidget, QGridLayout, QCheckBox, QFormLayout, QDialog,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtGui import QIcon, QColor, QFont, QAction

logger = logging.getLogger("KingdomAI.MCPControlCenter")


# Import MCP connector
try:
    from core.mcp_connector import (
        UnifiedMCPConnector, get_unified_mcp_connector, MCPTool
    )
    MCP_CONNECTOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"MCP connector not available: {e}")
    MCP_CONNECTOR_AVAILABLE = False
    UnifiedMCPConnector = None
    MCPTool = None

# Import individual MCP systems for direct access
try:
    from core.unity_mcp_integration import get_unity_mcp_tools, UnityMCPTools
    UNITY_MCP_AVAILABLE = True
except ImportError:
    UNITY_MCP_AVAILABLE = False
    UnityMCPTools = None

try:
    from core.software_automation_manager import SoftwareAutomationManager, SoftwareAutomationMCPTools
    SOFTWARE_MCP_AVAILABLE = True
except ImportError:
    SOFTWARE_MCP_AVAILABLE = False

try:
    from core.device_takeover_system import DeviceTakeover
    DEVICE_MCP_AVAILABLE = True
except ImportError:
    DEVICE_MCP_AVAILABLE = False

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


# Category icons and descriptions
MCP_CATEGORY_CONFIG = {
    "device": {
        "icon": "🔌",
        "color": "#00d4ff",
        "label": "Device Takeover",
        "description": "Control microcontrollers, USB devices, and hardware"
    },
    "software": {
        "icon": "🖥️",
        "color": "#ff00ff",
        "label": "Software Automation",
        "description": "Automate any Windows application"
    },
    "unity": {
        "icon": "🎮",
        "color": "#00ff88",
        "label": "Unity Engine",
        "description": "Create, build, and control Unity projects"
    },
    "thoth": {
        "icon": "🧠",
        "color": "#ffaa00",
        "label": "Thoth AI",
        "description": "AI model control and code generation"
    },
    "unknown": {
        "icon": "🔧",
        "color": "#666666",
        "label": "Other Tools",
        "description": "Miscellaneous MCP tools"
    }
}


class ToolExecutionWorker(QThread):
    """Background worker for MCP tool execution"""
    execution_complete = pyqtSignal(dict)
    execution_error = pyqtSignal(str)
    
    def __init__(self, mcp_connector, tool_name: str, parameters: Dict):
        super().__init__()
        self.mcp_connector = mcp_connector
        self.tool_name = tool_name
        self.parameters = parameters
    
    def run(self):
        try:
            result = self.mcp_connector.execute_tool(self.tool_name, self.parameters)
            self.execution_complete.emit(result)
        except Exception as e:
            self.execution_error.emit(str(e))


class ToolParameterDialog(QDialog):
    """Dialog for entering tool parameters before execution"""
    
    def __init__(self, tool_name: str, parameters_schema: Dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Execute Tool: {tool_name}")
        self.setMinimumWidth(500)
        self.parameters_schema = parameters_schema
        self.parameter_inputs = {}
        
        self._setup_ui(tool_name)
        self._apply_styling()
    
    def _setup_ui(self, tool_name: str):
        layout = QVBoxLayout(self)
        
        # Tool name header
        header = QLabel(f"🔧 {tool_name}")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {CYBERPUNK_THEME['accent']};")
        layout.addWidget(header)
        
        # Parameters form
        form_group = QGroupBox("Parameters")
        form_layout = QFormLayout(form_group)
        
        properties = self.parameters_schema.get("properties", {})
        required = self.parameters_schema.get("required", [])
        
        if not properties:
            no_params_label = QLabel("This tool requires no parameters")
            no_params_label.setStyleSheet(f"color: {CYBERPUNK_THEME['text_secondary']};")
            form_layout.addRow(no_params_label)
        else:
            for param_name, param_info in properties.items():
                param_type = param_info.get("type", "string")
                is_required = param_name in required
                
                label_text = f"{param_name}{'*' if is_required else ''}"
                
                if param_type == "integer":
                    input_widget = QSpinBox()
                    input_widget.setRange(-999999, 999999)
                    input_widget.setValue(0)
                elif param_type == "boolean":
                    input_widget = QCheckBox()
                elif param_type == "object":
                    input_widget = QTextEdit()
                    input_widget.setMaximumHeight(80)
                    input_widget.setPlaceholderText("Enter JSON object...")
                else:
                    input_widget = QLineEdit()
                    input_widget.setPlaceholderText(f"Enter {param_name}...")
                
                self.parameter_inputs[param_name] = (input_widget, param_type)
                form_layout.addRow(label_text, input_widget)
        
        layout.addWidget(form_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _apply_styling(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {CYBERPUNK_THEME['bg_primary']};
                color: {CYBERPUNK_THEME['text_primary']};
            }}
            QGroupBox {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                color: {CYBERPUNK_THEME['accent']};
            }}
            QLineEdit, QTextEdit, QSpinBox {{
                background-color: {CYBERPUNK_THEME['bg_primary']};
                color: {CYBERPUNK_THEME['text_primary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                border-radius: 3px;
                padding: 5px;
            }}
            QPushButton {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                color: {CYBERPUNK_THEME['accent']};
                border: 1px solid {CYBERPUNK_THEME['accent']};
                border-radius: 5px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {CYBERPUNK_THEME['accent']};
                color: {CYBERPUNK_THEME['bg_primary']};
            }}
        """)
    
    def get_parameters(self) -> Dict:
        """Get the entered parameters"""
        result = {}
        for param_name, (widget, param_type) in self.parameter_inputs.items():
            if param_type == "integer":
                result[param_name] = widget.value()
            elif param_type == "boolean":
                result[param_name] = widget.isChecked()
            elif param_type == "object":
                try:
                    text = widget.toPlainText()
                    if text.strip():
                        result[param_name] = json.loads(text)
                except json.JSONDecodeError:
                    pass
            else:
                text = widget.text()
                if text.strip():
                    result[param_name] = text
        return result


class MCPControlCenterTab(QWidget):
    """MCP Control Center - Unified interface for all MCP tools"""
    
    # Signals
    tool_executed = pyqtSignal(str, dict)
    system_status_changed = pyqtSignal(dict)
    
    def __init__(self, event_bus=None, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.setObjectName("MCPControlCenterTab")
        
        # Initialize MCP connector
        self.mcp_connector = None
        if MCP_CONNECTOR_AVAILABLE:
            try:
                self.mcp_connector = get_unified_mcp_connector(event_bus)
                logger.info("✅ MCP Control Center connected to unified MCP connector")
            except Exception as e:
                logger.error(f"❌ Failed to initialize MCP connector: {e}")
        
        # State
        self.tools_by_category: Dict[str, List[Dict]] = {}
        self.selected_tool: Optional[Dict] = None
        self._execution_worker = None
        
        # Build UI
        self._setup_ui()
        self._apply_styling()
        self._setup_event_bus()
        
        # Load tools
        self._refresh_tools()
        
        # Auto-refresh timer for status
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(10000)  # Every 10 seconds
        
        logger.info("✅ MCP Control Center Tab initialized")
    
    def _setup_ui(self):
        """Build the complete UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header with status overview
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - System status and categories
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Tools and execution
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([350, 650])
        main_layout.addWidget(splitter, 1)
        
        # Bottom panel - Execution log
        log_panel = self._create_log_panel()
        main_layout.addWidget(log_panel)
    
    def _create_header(self) -> QWidget:
        """Create header with title and quick actions"""
        header = QFrame()
        header.setObjectName("header_frame")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Title
        title_label = QLabel("🎛️ MCP Control Center")
        title_label.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {CYBERPUNK_THEME['accent']};
        """)
        layout.addWidget(title_label)
        
        # Subtitle
        subtitle = QLabel("Unified Tool Discovery & Execution")
        subtitle.setStyleSheet(f"color: {CYBERPUNK_THEME['text_secondary']}; font-size: 12px;")
        layout.addWidget(subtitle)
        
        layout.addStretch()
        
        # Total tools count
        self.total_tools_label = QLabel("0 tools available")
        self.total_tools_label.setStyleSheet(f"color: {CYBERPUNK_THEME['accent']};")
        layout.addWidget(self.total_tools_label)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh All")
        refresh_btn.clicked.connect(self._refresh_tools)
        layout.addWidget(refresh_btn)
        
        return header
    
    def _create_left_panel(self) -> QWidget:
        """Create left panel with system status and categories"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # System Status Group
        status_group = QGroupBox("🔋 MCP Systems Status")
        status_layout = QVBoxLayout(status_group)
        
        # Status indicators for each system
        self.system_status_widgets = {}
        
        systems = [
            ("device", "🔌 Device Takeover", DEVICE_MCP_AVAILABLE),
            ("software", "🖥️ Software Automation", SOFTWARE_MCP_AVAILABLE),
            ("unity", "🎮 Unity Engine", UNITY_MCP_AVAILABLE),
            ("thoth", "🧠 Thoth AI", MCP_CONNECTOR_AVAILABLE),
        ]
        
        for sys_id, sys_name, available in systems:
            row = QHBoxLayout()
            
            status_icon = QLabel("✅" if available else "❌")
            status_icon.setFixedWidth(30)
            row.addWidget(status_icon)
            
            name_label = QLabel(sys_name)
            name_label.setStyleSheet(f"color: {CYBERPUNK_THEME['text_primary']};")
            row.addWidget(name_label, 1)
            
            tools_count = QLabel("0 tools")
            tools_count.setStyleSheet(f"color: {CYBERPUNK_THEME['text_secondary']};")
            row.addWidget(tools_count)
            
            self.system_status_widgets[sys_id] = {
                "icon": status_icon,
                "name": name_label,
                "count": tools_count
            }
            
            status_layout.addLayout(row)
        
        layout.addWidget(status_group)
        
        # Category Tree
        category_group = QGroupBox("📂 Tool Categories")
        category_layout = QVBoxLayout(category_group)
        
        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderHidden(True)
        self.category_tree.itemClicked.connect(self._on_category_selected)
        category_layout.addWidget(self.category_tree)
        
        layout.addWidget(category_group, 1)
        
        # Quick Actions
        quick_group = QGroupBox("⚡ Quick Actions")
        quick_layout = QGridLayout(quick_group)
        
        # Common quick action buttons
        quick_actions = [
            ("🔍 Find Devices", self._quick_find_devices, 0, 0),
            ("📋 List Windows", self._quick_list_windows, 0, 1),
            ("🎮 Launch Unity Hub", self._quick_launch_unity, 1, 0),
            ("🔗 Connect Device", self._quick_connect_device, 1, 1),
        ]
        
        for label, callback, row, col in quick_actions:
            btn = QPushButton(label)
            btn.clicked.connect(callback)
            btn.setMinimumHeight(40)
            quick_layout.addWidget(btn, row, col)
        
        layout.addWidget(quick_group)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """Create right panel with tools list and execution"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tools table
        tools_group = QGroupBox("🔧 Available Tools")
        tools_layout = QVBoxLayout(tools_group)
        
        # Search filter
        search_layout = QHBoxLayout()
        self.tool_search = QLineEdit()
        self.tool_search.setPlaceholderText("🔍 Search tools by name or description...")
        self.tool_search.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.tool_search)
        
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", "all")
        for cat_id, cat_info in MCP_CATEGORY_CONFIG.items():
            self.category_filter.addItem(f"{cat_info['icon']} {cat_info['label']}", cat_id)
        self.category_filter.currentIndexChanged.connect(self._on_filter_changed)
        search_layout.addWidget(self.category_filter)
        
        tools_layout.addLayout(search_layout)
        
        # Tools table
        self.tools_table = QTableWidget()
        self.tools_table.setColumnCount(4)
        self.tools_table.setHorizontalHeaderLabels(["Tool", "Category", "Description", "Action"])
        self.tools_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tools_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tools_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tools_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tools_table.setColumnWidth(0, 180)
        self.tools_table.setColumnWidth(1, 120)
        self.tools_table.setColumnWidth(3, 100)
        self.tools_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tools_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tools_table.itemSelectionChanged.connect(self._on_tool_selected)
        tools_layout.addWidget(self.tools_table)
        
        layout.addWidget(tools_group, 1)
        
        # Tool details panel
        details_group = QGroupBox("📋 Tool Details")
        details_layout = QVBoxLayout(details_group)
        
        # Tool info
        info_layout = QGridLayout()
        
        self.detail_name = QLabel("-")
        self.detail_name.setStyleSheet(f"font-weight: bold; color: {CYBERPUNK_THEME['accent']};")
        self.detail_category = QLabel("-")
        self.detail_description = QLabel("-")
        self.detail_description.setWordWrap(True)
        
        info_layout.addWidget(QLabel("Name:"), 0, 0)
        info_layout.addWidget(self.detail_name, 0, 1)
        info_layout.addWidget(QLabel("Category:"), 1, 0)
        info_layout.addWidget(self.detail_category, 1, 1)
        info_layout.addWidget(QLabel("Description:"), 2, 0)
        info_layout.addWidget(self.detail_description, 2, 1)
        
        details_layout.addLayout(info_layout)
        
        # Parameters display
        self.params_display = QTextEdit()
        self.params_display.setReadOnly(True)
        self.params_display.setMaximumHeight(80)
        self.params_display.setPlaceholderText("Select a tool to see its parameters...")
        details_layout.addWidget(self.params_display)
        
        # Execute button
        btn_layout = QHBoxLayout()
        
        self.execute_btn = QPushButton("▶️ Execute Tool")
        self.execute_btn.clicked.connect(self._on_execute_tool)
        self.execute_btn.setEnabled(False)
        self.execute_btn.setMinimumHeight(40)
        self.execute_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {CYBERPUNK_THEME['success']};
                color: {CYBERPUNK_THEME['bg_primary']};
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #00cc77;
            }}
            QPushButton:disabled {{
                background-color: {CYBERPUNK_THEME['border']};
                color: {CYBERPUNK_THEME['text_secondary']};
            }}
        """)
        btn_layout.addWidget(self.execute_btn)
        
        details_layout.addLayout(btn_layout)
        
        layout.addWidget(details_group)
        
        return panel
    
    def _create_log_panel(self) -> QWidget:
        """Create bottom panel for execution log"""
        group = QGroupBox("📜 Execution Log")
        layout = QVBoxLayout(group)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        self.log_output.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_output)
        
        # Clear button
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("🗑️ Clear Log")
        clear_btn.clicked.connect(lambda: self.log_output.clear())
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        group.setMaximumHeight(180)
        return group
    
    def _apply_styling(self):
        """Apply cyberpunk styling"""
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
            
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {CYBERPUNK_THEME['bg_primary']};
                color: {CYBERPUNK_THEME['text_primary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                border-radius: 3px;
                padding: 5px;
            }}
            
            QTableWidget, QTreeWidget {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                gridline-color: {CYBERPUNK_THEME['border']};
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
            
            #header_frame {{
                background-color: {CYBERPUNK_THEME['bg_secondary']};
                border: 1px solid {CYBERPUNK_THEME['border']};
                border-radius: 5px;
            }}
        """)
    
    def _setup_event_bus(self):
        """Setup event bus subscriptions"""
        if not self.event_bus:
            return
        
        try:
            if hasattr(self.event_bus, 'subscribe'):
                self.event_bus.subscribe('mcp.tool.executed', self._handle_tool_executed)
                self.event_bus.subscribe('mcp.status.changed', self._handle_status_changed)
                logger.info("✅ MCP Control Center event bus subscriptions registered")
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
    
    # === Data Loading ===
    
    def _refresh_tools(self):
        """Refresh all tools from MCP connector"""
        if not self.mcp_connector:
            self._log("MCP connector not available", "error")
            return
        
        try:
            # Get all tools
            all_tools = self.mcp_connector.get_all_tools()
            
            # Organize by category
            self.tools_by_category = {}
            for tool in all_tools:
                category = tool.category if hasattr(tool, 'category') else 'unknown'
                if category not in self.tools_by_category:
                    self.tools_by_category[category] = []
                self.tools_by_category[category].append(tool)
            
            # Update UI
            self._update_category_tree()
            self._update_tools_table()
            self._update_status_counts()
            
            total = len(all_tools)
            self.total_tools_label.setText(f"{total} tools available")
            self._log(f"Loaded {total} MCP tools from {len(self.tools_by_category)} categories", "success")
            
        except Exception as e:
            self._log(f"Error loading tools: {e}", "error")
            logger.error(f"Error refreshing tools: {e}")
    
    def _update_category_tree(self):
        """Update the category tree"""
        self.category_tree.clear()
        
        for category, tools in sorted(self.tools_by_category.items()):
            config = MCP_CATEGORY_CONFIG.get(category, MCP_CATEGORY_CONFIG['unknown'])
            
            cat_item = QTreeWidgetItem([f"{config['icon']} {config['label']} ({len(tools)})"])
            cat_item.setData(0, Qt.ItemDataRole.UserRole, category)
            
            for tool in tools:
                tool_name = tool.name if hasattr(tool, 'name') else str(tool)
                tool_item = QTreeWidgetItem([f"  🔧 {tool_name}"])
                tool_item.setData(0, Qt.ItemDataRole.UserRole, tool)
                cat_item.addChild(tool_item)
            
            self.category_tree.addTopLevelItem(cat_item)
        
        self.category_tree.expandAll()
    
    def _update_tools_table(self, filter_category: str = "all", search_text: str = ""):
        """Update tools table with optional filters"""
        self.tools_table.setRowCount(0)
        
        all_tools = []
        for category, tools in self.tools_by_category.items():
            if filter_category != "all" and category != filter_category:
                continue
            for tool in tools:
                all_tools.append((tool, category))
        
        # Apply search filter
        if search_text:
            search_lower = search_text.lower()
            all_tools = [
                (tool, cat) for tool, cat in all_tools
                if search_lower in (tool.name if hasattr(tool, 'name') else str(tool)).lower()
                or search_lower in (tool.description if hasattr(tool, 'description') else '').lower()
            ]
        
        self.tools_table.setRowCount(len(all_tools))
        
        for row, (tool, category) in enumerate(all_tools):
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            description = tool.description if hasattr(tool, 'description') else ''
            config = MCP_CATEGORY_CONFIG.get(category, MCP_CATEGORY_CONFIG['unknown'])
            
            # Tool name
            name_item = QTableWidgetItem(f"🔧 {tool_name}")
            name_item.setData(Qt.ItemDataRole.UserRole, tool)
            self.tools_table.setItem(row, 0, name_item)
            
            # Category
            cat_item = QTableWidgetItem(f"{config['icon']} {config['label']}")
            self.tools_table.setItem(row, 1, cat_item)
            
            # Description
            desc_item = QTableWidgetItem(description[:80] + "..." if len(description) > 80 else description)
            self.tools_table.setItem(row, 2, desc_item)
            
            # Execute button
            exec_btn = QPushButton("▶️ Run")
            exec_btn.clicked.connect(lambda checked, t=tool: self._execute_tool_direct(t))
            self.tools_table.setCellWidget(row, 3, exec_btn)
    
    def _update_status_counts(self):
        """Update tool counts in status panel"""
        for category, widgets in self.system_status_widgets.items():
            count = len(self.tools_by_category.get(category, []))
            widgets['count'].setText(f"{count} tools")
    
    def _refresh_status(self):
        """Refresh system status"""
        if not self.mcp_connector:
            return
        
        try:
            status = self.mcp_connector.get_system_status()
            # Could update status indicators here if needed
        except Exception as e:
            logger.warning(f"Status refresh error: {e}")
    
    # === Event Handlers ===
    
    def _on_category_selected(self, item: QTreeWidgetItem, column: int):
        """Handle category/tool selection in tree"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if isinstance(data, str):
            # Category selected - filter table
            self.category_filter.setCurrentIndex(
                self.category_filter.findData(data)
            )
        elif data is not None:
            # Tool selected
            self.selected_tool = data
            self._update_tool_details(data)
    
    def _on_tool_selected(self):
        """Handle tool selection in table"""
        selected = self.tools_table.selectedItems()
        if selected:
            item = self.tools_table.item(selected[0].row(), 0)
            tool = item.data(Qt.ItemDataRole.UserRole)
            if tool:
                self.selected_tool = tool
                self._update_tool_details(tool)
    
    def _on_search_changed(self, text: str):
        """Handle search text change"""
        category = self.category_filter.currentData()
        self._update_tools_table(category, text)
    
    def _on_filter_changed(self, index: int):
        """Handle category filter change"""
        category = self.category_filter.currentData()
        search = self.tool_search.text()
        self._update_tools_table(category, search)
    
    def _update_tool_details(self, tool):
        """Update tool details panel"""
        name = tool.name if hasattr(tool, 'name') else str(tool)
        category = tool.category if hasattr(tool, 'category') else 'unknown'
        description = tool.description if hasattr(tool, 'description') else ''
        parameters = tool.parameters if hasattr(tool, 'parameters') else {}
        
        config = MCP_CATEGORY_CONFIG.get(category, MCP_CATEGORY_CONFIG['unknown'])
        
        self.detail_name.setText(name)
        self.detail_category.setText(f"{config['icon']} {config['label']}")
        self.detail_description.setText(description)
        
        # Show parameters
        params_text = json.dumps(parameters, indent=2) if parameters else "No parameters required"
        self.params_display.setPlainText(params_text)
        
        self.execute_btn.setEnabled(True)
    
    def _on_execute_tool(self):
        """Execute the selected tool"""
        if not self.selected_tool:
            return
        
        self._execute_tool_direct(self.selected_tool)
    
    def _execute_tool_direct(self, tool):
        """Execute a tool with parameter dialog"""
        if not self.mcp_connector:
            QMessageBox.warning(self, "Error", "MCP connector not available")
            return
        
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        parameters = tool.parameters if hasattr(tool, 'parameters') else {}
        
        # Show parameter dialog
        dialog = ToolParameterDialog(tool_name, parameters, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            params = dialog.get_parameters()
            
            self._log(f"Executing: {tool_name}...", "info")
            
            # Execute in background
            self._execution_worker = ToolExecutionWorker(
                self.mcp_connector, tool_name, params
            )
            self._execution_worker.execution_complete.connect(self._on_execution_complete)
            self._execution_worker.execution_error.connect(self._on_execution_error)
            self._execution_worker.start()
    
    def _on_execution_complete(self, result: Dict):
        """Handle execution completion"""
        success = result.get("success", False)
        
        if success:
            self._log(f"✅ Execution successful: {json.dumps(result, default=str)[:200]}", "success")
        else:
            error = result.get("error", "Unknown error")
            self._log(f"⚠️ Execution returned: {error}", "warning")
        
        self.tool_executed.emit("", result)
    
    def _on_execution_error(self, error: str):
        """Handle execution error"""
        self._log(f"❌ Execution failed: {error}", "error")
    
    # === Quick Actions ===
    
    def _quick_find_devices(self):
        """Quick action: Find all devices"""
        if not self.mcp_connector:
            return
        
        self._log("Finding devices...", "info")
        result = self.mcp_connector.execute_tool("find_all_devices", {})
        
        if result.get("success"):
            devices = result.get("devices", [])
            self._log(f"Found {len(devices)} devices", "success")
        else:
            self._log(f"Device scan failed: {result.get('error')}", "error")
    
    def _quick_list_windows(self):
        """Quick action: List all windows"""
        if not self.mcp_connector:
            return
        
        self._log("Listing windows...", "info")
        result = self.mcp_connector.execute_tool("list_windows", {})
        
        if result.get("success"):
            windows = result.get("windows", [])
            self._log(f"Found {len(windows)} windows", "success")
        else:
            self._log(f"Window list failed: {result.get('error')}", "error")
    
    def _quick_launch_unity(self):
        """Quick action: Launch Unity Hub"""
        if not self.mcp_connector:
            return
        
        self._log("Launching Unity Hub...", "info")
        result = self.mcp_connector.execute_tool("unity_launch_hub", {})
        
        if result.get("success"):
            self._log("Unity Hub launched", "success")
        else:
            self._log(f"Unity Hub launch failed: {result.get('error')}", "error")
    
    def _quick_connect_device(self):
        """Quick action: Connect to first available device"""
        if not self.mcp_connector:
            return
        
        self._log("Connecting to device...", "info")
        # First find devices
        result = self.mcp_connector.execute_tool("find_all_devices", {})
        
        if result.get("success"):
            devices = result.get("devices", [])
            if devices:
                device = devices[0]
                device_id = device.get("id") or device.get("port") or "unknown"
                self._log(f"Found device: {device_id}", "info")
                
                # Connect to first device
                connect_result = self.mcp_connector.execute_tool("connect_device", {
                    "device_id": device_id
                })
                
                if connect_result.get("success"):
                    self._log(f"Connected to: {device_id}", "success")
                else:
                    self._log(f"Connection failed: {connect_result.get('error')}", "error")
            else:
                self._log("No devices found", "warning")
        else:
            self._log(f"Device scan failed: {result.get('error')}", "error")
    
    # === Event Bus Handlers ===
    
    def _handle_tool_executed(self, data: Dict):
        """Handle tool execution event"""
        tool = data.get("tool", "unknown")
        result = data.get("result", {})
        self._log(f"Tool executed: {tool}", "info")
    
    def _handle_status_changed(self, data: Dict):
        """Handle status change event"""
        self._refresh_status()
    
    # === Public API ===
    
    def get_mcp_connector(self):
        """Get the MCP connector for external access"""
        return self.mcp_connector
    
    def execute_tool(self, tool_name: str, parameters: Dict) -> Dict:
        """Execute a tool programmatically"""
        if not self.mcp_connector:
            return {"success": False, "error": "MCP connector not available"}
        
        return self.mcp_connector.execute_tool(tool_name, parameters)
