#!/usr/bin/env python3
"""
Dashboard Frame for Kingdom AI GUI.
Provides an overview of system status and key metrics including the Quantum Redis Nexus.
"""

import tkinter as tk
from tkinter import ttk
import logging
import asyncio
import os
import sys
from datetime import datetime

from .base_frame import BaseFrame
from .dashboard_market_handler import DashboardMarketHandler

# TEMP FIX: event_bus_wrapper import hangs
try:
    from core.event_bus_wrapper import get_event_bus_wrapper
except ImportError:
    def get_event_bus_wrapper():
        return None
import time
import json
import platform

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.redis_connector import RedisQuantumNexusConnector, RedisConnector

class DashboardFrame(BaseFrame, DashboardMarketHandler):
    """Dashboard frame for displaying system metrics, component status, and real-time data."""
    """Dashboard frame for the Kingdom AI GUI."""
    
    def __init__(self, parent, event_bus=None, api_key_connector=None, name="DashboardFrame", **kwargs):
        """Initialize the dashboard frame.
        
        Args:
            parent: The parent widget
            event_bus: The event bus for publishing/subscribing to events
            api_key_connector: Connector for accessing API keys
            name: Name of the frame
            **kwargs: Additional kwargs for the frame
        """
        # Initialize BaseFrame properly
        BaseFrame.__init__(self, parent, event_bus, name)
        
        # Initialize DashboardMarketHandler
        DashboardMarketHandler.__init__(self)
        
        # Store API key connector
        self.api_key_connector = api_key_connector
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Component metrics
        self.component_status = {}
        self.system_metrics = {
            "cpu_usage": 0,
            "memory_usage": 0,
            "uptime": 0,
            "active_components": 0,
            "total_components": 0
        }
        
        # API keys for data services
        self.data_service_keys = {}
        
        # UI elements
        self.redis_status_label = None
        self.redis_toggle_button = None
        self.redis_info_labels = {}
        
        # Time tracking
        self.start_time = time.time()
        
        # Redis connection
        self.redis_status_dict = {
            "connected": False,
            "server_running": False,
            "port": 6380,  # MANDATORY: Using port 6380 for Redis Quantum Nexus
            "version": "Unknown",
            "uptime": 0,
            "clients": 0,
            "memory_used": 0
        }
        
        # System packages
        self.system_packages = {}
        self.redis_client = None
        self.auto_start_attempted = False

        # System status indicators
        self.system_indicators = {}
        self.environment_packages = {"conda": {}, "micromamba": {}}
        # Blockchain connection status
        self.blockchain_status = {
            "blockchain_connected": False,
            "web3_connected": False,
            "connection_type": "none",
            "network": "unknown",
            "node_version": "unknown"
        }
        
        # Method for API key handling
        if not hasattr(self, 'get_api_key'):
            self.get_api_key = self._get_api_key
    
    async def initialize(self):
        """Initialize the dashboard frame."""
        self.logger.info("Initializing Dashboard frame")
        
        try:
            # Initialize Redis status dictionary with default values
            self.redis_status_dict = {
                "connected": False,
                "server_running": False,
                "port": 6380,  # MANDATORY: Using port 6380 for Redis Quantum Nexus
                "version": "Unknown",
                "uptime": 0,
                "clients": 0,
                "memory_used": 0
            }
            
            # Load API keys for data services
            await self._load_data_service_keys()
            
            # Call parent initialization
            await super().initialize()
            
            # Create dashboard-specific layout
            self._create_dashboard_layout()
            
            # Initialize required attributes
            self.toggle_redis_button = None
            self.app = self.parent.winfo_toplevel()
            
            # Initialize Redis manager with proper configuration
            self.redis_manager = RedisQuantumNexusConnector(
                port=6380,
                host='localhost',
                password='QuantumNexus2025',
                db=0
            )
            
            # Register Redis event handlers
            await self._register_redis_events()
            
            # Start background tasks
            await self._start_background_tasks()            
            
            # Auto-start Redis server if not already running
            if not self.auto_start_attempted and not self.redis_status_dict.get("server_running", False):
                self.auto_start_attempted = True
                await self._auto_start_redis_server()
            else:
                # Update UI with current status
                self._update_redis_status_ui(self.redis_status_dict.get("server_running", False))
                
            # Load system package information
            await self._load_system_packages()
            
            # Initial UI update
            self.update_status("Dashboard ready", "#4CAF50")
            self._update_redis_quantum_nexus_status()
            
            # Force update to ensure widgets are visible
            try:
                if hasattr(self, 'winfo_children'):
                    for widget in self.winfo_children():
                        if hasattr(widget, 'update_idletasks'):
                            widget.update_idletasks()
                if hasattr(self, 'update_idletasks'):
                    self.update_idletasks()
                elif hasattr(self.parent, 'update_idletasks'):
                    self.parent.update_idletasks()
            except Exception as update_error:
                self.logger.warning(f"Could not update widgets: {update_error}")
            
            self.logger.info("Dashboard frame initialized successfully")
            
            # Initial status check
            await self._check_redis_connection()
            
        except Exception as e:
            self.logger.error(f"Error initializing dashboard: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.update_status(f"Error: {str(e)[:30]}...", "#F44336")
        
        return True
    
    def _subscribe_to_events(self):
        """Subscribe to the events that this frame is interested in."""
        self.logger.debug("Subscribing to events for Dashboard Frame")
        # Use loop.create_task to handle async _register_common_events without awaiting
        if hasattr(asyncio, 'get_event_loop'):
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self._register_common_events())
            except RuntimeError:
                self.logger.error("Error getting event loop in _subscribe_to_events")
        return None  # Return None to match parent method signature
    
    async def _register_common_events(self):
        """Register common events that the dashboard should respond to."""
        # Call the parent method to register common events
        if hasattr(super(), '_register_common_events'):
            await super()._register_common_events()
        
        # Register dashboard-specific events
        try:
            # Subscribe to blockchain status events
            await self._safe_subscribe("blockchain.status", self._handle_blockchain_status)
            
            # Subscribe to dashboard-specific events using _safe_subscribe for consistency
            await self._safe_subscribe("system.metrics", self._handle_system_metrics)
            await self._safe_subscribe("component.status", self._handle_component_status)
            
            # Redis-specific subscriptions
            await self._safe_subscribe("redis.status", self._handle_redis_status)
            await self._safe_subscribe("redis.quantum.status", self._handle_redis_quantum_status)
            await self._safe_subscribe("redis.server.status", self._handle_redis_server_status)
            await self._safe_subscribe("redis.package.count", self._handle_redis_package_count)
            
            # Market data subscriptions
            await self._safe_subscribe("market.data", self._handle_market_data)
            
            # Register market data events (if this is an async method, make sure to await it)
            if hasattr(self, 'register_market_events'):
                if asyncio.iscoroutinefunction(self.register_market_events):
                    await self.register_market_events(self.event_bus)
                else:
                    self.register_market_events(self.event_bus)
            
            # Subscribe to API key updates
            await self._safe_subscribe("api_keys.updated", self._handle_api_key_update)
            
            self.logger.info("Dashboard subscribed to all system and component events")
        except Exception as e:
            self.logger.error(f"Error registering dashboard events: {e}")
    
    def _create_dashboard_layout(self):
        """Create the dashboard layout with metrics and status indicators."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create main dashboard tab
        self.dashboard_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_tab, text="Dashboard")
        
        # Create Redis tab
        self.redis_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.redis_tab, text="Redis Quantum Nexus")
        
        # Create Market Data tab
        self.market_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.market_tab, text="Market Data")
        
        # Top metrics frame in main dashboard tab
        self.metrics_frame = ttk.Frame(self.dashboard_tab)
        self.metrics_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create metric cards
        self._create_metric_cards()
        
        # System status overview
        self.status_frame = ttk.LabelFrame(self.dashboard_tab, text="System Status")
        
        # Setup Redis Quantum Nexus tab
        self._setup_redis_tab()
        self.status_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create component status grid
        self._create_component_status_grid()

        # Create system status indicators
        self._create_system_status_indicators()
        
        # Setup Market Data display
        self.setup_market_display(self.market_tab)
        
        # Recent activity log
        self.log_frame = ttk.LabelFrame(self.content_frame, text="Recent Activity")
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = tk.Text(self.log_frame, height=6, width=50, bg="#1E1E1E", fg="white")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add an auto-scroll bar
        log_scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        
        # Add a welcome message
        self.log_message("Welcome to Kingdom AI Dashboard")
        self.log_message("System is initializing components...")

    # Note: _update_redis_status is defined more comprehensively later in the file
    
    # Note: _update_redis_status_ui is defined more comprehensively later in the file
    
    # Note: _update_redis_quantum_nexus_status is defined more comprehensively later in the file with mandatory port 6380 enforcement
    
    # Note: _update_kingdom_ai_status is defined more comprehensively later in the file
    # Note: _update_system_indicator is defined more comprehensively later in the file
            
    # Note: log_message is defined more comprehensively later in the file
            
    async def _auto_start_redis_server(self):
        """Automatically start the Redis Quantum Nexus server if not running."""
        if not hasattr(self, 'auto_start_attempted'):
            self.auto_start_attempted = False
            
        if self.auto_start_attempted:
            return
                
        self.auto_start_attempted = True
            
        self.logger.info("Auto-starting Redis Quantum Nexus server")
            
        try:
            # Check if Redis is already running
            if hasattr(self, 'redis_status_dict') and self.redis_status_dict.get("server_running", False):
                self.logger.info("Redis Quantum Nexus already running")
                    
                # Update Redis status
                self._update_redis_status(True)
                    
                # Update UI to show Redis is running
                self._update_redis_status_ui(True)
            else:
                self.register_market_events(self.event_bus)
            
                # Start Redis server
                await self.start_redis_server()
        except Exception as e:
            self.logger.error(f"Error auto-starting Redis server: {e}")
            self.update_status(f"Redis error: {str(e)[:30]}...", "#F44336")
    # Method removed to eliminate duplicate _create_dashboard_layout
    # The complete implementation is kept in the first occurrence at line 214-269

    async def start_redis_server(self):
        """Start Redis Quantum Nexus server on mandatory port 6380."""
        self.logger.info("Starting Redis Quantum Nexus server on port 6380")
        
        try:
            # Get component manager
            component_manager = None
            if hasattr(self, 'app') and hasattr(self.app, 'component_manager'):
                component_manager = self.app.component_manager
            elif hasattr(self.parent, 'component_manager'):
                component_manager = self.parent.component_manager

            if not component_manager:
                self.logger.error("Component manager not available")
                self.update_status("Component manager not available", "#F44336")
                return False

            # Get Redis connector
            redis_connector = component_manager.get_component('RedisQuantumNexusConnector')
            if not redis_connector:
                self.logger.error("Redis Quantum Nexus connector not found")
                self.update_status("Redis connector not found", "#F44336")
                return False

            # Verify port is 6380 (mandatory)
            redis_port = 6380
            if hasattr(redis_connector, 'config') and 'port' in redis_connector.config:
                redis_port = redis_connector.config['port']

            if redis_port != 6380:
                self.logger.error(f"Redis must use port 6380. Found: {redis_port}")
                self.update_status("Error: Redis must use port 6380", "#F44336")
                return False

            # Initialize Redis connection
            self.update_status("Starting Redis connection...", "#FFC107")

            # Initialize Redis connector
            if hasattr(redis_connector, 'initialize'):
                await redis_connector.initialize()

            # Check connection success
            connection_success = False
            if hasattr(redis_connector, 'check_connection'):
                connection_success = await redis_connector.check_connection()
            elif hasattr(redis_connector, 'is_healthy'):
                connection_success = await redis_connector.is_healthy()

            if connection_success:
                self._update_redis_status(True)
                self.update_status("Redis connected on port 6380", "#4CAF50")

                # Publish event
                if hasattr(self, 'event_bus') and self.event_bus:
                    from datetime import datetime
                    self.event_bus.emit("redis.status", {
                        "status": "connected",
                        "running": True,
                        "port": 6380,
                        "timestamp": datetime.now().isoformat()
                    })

                # Update UI
                self._update_redis_status_ui(True)
                self._update_redis_quantum_nexus_status()
                self._update_kingdom_ai_status()

                return True
            else:
                self.logger.error("Failed to connect to Redis")
                self.update_status("Failed to connect to Redis", "#F44336")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting Redis server: {str(e)}")
            self.update_status(f"Redis error: {str(e)[:30]}...", "#F44336")
            return False

    async def stop_redis_server(self):
        """Stop Redis Quantum Nexus server."""
        try:
            self.logger.info("Stopping Redis Quantum Nexus server")
            if hasattr(self, 'app') and hasattr(self.app, 'component_manager'):
                component_manager = self.app.component_manager
            elif hasattr(self.parent, 'component_manager'):
                component_manager = self.parent.component_manager
            else:
                self.logger.error("Could not find component manager")
                return False

            # Get Redis connector
            redis_connector = component_manager.get_component('RedisQuantumNexusConnector')
            if not redis_connector:
                self.logger.error("Could not find RedisQuantumNexusConnector")
                self.update_status("Redis connector not found", "#F44336")
                return False

            # Stop Redis server
            success = await redis_connector.stop_server()

            # Update status
            if success:
                self.logger.info("Successfully stopped Redis Quantum Nexus server")
                self.update_status("Redis server stopped", "#4CAF50")
                
                # Update UI
                self._update_redis_status_ui(False)
                self._update_redis_quantum_nexus_status()
                self._update_kingdom_ai_status()
                
                # Publish event
                if hasattr(self, 'event_bus') and self.event_bus:
                    self.event_bus.emit("redis.status", {
                        "status": "disconnected",
                        "running": False,
                        "port": 6380,
                        "timestamp": datetime.now().isoformat()
                    })
                
                return True
            else:
                self.logger.error("Failed to stop Redis server")
                self.update_status("Failed to stop Redis server", "#F44336")
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping Redis server: {str(e)}")
            self.update_status(f"Redis error: {str(e)[:30]}...", "#F44336")
            return False

    async def _auto_start_redis_server(self):
        """Automatically start the Redis Quantum Nexus server if not running."""
        if not hasattr(self, 'auto_start_attempted'):
            self.auto_start_attempted = False

        if self.auto_start_attempted:
            return

        self.auto_start_attempted = True
        self.logger.info("Auto-starting Redis Quantum Nexus server")

        try:
            # First check if Redis is already running
            is_running = False
            if hasattr(self, 'redis_manager') and self.redis_manager:
                is_running = await self.redis_manager.test_connection()
            
            if is_running:
                self.logger.info("Redis Quantum Nexus already running")
                self.redis_status_dict.update({
                    'connected': True,
                    'server_running': True,
                    'port': 6380
                })
                self._update_redis_status_ui(True)
                # Update Redis info
                await self._check_redis_connection()
            else:
                self.logger.info("Starting Redis Quantum Nexus server...")
                # Register market events
                if hasattr(self, 'register_market_events') and hasattr(self, 'event_bus'):
                    self.register_market_events(self.event_bus)
                # Start the server
                success = await self.start_redis_server()
                if success:
                    # Update status after a short delay to allow server to start
                    await asyncio.sleep(1)
                    await self._check_redis_connection()
        except Exception as e:
            self.logger.error(f"Error auto-starting Redis server: {e}")
            self.update_status(f"Redis error: {str(e)[:30]}...", "#F44336")

async def start_redis_server(self):
    """Start Redis Quantum Nexus server on mandatory port 6380."""
    self.logger.info("Starting Redis Quantum Nexus server on port 6380")

    try:
        # Get component manager
        component_manager = None
        if hasattr(self, 'app') and hasattr(self.app, 'component_manager'):
            component_manager = self.app.component_manager
        elif hasattr(self.parent, 'component_manager'):
            component_manager = self.parent.component_manager

        if not component_manager:
            self.logger.error("Component manager not available")
            self.update_status("Component manager not available", "#F44336")
            return False

        # Get Redis connector
        redis_connector = component_manager.get_component('RedisQuantumNexusConnector')
        if not redis_connector:
            self.logger.error("Redis Quantum Nexus connector not found")
            self.update_status("Redis connector not found", "#F44336")
            return False

        # Verify port is 6380 (mandatory)
        redis_port = 6380
        if hasattr(redis_connector, 'config') and 'port' in redis_connector.config:
            redis_port = redis_connector.config['port']

        if redis_port != 6380:
            self.logger.error(f"Redis must use port 6380. Found: {redis_port}")
            self.update_status("Error: Redis must use port 6380", "#F44336")
            return False

        # Initialize Redis connection
        self.update_status("Starting Redis connection...", "#FFC107")

        # Initialize Redis connector
        if hasattr(redis_connector, 'initialize'):
            await redis_connector.initialize()

        # Check connection success
        connection_success = False
        if hasattr(redis_connector, 'check_connection'):
            connection_success = await redis_connector.check_connection()
        elif hasattr(redis_connector, 'is_healthy'):
            connection_success = await redis_connector.is_healthy()

        if connection_success:
            self._update_redis_status(True)
            self.update_status("Redis connected on port 6380", "#4CAF50")

            # Publish event
            if hasattr(self, 'event_bus') and self.event_bus:
                from datetime import datetime
                self.event_bus.emit("redis.status", {
                    "status": "connected",
                    "running": True,
                    "port": 6380,
                    "timestamp": datetime.now().isoformat()
                })

            # Update UI
            self._update_redis_status_ui(True)
            self._update_redis_quantum_nexus_status()
            self._update_kingdom_ai_status()

            return True
        else:
            self.logger.error("Failed to connect to Redis")
            self.update_status("Failed to connect to Redis", "#F44336")
            return False

    except Exception as e:
        self.logger.error(f"Error starting Redis server: {str(e)}")
        self.update_status(f"Redis error: {str(e)[:30]}...", "#F44336")
        return False

async def stop_redis_server(self):
    """Stop Redis Quantum Nexus server (synchronous wrapper)."""
    try:
        self.logger.info("Stopping Redis Quantum Nexus server")
        if hasattr(self, 'app') and hasattr(self.app, 'component_manager'):
            component_manager = self.app.component_manager
        elif hasattr(self.parent, 'component_manager'):
            component_manager = self.parent.component_manager
        else:
            self.logger.error("Could not find component manager")
            return False

        # Get Redis connector
        redis_connector = component_manager.get_component("RedisQuantumNexusConnector")
        if not redis_connector:
            self.logger.error("Could not find RedisQuantumNexusConnector")
            return False

        # Stop Redis server
        success = await redis_connector.stop_server()

        # Update status
        if success:
            self.logger.info("Successfully stopped Redis Quantum Nexus server")
            self.update_status("Redis server stopped", "#4CAF50")

            # Update UI
            self._update_redis_status_ui(False)
            self._update_redis_quantum_nexus_status()
            self._update_kingdom_ai_status()

            return True
        else:
            self.logger.error("Failed to stop Redis server")
            self.update_status("Failed to stop Redis server", "#F44336")
            return False

    except Exception as e:
        self.logger.error(f"Error stopping Redis server: {str(e)}")
        self.update_status(f"Redis error: {str(e)[:30]}...", "#F44336")
        return False

async def stop_redis_server_async(self):
    """Stop Redis Quantum Nexus server asynchronously."""
    self.logger.info("Stopping Redis Quantum Nexus server")

    try:
        # Get Redis connector
        component_manager = None
        if hasattr(self, 'app') and hasattr(self.app, 'component_manager'):
            component_manager = self.app.component_manager
        elif hasattr(self.parent, 'component_manager'):
            component_manager = self.parent.component_manager

        if not component_manager:
            self.logger.error("Component manager not available")
            self.update_status("Component manager not available", "#F44336")
            return False

        redis_connector = component_manager.get_component('redis_connector')
        if not redis_connector:
            self.logger.error("Redis connector not found")
            self.update_status("Redis connector not found", "#F44336")
            return False

        # Close Redis connection
        self.update_status("Stopping Redis connection...", "#FFC107")

        # Close the connection - try different methods depending on the connector implementation
        if hasattr(redis_connector, 'close') and callable(redis_connector.close):
            await redis_connector.close()
        elif hasattr(redis_connector, 'redis') and redis_connector.redis:
            # Fall back to closing the underlying Redis connection
            redis_connector.redis.close()
            if hasattr(redis_connector, 'connected'):
                redis_connector.connected = False

        self._update_redis_status(False)
        self.update_status("Redis disconnected", "#F44336")

        # Publish event
        if hasattr(self, 'event_bus') and self.event_bus:
            from datetime import datetime
            self.event_bus.emit("redis.status", {
                "status": "disconnected",
                "running": False,
                "port": 6380,
                "timestamp": datetime.now().isoformat()
            })

        # Update UI
        self._update_redis_status_ui(False)
        self._update_redis_quantum_nexus_status()
        self._update_kingdom_ai_status()

        return True
    except Exception as e:
        self.logger.error(f"Error stopping Redis server: {str(e)}")
        self.update_status(f"Redis error: {str(e)[:30]}...", "#F44336")
        return False

async def _toggle_redis_server(self):
    """Toggle Redis Quantum Nexus server on/off with mandatory port 6380."""
    self.logger.info("Toggle Redis button clicked")

    try:
        # Get current status
        redis_status_dict = getattr(self, 'redis_status_dict', {})
        if not isinstance(redis_status_dict, dict):
            redis_status_dict = {}
            self.redis_status_dict = redis_status_dict

        is_running = redis_status_dict.get("server_running", False)

        # Get button text as fallback
        if hasattr(self, 'toggle_redis_button') and self.toggle_redis_button:
            button_text = self.toggle_redis_button.cget("text") if hasattr(self.toggle_redis_button, 'cget') else ""
            if not is_running and "stop" in button_text.lower():
                is_running = True
            elif is_running and "start" in button_text.lower():
                is_running = False

        # Start or stop based on current state
        if not is_running:
            await self.start_redis_server()
        else:
            await self.stop_redis_server()
    except Exception as e:
        self.logger.error(f"Error toggling Redis server: {e}")
        self.update_status(f"Redis error: {str(e)[:30]}...", "#F44336")

def _register_redis_events(self):
    """Register for Redis status events via the event bus"""
    try:
        if not hasattr(self, 'event_bus'):
            self.logger.error("No event bus available for Redis events")
            return
            
        # Register for Redis-related events
        self.event_bus.subscribe("redis.status", self._handle_redis_status)
        self.event_bus.subscribe("redis.server.status", self._handle_redis_status)
        self.event_bus.subscribe("redis.package.count", self._handle_redis_package_count)
        
        self.logger.info("Registered for Redis events")
    except Exception as e:
        self.logger.error(f"Error registering Redis events: {e}")

def _handle_redis_status_event(self, event_data):
    """Handle Redis status events from the event bus"""
    try:
        self.logger.info(f"Received Redis status event: {event_data}")
        
        # Extract status data
        if isinstance(event_data, dict):
            status = event_data.get('status', 'unknown')
            running = event_data.get('running', False)
            port = event_data.get('port', 0)

            # Verify port is 6380 (mandatory)
            if port != 0 and port != 6380:
                self.logger.error(f"Redis must use port 6380. Found: {port}")
                self.update_status("Error: Redis must use port 6380", "#F44336")
                self.log_message(f"Redis port error: Expected 6380, found {port}")
                return
                    
            # Update internal status and UI
            self._update_redis_status(running)
            self._update_redis_status_ui(running)
            self._update_redis_quantum_nexus_status()
            self._update_kingdom_ai_status()
            
            # Log connection status
            if running:
                self.log_message(f"Redis Quantum Nexus connected on port {port}")
            else:
                self.log_message("Redis Quantum Nexus disconnected")
    except Exception as e:
        self.logger.error(f"Error handling Redis status: {e}")

async def _get_api_key(self, service):
    """Get API key for a specific service.
    
    Args:
        service: The service to get the API key for
            
    Returns:
        The API key if found, None otherwise
    """
    try:
        if self.api_key_connector:
            return await self.api_key_connector.get_api_key(service)
        self.logger.warning(f"No API key connector available for service: {service}")
        return None
    except Exception as e:
        self.logger.error(f"Error getting API key for {service}: {e}")
        return None
    
def log_message(self, message):
    """Log a message to the system log and update UI."""
    try:
        # Get current timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # Add to log history
        if not hasattr(self, 'log_messages'):
            self.log_messages = []
        self.log_messages.append(log_entry)
        
        # Keep only the last 100 messages
        if len(self.log_messages) > 100:
            self.log_messages = self.log_messages[-100:]
            
        # Update log display if it exists
        if hasattr(self, 'log_text') and self.log_text:
            # Ensure UI updates happen in the main thread
            try:
                self.log_text.config(state="normal")
                self.log_text.insert(tk.END, log_entry + "\n")
                self.log_text.see(tk.END)  # Scroll to end
                self.log_text.config(state="disabled")
            except Exception as e:
                self.logger.error(f"Error updating log UI: {e}")
    except Exception as e:
        self.logger.error(f"Error logging message: {e}")

async def _load_data_service_keys(self):
    """Load API keys for data services."""
    try:
        if self.api_key_connector:
            # Load API keys for various data services
            for service in ['redis', 'market_data', 'blockchain_data', 'thoth_ai']:
                key = await self._get_api_key(service)
                if key:
                    self.data_service_keys[service] = key
                    self.logger.info(f"Loaded API key for {service}")
                    
            self.logger.info(f"Loaded {len(self.data_service_keys)} API keys for data services")
        else:
            self.logger.warning("No API key connector available for loading data service keys")
    except Exception as e:
        self.logger.error(f"Error loading data service API keys: {e}")

async def _handle_api_key_update(self, event_data):
    """Handle API key update events.
    
    Args:
        event_data: Event data containing updated API key information
    """
    try:
        if not event_data or 'service' not in event_data:
            return
            
        service = event_data['service']
        
        # Check if the updated key is for a data service we use
        data_services = ['alphavantage', 'finnhub', 'polygon', 'marketstack', 
                         'newsapi', 'bloomberg', 'reuters']
                      
        if service in data_services:
            self.logger.info(f"Reloading API key for {service}")
            await self._load_data_service_keys()
            self.update_status(f"Updated API key for {service}")
    except Exception as e:
        self.logger.error(f"Error handling API key update: {e}")

def _handle_redis_package_count(self, data):
    """Handle Redis package count updates."""
    try:
        # Clear existing package tree
        for item in self.package_tree.get_children():
            self.package_tree.delete(item)
        
        # Update package count data
        self.system_packages = data.get("packages", {})
        
        # Add packages to treeview
        for package, info in self.system_packages.items():
            version = info.get("version", "Unknown")
            category = info.get("category", "Other")
            
            self.package_tree.insert(
                "", "end", 
                values=(package, version, category)
            )
        
    except Exception as e:
        self.logger.error(f"Error handling Redis package count: {e}")

def _handle_redis_command_result(self, data):
    """Handle Redis command result updates."""
    try:
        command = data.get("command", "")
        success = data.get("success", False)
        message = data.get("message", "")
        
        if command == "start":
            if success:
                self.redis_status_label.config(text="Running", foreground="green")
                self.redis_toggle_button.config(text="Stop Server", state="normal")
                self.redis_status_dict["server_running"] = True
            else:
                self.redis_status_label.config(text="Start Failed", foreground="red")
                self.redis_toggle_button.config(text="Start Server", state="normal")
                self.redis_status_dict["server_running"] = False
                
        elif command == "stop":
            if success:
                self.redis_status_label.config(text="Not Running", foreground="red")
                self.redis_toggle_button.config(text="Start Server", state="normal")
                self.redis_status_dict["server_running"] = False
            else:
                self.redis_status_label.config(text="Stop Failed", foreground="red")
                self.redis_toggle_button.config(text="Stop Server", state="normal")
                self.redis_status_dict["server_running"] = True
                
    except Exception as e:
        self.logger.error(f"Error handling Redis command result: {e}")

def _update_redis_status(self, is_running):
    """Update Redis status dictionary and UI."""
    try:
        # Update status dictionary
        self.redis_status_dict["server_running"] = is_running
        self.redis_status_dict["connected"] = is_running
        self.redis_status_dict["port"] = 6380  # Always enforce port 6380
        
        # Check if we have a timestamp to calculate uptime
        if is_running and "start_time" not in self.redis_status_dict:
            self.redis_status_dict["start_time"] = time.time()
    except Exception as e:
        self.logger.error(f"Error updating Redis status: {e}")
        
async def _check_redis_connection(self):
    """Check and update Redis connection status."""
    try:
        if not hasattr(self, 'redis_manager') or not self.redis_manager:
            self.logger.warning("Redis manager not initialized")
            return False
            
        is_connected = await self.redis_manager.test_connection()
        self.redis_status_dict['connected'] = is_connected
        self.redis_status_dict['server_running'] = is_connected
        
        if is_connected:
            try:
                # Get Redis server info
                info = await self.redis_manager.get_info()
                self.redis_status_dict['version'] = info.get('redis_version', 'Unknown')
                self.redis_status_dict['uptime'] = int(info.get('uptime_in_seconds', 0))
                self.redis_status_dict['clients'] = int(info.get('connected_clients', 0))
                self.redis_status_dict['memory_used'] = int(info.get('used_memory', 0)) / (1024 * 1024)  # Convert to MB
            except Exception as e:
                self.logger.warning(f"Could not get Redis info: {e}")
        
        # Update UI
        self._update_redis_status_ui(is_connected)
        return is_connected
        
    except Exception as e:
        self.logger.error(f"Error checking Redis connection: {e}")
        self.redis_status_dict['connected'] = False
        self.redis_status_dict['server_running'] = False
        self._update_redis_status_ui(False)
        return False

def _update_redis_status_ui(self, is_running):
    """Update Redis UI elements based on server status."""
    try:
        # Ensure status dict exists
        if not hasattr(self, 'redis_status_dict'):
            self.redis_status_dict = {
                "connected": False,
                "server_running": False,
                "port": 6380,
                "version": "Unknown",
                "uptime": 0,
                "clients": 0,
                "memory_used": 0
            }
        
        # Update status in the main thread
        def update_ui():
            try:
                port = self.redis_status_dict.get('port', 6380)
                
                # Update status label
                if hasattr(self, 'redis_status_label'):
                    if is_running:
                        self.redis_status_label.config(
                            text=f"Running on port {port}",
                            foreground="green"
                        )
                        
                        # Update additional info if available
                        if hasattr(self, 'redis_info_labels'):
                            if 'version' in self.redis_info_labels:
                                self.redis_info_labels['version'].config(
                                    text=f"Version: {self.redis_status_dict.get('version', 'Unknown')}"
                                )
                            if 'clients' in self.redis_info_labels:
                                self.redis_info_labels['clients'].config(
                                    text=f"Clients: {self.redis_status_dict.get('clients', 0)}"
                                )
                    else:
                        port_status = "" if port == 6380 else f" (Port: {port}, should be 6380)"
                        self.redis_status_label.config(
                            text=f"Not Running{port_status}",
                            foreground="red"
                        )
                
                # Update toggle button
                if hasattr(self, 'redis_toggle_button'):
                    self.redis_toggle_button.config(
                        text="Stop Server" if is_running else "Start Server",
                        state="normal"
                    )
                
                # Update Quantum Nexus status
                self._update_redis_quantum_nexus_status()
                
            except Exception as e:
                self.logger.error(f"Error in UI update: {e}")
        
        # Schedule the UI update in the main thread
        if hasattr(self, 'after'):
            self.after(0, update_ui)
        else:
            update_ui()
            
    except Exception as e:
        self.logger.error(f"Error updating Redis status UI: {e}")
        if hasattr(self, 'redis_status_label'):
            try:
                self.redis_status_label.config(
                    text="Error: Check Logs",
                    foreground="orange"
                )
            except:
                pass

def _update_redis_quantum_nexus_status(self):
    """Update the Redis Quantum Nexus system indicator."""
    try:
        if not hasattr(self, 'system_indicators'):
            return
                
        # Ensure status dict exists
        if not hasattr(self, 'redis_status_dict'):
            self.redis_status_dict = {
                "connected": False,
                "server_running": False,
                "port": 6380,
                "version": "Unknown",
                "uptime": 0,
                "clients": 0,
                "memory_used": 0
            }
            
        is_connected = self.redis_status_dict.get('connected', False)
        port = self.redis_status_dict.get('port', 6380)
        
        # Update the system indicator
        def update_ui():
            try:
                if is_connected and port == 6380:
                    status_text = f"Redis Quantum Nexus: Online (Port: {port})"
                    self._update_system_indicator(
                        'redis_quantum_nexus', 
                        status_text, 
                        '#4CAF50'  # Green
                    )
                    
                    # Update Redis info labels if they exist
                    if hasattr(self, 'redis_info_labels'):
                        if 'version' in self.redis_info_labels:
                            self.redis_info_labels['version'].config(
                                text=f"Version: {self.redis_status_dict.get('version', 'Unknown')}"
                            )
                        if 'uptime' in self.redis_info_labels:
                            uptime = self.redis_status_dict.get('uptime', 0)
                            hours, remainder = divmod(uptime, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            self.redis_info_labels['uptime'].config(
                                text=f"Uptime: {int(hours)}h {int(minutes)}m {int(seconds)}s"
                            )
                        if 'memory' in self.redis_info_labels:
                            memory_used = self.redis_status_dict.get('memory_used', 0)
                            self.redis_info_labels['memory'].config(
                                text=f"Memory: {memory_used:.2f} MB"
                            )
                else:
                    port_status = "" if port == 6380 else f" (Port: {port}, should be 6380)"
                    status_text = f"Redis Quantum Nexus: Offline{port_status}"
                    self._update_system_indicator(
                        'redis_quantum_nexus', 
                        status_text, 
                        '#F44336'  # Red
                    )
                
                # Update the Kingdom AI status
                self._update_kingdom_ai_status()
                
            except Exception as e:
                self.logger.error(f"Error in Quantum Nexus UI update: {e}")
        
        # Schedule the UI update in the main thread
        if hasattr(self, 'after'):
            self.after(0, update_ui)
        else:
            update_ui()
        
    except Exception as e:
        self.logger.error(f"Error updating Redis Quantum Nexus status: {e}")
        if hasattr(self, 'redis_status_label'):
            try:
                self.redis_status_label.config(
                    text="Error: Check Logs",
                    foreground="orange"
                )
            except:
                pass

def _update_kingdom_ai_status(self):
    """Update the Kingdom AI system status based on Redis and API Key Manager status."""
    try:
        # Check if Redis and API Key Manager are connected
        redis_connected = self.redis_status_dict.get("connected", False)
        api_keys_loaded = len(self.data_service_keys) > 0 if hasattr(self, 'data_service_keys') else False
        
        blockchain_connected = self.blockchain_status.get("blockchain_connected", False) if hasattr(self, 'blockchain_status') else False

        if hasattr(self, '_update_system_indicator'):
            if redis_connected and api_keys_loaded and blockchain_connected:
                self._update_system_indicator("kingdom_ai", "Online", "#4CAF50")  # Green
            elif redis_connected or api_keys_loaded or blockchain_connected:
                self._update_system_indicator("kingdom_ai", "Partial", "#FFC107")  # Yellow/Amber
            else:
                self._update_system_indicator("kingdom_ai", "Offline", "#F44336")  # Red
    except Exception as e:
        self.logger.error(f"Error updating Kingdom AI status: {e}")

def _update_system_indicator(self, system_id, status_text, color="#FFEB3B"):
    """Update a system status indicator.
    
    Args:
        system_id: ID of the system to update
        status_text: Status text to display
        color: Color for the LED indicator
    """
    if hasattr(self, 'system_indicators') and system_id in self.system_indicators:
        indicator = self.system_indicators[system_id]
        if hasattr(indicator["status"], "config"):
            indicator["status"].config(text=status_text)
        if hasattr(indicator["indicator"], "itemconfig") and "led" in indicator:
            indicator["indicator"].itemconfig(indicator["led"], fill=color)
        if hasattr(self, 'log_message'):
            self.log_message(f"{indicator['label']['text']}: {status_text}")
            
async def _handle_market_update(self, event_data):
    """Handle market update events."""
    try:
        if "symbol" in event_data and "price" in event_data:
            self.log_message(f"Market update: {event_data['symbol']} = {event_data['price']}")
    except Exception as e:
        self.logger.error(f"Error handling market update: {e}")

async def _handle_wallet_update(self, event_data):
    """Handle wallet update events."""
    try:
        if "balance" in event_data:
            self.log_message(f"Wallet balance updated: {event_data['balance']}")
    except Exception as e:
        self.logger.error(f"Error handling wallet update: {e}")

async def _handle_mining_update(self, event_data):
    """Handle mining status events."""
    try:
        if "hashrate" in event_data:
            self.log_message(f"Mining hashrate: {event_data['hashrate']} H/s")
    except Exception as e:
        self.logger.error(f"Error handling mining update: {e}")

async def _handle_vr_update(self, event_data):
    """Handle VR status events."""
    try:
        if "status" in event_data:
            self.log_message(f"VR status: {event_data['status']}")
    except Exception as e:
        self.logger.error(f"Error handling VR update: {e}")

async def _start_background_tasks(self):
    """Start background tasks for dashboard monitoring."""
    try:
        self.logger.debug("Starting dashboard background tasks")
        # Additional background task initialization can go here
        return True
    except Exception as e:
        self.logger.error(f"Error starting background tasks: {e}")
        return False
        
async def _load_system_packages(self):
    """Load system package information."""
    try:
        self.logger.debug("Loading system package information")
        # Implementation can be added here
        return True
    except Exception as e:
        self.logger.error(f"Error loading system packages: {e}")
        return False
        
async def _handle_blockchain_status(self, event_data):
    """Handle blockchain status events.
    
    Args:
        event_data: Dictionary containing blockchain status information with keys:
            - status_type: Type of status (e.g., 'connected', 'error')
            - message: Status message
            - data: Additional status data including:
                - is_connected: Boolean indicating connection status
                - chain_id: Network chain ID
                - client_version: Node client version
    """
    try:
        self.logger.debug(f"Handling blockchain status: {event_data}")
        
        # Update blockchain status
        self.blockchain_status = {
            "blockchain_connected": event_data.get('connected', False),
            "web3_connected": event_data.get('web3_connected', False),
            "connection_type": event_data.get('connection_type', 'none'),
            "network": event_data.get('network', 'unknown'),
            "node_version": event_data.get('node_version', 'unknown')
        }
        
        # Update UI based on connection status
        if self.blockchain_status['blockchain_connected']:
            self._update_system_indicator('blockchain', "Connected", '#4CAF50')  # Green
            self.log_message("Blockchain connected")
        elif self.blockchain_status['web3_connected']:
            self._update_system_indicator('blockchain', "Web3 Connected", '#4CAF50')  # Green
            self.log_message("Web3 connected")
        else:
            self._update_system_indicator('blockchain', "Disconnected", '#F44336')  # Red
            self.log_message("Blockchain disconnected")
        
        # Update Kingdom AI status which depends on blockchain status
        self._update_kingdom_ai_status()
        
        # Update Redis server status in UI
        status = event_data.get('status', 'stopped')
        self._update_redis_quantum_nexus_status(status == 'running')
        return True
    except Exception as e:
        self.logger.error(f"Error handling blockchain status: {e}")
        return False
            
    async def _handle_market_data(self, event_data):
        """Handle market data events."""
        try:
            self.logger.debug(f"Handling market data: {event_data}")
            # Process market data and update UI
            return True
        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")
            return False
            
    # Note: _handle_api_key_update is defined more comprehensively earlier in the file
