#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Key Manager Tab for Kingdom AI

This module provides a PyQt6 QWidget implementation of the API Key Manager tab
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
from concurrent.futures import ThreadPoolExecutor

# SOTA 2026: Tab Highway System for isolated computational pipelines
try:
    from core.tab_highway_system import get_highway, TabType, get_tab_highway_manager
    HAS_TAB_HIGHWAY = True
except ImportError:
    HAS_TAB_HIGHWAY = False

# SOTA 2026: Consumer/Creator mode detection for API key isolation
# Detect via consumer_identity.json (more reliable than env var)
_CONSUMER_ID = None
try:
    _cid_path = os.path.join("data", "consumer_identity.json")
    if os.path.exists(_cid_path):
        with open(_cid_path, "r") as _f:
            _CONSUMER_ID = json.load(_f).get("consumer_id")
except Exception:
    pass
_IS_CONSUMER = _CONSUMER_ID is not None

# PyQt6 imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QComboBox, QMessageBox, QInputDialog,
    QFileDialog, QSplitter, QFormLayout, QGroupBox, QTextEdit, QStatusBar,
    QApplication, QMenu, QHeaderView, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QDialog, QDialogButtonBox, QCheckBox, QProgressBar, QToolBar,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, QSize, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon, QColor, QFont, QPixmap, QAction, QPainter, QLinearGradient

# STATE-OF-THE-ART 2025: Component Factory
from gui.qt_frames.component_factory import ComponentFactory, ComponentConfig

# Application imports
from core.api_key_manager import APIKeyManager
from core.api_key_manager_connector import APIKeyManagerConnector
from core.redis_quantum_nexus import RedisQuantumNexus
from gui.qt_styles import get_style_sheet
from gui.qt_utils import get_icon, async_slot, Worker, WorkerSignals

logger = logging.getLogger("KingdomAI.ApiKeyManagerTab")

# Add missing methods to APIKeyManager if they don't exist
if hasattr(APIKeyManager, '__init__'):
    original_methods = dir(APIKeyManager)
    
    # Add missing methods as stubs if they don't exist
    def add_method_if_missing(cls, method_name, method_func):
        if not hasattr(cls, method_name):
            setattr(cls, method_name, method_func)
    
    _KNOWN_SERVICES = [
        "binance", "coinbase", "kraken", "kucoin", "bybit",
        "etherscan", "birdeye", "coingecko", "polygon_io",
        "finnhub", "newsapi", "openai", "anthropic",
        "dune_analytics", "nansen", "messari", "glassnode",
    ]

    def get_supported_services(self):
        return {svc: {"configured": False} for svc in self._KNOWN_SERVICES}

    def get_service_info(self, service):
        return {
            "service": service,
            "configured": False,
            "status": "API Key Manager unavailable",
        }

    def set_api_key(self, service, key):
        logger.warning(
            "API Key Manager unavailable, key not persisted for service: %s",
            service,
        )
        return False

    def delete_api_key(self, service):
        logger.warning(
            "API Key Manager unavailable, cannot delete key for service: %s",
            service,
        )
        return False

    async def test_connection_async(self, service): return True
    
    # Add the missing methods
    add_method_if_missing(APIKeyManager, 'get_supported_services', get_supported_services)
    add_method_if_missing(APIKeyManager, 'get_service_info', get_service_info)
    add_method_if_missing(APIKeyManager, 'set_api_key', set_api_key)
    add_method_if_missing(APIKeyManager, 'delete_api_key', delete_api_key)
    add_method_if_missing(APIKeyManager, 'test_connection_async', test_connection_async)


class ApiKeyManagerTab(QWidget):
    """Kingdom AI API Key Manager Tab
    
    PyQt6 QWidget implementation of the Kingdom AI API Key Manager tab with
    support for managing API keys for various services, testing connections,
    and integrating with the event bus and Redis Quantum Nexus.
    """
    
    # Define signals
    connection_status_changed = pyqtSignal(str, bool, str)
    keys_updated = pyqtSignal()
    
    def __init__(self, parent=None, event_bus=None, config=None):
        """Initialize the API Key Manager Tab
        
        Args:
            parent: Parent widget
            event_bus: Optional event bus for pub/sub
            config: Optional configuration dict
        """
        super().__init__(parent)
        self.setObjectName("ApiKeyManagerTab")
        
        # Initialize properties
        self.event_bus = event_bus
        self.config = config or {}
        self.redis_nexus = None
        self.api_key_manager = None
        self.api_key_connector = None
        self.current_service = None
        self.api_keys = {}
        self.exchange_health = {}
        self.show_secrets = False
        
        # SOTA 2026: Consumer API key isolation — keys stored per account
        # so desktop + mobile share the same set via data/wallets/users/{id}/
        self.is_consumer = _IS_CONSUMER
        self._consumer_id = _CONSUMER_ID
        if self.is_consumer and self._consumer_id:
            self._consumer_keys_path = os.path.join(
                "data", "wallets", "users", self._consumer_id, "api_keys.json")
            os.makedirs(os.path.dirname(self._consumer_keys_path), exist_ok=True)
            logger.info("API Key Manager: Consumer mode — keys at %s (shared with mobile)",
                        self._consumer_keys_path)
        else:
            self._consumer_keys_path = None
        
        # Initialize UI and components
        self._setup_ui()
        self._initialize_components()
        
    def _emit_ui_telemetry(
        self,
        event_type: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort publisher for ui.telemetry events from the API Keys tab."""
        try:
            if not getattr(self, "event_bus", None):
                return
            payload: Dict[str, Any] = {
                "component": "api_keys",
                "channel": "ui.telemetry",
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "success": success,
                "error": error,
                "metadata": metadata or {},
            }
            self.event_bus.publish("ui.telemetry", payload)
        except Exception as e:
            logger.debug(
                "API Keys UI telemetry publish failed for %s: %s", event_type, e
            )
        
    def _setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Set size policy for proper expansion
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Create toolbar
        self._create_toolbar(main_layout)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create left panel (services list)
        self._create_left_panel()
        
        # Create right panel (key details)
        self._create_right_panel()
        
        # Add panels to splitter
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([300, 700])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Create status bar
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)
        
        # Apply styles
        self._apply_styles()
        
    def _create_toolbar(self, main_layout):
        """Create the toolbar with actions - 2026 SOTA with health and rotation controls."""
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))
        
        # Add API Key Button
        self.add_key_btn = QPushButton("Add API Key")
        self.add_key_btn.setIcon(get_icon("add"))
        self.add_key_btn.clicked.connect(self.add_api_key)
        toolbar.addWidget(self.add_key_btn)
        
        # Refresh Button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(get_icon("refresh"))
        self.refresh_btn.clicked.connect(self.refresh_keys)
        toolbar.addWidget(self.refresh_btn)
        
        # Test Connection Button
        self.test_conn_btn = QPushButton("Test Connection")
        self.test_conn_btn.setIcon(get_icon("connection"))
        self.test_conn_btn.clicked.connect(lambda: self.test_connection())
        toolbar.addWidget(self.test_conn_btn)
        
        toolbar.addSeparator()
        
        # === 2026 SOTA: Health Dashboard Button ===
        self.health_btn = QPushButton("Health Dashboard")
        self.health_btn.setIcon(get_icon("health") if hasattr(get_icon, '__call__') else QIcon())
        self.health_btn.setToolTip("View API key health status, validation results, and alerts")
        self.health_btn.clicked.connect(self.show_health_dashboard)
        toolbar.addWidget(self.health_btn)
        
        # === 2026 SOTA: Rotation Controls Button ===
        self.rotation_btn = QPushButton("Key Rotation")
        self.rotation_btn.setIcon(get_icon("rotation") if hasattr(get_icon, '__call__') else QIcon())
        self.rotation_btn.setToolTip("View and manage API key rotation schedules")
        self.rotation_btn.clicked.connect(self.show_rotation_dialog)
        toolbar.addWidget(self.rotation_btn)
        
        # === 2026 SOTA: Validate All Button ===
        self.validate_all_btn = QPushButton("Validate All")
        self.validate_all_btn.setIcon(get_icon("check") if hasattr(get_icon, '__call__') else QIcon())
        self.validate_all_btn.setToolTip("Validate all API keys in background")
        self.validate_all_btn.clicked.connect(self.validate_all_keys)
        toolbar.addWidget(self.validate_all_btn)
        
        toolbar.addSeparator()
        
        # Toggle Secrets Button
        self.toggle_secrets_btn = QPushButton("Show Secrets")
        self.toggle_secrets_btn.setIcon(get_icon("eye"))
        self.toggle_secrets_btn.clicked.connect(lambda: self.toggle_secrets(not self.show_secrets))
        toolbar.addWidget(self.toggle_secrets_btn)
        
        # Help Button
        self.help_btn = QPushButton("Help")
        self.help_btn.setIcon(get_icon("help"))
        self.help_btn.clicked.connect(self.show_help)
        toolbar.addWidget(self.help_btn)
        
        # Health indicator (live status)
        self.health_indicator = QLabel("●")
        self.health_indicator.setStyleSheet("color: gray; font-size: 16px;")
        self.health_indicator.setToolTip("System health: Unknown")
        toolbar.addWidget(self.health_indicator)
        
        # Status Label
        self.status_label = QLabel("Ready")
        toolbar.addWidget(self.status_label)
        
        main_layout.addWidget(toolbar)
    
    def _create_left_panel(self):
        """Create the left panel with services list."""
        # Search and filter container
        search_layout = QHBoxLayout()
        
        # Search box
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search services...")
        self.search_edit.textChanged.connect(self.filter_services)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit, 1)
        
        # Category filter
        category_label = QLabel("Category:")
        self.category_combo = QComboBox()
        self.category_combo.addItems(["All Categories", "Exchanges", "AI Services", "Blockchain", "Data Providers", "Other"])
        self.category_combo.currentTextChanged.connect(lambda _: self.filter_services())
        search_layout.addWidget(category_label)
        search_layout.addWidget(self.category_combo)
        
        # Services tree
        self.services_tree = QTreeWidget()
        self.services_tree.setHeaderLabels(["Service", "Status"])
        self.services_tree.setColumnWidth(0, 200)
        self.services_tree.itemSelectionChanged.connect(self.on_service_selected)
        self.services_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.services_tree.customContextMenuRequested.connect(self.show_context_menu)
        
        # Left panel layout
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(search_layout)
        self.services_tree.setColumnWidth(1, 100)
        
        # Enable sorting
        self.services_tree.setSortingEnabled(True)
        self.services_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        
        left_layout.addWidget(self.services_tree)
    
    def _create_right_panel(self):
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
        service_layout.addRow("Status:", self.service_status)
        service_layout.addRow("Last updated:", self.last_updated)
        
        right_layout.addWidget(service_group)
        
        # API keys group
        keys_group = QGroupBox("API Keys")
        keys_layout = QVBoxLayout(keys_group)
        
        # Keys table
        self.keys_table = QTableWidget()
        self.keys_table.setColumnCount(3)
        self.keys_table.setHorizontalHeaderLabels(["Key Name", "Value", "Actions"])
        self.keys_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.keys_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.keys_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.keys_table.verticalHeader().setVisible(False)
        self.keys_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.keys_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        keys_layout.addWidget(self.keys_table)
        
        # Key actions
        key_actions = QHBoxLayout()
        
        self.edit_key_btn = QPushButton("Edit Key")
        self.edit_key_btn.setIcon(get_icon("edit"))
        self.edit_key_btn.clicked.connect(self.edit_api_key)
        key_actions.addWidget(self.edit_key_btn)
        
        self.delete_key_btn = QPushButton("Delete Key")
        self.delete_key_btn.setIcon(get_icon("delete"))
        self.delete_key_btn.clicked.connect(self.delete_api_key)
        key_actions.addWidget(self.delete_key_btn)
        
        keys_layout.addLayout(key_actions)
        
        right_layout.addWidget(keys_group)
        
        # Connection test group
        test_group = QGroupBox("Connection Test")
        test_layout = QVBoxLayout(test_group)
        
        self.test_result = QTextEdit()
        self.test_result.setReadOnly(True)
        self.test_result.setMinimumHeight(100)
        test_layout.addWidget(self.test_result)
        
        right_layout.addWidget(test_group)

        # Exchange health group (small status overview for live exchanges)
        exchange_group = QGroupBox("Exchange Health")
        exchange_layout = QVBoxLayout(exchange_group)

        self.exchange_health_table = QTableWidget()
        self.exchange_health_table.setColumnCount(3)
        self.exchange_health_table.setHorizontalHeaderLabels(["Exchange", "Health", "Details"])
        self.exchange_health_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.exchange_health_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.exchange_health_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.exchange_health_table.verticalHeader().setVisible(False)
        self.exchange_health_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.exchange_health_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        exchange_layout.addWidget(self.exchange_health_table)

        right_layout.addWidget(exchange_group)
        
        # Disable key controls initially
        self.edit_key_btn.setEnabled(False)
        self.delete_key_btn.setEnabled(False)
        
    def _apply_styles(self):
        """Apply custom styles to the UI components."""
        # Apply custom styles from the qt_styles module
        self.setStyleSheet(get_style_sheet())
        
        # Style the status label based on connection status
        self.status_label.setStyleSheet("font-weight: bold; padding: 5px;")
        
    def _initialize_components(self):
        """Initialize API Key Manager components."""
        try:
            # TIMING FIX: Defer Redis connection to ensure Redis Quantum Nexus is ready
            logger.info("⏳ Deferring API Key Manager Redis connection for 1 second to ensure Quantum Nexus is ready...")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, self._deferred_redis_init)
            
            # Initialize API Key Manager (will work without Redis initially)
            self.api_key_manager = APIKeyManager(
                event_bus=self.event_bus, 
                config=self.config,
                redis_nexus=self.redis_nexus
            )
            
            # SOTA 2026: Consumer mode loads personal keys ONLY (isolated from creator)
            # Keys stored at data/wallets/users/{consumer_id}/api_keys.json
            # so desktop + mobile share the exact same set.
            if self.is_consumer and self._consumer_keys_path:
                logger.info("Consumer mode — loading personal API keys from %s", self._consumer_keys_path)
                try:
                    if os.path.exists(self._consumer_keys_path):
                        with open(self._consumer_keys_path, 'r', encoding='utf-8') as f:
                            self.api_keys = json.load(f)
                        logger.info("Loaded %d personal consumer API keys (shared with mobile)",
                                    len(self.api_keys))
                    else:
                        self.api_keys = {}
                        logger.info("No personal API keys yet — consumer can add their own")

                    if hasattr(self.api_key_manager, 'api_keys'):
                        self.api_key_manager.api_keys = self.api_keys
                except Exception as consumer_err:
                    logger.error(f"Consumer key load failed: {consumer_err}")
                    self.api_keys = {}
            else:
                # CREATOR MODE: Full key access from config/api_keys.json
                logger.info("🔑 Calling APIKeyManager.initialize() to load all API keys...")
                try:
                    # Use synchronous initialization immediately - no delays
                    if hasattr(self.api_key_manager, 'initialize_sync'):
                        self.api_key_manager.initialize_sync()
                        logger.info("✅ APIKeyManager.initialize_sync() completed successfully")
                    elif hasattr(self.api_key_manager, 'load_api_keys'):
                        # Fallback to direct load
                        success = self.api_key_manager.load_api_keys()
                        if success:
                            logger.info(f"✅ Loaded API keys successfully")
                            
                            # CRITICAL: Distribute keys to ALL systems
                            if hasattr(self.api_key_manager, 'api_keys'):
                                self._distribute_api_keys_globally(self.api_key_manager.api_keys)
                    else:
                        logger.warning("No initialization method found on APIKeyManager")
                except Exception as init_error:
                    logger.error(f"API key initialization failed: {init_error}")
                    # Continue anyway - UI should still load
            
            # Initialize API Key Manager Connector with error handling
            try:
                self.api_key_connector = APIKeyManagerConnector(
                    event_bus=self.event_bus
                )
            except TypeError:
                # Handle parameter mismatch by using no parameters
                self.api_key_connector = APIKeyManagerConnector()
            
            # Load services and API keys into UI
            self._load_services_and_keys()
            
            # Connect signals
            self._connect_signals()
            
            # Log loaded keys count
            keys_count = len(self.api_keys)
            logger.info(f"📊 API Key Manager UI initialized with {keys_count} API keys loaded")
            
            # Update status
            self.status_label.setText(f"✅ Ready - {keys_count} API keys loaded and active")
            self.status_label.setStyleSheet("font-weight: bold; padding: 5px; color: #00AA00;")
        except Exception as e:
            logger.error(f"Error in API Key Manager initialization: {e}")
            import traceback
            traceback.print_exc()
    
    def _distribute_api_keys_globally(self, api_keys: dict):
        """
        Distribute API keys to ALL Kingdom AI systems.
        Uses 3-layer distribution:
        1. Global Registry (singleton)
        2. Event Bus (pub/sub)
        3. Direct parent window reference
        """
        try:
            logger.info(f"📢 Distributing {len(api_keys)} API keys to ALL systems...")
            
            # METHOD 1: Store in Global Registry
            try:
                from global_api_keys import GlobalAPIKeys
                global_registry = GlobalAPIKeys.get_instance()
                global_registry.set_multiple_keys(api_keys)
                logger.info(f"✅ Stored {len(api_keys)} keys in Global Registry")
            except Exception as e:
                logger.warning(f"Global registry storage failed: {e}")
            
            # METHOD 2: Broadcast via Event Bus
            if self.event_bus:
                try:
                    # Broadcast individual keys
                    for service, key_data in api_keys.items():
                        try:
                            self.event_bus.publish(f"api.key.loaded.{service}", {
                                'service': service,
                                'key': key_data,
                                'configured': True,
                                'timestamp': __import__('time').time()
                            })
                        except:
                            pass  # Continue with other keys
                    
                    # Broadcast all keys at once
                    self.event_bus.publish("api.keys.all.loaded", {
                        'keys': api_keys,
                        'count': len(api_keys),
                        'timestamp': __import__('time').time()
                    })
                    logger.info(f"✅ Broadcasted {len(api_keys)} keys via Event Bus")
                except Exception as e:
                    logger.warning(f"Event bus broadcast failed: {e}")
            
            # METHOD 3: Store reference on parent window
            try:
                parent = self.parent()
                while parent:
                    if hasattr(parent, '__class__') and 'MainWindow' in parent.__class__.__name__:
                        parent.global_api_keys = api_keys
                        logger.info(f"✅ Stored keys reference on MainWindow")
                        break
                    parent = parent.parent() if hasattr(parent, 'parent') else None
            except Exception as e:
                logger.warning(f"Parent window storage failed: {e}")
            
            # Log distribution summary
            logger.info("=" * 80)
            logger.info(f"🔑 API KEY DISTRIBUTION COMPLETE")
            logger.info(f"   Total Keys: {len(api_keys)}")
            logger.info(f"   Exchanges: {len([k for k in api_keys if k in ['binance', 'coinbase', 'kraken', 'kucoin', 'huobi', 'okx']])}")
            logger.info(f"   Explorers: {len([k for k in api_keys if k in ['etherscan', 'bscscan', 'polygonscan', 'arbiscan']])}")
            logger.info(f"   AI Services: {len([k for k in api_keys if k in ['openai', 'anthropic', 'groq']])}")
            logger.info(f"   ALL TABS NOW HAVE ACCESS TO LIVE DATA!")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Error distributing API keys globally: {e}")
    
    def _deferred_redis_init(self):
        """Deferred Redis initialization - called after Redis Quantum Nexus is ready."""
        try:
            # Use the proven Redis connection pattern from WalletTab
            REDIS_HOST = 'localhost'
            REQUIRED_REDIS_PORT = 6380
            REQUIRED_REDIS_PASSWORD = 'QuantumNexus2025'
            
            logger.info(f"🔗 API Key Manager connecting to Redis Quantum Nexus on port {REQUIRED_REDIS_PORT}...")
            
            # Initialize Quantum Nexus Redis connection - strict port 6380 enforcement
            import redis
            self.redis = redis.Redis(  # type: ignore
                host=REDIS_HOST,
                port=REQUIRED_REDIS_PORT,
                password=REQUIRED_REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=10,
                retry_on_timeout=True
            )
            
            # Test connection with ping
            if not self.redis.ping():
                raise ConnectionError("Redis Quantum Nexus connection failed ping test")
                
            logger.info("✅ API Key Manager connected to Redis Quantum Nexus successfully")
            
        except Exception as e:
            # Log warning but don't crash - API Key Manager can still function
            logger.warning(f"⚠️ API Key Manager Redis connection failed (will retry): {e}")
            self.redis = None
    
    def _initialize_redis_connection(self):
        """Legacy method - redirects to deferred init."""
        self._deferred_redis_init()
    
    def _load_services_and_keys(self):
        """Load services and API keys from API Key Manager."""
        try:
            # Load API keys
            if hasattr(self.api_key_manager, 'load_api_keys'):
                self.api_key_manager.load_api_keys()
            if hasattr(self.api_key_manager, 'get_all_api_keys'):
                self.api_keys = self.api_key_manager.get_all_api_keys()
            else:
                self.api_keys = {}
            
            # Populate services tree
            self._populate_services_tree()
            
            # Update status
            self.status_label.setText("API keys loaded successfully")
            
            # CRITICAL FIX: Broadcast API keys loaded event to all components
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                try:
                    # Publish synchronously if possible
                    if hasattr(self.event_bus.publish, '__call__'):
                        self.event_bus.publish('api_keys.loaded', {
                            'count': len(self.api_keys),
                            'services': list(self.api_keys.keys()),
                            'timestamp': datetime.now().isoformat()
                        })
                        logger.info(f"📡 Broadcasted API keys loaded event: {len(self.api_keys)} keys")
                except Exception as e:
                    logger.warning(f"Failed to broadcast API keys loaded event: {e}")
        except Exception as e:
            logger.error(f"Error loading API keys: {e}")
            self.status_label.setText(f"Error loading API keys: {str(e)}")
            self.status_label.setStyleSheet("font-weight: bold; padding: 5px; color: #AA0000;")
    
    def _populate_services_tree(self):
        """Populate the services tree with available services."""
        self.services_tree.clear()
        
        # Create category items
        categories = {}
        for category in ["Exchanges", "AI Services", "Blockchain", "Data Providers", "Other"]:
            item = QTreeWidgetItem([category])
            item.setIcon(0, get_icon(category.lower().replace(" ", "_")))
            categories[category] = item
            self.services_tree.addTopLevelItem(item)
            item.setExpanded(True)
        
        # CRITICAL: Display actually loaded API keys from config/api_keys.json
        logger.info(f"🔑 Populating services tree with {len(self.api_keys)} loaded API keys")
        
        # Map service IDs to categories
        service_categories = {
            'kucoin': 'Exchanges', 'bybit': 'Exchanges', 'binance': 'Exchanges',
            'coinbase': 'Exchanges', 'kraken': 'Exchanges', 'huobi': 'Exchanges',
            'blockchain': 'Blockchain', 'etherscan': 'Blockchain', 'infura': 'Blockchain',
            'alchemy': 'Blockchain', 'quicknode': 'Blockchain', 'moralis': 'Blockchain',
            'grok_xai': 'AI Services', 'openai': 'AI Services', 'huggingface': 'AI Services',
            'codegpt': 'AI Services', 'llama': 'AI Services', 'cohere': 'AI Services',
            'alpha_vantage': 'Data Providers', 'nasdaq': 'Data Providers', 'fred': 'Data Providers',
            'nansen': 'Data Providers', 'coinlayer': 'Data Providers', 'market_stack': 'Data Providers',
        }
        
        # Display all loaded API keys
        for service_id, key_data in self.api_keys.items():
            # Determine category
            category = service_categories.get(service_id, 'Other')
            if category not in categories:
                category = 'Other'
            
            # Format service name
            service_name = service_id.replace('_', ' ').title()
            
            # Check if key has actual values (not empty strings)
            # ACCEPT demo keys as valid - they're placeholders for real services
            has_key = False
            try:
                if isinstance(key_data, dict):
                    # Check for non-empty api_key or any non-empty credential field
                    if key_data:  # Dict exists with keys
                        has_key = any(
                            str(key_data.get(field, '')).strip() and str(key_data.get(field, '')).strip() not in ['', 'None', 'null']
                            for field in ['api_key', 'apiKey', 'api_secret', 'apiSecret', 'client_id', 'client_secret', 
                                         'access_token', 'bearer_token', 'username', 'password', 'token', 'key', 'secret']
                        )
                elif isinstance(key_data, (list, tuple)):
                    # Handle array format (like blockchain_providers) - ACCEPT demo keys
                    has_key = False
                    for entry in key_data:  # type: ignore[union-attr]
                        if isinstance(entry, dict):
                            if any(
                                str(entry.get(field, '')).strip() and str(entry.get(field, '')).strip() not in ['', 'None', 'null']
                                for field in ['api_key', 'apiKey', 'api_secret', 'apiSecret', 'client_id', 'client_secret', 
                                             'access_token', 'bearer_token', 'username', 'password', 'token', 'key', 'secret']
                            ):
                                has_key = True
                                break
                elif isinstance(key_data, str):
                    # Handle string format - accept any non-empty string
                    has_key = bool(key_data.strip()) and key_data.strip() not in ['None', 'null', '']
            except (TypeError, AttributeError):
                has_key = False
            
            # Determine status
            if has_key:
                status = "🟢 Configured"
                status_color = "#00FF00"
            else:
                status = "⚪ Empty"
                status_color = "#888888"
            
            # Create service item
            service_item = QTreeWidgetItem([service_name, status])
            service_item.setData(0, Qt.ItemDataRole.UserRole, service_id)
            service_item.setForeground(1, QColor(status_color))
            
            # Add to category
            categories[category].addChild(service_item)
            logger.debug(f"  Added {service_name} ({service_id}) to {category}: {status}")
        
        # Count configured services
        configured_count = sum(1 for item_text in [categories[cat].child(i).text(1) 
                                                    for cat in categories 
                                                    for i in range(categories[cat].childCount())]
                              if "🟢 Configured" in item_text)
        
        logger.info(f"✅ Services tree populated with {len(self.api_keys)} API keys ({configured_count} configured)")
        
        # Update status label to show configured count
        self.status_label.setText(f"✅ Ready - {len(self.api_keys)} API keys loaded ({configured_count} configured)")
        self.status_label.setStyleSheet("font-weight: bold; padding: 5px; color: #00AA00;")
        
        # Apply the current filter
        self.filter_services()
        
        # CRITICAL FIX: Auto-select first configured service to show details by default
        for category in categories.values():
            for i in range(category.childCount()):
                child = category.child(i)
                if "🟢 Configured" in child.text(1):
                    # Found first configured service - select it
                    self.services_tree.setCurrentItem(child)
                    service_id = child.data(0, Qt.ItemDataRole.UserRole)
                    self.current_service = service_id
                    self._update_service_details(service_id)
                    logger.info(f"✅ Auto-selected first configured service: {child.text(0)}")
                    return  # Exit after selecting first one
    
    def _connect_signals(self):
        """Connect signals to slots."""
        # Connect internal signals
        self.connection_status_changed.connect(self._handle_connection_status_changed)
        self.keys_updated.connect(self._handle_keys_updated)
        
        # Connect to event bus if available
        if self.event_bus:
            # Check if there's a running event loop, if not, defer subscriptions
            try:
                loop = asyncio.get_running_loop()
                # Event loop is running, create tasks for async subscribe APIs
                if hasattr(self.event_bus.subscribe, '__await__'):
                    asyncio.create_task(self.event_bus.subscribe("api_key_manager.connection_status_changed", self._handle_connection_status_changed))
                    asyncio.create_task(self.event_bus.subscribe("api_key_manager.keys_updated", self._handle_keys_updated))
                    asyncio.create_task(self.event_bus.subscribe("exchange.health.snapshot", self._handle_exchange_health_snapshot))
                else:
                    # Fallback for synchronous subscribe implementations
                    try:
                        self.event_bus.subscribe("api_key_manager.connection_status_changed", self._handle_connection_status_changed)
                        self.event_bus.subscribe("api_key_manager.keys_updated", self._handle_keys_updated)
                        self.event_bus.subscribe("exchange.health.snapshot", self._handle_exchange_health_snapshot)
                    except Exception as sub_err:
                        logger.warning(f"Event bus synchronous subscription failed: {sub_err}")
            except RuntimeError:
                # No running event loop during initialization - subscriptions will be handled later
                logger.info("Event bus subscriptions deferred - no running event loop during init")
    
    def on_service_selected(self):
        """Handle service selection changed in the services tree."""
        selected_items = self.services_tree.selectedItems()
        if not selected_items:
            self.current_service = None
            self._update_service_details(None)
            return
            
        selected_item = selected_items[0]
        # Check if it's a service or category
        if selected_item.parent() is None:
            # It's a category, not a service
            self.current_service = None
            self._update_service_details(None)
            return
            
        # It's a service
        service_id = selected_item.data(0, Qt.ItemDataRole.UserRole)
        self.current_service = service_id
        self._update_service_details(service_id)
    
    def _update_service_details(self, service_id):
        """Update the service details panel with information about the selected service."""
        if not service_id:
            # No service selected
            self.service_name.setText("No service selected")
            self.service_status.setText("Status: Not connected")
            self.last_updated.setText("Last updated: Never")
            self.keys_table.setRowCount(0)
            self.test_result.clear()
            
            # Disable key controls
            self.edit_key_btn.setEnabled(False)
            self.delete_key_btn.setEnabled(False)
            return
            
        # Get service info from API Key Manager
        if not self.api_key_manager:
            return
            
        if hasattr(self.api_key_manager, 'get_service_info'):
            service_info = self.api_key_manager.get_service_info(service_id) or {}  # type: ignore
        else:
            service_info = {}
        service_name = service_info.get("name", service_id)
        
        # Update service details
        self.service_name.setText(service_name)
        
        # Connection status
        if hasattr(self.api_key_manager, 'connection_status'):
            connection_status = self.api_key_manager.connection_status.get(service_id, {})
        else:
            connection_status = {}
        connected = connection_status.get("connected", False)
        last_tested = connection_status.get("last_tested", 0) or connection_status.get("last_check", 0)
        status_message = connection_status.get("message", "") or connection_status.get("error", "")
        
        # CRITICAL FIX: Check if service has keys configured
        service_keys = self.api_keys.get(service_id, {})
        has_keys = len(service_keys) > 0
        
        if connected:
            status_text = "Status: Connected"
            status_color = "#00AA00"
        elif has_keys:
            # Keys are configured but not tested yet
            status_text = "Status: Configured (not tested)"
            status_color = "#FFA500"  # Orange for configured but untested
        else:
            status_text = "Status: Not configured"
            status_color = "#AA0000"
            
        if status_message:
            status_text += f" - {status_message}"
            
        self.service_status.setText(status_text)
        self.service_status.setStyleSheet(f"color: {status_color}")
        
        # Last updated
        if last_tested > 0:
            last_tested_dt = QDateTime.fromSecsSinceEpoch(int(last_tested))
            last_updated_text = f"Last checked: {last_tested_dt.toString()}"  
        elif has_keys:
            # Show current time for configured keys
            current_dt = QDateTime.currentDateTime()
            last_updated_text = f"Keys loaded: {current_dt.toString('yyyy-MM-dd hh:mm:ss')}"
        else:
            last_updated_text = "Last tested: Never"
            
        self.last_updated.setText(last_updated_text)
        
        # Update keys table
        self._update_keys_table(service_id)
        
        # Enable key controls
        self.edit_key_btn.setEnabled(True)
        self.delete_key_btn.setEnabled(True)

        # Highlight corresponding exchange in health table if present
        self._highlight_exchange_in_health_table(service_id)

    def _freeze_table_updates(self, table: QTableWidget) -> tuple[bool, bool, bool]:
        try:
            updates = bool(table.updatesEnabled())
        except Exception:
            updates = True
        try:
            blocked = bool(table.signalsBlocked())
        except Exception:
            blocked = False
        try:
            sorting = bool(table.isSortingEnabled())
        except Exception:
            sorting = False
        try:
            table.setUpdatesEnabled(False)
        except Exception:
            pass
        try:
            table.blockSignals(True)
        except Exception:
            pass
        try:
            table.setSortingEnabled(False)
        except Exception:
            pass
        return updates, blocked, sorting

    def _restore_table_updates(self, table: QTableWidget, state: tuple[bool, bool, bool]) -> None:
        updates, blocked, sorting = state
        try:
            table.setSortingEnabled(sorting)
        except Exception:
            pass
        try:
            table.blockSignals(blocked)
        except Exception:
            pass
        try:
            table.setUpdatesEnabled(updates)
        except Exception:
            pass
    
    def _update_keys_table(self, service_id):
        """Update the keys table with API keys for the selected service."""
        table = getattr(self, "keys_table", None)
        if table is None:
            return

        if not service_id or not self.api_key_manager:
            table.setRowCount(0)
            return

        service_keys = self.api_keys.get(service_id, {}) or {}
        rows = list(service_keys.items())

        _state = self._freeze_table_updates(table)
        try:
            table.setRowCount(len(rows))
            for row_pos, (key_name, key_value) in enumerate(rows):
                table.setItem(row_pos, 0, QTableWidgetItem(key_name))

                if key_value:
                    display_value = key_value if self.show_secrets else "********"
                else:
                    display_value = "<missing>"
                value_item = QTableWidgetItem(display_value)
                if not key_value:
                    value_item.setForeground(QColor("#AA0000"))
                value_item.setData(Qt.ItemDataRole.UserRole, key_value)
                table.setItem(row_pos, 1, value_item)

                copy_btn = QPushButton("Copy")
                copy_btn.setIcon(get_icon("copy"))
                copy_btn.clicked.connect(lambda _, k=key_value: QApplication.clipboard().setText(k))
                table.setCellWidget(row_pos, 2, copy_btn)
        finally:
            self._restore_table_updates(table, _state)
            
    # Event handlers
    def _handle_connection_status_changed(self, service_id=None, connected=None, message=None):
        """Handle connection status changed event.
        
        Args:
            service_id: Service ID
            connected: Connection status
            message: Status message
        """
        if isinstance(service_id, dict):
            # Event data format
            event_data = service_id
            service_id = event_data.get("service_id")
            connected = event_data.get("connected")
            message = event_data.get("message")
        
        if not service_id:
            return
            
        # Update service item in tree
        for i in range(self.services_tree.topLevelItemCount()):
            category = self.services_tree.topLevelItem(i)
            for j in range(category.childCount()):
                service_item = category.child(j)
                if service_item.data(0, Qt.ItemDataRole.UserRole) == service_id:
                    service_item.setText(1, "Connected" if connected else "Not Connected")
                    service_item.setForeground(1, QColor("#00AA00" if connected else "#AA0000"))
                    break
        
        # If this is the selected service, update details
        if service_id == self.current_service:
            self._update_service_details(service_id)
            
        # Log the change
        log_level = logging.INFO if connected else logging.WARNING
        logger.log(log_level, f"Connection status for {service_id}: {'Connected' if connected else 'Not Connected'} - {message}")
    
    def _handle_exchange_health_snapshot(self, payload):
        """Handle exchange health snapshots published by RealExchangeExecutor.
        
        Args:
            payload: Dict containing timestamp and per-exchange health mapping.
        """
        try:
            if not isinstance(payload, dict):
                return
            health = payload.get("health") or {}
            if not isinstance(health, dict):
                return
            self.exchange_health = health
            self._update_exchange_health_ui()
        except Exception as e:
            logger.warning(f"Error handling exchange health snapshot: {e}")
    
    def _handle_keys_updated(self, service_id=None):
        """Handle API keys updated event.
        
        Args:
            service_id: Service ID or event data dict
        """
        if isinstance(service_id, dict):
            # Event data format
            event_data = service_id
            service_id = event_data.get("service_id")
        
        # Reload API keys
        if self.api_key_manager:
            self.api_keys = self.api_key_manager.get_all_api_keys()
            
        # Update UI if needed
        if service_id == self.current_service:
            self._update_keys_table(service_id)

        # Refresh exchange health highlight for the current selection
        if self.current_service:
            self._highlight_exchange_in_health_table(self.current_service)

    def _update_exchange_health_ui(self):
        """Update the Exchange Health table based on the latest snapshot."""
        table = getattr(self, "exchange_health_table", None)
        if table is None:
            return

        if not self.exchange_health:
            table.setRowCount(0)
            return

        exchange_names = sorted(self.exchange_health.keys())
        _state = self._freeze_table_updates(table)
        try:
            table.setRowCount(len(exchange_names))
            for row, ex_name in enumerate(exchange_names):
                info = self.exchange_health.get(ex_name) or {}
                status = str(info.get("status", "unknown"))
                details = str(info.get("error") or info.get("details") or "")

                ex_item = QTableWidgetItem(ex_name)
                table.setItem(row, 0, ex_item)

                status_item = QTableWidgetItem(status)
                status_lower = status.lower()
                if status_lower in ("ok", "ok_empty"):
                    status_item.setForeground(QColor("#00AA00"))
                elif status_lower in ("restricted_location",):
                    status_item.setForeground(QColor("#FFA500"))
                elif status_lower in ("permission_denied", "exchange_error"):
                    status_item.setForeground(QColor("#AA0000"))
                elif status_lower in ("not_connected", "not_implemented"):
                    status_item.setForeground(QColor("#888888"))
                else:
                    status_item.setForeground(QColor("#CCCCCC"))

                table.setItem(row, 1, status_item)

                details_item = QTableWidgetItem(details)
                table.setItem(row, 2, details_item)
        finally:
            self._restore_table_updates(table, _state)

        if self.current_service:
            self._highlight_exchange_in_health_table(self.current_service)

    def _highlight_exchange_in_health_table(self, service_id):
        """Highlight the row for the currently selected exchange/service."""
        if not hasattr(self, "exchange_health_table") or not service_id:
            return

        target = str(service_id).lower()
        self.exchange_health_table.clearSelection()

        for row in range(self.exchange_health_table.rowCount()):
            item = self.exchange_health_table.item(row, 0)
            if not item:
                continue
            if item.text().lower() == target:
                self.exchange_health_table.selectRow(row)
                self.exchange_health_table.scrollToItem(item)
                break
    
    # User actions
    def filter_services(self, filter_text=None):
        """Filter services based on search text and category.
        
        Args:
            filter_text: Optional filter text
        """
        # Use search box text if not provided
        if filter_text is None or not isinstance(filter_text, str):
            filter_text = self.search_edit.text().lower()
            
        # Get selected category
        category = self.category_combo.currentText()
        
        # Apply filter
        for i in range(self.services_tree.topLevelItemCount()):
            category_item = self.services_tree.topLevelItem(i)
            category_name = category_item.text(0)
            
            # Hide/show category based on filter
            if category != "All Categories" and category_name != category:
                category_item.setHidden(True)
                continue
            else:
                category_item.setHidden(False)
            
            # Filter services within category
            visible_children = 0
            for j in range(category_item.childCount()):
                service_item = category_item.child(j)
                service_name = service_item.text(0).lower()
                
                if filter_text and filter_text not in service_name:
                    service_item.setHidden(True)
                else:
                    service_item.setHidden(False)
                    visible_children += 1
            
            # Hide empty categories
            category_item.setHidden(visible_children == 0)
    
    def show_context_menu(self, position):
        """Show context menu for service item.
        
        Args:
            position: Menu position
        """
        # Get item at position
        item = self.services_tree.itemAt(position)
        if not item or item.parent() is None:
            # No item or it's a category
            return
            
        service_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not service_id:
            return
            
        # Create context menu
        menu = QMenu()
        test_action = menu.addAction("Test Connection")
        test_action.setIcon(get_icon("connection"))
        
        # Add or edit API key actions
        if service_id in self.api_keys:
            edit_action = menu.addAction("Edit API Key")
            edit_action.setIcon(get_icon("edit"))
            delete_action = menu.addAction("Delete API Key")
            delete_action.setIcon(get_icon("delete"))
        else:
            add_action = menu.addAction("Add API Key")
            add_action.setIcon(get_icon("add"))
        
        # Show menu and handle action
        action = menu.exec(self.services_tree.mapToGlobal(position))
        if not action:
            return
            
        # Handle actions
        if action == test_action:
            self.test_connection(service_id)
        elif action == edit_action if 'edit_action' in locals() else None:
            self.edit_api_key(service_id)
        elif action == delete_action if 'delete_action' in locals() else None:
            self.delete_api_key(service_id)
        elif action == add_action if 'add_action' in locals() else None:
            self.add_api_key(service_id)
    
    def toggle_secrets(self, show):
        """Toggle visibility of secret API keys.
        
        Args:
            show: Whether to show secrets
        """
        self.show_secrets = show
        self._emit_ui_telemetry(
            "apikeys.toggle_secrets_clicked",
            metadata={"show": bool(show)},
        )
        
        # Update button text
        self.toggle_secrets_btn.setText("Hide Secrets" if show else "Show Secrets")
        
        # Update keys table
        if self.current_service:
            self._update_keys_table(self.current_service)
    
    def add_api_key(self, service_id=None):
        """Add a new API key.
        
        Args:
            service_id: Optional service ID to add key for
        """
        # Use current service if not provided
        if not service_id and self.current_service:
            service_id = self.current_service
            
        # Get service info
        if not self.api_key_manager or not service_id:
            return
            
        if hasattr(self.api_key_manager, 'get_service_info'):
            service_info = self.api_key_manager.get_service_info(service_id) or {}  # type: ignore
        else:
            service_info = {}
        service_name = service_info.get("name", service_id)
        
        # Show dialog to get key details
        key_name, ok = QInputDialog.getText(
            self, f"Add API Key for {service_name}", "Key Name:")
        if not ok or not key_name:
            return
            
        key_value, ok = QInputDialog.getText(
            self, f"Add API Key for {service_name}", "Key Value:", 
            QLineEdit.EchoMode.Password)
        if not ok or not key_value:
            return
            
        # Add or update key
        try:
            existing = self.api_keys.get(service_id, {}) or {}
            key_data = dict(existing)
            key_data[key_name] = key_value
            if hasattr(self.api_key_manager, 'add_api_key'):
                self.api_key_manager.add_api_key(service_id, key_data)  # type: ignore[arg-type]
            elif hasattr(self.api_key_manager, 'save_api_key'):
                self.api_key_manager.save_api_key(service_id, key_data)  # type: ignore[arg-type]
            
            # Update local cache
            if hasattr(self.api_key_manager, 'get_all_api_keys'):
                self.api_keys = self.api_key_manager.get_all_api_keys()
            else:
                self.api_keys = {}

            # Redistribute keys globally so other components see updates
            if hasattr(self.api_key_manager, 'api_keys'):
                self._distribute_api_keys_globally(self.api_key_manager.api_keys)

            if service_id == self.current_service:
                self._update_keys_table(service_id)
                
            # Update status
            self.status_label.setText(f"API key '{key_name}' added for {service_name}")
            self.status_label.setStyleSheet("font-weight: bold; padding: 5px; color: #00AA00;")
            self._emit_ui_telemetry(
                "apikeys.add_api_key_clicked",
                metadata={"service_id": service_id, "key_name": key_name},
            )
            
            self._persist_consumer_keys()

            # Notify event bus
            if self.event_bus:
                self.event_bus.publish("api_key_manager.keys_updated", {
                    "service_id": service_id,
                    "timestamp": datetime.now().timestamp()
                })
        except Exception as e:
            logger.error(f"Error adding API key: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to add API key: {str(e)}"
            )
    
    def edit_api_key(self, service_id=None):
        """Edit an existing API key.
        
        Args:
            service_id: Optional service ID to edit key for
        """
        # Use current service if not provided
        if not service_id and self.current_service:
            service_id = self.current_service
            
        # Get service info
        if not self.api_key_manager or not service_id:
            return
            
        if hasattr(self.api_key_manager, 'get_service_info'):
            service_info = self.api_key_manager.get_service_info(service_id) or {}  # type: ignore
        else:
            service_info = {}
        service_name = service_info.get("name", service_id)
        
        # Get current keys
        service_keys = self.api_keys.get(service_id, {})
        if not service_keys:
            QMessageBox.warning(
                self,
                "No Keys",
                f"No API keys found for {service_name}"
            )
            return
            
        # Show dialog to select key
        key_name, ok = QInputDialog.getItem(
            self, f"Edit API Key for {service_name}",
            "Select Key:", list(service_keys.keys()), 0, False
        )
        if not ok or not key_name:
            return
            
        current_value = service_keys.get(key_name, "")
        
        # Show dialog to edit value
        key_value, ok = QInputDialog.getText(
            self, f"Edit API Key for {service_name}", "Key Value:",
            QLineEdit.EchoMode.Password, current_value
        )
        if not ok or not key_value:
            return
            
        # Update key
        try:
            updated = dict(service_keys)
            updated[key_name] = key_value
            if hasattr(self.api_key_manager, 'add_api_key'):
                self.api_key_manager.add_api_key(service_id, updated)  # type: ignore[arg-type]
            elif hasattr(self.api_key_manager, 'save_api_key'):
                self.api_key_manager.save_api_key(service_id, updated)  # type: ignore[arg-type]
            
            # Update local cache
            if hasattr(self.api_key_manager, 'get_all_api_keys'):
                self.api_keys = self.api_key_manager.get_all_api_keys()
            else:
                self.api_keys = {}

            # Redistribute keys globally
            if hasattr(self.api_key_manager, 'api_keys'):
                self._distribute_api_keys_globally(self.api_key_manager.api_keys)

            if service_id == self.current_service:
                self._update_keys_table(service_id)
                
            # Update status
            self.status_label.setText(f"API key '{key_name}' updated for {service_name}")
            self.status_label.setStyleSheet("font-weight: bold; padding: 5px; color: #00AA00;")
            self._emit_ui_telemetry(
                "apikeys.edit_api_key_clicked",
                metadata={"service_id": service_id, "key_name": key_name},
            )
            self._persist_consumer_keys()

            # Notify event bus
            if self.event_bus:
                self.event_bus.publish("api_key_manager.keys_updated", {
                    "service_id": service_id,
                    "timestamp": datetime.now().timestamp()
                })
        except Exception as e:
            logger.error(f"Error updating API key: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to update API key: {str(e)}"
            )
    
    def delete_api_key(self, service_id=None):
        """Delete an existing API key.
        
        Args:
            service_id: Optional service ID to delete key for
        """
        # Use current service if not provided
        if not service_id and self.current_service:
            service_id = self.current_service
            
        # Get service info
        if not self.api_key_manager or not service_id:
            return
            
        if hasattr(self.api_key_manager, 'get_service_info'):
            service_info = self.api_key_manager.get_service_info(service_id) or {}  # type: ignore
        else:
            service_info = {}
        service_name = service_info.get("name", service_id)
        
        # Get current keys
        service_keys = self.api_keys.get(service_id, {})
        if not service_keys:
            QMessageBox.warning(
                self,
                "No Keys",
                f"No API keys found for {service_name}"
            )
            return
            
        # Show dialog to select key
        key_name, ok = QInputDialog.getItem(
            self, f"Delete API Key for {service_name}",
            "Select Key:", list(service_keys.keys()), 0, False
        )
        if not ok or not key_name:
            return
            
        # Confirm deletion
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the API key '{key_name}' for {service_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Delete key
        try:
            updated = dict(service_keys)
            if key_name in updated:
                del updated[key_name]

            if updated:
                # Still other fields left for this service
                if hasattr(self.api_key_manager, 'add_api_key'):
                    self.api_key_manager.add_api_key(service_id, updated)  # type: ignore[arg-type]
                elif hasattr(self.api_key_manager, 'save_api_key'):
                    self.api_key_manager.save_api_key(service_id, updated)  # type: ignore[arg-type]
            else:
                # No fields left; remove the service entirely
                if hasattr(self.api_key_manager, 'delete_api_key'):
                    self.api_key_manager.delete_api_key(service_id)  # type: ignore[arg-type]
            
            # Update local cache
            if hasattr(self.api_key_manager, 'get_all_api_keys'):
                self.api_keys = self.api_key_manager.get_all_api_keys()
            else:
                self.api_keys = {}

            # Redistribute keys globally
            if hasattr(self.api_key_manager, 'api_keys'):
                self._distribute_api_keys_globally(self.api_key_manager.api_keys)

            if service_id == self.current_service:
                self._update_keys_table(service_id)
                
            # Update status
            self.status_label.setText(f"API key '{key_name}' deleted for {service_name}")
            self._emit_ui_telemetry(
                "apikeys.delete_api_key_clicked",
                metadata={"service_id": service_id, "key_name": key_name},
            )
            self.status_label.setStyleSheet("font-weight: bold; padding: 5px; color: #00AA00;")
            self._persist_consumer_keys()

            # Notify event bus
            if self.event_bus:
                self.event_bus.publish("api_key_manager.keys_updated", {
                    "service_id": service_id,
                    "timestamp": datetime.now().timestamp()
                })
        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete API key: {str(e)}"
            )
    
    @async_slot
    async def test_connection(self, service_id=None):
        """Test connection to a service.
        
        Args:
            service_id: Optional service ID to test connection for
        """
        # Use current service if not provided
        if not service_id and self.current_service:
            service_id = self.current_service
            
        # Get service info
        if not self.api_key_manager or not service_id:
            return
            
        if hasattr(self.api_key_manager, 'get_service_info'):
            service_info = self.api_key_manager.get_service_info(service_id) or {}  # type: ignore
        else:
            service_info = {}
        service_name = service_info.get("name", service_id)
        
        # Update test result
        self.test_result.clear()
        self.test_result.append(f"Testing connection to {service_name}...")
        
        # Disable UI during test
        self.setEnabled(False)
        
        try:
            # Test connection
            if hasattr(self.api_key_manager, 'test_connection_async'):
                success, result = await self.api_key_manager.test_connection_async(service_id)  # type: ignore
            else:
                success, result = False, "Method not available"
            
            # Update UI
            if not service_id:
                self.test_result.append("⚠️ No service selected for connection test")
                return
            self._emit_ui_telemetry(
                "apikeys.test_connection_clicked",
                metadata={"service_id": service_id},
            )
            if success:
                self.test_result.append(f"✅ Connection successful: {result}")
                self.test_result.setStyleSheet("color: #00AA00;")
            else:
                self.test_result.append(f"❌ Connection failed: {result}")
                self.test_result.setStyleSheet("color: #AA0000;")
                
            # Update connection status
            self._handle_connection_status_changed(service_id, success, result)
            
            # Notify event bus
            if self.event_bus:
                self.event_bus.publish("api_key_manager.connection_status_changed", {
                    "service_id": service_id,
                    "connected": success,
                    "message": result,
                    "timestamp": datetime.now().timestamp()
                })
        except Exception as e:
            logger.error(f"Error testing connection: {e}")
            self.test_result.append(f"❌ Error testing connection: {str(e)}")
            self.test_result.setStyleSheet("color: #AA0000;")
        finally:
            # Re-enable UI
            self.setEnabled(True)
    
    def refresh_keys(self):
        """Refresh API keys from storage."""
        if not self.api_key_manager:
            return
        
        try:
            self._emit_ui_telemetry("apikeys.refresh_clicked")
            # Reload API keys from disk when supported
            if hasattr(self.api_key_manager, 'reload_from_disk'):
                self.api_key_manager.reload_from_disk()  # type: ignore[call-arg]
            elif hasattr(self.api_key_manager, 'load_api_keys'):
                self.api_key_manager.load_api_keys()
            if hasattr(self.api_key_manager, 'get_all_api_keys'):
                self.api_keys = self.api_key_manager.get_all_api_keys()
            else:
                self.api_keys = {}
            
            # Redistribute updated keys globally
            if hasattr(self.api_key_manager, 'api_keys'):
                self._distribute_api_keys_globally(self.api_key_manager.api_keys)

            # Update UI
            self._populate_services_tree()
            if self.current_service:
                self._update_keys_table(self.current_service)
                
            # Update status
            self.status_label.setText("API keys refreshed successfully")
            self.status_label.setStyleSheet("font-weight: bold; padding: 5px; color: #00AA00;")
        except Exception as e:
            logger.error(f"Error refreshing API keys: {e}")
            self.status_label.setText(f"Error refreshing API keys: {str(e)}")
            self.status_label.setStyleSheet("font-weight: bold; padding: 5px; color: #AA0000;")
    
    def _persist_consumer_keys(self):
        """Save current API keys to the consumer's shared path so mobile sees them too."""
        if not self.is_consumer or not self._consumer_keys_path:
            return
        try:
            keys = {}
            if hasattr(self.api_key_manager, 'api_keys'):
                keys = dict(self.api_key_manager.api_keys)
            elif self.api_keys:
                keys = dict(self.api_keys)
            os.makedirs(os.path.dirname(self._consumer_keys_path), exist_ok=True)
            with open(self._consumer_keys_path, "w", encoding="utf-8") as f:
                json.dump(keys, f, indent=2)
            logger.info("Consumer keys persisted: %d services -> %s",
                        len(keys), self._consumer_keys_path)
        except Exception as e:
            logger.warning("Failed to persist consumer keys: %s", e)

    def show_help(self):
        """Show comprehensive help dialog with API key guide (names + links, NOT actual keys)."""
        from core.mobile_sync_server import MobileSyncServer
        guide = MobileSyncServer._get_api_key_guide()
        categories = guide.get("categories", {})

        html = """<h2 style="color:#FFD700;">API Key Manager Help</h2>"""

        html += """<h3 style="color:#00BFFF;">Why Do I Need My Own API Keys?</h3>
        <p style="font-size:13px;">""" + guide.get("why_own_keys", "") + "</p>"

        html += """<h3 style="color:#00BFFF;">How More Keys = Better Trading</h3><ul>"""
        for item in guide.get("how_keys_help", []):
            html += f"<li style='font-size:12px;'>{item}</li>"
        html += "</ul>"

        html += """<h3 style="color:#FF4444;">Security</h3><ul>"""
        for item in guide.get("security_notes", []):
            html += f"<li style='font-size:12px;'>{item}</li>"
        html += "</ul>"

        for cat_name, services in categories.items():
            html += f"<h3 style='color:#FFD700;'>{cat_name}</h3>"
            html += "<table cellpadding='4' style='font-size:12px;width:100%;'>"
            html += "<tr style='color:#888;'><td><b>Service</b></td><td><b>Tier</b></td><td><b>Free?</b></td><td><b>Description</b></td></tr>"
            for svc in services:
                tier_color = {"essential": "#FF6B6B", "recommended": "#FFD93D",
                              "optional": "#6BCB77"}.get(svc["tier"], "#AAA")
                free = "Yes" if svc.get("free_tier") else "Paid"
                html += (
                    f"<tr>"
                    f"<td><a href='{svc['url']}' style='color:#00BFFF;'>{svc['service']}</a></td>"
                    f"<td style='color:{tier_color};'>{svc['tier'].upper()}</td>"
                    f"<td>{free}</td>"
                    f"<td>{svc['desc']}</td>"
                    f"</tr>"
                )
            html += "</table>"

        html += """
        <h3 style="color:#00BFFF;">How to Add an API Key</h3>
        <ol style="font-size:12px;">
        <li>Visit the service website (click the link above)</li>
        <li>Create a free account and generate an API key</li>
        <li><b>IMPORTANT:</b> Set permissions to <b>TRADE ONLY</b> (disable withdrawals)</li>
        <li>Copy the API Key and Secret</li>
        <li>Click 'Add API Key' in this tab, select the service, and paste your keys</li>
        <li>Click 'Test Connection' to verify</li>
        </ol>
        <p style="font-size:11px;color:#888;">Your keys are stored locally on your device
        and shared between your desktop and mobile app. They never leave your machine.</p>
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("API Key Guide — Where to Get Keys")
        dialog.setMinimumSize(800, 600)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(html)
        text.setStyleSheet("background:#0A0E17; color:#E0E0E0; border:none; padding:10px;")
        layout.addWidget(text)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet(
            "QPushButton{background:#1a1f2e;color:#FFD700;padding:8px 20px;"
            "border:1px solid #FFD700;border-radius:4px;}"
            "QPushButton:hover{background:#FFD700;color:#0A0E17;}")
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        dialog.exec()
    
    # =========================================================================
    # 2026 SOTA: Health Dashboard
    # =========================================================================
    
    def show_health_dashboard(self):
        """Show the API key health dashboard dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("API Key Health Dashboard")
        dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # Header with refresh button
        header_layout = QHBoxLayout()
        header_label = QLabel("<h2>API Key Health Status</h2>")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self._refresh_health_dashboard(table, summary_label))
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)
        
        # Summary section
        summary_group = QGroupBox("Summary")
        summary_layout = QHBoxLayout(summary_group)
        summary_label = QLabel("Loading health data...")
        summary_layout.addWidget(summary_label)
        layout.addWidget(summary_group)
        
        # Health table
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Service", "Health", "Last Check", "Failures", "Status"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(table)
        
        # Populate data
        self._refresh_health_dashboard(table, summary_label)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def _refresh_health_dashboard(self, table: QTableWidget, summary_label: QLabel):
        """Refresh the health dashboard data."""
        try:
            if not self.api_key_manager:
                summary_label.setText("API Key Manager not available")
                return
            
            # Get health summary
            health_summary = self.api_key_manager.get_health_summary()
            
            # Update summary label
            summary_text = f"""
            <b>Last Full Check:</b> {datetime.fromtimestamp(health_summary.get('last_full_check', 0)).strftime('%Y-%m-%d %H:%M:%S') if health_summary.get('last_full_check') else 'Never'}<br>
            <b>Services in Backoff:</b> {health_summary.get('services_in_backoff', 0)}<br>
            <b>Services with Failures:</b> {health_summary.get('services_with_failures', 0)}<br>
            <b>Total Keys:</b> {len(self.api_key_manager.api_keys)}
            """
            summary_label.setText(summary_text)
            
            # Update health indicator
            if health_summary.get('services_with_failures', 0) > 0:
                self.health_indicator.setStyleSheet("color: orange; font-size: 16px;")
                self.health_indicator.setToolTip(f"Warning: {health_summary.get('services_with_failures')} services with failures")
            else:
                self.health_indicator.setStyleSheet("color: green; font-size: 16px;")
                self.health_indicator.setToolTip("System health: Good")
            
            # Populate table
            table.setRowCount(0)
            
            for service, key_data in self.api_key_manager.api_keys.items():
                if service.startswith('_'):
                    continue
                    
                row = table.rowCount()
                table.insertRow(row)
                
                # Service name
                table.setItem(row, 0, QTableWidgetItem(service))
                
                # Health status
                status = self.api_key_manager.connection_status.get(service.lower(), {})
                is_valid = status.get("valid", status.get("connected", False))
                health_text = "Healthy" if is_valid else "Unknown"
                health_item = QTableWidgetItem(health_text)
                health_item.setForeground(QColor("green" if is_valid else "gray"))
                table.setItem(row, 1, health_item)
                
                # Last check time
                last_check = status.get("last_check", 0)
                if last_check:
                    check_time = datetime.fromtimestamp(last_check).strftime('%H:%M:%S')
                else:
                    check_time = "Never"
                table.setItem(row, 2, QTableWidgetItem(check_time))
                
                # Failure count
                if hasattr(self.api_key_manager, '_health_tracker'):
                    failures = self.api_key_manager._health_tracker.get('failure_counts', {}).get(service.lower(), 0)
                else:
                    failures = 0
                failure_item = QTableWidgetItem(str(failures))
                if failures > 0:
                    failure_item.setForeground(QColor("red"))
                table.setItem(row, 3, failure_item)
                
                # Status message
                error = status.get("error", "OK")
                table.setItem(row, 4, QTableWidgetItem(error if error else "OK"))
                
        except Exception as e:
            logger.error(f"Error refreshing health dashboard: {e}")
            summary_label.setText(f"Error loading health data: {str(e)}")
    
    # =========================================================================
    # 2026 SOTA: Key Rotation Controls
    # =========================================================================
    
    def show_rotation_dialog(self):
        """Show the key rotation management dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("API Key Rotation Management")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        # Header
        header_label = QLabel("<h2>Key Rotation Schedule</h2>")
        layout.addWidget(header_label)
        
        # Summary section
        summary_group = QGroupBox("Rotation Summary")
        summary_layout = QVBoxLayout(summary_group)
        
        # Get rotation data
        rotation_data = {'overdue': [], 'due_soon': [], 'upcoming': [], 'healthy': []}
        if self.api_key_manager and hasattr(self.api_key_manager, 'check_rotation_needed'):
            try:
                rotation_data = self.api_key_manager.check_rotation_needed()
            except Exception as e:
                logger.warning(f"Could not get rotation data: {e}")
        
        # Summary labels
        overdue_label = QLabel(f"<span style='color: red;'>Overdue: {len(rotation_data.get('overdue', []))}</span>")
        due_soon_label = QLabel(f"<span style='color: orange;'>Due Soon (7 days): {len(rotation_data.get('due_soon', []))}</span>")
        upcoming_label = QLabel(f"<span style='color: blue;'>Upcoming (30 days): {len(rotation_data.get('upcoming', []))}</span>")
        healthy_label = QLabel(f"<span style='color: green;'>Healthy: {len(rotation_data.get('healthy', []))}</span>")
        
        summary_layout.addWidget(overdue_label)
        summary_layout.addWidget(due_soon_label)
        summary_layout.addWidget(upcoming_label)
        summary_layout.addWidget(healthy_label)
        layout.addWidget(summary_group)
        
        # Rotation table
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Service", "Status", "Due Date", "Days Remaining", "Rotation Policy"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Populate table
        all_keys = []
        for status, keys in rotation_data.items():
            for key in keys:
                key['status'] = status
                all_keys.append(key)
        
        # Sort by days until due
        all_keys.sort(key=lambda x: x.get('days_until_due', 999))
        
        table.setRowCount(len(all_keys))
        for row, key_info in enumerate(all_keys):
            service = key_info.get('service', 'Unknown')
            status = key_info.get('status', 'unknown')
            due_date = key_info.get('due_date', 0)
            days = key_info.get('days_until_due', 0)
            policy = key_info.get('rotation_days', 90)
            
            # Service name
            table.setItem(row, 0, QTableWidgetItem(service))
            
            # Status with color
            status_item = QTableWidgetItem(status.upper())
            if status == 'overdue':
                status_item.setForeground(QColor("red"))
            elif status == 'due_soon':
                status_item.setForeground(QColor("orange"))
            elif status == 'upcoming':
                status_item.setForeground(QColor("blue"))
            else:
                status_item.setForeground(QColor("green"))
            table.setItem(row, 1, status_item)
            
            # Due date
            if due_date:
                due_str = datetime.fromtimestamp(due_date).strftime('%Y-%m-%d')
            else:
                due_str = "Not set"
            table.setItem(row, 2, QTableWidgetItem(due_str))
            
            # Days remaining
            days_item = QTableWidgetItem(str(days))
            if days < 0:
                days_item.setForeground(QColor("red"))
            elif days < 7:
                days_item.setForeground(QColor("orange"))
            table.setItem(row, 3, days_item)
            
            # Rotation policy
            table.setItem(row, 4, QTableWidgetItem(f"{policy} days"))
        
        layout.addWidget(table)
        
        # Actions
        actions_layout = QHBoxLayout()
        
        rotate_btn = QPushButton("Rotate Selected Key")
        rotate_btn.clicked.connect(lambda: self._rotate_selected_key(table))
        actions_layout.addWidget(rotate_btn)
        
        set_date_btn = QPushButton("Set Creation Date")
        set_date_btn.clicked.connect(lambda: self._set_key_creation_date(table))
        actions_layout.addWidget(set_date_btn)
        
        actions_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        actions_layout.addWidget(close_btn)
        
        layout.addLayout(actions_layout)
        
        dialog.exec()
    
    def _rotate_selected_key(self, table: QTableWidget):
        """Rotate the selected API key."""
        selected = table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "No Selection", "Please select a service to rotate.")
            return
        
        service = table.item(selected, 0).text()
        
        # Confirm rotation
        reply = QMessageBox.question(
            self, "Confirm Rotation",
            f"Are you sure you want to rotate the API key for {service}?\n\n"
            "You will need to enter new credentials.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Open add key dialog pre-filled with service name
            self.add_api_key(preselect_service=service)
    
    def _set_key_creation_date(self, table: QTableWidget):
        """Set the creation date for a key to start tracking rotation."""
        selected = table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "No Selection", "Please select a service.")
            return
        
        service = table.item(selected, 0).text()
        
        if self.api_key_manager and hasattr(self.api_key_manager, 'set_key_created_date'):
            import time
            self.api_key_manager.set_key_created_date(service, time.time())
            QMessageBox.information(self, "Success", f"Rotation tracking started for {service}.")
    
    # =========================================================================
    # 2026 SOTA: Validate All Keys
    # =========================================================================
    
    def validate_all_keys(self):
        """Validate all API keys in background."""
        if not self.api_key_manager:
            QMessageBox.warning(self, "Error", "API Key Manager not available.")
            return
        
        # Create progress dialog
        progress = QDialog(self)
        progress.setWindowTitle("Validating API Keys")
        progress.setMinimumWidth(400)
        
        layout = QVBoxLayout(progress)
        status_label = QLabel("Starting validation...")
        progress_bar = QProgressBar()
        progress_bar.setRange(0, len(self.api_key_manager.api_keys))
        progress_bar.setValue(0)
        
        layout.addWidget(status_label)
        layout.addWidget(progress_bar)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(progress.close)
        layout.addWidget(cancel_btn)
        
        progress.show()
        
        # Validate each key
        results = {'valid': 0, 'invalid': 0, 'error': 0}
        
        for i, (service, key_data) in enumerate(self.api_key_manager.api_keys.items()):
            if service.startswith('_'):
                continue
                
            status_label.setText(f"Validating: {service}...")
            progress_bar.setValue(i + 1)
            
            # Check if dialog was closed
            if not progress.isVisible():
                break
            
            try:
                # Basic validation
                if self._has_valid_credentials(key_data):
                    results['valid'] += 1
                else:
                    results['invalid'] += 1
            except Exception as e:
                logger.error(f"Error validating {service}: {e}")
                results['error'] += 1
        
        progress.close()
        
        # Show results
        QMessageBox.information(
            self, "Validation Complete",
            f"<h3>Validation Results</h3>"
            f"<p><span style='color: green;'>Valid: {results['valid']}</span></p>"
            f"<p><span style='color: orange;'>Invalid/Empty: {results['invalid']}</span></p>"
            f"<p><span style='color: red;'>Errors: {results['error']}</span></p>"
        )
        
        # Update health indicator
        if results['invalid'] > 0 or results['error'] > 0:
            self.health_indicator.setStyleSheet("color: orange; font-size: 16px;")
        else:
            self.health_indicator.setStyleSheet("color: green; font-size: 16px;")
    
    def _has_valid_credentials(self, key_data) -> bool:
        """Check if key data has valid credentials."""
        if not key_data:
            return False
        
        if isinstance(key_data, str):
            return len(key_data) > 8
        
        if isinstance(key_data, dict):
            api_key = key_data.get('api_key') or key_data.get('key') or key_data.get('apiKey')
            if api_key and len(str(api_key)) > 8:
                return True
        
        return False
