#!/usr/bin/env python3
"""
Dashboard Market Handler

Adds real-time market data capabilities to the Dashboard frame.
"""

import tkinter as tk
from tkinter import ttk
import logging
import asyncio
from datetime import datetime

class DashboardMarketHandler:
    """
    Mixin class to add market data handling capabilities to the Dashboard frame.
    """
    
    def __init__(self):
        """Initialize the market handler mixin."""
        self.logger = logging.getLogger("KingdomAI.DashboardMarketHandler")
        
        # Market data storage
        self.market_data = {}
        self.market_updates_count = 0
        
        # UI elements for market data
        self.market_frame = None
        self.market_labels = {}
        
        # Store crypto symbols and their display names
        self.crypto_symbols = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
            "XRP": "Ripple",
            "ADA": "Cardano",
            "SOL": "Solana",
            "DOT": "Polkadot"
        }
        
        self.logger.info("DashboardMarketHandler initialized")
    
    def setup_market_display(self, parent_frame):
        """
        Create UI elements for displaying market data.
        
        Args:
            parent_frame: The parent frame to contain market widgets
        """
        # Create a frame for market data
        self.market_frame = ttk.LabelFrame(parent_frame, text="Market Data")
        self.market_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create headers
        headers_frame = ttk.Frame(self.market_frame)
        headers_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Column headers
        ttk.Label(headers_frame, text="Symbol", width=10).grid(row=0, column=0, padx=5)
        ttk.Label(headers_frame, text="Price", width=12).grid(row=0, column=1, padx=5)
        ttk.Label(headers_frame, text="24h Change", width=10).grid(row=0, column=2, padx=5)
        ttk.Label(headers_frame, text="Trend", width=10).grid(row=0, column=3, padx=5)
        
        # Create a container for the crypto rows
        data_frame = ttk.Frame(self.market_frame)
        data_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create rows for each cryptocurrency
        row = 0
        for symbol, name in self.crypto_symbols.items():
            # Symbol label
            symbol_label = ttk.Label(data_frame, text=f"{symbol}", width=10)
            symbol_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")
            
            # Price label
            price_label = ttk.Label(data_frame, text="Loading...", width=12)
            price_label.grid(row=row, column=1, padx=5, pady=2)
            
            # 24h Change label
            change_label = ttk.Label(data_frame, text="--", width=10)
            change_label.grid(row=row, column=2, padx=5, pady=2)
            
            # Trend label
            trend_label = ttk.Label(data_frame, text="--", width=10)
            trend_label.grid(row=row, column=3, padx=5, pady=2)
            
            # Store references to labels
            self.market_labels[symbol] = {
                "symbol": symbol_label,
                "price": price_label,
                "change": change_label,
                "trend": trend_label
            }
            
            row += 1
        
        # Add a last updated timestamp at the bottom
        self.last_updated_label = ttk.Label(self.market_frame, text="Last updated: Never")
        self.last_updated_label.pack(anchor="e", padx=5, pady=5)
        
        self.logger.info("Market display UI created")
    
    async def handle_market_update(self, event_data):
        """
        Handle market update events.
        
        Args:
            event_data: The event data containing market information
        """
        try:
            if not event_data:
                return
            
            symbol = event_data.get("symbol")
            price = event_data.get("price")
            
            if not symbol or price is None:
                return
            
            # Store the data
            if symbol not in self.market_data:
                self.market_data[symbol] = {}
            
            self.market_data[symbol].update({
                "price": price,
                "volume": event_data.get("volume", 0),
                "trend": event_data.get("trend", "stable"),
                "24h_change": event_data.get("24h_change", 0),
                "timestamp": event_data.get("timestamp", datetime.now().isoformat())
            })
            
            # Update UI if we have the labels
            if symbol in self.market_labels:
                # Format price with commas and appropriate decimals
                formatted_price = f"${price:,.2f}"
                
                # Get the 24h change
                change = self.market_data[symbol].get("24h_change", 0)
                change_text = f"{change:+.2f}%" if change else "--"
                
                # Set color based on change
                change_color = "#4CAF50" if change > 0 else "#F44336" if change < 0 else "#757575"
                
                # Get trend
                trend = self.market_data[symbol].get("trend", "stable")
                trend_color = "#4CAF50" if trend == "bullish" else "#F44336" if trend == "bearish" else "#FFC107"
                
                # Update labels
                if hasattr(self, "after"):
                    self.after(0, lambda: self._update_market_labels(
                        symbol, formatted_price, change_text, change_color, trend, trend_color
                    ))
            
            # Increment update counter and update timestamp
            self.market_updates_count += 1
            self._update_last_updated()
            
            # Log the update
            if hasattr(self, "log_message"):
                message = f"Market update: {symbol} = {price:,.2f} ({event_data.get('24h_change', 0):+.2f}%)"
                self.log_message(message)
            
            # Update any dashboard status indicators if available
            if hasattr(self, "update_component_status"):
                self.update_component_status("trading", "Receiving market data", "#4CAF50")
        except Exception as e:
            self.logger.error(f"Error handling market update: {e}")
    
    def _update_market_labels(self, symbol, price_text, change_text, change_color, trend, trend_color):
        """
        Update the market data labels in the UI.
        
        Args:
            symbol: The cryptocurrency symbol
            price_text: Formatted price text
            change_text: Formatted 24h change text
            change_color: Color for the change label
            trend: Trend text
            trend_color: Color for the trend label
        """
        if symbol in self.market_labels:
            labels = self.market_labels[symbol]
            
            # Update price
            labels["price"].config(text=price_text)
            
            # Update change with color
            labels["change"].config(text=change_text, foreground=change_color)
            
            # Update trend with color
            labels["trend"].config(text=trend, foreground=trend_color)
    
    def _update_last_updated(self):
        """Update the last updated timestamp."""
        if hasattr(self, "last_updated_label") and hasattr(self, "after"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.after(0, lambda: self.last_updated_label.config(
                text=f"Last updated: {timestamp} ({self.market_updates_count} updates)"
            ))
    
    def register_market_events(self, event_bus_wrapper):
        """
        Register to market-related events.
        
        Args:
            event_bus_wrapper: The EventBusWrapper to use for subscription
        """
        try:
            # Subscribe to market updates
            event_bus_wrapper.subscribe("market.update", self.handle_market_update)
            event_bus_wrapper.subscribe("market.prices_update", self.handle_market_update)
            
            self.logger.info("Registered market events")
            return True
        except Exception as e:
            self.logger.error(f"Error registering market events: {e}")
            return False
