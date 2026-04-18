#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
PortfolioManager component for tracking and optimizing crypto assets.
"""

import os
import asyncio
import logging
import json
import aiohttp
from datetime import datetime, timedelta
import numpy as np

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class PortfolioManager(BaseComponent):
    """
    Component for managing crypto asset portfolio.
    Handles allocation, rebalancing, and performance tracking.
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the PortfolioManager component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(name="PortfolioManager", event_bus=event_bus, config=config)
        self.name = "PortfolioManager"
        self.description = "Manages crypto asset portfolio allocation and tracking"
        
        # Portfolio configuration
        self.target_allocation = self.config.get("target_allocation", {
            "BTC": 0.4,    # 40% Bitcoin
            "ETH": 0.3,    # 30% Ethereum
            "SOL": 0.1,    # 10% Solana
            "STABLES": 0.2 # 20% Stablecoins
        })
        self.rebalance_threshold = self.config.get("rebalance_threshold", 0.05)  # 5% deviation
        self.rebalance_interval = self.config.get("rebalance_interval", 86400)  # 1 day in seconds
        self.tax_harvest_threshold = self.config.get("tax_harvest_threshold", -0.1)  # -10% unrealized loss
        
        # Portfolio state
        self.portfolio = {}  # Current holdings
        self.asset_values = {}  # Current asset values
        self.total_value = 0.0  # Total portfolio value
        self.current_allocation = {}  # Current percentage allocation
        self.unrealized_pnl = {}  # Unrealized profit/loss
        self.realized_pnl = {}  # Realized profit/loss
        self.historical_performance = []  # Historical portfolio performance
        self.historical_allocations = []  # Historical allocations
        
        # Exchange connectivity
        self.session = None
        self.exchange_balances = {}  # Balances by exchange
        
        # Tasks
        self.update_interval = self.config.get("update_interval", 300)  # 5 minutes
        self.is_running = False
        self.update_task = None
        self.last_rebalance = None
        
    async def initialize(self, event_bus=None, config=None):
        """Initialize the PortfolioManager component."""
        logger.info("Initializing PortfolioManager component")
        return True
        
        # Subscribe to relevant events
        self.event_bus and self.event_bus.subscribe_sync("portfolio.update.balances", self.on_update_balances)
        self.event_bus and self.event_bus.subscribe_sync("portfolio.rebalance", self.on_rebalance_request)
        self.event_bus and self.event_bus.subscribe_sync("portfolio.allocation.update", self.on_allocation_update)
        self.event_bus and self.event_bus.subscribe_sync("portfolio.status", self.on_portfolio_status)
        self.event_bus and self.event_bus.subscribe_sync("market.data.update", self.on_market_data_update)
        self.event_bus and self.event_bus.subscribe_sync("order.filled", self.on_order_filled)
        self.event_bus and self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        
        # Create HTTP session
        self.session = aiohttp.ClientSession()
        
        # Load portfolio data
        await self.load_portfolio_data()
        
        # Start update task
        self.is_running = True
        self.update_task = asyncio.create_task(self.update_portfolio_loop())
        
        logger.info("PortfolioManager component initialized")
        
    async def load_portfolio_data(self):
        """Load portfolio data from storage."""
        portfolio_file = os.path.join(self.config.get("data_dir", "data"), "portfolio.json")
        
        try:
            if os.path.exists(portfolio_file):
                with open(portfolio_file, 'r') as f:
                    portfolio_data = json.load(f)
                    
                # Load portfolio state
                if "portfolio" in portfolio_data:
                    self.portfolio = portfolio_data["portfolio"]
                    
                if "asset_values" in portfolio_data:
                    self.asset_values = portfolio_data["asset_values"]
                    
                if "total_value" in portfolio_data:
                    self.total_value = portfolio_data["total_value"]
                    
                if "current_allocation" in portfolio_data:
                    self.current_allocation = portfolio_data["current_allocation"]
                    
                if "unrealized_pnl" in portfolio_data:
                    self.unrealized_pnl = portfolio_data["unrealized_pnl"]
                    
                if "realized_pnl" in portfolio_data:
                    self.realized_pnl = portfolio_data["realized_pnl"]
                    
                if "last_rebalance" in portfolio_data:
                    self.last_rebalance = portfolio_data["last_rebalance"]
                    
                # Load historical data
                if "historical_performance" in portfolio_data:
                    self.historical_performance = portfolio_data["historical_performance"]
                    
                if "historical_allocations" in portfolio_data:
                    self.historical_allocations = portfolio_data["historical_allocations"]
                    
                # Load exchange balances
                if "exchange_balances" in portfolio_data:
                    self.exchange_balances = portfolio_data["exchange_balances"]
                    
                logger.info("Loaded portfolio data")
        except Exception as e:
            logger.error(f"Error loading portfolio data: {str(e)}")
    
    async def save_portfolio_data(self):
        """Save portfolio data to storage."""
        portfolio_file = os.path.join(self.config.get("data_dir", "data"), "portfolio.json")
        
        try:
            os.makedirs(os.path.dirname(portfolio_file), exist_ok=True)
            
            portfolio_data = {
                "portfolio": self.portfolio,
                "asset_values": self.asset_values,
                "total_value": self.total_value,
                "current_allocation": self.current_allocation,
                "unrealized_pnl": self.unrealized_pnl,
                "realized_pnl": self.realized_pnl,
                "last_rebalance": self.last_rebalance,
                "historical_performance": self.historical_performance[-100:],  # Keep last 100 entries
                "historical_allocations": self.historical_allocations[-100:],  # Keep last 100 entries
                "exchange_balances": self.exchange_balances,
                "last_saved": datetime.now().isoformat()
            }
            
            with open(portfolio_file, 'w') as f:
                json.dump(portfolio_data, f, indent=2)
                
            logger.info("Saved portfolio data")
        except Exception as e:
            logger.error(f"Error saving portfolio data: {str(e)}")
    
    async def update_portfolio_loop(self):
        """Continuously update portfolio at specified interval."""
        try:
            while self.is_running:
                await self.update_portfolio()
                await asyncio.sleep(self.update_interval)
        except asyncio.CancelledError:
            logger.info("Portfolio update loop cancelled")
        except Exception as e:
            logger.error(f"Error in portfolio update loop: {str(e)}")
            # Restart the loop
            if self.is_running:
                self.update_task = asyncio.create_task(self.update_portfolio_loop())
    
    async def update_portfolio(self):
        """Update portfolio state and check for rebalance needs."""
        try:
            # Calculate portfolio total value
            self.total_value = sum(self.asset_values.values())
            
            if self.total_value > 0:
                # Calculate current allocation
                for asset, value in self.asset_values.items():
                    self.current_allocation[asset] = value / self.total_value
            
            # Check if rebalance is needed
            rebalance_needed = await self.check_rebalance_needed()
            
            # Record portfolio performance
            self.historical_performance.append({
                "timestamp": datetime.now().isoformat(),
                "total_value": self.total_value,
                "allocation": self.current_allocation.copy()
            })
            
            # Trim history if too long
            if len(self.historical_performance) > 1000:
                self.historical_performance = self.historical_performance[-1000:]
            
            # Save portfolio data
            await self.save_portfolio_data()
            
            # Publish portfolio update
            self.event_bus.publish("portfolio.updated", {
                "total_value": self.total_value,
                "allocation": self.current_allocation,
                "assets": self.portfolio,
                "asset_values": self.asset_values,
                "unrealized_pnl": self.unrealized_pnl,
                "realized_pnl": self.realized_pnl,
                "rebalance_needed": rebalance_needed,
                "timestamp": datetime.now().isoformat()
            })
            
            # Check if automatic rebalancing is enabled and needed
            if rebalance_needed and self.config.get("auto_rebalance", False):
                await self.rebalance_portfolio()
                
        except Exception as e:
            logger.error(f"Error updating portfolio: {str(e)}")
    
    async def check_rebalance_needed(self):
        """
        Check if portfolio rebalancing is needed.
        
        Returns:
            bool: True if rebalancing is needed
        """
        if not self.target_allocation or not self.current_allocation:
            return False
            
        # Check allocation deviations
        for asset, target in self.target_allocation.items():
            current = self.current_allocation.get(asset, 0)
            deviation = abs(current - target)
            
            if deviation > self.rebalance_threshold:
                logger.info(f"Rebalance needed: {asset} deviation {deviation:.2%} exceeds threshold {self.rebalance_threshold:.2%}")
                return True
        
        # Check time since last rebalance
        if self.last_rebalance:
            last_time = datetime.fromisoformat(self.last_rebalance)
            elapsed_seconds = (datetime.now() - last_time).total_seconds()
            
            if elapsed_seconds > self.rebalance_interval:
                logger.info(f"Rebalance needed: Time since last rebalance ({elapsed_seconds:.0f}s) exceeds interval ({self.rebalance_interval}s)")
                return True
        
        return False
    
    async def analyze(self, portfolio_data=None):
        """Analyze portfolio performance and metrics."""
        try:
            data = portfolio_data or {
                'portfolio': self.portfolio,
                'total_value': self.total_value,
                'allocation': self.current_allocation
            }
            
            return {
                'status': 'success',
                'total_value': self.total_value,
                'allocation': self.current_allocation,
                'unrealized_pnl': sum(self.unrealized_pnl.values()),
                'realized_pnl': sum(self.realized_pnl.values()),
                'assets': len(self.portfolio)
            }
        except Exception as e:
            logger.error(f"Portfolio analysis error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def rebalance(self):
        """Rebalance portfolio to target allocation."""
        return await self.rebalance_portfolio()
    
    async def generate_report(self, report_type='summary'):
        """Generate portfolio report."""
        try:
            return {
                'status': 'success',
                'report_type': report_type,
                'timestamp': datetime.now().isoformat(),
                'total_value': self.total_value,
                'allocation': self.current_allocation,
                'performance': self.historical_performance[-10:] if self.historical_performance else []
            }
        except Exception as e:
            logger.error(f"Report generation error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def rebalance_portfolio(self):
        """
        Rebalance portfolio to match target allocation.
        
        Returns:
            dict: Rebalance result
        """
        try:
            logger.info("Rebalancing portfolio")
            
            if not self.target_allocation or not self.current_allocation or self.total_value == 0:
                return {
                    "success": False,
                    "error": "Insufficient portfolio data for rebalancing"
                }
            
            # Calculate target values
            target_values = {}
            for asset, allocation in self.target_allocation.items():
                target_values[asset] = self.total_value * allocation
            
            # Calculate needed adjustments
            adjustments = {}
            for asset, target_value in target_values.items():
                current_value = self.asset_values.get(asset, 0)
                adjustment = target_value - current_value
                
                if abs(adjustment) > 0.01:  # Ignore tiny adjustments
                    adjustments[asset] = adjustment
            
            if not adjustments:
                logger.info("No significant adjustments needed for rebalancing")
                return {
                    "success": True,
                    "message": "No significant adjustments needed"
                }
            
            # Record rebalance in history
            self.historical_allocations.append({
                "timestamp": datetime.now().isoformat(),
                "before": self.current_allocation.copy(),
                "target": self.target_allocation.copy(),
                "adjustments": adjustments
            })
            
            # Update last rebalance time
            self.last_rebalance = datetime.now().isoformat()
            
            # Publish rebalance event
            self.event_bus.publish("portfolio.rebalance.needed", {
                "adjustments": adjustments,
                "current_allocation": self.current_allocation,
                "target_allocation": self.target_allocation,
                "timestamp": datetime.now().isoformat()
            })
            
            # Save portfolio data
            await self.save_portfolio_data()
            
            return {
                "success": True,
                "adjustments": adjustments,
                "current_allocation": self.current_allocation,
                "target_allocation": self.target_allocation
            }
            
        except Exception as e:
            logger.error(f"Error rebalancing portfolio: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_asset_prices(self, market_data):
        """
        Update asset prices based on market data.
        
        Args:
            market_data: Market data update
        """
        try:
            market = market_data.get("market")
            if not market:
                return
                
            # Extract asset from market symbol
            asset = market.split("/")[0] if "/" in market else market.split("-")[0]
            
            # Get price from market data
            price = market_data.get("price")
            if not price:
                return
                
            # Update asset value if we have it in portfolio
            if asset in self.portfolio:
                amount = self.portfolio[asset]
                self.asset_values[asset] = amount * price
                
                # Calculate unrealized PnL if we have cost basis
                if asset in self.unrealized_pnl:
                    cost_basis = self.unrealized_pnl[asset].get("cost_basis", 0)
                    if cost_basis > 0:
                        current_value = self.asset_values[asset]
                        unrealized_pnl = current_value - cost_basis
                        unrealized_pnl_percent = unrealized_pnl / cost_basis if cost_basis > 0 else 0
                        
                        self.unrealized_pnl[asset].update({
                            "unrealized_pnl": unrealized_pnl,
                            "unrealized_pnl_percent": unrealized_pnl_percent,
                            "current_price": price,
                            "last_updated": datetime.now().isoformat()
                        })
                        
                        # Check for tax loss harvesting opportunity
                        if (unrealized_pnl_percent < self.tax_harvest_threshold and 
                            self.config.get("tax_loss_harvesting", False)):
                            self.event_bus.publish("portfolio.tax_harvest.opportunity", {
                                "asset": asset,
                                "unrealized_pnl": unrealized_pnl,
                                "unrealized_pnl_percent": unrealized_pnl_percent,
                                "cost_basis": cost_basis,
                                "current_value": current_value,
                                "timestamp": datetime.now().isoformat()
                            })
                
        except Exception as e:
            logger.error(f"Error updating asset prices: {str(e)}")
    
    async def update_balances(self, balances_data):
        """
        Update portfolio balances.
        
        Args:
            balances_data: Balance update data
            
        Returns:
            dict: Update result
        """
        try:
            exchange = balances_data.get("exchange")
            balances = balances_data.get("balances", {})
            cost_basis = balances_data.get("cost_basis", {})
            
            if not exchange or not balances:
                return {
                    "success": False,
                    "error": "Missing exchange or balances data"
                }
            
            # Store exchange-specific balances
            self.exchange_balances[exchange] = balances
            
            # Update combined portfolio
            self.portfolio = {}
            
            # Merge balances from all exchanges
            for ex_balances in self.exchange_balances.values():
                for asset, amount in ex_balances.items():
                    if asset in self.portfolio:
                        self.portfolio[asset] += amount
                    else:
                        self.portfolio[asset] = amount
            
            # Update cost basis for PnL calculation
            if cost_basis:
                for asset, basis in cost_basis.items():
                    if asset not in self.unrealized_pnl:
                        self.unrealized_pnl[asset] = {
                            "cost_basis": basis,
                            "unrealized_pnl": 0,
                            "unrealized_pnl_percent": 0,
                            "current_price": 0,
                            "last_updated": datetime.now().isoformat()
                        }
                    else:
                        self.unrealized_pnl[asset]["cost_basis"] = basis
            
            logger.info(f"Updated balances for {exchange} with {len(balances)} assets")
            
            # Update overall portfolio
            await self.update_portfolio()
            
            return {
                "success": True,
                "message": f"Updated balances for {exchange}"
            }
            
        except Exception as e:
            logger.error(f"Error updating balances: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_allocation(self, allocation_data):
        """
        Update target allocation.
        
        Args:
            allocation_data: Allocation update data
            
        Returns:
            dict: Update result
        """
        try:
            allocation = allocation_data.get("allocation")
            if not allocation:
                return {
                    "success": False,
                    "error": "Missing allocation data"
                }
            
            # Validate allocation (should sum to 1.0)
            total = sum(allocation.values())
            if abs(total - 1.0) > 0.01:  # Allow small rounding errors
                return {
                    "success": False,
                    "error": f"Allocation must sum to 1.0 (got {total})"
                }
            
            # Update target allocation
            self.target_allocation = allocation
            
            logger.info(f"Updated target allocation with {len(allocation)} assets")
            
            # Save portfolio data
            await self.save_portfolio_data()
            
            return {
                "success": True,
                "message": "Updated target allocation",
                "allocation": self.target_allocation
            }
            
        except Exception as e:
            logger.error(f"Error updating allocation: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_portfolio_status(self):
        """
        Get current portfolio status.
        
        Returns:
            dict: Portfolio status
        """
        # Calculate performance metrics
        performance_metrics = self.calculate_performance_metrics()
        
        return {
            "portfolio": self.portfolio,
            "asset_values": self.asset_values,
            "total_value": self.total_value,
            "current_allocation": self.current_allocation,
            "target_allocation": self.target_allocation,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "performance": performance_metrics,
            "exchange_balances": self.exchange_balances,
            "last_rebalance": self.last_rebalance,
            "timestamp": datetime.now().isoformat()
        }
    
    def calculate_performance_metrics(self):
        """
        Calculate portfolio performance metrics.
        
        Returns:
            dict: Performance metrics
        """
        try:
            # Need at least 2 data points for performance calculation
            if len(self.historical_performance) < 2:
                return {
                    "daily_return": 0,
                    "weekly_return": 0,
                    "monthly_return": 0,
                    "volatility": 0,
                    "sharpe_ratio": 0
                }
            
            # Get current and historical values
            current_time = datetime.now()
            current_value = self.total_value
            
            # Find historical values at specific time points
            daily_value = None
            weekly_value = None
            monthly_value = None
            
            # Extract values for return calculation
            values = []
            timestamps = []
            
            for entry in reversed(self.historical_performance):
                try:
                    timestamp = datetime.fromisoformat(entry.get("timestamp"))
                    value = entry.get("total_value", 0)
                    
                    # Record for volatility calculation
                    values.append(value)
                    timestamps.append(timestamp)
                    
                    # Find specific time points
                    time_diff = current_time - timestamp
                    
                    if daily_value is None and time_diff >= timedelta(days=1):
                        daily_value = value
                        
                    if weekly_value is None and time_diff >= timedelta(days=7):
                        weekly_value = value
                        
                    if monthly_value is None and time_diff >= timedelta(days=30):
                        monthly_value = value
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing historical entry: {str(e)}")
            
            # Calculate returns
            daily_return = (current_value / daily_value) - 1 if daily_value and daily_value > 0 else 0
            weekly_return = (current_value / weekly_value) - 1 if weekly_value and weekly_value > 0 else 0
            monthly_return = (current_value / monthly_value) - 1 if monthly_value and monthly_value > 0 else 0
            
            # Calculate volatility (standard deviation of daily returns)
            returns = []
            for i in range(1, len(values)):
                if values[i-1] > 0:
                    daily_ret = (values[i] / values[i-1]) - 1
                    returns.append(daily_ret)
            
            volatility = np.std(returns) * np.sqrt(365) if returns else 0
            
            # Calculate Sharpe ratio (assuming risk-free rate of 0.02 or 2%)
            risk_free_rate = 0.02
            excess_return = monthly_return * 12 - risk_free_rate  # Annualized excess return
            sharpe_ratio = excess_return / volatility if volatility > 0 else 0
            
            return {
                "daily_return": daily_return,
                "weekly_return": weekly_return,
                "monthly_return": monthly_return,
                "volatility": volatility,
                "sharpe_ratio": sharpe_ratio
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {str(e)}")
            return {
                "daily_return": 0,
                "weekly_return": 0,
                "monthly_return": 0,
                "volatility": 0,
                "sharpe_ratio": 0,
                "error": str(e)
            }
    
    async def on_update_balances(self, data):
        """
        Handle balance update event.
        
        Args:
            data: Balance update data
        """
        request_id = data.get("request_id")
        result = await self.update_balances(data)
        
        # Publish result
        self.event_bus.publish("portfolio.update.balances.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_rebalance_request(self, data):
        """
        Handle rebalance request event.
        
        Args:
            data: Rebalance request data
        """
        request_id = data.get("request_id")
        result = await self.rebalance_portfolio()
        
        # Publish result
        self.event_bus.publish("portfolio.rebalance.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_allocation_update(self, data):
        """
        Handle allocation update event.
        
        Args:
            data: Allocation update data
        """
        request_id = data.get("request_id")
        result = await self.update_allocation(data)
        
        # Publish result
        self.event_bus.publish("portfolio.allocation.update.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_portfolio_status(self, data):
        """
        Handle portfolio status request event.
        
        Args:
            data: Status request data
        """
        request_id = data.get("request_id")
        status = await self.get_portfolio_status()
        
        # Publish result
        self.event_bus.publish("portfolio.status.result", {
            "request_id": request_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_market_data_update(self, data):
        """
        Handle market data update event.
        
        Args:
            data: Market data update
        """
        await self.update_asset_prices(data)
    
    async def on_order_filled(self, data):
        """
        Handle order filled event.
        
        Args:
            data: Filled order data
        """
        # Update realized PnL based on filled order
        try:
            market = data.get("market")
            side = data.get("side")
            amount = data.get("filled", data.get("amount", 0))
            price = data.get("average_price", data.get("price", 0))
            
            if not market or not side or not amount or not price:
                return
                
            # Extract asset from market symbol
            asset = market.split("/")[0] if "/" in market else market.split("-")[0]
            
            # Update realized PnL for sells
            if side == "sell" and asset in self.unrealized_pnl:
                cost_basis_per_unit = self.unrealized_pnl[asset].get("cost_basis", 0) / self.portfolio.get(asset, 1)
                realized_pnl = (price - cost_basis_per_unit) * amount
                
                if asset not in self.realized_pnl:
                    self.realized_pnl[asset] = {
                        "realized_pnl": realized_pnl,
                        "trades": 1,
                        "last_updated": datetime.now().isoformat()
                    }
                else:
                    self.realized_pnl[asset]["realized_pnl"] += realized_pnl
                    self.realized_pnl[asset]["trades"] += 1
                    self.realized_pnl[asset]["last_updated"] = datetime.now().isoformat()
                
                logger.info(f"Updated realized PnL for {asset}: {realized_pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating realized PnL: {str(e)}")
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the PortfolioManager component."""
        logger.info("Shutting down PortfolioManager component")
        
        # Stop update task
        self.is_running = False
        if self.update_task and not self.update_task.done():
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        
        # Save final portfolio data
        await self.save_portfolio_data()
        
        # Close HTTP session
        if self.session:
            await self.session.close()
        
        logger.info("PortfolioManager component shut down successfully")
