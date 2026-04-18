"""
Order Entry Widget for Trading Interface
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QDoubleSpinBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
import logging
import asyncio

from core.event_bus import EventBus

logger = logging.getLogger(__name__)

class OrderEntryWidget(QWidget):
    """Widget for entering and submitting trading orders."""
    
    order_submitted = pyqtSignal(dict)  # Signal emitted when order is submitted
    
    def __init__(self, parent=None, event_bus=None):
        """Initialize the order entry widget.
        
        Args:
            parent: Parent widget
            event_bus: Event bus for communication
        """
        super().__init__(parent)
        self.event_bus = event_bus
        self.setup_ui()
        
        # Subscribe to events if event bus is provided
        if self.event_bus:
            self._subscribe_to_events()
        
    def _subscribe_to_events(self):
        """Subscribe to event bus events."""
        if self.event_bus:
            # Subscribe to market data events using safe scheduling
            from utils.async_qt_helper import schedule_multiple_subscriptions
            schedule_multiple_subscriptions([
                (self.event_bus, "trading.market_data", self._on_market_data_event),
                (self.event_bus, "trading.symbols", self._on_symbols_event),
            ], delay_ms=2850)
            logger.info("OrderEntryWidget: Scheduled trading event subscriptions")
    
    def _unsubscribe_from_events(self):
        """Unsubscribe from event bus events."""
        if self.event_bus:
            try:
                # Unsubscribe from events (synchronous)
                self.event_bus.unsubscribe("trading.market_data", self._on_market_data_event)
                self.event_bus.unsubscribe("trading.symbols", self._on_symbols_event)
                logger.info("OrderEntryWidget: Unsubscribed from trading events")
            except Exception as e:
                logger.error(f"OrderEntryWidget: Error unsubscribing from events: {e}")
    
    def _on_market_data_event(self, event_data):
        """Handle market data events from the event bus."""
        if isinstance(event_data, dict):
            symbol = event_data.get('symbol')
            price = event_data.get('price')
            
            if symbol and price is not None:
                self.update_market_data(symbol, price)
    
    def _on_symbols_event(self, event_data):
        """Handle symbol list events from the event bus."""
        if isinstance(event_data, list) and event_data:
            current = self.symbol_combo.currentText()
            self.symbol_combo.clear()
            self.symbol_combo.addItems(event_data)
            
            # Try to restore previous selection if possible
            index = self.symbol_combo.findText(current)
            if index >= 0:
                self.symbol_combo.setCurrentIndex(index)
            
    def setup_ui(self):
        """Set up the user interface."""
        self.layout = QVBoxLayout(self)
        
        # Symbol selection
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
        
        # Order type
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(['Market', 'Limit', 'Stop', 'Stop Limit'])
        
        # Side selection
        self.side_combo = QComboBox()
        self.side_combo.addItems(['Buy', 'Sell'])
        
        # Quantity
        self.quantity_spin = QDoubleSpinBox()
        self.quantity_spin.setRange(0.001, 1000)
        self.quantity_spin.setDecimals(8)
        self.quantity_spin.setValue(0.01)
        
        # Price (disabled for market orders)
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.00000001, 1000000)
        self.price_spin.setDecimals(8)
        self.price_spin.setValue(50000.0)
        
        # Stop price (for stop orders)
        self.stop_price_spin = QDoubleSpinBox()
        self.stop_price_spin.setRange(0.00000001, 1000000)
        self.stop_price_spin.setDecimals(8)
        self.stop_price_spin.setValue(51000.0)
        self.stop_price_spin.setVisible(False)
        
        # Submit button
        self.submit_btn = QPushButton("Submit Order")
        self.submit_btn.clicked.connect(self.on_submit)
        
        # Layout
        form_layout = QVBoxLayout()
        
        def add_row(label, widget):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(widget)
            form_layout.addLayout(row)
        
        add_row("Symbol:", self.symbol_combo)
        add_row("Type:", self.order_type_combo)
        add_row("Side:", self.side_combo)
        add_row("Quantity:", self.quantity_spin)
        add_row("Price:", self.price_spin)
        add_row("Stop Price:", self.stop_price_spin)
        
        self.layout.addLayout(form_layout)
        self.layout.addWidget(self.submit_btn)
        
        # Connect signals
        self.order_type_combo.currentTextChanged.connect(self.on_order_type_changed)
        
    def on_order_type_changed(self, order_type):
        """Handle order type changes."""
        is_market = order_type == 'Market'
        is_stop = 'Stop' in order_type
        
        self.price_spin.setVisible(not is_market)
        self.stop_price_spin.setVisible(is_stop)
        
    def on_submit(self):
        """Handle order submission."""
        try:
            order = {
                'symbol': self.symbol_combo.currentText(),
                'type': self.order_type_combo.currentText().lower(),
                'side': self.side_combo.currentText().lower(),
                'quantity': self.quantity_spin.value(),
                'price': self.price_spin.value()
            }
            
            if 'stop' in order['type']:
                order['stop_price'] = self.stop_price_spin.value()
            
            # Emit the signal for backward compatibility with old code
            self.order_submitted.emit(order)
            
            # Publish to event bus if available
            if self.event_bus:
                from utils.async_qt_helper import schedule_event_publish
                schedule_event_publish(self.event_bus, "trading.order_submit", order, delay_ms=50)
                logger.info(f"Order scheduled for publish: {order}")
            else:
                logger.info(f"Order submitted via signal: {order}")
            
        except Exception as e:
            logger.error(f"Error submitting order: {e}")
    
    def update_market_data(self, symbol, price):
        """Update market data for the selected symbol."""
        if symbol == self.symbol_combo.currentText():
            self.price_spin.setValue(price)
            self.stop_price_spin.setValue(price * 1.02)  # Default stop 2% above
            
    def closeEvent(self, event):
        """Handle close event for proper cleanup."""
        # Unsubscribe from events when widget is closed
        self._unsubscribe_from_events()
        # Let parent class handle the rest
        super().closeEvent(event)
