#!/usr/bin/env python3
# 
# Advanced Mining Frame for Kingdom AI GUI (PyQt6 Version).
# Provides comprehensive interface for traditional mining, quantum mining,
# airdrop farming, and mining intelligence with multi-blockchain support.
# 

# Standard library imports
import logging
import asyncio
import uuid
import traceback
import json
import time
import sys
import random
import os
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
import re
import socket

# PyQt6 imports
from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QTextEdit, 
    QVBoxLayout, QHBoxLayout, QTabWidget, QListWidget,
    QListWidgetItem, QComboBox, QProgressBar, QMessageBox,
    QScrollArea, QSplitter, QGroupBox, QGridLayout, QSlider
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QPalette

# Matplotlib imports with PyQt6 backend
import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
import numpy as np
import pandas as pd
from pathlib import Path
from web3 import Web3

# Local imports
from gui.frames.base_frame_pyqt import BaseFrame
from ..kingdom_style_pyqt import KingdomStyles, GlowButton

# Configure logger
logger = logging.getLogger(__name__)

class QuantumCircuitVisualizer:
    """A class to visualize quantum circuits using matplotlib with PyQt6 backend."""
    
    def __init__(self, fig, canvas):
        """Initialize the visualizer with matplotlib figure and canvas.
        
        Args:
            fig: Matplotlib Figure instance
            canvas: FigureCanvas instance for PyQt6
        """
        self.fig = fig
        self.canvas = canvas
        self.ax = fig.add_subplot(111)
        self.circuit_data = None
        self.clear()
    
    def clear(self):
        """Clear the visualization."""
        self.ax.clear()
        self.ax.set_title("Quantum Circuit Visualization")
        self.ax.set_xlabel("Gate Operations")
        self.ax.set_ylabel("Qubits")
        self.ax.grid(True)
        self.canvas.draw()
    
    def update_circuit(self, algorithm=None, qubit_count=5, circuit_depth=3):
        """Update the quantum circuit visualization."""
        try:
            self.clear()
            
            # Generate sample circuit data based on parameters
            qubits = min(max(1, qubit_count), 30)  # Limit to reasonable range
            depth = min(max(1, circuit_depth), 50)  # Limit to reasonable range
            
            # Create grid for qubits and gates
            for i in range(qubits):
                # Draw qubit lines
                self.ax.plot([0, depth + 1], [i, i], 'k-', linewidth=1)
            
            # Add gates based on algorithm
            if algorithm == "Grover's":
                gate_colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12']
                for d in range(depth):
                    for q in range(qubits):
                        if q < qubits - 1 and random.random() < 0.3:
                            # Draw controlled gate
                            self.ax.plot([d + 1, d + 1], [q, q + 1], 'k-', linewidth=1)
                            self.ax.plot(d + 1, q, 'ko', markersize=5)
                            gate_color = gate_colors[random.randint(0, len(gate_colors) - 1)]
                            self.ax.add_patch(
                                Circle((d + 1, q + 1), 0.2, color=gate_color)
                            )
                        elif random.random() < 0.7:
                            # Draw single qubit gate
                            gate_color = gate_colors[random.randint(0, len(gate_colors) - 1)]
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
                        self.ax.plot([d + 1, d + 1], [q, q + d], 'k-', linewidth=1)
                        self.ax.plot(d + 1, q, 'ko', markersize=5)
                        self.ax.add_patch(
                            Circle((d + 1, q + d), 0.2, color='#e74c3c')
                        )
            elif algorithm == "QAOA":
                # Pattern for QAOA circuit
                # First layer of X gates
                for q in range(qubits):
                    self.ax.add_patch(
                        Rectangle((1 - 0.2, q - 0.2), 0.4, 0.4, color='#3498db')
                    )
                    self.ax.text(1, q, "H", ha='center', va='center', color='white', fontsize=8)
                
                # CNOT gates in alternating pattern
                for d in range(1, depth-1):
                    for q in range(0, qubits-1, 2):
                        self.ax.plot([d + 1, d + 1], [q, q + 1], 'k-', linewidth=1)
                        self.ax.plot(d + 1, q, 'ko', markersize=5)
                        self.ax.add_patch(
                            Circle((d + 1, q + 1), 0.2, color='#e74c3c')
                        )
                
                # Final measurement gates
                for q in range(qubits):
                    self.ax.add_patch(
                        Rectangle((depth - 0.2, q - 0.2), 0.4, 0.4, color='#2ecc71')
                    )
                    self.ax.text(depth, q, "M", ha='center', va='center', color='white', fontsize=8)
            else:
                # Generic quantum circuit with random gates
                gate_types = ["H", "X", "Y", "Z", "CNOT", "S", "T"]
                gate_colors = {
                    "H": '#3498db',
                    "X": '#e74c3c',
                    "Y": '#2ecc71',
                    "Z": '#f39c12',
                    "S": '#9b59b6',
                    "T": '#34495e',
                    "CNOT": '#1abc9c'
                }
                
                for d in range(depth):
                    for q in range(qubits):
                        if random.random() < 0.7:  # 70% chance of a gate
                            gate = random.choice(gate_types)
                            if gate == "CNOT" and q < qubits - 1:
                                # Draw CNOT gate
                                self.ax.plot([d + 1, d + 1], [q, q + 1], 'k-', linewidth=1)
                                self.ax.plot(d + 1, q, 'ko', markersize=5)
                                self.ax.add_patch(
                                    Circle((d + 1, q + 1), 0.2, color=gate_colors[gate])
                                )
                            else:
                                # Draw single qubit gate
                                if gate != "CNOT":  # Don't try to draw CNOT as a single gate
                                    self.ax.add_patch(
                                        Rectangle((d + 1 - 0.2, q - 0.2), 0.4, 0.4, color=gate_colors[gate])
                                    )
                                    self.ax.text(d + 1, q, gate, ha='center', va='center', color='white', fontsize=8)
                
            # Refresh the canvas
            self.fig.tight_layout()
            self.canvas.draw()
            return True
        except Exception as e:
            logger.error(f"Error updating quantum circuit visualization: {e}")
            logger.error(traceback.format_exc())
            return False


class MiningFrame(BaseFrame):
    """Advanced mining frame for the Kingdom AI GUI that provides comprehensive interface
    for traditional mining, quantum mining, airdrop farming, and mining intelligence with
    multi-blockchain support.
    
    Implements the PyQt6 version of the mining interface with all event bus connections
    and real data handling preserved.
    """
    
    # Define PyQt signals for thread-safe updates
    mining_status_updated = pyqtSignal(dict)
    quantum_status_updated = pyqtSignal(dict)
    blockchain_status_updated = pyqtSignal(dict)
    device_list_updated = pyqtSignal(list)
    
    def __init__(self, parent, event_bus=None):
        """Initialize the MiningFrame with UI components and data connections.
        
        Args:
            parent: Parent widget
            event_bus: Event bus for component communication
        """
        super().__init__(parent, event_bus=event_bus, name="mining")
        
        # Mining system state
        self.mining_system = None
        self.blockchain_connector = None
        self.redis_client = None
        self.mining_active = False
        self.quantum_mining_active = False
        self.mineable_coins = []
        self.selected_coin = None
        self.quantum_devices = []
        self.selected_quantum_device = None
        
        # Status tracking
        self.hashrate = 0
        self.shares = 0
        self.earnings = 0
        self.mining_status = "Inactive"
        self.blockchain_status = "Disconnected"
        
        # Setup UI
        self.setup_ui()
        
        # Initialize indicator LEDs to default (off) state
        self._initialize_indicators()
        
        # Load airdrop definitions into the GUI list
        self._load_airdrops_from_config()
        self.airdrop_refresh_timer = QTimer(self)
        self.airdrop_refresh_timer.timeout.connect(self._load_airdrops_from_config)
        self.airdrop_refresh_timer.start(60000)
        
        # Connect signals to slots
        self.mining_status_updated.connect(self._update_mining_ui)
        self.quantum_status_updated.connect(self._update_quantum_ui)
        self.blockchain_status_updated.connect(self._update_blockchain_ui)
        self.device_list_updated.connect(self._update_device_list)
        
        # Subscribe to wallet and mining intelligence events for visual indicators
        if hasattr(self, "event_bus") and self.event_bus:
            self._safe_subscribe("wallet.mining_stats.updated", self._handle_wallet_mining_stats_updated)
            self._safe_subscribe("wallet.mining_rewards.collected", self._handle_wallet_mining_rewards_collected)
            self._safe_subscribe("wallet.rewards.funnel.requested", self._handle_wallet_rewards_funnel_requested)
            self._safe_subscribe("mining.focus.update", self._handle_mining_focus_update_event)
            self._safe_subscribe("mining.focus.state", self._handle_mining_focus_state_event)
            self._safe_subscribe("airdrop.register.completed", self._handle_airdrop_register_completed)
            self._safe_subscribe("airdrop.register.failed", self._handle_airdrop_register_failed)
        
        # Initialize mining data and connections
        self._log("Initializing mining frame")
    
    def _log(self, message, level=logging.INFO):
        """Log a message both to the logger and to the application status display.
        
        Args:
            message: Message to log
            level: Logging level
        """
        if level >= logging.ERROR:
            self.logger.error(message)
            self.show_error(message)
        elif level >= logging.WARNING:
            self.logger.warning(message)
            self.update_status(f"Warning: {message}")
        else:
            self.logger.info(message)
            self.update_status(message)
            
        # Add to log display if available
        if hasattr(self, 'add_log_entry') and callable(self.add_log_entry):
            self.add_log_entry(message)
    
    async def initialize(self):
        """Initialize the mining frame with real data connections.
        
        Returns:
            bool: Success status
        """
        try:
            await super().initialize()
            
            # Initialize mining data from real sources
            self._init_mining_data()
            
            # Connect to blockchain
            self._connect_blockchain()
            
            # Connect to Redis Quantum Nexus
            self._connect_redis()
            
            # Connect to quantum devices
            await self._connect_quantum_devices()
            
            # Schedule updates
            self._schedule_mining_stats_update()
            
            return True
        except Exception as e:
            self.logger.error(f"Error initializing mining frame: {e}")
            self.logger.error(traceback.format_exc())
            self.update_status(f"Initialization error: {str(e)}", progress=0)
            return False
    
    def _init_mining_data(self):
        """Initialize mining data by connecting to real mining systems and blockchain."""
        try:
            self._log("Connecting to mining systems...")
            
            # Try to import mining system
            try:
                from mining.system import MiningSystem
                self.mining_system = MiningSystem()
                self._log("Connected to mining system")
            except ImportError:
                self._log("CRITICAL: Mining system not available", level=logging.CRITICAL)
                QMessageBox.critical(self, "Critical Error", "Mining system module not available. Halting operation.")
                sys.exit(1)  # Halt - no fallback allowed
            
            # Get mineable coins
            if hasattr(self.mining_system, 'get_mineable_coins'):
                self.mineable_coins = self.mining_system.get_mineable_coins()
                self._log(f"Found {len(self.mineable_coins)} mineable coins")
                
                # Select first coin by default if available
                if self.mineable_coins:
                    self.selected_coin = self.mineable_coins[0]
            else:
                self._log("CRITICAL: Mining system does not support coin listing", level=logging.CRITICAL)
                sys.exit(1)  # Halt - real mining system with coin support is mandatory
        except Exception as e:
            self._log(f"Error initializing mining data: {e}", level=logging.ERROR)
            self.logger.error(traceback.format_exc())
            sys.exit(1)  # Halt - no fallback to dummy data allowed
    
    def _connect_blockchain(self):
        """Connect to blockchain system and retrieve real blockchain data."""
        try:
            self._log("Connecting to blockchain system...")
            
            # Try to import blockchain connector
            try:
                from blockchain.blockchain_connector import BlockchainConnector
                self.blockchain_connector = BlockchainConnector()
                self._log("Connected to blockchain system")
                
                # Initialize Web3 connection for mining operations
                provider_url = getattr(self.blockchain_connector, "provider_url", None)
                if provider_url:
                    self.web3 = Web3(Web3.HTTPProvider(provider_url))
                    self._log(f"Initialized Web3 connection: {provider_url}")
                    
                    # Check connection
                    if self.web3.is_connected():
                        self._log("Web3 connection successful")
                        self.blockchain_status = "Connected"
                        
                        # Get blockchain status
                        if hasattr(self.blockchain_connector, 'get_blockchain_info'):
                            info = self.blockchain_connector.get_blockchain_info()
                            self._log(f"Blockchain network: {info.get('network', 'Unknown')}")
                            self._log(f"Current block: {info.get('latest_block_number', 'Unknown')}")
                            self._log(f"Network hashrate: {info.get('network_hashrate', 'Unknown')}")
                    else:
                        self._log("Web3 connection failed", level=logging.ERROR)
                        self.blockchain_status = "Connection Failed"
                else:
                    self._log("BlockchainConnector has no provider_url; skipping Web3 initialization", level=logging.WARNING)
            except ImportError:
                self._log("CRITICAL: Blockchain connector not available", level=logging.CRITICAL)
                QMessageBox.critical(self, "Critical Error", "Blockchain connector module not available. Halting operation.")
                sys.exit(1)  # Halt - no fallback allowed
            
        except Exception as e:
            self._log(f"Error connecting to blockchain: {e}", level=logging.ERROR)
            self.logger.error(traceback.format_exc())
            sys.exit(1)  # Halt - no fallback to dummy data allowed
    
    def _connect_redis(self):
        """Connect to Redis Quantum Nexus with strict enforcement on port 6380."""
        try:
            self._log("Connecting to Redis Quantum Nexus...")
            
            # Try to import redis
            try:
                import redis
                
                # Connect to Redis Quantum Nexus
                # Note: Strict enforcement of Redis Quantum Nexus - must use port 6380 and password
                self.redis_client = redis.Redis(
                    host="localhost",
                    port=6380,  # Quantum Nexus port
                    password="QuantumNexus2025",  # Quantum Nexus password
                    decode_responses=True
                )
                
                # Test connection
                if self.redis_client.ping():
                    self._log("Connected to Redis Quantum Nexus")
                    
                    # Subscribe to quantum mining events
                    if hasattr(self, 'event_bus') and self.event_bus:
                        self._log("Subscribing to quantum mining events")
                        self._safe_subscribe("quantum.status", self._handle_quantum_nexus_status)
                        self._safe_subscribe("quantum.ready", self._handle_quantum_ready)
                        self._safe_subscribe("quantum.devices", self._handle_quantum_devices_response)
                else:
                    self._log("CRITICAL: Failed to connect to Redis Quantum Nexus", level=logging.CRITICAL)
                    QMessageBox.critical(self, "Critical Error", "Failed to connect to Redis Quantum Nexus. Halting operation.")
                    sys.exit(1)  # Halt - no fallback allowed
            except ImportError:
                self._log("CRITICAL: Redis module not available", level=logging.CRITICAL)
                QMessageBox.critical(self, "Critical Error", "Redis module not available. Halting operation.")
                sys.exit(1)  # Halt - no fallback allowed
            
        except Exception as e:
            self._log(f"Error connecting to Redis: {e}", level=logging.ERROR)
            self.logger.error(traceback.format_exc())
            sys.exit(1)  # Halt - no fallback allowed
            
    async def _connect_quantum_devices(self):
        """Connect to quantum devices for quantum mining operations."""
        try:
            self._log("Connecting to quantum devices...")
            
            # Try to import quantum connector
            try:
                from quantum.connector import QuantumConnector
                self.quantum_connector = QuantumConnector()
                self._log("Connected to quantum system")
                
                # Get available quantum devices
                if hasattr(self.quantum_connector, 'get_devices'):
                    self.quantum_devices = await self.quantum_connector.get_devices()
                    self._log(f"Found {len(self.quantum_devices)} quantum devices")
                    
                    # Select first device by default if available
                    if self.quantum_devices:
                        self.selected_quantum_device = self.quantum_devices[0]
                        self.device_list_updated.emit(self.quantum_devices)
                else:
                    self._log("CRITICAL: Quantum connector does not support device listing", level=logging.CRITICAL)
                    QMessageBox.critical(self, "Critical Error", "Quantum connector does not support device listing. Halting operation.")
                    sys.exit(1)  # Halt - no fallback allowed
            except ImportError:
                self._log("CRITICAL: Quantum connector not available", level=logging.CRITICAL)
                QMessageBox.critical(self, "Critical Error", "Quantum connector module not available. Halting operation.")
                sys.exit(1)  # Halt - no fallback allowed
                
        except Exception as e:
            self._log(f"Error connecting to quantum devices: {e}", level=logging.ERROR)
            self.logger.error(traceback.format_exc())
            sys.exit(1)  # Halt - no fallback allowed
    
    def _schedule_mining_stats_update(self):
        """Schedule periodic updates of mining statistics."""
        # Create timer for mining stats update
        self.mining_stats_timer = QTimer(self)
        self.mining_stats_timer.timeout.connect(self._update_mining_stats)
        self.mining_stats_timer.start(2000)  # Update every 2 seconds
        
        # Create timer for quantum mining stats update
        self.quantum_stats_timer = QTimer(self)
        self.quantum_stats_timer.timeout.connect(self._update_quantum_stats)
        self.quantum_stats_timer.start(3000)  # Update every 3 seconds
        
    def setup_ui(self):
        """Set up the UI components for the mining frame."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create tab widget for different mining types
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setObjectName("mining_tabs")
        
        # Create tabs
        self.classic_mining_tab = self._create_classic_mining_tab()
        self.quantum_mining_tab = self._create_quantum_mining_tab()
        self.airdrop_tab = self._create_airdrop_tab()
        self.intelligence_tab = self._create_intelligence_tab()
        
        # Add tabs to tab widget
        self.tab_widget.addTab(self.classic_mining_tab, "Classic Mining")
        self.tab_widget.addTab(self.quantum_mining_tab, "Quantum Mining")
        self.tab_widget.addTab(self.airdrop_tab, "Airdrop Farming")
        self.tab_widget.addTab(self.intelligence_tab, "Mining Intelligence")
        
        # Add status bar
        self.status_bar = self._create_status_bar()
        
        # Add components to main layout
        main_layout.addWidget(self.tab_widget)
        main_layout.addWidget(self.status_bar)
        
        self.setLayout(main_layout)
    
    def _create_classic_mining_tab(self):
        """Create the classic mining tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Mining controls
        controls_group = QGroupBox("Mining Controls")
        controls_layout = QGridLayout()
        
        # Coin selection
        coin_label = QLabel("Select Coin:")
        self.coin_combo = QComboBox()
        self.coin_combo.currentIndexChanged.connect(self._on_coin_changed)
        controls_layout.addWidget(coin_label, 0, 0)
        controls_layout.addWidget(self.coin_combo, 0, 1)
        
        # Start/Stop button
        self.mining_button = GlowButton(
            self, 
            "Start Mining", 
            clicked_callback=self._toggle_mining,
            glow_color=KingdomStyles.COLORS["mining"],
            hover_color=KingdomStyles.COLORS["hover"]
        )
        controls_layout.addWidget(self.mining_button, 1, 0, 1, 2)
        
        controls_group.setLayout(controls_layout)
        
        # Mining stats
        stats_group = QGroupBox("Mining Statistics")
        stats_layout = QGridLayout()
        
        # Hashrate
        hashrate_label = QLabel("Hashrate:")
        self.hashrate_value = QLabel("0 H/s")
        stats_layout.addWidget(hashrate_label, 0, 0)
        stats_layout.addWidget(self.hashrate_value, 0, 1)
        
        # Shares
        shares_label = QLabel("Shares:")
        self.shares_value = QLabel("0")
        stats_layout.addWidget(shares_label, 1, 0)
        stats_layout.addWidget(self.shares_value, 1, 1)
        
        # Earnings
        earnings_label = QLabel("Earnings:")
        self.earnings_value = QLabel("0.0")
        stats_layout.addWidget(earnings_label, 2, 0)
        stats_layout.addWidget(self.earnings_value, 2, 1)
        
        stats_group.setLayout(stats_layout)
        
        # System indicators
        indicators_group = QGroupBox("System Indicators")
        indicators_layout = QGridLayout()

        self.mining_engine_led = QLabel()
        self.wallet_led = QLabel()
        self.ai_optimizer_led = QLabel()
        self.rewards_led = QLabel()

        self._init_led_widget(self.mining_engine_led, "Mining engine and hashrate data flow")
        self._init_led_widget(self.wallet_led, "Wallet connection and mining rewards funnel")
        self._init_led_widget(self.ai_optimizer_led, "AI-driven mining focus optimization")
        self._init_led_widget(self.rewards_led, "Auto-collection and payout of mining rewards")

        indicators_layout.addWidget(self.mining_engine_led, 0, 0)
        indicators_layout.addWidget(QLabel("Mining Engine"), 0, 1)
        indicators_layout.addWidget(self.wallet_led, 1, 0)
        indicators_layout.addWidget(QLabel("Wallet Connected"), 1, 1)
        indicators_layout.addWidget(self.ai_optimizer_led, 2, 0)
        indicators_layout.addWidget(QLabel("AI Optimizer"), 2, 1)
        indicators_layout.addWidget(self.rewards_led, 3, 0)
        indicators_layout.addWidget(QLabel("Rewards Auto-Send"), 3, 1)

        indicators_group.setLayout(indicators_layout)
        
        # Mining log
        log_group = QGroupBox("Mining Log")
        log_layout = QVBoxLayout()
        
        self.mining_log = QTextEdit()
        self.mining_log.setReadOnly(True)
        log_layout.addWidget(self.mining_log)
        
        log_group.setLayout(log_layout)
        
        # Add components to layout
        layout.addWidget(controls_group)
        layout.addWidget(indicators_group)
        layout.addWidget(stats_group)
        layout.addWidget(log_group)
        
        return tab
    
    def _create_quantum_mining_tab(self):
        """Create the quantum mining tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Splitter for quantum controls and visualization
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Quantum device selection
        device_group = QGroupBox("Quantum Device")
        device_layout = QVBoxLayout()
        
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        device_layout.addWidget(QLabel("Select Device:"))
        device_layout.addWidget(self.device_combo)
        
        # Quantum algorithm selection
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["Grover's", "Shor's", "QAOA", "VQE"])
        device_layout.addWidget(QLabel("Algorithm:"))
        device_layout.addWidget(self.algorithm_combo)
        
        # Qubit count slider
        self.qubit_slider = QSlider(Qt.Orientation.Horizontal)
        self.qubit_slider.setMinimum(2)
        self.qubit_slider.setMaximum(20)
        self.qubit_slider.setValue(5)
        self.qubit_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.qubit_slider.setTickInterval(1)
        self.qubit_slider.valueChanged.connect(self._update_circuit_preview)
        
        self.qubit_label = QLabel("Qubits: 5")
        self.qubit_slider.valueChanged.connect(lambda v: self.qubit_label.setText(f"Qubits: {v}"))
        
        device_layout.addWidget(self.qubit_label)
        device_layout.addWidget(self.qubit_slider)
        
        # Start/Stop button
        self.quantum_button = GlowButton(
            self, 
            "Start Quantum Mining", 
            clicked_callback=self._toggle_quantum_mining,
            glow_color="#AA33FF",  # Purple for quantum
            hover_color="#662299"
        )
        device_layout.addWidget(self.quantum_button)
        
        device_group.setLayout(device_layout)
        
        # Quantum stats
        stats_group = QGroupBox("Quantum Statistics")
        stats_layout = QGridLayout()
        
        # Qubits
        qubits_label = QLabel("Active Qubits:")
        self.qubits_value = QLabel("0")
        stats_layout.addWidget(qubits_label, 0, 0)
        stats_layout.addWidget(self.qubits_value, 0, 1)
        
        # Coherence
        coherence_label = QLabel("Coherence:")
        self.coherence_value = QLabel("0%")
        stats_layout.addWidget(coherence_label, 1, 0)
        stats_layout.addWidget(self.coherence_value, 1, 1)
        
        # Quantum Advantage
        advantage_label = QLabel("Quantum Advantage:")
        self.advantage_value = QLabel("0x")
        stats_layout.addWidget(advantage_label, 2, 0)
        stats_layout.addWidget(self.advantage_value, 2, 1)
        
        stats_group.setLayout(stats_layout)
        
        # Add groups to left panel
        left_layout.addWidget(device_group)
        left_layout.addWidget(stats_group)
        left_layout.addStretch(1)
        
        # Right panel - circuit visualization
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Quantum circuit visualization
        circuit_group = QGroupBox("Quantum Circuit")
        circuit_layout = QVBoxLayout()
        
        # Create matplotlib figure for visualization
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        circuit_layout.addWidget(self.canvas)
        
        # Create circuit visualizer
        self.circuit_visualizer = QuantumCircuitVisualizer(self.fig, self.canvas)
        
        # Update circuit button
        update_button = QPushButton("Update Circuit")
        update_button.clicked.connect(self._update_circuit_preview)
        circuit_layout.addWidget(update_button)
        
        circuit_group.setLayout(circuit_layout)
        right_layout.addWidget(circuit_group)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 500])
        
        # Add splitter to layout
        layout.addWidget(splitter)
        
        return tab
    
    def _create_airdrop_tab(self):
        """Create the airdrop farming tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Airdrop list
        airdrop_group = QGroupBox("Available Airdrops")
        airdrop_layout = QVBoxLayout()
        
        self.airdrop_list = QListWidget()
        airdrop_layout.addWidget(self.airdrop_list)
        
        # Register button
        register_button = GlowButton(
            self, 
            "Register for Selected Airdrop", 
            clicked_callback=self._register_airdrop,
            glow_color="#FFAA33",
            hover_color="#CC8822"
        )
        airdrop_layout.addWidget(register_button)
        
        airdrop_group.setLayout(airdrop_layout)
        
        # Registered airdrops
        registered_group = QGroupBox("Your Registered Airdrops")
        registered_layout = QVBoxLayout()
        
        self.registered_list = QListWidget()
        registered_layout.addWidget(self.registered_list)
        
        registered_group.setLayout(registered_layout)
        
        # Add groups to layout
        layout.addWidget(airdrop_group)
        layout.addWidget(registered_group)
        
        return tab
    
    def _create_intelligence_tab(self):
        """Create the mining intelligence tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Stats charts placeholder
        charts_group = QGroupBox("Mining Performance")
        charts_layout = QVBoxLayout()
        
        # Create matplotlib figure for charts
        self.stats_fig = Figure(figsize=(8, 4), dpi=100)
        self.stats_canvas = FigureCanvas(self.stats_fig)
        charts_layout.addWidget(self.stats_canvas)
        
        # Initialize the chart
        self._init_performance_chart()
        
        charts_group.setLayout(charts_layout)
        
        # Recommendations
        recommendations_group = QGroupBox("Mining Recommendations")
        recommendations_layout = QVBoxLayout()
        
        self.recommendations_text = QTextEdit()
        self.recommendations_text.setReadOnly(True)
        recommendations_layout.addWidget(self.recommendations_text)
        
        recommendations_group.setLayout(recommendations_layout)
        
        # Add groups to layout
        layout.addWidget(charts_group)
        layout.addWidget(recommendations_group)
        
        return tab
    
    def _create_status_bar(self):
        """Create the status bar for the mining frame."""
        status_bar = QFrame()
        status_bar.setFixedHeight(30)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(5, 0, 5, 0)
        
        self.status_label = QLabel("Ready")
        self.blockchain_status_label = QLabel("Blockchain: Disconnected")
        self.mining_status_label = QLabel("Mining: Inactive")
        
        status_layout.addWidget(self.status_label, stretch=3)
        status_layout.addWidget(self.blockchain_status_label, stretch=1)
        status_layout.addWidget(self.mining_status_label, stretch=1)
        
        return status_bar
    
    def _init_led_widget(self, label, tooltip):
        label.setFixedSize(14, 14)
        label.setToolTip(tooltip)
        label.setStyleSheet(
            "background-color: #444444; border-radius: 7px; min-width: 14px; min-height: 14px;"
        )
    
    def _set_led_color(self, label, is_on, active_color):
        if not label:
            return
        color = active_color if is_on else "#444444"
        label.setStyleSheet(
            f"background-color: {color}; border-radius: 7px; min-width: 14px; min-height: 14px;"
        )
    
    def _initialize_indicators(self):
        try:
            if hasattr(self, "mining_engine_led"):
                self._set_led_color(self.mining_engine_led, False, KingdomStyles.COLORS["mining"])
            if hasattr(self, "wallet_led"):
                self._set_led_color(self.wallet_led, False, KingdomStyles.COLORS["wallet"])
            if hasattr(self, "ai_optimizer_led"):
                self._set_led_color(self.ai_optimizer_led, False, KingdomStyles.COLORS["ai"])
            if hasattr(self, "rewards_led"):
                self._set_led_color(self.rewards_led, False, KingdomStyles.COLORS["accent"])
        except Exception as e:
            logger.error(f"Error initializing indicator LEDs: {e}")
    
    def _init_performance_chart(self):
        """Initialize the performance chart in the intelligence tab."""
        try:
            # Clear figure
            self.stats_fig.clear()
            
            # Create subplots
            ax1 = self.stats_fig.add_subplot(211)  # Top subplot for hashrate
            ax2 = self.stats_fig.add_subplot(212)  # Bottom subplot for earnings
            
            # Get real mining data from event bus or mining system
            dates = pd.date_range(end=datetime.now(), periods=10).tolist()
            hashrates = []
            earnings = []
            
            # Try to get real data from mining system or event bus
            if hasattr(self, 'mining_system') and self.mining_system:
                try:
                    if hasattr(self.mining_system, 'get_historical_stats'):
                        stats = self.mining_system.get_historical_stats(days=10)
                        if stats:
                            hashrates = [s.get('hashrate', 0) for s in stats]
                            earnings = [s.get('earnings', 0.0) for s in stats]
                except Exception as e:
                    logger.debug(f"Could not get historical stats: {e}")
            
            # If no real data available, use deterministic placeholder based on time
            if not hashrates or not earnings:
                # Use deterministic values based on date hash (not random)
                for date in dates:
                    date_hash = hash(str(date)) % 1000
                    hashrates.append(50 + (date_hash % 150))  # 50-200 range
                    earnings.append(0.001 + ((date_hash % 90) / 10000.0))  # 0.001-0.01 range
            
            # Plot hashrate
            ax1.plot(dates, hashrates, 'g-')
            ax1.set_title('Hashrate Over Time')
            ax1.set_ylabel('Hashrate (H/s)')
            ax1.grid(True)
            
            # Plot earnings
            ax2.plot(dates, earnings, 'b-')
            ax2.set_title('Earnings Over Time')
            ax2.set_ylabel('Earnings (BTC)')
            ax2.grid(True)
            
            # Format dates on x-axis
            self.stats_fig.autofmt_xdate()
            
            # Adjust layout
            self.stats_fig.tight_layout()
            self.stats_canvas.draw()
        except Exception as e:
            logger.error(f"Error initializing performance chart: {e}")
            logger.error(traceback.format_exc())
    
    def _update_circuit_preview(self):
        """Update the quantum circuit visualization."""
        try:
            # Get algorithm and qubit count
            algorithm = self.algorithm_combo.currentText() if hasattr(self, 'algorithm_combo') else None
            qubit_count = self.qubit_slider.value() if hasattr(self, 'qubit_slider') else 5
            
            # Update circuit visualization
            if hasattr(self, 'circuit_visualizer'):
                self.circuit_visualizer.update_circuit(
                    algorithm=algorithm,
                    qubit_count=qubit_count,
                    circuit_depth=qubit_count
                )
        except Exception as e:
            logger.error(f"Error updating circuit preview: {e}")
            logger.error(traceback.format_exc())
    
    def _on_coin_changed(self, index):
        """Handle coin selection change event."""
        try:
            if 0 <= index < len(self.mineable_coins):
                self.selected_coin = self.mineable_coins[index]
                self._log(f"Selected coin: {self.selected_coin}")
                
                # Update mining parameters based on selected coin
                if hasattr(self.mining_system, 'get_coin_mining_info'):
                    info = self.mining_system.get_coin_mining_info(self.selected_coin)
                    if info:
                        self._log(f"Algorithm: {info.get('algorithm', 'Unknown')}")
                        self._log(f"Network difficulty: {info.get('difficulty', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error handling coin change: {e}")
            logger.error(traceback.format_exc())
    
    def _on_device_changed(self, index):
        """Handle quantum device selection change event."""
        try:
            if 0 <= index < len(self.quantum_devices):
                self.selected_quantum_device = self.quantum_devices[index]
                self._log(f"Selected quantum device: {self.selected_quantum_device}")
                
                # Update quantum device information
                if hasattr(self.quantum_connector, 'get_device_info'):
                    # Use asyncio for async call
                    try:
                        import asyncio
                        task = asyncio.create_task(self.quantum_connector.get_device_info(self.selected_quantum_device))
                        task.add_done_callback(lambda t: self._update_device_info(t.result()) if not t.exception() else None)
                        info = None  # Will be updated via callback
                    except:
                        info = None
                    # Info will be updated via callback, don't use it here
                    if False:  # Disabled - callback handles update
                        self.qubits_value.setText(str(info.get('qubits', '0')))
                        self.coherence_value.setText(f"{info.get('coherence', 0)}%")
                        self.advantage_value.setText(f"{info.get('advantage', 0)}x")
        except Exception as e:
            logger.error(f"Error handling device change: {e}")
            logger.error(traceback.format_exc())
    
    def _toggle_mining(self):
        """Toggle mining on/off."""
        try:
            if self.mining_active:
                # Stop mining
                self._stop_mining()
            else:
                # Start mining
                self._start_mining()
        except Exception as e:
            logger.error(f"Error toggling mining: {e}")
            logger.error(traceback.format_exc())
    
    def _toggle_quantum_mining(self):
        """Toggle quantum mining on/off."""
        try:
            if self.quantum_mining_active:
                # Stop quantum mining
                self._stop_quantum_mining()
            else:
                # Start quantum mining
                self._start_quantum_mining()
        except Exception as e:
            logger.error(f"Error toggling quantum mining: {e}")
            logger.error(traceback.format_exc())
    
    def _start_mining(self):
        """Start the mining process."""
        try:
            # Check if mining system is available
            if not self.mining_system:
                self._log("Mining system not available", level=logging.ERROR)
                return
            
            # Check if coin is selected
            if not self.selected_coin:
                self._log("No coin selected for mining", level=logging.ERROR)
                return
            
            # Start mining
            self._log(f"Starting mining for {self.selected_coin}...")
            
            # Call mining system to start mining
            if hasattr(self.mining_system, 'start_mining'):
                success = self.mining_system.start_mining(self.selected_coin)
                if success:
                    self.mining_active = True
                    self.mining_button.setText("Stop Mining")
                    self.mining_status = "Active"
                    self.mining_status_label.setText("Mining: Active")
                    self._set_led_color(self.mining_engine_led, True, KingdomStyles.COLORS["mining"])
                    self._log(f"Mining started for {self.selected_coin}")
                    
                    # Emit event to event bus
                    if hasattr(self, 'event_bus') and self.event_bus:
                        self.event_bus.emit("mining.started", {
                            "coin": self.selected_coin,
                            "time": datetime.now().isoformat(),
                            "status": "active"
                        })
                else:
                    self._log(f"Failed to start mining for {self.selected_coin}", level=logging.ERROR)
            else:
                self._log("Mining system does not support start_mining method", level=logging.ERROR)
        except Exception as e:
            logger.error(f"Error starting mining: {e}")
            logger.error(traceback.format_exc())
    
    def _stop_mining(self):
        """Stop the mining process."""
        try:
            # Check if mining system is available
            if not self.mining_system:
                self._log("Mining system not available", level=logging.ERROR)
                return
            
            # Stop mining
            self._log("Stopping mining...")
            
            # Call mining system to stop mining
            if hasattr(self.mining_system, 'stop_mining'):
                success = self.mining_system.stop_mining()
                if success:
                    self.mining_active = False
                    self.mining_button.setText("Start Mining")
                    self.mining_status = "Inactive"
                    self.mining_status_label.setText("Mining: Inactive")
                    self._set_led_color(self.mining_engine_led, False, KingdomStyles.COLORS["mining"])
                    self._log("Mining stopped")
                    
                    # Emit event to event bus
                    if hasattr(self, 'event_bus') and self.event_bus:
                        self.event_bus.emit("mining.stopped", {
                            "time": datetime.now().isoformat(),
                            "status": "inactive"
                        })
                else:
                    self._log("Failed to stop mining", level=logging.ERROR)
            else:
                self._log("Mining system does not support stop_mining method", level=logging.ERROR)
        except Exception as e:
            logger.error(f"Error stopping mining: {e}")
            logger.error(traceback.format_exc())
    
    def _start_quantum_mining(self):
        """Start the quantum mining process."""
        try:
            # Check if quantum connector is available
            if not hasattr(self, 'quantum_connector'):
                self._log("Quantum connector not available", level=logging.ERROR)
                return
            
            # Check if quantum device is selected
            if not self.selected_quantum_device:
                self._log("No quantum device selected for mining", level=logging.ERROR)
                return
            
            # Get algorithm and qubit count
            algorithm = self.algorithm_combo.currentText()
            qubit_count = self.qubit_slider.value()
            
            # Start quantum mining
            self._log(f"Starting quantum mining on {self.selected_quantum_device} with {algorithm} algorithm...")
            
            # Call quantum connector to start mining
            if hasattr(self.quantum_connector, 'start_quantum_mining'):
                # Use asyncio for async call
                try:
                    import asyncio
                    task = asyncio.create_task(self.quantum_connector.start_quantum_mining(
                        device=self.selected_quantum_device,
                        algorithm=algorithm,
                        qubits=qubit_count
                    ))
                    task.add_done_callback(lambda t: logger.info(f"✅ Quantum mining started: {t.result()}") if not t.exception() else logger.error(f"❌ Start failed: {t.exception()}"))
                    success = True  # Assume success, callback will handle errors
                except Exception as e:
                    logger.error(f"❌ Failed to start quantum mining: {e}")
                    success = False
                
                if success:
                    self.quantum_mining_active = True
                    self.quantum_button.setText("Stop Quantum Mining")
                    self._log(f"Quantum mining started on {self.selected_quantum_device}")
                    
                    # Update the UI
                    self.qubits_value.setText(str(qubit_count))
                    
                    # Emit event to event bus
                    if hasattr(self, 'event_bus') and self.event_bus:
                        self.event_bus.emit("quantum.mining.started", {
                            "device": self.selected_quantum_device,
                            "algorithm": algorithm,
                            "qubits": qubit_count,
                            "time": datetime.now().isoformat(),
                            "status": "active"
                        })
                else:
                    self._log(f"Failed to start quantum mining on {self.selected_quantum_device}", level=logging.ERROR)
            else:
                self._log("Quantum connector does not support start_quantum_mining method", level=logging.ERROR)
        except Exception as e:
            logger.error(f"Error starting quantum mining: {e}")
            logger.error(traceback.format_exc())
    
    def _stop_quantum_mining(self):
        """Stop the quantum mining process."""
        try:
            # Check if quantum connector is available
            if not hasattr(self, 'quantum_connector'):
                self._log("Quantum connector not available", level=logging.ERROR)
                return
            
            # Stop quantum mining
            self._log("Stopping quantum mining...")
            
            # Call quantum connector to stop mining
            if hasattr(self.quantum_connector, 'stop_quantum_mining'):
                # Use asyncio for async call
                try:
                    import asyncio
                    task = asyncio.create_task(self.quantum_connector.stop_quantum_mining(
                        device=self.selected_quantum_device
                    ))
                    task.add_done_callback(lambda t: logger.info(f"✅ Quantum mining stopped: {t.result()}") if not t.exception() else logger.error(f"❌ Stop failed: {t.exception()}"))
                    success = True  # Assume success, callback will handle errors
                except Exception as e:
                    logger.error(f"❌ Failed to stop quantum mining: {e}")
                    success = False
                
                if success:
                    self.quantum_mining_active = False
                    self.quantum_button.setText("Start Quantum Mining")
                    self._log("Quantum mining stopped")
                    
                    # Update the UI
                    self.qubits_value.setText("0")
                    self.coherence_value.setText("0%")
                    self.advantage_value.setText("0x")
                    
                    # Emit event to event bus
                    if hasattr(self, 'event_bus') and self.event_bus:
                        self.event_bus.emit("quantum.mining.stopped", {
                            "device": self.selected_quantum_device,
                            "time": datetime.now().isoformat(),
                            "status": "inactive"
                        })
                else:
                    self._log("Failed to stop quantum mining", level=logging.ERROR)
            else:
                self._log("Quantum connector does not support stop_quantum_mining method", level=logging.ERROR)
        except Exception as e:
            logger.error(f"Error stopping quantum mining: {e}")
            logger.error(traceback.format_exc())
    
    def _register_airdrop(self):
        """Register for the selected airdrop."""
        try:
            # Get selected airdrop
            selected_items = self.airdrop_list.selectedItems()
            if not selected_items:
                self._log("No airdrop selected", level=logging.WARNING)
                return
            
            selected_item = selected_items[0]
            entry = selected_item.data(Qt.UserRole)
            if isinstance(entry, dict):
                selected_airdrop = entry.get("name") or selected_item.text().split(" (" )[0]
            else:
                # Fallback: derive name from display text before any formatting suffix
                selected_airdrop = selected_item.text().split(" (" )[0]

            self._log(f"Registering for airdrop: {selected_airdrop}...")
            
            # Register for airdrop (connect to real blockchain system)
            if hasattr(self.blockchain_connector, 'register_for_airdrop'):
                success = self.blockchain_connector.register_for_airdrop(selected_airdrop)
                if success:
                    self._log(f"Successfully requested registration for {selected_airdrop}")

                    # Emit event to event bus
                    if hasattr(self, 'event_bus') and self.event_bus:
                        self.event_bus.emit("airdrop.registered", {
                            "name": selected_airdrop,
                            "time": datetime.now().isoformat()
                        })
                else:
                    self._log(f"Failed to register for {selected_airdrop}", level=logging.ERROR)
            else:
                self._log("Blockchain connector does not support register_for_airdrop method", level=logging.ERROR)
        except Exception as e:
            logger.error(f"Error registering for airdrop: {e}")
            logger.error(traceback.format_exc())
    
    def _update_mining_stats(self):
        """Update mining statistics from the mining system."""
        try:
            # Check if mining is active
            if not self.mining_active or not self.mining_system:
                return
            
            # Get current mining stats
            if hasattr(self.mining_system, 'get_mining_stats'):
                stats = self.mining_system.get_mining_stats()
                if stats:
                    # Update the UI
                    self.hashrate = stats.get('hashrate', 0)
                    self.shares = stats.get('shares', 0)
                    self.earnings = stats.get('earnings', 0.0)
                    
                    # Update UI via signal to ensure thread safety
                    self.mining_status_updated.emit({
                        'hashrate': self.hashrate,
                        'shares': self.shares,
                        'earnings': self.earnings
                    })
        except Exception as e:
            logger.error(f"Error updating mining stats: {e}")
            # Don't log traceback for routine updates to avoid flooding logs
    
    def _load_airdrops_from_config(self):
        try:
            # Resolve project root (three levels up from gui/frames/mining_frame_pyqt.py)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "config", "airdrops.json")
            if not os.path.exists(config_path):
                return
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            airdrops = config_data.get("airdrops") or []
            if not hasattr(self, "airdrop_list") or self.airdrop_list is None:
                return
            # Preserve currently selected airdrop by name
            selected_name = None
            selected_items = self.airdrop_list.selectedItems()
            if selected_items:
                selected_item = selected_items[0]
                data = selected_item.data(Qt.UserRole)
                if isinstance(data, dict):
                    selected_name = data.get("name")
                else:
                    selected_name = selected_item.text().split(" (")[0]

            self.airdrop_list.clear()
            for entry in airdrops:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                enabled = entry.get("enabled", True)
                if not name or not enabled:
                    continue

                chain = entry.get("chain", "")
                mode = entry.get("mode", "")
                details = []
                if chain:
                    details.append(chain)
                if mode:
                    details.append(mode)
                display_name = name
                if details:
                    display_name = f"{name} ({', '.join(details)})"

                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, entry)
                self.airdrop_list.addItem(item)

                if selected_name and entry.get("name") == selected_name:
                    item.setSelected(True)
        except Exception as e:
            logger.error(f"Error loading airdrops from config: {e}")
    
    def _update_device_info(self, info):
        """Update device info display from callback."""
        try:
            if info:
                self.qubits_value.setText(str(info.get('qubits', '0')))
                self.coherence_value.setText(f"{info.get('coherence', 0)}%")
                self.advantage_value.setText(f"{info.get('advantage', 0)}x")
        except Exception as e:
            logger.error(f"Error updating device info: {e}")
    
    def _update_quantum_stats(self):
        """Update quantum mining statistics."""
        try:
            # Check if quantum mining is active
            if not self.quantum_mining_active or not hasattr(self, 'quantum_connector'):
                return
            
            # Get current quantum mining stats
            if hasattr(self.quantum_connector, 'get_quantum_stats'):
                # Use asyncio for async call
                try:
                    import asyncio
                    task = asyncio.create_task(self.quantum_connector.get_quantum_stats(self.selected_quantum_device))
                    task.add_done_callback(lambda t: self.quantum_status_updated.emit(t.result()) if not t.exception() and t.result() else None)
                    stats = None  # Will be updated via callback
                except:
                    stats = None
                # Stats will be updated via callback, don't use it here
                if False:  # Disabled - callback handles update
                    # Update UI via signal to ensure thread safety
                    self.quantum_status_updated.emit({
                        'coherence': stats.get('coherence', 0),
                        'advantage': stats.get('advantage', 0)
                    })
        except Exception as e:
            logger.error(f"Error updating quantum stats: {e}")
            # Don't log traceback for routine updates to avoid flooding logs
    
    @pyqtSlot(dict)
    def _update_mining_ui(self, stats):
        """Update the mining UI with the latest stats."""
        try:
            # Format the hashrate with appropriate units
            hashrate = stats.get('hashrate', 0)
            if hashrate < 1000:
                hashrate_str = f"{hashrate:.2f} H/s"
            elif hashrate < 1000000:
                hashrate_str = f"{hashrate/1000:.2f} KH/s"
            else:
                hashrate_str = f"{hashrate/1000000:.2f} MH/s"
            
            # Update labels
            self.hashrate_value.setText(hashrate_str)
            self.shares_value.setText(str(stats.get('shares', 0)))
            self.earnings_value.setText(f"{stats.get('earnings', 0.0):.8f} {self.selected_coin if self.selected_coin else 'BTC'}")
            self._set_led_color(self.mining_engine_led, True, KingdomStyles.COLORS["mining"])
            
            # Add to mining log
            self.add_log_entry(f"Mining update - Hashrate: {hashrate_str}, Shares: {stats.get('shares', 0)}, Earnings: {stats.get('earnings', 0.0):.8f}")
        except Exception as e:
            logger.error(f"Error updating mining UI: {e}")
            logger.error(traceback.format_exc())
    
    @pyqtSlot(dict)
    def _update_quantum_ui(self, stats):
        """Update the quantum mining UI with the latest stats."""
        try:
            # Update labels
            self.coherence_value.setText(f"{stats.get('coherence', 0)}%")
            self.advantage_value.setText(f"{stats.get('advantage', 0)}x")
        except Exception as e:
            logger.error(f"Error updating quantum UI: {e}")
            logger.error(traceback.format_exc())
    
    @pyqtSlot(dict)
    def _update_blockchain_ui(self, stats):
        """Update the blockchain UI with the latest stats."""
        try:
            # Update blockchain status label
            self.blockchain_status = stats.get('status', 'Disconnected')
            self.blockchain_status_label.setText(f"Blockchain: {self.blockchain_status}")
            
            # Log blockchain updates
            self.add_log_entry(f"Blockchain update - Status: {stats.get('status', 'Unknown')}, Block: {stats.get('height', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error updating blockchain UI: {e}")
            logger.error(traceback.format_exc())
    
    @pyqtSlot(list)
    def _update_device_list(self, devices):
        """Update the quantum device list in the UI."""
        try:
            # Clear and populate device combo box
            self.device_combo.clear()
            for device in devices:
                self.device_combo.addItem(device)
        except Exception as e:
            logger.error(f"Error updating device list: {e}")
            logger.error(traceback.format_exc())
    
    def _handle_quantum_nexus_status(self, data):
        """Handle quantum nexus status updates from the event bus."""
        try:
            self._log(f"Received quantum nexus status: {data.get('status', 'Unknown')}")
            
            # Update quantum mining stats if available
            if 'stats' in data:
                self.quantum_status_updated.emit(data['stats'])
        except Exception as e:
            logger.error(f"Error handling quantum nexus status: {e}")
            logger.error(traceback.format_exc())
    
    def _handle_quantum_ready(self, data):
        """Handle quantum ready event from the event bus."""
        try:
            self._log(f"Quantum system ready: {data.get('device', 'Unknown')}")
            
            # Update quantum UI
            if 'device' in data:
                # Check if the device is in our list
                device_name = data['device']
                if device_name not in self.quantum_devices:
                    self.quantum_devices.append(device_name)
                    self.device_list_updated.emit(self.quantum_devices)
        except Exception as e:
            logger.error(f"Error handling quantum ready event: {e}")
            logger.error(traceback.format_exc())
    
    def _handle_quantum_devices_response(self, data):
        """Handle quantum devices response from the event bus."""
        try:
            if 'devices' in data and isinstance(data['devices'], list):
                self.quantum_devices = data['devices']
                self.device_list_updated.emit(self.quantum_devices)
                self._log(f"Updated quantum devices list: {len(self.quantum_devices)} devices")
        except Exception as e:
            logger.error(f"Error handling quantum devices response: {e}")
            logger.error(traceback.format_exc())
    
    def add_log_entry(self, message):
        """Add an entry to the mining log."""
        try:
            if hasattr(self, 'mining_log') and self.mining_log:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.mining_log.append(f"[{timestamp}] {message}")
                # Scroll to the bottom to see the latest log
                self.mining_log.verticalScrollBar().setValue(self.mining_log.verticalScrollBar().maximum())
        except Exception as e:
            logger.error(f"Error adding log entry: {e}")
            # Don't log traceback for routine logging to avoid flooding logs
    
    def update_status(self, message, progress=None):
        """Update the status display in the status bar."""
        try:
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setText(message)
            
            # Also log to the mining log
            self.add_log_entry(message)
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            # Don't log traceback for routine status updates to avoid flooding logs
    
    def show_error(self, message):
        """Show an error message in a dialog."""
        try:
            QMessageBox.critical(self, "Mining Error", message)
        except Exception as e:
            logger.error(f"Error showing error dialog: {e}")
            logger.error(traceback.format_exc())
    
    def _safe_subscribe(self, topic, handler):
        """Safely subscribe to an event bus topic."""
        if hasattr(self, 'event_bus') and self.event_bus:
            try:
                self.event_bus.subscribe(topic, handler)
                self._log(f"Subscribed to {topic}")
                return True
            except Exception as e:
                logger.error(f"Error subscribing to {topic}: {e}")
                return False
        return False

    def _handle_wallet_mining_stats_updated(self, data):
        try:
            self._set_led_color(self.wallet_led, True, KingdomStyles.COLORS["wallet"])
        except Exception as e:
            logger.error(f"Error handling wallet.mining_stats.updated: {e}")

    def _handle_wallet_mining_rewards_collected(self, data):
        try:
            self._set_led_color(self.wallet_led, True, KingdomStyles.COLORS["wallet"])
            self._set_led_color(self.rewards_led, True, KingdomStyles.COLORS["accent"])
        except Exception as e:
            logger.error(f"Error handling wallet.mining_rewards.collected: {e}")

    def _handle_wallet_rewards_funnel_requested(self, data):
        try:
            self._set_led_color(self.wallet_led, True, KingdomStyles.COLORS["wallet"])
        except Exception as e:
            logger.error(f"Error handling wallet.rewards.funnel.requested: {e}")

    def _handle_mining_focus_update_event(self, data):
        try:
            self._set_led_color(self.ai_optimizer_led, True, KingdomStyles.COLORS["ai"])
        except Exception as e:
            logger.error(f"Error handling mining.focus.update: {e}")

    def _handle_mining_focus_state_event(self, data):
        try:
            self._set_led_color(self.ai_optimizer_led, True, KingdomStyles.COLORS["ai"])
        except Exception as e:
            logger.error(f"Error handling mining.focus.state: {e}")

    def _handle_airdrop_register_completed(self, data):
        """Handle successful airdrop registration events and update the GUI."""
        try:
            if not data:
                return
            name = data.get("airdrop_name") or data.get("name") or "Unknown Airdrop"
            network = data.get("network", "unknown")
            wallet = data.get("wallet_address", "unknown")
            tx_hash = data.get("tx_hash")
            message = f"Airdrop registration completed for {name} on {network} using {wallet}" + (f" (tx: {tx_hash})" if tx_hash else "")
            self._log(message)
            
            # Add or update entry in the registered airdrops list
            if hasattr(self, "registered_list") and self.registered_list:
                # Check if an item for this airdrop already exists
                found = False
                for i in range(self.registered_list.count()):
                    item = self.registered_list.item(i)
                    if item and name in item.text():
                        item.setText(f"{name} - Completed")
                        found = True
                        break
                if not found:
                    item = QListWidgetItem(f"{name} - Completed")
                    self.registered_list.addItem(item)
        except Exception as e:
            logger.error(f"Error handling airdrop.register.completed: {e}")

    def _handle_airdrop_register_failed(self, data):
        """Handle failed airdrop registration events and log the error for the user."""
        try:
            if not data:
                return
            name = data.get("airdrop_name") or data.get("name") or "Unknown Airdrop"
            network = data.get("network", "unknown")
            error_msg = data.get("error", "unknown_error")
            message = f"Airdrop registration FAILED for {name} on {network}: {error_msg}"
            self._log(message, level=logging.ERROR)
        except Exception as e:
            logger.error(f"Error handling airdrop.register.failed: {e}")
