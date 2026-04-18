"""
Modern QT Wallet for Kingdom AI

A state-of-the-art cryptocurrency wallet with support for multiple blockchains,
DeFi integration, and seamless trading/mining system integration.

Features:
- Multi-chain support (Ethereum, Bitcoin, Solana, etc.)
- Real-time balance and transaction updates
- DeFi integration (staking, yield farming)
- NFT gallery and management
- Cross-chain swaps
- Portfolio analytics
- Hardware wallet support
- Biometric authentication
- Integrated with Kingdom AI theming system
"""

import os
import sys
import json
import time
import asyncio
import logging
import redis
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from datetime import datetime, timedelta

# QT Imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QLineEdit, QComboBox, QMessageBox, QSplitter, QFrame, QHeaderView,
    QAbstractItemView, QFormLayout, QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QProgressBar, QMenu, QMenuBar,
    QApplication, QAbstractScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QSize, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread, QObject, QSettings
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QLinearGradient, QFont, QFontMetrics, QAction

# Local imports
from core.wallet_manager import WalletManager
from core.event_bus import EventBus
from core.redis_connector import RedisQuantumNexusConnector
from utils.helpers import format_currency, format_crypto, format_date
from utils.logger import get_logger
from ..kingdom_style import GlowButton, RGBBorderFrame, FrameHeader, create_themed_frame, rgb_animation_manager
from ..styles import (
    ACCENT_COLOR, BACKGROUND_COLOR, CARD_COLOR, TEXT_COLOR, SECONDARY_TEXT,
    ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR, BORDER_COLOR, HOVER_COLOR
)
from .base_frame_qt import BaseFrameQt

# Type hints
from typing import Dict, List, Optional, Any, Union, Tuple, Callable

# Configure logger
logger = get_logger(__name__)

class WalletQt(BaseFrameQt):
    """Modern QT Wallet for Kingdom AI"""
    
    # Supported blockchains and their properties
    SUPPORTED_BLOCKCHAINS = {
        "ETH": {
            "name": "Ethereum",
            "icon": "ethereum.png",
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
        # Add other blockchains as needed
    }
    
    # Define signals
    theme_changed = pyqtSignal(str)  # Emitted when theme changes
    
    def __init__(self, parent=None, event_bus: Optional[EventBus] = None, **kwargs):
        """Initialize the wallet"""
        super().__init__(parent, event_bus, **kwargs)
        self.setObjectName("WalletQt")
        
        # Initialize Redis connection first - Kingdom AI requires Redis
        self._initialize_redis_connection()
        
        # Initialize wallet manager
        self.wallet_manager = WalletManager(event_bus=event_bus)
        
        # Wallet state
        self.wallets = {}
        self.transactions = []
        self.balances = {}
        self.prices = {}
        self.selected_wallet = None
        self.selected_chain = "ETH"  # Default to Ethereum
        
        # UI State
        settings = QSettings("KingdomAI", "Wallet")
        saved_theme = settings.value("theme", "dark")
        self.current_theme = self._load_theme(saved_theme)
        
        # Set window properties
        self.setWindowTitle("Kingdom AI Wallet")
        self.setWindowIcon(QIcon(":/icons/wallet.png"))
        
        # Enable high DPI scaling
        self.setAttribute(Qt.WidgetAttribute.WA_UseHighDpiPixmaps)
        
        # Set window size and position
        screen = QApplication.primaryScreen().geometry()
        self.resize(
            min(1200, screen.width() * 0.8),
            min(800, screen.height() * 0.8)
        )
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
        
        # Initialize UI
        self.init_ui()
        
        # Connect to wallet manager
        self._connect_wallet_manager()
        
        # Start periodic updates
        self._start_updates()
        
    def _initialize_redis_connection(self):
        """Initialize Redis connection with strict enforcement.
        
        Kingdom AI requires a strict Redis connection policy with immediate halt on failure.
        No fallbacks or degraded modes are allowed.
        """
        logger.info("Initializing Redis connection for Wallet tab")
        try:
            # Create Redis connection
            self.redis_conn = redis.Redis(
                host='localhost',
                port=6380,  # Kingdom AI strictly requires port 6380
                password='QuantumNexus2025',  # Required password for Kingdom AI
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection with ping
            if not self.redis_conn.ping():
                error_msg = "Redis Quantum Nexus connection failed (ping failed)"
                logger.critical(error_msg)
                QMessageBox.critical(
                    self,
                    "Critical Error",
                    "Redis Quantum Nexus connection failed. Kingdom AI requires Redis to function. System will exit."
                )
                sys.exit(1)  # Halt system immediately as required
                
            logger.info("Successfully connected to Redis Quantum Nexus")
            
        except Exception as e:
            error_msg = f"Redis Quantum Nexus connection error: {str(e)}"
            logger.critical(error_msg)
            QMessageBox.critical(
                self,
                "Critical Error",
                f"Failed to connect to Redis Quantum Nexus: {str(e)}\n\nKingdom AI requires Redis to function. System will exit."
            )
            sys.exit(1)  # Halt system immediately as required
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setMinimumSize(800, 600)
        
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar, stretch=1)
        
        # Content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # Header
        header = self._create_header()
        content_layout.addLayout(header)
        
        # Balance card
        self.balance_card = self._create_balance_card()
        content_layout.addWidget(self.balance_card)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("walletTabs")
        
        # Add tabs
        self.overview_tab = self._create_overview_tab()
        self.send_tab = self._create_send_tab()
        self.receive_tab = self._create_receive_tab()
        self.transactions_tab = self._create_transactions_tab()
        self.defi_tab = self._create_defi_tab()
        self.nft_tab = self._create_nft_tab()
        
        self.tabs.addTab(self.overview_tab, self.tr("Overview"))
        self.tabs.addTab(self.send_tab, self.tr("Send"))
        self.tabs.addTab(self.receive_tab, self.tr("Receive"))
        self.tabs.addTab(self.transactions_tab, self.tr("Transactions"))
        self.tabs.addTab(self.defi_tab, self.tr("DeFi"))
        self.tabs.addTab(self.nft_tab, self.tr("NFTs"))
        
        content_layout.addWidget(self.tabs, stretch=1)
        
        main_layout.addWidget(content_widget, stretch=4)
        
        # Apply styles
        self._apply_styles()
    
    def _create_sidebar(self) -> QWidget:
        """Create the sidebar with wallet list and navigation"""
        # Create a themed frame for the sidebar
        sidebar_frame, inner_frame = create_themed_frame(self, border_width=2, corner_radius=10)
        layout = QVBoxLayout(inner_frame)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(15)
        
        # Create header with Kingdom AI styling
        header = FrameHeader(inner_frame, "WALLETS")
        layout.addWidget(header)
        
        # Add wallet button with glow effect
        add_wallet_btn = GlowButton(
            inner_frame,
            text="+ Add Wallet",
            glow_color=SUCCESS_COLOR,
            command=self._on_add_wallet
        )
        add_wallet_btn.setFixedHeight(40)
        
        # Wallet list with custom styling
        self.wallet_list = QListWidget()
        self.wallet_list.setObjectName("walletList")
        self.wallet_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: 1px solid #2D2D3D;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #1E1E2D;
                border-radius: 5px;
                padding: 10px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background-color: #2D2D3D;
                border: 1px solid #4CAF50;
            }
        """)
        self.wallet_list.itemClicked.connect(self._on_wallet_selected)
        
        # Add to layout
        layout.addWidget(add_wallet_btn)
        layout.addWidget(self.wallet_list, 1)  # Take remaining space
        
        return sidebar_frame
    
    def _create_header(self) -> QHBoxLayout:
        """Create the header with title and actions"""
        header = QHBoxLayout()
        
        # Title with accent color
        title = QLabel("WALLET DASHBOARD")
        title.setStyleSheet(f"""
            QLabel {{
                color: {ACCENT_COLOR};
                font-size: 18px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
        """)
        
        # Actions container with glow effect
        actions_container = QFrame()
        actions_container.setStyleSheet("""
            QFrame {
                background-color: #1E1E2D;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        actions = QHBoxLayout(actions_container)
        actions.setContentsMargins(5, 5, 5, 5)
        actions.setSpacing(10)
        
        # Refresh button with glow effect
        refresh_btn = GlowButton(
            text="",
            icon=QIcon(":/icons/refresh.png"),
            glow_color=ACCENT_COLOR,
            command=self._on_refresh
        )
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setToolTip("Refresh Wallet Data")
        
        # Settings button with glow effect
        settings_btn = GlowButton(
            text="",
            icon=QIcon(":/icons/settings.png"),
            glow_color=ACCENT_COLOR,
            command=self._on_settings
        )
        settings_btn.setFixedSize(32, 32)
        settings_btn.setToolTip("Wallet Settings")
        
        actions.addWidget(refresh_btn)
        actions.addWidget(settings_btn)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(actions_container)
        
        return header
    
    def _create_balance_card(self) -> QWidget:
        """Create the balance card widget with Kingdom AI theming"""
        # Create a themed frame for the balance card
        card, inner_frame = create_themed_frame(self, corner_radius=10, border_width=2)
        layout = QVBoxLayout(inner_frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Total balance label
        balance_title = QLabel("TOTAL BALANCE")
        balance_title.setStyleSheet(f"""
            QLabel {{
                color: {SECONDARY_TEXT};
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
        """)
        
        # Total balance amount with large font
        self.total_balance_label = QLabel("$0.00")
        self.total_balance_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_COLOR};
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
        """)
        
        # 24h change with color-coded indicator
        self.balance_change_label = QLabel("+0.00% (24h)")
        self.balance_change_label.setStyleSheet(f"""
            QLabel {{
                color: {SUCCESS_COLOR};
                font-size: 14px;
                font-weight: bold;
            }}
        """)
        
        # Chain selector with custom styling
        chain_selector_frame = QFrame()
        chain_selector_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 5px;
                padding: 5px;
            }}
        """)
        chain_selector_layout = QHBoxLayout(chain_selector_frame)
        chain_selector_layout.setContentsMargins(5, 2, 5, 2)
        
        chain_label = QLabel("Network:")
        chain_label.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 12px;")
        
        self.chain_selector = QComboBox()
        self.chain_selector.setStyleSheet(f"""
            QComboBox {{
                background-color: transparent;
                color: {TEXT_COLOR};
                border: none;
                padding: 5px;
                min-width: 120px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {CARD_COLOR};
                color: {TEXT_COLOR};
                selection-background-color: {ACCENT_COLOR};
                border: 1px solid {BORDER_COLOR};
            }}
        """)
        
        # Add supported chains with icons if available
        for chain_id, chain in self.SUPPORTED_BLOCKCHAINS.items():
            self.chain_selector.addItem(chain["name"], chain_id)
        
        self.chain_selector.currentIndexChanged.connect(self._on_chain_changed)
        
        chain_selector_layout.addWidget(chain_label)
        chain_selector_layout.addWidget(self.chain_selector, 1)
        
        # Add to layout
        layout.addWidget(balance_title)
        layout.addWidget(self.total_balance_label)
        layout.addWidget(self.balance_change_label)
        layout.addWidget(chain_selector_frame)
        
        # Add stretch to push content to top
        layout.addStretch()
        
        return card
    
    def _create_overview_tab(self) -> QWidget:
        """Create the overview tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Portfolio chart
        self.portfolio_chart = QLabel("Portfolio Chart")
        self.portfolio_chart.setMinimumHeight(200)
        
        # Assets table
        self.assets_table = QTableWidget()
        self.assets_table.setColumnCount(5)
        self.assets_table.setHorizontalHeaderLabels(["Asset", "Balance", "Price", "Value", "24h"])
        self.assets_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.assets_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Add to layout
        layout.addWidget(QLabel("Portfolio"))
        layout.addWidget(self.portfolio_chart)
        layout.addWidget(QLabel("Assets"))
        layout.addWidget(self.assets_table)
        
        return tab
    
    def _create_send_tab(self) -> QWidget:
        """Create the send tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Form
        form = QFormLayout()
        
        # Asset selector
        self.send_asset = QComboBox()
        
        # Amount
        self.send_amount = QLineEdit()
        self.send_amount.setPlaceholderText("0.00")
        
        # Recipient
        self.recipient = QLineEdit()
        self.recipient.setPlaceholderText("Address or ENS")
        
        # Max button
        max_btn = QPushButton("MAX")
        max_btn.clicked.connect(self._on_max_clicked)
        
        # Send button
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._on_send_clicked)
        
        # Add to form
        form.addRow("Asset:", self.send_asset)
        form.addRow("Amount:", self.send_amount)
        form.addRow("To:", self.recipient)
        form.addRow("", max_btn)
        form.addRow("", send_btn)
        
        layout.addLayout(form)
        layout.addStretch()
        
        return tab
    
    def _create_receive_tab(self) -> QWidget:
        """Create the receive tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # QR code
        self.qr_code = QLabel()
        self.qr_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Address
        self.address_label = QLabel()
        self.address_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.address_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        # Copy button
        copy_btn = QPushButton("Copy Address")
        copy_btn.clicked.connect(self._on_copy_address)
        
        # Add to layout
        layout.addStretch()
        layout.addWidget(self.qr_code)
        layout.addWidget(self.address_label)
        layout.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        
        return tab
    
    def _create_transactions_tab(self) -> QWidget:
        """Create the transactions tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Transactions table
        self.transactions_table = QTableWidget()
        self.transactions_table.setColumnCount(5)
        self.transactions_table.setHorizontalHeaderLabels(["Date", "Type", "Amount", "Status", "Details"])
        self.transactions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.transactions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.transactions_table)
        
        return tab
    
    def _create_defi_tab(self) -> QWidget:
        """Create the DeFi tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Placeholder for DeFi content
        layout.addWidget(QLabel("DeFi features coming soon..."))
        
        return tab
    
    def _create_nft_tab(self) -> QWidget:
        """Create the NFTs tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Placeholder for NFT content
        layout.addWidget(QLabel("NFT gallery coming soon..."))
        
        return tab
    
    def _connect_signals(self):
        """Connect all UI signals to their respective slots"""
        # Connect tab changes
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        # Connect wallet actions
        self.send_button.clicked.connect(self._on_send_clicked)
        self.receive_button.clicked.connect(self._on_receive_clicked)
        self.refresh_button.clicked.connect(self._on_refresh)
        
        # Connect menu actions
        self.settings_action.triggered.connect(self._on_settings)
        self.export_action.triggered.connect(self._on_export_wallet)
        self.import_action.triggered.connect(self._on_import_wallet)
        self.about_action.triggered.connect(self._show_about)
    
    def _load_initial_data(self):
        """Load initial wallet data and populate UI"""
        try:
            # Load wallets from wallet manager
            self.wallets = self.wallet_manager.get_wallets()
            
            # Update wallet list
            self._update_wallet_list()
            
            # Load initial balances
            self._update_balances()
            
            # Load recent transactions
            self._load_transactions()
            
        except Exception as e:
            logger.error(f"Error loading initial wallet data: {e}")
            self.show_error("Error", f"Failed to load wallet data: {str(e)}")
    
    def _apply_styles(self):
        """Apply Kingdom AI theming to the wallet"""
        try:
            if not hasattr(self, 'current_theme') or not self.current_theme:
                logger.warning("No theme set, loading default theme")
                self.current_theme = self._load_theme("dark")
            
            # Apply the generated styles
            self.setStyleSheet(self.current_theme.get('styles', ''))
            
            # Apply any additional dynamic styles
            self._apply_dynamic_styles()
            
            # Save theme preference
            settings = QSettings("KingdomAI", "Wallet")
            settings.setValue("theme/name", self.current_theme.get('name', 'dark'))
            settings.setValue("theme/variant", self.current_theme.get('variant', 'default'))
            
            # Update status bar with theme info if available
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(
                    f"Theme set to {self.current_theme.get('name', 'dark')} "
                    f"({self.current_theme.get('variant', 'default')})"
                )
                
            # Force refresh of all widgets
            self.update()
            
            # Log theme change
            logger.info(
                "Theme changed to %s (%s)", 
                self.current_theme.get('name', 'dark'),
                self.current_theme.get('variant', 'default')
            )
            
            # Emit theme changed signal
            self.theme_changed.emit(self.current_theme.get('name', 'dark'))
            
        except Exception as e:
            logger.error("Error applying theme: %s", str(e))
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(f"Error applying theme: {str(e)}", 5000)
                
    def _apply_dynamic_styles(self):
        """Apply styles that need to be updated dynamically.
        
        This method updates the styles of various UI elements based on the current theme.
        It handles dynamic styling for balance labels, sidebar, and title elements.
        """
        if not hasattr(self, 'current_theme') or not self.current_theme:
            logger.warning("No theme available for dynamic styling")
            return
            
        theme = self.current_theme
        
        # Ensure required theme properties exist
        theme.setdefault('primary', '#89b4fa')
        theme.setdefault('secondary', '#b4befe')
        theme.setdefault('accent', '#f5c2e7')
        theme.setdefault('background', '#1e1e2e')
        theme.setdefault('surface', '#313244')
        theme.setdefault('border', '#45475a')
        theme.setdefault('text', '#cdd6f4')
        theme.setdefault('text_secondary', '#a6adc8')
        theme.setdefault('highlight', '#585b70')
        
        # Update balance label if it exists
        if hasattr(self, 'balance_label'):
            self.balance_label.setStyleSheet(
                f"""
                QLabel {{
                    font-size: 32px;
                    font-weight: bold;
                    color: {theme.get('primary', '#ffffff')};
                    margin: 0;
                    padding: 0;
                }}
                """
            )
        
        # Apply sidebar styles if sidebar exists
        if hasattr(self, 'sidebar'):
            self.sidebar.setStyleSheet(
                f"""
                QFrame#walletSidebar {{
                    background-color: {theme.get('card', '#313244')};
                    border-right: 1px solid {theme.get('border', '#45475a')};
                }}
                """
            )
        
        # Apply title styles if title label exists
        if hasattr(self, 'title_label'):
            self.title_label.setStyleSheet(
                f"""
                QLabel#pageTitle {{
                    color: {theme.get('text', '#ffffff')};
                    font-size: 24px;
                    font-weight: bold;
                    margin: 10px 0;
                    padding: 0;
                }}
                """
            )
        
        # Apply button styles
        button_style = f"""
            QPushButton {{
                background-color: {0};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            
            QPushButton:hover {{
                background-color: {1};
            }}
            
            QPushButton:pressed {{
                background-color: {2};
            }}
        """.format(
            theme.get('primary', '#89b4fa'),
            theme.get('secondary', '#b4befe'),
            theme.get('accent', '#f5c2e7')
        )
        
        # Apply styles to all buttons
        for widget in self.findChildren(QPushButton):
            widget.setStyleSheet(button_style)
            
        # Apply tab widget styles
        tab_style = f"""
            QTabWidget::pane {{
                border: none;
                background: transparent;
            }}
            
            QTabBar::tab {{
                background: transparent;
                padding: 8px 16px;
                border: none;
                color: {theme.get('text_secondary', '#a6adc8')};
                font-weight: 500;
            }}
            
            QTabBar::tab:selected {{
                color: {theme.get('text', '#cdd6f4')};
                border-bottom: 2px solid {theme.get('primary', '#89b4fa')};
                font-weight: 600;
            }}
            
            QTabBar::tab:hover {{
                color: {theme.get('text', '#cdd6f4')};
                background-color: {theme.get('highlight', '#585b70')};
            }}
            
            QTabBar::tab:selected:hover {{
                background-color: transparent;
            }}
        """
        
        # Apply tab styles to all tab widgets
        for widget in self.findChildren(QTabWidget):
            widget.setStyleSheet(tab_style)
            
        # Apply table widget styles
        table_style = f"""
            QTableWidget {{
                background: {0};
                border: 1px solid {1};
                border-radius: 8px;
                gridline-color: {1};
                color: {2};
                font-size: 14px;
            }}
            
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {1};
            }}
            
            QTableWidget::item:selected {{
                background-color: {3};
                color: {4};
            }}
            
            QHeaderView::section {{
                background-color: {5};
                color: {6};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {1};
                font-weight: bold;
            }}
            
            QTableCornerButton::section {{
                background-color: {5};
                border: none;
                border-bottom: 1px solid {1};
                border-right: 1px solid {1};
            }}
        """.format(
            theme.get('surface', '#313244'),
            theme.get('border', '#45475a'),
            theme.get('text', '#cdd6f4'),
            theme.get('highlight', '#585b70'),
            theme.get('text', '#cdd6f4'),
            theme.get('background', '#1e1e2e'),
            theme.get('text_secondary', '#a6adc8')
        )
        
        # Apply table styles to all table widgets
        for widget in self.findChildren(QTableWidget):
            widget.setStyleSheet(table_style)
            
        # Apply scrollbar styles
        scrollbar_style = f"""
            QScrollBar:vertical {{
                border: none;
                background: {0};
                width: 10px;
                margin: 0px;
            }}
            
            QScrollBar::handle:vertical {{
                background: {1};
                min-height: 20px;
                border-radius: 5px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background: {2};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """.format(
            theme.get('surface', '#313244'),
            theme.get('highlight', '#585b70'),
            theme.get('accent', '#f5c2e7')
        )
        
        # Apply scrollbar styles to all scroll areas and scrollable widgets
        for widget in self.findChildren((QScrollArea, QScrollBar, QAbstractScrollArea)):
            widget.setStyleSheet(scrollbar_style)
        
        # Apply line edit styles
        line_edit_style = f"""
            QLineEdit {{
                background-color: {0};
                border: 1px solid {1};
                border-radius: 4px;
                padding: 8px 12px;
                color: {2};
                font-size: 14px;
                selection-background-color: {3};
            }}
            
            QLineEdit:focus {{
                border: 1px solid {4};
                outline: none;
            }}
            
            QLineEdit:disabled {{
                background-color: {5};
                color: {6};
            }}
        """.format(
            theme.get('surface', '#313244'),
            theme.get('border', '#45475a'),
            theme.get('text', '#cdd6f4'),
            theme.get('highlight', '#585b70'),
            theme.get('primary', '#89b4fa'),
            theme.get('background', '#1e1e2e'),
            theme.get('text_secondary', '#a6adc8')
        )
        
        # Apply line edit styles to all line edits
        for widget in self.findChildren(QLineEdit):
            widget.setStyleSheet(line_edit_style)
        
        # Apply combo box styles
        combo_style = f"""
            QComboBox {{
                background-color: {0};
                border: 1px solid {1};
                border-radius: 4px;
                padding: 8px 12px;
                color: {2};
                font-size: 14px;
                min-width: 100px;
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            
            QComboBox::down-arrow {{
                image: url(':/icons/arrow_down.png');
                width: 12px;
                height: 12px;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {0};
                color: {2};
                selection-background-color: {3};
                border: 1px solid {1};
                border-radius: 4px;
                padding: 4px;
            }}
        """.format(
            theme.get('surface', '#313244'),
            theme.get('border', '#45475a'),
            theme.get('text', '#cdd6f4'),
            theme.get('highlight', '#585b70')
        )
        
        # Apply combo box styles to all combo boxes
        for widget in self.findChildren(QComboBox):
            widget.setStyleSheet(combo_style)
            
        # Apply remaining styles using string formatting with theme colors
        remaining_style = """
            /* Main window and global styles */
            QMainWindow, QDialog, QWidget {{
                background-color: {background};
                color: {text};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            
            /* Labels */
            QLabel {{
                color: {text};
                font-size: 14px;
            }}
            
            QLabel#balanceLabel {{
                font-size: 24px;
                font-weight: bold;
                color: {primary};
            }}
            
            QLabel#secondaryLabel {{
                color: {text_secondary};
                font-size: 12px;
            }}
            
            /* Frames and cards */
            QFrame#card {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 16px;
            }}
            
            /* Tables */
            QTableWidget {{
                border: 1px solid {border};
                border-radius: 5px;
                gridline-color: {border};
                background-color: {surface};
                selection-background-color: {highlight};
                selection-color: {text};
            }}
            
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {border};
            }}
            
            QTableWidget::item:selected {{
                background-color: {highlight};
                color: {text};
            }}
            
            QHeaderView::section {{
                background-color: {background};
                color: {text_secondary};
                padding: 8px;
                border: none;
                border-right: 1px solid {border};
                border-bottom: 1px solid {border};
                font-weight: bold;
            }}
            
            /* Scrollbars */
            QScrollBar:vertical {{
                border: none;
                background: {background};
                width: 10px;
                margin: 0px;
            }}
            
            QScrollBar::handle:vertical {{
                background: {highlight};
                min-height: 20px;
                border-radius: 5px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background: {accent};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            
            /* Progress bars */
            QProgressBar {{
                border: 1px solid {border};
                border-radius: 4px;
                text-align: center;
                background: {background};
            }}
            
            QProgressBar::chunk {{
                background: {primary};
                border-radius: 2px;
            }}
            
            /* Tooltips */
            QToolTip {{
                background: {surface};
                color: {text};
                border: 1px solid {border};
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
            }}
            
            /* Status bar */
            QStatusBar {{
                background: {background};
                color: {text_secondary};
                border-top: 1px solid {border};
            }}
            
            /* Menu bar */
            QMenuBar {{
                background: {background};
                color: {text};
                border-bottom: 1px solid {border};
                padding: 4px 0;
            }}
            
            QMenuBar::item {{
                padding: 4px 8px;
                background: transparent;
                border-radius: 4px;
            }}
            
            QMenuBar::item:selected {{
                background: {highlight};
            }}
            
            QMenuBar::item:pressed {{
                background: {accent};
            }}
            
            /* Menus */
            QMenu {{
                background: {surface};
                border: 1px solid {border};
                padding: 4px;
                border-radius: 4px;
            }}
            
            QMenu::item {{
                padding: 6px 24px 6px 8px;
                margin: 2px 0;
                border-radius: 2px;
            }}
            
            QMenu::item:selected {{
                background: {highlight};
            }}
            
            QMenu::item:disabled {{
                color: {text_secondary};
            }}
            
            QMenu::separator {{
                height: 1px;
                background: {border};
                margin: 4px 0;
            }}
            
            QMenu::indicator {{
                width: 16px;
                height: 16px;
            }}
        """.format(
            background=theme.get('background', '#1e1e2e'),
            surface=theme.get('surface', '#313244'),
            text=theme.get('text', '#cdd6f4'),
            text_secondary=theme.get('text_secondary', '#a6adc8'),
            primary=theme.get('primary', '#89b4fa'),
            highlight=theme.get('highlight', '#585b70'),
            accent=theme.get('accent', '#f5c2e7'),
            border=theme.get('border', '#45475a')
        )
        
        # Apply remaining styles to the main window and all child widgets
        self.setStyleSheet(remaining_style)
        
        # Force update of all child widgets to ensure styles are applied
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
    
    # Event Handlers
    def _on_add_wallet(self):
        """Handle add wallet button click"""
        try:
            from gui.dialogs.wallet_creation_dialog import WalletCreationDialog
            
            dialog = WalletCreationDialog(self, self.wallet_manager, self.event_bus)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                wallet_data = dialog.get_wallet_data()
                if wallet_data:
                    # Create wallet via wallet manager
                    wallet = self.wallet_manager.create_wallet(
                        name=wallet_data.get("name"),
                        chain=wallet_data.get("chain", "ETH"),
                        wallet_type=wallet_data.get("type", "software")
                    )
                    if wallet:
                        self._update_wallet_list()
                        self._update_wallet_data()
                        QMessageBox.information(self, "Success", f"Wallet '{wallet_data.get('name')}' created successfully")
                    else:
                        QMessageBox.warning(self, "Error", "Failed to create wallet")
        except ImportError:
            # Fallback if dialog not available
            from PyQt6.QtWidgets import QInputDialog
            
            name, ok = QInputDialog.getText(self, "Add Wallet", "Wallet Name:")
            if ok and name:
                try:
                    wallet = self.wallet_manager.create_wallet(name=name, chain="ETH", wallet_type="software")
                    if wallet:
                        self._update_wallet_list()
                        self._update_wallet_data()
                        QMessageBox.information(self, "Success", f"Wallet '{name}' created")
                    else:
                        QMessageBox.warning(self, "Error", "Failed to create wallet")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to create wallet: {str(e)}")
        except Exception as e:
            logger.error(f"Error adding wallet: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add wallet: {str(e)}")
    
    def _on_wallet_selected(self, item):
        """Handle wallet selection"""
        self.selected_wallet = item.data(Qt.ItemDataRole.UserRole)
        self._update_wallet_details()
    
    def _on_chain_changed(self, index):
        """Handle chain selection change"""
        self.selected_chain = self.chain_selector.currentData()
        self._update_chain_data()
    
    def _on_refresh(self):
        """Handle refresh button click"""
        self._update_wallet_data()
    
    def _on_settings(self):
        """Handle settings button click"""
        try:
            from gui.dialogs.wallet_settings_dialog import WalletSettingsDialog
            
            dialog = WalletSettingsDialog(self, self.wallet_manager, self.event_bus)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                settings = dialog.get_settings()
                if settings:
                    # Apply settings via wallet manager
                    self.wallet_manager.update_settings(settings)
                    self._update_wallet_data()
                    QMessageBox.information(self, "Success", "Settings updated successfully")
        except ImportError:
            # Fallback: show basic settings
            from PyQt6.QtWidgets import QInputDialog
            
            chains = list(self.SUPPORTED_BLOCKCHAINS.keys())
            chain, ok = QInputDialog.getItem(self, "Wallet Settings", "Default Chain:", chains, 0, False)
            if ok:
                self.selected_chain = chain
                self._update_chain_data()
                QMessageBox.information(self, "Settings", f"Default chain set to {chain}")
        except Exception as e:
            logger.error(f"Error opening settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open settings: {str(e)}")
    
    def _on_max_clicked(self):
        """Handle max button click in send tab"""
        if self.selected_wallet and self.selected_chain in self.balances:
            balance = self.balances[self.selected_chain].get("balance", 0)
            self.send_amount.setText(str(balance))
    
    def _on_send_clicked(self):
        """Handle send button click"""
        try:
            if not self.selected_wallet:
                QMessageBox.warning(self, "No Wallet", "Please select a wallet first")
                return
            
            # Get send parameters
            asset = self.send_asset.currentData()
            amount_str = self.send_amount.text().strip()
            recipient = self.recipient.text().strip()
            
            if not asset or not amount_str or not recipient:
                QMessageBox.warning(self, "Invalid Input", "Please fill in all fields")
                return
            
            try:
                amount = float(amount_str)
            except ValueError:
                QMessageBox.warning(self, "Invalid Amount", "Please enter a valid amount")
                return
            
            # Validate recipient address format (basic check)
            if len(recipient) < 20:
                QMessageBox.warning(self, "Invalid Address", "Recipient address appears invalid")
                return
            
            # Confirm transaction
            reply = QMessageBox.question(
                self,
                "Confirm Transaction",
                f"Send {amount} {asset} to {recipient[:10]}...?\n\nThis action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Execute transaction via wallet manager
                try:
                    tx_result = self.wallet_manager.send_transaction(
                        wallet_id=self.selected_wallet.get("id"),
                        to_address=recipient,
                        amount=amount,
                        asset=asset,
                        chain=self.selected_chain
                    )
                    
                    if tx_result.get("success"):
                        tx_hash = tx_result.get("tx_hash", "unknown")
                        QMessageBox.information(
                            self,
                            "Transaction Sent",
                            f"Transaction submitted successfully!\n\nTX Hash: {tx_hash[:20]}..."
                        )
                        # Refresh wallet data
                        self._update_wallet_data()
                    else:
                        error_msg = tx_result.get("error", "Unknown error")
                        QMessageBox.critical(self, "Transaction Failed", f"Transaction failed: {error_msg}")
                except Exception as e:
                    logger.error(f"Error sending transaction: {e}")
                    QMessageBox.critical(self, "Error", f"Failed to send transaction: {str(e)}")
        except Exception as e:
            logger.error(f"Error in send transaction handler: {e}")
            QMessageBox.critical(self, "Error", f"Failed to process send request: {str(e)}")
    
    def _on_copy_address(self):
        """Handle copy address button click"""
        if self.selected_wallet:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.selected_wallet["address"])
            QMessageBox.information(self, "Copied", "Address copied to clipboard!")
    
    # Data Management
    def _connect_wallet_manager(self):
        """Connect to wallet manager events"""
        if self.event_bus:
            self.event_bus.subscribe("wallet.balance_updated", self._on_balance_updated)
            self.event_bus.subscribe("wallet.transaction", self._on_transaction)
            self.event_bus.subscribe("wallet.error", self._on_wallet_error)
    
    def _start_updates(self):
        """Start periodic updates"""
        # Create update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_wallet_data)
        self.update_timer.timeout.connect(self._check_redis_health)
        self.update_timer.start(30000)  # 30 seconds
        
        # Initial update
        self._update_wallet_data()
    
    def _check_redis_health(self):
        """Check Redis connection health periodically.
        
        Kingdom AI requires Redis to be healthy at all times.
        If the connection fails, the system must halt immediately.
        """
        try:
            if not hasattr(self, 'redis_conn') or not self.redis_conn.ping():
                error_msg = "Redis Quantum Nexus connection lost"
                logger.critical(error_msg)
                QMessageBox.critical(
                    self,
                    "Critical Error",
                    "Redis Quantum Nexus connection lost. Kingdom AI requires Redis to function. System will exit."
                )
                sys.exit(1)  # Halt system immediately as required
        except Exception as e:
            error_msg = f"Redis Quantum Nexus health check failed: {str(e)}"
            logger.critical(error_msg)
            QMessageBox.critical(
                self,
                "Critical Error",
                f"Redis Quantum Nexus health check failed: {str(e)}\n\nKingdom AI requires Redis to function. System will exit."
            )
            sys.exit(1)  # Halt system immediately as required
    
    def _update_wallet_data(self):
        """Update wallet data from wallet manager"""
        # First check Redis connection
        self._check_redis_health()
        
        try:
            # Get current wallets
            self.wallets = self.wallet_manager.get_wallets()
            
            # Get balances
            self.balances = self.wallet_manager.get_balances()
            
            # Get transactions
            self.transactions = self.wallet_manager.get_transactions()
            
            # Get prices
            self.prices = self.wallet_manager.get_prices()
            
            # Update UI
            self._update_wallet_list()
            self._update_wallet_details()
            self._update_balance_display()
            self._update_assets_table()
            self._update_transactions_table()
        except Exception as e:
            logger.error(f"Error updating wallet data: {str(e)}")
            # Only show an error message but don't exit if this is not Redis-related
            # Redis errors are handled in _check_redis_health
        
        # Update QR code
        self._update_qr_code()
        
        # Update send tab
        self._update_send_tab()
    
    def _update_wallet_details(self):
        """Update UI with selected wallet details"""
        if not self.selected_wallet:
            return
            
        # Update address
        self.address_label.setText(self.selected_wallet["address"])
        
        # Update QR code
        self._update_qr_code()
        
        # Update send tab
        self._update_send_tab()
    
    def _update_chain_data(self):
        """Update UI for selected chain"""
        # Update balance display
        self._update_balance_display()
        
        # Update assets table
        self._update_assets_table()
        
        # Update transactions
        self._update_transactions_table()
    
    def _update_balance_display(self):
        """Update the balance display"""
        if self.selected_chain in self.balances:
            balance = self.balances[self.selected_chain]
            self.total_balance_label.setText(f"${balance.get('usd_value', '0.00'):,.2f}")
            
            # Update 24h change
            change = balance.get('24h_change', 0)
            change_text = f"{change:+.2f}% (24h)"
            self.balance_change_label.setText(change_text)
            
            # Set color based on change
            color = "#50C878" if change >= 0 else "#FF6B6B"
            self.balance_change_label.setStyleSheet(f"color: {color};")
    
    def _update_assets_table(self):
        """Update the assets table from current balances and prices."""
        try:
            self.assets_table.setRowCount(0)
            row = 0
            for chain_id, balance_data in self.balances.items():
                if not isinstance(balance_data, dict):
                    continue
                chain_info = self.SUPPORTED_BLOCKCHAINS.get(chain_id, {})
                asset_name = chain_info.get("name", chain_id)
                bal = balance_data.get("balance", 0)
                price = self.prices.get(chain_id, 0)
                usd_value = balance_data.get("usd_value", bal * price if price else 0)
                change_24h = balance_data.get("change_24h", 0)

                self.assets_table.insertRow(row)
                self.assets_table.setItem(row, 0, QTableWidgetItem(asset_name))
                self.assets_table.setItem(row, 1, QTableWidgetItem(f"{bal:,.6f}"))
                self.assets_table.setItem(row, 2, QTableWidgetItem(f"${price:,.2f}" if price else "N/A"))
                self.assets_table.setItem(row, 3, QTableWidgetItem(f"${usd_value:,.2f}"))

                change_item = QTableWidgetItem(f"{change_24h:+.2f}%")
                color = QColor(SUCCESS_COLOR) if change_24h >= 0 else QColor(ERROR_COLOR)
                change_item.setForeground(color)
                self.assets_table.setItem(row, 4, change_item)
                row += 1
        except Exception as e:
            logger.error(f"Error updating assets table: {e}")

    def _update_transactions_table(self):
        """Update the transactions table from current transaction history."""
        try:
            self.transactions_table.setRowCount(0)
            sorted_txns = sorted(
                self.transactions,
                key=lambda t: t.get("timestamp", "") if isinstance(t, dict) else "",
                reverse=True,
            )
            for row, tx in enumerate(sorted_txns[:200]):
                if not isinstance(tx, dict):
                    continue
                self.transactions_table.insertRow(row)
                ts = tx.get("timestamp", "")
                if ts:
                    try:
                        ts = datetime.fromisoformat(str(ts)).strftime("%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        ts = str(ts)
                self.transactions_table.setItem(row, 0, QTableWidgetItem(ts))
                self.transactions_table.setItem(row, 1, QTableWidgetItem(tx.get("type", "unknown").capitalize()))
                self.transactions_table.setItem(row, 2, QTableWidgetItem(f"{tx.get('amount', 0):,.6f}"))

                status = tx.get("status", "pending")
                status_item = QTableWidgetItem(status.capitalize())
                if status == "confirmed":
                    status_item.setForeground(QColor(SUCCESS_COLOR))
                elif status == "failed":
                    status_item.setForeground(QColor(ERROR_COLOR))
                else:
                    status_item.setForeground(QColor(WARNING_COLOR))
                self.transactions_table.setItem(row, 3, status_item)

                details = tx.get("hash", tx.get("details", ""))
                if isinstance(details, str) and len(details) > 20:
                    details = details[:10] + "..." + details[-6:]
                self.transactions_table.setItem(row, 4, QTableWidgetItem(str(details)))
        except Exception as e:
            logger.error(f"Error updating transactions table: {e}")
    
    def _update_qr_code(self):
        """Update the QR code for the selected wallet"""
        if not self.selected_wallet:
            return
            
        try:
            # Generate QR code
            import qrcode
            from PIL import ImageQt
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(self.selected_wallet["address"])
            qr.make(fit=True)
            
            # Convert to QPixmap
            img = qr.make_image(fill_color="black", back_color="white")
            qimg = ImageQt.ImageQt(img)
            pixmap = QPixmap.fromImage(qimg)
            
            # Scale and set
            scaled = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.qr_code.setPixmap(scaled)
            
        except ImportError:
            self.qr_code.setText("QR Code requires qrcode and PIL packages")
    
    def _update_send_tab(self):
        """Update the send tab with current wallet data"""
        if not self.selected_wallet:
            return
            
        # Update asset selector
        self.send_asset.clear()
        for chain_id, balance in self.balances.items():
            if chain_id in self.SUPPORTED_BLOCKCHAINS:
                name = self.SUPPORTED_BLOCKCHAINS[chain_id]["name"]
                self.send_asset.addItem(name, chain_id)
    
    # Event Handlers
    def _on_balance_updated(self, event_data):
        """Handle balance update event"""
        chain_id = event_data.get("chain")
        if chain_id:
            self.balances[chain_id] = event_data
            self._update_balance_display()
    
    def _on_transaction(self, event_data):
        """Handle new transaction event"""
        self.transactions.append(event_data)
        self._update_transactions_table()
    
    def _on_wallet_error(self, event_data):
        """Handle wallet error event"""
        error_msg = event_data.get("message", "Unknown error")
        QMessageBox.critical(self, "Wallet Error", error_msg)
    
    # Theme Management
    def _load_theme(self, theme_name: str, variant: str = 'default') -> dict:
        """Load a theme by name and variant.
        
        Args:
            theme_name: Name of the theme to load (e.g., 'dark', 'light')
            variant: Theme variant (e.g., 'default', 'high_contrast')
            
        Returns:
            dict: Theme dictionary with styles and colors
            
        Raises:
            KeyError: If theme or variant is not found
            Exception: For other unexpected errors
        """
        # Define available themes with complete color schemes
        themes = {
            'dark': {
                'default': {
                    'primary': '#89b4fa',
                    'secondary': '#b4befe',
                    'accent': '#f5c2e7',
                    'background': '#1e1e2e',
                    'surface': '#313244',
                    'border': '#45475a',
                    'text': '#cdd6f4',
                    'text_secondary': '#a6adc8',
                    'highlight': '#585b70',
                    'success': '#a6e3a1',
                    'warning': '#f9e2af',
                    'error': '#f38ba8',
                    'info': '#89dceb'
                },
                'high_contrast': {
                    'primary': '#74c7ec',
                    'secondary': '#94e2d5',
                    'accent': '#f5c2e7',
                    'background': '#11111b',
                    'surface': '#181825',
                    'border': '#6c7086',
                    'text': '#ffffff',
                    'text_secondary': '#a6adc8',
                    'highlight': '#6c7086',
                    'success': '#a6e3a1',
                    'warning': '#f9e2af',
                    'error': '#f38ba8',
                    'info': '#89dceb'
                }
            },
            'light': {
                'default': {
                    'primary': '#1e66f5',
                    'secondary': '#1e66f5',
                    'accent': '#ea76cb',
                    'background': '#eff1f5',
                    'surface': '#e6e9ef',
                    'border': '#ccd0da',
                    'text': '#4c4f69',
                    'text_secondary': '#6c6f85',
                    'highlight': '#acb0be',
                    'success': '#40a02b',
                    'warning': '#df8e1d',
                    'error': '#d20f39',
                    'info': '#04a5e5'
                },
                'high_contrast': {
                    'primary': '#1e66f5',
                    'secondary': '#1e66f5',
                    'accent': '#ea76cb',
                    'background': '#ffffff',
                    'surface': '#e6e9ef',
                    'border': '#9ca0b0',
                    'text': '#4c4f69',
                    'text_secondary': '#5c5f77',
                    'highlight': '#8c8fa1',
                    'success': '#40a02b',
                    'warning': '#df8e1d',
                    'error': '#d20f39',
                    'info': '#04a5e5',
                    'accent_alt': '#ff5f5f',
                    'text_alt': '#ffffff',
                    'text_secondary_alt': '#b0b0b0',
                    'success_alt': '#00c853',
                    'warning_alt': '#ffab00',
                    'error_alt': '#ff3d00',
                    'border_alt': '#333333',
                    'highlight_alt': '#444444',
                    'card': '#121212'
                }
            }
        }

        try:
            # Get the theme colors
            theme = themes[theme_name][variant].copy()  # Create a copy to avoid modifying the original

            # Generate styles for this theme
            styles = f"""
                /* Main window */
                QMainWindow {{
                    background-color: {theme['background']};
                    color: {theme['text']};
                }}

                /* Buttons */
                QPushButton {{
                    background-color: {theme['primary']};
                    color: {theme['background']};
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: 500;
                }}

                QPushButton:hover {{
                    background-color: {theme['secondary']};
                }}

                QPushButton:pressed {{
                    background-color: {theme['accent']};
                }}

                /* Labels */
                QLabel {{
                    color: {theme['text']};
                }}

                /* Line edits */
                QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                QDateEdit, QTimeEdit, QDateTimeEdit, QDial, QSlider, QScrollBar {{
                    background-color: {theme['surface']};
                    color: {theme['text']};
                    border: 1px solid {theme['border']};
                    border-radius: 4px;
                    padding: 4px 8px;
                }}

                QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
                QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus,
                QDateTimeEdit:focus {{
                    border: 1px solid {theme['primary']};
                    box-shadow: 0 0 0 1px {theme['primary']}40;
                }}

                /* Scroll bars */
                QScrollBar:vertical {{
                    border: none;
                    background: {theme['surface']};
                    width: 12px;
                    margin: 0px 0px 0px 0px;
                }}

                QScrollBar::handle:vertical {{
                    background: {theme['highlight']};
                    min-height: 20px;
                    border-radius: 6px;
                }}

                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}

                /* Tabs */
                QTabBar::tab {{
                    background: {theme['surface']};
                    color: {theme['text_secondary']};
                    padding: 8px 16px;
                    border: 1px solid {theme['border']};
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                }}

                QTabBar::tab:selected, QTabBar::tab:hover {{
                    background: {theme['background']};
                    color: {theme['text']};
                    border-bottom: 2px solid {theme['primary']};
                }}

                QTabWidget::pane {{
                    border: 1px solid {theme['border']};
                    background: {theme['background']};
                }}

                /* Tables */
                QTableWidget {{
                    background: {theme['surface']};
                    gridline-color: {theme['border']};
                    border: 1px solid {theme['border']};
                    border-radius: 4px;
                }}

                QTableWidget::item {{
                    padding: 8px;
                    border-bottom: 1px solid {theme['border']};
                }}

                QTableWidget::item:selected {{
                    background: {theme['highlight']};
                    color: {theme['text']};
                }}

                QHeaderView::section {{
                    background: {theme['background']};
                    color: {theme['text_secondary']};
                    padding: 8px;
                    border: none;
                    border-bottom: 1px solid {theme['border']};
                }}

                /* Tooltips */
                QToolTip {{
                    background: {theme['surface']};
                    color: {theme['text']};
                    border: 1px solid {theme['border']};
                    padding: 4px 8px;
                    border-radius: 4px;
                }}

                /* Status bar */
                QStatusBar {{
                    background: {theme['surface']};
                    color: {theme['text_secondary']};
                    border-top: 1px solid {theme['border']};
                }}

                /* Menu bar */
                QMenuBar {{
                    background: {theme['background']};
                    color: {theme['text']};
                    border-bottom: 1px solid {theme['border']};
                }}

                QMenuBar::item:selected {{
                    background: {theme['highlight']};
                }}

                QMenu {{
                    background: {theme['surface']};
                    color: {theme['text']};
                    border: 1px solid {theme['border']};
                }}

                QMenu::item:selected {{
                    background: {theme['highlight']};
                }}

                /* Checkboxes and radio buttons */
                QCheckBox::indicator, QRadioButton::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 1px solid {theme['border']};
                    border-radius: 3px;
                    background: {theme['surface']};
                }}

                QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
                    background: {theme['primary']};
                    border: 1px solid {theme['primary']};
                }}

                /* Progress bar */
                QProgressBar {{
                    border: 1px solid {theme['border']};
                    border-radius: 3px;
                    text-align: center;
                    background: {theme['surface']};
                }}

                QProgressBar::chunk {{
                    background: {theme['primary']};
                    width: 10px;
                }}
            """

            # Save the theme and styles
            self.current_theme = theme.copy()
            self.current_theme['name'] = theme_name
            self.current_theme['variant'] = variant
            self.current_theme['styles'] = styles

            # Apply the theme
            self._apply_styles()
            
            # Save theme preference
            settings = QSettings("KingdomAI", "Wallet")
            settings.setValue("theme/name", theme_name)
            settings.setValue("theme/variant", variant)
            
            logger.info("Loaded theme: %s (%s)", theme_name, variant)
            return True
            
        except KeyError as e:
            logger.error("Theme or variant not found: %s (%s). Error: %s", 
                        theme_name, variant, str(e))
            return False
        except Exception as e:
            logger.error("Error loading theme: %s", str(e))
            return False

        return True

    def toggle_theme(self, theme_name=None):
        """Toggle between available themes or set a specific theme"""
        available_themes = ["dark", "light", "high_contrast"]

        if theme_name and theme_name in available_themes:
            self.current_theme = self._load_theme(theme_name)
        else:
            # Cycle to next theme
            current_theme = self.current_theme.get('name', 'dark')
            next_theme_idx = (available_themes.index(current_theme) + 1) % len(available_themes)
            self.current_theme = self._load_theme(available_themes[next_theme_idx])

        # Save theme preference
        settings = QSettings("KingdomAI", "Wallet")
        settings.setValue("theme", self.current_theme['name'])

        # Apply the new theme
        self._apply_styles()
        
        # Notify other components of theme change
        self.theme_changed.emit(self.current_theme['name'])
        
        logger.info(f"Theme changed to {self.current_theme['name']}")
        
        return self.current_theme['name']

    # Public API
    def set_wallet_manager(self, wallet_manager: WalletManager):
        """Set the wallet manager instance"""
        self.wallet_manager = wallet_manager
        self._update_wallet_data()
    
    def get_balances(self) -> Dict[str, float]:
        """Get current balances"""
        return self.balances
    
    def get_transactions(self) -> List[Dict]:
        """Get transaction history"""
        return self.transactions


if __name__ == "__main__":
    # For testing the wallet standalone
    import sys
    from PyQt6.QtWidgets import QApplication
    from core.event_bus import EventBus
    
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show wallet
    event_bus = EventBus()
    wallet = WalletQt(event_bus=event_bus)
    wallet.show()
    
    # Start event loop
    sys.exit(app.exec())
