"""
Trading Window - Main Trading Interface for Kingdom AI

This module implements the main trading interface using PyQt6, providing
advanced trading capabilities with real-time market data, order management,
portfolio tracking, and AI-powered trading signals.
"""

import sys
import os
import logging
import asyncio
import getpass
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Constants for Redis connection
REDIS_PORT = 6380  # Mandatory port for Redis Quantum Nexus
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')  # Default to localhost

# Get Redis password from environment variable
_redis_password = os.getenv('REDIS_QUANTUM_NEXUS_PASSWORD')
if not _redis_password:
    logger.error("REDIS_QUANTUM_NEXUS_PASSWORD environment variable is not set")
    print("ERROR: REDIS_QUANTUM_NEXUS_PASSWORD environment variable is not set")
    sys.exit(1)
    
REDIS_PASSWORD = _redis_password

# PyQt6 Imports
from PyQt6.QtCore import Qt, QTimer, QSize, QThread, pyqtSignal, QObject, QMetaObject, Q_ARG, QEventLoop, pyqtSlot, QEvent
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMenuBar,
    QMenu, QToolBar, QStatusBar, QMessageBox, QDockWidget, QFormLayout,
    QGroupBox, QCheckBox, QProgressBar, QSizePolicy, QSpacerItem, QFrame,
    QStackedWidget, QToolButton, QFileDialog, QInputDialog, QScrollArea,
    QDialog, QDialogButtonBox, QTextEdit, QProgressDialog
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QColor, QPalette, QFont, QAction, QKeySequence,
    QIntValidator, QDoubleValidator, QFontMetrics, QPainter, QLinearGradient,
    QBrush, QPen, QPainterPath, QMouseEvent, QKeyEvent
)

# Application Imports
from core.event_bus import EventBus
from core.config_manager import ConfigManager
from core.redis_manager import RedisManager

# Local Widgets
from .widgets.market_data import MarketDataWidget
from .widgets.order_entry import OrderEntryWidget
from .widgets.positions import PositionWidget
from .widgets.orders import OrderWidget
from .widgets.chart import TradingChartWidget
from .widgets.order_book import OrderBookWidget
from .widgets.trade_history import TradeHistoryWidget
from .widgets.trading_console import TradingConsoleWidget
from .widgets.ai_signals import AISignalsWidget
from .widgets.risk_management import RiskManagementWidget
from .widgets.strategy_builder import StrategyBuilderWidget
from .widgets.backtesting import BacktestingWidget

# Utils
from ..utils.style import load_stylesheet
from ..utils.helpers import format_currency, format_percentage, format_timestamp

# Configure logger
logger = logging.getLogger(__name__)

class TradingSignals(QObject):
    """Signals for the trading window to communicate with worker threads."""
    
    # Market Data Signals
    market_data_updated = pyqtSignal(dict)  # Market data update
    order_book_updated = pyqtSignal(dict)   # Order book update
    trade_executed = pyqtSignal(dict)       # Trade executed
    
    # Order Signals
    order_created = pyqtSignal(dict)        # New order created
    order_updated = pyqtSignal(dict)        # Order status updated
    order_cancelled = pyqtSignal(dict)      # Order cancelled
    
    # Position Signals
    position_opened = pyqtSignal(dict)      # New position opened
    position_updated = pyqtSignal(dict)     # Position updated
    position_closed = pyqtSignal(dict)      # Position closed
    
    # Account Signals
    balance_updated = pyqtSignal(dict)      # Account balance updated
    
    # AI Signals
    ai_signal_generated = pyqtSignal(dict)  # New AI trading signal
    
    # System Signals
    connection_status_changed = pyqtSignal(bool)  # Connection status changed
    error_occurred = pyqtSignal(str)              # Error occurred

    # Event Handlers - Called from signals
    def _on_market_data_updated(self, data):
        """Handle market data updates from signals."""
        try:
            symbol = data.get('symbol', '')
            if symbol == self.current_symbol:
                self.chart_widget.update_market_data(data)
                self.market_data_widget.update_data(data)
        except Exception as e:
            logger.error(f"Error in market data update: {e}", exc_info=True)
    
    def _on_order_book_updated(self, data):
        """Handle order book updates from signals."""
        try:
            self.order_book_widget.update_order_book(data)
        except Exception as e:
            logger.error(f"Error in order book update: {e}", exc_info=True)
    
    def _on_trade_executed(self, data):
        """Handle trade execution updates from signals."""
        try:
            self.trade_history_widget.add_trade(data)
        except Exception as e:
            logger.error(f"Error in trade execution update: {e}", exc_info=True)
    
    def _on_order_created(self, order):
        """Handle new order creation from signals."""
        try:
            self.orders_widget.add_order(order)
            self.console_widget.add_message(f"Order created: {order['id']}", "info")
        except Exception as e:
            logger.error(f"Error in order created: {e}", exc_info=True)
    
    def _on_order_updated(self, order):
        """Handle order updates from signals."""
        try:
            self.orders_widget.update_order(order)
        except Exception as e:
            logger.error(f"Error in order update: {e}", exc_info=True)
    
    def _on_order_cancelled(self, order):
        """Handle order cancellation from signals."""
        try:
            self.orders_widget.remove_order(order['id'])
            self.console_widget.add_message(f"Order cancelled: {order['id']}", "warning")
        except Exception as e:
            logger.error(f"Error in order cancellation: {e}", exc_info=True)
    
    def _on_position_opened(self, position):
        """Handle new position opened from signals."""
        try:
            self.positions_widget.add_position(position)
            self.console_widget.add_message(f"Position opened: {position['symbol']}", "success")
        except Exception as e:
            logger.error(f"Error in position opened: {e}", exc_info=True)
    
    def _on_position_updated(self, position):
        """Handle position updates from signals."""
        try:
            self.positions_widget.update_position(position)
        except Exception as e:
            logger.error(f"Error in position update: {e}", exc_info=True)
    
    def _on_position_closed(self, position):
        """Handle position closed from signals."""
        try:
            self.positions_widget.remove_position(position['id'])
            self.console_widget.add_message(
                f"Position closed: {position['symbol']} "
                f"P&L: {position.get('realized_pnl', 0):.2f}", 
                "info"
            )
        except Exception as e:
            logger.error(f"Error in position closed: {e}", exc_info=True)
    
    def _on_balance_updated(self, balance):
        """Handle account balance updates from signals."""
        try:
            self.account_balance = balance
            self.balance_label.setText(f"Balance: {balance.get('total', 0):.2f} USDT")
        except Exception as e:
            logger.error(f"Error in balance update: {e}", exc_info=True)
    
    def _on_ai_signal_generated(self, signal):
        """Handle new AI trading signals from signals."""
        try:
            self.ai_signals_widget.add_signal(signal)
            
            # If auto-trading is enabled, execute the signal
            if self.auto_trading_enabled and signal.get('confidence', 0) >= 0.8:
                self._execute_ai_signal(signal)
                
        except Exception as e:
            logger.error(f"Error in AI signal handling: {e}", exc_info=True)
    
    def _on_connection_status_changed(self, connected):
        """Handle connection status changes from signals."""
        self.connected = connected
        status_text = "Connected" if connected else "Disconnected"
        status_color = "green" if connected else "red"
        self.connection_status_label.setText(f"Status: <font color='{status_color}'>{status_text}</font>")
        
        # Enable/disable trading controls based on connection status
        self._set_trading_enabled(connected)
        
        # Log connection status change
        if connected:
            self.console_widget.add_message("Connected to trading system", "success")
        else:
            self.console_widget.add_message("Disconnected from trading system", "error")
    
    def _on_error_occurred(self, error_msg):
        """Handle error messages from signals."""
        self.console_widget.add_message(f"Error: {error_msg}", "error")
        
        # Show critical errors in a message box
        if "critical" in error_msg.lower():
            QMessageBox.critical(
                self,
                "Critical Error",
                error_msg,
                QMessageBox.StandardButton.Ok
            )
    
    # Event Bus Handlers - Called from event bus
    def _handle_market_data_update(self, event_data):
        """Handle market data update from event bus."""
        self.signals.market_data_updated.emit(event_data)
    
    def _handle_order_book_update(self, event_data):
        """Handle order book update from event bus."""
        self.signals.order_book_updated.emit(event_data)
    
    def _handle_trades_update(self, event_data):
        """Handle trades update from event bus."""
        self.signals.trade_executed.emit(event_data)
    
    def _handle_order_created(self, event_data):
        """Handle order created from event bus."""
        self.signals.order_created.emit(event_data)
    
    def _handle_order_updated(self, event_data):
        """Handle order updated from event bus."""
        self.signals.order_updated.emit(event_data)
    
    def _handle_order_cancelled(self, event_data):
        """Handle order cancelled from event bus."""
        self.signals.order_cancelled.emit(event_data)
    
    def _handle_position_opened(self, event_data):
        """Handle position opened from event bus."""
        self.signals.position_opened.emit(event_data)
    
    def _handle_position_updated(self, event_data):
        """Handle position updated from event bus."""
        self.signals.position_updated.emit(event_data)
    
    def _handle_position_closed(self, event_data):
        """Handle position closed from event bus."""
        self.signals.position_closed.emit(event_data)
    
    def _handle_balance_updated(self, event_data):
        """Handle balance updated from event bus."""
        self.signals.balance_updated.emit(event_data)
    
    def _handle_ai_signal(self, event_data):
        """Handle AI signal from event bus."""
        self.signals.ai_signal_generated.emit(event_data)
    
    def _handle_connection_status(self, event_data):
        """Handle connection status from event bus."""
        self.signals.connection_status_changed.emit(event_data.get('connected', False))
    
    def _handle_system_error(self, event_data):
        """Handle system error from event bus."""
        error_msg = event_data.get('message', 'Unknown error')
        self.signals.error_occurred.emit(error_msg)


class TradingWindow(QMainWindow):
    """
    Main trading window for Kingdom AI Trading Platform.
    
    This window provides a comprehensive interface for both manual and automated trading,
    including real-time market data, order management, portfolio tracking, and AI-powered
    trading signals.
    """
    
    def __init__(self, parent=None):
        """Initialize the trading window."""
        super().__init__(parent)
        
        # Initialize properties
        self.parent = parent
        self.event_bus = EventBus.get_instance()
        self.config = ConfigManager.get_instance()
        self.redis_manager = None
        
        # Trading state
        self.connected = False
        self.initialized = False
        self.trading_enabled = False
        self.current_symbol = "BTC/USDT"
        self.watchlist = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
        self.timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        self.current_timeframe = "1h"
        
        # Data caches
        self.market_data = {}
        self.positions = {}
        self.orders = {}
        self.account_balance = {"total": 0.0, "available": 0.0, "in_use": 0.0}
        
        # Initialize UI
        self._init_ui()
        
        # Initialize signals
        self._init_signals()
        
        # Connect to trading systems
        self._connect_to_redis()
        
        # Start update timers
        self._init_timers()
        
        # Set window properties
        self.setWindowTitle("Kingdom AI - Trading")
        self.setMinimumSize(1280, 800)
        self.showMaximized()
    
    def _init_ui(self):
        """Initialize the user interface."""
        # Set style sheet
        self.setStyleSheet(load_stylesheet("trading"))
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        
        # Create main splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)
        
        # Initialize panels
        self._init_left_panel()
        self._init_center_panel()
        self._init_right_panel()
        
        # Set initial sizes
        self.main_splitter.setSizes([250, 700, 350])
        
        # Initialize other UI components
        self._init_menu_bar()
        self._init_toolbar()
        self._init_status_bar()
        self._init_dock_widgets()
    
    def _init_left_panel(self):
        """Initialize the left panel with watchlist, positions, and orders."""
        # Create left panel container
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(2, 2, 2, 2)
        left_layout.setSpacing(5)
        
        # Watchlist widget
        self.watchlist_widget = MarketDataWidget(self.watchlist, self)
        left_layout.addWidget(self.watchlist_widget, 1)
        
        # Positions widget
        self.positions_widget = PositionsWidget(self)
        left_layout.addWidget(self.positions_widget, 2)
        
        # Orders widget
        self.orders_widget = OrdersWidget(self)
        left_layout.addWidget(self.orders_widget, 2)
        
        # Add to main splitter
        self.main_splitter.addWidget(left_panel)
    
    def _init_center_panel(self):
        """Initialize the center panel with chart and order entry."""
        # Create center panel container
        center_panel = QWidget()
        center_panel.setObjectName("centerPanel")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(2, 2, 2, 2)
        center_layout.setSpacing(5)
        
        # Chart widget
        self.chart_widget = TradingChartWidget(self)
        center_layout.addWidget(self.chart_widget, 3)
        
        # Order entry widget
        self.order_entry_widget = OrderEntryWidget(self)
        center_layout.addWidget(self.order_entry_widget, 1)
        
        # Add to main splitter
        self.main_splitter.addWidget(center_panel)
    
    def _init_right_panel(self):
        """Initialize the right panel with order book, trade history, and AI signals."""
        # Create right panel container with tabs
        right_panel = QTabWidget()
        right_panel.setObjectName("rightPanel")
        
        # Order book tab
        self.order_book_widget = OrderBookWidget(self)
        right_panel.addTab(self.order_book_widget, "Order Book")
        
        # Trade history tab
        self.trade_history_widget = TradeHistoryWidget(self)
        right_panel.addTab(self.trade_history_widget, "Trades")
        
        # AI signals tab
        self.ai_signals_widget = AISignalsWidget(self)
        right_panel.addTab(self.ai_signals_widget, "AI Signals")
        
        # Add to main splitter
        self.main_splitter.addWidget(right_panel)
    
    def _init_dock_widgets(self):
        """Initialize dockable widgets."""
        # Console dock
        self.console_dock = QDockWidget("Trading Console", self)
        self.console_dock.setObjectName("consoleDock")
        self.console_widget = TradingConsoleWidget(self)
        self.console_dock.setWidget(self.console_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)
        
        # Risk management dock
        self.risk_dock = QDockWidget("Risk Management", self)
        self.risk_dock.setObjectName("riskDock")
        self.risk_widget = RiskManagementWidget(self)
        self.risk_dock.setWidget(self.risk_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.risk_dock)
        
        # Strategy builder dock (initially hidden)
        self.strategy_dock = QDockWidget("Strategy Builder", self)
        self.strategy_dock.setObjectName("strategyDock")
        self.strategy_widget = StrategyBuilderWidget(self)
        self.strategy_dock.setWidget(self.strategy_widget)
        self.strategy_dock.setVisible(False)
        
        # Backtesting dock (initially hidden)
        self.backtest_dock = QDockWidget("Backtesting", self)
        self.backtest_dock.setObjectName("backtestDock")
        self.backtest_widget = BacktestingWidget(self)
        self.backtest_dock.setWidget(self.backtest_widget)
        self.backtest_dock.setVisible(False)

        # Policy: strict single-window UI. Prevent all dock float/move pop-outs.
        for _dock in (self.console_dock, self.risk_dock, self.strategy_dock, self.backtest_dock):
            try:
                feats = _dock.features()
                feats = feats & ~QDockWidget.DockWidgetFeature.DockWidgetFloatable
                feats = feats & ~QDockWidget.DockWidgetFeature.DockWidgetMovable
                _dock.setFeatures(feats)
            except Exception:
                try:
                    _dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
                except Exception:
                    pass
            try:
                _dock.setFloating(False)
            except Exception:
                pass
    
    def _init_menu_bar(self):
        """Initialize the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_strategy_action = QAction("&New Strategy", self)
        new_strategy_action.setShortcut("Ctrl+N")
        new_strategy_action.triggered.connect(self._new_strategy)
        file_menu.addAction(new_strategy_action)
        
        load_strategy_action = QAction("&Load Strategy...", self)
        load_strategy_action.setShortcut("Ctrl+O")
        load_strategy_action.triggered.connect(self._load_strategy)
        file_menu.addAction(load_strategy_action)
        
        save_strategy_action = QAction("&Save Strategy", self)
        save_strategy_action.setShortcut("Ctrl+S")
        save_strategy_action.triggered.connect(self._save_strategy)
        file_menu.addAction(save_strategy_action)
        
        file_menu.addSeparator()
        
        export_data_action = QAction("&Export Data...", self)
        export_data_action.triggered.connect(self._export_data)
        file_menu.addAction(export_data_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        show_console_action = QAction("Show &Console", self, checkable=True)
        show_console_action.setChecked(True)
        show_console_action.triggered.connect(lambda: self.console_dock.setVisible(show_console_action.isChecked()))
        view_menu.addAction(show_console_action)
        
        show_risk_action = QAction("Show &Risk Management", self, checkable=True)
        show_risk_action.setChecked(True)
        show_risk_action.triggered.connect(lambda: self.risk_dock.setVisible(show_risk_action.isChecked()))
        view_menu.addAction(show_risk_action)
        
        show_strategy_action = QAction("Show Strategy &Builder", self, checkable=True)
        show_strategy_action.triggered.connect(lambda: self.strategy_dock.setVisible(show_strategy_action.isChecked()))
        view_menu.addAction(show_strategy_action)
        
        show_backtest_action = QAction("Show &Backtesting", self, checkable=True)
        show_backtest_action.triggered.connect(lambda: self.backtest_dock.setVisible(show_backtest_action.isChecked()))
        view_menu.addAction(show_backtest_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        preferences_action = QAction("&Preferences...", self)
        preferences_action.triggered.connect(self._show_preferences)
        tools_menu.addAction(preferences_action)
        
        api_keys_action = QAction("&API Keys Management...", self)
        api_keys_action.triggered.connect(self._manage_api_keys)
        tools_menu.addAction(api_keys_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        documentation_action = QAction("&Documentation", self)
        documentation_action.triggered.connect(self._show_documentation)
        help_menu.addAction(documentation_action)
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _init_toolbar(self):
        """Initialize the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Connect button
        self.connect_action = QAction(QIcon(":/icons/connect.png"), "Connect", self)
        self.connect_action.triggered.connect(self._toggle_connection)
        toolbar.addAction(self.connect_action)
        
        # Buy/Sell buttons
        toolbar.addSeparator()
        
        self.buy_market_action = QAction(QIcon(":/icons/buy.png"), "Buy Market", self)
        self.buy_market_action.triggered.connect(lambda: self._show_order_dialog("buy", "market"))
        toolbar.addAction(self.buy_market_action)
        
        self.sell_market_action = QAction(QIcon(":/icons/sell.png"), "Sell Market", self)
        self.sell_market_action.triggered.connect(lambda: self._show_order_dialog("sell", "market"))
        toolbar.addAction(self.sell_market_action)
        
        # Trading mode selector
        toolbar.addSeparator()
        self.trading_mode_combo = QComboBox()
        self.trading_mode_combo.addItems(["Manual Trading", "AI-Assisted", "Fully Automated"])
        self.trading_mode_combo.currentIndexChanged.connect(self._on_trading_mode_changed)
        toolbar.addWidget(QLabel("Mode: "))
        toolbar.addWidget(self.trading_mode_combo)
        
        # Strategy selector
        toolbar.addSeparator()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["Trend Following", "Mean Reversion", "Breakout", "Custom..."])
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        toolbar.addWidget(QLabel("Strategy: "))
        toolbar.addWidget(self.strategy_combo)
    
    def _init_status_bar(self):
        """Initialize the status bar."""
        status = QStatusBar()
        self.setStatusBar(status)
        
        # Connection status
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        status.addPermanentWidget(QLabel("Status: "))
        status.addPermanentWidget(self.connection_status)
        
        # Balance
        self.balance_label = QLabel("Balance: $0.00")
        status.addPermanentWidget(self.balance_label)
        
        # PnL
        self.pnl_label = QLabel("PnL: $0.00 (0.00%)")
        status.addPermanentWidget(self.pnl_label)
        
        # Last update
        self.last_update_label = QLabel("Last update: Never")
        status.addPermanentWidget(self.last_update_label)
    
    def _init_signals(self):
        """Initialize signal connections and event bus handlers."""
        # Create signals object
        self.signals = TradingSignals()
        
        # Connect market data signals
        self.signals.market_data_updated.connect(self._on_market_data_updated)
        self.signals.order_book_updated.connect(self._on_order_book_updated)
        self.signals.trade_executed.connect(self._on_trade_executed)
        
        # Connect order signals
        self.signals.order_created.connect(self._on_order_created)
        self.signals.order_updated.connect(self._on_order_updated)
        self.signals.order_cancelled.connect(self._on_order_cancelled)
        
        # Connect position signals
        self.signals.position_opened.connect(self._on_position_opened)
        self.signals.position_updated.connect(self._on_position_updated)
        self.signals.position_closed.connect(self._on_position_closed)
        
        # Connect account signals
        self.signals.balance_updated.connect(self._on_balance_updated)
        
        # Connect AI signals
        self.signals.ai_signal_generated.connect(self._on_ai_signal_generated)
        
        # Connect system signals
        self.signals.connection_status_changed.connect(self._on_connection_status_changed)
        self.signals.error_occurred.connect(self._on_error_occurred)
        
        # Initialize event bus handlers
        self._init_event_bus_handlers()
    
    def _init_event_bus_handlers(self):
        """Initialize event bus message handlers."""
        if not self.event_bus:
            logger.error("Event bus not available for initializing handlers")
            return
            
        try:
            # Market data events
            self.event_bus.subscribe("market_data.update", self._handle_market_data_update)
            self.event_bus.subscribe("order_book.update", self._handle_order_book_update)
            self.event_bus.subscribe("trades.update", self._handle_trades_update)
            
            # Order events
            self.event_bus.subscribe("order.created", self._handle_order_created)
            self.event_bus.subscribe("order.updated", self._handle_order_updated)
            self.event_bus.subscribe("order.cancelled", self._handle_order_cancelled)
            
            # Position events
            self.event_bus.subscribe("position.opened", self._handle_position_opened)
            self.event_bus.subscribe("position.updated", self._handle_position_updated)
            self.event_bus.subscribe("position.closed", self._handle_position_closed)
            
            # Account events
            self.event_bus.subscribe("account.balance_updated", self._handle_balance_updated)
            
            # AI signals
            self.event_bus.subscribe("ai.signal_generated", self._handle_ai_signal)
            
            # System events
            self.event_bus.subscribe("system.connection_status", self._handle_connection_status)
            self.event_bus.subscribe("system.error", self._handle_system_error)
            
            logger.info("Event bus handlers initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize event bus handlers: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.signals.error_occurred.emit(error_msg)
    
    def _init_timers(self):
        """Initialize timers for periodic updates."""
        # Market data update timer
        self.market_data_timer = QTimer(self)
        self.market_data_timer.timeout.connect(self._update_market_data)
        self.market_data_timer.setInterval(1000)  # 1 second
        
        # Account update timer
        self.account_update_timer = QTimer(self)
        self.account_update_timer.timeout.connect(self._update_account_info)
        self.account_update_timer.setInterval(5000)  # 5 seconds
        
        # UI update timer
        self.ui_update_timer = QTimer(self)
        self.ui_update_timer.timeout.connect(self._update_ui)
        self.ui_update_timer.setInterval(500)  # SOTA 2026 FIX: 500ms saves CPU vs 100ms

        self._sync_update_timers()

    def _should_update_timers_run(self) -> bool:
        if not getattr(self, '_timers_enabled', True):
            return False
        if not self.isVisible():
            return False
        try:
            if self.isMinimized():
                return False
        except Exception:
            pass
        return True

    def _sync_update_timers(self):
        try:
            should_run = self._should_update_timers_run()

            timers = (
                ('market_data_timer', 1000),
                ('account_update_timer', 5000),
                ('ui_update_timer', 500),
            )

            for timer_attr, default_interval in timers:
                timer = getattr(self, timer_attr, None)
                if timer is None:
                    continue

                if should_run:
                    if not timer.isActive():
                        interval = default_interval
                        try:
                            interval = timer.interval() or default_interval
                        except Exception:
                            pass
                        timer.start(interval)
                else:
                    if timer.isActive():
                        timer.stop()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_update_timers()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_update_timers()

    def changeEvent(self, event):
        super().changeEvent(event)
        try:
            if event.type() == QEvent.Type.WindowStateChange:
                self._sync_update_timers()
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            self._timers_enabled = False
            self._sync_update_timers()
        except Exception:
            pass
        super().closeEvent(event)
    
    def _connect_to_redis(self):
        """
        Connect to Redis Quantum Nexus with strict requirements:
        - Mandatory port 6380
        - Mandatory password 'QuantumNexus2025'
        - No fallback allowed
        - System will halt on connection failure
        """
        try:
            # Log connection attempt
            self.console_widget.add_message("Connecting to Redis Quantum Nexus on port 6380...", "info")
            
            # Verify Redis connection details
            logger.info(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")
                
            # Initialize Redis manager with mandatory settings
            self.redis_manager = RedisManager(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                db=0,
                socket_timeout=10.0,  # Increased timeout for initial connection
                socket_connect_timeout=10.0,
                retry_on_timeout=False,  # No retries on timeout
                decode_responses=True,
                health_check_interval=30,  # Check connection health
                client_name=f"trading_ui_{os.getpid()}"  # Identify this client
            )
            
            # Test connection with timeout
            try:
                if not self.redis_manager.ping():
                    raise ConnectionError("Redis ping failed")
                    
                # Connection successful
                self.connected = True
                self.signals.connection_status_changed.emit(True)
                self.console_widget.add_message("✓ Connected to Redis Quantum Nexus on port 6380", "success")
                
                # Subscribe to channels
                self._subscribe_to_redis_channels()
                
                # Initialize trading components
                self._initialize_trading_components()
                
            except Exception as e:
                raise ConnectionError(f"Failed to verify Redis connection: {str(e)}") from e
                
        except Exception as e:
            error_msg = f"CRITICAL: Failed to connect to Redis Quantum Nexus: {str(e)}\n"
            error_msg += f"The system requires Redis Quantum Nexus running on {REDIS_HOST}:{REDIS_PORT} with proper authentication.\n"
            error_msg += "Please ensure Redis is running with the correct configuration.\n"
            error_msg += f"Current configuration - Host: {REDIS_HOST}, Port: {REDIS_PORT}"
            
            # Log critical error
            logger.critical(error_msg)
            self.console_widget.add_message(error_msg, "critical")
            self.signals.error_occurred.emit(error_msg)
            
            # Show critical error message box
            QMessageBox.critical(
                self,
                "Critical Error - Redis Connection Failed",
                error_msg,
                QMessageBox.StandardButton.Ok
            )
            
            # CRITICAL FIX: DO NOT SHUTDOWN - Log error and continue running
            # The system must stay operational even if Redis connection fails
            logger.critical("⚠️ Trading window will operate in degraded mode without Redis")
            self.console_widget.add_message("⚠️ Operating in degraded mode - some features unavailable", "warning")
            self.connected = False
            self.signals.connection_status_changed.emit(False)
    
    def _shutdown_application(self):
        """DEPRECATED: No longer shuts down application.
        
        This method is kept for compatibility but does nothing.
        The system must never shutdown due to subsystem failures.
        """
        logger.warning("_shutdown_application called but ignored - system must stay running")
        self.console_widget.add_message("⚠️ Critical error detected but system continues running", "warning")
    
    def _subscribe_to_redis_channels(self):
        """Subscribe to Redis channels for real-time updates."""
        if not self.redis_manager:
            return
        
        # Subscribe to market data channels
        self.redis_manager.subscribe("market_data:*", self._on_market_data_message)
        self.redis_manager.subscribe("order_book:*", self._on_order_book_message)
        self.redis_manager.subscribe("trades:*", self._on_trade_message)
        
        # Subscribe to order updates
        self.redis_manager.subscribe("orders:*", self._on_order_update_message)
        
        # Subscribe to position updates
        self.redis_manager.subscribe("positions:*", self._on_position_update_message)
        
        # Subscribe to account updates
        self.redis_manager.subscribe("account:*", self._on_account_update_message)
        
        # Subscribe to AI signals
        self.redis_manager.subscribe("ai_signals:*", self._on_ai_signal_message)
        
        self.console_widget.add_message("Subscribed to Redis channels", "info")
