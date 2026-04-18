"""
Positions Widget

This module contains the PositionWidget class for displaying current trading positions.
"""
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QLabel, QMenu
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QBrush, QPainter
import logging
import asyncio
import random
import redis
import sys

from .base import ResizableWidget
from core.event_bus import EventBus

# Initialize logger first
logger = logging.getLogger(__name__)

# Check if cyberpunk styling is available
try:
    from gui.cyberpunk_style import CyberpunkRGBBorderWidget, CYBERPUNK_THEME, CyberpunkParticleSystem
    _base_class = CyberpunkRGBBorderWidget
    has_cyberpunk = True
    logger.info("Cyberpunk styling loaded successfully for PositionWidget")
except ImportError:
    _base_class = ResizableWidget
    has_cyberpunk = False
    CyberpunkParticleSystem = None
    logger.info("Using standard styling for PositionWidget (cyberpunk styling optional)")

# Logger already defined above

class PositionWidget(_base_class):  # type: ignore
    """Widget for displaying current trading positions."""
    
    def __init__(self, parent=None, event_bus=None):
        """Initialize the PositionWidget.
        
        Args:
            parent: Parent widget
            event_bus: Event bus for communication
        """
        # Initialize with cyberpunk border if available
        if has_cyberpunk:
            super().__init__(parent=parent, min_width=400, min_height=200)
        else:
            super().__init__(parent=parent, min_width=400, min_height=200)
            
        self.event_bus = event_bus
        self.redis_conn = None
        
        # Initialize Redis Quantum Nexus connection
        try:
            self.redis_conn = redis.Redis(  # type: ignore
                host='localhost',
                port=6380,  # Quantum Nexus port
                password='QuantumNexus2025',
                decode_responses=True
            )
            # Test connection
            self.redis_conn.ping()
            logger.info("PositionWidget: Redis Quantum Nexus connection established")
        except Exception as e:
            logger.critical(f"PositionWidget: Redis Quantum Nexus connection failed: {e}")
            # Halt system on Redis connection failure - no fallbacks allowed
            sys.exit(1)
            
        # Initialize particle system for visual effects
        if has_cyberpunk:
            self.particle_system = CyberpunkParticleSystem(max_particles=50)
            self._animations_enabled = True
            self._animation_interval_ms = 16
            # Animation timer
            self.animation_timer = QTimer(self)
            self.animation_timer.timeout.connect(self._update_animations)
            self._sync_animation_timer()
            
        self._init_ui()
        
        # Subscribe to position events if event bus is provided
        if self.event_bus:
            self._subscribe_to_events()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Title with cyberpunk style
        self.title_label = QLabel("Positions")
        if has_cyberpunk:
            self.title_label.setStyleSheet(f"""
                font-weight: bold; 
                font-size: 16px;
                color: {CYBERPUNK_THEME['text_bright']};
                background-color: transparent;
                border-bottom: 1px solid {CYBERPUNK_THEME['accent']};
                padding-bottom: 3px;
            """)
        else:
            self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            
        layout.addWidget(self.title_label)
        
        # Positions table with cyberpunk styling
        self.table = QTableWidget(0, 6)  # Symbol, Size, Entry, Mark, PnL, PnL%
        self.table.setHorizontalHeaderLabels(["Symbol", "Size", "Entry", "Mark", "PnL", "PnL%"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Apply cyberpunk styling to table
        if has_cyberpunk:
            self.table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {CYBERPUNK_THEME['bg_dark']};
                    color: {CYBERPUNK_THEME['text']};
                    gridline-color: {CYBERPUNK_THEME['accent']};
                    border: 1px solid {CYBERPUNK_THEME['border']};
                }}
                
                QTableWidget::item {{
                    border-bottom: 1px solid {CYBERPUNK_THEME['border_light']};
                }}
                
                QTableWidget::item:selected {{
                    background-color: {CYBERPUNK_THEME['selection']};
                }}
                
                QHeaderView::section {{
                    background-color: {CYBERPUNK_THEME['bg_header']};
                    color: {CYBERPUNK_THEME['accent']};
                    border: none;
                    padding: 4px;
                    font-weight: bold;
                }}
            """)
        
        layout.addWidget(self.table)
    
    def _subscribe_to_events(self):
        """Subscribe to event bus events."""
        if self.event_bus:
            # Subscribe to position update events using safe scheduling
            from utils.async_qt_helper import schedule_multiple_subscriptions
            schedule_multiple_subscriptions([
                (self.event_bus, "trading.position_update", self._on_position_update_event),
                (self.event_bus, "trading.positions", self._on_positions_event),
            ], delay_ms=2800)
            logger.info("PositionWidget: Scheduled position event subscriptions")
    
    def _unsubscribe_from_events(self):
        """Unsubscribe from event bus events."""
        if self.event_bus:
            try:
                # Unsubscribe immediately (cleanup can be synchronous)
                from PyQt6.QtCore import QTimer
                def unsub():
                    try:
                        # Synchronous unsubscribe (event_bus.unsubscribe is likely sync)
                        self.event_bus.unsubscribe("trading.position_update", self._on_position_update_event)
                        self.event_bus.unsubscribe("trading.positions", self._on_positions_event)
                        logger.info("PositionWidget: Unsubscribed from position events")
                    except Exception as e:
                        logger.error(f"Error: {e}")
                QTimer.singleShot(10, unsub)
            except Exception as e:
                logger.error(f"PositionWidget: Error unsubscribing from events: {e}")
    
    def _on_position_update_event(self, event_data):
        """Handle position update events from the event bus."""
        if isinstance(event_data, dict):
            # Single position update
            # Find if we already have this position
            position_found = False
            for row in range(self.table.rowCount()):
                symbol_item = self.table.item(row, 0)
                if symbol_item and symbol_item.text() == event_data.get('symbol'):
                    # Update the existing position
                    self.table.removeRow(row)
                    self._add_position_row(event_data)
                    position_found = True
                    break
            
            # If position not found, add it as new
            if not position_found:
                self._add_position_row(event_data)
    
    def _on_positions_event(self, event_data):
        """Handle positions list events from the event bus."""
        if isinstance(event_data, list):
            filtered = []
            for pos in event_data:
                if not isinstance(pos, dict):
                    continue
                filtered.append(pos)
            if not filtered:
                return
            self.update_data(filtered)
    
    def update_data(self, positions: List[Dict[str, Any]]) -> None:
        """
        Update the positions display.
        
        Args:
            positions: List of position dictionaries
        """
        try:
            self.table.setRowCount(0)  # Clear existing data
            
            for pos in positions:
                self._add_position_row(pos)
                
        except Exception as e:
            logger.error(f"Error updating positions: {e}", exc_info=True)
    
    def _add_position_row(self, position: Dict[str, Any]):
        """Add a row for a single position."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Extract position data
        asset_class = str(position.get('asset_class') or position.get('asset_type') or '').lower()
        symbol = position.get('symbol', 'N/A')
        size = float(position.get('size', 0))
        entry_price = float(position.get('entry_price', 0))
        mark_price = float(position.get('mark_price', entry_price))
        pnl = float(position.get('unrealized_pnl', 0))
        pnl_pct = (pnl / (abs(size) * entry_price)) * 100 if size != 0 and entry_price != 0 else 0
        
        # Get previous position if exists for animations
        prev_pnl = 0.0
        for prev_row in range(self.table.rowCount()):
            if prev_row != row and self.table.item(prev_row, 0) and self.table.item(prev_row, 0).text() == symbol:
                if self.table.item(prev_row, 4):
                    try:
                        prev_text = self.table.item(prev_row, 4).text().replace('+', '').replace(',', '')
                        prev_pnl = float(prev_text)
                    except (ValueError, AttributeError):
                        pass
                break
                
        # Symbol
        symbol_item = QTableWidgetItem(symbol)
        if asset_class:
            symbol_item.setData(Qt.ItemDataRole.UserRole, asset_class)
        if has_cyberpunk:
            symbol_item.setForeground(QColor(CYBERPUNK_THEME['text_bright']))
        
        # Size (colored based on long/short)
        size_item = QTableWidgetItem(f"{size:,.4f}")
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Entry price
        entry_item = QTableWidgetItem(f"{entry_price:,.2f}")
        entry_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Mark price
        mark_item = QTableWidgetItem(f"{mark_price:,.2f}")
        mark_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # PnL (colored based on profit/loss)
        pnl_item = QTableWidgetItem(f"{pnl:+,.2f}")
        pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # PnL %
        pnl_pct_item = QTableWidgetItem(f"{pnl_pct:+.2f}%")
        pnl_pct_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Set colors based on position and PnL with cyberpunk theme if available
        if has_cyberpunk:
            if size > 0:  # Long position
                size_item.setForeground(QColor(CYBERPUNK_THEME['positive']))
                pnl_color = QColor(CYBERPUNK_THEME['positive']) if pnl >= 0 else QColor(CYBERPUNK_THEME['negative'])
            else:  # Short position
                size_item.setForeground(QColor(CYBERPUNK_THEME['negative']))
                pnl_color = QColor(CYBERPUNK_THEME['positive']) if pnl >= 0 else QColor(CYBERPUNK_THEME['negative'])
        else:
            if size > 0:  # Long position
                size_item.setForeground(QColor("#4CAF50"))  # Green
                pnl_color = QColor("#4CAF50") if pnl >= 0 else QColor("#F44336")
            else:  # Short position
                size_item.setForeground(QColor("#F44336"))  # Red
                pnl_color = QColor("#4CAF50") if pnl >= 0 else QColor("#F44336")
        
        pnl_item.setForeground(pnl_color)
        pnl_pct_item.setForeground(pnl_color)
        
        # Add items to table
        self.table.setItem(row, 0, symbol_item)
        self.table.setItem(row, 1, size_item)
        self.table.setItem(row, 2, entry_item)
        self.table.setItem(row, 3, mark_item)
        self.table.setItem(row, 4, pnl_item)
        self.table.setItem(row, 5, pnl_pct_item)
        
        # Emit particles for significant PnL changes
        if has_cyberpunk and hasattr(self, 'particle_system') and abs(pnl - prev_pnl) > 1.0:
            # Get table cell rectangle for positioning particles
            rect = self.table.visualItemRect(pnl_item)
            x = rect.x() + rect.width() // 2
            y = rect.y() + rect.height() // 2
            # Emit particles based on whether PnL increased or decreased
            if pnl > prev_pnl:
                self._emit_particles(x, y, "increase")
            else:
                self._emit_particles(x, y, "decrease")
                
        # Update Redis with position data
        try:
            if self.redis_conn:
                # Store position data in Redis
                position_key = f"kingdom:position:{symbol}"
                self.redis_conn.hset(position_key, "symbol", symbol)
                self.redis_conn.hset(position_key, "size", str(size))
                self.redis_conn.hset(position_key, "entry_price", str(entry_price))
                self.redis_conn.hset(position_key, "mark_price", str(mark_price))
                self.redis_conn.hset(position_key, "pnl", str(pnl))
                self.redis_conn.hset(position_key, "pnl_pct", str(pnl_pct))
                if asset_class:
                    self.redis_conn.hset(position_key, "asset_class", asset_class)
                self.redis_conn.hset(position_key, "last_update", str(asyncio.get_event_loop().time()))
        except Exception as e:
            # Halt system on Redis failure - no fallbacks allowed
            logger.critical(f"PositionWidget: Redis Quantum Nexus update failed: {e}")
            sys.exit(1)
    
    def clear(self) -> None:
        """Clear all data from the widget."""
        self.table.setRowCount(0)
    
    def _show_context_menu(self, position):
        """Show context menu for position actions (close/hedge)."""
        row = self.table.rowAt(position.y())
        if row < 0:
            return

        menu = QMenu(self)
        close_action = menu.addAction("Close Position")
        hedge_action = menu.addAction("Hedge Position")

        global_pos = self.table.viewport().mapToGlobal(position)
        action = menu.exec(global_pos)

        if action is close_action:
            self._handle_close_position_action(row)
        elif action is hedge_action:
            self._handle_hedge_position_action(row)

    def _handle_close_position_action(self, row: int) -> None:
        """Publish a close-position request routed by asset_class.

        Stocks route via stock.order_submit (RealStockExecutor/Alpaca),
        while crypto/FX and other trading positions route via trading.signal
        so the crypto trading engine/RealExchangeExecutor can execute the
        appropriate offsetting order.
        """
        if not self.event_bus:
            return

        symbol_item = self.table.item(row, 0)
        size_item = self.table.item(row, 1)
        if not symbol_item or not size_item:
            return

        symbol = symbol_item.text()
        asset_class = str(symbol_item.data(Qt.ItemDataRole.UserRole) or "").lower()

        try:
            size_text = size_item.text().replace(",", "")
            size = float(size_text)
        except (TypeError, ValueError):
            size = 0.0

        if not symbol or size == 0.0:
            return

        side = "sell" if size > 0 else "buy"
        quantity = abs(size)

        try:
            if asset_class in ("stock", "equity", "equities"):
                order_payload = {
                    "symbol": symbol,
                    "side": side,
                    "type": "market",
                    "quantity": quantity,
                }
                self.event_bus.publish("stock.order_submit", order_payload)
            else:
                signal_payload = {
                    "symbol": symbol,
                    "signal_type": side,
                    "quantity": quantity,
                }
                self.event_bus.publish("trading.signal", signal_payload)
        except Exception as e:
            logger.error(f"PositionWidget: failed to publish close-position event: {e}")

    def _handle_hedge_position_action(self, row: int) -> None:
        """Publish a hedge-position request tagged with asset_class.

        This does not perform hedging locally; it emits events on distinct
        channels for stock vs. crypto/FX so dedicated risk/hedging components
        can react with the correct instruments.
        """
        if not self.event_bus:
            return

        symbol_item = self.table.item(row, 0)
        size_item = self.table.item(row, 1)
        if not symbol_item or not size_item:
            return

        symbol = symbol_item.text()
        asset_class = str(symbol_item.data(Qt.ItemDataRole.UserRole) or "").lower()

        try:
            size_text = size_item.text().replace(",", "")
            size = float(size_text)
        except (TypeError, ValueError):
            size = 0.0

        if not symbol or size == 0.0:
            return

        payload = {
            "symbol": symbol,
            "size": size,
            "asset_class": asset_class,
        }

        try:
            if asset_class in ("stock", "equity", "equities"):
                self.event_bus.publish("stock.hedge.request", payload)
            else:
                self.event_bus.publish("trading.hedge.request", payload)
        except Exception as e:
            logger.error(f"PositionWidget: failed to publish hedge-position event: {e}")
        
    def _emit_particles(self, x, y, change_type):
        """Emit particles for visual effect on position changes.
        
        Args:
            x: X coordinate to emit particles
            y: Y coordinate to emit particles
            change_type: 'increase' or 'decrease' to determine particle color
        """
        if has_cyberpunk and hasattr(self, 'particle_system'):
            color = QColor(CYBERPUNK_THEME["positive"]) if change_type == "increase" else QColor(CYBERPUNK_THEME["negative"])
            count = random.randint(5, 15)  # Random number of particles
            self.particle_system.emit(x, y, count)
            
    def _update_animations(self):
        """Update all animations and particle effects for cyberpunk visual style."""
        if has_cyberpunk:
            # Update RGB border animation if we're using the cyberpunk border widget
            if hasattr(self, '_update_animation'):
                self._update_animation()
            
            # Update particle effects
            if hasattr(self, 'particle_system'):
                self.particle_system.update()
                self.update()  # Trigger widget repaint
                
    def _should_animations_run(self) -> bool:
        if not has_cyberpunk:
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
                    timer.start(getattr(self, '_animation_interval_ms', 16))
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
                 
    def paintEvent(self, event):
        """Override paint event to draw custom cyberpunk effects."""
        if has_cyberpunk:
            if isinstance(self, CyberpunkRGBBorderWidget):
                super().paintEvent(event)
            else:
                super().paintEvent(event)
                
            if hasattr(self, 'particle_system'):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                self.particle_system.draw(painter)
                painter.end()
        else:
            super().paintEvent(event)
            
    def closeEvent(self, event):
        """Handle close event for proper cleanup."""
        # Stop animation timer if exists
        if hasattr(self, 'animation_timer') and self.animation_timer.isActive():
            self.animation_timer.stop()
            
        # Clean up Redis connection
        if hasattr(self, 'redis_conn') and self.redis_conn:
            try:
                self.redis_conn.close()
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
                
        # Unsubscribe from events when widget is closed
        self._unsubscribe_from_events()
        # Let parent class handle the rest
        super().closeEvent(event)
