#!/usr/bin/env python3
"""
Kingdom AI - API Keys Frame

This module implements the comprehensive API Keys management interface for Kingdom AI.
It handles display, addition, testing, monitoring, and real-time updates of 100+ API keys
for various services across the entire Kingdom AI ecosystem.

Features:
- Real-time connection status monitoring
- Categorized API key management
- Secure key storage and display
- Automated validation and testing
- Search and filtering capabilities
- Bulk operations support
- Advanced visualization of API usage and health
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import asyncio
import json
import os
import re
import time
import traceback
import threading
import webbrowser
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Set, Union
from functools import partial
from pathlib import Path
import matplotlib
# Use QtAgg backend for PyQt6 compatibility (set before any Qt imports)
try:
    matplotlib.use("QtAgg")  # PyQt6 compatible backend
except Exception:
    try:
        matplotlib.use("QtAgg")  # Use QtAgg for PyQt6
    except Exception:
        pass  # Use default backend if both fail
from matplotlib.figure import Figure
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from gui.frames.base_frame import BaseFrame
from utils.api_key_connector import get_api_key_connector

logger = logging.getLogger("KingdomAI.APIKeysFrame")

class APIKeysFrame(BaseFrame):
    """Advanced frame for comprehensive API key management in the Kingdom AI system.
    
    This frame provides a complete interface for managing, monitoring, and updating
    all API keys used throughout the Kingdom AI ecosystem. It features real-time
    status updates, categorized views, and advanced visualization capabilities.
    """
    
    # API key categories for organization
    CATEGORIES = {
        # Cryptocurrency exchanges - expanded with latest platforms
        "crypto_exchanges": [
            "binance", "kucoin", "bybit", "coinbase", "kraken", "huobi", "okx", "gemini", "bitfinex", 
            "bitstamp", "deribit", "bitget", "mexc", "gate_io", "crypto_com", "phemex", "bitmex", "bittrex", 
            "ftx_international", "lbank", "kucoin_futures", "bybit_futures", "binance_futures", "dydx", "woo_x",
            "bitmart", "ascendex", "whitebit", "poloniex", "probit", "hotbit", "coinex", "bitflyer"
        ],
        
        # Traditional stock exchanges and brokerages
        "stock_exchanges": [
            "alpaca", "td_ameritrade", "interactive_brokers", "robinhood", "public_api", "webull", "etrade", 
            "fidelity", "schwab", "thinkorswim", "tradier", "tradingview", "moomoo", "tiger_brokers", "degiro",
            "trading212", "saxo_bank", "ig_group", "plus500", "nasdaq_data_link", "nyse_data", "cboe"
        ],
        
        # Forex and CFD platforms
        "forex_trading": [
            "oanda", "forex_com", "fxcm", "ig_markets", "dukascopy", "pepperstone", "exness", "xm", 
            "hotforex", "fxtm", "forex_factory", "myfxbook", "tradingview_forex", "fxstreet", "fcsapi"
        ],
        
        # Professional market data providers
        "market_data": [
            "bloomberg", "refinitiv", "factset", "morningstar", "s_and_p", "moodys", "iex_cloud", "quandl", 
            "finnhub", "fmp_cloud", "eodhd", "tiingo", "polygon_io", "marketstack", "alpha_vantage", "intrinio", 
            "yfinance", "finmap_io", "finage", "benzinga", "newsapi", "fred", "twelve_data", "tradier_market", 
            "trading_economics"
        ],
        
        # Fixed income and bond markets
        "fixed_income": [
            "finra_trace", "msrb_emma", "treasury_direct", "bloomberg_fixed", "refinitiv_bonds", "factset_fixed", 
            "bondedge", "ice_data", "ftse_russell", "markit", "cbonds", "bloomberg_barclays", "moodys_bond", 
            "tradeweb", "interactive_brokers_bonds", "schwab_bonds", "fidelity_bonds", "bond_supermart"
        ],
        
        # Commodities and futures markets
        "commodities": [
            "cme_group", "ice_futures", "eurex", "lme", "nymex", "comex", "cbot", "tocom", "sgx", 
            "eex", "commodities_api", "metals_api", "commodities_data", "barchart", "mcx", "usda"
        ],
        
        # Derivatives and options data
        "derivatives": [
            "cboe_options", "nyse_options", "nasdaq_options", "opra", "cme_options", "ice_options", 
            "eurex_options", "optiondata", "orats", "livevol", "volatility_analytics", "options_price_reporting_authority"
        ],
        
        # Alternative investments
        "alternative_investments": [
            "preqin", "pitchbook", "crunchbase", "cb_insights", "venture_source", "real_estate_data", 
            "reit_data", "hedge_fund_research", "morningstar_alternatives", "eurekahedge", "albourne", "private_equity"
        ],
        
        # Blockchain and crypto data providers
        "blockchain_data": [
            "etherscan", "blockchain", "nansen", "blockchair", "glassnode", "santiment", "cryptoquant", "bitquery", 
            "amberdata", "coinglass", "defilama", "dune_analytics", "chainlink", "covalent", "moralis", "alchemy", 
            "infura", "ankr", "quicknode", "chainstack", "coinmarketcap", "coingecko", "cryptocompare", "nomics", 
            "messari", "lunarcrush", "kaiko", "coinapi", "coinlayer", "coinpaprika"
        ],
        
        # AI and machine learning services
        "ai_services": [
            "openai", "claude", "llama", "huggingface", "cohere", "stability", "codegpt", "meshy", "grok_xai", 
            "pinecone", "riva", "anthropic", "mistral", "gemini", "vertex_ai", "openrouter", "together_ai", "replicate", 
            "deepinfra", "groq", "fireworks", "forefront", "lepton"
        ],
        
        # ESG and sustainable finance data
        "esg_data": [
            "msci_esg", "sustainalytics", "refinitiv_esg", "bloomberg_esg", "s_and_p_esg", "iss_esg", 
            "morningstar_sustainalytics", "cdp", "trucost", "factset_esg", "arabesque"
        ],
        
        # Financial services APIs
        "financial_services": [
            "bank_data", "tax_data", "bin_checker", "vatlayer", "currency_data", "odds", "rundown",
            "plaid", "stripe", "square", "paypal", "mastercard", "visa", "authorize_net", "adyen", 
            "worldpay", "checkout", "intuit", "xero", "quickbooks", "klarna", "affirm", "afterpay"
        ],
        
        # Cloud services
        "cloud_services": [
            "heroku", "google", "aws", "azure", "gcp", "alibaba_cloud", "oracle_cloud", "ibm_cloud", 
            "digitalocean", "cloudflare", "vercel", "netlify"
        ],
        
        # Social media and sentiment analysis
        "social_media": [
            "twitter", "reddit", "discord", "slack", "stocktwits", "tradingview_social", "facebook", 
            "linkedin", "instagram", "tiktok", "sentiment_analysis", "social_market_analytics"
        ],
        
        # Other specialized APIs
        "other": [
            "sourcery", "figma", "vault", "deepl", "investing_com", "market_watch", "financial_times", 
            "wall_street_journal", "bloomberg_terminal", "factset_workstation", "capitalmind"
        ]
    }
    
    # Status indicators with colors
    STATUS_COLORS = {
        "connected": "#4CAF50",  # Green
        "disconnected": "#F44336",  # Red
        "unknown": "#9E9E9E",  # Gray
        "warning": "#FFC107",  # Amber
        "expired": "#FF9800",  # Orange
        "invalid": "#F44336",  # Red
        "pending": "#2196F3"   # Blue
    }
    
    def __init__(self, parent, event_bus=None, api_key_connector=None):
        """Initialize the API Keys frame with advanced features.
        
        Args:
            parent: The parent widget
            event_bus: The application event bus
            api_key_connector: API key connector for accessing keys across the system
        """
        super().__init__(parent, event_bus=event_bus)
        self.pack(fill=tk.BOTH, expand=True)
        
        # Use the provided API key connector or get the global instance
        self.api_key_connector = api_key_connector or get_api_key_connector(event_bus)
        
        # Initialize data structures
        self.api_keys = {}  # All API keys by service
        self.api_key_status = {}  # Status for each API key
        self.api_key_usage = {}  # Usage statistics
        self.selected_service = None  # Currently selected service
        self.selected_category = None  # Currently selected category
        self.search_term = ""  # Current search filter
        self.last_refresh_time = None  # When keys were last refreshed
        self.refresh_in_progress = False  # Flag to prevent multiple refreshes
        self.categorized_keys = {cat: [] for cat in self.CATEGORIES.keys()}  # Keys organized by category
        
        # Data visualization
        self.usage_data = {}  # API usage data for charts
        self.status_history = {}  # Historical status data
        
        # Auto refresh settings
        self.auto_refresh_enabled = False  # Whether auto-refresh is enabled
        self.auto_refresh_interval = 60  # Default refresh interval in seconds
        self.auto_refresh_timer = None  # Timer for auto refresh scheduling
        
        # Initialize test progress indicator
        self.test_progress = None
        
        # Register event handlers
        if self.event_bus:
            self.event_bus.subscribe_sync("api_key_updated", self._on_update_key)
        
        # UI components
        self.notebook = None  # Main notebook for tabs
        self.tree_views = {}  # TreeViews for each category
        self.status_indicators = {}  # Status indicators for each service
        self.search_var = tk.StringVar()  # Search box variable
        self.status_label = None  # Status message label
        self.progress_bar = None  # Progress indicator
        self.category_filters = {}  # Category filter buttons
        self.visualization_canvas = None  # Canvas for charts
        self.key_details_frame = None  # Frame for selected key details
        
        # Create the advanced UI
        self._create_widgets()
        
        # Set up auto-refresh
        self.auto_refresh_enabled = tk.BooleanVar(value=True)
        self.auto_refresh_interval = 60  # seconds
        self.auto_refresh_timer = None
        
        # Subscribe to events AFTER init completes
        from PyQt6.QtCore import QTimer
        
        def subscribe_delayed():
            try:
                asyncio.create_task(self._subscribe_to_events())
            except Exception as e:
                logger.error(f"Error subscribing to events: {e}")
        
        QTimer.singleShot(4600, subscribe_delayed)  # 4.6 seconds after init
        
        # Initial load of API keys
        self._load_api_keys()
        
        # Start auto-refresh timer
        self._schedule_auto_refresh()
        
    def _create_widgets(self):
        """Create an advanced UI for comprehensive API key management."""
        # Main container with modern styling
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top toolbar with actions and search
        self._create_toolbar(main_container)
        
        # Main content - notebook with tabs for different views
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create the different views
        self._create_category_view()
        self._create_status_view()
        self._create_visualization_view()
        self._create_configuration_view()
        
        # Bottom status bar with refresh indicator and progress
        self._create_status_bar(main_container)
        
        # Details panel for selected key
        self._create_details_panel(main_container)
    
    def _create_toolbar(self, parent):
        """Create the top toolbar with actions and search functionality."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        # Left side - action buttons
        actions_frame = ttk.Frame(toolbar)
        actions_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Action buttons with icons (we'll use text for now)
        ttk.Button(actions_frame, text="+ Add Key", command=self._on_add_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions_frame, text="✓ Test Selected", command=self._on_test_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions_frame, text="⟳ Refresh All", command=self._refresh_all_keys).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions_frame, text="⚙ Bulk Actions", command=self._show_bulk_actions).pack(side=tk.LEFT, padx=2)
        
        # Right side - search and filter
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Search functionality
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind("<KeyRelease>", self._on_search)
        
        # Auto-refresh toggle
        auto_refresh_check = ttk.Checkbutton(search_frame, text="Auto Refresh", 
                                           variable=self.auto_refresh_enabled,
                                           command=self._toggle_auto_refresh)
        auto_refresh_check.pack(side=tk.LEFT, padx=10)
    
    def _create_category_view(self):
        """Create the main categorized view of API keys."""
        category_frame = ttk.Frame(self.notebook)
        self.notebook.add(category_frame, text="Categories")
        
        # Left side - category filters
        filter_frame = ttk.Frame(category_frame)
        filter_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Categories", font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=5)
        
        # Create a button for each category
        for category in self.CATEGORIES:
            display_name = category.replace("_", " ").title()
            btn = ttk.Button(filter_frame, text=display_name, width=15,
                            command=lambda cat=category: self._filter_by_category(cat))
            btn.pack(anchor=tk.W, pady=2)
            self.category_filters[category] = btn
        
        # All categories button
        ttk.Button(filter_frame, text="All Services", width=15,
                  command=lambda: self._filter_by_category(None)).pack(anchor=tk.W, pady=2)
        
        # Right side - TreeView with API keys
        keys_frame = ttk.Frame(category_frame)
        keys_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview with scrollbar
        columns = ("Service", "Status", "Key", "Type", "Last Tested", "Expires")
        self.api_keys_tree = ttk.Treeview(keys_frame, columns=columns, show="headings")
        
        # Configure columns
        self.api_keys_tree.heading("Service", text="Service")
        self.api_keys_tree.heading("Status", text="Status")
        self.api_keys_tree.heading("Key", text="API Key")
        self.api_keys_tree.heading("Type", text="Type")
        self.api_keys_tree.heading("Last Tested", text="Last Updated")
        self.api_keys_tree.heading("Expires", text="Expires")
        
        self.api_keys_tree.column("Service", width=120)
        self.api_keys_tree.column("Status", width=80)
        self.api_keys_tree.column("Key", width=200)
        self.api_keys_tree.column("Type", width=80)
        self.api_keys_tree.column("Last Tested", width=100)
        self.api_keys_tree.column("Expires", width=100)
        
        # Scrollbars
        y_scrollbar = ttk.Scrollbar(keys_frame, orient=tk.VERTICAL, command=self.api_keys_tree.yview)
        self.api_keys_tree.configure(yscrollcommand=y_scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.api_keys_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind events
        self.api_keys_tree.bind("<<TreeviewSelect>>", self._on_key_selected)
        self.api_keys_tree.bind("<Double-1>", self._on_key_double_click)
        
        # Store this view
        self.tree_views["category"] = self.api_keys_tree
        
    def _create_status_view(self):
        """Create the status overview tab showing connection statuses."""
        status_frame = ttk.Frame(self.notebook)
        self.notebook.add(status_frame, text="Status Overview")
        
        # Top status summary
        summary_frame = ttk.LabelFrame(status_frame, text="Connection Status Summary")
        summary_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Status counters
        status_counts = ttk.Frame(summary_frame)
        status_counts.pack(fill=tk.X, padx=10, pady=10)
        
        # Status indicators with counts
        for status, color in self.STATUS_COLORS.items():
            status_indicator = ttk.Frame(status_counts, width=15, height=15)
            status_indicator.pack(side=tk.LEFT, padx=5)
            status_indicator.configure(style=f"{status}.TFrame")
            
            count_var = tk.StringVar(value="0")
            self.status_indicators[status] = count_var
            
            ttk.Label(status_counts, text=f"{status.title()}: ").pack(side=tk.LEFT)
            ttk.Label(status_counts, textvariable=count_var).pack(side=tk.LEFT, padx=(0, 15))
        
        # Status grouping treeview
        status_list_frame = ttk.Frame(status_frame)
        status_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create status treeview
        columns = ("Service", "Category", "Status", "Last Checked", "Response Time", "Issues")
        status_tree = ttk.Treeview(status_list_frame, columns=columns, show="headings")
        
        # Configure columns
        for col in columns:
            status_tree.heading(col, text=col)
            width = 100 if col != "Issues" else 200
            status_tree.column(col, width=width)
        
        # Scrollbar
        y_scrollbar = ttk.Scrollbar(status_list_frame, orient=tk.VERTICAL, command=status_tree.yview)
        status_tree.configure(yscrollcommand=y_scrollbar.set)
        
        # Pack the treeview and scrollbar
        status_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Store this view
        self.tree_views["status"] = status_tree
        
    def _create_visualization_view(self):
        """Create the visualization tab with charts and graphs."""
        viz_frame = ttk.Frame(self.notebook)
        self.notebook.add(viz_frame, text="Usage Analytics")
        
        # Controls for visualization selection
        control_frame = ttk.Frame(viz_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="View:").pack(side=tk.LEFT, padx=5)
        viz_options = ["API Usage Over Time", "Status Distribution", "Response Times", "Key Expiration"]
        viz_combo = ttk.Combobox(control_frame, values=viz_options, state="readonly")
        viz_combo.pack(side=tk.LEFT, padx=5)
        viz_combo.current(0)
        viz_combo.bind("<<ComboboxSelected>>", self._update_visualization)
        
        # Time range selection
        ttk.Label(control_frame, text="Time Range:").pack(side=tk.LEFT, padx=(15, 5))
        time_options = ["Last 24 Hours", "Last Week", "Last Month", "Last Year"]
        time_combo = ttk.Combobox(control_frame, values=time_options, state="readonly")
        time_combo.pack(side=tk.LEFT, padx=5)
        time_combo.current(0)
        time_combo.bind("<<ComboboxSelected>>", self._update_visualization)
        
        # Canvas for matplotlib charts
        chart_frame = ttk.Frame(viz_frame)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create figure and canvas for matplotlib
        figure = Figure(figsize=(6, 4), dpi=100)
        self.visualization_canvas = FigureCanvasTkAgg(figure, chart_frame)
        self.visualization_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial plot
        self.figure = figure
        self._plot_initial_chart()
        
    def _create_configuration_view(self):
        """Create the configuration tab for adding and editing API keys."""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="Configuration")
        
        # Left side - configuration form
        form_frame = ttk.LabelFrame(config_frame, text="API Key Details")
        form_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Service selection
        service_frame = ttk.Frame(form_frame)
        service_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(service_frame, text="Service:").pack(side=tk.LEFT, padx=5, pady=5)
        
        # Get all services from all categories
        all_services = []
        for category_services in self.CATEGORIES.values():
            all_services.extend(category_services)
        all_services.sort()
        
        self.service_combo = ttk.Combobox(service_frame, values=all_services)
        self.service_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # Custom service option
        ttk.Button(service_frame, text="Custom", command=self._add_custom_service).pack(side=tk.LEFT, padx=5)
        
        # API Key input
        key_frame = ttk.Frame(form_frame)
        key_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(key_frame, text="API Key:").pack(side=tk.LEFT, padx=5, pady=5)
        self.api_key_entry = ttk.Entry(key_frame, width=50)
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # API Secret input
        secret_frame = ttk.Frame(form_frame)
        secret_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(secret_frame, text="API Secret:").pack(side=tk.LEFT, padx=5, pady=5)
        self.api_secret_entry = ttk.Entry(secret_frame, width=50, show="*")
        self.api_secret_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # Show/Hide toggle for secret
        self.show_secret_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(secret_frame, text="Show", variable=self.show_secret_var, 
                       command=self._toggle_secret_visibility).pack(side=tk.LEFT, padx=5)
        
        # Additional fields frame
        additional_frame = ttk.LabelFrame(form_frame, text="Additional Settings")
        additional_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Description
        desc_frame = ttk.Frame(additional_frame)
        desc_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(desc_frame, text="Description:").pack(side=tk.LEFT, padx=5, pady=5)
        self.description_entry = ttk.Entry(desc_frame, width=50)
        self.description_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # Expiration date
        expire_frame = ttk.Frame(additional_frame)
        expire_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(expire_frame, text="Expires:").pack(side=tk.LEFT, padx=5, pady=5)
        self.expiry_entry = ttk.Entry(expire_frame, width=20)
        self.expiry_entry.pack(side=tk.LEFT, padx=5, pady=5)
        self.expiry_entry.insert(0, "YYYY-MM-DD")
        
        # Auto-test checkbox
        self.auto_test_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(additional_frame, text="Test key automatically after adding", 
                       variable=self.auto_test_var).pack(anchor=tk.W, padx=10, pady=5)
        
        # Action buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Add Key", command=self._on_add_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Update Key", command=self._on_update_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Test Connection", command=self._on_test_key).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Key", command=self._on_delete_key).pack(side=tk.LEFT, padx=5)
        
        # Right side - Documentation
        doc_frame = ttk.LabelFrame(config_frame, text="Documentation & Help")
        doc_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5, pady=5, expand=False, ipadx=5, ipady=5)
        
        # Documentation text
        doc_text = tk.Text(doc_frame, wrap=tk.WORD, width=30, height=20)
        doc_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        doc_text.insert(tk.END, "Select a service to see documentation about required API key format and setup instructions.")
        doc_text.config(state=tk.DISABLED)
        
        # Store the doc text widget for later updates
        self.doc_text = doc_text
        
        # Links for API documentation
        link_frame = ttk.Frame(doc_frame)
        link_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(link_frame, text="Open API Documentation",
              command=self._open_api_documentation).pack(anchor=tk.W, pady=2)
        ttk.Button(link_frame, text="View API Key Security Guidelines",
              command=self._open_security_guidelines).pack(anchor=tk.W, pady=2)
    
    def _on_update_key(self, event_data):
        """Handle API key update events.
        
        Args:
            event_data: Dictionary containing information about the updated key
                       including 'service', 'key_id', and 'status'
        """
        if not event_data or not isinstance(event_data, dict):
            return
            
        service = event_data.get('service')
        key_id = event_data.get('key_id')
        status = event_data.get('status', 'unknown')
        
        if service and key_id:
            # Update internal status tracking
            if service not in self.api_key_status:
                self.api_key_status[service] = {}
            
            self.api_key_status[service][key_id] = status
            
            # Update the UI if this service is currently displayed
            if hasattr(self, 'current_category') and self.current_category == service:
                self._update_api_keys_display()
            
            # Show a notification toast
            message = f"API key for {service} has been updated. Status: {status}"
            self._show_toast(message, bg_color=self.STATUS_COLORS.get(status, "#333333"))
              
    def _create_status_bar(self, parent=None):
        """Create the status bar with refresh indicator.
        
        Args:
            parent: The parent widget. If None, uses self as parent.
        """
        # Use self as parent if not provided
        if parent is None:
            parent = self
            
        status_bar = ttk.Frame(parent)
        status_bar.pack(fill=tk.X, padx=5, pady=5)
        
        # Status message on left
        self.status_label = ttk.Label(status_bar, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Progress bar for operations
        self.progress_bar = ttk.Progressbar(status_bar, mode="indeterminate", length=100)
        self.progress_bar.pack(side=tk.LEFT, padx=5)
        
        # Last refresh time on right
        self.refresh_label = ttk.Label(status_bar, text="")
        self.refresh_label.pack(side=tk.RIGHT, padx=5)
        
    def _create_details_panel(self, parent):
        """Create the details panel for the selected API key."""
        self.key_details_frame = ttk.LabelFrame(parent, text="Selected API Key Details")
        self.key_details_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create a frame for details with two columns
        details_grid = ttk.Frame(self.key_details_frame)
        details_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Left column - Basic details
        left_col = ttk.Frame(details_grid)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Service name
        service_frame = ttk.Frame(left_col)
        service_frame.pack(fill=tk.X, pady=2)
        ttk.Label(service_frame, text="Service:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.detail_service = ttk.Label(service_frame, text="")
        self.detail_service.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # API Key (masked)
        key_frame = ttk.Frame(left_col)
        key_frame.pack(fill=tk.X, pady=2)
        ttk.Label(key_frame, text="API Key:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.detail_key = ttk.Label(key_frame, text="")
        self.detail_key.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Description
        desc_frame = ttk.Frame(left_col)
        desc_frame.pack(fill=tk.X, pady=2)
        ttk.Label(desc_frame, text="Description:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.detail_desc = ttk.Label(desc_frame, text="")
        self.detail_desc.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Right column - Status and actions
        right_col = ttk.Frame(details_grid)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Status indicator
        status_frame = ttk.Frame(right_col)
        status_frame.pack(fill=tk.X, pady=2)
        ttk.Label(status_frame, text="Status:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.detail_status = ttk.Label(status_frame, text="")
        self.detail_status.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Last check time
        check_frame = ttk.Frame(right_col)
        check_frame.pack(fill=tk.X, pady=2)
        ttk.Label(check_frame, text="Last Check:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.detail_check = ttk.Label(check_frame, text="")
        self.detail_check.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Quick action buttons
        action_frame = ttk.Frame(right_col)
        action_frame.pack(fill=tk.X, pady=5)
        ttk.Button(action_frame, text="Test", command=self._test_selected_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Edit", command=self._edit_selected_key).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Copy Key", command=self._copy_key_to_clipboard).pack(side=tk.LEFT, padx=2)
        
        # Initially hide the details panel until a key is selected
        self.key_details_frame.pack_forget()
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT)
        
    def _load_api_keys(self):
        """Load all API keys from the API key connector and configuration files."""
        self.status_label.config(text="Loading API keys...")
        self.progress_bar.start()
        
        # Load keys asynchronously
        asyncio.create_task(self._load_api_keys_async())
    
    async def _load_api_keys_async(self):
        """Asynchronously load all API keys from various sources."""
        try:
            # First, get keys from the API key connector
            if self.api_key_connector:
                services = await self.api_key_connector.list_available_services()
                
                for service in services:
                    key_data = await self.api_key_connector.get_api_key(service)
                    if key_data:
                        self.api_keys[service] = key_data
            
            # Then load keys directly from configuration files for completeness
            await self._load_keys_from_config_files()
            
            # Categorize the keys by type
            self._categorize_keys()
            
            # Update the UI with the loaded keys
            self._update_api_keys_display()
            
            # Check connection status for all keys
            await self._check_connection_status()
            
            # Update last refresh time
            self.last_refresh_time = datetime.now()
            self.refresh_label.config(text=f"Last refreshed: {self.last_refresh_time.strftime('%H:%M:%S')}")
            
            # Update status
            self.status_label.config(text=f"Loaded {len(self.api_keys)} API keys")
            self.progress_bar.stop()
            
        except Exception as e:
            logger.error(f"Error loading API keys: {e}")
            self.status_label.config(text=f"Error loading API keys: {str(e)}")
            self.progress_bar.stop()
            traceback.print_exc()
    
    async def _load_keys_from_config_files(self):
        """Load API keys from configuration files."""
        try:
            # Check config/api_keys.json
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                       'config', 'api_keys.json')
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    try:
                        keys_data = json.load(f)
                        for service, key_data in keys_data.items():
                            # Only add if not already loaded from connector
                            if service not in self.api_keys:
                                self.api_keys[service] = key_data
                            # Otherwise merge any additional fields
                            elif isinstance(key_data, dict):
                                for k, v in key_data.items():
                                    if k not in self.api_keys[service]:
                                        self.api_keys[service][k] = v
                        
                        logger.info(f"Loaded API keys from {config_path}")
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in {config_path}")
            
            # Also check config/api_keys.env for environment-style keys
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                    'config', 'api_keys.env')
            
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                            
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            
                            # Extract service name from key pattern
                            service = None
                            key_type = None
                            
                            if '_API_KEY' in key:
                                service = key.split('_API_KEY')[0].lower()
                                key_type = 'api_key'
                            elif '_SECRET_KEY' in key or '_API_SECRET' in key:
                                service = key.split('_SECRET')[0].lower()
                                key_type = 'api_secret'
                            
                            if service and key_type and value:
                                if service not in self.api_keys:
                                    self.api_keys[service] = {}
                                self.api_keys[service][key_type] = value
                    
                    logger.info(f"Loaded API keys from {env_path}")
                    
        except Exception as e:
            logger.error(f"Error loading API keys from configuration files: {e}")
            traceback.print_exc()
    
    def _categorize_keys(self):
        """Categorize loaded API keys based on service type."""
        # Reset categorized keys
        self.categorized_keys = {cat: [] for cat in self.CATEGORIES.keys()}
        self.categorized_keys["other"] = []  # Default for uncategorized keys
        
        # Categorize each service
        for service in self.api_keys.keys():
            categorized = False
            for category, services in self.CATEGORIES.items():
                if service in services:
                    self.categorized_keys[category].append(service)
                    categorized = True
                    break
            
            # If not found in any category, add to "other"
            if not categorized:
                self.categorized_keys["other"].append(service)
    
    def _subscribe_to_events(self):
        """Subscribe to API key related events."""
        if not self.event_bus:
            logger.warning("No event bus available to subscribe to")
            return
            
        try:
            # Using subscribe_sync instead of async subscribe to avoid coroutine warnings
            self.event_bus.subscribe_sync("api.keys.status", self._handle_api_keys_status)
            self.event_bus.subscribe_sync("api.keys.list", self._handle_api_keys_list)
            self.event_bus.subscribe_sync("api.connection.test.result", self._handle_api_connection_test_result)
            self.event_bus.subscribe_sync("api.key.update", self._handle_api_key_update)
            self.event_bus.subscribe_sync("api.key.delete", self._handle_api_key_delete)
            self.event_bus.subscribe_sync("api.key.status.*", self._handle_api_key_status_update)
            
            logger.info("Subscribed to API key events")
            
            # Request initial list of API keys
            self.event_bus.publish_sync("api.keys.request_list", {
                "source": "api_keys_frame",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error subscribing to API key events: {e}")
            logger.error(traceback.format_exc())
            
    def _update_api_keys_display(self):
        """Update the UI display with current API keys."""
        # Clear existing items in the main treeview
        for item in self.api_keys_tree.get_children():
            self.api_keys_tree.delete(item)
        
        # Clear status treeview if it exists
        if "status" in self.tree_views:
            status_tree = self.tree_views["status"]
            for item in status_tree.get_children():
                status_tree.delete(item)
        
        # Filter services based on current category and search term
        filtered_services = self._get_filtered_services()
        
        # Add filtered services to the treeview
        for service in filtered_services:
            key_data = self.api_keys.get(service, {})
            
            # Determine service category
            category = "other"
            for cat, services in self.CATEGORIES.items():
                if service in services:
                    category = cat
                    break
            
            # Get status data
            status_data = self.api_key_status.get(service, {})
            status = status_data.get("status", "unknown")
            last_checked = status_data.get("last_checked", "Never")
            if isinstance(last_checked, (int, float)):
                last_checked = datetime.fromtimestamp(last_checked).strftime("%Y-%m-%d %H:%M")
            
            # Mask API key for display
            masked_key = self._mask_sensitive_data(key_data.get("api_key", ""))
            
            # Get expiration if available
            expires = key_data.get("expires", "")
            if isinstance(expires, (int, float)):
                expires = datetime.fromtimestamp(expires).strftime("%Y-%m-%d")
            
            # Determine key type
            key_type = key_data.get("type", "standard")
            
            # Add to main treeview
            item_id = self.api_keys_tree.insert("", tk.END, text=service, values=(
                service, status, masked_key, key_type, last_checked, expires
            ))
            
            # Set tag for status color
            if status in self.STATUS_COLORS:
                self.api_keys_tree.tag_configure(status, foreground=self.STATUS_COLORS[status])
                self.api_keys_tree.item(item_id, tags=(status,))
            
            # Add to status treeview if it exists
            if "status" in self.tree_views:
                status_tree = self.tree_views["status"]
                response_time = status_data.get("response_time", "--")
                issues = status_data.get("issues", "")
                
                status_tree.insert("", tk.END, text=service, values=(
                    service, category, status, last_checked, response_time, issues
                ))
        
        # Update status counts
        self._update_status_counts()
    
    def _get_filtered_services(self):
        """Get services filtered by current category and search term."""
        filtered_services = []
        
        # Get services based on selected category
        if self.selected_category:
            services = self.categorized_keys.get(self.selected_category, [])
        else:
            # All services if no category selected
            services = list(self.api_keys.keys())
        
        # Apply search filter if needed
        if self.search_term:
            term = self.search_term.lower()
            filtered_services = [s for s in services if term in s.lower() or 
                               term in str(self.api_keys.get(s, {}).get("description", "")).lower()]
        else:
            filtered_services = services
        
        # Sort alphabetically
        filtered_services.sort()
        
        return filtered_services
    
    def _update_status_counts(self):
        """Update the status indicator counts."""
        # Count services by status
        status_counts = {status: 0 for status in self.STATUS_COLORS.keys()}
        
        # Count each status
        for service, status_data in self.api_key_status.items():
            status = status_data.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1
        
        # Update the status indicator labels
        for status, count in status_counts.items():
            if status in self.status_indicators:
                self.status_indicators[status].set(str(count))
    
    async def _check_connection_status(self):
        """Check connection status for all API keys."""
        if not self.event_bus:
            logger.warning("No event bus available to check connection status")
            return
        
        # Update status for each service
        for service in list(self.api_keys.keys()):
            # Skip if we've already checked recently
            status_data = self.api_key_status.get(service, {})
            last_checked = status_data.get("last_checked", 0)
            
            # Only check if it's been more than 10 minutes since last check
            if time.time() - last_checked < 600:
                continue
                
            # Request status check from API Key Manager
            try:
                await self.event_bus.publish("api.keys.test", {
                    "service": service,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Update the last checked time
                if service not in self.api_key_status:
                    self.api_key_status[service] = {}
                    
                self.api_key_status[service]["last_checked"] = time.time()
                self.api_key_status[service]["status"] = "pending"
                
                # Small delay to avoid flooding the event bus
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error requesting status check for {service}: {e}")
    
    def _filter_by_category(self, category):
        """Filter the displayed API keys by category."""
        self.selected_category = category
        
        # Update category button styles
        for cat, btn in self.category_filters.items():
            # Reset all button styles
            btn.configure(style="TButton")
        
        # Highlight selected category button
        if category and category in self.category_filters:
            self.category_filters[category].configure(style="Accent.TButton")
        
        # Update the display
        self._update_api_keys_display()
    
    def _on_search(self, event):
        """Handle search box input."""
        self.search_term = self.search_var.get()
        self._update_api_keys_display()
    
    def _mask_sensitive_data(self, value):
        """Mask sensitive data for display in the UI."""
        if not value:
            return ""
            
        value = str(value)
        
        # Show first 4 and last 4 characters, mask the rest
        if len(value) > 8:
            return value[:4] + "*" * (len(value) - 8) + value[-4:]
        elif len(value) > 4:
            return value[:2] + "*" * (len(value) - 4) + value[-2:]
        else:
            return "*" * len(value)
    
    def _schedule_auto_refresh(self):
        """Schedule the auto-refresh timer."""
        # Cancel any existing timer
        if self.auto_refresh_timer:
            self.after_cancel(self.auto_refresh_timer)
        
        # Schedule new timer if enabled
        if self.auto_refresh_enabled.get():
            self.auto_refresh_timer = self.after(
                self.auto_refresh_interval * 1000, 
                lambda: asyncio.create_task(self._auto_refresh())
            )
    
    async def _auto_refresh(self):
        """Automatically refresh API keys and status."""
        if not self.refresh_in_progress:
            self.refresh_in_progress = True
            
            try:
                # Refresh all keys
                await self._load_api_keys_async()
                
                # Schedule next refresh
                self._schedule_auto_refresh()
                
            except Exception as e:
                logger.error(f"Error during auto-refresh: {e}")
                traceback.print_exc()
            finally:
                self.refresh_in_progress = False
    
    def _toggle_auto_refresh(self):
        """Toggle automatic refresh on/off."""
        if self.auto_refresh_enabled.get():
            self._schedule_auto_refresh()
            self.status_label.config(text="Auto-refresh enabled")
        else:
            if self.auto_refresh_timer:
                self.after_cancel(self.auto_refresh_timer)
                self.auto_refresh_timer = None
            self.status_label.config(text="Auto-refresh disabled")
    
    def _refresh_all_keys(self):
        """Manually refresh all API keys."""
        if not self.refresh_in_progress:
            self.status_label.config(text="Refreshing API keys...")
            self.progress_bar.start()
            self._load_api_keys()
    
    def _show_bulk_actions(self):
        """Show bulk actions dialog."""
        # Create a toplevel window for bulk actions
        bulk_window = tk.Toplevel(self)
        bulk_window.title("Bulk API Key Actions")
        bulk_window.geometry("400x300")
        bulk_window.transient(self)
        bulk_window.grab_set()
        
        # Add bulk action options
        ttk.Label(bulk_window, text="Bulk Actions", font=("TkDefaultFont", 12, "bold")).pack(pady=10)
        
        ttk.Button(bulk_window, text="Test All Keys", 
                  command=lambda: asyncio.create_task(self._test_all_keys())).pack(fill=tk.X, padx=20, pady=5)
                  
        ttk.Button(bulk_window, text="Export All Keys", 
                  command=self._export_keys).pack(fill=tk.X, padx=20, pady=5)
                  
        ttk.Button(bulk_window, text="Import Keys", 
                  command=self._import_keys).pack(fill=tk.X, padx=20, pady=5)
                  
        ttk.Button(bulk_window, text="Remove Invalid Keys", 
                  command=self._remove_invalid_keys).pack(fill=tk.X, padx=20, pady=5)
                  
        ttk.Button(bulk_window, text="Close", 
                  command=bulk_window.destroy).pack(fill=tk.X, padx=20, pady=20)
    
    def _toggle_secret_visibility(self):
        """Toggle visibility of the API secret field."""
        if self.show_secret_var.get():
            self.api_secret_entry.config(show="")
        else:
            self.api_secret_entry.config(show="*")
    
    def _add_custom_service(self):
        """Add a custom service that's not in the predefined list."""
        custom_service = simpledialog.askstring("Custom Service", "Enter the name of the custom service:")
        if custom_service:
            custom_service = custom_service.lower().strip()
            
            # Add to the service dropdown
            services = list(self.service_combo["values"])
            if custom_service not in services:
                services.append(custom_service)
                services.sort()
                self.service_combo["values"] = services
            
            # Select the new service
            self.service_combo.set(custom_service)
    
    def _on_key_selected(self, event):
        """Handle selection of an API key in the treeview."""
        selected = self.api_keys_tree.selection()
        if not selected:
            # Hide details panel if nothing selected
            self.key_details_frame.pack_forget()
            return
        
        # Get the selected service
        item = selected[0]
        values = self.api_keys_tree.item(item, "values")
        service = values[0]
        
        # Update selected service
        self.selected_service = service
        
        # Update details panel
        self._update_key_details(service)
        
        # Show details panel
        self.key_details_frame.pack(fill=tk.X, padx=5, pady=5)
    
    def _update_key_details(self, service):
        """Update the key details panel with the selected service info."""
        if service not in self.api_keys:
            return
            
        key_data = self.api_keys[service]
        status_data = self.api_key_status.get(service, {})
        
        # Update service info
        self.detail_service.config(text=service)
        
        # Update key info (masked)
        masked_key = self._mask_sensitive_data(key_data.get("api_key", ""))
        self.detail_key.config(text=masked_key)
        
        # Update description
        description = key_data.get("description", "")
        self.detail_desc.config(text=description)
        
        # Update status
        status = status_data.get("status", "unknown")
        self.detail_status.config(text=status)
        if status in self.STATUS_COLORS:
            self.detail_status.config(foreground=self.STATUS_COLORS[status])
        
        # Update last check time
        last_checked = status_data.get("last_checked", "Never")
        if isinstance(last_checked, (int, float)):
            last_checked = datetime.fromtimestamp(last_checked).strftime("%Y-%m-%d %H:%M")
        self.detail_check.config(text=last_checked)
    
    def _on_key_double_click(self, event):
        """Handle double-click on a key to edit it."""
        self._edit_selected_key()
    
    def _test_selected_key(self):
        """Test the currently selected API key."""
        if not self.selected_service:
            messagebox.showinfo("No Selection", "Please select an API key to test.")
            return
            
        # Update status
        self.status_label.config(text=f"Testing {self.selected_service} API key...")
        self.progress_bar.start()
        
        # Start the test in the background
        asyncio.create_task(self._test_key(self.selected_service))
    
    async def _test_key(self, service):
        """Test the specified API key by publishing a test request."""
        if not self.event_bus:
            messagebox.showerror("Error", "Event bus not available for testing")
            self.progress_bar.stop()
            return
            
        try:
            # Update status to pending
            if service not in self.api_key_status:
                self.api_key_status[service] = {}
                
            self.api_key_status[service]["status"] = "pending"
            self.api_key_status[service]["last_checked"] = time.time()
            
            # Update the UI
            self._update_api_keys_display()
            if self.selected_service == service:
                self._update_key_details(service)
            
            # Request a test
            await self.event_bus.publish("api.keys.test", {
                "service": service,
                "timestamp": datetime.now().isoformat()
            })
            
            # Status will be updated when we receive the test result event
            
        except Exception as e:
            logger.error(f"Error testing API key for {service}: {e}")
            messagebox.showerror("Error", f"Failed to test API key: {str(e)}")
            
            # Update status to error
            self.api_key_status[service]["status"] = "error"
            self.api_key_status[service]["issues"] = str(e)
            
            # Update the UI
            self._update_api_keys_display()
            if self.selected_service == service:
                self._update_key_details(service)
        finally:
            self.progress_bar.stop()
            self.status_label.config(text="Ready")
    
    def _edit_selected_key(self):
        """Edit the currently selected API key."""
        if not self.selected_service:
            messagebox.showinfo("No Selection", "Please select an API key to edit.")
            return
            
        # Switch to the configuration tab
        self.notebook.select(3)  # Assuming Configuration is the 4th tab (index 3)
        
        # Fill in the form with the current key data
        service = self.selected_service
        key_data = self.api_keys.get(service, {})
        
        self.service_combo.set(service)
        self.api_key_entry.delete(0, tk.END)
        self.api_key_entry.insert(0, key_data.get("api_key", ""))
        
        self.api_secret_entry.delete(0, tk.END)
        self.api_secret_entry.insert(0, key_data.get("api_secret", ""))
        
        self.description_entry.delete(0, tk.END)
        self.description_entry.insert(0, key_data.get("description", ""))
        
        # Set expiration if available
        expires = key_data.get("expires", "")
        self.expiry_entry.delete(0, tk.END)
        if isinstance(expires, (int, float)):
            expires_str = datetime.fromtimestamp(expires).strftime("%Y-%m-%d")
            self.expiry_entry.insert(0, expires_str)
        else:
            self.expiry_entry.insert(0, "YYYY-MM-DD")
    
    def _copy_key_to_clipboard(self):
        """Copy the selected API key to the clipboard."""
        if not self.selected_service or self.selected_service not in self.api_keys:
            messagebox.showinfo("No Selection", "Please select a valid API key to copy.")
            return
            
        key_data = self.api_keys[self.selected_service]
        api_key = key_data.get("api_key", "")
        
        if not api_key:
            messagebox.showinfo("No Key", "The selected service does not have an API key.")
            return
            
        # Copy to clipboard
        self.clipboard_clear()
        self.clipboard_append(api_key)
        
        # Show confirmation
        self.status_label.config(text=f"Copied {self.selected_service} API key to clipboard")
        
    def _plot_initial_chart(self):
        """Create the initial visualization chart."""
        # Clear any existing plots
        self.figure.clear()
        
        # Create a placeholder chart
        ax = self.figure.add_subplot(111)
        ax.set_title("API Key Usage Analytics")
        ax.set_xlabel("Time")
        ax.set_ylabel("Usage Count")
        
        # Add a message if no data is available
        ax.text(0.5, 0.5, "No usage data available yet", 
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12)
        
        # Refresh the canvas
        self.figure.tight_layout()
        self.visualization_canvas.draw()
    
    def _update_visualization(self, event=None):
        """Update the visualization based on current selection."""
        # This is a placeholder for now
        # In a full implementation, this would visualize actual API usage data
        self._plot_initial_chart()
        
    def _open_api_documentation(self):
        """Open API documentation for the current service."""
        service = self.service_combo.get()
        if not service:
            messagebox.showinfo("No Service", "Please select a service first.")
            return
            
        # Map of services to documentation URLs
        doc_urls = {
            "binance": "https://binance-docs.github.io/apidocs/",
            "coinbase": "https://docs.cloud.coinbase.com/",
            "openai": "https://platform.openai.com/docs/",
            "alpha_vantage": "https://www.alphavantage.co/documentation/",
            "google": "https://developers.google.com/apis-explorer",
            "github": "https://docs.github.com/en/rest"
        }
        
        # Get the URL for the selected service or use a default
        url = doc_urls.get(service.lower(), "https://apilist.fun")
        
        # Open in browser
        webbrowser.open(url)
        
    def _open_security_guidelines(self):
        """Open API key security guidelines."""
        webbrowser.open("https://cheatsheetseries.owasp.org/cheatsheets/API_Security_Cheat_Sheet.html")
        
    async def _test_all_keys(self):
        """Test all API keys in the system."""
        self.status_label.config(text="Testing all API keys...")
        self.progress_bar.start()
        
        try:
            count = 0
            total = len(self.api_keys)
            
            for service in list(self.api_keys.keys()):
                count += 1
                self.status_label.config(text=f"Testing API keys ({count}/{total}): {service}")
                
                # Test each key
                await self._test_key(service)
                
                # Small delay to prevent flooding
                await asyncio.sleep(0.5)
                
            self.status_label.config(text=f"Completed testing {total} API keys")
            
        except Exception as e:
            logger.error(f"Error during bulk testing: {e}")
            self.status_label.config(text=f"Error testing API keys: {str(e)}")
            traceback.print_exc()
        finally:
            self.progress_bar.stop()
    
    def _export_keys(self):
        """Export API keys to a JSON file."""
        # Create a safe export with masked secrets
        export_data = {}
        
        for service, key_data in self.api_keys.items():
            export_data[service] = {}
            
            # Copy basic fields
            for field in ["description", "type", "expires"]:
                if field in key_data:
                    export_data[service][field] = key_data[field]
            
            # Mask sensitive fields
            for field in ["api_key", "api_secret"]:
                if field in key_data:
                    export_data[service][field] = self._mask_sensitive_data(key_data[field])
        
        # Ask for export location
        export_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export API Keys"
        )
        
        if not export_path:
            return
            
        try:
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
                
            self.status_label.config(text=f"Exported {len(export_data)} API keys to {export_path}")
            messagebox.showinfo("Export Complete", f"Successfully exported {len(export_data)} API keys.")
            
        except Exception as e:
            logger.error(f"Error exporting API keys: {e}")
            messagebox.showerror("Export Error", f"Failed to export API keys: {str(e)}")
    
    def _import_keys(self):
        """Import API keys from a JSON file."""
        import_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Import API Keys"
        )
        
        if not import_path:
            return
            
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)
                
            # Validate the import data
            if not isinstance(import_data, dict):
                raise ValueError("Invalid import file format")
                
            # Import each key
            count = 0
            for service, key_data in import_data.items():
                if service and isinstance(key_data, dict):
                    # Skip masked keys
                    if "api_key" in key_data and all(c == '*' for c in key_data["api_key"]):
                        continue
                        
                    # Add to our keys
                    self.api_keys[service] = key_data
                    count += 1
            
            # Update the UI
            self._categorize_keys()
            self._update_api_keys_display()
            
            self.status_label.config(text=f"Imported {count} API keys from {import_path}")
            messagebox.showinfo("Import Complete", f"Successfully imported {count} API keys.")
            
        except Exception as e:
            logger.error(f"Error importing API keys: {e}")
            messagebox.showerror("Import Error", f"Failed to import API keys: {str(e)}")
    
    def _remove_invalid_keys(self):
        """Remove API keys that are marked as invalid or have issues."""
        invalid_services = []
        
        for service, status_data in self.api_key_status.items():
            status = status_data.get("status", "unknown")
            if status in ["invalid", "error", "expired"]:
                invalid_services.append(service)
        
        if not invalid_services:
            messagebox.showinfo("No Invalid Keys", "No invalid API keys were found.")
            return
            
        # Confirm removal
        confirm = messagebox.askyesno(
            "Remove Invalid Keys",
            f"Are you sure you want to remove {len(invalid_services)} invalid API keys?"
        )
        
        if not confirm:
            return
            
        # Remove the keys
        for service in invalid_services:
            if service in self.api_keys:
                del self.api_keys[service]
            if service in self.api_key_status:
                del self.api_key_status[service]
        
        # Update the UI
        self._categorize_keys()
        self._update_api_keys_display()
        
        self.status_label.config(text=f"Removed {len(invalid_services)} invalid API keys")
        
    async def _handle_api_keys_status(self, event_type, data):
        """Handle API key status event."""
        if not data:
            return
            
        key_id = data.get("id")
        status = data.get("status", "unknown")
        service = data.get("service", "Unknown")
        
        try:
            # Update the status in our tracking dictionary
            if service not in self.api_key_status:
                self.api_key_status[service] = {}
                
            self.api_key_status[service]["status"] = status
            self.api_key_status[service]["last_checked"] = time.time()
            
            # Add any additional info from the event
            if "response_time" in data:
                self.api_key_status[service]["response_time"] = data["response_time"]
            if "issues" in data:
                self.api_key_status[service]["issues"] = data["issues"]
                
            # Update the UI
            self._update_api_keys_display()
            
            # Update key details if this is the selected service
            if self.selected_service == service:
                self._update_key_details(service)
                
            # Log the status update
            logger.info(f"API key status updated for {service}: {status}")
            
        except Exception as e:
            logger.error(f"Error handling API key status: {e}")
            traceback.print_exc()
        
        logger.info(f"API key status update: {service} - {status}")
        
        # Update status in treeview
        if key_id:
            for item_id in self.api_keys_tree.get_children():
                if self.api_keys_tree.item(item_id, "values")[2] == key_id:
                    values = list(self.api_keys_tree.item(item_id, "values"))
                    values[3] = status
                    self.api_keys_tree.item(item_id, values=values)
                    break
        
    async def _handle_api_keys_list(self, event_type, data):
        """Handle API keys list event."""
        if not data or "keys" not in data:
            return
            
        # Update the API keys
        self.api_keys = data["keys"]
        self._categorize_keys()
        self._update_api_keys_display()
        
        # Update refresh time
        self.last_refresh_time = time.time()
        self.refresh_in_progress = False
        
        # Update status
        if self.status_label:
            self.status_label.config(text=f"API keys refreshed at {datetime.now().strftime('%H:%M:%S')}")
        
        logger.info(f"Received {len(self.api_keys)} API keys")
    
    def _remove_invalid_keys(self):
        """Remove API keys that are marked as invalid or have issues."""
        invalid_services = []
        for service, key_data in self.api_keys.items():
            if key_data.get("status") == "invalid" or key_data.get("issues"):
                invalid_services.append(service)
                
        for service in invalid_services:
            if service in self.api_keys:
                del self.api_keys[service]
                logger.info(f"Removed invalid key for service: {service}")
    
    def _show_toast(self, message, bg_color="#333333", fg_color="#FFFFFF", duration=3000):
        """Show a toast notification in the bottom right of the frame.
        
        Args:
            message: The message to display
            bg_color: Background color (default: dark gray)
            fg_color: Text color (default: white)
            duration: Duration in milliseconds (default: 3 seconds)
        """
        try:
            # Create toast frame
            toast_frame = tk.Frame(self, bg=bg_color, padx=10, pady=5)
            toast_frame.place(relx=0.98, rely=0.98, anchor="se")
            
            # Add message label
            label = tk.Label(toast_frame, text=message, bg=bg_color, fg=fg_color,
                            font=("Arial", 10, "bold"))
            label.pack()
            
            # Auto-destroy after duration
            self.after(duration, toast_frame.destroy)
            
        except Exception as e:
            logger.error(f"Error showing toast notification: {e}")
            # Toast is non-critical, so just log the error
            
    async def _handle_api_connection_test_result(self, event_type, data):
        """Handle API connection test result event."""
        if not data:
            return
            
        service = data.get("service", "Unknown")
        success = data.get("success", False)
        message = data.get("message", "")
        response_time = data.get("response_time", 0)
        
        try:
            # Update the progress spinner and status
            if hasattr(self, 'test_progress') and self.test_progress:
                self.test_progress.stop()
                self.test_progress.config(text="")
                
            # Update the key status
            if service not in self.api_key_status:
                self.api_key_status[service] = {}
                
            status = "connected" if success else "error"
            self.api_key_status[service]["status"] = status
            self.api_key_status[service]["last_checked"] = time.time()
            self.api_key_status[service]["test_message"] = message
            self.api_key_status[service]["response_time"] = response_time
            
            # Update the UI
            self._update_api_keys_display()
            
            # Update key details if this is the selected service
            if self.selected_service == service:
                self._update_key_details(service)
                
            # Show a toast notification
            bg_color = "#4CAF50" if success else "#F44336"  # Green or Red
            fg_color = "#FFFFFF"  # White
            status_text = "Connection successful" if success else "Connection failed"
            self._show_toast(f"{service}: {status_text}", bg_color, fg_color)
            
            logger.info(f"API connection test result: {service} - {status} - {message}")
            
            # Update status label
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.config(text=f"Test result: {service} - {status}")
                
        except Exception as e:
            logger.error(f"Error handling API connection test result: {e}")
            traceback.print_exc()
            
            # Show error to user
            messagebox.showerror("Error", f"Failed to process connection test result: {str(e)}")
    
    async def _handle_api_key_update(self, event_type, data):
        """Handle API key update event."""
        if not data:
            return
            
        key_id = data.get("id")
        service = data.get("service", "Unknown")
        status = data.get("status", "unknown")
        
        try:
            # Update the key in our dictionary
            if key_id in self.api_keys:
                self.api_keys[key_id].update(data)
            else:
                self.api_keys[key_id] = data
                
            # Recategorize keys
            self._categorize_keys()
            
            # Update the display
            self._update_api_keys_display()
            
            # Update key details if this is the selected service
            if self.selected_service == service:
                self._update_key_details(service)
                
            # Show a toast notification
            bg_color = "#2196F3"  # Blue
            fg_color = "#FFFFFF"  # White
            if hasattr(self, '_show_toast'):
                self._show_toast(f"{service} API key updated", bg_color, fg_color)
                
            logger.info(f"API key updated: {service}")
            
        except Exception as e:
            logger.error(f"Error handling API key update: {e}")
            traceback.print_exc()
    
    async def _handle_api_key_delete(self, event_type, data):
        """Handle API key delete event."""
        if not data:
            return
            
        key_id = data.get("id")
        service = data.get("service", "Unknown")
        
        try:
            # Remove the key from our dictionary
            if key_id in self.api_keys:
                del self.api_keys[key_id]
                
            # Recategorize keys
            self._categorize_keys()
            
            # Update the display
            self._update_api_keys_display()
            
            # Clear details panel if this was the selected service
            if self.selected_service == service:
                self.selected_service = None
                if hasattr(self, 'key_details_frame') and self.key_details_frame:
                    for widget in self.key_details_frame.winfo_children():
                        widget.destroy()
                        
            # Show a toast notification
            bg_color = "#FF5722"  # Deep Orange
            fg_color = "#FFFFFF"  # White
            if hasattr(self, '_show_toast'):
                self._show_toast(f"{service} API key deleted", bg_color, fg_color)
                
            logger.info(f"API key deleted: {service}")
            
        except Exception as e:
            logger.error(f"Error handling API key delete: {e}")
            traceback.print_exc()
    
    async def _handle_api_key_status_update(self, event_type, data):
        """Handle API key status update event."""
        if not data:
            return
            
        # Extract service from event type
        # Format: api.key.status.{service}
        parts = event_type.split('.')
        if len(parts) >= 4:
            service = parts[3]
        else:
            service = data.get("service", "Unknown")
            
        status = data.get("status", "unknown")
        
        try:
            # Update the status in our tracking dictionary
            if service not in self.api_key_status:
                self.api_key_status[service] = {}
                
            self.api_key_status[service]["status"] = status
            self.api_key_status[service]["last_checked"] = time.time()
            
            # Add any additional info from the event
            for key in ["response_time", "issues", "quota", "rate_limit"]:
                if key in data:
                    self.api_key_status[service][key] = data[key]
            
            # Update the UI
            self._update_api_keys_display()
            
            # Update key details if this is the selected service
            if self.selected_service == service:
                self._update_key_details(service)
                
            # Log the status update
            logger.info(f"API key status updated for {service}: {status}")
            
        except Exception as e:
            logger.error(f"Error handling API key status update: {e}")
            traceback.print_exc()
    
    def _on_add_key(self):
        """Handle add key button click."""
        # Get values from form
        service = self.service_combo.get()
        api_key = self.api_key_entry.get().strip()
        api_secret = self.api_secret_entry.get().strip()
        description = self.description_entry.get().strip()
        
        # Validate
        if not service or not api_key or not api_secret:
            messagebox.showerror("Error", "Service, API Key and API Secret are required")
            return
            
        # Publish event to add the key
        asyncio.create_task(self._add_key(service, api_key, api_secret, description))
    
    async def _add_key(self, service, api_key, api_secret, description):
        """Add an API key."""
        if not self.event_bus:
            logger.error("No event bus available to add key")
            return
            
        try:
            await self.event_bus.publish("api.keys.add", {
                "service": service,
                "key": api_key,
                "secret": api_secret,
                "description": description,
                "timestamp": datetime.now().isoformat()
            })
            
            # Clear form
            self.api_key_entry.delete(0, tk.END)
            self.api_secret_entry.delete(0, tk.END)
            self.description_entry.delete(0, tk.END)
            
            # Update status
            self.status_label.config(text=f"Adding {service} API key...")
        except Exception as e:
            logger.error(f"Error adding API key: {e}")
            messagebox.showerror("Error", f"Failed to add API key: {str(e)}")
    
    def _on_delete_key(self):
        """Handle delete key button click."""
        # Get selected item
        selected = self.api_keys_tree.selection()
        if not selected:
            messagebox.showerror("Error", "No API key selected")
            return
            
        # Get key ID
        selected_item = selected[0]
        masked_key = self.api_keys_tree.item(selected_item, "values")[2]
        service = self.api_keys_tree.item(selected_item, "values")[0]
        
        # Confirm deletion
        if messagebox.askyesno("Confirm", f"Are you sure you want to delete the {service} API key?"):
            # Find the key ID from the masked key
            key_id = None
            for k_id, key in self.api_keys.items():
                if key.get("masked_key") == masked_key:
                    key_id = k_id
                    break
                    
            if key_id:
                asyncio.create_task(self._delete_key(key_id))
            else:
                messagebox.showerror("Error", "Could not find API key to delete")
    
    async def _delete_key(self, key_id):
        """Delete an API key."""
        if not self.event_bus:
            logger.error("No event bus available to delete key")
            return
            
        try:
            await self.event_bus.publish("api.keys.delete", {
                "id": key_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Update status
            self.status_label.config(text=f"Deleting API key...")
        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            messagebox.showerror("Error", f"Failed to delete API key: {str(e)}")
    
    def _on_test_key(self):
        """Handle test key button click."""
        # Get selected item
        selected = self.api_keys_tree.selection()
        if not selected:
            messagebox.showerror("Error", "No API key selected")
            return
            
        # Get key ID
        selected_item = selected[0]
        masked_key = self.api_keys_tree.item(selected_item, "values")[2]
        service = self.api_keys_tree.item(selected_item, "values")[0]
        
        # Find the key ID from the masked key
        key_id = None
        for k_id, key in self.api_keys.items():
            if key.get("masked_key") == masked_key:
                key_id = k_id
                break
                
        if key_id:
            asyncio.create_task(self._test_key(key_id, service))
        else:
            messagebox.showerror("Error", "Could not find API key to test")
    
    async def _test_key(self, key_id, service):
        """Test an API key connection."""
        if not self.event_bus:
            logger.error("No event bus available to test key")
            return
            
        try:
            await self.event_bus.publish("api.keys.test", {
                "id": key_id,
                "service": service,
                "timestamp": datetime.now().isoformat()
            })
            
            # Update status
            self.status_label.config(text=f"Testing {service} API key...")
        except Exception as e:
            logger.error(f"Error testing API key: {e}")
            messagebox.showerror("Error", f"Failed to test API key: {str(e)}")
    
    def _on_key_selected(self, event):
        """Handle API key selection."""
        # Get selected item
        selected = self.api_keys_tree.selection()
        if not selected:
            return
            
        # Get service
        selected_item = selected[0]
        service = self.api_keys_tree.item(selected_item, "values")[0]
        
        # Set service in dropdown
        if service in self.service_combo["values"]:
            self.service_combo.set(service)
