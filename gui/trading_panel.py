#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Trading Panel GUI

This module provides a Tkinter-based trading panel for the Kingdom AI system,
allowing users to place orders and view real-time market data.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import asyncio
import logging
import threading
import json
import time
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Callable
from core.base_component import BaseComponent

logger = logging.getLogger('KingdomAI.TradingPanel')

class TradingPanel(BaseComponent):
    """Tkinter-based trading panel GUI."""
    
    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None):
        """Initialize trading panel component."""
        super().__init__(event_bus)
        self.config = config or {}
        
        # GUI elements
        self.parent = None
        self.price_labels = {}
        self.order_history = None
        self.symbol_var = None
        self.quantity_var = None
        self.price_var = None
        self.market_order_var = None
        self.side_var = None
        self.strategy_var = None
        self.strategy_params_frame = None
        self.trader_id_var = None
        self.price_entry = None
        self.chart_canvas = None
        
        # Trading state
        self.current_prices = {}
        self.depth_data = {}  # Store depth data for market depth visualization
        self.trade_history = None  # Will be initialized when needed
        self.running = False
        self.update_loop_task = None
        self._refresh_timer_id = None
        
        # Strategy state
        self.strategies = {}
        self.strategy_performance = {}
        self.backtesting_results = {}
        self.performance_figure = None
        self.performance_canvas = None
        
        # Default symbols to track
        self.default_symbols = self.config.get("default_symbols", ["BTCUSDT", "ETHUSDT", "BNBUSDT"])
        
    async def initialize(self) -> bool:
        """Initialize trading panel component and connect to trading interface and ThothAI."""
        logger.info("Initializing trading panel and connecting to trading services")
        
        if self.event_bus:
            # Subscribe to market data events
            self.event_bus.subscribe_sync('market.price_update', self._handle_price_update)
            self.event_bus.subscribe_sync('market.order_response', self._handle_order_response)
            self.event_bus.subscribe_sync('system.shutdown', self._handle_shutdown)
            
            # Strategy-related events
            self.event_bus.subscribe_sync('strategy.created', self._handle_strategy_created)
            self.event_bus.subscribe_sync('strategy.backtest_result', self._handle_backtest_result)
            self.event_bus.subscribe_sync('strategy.optimization_result', self._handle_optimization_result)
            self.event_bus.subscribe_sync('strategy.execution_result', self._handle_execution_result)
            self.event_bus.subscribe_sync('strategy.listed', self._handle_strategy_list)
            
            # Trading interface events for real-time updates
            self.event_bus.subscribe_sync('trading.interface.connected', self._handle_trading_connected)
            self.event_bus.subscribe_sync('trading.interface.market_update', self._handle_market_update)
            self.event_bus.subscribe_sync('trading.interface.order_update', self._handle_order_update)
            self.event_bus.subscribe_sync('trading.interface.portfolio', self._handle_portfolio_update)
            self.event_bus.subscribe_sync('trading.interface.markets', self._handle_markets_list)
            self.event_bus.subscribe_sync('trading.interface.strategy_result', self._handle_strategy_result)
            self.event_bus.subscribe_sync('trading.interface.ai_response', self._handle_ai_response)
            
            # Request available markets list from trading interface
            await self.event_bus.publish("gui.trading.request_markets", {})
            
            # Notify system that trading panel is initialized
            await self.event_bus.publish("trading.panel.initialized", {
                "status": "ready",
                "component": "TradingPanel"
            })
            
            logger.info("Trading panel initialized and connected to trading services")
        
        self.running = True
        return True
        
    async def _handle_strategy_created(self, event_data: Dict[str, Any]) -> None:
        """Handle strategy creation events.
        
        Args:
            event_data: Strategy creation data
        """
        try:
            strategy_id = event_data.get("strategy_id")
            strategy_type = event_data.get("type")
            
            if not strategy_id:
                return
                
            # Store strategy info
            self.strategies[strategy_id] = {
                "id": strategy_id,
                "type": strategy_type,
                "status": "idle"
            }
            
            # Update the UI in the main thread
            if self.parent:
                self.parent.after(0, lambda: self._add_to_history(
                    f"Strategy created: {strategy_id} (type: {strategy_type})"
                ))
                
                # Update strategy dropdown if it exists
                if hasattr(self, "strategy_dropdown") and self.strategy_dropdown:
                    current_values = list(self.strategy_dropdown["values"])
                    current_values.append(strategy_id)
                    self.parent.after(0, lambda: self.strategy_dropdown.configure(values=current_values))
                    
        except Exception as e:
            logger.error(f"Error handling strategy creation: {e}")
            
    async def _handle_backtest_result(self, event_data: Dict[str, Any]) -> None:
        """Handle strategy backtesting results.
        
        Args:
            event_data: Backtesting result data
        """
        try:
            strategy_id = event_data.get("strategy_id")
            cumulative_returns = event_data.get("cumulative_returns", [])
            trades = event_data.get("trades", [])
            metrics = event_data.get("metrics", {})
            
            if not strategy_id:
                return
                
            # Store backtesting results
            self.backtesting_results[strategy_id] = {
                "returns": cumulative_returns,
                "trades": trades,
                "metrics": metrics,
                "timestamp": time.time()
            }
            
            # Update the UI in the main thread
            if self.parent:
                # Add to history
                message = (
                    f"Backtest results for {strategy_id}:\n"
                    f"Total Return: {metrics.get('total_return', 0):.2f}%\n"
                    f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}\n"
                    f"Win Rate: {metrics.get('win_rate', 0):.2f}%\n"
                    f"Trades: {len(trades)}"
                )
                self.parent.after(0, lambda: self._add_to_history(message))
                
                # Update visualization if the strategy is selected
                if self.strategy_var and self.strategy_var.get() == strategy_id:
                    self.parent.after(0, lambda: self._update_performance_chart(strategy_id))
                    
        except Exception as e:
            logger.error(f"Error handling backtest results: {e}")
            
    async def _handle_optimization_result(self, event_data: Dict[str, Any]) -> None:
        """Handle strategy optimization results.
        
        Args:
            event_data: Optimization result data
        """
        try:
            strategy_id = event_data.get("strategy_id")
            best_params = event_data.get("best_params", {})
            improvement = event_data.get("improvement", 0)
            
            if not strategy_id:
                return
                
            # Store optimization results with the strategy
            if strategy_id in self.strategies:
                self.strategies[strategy_id]["optimized_params"] = best_params
                self.strategies[strategy_id]["optimization_improvement"] = improvement
            
            # Update the UI in the main thread
            if self.parent:
                message = (
                    f"Optimization results for {strategy_id}:\n"
                    f"Improvement: {improvement:.2f}%\n"
                    f"Best parameters: {json.dumps(best_params, indent=2)}"
                )
                self.parent.after(0, lambda: self._add_to_history(message))
                
        except Exception as e:
            logger.error(f"Error handling optimization results: {e}")
            
    async def _handle_execution_result(self, event_data: Dict[str, Any]) -> None:
        """Handle strategy execution results.
        
        Args:
            event_data: Execution result data
        """
        try:
            strategy_id = event_data.get("strategy_id")
            action = event_data.get("action")  # buy, sell, hold
            confidence = event_data.get("confidence", 0)
            price = event_data.get("price")
            symbol = event_data.get("symbol")
            
            if not strategy_id or not action:
                return
                
            # Store strategy execution result
            if strategy_id not in self.strategy_performance:
                self.strategy_performance[strategy_id] = []
                
            self.strategy_performance[strategy_id].append({
                "timestamp": time.time(),
                "action": action,
                "confidence": confidence,
                "price": price,
                "symbol": symbol
            })
            
            # Limit stored performance data
            if len(self.strategy_performance[strategy_id]) > 100:
                self.strategy_performance[strategy_id] = self.strategy_performance[strategy_id][-100:]
            
            # Update the UI in the main thread
            if self.parent:
                message = (
                    f"Strategy {strategy_id} signal: {action.upper()} "
                    f"{symbol} at {price} (confidence: {confidence:.2f})"
                )
                self.parent.after(0, lambda: self._add_to_history(message))
                
                # If auto-trading is enabled, execute the trade
                # This would be controlled by a UI setting
                
        except Exception as e:
            logger.error(f"Error handling execution results: {e}")
            
    async def _handle_strategy_list(self, event_data: Dict[str, Any]) -> None:
        """Handle strategy listing.
        
        Args:
            event_data: Strategy list data
        """
        try:
            strategies = event_data.get("strategies", [])
            
            # Store strategies
            for strategy in strategies:
                strategy_id = strategy.get("id")
                if strategy_id:
                    self.strategies[strategy_id] = strategy
            
            # Update the UI in the main thread
            if self.parent and hasattr(self, "strategy_dropdown"):
                # Update strategy dropdown
                strategy_ids = list(self.strategies.keys())
                self.parent.after(0, lambda: self.strategy_dropdown.configure(values=strategy_ids))
                
        except Exception as e:
            logger.error(f"Error handling strategy list: {e}")
            
    async def _handle_price_update(self, event_data: Dict[str, Any]):
        """Handle price update events from the market API.
        
        Args:
            event_data: Price update data
        """
        try:
            symbol = event_data.get("symbol", "")
            price = event_data.get("price", 0)
            
            # Store current price
            self.current_prices[symbol] = price
            
            # Schedule UI update in main thread
            if symbol in self.price_labels:
                if self.parent:
                    self.parent.after(0, lambda: self._update_price_label(symbol, price))
                
        except Exception as e:
            logger.error(f"Error handling price update: {e}")
            
    def _update_price_label(self, symbol: str, price: float):
        """Update price label in the main thread.
        
        Args:
            symbol: Symbol to update
            price: New price
        """
        if symbol in self.price_labels:
            self.price_labels[symbol]["price"].config(text=f"${price:.2f}")
            
    async def _handle_order_response(self, event_data: Dict[str, Any]):
        """Handle order response events.
        
        Args:
            event_data: Order response data
        """
        try:
            success = event_data.get("success", False)
            order_id = event_data.get("order_id")
            error = event_data.get("error")
            
            if success:
                message = f"Order placed successfully (ID: {order_id})"
                if self.parent:
                    self.parent.after(0, lambda: self._add_to_history(message))
                    self.parent.after(0, lambda: messagebox.showinfo("Order Placed", message))
            else:
                message = f"Order failed: {error}"
                if self.parent:
                    self.parent.after(0, lambda: self._add_to_history(message))
                    self.parent.after(0, lambda: messagebox.showerror("Order Failed", message))
                
        except Exception as e:
            logger.error(f"Error handling order response: {e}")
            
    def _handle_close(self):
        """Handle window close event."""
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            self.running = False
            if self.parent and hasattr(self.parent, 'destroy'):
                self.parent.destroy()
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("system.component_shutdown", {"component": "trading_panel"}),
                asyncio.get_event_loop()
            )
            
    async def _handle_shutdown(self, _: Dict[str, Any]):
        """Handle system shutdown event."""
        if self.parent and self.parent.winfo_exists():
            self.parent.after(0, self.parent.destroy)
            
    def _add_to_history(self, message: str) -> None:
        """Add a message to the order history."""
        if not self.order_history:
            return
            
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Enable text widget for editing
        self.order_history.config(state=tk.NORMAL)
        
        # Add the message with timestamp
        self.order_history.insert(tk.END, f"[{timestamp}] {message}\n")
        
        # Autoscroll to the end
        self.order_history.see(tk.END)
        
        # Disable editing again
        self.order_history.config(state=tk.DISABLED)
        
    def _apply_strategy(self) -> None:
        """Apply the selected trading strategy."""
        if not self.parent or not self.strategy_var or not self.symbol_var:
            logger.error("UI components not initialized")
            return
            
        strategy = self.strategy_var.get()
        
        if strategy == "None":
            messagebox.showinfo("Strategy", "Please select a trading strategy.", parent=self.parent)
            return
            
        # Configuration based on strategy type
        config = self._get_strategy_config()
        
        # Apply the strategy by sending to the strategy manager
        if self.event_bus:
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("strategy.execute", {
                    "strategy_id": strategy,
                    "symbol": self.symbol_var.get(),
                    "config": config
                }),
                asyncio.get_event_loop()
            )
        
        self._add_to_history(f"Applied {strategy} strategy to {self.symbol_var.get()}")
        
    def _backtest_strategy(self) -> None:
        """Backtest the selected trading strategy."""
        if not self.parent or not self.strategy_var or not self.symbol_var:
            logger.error("UI components not initialized")
            return
            
        strategy = self.strategy_var.get()
        
        if strategy == "None":
            messagebox.showinfo("Strategy", "Please select a trading strategy.", parent=self.parent)
            return
            
        # Get strategy configuration
        config = self._get_strategy_config()
        
        # Request backtesting
        if self.event_bus:
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("strategy.backtest", {
                    "strategy_id": strategy,
                    "symbol": self.symbol_var.get(),
                    "config": config,
                    "timeframe": "1d",
                    "start_time": int(time.time()) - (86400 * 30),  # Last 30 days
                    "end_time": int(time.time())
                }),
                asyncio.get_event_loop()
            )
        
        self._add_to_history(f"Backtesting {strategy} strategy on {self.symbol_var.get()}")
        
    def _setup_strategy_section(self, parent_frame: tk.Widget) -> None:
        """Set up the trading strategy section."""
        # Strategy frame
        strategy_frame = ttk.LabelFrame(parent_frame, text="Trading Strategies", padding="5")
        strategy_frame.pack(fill=tk.X, pady=5)
        
        # Strategy selection
        strategy_selector_frame = ttk.Frame(strategy_frame, style="Trading.TFrame")
        strategy_selector_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(strategy_selector_frame, text="Strategy:", style="Trading.TLabel").pack(side=tk.LEFT)
        self.strategy_var = tk.StringVar(value="None")
        strategies = ["None", "Moving Average", "RSI", "MACD", "Bollinger Bands", "Custom", "Anomaly Detection"]
        self.strategy_dropdown = ttk.Combobox(strategy_selector_frame, textvariable=self.strategy_var, 
                                values=strategies, state="readonly", width=15)
        self.strategy_dropdown.pack(side=tk.LEFT, padx=5)
        self.strategy_dropdown.bind("<<ComboboxSelected>>", self._on_strategy_selected)
        
        # Create new strategy button
        ttk.Button(strategy_selector_frame, text="Create New",
                  command=self._create_new_strategy).pack(side=tk.LEFT, padx=5)
        
        # Strategy parameters frame
        self.strategy_params_frame = ttk.Frame(strategy_frame, style="Trading.TFrame")
        self.strategy_params_frame.pack(fill=tk.X, pady=5)
        
        # Strategy control buttons
        strategy_control_frame = ttk.Frame(strategy_frame, style="Trading.TFrame")
        strategy_control_frame.pack(fill=tk.X, pady=2)
        
        ttk.Button(strategy_control_frame, text="Apply Strategy", 
                  command=self._apply_strategy).pack(side=tk.LEFT, padx=5)
        ttk.Button(strategy_control_frame, text="Backtest", 
                  command=self._backtest_strategy).pack(side=tk.LEFT, padx=5)
        ttk.Button(strategy_control_frame, text="Optimize", 
                  command=self._optimize_strategy).pack(side=tk.LEFT, padx=5)
        ttk.Button(strategy_control_frame, text="Save Strategy", 
                  command=self._save_strategy).pack(side=tk.LEFT, padx=5)
        
        # Performance visualization
        performance_frame = ttk.LabelFrame(parent_frame, text="Strategy Performance", padding="5")
        performance_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create matplotlib figure for performance visualization
        self.performance_figure = Figure(figsize=(6, 4), dpi=100)
        self.performance_canvas = FigureCanvasTkAgg(self.performance_figure, performance_frame)
        self.performance_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def _create_new_strategy(self) -> None:
        """Create a new trading strategy."""
        if not self.parent or not self.symbol_var:
            logger.error("UI components not initialized")
            return
            
        # Create a popup window for strategy creation
        strategy_window = tk.Toplevel(self.parent)
        strategy_window.title("Create New Strategy")
        strategy_window.geometry("400x300")
        strategy_window.resizable(False, False)
        
        # Strategy type selection
        type_frame = ttk.Frame(strategy_window, padding="10", style="Trading.TFrame")
        type_frame.pack(fill=tk.X)
        
        ttk.Label(type_frame, text="Strategy Type:", style="Trading.TLabel").pack(side=tk.LEFT)
        strategy_type_var = tk.StringVar(value="anomaly_detection")
        strategy_types = ["anomaly_detection", "reinforcement_learning", "custom"]
        ttk.Combobox(type_frame, textvariable=strategy_type_var,
                    values=strategy_types, state="readonly", width=20).pack(side=tk.LEFT, padx=5)
        
        # Strategy ID
        id_frame = ttk.Frame(strategy_window, padding="10", style="Trading.TFrame")
        id_frame.pack(fill=tk.X)
        
        ttk.Label(id_frame, text="Strategy ID:", style="Trading.TLabel").pack(side=tk.LEFT)
        strategy_id_var = tk.StringVar(value=f"strategy_{len(self.strategies)}")
        ttk.Entry(id_frame, textvariable=strategy_id_var, width=25).pack(side=tk.LEFT, padx=5)
        
        # Symbol selection
        symbol_frame = ttk.Frame(strategy_window, padding="10", style="Trading.TFrame")
        symbol_frame.pack(fill=tk.X)
        
        ttk.Label(symbol_frame, text="Symbol:", style="Trading.TLabel").pack(side=tk.LEFT)
        symbol_var = tk.StringVar(value=self.symbol_var.get())
        ttk.Combobox(symbol_frame, textvariable=symbol_var,
                    values=self.default_symbols, state="readonly", width=15).pack(side=tk.LEFT, padx=5)
        
        # Parameters frame (expandable based on strategy type)
        params_frame = ttk.LabelFrame(strategy_window, text="Parameters", padding="10")
        params_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create button
        ttk.Button(strategy_window, text="Create Strategy",
                  command=lambda: self._submit_strategy_creation(
                      strategy_type_var.get(),
                      strategy_id_var.get(),
                      symbol_var.get(),
                      strategy_window
                  )).pack(side=tk.BOTTOM, pady=10)
                  
    def _submit_strategy_creation(self, strategy_type: str, strategy_id: str, 
                                symbol: str, window: tk.Toplevel) -> None:
        """Submit strategy creation to AI trading system."""
        if not strategy_id or not strategy_type or not symbol:
            messagebox.showerror("Error", "Please fill in all fields", parent=window)
            return
            
        if self.event_bus:
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("strategy.create", {
                    "strategy_id": strategy_id,
                    "type": strategy_type,
                    "symbol": symbol
                }),
                asyncio.get_event_loop()
            )
        
        self._add_to_history(f"Creating strategy: {strategy_id} (type: {strategy_type})")
        window.destroy()
        
    def _on_strategy_selected(self, event) -> None:
        """Handle strategy selection in dropdown."""
        strategy = self.strategy_var.get()
        
        # Clear parameters frame
        if self.strategy_params_frame:
            for widget in self.strategy_params_frame.winfo_children():
                widget.destroy()
            
        if strategy == "None":
            return
            
        # Display parameters based on strategy type
        if strategy in self.strategies:
            # Display stored strategy parameters
            strategy_data = self.strategies.get(strategy, {})
            strategy_type = strategy_data.get("type", "unknown")
            
            ttk.Label(self.strategy_params_frame, 
                     text=f"Type: {strategy_type}").pack(side=tk.TOP, anchor=tk.W)
                     
            # Display parameters if available
            params = strategy_data.get("params", {})
            for param_name, param_value in params.items():
                param_frame = ttk.Frame(self.strategy_params_frame, style="Trading.TFrame")
                param_frame.pack(fill=tk.X, pady=2)
                
                ttk.Label(param_frame, text=f"{param_name}:", style="Trading.TLabel").pack(side=tk.LEFT)
                ttk.Entry(param_frame, width=10).pack(side=tk.LEFT, padx=5)
                
            # Update performance chart if results are available
            self._update_performance_chart(strategy)
        else:
            # Display default parameters based on strategy name
            self._setup_default_params(strategy)
            
    def _setup_default_params(self, strategy_name: str) -> None:
        """Set up default parameters for a strategy."""
        params = {}
        
        if strategy_name == "Moving Average":
            params = {
                "short_period": "9",
                "long_period": "21",
                "signal_period": "9"
            }
        elif strategy_name == "RSI":
            params = {
                "period": "14",
                "overbought": "70",
                "oversold": "30"
            }
        elif strategy_name == "MACD":
            params = {
                "fast_period": "12",
                "slow_period": "26",
                "signal_period": "9"
            }
        elif strategy_name == "Bollinger Bands":
            params = {
                "period": "20",
                "std_dev": "2.0"
            }
        elif strategy_name == "Anomaly Detection":
            params = {
                "threshold": "0.5",
                "window": "20"
            }
            
        # Create UI elements for each parameter
        for param_name, default_value in params.items():
            param_frame = ttk.Frame(self.strategy_params_frame, style="Trading.TFrame")
            param_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(param_frame, text=f"{param_name}:", style="Trading.TLabel").pack(side=tk.LEFT)
            param_var = tk.StringVar(value=default_value)
            ttk.Entry(param_frame, textvariable=param_var, 
                     width=10).pack(side=tk.LEFT, padx=5)
                     
    def _update_performance_chart(self, strategy_id: str) -> None:
        """Update the performance chart for a strategy."""
        if not self.performance_figure:
            return
            
        # Clear the figure
        self.performance_figure.clear()
        
        # Check if we have backtest results for this strategy
        if strategy_id in self.backtesting_results:
            backtest_data = self.backtesting_results.get(strategy_id, {})
            if not backtest_data:
                return
                
            returns = backtest_data.get("returns", [])
            if returns:
                # Convert returns to a pandas Series if it's not already
                if not isinstance(returns, pd.Series):
                    # If it's a list, convert to Series
                    if isinstance(returns, list):
                        returns = pd.Series(returns)
                    # If it's a dict, convert to Series
                    elif isinstance(returns, dict):
                        returns = pd.Series(list(returns.values()), index=list(returns.keys()))
                
                ax = self.performance_figure.add_subplot(111)
                
                # Convert to numpy arrays for plotting (fixes the typing issue)
                if isinstance(returns, pd.Series):
                    x_values = np.array(returns.index.astype(str))
                    y_values = np.array(returns.values)
                    ax.plot(x_values, y_values, label='Strategy Returns')
                else:
                    # Fallback if we can't convert to Series
                    ax.plot(range(len(returns)), returns, label='Strategy Returns')
                
                ax.set_title(f"Strategy Performance: {strategy_id}")
                ax.set_xlabel('Time')
                ax.set_ylabel('Returns (%)')
                ax.grid(True)
                ax.legend()
                
                # Update metrics display
                metrics = backtest_data.get("metrics", {})
                if metrics:
                    info_text = (
                        f"Total Return: {metrics.get('total_return', 0):.2f}%\n"
                        f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}\n"
                        f"Win Rate: {metrics.get('win_rate', 0):.2f}%"
                    )
                    ax.text(0.02, 0.02, info_text, transform=ax.transAxes,
                           bbox=dict(facecolor='white', alpha=0.8))
        else:
            # Display placeholder
            ax = self.performance_figure.add_subplot(111)
            ax.text(0.5, 0.5, "No performance data available.\nRun a backtest first.",
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes)
            ax.set_title(f"Strategy Performance: {strategy_id}")
            ax.axis('off')
            
        # Refresh the canvas
        if self.performance_canvas:
            self.performance_canvas.draw()
            
    def _optimize_strategy(self) -> None:
        """Optimize the selected trading strategy."""
        if not self.parent or not self.strategy_var or not self.symbol_var:
            logger.error("UI components not initialized")
            return
            
        strategy = self.strategy_var.get()
        
        if strategy == "None":
            messagebox.showinfo("Strategy", "Please select a trading strategy.", parent=self.parent)
            return
            
        # Get strategy configuration
        config = self._get_strategy_config()
        
        # Request optimization
        if self.event_bus:
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("strategy.optimize", {
                    "strategy_id": strategy,
                    "symbol": self.symbol_var.get(),
                    "config": config,
                    "timeframe": "1d",
                    "start_time": int(time.time()) - (86400 * 30),  # Last 30 days
                    "end_time": int(time.time())
                }),
                asyncio.get_event_loop()
            )
        
        self._add_to_history(f"Optimizing {strategy} strategy for {self.symbol_var.get()}")
        
    def _get_strategy_config(self) -> Dict[str, Any]:
        """Get strategy configuration from UI elements."""
        if not self.strategy_var:
            return {}
            
        strategy = self.strategy_var.get()
        config = {}
        
        # Check if we have UI elements for parameters
        if self.strategy_params_frame:
            for child in self.strategy_params_frame.winfo_children():
                if isinstance(child, ttk.Frame):
                    # Each parameter is in its own frame with a label and entry
                    param_name = None
                    param_value = None
                    
                    for widget in child.winfo_children():
                        if isinstance(widget, ttk.Label):
                            # Extract parameter name from the label text (remove the colon)
                            text = widget.cget("text")
                            if text.endswith(":"):
                                param_name = text[:-1]
                        elif isinstance(widget, ttk.Entry):
                            # Get parameter value from entry
                            param_value = widget.get()
                            
                    if param_name and param_value:
                        # Convert to appropriate type if needed
                        try:
                            # Try numeric conversion
                            if "." in param_value:
                                param_value = float(param_value)
                            else:
                                param_value = int(param_value)
                        except ValueError:
                            # Keep as string if conversion fails
                            pass
                            
                        config[param_name] = param_value
        
        # If no parameters were found in UI, use defaults based on strategy type
        if not config:
            if strategy == "Moving Average":
                config = {
                    "short_period": 9,
                    "long_period": 21,
                    "signal_period": 9,
                    "source": "close"
                }
            elif strategy == "RSI":
                config = {
                    "period": 14,
                    "overbought": 70,
                    "oversold": 30
                }
            elif strategy == "MACD":
                config = {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9
                }
            elif strategy == "Bollinger Bands":
                config = {
                    "period": 20,
                    "std_dev": 2.0
                }
            elif strategy == "Anomaly Detection":
                config = {
                    "threshold": 0.5,
                    "window": 20
                }
                
        return config
        
    def _save_strategy(self) -> None:
        """Save the current strategy configuration."""
        if not self.parent or not self.strategy_var or not self.symbol_var:
            logger.error("UI components not initialized")
            return
            
        strategy = self.strategy_var.get()
        
        if strategy == "None":
            messagebox.showinfo("Strategy", "Please select a trading strategy.", parent=self.parent)
            return
            
        # Get strategy configuration
        config = self._get_strategy_config()
        
        # Save strategy
        if self.event_bus:
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish("strategy.save", {
                    "strategy_id": strategy,
                    "symbol": self.symbol_var.get(),
                    "config": config
                }),
                asyncio.get_event_loop()
            )
        
        self._add_to_history(f"Saved {strategy} strategy for {self.symbol_var.get()}")

    async def _handle_trading_connected(self, event_data: Dict[str, Any]) -> None:
        """Handle successful connection to trading services.
        
        Args:
            event_data: Connection status data
        """
        success = event_data.get("success", False)
        exchange = event_data.get("exchange", "")
        message = event_data.get("message", "")
        markets = event_data.get("markets", [])
        
        if self.parent:
            if success:
                self.parent.after(0, lambda: self._add_to_history(
                    f"Connected to {exchange} trading services. {len(markets)} markets available."
                ))
                
                # Update markets dropdown if available
                if markets and hasattr(self, 'symbol_var') and self.symbol_var:
                    def update_markets():
                        if hasattr(self, 'market_dropdown') and self.market_dropdown:
                            self.market_dropdown['values'] = markets
                            if markets and markets[0]:
                                self.symbol_var.set(markets[0])
                    
                    self.parent.after(0, update_markets)
            else:
                self.parent.after(0, lambda: self._add_to_history(
                    f"Failed to connect to trading services: {message}"
                ))

    async def _handle_market_update(self, event_data: Dict[str, Any]) -> None:
        """Handle market data updates from trading system.
        
        Args:
            event_data: Market data update
        """
        market = event_data.get("market", "")
        price = event_data.get("price", 0.0)
        timestamp = event_data.get("timestamp", 0)
        
        if market and price > 0:
            self.current_prices[market] = price
            
            # Update price label in UI
            if self.parent:
                self.parent.after(0, lambda m=market, p=price: self._update_price_label(m, p))

    async def _handle_order_update(self, event_data: Dict[str, Any]) -> None:
        """Handle order status updates from trading system.
        
        Args:
            event_data: Order update data
        """
        order_id = event_data.get("order_id", "")
        status = event_data.get("status", "")
        symbol = event_data.get("symbol", "")
        side = event_data.get("side", "")
        quantity = event_data.get("quantity", "")
        
        if order_id and self.parent:
            self.parent.after(0, lambda: self._add_to_history(
                f"Order update: {order_id} - {symbol} {side} {quantity} - Status: {status}"
            ))

    async def _handle_portfolio_update(self, event_data: Dict[str, Any]) -> None:
        """Handle portfolio updates from trading system.
        
        Args:
            event_data: Portfolio data
        """
        portfolio = event_data.get("portfolio", {})
        
        if not portfolio or not self.parent:
            return
            
        # Update portfolio display in the UI
        def update_portfolio():
            if hasattr(self, 'portfolio_tree') and self.portfolio_tree:
                # Clear existing items
                for item in self.portfolio_tree.get_children():
                    self.portfolio_tree.delete(item)
                
                # Add new items
                for asset, details in portfolio.items():
                    balance = details.get("balance", 0)
                    value_usd = details.get("value_usd", 0)
                    self.portfolio_tree.insert("", tk.END, values=(asset, balance, f"${value_usd:,.2f}"))
        
        self.parent.after(0, update_portfolio)

    async def _handle_markets_list(self, event_data: Dict[str, Any]) -> None:
        """Handle list of available markets from trading system.
        
        Args:
            event_data: Markets data
        """
        markets = event_data.get("markets", [])
        
        if markets and self.parent:
            def update_markets():
                if hasattr(self, 'market_dropdown') and self.market_dropdown:
                    self.market_dropdown['values'] = markets
                    if markets and markets[0]:
                        self.symbol_var.set(markets[0])
            
            self.parent.after(0, update_markets)

    async def _handle_strategy_result(self, event_data: Dict[str, Any]) -> None:
        """Handle strategy execution results from trading system.
        
        Args:
            event_data: Strategy execution result
        """
        strategy_name = event_data.get("strategy_name", "")
        market = event_data.get("market", "")
        success = event_data.get("success", False)
        message = event_data.get("message", "")
        orders_generated = event_data.get("orders_generated", 0)
        
        if self.parent:
            status = "Success" if success else "Failed"
            self.parent.after(0, lambda: self._add_to_history(
                f"Strategy {strategy_name} for {market}: {status}. {message} Orders: {orders_generated}"
            ))

    async def _handle_ai_response(self, event_data: Dict[str, Any]) -> None:
        """Handle AI-generated trading insights and responses.
        
        Args:
            event_data: AI response data
        """
        success = event_data.get("success", False)
        response = event_data.get("response", "")
        query = event_data.get("query", "")
        
        if not self.parent:
            return
            
        if success and response:
            self.parent.after(0, lambda: self._add_to_history(
                f"AI Trading Assistant: {response}"
            ))
        else:
            self.parent.after(0, lambda: self._add_to_history(
                f"AI Trading Assistant failed to respond to: {query}"
            ))
        
    def initialize_sync(self):

        
        """Synchronous version of initialize"""

        
        return True
