#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Sleep Manager Component
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, Any, List, Optional, Union, Callable

# Try to import psutil for resource monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Configure logging
logger = logging.getLogger('kingdom_ai.sleep_manager')

class SleepManager:
    """Power-saving sleep mode manager for continuous operation.
    
    This class implements sleep mode management for Kingdom AI during periods of
    inactivity to save power while maintaining essential functionality.
    """
    
    def __init__(self, event_bus, config=None):
        """Initialize the sleep manager.
        
        Args:
            event_bus: System event bus for communication
            config: Configuration dictionary
        """
        self.event_bus = event_bus
        self.config = config or {}
        self.running = False
        
        # Sleep mode configuration
        self.sleep_enabled = self.config.get("enable_sleep_mode", True)
        self.inactivity_threshold = self.config.get("sleep_inactivity_threshold", 1800)  # 30 minutes
        self.resource_check_interval = self.config.get("resource_check_interval", 60)  # 1 minute
        
        # Sleep state tracking
        self.in_sleep_mode = False
        self.last_activity_time = time.time()
        self.last_resource_check = time.time()
        
        # Resource thresholds for sleep mode
        self.cpu_threshold = self.config.get("sleep_cpu_threshold", 0.3)  # CPU below 30%
        self.memory_threshold = self.config.get("sleep_memory_threshold", 0.7)  # Memory below 70%
        
        # Components to pause in sleep mode
        self.sleepable_components = self.config.get("sleepable_components", [
            "GUIManager", "VoiceAssistant", "APIGateway"
        ])
        
        # Register event handlers
        self._register_events()
        
        logger.info("Sleep Manager initialized successfully")
        self.running = True
    
    def _register_events(self):
        """Register event handlers for activity-related events."""
        try:
            if self.event_bus:
                # Subscribe to events - FIXED: EventBus methods are now sync
                self.event_bus.subscribe("user.activity", self._handle_user_activity)
                self.event_bus.subscribe("voice.command", self._handle_user_activity)
                self.event_bus.subscribe("system.resource_status", self._handle_resource_status)
                logger.debug("Sleep Manager event handlers registered")
        except Exception as e:
            logger.error(f"Failed to register Sleep Manager event handlers: {str(e)}")
    
    def _handle_user_activity(self, event):
        """Handle any user activity event to reset inactivity timer."""
        self.last_activity_time = time.time()
        
        # If in sleep mode, exit immediately on user activity
        if self.in_sleep_mode:
            self.exit_sleep_mode()
    
    def _handle_resource_status(self, event):
        """Handle system resource status events."""
        # Update last resource check time
        self.last_resource_check = time.time()
        
        # Get resource information
        cpu_usage = event.get("cpu_usage", 0.0)
        memory_usage = event.get("memory_usage", 0.0)
        
        # If resources are critical, consider sleep mode regardless of activity
        if cpu_usage > 0.9 or memory_usage > 0.9:
            logger.warning(f"Critical resource usage detected: CPU {cpu_usage:.2f}, Memory {memory_usage:.2f}")
            
            # Publish resource warning
            if self.event_bus:
                self.event_bus.publish("system.warning", {
                    "source": "SleepManager",
                    "message": "Critical resource usage detected",
                    "data": {
                        "cpu_usage": cpu_usage,
                        "memory_usage": memory_usage
                    }
                })
                
            # If not in sleep mode and sleep is enabled, consider entering sleep
            if not self.in_sleep_mode and self.sleep_enabled:
                # Only enter sleep if no critical tasks are running
                # This would need to check with TaskManager for critical tasks
                self.enter_sleep_mode()
    
    def should_enter_sleep_mode(self):
        """Determine if the system should enter sleep mode based on activity and resources.
        
        Returns:
            bool: True if system should enter sleep mode
        """
        if not self.sleep_enabled or self.in_sleep_mode:
            return False
            
        current_time = time.time()
        
        # Check inactivity period
        inactive_time = current_time - self.last_activity_time
        if inactive_time < self.inactivity_threshold:
            return False
            
        # If we've been inactive long enough, check resources
        if current_time - self.last_resource_check > self.resource_check_interval:
            # Update resource usage
            if HAS_PSUTIL:
                try:
                    # Get CPU and memory usage
                    cpu_usage = psutil.cpu_percent(interval=0.1) / 100.0
                    memory_usage = psutil.virtual_memory().percent / 100.0
                    
                    # Publish resource status event
                    if self.event_bus:
                        self.event_bus.publish("system.resource_status", {
                            "cpu_usage": cpu_usage,
                            "memory_usage": memory_usage,
                            "timestamp": current_time
                        })
                    
                    self.last_resource_check = current_time
                        
                except Exception as e:
                    logger.error(f"Failed to check system resources: {str(e)}")
                    # Default to not sleeping if resource check fails
                    return False
            else:
                logger.warning("psutil not available, cannot check system resources for sleep decision")
                # Default to using only inactivity for sleep decision when psutil not available
                
        return True
    
    def should_exit_sleep_mode(self):
        """Determine if the system should exit sleep mode.
        
        Returns:
            bool: True if system should exit sleep mode
        """
        if not self.in_sleep_mode:
            return False
            
        # Check if there's been recent activity
        if time.time() - self.last_activity_time < 5:  # Exit immediately on activity
            return True
            
        return False
    
    def enter_sleep_mode(self):
        """Enter low-power sleep mode while maintaining critical functions."""
        if self.in_sleep_mode:
            return
            
        try:
            logger.info("Entering sleep mode")
            self.in_sleep_mode = True
            
            # Notify components to enter low-power mode
            if self.event_bus:
                self.event_bus.publish("system.sleep", {
                    "entering_sleep": True,
                    "timestamp": time.time(),
                    "components_to_sleep": self.sleepable_components
                })
                
            # Reduce polling intervals for components
            # (Implementation depends on components supporting sleep mode)
            
            # Keep wake word detector active
            # (This would normally keep minimal functionality active)
            
        except Exception as e:
            logger.error(f"Error entering sleep mode: {str(e)}")
            self.in_sleep_mode = False
    
    def exit_sleep_mode(self):
        """Exit sleep mode and restore full system functionality."""
        if not self.in_sleep_mode:
            return
            
        try:
            logger.info("Exiting sleep mode")
            self.in_sleep_mode = False
            
            # Reset activity timer
            self.last_activity_time = time.time()
            
            # Notify components to resume normal operation
            if self.event_bus:
                self.event_bus.publish("system.sleep", {
                    "entering_sleep": False,
                    "timestamp": time.time(),
                    "components_to_wake": self.sleepable_components
                })
                
            # Restore normal polling intervals
            # (Implementation depends on components supporting wake from sleep)
            
        except Exception as e:
            logger.error(f"Error exiting sleep mode: {str(e)}")
            # Force exit sleep mode anyway
            self.in_sleep_mode = False
    
    def shutdown(self):
        """Shut down the sleep manager cleanly."""
        logger.info("Shutting down Sleep Manager")
        self.running = False
        
        # Exit sleep mode if needed
        if self.in_sleep_mode:
            self.exit_sleep_mode()
