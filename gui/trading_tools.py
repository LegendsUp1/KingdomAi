#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Trading Tools GUI for Kingdom AI.

This module provides a graphical interface for trading tools,
including market selection, chart display, order entry, and portfolio management.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import logging
import json
import random
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable

# Setup logging
logger = logging.getLogger(__name__)

class TradingToolsGUI:
    """Trading Tools GUI for Kingdom AI system."""
    
    def __init__(self, master=None, config: Optional[Dict[str, Any]] = None, event_bus=None):
        """
        Initialize the Trading Tools GUI.
        
        Args:
            master: Tkinter master widget
            config: Configuration for the trading tools
            event_bus: Event bus for component communication
        """
        self.master = master or tk.Tk()
        self.master.title("Kingdom AI - Trading Tools")
        self.master.geometry("1200x800")
        self.master.minsize(1000, 700)
        
        self.config = config or {}
        self.event_bus = event_bus
        self.is_connected = False
        self.selected_market = tk.StringVar()
        self.order_type = tk.StringVar(value="limit")
        self.order_side = tk.StringVar(value="buy")
        self.amount = tk.StringVar()
        self.price = tk.StringVar()
        
        # Store available markets
        self.markets = []
        
        # Initialize the UI components
        self._init_ui()
        
        logger.info("Trading Tools GUI initialized")
    
    def _init_ui(self):
        """Initialize the user interface."""
        # Create main frame with padding
        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create top frame for market selection and connection status
        self._create_top_frame()
        
        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create trading tab
        self.trading_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.trading_tab, text="Trading")
        
        # Create code generator/chat tab
        self.chat_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_tab, text="AI Assistant")
        
        # Create content for trading tab
        self._create_content_frame(self.trading_tab)
        
        # Create content for chat tab
        self._create_chat_frame(self.chat_tab)
        
        # Create bottom frame for status and logs
        self._create_bottom_frame()
    
    def _create_top_frame(self):
        """Create the top frame with market selection and connection status."""
        top_frame = ttk.Frame(self.main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Market selection
        ttk.Label(top_frame, text="Market:").pack(side=tk.LEFT, padx=(0, 5))
        self.market_combo = ttk.Combobox(
            top_frame, 
            textvariable=self.selected_market,
            state="readonly",
            width=20
        )
        self.market_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.market_combo.bind("<<ComboboxSelected>>", self._on_market_selected)
        
        # Connection status and controls
        self.status_label = ttk.Label(top_frame, text="Status: Disconnected", foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.connect_button = ttk.Button(top_frame, text="Connect", command=self._connect)
        self.connect_button.pack(side=tk.LEFT)
        
        # Refresh button
        self.refresh_button = ttk.Button(top_frame, text="Refresh", command=self._refresh_data)
        self.refresh_button.pack(side=tk.LEFT, padx=(10, 0))
    
    def _create_content_frame(self, parent):
        """Create the content frame containing chart and trading controls."""
        content_frame = ttk.Frame(parent)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure content frame grid columns
        content_frame.columnconfigure(0, weight=3)  # Chart area takes 3/4
        content_frame.columnconfigure(1, weight=1)  # Controls take 1/4
        content_frame.rowconfigure(0, weight=1)
        
        # Chart area - placeholder for now
        self.chart_frame = ttk.LabelFrame(content_frame, text="Chart")
        self.chart_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Placeholder for chart
        self.chart_placeholder = ttk.Label(self.chart_frame, text="Chart will appear here")
        self.chart_placeholder.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Trading controls
        self._create_trading_controls(content_frame)
    
    def _create_trading_controls(self, parent):
        """Create the trading controls panel."""
        # Trading controls frame
        trading_frame = ttk.LabelFrame(parent, text="Trading Controls")
        trading_frame.grid(row=0, column=1, sticky="nsew")
        
        # Order entry section
        order_frame = ttk.Frame(trading_frame)
        order_frame.pack(fill=tk.X, expand=False, padx=10, pady=10)
        
        # Order type selection
        ttk.Label(order_frame, text="Order Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        order_type_frame = ttk.Frame(order_frame)
        order_type_frame.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(
            order_type_frame, text="Limit", value="limit", variable=self.order_type
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(
            order_type_frame, text="Market", value="market", variable=self.order_type
        ).pack(side=tk.LEFT)
        
        # Order side selection
        ttk.Label(order_frame, text="Side:").grid(row=1, column=0, sticky=tk.W, pady=5)
        side_frame = ttk.Frame(order_frame)
        side_frame.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(
            side_frame, text="Buy", value="buy", variable=self.order_side
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(
            side_frame, text="Sell", value="sell", variable=self.order_side
        ).pack(side=tk.LEFT)
        
        # Amount
        ttk.Label(order_frame, text="Amount:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(order_frame, textvariable=self.amount).grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        # Price (only for limit orders)
        ttk.Label(order_frame, text="Price:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(order_frame, textvariable=self.price).grid(row=3, column=1, sticky=tk.EW, pady=5)
        
        # Submit button
        ttk.Button(
            order_frame, text="Place Order", command=self._place_order
        ).grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=(10, 0))
        
        # Portfolio section
        portfolio_frame = ttk.LabelFrame(trading_frame, text="Portfolio")
        portfolio_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Portfolio treeview
        self.portfolio_tree = ttk.Treeview(
            portfolio_frame, 
            columns=("Asset", "Balance", "Value"),
            show="headings"
        )
        self.portfolio_tree.heading("Asset", text="Asset")
        self.portfolio_tree.heading("Balance", text="Balance")
        self.portfolio_tree.heading("Value", text="Value (USD)")
        
        self.portfolio_tree.column("Asset", width=80)
        self.portfolio_tree.column("Balance", width=100)
        self.portfolio_tree.column("Value", width=100)
        
        self.portfolio_tree.pack(fill=tk.BOTH, expand=True)
        
        # Open orders section
        orders_frame = ttk.LabelFrame(trading_frame, text="Open Orders")
        orders_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Orders treeview
        self.orders_tree = ttk.Treeview(
            orders_frame, 
            columns=("ID", "Market", "Type", "Side", "Amount", "Price", "Status"),
            show="headings",
            height=5
        )
        self.orders_tree.heading("ID", text="ID")
        self.orders_tree.heading("Market", text="Market")
        self.orders_tree.heading("Type", text="Type")
        self.orders_tree.heading("Side", text="Side")
        self.orders_tree.heading("Amount", text="Amount")
        self.orders_tree.heading("Price", text="Price")
        self.orders_tree.heading("Status", text="Status")
        
        self.orders_tree.column("ID", width=60)
        self.orders_tree.column("Market", width=70)
        self.orders_tree.column("Type", width=60)
        self.orders_tree.column("Side", width=60)
        self.orders_tree.column("Amount", width=70)
        self.orders_tree.column("Price", width=70)
        self.orders_tree.column("Status", width=70)
        
        self.orders_tree.pack(fill=tk.BOTH, expand=True)
    
    def _create_chat_frame(self, parent):
        """Create the chat interface for AI assistant and code generation."""
        chat_frame = ttk.Frame(parent)
        chat_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)
        chat_frame.rowconfigure(1, weight=0)
        chat_frame.rowconfigure(2, weight=0)
        
        # Chat history display
        history_frame = ttk.LabelFrame(chat_frame, text="AI Assistant Chat")
        history_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        self.chat_history = scrolledtext.ScrolledText(
            history_frame, 
            wrap=tk.WORD,
            width=50, 
            height=20,
            font=("TkDefaultFont", 10),
            state="disabled"  # Make it read-only
        )
        self.chat_history.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Quick actions frame
        action_frame = ttk.Frame(chat_frame)
        action_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        action_buttons = [
            ("Generate Trading Strategy", self._generate_trading_strategy),
            ("Analyze Market", self._analyze_market),
            ("Optimize Portfolio", self._optimize_portfolio),
            ("Explain Indicator", self._explain_indicator),
            ("Clear Chat", self._clear_chat)
        ]
        
        for i, (text, command) in enumerate(action_buttons):
            btn = ttk.Button(action_frame, text=text, command=command)
            btn.pack(side=tk.LEFT, padx=5)
        
        # User input area
        input_frame = ttk.Frame(chat_frame)
        input_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        
        self.user_input = tk.Text(input_frame, wrap=tk.WORD, height=3)
        self.user_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind Enter key to send message
        self.user_input.bind("<Return>", self._on_enter_pressed)
        self.user_input.bind("<Shift-Return>", lambda e: None)  # Allow Shift+Enter for new line
        
        send_button = ttk.Button(
            input_frame, 
            text="Send", 
            command=self._send_message
        )
        send_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Initialize chat with welcome message
        self._add_message("AI Assistant", "Welcome to Kingdom AI Trading Assistant! How can I help you with your trading today?")
    
    def _on_enter_pressed(self, event):
        """Handle Enter key press in the chat input."""
        # Don't handle if Shift+Enter is pressed (that's for new line)
        if event.state & 0x1:  # Shift is pressed
            return
        
        self._send_message()
        return "break"  # Prevents the default Enter behavior (new line)
    
    def _send_message(self):
        """Send the user message to the AI assistant."""
        message = self.user_input.get("1.0", tk.END).strip()
        if not message:
            return
        
        # Add user message to chat
        self._add_message("You", message)
        
        # Clear input field
        self.user_input.delete("1.0", tk.END)
        
        # Process the message and get a response
        self._process_message(message)
    
    def _add_message(self, sender, message):
        """Add a message to the chat history."""
        # Enable text widget to insert text
        self.chat_history.config(state="normal")
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message with sender and timestamp
        formatted_message = f"[{timestamp}] {sender}: "
        
        # Insert sender with appropriate tag
        self.chat_history.insert(tk.END, formatted_message)
        
        # Make sender bold using tags
        end_pos = self.chat_history.index(tk.END)
        start_pos = f"{float(end_pos) - len(formatted_message)/10}"
        self.chat_history.tag_add("bold", start_pos, end_pos)
        self.chat_history.tag_config("bold", font=("TkDefaultFont", 10, "bold"))
        
        # Insert message text
        self.chat_history.insert(tk.END, f"{message}\n\n")
        
        # Scroll to the end
        self.chat_history.see(tk.END)
        
        # Disable text widget again
        self.chat_history.config(state="disabled")
    
    def _process_message(self, message):
        """Process user message and generate a response."""
        # Simulate AI thinking time
        self.update_status_bar("AI Assistant is thinking...")
        self.master.after(1000, lambda: self._generate_response(message))
    
    def _generate_response(self, message):
        """Generate AI response based on user message."""
        response = None
        
        # Simple keyword-based responses for demonstration
        message_lower = message.lower()
        
        if "hello" in message_lower or "hi" in message_lower or "hey" in message_lower:
            response = "Hello! How can I assist with your trading today?"
        
        elif "strategy" in message_lower or "recommend" in message_lower:
            response = "I'd recommend considering a simple moving average crossover strategy. Would you like me to generate sample code for this?"
        
        elif "market" in message_lower and ("analysis" in message_lower or "analyze" in message_lower):
            response = "Based on recent market data, there's increased volatility in crypto markets. This could present both opportunities and risks."
        
        elif "code" in message_lower or "script" in message_lower or "generate" in message_lower:
            response = "Here's a simple trading strategy code snippet:\n\n```python\ndef simple_moving_average_strategy(data, short_window=20, long_window=50):\n    # Calculate moving averages\n    data['short_ma'] = data['close'].rolling(window=short_window).mean()\n    data['long_ma'] = data['close'].rolling(window=long_window).mean()\n    \n    # Generate signals\n    data['signal'] = 0\n    data.loc[data['short_ma'] > data['long_ma'], 'signal'] = 1  # Buy signal\n    data.loc[data['short_ma'] < data['long_ma'], 'signal'] = -1  # Sell signal\n    \n    return data\n```\n\nWould you like me to explain how this works?"
        
        elif "portfolio" in message_lower and "optimize" in message_lower:
            response = "For portfolio optimization, I'd suggest using Modern Portfolio Theory to balance risk and return. Would you like me to generate an example?"
        
        elif "indicator" in message_lower or "indicators" in message_lower:
            response = "Common technical indicators include Moving Averages, RSI, MACD, and Bollinger Bands. Each has different applications for market analysis. Which one would you like to learn more about?"
        
        elif "thank" in message_lower or "thanks" in message_lower:
            response = "You're welcome! Feel free to ask if you need any other assistance with your trading."
        
        else:
            response = "I'm here to help with trading strategies, market analysis, and code generation. What specific trading topic can I assist you with?"
        
        # Add AI response to chat
        self._add_message("AI Assistant", response)
        self.update_status_bar("Ready")
        
    def _generate_trading_strategy(self):
        """Generate a trading strategy based on current market."""
        market = self.selected_market.get() if self.selected_market.get() else "BTC/USD"
        self._add_message("You", f"Please generate a trading strategy for {market}")
        
        strategy_code = (
            f"Here's a momentum-based trading strategy for {market}:\n\n"
            "```python\n"
            "import pandas as pd\n"
            "import numpy as np\n\n"
            "def momentum_strategy(data, lookback_period=14):\n"
            "    # Calculate returns\n"
            "    data['returns'] = data['close'].pct_change()\n\n"
            "    # Calculate momentum (cumulative returns over lookback period)\n"
            "    data['momentum'] = data['returns'].rolling(window=lookback_period).sum()\n\n"
            "    # Generate signals\n"
            "    data['signal'] = 0\n"
            "    data.loc[data['momentum'] > 0, 'signal'] = 1  # Buy when momentum is positive\n"
            "    data.loc[data['momentum'] < 0, 'signal'] = -1  # Sell when momentum is negative\n\n"
            "    # Calculate strategy returns\n"
            "    data['strategy_returns'] = data['signal'].shift(1) * data['returns']\n\n"
            "    return data\n"
            "```\n\n"
            "This strategy buys when price momentum is positive and sells when it's negative. "
            "You can adjust the lookback period to make it more or less sensitive to recent price changes."
        )
        
        self._add_message("AI Assistant", strategy_code)
    
    def _analyze_market(self):
        """Provide market analysis for the selected market."""
        market = self.selected_market.get() if self.selected_market.get() else "BTC/USD"
        self._add_message("You", f"Can you analyze the current {market} market?")
        
        # Simulate market analysis
        analysis = (
            f"## Market Analysis for {market}\n\n"
            "### Current Market Conditions\n"
            "- Market sentiment: Cautiously bullish\n"
            "- Volatility: Moderate\n"
            "- Volume: Above average\n\n"
            "### Key Levels\n"
            "- Resistance: $42,500\n"
            "- Support: $38,750\n"
            "- 200-day MA: $39,875\n\n"
            "### Market Drivers\n"
            "- Increased institutional adoption\n"
            "- Regulatory developments in major markets\n"
            "- Technical breakout from consolidation pattern\n\n"
            "### Recommendation\n"
            "Consider scaling into positions at support levels with tight stop losses. "
            "The market is showing signs of strength but remains susceptible to broader "
            "macroeconomic factors."
        )
        
        self._add_message("AI Assistant", analysis)
    
    def _optimize_portfolio(self):
        """Generate a portfolio optimization strategy."""
        self._add_message("You", "How can I optimize my crypto portfolio?")
        
        optimization = (
            "# Portfolio Optimization Strategy\n\n"
            "### Modern Portfolio Theory Approach\n\n"
            "```python\n"
            "import numpy as np\n"
            "import pandas as pd\n"
            "from scipy.optimize import minimize\n\n"
            "def portfolio_optimization(returns, target_return=None):\n"
            "    # Calculate expected returns and covariance matrix\n"
            "    mean_returns = returns.mean()\n"
            "    cov_matrix = returns.cov()\n\n"
            "    # Number of assets\n"
            "    num_assets = len(mean_returns)\n\n"
            "    # Constraints and bounds\n"
            "    constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]  # Weights sum to 1\n"
            "    if target_return is not None:\n"
            "        constraints.append({\n"
            "            'type': 'eq',\n"
            "            'fun': lambda x: np.sum(x * mean_returns) - target_return\n"
            "        })\n\n"
            "    bounds = tuple((0, 1) for _ in range(num_assets))  # Weights between 0-1\n\n"
            "    # Objective function (minimize portfolio variance)\n"
            "    def objective(weights):\n"
            "        portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))\n"
            "        return portfolio_variance\n\n"
            "    # Initial guess (equal weights)\n"
            "    init_guess = np.array([1/num_assets] * num_assets)\n\n"
            "    # Run optimization\n"
            "    optimal_weights = minimize(\n"
            "        objective, init_guess, method='SLSQP',\n"
            "        bounds=bounds, constraints=constraints\n"
            "    )\n\n"
            "    return optimal_weights['x']\n"
            "```\n\n"
            "This code implements a portfolio optimizer based on Modern Portfolio Theory, "
            "which aims to maximize returns for a given level of risk. It works by finding "
            "the optimal allocation of assets that minimizes portfolio variance while meeting return targets.\n\n"
            "To use it effectively:\n"
            "1. Start with a diverse set of assets that have low correlation\n"
            "2. Rebalance periodically (monthly or quarterly)\n"
            "3. Monitor market conditions and adjust your target return accordingly"
        )
        
        self._add_message("AI Assistant", optimization)
    
    def _explain_indicator(self):
        """Explain a trading indicator."""
        self._add_message("You", "Can you explain the RSI indicator?")
        
        explanation = (
            "# Relative Strength Index (RSI)\n\n"
            "RSI is a momentum oscillator that measures the speed and change of price movements "
            "on a scale from 0 to 100.\n\n"
            "### How RSI Works\n"
            "- RSI compares the magnitude of recent gains to recent losses\n"
            "- Formula: RSI = 100 - (100 / (1 + RS))\n"
            "- Where RS = Average Gain / Average Loss over a specific period (typically 14 days)\n\n"
            "### Interpretation\n"
            "- RSI > 70: Potentially overbought conditions\n"
            "- RSI < 30: Potentially oversold conditions\n"
            "- Divergence: When price makes a new high/low but RSI doesn't, suggesting potential reversal\n\n"
            "### Implementation in Python\n"
            "```python\n"
            "def calculate_rsi(data, period=14):\n"
            "    # Calculate price changes\n"
            "    delta = data['close'].diff()\n\n"
            "    # Separate gains and losses\n"
            "    gain = delta.where(delta > 0, 0)\n"
            "    loss = -delta.where(delta < 0, 0)\n\n"
            "    # Calculate average gain and loss\n"
            "    avg_gain = gain.rolling(window=period).mean()\n"
            "    avg_loss = loss.rolling(window=period).mean()\n\n"
            "    # Calculate RS\n"
            "    rs = avg_gain / avg_loss\n\n"
            "    # Calculate RSI\n"
            "    rsi = 100 - (100 / (1 + rs))\n\n"
            "    return rsi\n"
            "```\n\n"
            "RSI is best used in conjunction with other indicators and price action analysis for confirmation."
        )
        
        self._add_message("AI Assistant", explanation)
    
    def _clear_chat(self):
        """Clear the chat history."""
        self.chat_history.config(state="normal")
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.config(state="disabled")
        self._add_message("AI Assistant", "Chat history cleared. How can I help you with your trading today?")
    
    def _create_bottom_frame(self):
        """Create the bottom frame with status and logs."""
        bottom_frame = ttk.Frame(self.main_frame)
        bottom_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Status bar
        self.status_bar = ttk.Label(
            bottom_frame, 
            text="Ready",
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_bar.pack(fill=tk.X)
    
    def _on_market_selected(self, event):
        """Handle market selection event."""
        market = self.selected_market.get()
        self.update_status_bar(f"Selected market: {market}")
        logger.info(f"Market selected: {market}")
        
        # You would normally update the chart and other data here
        # For now, just update the placeholder text
        self.chart_placeholder.config(text=f"Chart for {market} will appear here")
    
    def _connect(self):
        """Connect to trading service."""
        if not self.is_connected:
            self.update_status_bar("Connecting to trading service...")
            
            # Simulate connection
            def connect_thread():
                # In a real implementation, this would connect to the trading API
                # For now, just simulate a delay
                import time
                time.sleep(1)
                
                # Update UI in the main thread
                self.master.after(0, self._on_connected)
            
            threading.Thread(target=connect_thread, daemon=True).start()
        else:
            # Disconnect
            self.is_connected = False
            self.status_label.config(text="Status: Disconnected", foreground="red")
            self.connect_button.config(text="Connect")
            self.update_status_bar("Disconnected from trading service")
    
    def _on_connected(self):
        """Handle successful connection."""
        self.is_connected = True
        self.status_label.config(text="Status: Connected", foreground="green")
        self.connect_button.config(text="Disconnect")
        self.update_status_bar("Connected to trading service")
        
        # Populate markets dropdown with some example markets
        self.markets = [
            "BTC/USD", "ETH/USD", "XRP/USD", "ADA/USD", "DOT/USD",
            "SOL/USD", "DOGE/USD", "AVAX/USD", "MATIC/USD", "LINK/USD"
        ]
        self.market_combo["values"] = self.markets
        
        if self.markets:
            self.selected_market.set(self.markets[0])
            self._on_market_selected(None)
        
        # Populate portfolio with example data
        self._populate_example_portfolio()
        
        # Populate orders with example data
        self._populate_example_orders()
    
    def _populate_example_portfolio(self):
        """Populate portfolio with example data."""
        # Clear existing data
        for item in self.portfolio_tree.get_children():
            self.portfolio_tree.delete(item)
        
        # Add example data
        example_portfolio = [
            ("BTC", "0.25", "10,250.00"),
            ("ETH", "2.5", "7,500.00"),
            ("USD", "5,000.00", "5,000.00"),
            ("XRP", "5000", "2,750.00"),
            ("ADA", "3000", "1,500.00")
        ]
        
        for asset, balance, value in example_portfolio:
            self.portfolio_tree.insert("", tk.END, values=(asset, balance, value))
    
    def _populate_example_orders(self):
        """Populate orders with example data."""
        # Clear existing data
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)
        
        # Add example data
        example_orders = [
            ("12345", "BTC/USD", "limit", "buy", "0.1", "39,500", "open"),
            ("12346", "ETH/USD", "limit", "sell", "1.0", "3,100", "open"),
            ("12347", "XRP/USD", "market", "buy", "1000", "Market", "filled")
        ]
        
        for order_id, market, order_type, side, amount, price, status in example_orders:
            self.orders_tree.insert("", tk.END, values=(order_id, market, order_type, side, amount, price, status))
    
    def _refresh_data(self):
        """Refresh market data, portfolio, and orders."""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to the trading service first.")
            return
        
        self.update_status_bar("Refreshing data...")
        
        # In a real implementation, this would fetch latest data
        # For now, just simulate a refresh with the same example data
        self._populate_example_portfolio()
        self._populate_example_orders()
        
        self.update_status_bar("Data refreshed at " + datetime.now().strftime("%H:%M:%S"))
    
    def _place_order(self):
        """Place a trading order."""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to the trading service first.")
            return
        
        market = self.selected_market.get()
        if not market:
            messagebox.showwarning("Invalid Market", "Please select a market first.")
            return
        
        order_type = self.order_type.get()
        side = self.order_side.get()
        
        try:
            amount = float(self.amount.get())
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            messagebox.showwarning("Invalid Amount", "Please enter a valid positive amount.")
            return
        
        # For limit orders, validate price
        price = None
        if order_type == "limit":
            try:
                price = float(self.price.get())
                if price <= 0:
                    raise ValueError("Price must be positive")
            except ValueError:
                messagebox.showwarning("Invalid Price", "Please enter a valid positive price.")
                return
        
        # Construct order details
        order_details = {
            "market": market,
            "type": order_type,
            "side": side,
            "amount": amount
        }
        
        if price is not None:
            order_details["price"] = price
        
        # Submit order (in a real implementation, this would call the trading API)
        # For now, just log the order and show a success message
        logger.info(f"Placing order: {order_details}")
        
        # Simulate successful order placement
        order_id = f"{12348 + len(self.orders_tree.get_children())}"
        
        # Add to orders list
        price_display = str(price) if price is not None else "Market"
        self.orders_tree.insert(
            "", 0, values=(order_id, market, order_type, side, amount, price_display, "open")
        )
        
        # Clear form
        self.amount.set("")
        self.price.set("")
        
        # Update status
        self.update_status_bar(f"Order placed: {side} {amount} {market.split('/')[0]} at {price_display}")
        messagebox.showinfo("Order Placed", f"Successfully placed {side} order for {amount} {market.split('/')[0]}.")
    
    def update_status_bar(self, message):
        """Update the status bar with a message."""
        self.status_bar.config(text=message)
    
    def run(self):
        """Run the trading tools GUI."""
        self.master.mainloop()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and run GUI
    app = TradingToolsGUI()
    app.run()
