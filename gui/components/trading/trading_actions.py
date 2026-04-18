#!/usr/bin/env python3
"""
Kingdom AI Trading Actions Module

This module implements action handlers for trading operations,
connecting UI events to trading system actions.
"""

import logging
import traceback
import threading
from datetime import datetime
import time
import json

logger = logging.getLogger("KingdomAI.TradingActions")

class TradingActions:
    """
    Trading action handlers.
    
    This class provides specific action handlers for trading operations,
    connecting UI events to trading system functionality.
    """
    
    def __init__(self, event_bus=None, trading_binder=None, action_triggers=None):
        """Initialize the trading actions"""
        self.event_bus = event_bus
        self.trading_binder = trading_binder
        self.action_triggers = action_triggers
        
        # Trading state
        self.active_symbols = []
        self.current_symbol = None
        self.order_book = {}
        self.recent_trades = {}
        self.chart_data = {}
        self.strategy_settings = {}
        self.auto_trading_enabled = False
        
        self.logger = logger
        self.logger.info("Trading Actions initialized")
    
    def register_actions(self):
        """Register trading actions with the action triggers"""
        if not self.action_triggers:
            self.logger.warning("Cannot register trading actions: No action triggers available")
            return False
        
        # Register basic trading actions
        self.action_triggers.register_action(
            "trading.refresh_market_data", 
            self.refresh_market_data,
            "trading"
        )
        
        self.action_triggers.register_action(
            "trading.place_order", 
            self.place_order,
            "trading"
        )
        
        self.action_triggers.register_action(
            "trading.cancel_order", 
            self.cancel_order,
            "trading"
        )
        
        self.action_triggers.register_action(
            "trading.change_symbol", 
            self.change_symbol,
            "trading"
        )
        
        self.action_triggers.register_action(
            "trading.toggle_auto_trading", 
            self.toggle_auto_trading,
            "trading"
        )
        
        self.action_triggers.register_action(
            "trading.update_strategy_settings", 
            self.update_strategy_settings,
            "trading"
        )
        
        self.logger.info("Registered trading actions")
        return True
    
    def refresh_market_data(self):
        """Refresh market data for the current symbol"""
        if self.trading_binder:
            if self.current_symbol:
                self.trading_binder.request_market_data([self.current_symbol])
                self.logger.info(f"Refreshing market data for {self.current_symbol}")
            else:
                self.trading_binder.request_market_data(self.active_symbols)
                self.logger.info("Refreshing market data for all active symbols")
            
            # Also refresh orders and portfolio
            self.trading_binder.request_orders()
            self.trading_binder.request_portfolio()
            
            return True
        else:
            self.logger.warning("Cannot refresh market data: No trading binder available")
            return False
    
    def place_order(self, symbol, side, order_type, amount, price=None):
        """
        Place a trading order
        
        Parameters:
        -----------
        symbol : str
            Trading symbol (e.g. 'BTC/USD')
        side : str
            'buy' or 'sell'
        order_type : str
            'market', 'limit', 'stop', etc.
        amount : float
            Amount to buy/sell
        price : float, optional
            Price for limit orders
        """
        if not self.trading_binder:
            self.logger.warning("Cannot place order: No trading binder available")
            return False
        
        # Create the order data
        order_data = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": float(amount)
        }
        
        # Add price for limit orders
        if order_type == "limit" and price is not None:
            order_data["price"] = float(price)
        
        # Place the order through the trading binder
        success = self.trading_binder.place_order(order_data)
        
        if success:
            self.logger.info(f"Placed {side} order for {amount} {symbol}")
            
            # Refresh orders after a short delay
            def delayed_refresh():
                time.sleep(2)
                self.trading_binder.request_orders()
                self.trading_binder.request_portfolio()
            
            threading.Thread(target=delayed_refresh, daemon=True).start()
        
        return success
    
    def cancel_order(self, order_id):
        """Cancel an existing order"""
        if not self.trading_binder:
            self.logger.warning("Cannot cancel order: No trading binder available")
            return False
        
        # Cancel the order through the trading binder
        success = self.trading_binder.cancel_order(order_id)
        
        if success:
            self.logger.info(f"Cancelled order {order_id}")
            
            # Refresh orders after a short delay
            def delayed_refresh():
                time.sleep(2)
                self.trading_binder.request_orders()
            
            threading.Thread(target=delayed_refresh, daemon=True).start()
        
        return success
    
    def change_symbol(self, symbol):
        """Change the current trading symbol"""
        self.current_symbol = symbol
        
        # Add to active symbols if not already there
        if symbol not in self.active_symbols:
            self.active_symbols.append(symbol)
        
        # Request data for the new symbol
        if self.trading_binder:
            self.trading_binder.request_market_data([symbol])
            self.logger.info(f"Changed current symbol to {symbol}")
            
            # Publish a symbol change event
            if self.event_bus:
                self.event_bus.publish("trading.symbol_changed", {
                    "symbol": symbol
                })
            
            return True
        else:
            self.logger.warning(f"Changed symbol to {symbol}, but no trading binder available for data request")
            return False
    
    def toggle_auto_trading(self, enabled=None):
        """Toggle auto-trading on/off"""
        if enabled is not None:
            self.auto_trading_enabled = enabled
        else:
            self.auto_trading_enabled = not self.auto_trading_enabled
        
        # Publish the auto-trading status change
        if self.event_bus:
            self.event_bus.publish("trading.auto_trading", {
                "enabled": self.auto_trading_enabled
            })
        
        self.logger.info(f"Auto-trading {'enabled' if self.auto_trading_enabled else 'disabled'}")
        return self.auto_trading_enabled
    
    def update_strategy_settings(self, strategy_id, settings):
        """Update settings for a trading strategy"""
        if strategy_id in self.strategy_settings:
            # Update existing strategy
            self.strategy_settings[strategy_id].update(settings)
        else:
            # Create new strategy settings
            self.strategy_settings[strategy_id] = settings
        
        # Publish the strategy update
        if self.event_bus:
            self.event_bus.publish("trading.strategy_updated", {
                "strategy_id": strategy_id,
                "settings": self.strategy_settings[strategy_id]
            })
        
        self.logger.info(f"Updated settings for strategy {strategy_id}")
        return True
    
    def get_order_book(self, symbol=None):
        """Get the order book for a symbol"""
        if symbol is None:
            symbol = self.current_symbol
        
        if symbol in self.order_book:
            return self.order_book[symbol]
        else:
            return {"bids": [], "asks": []}
    
    def get_recent_trades(self, symbol=None):
        """Get recent trades for a symbol"""
        if symbol is None:
            symbol = self.current_symbol
        
        if symbol in self.recent_trades:
            return self.recent_trades[symbol]
        else:
            return []
    
    def get_chart_data(self, symbol=None, timeframe="1h"):
        """Get chart data for a symbol and timeframe"""
        if symbol is None:
            symbol = self.current_symbol
        
        if symbol in self.chart_data and timeframe in self.chart_data[symbol]:
            return self.chart_data[symbol][timeframe]
        else:
            return []
    
    def update_order_book(self, symbol, order_book):
        """Update the order book data"""
        self.order_book[symbol] = order_book
        
        # Publish an order book update event
        if self.event_bus:
            # Use the canonical topic name expected by modern Qt TradingTab
            # and other consumers: 'trading.order_book_update'.
            self.event_bus.publish("trading.order_book_update", {
                "symbol": symbol,
                "order_book": order_book
            })
        
        self.logger.debug(f"Updated order book for {symbol}")
    
    def update_recent_trades(self, symbol, trades):
        """Update the recent trades data"""
        self.recent_trades[symbol] = trades
        
        # Publish a recent trades update event
        if self.event_bus:
            self.event_bus.publish("trading.recent_trades_updated", {
                "symbol": symbol,
                "trades": trades
            })
        
        self.logger.debug(f"Updated recent trades for {symbol}")
    
    def update_chart_data(self, symbol, timeframe, data):
        """Update the chart data"""
        if symbol not in self.chart_data:
            self.chart_data[symbol] = {}
        
        self.chart_data[symbol][timeframe] = data
        
        # Publish a chart data update event
        if self.event_bus:
            self.event_bus.publish("trading.chart_data_updated", {
                "symbol": symbol,
                "timeframe": timeframe,
                "data": data
            })
        
        self.logger.debug(f"Updated chart data for {symbol} ({timeframe})")
    
    def setup_trading_tab_bindings(self, trading_tab):
        """
        Set up event handlers for the trading tab
        
        Parameters:
        -----------
        trading_tab : object
            The trading tab object
        """
        if not trading_tab:
            self.logger.warning("Cannot set up trading tab bindings: No trading tab provided")
            return False
        
        # Set up button click handlers
        if hasattr(trading_tab, "buy_button") and self.action_triggers:
            buy_action = lambda: self._handle_buy_button_click(trading_tab)
            self.action_triggers.register_action("trading.buy", buy_action, "trading")
            trading_tab.buy_button.config(command=buy_action)
        
        if hasattr(trading_tab, "sell_button") and self.action_triggers:
            sell_action = lambda: self._handle_sell_button_click(trading_tab)
            self.action_triggers.register_action("trading.sell", sell_action, "trading")
            trading_tab.sell_button.config(command=sell_action)
        
        if hasattr(trading_tab, "cancel_button") and self.action_triggers:
            cancel_action = lambda: self._handle_cancel_button_click(trading_tab)
            self.action_triggers.register_action("trading.cancel_selected", cancel_action, "trading")
            trading_tab.cancel_button.config(command=cancel_action)
        
        if hasattr(trading_tab, "symbol_combo") and hasattr(trading_tab.symbol_combo, "bind"):
            trading_tab.symbol_combo.bind("<<ComboboxSelected>>", 
                                          lambda e: self._handle_symbol_change(trading_tab))
        
        if hasattr(trading_tab, "auto_trading_check") and hasattr(trading_tab.auto_trading_check, "config"):
            auto_trading_action = lambda: self._handle_auto_trading_toggle(trading_tab)
            trading_tab.auto_trading_check.config(command=auto_trading_action)
        
        self.logger.info("Set up trading tab bindings")
        return True
    
    def _handle_buy_button_click(self, trading_tab):
        """Handle buy button click"""
        try:
            # Extract values from trading tab
            symbol = self.current_symbol
            if not symbol and hasattr(trading_tab, "symbol_combo") and hasattr(trading_tab.symbol_combo, "get"):
                symbol = trading_tab.symbol_combo.get()
            
            if not symbol:
                self.logger.warning("Cannot place buy order: No symbol selected")
                return
            
            # Get order type (market/limit)
            order_type = "market"
            if hasattr(trading_tab, "order_type_var") and hasattr(trading_tab.order_type_var, "get"):
                order_type = trading_tab.order_type_var.get()
            
            # Get amount
            amount = 0
            if hasattr(trading_tab, "amount_entry") and hasattr(trading_tab.amount_entry, "get"):
                try:
                    amount = float(trading_tab.amount_entry.get())
                except ValueError:
                    self.logger.warning("Invalid amount for buy order")
                    return
            
            if amount <= 0:
                self.logger.warning("Cannot place buy order: Amount must be positive")
                return
            
            # Get price for limit orders
            price = None
            if order_type == "limit" and hasattr(trading_tab, "price_entry") and hasattr(trading_tab.price_entry, "get"):
                try:
                    price = float(trading_tab.price_entry.get())
                except ValueError:
                    self.logger.warning("Invalid price for limit buy order")
                    return
            
            # Place the order
            self.place_order(symbol, "buy", order_type, amount, price)
            
        except Exception as e:
            self.logger.error(f"Error handling buy button click: {e}")
            self.logger.error(traceback.format_exc())
    
    def _handle_sell_button_click(self, trading_tab):
        """Handle sell button click"""
        try:
            # Extract values from trading tab
            symbol = self.current_symbol
            if not symbol and hasattr(trading_tab, "symbol_combo") and hasattr(trading_tab.symbol_combo, "get"):
                symbol = trading_tab.symbol_combo.get()
            
            if not symbol:
                self.logger.warning("Cannot place sell order: No symbol selected")
                return
            
            # Get order type (market/limit)
            order_type = "market"
            if hasattr(trading_tab, "order_type_var") and hasattr(trading_tab.order_type_var, "get"):
                order_type = trading_tab.order_type_var.get()
            
            # Get amount
            amount = 0
            if hasattr(trading_tab, "amount_entry") and hasattr(trading_tab.amount_entry, "get"):
                try:
                    amount = float(trading_tab.amount_entry.get())
                except ValueError:
                    self.logger.warning("Invalid amount for sell order")
                    return
            
            if amount <= 0:
                self.logger.warning("Cannot place sell order: Amount must be positive")
                return
            
            # Get price for limit orders
            price = None
            if order_type == "limit" and hasattr(trading_tab, "price_entry") and hasattr(trading_tab.price_entry, "get"):
                try:
                    price = float(trading_tab.price_entry.get())
                except ValueError:
                    self.logger.warning("Invalid price for limit sell order")
                    return
            
            # Place the order
            self.place_order(symbol, "sell", order_type, amount, price)
            
        except Exception as e:
            self.logger.error(f"Error handling sell button click: {e}")
            self.logger.error(traceback.format_exc())
    
    def _handle_cancel_button_click(self, trading_tab):
        """Handle cancel button click"""
        try:
            # Get selected order
            if hasattr(trading_tab, "orders_tree") and hasattr(trading_tab.orders_tree, "selection"):
                selected_items = trading_tab.orders_tree.selection()
                if not selected_items:
                    self.logger.warning("No order selected for cancellation")
                    return
                
                # Get the order ID from the selected item
                order_id = trading_tab.orders_tree.item(selected_items[0], "text")
                
                # Cancel the order
                self.cancel_order(order_id)
            
        except Exception as e:
            self.logger.error(f"Error handling cancel button click: {e}")
            self.logger.error(traceback.format_exc())
    
    def _handle_symbol_change(self, trading_tab):
        """Handle symbol change"""
        try:
            if hasattr(trading_tab, "symbol_combo") and hasattr(trading_tab.symbol_combo, "get"):
                symbol = trading_tab.symbol_combo.get()
                if symbol:
                    self.change_symbol(symbol)
            
        except Exception as e:
            self.logger.error(f"Error handling symbol change: {e}")
            self.logger.error(traceback.format_exc())
    
    def _handle_auto_trading_toggle(self, trading_tab):
        """Handle auto-trading toggle"""
        try:
            if hasattr(trading_tab, "auto_trading_var") and hasattr(trading_tab.auto_trading_var, "get"):
                enabled = trading_tab.auto_trading_var.get()
                self.toggle_auto_trading(enabled)
            
        except Exception as e:
            self.logger.error(f"Error handling auto-trading toggle: {e}")
            self.logger.error(traceback.format_exc())

# Singleton instance for global access
_instance = None

def get_instance(event_bus=None, trading_binder=None, action_triggers=None):
    """Get the singleton instance of the trading actions"""
    global _instance
    if _instance is None:
        _instance = TradingActions(event_bus, trading_binder, action_triggers)
    return _instance
