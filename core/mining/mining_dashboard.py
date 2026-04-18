#!/usr/bin/env python3

import os
import sys
import time
import asyncio
import logging
import traceback
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
import json

from core.base_component import BaseComponent

logger = logging.getLogger("Kingdom.MiningDashboard")

class MiningDashboard(BaseComponent):
    """
    Kingdom AI Mining Dashboard - Visualizes and monitors mining operations
    
    Features:
    - Real-time mining statistics display
    - Historical mining data visualization
    - Profitability analysis
    - Hardware monitoring integration
    - Alert system for mining issues
    """
    
    def __init__(self, event_bus=None, config=None, name="MiningDashboard"):
        """Initialize the mining dashboard."""
        super().__init__(event_bus=event_bus, config=config)
        self.name = name
        self.logger = logging.getLogger(f"Kingdom.{name}")
        
        # Initialize default attributes
        self.stats_history = []
        self.max_history_entries = 1000  # Max entries to keep in history
        self.last_update_time = None
        self.dashboard_data = {
            "current_hashrate": 0,
            "average_hashrate": 0,
            "accepted_shares": 0,
            "rejected_shares": 0,
            "revenue_24h": 0.0,
            "uptime": 0,
            "algorithms": [],
            "pools": [],
            "devices": []
        }
        
        # Set up data storage directory
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data',
            'mining'
        )
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.logger.info(f"{name} initialized")
    
    async def initialize(self) -> bool:
        """Initialize the mining dashboard and load historical data."""
        try:
            self.logger.info("Initializing Mining Dashboard")
            
            # Call parent initialization
            await super().initialize()
            
            # Load configuration
            if self.config:
                self.max_history_entries = self.config.get("max_history_entries", self.max_history_entries)
            
            # Load historical data if available
            await self._load_historical_data()
            
            # Subscribe to mining events
            if self.event_bus:
                self.event_bus.subscribe_sync('mining.status.update', self._handle_mining_status_update)
                self.event_bus.subscribe_sync('mining.alert', self._handle_mining_alert)
                self.event_bus.subscribe_sync('system.shutdown', self._handle_shutdown)
                self.logger.info("Subscribed to mining events")
            
            self.is_initialized = True
            self.logger.info("Mining Dashboard initialization complete")
            
            return True
        except Exception as e:
            self.logger.error(f"Error initializing Mining Dashboard: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def initialize_sync(self) -> bool:
        """Synchronous version of initialize."""
        try:
            self.logger.info("Initializing Mining Dashboard (sync)")
            
            # Load configuration
            if self.config:
                self.max_history_entries = self.config.get("max_history_entries", self.max_history_entries)
            
            # Try to load historical data synchronously
            self._load_historical_data_sync()
            
            self.is_initialized = True
            
            return True
        except Exception as e:
            self.logger.error(f"Error in synchronous initialization: {e}")
            return False
    
    async def _handle_mining_status_update(self, event_data: Dict[str, Any]) -> None:
        """Handle mining status update event."""
        try:
            is_mining = event_data.get("is_mining", False)
            stats = event_data.get("stats", {})
            timestamp = event_data.get("timestamp", time.time())
            
            # Update dashboard data
            self.dashboard_data["current_hashrate"] = stats.get("hashrate", 0)
            self.dashboard_data["accepted_shares"] = stats.get("accepted_shares", 0)
            self.dashboard_data["rejected_shares"] = stats.get("rejected_shares", 0)
            self.dashboard_data["uptime"] = stats.get("uptime", 0)
            
            # Format timestamp
            timestamp_dt = datetime.fromtimestamp(timestamp)
            
            # Add to history if mining
            if is_mining:
                history_entry = {
                    "timestamp": timestamp,
                    "timestamp_formatted": timestamp_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "hashrate": stats.get("hashrate", 0),
                    "accepted_shares": stats.get("accepted_shares", 0),
                    "rejected_shares": stats.get("rejected_shares", 0),
                    "revenue": stats.get("revenue", 0.0)
                }
                
                self.stats_history.append(history_entry)
                
                # Limit history size
                if len(self.stats_history) > self.max_history_entries:
                    self.stats_history = self.stats_history[-self.max_history_entries:]
                
                # Update average statistics
                self._update_average_statistics()
                
                # Save history periodically (every 5 minutes)
                current_time = time.time()
                if not self.last_update_time or (current_time - self.last_update_time > 300):
                    self.last_update_time = current_time
                    asyncio.create_task(self._save_historical_data())
            
            # Publish dashboard update
            await self._publish_dashboard_update()
            
        except Exception as e:
            self.logger.error(f"Error handling mining status update: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_mining_alert(self, event_data: Dict[str, Any]) -> None:
        """Handle mining alert event."""
        try:
            alert_type = event_data.get("type", "unknown")
            alert_message = event_data.get("message", "")
            
            self.logger.warning(f"Mining alert received: {alert_type} - {alert_message}")
            
            # Log the alert
            alert_entry = {
                "timestamp": time.time(),
                "timestamp_formatted": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": alert_type,
                "message": alert_message
            }
            
            # Save alert to file
            alert_file = os.path.join(self.data_dir, "mining_alerts.json")
            try:
                # Load existing alerts
                existing_alerts = []
                if os.path.exists(alert_file):
                    with open(alert_file, 'r') as f:
                        existing_alerts = json.load(f)
                
                # Add new alert
                existing_alerts.append(alert_entry)
                
                # Limit to last 100 alerts
                if len(existing_alerts) > 100:
                    existing_alerts = existing_alerts[-100:]
                
                # Save updated alerts
                with open(alert_file, 'w') as f:
                    json.dump(existing_alerts, f, indent=2)
            except Exception as file_error:
                self.logger.error(f"Error saving alert to file: {file_error}")
            
        except Exception as e:
            self.logger.error(f"Error handling mining alert: {e}")
    
    async def _handle_shutdown(self, _: Dict[str, Any] = None) -> None:
        """Handle system shutdown event."""
        try:
            self.logger.info("System shutdown requested, saving mining history")
            await self._save_historical_data()
        except Exception as e:
            self.logger.error(f"Error handling shutdown event: {e}")
    
    async def _publish_dashboard_update(self) -> None:
        """Publish dashboard update to event bus."""
        try:
            if not self.event_bus:
                return
                
            # Create dashboard update data
            update_data = {
                "dashboard": self.dashboard_data,
                "timestamp": time.time()
            }
            
            # Publish update event
            self.event_bus.publish("mining.dashboard.update", update_data)
            
        except Exception as e:
            self.logger.error(f"Error publishing dashboard update: {e}")
    
    def _update_average_statistics(self) -> None:
        """Update average statistics based on history."""
        try:
            if not self.stats_history:
                return
                
            # Calculate 24-hour window
            current_time = time.time()
            time_24h_ago = current_time - (24 * 3600)
            
            # Filter history entries within 24 hours
            recent_entries = [entry for entry in self.stats_history if entry["timestamp"] > time_24h_ago]
            
            if not recent_entries:
                return
                
            # Calculate averages
            avg_hashrate = sum(entry["hashrate"] for entry in recent_entries) / len(recent_entries)
            total_revenue_24h = sum(entry["revenue"] for entry in recent_entries)
            
            # Update dashboard data
            self.dashboard_data["average_hashrate"] = avg_hashrate
            self.dashboard_data["revenue_24h"] = total_revenue_24h
            
        except Exception as e:
            self.logger.error(f"Error updating average statistics: {e}")
    
    async def _load_historical_data(self) -> None:
        """Load historical mining data from file."""
        try:
            history_file = os.path.join(self.data_dir, "mining_history.json")
            
            if not os.path.exists(history_file):
                self.logger.info("No historical mining data found")
                return
                
            try:
                with open(history_file, 'r') as f:
                    self.stats_history = json.load(f)
                    
                self.logger.info(f"Loaded {len(self.stats_history)} historical mining entries")
                
                # Update average statistics
                self._update_average_statistics()
                
            except Exception as file_error:
                self.logger.error(f"Error loading historical data: {file_error}")
                
        except Exception as e:
            self.logger.error(f"Error in _load_historical_data: {e}")
    
    def _load_historical_data_sync(self) -> None:
        """Synchronous version of _load_historical_data."""
        try:
            history_file = os.path.join(self.data_dir, "mining_history.json")
            
            if not os.path.exists(history_file):
                self.logger.info("No historical mining data found")
                return
                
            try:
                with open(history_file, 'r') as f:
                    self.stats_history = json.load(f)
                    
                self.logger.info(f"Loaded {len(self.stats_history)} historical mining entries")
                
                # Update average statistics
                self._update_average_statistics()
                
            except Exception as file_error:
                self.logger.error(f"Error loading historical data: {file_error}")
                
        except Exception as e:
            self.logger.error(f"Error in _load_historical_data_sync: {e}")
    
    async def _save_historical_data(self) -> None:
        """Save historical mining data to file."""
        try:
            if not self.stats_history:
                return
                
            history_file = os.path.join(self.data_dir, "mining_history.json")
            
            with open(history_file, 'w') as f:
                json.dump(self.stats_history, f, indent=2)
                
            self.logger.info(f"Saved {len(self.stats_history)} historical mining entries")
            
        except Exception as e:
            self.logger.error(f"Error saving historical data: {e}")
    
    def get_summary_data(self) -> Dict[str, Any]:
        """Get summarized dashboard data for UI display."""
        return {
            "current_hashrate": f"{self.dashboard_data['current_hashrate']:.2f} MH/s",
            "average_hashrate": f"{self.dashboard_data['average_hashrate']:.2f} MH/s",
            "accepted_shares": self.dashboard_data['accepted_shares'],
            "rejected_shares": self.dashboard_data['rejected_shares'],
            "revenue_24h": f"${self.dashboard_data['revenue_24h']:.4f}",
            "uptime": self._format_uptime(self.dashboard_data['uptime'])
        }
    
    def _format_uptime(self, uptime_seconds: float) -> str:
        """Format uptime in a human-readable format."""
        if uptime_seconds < 60:
            return f"{int(uptime_seconds)} seconds"
        elif uptime_seconds < 3600:
            minutes = int(uptime_seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = int(uptime_seconds / 3600)
            minutes = int((uptime_seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
