"""
Trading Tab for Kingdom AI system.

This module implements the trading interface with strict Redis connection
requirements and event-driven architecture.
"""

import logging
from typing import Dict, Any, Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLineEdit, QDoubleSpinBox, QMessageBox, QFormLayout, QSpacerItem,
    QSizePolicy, QTabWidget, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon

from core.event_handlers import BaseEventHandler
from gui.base_tab import BaseTab

class TradingEventHandler(BaseEventHandler):
    """Event handler for the Trading tab."""
    
    def __init__(self, name: str = "TradingHandler"):
        """Initialize the trading event handler."""
        super().__init__(name)
        self.logger = logging.getLogger(f"kingdom_ai.trading.{name}")
        
        # Trading-specific state
        self.positions = {}
        self.orders = {}
        self.market_data = {}
        
        # Subscribe to trading events
        self._subscribe_to_events()
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant Redis events."""
        self.subscribe("trading.position_update", self._handle_position_update)
        self.subscribe("trading.order_update", self._handle_order_update)
        self.subscribe("trading.market_data", self._handle_market_data)
        self.subscribe("trading.signal", self._handle_trading_signal)
        self.subscribe("trading.error", self._handle_trading_error)
    
    def _handle_position_update(self, data: Dict[str, Any]) -> None:
        """Handle position update events."""
        try:
            symbol = data.get('symbol')
            if symbol:
                self.positions[symbol] = data
                self.data_updated.emit("position_update", data)
        except Exception as e:
            self.logger.error(f"Error handling position update: {e}")
    
    def _handle_order_update(self, data: Dict[str, Any]) -> None:
        """Handle order update events."""
        try:
            order_id = data.get('order_id')
            if order_id:
                self.orders[order_id] = data
                self.data_updated.emit("order_update", data)
        except Exception as e:
            self.logger.error(f"Error handling order update: {e}")
    
    def _handle_market_data(self, data: Dict[str, Any]) -> None:
        """Handle market data events."""
        try:
            symbol = data.get('symbol')
            if symbol:
                self.market_data[symbol] = data
                self.data_updated.emit("market_data", data)
        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")
    
    def _handle_trading_signal(self, data: Dict[str, Any]) -> None:
        """Handle trading signal events."""
        try:
            self.data_updated.emit("trading_signal", data)
        except Exception as e:
            self.logger.error(f"Error handling trading signal: {e}")
    
    def _handle_trading_error(self, data: Dict[str, Any]) -> None:
        """Handle trading error events."""
        try:
            error_msg = data.get('error', 'Unknown trading error')
            self.status_update.emit(f"Trading Error: {error_msg}", "error")
        except Exception as e:
            self.logger.error(f"Error handling trading error: {e}")
    
    def place_order(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place a new order.
        
        Args:
            order_data: Dictionary containing order details
            
        Returns:
            Order confirmation or None if failed
        """
        try:
            if not self._connected:
                raise RedisConnectionError("Not connected to Redis")
                
            # Validate order data
            required_fields = ['symbol', 'side', 'order_type', 'qty']
            for field in required_fields:
                if field not in order_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Publish order request
            self.publish("trading.place_order", order_data)
            self.status_update.emit(f"Placing {order_data['side']} order for {order_data['symbol']}", "info")
            
            # In a real implementation, we would wait for order confirmation
            return {"status": "submitted", "message": "Order submitted for processing"}
            
        except Exception as e:
            error_msg = f"Failed to place order: {str(e)}"
            self.logger.error(error_msg)
            self.status_update.emit(error_msg, "error")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order.
        
        Args:
            order_id: ID of the order to cancel
            
        Returns:
            bool: True if cancellation was successful, False otherwise
        """
        try:
            if not self._connected:
                raise RedisConnectionError("Not connected to Redis")
                
            if not order_id:
                raise ValueError("Order ID is required")
            
            # Publish cancel request
            self.publish("trading.cancel_order", {"order_id": order_id})
            self.status_update.emit(f"Canceling order {order_id}", "info")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to cancel order {order_id}: {str(e)}"
            self.logger.error(error_msg)
            self.status_update.emit(error_msg, "error")
            return False


class TradingTab(BaseTab):
    """Trading tab for the Kingdom AI system."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the trading tab."""
        super().__init__("trading", TradingEventHandler, parent)
        self.logger = logging.getLogger("kingdom_ai.trading")
        
        # Trading state
        self.selected_symbol = ""
        self.current_price = 0.0
        self.position_size = 0.0
        
        # Initialize UI
        self._init_ui()
        
        # Start market data updates
        self._start_market_data_updates()
    
    def _init_ui(self) -> None:
        """Initialize the user interface."""
        # Main layout
        main_layout = QHBoxLayout(self)
        self.setLayout(main_layout)
        
        # Create a splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Order entry
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Symbol selection
        symbol_layout = QHBoxLayout()
        symbol_layout.addWidget(QLabel("Symbol:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "ADA/USD"])
        self.symbol_combo.currentTextChanged.connect(self._on_symbol_changed)
        symbol_layout.addWidget(self.symbol_combo)
        left_layout.addLayout(symbol_layout)
        
        # Price display
        self.price_label = QLabel("Price: --")
        self.price_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.price_label)
        
        # Change indicator
        self.change_label = QLabel("+0.00%")
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.change_label)
        
        # Order form
        form_layout = QFormLayout()
        
        # Order type
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["Market", "Limit", "Stop", "Stop Limit"])
        form_layout.addRow("Order Type:", self.order_type_combo)
        
        # Side (Buy/Sell)
        self.side_combo = QComboBox()
        self.side_combo.addItems(["Buy", "Sell"])
        form_layout.addRow("Side:", self.side_combo)
        
        # Quantity
        self.quantity_spin = QDoubleSpinBox()
        self.quantity_spin.setRange(0.0001, 1000.0)
        self.quantity_spin.setDecimals(4)
        self.quantity_spin.setValue(0.1)
        form_layout.addRow("Quantity:", self.quantity_spin)
        
        # Price (for limit orders)
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.0001, 1000000.0)
        self.price_spin.setDecimals(2)
        self.price_spin.setValue(50000.0)
        form_layout.addRow("Price:", self.price_spin)
        
        left_layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.buy_button = QPushButton("Buy")
        self.buy_button.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.buy_button.clicked.connect(self._on_buy_clicked)
        button_layout.addWidget(self.buy_button)
        
        self.sell_button = QPushButton("Sell")
        self.sell_button.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.sell_button.clicked.connect(self._on_sell_clicked)
        button_layout.addWidget(self.sell_button)
        
        left_layout.addLayout(button_layout)
        
        # Add stretch to push content to the top
        left_layout.addStretch()
        
        # Right panel - Positions and orders
        right_panel = QTabWidget()
        
        # Positions tab
        positions_tab = QWidget()
        positions_layout = QVBoxLayout(positions_tab)
        
        self.positions_table = QTableWidget(0, 5)
        self.positions_table.setHorizontalHeaderLabels(["Symbol", "Side", "Size", "Entry", "P&L"])
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        positions_layout.addWidget(self.positions_table)
        
        right_panel.addTab(positions_tab, "Positions")
        
        # Orders tab
        orders_tab = QWidget()
        orders_layout = QVBoxLayout(orders_tab)
        
        self.orders_table = QTableWidget(0, 6)
        self.orders_table.setHorizontalHeaderLabels(["ID", "Symbol", "Side", "Type", "Qty", "Price", "Status"])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        orders_layout.addWidget(self.orders_table)
        
        right_panel.addTab(orders_tab, "Orders")
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # Set initial sizes
        splitter.setSizes([self.width() // 3, 2 * self.width() // 3])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Set initial symbol
        self._on_symbol_changed(self.symbol_combo.currentText())
    
    def _on_symbol_changed(self, symbol: str) -> None:
        """Handle symbol selection change."""
        self.selected_symbol = symbol
        self.status_update.emit(f"Selected symbol: {symbol}", "info")
        
        # Update price display with the selected symbol
        self._update_price_display()
    
    def _update_price_display(self) -> None:
        """Update the price display with current market data."""
        if not hasattr(self, 'event_handler'):
            return
            
        symbol = self.selected_symbol
        market_data = self.event_handler.market_data.get(symbol, {})
        
        if 'price' in market_data:
            self.current_price = market_data['price']
            self.price_label.setText(f"{symbol}\n{self.current_price:,.2f}")
            
            # Update change
            if 'change_24h' in market_data:
                change = market_data['change_24h']
                self.change_label.setText(f"{change:+.2f}%")
                
                # Set color based on change
                if change > 0:
                    self.change_label.setStyleSheet("color: #28a745; font-weight: bold;")
                elif change < 0:
                    self.change_label.setStyleSheet("color: #dc3545; font-weight: bold;")
                else:
                    self.change_label.setStyleSheet("color: #6c757d;")
    
    def _on_buy_clicked(self) -> None:
        """Handle buy button click."""
        self._place_order("buy")
    
    def _on_sell_clicked(self) -> None:
        """Handle sell button click."""
        self._place_order("sell")
    
    def _place_order(self, side: str) -> None:
        """Place a new order."""
        if not hasattr(self, 'event_handler'):
            self.status_update.emit("Trading system not initialized", "error")
            return
            
        try:
            # Get order details
            symbol = self.selected_symbol
            order_type = self.order_type_combo.currentText().lower()
            quantity = self.quantity_spin.value()
            price = self.price_spin.value()
            
            # Create order data
            order_data = {
                'symbol': symbol,
                'side': side.lower(),
                'order_type': order_type,
                'qty': quantity,
                'price': price if order_type != 'market' else None,
                'time_in_force': 'gtc',  # Good till cancelled
                'reduce_only': False
            }
            
            # Place order through event handler
            result = self.event_handler.place_order(order_data)
            
            if result:
                self.status_update.emit("Order placed successfully", "success")
            else:
                self.status_update.emit("Failed to place order", "error")
                
        except Exception as e:
            self.status_update.emit(f"Error placing order: {str(e)}", "error")
    
    def _start_market_data_updates(self) -> None:
        """Start periodic market data updates."""
        self.market_data_timer = QTimer(self)
        self.market_data_timer.timeout.connect(self._update_market_data)
        self.market_data_timer.start(1000)  # Update every second
    
    def _update_market_data(self) -> None:
        """Update market data display."""
        if not hasattr(self, 'event_handler') or not self.event_handler._connected:
            return
            
        # Update price display
        self._update_price_display()
        
        # Update positions and orders
        self._update_positions()
        self._update_orders()
    
    def _update_positions(self) -> None:
        """Update positions table."""
        if not hasattr(self, 'event_handler'):
            return
            
        try:
            # Clear existing rows
            self.positions_table.setRowCount(0)
            
            # Add positions
            for symbol, position in self.event_handler.positions.items():
                row = self.positions_table.rowCount()
                self.positions_table.insertRow(row)
                
                # Add position data
                self.positions_table.setItem(row, 0, QTableWidgetItem(position.get('symbol', '')))
                self.positions_table.setItem(row, 1, QTableWidgetItem(position.get('side', '').capitalize()))
                self.positions_table.setItem(row, 2, QTableWidgetItem(f"{position.get('size', 0):.4f}"))
                self.positions_table.setItem(row, 3, QTableWidgetItem(f"{position.get('entry_price', 0):.2f}"))
                
                # Calculate P&L
                pnl = position.get('unrealized_pnl', 0)
                pnl_item = QTableWidgetItem(f"{pnl:.2f}")
                if pnl > 0:
                    pnl_item.setForeground(QColor(40, 167, 69))  # Green
                elif pnl < 0:
                    pnl_item.setForeground(QColor(220, 53, 69))  # Red
                self.positions_table.setItem(row, 4, pnl_item)
                
        except Exception as e:
            self.logger.error(f"Error updating positions: {e}")
    
    def _update_orders(self) -> None:
        """Update orders table."""
        if not hasattr(self, 'event_handler'):
            return
            
        try:
            # Clear existing rows
            self.orders_table.setRowCount(0)
            
            # Add orders
            for order_id, order in self.event_handler.orders.items():
                row = self.orders_table.rowCount()
                self.orders_table.insertRow(row)
                
                # Add order data
                self.orders_table.setItem(row, 0, QTableWidgetItem(order.get('order_id', '')[:8]))
                self.orders_table.setItem(row, 1, QTableWidgetItem(order.get('symbol', '')))
                self.orders_table.setItem(row, 2, QTableWidgetItem(order.get('side', '').capitalize()))
                self.orders_table.setItem(row, 3, QTableWidgetItem(order.get('order_type', '').capitalize()))
                self.orders_table.setItem(row, 4, QTableWidgetItem(f"{order.get('qty', 0):.4f}"))
                self.orders_table.setItem(row, 5, QTableWidgetItem(f"{order.get('price', 'Market'):.2f}"))
                
                # Status with color coding
                status = order.get('status', '').capitalize()
                status_item = QTableWidgetItem(status)
                
                if status.lower() in ['filled', 'done']:
                    status_item.setForeground(QColor(40, 167, 69))  # Green
                elif status.lower() in ['canceled', 'rejected', 'expired']:
                    status_item.setForeground(QColor(108, 117, 125))  # Gray
                elif status.lower() in ['new', 'open', 'partially_filled']:
                    status_item.setForeground(QColor(23, 162, 184))  # Cyan
                else:
                    status_item.setForeground(QColor(255, 193, 7))  # Yellow
                    
                self.orders_table.setItem(row, 6, status_item)
                
        except Exception as e:
            self.logger.error(f"Error updating orders: {e}")
    
    def on_connected(self) -> None:
        """Called when the trading system is connected."""
        super().on_connected()
        self.status_update.emit("Connected to trading system", "success")
        
        # Enable trading controls
        self._set_trading_enabled(True)
    
    def on_disconnected(self) -> None:
        """Called when the trading system is disconnected."""
        super().on_disconnected()
        self.status_update.emit("Disconnected from trading system", "warning")
        
        # Disable trading controls
        self._set_trading_enabled(False)
    
    def _set_trading_enabled(self, enabled: bool) -> None:
        """Enable or disable trading controls."""
        self.buy_button.setEnabled(enabled)
        self.sell_button.setEnabled(enabled)
        self.quantity_spin.setEnabled(enabled)
        self.price_spin.setEnabled(enabled)
        self.side_combo.setEnabled(enabled)
        self.order_type_combo.setEnabled(enabled)
    
    def cleanup(self) -> None:
        """Clean up resources."""
        # Stop market data timer
        if hasattr(self, 'market_data_timer'):
            self.market_data_timer.stop()
            
        # Call parent cleanup
        super().cleanup()
