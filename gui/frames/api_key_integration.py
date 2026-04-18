#!/usr/bin/env python3
"""
API Key Integration for Kingdom AI GUI.
Provides immediate API key access during component initialization.
"""

import logging
import os
import json
import asyncio
import traceback
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class APIKeyIntegrationMixin:
    """Mixin class providing immediate API key access during initialization."""
    
    def __init__(self):
        """Initialize API key integration settings."""
        self.api_keys = {}
        self.api_key_sources = ["connector", "file", "env"]
    
    async def load_api_keys_immediate(self, service_types: list = None) -> Dict[str, Dict[str, Any]]:
        """
        Immediately load API keys during initialization.
        
        Args:
            service_types: Optional list of service types to load keys for
                          If None, loads all available keys
                          
        Returns:
            Dict: Mapping of service names to their API key data
        """
        loaded_keys = {}
        
        try:
            # Try all sources in order of preference
            for source in self.api_key_sources:
                if source == "connector" and hasattr(self, 'api_key_connector') and self.api_key_connector:
                    # Get keys from API key connector
                    if service_types:
                        for service_type in service_types:
                            key_data = await self._get_key_from_connector(service_type)
                            if key_data:
                                loaded_keys[service_type] = key_data
                                self.api_keys[service_type] = key_data
                    else:
                        # Get all available services
                        if hasattr(self.api_key_connector, 'list_available_services_sync'):
                            available_services = self.api_key_connector.list_available_services_sync()
                            for service in available_services:
                                key_data = await self._get_key_from_connector(service)
                                if key_data:
                                    loaded_keys[service] = key_data
                                    self.api_keys[service] = key_data
                
                elif source == "file":
                    # Try loading from config/api_keys.json
                    file_keys = await self._load_api_keys_from_file()
                    if file_keys:
                        for service, key_data in file_keys.items():
                            if not service in loaded_keys:  # Don't overwrite keys from connector
                                if not service_types or service in service_types:
                                    loaded_keys[service] = key_data
                                    self.api_keys[service] = key_data
                
                elif source == "env":
                    # Try loading from config/api_keys.env
                    env_keys = await self._load_api_keys_from_env()
                    if env_keys:
                        for service, key_data in env_keys.items():
                            if not service in loaded_keys:  # Don't overwrite keys from better sources
                                if not service_types or service in service_types:
                                    loaded_keys[service] = key_data
                                    self.api_keys[service] = key_data
            
            logger.info(f"Loaded {len(loaded_keys)} API keys during initialization")
            return loaded_keys
            
        except Exception as e:
            logger.error(f"Error loading API keys: {e}")
            logger.debug(traceback.format_exc())
            return {}
    
    async def _get_key_from_connector(self, service: str) -> Dict[str, Any]:
        """
        Get API key from connector with retry logic.
        
        Args:
            service: Service name to get key for
            
        Returns:
            Dict: API key data or empty dict if not found
        """
        if not hasattr(self, 'api_key_connector') or not self.api_key_connector:
            return {}
            
        try:
            # Try async version first
            if hasattr(self.api_key_connector, 'get_api_key'):
                if asyncio.iscoroutinefunction(self.api_key_connector.get_api_key):
                    key_data = await self.api_key_connector.get_api_key(service)
                else:
                    key_data = self.api_key_connector.get_api_key(service)
                
                if key_data:
                    return key_data
            
            # Fall back to sync version if async fails or doesn't exist
            if hasattr(self.api_key_connector, 'get_api_key_sync'):
                key_data = self.api_key_connector.get_api_key_sync(service)
                if key_data:
                    return key_data
                    
            return {}
            
        except Exception as e:
            logger.warning(f"Error getting API key for {service} from connector: {e}")
            return {}
    
    async def _load_api_keys_from_file(self) -> Dict[str, Dict[str, Any]]:
        """
        Load API keys from JSON file.
        
        Returns:
            Dict: Mapping of service names to their API key data
        """
        try:
            # Find config directory
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_dir = os.path.join(base_dir, 'config')
            api_keys_path = os.path.join(config_dir, 'api_keys.json')
            
            if not os.path.exists(api_keys_path):
                logger.warning(f"API keys file not found: {api_keys_path}")
                return {}
                
            with open(api_keys_path, 'r', encoding='utf-8') as f:
                keys_data = json.load(f)
                
            if not isinstance(keys_data, dict):
                logger.warning("Invalid API keys format, expected dictionary")
                return {}
                
            return keys_data
            
        except Exception as e:
            logger.warning(f"Error loading API keys from file: {e}")
            return {}
    
    async def _load_api_keys_from_env(self) -> Dict[str, Dict[str, Any]]:
        """
        Load API keys from environment file.
        
        Returns:
            Dict: Mapping of service names to their API key data
        """
        try:
            # Find config directory
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_dir = os.path.join(base_dir, 'config')
            env_path = os.path.join(config_dir, 'api_keys.env')
            
            if not os.path.exists(env_path):
                logger.warning(f"API keys env file not found: {env_path}")
                return {}
                
            # Parse env file
            keys_data = {}
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                        
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Extract service name from key format (e.g., BINANCE_API_KEY -> binance)
                        parts = key.lower().split('_')
                        if len(parts) >= 2:
                            service = parts[0]
                            key_type = '_'.join(parts[1:])
                            
                            if not service in keys_data:
                                keys_data[service] = {}
                                
                            keys_data[service][key_type] = value
                
            return keys_data
            
        except Exception as e:
            logger.warning(f"Error loading API keys from env file: {e}")
            return {}
