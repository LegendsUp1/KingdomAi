#!/usr/bin/env python3
"""
Kingdom AI - Diagnostic Frame

This module implements a diagnostic frame for the Kingdom AI GUI that displays
system health information, component statuses, event bus activity, and provides
tools for troubleshooting and system configuration.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
import asyncio
import traceback
from datetime import datetime
import time
from typing import Dict, Any, Optional, List

from gui.frames.base_frame import BaseFrame

logger = logging.getLogger("KingdomAI.DiagnosticFrame")

class DiagnosticsFrame(BaseFrame):
    """Frame for system diagnostics and health monitoring."""
    
    def __init__(self, parent, event_bus=None, api_key_connector=None):
        """Initialize the diagnostic frame.
        
        Args:
            parent: The parent widget
            event_bus: The application event bus
            api_key_connector: Connector for accessing API keys
        """
        # Call parent constructor and store api_key_connector explicitly
        super().__init__(parent, event_bus=event_bus, name="Diagnostics")
        self.api_key_connector = api_key_connector
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Initialize state
        self.component_statuses = {}
        self.event_counter = 0
        self.event_history = []
        self.max_event_history = 100
        self.system_start_time = time.time()
        
        # API keys status
        self.api_key_statuses = {}
        self.api_keys_tree = None
        self.api_services = [
            'binance', 'coinbase', 'kraken', 'kucoin', 'bitfinex',  # Exchanges
            'openai', 'claude', 'stability',  # AI services
            'infura', 'alchemy',  # Blockchain providers
            'alphavantage', 'finnhub',  # Market data
            'ethermine', 'flypool', 'f2pool'  # Mining pools
        ]
        
        # Create widgets
        self._create_widgets()
        
        # Subscribe to events
        self._subscribe_to_events()
        
    def _create_widgets(self):
        """Create widgets for the diagnostic frame."""
        # Use a consistent geometry manager, choosing 'pack' for the main layout
        self.logger.info("Creating diagnostic widgets")
        
        # Main layout
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Control area
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        # Title
        title_label = ttk.Label(control_frame, text="System Diagnostics", font=("Arial", 14, "bold"))
        title_label.pack(side=tk.LEFT, padx=5)
        
        # Buttons
        refresh_button = ttk.Button(control_frame, text="Refresh", command=self._on_refresh)
        refresh_button.pack(side=tk.RIGHT, padx=5)
        
        test_button = ttk.Button(control_frame, text="Test Event Bus", command=self._on_test_event_bus)
        test_button.pack(side=tk.RIGHT, padx=5)
        
        clear_button = ttk.Button(control_frame, text="Clear Events", command=self._on_clear_events)
        clear_button.pack(side=tk.RIGHT, padx=5)
        
        # Notebook for different diagnostic views
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Component status tab
        self.status_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.status_frame, text="Component Status")
        
        # API keys tab
        self.api_keys_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.api_keys_frame, text="API Keys")
        
        # Event monitor tab
        self.event_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.event_frame, text="Event Monitor")
        
        # Log viewer tab
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="Log Viewer")
        
        # System info tab
        self.info_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.info_frame, text="System Info")
        
        # Setup each tab
        self._setup_status_tab()
        self._setup_event_tab()
        self._setup_log_tab()
        self._setup_info_tab()
        self._create_api_keys_tab()
        
    def _create_api_keys_tab(self):
        """Create the API keys tab."""
        # Configure layout
        self.api_keys_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # API keys treeview
        self.api_keys_tree = ttk.Treeview(
            self.api_keys_frame, 
            columns=("service", "status", "last_update", "details"),
            show="headings"
        )
        
        # Configure headings
        self.api_keys_tree.heading("service", text="Service")
        self.api_keys_tree.heading("status", text="Status")
        self.api_keys_tree.heading("last_update", text="Last Update")
        self.api_keys_tree.heading("details", text="Details")
        
        # Configure columns
        self.api_keys_tree.column("service", width=150)
        self.api_keys_tree.column("status", width=100)
        self.api_keys_tree.column("last_update", width=150)
        self.api_keys_tree.column("details", width=300)
        
        # Add scrollbar
        api_keys_scrollbar = ttk.Scrollbar(self.api_keys_frame, orient="vertical", command=self.api_keys_tree.yview)
        self.api_keys_tree.configure(yscrollcommand=api_keys_scrollbar.set)
        
        # Place treeview and scrollbar
        self.api_keys_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        api_keys_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def _update_api_keys_tab(self):
        """Update the API keys tab."""
        # Ensure the API keys tree exists
        if not self.api_keys_tree:
            return
            
        # Clear existing items
        for item in self.api_keys_tree.get_children():
            self.api_keys_tree.delete(item)
        
        # Add API key statuses
        for service, status_data in self.api_key_statuses.items():
            status = status_data["status"]
            timestamp = status_data["last_update"]
            details = status_data.get("details", "")
            
            # Format timestamp for display
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime("%H:%M:%S %Y-%m-%d")
            except:
                formatted_time = timestamp
            
            self.api_keys_tree.insert("", "end", values=(service, status, formatted_time, details))
            
        # If no keys loaded yet, show default services
        if not self.api_key_statuses and self.api_services:
            for service in self.api_services:
                self.api_keys_tree.insert("", "end", values=(service, "Unknown", "", "Not checked yet"))
    
    def _setup_status_tab(self):
        """Set up the component status tab."""
        # Configure layout
        self.status_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Component status treeview
        self.status_tree = ttk.Treeview(
            self.status_frame, 
            columns=("component", "status", "last_update", "details"),
            show="headings"
        )
        
        # Configure headings
        self.status_tree.heading("component", text="Component")
        self.status_tree.heading("status", text="Status")
        self.status_tree.heading("last_update", text="Last Update")
        self.status_tree.heading("details", text="Details")
        
        # Configure columns
        self.status_tree.column("component", width=150)
        self.status_tree.column("status", width=100)
        self.status_tree.column("last_update", width=150)
        self.status_tree.column("details", width=300)
        
        # Add scrollbar
        status_scrollbar = ttk.Scrollbar(self.status_frame, orient="vertical", command=self.status_tree.yview)
        self.status_tree.configure(yscrollcommand=status_scrollbar.set)
        
        # Place treeview and scrollbar
        self.status_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def _setup_event_tab(self):
        """Set up the event monitor tab."""
        # Configure layout
        self.event_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Filter area
        filter_frame = ttk.Frame(self.event_frame)
        filter_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)
        
        self.filter_entry = ttk.Entry(filter_frame, width=30)
        self.filter_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            filter_frame, 
            text="Apply Filter", 
            command=self._on_apply_filter
        ).pack(side=tk.LEFT, padx=5)
        
        # Event statistics
        self.event_stats_label = ttk.Label(filter_frame, text="Events: 0")
        self.event_stats_label.pack(side=tk.LEFT, padx=10)
        
        # Event list
        event_list_frame = ttk.Frame(self.event_frame)
        event_list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Event treeview
        self.event_tree = ttk.Treeview(
            event_list_frame, 
            columns=("timestamp", "event_type", "source", "details"),
            show="headings"
        )
        
        # Configure headings
        self.event_tree.heading("timestamp", text="Timestamp")
        self.event_tree.heading("event_type", text="Event Type")
        self.event_tree.heading("source", text="Source")
        self.event_tree.heading("details", text="Details")
        
        # Configure columns
        self.event_tree.column("timestamp", width=150)
        self.event_tree.column("event_type", width=150)
        self.event_tree.column("source", width=100)
        self.event_tree.column("details", width=300)
        
        # Add scrollbar
        event_scrollbar = ttk.Scrollbar(event_list_frame, orient="vertical", command=self.event_tree.yview)
        self.event_tree.configure(yscrollcommand=event_scrollbar.set)
        
        # Place treeview and scrollbar
        self.event_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        event_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def _setup_log_tab(self):
        """Set up the log viewer tab."""
        # Configure layout
        self.log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Control area
        log_control_frame = ttk.Frame(self.log_frame)
        log_control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Log level selection
        ttk.Label(log_control_frame, text="Log Level:").pack(side=tk.LEFT, padx=5)
        
        self.log_level = tk.StringVar(value="INFO")
        log_level_combo = ttk.Combobox(
            log_control_frame, 
            textvariable=self.log_level, 
            values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
        log_level_combo.pack(side=tk.LEFT, padx=5)
        log_level_combo.bind("<<ComboboxSelected>>", self._on_log_level_changed)
        
        # Refresh logs button
        ttk.Button(
            log_control_frame, 
            text="Refresh Logs", 
            command=self._on_refresh_logs
        ).pack(side=tk.LEFT, padx=5)
        
        # Auto-refresh checkbox
        self.auto_refresh_var = tk.BooleanVar(value=False)
        auto_refresh_check = ttk.Checkbutton(
            log_control_frame, 
            text="Auto Refresh", 
            variable=self.auto_refresh_var,
            command=self._on_auto_refresh_toggled
        )
        auto_refresh_check.pack(side=tk.LEFT, padx=15)
        
        # Log file selection
        ttk.Label(log_control_frame, text="Log File:").pack(side=tk.LEFT, padx=5)
        
        self.log_file = tk.StringVar(value="kingdom_error.log")
        log_file_combo = ttk.Combobox(
            log_control_frame, 
            textvariable=self.log_file, 
            values=["kingdom_error.log", "kingdom_info.log", "windsurf_setup.log"]
        )
        log_file_combo.pack(side=tk.LEFT, padx=5)
        log_file_combo.bind("<<ComboboxSelected>>", self._on_log_file_changed)
        
        # Log content
        log_content_frame = ttk.Frame(self.log_frame)
        log_content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Log text area
        self.log_text = scrolledtext.ScrolledText(
            log_content_frame,
            wrap=tk.WORD,
            background="#1e1e1e",
            foreground="#f0f0f0",
            font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.log_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Configure tags for different log levels
        self.log_text.tag_configure("DEBUG", foreground="#3498DB")
        self.log_text.tag_configure("INFO", foreground="#58D68D")
        self.log_text.tag_configure("WARNING", foreground="#F4D03F")
        self.log_text.tag_configure("ERROR", foreground="#E74C3C")
        self.log_text.tag_configure("CRITICAL", foreground="#EC7063", background="#641E16")
        
    def _setup_info_tab(self):
        """Set up the system info tab."""
        # Configure layout
        self.info_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Create scrollable frame
        info_canvas = tk.Canvas(self.info_frame, borderwidth=0)
        info_scrollbar = ttk.Scrollbar(self.info_frame, orient="vertical", command=info_canvas.yview)
        info_scrollable_frame = ttk.Frame(info_canvas)
        
        info_scrollable_frame.bind(
            "<Configure>",
            lambda e: info_canvas.configure(scrollregion=info_canvas.bbox("all"))
        )
        
        info_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        info_canvas.create_window((0, 0), window=info_scrollable_frame, anchor="nw")
        info_canvas.configure(yscrollcommand=info_scrollbar.set)
        
        # System info sections
        sections = [
            {"title": "System Overview", "id": "overview"},
            {"title": "Event Bus Statistics", "id": "event_bus"},
            {"title": "Component Health", "id": "components"},
            {"title": "Resource Usage", "id": "resources"},
            {"title": "Environment", "id": "environment"}
        ]
        
        # Create frames for each section
        self.info_sections = {}
        
        for i, section in enumerate(sections):
            # Section frame
            section_frame = ttk.LabelFrame(info_scrollable_frame, text=section["title"])
            section_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
            
            # Content frame for section
            content_frame = ttk.Frame(section_frame)
            content_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
            
            # Store reference
            self.info_sections[section["id"]] = content_frame
            
    async def _get_api_key(self, service):
        """Get API key for a specific service.
        
        Args:
            service: The service to get the API key for
            
        Returns:
            The API key if found, None otherwise
        """
        try:
            if not hasattr(self, 'api_key_connector') or not self.api_key_connector:
                self.logger.warning(f"No API key connector available for {service}")
                return None
                
            # Try to get the key from the connector
            key = await self.api_key_connector.get_api_key(service)
            if key:
                # Update status in our tracking dict
                self.api_key_statuses[service] = {
                    'status': 'Valid',
                    'last_update': datetime.now().isoformat()
                }
                return key
            else:
                self.api_key_statuses[service] = {
                    'status': 'Missing',
                    'last_update': datetime.now().isoformat()
                }
                self.logger.warning(f"API key not found for {service}")
                return None
        except Exception as e:
            self.api_key_statuses[service] = {
                'status': 'Error',
                'last_update': datetime.now().isoformat(),
                'error': str(e)
            }
            self.logger.error(f"Error getting API key for {service}: {e}")
            return None
        
    async def _handle_api_key_update(self, event_type, data):
        """Handle API key update event.
        
        Args:
            event_type: The event type
            data: Event data containing the service and status
        """
        if not data:
            return
        
        service = data.get('service')
        if not service:
            return
        
        # Update our tracking of API key status
        self.api_key_statuses[service] = {
            'status': data.get('status', 'Unknown'),
            'last_update': datetime.now().isoformat(),
            'details': data.get('details', '')
        }
        
        # Refresh the API keys tab if it exists
        self._update_api_keys_tab()
        
    async def _load_initial_api_keys(self):
        """Load initial API key statuses for all known services."""
        try:
            if not hasattr(self, 'api_key_connector') or not self.api_key_connector:
                self.logger.warning("No API key connector available for initial key loading")
                return
                
            # Check status for all known services
            for service in self.api_services:
                try:
                    # Attempt to get the key to check its validity
                    await self._get_api_key(service)
                except Exception as e:
                    self.logger.error(f"Error loading initial status for {service}: {e}")
                    self.api_key_statuses[service] = {
                        'status': 'Error',
                        'last_update': datetime.now().isoformat(),
                        'error': str(e)
                    }
            
            # Update the API keys display
            self._update_api_keys_tab()
        except Exception as e:
            self.logger.error(f"Error loading initial API keys: {e}")
            self.logger.error(traceback.format_exc())

    async def _handle_component_status(self, event_type, data):
        """Handle component status event."""
        if not data:
            return

        component = data.get("component", "Unknown")
        status = data.get("status", "Unknown")
        details = data.get("details", "")
        timestamp = data.get("timestamp", datetime.now().isoformat())

        # Update component status
        self.component_statuses[component] = {
            "status": status,
            "last_update": timestamp,
            "details": details
        }

        # Update status treeview
        self._update_status_tree()

    async def _handle_system_metrics(self, event_data):
        """Handle system metrics updates.

        Args:
            event_data: System metrics data
        """
        try:
            if not event_data:
                return
                
            # Update system metrics display
            self._update_system_info(event_data)
        except Exception as e:
            logger.error(f"Error handling system metrics: {e}")
            logger.error(traceback.format_exc())

    async def _monitor_all_events(self, event_type, data):
        """Monitor all events for the event monitor."""
        # Skip internal diagnostic events to avoid loops
        if event_type.startswith("diagnostic."):
            return
            
        # Increment event counter
        self.event_counter += 1
        
        # Update event stats
        self.event_stats_label.config(text=f"Events: {self.event_counter}")
        
        # Add to event history
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "source": data.get("source", "Unknown") if data else "Unknown",
            "data": data
        }
        
        self.event_history.append(event_data)
        
        # Limit history size
        if len(self.event_history) > self.max_event_history:
            self.event_history = self.event_history[-self.max_event_history:]
        
        # Update event tree
        self._update_event_tree()

    async def _handle_log_entry(self, event_type, data):
        """Handle log entry event."""
        if not data:
            return
            
        log_level = data.get("level", "INFO")
        message = data.get("message", "")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        log_file = data.get("log_file", "kingdom_error.log")
        
        # Check if this log entry should be displayed
        if log_file == self.log_file.get() and self._should_show_log_level(log_level):
            self._add_log_entry(timestamp, log_level, message)
    
    async def _handle_system_info(self, event_type, data):
        """Handle system info event."""
        if not data:
            return
            
        # Update system info sections
        self._update_system_info(data)
    
    async def _handle_test_response(self, event_type, data):
        """Handle test response event."""
        if not data:
            return
            
        success = data.get("success", False)
        message = data.get("message", "")
        response_time = data.get("response_time", 0)
        
        # Show result in a dialog
        if success:
            self._add_log_entry(
                datetime.now().isoformat(),
                "INFO",
                f"Event bus test successful: Response time {response_time}ms"
            )
        else:
            self._add_log_entry(
                datetime.now().isoformat(),
                "ERROR",
                f"Event bus test failed: {message}"
            )
    
    def _update_status_tree(self):
        """Update the component status treeview."""
        # Clear existing items
        for item in self.status_tree.get_children():
            self.status_tree.delete(item)
        
        # Add component statuses
        for component, status_data in self.component_statuses.items():
            status = status_data["status"]
            timestamp = status_data["last_update"]
            details = status_data["details"]
            
            # Format timestamp for display
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime("%H:%M:%S %Y-%m-%d")
            except:
                formatted_time = timestamp
            
            self.status_tree.insert("", "end", values=(component, status, formatted_time, details))
    
    def _update_event_tree(self):
        """Update the event monitor treeview."""
        # Clear existing items
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)
        
        # Apply filter if any
        filter_text = self.filter_entry.get().lower()
        filtered_events = self.event_history
        
        if filter_text:
            filtered_events = [
                e for e in self.event_history 
                if filter_text in e["event_type"].lower() or 
                   filter_text in str(e["source"]).lower() or
                   filter_text in str(e["data"]).lower()
            ]
        
        # Add events
        for event in reversed(filtered_events):  # Newest first
            timestamp = event["timestamp"]
            event_type = event["event_type"]
            source = event["source"]
            data_str = str(event["data"])
            
            # Format timestamp for display
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime("%H:%M:%S.%f")[:-3]
            except:
                formatted_time = timestamp
            
            # Truncate data string if too long
            if len(data_str) > 100:
                data_str = data_str[:97] + "..."
            
            self.event_tree.insert("", "end", values=(formatted_time, event_type, source, data_str))
    
    def _update_system_info(self, data=None):
        """Update the system info tab with the latest data."""
        # Clear existing content
        for section_frame in self.info_sections.values():
            for widget in section_frame.winfo_children():
                widget.destroy()
        
        # System Overview section
        overview_frame = self.info_sections["overview"]
        
        # Calculate uptime
        uptime_seconds = time.time() - self.system_start_time
        days, remainder = divmod(int(uptime_seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        # Add system overview info
        system_info = [
            ("System Name", "Kingdom AI"),
            ("Status", "Running"),
            ("Uptime", uptime_str),
            ("Connected Components", str(len(self.component_statuses))),
            ("Events Processed", str(self.event_counter))
        ]
        
        for i, (label, value) in enumerate(system_info):
            ttk.Label(overview_frame, text=label + ":", width=20).pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
            ttk.Label(overview_frame, text=value).pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
        
        # Event Bus Statistics section
        event_bus_frame = self.info_sections["event_bus"]
        
        # Add sample event bus stats
        ttk.Label(event_bus_frame, text="Active Events:").pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
        
        # Show top 5 event types
        for i, (event_type, count) in enumerate(sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:5]):
            ttk.Label(event_bus_frame, text=f"{event_type}: {count}").pack(side=tk.TOP, fill=tk.X, padx=20, pady=2)
        
        # Other sections - can be populated with actual data when available
        if data:
            # Add custom data from the system.info event if available
            pass
    
    def _add_log_entry(self, timestamp, level, message):
        """Add a log entry to the log viewer."""
        self.log_text.config(state=tk.NORMAL)
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime("%H:%M:%S.%f")[:-3]
        except:
            formatted_time = timestamp
        
        # Format log entry
        log_entry = f"[{formatted_time}] [{level}] {message}\n"
        
        # Insert with appropriate tag
        self.log_text.insert(tk.END, log_entry, level)
        
        # Scroll to end
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def _on_refresh(self):
        """Handle refresh button click."""
        try:
            # Refresh component statuses
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("diagnostic.refresh", {
                    "source": "DiagnosticsFrame",
                    "timestamp": datetime.now().isoformat()
                }))
                
            # Refresh system info
            self._update_system_info()
            
            # Refresh API keys
            asyncio.create_task(self._load_initial_api_keys())
        except Exception as e:
            self.logger.error(f"Error refreshing diagnostics: {e}")
            self.logger.error(traceback.format_exc())
    
    def _on_test_event_bus(self):
        """Handle test event bus button click."""
        # Send a test event and measure response time
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish("diagnostic.test_request", {
                "source": "diagnostic_frame",
                "timestamp": datetime.now().isoformat(),
                "test_id": str(int(time.time()))
            }))
            
            self._add_log_entry(
                datetime.now().isoformat(),
                "INFO",
                "Sent event bus test request"
            )
    
    def _on_clear_events(self):
        """Handle clear events button click."""
        # Clear event history
        self.event_history = []
        
        # Update event tree
        self._update_event_tree()
    
    def _on_apply_filter(self):
        """Handle apply filter button click."""
        # Update event tree with filter
        self._update_event_tree()
    
    def _on_log_level_changed(self, event):
        """Handle log level changed event."""
        # Request logs with the new level
        self._on_refresh_logs()
    
    def _on_log_file_changed(self, event):
        """Handle log file changed event."""
        # Request logs from the new file
        self._on_refresh_logs()
    
    def _on_refresh_logs(self):
        """Handle refresh logs button click."""
        # Clear existing logs
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # Request log entries
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish("log.request_entries", {
                "source": "diagnostic_frame",
                "log_file": self.log_file.get(),
                "log_level": self.log_level.get(),
                "timestamp": datetime.now().isoformat()
            }))
    
    def _on_auto_refresh_toggled(self):
        """Handle auto refresh checkbox toggled."""
        try:
            enabled = self.auto_refresh_var.get()
            if enabled:
                self._auto_refresh_job = self.after(5000, self._auto_refresh_tick)
                logger.info("Auto-refresh enabled (5s interval)")
            else:
                if hasattr(self, '_auto_refresh_job') and self._auto_refresh_job:
                    self.after_cancel(self._auto_refresh_job)
                    self._auto_refresh_job = None
                logger.info("Auto-refresh disabled")
        except Exception as e:
            logger.error("Error toggling auto-refresh: %s", e)

    def _auto_refresh_tick(self):
        """Perform an auto-refresh cycle and schedule the next one."""
        try:
            if self.auto_refresh_var.get():
                self._on_refresh()
                self._auto_refresh_job = self.after(5000, self._auto_refresh_tick)
        except Exception as e:
            logger.error("Error in auto-refresh tick: %s", e)
    
    def _should_show_log_level(self, level):
        """Check if a log level should be shown based on the current filter."""
        levels = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "ERROR": 3,
            "CRITICAL": 4
        }
        
        current_level = levels.get(self.log_level.get(), 0)
        level_value = levels.get(level, 0)
        
        return level_value >= current_level

    def _setup_layout(self):
        """Setup the layout of the diagnostics frame using grid."""
        logger.info("Setting up layout for DiagnosticsFrame with grid manager")
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Ensure all child widgets use grid
        for child in self.winfo_children():
            if hasattr(child, 'pack'):
                child.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
