#!/usr/bin/env python3
"""
Mining Frame for Kingdom AI GUI.
Provides interface for crypto mining operations and monitoring.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
import asyncio
import traceback
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union

from .base_frame import BaseFrame

logger = logging.getLogger(__name__)

class MiningFrame(BaseFrame):
    """Mining frame for the Kingdom AI GUI that provides interface for crypto mining operations and monitoring."""
    
    def __init__(self, parent: tk.Widget, event_bus: Any, name: str = "MiningFrame") -> None:
        """
        Initialize the Mining Frame.
        
        Args:
            parent: Parent widget
            event_bus: Event bus for pub/sub messaging
            name: Name of the frame
        """
        super().__init__(parent, event_bus, name)
        
        # Mining state variables
        self.mining_active = False
        self.hashrate = 0.0
        self.shares_accepted = 0
        self.shares_rejected = 0
        self.mining_devices = []
        self.mining_pool = ""
        self.wallet_address = ""
        self.pool_credentials = {}
        self.mining_rewards = 0.0
        self.temperature_data = {}
        self.efficiency_data = {}
        self.mining_logs = []
        
        # Tkinter variables for UI components
        self.hashrate_var = tk.StringVar(value="0.0 H/s")
        self.shares_accepted_var = tk.StringVar(value="0")
        self.shares_rejected_var = tk.StringVar(value="0")
        self.mining_status_var = tk.StringVar(value="Inactive")
        self.mining_rewards_var = tk.StringVar(value="0.0")
        self.wallet_address_var = tk.StringVar(value="Not set")
        self.mining_pool_var = tk.StringVar(value="Not set")
        
        # Create frame layout
        self.setup_ui()
        
        # Register event handlers
        self.register_event_handlers()
        
        logger.info(f"{self.name} initialized successfully")
    
    def setup_ui(self) -> None:
        """
        Set up the UI components of the Mining Frame.
        """
        # Main container for the mining frame
        self.main_container = ttk.Frame(self)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create header
        self.create_header()
        
        # Create mining control panel
        self.create_control_panel()
        
        # Create mining stats panel
        self.create_stats_panel()
        
        # Create mining devices panel
        self.create_devices_panel()
        
        # Create mining logs panel
        self.create_logs_panel()
    
    def create_header(self) -> None:
        """
        Create the header section with title and description
        """
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(
            header_frame, 
            text="Mining Dashboard", 
            font=("Arial", 16, "bold")
        )
        title_label.pack(anchor=tk.W)
        
        description_label = ttk.Label(
            header_frame,
            text="Monitor and control crypto mining operations",
            font=("Arial", 10)
        )
        description_label.pack(anchor=tk.W)
        
        # Add horizontal separator
        separator = ttk.Separator(self.main_container, orient="horizontal")
        separator.pack(fill=tk.X, pady=5)
    
    def create_control_panel(self) -> None:
        """
        Create the mining control panel with start/stop buttons and configuration options
        """
        control_frame = ttk.LabelFrame(self.main_container, text="Mining Controls")
        control_frame.pack(fill=tk.X, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Start mining button
        self.start_button = ttk.Button(
            button_frame,
            text="Start Mining",
            command=self.start_mining
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # Stop mining button
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Mining",
            command=self.stop_mining,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Status indicator
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            status_frame, 
            textvariable=self.mining_status_var,
            foreground="red"
        ).pack(side=tk.LEFT, padx=5)
        
        # Configuration frame
        config_frame = ttk.Frame(control_frame)
        config_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Wallet address configuration
        wallet_frame = ttk.Frame(config_frame)
        wallet_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(wallet_frame, text="Wallet Address:").pack(side=tk.LEFT, padx=5)
        self.wallet_entry = ttk.Entry(wallet_frame, width=40)
        self.wallet_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.wallet_entry.insert(0, self.wallet_address)
        
        wallet_button = ttk.Button(
            wallet_frame, 
            text="Update", 
            command=self.update_wallet
        )
        wallet_button.pack(side=tk.LEFT, padx=5)
        
        # Mining pool configuration
        pool_frame = ttk.Frame(config_frame)
        pool_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(pool_frame, text="Mining Pool:").pack(side=tk.LEFT, padx=5)
        self.pool_entry = ttk.Entry(pool_frame, width=40)
        self.pool_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.pool_entry.insert(0, self.mining_pool)
        
        pool_button = ttk.Button(
            pool_frame, 
            text="Update", 
            command=self.update_pool
        )
        pool_button.pack(side=tk.LEFT, padx=5)
    
    def create_stats_panel(self) -> None:
        """
        Create the mining statistics panel showing hashrate, shares, and rewards
        """
        stats_frame = ttk.LabelFrame(self.main_container, text="Mining Statistics")
        stats_frame.pack(fill=tk.X, pady=5)
        
        # Create columns for stats
        stats_container = ttk.Frame(stats_frame)
        stats_container.pack(fill=tk.X, padx=10, pady=10)
        
        # Configure grid columns
        stats_container.columnconfigure(0, weight=1)
        stats_container.columnconfigure(1, weight=1)
        stats_container.columnconfigure(2, weight=1)
        
        # Hashrate display
        hashrate_frame = ttk.Frame(stats_container)
        hashrate_frame.grid(row=0, column=0, padx=10, sticky=tk.W+tk.E)
        
        ttk.Label(
            hashrate_frame, 
            text="Hashrate", 
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.CENTER)
        
        ttk.Label(
            hashrate_frame, 
            textvariable=self.hashrate_var,
            font=("Arial", 14)
        ).pack(anchor=tk.CENTER, pady=5)
        
        # Shares display
        shares_frame = ttk.Frame(stats_container)
        shares_frame.grid(row=0, column=1, padx=10, sticky=tk.W+tk.E)
        
        ttk.Label(
            shares_frame, 
            text="Shares (Accepted/Rejected)", 
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.CENTER)
        
        shares_display = ttk.Frame(shares_frame)
        shares_display.pack(anchor=tk.CENTER, pady=5)
        
        ttk.Label(
            shares_display, 
            textvariable=self.shares_accepted_var,
            font=("Arial", 14),
            foreground="green"
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            shares_display, 
            text=" / ",
            font=("Arial", 14)
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            shares_display, 
            textvariable=self.shares_rejected_var,
            font=("Arial", 14),
            foreground="red"
        ).pack(side=tk.LEFT)
        
        # Rewards display
        rewards_frame = ttk.Frame(stats_container)
        rewards_frame.grid(row=0, column=2, padx=10, sticky=tk.W+tk.E)
        
        ttk.Label(
            rewards_frame, 
            text="Estimated Rewards", 
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.CENTER)
        
        ttk.Label(
            rewards_frame, 
            textvariable=self.mining_rewards_var,
            font=("Arial", 14)
        ).pack(anchor=tk.CENTER, pady=5)
        
        # Add cryptocurrency unit label
        ttk.Label(
            rewards_frame, 
            text="BTC",
            font=("Arial", 8)
        ).pack(anchor=tk.CENTER)
    
    def create_devices_panel(self) -> None:
        """
        Create the mining devices panel showing all connected devices and their stats
        """
        devices_frame = ttk.LabelFrame(self.main_container, text="Mining Devices")
        devices_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create a frame for the devices list
        devices_container = ttk.Frame(devices_frame)
        devices_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create treeview for devices
        columns = ("device", "hashrate", "temp", "efficiency", "status")
        self.devices_tree = ttk.Treeview(devices_container, columns=columns, show="headings", height=5)
        
        # Define column headings
        self.devices_tree.heading("device", text="Device")
        self.devices_tree.heading("hashrate", text="Hashrate")
        self.devices_tree.heading("temp", text="Temperature")
        self.devices_tree.heading("efficiency", text="Efficiency")
        self.devices_tree.heading("status", text="Status")
        
        # Define column widths
        self.devices_tree.column("device", width=200)
        self.devices_tree.column("hashrate", width=100)
        self.devices_tree.column("temp", width=100)
        self.devices_tree.column("efficiency", width=100)
        self.devices_tree.column("status", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(devices_container, orient=tk.VERTICAL, command=self.devices_tree.yview)
        self.devices_tree.configure(yscroll=scrollbar.set)
        
        # Pack widgets
        self.devices_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add refresh button
        refresh_frame = ttk.Frame(devices_frame)
        refresh_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        refresh_button = ttk.Button(
            refresh_frame,
            text="Refresh Devices",
            command=self.refresh_devices
        )
        refresh_button.pack(side=tk.RIGHT)
    
    def create_logs_panel(self) -> None:
        """
        Create the mining logs panel showing mining activity logs
        """
        logs_frame = ttk.LabelFrame(self.main_container, text="Mining Logs")
        logs_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create text widget for logs
        self.logs_text = scrolledtext.ScrolledText(
            logs_frame,
            wrap=tk.WORD,
            height=5,
            width=50,
            font=("Courier", 9)
        )
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.logs_text.config(state=tk.DISABLED)
        
        # Add clear button
        clear_frame = ttk.Frame(logs_frame)
        clear_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        clear_button = ttk.Button(
            clear_frame,
            text="Clear Logs",
            command=self.clear_logs
        )
        clear_button.pack(side=tk.RIGHT)
    
    def register_event_handlers(self) -> None:
        """
        Register event handlers for mining events
        """
        self.event_bus.subscribe("mining.status", self.handle_mining_status)
        self.event_bus.subscribe("mining.hashrate", self.handle_hashrate_update)
        self.event_bus.subscribe("mining.shares", self.handle_shares_update)
        self.event_bus.subscribe("mining.devices", self.handle_devices_update)
        self.event_bus.subscribe("mining.rewards", self.handle_rewards_update)
        self.event_bus.subscribe("mining.temperature", self.handle_temperature_update)
        self.event_bus.subscribe("mining.efficiency", self.handle_efficiency_update)
        self.event_bus.subscribe("mining.log", self.handle_log_update)
    
    def start_mining(self) -> None:
        """
        Start the mining process
        """
        if self.mining_active:
            messagebox.showinfo("Mining", "Mining is already active")
            return
        
        # Validate wallet address and pool
        if not self.wallet_address:
            messagebox.showwarning("Mining", "Please set a wallet address before starting mining")
            return
        
        if not self.mining_pool:
            messagebox.showwarning("Mining", "Please set a mining pool before starting mining")
            return
        
        # Update UI
        self.mining_status_var.set("Starting...")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Add log entry
        self.add_log_entry(f"Starting mining with pool: {self.mining_pool}")
        
        # Send start mining event
        self.event_bus.publish("mining.command", {
            "command": "start",
            "wallet": self.wallet_address,
            "pool": self.mining_pool,
            "credentials": self.pool_credentials
        })
        
        # Update state
        self.mining_active = True
        self.mining_status_var.set("Active")
        
        logger.info(f"Mining started with pool: {self.mining_pool}")
    
    def stop_mining(self) -> None:
        """
        Stop the mining process
        """
        if not self.mining_active:
            messagebox.showinfo("Mining", "Mining is not active")
            return
        
        # Update UI
        self.mining_status_var.set("Stopping...")
        self.stop_button.config(state=tk.DISABLED)
        
        # Add log entry
        self.add_log_entry("Stopping mining operation")
        
        # Send stop mining event
        self.event_bus.publish("mining.command", {
            "command": "stop"
        })
        
        # Update state
        self.mining_active = False
        self.mining_status_var.set("Inactive")
        self.start_button.config(state=tk.NORMAL)
        
        logger.info("Mining stopped")
    
    def update_wallet(self) -> None:
        """
        Update the wallet address
        """
        new_wallet = self.wallet_entry.get().strip()
        
        if not new_wallet:
            messagebox.showwarning("Wallet", "Please enter a valid wallet address")
            return
        
        self.wallet_address = new_wallet
        self.wallet_address_var.set(new_wallet)
        
        # Add log entry
        self.add_log_entry(f"Wallet address updated: {self.wallet_address}")
        
        logger.info(f"Wallet address updated: {self.wallet_address}")
    
    def update_pool(self) -> None:
        """
        Update the mining pool
        """
        new_pool = self.pool_entry.get().strip()
        
        if not new_pool:
            messagebox.showwarning("Pool", "Please enter a valid mining pool")
            return
        
        self.mining_pool = new_pool
        self.mining_pool_var.set(new_pool)
        
        # Add log entry
        self.add_log_entry(f"Mining pool updated: {self.mining_pool}")
        
        logger.info(f"Mining pool updated: {self.mining_pool}")
    
    def refresh_devices(self) -> None:
        """
        Refresh the list of mining devices
        """
        # Send refresh devices event
        self.event_bus.publish("mining.command", {
            "command": "refresh_devices"
        })
        
        # Add log entry
        self.add_log_entry("Refreshing mining devices")
        
        logger.info("Refreshing mining devices")
    
    def clear_logs(self) -> None:
        """
        Clear the mining logs
        """
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.delete(1.0, tk.END)
        self.logs_text.config(state=tk.DISABLED)
        self.mining_logs = []
        
        logger.info("Mining logs cleared")
    
    def add_log_entry(self, message: str) -> None:
        """
        Add a new entry to the mining logs
        
        Args:
            message: The log message to add
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # Add to logs list
        self.mining_logs.append(log_entry)
        
        # Update text widget
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.insert(tk.END, log_entry)
        self.logs_text.see(tk.END)
        self.logs_text.config(state=tk.DISABLED)
    
    def update_device_list(self) -> None:
        """
        Update the mining devices treeview with current devices
        """
        # Clear existing items
        for item in self.devices_tree.get_children():
            self.devices_tree.delete(item)
        
        # Add devices to treeview
        for device in self.mining_devices:
            device_id = device.get("id", "unknown")
            hashrate = f"{device.get('hashrate', 0)} H/s"
            temperature = f"{device.get('temperature', 0)}°C"
            efficiency = f"{device.get('efficiency', 0)} H/W"
            status = device.get("status", "Unknown")
            
            # Set status color
            if status.lower() == "active":
                status_tag = "active"
            elif status.lower() == "idle":
                status_tag = "idle"
            else:
                status_tag = "error"
            
            # Insert into treeview
            self.devices_tree.insert("", tk.END, values=(device_id, hashrate, temperature, efficiency, status), tags=(status_tag,))
        
        # Configure tag colors
        self.devices_tree.tag_configure("active", foreground="green")
        self.devices_tree.tag_configure("idle", foreground="orange")
        self.devices_tree.tag_configure("error", foreground="red")
    
    def handle_mining_status(self, event_data: Dict[str, Any]) -> None:
        """
        Handle mining status events
        
        Args:
            event_data: The event data containing mining status information
        """
        status = event_data.get("status", "Unknown")
        
        # Update status variable
        self.mining_status_var.set(status)
        
        # Update buttons based on status
        if status.lower() == "active":
            self.mining_active = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.mining_active = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
        
        # Add log entry
        self.add_log_entry(f"Mining status changed to: {status}")
        
        logger.info(f"Mining status changed to: {status}")
    
    def handle_hashrate_update(self, event_data: Dict[str, Any]) -> None:
        """
        Handle hashrate update events
        
        Args:
            event_data: The event data containing hashrate information
        """
        hashrate = event_data.get("hashrate", 0)
        
        # Update hashrate variable
        self.hashrate = hashrate
        
        # Format hashrate for display
        if hashrate >= 1000000:
            formatted_hashrate = f"{hashrate/1000000:.2f} MH/s"
        elif hashrate >= 1000:
            formatted_hashrate = f"{hashrate/1000:.2f} kH/s"
        else:
            formatted_hashrate = f"{hashrate:.2f} H/s"
        
        self.hashrate_var.set(formatted_hashrate)
        
        # Add log entry if significant change
        logger.debug(f"Hashrate updated: {formatted_hashrate}")
    
    def handle_shares_update(self, event_data: Dict[str, Any]) -> None:
        """
        Handle shares update events
        
        Args:
            event_data: The event data containing shares information
        """
        accepted = event_data.get("accepted", 0)
        rejected = event_data.get("rejected", 0)
        
        # Update shares variables
        self.shares_accepted = accepted
        self.shares_rejected = rejected
        
        # Update displayed values
        self.shares_accepted_var.set(str(accepted))
        self.shares_rejected_var.set(str(rejected))
        
        # Add log entry for rejected shares
        if "new_rejected" in event_data and event_data["new_rejected"]:
            self.add_log_entry(f"Share rejected: {event_data.get('reason', 'Unknown reason')}")
        
        logger.debug(f"Shares updated: {accepted} accepted, {rejected} rejected")
    
    def handle_devices_update(self, event_data: Dict[str, Any]) -> None:
        """
        Handle devices update events
        
        Args:
            event_data: The event data containing devices information
        """
        devices = event_data.get("devices", [])
        
        # Update devices list
        self.mining_devices = devices
        
        # Update the devices treeview
        self.update_device_list()
        
        # Log the update
        logger.debug(f"Devices updated: {len(devices)} devices")
    
    def handle_rewards_update(self, event_data: Dict[str, Any]) -> None:
        """
        Handle rewards update events
        
        Args:
            event_data: The event data containing rewards information
        """
        rewards = event_data.get("rewards", 0.0)
        
        # Update rewards variable
        self.mining_rewards = rewards
        
        # Update displayed value (formatted to 8 decimal places for BTC)
        self.mining_rewards_var.set(f"{rewards:.8f}")
        
        logger.debug(f"Rewards updated: {rewards:.8f} BTC")
    
    def handle_temperature_update(self, event_data: Dict[str, Any]) -> None:
        """
        Handle temperature update events
        
        Args:
            event_data: The event data containing temperature information
        """
        device_id = event_data.get("device_id", "unknown")
        temperature = event_data.get("temperature", 0)
        
        # Update temperature data
        self.temperature_data[device_id] = temperature
        
        # Add log entry for high temperature
        if temperature > 80:
            self.add_log_entry(f"WARNING: High temperature ({temperature}°C) detected on device {device_id}")
        
        # Update device list to reflect new temperature
        self.update_device_list()
        
        logger.debug(f"Temperature updated for device {device_id}: {temperature}°C")
    
    def handle_efficiency_update(self, event_data: Dict[str, Any]) -> None:
        """
        Handle efficiency update events
        
        Args:
            event_data: The event data containing efficiency information
        """
        device_id = event_data.get("device_id", "unknown")
        efficiency = event_data.get("efficiency", 0)
        
        # Update efficiency data
        self.efficiency_data[device_id] = efficiency
        
        # Update device list to reflect new efficiency
        self.update_device_list()
        
        logger.debug(f"Efficiency updated for device {device_id}: {efficiency} H/W")
    
    def handle_log_update(self, event_data: Dict[str, Any]) -> None:
        """
        Handle log update events
        
        Args:
            event_data: The event data containing log information
        """
        message = event_data.get("message", "")
        level = event_data.get("level", "info")
        
        # Add to logs
        self.add_log_entry(f"[{level.upper()}] {message}")
        
        # Log based on level
        if level.lower() == "error":
            logger.error(message)
        elif level.lower() == "warning":
            logger.warning(message)
        else:
            logger.info(message)
