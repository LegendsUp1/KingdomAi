#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Sleep Manager Module

This module manages power-saving sleep mode during periods of inactivity
while maintaining wake word listening capabilities and monitoring system
resources to ensure continuous operation.
"""

import time
import logging
import threading
import datetime
from typing import Dict, Callable

# Set up logging
logger = logging.getLogger('KingdomAI.SleepManager')

class SleepManager:
    """
    Manages power-saving sleep mode during periods of inactivity.
    Maintains wake word listening even in sleep mode and automatically 
    exits sleep mode upon user activity.
    """
    
    def __init__(self, 
                 event_bus=None, 
                 inactivity_threshold: int = 300,  # 5 minutes
                 resource_check_interval: int = 60,  # 1 minute
                 resource_monitor=None):
        """
        Initialize the Sleep Manager.
        
        Args:
            event_bus: Event bus for publishing sleep events
            inactivity_threshold: Seconds of inactivity before entering sleep mode
            resource_check_interval: Interval for checking system resources
            resource_monitor: Reference to the resource monitor component
        """
        self.event_bus = event_bus
        self.inactivity_threshold = inactivity_threshold
        self.resource_check_interval = resource_check_interval
        self.resource_monitor = resource_monitor
        
        self.sleeping = False
        self.last_activity_time = time.time()
        self.sleep_start_time = None
        self.monitoring_thread = None
        self.running = False
        self.lock = threading.RLock()
        self.wake_word_active = True
        self.sleep_callbacks = {}
        self.wake_callbacks = {}
        self.intent_patterns = self._register_intent_patterns()
        
    def initialize(self) -> bool:
        """
        Initialize the Sleep Manager.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        logger.info("Initializing Sleep Manager")
        
        try:
            self.running = True
            self.last_activity_time = time.time()
            
            # Start monitoring thread
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                name="SleepMonitor",
                daemon=True
            )
            self.monitoring_thread.start()
            
            # Register event handlers
            if self.event_bus:
                self.event_bus.subscribe_sync('user.activity', self._handle_user_activity)
                self.event_bus.subscribe_sync('sleep.enter_requested', self._handle_sleep_request)
                self.event_bus.subscribe_sync('sleep.exit_requested', self._handle_wake_request)
                
            logger.info(f"Sleep Manager initialized with inactivity threshold of {self.inactivity_threshold}s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Sleep Manager: {e}")
            return False
            
    def shutdown(self):
        """Shutdown the Sleep Manager."""
        logger.info("Shutting down Sleep Manager")
        
        with self.lock:
            self.running = False
            self.wake_word_active = False
            
            # If sleeping, exit sleep mode
            if self.sleeping:
                self._exit_sleep_mode()
        
        # Wait for monitoring thread to complete
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=2.0)
            
        logger.info("Sleep Manager shutdown complete")
        
    def record_activity(self):
        """
        Record user activity to prevent or exit sleep mode.
        """
        with self.lock:
            self.last_activity_time = time.time()
            
            # If currently sleeping, exit sleep mode
            if self.sleeping:
                self._exit_sleep_mode()
                
    def enter_sleep_mode_manually(self) -> bool:
        """
        Manually enter sleep mode.
        
        Returns:
            bool: True if entered sleep mode, False otherwise
        """
        with self.lock:
            if self.sleeping:
                logger.debug("Already in sleep mode, ignoring manual sleep request")
                return False
                
            return self._enter_sleep_mode()
            
    def exit_sleep_mode_manually(self) -> bool:
        """
        Manually exit sleep mode.
        
        Returns:
            bool: True if exited sleep mode, False otherwise
        """
        with self.lock:
            if not self.sleeping:
                logger.debug("Not in sleep mode, ignoring manual wake request")
                return False
                
            return self._exit_sleep_mode()
            
    def is_sleeping(self) -> bool:
        """
        Check if the system is currently in sleep mode.
        
        Returns:
            bool: True if in sleep mode, False otherwise
        """
        with self.lock:
            return self.sleeping
            
    def get_sleep_status(self) -> Dict:
        """
        Get the current sleep status.
        
        Returns:
            Dict: Sleep status information
        """
        with self.lock:
            now = time.time()
            time_since_activity = now - self.last_activity_time
            time_to_sleep = max(0, self.inactivity_threshold - time_since_activity)
            
            if self.sleeping:
                sleep_duration = now - self.sleep_start_time if self.sleep_start_time else 0
            else:
                sleep_duration = 0
                
            return {
                "sleeping": self.sleeping,
                "wake_word_active": self.wake_word_active,
                "time_since_activity": time_since_activity,
                "time_to_sleep": time_to_sleep,
                "sleep_duration": sleep_duration,
                "inactivity_threshold": self.inactivity_threshold
            }
            
    def register_sleep_callback(self, name: str, callback: Callable) -> bool:
        """
        Register a callback to be called when entering sleep mode.
        
        Args:
            name: Name of the callback
            callback: Function to call when entering sleep mode
            
        Returns:
            bool: True if registered successfully, False otherwise
        """
        with self.lock:
            self.sleep_callbacks[name] = callback
            return True
            
    def register_wake_callback(self, name: str, callback: Callable) -> bool:
        """
        Register a callback to be called when exiting sleep mode.
        
        Args:
            name: Name of the callback
            callback: Function to call when exiting sleep mode
            
        Returns:
            bool: True if registered successfully, False otherwise
        """
        with self.lock:
            self.wake_callbacks[name] = callback
            return True
            
    def _monitoring_loop(self):
        """Background thread that monitors for inactivity and resource usage."""
        logger.debug("Sleep monitoring thread started")
        
        last_resource_check = time.time()
        
        while self.running:
            try:
                # Sleep for a short interval to prevent busy waiting
                time.sleep(1.0)
                
                now = time.time()
                
                # Check if we should enter sleep mode due to inactivity
                with self.lock:
                    if not self.sleeping and (now - self.last_activity_time) >= self.inactivity_threshold:
                        self._enter_sleep_mode()
                        
                # Periodically check system resources
                if (now - last_resource_check) >= self.resource_check_interval:
                    self._check_system_resources()
                    last_resource_check = now
                    
            except Exception as e:
                logger.error(f"Error in sleep monitoring loop: {e}")
                
    def _enter_sleep_mode(self) -> bool:
        """
        Enter sleep mode to conserve resources.
        
        Returns:
            bool: True if entered sleep mode, False otherwise
        """
        if self.sleeping:
            return False
            
        logger.info("Entering sleep mode")
        self.sleeping = True
        self.sleep_start_time = time.time()
        
        # Execute registered sleep callbacks
        for name, callback in self.sleep_callbacks.items():
            try:
                callback()
            except Exception as e:
                logger.error(f"Error executing sleep callback '{name}': {e}")
                
        # Publish sleep event
        if self.event_bus:
            self.event_bus.publish('sleep.entered', {
                'timestamp': datetime.datetime.now().isoformat(),
                'inactivity_duration': time.time() - self.last_activity_time,
                'wake_word_active': self.wake_word_active
            })
            
        return True
        
    def _exit_sleep_mode(self) -> bool:
        """
        Exit sleep mode and resume normal operation.
        
        Returns:
            bool: True if exited sleep mode, False otherwise
        """
        if not self.sleeping:
            return False
            
        logger.info("Exiting sleep mode")
        sleep_duration = time.time() - self.sleep_start_time if self.sleep_start_time else 0
        self.sleeping = False
        self.sleep_start_time = None
        self.last_activity_time = time.time()
        
        # Execute registered wake callbacks
        for name, callback in self.wake_callbacks.items():
            try:
                callback()
            except Exception as e:
                logger.error(f"Error executing wake callback '{name}': {e}")
                
        # Publish wake event
        if self.event_bus:
            self.event_bus.publish('sleep.exited', {
                'timestamp': datetime.datetime.now().isoformat(),
                'sleep_duration': sleep_duration,
                'reason': 'user_activity'
            })
            
        return True
        
    def _check_system_resources(self):
        """Check system resources and adjust sleep behavior if needed."""
        if not self.resource_monitor:
            return
            
        try:
            # Get current resource usage
            resource_info = self.resource_monitor.get_resource_usage()
            
            # Implement adaptive sleep behavior based on resource usage
            # For example, if CPU usage is very high, may need to force sleep
            cpu_usage = resource_info.get('cpu_percent', 0)
            memory_usage = resource_info.get('memory_percent', 0)
            
            # Example: If resources are critically low, force sleep mode
            if cpu_usage > 90 or memory_usage > 90:
                logger.warning(f"Critical resource usage (CPU: {cpu_usage}%, Memory: {memory_usage}%), forcing sleep mode")
                with self.lock:
                    if not self.sleeping:
                        self._enter_sleep_mode()
                        
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            
    def _handle_user_activity(self, event_data):
        """Handle user activity events from the event bus."""
        activity_type = event_data.get('activity_type', 'unknown')
        logger.debug(f"User activity detected: {activity_type}")
        self.record_activity()
        
    def _handle_sleep_request(self, event_data):
        """Handle sleep request events from the event bus."""
        logger.debug("Sleep mode requested via event bus")
        self.enter_sleep_mode_manually()
        
    def _handle_wake_request(self, event_data):
        """Handle wake request events from the event bus."""
        logger.debug("Wake requested via event bus")
        self.exit_sleep_mode_manually()
        
    def _register_intent_patterns(self) -> Dict:
        """
        Register intent patterns for sleep-related commands.
        
        Returns:
            Dict: Dictionary of intent patterns and their handlers
        """
        return {
            'sleep': {
                'patterns': [
                    "go to sleep",
                    "enter sleep mode",
                    "take a nap",
                    "sleep now",
                    "power down",
                    "conserve power",
                    "rest now"
                ],
                'handler': self.enter_sleep_mode_manually
            },
            'wake': {
                'patterns': [
                    "wake up",
                    "exit sleep mode",
                    "stop sleeping",
                    "power up",
                    "come back",
                    "resume operation",
                    "wake mode"
                ],
                'handler': self.exit_sleep_mode_manually
            },
            'sleep_status': {
                'patterns': [
                    "are you sleeping",
                    "sleep status",
                    "power status",
                    "are you awake",
                    "are you in sleep mode"
                ],
                'handler': self.get_sleep_status
            }
        }
