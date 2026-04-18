"""
WebSocket Integration Helper for Trading Tab
Provides the _init_websocket_price_feeds method to be added to TradingTab
"""

import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)

def init_websocket_price_feeds(self):
    """
    Initialize WebSocket price feeds for real-time price updates.
    This method should be called from TradingTab.__init__()
    """
    try:
        # Import the concrete WebSocket price feed implementation. If this
        # import fails, an ImportError will be raised and we will fall back
        # to HTTP polling without relying on any instance attributes.
        from gui.qt_frames.trading.trading_websocket_price_feed import WebSocketPriceFeed, PriceFeedManager
        
        # Initialize price feed manager
        self.price_feed_manager = PriceFeedManager(self.event_bus)
        
        # SOTA 2026: Create price feed (Binance US compatible)
        self.price_feed = WebSocketPriceFeed(self.event_bus)
        self.price_feed_manager.add_feed('binanceus', self.price_feed)
        
        # Connect to price update signal
        self.price_feed.price_updated.connect(self._on_websocket_price_update)
        self.price_feed.connection_status.connect(self._on_websocket_connection_status)
        
        # Start WebSocket feeds in background using a Qt timer and safe
        # event-loop checks to avoid "no running event loop" errors.
        from PyQt6.QtCore import QTimer

        def _safe_start_feeds() -> None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # Event loop not ready yet; retry shortly
                logger.info("Event loop not running yet - retrying WebSocket start in 1000 ms")
                QTimer.singleShot(1000, _safe_start_feeds)
                return

            if not loop.is_running():
                logger.info("Event loop not running yet - retrying WebSocket start in 1000 ms")
                QTimer.singleShot(1000, _safe_start_feeds)
                return

            try:
                # SOTA 2026: Use asyncio.create_task instead of ensure_future
                asyncio.create_task(self._start_websocket_feeds())
                logger.info("WebSocket price feeds started")
            except Exception as exc:  # noqa: BLE001
                logger.error(f"❌ Failed to start WebSocket feeds: {exc}")

        QTimer.singleShot(1000, _safe_start_feeds)
        logger.info("✅ WebSocket price feeds initialization complete - startup scheduled via QTimer")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize WebSocket price feeds: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def start_websocket_feeds(self):
    """Start WebSocket connections asynchronously."""
    try:
        if hasattr(self, 'price_feed'):
            # Start ALL working exchanges (Binance US, Coinbase, Kraken, Bitstamp)
            self.price_feed.start()
            logger.info("✅ ALL WebSocket feeds started (Coinbase, Kraken, Bitstamp, Gemini)")
    except Exception as e:
        logger.error(f"❌ Error starting WebSocket feeds: {e}")

def on_websocket_price_update(self, price_data: Dict[str, Any]):
    """
    Handle real-time price updates from WebSocket.
    Called automatically when new price data arrives.
    """
    try:
        symbol = price_data.get('symbol', '')
        price = price_data.get('price', 0)
        change_24h = price_data.get('change_24h', 0)
        
        logger.debug(f"💰 WebSocket: {symbol} = ${price:,.2f} ({change_24h:+.2f}%)")
        
        # Update price display widgets
        if hasattr(self, 'price_labels') and symbol in self.price_labels:
            label = self.price_labels[symbol]
            if label:
                label.setText(f"${price:,.2f}")
        
        # Update change indicator
        if hasattr(self, 'change_labels') and symbol in self.change_labels:
            label = self.change_labels[symbol]
            if label:
                color = "#00FF00" if change_24h >= 0 else "#FF0000"
                sign = "+" if change_24h >= 0 else ""
                label.setText(f"{sign}{change_24h:.2f}%")
                label.setStyleSheet(f"color: {color}; font-weight: bold;")
        
        # Store latest price for trading system
        if not hasattr(self, 'latest_prices'):
            self.latest_prices = {}
        self.latest_prices[symbol] = price_data
        
        # Publish to event bus for other components
        if self.event_bus:
            self.event_bus.publish('trading:live_price_update', price_data)
        
    except Exception as e:
        logger.error(f"❌ Error handling WebSocket price update: {e}")

def on_websocket_connection_status(self, exchange: str, connected: bool):
    """Handle WebSocket connection status changes."""
    try:
        status = "CONNECTED" if connected else "DISCONNECTED"
        logger.info(f"📡 WebSocket {exchange}: {status}")
        
        # Update UI status indicator
        if hasattr(self, 'auto_trade_status_label'):
            if connected:
                current_text = self.auto_trade_status_label.text()
                if "WebSocket" not in current_text:
                    self.auto_trade_status_label.setText(f"{current_text} | WebSocket: LIVE")
            else:
                # Show reconnecting status
                self.auto_trade_status_label.setText(f"🟡 WebSocket {exchange}: Reconnecting...")
        
    except Exception as e:
        logger.error(f"❌ Error handling WebSocket status: {e}")


# Add these methods to TradingTab class
def add_websocket_methods_to_trading_tab(trading_tab_class):
    """
    Dynamically add WebSocket methods to TradingTab class.
    Call this before instantiating TradingTab.
    """
    trading_tab_class._init_websocket_price_feeds = init_websocket_price_feeds
    trading_tab_class._start_websocket_feeds = start_websocket_feeds
    trading_tab_class._on_websocket_price_update = on_websocket_price_update
    trading_tab_class._on_websocket_connection_status = on_websocket_connection_status
    logger.info("✅ WebSocket methods added to TradingTab class")
