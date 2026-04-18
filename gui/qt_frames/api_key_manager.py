"""
API Key Manager for Kingdom AI - Qt Implementation

This module provides a modern, secure API key management interface
with Redis Quantum Nexus integration and strict connection requirements.
"""

import os
import sys
import json
import logging
import asyncio
import base64
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union

# Qt imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QComboBox, QMessageBox, QInputDialog,
    QFileDialog, QSplitter, QFormLayout, QGroupBox, QTextEdit, QStatusBar,
    QApplication, QMainWindow, QMenu, QHeaderView, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QDialog, QDialogButtonBox, QCheckBox, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, QSize, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon, QColor, QFont, QPixmap, QAction, QPainter, QLinearGradient

# Application imports
from core.api_key_manager import APIKeyManager
from core.api_key_manager_connector import APIKeyManagerConnector
from core.redis_quantum_nexus import RedisQuantumNexus
from gui.qt_styles import get_style_sheet
from gui.qt_utils import get_icon, async_slot, Worker, WorkerSignals

logger = logging.getLogger("KingdomAI.APIKeyManager")

class APIKeyManagerWindow(QMainWindow):
    """Main window for the API Key Manager application."""
    
    def __init__(self, parent=None, event_bus=None, config=None):
        """Initialize the API Key Manager window."""
        super().__init__(parent)
        
        # Initialize properties
        self.event_bus = event_bus
        self.config = config or {}
        self.redis_nexus = None
        self.api_key_manager = None
        self.api_key_connector = None
        self.current_service = None
        self.api_keys = {}
        
        # Connect to central ThothAI brain system
        self._connect_to_central_brain()
        
        # Initialize UI and components
        self.init_ui()
        self.initialize_components()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Kingdom AI - API Key Manager")
        self.setMinimumSize(1000, 700)
        
        # Set application icon
        self.setWindowIcon(get_icon("key"))
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create left panel (services list)
        self.create_left_panel()
        
        # Create right panel (key details)
        self.create_right_panel()
        
        # Add panels to splitter
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([300, 700])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Apply styles
        self.apply_styles()
    
    def create_toolbar(self):
        """Create the main toolbar with actions and shortcuts."""
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        
        # Add API key action
        self.add_key_action = QAction(get_icon("add"), "Add API Key", self)
        self.add_key_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_N)
        self.add_key_action.setStatusTip("Add a new API key (Ctrl+N)")
        self.add_key_action.triggered.connect(self.add_api_key)
        toolbar.addAction(self.add_key_action)
        
        # Refresh action
        self.refresh_action = QAction(get_icon("refresh"), "Refresh", self)
        self.refresh_action.setShortcut(Qt.Key.Key_F5)
        self.refresh_action.setStatusTip("Refresh API keys (F5)")
        self.refresh_action.triggered.connect(self.refresh_keys)
        toolbar.addAction(self.refresh_action)
        
        toolbar.addSeparator()
        
        # Test connection action
        self.test_connection_action = QAction(get_icon("connection"), "Test Connection", self)
        self.test_connection_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_T)
        self.test_connection_action.setStatusTip("Test connection for selected service (Ctrl+T)")
        self.test_connection_action.triggered.connect(self.test_connection)
        toolbar.addAction(self.test_connection_action)
        
        # Toggle secrets action
        self.toggle_secrets_action = QAction(get_icon("visibility"), "Show Secrets", self)
        self.toggle_secrets_action.setShortcut(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_S)
        self.toggle_secrets_action.setStatusTip("Toggle visibility of secret keys (Ctrl+Shift+S)")
        self.toggle_secrets_action.setCheckable(True)
        self.toggle_secrets_action.toggled.connect(self.toggle_secrets)
        toolbar.addAction(self.toggle_secrets_action)
        
        # Add help action
        self.help_action = QAction(get_icon("help"), "Help", self)
        self.help_action.setShortcut(Qt.Key.Key_F1)
        self.help_action.setStatusTip("Show help (F1)")
        self.help_action.triggered.connect(self.show_help)
        toolbar.addAction(self.help_action)
    
    def create_left_panel(self):
        """Create the left panel with services list."""
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        
        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search services...")
        self.search_edit.textChanged.connect(self.filter_services)
        left_layout.addWidget(self.search_edit)
        
        # Category filter
        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories")
        self.category_combo.addItems(["Exchanges", "AI Services", "Blockchain", "Data Providers", "Other"])
        self.category_combo.currentTextChanged.connect(self.filter_services)
        left_layout.addWidget(self.category_combo)
        
        # Services tree
        self.services_tree = QTreeWidget()
        self.services_tree.setHeaderLabels(["Service", "Status"])
        self.services_tree.setColumnCount(2)
        self.services_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.services_tree.itemSelectionChanged.connect(self.on_service_selected)
        
        # Enable context menu
        self.services_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.services_tree.customContextMenuRequested.connect(self.show_context_menu)
        
        # Set column widths
        self.services_tree.setColumnWidth(0, 200)
        self.services_tree.setColumnWidth(1, 100)
        
        # Enable sorting
        self.services_tree.setSortingEnabled(True)
        self.services_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        
        left_layout.addWidget(self.services_tree)
    
    def create_right_panel(self):
        """Create the right panel with key details."""
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)
        
        # Service info group
        service_group = QGroupBox("Service Details")
        service_layout = QFormLayout(service_group)
        
        self.service_name = QLabel("No service selected")
        self.service_status = QLabel("Status: Not connected")
        self.last_updated = QLabel("Last updated: Never")
        
        service_layout.addRow("Service:", self.service_name)
        service_layout.addRow(self.service_status)
        service_layout.addRow(self.last_updated)
        
        # API Key details group
        key_group = QGroupBox("API Key Details")
        key_layout = QFormLayout(key_group)
        
        self.api_key_edit = QLineEdit()
        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        key_layout.addRow("API Key:", self.api_key_edit)
        key_layout.addRow("API Secret:", self.api_secret_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_api_key)
        
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self.test_connection)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.test_button)
        
        # Add widgets to right layout
        right_layout.addWidget(service_group)
        right_layout.addWidget(key_group)
        right_layout.addLayout(button_layout)
        right_layout.addStretch()
    
    def initialize_components(self):
        """Initialize all components with strict connection requirements."""
        # Show loading state
        self.status_bar.showMessage("Connecting to Redis Quantum Nexus...")
        
        try:
            # Initialize Redis Quantum Nexus with strict requirements
            self.redis_nexus = RedisQuantumNexus(
                host="localhost",
                port=6380,
                password="QuantumNexus2025",
                db=0,
                event_bus=self.event_bus
            )
            
            # Test Redis connection
            if not self.redis_nexus.ping():
                raise ConnectionError("Failed to connect to Redis Quantum Nexus")
                
            self.status_bar.showMessage("Connected to Redis Quantum Nexus. Initializing API Key Manager...")
            
            # Initialize API Key Manager
            self.api_key_manager = APIKeyManager(
                event_bus=self.event_bus,
                config=self.config,
                redis_nexus=self.redis_nexus
            )
            
            # Initialize API Key Connector
            self.api_key_connector = APIKeyManagerConnector(
                event_bus=self.event_bus,
                component_name="APIKeyManagerQt",
                config=self.config
            )
            
            # Load API keys
            self.load_api_keys()
            
            self.status_bar.showMessage("API Key Manager ready", 3000)
            
        except Exception as e:
            error_msg = f"Failed to initialize API Key Manager: {str(e)}"
            self.logger.critical(error_msg, exc_info=True)
            
            # Show detailed error message
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle("Critical Error")
            error_dialog.setText("Failed to initialize API Key Manager")
            error_dialog.setInformativeText(
                f"{str(e)}\n\n"
                "Please ensure Redis Quantum Nexus is running on localhost:6380\n"
                "with the correct password. The application will now exit."
            )
            error_dialog.setDetailedText(traceback.format_exc())
            error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_dialog.exec()
            
            # DO NOT HALT - system must stay running
            logger.critical("⚠️ API Key Manager will operate in degraded mode")
    
    def load_api_keys(self):
        """Load API keys from the key manager."""
        try:
            if not self.api_key_manager:
                raise RuntimeError("API Key Manager not initialized")
            
            # Clear existing items
            self.services_tree.clear()
            self.api_keys = {}
            
            # Get all API keys
            self.api_keys = self.api_key_manager.get_all_keys()
            
            # Add services to the tree
            for service_name, key_data in self.api_keys.items():
                item = QTreeWidgetItem([service_name, "Connected" if key_data.get("connected", False) else "Disconnected"])
                item.setData(0, Qt.ItemDataRole.UserRole, service_name)
                self.services_tree.addTopLevelItem(item)
            
            # Update status bar
            self.status_bar.showMessage(f"Loaded {len(self.api_keys)} API keys", 3000)
            
        except Exception as e:
            self.show_error("Error", f"Failed to load API keys: {str(e)}")
    
    def on_service_selected(self):
        """Handle service selection."""
        selected = self.services_tree.selectedItems()
        if not selected:
            return
        
        service_item = selected[0]
        service_name = service_item.data(0, Qt.ItemDataRole.UserRole)
        
        if service_name in self.api_keys:
            self.current_service = service_name
            self.update_service_details()
    
    def update_service_details(self):
        """Update the service details panel."""
        if not self.current_service or self.current_service not in self.api_keys:
            return
        
        key_data = self.api_keys[self.current_service]
        
        # Update service info
        self.service_name.setText(self.current_service)
        self.api_key_edit.setText(key_data.get("api_key", ""))
        self.api_secret_edit.setText(key_data.get("api_secret", ""))
        
        # Update status
        is_connected = key_data.get("connected", False)
        status_text = "Status: Connected" if is_connected else "Status: Disconnected"
        self.service_status.setText(status_text)
        
        # Update last updated
        last_updated = key_data.get("last_updated", "Never")
        self.last_updated.setText(f"Last updated: {last_updated}")
    
    def add_api_key(self):
        """Add a new API key."""
        service_name, ok = QInputDialog.getText(
            self, "Add API Key", "Enter service name:"
        )
        
        if ok and service_name:
            # Add new service
            self.current_service = service_name
            self.api_keys[service_name] = {
                "api_key": "",
                "api_secret": "",
                "connected": False,
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Add to tree
            item = QTreeWidgetItem([service_name, "Disconnected"])
            item.setData(0, Qt.ItemDataRole.UserRole, service_name)
            self.services_tree.addTopLevelItem(item)
            
            # Select the new item
            self.services_tree.setCurrentItem(item)
    
    def save_api_key(self):
        """Save the current API key."""
        if not self.current_service:
            self.show_warning("No service selected")
            return
        
        try:
            # Update key data
            self.api_keys[self.current_service].update({
                "api_key": self.api_key_edit.text(),
                "api_secret": self.api_secret_edit.text(),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Save to Redis
            if self.api_key_manager:
                self.api_key_manager.set_key(
                    self.current_service,
                    self.api_keys[self.current_service]
                )
            
            # Update status
            self.status_bar.showMessage(f"Saved API key for {self.current_service}", 3000)
            
        except Exception as e:
            self.show_error("Error", f"Failed to save API key: {str(e)}")
    
    def test_connection(self):
        """Test the API key connection."""
        if not self.current_service:
            self.show_warning("No service selected")
            return
        
        try:
            # Update key data first
            self.save_api_key()
            
            # Test connection
            if self.api_key_connector:
                is_connected = self.api_key_connector.test_connection(
                    self.current_service,
                    self.api_keys[self.current_service]
                )
                
                # Update status
                status = "connected" if is_connected else "disconnected"
                self.api_keys[self.current_service]["connected"] = is_connected
                self.service_status.setText(f"Status: {'Connected' if is_connected else 'Disconnected'}")
                
                # Update tree item
                for i in range(self.services_tree.topLevelItemCount()):
                    item = self.services_tree.topLevelItem(i)
                    if item.data(0, Qt.ItemDataRole.UserRole) == self.current_service:
                        item.setText(1, "Connected" if is_connected else "Disconnected")
                        break
                
                # Show result
                status_text = "successfully connected" if is_connected else "failed to connect"
                self.status_bar.showMessage(
                    f"Test connection {status_text} for {self.current_service}",
                    5000
                )
                
        except Exception as e:
            self.show_error("Connection Error", f"Connection test failed: {str(e)}")
    
    def filter_services(self):
        """Filter services based on search text and category."""
        search_text = self.search_edit.text().lower()
        category = self.category_combo.currentText()
        
        for i in range(self.services_tree.topLevelItemCount()):
            item = self.services_tree.topLevelItem(i)
            service_name = item.data(0, Qt.ItemDataRole.UserRole)
            
            # Filter by search text and category
            show_item = (
                (search_text in service_name.lower()) and
                (category == "All Categories" or 
                 (service_name in self.api_keys and 
                  self.api_keys[service_name].get("category", "") == category))
            )
            
            item.setHidden(not show_item)
    
    def show_context_menu(self, position):
        """Show context menu for service items."""
        item = self.services_tree.itemAt(position)
        if not item:
            return
            
        menu = QMenu()
        
        # Add actions
        delete_action = QAction("Delete Service", self)
        delete_action.triggered.connect(lambda: self.delete_service(item))
        menu.addAction(delete_action)
        
        # Show menu
        menu.exec(self.services_tree.viewport().mapToGlobal(position))
    
    def delete_service(self, item):
        """Delete the selected service."""
        service_name = item.data(0, Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, 
            "Confirm Delete", 
            f"Are you sure you want to delete the service '{service_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Delete from Redis
                if self.api_key_manager:
                    self.api_key_manager.delete_key(service_name)
                
                # Remove from UI
                self.services_tree.takeTopLevelItem(self.services_tree.indexOfTopLevelItem(item))
                
                # Clear selection if deleted service was selected
                if self.current_service == service_name:
                    self.current_service = None
                    self.clear_service_details()
                
                self.status_bar.showMessage(f"Deleted service: {service_name}", 3000)
                
            except Exception as e:
                self.show_error("Error", f"Failed to delete service: {str(e)}")
    
    def clear_service_details(self):
        """Clear the service details panel."""
        self.service_name.setText("No service selected")
        self.service_status.setText("Status: Not connected")
        self.last_updated.setText("Last updated: Never")
        self.api_key_edit.clear()
        self.api_secret_edit.clear()
    
    def toggle_secrets(self, show):
        """Toggle visibility of secret keys."""
        self.api_secret_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        )
        self.toggle_secrets_action.setText("Hide Secrets" if show else "Show Secrets")
    
    def refresh_keys(self):
        """Refresh the list of API keys."""
        self.load_api_keys()
    
    def show_error(self, title, message, details=None):
        """Show an error message with optional details."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle(title)
        msg.setText(message)
        
        if details:
            msg.setDetailedText(details)
            
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def show_warning(self, message, title="Warning"):
        """Show a warning message."""
        QMessageBox.warning(self, title, message)
    
    def _connect_to_central_brain(self):
        """Connect to ThothAI central brain system."""
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).replace('gui/qt_frames', ''))
            
            # FIXED: Using event bus instead of direct import
            # from main import get_thoth_ai
            
            # Connect to central ThothAI brain via event bus
            self._central_thoth = None  # Will use event bus for Thoth AI communication
            if self._central_thoth:
                self.logger.info("✅ API Key Manager Tab connected to ThothAI central brain")
                
                # Register API key events with central brain
                if hasattr(self._central_thoth, 'register_component'):
                    self._central_thoth.register_component('api_key_manager_tab')
                    
            else:
                # SOTA 2026 FIX: ThothAI is optional for API key management - use debug
                self.logger.debug("ℹ️ Central ThothAI not available for API key management (optional)")
                
        except Exception as e:
            # SOTA 2026 FIX: Expected fallback scenario - use debug not error
            self.logger.debug(f"ℹ️ Error connecting to central ThothAI: {e} (API keys will work without it)")
            self._central_thoth = None
        
    def show_info(self, message, title="Information"):
        """Show an information message."""
        QMessageBox.information(self, title, message)
        
    def show_help(self):
        """Show help information."""
        help_text = """
        <h2>API Key Manager Help</h2>
        
        <h3>Adding API Keys</h3>
        <p>1. Click <b>Add API Key</b> or press <b>Ctrl+N</b></p>
        <p>2. Enter the service name and click OK</p>
        <p>3. Enter the API key and secret in the right panel</p>
        <p>4. Click <b>Save</b> to store the key</p>
        
        <h3>Testing Connections</h3>
        <p>1. Select a service from the list</p>
        <p>2. Click <b>Test Connection</b> or press <b>Ctrl+T</b></p>
        
        <h3>Keyboard Shortcuts</h3>
        <ul>
            <li><b>Ctrl+N</b>: Add new API key</li>
            <li><b>F5</b>: Refresh keys</li>
            <li><b>Ctrl+T</b>: Test connection</li>
            <li><b>Ctrl+Shift+S</b>: Toggle secret visibility</li>
            <li><b>F1</b>: Show this help</li>
        </ul>
        """
        
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("API Key Manager Help")
        help_dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(help_dialog)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(help_text)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(help_dialog.accept)
        
        layout.addWidget(text_edit)
        layout.addWidget(button_box)
        
        help_dialog.exec()
    
    def apply_styles(self):
        """Apply styles to the application."""
        self.setStyleSheet(get_style_sheet("api_key_manager"))


def main():
    """Main entry point for the API Key Manager."""
    app = QApplication(sys.argv)
    
    # Set application style and palette
    app.setStyle("Fusion")
    
    # Create and show the main window
    window = APIKeyManagerWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
