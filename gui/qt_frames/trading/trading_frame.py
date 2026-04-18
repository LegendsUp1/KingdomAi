"""
Trading Frame for Kingdom AI

This module provides the Qt-based trading interface that integrates with the
trading component and displays trading information.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLineEdit, QDoubleSpinBox, QMessageBox, QTabWidget, QFormLayout,
    QGroupBox, QScrollArea, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QFont, QPalette

from core.base_component_v2 import BaseComponentV2
from core.event_bus import EventBus

# Configure logger
logger = logging.getLogger(__name__)

class TradingFrame(QWidget):
    """Trading frame for the Kingdom AI GUI."""
    
    # Signals for cross-thread communication
    order_updated = pyqtSignal(dict)
    position_updated = pyqtSignal(dict)
    market_data_updated = pyqtSignal(dict)
    trading_error = pyqtSignal(str)
    
    def __init__(self, parent: Optional[QWidget] = None, 
                 event_bus: Optional[EventBus] = None):
        """Initialize the trading frame.
        
        Args:
            parent: Parent widget
            event_bus: Event bus for communication
        """
        super().__init__(parent)
        self.event_bus = event_bus
        self.trading_component = None
        self.initialized = False
        
        # UI state
        self.symbol = "BTC/USD"
        self.order_type = "market"
        self.side = "buy"
        self.quantity = 0.1
        self.price = 0.0
        
        # Initialize UI
        self.init_ui()
        
        # Connect signals
        self.order_updated.connect(self.update_order_display)
        self.position_updated.connect(self.update_position_display)
        self.market_data_updated.connect(self.update_market_data_display)
        self.trading_error.connect(self.show_error)
        
        # Start initialization
        self.initialize_component()
    
    def init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Create a splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        
        # Top section: Order form and positions
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        
        # Left: Order form
        order_group = self._create_order_group()
        top_layout.addWidget(order_group, 1)
        
        # Right: Positions
        positions_group = self._create_positions_group()
        top_layout.addWidget(positions_group, 1)
        
        # Add top section to splitter
        splitter.addWidget(top_widget)
        
        # Bottom section: Orders and market data
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        
        # Left: Orders
        orders_group = self._create_orders_group()
        bottom_layout.addWidget(orders_group, 1)
        
        # Right: Market data
        market_data_group = self._create_market_data_group()
        bottom_layout.addWidget(market_data_group, 1)
        
        # Add bottom section to splitter
        splitter.addWidget(bottom_widget)
        
        # Set initial sizes for the splitter
        splitter.setSizes([300, 200])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QLabel("Initializing trading component...")
        self.status_bar.setStyleSheet("background-color: #333; color: #fff; padding: 3px;")
        main_layout.addWidget(self.status_bar)
    
    def _create_order_group(self) -> QGroupBox:
        """Create the order form group."""
        group = QGroupBox("New Order")
        layout = QFormLayout()
        
        # Symbol
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "ADA/USD"])
        self.symbol_combo.currentTextChanged.connect(self._on_symbol_changed)
        layout.addRow("Symbol:", self.symbol_combo)
        
        # Order Type
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["market", "limit", "stop", "stop_limit"])
        self.order_type_combo.currentTextChanged.connect(self._on_order_type_changed)
        layout.addRow("Order Type:", self.order_type_combo)
        
        # Side
        self.side_combo = QComboBox()
        self.side_combo.addItems(["buy", "sell"])
        self.side_combo.currentTextChanged.connect(self._on_side_changed)
        layout.addRow("Side:", self.side_combo)
        
        # Quantity
        self.quantity_spin = QDoubleSpinBox()
        self.quantity_spin.setRange(0.0001, 1000.0)
        self.quantity_spin.setDecimals(8)
        self.quantity_spin.setValue(0.1)
        self.quantity_spin.valueChanged.connect(self._on_quantity_changed)
        layout.addRow("Quantity:", self.quantity_spin)
        
        # Price (initially hidden for market orders)
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.00000001, 1000000.0)
        self.price_spin.setDecimals(8)
        self.price_spin.setValue(0.0)
        self.price_spin.valueChanged.connect(self._on_price_changed)
        self.price_label = QLabel("Price:")
        layout.addRow(self.price_label, self.price_spin)
        self._update_price_visibility()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.buy_button = QPushButton("Buy")
        self.buy_button.setStyleSheet("background-color: #4CAF50; color: white;")
        self.buy_button.clicked.connect(self._on_buy_clicked)
        
        self.sell_button = QPushButton("Sell")
        self.sell_button.setStyleSheet("background-color: #F44336; color: white;")
        self.sell_button.clicked.connect(self._on_sell_clicked)
        
        button_layout.addWidget(self.buy_button)
        button_layout.addWidget(self.sell_button)
        
        layout.addRow(button_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_positions_group(self) -> QGroupBox:
        """Create the positions group."""
        group = QGroupBox("Positions")
        layout = QVBoxLayout()
        
        # Positions table
        self.positions_table = QTableWidget(0, 5)
        self.positions_table.setHorizontalHeaderLabels(["Symbol", "Size", "Entry", "Mark", "PnL"])
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.positions_table.verticalHeader().setVisible(False)
        self.positions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.positions_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.positions_table)
        
        # Close position button
        self.close_position_button = QPushButton("Close Position")
        self.close_position_button.setEnabled(False)
        self.close_position_button.clicked.connect(self._on_close_position_clicked)
        layout.addWidget(self.close_position_button)
        
        group.setLayout(layout)
        return group
    
    def _create_orders_group(self) -> QGroupBox:
        """Create the orders group."""
        group = QGroupBox("Orders")
        layout = QVBoxLayout()
        
        # Orders table
        self.orders_table = QTableWidget(0, 7)
        self.orders_table.setHorizontalHeaderLabels(["ID", "Symbol", "Type", "Side", "Qty", "Price", "Status"])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.orders_table.verticalHeader().setVisible(False)
        self.orders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.orders_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.orders_table.itemSelectionChanged.connect(self._on_order_selection_changed)
        
        layout.addWidget(self.orders_table)
        
        # Order actions
        button_layout = QHBoxLayout()
        
        self.cancel_order_button = QPushButton("Cancel Order")
        self.cancel_order_button.setEnabled(False)
        self.cancel_order_button.clicked.connect(self._on_cancel_order_clicked)
        
        self.modify_order_button = QPushButton("Modify Order")
        self.modify_order_button.setEnabled(False)
        self.modify_order_button.clicked.connect(self._on_modify_order_clicked)
        
        button_layout.addWidget(self.cancel_order_button)
        button_layout.addWidget(self.modify_order_button)
        
        layout.addLayout(button_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_market_data_group(self) -> QGroupBox:
        """Create the market data group."""
        group = QGroupBox("Market Data")
        layout = QVBoxLayout()
        
        # Symbol selector
        self.market_data_symbol = QComboBox()
        self.market_data_symbol.addItems(["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "ADA/USD"])
        self.market_data_symbol.currentTextChanged.connect(self._on_market_data_symbol_changed)
        layout.addWidget(self.market_data_symbol)
        
        # Market data display
        self.market_data_display = QTableWidget(0, 2)
        self.market_data_display.setHorizontalHeaderLabels(["Field", "Value"])
        self.market_data_display.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.market_data_display.verticalHeader().setVisible(False)
        self.market_data_display.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Add some default market data fields
        self.market_data_fields = [
            "Last Price", "Bid", "Ask", "24h High", "24h Low", 
            "24h Volume", "24h Change", "24h Change %"
        ]
        
        self.market_data_display.setRowCount(len(self.market_data_fields))
        for i, field in enumerate(self.market_data_fields):
            self.market_data_display.setItem(i, 0, QTableWidgetItem(field))
            self.market_data_display.setItem(i, 1, QTableWidgetItem("-"))
        
        layout.addWidget(self.market_data_display)
        
        # Chart placeholder
        self.chart_label = QLabel("<center><i>Price chart will be displayed here</i></center>")
        self.chart_label.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.chart_label.setMinimumHeight(150)
        layout.addWidget(self.chart_label)
        
        group.setLayout(layout)
        return group
    
    def initialize_component(self):
        """Initialize the trading component asynchronously."""
        # This would be called to initialize the trading component
        # In a real implementation, this would connect to the trading API
        # and set up the necessary event handlers
        
        # Simulate initialization
        QTimer.singleShot(2000, self._on_component_initialized)
    
    def _on_component_initialized(self):
        """Called when the trading component is initialized."""
        self.initialized = True
        self.status_bar.setText("Ready")
        
        # Enable UI elements
        self.buy_button.setEnabled(True)
        self.sell_button.setEnabled(True)
        
        # Subscribe to events AFTER init completes
        if self.event_bus:
            from PyQt6.QtCore import QTimer
            
            def subscribe_all():
                try:
                    # Subscribe to trading events using SYNC subscribe (not async)
                    self.event_bus.subscribe("trading.order_update", self._on_order_update)
                    self.event_bus.subscribe("trading.position_update", self._on_position_update)
                    self.event_bus.subscribe("trading.market_data", self._on_market_data)
                    logger.info("TradingFrame: Successfully connected to event bus")
                except Exception as e:
                    logger.error(f"TradingFrame subscription error: {e}")
            
            # Schedule 4.4 seconds after init
            QTimer.singleShot(4400, subscribe_all)
    
    # Event handlers for UI elements
    def _on_symbol_changed(self, symbol: str):
        """Handle symbol selection change."""
        self.symbol = symbol
        # Update market data for the selected symbol
        self._update_market_data_display()
    
    def _on_order_type_changed(self, order_type: str):
        """Handle order type change."""
        self.order_type = order_type
        self._update_price_visibility()
    
    def _on_side_changed(self, side: str):
        """Handle side selection change."""
        self.side = side
    
    def _on_quantity_changed(self, quantity: float):
        """Handle quantity change."""
        self.quantity = quantity
    
    def _on_price_changed(self, price: float):
        """Handle price change."""
        self.price = price
    
    def _on_buy_clicked(self):
        """Handle buy button click."""
        self.side = "buy"
        self._place_order()
    
    def _on_sell_clicked(self):
        """Handle sell button click."""
        self.side = "sell"
        self._place_order()
    
    def _on_close_position_clicked(self):
        """Handle close position button click."""
        selected_items = self.positions_table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        symbol = self.positions_table.item(row, 0).text()
        
        # In a real implementation, this would close the position
        # through the trading component
        QMessageBox.information(
            self, 
            "Close Position", 
            f"Would close position for {symbol}"
        )
    
    def _on_order_selection_changed(self):
        """Handle order selection change."""
        selected = self.orders_table.selectedItems()
        self.cancel_order_button.setEnabled(len(selected) > 0)
        self.modify_order_button.setEnabled(len(selected) > 0)
    
    def _on_cancel_order_clicked(self):
        """Handle cancel order button click."""
        selected_items = self.orders_table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        order_id = self.orders_table.item(row, 0).text()
        
        # In a real implementation, this would cancel the order
        # through the trading component
        QMessageBox.information(
            self, 
            "Cancel Order", 
            f"Would cancel order {order_id}"
        )
    
    def _on_modify_order_clicked(self):
        """Handle modify order button click."""
        selected_items = self.orders_table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        order_id = self.orders_table.item(row, 0).text()
        
        # In a real implementation, this would open a dialog to modify the order
        QMessageBox.information(
            self, 
            "Modify Order", 
            f"Would modify order {order_id}"
        )
    
    def _on_market_data_symbol_changed(self, symbol: str):
        """Handle market data symbol change."""
        try:
            logger.info("Market data symbol changed to: %s", symbol)
            for i in range(len(self.market_data_fields)):
                self.market_data_display.setItem(i, 1, QTableWidgetItem("-"))

            if self.event_bus:
                self.event_bus.publish("trading.market_data.subscribe", {
                    "symbol": symbol,
                    "source": "trading_frame"
                })
            self._update_market_data_display()
        except Exception as e:
            logger.error("Error changing market data symbol: %s", e)
    
    def _update_price_visibility(self):
        """Update price input visibility based on order type."""
        show_price = self.order_type in ["limit", "stop", "stop_limit"]
        self.price_label.setVisible(show_price)
        self.price_spin.setVisible(show_price)
    
    def _place_order(self):
        """Place a new order."""
        if not self.initialized:
            QMessageBox.warning(self, "Not Ready", "Trading component is not initialized yet.")
            return
        
        # Validate inputs
        if self.quantity <= 0:
            QMessageBox.warning(self, "Invalid Quantity", "Quantity must be greater than zero.")
            return
            
        if self.order_type in ["limit", "stop", "stop_limit"] and self.price <= 0:
            QMessageBox.warning(self, "Invalid Price", "Price must be greater than zero for this order type.")
            return
        
        # Prepare order data
        order_data = {
            "symbol": self.symbol,
            "order_type": self.order_type,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price if self.order_type in ["limit", "stop", "stop_limit"] else None,
            "stop_price": self.price if self.order_type in ["stop", "stop_limit"] else None
        }
        
        # In a real implementation, this would place the order through the trading component
        # and handle the response asynchronously
        QMessageBox.information(
            self, 
            "Order Placed", 
            f"{self.side.upper()} {self.order_type.upper()} order for {self.quantity} {self.symbol} at {self.price if self.price > 0 else 'market'}"
        )
    
    def _update_market_data_display(self):
        """Update the market data display with current cached data."""
        try:
            symbol = self.market_data_symbol.currentText()
            self.status_bar.setText(f"Watching: {symbol}")
        except Exception as e:
            logger.debug("Error updating market data display: %s", e)
    
    # Event handlers for trading events
    def _on_order_update(self, event_data: Dict[str, Any]):
        """Handle order update events."""
        self.order_updated.emit(event_data)
    
    def _on_position_update(self, event_data: Dict[str, Any]):
        """Handle position update events."""
        self.position_updated.emit(event_data)
    
    def _on_market_data(self, event_data: Dict[str, Any]):
        """Handle market data events."""
        self.market_data_updated.emit(event_data)
    
    # Slots for cross-thread communication
    @pyqtSlot(dict)
    def update_order_display(self, order_data: Dict[str, Any]):
        """Update the orders table with new order data."""
        try:
            if not isinstance(order_data, dict):
                return

            order_id = str(order_data.get('order_id', order_data.get('id', '')))
            symbol = str(order_data.get('symbol', ''))
            order_type = str(order_data.get('type', order_data.get('order_type', '')))
            side = str(order_data.get('side', ''))
            qty = str(order_data.get('quantity', order_data.get('amount', '')))
            price = str(order_data.get('price', '-'))
            status = str(order_data.get('status', 'unknown'))

            for row in range(self.orders_table.rowCount()):
                if self.orders_table.item(row, 0) and self.orders_table.item(row, 0).text() == order_id:
                    self.orders_table.setItem(row, 6, QTableWidgetItem(status))
                    return

            row = self.orders_table.rowCount()
            self.orders_table.insertRow(row)
            for col, val in enumerate([order_id, symbol, order_type, side, qty, price, status]):
                self.orders_table.setItem(row, col, QTableWidgetItem(val))
        except Exception as e:
            logger.error("Error updating order display: %s", e)
    
    @pyqtSlot(dict)
    def update_position_display(self, position_data: Dict[str, Any]):
        """Update the positions table with new position data."""
        try:
            if not isinstance(position_data, dict):
                return

            symbol = str(position_data.get('symbol', ''))
            size = str(position_data.get('size', position_data.get('quantity', '')))
            entry = str(position_data.get('entry_price', '-'))
            mark = str(position_data.get('mark_price', position_data.get('current_price', '-')))
            pnl = str(position_data.get('pnl', position_data.get('unrealized_pnl', '-')))

            for row in range(self.positions_table.rowCount()):
                if self.positions_table.item(row, 0) and self.positions_table.item(row, 0).text() == symbol:
                    self.positions_table.setItem(row, 1, QTableWidgetItem(size))
                    self.positions_table.setItem(row, 3, QTableWidgetItem(mark))
                    self.positions_table.setItem(row, 4, QTableWidgetItem(pnl))
                    pnl_item = self.positions_table.item(row, 4)
                    try:
                        pnl_val = float(position_data.get('pnl', 0))
                        color = QColor("#4CAF50") if pnl_val >= 0 else QColor("#F44336")
                        pnl_item.setForeground(color)
                    except (TypeError, ValueError):
                        pass
                    return

            row = self.positions_table.rowCount()
            self.positions_table.insertRow(row)
            for col, val in enumerate([symbol, size, entry, mark, pnl]):
                self.positions_table.setItem(row, col, QTableWidgetItem(val))
            self.close_position_button.setEnabled(True)
        except Exception as e:
            logger.error("Error updating position display: %s", e)
    
    @pyqtSlot(dict)
    def update_market_data_display(self, market_data: Dict[str, Any]):
        """Update the market data display with new market data."""
        try:
            if not isinstance(market_data, dict):
                return

            field_map = {
                "Last Price": market_data.get("last_price", market_data.get("price")),
                "Bid": market_data.get("bid"),
                "Ask": market_data.get("ask"),
                "24h High": market_data.get("high_24h", market_data.get("high")),
                "24h Low": market_data.get("low_24h", market_data.get("low")),
                "24h Volume": market_data.get("volume_24h", market_data.get("volume")),
                "24h Change": market_data.get("change_24h"),
                "24h Change %": market_data.get("change_pct_24h"),
            }

            for i, field_name in enumerate(self.market_data_fields):
                value = field_map.get(field_name)
                display_val = "-"
                if value is not None:
                    try:
                        display_val = f"{float(value):,.8g}"
                    except (TypeError, ValueError):
                        display_val = str(value)
                self.market_data_display.setItem(i, 1, QTableWidgetItem(display_val))
        except Exception as e:
            logger.error("Error updating market data display: %s", e)
    
    @pyqtSlot(str)
    def show_error(self, error_message: str):
        """Show an error message to the user."""
        QMessageBox.critical(self, "Trading Error", error_message)
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Clean up resources
        if self.event_bus:
            # Unsubscribe from all events using SYNC unsubscribe (not async)
            try:
                self.event_bus.unsubscribe("trading.order_update", self._on_order_update)
                self.event_bus.unsubscribe("trading.position_update", self._on_position_update)
                self.event_bus.unsubscribe("trading.market_data", self._on_market_data)
                logger.info("TradingFrame: Successfully unsubscribed from event bus")
            except Exception as e:
                logger.error(f"TradingFrame: Error unsubscribing from event bus: {e}")
        event.accept()
