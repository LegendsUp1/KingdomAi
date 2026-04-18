"""
Capital Efficiency Module for Kingdom AI Trading System
Implements universal cross-margin, portfolio margin, and capital optimization for perpetual futures trading.
"""

import asyncio
import json
import logging
import time
import pandas as pd

from core.base_component import BaseComponent
from utils.redis_client import RedisClient
from utils.async_utils import AsyncSupport

class CapitalEfficiencyModule(BaseComponent):
    """
    Advanced capital efficiency module that implements universal cross-margin,
    portfolio margin, and capital optimization for perpetual futures trading.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the Capital Efficiency Module."""
        super().__init__("CapitalEfficiencyModule", event_bus, config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.redis_client = None
        self.shutdown_event = asyncio.Event()
        self.async_support: "AsyncSupport | None" = None  # Will be set during initialization
        
        # Default configuration
        self.config = config or {
            "margin_tiers": [
                {"tier": 1, "notional_limit": 50000, "maintenance_margin_rate": 0.04, "initial_margin_rate": 0.05},
                {"tier": 2, "notional_limit": 250000, "maintenance_margin_rate": 0.05, "initial_margin_rate": 0.065},
                {"tier": 3, "notional_limit": 1000000, "maintenance_margin_rate": 0.06, "initial_margin_rate": 0.08},
                {"tier": 4, "notional_limit": 5000000, "maintenance_margin_rate": 0.075, "initial_margin_rate": 0.10},
                {"tier": 5, "notional_limit": float('inf'), "maintenance_margin_rate": 0.10, "initial_margin_rate": 0.125}
            ],
            "cross_margin_enabled": True,
            "portfolio_margin_enabled": True,
            "margin_optimization_interval_seconds": 60,
            "risk_based_leverage_adjustment": True,
            "collateral_assets": ["BTC", "ETH", "USDT", "USDC", "SOL"],
            "collateral_haircuts": {
                "BTC": 0.90,  # 90% of BTC value can be used as collateral
                "ETH": 0.90,
                "USDT": 1.0,
                "USDC": 1.0,
                "SOL": 0.85
            },
            "max_leverage": 20.0,
            "auto_collateral_management": True,
            "position_netting": True,  # Allow netting of long/short positions for same asset
            "margin_reserve_percent": 5.0,  # Reserve margin buffer
            "auto_deleveraging_threshold": 0.8,  # Trigger auto-deleveraging at 80% of max leverage
            "margin_call_threshold": 0.75  # Margin call at 75% of maintenance margin
        }
        
        # Internal state
        self.account_state = {
            "total_collateral_value": 0.0,
            "total_notional_value": 0.0,
            "effective_leverage": 0.0,
            "available_margin": 0.0,
            "used_margin": 0.0,
            "maintenance_margin": 0.0,
            "margin_ratio": 0.0,
            "collateral_assets": {},
            "open_positions": {},
            "portfolio_margin_benefit": 0.0,
            "account_tier": 1,
            "last_updated": None
        }
        
    async def initialize(self):
        """Initialize the Capital Efficiency Module and connect to Redis Quantum Nexus."""
        self.logger.info("Initializing Capital Efficiency Module")
        
        # Connect to Redis Quantum Nexus with strict enforcement (no fallback)
        try:
            self.redis_client = RedisClient(
                host="localhost",
                port=6380,  # Strict port requirement
                password="QuantumNexus2025",  # Required password
                db=0,
                decode_responses=True
            )
            
            # Test connection and halt if not successful
            ping_result = await self.redis_client.ping()
            if not ping_result:
                raise ConnectionError("Redis ping failed")
                
            self.logger.info("Successfully connected to Redis Quantum Nexus")
        except Exception as e:
            self.logger.critical(f"Failed to connect to Redis Quantum Nexus: {e}")
            # Enforcing strict no-fallback policy
            raise SystemExit("Critical failure: Redis Quantum Nexus connection failed. Halting system.")
        
        # Register event handlers
        if self.event_bus:
            self.event_bus.subscribe_sync("account_update", self.on_account_update)
            self.event_bus.subscribe_sync("collateral_update", self.on_collateral_update)
            self.event_bus.subscribe_sync("position_open_request", self.on_position_open_request)
            self.event_bus.subscribe_sync("position_update", self.on_position_update)
            self.event_bus.subscribe_sync("position_close", self.on_position_close)
            self.event_bus.subscribe_sync("leverage_change_request", self.on_leverage_change_request)
            self.event_bus.subscribe_sync("margin_transfer_request", self.on_margin_transfer_request)
            self.event_bus.subscribe_sync("system_shutdown", self.on_shutdown)
        
        # Start background tasks using asyncio directly
        asyncio.create_task(self._task_optimize_margin())
        asyncio.create_task(self._task_rebalance_collateral())
        asyncio.create_task(self._task_monitor_margin_health())
        
        self.logger.info("Capital Efficiency Module initialized successfully")
        return True
        
    # Background tasks
    
    async def _task_optimize_margin(self):
        """Background task to optimize margin usage across positions."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Running margin optimization task")
                
                try:
                    # Skip if no cross-margin enabled
                    if not self.config["cross_margin_enabled"]:
                        await asyncio.sleep(self.config["optimization_interval"])
                        continue
                        
                    # Find positions with excess margin
                    positions_with_excess = []
                    positions_with_deficit = []
                    
                    for pos_id, pos in self.account_state["open_positions"].items():
                        symbol = pos.get("symbol")
                        size = pos.get("size")
                        leverage = pos.get("leverage", 1.0)
                        
                        if not all([symbol, size, leverage]):
                            continue
                            
                        # Calculate minimum maintenance margin
                        maintenance_margin = await self._calculate_maintenance_margin(symbol, size, leverage)
                        
                        # Get current margin
                        current_margin = pos.get("required_margin", 0)
                        
                        # Calculate excess (with safety buffer)
                        safety_buffer = self.config["margin_safety_buffer"]
                        min_required = maintenance_margin * (1 + safety_buffer)
                        
                        excess = current_margin - min_required
                        
                        if excess > self.config["min_transferable_amount"]:
                            positions_with_excess.append({
                                "position_id": pos_id,
                                "excess": excess
                            })
                        elif excess < -self.config["min_transferable_amount"]:
                            positions_with_deficit.append({
                                "position_id": pos_id,
                                "deficit": -excess
                            })
                    
                    # If we have both excess and deficit positions, initiate transfers
                    if positions_with_excess and positions_with_deficit:
                        for deficit_pos in positions_with_deficit:
                            deficit = deficit_pos["deficit"]
                            to_pos_id = deficit_pos["position_id"]
                            
                            # Find positions with excess to cover this deficit
                            for excess_pos in positions_with_excess:
                                from_pos_id = excess_pos["position_id"]
                                excess = excess_pos["excess"]
                                
                                if excess <= 0:
                                    continue
                                    
                                # Calculate transfer amount
                                transfer_amount = min(excess, deficit)
                                
                                if transfer_amount >= self.config["min_transferable_amount"]:
                                    # Execute margin transfer
                                    if self.event_bus:
                                        self.event_bus.publish_sync("margin_transfer", {
                                            "from_position_id": from_pos_id,
                                            "to_position_id": to_pos_id,
                                            "amount": transfer_amount,
                                            "auto_optimized": True,
                                            "timestamp": time.time()
                                        })
                                        
                                        self.logger.info(
                                            f"Auto-optimized margin transfer: {transfer_amount} from position "
                                            f"{from_pos_id} to {to_pos_id}"
                                        )
                                        
                                        # Update local tracking
                                        excess_pos["excess"] -= transfer_amount
                                        deficit -= transfer_amount
                                        
                                        if deficit <= self.config["min_transferable_amount"]:
                                            break
                    
                    # Handle excess margin that could be returned to available balance
                    available_margin = self.account_state["available_margin"]
                    if available_margin < self.config["min_available_margin"]:
                        # Find positions with largest excess to free up margin
                        positions_with_excess.sort(key=lambda x: x["excess"], reverse=True)
                        
                        margin_needed = self.config["target_available_margin"] - available_margin
                        
                        for excess_pos in positions_with_excess:
                            if margin_needed <= 0:
                                break
                                
                            transfer_amount = min(excess_pos["excess"], margin_needed)
                            
                            if transfer_amount >= self.config["min_transferable_amount"]:
                                # Free up margin
                                if self.event_bus:
                                    self.event_bus.publish_sync("margin_release", {
                                        "position_id": excess_pos["position_id"],
                                        "amount": transfer_amount,
                                        "timestamp": time.time()
                                    })
                                    
                                    self.logger.info(
                                        f"Released {transfer_amount} margin from position {excess_pos['position_id']} "
                                        f"to available balance"
                                    )
                                    
                                    margin_needed -= transfer_amount
                
                except Exception as e:
                    self.logger.error(f"Error in margin optimization: {e}")
                
                # Wait for next optimization cycle
                await asyncio.sleep(self.config["optimization_interval"])
                
        except asyncio.CancelledError:
            self.logger.info("Margin optimization task cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in margin optimization task: {e}")
    
    async def _task_rebalance_collateral(self):
        """Background task to rebalance collateral assets for optimal capital efficiency."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Running collateral rebalancing task")
                
                try:
                    # Skip if less than 2 collateral assets
                    if len(self.account_state["collateral_assets"]) < 2:
                        await asyncio.sleep(self.config["rebalance_interval"])
                        continue
                    
                    # Get collateral value distribution
                    total_value = self.account_state["total_collateral_value"]
                    if total_value <= 0:
                        await asyncio.sleep(self.config["rebalance_interval"])
                        continue
                        
                    # Calculate current weights vs target weights
                    rebalance_actions = []
                    
                    for asset, asset_data in self.account_state["collateral_assets"].items():
                        current_weight = asset_data["value"] / total_value
                        target_weight = self.config["collateral_target_weights"].get(asset, 0.0)
                        
                        # Skip assets with no target weight
                        if target_weight <= 0:
                            continue
                            
                        # Calculate weight difference
                        weight_diff = target_weight - current_weight
                        
                        # If difference exceeds threshold, add rebalance action
                        if abs(weight_diff) >= self.config["rebalance_threshold"]:
                            target_value = total_value * target_weight
                            value_diff = target_value - asset_data["value"]
                            
                            rebalance_actions.append({
                                "asset": asset,
                                "current_value": asset_data["value"],
                                "target_value": target_value,
                                "value_diff": value_diff,
                                "weight_diff": weight_diff
                            })
                    
                    # If rebalance needed, notify
                    if rebalance_actions and self.event_bus:
                        self.event_bus.publish_sync("collateral_rebalance_needed", {
                            "actions": rebalance_actions,
                            "timestamp": time.time()
                        })
                        
                        # Log rebalance recommendation
                        self.logger.info(
                            f"Collateral rebalance needed: {len(rebalance_actions)} assets need adjustment"
                        )
                        
                except Exception as e:
                    self.logger.error(f"Error in collateral rebalancing: {e}")
                
                # Wait for next rebalance cycle
                await asyncio.sleep(self.config["rebalance_interval"])
                
        except asyncio.CancelledError:
            self.logger.info("Collateral rebalancing task cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in collateral rebalancing task: {e}")
    
    async def _task_monitor_margin_health(self):
        """Background task to monitor margin health and issue warnings/auto-deleveraging."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Running margin health monitoring task")
                
                try:
                    # Calculate current margin ratio
                    margin_ratio = self.account_state["margin_ratio"]
                    
                    # If ratio exists and is below warning threshold, issue warning
                    if margin_ratio != float('inf'):
                        if margin_ratio < self.config["margin_warning_threshold"]:
                            # Issue warning
                            if self.event_bus:
                                self.event_bus.publish_sync("margin_warning", {
                                    "margin_ratio": margin_ratio,
                                    "threshold": self.config["margin_warning_threshold"],
                                    "account_state": self.account_state,
                                    "timestamp": time.time()
                                })
                                
                                self.logger.warning(
                                    f"Low margin ratio warning: {margin_ratio:.4f} < "
                                    f"{self.config['margin_warning_threshold']:.4f}"
                                )
                        
                        # If ratio below auto-deleveraging threshold, take action
                        if margin_ratio < self.config["auto_deleverage_threshold"]:
                            # Identify highest leverage positions
                            positions = list(self.account_state["open_positions"].items())
                            positions.sort(key=lambda p: p[1].get("leverage", 0), reverse=True)
                            
                            if positions:
                                # Select highest leverage position for auto-deleveraging
                                pos_id, pos = positions[0]
                                current_leverage = pos.get("leverage", 1.0)
                                
                                if current_leverage > 1.0:
                                    # Calculate new lower leverage (reduce by configured factor)
                                    new_leverage = max(
                                        1.0, 
                                        current_leverage * (1 - self.config["deleverage_factor"])
                                    )
                                    
                                    # Issue auto-deleveraging request
                                    if self.event_bus:
                                        self.event_bus.publish_sync("auto_deleverage", {
                                            "position_id": pos_id,
                                            "current_leverage": current_leverage,
                                            "new_leverage": new_leverage,
                                            "reason": f"Auto-deleveraging due to low margin ratio: {margin_ratio:.4f}",
                                            "timestamp": time.time()
                                        })
                                        
                                        self.logger.warning(
                                            f"Auto-deleveraging position {pos_id} from {current_leverage}x to "
                                            f"{new_leverage}x due to low margin ratio: {margin_ratio:.4f}"
                                        )
                
                except Exception as e:
                    self.logger.error(f"Error in margin health monitoring: {e}")
                
                # Wait for next monitoring cycle
                await asyncio.sleep(self.config["monitoring_interval"])
                
        except asyncio.CancelledError:
            self.logger.info("Margin health monitoring task cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in margin health monitoring task: {e}")
        
    # Event handlers
    
    async def on_account_update(self, data):
        """Handle account updates and recalculate margin metrics."""
        try:
            # Extract account data
            account_value = data.get("account_value")
            if account_value is None:
                self.logger.warning("Received account update with missing value")
                return
                
            # Update collateral value if provided
            collateral_value = data.get("collateral_value")
            if collateral_value is not None:
                self.account_state["total_collateral_value"] = collateral_value
                
            # Update positions if provided
            positions = data.get("positions")
            if positions is not None:
                self.account_state["open_positions"] = positions
                
                # Calculate total notional value
                total_notional = sum(position.get("notional_value", 0) for position in positions.values())
                self.account_state["total_notional_value"] = total_notional
                
                # Calculate effective leverage
                if self.account_state["total_collateral_value"] > 0:
                    self.account_state["effective_leverage"] = (
                        self.account_state["total_notional_value"] / 
                        self.account_state["total_collateral_value"]
                    )
                else:
                    self.account_state["effective_leverage"] = 0.0
            
            # Recalculate margin values
            await self._recalculate_margin_values()
            
            # Update timestamp
            self.account_state["last_updated"] = time.time()
            
            # Store current state in Redis for monitoring
            await self.redis_client.set(
                "capital:account_state",
                json.dumps(self.account_state)
            )
            
        except Exception as e:
            self.logger.error(f"Error processing account update: {e}")
    
    async def on_collateral_update(self, data):
        """Handle collateral asset updates and recalculate available margin."""
        try:
            asset = data.get("asset")
            amount = data.get("amount")
            price = data.get("price")
            
            if not all([asset, amount is not None, price is not None]):
                self.logger.warning(f"Incomplete collateral update data: {data}")
                return
                
            # Update collateral asset information
            if asset not in self.account_state["collateral_assets"]:
                self.account_state["collateral_assets"][asset] = {
                    "amount": 0.0,
                    "value": 0.0,
                    "price": 0.0
                }
                
            # Update amount and value
            self.account_state["collateral_assets"][asset]["amount"] = amount
            self.account_state["collateral_assets"][asset]["price"] = price
            
            # Apply haircut based on asset type
            haircut = self.config["collateral_haircuts"].get(asset, 0.5)  # Default 50% haircut
            self.account_state["collateral_assets"][asset]["value"] = amount * price * haircut
            
            # Recalculate total collateral value
            total_collateral = sum(
                asset_data["value"] 
                for asset_data in self.account_state["collateral_assets"].values()
            )
            self.account_state["total_collateral_value"] = total_collateral
            
            # Recalculate margin values
            await self._recalculate_margin_values()
            
            # Update effective leverage
            if self.account_state["total_collateral_value"] > 0:
                self.account_state["effective_leverage"] = (
                    self.account_state["total_notional_value"] / 
                    self.account_state["total_collateral_value"]
                )
            
            # Store current state in Redis for monitoring
            await self.redis_client.set(
                "capital:account_state",
                json.dumps(self.account_state)
            )
            
            # Publish updated collateral information
            if self.event_bus:
                self.event_bus.publish_sync("collateral_status", {
                    "total_value": self.account_state["total_collateral_value"],
                    "available_margin": self.account_state["available_margin"],
                    "effective_leverage": self.account_state["effective_leverage"],
                    "assets": self.account_state["collateral_assets"],
                    "timestamp": time.time()
                })
                
        except Exception as e:
            self.logger.error(f"Error processing collateral update: {e}")
    
    async def on_position_open_request(self, data):
        """Validate position open requests against capital efficiency rules.
        Returns approval or rejection based on margin availability."""
        try:
            position_id = data.get("position_id")
            symbol = data.get("symbol")
            side = data.get("side")
            size = data.get("size")
            leverage = data.get("leverage", 1.0)
            notional_value = data.get("notional_value")
            
            if not all([position_id, symbol, side, size is not None]):
                self.logger.warning(f"Incomplete position open request: {data}")
                await self._reject_position(position_id, "Incomplete request data")
                return
            
            # Calculate required margin for this position
            required_margin = await self._calculate_required_margin(symbol, size, leverage)
            
            # Check available margin
            if required_margin > self.account_state["available_margin"]:
                self.logger.warning(f"Insufficient margin: required {required_margin}, available {self.account_state['available_margin']}")
                await self._reject_position(
                    position_id, 
                    f"Insufficient margin. Required: {required_margin}, Available: {self.account_state['available_margin']}"
                )
                return
            
            # Check leverage limits
            max_leverage = self.config["max_leverage"]
            if leverage > max_leverage:
                await self._reject_position(
                    position_id,
                    f"Leverage {leverage}x exceeds maximum allowed {max_leverage}x"
                )
                return
                
            # Check potential portfolio leverage after this position
            new_notional = self.account_state["total_notional_value"]
            if notional_value:
                new_notional += notional_value
            else:
                new_notional += (size * leverage)
                
            new_leverage = new_notional / self.account_state["total_collateral_value"] if self.account_state["total_collateral_value"] > 0 else max_leverage
            
            if new_leverage > max_leverage:
                await self._reject_position(
                    position_id,
                    f"Opening this position would exceed max portfolio leverage. Current: {self.account_state['effective_leverage']:.2f}x, After: {new_leverage:.2f}x, Max: {max_leverage}x"
                )
                return
                
            # Check account tier and margin tier
            if notional_value:
                current_tier = self._get_margin_tier(notional_value)
                if current_tier > self.account_state["account_tier"]:
                    await self._reject_position(
                        position_id,
                        f"Position size exceeds current account tier. Upgrade required for positions > {self.config['margin_tiers'][self.account_state['account_tier']-1]['notional_limit']}"
                    )
                    return
                    
            # If all checks pass, approve the position with cross-margin benefits
            # Calculate portfolio margin benefits
            portfolio_benefit = 0.0
            if self.config["portfolio_margin_enabled"]:
                portfolio_benefit = await self._calculate_portfolio_margin_benefit(symbol, side, size)
                
            # Approve with calculated benefits
            await self._approve_position(position_id, {
                "required_margin": required_margin,
                "available_margin": self.account_state["available_margin"],
                "portfolio_margin_benefit": portfolio_benefit,
                "cross_margin": self.config["cross_margin_enabled"],
                "effective_margin": required_margin - portfolio_benefit
            })
            
        except Exception as e:
            self.logger.error(f"Error processing position open request: {e}")
            if 'position_id' in locals():
                await self._reject_position(position_id, f"Capital efficiency error: {str(e)}")
    
    async def on_position_update(self, data):
        """Handle position updates and recalculate margin requirements."""
        try:
            position_id = data.get("position_id")
            symbol = data.get("symbol")
            notional_value = data.get("notional_value")
            unrealized_pnl = data.get("unrealized_pnl")
            leverage = data.get("leverage")
            
            if not position_id or not symbol:
                return
                
            # Update position data
            if position_id not in self.account_state["open_positions"]:
                self.account_state["open_positions"][position_id] = {}
                
            self.account_state["open_positions"][position_id].update({
                "symbol": symbol,
                "notional_value": notional_value,
                "unrealized_pnl": unrealized_pnl,
                "leverage": leverage,
                "last_updated": time.time()
            })
            
            # Recalculate margin values
            await self._recalculate_margin_values()
            
            # Check margin health
            margin_ratio = self.account_state["margin_ratio"]
            if margin_ratio < self.config["margin_call_threshold"]:
                # Issue margin call alert
                if self.event_bus:
                    self.event_bus.publish_sync("margin_call_alert", {
                        "margin_ratio": margin_ratio,
                        "threshold": self.config["margin_call_threshold"],
                        "timestamp": time.time()
                    })
            
        except Exception as e:
            self.logger.error(f"Error processing position update: {e}")
    
    async def on_position_close(self, data):
        """Handle position close events and release margin."""
        position_id = data.get("position_id")
        
        if not position_id:
            return
            
        # Remove position from open positions
        if position_id in self.account_state["open_positions"]:
            del self.account_state["open_positions"][position_id]
            
        # Recalculate margin values
        await self._recalculate_margin_values()
        
        # Update state in Redis
        await self.redis_client.set(
            "capital:account_state",
            json.dumps(self.account_state)
        )
        
    async def on_leverage_change_request(self, data):
        """Handle leverage change requests and validate against capital efficiency rules."""
        position_id = data.get("position_id")
        new_leverage = data.get("new_leverage")
        
        if not position_id or new_leverage is None:
            return
            
        # Check if position exists
        if position_id not in self.account_state["open_positions"]:
            if self.event_bus:
                self.event_bus.publish_sync("leverage_change_rejected", {
                    "position_id": position_id,
                    "reason": "Position not found",
                    "timestamp": time.time()
                })
            return
            
        # Check if new leverage exceeds maximum
        max_leverage = self.config["max_leverage"]
        if new_leverage > max_leverage:
            if self.event_bus:
                self.event_bus.publish_sync("leverage_change_rejected", {
                    "position_id": position_id,
                    "reason": f"Requested leverage {new_leverage}x exceeds maximum {max_leverage}x",
                    "timestamp": time.time()
                })
            return
            
        # Calculate new margin requirement
        position = self.account_state["open_positions"][position_id]
        symbol = position.get("symbol")
        size = position.get("size")
        
        if not symbol or not size:
            return
            
        new_margin = await self._calculate_required_margin(symbol, size, new_leverage)
        
        # Check if we have sufficient available margin
        current_margin = position.get("required_margin", 0)
        margin_difference = new_margin - current_margin
        
        if margin_difference > 0 and margin_difference > self.account_state["available_margin"]:
            if self.event_bus:
                self.event_bus.publish_sync("leverage_change_rejected", {
                    "position_id": position_id,
                    "reason": f"Insufficient margin for leverage change. Additional margin required: {margin_difference}",
                    "timestamp": time.time()
                })
            return
            
        # If all checks pass, approve leverage change
        if self.event_bus:
            self.event_bus.publish_sync("leverage_change_approved", {
                "position_id": position_id,
                "new_leverage": new_leverage,
                "new_margin": new_margin,
                "timestamp": time.time()
            })
    
    async def on_margin_transfer_request(self, data):
        """Handle margin transfer requests between positions."""
        from_position_id = data.get("from_position_id")
        to_position_id = data.get("to_position_id")
        amount = data.get("amount")
        
        if not all([from_position_id, to_position_id, amount is not None]) or amount <= 0:
            if self.event_bus:
                self.event_bus.publish_sync("margin_transfer_rejected", {
                    "reason": "Invalid transfer parameters",
                    "timestamp": time.time()
                })
            return
            
        # Check if both positions exist
        if from_position_id not in self.account_state["open_positions"] or to_position_id not in self.account_state["open_positions"]:
            if self.event_bus:
                self.event_bus.publish_sync("margin_transfer_rejected", {
                    "reason": "One or both positions not found",
                    "timestamp": time.time()
                })
            return
            
        # Check if source position has sufficient margin
        from_position = self.account_state["open_positions"][from_position_id]
        from_margin = from_position.get("required_margin", 0)
        
        # Calculate minimum margin required for source position
        from_symbol = from_position.get("symbol")
        from_size = from_position.get("size")
        from_leverage = from_position.get("leverage", 1.0)
        
        min_margin = await self._calculate_maintenance_margin(from_symbol, from_size, from_leverage)
        available_for_transfer = from_margin - min_margin
        
        if amount > available_for_transfer:
            if self.event_bus:
                self.event_bus.publish_sync("margin_transfer_rejected", {
                    "reason": f"Insufficient margin available for transfer. Maximum available: {available_for_transfer}",
                    "timestamp": time.time()
                })
            return
            
        # If all checks pass, approve transfer
        if self.event_bus:
            self.event_bus.publish_sync("margin_transfer_approved", {
                "from_position_id": from_position_id,
                "to_position_id": to_position_id,
                "amount": amount,
                "timestamp": time.time()
            })
    
    async def on_shutdown(self, data):
        """Handle system shutdown."""
        self.logger.info("Shutting down Capital Efficiency Module")
        self.shutdown_event.set()
        if self.redis_client:
            await self.redis_client.close()
    
    # Helper methods
    
    async def _recalculate_margin_values(self):
        """Recalculate margin values based on current positions and collateral."""
        try:
            # Calculate total required margin
            total_required_margin = sum(
                position.get("required_margin", 0) 
                for position in self.account_state["open_positions"].values()
            )
            self.account_state["total_required_margin"] = total_required_margin
            
            # Calculate total maintenance margin
            total_maintenance_margin = sum(
                position.get("maintenance_margin", 0) 
                for position in self.account_state["open_positions"].values()
            )
            self.account_state["total_maintenance_margin"] = total_maintenance_margin
            
            # Calculate available margin
            self.account_state["available_margin"] = (
                self.account_state["total_collateral_value"] - 
                self.account_state["total_required_margin"]
            )
            
            # Calculate margin ratio
            if self.account_state["total_maintenance_margin"] > 0:
                self.account_state["margin_ratio"] = (
                    self.account_state["total_collateral_value"] / 
                    self.account_state["total_maintenance_margin"]
                )
            else:
                self.account_state["margin_ratio"] = float('inf')
                
            # Calculate total notional value
            total_notional = sum(
                position.get("notional_value", 0) 
                for position in self.account_state["open_positions"].values()
            )
            self.account_state["total_notional_value"] = total_notional
            
        except Exception as e:
            self.logger.error(f"Error recalculating margin values: {e}")
    
    async def _calculate_required_margin(self, symbol, size, leverage):
        """Calculate the required initial margin for a position."""
        try:
            # Get market data for this symbol
            market_data = await self._get_market_data(symbol)
            price = market_data.get("price", 0)
            
            # Calculate notional value
            notional_value = price * size
            
            # Apply margin rate based on leverage and market conditions
            # Universal cross-margin principle: adaptive margin rates
            base_margin_rate = 1 / leverage
            
            # Add risk premium based on market volatility
            vol_data = market_data.get("volatility", 0.01)  # Default 1% volatility
            risk_premium = min(0.05, vol_data * 0.5)  # Cap at 5%
            
            # Determine final margin rate with minimum floor
            margin_rate = max(base_margin_rate, 0.01) + risk_premium
            
            # Apply tier discount for large accounts if applicable
            tier = self.account_state["account_tier"]
            if tier > 1:
                tier_discount = self.config["tier_discounts"].get(tier, 0.0)
                margin_rate = margin_rate * (1 - tier_discount)
            
            # Calculate required margin
            required_margin = notional_value * margin_rate
            
            return required_margin
            
        except Exception as e:
            self.logger.error(f"Error calculating required margin: {e}")
            return float('inf')  # Return infinity to reject position on error
    
    async def _calculate_maintenance_margin(self, symbol, size, leverage):
        """Calculate maintenance margin for an existing position."""
        try:
            # Get market data
            market_data = await self._get_market_data(symbol)
            price = market_data.get("price", 0)
            
            # Calculate notional value
            notional_value = price * size
            
            # Maintenance margin is typically lower than initial margin
            # For perpetual futures, this follows universal cross-margin principles
            base_rate = 0.005  # 0.5% base maintenance margin
            
            # Add volatility component
            vol_data = market_data.get("volatility", 0.01)  # Default 1% volatility
            vol_component = min(0.02, vol_data * 0.3)  # Cap at 2%
            
            # Higher leverage means higher maintenance requirement
            leverage_component = 0.001 * (leverage - 1) if leverage > 1 else 0
            
            # Calculate final maintenance margin rate
            maintenance_rate = base_rate + vol_component + leverage_component
            
            # Apply tier-based adjustments if applicable
            tier = self.account_state["account_tier"]
            if tier > 1:
                tier_discount = self.config["tier_discounts"].get(tier, 0.0) * 0.5  # Half of the initial margin discount
                maintenance_rate = maintenance_rate * (1 - tier_discount)
            
            return notional_value * maintenance_rate
            
        except Exception as e:
            self.logger.error(f"Error calculating maintenance margin: {e}")
            return float('inf')  # Return infinity to trigger liquidation on error
    
    async def _calculate_portfolio_margin_benefit(self, symbol, side, size):
        """Calculate portfolio margin benefits from correlated positions."""
        try:
            # If portfolio margin is not enabled, no benefit
            if not self.config["portfolio_margin_enabled"]:
                return 0.0
                
            # Check for opposing positions that can offset risk
            opposing_positions = []
            for pos_id, pos in self.account_state["open_positions"].items():
                # Check if this is a correlated or opposing asset
                if pos.get("symbol") == symbol and pos.get("side") != side:
                    # Direct hedge on the same asset
                    opposing_positions.append({
                        "position_id": pos_id,
                        "size": pos.get("size", 0),
                        "correlation": -1.0  # Perfect negative correlation
                    })
                else:
                    # Check correlation with other assets
                    correlation = await self._get_correlation(symbol, pos.get("symbol", ""))
                    if abs(correlation) > 0.25:  # Only consider meaningful correlations
                        opposing_positions.append({
                            "position_id": pos_id,
                            "size": pos.get("size", 0),
                            "correlation": correlation
                        })
            
            if not opposing_positions:
                return 0.0
            
            # Calculate benefit based on correlation and position sizes
            total_benefit = 0.0
            market_data = await self._get_market_data(symbol)
            price = market_data.get("price", 0)
            notional_value = price * size
            
            for opp in opposing_positions:
                # Calculate risk offset
                offset_ratio = min(1.0, opp["size"] / size) if size > 0 else 0
                
                # Apply correlation factor (negative correlation provides higher benefit)
                corr_factor = max(0, -opp["correlation"])  # Only negative correlation provides benefit
                
                # Calculate benefit for this position pair
                pair_benefit = notional_value * offset_ratio * corr_factor * self.config["portfolio_margin_factor"]
                total_benefit += pair_benefit
            
            # Cap the total benefit
            max_benefit = notional_value * 0.8  # Maximum 80% benefit
            return min(max_benefit, total_benefit)
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio margin benefit: {e}")
            return 0.0  # No benefit on error
    
    async def _get_market_data(self, symbol):
        """Get market data for a symbol from Redis."""
        try:
            market_data_key = f"market_data:{symbol}"
            market_data = await self.redis_client.get(market_data_key)
            
            if not market_data:
                # If no data in Redis, use default values
                return {
                    "price": 100.0,  # Default price
                    "volatility": 0.02,  # Default 2% volatility
                    "timestamp": time.time()
                }
            
            return json.loads(market_data)
            
        except Exception as e:
            self.logger.error(f"Error retrieving market data for {symbol}: {e}")
            # Return default values on error
            return {
                "price": 100.0,
                "volatility": 0.05,  # Higher volatility assumption on error
                "timestamp": time.time()
            }
    
    async def _get_correlation(self, symbol1, symbol2):
        """Get correlation between two trading symbols."""
        try:
            if symbol1 == symbol2:
                return 1.0  # Perfect correlation with self
                
            # Check if we have correlation data in Redis
            correlation_key = f"correlation:{symbol1}:{symbol2}"
            correlation_data = await self.redis_client.get(correlation_key)
            
            if correlation_data:
                return float(correlation_data)
                
            # Reverse key check
            correlation_key = f"correlation:{symbol2}:{symbol1}"
            correlation_data = await self.redis_client.get(correlation_key)
            
            if correlation_data:
                return float(correlation_data)
                
            # If no data available, use a conservative default
            # Assume no correlation (0.0) to avoid incorrect risk reduction
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Error retrieving correlation data: {e}")
            return 0.0  # Assume no correlation on error
    
    def _get_margin_tier(self, notional_value):
        """Determine the margin tier based on notional value."""
        current_tier = 1
        
        for tier_data in self.config["margin_tiers"]:
            if notional_value <= tier_data["notional_limit"]:
                break
            current_tier += 1
            
        return current_tier
    
    async def _reject_position(self, position_id, reason):
        """Reject a position request."""
        if not self.event_bus:
            self.logger.error(f"Cannot reject position {position_id}: No event bus")
            return
            
        self.event_bus.publish_sync("position_rejected", {
            "position_id": position_id,
            "reason": reason,
            "timestamp": time.time()
        })
        
        self.logger.warning(f"Rejected position {position_id}: {reason}")
    
    async def _approve_position(self, position_id, margin_data):
        """Approve a position request."""
        if not self.event_bus:
            self.logger.error(f"Cannot approve position {position_id}: No event bus")
            return
            
        self.event_bus.publish_sync("position_approved", {
            "position_id": position_id,
            "margin_data": margin_data,
            "timestamp": time.time()
        })
        
        self.logger.info(f"Approved position {position_id} with margin: {margin_data['effective_margin']}")

# Main entry point for standalone execution
if __name__ == "__main__":
    import logging
    import sys
    from utils.redis_client import RedisClient
    from utils.event_bus import EventBus
    from utils.async_support import AsyncSupport
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )
    
    logger = logging.getLogger("CapitalEfficiency")
    
    async def main():
        # Create event bus
        event_bus = EventBus()
        
        # Create Redis client with required configuration
        redis_client = RedisClient(
            host="localhost",
            port=6380,
            password="QuantumNexus2025",
            db=0
        )
        
        # Connect to Redis
        try:
            await redis_client.connect()
            logger.info("Connected to Redis Quantum Nexus")
        except Exception as e:
            logger.warning(f"⚠️ Failed to connect to Redis: {e} - running in limited mode")
            
        # Create async support
        async_support = AsyncSupport()
        
        # Create capital efficiency module
        module = CapitalEfficiencyModule(
            event_bus=event_bus,
            config=None  # Will use default config
        )
        # Set redis_client and async_support after construction
        module.redis_client = redis_client
        module.async_support = async_support
        
        # Initialize module
        if not await module.initialize():
            logger.warning("⚠️ Failed to initialize Capital Efficiency Module - running in limited mode")
            
        logger.info("Capital Efficiency Module running...")
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            # Clean shutdown
            await module.on_shutdown({})
            await redis_client.close()
    
    # Run the async main function
    asyncio.run(main())
