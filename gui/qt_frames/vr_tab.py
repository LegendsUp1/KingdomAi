#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VR Tab for Kingdom AI

This is a wrapper class for the VRQTTab to ensure consistent
integration with the main window's TabManager.
"""

import asyncio
import logging
import traceback
import sys
from typing import Optional, Any

# PyQt imports
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal

# STATE-OF-THE-ART 2025: Component Factory
from gui.qt_frames.component_factory import ComponentFactory, ComponentConfig

# VR system components
from gui.qt_frames.vr_qt_tab import VRQTTab

# Event bus for pub/sub messaging
from core.event_bus import EventBus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VRTab(QWidget):
    """VR Tab wrapper for integration with the main window's TabManager.
    
    This class wraps the VRQTTab to ensure consistent integration
    with the main window's TabManager. It provides a simplified interface
    while delegating the actual functionality to the VRQTTab.
    """
    
    def __init__(self, parent=None, event_bus=None):
        """Initialize the VR Tab with parent and event bus.
        
        Args:
            parent: Parent widget
            event_bus: EventBus instance for pub/sub messaging
        """
        super().__init__(parent)
        self.parent = parent
        # Use provided event bus or get singleton instance
        if event_bus is None:
            from core.event_bus import EventBus
            self.event_bus = EventBus.get_instance() if hasattr(EventBus, 'get_instance') else EventBus()
            self._log("⚠️ VRTab: No event_bus provided, using singleton/new instance")
        else:
            self.event_bus = event_bus
            self._log("✅ VRTab: Using provided global event_bus")
        
        # Initialize VRQTTab
        try:
            self._log("Initializing VR Tab...")
            self.vr_tab = VRQTTab(parent=self, event_bus=self.event_bus)
            
            # Set up layout
            from PyQt6.QtWidgets import QVBoxLayout
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.vr_tab)
            self.setLayout(layout)
            
            self._log("VR Tab initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize VR Tab: {str(e)}\n{traceback.format_exc()}")
            self._log(f"WARNING: VR Tab initialization failed, using placeholder: {e}", level=logging.WARNING)
            # Graceful fallback - show placeholder instead of crashing
            from PyQt6.QtWidgets import QVBoxLayout, QLabel
            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)
            placeholder = QLabel("VR System Unavailable\n\nVR initialization failed. Check logs for details.")
            placeholder.setStyleSheet("color: #ff8080; font-size: 14px;")
            layout.addWidget(placeholder)
            self.setLayout(layout)
            self.vr_tab = None
    
    def _log(self, message, level=logging.INFO):
        """Log a message both to the logger and to the application status display.
        
        Args:
            message: Message to log
            level: Logging level
        """
        if level == logging.INFO:
            logger.info(message)
        elif level == logging.WARNING:
            logger.warning(message)
        elif level == logging.ERROR:
            logger.error(message)
        elif level == logging.CRITICAL:
            logger.critical(message)
        
        # Publish to event bus if available
        if self.event_bus:
            if hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync(
                    "system.log", 
                    {
                        "message": message,
                        "level": logging.getLevelName(level),
                        "source": "VRTab"
                    }
                )
            else:
                try:
                    # EventBus.publish is synchronous
                    self.event_bus.publish(
                        "system.log", 
                        {
                            "message": message,
                            "level": logging.getLevelName(level),
                            "source": "vr_tab"
                        }
                    )
                except Exception:
                    pass  # Ignore logging failures during init

    def subscribe_to_events(self):
        """Subscribe to event bus events.
        
        This method delegates to the VRQTTab's subscribe_to_events method.
        """
        if hasattr(self.vr_tab, 'subscribe_to_events'):
            self.vr_tab.subscribe_to_events()
        else:
            self._log("VRQTTab doesn't have subscribe_to_events method", logging.WARNING)
