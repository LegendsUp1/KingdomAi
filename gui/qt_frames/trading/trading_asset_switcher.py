"""
Trading Asset Switcher - Handler functions for asset type switching and live price display
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("KingdomAI.TradingAssetSwitcher")


def _switch_asset_type(self, asset_type: str):
    """Switch between crypto and stocks asset types."""
    try:
        self._current_asset_type = asset_type
        
        if asset_type == 'crypto':
            # Update button states
            self.asset_type_crypto_btn.setChecked(True)
            self.asset_type_stocks_btn.setChecked(False)
            
            # Show crypto buttons, hide stock buttons
            for btn in self.crypto_asset_buttons.values():
                btn.setVisible(True)
            for btn in self.stock_asset_buttons.values():
                btn.setVisible(False)
            
            # Switch to ETH as default crypto
            self._select_asset('ETH', 'crypto')
            
        elif asset_type == 'stocks':
            # Update button states
            self.asset_type_crypto_btn.setChecked(False)
            self.asset_type_stocks_btn.setChecked(True)
            
            # Show stock buttons, hide crypto buttons
            for btn in self.crypto_asset_buttons.values():
                btn.setVisible(False)
            for btn in self.stock_asset_buttons.values():
                btn.setVisible(True)
            
            # Switch to AAPL as default stock
            self._select_asset('AAPL', 'stocks')
        
        logger.info(f"✅ Switched to {asset_type} assets")
        
    except Exception as e:
        logger.error(f"Error switching asset type: {e}")


def _select_asset(self, asset: str, asset_type: str):
    """Select a specific asset to display live price."""
    try:
        self._current_asset = asset
        self._current_asset_type = asset_type
        
        # Build symbol based on asset type
        if asset_type == 'crypto':
            symbol = f"{asset}/USDT"
            # Also try /USD variant
            alt_symbol = f"{asset}/USD"
        else:
            symbol = asset  # Stock symbols are just the ticker
            alt_symbol = None
        
        # Get latest price from cache
        price_data = self._asset_prices.get(symbol) or self._asset_prices.get(alt_symbol)
        
        if price_data:
            price = price_data.get('price', 0)
            change = price_data.get('change_24h', 0)
            change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"
            color = "#00FF00" if change >= 0 else "#FF0000"
            
            display_text = f"{symbol}\n${price:,.2f} {change_str}"
            
            # Update color based on change
            self.current_asset_display.setStyleSheet(f"""
                QLabel {{
                    background-color: #1A1A3E;
                    color: {color};
                    padding: 15px;
                    border: 2px solid {color};
                    border-radius: 6px;
                    font-family: monospace;
                    font-size: 18px;
                    font-weight: bold;
                }}
            """)
        else:
            # No price data yet
            display_text = f"{symbol}\nLoading..."
            self.current_asset_display.setStyleSheet("""
                QLabel {
                    background-color: #1A1A3E;
                    color: #FFD700;
                    padding: 15px;
                    border: 2px solid #FFD700;
                    border-radius: 6px;
                    font-family: monospace;
                    font-size: 18px;
                    font-weight: bold;
                }
            """)
        
        self.current_asset_display.setText(display_text)
        
        # Request price update for this asset
        if self.event_bus:
            self.event_bus.publish('trading.price.request', {
                'symbol': symbol,
                'asset_type': asset_type,
                'source': 'trading_controls'
            })
        
        logger.info(f"✅ Selected asset: {symbol}")
        
    except Exception as e:
        logger.error(f"Error selecting asset: {e}")


def _update_asset_price_display(self, symbol: str, price_data: Dict[str, Any]):
    """Update the asset price display with live data from any connected market."""
    try:
        # Store in cache
        self._asset_prices[symbol] = price_data
        
        # Update display if this is the current asset
        current_symbol = f"{self._current_asset}/USDT" if self._current_asset_type == 'crypto' else self._current_asset
        alt_symbol = f"{self._current_asset}/USD" if self._current_asset_type == 'crypto' else None
        
        if symbol == current_symbol or symbol == alt_symbol:
            price = price_data.get('price', 0)
            change = price_data.get('change_24h', 0)
            exchange = price_data.get('exchange', 'Unknown')
            
            change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"
            color = "#00FF00" if change >= 0 else "#FF0000"
            
            display_text = f"{symbol}\n${price:,.2f} {change_str}"
            
            self.current_asset_display.setText(display_text)
            self.current_asset_display.setStyleSheet(f"""
                QLabel {{
                    background-color: #1A1A3E;
                    color: {color};
                    padding: 15px;
                    border: 2px solid {color};
                    border-radius: 6px;
                    font-family: monospace;
                    font-size: 18px;
                    font-weight: bold;
                }}
            """)
            
            logger.debug(f"💰 Updated {symbol}: ${price:,.2f} ({exchange})")
        
        # Update connected markets display
        self._update_connected_markets_display()
        
    except Exception as e:
        logger.error(f"Error updating asset price display: {e}")


def _update_connected_markets_display(self):
    """Update the connected markets label with actual connected exchanges."""
    try:
        connected = []
        
        # Get connected crypto exchanges
        if hasattr(self, '_exchanges') and self._exchanges:
            connected.extend(list(self._exchanges.keys())[:3])
        
        # Get connected stock brokers
        if hasattr(self, 'real_stock_executor') and self.real_stock_executor:
            if hasattr(self.real_stock_executor, 'alpaca') and self.real_stock_executor.alpaca:
                connected.append('Alpaca')
            if hasattr(self.real_stock_executor, 'oanda') and self.real_stock_executor.oanda:
                connected.append('Oanda')
        
        if connected:
            markets_text = f"📡 Connected: {', '.join(connected)}"
            color = "#00FF00"
        else:
            markets_text = "⚠️ No markets connected - Add API keys in Settings"
            color = "#FFA500"
        
        self.connected_markets_label.setText(markets_text)
        self.connected_markets_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 9px;
                padding: 4px;
                background-color: #0A1A0A;
                border-radius: 3px;
            }}
        """)
        
    except Exception as e:
        logger.error(f"Error updating connected markets display: {e}")


def _update_treasury_display(self, portfolio_data: Dict[str, Any]):
    """Update treasury display with live portfolio data."""
    try:
        treasury = portfolio_data.get('total_value', 0)
        available = portfolio_data.get('available_balance', 0)
        profit_24h = portfolio_data.get('profit_24h', 0)
        roi = portfolio_data.get('roi', 0)
        
        profit_color = "#00FF00" if profit_24h >= 0 else "#FF0000"
        profit_sign = "+" if profit_24h >= 0 else ""
        
        display_text = (
            f"💵 Treasury: ${treasury:,.2f}\n"
            f"💰 Available: ${available:,.2f}\n"
            f"📊 Profit (24h): {profit_sign}${profit_24h:,.2f}\n"
            f"📈 ROI: {roi:+.2f}%"
        )
        
        self.treasury_display.setText(display_text)
        
    except Exception as e:
        logger.error(f"Error updating treasury display: {e}")


def init_asset_switcher_handlers(trading_tab_class):
    """Add asset switcher handler methods to TradingTab class."""
    trading_tab_class._switch_asset_type = _switch_asset_type
    trading_tab_class._select_asset = _select_asset
    trading_tab_class._update_asset_price_display = _update_asset_price_display
    trading_tab_class._update_connected_markets_display = _update_connected_markets_display
    trading_tab_class._update_treasury_display = _update_treasury_display
    logger.info("✅ Asset switcher handlers added to TradingTab class")
