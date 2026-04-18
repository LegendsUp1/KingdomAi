"""
Kingdom AI API Key Tab Initialization Module
This module provides the initialization method for the API Key tab in the Kingdom AI GUI.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import uuid
import os
from datetime import datetime

logger = logging.getLogger("KingdomAI.TabManager")

async def _init_apikey_tab(self, tab_frame):
    """Initialize the API key management tab with secure storage and usage tracking.
    
    This method follows the 8-step lifecycle:
    1. Retrieval - Locate data sources
    2. Fetching - Active data retrieval
    3. Binding - Connect data to GUI elements
    4. Formatting - Present data in readable format
    5. Event Handling - Respond to user/system events
    6. Concurrency - Prevent UI blocking
    7. Error Handling - Graceful error management
    8. Debugging - Tools for diagnostics
    
    Args:
        tab_frame: The tab frame to populate
    """
    try:
        # STEP 1: RETRIEVAL - Identify data sources
        data_sources = {
            "api_keys": "secure_key_storage",
            "usage_logs": "api_usage_database",
            "services": "api_services_registry"
        }
        logger.info(f"API Key tab initializing with data sources: {list(data_sources.keys())}")
        
        # STEP 2: FETCHING - Set up infrastructure for data fetching
        # Will be triggered via event bus after UI elements are created
        
        # Import PyQt6 components (no Tkinter fallback as per requirements)
        from PyQt6.QtWidgets import (QLabel, QVBoxLayout, QHBoxLayout, QPushButton, 
                                   QFrame, QTableWidget, QTableWidgetItem, QLineEdit,
                                   QDialog, QFormLayout, QComboBox, QMessageBox)
        from PyQt6.QtCore import Qt, QSize
        
        # Main layout
        layout = tab_frame.layout()
        
        # Header with Title and Status
        header_widget = QFrame()
        header_layout = QHBoxLayout(header_widget)
        
        # Title
        title_label = QLabel("API Key Management")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label, 1)
        
        # Status
        self.apikey_status = QLabel("Status: Initializing...")
        header_layout.addWidget(self.apikey_status)
        
        layout.addWidget(header_widget)
        
        # API Keys Table
        table_frame = QFrame()
        table_layout = QVBoxLayout(table_frame)
        
        table_header = QLabel("Stored API Keys")
        table_header.setStyleSheet("font-weight: bold;")
        table_layout.addWidget(table_header)
        
        self.apikey_table = QTableWidget(0, 4)  # rows will be added dynamically, 4 columns
        self.apikey_table.setHorizontalHeaderLabels(["Service", "Key (masked)", "Added Date", "Usage"])
        self.apikey_table.horizontalHeader().setStretchLastSection(True)
        table_layout.addWidget(self.apikey_table)
        
        layout.addWidget(table_frame)
        
        # Search section
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        
        search_layout.addWidget(QLabel("Search Service:"))
        
        self.apikey_search = QLineEdit()
        self.apikey_search.setPlaceholderText("Enter service name...")
        self.apikey_search.textChanged.connect(self._filter_api_keys)
        search_layout.addWidget(self.apikey_search)
        
        layout.addWidget(search_frame)
        
        # Actions Section
        actions_frame = QFrame()
        actions_layout = QHBoxLayout(actions_frame)
        
        # STEP 5: EVENT HANDLING - Connect buttons to actions
        add_key_btn = QPushButton("Add API Key")
        add_key_btn.clicked.connect(self.add_api_key)
        actions_layout.addWidget(add_key_btn)
        
        edit_key_btn = QPushButton("Edit Selected")
        edit_key_btn.clicked.connect(self.edit_api_key)
        actions_layout.addWidget(edit_key_btn)
        
        remove_key_btn = QPushButton("Remove Selected")
        remove_key_btn.clicked.connect(self.remove_api_key)
        actions_layout.addWidget(remove_key_btn)
        
        test_key_btn = QPushButton("Test Selected")
        test_key_btn.clicked.connect(self.test_api_key)
        actions_layout.addWidget(test_key_btn)
        
        layout.addWidget(actions_frame)
        
        # Usage Statistics Section
        usage_frame = QFrame()
        usage_frame.setFrameShape(QFrame.Shape.StyledPanel)
        usage_layout = QVBoxLayout(usage_frame)
        
        usage_header = QLabel("Usage Statistics")
        usage_header.setStyleSheet("font-weight: bold;")
        usage_layout.addWidget(usage_header)
        
        self.usage_stats = QLabel("No API usage data available")
        usage_layout.addWidget(self.usage_stats)
        
        layout.addWidget(usage_frame)
        
        # STEP 3: BINDING - Register widgets for data updates
        if hasattr(self, 'widget_registry'):
            await self.widget_registry.register_widget("apikey_status", self.apikey_status)
            await self.widget_registry.register_widget("apikey_table", self.apikey_table)
            await self.widget_registry.register_widget("usage_stats", self.usage_stats)
            
        
        # STEP 6: CONCURRENCY - Fetch initial data asynchronously
        if self.event_bus:
            await self.request_apikey_data()
            
        # STEP 7: ERROR HANDLING - Done in the try/except block
        
        # STEP 8: DEBUGGING - Log completion
        logger.info("API Key tab initialized with secure storage")
        
    except Exception as e:
        # Error handling
        logger.error(f"Error initializing API key tab: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        
        # Display error in UI if possible
        try:
            if hasattr(self, 'apikey_status'):
                self.apikey_status.setText("Error: Failed to initialize API key tab")
                self.apikey_status.setStyleSheet("color: red;")
        except Exception:
            # Last resort if even error display fails
            pass
            
    def _filter_api_keys(self):
        """Filter API keys based on search criteria."""
        try:
            search_text = ""
            if hasattr(self, 'apikey_search'):
                search_text = self.apikey_search.text().lower()
                
            # Filter the QTableWidget based on search text
            for row in range(self.apikey_table.rowCount()):
                service_item = self.apikey_table.item(row, 0)
                if service_item and search_text in service_item.text().lower():
                    self.apikey_table.setRowHidden(row, False)
                else:
                    self.apikey_table.setRowHidden(row, True)
                    
            logger.debug(f"Filtering API keys with: {search_text}")
            
        except Exception as e:
            logger.error(f"Error filtering API keys: {e}")
            
    def _mask_api_key(self, key):
        """Mask an API key for display, showing only the first and last few characters."""
        if not key or len(key) < 8:
            return "****"
            
        visible_chars = 4  # Show first and last N characters
        masked_length = len(key) - (visible_chars * 2)
        
        if masked_length <= 0:
            return key[:2] + "**" + key[-2:]
            
        return key[:visible_chars] + "*" * masked_length + key[-visible_chars:]

    # Handler for API key data updates
    async def update_apikey_data(self, data: Dict[str, Any]) -> None:
        """Update API key management tab with stored keys and usage statistics.
        
        Args:
            data: Dictionary containing API key data from the event bus
        """
        try:
            logger.info(f"Received API key data update: {data}")
            if not data or not isinstance(data, dict):
                logger.warning("Received invalid API key data")
                return
                
            # Update API key table if available
            if 'api_keys' in data and hasattr(self, 'apikey_table'):
                api_keys = data.get('api_keys', [])
                
                if self.using_pyqt:
                    # Clear existing rows
                    self.apikey_table.setRowCount(0)
                    
                    # Add new rows
                    for i, key_data in enumerate(api_keys):
                        self.apikey_table.insertRow(i)
                        self.apikey_table.setItem(i, 0, QTableWidgetItem(key_data.get('service', '')))
                        self.apikey_table.setItem(i, 1, QTableWidgetItem(self._mask_api_key(key_data.get('key', ''))))
                        self.apikey_table.setItem(i, 2, QTableWidgetItem(key_data.get('date', '')))
                        self.apikey_table.setItem(i, 3, QTableWidgetItem(str(key_data.get('usage', 0))))
                else:
                    # Clear existing items
                    for item in self.apikey_table.get_children():
                        self.apikey_table.delete(item)
                        
                    # Add new items
                    for key_data in api_keys:
                        service = key_data.get('service', '')
                        masked_key = self._mask_api_key(key_data.get('key', ''))
                        date = key_data.get('date', '')
                        usage = str(key_data.get('usage', 0))
                        
                        self.apikey_table.insert("", "end", values=(service, masked_key, date, usage))
                        
            # Update usage statistics if available
            if 'usage_stats' in data and hasattr(self, 'usage_stats'):
                stats = data.get('usage_stats', {})
                
                if stats:
                    # Format usage stats
                    stats_text = "API Usage Statistics:\n"
                    for service, count in stats.items():
                        stats_text += f"• {service}: {count} calls\n"
                        
                    if self.using_pyqt:
                        self.usage_stats.setText(stats_text)
                    else:
                        self.usage_stats.config(text=stats_text)
                        
            # Update status if available
            if 'status' in data and hasattr(self, 'apikey_status'):
                status = data.get('status', 'Unknown')
                
                if self.using_pyqt:
                    self.apikey_status.setText(f"Status: {status}")
                else:
                    self.apikey_status.config(text=f"Status: {status}")
                    
        except Exception as e:
            logger.error(f"Error updating API key data: {e}")

# Add alias for backward compatibility with code that expects _init_api_keys_tab
_init_api_keys_tab = _init_apikey_tab
