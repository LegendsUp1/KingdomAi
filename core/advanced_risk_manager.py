"""
Advanced Risk Management System for Perpetual Futures Trading (2025)
Implements state-of-the-art volatility-adjusted position sizing, drawdown controls,
correlation analysis, and liquidation avoidance strategies.
"""

import asyncio
import logging
import time
import json
from typing import Any
import numpy as np
import pandas as pd

from core.base_component import BaseComponent
from utils.redis_client import RedisClient
from utils.async_utils import AsyncSupport

class AdvancedRiskManager(BaseComponent):
    """
    Advanced risk management system for perpetual futures trading that provides
    volatility-adjusted position sizing, drawdown limits, correlation monitoring,
    and liquidation avoidance strategies.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the Advanced Risk Manager component."""
        super().__init__("AdvancedRiskManager", event_bus, config)
        self.redis_client = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.shutdown_event = asyncio.Event()
        
        # Configuration
        self.config = config or {
            "max_portfolio_risk_percent": 2.0,      # Maximum allowed risk per day (% of portfolio)
            "max_position_risk_percent": 0.5,       # Maximum risk per position (% of portfolio)
            "target_daily_volatility": 1.5,         # Target daily volatility (%)
            "max_leverage": 5.0,                    # Maximum allowed leverage across all positions
            "emergency_deleveraging_threshold": 0.8, # % of max leverage to trigger emergency deleveraging
            "volatility_lookback_periods": 20,      # Number of periods for volatility calculation
            "correlation_lookback_days": 30,        # Days to look back for correlation analysis
            "position_sizing_models": ["volbased", "kelly", "adaptive"],
            "max_drawdown_percent": 15.0,           # Maximum allowed drawdown (%)
            "liquidation_buffer_percent": 30.0,     # Buffer from liquidation price (%)
            "risk_bands": [
                {"volatility": 15.0, "max_position_size": 0.8},
                {"volatility": 25.0, "max_position_size": 0.6},
                {"volatility": 35.0, "max_position_size": 0.4},
                {"volatility": 50.0, "max_position_size": 0.2},
                {"volatility": 100.0, "max_position_size": 0.1}
            ],
            "portfolio_heat_threshold": 0.7,        # Portfolio heat threshold (0-1)
            "auto_hedging_enabled": True,           # Enable automatic hedging
            "risk_factor_weights": {
                "volatility": 0.4,
                "correlation": 0.2,
                "liquidity": 0.2,
                "funding_rate": 0.1,
                "momentum": 0.1
            }
        }
        
        # Internal state
        self.portfolio_state = {
            "total_value": 0.0,
            "current_risk": 0.0,
            "positions": {},
            "leverage_used": 0.0,
            "drawdown": 0.0,
            "peak_value": 0.0,
            "heat": 0.0
        }
        
        self.volatility_data = {}
        self.correlation_matrix = None
        self.risk_alerts = []
    
    async def initialize(self):
        """Initialize the component and connect to Redis Quantum Nexus."""
        self.logger.info("Initializing Advanced Risk Manager")
        
        # Connect to Redis Quantum Nexus with strict enforcement
        try:
            self.redis_client = RedisClient(
                host="localhost", 
                port=6380,
                password="QuantumNexus2025",
                db=0,
                decode_responses=True
            )
            # Test connection
            ping_result = await self.redis_client.ping()
            if not ping_result:
                raise ConnectionError("Redis ping failed")
            self.logger.info("Successfully connected to Redis Quantum Nexus")
        except Exception as e:
            self.logger.critical(f"Failed to connect to Redis Quantum Nexus: {e}")
            # Enforcing strict no-fallback policy
            raise SystemExit("Critical failure: Redis Quantum Nexus connection failed. Halting system.")
        
        # Register event handlers (EventBus.subscribe is synchronous)
        if self.event_bus:
            self.event_bus.subscribe("portfolio_update", self.on_portfolio_update)
            self.event_bus.subscribe("position_open_request", self.on_position_open_request)
            self.event_bus.subscribe("position_update", self.on_position_update)
            self.event_bus.subscribe("market_data_update", self.on_market_data_update)
            self.event_bus.subscribe("risk_check_request", self.on_risk_check_request)
            self.event_bus.subscribe("system_shutdown", self.on_shutdown)
        
        # Start background tasks
        AsyncSupport.create_background_task(self.volatility_monitoring_task())
        AsyncSupport.create_background_task(self.correlation_analysis_task())
        AsyncSupport.create_background_task(self.portfolio_risk_assessment_task())
        AsyncSupport.create_background_task(self.liquidation_risk_monitoring_task())
        
        self.logger.info("Advanced Risk Manager initialized successfully")
        return True
    
    # Event handlers
    
    async def on_portfolio_update(self, data):
        """Handle portfolio updates and recalculate risk metrics."""
        try:
            portfolio_value = data.get("total_value")
            positions = data.get("positions", {})
            
            if portfolio_value is None:
                self.logger.warning("Received portfolio update with missing total value")
                return
                
            # Update portfolio state
            old_value = self.portfolio_state["total_value"]
            self.portfolio_state["total_value"] = portfolio_value
            
            # Track peak value for drawdown calculation
            if portfolio_value > self.portfolio_state["peak_value"]:
                self.portfolio_state["peak_value"] = portfolio_value
                
            # Calculate drawdown
            if self.portfolio_state["peak_value"] > 0:
                self.portfolio_state["drawdown"] = (
                    (self.portfolio_state["peak_value"] - portfolio_value) / 
                    self.portfolio_state["peak_value"] * 100.0
                )
            
            # Update positions data
            self.portfolio_state["positions"] = positions
            
            # Calculate total leverage used
            total_notional = sum(position.get("notional_value", 0) for position in positions.values())
            if portfolio_value > 0:
                self.portfolio_state["leverage_used"] = total_notional / portfolio_value
            else:
                self.portfolio_state["leverage_used"] = 0.0
            
            # Calculate portfolio heat (risk utilization)
            self.portfolio_state["heat"] = self.portfolio_state["leverage_used"] / self.config["max_leverage"]
            
            # Check for risk threshold violations
            await self._check_portfolio_risk_thresholds()
            
            # Log significant changes
            if old_value > 0 and abs(portfolio_value - old_value) / old_value > 0.05:
                self.logger.info(f"Significant portfolio value change: {old_value} -> {portfolio_value}")
                
            # Store current state in Redis for monitoring
            await self.redis_client.set(
                "risk:portfolio_state",
                json.dumps(self.portfolio_state),
            )

            # Build portfolio snapshot payload expected by TradingTab
            assets: dict[str, float] = {}
            by_wallet: dict[str, dict[str, Any]] = {}
            stable_usd = 0.0
            stocks_usd = 0.0
            crypto_nonstable_usd = 0.0
            internal_total_usd = 0.0
            external_total_usd = 0.0

            def wallet_type(name: str) -> str:
                lowered = (name or "").lower()
                if lowered.startswith("internal"):
                    return "internal"
                if "internal" in lowered or "treasury" in lowered or "vault" in lowered:
                    return "internal"
                if lowered in {"local", "paper", "sim", "simulation"}:
                    return "internal"
                return "external"

            try:
                for pos in positions.values():
                    if not isinstance(pos, dict):
                        continue
                    sym = pos.get("symbol")
                    if not isinstance(sym, str) or not sym:
                        continue
                    notional = pos.get("notional_value")
                    qty = pos.get("quantity")
                    ex_name = pos.get("exchange")
                    ex_name = str(ex_name) if ex_name is not None else "unknown"
                    try:
                        notional_f = float(notional) if notional is not None else 0.0
                    except (TypeError, ValueError):
                        notional_f = 0.0

                    sym_up = sym.upper()
                    is_stable = sym_up in {"USD", "USDT", "USDC"}
                    usd_value = notional_f
                    if usd_value <= 0.0 and is_stable:
                        try:
                            usd_value = float(qty) if qty is not None else 0.0
                        except (TypeError, ValueError):
                            usd_value = 0.0

                    if usd_value > 0.0:
                        wt = wallet_type(ex_name)
                        entry = by_wallet.get(ex_name)
                        if not isinstance(entry, dict):
                            entry = {
                                "wallet": ex_name,
                                "wallet_type": wt,
                                "total_usd": 0.0,
                                "stable_usd": 0.0,
                                "crypto_nonstable_usd": 0.0,
                                "stocks_usd": 0.0,
                            }
                            by_wallet[ex_name] = entry

                        entry["total_usd"] = float(entry.get("total_usd", 0.0) or 0.0) + usd_value

                        if ex_name.lower() == "alpaca" and not is_stable:
                            stocks_usd += usd_value
                            entry["stocks_usd"] = float(entry.get("stocks_usd", 0.0) or 0.0) + usd_value
                        elif is_stable:
                            stable_usd += usd_value
                            entry["stable_usd"] = float(entry.get("stable_usd", 0.0) or 0.0) + usd_value
                        else:
                            crypto_nonstable_usd += usd_value
                            entry["crypto_nonstable_usd"] = float(entry.get("crypto_nonstable_usd", 0.0) or 0.0) + usd_value

                        if wt == "internal":
                            internal_total_usd += usd_value
                        else:
                            external_total_usd += usd_value

                    if notional_f:
                        assets[sym] = assets.get(sym, 0.0) + notional_f
            except Exception as agg_err:
                self.logger.error(f"Error aggregating portfolio assets for snapshot: {agg_err}")

            total_usd = stable_usd + crypto_nonstable_usd + stocks_usd
            portfolio_snapshot = {
                "timestamp": time.time(),
                "assets": assets,
                "total_usd": total_usd,
                "breakdown": {
                    "stable_usd": stable_usd,
                    "crypto_nonstable_usd": crypto_nonstable_usd,
                    "stocks_usd": stocks_usd,
                    "internal_total_usd": internal_total_usd,
                    "external_total_usd": external_total_usd,
                    "by_wallet": by_wallet,
                },
            }

            # Build risk snapshot payload expected by TradingTab
            # Use a broad dict type because keys mix str labels with float values.
            per_asset: list[dict[str, Any]] = []
            total_exposure = 0.0
            for sym, usd_val in assets.items():
                try:
                    usd_f = float(usd_val)
                except (TypeError, ValueError):
                    continue
                total_exposure += max(usd_f, 0.0)
                per_asset.append(
                    {
                        "asset": sym,
                        "quantity": usd_f,
                        "usd_value": usd_f,
                    }
                )

            risk_snapshot = {
                "timestamp": time.time(),
                "total_exposure": total_exposure,
                "per_asset": per_asset,
                "max_drawdown": self.portfolio_state.get("drawdown"),
                "leverage": self.portfolio_state.get("leverage_used"),
            }

            # Broadcast LIVE risk/portfolio snapshots to all GUI and analytics
            # consumers. This exposes ONLY real, derived data based on the
            # latest portfolio_update event; no mock values.
            try:
                await self.publish_event("trading.portfolio.snapshot", portfolio_snapshot)
                await self.publish_event("trading.risk.snapshot", risk_snapshot)
            except Exception as pub_err:
                self.logger.error(f"Failed to publish risk/portfolio snapshot: {pub_err}")
            
        except Exception as e:
            self.logger.error(f"Error processing portfolio update: {e}")
    
    async def on_position_open_request(self, data):
        """
        Validate position open requests against risk rules.
        Returns approval or rejection with risk assessment.
        """
        try:
            position_id = data.get("position_id")
            symbol = data.get("symbol")
            side = data.get("side")
            size = data.get("size")
            leverage = data.get("leverage", 1.0)
            
            if not all([position_id, symbol, side, size is not None]):
                self.logger.warning(f"Incomplete position open request: {data}")
                await self._reject_position(position_id, "Incomplete request data")
                return
            
            # Get market data for risk assessment
            market_data = await self._get_market_data(symbol)
            if not market_data:
                await self._reject_position(position_id, "Insufficient market data for risk assessment")
                return
            
            # Calculate volatility-adjusted position size
            max_position_size = await self._calculate_max_position_size(symbol, side)
            
            # Check if requested size exceeds the maximum allowed
            if size > max_position_size:
                self.logger.warning(f"Position size {size} exceeds maximum allowed {max_position_size}")
                
                # Suggest adjusted position size
                suggested_size = max_position_size
                
                # Reject with recommendation
                await self._reject_position(
                    position_id, 
                    f"Position size exceeds risk limits. Max allowed: {max_position_size}"
                )
                return
            
            # Check leverage limits
            if leverage > self.config["max_leverage"]:
                await self._reject_position(
                    position_id,
                    f"Leverage {leverage}x exceeds maximum allowed {self.config['max_leverage']}x"
                )
                return
            
            # Check portfolio heat
            estimated_new_heat = self._estimate_new_portfolio_heat(symbol, size, leverage)
            if estimated_new_heat > self.config["portfolio_heat_threshold"]:
                await self._reject_position(
                    position_id,
                    f"Adding position would exceed portfolio risk threshold. Current: {self.portfolio_state['heat']:.2f}, Estimated: {estimated_new_heat:.2f}"
                )
                return
            
            # Calculate liquidation risk
            liquidation_risk = await self._calculate_liquidation_risk(symbol, side, size, leverage)
            if liquidation_risk > 0.2:  # High risk of liquidation
                await self._reject_position(
                    position_id,
                    f"Position has high liquidation risk ({liquidation_risk:.2f}). Consider lower leverage or smaller size."
                )
                return
            
            # If all checks pass, approve the position
            await self._approve_position(position_id, {
                "max_size": max_position_size,
                "approved_size": size,
                "volatility": market_data.get("volatility", 0),
                "liquidation_risk": liquidation_risk
            })
            
        except Exception as e:
            self.logger.error(f"Error processing position open request: {e}")
            if 'position_id' in locals():
                await self._reject_position(position_id, f"Risk assessment error: {str(e)}")
    
    async def on_position_update(self, data):
        """Process position updates to track risk exposure."""
        position_id = data.get("position_id")
        symbol = data.get("symbol")
        current_pnl = data.get("unrealized_pnl")
        liquidation_price = data.get("liquidation_price")
        
        if position_id and symbol:
            # Update position data in portfolio state
            if position_id not in self.portfolio_state["positions"]:
                self.portfolio_state["positions"][position_id] = {}
                
            self.portfolio_state["positions"][position_id].update({
                "symbol": symbol,
                "unrealized_pnl": current_pnl,
                "liquidation_price": liquidation_price,
                "last_updated": time.time()
            })
            
            # Check liquidation risk if we have the necessary data
            if liquidation_price is not None:
                await self._check_liquidation_risk(position_id)
    
    async def on_market_data_update(self, data):
        """Process market data updates for risk calculations."""
        exchange = data.get("exchange")
        symbol = data.get("symbol")
        price = data.get("price")
        
        if not all([exchange, symbol, price]):
            return
            
        # Update volatility data
        key = f"{exchange}:{symbol}"
        if key not in self.volatility_data:
            self.volatility_data[key] = {
                "prices": [],
                "timestamps": [],
                "volatility": None,
                "last_updated": None
            }
        
        # Add new price and timestamp
        self.volatility_data[key]["prices"].append(price)
        self.volatility_data[key]["timestamps"].append(time.time())
        
        # Keep only the lookback period number of data points
        lookback = self.config["volatility_lookback_periods"]
        if len(self.volatility_data[key]["prices"]) > lookback:
            self.volatility_data[key]["prices"] = self.volatility_data[key]["prices"][-lookback:]
            self.volatility_data[key]["timestamps"] = self.volatility_data[key]["timestamps"][-lookback:]
        
        # Update volatility if we have enough data points
        if len(self.volatility_data[key]["prices"]) >= 5:
            prices = np.array(self.volatility_data[key]["prices"])
            returns = np.diff(np.log(prices)) * 100  # Log returns in percentage
            
            # Calculate annualized volatility
            daily_vol = np.std(returns) * np.sqrt(24)  # Assuming hourly data, scale to daily
            self.volatility_data[key]["volatility"] = daily_vol
            self.volatility_data[key]["last_updated"] = time.time()
            
            # Store in Redis for other components to access
            await self.redis_client.hset(
                "risk:volatility", 
                key, 
                str(daily_vol)
            )
    
    async def on_risk_check_request(self, data):
        """Handle on-demand risk check requests."""
        check_type = data.get("check_type")
        parameters = data.get("parameters", {})
        
        results = {}
        
        if check_type == "portfolio":
            results = await self._perform_portfolio_risk_check()
        elif check_type == "position":
            symbol = parameters.get("symbol")
            side = parameters.get("side")
            size = parameters.get("size")
            leverage = parameters.get("leverage", 1.0)
            
            if all([symbol, side, size is not None]):
                results = await self._perform_position_risk_check(symbol, side, size, leverage)
        elif check_type == "correlation":
            symbols = parameters.get("symbols", [])
            results = await self._perform_correlation_check(symbols)
        elif check_type == "drawdown":
            results = await self._perform_drawdown_check()
        
        # Publish results
        if self.event_bus:
            await self.publish_event(
                "risk_check_results",
                {
                    "check_type": check_type,
                    "parameters": parameters,
                    "results": results,
                    "timestamp": time.time(),
                },
            )
    
    async def on_shutdown(self, data):
        """Handle system shutdown."""
        self.logger.info("Shutting down Advanced Risk Manager")
        self.shutdown_event.set()
        if self.redis_client:
            await self.redis_client.close()
    
    # Background monitoring tasks
    
    async def volatility_monitoring_task(self):
        """Monitor volatility changes and update risk parameters."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Running volatility monitoring task")
                
                for key, data in self.volatility_data.items():
                    if data["volatility"] is not None:
                        # Check for volatility spikes
                        if len(data["prices"]) > 5:
                            recent_prices = data["prices"][-5:]
                            recent_returns = np.diff(np.log(recent_prices)) * 100
                            recent_vol = np.std(recent_returns) * np.sqrt(24)
                            
                            vol_ratio = recent_vol / data["volatility"] if data["volatility"] > 0 else 1.0
                            
                            # Alert if recent volatility is significantly higher
                            if vol_ratio > 1.5:  # 50% increase in volatility
                                exchange, symbol = key.split(":")
                                alert = {
                                    "type": "volatility_spike",
                                    "exchange": exchange,
                                    "symbol": symbol,
                                    "volatility": recent_vol,
                                    "increase": f"{(vol_ratio-1)*100:.2f}%",
                                    "timestamp": time.time()
                                }
                                
                                self.risk_alerts.append(alert)
                                
                                # Publish alert
                                if self.event_bus:
                                    await self.publish_event("risk_alert", alert)
                
                await asyncio.sleep(60)  # Check every minute
                
        except asyncio.CancelledError:
            self.logger.info("Volatility monitoring task cancelled")
        except Exception as e:
            self.logger.error(f"Error in volatility monitoring task: {e}")
    
    async def correlation_analysis_task(self):
        """Analyze correlations between assets for portfolio diversification."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Running correlation analysis task")
                
                # Get all symbols in portfolio
                symbols = []
                for position in self.portfolio_state["positions"].values():
                    symbol = position.get("symbol")
                    if symbol and symbol not in symbols:
                        symbols.append(symbol)
                
                if len(symbols) >= 2:
                    # Calculate correlation matrix
                    returns_data = {}
                    
                    # Get price history for each symbol
                    for symbol in symbols:
                        history = await self._get_price_history(symbol)
                        if history and len(history) > 5:
                            prices = np.array(history)
                            returns = np.diff(np.log(prices)) * 100
                            returns_data[symbol] = returns
                    
                    if len(returns_data) >= 2:
                        # Create DataFrame for correlation calculation
                        df = pd.DataFrame(returns_data)
                        self.correlation_matrix = df.corr()
                        
                        # Store in Redis
                        await self.redis_client.set(
                            "risk:correlation_matrix", 
                            self.correlation_matrix.to_json()
                        )
                        
                        # Check for high correlations
                        high_correlations = []
                        for i, s1 in enumerate(self.correlation_matrix.index):
                            for j, s2 in enumerate(self.correlation_matrix.columns):
                                if i < j:
                                    corr = self.correlation_matrix.iloc[i, j]
                                    if abs(corr) > 0.8:  # High correlation threshold
                                        high_correlations.append({
                                            "symbol1": s1,
                                            "symbol2": s2,
                                            "correlation": corr
                                        })
                        
                        # Alert for concerning correlations
                        if high_correlations and self.event_bus:
                            await self.publish_event(
                                "risk_alert",
                                {
                                    "type": "high_correlation",
                                    "correlations": high_correlations,
                                    "timestamp": time.time(),
                                },
                            )
                
                await asyncio.sleep(3600)  # Run every hour
                
        except asyncio.CancelledError:
            self.logger.info("Correlation analysis task cancelled")
        except Exception as e:
            self.logger.error(f"Error in correlation analysis task: {e}")
    
    async def portfolio_risk_assessment_task(self):
        """Continuously assess overall portfolio risk metrics."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Running portfolio risk assessment")
                
                # Check for drawdown limits
                if self.portfolio_state["drawdown"] > self.config["max_drawdown_percent"]:
                    alert = {
                        "type": "excessive_drawdown",
                        "drawdown": self.portfolio_state["drawdown"],
                        "threshold": self.config["max_drawdown_percent"],
                        "timestamp": time.time()
                    }
                    
                    self.risk_alerts.append(alert)
                    
                    # Publish alert
                    if self.event_bus:
                        await self.publish_event("risk_alert", alert)
                
                # Check for excess leverage
                if self.portfolio_state["leverage_used"] > self.config["emergency_deleveraging_threshold"] * self.config["max_leverage"]:
                    alert = {
                        "type": "excess_leverage",
                        "current_leverage": self.portfolio_state["leverage_used"],
                        "max_allowed": self.config["max_leverage"],
                        "threshold": self.config["emergency_deleveraging_threshold"] * self.config["max_leverage"],
                        "timestamp": time.time()
                    }
                    
                    self.risk_alerts.append(alert)
                    
                    # Publish alert
                    if self.event_bus:
                        await self.publish_event("risk_alert", alert)

                        # Also trigger emergency deleveraging
                        await self.publish_event(
                            "emergency_deleveraging",
                            {
                                "current_leverage": self.portfolio_state["leverage_used"],
                                "target_leverage": self.config["max_leverage"] * 0.7,
                                "timestamp": time.time(),
                            },
                        )
                
                await asyncio.sleep(60)  # Check every minute
                
        except asyncio.CancelledError:
            self.logger.info("Portfolio risk assessment task cancelled")
        except Exception as e:
            self.logger.error(f"Error in portfolio risk assessment task: {e}")
    
    async def liquidation_risk_monitoring_task(self):
        """Monitor positions for liquidation risk and provide warnings."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Monitoring liquidation risk")
                
                for position_id, position in self.portfolio_state["positions"].items():
                    await self._check_liquidation_risk(position_id)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
        except asyncio.CancelledError:
            self.logger.info("Liquidation risk monitoring task cancelled")
        except Exception as e:
            self.logger.error(f"Error in liquidation risk monitoring task: {e}")
    
    # Helper methods
    
    async def _approve_position(self, position_id, details):
        """Approve a position open request."""
        if self.event_bus:
            await self.publish_event(
                "position_risk_approved",
                {
                    "position_id": position_id,
                    "details": details,
                    "timestamp": time.time(),
                },
            )
    
    async def _reject_position(self, position_id, reason):
        """Reject a position open request due to risk rules."""
        if self.event_bus:
            await self.publish_event(
                "position_risk_rejected",
                {
                    "position_id": position_id,
                    "reason": reason,
                    "timestamp": time.time(),
                },
            )
    
    async def _check_portfolio_risk_thresholds(self):
        """Check if portfolio risk thresholds are violated."""
        try:
            portfolio_heat = self.portfolio_state.get("portfolio_heat", 0)
            max_heat = self.config.get("max_portfolio_heat", 0.8)
            positions = self.portfolio_state.get("positions", {})
            total_notional = sum(p.get("notional_value", 0) for p in positions.values())
            max_notional = self.config.get("max_total_notional", 1_000_000)
            violations = []
            if portfolio_heat > max_heat:
                violations.append(f"Portfolio heat {portfolio_heat:.2f} exceeds max {max_heat}")
            if total_notional > max_notional:
                violations.append(f"Total notional ${total_notional:,.0f} exceeds max ${max_notional:,.0f}")
            for sym, pos in positions.items():
                unrealized_pnl_pct = pos.get("unrealized_pnl_pct", 0)
                max_loss_pct = self.config.get("max_position_loss_pct", -10)
                if unrealized_pnl_pct < max_loss_pct:
                    violations.append(f"{sym} loss {unrealized_pnl_pct:.1f}% exceeds max {max_loss_pct}%")
            if violations:
                logger.warning(f"Risk threshold violations: {violations}")
                if self.event_bus:
                    self.event_bus.publish("risk.threshold.violated", {"violations": violations})
        except Exception as e:
            logger.error(f"Portfolio risk check error: {e}")
    
    async def _calculate_max_position_size(self, symbol, side):
        """
        Calculate maximum allowed position size based on volatility,
        portfolio value, and risk limits.
        """
        # Get current volatility for the symbol
        volatility = await self._get_volatility(symbol)
        
        # Default to maximum volatility if not available
        if volatility is None:
            volatility = 100.0  # Very high default volatility (conservative)
        
        # Find the appropriate risk band based on volatility
        max_position_size_factor = 0.1  # Default to the most conservative
        for band in self.config["risk_bands"]:
            if volatility <= band["volatility"]:
                max_position_size_factor = band["max_position_size"]
                break
        
        # Calculate maximum position size based on portfolio value and risk factor
        portfolio_value = self.portfolio_state["total_value"]
        max_position_size = portfolio_value * max_position_size_factor
        
        # Adjust for current portfolio heat
        heat_adjustment = max(0, 1 - self.portfolio_state["heat"])
        max_position_size *= heat_adjustment
        
        return max_position_size
    
    async def _get_volatility(self, symbol):
        """Get current volatility for a symbol."""
        # Check if we have volatility data for this symbol
        for key, data in self.volatility_data.items():
            if symbol in key and data["volatility"] is not None:
                return data["volatility"]
        
        # If not found in memory, try to get from Redis
        try:
            for exchange in ["binance", "okx", "bybit", "deribit", "gate"]:
                key = f"{exchange}:{symbol}"
                vol_str = await self.redis_client.hget("risk:volatility", key)
                if vol_str:
                    return float(vol_str)
        except Exception as e:
            self.logger.error(f"Error fetching volatility from Redis: {e}")
        
        return None
    
    async def _get_market_data(self, symbol):
        """Get market data for a symbol."""
        # Implementation would fetch market data for risk assessment
        return {"volatility": await self._get_volatility(symbol)}
    
    async def _calculate_liquidation_risk(self, symbol, side, size, leverage):
        """Calculate risk of liquidation for a proposed position."""
        # In a real implementation, this would:
        # 1. Get current price and volatility
        # 2. Estimate liquidation price
        # 3. Calculate probability of hitting liquidation price
        
        # Simplified implementation
        volatility = await self._get_volatility(symbol) or 30.0  # Default to high volatility
        
        # Higher volatility and leverage means higher liquidation risk
        liquidation_risk = (volatility / 100.0) * (leverage / self.config["max_leverage"])
        
        return min(1.0, liquidation_risk)  # Risk score between 0-1
    
    async def _check_liquidation_risk(self, position_id):
        """Check if a position is at risk of liquidation."""
        position = self.portfolio_state["positions"].get(position_id)
        if not position:
            return
            
        symbol = position.get("symbol")
        current_price = position.get("current_price")
        liquidation_price = position.get("liquidation_price")
        
        if not all([symbol, current_price, liquidation_price]):
            return
            
        # Calculate price distance to liquidation as percentage
        price_distance = abs(current_price - liquidation_price) / current_price * 100.0
        
        # Get current volatility
        volatility = await self._get_volatility(symbol) or 30.0
        
        # Check if the position is at risk (price within volatility range of liquidation)
        if price_distance < (volatility * self.config["liquidation_buffer_percent"] / 100.0):
            alert = {
                "type": "liquidation_risk",
                "position_id": position_id,
                "symbol": symbol,
                "current_price": current_price,
                "liquidation_price": liquidation_price,
                "price_distance_percent": price_distance,
                "timestamp": time.time()
            }
            
            self.risk_alerts.append(alert)
            
            # Publish alert
            if self.event_bus:
                await self.publish_event("risk_alert", alert)
    
    async def _get_price_history(self, symbol):
        """Get price history for a symbol from Redis or exchange."""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6380, password='QuantumNexus2025', decode_responses=True)
            cached = r.get(f"price_history:{symbol}")
            if cached:
                import json
                return json.loads(cached)
        except Exception:
            pass
        try:
            import ccxt
            exchange = ccxt.binance({'enableRateLimit': True})
            ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=168)
            return [{"timestamp": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]} for c in ohlcv]
        except Exception as e:
            logger.debug(f"Price history fetch failed for {symbol}: {e}")
            return []
    
    def _estimate_new_portfolio_heat(self, symbol, size, leverage):
        """Estimate portfolio heat if a new position is added."""
        current_notional = sum(p.get("notional_value", 0) for p in self.portfolio_state["positions"].values())
        new_notional = current_notional + (size * leverage)
        
        if self.portfolio_state["total_value"] > 0:
            new_leverage = new_notional / self.portfolio_state["total_value"]
            new_heat = new_leverage / self.config["max_leverage"]
            return new_heat
        
        return 1.0  # Assume maximum heat if portfolio value is zero
    
    async def _perform_portfolio_risk_check(self):
        """Perform comprehensive portfolio risk check."""
        # Implementation would assess overall portfolio risk
        return {
            "drawdown": self.portfolio_state["drawdown"],
            "leverage": self.portfolio_state["leverage_used"],
            "heat": self.portfolio_state["heat"],
            "diversification_score": await self._calculate_diversification_score()
        }
    
    async def _perform_position_risk_check(self, symbol, side, size, leverage):
        """Perform risk check for a specific position."""
        # Implementation would check position-specific risks
        return {
            "max_allowed_size": await self._calculate_max_position_size(symbol, side),
            "liquidation_risk": await self._calculate_liquidation_risk(symbol, side, size, leverage),
            "volatility": await self._get_volatility(symbol)
        }
    
    async def _perform_correlation_check(self, symbols):
        """Check correlations between specified symbols."""
        # Implementation would check correlations
        cm = self.correlation_matrix
        if cm is None or len(symbols) < 2:
            return {}

        correlations: dict[str, float] = {}
        for i, s1 in enumerate(symbols):
            for j, s2 in enumerate(symbols):
                if i < j and s1 in cm.index and s2 in cm.columns:
                    key = f"{s1}/{s2}"
                    correlations[key] = float(cm.loc[s1, s2])

        return correlations
    
    async def _perform_drawdown_check(self):
        """Check current drawdown against limits."""
        return {
            "current_drawdown": self.portfolio_state["drawdown"],
            "max_allowed": self.config["max_drawdown_percent"],
            "status": "OK" if self.portfolio_state["drawdown"] <= self.config["max_drawdown_percent"] else "ALERT"
        }
    
    async def _calculate_diversification_score(self):
        """Calculate portfolio diversification score based on correlations and position sizes."""
        try:
            positions = self.portfolio_state.get("positions", {})
            if not positions or len(positions) < 2:
                return 1.0 / max(1, len(positions)) if positions else 0.0

            values = [abs(p.get("value", 0)) for p in (
                positions.values() if isinstance(positions, dict) else positions
            )]
            total = sum(values)
            if total == 0:
                return 0.0

            weights = [v / total for v in values]
            hhi = sum(w ** 2 for w in weights)
            n = len(weights)
            position_diversity = 1.0 - hhi

            corr_penalty = 0.0
            cm = self.correlation_matrix
            if cm is not None and len(cm) >= 2:
                import numpy as _np
                mask = ~_np.eye(len(cm), dtype=bool)
                avg_abs_corr = float(_np.abs(cm.values[mask]).mean()) if hasattr(cm, 'values') else 0.0
                corr_penalty = avg_abs_corr * 0.5

            score = max(0.0, min(1.0, position_diversity - corr_penalty))
            return score
        except Exception:
            return 0.5
