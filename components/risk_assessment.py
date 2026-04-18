"""
Kingdom AI - Risk Assessment Core

This module provides risk assessment capabilities for the Kingdom AI system.
It integrates with the trading system and other components to provide advanced
risk management and analysis.
"""

import logging
import asyncio
import time
import json
import os
from typing import Dict, List, Any, Optional, Union

from core.base_component import BaseComponent
from core.event_bus import EventBus

# Configure logging
logger = logging.getLogger("KingdomAI.RiskAssessment")

class RiskAssessmentCore(BaseComponent):
    """Risk Assessment Core for Kingdom AI.
    
    This component analyzes trading strategies, market conditions, and
    portfolio composition to provide risk assessment and management.
    """
    
    def __init__(self, name="risk_assessment", event_bus=None):
        """Initialize the Risk Assessment Core.
        
        Args:
            name: Component name
            event_bus: Event bus for inter-component communication
        """
        super().__init__(name=name, event_bus=event_bus)
        self.logger = logger
        
        # Risk metrics
        self.risk_metrics = {
            "volatility": 0.0,
            "var": 0.0,  # Value at Risk
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "risk_level": "medium"
        }
        
        # Risk thresholds
        self.risk_thresholds = {
            "max_position_size": 0.1,  # 10% of portfolio
            "max_leverage": 2.0,
            "stop_loss_percent": 0.05,  # 5%
            "take_profit_ratio": 3.0    # 3:1 reward/risk ratio
        }
        
        # Portfolio risk
        self.portfolio_risk = {
            "total_exposure": 0.0,
            "sector_concentration": {},
            "currency_exposure": {}
        }
        
        # Risk assessment status
        self.status = "initializing"
        
    async def initialize(self):
        """Initialize the Risk Assessment Core."""
        self.logger.info("Initializing Risk Assessment Core...")
        
        # Register event handlers
        if self.event_bus:
            self.event_bus.subscribe("portfolio.update", self.handle_portfolio_update)
            self.event_bus.subscribe("market.data", self.handle_market_data)
            self.event_bus.subscribe("trading.strategy.select", self.assess_strategy_risk)
            self.event_bus.subscribe("risk.threshold.update", self.update_risk_thresholds)
            self.event_bus.subscribe("risk.assessment.request", self.perform_risk_assessment)
            
        # Load risk configuration
        await self._load_risk_configuration()
        
        # Set status to ready
        self.status = "ready"
        self.logger.info("Risk Assessment Core initialized")
        
        # Publish status
        if self.event_bus:
            await self.event_bus.publish("risk.status", {
                "status": self.status,
                "metrics": self.risk_metrics
            })
    
    async def _load_risk_configuration(self):
        """Load risk configuration from file or use defaults."""
        try:
            config_path = os.path.join("config", "risk_assessment.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                    
                # Update thresholds from config
                if "thresholds" in config:
                    self.risk_thresholds.update(config["thresholds"])
                    
                self.logger.info("Loaded risk configuration")
            else:
                self.logger.warning("Risk configuration file not found, using defaults")
                
        except Exception as e:
            self.logger.error(f"Error loading risk configuration: {e}")
    
    async def handle_portfolio_update(self, event_type: str, data: Dict[str, Any]):
        """Handle portfolio updates.
        
        Args:
            event_type: Event type
            data: Portfolio data
        """
        try:
            # Update portfolio risk metrics
            if "positions" in data:
                # Calculate total exposure
                total_exposure = sum(position["value"] for position in data["positions"])
                self.portfolio_risk["total_exposure"] = total_exposure
                
                # Calculate sector and currency exposure
                sectors = {}
                currencies = {}
                for position in data["positions"]:
                    # Sector concentration
                    sector = position.get("sector", "unknown")
                    sectors[sector] = sectors.get(sector, 0) + position["value"]
                    
                    # Currency exposure
                    currency = position.get("currency", "unknown")
                    currencies[currency] = currencies.get(currency, 0) + position["value"]
                
                # Normalize to percentages
                if total_exposure > 0:
                    self.portfolio_risk["sector_concentration"] = {
                        sector: value / total_exposure for sector, value in sectors.items()
                    }
                    self.portfolio_risk["currency_exposure"] = {
                        currency: value / total_exposure for currency, value in currencies.items()
                    }
                
            # Recalculate risk metrics
            await self.perform_risk_assessment("portfolio.update", {})
            
        except Exception as e:
            self.logger.error(f"Error handling portfolio update: {e}")
    
    async def handle_market_data(self, event_type: str, data: Dict[str, Any]):
        """Handle market data updates.
        
        Args:
            event_type: Event type
            data: Market data
        """
        try:
            # Update volatility based on market data
            if "volatility" in data:
                self.risk_metrics["volatility"] = data["volatility"]
                
            # Recalculate risk level if needed
            if data.get("significant_change", False):
                self._calculate_risk_level()
                
        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")
    
    async def assess_strategy_risk(self, event_type: str, data: Dict[str, Any]):
        """Assess risk of a trading strategy.
        
        Args:
            event_type: Event type
            data: Strategy data
        """
        try:
            strategy_id = data.get("strategy_id")
            if not strategy_id:
                return
                
            # Calculate strategy risk metrics
            risk_assessment = {
                "strategy_id": strategy_id,
                "risk_level": "medium",  # Default
                "expected_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "recommendation": "proceed"
            }
            
            # Perform actual assessment based on strategy parameters
            params = data.get("parameters", {})
            
            # Assess leverage
            if "leverage" in params:
                leverage = params["leverage"]
                if leverage > self.risk_thresholds["max_leverage"]:
                    risk_assessment["risk_level"] = "high"
                    risk_assessment["recommendation"] = "reduce_leverage"
            
            # Assess position sizing
            if "position_size" in params:
                position_size = params["position_size"]
                if position_size > self.risk_thresholds["max_position_size"]:
                    risk_assessment["risk_level"] = "high"
                    risk_assessment["recommendation"] = "reduce_position_size"
            
            # Publish risk assessment results
            if self.event_bus:
                await self.event_bus.publish("risk.strategy.assessment", {
                    "strategy_id": strategy_id,
                    "assessment": risk_assessment
                })
                
        except Exception as e:
            self.logger.error(f"Error assessing strategy risk: {e}")
    
    async def update_risk_thresholds(self, event_type: str, data: Dict[str, Any]):
        """Update risk thresholds.
        
        Args:
            event_type: Event type
            data: New threshold values
        """
        try:
            # Update thresholds
            for key, value in data.items():
                if key in self.risk_thresholds:
                    self.risk_thresholds[key] = value
            
            # Save updated thresholds
            config_path = os.path.join("config", "risk_assessment.json")
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, "w") as f:
                json.dump({"thresholds": self.risk_thresholds}, f, indent=2)
                
            self.logger.info("Updated risk thresholds")
            
        except Exception as e:
            self.logger.error(f"Error updating risk thresholds: {e}")
    
    async def perform_risk_assessment(self, event_type: str, data: Dict[str, Any]):
        """Perform comprehensive risk assessment.
        
        Args:
            event_type: Event type
            data: Assessment request data
        """
        try:
            # Calculate Value at Risk (VaR)
            confidence_level = data.get("confidence_level", 0.95)
            self.risk_metrics["var"] = self._calculate_value_at_risk(confidence_level)
            
            # Calculate maximum drawdown
            self.risk_metrics["max_drawdown"] = self._calculate_max_drawdown()
            
            # Calculate Sharpe ratio
            self.risk_metrics["sharpe_ratio"] = self._calculate_sharpe_ratio()
            
            # Determine overall risk level
            self._calculate_risk_level()
            
            # Publish updated risk metrics
            if self.event_bus:
                await self.event_bus.publish("risk.metrics.update", {
                    "metrics": self.risk_metrics,
                    "portfolio_risk": self.portfolio_risk
                })
                
        except Exception as e:
            self.logger.error(f"Error performing risk assessment: {e}")
    
    def _calculate_value_at_risk(self, confidence_level: float) -> float:
        """Calculate Value at Risk (VaR).
        
        Args:
            confidence_level: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            Value at Risk
        """
        # Simplified VaR calculation
        # In a real implementation, this would use historical returns or Monte Carlo simulation
        if self.portfolio_risk["total_exposure"] > 0 and self.risk_metrics["volatility"] > 0:
            # Use volatility and a z-score for the confidence level
            if confidence_level == 0.95:
                z_score = 1.645
            elif confidence_level == 0.99:
                z_score = 2.326
            else:
                z_score = 1.0
                
            return self.portfolio_risk["total_exposure"] * self.risk_metrics["volatility"] * z_score
        return 0.0
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown.
        
        Returns:
            Maximum drawdown as a percentage
        """
        # In a real implementation, this would analyze historical portfolio values
        # Here, we're using a simplified model based on volatility
        return min(0.8, self.risk_metrics["volatility"] * 2.0)
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio.
        
        Returns:
            Sharpe ratio
        """
        # Simplified Sharpe ratio calculation
        # In a real implementation, this would use historical returns and standard deviation
        risk_free_rate = 0.02  # 2% risk-free rate
        expected_return = 0.10  # 10% expected return
        
        if self.risk_metrics["volatility"] > 0:
            return (expected_return - risk_free_rate) / self.risk_metrics["volatility"]
        return 0.0
    
    def _calculate_risk_level(self):
        """Calculate overall risk level based on metrics."""
        # Determine risk level based on multiple factors
        var_threshold_high = 0.10  # 10% VaR
        var_threshold_medium = 0.05  # 5% VaR
        
        drawdown_threshold_high = 0.20  # 20% max drawdown
        drawdown_threshold_medium = 0.10  # 10% max drawdown
        
        sharpe_threshold_low = 1.0
        sharpe_threshold_medium = 1.5
        
        # Count risk factors
        high_risk_factors = 0
        medium_risk_factors = 0
        
        # Check VaR
        if self.risk_metrics["var"] >= var_threshold_high:
            high_risk_factors += 1
        elif self.risk_metrics["var"] >= var_threshold_medium:
            medium_risk_factors += 1
            
        # Check max drawdown
        if self.risk_metrics["max_drawdown"] >= drawdown_threshold_high:
            high_risk_factors += 1
        elif self.risk_metrics["max_drawdown"] >= drawdown_threshold_medium:
            medium_risk_factors += 1
            
        # Check Sharpe ratio
        if self.risk_metrics["sharpe_ratio"] <= sharpe_threshold_low:
            high_risk_factors += 1
        elif self.risk_metrics["sharpe_ratio"] <= sharpe_threshold_medium:
            medium_risk_factors += 1
            
        # Determine overall risk level
        if high_risk_factors >= 2:
            self.risk_metrics["risk_level"] = "high"
        elif high_risk_factors >= 1 or medium_risk_factors >= 2:
            self.risk_metrics["risk_level"] = "medium"
        else:
            self.risk_metrics["risk_level"] = "low"
            
        self.logger.debug(f"Risk level calculated: {self.risk_metrics['risk_level']}")
