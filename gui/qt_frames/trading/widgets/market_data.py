"""
Cyberpunk Market Data Widget

This module contains the MarketDataWidget class for displaying real-time
market data in the trading interface with advanced cyberpunk styling
featuring RGB borders, glow effects, and futuristic aesthetics.
"""
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout,
    QLabel, QHBoxLayout, QFrame, QGraphicsDropShadowEffect,
    QLineEdit, QComboBox, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint, QRect, QSize
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPen, QLinearGradient, QGradient
import numpy as np
from datetime import datetime
import logging
logger = logging.getLogger(__name__)
import time
import math
import sys
import os
from decimal import Decimal
from core.event_bus import EventBus

# Import cyberpunk styling components
try:
    from gui.cyberpunk_style import CyberpunkStyle, CyberpunkEffect, CyberpunkRGBBorderWidget, CyberpunkParticleSystem, CYBERPUNK_THEME  # type: ignore
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
    
    # Create fallback RGB border widget if cyberpunk_style.py is not available
    class CyberpunkRGBBorderWidget(ResizableWidget):
        pass
    
    class CyberpunkParticleSystem:
        def __init__(self, max_particles=100): pass
        def emit(self, x, y, count): pass
        def update(self): pass
        def draw(self, painter): pass

import redis
import sys

# Connect to Redis Quantum Nexus - required with no fallbacks
def connect_to_redis():
    """Connect to Redis Quantum Nexus - required with no fallbacks"""
    try:
        redis_client = redis.Redis(
            host="localhost", 
            port=6380,  # Required specific port
            password="QuantumNexus2025",  # Required password
            decode_responses=True,
            socket_connect_timeout=3
        )
        # Test connection
        if not redis_client.ping():
            logger.warning("Redis Quantum Nexus connection unhealthy - widget will use fallback mode")
            return None
            
        logger.info("Successfully connected to Redis Quantum Nexus")
        return redis_client
    except Exception as e:
        logger.warning(f"Redis Quantum Nexus not available: {e} - widget will use fallback mode")
        return None

# Global Redis client - graceful fallback if not available
REDIS_CLIENT = connect_to_redis()

class MarketDataWidget(CyberpunkRGBBorderWidget if HAS_CYBERPUNK else ResizableWidget):  # type: ignore[misc]
    """
    Widget for displaying real-time market data including price, volume, and order book.
    """
    # Signals
    symbol_changed = pyqtSignal(str)
    timeframe_changed = pyqtSignal(str)
    
    def __init__(self, parent=None, event_bus=None):
        """Initialize the MarketDataWidget.
        
        Args:
            parent: Parent widget
            event_bus: Event bus for communication
        """
        # Initialize with cyberpunk RGB border if available, otherwise use base class
        if HAS_CYBERPUNK:
            super().__init__(parent=parent, min_width=400, min_height=300, border_width=2)
        else:
            super().__init__(parent=parent, min_width=400, min_height=300)
            
        self.event_bus = event_bus
        self.symbol = ""
        self.timeframe = "1m"
        self.symbol_index = []
        
        # RGB animation properties
        self._animations_enabled = True
        self._animation_interval_ms = 50
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self._sync_animation_timer()
        self.animation_phase = 0
        
        # Particle system for price changes
        self.particle_system = CyberpunkParticleSystem(max_particles=50)
        self.last_price = 0
        
        # Additional styling properties
        self.cyberpunk_fonts = {
            'title': QFont("Orbitron", 12, QFont.Weight.Bold),
            'data': QFont("Share Tech Mono", 10),
            'price': QFont("Orbitron", 22, QFont.Weight.Bold),
            'change': QFont("Share Tech Mono", 11)
        }
        
        # Fallback to standard fonts if custom ones not available
        if not self.cyberpunk_fonts['title'].exactMatch():
            self.cyberpunk_fonts['title'] = QFont("Arial", 12, QFont.Weight.Bold)
            self.cyberpunk_fonts['data'] = QFont("Consolas", 10) 
            self.cyberpunk_fonts['price'] = QFont("Arial", 22, QFont.Weight.Bold)
            self.cyberpunk_fonts['change'] = QFont("Consolas", 11)
        
        # Initialize Redis connection for realtime data
        self.redis_client = None
        try:
            self.redis_client = REDIS_CLIENT
        except:
            logger.warning("Using local market data only - Redis unavailable")
        
        self._init_ui()
        self._setup_connections()
        
        # Subscribe to market data events if event bus is provided
        if self.event_bus:
            self._subscribe_to_events()
    
    def _init_ui(self):
        """Initialize the user interface with cyberpunk styling."""
        # Apply cyberpunk styling to widget
        self.setObjectName("CyberpunkMarketData")
        
        # Main layout with cyberpunk styling
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # Increased margins for glowing border effect
        main_layout.setSpacing(8)  # Increased spacing for futuristic look
        
        # Header with symbol and timeframe - cyberpunk styled
        header_frame = QFrame()
        header_frame.setObjectName("CyberpunkHeaderFrame")
        header_frame.setStyleSheet(f"""
            QFrame#CyberpunkHeaderFrame {{
                background-color: {CYBERPUNK_THEME['background']};
                border: 1px solid {CYBERPUNK_THEME['accent']};
                border-radius: 5px;
            }}
        """)
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 8, 8, 8)
        
        # Symbol label with cyberpunk font and glow
        self.symbol_label = QLabel("SYMBOL: N/A")
        self.symbol_label.setFont(self.cyberpunk_fonts['title'])
        self.symbol_label.setStyleSheet(f"""
            color: {CYBERPUNK_THEME['foreground']};
            padding: 2px;
        """)
        symbol_glow = CyberpunkEffect.create_glow_effect(QColor(CYBERPUNK_THEME['foreground']), 10, 5)
        self.symbol_label.setGraphicsEffect(symbol_glow)
        header_layout.addWidget(self.symbol_label)
        
        # Timeframe selector with cyberpunk styling
        self.timeframe_label = QLabel("TF: 1m")
        self.timeframe_label.setFont(self.cyberpunk_fonts['data'])
        self.timeframe_label.setStyleSheet(f"""
            color: {CYBERPUNK_THEME['neutral']};
            padding: 2px;
            border: 1px solid {CYBERPUNK_THEME['neutral']};
            border-radius: 4px;
        """)
        header_layout.addWidget(self.timeframe_label)
        
        header_layout.addStretch()
        
        # Price display with cyberpunk styling and glow effect
        self.price_label = QLabel("-")
        self.price_label.setFont(self.cyberpunk_fonts['price'])
        self.price_label.setStyleSheet(f"""
            color: {CYBERPUNK_THEME['positive']};
            padding: 5px;
        """)
        price_glow = CyberpunkEffect.create_glow_effect(QColor(CYBERPUNK_THEME['positive']), 15, 8)
        self.price_label.setGraphicsEffect(price_glow)
        header_layout.addWidget(self.price_label)
        
        # Price change with cyberpunk styling
        self.change_label = QLabel("+0.00%")
        self.change_label.setFont(self.cyberpunk_fonts['change'])
        self.change_label.setStyleSheet(f"""
            color: {CYBERPUNK_THEME['positive']};
            padding: 2px;
        """)
        header_layout.addWidget(self.change_label)
        
        main_layout.addWidget(header_frame)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search symbol...")
        self.search_results = QComboBox()
        self.search_results.setEditable(False)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_results)
        main_layout.addLayout(search_layout)
        
        # Cyberpunk separator with glow
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet(f"""
            color: {CYBERPUNK_THEME['accent']};
            background-color: {CYBERPUNK_THEME['accent']};
            min-height: 1px;
        """)
        separator_glow = CyberpunkEffect.create_glow_effect(QColor(CYBERPUNK_THEME['accent']), 8, 5)
        separator.setGraphicsEffect(separator_glow)
        main_layout.addWidget(separator)
        
        # Data table with cyberpunk styling
        table_frame = QFrame()
        table_frame.setObjectName("CyberpunkTableFrame")
        table_frame.setStyleSheet(f"""
            QFrame#CyberpunkTableFrame {{
                background-color: {CYBERPUNK_THEME['background']};
                border: 1px solid {CYBERPUNK_THEME['neutral']};
                border-radius: 5px;
            }}
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(8, 8, 8, 8)
        
        self.table = QTableWidget(0, 2)
        self.table.setFont(self.cyberpunk_fonts['data'])
        self.table.setHorizontalHeaderLabels(["Field", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {CYBERPUNK_THEME['background']};
                alternate-background-color: rgba(30, 35, 40, 150);
                color: {CYBERPUNK_THEME['foreground']};
                gridline-color: {CYBERPUNK_THEME['accent']};
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: rgba(0, 150, 255, 100);
                color: {CYBERPUNK_THEME['foreground']};
            }}
            QHeaderView::section {{
                background-color: {CYBERPUNK_THEME['background']};
                color: {CYBERPUNK_THEME['accent']};
                padding: 5px;
                border: 1px solid {CYBERPUNK_THEME['neutral']};
            }}
        """)
        
        # Add data rows with cyberpunk styling
        self._add_table_row("Open", "-")
        self._add_table_row("High", "-")
        self._add_table_row("Low", "-")
        self._add_table_row("Close", "-")
        self._add_table_row("Volume", "-")
        self._add_table_row("Last Update", "-")
        
        table_layout.addWidget(self.table)
        main_layout.addWidget(table_frame)
        
        # Set overall widget style
        self.setStyleSheet(f"""
            QWidget#CyberpunkMarketData {{
                background-color: {CYBERPUNK_THEME['background']};
                color: {CYBERPUNK_THEME['foreground']};
                border-radius: 10px;
            }}
        """)
        
        # Custom context menu for additional options
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    
    def _setup_connections(self):
        """Set up signal connections."""
        # Connect UI element signals here as needed
        if HAS_CYBERPUNK:
            self.customContextMenuRequested.connect(self._show_context_menu)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_results.currentTextChanged.connect(self._on_search_result_selected)
            
    def _update_animation(self):
        """Update the RGB animation for cyberpunk effects"""
        if not self._should_animations_run():
            self._sync_animation_timer()
            return
            
        # Update RGB cycle animation
        self.animation_phase += 0.05
        if self.animation_phase > 2 * math.pi:
            self.animation_phase -= 2 * math.pi
            
        # Update particles
        self.particle_system.update()
        
        # Trigger repaint for animation
        self.update()

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
                    timer.start(getattr(self, '_animation_interval_ms', 50))
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

    def changeEvent(self, event):
        super().changeEvent(event)
        self._sync_animation_timer()
        
    def _show_context_menu(self, position):
        """Show cyberpunk context menu"""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {CYBERPUNK_THEME['background']};
                color: {CYBERPUNK_THEME['foreground']};
                border: 1px solid {CYBERPUNK_THEME['accent']};
                border-radius: 3px;
            }}
            QMenu::item {{
                padding: 5px 20px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: rgba(0, 150, 255, 100);
            }}
        """)
        
        refresh_action = menu.addAction("Refresh Data")
        timeframe_menu = menu.addMenu("Timeframe")
        
        for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
            timeframe_action = timeframe_menu.addAction(tf)
        
        # Show particles on menu display
        self.particle_system.emit(position.x(), position.y(), 10)
        
        menu.exec(self.mapToGlobal(position))
        
    def _subscribe_to_events(self):
        """Subscribe to event bus events."""
        if self.event_bus:
            # Subscribe to market data events using safe scheduling
            from utils.async_qt_helper import schedule_multiple_subscriptions
            schedule_multiple_subscriptions([
                (self.event_bus, "trading.market_data", self._on_market_data_event),
                # MarketAPI + other feeds publish per-tick updates on this topic
                (self.event_bus, "market:price_update", self._on_market_price_update_event),
                (self.event_bus, "trading.symbol_changed", self._on_symbol_changed_event),
                (self.event_bus, "trading.symbol_index", self._on_symbol_index_event),
            ], delay_ms=3000)
            logger.info(f"MarketDataWidget: Scheduled market data event subscriptions for {self.symbol}")
    
    def _unsubscribe_from_events(self):
        """Unsubscribe from event bus events."""
        if self.event_bus:
            try:
                # Unsubscribe from market data events (synchronous)
                self.event_bus.unsubscribe("trading.market_data", self._on_market_data_event)
                self.event_bus.unsubscribe("market:price_update", self._on_market_price_update_event)
                self.event_bus.unsubscribe("trading.symbol_changed", self._on_symbol_changed_event)
                self.event_bus.unsubscribe("trading.symbol_index", self._on_symbol_index_event)
                logger.info("MarketDataWidget: Unsubscribed from market data events")
            except Exception as e:
                logger.error(f"MarketDataWidget: Error unsubscribing from events: {e}")
    
    def _on_market_data_event(self, event_data):
        """Handle market data events from the event bus."""
        # Only process data for our currently selected symbol
        if 'symbol' in event_data and event_data['symbol'] == self.symbol:
            self.update_data(event_data)

    def _on_market_price_update_event(self, event_data):
        """Handle per-tick market updates from MarketAPI (market:price_update)."""
        try:
            if not isinstance(event_data, dict):
                return
            symbol = event_data.get("symbol")
            if symbol and self.symbol and str(symbol).upper() != str(self.symbol).upper():
                return
            # Normalize to MarketDataWidget expected keys
            payload = {
                "symbol": symbol or self.symbol,
                "price": event_data.get("price") or event_data.get("last"),
                "bid": event_data.get("bid"),
                "ask": event_data.get("ask"),
                "volume": event_data.get("volume") or event_data.get("quoteVolume") or event_data.get("baseVolume"),
                "change": event_data.get("change") or event_data.get("percentage"),
                "exchange": event_data.get("exchange"),
                "updated": event_data.get("updated") or event_data.get("timestamp"),
            }
            # Drop empty keys so update_data doesn't mis-handle types
            payload = {k: v for k, v in payload.items() if v is not None}
            if "symbol" in payload and payload.get("symbol"):
                self.update_data(payload)
        except Exception as e:
            logger.debug(f"MarketDataWidget: market:price_update parse error: {e}")
    
    def _on_symbol_changed_event(self, event_data):
        """Handle symbol change events from the event bus."""
        if 'symbol' in event_data:
            self.symbol = event_data['symbol']
            # Clear existing data when symbol changes
            self.clear()
            # Update symbol display
            self.symbol_label.setText(f"SYMBOL: {self.symbol}")

    def _on_symbol_index_event(self, event_data):
        """Handle symbol index events and populate search results."""
        symbols = event_data.get("symbols") if isinstance(event_data, dict) else None
        if not isinstance(symbols, list):
            return
        self.symbol_index = symbols
        self.search_results.blockSignals(True)
        self.search_results.clear()
        for entry in symbols[:200]:
            sym = str(entry.get("symbol") or "").upper()
            if sym:
                self.search_results.addItem(sym)
        self.search_results.blockSignals(False)
        if not self.symbol and symbols:
            first = symbols[0]
            sym0 = str(first.get("symbol") or "").upper()
            if sym0:
                self.search_results.setCurrentText(sym0)
                self._set_active_symbol(sym0, first.get("asset_class"))
    
    def _add_table_row(self, field: str, value: str):
        """Add a row to the data table."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Field column
        field_item = QTableWidgetItem(field)
        field_item.setFlags(field_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        field_item.setForeground(QColor("#888"))
        
        # Value column
        value_item = QTableWidgetItem(value)
        value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.table.setItem(row, 0, field_item)
        self.table.setItem(row, 1, value_item)

    def _on_search_text_changed(self, text: str):
        """Filter search results based on user input over the symbol index."""
        pattern = str(text or "").upper()
        if not self.symbol_index:
            return
        self.search_results.blockSignals(True)
        self.search_results.clear()
        count = 0
        for entry in self.symbol_index:
            sym = str(entry.get("symbol") or "").upper()
            if not sym:
                continue
            if pattern and pattern not in sym:
                continue
            self.search_results.addItem(sym)
            count += 1
            if count >= 200:
                break
        self.search_results.blockSignals(False)

    def _on_search_result_selected(self, symbol: str):
        """Handle selection from the search results combo and publish symbol change."""
        sym = str(symbol or "").upper()
        if not sym:
            return
        if sym == self.symbol:
            return
        asset_class = None
        for entry in self.symbol_index:
            if str(entry.get("symbol") or "").upper() == sym:
                asset_class = entry.get("asset_class")
                break
        self._set_active_symbol(sym, asset_class)

    def _set_active_symbol(self, symbol: str, asset_class: Optional[str]):
        """Set the active symbol locally and broadcast trading.symbol_changed."""
        self.symbol = symbol
        self.clear()
        self.symbol_label.setText(f"SYMBOL: {self.symbol}")
        if self.event_bus:
            payload = {"symbol": self.symbol}
            if asset_class:
                payload["asset_class"] = asset_class
            try:
                self.event_bus.publish("trading.symbol_changed", payload)
                # Also subscribe MarketAPI to this symbol so per-tick updates can flow.
                # MarketAPI listens to market.subscribe and will start publishing market:price_update.
                self.event_bus.publish("market.subscribe", {"symbol": self.symbol})
            except Exception as e:
                logger.error(f"MarketDataWidget: failed to publish symbol_changed: {e}")
    
    def _update_table_row(self, row: int, value: str, color: Optional[QColor] = None):
        """Update a row in the data table with cyberpunk animation effect."""
        if 0 <= row < self.table.rowCount():
            item = self.table.item(row, 1)
            if item:
                # Store old value for animation effect
                old_value = item.text()
                item.setText(str(value))
                
                # Apply cyberpunk color effect
                if color:
                    item.setForeground(color)
                else:
                    # Use default cyberpunk color scheme
                    item.setForeground(QColor(CYBERPUNK_THEME['foreground']))
                
                # Add particle effect on value change (if significant)
                if old_value != "-" and old_value != value and HAS_CYBERPUNK:
                    # Get item rectangle in table coordinates
                    rect = self.table.visualItemRect(item)
                    # Convert to widget coordinates
                    global_rect = self.table.mapToParent(rect.topLeft())
                    # Emit particles at change location
                    self.particle_system.emit(global_rect.x() + rect.width()/2, 
                                           global_rect.y() + rect.height()/2, 5)
    
    def update_data(self, data: Dict[str, Any]) -> None:
        """
        Update the widget with new market data with cyberpunk animation effects.
        
        Args:
            data: Dictionary containing market data with keys like 'symbol', 'price', 'change', etc.
        """
        try:
            # Redis pub/sub update - publish market data if Redis is available
            if self.redis_client and 'symbol' in data:
                try:
                    # Convert data to string for Redis
                    import json
                    redis_data = json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "data": data,
                        "source": "market_data_widget"
                    })
                    # Publish to Redis Quantum Nexus
                    self.redis_client.publish(f"market:data:{data['symbol']}", redis_data)
                except Exception as e:
                    logger.warning(f"Redis Quantum Nexus publication error: {e}")
            
            # Update symbol if changed
            if 'symbol' in data and data['symbol'] != self.symbol:
                self.symbol = data['symbol']
                self.symbol_label.setText(f"SYMBOL: {self.symbol}")
                # Emit particles on symbol change for visual effect
                if HAS_CYBERPUNK:
                    rect = self.symbol_label.rect()
                    center_x = rect.width() / 2
                    center_y = rect.height() / 2
                    self.particle_system.emit(center_x, center_y, 15)
                self.symbol_changed.emit(self.symbol)
            
            # Update price and change with cyberpunk animation
            if 'price' in data:
                price = float(data['price'])
                old_price = self.last_price
                self.last_price = price
                self.price_label.setText(f"{price:,.2f}")
                
                # Emit particles on significant price changes
                if HAS_CYBERPUNK and old_price > 0:
                    price_change_pct = abs((price - old_price) / old_price) * 100
                    if price_change_pct > 0.1:  # Only animate meaningful changes
                        # Calculate particle count based on change magnitude
                        particle_count = min(int(price_change_pct * 5), 30)
                        rect = self.price_label.rect()
                        self.particle_system.emit(
                            rect.width() / 2, 
                            rect.height() / 2, 
                            particle_count
                        )
                
                # Update price color based on change with cyberpunk colors
                if 'change' in data:
                    change = float(data['change'])
                    change_pct = float(data.get('change_percent', 0))
                    
                    if change > 0:
                        # Cyberpunk positive color (neon green)
                        color = QColor(CYBERPUNK_THEME['positive'])
                        change_text = f"+{change:.2f} ({change_pct:+.2f}%)"
                        price_effect = CyberpunkEffect.create_glow_effect(color, 15, 8)
                    elif change < 0:
                        # Cyberpunk negative color (neon red/pink)
                        color = QColor(CYBERPUNK_THEME['negative'])
                        change_text = f"{change:.2f} ({change_pct:+.2f}%)"
                        price_effect = CyberpunkEffect.create_glow_effect(color, 15, 8)
                    else:
                        # Cyberpunk neutral color (blue/cyan)
                        color = QColor(CYBERPUNK_THEME['neutral'])
                        change_text = f"{change:.2f} ({change_pct:+.2f}%)"
                        price_effect = CyberpunkEffect.create_glow_effect(color, 10, 5)
                    
                    self.change_label.setText(change_text)
                    self.change_label.setStyleSheet(
                        f"color: {color.name()}; padding: 2px;"
                    )
                    self.price_label.setStyleSheet(
                        f"color: {color.name()}; padding: 5px;"
                    )
                    
                    # Apply glow effect
                    self.price_label.setGraphicsEffect(price_effect)
            
            # Update OHLCV data with cyberpunk styling
            if 'open' in data:
                self._update_table_row(0, f"{float(data['open']):,.2f}", QColor(CYBERPUNK_THEME['foreground']))
            if 'high' in data:
                self._update_table_row(1, f"{float(data['high']):,.2f}", QColor(CYBERPUNK_THEME['positive']))
            if 'low' in data:
                self._update_table_row(2, f"{float(data['low']):,.2f}", QColor(CYBERPUNK_THEME['negative']))
            if 'close' in data:
                self._update_table_row(3, f"{float(data['close']):,.2f}", QColor(CYBERPUNK_THEME['foreground']))
            if 'volume' in data:
                self._update_table_row(4, f"{float(data['volume']):,.2f}", QColor(CYBERPUNK_THEME['accent']))
            
            # Update last update time with cyberpunk styling
            self._update_table_row(5, datetime.now().strftime("%H:%M:%S"), QColor(CYBERPUNK_THEME['neutral']))
            
        except Exception as e:
            logger.error(f"Error updating market data: {e}", exc_info=True)
    
    def clear(self) -> None:
        """Clear all data from the widget with cyberpunk styling."""
        self.symbol_label.setText("SYMBOL: N/A" if not self.symbol else f"SYMBOL: {self.symbol}")
        self.price_label.setText("-")
        self.change_label.setText("+0.00%")
        
        # Apply cyberpunk styling
        neutral_color = QColor(CYBERPUNK_THEME['neutral'])
        self.change_label.setStyleSheet(f"color: {neutral_color.name()}; padding: 2px;")
        self.price_label.setStyleSheet(f"color: {neutral_color.name()}; padding: 5px;")
        
        # Reset price effect to neutral
        neutral_effect = CyberpunkEffect.create_glow_effect(neutral_color, 10, 5)
        self.price_label.setGraphicsEffect(neutral_effect)
        
        # Clear table data with cyberpunk styling
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item:
                item.setText("-")
                item.setForeground(QColor(CYBERPUNK_THEME['foreground']))
        
        # Add particle reset effect
        if HAS_CYBERPUNK:
            self.particle_system.emit(self.width() / 2, self.height() / 2, 20)
                
    def closeEvent(self, event):
        """Handle close event for proper cleanup."""
        # Stop animation timer
        if self.animation_timer.isActive():
            self.animation_timer.stop()
        
        # Unsubscribe from events when widget is closed
        self._unsubscribe_from_events()
        
        # Update Redis status on shutdown
        try:
            if hasattr(self, 'redis_client') and self.redis_client:
                self.redis_client.publish("kingdom:events:component_shutdown", "market_data_widget")
        except Exception as e:
            logger.critical(f"Redis connection error during shutdown: {e}")
            sys.exit(1)  # Enforce strict Redis policy - halt on any errors
        
        # Let parent class handle the rest
        super().closeEvent(event)
        
    def paintEvent(self, event):
        """Custom paint event for cyberpunk effects"""
        # Let the parent class handle basic painting
        super().paintEvent(event)
        
        # Only add custom painting if cyberpunk styling is available
        if HAS_CYBERPUNK:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw particles for price changes
            self.particle_system.draw(painter)
            
            # Optional: Add custom cyberpunk overlay effects here
            # e.g., scan lines, glitch effects, etc.
            
            # Draw scan lines (semi-transparent horizontal lines)
            painter.setOpacity(0.05)  # Very subtle effect
            scan_pen = QPen(QColor(CYBERPUNK_THEME['foreground']))
            scan_pen.setWidth(1)
            painter.setPen(scan_pen)
            
            for y in range(0, self.height(), 4):  # Every 4 pixels
                painter.drawLine(0, y, self.width(), y)
            
            painter.end()
