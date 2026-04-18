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
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, 
    QLineEdit, QPushButton, QCheckBox, QSpinBox, QComboBox,
    QGroupBox, QFormLayout, QScrollArea, QMessageBox,
    QSlider, QTextEdit, QSplitter
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QPalette, QColor

logger = logging.getLogger("KingdomAI.GUI.SettingsTab")

try:
    from core.sentience.settings_sentience_integration import SettingsSentienceIntegration
except ImportError:
    logger.warning("SettingsSentienceIntegration not available")
    SettingsSentienceIntegration = None

try:
    from core.redis_connector import RedisQuantumNexusConnector
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
        
        # Initialize Redis connection - use provided or create new Quantum Nexus connection
        if redis_conn:
            self.redis_conn = redis_conn
        else:
            # Initialize Redis Quantum Nexus connection like successful tabs
            self._initialize_redis_connection()
            
        self.settings = {}
        self.default_settings = self._get_default_settings()
        self.dirty_settings = {}
        self.initialized = False
        
        # Initialize sentience integration
        self.sentience_integration = None
        if self.event_bus:
            self.sentience_integration = SettingsSentienceIntegration(
                settings_widget=self,
                event_bus=event_bus,
                redis_client=self.redis_conn,
                config={},
            )
            
        self.setup_ui()
        self.load_settings()
        
        if self.event_bus:
            self._connect_event_bus()
            
        # Start sentience monitoring if available
        if self.sentience_integration:
            self.sentience_integration.start_monitoring()

    def _initialize_redis_connection(self):
        """Initialize Redis Quantum Nexus connection with strict enforcement."""
        try:
            if RedisQuantumNexusConnector:
                self.redis_conn = RedisQuantumNexusConnector(
                    host='localhost',
                    port=6380,
                    password='QuantumNexus2025',
                    decode_responses=True
                )
                # Test connection
                self.redis_conn.ping()
                logger.info("✅ Redis Quantum Nexus connection established on port 6380")
            else:
                logger.critical("❌ CRITICAL: RedisQuantumNexusConnector not available")
                raise ImportError("Redis Quantum Nexus connector required")
        except Exception as e:
            logger.critical(f"❌ CRITICAL: Failed to connect to Redis Quantum Nexus: {e}")
            logger.critical("❌ SYSTEM HALT: Redis connection is MANDATORY")
            raise SystemExit("Redis Quantum Nexus connection failed - system cannot continue")

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Create tab widget for different settings categories
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create settings tabs
        self._create_general_tab()
        self._create_trading_tab()
        self._create_blockchain_tab()
        self._create_ai_tab()
        self._create_mining_tab()
        self._create_security_tab()
        self._create_advanced_tab()
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(self.reset_button)
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _create_general_tab(self):
        """Create general settings tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # Application settings
        app_group = QGroupBox("Application Settings")
        app_layout = QFormLayout(app_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "Cyberpunk", "Auto"])
        app_layout.addRow("Theme:", self.theme_combo)
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Spanish", "French", "German", "Chinese"])
        app_layout.addRow("Language:", self.language_combo)
        
        self.auto_save_checkbox = QCheckBox("Auto-save settings")
        app_layout.addRow(self.auto_save_checkbox)
        
        layout.addWidget(app_group)
        
        # Logging settings
        log_group = QGroupBox("Logging Settings")
        log_layout = QFormLayout(log_group)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        log_layout.addRow("Log Level:", self.log_level_combo)
        
        self.log_to_file_checkbox = QCheckBox("Log to file")
        log_layout.addRow(self.log_to_file_checkbox)
        
        layout.addWidget(log_group)
        
        self.tab_widget.addTab(tab, "General")

    def _create_trading_tab(self):
        """Create trading settings tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # Trading parameters
        trading_group = QGroupBox("Trading Parameters")
        trading_layout = QFormLayout(trading_group)
        
        self.max_position_size = QSpinBox()
        self.max_position_size.setRange(1, 1000000)
        self.max_position_size.setValue(10000)
        trading_layout.addRow("Max Position Size:", self.max_position_size)
        
        self.risk_percentage = QSpinBox()
        self.risk_percentage.setRange(1, 100)
        self.risk_percentage.setValue(2)
        trading_layout.addRow("Risk Percentage:", self.risk_percentage)
        
        self.stop_loss_percentage = QSpinBox()
        self.stop_loss_percentage.setRange(1, 50)
        self.stop_loss_percentage.setValue(5)
        trading_layout.addRow("Stop Loss %:", self.stop_loss_percentage)
        
        layout.addWidget(trading_group)
        
        # Exchange settings
        exchange_group = QGroupBox("Exchange Settings")
        exchange_layout = QFormLayout(exchange_group)
        
        self.default_exchange = QComboBox()
        self.default_exchange.addItems(["Binance", "Coinbase", "Kraken", "KuCoin"])
        exchange_layout.addRow("Default Exchange:", self.default_exchange)
        
        self.trading_pairs = QTextEdit()
        self.trading_pairs.setMaximumHeight(100)
        exchange_layout.addRow("Trading Pairs:", self.trading_pairs)
        
        layout.addWidget(exchange_group)
        
        self.tab_widget.addTab(tab, "Trading")

    def _create_blockchain_tab(self):
        """Create blockchain settings tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # Network settings
        network_group = QGroupBox("Network Settings")
        network_layout = QFormLayout(network_group)
        
        self.default_network = QComboBox()
        self.default_network.addItems(["Ethereum", "BSC", "Polygon", "Avalanche", "Arbitrum"])
        network_layout.addRow("Default Network:", self.default_network)
        
        self.gas_limit = QSpinBox()
        self.gas_limit.setRange(21000, 1000000)
        self.gas_limit.setValue(100000)
        network_layout.addRow("Gas Limit:", self.gas_limit)
        
        self.gas_price_gwei = QSpinBox()
        self.gas_price_gwei.setRange(1, 1000)
        self.gas_price_gwei.setValue(20)
        network_layout.addRow("Gas Price (Gwei):", self.gas_price_gwei)
        
        layout.addWidget(network_group)
        
        # RPC settings
        rpc_group = QGroupBox("RPC Settings")
        rpc_layout = QFormLayout(rpc_group)
        
        self.rpc_timeout = QSpinBox()
        self.rpc_timeout.setRange(5, 120)
        self.rpc_timeout.setValue(30)
        rpc_layout.addRow("RPC Timeout (s):", self.rpc_timeout)
        
        self.max_retries = QSpinBox()
        self.max_retries.setRange(1, 10)
        self.max_retries.setValue(3)
        rpc_layout.addRow("Max Retries:", self.max_retries)
        
        layout.addWidget(rpc_group)
        
        self.tab_widget.addTab(tab, "Blockchain")

    def _create_ai_tab(self):
        """Create AI settings tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # AI model settings
        ai_group = QGroupBox("AI Model Settings")
        ai_layout = QFormLayout(ai_group)
        
        self.ai_model = QComboBox()
        self.ai_model.addItems(["GPT-4", "Claude-3", "Llama-2", "Local Model"])
        ai_layout.addRow("AI Model:", self.ai_model)
        
        self.ai_temperature = QSlider(Qt.Orientation.Horizontal)
        self.ai_temperature.setRange(0, 100)
        self.ai_temperature.setValue(70)
        ai_layout.addRow("Temperature:", self.ai_temperature)
        
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(100, 8000)
        self.max_tokens.setValue(2000)
        ai_layout.addRow("Max Tokens:", self.max_tokens)
        
        layout.addWidget(ai_group)
        
        # Voice settings
        voice_group = QGroupBox("Voice Settings")
        voice_layout = QFormLayout(voice_group)
        
        self.voice_enabled = QCheckBox("Enable Voice Recognition")
        voice_layout.addRow(self.voice_enabled)
        
        self.voice_model = QComboBox()
        self.voice_model.addItems(["Whisper", "Google", "Azure", "Local"])
        voice_layout.addRow("Voice Model:", self.voice_model)
        
        layout.addWidget(voice_group)
        
        self.tab_widget.addTab(tab, "AI")

    def _create_mining_tab(self):
        """Create mining settings tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # Mining settings
        mining_group = QGroupBox("Mining Settings")
        mining_layout = QFormLayout(mining_group)
        
        self.mining_enabled = QCheckBox("Enable Mining")
        mining_layout.addRow(self.mining_enabled)
        
        self.mining_algorithm = QComboBox()
        self.mining_algorithm.addItems(["SHA-256", "Scrypt", "Ethash", "RandomX", "KawPow"])
        mining_layout.addRow("Algorithm:", self.mining_algorithm)
        
        self.mining_intensity = QSlider(Qt.Orientation.Horizontal)
        self.mining_intensity.setRange(1, 10)
        self.mining_intensity.setValue(5)
        mining_layout.addRow("Intensity:", self.mining_intensity)
        
        layout.addWidget(mining_group)
        
        # Pool settings
        pool_group = QGroupBox("Pool Settings")
        pool_layout = QFormLayout(pool_group)
        
        self.pool_url = QLineEdit()
        pool_layout.addRow("Pool URL:", self.pool_url)
        
        self.pool_username = QLineEdit()
        pool_layout.addRow("Username:", self.pool_username)
        
        layout.addWidget(pool_group)
        
        self.tab_widget.addTab(tab, "Mining")

    def _create_security_tab(self):
        """Create security settings tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # Security settings
        security_group = QGroupBox("Security Settings")
        security_layout = QFormLayout(security_group)
        
        self.encryption_enabled = QCheckBox("Enable Encryption")
        security_layout.addRow(self.encryption_enabled)
        
        self.two_factor_enabled = QCheckBox("Enable 2FA")
        security_layout.addRow(self.two_factor_enabled)
        
        self.session_timeout = QSpinBox()
        self.session_timeout.setRange(5, 1440)
        self.session_timeout.setValue(60)
        security_layout.addRow("Session Timeout (min):", self.session_timeout)
        
        layout.addWidget(security_group)
        
        # Backup settings
        backup_group = QGroupBox("Backup Settings")
        backup_layout = QFormLayout(backup_group)
        
        self.auto_backup = QCheckBox("Auto Backup")
        backup_layout.addRow(self.auto_backup)
        
        self.backup_interval = QSpinBox()
        self.backup_interval.setRange(1, 168)
        self.backup_interval.setValue(24)
        backup_layout.addRow("Backup Interval (hours):", self.backup_interval)
        
        layout.addWidget(backup_group)
        
        self.tab_widget.addTab(tab, "Security")

    def _create_advanced_tab(self):
        """Create advanced settings tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # Performance settings
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QFormLayout(perf_group)
        
        self.max_threads = QSpinBox()
        self.max_threads.setRange(1, 32)
        self.max_threads.setValue(4)
        perf_layout.addRow("Max Threads:", self.max_threads)
        
        self.cache_size = QSpinBox()
        self.cache_size.setRange(64, 2048)
        self.cache_size.setValue(256)
        perf_layout.addRow("Cache Size (MB):", self.cache_size)
        
        layout.addWidget(perf_group)
        
        # Debug settings
        debug_group = QGroupBox("Debug Settings")
        debug_layout = QFormLayout(debug_group)
        
        self.debug_mode = QCheckBox("Debug Mode")
        debug_layout.addRow(self.debug_mode)
        
        self.verbose_logging = QCheckBox("Verbose Logging")
        debug_layout.addRow(self.verbose_logging)
        
        layout.addWidget(debug_group)
        
        self.tab_widget.addTab(tab, "Advanced")

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings."""
        return {
            'general': {
                'theme': 'Cyberpunk',
                'language': 'English',
                'auto_save': True,
                'log_level': 'INFO',
                'log_to_file': True
            },
            'trading': {
                'max_position_size': 10000,
                'risk_percentage': 2,
                'stop_loss_percentage': 5,
                'default_exchange': 'Binance',
                'trading_pairs': 'BTC/USDT,ETH/USDT,BNB/USDT'
            },
            'blockchain': {
                'default_network': 'Ethereum',
                'gas_limit': 100000,
                'gas_price_gwei': 20,
                'rpc_timeout': 30,
                'max_retries': 3
            },
            'ai': {
                'ai_model': 'GPT-4',
                'ai_temperature': 70,
                'max_tokens': 2000,
                'voice_enabled': True,
                'voice_model': 'Whisper'
            },
            'mining': {
                'mining_enabled': False,
                'mining_algorithm': 'SHA-256',
                'mining_intensity': 5,
                'pool_url': '',
                'pool_username': ''
            },
            'security': {
                'encryption_enabled': True,
                'two_factor_enabled': False,
                'session_timeout': 60,
                'auto_backup': True,
                'backup_interval': 24
            },
            'advanced': {
                'max_threads': 4,
                'cache_size': 256,
                'debug_mode': False,
                'verbose_logging': False
            }
        }

    def load_settings(self):
        """Load settings from Redis."""
        try:
            if self.redis_conn:
                settings_json = self.redis_conn.get('kingdom_ai:settings')
                if settings_json:
                    self.settings = json.loads(settings_json)
                else:
                    self.settings = self.default_settings.copy()
            else:
                self.settings = self.default_settings.copy()
                
            self._apply_settings_to_ui()
            logger.info("Settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            self.settings = self.default_settings.copy()
            self._apply_settings_to_ui()

    def save_settings(self):
        """Save settings to Redis."""
        try:
            self._collect_settings_from_ui()
            
            if self.redis_conn:
                settings_json = json.dumps(self.settings, indent=2)
                self.redis_conn.set('kingdom_ai:settings', settings_json)
                logger.info("Settings saved successfully")
                
                # Emit settings changed signal
                self.settings_changed.emit(self.settings)
                
                QMessageBox.information(self, "Success", "Settings saved successfully!")
            else:
                QMessageBox.warning(self, "Warning", "Redis connection not available. Settings not saved.")
                
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def apply_settings(self):
        """Apply settings without saving."""
        try:
            self._collect_settings_from_ui()
            self.settings_changed.emit(self.settings)
            logger.info("Settings applied")
            
        except Exception as e:
            logger.error(f"Failed to apply settings: {e}")

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self, "Reset Settings", 
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.settings = self.default_settings.copy()
            self._apply_settings_to_ui()
            logger.info("Settings reset to defaults")

    def _apply_settings_to_ui(self):
        """Apply loaded settings to UI elements."""
        try:
            # General settings
            general = self.settings.get('general', {})
            self.theme_combo.setCurrentText(general.get('theme', 'Cyberpunk'))
            self.language_combo.setCurrentText(general.get('language', 'English'))
            self.auto_save_checkbox.setChecked(general.get('auto_save', True))
            self.log_level_combo.setCurrentText(general.get('log_level', 'INFO'))
            self.log_to_file_checkbox.setChecked(general.get('log_to_file', True))
            
            # Trading settings
            trading = self.settings.get('trading', {})
            self.max_position_size.setValue(trading.get('max_position_size', 10000))
            self.risk_percentage.setValue(trading.get('risk_percentage', 2))
            self.stop_loss_percentage.setValue(trading.get('stop_loss_percentage', 5))
            self.default_exchange.setCurrentText(trading.get('default_exchange', 'Binance'))
            self.trading_pairs.setPlainText(trading.get('trading_pairs', 'BTC/USDT,ETH/USDT,BNB/USDT'))
            
            # Blockchain settings
            blockchain = self.settings.get('blockchain', {})
            self.default_network.setCurrentText(blockchain.get('default_network', 'Ethereum'))
            self.gas_limit.setValue(blockchain.get('gas_limit', 100000))
            self.gas_price_gwei.setValue(blockchain.get('gas_price_gwei', 20))
            self.rpc_timeout.setValue(blockchain.get('rpc_timeout', 30))
            self.max_retries.setValue(blockchain.get('max_retries', 3))
            
            # AI settings
            ai = self.settings.get('ai', {})
            self.ai_model.setCurrentText(ai.get('ai_model', 'GPT-4'))
            self.ai_temperature.setValue(ai.get('ai_temperature', 70))
            self.max_tokens.setValue(ai.get('max_tokens', 2000))
            self.voice_enabled.setChecked(ai.get('voice_enabled', True))
            self.voice_model.setCurrentText(ai.get('voice_model', 'Whisper'))
            
            # Mining settings
            mining = self.settings.get('mining', {})
            self.mining_enabled.setChecked(mining.get('mining_enabled', False))
            self.mining_algorithm.setCurrentText(mining.get('mining_algorithm', 'SHA-256'))
            self.mining_intensity.setValue(mining.get('mining_intensity', 5))
            self.pool_url.setText(mining.get('pool_url', ''))
            self.pool_username.setText(mining.get('pool_username', ''))
            
            # Security settings
            security = self.settings.get('security', {})
            self.encryption_enabled.setChecked(security.get('encryption_enabled', True))
            self.two_factor_enabled.setChecked(security.get('two_factor_enabled', False))
            self.session_timeout.setValue(security.get('session_timeout', 60))
            self.auto_backup.setChecked(security.get('auto_backup', True))
            self.backup_interval.setValue(security.get('backup_interval', 24))
            
            # Advanced settings
            advanced = self.settings.get('advanced', {})
            self.max_threads.setValue(advanced.get('max_threads', 4))
            self.cache_size.setValue(advanced.get('cache_size', 256))
            self.debug_mode.setChecked(advanced.get('debug_mode', False))
            self.verbose_logging.setChecked(advanced.get('verbose_logging', False))
            
        except Exception as e:
            logger.error(f"Failed to apply settings to UI: {e}")

    def _collect_settings_from_ui(self):
        """Collect settings from UI elements."""
        try:
            self.settings = {
                'general': {
                    'theme': self.theme_combo.currentText(),
                    'language': self.language_combo.currentText(),
                    'auto_save': self.auto_save_checkbox.isChecked(),
                    'log_level': self.log_level_combo.currentText(),
                    'log_to_file': self.log_to_file_checkbox.isChecked()
                },
                'trading': {
                    'max_position_size': self.max_position_size.value(),
                    'risk_percentage': self.risk_percentage.value(),
                    'stop_loss_percentage': self.stop_loss_percentage.value(),
                    'default_exchange': self.default_exchange.currentText(),
                    'trading_pairs': self.trading_pairs.toPlainText()
                },
                'blockchain': {
                    'default_network': self.default_network.currentText(),
                    'gas_limit': self.gas_limit.value(),
                    'gas_price_gwei': self.gas_price_gwei.value(),
                    'rpc_timeout': self.rpc_timeout.value(),
                    'max_retries': self.max_retries.value()
                },
                'ai': {
                    'ai_model': self.ai_model.currentText(),
                    'ai_temperature': self.ai_temperature.value(),
                    'max_tokens': self.max_tokens.value(),
                    'voice_enabled': self.voice_enabled.isChecked(),
                    'voice_model': self.voice_model.currentText()
                },
                'mining': {
                    'mining_enabled': self.mining_enabled.isChecked(),
                    'mining_algorithm': self.mining_algorithm.currentText(),
                    'mining_intensity': self.mining_intensity.value(),
                    'pool_url': self.pool_url.text(),
                    'pool_username': self.pool_username.text()
                },
                'security': {
                    'encryption_enabled': self.encryption_enabled.isChecked(),
                    'two_factor_enabled': self.two_factor_enabled.isChecked(),
                    'session_timeout': self.session_timeout.value(),
                    'auto_backup': self.auto_backup.isChecked(),
                    'backup_interval': self.backup_interval.value()
                },
                'advanced': {
                    'max_threads': self.max_threads.value(),
                    'cache_size': self.cache_size.value(),
                    'debug_mode': self.debug_mode.isChecked(),
                    'verbose_logging': self.verbose_logging.isChecked()
                }
            }
        except Exception as e:
            logger.error(f"Failed to collect settings from UI: {e}")

    def _connect_event_bus(self):
        """Connect to event bus for real-time updates."""
        if self.event_bus:
            try:
                # Subscribe to settings-related events
                if hasattr(self.event_bus, 'subscribe'):
                    self.event_bus.subscribe('settings.request', self._handle_settings_request)
                    self.event_bus.subscribe('settings.update', self._handle_settings_update)
                    logger.info("Connected to event bus for settings updates")
            except Exception as e:
                logger.error(f"Failed to connect to event bus: {e}")

    def _handle_settings_request(self, event_data):
        """Handle settings request from event bus."""
        try:
            if self.event_bus:
                self.event_bus.publish('settings.response', self.settings)
        except Exception as e:
            logger.error(f"Failed to handle settings request: {e}")

    def _handle_settings_update(self, event_data):
        """Handle settings update from event bus."""
        try:
            if isinstance(event_data, dict):
                self.settings.update(event_data)
                self._apply_settings_to_ui()
                logger.info("Settings updated from event bus")
        except Exception as e:
            logger.error(f"Failed to handle settings update: {e}")


# Export the class
__all__ = ['SettingsTab']
