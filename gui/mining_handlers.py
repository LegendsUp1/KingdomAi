#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Mining Event Handlers Module
Contains implementation of mining event handlers for TabManager
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger("KingdomAI.MiningHandlers")

# Mining event handler methods
async def update_hashrate_data(self, event_type: str, event_data: Dict[str, Any]):
    """Update hashrate display when mining.hashrate events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing hashrate information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty hashrate data")
            return
            
        # Update mining data with latest hashrates
        if 'hashrates' in event_data:
            self.hashrate_data = event_data['hashrates']
            self.mining_data['hashrates'] = self.hashrate_data
            
        # Update hashrate displays if mining tab is present
        if 'mining' in self.tab_frames:
            mining_frame = self.tab_frames['mining']
            
            # Update hashrate labels if they exist
            if hasattr(mining_frame, 'hashrate_label'):
                total_hashrate = sum(self.hashrate_data.values()) if self.hashrate_data else 0
                
                # Format hashrate based on size
                if total_hashrate > 1_000_000_000:  # GH/s
                    formatted_hashrate = f"{total_hashrate / 1_000_000_000:.2f} GH/s"
                elif total_hashrate > 1_000_000:  # MH/s
                    formatted_hashrate = f"{total_hashrate / 1_000_000:.2f} MH/s"
                elif total_hashrate > 1_000:  # KH/s
                    formatted_hashrate = f"{total_hashrate / 1_000:.2f} KH/s"
                else:  # H/s
                    formatted_hashrate = f"{total_hashrate:.2f} H/s"
                
                if self.using_pyqt:
                    mining_frame.hashrate_label.setText(f"Total Hashrate: {formatted_hashrate}")
                elif self.using_tkinter:
                    mining_frame.hashrate_label.config(text=f"Total Hashrate: {formatted_hashrate}")
                    
            # Update individual device hashrates if available
            if hasattr(mining_frame, 'device_hashrates') and isinstance(mining_frame.device_hashrates, dict):
                for device_id, hashrate_widget in mining_frame.device_hashrates.items():
                    if device_id in self.hashrate_data:
                        device_hashrate = self.hashrate_data[device_id]
                        
                        # Format hashrate based on size
                        if device_hashrate > 1_000_000_000:  # GH/s
                            formatted = f"{device_hashrate / 1_000_000_000:.2f} GH/s"
                        elif device_hashrate > 1_000_000:  # MH/s
                            formatted = f"{device_hashrate / 1_000_000:.2f} MH/s"
                        elif device_hashrate > 1_000:  # KH/s
                            formatted = f"{device_hashrate / 1_000:.2f} KH/s"
                        else:  # H/s
                            formatted = f"{device_hashrate:.2f} H/s"
                        
                        if self.using_pyqt:
                            hashrate_widget.setText(f"Device {device_id}: {formatted}")
                        elif self.using_tkinter:
                            hashrate_widget.config(text=f"Device {device_id}: {formatted}")
        
        self.logger.debug(f"Updated hashrates for {len(self.hashrate_data) if self.hashrate_data else 0} devices")
    except Exception as e:
        self.logger.error(f"Error updating hashrate data: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_mining_rewards(self, event_type: str, event_data: Dict[str, Any]):
    """Update mining rewards display when mining.rewards events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing mining rewards information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty mining rewards data")
            return
            
        # Update mining rewards data
        if 'rewards' in event_data:
            self.mining_rewards = event_data['rewards']
            self.mining_data['rewards'] = self.mining_rewards
            
        # Update rewards display if mining tab is present
        if 'mining' in self.tab_frames:
            mining_frame = self.tab_frames['mining']
            
            # Update total rewards display if it exists
            if hasattr(mining_frame, 'total_rewards_label'):
                total_rewards = sum(self.mining_rewards.values()) if self.mining_rewards else 0
                
                if self.using_pyqt:
                    mining_frame.total_rewards_label.setText(f"Total Rewards: {total_rewards:.8f} BTC")
                elif self.using_tkinter:
                    mining_frame.total_rewards_label.config(text=f"Total Rewards: {total_rewards:.8f} BTC")
            
            # Update rewards history if it exists
            if hasattr(mining_frame, 'rewards_list'):
                if self.using_pyqt:
                    # Clear and update list
                    mining_frame.rewards_list.clear()
                    for period, reward in self.mining_rewards.items():
                        mining_frame.rewards_list.addItem(f"{period}: {reward:.8f} BTC")
                elif self.using_tkinter:
                    # Clear and update listbox
                    mining_frame.rewards_list.delete(0, 'end')
                    for period, reward in self.mining_rewards.items():
                        mining_frame.rewards_list.insert('end', f"{period}: {reward:.8f} BTC")
        
        self.logger.debug(f"Updated mining rewards for {len(self.mining_rewards) if self.mining_rewards else 0} periods")
    except Exception as e:
        self.logger.error(f"Error updating mining rewards: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_mining_status(self, event_type: str, event_data: Dict[str, Any]):
    """Update mining status display when mining.status events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing mining status information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty mining status data")
            return
            
        # Update mining status
        if 'status' in event_data:
            self.mining_status = event_data['status']
            self.mining_data['status'] = self.mining_status
            
        # Update mining status display if mining tab is present
        if 'mining' in self.tab_frames:
            mining_frame = self.tab_frames['mining']
            
            # Update status label if it exists
            if hasattr(mining_frame, 'status_label'):
                if self.using_pyqt:
                    mining_frame.status_label.setText(f"Mining Status: {self.mining_status}")
                elif self.using_tkinter:
                    mining_frame.status_label.config(text=f"Mining Status: {self.mining_status}")
            
            # Update mining control buttons based on status
            if hasattr(mining_frame, 'start_button') and hasattr(mining_frame, 'stop_button'):
                if self.mining_status == "active":
                    # Mining is active, enable stop button, disable start button
                    if self.using_pyqt:
                        mining_frame.start_button.setEnabled(False)
                        mining_frame.stop_button.setEnabled(True)
                    elif self.using_tkinter:
                        mining_frame.start_button.config(state='disabled')
                        mining_frame.stop_button.config(state='normal')
                elif self.mining_status in ["stopped", "error", "disconnected"]:
                    # Mining is inactive, enable start button, disable stop button
                    if self.using_pyqt:
                        mining_frame.start_button.setEnabled(True)
                        mining_frame.stop_button.setEnabled(False)
                    elif self.using_tkinter:
                        mining_frame.start_button.config(state='normal')
                        mining_frame.stop_button.config(state='disabled')
        
        self.logger.debug(f"Updated mining status: {self.mining_status}")
    except Exception as e:
        self.logger.error(f"Error updating mining status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_mining_devices(self, event_type: str, event_data: Dict[str, Any]):
    """Update mining devices display when mining.devices events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing mining device information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty mining devices data")
            return
            
        # Update mining devices data
        if 'devices' in event_data:
            devices = event_data['devices']
            self.mining_data['devices'] = devices
            
        # Update devices display if mining tab is present
        if 'mining' in self.tab_frames:
            mining_frame = self.tab_frames['mining']
            
            # Update devices list if it exists
            if hasattr(mining_frame, 'devices_list'):
                if self.using_pyqt:
                    # Clear and update list
                    mining_frame.devices_list.clear()
                    for device in devices:
                        device_id = device.get('id', 'Unknown')
                        device_type = device.get('type', 'Unknown')
                        status = device.get('status', 'Unknown')
                        temperature = device.get('temperature', 0)
                        
                        mining_frame.devices_list.addItem(
                            f"Device {device_id} ({device_type}) - Status: {status} - Temp: {temperature}°C"
                        )
                elif self.using_tkinter:
                    # Clear and update listbox
                    mining_frame.devices_list.delete(0, 'end')
                    for device in devices:
                        device_id = device.get('id', 'Unknown')
                        device_type = device.get('type', 'Unknown')
                        status = device.get('status', 'Unknown')
                        temperature = device.get('temperature', 0)
                        
                        mining_frame.devices_list.insert(
                            'end', 
                            f"Device {device_id} ({device_type}) - Status: {status} - Temp: {temperature}°C"
                        )
        
        self.logger.debug(f"Updated mining devices display with {len(devices) if devices else 0} devices")
    except Exception as e:
        self.logger.error(f"Error updating mining devices: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

# Tab-specific initialization methods
async def connect_to_blockchain(self):
    """Connect to blockchain nodes and initialize mining data feeds."""
    try:
        self.logger.info("Connecting to blockchain nodes")
        
        # Update mining status
        self.mining_status = "connecting"
        
        # Connect to Redis Quantum Nexus on required port and password
        if hasattr(self, 'redis_client'):
            try:
                # Ensure Redis connection uses port 6380 with QuantumNexus2025 password
                await self.redis_client.initialize(
                    host="localhost",
                    port=6380,
                    password="QuantumNexus2025",
                    environment="mining"
                )
                self.logger.info("Connected to Redis Quantum Nexus on port 6380 for mining data")
            except Exception as redis_error:
                self.logger.error(f"Failed to connect to Redis Quantum Nexus: {redis_error}")
                self.mining_status = "disconnected"
                return False
        
        # Request mining data
        if self.event_bus:
            await self.event_bus.emit("request_mining_data")
            await self.event_bus.emit("request_mining_devices")
            
        self.mining_status = "connected"
        return True
    except Exception as e:
        self.logger.error(f"Error connecting to blockchain: {e}")
        self.mining_status = "error"
        import traceback
        self.logger.error(traceback.format_exc())
        return False
