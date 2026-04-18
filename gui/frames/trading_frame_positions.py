"""
Trading Frame Positions Module
Handles position data integration with Redis Quantum Nexus for the Trading Frame
"""

import asyncio
import logging
import json
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional

from gui.frames.redis_positions_handler import RedisPositionsHandler

class TradingFramePositions:
    """
    Mixin class for TradingFrame to handle position data with mandatory
    Redis Quantum Nexus connectivity on port 6380.
    """
    
    def setup_positions_interface(self):
        """
        Set up the positions interface components in the trading frame.
        """
        try:
            # Create positions tree view in the positions tab
            self.positions_frame = ttk.Frame(self.positions_tab)
            self.positions_frame.pack(fill=tk.BOTH, expand=True)
            
            # Create positions tree with headers
            self.positions_tree = ttk.Treeview(
                self.positions_frame,
                columns=("Symbol", "Amount", "Entry Price", "Current Price", "P&L", "P&L %", "Value"),
                show="headings",
                height=10
            )
            
            # Configure columns
            self.positions_tree.heading("Symbol", text="Symbol")
            self.positions_tree.heading("Amount", text="Amount")
            self.positions_tree.heading("Entry Price", text="Entry Price")
            self.positions_tree.heading("Current Price", text="Current Price")
            self.positions_tree.heading("P&L", text="P&L")
            self.positions_tree.heading("P&L %", text="P&L %")
            self.positions_tree.heading("Value", text="Value USD")
            
            # Set column widths
            self.positions_tree.column("Symbol", width=100, anchor=tk.CENTER)
            self.positions_tree.column("Amount", width=100, anchor=tk.CENTER)
            self.positions_tree.column("Entry Price", width=100, anchor=tk.CENTER)
            self.positions_tree.column("Current Price", width=100, anchor=tk.CENTER)
            self.positions_tree.column("P&L", width=100, anchor=tk.CENTER)
            self.positions_tree.column("P&L %", width=100, anchor=tk.CENTER)
            self.positions_tree.column("Value", width=100, anchor=tk.CENTER)
            
            # Add a scrollbar
            positions_scroll = ttk.Scrollbar(self.positions_frame, orient="vertical", command=self.positions_tree.yview)
            self.positions_tree.configure(yscrollcommand=positions_scroll.set)
            
            # Layout
            self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            positions_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Create a refresh button for positions data
            refresh_frame = ttk.Frame(self.positions_tab)
            refresh_frame.pack(fill=tk.X, pady=5)
            
            refresh_button = ttk.Button(
                refresh_frame, 
                text="Refresh Positions From Redis",
                command=self._refresh_positions_from_redis
            )
            refresh_button.pack(side=tk.RIGHT, padx=10)
            
            # Status label for Redis connectivity
            self.redis_positions_status_var = tk.StringVar(value="Redis status: Not connected")
            self.redis_positions_status = ttk.Label(
                refresh_frame,
                textvariable=self.redis_positions_status_var,
                font=("Helvetica", 10)
            )
            self.redis_positions_status.pack(side=tk.LEFT, padx=10)
            
            # Initialize Redis positions handler
            asyncio.create_task(self._initialize_redis_positions_handler())
            
            # Subscribe to position update events
            self._subscribe_to_position_events()
            
            self.logger.info("Positions interface set up successfully")
            
        except Exception as e:
            self.logger.error(f"Error setting up positions interface: {e}")
    
    async def _initialize_redis_positions_handler(self):
        """
        Initialize the Redis Positions Handler with mandatory connectivity on port 6380.
        System will halt or display error if Redis is not available.
        """
        try:
            self.logger.info("Initializing Redis Positions Handler with mandatory connectivity...")
            self.redis_positions_status_var.set("Redis status: Connecting...")
            
            # Create and initialize the Redis positions handler
            self.positions_handler = RedisPositionsHandler(event_bus=self._event_bus)
            await self.positions_handler.initialize()
            
            # Initial fetch of positions data
            await self._update_positions_display()
            
            self.redis_positions_status_var.set("Redis status: Connected to port 6380")
            self.redis_positions_status.configure(foreground="green")
            self.logger.info("Redis Positions Handler initialized successfully")
            
        except ConnectionError as e:
            error_message = f"CRITICAL: Failed to connect to Redis Quantum Nexus: {str(e)}"
            self.logger.critical(error_message)
            self.redis_positions_status_var.set("Redis status: Connection FAILED")
            self.redis_positions_status.configure(foreground="red")
            
            # Disable trading functionality
            self._disable_trading_on_redis_failure()
            
            # Show error popup
            if hasattr(self, "update_status"):
                self.update_status(
                    "Redis Quantum Nexus connection failed - trading disabled",
                    color="red"
                )
            
            # Publish the Redis error event for system-wide handling
            if hasattr(self, "safe_publish"):
                self.safe_publish("system.error", {
                    "source": "trading_frame",
                    "error": "Redis Quantum Nexus connection failed",
                    "message": str(e),
                    "critical": True
                })
    
    def _subscribe_to_position_events(self):
        """Subscribe to position update events from the event bus."""
        if not hasattr(self, "_event_bus") or not self._event_bus:
            self.logger.warning("Event bus not available, cannot subscribe to position events")
            return
            
        # Subscribe to position update events
        asyncio.create_task(self._safe_subscribe("trading.position.update", self._handle_position_update))
        self.logger.info("Subscribed to position events")
    
    def _refresh_positions_from_redis(self):
        """
        Refresh positions data from Redis Quantum Nexus.
        Called by the refresh button.
        """
        asyncio.create_task(self._update_positions_display())
    
    async def _update_positions_display(self):
        """
        Update the positions display with data from Redis Quantum Nexus.
        No fallbacks allowed - will raise an error if Redis is unavailable.
        """
        try:
            if not hasattr(self, "positions_handler") or not self.positions_handler:
                self.logger.error("Redis Positions Handler not initialized")
                return
            
            # Clear existing entries
            if hasattr(self, "positions_tree"):
                for item in self.positions_tree.get_children():
                    self.positions_tree.delete(item)
            
            # Fetch positions data from Redis
            positions_data = await self.positions_handler.fetch_positions()
            
            if not positions_data:
                self.logger.info("No positions data found in Redis")
                return
            
            # Update the positions tree with the fetched data
            for symbol, position in positions_data.items():
                try:
                    # Calculate P&L
                    entry_price = float(position.get("entry_price", 0))
                    current_price = float(position.get("current_price", 0))
                    amount = float(position.get("amount", 0))
                    
                    if entry_price > 0 and current_price > 0 and amount > 0:
                        pnl = amount * (current_price - entry_price)
                        pnl_percent = ((current_price / entry_price) - 1) * 100
                        value = amount * current_price
                    else:
                        pnl = 0
                        pnl_percent = 0
                        value = 0
                    
                    # Format values for display
                    pnl_str = f"${pnl:.2f}"
                    pnl_percent_str = f"{pnl_percent:.2f}%"
                    
                    # Color code P&L values
                    pnl_color = "green" if pnl >= 0 else "red"
                    
                    # Insert the data into the tree with color
                    position_id = self.positions_tree.insert("", tk.END, values=(
                        symbol,
                        f"{amount:.6f}",
                        f"${entry_price:.2f}",
                        f"${current_price:.2f}",
                        pnl_str,
                        pnl_percent_str,
                        f"${value:.2f}"
                    ))
                    
                    # Apply color to P&L columns
                    self.positions_tree.item(position_id, tags=(pnl_color,))
                    
                except (ValueError, KeyError) as e:
                    self.logger.error(f"Error processing position data for {symbol}: {e}")
            
            # Configure color tags
            self.positions_tree.tag_configure("green", foreground="green")
            self.positions_tree.tag_configure("red", foreground="red")
            
            self.logger.info("Positions display updated from Redis Quantum Nexus")
            
        except ConnectionError as e:
            error_message = f"Redis connection error updating positions: {str(e)}"
            self.logger.critical(error_message)
            self._handle_redis_connection_failure(error_message)
        
        except Exception as e:
            self.logger.error(f"Error updating positions display: {e}")
    
    async def _handle_position_update(self, event_data):
        """
        Handle position update events from the event bus.
        
        Args:
            event_data (dict): Position update data
        """
        try:
            self.logger.debug("Received position update event")
            
            if not event_data or not isinstance(event_data, dict):
                self.logger.warning("Invalid position update data received")
                return
            
            # Update the Redis database with the new position data if necessary
            if "symbol" in event_data and "position" in event_data:
                symbol = event_data["symbol"]
                position_data = event_data["position"]
                
                # Update Redis with the new position data
                if hasattr(self, "positions_handler") and self.positions_handler:
                    await self.positions_handler.update_position(symbol, position_data)
            
            # Refresh the positions display
            await self._update_positions_display()
            
        except ConnectionError as e:
            error_message = f"Redis connection error handling position update: {str(e)}"
            self.logger.critical(error_message)
            self._handle_redis_connection_failure(error_message)
            
        except Exception as e:
            self.logger.error(f"Error handling position update: {e}")
    
    def _disable_trading_on_redis_failure(self):
        """
        Disable trading functionality when Redis connection fails.
        This is a critical action as we require mandatory Redis connectivity.
        """
        try:
            self.logger.warning("Disabling trading functionality due to Redis connection failure")
            
            # Disable trading controls
            for widget_name in ["buy_button", "sell_button", "submit_order_button"]:
                if hasattr(self, widget_name) and getattr(self, widget_name):
                    widget = getattr(self, widget_name)
                    if hasattr(widget, "configure"):
                        widget.configure(state="disabled")
            
            # Show warning message
            warning_msg = "TRADING DISABLED: Redis Quantum Nexus connection required"
            
            # Create a warning label if it doesn't exist
            if not hasattr(self, "redis_warning_label"):
                if hasattr(self, "main_frame"):
                    self.redis_warning_label = ttk.Label(
                        self.main_frame,
                        text=warning_msg,
                        font=("Helvetica", 12, "bold"),
                        foreground="red",
                        background="yellow"
                    )
                    self.redis_warning_label.pack(fill=tk.X, pady=5, padx=5)
            
            self.logger.critical("Trading functionality disabled due to Redis connection failure")
            
        except Exception as e:
            self.logger.error(f"Error disabling trading functionality: {e}")
    
    def _handle_redis_connection_failure(self, error_message):
        """
        Handle Redis connection failures with appropriate UI updates and system notifications.
        
        Args:
            error_message (str): The error message describing the connection failure
        """
        # Update status displays
        self.redis_positions_status_var.set("Redis status: Connection FAILED")
        self.redis_positions_status.configure(foreground="red")
        
        # Disable trading functionality
        self._disable_trading_on_redis_failure()
        
        # Update the status bar if it exists
        if hasattr(self, "update_status"):
            self.update_status(
                "Redis Quantum Nexus connection failed - trading disabled",
                color="red"
            )
        
        # Publish a system error event
        if hasattr(self, "safe_publish"):
            self.safe_publish("system.error", {
                "source": "trading_frame",
                "error": "Redis Quantum Nexus connection failed",
                "message": error_message,
                "critical": True
            })
