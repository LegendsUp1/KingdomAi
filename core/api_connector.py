#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
APIConnector for Kingdom AI.

This module provides a standardized interface for interacting with various APIs,
handling authentication, rate limiting, error management, and response parsing.
"""

import os
import sys
import time
import json
import logging
import threading
import hashlib
import hmac
import base64
import urllib.parse
import asyncio
import traceback
from typing import Dict, List, Any, Optional, Union, Tuple, Callable

class APIConnector:
    """
    API Connector for the Kingdom AI system.
    
    Provides a standardized interface for interacting with various APIs,
    including authentication, rate limiting, error management, and response parsing.
    """
    
    def __init__(self, event_bus=None, config=None, network_manager=None, security_manager=None):
        """
        Initialize the API Connector.
        
        Args:
            event_bus: The system's event bus for communication
            config: Configuration dictionary
            network_manager: The NetworkManager instance for making requests
            security_manager: The SecurityManager instance for secure API access
        """
        self.event_bus = event_bus
        self.config = config or {}
        self.network_manager = network_manager
        self.security_manager = security_manager
        self.logger = logging.getLogger('APIConnector')
        
        # API endpoints and credentials
        self.api_endpoints = self.config.get('api_endpoints', {})
        self.api_keys = {}
        self.api_secrets = {}
        
        # Load API credentials if security manager is available
        if self.security_manager:
            self._load_api_credentials()
        
        # API usage tracking
        self.api_usage = {}
        self.api_usage_lock = threading.Lock()
        
        # API rate limits
        self.rate_limits = self.config.get('api_rate_limits', {})
        
        # Default headers
        self.default_headers = {
            'User-Agent': self.config.get('user_agent', 'Kingdom-AI/1.0'),
            'Accept': 'application/json'
        }
        
        # Response parsing configuration
        self.response_parsers = {}
        
        # Register built-in parsers
        self._register_default_parsers()
        
        # Request retry settings
        self.max_retries = self.config.get('api_max_retries', 3)
        self.retry_delay = self.config.get('api_retry_delay', 1.0)
        
        # API request queue for async processing
        self.request_queue = []
        self.queue_lock = threading.Lock()
        self.processing_thread = None
        self.processing_active = False
    
    def initialize(self) -> bool:
        """
        Initialize the APIConnector and register event handlers.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            if self.event_bus:
                self.logger.info("Registering API event handlers")
                self.event_bus.subscribe_sync('api.request', self.handle_api_request_event)
                self.event_bus.subscribe_sync('api.register_parser', self.register_parser_event)
                self.event_bus.subscribe_sync('api.reload_endpoints', self.reload_endpoints)
                
            # Start async request processor if configured
            if self.config.get('enable_async_api_requests', True):
                self._start_async_processor()
            
            self.logger.info("APIConnector initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize APIConnector: {str(e)}")
            return False
    
    def _load_api_credentials(self) -> None:
        """
        Load API credentials from the security manager.
        """
        try:
            # Get API keys
            api_keys = self.security_manager.get_secret('api_keys') or {}
            if api_keys and isinstance(api_keys, dict):
                self.api_keys = api_keys
                self.logger.info(f"Loaded {len(self.api_keys)} API keys")
            
            # Get API secrets
            api_secrets = self.security_manager.get_secret('api_secrets') or {}
            if api_secrets and isinstance(api_secrets, dict):
                self.api_secrets = api_secrets
                self.logger.info(f"Loaded {len(self.api_secrets)} API secrets")
                
        except Exception as e:
            self.logger.error(f"Failed to load API credentials: {str(e)}")
    
    def _register_default_parsers(self) -> None:
        """
        Register default response parsers for common API formats.
        """
        # JSON parser
        self.register_parser('json', self._parse_json_response)
        
        # XML parser (if xmltodict is available)
        try:
            import xmltodict
            self.register_parser('xml', self._parse_xml_response)
        except ImportError:
            self.logger.warning("xmltodict not available, XML parsing disabled")
        
        # CSV parser
        self.register_parser('csv', self._parse_csv_response)
    
    def _start_async_processor(self) -> None:
        """
        Start the asynchronous API request processor thread.
        """
        def process_requests():
            self.logger.info("Starting asynchronous API request processor")
            self.processing_active = True
            
            while self.processing_active:
                try:
                    # Get a request from the queue
                    request = None
                    with self.queue_lock:
                        if self.request_queue:
                            request = self.request_queue.pop(0)
                    
                    # Process the request if there is one
                    if request:
                        endpoint, params, callback, request_id = request
                        self._process_api_request(endpoint, params, callback, request_id)
                    else:
                        # Sleep to avoid busy waiting
                        time.sleep(0.1)
                        
                except Exception as e:
                    self.logger.error(f"Error in API request processor: {str(e)}")
        
        self.processing_thread = threading.Thread(target=process_requests, daemon=True)
        self.processing_thread.start()
    
    def reload_endpoints(self, event_data: Any = None) -> None:
        """
        Reload API endpoints from configuration.
        
        Args:
            event_data: Optional event data (not used)
        """
        try:
            if self.config:
                self.api_endpoints = self.config.get('api_endpoints', {})
                self.logger.info(f"Reloaded {len(self.api_endpoints)} API endpoints")
        except Exception as e:
            self.logger.error(f"Failed to reload API endpoints: {str(e)}")
    
    def register_parser(self, content_type: str, parser_func: Callable) -> None:
        """
        Register a response parser for a specific content type.
        
        Args:
            content_type: Content type identifier
            parser_func: Function to parse the response
        """
        if callable(parser_func):
            self.response_parsers[content_type] = parser_func
            self.logger.debug(f"Registered parser for content type: {content_type}")
        else:
            self.logger.warning(f"Attempted to register non-callable parser for {content_type}")
    
    def register_parser_event(self, event_data: Dict) -> None:
        """
        Handle API parser registration events.
        
        Args:
            event_data: Event data containing parser information
        """
        if not isinstance(event_data, dict):
            self.logger.error("Invalid event data for api.register_parser event")
            return
        
        content_type = event_data.get('content_type')
        module_name = event_data.get('module')
        function_name = event_data.get('function')
        
        if not all([content_type, module_name, function_name]):
            self.logger.error("Missing required parameters for parser registration")
            return
        
        try:
            # Import the module dynamically
            module = importlib.import_module(module_name)
            parser_func = getattr(module, function_name)
            
            # Register the parser
            self.register_parser(content_type, parser_func)
            
        except Exception as e:
            self.logger.error(f"Failed to register parser: {str(e)}")
    
    def _parse_json_response(self, response_text: str) -> Any:
        """
        Parse JSON response data.
        
        Args:
            response_text: JSON response as text
            
        Returns:
            Any: Parsed JSON data
        """
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {str(e)}")
            return None
    
    def _parse_xml_response(self, response_text: str) -> Any:
        """
        Parse XML response data.
        
        Args:
            response_text: XML response as text
            
        Returns:
            Any: Parsed XML data as dict
        """
        try:
            import xmltodict
            return xmltodict.parse(response_text)
        except Exception as e:
            self.logger.error(f"XML parse error: {str(e)}")
            return None
    
    def _parse_csv_response(self, response_text: str) -> List[Dict]:
        """
        Parse CSV response data.
        
        Args:
            response_text: CSV response as text
            
        Returns:
            List[Dict]: List of dictionaries representing CSV rows
        """
        try:
            import csv
            from io import StringIO
            
            result = []
            csv_file = StringIO(response_text)
            reader = csv.DictReader(csv_file)
            
            for row in reader:
                result.append(dict(row))
                
            return result
            
        except Exception as e:
            self.logger.error(f"CSV parse error: {str(e)}")
            return None
    
    def safe_publish_event(self, event_name, event_data):
        """
        Safely publish an event to the event bus from a synchronous context.
        
        This method handles publishing events from synchronous callbacks without needing
        to directly await the coroutine, avoiding 'coroutine was never awaited' warnings.
        
        Args:
            event_name: Name of the event to publish
            event_data: Data to include with the event
        """
        if not self.event_bus:
            return
            
        # Get the current event loop or create a new one if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a task that will be executed in the running event loop
                asyncio.create_task(self._safe_publish_async(event_name, event_data))
            else:
                # Run directly in the idle loop
                loop.run_until_complete(self._safe_publish_async(event_name, event_data))
        except RuntimeError as e:
            self.logger.error(f"Error getting event loop in safe_publish_event: {e}")
            # As a fallback, we'll just log the event data since we can't publish it properly
            self.logger.info(f"Unpublished event '{event_name}': {event_data}")
    
    async def _safe_publish_async(self, event_name, event_data):
        """
        Async helper for safe_publish_event.
        
        Args:
            event_name: Name of the event to publish
            event_data: Data to include with the event
        """
        try:
            # Additional null check to be extra safe
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                await self.event_bus.publish(event_name, event_data)
            else:
                self.logger.warning(f"Cannot publish event '{event_name}': event_bus is not available")
        except Exception as e:
            self.logger.error(f"Error publishing event {event_name}: {e}")
            self.logger.debug(f"Event publish error details: {traceback.format_exc()}")
            
    def _get_endpoint_config(self, endpoint_name: str) -> Dict:
        """
        Get configuration for a specific API endpoint.
        
        Args:
            endpoint_name: Name of the endpoint
            
        Returns:
            Dict: Endpoint configuration
        """
        return self.api_endpoints.get(endpoint_name, {})
    
    def _build_url(self, endpoint_config: Dict, params: Dict = None) -> str:
        """
        Build the full URL for an API request.
        
        Args:
            endpoint_config: Endpoint configuration
            params: URL parameters to include
            
        Returns:
            str: Full URL
        """
        base_url = endpoint_config.get('base_url', '')
        path = endpoint_config.get('path', '')
        
        # Replace path parameters
        if params and path:
            for key, value in params.items():
                placeholder = f"{{{key}}}"
                if placeholder in path:
                    path = path.replace(placeholder, str(value))
        
        # Combine base URL and path
        url = base_url
        if path:
            url = urllib.parse.urljoin(url, path)
        
        return url
    
    def _prepare_headers(self, endpoint_config: Dict, params: Dict = None) -> Dict:
        """
        Prepare headers for an API request.
        
        Args:
            endpoint_config: Endpoint configuration
            params: Request parameters
            
        Returns:
            Dict: Headers for the request
        """
        # Start with default headers
        headers = dict(self.default_headers)
        
        # Add endpoint-specific headers
        endpoint_headers = endpoint_config.get('headers', {})
        headers.update(endpoint_headers)
        
        # Add auth headers if authentication is required
        auth_type = endpoint_config.get('auth_type')
        if auth_type:
            auth_headers = self._get_auth_headers(endpoint_config, params)
            headers.update(auth_headers)
        
        return headers
    
    def _get_auth_headers(self, endpoint_config: Dict, params: Dict = None) -> Dict:
        """
        Get authentication headers for an API request.
        
        Args:
            endpoint_config: Endpoint configuration
            params: Request parameters
            
        Returns:
            Dict: Authentication headers
        """
        auth_headers = {}
        auth_type = endpoint_config.get('auth_type')
        
        if auth_type == 'api_key':
            # API Key authentication
            api_key_name = endpoint_config.get('api_key_name', 'X-API-Key')
            api_key_source = endpoint_config.get('api_key_source', 'header')
            api_key_id = endpoint_config.get('api_key_id')
            
            if api_key_id and api_key_id in self.api_keys:
                api_key = self.api_keys[api_key_id]
                
                if api_key_source == 'header':
                    auth_headers[api_key_name] = api_key
            
        elif auth_type == 'basic':
            # Basic authentication
            username = endpoint_config.get('username')
            password = endpoint_config.get('password')
            
            if username and password:
                auth_string = f"{username}:{password}"
                encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
                auth_headers['Authorization'] = f"Basic {encoded_auth}"
                
        elif auth_type == 'bearer':
            # Bearer token authentication
            token_id = endpoint_config.get('token_id')
            
            if token_id and token_id in self.api_keys:
                token = self.api_keys[token_id]
                auth_headers['Authorization'] = f"Bearer {token}"
                
        elif auth_type == 'hmac':
            # HMAC signature authentication
            key_id = endpoint_config.get('key_id')
            secret_id = endpoint_config.get('secret_id')
            
            if key_id and secret_id and key_id in self.api_keys and secret_id in self.api_secrets:
                api_key = self.api_keys[key_id]
                api_secret = self.api_secrets[secret_id]
                
                # Create HMAC signature
                timestamp = str(int(time.time()))
                message = timestamp
                
                if params:
                    # Include sorted params in signature
                    param_str = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
                    message += param_str
                
                signature = hmac.new(
                    api_secret.encode('utf-8'),
                    message.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                # Add authentication headers
                auth_headers['X-API-Key'] = api_key
                auth_headers['X-Signature'] = signature
                auth_headers['X-Timestamp'] = timestamp
        
        return auth_headers
    
    def _prepare_data(self, endpoint_config: Dict, params: Dict = None) -> Tuple[Dict, Dict, Dict]:
        """
        Prepare data for an API request.
        
        Args:
            endpoint_config: Endpoint configuration
            params: Request parameters
            
        Returns:
            Tuple[Dict, Dict, Dict]: URL parameters, form data, and JSON data
        """
        url_params = {}
        form_data = {}
        json_data = {}
        
        if not params:
            return url_params, form_data, json_data
        
        # Determine parameter types based on endpoint configuration
        param_locations = endpoint_config.get('param_locations', {})
        default_location = endpoint_config.get('default_param_location', 'query')
        
        for key, value in params.items():
            # Get parameter location for this key
            location = param_locations.get(key, default_location)
            
            if location == 'query':
                url_params[key] = value
            elif location == 'form':
                form_data[key] = value
            elif location == 'json':
                json_data[key] = value
        
        return url_params, form_data, json_data
    
    def _track_api_usage(self, endpoint_name: str) -> None:
        """
        Track API usage for rate limiting.
        
        Args:
            endpoint_name: Name of the API endpoint
        """
        with self.api_usage_lock:
            current_time = time.time()
            
            if endpoint_name not in self.api_usage:
                self.api_usage[endpoint_name] = []
            
            # Add this request to usage tracking
            self.api_usage[endpoint_name].append(current_time)
            
            # Clean up old entries (older than 1 hour)
            one_hour_ago = current_time - 3600
            self.api_usage[endpoint_name] = [t for t in self.api_usage[endpoint_name] if t > one_hour_ago]
    
    def _check_rate_limit(self, endpoint_name: str) -> bool:
        """
        Check if the current request would exceed the rate limit.
        
        Args:
            endpoint_name: Name of the API endpoint
            
        Returns:
            bool: True if under limit, False if limit would be exceeded
        """
        with self.api_usage_lock:
            current_time = time.time()
            
            # Get rate limit configuration
            rate_limit = self.rate_limits.get(endpoint_name)
            if not rate_limit:
                return True  # No rate limit configured
                
            requests_per_minute = rate_limit.get('requests_per_minute')
            requests_per_hour = rate_limit.get('requests_per_hour')
            requests_per_day = rate_limit.get('requests_per_day')
            
            # Get usage for this endpoint
            usage = self.api_usage.get(endpoint_name, [])
            
            # Check minute limit
            if requests_per_minute:
                one_minute_ago = current_time - 60
                minute_usage = len([t for t in usage if t > one_minute_ago])
                if minute_usage >= requests_per_minute:
                    return False
            
            # Check hour limit
            if requests_per_hour:
                one_hour_ago = current_time - 3600
                hour_usage = len([t for t in usage if t > one_hour_ago])
                if hour_usage >= requests_per_hour:
                    return False
            
            # Check day limit
            if requests_per_day:
                one_day_ago = current_time - 86400
                day_usage = len([t for t in usage if t > one_day_ago])
                if day_usage >= requests_per_day:
                    return False
            
            return True
    
    def call_api(self, endpoint_name: str, params: Dict = None, 
                retry: bool = True, async_call: bool = False,
                callback: Callable = None) -> Tuple[bool, Any, Dict]:
        """
        Make an API request.
        
        Args:
            endpoint_name: Name of the API endpoint
            params: Parameters for the request
            retry: Whether to retry failed requests
            async_call: Whether to make the request asynchronously
            callback: Function to call with results (for async requests)
            
        Returns:
            Tuple[bool, Any, Dict]: (success, response_data, metadata)
        """
        params = params or {}
        
        # Check if endpoint exists
        endpoint_config = self._get_endpoint_config(endpoint_name)
        if not endpoint_config:
            error_msg = f"Unknown API endpoint: {endpoint_name}"
            self.logger.error(error_msg)
            return False, None, {'error': 'unknown_endpoint'}
        
        # Check if NetworkManager is available
        if not self.network_manager:
            error_msg = "NetworkManager is not available"
            self.logger.error(error_msg)
            return False, None, {'error': 'network_manager_unavailable'}
        
        # Handle async requests
        if async_call:
            request_id = self.config.get('request_id_prefix', 'api_') + str(int(time.time() * 1000))
            
            with self.queue_lock:
                self.request_queue.append((endpoint_name, params, callback, request_id))
            
            return True, None, {'request_id': request_id, 'status': 'queued'}
        
        # Process synchronous requests
        return self._process_api_request(endpoint_name, params, callback)
    
    def _process_api_request(self, endpoint_name: str, params: Dict = None,
                           callback: Callable = None, request_id: str = None) -> Tuple[bool, Any, Dict]:
        """
        Process an API request (internal method).
        
        Args:
            endpoint_name: Name of the API endpoint
            params: Parameters for the request
            callback: Function to call with results
            request_id: Unique identifier for the request
            
        Returns:
            Tuple[bool, Any, Dict]: (success, response_data, metadata)
        """
        endpoint_config = self._get_endpoint_config(endpoint_name)
        
        # Check rate limit
        if not self._check_rate_limit(endpoint_name):
            error_msg = f"Rate limit exceeded for endpoint: {endpoint_name}"
            self.logger.warning(error_msg)
            result = (False, None, {'error': 'rate_limit_exceeded'})
            
            if callback:
                try:
                    callback(*result)
                except Exception as e:
                    self.logger.error(f"Error in API callback: {str(e)}")
            
            return result
        
        # Track API usage
        self._track_api_usage(endpoint_name)
        
        try:
            # Build request URL and headers
            url = self._build_url(endpoint_config, params)
            headers = self._prepare_headers(endpoint_config, params)
            
            # Prepare request data
            method = endpoint_config.get('method', 'GET').upper()
            url_params, form_data, json_data = self._prepare_data(endpoint_config, params)
            
            # Add content type header for JSON requests
            if json_data and 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
            
            # Make the request
            success, response_data, metadata = self.network_manager.make_request(
                url=url,
                method=method,
                headers=headers,
                params=url_params,
                data=form_data,
                json_data=json_data,
                timeout=endpoint_config.get('timeout')
            )
            
            # Parse response if needed
            if success and isinstance(response_data, str):
                content_type = metadata.get('headers', {}).get('Content-Type', '')
                
                if 'application/json' in content_type:
                    parser = self.response_parsers.get('json')
                    if parser:
                        response_data = parser(response_data) or response_data
                
                elif 'application/xml' in content_type or 'text/xml' in content_type:
                    parser = self.response_parsers.get('xml')
                    if parser:
                        response_data = parser(response_data) or response_data
                
                elif 'text/csv' in content_type:
                    parser = self.response_parsers.get('csv')
                    if parser:
                        response_data = parser(response_data) or response_data
            
            # Add endpoint name to metadata
            metadata['endpoint'] = endpoint_name
            if request_id:
                metadata['request_id'] = request_id
            
            # Call the callback if provided
            if callback:
                try:
                    callback(success, response_data, metadata)
                except Exception as e:
                    self.logger.error(f"Error in API callback: {str(e)}")
            
            return success, response_data, metadata
            
        except Exception as e:
            self.logger.error(f"Error making API request to {endpoint_name}: {str(e)}")
            result = (False, None, {'error': 'api_request_error', 'message': str(e)})
            
            if callback:
                try:
                    callback(*result)
                except Exception as e:
                    self.logger.error(f"Error in API callback: {str(e)}")
            
            return result
    
    async def handle_api_request_event(self, event_data: Dict) -> None:
        """
        Handle API request events from the event bus.
        
        Args:
            event_data: Event data containing request details
        """
        if not isinstance(event_data, dict):
            self.logger.error("Invalid event data for api.request event")
            return
        
        # Extract request parameters from event data
        endpoint = event_data.get('endpoint')
        params = event_data.get('params', {})
        request_id = event_data.get('request_id', str(int(time.time() * 1000)))
        
        if not endpoint:
            self.logger.error("Missing endpoint in api.request event")
            if self.event_bus:
                # EventBus.publish is synchronous in this codebase.
                self.event_bus.publish('api.response', {
                    'success': False,
                    'error': 'missing_endpoint',
                    'request_id': request_id
                })
            return
        
        # Define callback to publish response to event bus
        # Using a synchronous-safe approach to avoid 'coroutine never awaited' warnings
        def _callback(success, response_data, metadata):
            if self.event_bus:
                # Use our safe_publish_event method to handle the async call properly
                self.safe_publish_event('api.response', {
                    'success': success,
                    'data': response_data,
                    'metadata': metadata,
                    'request_id': request_id
                })
        
        # Make the API call asynchronously
        self.call_api(
            endpoint_name=endpoint,
            params=params,
            async_call=True,
            callback=_callback
        )
        # NOTE: There was an accidental, mis-indented block here (rate-limit stats logic)
        # which caused a SyntaxError ("unexpected indent"). It did not belong to this handler.
        return
    
    def teardown(self) -> None:
        """Clean up resources used by the APIConnector."""
        try:
            self.logger.info("Shutting down APIConnector")
            
            # Stop async processor
            self.processing_active = False
            
            # Unsubscribe from events
            if self.event_bus:
                self.event_bus.unsubscribe('api.request', self.handle_api_request_event)
                self.event_bus.unsubscribe('api.register_parser', self.register_parser_event)
                self.event_bus.unsubscribe('api.reload_endpoints', self.reload_endpoints)
                
        except Exception as e:
            self.logger.error(f"Error during APIConnector teardown: {str(e)}")
