"""
Order Book Widget

This module contains the OrderBookWidget class for displaying order book data
with advanced cyberpunk styling featuring RGB borders, neon glow effects,
and particle animations.
"""
from typing import Dict, Any, List, Tuple
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout,
    QLabel, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QBrush, QPainter, QPen, QLinearGradient, QFont
import logging
import asyncio
import random
import math

from .base import ResizableWidget
from core.event_bus import EventBus

# Import cyberpunk styling components
try:
    from gui.cyberpunk_style import (
        CyberpunkStyle, CyberpunkEffect, CyberpunkRGBBorderWidget,
        CyberpunkParticleSystem, CYBERPUNK_THEME
    )
    HAS_CYBERPUNK = True
except ImportError:
    logger.warning("Cyberpunk styling components not available - using fallback styling")
    HAS_CYBERPUNK = False
    # Define minimal fallback theme
    CYBERPUNK_THEME = {
        "background": "#0F111A",
        "foreground": "#00FFFF",
        "accent": "#FF00FF",
        "positive": "#00FF66",
        "negative": "#FF3366",
        "neutral": "#33CCFF",
        "rgb_cycle": ["#FF00FF", "#00FFFF", "#00FF66", "#FFFF00"]
    }
    
    # Minimal fallback classes if cyberpunk_style.py is not available
    class CyberpunkStyle:
        @staticmethod
        def apply_to_widget(widget, widget_type): pass
    
    class CyberpunkEffect:
        @staticmethod
        def create_glow_effect(color, intensity=5, spread=5): 
            effect = QGraphicsDropShadowEffect()
            effect.setColor(color)
            effect.setBlurRadius(spread)
            effect.setOffset(0, 0)
            return effect
    
    # SOTA 2026: Fallback RGB border widget when cyberpunk_style.py unavailable
    class CyberpunkRGBBorderWidget(ResizableWidget):
        """Fallback RGB border widget with animation support."""
        
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._animation_hue = 0.0
            self._animation_speed = 0.01
            self._border_width = 2
            self._glow_enabled = True
        
        def _update_animation(self):
            """Update RGB animation cycle."""
            import colorsys
            self._animation_hue = (self._animation_hue + self._animation_speed) % 1.0
            r, g, b = colorsys.hsv_to_rgb(self._animation_hue, 1.0, 1.0)
            color = f"rgb({int(r*255)}, {int(g*255)}, {int(b*255)})"
            
            # Apply animated border
            self.setStyleSheet(f"""
                border: {self._border_width}px solid {color};
                border-radius: 5px;
            """)
        
        def set_border_width(self, width):
            """Set border width."""
            self._border_width = max(1, min(10, width))
        
        def set_animation_speed(self, speed):
            """Set animation speed."""
            self._animation_speed = max(0.001, min(0.1, speed))
        
        def enable_glow(self, enabled):
            """Enable/disable glow effect."""
            self._glow_enabled = enabled
    
    class CyberpunkParticleSystem:
        """Fallback particle system for visual effects."""
        
        def __init__(self, max_particles=100):
            self.max_particles = max_particles
            self.particles = []
        
        def emit(self, x, y, count):
            """Emit particles at position."""
            import random
            for _ in range(min(count, self.max_particles - len(self.particles))):
                self.particles.append({
                    'x': x,
                    'y': y,
                    'vx': random.uniform(-2, 2),
                    'vy': random.uniform(-2, 2),
                    'life': 1.0,
                    'decay': random.uniform(0.02, 0.05),
                    'size': random.uniform(2, 5)
                })
        
        def update(self):
            """Update all particles."""
            for p in self.particles[:]:
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['life'] -= p['decay']
                if p['life'] <= 0:
                    self.particles.remove(p)
        
        def draw(self, painter):
            """Draw particles using QPainter."""
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QColor, QBrush
            
            for p in self.particles:
                alpha = int(p['life'] * 255)
                color = QColor(0, 255, 255, alpha)
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(int(p['x']), int(p['y']), int(p['size']), int(p['size']))

logger = logging.getLogger(__name__)

class OrderBookWidget(CyberpunkRGBBorderWidget if HAS_CYBERPUNK else ResizableWidget):
    """Widget for displaying order book data (bids and asks) with cyberpunk styling.
    
    Features:
    - Animated RGB glowing borders
    - Neon glow effects on price data
    - Particle animations for price changes
    - Strict Redis Quantum Nexus integration
    """
    
    def __init__(self, parent=None, event_bus=None, symbol=None):
        """Initialize the OrderBookWidget with cyberpunk styling.
        
        Args:
            parent: Parent widget
            event_bus: Event bus for communication
            symbol: Trading symbol to display order book for
        """
        # Initialize with cyberpunk styling if available
        if HAS_CYBERPUNK:
            CyberpunkRGBBorderWidget.__init__(self, parent=parent)
            ResizableWidget.__init__(self, parent=parent, min_width=300, min_height=300)
        else:
            ResizableWidget.__init__(self, parent=parent, min_width=300, min_height=300)
            
        self.event_bus = event_bus
        self.symbol = symbol or ""
        
        # Setup particle system for advanced visual effects
        if HAS_CYBERPUNK:
            self.particle_system = CyberpunkParticleSystem(max_particles=50)
            self._animations_enabled = True
            self._animation_interval_ms = 33
            self.animation_timer = QTimer(self)
            self.animation_timer.timeout.connect(self._update_animations)
            self._sync_animation_timer()
            
        # Initialize Redis Quantum Nexus connection with strict requirements
        try:
            import redis
            self.redis_conn = redis.Redis(
                host="localhost",
                port=6380,  # Kingdom AI strictly requires port 6380
                password="QuantumNexus2025",  # Required password for Kingdom AI
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection with ping - strict enforcement, no fallbacks
            if not self.redis_conn.ping():
                error_msg = "Redis Quantum Nexus connection failed (ping failed)"
                logger.critical(error_msg)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self,
                    "Critical Error",
                    "Redis Quantum Nexus connection failed. Kingdom AI requires Redis to function. System will exit."
                )
                import sys
                sys.exit(1)  # Halt system immediately as required by Kingdom AI specs
                
            logger.info("Successfully connected to Redis Quantum Nexus on port 6380")
            
        except Exception as e:
            error_msg = f"Redis Quantum Nexus connection error: {str(e)}"
            logger.critical(error_msg)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Critical Error",
                f"Failed to connect to Redis Quantum Nexus: {str(e)}\n\nKingdom AI requires Redis to function. System will exit."
            )
            import sys
            sys.exit(1)  # Halt system immediately as required
        
        self._init_ui()
        
        # Subscribe to events if event bus is provided
        if self.event_bus:
            self._subscribe_to_events()
    
    def _init_ui(self):
        """Initialize the UI components with cyberpunk styling."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)  # Increased spacing for cyberpunk aesthetic
        
        # Create a title with cyberpunk styling
        self.title_label = QLabel(f"Order Book: {self.symbol}")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("cyberpunk_title")
        
        # Apply cyberpunk font styling
        title_font = QFont("Consolas", 12, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        
        # Apply neon glow effect to title
        if HAS_CYBERPUNK:
            glow_effect = CyberpunkEffect.create_glow_effect(
                QColor(CYBERPUNK_THEME["accent"]), intensity=10, spread=10
            )
            self.title_label.setGraphicsEffect(glow_effect)
        
        # Create tables for bids and asks with cyberpunk styling
        self.bids_table = QTableWidget(0, 3)
        self.asks_table = QTableWidget(0, 3)
        
        # Set headers
        headers = ["Price", "Amount", "Total"]
        self.bids_table.setHorizontalHeaderLabels(headers)
        self.asks_table.setHorizontalHeaderLabels(headers)
        
        # Configure header and columns with cyberpunk styling
        for table in [self.bids_table, self.asks_table]:
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            
            # Apply cyberpunk styling to tables
            if HAS_CYBERPUNK:
                CyberpunkStyle.apply_to_widget(table, "data_table")
            else:
                # Fallback styling
                table.setStyleSheet(
                    "QTableWidget {background-color: #0F111A; color: #00FFFF; border: 1px solid #33CCFF;}"
                    "QHeaderView::section {background-color: #1A1C2C; color: #FF00FF; border: 1px solid #33CCFF;}"
                    "QTableWidget::item {border-bottom: 1px solid #33CCFF30;}"
                )
            
            table.setAlternatingRowColors(True)
            
            # Add glow effect to tables
            if HAS_CYBERPUNK:
                glow = CyberpunkEffect.create_glow_effect(
                    QColor(CYBERPUNK_THEME["neutral"]), intensity=3, spread=5
                )
                table.setGraphicsEffect(glow)
        
        # Add a QFrame separator with neon effect
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(2)
        if HAS_CYBERPUNK:
            separator_glow = CyberpunkEffect.create_glow_effect(
                QColor(CYBERPUNK_THEME["accent"]), intensity=5, spread=3
            )
            separator.setGraphicsEffect(separator_glow)
            separator.setStyleSheet(f"background-color: {CYBERPUNK_THEME['accent']};")
        else:
            separator.setStyleSheet("background-color: #FF00FF;")
        
        # Add components to layout
        layout.addWidget(self.title_label)
        layout.addWidget(self.asks_table)
        layout.addWidget(separator)
        layout.addWidget(self.bids_table)
        self.setLayout(layout)
        
        # Set widget background and border style
        if not HAS_CYBERPUNK:  # Only apply if not using CyberpunkRGBBorderWidget
            self.setStyleSheet(
                "QWidget {background-color: #0F111A; border: 2px solid #33CCFF; border-radius: 5px;}"
            )
    
    def _subscribe_to_events(self):
        """Subscribe to event bus events."""
        if self.event_bus:
            # Subscribe to order book data events using safe scheduling
            from utils.async_qt_helper import schedule_multiple_subscriptions
            schedule_multiple_subscriptions([
                (self.event_bus, "trading.order_book", self._on_order_book_event),
                (self.event_bus, "trading.symbol_changed", self._on_symbol_changed_event),
            ], delay_ms=2900)
            logger.info(f"OrderBookWidget: Scheduled order book event subscriptions for {self.symbol}")
    
    def _unsubscribe_from_events(self):
        """Unsubscribe from event bus events."""
        if self.event_bus:
            try:
                # Unsubscribe from events (synchronous)
                self.event_bus.unsubscribe("trading.order_book", self._on_order_book_event)
                self.event_bus.unsubscribe("trading.symbol_changed", self._on_symbol_changed_event)
                logger.info("OrderBookWidget: Unsubscribed from order book events")
            except Exception as e:
                logger.error(f"OrderBookWidget: Error unsubscribing from events: {e}")
    
    def _on_order_book_event(self, event_data):
        """Handle order book events from the event bus."""
        # Only process data for our currently selected symbol
        if 'symbol' in event_data and event_data['symbol'] == self.symbol:
            self.update_data(event_data)
    
    def _on_symbol_changed_event(self, event_data):
        """Handle symbol change events from the event bus."""
        if 'symbol' in event_data:
            old_symbol = self.symbol
            self.symbol = event_data['symbol']
            logger.info(f"OrderBookWidget: Symbol changed from {old_symbol} to {self.symbol}")
            # Clear the order book when symbol changes
            self.clear()
            self._unsubscribe_from_events()
            self._subscribe_to_events()
            
    def _update_animations(self):
        """Update all animations and particle effects for cyberpunk visual style."""
        if HAS_CYBERPUNK:
            if hasattr(self, '_update_animation'):
                self._update_animation()
            
            if hasattr(self, 'particle_system'):
                self.particle_system.update()
                self.update()  # Trigger widget repaint

    def _should_animations_run(self) -> bool:
        if not HAS_CYBERPUNK:
            return False
        if not getattr(self, '_animations_enabled', True):
            return False
        if not self.isVisible():
            return False
        try:
            window = self.window()
            if window is not None and window.isMinimized():
                return False
        except Exception:
            pass
        return True

    def _sync_animation_timer(self):
        try:
            timer = getattr(self, 'animation_timer', None)
            if timer is None:
                return

            if self._should_animations_run():
                if not timer.isActive():
                    timer.start(getattr(self, '_animation_interval_ms', 33))
            else:
                if timer.isActive():
                    timer.stop()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_animation_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_animation_timer()
    
    def paintEvent(self, event):
        """Override paint event to draw custom cyberpunk effects."""
        if HAS_CYBERPUNK:
            if isinstance(self, CyberpunkRGBBorderWidget):
                super(OrderBookWidget, self).paintEvent(event)
            else:
                super().paintEvent(event)
                
            if hasattr(self, 'particle_system'):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                self.particle_system.draw(painter)
                painter.end()
        else:
            super().paintEvent(event)
    
    def _emit_particles(self, x, y, price_change_type):
        """Emit particles for visual effect on price changes.
        
        Args:
            x: X coordinate to emit particles
            y: Y coordinate to emit particles
            price_change_type: 'increase' or 'decrease' to determine particle color
        """
        if HAS_CYBERPUNK and hasattr(self, 'particle_system'):
            color = QColor(CYBERPUNK_THEME["positive"]) if price_change_type == "increase" else QColor(CYBERPUNK_THEME["negative"])
            count = random.randint(5, 15)  # Random number of particles
            self.particle_system.emit(x, y, count)
    
    def update_data(self, data: Dict[str, Any]):
        """Update the order book tables with new data and cyberpunk styling.
        
        Args:
            data: Order book data containing bids and asks
        """
        # Store old data for comparison (to animate price changes)
        old_bids = {}
        old_asks = {}
        
        for row in range(self.bids_table.rowCount()):
            price_item = self.bids_table.item(row, 0)
            if price_item:
                old_bids[price_item.text()] = row
                
        for row in range(self.asks_table.rowCount()):
            price_item = self.asks_table.item(row, 0)
            if price_item:
                old_asks[price_item.text()] = row
        
        # Clear the tables
        self.bids_table.setRowCount(0)
        self.asks_table.setRowCount(0)
        
        # Skip if no data
        if not data or not isinstance(data, dict):
            return
            
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        # Update the title with symbol
        if self.symbol and hasattr(self, 'title_label'):
            self.title_label.setText(f"Order Book: {self.symbol}")
        
        # Process bids (buy orders) - sort by price descending
        bids.sort(key=lambda x: float(x[0]), reverse=True)
        for i, bid in enumerate(bids[:10]):  # Show top 10 bids
            self._add_order_row(self.bids_table, bid, "bid", i, old_bids)
            
        # Process asks (sell orders) - sort by price ascending
        asks.sort(key=lambda x: float(x[0]))
        for i, ask in enumerate(asks[:10]):  # Show top 10 asks
            self._add_order_row(self.asks_table, ask, "ask", i, old_asks)
            
        # Update Redis with order book data
        try:
            # Store the latest data in Redis Quantum Nexus
            self.redis_conn.hset(
                f"kingdom:orderbook:{self.symbol}",
                "last_update",
                str(asyncio.get_event_loop().time())
            )
            
            # Store bid/ask counts for analytics
            self.redis_conn.hset(
                f"kingdom:orderbook:{self.symbol}",
                "bid_count",
                str(len(bids))
            )
            
            self.redis_conn.hset(
                f"kingdom:orderbook:{self.symbol}",
                "ask_count",
                str(len(asks))
            )
        except Exception as e:
            # If Redis fails, system must halt (Kingdom AI requirement)
            logger.critical(f"Redis Quantum Nexus update failed: {e}")
            import sys
            sys.exit(1)
    
    def _add_order_row(self, table, order_data, order_type, row_idx, old_data):
        """Add a row to the order book table with cyberpunk styling.
        
        Args:
            table: Target table (bids or asks)
            order_data: The order data (price, size)
            order_type: 'bid' or 'ask'
            row_idx: Table row index
            old_data: Previous order data for comparison
        """
        table.insertRow(row_idx)
        
        price = float(order_data[0])
        size = float(order_data[1])
        total = price * size
        
        # Format with appropriate precision
        price_str = f"{price:.2f}"
        size_str = f"{size:.6f}"
        total_str = f"{total:.6f}"
        
        # Create items with cyberpunk styling
        price_item = QTableWidgetItem(price_str)
        size_item = QTableWidgetItem(size_str)
        total_item = QTableWidgetItem(total_str)
        
        # Set colors based on type (bid/ask) with cyberpunk neon colors
        if order_type == 'bid':
            color = QColor(CYBERPUNK_THEME["positive"])  # Neon green for bids
        else:
            color = QColor(CYBERPUNK_THEME["negative"])  # Neon red/pink for asks
        
        price_item.setForeground(QBrush(color))
        
        # Set item background with subtle gradient
        if HAS_CYBERPUNK:
            gradient = QLinearGradient(0, 0, 0, 30)
            if order_type == 'bid':
                gradient.setColorAt(0, QColor(0, 20, 10))
                gradient.setColorAt(1, QColor(0, 30, 15))
            else:
                gradient.setColorAt(0, QColor(20, 0, 10))
                gradient.setColorAt(1, QColor(30, 0, 15))
            
            brush = QBrush(gradient)
            price_item.setBackground(brush)
            size_item.setBackground(brush)
            total_item.setBackground(brush)
        
        # Check for price changes and trigger particle animation
        if price_str in old_data:
            old_row = old_data[price_str]
            if old_row != row_idx:
                price_change_type = "increase" if old_row > row_idx else "decrease"
                if HAS_CYBERPUNK:
                    # Get item position for particle animation
                    rect = table.visualItemRect(table.item(row_idx, 0)) if table.item(row_idx, 0) else QRect(0, 0, 0, 0)
                    pos_x = rect.x() + rect.width() // 2
                    pos_y = rect.y() + rect.height() // 2
                    self._emit_particles(pos_x, pos_y, price_change_type)
        
        # Add items to table
        table.setItem(row_idx, 0, price_item)
        table.setItem(row_idx, 1, size_item)
        table.setItem(row_idx, 2, total_item)
    
    def _add_separator_row(self):
        """Add a separator row between asks and bids."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Create a single cell that spans all columns
        separator = QTableWidgetItem("-" * 30)
        separator.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        separator.setBackground(QColor("#E0E0E0"))
        
        self.table.setSpan(row, 0, 1, 3)  # Span all 3 columns
        self.table.setItem(row, 0, separator)
    
    def clear(self) -> None:
        """Clear all data from the widget."""
        self.table.setRowCount(0)
        
    def closeEvent(self, event):
        """Handle close event for proper cleanup."""
        # Unsubscribe from events when widget is closed
        self._unsubscribe_from_events()
        # Let parent class handle the rest
        super().closeEvent(event)
