#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Trading Event Handlers Module
Contains implementation of trading event handlers for TabManager
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger("KingdomAI.TradingHandlers")

# Trading event handler methods
async def update_price_display(self, event_type: str, event_data: Dict[str, Any]):
    """Update price display when trading.market_data events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing market price information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty market data")
            return
            
        # Update trading data with latest prices
        if 'prices' in event_data:
            self.current_prices = event_data['prices']
            self.trading_data['current_prices'] = self.current_prices
            
        # Update price displays if trading tab is present
        if 'trading' in self.tab_frames:
            trading_frame = self.tab_frames['trading']
            
            # Update price labels if they exist
            if hasattr(trading_frame, 'price_widgets'):
                for symbol, price_widget in trading_frame.price_widgets.items():
                    if symbol in self.current_prices:
                        price = self.current_prices[symbol]
                        if self.using_pyqt:
                            price_widget.setText(f"{symbol}: ${price:.2f}")
                        elif self.using_tkinter:
                            price_widget.config(text=f"{symbol}: ${price:.2f}")
        
        self.logger.debug(f"Updated prices for {len(self.current_prices) if self.current_prices else 0} symbols")
    except Exception as e:
        self.logger.error(f"Error updating price display: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_order_status(self, event_type: str, event_data: Dict[str, Any]):
    """Update order status display when trading.order_status events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing order status information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty order status data")
            return
            
        # Add order to history if it's a new or updated order
        if 'order' in event_data:
            order = event_data['order']
            # Check if order already exists in history
            order_id = order.get('id')
            existing = False
            for i, existing_order in enumerate(self.order_history):
                if existing_order.get('id') == order_id:
                    # Update existing order
                    self.order_history[i] = order
                    existing = True
                    break
            
            if not existing:
                # Add new order to history
                self.order_history.append(order)
                # Limit history size
                if len(self.order_history) > 100:
                    self.order_history = self.order_history[-100:]
            
            # Store in trading data
            self.trading_data['order_history'] = self.order_history
            
        # Update order display if trading tab is present
        if 'trading' in self.tab_frames:
            trading_frame = self.tab_frames['trading']
            
            # Update order history display if it exists
            if hasattr(trading_frame, 'order_list'):
                if self.using_pyqt:
                    # Clear and update list
                    trading_frame.order_list.clear()
                    for order in self.order_history:
                        # Format order details
                        symbol = order.get('symbol', 'Unknown')
                        side = order.get('side', 'Unknown')
                        status = order.get('status', 'Unknown')
                        quantity = order.get('quantity', 0)
                        price = order.get('price', 0)
                        
                        # Create display string
                        display = f"{symbol} - {side} {quantity} @ ${price:.2f} - {status}"
                        trading_frame.order_list.addItem(display)
                elif self.using_tkinter:
                    # Clear and update listbox
                    trading_frame.order_list.delete(0, 'end')
                    for order in self.order_history:
                        # Format order details
                        symbol = order.get('symbol', 'Unknown')
                        side = order.get('side', 'Unknown')
                        status = order.get('status', 'Unknown')
                        quantity = order.get('quantity', 0)
                        price = order.get('price', 0)
                        
                        # Create display string
                        display = f"{symbol} - {side} {quantity} @ ${price:.2f} - {status}"
                        trading_frame.order_list.insert('end', display)
                        
        self.logger.debug(f"Updated order status display with {len(self.order_history)} orders")
    except Exception as e:
        self.logger.error(f"Error updating order status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_portfolio_display(self, event_type: str, event_data: Dict[str, Any]):
    """Update portfolio display when trading.portfolio events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing portfolio information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty portfolio data")
            return
            
        # Update portfolio data
        if 'portfolio' in event_data:
            self.portfolio_data = event_data['portfolio']
            self.trading_data['portfolio'] = self.portfolio_data
            
        # Update portfolio display if trading tab is present
        if 'trading' in self.tab_frames:
            trading_frame = self.tab_frames['trading']
            
            # Update portfolio display if it exists
            if hasattr(trading_frame, 'portfolio_list'):
                portfolio = self.portfolio_data.get('holdings', {})
                
                if self.using_pyqt:
                    # Clear and update list
                    trading_frame.portfolio_list.clear()
                    # Add balance
                    balance = self.portfolio_data.get('balance', 0)
                    trading_frame.portfolio_list.addItem(f"Cash Balance: ${balance:.2f}")
                    
                    # Add holdings
                    for symbol, holding in portfolio.items():
                        quantity = holding.get('quantity', 0)
                        value = holding.get('value', 0)
                        avg_price = holding.get('avg_price', 0)
                        
                        display = f"{symbol}: {quantity} shares @ ${avg_price:.2f} (${value:.2f})"
                        trading_frame.portfolio_list.addItem(display)
                elif self.using_tkinter:
                    # Clear and update listbox
                    trading_frame.portfolio_list.delete(0, 'end')
                    # Add balance
                    balance = self.portfolio_data.get('balance', 0)
                    trading_frame.portfolio_list.insert('end', f"Cash Balance: ${balance:.2f}")
                    
                    # Add holdings
                    for symbol, holding in portfolio.items():
                        quantity = holding.get('quantity', 0)
                        value = holding.get('value', 0)
                        avg_price = holding.get('avg_price', 0)
                        
                        display = f"{symbol}: {quantity} shares @ ${avg_price:.2f} (${value:.2f})"
                        trading_frame.portfolio_list.insert('end', display)
                        
            # Update total value display if it exists
            if hasattr(trading_frame, 'total_value_label'):
                total_value = self.portfolio_data.get('total_value', 0)
                
                if self.using_pyqt:
                    trading_frame.total_value_label.setText(f"Total Portfolio Value: ${total_value:.2f}")
                elif self.using_tkinter:
                    trading_frame.total_value_label.config(text=f"Total Portfolio Value: ${total_value:.2f}")
                    
        self.logger.debug("Updated portfolio display")
    except Exception as e:
        self.logger.error(f"Error updating portfolio display: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_transaction_history(self, event_type: str, event_data: Dict[str, Any]):
    """Update transaction history display when trading.transaction events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing transaction information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty transaction data")
            return
            
        # Add transaction to history if it's a new transaction
        if 'transaction' in event_data:
            transaction = event_data['transaction']
            self.transaction_history.append(transaction)
            # Limit history size
            if len(self.transaction_history) > 100:
                self.transaction_history = self.transaction_history[-100:]
            
            # Store in trading data
            self.trading_data['transaction_history'] = self.transaction_history
            
        # Update transaction display if trading tab is present
        if 'trading' in self.tab_frames:
            trading_frame = self.tab_frames['trading']
            
            # Update transaction history display if it exists
            if hasattr(trading_frame, 'transaction_list'):
                if self.using_pyqt:
                    # Clear and update list
                    trading_frame.transaction_list.clear()
                    for txn in self.transaction_history:
                        # Format transaction details
                        symbol = txn.get('symbol', 'Unknown')
                        action = txn.get('action', 'Unknown')
                        quantity = txn.get('quantity', 0)
                        price = txn.get('price', 0)
                        timestamp = txn.get('timestamp', 'Unknown')
                        
                        # Create display string
                        display = f"{timestamp} - {action} {quantity} {symbol} @ ${price:.2f}"
                        trading_frame.transaction_list.addItem(display)
                elif self.using_tkinter:
                    # Clear and update listbox
                    trading_frame.transaction_list.delete(0, 'end')
                    for txn in self.transaction_history:
                        # Format transaction details
                        symbol = txn.get('symbol', 'Unknown')
                        action = txn.get('action', 'Unknown')
                        quantity = txn.get('quantity', 0)
                        price = txn.get('price', 0)
                        timestamp = txn.get('timestamp', 'Unknown')
                        
                        # Create display string
                        display = f"{timestamp} - {action} {quantity} {symbol} @ ${price:.2f}"
                        trading_frame.transaction_list.insert('end', display)
                        
        self.logger.debug(f"Updated transaction history display with {len(self.transaction_history)} transactions")
    except Exception as e:
        self.logger.error(f"Error updating transaction history: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_trading_status(self, event_type: str, event_data: Dict[str, Any]):
    """Update trading status display when trading.status events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing trading status information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty trading status data")
            return
            
        # Update trading status
        if 'status' in event_data:
            self.trading_status = event_data['status']
            self.trading_data['status'] = self.trading_status
            
        # Update trading status display if trading tab is present
        if 'trading' in self.tab_frames:
            trading_frame = self.tab_frames['trading']
            
            # Update status label if it exists
            if hasattr(trading_frame, 'status_label'):
                if self.using_pyqt:
                    trading_frame.status_label.setText(f"Trading Status: {self.trading_status}")
                elif self.using_tkinter:
                    trading_frame.status_label.config(text=f"Trading Status: {self.trading_status}")
                    
            # Update trading buttons based on status
            if hasattr(trading_frame, 'start_button') and hasattr(trading_frame, 'stop_button'):
                if self.trading_status == "active":
                    # Trading is active, enable stop button, disable start button
                    if self.using_pyqt:
                        trading_frame.start_button.setEnabled(False)
                        trading_frame.stop_button.setEnabled(True)
                    elif self.using_tkinter:
                        trading_frame.start_button.config(state='disabled')
                        trading_frame.stop_button.config(state='normal')
                else:
                    # Trading is inactive, enable start button, disable stop button
                    if self.using_pyqt:
                        trading_frame.start_button.setEnabled(True)
                        trading_frame.stop_button.setEnabled(False)
                    elif self.using_tkinter:
                        trading_frame.start_button.config(state='normal')
                        trading_frame.stop_button.config(state='disabled')
                        
        self.logger.debug(f"Updated trading status: {self.trading_status}")
    except Exception as e:
        self.logger.error(f"Error updating trading status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

# Tab-specific initialization methods
async def refresh_dashboard(self):
    """Refresh all dashboard components with latest data."""
    try:
        self.logger.info("Refreshing dashboard data")
        
        # Update system status
        if self.event_bus:
            await self.event_bus.emit("request_system_status")
            await self.event_bus.emit("request_performance_metrics")
            await self.event_bus.emit("request_recent_activity")
            await self.event_bus.emit("request_resource_metrics")
            
        return True
    except Exception as e:
        self.logger.error(f"Error refreshing dashboard: {e}")
        import traceback
        self.logger.error(traceback.format_exc())
        return False

async def connect_to_markets(self):
    """Connect to trading markets and initialize data feeds."""
    try:
        self.logger.info("Connecting to trading markets")
        
        # Update trading status
        self.trading_status = "connecting"
        
        # Connect to Redis Quantum Nexus on required port and password
        if hasattr(self, 'redis_client'):
            try:
                # Ensure Redis connection uses port 6380 with QuantumNexus2025 password
                await self.redis_client.initialize(
                    host="localhost",
                    port=6380,
                    password="QuantumNexus2025",
                    environment="trading"
                )
                self.logger.info("Connected to Redis Quantum Nexus on port 6380")
            except Exception as redis_error:
                self.logger.error(f"Failed to connect to Redis Quantum Nexus: {redis_error}")
                self.trading_status = "disconnected"
                return False
        
        # Request market data
        if self.event_bus:
            await self.event_bus.emit("request_market_data")
            
        self.trading_status = "connected"
        return True
    except Exception as e:
        self.logger.error(f"Error connecting to markets: {e}")
        self.trading_status = "error"
        import traceback
        self.logger.error(traceback.format_exc())
        return False
