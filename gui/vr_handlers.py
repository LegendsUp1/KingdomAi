#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI VR Event Handlers Module
Contains implementation of VR event handlers for TabManager
"""

import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("KingdomAI.VRHandlers")

# VR event handler methods
async def update_vr_status(self, event_type: str, event_data: Dict[str, Any]):
    """Update VR status display when vr.status events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing VR status information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty VR status data")
            return
            
        # Update VR status
        if 'status' in event_data:
            self.vr_status = event_data['status']
            self.vr_data['status'] = self.vr_status
            
        # Update VR status display if VR tab is present
        if 'vr' in self.tab_frames:
            vr_frame = self.tab_frames['vr']
            
            # Update status label if it exists
            if hasattr(vr_frame, 'status_label'):
                if self.using_pyqt:
                    vr_frame.status_label.setText(f"VR Status: {self.vr_status}")
                elif self.using_tkinter:
                    vr_frame.status_label.config(text=f"VR Status: {self.vr_status}")
            
            # Update connection indicator if it exists
            if hasattr(vr_frame, 'connection_indicator'):
                if self.vr_status == "connected":
                    indicator_color = "green"
                elif self.vr_status == "connecting":
                    indicator_color = "yellow"
                else:
                    indicator_color = "red"
                    
                if self.using_pyqt:
                    vr_frame.connection_indicator.setStyleSheet(f"background-color: {indicator_color};")
                elif self.using_tkinter:
                    vr_frame.connection_indicator.config(bg=indicator_color)
                    
            # Update connect button if it exists
            if hasattr(vr_frame, 'connect_button'):
                if self.vr_status == "connected":
                    button_text = "Disconnect"
                    if self.using_pyqt:
                        vr_frame.connect_button.setText(button_text)
                    elif self.using_tkinter:
                        vr_frame.connect_button.config(text=button_text)
                else:
                    button_text = "Connect"
                    if self.using_pyqt:
                        vr_frame.connect_button.setText(button_text)
                    elif self.using_tkinter:
                        vr_frame.connect_button.config(text=button_text)
                    
        self.logger.debug(f"Updated VR status: {self.vr_status}")
    except Exception as e:
        self.logger.error(f"Error updating VR status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_vr_environments(self, event_type: str, event_data: Dict[str, Any]):
    """Update VR environments display when vr.environments events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing VR environments information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty VR environments data")
            return
            
        # Update VR environments
        if 'environments' in event_data:
            self.vr_environments = event_data['environments']
            self.vr_data['environments'] = self.vr_environments
            
        # Update current environment if provided
        if 'current_environment' in event_data:
            self.current_vr_environment = event_data['current_environment']
            self.vr_data['current_environment'] = self.current_vr_environment
            
        # Update VR environments display if VR tab is present
        if 'vr' in self.tab_frames:
            vr_frame = self.tab_frames['vr']
            
            # Update environments list if it exists
            if hasattr(vr_frame, 'environments_list'):
                if self.using_pyqt:
                    # Clear and update list
                    vr_frame.environments_list.clear()
                    for env in self.vr_environments:
                        name = env.get('name', 'Unknown')
                        description = env.get('description', '')
                        
                        display = f"{name}"
                        if description:
                            display += f" - {description}"
                            
                        vr_frame.environments_list.addItem(display)
                        
                        # Set current item if it matches current environment
                        if env.get('id') == self.current_vr_environment:
                            vr_frame.environments_list.setCurrentRow(
                                vr_frame.environments_list.count() - 1
                            )
                elif self.using_tkinter:
                    # Clear and update listbox
                    vr_frame.environments_list.delete(0, 'end')
                    current_index = 0
                    
                    for i, env in enumerate(self.vr_environments):
                        name = env.get('name', 'Unknown')
                        description = env.get('description', '')
                        
                        display = f"{name}"
                        if description:
                            display += f" - {description}"
                            
                        vr_frame.environments_list.insert('end', display)
                        
                        # Track current environment index
                        if env.get('id') == self.current_vr_environment:
                            current_index = i
                    
                    # Select current environment
                    vr_frame.environments_list.selection_set(current_index)
            
            # Update current environment label if it exists
            if hasattr(vr_frame, 'current_env_label'):
                current_name = "None"
                
                # Find current environment name
                for env in self.vr_environments:
                    if env.get('id') == self.current_vr_environment:
                        current_name = env.get('name', 'Unknown')
                        break
                
                if self.using_pyqt:
                    vr_frame.current_env_label.setText(f"Current Environment: {current_name}")
                elif self.using_tkinter:
                    vr_frame.current_env_label.config(text=f"Current Environment: {current_name}")
                    
        self.logger.debug(f"Updated VR environments with {len(self.vr_environments) if self.vr_environments else 0} environments")
    except Exception as e:
        self.logger.error(f"Error updating VR environments: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_vr_data(self, event_type: str, event_data: Dict[str, Any]):
    """Update VR visualization data when vr.data events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing VR visualization data
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty VR data")
            return
            
        # Store visualization data
        if 'visualization' in event_data:
            visualization_data = event_data['visualization']
            self.vr_data['visualization'] = visualization_data
            
        # Update VR visualization display if VR tab is present
        if 'vr' in self.tab_frames:
            vr_frame = self.tab_frames['vr']
            
            # Update visualization panel if it exists
            if hasattr(vr_frame, 'visualization_panel'):
                if self.using_pyqt:
                    # If using PyQt, update the visualization widget
                    # This would be more complex and specific to the visualization implementation
                    self.logger.debug("PyQt visualization update would be implemented here")
                elif self.using_tkinter:
                    # If using Tkinter, update the visualization canvas
                    self.logger.debug("Tkinter visualization update would be implemented here")
                    
        self.logger.debug("Updated VR visualization data")
    except Exception as e:
        self.logger.error(f"Error updating VR data: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

# Tab-specific initialization methods
async def connect_vr(self):
    """Connect to VR system and initialize data feeds."""
    try:
        self.logger.info("Connecting to VR system")
        
        # Update VR status
        self.vr_status = "connecting"
        
        # Connect to Redis Quantum Nexus on required port and password
        if hasattr(self, 'redis_client'):
            try:
                # Ensure Redis connection uses port 6380 with QuantumNexus2025 password
                await self.redis_client.initialize(
                    host="localhost",
                    port=6380,
                    password="QuantumNexus2025",
                    environment="vr"
                )
                self.logger.info("Connected to Redis Quantum Nexus on port 6380 for VR data")
            except Exception as redis_error:
                self.logger.error(f"Failed to connect to Redis Quantum Nexus: {redis_error}")
                self.vr_status = "disconnected"
                return False
        
        # Request VR data
        if self.event_bus:
            await self.event_bus.emit("connect_vr_system")
            await self.event_bus.emit("request_vr_environments")
            
        self.vr_status = "connected"
        return True
    except Exception as e:
        self.logger.error(f"Error connecting to VR system: {e}")
        self.vr_status = "error"
        import traceback
        self.logger.error(traceback.format_exc())
        return False
