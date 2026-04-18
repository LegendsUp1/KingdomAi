#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Tab Frames Module.

This module provides the tab frames for all tabs in Kingdom AI.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk
import logging
import time
import json
import asyncio
from datetime import datetime

# Configure logger first to avoid NameError exceptions
logger = logging.getLogger(__name__)

# Import base frame
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gui.base_frame import BaseFrame

# Import frames from individual files in the frames directory
try:
    from gui.frames.wallet_frame import WalletFrame
except ImportError as e:
    logger.error(f"Error importing WalletFrame: {e}")
    # Create a placeholder class if import fails
    class WalletFrame(BaseFrame):
        """Placeholder for Wallet frame."""
        def __init__(self, parent, event_bus=None):
            super().__init__(parent, event_bus=event_bus)
            self.name = "Wallet"
            self._setup_ui()
        def _setup_ui(self):
            label = tk.Label(self, text="Wallet frame not implemented or could not be loaded.")
            label.pack(padx=20, pady=20)

try:
    from gui.frames.thoth_frame import ThothFrame as ThothAIFrame
except ImportError as e:
    logger.error(f"Error importing ThothAIFrame: {e}")
    # Create a placeholder class if import fails
    class ThothAIFrame(BaseFrame):
        """Placeholder for Thoth AI frame."""
        def __init__(self, parent, event_bus=None):
            super().__init__(parent, event_bus=event_bus)
            self.name = "Thoth AI"
            self._setup_ui()
        def _setup_ui(self):
            label = tk.Label(self, text="Thoth AI frame not implemented or could not be loaded.")
            label.pack(padx=20, pady=20)

try:
    from gui.frames.code_generator_frame import CodeGeneratorFrame
except ImportError as e:
    logger.error(f"Error importing CodeGeneratorFrame: {e}")
    # Create a placeholder class if import fails
    class CodeGeneratorFrame(BaseFrame):
        """Placeholder for Code Generator frame."""
        def __init__(self, parent, event_bus=None):
            super().__init__(parent, event_bus=event_bus)
            self.name = "Code Generator"
            self._setup_ui()
        def _setup_ui(self):
            label = tk.Label(self, text="Code Generator frame not implemented or could not be loaded.")
            label.pack(padx=20, pady=20)

try:
    from gui.frames.diagnostic_frame import DiagnosticsFrame
except ImportError as e:
    logger.error(f"Error importing DiagnosticsFrame: {e}")
    # Create a placeholder class if import fails
    class DiagnosticsFrame(BaseFrame):
        """Placeholder for Diagnostics frame."""
        def __init__(self, parent, event_bus=None):
            super().__init__(parent, event_bus=event_bus)
            self.name = "Diagnostics"
            self._setup_ui()
        def _setup_ui(self):
            label = tk.Label(self, text="Diagnostics frame not implemented or could not be loaded.")
            label.pack(padx=20, pady=20)

class DashboardFrame(BaseFrame):
    """Dashboard tab frame."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus=event_bus)
        self.name = "Dashboard"
    
    def _setup_ui(self):
        """Set up the dashboard UI."""
        # Status indicator
        self.status_indicator = tk.Frame(self, width=20, height=20, bg='gray')
        self.status_indicator.grid(row=0, column=0, padx=5, pady=5, sticky='nw')
        
        # Title
        title = tk.Label(self, text="Kingdom AI Dashboard", font=("Arial", 16, "bold"))
        title.grid(row=0, column=1, padx=5, pady=5, sticky='nw')
        
        # System status frame
        status_frame = tk.LabelFrame(self, text="System Status")
        status_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky='nsew')
        
        # Status labels
        self.redis_status = tk.Label(status_frame, text="Redis: Disconnected", fg="red")
        self.redis_status.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        
        self.event_bus_status = tk.Label(status_frame, text="Event Bus: Connected", fg="green")
        self.event_bus_status.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        
        self.api_status = tk.Label(status_frame, text="API Connections: Unknown", fg="gray")
        self.api_status.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        
        self.blockchain_status = tk.Label(status_frame, text="Blockchain: Disconnected", fg="red")
        self.blockchain_status.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        
        # Quick actions frame
        actions_frame = tk.LabelFrame(self, text="Quick Actions")
        actions_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky='nsew')
        
        # Action buttons
        self.refresh_btn = tk.Button(actions_frame, text="Refresh Status", command=self.refresh)
        self.refresh_btn.grid(row=0, column=0, padx=5, pady=5)
        
        self.toggle_redis_btn = tk.Button(actions_frame, text="Start Redis", command=self._toggle_redis)
        self.toggle_redis_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.check_apis_btn = tk.Button(actions_frame, text="Check APIs", command=self._check_apis)
        self.check_apis_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Configure grid weights
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
    def _connect_events(self):
        """Connect events to handlers."""
        if self.event_bus:
            # Subscribe to status events using subscribe_sync to prevent coroutine warnings
            if hasattr(self.event_bus, 'subscribe_sync'):
                # Use synchronous subscription to prevent coroutine warnings
                self.event_bus.subscribe_sync("redis.status", self._handle_redis_status)
                self.event_bus.subscribe_sync("api.status", self._handle_api_status)
                self.event_bus.subscribe_sync("blockchain.status", self._handle_blockchain_status)
                logger.info("Dashboard status events subscribed using subscribe_sync")
            else:
                # Fallback to async subscription when sync is not available
                # We should run these coroutines to ensure they complete
                import asyncio
                loop = asyncio.get_event_loop()
                async def subscribe_to_events():
                    await self.event_bus.subscribe("redis.status", self._handle_redis_status)
                    await self.event_bus.subscribe("api.status", self._handle_api_status)
                    await self.event_bus.subscribe("blockchain.status", self._handle_blockchain_status)
                loop.run_until_complete(subscribe_to_events())
                logger.info("Dashboard status events subscribed using async approach")
    
    def _handle_redis_status(self, data):
        """Handle Redis status updates."""
        try:
            status = data.get('status', 'unknown')
            if status == 'connected':
                self.redis_status.config(text="Redis: Connected", fg="green")
            elif status == 'connecting':
                self.redis_status.config(text="Redis: Connecting...", fg="orange")
            elif status == 'disconnected':
                self.redis_status.config(text="Redis: Disconnected", fg="red")
            else:
                self.redis_status.config(text=f"Redis: {status.capitalize()}", fg="gray")
        except Exception as e:
            logger.error(f"Error handling Redis status: {e}")
    
    def _handle_api_status(self, data):
        """Handle API status updates."""
        try:
            status = data.get('status', 'unknown')
            if status == 'connected':
                self.api_status.config(text="API Connections: Connected", fg="green")
            elif status == 'partial':
                self.api_status.config(text="API Connections: Partial", fg="orange")
            elif status == 'disconnected':
                self.api_status.config(text="API Connections: Disconnected", fg="red")
            else:
                self.api_status.config(text=f"API Connections: {status.capitalize()}", fg="gray")
        except Exception as e:
            logger.error(f"Error handling API status: {e}")
    
    def _handle_blockchain_status(self, data):
        """Handle blockchain status updates."""
        try:
            status = data.get('status', 'unknown')
            if status == 'connected':
                self.blockchain_status.config(text="Blockchain: Connected", fg="green")
            elif status == 'connecting':
                self.blockchain_status.config(text="Blockchain: Connecting...", fg="orange")
            elif status == 'disconnected':
                self.blockchain_status.config(text="Blockchain: Disconnected", fg="red")
            else:
                self.blockchain_status.config(text=f"Blockchain: {status.capitalize()}", fg="gray")
        except Exception as e:
            logger.error(f"Error handling blockchain status: {e}")
    
    def _toggle_redis(self):
        """Toggle Redis server state."""
        if self.event_bus:
            try:
                # Publish event to toggle Redis
                self.event_bus.publish("redis.toggle", {"action": "toggle"})
            except Exception as e:
                logger.error(f"Error toggling Redis: {e}")
    
    def _check_apis(self):
        """Check API connections."""
        if self.event_bus:
            try:
                # Publish event to check APIs
                self.event_bus.publish("api.check", {"check_all": True})
            except Exception as e:
                logger.error(f"Error checking APIs: {e}")
    
    def refresh(self):
        """Refresh dashboard data."""
        if self.event_bus:
            try:
                # Request status updates
                self.event_bus.publish("redis.status.request", {})
                self.event_bus.publish("api.status.request", {})
                self.event_bus.publish("blockchain.status.request", {})
                return True
            except Exception as e:
                logger.error(f"Error refreshing dashboard: {e}")
                return False
        return False

class MiningFrame(BaseFrame):
    """Mining tab frame."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus=event_bus)
        self.name = "Mining"
    
    def _setup_ui(self):
        """Set up the mining UI."""
        # Status indicator
        self.status_indicator = tk.Frame(self, width=20, height=20, bg='gray')
        self.status_indicator.grid(row=0, column=0, padx=5, pady=5, sticky='nw')
        
        # Title
        title = tk.Label(self, text="Mining Dashboard", font=("Arial", 16, "bold"))
        title.grid(row=0, column=1, padx=5, pady=5, sticky='nw')
        
        # Placeholder
        placeholder = tk.Label(self, text="Mining Dashboard - Under Construction")
        placeholder.grid(row=1, column=0, columnspan=2, padx=10, pady=10)

class TradingFrame(BaseFrame):
    """Trading tab frame."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus=event_bus)
        self.name = "Trading"
        self.markets = {}
        self.current_market = ""
        self.orders = []
        self.strategies = []
    
    def _setup_ui(self):
        """Set up the trading UI."""
        # Main container with tabs for different trading views
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Market view
        self.market_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.market_frame, text="Markets")
        
        # Create market selection dropdown
        market_frame = ttk.LabelFrame(self.market_frame, text="Select Market")
        market_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(market_frame, text="Market:").grid(row=0, column=0, padx=5, pady=5)
        self.market_combo = ttk.Combobox(market_frame, state="readonly")
        self.market_combo.grid(row=0, column=1, padx=5, pady=5)
        self.market_combo.bind("<<ComboboxSelected>>", self._on_market_selected)
        
        refresh_btn = ttk.Button(market_frame, text="Refresh", command=self._refresh_markets)
        refresh_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Price chart frame
        chart_frame = ttk.LabelFrame(self.market_frame, text="Price Chart")
        chart_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add chart placeholder
        self.chart_label = ttk.Label(chart_frame, text="Chart will appear here", font=("Arial", 14))
        self.chart_label.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Order book frame
        order_book_frame = ttk.LabelFrame(self.market_frame, text="Order Book")
        order_book_frame.pack(fill="x", padx=10, pady=10)
        
        # Buy side
        buy_frame = ttk.Frame(order_book_frame)
        buy_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(buy_frame, text="Buy Orders", foreground="green").pack()
        self.buy_orders_tree = ttk.Treeview(buy_frame, columns=("Price", "Amount", "Total"), show="headings", height=5)
        self.buy_orders_tree.heading("Price", text="Price")
        self.buy_orders_tree.heading("Amount", text="Amount")
        self.buy_orders_tree.heading("Total", text="Total")
        self.buy_orders_tree.pack(fill="both", expand=True)
        
        # Sell side
        sell_frame = ttk.Frame(order_book_frame)
        sell_frame.pack(side="right", fill="both", expand=True)
        ttk.Label(sell_frame, text="Sell Orders", foreground="red").pack()
        self.sell_orders_tree = ttk.Treeview(sell_frame, columns=("Price", "Amount", "Total"), show="headings", height=5)
        self.sell_orders_tree.heading("Price", text="Price")
        self.sell_orders_tree.heading("Amount", text="Amount")
        self.sell_orders_tree.heading("Total", text="Total")
        self.sell_orders_tree.pack(fill="both", expand=True)
        
        # Trading view
        self.trading_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.trading_frame, text="Trade")
        
        # Order form
        order_form = ttk.LabelFrame(self.trading_frame, text="Place Order")
        order_form.pack(fill="x", padx=10, pady=10)
        
        # Order type
        ttk.Label(order_form, text="Order Type:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.order_type = tk.StringVar(value="limit")
        ttk.Radiobutton(order_form, text="Limit", variable=self.order_type, value="limit").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Radiobutton(order_form, text="Market", variable=self.order_type, value="market").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        
        # Buy/Sell
        ttk.Label(order_form, text="Side:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.order_side = tk.StringVar(value="buy")
        ttk.Radiobutton(order_form, text="Buy", variable=self.order_side, value="buy").grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Radiobutton(order_form, text="Sell", variable=self.order_side, value="sell").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        
        # Price
        ttk.Label(order_form, text="Price:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.price_entry = ttk.Entry(order_form)
        self.price_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Amount
        ttk.Label(order_form, text="Amount:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.amount_entry = ttk.Entry(order_form)
        self.amount_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Submit button
        submit_btn = ttk.Button(order_form, text="Place Order", command=self._place_order)
        submit_btn.grid(row=4, column=0, columnspan=3, padx=5, pady=10)
        
        # Order history view
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="History")
        
        # Order history table
        self.orders_tree = ttk.Treeview(self.history_frame, columns=("Date", "Market", "Type", "Side", "Price", "Amount", "Status"), show="headings")
        self.orders_tree.heading("Date", text="Date")
        self.orders_tree.heading("Market", text="Market")
        self.orders_tree.heading("Type", text="Type")
        self.orders_tree.heading("Side", text="Side")
        self.orders_tree.heading("Price", text="Price")
        self.orders_tree.heading("Amount", text="Amount")
        self.orders_tree.heading("Status", text="Status")
        self.orders_tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.history_frame, orient="vertical", command=self.orders_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.orders_tree.configure(yscrollcommand=scrollbar.set)
        
        # Portfolio view
        self.portfolio_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.portfolio_frame, text="Portfolio")
        
        # Portfolio table
        self.portfolio_tree = ttk.Treeview(self.portfolio_frame, columns=("Asset", "Balance", "Value", "Change"), show="headings")
        self.portfolio_tree.heading("Asset", text="Asset")
        self.portfolio_tree.heading("Balance", text="Balance")
        self.portfolio_tree.heading("Value", text="Value (USD)")
        self.portfolio_tree.heading("Change", text="24h Change")
        self.portfolio_tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.portfolio_frame, orient="vertical", command=self.portfolio_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.portfolio_tree.configure(yscrollcommand=scrollbar.set)
        
        # Strategies view
        self.strategies_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.strategies_frame, text="Strategies")
        
        # Strategy selection
        strategies_select = ttk.LabelFrame(self.strategies_frame, text="Trading Strategies")
        strategies_select.pack(fill="x", padx=10, pady=10)
        
        # List of strategies
        self.strategies_tree = ttk.Treeview(strategies_select, columns=("Name", "Type", "Status"), show="headings", height=5)
        self.strategies_tree.heading("Name", text="Strategy Name")
        self.strategies_tree.heading("Type", text="Type")
        self.strategies_tree.heading("Status", text="Status")
        self.strategies_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Strategy buttons
        buttons_frame = ttk.Frame(strategies_select)
        buttons_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(buttons_frame, text="Start Strategy", command=self._start_strategy).pack(side="left", padx=5)
        ttk.Button(buttons_frame, text="Stop Strategy", command=self._stop_strategy).pack(side="left", padx=5)
        ttk.Button(buttons_frame, text="Backtest", command=self._backtest_strategy).pack(side="left", padx=5)
    
    def _connect_events(self):
        """Connect to event bus events."""
        if self.event_bus:
            if hasattr(self.event_bus, 'subscribe_sync'):
                self.event_bus.subscribe_sync("market.update", self._handle_market_update)
                self.event_bus.subscribe_sync("order.update", self._handle_order_update)
                self.event_bus.subscribe_sync("portfolio.update", self._handle_portfolio_update)
                self.event_bus.subscribe_sync("strategy.update", self._handle_strategy_update)
                logger.info(f"{self.name} events subscribed using subscribe_sync")
            else:
                # Fallback to async subscription
                async def subscribe_to_events():
                    await self.event_bus.subscribe("market.update", self._handle_market_update)
                    await self.event_bus.subscribe("order.update", self._handle_order_update)
                    await self.event_bus.subscribe("portfolio.update", self._handle_portfolio_update)
                    await self.event_bus.subscribe("strategy.update", self._handle_strategy_update)
                
                # Execute the coroutine
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(subscribe_to_events())
                except RuntimeError:
                    # Handle case where no event loop is running
                    pass
    
    def _handle_market_update(self, data):
        """Handle market data updates."""
        try:
            if 'markets' in data:
                self.markets = data['markets']
                self.market_combo['values'] = list(self.markets.keys())
                
            if 'orderbook' in data and self.current_market:
                orderbook = data['orderbook']
                
                # Clear existing orders
                for item in self.buy_orders_tree.get_children():
                    self.buy_orders_tree.delete(item)
                    
                for item in self.sell_orders_tree.get_children():
                    self.sell_orders_tree.delete(item)
                
                # Add buy orders
                for order in orderbook.get('bids', []):
                    price = order[0]
                    amount = order[1]
                    total = float(price) * float(amount)
                    self.buy_orders_tree.insert("", "end", values=(price, amount, f"{total:.8f}"))
                
                # Add sell orders
                for order in orderbook.get('asks', []):
                    price = order[0]
                    amount = order[1]
                    total = float(price) * float(amount)
                    self.sell_orders_tree.insert("", "end", values=(price, amount, f"{total:.8f}"))
            
            return True
        except Exception as e:
            logger.error(f"Error handling market update: {e}")
            return True
    
    def _handle_order_update(self, data):
        """Handle order updates."""
        try:
            if 'orders' in data:
                # Clear existing orders
                for item in self.orders_tree.get_children():
                    self.orders_tree.delete(item)
                
                # Add orders to history
                for order in data['orders']:
                    self.orders_tree.insert("", "end", values=(
                        order.get('date', ''),
                        order.get('market', ''),
                        order.get('type', ''),
                        order.get('side', ''),
                        order.get('price', ''),
                        order.get('amount', ''),
                        order.get('status', '')
                    ))
            
            return True
        except Exception as e:
            logger.error(f"Error handling order update: {e}")
            return True
    
    def _handle_portfolio_update(self, data):
        """Handle portfolio updates."""
        try:
            if 'portfolio' in data:
                # Clear existing portfolio items
                for item in self.portfolio_tree.get_children():
                    self.portfolio_tree.delete(item)
                
                # Add portfolio items
                for asset in data['portfolio']:
                    self.portfolio_tree.insert("", "end", values=(
                        asset.get('asset', ''),
                        asset.get('balance', ''),
                        asset.get('value', ''),
                        asset.get('change', '')
                    ))
            
            return True
        except Exception as e:
            logger.error(f"Error handling portfolio update: {e}")
            return True
    
    def _handle_strategy_update(self, data):
        """Handle strategy updates."""
        try:
            if 'strategies' in data:
                self.strategies = data['strategies']
                
                # Clear existing strategies
                for item in self.strategies_tree.get_children():
                    self.strategies_tree.delete(item)
                
                # Add strategies
                for strategy in self.strategies:
                    self.strategies_tree.insert("", "end", values=(
                        strategy.get('name', ''),
                        strategy.get('type', ''),
                        strategy.get('status', '')
                    ))
            
            return True
        except Exception as e:
            logger.error(f"Error handling strategy update: {e}")
            return True
    
    def _on_market_selected(self, event):
        """Handle market selection."""
        self.current_market = self.market_combo.get()
        if self.event_bus:
            self.event_bus.publish_sync("market.select", {"market": self.current_market})
    
    def _refresh_markets(self):
        """Refresh market data."""
        if self.event_bus:
            self.event_bus.publish_sync("market.refresh", {})
    
    def _place_order(self):
        """Place a new order."""
        try:
            order_data = {
                "market": self.current_market,
                "type": self.order_type.get(),
                "side": self.order_side.get(),
                "price": self.price_entry.get() if self.order_type.get() == "limit" else "market",
                "amount": self.amount_entry.get()
            }
            
            if self.event_bus:
                self.event_bus.publish_sync("order.create", order_data)
                
            # Clear form
            self.price_entry.delete(0, tk.END)
            self.amount_entry.delete(0, tk.END)
        except Exception as e:
            logger.error(f"Error placing order: {e}")
    
    def _start_strategy(self):
        """Start the selected strategy."""
        selected = self.strategies_tree.selection()
        if not selected:
            return
            
        # Get selected strategy
        index = self.strategies_tree.index(selected[0])
        if index < len(self.strategies):
            strategy = self.strategies[index]
            
            if self.event_bus:
                self.event_bus.publish_sync("strategy.start", {"name": strategy.get('name')})
    
    def _stop_strategy(self):
        """Stop the selected strategy."""
        selected = self.strategies_tree.selection()
        if not selected:
            return
            
        # Get selected strategy
        index = self.strategies_tree.index(selected[0])
        if index < len(self.strategies):
            strategy = self.strategies[index]
            
            if self.event_bus:
                self.event_bus.publish_sync("strategy.stop", {"name": strategy.get('name')})
    
    def _backtest_strategy(self):
        """Backtest the selected strategy."""
        selected = self.strategies_tree.selection()
        if not selected:
            return
            
        # Get selected strategy
        index = self.strategies_tree.index(selected[0])
        if index < len(self.strategies):
            strategy = self.strategies[index]
            
            if self.event_bus:
                self.event_bus.publish_sync("strategy.backtest", {"name": strategy.get('name')})
    
    def refresh(self):
        """Refresh tab data."""
        if self.event_bus:
            self.event_bus.publish_sync("market.refresh", {})
            self.event_bus.publish_sync("order.refresh", {})
            self.event_bus.publish_sync("portfolio.refresh", {})
            self.event_bus.publish_sync("strategy.refresh", {})

class SettingsFrame(BaseFrame):
    """Settings tab frame."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus=event_bus)
        self.name = "Settings"
    
    def _setup_ui(self):
        """Set up the settings UI."""
        # Status indicator
        self.status_indicator = tk.Frame(self, width=20, height=20, bg='gray')
        self.status_indicator.grid(row=0, column=0, padx=5, pady=5, sticky='nw')
        
        # Title
        title = tk.Label(self, text="Settings", font=("Arial", 16, "bold"))
        title.grid(row=0, column=1, padx=5, pady=5, sticky='nw')

class LogFrame(BaseFrame):
    """Log tab frame."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus=event_bus)
        self.name = "Logs"
    
    def _setup_ui(self):
        """Set up the log UI."""
        # Status indicator
        self.status_indicator = tk.Frame(self, width=20, height=20, bg='gray')
        self.status_indicator.grid(row=0, column=0, padx=5, pady=5, sticky='nw')
        
        # Title
        title = tk.Label(self, text="System Logs", font=("Arial", 16, "bold"))
        title.grid(row=0, column=1, padx=5, pady=5, sticky='nw')
        
        try:
            # Placeholder
            placeholder = tk.Label(self, text="System Logs - Under Construction")
            placeholder.grid(row=1, column=0, columnspan=2, padx=10, pady=10)
        except Exception as e:
            logger.error(f"Error: {e}")
class ApiKeyFrame(BaseFrame):
    """API Key tab frame."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus=event_bus)
        self.name = "API Keys"
    
    def _setup_ui(self):
        """Set up the API key UI."""
        # Status indicator
        self.status_indicator = tk.Frame(self, width=20, height=20, bg='gray')
        self.status_indicator.grid(row=0, column=0, padx=5, pady=5, sticky='nw')
        
        # Title
        title = tk.Label(self, text="API Key Management", font=("Arial", 16, "bold"))
        title.grid(row=0, column=1, padx=5, pady=5, sticky='nw')
        
        # Placeholder
        placeholder = tk.Label(self, text="API Key Management - Under Construction")
        placeholder.grid(row=1, column=0, columnspan=2, padx=10, pady=10)

class VRSystemFrame(BaseFrame):
    """VR System tab frame."""
    
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, event_bus=event_bus)
        self.name = "VR System"
        self.vr_status = "disconnected"
        self.vr_enabled = False
    
    def _setup_ui(self):
        """Set up the VR system UI."""
        # Status indicator
        self.status_indicator = tk.Frame(self, width=20, height=20, bg='red')
        self.status_indicator.grid(row=0, column=0, padx=5, pady=5, sticky='nw')
        
        # Title
        title = tk.Label(self, text="Virtual Reality System", font=("Arial", 16, "bold"))
        title.grid(row=0, column=1, padx=5, pady=5, sticky='nw')
        
        # VR status frame
        status_frame = tk.LabelFrame(self, text="VR System Status")
        status_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky='nsew')
        
        # Status labels
        self.status_label = tk.Label(status_frame, text="VR System: Disconnected", fg="red")
        self.status_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        
        self.connection_label = tk.Label(status_frame, text="Headset: Not Detected", fg="red")
        self.connection_label.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        
        self.tracking_label = tk.Label(status_frame, text="Tracking: Not Available", fg="gray")
        self.tracking_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        
        self.battery_label = tk.Label(status_frame, text="Battery: Unknown", fg="gray")
        self.battery_label.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        
        # Controls frame
        controls_frame = tk.LabelFrame(self, text="VR Controls")
        controls_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky='nsew')
        
        # Control buttons
        self.connect_btn = tk.Button(controls_frame, text="Connect VR Headset", command=self._connect_vr)
        self.connect_btn.grid(row=0, column=0, padx=5, pady=5)
        
        self.calibrate_btn = tk.Button(controls_frame, text="Calibrate Tracking", command=self._calibrate_tracking, state=tk.DISABLED)
        self.calibrate_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.reset_btn = tk.Button(controls_frame, text="Reset VR Session", command=self._reset_vr, state=tk.DISABLED)
        self.reset_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Settings frame
        settings_frame = tk.LabelFrame(self, text="VR Settings")
        settings_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky='nsew')
        
        # Settings controls
        tk.Label(settings_frame, text="Resolution:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.resolution_combo = ttk.Combobox(settings_frame, values=["Low", "Medium", "High", "Ultra"])
        self.resolution_combo.current(1)  # Default to Medium
        self.resolution_combo.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        
        tk.Label(settings_frame, text="Tracking Quality:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.tracking_combo = ttk.Combobox(settings_frame, values=["Minimal", "Standard", "Enhanced", "Full Body"])
        self.tracking_combo.current(1)  # Default to Standard
        self.tracking_combo.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        
        self.audio_var = tk.BooleanVar(value=True)
        self.audio_check = tk.Checkbutton(settings_frame, text="Enable Spatial Audio", variable=self.audio_var)
        self.audio_check.grid(row=2, column=0, padx=5, pady=5, sticky='w')
        
        self.haptic_var = tk.BooleanVar(value=True)
        self.haptic_check = tk.Checkbutton(settings_frame, text="Enable Haptic Feedback", variable=self.haptic_var)
        self.haptic_check.grid(row=2, column=1, padx=5, pady=5, sticky='w')
        
        self.apply_btn = tk.Button(settings_frame, text="Apply Settings", command=self._apply_settings, state=tk.DISABLED)
        self.apply_btn.grid(row=3, column=0, columnspan=2, padx=5, pady=5)
        
        # Configure grid weights
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
    
    def _connect_events(self):
        """Connect events to handlers."""
        if self.event_bus and hasattr(self.event_bus, 'subscribe_sync'):
            self.event_bus.subscribe_sync("vr.status", self._handle_vr_status)
            self.event_bus.subscribe_sync("vr.headset", self._handle_headset_status)
            self.event_bus.subscribe_sync("vr.tracking", self._handle_tracking_status)
            self.event_bus.subscribe_sync("vr.battery", self._handle_battery_status)
            logger.info("VR System events subscribed using subscribe_sync")
    
    def _handle_vr_status(self, data):
        """Handle VR status updates."""
        try:
            status = data.get('status', 'disconnected')
            self.vr_status = status
            
            if status == 'connected':
                self.status_label.config(text="VR System: Connected", fg="green")
                self.status_indicator.config(bg="green")
                self.connect_btn.config(text="Disconnect VR", state=tk.NORMAL)
                self.calibrate_btn.config(state=tk.NORMAL)
                self.reset_btn.config(state=tk.NORMAL)
                self.apply_btn.config(state=tk.NORMAL)
                self.vr_enabled = True
            elif status == 'connecting':
                self.status_label.config(text="VR System: Connecting...", fg="orange")
                self.status_indicator.config(bg="orange")
                self.connect_btn.config(state=tk.DISABLED)
                self.vr_enabled = False
            else:  # disconnected
                self.status_label.config(text="VR System: Disconnected", fg="red")
                self.status_indicator.config(bg="red")
                self.connect_btn.config(text="Connect VR Headset", state=tk.NORMAL)
                self.calibrate_btn.config(state=tk.DISABLED)
                self.reset_btn.config(state=tk.DISABLED)
                self.apply_btn.config(state=tk.DISABLED)
                self.vr_enabled = False
        except Exception as e:
            logger.error(f"Error handling VR status: {e}")
    
    def _handle_headset_status(self, data):
        """Handle headset status updates."""
        try:
            status = data.get('status', 'not_detected')
            
            if status == 'connected':
                self.connection_label.config(text=f"Headset: {data.get('model', 'Connected')}", fg="green")
            elif status == 'connecting':
                self.connection_label.config(text="Headset: Connecting...", fg="orange")
            else:  # not_detected
                self.connection_label.config(text="Headset: Not Detected", fg="red")
        except Exception as e:
            logger.error(f"Error handling headset status: {e}")
    
    def _handle_tracking_status(self, data):
        """Handle tracking status updates."""
        try:
            status = data.get('status', 'unavailable')
            quality = data.get('quality', 0)
            
            if status == 'active':
                self.tracking_label.config(text=f"Tracking: Active ({quality}%)", fg="green")
            elif status == 'calibrating':
                self.tracking_label.config(text="Tracking: Calibrating...", fg="orange")
            else:  # unavailable
                self.tracking_label.config(text="Tracking: Not Available", fg="gray")
        except Exception as e:
            logger.error(f"Error handling tracking status: {e}")
    
    def _handle_battery_status(self, data):
        """Handle battery status updates."""
        try:
            level = data.get('level', -1)
            charging = data.get('charging', False)
            
            if level >= 0:
                if charging:
                    self.battery_label.config(text=f"Battery: {level}% (Charging)", fg="green")
                else:
                    if level > 20:
                        self.battery_label.config(text=f"Battery: {level}%", fg="green")
                    else:
                        self.battery_label.config(text=f"Battery: {level}% (Low)", fg="red")
            else:
                self.battery_label.config(text="Battery: Unknown", fg="gray")
        except Exception as e:
            logger.error(f"Error handling battery status: {e}")
    
    def _connect_vr(self):
        """Connect or disconnect VR headset."""
        if self.vr_enabled:
            # Disconnect VR
            self._publish_vr_status('disconnecting')
            self.status_label.config(text="VR System: Disconnecting...", fg="orange")
            self.connect_btn.config(state=tk.DISABLED)
        else:
            # Connect VR
            self._publish_vr_status('connecting')
            self.status_label.config(text="VR System: Connecting...", fg="orange")
            self.connect_btn.config(state=tk.DISABLED)
    
    def _calibrate_tracking(self):
        """Calibrate VR tracking."""
        if self.vr_enabled:
            self._publish_event('vr.tracking.calibrate', {'action': 'start'})
            self.tracking_label.config(text="Tracking: Calibrating...", fg="orange")
            self.calibrate_btn.config(state=tk.DISABLED)
    
    def _reset_vr(self):
        """Reset VR session."""
        if self.vr_enabled:
            self._publish_event('vr.session.reset', {'action': 'reset'})
    
    def _apply_settings(self):
        """Apply VR settings."""
        if self.vr_enabled:
            settings = {
                'resolution': self.resolution_combo.get(),
                'tracking_quality': self.tracking_combo.get(),
                'spatial_audio': self.audio_var.get(),
                'haptic_feedback': self.haptic_var.get()
            }
            self._publish_event('vr.settings.update', settings)
    
    def _publish_vr_status(self, status):
        """Publish VR status update."""
        self._publish_event('vr.status.update', {'status': status})
    
    def _publish_event(self, event, data):
        """Publish event to event bus."""
        if self.event_bus:
            if hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync(event, data)
            elif hasattr(self.event_bus, 'publish'):
                if asyncio.iscoroutinefunction(self.event_bus.publish):
                    # Create and run task for async publish
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(self.event_bus.publish(event, data))
                        else:
                            loop.run_until_complete(self.event_bus.publish(event, data))
                    except Exception as e:
                        logger.error(f"Error publishing event {event}: {e}")
                else:
                    # Direct call for sync publish
                    self.event_bus.publish(event, data)
    
    def refresh(self):
        """Refresh VR system frame."""
        try:
            # Request current status
            self._publish_event('vr.status.request', {'action': 'get_status'})
            
            # Update UI based on current stored state
            self._update_ui_state()
            
            # Always return True for consistency with BaseFrame
            return True
        except Exception as e:
            logger.error(f"Error refreshing VR system: {e}")
            # Always return True for consistency with BaseFrame
            return True
            
    def update_data(self, data):
        """Update the VR system frame with new data.
        
        Args:
            data (dict): Data containing VR system status information
        """
        try:
            if not data:
                return True
                
            # Update our internal state
            status = data.get('status', self.vr_status)
            if status:
                self.vr_status = status
                
            # Handle headset model if available
            if 'model' in data:
                self.headset_model = data.get('model', 'Unknown')
                
            # Handle tracking status if available
            if 'tracking' in data:
                self.tracking_status = data.get('tracking', 'unavailable')
                
            # Handle battery information if available
            if 'battery' in data:
                self.battery_level = data.get('battery', {}).get('level', -1)
                self.battery_charging = data.get('battery', {}).get('charging', False)
                
            # Update UI with new data
            self._update_ui_state()
            
            return True
        except Exception as e:
            logger.error(f"Error updating VR system data: {e}")
            return True
            
    def _update_ui_state(self):
        """Update UI elements based on current state."""
        try:
            # Update status label and connection button
            if self.vr_status == 'connected':
                self.vr_enabled = True
                self.status_label.config(text="VR System: Connected", fg="green")
                self.connect_btn.config(text="Disconnect VR", state=tk.NORMAL)
                self.settings_frame.config(state=tk.NORMAL)
                self.calibrate_btn.config(state=tk.NORMAL)
                self.reset_btn.config(state=tk.NORMAL)
            elif self.vr_status == 'connecting':
                self.status_label.config(text="VR System: Connecting...", fg="orange")
                self.connect_btn.config(state=tk.DISABLED)
            elif self.vr_status == 'disconnecting':
                self.status_label.config(text="VR System: Disconnecting...", fg="orange")
                self.connect_btn.config(state=tk.DISABLED)
            else:  # disconnected
                self.vr_enabled = False
                self.status_label.config(text="VR System: Disconnected", fg="red")
                self.connect_btn.config(text="Connect VR", state=tk.NORMAL)
                self.settings_frame.config(state=tk.DISABLED)
                self.calibrate_btn.config(state=tk.DISABLED)
                self.reset_btn.config(state=tk.DISABLED)
                
            # Update headset model
            if hasattr(self, 'model_label'):
                self.model_label.config(text=f"Headset: {self.headset_model}")
                
            # Update tracking status
            if hasattr(self, 'tracking_label'):
                if self.tracking_status == 'calibrated':
                    self.tracking_label.config(text="Tracking: Calibrated", fg="green")
                elif self.tracking_status == 'active':
                    self.tracking_label.config(text="Tracking: Active", fg="green")
                elif self.tracking_status == 'calibrating':
                    self.tracking_label.config(text="Tracking: Calibrating...", fg="orange")
                else:  # unavailable
                    self.tracking_label.config(text="Tracking: Not Available", fg="gray")
                    
            # Update battery status
            if hasattr(self, 'battery_label'):
                if self.battery_level >= 0:
                    if self.battery_charging:
                        self.battery_label.config(text=f"Battery: {self.battery_level}% (Charging)", fg="green")
                    else:
                        if self.battery_level > 20:
                            self.battery_label.config(text=f"Battery: {self.battery_level}%", fg="green")
                        else:
                            self.battery_label.config(text=f"Battery: {self.battery_level}% (Low)", fg="red")
                else:
                    self.battery_label.config(text="Battery: Unknown", fg="gray")
        except Exception as e:
            logger.error(f"Error updating VR UI state: {e}")
            logger.error(f"Error details: {str(e)}")
