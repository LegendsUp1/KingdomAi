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
import logging
import traceback
import secrets  # For cryptographically secure random number generation
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
import re
import socket
import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
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
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QCheckBox, QProgressBar, QGroupBox, QTabWidget, QSplitter,
    QTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QFrame, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, QDateTime
from PyQt6.QtGui import QColor, QFont, QPalette

# Local imports
from core.mining_system import MiningSystem
from blockchain.blockchain_connector import BlockchainConnector
from core.event_bus import EventBus
from core.redis_nexus import RedisQuantumNexus
from utils.async_support import async_slot, AsyncSupport
from utils.qt_styles import get_style_sheet, get_icon
from utils.redis_security import get_redis_password, get_redis_config

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
        self.ax = fig.add_subplot(111)
        self.canvas = canvas
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
        """Update the quantum circuit visualization.
        
        Args:
            algorithm: Quantum algorithm name
            qubit_count: Number of qubits
            circuit_depth: Circuit depth/complexity
            
        Returns:
            bool: Success status
        """
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
                        # Use secure random number generation
                        # These are only for visualization purposes, not for cryptography,
                        # but we use secrets to follow best practices
                        if q < qubits - 1 and (secrets.randbelow(100)/100) < 0.3:
                            # Draw controlled gate
                            self.ax.plot([d + 1, d + 1], [q, q + 1], 'k-', linewidth=1)
                            self.ax.plot(d + 1, q, 'ko', markersize=5)
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
                        self.ax.plot([d + 1, d + 1], [q, q + d], 'k-', linewidth=1)
                        self.ax.plot(d + 1, q, 'ko', markersize=5)
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
                self.ax.set_title(f"{algorithm} Algorithm Circuit")
                
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
        self.parent = parent
        self.event_bus = event_bus or EventBus()
        
        # Initialize variables
        self.hashrate = "0.00 H/s"
        self.shares_accepted = 0
        self.rejected_shares = 0
        self.blockchain = "None"
        self.earnings = "0.00000000"
        self.uptime = "00:00:00"
        self.mining_status = "Stopped"
        
        # Quantum variables
        self.quantum_device = "None"
        self.q_algorithm = "None"
        self.qubit_count = 5
        self.circuit_depth = 3
        self.q_mining_status = "Disconnected"
        self.q_progress = 0.0
        self.error_correction = False
        self.auto_optimize = False
        self.entanglement = False
        self.quantum_status = "Disconnected"
        self.q_hashrate = "0.00 QH/s"
        self.q_efficiency = "0.0%"
        self.q_connection = "Not connected"
        self.q_earnings = "0.00000000"
        self.blockchain_status = "Disconnected"
        self.blockchain_progress = 0.0
        
        # Setup UI
        self.setup_ui()
        
        # Connect to systems (mandatory)
        self._init_mining_data()
        
        # Setup event bus subscribers
        self._subscribe_to_events()
        
        # Update UI elements with initial data
        self.update_mining_stats()
        self.update_quantum_stats()
        
        # Start timer for UI updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_uptime)
        self.update_timer.start(1000)  # Update every second
        
    def _log(self, message, level=logging.INFO):
        """Log a message both to the logger and to the application status display."""
        logger.log(level, message)
        if hasattr(self, 'event_bus') and self.event_bus:
            try:
                self.event_bus.publish('gui_update', {
                    'component': 'mining_tab',
                    'message': message,
                    'level': level,
                    'timestamp': time.time()
                })
            except Exception as e:
                logger.error(f"Error publishing log message to event bus: {e}")
                
    def setup_ui(self):
        """Setup the Mining Tab UI components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create tabs for different mining functions
        tabs = QTabWidget()
        
        # Add tabs
        tabs.addTab(self._create_traditional_mining_tab(), "Traditional Mining")
        tabs.addTab(self._create_quantum_mining_tab(), "Quantum Mining")
        tabs.addTab(self._create_mining_intelligence_tab(), "Mining Intelligence")
        tabs.addTab(self._create_blockchain_tab(), "Blockchain Status")
        tabs.addTab(self._create_airdrop_farming_tab(), "Airdrop Farming")
        
        # Add to main layout
        main_layout.addWidget(tabs)
        
        # Create status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Mining System: Initializing...")
        self.status_label.setStyleSheet("color: orange;")
        status_layout.addWidget(self.status_label)
        
        # Add blockchain status indicator
        self.blockchain_status_label = QLabel("Blockchain: Disconnected")
        self.blockchain_status_label.setStyleSheet("color: red;")
        status_layout.addWidget(self.blockchain_status_label)
        
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
        layout = QVBoxLayout(tab)
        
        # Control panel
        control_group = QGroupBox("Mining Control")
        control_layout = QVBoxLayout(control_group)
        
        # Settings layout
        settings_layout = QHBoxLayout()
        
        # Blockchain selection
        blockchain_layout = QVBoxLayout()
        blockchain_layout.addWidget(QLabel("Blockchain:"))
        self.blockchain_combo = QComboBox()
        self.blockchain_combo.addItems(["Bitcoin", "Ethereum", "Litecoin", "Monero", "Zcash"])
        self.blockchain_combo.currentTextChanged.connect(self._on_blockchain_changed)
        blockchain_layout.addWidget(self.blockchain_combo)
        settings_layout.addLayout(blockchain_layout)
        
        # Mining pool
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
        self.start_button.clicked.connect(self._on_start_mining)
        self.stop_button = QPushButton("Stop Mining")
        self.stop_button.clicked.connect(self._on_stop_mining)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
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
        self.earnings_label = QLabel("0.00000000")
        stats_layout.addWidget(self.earnings_label, 4, 1)
        
        stats_layout.addWidget(QLabel("Uptime:"), 5, 0)
        self.uptime_label = QLabel("00:00:00")
        stats_layout.addWidget(self.uptime_label, 5, 1)
        
        # Add spacer
        stats_layout.setRowStretch(6, 1)
        
        layout.addWidget(stats_group)
        
        # Hashrate chart
        chart_group = QGroupBox("Hashrate History")
        chart_layout = QVBoxLayout(chart_group)
        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        chart_layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Hashrate over Time")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Hashrate (H/s)")
        self.ax.grid(True)
        
        layout.addWidget(chart_group)
        
        return tab
    
    def _create_quantum_mining_tab(self):
        """Create the quantum mining tab with controls and visualization."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Top section with control panel and stats
        top_layout = QHBoxLayout()
        
        # Control panel
        control_group = QGroupBox("Quantum Mining Control")
        control_layout = QVBoxLayout(control_group)
        
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
        
        top_layout.addWidget(control_group)
        
        # Stats panel
        q_stats_group = QGroupBox("Quantum Mining Statistics")
        q_stats_layout = QGridLayout(q_stats_group)
        
        q_stats_layout.addWidget(QLabel("Status:"), 0, 0)
        self.q_mining_status_label = QLabel("Disconnected")
        self.q_mining_status_label.setStyleSheet("color: red;")
        q_stats_layout.addWidget(self.q_mining_status_label, 0, 1)
        
        q_stats_layout.addWidget(QLabel("Quantum Hashrate:"), 1, 0)
        self.q_hashrate_label = QLabel("0.00 QH/s")
        q_stats_layout.addWidget(self.q_hashrate_label, 1, 1)
        
        q_stats_layout.addWidget(QLabel("Quantum Efficiency:"), 2, 0)
        self.q_efficiency_label = QLabel("0.0%")
        q_stats_layout.addWidget(self.q_efficiency_label, 2, 1)
        
        q_stats_layout.addWidget(QLabel("Connection Quality:"), 3, 0)
        self.q_connection_label = QLabel("Not connected")
        q_stats_layout.addWidget(self.q_connection_label, 3, 1)
        
        q_stats_layout.addWidget(QLabel("Quantum Earnings:"), 4, 0)
        self.q_earnings_label = QLabel("0.00000000")
        q_stats_layout.addWidget(self.q_earnings_label, 4, 1)
        
        q_stats_layout.addWidget(QLabel("Progress:"), 5, 0)
        self.q_progress_bar = QProgressBar()
        self.q_progress_bar.setValue(0)
        q_stats_layout.addWidget(self.q_progress_bar, 5, 1)
        
        top_layout.addWidget(q_stats_group)
        
        layout.addLayout(top_layout)
        
        # Quantum Circuit Visualization
        q_circuit_group = QGroupBox("Quantum Circuit Visualization")
        q_circuit_layout = QVBoxLayout(q_circuit_group)
        self.q_figure = Figure(figsize=(10, 4), dpi=100)
        self.q_canvas = FigureCanvas(self.q_figure)
        q_circuit_layout.addWidget(self.q_canvas)
        
        # Initialize visualizer
        self.quantum_visualization = QuantumCircuitVisualizer(self.q_figure, self.q_canvas)
        self.quantum_visualization.update_circuit(algorithm="Generic", qubit_count=5, circuit_depth=3)
        
        # Update button
        q_viz_button_layout = QHBoxLayout()
        self.update_circuit_button = QPushButton("Update Circuit Visualization")
        self.update_circuit_button.clicked.connect(self._on_update_quantum_circuit)
        q_viz_button_layout.addWidget(self.update_circuit_button)
        q_circuit_layout.addLayout(q_viz_button_layout)
        
        layout.addWidget(q_circuit_group)
        
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
        
        # Add profit chart
        self.profit_figure = Figure(figsize=(8, 4), dpi=100)
        self.profit_canvas = FigureCanvas(self.profit_figure)
        self.profit_ax = self.profit_figure.add_subplot(111)
        self.profit_ax.set_title("Projected Mining Profit")
        self.profit_ax.set_xlabel("Time")
        self.profit_ax.set_ylabel("Profit (USD)")
        self.profit_ax.grid(True)
        profit_layout.addWidget(self.profit_canvas)
        
        layout.addWidget(profit_group)
        
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
    
    def _init_mining_data(self) -> None:
        """Initialize mining data by connecting to real mining systems and blockchain.
        
        This method enforces strict connection requirements with no fallbacks.
        System will halt if any connection fails.
        """
        try:
            self._log("Initializing mining data...", level=logging.INFO)
            
            # Try to get mining system component
            try:
                from core.mining_system import MiningSystem
                MiningTab.mining_system = MiningSystem(event_bus=self.event_bus)
                self._log("Successfully obtained mining system instance", level=logging.INFO)
            except ImportError:
                self._log("Could not import MiningSystem, trying alternative paths", level=logging.WARNING)
                try:
                    import importlib.util
                    import sys
                    _project_root = str(Path(__file__).resolve().parent.parent.parent)
                    paths = [
                        "core/mining_system.py",
                        os.path.join(_project_root, "core", "mining_system.py"),
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

            # Connect to Redis Quantum Nexus - mandatory, no fallback
            self._connect_redis()
            
            # Connect to blockchain
            self._connect_blockchain()
            
            # Connect to quantum devices
            self._connect_quantum_devices()
            
            # Request initial mining data if event bus is available
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                try:
                    self.event_bus.publish("mining.get_status", {"source": "mining_tab"})
                    self._log("Requested initial mining data", level=logging.INFO)
                except Exception as e:
                    logger.error(f"Critical error initializing mining data: {e}")
                    self._log(f"Critical error initializing mining data: {e}", level=logging.CRITICAL)
                    self._log("CRITICAL: Kingdom AI requires real mining data to function", level=logging.CRITICAL)
                    sys.exit(1)  # Halt system - proper handling with real data is mandatory
        except Exception as e:
            logger.error(f"Error initializing mining data: {e}\n{traceback.format_exc()}")
            self._log(f"CRITICAL: Failed to initialize mining data: {e}", level=logging.CRITICAL)
            sys.exit(1)  # Enforce real data initialization

    def _connect_blockchain(self) -> None:
        """Connect to blockchain system and retrieve real blockchain data.
        
        Connection is mandatory with no fallbacks allowed. System will halt if connection fails.
        """
        try:
            self._log("Connecting to blockchain system...", level=logging.INFO)         
            # Try to get blockchain connector component
            try:
                from blockchain.blockchain_connector import BlockchainConnector
                MiningTab.blockchain_connector = BlockchainConnector(event_bus=self.event_bus)
                self._log("Successfully obtained blockchain connector instance", level=logging.INFO)
            except ImportError:
                self._log("Could not import BlockchainConnector, trying alternative paths", level=logging.WARNING)
                try:
                    import importlib.util
                    import sys
                    _project_root = str(Path(__file__).resolve().parent.parent.parent)
                    paths = [
                        "blockchain/blockchain_connector.py",
                        os.path.join(_project_root, "blockchain", "blockchain_connector.py"),
                    ]
                    for path in paths:
                        try:
                            spec = importlib.util.spec_from_file_location("blockchain_connector", path)
                            if spec and spec.loader:
                                blockchain_module = importlib.util.module_from_spec(spec)
                                sys.modules["blockchain_connector"] = blockchain_module
                                spec.loader.exec_module(blockchain_module)
                                BlockchainConnector = blockchain_module.BlockchainConnector
                                MiningTab.blockchain_connector = BlockchainConnector(event_bus=self.event_bus)
                                self._log("Successfully loaded BlockchainConnector from alternative path", level=logging.INFO)
                                break
                        except Exception as e:
                            self._log(f"Failed to load from {path}: {e}", level=logging.ERROR)
                            continue
                    else:
                        self._log("CRITICAL: Failed to load BlockchainConnector from any alternative path", level=logging.CRITICAL)
                        sys.exit(1)  # System halts - blockchain connector is mandatory
                except Exception as e:
                    logger.error(f"Unexpected error loading blockchain connector: {e}\n{traceback.format_exc()}")
                    self._log(f"CRITICAL: Unexpected error loading blockchain connector: {e}", level=logging.CRITICAL)
                    sys.exit(1)  # System halts - blockchain connector is mandatory

            # Check blockchain connection status - mandatory, no fallback
            if hasattr(MiningTab.blockchain_connector, 'is_connected'):
                is_connected_result = MiningTab.blockchain_connector.is_connected
                if callable(is_connected_result):
                    is_connected_result = is_connected_result()
                if asyncio.iscoroutine(is_connected_result):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    is_connected = loop.run_until_complete(is_connected_result)
                else:
                    is_connected = is_connected_result

                if not is_connected:
                    self._log("CRITICAL: Blockchain connector failed to connect", level=logging.CRITICAL)
                    sys.exit(1)  # System halts - blockchain connection is mandatory
                else:
                    self._log("Blockchain connector is connected", level=logging.INFO)
                    self.blockchain_status_label.setText("Blockchain: Connected")
                    self.blockchain_status_label.setStyleSheet("color: green;")
            else:
                self._log("CRITICAL: Blockchain connector does not have is_connected method", level=logging.CRITICAL)
                sys.exit(1)  # System halts - blockchain connection check is mandatory
        except Exception as e:
            logger.error(f"Error connecting to blockchain: {e}\n{traceback.format_exc()}")
            self._log(f"CRITICAL: Failed to connect to blockchain: {e}", level=logging.CRITICAL)
            sys.exit(1)  # Enforce real blockchain connectivity - no fallbacks

    def _connect_redis(self) -> None:
        """Connect to Redis Quantum Nexus with strict enforcement on port 6380.
        
        Connection is mandatory with no fallbacks allowed. System will halt if connection fails.
        """
        try:
            import redis
            self._log("Connecting to Redis Quantum Nexus on port 6380...", level=logging.INFO)
            # Use the centralized Redis security module for password handling
            redis_client = redis.Redis(
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
        except redis.AuthenticationError:
            self._log("CRITICAL: Redis authentication failure", level=logging.CRITICAL)
            sys.exit(1)  # System halts - correct credentials are mandatory
        except redis.ConnectionError:
            self._log("CRITICAL: Redis connection failure", level=logging.CRITICAL)
            sys.exit(1)  # System halts - connection is mandatory
        except redis.TimeoutError:
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
            self.event_bus.publish("quantum.nexus.query.devices", {
                "source": "mining_tab",
                "request_id": str(uuid.uuid4()),
                "mandatory": True,  # Connection is mandatory - no fallbacks
                "port": redis_port,
                "password": redis_password
            })
            
            # This will be handled asynchronously via event bus callbacks
        except Exception as e:
            logger.error(f"Error connecting to quantum devices: {e}\n{traceback.format_exc()}")
            self._log(f"CRITICAL: Failed to connect to quantum devices: {e}", level=logging.CRITICAL)
            sys.exit(1)  # Enforce real quantum device connectivity - no fallbacks

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
            if self.quantum_circuit_visualizer:
                if circuit_data:
                    # Use provided circuit data if available
                    success = self.quantum_circuit_visualizer.update_circuit_data(circuit_data)
                else:
                    # Otherwise update based on algorithm and parameters
                    success = self.quantum_circuit_visualizer.update_circuit(algorithm, qubit_count, circuit_depth)
                
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
                self.quantum_mining_circuits_value.setText(str(data["circuits_processed"]))
            
            if "success_rate" in data:
                self.quantum_mining_success_value.setText(f"{data['success_rate']:.2f}%")
                
            if "advantage_factor" in data:
                self.quantum_mining_advantage_value.setText(f"{data['advantage_factor']:.2f}x")
                
            # Create notification for significant results
            if success and data.get("significant", False):
                self.show_notification(
                    "Quantum Mining Success", 
                    f"{result_type}: {message}", 
                    level="success"
                )
                
            # Update circuit visualization if provided
            if "circuit_data" in data and self.quantum_circuit_visualizer:
                self.quantum_circuit_visualizer.update_circuit_data(data["circuit_data"])
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
                if "efficiency" in intel_data and self.mining_intel_efficiency_value:
                    self.mining_intel_efficiency_value.setText(f"{intel_data['efficiency']:.2f}%")
                
                if "projected_earnings" in intel_data and self.mining_intel_earnings_value:
                    self.mining_intel_earnings_value.setText(
                        f"{intel_data['projected_earnings']:.8f}"
                    )
                
                if "optimal_threads" in intel_data and self.mining_intel_threads_value:
                    self.mining_intel_threads_value.setText(str(intel_data["optimal_threads"]))
                
                if "network_share" in intel_data and self.mining_intel_share_value:
                    self.mining_intel_share_value.setText(f"{intel_data['network_share']:.6f}%")
            
            elif intel_type == "profit_prediction":
                # Update profit prediction chart
                if "prediction_data" in intel_data and isinstance(intel_data["prediction_data"], list):
                    self.profit_history = intel_data["prediction_data"]
                    self._update_profit_chart()
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
            if self.mining_intel_recommendations_list:
                self.mining_intel_recommendations_list.clear()
                
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
                    
                    self.mining_intel_recommendations_list.addItem(item)
                
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

    def _handle_mining_intelligence_profit_prediction(self, data: dict) -> None:
        """Handle mining profit prediction updates from the event bus."""
        try:
            prediction_data = data.get("prediction_data", [])
            if not prediction_data:
                return
                
            self._log("Received mining profit prediction update", level=logging.INFO)
            
            # Update profit history and chart
            self.profit_history = prediction_data
            self._update_profit_chart()
            
            # Update summary statistics if provided
            if "daily_estimate" in data and self.mining_intel_daily_value:
                self.mining_intel_daily_value.setText(f"{data['daily_estimate']:.8f}")
            
            if "weekly_estimate" in data and self.mining_intel_weekly_value:
                self.mining_intel_weekly_value.setText(f"{data['weekly_estimate']:.8f}")
            
            if "monthly_estimate" in data and self.mining_intel_monthly_value:
                self.mining_intel_monthly_value.setText(f"{data['monthly_estimate']:.8f}")
        except Exception as e:
            logger.error(f"Error handling mining profit prediction: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling mining profit prediction: {e}", level=logging.ERROR)

    # Airdrop farming event handlers
    def _handle_airdrop_campaigns_update(self, data: dict) -> None:
        """Handle airdrop campaigns updates from the event bus."""
        try:
            campaigns = data.get("campaigns", [])
            if not campaigns:
                return
                
            self._log(f"Received {len(campaigns)} airdrop campaigns", level=logging.INFO)
            
            # Update campaigns table
            if self.airdrop_campaigns_table:
                self.airdrop_campaigns_table.setRowCount(0)  # Clear existing rows
                
                for campaign in campaigns:
                    row_position = self.airdrop_campaigns_table.rowCount()
                    self.airdrop_campaigns_table.insertRow(row_position)
                    
                    # Campaign Name
                    name_item = QTableWidgetItem(campaign.get("name", "Unknown"))
                    self.airdrop_campaigns_table.setItem(row_position, 0, name_item)
                    
                    # Status
                    status = campaign.get("status", "inactive")
                    status_item = QTableWidgetItem(status.capitalize())
                    if status.lower() == "active":
                        status_item.setForeground(QColor("green"))
                    elif status.lower() == "completed":
                        status_item.setForeground(QColor("blue"))
                    self.airdrop_campaigns_table.setItem(row_position, 1, status_item)
                    
                    # Reward
                    reward = campaign.get("reward", "Unknown")
                    reward_item = QTableWidgetItem(reward)
                    self.airdrop_campaigns_table.setItem(row_position, 2, reward_item)
                    
                    # Progress
                    progress = campaign.get("progress", 0)
                    progress_item = QTableWidgetItem(f"{progress:.1f}%")
                    self.airdrop_campaigns_table.setItem(row_position, 3, progress_item)
                    
                    # ETA
                    eta = campaign.get("eta", "Unknown")
                    eta_item = QTableWidgetItem(eta)
                    self.airdrop_campaigns_table.setItem(row_position, 4, eta_item)
                
                self.airdrop_campaigns_table.resizeColumnsToContents()
        except Exception as e:
            logger.error(f"Error handling airdrop campaigns update: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling airdrop campaigns update: {e}", level=logging.ERROR)

    def _handle_airdrop_farming_status(self, data: dict) -> None:
        """Handle airdrop farming status updates from the event bus."""
        try:
            status = data.get("status", "inactive")
            
            self._log(f"Airdrop farming status update: {status}", level=logging.INFO)
            
            # Update farming status and button state
            if status.lower() == "active":
                self.airdrop_start_button.setText("Stop Farming")
                self.airdrop_start_button.setStyleSheet("background-color: #990000;")
                
                if self.airdrop_status_value:
                    self.airdrop_status_value.setText("Active")
                    self.airdrop_status_value.setStyleSheet("color: green;")
            else:  # inactive or any other state
                self.airdrop_start_button.setText("Start Farming")
                self.airdrop_start_button.setStyleSheet("background-color: #006600;")
                
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

    def subscribe_to_events(self) -> None:
        """Subscribe to event bus events for mining operations.
        
        These subscriptions enable real-time updates to the mining UI based on
        backend events from the mining system, blockchain, and quantum devices.
        """
        if not self.event_bus:
            self._log("Cannot subscribe to events - no event bus available", level=logging.CRITICAL)
            return
        
        self._log("Subscribing to mining events...", level=logging.INFO)
        
        # Traditional mining events
        self.event_bus.subscribe("mining.status_update", self._handle_mining_status_update)
        self.event_bus.subscribe("mining.hashrate_update", self._handle_hashrate_update)
        self.event_bus.subscribe("mining.worker_update", self._handle_worker_update)
        self.event_bus.subscribe("mining.new_block_found", self._handle_new_block_found)
        self.event_bus.subscribe("mining.error", self._handle_mining_error)
        
        # Blockchain events
        self.event_bus.subscribe("blockchain.status_update", self._handle_blockchain_status_update)
        self.event_bus.subscribe("blockchain.network_stats", self._handle_blockchain_network_stats)
        self.event_bus.subscribe("blockchain.market_data", self._handle_blockchain_market_data)
        self.event_bus.subscribe("blockchain.blocks", self._handle_blockchain_blocks)
        
        # Quantum mining events
        self.event_bus.subscribe("quantum.mining.status", self._handle_quantum_mining_status)
        self.event_bus.subscribe("quantum.mining.circuit_update", self._handle_quantum_circuit_update)
        self.event_bus.subscribe("quantum.mining.result", self._handle_quantum_mining_result)
        self.event_bus.subscribe("quantum.device.status", self._handle_quantum_device_status)
        
        # Mining intelligence events
        self.event_bus.subscribe("mining.intelligence.update", self._handle_mining_intelligence_update)
        self.event_bus.subscribe("mining.intelligence.recommendation", self._handle_mining_intelligence_recommendation)
        self.event_bus.subscribe("mining.intelligence.profit_prediction", self._handle_mining_intelligence_profit_prediction)
        
        # Airdrop farming events
        self.event_bus.subscribe("airdrop.campaigns.update", self._handle_airdrop_campaigns_update)
        self.event_bus.subscribe("airdrop.farming.status", self._handle_airdrop_farming_status)
        self.event_bus.subscribe("airdrop.farming.history", self._handle_airdrop_farming_history)
        
        self._log("Successfully subscribed to all mining events", level=logging.INFO)

    # Traditional mining event handlers
    def _handle_mining_status_update(self, data: dict) -> None:
        """Handle mining status updates from the event bus."""
        try:
            status = data.get("status")
            if status:
                self._log(f"Mining status update received: {status}", level=logging.INFO)
                
                # Update mining system status label
                if status == "running":
                    self.mining_status_label.setText("Mining: Active")
                    self.mining_status_label.setStyleSheet("color: green;")
                    self.trad_mining_start_button.setText("Stop Mining")
                    self.trad_mining_start_button.setStyleSheet("background-color: #990000;")
                elif status == "stopped":
                    self.mining_status_label.setText("Mining: Inactive")
                    self.mining_status_label.setStyleSheet("color: #AA0000;")
                    self.trad_mining_start_button.setText("Start Mining")
                    self.trad_mining_start_button.setStyleSheet("background-color: #006600;")
                elif status == "paused":
                    self.mining_status_label.setText("Mining: Paused")
                    self.mining_status_label.setStyleSheet("color: #CCAA00;")
                    self.trad_mining_start_button.setText("Resume Mining")
                    self.trad_mining_start_button.setStyleSheet("background-color: #006600;")
                    
                # Update mining statistics
                if "hashrate" in data:
                    self.trad_mining_hashrate_value.setText(f"{data['hashrate']:.2f} H/s")
                if "shares" in data:
                    self.trad_mining_shares_value.setText(f"{data['shares']}")
                if "rejects" in data:
                    self.trad_mining_rejects_value.setText(f"{data['rejects']}")
                if "blocks_found" in data:
                    self.trad_mining_blocks_value.setText(f"{data['blocks_found']}")
                if "uptime" in data:
                    hours, remainder = divmod(int(data['uptime']), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self.trad_mining_uptime_value.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        except Exception as e:
            logger.error(f"Error handling mining status update: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling mining status update: {e}", level=logging.ERROR)

    def _handle_hashrate_update(self, data: dict) -> None:
        """Handle hashrate updates from the event bus."""
        try:
            if "hashrate" in data:
                hashrate = data["hashrate"]
                self.trad_mining_hashrate_value.setText(f"{hashrate:.2f} H/s")
                
                # Update hashrate history for the chart
                timestamp = data.get("timestamp", time.time())
                self.hashrate_history.append((timestamp, hashrate))
                
                # Keep only the last 100 points
                if len(self.hashrate_history) > 100:
                    self.hashrate_history = self.hashrate_history[-100:]
                    
                # Update the hashrate chart
                self._update_hashrate_chart()
        except Exception as e:
            logger.error(f"Error handling hashrate update: {e}\n{traceback.format_exc()}")
            self._log(f"Error handling hashrate update: {e}", level=logging.ERROR)

    def _handle_worker_update(self, data: dict) -> None:
        """Handle worker updates from the event bus."""
        try:
            if "workers" in data:
                workers = data["workers"]
                worker_count = len(workers)
                active_workers = sum(1 for w in workers if w.get("status") == "active")
                
                self.trad_mining_workers_value.setText(f"{active_workers}/{worker_count}")
                
                # Update worker threads combobox if available workers changed
                current_worker_count = self.trad_mining_threads_combo.count()
                if worker_count != current_worker_count:
                    self.trad_mining_threads_combo.clear()
                    for i in range(1, worker_count + 1):
                        self.trad_mining_threads_combo.addItem(str(i))
                    
                    # Select the number of active workers
                    self.trad_mining_threads_combo.setCurrentIndex(active_workers - 1)
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
                self.trad_mining_start_button.setStyleSheet("background-color: #006600;")
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
                    self.quantum_mining_start_button.setStyleSheet("background-color: #990000;")
                elif status == "stopped":
                    self.quantum_status_label.setText("Quantum Mining: Inactive")
                    self.quantum_status_label.setStyleSheet("color: #AA0000;")
                    self.quantum_mining_start_button.setText("Start Quantum Mining")
                    self.quantum_mining_start_button.setStyleSheet("background-color: #006600;")
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
