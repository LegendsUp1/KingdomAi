#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Wallet Event Handlers Module
Contains implementation of wallet event handlers for TabManager
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger("KingdomAI.WalletHandlers")

# Wallet event handler methods
async def update_wallet_status(self, event_type: str, event_data: Dict[str, Any]):
    """Update wallet status display when wallet.status events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing wallet status information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty wallet status data")
            return
            
        # Update wallet status
        if 'status' in event_data:
            self.wallet_status = event_data['status']
            self.wallet_data['status'] = self.wallet_status
            
        # Update wallet status display if wallet tab is present
        if 'wallet' in self.tab_frames:
            wallet_frame = self.tab_frames['wallet']
            
            # Update status label if it exists
            if hasattr(wallet_frame, 'status_label'):
                if self.using_pyqt:
                    wallet_frame.status_label.setText(f"Wallet Status: {self.wallet_status}")
                elif self.using_tkinter:
                    wallet_frame.status_label.config(text=f"Wallet Status: {self.wallet_status}")
            
            # Update connection indicator if it exists
            if hasattr(wallet_frame, 'connection_indicator'):
                if self.wallet_status == "connected":
                    indicator_color = "green"
                elif self.wallet_status == "connecting":
                    indicator_color = "yellow"
                else:
                    indicator_color = "red"
                    
                if self.using_pyqt:
                    wallet_frame.connection_indicator.setStyleSheet(f"background-color: {indicator_color};")
                elif self.using_tkinter:
                    wallet_frame.connection_indicator.config(bg=indicator_color)
                    
        self.logger.debug(f"Updated wallet status: {self.wallet_status}")
    except Exception as e:
        self.logger.error(f"Error updating wallet status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_wallet_balances(self, event_type: str, event_data: Dict[str, Any]):
    """Update wallet balance display when wallet.balances events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing wallet balance information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty wallet balance data")
            return
            
        # Update wallet balances
        if 'balances' in event_data:
            self.wallet_balances = event_data['balances']
            self.wallet_data['balances'] = self.wallet_balances
            
        # Update wallet balance display if wallet tab is present
        if 'wallet' in self.tab_frames:
            wallet_frame = self.tab_frames['wallet']
            
            # Update balance list if it exists
            if hasattr(wallet_frame, 'balance_list'):
                if self.using_pyqt:
                    # Clear and update list
                    wallet_frame.balance_list.clear()
                    for currency, balance in self.wallet_balances.items():
                        # Format balance based on currency type
                        if currency.upper() in ["BTC", "BCH", "ETH", "LTC"]:
                            formatted_balance = f"{balance:.8f}"
                        else:
                            formatted_balance = f"{balance:.2f}"
                            
                        wallet_frame.balance_list.addItem(f"{currency.upper()}: {formatted_balance}")
                elif self.using_tkinter:
                    # Clear and update listbox
                    wallet_frame.balance_list.delete(0, 'end')
                    for currency, balance in self.wallet_balances.items():
                        # Format balance based on currency type
                        if currency.upper() in ["BTC", "BCH", "ETH", "LTC"]:
                            formatted_balance = f"{balance:.8f}"
                        else:
                            formatted_balance = f"{balance:.2f}"
                            
                        wallet_frame.balance_list.insert('end', f"{currency.upper()}: {formatted_balance}")
            
            # Update total balance display if it exists
            if hasattr(wallet_frame, 'total_balance_label'):
                # Calculate total USD equivalent if available
                total_usd = self.wallet_balances.get('usd', 0)
                
                if self.using_pyqt:
                    wallet_frame.total_balance_label.setText(f"Total Value (USD): ${total_usd:.2f}")
                elif self.using_tkinter:
                    wallet_frame.total_balance_label.config(text=f"Total Value (USD): ${total_usd:.2f}")
                    
        self.logger.debug(f"Updated wallet balances for {len(self.wallet_balances) if self.wallet_balances else 0} currencies")
    except Exception as e:
        self.logger.error(f"Error updating wallet balances: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_transaction_history(self, event_type: str, event_data: Dict[str, Any]):
    """Update transaction history display when wallet.transactions events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing transaction history
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty transaction history data")
            return
            
        # Update transaction history
        if 'transactions' in event_data:
            self.transaction_history = event_data['transactions']
            self.wallet_data['transactions'] = self.transaction_history
            
        # Update transaction history display if wallet tab is present
        if 'wallet' in self.tab_frames:
            wallet_frame = self.tab_frames['wallet']
            
            # Update transaction history list if it exists
            if hasattr(wallet_frame, 'transaction_list'):
                if self.using_pyqt:
                    # Clear and update list
                    wallet_frame.transaction_list.clear()
                    for tx in self.transaction_history:
                        # Format transaction details
                        tx_id = tx.get('id', 'Unknown')
                        tx_type = tx.get('type', 'Unknown')
                        currency = tx.get('currency', 'Unknown')
                        amount = tx.get('amount', 0)
                        timestamp = tx.get('timestamp', 'Unknown')
                        status = tx.get('status', 'Unknown')
                        
                        # Format amount based on currency type
                        if currency.upper() in ["BTC", "BCH", "ETH", "LTC"]:
                            formatted_amount = f"{amount:.8f}"
                        else:
                            formatted_amount = f"{amount:.2f}"
                            
                        display = f"[{timestamp}] {tx_type} {formatted_amount} {currency.upper()} - {status}"
                        wallet_frame.transaction_list.addItem(display)
                elif self.using_tkinter:
                    # Clear and update listbox
                    wallet_frame.transaction_list.delete(0, 'end')
                    for tx in self.transaction_history:
                        # Format transaction details
                        tx_id = tx.get('id', 'Unknown')
                        tx_type = tx.get('type', 'Unknown')
                        currency = tx.get('currency', 'Unknown')
                        amount = tx.get('amount', 0)
                        timestamp = tx.get('timestamp', 'Unknown')
                        status = tx.get('status', 'Unknown')
                        
                        # Format amount based on currency type
                        if currency.upper() in ["BTC", "BCH", "ETH", "LTC"]:
                            formatted_amount = f"{amount:.8f}"
                        else:
                            formatted_amount = f"{amount:.2f}"
                            
                        display = f"[{timestamp}] {tx_type} {formatted_amount} {currency.upper()} - {status}"
                        wallet_frame.transaction_list.insert('end', display)
                        
        self.logger.debug(f"Updated transaction history with {len(self.transaction_history) if self.transaction_history else 0} transactions")
    except Exception as e:
        self.logger.error(f"Error updating transaction history: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_wallet_addresses(self, event_type: str, event_data: Dict[str, Any]):
    """Update wallet addresses display when wallet.addresses events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing wallet addresses
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty wallet addresses data")
            return
            
        # Update wallet addresses
        if 'addresses' in event_data:
            addresses = event_data['addresses']
            self.wallet_data['addresses'] = addresses
            
        # Update wallet addresses display if wallet tab is present
        if 'wallet' in self.tab_frames:
            wallet_frame = self.tab_frames['wallet']
            
            # Update address list if it exists
            if hasattr(wallet_frame, 'address_list'):
                if self.using_pyqt:
                    # Clear and update list
                    wallet_frame.address_list.clear()
                    for entry in addresses:
                        currency = entry.get('currency', 'Unknown')
                        address = entry.get('address', 'Unknown')
                        
                        wallet_frame.address_list.addItem(f"{currency.upper()}: {address}")
                elif self.using_tkinter:
                    # Clear and update listbox
                    wallet_frame.address_list.delete(0, 'end')
                    for entry in addresses:
                        currency = entry.get('currency', 'Unknown')
                        address = entry.get('address', 'Unknown')
                        
                        wallet_frame.address_list.insert('end', f"{currency.upper()}: {address}")
                        
        self.logger.debug(f"Updated wallet addresses with {len(addresses) if addresses else 0} addresses")
    except Exception as e:
        self.logger.error(f"Error updating wallet addresses: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

# Tab-specific initialization methods
async def request_wallet_data(self):
    """Request wallet data updates from the backend."""
    try:
        self.logger.info("Requesting wallet data")
        
        # Update wallet status
        self.wallet_status = "connecting"
        
        # Connect to Redis Quantum Nexus on required port and password
        if hasattr(self, 'redis_client'):
            try:
                # Ensure Redis connection uses port 6380 with QuantumNexus2025 password
                await self.redis_client.initialize(
                    host="localhost",
                    port=6380,
                    password="QuantumNexus2025",
                    environment="wallet"
                )
                self.logger.info("Connected to Redis Quantum Nexus on port 6380 for wallet data")
            except Exception as redis_error:
                self.logger.error(f"Failed to connect to Redis Quantum Nexus: {redis_error}")
                self.wallet_status = "disconnected"
                return False
        
        # Request wallet data
        if self.event_bus:
            await self.event_bus.emit("request_wallet_status")
            await self.event_bus.emit("request_wallet_balances")
            await self.event_bus.emit("request_transaction_history")
            await self.event_bus.emit("request_wallet_addresses")
            
        self.wallet_status = "connected"
        return True
    except Exception as e:
        self.logger.error(f"Error requesting wallet data: {e}")
        self.wallet_status = "error"
        import traceback
        self.logger.error(traceback.format_exc())
        return False
