#!/usr/bin/env python3
"""
Kingdom AI Mining Dashboard

Core implementation of the Mining Dashboard component.
This component displays real-time mining statistics and connects to the mining system.
"""

import logging
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MiningDashboard:
    """Mining Dashboard component for Kingdom AI.
    
    Displays real-time mining statistics, profitability calculations,
    and blockchain information from the mining system.
    """
    
    def __init__(self, config=None, event_bus=None):
        """Initialize Mining Dashboard.
        
        Args:
            config: Optional configuration dictionary
            event_bus: Event bus for component communication
        """
        self.config = config or {}
        self.event_bus = event_bus
        self.mining_system = None
        self.logger = logging.getLogger(__name__)
        self.connected = False
        self.mining_stats = {}
        self.profitability = {}
        self.hash_rate_history = []
        self.earnings_history = []
        
        # Initialize component
        self.logger.info("Mining Dashboard initialized")
    
    async def initialize(self):
        """Initialize the component asynchronously."""
        if self.event_bus:
            # Subscribe to mining events (subscribe is SYNC, not async)
            self.event_bus.subscribe("mining.stats.updated", self.handle_mining_stats_update)
            self.event_bus.subscribe("mining.profitability.updated", self.handle_profitability_update)
            self.event_bus.subscribe("mining.worker.status", self.handle_worker_status_update)
            
            # Notify system that component is ready (publish is SYNC)
            self.event_bus.publish("component.initialized", {
                "component": "MiningDashboard",
                "status": "ready"
            })
            
            self.logger.info("Mining Dashboard subscribed to events")
        return True
    
    def update_stats(self, stats):
        """Update mining statistics."""
        self.mining_stats = stats
        # Notify UI if connected
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish("mining.dashboard.stats_updated", {
                "stats": stats,
                "component": "MiningDashboard"
            }))
    
    def set_mining_system(self, mining_system):
        """Connect to the mining system component.
        
        Args:
            mining_system: The mining system component instance
        
        Returns:
            bool: True if connected successfully, False otherwise
        """
        if mining_system is None:
            self.logger.warning("Null mining system provided to MiningDashboard")
            return False
            
        self.mining_system = mining_system
        self.logger.info(f"MiningDashboard connected to {mining_system.__class__.__name__}")
        
        # Set connected flag
        self.connected = True
        return True
    
    async def handle_mining_stats_update(self, event_data):
        """Handle mining stats update events."""
        if isinstance(event_data, dict):
            self.update_stats(event_data)
    
    async def handle_profitability_update(self, event_data):
        """Handle profitability update events."""
        if isinstance(event_data, dict):
            self.profitability = event_data
    
    async def handle_mining_status_change(self, event_data):
        """Handle mining status change events."""
        if hasattr(self, "status_var") and self.status_var is not None:
            status = event_data.get("status", "Unknown")
            self.status_var.set(status)
            # Update status indicator color
            if status.lower() == "mining":
                self.status_indicator.config(bg="green")
            elif status.lower() == "idle":
                self.status_indicator.config(bg="yellow")
            else:
                self.status_indicator.config(bg="red")
    
    async def handle_worker_status_update(self, event_data):
        """Handle worker status update events."""
        # Implementation depends on worker status data structure
        if isinstance(event_data, dict):
            self.logger.info(f"Worker status updated: {event_data}")
