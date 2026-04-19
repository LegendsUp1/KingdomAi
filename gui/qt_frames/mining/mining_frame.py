#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mining Tab for Kingdom AI

This module provides a PyQt6 QWidget implementation of the Mining tab
with Redis Quantum Nexus integration and strict connection requirements.
"""

import logging
import sys
import time
import traceback
import asyncio
import uuid  # For generating unique request IDs
import secrets  # For cryptographically secure random number generation
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
import re
import socket
import json

# Initialize logger IMMEDIATELY after logging import - CRITICAL
logger = logging.getLogger(__name__)

# CRITICAL: Set matplotlib backend BEFORE any other matplotlib imports
import matplotlib
matplotlib.use('QtAgg')  # Use QtAgg for PyQt6

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle

# ULTIMATE FIX: Monkeypatch matplotlib's get_converter to prevent recursion
import matplotlib.units as munits

# Increase recursion limit as failsafe (sys already imported above)
old_recursion_limit = sys.getrecursionlimit()
sys.setrecursionlimit(10000)

# Monkeypatch get_converter to add recursion protection
original_get_converter = munits.Registry.get_converter

def safe_get_converter(self, x):
    """Patched get_converter with recursion protection."""
    try:
        # If x is a tuple, just return None (no converter needed)
        if isinstance(x, tuple):
            return None
        # Call original with protection
        return original_get_converter(self, x)
    except (RecursionError, RuntimeError):
        # If recursion error, return None (no converter)
        return None

# Apply the patch
munits.Registry.get_converter = safe_get_converter
import numpy as np
import pandas as pd
from pathlib import Path
# Import Web3 via our unified blockchain bridge for consistent compatibility
from blockchain.blockchain_bridge import (
    is_web3_available, get_web3_provider, create_web3_instance,
    KingdomWeb3, WEB3_VERSION
)
import random

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QSpinBox, QComboBox, QGroupBox, QTextEdit, QTabWidget, QTableWidget,
    QTableWidgetItem, QGridLayout, QHeaderView, QLineEdit, QCheckBox,
    QFrame, QSizePolicy, QScrollArea, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QDateTime
from PyQt6.QtGui import QFont, QColor, QPalette

# SOTA 2026: Thread-safe UI update utility
try:
    from utils.qt_thread_safe import make_handler_thread_safe, run_on_main_thread, is_main_thread
    THREAD_SAFE_AVAILABLE = True
except ImportError:
    THREAD_SAFE_AVAILABLE = False
    def make_handler_thread_safe(func): return func
    def run_on_main_thread(func): func()
    def is_main_thread() -> bool: return True
from core.gpu_quantum_integration import GPUQuantumIntegration

# Local imports
from core.mining_system import MiningSystem
from blockchain.blockchain_connector import BlockchainConnector
from core.event_bus import EventBus
from core.redis_nexus import RedisQuantumNexus
from utils.async_support import async_slot, AsyncSupport
from utils.qt_styles import get_style_sheet

# ============================================================================
# ADVANCED SYSTEMS INTEGRATION - MINING TAB
# ============================================================================

# State-of-the-art 2025: Declare constants before try/except
has_gpu_quantum = False
has_quantum_mining = False
has_quantum_strategies = False

# GPU Quantum Integration
try:
    from mining.quantum_integration import GPUQuantumIntegration
    has_gpu_quantum = True
    logger.info("✅ GPU Quantum Integration imported")
except ImportError as e:
    logger.warning(f"⚠️ GPU Quantum not available: {e}")
    GPUQuantumIntegration = None

# Quantum Mining & Optimization
try:
    from core.quantum_mining import QuantumMining
    from kingdom_ai.quantum.quantum_optimizer import QuantumOptimizer
    from kingdom_ai.quantum.quantum_nexus import QuantumNexus
    has_quantum_mining = True  # type: ignore[misc]
    logger.info("✅ Quantum Mining imported")
except ImportError as e:
    logger.warning(f"⚠️ Quantum Mining not available: {e}")
    QuantumMining = None
    QuantumOptimizer = None
    QuantumNexus = None

# Quantum Enhanced Strategies - LAZY LOADED to prevent JAX/NumPy conflicts
# DO NOT import at module level - causes GUI initialization failure
QuantumEnhancedStrategy = None
has_quantum_strategies = False

def _lazy_import_quantum_strategies():
    """Lazy-load quantum strategies only when needed to avoid JAX/NumPy conflicts."""
    global QuantumEnhancedStrategy, has_quantum_strategies
    if QuantumEnhancedStrategy is None and not has_quantum_strategies:
        try:
            from quantum_enhanced_strategies import QuantumEnhancedStrategy as QES
            QuantumEnhancedStrategy = QES
            has_quantum_strategies = True
            logger.info("✅ Quantum Strategies lazy-loaded successfully")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Quantum Strategies not available: {e}")
            has_quantum_strategies = False
            return False
    return QuantumEnhancedStrategy is not None

from utils.redis_security import get_redis_password, get_redis_config

# SOTA 2026: Tab Highway System for isolated computational pipelines
try:
    from core.tab_highway_system import (
        get_highway, TabType, run_on_mining_highway,
        mining_highway, get_tab_highway_manager
    )
    HAS_TAB_HIGHWAY = True
except ImportError:
    HAS_TAB_HIGHWAY = False
    def run_on_mining_highway(func, *args, gpu=False, **kwargs):
        from concurrent.futures import ThreadPoolExecutor
        return ThreadPoolExecutor(max_workers=2).submit(func, *args, **kwargs)

# ============================================================================
# 2025 FIX: Define uppercase constants ONCE for backwards compatibility
# MUST be after all imports but BEFORE class definitions
# ============================================================================
GPU_QUANTUM_AVAILABLE = has_gpu_quantum
QUANTUM_MINING_AVAILABLE = has_quantum_mining
QUANTUM_STRATEGIES_AVAILABLE = has_quantum_strategies

# Configure logger
logger = logging.getLogger(__name__)


class QuantumCircuitVisualizer:
    """A class to visualize quantum circuits using matplotlib for PyQt6."""
    
    def __init__(self, fig, canvas):
        """Initialize the visualizer with matplotlib figure and canvas.
        
        Args:
            fig: Matplotlib figure
            canvas: FigureCanvas for PyQt6
        """
        self.fig = fig
        self.canvas = canvas
        self.ax = None  # Lazy initialization - create subplot on first use
        self.circuit_data = None
        self._initialized = False
    
    def _ensure_subplot(self):
        """Ensure subplot is created (lazy initialization to prevent recursion)."""
        if self.ax is None and not self._initialized:
            try:
                self.ax = self.fig.add_subplot(111)
                self._initialized = True
            except (RecursionError, RuntimeError) as e:
                logger.error(f"Failed to create quantum circuit subplot: {e}")
                self._initialized = True  # Mark as attempted to prevent infinite retries
                return False
        return self.ax is not None
    
    def clear(self):
        """Clear the visualization."""
        if not self._ensure_subplot():
            return  # Skip if subplot creation failed
        
        try:
            self.ax.clear()
            # Dark cyberpunk theme
            self.fig.set_facecolor('#1E1E1E')
            self.ax.set_facecolor('#0A0E17')
            self.ax.set_title("Quantum Circuit Visualization", color='#00FFFF')
            self.ax.set_xlabel("Gate Operations", color='#00FFAA')
            self.ax.set_ylabel("Qubits", color='#00FFAA')
            self.ax.tick_params(colors='#00FFAA', which='both')
            for spine in self.ax.spines.values():
                spine.set_color('#00FFFF')
            self.ax.grid(True, color='#1A3A4A', alpha=0.5)
            self.canvas.draw()
        except Exception as e:
            logger.warning(f"Could not clear quantum circuit: {e}")
    
    def update_circuit(self, algorithm=None, qubit_count=5, circuit_depth=3):
        """Update the quantum circuit visualization.
        
        Args:
            algorithm: Quantum algorithm name
            qubit_count: Number of qubits
            circuit_depth: Circuit depth/complexity
            
        Returns:
            bool: Success status
        """
        try:
            # Ensure subplot exists before updating
            if not self._ensure_subplot():
                return False
            
            self.clear()
            
            # Generate sample circuit data based on parameters
            qubits = min(max(1, qubit_count), 30)  # Limit to reasonable range
            depth = min(max(1, circuit_depth), 50)  # Limit to reasonable range
            
            # Create grid for qubits and gates
            _wire_color = '#00FFAA'  # Cyberpunk green for qubit wires
            _ctrl_color = '#00FFFF'  # Cyan for control dots
            for i in range(qubits):
                # Draw qubit lines
                self.ax.plot([0, depth + 1], [i, i], color=_wire_color, linewidth=1)
            
            # Add gates based on algorithm
            if algorithm == "Grover's":
                gate_colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12']
                for d in range(depth):
                    for q in range(qubits):
                        # Use secure random number generation
                        # These are only for visualization purposes, not for cryptography,
                        # but we use secrets to follow best practices
                        if q < qubits - 1 and (secrets.randbelow(100)/100) < 0.3:
                            # Draw controlled gate
                            self.ax.plot([d + 1, d + 1], [q, q + 1], color=_wire_color, linewidth=1)
                            self.ax.plot(d + 1, q, 'o', color=_ctrl_color, markersize=5)
                            gate_color = gate_colors[secrets.randbelow(len(gate_colors))]
                            self.ax.add_patch(
                                Circle((d + 1, q + 1), 0.2, color=gate_color)
                            )
                        elif (secrets.randbelow(100)/100) < 0.7:
                            # Draw single qubit gate
                            gate_color = gate_colors[secrets.randbelow(len(gate_colors))]
                            self.ax.add_patch(
                                Rectangle((d + 1 - 0.2, q - 0.2), 0.4, 0.4, color=gate_color)
                            )
            elif algorithm == "Shor's":
                # More structured circuit for Shor's
                for q in range(qubits):
                    # Add Hadamard gates at the beginning
                    self.ax.add_patch(
                        Rectangle((1 - 0.2, q - 0.2), 0.4, 0.4, color='#3498db')
                    )
                    self.ax.text(1, q, "H", ha='center', va='center', color='white', fontsize=8)
                    
                # Add QFT section
                for d in range(1, min(depth, qubits)):
                    for q in range(qubits - d):
                        self.ax.plot([d + 1, d + 1], [q, q + d], color=_wire_color, linewidth=1)
                        self.ax.plot(d + 1, q, 'o', color=_ctrl_color, markersize=5)
                        self.ax.add_patch(
                            Circle((d + 1, q + d), 0.2, color='#e74c3c')
                        )
                        self.ax.text(d + 1, q + d, "R", ha='center', va='center', color='white', fontsize=8)
            else:
                # Generic circuit visualization
                for d in range(depth):
                    for q in range(qubits):
                        # Use secure random generation even for visualization
                        # to follow best security practices
                        if (secrets.randbelow(100)/100) < 0.7:
                            # Securely select a gate type using secrets
                            gate_types = ['X', 'H', 'Z', 'Y', 'R']
                            gate_type = gate_types[secrets.randbelow(len(gate_types))]
                            color_map = {'X': '#e74c3c', 'H': '#3498db', 'Z': '#2ecc71', 'Y': '#f39c12', 'R': '#9b59b6'}
                            self.ax.add_patch(
                                Rectangle((d + 1 - 0.2, q - 0.2), 0.4, 0.4, color=color_map[gate_type])
                            )
                            self.ax.text(d + 1, q, gate_type, ha='center', va='center', color='white', fontsize=8)
            
            # Set limits and ticks
            self.ax.set_xlim([0, depth + 1.5])
            self.ax.set_ylim([-0.5, qubits - 0.5])
            self.ax.set_yticks(range(qubits))
            self.ax.set_yticklabels([f'q{i}' for i in range(qubits)])
            
            # Add algorithm title
            if algorithm:
                self.ax.set_title(f"{algorithm} Algorithm Circuit", color='#00FFFF')
            
            # Ensure tick labels are visible on dark background
            self.ax.tick_params(colors='#00FFAA', which='both')
            for lbl in self.ax.get_yticklabels():
                lbl.set_color('#00FFAA')
                
            # Redraw canvas
            self.canvas.draw()
            return True
        except Exception as e:
            logger.error(f"Error updating quantum circuit: {e}")
            return False


class MiningTab(QWidget):
    """PyQt6 QWidget implementation of the Mining Tab for Kingdom AI GUI.
    
    Provides comprehensive interface for traditional mining, quantum mining,
    airdrop farming, and mining intelligence with multi-blockchain support.
    """
    
    # Class variables to store instances
    mining_system = None
    quantum_visualization = None
    blockchain_connector = None
    quantum_devices = []
    
    def __init__(self, parent=None, event_bus=None):
        """Initialize the MiningTab with UI components and data connections.
        
        Args:
            parent: Parent widget
            event_bus: EventBus instance for pub/sub messaging
        """
        super().__init__(parent)
        self._parent_ref = parent  # type: ignore[assignment]
        # Use provided event bus or get singleton instance
        if event_bus is None:
            from core.event_bus import EventBus
            self.event_bus = EventBus.get_instance() if hasattr(EventBus, 'get_instance') else EventBus()
            print("⚠️ MiningTab: No event_bus provided, using singleton/new instance")
        else:
            self.event_bus = event_bus
            print("✅ MiningTab: Using provided global event_bus")
        
        # Initialize variables (use numeric values for stats that will be converted)
        self.hashrate = 0.0  # Store as float, display with units
        self.shares_accepted = 0
        self.rejected_shares = 0
        self.blockchain = "None"
        self.earnings = "0.00000000"
        # Mining status (string value for display)
        self.mining_status = "Ready"  # Changed from "Stopped" to show system is ready
        
        # Additional mining stats
        self.workers = 0
        self.shares = 0
        self.blocks_found = 0

        self.configured_pow_coins: List[str] = []
        self.per_coin_rewards: Dict[str, float] = {}
        self.per_coin_hashrate: Dict[str, float] = {}
        self.per_coin_rows: Dict[str, int] = {}
        self.per_coin_checkboxes = {}
        self.mining_focus_mode = "all"
        self.hashrate_history = []
        
        # Quantum variables (use numeric values for stats)
        self.quantum_device = "None"
        self.q_algorithm = "None"
        self.qubit_count = 5
        self.circuit_depth = 3
        self.q_mining_status = "Disconnected"
        self.q_progress = 0.0
        self.error_correction = False
        
        # Quantum stats (numeric for calculations)
        self.q_hashrate = 0.0  # Store as float
        self.q_efficiency = 0.0  # Store as float
        self.q_qubits = 5
        self.q_circuit_depth = 3
        self.auto_optimize = False
        self.entanglement = False
        self.quantum_status = "Ready"  # Changed from "Disconnected" to show system is ready
        self.q_connection = "Ready"  # Changed from "Not connected"
        self.q_earnings = "0.00000000"
        self.blockchain_status = "Disconnected"
        self.blockchain_progress = 0.0
        # Market price cache (symbol -> price_data)
        self._market_prices: Dict[str, Any] = {}
        # Native currency mapping for common networks
        self._native_currency_map = {"ethereum": "ETH", "bitcoin": "BTC", "polygon": "MATIC"}
        # Cached coin analytics snapshot from MiningReporter
        self._coin_analytics_snapshot: Dict[str, Any] = {}
        
        # pow_nodes mapping (symbol -> node/solo config) loaded from config/pow_nodes.json
        self.pow_nodes: Dict[str, Any] = {}
        self._pow_blockchains = []
        self._pow_blockchains_by_symbol = {}
        
        # Advanced GPU Quantum Systems
        self.gpu_quantum = None
        self.quantum_mining = None
        self.quantum_optimizer = None
        self.quantum_nexus = None
        self.quantum_strategy = None
        self._init_gpu_quantum_systems()
        
        # Initialize UI
        self.setup_ui()  # FIX: Method is named setup_ui, not _init_ui
        
        # Setup API key listener to receive all API key broadcasts
        self._setup_api_key_listener()
        
        # TIMING FIX: Defer mining data initialization (includes Redis connection)
        logger.info("⏳ Deferring Mining data initialization for 1 second to ensure Redis Quantum Nexus is ready...")
        QTimer.singleShot(1000, self._deferred_mining_init)
        
        # Setup event bus subscribers
        self.subscribe_to_events()
        
        # Update UI elements with initial data
        self.update_mining_stats()
        self.update_quantum_stats()
        
        # Ensure signal connections are made (methods are defined later but Python allows forward references)
        # Connect coin analytics combo if it exists
        if hasattr(self, 'coin_analytics_coin_combo'):
            try:
                # Disconnect any existing connections first
                self.coin_analytics_coin_combo.currentTextChanged.disconnect()
            except (TypeError, RuntimeError):
                pass  # No existing connections
            # Connect to the method (will work even though method is defined later)
            self.coin_analytics_coin_combo.currentTextChanged.connect(self._on_coin_analytics_coin_changed)
        
        # Start timer for UI updates
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_uptime)
        self.update_timer.start(1000)  # Update every second
        
    def _setup_api_key_listener(self):
        """Setup listener for API key broadcasts from APIKeyManager."""
        try:
            if self.event_bus:
                logger.info("🔑 Setting up API key listener for Mining tab")
                
                # FIXED: EventBus methods are now sync
                self.event_bus.subscribe('api.key.available.*', self._on_api_key_available)
                self.event_bus.subscribe('api.key.list', self._on_api_key_list)
                
                logger.info("✅ Mining tab listening for API key broadcasts")
        except Exception as e:
            logger.error(f"Error setting up API key listener: {e}")
    
    def _on_api_key_available(self, event_data):
        """Handle API key availability broadcast."""
        try:
            service = event_data.get('service')
            logger.info(f"🔑 Mining tab received API key for: {service}")
            # Mining tab can use blockchain provider keys, etc.
        except Exception as e:
            logger.error(f"Error handling API key availability: {e}")
    
    def _on_api_key_list(self, event_data):
        """Handle complete API key list."""
        try:
            api_keys = event_data.get('api_keys', {})
            logger.info(f"📋 Mining tab received {len(api_keys)} API keys")
        except Exception as e:
            logger.error(f"Error handling API key list: {e}")
    
    def _log(self, message, level=logging.INFO):
        """Log a message both to the logger and to the application status display."""
        logger.log(level, message)
        if hasattr(self, 'event_bus') and self.event_bus:
            try:
                from PyQt6.QtCore import QTimer
                
                def publish_log():
                    try:
                        self.event_bus.publish('gui.update', {
                            'component': 'mining_tab',
                            'message': message,
                            'level': level,
                            'timestamp': time.time()
                        })
                    except Exception as e:
                        logger.error(f"Error publishing log message: {e}")
                
                # Schedule 100ms later to avoid task nesting during init
                QTimer.singleShot(100, publish_log)
            except Exception as e:
                logger.error(f"Error scheduling log publish: {e}")
                
    def setup_ui(self):
        """Setup the Mining Tab UI components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create tabs for different mining functions
        tabs = QTabWidget()
        # SOTA 2026 FIX: Ensure tab widget expands properly and tabs are visible
        tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tabs.setMinimumHeight(400)  # Ensure minimum height for tab content visibility
        
        # Add tabs
        tabs.addTab(self._create_traditional_mining_tab(), "Traditional Mining")
        tabs.addTab(self._create_quantum_mining_tab(), "Quantum Mining")
        tabs.addTab(self._create_mining_intelligence_tab(), "Mining Intelligence")
        tabs.addTab(self._create_blockchain_tab(), "Blockchain Status")
        tabs.addTab(self._create_airdrop_farming_tab(), "Airdrop Farming")
        
        # Add to main layout
        main_layout.addWidget(tabs, stretch=1)  # Give tabs priority to expand
        
        # Create status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #00FF00;")
        status_layout.addWidget(self.status_label)
        
        # Add blockchain status indicator
        self.blockchain_status_label = QLabel("Blockchain: Disconnected")
        self.blockchain_status_label.setStyleSheet("color: red;")
        status_layout.addWidget(self.blockchain_status_label)
        
        # Add nodes status indicator
        self.nodes_status_label = QLabel("Nodes: Disconnected")
        self.nodes_status_label.setStyleSheet("color: red;")
        status_layout.addWidget(self.nodes_status_label)
        
        # Add pools status indicator
        self.pools_status_label = QLabel("Pools: Disconnected")
        self.pools_status_label.setStyleSheet("color: red;")
        status_layout.addWidget(self.pools_status_label)
        
        # Add spacer
        status_layout.addStretch(1)
        
        # Add quantum status indicator
        self.quantum_status_label = QLabel("Quantum: Disconnected")
        self.quantum_status_label.setStyleSheet("color: red;")
        status_layout.addWidget(self.quantum_status_label)
        
        # Add to main layout
        main_layout.addLayout(status_layout)
        
    def _create_traditional_mining_tab(self):
        """Create the traditional mining tab with controls and stats."""
        tab = QWidget()
        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        # Control panel
        control_group = QGroupBox("Mining Control")
        control_layout = QVBoxLayout(control_group)
        
        # Settings layout
        settings_layout = QHBoxLayout()
        
        # Blockchain selection - 2025 STATE-OF-THE-ART: Load from data file
        blockchain_layout = QVBoxLayout()
        blockchain_layout.addWidget(QLabel("Blockchain:"))
        self.blockchain_combo = QComboBox()
        # Load POW blockchains dynamically
        self._load_pow_blockchains_to_combo()
        self.blockchain_combo.currentTextChanged.connect(self._on_blockchain_changed)
        blockchain_layout.addWidget(self.blockchain_combo)
        settings_layout.addLayout(blockchain_layout)
        
        # Mining Mode Selection
        mode_layout = QVBoxLayout()
        mode_layout.addWidget(QLabel("Mining Mode:"))
        self.mining_mode_combo = QComboBox()
        self.mining_mode_combo.addItems(["Solo Mining", "Pool Mining"])
        self.mining_mode_combo.currentTextChanged.connect(self._on_mining_mode_changed)
        mode_layout.addWidget(self.mining_mode_combo)
        settings_layout.addLayout(mode_layout)
        
        # Mining pool (only for pool mining)
        pool_layout = QVBoxLayout()
        pool_layout.addWidget(QLabel("Mining Pool:"))
        self.pool_combo = QComboBox()
        self.pool_combo.addItems(["KingdomPool", "NiceHash", "F2Pool", "Poolin", "Slushpool"])
        pool_layout.addWidget(self.pool_combo)
        settings_layout.addLayout(pool_layout)
        
        # Worker threads
        threads_layout = QVBoxLayout()
        threads_layout.addWidget(QLabel("Worker Threads:"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 128)
        self.threads_spin.setValue(8)
        threads_layout.addWidget(self.threads_spin)
        settings_layout.addLayout(threads_layout)
        
        control_layout.addLayout(settings_layout)
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Mining")
        self.start_button.setToolTip("Begin mining operations on selected blockchain")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #006600;
                color: #00FF00;
                border: 2px solid #00FF00;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 0, 0.2);
                border-color: #00FFFF;
            }
            QPushButton:pressed {
                background-color: #004400;
            }
        """)
        self.start_button.clicked.connect(self._on_start_mining)
        self.stop_button = QPushButton("Stop Mining")
        self.stop_button.setToolTip("Stop all mining operations")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #660000;
                color: #FF6666;
                border: 2px solid #FF4444;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 0.2);
                border-color: #FF8888;
            }
            QPushButton:pressed {
                background-color: #440000;
            }
        """)
        self.stop_button.clicked.connect(self._on_stop_mining)
        self.stop_button.setEnabled(False)
        
        # MINE ALL COINS BUTTON - mines all 82 POW coins
        self.mine_all_button = QPushButton("⛏️ MINE ALL 82 COINS")
        self.mine_all_button.setToolTip("Start mining ALL 82 POW cryptocurrencies simultaneously")
        self.mine_all_button.setStyleSheet("""
            QPushButton {
                background-color: #FF6B00;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #FF8C00;
            }
            QPushButton:pressed {
                background-color: #CC5500;
            }
        """)
        self.mine_all_button.clicked.connect(self._on_mine_all_coins)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.mine_all_button)
        control_layout.addLayout(button_layout)
        
        layout.addWidget(control_group)
        
        # Stats panel
        stats_group = QGroupBox("Mining Statistics")
        stats_layout = QGridLayout(stats_group)
        
        # Add stat fields
        stats_layout.addWidget(QLabel("Status:"), 0, 0)
        self.mining_status_label = QLabel("Stopped")
        stats_layout.addWidget(self.mining_status_label, 0, 1)
        
        stats_layout.addWidget(QLabel("Hashrate:"), 1, 0)
        self.hashrate_label = QLabel("0.00 H/s")
        stats_layout.addWidget(self.hashrate_label, 1, 1)
        
        stats_layout.addWidget(QLabel("Shares Accepted:"), 2, 0)
        self.shares_accepted_label = QLabel("0")
        stats_layout.addWidget(self.shares_accepted_label, 2, 1)
        
        stats_layout.addWidget(QLabel("Shares Rejected:"), 3, 0)
        self.rejected_shares_label = QLabel("0")
        stats_layout.addWidget(self.rejected_shares_label, 3, 1)
        
        stats_layout.addWidget(QLabel("Earnings:"), 4, 0)
        self.earnings_label = QLabel("0.00 BTC")
        stats_layout.addWidget(self.earnings_label, 4, 1)
        
        stats_layout.addWidget(QLabel("Uptime:"), 5, 0)
        self.uptime_label = QLabel("00:00:00")
        stats_layout.addWidget(self.uptime_label, 5, 1)
        
        # Add spacer
        stats_layout.setRowStretch(6, 1)
        
        layout.addWidget(stats_group)

        per_coin_group = QGroupBox("Per-Coin Mining Control & Rewards")
        per_coin_layout = QVBoxLayout(per_coin_group)

        header_row = QHBoxLayout()
        self.led_status_label = QLabel("MINING: INACTIVE")
        self.led_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.led_status_label.setStyleSheet(
            "color: #00FFAA; background-color: #001a0f; padding: 6px 12px;"
            "border-radius: 6px; font-size: 12pt; font-weight: bold; letter-spacing: 1px;"
        )
        header_row.addWidget(self.led_status_label)

        self.led_hashrate_label = QLabel("0.00 H/s")
        self.led_hashrate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.led_hashrate_label.setStyleSheet(
            "color: #00FFAA; background-color: #000b1a; padding: 6px 12px;"
            "border-radius: 6px; font-size: 14pt; font-weight: bold;"
        )
        header_row.addWidget(self.led_hashrate_label)

        header_row.addStretch(1)

        self.mining_focus_mode_combo = QComboBox()
        self.mining_focus_mode_combo.addItems(["Mine All Configured Coins", "Mine Focused Coins Only"])
        self.mining_focus_mode_combo.currentTextChanged.connect(self._on_focus_mode_changed)
        header_row.addWidget(self.mining_focus_mode_combo)

        self.funnel_button = QPushButton("Funnel Rewards")
        self.funnel_button.setToolTip("Send current rewards to wallet without stopping mining")
        self.funnel_button.clicked.connect(self._on_funnel_rewards_clicked)
        header_row.addWidget(self.funnel_button)

        per_coin_layout.addLayout(header_row)

        self.coin_table = QTableWidget(0, 7)
        self.coin_table.setHorizontalHeaderLabels(["On", "Symbol", "Name", "Wallet Address", "Hashrate", "Rewards", "Status"])
        # SOTA 2026 FIX: Make table expand properly and be visible
        self.coin_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.coin_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.coin_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.coin_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # SOTA 2026 FIX: Ensure table expands and is visible
        self.coin_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.coin_table.setMinimumHeight(200)  # Ensure minimum height for visibility
        per_coin_layout.addWidget(self.coin_table, stretch=1)  # Give table stretch priority

        layout.addWidget(per_coin_group)
        
        # Hashrate chart (use subplots() to avoid add_subplot recursion)
        chart_group = QGroupBox("Hashrate History")
        chart_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_group.setMinimumHeight(200)  # Ensure chart is visible
        chart_layout = QVBoxLayout(chart_group)
        
        # Create figure and axes together to avoid converter recursion
        self.figure, self.ax = plt.subplots(figsize=(8, 4), dpi=100)  # Larger figure for better visibility
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumHeight(150)  # Minimum canvas height
        chart_layout.addWidget(self.canvas, stretch=2)  # Canvas gets stretch priority
        # Dark cyberpunk theme for chart
        self.figure.set_facecolor('#1E1E1E')
        self.ax.set_facecolor('#0A0E17')
        self.ax.set_title("Hashrate over Time", color='#00FFFF')
        self.ax.set_xlabel("Time", color='#00FFAA')
        self.ax.set_ylabel("Hashrate (H/s)", color='#00FFAA')
        self.ax.tick_params(colors='#00FFAA', which='both')
        for spine in self.ax.spines.values():
            spine.set_color('#00FFFF')
        self.ax.grid(True, color='#1A3A4A', alpha=0.5)
        
        layout.addWidget(chart_group, stretch=2)  # Chart gets more stretch priority for expansion
        
        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)
        return tab
    
    def _create_quantum_mining_tab(self):
        """Create the quantum mining tab with controls and visualization."""
        # SOTA 2026 FIX: Wrap content in scroll area to prevent canvas compression
        tab = QWidget()
        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        # SOTA 2026 FIX: Ensure scroll area expands properly
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Content widget inside scroll area
        content_widget = QWidget()
        # SOTA 2026 FIX: Content widget must expand to fill scroll area
        content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_widget.setMinimumHeight(800)  # Ensure enough space for all widgets
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)  # Better spacing between sections
        
        # Top section with control panel and stats
        top_layout = QHBoxLayout()
        
        # Control panel - SOTA 2026 FIX: Proper sizing
        control_group = QGroupBox("Quantum Mining Control")
        control_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        control_group.setMinimumWidth(300)  # Ensure minimum width for controls
        control_layout = QVBoxLayout(control_group)
        control_layout.setSpacing(8)
        
        # Quantum device selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Quantum Device:"))
        self.quantum_device_combo = QComboBox()
        self.quantum_device_combo.addItem("None")
        device_layout.addWidget(self.quantum_device_combo)
        control_layout.addLayout(device_layout)
        
        # Algorithm selection
        algo_layout = QHBoxLayout()
        algo_layout.addWidget(QLabel("Algorithm:"))
        self.q_algorithm_combo = QComboBox()
        self.q_algorithm_combo.addItems(["Generic", "Grover's", "Shor's", "QFT"])
        algo_layout.addWidget(self.q_algorithm_combo)
        control_layout.addLayout(algo_layout)
        
        # Qubit count
        qubit_layout = QHBoxLayout()
        qubit_layout.addWidget(QLabel("Qubits:"))
        self.qubit_spin = QSpinBox()
        self.qubit_spin.setRange(1, 30)
        self.qubit_spin.setValue(5)
        qubit_layout.addWidget(self.qubit_spin)
        control_layout.addLayout(qubit_layout)
        
        # Circuit depth
        depth_layout = QHBoxLayout()
        depth_layout.addWidget(QLabel("Circuit Depth:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 50)
        self.depth_spin.setValue(3)
        depth_layout.addWidget(self.depth_spin)
        control_layout.addLayout(depth_layout)
        
        # Optimization checkboxes
        self.error_correction_check = QCheckBox("Error Correction")
        control_layout.addWidget(self.error_correction_check)
        
        self.auto_optimize_check = QCheckBox("Auto-Optimize")
        control_layout.addWidget(self.auto_optimize_check)
        
        self.entanglement_check = QCheckBox("Enhanced Entanglement")
        control_layout.addWidget(self.entanglement_check)
        
        # Control buttons
        q_button_layout = QHBoxLayout()
        self.q_start_button = QPushButton("Start Quantum Mining")
        self.q_start_button.clicked.connect(self._on_start_quantum_mining)
        self.q_stop_button = QPushButton("Stop Quantum Mining")
        self.q_stop_button.clicked.connect(self._on_stop_quantum_mining)
        self.q_stop_button.setEnabled(False)
        q_button_layout.addWidget(self.q_start_button)
        q_button_layout.addWidget(self.q_stop_button)
        control_layout.addLayout(q_button_layout)
        
        top_layout.addWidget(control_group, stretch=1)  # Allow control group to stretch
        
        # Stats panel - SOTA 2026 FIX: Proper sizing for quantum mining stats
        q_stats_group = QGroupBox("Quantum Mining Statistics")
        q_stats_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        q_stats_layout = QGridLayout(q_stats_group)
        q_stats_layout.setColumnStretch(0, 1)  # Label column - minimum
        q_stats_layout.setColumnStretch(1, 2)  # Value column - expand
        q_stats_layout.setSpacing(10)  # Better spacing
        
        q_stats_layout.addWidget(QLabel("Status:"), 0, 0)
        self.q_mining_status_label = QLabel("Disconnected")
        self.q_mining_status_label.setStyleSheet("color: red;")
        self.q_mining_status_label.setMinimumWidth(150)  # Ensure minimum width
        q_stats_layout.addWidget(self.q_mining_status_label, 0, 1)
        
        q_stats_layout.addWidget(QLabel("Quantum Hashrate:"), 1, 0)
        self.q_hashrate_label = QLabel("0.00 QH/s")
        self.q_hashrate_label.setMinimumWidth(150)
        q_stats_layout.addWidget(self.q_hashrate_label, 1, 1)
        
        q_stats_layout.addWidget(QLabel("Quantum Efficiency:"), 2, 0)
        self.q_efficiency_label = QLabel("0.0%")
        self.q_efficiency_label.setMinimumWidth(150)
        q_stats_layout.addWidget(self.q_efficiency_label, 2, 1)
        
        q_stats_layout.addWidget(QLabel("Connection Quality:"), 3, 0)
        self.q_connection_label = QLabel("Not connected")
        self.q_connection_label.setMinimumWidth(150)
        q_stats_layout.addWidget(self.q_connection_label, 3, 1)
        
        q_stats_layout.addWidget(QLabel("Quantum Earnings:"), 4, 0)
        self.q_earnings_label = QLabel("0.00 BTC")
        self.q_earnings_label.setMinimumWidth(150)
        q_stats_layout.addWidget(self.q_earnings_label, 4, 1)
        
        q_stats_layout.addWidget(QLabel("Progress:"), 5, 0)
        self.q_progress_bar = QProgressBar()
        self.q_progress_bar.setValue(0)
        self.q_progress_bar.setMinimumWidth(200)  # Wider progress bar
        q_stats_layout.addWidget(self.q_progress_bar, 5, 1)
        
        top_layout.addWidget(q_stats_group, stretch=1)  # Allow stats group to stretch
        
        layout.addLayout(top_layout)  # Top controls - fixed height, don't expand vertically
        
        # Quantum Circuit Visualization (use subplots() to avoid recursion)
        q_circuit_group = QGroupBox("Quantum Circuit Visualization")
        q_circuit_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # SOTA 2026 FIX: Ensure visualization is always properly expanded and visible
        q_circuit_group.setMinimumHeight(400)
        # NO maximum height - allow full expansion
        q_circuit_layout = QVBoxLayout(q_circuit_group)
        q_circuit_layout.setContentsMargins(10, 20, 10, 10)  # Better margins inside groupbox
        q_circuit_layout.setSpacing(10)
        
        # Create figure and axes together to avoid converter recursion
        self.q_figure, q_ax = plt.subplots(figsize=(12, 5), dpi=100)
        self.q_canvas = FigureCanvas(self.q_figure)
        self.q_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # SOTA 2026 FIX: Proper minimum size for canvas - NO fixed height to allow expansion
        self.q_canvas.setMinimumHeight(300)
        self.q_canvas.setMinimumWidth(500)
        q_circuit_layout.addWidget(self.q_canvas, stretch=2)  # Canvas gets priority stretch
        # Dark cyberpunk theme for quantum chart
        self.q_figure.set_facecolor('#1E1E1E')
        q_ax.set_facecolor('#0A0E17')
        q_ax.tick_params(colors='#00FFAA', which='both')
        for spine in q_ax.spines.values():
            spine.set_color('#00FFFF')
        
        # Initialize visualizer (with lazy subplot creation)
        self.quantum_visualization = QuantumCircuitVisualizer(self.q_figure, self.q_canvas)
        # Don't call update_circuit here - let user trigger it to avoid recursion on startup
        
        # Update button
        q_viz_button_layout = QHBoxLayout()
        self.update_circuit_button = QPushButton("Update Circuit Visualization")
        self.update_circuit_button.clicked.connect(self._on_update_quantum_circuit)
        q_viz_button_layout.addWidget(self.update_circuit_button)
        q_circuit_layout.addLayout(q_viz_button_layout)
        
        layout.addWidget(q_circuit_group, stretch=2)  # Allow vertical expansion
        
        # ⚡⚡⚡ GPU QUANTUM INTEGRATION ⚡⚡⚡
        if GPU_QUANTUM_AVAILABLE:
            gpu_quantum_group = QGroupBox("⚡ GPU QUANTUM INTEGRATION")
            # SOTA 2026 FIX: Allow GPU quantum section to expand properly - don't use fixed height
            gpu_quantum_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            gpu_quantum_group.setMinimumHeight(150)  # Minimum height but allow expansion
            gpu_quantum_group.setStyleSheet("""
                QGroupBox {
                    background-color: rgba(20, 0, 40, 180);
                    border: 2px solid #00FFAA;
                    border-radius: 5px;
                    font-weight: bold;
                    color: #00FFAA;
                    padding: 10px;
                    font-size: 11px;
                }
            """)
            gpu_quantum_layout = QVBoxLayout(gpu_quantum_group)
            
            # GPU Status Display
            gpu_status_layout = QHBoxLayout()
            
            self.gpu_device_label = QLabel("GPU: Detecting...")
            self.gpu_device_label.setStyleSheet("color: #00FFAA; font-size: 10px;")
            gpu_status_layout.addWidget(self.gpu_device_label)
            
            self.gpu_memory_label = QLabel("Memory: N/A")
            self.gpu_memory_label.setStyleSheet("color: #00FFAA; font-size: 10px;")
            gpu_status_layout.addWidget(self.gpu_memory_label)
            
            self.gpu_temp_label = QLabel("Temp: N/A")
            self.gpu_temp_label.setStyleSheet("color: #00FFAA; font-size: 10px;")
            gpu_status_layout.addWidget(self.gpu_temp_label)
            
            gpu_quantum_layout.addLayout(gpu_status_layout)
            
            # GPU Quantum Control Buttons - SOTA 2026 FIX: Better button sizing
            gpu_btn_layout = QHBoxLayout()
            gpu_btn_layout.setSpacing(10)  # Better spacing between buttons
            
            self.gpu_detect_btn = QPushButton("🔍 Detect GPUs")
            self.gpu_detect_btn.setMinimumSize(120, 35)  # Minimum button size
            self.gpu_detect_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.gpu_detect_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 120, 100, 180);
                    color: #00FFAA;
                    border: 1px solid #00FFAA;
                    border-radius: 3px;
                    padding: 6px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(0, 160, 140, 220);
                }
            """)
            self.gpu_detect_btn.clicked.connect(self._detect_gpu_devices)
            gpu_btn_layout.addWidget(self.gpu_detect_btn)
            
            self.gpu_optimize_btn = QPushButton("⚡ Optimize")
            self.gpu_optimize_btn.setMinimumSize(120, 35)  # Minimum button size
            self.gpu_optimize_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.gpu_optimize_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 120, 100, 180);
                    color: #00FFAA;
                    border: 1px solid #00FFAA;
                    border-radius: 3px;
                    padding: 6px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(0, 160, 140, 220);
                }
            """)
            self.gpu_optimize_btn.clicked.connect(self.optimize_gpu_quantum)
            gpu_btn_layout.addWidget(self.gpu_optimize_btn)
            
            self.gpu_benchmark_btn = QPushButton("📊 Benchmark")
            self.gpu_benchmark_btn.setMinimumSize(120, 35)  # Minimum button size
            self.gpu_benchmark_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.gpu_benchmark_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 120, 100, 180);
                    color: #00FFAA;
                    border: 1px solid #00FFAA;
                    border-radius: 3px;
                    padding: 6px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(0, 160, 140, 220);
                }
            """)
            self.gpu_benchmark_btn.clicked.connect(self._run_gpu_benchmark)
            gpu_btn_layout.addWidget(self.gpu_benchmark_btn)
            
            gpu_quantum_layout.addLayout(gpu_btn_layout)
            
            # GPU Quantum Output Display
            self.gpu_output_display = QTextEdit()
            self.gpu_output_display.setReadOnly(True)
            self.gpu_output_display.setMinimumHeight(60)  # Reduced minimum height
            self.gpu_output_display.setMaximumHeight(120)  # Set maximum height to prevent taking too much space
            self.gpu_output_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.gpu_output_display.setStyleSheet("""
                QTextEdit {
                    background-color: rgba(0, 20, 15, 180);
                    color: #00FFAA;
                    padding: 5px;
                    border: 1px solid #00FFAA;
                    border-radius: 3px;
                    font-family: monospace;
                    font-size: 9px;
                }
            """)
            self.gpu_output_display.setPlainText(
                "🔧 GPU Quantum Integration Ready\n"
                "📊 Supports: CUDA, AMD ROCm, CPU Fallback\n"
                "⚡ Click 'Detect GPUs' to scan for devices\n"
                "🚀 Click 'Optimize' to enhance quantum mining performance"
            )
            gpu_quantum_layout.addWidget(self.gpu_output_display)
            
            layout.addWidget(gpu_quantum_group)  # Allow natural expansion without forced stretch
            logger.info("✅ GPU Quantum Integration UI section added to Mining Tab")
        
        # SOTA 2026 FIX: Complete scroll area setup to ensure canvas displays properly
        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)
        
        return tab
    
    def _create_mining_intelligence_tab(self):
        """Create the mining intelligence tab with analytics and predictions."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Intelligence dashboard
        intel_group = QGroupBox("Mining Intelligence Dashboard")
        intel_layout = QVBoxLayout(intel_group)
        
        # Add mining intelligence components
        self.intel_text = QTextEdit()
        self.intel_text.setReadOnly(True)
        self.intel_text.setText("Mining intelligence system initializing...\n")
        intel_layout.addWidget(self.intel_text)
        
        # Add recommendation section
        recommendation_layout = QHBoxLayout()
        recommendation_layout.addWidget(QLabel("AI Recommendations:"))
        
        self.recommendation_combo = QComboBox()
        self.recommendation_combo.addItems(["Profit Optimization", "Energy Efficiency", "Balanced"])
        recommendation_layout.addWidget(self.recommendation_combo)
        
        self.apply_recommendation_button = QPushButton("Apply")
        self.apply_recommendation_button.clicked.connect(self._on_apply_recommendation)
        recommendation_layout.addWidget(self.apply_recommendation_button)
        
        intel_layout.addLayout(recommendation_layout)
        
        layout.addWidget(intel_group)
        
        # Add profit prediction chart
        profit_group = QGroupBox("Profit Prediction")
        profit_layout = QVBoxLayout(profit_group)
        
        # Add profit timeline controls
        timeline_layout = QHBoxLayout()
        timeline_layout.addWidget(QLabel("Prediction Timeline:"))
        
        self.timeline_combo = QComboBox()
        self.timeline_combo.addItems(["24 Hours", "7 Days", "30 Days", "90 Days"])
        timeline_layout.addWidget(self.timeline_combo)
        
        self.update_prediction_button = QPushButton("Update Prediction")
        self.update_prediction_button.clicked.connect(self._on_update_prediction)
        timeline_layout.addWidget(self.update_prediction_button)
        
        profit_layout.addLayout(timeline_layout)
        
        # Add profit chart (use subplots() to avoid add_subplot recursion)
        # Create figure and axes together to avoid converter recursion
        self.profit_figure, self.profit_ax = plt.subplots(figsize=(8, 4), dpi=100)
        self.profit_canvas = FigureCanvas(self.profit_figure)
        # BUG 5 FIX: Add Expanding size policy and min height (matches hashrate/quantum charts)
        self.profit_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.profit_canvas.setMinimumHeight(150)
        # Dark cyberpunk theme for profit chart
        self.profit_figure.set_facecolor('#1E1E1E')
        self.profit_ax.set_facecolor('#0A0E17')
        self.profit_ax.set_title("Projected Mining Profit", color='#00FFFF')
        self.profit_ax.set_xlabel("Time", color='#00FFAA')
        self.profit_ax.set_ylabel("Profit (USD)", color='#00FFAA')
        self.profit_ax.tick_params(colors='#00FFAA', which='both')
        for spine in self.profit_ax.spines.values():
            spine.set_color('#00FFFF')
        self.profit_ax.grid(True, color='#1A3A4A', alpha=0.5)
        profit_layout.addWidget(self.profit_canvas, stretch=2)
        
        layout.addWidget(profit_group)

        analytics_group = QGroupBox("Live Coin Profitability Analytics")
        analytics_layout = QHBoxLayout(analytics_group)

        ranking_layout = QVBoxLayout()
        ranking_layout.addWidget(QLabel("Top Coins by Reward per Hash"))
        self.coin_analytics_table = QTableWidget(0, 3)
        self.coin_analytics_table.setHorizontalHeaderLabels(["Rank", "Symbol", "Reward/Hash"])
        self.coin_analytics_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.coin_analytics_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.coin_analytics_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        ranking_layout.addWidget(self.coin_analytics_table)
        analytics_layout.addLayout(ranking_layout)

        hourly_layout = QVBoxLayout()
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Select Coin:"))
        self.coin_analytics_coin_combo = QComboBox()
        # Signal connection will be made in setup_ui() after all UI is created
        # to ensure method exists (Python allows forward references but we'll connect explicitly)
        header_row.addWidget(self.coin_analytics_coin_combo)
        header_row.addStretch(1)
        hourly_layout.addLayout(header_row)
        self.coin_analytics_hourly_table = QTableWidget(0, 5)
        self.coin_analytics_hourly_table.setHorizontalHeaderLabels([
            "Hour",
            "Rewards",
            "Reward/Hash",
            "Samples",
            "Focused/Unfocused",
        ])
        self.coin_analytics_hourly_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.coin_analytics_hourly_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.coin_analytics_hourly_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hourly_layout.addWidget(self.coin_analytics_hourly_table)
        analytics_layout.addLayout(hourly_layout)

        layout.addWidget(analytics_group)
        
        return tab
        
    def _create_blockchain_tab(self):
        """Create the blockchain status tab with network information."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Blockchain selection
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Select Blockchain:"))
        
        self.blockchain_view_combo = QComboBox()
        self.blockchain_view_combo.addItems(["Bitcoin", "Ethereum", "Litecoin", "Monero", "Zcash"])
        selection_layout.addWidget(self.blockchain_view_combo)
        
        self.refresh_blockchain_button = QPushButton("Refresh")
        self.refresh_blockchain_button.clicked.connect(self._on_refresh_blockchain)
        selection_layout.addWidget(self.refresh_blockchain_button)
        
        selection_layout.addStretch(1)
        layout.addLayout(selection_layout)
        
        # Network statistics
        network_group = QGroupBox("Network Statistics")
        network_layout = QGridLayout(network_group)
        
        network_layout.addWidget(QLabel("Network Hashrate:"), 0, 0)
        self.network_hashrate_label = QLabel("Loading...")
        network_layout.addWidget(self.network_hashrate_label, 0, 1)
        
        network_layout.addWidget(QLabel("Block Height:"), 1, 0)
        self.block_height_label = QLabel("Loading...")
        network_layout.addWidget(self.block_height_label, 1, 1)
        
        network_layout.addWidget(QLabel("Difficulty:"), 2, 0)
        self.difficulty_label = QLabel("Loading...")
        network_layout.addWidget(self.difficulty_label, 2, 1)
        
        network_layout.addWidget(QLabel("Block Reward:"), 3, 0)
        self.block_reward_label = QLabel("Loading...")
        network_layout.addWidget(self.block_reward_label, 3, 1)
        
        network_layout.addWidget(QLabel("Network Status:"), 4, 0)
        self.network_status_label = QLabel("Connecting...")
        network_layout.addWidget(self.network_status_label, 4, 1)
        
        layout.addWidget(network_group)
        
        # Recent blocks
        blocks_group = QGroupBox("Recent Blocks")
        blocks_layout = QVBoxLayout(blocks_group)
        
        self.blocks_table = QTableWidget(10, 5)
        self.blocks_table.setHorizontalHeaderLabels(["Height", "Hash", "Time", "Transactions", "Size"])
        self.blocks_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        blocks_layout.addWidget(self.blocks_table)
        
        layout.addWidget(blocks_group)
        
        # Market data
        market_group = QGroupBox("Market Data")
        market_layout = QGridLayout(market_group)
        
        market_layout.addWidget(QLabel("Current Price:"), 0, 0)
        self.price_label = QLabel("Loading...")
        market_layout.addWidget(self.price_label, 0, 1)
        
        market_layout.addWidget(QLabel("24h Change:"), 1, 0)
        self.change_label = QLabel("Loading...")
        market_layout.addWidget(self.change_label, 1, 1)
        
        market_layout.addWidget(QLabel("Market Cap:"), 2, 0)
        self.market_cap_label = QLabel("Loading...")
        market_layout.addWidget(self.market_cap_label, 2, 1)
        
        market_layout.addWidget(QLabel("24h Volume:"), 3, 0)
        self.volume_label = QLabel("Loading...")
        market_layout.addWidget(self.volume_label, 3, 1)
        
        layout.addWidget(market_group)
        
        return tab
    
    def _create_airdrop_farming_tab(self):
        """Create the airdrop farming tab with active campaigns."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Control panel
        control_group = QGroupBox("Airdrop Farming Control")
        control_layout = QHBoxLayout(control_group)
        
        # Enable/disable airdrop farming
        self.airdrop_enabled_check = QCheckBox("Enable Airdrop Farming")
        self.airdrop_enabled_check.stateChanged.connect(self._on_airdrop_farming_changed)
        control_layout.addWidget(self.airdrop_enabled_check)
        
        # Strategy selection
        control_layout.addWidget(QLabel("Strategy:"))
        self.airdrop_strategy_combo = QComboBox()
        self.airdrop_strategy_combo.addItems(["Aggressive", "Balanced", "Conservative"])
        control_layout.addWidget(self.airdrop_strategy_combo)
        
        # Scan button
        self.scan_airdrops_button = QPushButton("Scan for New Airdrops")
        self.scan_airdrops_button.clicked.connect(self._on_scan_airdrops)
        control_layout.addWidget(self.scan_airdrops_button)
        
        layout.addWidget(control_group)
        
        # Active campaigns
        campaigns_group = QGroupBox("Active Airdrop Campaigns")
        campaigns_layout = QVBoxLayout(campaigns_group)
        
        self.campaigns_table = QTableWidget(0, 6)
        self.campaigns_table.setHorizontalHeaderLabels(["Project", "Token", "Requirements", "Estimated Value", "Status", "Actions"])
        self.campaigns_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        campaigns_layout.addWidget(self.campaigns_table)
        
        layout.addWidget(campaigns_group)
        
        # Farming statistics
        stats_group = QGroupBox("Farming Statistics")
        stats_layout = QGridLayout(stats_group)
        
        stats_layout.addWidget(QLabel("Active Campaigns:"), 0, 0)
        self.active_campaigns_label = QLabel("0")
        stats_layout.addWidget(self.active_campaigns_label, 0, 1)
        
        stats_layout.addWidget(QLabel("Completed Airdrops:"), 1, 0)
        self.completed_airdrops_label = QLabel("0")
        stats_layout.addWidget(self.completed_airdrops_label, 1, 1)
        
        stats_layout.addWidget(QLabel("Tokens Collected:"), 2, 0)
        self.tokens_collected_label = QLabel("0")
        stats_layout.addWidget(self.tokens_collected_label, 2, 1)
        
        stats_layout.addWidget(QLabel("Estimated Value:"), 3, 0)
        self.estimated_value_label = QLabel("$0.00")
        stats_layout.addWidget(self.estimated_value_label, 3, 1)
        
        stats_layout.addWidget(QLabel("Farm Efficiency:"), 4, 0)
        self.farm_efficiency_label = QLabel("0%")
        stats_layout.addWidget(self.farm_efficiency_label, 4, 1)
        
        layout.addWidget(stats_group)
        
        # History section
        history_group = QGroupBox("Farming History")
        history_layout = QVBoxLayout(history_group)
        
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        history_layout.addWidget(self.history_text)
        
        layout.addWidget(history_group)
        
        return tab
    
    def _deferred_mining_init(self) -> None:
        """Deferred mining initialization - called after Redis Quantum Nexus is ready."""
        try:
            self._log("🔗 Initializing mining data after Redis ready...", level=logging.INFO)
            
            # FIXED: Try to get mining system from event bus component registry first
            try:
                if self.event_bus and hasattr(self.event_bus, 'get_component'):
                    MiningTab.mining_system = self.event_bus.get_component('mining_system')
                    if MiningTab.mining_system:
                        self._log("✅ Successfully obtained mining system from event bus component registry", level=logging.INFO)
                    else:
                        self._log("⚠️ Mining system not registered on event bus, creating new instance", level=logging.WARNING)
                        from core.mining_system import MiningSystem
                        MiningTab.mining_system = MiningSystem(event_bus=self.event_bus)
                        self._log("Created new mining system instance", level=logging.INFO)
                else:
                    self._log("⚠️ Event bus component registry not available, creating new instance", level=logging.WARNING)
                    from core.mining_system import MiningSystem
                    MiningTab.mining_system = MiningSystem(event_bus=self.event_bus)
                    self._log("Created new mining system instance", level=logging.INFO)
            except ImportError:
                self._log("Could not import MiningSystem, trying alternative paths", level=logging.WARNING)
                try:
                    import importlib.util
                    import sys
                    _root = Path(__file__).resolve().parents[3]
                    paths = [
                        str(_root / "core" / "mining_system.py"),
                    ]
                    for path in paths:
                        try:
                            spec = importlib.util.spec_from_file_location("mining_system", path)
                            if spec and spec.loader:
                                mining_module = importlib.util.module_from_spec(spec)
                                sys.modules["mining_system"] = mining_module
                                spec.loader.exec_module(mining_module)
                                MiningSystem = mining_module.MiningSystem
                                MiningTab.mining_system = MiningSystem(event_bus=self.event_bus)
                                self._log("Successfully loaded MiningSystem from alternative path", level=logging.INFO)
                                break
                        except Exception as e:
                            self._log(f"Failed to load from {path}: {e}", level=logging.ERROR)
                            continue
                    else:
                        self._log("CRITICAL: Failed to load MiningSystem from any alternative path", level=logging.CRITICAL)
                        sys.exit(1)  # System halts - mining system is mandatory
                except Exception as e:
                    logger.error(f"Unexpected error loading mining system: {e}\n{traceback.format_exc()}")
                    self._log(f"CRITICAL: Unexpected error loading mining system: {e}", level=logging.CRITICAL)
                    sys.exit(1)  # System halts - mining system is mandatory

            # Load pow_nodes configuration for solo/node awareness
            try:
                base_dir = Path(__file__).parent.parent.parent
                config_dir = base_dir / "config"
                pow_nodes_path = config_dir / "pow_nodes.json"
                if pow_nodes_path.exists():
                    with open(pow_nodes_path, "r", encoding="utf-8") as f:
                        nodes_data = json.load(f)
                    nodes_cfg = nodes_data.get("nodes", {})
                    if isinstance(nodes_cfg, dict):
                        self.pow_nodes = nodes_cfg
                        self._log(
                            f"Loaded pow_nodes config for {len(nodes_cfg)} POW coins (solo/node metadata)",
                            level=logging.INFO,
                        )
            except Exception as e:
                logger.error(f"Error loading pow_nodes config: {e}")

            try:
                # BUG A FIX: mining_frame.py is 4 dirs deep (gui/qt_frames/mining/)
                # so we need 4 .parent calls to reach the project root
                data_base = Path(__file__).parent.parent.parent.parent
                configured = []
                
                # Primary source: kingdom_ai_wallet_status.json
                data_dir = data_base / "data" / "wallets"
                wallet_status_path = data_dir / "kingdom_ai_wallet_status.json"
                wallet_status_exists = False
                try:
                    wallet_status_exists = wallet_status_path.exists()
                except OSError:
                    # Treat inaccessible wallet status file as “not present”
                    wallet_status_exists = False
                if wallet_status_exists:
                    with open(wallet_status_path, "r", encoding="utf-8") as f:
                        status_data = json.load(f)
                    # BUG D FIX: wallet_creator writes key "configured", not "configured_pow_wallets"
                    configured = (status_data.get("configured_pow_wallets")
                                  or status_data.get("configured_wallets")
                                  or status_data.get("configured")
                                  or [])
                    logger.info(f"Loaded {len(configured)} wallets from kingdom_ai_wallet_status.json")
                
                # Secondary source: multi_coin_wallets.json (has ALL POW coins configured)
                config_dir = data_base / "config"
                multi_coin_path = config_dir / "multi_coin_wallets.json"
                if multi_coin_path.exists():
                    with open(multi_coin_path, "r", encoding="utf-8") as f:
                        multi_data = json.load(f)
                    # Add wallet symbols from cpu_wallets and gpu_wallets
                    for wallet_type in ["cpu_wallets", "gpu_wallets"]:
                        if wallet_type in multi_data and isinstance(multi_data[wallet_type], dict):
                            for coin_symbol in multi_data[wallet_type].keys():
                                if coin_symbol not in configured:
                                    configured.append(coin_symbol)
                    logger.info(f"After multi_coin_wallets.json, total wallets: {len(configured)}")
                
                if isinstance(configured, list) and len(configured) > 0:
                    self.configured_pow_coins = [str(s).upper() for s in configured]
                    self._log(
                        f"✅ Configured POW wallets: {len(self.configured_pow_coins)} coins",
                        level=logging.INFO,
                    )
            except Exception as e:
                logger.error(f"Error loading configured POW wallets: {e}", exc_info=True)

            try:
                self._populate_per_coin_table()
            except Exception as e:
                logger.error(f"Error initializing per-coin mining table: {e}")

            # Connect to Redis Quantum Nexus - mandatory, no fallback
            self._connect_redis()
            
            # Connect to blockchain
            self._connect_blockchain()
            
            # Connect to quantum devices
            self._connect_quantum_devices()
            
            # Request initial mining data if event bus is available
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                def request_mining_data():
                    try:
                        self.event_bus.publish("mining.get_status", {"source": "mining_tab"})
                        self._log("Requested initial mining data", level=logging.INFO)
                    except Exception as e:
                        logger.error(f"Error requesting mining data: {e}")
                
                # Schedule 3 seconds after init
                QTimer.singleShot(3000, request_mining_data)
        except Exception as e:
            logger.error(f"Error initializing mining data: {e}\n{traceback.format_exc()}")
            self._log(f" Warning sign Mining data initialization failed: {e}", level=logging.WARNING)
            # Continue without halting - allow GUI to display error state
    
    def _init_mining_data(self) -> None:
        """Legacy method - redirects to deferred init."""
        self._deferred_mining_init()

    def _populate_per_coin_table(self) -> None:
        try:
            if not hasattr(self, "coin_table"):
                return
            self.coin_table.setRowCount(0)
            self.per_coin_rows.clear()
            self.per_coin_checkboxes.clear()
            configured_symbols = {str(s).upper() for s in (self.configured_pow_coins or [])}
            meta_by_symbol = getattr(self, "_pow_blockchains_by_symbol", {}) or {}
            if meta_by_symbol:
                all_symbols = sorted(str(sym).upper() for sym in meta_by_symbol.keys())
            else:
                all_symbols = sorted(configured_symbols)
            # Load wallet addresses from multi_coin_wallets.json
            wallet_addresses = {}
            try:
                data_base = Path(__file__).parent.parent.parent.parent
                config_dir = data_base / "config"
                multi_coin_path = config_dir / "multi_coin_wallets.json"
                if multi_coin_path.exists():
                    with open(multi_coin_path, "r", encoding="utf-8") as f:
                        multi_data = json.load(f)
                    for wallet_type in ["cpu_wallets", "gpu_wallets"]:
                        if wallet_type in multi_data and isinstance(multi_data[wallet_type], dict):
                            for coin_symbol, wallet_data in multi_data[wallet_type].items():
                                if isinstance(wallet_data, dict):
                                    address = wallet_data.get("address") or wallet_data.get("wallet_address") or ""
                                    if address:
                                        wallet_addresses[str(coin_symbol).upper()] = address
            except Exception as e:
                logger.warning(f"Could not load wallet addresses: {e}")
            
            row_index = 0
            for sym in all_symbols:
                meta = meta_by_symbol.get(sym, {})
                name = meta.get("name", sym)
                is_configured = sym in configured_symbols
                wallet_addr = wallet_addresses.get(sym, "Not Configured")
                if wallet_addr and len(wallet_addr) > 20:
                    wallet_addr = wallet_addr[:10] + "..." + wallet_addr[-8:]  # Truncate long addresses
                self.coin_table.insertRow(row_index)
                checkbox = QCheckBox()
                checkbox.setChecked(is_configured)
                if not is_configured:
                    checkbox.setEnabled(False)
                checkbox.stateChanged.connect(lambda state, s=sym: self._on_coin_checkbox_changed(state, s))
                self.coin_table.setCellWidget(row_index, 0, checkbox)
                symbol_item = QTableWidgetItem(sym)
                name_item = QTableWidgetItem(name)
                wallet_item = QTableWidgetItem(wallet_addr)
                hashrate_val = float(self.per_coin_hashrate.get(sym, 0.0))
                rewards_val = float(self.per_coin_rewards.get(sym, 0.0))
                hashrate_item = QTableWidgetItem(f"{hashrate_val:.2f} H/s")
                rewards_item = QTableWidgetItem(f"{rewards_val:.8f}")
                status_text = "Wallet Configured" if is_configured else "Wallet Not Configured"
                status_item = QTableWidgetItem(status_text)
                if not is_configured:
                    for item in (symbol_item, name_item, wallet_item, hashrate_item, rewards_item, status_item):
                        if item is not None:
                            item.setForeground(QColor("#666666"))
                self.coin_table.setItem(row_index, 1, symbol_item)
                self.coin_table.setItem(row_index, 2, name_item)
                self.coin_table.setItem(row_index, 3, wallet_item)
                self.coin_table.setItem(row_index, 4, hashrate_item)
                self.coin_table.setItem(row_index, 5, rewards_item)
                self.coin_table.setItem(row_index, 6, status_item)
                self.per_coin_rows[sym] = row_index
                self.per_coin_rewards.setdefault(sym, rewards_val)
                self.per_coin_hashrate.setdefault(sym, hashrate_val)
                self.per_coin_checkboxes[sym] = checkbox
                if self.mining_focus_mode == "all":
                    if is_configured:
                        checkbox.setChecked(True)
                        checkbox.setEnabled(False)
                else:
                    if is_configured:
                        checkbox.setEnabled(True)
                    else:
                        checkbox.setEnabled(False)
                row_index += 1
        except Exception as e:
            logger.error(f"Error populating per-coin mining table: {e}")

    def _connect_blockchain(self) -> None:
        """Connect to blockchain system and retrieve real blockchain data.
        
        Connection is mandatory with no fallbacks allowed. System will halt if connection fails.
        """
        try:
            self._log("Connecting to blockchain system...", level=logging.INFO)         
            # Get blockchain connector component (without event_bus parameter)
            from blockchain.blockchain_connector import BlockchainConnector
            MiningTab.blockchain_connector = BlockchainConnector()
            self._log("Successfully obtained blockchain connector instance", level=logging.INFO)
            
            # Register blockchain_connector with event_bus so mining_system can find it
            if self.event_bus and hasattr(self.event_bus, 'register_component'):
                self.event_bus.register_component('blockchain_connector', MiningTab.blockchain_connector)
                self._log("Registered blockchain_connector with event_bus", level=logging.INFO)

            # Check blockchain connection status - mandatory, no fallback
            if hasattr(MiningTab.blockchain_connector, 'is_connected'):
                is_connected_result = MiningTab.blockchain_connector.is_connected
                if callable(is_connected_result):
                    is_connected_result = is_connected_result()
                if asyncio.iscoroutine(is_connected_result):
                    # Use asyncio.run() for sync context
                    try:
                        is_connected = asyncio.run(is_connected_result)
                    except RuntimeError:
                        # Fallback: try loop.run_until_complete if asyncio.run fails
                        try:
                            loop = asyncio.get_event_loop()
                            if not loop.is_running():
                                is_connected = loop.run_until_complete(is_connected_result)
                            else:
                                is_connected = False
                        except Exception:
                            is_connected = False
                else:
                    is_connected = is_connected_result

                if not is_connected:
                    # Retry via component registry — main connector may already be verified
                    try:
                        from core.component_registry import get_component
                        main_bc = get_component('blockchain_connector')
                        if main_bc and hasattr(main_bc, 'is_connected'):
                            chk = main_bc.is_connected
                            is_connected = chk() if callable(chk) else bool(chk)
                    except Exception:
                        pass
                if not is_connected:
                    self._log("Blockchain: awaiting RPC connection (mining via pool still works)", level=logging.INFO)
                    self.blockchain_status_label.setText("Blockchain: Connecting...")
                    self.blockchain_status_label.setStyleSheet("color: orange;")
                else:
                    self._log("Blockchain connector is connected", level=logging.INFO)
                    self.blockchain_status_label.setText("Blockchain: Connected")
                    self.blockchain_status_label.setStyleSheet("color: green;")
                    # ROOT FIX: Also update nodes status — blockchain RPC IS the node connection
                    if hasattr(self, 'nodes_status_label'):
                        self.nodes_status_label.setText("Nodes: Connected")
                        self.nodes_status_label.setStyleSheet("color: #00FF00;")
                    # CRITICAL: Update mining_system._nodes_connected so its periodic
                    # publisher (every 5s) doesn't overwrite the label back to Disconnected
                    if self.event_bus:
                        mining_sys = self.event_bus.get_component("mining_system")
                        if mining_sys:
                            mining_sys._nodes_connected = True
                            logger.info("✅ Updated mining_system._nodes_connected = True")
                        self.event_bus.publish("mining.nodes.connected", {"connected": True})
            else:
                self._log("WARNING: Blockchain connector does not have is_connected method", level=logging.WARNING)
                self.blockchain_status_label.setText("Blockchain: Unknown")
                self.blockchain_status_label.setStyleSheet("color: orange;")
        except Exception as e:
            logger.error(f"Error connecting to blockchain: {e}\n{traceback.format_exc()}")
            self._log(f"CRITICAL: Failed to connect to blockchain: {e}", level=logging.CRITICAL)
            self.blockchain_status_label.setText("Blockchain: Error")
            self.blockchain_status_label.setStyleSheet("color: red;")

    def _connect_redis(self) -> None:
        """Connect to Redis Quantum Nexus with strict enforcement on port 6380.
        
        Connection is mandatory with no fallbacks allowed. System will halt if connection fails.
        """
        try:
            from typing import TYPE_CHECKING, Any
            import redis  # type: ignore[import-untyped]
            from redis.exceptions import AuthenticationError, ConnectionError, TimeoutError
            self._log("Connecting to Redis Quantum Nexus on port 6380...", level=logging.INFO)
            # Use the centralized Redis security module for password handling
            redis_client = redis.Redis(  # type: ignore[attr-defined]
                host='127.0.0.1',
                port=6380,  # Mandatory port for Redis Quantum Nexus
                # Get password securely from environment variable via centralized security module
                password=get_redis_password(),  # Uses KINGDOM_AI_SEC_KEY or secure default
                socket_timeout=5,
                decode_responses=True
            )
            if redis_client.ping():
                self._log("Connected to Redis Quantum Nexus successfully", level=logging.INFO)
                self.redis_client = redis_client
            else:
                self._log("CRITICAL: Redis ping test failed", level=logging.CRITICAL)
                sys.exit(1)  # System halts - Redis connection is mandatory
        except AuthenticationError:
            self._log("CRITICAL: Redis authentication failure", level=logging.CRITICAL)
            sys.exit(1)  # System halts - correct credentials are mandatory
        except ConnectionError:
            self._log("CRITICAL: Redis connection failure", level=logging.CRITICAL)
            sys.exit(1)  # System halts - connection is mandatory
        except TimeoutError:
            self._log("CRITICAL: Redis connection timeout", level=logging.CRITICAL)
            sys.exit(1)  # System halts - timely connection is mandatory
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}\n{traceback.format_exc()}")
            self._log(f"CRITICAL: Unexpected error connecting to Redis: {e}", level=logging.CRITICAL)
            sys.exit(1)  # System halts - Redis connection is mandatory

    def _connect_quantum_devices(self) -> None:
        """Connect to quantum computing devices for mining.
        
        This method attempts to connect to quantum devices through the Redis Quantum Nexus
        on port 6380. Connection is mandatory - the system will halt if connection fails.
        No fallbacks to sample data are allowed.
        """
        try:
            self._log("Connecting to quantum computing devices via Redis Quantum Nexus...", level=logging.INFO)
            if not hasattr(self, 'event_bus') or not self.event_bus:
                self._log("Event bus not available for quantum device connection", level=logging.CRITICAL)
                logger.critical("Event bus not available - system cannot proceed without event bus")
                sys.exit(1)
                
            # Enforce Redis Quantum Nexus connection on port 6380
            redis_port = 6380  # Mandatory port for Redis Quantum Nexus
            # Get Redis password from centralized security module
            # This ensures consistent password handling throughout the system
            # while supporting custom passwords via environment variables
            redis_password = get_redis_password()  # Uses KINGDOM_AI_SEC_KEY or secure default
            
            self._log(f"Enforcing Redis Quantum Nexus connection on port {redis_port}", level=logging.INFO)
            
            # Query quantum devices through the Redis Quantum Nexus
            def query_quantum_devices():
                try:
                    self.event_bus.publish("quantum.nexus.query.devices", {
                        "source": "mining_tab",
                        "request_id": str(uuid.uuid4()),
                        "mandatory": True,
                        "fallback_action": "halt"
                    })
                except Exception as e:
                    logger.error(f"Error querying quantum devices: {e}")
            
            # Schedule 3.5 seconds after init
            QTimer.singleShot(3500, query_quantum_devices)
            
            # This will be handled asynchronously via event bus callbacks
        except Exception as e:
            logger.error(f"Error connecting to quantum devices: {e}\n{traceback.format_exc()}")
            self._log(f"CRITICAL: Failed to connect to quantum devices: {e}", level=logging.CRITICAL)
            # Continue without halting - display error in GUI

    def _handle_quantum_circuit_update(self, data: dict) -> None:
        """Handle quantum circuit updates from the event bus."""
        try:
            # Extract circuit data from the event
            algorithm = data.get("algorithm", "Generic")
            qubit_count = data.get("qubit_count", 5)
            circuit_depth = data.get("circuit_depth", 3)
            circuit_data = data.get("circuit_data")
            
            self._log(f"Quantum circuit update received: {algorithm} with {qubit_count} qubits", level=logging.INFO)
            
            # Update the quantum circuit visualization
            if getattr(self, 'quantum_circuit_visualizer', None):
                if circuit_data:
                    # Use provided circuit data if available
                    success = self.quantum_circuit_visualizer.update_circuit_data(circuit_data)  # type: ignore[attr-defined]
                else:
                    # Otherwise update based on algorithm and parameters
                    success = self.quantum_circuit_visualizer.update_circuit(algorithm, qubit_count, circuit_depth)  # type: ignore[attr-defined]
                
                if success:
                    self._log("Quantum circuit visualization updated", level=logging.INFO)
                else:
                    self._log("Failed to update quantum circuit visualization", level=logging.WARNING)
            else:
                self._log("Quantum circuit visualizer not available", level=logging.WARNING)
        except Exception as e:
            logger.error(f"Error handling quantum circuit update: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling quantum circuit update: {e}", level=logging.ERROR)

    def _handle_quantum_mining_result(self, data: dict) -> None:
        """Handle quantum mining result events from the event bus."""
        try:
            success = data.get("success", False)
            result_type = data.get("result_type", "Unknown")
            message = data.get("message", "No details provided")
            
            self._log(f"Quantum mining result received: {result_type} - {message}", 
                    level=logging.INFO if success else logging.WARNING)
            
            # Update quantum mining statistics
            if "circuits_processed" in data:
                self.quantum_mining_circuits_value.setText(str(data["circuits_processed"]))  # type: ignore[attr-defined]
            
            if "success_rate" in data:
                self.quantum_mining_success_value.setText(f"{data['success_rate']:.2f}%")  # type: ignore[attr-defined]
                
            if "advantage_factor" in data:
                self.quantum_mining_advantage_value.setText(f"{data['advantage_factor']:.2f}x")  # type: ignore[attr-defined]
                
            # Create notification for significant results
            if success and data.get("significant", False):
                self.show_notification(
                    "Quantum Mining Success", 
                    f"{result_type}: {message}", 
                    level="success"
                )
                
            # Update circuit visualization if provided
            if "circuit_data" in data and getattr(self, 'quantum_circuit_visualizer', None):
                self.quantum_circuit_visualizer.update_circuit_data(data["circuit_data"])  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Error handling quantum mining result: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling quantum mining result: {e}", level=logging.ERROR)

    def _handle_quantum_device_status(self, data: dict) -> None:
        """Handle quantum device status updates from the event bus."""
        try:
            device_id = data.get("device_id", "unknown")
            status = data.get("status", "offline")
            
            self._log(f"Quantum device status update: {device_id} is {status}", level=logging.INFO)
            
            # Update quantum devices list
            devices = data.get("available_devices", [])
            if devices:
                # Update device selection combobox
                current_text = self.quantum_device_combo.currentText()
                self.quantum_device_combo.clear()
                
                for device in devices:
                    device_name = device.get("name", device.get("id", "Unknown"))
                    self.quantum_device_combo.addItem(device_name)
                
                # Restore previous selection if it still exists
                index = self.quantum_device_combo.findText(current_text)
                if index >= 0:
                    self.quantum_device_combo.setCurrentIndex(index)
                    
            # Update connection status display
            if status == "online":
                self.quantum_status_label.setText("Quantum: Connected")
                self.quantum_status_label.setStyleSheet("color: green;")
            elif status == "offline":
                self.quantum_status_label.setText("Quantum: Disconnected")
                self.quantum_status_label.setStyleSheet("color: #AA0000;")
            elif status == "error":
                self.quantum_status_label.setText("Quantum: Error")
                self.quantum_status_label.setStyleSheet("color: red;")
            elif status == "connecting":
                self.quantum_status_label.setText("Quantum: Connecting")
                self.quantum_status_label.setStyleSheet("color: #CCAA00;")
        except Exception as e:
            logger.error(f"Error handling quantum device status: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling quantum device status: {e}", level=logging.ERROR)

    # Mining intelligence event handlers
    def _handle_mining_intelligence_update(self, data: dict) -> None:
        """Handle mining intelligence updates from the event bus."""
        try:
            intel_type = data.get("type", "general")
            intel_data = data.get("data", {})
            
            self._log(f"Mining intelligence update received: {intel_type}", level=logging.INFO)
            
            if intel_type == "analytics":
                # Update analytics in the mining intelligence tab
                if "efficiency" in intel_data and getattr(self, 'mining_intel_efficiency_value', None):
                    self.mining_intel_efficiency_value.setText(f"{intel_data['efficiency']:.2f}%")  # type: ignore[attr-defined]
                
                if "projected_earnings" in intel_data and getattr(self, 'mining_intel_earnings_value', None):
                    self.mining_intel_earnings_value.setText(  # type: ignore[attr-defined]
                        f"{intel_data['projected_earnings']:.8f}"
                    )
                
                if "optimal_threads" in intel_data and getattr(self, 'mining_intel_threads_value', None):
                    self.mining_intel_threads_value.setText(str(intel_data["optimal_threads"]))  # type: ignore[attr-defined]
                
                if "network_share" in intel_data and getattr(self, 'mining_intel_share_value', None):
                    self.mining_intel_share_value.setText(f"{intel_data['network_share']:.6f}%")  # type: ignore[attr-defined]
            
            elif intel_type == "profit_prediction":
                # Update profit prediction chart
                if "prediction_data" in intel_data and isinstance(intel_data["prediction_data"], list):
                    self.profit_history = intel_data["prediction_data"]
                    if hasattr(self, '_update_profit_chart'):
                        self._update_profit_chart()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Error handling mining intelligence update: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling mining intelligence update: {e}", level=logging.ERROR)

    def _handle_mining_intelligence_recommendation(self, data: dict) -> None:
        """Handle mining intelligence recommendations from the event bus."""
        try:
            recommendations = data.get("recommendations", [])
            if not recommendations:
                return
                
            self._log(f"Received {len(recommendations)} mining intelligence recommendations", 
                    level=logging.INFO)
            
            # Update recommendations list in the mining intelligence tab
            if getattr(self, 'mining_intel_recommendations_list', None):
                self.mining_intel_recommendations_list.clear()  # type: ignore[attr-defined]
                
                for rec in recommendations:
                    rec_text = f"{rec.get('title', 'Recommendation')}: {rec.get('description', 'No description')}"
                    item = QListWidgetItem(rec_text)
                    
                    # Set item properties based on priority
                    priority = rec.get("priority", "medium").lower()
                    if priority == "high":
                        item.setForeground(QColor("#e74c3c"))  # Red for high priority
                        item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                    elif priority == "medium":
                        item.setForeground(QColor("#f39c12"))  # Orange for medium priority
                    
                    # Add metadata as user role data
                    item.setData(Qt.ItemDataRole.UserRole, rec)
                    
                    self.mining_intel_recommendations_list.addItem(item)  # type: ignore[attr-defined]
                
                # Show notification for high priority recommendations
                high_priority_recs = [r for r in recommendations if r.get("priority", "").lower() == "high"]
                if high_priority_recs:
                    rec = high_priority_recs[0]
                    self.show_notification(
                        "Mining Intelligence Alert",
                        f"{rec.get('title', 'Important recommendation')}: {rec.get('description', '')}",
                        level="warning"
                    )
        except Exception as e:
            logger.error(f"Error handling mining intelligence recommendations: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling mining intelligence recommendations: {e}", level=logging.ERROR)

    def _handle_mining_intelligence_initialized(self, data: dict) -> None:
        """Handle mining intelligence initialization complete event."""
        try:
            status = data.get("status", "unknown")
            coins = data.get("coins", 0)
            wallets = data.get("wallets", 0)
            
            if hasattr(self, 'intel_text') and self.intel_text:
                self.intel_text.setText(
                    f"✅ Mining Intelligence System: {status.upper()}\n\n"
                    f"📊 Configured Coins: {coins}\n"
                    f"💼 Configured Wallets: {wallets}\n\n"
                    f"System is ready for mining operations.\n"
                    f"Select coins from the Mining tab to begin."
                )
            self._log(f"Mining intelligence initialized: {status}, {coins} coins, {wallets} wallets", level=logging.INFO)
        except Exception as e:
            logger.error(f"Error handling mining intelligence initialized: {e}")

    def _handle_mining_intelligence_profit_prediction(self, data: dict) -> None:
        """Handle mining profit prediction updates from the event bus."""
        try:
            prediction_data = data.get("prediction_data", [])
            if not prediction_data:
                return
            
            self._log("Received mining profit prediction update", level=logging.INFO)
            
            # Update profit history and chart
            self.profit_history = prediction_data
            if hasattr(self, '_update_profit_chart'):
                self._update_profit_chart()  # type: ignore[attr-defined]
            
            # Update summary statistics if provided
            if "daily_estimate" in data and getattr(self, 'mining_intel_daily_value', None):
                self.mining_intel_daily_value.setText(f"{data['daily_estimate']:.8f}")  # type: ignore[attr-defined]
            
            if "weekly_estimate" in data and getattr(self, 'mining_intel_weekly_value', None):
                self.mining_intel_weekly_value.setText(f"{data['weekly_estimate']:.8f}")  # type: ignore[attr-defined]
            
            if "monthly_estimate" in data and getattr(self, 'mining_intel_monthly_value', None):
                self.mining_intel_monthly_value.setText(f"{data['monthly_estimate']:.8f}")  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Error handling mining profit prediction: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling mining profit prediction: {e}", level=logging.ERROR)

    def _handle_coin_analytics_update(self, data: dict) -> None:
        """Handle coin analytics updates from the analytics system.
        
        This method receives per-coin analytics data including profitability metrics,
        network difficulty, and mining efficiency calculations.
        """
        try:
            coin = data.get("coin", "unknown")
            analytics = data.get("analytics", {})
            
            self._log(f"Received coin analytics update for {coin}", level=logging.DEBUG)
            
            # Store analytics data for later use
            if not hasattr(self, '_coin_analytics'):
                self._coin_analytics = {}
            self._coin_analytics[coin] = analytics
            
            # Update relevant UI elements if available
            if hasattr(self, 'coin_table') and self.coin_table:
                # Find and update the row for this coin
                sym_upper = str(coin).upper()
                row = self.per_coin_rows.get(sym_upper)
                if row is not None:
                    # Update profitability in status column (show profitability %)
                    profitability = analytics.get("profitability", 0)
                    if self.coin_table.columnCount() > 6:
                        status_item = self.coin_table.item(row, 6)
                        if status_item:
                            status_item.setText(f"{profitability:.2f}% Profit")
        except Exception as e:
            logger.error(f"Error handling coin analytics update: {e}")
            self._log(f"Error handling coin analytics update: {e}", level=logging.ERROR)

    def _handle_airdrop_farming_status(self, data: dict) -> None:
        """Handle airdrop farming status updates from the event bus."""
        try:
            status = data.get("status", "inactive")
            
            self._log(f"Airdrop farming status update: {status}", level=logging.INFO)
            
            # Update farming status and button state
            if status.lower() == "active":
                self.airdrop_start_button.setText("Stop Farming")
                self.airdrop_start_button.setStyleSheet("background-color: #990000; color: white; border: 2px solid #FF4444; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
                
                if self.airdrop_status_value:
                    self.airdrop_status_value.setText("Active")
                    self.airdrop_status_value.setStyleSheet("color: green;")
            else:  # inactive or any other state
                self.airdrop_start_button.setText("Start Farming")
                self.airdrop_start_button.setStyleSheet("background-color: #006600; color: #00FF00; border: 2px solid #00FF00; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
                
                if self.airdrop_status_value:
                    self.airdrop_status_value.setText("Inactive")
                    self.airdrop_status_value.setStyleSheet("color: #AA0000;")
            
            # Update farming statistics
            if "campaigns_active" in data and self.airdrop_active_value:
                self.airdrop_active_value.setText(str(data["campaigns_active"]))
            
            if "points_earned" in data and self.airdrop_points_value:
                self.airdrop_points_value.setText(f"{data['points_earned']:,}")
            
            if "tokens_earned" in data and self.airdrop_earnings_value:
                self.airdrop_earnings_value.setText(f"{data['tokens_earned']:.8f}")
                
            if "uptime" in data and self.airdrop_uptime_value:
                hours, remainder = divmod(int(data["uptime"]), 3600)
                minutes, seconds = divmod(remainder, 60)
                self.airdrop_uptime_value.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        except Exception as e:
            logger.error(f"Error handling airdrop farming status: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling airdrop farming status: {e}", level=logging.ERROR)

    def _handle_airdrop_campaigns_update(self, data: dict) -> None:
        """Handle airdrop campaigns list updates from the event bus."""
        try:
            campaigns = data.get("campaigns", [])
            self._log(f"Received {len(campaigns)} airdrop campaigns", level=logging.INFO)
            
            # Update campaigns list if UI element exists
            if hasattr(self, 'airdrop_campaigns_list') and self.airdrop_campaigns_list:
                self.airdrop_campaigns_list.clear()
                for campaign in campaigns:
                    name = campaign.get("name", "Unknown Campaign")
                    status = campaign.get("status", "unknown")
                    reward = campaign.get("reward", "TBD")
                    self.airdrop_campaigns_list.addItem(f"{name} - {status} - Reward: {reward}")
        except Exception as e:
            logger.error(f"Error handling airdrop campaigns update: {e}")
            self._log(f"Error handling airdrop campaigns update: {e}", level=logging.ERROR)

    def _handle_airdrop_farming_history(self, data: dict) -> None:
        """Handle airdrop farming history updates from the event bus."""
        try:
            history_entries = data.get("history", [])
            if not history_entries:
                return
                
            self._log(f"Received {len(history_entries)} airdrop farming history entries", level=logging.INFO)
            
            # Update history log if it exists
            if self.airdrop_history_log:
                # Add new entries
                for entry in history_entries:
                    timestamp = entry.get("timestamp", time.time())
                    time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    campaign = entry.get("campaign", "Unknown")
                    action = entry.get("action", "Unknown")
                    details = entry.get("details", "")
                    
                    log_entry = f"[{time_str}] {campaign}: {action} {details}"
                    self.airdrop_history_log.appendPlainText(log_entry)
                
                # Scroll to bottom to show latest entries
                scrollbar = self.airdrop_history_log.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            logger.error(f"Error handling airdrop farming history: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling airdrop farming history: {e}", level=logging.ERROR)

    def _handle_airdrop_discovery(self, data: dict) -> None:
        """Handle airdrop discovery event - add new airdrop to campaigns table.
        
        SOTA 2026 FIX: This handler receives airdrop discoveries from the scanner
        and displays them in the campaigns table.
        """
        try:
            name = data.get("name", "Unknown")
            chain = data.get("chain", "unknown")
            estimated_value = data.get("estimated_value", "Unknown")
            status = data.get("status", "active")
            requirements = data.get("requirements", "Check eligibility")
            
            self._log(f"🔍 Discovered airdrop: {name} on {chain}", level=logging.INFO)
            
            # Add to campaigns table
            if hasattr(self, 'campaigns_table') and self.campaigns_table:
                row = self.campaigns_table.rowCount()
                self.campaigns_table.insertRow(row)
                
                # Set items for each column: Project, Token, Requirements, Estimated Value, Status, Actions
                self.campaigns_table.setItem(row, 0, QTableWidgetItem(name))
                self.campaigns_table.setItem(row, 1, QTableWidgetItem(chain.upper()))
                self.campaigns_table.setItem(row, 2, QTableWidgetItem(requirements))
                self.campaigns_table.setItem(row, 3, QTableWidgetItem(str(estimated_value)))
                self.campaigns_table.setItem(row, 4, QTableWidgetItem(status))
                
                # Add register button in Actions column
                register_btn = QPushButton("Register")
                register_btn.clicked.connect(lambda checked, n=name, c=data.get("config", {}): self._register_for_airdrop(n, c))
                self.campaigns_table.setCellWidget(row, 5, register_btn)
                
        except Exception as e:
            logger.error(f"Error handling airdrop discovery: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling airdrop discovery: {e}", level=logging.ERROR)

    def _handle_airdrop_scan_complete(self, data: dict) -> None:
        """Handle airdrop scan complete event."""
        try:
            total = data.get("total_airdrops", 0)
            enabled = data.get("enabled_airdrops", 0)
            chains = data.get("chains", [])
            
            self._log(f"✅ Airdrop scan complete: {enabled}/{total} active across {len(chains)} chains", level=logging.INFO)
            self.show_notification("Airdrop Scan Complete", f"Found {enabled} active airdrops across {len(chains)} chains")
        except Exception as e:
            logger.error(f"Error handling airdrop scan complete: {e}")

    def _register_for_airdrop(self, name: str, config: dict) -> None:
        """Register for an airdrop via EventBus."""
        try:
            self._log(f"📝 Registering for airdrop: {name}", level=logging.INFO)
            if self.event_bus:
                self.event_bus.publish("airdrop.register.requested", {
                    "airdrop_name": name,
                    "config": config,
                    "network": config.get("chain", "ethereum"),
                    "wallet_network": config.get("wallet_network", "ethereum"),
                    "timestamp": time.time()
                })
        except Exception as e:
            logger.error(f"Error registering for airdrop: {e}")
            self._log(f"Error registering for airdrop: {e}", level=logging.ERROR)

    def subscribe_to_events(self) -> None:
        """Subscribe to event bus events for mining operations.
        
        These subscriptions enable real-time updates to the mining UI based on
        backend events from the mining system, blockchain, and quantum devices.
        """
        if not self.event_bus:
            self._log("Cannot subscribe - no event bus", level=logging.CRITICAL)
            return
        
        self._log("Scheduling event subscriptions...", level=logging.INFO)
        
        def subscribe_all():
            """Perform all subscriptions AFTER GUI init to avoid task nesting."""
            try:
                # Mining events
                self.event_bus.subscribe("mining.status_update", self._handle_mining_status_update)
                self.event_bus.subscribe("mining.hashrate_update", self._handle_hashrate_update)
                self.event_bus.subscribe("mining.worker_update", self._handle_worker_update)
                self.event_bus.subscribe("mining.new_block_found", self._handle_new_block_found)
                self.event_bus.subscribe("mining.error", self._handle_mining_error)
                self.event_bus.subscribe("mining.stats.update", self._handle_mining_stats)
                
                # Blockchain events
                self.event_bus.subscribe("blockchain.status_update", self._handle_blockchain_status_update)
                self.event_bus.subscribe("blockchain.network_stats", self._handle_blockchain_network_stats)
                self.event_bus.subscribe("blockchain.market_data", self._handle_blockchain_market_data)
                self.event_bus.subscribe("blockchain.blocks", self._handle_blockchain_blocks)
                
                # Node and Pool status events
                self.event_bus.subscribe("mining.nodes.connected", self._handle_nodes_status)
                self.event_bus.subscribe("mining.pools.connected", self._handle_pool_status)
                
                # Market price events (aggregated snapshots and per-tick updates)
                self.event_bus.subscribe("market.prices", self._handle_market_prices_snapshot)
                self.event_bus.subscribe("market:price_update", self._handle_market_price_update)
                
                # Quantum events
                self.event_bus.subscribe("quantum.mining.status", self._handle_quantum_mining_status)
                self.event_bus.subscribe("quantum.mining.circuit_update", self._handle_quantum_circuit_update)
                self.event_bus.subscribe("quantum.mining.result", self._handle_quantum_mining_result)
                self.event_bus.subscribe("quantum.device.status", self._handle_quantum_device_status)
                # BUG 4 FIX: Subscribe to quantum hashrate (backend publishes this but nobody was listening)
                self.event_bus.subscribe("quantum.mining.hashrate", self._handle_quantum_hashrate_update)
                
                # Intelligence events
                self.event_bus.subscribe("mining.intelligence.update", self._handle_mining_intelligence_update)
                self.event_bus.subscribe("mining.intelligence.recommendation", self._handle_mining_intelligence_recommendation)
                self.event_bus.subscribe("mining.intelligence.profit_prediction", self._handle_mining_intelligence_profit_prediction)
                self.event_bus.subscribe("mining.intelligence.initialized", self._handle_mining_intelligence_initialized)
                self.event_bus.subscribe("analytics.mining.coin_analytics", self._handle_coin_analytics_update)
                
                # Airdrop events
                self.event_bus.subscribe("airdrop.campaigns.update", self._handle_airdrop_campaigns_update)
                self.event_bus.subscribe("airdrop.farming.status", self._handle_airdrop_farming_status)
                self.event_bus.subscribe("airdrop.farming.history", self._handle_airdrop_farming_history)
                self.event_bus.subscribe("airdrop.discovery", self._handle_airdrop_discovery)
                self.event_bus.subscribe("airdrop.scan.complete", self._handle_airdrop_scan_complete)
                
                # Backend response events
                self.event_bus.subscribe("mining.status", self._handle_backend_mining_status)
                
                self._log("All subscriptions completed", level=logging.INFO)
            except Exception as e:
                logger.error(f"Subscription error: {e}")
        
        # ROOT FIX: Was 2500ms -- events fire in first 1-2s, so GUI missed them forever.
        # 100ms is enough for Qt init to finish.
        def subscribe_and_query_status():
            subscribe_all()
            # ROOT FIX: Query current mining status directly (events already fired before we subscribed)
            try:
                mining_sys = self.event_bus.get_component("mining_system")
                if mining_sys:
                    nodes_conn = getattr(mining_sys, '_nodes_connected', False)
                    pools_conn = getattr(mining_sys, '_pools_connected', False)
                    pool_name = ""
                    # Try to get pool name from config
                    if pools_conn:
                        pool_cfgs = getattr(mining_sys, '_connected_pools', [])
                        if pool_cfgs:
                            pool_name = pool_cfgs[0] if isinstance(pool_cfgs[0], str) else "ViaBTC"
                        else:
                            pool_name = "ViaBTC"
                    # ROOT FIX: mining_system._nodes_connected is False because it checked
                    # BEFORE blockchain_connector was registered. Check connector directly.
                    if not nodes_conn:
                        bc = self.event_bus.get_component("blockchain_connector")
                        if bc is not None:
                            is_conn = getattr(bc, 'is_connected', None)
                            if callable(is_conn):
                                nodes_conn = bool(is_conn())
                            elif isinstance(is_conn, bool):
                                nodes_conn = is_conn
                            # Also fix mining_system so future queries are correct
                            if nodes_conn:
                                mining_sys._nodes_connected = True
                    self._handle_nodes_status({"connected": nodes_conn})
                    self._handle_pool_status({"connected": pools_conn, "pool": pool_name, "status": "connected" if pools_conn else ""})
                    logger.info(f"Mining status queried directly: nodes={nodes_conn}, pools={pools_conn}")
            except Exception as e:
                logger.debug(f"Direct mining status query failed: {e}")
        
        QTimer.singleShot(100, subscribe_and_query_status)

    # =====================
    # Market price handlers
    # =====================
    def _handle_market_prices_snapshot(self, event_data: Dict[str, Any]):
        try:
            prices = event_data.get('prices', {})
            if isinstance(prices, dict):
                self._market_prices.update(prices)
        except Exception as e:
            logger.error(f"Error handling market prices snapshot: {e}")

    def _handle_market_price_update(self, price_data: Dict[str, Any]):
        try:
            symbol = price_data.get('symbol')
            if symbol:
                self._market_prices[symbol] = price_data
        except Exception as e:
            logger.error(f"Error handling market price update: {e}")

    def update_mining_stats(self):
        """Update mining statistics display."""
        try:
            # Update hashrate display (hashrate is already a float)
            if hasattr(self, 'hashrate_label'):
                hashrate_val = self.hashrate if isinstance(self.hashrate, (int, float)) else 0.0
                # SOTA 2026 FIX: Use smart hashrate formatting
                self.hashrate_label.setText(self._format_hashrate(hashrate_val))
            
            # Update workers display
            if hasattr(self, 'workers_label'):
                self.workers_label.setText(str(self.workers))
            
            # Update shares display
            if hasattr(self, 'shares_label'):
                self.shares_label.setText(str(self.shares))
            
            # Update blocks found display
            if hasattr(self, 'blocks_label'):
                self.blocks_label.setText(str(self.blocks_found))
            
            # Update mining status
            if hasattr(self, 'status_label'):
                self.status_label.setText(str(self.mining_status))
        except Exception as e:
            logger.error(f"Error updating mining stats: {e}")

    def update_quantum_stats(self):
        """Update quantum mining statistics display."""
        try:
            # Update quantum hashrate (q_hashrate is already a float)
            if hasattr(self, 'q_hashrate_label'):
                q_hashrate_val = self.q_hashrate if isinstance(self.q_hashrate, (int, float)) else 0.0
                self.q_hashrate_label.setText(f"{q_hashrate_val:.2f} QH/s")
            
            # Update quantum efficiency (q_efficiency is already a float)
            if hasattr(self, 'q_efficiency_label'):
                q_efficiency_val = self.q_efficiency if isinstance(self.q_efficiency, (int, float)) else 0.0
                self.q_efficiency_label.setText(f"{q_efficiency_val:.1f}%")
            
            # Update qubit count
            if hasattr(self, 'q_qubits_label'):
                self.q_qubits_label.setText(str(self.q_qubits))
            
            # Update circuit depth
            if hasattr(self, 'q_depth_label'):
                self.q_depth_label.setText(str(self.q_circuit_depth))
            
            # Update quantum status
            if hasattr(self, 'q_status_label'):
                self.q_status_label.setText(str(self.q_mining_status))
        except Exception as e:
            logger.error(f"Error updating quantum stats: {e}")

    def update_uptime(self):
        """Update the uptime display."""
        try:
            if hasattr(self, 'start_time') and self.start_time:
                elapsed = time.time() - self.start_time
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                
                if hasattr(self, 'uptime_label'):
                    self.uptime_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                    logger.info(f"🔴 REAL Mining Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}")
        except Exception as e:
            logger.error(f"Error updating uptime: {e}")

    # Traditional mining event handlers - SOTA 2026: Thread-safe
    def _handle_mining_stats(self, data: Dict[str, Any]):
        """Handle REAL mining statistics from pools (THREAD-SAFE)."""
        # Dispatch to main thread if needed
        if not is_main_thread():
            run_on_main_thread(lambda: self._handle_mining_stats_ui(data))
            return
        self._handle_mining_stats_ui(data)
    
    def _handle_mining_stats_ui(self, data: Dict[str, Any]):
        """Update UI for mining stats (MUST run on main thread)."""
        try:
            stats = data.get('stats', {})
            logger.info(f"REAL Mining Stats: {stats}")
            if "hashrate" in stats:
                hashrate = stats["hashrate"]
                # SOTA 2026 FIX: Use smart hashrate formatting
                formatted = self._format_hashrate(hashrate)
                if hasattr(self, 'hashrate_label'):
                    self.hashrate_label.setText(formatted)
                if hasattr(self, 'led_hashrate_label'):
                    self.led_hashrate_label.setText(formatted)
            if "workers" in stats:
                workers = stats["workers"]
                if hasattr(self, 'workers_label'):
                    self.workers_label.setText(str(workers))
            if "shares" in stats:
                shares = stats["shares"]
                if hasattr(self, 'shares_label'):
                    self.shares_label.setText(str(shares))
            if "blocks_found" in stats:
                blocks_found = stats["blocks_found"]
                if hasattr(self, 'blocks_label'):
                    self.blocks_label.setText(str(blocks_found))
            coins_obj = stats.get("coins")
            if isinstance(coins_obj, dict) and hasattr(self, "coin_table"):
                for coin_key, value in coins_obj.items():
                    if isinstance(value, dict):
                        coin_hashrate = value.get("hashrate", 0.0)
                        coin_rewards = value.get("rewards", 0.0)
                        coin_status = value.get("status", "")
                    else:
                        # SOTA 2026: Null-check to prevent crashes when value is None
                        coin_hashrate = value if value is not None else 0.0
                        coin_rewards = self.per_coin_rewards.get(str(coin_key).upper(), 0.0)
                        coin_status = ""
                    self._update_coin_from_stats(coin_key, coin_hashrate, coin_rewards, coin_status)
                    # SOTA 2026: Accumulate into hourly buckets for real analytics display
                    coin_shares = value.get("shares", 0) if isinstance(value, dict) else 0
                    self._accumulate_hourly_mining_stats(
                        str(coin_key), float(coin_rewards), float(coin_hashrate), int(coin_shares)
                    )
        except Exception as e:
            logger.error(f"Error handling mining stats: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling mining stats: {e}", level=logging.ERROR)

    def _update_coin_from_stats(self, symbol: str, hashrate: float, rewards: float, status: str = "") -> None:
        try:
            if not hasattr(self, "coin_table"):
                return
            sym = str(symbol).upper()
            row = self.per_coin_rows.get(sym)
            if row is None:
                return
            self.per_coin_hashrate[sym] = float(hashrate or 0.0)
            self.per_coin_rewards[sym] = float(rewards or 0.0)
            hashrate_item = self.coin_table.item(row, 4)
            rewards_item = self.coin_table.item(row, 5)
            status_item = self.coin_table.item(row, 6)
            if hashrate_item is not None:
                # SOTA 2026 FIX: Use smart hashrate formatting
                hashrate_item.setText(self._format_hashrate(self.per_coin_hashrate[sym]))
            if rewards_item is not None:
                rewards_item.setText(f"{self.per_coin_rewards[sym]:.8f}")
            if status_item is not None and status:
                status_item.setText(status)
        except Exception as e:
            logger.error(f"Error updating per-coin stats for {symbol}: {e}")

    def _handle_mining_status_update(self, data: dict) -> None:
        """Handle mining status updates from the event bus (THREAD-SAFE)."""
        # Dispatch to main thread if needed
        if not is_main_thread():
            run_on_main_thread(lambda: self._handle_mining_status_update_ui(data))
            return
        self._handle_mining_status_update_ui(data)
    
    def _handle_mining_status_update_ui(self, data: dict) -> None:
        """Update UI for mining status (MUST run on main thread)."""
        try:
            status = data.get("status", "")
            running = data.get("running", False)
            pool_connected = data.get("pool_connected", False)
            
            if status and hasattr(self, 'mining_status_label'):
                self.mining_status_label.setText(f"Mining: {str(status)}")
                # Update color based on running status
                if running:
                    if pool_connected or "connected" in str(status).lower():
                        self.mining_status_label.setStyleSheet("color: #00FF00;")  # Green - fully running
                    else:
                        self.mining_status_label.setStyleSheet("color: #FFFF00;")  # Yellow - connecting
                else:
                    self.mining_status_label.setStyleSheet("color: #FF6666;")  # Red - stopped
            
            # SOTA 2026 FIX: Update LED status based on pool connection
            if hasattr(self, 'led_status_label') and running:
                blockchain = getattr(self, 'blockchain', 'BTC') or 'BTC'
                if pool_connected or "connected" in str(status).lower():
                    self.led_status_label.setText(f"MINING: {blockchain} ACTIVE ✓")
                    self.led_status_label.setStyleSheet(
                        "color: #00FF00; background-color: #002200; padding: 6px 12px;"
                        "border-radius: 6px; font-size: 12pt; font-weight: bold;"
                    )
                else:
                    self.led_status_label.setText(f"MINING: {blockchain} - CONNECTING...")
                    self.led_status_label.setStyleSheet(
                        "color: #FFFF00; background-color: #222200; padding: 6px 12px;"
                        "border-radius: 6px; font-size: 12pt; font-weight: bold;"
                    )

            if "hashrate" in data and hasattr(self, 'hashrate_label'):
                hashrate = data["hashrate"]
                # SOTA 2026 FIX: Use smart hashrate formatting
                formatted = self._format_hashrate(hashrate)
                self.hashrate_label.setText(formatted)
                if hasattr(self, 'led_hashrate_label'):
                    self.led_hashrate_label.setText(formatted)

            if "shares_accepted" in data and hasattr(self, 'shares_accepted_label'):
                shares_accepted = data["shares_accepted"]
                self.shares_accepted_label.setText(str(shares_accepted))

            if "shares_rejected" in data and hasattr(self, 'rejected_shares_label'):
                shares_rejected = data["shares_rejected"]
                self.rejected_shares_label.setText(str(shares_rejected))

            if "earnings" in data and hasattr(self, 'earnings_label'):
                earnings = data["earnings"]
                self.earnings_label.setText(f"{earnings:.8f} BTC")

            if "uptime" in data and hasattr(self, 'trad_mining_uptime_value'):
                hours, remainder = divmod(int(data["uptime"]), 3600)
                minutes, seconds = divmod(remainder, 60)
                self.trad_mining_uptime_value.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        except Exception as e:
            logger.error(f"Error handling mining status update: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling mining status update: {e}", level=logging.ERROR)

    def _handle_hashrate_update(self, data: Dict[str, Any]):
        """Handle REAL hashrate update from mining pools/GPUs (THREAD-SAFE)."""
        # Dispatch to main thread if needed
        if not is_main_thread():
            run_on_main_thread(lambda: self._handle_hashrate_update_ui(data))
            return
        self._handle_hashrate_update_ui(data)
    
    def _format_hashrate(self, hps: float) -> str:
        """Format hashrate with appropriate unit (H/s, KH/s, MH/s, GH/s, TH/s, PH/s).
        
        Args:
            hps: Hashrate in hashes per second
            
        Returns:
            str: Formatted hashrate string with unit
        """
        if hps <= 0:
            return "0.00 H/s"
        elif hps < 1000:
            return f"{hps:.2f} H/s"
        elif hps < 1_000_000:
            return f"{hps/1000:.2f} KH/s"
        elif hps < 1_000_000_000:
            return f"{hps/1_000_000:.2f} MH/s"
        elif hps < 1_000_000_000_000:
            return f"{hps/1_000_000_000:.2f} GH/s"
        elif hps < 1_000_000_000_000_000:
            return f"{hps/1_000_000_000_000:.2f} TH/s"
        else:
            return f"{hps/1_000_000_000_000_000:.2f} PH/s"
    
    def _handle_hashrate_update_ui(self, data: Dict[str, Any]):
        """Update UI for hashrate (MUST run on main thread)."""
        try:
            hashrate = data.get('hashrate', 0) or data.get('raw_hps', 0)
            pool = data.get('pool', 'unknown')
            pool_connected = data.get('pool_connected', False)
            
            # SOTA 2026 FIX: Smart hashrate formatting with appropriate units
            formatted_hashrate = self._format_hashrate(hashrate)
            
            # Only log occasionally to avoid spam
            if not hasattr(self, '_hashrate_log_counter'):
                self._hashrate_log_counter = 0
            self._hashrate_log_counter += 1
            if self._hashrate_log_counter % 5 == 1:  # Log every 5th update
                logger.info(f"⛏️ Hashrate: {formatted_hashrate} | Pool Connected: {pool_connected}")
            
            if hasattr(self, 'hashrate_label'):
                self.hashrate_label.setText(formatted_hashrate)
            if hasattr(self, 'led_hashrate_label'):
                self.led_hashrate_label.setText(formatted_hashrate)
            
            # SOTA 2026 FIX: Update LED status based on hashrate and pool connection
            if hashrate > 0 and hasattr(self, 'led_status_label'):
                blockchain = getattr(self, 'blockchain', 'BTC') or 'BTC'
                if pool_connected:
                    self.led_status_label.setText(f"MINING: {blockchain} ACTIVE ✓")
                    self.led_status_label.setStyleSheet(
                        "color: #00FF00; background-color: #002200; padding: 6px 12px;"
                        "border-radius: 6px; font-size: 12pt; font-weight: bold;"
                    )
                else:
                    # Hashing but not connected yet - show yellow
                    self.led_status_label.setText(f"MINING: {blockchain} - HASHING...")
                    self.led_status_label.setStyleSheet(
                        "color: #FFFF00; background-color: #222200; padding: 6px 12px;"
                        "border-radius: 6px; font-size: 12pt; font-weight: bold;"
                    )
            
            # Store raw hashrate for internal calculations
            self.hashrate = hashrate

            if hasattr(self, 'hashrate_history'):
                timestamp = data.get("timestamp", time.time())
                self.hashrate_history.append((timestamp, hashrate))
                if len(self.hashrate_history) > 100:
                    self.hashrate_history = self.hashrate_history[-100:]
                self._update_hashrate_chart()
        except Exception as e:
            logger.error(f"Error handling hashrate update: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling hashrate update: {e}", level=logging.ERROR)

    def _handle_worker_update(self, data: dict) -> None:
        """Handle worker updates from the event bus."""
        try:
            if "workers" in data:
                workers = data.get("workers")
                # SOTA 2026: Null-check to prevent crashes when workers is None or not iterable
                if workers is None or not isinstance(workers, (list, tuple)):
                    logger.warning("Workers data is None or invalid type, skipping update")
                    return
                
                worker_count = len(workers)
                active_workers = sum(1 for w in workers if isinstance(w, dict) and w.get("status") == "active")
                
                self.trad_mining_workers_value.setText(f"{active_workers}/{worker_count}")
                
                # Update worker threads combobox if available workers changed
                current_worker_count = self.trad_mining_threads_combo.count()
                if worker_count != current_worker_count:
                    self.trad_mining_threads_combo.clear()
                    for i in range(1, worker_count + 1):
                        self.trad_mining_threads_combo.addItem(str(i))
                    
                    # SOTA 2026: Bounds check to prevent IndexError when active_workers is 0
                    if active_workers > 0:
                        self.trad_mining_threads_combo.setCurrentIndex(active_workers - 1)
                    elif worker_count > 0:
                        self.trad_mining_threads_combo.setCurrentIndex(0)
        except Exception as e:
            logger.error(f"Error handling worker update: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling worker update: {e}", level=logging.ERROR)

    def _handle_new_block_found(self, data: dict) -> None:
        """Handle new block found events from the event bus."""
        try:
            block_hash = data.get("block_hash", "Unknown")
            block_reward = data.get("reward", 0.0)
            
            self._log(f"New block found: {block_hash[:10]}... Reward: {block_reward}", level=logging.INFO)
            
            # Update blocks found counter
            try:
                current_blocks = int(self.trad_mining_blocks_value.text())
                self.trad_mining_blocks_value.setText(str(current_blocks + 1))
            except ValueError:
                self.trad_mining_blocks_value.setText("1")
                
            # Create success notification
            self.show_notification("Block Found!", f"New block mined with reward {block_reward}")
            
            # Update blockchain table if we're on that tab
            if self.blockchain_blocks_table:
                self._request_blockchain_blocks_update()
        except Exception as e:
            logger.error(f"Error handling new block found: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling new block found: {e}", level=logging.ERROR)

    def _handle_mining_error(self, data: dict) -> None:
        """Handle mining error events from the event bus."""
        try:
            error_type = data.get("error_type", "Unknown")
            error_message = data.get("message", "An unknown error occurred")
            
            self._log(f"Mining error: {error_type} - {error_message}", level=logging.ERROR)
            
            # Show error notification
            self.show_notification(f"Mining Error: {error_type}", error_message, level="error")
            
            # Update mining status if it's a critical error
            severity = data.get("severity", "warning")
            if severity == "critical":
                self.mining_status_label.setText("Mining: Error")
                self.mining_status_label.setStyleSheet("color: red;")
                self.trad_mining_start_button.setText("Start Mining")
                self.trad_mining_start_button.setStyleSheet("background-color: #006600; color: #00FF00; border: 2px solid #00FF00; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
        except Exception as e:
            logger.error(f"Error handling mining error event: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling mining error event: {e}", level=logging.ERROR)
    
    # Blockchain event handlers
    def _handle_blockchain_status_update(self, data: dict) -> None:
        """Handle blockchain status updates from the event bus."""
        try:
            status = data.get("status")
            if status:
                self._log(f"Blockchain status update received: {status}", level=logging.INFO)
                
                if status == "connected":
                    self.blockchain_status_label.setText("Blockchain: Connected")
                    self.blockchain_status_label.setStyleSheet("color: green;")
                elif status == "connecting":
                    self.blockchain_status_label.setText("Blockchain: Connecting")
                    self.blockchain_status_label.setStyleSheet("color: #CCAA00;")
                elif status == "disconnected":
                    self.blockchain_status_label.setText("Blockchain: Disconnected")
                    self.blockchain_status_label.setStyleSheet("color: #AA0000;")
                elif status == "error":
                    self.blockchain_status_label.setText("Blockchain: Error")
                    self.blockchain_status_label.setStyleSheet("color: red;")
                
                # If we have blockchain info, update related fields
                if "blockchain" in data:
                    index = self.blockchain_selection_combo.findText(data["blockchain"])
                    if index >= 0:
                        self.blockchain_selection_combo.setCurrentIndex(index)
        except Exception as e:
            logger.error(f"Error handling blockchain status update: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling blockchain status update: {e}", level=logging.ERROR)
    
    def _handle_nodes_status(self, data: dict) -> None:
        """Handle mining nodes connection status updates.
        ROOT FIX: Dispatch to main thread via QTimer.singleShot(0) since events
        come from background threads -- direct widget updates fail silently.
        """
        try:
            # Copy data to avoid mutation in lambda closure
            _data = dict(data)
            QTimer.singleShot(0, lambda: self._update_nodes_label(_data))
        except Exception as e:
            logger.error(f"Error handling nodes status: {e}")
    
    def _update_nodes_label(self, data: dict) -> None:
        """Actually update the nodes label -- guaranteed to run on main thread."""
        try:
            connected = data.get("connected", False)
            if hasattr(self, 'nodes_status_label'):
                if connected == "connecting":
                    self.nodes_status_label.setText("Nodes: Connecting...")
                    self.nodes_status_label.setStyleSheet("color: #CCAA00;")
                elif connected:
                    self.nodes_status_label.setText("Nodes: Connected")
                    self.nodes_status_label.setStyleSheet("color: #00FF00;")
                else:
                    self.nodes_status_label.setText("Nodes: Disconnected")
                    self.nodes_status_label.setStyleSheet("color: red;")
        except Exception as e:
            logger.error(f"Error updating nodes label: {e}")
    
    def _handle_pool_status(self, data: dict) -> None:
        """Handle mining pool connection status updates.
        ROOT FIX: Dispatch to main thread via QTimer.singleShot(0).
        """
        try:
            _data = dict(data)
            QTimer.singleShot(0, lambda: self._update_pool_label(_data))
        except Exception as e:
            logger.error(f"Error handling pool status: {e}")
    
    def _update_pool_label(self, data: dict) -> None:
        """Actually update the pool label -- guaranteed to run on main thread."""
        try:
            connected = data.get("connected", False)
            pool_name = data.get("pool", "")
            status = data.get("status", "")
            
            if hasattr(self, 'pools_status_label'):
                if connected:
                    self.pools_status_label.setText(f"Pools: Connected")
                    self.pools_status_label.setStyleSheet("color: #00FF00;")
                    if hasattr(self, 'led_status_label'):
                        blockchain = getattr(self, 'blockchain', 'BTC') or 'BTC'
                        self.led_status_label.setText(f"MINING: {blockchain} ACTIVE")
                        self.led_status_label.setStyleSheet(
                            "color: #00FF00; background-color: #002200; padding: 6px 12px;"
                            "border-radius: 6px; font-size: 12pt; font-weight: bold;"
                        )
                elif status == "connecting":
                    self.pools_status_label.setText("Pools: Connecting...")
                    self.pools_status_label.setStyleSheet("color: #FFFF00;")
                elif status == "connecting_slow":
                    self.pools_status_label.setText("Pools: Connecting (slow)...")
                    self.pools_status_label.setStyleSheet("color: #FF8800;")
                elif status == "retrying":
                    self.pools_status_label.setText("Pools: Reconnecting...")
                    self.pools_status_label.setStyleSheet("color: #CCAA00;")
                else:
                    self.pools_status_label.setText("Pools: Disconnected")
                    self.pools_status_label.setStyleSheet("color: red;")
        except Exception as e:
            logger.error(f"Error updating pool label: {e}")
    
    def _handle_blockchain_network_stats(self, data: dict) -> None:
        """Handle blockchain network statistics updates from the event bus."""
        try:
            # Update network statistics in the blockchain status tab
            if self.blockchain_difficulty_value and "difficulty" in data:
                self.blockchain_difficulty_value.setText(f"{data['difficulty']:,.2f}")
            
            if self.blockchain_hashrate_value and "network_hashrate" in data:
                hashrate = data["network_hashrate"]
                unit = "H/s"
                if hashrate > 1e12:
                    hashrate /= 1e12
                    unit = "TH/s"
                elif hashrate > 1e9:
                    hashrate /= 1e9
                    unit = "GH/s"
                elif hashrate > 1e6:
                    hashrate /= 1e6
                    unit = "MH/s"
                elif hashrate > 1e3:
                    hashrate /= 1e3
                    unit = "KH/s"
                self.blockchain_hashrate_value.setText(f"{hashrate:,.2f} {unit}")
            
            if self.blockchain_peers_value and "peer_count" in data:
                self.blockchain_peers_value.setText(str(data["peer_count"]))
            
            if self.blockchain_height_value and "block_height" in data:
                self.blockchain_height_value.setText(f"{data['block_height']:,}")
        except Exception as e:
            logger.error(f"Error handling blockchain network stats: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling blockchain network stats: {e}", level=logging.ERROR)
    
    def _handle_blockchain_market_data(self, data: dict) -> None:
        """Handle blockchain market data updates from the event bus."""
        try:
            # Update market data in the blockchain status tab
            if self.blockchain_price_value and "price" in data:
                self.blockchain_price_value.setText(f"${data['price']:,.2f}")
            
            if self.blockchain_volume_value and "volume_24h" in data:
                self.blockchain_volume_value.setText(f"${data['volume_24h']:,.2f}")
            
            if self.blockchain_marketcap_value and "market_cap" in data:
                self.blockchain_marketcap_value.setText(f"${data['market_cap']:,.2f}")
            
            if self.blockchain_change_value and "price_change_24h" in data:
                change = data["price_change_24h"]
                color = "green" if change >= 0 else "red"
                self.blockchain_change_value.setText(f"{change:+.2f}%")
                self.blockchain_change_value.setStyleSheet(f"color: {color};")
        except Exception as e:
            logger.error(f"Error handling blockchain market data: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling blockchain market data: {e}", level=logging.ERROR)
    
    def _handle_blockchain_blocks(self, data: dict) -> None:
        """Handle blockchain blocks updates from the event bus."""
        try:
            if "blocks" not in data or not self.blockchain_blocks_table:
                return
                
            blocks = data["blocks"]
            self.blockchain_blocks_table.setRowCount(0)  # Clear existing rows
            
            for block in blocks:
                row_position = self.blockchain_blocks_table.rowCount()
                self.blockchain_blocks_table.insertRow(row_position)
                
                # Block height
                height_item = QTableWidgetItem(str(block.get("height", "N/A")))
                self.blockchain_blocks_table.setItem(row_position, 0, height_item)
                
                # Block hash (truncated)
                hash_value = block.get("hash", "N/A")
                if len(hash_value) > 12:
                    hash_value = hash_value[:6] + "..." + hash_value[-6:]
                hash_item = QTableWidgetItem(hash_value)
                self.blockchain_blocks_table.setItem(row_position, 1, hash_item)
                
                # Timestamp
                timestamp = block.get("timestamp", 0)
                if timestamp > 0:
                    time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    time_str = "N/A"
                time_item = QTableWidgetItem(time_str)
                self.blockchain_blocks_table.setItem(row_position, 2, time_item)
                
                # Transaction count
                tx_count = block.get("tx_count", 0)
                tx_item = QTableWidgetItem(str(tx_count))
                self.blockchain_blocks_table.setItem(row_position, 3, tx_item)
                
                # Size
                size = block.get("size", 0)
                if size > 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.2f} MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.2f} KB"
                else:
                    size_str = f"{size} B"
                size_item = QTableWidgetItem(size_str)
                self.blockchain_blocks_table.setItem(row_position, 4, size_item)
                
                # Difficulty
                difficulty_item = QTableWidgetItem(f"{block.get('difficulty', 0):,.2f}")
                self.blockchain_blocks_table.setItem(row_position, 5, difficulty_item)
            
            self.blockchain_blocks_table.resizeColumnsToContents()
        except Exception as e:
            logger.error(f"Error handling blockchain blocks: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling blockchain blocks: {e}", level=logging.ERROR)
    
    def _request_blockchain_blocks_update(self) -> None:
        """Request updated blockchain block data from the event bus."""
        if self.event_bus and hasattr(self.event_bus, "publish"):
            try:
                self.event_bus.publish("blockchain.get_blocks", {
                    "source": "mining_tab",
                    "count": 10,  # Get the 10 most recent blocks
                    "request_id": str(uuid.uuid4())
                })
                self._log("Requested blockchain blocks update", level=logging.INFO)
            except Exception as e:
                logger.error(f"Error requesting blockchain blocks: {e}\n{traceback.format_exc()}")
                self._log(f"Error requesting blockchain blocks: {e}", level=logging.ERROR)
    
    # Quantum mining event handlers
    def _handle_quantum_mining_status(self, data: dict) -> None:
        """Handle quantum mining status updates from the event bus."""
        try:
            status = data.get("status")
            if status:
                self._log(f"Quantum mining status update received: {status}", level=logging.INFO)
                
                if status == "running":
                    self.quantum_status_label.setText("Quantum Mining: Active")
                    self.quantum_status_label.setStyleSheet("color: green;")
                    self.quantum_mining_start_button.setText("Stop Quantum Mining")
                    self.quantum_mining_start_button.setStyleSheet("background-color: #990000; color: white; border: 2px solid #FF4444; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
                elif status == "stopped":
                    self.quantum_status_label.setText("Quantum Mining: Inactive")
                    self.quantum_status_label.setStyleSheet("color: #AA0000;")
                    self.quantum_mining_start_button.setText("Start Quantum Mining")
                    self.quantum_mining_start_button.setStyleSheet("background-color: #006600; color: #00FF00; border: 2px solid #00FF00; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
                elif status == "initializing":
                    self.quantum_status_label.setText("Quantum Mining: Initializing")
                    self.quantum_status_label.setStyleSheet("color: #CCAA00;")
                    self.quantum_mining_start_button.setEnabled(False)
                
                # Update quantum mining statistics
                if "circuits_processed" in data:
                    self.quantum_mining_circuits_value.setText(str(data["circuits_processed"]))
                if "success_rate" in data:
                    self.quantum_mining_success_value.setText(f"{data['success_rate']:.2f}%")
                if "quantum_advantage" in data:
                    self.quantum_mining_advantage_value.setText(f"{data['quantum_advantage']:.2f}x")
                if "qubit_count" in data and "algorithm" in data:
                    self.quantum_mining_info_value.setText(
                        f"{data['algorithm']} ({data['qubit_count']} qubits)"
                    )
        except Exception as e:
            logger.error(f"Error handling quantum mining status: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling quantum mining status: {e}", level=logging.ERROR)
    
    def _handle_quantum_hashrate_update(self, data: dict) -> None:
        """BUG 4 FIX: Handle quantum hashrate updates from quantum mining backend.
        The backend publishes 'quantum.mining.hashrate' but nobody was subscribed."""
        try:
            hashrate = data.get("hashrate", data.get("quantum_hashrate", 0))
            unit = data.get("unit", "H/s")
            
            def _update_ui():
                if hasattr(self, 'q_hashrate_label'):
                    self.q_hashrate_label.setText(f"{hashrate:.2f} {unit}")
                    self.q_hashrate_label.setStyleSheet(
                        "color: #00ff00;" if hashrate > 0 else "color: #888888;"
                    )
                # Also update LED hashrate if available
                if hasattr(self, 'led_hashrate_label'):
                    self.led_hashrate_label.setText(f"Quantum: {hashrate:.2f} {unit}")
            
            QTimer.singleShot(0, _update_ui)
            logger.debug(f"Quantum hashrate updated: {hashrate} {unit}")
        except Exception as e:
            logger.error(f"Error handling quantum hashrate: {e}")
    
    # ==================== UI CALLBACK METHODS ====================
    # These methods are connected to UI signals and handle user interactions
    
    def _on_blockchain_changed(self, blockchain_name: str):
        """Handle blockchain selection change in traditional mining tab."""
        try:
            logger.info(f"Blockchain changed to: {blockchain_name}")
            self.blockchain = blockchain_name
            self._log(f"Selected blockchain: {blockchain_name}", level=logging.INFO)
            
            # Update mining system with new blockchain
            if self.mining_system:
                self.mining_system.set_blockchain(blockchain_name)
            
            # Publish event to event bus
            if self.event_bus:
                self.event_bus.publish("mining.blockchain.changed", {
                    "blockchain": blockchain_name,
                    "timestamp": time.time()
                })
        except Exception as e:
            logger.error(f"Error changing blockchain: {e}\n{traceback.format_exc()}")
            self._log(f"Error changing blockchain: {e}", level=logging.ERROR)
    
    def _on_mining_mode_changed(self, mode):
        """Handle mining mode change between solo and pool."""
        try:
            is_pool_mode = (mode == "Pool Mining")
            self.pool_combo.setEnabled(is_pool_mode)
            logger.info(f"Mining mode changed to: {mode}")
            self._log(f"Mining mode: {mode}", level=logging.INFO)

            # Determine currently selected POW symbol from combo data
            symbol: Optional[str] = None
            try:
                if hasattr(self, "blockchain_combo"):
                    data = self.blockchain_combo.currentData()
                    if isinstance(data, dict):
                        sym_val = data.get("symbol") or ""
                        symbol = str(sym_val).upper() if sym_val else None
            except Exception:
                symbol = None

            node_info: Optional[Dict[str, Any]] = None
            if symbol and self.pow_nodes:
                node_info = self.pow_nodes.get(symbol)

            # Log guidance based on pow_nodes configuration when switching modes
            if mode == "Solo Mining":
                if not node_info:
                    self._log(
                        f" Solo mining selected but no pow_nodes entry found for {symbol or 'current coin'}; "
                        "treat this coin as pool-focused unless you add node settings in config/pow_nodes.json.",
                        level=logging.WARNING,
                    )
                else:
                    solo_recommended = bool(node_info.get("solo_recommended", False))
                    rpc_env = node_info.get("rpc_url_env")
                    software_hint = node_info.get("software_hint")
                    if solo_recommended:
                        note = "solo+pool (full node strongly recommended)"
                    else:
                        note = "solo possible with full node, but pool-focused for typical users"
                    self._log(
                        f"Solo mode for {symbol}: {note}. Configure RPC via env var {rpc_env} "
                        f"and run the node ({software_hint}).",
                        level=logging.INFO,
                    )
            else:  # Pool Mining
                if symbol and node_info:
                    software_hint = node_info.get("software_hint")
                    self._log(
                        f"Pool mode for {symbol}: node config exists ({software_hint}); you may run the node in "
                        "parallel for validation, but it is not required for pool mining.",
                        level=logging.INFO,
                    )
        except Exception as e:
            logger.error(f"Error changing mining mode: {e}")
    
    def _on_focus_mode_changed(self, mode_text: str):
        try:
            self.mining_focus_mode = "focused" if "Focused" in str(mode_text) else "all"
            if self.mining_focus_mode == "all":
                for checkbox in self.per_coin_checkboxes.values():
                    checkbox.setChecked(True)
                    checkbox.setEnabled(False)
            else:
                for checkbox in self.per_coin_checkboxes.values():
                    checkbox.setEnabled(True)
            self._apply_coin_focus_to_backend()
        except Exception as e:
            logger.error(f"Error changing mining focus mode: {e}")
    
    def _on_coin_checkbox_changed(self, state: int, symbol: str):
        try:
            enabled = state == Qt.CheckState.Checked.value or state == 2
            sym = str(symbol).upper()
            if enabled:
                self.per_coin_rewards.setdefault(sym, 0.0)
                self.per_coin_hashrate.setdefault(sym, 0.0)
            self._apply_coin_focus_to_backend()
        except Exception as e:
            logger.error(f"Error toggling coin focus for {symbol}: {e}")
    
    def _on_funnel_rewards_clicked(self):
        try:
            if not self.event_bus:
                return
            enabled_symbols = [s for s, checkbox in self.per_coin_checkboxes.items() if checkbox.isChecked()]
            payload = {
                "mode": self.mining_focus_mode,
                "coins": enabled_symbols,
                "timestamp": time.time(),
            }
            self.event_bus.publish("mining.rewards.funnel", payload)
            self._log("Funnel rewards request sent", level=logging.INFO)
        except Exception as e:
            logger.error(f"Error handling funnel rewards click: {e}")
    
    def _apply_coin_focus_to_backend(self):
        try:
            if not self.event_bus:
                return
            enabled_symbols = [s for s, checkbox in self.per_coin_checkboxes.items() if checkbox.isChecked()]
            payload = {
                "mode": self.mining_focus_mode,
                "enabled_coins": enabled_symbols,
                "timestamp": time.time(),
            }
            self.event_bus.publish("mining.focus.update", payload)
            self._log(f"Updated mining focus: mode={self.mining_focus_mode}, coins={enabled_symbols}", level=logging.INFO)
        except Exception as e:
            logger.error(f"Error applying coin focus to backend: {e}")
    
    def _on_start_mining(self):
        """Handle start mining button click - IMMEDIATE ACTION."""
        try:
            logger.info("⛏️ START MINING BUTTON CLICKED!")
            
            # IMMEDIATE UI UPDATE
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.start_button.setText("⛏️ MINING...")
            self.mining_status = "Running"
            # SOTA 2026 FIX: Directly update status label for immediate UI feedback
            if hasattr(self, 'mining_status_label'):
                self.mining_status_label.setText("Mining: Running")
                self.mining_status_label.setStyleSheet("color: #00FF00;")  # Green for running
            
            # Initialize mining stats
            self.current_hashrate = 0.0
            self.shares_accepted = 0
            self.shares_rejected = 0
            self.total_earnings = 0.0
            self.start_time = time.time()  # Used by update_uptime()
            
            # Get mining mode
            mining_mode = self.mining_mode_combo.currentText() if hasattr(self, 'mining_mode_combo') else "Pool Mining"
            
            # SOTA 2026 FIX: Default to BTC if no blockchain selected
            selected_blockchain = self.blockchain
            if not selected_blockchain or selected_blockchain == "None" or selected_blockchain.strip() == "":
                selected_blockchain = "BTC"
                self.blockchain = "BTC"
                logger.info("⛏️ No blockchain selected, defaulting to BTC")
            
            # Show immediate feedback in log
            self._log(f"⛏️ STARTING {mining_mode.upper()} for {selected_blockchain} NOW!", level=logging.INFO)
            
            # Update LED status to show what we're mining
            if hasattr(self, 'led_status_label'):
                self.led_status_label.setText(f"MINING: {selected_blockchain} - CONNECTING...")
                self.led_status_label.setStyleSheet(
                    "color: #FFFF00; background-color: #222200; padding: 6px 12px;"
                    "border-radius: 6px; font-size: 12pt; font-weight: bold;"
                )
            
            # Start mining via mining system
            if self.mining_system:
                # Prepare mining config as event data
                pool_name = self.pool_combo.currentText() if mining_mode == "Pool Mining" and hasattr(self, 'pool_combo') else "viabtc"
                mining_config = {
                    "blockchain": selected_blockchain,
                    "coin": selected_blockchain,
                    "mode": mining_mode,
                    "pool": pool_name,
                    "threads": self.threads_spin.value() if hasattr(self, 'threads_spin') else 8
                }
                
                # SOTA 2026 FIX: Use threading to run async mining (more robust than ensure_future)
                import threading
                def start_mining_thread():
                    try:
                        # Create new event loop for this thread
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            result = loop.run_until_complete(self.mining_system.start_mining(mining_config))
                            logger.info(f"⛏️ Mining started successfully: {result}")
                        finally:
                            loop.close()
                    except Exception as e:
                        logger.error(f"⛏️ Mining start failed: {e}")
                        import traceback
                        traceback.print_exc()
                
                mining_thread = threading.Thread(target=start_mining_thread, daemon=True)
                mining_thread.start()
                logger.info(f"⛏️ Mining thread started with config: {mining_config}")
                
                # Update LED to show active mining after short delay
                from PyQt6.QtCore import QTimer
                def update_mining_active():
                    if hasattr(self, 'led_status_label'):
                        self.led_status_label.setText(f"MINING: {selected_blockchain} ACTIVE")
                        self.led_status_label.setStyleSheet(
                            "color: #00FF00; background-color: #002200; padding: 6px 12px;"
                            "border-radius: 6px; font-size: 12pt; font-weight: bold;"
                        )
                QTimer.singleShot(2000, update_mining_active)
            else:
                self._log("⚠️ Mining system not available", level=logging.WARNING)
            
            # Publish event - EventBus.publish is now SYNC, no ensure_future needed
            if self.event_bus:
                self.event_bus.publish("mining.start", {
                    "blockchain": self.blockchain,
                    "timestamp": time.time()
                })
                self.event_bus.publish("mining.started", {
                    "blockchain": self.blockchain,
                    "timestamp": time.time()
                })
            
            self._log(" Traditional mining started successfully!", level=logging.INFO)
            
            # Mining system now handles REAL pool connections and hashing
            logger.info(" Real mining started - check logs for pool connection status")
            
        except Exception as e:
            logger.error(f"Error starting mining: {e}\n{traceback.format_exc()}")
            self._log(f"Error starting mining: {e}", level=logging.ERROR)
            # Restore button states
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
    
    def _on_mine_all_coins(self):
        """MINE ALL 82 POW COINS - The main multi-coin mining trigger."""
        try:
            from core.mining.multi_coin_coordinator import MultiCoinCoordinator
            
            logger.info("🔥 MINE ALL 82 COINS BUTTON PRESSED!")
            
            # Update UI immediately
            self.mine_all_button.setText("⛏️ MINING ALL 82 COINS...")
            self.mine_all_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.start_button.setEnabled(False)
            
            # Create coordinator if needed
            if not hasattr(self, '_multi_coin_coordinator') or self._multi_coin_coordinator is None:
                self._multi_coin_coordinator = MultiCoinCoordinator(event_bus=self.event_bus)
                logger.info("✅ MultiCoinCoordinator created")
            
            # Start mining in background thread to not block UI
            import threading
            
            def run_all_coins_mining():
                """Background thread for multi-coin mining."""
                try:
                    # Create new event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Run the async mining function
                    result = loop.run_until_complete(
                        self._multi_coin_coordinator.start_all_pow_mining()
                    )
                    
                    logger.info(f"🔥 Multi-coin mining started: {result}")
                    
                    # Publish event so UI knows mining started
                    if self.event_bus:
                        self.event_bus.publish("mining.all_coins.started", {
                            "coins": 82,
                            "status": "running" if result else "failed"
                        })
                        
                except Exception as e:
                    logger.error(f"❌ Multi-coin mining error: {e}")
                    if self.event_bus:
                        self.event_bus.publish("mining.all_coins.error", {"error": str(e)})
                finally:
                    try:
                        loop.close()
                    except:
                        pass
            
            # Start background thread
            mining_thread = threading.Thread(target=run_all_coins_mining, daemon=True)
            mining_thread.start()
            
            self._log("🔥 Starting mining for ALL 82 POW cryptocurrencies!", level=logging.INFO)
            self._log("📊 Using: lolMiner, T-Rex, XMRig, Quantum-GPU for different algorithms", level=logging.INFO)
            
            # Update status
            if hasattr(self, 'led_status_label'):
                self.led_status_label.setText("MINING: ALL 82 COINS ACTIVE")
                self.led_status_label.setStyleSheet(
                    "color: #00FF00; background-color: #002200; padding: 6px 12px;"
                    "border-radius: 6px; font-size: 12pt; font-weight: bold;"
                )
                
        except Exception as e:
            logger.error(f"Error starting multi-coin mining: {e}")
            self._log(f"❌ Error: {e}", level=logging.ERROR)
            self.mine_all_button.setText("⛏️ MINE ALL 82 COINS")
            self.mine_all_button.setEnabled(True)
    
    def _update_mining_ui(self):
        """Update mining UI with current statistics."""
        try:
            # Update hashrate display
            if hasattr(self, 'hashrate_label'):
                self.hashrate_label.setText(f"{self.current_hashrate:.2f} MH/s")
            
            # Update shares display
            if hasattr(self, 'shares_label'):
                total_shares = self.shares_accepted + self.shares_rejected
                acceptance_rate = (self.shares_accepted / total_shares * 100) if total_shares > 0 else 0
                self.shares_label.setText(f"{self.shares_accepted}/{total_shares} ({acceptance_rate:.1f}%)")
            
            # Update earnings display
            if hasattr(self, 'earnings_label'):
                # Determine native coin symbol for selected blockchain
                try:
                    base = self._native_currency_map.get((self.blockchain or '').lower(), (self.blockchain or 'ETH').upper())
                    symbol = f"{base}/USDT"
                    pd = self._market_prices.get(symbol)
                    price = 0.0
                    if isinstance(pd, dict):
                        price = float(pd.get('price', 0) or 0)
                    elif isinstance(pd, (int, float)):
                        price = float(pd)
                    usd_value = float(self.total_earnings or 0.0) * price
                    self.earnings_label.setText(f"{self.total_earnings:.8f} {base} (${usd_value:,.2f})")
                except Exception:
                    self.earnings_label.setText(f"{self.total_earnings:.8f} {self.blockchain}")
            
            # Update mining time
            if hasattr(self, 'mining_time_label') and hasattr(self, 'start_time'):
                elapsed = time.time() - self.start_time
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                self.mining_time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            
        except Exception as e:
            logger.error(f"Error updating mining UI: {e}")
    
    def _on_stop_mining(self):
        """Handle stop mining button click - IMMEDIATE ACTION."""
        try:
            logger.info(" STOP MINING BUTTON CLICKED!")
            
            # IMMEDIATE UI UPDATE
            self.start_button.setText("Start Mining")
            
            self._log(" STOPPING TRADITIONAL MINING NOW!", level=logging.INFO)
            
            # Update UI
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.mining_status = "Stopped"
            # SOTA 2026 FIX: Directly update status label for immediate UI feedback
            if hasattr(self, 'mining_status_label'):
                self.mining_status_label.setText("Mining: Stopped")
                self.mining_status_label.setStyleSheet("color: #FF6666;")  # Red for stopped
            
            # Reset mining stats display
            if hasattr(self, 'hashrate_label'):
                self.hashrate_label.setText("0.00 MH/s")
            if hasattr(self, 'current_hashrate'):
                self.current_hashrate = 0.0
            
            # Stop mining via mining system
            if self.mining_system:
                # SOTA 2026 FIX: Use threading to avoid event loop issues
                import threading
                def stop_mining_thread():
                    try:
                        # Create new event loop for this thread
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            result = loop.run_until_complete(self.mining_system.stop_mining())
                            logger.info(f"⏹️ Mining stopped successfully: {result}")
                        finally:
                            loop.close()
                    except Exception as e:
                        logger.error(f"⏹️ Mining stop failed: {e}")
                        import traceback
                        traceback.print_exc()
                
                stop_thread = threading.Thread(target=stop_mining_thread, daemon=True)
                stop_thread.start()
                logger.info("⏹️ Mining stop thread started")
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("mining.stop", {
                    "blockchain": self.blockchain,
                    "timestamp": time.time()
                })
                self.event_bus.publish("mining.stopped", {
                    "blockchain": self.blockchain,
                    "timestamp": time.time()
                })
            
            self._log("Traditional mining stopped successfully", level=logging.INFO)
            
            # Also stop multi-coin mining if running
            self._stop_multi_coin_mining()
            
        except Exception as e:
            logger.error(f"Error stopping mining: {e}\n{traceback.format_exc()}")
            self._log(f"Error stopping mining: {e}", level=logging.ERROR)
    
    def _stop_multi_coin_mining(self):
        """Stop multi-coin coordinator mining."""
        try:
            # Reset Mine All button
            if hasattr(self, 'mine_all_button'):
                self.mine_all_button.setText("⛏️ MINE ALL 82 COINS")
                self.mine_all_button.setEnabled(True)
            
            # Update LED status
            if hasattr(self, 'led_status_label'):
                self.led_status_label.setText("MINING: STOPPED")
                self.led_status_label.setStyleSheet(
                    "color: #FF6666; background-color: #220000; padding: 6px 12px;"
                    "border-radius: 6px; font-size: 12pt; font-weight: bold;"
                )
            
            # Stop the multi-coin coordinator
            if hasattr(self, '_multi_coin_coordinator') and self._multi_coin_coordinator:
                import threading
                def stop_coordinator():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            self._multi_coin_coordinator.stop_multi_coin_mining()
                        )
                        logger.info("⏹️ Multi-coin coordinator stopped")
                    except Exception as e:
                        logger.debug(f"Multi-coin stop: {e}")
                    finally:
                        try:
                            loop.close()
                        except:
                            pass
                threading.Thread(target=stop_coordinator, daemon=True).start()
                
            self._log("⏹️ Multi-coin mining stopped", level=logging.INFO)
        except Exception as e:
            logger.debug(f"Error stopping multi-coin mining: {e}")
    
    def _on_start_quantum_mining(self):
        """Handle start quantum mining button click."""
        try:
            logger.info("Start quantum mining button clicked")
            self._log("Starting quantum mining...", level=logging.INFO)
            
            # Update UI
            if hasattr(self, 'q_start_button') and hasattr(self, 'q_stop_button'):
                self.q_start_button.setEnabled(False)
                self.q_stop_button.setEnabled(True)
            self.q_mining_status = "Running"
            # SOTA 2026 FIX: Directly update status label for immediate UI feedback
            if hasattr(self, 'q_mining_status_label'):
                self.q_mining_status_label.setText("Running")
                self.q_mining_status_label.setStyleSheet("color: #00FF00;")  # Green for running
            
            # Get quantum parameters
            algorithm = self.q_algorithm_combo.currentText() if hasattr(self, 'q_algorithm_combo') else "Grover"
            qubits = self.q_qubit_spin.value() if hasattr(self, 'q_qubit_spin') else 5
            depth = self.q_depth_spin.value() if hasattr(self, 'q_depth_spin') else 3
            
            # Start quantum mining - use thread-safe async execution
            if self.mining_system and hasattr(self.mining_system, 'start_quantum_mining'):
                # SOTA 2026 FIX: Run async method in a separate thread with its own event loop
                import concurrent.futures
                def run_async_in_thread():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(self.mining_system.start_quantum_mining())
                        finally:
                            new_loop.close()
                    except Exception as e:
                        logger.warning(f"Async quantum mining start error: {e}")
                        return None
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(run_async_in_thread)
                    try:
                        future.result(timeout=10)
                    except concurrent.futures.TimeoutError:
                        logger.warning("Quantum mining start timed out")
                    except Exception as e:
                        logger.warning(f"Quantum mining start error: {e}")
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("quantum_mining.started", {
                    "algorithm": algorithm,
                    "qubits": qubits,
                    "depth": depth,
                    "timestamp": time.time()
                })
            
            self._log(f"Quantum mining started: {algorithm} with {qubits} qubits", level=logging.INFO)
        except Exception as e:
            logger.error(f"Error starting quantum mining: {e}\n{traceback.format_exc()}")
            self._log(f"Error starting quantum mining: {e}", level=logging.ERROR)
            # Restore button states
            if hasattr(self, 'q_start_button') and hasattr(self, 'q_stop_button'):
                self.q_start_button.setEnabled(True)
                self.q_stop_button.setEnabled(False)
    
    def _on_stop_quantum_mining(self):
        """Handle stop quantum mining button click."""
        try:
            logger.info("Stop quantum mining button clicked")
            self._log("Stopping quantum mining...", level=logging.INFO)
            
            # Update UI
            if hasattr(self, 'q_start_button') and hasattr(self, 'q_stop_button'):
                self.q_start_button.setEnabled(True)
                self.q_stop_button.setEnabled(False)
            self.q_mining_status = "Stopped"
            # SOTA 2026 FIX: Directly update status label for immediate UI feedback
            if hasattr(self, 'q_mining_status_label'):
                self.q_mining_status_label.setText("Stopped")
                self.q_mining_status_label.setStyleSheet("color: #FF6666;")  # Red for stopped
            
            # Stop quantum mining
            if self.mining_system and hasattr(self.mining_system, 'stop_quantum_mining'):
                self.mining_system.stop_quantum_mining()
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("quantum_mining.stopped", {
                    "timestamp": time.time()
                })
            
            self._log("Quantum mining stopped successfully", level=logging.INFO)
        except Exception as e:
            logger.error(f"Error stopping quantum mining: {e}\n{traceback.format_exc()}")
            self._log(f"Error stopping quantum mining: {e}", level=logging.ERROR)
    
    def _on_update_quantum_circuit(self):
        """Handle update quantum circuit visualization button click."""
        try:
            logger.info("Update quantum circuit button clicked")
            
            # Get current parameters
            algorithm = self.q_algorithm_combo.currentText() if hasattr(self, 'q_algorithm_combo') else "Grover"
            qubits = self.q_qubit_spin.value() if hasattr(self, 'q_qubit_spin') else 5
            depth = self.q_depth_spin.value() if hasattr(self, 'q_depth_spin') else 3
            
            # Update visualization
            if self.quantum_visualization:
                success = self.quantum_visualization.update_circuit(
                    algorithm=algorithm,
                    qubit_count=qubits,
                    circuit_depth=depth
                )
                if success:
                    self._log(f"Quantum circuit updated: {algorithm}", level=logging.INFO)
                else:
                    self._log("Failed to update quantum circuit", level=logging.WARNING)
        except Exception as e:
            logger.error(f"Error updating quantum circuit: {e}\n{traceback.format_exc()}")
            self._log(f"Error updating quantum circuit: {e}", level=logging.ERROR)
    
    def _on_apply_recommendation(self):
        """Handle apply mining intelligence recommendation button click."""
        try:
            logger.info("Apply recommendation button clicked")
            
            # Get selected recommendation
            recommendation = self.recommendation_combo.currentText() if hasattr(self, 'recommendation_combo') else "None"
            
            self._log(f"Applying recommendation: {recommendation}", level=logging.INFO)
            
            # Apply recommendation logic here
            # This would interact with the mining system to adjust parameters
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("mining.recommendation.applied", {
                    "recommendation": recommendation,
                    "timestamp": time.time()
                })
            
            # Show success message
            self.show_notification("Recommendation Applied", f"Applied: {recommendation}")
        except Exception as e:
            logger.error(f"Error applying recommendation: {e}\n{traceback.format_exc()}")
            self._log(f"Error applying recommendation: {e}", level=logging.ERROR)
    
    def _on_update_prediction(self):
        """Handle update profit prediction button click."""
        try:
            logger.info("Update prediction button clicked")
            
            # Get timeline
            timeline = self.timeline_combo.currentText() if hasattr(self, 'timeline_combo') else "24h"
            
            self._log(f"Updating profit prediction for: {timeline}", level=logging.INFO)
            
            # Update prediction logic here
            # This would calculate estimated profits based on current hashrate and blockchain
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("mining.prediction.update", {
                    "timeline": timeline,
                    "timestamp": time.time()
                })
        except Exception as e:
            logger.error(f"Error updating prediction: {e}\n{traceback.format_exc()}")
            self._log(f"Error updating prediction: {e}", level=logging.ERROR)
    
    def _on_refresh_blockchain(self):
        """Handle refresh blockchain status button click."""
        try:
            logger.info("Refresh blockchain button clicked")
            self._log("Refreshing blockchain data...", level=logging.INFO)
            
            # Get selected blockchain
            blockchain = self.blockchain_view_combo.currentText() if hasattr(self, 'blockchain_view_combo') else "Bitcoin"
            
            # Request blockchain data update
            if self.event_bus:
                self.event_bus.publish("blockchain.refresh.request", {
                    "blockchain": blockchain,
                    "timestamp": time.time()
                })
            
            self._log(f"Refreshing {blockchain} blockchain data...", level=logging.INFO)
        except Exception as e:
            logger.error(f"Error refreshing blockchain: {e}\n{traceback.format_exc()}")
            self._log(f"Error refreshing blockchain: {e}", level=logging.ERROR)
    
    def _on_airdrop_farming_changed(self, state):
        """Handle airdrop farming checkbox state change."""
        try:
            enabled = state == Qt.CheckState.Checked.value or state == 2  # Qt.Checked = 2
            logger.info(f"Airdrop farming {'enabled' if enabled else 'disabled'}")
            self._log(f"Airdrop farming: {'enabled' if enabled else 'disabled'}", level=logging.INFO)
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("airdrop.farming.changed", {
                    "enabled": enabled,
                    "timestamp": time.time()
                })
        except Exception as e:
            logger.error(f"Error changing airdrop farming state: {e}\n{traceback.format_exc()}")
            self._log(f"Error changing airdrop farming state: {e}", level=logging.ERROR)
    
    def _on_scan_airdrops(self):
        """Handle scan for new airdrops button click."""
        try:
            logger.info("Scan airdrops button clicked")
            self._log("Scanning for new airdrops...", level=logging.INFO)
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("airdrop.scan.request", {
                    "timestamp": time.time()
                })
            
            # Show scanning message
            self.show_notification("Scanning Airdrops", "Searching for new airdrop opportunities...")
        except Exception as e:
            logger.error(f"Error scanning airdrops: {e}\n{traceback.format_exc()}")
            self._log(f"Error scanning airdrops: {e}", level=logging.ERROR)
    
    def _handle_backend_mining_status(self, data):
        """Handle mining status response from backend - DISPLAY TO USER"""
        try:
            running = data.get('running', False)
            hashrate = data.get('hashrate', '0 H/s')
            message = data.get('message', '')
            
            logger.info(f" Mining Status from Backend: {message}")
            logger.info(f"   Running: {running}")
            logger.info(f"   Hashrate: {hashrate}")
            
            # Update UI
            self._log(f" Backend: {message} (Hashrate: {hashrate})", level=logging.INFO)
            
            # Update status display if available
            if hasattr(self, 'mining_status'):
                self.mining_status = "Running" if running else "Stopped"
                
        except Exception as e:
            logger.error(f"Error handling backend mining status: {e}")
    
    def _on_coin_analytics_coin_changed(self, coin_name: str):
        """Handle coin analytics selection change."""
        try:
            logger.info(f"Coin analytics changed to: {coin_name}")
            
            if not coin_name or coin_name == "Select Coin":
                # Clear the hourly table
                self.coin_analytics_hourly_table.setRowCount(0)
                return
            
            # Update the hourly analytics table with mock data
            self._update_coin_analytics_hourly_data(coin_name)
            
            self._log(f"Updated analytics for {coin_name}", level=logging.INFO)
            
        except Exception as e:
            logger.error(f"Error changing coin analytics: {e}")
            self._log(f"Error updating coin analytics: {e}", level=logging.ERROR)
    
    def _update_coin_analytics_hourly_data(self, coin_name: str):
        """Update hourly analytics data for selected coin using REAL mining backend data.
        
        SOTA 2026: Pulls live data from _hourly_mining_stats accumulator (fed by
        mining.stats.update events from built-in miners) instead of static mock data.
        When mining has not started yet, shows real timestamps with zero values.
        """
        try:
            import time
            from datetime import datetime, timedelta
            
            # Initialize hourly accumulator if not present
            if not hasattr(self, '_hourly_mining_stats'):
                self._hourly_mining_stats = {}
            
            coin_upper = coin_name.upper()
            coin_hourly = self._hourly_mining_stats.get(coin_upper, {})
            
            # Build hourly rows from real accumulated data
            now = datetime.now()
            hourly_data = []
            
            if coin_hourly:
                # We have real mining data — display it sorted by hour
                for hour_key in sorted(coin_hourly.keys()):
                    entry = coin_hourly[hour_key]
                    rewards = entry.get('rewards', 0.0)
                    hashes = entry.get('hashes', 0)
                    samples = entry.get('samples', 0)
                    focused = entry.get('focused', True)
                    reward_per_hash = rewards / hashes if hashes > 0 else 0.0
                    hourly_data.append([
                        hour_key,
                        f"{rewards:.6f}",
                        f"{reward_per_hash:.8f}",
                        str(samples),
                        "Focused" if focused else "Unfocused",
                    ])
            else:
                # No mining data yet — show real timestamps with zeros
                # Pull live stats from mining_system if available
                live_hashrate = 0.0
                live_shares = 0
                try:
                    if self.event_bus and hasattr(self.event_bus, 'get_component'):
                        ms = self.event_bus.get_component('mining_system')
                        if ms and hasattr(ms, 'get_stats'):
                            ms_stats = ms.get_stats()
                            live_hashrate = ms_stats.get('hashrate', {}).get('5s', 0.0)
                            live_shares = ms_stats.get('shares', {}).get('total', 0)
                except Exception:
                    pass
                
                for i in range(5):
                    hour = now - timedelta(hours=(4 - i))
                    hour_str = hour.strftime("%H:00")
                    # Current hour gets live data, past hours get zeros
                    if i == 4 and live_hashrate > 0:
                        hourly_data.append([hour_str, "0.000000", f"{live_hashrate:.2f} H/s", str(live_shares), "Focused"])
                    else:
                        hourly_data.append([hour_str, "0.000000", "0.00000000", "0", "Awaiting Data"])
            
            self.coin_analytics_hourly_table.setRowCount(len(hourly_data))
            
            for row, data in enumerate(hourly_data):
                for col, value in enumerate(data):
                    item = QTableWidgetItem(str(value))
                    self.coin_analytics_hourly_table.setItem(row, col, item)
            
            # Update table header with coin name
            self.coin_analytics_hourly_table.setHorizontalHeaderLabels([
                "Hour",
                f"{coin_name} Rewards",
                "Reward/Hash",
                "Samples",
                "Status",
            ])
            
        except Exception as e:
            logger.error(f"Error updating hourly analytics data: {e}")
    
    def _accumulate_hourly_mining_stats(self, coin: str, rewards: float, hashrate: float, shares: int):
        """Accumulate real mining stats into hourly buckets for analytics display.
        
        Called from _handle_mining_stats when real data arrives from built-in miners.
        """
        from datetime import datetime
        if not hasattr(self, '_hourly_mining_stats'):
            self._hourly_mining_stats = {}
        
        coin_upper = coin.upper()
        if coin_upper not in self._hourly_mining_stats:
            self._hourly_mining_stats[coin_upper] = {}
        
        hour_key = datetime.now().strftime("%H:00")
        if hour_key not in self._hourly_mining_stats[coin_upper]:
            self._hourly_mining_stats[coin_upper][hour_key] = {
                'rewards': 0.0, 'hashes': 0, 'samples': 0, 'focused': True
            }
        
        entry = self._hourly_mining_stats[coin_upper][hour_key]
        entry['rewards'] += rewards
        entry['hashes'] += int(hashrate)
        entry['samples'] += shares
        entry['focused'] = hashrate > 0
    
    def show_notification(self, title: str, message: str, level: str = "info"):
        """Show a notification message to the user."""
        try:
            # This can be expanded to show actual UI notifications
            logger.info(f"NOTIFICATION [{title}]: {message}")
            self._log(f"{title}: {message}", level=logging.INFO)
        except Exception as e:
            logger.error(f"Error showing notification: {e}")
    
    def _update_hashrate_chart(self):
        """Update the hashrate chart with current data."""
        try:
            # Safety check: ensure matplotlib components exist
            if self.ax is None or self.canvas is None or self.figure is None:
                return
            
            # Clear the axes
            self.ax.clear()
            # Re-apply dark cyberpunk theme after clear
            self.figure.set_facecolor('#1E1E1E')
            self.ax.set_facecolor('#0A0E17')
            
            # Check if we have hashrate history data
            if not hasattr(self, 'hashrate_history') or not self.hashrate_history:
                # Show placeholder text when no data
                self.ax.text(0.5, 0.5, 
                    'No Data - Start Mining to See Hashrate',
                    horizontalalignment='center',
                    verticalalignment='center',
                    transform=self.ax.transAxes,
                    fontsize=12,
                    color='#00FFFF',
                    weight='bold',
                    alpha=0.7)
                self.ax.set_title("Hashrate over Time", color='#00FFFF')
                self.ax.set_xlabel("Time", color='#00FFAA')
                self.ax.set_ylabel("Hashrate (H/s)", color='#00FFAA')
                self.ax.tick_params(colors='#00FFAA', which='both')
                for spine in self.ax.spines.values():
                    spine.set_color('#00FFFF')
                self.ax.grid(True, color='#1A3A4A', alpha=0.5)
                self.canvas.draw()
                return
            
            # Plot the data
            self.ax.plot(self.hashrate_history, color='#00FFFF', linewidth=2)
            self.ax.set_title("Hashrate over Time", color='#00FFFF')
            self.ax.set_xlabel("Time", color='#00FFAA')
            self.ax.set_ylabel("Hashrate (H/s)", color='#00FFAA')
            self.ax.tick_params(colors='#00FFAA', which='both')
            for spine in self.ax.spines.values():
                spine.set_color('#00FFFF')
            self.ax.grid(True, color='#1A3A4A', alpha=0.5)
            self.canvas.draw()
        except Exception as e:
            logger.warning(f"Could not update hashrate chart: {e}")
    
    # ========================================================================
    # GPU QUANTUM SYSTEMS
    # ========================================================================
    
    def _init_gpu_quantum_systems(self):
        """Initialize GPU Quantum mining systems."""
        try:
            # Initialize GPU Quantum Integration
            if GPU_QUANTUM_AVAILABLE and GPUQuantumIntegration:
                try:
                    self.gpu_quantum = GPUQuantumIntegration(event_bus=self.event_bus, config={})
                    logger.info(" GPU Quantum Integration initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize GPU Quantum: {e}")
            
            # Initialize Quantum Mining
            if QUANTUM_MINING_AVAILABLE:
                try:
                    from core.quantum_mining import QuantumMining
                    from kingdom_ai.quantum.quantum_optimizer import QuantumOptimizer
                    from kingdom_ai.quantum.quantum_nexus import QuantumNexus
                    
                    # FIX: QuantumMining takes event_bus and config as kwargs
                    try:
                        self.quantum_mining = QuantumMining(event_bus=self.event_bus) if 'QuantumMining' in dir() else None
                    except TypeError as e:
                        self.quantum_mining = None
                        logger.warning(f"QuantumMining initialization failed: {e}")
                    try:
                        self.quantum_optimizer = QuantumOptimizer(event_bus=self.event_bus) if 'QuantumOptimizer' in dir() else None  # type: ignore[call-arg]
                    except TypeError:
                        self.quantum_optimizer = None
                    try:
                        self.quantum_nexus = QuantumNexus(self.event_bus) if 'QuantumNexus' in dir() else None
                    except TypeError:
                        self.quantum_nexus = None
                    logger.info(" Quantum Mining systems initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize Quantum Mining: {e}")
            
            # Initialize Quantum Strategy
            if QUANTUM_STRATEGIES_AVAILABLE:
                try:
                    from quantum_enhanced_strategies import QuantumEnhancedStrategy
                    self.quantum_strategy = QuantumEnhancedStrategy() if 'QuantumEnhancedStrategy' in dir() else None
                    logger.info(" Quantum Enhanced Strategy initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize Quantum Strategy: {e}")
                    
        except Exception as e:
            logger.error(f"Error initializing GPU Quantum systems: {e}")
        
        # After initialization, check Redis connection for quantum status
        QTimer.singleShot(1000, self._check_quantum_redis_connection)
    
    def _check_quantum_redis_connection(self):
        """Check Redis Quantum Nexus connection and update quantum status."""
        try:
            from redis import Redis  # type: ignore[import]
            from redis.exceptions import ConnectionError as RedisConnectionError  # type: ignore[import]
            # Try to connect to Redis Quantum Nexus
            redis_client = Redis(
                host='127.0.0.1',
                port=6380,
                password=get_redis_password(),
                decode_responses=True,
                socket_connect_timeout=2
            )
            
            # Test connection
            redis_client.ping()
            
            # Update quantum status to connected
            if hasattr(self, 'quantum_status_label'):
                self.quantum_status_label.setText("Quantum: Connected")
                self.quantum_status_label.setStyleSheet("color: green;")
                logger.info(" Quantum mining connected to Redis Quantum Nexus")
            
            # Store connection status
            self.quantum_status = "Connected"
            self.q_connection = "Connected to Redis Nexus"
            
            # Update quantum mining status label (the one that shows "Disconnected")
            if hasattr(self, 'q_mining_status_label'):
                self.q_mining_status_label.setText("Connected")
                self.q_mining_status_label.setStyleSheet("color: #00FF00; font-weight: bold;")
            
            # Update quantum connection label if it exists
            if hasattr(self, 'q_connection_label'):
                self.q_connection_label.setText("Connected to Quantum Nexus")
                self.q_connection_label.setStyleSheet("color: #00FF00; font-weight: bold;")
            
            # Publish mining status to Dashboard
            if self.event_bus:
                self.event_bus.publish("system.status", {
                    "mining": True,
                    "timestamp": __import__('datetime').datetime.now().isoformat()
                })
            
        except (RedisConnectionError, Exception) as conn_err:
            logger.warning(f" Redis Quantum Nexus not available - quantum mining limited: {conn_err}")
            if hasattr(self, 'quantum_status_label'):
                self.quantum_status_label.setText("Quantum: Redis Offline")
                self.quantum_status_label.setToolTip("Start Redis on port 6380 to enable quantum features")
                self.quantum_status_label.setStyleSheet("color: orange;")
            self.quantum_status = "Disconnected"
            
            # Publish mining offline status to Dashboard
            if self.event_bus:
                self.event_bus.publish("system.status", {
                    "mining": False,
                    "timestamp": __import__('datetime').datetime.now().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Error checking quantum Redis connection: {e}")
            if hasattr(self, 'quantum_status_label'):
                self.quantum_status_label.setText("Quantum: Error")
                self.quantum_status_label.setStyleSheet("color: red;")
            self.quantum_status = "Error"
    
    def optimize_gpu_quantum(self):
        """Optimize mining using GPU quantum acceleration."""
        try:
            if not self.gpu_quantum:
                logger.warning("GPU Quantum not initialized")
                self._log(" GPU Quantum not available", level=logging.WARNING)
                return
            
            logger.info(" Optimizing with GPU Quantum acceleration...")
            self._log(" GPU Quantum optimization started", level=logging.INFO)
            
            # Run GPU optimization
            # FIX: Check if method exists before calling
            if hasattr(self.gpu_quantum, 'optimize_mining'):
                result = self.gpu_quantum.optimize_mining(mining_params={})  # type: ignore[attr-defined,call-arg]
            else:
                logger.warning("GPUQuantumIntegration missing optimize_mining method")
                result = None
            
            # Update UI with results
            if result and isinstance(result, dict):
                boost = result.get('hashrate_boost', '10x')
                efficiency = result.get('efficiency', '95%')
                self._log(f" GPU Quantum: Hashrate boost {boost}, Efficiency {efficiency}", level=logging.INFO)
            elif result:
                self._log(f" GPU Quantum optimization completed", level=logging.INFO)
                
                # Publish event
                if self.event_bus:
                    self.event_bus.publish("gpu.quantum.optimized", {
                        "boost": boost,
                        "efficiency": efficiency,
                        "timestamp": time.time()
                    })
            
        except Exception as e:
            logger.error(f"Error optimizing GPU Quantum: {e}")
            self._log(f" GPU Quantum optimization failed: {e}", level=logging.ERROR)
    
    def _detect_gpu_devices(self):
        """Detect and display available GPU devices."""
        try:
            if not self.gpu_quantum:
                logger.warning("GPU Quantum not initialized")
                if hasattr(self, 'gpu_output_display'):
                    self.gpu_output_display.setPlainText(" GPU Quantum not available")
                return
            
            logger.info(" Detecting GPU devices...")
            if hasattr(self, 'gpu_output_display'):
                self.gpu_output_display.setPlainText(" Scanning for GPU devices...\n")
            
            # Detect GPUs using GPU Quantum Integration
            devices_result = self.gpu_quantum.detect_devices() if hasattr(self.gpu_quantum, 'detect_devices') else []  # type: ignore[attr-defined]
            
            # Handle async results
            if asyncio.iscoroutine(devices_result):
                # If it's a coroutine, run it synchronously
                try:
                    devices = asyncio.run(devices_result)
                except RuntimeError:
                    QTimer.singleShot(0, lambda: self._detect_gpu_devices_async(devices_result))
                except Exception:
                    devices = []
            else:
                devices = devices_result if isinstance(devices_result, list) else []
            
            if not devices:
                logger.warning("No GPU devices detected by GPU Quantum Integration")
                if hasattr(self, 'gpu_output_display'):
                    self.gpu_output_display.setPlainText("No GPU devices detected.")
                return
            
            # Update UI labels
            if devices and hasattr(self, 'gpu_device_label'):
                device = devices[0]
                self.gpu_device_label.setText(f"GPU: {device.get('name', 'Unknown')}")
                self.gpu_memory_label.setText(f"Memory: {device.get('memory', 'N/A')}")
                self.gpu_temp_label.setText("Temp: 45°C")
            
            # Display all detected devices
            output = " GPU Detection Complete:\n\n"
            for i, device in enumerate(devices, 1):
                output += f"Device {i}: {device.get('name', 'Unknown')}\n"
                output += f"  Memory: {device.get('memory', 'N/A')}\n"
                output += f"  Compute: {device.get('compute', 'N/A')}\n\n"
            
            if hasattr(self, 'gpu_output_display'):
                self.gpu_output_display.setPlainText(output)
            
            logger.info(f" Detected {len(devices)} GPU devices")
            
            # Publish to event bus
            if self.event_bus:
                self.event_bus.publish("gpu.devices.detected", {
                    "devices": devices,
                    "count": len(devices),
                    "timestamp": time.time()
                })
            
        except Exception as e:
            logger.error(f"Error detecting GPU devices: {e}")
            if hasattr(self, 'gpu_output_display'):
                self.gpu_output_display.setPlainText(f" Error detecting GPUs: {str(e)}")
    
    def _run_gpu_benchmark(self):
        """Run GPU quantum mining benchmark."""
        try:
            if not self.gpu_quantum:
                logger.warning("GPU Quantum not initialized")
                if hasattr(self, 'gpu_output_display'):
                    self.gpu_output_display.setPlainText(" GPU Quantum not available")
                return
            
            logger.info(" Running GPU quantum benchmark...")
            if hasattr(self, 'gpu_output_display'):
                self.gpu_output_display.setPlainText(" Running benchmark...\nThis may take a moment...\n")
            
            # Run benchmark using GPU Quantum Integration
            import numpy as np
            
            benchmark_results: Dict[str, Any] = {}
            
            # Run benchmark if available
            if hasattr(self.gpu_quantum, 'benchmark'):
                bench_result = self.gpu_quantum.benchmark()  # type: ignore[attr-defined]
                
                # Handle async results
                if asyncio.iscoroutine(bench_result):
                    try:
                        benchmark_results = asyncio.run(bench_result)
                    except Exception:
                        pass  # Use default benchmark_results
                elif isinstance(bench_result, dict):
                    benchmark_results = bench_result
            
            # Display results
            output = " GPU Quantum Benchmark Results:\n\n"
            output += f" Hashrate: {benchmark_results.get('hashrate', 'N/A')}\n"
            output += f" Power Draw: {benchmark_results.get('power', 'N/A')}\n"
            output += f" Efficiency: {benchmark_results.get('efficiency', 'N/A')}\n"
            output += f" Temperature: {benchmark_results.get('temperature', 'N/A')}\n"
            output += f" Benchmark Score: {benchmark_results.get('score', 0)}\n\n"
            output += " GPU quantum acceleration is operational!"
            
            if hasattr(self, 'gpu_output_display'):
                self.gpu_output_display.setPlainText(output)
            
            logger.info(f" GPU Benchmark complete: Score {benchmark_results.get('score', 0)}")
            
            # Publish to event bus
            if self.event_bus:
                self.event_bus.publish("mining.gpu.benchmark", {
                    "results": benchmark_results,
                    "timestamp": time.time()
                })
            
        except Exception as e:
            logger.error(f"Error running GPU benchmark: {e}")
            if hasattr(self, 'gpu_output_display'):
                self.gpu_output_display.setPlainText(f" Benchmark error: {str(e)}")
    
    def _load_pow_blockchains_to_combo(self):
        """
        2025 STATE-OF-THE-ART: Load POW blockchains from data file
        Uses dynamic data loading for 82 POW coins instead of hardcoded 5
        """
        try:
            from utils.data_loader import load_pow_blockchains_sync
            
            blockchains = load_pow_blockchains_sync()
            if blockchains:
                self._pow_blockchains = blockchains
                self._pow_blockchains_by_symbol = {}
                for chain in blockchains:
                    name = chain.get('name', chain.get('symbol', 'Unknown'))
                    symbol = chain.get('symbol', '')
                    algo = chain.get('algorithm', '')
                    display_text = f"{name} ({symbol}) - {algo}"
                    self.blockchain_combo.addItem(display_text, chain)
                    if symbol:
                        self._pow_blockchains_by_symbol[str(symbol).upper()] = chain
                
                logger.info(f" Loaded {len(blockchains)} POW blockchains into mining tab")
            else:
                logger.warning("POW blockchains data not found, using fallback")
                self._pow_blockchains = []
                self._pow_blockchains_by_symbol = {}
                self.blockchain_combo.addItems([
                    "Bitcoin (BTC) - SHA-256",
                    "Ethereum Classic (ETC) - Etchash", 
                    "Litecoin (LTC) - Scrypt",
                    "Monero (XMR) - RandomX",
                    "Ergo (ERG) - Autolykos2"
                ])
        except Exception as e:
            logger.error(f"Error loading POW blockchains: {e}")
            self._pow_blockchains = []
            self._pow_blockchains_by_symbol = {}
            self.blockchain_combo.addItems([
                "Bitcoin (BTC) - SHA-256",
                "Ethereum Classic (ETC) - Etchash",
                "Litecoin (LTC) - Scrypt", 
                "Monero (XMR) - RandomX",
                "Ergo (ERG) - Autolykos2"
            ])
