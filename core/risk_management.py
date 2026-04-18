#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RiskManagement component for trading risk assessment and control.
"""

import os
import asyncio
import logging
import json
from datetime import datetime

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class RiskManagement(BaseComponent):
    """
    Component for managing trading risks.
    Handles risk assessment, position sizing, and trade limitations.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the RiskManagement component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "RiskManagement"
        self.description = "Manages trading risks and position sizing"
        
        # Risk parameters
        self.max_position_size = self.config.get("max_position_size", {
            "BTC": 1.0,
            "ETH": 10.0,
            "default": 0.1  # Default for other assets
        })
        self.max_order_size = self.config.get("max_order_size", {
            "BTC": 0.5,
            "ETH": 5.0,
            "default": 0.05  # Default for other assets
        })
        self.daily_loss_limit = self.config.get("daily_loss_limit", 0.05)  # 5% of portfolio
        self.max_open_trades = self.config.get("max_open_trades", 10)
        self.max_open_trades_per_market = self.config.get("max_open_trades_per_market", 3)
        self.max_drawdown = self.config.get("max_drawdown", 0.15)  # 15% max drawdown
        self.min_trade_interval = self.config.get("min_trade_interval", 60)  # Seconds
        
        # Risk metrics
        self.portfolio_value = 0.0
        self.open_positions = {}
        self.position_values = {}
        self.portfolio_history = []
        self.trade_history = []
        self.daily_pnl = 0.0
        self.peak_portfolio_value = 0.0
        self.drawdown = 0.0
        self.last_trade_time = {}
        
        # Validation frequency
        self.validation_interval = self.config.get("validation_interval", 60)  # Seconds
        self.is_running = False
        self.validation_task = None
        
    async def initialize(self):
        """Initialize the RiskManagement component."""
        logger.info("Initializing RiskManagement component")
        
        # Subscribe to relevant events
        self.event_bus and self.event_bus.subscribe_sync("order.validate", self.on_order_validate)
        self.event_bus and self.event_bus.subscribe_sync("portfolio.update", self.on_portfolio_update)
        self.event_bus and self.event_bus.subscribe_sync("risk.config.update", self.on_config_update)
        self.event_bus and self.event_bus.subscribe_sync("risk.status", self.on_risk_status)
        self.event_bus and self.event_bus.subscribe_sync("order.filled", self.on_order_filled)
        self.event_bus and self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        
        # Load risk configuration and history
        await self.load_risk_data()
        
        # Start validation task
        self.is_running = True
        self.validation_task = asyncio.create_task(self.validate_portfolio_loop())
        
        logger.info("RiskManagement component initialized")
        
    async def load_risk_data(self):
        """Load risk configuration and history from storage."""
        risk_file = os.path.join(self.config.get("data_dir", "data"), "risk_data.json")
        
        try:
            if os.path.exists(risk_file):
                with open(risk_file, 'r') as f:
                    risk_data = json.load(f)
                    
                # Load risk configuration
                if "config" in risk_data:
                    config = risk_data["config"]
                    self.max_position_size = config.get("max_position_size", self.max_position_size)
                    self.max_order_size = config.get("max_order_size", self.max_order_size)
                    self.daily_loss_limit = config.get("daily_loss_limit", self.daily_loss_limit)
                    self.max_open_trades = config.get("max_open_trades", self.max_open_trades)
                    self.max_open_trades_per_market = config.get("max_open_trades_per_market", self.max_open_trades_per_market)
                    self.max_drawdown = config.get("max_drawdown", self.max_drawdown)
                    self.min_trade_interval = config.get("min_trade_interval", self.min_trade_interval)
                
                # Load portfolio data
                if "portfolio" in risk_data:
                    portfolio = risk_data["portfolio"]
                    self.portfolio_value = portfolio.get("value", 0.0)
                    self.open_positions = portfolio.get("positions", {})
                    self.position_values = portfolio.get("position_values", {})
                    self.portfolio_history = portfolio.get("history", [])
                    self.peak_portfolio_value = portfolio.get("peak_value", 0.0)
                    self.drawdown = portfolio.get("drawdown", 0.0)
                    self.daily_pnl = portfolio.get("daily_pnl", 0.0)
                
                # Load trade history
                if "trades" in risk_data:
                    self.trade_history = risk_data["trades"]
                    
                    # Reconstruct last trade time dictionary
                    for trade in self.trade_history:
                        market = trade.get("market")
                        timestamp = trade.get("timestamp")
                        if market and timestamp:
                            self.last_trade_time[market] = timestamp
                
                logger.info("Loaded risk management data")
        except Exception as e:
            logger.error(f"Error loading risk data: {str(e)}")
    
    async def save_risk_data(self):
        """Save risk configuration and history to storage."""
        risk_file = os.path.join(self.config.get("data_dir", "data"), "risk_data.json")
        
        try:
            os.makedirs(os.path.dirname(risk_file), exist_ok=True)
            
            risk_data = {
                "config": {
                    "max_position_size": self.max_position_size,
                    "max_order_size": self.max_order_size,
                    "daily_loss_limit": self.daily_loss_limit,
                    "max_open_trades": self.max_open_trades,
                    "max_open_trades_per_market": self.max_open_trades_per_market,
                    "max_drawdown": self.max_drawdown,
                    "min_trade_interval": self.min_trade_interval
                },
                "portfolio": {
                    "value": self.portfolio_value,
                    "positions": self.open_positions,
                    "position_values": self.position_values,
                    "history": self.portfolio_history[-100:],  # Keep last 100 entries
                    "peak_value": self.peak_portfolio_value,
                    "drawdown": self.drawdown,
                    "daily_pnl": self.daily_pnl
                },
                "trades": self.trade_history[-100:],  # Keep last 100 trades
                "last_saved": datetime.now().isoformat()
            }
            
            with open(risk_file, 'w') as f:
                json.dump(risk_data, f, indent=2)
                
            logger.info("Saved risk management data")
        except Exception as e:
            logger.error(f"Error saving risk data: {str(e)}")
    
    async def validate_portfolio_loop(self):
        """Continuously validate portfolio risk at specified intervals."""
        try:
            while self.is_running:
                await self.validate_portfolio()
                await asyncio.sleep(self.validation_interval)
        except asyncio.CancelledError:
            logger.info("Portfolio validation loop cancelled")
        except Exception as e:
            logger.error(f"Error in portfolio validation loop: {str(e)}")
            # Restart the loop
            if self.is_running:
                self.validation_task = asyncio.create_task(self.validate_portfolio_loop())
    
    async def validate_portfolio(self):
        """Validate portfolio against risk parameters."""
        try:
            # Calculate current drawdown
            if self.portfolio_value > self.peak_portfolio_value:
                self.peak_portfolio_value = self.portfolio_value
                self.drawdown = 0.0
            elif self.peak_portfolio_value > 0:
                self.drawdown = 1.0 - (self.portfolio_value / self.peak_portfolio_value)
            
            # Check if drawdown exceeds limit
            if self.drawdown > self.max_drawdown:
                logger.warning(f"Maximum drawdown exceeded: {self.drawdown:.2%} > {self.max_drawdown:.2%}")
                self.event_bus.publish("risk.alert", {
                    "type": "max_drawdown_exceeded",
                    "current_drawdown": self.drawdown,
                    "max_drawdown": self.max_drawdown,
                    "portfolio_value": self.portfolio_value,
                    "peak_value": self.peak_portfolio_value,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Check daily loss limit
            if self.daily_pnl < 0 and abs(self.daily_pnl) > self.daily_loss_limit * self.portfolio_value:
                logger.warning(f"Daily loss limit exceeded: {abs(self.daily_pnl):.2f} > {self.daily_loss_limit * self.portfolio_value:.2f}")
                self.event_bus.publish("risk.alert", {
                    "type": "daily_loss_limit_exceeded",
                    "daily_pnl": self.daily_pnl,
                    "daily_loss_limit": self.daily_loss_limit * self.portfolio_value,
                    "portfolio_value": self.portfolio_value,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Record portfolio history
            self.portfolio_history.append({
                "timestamp": datetime.now().isoformat(),
                "value": self.portfolio_value,
                "drawdown": self.drawdown,
                "daily_pnl": self.daily_pnl
            })
            
            # Trim history if too long
            if len(self.portfolio_history) > 1000:
                self.portfolio_history = self.portfolio_history[-1000:]
            
            # Save risk data periodically
            await self.save_risk_data()
            
        except Exception as e:
            logger.error(f"Error validating portfolio: {str(e)}")
    
    async def validate_order(self, order_data):
        """
        Validate an order against risk parameters.
        
        Args:
            order_data: Order data to validate
            
        Returns:
            dict: Validation result
        """
        try:
            # Extract order details
            market = order_data.get("market")
            side = order_data.get("side")
            order_type = order_data.get("type")
            amount = order_data.get("amount", 0)
            price = order_data.get("price", 0)
            
            if not market or not side or not amount:
                return {
                    "valid": False,
                    "reason": "Missing required order parameters",
                    "order_data": order_data
                }
            
            # Get asset from market symbol
            asset = market.split("/")[0] if "/" in market else market.split("-")[0]
            
            # Check against maximum order size
            max_size = self.max_order_size.get(asset, self.max_order_size.get("default", 0.05))
            if amount > max_size:
                return {
                    "valid": False,
                    "reason": f"Order size exceeds maximum ({amount} > {max_size})",
                    "order_data": order_data
                }
            
            # Check current position size
            current_position = self.open_positions.get(market, 0)
            if side == "buy":
                new_position = current_position + amount
            else:  # sell
                new_position = current_position - amount
                
                # Check if selling more than we have
                if new_position < 0 and order_type != "margin":
                    return {
                        "valid": False,
                        "reason": f"Insufficient position for sell order ({current_position} < {amount})",
                        "order_data": order_data
                    }
            
            # Check against maximum position size (for buys)
            if side == "buy":
                max_position = self.max_position_size.get(asset, self.max_position_size.get("default", 0.1))
                if new_position > max_position:
                    return {
                        "valid": False,
                        "reason": f"Position size would exceed maximum ({new_position} > {max_position})",
                        "order_data": order_data
                    }
            
            # Check number of open trades
            open_trade_count = len(self.open_positions)
            if side == "buy" and current_position == 0 and open_trade_count >= self.max_open_trades:
                return {
                    "valid": False,
                    "reason": f"Maximum number of open trades reached ({open_trade_count} >= {self.max_open_trades})",
                    "order_data": order_data
                }
            
            # Check number of open trades per market
            market_base = market.split("/")[0] if "/" in market else market.split("-")[0]
            market_trades = sum(1 for m in self.open_positions if m.startswith(market_base))
            if side == "buy" and current_position == 0 and market_trades >= self.max_open_trades_per_market:
                return {
                    "valid": False,
                    "reason": f"Maximum number of trades for {market_base} reached ({market_trades} >= {self.max_open_trades_per_market})",
                    "order_data": order_data
                }
            
            # Check minimum trade interval
            if market in self.last_trade_time:
                last_time = datetime.fromisoformat(self.last_trade_time[market])
                elapsed_seconds = (datetime.now() - last_time).total_seconds()
                if elapsed_seconds < self.min_trade_interval:
                    return {
                        "valid": False,
                        "reason": f"Minimum trade interval not reached ({elapsed_seconds:.1f}s < {self.min_trade_interval}s)",
                        "order_data": order_data
                    }
            
            # If all checks pass, order is valid
            return {
                "valid": True,
                "order_data": order_data
            }
            
        except Exception as e:
            logger.error(f"Error validating order: {str(e)}")
            return {
                "valid": False,
                "reason": f"Validation error: {str(e)}",
                "order_data": order_data
            }
    
    async def update_position(self, order_data):
        """
        Update position based on filled order.
        
        Args:
            order_data: Filled order data
        """
        try:
            market = order_data.get("market")
            side = order_data.get("side")
            amount = order_data.get("filled", order_data.get("amount", 0))
            price = order_data.get("average_price", order_data.get("price", 0))
            
            if not market or not side or not amount or not price:
                logger.warning("Cannot update position: missing order details")
                return
            
            # Update position
            current_position = self.open_positions.get(market, 0)
            if side == "buy":
                new_position = current_position + amount
            else:  # sell
                new_position = current_position - amount
            
            # Calculate position value
            position_value = new_position * price
            
            # Update stored values
            if new_position > 0:
                self.open_positions[market] = new_position
                self.position_values[market] = position_value
            else:
                # Remove position if zero or negative
                self.open_positions.pop(market, None)
                self.position_values.pop(market, None)
            
            # Update last trade time
            self.last_trade_time[market] = datetime.now().isoformat()
            
            # Record trade
            trade_record = {
                "market": market,
                "side": side,
                "amount": amount,
                "price": price,
                "position": new_position,
                "position_value": position_value,
                "timestamp": datetime.now().isoformat()
            }
            self.trade_history.append(trade_record)
            
            # Trim trade history if too long
            if len(self.trade_history) > 1000:
                self.trade_history = self.trade_history[-1000:]
            
            logger.info(f"Updated position for {market}: {new_position} (value: {position_value:.2f})")
            
            # Calculate total portfolio value
            self.portfolio_value = sum(self.position_values.values())
            
            # Publish position update
            self.event_bus.publish("risk.position.update", {
                "market": market,
                "position": new_position,
                "position_value": position_value,
                "portfolio_value": self.portfolio_value,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error updating position: {str(e)}")
    
    async def update_portfolio(self, portfolio_data):
        """
        Update portfolio data.
        
        Args:
            portfolio_data: Portfolio update data
        """
        try:
            # Update portfolio value
            if "total_value" in portfolio_data:
                self.portfolio_value = portfolio_data["total_value"]
                
                # Update peak value and drawdown
                if self.portfolio_value > self.peak_portfolio_value:
                    self.peak_portfolio_value = self.portfolio_value
                    self.drawdown = 0.0
                elif self.peak_portfolio_value > 0:
                    self.drawdown = 1.0 - (self.portfolio_value / self.peak_portfolio_value)
            
            # Update positions
            if "positions" in portfolio_data:
                positions = portfolio_data["positions"]
                self.open_positions = {}
                self.position_values = {}
                
                for market, position in positions.items():
                    amount = position.get("amount", 0)
                    value = position.get("value", 0)
                    
                    if amount > 0:
                        self.open_positions[market] = amount
                        self.position_values[market] = value
            
            # Update daily PnL
            if "daily_pnl" in portfolio_data:
                self.daily_pnl = portfolio_data["daily_pnl"]
            
            # Record in portfolio history
            self.portfolio_history.append({
                "timestamp": datetime.now().isoformat(),
                "value": self.portfolio_value,
                "drawdown": self.drawdown,
                "daily_pnl": self.daily_pnl
            })
            
            # Trim history if too long
            if len(self.portfolio_history) > 1000:
                self.portfolio_history = self.portfolio_history[-1000:]
            
            logger.info(f"Updated portfolio: {self.portfolio_value:.2f} (drawdown: {self.drawdown:.2%})")
            
            # Save updated data
            await self.save_risk_data()
            
        except Exception as e:
            logger.error(f"Error updating portfolio: {str(e)}")
    
    async def get_risk_status(self):
        """
        Get current risk status.
        
        Returns:
            dict: Risk status information
        """
        return {
            "portfolio_value": self.portfolio_value,
            "open_positions": self.open_positions,
            "position_values": self.position_values,
            "portfolio_peak": self.peak_portfolio_value,
            "drawdown": self.drawdown,
            "daily_pnl": self.daily_pnl,
            "risk_limits": {
                "max_position_size": self.max_position_size,
                "max_order_size": self.max_order_size,
                "daily_loss_limit": self.daily_loss_limit,
                "max_open_trades": self.max_open_trades,
                "max_open_trades_per_market": self.max_open_trades_per_market,
                "max_drawdown": self.max_drawdown,
                "min_trade_interval": self.min_trade_interval
            },
            "trade_count": len(self.trade_history),
            "active_markets": list(self.open_positions.keys()),
            "timestamp": datetime.now().isoformat()
        }
    
    async def update_risk_config(self, config_data):
        """
        Update risk configuration.
        
        Args:
            config_data: New configuration values
            
        Returns:
            dict: Updated configuration
        """
        try:
            # Update configuration parameters
            if "max_position_size" in config_data:
                self.max_position_size = config_data["max_position_size"]
                
            if "max_order_size" in config_data:
                self.max_order_size = config_data["max_order_size"]
                
            if "daily_loss_limit" in config_data:
                self.daily_loss_limit = config_data["daily_loss_limit"]
                
            if "max_open_trades" in config_data:
                self.max_open_trades = config_data["max_open_trades"]
                
            if "max_open_trades_per_market" in config_data:
                self.max_open_trades_per_market = config_data["max_open_trades_per_market"]
                
            if "max_drawdown" in config_data:
                self.max_drawdown = config_data["max_drawdown"]
                
            if "min_trade_interval" in config_data:
                self.min_trade_interval = config_data["min_trade_interval"]
                
            # Save updated configuration
            await self.save_risk_data()
            
            logger.info("Updated risk management configuration")
            
            return {
                "max_position_size": self.max_position_size,
                "max_order_size": self.max_order_size,
                "daily_loss_limit": self.daily_loss_limit,
                "max_open_trades": self.max_open_trades,
                "max_open_trades_per_market": self.max_open_trades_per_market,
                "max_drawdown": self.max_drawdown,
                "min_trade_interval": self.min_trade_interval
            }
            
        except Exception as e:
            logger.error(f"Error updating risk configuration: {str(e)}")
            return {}
    
    async def on_order_validate(self, data):
        """
        Handle order validate event.
        
        Args:
            data: Order validation request data
        """
        request_id = data.get("request_id")
        order_data = data.get("order", {})
        
        result = await self.validate_order(order_data)
        
        # Publish validation result
        self.event_bus.publish("order.validate.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_portfolio_update(self, data):
        """
        Handle portfolio update event.
        
        Args:
            data: Portfolio update data
        """
        await self.update_portfolio(data)
    
    async def on_config_update(self, data):
        """
        Handle risk configuration update event.
        
        Args:
            data: Configuration update data
        """
        request_id = data.get("request_id")
        config_data = data.get("config", {})
        
        result = await self.update_risk_config(config_data)
        
        # Publish configuration update result
        self.event_bus.publish("risk.config.updated", {
            "request_id": request_id,
            "config": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_risk_status(self, data):
        """
        Handle risk status request event.
        
        Args:
            data: Risk status request data
        """
        request_id = data.get("request_id")
        
        status = await self.get_risk_status()
        
        # Publish risk status
        self.event_bus.publish("risk.status.result", {
            "request_id": request_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_order_filled(self, data):
        """
        Handle order filled event.
        
        Args:
            data: Filled order data
        """
        await self.update_position(data)
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the RiskManagement component."""
        logger.info("Shutting down RiskManagement component")
        
        # Stop validation task
        self.is_running = False
        if self.validation_task and not self.validation_task.done():
            self.validation_task.cancel()
            try:
                await self.validation_task
            except asyncio.CancelledError:
                pass
        
        # Save final risk data
        await self.save_risk_data()
        
        logger.info("RiskManagement component shut down successfully")
