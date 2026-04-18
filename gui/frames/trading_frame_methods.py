import asyncio
import logging
import tkinter as tk
from tkinter import ttk
from datetime import datetime

class TradingFrameMethods:
    """
    Core methods to be integrated into TradingFrame.
    Includes Redis connection handling, UI setup, and event handlers.
    """
    
    async def _disable_trading_on_redis_failure(self, error_message):
        """
        Disable all trading UI elements when Redis connection fails.
        This enforces the mandatory Redis connectivity requirement.
        
        Args:
            error_message: The error message to display
        """
        self.logger.error(f"Disabling trading due to Redis failure: {error_message}")
        self.redis_connected = False
        
        # Update Redis status display
        self.redis_status_var.set(f"Redis error: {str(error_message)[:50]}...")
        
        # Disable UI elements if they exist
        for widget_name in ['start_button', 'pause_button', 'stop_button', 'auto_trading_toggle']:
            if hasattr(self, widget_name) and getattr(self, widget_name):
                getattr(self, widget_name).configure(state=tk.DISABLED)
        
        # Update trading status
        self.trading_status_var.set("Trading disabled: No Redis connection")
        if hasattr(self, "trading_status_label"):
            self.trading_status_label.configure(foreground="red")
        
        # Publish system critical error event
        if hasattr(self, "safe_publish"):
            self.safe_publish("system.critical_error", {
                "source": "trading_frame",
                "component": "redis_quantum_nexus",
                "error": str(error_message),
                "message": "Mandatory Redis connection on port 6380 failed",
                "timestamp": datetime.now().timestamp()
            })
            
        # Log the critical error
        self.logger.critical(f"CRITICAL: Redis connection failure on port 6380: {error_message}")

    def _setup_profit_display(self):
        """
        Set up the profit goal display panel showing:
        - Profit goal ($2 trillion)
        - Current profit
        - Progress percentage
        - Progress bar
        """
        self.logger.debug("Setting up profit goal display panel")
        
        # Create profit frame
        profit_frame = ttk.LabelFrame(self.profit_frame_placeholder, text="Profit Goal Tracking")
        profit_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Goal and current profit display
        goal_frame = ttk.Frame(profit_frame)
        goal_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(goal_frame, text="Goal:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(goal_frame, textvariable=self.profit_goal_var, foreground="blue").grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=2
        )
        
        ttk.Label(goal_frame, text="Current:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.current_profit_label = ttk.Label(goal_frame, textvariable=self.current_profit_var, foreground="green")
        self.current_profit_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(goal_frame, text="Progress:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.profit_percentage_label = ttk.Label(goal_frame, textvariable=self.profit_percentage_var)
        self.profit_percentage_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Progress bar
        progress_frame = ttk.Frame(profit_frame)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.profit_progress = ttk.Progressbar(
            progress_frame, orient=tk.HORIZONTAL, length=200, mode='determinate'
        )
        self.profit_progress.pack(fill=tk.X, padx=5, pady=5)
        
        self.logger.debug("Profit goal display panel setup complete")

    def _setup_trading_controls(self):
        """
        Set up automated trading controls:
        - Auto-trading toggle
        - Start/Pause/Stop buttons
        - Trading status display
        """
        self.logger.debug("Setting up trading controls panel")
        
        # Create controls frame
        controls_frame = ttk.LabelFrame(self.controls_frame_placeholder, text="Trading Controls")
        controls_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Auto-trading toggle
        auto_frame = ttk.Frame(controls_frame)
        auto_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.auto_trading_toggle = ttk.Checkbutton(
            auto_frame, 
            text="Automated Trading", 
            variable=self.auto_trading_var,
            command=lambda: self._toggle_automated_trading() if self.redis_connected else None,
            state=tk.DISABLED  # Start disabled until Redis connection is confirmed
        )
        self.auto_trading_toggle.pack(side=tk.LEFT, padx=5)
        
        # Trading status display
        status_frame = ttk.Frame(controls_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.trading_status_label = ttk.Label(status_frame, textvariable=self.trading_status_var)
        self.trading_status_label.pack(side=tk.LEFT, padx=5)
        
        # Control buttons
        buttons_frame = ttk.Frame(controls_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(
            buttons_frame, 
            text="Start Trading", 
            command=lambda: self._start_trading() if self.redis_connected else None,
            state=tk.DISABLED  # Start disabled until Redis connection is confirmed
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = ttk.Button(
            buttons_frame, 
            text="Pause Trading", 
            command=lambda: self._pause_trading() if self.redis_connected else None,
            state=tk.DISABLED  # Start disabled until Redis connection is confirmed
        )
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            buttons_frame, 
            text="Stop Trading", 
            command=lambda: self._stop_trading() if self.redis_connected else None,
            state=tk.DISABLED  # Start disabled until Redis connection is confirmed
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.logger.debug("Trading controls panel setup complete")

    def _setup_thoth_controls(self):
        """
        Set up Thoth AI integration controls:
        - AI connection status
        - Insights text area
        - Market prediction label
        """
        self.logger.debug("Setting up Thoth AI controls panel")
        
        # Create Thoth frame
        thoth_frame = ttk.LabelFrame(self.thoth_frame_placeholder, text="Thoth AI Trading Assistant")
        thoth_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status display
        status_frame = ttk.Frame(thoth_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(status_frame, text="Thoth Status:").pack(side=tk.LEFT, padx=5)
        self.thoth_status_label = ttk.Label(status_frame, textvariable=self.thoth_status_var, foreground="orange")
        self.thoth_status_label.pack(side=tk.LEFT, padx=5)
        
        # Insights text area
        insights_frame = ttk.Frame(thoth_frame)
        insights_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Label(insights_frame, text="AI Insights:").pack(anchor=tk.W, padx=5)
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(insights_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.thoth_insights_text = tk.Text(text_frame, height=5, wrap=tk.WORD)
        self.thoth_insights_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame, command=self.thoth_insights_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.thoth_insights_text.config(yscrollcommand=scrollbar.set)
        
        # Prediction display
        prediction_frame = ttk.Frame(thoth_frame)
        prediction_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(prediction_frame, text="Market Prediction:").pack(anchor=tk.W, padx=5)
        self.market_prediction_var = tk.StringVar(value="No prediction available")
        self.market_prediction_label = ttk.Label(
            prediction_frame, 
            textvariable=self.market_prediction_var,
            wraplength=350
        )
        self.market_prediction_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # Insert default text
        self.thoth_insights_text.insert(tk.END, "Waiting for Thoth AI connection...\n")
        self.thoth_insights_text.config(state=tk.DISABLED)  # Make read-only initially
        
        self.logger.debug("Thoth AI controls panel setup complete")

    def _subscribe_to_events(self):
        """Subscribe to necessary events for trading and AI integration."""
        if not self._event_bus:
            self.logger.error("Cannot subscribe to events: No event bus available")
            return
            
        self.logger.debug("Subscribing to trading events")
        
        # Profit update events
        self._event_bus.subscribe("trading.profit.update", self._handle_profit_update)
        
        # Thoth AI event handling
        self._event_bus.subscribe("thoth.ai.command", self._handle_thoth_command)
        self._event_bus.subscribe("thoth.ai.insight", self._handle_thoth_insight)
        self._event_bus.subscribe("thoth.ai.market_prediction", self._handle_market_prediction)
        
        # Redis connection events
        self._event_bus.subscribe("redis.quantum_nexus.connection_lost", 
                                 lambda data: self._disable_trading_on_redis_failure("Connection lost"))
        
        self.logger.debug("Event subscriptions complete")
