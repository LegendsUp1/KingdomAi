"""
Model Manager Widget for Thoth AI Qt Interface

This module provides a widget for managing AI models, including model selection,
configuration, and status monitoring with full Ollama integration.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QGroupBox, QFormLayout, QSlider, QCheckBox, QSpinBox, QDoubleSpinBox,
    QTextEdit, QProgressBar, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

# Import Ollama connector
try:
    from core.thoth_ollama_connector import ThothOllamaConnector, get_ollama_connector
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False
    logger.warning("Ollama connector not available")

# Configure logging
logger = logging.getLogger("KingdomAI.ModelManagerWidget")


class ModelManagerWidget(QWidget):
    """Widget for managing AI models"""
    
    # Signals
    model_changed = pyqtSignal(str)  # Emits model name
    settings_changed = pyqtSignal(dict)  # Emits settings dict
    
    def __init__(self, event_bus=None, config=None, parent=None):
        """Initialize the model manager widget
        
        Args:
            event_bus: Event bus for inter-component communication
            config: Configuration dictionary
            parent: Parent widget
        """
        super().__init__(parent)
        self.event_bus = event_bus
        self.config = config or {}
        self.current_model = None
        self.available_models = []
        self.ollama_connector = None
        self.model_loaded = False
        
        logger.info("Initializing Model Manager Widget with Ollama integration")
        self._init_ui()
        self._init_ollama_connection()
        self._load_available_models()
        
    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
        title = QLabel("🤖 Model Manager")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00FF41; padding: 10px;")
        layout.addWidget(title)
        
        # Model Selection Group
        model_group = QGroupBox("Model Selection")
        model_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #00FF41;
                border-radius: 5px;
                margin-top: 10px;
                padding: 10px;
                color: #00FF41;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        model_layout = QFormLayout()
        model_group.setLayout(model_layout)
        
        # Model selector
        self.model_combo = QComboBox()
        self.model_combo.addItems(["Loading models..."])
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.model_combo.setStyleSheet("""
            QComboBox {
                background: #1a1a1b;
                color: #00FF41;
                border: 1px solid #00FF41;
                padding: 5px;
                border-radius: 3px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #00FF41;
            }
        """)
        model_layout.addRow("Model:", self.model_combo)
        
        # Model status
        self.status_label = QLabel("Status: Not loaded")
        self.status_label.setStyleSheet("color: #888; padding: 5px;")
        model_layout.addRow("", self.status_label)
        
        layout.addWidget(model_group)
        
        # Model Parameters Group
        params_group = QGroupBox("Model Parameters")
        params_group.setStyleSheet(model_group.styleSheet())
        params_layout = QFormLayout()
        params_group.setLayout(params_layout)
        
        # Temperature slider
        self.temperature_slider = QSlider(Qt.Orientation.Horizontal)
        self.temperature_slider.setMinimum(0)
        self.temperature_slider.setMaximum(200)
        self.temperature_slider.setValue(70)
        self.temperature_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.temperature_slider.setTickInterval(20)
        self.temperature_slider.valueChanged.connect(self._on_settings_changed)
        self.temperature_label = QLabel("0.70")
        self.temperature_label.setStyleSheet("color: #00FF41;")
        self.temperature_slider.valueChanged.connect(
            lambda v: self.temperature_label.setText(f"{v/100:.2f}")
        )
        
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(self.temperature_slider)
        temp_layout.addWidget(self.temperature_label)
        params_layout.addRow("Temperature:", temp_layout)
        
        # Max tokens
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setMinimum(1)
        self.max_tokens_spin.setMaximum(32000)
        self.max_tokens_spin.setValue(2048)
        self.max_tokens_spin.setSingleStep(256)
        self.max_tokens_spin.valueChanged.connect(self._on_settings_changed)
        self.max_tokens_spin.setStyleSheet("""
            QSpinBox {
                background: #1a1a1b;
                color: #00FF41;
                border: 1px solid #00FF41;
                padding: 5px;
                border-radius: 3px;
            }
        """)
        params_layout.addRow("Max Tokens:", self.max_tokens_spin)
        
        # Top P
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setMinimum(0.0)
        self.top_p_spin.setMaximum(1.0)
        self.top_p_spin.setValue(0.9)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setDecimals(2)
        self.top_p_spin.valueChanged.connect(self._on_settings_changed)
        self.top_p_spin.setStyleSheet(self.max_tokens_spin.styleSheet())
        params_layout.addRow("Top P:", self.top_p_spin)
        
        # Stream responses
        self.stream_checkbox = QCheckBox("Stream responses")
        self.stream_checkbox.setChecked(True)
        self.stream_checkbox.stateChanged.connect(self._on_settings_changed)
        self.stream_checkbox.setStyleSheet("color: #00FF41;")
        params_layout.addRow("", self.stream_checkbox)
        
        layout.addWidget(params_group)
        
        # Model Info Group
        info_group = QGroupBox("Model Information")
        info_group.setStyleSheet(model_group.styleSheet())
        info_layout = QVBoxLayout()
        info_group.setLayout(info_layout)
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(100)
        self.info_text.setPlainText("Select a model to view information")
        self.info_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a1b;
                color: #888;
                border: 1px solid #333;
                padding: 5px;
                border-radius: 3px;
            }
        """)
        info_layout.addWidget(self.info_text)
        
        layout.addWidget(info_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.load_btn = QPushButton("📥 Load Model")
        self.load_btn.clicked.connect(self._load_model)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background: #1a1a1b;
                color: #00FF41;
                border: 1px solid #00FF41;
                padding: 8px 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #00FF41;
                color: #000;
            }
        """)
        button_layout.addWidget(self.load_btn)
        
        self.unload_btn = QPushButton("📤 Unload Model")
        self.unload_btn.clicked.connect(self._unload_model)
        self.unload_btn.setEnabled(False)
        self.unload_btn.setStyleSheet(self.load_btn.styleSheet())
        button_layout.addWidget(self.unload_btn)
        
        layout.addLayout(button_layout)
        
        # Spacer
        layout.addStretch()
        
        logger.info("✅ Model Manager UI initialized")
    
    def _init_ollama_connection(self):
        """Initialize connection to Ollama"""
        if not HAS_OLLAMA:
            logger.warning("Ollama connector not available")
            return
            
        try:
            # Create Ollama connector
            self.ollama_connector = ThothOllamaConnector(self.event_bus)
            logger.info("✅ Ollama connector created")
            
            # Schedule async initialization
            QTimer.singleShot(100, self._async_init_ollama)
            
        except Exception as e:
            logger.error(f"❌ Failed to create Ollama connector: {e}")
    
    def _async_init_ollama(self):
        """Async initialization of Ollama (called via QTimer)"""
        try:
            # Run async initialization in event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._init_ollama_async())
            else:
                loop.run_until_complete(self._init_ollama_async())
        except Exception as e:
            logger.error(f"❌ Failed to initialize Ollama: {e}")
    
    async def _init_ollama_async(self):
        """Async initialization of Ollama connector"""
        try:
            if self.ollama_connector:
                await self.ollama_connector.initialize()
                logger.info("✅ Ollama connector initialized")
                
                # Reload models from Ollama
                self._load_available_models()
        except Exception as e:
            logger.error(f"❌ Ollama initialization failed: {e}")
    
    def _load_available_models(self):
        """Load list of available models from Ollama"""
        try:
            # Try to get models from Ollama first
            if self.ollama_connector and self.ollama_connector.available_models:
                self.available_models = self.ollama_connector.available_models
                logger.info(f"✅ Loaded {len(self.available_models)} models from Ollama")
            else:
                # Fallback to default models
                self.available_models = [
                    "llama3.2:latest",
                    "llama3.1:latest", 
                    "llama2:latest",
                    "mistral:latest",
                    "codellama:latest",
                    "phi3:latest",
                    "gemma2:latest",
                    "deepseek-coder:latest",
                    "qwen2.5:latest",
                    "mixtral:latest"
                ]
                logger.info(f"✅ Loaded {len(self.available_models)} default models")
            
            self.model_combo.clear()
            self.model_combo.addItems(self.available_models)
            
            # Update status
            if self.ollama_connector and self.ollama_connector.active:
                self.status_label.setText("Status: ✅ Ollama connected")
                self.status_label.setStyleSheet("color: #00FF41;")
            else:
                self.status_label.setText("Status: ⚠️ Ollama not connected")
                self.status_label.setStyleSheet("color: #FFA500;")
            
        except Exception as e:
            logger.error(f"❌ Failed to load models: {e}")
            self.model_combo.clear()
            self.model_combo.addItem("Error loading models")
            self.status_label.setText("Status: ❌ Error")
            self.status_label.setStyleSheet("color: #FF0000;")
    
    def _on_model_changed(self, model_name: str):
        """Handle model selection change"""
        if not model_name or model_name == "Loading models..." or model_name == "Error loading models":
            return
            
        logger.info(f"Model selected: {model_name}")
        self.current_model = model_name
        
        # Update info
        self.info_text.setPlainText(f"Model: {model_name}\nStatus: Not loaded\nClick 'Load Model' to initialize")
        
        # Emit signal
        self.model_changed.emit(model_name)
        
        # Publish to event bus
        if self.event_bus:
            try:
                self.event_bus.publish("thoth.model.selected", {
                    "model": model_name,
                    "timestamp": str(QTimer.currentTime())
                })
            except Exception as e:
                logger.error(f"Failed to publish model selection: {e}")
    
    def _on_settings_changed(self):
        """Handle settings change"""
        settings = self.get_settings()
        logger.debug(f"Settings changed: {settings}")
        self.settings_changed.emit(settings)
        
        # Publish to event bus
        if self.event_bus:
            try:
                self.event_bus.publish("thoth.settings.changed", settings)
            except Exception as e:
                logger.error(f"Failed to publish settings change: {e}")
    
    def _load_model(self):
        """Load the selected model via Ollama"""
        if not self.current_model:
            logger.warning("No model selected")
            return
            
        logger.info(f"Loading model: {self.current_model}")
        self.status_label.setText(f"Status: Loading {self.current_model}...")
        self.status_label.setStyleSheet("color: #FFA500;")
        self.load_btn.setEnabled(False)
        
        # Use Ollama connector to load model
        if self.ollama_connector:
            try:
                # Change model in Ollama
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._load_model_async())
                else:
                    loop.run_until_complete(self._load_model_async())
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self.status_label.setText(f"Status: ❌ Load failed")
                self.status_label.setStyleSheet("color: #FF0000;")
                self.load_btn.setEnabled(True)
        else:
            # Fallback: simulate loading
            QTimer.singleShot(1000, self._on_model_loaded)
        
        # Publish to event bus
        if self.event_bus:
            try:
                self.event_bus.publish("thoth.model.load", {
                    "model": self.current_model,
                    "settings": self.get_settings()
                })
            except Exception as e:
                logger.error(f"Failed to publish model load: {e}")
    
    async def _load_model_async(self):
        """Async model loading via Ollama"""
        try:
            if self.ollama_connector:
                # Change the model
                await self.ollama_connector._handle_model_change({
                    "model": self.current_model
                })
                
                # Test the model with a simple prompt
                await self.ollama_connector._handle_request({
                    "prompt": "Hello",
                    "model": self.current_model,
                    "streaming": False
                })
                
                # Mark as loaded
                self.model_loaded = True
                self._on_model_loaded()
        except Exception as e:
            logger.error(f"Async model load failed: {e}")
            self.status_label.setText(f"Status: ❌ Load failed")
            self.status_label.setStyleSheet("color: #FF0000;")
            self.load_btn.setEnabled(True)
    
    def _on_model_loaded(self):
        """Handle model loaded"""
        self.status_label.setText(f"Status: ✅ {self.current_model} loaded")
        self.status_label.setStyleSheet("color: #00FF41;")
        self.load_btn.setEnabled(True)
        self.unload_btn.setEnabled(True)
        self.info_text.setPlainText(f"Model: {self.current_model}\nStatus: Loaded and ready\nParameters: {self.get_settings()}")
        logger.info(f"✅ Model loaded: {self.current_model}")
    
    def _unload_model(self):
        """Unload the current model"""
        logger.info(f"Unloading model: {self.current_model}")
        self.status_label.setText("Status: Not loaded")
        self.status_label.setStyleSheet("color: #888;")
        self.unload_btn.setEnabled(False)
        self.info_text.setPlainText(f"Model: {self.current_model}\nStatus: Unloaded")
        
        # Publish to event bus
        if self.event_bus:
            try:
                self.event_bus.publish("thoth.model.unload", {
                    "model": self.current_model
                })
            except Exception as e:
                logger.error(f"Failed to publish model unload: {e}")
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current model settings"""
        return {
            "model": self.current_model,
            "temperature": self.temperature_slider.value() / 100.0,
            "max_tokens": self.max_tokens_spin.value(),
            "top_p": self.top_p_spin.value(),
            "stream": self.stream_checkbox.isChecked()
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """Set model settings"""
        if "temperature" in settings:
            self.temperature_slider.setValue(int(settings["temperature"] * 100))
        if "max_tokens" in settings:
            self.max_tokens_spin.setValue(settings["max_tokens"])
        if "top_p" in settings:
            self.top_p_spin.setValue(settings["top_p"])
        if "stream" in settings:
            self.stream_checkbox.setChecked(settings["stream"])
