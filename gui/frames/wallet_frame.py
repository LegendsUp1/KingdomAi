#!/usr/bin/env python3
"""
Wallet Frame for Kingdom AI GUI.
Provides a state-of-the-art interface for multi-chain cryptocurrency and stock wallet management.

Features:
- Multi-blockchain support (ETH, BTC, XRP, SOL, and many more)
- Real-time portfolio tracking and visualization
- DeFi integration (staking, swapping, yield farming)
- NFT gallery and management
- Cross-chain transactions and asset bridging
- Hardware wallet integration
- Advanced security features
- AI-assisted portfolio optimization
"""

import logging
import asyncio
from datetime import datetime, timedelta
import json
import os
import time
import webbrowser
import uuid
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
import traceback
from functools import partial

# PyQt6 imports
from PyQt6.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal, pyqtSlot, QObject, QUrl
from PyQt6.QtGui import QPixmap, QImage, QFont, QIcon, QPainter, QColor, QPen, QAction
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, 
                             QLineEdit, QComboBox, QTabWidget, QFrame, QTextEdit, 
                             QScrollArea, QTreeWidget, QTreeWidgetItem, QProgressBar, 
                             QMessageBox, QFileDialog, QInputDialog, QSpinBox, 
                             QDoubleSpinBox, QCheckBox, QRadioButton, QSlider, QGroupBox,
                             QSplitter, QSizePolicy, QMenu)

# Data visualization libraries
import matplotlib
matplotlib.use('QtAgg')  # Use QtAgg backend for PyQt6
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np

# QR code generation for wallet addresses
try:
    import qrcode
    from PIL import Image
    qr_code_available = True
except ImportError:
    qr_code_available = False

from .base_frame_pyqt import BaseFrame

class WalletFrame(BaseFrame):
    """State-of-the-art multi-chain wallet frame for the Kingdom AI GUI.
    
    This advanced wallet interface provides comprehensive management for cryptocurrency
    and stock wallets across multiple blockchains and platforms. It features real-time
    portfolio tracking, DeFi integration, NFT management, cross-chain transactions,
    and advanced security features.
    """
    
    # Define supported blockchains with their properties
    SUPPORTED_BLOCKCHAINS = {
        "ETH": {
            "name": "Ethereum",
            "icon": "ethereum.png",  # Icons would be in an assets folder
            "color": "#627EEA",
            "networks": ["mainnet", "sepolia", "goerli"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": True
        },
        "BTC": {
            "name": "Bitcoin",
            "icon": "bitcoin.png",
            "color": "#F7931A",
            "networks": ["mainnet", "testnet"],
            "defi_enabled": False,
            "nft_enabled": False,
            "staking_enabled": False
        },
        "XRP": {
            "name": "XRP Ledger",
            "icon": "xrp.png",
            "color": "#23292F",
            "networks": ["mainnet", "testnet"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": False
        },
        "SOL": {
            "name": "Solana",
            "icon": "solana.png",
            "color": "#9945FF",
            "networks": ["mainnet", "devnet"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": True
        },
        "DOT": {
            "name": "Polkadot",
            "icon": "polkadot.png",
            "color": "#E6007A",
            "networks": ["mainnet", "testnet"],
            "defi_enabled": True,
            "nft_enabled": False,
            "staking_enabled": True
        },
        "AVAX": {
            "name": "Avalanche",
            "icon": "avalanche.png",
            "color": "#E84142",
            "networks": ["mainnet", "fuji"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": True
        },
        "NEAR": {
            "name": "NEAR Protocol",
            "icon": "near.png",
            "color": "#000000",
            "networks": ["mainnet", "testnet"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": True
        },
        "ADA": {
            "name": "Cardano",
            "icon": "cardano.png",
            "color": "#0033AD",
            "networks": ["mainnet", "testnet"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": True
        },
        "ALGO": {
            "name": "Algorand",
            "icon": "algorand.png",
            "color": "#000000",
            "networks": ["mainnet", "testnet"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": True
        },
        "ATOM": {
            "name": "Cosmos",
            "icon": "cosmos.png",
            "color": "#2E3148",
            "networks": ["mainnet", "testnet"],
            "defi_enabled": True,
            "nft_enabled": False,
            "staking_enabled": True
        },
        "MATIC": {
            "name": "Polygon",
            "icon": "polygon.png",
            "color": "#8247E5",
            "networks": ["mainnet", "mumbai"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": True
        },
        "FTM": {
            "name": "Fantom",
            "icon": "fantom.png",
            "color": "#1969FF",
            "networks": ["mainnet", "testnet"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": True
        },
        "HBAR": {
            "name": "Hedera",
            "icon": "hedera.png",
            "color": "#222222",
            "networks": ["mainnet", "testnet"],
            "defi_enabled": True,
            "nft_enabled": True,
            "staking_enabled": True
        },
        "STOCK": {
            "name": "Stocks",
            "icon": "stocks.png",
            "color": "#006644",
            "networks": ["nyse", "nasdaq", "tsx", "lse"],
            "defi_enabled": False,
            "nft_enabled": False,
            "staking_enabled": False
        }
    }
    
    # Supported cross-chain bridges
    SUPPORTED_BRIDGES = {
        "LayerZero": ["ETH", "AVAX", "MATIC", "FTM", "BNB"],
        "Wormhole": ["ETH", "SOL", "AVAX", "MATIC", "BNB"],
        "Axelar": ["ETH", "AVAX", "MATIC", "FTM", "BNB", "ATOM"],
        "Multichain": ["ETH", "AVAX", "MATIC", "FTM", "BNB", "ATOM", "ALGO"],
        "Hop": ["ETH", "MATIC", "AVAX"],
        "Synapse": ["ETH", "AVAX", "MATIC", "FTM", "BNB"],
        "Stargate": ["ETH", "AVAX", "MATIC", "FTM", "BNB"]
    }
    
    # DeFi protocols by blockchain
    DEFI_PROTOCOLS = {
        "ETH": ["Uniswap", "Aave", "Compound", "Curve", "Balancer", "Lido"],
        "SOL": ["Raydium", "Marinade", "Saber", "Serum", "Orca"],
        "AVAX": ["Trader Joe", "Pangolin", "Benqi", "AAVE"],
        "MATIC": ["QuickSwap", "AAVE", "Curve", "Balancer"],
        "FTM": ["SpookySwap", "Curve", "Yearn"],
        "ATOM": ["Osmosis", "Crescent", "Stride"],
        "BNB": ["PancakeSwap", "Venus", "BiSwap"]
    }
    
    # Transaction types
    TRANSACTION_TYPES = [
        "send", "receive", "swap", "stake", "unstake", "yield", "nft_buy", 
        "nft_sell", "bridge", "loan", "repay", "stock_buy", "stock_sell", 
        "dividend", "airdrop", "gas_fee", "mining_reward"
    ]
    
    def __init__(self, parent, event_bus=None, api_key_connector=None, name="WalletFrame", **kwargs):
        """Initialize the advanced multi-chain wallet frame.
        
        Args:
            parent: The parent widget
            event_bus: The application event bus
            api_key_connector: Connector for accessing API keys
            name: Name of the frame
            **kwargs: Additional keyword arguments
        """
        super().__init__(parent, event_bus, name)
        
        # Store API key connector
        self.api_key_connector = api_key_connector
        
        # Setup logger
        self.logger = logging.getLogger(__name__)
        
        # Register that we've been created
        self.logger.info(f"Registered common events for {name}")
        self.logger.info(f"Created {name} frame")
        
        # Wallet state - Enhanced data structures for multi-chain support
        self.wallets = {}  # Format: {chain: {address: {details}}}
        self.transactions = []  # List of all transactions across chains
        self.selected_wallet = ""
        self.selected_chain = ""
        self.selected_network = ""
        self.total_balance_usd = 0.0
        
        # Advanced tracking for multi-chain assets
        self.portfolio_value_history = {}
        self.asset_allocation = {}
        self.defi_positions = {}
        self.staking_rewards = {}
        self.nft_collections = {}
        self.price_alerts = {}
        self.gas_prices = {}
        
        # Filter and view settings
        self.transaction_filter = "all"
        self.portfolio_timeframe = "1M"  # Default 1 month view
        self.current_tab = "overview"  # Default tab
        self.chart_type = "line"  # Default chart type
        self.show_hidden_assets = False
        
        # UI Theme and display settings
        self.dark_mode = True
        self.theme_colors = self._get_theme_colors()
        
        # Bridge and cross-chain transaction tracking
        self.bridge_transactions = {}
        self.pending_bridges = {}
        
        # Hardware wallet integration status
        self.hardware_wallets = {}
        self.hardware_wallet_connected = False
        
        # Blockchain provider keys and connections
        self.blockchain_providers = {}
        self.web3_connections = {}
        self.node_status = {}
        
        # Real-time data refresh rates
        self.refresh_rates = {
            "portfolio": 60,  # seconds
            "prices": 30,
            "transactions": 120,
            "gas": 60,
            "staking": 300,
            "defi": 180
        }
        
        # Create an icon cache for blockchain icons
        self.icon_cache = {}
        
        # Initialize portfolio analytics
        self.portfolio_analytics = {
            "daily_change": 0.0,
            "weekly_change": 0.0,
            "monthly_change": 0.0,
            "yearly_change": 0.0,
            "best_performer": None,
            "worst_performer": None,
            "risk_score": 0.0,
            "diversification_score": 0.0
        }
        
        # Perform synchronous initialization
        self.sync_initialize()
    
    def sync_initialize(self):
        """Synchronous initialization of the wallet frame.
        
        Returns:
            bool: True if initialization was successful
        """
        self.logger.info("Synchronously initializing Wallet frame")
        
        try:
            # Initialize data structures
            self.wallets = {}
            self.balances = {}
            self.transactions = []  # Changed to list since we use append
            self.mining_rewards = {}
            self.trading_profits = {}
            self.pending_transactions = []
            self.blockchain_statuses = {}
            
            # Create content frame (main layout container)
            self.content_frame = QWidget(self)
            self.main_layout = QVBoxLayout(self.content_frame)
            self.main_layout.setContentsMargins(15, 10, 15, 10)
            self.setLayout(QVBoxLayout())
            self.layout().addWidget(self.content_frame)
            
            # Create wallet-specific layout
            self._setup_ui()
            
            self.logger.info("Wallet frame basic synchronous initialization completed")
            self.update_status("Wallet interface initializing...", "#FFA500")
            
            return True
        except Exception as e:
            self.logger.error(f"Error in sync initialization of wallet frame: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.update_status(f"Error: {str(e)[:30]}...", "#F44336")
            return False
    
    def _setup_ui(self):
        """Setup the wallet UI with PyQt6 widgets."""
        try:
            self.logger.info("Setting up wallet UI with PyQt6")
            
            # Create main layout structure
            self.wallet_tabs = QTabWidget(self.content_frame)
            self.main_layout.addWidget(self.wallet_tabs)
            
            # Create the tabs for different sections
            self.overview_tab = QWidget()
            self.assets_tab = QWidget()
            self.transactions_tab = QWidget()
            self.defi_tab = QWidget()
            self.nft_tab = QWidget()
            self.bridge_tab = QWidget()
            self.settings_tab = QWidget()
            
            # Add tabs to the tabwidget
            self.wallet_tabs.addTab(self.overview_tab, "Overview")
            self.wallet_tabs.addTab(self.assets_tab, "Assets")
            self.wallet_tabs.addTab(self.transactions_tab, "Transactions")
            self.wallet_tabs.addTab(self.defi_tab, "DeFi")
            self.wallet_tabs.addTab(self.nft_tab, "NFTs")
            self.wallet_tabs.addTab(self.bridge_tab, "Bridge")
            self.wallet_tabs.addTab(self.settings_tab, "Settings")
            
            # Setup each tab's content
            self._setup_overview_tab()
            self._setup_assets_tab()
            self._setup_transactions_tab()
            self._setup_defi_tab()
            self._setup_nft_tab()
            self._setup_bridge_tab()
            self._setup_settings_tab()
            
            # Create status bar at bottom
            self.status_bar = QWidget(self.content_frame)
            status_layout = QHBoxLayout(self.status_bar)
            status_layout.setContentsMargins(0, 5, 0, 0)
            
            self.status_label = QLabel("Ready")
            self.blockchain_status_indicator = QLabel()
            self.refresh_button = QPushButton("Refresh")
            self.refresh_button.clicked.connect(self._refresh_wallet_data)
            
            status_layout.addWidget(self.status_label, 1)  # 1 is stretch factor
            status_layout.addWidget(self.blockchain_status_indicator)
            status_layout.addWidget(self.refresh_button)
            
            self.main_layout.addWidget(self.status_bar)
            
            # Create refresh timer
            self.refresh_timer = QTimer(self)
            self.refresh_timer.timeout.connect(self._auto_refresh)
            self.refresh_timer.start(60000)  # Refresh every minute
            
            self.logger.info("Wallet UI setup completed")
        except Exception as e:
            self.logger.error(f"Error setting up wallet UI: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _setup_overview_tab(self):
        """Setup the overview tab with portfolio summary and charts."""
        layout = QVBoxLayout(self.overview_tab)
        
        # Top section with total balance
        top_section = QWidget()
        top_layout = QHBoxLayout(top_section)
        
        # Total balance display
        balance_widget = QWidget()
        balance_layout = QVBoxLayout(balance_widget)
        balance_label = QLabel("Total Portfolio Value")
        balance_value = QLabel(f"${self.total_balance_usd:.2f}")
        balance_value.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        balance_layout.addWidget(balance_label)
        balance_layout.addWidget(balance_value)
        
        # Portfolio change display
        change_widget = QWidget()
        change_layout = QVBoxLayout(change_widget)
        change_label = QLabel("24h Change")
        change_value = QLabel(f"+${self.portfolio_analytics.get('daily_change', 0.0):.2f}")
        change_value.setFont(QFont("Arial", 18))
        change_layout.addWidget(change_label)
        change_layout.addWidget(change_value)
        
        # Add to top section
        top_layout.addWidget(balance_widget)
        top_layout.addWidget(change_widget)
        
        # Chart section
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        
        # Create matplotlib figure for portfolio chart
        figure = Figure(figsize=(8, 4), dpi=100)
        self.portfolio_chart = figure.add_subplot(111)
        canvas = FigureCanvas(figure)
        chart_layout.addWidget(canvas)
        
        # Add sections to main layout
        layout.addWidget(top_section)
        layout.addWidget(chart_widget, 1)  # 1 is stretch factor
        
        # Quick actions section
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        
        send_btn = QPushButton("Send")
        receive_btn = QPushButton("Receive")
        swap_btn = QPushButton("Swap")
        stake_btn = QPushButton("Stake")
        
        # Connect buttons to actions
        send_btn.clicked.connect(self._show_send_dialog)
        receive_btn.clicked.connect(self._show_receive_dialog)
        swap_btn.clicked.connect(self._show_swap_dialog)
        stake_btn.clicked.connect(self._show_stake_dialog)
        
        actions_layout.addWidget(send_btn)
        actions_layout.addWidget(receive_btn)
        actions_layout.addWidget(swap_btn)
        actions_layout.addWidget(stake_btn)
        
        layout.addWidget(actions_widget)
    
    def _setup_assets_tab(self):
        """Setup the assets tab with list of all owned assets."""
        # Placeholder implementation - will be expanded in future commits
        layout = QVBoxLayout(self.assets_tab)
        
        # Filter controls
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        
        chain_combo = QComboBox()
        chain_combo.addItems(["All Chains"] + list(self.SUPPORTED_BLOCKCHAINS.keys()))
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search assets...")
        
        filter_layout.addWidget(QLabel("Chain:"))
        filter_layout.addWidget(chain_combo)
        filter_layout.addWidget(search_input, 1)  # 1 is stretch factor
        
        # Assets list
        self.assets_tree = QTreeWidget()
        self.assets_tree.setHeaderLabels(["Asset", "Balance", "Price", "Value", "24h"])
        self.assets_tree.setAlternatingRowColors(True)
        
        # Add to layout
        layout.addWidget(filter_widget)
        layout.addWidget(self.assets_tree)
    
    def _setup_transactions_tab(self):
        """Setup the transactions tab with transaction history."""
        # Placeholder implementation - will be expanded in future commits
        layout = QVBoxLayout(self.transactions_tab)
        
        # Transactions list
        self.transactions_tree = QTreeWidget()
        self.transactions_tree.setHeaderLabels(["Date", "Type", "Amount", "Asset", "Status", "Details"])
        self.transactions_tree.setAlternatingRowColors(True)
        
        layout.addWidget(self.transactions_tree)
    
    def _setup_defi_tab(self):
        """Setup the DeFi tab for staking, lending, and yield farming."""
        # Placeholder implementation - will be expanded in future commits
        layout = QVBoxLayout(self.defi_tab)
        layout.addWidget(QLabel("DeFi positions will be displayed here"))
    
    def _setup_nft_tab(self):
        """Setup the NFT tab for NFT collections and management."""
        # Placeholder implementation - will be expanded in future commits
        layout = QVBoxLayout(self.nft_tab)
        layout.addWidget(QLabel("NFT collections will be displayed here"))
    
    def _setup_bridge_tab(self):
        """Setup the bridge tab for cross-chain asset transfers."""
        # Placeholder implementation - will be expanded in future commits
        layout = QVBoxLayout(self.bridge_tab)
        layout.addWidget(QLabel("Cross-chain bridge interface will be displayed here"))
    
    def _setup_settings_tab(self):
        """Setup the settings tab for wallet configuration."""
        # Placeholder implementation - will be expanded in future commits
        layout = QVBoxLayout(self.settings_tab)
        layout.addWidget(QLabel("Wallet settings will be displayed here"))
    
    def _refresh_wallet_data(self):
        """Refresh wallet data from blockchain and other sources."""
        self.update_status("Refreshing wallet data...", "#2196F3")
        # In a real implementation, this would trigger async data loading
        # For now, just simulate with a timer
        QTimer.singleShot(1000, lambda: self.update_status("Wallet data refreshed", "#4CAF50"))
    
    def _auto_refresh(self):
        """Automatically refresh wallet data on timer interval."""
        self.logger.debug("Auto-refreshing wallet data")
        self._refresh_wallet_data()
    
    def _show_send_dialog(self):
        """Show dialog for sending assets to another address."""
        # In a real implementation, this would show a proper send dialog
        QMessageBox.information(self, "Send Assets", 
                              "Send dialog will be implemented in the next version.")
    
    def _show_receive_dialog(self):
        """Show dialog for receiving assets (displaying address)."""
        # In a real implementation, this would show a proper receive dialog with QR code
        QMessageBox.information(self, "Receive Assets", 
                              "Receive dialog will be implemented in the next version.")
    
    def _show_swap_dialog(self):
        """Show dialog for swapping between assets."""
        QMessageBox.information(self, "Swap Assets", 
                              "Swap dialog will be implemented in the next version.")
    
    def _show_stake_dialog(self):
        """Show dialog for staking assets."""
        QMessageBox.information(self, "Stake Assets", 
                              "Staking dialog will be implemented in the next version.")
    
    def update_status(self, message, color="#FFFFFF"):
        """Update status message in the status bar.
        
        Args:
            message: Status message to display
            color: Color for the message (hex format)
        """
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
            self.status_label.setStyleSheet(f"color: {color}")
            self.logger.debug(f"Status updated: {message}")
        else:
            self.logger.debug(f"Status update (no label): {message}")
    
    async def initialize(self):
        """Initialize the wallet frame.
        
        Returns:
            Literal[True]: Always returns True on successful initialization
        """
        from typing import Literal
        self.logger.info("Initializing Wallet frame")
        
        try:
            # Call parent initialization first
            await super().initialize()
            
            # Load blockchain provider API keys
            await self._load_blockchain_provider_keys()
            
            # Request initial data from all connected systems
            if hasattr(self, 'event_bus') and self.event_bus is not None:
                # Request wallet data
                self.event_bus.publish("wallet.request_data", {
                    "timestamp": datetime.now().isoformat()
                })
                
                # Request trading profit data
                self.event_bus.publish("trading.request_profits", {
                    "timestamp": datetime.now().isoformat()
                })
                
                # Request mining reward data
                self.event_bus.publish("mining.request_rewards", {
                    "timestamp": datetime.now().isoformat()
                })
                
                # Request blockchain status
                self.event_bus.publish("blockchain.request_status", {
                    "timestamp": datetime.now().isoformat()
                })
            
            self._request_wallet_data()
            
            self.update_status("Wallet interface ready with full system integration", "#4CAF50")
            self.logger.info("Wallet frame initialized with trading, mining, and blockchain connections")
        except Exception as e:
            self.logger.error(f"Error initializing wallet frame: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.update_status(f"Error: {str(e)[:30]}...", "#F44336")
            # Don't interrupt the initialization flow even if there's an error
        
        return True
    
    def register_event_handlers(self) -> None:
        """
        Register event handlers for wallet-related events.
        """
        if not self.event_bus:
            logger.warning("No event bus available for registration")
            return
        
        # Register event handlers synchronously to avoid coroutine warnings
        event_handlers = [
            ("wallet.ready", self._handle_wallet_ready),
            ("wallet.data", self._handle_wallet_data),
            ("wallet.transactions", self._handle_transactions_update),
            ("wallet.nfts", self._handle_nfts_update),
            ("wallet.defi", self._handle_defi_update),
            ("trading.profits", self._handle_trading_profits),
            ("mining.rewards", self._handle_mining_rewards),
            ("blockchain.status", self._handle_blockchain_status),
        ]
        
        for event_name, handler in event_handlers:
            try:
                # Synchronous subscription without await
                if hasattr(self.event_bus, 'subscribe_sync'):
                    self.event_bus.subscribe_sync(event_name, handler)
                else:
                    self.event_bus.subscribe(event_name, handler)
            except Exception as e:
                logger.error(f"Error registering handler for {event_name}: {str(e)}")
    
    def _subscribe_to_events(self):
        """Subscribe to wallet-specific events."""
        super()._subscribe_to_events()
        
        # Wallet-specific subscriptions
        if hasattr(self, 'event_bus') and self.event_bus is not None:
            try:
                # Core wallet events
                self._setup_event_listeners()
                
                # API key related events
                self._safe_subscribe("api_keys.updated", self._handle_api_key_update)
                self._safe_subscribe("api.key.added", self._handle_api_key_update)
                self._safe_subscribe("api.key.updated", self._handle_api_key_update)
                self._safe_subscribe("api.key.deleted", self._handle_api_key_update)
                
                # Trading system events for profits to wallet
                self._safe_subscribe("trading.profit", self._handle_trading_profit)
                self._safe_subscribe("trading.executed", self._handle_trade_executed)
                self._safe_subscribe("trading.fee", self._handle_trading_fee)
                
                # Mining system events for rewards to wallet
                self._safe_subscribe("mining.reward", self._handle_mining_reward)
                self._safe_subscribe("mining.payout", self._handle_mining_payout)
                
                # Blockchain events
                self._safe_subscribe("blockchain.transaction", self._handle_blockchain_transaction)
                self._safe_subscribe("blockchain.confirmation", self._handle_blockchain_confirmation)
                self._safe_subscribe("blockchain.status", self._handle_blockchain_status)
                
                self.logger.info("Wallet frame subscribed to events with full system integration")
            except Exception as e:
                self.logger.error(f"Error subscribing to wallet events: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
    
    def _setup_event_listeners(self):
        """Set up event listeners for wallet events."""
        if hasattr(self, 'event_bus') and self.event_bus:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._async_setup_event_listeners())
                else:
                    loop.run_until_complete(self._async_setup_event_listeners())
            except RuntimeError as e:
                logging.warning(f"Event loop error during event listener setup: {e}")
        else:
            logging.warning("No event bus available for event listener setup")
    
    async def _async_setup_event_listeners(self):
        """Asynchronously set up event listeners for wallet events."""
        self._safe_subscribe("wallet.balance", self._handle_balance_update)
        self._safe_subscribe("wallet.transaction", self._handle_transaction_update)
        self._safe_subscribe("wallet.address", self._handle_address_update)
        logging.info("Successfully subscribed to wallet events")
    
    async def _get_api_key(self, service):
        """Get API key for a specific service.
        
        Args:
            service: The service to get the API key for
            
        Returns:
            The API key if found, None otherwise
        """
        try:
            if not hasattr(self, 'api_key_connector') or not self.api_key_connector:
                self.logger.warning(f"No API key connector available for {service}")
                return None
                
            # Try to get the key from the connector
            key = await self.api_key_connector.get_api_key(service)
            if key:
                return key
            else:
                self.logger.warning(f"API key not found for {service}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting API key for {service}: {e}")
            return None
    
    async def _handle_api_key_update(self, event_data):
        """Handle API key update events.
        
        Args:
            event_data: Event data containing updated API key information
        """
        try:
            if not event_data or 'service' not in event_data:
                return
                
            service = event_data['service']
            
            # Check if this is a blockchain provider service
            blockchain_services = ['infura', 'alchemy', 'etherscan', 'blockcypher', 'chainstack', 'moralis', 'ethereum', 'bitcoin', 'coinbase', 'binance', 'polygon']
            
            if service in blockchain_services:
                # Reload blockchain provider keys
                self.logger.info(f"Reloading blockchain provider keys for {service}")
                await self._load_blockchain_provider_keys()
                self.update_status(f"Updated blockchain provider keys for {service}", "#4CAF50")
                
            # Check if the updated key is for a blockchain provider
            if service in ['infura', 'alchemy', 'etherscan', 'blockcypher', 'chainstack', 'moralis']:
                self.logger.info(f"Reloading API key for {service}")
                await self._load_blockchain_provider_keys()
                
                # If this is a blockchain we're actively using, reinitialize connections
                if service in self.web3_connections:
                    # Reinitialize the connection with the new API key
                    self.logger.info(f"Reinitializing connection for {service}")
                    # Implementation will depend on the specific blockchain provider
                    
                # Request updated wallet data with new API keys
                await self._request_wallet_data()
        except Exception as e:
            self.logger.error(f"Error handling API key update: {e}")
    
    async def _load_blockchain_provider_keys(self):
        """Load blockchain provider API keys from the API key connector."""
        try:
            # Load Ethereum provider keys
            for provider in ['infura', 'alchemy', 'etherscan']:
                provider_keys = await self._get_api_key(provider)
                if provider_keys:
                    self.blockchain_providers[provider] = provider_keys
                    self.logger.info(f"Loaded API key for {provider}")
                else:
                    self.logger.warning(f"No API key found for {provider}")
            
            # Load other blockchain provider keys
            for provider in ['blockcypher', 'chainstack', 'moralis']:
                provider_keys = await self._get_api_key(provider)
                if provider_keys:
                    self.blockchain_providers[provider] = provider_keys
                    self.logger.info(f"Loaded API key for {provider}")
            
            if not self.blockchain_providers:
                self.logger.warning("No blockchain provider API keys found. Some wallet functionality may be limited.")
                
            return True
        except Exception as e:
            self.logger.error(f"Error loading blockchain provider API keys: {str(e)}")
            return False
    
    def _get_theme_colors(self):
        """Get the theme colors based on dark/light mode setting.
        
        Returns:
            dict: Dictionary of theme colors
        """
        if self.dark_mode:
            return {
                "background": "#1e1e2e",
                "foreground": "#cdd6f4",
                "accent": "#89b4fa", 
                "secondary": "#a6e3a1",
                "tertiary": "#f5c2e7",
                "warning": "#fab387",
                "error": "#f38ba8",
                "success": "#a6e3a1",
                "chart_colors": ["#89b4fa", "#a6e3a1", "#f5c2e7", "#fab387", "#f38ba8", "#cba6f7"],
                "grid": "#313244",
                "panel": "#181825",
                "button": "#45475a",
                "button_hover": "#585b70"
            }
        else:
            return {
                "background": "#ffffff",
                "foreground": "#4c4f69",
                "accent": "#1e66f5",
                "secondary": "#40a02b",
                "tertiary": "#ea76cb",
                "warning": "#fe640b",
                "error": "#d20f39",
                "success": "#40a02b",
                "chart_colors": ["#1e66f5", "#40a02b", "#ea76cb", "#fe640b", "#d20f39", "#8839ef"],
                "grid": "#dce0e8",
                "panel": "#eff1f5",
                "button": "#ccd0da",
                "button_hover": "#bcc0cc"
            }
    
    def _setup_ui(self):
        """Set up the advanced multi-chain wallet UI components."""
        # Set theme colors
        self.colors = self._get_theme_colors()
        
        # Initialize UI elements dictionary
        self.ui_elements = {}
        
        # Create base styles for widgets
        self.style = ttk.Style()
        self.style.configure(
            "Wallet.TFrame", 
            background=self.colors["background"]
        )
        self.style.configure(
            "Wallet.TLabel", 
            background=self.colors["background"],
            foreground=self.colors["foreground"]
        )
        self.style.configure(
            "Wallet.TButton", 
            background=self.colors["button"],
            foreground=self.colors["foreground"]
        )
        
        # Create Treeview styles
        self.style.configure(
            "Wallet.Treeview", 
            background=self.colors["panel"],
            foreground=self.colors["foreground"],
            fieldbackground=self.colors["panel"]
        )
        self.style.configure(
            "Wallet.Treeview.Heading", 
            background=self.colors["button"],
            foreground=self.colors["foreground"]
        )
        
        # Setup content panels
        self.configure(bg=self.colors["background"])
        
        # Create the wallet interface
        self._create_wallet_layout()
        
    def _create_wallet_layout(self):
        """Create the advanced multi-chain wallet interface layout."""
        # Create main content frame if it doesn't exist
        if not hasattr(self, 'content_frame'):
            self.content_frame = ttk.Frame(self, style="Wallet.TFrame")
            self.content_frame.pack(fill=tk.BOTH, expand=True)
            
        # Portfolio overview section at the top
        self.portfolio_frame = ttk.Frame(self.content_frame, style="Wallet.TFrame")
        self.portfolio_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Total portfolio value display
        self.total_value_frame = ttk.Frame(self.portfolio_frame, style="Wallet.TFrame")
        self.total_value_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.portfolio_label = ttk.Label(
            self.total_value_frame, 
            text="Total Portfolio Value", 
            font=("Helvetica", 12),
            style="Wallet.TLabel"
        )
        self.portfolio_label.pack(anchor=tk.W)
        
        self.portfolio_value = ttk.Label(
            self.total_value_frame, 
            text="$0.00", 
            font=("Helvetica", 24, "bold"),
            style="Wallet.TLabel"
        )
        self.portfolio_value.pack(anchor=tk.W)
        
        # Performance indicators
        self.performance_frame = ttk.Frame(self.total_value_frame, style="Wallet.TFrame")
        self.performance_frame.pack(anchor=tk.W, fill=tk.X, pady=5)
        
        self.daily_change = ttk.Label(
            self.performance_frame, 
            text="24h: +0.00%", 
            foreground=self.colors["success"],
            style="Wallet.TLabel"
        )
        self.daily_change.pack(side=tk.LEFT, padx=(0, 15))
        
        self.weekly_change = ttk.Label(
            self.performance_frame, 
            text="7d: +0.00%", 
            foreground=self.colors["success"],
            style="Wallet.TLabel"
        )
        self.weekly_change.pack(side=tk.LEFT, padx=(0, 15))
        
        self.monthly_change = ttk.Label(
            self.performance_frame, 
            text="30d: +0.00%", 
            foreground=self.colors["success"],
            style="Wallet.TLabel"
        )
        self.monthly_change.pack(side=tk.LEFT)
        
        # Action buttons
        self.action_frame = ttk.Frame(self.portfolio_frame, style="Wallet.TFrame")
        self.action_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 0))
        
        # Add blockchain filter
        self.chain_filter_frame = ttk.Frame(self.action_frame, style="Wallet.TFrame")
        self.chain_filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.chain_label = ttk.Label(
            self.chain_filter_frame, 
            text="Blockchain:", 
            style="Wallet.TLabel"
        )
        self.chain_label.pack(side=tk.LEFT, padx=(0, 5))
        
        chain_values = ["All Chains"] + [self.SUPPORTED_BLOCKCHAINS[chain]["name"] for chain in self.SUPPORTED_BLOCKCHAINS]
        self.chain_dropdown = ttk.Combobox(
            self.chain_filter_frame, 
            values=chain_values,
            width=15,
            state="readonly"
        )
        self.chain_dropdown.current(0)
        self.chain_dropdown.pack(side=tk.LEFT)
        self.chain_dropdown.bind("<<ComboboxSelected>>", self._on_chain_selected)
        
        # Main buttons
        self.add_wallet_btn = ttk.Button(
            self.action_frame, 
            text="Add Wallet", 
            command=self._on_add_wallet,
            style="Wallet.TButton",
            width=15
        )
        self.add_wallet_btn.pack(pady=2)
        
        self.refresh_btn = ttk.Button(
            self.action_frame, 
            text="Refresh", 
            command=self._on_refresh_wallets,
            style="Wallet.TButton",
            width=15
        )
        self.refresh_btn.pack(pady=2)
        
        # Create notebook for different wallet sections
        self.wallet_notebook = ttk.Notebook(self.content_frame)
        self.wallet_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs for the notebook
        self.wallets_tab = ttk.Frame(self.wallet_notebook, style="Wallet.TFrame")
        self.wallet_notebook.add(self.wallets_tab, text="Wallets")
        
        self.transactions_tab = ttk.Frame(self.wallet_notebook, style="Wallet.TFrame")
        self.wallet_notebook.add(self.transactions_tab, text="Transactions")
        
        self.defi_tab = ttk.Frame(self.wallet_notebook, style="Wallet.TFrame")
        self.wallet_notebook.add(self.defi_tab, text="DeFi")
        
        self.nft_tab = ttk.Frame(self.wallet_notebook, style="Wallet.TFrame")
        self.wallet_notebook.add(self.nft_tab, text="NFTs")
        
        self.staking_tab = ttk.Frame(self.wallet_notebook, style="Wallet.TFrame")
        self.wallet_notebook.add(self.staking_tab, text="Staking")
        
        self.cross_chain_tab = ttk.Frame(self.wallet_notebook, style="Wallet.TFrame")
        self.wallet_notebook.add(self.cross_chain_tab, text="Cross-Chain")
        
        # Bind tab change event
        self.wallet_notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)
        
        # Setup split view in the Wallets tab
        self.wallets_tab.columnconfigure(0, weight=1)
        self.wallets_tab.rowconfigure(0, weight=1)
        
        self.wallets_paned = ttk.PanedWindow(self.wallets_tab, orient=tk.HORIZONTAL)
        self.wallets_paned.grid(row=0, column=0, sticky="nsew")
        
        # Left panel for wallets list
        self.wallets_frame = ttk.Frame(self.wallets_paned, style="Wallet.TFrame")
        self.wallets_paned.add(self.wallets_frame, weight=1)
        
        # Right panel for wallet details and visualization
        self.wallet_details_frame = ttk.Frame(self.wallets_paned, style="Wallet.TFrame")
        self.wallets_paned.add(self.wallet_details_frame, weight=2)
        
        # Setup transactions tab
        self.transactions_tab.columnconfigure(0, weight=1)
        self.transactions_tab.rowconfigure(0, weight=1)
        
        # Create the frames for each tab
        self.transactions_frame = ttk.Frame(self.transactions_tab, style="Wallet.TFrame")
        self.transactions_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Setup DeFi tab
        self.defi_tab.columnconfigure(0, weight=1)
        self.defi_tab.rowconfigure(0, weight=1)
        self.defi_frame = ttk.Frame(self.defi_tab, style="Wallet.TFrame")
        self.defi_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Setup NFT tab
        self.nft_tab.columnconfigure(0, weight=1)
        self.nft_tab.rowconfigure(0, weight=1)
        self.nft_frame = ttk.Frame(self.nft_tab, style="Wallet.TFrame")
        self.nft_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Setup Staking tab
        self.staking_tab.columnconfigure(0, weight=1)
        self.staking_tab.rowconfigure(0, weight=1)
        self.staking_frame = ttk.Frame(self.staking_tab, style="Wallet.TFrame")
        self.staking_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Setup Cross-Chain tab
        self.cross_chain_tab.columnconfigure(0, weight=1)
        self.cross_chain_tab.rowconfigure(0, weight=1)
        self.cross_chain_frame = ttk.Frame(self.cross_chain_tab, style="Wallet.TFrame")
        self.cross_chain_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Operations panel at the bottom
        self.operations_frame = ttk.Frame(self.content_frame, style="Wallet.TFrame")
        self.operations_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Create the component panels
        self._create_wallets_panel()
        self._create_transactions_panel()
        self._create_operations_panel()
        
        # Skip these panels for now if methods not yet defined
        # They'll be properly implemented in subsequent updates
        if hasattr(self, '_create_defi_panel'):
            self._create_defi_panel()
        if hasattr(self, '_create_nft_panel'):
            self._create_nft_panel()
        if hasattr(self, '_create_staking_panel'):
            self._create_staking_panel()
        if hasattr(self, '_create_cross_chain_panel'):
            self._create_cross_chain_panel()
    
    def _create_wallets_panel(self):
        """Create the wallets overview panel."""
        # Title
        wallets_label = ttk.Label(self.wallets_frame, text="My Wallets", font=("Helvetica", 12, "bold"))
        wallets_label.pack(pady=(0, 10))
        
        # Total balance card
        balance_frame = tk.Frame(self.wallets_frame, bg="#1E1E1E", height=80)
        balance_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(balance_frame, text="Total Balance (USD)", background="#1E1E1E", foreground="white").pack(pady=(5, 0))
        
        self.total_balance = tk.Label(
            balance_frame, text="$0.00", 
            font=("Helvetica", 20, "bold"), bg="#1E1E1E", fg="#4CAF50"
        )
        self.total_balance.pack(pady=(0, 5))
        
        # Wallet list
        wallet_list_frame = ttk.LabelFrame(self.wallets_frame, text="Cryptocurrencies")
        wallet_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview for wallets
        columns = ("Currency", "Balance", "Value")
        self.wallet_tree = ttk.Treeview(wallet_list_frame, columns=columns, show="headings", height=10)
        
        # Configure columns
        self.wallet_tree.heading("Currency", text="Currency")
        self.wallet_tree.heading("Balance", text="Balance")
        self.wallet_tree.heading("Value", text="Value (USD)")
        
        self.wallet_tree.column("Currency", width=100)
        self.wallet_tree.column("Balance", width=150)
        self.wallet_tree.column("Value", width=100)
        
        # Add scrollbar
        wallet_scrollbar = ttk.Scrollbar(wallet_list_frame, orient=tk.VERTICAL, command=self.wallet_tree.yview)
        self.wallet_tree.configure(yscrollcommand=wallet_scrollbar.set)
        
        # Pack tree and scrollbar
        self.wallet_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        wallet_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection event
        self.wallet_tree.bind("<<TreeviewSelect>>", self._on_wallet_selected)
        
        # Buttons for wallet management
        button_frame = ttk.Frame(self.wallets_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.add_wallet_button = ttk.Button(button_frame, text="Add Wallet", command=self._on_add_wallet)
        self.add_wallet_button.pack(side=tk.LEFT, padx=5)
        
        self.remove_wallet_button = ttk.Button(button_frame, text="Remove", command=self._on_remove_wallet)
        self.remove_wallet_button.pack(side=tk.LEFT, padx=5)
        
        self.refresh_button = ttk.Button(button_frame, text="Refresh", command=self._on_refresh_wallets)
        self.refresh_button.pack(side=tk.RIGHT, padx=5)
    
    def _create_transactions_panel(self):
        """Create the transactions panel."""
        # Title
        trans_label = ttk.Label(self.transactions_frame, text="Transactions", font=("Helvetica", 12, "bold"))
        trans_label.pack(pady=(0, 10))
        
        # Filter frame
        filter_frame = ttk.Frame(self.transactions_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Wallet:").pack(side=tk.LEFT, padx=5)
        self.wallet_selector = ttk.Combobox(filter_frame, textvariable=self.selected_wallet)
        self.wallet_selector.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Transactions list
        trans_list_frame = ttk.LabelFrame(self.transactions_frame, text="Recent Transactions")
        trans_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview for transactions
        columns = ("Date", "Type", "Amount", "Status")
        self.trans_tree = ttk.Treeview(trans_list_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.trans_tree.heading("Date", text="Date")
        self.trans_tree.heading("Type", text="Type")
        self.trans_tree.heading("Amount", text="Amount")
        self.trans_tree.heading("Status", text="Status")
        
        self.trans_tree.column("Date", width=120)
        self.trans_tree.column("Type", width=80)
        self.trans_tree.column("Amount", width=100)
        self.trans_tree.column("Status", width=80)
        
        # Add scrollbar
        trans_scrollbar = ttk.Scrollbar(trans_list_frame, orient=tk.VERTICAL, command=self.trans_tree.yview)
        self.trans_tree.configure(yscrollcommand=trans_scrollbar.set)
        
        # Pack tree and scrollbar
        self.trans_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        trans_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Details button
        details_button = ttk.Button(self.transactions_frame, text="Transaction Details", command=self._on_view_transaction)
        details_button.pack(anchor=tk.E, padx=5, pady=5)
    
    def _create_operations_panel(self):
        """Create the wallet operations panel."""
        operations_frame = ttk.LabelFrame(self.content_frame, text="Wallet Operations")
        operations_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create a row of operation buttons
        button_frame = ttk.Frame(operations_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        operations = [
            {"text": "Send", "command": self._on_send, "icon": "↑", "color": "#F44336"},
            {"text": "Receive", "command": self._on_receive, "icon": "↓", "color": "#4CAF50"},
            {"text": "Swap", "command": self._on_swap, "icon": "⇄", "color": "#2196F3"},
            {"text": "Stake", "command": self._on_stake, "icon": "✓", "color": "#FF9800"}
        ]
        
        for op in operations:
            # Create a frame for the button
            op_frame = tk.Frame(button_frame, bg=op["color"], width=120, height=80)
            op_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            op_frame.pack_propagate(False)  # Don't shrink
            
            # Create the button label
            icon = tk.Label(op_frame, text=op["icon"], font=("Helvetica", 20), bg=op["color"], fg="white")
            icon.pack(pady=(10, 0))
            
            text = tk.Label(op_frame, text=op["text"], bg=op["color"], fg="white")
            text.pack()
            
            # Make the frame clickable
            op_frame.bind("<Button-1>", op["command"])
            icon.bind("<Button-1>", op["command"])
            text.bind("<Button-1>", op["command"])
    
    def update_wallets(self, wallets):
        """Update the wallets list with new data."""
        # Clear existing items
        for item in self.wallet_tree.get_children():
            self.wallet_tree.delete(item)
        
        # Update wallet selector values
        wallet_names = ["All Wallets"] + [w.get("name", w.get("currency", "Unknown")) for w in wallets]
        self.wallet_selector.config(values=wallet_names)
        if not self.selected_wallet.get() or self.selected_wallet.get() not in wallet_names:
            self.selected_wallet.set("All Wallets")
        
        # Calculate total balance
        total_usd = 0.0
        
        # Add wallets to tree
        for wallet in wallets:
            currency = wallet.get("currency", "Unknown")
            balance = wallet.get("balance", 0.0)
            usd_value = wallet.get("usd_value", 0.0)
            
            # Format values
            if balance < 0.01:
                balance_str = f"{balance:.8f}".rstrip('0').rstrip('.')
            else:
                balance_str = f"{balance:.4f}".rstrip('0').rstrip('.')
            
            usd_str = f"${usd_value:.2f}"
            
            # Add to tree
            self.wallet_tree.insert("", tk.END, values=(currency, balance_str, usd_str))
            
            # Add to total
            total_usd += usd_value
        
        # Update total balance
        self.total_balance.config(text=f"${total_usd:.2f}")
        self.total_balance_usd = total_usd
        
        # Store wallets data
        self.wallets = {w.get("currency", f"wallet_{i}"): w for i, w in enumerate(wallets)}
        self.log_message(f"Updated {len(wallets)} wallets")
    
    def update_transactions(self, transactions, wallet_filter=None):
        """Update the transactions list with new data."""
        # Clear existing items
        for item in self.trans_tree.get_children():
            self.trans_tree.delete(item)
        
        # Filter transactions if needed
        if wallet_filter and wallet_filter != "All Wallets":
            filtered_transactions = [t for t in transactions if t.get("currency", "") == wallet_filter]
        else:
            filtered_transactions = transactions
        
        # Add transactions to tree
        for transaction in filtered_transactions:
            # Get transaction details
            date = transaction.get("date", "Unknown")
            tx_type = transaction.get("type", "Unknown")
            amount = transaction.get("amount", 0.0)
            status = transaction.get("status", "Pending")
            
            # Format amount with sign
            if tx_type.lower() == "send":
                amount_str = f"-{amount:.8f}".rstrip('0').rstrip('.')
                tag = "send"
            else:
                amount_str = f"+{amount:.8f}".rstrip('0').rstrip('.')
                tag = "receive"
            
            # Status tag
            status_tag = status.lower()
            
            # Add to tree with appropriate tags
            self.trans_tree.insert("", 0, values=(date, tx_type, amount_str, status), tags=(tag, status_tag))
        
        # Configure tag colors
        self.trans_tree.tag_configure("send", foreground="#F44336")
        self.trans_tree.tag_configure("receive", foreground="#4CAF50")
        self.trans_tree.tag_configure("confirmed", background="#E8F5E9")
        self.trans_tree.tag_configure("pending", background="#FFF9C4")
        self.trans_tree.tag_configure("failed", background="#FFEBEE")
        
        # Store transactions
        self.transactions = transactions
        self.log_message(f"Updated {len(filtered_transactions)} transactions")
    
    def _on_wallet_selected(self, event):
        """Handle wallet selection in the treeview."""
        selected_items = self.wallet_tree.selection()
        if not selected_items:
            return
        
        # Get the selected wallet
        item = selected_items[0]
        currency = self.wallet_tree.item(item, 'values')[0]
        
        # Update selected wallet
        self.selected_wallet.set(currency)
        self.log_message(f"Selected wallet: {currency}")
        
        # Update transactions for this wallet
        self.update_transactions(self.transactions, currency)
    
    def _on_add_wallet(self):
        """Handle add wallet button click."""
        try:
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("wallet.add_wallet", {
                    "request_id": str(uuid.uuid4()),
                    "source": "wallet_frame",
                    "timestamp": datetime.now().isoformat()
                })
                self.log_message("Add wallet request published")
                self.update_status("Opening add wallet dialog...", "#4CAF50")
            else:
                self.log_message("Event bus unavailable for add wallet")
                self.update_status("Event bus not connected", "#FF5252")
        except Exception as e:
            self.logger.error(f"Error in _on_add_wallet: {e}")
            self.update_status(f"Error: {e}", "#FF5252")
    
    def _on_receive(self, event=None):
        """Handle receive button click."""
        selected_wallet = self._get_selected_wallet()
        if not selected_wallet:
            self.update_status("No wallet selected", "#FF5252")
            return
        
        # Display receive address for the selected wallet
        self.log_message(f"Showing receive address for {selected_wallet}")
        
        # In a real implementation, we would display a QR code and address
        # This would use blockchain provider APIs which would need API keys
    
    def _on_remove_wallet(self):
        """Handle remove wallet button click."""
        try:
            selected_items = self.wallet_tree.selection()
            if not selected_items:
                self.update_status("No wallet selected", "#FF5252")
                return
            
            item = selected_items[0]
            currency = self.wallet_tree.item(item, 'values')[0]
            
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("wallet.remove_wallet", {
                    "request_id": str(uuid.uuid4()),
                    "currency": currency,
                    "source": "wallet_frame",
                    "timestamp": datetime.now().isoformat()
                })
                self.log_message(f"Remove wallet request published for {currency}")
                self.update_status(f"Removing {currency} wallet...", "#FFC107")
            else:
                self.log_message("Event bus unavailable for remove wallet")
                self.update_status("Event bus not connected", "#FF5252")
        except Exception as e:
            self.logger.error(f"Error in _on_remove_wallet: {e}")
            self.update_status(f"Error: {e}", "#FF5252")
    
    def _on_refresh_wallets(self):
        """Handle refresh button click."""
        self.log_message("Refreshing wallet data...")
        
        # Request updated wallet data
        self._request_wallet_data()
        
    def _on_view_transaction(self):
        """Handle view transaction details button click."""
        try:
            selected_items = self.trans_tree.selection()
            if not selected_items:
                self.update_status("No transaction selected", "#FF5252")
                return
            
            item = selected_items[0]
            values = self.trans_tree.item(item, 'values')
            date = values[0]
            tx_type = values[1]
            amount = values[2] if len(values) > 2 else "N/A"
            status = values[3] if len(values) > 3 else "N/A"
            
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("wallet.view_transaction", {
                    "request_id": str(uuid.uuid4()),
                    "date": date,
                    "type": tx_type,
                    "amount": amount,
                    "status": status,
                    "source": "wallet_frame",
                    "timestamp": datetime.now().isoformat()
                })
                self.log_message(f"Viewing transaction: {tx_type} on {date}")
                self.update_status(f"Loading transaction details...", "#4CAF50")
            else:
                self.log_message(f"Transaction: {tx_type} | {date} | {amount} | {status}")
        except Exception as e:
            self.logger.error(f"Error in _on_view_transaction: {e}")
            self.update_status(f"Error: {e}", "#FF5252")
    
    def _on_send(self, event=None):
        """Handle send button click."""
        try:
            selected_wallet = self._get_selected_wallet()
            if not selected_wallet:
                self.update_status("No wallet selected", "#FF5252")
                return
            
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("wallet.send", {
                    "request_id": str(uuid.uuid4()),
                    "currency": selected_wallet,
                    "source": "wallet_frame",
                    "timestamp": datetime.now().isoformat()
                })
                self.log_message(f"Send request published for {selected_wallet}")
                self.update_status(f"Opening send dialog for {selected_wallet}...", "#4CAF50")
            else:
                self.log_message("Event bus unavailable for send")
                self.update_status("Event bus not connected", "#FF5252")
        except Exception as e:
            self.logger.error(f"Error in _on_send: {e}")
            self.update_status(f"Error: {e}", "#FF5252")
    
    def _on_swap(self, event=None):
        """Handle swap button click."""
        try:
            selected_wallet = self._get_selected_wallet()
            if not selected_wallet:
                self.update_status("No wallet selected", "#FF5252")
                return
            
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("wallet.swap", {
                    "request_id": str(uuid.uuid4()),
                    "currency": selected_wallet,
                    "source": "wallet_frame",
                    "timestamp": datetime.now().isoformat()
                })
                self.log_message(f"Swap request published for {selected_wallet}")
                self.update_status(f"Opening swap dialog for {selected_wallet}...", "#4CAF50")
            else:
                self.log_message("Event bus unavailable for swap")
                self.update_status("Event bus not connected", "#FF5252")
        except Exception as e:
            self.logger.error(f"Error in _on_swap: {e}")
            self.update_status(f"Error: {e}", "#FF5252")
    
    def _on_stake(self, event=None):
        """Handle stake button click."""
        try:
            selected_wallet = self._get_selected_wallet()
            if not selected_wallet:
                self.update_status("No wallet selected", "#FF5252")
                return
            
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("wallet.stake", {
                    "request_id": str(uuid.uuid4()),
                    "currency": selected_wallet,
                    "source": "wallet_frame",
                    "timestamp": datetime.now().isoformat()
                })
                self.log_message(f"Stake request published for {selected_wallet}")
                self.update_status(f"Opening staking options for {selected_wallet}...", "#4CAF50")
            else:
                self.log_message("Event bus unavailable for stake")
                self.update_status("Event bus not connected", "#FF5252")
        except Exception as e:
            self.logger.error(f"Error in _on_stake: {e}")
            self.update_status(f"Error: {e}", "#FF5252")
    
    def _get_selected_wallet(self):
        """Get the currently selected wallet from the treeview."""
        selected_items = self.wallet_tree.selection()
        if not selected_items:
            return None
        
        # Get the selected wallet
        item = selected_items[0]
        currency = self.wallet_tree.item(item, 'values')[0]
        return currency
    
    def _request_wallet_data(self):
        """Request updated wallet data."""
        if hasattr(self, 'event_bus') and self.event_bus:
            self.event_bus.publish("wallet.request_data", {
                "request_id": str(uuid.uuid4()),
                "source": "wallet_frame"
            })
        else:
            logger.warning("Event bus not available for requesting wallet data")
        return None
    
    async def _handle_wallet_data(self, event_data):
        """Handle wallet data events.
        
        Args:
            event_data: Dictionary containing wallet data
        """
        try:
            if "wallets" in event_data:
                wallets = event_data["wallets"]
                self.update_wallets(wallets)
            
            if "transactions" in event_data:
                transactions = event_data["transactions"]
                wallet_filter = self.selected_wallet.get()
                self.update_transactions(transactions, wallet_filter)
        except Exception as e:
            self.logger.error(f"Error handling wallet data: {e}")
    
    async def _handle_balance_update(self, event_data):
        """Handle wallet balance update events.
        
        Args:
            event_data: Dictionary containing balance update information
        """
        try:
            if "currency" in event_data and "balance" in event_data:
                currency = event_data["currency"]
                balance = event_data["balance"]
                usd_value = event_data.get("usd_value", 0.0)
                
                # Update wallet in cache
                if currency in self.wallets:
                    self.wallets[currency]["balance"] = balance
                    self.wallets[currency]["usd_value"] = usd_value
                
                # Refresh wallet list
                wallets = list(self.wallets.values())
                self.update_wallets(wallets)
                
                self.log_message(f"Updated {currency} balance: {balance}")
        except Exception as e:
            self.logger.error(f"Error handling balance update: {e}")
    
    async def _handle_transaction_update(self, event_data):
        """Handle transaction update events.
        
        Args:
            event_data: Dictionary containing transaction information
        """
        try:
            if "transaction" in event_data:
                transaction = event_data["transaction"]
                wallet_id = event_data.get("wallet_id")
                
                # Add to transactions list
                self.transactions.append(transaction)
                
                # Update transactions view
                self.update_transactions(self.transactions, wallet_id)
                
                # Update status
                tx_type = transaction.get("type", "Transaction")
                tx_status = transaction.get("status", "completed")
                amount = transaction.get("amount", 0.0)
                currency = transaction.get("currency", "")
                
                self.update_status(f"{tx_type} {tx_status}", "#4CAF50")
                self.log_message(f"New transaction: {tx_type} {amount} {currency}")
        except Exception as e:
            self.logger.error(f"Error handling transaction update: {e}")
    
    async def _handle_address_update(self, event_data):
        """Handle address update events.
        
        Args:
            event_data: Dictionary containing address information
        """
        try:
            if "address" in event_data and "currency" in event_data:
                address = event_data["address"]
                currency = event_data["currency"]
                
                # Update wallet in cache
                if currency in self.wallets:
                    self.wallets[currency]["address"] = address
                
                # Refresh wallet list
                wallets = list(self.wallets.values())
                self.update_wallets(wallets)
                
                self.log_message(f"Updated {currency} address: {address}")
        except Exception as e:
            self.logger.error(f"Error handling address update: {e}")
    
    async def _handle_wallet_error(self, event_data):
        """Handle wallet error events.
        
        Args:
            event_data: Dictionary containing error information
        """
        try:
            error_msg = event_data.get("message", "Unknown wallet error")
            self.logger.error(f"Wallet error: {error_msg}")
            self.update_status(f"Error: {error_msg}", "#FF5252")
        except Exception as e:
            self.logger.error(f"Error handling wallet error: {e}")
    
    def log_message(self, message, level="info"):
        """Log a message to the application log and the logger.
        
        Args:
            message: The message to log
            level: The log level (info, warning, error)
        """
        if level == "error":
            self.logger.error(message)
        elif level == "warning":
            self.logger.warning(message)
        else:
            self.logger.info(message)
        
        # Update status bar
        color = "#4CAF50"  # Default green
        if level == "error":
            color = "#FF5252"  # Red
        elif level == "warning":
            color = "#FFC107"  # Amber
            
        self.update_status(message, color)
        
    # ---- Trading System Integration Handlers ----
    
    async def _handle_trading_profit(self, event_data):
        """Handle trading profit events from the trading system.
        
        Args:
            event_data: Dictionary containing profit information
        """
        try:
            if not event_data:
                return
                
            # Extract trading profit details
            profit_amount = event_data.get("amount", 0.0)
            currency = event_data.get("currency", "UNKNOWN")
            trade_id = event_data.get("trade_id", "unknown")
            timestamp = event_data.get("timestamp", datetime.now().isoformat())
            exchange = event_data.get("exchange", "unknown")
            
            # Store trading profit for tracking
            self.trading_profits[trade_id] = {
                "amount": profit_amount,
                "currency": currency,
                "timestamp": timestamp,
                "exchange": exchange,
                "type": "trading_profit"
            }
            
            # Create wallet transaction from trading profit
            transaction = {
                "tx_hash": f"trade_{trade_id}",
                "amount": profit_amount,
                "currency": currency,
                "timestamp": timestamp,
                "type": "income",
                "category": "trading_profit",
                "status": "completed",
                "source": exchange
            }
            
            # Add to transactions list
            self.transactions.append(transaction)
            
            # Update transactions view
            self.update_transactions(self.transactions)
            
            # Update wallet balance
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("wallet.update_balance", {
                    "currency": currency,
                    "amount": profit_amount,
                    "source": "trading"
                })
            
            self.log_message(f"Trading profit received: {profit_amount} {currency} from {exchange}")
        except Exception as e:
            self.logger.error(f"Error handling trading profit: {e}")
    
    async def _handle_trade_executed(self, event_data):
        """Handle trade executed events from the trading system.
        
        Args:
            event_data: Dictionary containing trade execution information
        """
        try:
            if not event_data:
                return
                
            # Extract trade details
            order_id = event_data.get("order_id", "unknown")
            side = event_data.get("side", "unknown")
            amount = event_data.get("amount", 0.0)
            price = event_data.get("price", 0.0)
            currency = event_data.get("currency", "UNKNOWN")
            market = event_data.get("market", "unknown")
            timestamp = event_data.get("timestamp", datetime.now().isoformat())
            exchange = event_data.get("exchange", "unknown")
            
            # Create transaction for tracking
            transaction = {
                "tx_hash": f"order_{order_id}",
                "amount": amount,
                "price": price,
                "currency": currency,
                "timestamp": timestamp,
                "type": "buy" if side.lower() == "buy" else "sell",
                "category": "trading",
                "status": "completed",
                "source": exchange,
                "market": market
            }
            
            # Add to transactions list
            self.transactions.append(transaction)
            
            # Update transactions view
            self.update_transactions(self.transactions)
            
            # Update status
            self.log_message(f"Trade executed: {side} {amount} {currency} at {price}")
        except Exception as e:
            self.logger.error(f"Error handling trade executed: {e}")
    
    async def _handle_trading_fee(self, event_data):
        """Handle trading fee events from the trading system.
        
        Args:
            event_data: Dictionary containing fee information
        """
        try:
            if not event_data:
                return
                
            # Extract fee details
            fee_amount = event_data.get("amount", 0.0)
            currency = event_data.get("currency", "UNKNOWN")
            order_id = event_data.get("order_id", "unknown")
            timestamp = event_data.get("timestamp", datetime.now().isoformat())
            exchange = event_data.get("exchange", "unknown")
            
            # Create transaction for fee
            transaction = {
                "tx_hash": f"fee_{order_id}",
                "amount": -fee_amount,  # Negative for outgoing
                "currency": currency,
                "timestamp": timestamp,
                "type": "fee",
                "category": "trading_fee",
                "status": "completed",
                "source": exchange
            }
            
            # Add to transactions list
            self.transactions.append(transaction)
            
            # Update transactions view
            self.update_transactions(self.transactions)
            
            # Update wallet balance
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("wallet.update_balance", {
                    "currency": currency,
                    "amount": -fee_amount,  # Negative for outgoing
                    "source": "trading_fee"
                })
            
            self.log_message(f"Trading fee: {fee_amount} {currency} on {exchange}")
        except Exception as e:
            self.logger.error(f"Error handling trading fee: {e}")
    
    # ---- Mining System Integration Handlers ----
    
    async def _handle_mining_reward(self, event_data):
        """Handle mining reward events from the mining system.
        
        Args:
            event_data: Dictionary containing mining reward information
        """
        try:
            if not event_data:
                return
                
            # Extract mining reward details
            reward_amount = event_data.get("amount", 0.0)
            currency = event_data.get("currency", "UNKNOWN")
            block_id = event_data.get("block_id", "unknown")
            timestamp = event_data.get("timestamp", datetime.now().isoformat())
            pool = event_data.get("pool", "unknown")
            status = event_data.get("status", "pending")
            
            # Store mining reward for tracking
            self.mining_rewards[block_id] = {
                "amount": reward_amount,
                "currency": currency,
                "timestamp": timestamp,
                "pool": pool,
                "status": status,
                "type": "mining_reward"
            }
            
            # If the reward is confirmed, add it as a transaction
            if status == "confirmed":
                # Create wallet transaction from mining reward
                transaction = {
                    "tx_hash": f"mining_{block_id}",
                    "amount": reward_amount,
                    "currency": currency,
                    "timestamp": timestamp,
                    "type": "income",
                    "category": "mining_reward",
                    "status": "completed",
                    "source": pool
                }
                
                # Add to transactions list
                self.transactions.append(transaction)
                
                # Update transactions view
                self.update_transactions(self.transactions)
                
                # Update wallet balance
                if hasattr(self, 'event_bus') and self.event_bus:
                    self.event_bus.publish("wallet.update_balance", {
                        "currency": currency,
                        "amount": reward_amount,
                        "source": "mining"
                    })
            
            self.log_message(f"Mining reward: {reward_amount} {currency} from {pool} ({status})")
        except Exception as e:
            self.logger.error(f"Error handling mining reward: {e}")
    
    async def _handle_mining_payout(self, event_data):
        """Handle mining payout events from the mining system.
        
        Args:
            event_data: Dictionary containing mining payout information
        """
        try:
            if not event_data:
                return
                
            # Extract mining payout details
            payout_amount = event_data.get("amount", 0.0)
            currency = event_data.get("currency", "UNKNOWN")
            tx_hash = event_data.get("tx_hash", "unknown")
            timestamp = event_data.get("timestamp", datetime.now().isoformat())
            pool = event_data.get("pool", "unknown")
            
            # Create wallet transaction from mining payout
            transaction = {
                "tx_hash": tx_hash,
                "amount": payout_amount,
                "currency": currency,
                "timestamp": timestamp,
                "type": "income",
                "category": "mining_payout",
                "status": "completed",
                "source": pool
            }
            
            # Add to transactions list
            self.transactions.append(transaction)
            
            # Update transactions view
            self.update_transactions(self.transactions)
            
            # Update wallet balance
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("wallet.update_balance", {
                    "currency": currency,
                    "amount": payout_amount,
                    "source": "mining_payout"
                })
            
            self.log_message(f"Mining payout received: {payout_amount} {currency} from {pool}")
        except Exception as e:
            self.logger.error(f"Error handling mining payout: {e}")
    
    # ---- Blockchain Integration Handlers ----
    
    async def _handle_blockchain_transaction(self, event_data):
        """Handle blockchain transaction events.
        
        Args:
            event_data: Dictionary containing blockchain transaction information
        """
        try:
            if not event_data:
                return
                
            # Extract transaction details
            tx_hash = event_data.get("tx_hash", "unknown")
            amount = event_data.get("amount", 0.0)
            currency = event_data.get("currency", "UNKNOWN")
            timestamp = event_data.get("timestamp", datetime.now().isoformat())
            from_address = event_data.get("from", "unknown")
            to_address = event_data.get("to", "unknown")
            confirmations = event_data.get("confirmations", 0)
            blockchain = event_data.get("blockchain", "unknown")
            
            # Store pending transaction
            self.pending_transactions[tx_hash] = {
                "amount": amount,
                "currency": currency,
                "timestamp": timestamp,
                "from": from_address,
                "to": to_address,
                "confirmations": confirmations,
                "blockchain": blockchain,
                "status": "pending" if confirmations < 6 else "confirmed"
            }
            
            # Update transactions in UI
            self._refresh_pending_transactions()
            
            self.log_message(f"Blockchain transaction: {amount} {currency}, confirmations: {confirmations}")
        except Exception as e:
            self.logger.error(f"Error handling blockchain transaction: {e}")
    
    async def _handle_blockchain_confirmation(self, event_data):
        """Handle blockchain confirmation events.
        
        Args:
            event_data: Dictionary containing confirmation information
        """
        try:
            if not event_data:
                return
                
            # Extract confirmation details
            tx_hash = event_data.get("tx_hash", "unknown")
            confirmations = event_data.get("confirmations", 0)
            
            # Update pending transaction if exists
            if tx_hash in self.pending_transactions:
                self.pending_transactions[tx_hash]["confirmations"] = confirmations
                self.pending_transactions[tx_hash]["status"] = "pending" if confirmations < 6 else "confirmed"
                
                # If newly confirmed, add to regular transactions
                if confirmations >= 6 and self.pending_transactions[tx_hash].get("added_to_transactions", False) == False:
                    tx_data = self.pending_transactions[tx_hash]
                    
                    # Create wallet transaction
                    transaction = {
                        "tx_hash": tx_hash,
                        "amount": tx_data["amount"],
                        "currency": tx_data["currency"],
                        "timestamp": tx_data["timestamp"],
                        "type": "income" if tx_data["to"] == self.get_wallet_address(tx_data["currency"]) else "expense",
                        "category": "blockchain_transfer",
                        "status": "completed",
                        "source": tx_data["blockchain"],
                        "from": tx_data["from"],
                        "to": tx_data["to"]
                    }
                    
                    # Add to transactions list
                    self.transactions.append(transaction)
                    self.pending_transactions[tx_hash]["added_to_transactions"] = True
                    
                    # Update wallet balance if incoming transaction
                    if hasattr(self, 'event_bus') and self.event_bus:
                        self.event_bus.publish("wallet.update_balance", {
                            "currency": tx_data["currency"],
                            "amount": tx_data["amount"],
                            "source": "blockchain_transfer"
                        })
                
                # Update transactions in UI
                self._refresh_pending_transactions()
                self.update_transactions(self.transactions)
            
            self.log_message(f"Transaction {tx_hash}: {confirmations} confirmations")
        except Exception as e:
            self.logger.error(f"Error handling blockchain confirmation: {e}")
    
    async def _handle_blockchain_status(self, event_data):
        """Handle blockchain status events.
        
        Args:
            event_data: Dictionary containing blockchain status information
        """
        try:
            if not event_data:
                return
                
            # Extract blockchain status details
            blockchain = event_data.get("blockchain", "unknown")
            status = event_data.get("status", "unknown")
            block_height = event_data.get("block_height", 0)
            sync_status = event_data.get("sync_status", 0.0)  # As percentage
            network = event_data.get("network", "mainnet")
            
            # Store blockchain status
            self.blockchain_statuses[blockchain] = {
                "status": status,
                "block_height": block_height,
                "sync_status": sync_status,
                "network": network,
                "last_updated": datetime.now().isoformat()
            }
            
            # Update status if needed
            if status != "connected":
                self.log_message(f"Blockchain {blockchain} status: {status}", "warning")
        except Exception as e:
            self.logger.error(f"Error handling blockchain status: {e}")
    
    def _refresh_pending_transactions(self):
        """Refresh the pending transactions view."""
        try:
            # Implementation of pending transactions update in UI
            # This would update a separate pending transactions section in the UI
            pass
        except Exception as e:
            self.logger.error(f"Error refreshing pending transactions: {e}")
    
    def _on_chain_selected(self, event):
        """Handle blockchain selection change.
        
        Args:
            event: The event object
        """
        try:
            selected = self.chain_dropdown.get()
            self.logger.info(f"Selected blockchain: {selected}")
            
            # Update UI with wallets for selected blockchain
            if selected == "All Chains":
                # Show all wallets
                self.update_wallets(self.wallets)
            else:
                # Find the chain code for the selected name
                chain_code = None
                for code, chain_info in self.SUPPORTED_BLOCKCHAINS.items():
                    if chain_info["name"] == selected:
                        chain_code = code
                        break
                        
                if chain_code and chain_code in self.wallets:
                    # Show only wallets for the selected blockchain
                    self.update_wallets({chain_code: self.wallets[chain_code]})
                else:
                    # No wallets for this blockchain yet
                    self.update_wallets({})
                    
            # Update UI elements based on blockchain selection
            self._update_blockchain_specific_ui(selected)
        except Exception as e:
            self.logger.error(f"Error handling blockchain selection: {e}")
            
    def _update_blockchain_specific_ui(self, blockchain):
        """Update UI elements specific to the selected blockchain.
        
        Args:
            blockchain: The selected blockchain name
        """
        try:
            # Update DeFi options, network options, etc. based on selected blockchain
            if blockchain == "All Chains":
                # Show generic/combined options
                pass
            else:
                # Find blockchain code
                chain_code = None
                for code, info in self.SUPPORTED_BLOCKCHAINS.items():
                    if info["name"] == blockchain:
                        chain_code = code
                        break
                        
                if chain_code:
                    # Update network options
                    networks = self.SUPPORTED_BLOCKCHAINS[chain_code]["networks"]
                    
                    # Update DeFi capabilities
                    defi_enabled = self.SUPPORTED_BLOCKCHAINS[chain_code]["defi_enabled"]
                    
                    # Update staking capabilities
                    staking_enabled = self.SUPPORTED_BLOCKCHAINS[chain_code]["staking_enabled"]
                    
                    # Update NFT capabilities
                    nft_enabled = self.SUPPORTED_BLOCKCHAINS[chain_code]["nft_enabled"]
                    
                    # Update UI accordingly
                    # This would enable/disable various buttons and options
        except Exception as e:
            self.logger.error(f"Error updating blockchain-specific UI: {e}")
            
    def _on_notebook_tab_changed(self, event):
        """Handle notebook tab change events.
        
        Args:
            event: The event object
        """
        try:
            tab_id = self.wallet_notebook.index("current")
            tab_name = self.wallet_notebook.tab(tab_id, "text")
            self.logger.info(f"Switched to tab: {tab_name}")
            
            # Update UI based on selected tab
            if tab_name == "Wallets":
                # Refresh wallet list
                self._request_wallet_data()
            elif tab_name == "Transactions":
                # Refresh transaction history
                self.update_transactions(self.transactions)
            elif tab_name == "DeFi":
                # Refresh DeFi positions and opportunities
                self._refresh_defi_data()
            elif tab_name == "NFTs":
                # Refresh NFT gallery
                self._refresh_nft_data()
            elif tab_name == "Staking":
                # Refresh staking positions
                self._refresh_staking_data()
            elif tab_name == "Cross-Chain":
                # Refresh cross-chain transfer options
                self._refresh_cross_chain_data()
        except Exception as e:
            self.logger.error(f"Error handling tab change: {e}")
    
    def _create_defi_panel(self):
        """Create the DeFi panel with liquidity pools, yield farming, and more."""
        try:
            # Setup the DeFi panel in the DeFi tab
            self.defi_frame.columnconfigure(0, weight=1)
            self.defi_frame.rowconfigure(0, weight=1)
            
            # Create header with DeFi overview
            self.defi_header = ttk.Frame(self.defi_frame, style="Wallet.TFrame")
            self.defi_header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
            
            self.defi_title = ttk.Label(
                self.defi_header,
                text="DeFi Dashboard",
                font=("Helvetica", 16, "bold"),
                style="Wallet.TLabel"
            )
            self.defi_title.pack(side=tk.LEFT, anchor=tk.W)
            
            # Create main content area with tabs for different DeFi activities
            self.defi_notebook = ttk.Notebook(self.defi_frame)
            self.defi_notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
            
            # Create tabs for different DeFi features
            self.pools_tab = ttk.Frame(self.defi_notebook, style="Wallet.TFrame")
            self.defi_notebook.add(self.pools_tab, text="Liquidity Pools")
            
            self.farming_tab = ttk.Frame(self.defi_notebook, style="Wallet.TFrame")
            self.defi_notebook.add(self.farming_tab, text="Yield Farming")
            
            self.lending_tab = ttk.Frame(self.defi_notebook, style="Wallet.TFrame")
            self.defi_notebook.add(self.lending_tab, text="Lending")
            
            self.borrowing_tab = ttk.Frame(self.defi_notebook, style="Wallet.TFrame")
            self.defi_notebook.add(self.borrowing_tab, text="Borrowing")
            
            # Create an overview panel for total DeFi position value
            self.defi_overview = ttk.Frame(self.defi_frame, style="Wallet.TFrame")
            self.defi_overview.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
            
            self.total_defi_label = ttk.Label(
                self.defi_overview,
                text="Total DeFi Value:",
                style="Wallet.TLabel"
            )
            self.total_defi_label.pack(side=tk.LEFT, padx=(0, 5))
            
            self.total_defi_value = ttk.Label(
                self.defi_overview,
                text="$0.00",
                font=("Helvetica", 12, "bold"),
                style="Wallet.TLabel"
            )
            self.total_defi_value.pack(side=tk.LEFT)
            
            # Add placeholder content
            self._setup_defi_placeholder()
        except Exception as e:
            self.logger.error(f"Error creating DeFi panel: {e}")
    
    def _setup_defi_placeholder(self):
        """Set up placeholder content for DeFi tabs."""
        # Add placeholder content to liquidity pools tab
        ttk.Label(
            self.pools_tab,
            text="Connect a wallet to view available liquidity pools",
            style="Wallet.TLabel"
        ).pack(padx=20, pady=20)
        
        # Add placeholder content to yield farming tab
        ttk.Label(
            self.farming_tab,
            text="Connect a wallet to view yield farming opportunities",
            style="Wallet.TLabel"
        ).pack(padx=20, pady=20)
    
    def _create_nft_panel(self):
        """Create the NFT gallery panel."""
        try:
            # Setup the NFT panel in the NFT tab
            self.nft_frame.columnconfigure(0, weight=1)
            self.nft_frame.rowconfigure(1, weight=1)
            
            # Create header with search and filter options
            self.nft_header = ttk.Frame(self.nft_frame, style="Wallet.TFrame")
            self.nft_header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
            
            self.nft_title = ttk.Label(
                self.nft_header,
                text="NFT Gallery",
                font=("Helvetica", 16, "bold"),
                style="Wallet.TLabel"
            )
            self.nft_title.pack(side=tk.LEFT, anchor=tk.W)
            
            # Create NFT grid view
            self.nft_canvas = tk.Canvas(
                self.nft_frame,
                bg=self.colors["panel"],
                highlightthickness=0
            )
            self.nft_canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
            
            # Add scrollbar
            self.nft_scrollbar = ttk.Scrollbar(self.nft_frame, orient="vertical", command=self.nft_canvas.yview)
            self.nft_canvas.configure(yscrollcommand=self.nft_scrollbar.set)
            
            # Create frame for NFT items
            self.nft_grid = ttk.Frame(self.nft_canvas, style="Wallet.TFrame")
            self.nft_canvas.create_window((0, 0), window=self.nft_grid, anchor="nw")
            
            # Add placeholder content
            self._setup_nft_placeholder()
        except Exception as e:
            self.logger.error(f"Error creating NFT panel: {e}")
    
    def _setup_nft_placeholder(self):
        """Set up placeholder content for NFT gallery."""
        ttk.Label(
            self.nft_grid,
            text="Connect a wallet to view your NFT collection",
            style="Wallet.TLabel"
        ).pack(padx=20, pady=20)
    
    def _create_staking_panel(self):
        """Create the staking panel for various staking opportunities."""
        try:
            # Setup the staking panel in the staking tab
            self.staking_frame.columnconfigure(0, weight=1)
            self.staking_frame.rowconfigure(1, weight=1)
            
            # Create header with overview
            self.staking_header = ttk.Frame(self.staking_frame, style="Wallet.TFrame")
            self.staking_header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
            
            self.staking_title = ttk.Label(
                self.staking_header,
                text="Staking Dashboard",
                font=("Helvetica", 16, "bold"),
                style="Wallet.TLabel"
            )
            self.staking_title.pack(side=tk.LEFT, anchor=tk.W)
            
            # Create main content with staking opportunities
            self.staking_content = ttk.Frame(self.staking_frame, style="Wallet.TFrame")
            self.staking_content.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
            
            # Create treeview for staking options
            self.staking_tree = ttk.Treeview(
                self.staking_content,
                columns=("asset", "network", "apy", "lockup", "status"),
                show="headings",
                style="Wallet.Treeview"
            )
            
            # Define columns
            self.staking_tree.heading("asset", text="Asset")
            self.staking_tree.heading("network", text="Network")
            self.staking_tree.heading("apy", text="APY")
            self.staking_tree.heading("lockup", text="Lockup Period")
            self.staking_tree.heading("status", text="Status")
            
            self.staking_tree.column("asset", width=100)
            self.staking_tree.column("network", width=100)
            self.staking_tree.column("apy", width=80)
            self.staking_tree.column("lockup", width=100)
            self.staking_tree.column("status", width=100)
            
            self.staking_tree.pack(fill=tk.BOTH, expand=True)
            
            # Add sample staking options
            self._populate_staking_options()
        except Exception as e:
            self.logger.error(f"Error creating staking panel: {e}")
    
    def _populate_staking_options(self):
        """Populate staking options with sample data."""
        # Clear existing items
        for item in self.staking_tree.get_children():
            self.staking_tree.delete(item)
            
        # Add sample staking options
        sample_options = [
            ("ETH", "Ethereum", "5.2%", "None", "Available"),
            ("SOL", "Solana", "7.8%", "None", "Available"),
            ("DOT", "Polkadot", "12.5%", "28 days", "Available"),
            ("ADA", "Cardano", "4.8%", "None", "Available"),
            ("ATOM", "Cosmos", "10.2%", "21 days", "Available"),
            ("ALGO", "Algorand", "6.1%", "None", "Available")
        ]
        
        for option in sample_options:
            self.staking_tree.insert("", tk.END, values=option)
    
    def _create_cross_chain_panel(self):
        """Create the cross-chain transfer panel."""
        try:
            # Setup the cross-chain panel
            self.cross_chain_frame.columnconfigure(0, weight=1)
            self.cross_chain_frame.rowconfigure(1, weight=1)
            
            # Create header
            self.cross_chain_header = ttk.Frame(self.cross_chain_frame, style="Wallet.TFrame")
            self.cross_chain_header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
            
            self.cross_chain_title = ttk.Label(
                self.cross_chain_header,
                text="Cross-Chain Transfers",
                font=("Helvetica", 16, "bold"),
                style="Wallet.TLabel"
            )
            self.cross_chain_title.pack(side=tk.LEFT, anchor=tk.W)
            
            # Create main content for cross-chain transfers
            self.bridge_frame = ttk.Frame(self.cross_chain_frame, style="Wallet.TFrame")
            self.bridge_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
            
            # Create bridge selection section
            self.bridge_selection = ttk.LabelFrame(
                self.bridge_frame,
                text="Bridge Selection",
                style="Wallet.TFrame"
            )
            self.bridge_selection.pack(fill=tk.X, padx=10, pady=10)
            
            # Source blockchain dropdown
            self.source_frame = ttk.Frame(self.bridge_selection, style="Wallet.TFrame")
            self.source_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(
                self.source_frame,
                text="From:",
                style="Wallet.TLabel"
            ).pack(side=tk.LEFT, padx=(0, 5))
            
            self.source_chain = ttk.Combobox(
                self.source_frame,
                values=[self.SUPPORTED_BLOCKCHAINS[chain]["name"] for chain in self.SUPPORTED_BLOCKCHAINS],
                state="readonly",
                width=15
            )
            self.source_chain.pack(side=tk.LEFT, padx=5)
            
            # Destination blockchain dropdown
            self.dest_frame = ttk.Frame(self.bridge_selection, style="Wallet.TFrame")
            self.dest_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(
                self.dest_frame,
                text="To:    ",
                style="Wallet.TLabel"
            ).pack(side=tk.LEFT, padx=(0, 5))
            
            self.dest_chain = ttk.Combobox(
                self.dest_frame,
                values=[self.SUPPORTED_BLOCKCHAINS[chain]["name"] for chain in self.SUPPORTED_BLOCKCHAINS],
                state="readonly",
                width=15
            )
            self.dest_chain.pack(side=tk.LEFT, padx=5)
            
            # Bridge provider selection
            self.bridge_provider_frame = ttk.Frame(self.bridge_selection, style="Wallet.TFrame")
            self.bridge_provider_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(
                self.bridge_provider_frame,
                text="Bridge:",
                style="Wallet.TLabel"
            ).pack(side=tk.LEFT, padx=(0, 5))
            
            self.bridge_provider = ttk.Combobox(
                self.bridge_provider_frame,
                values=["Multichain", "Wormhole", "Synapse", "Hop", "Across", "Stargate"],
                state="readonly",
                width=15
            )
            self.bridge_provider.pack(side=tk.LEFT, padx=5)
            
            # Amount to bridge
            self.amount_frame = ttk.Frame(self.bridge_selection, style="Wallet.TFrame")
            self.amount_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(
                self.amount_frame,
                text="Amount:",
                style="Wallet.TLabel"
            ).pack(side=tk.LEFT, padx=(0, 5))
            
            self.bridge_amount = ttk.Entry(self.amount_frame, width=15)
            self.bridge_amount.pack(side=tk.LEFT, padx=5)
            
            # Bridge button
            self.bridge_button_frame = ttk.Frame(self.bridge_selection, style="Wallet.TFrame")
            self.bridge_button_frame.pack(fill=tk.X, padx=10, pady=10)
            
            self.bridge_button = ttk.Button(
                self.bridge_button_frame,
                text="Bridge Assets",
                command=self._on_bridge_assets,
                style="Wallet.TButton"
            )
            self.bridge_button.pack(side=tk.RIGHT)
            
            # Create bridge history section
            self.bridge_history = ttk.LabelFrame(
                self.bridge_frame,
                text="Bridge History",
                style="Wallet.TFrame"
            )
            self.bridge_history.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Create treeview for bridge history
            self.bridge_tree = ttk.Treeview(
                self.bridge_history,
                columns=("date", "from", "to", "amount", "status"),
                show="headings",
                style="Wallet.Treeview"
            )
            
            # Define columns
            self.bridge_tree.heading("date", text="Date")
            self.bridge_tree.heading("from", text="From")
            self.bridge_tree.heading("to", text="To")
            self.bridge_tree.heading("amount", text="Amount")
            self.bridge_tree.heading("status", text="Status")
            
            self.bridge_tree.column("date", width=150)
            self.bridge_tree.column("from", width=100)
            self.bridge_tree.column("to", width=100)
            self.bridge_tree.column("amount", width=100)
            self.bridge_tree.column("status", width=100)
            
            self.bridge_tree.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            self.logger.error(f"Error creating cross-chain panel: {e}")
    
    def _on_bridge_assets(self):
        """Handle bridge assets button click."""
        try:
            source = self.source_chain.get()
            destination = self.dest_chain.get()
            bridge = self.bridge_provider.get()
            amount = self.bridge_amount.get()
            
            if not source or not destination or not bridge or not amount:
                messagebox.showwarning("Incomplete Information", "Please fill in all fields")
                return
                
            if source == destination:
                messagebox.showwarning("Invalid Selection", "Source and destination blockchains must be different")
                return
                
            try:
                amount_float = float(amount)
                if amount_float <= 0:
                    messagebox.showwarning("Invalid Amount", "Amount must be greater than zero")
                    return
            except ValueError:
                messagebox.showwarning("Invalid Amount", "Amount must be a valid number")
                return
                
            # In a real implementation, this would initiate the cross-chain transfer
            # For now, just show a message and add to history
            messagebox.showinfo("Bridge Initiated", 
                               f"Initiating transfer of {amount} from {source} to {destination} via {bridge}")
                               
            # Add to bridge history
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "Pending"
            
            self.bridge_tree.insert("", tk.END, values=(date, source, destination, amount, status))
            
            # Clear input fields
            self.bridge_amount.delete(0, tk.END)
        except Exception as e:
            self.logger.error(f"Error initiating bridge: {e}")
    
    def _refresh_defi_data(self):
        """Refresh DeFi data from blockchain."""
        try:
            self.log_message("Refreshing DeFi data...")
            if hasattr(self, 'total_defi_value'):
                self.total_defi_value.configure(text="Refreshing...")
            
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("defi.request_data", {
                    "request_id": str(uuid.uuid4()),
                    "source": "wallet_frame",
                    "data_types": ["pools", "farming", "lending", "borrowing"],
                    "timestamp": datetime.now().isoformat()
                })
            else:
                self.logger.warning("Event bus not available for DeFi refresh")
                if hasattr(self, 'total_defi_value'):
                    self.total_defi_value.configure(text="$0.00 (offline)")
        except Exception as e:
            self.logger.error(f"Error refreshing DeFi data: {e}")
            if hasattr(self, 'total_defi_value'):
                self.total_defi_value.configure(text="Error")
    
    def _refresh_nft_data(self):
        """Refresh NFT data from blockchain."""
        try:
            self.log_message("Refreshing NFT data...")
            if hasattr(self, 'nft_title'):
                self.nft_title.configure(text="NFT Gallery (refreshing...)")
            
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("nft.request_data", {
                    "request_id": str(uuid.uuid4()),
                    "source": "wallet_frame",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                self.logger.warning("Event bus not available for NFT refresh")
                if hasattr(self, 'nft_title'):
                    self.nft_title.configure(text="NFT Gallery (offline)")
        except Exception as e:
            self.logger.error(f"Error refreshing NFT data: {e}")
            if hasattr(self, 'nft_title'):
                self.nft_title.configure(text="NFT Gallery (error)")
    
    def _refresh_staking_data(self):
        """Refresh staking data from blockchain."""
        try:
            self.log_message("Refreshing staking data...")
            if hasattr(self, 'staking_title'):
                self.staking_title.configure(text="Staking Dashboard (refreshing...)")
            
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("staking.request_data", {
                    "request_id": str(uuid.uuid4()),
                    "source": "wallet_frame",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                self.logger.warning("Event bus not available for staking refresh")
                if hasattr(self, 'staking_tree'):
                    self._populate_staking_options()
                if hasattr(self, 'staking_title'):
                    self.staking_title.configure(text="Staking Dashboard (offline)")
        except Exception as e:
            self.logger.error(f"Error refreshing staking data: {e}")
            if hasattr(self, 'staking_title'):
                self.staking_title.configure(text="Staking Dashboard (error)")
    
    def _refresh_cross_chain_data(self):
        """Refresh cross-chain bridge data."""
        try:
            self.log_message("Refreshing cross-chain data...")
            if hasattr(self, 'cross_chain_title'):
                self.cross_chain_title.configure(text="Cross-Chain Transfers (refreshing...)")
            
            if hasattr(self, 'event_bus') and self.event_bus:
                self.event_bus.publish("cross_chain.request_data", {
                    "request_id": str(uuid.uuid4()),
                    "source": "wallet_frame",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                self.logger.warning("Event bus not available for cross-chain refresh")
                if hasattr(self, 'cross_chain_title'):
                    self.cross_chain_title.configure(text="Cross-Chain Transfers (offline)")
        except Exception as e:
            self.logger.error(f"Error refreshing cross-chain data: {e}")
            if hasattr(self, 'cross_chain_title'):
                self.cross_chain_title.configure(text="Cross-Chain Transfers (error)")
    
    def get_wallet_address(self, currency):
        """Get wallet address for a specific currency.
        
        Args:
            currency: Currency to get address for
            
        Returns:
            Wallet address if found, None otherwise
        """
        try:
            if currency in self.wallets:
                return self.wallets[currency].get("address")
            return None
        except Exception as e:
            self.logger.error(f"Error getting wallet address: {e}")
            return None

    def _safe_subscribe(self, event_name: str, handler: Callable) -> None:
        try:
            if hasattr(self, 'event_bus') and self.event_bus and hasattr(self.event_bus, 'subscribe'):
                self.event_bus.subscribe(event_name, handler)
                logging.debug(f"Subscribed to {event_name} in {self.name}")
            else:
                logging.warning(f"No event bus available for {event_name} in {self.name}")
        except Exception as e:
            logging.error(f"Error subscribing to {event_name} in {self.name}: {e}")
