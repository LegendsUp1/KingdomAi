#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Device Manager Tab Initialization for Kingdom AI - SOTA 2026

This module provides the initialization function for the Device Manager tab,
integrating with the TabIntegrationMaster for unified tab management.

Features:
- Host device detection (USB, Serial, Bluetooth, Audio, Webcam, VR)
- Real-time device monitoring via event bus
- MCP tools integration for AI device control
- Thread-safe UI updates for device status changes
"""

import logging
from typing import Optional, Any

logger = logging.getLogger("KingdomAI.DeviceTabInit")


def _init_device_manager_tab(self) -> Optional[Any]:
    """
    Initialize the Device Manager tab with host device detection.
    
    This function is bound to the TabManager instance via TabIntegrationMaster.
    It creates the DeviceManagerTab widget with proper event bus integration.
    
    Args:
        self: TabManager instance (bound via __get__)
        
    Returns:
        DeviceManagerTab widget or None if initialization fails
    """
    try:
        from gui.qt_frames.device_manager_tab import DeviceManagerTab, DEVICE_MANAGER_AVAILABLE
        
        if not DEVICE_MANAGER_AVAILABLE:
            logger.warning("Device Manager dependencies not available")
            return None
        
        # Get event bus from TabManager
        event_bus = getattr(self, 'event_bus', None)
        
        # Create the Device Manager tab widget
        device_tab = DeviceManagerTab(event_bus=event_bus)
        
        # Register tab for lifecycle management
        if hasattr(self, '_register_tab_widget'):
            self._register_tab_widget('devices', device_tab)
        
        logger.info("✅ Device Manager tab initialized successfully")
        return device_tab
        
    except ImportError as e:
        logger.error(f"Failed to import DeviceManagerTab: {e}")
        return None
    except Exception as e:
        logger.error(f"Error initializing Device Manager tab: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def update_device_connected(self, event_data: dict):
    """
    Handle device connected events.
    
    Args:
        self: TabManager instance
        event_data: Device connection data
    """
    try:
        device_name = event_data.get('name', event_data.get('device_name', 'Unknown'))
        logger.info(f"Device connected: {device_name}")
        
        # Update device manager tab if available
        if hasattr(self, 'tab_widgets') and 'devices' in self.tab_widgets:
            device_tab = self.tab_widgets['devices']
            if hasattr(device_tab, '_populate_device_tree'):
                from utils.qt_thread_safe import run_on_main_thread
                run_on_main_thread(device_tab._populate_device_tree)
                
    except Exception as e:
        logger.error(f"Error handling device connected event: {e}")


def update_device_disconnected(self, event_data: dict):
    """
    Handle device disconnected events.
    
    Args:
        self: TabManager instance
        event_data: Device disconnection data
    """
    try:
        device_name = event_data.get('name', event_data.get('device_name', 'Unknown'))
        logger.info(f"Device disconnected: {device_name}")
        
        # Update device manager tab if available
        if hasattr(self, 'tab_widgets') and 'devices' in self.tab_widgets:
            device_tab = self.tab_widgets['devices']
            if hasattr(device_tab, '_populate_device_tree'):
                from utils.qt_thread_safe import run_on_main_thread
                run_on_main_thread(device_tab._populate_device_tree)
                
    except Exception as e:
        logger.error(f"Error handling device disconnected event: {e}")


def update_device_scan_complete(self, event_data: dict):
    """
    Handle device scan complete events.
    
    Args:
        self: TabManager instance
        event_data: Scan results data
    """
    try:
        total_devices = event_data.get('total_devices', 0)
        logger.info(f"Device scan complete: {total_devices} devices found")
        
        # Update device manager tab if available
        if hasattr(self, 'tab_widgets') and 'devices' in self.tab_widgets:
            device_tab = self.tab_widgets['devices']
            if hasattr(device_tab, '_populate_device_tree'):
                from utils.qt_thread_safe import run_on_main_thread
                run_on_main_thread(device_tab._populate_device_tree)
                
    except Exception as e:
        logger.error(f"Error handling device scan complete event: {e}")


def update_device_status(self, event_data: dict):
    """
    Handle device status update events.
    
    Args:
        self: TabManager instance
        event_data: Device status data
    """
    try:
        device_id = event_data.get('device_id', event_data.get('id', 'Unknown'))
        status = event_data.get('status', 'unknown')
        logger.debug(f"Device status update: {device_id} -> {status}")
        
        # Update device manager tab if available
        if hasattr(self, 'tab_widgets') and 'devices' in self.tab_widgets:
            device_tab = self.tab_widgets['devices']
            if hasattr(device_tab, '_populate_device_tree'):
                from utils.qt_thread_safe import run_on_main_thread
                run_on_main_thread(device_tab._populate_device_tree)
                
    except Exception as e:
        logger.error(f"Error handling device status event: {e}")


# Export for import
__all__ = [
    '_init_device_manager_tab',
    'update_device_connected',
    'update_device_disconnected',
    'update_device_scan_complete',
    'update_device_status'
]
