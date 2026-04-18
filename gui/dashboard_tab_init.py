"""
Kingdom AI Dashboard Tab Initialization Module
This module provides the initialization method for the Dashboard tab in the Kingdom AI GUI.
"""

import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("KingdomAI.TabManager")

async def _init_dashboard_tab(self, tab_frame):
    """Initialize the dashboard tab with system overview and metrics.
    
    This method follows the 8-step lifecycle:
    1. Retrieval - Locate data sources
    2. Fetching - Active data retrieval
    3. Binding - Connect data to GUI elements
    4. Formatting - Present data in readable format
    5. Event Handling - Respond to user/system events
    6. Concurrency - Prevent UI blocking
    7. Error Handling - Graceful error management
    8. Debugging - Tools for diagnostics
    
    Args:
        tab_frame: The tab frame to populate
    """
    try:
        # STEP 1: RETRIEVAL - Identify data sources
        data_sources = {
            "system_stats": "system_monitor",
            "market_data": "market_api",
            "ai_stats": "thoth_metrics",
            "alerts": "notification_service"
        }
        logger.info(f"Dashboard initializing with data sources: {list(data_sources.keys())}")
        
        # Create UI based on framework
        if self.using_pyqt:
            await self._init_dashboard_pyqt(tab_frame)
        elif self.using_tkinter:
            await self._init_dashboard_tkinter(tab_frame)
            
        # STEP 6: CONCURRENCY - Fetch initial data asynchronously
        if self.event_bus:
            await self.request_dashboard_updates()
            
        # STEP 8: DEBUGGING - Log completion
        logger.info("Dashboard initialized with system overview")
        
    except Exception as e:
        # STEP 7: ERROR HANDLING
        logger.error(f"Error initializing dashboard tab: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        
        # Display error in UI if possible
        try:
            if hasattr(self, 'dashboard_status'):
                if self.using_pyqt:
                    self.dashboard_status.setText("Error: Failed to initialize dashboard")
                    self.dashboard_status.setStyleSheet("color: red;")
                else:
                    self.dashboard_status.config(text="Error: Failed to initialize dashboard", foreground="red")
        except Exception:
            pass

async def _init_dashboard_pyqt(self, tab_frame):
    """Initialize dashboard with PyQt UI components."""
    from PyQt6.QtWidgets import (QLabel, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QFrame, QGridLayout, QProgressBar)
    from PyQt6.QtCore import Qt
    
    # Main layout
    layout = tab_frame.layout()
    
    # Header with title and status
    header_widget = QFrame()
    header_layout = QHBoxLayout(header_widget)
    
    title_label = QLabel("System Dashboard")
    title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
    header_layout.addWidget(title_label, 1)
    
    self.dashboard_status = QLabel("Status: Initializing...")
    header_layout.addWidget(self.dashboard_status)
    
    layout.addWidget(header_widget)
    
    # System Overview Section
    system_frame = QFrame()
    system_frame.setFrameShape(QFrame.Shape.StyledPanel)
    system_layout = QGridLayout(system_frame)
    
    # CPU, Memory, etc. widgets
    system_layout.addWidget(QLabel("CPU Usage:"), 0, 0)
    self.cpu_bar = QProgressBar()
    self.cpu_bar.setRange(0, 100)
    system_layout.addWidget(self.cpu_bar, 0, 1)
    
    system_layout.addWidget(QLabel("Memory Usage:"), 1, 0)
    self.memory_bar = QProgressBar()
    self.memory_bar.setRange(0, 100)
    system_layout.addWidget(self.memory_bar, 1, 1)
    
    # Component status
    system_layout.addWidget(QLabel("Components Active:"), 2, 0)
    self.components_label = QLabel("0/0")
    system_layout.addWidget(self.components_label, 2, 1)
    
    layout.addWidget(system_frame)
    
    # Market Overview
    market_frame = QFrame()
    market_frame.setFrameShape(QFrame.Shape.StyledPanel)
    market_layout = QVBoxLayout(market_frame)
    
    market_header = QLabel("Market Overview")
    market_header.setStyleSheet("font-weight: bold;")
    market_layout.addWidget(market_header)
    
    self.market_stats = QLabel("Loading market data...")
    market_layout.addWidget(self.market_stats)
    
    layout.addWidget(market_frame)
    
    # Recent Activity
    activity_frame = QFrame()
    activity_frame.setFrameShape(QFrame.Shape.StyledPanel)
    activity_layout = QVBoxLayout(activity_frame)
    
    activity_header = QLabel("Recent Activity")
    activity_header.setStyleSheet("font-weight: bold;")
    activity_layout.addWidget(activity_header)
    
    self.activity_list = QLabel("No recent activities")
    activity_layout.addWidget(self.activity_list)
    
    layout.addWidget(activity_frame)
    
    # Action buttons
    action_frame = QFrame()
    action_layout = QHBoxLayout(action_frame)
    
    refresh_btn = QPushButton("Refresh Dashboard")
    refresh_btn.clicked.connect(self.refresh_dashboard)
    action_layout.addWidget(refresh_btn)
    
    settings_btn = QPushButton("Dashboard Settings")
    settings_btn.clicked.connect(self.dashboard_settings)
    action_layout.addWidget(settings_btn)
    
    layout.addWidget(action_frame)
    
    # STEP 3: BINDING - Register widgets for data updates
    if hasattr(self, 'widget_registry'):
        await self.widget_registry.register_widget("cpu_usage", self.cpu_bar)
        await self.widget_registry.register_widget("memory_usage", self.memory_bar)
        await self.widget_registry.register_widget("components_active", self.components_label)
        await self.widget_registry.register_widget("market_stats", self.market_stats)
        await self.widget_registry.register_widget("activity_list", self.activity_list)
        await self.widget_registry.register_widget("dashboard_status", self.dashboard_status)

async def _init_dashboard_tkinter(self, tab_frame):
    """Initialize dashboard with Tkinter UI components."""
    import tkinter as tk
    from tkinter import ttk
    
    # Create frame structure
    title_frame = ttk.Frame(tab_frame)
    title_frame.pack(fill="x", padx=10, pady=5)
    
    title_label = ttk.Label(title_frame, text="System Dashboard", font=("Helvetica", 14, "bold"))
    title_label.pack(side="left")
    
    self.dashboard_status = ttk.Label(title_frame, text="Status: Initializing...")
    self.dashboard_status.pack(side="right")
    
    # System Overview Frame
    system_frame = ttk.LabelFrame(tab_frame, text="System Overview")
    system_frame.pack(fill="x", expand=False, padx=10, pady=5)
    
    # System metrics grid
    system_grid = ttk.Frame(system_frame)
    system_grid.pack(fill="x", padx=5, pady=5)
    
    ttk.Label(system_grid, text="CPU Usage:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    self.cpu_bar = ttk.Progressbar(system_grid, orient=tk.HORIZONTAL, length=200, mode='determinate')
    self.cpu_bar.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
    self.cpu_bar["value"] = 0
    
    ttk.Label(system_grid, text="Memory Usage:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    self.memory_bar = ttk.Progressbar(system_grid, orient=tk.HORIZONTAL, length=200, mode='determinate')
    self.memory_bar.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
    self.memory_bar["value"] = 0
    
    ttk.Label(system_grid, text="Components Active:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    self.components_label = ttk.Label(system_grid, text="0/0")
    self.components_label.grid(row=2, column=1, sticky="w", padx=5, pady=2)
    
    # Market Overview Frame
    market_frame = ttk.LabelFrame(tab_frame, text="Market Overview")
    market_frame.pack(fill="x", expand=False, padx=10, pady=5)
    
    self.market_stats = ttk.Label(market_frame, text="Loading market data...")
    self.market_stats.pack(anchor="w", padx=5, pady=5)
    
    # Recent Activity Frame
    activity_frame = ttk.LabelFrame(tab_frame, text="Recent Activity")
    activity_frame.pack(fill="both", expand=True, padx=10, pady=5)
    
    self.activity_list = ttk.Label(activity_frame, text="No recent activities")
    self.activity_list.pack(anchor="w", padx=5, pady=5)
    
    # Actions Frame
    actions_frame = ttk.Frame(tab_frame)
    actions_frame.pack(fill="x", padx=10, pady=10)
    
    refresh_btn = ttk.Button(actions_frame, text="Refresh Dashboard", command=self.refresh_dashboard)
    refresh_btn.pack(side="left", padx=5)
    
    settings_btn = ttk.Button(actions_frame, text="Dashboard Settings", command=self.dashboard_settings)
    settings_btn.pack(side="left", padx=5)
    
    # STEP 3: BINDING - Register widgets for data updates
    if hasattr(self, 'widget_registry'):
        await self.widget_registry.register_widget("cpu_usage", self.cpu_bar)
        await self.widget_registry.register_widget("memory_usage", self.memory_bar)
        await self.widget_registry.register_widget("components_active", self.components_label)
        await self.widget_registry.register_widget("market_stats", self.market_stats)
        await self.widget_registry.register_widget("activity_list", self.activity_list)
        await self.widget_registry.register_widget("dashboard_status", self.dashboard_status)

async def update_dashboard_stats(self, data: Dict[str, Any]) -> None:
    """Update dashboard with real-time system and market data.
    
    Args:
        data: Dictionary containing dashboard statistic updates from the event bus
    """
    try:
        logger.info(f"Received dashboard data update: {data}")
        if not data or not isinstance(data, dict):
            logger.warning("Received invalid dashboard data")
            return
            
        # Update CPU usage if available
        if 'cpu_percent' in data and hasattr(self, 'cpu_bar'):
            cpu_usage = data.get('cpu_percent', 0)
            
            if self.using_pyqt:
                self.cpu_bar.setValue(int(cpu_usage))
            else:
                self.cpu_bar["value"] = cpu_usage
                
        # Update memory usage if available
        if 'memory_percent' in data and hasattr(self, 'memory_bar'):
            memory_usage = data.get('memory_percent', 0)
            
            if self.using_pyqt:
                self.memory_bar.setValue(int(memory_usage))
            else:
                self.memory_bar["value"] = memory_usage
                
        # Update active components if available
        if 'active_components' in data and 'total_components' in data and hasattr(self, 'components_label'):
            active = data.get('active_components', 0)
            total = data.get('total_components', 0)
            
            if self.using_pyqt:
                self.components_label.setText(f"{active}/{total}")
            else:
                self.components_label.config(text=f"{active}/{total}")
                
        # Update market stats if available
        if 'market_summary' in data and hasattr(self, 'market_stats'):
            market_summary = data.get('market_summary', 'No data available')
            
            if self.using_pyqt:
                self.market_stats.setText(market_summary)
            else:
                self.market_stats.config(text=market_summary)
                
        # Update activity list if available
        if 'recent_activities' in data and hasattr(self, 'activity_list'):
            activities = data.get('recent_activities', [])
            if activities:
                formatted_activities = '\n'.join(activities)
                
                if self.using_pyqt:
                    self.activity_list.setText(formatted_activities)
                else:
                    self.activity_list.config(text=formatted_activities)
                    
        # Update dashboard status if available
        if 'status' in data and hasattr(self, 'dashboard_status'):
            status = data.get('status', 'Unknown')
            
            if self.using_pyqt:
                self.dashboard_status.setText(f"Status: {status}")
                if status == "Online":
                    self.dashboard_status.setStyleSheet("color: green;")
                elif status == "Error":
                    self.dashboard_status.setStyleSheet("color: red;")
            else:
                self.dashboard_status.config(text=f"Status: {status}")
                if status == "Online":
                    self.dashboard_status.config(foreground="green")
                elif status == "Error":
                    self.dashboard_status.config(foreground="red")
                    
    except Exception as e:
        logger.error(f"Error updating dashboard: {e}")
