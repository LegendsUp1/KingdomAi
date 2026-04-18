#!/usr/bin/env python3
"""
API Connector Component for Kingdom AI System
Handles connections to various external APIs and allows runtime configuration
"""

import os
import json
import logging
import asyncio
import aiohttp
import base64
import hashlib
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path

# Ensure the logger is properly configured
logger = logging.getLogger('KingdomAI.APIConnector')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Import base component structure
from base_component import BaseComponent

class APIKeys:
    """Secure storage for API keys"""
    
    def __init__(self):
        self.keys = {}
        self.config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
        self.config_file = os.path.join(self.config_dir, 'api_keys.json')
        os.makedirs(self.config_dir, exist_ok=True)
        self._load_keys()
    
    def _load_keys(self):
        """Load API keys from encrypted storage"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    encrypted_data = f.read()
                    if encrypted_data:
                        # Simple XOR-based obfuscation, not real security but better than plaintext
                        machine_id = self._get_machine_id()
                        decrypted = self._xor_decrypt(encrypted_data, machine_id)
                        self.keys = json.loads(decrypted)
                        logging.info(f"Loaded {len(self.keys)} API keys from config")
        except Exception as e:
            logging.error(f"Error loading API keys: {e}")
            self.keys = {}
    
    def _save_keys(self):
        """Save API keys to encrypted storage"""
        try:
            # Simple XOR-based obfuscation
            machine_id = self._get_machine_id()
            data_str = json.dumps(self.keys)
            encrypted = self._xor_encrypt(data_str, machine_id)
            
            with open(self.config_file, 'w') as f:
                f.write(encrypted)
            logging.info(f"Saved {len(self.keys)} API keys to config")
            return True
        except Exception as e:
            logging.error(f"Error saving API keys: {e}")
            return False
    
    def _get_machine_id(self) -> str:
        """Get a unique machine identifier for encryption"""
        try:
            # Try to create a somewhat stable machine identifier
            import platform
            machine_info = platform.node() + platform.machine() + platform.processor()
            return hashlib.sha256(machine_info.encode()).hexdigest()[:32]  # Return first 32 chars for compatibility
        except:
            # Fallback to a default value
            return "KingdomAI2025QuantumNexus"
    
    def _xor_encrypt(self, data: str, key: str) -> str:
        """Simple XOR encryption for basic obfuscation"""
        encrypted = []
        for i, char in enumerate(data):
            key_char = key[i % len(key)]
            encrypted_char = chr(ord(char) ^ ord(key_char))
            encrypted.append(encrypted_char)
        return base64.b64encode(''.join(encrypted).encode()).decode()
    
    def _xor_decrypt(self, encrypted_data: str, key: str) -> str:
        """Simple XOR decryption"""
        try:
            data = base64.b64decode(encrypted_data).decode()
            decrypted = []
            for i, char in enumerate(data):
                key_char = key[i % len(key)]
                decrypted_char = chr(ord(char) ^ ord(key_char))
                decrypted.append(decrypted_char)
            return ''.join(decrypted)
        except Exception as e:
            logging.error(f"Decryption error: {e}")
            return "{}"
    
    def get_key(self, service_name: str) -> Optional[str]:
        """Get API key for a specific service"""
        return self.keys.get(service_name)
    
    def set_key(self, service_name: str, api_key: str) -> bool:
        """Set API key for a specific service"""
        if not service_name or not api_key:
            return False
        
        self.keys[service_name] = api_key
        return self._save_keys()
    
    def delete_key(self, service_name: str) -> bool:
        """Delete API key for a specific service"""
        if service_name in self.keys:
            del self.keys[service_name]
            return self._save_keys()
        return False
    
    def list_services(self) -> List[str]:
        """List all services with saved API keys"""
        return list(self.keys.keys())


class APIConnector(BaseComponent):
    """Component for managing connections to external APIs"""
    
    def __init__(self, event_bus=None, monitor=None):
        # Initialize BaseComponent 
        super().__init__(monitor=monitor)
        # Store the event bus
        self._event_bus = None
        self.logger = logging.getLogger('KingdomAI.APIConnector')
        
        # Initialize other attributes
        self.keys = APIKeys()
        self.sessions = {}
        
        # Initialize API status
        self.status = {}
        
        # Set the event bus and register handlers
        if event_bus is not None:
            self.set_event_bus(event_bus)
    
    def set_event_bus(self, event_bus):
        """Set the event bus for this component."""
        self._event_bus = event_bus
        if self._event_bus is not None:
            self._register_event_handlers()
            
    def _register_event_handlers(self):
        """Register event handlers with the event bus."""
        if self._event_bus:
            # Create an async task to handle event subscriptions
            asyncio.create_task(self._async_register_handlers())
            
    async def _async_register_handlers(self):
        """Register event handlers asynchronously with proper awaiting."""
        if not self._event_bus:
            return
            
        try:
            # Check if the subscribe method is a coroutine function
            if asyncio.iscoroutinefunction(self._event_bus.subscribe):
                # Await each subscription properly
                await self._event_bus.subscribe("api.test_key", self.test_api_key_handler)
                await self._event_bus.subscribe("api.add_key", self.add_api_key_handler)
                await self._event_bus.subscribe("api.delete_key", self.delete_api_key_handler)
                await self._event_bus.subscribe("api.get_keys", self.get_api_keys_handler)
            else:
                # Call synchronously if not a coroutine function
                self._event_bus.subscribe("api.test_key", self.test_api_key_handler)
                self._event_bus.subscribe("api.add_key", self.add_api_key_handler)
                self._event_bus.subscribe("api.delete_key", self.delete_api_key_handler)
                self._event_bus.subscribe("api.get_keys", self.get_api_keys_handler)
                
            self.logger.info("✅ Successfully registered API connector event handlers")
        except Exception as e:
            self.logger.error(f"❌ Failed to register API connector event handlers: {e}")
            self.logger.error(traceback.format_exc())
                
    def test_api_key_handler(self, data):
        """Handle API key test requests."""
        self.logger.info(f"Testing API key for service: {data.get('service')}")
        # Add implementation here
        
    def add_api_key_handler(self, data):
        """Handle adding API keys."""
        self.logger.info(f"Adding API key for service: {data.get('service')}")
        # Add implementation here
        
    def delete_api_key_handler(self, data):
        """Handle deleting API keys."""
        self.logger.info(f"Deleting API key for service: {data.get('service')}")
        # Add implementation here
        
    def get_api_keys_handler(self, data):
        """Handle getting API keys."""
        self.logger.info("Getting all API keys")
        # Add implementation here
        self.apis = {
            "binance": {
                "base_url": "https://api.binance.com",
                "test_endpoint": "/api/v3/ping",
                "description": "Cryptocurrency exchange API",
                "required_keys": ["api_key", "api_secret"],
                "status": "disconnected"
            },
            "coinbase": {
                "base_url": "https://api.coinbase.com",
                "test_endpoint": "/v2/currencies",
                "description": "Cryptocurrency exchange API",
                "required_keys": ["api_key", "api_secret"]
            },
            "openai": {
                "base_url": "https://api.openai.com",
                "test_endpoint": "/v1/models",
                "description": "AI model API for GPT",
                "required_keys": ["api_key"]
            },
            "mining_pool": {
                "base_url": "https://pool.example.com",
                "test_endpoint": "/api/stats",
                "description": "Mining pool API",
                "required_keys": ["api_key"]
            },
            "custom": {
                "base_url": "",
                "test_endpoint": "",
                "description": "Custom API endpoint",
                "required_keys": ["api_key"]
            }
        }
    
    async def initialize(self, config=None) -> bool:
        """Initialize the API connector component"""
        self.logger.info("Initializing API Connector...")
        
        try:
            # Store config if provided
            if config:
                self._config = config
                
            # Subscribe to events
            if self._event_bus:
                self._event_bus.subscribe("api.update_config", self._handle_update_config)
                self._event_bus.subscribe("api.test_connection", self._handle_test_connection)
                self._event_bus.subscribe("api.get_services", self._handle_get_services)
                self._event_bus.subscribe("api.get_config", self._handle_get_config)
            else:
                self.logger.warning("No event bus available, API connector functionality will be limited")
            
            # Create aiohttp ClientSession for API requests
            self.session = aiohttp.ClientSession()
            
            # Log all available APIs
            self.logger.info(f"API Connector initialized with {len(self.apis)} API definitions")
            
            # Set initialization flag
            self._initialized = True
            self.logger.info("API connector initialized successfully")
            # Log all available APIs
            self.logger.info(f"API Connector initialized with {len(self.apis)} API definitions")
            
            # Load saved API keys and test connections
            services_with_keys = self.keys.list_services()
            self.logger.info(f"Found {len(services_with_keys)} saved API configurations")
            
            # Publish initialization success
            if self._event_bus:
                self._event_bus.publish("api.status", {
                    "status": "initialized",
                    "available_services": list(self.apis.keys()),
                    "configured_services": services_with_keys
                })
            
            return True
        except Exception as e:
            self.logger.error(f"Error initializing API Connector: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """Clean up resources used by the API connector"""
        try:
            # Close any active sessions
            if hasattr(self, 'session') and self.session:
                await self.session.close()
            
            # Close any API-specific sessions
            for service, session in self.sessions.items():
                if session:
                    await session.close()
            
            self.logger.info("API Connector resources cleaned up")
            return True
        except Exception as e:
            self.logger.error(f"Error during API Connector cleanup: {e}")
            return False
    
    async def _handle_update_config(self, data: Dict[str, Any]) -> None:
        """Handle event to update API configuration"""
        try:
            service = data.get("service")
            api_key = data.get("api_key")
            api_secret = data.get("api_secret", "")
            
            if not service or not api_key:
                self.logger.error("Missing required parameters for API config update")
                if self._event_bus:
                    self._event_bus.publish("api.update_result", {
                        "success": False,
                        "service": service,
                        "error": "Missing required parameters"
                    })
                return
            
            # For services that need both key and secret
            if service in ["binance", "coinbase"] and not api_secret:
                self.logger.error(f"{service} requires both API key and secret")
                if self._event_bus:
                    self._event_bus.publish("api.update_result", {
                        "success": False,
                        "service": service,
                        "error": "API secret is required"
                    })
                return
            
            # Store the API key
            key_data = {"api_key": api_key}
            if api_secret:
                key_data["api_secret"] = api_secret
            
            success = self.keys.set_key(service, json.dumps(key_data))
            
            if success:
                self.logger.info(f"Updated API configuration for {service}")
                # Test the connection with new credentials
                test_result = await self._test_api_connection(service)
                
                if self._event_bus:
                    self._event_bus.publish("api.update_result", {
                        "success": True,
                        "service": service,
                        "connection_test": test_result
                    })
            else:
                self.logger.error(f"Failed to update API configuration for {service}")
                if self._event_bus:
                    self._event_bus.publish("api.update_result", {
                        "success": False,
                        "service": service,
                        "error": "Failed to save configuration"
                    })
        
        except Exception as e:
            self.logger.error(f"Error handling API config update: {e}")
            if self._event_bus:
                self._event_bus.publish("api.update_result", {
                    "success": False,
                    "service": data.get("service", "unknown"),
                    "error": str(e)
                })
    
    async def _handle_test_connection(self, data: Dict[str, Any]) -> None:
        """Handle event to test API connection"""
        try:
            service = data.get("service")
            if not service:
                self.logger.error("Missing service parameter for connection test")
                if self._event_bus:
                    self._event_bus.publish("api.test_result", {
                        "success": False,
                        "error": "Missing service parameter"
                    })
                return
            
            test_result = await self._test_api_connection(service)
            
            if self._event_bus:
                self._event_bus.publish("api.test_result", {
                    "service": service,
                    "success": test_result.get("success", False),
                    "message": test_result.get("message", "Unknown error"),
                    "timestamp": test_result.get("timestamp", 0)
                })
        
        except Exception as e:
            self.logger.error(f"Error testing API connection: {e}")
            if self._event_bus:
                self._event_bus.publish("api.test_result", {
                    "service": data.get("service", "unknown"),
                    "success": False,
                    "message": str(e),
                    "timestamp": int(time.time())
                })
    
    async def _handle_get_services(self, data: Dict[str, Any]) -> None:
        """Handle event to get available API services"""
        try:
            configured_services = self.keys.list_services()
            
            if self._event_bus:
                self._event_bus.publish("api.services", {
                    "available": list(self.apis.keys()),
                    "configured": configured_services,
                    "definitions": self.apis
                })
        
        except Exception as e:
            self.logger.error(f"Error getting API services: {e}")
            if self._event_bus:
                self._event_bus.publish("api.services", {
                    "error": str(e)
                })
    
    async def _handle_get_config(self, data: Dict[str, Any]) -> None:
        """Handle event to get API configuration"""
        try:
            service = data.get("service")
            if not service:
                self.logger.error("Missing service parameter for get config")
                if self._event_bus:
                    self._event_bus.publish("api.config", {
                        "success": False,
                        "error": "Missing service parameter"
                    })
                return
            
            # Get API key for the requested service
            api_key_data = self.keys.get_key(service)
            
            # Mask the actual key values for security
            masked_config = {}
            if api_key_data:
                try:
                    config = json.loads(api_key_data)
                    for key, value in config.items():
                        if value:
                            # Show first 4 and last 4 characters, mask the rest
                            if len(value) > 8:
                                masked_config[key] = value[:4] + "*" * (len(value) - 8) + value[-4:]
                            else:
                                masked_config[key] = "********"
                except:
                    masked_config = {"error": "Invalid configuration format"}
            
            if self._event_bus:
                self._event_bus.publish("api.config", {
                    "service": service,
                    "config": masked_config,
                    "has_config": bool(api_key_data)
                })
        
        except Exception as e:
            self.logger.error(f"Error getting API config: {e}")
            if self._event_bus:
                self._event_bus.publish("api.config", {
                    "service": data.get("service", "unknown"),
                    "success": False,
                    "error": str(e)
                })
    
    async def _test_api_connection(self, service: str) -> Dict[str, Any]:
        """Test connection to an API service"""
        import time
        
        if service not in self.apis:
            return {
                "success": False,
                "message": f"Unknown service: {service}",
                "timestamp": int(time.time())
            }
        
        # Get the API key data
        api_key_data = self.keys.get_key(service)
        if not api_key_data:
            return {
                "success": False,
                "message": f"No API key configured for {service}",
                "timestamp": int(time.time())
            }
        
        try:
            # Parse API key data
            config = json.loads(api_key_data)
            
            # Get API definition
            api_def = self.apis[service]
            base_url = api_def["base_url"]
            test_endpoint = api_def["test_endpoint"]
            
            # Skip test for custom API if no base URL is set
            if service == "custom" and not base_url:
                return {
                    "success": False,
                    "message": "Custom API has no base URL configured",
                    "timestamp": int(time.time())
                }
            
            # Create headers with API key
            headers = {}
            if "api_key" in config:
                if service == "openai":
                    headers["Authorization"] = f"Bearer {config['api_key']}"
                else:
                    headers["X-API-Key"] = config["api_key"]
            
            # Full test URL
            test_url = f"{base_url}{test_endpoint}"
            
            # Make the request
            async with self.session.get(test_url, headers=headers, timeout=10) as response:
                status = response.status
                
                if status == 200:
                    return {
                        "success": True,
                        "message": f"Successfully connected to {service} API",
                        "timestamp": int(time.time()),
                        "status_code": status
                    }
                else:
                    return {
                        "success": False,
                        "message": f"API returned status code {status}",
                        "timestamp": int(time.time()),
                        "status_code": status
                    }
        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "message": f"Connection to {service} API timed out",
                "timestamp": int(time.time())
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error connecting to {service} API: {str(e)}",
                "timestamp": int(time.time())
            }
    
    async def make_api_request(self, service: str, endpoint: str, method: str = "GET", 
                              data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an API request to a configured service"""
        if service not in self.apis:
            return {
                "success": False,
                "error": f"Unknown service: {service}"
            }
        
        # Get the API key data
        api_key_data = self.keys.get_key(service)
        if not api_key_data:
            return {
                "success": False,
                "error": f"No API key configured for {service}"
            }
        
        try:
            # Parse API key data
            config = json.loads(api_key_data)
            
            # Get API definition
            api_def = self.apis[service]
            base_url = api_def["base_url"]
            
            if not base_url:
                return {
                    "success": False,
                    "error": f"No base URL configured for {service}"
                }
            
            # Create headers with API key
            headers = {}
            if "api_key" in config:
                if service == "openai":
                    headers["Authorization"] = f"Bearer {config['api_key']}"
                else:
                    headers["X-API-Key"] = config["api_key"]
            
            # Add Content-Type for POST requests
            if method in ["POST", "PUT", "PATCH"] and data:
                headers["Content-Type"] = "application/json"
            
            # Full request URL
            request_url = f"{base_url}{endpoint}"
            
            # Make the request based on the method
            if method == "GET":
                async with self.session.get(request_url, headers=headers, params=params, timeout=30) as response:
                    status = response.status
                    try:
                        response_data = await response.json()
                    except:
                        response_data = await response.text()
                    
                    return {
                        "success": status < 400,
                        "status_code": status,
                        "data": response_data
                    }
            
            elif method == "POST":
                async with self.session.post(request_url, headers=headers, json=data, params=params, timeout=30) as response:
                    status = response.status
                    try:
                        response_data = await response.json()
                    except:
                        response_data = await response.text()
                    
                    return {
                        "success": status < 400,
                        "status_code": status,
                        "data": response_data
                    }
            
            elif method == "PUT":
                async with self.session.put(request_url, headers=headers, json=data, params=params, timeout=30) as response:
                    status = response.status
                    try:
                        response_data = await response.json()
                    except:
                        response_data = await response.text()
                    
                    return {
                        "success": status < 400,
                        "status_code": status,
                        "data": response_data
                    }
            
            elif method == "DELETE":
                async with self.session.delete(request_url, headers=headers, params=params, timeout=30) as response:
                    status = response.status
                    try:
                        response_data = await response.json()
                    except:
                        response_data = await response.text()
                    
                    return {
                        "success": status < 400,
                        "status_code": status,
                        "data": response_data
                    }
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported HTTP method: {method}"
                }
        
        except Exception as e:
            self.logger.error(f"Error making API request to {service}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
