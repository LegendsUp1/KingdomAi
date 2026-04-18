#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
NetworkManager component for Kingdom AI.
Manages network connections, status, and reconnection logic.
"""

import asyncio
import logging
import json
import time
import socket
import aiohttp
import inspect
import random
import ssl
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class NetworkManager(BaseComponent):
    """
    Component for managing network connections and status.
    Provides network health monitoring and reconnection capabilities.
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the NetworkManager component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        # Ensure proper initialization with event_bus
        super().__init__("NetworkManager", event_bus, config)
        self.description = "Manages network connections and status"
        self.logger = logging.getLogger("core.network_manager")
        self.logger.info("Initializing NetworkManager")
        
        # Network configuration
        self.check_interval = self.config.get("check_interval", 30)  # seconds
        self.timeout = self.config.get("timeout", 5)  # seconds
        self.max_retries = self.config.get("max_retries", 3)
        self.heartbeat_interval = self.config.get("heartbeat_interval", 60)  # seconds
        
        # Endpoints to monitor
        self.endpoints = self.config.get("endpoints", {
            "internet": {
                "urls": ["https://google.com", "https://cloudflare.com"],
                "ports": [],
                "priority": "critical"
            },
            "exchanges": {
                "urls": ["https://api.binance.com", "https://api.kraken.com"],
                "ports": [],
                "priority": "high"
            },
            "blockchain": {
                "urls": ["https://api.etherscan.io", "https://api.blockchain.info"],
                "ports": [],
                "priority": "high"
            },
            "custom": {
                "urls": self.config.get("custom_urls", []),
                "ports": self.config.get("custom_ports", []),
                "priority": "medium"
            }
        })
        
        # Client session
        self.session = None
        self._session_lock = None
        self._session_force_close = False
        
        # Status tracking
        self.status = {}
        # Initialize status for each endpoint category
        for category in self.endpoints.keys():
            self.status[category] = False
        self.last_check_times = {}
        self.check_task = None
        self.heartbeat_task = None
        self.is_running = False
        self.retry_counts = {}
        
        # Connection metrics
        self.metrics = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "avg_response_time": 0,
            "total_response_time": 0,
            "outages": []
        }
        
        # Certificate validation
        self.verify_certs = self.config.get("verify_certs", True)
        
        # Request cache
        self.enable_request_cache = self.config.get("enable_request_cache", True)
        self.cache_max_size = self.config.get("cache_max_size", 100)
        self.cache_ttl = self.config.get("cache_ttl", 60)  # seconds
        self.request_cache = {}
        
        # Request configuration
        self.requests_per_minute = self.config.get("requests_per_minute", 60)
        self.request_timeout = self.config.get("request_timeout", 10)
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_backoff_factor = self.config.get("retry_backoff_factor", 0.5)
        self.enable_fallback = self.config.get("enable_fallback", True)
        
    async def safe_publish(self, event_name, event_data=None):
        """Safely publish an event to the event bus if it exists.
        
        Args:
            event_name: Name of the event to publish
            event_data: Data to include with the event
        """
        if self.event_bus:
            try:
                publish_fn = getattr(self.event_bus, "publish", None)
                if publish_fn:
                    publish_result = publish_fn(event_name, event_data)
                    if asyncio.iscoroutine(publish_result):
                        await publish_result
            except Exception as e:
                self.logger.error(f"Error publishing event {event_name}: {e}")
        else:
            self.logger.debug(f"Event {event_name} not published (no event bus)")

    def _is_transport_corruption_error(self, exc: BaseException) -> bool:
        error_text = str(exc).lower()
        if (
            "bad record mac" in error_text
            or "decryption failed" in error_text
            or "wrong version number" in error_text
            or "eof occurred in violation of protocol" in error_text
            or "connection reset" in error_text
            or "forcibly closed" in error_text
            or "broken pipe" in error_text
            or "connection aborted" in error_text
        ):
            return True

        client_ssl_error = getattr(aiohttp, "ClientSSLError", None)
        if client_ssl_error and isinstance(exc, client_ssl_error):
            return True
        if isinstance(exc, (ssl.SSLError, ConnectionResetError, BrokenPipeError)):
            return True

        cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
        if cause and cause is not exc:
            return self._is_transport_corruption_error(cause)

        return False

    def _build_tcp_connector(self, force_close: bool) -> aiohttp.TCPConnector:
        connector_kwargs: Dict[str, Any] = {"ssl": self.verify_certs, "force_close": force_close}
        try:
            if "enable_cleanup_closed" in inspect.signature(aiohttp.TCPConnector).parameters:
                connector_kwargs["enable_cleanup_closed"] = True
        except Exception:
            pass
        return aiohttp.TCPConnector(**connector_kwargs)

    async def _ensure_session(self, timeout: float, force_close: bool) -> None:
        if self._session_lock is None:
            self._session_lock = asyncio.Lock()

        async with self._session_lock:
            if self.session and getattr(self.session, "closed", False):
                self.session = None

            if self.session is None or self._session_force_close != force_close:
                if self.session:
                    try:
                        await self.session.close()
                    except Exception:
                        pass

                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    connector=self._build_tcp_connector(force_close=force_close),
                )
                self._session_force_close = force_close

    async def _reset_session(self, timeout: float, force_close: bool) -> None:
        if self._session_lock is None:
            self._session_lock = asyncio.Lock()

        async with self._session_lock:
            if self.session:
                try:
                    await self.session.close()
                except Exception:
                    pass

            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout),
                connector=self._build_tcp_connector(force_close=force_close),
            )
            self._session_force_close = force_close

    async def initialize(self) -> bool:
        """Initialize the NetworkManager component.
        
        Returns:
            bool: True if initialized successfully, False otherwise
        """
        try:
            # Set up event subscriptions if event_bus is available
            if self.event_bus:
                self.event_bus.subscribe_sync('network.check', self.on_network_check)
                self.event_bus.subscribe_sync('network.status.request', self.on_status_request)
                self.event_bus.subscribe_sync('system.shutdown', self.on_shutdown)
                self.event_bus.subscribe_sync('config.update.network', self.on_config_update)
                self.logger.info("Network manager event subscriptions initialized")
            else:
                self.logger.warning("No event bus available, network events will not be published")
                
            await self._reset_session(timeout=self.timeout, force_close=False)
            
            # Start network checking
            self.is_running = True
            self.check_task = asyncio.create_task(self.check_network_periodically())
            self.heartbeat_task = asyncio.create_task(self.send_heartbeat_periodically())
            
            # Publish initial status
            await self.check_all_endpoints()
            
            logger.info("NetworkManager initialized")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize network manager: {e}")
            return False
        
    async def check_network_periodically(self):
        """Check network status periodically."""
        try:
            while self.is_running:
                await self.check_all_endpoints()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("Network check task cancelled")
        except Exception as e:
            logger.error(f"Error in network check task: {str(e)}")
            
            if self.is_running:
                # Restart the task
                self.check_task = asyncio.create_task(self.check_network_periodically())
    
    async def send_heartbeat_periodically(self):
        """Send network heartbeat periodically."""
        try:
            while self.is_running:
                await self.safe_publish("network.heartbeat", {
                    "status": self.status,
                    "metrics": self.metrics,
                    "timestamp": datetime.now().isoformat()
                })
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:
            logger.info("Network heartbeat task cancelled")
        except Exception as e:
            logger.error(f"Error in network heartbeat task: {str(e)}")
            
            if self.is_running:
                # Restart the task
                self.heartbeat_task = asyncio.create_task(self.send_heartbeat_periodically())
    
    async def check_all_endpoints(self):
        """Check all configured endpoints."""
        current_time = datetime.now()
        previous_status = dict(self.status)
        
        # Update metrics
        self.metrics["total_checks"] += 1
        
        # Check each endpoint category
        for category, endpoints in self.endpoints.items():
            urls = endpoints["urls"]
            ports = endpoints["ports"]
            
            # Skip empty categories
            if not urls and not ports:
                continue
            
            category_status = False
            start_time = time.time()
            
            # Check URLs
            if urls:
                url_status = await self.check_urls(category, urls)
                category_status = url_status
            
            # Check ports
            if ports:
                port_status = await self.check_ports(category, ports)
                category_status = category_status or port_status
            
            # Update response time metrics
            end_time = time.time()
            response_time = end_time - start_time
            self.metrics["total_response_time"] += response_time
            if self.metrics["total_checks"] > 0:
                self.metrics["avg_response_time"] = self.metrics["total_response_time"] / self.metrics["total_checks"]
            
            # Update status
            self.status[category] = category_status
            self.last_check_times[category] = current_time
            
            # Detect status changes
            if previous_status.get(category, False) != category_status:
                if category_status:
                    logger.info(f"Network {category} connection restored")
                    
                    # Calculate outage duration if this was a recovery
                    if category in self.retry_counts and self.retry_counts[category] > 0:
                        # Find the most recent outage for this category
                        for outage in reversed(self.metrics["outages"]):
                            if outage["category"] == category and outage["end_time"] is None:
                                outage["end_time"] = current_time.isoformat()
                                outage["duration"] = (current_time - datetime.fromisoformat(outage["start_time"])).total_seconds()
                                break
                    
                    await self.safe_publish("network.status.up", {
                        "category": category,
                        "timestamp": current_time.isoformat()
                    })
                else:
                    logger.warning(f"Network {category} connection lost")
                    
                    # Record outage
                    self.metrics["outages"].append({
                        "category": category,
                        "start_time": current_time.isoformat(),
                        "end_time": None,
                        "duration": None
                    })
                    
                    await self.safe_publish("network.status.down", {
                        "category": category,
                        "timestamp": current_time.isoformat()
                    })
        
        # Update success/failure metrics
        critical_endpoints = [category for category in self.status.keys() 
                           if category in self.endpoints and 
                           self.endpoints[category].get("priority") == "critical"]
        
        # If there are critical endpoints, check if they are all up
        if critical_endpoints:
            overall_status = all(self.status[category] for category in critical_endpoints)
        else:
            # If no critical endpoints, check if any endpoint is up
            overall_status = any(status for status in self.status.values())
        
        if overall_status:
            self.metrics["successful_checks"] += 1
        else:
            self.metrics["failed_checks"] += 1
        
        # Publish overall status
        await self.safe_publish("network.status", {
            "overall": overall_status,
            "categories": self.status,
            "timestamp": current_time.isoformat()
        })
        
        return overall_status
    
    async def check_urls(self, category: str, urls: List[str]) -> bool:
        """
        Check a list of URLs for connectivity.
        
        Args:
            category: Category name for the URLs
            urls: List of URLs to check
            
        Returns:
            bool: True if any URL is reachable
        """
        if not urls:
            return False
            
        # Initialize retry count if needed
        if category not in self.retry_counts:
            self.retry_counts[category] = 0
            
        # Try each URL until one succeeds
        for url in urls:
            try:
                if not self.session:
                    self.logger.error("No active session available for URL check")
                    return False
                    
                async with self.session.get(url, raise_for_status=False) as response:
                    if response.status < 400:
                        # Success
                        self.retry_counts[category] = 0
                        return True
                    else:
                        self.logger.warning(f"URL {url} returned status {response.status}")
            except aiohttp.ClientError as e:
                self.logger.warning(f"Error connecting to {url}: {str(e)}")
            except Exception as e:
                self.logger.error(f"Unexpected error checking {url}: {str(e)}")
        
        # All URLs failed
        self.retry_counts[category] += 1
        
        # If we haven't reached max retries, don't consider it a failure yet
        if self.retry_counts[category] <= self.max_retries:
            return self.status.get(category, False)  # Keep previous status
            
        return False
    
    async def check_ports(self, category: str, port_specs: List[Dict]) -> bool:
        """
        Check connectivity to a list of ports.
        
        Args:
            category: Category name for the ports
            port_specs: List of port specifications (host, port)
            
        Returns:
            bool: True if any port is reachable
        """
        if not port_specs:
            return False
            
        # Initialize retry count if needed
        if category not in self.retry_counts:
            self.retry_counts[category] = 0
            
        # Try each port until one succeeds
        for spec in port_specs:
            host = spec.get("host", "localhost")
            port = spec.get("port", 80)
            
            try:
                # Create socket and attempt to connect
                future = self._check_port_async(host, port)
                result = await asyncio.wait_for(future, timeout=self.timeout)
                if result:
                    # Success
                    self.retry_counts[category] = 0
                    return True
            except (asyncio.TimeoutError, ConnectionRefusedError):
                self.logger.warning(f"Could not connect to {host}:{port}")
            except Exception as e:
                self.logger.error(f"Unexpected error checking {host}:{port}: {str(e)}")
        
        # All ports failed
        self.retry_counts[category] += 1
        
        # If we haven't reached max retries, don't consider it a failure yet
        if self.retry_counts[category] <= self.max_retries:
            return self.status.get(category, False)  # Keep previous status
            
        return False
    
    async def _check_port_async(self, host: str, port: int) -> bool:
        """
        Check if a port is reachable asynchronously.
        
        Args:
            host: Host to check
            port: Port number to check
            
        Returns:
            bool: True if the port is reachable
        """
        try:
            # Run socket connection in a thread to avoid blocking
            socket_connect = lambda: socket.create_connection((host, port), timeout=self.timeout)
            loop = asyncio.get_running_loop()
            sock = await loop.run_in_executor(None, socket_connect)
            sock.close()
            return True
        except Exception:
            return False
    
    async def on_network_check(self, _):
        """
        Handle network check request.
        
        Args:
            _: Event data (not used)
        """
        result = await self.check_all_endpoints()
        
        await self.safe_publish("network.check.result", {
            "success": result,
            "status": self.status,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_status_request(self, data):
        """
        Handle network status request.
        
        Args:
            data: Request data
        """
        request_id = data.get("request_id", "unknown") if data else "unknown"
        
        await self.safe_publish("network.status.response", {
            "request_id": request_id,
            "overall": all(status for category, status in self.status.items() 
                        if self.endpoints[category]["priority"] == "critical"),
            "categories": self.status,
            "metrics": self.metrics,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_config_update(self, data):
        """
        Handle configuration update.
        
        Args:
            data: Configuration data
        """
        # Update configuration
        endpoints = data.get("endpoints")
        if endpoints:
            self.endpoints.update(endpoints)
        
        check_interval = data.get("check_interval")
        if check_interval:
            self.check_interval = check_interval
            
        timeout = data.get("timeout")
        if timeout:
            self.timeout = timeout
            
        max_retries = data.get("max_retries")
        if max_retries:
            self.max_retries = max_retries
            
        heartbeat_interval = data.get("heartbeat_interval")
        if heartbeat_interval:
            self.heartbeat_interval = heartbeat_interval
            
        verify_certs = data.get("verify_certs")
        if verify_certs is not None:
            self.verify_certs = verify_certs
            
            # Update session with new SSL settings
            await self._reset_session(timeout=self.timeout, force_close=self._session_force_close)
        
        self.logger.info("Network configuration updated")
    
    async def on_shutdown(self, _=None):
        """Handle system shutdown event.
        
        Args:
            _: Event data (not used)
        """
        self.logger.info("Handling system shutdown event")
        await self.shutdown()
        
    def check_internet_connection(self) -> bool:
        """Check if internet connection is available.
        
        Returns:
            bool: True if connected to the internet, False otherwise
        """
        # Return the cached status of internet connectivity
        return self.status.get("internet", False)
        
    async def make_request(self, url: str, method: str = "GET", headers: Optional[Dict] = None,
                        data: Any = None, params: Optional[Dict] = None,
                        timeout: Optional[float] = None, cache: bool = True,
                        retries: Optional[int] = None) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Make an HTTP request with caching, retries, and fallback.
        
        Args:
            url: URL to request
            method: HTTP method (GET, POST, etc.)
            headers: Optional request headers
            data: Optional request data
            params: Optional URL parameters
            timeout: Request timeout in seconds
            cache: Whether to use cache for GET requests
            retries: Number of retries if request fails
            
        Returns:
            Tuple of (success (bool), response data (dict or None), error message (str or None))
        """
        method = method.upper()
        base_headers = headers or {}

        timeout_raw = self.request_timeout if timeout is None else timeout
        try:
            timeout = float(timeout_raw)
        except Exception:
            timeout = 10.0

        retries_raw = self.max_retries if retries is None else retries
        try:
            retry_count = max(0, int(retries_raw)) if retries_raw is not None else 0
        except Exception:
            try:
                retry_count = int(self.max_retries) if self.max_retries is not None else 3
            except Exception:
                retry_count = 3

        force_close = False
        
        # Create a cache key for GET requests
        cache_key = None
        if method == "GET" and cache and self.enable_request_cache:
            # Create a cache key from the URL, headers and params
            param_json = json.dumps(params or {}) if params is not None else "{}"
            cache_key = f"{url}:{param_json}"
            
            # Check if we have a cached response
            if cache_key in self.request_cache:
                cached = self.request_cache[cache_key]
                # Check if the cache is still valid
                if time.time() - cached["timestamp"] < self.cache_ttl:
                    self.logger.debug(f"Using cached response for {url}")
                    return True, cached["data"], None
        
        # Make the request with retries
        for attempt in range(retry_count + 1):
            try:
                request_headers = dict(base_headers)
                if force_close and "Connection" not in request_headers:
                    request_headers["Connection"] = "close"

                await self._ensure_session(timeout=timeout, force_close=force_close)
                request_timeout = aiohttp.ClientTimeout(total=timeout)
                
                # Choose the appropriate method
                if method == "GET":
                    async with self.session.get(url, headers=request_headers, params=params, 
                                              timeout=request_timeout) as response:
                        if response.status < 400:
                            # Parse the response based on content type
                            content_type = response.headers.get("Content-Type", "")
                            result_data = None
                            try:
                                if "application/json" in content_type:
                                    result_data = await response.json()
                                else:
                                    # Convert text to dict for consistent return type
                                    result_data = {"text": await response.text()}
                            except Exception as e:
                                # If parsing fails, fallback to text
                                self.logger.warning(f"Response parsing failed: {e}, falling back to text")
                                result_data = {"text": await response.text()}
                                
                            # Cache the successful response for GET requests
                            if cache_key and self.enable_request_cache:
                                self.request_cache[cache_key] = {
                                    "data": result_data,
                                    "timestamp": time.time()
                                }
                                
                                # Trim cache if it's too large
                                self._trim_cache()
                                        
                            return True, result_data, None
                        else:
                            error_msg = f"HTTP error {response.status}: {await response.text()}"
                            self.logger.warning(f"Request to {url} failed: {error_msg}")
                            
                            # For the last attempt, return the error
                            if attempt == retry_count:
                                return False, None, error_msg
                            
                elif method == "POST":
                    async with self.session.post(url, headers=request_headers, json=data if data else None, 
                                              params=params, timeout=request_timeout) as response:
                        if response.status < 400:
                            content_type = response.headers.get("Content-Type", "")
                            try:
                                if "application/json" in content_type:
                                    return True, await response.json(), None
                                else:
                                    return True, {"text": await response.text()}, None
                            except Exception as e:
                                self.logger.warning(f"Response parsing failed: {e}, falling back to text")
                                return True, {"text": await response.text()}, None
                        else:
                            error_msg = f"HTTP error {response.status}: {await response.text()}"
                            self.logger.warning(f"Request to {url} failed: {error_msg}")
                            
                            # For the last attempt, return the error
                            if attempt == retry_count:
                                return False, None, error_msg
                else:
                    # Other methods can be implemented similarly
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
            except asyncio.TimeoutError as e:
                error_msg = f"Timeout error: {str(e)}"
                self.logger.warning(f"Request to {url} failed: {error_msg}")
                
                # For the last attempt, return the error
                if attempt == retry_count:
                    return False, None, error_msg
            except aiohttp.ClientError as e:
                error_msg = f"Client error: {str(e)}"
                self.logger.warning(f"Request to {url} failed: {error_msg}")

                if self._is_transport_corruption_error(e):
                    force_close = True
                    try:
                        await self._reset_session(timeout=timeout, force_close=True)
                    except Exception:
                        pass
                
                # For the last attempt, return the error
                if attempt == retry_count:
                    return False, None, error_msg
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                self.logger.error(f"Request to {url} failed: {error_msg}")

                if self._is_transport_corruption_error(e):
                    force_close = True
                    try:
                        await self._reset_session(timeout=timeout, force_close=True)
                    except Exception:
                        pass
                
                # For the last attempt, return the error
                if attempt == retry_count:
                    return False, None, error_msg
            
            # If we get here, the request failed and we should retry
            # Wait with exponential backoff
            if attempt < retry_count:
                backoff_raw = 0.5 if self.retry_backoff_factor is None else self.retry_backoff_factor
                try:
                    backoff_factor = float(backoff_raw)
                except Exception:
                    backoff_factor = 0.5
                wait_time = backoff_factor * (2 ** attempt)
                jitter = random.uniform(0.0, max(0.0, wait_time * 0.1))
                wait_time_with_jitter = wait_time + jitter
                self.logger.info(f"Retrying request to {url} in {wait_time_with_jitter:.2f} seconds (attempt {attempt+1}/{retry_count})") 
                await asyncio.sleep(wait_time_with_jitter)
        
        # We should never get here, but just in case
        return False, None, "Unknown error"
        
    def _trim_cache(self):
        """Trim the request cache if it exceeds the maximum size."""
        cache_size = len(self.request_cache)
        # Ensure max_size is a positive integer
        max_size = 100 if self.cache_max_size is None else self.cache_max_size
        safe_max_size = max(1, int(max_size) if isinstance(max_size, (int, float)) else 100)
        
        if cache_size > safe_max_size:
            # Remove oldest entries
            oldest = sorted(self.request_cache.items(), 
                         key=lambda x: x[1]["timestamp"])
            for key, _ in oldest[:max(0, cache_size - safe_max_size)]:
                del self.request_cache[key]
    
    async def shutdown(self):
        """Shutdown the NetworkManager component. Public method for proper shutdown."""
        self.logger.info("Shutting down NetworkManager")
        
        # Stop tasks
        self.is_running = False
        
        # Cancel network check task
        if hasattr(self, 'check_task') and self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(f"Error cancelling check task: {e}")
        
        # Cancel heartbeat task
        if hasattr(self, 'heartbeat_task') and self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(f"Error cancelling heartbeat task: {e}")
        
        # Close HTTP session
        if hasattr(self, 'session') and self.session:
            try:
                await self.session.close()
                self.session = None
            except Exception as e:
                self.logger.error(f"Error closing HTTP session: {e}")
        
        # Publish shutdown completion event
        try:
            await self.safe_publish("network.manager.shutdown.complete", {
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            self.logger.error(f"Error publishing shutdown event: {e}")
            
        self.logger.info("NetworkManager shut down successfully")
