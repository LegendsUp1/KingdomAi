#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Wallet Panel GUI

This module provides a Tkinter-based wallet management panel for the Kingdom AI system,
allowing users to view balances, create wallets, and make transactions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from tkinter.ttk import Frame, LabelFrame, Label, Button
import asyncio
import logging
import threading
import json
import time
from typing import Dict, Any, Optional, List, Callable, Union

from core.base_component import BaseComponent

logger = logging.getLogger('KingdomAI.WalletPanel')

class WalletPanel(BaseComponent):
    """Tkinter-based wallet management panel GUI."""
    
    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None):
        """Initialize wallet panel component."""
        super().__init__(event_bus)
        self.config = config or {}
        
        # GUI elements
        self.parent = None
        self.balance_labels: Dict[str, Dict[str, Any]] = {}
        self.transaction_history = None
        self.coin_var = None
        self.amount_var = None
        self.to_address_var = None
        
        # Wallet state
        self.wallets: Dict[str, Dict[str, Any]] = {}
        self.balances: Dict[str, float] = {}
        self.running = False
        self.update_loop_task = None
        
        # Supported coins
        self.supported_coins = self.config.get("supported_coins", ["ETH", "BTC", "XRP", "SOL", "PI"])
        
    def _safe_publish(self, event_type: str, data: Dict[str, Any] = None) -> None:
        """Safely publish an event using the best available method.
        
        Args:
            event_type: The type of event to publish
            data: Optional data to include with the event
        """
        if self.event_bus is None:
            logger.error(f"Cannot publish event {event_type}: event_bus is None")
            return
        
        if data is None:
            data = {}
            
        # Try to use publish_sync first (preferred for GUI context)
        publish_sync = getattr(self.event_bus, 'publish_sync', None)
        if publish_sync and callable(publish_sync):
            try:
                publish_sync(event_type, data)
                return
            except Exception as e:
                logger.error(f"Error in publish_sync for {event_type}: {e}")
                
        # Fall back to async publish with proper handling
        publish = getattr(self.event_bus, 'publish', None)
        if publish and callable(publish):
            try:
                result = publish(event_type, data)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
                return
            except Exception as e:
                logger.error(f"Error in async publish for {event_type}: {e}")
                
        logger.error(f"No working publish method found for {event_type}")
    
    async def _handle_wallet_created(self, data: Dict[str, Any]) -> None:
        """Handle wallet created event.
        
        Args:
            data: Event data containing coin and address information
        """
        coin = data.get("coin")
        address = data.get("address")
        
        if not coin or not address:
            return
            
        # Store wallet info
        if coin not in self.wallets:
            self.wallets[coin] = {}
        self.wallets[coin]["address"] = address
        
        # Update UI if balance labels exist for this coin
        if coin in self.balance_labels:
            # Shorten address for display
            short_addr = address[:6] + "..." + address[-4:]
            self.balance_labels[coin]["address"].config(text=short_addr)
            
        self._add_to_history(f"Created new {coin} wallet: {address}")
        
        # Request initial balance
        self._safe_publish("wallet.get_balance", {
            "coin": coin,
            "address": address
        })
        
    async def _handle_balance_update(self, data: Dict[str, Any]) -> None:
        """Handle balance update event.
        
        Args:
            data: Event data containing balance information
        """
        coin = data.get("coin")
        balance = data.get("balance", 0.0)  # Default to 0.0 if not present
        address = data.get("address")
        
        if not coin or coin not in self.balance_labels:
            return
            
        # Update stored balance
        self.balances[coin] = float(balance)  # Ensure float type
        
        # Update UI
        self.balance_labels[coin]["balance"].config(text=f"{balance:.8f}")
        
        # Update address if available
        if address and coin in self.wallets:
            short_addr = address[:6] + "..." + address[-4:]
            self.balance_labels[coin]["address"].config(text=short_addr)
    
    async def _handle_transaction_sent(self, data: Dict[str, Any]) -> None:
        """Handle transaction sent event.
        
        Args:
            data: Event data containing transaction details
        """
        coin = data.get("coin")
        from_address = data.get("from_address")
        to_address = data.get("to_address")
        amount = data.get("amount")
        tx_hash = data.get("tx_hash")
        
        if not all([coin, from_address, to_address, amount, tx_hash]):
            return
            
        # Add to history
        self._add_to_history(
            f"Transaction sent: {amount} {coin} to {to_address}\n"
            f"  Hash: {tx_hash}"
        )
        
        # Request updated balance after transaction
        self._safe_publish("wallet.get_balance", {
            "coin": coin,
            "address": from_address
        })
    
    async def _handle_wallet_list(self, data: Dict[str, Any]) -> None:
        """Handle wallet list response event.
        
        Args:
            data: Event data containing list of wallets
        """
        wallets = data.get("wallets", [])
        
        for wallet in wallets:
            coin = wallet.get("coin")
            address = wallet.get("address")
            
            if not coin or not address:
                continue
                
            # Store wallet info
            if coin not in self.wallets:
                self.wallets[coin] = {}
            self.wallets[coin]["address"] = address
            
            # Update UI
            if coin in self.balance_labels:
                # Shorten address for display
                short_addr = address[:6] + "..." + address[-4:]
                self.balance_labels[coin]["address"].config(text=short_addr)
                
            # Request initial balance
            self._safe_publish("wallet.get_balance", {
                "coin": coin,
                "address": address
            })
    
    async def _handle_wallet_error(self, data: Dict[str, Any]) -> None:
        """Handle wallet error event.
        
        Args:
            data: Event data containing error information
        """
        coin = data.get("coin")
        operation = data.get("operation")
        error = data.get("error")
        
        if not all([coin, operation, error]):
            return
            
        # Add to history
        self._add_to_history(f"Error: {coin} {operation} failed: {error}")
        
    async def _handle_shutdown(self, _: Dict[str, Any]) -> None:
        """Handle system shutdown event.
        
        Args:
            _: Event data (not used)
        """
        self.running = False
    
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize wallet panel component.
        
        Args:
            event_bus: Optional event bus to use instead of the one passed to constructor
            config: Optional config to use instead of the one passed to constructor
            
        Returns:
            bool: True if initialization was successful
        """
        try:
            logger.info("Initializing Wallet Panel...")
            
            # Use provided event_bus and config if given
            if event_bus is not None:
                self.event_bus = event_bus
            if config is not None:
                self.config = config
            
            # Register event handlers
            if self.event_bus:
                self.event_bus.subscribe_sync("wallet.created", self._handle_wallet_created)
                self.event_bus.subscribe_sync("wallet.balance", self._handle_balance_update)
                self.event_bus.subscribe_sync("wallet.transaction_sent", self._handle_transaction_sent)
                self.event_bus.subscribe_sync("wallet.list_response", self._handle_wallet_list)
                self.event_bus.subscribe_sync("wallet.error", self._handle_wallet_error)
                self.event_bus.subscribe_sync("system.shutdown", self._handle_shutdown)
                
                # Get existing wallets
                self._safe_publish("wallet.list", {})
            else:
                logger.error("Event bus not available for Wallet Panel")
            
            # Set running state
            self.running = True
            
            logger.info("Wallet Panel initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Wallet Panel: {e}")
            return False
            
    def create_ui(self, parent_frame: ttk.Frame) -> None:
        """Create the wallet panel UI within the parent frame."""
        self.parent = parent_frame
        
        # Create main frame with padding
        main_frame = ttk.Frame(parent_frame, padding="10", style="Wallet.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create top frame for wallet balances
        balance_frame = ttk.LabelFrame(main_frame, text="Wallet Balances", padding="5")
        balance_frame.pack(fill=tk.X, pady=5)
        
        # Add balance labels for supported coins
        self._setup_balance_area(balance_frame)
        
        # Create wallet management frame
        mgmt_frame = ttk.LabelFrame(main_frame, text="Wallet Management", padding="5")
        mgmt_frame.pack(fill=tk.X, pady=5)
        
        # Wallet creation area
        create_frame = ttk.Frame(mgmt_frame, style="Wallet.TFrame")
        create_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(create_frame, text="Create New Wallet:", style="Wallet.TLabel").pack(side=tk.LEFT)
        
        self.create_coin_var = tk.StringVar(value=self.supported_coins[0])
        coin_combo = ttk.Combobox(create_frame, textvariable=self.create_coin_var, 
                                  values=self.supported_coins, state="readonly", width=10)
        coin_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(create_frame, text="Create Wallet", 
                  command=self._create_wallet).pack(side=tk.LEFT, padx=5)
        
        # Transaction area
        tx_frame = ttk.LabelFrame(main_frame, text="Send Transaction", padding="5")
        tx_frame.pack(fill=tk.X, pady=5)
        
        # Coin selection
        coin_frame = ttk.Frame(tx_frame, style="Wallet.TFrame")
        coin_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(coin_frame, text="Coin:", style="Wallet.TLabel").pack(side=tk.LEFT)
        self.coin_var = tk.StringVar(value=self.supported_coins[0] if self.supported_coins else "")
        coin_combo = ttk.Combobox(coin_frame, textvariable=self.coin_var, 
                                 values=self.supported_coins, state="readonly", width=15)
        coin_combo.pack(side=tk.LEFT, padx=5)
        
        # Recipient address
        address_frame = ttk.Frame(tx_frame, style="Wallet.TFrame")
        address_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(address_frame, text="To Address:", style="Wallet.TLabel").pack(side=tk.LEFT)
        self.to_address_var = tk.StringVar()
        ttk.Entry(address_frame, textvariable=self.to_address_var, width=50).pack(side=tk.LEFT, padx=5)
        
        # Amount
        amount_frame = ttk.Frame(tx_frame, style="Wallet.TFrame")
        amount_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(amount_frame, text="Amount:", style="Wallet.TLabel").pack(side=tk.LEFT)
        self.amount_var = tk.StringVar(value="0.01")
        ttk.Entry(amount_frame, textvariable=self.amount_var, width=15).pack(side=tk.LEFT, padx=5)
        
        # Transaction buttons
        button_frame = ttk.Frame(tx_frame, style="Wallet.TFrame")
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(button_frame, text="Send", 
                  command=self._send_transaction).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Reset", 
                  command=self._reset_form).pack(side=tk.LEFT, padx=5)
        
        # Transaction history
        history_frame = ttk.LabelFrame(main_frame, text="Transaction History", padding="5")
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.transaction_history = scrolledtext.ScrolledText(history_frame, height=10, wrap=tk.WORD)
        self.transaction_history.pack(fill=tk.BOTH, expand=True)
        self.transaction_history.config(state=tk.DISABLED)
        
        # Add entry to transaction history
        self._add_to_history("Wallet panel initialized. Create or select a wallet to begin.")
        
        # Start update loop in thread
        self._start_balance_updates()
    
    def _setup_balance_area(self, balance_frame: Union[Frame, LabelFrame]) -> None:
        """Setup the balance display area for different coins."""
        # Create initial row_frame
        row_frame = Frame(balance_frame)
        row_frame.pack(fill=tk.X, pady=2)
        
        for i, coin in enumerate(self.supported_coins):
            if i > 0 and i % 3 == 0:
                # Create a new row for every 3 coins
                row_frame = Frame(balance_frame)
                row_frame.pack(fill=tk.X, pady=2)
            
            # Create a frame for this coin
            coin_frame = Frame(row_frame)
            coin_frame.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
            
            # Coin label
            Label(coin_frame, text=f"{coin}:", width=8).pack(side=tk.LEFT)
            
            # Create balance display with address button
            balance_display_frame = Frame(coin_frame)
            balance_display_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Balance label
            balance_label = Label(balance_display_frame, text="Not available", width=15)
            balance_label.pack(anchor=tk.W)
            
            # Address label (shortened)
            address_label = Label(balance_display_frame, text="No wallet", font=("Courier", 8))
            address_label.pack(anchor=tk.W)
            
            # Create refresh button
            refresh_btn = Button(coin_frame, text="↻", width=3, 
                               command=lambda c=coin: self._refresh_balance(c))
            refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))
            
            # Store references to labels
            self.balance_labels[coin] = {
                "balance": balance_label,
                "address": address_label,
                "refresh": refresh_btn
            }
    
    def initialize_sync(self) -> bool:
        """Synchronous version of initialize"""
        try:
            logger.info("Initializing Wallet Panel (sync)...")
            
            # Register event handlers
            if self.event_bus:
                self.event_bus.subscribe_sync("wallet.created", self._handle_wallet_created)
                self.event_bus.subscribe_sync("wallet.balance", self._handle_balance_update)
                self.event_bus.subscribe_sync("wallet.transaction_sent", self._handle_transaction_sent)
                self.event_bus.subscribe_sync("wallet.list_response", self._handle_wallet_list)
                self.event_bus.subscribe_sync("wallet.error", self._handle_wallet_error)
                self.event_bus.subscribe_sync("system.shutdown", self._handle_shutdown)
                
            # Get existing wallets
            if self.event_bus:
                self.event_bus.publish("wallet.list", {})
            
            # Set running state
            self.running = True
            
            logger.info("Wallet Panel initialized successfully (sync)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Wallet Panel (sync): {e}")
            return False
    
    def _start_balance_updates(self) -> None:
        """Start the periodic balance update loop."""
        if not self.running:
            return
            
        def update_loop():
            while self.running:
                # Schedule balance updates through event loop
                for coin, wallet in self.wallets.items():
                    asyncio.run_coroutine_threadsafe(
                        self._safe_publish("wallet.get_balance", {
                            "coin": coin,
                            "address": wallet.get("address")
                        }),
                        asyncio.get_event_loop()
                    )
                
                # Sleep for 30 seconds
                time.sleep(30)
                
        # Start update loop in background thread
        threading.Thread(target=update_loop, daemon=True).start()
    
    def _create_wallet(self) -> None:
        """Handle wallet creation from GUI."""
        try:
            coin = self.coin_var.get() if hasattr(self, 'coin_var') and self.coin_var else self.create_coin_var.get() if hasattr(self, 'create_coin_var') and self.create_coin_var else None
            if not coin:
                messagebox.showerror("Error", "Please select a coin")
                return
                
            # Add to history
            self._add_to_history(f"Creating wallet for {coin}...")
            
            # Publish create wallet event
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("wallet.create", {"coin": coin}))
            else:
                logger.error("Event bus not available for wallet creation")
                self._add_to_history("Error: Could not create wallet - event bus unavailable")
                
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            self._add_to_history(f"Error creating wallet: {e}")
            messagebox.showerror("Error", f"Failed to create wallet: {e}")

    def _send_transaction(self) -> None:
        """Handle transaction sending from GUI."""
        try:
            coin = self.coin_var.get() if hasattr(self, 'coin_var') and self.coin_var else None
            amount = self.amount_var.get() if hasattr(self, 'amount_var') and self.amount_var else None
            to_address = self.to_address_var.get() if hasattr(self, 'to_address_var') and self.to_address_var else None
            
            if not coin or not amount or not to_address:
                messagebox.showerror("Error", "All fields are required")
                return
                
            try:
                amount = float(amount)
            except ValueError:
                messagebox.showerror("Error", "Amount must be a number")
                return
                
            # Add to history
            self._add_to_history(f"Sending {amount} {coin} to {to_address[:10]}...")
            
            # Publish transaction event
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("wallet.send_transaction", {
                    "coin": coin,
                    "amount": amount,
                    "to_address": to_address
                }))
            else:
                logger.error("Event bus not available for sending transaction")
                self._add_to_history("Error: Could not send transaction - event bus unavailable")
                
            # Reset form
            self._reset_form()
            
        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            self._add_to_history(f"Error sending transaction: {e}")
            messagebox.showerror("Error", f"Failed to send transaction: {e}")

    def _refresh_balance(self, coin: str) -> None:
        """Manually refresh balance for a coin."""
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish("wallet.balance.request", {"coin": coin}))
            self._add_to_history(f"Refreshing {coin} balance...")
        else:
            logger.error("Event bus not available for balance refresh")
            self._add_to_history("Error: Could not refresh balance - event bus unavailable")
    
    def _reset_form(self) -> None:
        """Reset the transaction form."""
        if not self.to_address_var or not self.amount_var:
            logger.error("UI components not initialized")
            return
            
        self.to_address_var.set("")
        self.amount_var.set("0.01")
    
    def _add_to_history(self, message: str) -> None:
        """Add a message to the transaction history."""
        if not self.transaction_history:
            return
            
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        self.transaction_history.config(state=tk.NORMAL)
        self.transaction_history.insert(tk.END, f"[{timestamp}] {message}\n")
        self.transaction_history.see(tk.END)
        self.transaction_history.config(state=tk.DISABLED)
