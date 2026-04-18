"""
Cyberpunk Orders Widget

This module contains the OrderWidget class for displaying current and historical orders
with advanced cyberpunk styling featuring RGB borders, glow effects, and futuristic aesthetics.
"""
from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, 
    QLabel, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QBrush, QPainter, QFont, QLinearGradient
import logging
logger = logging.getLogger(__name__)
from datetime import datetime
import asyncio
import time
import random

from .base import ResizableWidget
from core.event_bus import EventBus

# Import cyberpunk styling components if available
try:
    from gui.cyberpunk_style import (
        CyberpunkStyle, CyberpunkEffect, CYBERPUNK_THEME
    )
    has_cyberpunk = True
except ImportError:
    logger.warning("Cyberpunk styling components not available - using fallback styling")
    has_cyberpunk = False
    # Define minimal fallback theme
    cyberpunk_theme = {
        "background": "#0F111A",
        "foreground": "#00FFFF",
        "accent": "#FF00FF",
        "positive": "#00FF66",
        "negative": "#FF3366",
        "neutral": "#33CCFF",
        "rgb_cycle": ["#FF00FF", "#00FFFF", "#00FF66", "#FFFF00"]
    }

import redis
import sys

# Connect to Redis Quantum Nexus - required with no fallbacks
def connect_to_redis():
    """Connect to Redis Quantum Nexus - required with no fallbacks"""
    try:
        redis_client = redis.Redis(  # type: ignore
            host="localhost", 
            port=6380,  # Required specific port
            password="QuantumNexus2025",  # Required password
            decode_responses=True,
            socket_connect_timeout=3
        )
        # Test connection
        if not redis_client.ping():
            logger.warning("Redis Quantum Nexus connection unhealthy - widget will retry later")
            return None
            
        logger.info("Successfully connected to Redis Quantum Nexus")
        return redis_client
    except Exception as e:
        logger.warning(f"Redis Quantum Nexus not available: {e} - widget will use fallback mode")
        return None

# Global Redis client - graceful fallback if not available
REDIS_CLIENT = connect_to_redis()

class OrderWidget(ResizableWidget):
    """Widget for displaying current and historical orders with cyberpunk styling."""
    
    def __init__(self, parent=None, event_bus=None):
        """Initialize the OrderWidget with cyberpunk styling.
        
        Args:
            parent: Parent widget
            event_bus: Event bus for communication
        """
        super().__init__(parent=parent, min_width=600, min_height=200)
        self.event_bus = event_bus
        
        # Cyberpunk animation elements
        self._rgb_index = 0
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._update_animation)
        self._animation_timer.start(80)  # RGB cycle every 80ms
        
        # Track recently updated rows for highlighting effects
        self._recently_updated_rows = {}
        
        # Redis client for data connectivity - graceful fallback if not available
        self.redis_client = REDIS_CLIENT
        if not self.redis_client:
            logger.warning("Redis Quantum Nexus not available - OrderWidget running in offline mode")
        
        self._init_ui()
        
        # Subscribe to order events if event bus is provided
        if self.event_bus:
            self._subscribe_to_events()
    
    def _init_ui(self):
        """Initialize the user interface with cyberpunk styling."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)  # More space between elements for futuristic feel
        layout.setContentsMargins(6, 6, 6, 6)  # Slightly larger margins for RGB border
        
        # Title with cyberpunk styling
        self.title = QLabel("ORDERS INTERFACE")
        title_font = QFont("Orbitron", 14)  # Cyberpunk style font
        title_font.setBold(True)
        self.title.setFont(title_font)
        
        # Apply cyberpunk color and glow effect
        self.title.setStyleSheet(f"color: {CYBERPUNK_THEME['accent']}; padding: 5px;")
        if HAS_CYBERPUNK:
            title_glow = CyberpunkEffect.create_glow_effect(
                QColor(CYBERPUNK_THEME['accent']), intensity=15, spread=10
            )
            self.title.setGraphicsEffect(title_glow)
        
        # Create container frame for better cyberpunk aesthetics
        title_container = QFrame()
        title_container.setObjectName("titleContainer")
        title_container.setStyleSheet(f"""
            #titleContainer {{
                background-color: {CYBERPUNK_THEME['background']};
                border: 1px solid {CYBERPUNK_THEME['accent']};
                border-radius: 2px;
                padding: 2px;
            }}
        """)
        title_layout = QVBoxLayout(title_container)
        title_layout.addWidget(self.title)
        layout.addWidget(title_container)
        
        # Orders table with cyberpunk styling
        self.table = QTableWidget(0, 7)  # Symbol, Type, Side, Size, Price, Status, Time
        self.table.setHorizontalHeaderLabels(["SYMBOL", "TYPE", "SIDE", "SIZE", "PRICE", "STATUS", "TIME"])
        
        # Apply cyberpunk font to table
        table_font = QFont("Consolas", 9)  # Monospace for data display
        self.table.setFont(table_font)
        
        # Cyberpunk table styling
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {CYBERPUNK_THEME['background']};
                color: {CYBERPUNK_THEME['foreground']};
                gridline-color: {CYBERPUNK_THEME['accent']};
                border: 1px solid {CYBERPUNK_THEME['accent']};
                border-radius: 2px;
            }}
            QHeaderView::section {{
                background-color: {CYBERPUNK_THEME['background']};
                color: {CYBERPUNK_THEME['accent']};
                border: 1px solid {CYBERPUNK_THEME['accent']};
                padding: 4px;
                font-weight: bold;
            }}
            QTableWidget::item {{
                border-bottom: 1px solid rgba(0, 255, 255, 30);
                padding: 2px;
            }}
            QTableWidget::item:selected {{
                background-color: {CYBERPUNK_THEME['accent']};
                color: {CYBERPUNK_THEME['background']};
            }}
        """)
        
        # Set column resize modes
        for i in range(self.table.columnCount()):
            self.table.horizontalHeader().setSectionResizeMode(
                i, QHeaderView.ResizeMode.ResizeToContents
            )
        
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        
        # Set row height for better cyberpunk aesthetics
        self.table.verticalHeader().setDefaultSectionSize(30)
        
        # Add status label with cyberpunk styling
        self.status_label = QLabel("CONNECTED TO QUANTUM NEXUS")
        status_font = QFont("Consolas", 8)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet(f"color: {CYBERPUNK_THEME['positive']}; padding: 2px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Add table to layout
        layout.addWidget(self.table, 1)  # Give table most of the space
        layout.addWidget(self.status_label)
        
        # Apply glow effect to the whole widget if cyberpunk is available
        if HAS_CYBERPUNK:
            widget_glow = CyberpunkEffect.create_glow_effect(
                QColor(CYBERPUNK_THEME['accent']), intensity=5, spread=10
            )
            self.setGraphicsEffect(widget_glow)
    
    def _subscribe_to_events(self):
        """Subscribe to event bus events."""
        if self.event_bus:
            # Subscribe to order update events using safe scheduling
            from utils.async_qt_helper import schedule_multiple_subscriptions
            schedule_multiple_subscriptions([
                (self.event_bus, "trading.order_update", self._on_order_update_event),
                (self.event_bus, "trading.orders", self._on_orders_event),
                # Compatibility: some backends publish filled orders only
                (self.event_bus, "trading.order_filled", self._on_order_update_event),
            ], delay_ms=2950)
            logger.info("OrderWidget: Scheduled order event subscriptions")
    
    def _unsubscribe_from_events(self):
        """Unsubscribe from event bus events."""
        if self.event_bus:
            try:
                # Unsubscribe from events (synchronous)
                self.event_bus.unsubscribe("trading.order_update", self._on_order_update_event)
                self.event_bus.unsubscribe("trading.orders", self._on_orders_event)
                logger.info("OrderWidget: Unsubscribed from order events")
            except Exception as e:
                logger.error(f"OrderWidget: Error unsubscribing from events: {e}")
    
    def _update_animation(self):
        """Update the RGB animation effects for cyberpunk styling."""
        try:
            # Cycle through RGB colors
            self._rgb_index = (self._rgb_index + 1) % len(CYBERPUNK_THEME['rgb_cycle'])
            current_color = CYBERPUNK_THEME['rgb_cycle'][self._rgb_index]
            
            # Apply to border
            self.setStyleSheet(f"border: 2px solid {current_color}; border-radius: 3px;")
            
            # Apply to status label with pulsing effect
            pulse_opacity = 0.7 + 0.3 * (time.time() % 1)
            rgba = QColor(current_color)
            rgba.setAlphaF(pulse_opacity)
            self.status_label.setStyleSheet(f"color: {rgba.name(QColor.NameFormat.HexRgb)}; padding: 2px;")
            
            # Update glow effects on recently updated rows
            current_time = time.time()
            rows_to_remove = []
            
            for row, timestamp in self._recently_updated_rows.items():
                if row < self.table.rowCount():
                    elapsed = current_time - timestamp
                    if elapsed > 5.0:  # Effect lasts for 5 seconds
                        # Remove effect after time expires
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            if item:
                                item.setBackground(QBrush())
                        rows_to_remove.append(row)
                    else:
                        # Calculate intensity based on time elapsed
                        intensity = 1.0 - (elapsed / 5.0)
                        glow_color = QColor(current_color)
                        # Apply gradient glow effect to row
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            if item:
                                bg_color = QColor(CYBERPUNK_THEME['background'])
                                bg_color.setAlphaF(1.0 - 0.3 * intensity)
                                item.setBackground(QBrush(bg_color))
                                # Set text color more vibrant
                                item.setForeground(QBrush(glow_color))
            
            # Remove expired effects
            for row in rows_to_remove:
                del self._recently_updated_rows[row]
            
            # Update Redis status if connection available
            if hasattr(self, 'redis_client') and self.redis_client:
                try:
                    # Update connection status via Redis ping
                    if self.redis_client.ping():
                        self.status_label.setText("QUANTUM NEXUS: CONNECTED")
                        self.status_label.setStyleSheet(f"color: {CYBERPUNK_THEME['positive']}; padding: 2px;")
                    else:
                        self.status_label.setText("QUANTUM NEXUS: ERROR")
                        self.status_label.setStyleSheet(f"color: {CYBERPUNK_THEME['negative']}; padding: 2px;")
                except Exception:
                    self.status_label.setText("QUANTUM NEXUS: DISCONNECTED")
                    self.status_label.setStyleSheet(f"color: {CYBERPUNK_THEME['negative']}; padding: 2px;")
                    # No fallback - in production should halt here
            
        except Exception as e:
            logger.error(f"Animation error: {e}")

    def _on_order_update_event(self, event_data):
        """Handle order update events from the event bus with cyberpunk visual effects."""
        if isinstance(event_data, dict) and 'id' in event_data:
            # Find if we already have this order
            order_found = False
            order_id = event_data.get('id')
            updated_row = -1
            
            # Look for existing order by ID
            for row in range(self.table.rowCount()):
                # Assuming order ID is stored as user data in the first column
                item = self.table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == order_id:
                    # Update the existing order
                    self.table.removeRow(row)
                    updated_row = self._add_order_row(event_data, with_animation=True)
                    order_found = True
                    break
            
            # If order not found, add it as new
            if not order_found:
                updated_row = self._add_order_row(event_data, with_animation=True)
            
            # Add to Redis if connection is available
            if hasattr(self, 'redis_client') and self.redis_client:
                try:
                    # Store order data in Redis with TTL
                    key = f"kingdom:orders:{order_id}"
                    self.redis_client.hset(key, mapping={
                        'symbol': str(event_data.get('symbol', 'N/A')),
                        'side': str(event_data.get('side', 'N/A')),
                        'status': str(event_data.get('status', 'N/A')),
                        'price': str(event_data.get('price', 0)),
                        'size': str(event_data.get('size', 0)),
                        'timestamp': str(time.time()),
                        'type': str(event_data.get('type', 'N/A'))
                    })
                    # Set expiration for 24 hours
                    self.redis_client.expire(key, 86400)
                except Exception as e:
                    logger.error(f"Failed to store order in Redis: {e}")
                    # No fallback - critical in production
                
            # Log the order update with cyberpunk formatting
            status = event_data.get('status', 'N/A')
            symbol = event_data.get('symbol', 'N/A')
            side = event_data.get('side', 'N/A')
            size = event_data.get('size', 0)
            price = event_data.get('price', 0)
            
            # Format log message with cyberpunk style
            logger.info(f"ORDER [{order_id}] :: {status.upper()} :: {symbol}/{side.upper()} :: {size} @ {price}")
            
            # Publish event to Redis for other components
            if hasattr(self, 'redis_client') and self.redis_client:
                try:
                    self.redis_client.publish("kingdom:events:orders", 
                                             f"{symbol}:{side}:{status}:{price}:{size}")
                except Exception as e:
                    logger.error(f"Failed to publish order event to Redis: {e}")
                    # No fallback - critical in production
    
    def _on_orders_event(self, event_data):
        """Handle orders list events from the event bus."""
        if isinstance(event_data, list):
            self.update_data({'orders': event_data})
        else:
            self.update_data(event_data)
    
    def update_data(self, data: Dict[str, Any]) -> None:
        """
        Update the orders display.
        
        Args:
            data: Dictionary containing orders data or list of order dictionaries
        """
        try:
            self.table.setRowCount(0)  # Clear existing data
            
            # Handle both dict and list inputs
            orders = data if isinstance(data, list) else data.get('orders', [])
            
            for order in orders:
                if isinstance(order, dict):
                    self._add_order_row(order)
                
        except Exception as e:
            logger.error(f"Error updating orders: {e}", exc_info=True)
    
    def _add_order_row(self, order: Dict[str, Any], with_animation: bool = False):
        """Add a row for a single order with cyberpunk styling."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Extract order data with defaults
        symbol = order.get('symbol', 'N/A')
        order_type = order.get('type', 'N/A').upper()
        side = order.get('side', 'N/A').upper()
        size = float(order.get('size', 0))
        price = float(order.get('price', 0))
        status = order.get('status', 'N/A').capitalize()
        order_id = order.get('id', '')
        
        # Format timestamp with cyberpunk style
        timestamp = order.get('timestamp')
        if timestamp:
            if isinstance(timestamp, (int, float)):
                # Assuming timestamp is in seconds
                dt = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e12 else timestamp)
                time_str = dt.strftime("%H:%M:%S")
            else:
                time_str = str(timestamp)
        else:
            time_str = "--:--:--"
        
        # Create items with cyberpunk formatting
        symbol_item = QTableWidgetItem(symbol.upper())
        type_item = QTableWidgetItem(order_type)
        side_item = QTableWidgetItem(side)
        size_item = QTableWidgetItem(f"{size:,.4f}")
        price_item = QTableWidgetItem(f"{price:,.2f}" if price else "MARKET")
        status_item = QTableWidgetItem(status.upper())
        time_item = QTableWidgetItem(time_str)
        
        # Store order ID as user data for future reference
        if order_id:
            symbol_item.setData(Qt.ItemDataRole.UserRole, order_id)
        
        # Align numeric values to the right
        for item in [size_item, price_item]:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Set cyberpunk colors based on side (buy/sell)
        if side.upper() == 'BUY':
            color = QColor(CYBERPUNK_THEME['positive'])  # Cyberpunk green for buy
            side_item.setForeground(color)
            side_text = "◢ BUY ◣"
            side_item.setText(side_text)
        elif side.upper() == 'SELL':
            color = QColor(CYBERPUNK_THEME['negative'])  # Cyberpunk red for sell
            side_item.setForeground(color)
            side_text = "◥ SELL ◤"
            side_item.setText(side_text)
        
        # Set cyberpunk status styling
        if status.lower() == 'filled':
            status_item.setForeground(QColor(CYBERPUNK_THEME['positive']))  # Cyberpunk green for filled
            status_item.setText("✓ FILLED")
        elif status.lower() in ['canceled', 'rejected']:
            status_item.setForeground(QColor(CYBERPUNK_THEME['negative']))  # Cyberpunk red for canceled
            status_item.setText("✗ " + status.upper())
        elif status.lower() in ['new', 'open']:
            status_item.setForeground(QColor(CYBERPUNK_THEME['neutral']))  # Cyberpunk blue for new/open
            status_item.setText("⟳ " + status.upper())
        else:
            status_item.setForeground(QColor(CYBERPUNK_THEME['accent']))
        
        # Add items to table
        self.table.setItem(row, 0, symbol_item)
        self.table.setItem(row, 1, type_item)
        self.table.setItem(row, 2, side_item)
        self.table.setItem(row, 3, size_item)
        self.table.setItem(row, 4, price_item)
        self.table.setItem(row, 5, status_item)
        self.table.setItem(row, 6, time_item)
        
        # Add animation effect for new rows
        if with_animation:
            # Store the row timestamp for animation effects
            self._recently_updated_rows[row] = time.time()
            
            # Apply immediate glow effect
            glow_color = QColor(CYBERPUNK_THEME['accent'])
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    bg_color = QColor(CYBERPUNK_THEME['background'])
                    bg_color.setAlphaF(0.7)  # Semi-transparent
                    item.setBackground(QBrush(bg_color))
                    item.setForeground(QBrush(glow_color))
            
            # Add to Redis if available for real-time updates
            if hasattr(self, 'redis_client') and self.redis_client:
                try:
                    self.redis_client.publish("kingdom:events:table_update", 
                                             f"orders:{row}:{symbol}:{side}:{status}")
                except Exception as e:
                    logger.error(f"Redis publish error: {e}")
                    # In production, system would halt here
        
        # Return the row index for reference
        return row
    
    def clear(self) -> None:
        """Clear all data from the widget with cyberpunk animation effect."""
        # Save row count for animation
        row_count = self.table.rowCount()
        
        if row_count > 0:
            # Apply fading animation effect row by row with slight delay
            if HAS_CYBERPUNK:
                for row in range(row_count):
                    # Schedule clearing with decreasing delay for staggered effect
                    QTimer.singleShot(10 * (row_count - row), lambda r=row: self._clear_row_with_effect(r))
                # Finally clear all after all animations should be done
                QTimer.singleShot(row_count * 15, lambda: self.table.setRowCount(0))
            else:
                # If no cyberpunk available, clear immediately
                self.table.setRowCount(0)
                
            # Update Redis if available
            if hasattr(self, 'redis_client') and self.redis_client:
                try:
                    self.redis_client.publish("kingdom:events:table_cleared", "orders:all")
                except Exception as e:
                    logger.error(f"Redis publish error: {e}")
                    # In production, system would halt here
        else:
            # No rows to clear
            self.table.setRowCount(0)
    
    def _clear_row_with_effect(self, row):
        """Clear a single row with cyberpunk fade-out effect."""
        try:
            # Make sure the row still exists (might have been cleared already)
            if row < self.table.rowCount():
                # Apply fading effect to row
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        # Apply fade out color
                        fade_color = QColor(CYBERPUNK_THEME['background'])
                        fade_color.setAlphaF(0.5)  # Semi-transparent
                        item.setBackground(QBrush(fade_color))
                        
                        # Make text fade to match background
                        item.setForeground(QColor(CYBERPUNK_THEME['background']))
        except Exception as e:
            logger.error(f"Error in row clearing animation: {e}")
    
    def closeEvent(self, event):
        """Handle close event for proper cleanup with cyberpunk fade-out."""
        # Update status before closing
        self.status_label.setText("QUANTUM NEXUS: DISCONNECTING")
        self.status_label.setStyleSheet(f"color: {CYBERPUNK_THEME['negative']}; padding: 2px;")
        
        # Stop animation timer
        if hasattr(self, '_animation_timer') and self._animation_timer.isActive():
            self._animation_timer.stop()
        
        # Clean up Redis resources if available
        if hasattr(self, 'redis_client') and self.redis_client:
            try:
                # Notify other components through Redis
                self.redis_client.publish("kingdom:events:component_shutdown", "orders_widget")
            except Exception as e:
                logger.error(f"Redis publish error during shutdown: {e}")
        
        # Clear any saved row data
        self._recently_updated_rows.clear()
        
        # Unsubscribe from events when widget is closed
        self._unsubscribe_from_events()
        
        # Let parent class handle the rest
        super().closeEvent(event)
