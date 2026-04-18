#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Communications Tab Initialization for Kingdom AI - SOTA 2026

This module provides the initialization function for the Communications tab,
integrating with the TabIntegrationMaster for unified tab management.

Features:
- Full-spectrum RF communications (ELF to mmWave)
- Real-time spectrum analyzer with FFT
- Two-way radio TX/RX with power control
- Sonar, video, and voice call integration
- Event bus driven architecture
"""

import logging
from typing import Optional, Any

logger = logging.getLogger("KingdomAI.CommsTabInit")


def _init_comms_tab(self) -> Optional[Any]:
    """
    Initialize the Communications tab with radio/sonar/video/call capabilities.
    
    This function is bound to the TabManager instance via TabIntegrationMaster.
    It creates the ThothCommunicationsTab widget with proper event bus integration.
    
    Args:
        self: TabManager instance (bound via __get__)
        
    Returns:
        ThothCommunicationsTab widget or None if initialization fails
    """
    try:
        from gui.qt_frames.thoth_comms_tab import ThothCommunicationsTab
        
        # Get event bus from TabManager
        event_bus = getattr(self, 'event_bus', None)
        
        # Create the Communications tab widget
        comms_tab = ThothCommunicationsTab(event_bus=event_bus)
        
        # Register tab for lifecycle management
        if hasattr(self, '_register_tab_widget'):
            self._register_tab_widget('comms', comms_tab)
        
        logger.info("✅ Communications tab initialized successfully")
        return comms_tab
        
    except ImportError as e:
        logger.error(f"Failed to import ThothCommunicationsTab: {e}")
        return None
    except Exception as e:
        logger.error(f"Error initializing Communications tab: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def update_comms_scan(self, event_data: dict):
    """
    Handle communications scan response events.
    
    Args:
        self: TabManager instance
        event_data: Scan results data
    """
    try:
        capabilities = event_data.get('capabilities', {})
        logger.info(f"Comms scan complete: {len(capabilities)} capabilities detected")
        
        # Forward to comms tab if available
        if hasattr(self, 'tab_widgets') and 'comms' in self.tab_widgets:
            comms_tab = self.tab_widgets['comms']
            if hasattr(comms_tab, 'update_capabilities'):
                from utils.qt_thread_safe import run_on_main_thread
                run_on_main_thread(lambda: comms_tab.update_capabilities(capabilities))
                
    except Exception as e:
        logger.error(f"Error handling comms scan event: {e}")


def update_comms_radio(self, event_data: dict):
    """
    Handle radio transmit/receive response events.
    
    Args:
        self: TabManager instance
        event_data: Radio operation data
    """
    try:
        success = event_data.get('success', False)
        operation = event_data.get('operation', 'unknown')
        logger.debug(f"Radio operation {operation}: {'success' if success else 'failed'}")
        
    except Exception as e:
        logger.error(f"Error handling radio event: {e}")


def update_comms_sonar(self, event_data: dict):
    """
    Handle sonar start/stop response events.
    
    Args:
        self: TabManager instance
        event_data: Sonar operation data
    """
    try:
        success = event_data.get('success', False)
        logger.debug(f"Sonar operation: {'success' if success else 'failed'}")
        
    except Exception as e:
        logger.error(f"Error handling sonar event: {e}")


def update_comms_call(self, event_data: dict):
    """
    Handle voice call start/stop response events.
    
    Args:
        self: TabManager instance
        event_data: Call operation data
    """
    try:
        success = event_data.get('success', False)
        call_id = event_data.get('call_id', 'unknown')
        logger.debug(f"Call operation {call_id}: {'success' if success else 'failed'}")
        
    except Exception as e:
        logger.error(f"Error handling call event: {e}")


def update_comms_status(self, event_data: dict):
    """
    Handle communications status update events.
    
    Args:
        self: TabManager instance
        event_data: Status data
    """
    try:
        status = event_data.get('status', 'unknown')
        logger.debug(f"Comms status update: {status}")
        
    except Exception as e:
        logger.error(f"Error handling comms status event: {e}")


# Export for import
__all__ = [
    '_init_comms_tab',
    'update_comms_scan',
    'update_comms_radio',
    'update_comms_sonar',
    'update_comms_call',
    'update_comms_status'
]
