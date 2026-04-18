"""
TradingQt - Main Trading Interface for Kingdom AI

This module provides the main trading interface for the Kingdom AI platform,
built with PyQt6 and integrated with Redis Quantum Nexus for real-time data.
"""

import sys
import logging
import json
from typing import Dict, Any, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTabWidget, QSplitter, QFrame, QStatusBar, QMenuBar,
    QMenu, QToolBar, QToolButton, QSizePolicy, QMessageBox
)
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPalette, QColor, QFont

# Local imports
from .utils.redis_manager import RedisManager, RedisConnectionError

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradingQt(QMainWindow):
    """Main trading window for Kingdom AI.
    
    This class implements the main trading interface with real-time
    market data, order management, and portfolio tracking.
    """
    
    # Signals
    market_data_updated = pyqtSignal(dict)  # Market data update signal
    order_update = pyqtSignal(dict)         # Order update signal
    position_update = pyqtSignal(dict)      # Position update signal
    
    def __init__(self, event_bus=None, parent=None):
        """Initialize the trading interface.
        
        Args:
            event_bus: Event bus for component communication
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Initialize properties
        self.event_bus = event_bus
        self.redis_manager = None
        self.connected = False
        self.market_data = {}
        self.positions = {}
        self.orders = {}
        self.watchlist = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
        self.current_symbol = "BTC/USDT"
        
        # Initialize UI
        self.setup_ui()
        
        # Connect to Redis
        self._connect_redis()
        
        # Set window properties
        self.setWindowTitle("Kingdom AI - Trading")
        self.setMinimumSize(1280, 800)
        self.showMaximized()
    
    def setup_ui(self) -> None:
        """Set up the UI components."""
        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create central widget with layout
        self.central_widget = QWidget(self)
        central_layout = QVBoxLayout(self.central_widget)
        central_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create main UI components
        self._create_ui_components()
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create toolbar
        self._create_toolbar()
        
        # Create status bar
        self._create_status_bar()
        
        # Apply dark theme
        self._apply_dark_theme()
        
        # Set the central widget - this was missing
        self.setCentralWidget(self.central_widget)
    
    def _create_ui_components(self) -> None:
        """Create the main UI components for the trading interface."""
        # Central layout should already exist
        central_layout = self.central_widget.layout()
        
        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # Left panel (watchlist, positions)
        left_panel = self._create_left_panel()
        left_panel.setMaximumWidth(300)
        
        # Center panel (charts, order entry)
        center_panel = self._create_center_panel()
        
        # Right panel (order book, trade history)
        right_panel = self._create_right_panel()
        right_panel.setMaximumWidth(300)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        
        # Set initial sizes
        splitter.setSizes([250, 500, 250])
        
        # Add splitter to central layout
        central_layout.addWidget(splitter)
    
    def _create_left_panel(self) -> QWidget:
        """Create the left panel with watchlist, positions, and orders."""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        
        # Watchlist
        watchlist_group = QFrame()
        watchlist_group.setFrameShape(QFrame.Shape.StyledPanel)
        watchlist_layout = QVBoxLayout(watchlist_group)
        watchlist_layout.addWidget(QLabel("<b>Watchlist</b>"))
        
        # Watchlist table (placeholder)
        self.watchlist_widget = QLabel("Watchlist will appear here")
        watchlist_layout.addWidget(self.watchlist_widget)
        
        # Positions
        positions_group = QFrame()
        positions_group.setFrameShape(QFrame.Shape.StyledPanel)
        positions_layout = QVBoxLayout(positions_group)
        positions_layout.addWidget(QLabel("<b>Positions</b>"))
        
        # Positions table (placeholder)
        self.positions_widget = QLabel("Open positions will appear here")
        positions_layout.addWidget(self.positions_widget)
        
        # Add widgets to layout
        layout.addWidget(watchlist_group, 1)
        layout.addWidget(positions_group, 2)
        
        return panel
    
    def _create_center_panel(self) -> QWidget:
        """Create the center panel with chart and order entry."""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        
        # Chart area
        chart_group = QFrame()
        chart_group.setFrameShape(QFrame.Shape.StyledPanel)
        chart_layout = QVBoxLayout(chart_group)
        
        # Chart controls
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1m", "5m", "15m", "1h", "4h", "1d", "1w"])
        controls_layout.addWidget(self.timeframe_combo)
        controls_layout.addStretch()
        
        # Chart widget (placeholder)
        self.chart_widget = QLabel("<center><h3>Price Chart</h3><p>Real-time price chart will appear here</p></center>")
        self.chart_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add to layout
        chart_layout.addLayout(controls_layout)
        chart_layout.addWidget(self.chart_widget, 1)
        
        # Order entry (placeholder)
        order_entry = QFrame()
        order_entry.setFrameShape(QFrame.Shape.StyledPanel)
        order_layout = QVBoxLayout(order_entry)
        order_layout.addWidget(QLabel("<b>New Order</b>"))
        order_layout.addWidget(QLabel("Order entry form will appear here"))
        
        # Add to main layout
        layout.addWidget(chart_group, 3)
        layout.addWidget(order_entry, 1)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """Create the right panel with order book and trade history."""
        panel = QTabWidget()
        
        # Order book tab
        order_book_tab = QWidget()
        order_book_layout = QVBoxLayout(order_book_tab)
        order_book_layout.addWidget(QLabel("<b>Order Book</b>"))
        self.order_book_widget = QLabel("Order book will appear here")
        order_book_layout.addWidget(self.order_book_widget)
        
        # Trade history tab
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.addWidget(QLabel("<b>Trade History</b>"))
        self.history_widget = QLabel("Trade history will appear here")
        history_layout.addWidget(self.history_widget)
        
        # Add tabs
        panel.addTab(order_book_tab, "Order Book")
        panel.addTab(history_tab, "Trade History")
        
        return panel
    
    def _create_menu_bar(self) -> None:
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_action = QAction("&New", self)
        new_action.setShortcut("Ctrl+N")
        file_menu.addAction(new_action)
        
        open_action = QAction("&Open", self)
        open_action.setShortcut("Ctrl+O")
        file_menu.addAction(open_action)
        
        save_action = QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self) -> None:
        """Create the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Add actions
        new_action = QAction(QIcon(":/icons/new.png"), "New", self)
        toolbar.addAction(new_action)
        
        save_action = QAction(QIcon(":/icons/save.png"), "Save", self)
        toolbar.addAction(save_action)
        
        toolbar.addSeparator()
        
        buy_action = QAction(QIcon(":/icons/buy.png"), "Buy", self)
        toolbar.addAction(buy_action)
        
        sell_action = QAction(QIcon(":/icons/sell.png"), "Sell", self)
        toolbar.addAction(sell_action)
    
    def _create_status_bar(self) -> None:
        """Create the status bar."""
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
    
    def _apply_dark_theme(self) -> None:
        """Apply a dark theme to the application."""
        # Set the style
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #e0e0e0;
            }
            QFrame {
                border: 1px solid #44475a;
                border-radius: 4px;
                padding: 5px;
            }
            QLabel {
                color: #e0e0e0;
            }
            QTabWidget::pane {
                border: 1px solid #44475a;
                border-radius: 4px;
                margin: 2px;
                padding: 2px;
            }
            QTabBar::tab {
                background: #2d2d3a;
                color: #e0e0e0;
                padding: 5px 10px;
                border: 1px solid #44475a;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #44475a;
                border-bottom: 2px solid #6272a4;
            }
            QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #282a36;
                color: #f8f8f2;
                border: 1px solid #44475a;
                padding: 3px;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #44475a;
                color: #f8f8f2;
                border: 1px solid #6272a4;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #6272a4;
            }
            QPushButton:pressed {
                background-color: #44475a;
            }
        """)
    
    def _connect_redis(self) -> None:
        """Connect to Redis Quantum Nexus - STRICT ENFORCEMENT
        
        According to system requirements, the application must halt and exit
        if Redis connection fails. No fallback is permitted.
        """
        try:
            self.redis_manager = RedisManager(
                host='localhost',
                port=6380,
                password='QuantumNexus2025',
                db=0
            )
            
            # Connect signals
            self.redis_manager.signals.connected.connect(self._on_redis_connected)
            self.redis_manager.signals.disconnected.connect(self._on_redis_disconnected)
            self.redis_manager.signals.message_received.connect(self._on_redis_message)
            
            # Connect to Redis - STRICT ENFORCEMENT
            if not self.redis_manager.connect():
                error_msg = "Failed to connect to Redis Quantum Nexus"
                self.logger.critical(error_msg)
                QMessageBox.critical(
                    self,
                    "Critical Redis Connection Error",
                    f"{error_msg}\n\nThe application will now exit."
                )
                sys.exit(1)
            
            # Subscribe to channels
            self.redis_manager.subscribe([
                "market_data",
                "order_updates",
                "position_updates",
                "account_updates"
            ])
            
        except RedisConnectionError as e:
            error_msg = f"Failed to connect to Redis Quantum Nexus: {str(e)}"
            self.logger.critical(error_msg)
            
            # Show critical error and exit
            QMessageBox.critical(
                self,
                "Critical Redis Connection Error",
                f"{error_msg}\n\nThe application will now exit."
            )
            sys.exit(1)
    
    def _on_redis_connected(self) -> None:
        """Handle successful Redis connection."""
        self.connected = True
        self.connection_status.setText("Connected")
        self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        self.statusBar().showMessage("Connected to Redis Quantum Nexus", 3000)
    
    def _on_redis_disconnected(self, message: str) -> None:
        """Handle Redis disconnection."""
        self.connected = False
        self.connection_status.setText("Disconnected")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        self.statusBar().showMessage(f"Disconnected from Redis: {message}", 5000)
    
    def _show_connection_error(self, error_message: str) -> None:
        """Display Redis connection error in the UI.
        
        Args:
            error_message: The error message to display
        """
        # Clear main layout if needed
        for i in reversed(range(self.central_widget.layout().count())):
            widget = self.central_widget.layout().itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        
        # Create error display layout
        error_layout = QVBoxLayout()
        
        # Create error icon and message
        error_icon = QLabel()
        error_icon.setPixmap(self.style().standardPixmap(QStyle.StandardPixmap.SP_MessageBoxCritical))
        error_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        error_title = QLabel("Redis Connection Error")
        error_title.setStyleSheet("font-size: 18px; font-weight: bold; color: red;")
        error_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        error_text = QLabel(f"Failed to connect to Redis Quantum Nexus:\n{error_message}\n\nTrading functionality is limited.")
        error_text.setWordWrap(True)
        error_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_text.setStyleSheet("font-size: 14px; margin: 10px;")
        
        # Add components to layout
        error_layout.addStretch(1)
        error_layout.addWidget(error_icon)
        error_layout.addWidget(error_title)
        error_layout.addWidget(error_text)
        
        # Add retry button
        retry_button = QPushButton("Retry Connection")
        retry_button.setMinimumWidth(150)
        retry_button.clicked.connect(self._retry_redis_connection)
        retry_button.setStyleSheet(
            "QPushButton {background-color: #44475a; color: white; padding: 8px 16px; border-radius: 4px;}"
            "QPushButton:hover {background-color: #6272a4;}"
        )
        
        # Add buttons for REAL trading actions
        button_layout = QHBoxLayout()
        
        buy_button = QPushButton("Buy")
        buy_button.clicked.connect(self._execute_buy_order)
        sell_button = QPushButton("Sell")
        sell_button.clicked.connect(self._execute_sell_order)
        
        button_layout.addWidget(buy_button)
        button_layout.addWidget(sell_button)
        
        error_layout.addLayout(button_layout)
        error_layout.addStretch(1)
        
        # Create container widget
        error_container = QWidget()
        error_container.setLayout(error_layout)
        error_container.setStyleSheet("background-color: #282a36; border-radius: 8px; margin: 20px;")
        
        # Add to central widget
        self.central_widget.layout().addWidget(error_container)
        
    def _retry_redis_connection(self) -> None:
        """Attempt to reconnect to Redis."""
        self.logger.info("Attempting to reconnect to Redis Quantum Nexus...")
        try:
            # Clear error display
            for i in reversed(range(self.central_widget.layout().count())):
                widget = self.central_widget.layout().itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)
                    
            # Recreate original UI components
            self._create_ui_components()
            
            # Try connecting to Redis again
            self._connect_redis()
            
        except Exception as e:
            self.logger.error(f"Failed to reconnect: {str(e)}")
            self._show_connection_error(str(e))
    
    def _on_redis_message(self, channel: str, message: Dict[str, Any]) -> None:
        """Handle incoming Redis messages."""
        try:
            if channel == "market_data":
                self._handle_market_data(message)
            elif channel == "order_updates":
                self._handle_order_update(message)
            elif channel == "position_updates":
                self._handle_position_update(message)
            elif channel == "account_updates":
                self._handle_account_update(message)
        except Exception as e:
            logger.error(f"Error processing {channel} message: {e}", exc_info=True)
    
    def _handle_market_data(self, data: Dict[str, Any]) -> None:
        """Handle incoming market data."""
        self.market_data[data['symbol']] = data
        self.market_data_updated.emit(data)
    
    def _handle_order_update(self, data: Dict[str, Any]) -> None:
        """Handle order updates."""
        self.orders[data['order_id']] = data
        self.order_update.emit(data)
    
    def _handle_position_update(self, data: Dict[str, Any]) -> None:
        """Handle position updates."""
        symbol = data['symbol']
        if data['size'] == 0 and symbol in self.positions:
            del self.positions[symbol]
        else:
            self.positions[symbol] = data
        self.position_update.emit(data)
    
    def _handle_account_update(self, data: Dict[str, Any]) -> None:
        """Handle account updates."""
        if 'balance' in data:
            self.balance_label.setText(f"Balance: ${data['balance']:,.2f}")
    
    def _show_about(self) -> None:
        """Show the about dialog."""
        QMessageBox.about(
            self,
            "About Kingdom AI Trading",
            "<h2>Kingdom AI Trading Platform</h2>"
            "<p>Version 1.0.0</p>"
            "<p>Advanced trading platform with AI-powered insights.</p>"
            "<p>&copy; 2025 Kingdom AI. All rights reserved.</p>"
        )
    
    def closeEvent(self, event) -> None:
        """Handle window close event."""
        if self.redis_manager:
            self.redis_manager.disconnect()
        event.accept()


def main():
    """Main entry point for the TradingQt application."""
    app = QApplication(sys.argv)
    
    # Set application information
    app.setApplicationName("Kingdom AI Trading")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Kingdom AI")
    
    # Create and show main window
    window = TradingQt()
    window.show()
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
