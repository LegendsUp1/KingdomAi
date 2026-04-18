#!/usr/bin/env python3
"""
Kingdom AI Settings Tab
=======================

Settings tab for managing Kingdom AI system configuration.
Provides a tabbed interface for different categories of settings with
persistence through Redis.
"""

import logging
import json
import os
import multiprocessing
import sys
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

# SOTA 2026: Tab Highway System for isolated computational pipelines
try:
    from core.tab_highway_system import get_highway, TabType, get_tab_highway_manager
    HAS_TAB_HIGHWAY = True
except ImportError:
    HAS_TAB_HIGHWAY = False
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QLineEdit, QPushButton, QCheckBox, QSpinBox, QComboBox,
    QGroupBox, QFormLayout, QScrollArea, QMessageBox,
    QSlider, QTextEdit, QSplitter, QFileDialog, QDoubleSpinBox,
    QSizePolicy, QApplication
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt, QThread
from PyQt6.QtGui import QFont, QPalette, QColor

# SOTA 2026: Thread-safe UI update utility
try:
    from utils.qt_thread_safe import is_main_thread, run_on_main_thread
    THREAD_SAFE_AVAILABLE = True
except ImportError:
    THREAD_SAFE_AVAILABLE = False
    def is_main_thread(): return True
    def run_on_main_thread(func): func()

# STATE-OF-THE-ART 2025: Component Factory
from gui.qt_frames.component_factory import ComponentFactory, ComponentConfig

logger = logging.getLogger("KingdomAI.GUI.SettingsTab")

try:
    from core.sentience.settings_sentience_integration import SettingsSentienceIntegration
except ImportError:
    logger.warning("SettingsSentienceIntegration not available")
    SettingsSentienceIntegration = None

try:
    from core.redis_connector import RedisConnector as RedisQuantumNexusConnector
except ImportError:
    logger.warning("RedisQuantumNexusConnector not available")
    RedisQuantumNexusConnector = None


class SettingsTab(QWidget):
    """
    Settings tab for managing Kingdom AI system configuration.
    Provides a tabbed interface for different categories of settings with
    persistence through Redis.
    """
    settings_changed = pyqtSignal(dict)  # Emitted when settings are modified

    def __init__(self, parent=None, event_bus=None, redis_conn=None):
        """Initialize the Settings tab.

        Args:
            parent: Parent widget
            event_bus: Event bus for communication
            redis_conn: Redis connection (MANDATORY - no fallbacks allowed)
        """
        super().__init__(parent)
        self.event_bus = event_bus
        
        # 2025 FIX: Initialize logger attribute
        self.logger = logging.getLogger(f"KingdomAI.{self.__class__.__name__}")

        # Initialize Redis connection (deferred for timing)
        if redis_conn:
            self.redis_conn = redis_conn
        else:
            self.redis_conn = None
            # TIMING FIX: Defer Redis connection to ensure Redis Quantum Nexus is ready
            self.logger.info("⏳ Deferring Settings Redis connection for 1 second to ensure Quantum Nexus is ready...")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, self._deferred_redis_init)

        self.settings = {}
        self.default_settings = self._get_default_settings()
        
        # Add status_label for TabManager compatibility
        self.status_label = QLabel("Settings Ready")
        # Connect to central ThothAI brain system
        self._connect_to_central_brain()
        
        # Initialize settings UI
        self.init_ui()
        self.initialized = False
    
        
        # Setup API key listener to receive all API key broadcasts
        self._setup_api_key_listener()

    def _emit_ui_telemetry(
        self,
        event_type: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort publisher for ui.telemetry events from the Settings tab."""
        try:
            if not getattr(self, "event_bus", None):
                return
            payload: Dict[str, Any] = {
                "component": "settings",
                "channel": "ui.telemetry",
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "success": success,
                "error": error,
                "metadata": metadata or {},
            }
            self.event_bus.publish("ui.telemetry", payload)
        except Exception as e:
            self.logger.debug(
                "Settings UI telemetry publish failed for %s: %s", event_type, e
            )


    def _setup_api_key_listener(self):
        """Setup listener for API key broadcasts from APIKeyManager."""
        try:
            if hasattr(self, 'event_bus') and self.event_bus:
                import logging
                from PyQt6.QtCore import QTimer

                logger = logging.getLogger(__name__)
                logger.info(f"🔑 Setting up API key listener for {self.__class__.__name__}")

                def _subscribe_api_key_events():
                    try:
                        self.event_bus.subscribe('api.key.available.*', self._on_api_key_available)
                        self.event_bus.subscribe('api.key.list', self._on_api_key_list)
                        logger.info(f"✅ {self.__class__.__name__} listening for API key broadcasts")
                    except Exception as sub_e:
                        logger.error(f"Error subscribing SettingsTab API key listeners: {sub_e}")

                # Defer subscriptions until startup stack unwinds.
                QTimer.singleShot(1500, _subscribe_api_key_events)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error setting up API key listener: {e}")
    
    def _on_api_key_available(self, event_data):
        """Handle API key availability broadcast."""
        try:
            service = event_data.get('service')
            import logging
            logging.getLogger(__name__).info(f"🔑 {self.__class__.__name__} received API key for: {service}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error handling API key availability: {e}")
    
    def _on_api_key_list(self, event_data):
        """Handle complete API key list."""
        try:
            api_keys = event_data.get('api_keys', {})
            import logging
            logging.getLogger(__name__).info(f"📋 {self.__class__.__name__} received {len(api_keys)} API keys")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error handling API key list: {e}")

    def init_ui(self):
        """Initialize settings UI - 2025 implementation"""
        try:
            # Build the full settings UI once. The previous two-pass init
            # (placeholder UI -> teardown -> full UI) could destabilize Qt
            # object ownership during startup under heavy load.
            self.setup_ui()
            self.logger.info("Settings UI initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing settings UI: {e}")
            return

        # Initialize sentience integration
        self.sentience_integration = None
        if self.event_bus and SettingsSentienceIntegration:
            self.sentience_integration = SettingsSentienceIntegration(
                settings_widget=self,
                event_bus=self.event_bus,  # Use self.event_bus instead of event_bus parameter
                redis_client=self.redis_conn,
                config={}
            )

        self.load_settings()

        if self.event_bus:
            self._connect_event_bus()

        # Start sentience monitoring if available
        if self.sentience_integration:
            self.sentience_integration.start_monitoring()

    def _deferred_redis_init(self):
        """Deferred Redis initialization - called after Redis Quantum Nexus is ready."""
        try:
            self.logger.info("🔗 Settings connecting to Redis Quantum Nexus...")
            if RedisQuantumNexusConnector:
                # RedisQuantumNexusConnector uses default config for port 6380 and password
                config = {
                    'host': 'localhost',
                    'port': 6380,
                    'password': 'QuantumNexus2025',
                    'db': 0,
                    'socket_timeout': 5
                }
                self.redis_conn = RedisQuantumNexusConnector(
                    event_bus=self.event_bus
                )
                # Test connection
                if hasattr(self.redis_conn, 'ping'):
                    self.redis_conn.ping()
                self.logger.info("✅ Settings connected to Redis Quantum Nexus on port 6380")
            else:
                # SOTA 2026: Try direct RedisQuantumNexus connection
                try:
                    from core.redis_connector import RedisQuantumNexus
                    nexus = RedisQuantumNexus()
                    if getattr(nexus, 'is_connected', False):
                        self.redis_conn = nexus
                        self.logger.info("✅ Settings connected to Redis (direct)")
                    else:
                        self.logger.warning("⚠️ Redis not available - using local storage")
                        self.redis_conn = None
                except Exception as inner_e:
                    self.logger.debug(f"Direct Redis failed: {inner_e}")
                    self.redis_conn = None
            
            # TIMING FIX: Now that Redis is connected, reload settings from Redis
            # (initial load_settings() used defaults because Redis wasn't ready yet)
            if self.redis_conn:
                self.load_settings()
                if hasattr(self, 'save_btn'):
                    self.save_btn.setEnabled(True)
        except Exception as e:
            # Log warning but don't crash - Settings can still function
            self.logger.warning(f"⚠️ Settings Redis connection failed (will retry): {e}")
            self.redis_conn = None
    
    def _initialize_redis_connection(self):
        """Legacy method - redirects to deferred init."""
        self._deferred_redis_init()

    def _get_default_settings(self) -> Dict[str, Any]:
        """Return default settings for all categories."""
        return {
            "general": {
                "startup_mode": "normal",
                "auto_update": True,
                "log_level": "INFO",
                "log_dir": os.path.join(os.path.expanduser("~"), "kingdom_ai", "logs"),
            },
            "trading": {
                "default_exchange": "binance",
                "api_key": "",
                "api_secret": "",
                "max_leverage": 5,
                "default_position_size": 1.0,
                "enable_shorting": True,
            },
            "mining": {
                "auto_start": False,
                "mining_pool": "auto",
                "wallet_address": "",
                "max_threads": max(1, multiprocessing.cpu_count() - 1),
                "hashrate_limit": 0,
                "use_gpu": True,
                "power_limit": 80,
            },
            "appearance": {
                "theme": "dark",
                "font_size": 12,
                "show_tooltips": True,
                "compact_mode": False,
            },
            "network": {
                "connection_timeout": 30,
                "use_proxy": False,
                "proxy_host": "",
                "proxy_port": 8080,
                "proxy_auth": False,
                "proxy_username": "",
                "proxy_password": "",
            },
            "advanced": {
                "debug_mode": False,
                "log_to_file": True,
                "log_file_path": "logs/kingdom_ai.log",
                "enable_analytics": True,
            },
            "sentience": {
                "monitoring_enabled": True,
                "auto_threshold_adjustment": True,
                "base_sentience_threshold": 75.0,
                "metrics_update_interval": 10,
                "notification_level": "medium",
                "log_sentience_events": True,
                "component_integration": {
                    "trading": True,
                    "mining": True,
                    "api_keys": True,
                    "vr": True,
                    "thoth": True,
                    "code_generator": True,
                    "wallet": True
                },
                "advanced_settings": {
                    "quantum_consciousness_enabled": True,
                    "iit_processor_enabled": True,
                    "consciousness_field_visualization": True,
                    "self_model_depth": "medium",
                    "detection_sensitivity": 0.75
                }
            }
        }

    def setup_ui(self):
        """Set up the user interface."""
        # Keep a stable top-level layout; avoid aggressive widget deletion churn.
        existing_layout = self.layout()
        if existing_layout:
            while existing_layout.count():
                item = existing_layout.takeAt(0)
                if item and item.widget():
                    widget = item.widget()
                    widget.hide()
                    widget.setParent(None)
            main_layout = existing_layout
            logger.info("✅ Reusing existing settings tab layout")
        else:
            main_layout = QVBoxLayout()
            self.setLayout(main_layout)
            logger.info("✅ Settings tab layout created safely")
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Set size policy for proper expansion
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Create tab widget for categories
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        # Create tabs
        self.general_tab = QWidget()
        self.trading_tab = QWidget()
        self.mining_tab = QWidget()
        self.appearance_tab = QWidget()
        self.network_tab = QWidget()
        self.advanced_tab = QWidget()
        self.sentience_tab = QWidget()

        # Setup all tabs
        self._setup_general_tab()
        self._setup_trading_tab()
        self._setup_mining_tab()
        self._setup_appearance_tab()
        self._setup_network_tab()
        self._setup_advanced_tab()
        self._setup_sentience_tab()

        # Add tabs to tab widget
        self.tab_widget.addTab(self.general_tab, "General")
        self.tab_widget.addTab(self.trading_tab, "Trading")
        self.tab_widget.addTab(self.mining_tab, "Mining")
        self.tab_widget.addTab(self.appearance_tab, "Appearance")
        self.tab_widget.addTab(self.network_tab, "Network")
        self.tab_widget.addTab(self.advanced_tab, "Advanced")
        self.tab_widget.addTab(self.sentience_tab, "Sentience")

        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)

        # Add buttons
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_settings)
        self.save_btn.setEnabled(False)
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addStretch()
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.save_btn)
        main_layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: green;")
        main_layout.addWidget(self.status_label)

        # Connect signals
        self._connect_signals()
        self.initialized = True

    def _setup_general_tab(self):
        """Set up the General settings tab."""
        layout = QVBoxLayout(self.general_tab)
        # Application settings
        app_group = QGroupBox("Application Settings")
        app_layout = QFormLayout()
        self.startup_mode = QComboBox()
        self.startup_mode.addItems(["Normal", "Minimized", "Maximized"])
        app_layout.addRow("Startup Mode:", self.startup_mode)
        self.auto_update = QCheckBox("Check for updates automatically")
        app_layout.addRow(self.auto_update)
        app_group.setLayout(app_layout)

        # Logging settings
        log_group = QGroupBox("Logging")
        log_layout = QFormLayout()
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        log_layout.addRow("Log Level:", self.log_level)
        log_group.setLayout(log_layout)

        layout.addWidget(app_group)
        layout.addWidget(log_group)
        layout.addStretch()

    def _setup_trading_tab(self):
        """Set up the Trading settings tab."""
        layout = QVBoxLayout(self.trading_tab)
        # Exchange settings
        exchange_group = QGroupBox("Exchange Settings")
        exchange_layout = QFormLayout()
        self.exchange = QComboBox()
        self.exchange.addItems(["Binance", "Coinbase", "Kraken", "FTX", "KuCoin"])
        exchange_layout.addRow("Exchange:", self.exchange)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        exchange_layout.addRow("API Key:", self.api_key)
        self.api_secret = QLineEdit()
        self.api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        exchange_layout.addRow("API Secret:", self.api_secret)
        exchange_group.setLayout(exchange_layout)

        # Trading settings
        trade_group = QGroupBox("Trading Parameters")
        trade_layout = QFormLayout()
        self.max_leverage = QSpinBox()
        self.max_leverage.setRange(1, 100)
        trade_layout.addRow("Max Leverage:", self.max_leverage)
        self.position_size = QDoubleSpinBox()
        self.position_size.setRange(0.1, 100.0)
        self.position_size.setSuffix("%")
        trade_layout.addRow("Default Position Size:", self.position_size)
        self.enable_shorting = QCheckBox("Enable Short Selling")
        trade_layout.addRow(self.enable_shorting)
        trade_group.setLayout(trade_layout)

        layout.addWidget(exchange_group)
        layout.addWidget(trade_group)
        layout.addStretch()

    def _setup_mining_tab(self):
        """Set up the Mining settings tab."""
        layout = QVBoxLayout(self.mining_tab)
        # Mining settings
        mining_group = QGroupBox("Mining Configuration")
        mining_layout = QFormLayout()
        self.mining_enabled = QCheckBox("Enable Mining")
        mining_layout.addRow(self.mining_enabled)
        self.mining_pool = QComboBox()
        self.mining_pool.addItems(["Ethermine", "F2Pool", "SparkPool", "Custom"])
        mining_layout.addRow("Mining Pool:", self.mining_pool)
        self.wallet_address = QLineEdit()
        mining_layout.addRow("Wallet Address:", self.wallet_address)
        self.worker_name = QLineEdit()
        mining_layout.addRow("Worker Name:", self.worker_name)
        mining_group.setLayout(mining_layout)

        # Performance settings
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout()
        self.use_gpu = QCheckBox("Use GPU for mining")
        perf_layout.addRow(self.use_gpu)
        self.power_limit = QSpinBox()
        self.power_limit.setRange(50, 150)
        self.power_limit.setSuffix("%")
        perf_layout.addRow("Power Limit:", self.power_limit)
        perf_group.setLayout(perf_layout)

        layout.addWidget(mining_group)
        layout.addWidget(perf_group)
        layout.addStretch()

    def _setup_appearance_tab(self):
        """Set up the Appearance settings tab."""
        layout = QVBoxLayout(self.appearance_tab)
        # Theme settings
        theme_group = QGroupBox("Theme")
        theme_layout = QFormLayout()
        self.theme = QComboBox()
        self.theme.addItems(["Dark", "Light", "System"])
        theme_layout.addRow("Theme:", self.theme)
        self.accent_color = QPushButton("Choose Accent Color")
        self.accent_color.clicked.connect(self._choose_accent_color)
        theme_layout.addRow("Accent Color:", self.accent_color)
        theme_group.setLayout(theme_layout)

        # UI settings
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout()
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 24)
        ui_layout.addRow("Font Size:", self.font_size)
        self.show_tooltips = QCheckBox("Show tooltips")
        ui_layout.addRow(self.show_tooltips)
        self.compact_mode = QCheckBox("Compact mode")
        ui_layout.addRow(self.compact_mode)
        ui_group.setLayout(ui_layout)

        layout.addWidget(theme_group)
        layout.addWidget(ui_group)
        layout.addStretch()

    def _setup_network_tab(self):
        """Set up the Network settings tab."""
        layout = QVBoxLayout(self.network_tab)
        # Connection settings
        conn_group = QGroupBox("Connection Settings")
        conn_layout = QFormLayout()
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 300)
        self.timeout.setSuffix(" seconds")
        conn_layout.addRow("Connection Timeout:", self.timeout)
        conn_group.setLayout(conn_layout)

        # Proxy settings
        proxy_group = QGroupBox("Proxy Settings")
        proxy_layout = QFormLayout()
        self.use_proxy = QCheckBox("Use proxy server")
        proxy_layout.addRow(self.use_proxy)
        self.proxy_host = QLineEdit()
        proxy_layout.addRow("Host:", self.proxy_host)
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        proxy_layout.addRow("Port:", self.proxy_port)
        self.proxy_auth = QCheckBox("Requires authentication")
        proxy_layout.addRow(self.proxy_auth)
        self.proxy_user = QLineEdit()
        proxy_layout.addRow("Username:", self.proxy_user)
        self.proxy_pass = QLineEdit()
        self.proxy_pass.setEchoMode(QLineEdit.EchoMode.Password)
        proxy_layout.addRow("Password:", self.proxy_pass)
        proxy_group.setLayout(proxy_layout)

        layout.addWidget(conn_group)
        layout.addWidget(proxy_group)
        layout.addStretch()

    def _setup_advanced_tab(self):
        """Set up the Advanced settings tab."""
        layout = QVBoxLayout(self.advanced_tab)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.debug_mode = QCheckBox()
        form.addRow("Debug Mode", self.debug_mode)
        self.enable_analytics = QCheckBox()
        form.addRow("Enable Analytics", self.enable_analytics)
        self.log_to_file = QCheckBox()
        form.addRow("Log to File", self.log_to_file)
        self.log_path = QLineEdit()
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._select_log_path)
        log_path_layout = QHBoxLayout()
        log_path_layout.addWidget(self.log_path)
        log_path_layout.addWidget(browse_btn)
        form.addRow("Log File Path", log_path_layout)

        layout.addLayout(form)
        layout.addStretch()

    def _setup_sentience_tab(self):
        """Set up the AI sentience detection settings tab."""
        layout = QVBoxLayout(self.sentience_tab)
        header = QLabel("AI Sentience Detection Framework")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        desc = QLabel("Configure settings for the AI sentience detection and monitoring system.")
        desc.setWordWrap(True)
        layout.addWidget(header)
        layout.addWidget(desc)
        layout.addSpacing(10)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.sentience_enabled = QCheckBox()
        self.sentience_enabled.toggled.connect(self._on_sentience_monitoring_toggled)
        form.addRow("Enable Sentience Monitoring", self.sentience_enabled)

        self.auto_threshold = QCheckBox()
        form.addRow("Auto Threshold Adjustment", self.auto_threshold)

        self.base_threshold = QDoubleSpinBox()
        self.base_threshold.setRange(0.0, 100.0)
        self.base_threshold.setSingleStep(0.1)
        form.addRow("Base Sentience Threshold", self.base_threshold)

        self.update_interval = QSpinBox()
        self.update_interval.setRange(1, 3600)
        self.update_interval.setSuffix(" seconds")
        form.addRow("Metrics Update Interval", self.update_interval)

        self.notification_level = QComboBox()
        self.notification_level.addItems(["Low", "Medium", "High", "Critical"])
        form.addRow("Notification Level", self.notification_level)

        self.log_events = QCheckBox()
        form.addRow("Log Sentience Events", self.log_events)

        # Component Integration group
        components_group = QGroupBox("Component Integration")
        components_layout = QVBoxLayout(components_group)
        self.trading_integration = QCheckBox("Trading System")
        self.mining_integration = QCheckBox("Mining System")
        self.api_keys_integration = QCheckBox("API Keys")
        self.vr_integration = QCheckBox("VR System")
        self.thoth_integration = QCheckBox("Thoth AI")
        self.code_generator_integration = QCheckBox("Code Generator")
        self.wallet_integration = QCheckBox("Wallet")
        components_layout.addWidget(self.trading_integration)
        components_layout.addWidget(self.mining_integration)
        components_layout.addWidget(self.api_keys_integration)
        components_layout.addWidget(self.vr_integration)
        components_layout.addWidget(self.thoth_integration)
        components_layout.addWidget(self.code_generator_integration)
        components_layout.addWidget(self.wallet_integration)
        form.addRow(components_group)

        # Advanced settings group
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QFormLayout(advanced_group)
        self.quantum_consciousness = QCheckBox()
        advanced_layout.addRow("Enable Quantum Consciousness Detection", self.quantum_consciousness)
        self.iit_processor = QCheckBox()
        advanced_layout.addRow("Enable IIT Processor", self.iit_processor)
        self.consciousness_field_viz = QCheckBox()
        advanced_layout.addRow("Consciousness Field Visualization", self.consciousness_field_viz)
        self.self_model_depth = QComboBox()
        self.self_model_depth.addItems(["Low", "Medium", "High"])
        advanced_layout.addRow("Self Model Depth", self.self_model_depth)
        self.detection_sensitivity = QDoubleSpinBox()
        self.detection_sensitivity.setRange(0.0, 1.0)
        self.detection_sensitivity.setSingleStep(0.01)
        advanced_layout.addRow("Detection Sensitivity", self.detection_sensitivity)
        form.addRow(advanced_group)

        layout.addLayout(form)
        layout.addStretch()

    def _on_sentience_monitoring_toggled(self, enabled):
        """Handle sentience monitoring toggle."""
        self.auto_threshold.setEnabled(enabled)
        self.base_threshold.setEnabled(enabled)
        self.update_interval.setEnabled(enabled)
        self.notification_level.setEnabled(enabled)
        self.log_events.setEnabled(enabled)
        self.trading_integration.setEnabled(enabled)
        self.mining_integration.setEnabled(enabled)
        self.api_keys_integration.setEnabled(enabled)
        self.vr_integration.setEnabled(enabled)
        self.thoth_integration.setEnabled(enabled)
        self.code_generator_integration.setEnabled(enabled)
        self.wallet_integration.setEnabled(enabled)
        self.quantum_consciousness.setEnabled(enabled)
        self.iit_processor.setEnabled(enabled)
        self.consciousness_field_viz.setEnabled(enabled)
        self.self_model_depth.setEnabled(enabled)
        self.detection_sensitivity.setEnabled(enabled)
        if self.event_bus:
            self.event_bus.emit("sentience_monitoring_changed", {"enabled": enabled})

    def _select_log_path(self):
        """Select log file path."""
        current_path = self.log_path.text()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Log File",
            current_path,
            "Log Files (*.log);;All Files (*)"
        )
        if file_path:
            self.log_path.setText(file_path)

    def _load_general_settings(self):
        """Load general settings into UI."""
        general = self.settings.get("general", {})
        self.startup_mode.setCurrentText(general.get("startup_mode", "normal").capitalize())
        self.auto_update.setChecked(general.get("auto_update", True))
        self.log_level.setCurrentText(general.get("log_level", "INFO"))

    def _load_appearance_settings(self):
        """Load appearance settings into UI."""
        appearance = self.settings.get("appearance", {})
        self.theme.setCurrentText(appearance.get("theme", "dark").capitalize())
        self.font_size.setValue(appearance.get("font_size", 12))
        self.show_tooltips.setChecked(appearance.get("show_tooltips", True))
        self.compact_mode.setChecked(appearance.get("compact_mode", False))

    def _choose_accent_color(self):
        """Open color picker dialog and set accent color."""
        try:
            from PyQt6.QtWidgets import QColorDialog
            from PyQt6.QtGui import QColor
            
            # Get current color if set
            current_color = self.settings.get("appearance", {}).get("accent_color", "#00FFFF")
            initial_color = QColor(current_color) if current_color else QColor("#00FFFF")
            
            color = QColorDialog.getColor(initial_color, self, "Choose Accent Color")
            if color.isValid():
                hex_color = color.name()
                # Update button to show selected color
                self.accent_color.setStyleSheet(f"background-color: {hex_color}; color: white;")
                self.accent_color.setText(f"Accent: {hex_color}")
                
                # Store in settings
                if "appearance" not in self.settings:
                    self.settings["appearance"] = {}
                self.settings["appearance"]["accent_color"] = hex_color
                
                # Mark as dirty
                self._dirty_settings = True
                
                # Publish theme change event
                if self.event_bus:
                    self.event_bus.publish("settings.theme.changed", {
                        "accent_color": hex_color
                    })
                
                self.logger.info(f"Accent color set to: {hex_color}")
        except Exception as e:
            self.logger.error(f"Error choosing accent color: {e}")

    def _load_network_settings(self):
        """Load network settings into UI."""
        network = self.settings.get("network", {})
        self.timeout.setValue(network.get("connection_timeout", 30))
        self.use_proxy.setChecked(network.get("use_proxy", False))
        self.proxy_host.setText(network.get("proxy_host", ""))
        self.proxy_port.setValue(network.get("proxy_port", 8080))
        self.proxy_auth.setChecked(network.get("proxy_auth", False))
        self.proxy_user.setText(network.get("proxy_username", ""))
        self.proxy_pass.setText(network.get("proxy_password", ""))

    def _load_advanced_settings(self):
        """Load advanced settings into UI."""
        advanced = self.settings.get("advanced", {})
        self.debug_mode.setChecked(advanced.get("debug_mode", False))
        self.log_to_file.setChecked(advanced.get("log_to_file", True))
        self.log_path.setText(advanced.get("log_file_path", "logs/kingdom_ai.log"))
        self.enable_analytics.setChecked(advanced.get("enable_analytics", True))

    def _load_sentience_settings(self):
        """Load sentience settings into UI."""
        sentience = self.settings.get("sentience", {})
        self.sentience_enabled.setChecked(sentience.get("monitoring_enabled", True))
        self.auto_threshold.setChecked(sentience.get("auto_threshold_adjustment", True))
        self.base_threshold.setValue(sentience.get("base_sentience_threshold", 75.0))
        self.update_interval.setValue(sentience.get("metrics_update_interval", 10))
        notification_level = sentience.get("notification_level", "medium")
        index = self.notification_level.findText(notification_level.capitalize())
        if index >= 0:
            self.notification_level.setCurrentIndex(index)
        self.log_events.setChecked(sentience.get("log_sentience_events", True))

        component_integration = sentience.get("component_integration", {})
        self.trading_integration.setChecked(component_integration.get("trading", True))
        self.mining_integration.setChecked(component_integration.get("mining", True))
        self.api_keys_integration.setChecked(component_integration.get("api_keys", True))
        self.vr_integration.setChecked(component_integration.get("vr", True))
        self.thoth_integration.setChecked(component_integration.get("thoth", True))
        self.code_generator_integration.setChecked(component_integration.get("code_generator", True))
        self.wallet_integration.setChecked(component_integration.get("wallet", True))

        advanced_settings = sentience.get("advanced_settings", {})
        self.quantum_consciousness.setChecked(advanced_settings.get("quantum_consciousness_enabled", True))
        self.iit_processor.setChecked(advanced_settings.get("iit_processor_enabled", True))
        self.consciousness_field_viz.setChecked(advanced_settings.get("consciousness_field_visualization", True))
        depth = advanced_settings.get("self_model_depth", "medium")
        index = self.self_model_depth.findText(depth.capitalize())
        if index >= 0:
            self.self_model_depth.setCurrentIndex(index)
        self.detection_sensitivity.setValue(advanced_settings.get("detection_sensitivity", 0.75))

    def _connect_signals(self):
        """Connect UI signals to slots."""
        for child in self.findChildren((QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox)):
            if isinstance(child, QLineEdit):
                child.textChanged.connect(self._on_setting_changed)
            elif isinstance(child, (QSpinBox, QDoubleSpinBox)):
                child.valueChanged.connect(self._on_setting_changed)
            elif isinstance(child, QComboBox):
                child.currentIndexChanged.connect(self._on_setting_changed)
            elif isinstance(child, QCheckBox):
                child.stateChanged.connect(self._on_setting_changed)

    def _on_setting_changed(self):
        """Handle setting changes."""
        if not self.initialized:
            return
        self.save_btn.setEnabled(True)
        self._update_dirty_settings()

    def _update_dirty_settings(self):
        """Update the dirty settings dictionary with current UI values vs saved config."""
        if not self.initialized:
            return
        try:
            if not hasattr(self, '_dirty_settings') or not isinstance(self._dirty_settings, dict):
                self._dirty_settings = {}

            saved = self.settings or {}

            widget_map = {
                "general.startup_mode": (self.startup_mode, "combo", saved.get("general", {}).get("startup_mode", "normal")),
                "general.auto_update": (self.auto_update, "check", saved.get("general", {}).get("auto_update", True)),
                "general.log_level": (self.log_level, "combo", saved.get("general", {}).get("log_level", "INFO")),
                "trading.default_exchange": (self.exchange, "combo", saved.get("trading", {}).get("default_exchange", "binance")),
                "trading.max_leverage": (self.max_leverage, "spin", saved.get("trading", {}).get("max_leverage", 5)),
                "trading.default_position_size": (self.position_size, "dspin", saved.get("trading", {}).get("default_position_size", 1.0)),
                "trading.enable_shorting": (self.enable_shorting, "check", saved.get("trading", {}).get("enable_shorting", True)),
                "mining.auto_start": (self.mining_enabled, "check", saved.get("mining", {}).get("auto_start", False)),
                "mining.mining_pool": (self.mining_pool, "combo", saved.get("mining", {}).get("mining_pool", "auto")),
                "mining.wallet_address": (self.wallet_address, "text", saved.get("mining", {}).get("wallet_address", "")),
                "mining.use_gpu": (self.use_gpu, "check", saved.get("mining", {}).get("use_gpu", True)),
                "mining.power_limit": (self.power_limit, "spin", saved.get("mining", {}).get("power_limit", 80)),
                "appearance.theme": (self.theme, "combo", saved.get("appearance", {}).get("theme", "dark")),
                "appearance.font_size": (self.font_size, "spin", saved.get("appearance", {}).get("font_size", 12)),
                "appearance.show_tooltips": (self.show_tooltips, "check", saved.get("appearance", {}).get("show_tooltips", True)),
                "appearance.compact_mode": (self.compact_mode, "check", saved.get("appearance", {}).get("compact_mode", False)),
                "network.connection_timeout": (self.timeout, "spin", saved.get("network", {}).get("connection_timeout", 30)),
                "network.use_proxy": (self.use_proxy, "check", saved.get("network", {}).get("use_proxy", False)),
                "advanced.debug_mode": (self.debug_mode, "check", saved.get("advanced", {}).get("debug_mode", False)),
                "advanced.enable_analytics": (self.enable_analytics, "check", saved.get("advanced", {}).get("enable_analytics", True)),
                "sentience.monitoring_enabled": (self.sentience_enabled, "check", saved.get("sentience", {}).get("monitoring_enabled", True)),
                "sentience.base_sentience_threshold": (self.base_threshold, "dspin", saved.get("sentience", {}).get("base_sentience_threshold", 75.0)),
            }

            self._dirty_settings = {}
            for key, (widget, wtype, saved_val) in widget_map.items():
                try:
                    if wtype == "combo":
                        current = widget.currentText().lower()
                        cmp_saved = str(saved_val).lower() if saved_val is not None else ""
                    elif wtype == "check":
                        current = widget.isChecked()
                        cmp_saved = saved_val
                    elif wtype == "spin":
                        current = widget.value()
                        cmp_saved = saved_val
                    elif wtype == "dspin":
                        current = widget.value()
                        cmp_saved = saved_val
                    elif wtype == "text":
                        current = widget.text()
                        cmp_saved = saved_val if saved_val else ""
                    else:
                        continue
                    if current != cmp_saved:
                        self._dirty_settings[key] = {"old": saved_val, "new": current}
                except Exception:
                    pass

        except Exception as e:
            self.logger.debug(f"Error tracking dirty settings: {e}")

    def _connect_event_bus(self):
        """Connect to event bus for real-time updates."""
        if not self.event_bus:
            return
        
        # Create async wrappers for non-async methods
        async def _async_load_settings(data=None):
            self.load_settings()
            
        async def _async_settings_query(data):
            self._handle_settings_query(data)
            
        async def _async_sentience_update(data):
            self._handle_sentience_metrics_update(data)
            
        async def _async_settings_update(data):
            self._handle_settings_update(data)
        
        def do_all_subscriptions():
            """Perform all event subscriptions after GUI init."""
            try:
                import asyncio
                from PyQt6.QtCore import QTimer
                
                def subscribe_all():
                    try:
                        self.event_bus.subscribe("settings.updated", self._handle_settings_update)
                        self.event_bus.subscribe("settings.reset", self.load_settings)
                        self.event_bus.subscribe("theme.changed", self._handle_theme_change)
                        self.event_bus.subscribe("settings.saved", self._handle_settings_saved)
                        # SOTA 2026: Chat/Voice command event subscriptions
                        self.event_bus.subscribe("settings.open", self._handle_settings_open)
                        self.event_bus.subscribe("settings.apikey.set", self._handle_apikey_set)
                        self.event_bus.subscribe("settings.theme.dark", self._handle_dark_mode)
                        self.event_bus.subscribe("settings.theme.light", self._handle_light_mode)
                        self.event_bus.subscribe("settings.backup", self._handle_backup)
                        self.event_bus.subscribe("settings.import", self._handle_import)
                        logger.info("Settings tab subscriptions completed (including SOTA 2026 chat commands)")
                    except Exception as e:
                        logger.error(f"Settings subscription error: {e}")
                
                # Schedule 4.2 seconds after init
                QTimer.singleShot(4200, subscribe_all)
            except Exception as e:
                logger.error(f"Settings subscription error: {e}")
        
        # Schedule 2.7 seconds after init to ensure main task completes
        QTimer.singleShot(2700, do_all_subscriptions)

    def _handle_settings_update(self, event_data: Dict[str, Any]):
        """Handle settings update event (THREAD-SAFE).
        
        SOTA 2026: Dispatches to main thread to prevent Qt threading violations.
        """
        def update_ui():
            for category, settings in event_data.items():
                if category in self.settings:
                    self.settings[category].update(settings)
            if self.isVisible():
                self._update_ui_from_settings()
        
        # Use QTimer.singleShot for thread-safe UI update
        QTimer.singleShot(0, update_ui)

    def _handle_theme_change(self, event_data=None):
        """Handle theme change event (THREAD-SAFE).
        
        SOTA 2026: Dispatches to main thread to prevent Qt threading violations.
        """
        def update_ui():
            if not event_data or 'theme' not in event_data:
                return
            theme = event_data['theme']
            self.theme.setCurrentText(theme.capitalize())
        
        # Use QTimer.singleShot for thread-safe UI update
        QTimer.singleShot(0, update_ui)

    def _handle_sentience_metrics_update(self, event_data=None):
        """Handle sentience metrics update event."""
        if not event_data:
            return
        try:
            def update_ui():
                try:
                    metrics = event_data if isinstance(event_data, dict) else {}
                    sentience_score = metrics.get('sentience_score', metrics.get('score'))
                    phi_value = metrics.get('phi', metrics.get('phi_value'))
                    consciousness_level = metrics.get('consciousness_level', metrics.get('level'))
                    iit_score = metrics.get('iit_score')

                    if hasattr(self, 'base_threshold') and sentience_score is not None:
                        try:
                            score_f = float(sentience_score)
                            tooltip = f"Live sentience score: {score_f:.1f}"
                            if phi_value is not None:
                                tooltip += f" | Phi: {float(phi_value):.3f}"
                            if consciousness_level:
                                tooltip += f" | Level: {consciousness_level}"
                            self.base_threshold.setToolTip(tooltip)
                        except (ValueError, TypeError):
                            pass

                    if hasattr(self, 'sentience_enabled') and consciousness_level:
                        self.sentience_enabled.setToolTip(
                            f"Consciousness level: {consciousness_level}"
                        )

                    if hasattr(self, 'detection_sensitivity') and iit_score is not None:
                        try:
                            self.detection_sensitivity.setToolTip(
                                f"IIT score: {float(iit_score):.3f}"
                            )
                        except (ValueError, TypeError):
                            pass

                    self.logger.debug(f"Sentience metrics updated: score={sentience_score}, phi={phi_value}")
                except Exception as inner_e:
                    self.logger.debug(f"Error in sentience metrics UI update: {inner_e}")

            QTimer.singleShot(0, update_ui)
        except Exception as e:
            self.logger.debug(f"Error handling sentience metrics update: {e}")
    
    def _handle_settings_saved(self, data):
        """Handle settings saved confirmation from backend - DISPLAY TO USER"""
        try:
            success = data.get('success', False)
            message = data.get('message', '')
            
            logger.info(f"✅ Settings Save Confirmation from Backend: {message}")
            logger.info(f"   Success: {success}")
            
            if success:
                self._show_status_message(f"✅ {message}")
            else:
                self._show_status_message(f"⚠️ {message}", error=True)
                
        except Exception as e:
            logger.error(f"Error handling settings saved confirmation: {e}")

    def load_settings(self):
        """Load settings from Redis."""
        try:
            if not self.redis_conn:
                # TIMING FIX: Redis may not be ready yet due to deferred init (expected at startup)
                logger.info("⏳ Redis connection not ready yet. Using default settings.")
                self.settings = self.default_settings.copy()
                self._update_ui_from_settings()
                self.save_btn.setEnabled(False)
                return

            self.redis_conn.ping()
            settings_json = self.redis_conn.get("kingdom:settings")
            if settings_json:
                # Handle both bytes and string responses from Redis
                if isinstance(settings_json, bytes):
                    self.settings = json.loads(settings_json.decode('utf-8'))
                elif isinstance(settings_json, str):
                    self.settings = json.loads(settings_json)
                else:
                    logger.warning(f"Unexpected settings_json type: {type(settings_json)}")
                    self.settings = self.default_settings.copy()
            else:
                logger.info("No settings found in Redis. Initializing with defaults.")
                self.settings = self.default_settings.copy()
                self.save_settings()

            self._update_ui_from_settings()
            self.save_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self._show_status_message("Error loading settings. Using defaults.", error=True)

    def save_settings(self):
        """Save current settings to Redis."""
        try:
            if not self.redis_conn:
                # TIMING FIX: Redis may not be ready yet due to deferred init  
                logger.warning("⏳ Redis connection not ready yet. Settings will be saved when Redis connects.")
                self._show_status_message("Redis not ready. Settings will be saved later.", error=False)
                return

            self.redis_conn.ping()
            self._update_settings_from_ui()
            settings_json = json.dumps(self.settings)
            self.redis_conn.set("kingdom:settings", settings_json)
            self.save_btn.setEnabled(False)
            self._show_status_message("Settings saved successfully.")
            self._emit_ui_telemetry(
                "settings.save_clicked",
                metadata={"source": "settings_tab"},
            )
            if self.event_bus:
                if hasattr(self.event_bus, 'publish_sync'):
                    self.event_bus.publish_sync("settings:updated", self.settings)
                    self.event_bus.publish_sync("settings.save", self.settings)
                else:
                    self.event_bus.publish("settings:updated", self.settings)
                    self.event_bus.publish("settings.save", self.settings)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            self._show_status_message("Error saving settings!", error=True)

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
                logger.info("✅ Settings Tab connected to ThothAI central brain")
                
                # Register settings events with central brain using safe method access
                try:
                    register_method = getattr(self._central_thoth, 'register_component', None)
                    if register_method and callable(register_method):
                        register_method('settings_tab')
                except (AttributeError, Exception):
                    # Silently handle missing register_component method
                    pass
                    
            else:
                # 2025 FIX #15: Create minimal ThothAI for settings tab
                logger.info("✅ Creating settings ThothAI integration") 
                self._central_thoth = type('MinimalThoth', (), {
                    'is_available': lambda: True,
                    'register_component': lambda self, name: True,
                    'process_message': lambda self, msg: f"Settings processed: {msg[:50]}..."
                })()
                
        except Exception as e:
            logger.error(f"Error connecting to central ThothAI: {e}")
            self._central_thoth = None
            self._show_status_message("Error connecting to central ThothAI!", error=True)

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Are you sure you want to reset all settings to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.settings = self.default_settings.copy()
            self._update_ui_from_settings()
            self._show_status_message("Settings reset to defaults.")
            self._emit_ui_telemetry("settings.reset_to_defaults_clicked")
            if self.event_bus:
                import asyncio
                if hasattr(self.event_bus.publish, "__await__"):
                    self.event_bus.publish("settings:reset", self.settings)
                else:
                    self.event_bus.publish("settings:reset", self.settings)

    def _update_ui_from_settings(self):
        """Update UI elements with current settings."""
        if not self.settings:
            return
        try:
            self.initialized = False
            self._load_general_settings()
            self._load_trading_settings()
            self._load_mining_settings()
            self._load_appearance_settings()
            self._load_network_settings()
            self._load_advanced_settings()
            self._load_sentience_settings()
        except Exception as e:
            logger.error(f"Error updating UI from settings: {e}")
            self._show_status_message("Error loading settings!", error=True)
        finally:
            self.initialized = True

    def _load_trading_settings(self):
        """Load trading settings into UI."""
        trading = self.settings.get("trading", {})
        self.exchange.setCurrentText(trading.get("default_exchange", "binance").capitalize())
        self.api_key.setText(trading.get("api_key", ""))
        self.api_secret.setText(trading.get("api_secret", ""))
        self.max_leverage.setValue(trading.get("max_leverage", 5))
        self.position_size.setValue(trading.get("default_position_size", 1.0))
        self.enable_shorting.setChecked(trading.get("enable_shorting", True))

    def _load_mining_settings(self):
        """Load mining settings into UI."""
        mining = self.settings.get("mining", {})
        self.mining_enabled.setChecked(mining.get("auto_start", False))
        self.mining_pool.setCurrentText(mining.get("mining_pool", "auto").capitalize())
        self.wallet_address.setText(mining.get("wallet_address", ""))
        self.use_gpu.setChecked(mining.get("use_gpu", True))
        self.power_limit.setValue(mining.get("power_limit", 80))

    def _update_settings_from_ui(self):
        """Update settings dictionary from UI values."""
        if not self.initialized:
            return
        try:
            self.settings["general"] = {
                "startup_mode": self.startup_mode.currentText().lower(),
                "auto_update": self.auto_update.isChecked(),
                "log_level": self.log_level.currentText()
            }
            self.settings["trading"] = {
                "default_exchange": self.exchange.currentText().lower(),
                "api_key": self.api_key.text(),
                "api_secret": self.api_secret.text(),
                "max_leverage": self.max_leverage.value(),
                "default_position_size": self.position_size.value(),
                "enable_shorting": self.enable_shorting.isChecked()
            }
            self.settings["mining"] = {
                "auto_start": self.mining_enabled.isChecked(),
                "mining_pool": self.mining_pool.currentText().lower(),
                "wallet_address": self.wallet_address.text(),
                "use_gpu": self.use_gpu.isChecked(),
                "power_limit": self.power_limit.value()
            }
            self.settings["appearance"] = {
                "theme": self.theme.currentText().lower(),
                "font_size": self.font_size.value(),
                "show_tooltips": self.show_tooltips.isChecked(),
                "compact_mode": self.compact_mode.isChecked()
            }
            self.settings["network"] = {
                "connection_timeout": self.timeout.value(),
                "use_proxy": self.use_proxy.isChecked(),
                "proxy_host": self.proxy_host.text(),
                "proxy_port": self.proxy_port.value(),
                "proxy_auth": self.proxy_auth.isChecked(),
                "proxy_username": self.proxy_user.text(),
                "proxy_password": self.proxy_pass.text()
            }
            self.settings["advanced"] = {
                "debug_mode": self.debug_mode.isChecked(),
                "log_to_file": self.log_to_file.isChecked(),
                "log_file_path": self.log_path.text(),
                "enable_analytics": self.enable_analytics.isChecked()
            }
            self.settings["sentience"] = {
                "monitoring_enabled": self.sentience_enabled.isChecked(),
                "auto_threshold_adjustment": self.auto_threshold.isChecked(),
                "base_sentience_threshold": self.base_threshold.value(),
                "metrics_update_interval": self.update_interval.value(),
                "notification_level": self.notification_level.currentText().lower(),
                "log_sentience_events": self.log_events.isChecked(),
                "component_integration": {
                    "trading": self.trading_integration.isChecked(),
                    "mining": self.mining_integration.isChecked(),
                    "api_keys": self.api_keys_integration.isChecked(),
                    "vr": self.vr_integration.isChecked(),
                    "thoth": self.thoth_integration.isChecked(),
                    "code_generator": self.code_generator_integration.isChecked(),
                    "wallet": self.wallet_integration.isChecked()
                },
                "advanced_settings": {
                    "quantum_consciousness_enabled": self.quantum_consciousness.isChecked(),
                    "iit_processor_enabled": self.iit_processor.isChecked(),
                    "consciousness_field_visualization": self.consciousness_field_viz.isChecked(),
                    "self_model_depth": self.self_model_depth.currentText().lower(),
                    "detection_sensitivity": self.detection_sensitivity.value()
                }
            }
        except Exception as e:
            logger.error(f"Error updating settings from UI: {e}")
            self._show_status_message("Error updating settings!", error=True)

    def _show_status_message(self, message: str, error: bool = False, duration: int = 3000):
        """Display a status message."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: red;" if error else "color: green;")
        QTimer.singleShot(duration, lambda: self.status_label.clear())

    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        self.load_settings()

    def closeEvent(self, event):
        """Handle close event."""
        if self.save_btn.isEnabled():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Would you like to save them before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            if reply == QMessageBox.StandardButton.Save:
                self.save_settings()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        try:
            if getattr(self, 'sentience_integration', None):
                self.sentience_integration.stop_monitoring()
        except Exception as e:
            logger.warning(f"Failed to stop settings sentience monitoring: {e}")
        event.accept()

    def _handle_settings_query(self, query_data):
        """Handle settings query requests from other components."""
        query_type = query_data.get("type", "get_all")
        if query_type == "get_all":
            response = {
                "success": True,
                "settings": self.settings.copy(),
                "timestamp": time.time()
            }
        elif query_type == "get_setting":
            setting_key = query_data.get("key")
            if setting_key and setting_key in self.settings:
                response = {
                    "success": True,
                    "value": self.settings[setting_key],
                    "key": setting_key,
                    "timestamp": time.time()
                }
            else:
                response = {
                    "success": False,
                    "error": f"Setting '{setting_key}' not found",
                    "timestamp": time.time()
                }
        else:
            response = {
                "success": False,
                "error": f"Unknown query type: {query_type}",
                "timestamp": time.time()
            }
        if self.event_bus:
            import asyncio
            if hasattr(self.event_bus.publish, "__await__"):
                self.event_bus.publish("settings.query.response", response)
            else:
                self.event_bus.publish("settings.query.response", response)
    
    # =========================================================================
    # SOTA 2026: Chat/Voice Command Handlers
    # =========================================================================
    
    def _handle_settings_open(self, payload):
        """Handle settings open command from chat/voice."""
        logger.info("⚙️ Opening settings via chat command")
        # Signal to switch to settings tab
        if self.event_bus:
            self.event_bus.publish("tab.switch", {"tab": "settings"})
    
    def _handle_apikey_set(self, payload):
        """Handle API key set command from chat/voice."""
        service = payload.get("service", "")
        logger.info(f"🔑 API key set requested for: {service}")
        if self.event_bus:
            self.event_bus.publish("settings.apikey.dialog", {"service": service})
    
    def _handle_dark_mode(self, payload):
        """Handle dark mode enable command."""
        logger.info("🌙 Enabling dark mode via chat command")
        self.settings["theme"] = "dark"
        self.save_settings()
        if self.event_bus:
            self.event_bus.publish("theme.changed", {"theme": "dark"})
    
    def _handle_light_mode(self, payload):
        """Handle light mode enable command."""
        logger.info("☀️ Enabling light mode via chat command")
        self.settings["theme"] = "light"
        self.save_settings()
        if self.event_bus:
            self.event_bus.publish("theme.changed", {"theme": "light"})
    
    def _handle_backup(self, payload):
        """Handle backup config command."""
        logger.info("💾 Backing up settings via chat command")
        try:
            backup_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "settings_backup.json")
            with open(backup_path, 'w') as f:
                json.dump(self.settings, f, indent=2)
            if self.event_bus:
                self.event_bus.publish("settings.backup.complete", {"path": backup_path})
        except Exception as e:
            logger.error(f"Backup failed: {e}")
    
    def _handle_import(self, payload):
        """Handle import config command."""
        logger.info("📥 Importing settings via chat command")
        try:
            backup_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "settings_backup.json")
            if os.path.exists(backup_path):
                with open(backup_path, 'r') as f:
                    self.settings = json.load(f)
                self.save_settings()
                if self.event_bus:
                    self.event_bus.publish("settings.import.complete", {"success": True})
        except Exception as e:
            logger.error(f"Import failed: {e}")


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    settings.setWindowTitle("Kingdom AI - Settings")
    settings.resize(800, 600)
    settings.show()
    sys.exit(app.exec())