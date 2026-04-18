#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VR Event Handlers for TabManager in Kingdom AI.
This module contains the VR event handler methods that need to be added to the TabManager class.
"""

# VR event handlers to be added to TabManager class

async def _handle_vr_connection_response(self, event_type: str, event_data: dict) -> None:
    """Handle VR connection response events.
    
    Args:
        event_type: The event type
        event_data: The event data containing connection status
    """
    try:
        status = event_data.get("status", "unknown")
        device = event_data.get("device", "unknown")
        message = f"Status: {status.capitalize()} - Device: {device}"
        
        if hasattr(self, 'vr_status'):
            self.vr_status.config(text=message)
            
        # If we're using the complete VRFrame, let it handle the event details
        if hasattr(self, 'vr_frame') and self.vr_frame:
            # The VR frame has methods to handle connection responses
            # Enable appropriate buttons based on connection status
            if status == "connected":
                if "connect" in self.vr_frame.control_buttons:
                    self.vr_frame.control_buttons["connect"].config(state="disabled")
                if "disconnect" in self.vr_frame.control_buttons:
                    self.vr_frame.control_buttons["disconnect"].config(state="normal")
                self.vr_frame.connected = True
            else:
                if "connect" in self.vr_frame.control_buttons:
                    self.vr_frame.control_buttons["connect"].config(state="normal")
                if "disconnect" in self.vr_frame.control_buttons:
                    self.vr_frame.control_buttons["disconnect"].config(state="disabled")
                self.vr_frame.connected = False
            
            # Update status message in VR frame
            self.vr_frame._add_status_message(f"Connection {status} for device {device}", 
                                            "success" if status == "connected" else "error")
            
        logger.info(f"VR connection response: {message}")
    except Exception as e:
        logger.error(f"Error handling VR connection response: {e}")

async def _handle_vr_environment_loaded(self, event_type: str, event_data: dict) -> None:
    """Handle VR environment loaded events.
    
    Args:
        event_type: The event type
        event_data: The event data containing environment info
    """
    try:
        environment = event_data.get("environment", "unknown")
        status = event_data.get("status", "unknown")
        
        # If we're using the complete VRFrame, let it handle the event details
        if hasattr(self, 'vr_frame') and self.vr_frame:
            # Update environment status in VRFrame
            self.vr_frame.environment = environment
            self.vr_frame.environment_loaded = (status == "loaded")
            
            # Update environment dropdown if it exists
            if hasattr(self.vr_frame, 'environment_var'):
                self.vr_frame.environment_var.set(environment)
            
            # Update status message in VR frame
            self.vr_frame._add_status_message(f"Environment {environment} {status}", 
                                             "success" if status == "loaded" else "info")
        elif hasattr(self, 'vr_status'):
            self.vr_status.config(text=f"Status: Environment {environment} {status}")
            
        logger.info(f"VR environment {environment} {status}")
    except Exception as e:
        logger.error(f"Error handling VR environment loaded event: {e}")

async def _handle_vr_tracking_status(self, event_type: str, event_data: dict) -> None:
    """Handle VR tracking status events.
    
    Args:
        event_type: The event type
        event_data: The event data containing tracking status
    """
    try:
        enabled = event_data.get("enabled", False)
        tracking_data = event_data.get("data", {})
        quality = event_data.get("quality", "unknown")
        
        # If we're using the complete VRFrame, let it handle the event details
        if hasattr(self, 'vr_frame') and self.vr_frame:
            # Update tracking status in VRFrame
            self.vr_frame.tracking_enabled = enabled
            
            # Update tracking data if provided
            if tracking_data:
                self.vr_frame.tracking_data = tracking_data
            
            # Update tracking quality
            self.vr_frame.tracking_quality = quality
            
            # Update tracking checkbox if it exists
            if hasattr(self.vr_frame, 'tracking_var'):
                self.vr_frame.tracking_var.set(enabled)
            
            # Update status indicators if they exist
            if "tracking" in self.vr_frame.status_indicators:
                status_text = f"Enabled ({quality})" if enabled else "Disabled"
                self.vr_frame.status_indicators["tracking"].config(text=status_text)
            
            # Update status message in VR frame
            self.vr_frame._add_status_message(f"Tracking {'enabled' if enabled else 'disabled'} (Quality: {quality})", 
                                              "success" if enabled else "info")
        elif hasattr(self, 'vr_status'):
            status = "Enabled" if enabled else "Disabled"
            self.vr_status.config(text=f"Status: Tracking {status} (Quality: {quality})")
            
        logger.info(f"VR tracking {'enabled' if enabled else 'disabled'} with quality {quality}")
    except Exception as e:
        logger.error(f"Error handling VR tracking status event: {e}")

async def _handle_vr_device_status(self, event_type: str, event_data: dict) -> None:
    """Handle VR device status events.
    
    Args:
        event_type: The event type
        event_data: The event data containing device status info
    """
    try:
        battery = event_data.get("battery", {})
        connection_strength = event_data.get("connection_strength", 0)
        latency = event_data.get("latency", 0)
        
        # If we're using the complete VRFrame, let it handle the event details
        if hasattr(self, 'vr_frame') and self.vr_frame:
            # Update battery levels
            if battery:
                self.vr_frame.battery_level = battery
            
            # Update status indicators if they exist
            if "battery_headset" in self.vr_frame.status_indicators and "headset" in battery:
                self.vr_frame.status_indicators["battery_headset"].config(text=f"{battery['headset']}%")
                
            if "battery_left" in self.vr_frame.status_indicators and "left" in battery:
                self.vr_frame.status_indicators["battery_left"].config(text=f"{battery['left']}%")
                
            if "battery_right" in self.vr_frame.status_indicators and "right" in battery:
                self.vr_frame.status_indicators["battery_right"].config(text=f"{battery['right']}%")
                
            if "connection" in self.vr_frame.status_indicators:
                self.vr_frame.status_indicators["connection"].config(text=f"{connection_strength}%")
                
            if "latency" in self.vr_frame.status_indicators:
                self.vr_frame.status_indicators["latency"].config(text=f"{latency}ms")
            
            # Update status message in VR frame
            self.vr_frame._add_status_message(f"Device status updated - Connection: {connection_strength}%, Latency: {latency}ms", 
                                             "info")
        
        logger.info(f"VR device status update received - Battery: {battery}, Connection: {connection_strength}%, Latency: {latency}ms")
    except Exception as e:
        logger.error(f"Error handling VR device status event: {e}")

async def _handle_vr_error(self, event_type: str, event_data: dict) -> None:
    """Handle VR error events.
    
    Args:
        event_type: The event type
        event_data: The event data containing error info
    """
    try:
        error_type = event_data.get("type", "unknown")
        message = event_data.get("message", "Unknown error")
        
        # If we're using the complete VRFrame, let it handle the event details
        if hasattr(self, 'vr_frame') and self.vr_frame:
            # Update status message in VR frame with error
            self.vr_frame._add_status_message(f"Error: {message}", "error")
            
            # Reset connection state if it's a connection error
            if error_type == "connection":
                self.vr_frame.connected = False
                if "connect" in self.vr_frame.control_buttons:
                    self.vr_frame.control_buttons["connect"].config(state="normal")
                if "disconnect" in self.vr_frame.control_buttons:
                    self.vr_frame.control_buttons["disconnect"].config(state="disabled")
        elif hasattr(self, 'vr_status'):
            self.vr_status.config(text=f"Error: {message}")
            
        logger.error(f"VR error ({error_type}): {message}")
    except Exception as e:
        logger.error(f"Error handling VR error event: {e}")

# Additional VR interaction methods

def _on_tracking_reset_clicked(self):
    """Handle reset tracking button click."""
    try:
        # Update status
        self._add_status_message("Resetting tracking...", "info")
        
        # Send tracking reset request
        self._publish_event("vr.tracking.reset", {})
    except Exception as e:
        logger.error(f"Error resetting tracking: {e}")
        self._add_status_message(f"Tracking reset error: {e}", "error")

def _on_tracking_toggle_clicked(self):
    """Handle toggle tracking button click."""
    try:
        enable = not self.tracking_enabled
        
        # Update status
        action = "Enabling" if enable else "Disabling"
        self._add_status_message(f"{action} tracking...", "info")
        
        # Send tracking toggle request
        self._publish_event("vr.tracking.toggle", {
            "enable": enable
        })
    except Exception as e:
        logger.error(f"Error toggling tracking: {e}")
        self._add_status_message(f"Tracking toggle error: {e}", "error")

def _on_environment_change(self, environment):
    """Handle environment change.
    
    Args:
        environment: The environment name to change to
    """
    try:
        # Update status
        self._add_status_message(f"Changing environment to {environment}...", "info")
        
        # Send environment change request
        self._publish_event("vr.environment.change", {
            "environment": environment
        })
    except Exception as e:
        logger.error(f"Error changing environment: {e}")
        self._add_status_message(f"Environment change error: {e}", "error")
