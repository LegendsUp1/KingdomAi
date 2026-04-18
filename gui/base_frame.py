#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Base Frame Module.

This module provides the base frame class for all tab frames in Kingdom AI.
Implemented with PyQt6 with no Tkinter fallbacks.
"""

from PyQt6.QtWidgets import QFrame, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
import logging
import asyncio
import traceback
import os
import json
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

class BaseFrame(QFrame):
    """Base frame for all tab frames in Kingdom AI."""
    
    # Signal for status updates
    statusChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None, event_bus=None, api_key_connector=None, **kwargs):
        """Initialize the base frame.
        
        Args:
            parent: Parent widget
            event_bus: Event bus for communication
            api_key_connector: Connector for accessing API keys
            **kwargs: Additional keyword arguments for QFrame
        """
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.event_bus = event_bus
        self.api_key_connector = api_key_connector
        self.logger = logging.getLogger(f"BaseFrame.{self.__class__.__name__}")
        self.components = {}
        self._initialized = False
        self.status_ready = False
        self.api_keys = {}
        self._status_color = "gray"

    def initialize(self):
        """Initialize the frame.
        
        Override this method in derived classes to add custom initialization.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            # Load API keys if available
            self._load_api_keys()
            
            # Setup UI and connect events
            self._setup_ui()
            self._connect_events()
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing {self.__class__.__name__}: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _setup_ui(self):
        """Set up the user interface.
        
        Override this method in derived classes to add custom UI elements.
        In PyQt6, this typically involves creating layouts and adding widgets.
        """
        # PyQt6 specific setup (to be overridden by subclasses)
        self.setLayout(None)  # Child classes should set their own layout
        
    def _load_api_keys(self):
        """Load API keys from the api_key_connector or configuration files.
        
        This method attempts to load API keys from multiple sources in this order:
        1. From the api_key_connector if available
        2. From config/api_keys.json
        3. From config/api_keys.env
        """
        try:
            # First try to get API keys from the connector
            if self.api_key_connector:
                self.logger.debug("Loading API keys from API Key Connector")
                # For async compatibility, we'll use the sync version since this is called during initialization
                available_services = self.api_key_connector.list_available_services_sync()
                for service in available_services:
                    self.api_keys[service] = self.api_key_connector.get_api_key_sync(service)
                    
                if self.api_keys:
                    self.logger.info(f"Loaded API keys for {len(self.api_keys)} services from API Key Connector")
                    return
            
            # If connector didn't provide keys, try loading from files
            self._load_api_keys_from_files()
            
        except Exception as e:
            self.logger.error(f"Error loading API keys: {e}")
            self.logger.error(traceback.format_exc())
    
    def _load_api_keys_from_files(self):
        """Load API keys from configuration files."""
        try:
            # Check for API keys in JSON file
            api_keys_json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'api_keys.json')
            if os.path.exists(api_keys_json_path):
                with open(api_keys_json_path, 'r', encoding='utf-8') as f:
                    try:
                        keys_data = json.load(f)
                        if keys_data and isinstance(keys_data, dict):
                            self.api_keys.update(keys_data)
                            self.logger.info(f"Loaded API keys from {api_keys_json_path}")
                    except json.JSONDecodeError:
                        self.logger.error(f"Error parsing API keys JSON from {api_keys_json_path}")
            
            # Check for API keys in .env file
            api_keys_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'api_keys.env')
            if os.path.exists(api_keys_env_path):
                try:
                    import dotenv
                    env_vars = dotenv.dotenv_values(api_keys_env_path)
                    
                    # Process environment variables for known patterns
                    services = {}
                    for key, value in env_vars.items():
                        # Skip empty values and comments
                        if not value or key.startswith('#'):
                            continue
                            
                        # Extract service name and key type
                        if '_API_KEY' in key:
                            service = key.split('_API_KEY')[0].lower()
                            if service not in services:
                                services[service] = {}
                            services[service]['api_key'] = value
                        elif '_SECRET_KEY' in key or '_API_SECRET' in key:
                            service = key.split('_SECRET')[0].lower()
                            if service not in services:
                                services[service] = {}
                            services[service]['api_secret'] = value
                    
                    # Add to existing API keys
                    for service, key_data in services.items():
                        if service not in self.api_keys:
                            self.api_keys[service] = {}
                        self.api_keys[service].update(key_data)
                    
                    self.logger.info(f"Loaded API keys from {api_keys_env_path}")
                except ImportError:
                    self.logger.warning("python-dotenv package not available, skipping .env file parsing")
        except Exception as e:
            self.logger.error(f"Error loading API keys from files: {e}")
            self.logger.error(traceback.format_exc())
    
    async def get_api_key(self, service: str) -> Dict[str, Any]:
        """Get API key for a specific service asynchronously.
        
        This method first checks the local cache, then tries to get the key
        from the API Key Connector if available.
        
        Args:
            service: The service name to get the API key for
            
        Returns:
            Dict containing the API key information or empty dict if not found
        """
        # Check if we already have the key locally
        if service in self.api_keys:
            return self.api_keys[service]
            
        # Try to get from connector asynchronously
        if self.api_key_connector:
            try:
                key_data = await self.api_key_connector.get_api_key(service)
                if key_data:
                    # Update local cache
                    self.api_keys[service] = key_data
                    return key_data
            except Exception as e:
                self.logger.error(f"Error getting API key for {service}: {e}")
        
        # If not found, return empty dict
        return {}
    
    def get_api_key_sync(self, service: str) -> Dict[str, Any]:
        """Get API key for a specific service synchronously.
        
        This method only checks the local cache and does not make any
        asynchronous requests.
        
        Args:
            service: The service name to get the API key for
            
        Returns:
            Dict containing the API key information or empty dict if not found
        """
        return self.api_keys.get(service, {})
    
    def _connect_events(self):
        """Connect events to handlers.
        
        Override this method in derived classes to add custom event connections.
        """
        # Default implementation does nothing
        pass
    
    async def safe_publish(self, event, data=None):
        """Safely publish an event to the event bus.
        
        Args:
            event (str): Event name
            data (dict, optional): Event data
        
        Returns:
            bool: True if event was published successfully
        """
        if self.event_bus is None:
            self.logger.warning(f"Cannot publish event {event}: event_bus is None")
            return False
            
        try:
            # Create a coroutine that directly awaits the event bus publish
            async def publish_event():
                await self.event_bus.publish(event, data)
                
            # Run the coroutine
            await publish_event()
            return True
        except Exception as e:
            self.logger.error(f"Error publishing event {event}: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    def safe_publish_sync(self, event, data=None):
        """Synchronous version of safe_publish for use in slots and other non-async contexts.
        
        Args:
            event (str): Event name
            data (dict, optional): Event data
        
        Returns:
            bool: True if event was published successfully
        """
        if self.event_bus is None:
            self.logger.warning(f"Cannot publish event {event}: event_bus is None")
            return False
            
        try:
            # For synchronous contexts in PyQt6, we need to ensure the event is dispatched properly
            # Using asyncio.create_task to avoid blocking the GUI thread
            asyncio.create_task(self.safe_publish(event, data))
            return True
        except Exception as e:
            self.logger.error(f"Error scheduling event {event}: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def create_status_indicator(self, parent=None):
        """Create a PyQt6 status indicator widget.
        
        Args:
            parent: Parent widget for the status indicator
            
        Returns:
            QWidget: A status indicator widget
        """
        from PyQt6.QtWidgets import QWidget
        from PyQt6.QtCore import QSize
        
        if parent is None:
            parent = self
            
        indicator = QWidget(parent)
        indicator.setMinimumSize(QSize(16, 16))
        indicator.setMaximumSize(QSize(16, 16))
        indicator.setStyleSheet(f"background-color: {self._status_color}; border-radius: 8px;")
        self.status_indicator = indicator
        return indicator
        
    def refresh(self):
        """Refresh the frame content.
        
        Override this method in derived classes to update UI with new data.
        
        Returns:
            bool: True if refresh was successful
        """
        # Default implementation does nothing
        return True
    
    def update_status(self, status):
        """Update the status of the frame.
        
        Args:
            status (dict): Status information
            
        Returns:
            bool: True if status update was successful
        """
        try:
            # Update status indicator if available
            if hasattr(self, 'status_indicator') and self.status_indicator:
                if status.get('status') == 'connected':
                    self._status_color = 'green'
                    self.status_ready = True
                elif status.get('status') == 'connecting':
                    self._status_color = 'yellow'
                    self.status_ready = False
                elif status.get('status') == 'disconnected':
                    self._status_color = 'red'
                    self.status_ready = False
                else:
                    self._status_color = 'gray'
                    self.status_ready = False
                    
                # Apply style using PyQt6 styling
                self.status_indicator.setStyleSheet(f"background-color: {self._status_color};")
                
                # Emit the signal with the status information
                self.statusChanged.emit(status)
            return True
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            return False
