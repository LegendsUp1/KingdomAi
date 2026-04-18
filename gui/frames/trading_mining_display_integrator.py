#!/usr/bin/env python3
"""
Trading and Mining Display Integrator for Kingdom AI GUI

This module enhances the Trading and Mining frames to properly display
data from the Redis Quantum Nexus, ensuring the dashboard shows live data.
"""

import asyncio
import logging
import time
import tkinter as tk
from tkinter import ttk
import traceback
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

# Set up logging
logger = logging.getLogger("KingdomAI.GUI.DisplayIntegrator")

class TradingMiningDisplayIntegrator:
    """
    Integrates the Trading and Mining frames with data from the Redis Quantum Nexus.
    Ensures the dashboard displays real-time data from the trading and mining systems.
    """
    
    def __init__(self, event_bus=None, trading_frame=None, mining_frame=None, dashboard_frame=None):
        """
        Initialize the display integrator.
        
        Args:
            event_bus: Event bus for component communication
            trading_frame: Trading frame instance
            mining_frame: Mining frame instance
            dashboard_frame: Dashboard frame instance
        """
        self.event_bus = event_bus
        self.trading_frame = trading_frame
        self.mining_frame = mining_frame
        self.dashboard_frame = dashboard_frame
        self.logger = logger
        self.initialized = False
        self.update_interval = 5  # seconds
        self.running = False
        self.update_task = None
        
        # Data cache
        self.trading_data = {}
        self.mining_data = {}
        
        # GUI update flags
        self.trading_frame_ready = False
        self.mining_frame_ready = False
        self.dashboard_frame_ready = False
        
        # Statistics
        self.stats = {
            "last_trading_update": 0,
            "last_mining_update": 0,
            "total_updates": 0
        }
    
    async def initialize(self):
        """Initialize the display integrator."""
        logger.info("Initializing Trading and Mining Display Integrator...")
        
        try:
            # Subscribe to events
            await self.subscribe_to_events()
            
            # Check if frames are available
            self.trading_frame_ready = self.trading_frame is not None
            self.mining_frame_ready = self.mining_frame is not None
            self.dashboard_frame_ready = self.dashboard_frame is not None
            
            # Request initial data
            if self.event_bus:
                # Request trading data
                logger.info("Requesting initial trading data...")
                try:
                    response = await self.event_bus.request("trading.data.request", {})
                    if response:
                        self.trading_data = response
                        self.stats["last_trading_update"] = time.time()
                        logger.info("Received initial trading data")
                except Exception as e:
                    logger.warning(f"Error requesting initial trading data: {e}")
                
                # Request mining data
                logger.info("Requesting initial mining data...")
                try:
                    response = await self.event_bus.request("mining.data.request", {})
                    if response:
                        self.mining_data = response
                        self.stats["last_mining_update"] = time.time()
                        logger.info("Received initial mining data")
                except Exception as e:
                    logger.warning(f"Error requesting initial mining data: {e}")
            
            # Start update task
            self.running = True
            self.update_task = asyncio.create_task(self.update_frames_task())
            
            self.initialized = True
            logger.info("Trading and Mining Display Integrator initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Trading and Mining Display Integrator: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def subscribe_to_events(self):
        """Subscribe to relevant events."""
        if not self.event_bus:
            logger.warning("No event bus available, cannot subscribe to events")
            return False
        
        try:
            # GUI update events
            await self.event_bus.subscribe("gui.trading.update", self.handle_trading_update)
            await self.event_bus.subscribe("gui.mining.update", self.handle_mining_update)
            await self.event_bus.subscribe("gui.trading.data", self.handle_trading_data)
            await self.event_bus.subscribe("gui.mining.data", self.handle_mining_data)
            
            # System events
            await self.event_bus.subscribe("system.shutdown", self.handle_shutdown)
            
            logger.info("Successfully subscribed to events")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to events: {e}")
            return False
    
    async def update_frames_task(self):
        """Background task to periodically update frames."""
        logger.info("Starting frames update task")
        
        while self.running:
            try:
                # Update trading frame
                if self.trading_frame_ready and self.trading_data:
                    self.update_trading_frame()
                
                # Update mining frame
                if self.mining_frame_ready and self.mining_data:
                    self.update_mining_frame()
                
                # Update dashboard
                if self.dashboard_frame_ready:
                    self.update_dashboard_frame()
                
                # Request fresh data periodically
                if self.event_bus:
                    if time.time() - self.stats["last_trading_update"] > self.update_interval:
                        await self.event_bus.publish("gui.trading.refresh", {})
                    
                    if time.time() - self.stats["last_mining_update"] > self.update_interval:
                        await self.event_bus.publish("gui.mining.refresh", {})
                
                self.stats["total_updates"] += 1
            except Exception as e:
                logger.error(f"Error in frames update task: {e}")
            
            # Wait for next update
            await asyncio.sleep(1)  # Check every second, but only refresh data at update_interval
    
    def update_trading_frame(self):
        """Update the trading frame with current data."""
        try:
            if not self.trading_frame or not hasattr(self.trading_frame, 'update_display'):
                # Try to find standard update methods that might exist
                if hasattr(self.trading_frame, 'update_portfolio'):
                    if 'portfolio' in self.trading_data:
                        self.trading_frame.update_portfolio(self.trading_data['portfolio'])
                
                if hasattr(self.trading_frame, 'update_market_data'):
                    if 'market' in self.trading_data:
                        self.trading_frame.update_market_data(self.trading_data['market'])
                
                if hasattr(self.trading_frame, 'update_status'):
                    self.trading_frame.update_status({
                        'last_update': datetime.fromtimestamp(self.stats["last_trading_update"]).strftime('%Y-%m-%d %H:%M:%S'),
                        'status': 'Connected' if self.trading_data else 'Disconnected'
                    })
            else:
                # Use the unified update method if it exists
                self.trading_frame.update_display(self.trading_data)
            
            logger.debug("Trading frame updated")
        except Exception as e:
            logger.error(f"Error updating trading frame: {e}")
    
    def update_mining_frame(self):
        """Update the mining frame with current data."""
        try:
            if not self.mining_frame or not hasattr(self.mining_frame, 'update_display'):
                # Try to find standard update methods that might exist
                if hasattr(self.mining_frame, 'update_stats'):
                    if 'stats' in self.mining_data:
                        self.mining_frame.update_stats(self.mining_data['stats'])
                
                if hasattr(self.mining_frame, 'update_hardware'):
                    if 'hardware' in self.mining_data:
                        self.mining_frame.update_hardware(self.mining_data['hardware'])
                
                if hasattr(self.mining_frame, 'update_pools'):
                    if 'pools' in self.mining_data:
                        self.mining_frame.update_pools(self.mining_data['pools'])
                
                if hasattr(self.mining_frame, 'update_status'):
                    self.mining_frame.update_status({
                        'last_update': datetime.fromtimestamp(self.stats["last_mining_update"]).strftime('%Y-%m-%d %H:%M:%S'),
                        'status': 'Connected' if self.mining_data else 'Disconnected',
                        'active': self.mining_data.get('active', False)
                    })
            else:
                # Use the unified update method if it exists
                self.mining_frame.update_display(self.mining_data)
            
            logger.debug("Mining frame updated")
        except Exception as e:
            logger.error(f"Error updating mining frame: {e}")
    
    def update_dashboard_frame(self):
        """Update the dashboard frame with summarized data."""
        try:
            if not self.dashboard_frame:
                return
            
            # Create summary data for dashboard
            dashboard_data = {
                'trading': {
                    'status': 'Connected' if self.trading_data else 'Disconnected',
                    'last_update': datetime.fromtimestamp(self.stats["last_trading_update"]).strftime('%Y-%m-%d %H:%M:%S'),
                    'portfolio_value': self.get_portfolio_value(),
                    'active_orders': self.get_active_orders_count()
                },
                'mining': {
                    'status': 'Connected' if self.mining_data else 'Disconnected',
                    'active': self.mining_data.get('active', False),
                    'hashrate': self.get_total_hashrate(),
                    'devices': len(self.mining_data.get('hardware', [])),
                    'earnings': self.get_mining_earnings()
                }
            }
            
            # Update dashboard
            if hasattr(self.dashboard_frame, 'update_trading_summary'):
                self.dashboard_frame.update_trading_summary(dashboard_data['trading'])
            
            if hasattr(self.dashboard_frame, 'update_mining_summary'):
                self.dashboard_frame.update_mining_summary(dashboard_data['mining'])
            
            # If there's a unified update method, use it
            if hasattr(self.dashboard_frame, 'update_display'):
                self.dashboard_frame.update_display(dashboard_data)
            
            logger.debug("Dashboard frame updated")
        except Exception as e:
            logger.error(f"Error updating dashboard frame: {e}")
    
    def get_portfolio_value(self):
        """Get the total portfolio value from trading data."""
        try:
            if 'portfolio' not in self.trading_data:
                return 0.0
            
            portfolio = self.trading_data['portfolio']
            if isinstance(portfolio, dict) and 'total_value' in portfolio:
                return portfolio['total_value']
            
            # Try to calculate if not provided directly
            total = 0.0
            if isinstance(portfolio, dict) and 'balance' in portfolio:
                total += float(portfolio['balance'])
            
            if isinstance(portfolio, dict) and 'positions' in portfolio:
                positions = portfolio['positions']
                if isinstance(positions, dict):
                    for symbol, position in positions.items():
                        if isinstance(position, dict) and 'value' in position:
                            total += float(position['value'])
            
            return total
        except Exception as e:
            logger.error(f"Error calculating portfolio value: {e}")
            return 0.0
    
    def get_active_orders_count(self):
        """Get the count of active orders from trading data."""
        try:
            if 'orders' not in self.trading_data:
                return 0
            
            orders = self.trading_data.get('orders', [])
            if not isinstance(orders, list):
                return 0
            
            # Count only active orders
            active_count = 0
            for order in orders:
                if isinstance(order, dict) and order.get('status') in ['open', 'pending', 'active']:
                    active_count += 1
            
            return active_count
        except Exception as e:
            logger.error(f"Error counting active orders: {e}")
            return 0
    
    def get_total_hashrate(self):
        """Get the total hashrate from mining data."""
        try:
            if 'stats' not in self.mining_data:
                return 0.0
            
            stats = self.mining_data['stats']
            if isinstance(stats, dict) and 'hashrate' in stats:
                return stats['hashrate']
            
            # Try to calculate from hardware if not provided directly
            total = 0.0
            if 'hardware' in self.mining_data:
                hardware = self.mining_data['hardware']
                if isinstance(hardware, list):
                    for device in hardware:
                        if isinstance(device, dict) and 'hashrate' in device:
                            total += float(device['hashrate'])
            
            return total
        except Exception as e:
            logger.error(f"Error calculating total hashrate: {e}")
            return 0.0
    
    def get_mining_earnings(self):
        """Get the mining earnings from mining data."""
        try:
            if 'stats' not in self.mining_data:
                return 0.0
            
            stats = self.mining_data['stats']
            if isinstance(stats, dict) and 'earnings' in stats:
                return stats['earnings']
            
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating mining earnings: {e}")
            return 0.0
    
    async def handle_trading_update(self, event_type, data):
        """Handle trading updates."""
        try:
            # Update specific part of trading data
            update_type = data.get('type')
            update_data = data.get('data')
            
            if not self.trading_data:
                self.trading_data = {}
            
            if update_type and update_data:
                self.trading_data[update_type] = update_data
                self.stats["last_trading_update"] = time.time()
                
                # Update frame immediately
                if self.trading_frame_ready:
                    self.update_trading_frame()
                
                # Update dashboard
                if self.dashboard_frame_ready:
                    self.update_dashboard_frame()
                
                logger.debug(f"Handled trading update: {update_type}")
        except Exception as e:
            logger.error(f"Error handling trading update: {e}")
    
    async def handle_mining_update(self, event_type, data):
        """Handle mining updates."""
        try:
            # Update specific part of mining data
            update_type = data.get('type')
            update_data = data.get('data')
            
            if not self.mining_data:
                self.mining_data = {}
            
            if update_type and update_data:
                self.mining_data[update_type] = update_data
                self.stats["last_mining_update"] = time.time()
                
                # Update frame immediately
                if self.mining_frame_ready:
                    self.update_mining_frame()
                
                # Update dashboard
                if self.dashboard_frame_ready:
                    self.update_dashboard_frame()
                
                logger.debug(f"Handled mining update: {update_type}")
        except Exception as e:
            logger.error(f"Error handling mining update: {e}")
    
    async def handle_trading_data(self, event_type, data):
        """Handle complete trading data updates."""
        try:
            if 'trading_data' in data:
                self.trading_data = data['trading_data']
                self.stats["last_trading_update"] = time.time()
                
                # Update frame immediately
                if self.trading_frame_ready:
                    self.update_trading_frame()
                
                # Update dashboard
                if self.dashboard_frame_ready:
                    self.update_dashboard_frame()
                
                logger.debug("Handled complete trading data update")
        except Exception as e:
            logger.error(f"Error handling trading data: {e}")
    
    async def handle_mining_data(self, event_type, data):
        """Handle complete mining data updates."""
        try:
            if 'mining_data' in data:
                self.mining_data = data['mining_data']
                self.stats["last_mining_update"] = time.time()
                
                # Update frame immediately
                if self.mining_frame_ready:
                    self.update_mining_frame()
                
                # Update dashboard
                if self.dashboard_frame_ready:
                    self.update_dashboard_frame()
                
                logger.debug("Handled complete mining data update")
        except Exception as e:
            logger.error(f"Error handling mining data: {e}")
    
    async def handle_shutdown(self, event_type, data):
        """Handle system shutdown event."""
        logger.info("Handling shutdown event")
        await self.shutdown()
    
    async def shutdown(self):
        """Properly shut down the display integrator."""
        logger.info("Shutting down Trading and Mining Display Integrator...")
        
        # Stop update task
        self.running = False
        if self.update_task:
            try:
                self.update_task.cancel()
                await asyncio.sleep(0.1)  # Allow task to cancel
            except Exception as e:
                logger.warning(f"Error cancelling update task: {e}")
        
        logger.info("Trading and Mining Display Integrator shutdown complete")

async def initialize_display_integrator(event_bus, main_window):
    """
    Initialize the display integrator with frames from the main window.
    
    Args:
        event_bus: Event bus for component communication
        main_window: Main window instance containing the frames
        
    Returns:
        TradingMiningDisplayIntegrator instance
    """
    try:
        # Get frames from main window
        trading_frame = None
        mining_frame = None
        dashboard_frame = None
        
        if hasattr(main_window, 'trading_frame'):
            trading_frame = main_window.trading_frame
        
        if hasattr(main_window, 'mining_frame'):
            mining_frame = main_window.mining_frame
        
        if hasattr(main_window, 'dashboard_frame'):
            dashboard_frame = main_window.dashboard_frame
        
        # Create integrator
        integrator = TradingMiningDisplayIntegrator(
            event_bus=event_bus,
            trading_frame=trading_frame,
            mining_frame=mining_frame,
            dashboard_frame=dashboard_frame
        )
        
        # Initialize integrator
        await integrator.initialize()
        
        return integrator
    except Exception as e:
        logger.error(f"Failed to initialize display integrator: {e}")
        return None

# Add to Kingdom AI initialization in main.py
def add_to_kingdom_ai(event_bus, main_window):
    """
    Add this display integrator to the Kingdom AI initialization sequence.
    
    Args:
        event_bus: Event bus for component communication
        main_window: Main window instance
        
    Returns:
        Coroutine to initialize the display integrator
    """
    return initialize_display_integrator(event_bus, main_window)
