#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TradingStrategies component for managing and executing various trading strategies.
"""

import os
import asyncio
import logging
import json
import importlib
from datetime import datetime

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class TradingStrategies(BaseComponent):
    """
    Component for managing and executing various trading strategies.
    Handles strategy initialization, execution, and performance tracking.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the TradingStrategies component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "TradingStrategies"
        self.description = "Manages and executes trading strategies"
        
        # Initialize strategy containers
        self.strategies = {}  # Loaded strategy instances
        self.strategy_configs = {}  # Strategy configurations
        self.active_strategies = {}  # Currently running strategies
        self.strategy_performance = {}  # Performance metrics for strategies
        
        # Strategy execution settings
        self.execution_interval = self.config.get("execution_interval", 60)  # In seconds
        self.max_concurrent_strategies = self.config.get("max_concurrent_strategies", 10)
        
        # Strategy paths
        self.strategy_paths = self.config.get("strategy_paths", ["strategies"])
        
        # Strategy execution task
        self.execution_task = None
        
    async def safe_publish(self, event_name, event_data=None):
        """Safely publish an event to the event bus with error handling.
        
        Args:
            event_name: The name of the event to publish
            event_data: The data to include with the event
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.event_bus is None:
            logger.warning(f"Cannot publish event {event_name}: Event bus is None")
            return False
            
        try:
            await self.event_bus.publish(event_name, event_data)
            return True
        except Exception as e:
            logger.error(f"Error publishing event {event_name}: {str(e)}")
            return False
    
    async def initialize(self):
        """Initialize the TradingStrategies component.
        
        Returns:
            bool: True if initialization was successful
        """
        logger.info("Initializing TradingStrategies component")
        
        # Subscribe to relevant events
        if self.event_bus is not None:
            self.event_bus and self.event_bus.subscribe_sync("market.data.update", self.on_market_data_update)
            self.event_bus and self.event_bus.subscribe_sync("strategy.activate", self.on_strategy_activate)
            self.event_bus and self.event_bus.subscribe_sync("strategy.deactivate", self.on_strategy_deactivate)
            self.event_bus and self.event_bus.subscribe_sync("strategy.backtest", self.on_strategy_backtest)
            self.event_bus and self.event_bus.subscribe_sync("strategy.params.update", self.on_strategy_params_update)
            self.event_bus and self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
            # KAIG Intelligence Bridge — THREE TARGETS + rebrand resilience
            self.event_bus and self.event_bus.subscribe_sync("kaig.intel.trading.directive", self._on_kaig_directive)
            self.event_bus and self.event_bus.subscribe_sync("kaig.identity.changed", self._on_identity_changed)
        else:
            logger.warning("No event bus available, TradingStrategies will operate with limited functionality")
        
        # KAIG directive storage — all strategies must know the 3 targets
        self._kaig_directive = {}
        
        # Load available strategies
        await self.load_strategies()
        
        # Load strategy configurations
        await self.load_strategy_configs()
        
        # Start strategy execution task if configured to auto-start
        if self.config.get("auto_start", True):
            await self.start_execution_task()
        
        logger.info(f"TradingStrategies initialized with {len(self.strategies)} strategies")
        return True
        
    async def load_strategies(self):
        """Load available trading strategies from strategy paths."""
        for path in self.strategy_paths:
            full_path = os.path.join(os.path.dirname(__file__), "..", path)
            if not os.path.exists(full_path):
                logger.warning(f"Strategy path {full_path} does not exist")
                continue
                
            logger.info(f"Loading strategies from {full_path}")
            
            # Get all Python files in the directory
            for filename in os.listdir(full_path):
                if filename.endswith(".py") and not filename.startswith("_"):
                    module_name = filename[:-3]  # Remove .py extension
                    module_path = f"{path}.{module_name}"
                    
                    try:
                        # Import the module
                        module = importlib.import_module(module_path)
                        
                        # Look for Strategy classes
                        for attr_name in dir(module):
                            if attr_name.endswith("Strategy") and not attr_name.startswith("Base"):
                                strategy_class = getattr(module, attr_name)
                                
                                # Check if it has the required methods
                                if (hasattr(strategy_class, "execute") and 
                                    hasattr(strategy_class, "validate")):
                                    
                                    # Create an instance of the strategy
                                    strategy_instance = strategy_class(self.event_bus)
                                    strategy_id = f"{module_name}.{attr_name}"
                                    
                                    # Register the strategy
                                    self.strategies[strategy_id] = strategy_instance
                                    logger.info(f"Loaded strategy: {strategy_id}")
                        
                    except Exception as e:
                        logger.error(f"Error loading strategy module {module_path}: {str(e)}")
        
        # Publish available strategies
        await self.safe_publish("strategies.available", {
            "strategies": [
                {
                    "id": strategy_id,
                    "name": strategy.name if hasattr(strategy, "name") else strategy_id,
                    "description": strategy.description if hasattr(strategy, "description") else "",
                    "parameters": strategy.parameters if hasattr(strategy, "parameters") else {},
                    "markets": strategy.supported_markets if hasattr(strategy, "supported_markets") else ["all"]
                }
                for strategy_id, strategy in self.strategies.items()
            ]
        })
    
    async def load_strategy_configs(self):
        """Load strategy configurations from storage."""
        config_file = os.path.join(self.config.get("data_dir", "data"), "strategy_configs.json")
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    self.strategy_configs = json.load(f)
                logger.info(f"Loaded {len(self.strategy_configs)} strategy configurations")
                
                # Activate strategies that should be auto-activated
                for strategy_id, config in self.strategy_configs.items():
                    if config.get("auto_activate", False) and strategy_id in self.strategies:
                        await self.activate_strategy(strategy_id, config.get("parameters", {}))
        except Exception as e:
            logger.error(f"Error loading strategy configurations: {str(e)}")
    
    async def save_strategy_configs(self):
        """Save strategy configurations to storage."""
        config_file = os.path.join(self.config.get("data_dir", "data"), "strategy_configs.json")
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            
            with open(config_file, 'w') as f:
                json.dump(self.strategy_configs, f, indent=2)
            
            logger.info(f"Saved {len(self.strategy_configs)} strategy configurations")
        except Exception as e:
            logger.error(f"Error saving strategy configurations: {str(e)}")
    
    async def start_execution_task(self):
        """Start the strategy execution task."""
        if self.execution_task is None or self.execution_task.done():
            self.execution_task = asyncio.create_task(self.execute_strategies_loop())
            logger.info("Started strategy execution task")
    
    async def stop_execution_task(self):
        """Stop the strategy execution task."""
        if self.execution_task and not self.execution_task.done():
            self.execution_task.cancel()
            try:
                await self.execution_task
            except asyncio.CancelledError:
                pass
            self.execution_task = None
            logger.info("Stopped strategy execution task")
    
    async def execute_strategies_loop(self):
        """Continuously execute active strategies at the specified interval."""
        try:
            while True:
                await self.execute_active_strategies()
                await asyncio.sleep(self.execution_interval)
        except asyncio.CancelledError:
            logger.info("Strategy execution loop cancelled")
        except Exception as e:
            logger.error(f"Error in strategy execution loop: {str(e)}")
            # Restart the execution task
            self.execution_task = None
            await self.start_execution_task()
    
    async def execute_active_strategies(self):
        """Execute all active strategies."""
        for strategy_id, strategy_info in list(self.active_strategies.items()):
            try:
                # Skip if market data is not available
                if not strategy_info.get("market_data"):
                    continue
                
                # Get the strategy instance
                strategy = self.strategies.get(strategy_id)
                if not strategy:
                    logger.warning(f"Strategy {strategy_id} not found, removing from active strategies")
                    self.active_strategies.pop(strategy_id, None)
                    continue
                
                # Execute the strategy
                logger.debug(f"Executing strategy {strategy_id}")
                result = await strategy.execute(
                    strategy_info.get("market_data", {}),
                    strategy_info.get("parameters", {})
                )
                
                # Update execution time
                self.active_strategies[strategy_id]["last_execution"] = datetime.now().isoformat()
                
                # Process the result
                if result:
                    # Update performance metrics
                    await self.update_strategy_performance(strategy_id, result)
                    
                    # Publish strategy signals
                    if "signals" in result:
                        await self.safe_publish("strategy.signals", {
                            "strategy_id": strategy_id,
                            "signals": result["signals"],
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Publish strategy orders
                    if "orders" in result:
                        await self.safe_publish("strategy.orders", {
                            "strategy_id": strategy_id,
                            "orders": result["orders"],
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Log any errors or warnings
                    if "errors" in result:
                        for error in result["errors"]:
                            logger.error(f"Strategy {strategy_id} error: {error}")
                    
                    if "warnings" in result:
                        for warning in result["warnings"]:
                            logger.warning(f"Strategy {strategy_id} warning: {warning}")
                    
                    # Update strategy status
                    self.active_strategies[strategy_id]["status"] = result.get("status", "executed")
                    
            except Exception as e:
                logger.error(f"Error executing strategy {strategy_id}: {str(e)}")
                self.active_strategies[strategy_id]["status"] = "error"
                self.active_strategies[strategy_id]["error"] = str(e)
                
                # Publish error event
                await self.safe_publish("strategy.error", {
                    "strategy_id": strategy_id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
    
    async def activate_strategy(self, strategy_id, parameters=None):
        """
        Activate a trading strategy.
        
        Args:
            strategy_id: ID of the strategy to activate
            parameters: Strategy parameters
            
        Returns:
            bool: True if strategy was activated, False otherwise
        """
        if strategy_id not in self.strategies:
            logger.error(f"Strategy {strategy_id} not found")
            return False
        
        if len(self.active_strategies) >= self.max_concurrent_strategies:
            logger.error(f"Maximum number of concurrent strategies ({self.max_concurrent_strategies}) reached")
            return False
        
        # Get strategy parameters
        strategy_parameters = parameters or {}
        if not parameters and strategy_id in self.strategy_configs:
            strategy_parameters = self.strategy_configs[strategy_id].get("parameters", {})
        
        # Activate the strategy
        self.active_strategies[strategy_id] = {
            "activated_at": datetime.now().isoformat(),
            "parameters": strategy_parameters,
            "market_data": None,  # Will be populated by market data updates
            "status": "active",
            "last_execution": None
        }
        
        # Update strategy config
        self.strategy_configs[strategy_id] = {
            "parameters": strategy_parameters,
            "auto_activate": True,
            "last_active": datetime.now().isoformat()
        }
        
        # Save strategy configs
        await self.save_strategy_configs()
        
        logger.info(f"Activated strategy {strategy_id}")
        
        # Publish activation event
        await self.safe_publish("strategy.activated", {
            "strategy_id": strategy_id,
            "parameters": strategy_parameters,
            "timestamp": datetime.now().isoformat()
        })
        
        return True
    
    async def deactivate_strategy(self, strategy_id):
        """
        Deactivate a trading strategy.
        
        Args:
            strategy_id: ID of the strategy to deactivate
            
        Returns:
            bool: True if strategy was deactivated, False otherwise
        """
        if strategy_id not in self.active_strategies:
            logger.warning(f"Strategy {strategy_id} is not active")
            return False
        
        # Deactivate the strategy
        strategy_info = self.active_strategies.pop(strategy_id)
        
        # Update strategy config
        if strategy_id in self.strategy_configs:
            self.strategy_configs[strategy_id]["auto_activate"] = False
            self.strategy_configs[strategy_id]["last_active"] = strategy_info.get("last_execution", 
                                                                 strategy_info.get("activated_at"))
            
        # Save strategy configs
        await self.save_strategy_configs()
        
        logger.info(f"Deactivated strategy {strategy_id}")
        
        # Publish deactivation event
        await self.safe_publish("strategy.deactivated", {
            "strategy_id": strategy_id,
            "timestamp": datetime.now().isoformat()
        })
        
        return True
    
    async def update_strategy_parameters(self, strategy_id, parameters):
        """
        Update parameters for a strategy.
        
        Args:
            strategy_id: ID of the strategy to update
            parameters: New strategy parameters
            
        Returns:
            bool: True if parameters were updated, False otherwise
        """
        if strategy_id not in self.strategies:
            logger.error(f"Strategy {strategy_id} not found")
            return False
        
        # Update strategy config
        if strategy_id not in self.strategy_configs:
            self.strategy_configs[strategy_id] = {
                "parameters": parameters,
                "auto_activate": False,
                "last_updated": datetime.now().isoformat()
            }
        else:
            self.strategy_configs[strategy_id]["parameters"] = parameters
            self.strategy_configs[strategy_id]["last_updated"] = datetime.now().isoformat()
        
        # Update active strategy parameters if it's active
        if strategy_id in self.active_strategies:
            self.active_strategies[strategy_id]["parameters"] = parameters
        
        # Save strategy configs
        await self.save_strategy_configs()
        
        logger.info(f"Updated parameters for strategy {strategy_id}")
        
        # Publish parameter update event
        await self.safe_publish("strategy.parameters.updated", {
            "strategy_id": strategy_id,
            "parameters": parameters,
            "timestamp": datetime.now().isoformat()
        })
        
        return True
    
    async def update_strategy_performance(self, strategy_id, result):
        """
        Update performance metrics for a strategy.
        
        Args:
            strategy_id: ID of the strategy
            result: Execution result including performance metrics
        """
        if "performance" not in result:
            return
            
        performance = result["performance"]
        
        if strategy_id not in self.strategy_performance:
            self.strategy_performance[strategy_id] = {
                "executions": 0,
                "successful_trades": 0,
                "failed_trades": 0,
                "total_profit_loss": 0,
                "win_rate": 0,
                "average_return": 0,
                "max_drawdown": 0,
                "last_updated": None
            }
        
        # Update performance metrics
        perf = self.strategy_performance[strategy_id]
        perf["executions"] += 1
        
        if "trades" in performance:
            successful_trades = sum(1 for trade in performance["trades"] if trade.get("successful", False))
            failed_trades = len(performance["trades"]) - successful_trades
            
            perf["successful_trades"] += successful_trades
            perf["failed_trades"] += failed_trades
            
        if "profit_loss" in performance:
            perf["total_profit_loss"] += performance["profit_loss"]
            
        if perf["executions"] > 0:
            total_trades = perf["successful_trades"] + perf["failed_trades"]
            if total_trades > 0:
                perf["win_rate"] = perf["successful_trades"] / total_trades
            
            perf["average_return"] = perf["total_profit_loss"] / perf["executions"]
            
        if "max_drawdown" in performance:
            perf["max_drawdown"] = max(perf["max_drawdown"], performance["max_drawdown"])
            
        perf["last_updated"] = datetime.now().isoformat()
        
        # Publish performance update
        await self.safe_publish("strategy.performance.updated", {
            "strategy_id": strategy_id,
            "performance": perf,
            "timestamp": datetime.now().isoformat()
        })
    
    async def backtest_strategy(self, strategy_id, parameters, historical_data):
        """
        Backtest a trading strategy using historical data.
        
        Args:
            strategy_id: ID of the strategy to backtest
            parameters: Strategy parameters for backtesting
            historical_data: Historical market data for backtesting
            
        Returns:
            dict: Backtest results
        """
        if strategy_id not in self.strategies:
            msg = f"Strategy {strategy_id} not found"
            logger.error(msg)
            return {"success": False, "error": msg}
        
        try:
            strategy = self.strategies[strategy_id]
            
            # Check if strategy supports backtesting
            if not hasattr(strategy, "backtest"):
                msg = f"Strategy {strategy_id} does not support backtesting"
                logger.error(msg)
                return {"success": False, "error": msg}
            
            # Run the backtest
            logger.info(f"Running backtest for strategy {strategy_id}")
            backtest_result = await strategy.backtest(historical_data, parameters)
            
            # Process and return the result
            result = {
                "success": True,
                "strategy_id": strategy_id,
                "parameters": parameters,
                "results": backtest_result,
                "timestamp": datetime.now().isoformat()
            }
            
            # Publish backtest result
            self.event_bus.publish("strategy.backtest.completed", result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error backtesting strategy {strategy_id}: {str(e)}")
            return {
                "success": False,
                "strategy_id": strategy_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def on_market_data_update(self, data):
        """
        Handle market data update event.
        
        Args:
            data: Market data update
        """
        market = data.get("market")
        if not market:
            return
            
        # Update market data for active strategies that support this market
        for strategy_id, strategy_info in self.active_strategies.items():
            strategy = self.strategies.get(strategy_id)
            
            # Check if strategy supports this market
            if (strategy is not None and hasattr(strategy, "supported_markets") and 
                (market in strategy.supported_markets or "all" in strategy.supported_markets)):
                
                # Update market data
                if "market_data" not in strategy_info:
                    self.active_strategies[strategy_id]["market_data"] = {}
                    
                self.active_strategies[strategy_id]["market_data"][market] = data
    
    async def on_strategy_activate(self, data):
        """
        Handle strategy activation event.
        
        Args:
            data: Activation data
        """
        strategy_id = data.get("strategy_id")
        parameters = data.get("parameters")
        
        if not strategy_id:
            logger.warning("Strategy activation request missing strategy_id")
            return
            
        success = await self.activate_strategy(strategy_id, parameters)
        
        # Publish response
        await self.safe_publish("strategy.activate.result", {
            "request_id": data.get("request_id"),
            "strategy_id": strategy_id,
            "success": success,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_strategy_deactivate(self, data):
        """
        Handle strategy deactivation event.
        
        Args:
            data: Deactivation data
        """
        strategy_id = data.get("strategy_id")
        
        if not strategy_id:
            logger.warning("Strategy deactivation request missing strategy_id")
            return
            
        success = await self.deactivate_strategy(strategy_id)
        
        # Publish response
        await self.safe_publish("strategy.deactivate.result", {
            "request_id": data.get("request_id"),
            "strategy_id": strategy_id,
            "success": success,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_strategy_backtest(self, data):
        """
        Handle strategy backtest event.
        
        Args:
            data: Backtest data
        """
        strategy_id = data.get("strategy_id")
        parameters = data.get("parameters")
        historical_data = data.get("historical_data")
        
        if not strategy_id:
            logger.warning("Strategy backtest request missing strategy_id")
            return
            
        if not historical_data:
            logger.warning("Strategy backtest request missing historical_data")
            return
            
        result = await self.backtest_strategy(strategy_id, parameters, historical_data)
        
        # Publish response
        await self.safe_publish("strategy.backtest.result", {
            "request_id": data.get("request_id"),
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_strategy_params_update(self, data):
        """
        Handle strategy parameter update event.
        
        Args:
            data: Parameter update data
        """
        strategy_id = data.get("strategy_id")
        parameters = data.get("parameters")
        
        if not strategy_id:
            logger.warning("Strategy parameter update request missing strategy_id")
            return
            
        if not parameters:
            logger.warning("Strategy parameter update request missing parameters")
            return
            
        success = await self.update_strategy_parameters(strategy_id, parameters)
        
        # Publish response
        await self.safe_publish("strategy.params.update.result", {
            "request_id": data.get("request_id"),
            "strategy_id": strategy_id,
            "success": success,
            "parameters": parameters,
            "timestamp": datetime.now().isoformat()
        })
    
    def _on_kaig_directive(self, event_data):
        """Receive KAIG directive — 3 targets all strategies must know.
        
        1. SURVIVAL FLOOR: $26K realized → $13K treasury (existential, FIRST)
        2. KAIG PRICE FLOOR: 1 KAIG > highest crypto ATH ever (live-monitored)
        3. ULTIMATE TARGET: $2T (aspirational, always pursue)
        """
        if isinstance(event_data, dict):
            self._kaig_directive = event_data
            floor = event_data.get('kaig_survival_floor', {})
            survival_met = floor.get('survival_met', False)
            if not survival_met:
                logger.info("KAIG → TradingStrategies: SURVIVAL NOT MET — all strategies must maximize realized gains")

    def _on_identity_changed(self, event_data):
        """Handle token rebrand — all strategy profits and balances preserved.
        Tracked by wallet address, not token name. Zero loss. Users do nothing."""
        if isinstance(event_data, dict):
            logger.warning(
                "TradingStrategies: TOKEN REBRANDED %s → %s. All strategy profits preserved.",
                event_data.get("old_ticker", "?"),
                event_data.get("new_ticker", "?"))

    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the TradingStrategies component."""
        logger.info("Shutting down TradingStrategies component")
        
        # Stop execution task
        await self.stop_execution_task()
        
        # Save strategy configurations
        await self.save_strategy_configs()
        
        # Deactivate all strategies
        for strategy_id in list(self.active_strategies.keys()):
            await self.deactivate_strategy(strategy_id)
        
        logger.info("TradingStrategies component shut down successfully")
