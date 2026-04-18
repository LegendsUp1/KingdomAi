"""
Kingdom AI Blockchain Tab - PyQt6 Implementation
Comprehensive blockchain network monitoring and interaction
"""

from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QLinearGradient, QFont

# SOTA 2026: Thread-safe UI update utility
try:
    from utils.qt_thread_safe import is_main_thread, run_on_main_thread
    THREAD_SAFE_AVAILABLE = True
except ImportError:
    THREAD_SAFE_AVAILABLE = False
    def is_main_thread(): return True
    def run_on_main_thread(func): func()
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, 
    QTextEdit, QFrame, QScrollArea, QGroupBox, QGridLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QMessageBox,
    QTabWidget, QProgressBar, QHeaderView, QApplication
)
import logging
import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# SOTA 2026: Tab Highway System for isolated computational pipelines
try:
    from core.tab_highway_system import (
        get_highway, TabType, run_on_blockchain_highway,
        blockchain_highway, get_tab_highway_manager
    )
    HAS_TAB_HIGHWAY = True
except ImportError:
    HAS_TAB_HIGHWAY = False
    def run_on_blockchain_highway(func, *args, **kwargs):
        return ThreadPoolExecutor(max_workers=2).submit(func, *args, **kwargs)

# Initialize logger early so it's available for all import error handling
logger = logging.getLogger("KingdomAI.BlockchainTab")

# Component Factory
try:
    from gui.qt_frames.component_factory import ComponentFactory, ComponentConfig
except ImportError:
    ComponentFactory = None
    ComponentConfig = None

# Blockchain imports
try:
    from blockchain.blockchain_connector import BlockchainConnector
    BLOCKCHAIN_CONNECTOR_AVAILABLE = True
except ImportError:
    BLOCKCHAIN_CONNECTOR_AVAILABLE = False
    BlockchainConnector = None

# CRITICAL FIX: Try multiple import paths for blockchain networks
COMPLETE_BLOCKCHAIN_NETWORKS = {}
try:
    from core.blockchain.kingdomweb3_v2 import COMPLETE_BLOCKCHAIN_NETWORKS
except ImportError:
    try:
        # Fallback to root level kingdomweb3_v2
        from kingdomweb3_v2 import COMPLETE_BLOCKCHAIN_NETWORKS
    except ImportError:
        logger.warning("Failed to import blockchain networks from kingdomweb3_v2")
        COMPLETE_BLOCKCHAIN_NETWORKS = {}

# Log the result
if COMPLETE_BLOCKCHAIN_NETWORKS:
    logger.info(f"✅ Loaded {len(COMPLETE_BLOCKCHAIN_NETWORKS)} blockchain networks")
else:
    logger.warning("⚠️ No blockchain networks loaded - GUI will show limited options")

# Timer utilities - SOTA 2026: Use QTimer directly for simplicity
def start_timer_safe(timer, interval, callback=None):
    """Start a QTimer safely - supports both old and new signatures"""
    if callback is not None:
        timer.timeout.connect(callback)
    timer.start(interval)

def stop_timer_safe(timer):
    """Stop a QTimer safely"""
    timer.stop()


class BlockchainTab(QWidget):
    """
    Blockchain Tab - Network monitoring, smart contract interaction, and blockchain analytics.
    
    Features:
    - Multi-chain network monitoring
    - Smart contract interaction
    - Transaction tracking
    - Gas price monitoring
    - Block explorer integration
    """
    
    # Signals
    network_changed = pyqtSignal(str)
    balance_updated = pyqtSignal(str, float)
    transaction_sent = pyqtSignal(dict)
    contract_called = pyqtSignal(dict)
    
    def __init__(self, event_bus=None, blockchain_connector=None):
        super().__init__()
        
        self.logger = logging.getLogger("KingdomAI.BlockchainTab")
        self.event_bus = event_bus
        self.blockchain_connector = blockchain_connector
        
        # State
        self.current_network = "ethereum"
        self.networks = COMPLETE_BLOCKCHAIN_NETWORKS or {}
        self.connected_networks = {}
        self.gas_prices = {}
        self.block_heights = {}
        
        # UI components
        self.network_combo = None
        self.status_label = None
        self.gas_label = None
        self.block_label = None
        self.contract_address_input = None
        self.contract_abi_input = None
        self.transaction_table = None
        
        # Timers
        self._refresh_timer = None
        self._gas_timer = None
        
        # Initialize UI
        self._init_ui()
        
        # Deferred initialization
        QTimer.singleShot(500, self._deferred_blockchain_init)
        
        # Subscribe to events
        if self.event_bus:
            self._subscribe_events()

    def _setup_complete_ui(self):
        """Post-initialization: verify blockchain backend and refresh live data.
        
        Called by KingdomMainWindow after all tabs and event bus components
        are fully registered, making backends reachable.
        """
        try:
            self.logger.info("BlockchainTab: running _setup_complete_ui backend verification...")

            # 1. Ensure blockchain connector is available
            if not self.blockchain_connector and self.event_bus:
                if hasattr(self.event_bus, 'get_component'):
                    self.blockchain_connector = self.event_bus.get_component('blockchain_connector')
                    if self.blockchain_connector:
                        self.logger.info("BlockchainTab: acquired blockchain_connector from event bus")

            # 2. Verify connector is connected
            if self.blockchain_connector:
                connected = False
                if hasattr(self.blockchain_connector, 'is_connected'):
                    is_conn = self.blockchain_connector.is_connected
                    connected = is_conn() if callable(is_conn) else bool(is_conn)
                if connected:
                    self.logger.info("BlockchainTab: blockchain connector verified CONNECTED")
                else:
                    self.logger.warning("BlockchainTab: blockchain connector exists but not connected")
                    # Try to reconnect
                    if hasattr(self.blockchain_connector, 'connect'):
                        self.blockchain_connector.connect()
            else:
                self.logger.warning("BlockchainTab: no blockchain_connector available")

            # 3. Force an immediate network stats refresh
            if hasattr(self, '_refresh_network_stats_sync'):
                self._refresh_network_stats_sync()

            # 4. Populate networks if not already done
            if hasattr(self, '_populate_networks'):
                self._populate_networks()

            self.logger.info("✅ BlockchainTab _setup_complete_ui complete")
        except Exception as e:
            self.logger.warning(f"BlockchainTab _setup_complete_ui non-critical error: {e}")

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Main content area with tabs
        content_tabs = QTabWidget()
        content_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #333; background: #1a1a2e; }
            QTabBar::tab { background: #16213e; color: #fff; padding: 8px 16px; margin-right: 2px; }
            QTabBar::tab:selected { background: #0f3460; border-bottom: 2px solid #00ff88; }
        """)
        
        # Network Status Tab
        network_tab = self._create_network_tab()
        content_tabs.addTab(network_tab, "Network Status")
        
        # Smart Contracts Tab
        contracts_tab = self._create_contracts_tab()
        content_tabs.addTab(contracts_tab, "Smart Contracts")
        
        # Transactions Tab
        transactions_tab = self._create_transactions_tab()
        content_tabs.addTab(transactions_tab, "Transactions")
        
        # Explorer Tab
        explorer_tab = self._create_explorer_tab()
        content_tabs.addTab(explorer_tab, "Block Explorer")
        
        # Wallet Send/Receive Tab — direct chain-level wallet operations
        wallet_ops_tab = self._create_wallet_ops_tab()
        content_tabs.addTab(wallet_ops_tab, "Wallet Send/Receive")
        
        main_layout.addWidget(content_tabs)
        
        # Status bar
        self.status_bar = QLabel("Initializing blockchain connections...")
        self.status_bar.setStyleSheet("color: #888; padding: 5px;")
        main_layout.addWidget(self.status_bar)
    
    def _create_header(self):
        """Create header section."""
        header = QFrame()
        header.setStyleSheet("background: #16213e; border-radius: 8px; padding: 10px;")
        layout = QHBoxLayout(header)
        
        # Title
        title = QLabel("Blockchain Networks")
        title.setStyleSheet("color: #00ff88; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Network selector
        layout.addWidget(QLabel("Network:"))
        self.network_combo = QComboBox()
        self.network_combo.setMinimumWidth(200)
        self.network_combo.setStyleSheet("""
            QComboBox { background: #1a1a2e; color: #fff; padding: 5px; border: 1px solid #333; }
            QComboBox::drop-down { border: none; }
        """)
        self._populate_networks()
        self.network_combo.currentTextChanged.connect(self._on_network_changed)
        layout.addWidget(self.network_combo)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("background: #0f3460; color: #fff; padding: 8px 16px;")
        refresh_btn.clicked.connect(self._refresh_network_stats_sync)
        layout.addWidget(refresh_btn)
        
        return header
    
    def _create_network_tab(self):
        """Create network status tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Stats grid
        stats_group = QGroupBox("Network Statistics")
        stats_group.setStyleSheet("QGroupBox { color: #00ff88; border: 1px solid #333; }")
        stats_layout = QGridLayout(stats_group)
        
        # Status
        stats_layout.addWidget(QLabel("Status:"), 0, 0)
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #ff6b6b;")
        stats_layout.addWidget(self.status_label, 0, 1)
        
        # Block height
        stats_layout.addWidget(QLabel("Block Height:"), 1, 0)
        self.block_label = QLabel("--")
        self.block_label.setStyleSheet("color: #4ecdc4;")
        stats_layout.addWidget(self.block_label, 1, 1)
        
        # Gas price
        stats_layout.addWidget(QLabel("Gas Price:"), 2, 0)
        self.gas_label = QLabel("-- Gwei")
        self.gas_label.setStyleSheet("color: #ffe66d;")
        stats_layout.addWidget(self.gas_label, 2, 1)
        
        # Network peers
        stats_layout.addWidget(QLabel("Peers:"), 3, 0)
        self.peers_label = QLabel("--")
        self.peers_label.setStyleSheet("color: #a8e6cf;")
        stats_layout.addWidget(self.peers_label, 3, 1)
        
        layout.addWidget(stats_group)
        
        # Connected networks list
        networks_group = QGroupBox("Connected Networks")
        networks_group.setStyleSheet("QGroupBox { color: #00ff88; border: 1px solid #333; }")
        networks_layout = QVBoxLayout(networks_group)
        
        self.networks_table = QTableWidget()
        self.networks_table.setColumnCount(4)
        self.networks_table.setHorizontalHeaderLabels(["Network", "Status", "Block", "Gas"])
        self.networks_table.horizontalHeader().setStretchLastSection(True)
        self.networks_table.setStyleSheet("""
            QTableWidget { background: #1a1a2e; color: #fff; border: none; }
            QHeaderView::section { background: #16213e; color: #00ff88; }
        """)
        networks_layout.addWidget(self.networks_table)
        
        layout.addWidget(networks_group)
        
        return tab
    
    def _create_contracts_tab(self):
        """Create smart contracts tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Contract interaction group
        interact_group = QGroupBox("Smart Contract Interaction")
        interact_group.setStyleSheet("QGroupBox { color: #00ff88; border: 1px solid #333; }")
        interact_layout = QGridLayout(interact_group)
        
        # Contract address
        interact_layout.addWidget(QLabel("Contract Address:"), 0, 0)
        self.contract_address_input = QLineEdit()
        self.contract_address_input.setPlaceholderText("Enter contract address (0x...)")
        self.contract_address_input.setStyleSheet("""
            QLineEdit {
                background-color: #1A1A2E;
                color: #00FF00;
                border: 2px solid #00FF00;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                font-weight: bold;
                min-height: 40px;
            }
            QLineEdit:focus {
                border: 3px solid #00FFFF;
                background-color: #0F0F1E;
                color: #00FFFF;
            }
            QLineEdit:hover {
                border: 2px solid #00FFFF;
                background-color: #151525;
            }
        """)
        interact_layout.addWidget(self.contract_address_input, 0, 1)
        
        # ABI input
        interact_layout.addWidget(QLabel("Contract ABI:"), 1, 0, Qt.AlignmentFlag.AlignTop)
        self.contract_abi_input = QTextEdit()
        self.contract_abi_input.setPlaceholderText("Paste contract ABI JSON here...")
        self.contract_abi_input.setMaximumHeight(150)
        self.contract_abi_input.setStyleSheet("""
            QTextEdit { background: #1a1a2e; color: #fff; border: 1px solid #333; }
        """)
        interact_layout.addWidget(self.contract_abi_input, 1, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.load_contract_btn = QPushButton("Load Contract")
        self.load_contract_btn.setStyleSheet("background: #0f3460; color: #fff; padding: 8px 16px;")
        self.load_contract_btn.clicked.connect(self._load_contract)
        btn_layout.addWidget(self.load_contract_btn)
        
        self.call_contract_btn = QPushButton("Call Function")
        self.call_contract_btn.setStyleSheet("""
            QPushButton {
                background: linear-gradient(135deg, #6a5acd, #9370db);
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: rgba(197, 125, 255, 220);
            }
        """)
        self.call_contract_btn.clicked.connect(self._call_contract_function_safe)
        btn_layout.addWidget(self.call_contract_btn)
        
        self.gas_optimize_btn = QPushButton("Optimize Gas")
        self.gas_optimize_btn.setStyleSheet("background: #0f3460; color: #fff; padding: 8px 16px;")
        self.gas_optimize_btn.clicked.connect(self._optimize_gas)
        btn_layout.addWidget(self.gas_optimize_btn)
        
        interact_layout.addLayout(btn_layout, 2, 1)
        
        layout.addWidget(interact_group)
        
        # Contract results
        results_group = QGroupBox("Contract Results")
        results_group.setStyleSheet("QGroupBox { color: #00ff88; border: 1px solid #333; }")
        results_layout = QVBoxLayout(results_group)
        
        self.contract_results = QTextEdit()
        self.contract_results.setReadOnly(True)
        self.contract_results.setStyleSheet("background: #1a1a2e; color: #a8e6cf; font-family: monospace;")
        results_layout.addWidget(self.contract_results)
        
        layout.addWidget(results_group)
        
        return tab
    
    def _create_transactions_tab(self):
        """Create transactions tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Transaction history
        self.transaction_table = QTableWidget()
        self.transaction_table.setColumnCount(6)
        self.transaction_table.setHorizontalHeaderLabels(["Hash", "From", "To", "Value", "Gas", "Status"])
        self.transaction_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.transaction_table.setStyleSheet("""
            QTableWidget { background: #1a1a2e; color: #fff; border: none; }
            QHeaderView::section { background: #16213e; color: #00ff88; }
        """)
        layout.addWidget(self.transaction_table)
        
        return tab
    
    def _create_explorer_tab(self):
        """Create block explorer tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Search bar
        search_layout = QHBoxLayout()
        self.explorer_search = QLineEdit()
        self.explorer_search.setPlaceholderText("Search by address, tx hash, or block number...")
        self.explorer_search.setStyleSheet("background: #1a1a2e; color: #fff; padding: 8px; border: 1px solid #333;")
        search_layout.addWidget(self.explorer_search)
        
        search_btn = QPushButton("Search")
        search_btn.setStyleSheet("background: #0f3460; color: #fff; padding: 8px 16px;")
        search_btn.clicked.connect(self._search_explorer)
        search_layout.addWidget(search_btn)
        
        layout.addLayout(search_layout)
        
        # Results area
        self.explorer_results = QTextEdit()
        self.explorer_results.setReadOnly(True)
        self.explorer_results.setStyleSheet("background: #1a1a2e; color: #fff; font-family: monospace;")
        layout.addWidget(self.explorer_results)
        
        return tab
    
    def _create_wallet_ops_tab(self):
        """Create the Wallet Send/Receive tab linked to all KingdomWeb3 chains."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info_label = QLabel("Send or receive on any chain connected to KingdomWeb3 v2. "
                            "AI validates every outgoing transaction via Ollama.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #aaa; padding: 4px;")
        layout.addWidget(info_label)

        form_group = QGroupBox("Send Transaction")
        form_group.setStyleSheet("QGroupBox { color: #00ff88; border: 1px solid #333; }")
        form_layout = QVBoxLayout(form_group)

        # Network selector (all chains)
        net_row = QHBoxLayout()
        net_row.addWidget(QLabel("Chain:"))
        self._wops_network = QComboBox()
        self._wops_network.setMinimumWidth(220)
        self._wops_network.setStyleSheet(
            "QComboBox { background: #1a1a2e; color: #fff; padding: 5px; border: 1px solid #333; }")
        chains = list(self.networks.keys()) if self.networks else []
        for c in sorted(chains):
            self._wops_network.addItem(c.title(), c)
        net_row.addWidget(self._wops_network)
        net_row.addStretch()
        form_layout.addLayout(net_row)

        # Recipient
        addr_row = QHBoxLayout()
        addr_row.addWidget(QLabel("To Address:"))
        self._wops_address = QLineEdit()
        self._wops_address.setPlaceholderText("0x... or recipient address")
        self._wops_address.setStyleSheet(
            "background: #1a1a2e; color: #fff; padding: 8px; border: 1px solid #333;")
        addr_row.addWidget(self._wops_address)
        form_layout.addLayout(addr_row)

        # Amount
        amt_row = QHBoxLayout()
        amt_row.addWidget(QLabel("Amount:"))
        self._wops_amount = QLineEdit()
        self._wops_amount.setPlaceholderText("0.0")
        self._wops_amount.setStyleSheet(
            "background: #1a1a2e; color: #fff; padding: 8px; border: 1px solid #333;")
        amt_row.addWidget(self._wops_amount)
        form_layout.addLayout(amt_row)

        send_btn = QPushButton("Send Transaction (AI Validated)")
        send_btn.setStyleSheet(
            "background: #e94560; color: #fff; padding: 10px 24px; font-weight: bold; "
            "border-radius: 6px;")
        send_btn.clicked.connect(self._blockchain_tab_send)
        form_layout.addWidget(send_btn)

        layout.addWidget(form_group)

        # Receive section
        recv_group = QGroupBox("Receive — Your Address on Selected Chain")
        recv_group.setStyleSheet("QGroupBox { color: #00ff88; border: 1px solid #333; }")
        recv_layout = QVBoxLayout(recv_group)

        self._wops_recv_label = QLabel("Select a chain above to view your receive address.")
        self._wops_recv_label.setWordWrap(True)
        self._wops_recv_label.setTextInteractionFlags(
            self._wops_recv_label.textInteractionFlags()
            | self._wops_recv_label.textInteractionFlags().__class__(1))  # selectable
        self._wops_recv_label.setStyleSheet(
            "color: #fff; font-family: monospace; padding: 8px; background: #1a1a2e; "
            "border: 1px solid #333; border-radius: 4px;")
        recv_layout.addWidget(self._wops_recv_label)
        self._wops_network.currentIndexChanged.connect(self._update_recv_address)
        layout.addWidget(recv_group)

        # Result area
        self._wops_result = QTextEdit()
        self._wops_result.setReadOnly(True)
        self._wops_result.setMaximumHeight(120)
        self._wops_result.setStyleSheet(
            "background: #1a1a2e; color: #0f0; font-family: monospace;")
        layout.addWidget(self._wops_result)
        layout.addStretch()

        return tab

    def _blockchain_tab_send(self):
        """Execute a send via wallet_manager.send_transaction from the blockchain tab."""
        try:
            network = self._wops_network.currentData() or "ethereum"
            to_addr = self._wops_address.text().strip()
            amount_text = self._wops_amount.text().strip()
            if not to_addr or not amount_text:
                self._wops_result.setText("ERROR: Address and amount are required.")
                return
            amount = float(amount_text)

            wm = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wm = self.event_bus.get_component('wallet_manager')
            if not wm:
                self._wops_result.setText("ERROR: WalletManager not initialized.")
                return

            self._wops_result.setText(f"Sending {amount} on {network} to {to_addr[:20]}... (AI validating)")
            try:
                tx_hash = wm.send_transaction(network.upper(), to_addr, amount)
                self._wops_result.setText(
                    f"SUCCESS\nNetwork: {network}\nTo: {to_addr}\n"
                    f"Amount: {amount}\nTX Hash: {tx_hash}")
            except ValueError as ve:
                self._wops_result.setText(f"BLOCKED: {ve}")
            except ConnectionError as ce:
                self._wops_result.setText(f"CONNECTION ERROR: {ce}")
            except Exception as ex:
                self._wops_result.setText(f"ERROR: {ex}")
        except Exception as e:
            self._wops_result.setText(f"ERROR: {e}")

    def _update_recv_address(self):
        """Update the receive address label when chain selection changes."""
        network = self._wops_network.currentData() or ""
        wm = None
        if self.event_bus and hasattr(self.event_bus, 'get_component'):
            wm = self.event_bus.get_component('wallet_manager')
        if wm and hasattr(wm, 'get_address'):
            addr = wm.get_address(network)
            if addr:
                self._wops_recv_label.setText(f"Chain: {network}\nAddress: {addr}")
                return
        self._wops_recv_label.setText(f"No wallet configured for {network}")

    def _populate_networks(self):
        """Populate network selector with available networks."""
        if self.network_combo:
            self.network_combo.clear()
            networks = list(self.networks.keys()) if self.networks else ["ethereum", "bsc", "polygon", "arbitrum", "optimism"]
            for network in networks[:50]:  # Limit to first 50 networks
                self.network_combo.addItem(network.title(), network)
    
    def _subscribe_events(self):
        """Subscribe to event bus events."""
        if not self.event_bus:
            return
        
        try:
            # Use sync subscription to avoid asyncio issues in Qt context
            if hasattr(self.event_bus, 'subscribe_sync'):
                self.event_bus.subscribe_sync('blockchain.block.new', self._handle_new_block)
                self.event_bus.subscribe_sync('blockchain.gas.update', self._handle_gas_update)
                self.event_bus.subscribe_sync('blockchain.status', self._handle_status_update)
                # SOTA 2026: Subscribe to transaction events for table population
                self.event_bus.subscribe_sync('blockchain.transaction.new', self._handle_new_transaction)
                self.event_bus.subscribe_sync('blockchain.transactions', self._handle_transactions_batch)
                # Wallet integration — show send results from any source
                self.event_bus.subscribe_sync('wallet.send.result', self._handle_wallet_send_result)
                self.event_bus.subscribe_sync('wallet.send.error', self._handle_wallet_send_error)
                self.event_bus.subscribe_sync('wallet.transaction.confirmed', self._handle_wallet_tx_confirmed)
            elif hasattr(self.event_bus, 'subscribe'):
                # Safe event bus subscription without asyncio.create_task
                self.event_bus.subscribe('blockchain.block.new', self._handle_new_block)
                self.event_bus.subscribe('blockchain.gas.update', self._handle_gas_update)
                self.event_bus.subscribe('blockchain.status', self._handle_status_update)
                # SOTA 2026: Subscribe to transaction events for table population
                self.event_bus.subscribe('blockchain.transaction.new', self._handle_new_transaction)
                self.event_bus.subscribe('wallet.send.result', self._handle_wallet_send_result)
                self.event_bus.subscribe('wallet.send.error', self._handle_wallet_send_error)
                self.event_bus.subscribe('blockchain.transactions', self._handle_transactions_batch)
        except Exception as e:
            self.logger.warning(f"Failed to subscribe to events: {e}")
    
    def _deferred_blockchain_init(self):
        """Deferred initialization to avoid blocking UI."""
        try:
            # Start refresh timer
            self._refresh_timer = QTimer(self)
            self._refresh_timer.timeout.connect(self._refresh_network_stats_sync)
            start_timer_safe(self._refresh_timer, 30000)  # Every 30 seconds
            
            # Initial refresh
            self._refresh_network_stats_sync()
            
            self.status_bar.setText("Blockchain tab initialized")
            self.logger.info("Blockchain tab initialized successfully")
        except Exception as e:
            self.logger.error(f"Blockchain initialization error: {e}")
            self.status_bar.setText(f"Initialization error: {e}")
    
    def _on_network_changed(self, network_name: str):
        """Handle network selection change."""
        network_key = self.network_combo.currentData() or network_name.lower()
        self.current_network = network_key
        self.network_changed.emit(network_key)
        self._refresh_network_stats_sync()
    
    def _refresh_network_stats_sync(self):
        """Refresh network statistics synchronously (Qt-compatible)."""
        try:
            # SOTA 2026: Use thread-safe approach instead of asyncio.run()
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None
            
            if loop and loop.is_running():
                # Schedule async refresh without blocking
                asyncio.ensure_future(self._refresh_network_stats())
            else:
                # Run in executor to avoid blocking GUI
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    try:
                        future = executor.submit(self._refresh_sync_worker)
                        result = future.result(timeout=10)
                        if result:
                            self._update_ui_from_result(result)
                    except concurrent.futures.TimeoutError:
                        self.logger.warning("Network refresh timed out")
                    except Exception as e:
                        self.logger.warning(f"Network refresh error: {e}")
        except Exception as e:
            self.logger.error(f"Refresh error: {e}")
    
    def _refresh_sync_worker(self):
        """Worker for synchronous refresh."""
        result = {
            'status': 'connected',
            'block': 0,
            'gas': 0,
            'peers': 0
        }
        
        try:
            if self.blockchain_connector and hasattr(self.blockchain_connector, 'get_block_number'):
                result['block'] = self.blockchain_connector.get_block_number() or 0
            if self.blockchain_connector and hasattr(self.blockchain_connector, 'get_gas_price'):
                result['gas'] = self.blockchain_connector.get_gas_price() or 0
        except Exception as e:
            result['status'] = f'error: {e}'
        
        return result
    
    def _update_ui_from_result(self, result: dict):
        """Update UI elements from refresh result."""
        try:
            if self.status_label:
                status = result.get('status', 'unknown')
                if 'connected' in str(status).lower():
                    self.status_label.setText("Connected")
                    self.status_label.setStyleSheet("color: #00ff88;")
                else:
                    self.status_label.setText("Disconnected")
                    self.status_label.setStyleSheet("color: #ff6b6b;")
            
            if self.block_label:
                self.block_label.setText(str(result.get('block', '--')))
            
            if self.gas_label:
                gas = result.get('gas', 0)
                self.gas_label.setText(f"{gas} Gwei")
            
            if self.peers_label:
                self.peers_label.setText(str(result.get('peers', '--')))
        except Exception as e:
            self.logger.error(f"UI update error: {e}")
    
    async def _refresh_network_stats(self):
        """Async refresh network statistics."""
        try:
            if self.blockchain_connector:
                # Get stats from connector
                if hasattr(self.blockchain_connector, 'get_block_number'):
                    block = await self.blockchain_connector.get_block_number() if asyncio.iscoroutinefunction(self.blockchain_connector.get_block_number) else self.blockchain_connector.get_block_number()
                    self.block_heights[self.current_network] = block
                
                if hasattr(self.blockchain_connector, 'get_gas_price'):
                    gas = await self.blockchain_connector.get_gas_price() if asyncio.iscoroutinefunction(self.blockchain_connector.get_gas_price) else self.blockchain_connector.get_gas_price()
                    self.gas_prices[self.current_network] = gas
            
            # Update UI on main thread
            QTimer.singleShot(0, self._update_network_display)
        except Exception as e:
            self.logger.error(f"Error refreshing network stats: {e}")
    
    def _update_network_display(self):
        """Update network display on main thread."""
        try:
            block = self.block_heights.get(self.current_network, 0)
            gas = self.gas_prices.get(self.current_network, 0)
            
            if self.block_label:
                self.block_label.setText(str(block) if block else "--")
            
            if self.gas_label:
                self.gas_label.setText(f"{gas} Gwei" if gas else "-- Gwei")
            
            if self.status_label:
                if block or gas:
                    self.status_label.setText("Connected")
                    self.status_label.setStyleSheet("color: #00ff88;")
                else:
                    self.status_label.setText("Connecting...")
                    self.status_label.setStyleSheet("color: #ffe66d;")
            
            # SOTA 2026: Update networks table with current data
            self._update_networks_table()
        except Exception as e:
            self.logger.error(f"Display update error: {e}")
    
    def _update_networks_table(self):
        """Populate networks_table with current network data (SOTA 2026 FIX)."""
        try:
            if not self.networks_table:
                return
            
            # Collect all networks that have data
            networks_with_data = set(self.block_heights.keys()) | set(self.gas_prices.keys()) | set(self.connected_networks.keys())
            
            # Always include current network
            networks_with_data.add(self.current_network)
            
            # Set row count
            self.networks_table.setRowCount(len(networks_with_data))
            
            # Populate rows
            for row, network in enumerate(sorted(networks_with_data)):
                # Network name
                name_item = QTableWidgetItem(network.title())
                name_item.setForeground(QColor("#00ff88"))
                self.networks_table.setItem(row, 0, name_item)
                
                # Status
                status = "Connected" if network in self.connected_networks or self.block_heights.get(network) else "Disconnected"
                status_item = QTableWidgetItem(status)
                status_item.setForeground(QColor("#00ff88" if status == "Connected" else "#ff6b6b"))
                self.networks_table.setItem(row, 1, status_item)
                
                # Block height
                block = self.block_heights.get(network, 0)
                block_item = QTableWidgetItem(str(block) if block else "--")
                block_item.setForeground(QColor("#4ecdc4"))
                self.networks_table.setItem(row, 2, block_item)
                
                # Gas price
                gas = self.gas_prices.get(network, 0)
                gas_item = QTableWidgetItem(f"{gas} Gwei" if gas else "--")
                gas_item.setForeground(QColor("#ffe66d"))
                self.networks_table.setItem(row, 3, gas_item)
            
            self.logger.debug(f"Networks table updated with {len(networks_with_data)} networks")
        except Exception as e:
            self.logger.error(f"Networks table update error: {e}")
    
    def _update_transaction_table(self, transactions: List[Dict[str, Any]]):
        """Populate transaction_table with transaction data (SOTA 2026 FIX).
        
        Args:
            transactions: List of transaction dicts with keys: hash, from, to, value, gas, status
        """
        try:
            if not self.transaction_table:
                return
            
            if not transactions or not isinstance(transactions, list):
                return
            
            # Set row count
            self.transaction_table.setRowCount(len(transactions))
            
            # Populate rows
            for row, tx in enumerate(transactions):
                if not isinstance(tx, dict):
                    continue
                
                # Hash (truncated)
                tx_hash = tx.get("hash", "")
                hash_display = f"{tx_hash[:10]}...{tx_hash[-6:]}" if len(tx_hash) > 20 else tx_hash
                hash_item = QTableWidgetItem(hash_display)
                hash_item.setForeground(QColor("#00ff88"))
                hash_item.setToolTip(tx_hash)  # Full hash on hover
                self.transaction_table.setItem(row, 0, hash_item)
                
                # From address (truncated)
                from_addr = tx.get("from", "")
                from_display = f"{from_addr[:8]}...{from_addr[-6:]}" if len(from_addr) > 18 else from_addr
                from_item = QTableWidgetItem(from_display)
                from_item.setForeground(QColor("#4ecdc4"))
                from_item.setToolTip(from_addr)
                self.transaction_table.setItem(row, 1, from_item)
                
                # To address (truncated)
                to_addr = tx.get("to", "")
                to_display = f"{to_addr[:8]}...{to_addr[-6:]}" if len(to_addr) > 18 else to_addr
                to_item = QTableWidgetItem(to_display)
                to_item.setForeground(QColor("#a8e6cf"))
                to_item.setToolTip(to_addr)
                self.transaction_table.setItem(row, 2, to_item)
                
                # Value
                value = tx.get("value", 0)
                value_item = QTableWidgetItem(f"{value:.6f}" if isinstance(value, float) else str(value))
                value_item.setForeground(QColor("#ffe66d"))
                self.transaction_table.setItem(row, 3, value_item)
                
                # Gas
                gas = tx.get("gas", 0)
                gas_item = QTableWidgetItem(str(gas))
                gas_item.setForeground(QColor("#ff9f43"))
                self.transaction_table.setItem(row, 4, gas_item)
                
                # Status
                status = tx.get("status", "pending")
                status_item = QTableWidgetItem(status.title())
                if status.lower() == "success" or status.lower() == "confirmed":
                    status_item.setForeground(QColor("#00ff88"))
                elif status.lower() == "pending":
                    status_item.setForeground(QColor("#ffe66d"))
                else:
                    status_item.setForeground(QColor("#ff6b6b"))
                self.transaction_table.setItem(row, 5, status_item)
            
            self.logger.debug(f"Transaction table updated with {len(transactions)} transactions")
        except Exception as e:
            self.logger.error(f"Transaction table update error: {e}")
    
    def add_transaction(self, tx: Dict[str, Any]):
        """Add a single transaction to the table (for real-time updates).
        
        Args:
            tx: Transaction dict with keys: hash, from, to, value, gas, status
        """
        try:
            if not self.transaction_table or not isinstance(tx, dict):
                return
            
            # Insert at top of table
            self.transaction_table.insertRow(0)
            
            # Hash
            tx_hash = tx.get("hash", "")
            hash_display = f"{tx_hash[:10]}...{tx_hash[-6:]}" if len(tx_hash) > 20 else tx_hash
            hash_item = QTableWidgetItem(hash_display)
            hash_item.setForeground(QColor("#00ff88"))
            hash_item.setToolTip(tx_hash)
            self.transaction_table.setItem(0, 0, hash_item)
            
            # From
            from_addr = tx.get("from", "")
            from_display = f"{from_addr[:8]}...{from_addr[-6:]}" if len(from_addr) > 18 else from_addr
            from_item = QTableWidgetItem(from_display)
            from_item.setForeground(QColor("#4ecdc4"))
            from_item.setToolTip(from_addr)
            self.transaction_table.setItem(0, 1, from_item)
            
            # To
            to_addr = tx.get("to", "")
            to_display = f"{to_addr[:8]}...{to_addr[-6:]}" if len(to_addr) > 18 else to_addr
            to_item = QTableWidgetItem(to_display)
            to_item.setForeground(QColor("#a8e6cf"))
            to_item.setToolTip(to_addr)
            self.transaction_table.setItem(0, 2, to_item)
            
            # Value
            value = tx.get("value", 0)
            value_item = QTableWidgetItem(f"{value:.6f}" if isinstance(value, float) else str(value))
            value_item.setForeground(QColor("#ffe66d"))
            self.transaction_table.setItem(0, 3, value_item)
            
            # Gas
            gas = tx.get("gas", 0)
            gas_item = QTableWidgetItem(str(gas))
            gas_item.setForeground(QColor("#ff9f43"))
            self.transaction_table.setItem(0, 4, gas_item)
            
            # Status
            status = tx.get("status", "pending")
            status_item = QTableWidgetItem(status.title())
            if status.lower() == "success" or status.lower() == "confirmed":
                status_item.setForeground(QColor("#00ff88"))
            elif status.lower() == "pending":
                status_item.setForeground(QColor("#ffe66d"))
            else:
                status_item.setForeground(QColor("#ff6b6b"))
            self.transaction_table.setItem(0, 5, status_item)
            
            # Limit table to 100 rows
            while self.transaction_table.rowCount() > 100:
                self.transaction_table.removeRow(self.transaction_table.rowCount() - 1)
            
            self.logger.debug(f"Added transaction {tx_hash[:10]}... to table")
        except Exception as e:
            self.logger.error(f"Error adding transaction: {e}")
    
    def _handle_new_block(self, data):
        """Handle new block event."""
        try:
            network = data.get('network', self.current_network)
            block = data.get('block_number', 0)
            self.block_heights[network] = block
            
            # SOTA 2026: Mark network as connected when we receive block data
            self.connected_networks[network] = True
            
            # Always update display and table (not just for current network)
            QTimer.singleShot(0, self._update_network_display)
        except Exception as e:
            self.logger.error(f"Block event error: {e}")
    
    def _handle_gas_update(self, data):
        """Handle gas price update event."""
        try:
            network = data.get('network', self.current_network)
            gas = data.get('gas_price', 0)
            self.gas_prices[network] = gas
            
            # SOTA 2026: Mark network as connected when we receive gas data
            self.connected_networks[network] = True
            
            # Always update display and table (not just for current network)
            QTimer.singleShot(0, self._update_network_display)
        except Exception as e:
            self.logger.error(f"Gas event error: {e}")
    
    def _handle_status_update(self, data):
        """Handle blockchain status update (THREAD-SAFE).
        
        SOTA 2026: Dispatches to main thread to prevent Qt threading violations.
        """
        # Use QTimer.singleShot for thread-safe UI update (consistent with other handlers)
        def update_ui():
            try:
                status = data.get('status', 'unknown')
                if self.status_label:
                    self.status_label.setText(status.title())
            except Exception as e:
                self.logger.error(f"Status event error: {e}")
        
        QTimer.singleShot(0, update_ui)
    
    def _handle_new_transaction(self, data):
        """Handle new transaction event (SOTA 2026 - enables real-time transaction display).
        
        Args:
            data: Transaction dict with keys: hash, from, to, value, gas, status
        """
        try:
            if not isinstance(data, dict):
                return
            
            # Thread-safe UI update
            QTimer.singleShot(0, lambda: self.add_transaction(data))
            
            # Emit signal for external listeners
            self.transaction_sent.emit(data)
        except Exception as e:
            self.logger.error(f"Transaction event error: {e}")
    
    def _handle_transactions_batch(self, data):
        """Handle batch transactions event (SOTA 2026 - enables bulk transaction loading).
        
        Args:
            data: Dict with 'transactions' key containing list of transaction dicts
        """
        try:
            transactions = data.get('transactions', []) if isinstance(data, dict) else data
            if not isinstance(transactions, list):
                return
            
            # Thread-safe UI update
            QTimer.singleShot(0, lambda: self._update_transaction_table(transactions))
        except Exception as e:
            self.logger.error(f"Transactions batch event error: {e}")
    
    def _handle_wallet_send_result(self, data):
        """Show wallet.send.result events in the blockchain tab result area."""
        try:
            if not isinstance(data, dict):
                return
            tx_hash = data.get("tx_hash", "")
            network = data.get("network", "")
            amount = data.get("amount", "")
            msg = f"TX Confirmed — {amount} on {network}\nHash: {tx_hash}"
            if hasattr(self, '_wops_result'):
                QTimer.singleShot(0, lambda: self._wops_result.append(msg))
        except Exception as e:
            self.logger.debug("wallet.send.result handler: %s", e)

    def _handle_wallet_send_error(self, data):
        """Show wallet.send.error events."""
        try:
            if not isinstance(data, dict):
                return
            err = data.get("error", "Unknown error")
            if hasattr(self, '_wops_result'):
                QTimer.singleShot(0, lambda: self._wops_result.append(f"TX Error: {err}"))
        except Exception as e:
            self.logger.debug("wallet.send.error handler: %s", e)

    def _handle_wallet_tx_confirmed(self, data):
        """Show confirmed wallet transactions in the blockchain tab."""
        try:
            if not isinstance(data, dict):
                return
            tx_hash = data.get("tx_hash", "")
            network = data.get("network", "")
            msg = f"Confirmed on {network}: {tx_hash}"
            if hasattr(self, '_wops_result'):
                QTimer.singleShot(0, lambda: self._wops_result.append(msg))
        except Exception as e:
            self.logger.debug("wallet.transaction.confirmed handler: %s", e)

    def _load_contract(self):
        """Load smart contract."""
        try:
            address = self.contract_address_input.text().strip()
            abi_text = self.contract_abi_input.toPlainText().strip()
            
            if not address:
                QMessageBox.warning(self, "Error", "Please enter a contract address")
                return
            
            if abi_text:
                try:
                    abi = json.loads(abi_text)
                except json.JSONDecodeError:
                    QMessageBox.warning(self, "Error", "Invalid ABI JSON format")
                    return
            else:
                abi = None
            
            self.contract_results.setText(f"Contract loaded: {address}\nABI: {'Provided' if abi else 'Not provided'}")
            self.logger.info(f"Contract loaded: {address}")
        except Exception as e:
            self.logger.error(f"Contract load error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load contract: {e}")
    
    def _call_contract_function_safe(self):
        """Safely call contract function without asyncio issues."""
        try:
            address = self.contract_address_input.text().strip()
            if not address:
                QMessageBox.warning(self, "Error", "Please enter a contract address first")
                return
            
            # Use thread-safe execution
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                try:
                    future = executor.submit(self._call_contract_sync, address)
                    result = future.result(timeout=30)
                    self.contract_results.setText(f"Contract call result:\n{result}")
                except concurrent.futures.TimeoutError:
                    self.contract_results.setText("Contract call timed out")
                except Exception as e:
                    self.contract_results.setText(f"Error: {e}")
        except Exception as e:
            self.logger.error(f"Contract call error: {e}")
            self.contract_results.setText(f"Error calling contract: {e}")
    
    def _call_contract_sync(self, address: str):
        """Synchronous contract call worker."""
        try:
            if self.blockchain_connector and hasattr(self.blockchain_connector, 'call_contract'):
                return self.blockchain_connector.call_contract(address)
            return "Blockchain connector not available"
        except Exception as e:
            return f"Error: {e}"
    
    async def _call_contract_function(self):
        """Async call contract function (for use within async context)."""
        try:
            address = self.contract_address_input.text().strip()
            if not address:
                return
            
            if self.blockchain_connector and hasattr(self.blockchain_connector, 'call_contract'):
                result = await self.blockchain_connector.call_contract(address)
                self.contract_results.setText(f"Result: {result}")
                self.contract_called.emit({'address': address, 'result': result})
        except Exception as e:
            self.logger.error(f"Contract call error: {e}")
            self.contract_results.setText(f"Error: {e}")
    
    def _search_explorer(self):
        """Search block explorer using public Etherscan / Blockchair API."""
        try:
            query = self.explorer_search.text().strip()
            if not query:
                return

            self.explorer_results.setText(f"Searching for: {query}\n\nFetching from blockchain explorer...")

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._explorer_search_worker, query)
                try:
                    result_text = future.result(timeout=15)
                    self.explorer_results.setText(result_text)
                except concurrent.futures.TimeoutError:
                    self.explorer_results.setText(f"Search timed out for: {query}")
                except Exception as e:
                    self.explorer_results.setText(f"Search error: {e}")
        except Exception as e:
            self.logger.error(f"Explorer search error: {e}")

    def _explorer_search_worker(self, query: str) -> str:
        """Synchronous worker that queries blockchain explorers."""
        import urllib.request, urllib.error, json as _json

        query = query.strip()
        lines = [f"=== Blockchain Explorer Search ===\nQuery: {query}\n"]

        # Determine query type
        is_tx = query.startswith('0x') and len(query) == 66
        is_addr = query.startswith('0x') and len(query) == 42
        is_block = query.isdigit()

        network = self.current_network or "ethereum"

        # Map network to Blockchair chain slug
        chain_map = {
            'ethereum': 'ethereum', 'bsc': 'binance-smart-chain', 'bitcoin': 'bitcoin',
            'polygon': 'polygon', 'arbitrum': 'arbitrum', 'optimism': 'optimism',
            'avalanche': 'avalanche', 'fantom': 'fantom', 'base': 'base',
        }
        chain_slug = chain_map.get(network.lower(), 'ethereum')

        try:
            if is_tx:
                url = f"https://api.blockchair.com/{chain_slug}/dashboards/transaction/{query}"
                req = urllib.request.Request(url, headers={"User-Agent": "KingdomAI/1.0"})
                resp = urllib.request.urlopen(req, timeout=10)
                data = _json.loads(resp.read().decode())
                tx = data.get('data', {}).get(query.lower(), {}).get('transaction', {})
                if tx:
                    lines.append(f"Type: Transaction")
                    lines.append(f"Hash: {tx.get('hash', query)}")
                    lines.append(f"Block: {tx.get('block_id', 'pending')}")
                    lines.append(f"Time: {tx.get('time', 'N/A')}")
                    lines.append(f"From: {tx.get('sender', 'N/A') or tx.get('input_address', 'N/A')}")
                    lines.append(f"To: {tx.get('recipient', 'N/A') or tx.get('output_address', 'N/A')}")
                    val = tx.get('value', 0)
                    lines.append(f"Value: {int(val) / 1e18:.6f} ETH" if chain_slug == 'ethereum' else f"Value: {val}")
                    lines.append(f"Fee: {tx.get('fee', 'N/A')}")
                else:
                    lines.append("Transaction not found or pending.")

            elif is_addr:
                url = f"https://api.blockchair.com/{chain_slug}/dashboards/address/{query}"
                req = urllib.request.Request(url, headers={"User-Agent": "KingdomAI/1.0"})
                resp = urllib.request.urlopen(req, timeout=10)
                data = _json.loads(resp.read().decode())
                addr = data.get('data', {}).get(query.lower(), {}).get('address', {})
                if addr:
                    lines.append(f"Type: Address")
                    lines.append(f"Address: {query}")
                    bal = addr.get('balance', 0)
                    lines.append(f"Balance: {int(bal) / 1e18:.6f} ETH" if chain_slug == 'ethereum' else f"Balance: {bal}")
                    lines.append(f"Tx Count: {addr.get('transaction_count', 'N/A')}")
                    lines.append(f"First Seen: {addr.get('first_seen_receiving', 'N/A')}")
                else:
                    lines.append("Address not found.")

            elif is_block:
                url = f"https://api.blockchair.com/{chain_slug}/dashboards/block/{query}"
                req = urllib.request.Request(url, headers={"User-Agent": "KingdomAI/1.0"})
                resp = urllib.request.urlopen(req, timeout=10)
                data = _json.loads(resp.read().decode())
                blk = data.get('data', {}).get(query, {}).get('block', {})
                if blk:
                    lines.append(f"Type: Block")
                    lines.append(f"Block: {blk.get('id', query)}")
                    lines.append(f"Hash: {blk.get('hash', 'N/A')}")
                    lines.append(f"Time: {blk.get('time', 'N/A')}")
                    lines.append(f"Transactions: {blk.get('transaction_count', 'N/A')}")
                    lines.append(f"Size: {blk.get('size', 'N/A')} bytes")
                else:
                    lines.append("Block not found.")
            else:
                lines.append(f"Unrecognized query format.\n"
                             f"Use a 0x-prefixed tx hash (66 chars), address (42 chars), or block number.")

        except urllib.error.HTTPError as he:
            lines.append(f"API error: HTTP {he.code}")
        except urllib.error.URLError as ue:
            lines.append(f"Network error: {ue.reason}")
        except Exception as e:
            lines.append(f"Error: {e}")

        lines.append(f"\nNetwork: {network.title()} ({chain_slug})")
        return "\n".join(lines)
    
    def _optimize_gas(self):
        """Analyze and optimize gas settings for transactions."""
        try:
            self.contract_results.append("\n--- Gas Optimization Analysis ---\n")
            
            # Get current gas price from blockchain connector
            if self.blockchain_connector:
                try:
                    # Get current gas price
                    gas_price = self.blockchain_connector.get_gas_price() if hasattr(self.blockchain_connector, 'get_gas_price') else None
                    
                    if gas_price:
                        gas_gwei = gas_price / 1e9 if isinstance(gas_price, (int, float)) else 0
                        self.contract_results.append(f"Current Gas Price: {gas_gwei:.2f} Gwei\n")
                        
                        # Recommend optimizations based on gas price
                        if gas_gwei < 20:
                            self.contract_results.append("✅ Gas price is LOW - good time to send transactions\n")
                            self.contract_results.append("Recommendation: Execute pending transactions now\n")
                        elif gas_gwei < 50:
                            self.contract_results.append("⚠️ Gas price is MODERATE\n")
                            self.contract_results.append("Recommendation: Consider batching transactions\n")
                        else:
                            self.contract_results.append("❌ Gas price is HIGH - wait if possible\n")
                            self.contract_results.append("Recommendation: Use gas tokens or wait for lower prices\n")
                    else:
                        self.contract_results.append("Unable to fetch current gas price\n")
                except Exception as e:
                    self.contract_results.append(f"Error getting gas price: {e}\n")
            else:
                self.contract_results.append("No blockchain connector available\n")
            
            # General optimization tips
            self.contract_results.append("\n--- General Gas Optimization Tips ---\n")
            self.contract_results.append("1. Batch multiple operations into single transactions\n")
            self.contract_results.append("2. Use calldata instead of memory for function arguments\n")
            self.contract_results.append("3. Pack storage variables efficiently\n")
            self.contract_results.append("4. Use events instead of storage for logging\n")
            self.contract_results.append("5. Consider using EIP-1559 for more predictable fees\n")
            
            # Publish event for gas optimization
            if self.event_bus:
                self.event_bus.publish("blockchain.gas.optimized", {
                    "timestamp": datetime.now().isoformat(),
                    "action": "gas_analysis"
                })
            
            self.logger.info("Gas optimization analysis completed")
        except Exception as e:
            self.logger.error(f"Gas optimization error: {e}")
            self.contract_results.append(f"\nError during gas optimization: {e}\n")
    
    def cleanup(self):
        """Cleanup resources."""
        try:
            if self._refresh_timer:
                stop_timer_safe(self._refresh_timer)
            if self._gas_timer:
                stop_timer_safe(self._gas_timer)
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def closeEvent(self, event):
        """Handle close event."""
        self.cleanup()
        super().closeEvent(event)
