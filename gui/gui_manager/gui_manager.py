#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Manager Module for Kingdom AI.

This module provides graphical user interface management capabilities
for the Kingdom AI system, handling all UI components and interactions.
"""

import asyncio
import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Optional, Union, Callable, cast

from core.event_bus import EventBus
from utils.thoth import Thoth
from performance_manager import PerformanceManager
from trading_hub import TradingHub
from portfolio_manager import PortfolioManager
from risk_manager import RiskManager

# Setup logging
logger = logging.getLogger(__name__)

class GUIManager:
    """
    GUI Manager for the Kingdom AI system.

    Handles all graphical user interface components, windows, and user interactions
    for the Kingdom AI system.
    """
    
    # Singleton instance
    _instance = None
    
    @classmethod
    def get_instance(cls, config: Optional[Dict[str, Any]] = None, event_bus: Optional[EventBus] = None, **kwargs):
        """
        Get the singleton instance of the GUIManager class.
        
        Args:
            config: Configuration dictionary
            event_bus: Event bus instance
            **kwargs: Additional keyword arguments
            
        Returns:
            The GUIManager singleton instance
        """
        if cls._instance is None:
            cls._instance = cls(config=config, event_bus=event_bus, **kwargs)
            logger.info("Created new GUIManager singleton instance")
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None, event_bus: Optional[EventBus] = None):
        """
        Initialize the GUI Manager component.

        Args:
            config: GUI manager configuration settings
            event_bus: Event bus for component communication
        """
        # Setup component configuration
        self.config = config or {}
        self.event_bus = event_bus if event_bus is not None else EventBus()

        # Initialize components
        self.thoth = Thoth(self.event_bus, self.config.get("thoth", {}))
        self.performance_manager = PerformanceManager(self.event_bus, cast(Optional[Thoth], self.thoth))
        self.trading_hub = TradingHub(self.event_bus, self.config.get("trading", {}))
        self.portfolio_manager = PortfolioManager(self.event_bus, cast(Optional[Thoth], self.thoth))
        self.risk_manager = RiskManager(self.event_bus, cast(Optional[Thoth], self.thoth))

        # Internal state
        self.is_initialized = False
        self.lock = threading.RLock()
        self.root = None
        self.frames: Dict[str, Any] = {}
        self.active_frame = None

        # Component states
        self._component_states = {
            "thoth": False,
            "performance": False,
            "trading": False,
            "portfolio": False,
            "risk": False
        }

        logger.info("GUIManager instance created")

    def start_event_loop(self):
        """
        Start the Tkinter mainloop on the root window in a thread-safe way.
        This should be called once, after all initialization is complete.
        """
        if not self.root:
            logger.error("Cannot start mainloop: root window is not initialized.")
            return
        if hasattr(self, '_mainloop_started') and self._mainloop_started:
            logger.warning("Tkinter mainloop has already been started.")
            return
        self._mainloop_started = True
        def run_loop():
            try:
                logger.info("Starting Tkinter mainloop...")
                if self.root is not None:
                    self.root.mainloop()
                else:
                    logger.error("Cannot start mainloop: self.root is None (window not initialized)")
            except Exception as e:
                logger.error(f"Error in Tkinter mainloop: {e}")
        # Start mainloop in a separate thread to avoid blocking asyncio
        threading.Thread(target=run_loop, daemon=True).start()

    async def initialize(self) -> bool:
        """
        Initialize the GUI Manager component.

        Returns:
            bool: True if initialization was successful
        """
        logger.info("Initializing GUI Manager...")
        
        with self.lock:
            # Avoid re-initialization if already initialized
            if self.is_initialized:
                logger.debug("GUI Manager already initialized")
                return True
            
            try:
                # Initialize event bus if it has an initialize method
                if hasattr(self.event_bus, 'initialize'):
                    await self.event_bus.initialize()
                    
                # Initialize Thoth
                if await self.thoth.initialize():
                    self._component_states["thoth"] = True
                    
                # Initialize PerformanceManager
                if await self.performance_manager.initialize():
                    self._component_states["performance"] = True
                    
                # Initialize TradingHub
                if await self.trading_hub.initialize():
                    self._component_states["trading"] = True
                    
                # Initialize PortfolioManager
                if await self.portfolio_manager.initialize():
                    self._component_states["portfolio"] = True
                    
                # Initialize RiskManager
                if await self.risk_manager.initialize():
                    self._component_states["risk"] = True
                    
                # Create root window if we're in the main thread
                try:
                    self.root = tk.Tk()
                    self.root.title("Kingdom AI - Quantum Nexus")
                    self.root.geometry("1200x800")
                    self.root.withdraw()  # Hide window initially
                    
                    # Configure style
                    style = ttk.Style()
                    style.theme_use('clam')
                    
                    logger.debug("Tkinter root window created")
                except Exception as e:
                    logger.error(f"Failed to create Tkinter root window: {e}")
                    return False
                
                # Register GUI events
                self.event_bus.subscribe_sync('system.gui.show', self.show_window)
                self.event_bus.subscribe_sync('system.gui.hide', self.hide_window)
                self.event_bus.subscribe_sync('system.gui.update', self.update_display)
                # Register component events with correct callback signatures
                self.event_bus.subscribe_sync('thoth.analysis', self._handle_thoth_analysis)
                self.event_bus.subscribe_sync('performance.update', self._handle_performance_update)
                self.event_bus.subscribe_sync('trading.update', self._handle_trading_update)
                self.event_bus.subscribe_sync('portfolio.update', self._handle_portfolio_update)
                self.event_bus.subscribe_sync('risk.update', self._handle_risk_update)
                
                # Set initialized flag if all critical components are ready
                self.is_initialized = all(self._component_states.values())
                
                if self.is_initialized:
                    logger.info("GUI Manager initialized successfully")
                    return True
                else:
                    failed_components = [
                        comp for comp, state in self._component_states.items() 
                        if not state
                    ]
                    logger.error(f"Failed to initialize components: {failed_components}")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to initialize GUI Manager: {e}")
                return False
                
    async def _handle_thoth_analysis(self, event: str, data: Dict[str, Any]) -> None:
        """Handle Thoth analysis updates."""
        if not self.is_initialized:
            return
            
        try:
            # Update relevant GUI components with analysis results
            await self.update_display({
                "type": "thoth_analysis",
                "data": data
            })
        except Exception as e:
            logger.error(f"Error handling Thoth analysis: {e}")
            
    async def _handle_performance_update(self, event: str, data: Dict[str, Any]) -> None:
        """Handle performance metric updates."""
        if not self.is_initialized:
            return
            
        try:
            # Update performance displays
            await self.update_display({
                "type": "performance_update",
                "data": data
            })
        except Exception as e:
            logger.error(f"Error handling performance update: {e}")
            
    async def _handle_trading_update(self, event: str, data: Dict[str, Any]) -> None:
        """Handle trading updates."""
        if not self.is_initialized:
            return
            
        try:
            # Update trading displays
            await self.update_display({
                "type": "trading_update",
                "data": data
            })
        except Exception as e:
            logger.error(f"Error handling trading update: {e}")
            
    async def _handle_portfolio_update(self, event: str, data: Dict[str, Any]) -> None:
        """Handle portfolio updates."""
        if not self.is_initialized:
            return
            
        try:
            # Update portfolio displays
            await self.update_display({
                "type": "portfolio_update",
                "data": data
            })
        except Exception as e:
            logger.error(f"Error handling portfolio update: {e}")
            
    async def _handle_risk_update(self, event: str, data: Dict[str, Any]) -> None:
        """Handle risk updates."""
        if not self.is_initialized:
            return
            
        try:
            # Update risk displays
            await self.update_display({
                "type": "risk_update",
                "data": data
            })
        except Exception as e:
            logger.error(f"Error handling risk update: {e}")
            
    async def show_window(self, window_name: str = "main") -> bool:
        """Show a specific window."""
        logger.info(f"Show window request received: {window_name}")
        
        if not self.is_initialized or self.root is None:
            logger.error("GUI Manager not initialized")
            return False
            
        try:
            if window_name == "main":
                self.root.deiconify()
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error showing window: {e}")
            return False
            
    async def hide_window(self, window_name: str = "main") -> bool:
        """Hide a specific window."""
        logger.info(f"Hide window request received: {window_name}")
        
        if not self.is_initialized or self.root is None:
            logger.error("GUI Manager not initialized")
            return False
            
        try:
            if window_name == "main":
                self.root.withdraw()
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error hiding window: {e}")
            return False
            
    async def update_display(self, data: Dict[str, Any]) -> bool:
        """Update the display with new data."""
        if not self.is_initialized or self.root is None:
            logger.error("GUI Manager not initialized")
            return False
            
        try:
            update_type = data.get("type", "")
            update_data = data.get("data", {})
            
            if update_type == "thoth_analysis":
                await self._update_thoth_display(update_data)
            elif update_type == "performance_update":
                await self._update_performance_display(update_data)
            elif update_type == "trading_update":
                await self._update_trading_display(update_data)
            elif update_type == "portfolio_update":
                await self._update_portfolio_display(update_data)
            elif update_type == "risk_update":
                await self._update_risk_display(update_data)
                
            return True
            
        except Exception as e:
            logger.error(f"Error updating display: {e}")
            return False
            
    async def _update_thoth_display(self, data: Dict[str, Any]) -> None:
        """Update Thoth analysis display."""
        if "thoth_frame" not in self.frames:
            return
            
        # Update Thoth analysis widgets
        frame = self.frames["thoth_frame"]
        # Update widgets with data...
        
    async def _update_performance_display(self, data: Dict[str, Any]) -> None:
        """Update performance metrics display."""
        if "performance_frame" not in self.frames:
            return
            
        # Update performance widgets
        frame = self.frames["performance_frame"]
        # Update widgets with data...
        
    async def _update_trading_display(self, data: Dict[str, Any]) -> None:
        """Update trading display."""
        if "trading_frame" not in self.frames:
            return
            
        # Update trading widgets
        frame = self.frames["trading_frame"]
        # Update widgets with data...
        
    async def _update_portfolio_display(self, data: Dict[str, Any]) -> None:
        """Update portfolio display."""
        if "portfolio_frame" not in self.frames:
            return
            
        # Update portfolio widgets
        frame = self.frames["portfolio_frame"]
        # Update widgets with data...
        
    async def _update_risk_display(self, data: Dict[str, Any]) -> None:
        """Update risk metrics display."""
        if "risk_frame" not in self.frames:
            return
            
        # Update risk widgets
        frame = self.frames["risk_frame"]
        # Update widgets with data...
        
    def create_loading_screen(self) -> Any:
        """Create and return a loading screen frame."""
        logger.info("Creating loading screen")
        
        if not self.is_initialized or self.root is None:
            logger.error("GUI Manager not initialized")
            return None
            
        try:
            # Create loading screen frame
            frame = ttk.Frame(self.root)
            
            # Add Kingdom AI logo/title
            title = ttk.Label(
                frame,
                text="Kingdom AI",
                font=("Helvetica", 24, "bold")
            )
            title.pack(pady=20)
            
            # Add loading message
            message = ttk.Label(
                frame,
                text="Initializing System Components...",
                font=("Helvetica", 12)
            )
            message.pack(pady=10)
            
            # Add progress bar
            progress = ttk.Progressbar(
                frame,
                mode='indeterminate',
                length=300
            )
            progress.pack(pady=20)
            progress.start()
            
            # Add component status indicators
            status_frame = ttk.Frame(frame)
            status_frame.pack(pady=20)
            
            for component in self._component_states:
                label = ttk.Label(
                    status_frame,
                    text=f"{component.title()}: Initializing...",
                    font=("Helvetica", 10)
                )
                label.pack(pady=5)
                
            # Store frame
            self.frames['loading'] = frame
            
            return frame
            
        except Exception as e:
            logger.error(f"Error creating loading screen: {e}")
            return None
            
    async def show_loading_screen(self) -> bool:
        """Show the loading screen."""
        logger.info("Showing loading screen")
        
        if not self.is_initialized or self.root is None:
            logger.error("GUI Manager not initialized")
            return False
            
        try:
            # Create loading screen if it doesn't exist
            if 'loading' not in self.frames:
                self.create_loading_screen()
                
            # Show loading screen
            if 'loading' in self.frames:
                if self.active_frame:
                    self.active_frame.pack_forget()
                    
                self.frames['loading'].pack(expand=True, fill=tk.BOTH)
                self.active_frame = self.frames['loading']
                self.root.deiconify()
                
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error showing loading screen: {e}")
            return False
            
    async def hide_loading_screen(self) -> bool:
        """Hide the loading screen."""
        logger.info("Hiding loading screen")
        
        if not self.is_initialized or self.root is None:
            logger.error("GUI Manager not initialized")
            return False
            
        try:
            if 'loading' in self.frames:
                self.frames['loading'].pack_forget()
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error hiding loading screen: {e}")
            return False
