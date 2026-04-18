"""
Public interface methods for VRFrame to support TabManager integration.
These methods should be added to the VRFrame class to ensure proper communication
between TabManager and VRFrame without exposing protected methods.
"""

# Public methods to add to VRFrame class

def add_status_message(self, message, message_type="info"):
    """Add a status message to the status panel.
    
    Args:
        message: The message to add
        message_type: The type of message (info, success, warning, error)
    """
    # Call the protected method
    self._add_status_message(message, message_type)

def change_environment(self, environment):
    """Change the VR environment.
    
    Args:
        environment: The environment to change to
    """
    # Update UI
    self.add_status_message(f"Changing environment to {environment}...", "info")
    
    # Update environment variable if it exists
    if hasattr(self, 'environment_var'):
        self.environment_var.set(environment)
    
    # Send environment change request to event bus
    if self.event_bus:
        # Create async task to avoid blocking
        import asyncio
        asyncio.create_task(self.event_bus.publish("vr.environment.change", {
            "environment": environment
        }))
    else:
        self.add_status_message("No event bus available", "error")

def reset_tracking(self):
    """Reset VR tracking."""
    # Update status
    self.add_status_message("Resetting tracking...", "info")
    
    # Send tracking reset request to event bus
    if self.event_bus:
        # Create async task to avoid blocking
        import asyncio
        asyncio.create_task(self.event_bus.publish("vr.tracking.reset", {}))
    else:
        self.add_status_message("No event bus available", "error")

def toggle_tracking(self, enable=None):
    """Toggle VR tracking.
    
    Args:
        enable: Whether to enable tracking, if None toggles current state
    """
    # Determine enable state
    if enable is None:
        enable = not self.tracking_enabled
        
    # Update status
    action = "Enabling" if enable else "Disabling"
    self.add_status_message(f"{action} tracking...", "info")
    
    # Send tracking toggle request to event bus
    if self.event_bus:
        # Create async task to avoid blocking
        import asyncio
        asyncio.create_task(self.event_bus.publish("vr.tracking.toggle", {
            "enable": enable
        }))
    else:
        self.add_status_message("No event bus available", "error")

def connect_device(self, device=None, wireless=None, ip=None, adb_path=None):
    """Connect to a VR device.
    
    Args:
        device: Device to connect to, if None uses current selection
        wireless: Whether to use wireless mode, if None uses current setting
        ip: IP address for wireless connection, if None uses current entry
        adb_path: Path to ADB for wireless connection, if None uses current entry
    """
    # Get device from dropdown if not specified
    if device is None and hasattr(self, 'device_var'):
        device = self.device_var.get()
    elif device is None:
        device = self.vr_device
        
    # Get wireless mode from checkbox if not specified
    if wireless is None and hasattr(self, 'wireless_var'):
        wireless = bool(self.wireless_var.get())
    elif wireless is None:
        wireless = self.wireless_mode
        
    # Get IP and ADB path from entries if not specified
    if wireless:
        if ip is None and hasattr(self, 'ip_entry'):
            ip = self.ip_entry.get().strip()
        elif ip is None:
            ip = self.device_ip
            
        if adb_path is None and hasattr(self, 'adb_entry'):
            adb_path = self.adb_entry.get().strip()
        elif adb_path is None:
            adb_path = self.adb_path
    
    # Validate inputs for wireless mode
    if wireless and (not ip or not adb_path):
        self.add_status_message("IP address and ADB path are required for wireless mode", "error")
        return
    
    # Update status
    self.add_status_message(f"Connecting to {device}...", "info")
    
    # Send connect request to event bus
    if self.event_bus:
        # Create connection request data
        data = {
            "device": device,
            "wireless": wireless
        }
        
        # Add wireless configuration if needed
        if wireless:
            data["ip"] = ip
            data["adb_path"] = adb_path
        
        # Create async task to avoid blocking
        import asyncio
        asyncio.create_task(self.event_bus.publish("vr.connect", data))
    else:
        self.add_status_message("No event bus available", "error")

def disconnect_device(self):
    """Disconnect from the current VR device."""
    # Update status
    self.add_status_message("Disconnecting from VR device...", "info")
    
    # Send disconnect request to event bus
    if self.event_bus:
        # Create async task to avoid blocking
        import asyncio
        asyncio.create_task(self.event_bus.publish("vr.disconnect", {}))
    else:
        self.add_status_message("No event bus available", "error")
