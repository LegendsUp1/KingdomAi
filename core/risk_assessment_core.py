#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RiskAssessmentCore component for the Kingdom AI trading system.
Provides comprehensive risk assessment and management capabilities.
"""

import logging
import asyncio
import traceback
from typing import Dict, List, Any, Optional

logger = logging.getLogger("kingdom.RiskAssessmentCore")

class RiskAssessmentCore:
    """
    Core component for risk assessment in the Kingdom AI trading system.
    Evaluates trading risks, portfolio exposure, and provides risk metrics.
    """
    
    def __init__(self, event_bus=None):
        """
        Initialize the RiskAssessmentCore component.
        
        Args:
            event_bus: Optional event bus for component communication
        """
        self.name = "RiskAssessmentCore"
        self.event_bus = event_bus
        self.config = {}
        self.risk_models = {}
        self.is_initialized = False
        self.subscribers = {}
        logger.info(f"{self.name} component created")
        
    def set_event_bus(self, event_bus):
        """Set the event bus for this component"""
        self.event_bus = event_bus
        logger.info(f"Event bus set for {self.name}")
        return self
        
    def set_config(self, config: Dict[str, Any]):
        """Set configuration for this component"""
        self.config = config
        logger.info(f"Configuration set for {self.name}")
        return self
        
    async def initialize(self):
        """Initialize the risk assessment core component"""
        logger.info(f"Initializing {self.name}")
        # Register event handlers
        if self.event_bus:
            try:
                await self.event_bus.subscribe("trading.order.new", self._handle_new_order)
                await self.event_bus.subscribe("portfolio.update", self._handle_portfolio_update)
                await self.event_bus.subscribe("market.volatility_change", self._handle_volatility_change)
                await self.event_bus.subscribe("system.risk.assess", self._handle_risk_assessment_request)
                logger.info("Subscribed to event bus events")
            except Exception as e:
                logger.error(f"Error subscribing to events: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Initialize risk models
        self._initialize_risk_models()
        
        self.is_initialized = True
        logger.info(f"{self.name} initialized")
        return self
    
    # Alias methods for compatibility
    async def init(self):
        """Alias for initialize() to maintain compatibility"""
        return await self.initialize()
    
    async def setup(self):
        """Set up risk models and parameters - alias for initialize()"""
        return await self.initialize()
    
    def _initialize_risk_models(self):
        """Initialize all risk models"""
        logger.info(f"Setting up risk models for {self.name}")
        
        try:
            # Initialize risk models
            self.risk_models = {
                "var": self._initialize_var_model(),
                "exposure": self._initialize_exposure_model(),
                "correlation": self._initialize_correlation_model(),
                "liquidity": self._initialize_liquidity_model(),
                "volatility": self._initialize_volatility_model()
            }
            logger.info(f"Risk models initialized: {', '.join(self.risk_models.keys())}")
        except Exception as e:
            logger.error(f"Error initializing risk models: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def assess_trade_risk(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess the risk of a trade order
        
        Args:
            order_data: Dictionary containing order details
            
        Returns:
            Dictionary of risk assessment results
        """
        logger.info(f"Assessing trade risk for order: {order_data.get('order_id', 'unknown')}")
        
        try:
            risk_assessment = {
                "order_id": order_data.get("order_id"),
                "risk_level": self._calculate_risk_level(order_data),
                "portfolio_impact": self._calculate_portfolio_impact(order_data),
                "max_drawdown": self._calculate_max_drawdown(order_data),
                "volatility_exposure": self._calculate_volatility_exposure(order_data),
                "recommendation": self._generate_risk_recommendation(order_data)
            }
            
            return risk_assessment
        except Exception as e:
            logger.error(f"Error assessing trade risk: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "order_id": order_data.get("order_id"),
                "error": str(e),
                "risk_level": 1.0,  # High risk due to error
                "recommendation": "Unable to assess risk - proceed with caution"
            }
    
    async def assess_portfolio_risk(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess the overall risk of a portfolio
        
        Args:
            portfolio_data: Dictionary containing portfolio details
            
        Returns:
            Dictionary of portfolio risk assessment results
        """
        logger.info("Assessing portfolio risk")
        
        try:
            risk_assessment = {
                "portfolio_id": portfolio_data.get("portfolio_id"),
                "total_risk_score": self._calculate_portfolio_risk_score(portfolio_data),
                "diversification_score": self._calculate_diversification_score(portfolio_data),
                "correlation_risk": self._calculate_correlation_risk(portfolio_data),
                "market_exposure": self._calculate_market_exposure(portfolio_data),
                "recommendations": self._generate_portfolio_recommendations(portfolio_data)
            }
            
            return risk_assessment
        except Exception as e:
            logger.error(f"Error assessing portfolio risk: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "portfolio_id": portfolio_data.get("portfolio_id"),
                "error": str(e),
                "total_risk_score": 0.75,  # High risk due to error
                "recommendations": ["Unable to fully assess portfolio risk - proceed with caution"]
            }
    
    # Event handlers
    
    async def _handle_new_order(self, event_data: Dict[str, Any]):
        """Handle new order events for risk assessment"""
        logger.info(f"Handling new order for risk assessment: {event_data.get('order_id', 'unknown')}")
        
        try:
            risk_assessment = await self.assess_trade_risk(event_data)
            
            # Publish risk assessment results
            await self._publish_risk_assessment(risk_assessment)
            
            # If high risk, publish warning
            if risk_assessment["risk_level"] > 0.7:  # 70% risk threshold
                await self._publish_risk_warning(risk_assessment)
                
        except Exception as e:
            logger.error(f"Error handling new order for risk assessment: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _handle_portfolio_update(self, event_data: Dict[str, Any]):
        """Handle portfolio update events"""
        logger.info("Handling portfolio update for risk assessment")
        
        try:
            risk_assessment = await self.assess_portfolio_risk(event_data)
            await self._publish_portfolio_risk_assessment(risk_assessment)
            
        except Exception as e:
            logger.error(f"Error handling portfolio update for risk assessment: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _handle_volatility_change(self, event_data: Dict[str, Any]):
        """Handle market volatility change events"""
        logger.info(f"Handling market volatility change: {event_data.get('market', 'unknown')}")
        
        try:
            # Update volatility model
            market = event_data.get("market", "unknown")
            volatility = event_data.get("volatility", 0.0)
            
            if "volatility" in self.risk_models:
                self.risk_models["volatility"]["markets"][market] = volatility
                
                # Reassess portfolio risk if significant change
                if volatility > self.risk_models["volatility"].get("threshold", 0.2):
                    await self._publish_status("reassessing_portfolio")
                    # Request portfolio data
                    await self._request_portfolio_data()
                    
        except Exception as e:
            logger.error(f"Error handling volatility change: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _handle_risk_assessment_request(self, event_data: Dict[str, Any]):
        """Handle explicit risk assessment requests"""
        logger.info(f"Handling risk assessment request: {event_data.get('request_id', 'unknown')}")
        
        try:
            request_type = event_data.get("type", "unknown")
            request_id = event_data.get("request_id", "unknown")
            
            if request_type == "trade":
                risk_assessment = await self.assess_trade_risk(event_data.get("data", {}))
                await self._publish_risk_assessment(risk_assessment, request_id)
                
            elif request_type == "portfolio":
                risk_assessment = await self.assess_portfolio_risk(event_data.get("data", {}))
                await self._publish_portfolio_risk_assessment(risk_assessment, request_id)
                
            else:
                logger.warning(f"Unknown risk assessment request type: {request_type}")
                
        except Exception as e:
            logger.error(f"Error handling risk assessment request: {str(e)}")
            logger.error(traceback.format_exc())
    
    # Utility methods for risk models
    
    def _initialize_var_model(self) -> Dict[str, Any]:
        """Initialize Value at Risk model"""
        return {
            "confidence_level": 0.95,
            "time_horizon": 1,  # days
            "historical_window": 252,  # trading days
            "method": "historical"
        }
    
    def _initialize_exposure_model(self) -> Dict[str, Any]:
        """Initialize exposure model"""
        return {
            "max_single_asset": 0.2,  # 20% max exposure to single asset
            "max_sector": 0.3,  # 30% max exposure to single sector
            "max_correlation": 0.7  # 70% max correlation between assets
        }
    
    def _initialize_correlation_model(self) -> Dict[str, Any]:
        """Initialize correlation model"""
        return {
            "window_size": 90,  # 90-day correlation window
            "min_data_points": 30,
            "threshold": 0.7  # Correlation threshold for warnings
        }
    
    def _initialize_liquidity_model(self) -> Dict[str, Any]:
        """Initialize liquidity risk model"""
        return {
            "max_days_to_liquidate": 3,
            "market_impact_threshold": 0.05,
            "volume_factor": 0.1  # Trade at 10% of daily volume
        }
    
    def _initialize_volatility_model(self) -> Dict[str, Any]:
        """Initialize volatility model"""
        return {
            "window_size": 30,  # 30-day volatility window
            "threshold": 0.2,  # Volatility threshold for reassessment
            "markets": {}  # Will store market volatilities
        }
    
    def _calculate_risk_level(self, order_data: Dict[str, Any]) -> float:
        """Calculate the risk level of a trade (0.0-1.0 scale)"""
        try:
            # Basic calculation based on order size relative to portfolio
            portfolio_value = order_data.get("portfolio_value", 100000)
            order_value = order_data.get("order_value", 1000)
            
            # Calculate as percentage of portfolio (normalized to 0-1)
            size_risk = min(1.0, order_value / (portfolio_value * 0.2))
            
            # Factor in market conditions if available
            market_volatility = order_data.get("market_volatility", 0.2)
            volatility_factor = market_volatility / 0.2  # Normalize to typical volatility
            
            # Combine factors
            risk_level = (size_risk * 0.6) + (volatility_factor * 0.4)
            return min(1.0, max(0.0, risk_level))
        except Exception as e:
            logger.error(f"Error calculating risk level: {str(e)}")
            return 0.5  # Medium risk as fallback
    
    def _calculate_portfolio_impact(self, order_data: Dict[str, Any]) -> float:
        """Calculate the impact of a trade on the portfolio (0.0-1.0 scale)"""
        try:
            # Get relevant data with defaults for safety
            portfolio_value = order_data.get("portfolio_value", 100000)
            order_value = order_data.get("order_value", 1000)
            
            # Basic impact calculation as percentage of portfolio
            impact = order_value / portfolio_value
            return min(1.0, impact * 5)  # Scale up for better visualization (5x)
        except Exception as e:
            logger.error(f"Error calculating portfolio impact: {str(e)}")
            return 0.2  # Low-medium impact as fallback
    
    def _calculate_max_drawdown(self, order_data: Dict[str, Any]) -> float:
        """Calculate the maximum potential drawdown from a trade (0.0-1.0 scale)"""
        try:
            # Get relevant data with defaults for safety
            market_volatility = order_data.get("market_volatility", 0.2)
            leverage = order_data.get("leverage", 1.0)
            
            # Calculate potential drawdown based on volatility and leverage
            base_drawdown = market_volatility * 2  # 2x volatility as worst case
            leveraged_drawdown = base_drawdown * leverage
            
            return min(1.0, leveraged_drawdown)
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {str(e)}")
            return 0.15  # 15% potential drawdown as fallback
    
    def _calculate_volatility_exposure(self, order_data: Dict[str, Any]) -> float:
        """Calculate the volatility exposure from a trade (0.0-1.0 scale)"""
        try:
            # Get relevant data with defaults for safety
            market_volatility = order_data.get("market_volatility", 0.2)
            order_size = order_data.get("order_size", 1.0)
            portfolio_size = order_data.get("portfolio_size", 10.0)
            
            # Calculate exposure based on order size and market volatility
            size_factor = order_size / portfolio_size
            exposure = size_factor * (market_volatility / 0.2)  # Normalize to typical volatility
            
            return min(1.0, exposure)
        except Exception as e:
            logger.error(f"Error calculating volatility exposure: {str(e)}")
            return 0.3  # 30% volatility exposure as fallback
    
    def _generate_risk_recommendation(self, order_data: Dict[str, Any]) -> str:
        """Generate a risk recommendation for a trade"""
        try:
            risk_level = self._calculate_risk_level(order_data)
            
            if risk_level > 0.8:
                return "High risk: Consider significantly reducing order size or avoiding this trade"
            elif risk_level > 0.6:
                return "Moderate-high risk: Consider reducing order size by 50% or implement tight stop-loss"
            elif risk_level > 0.4:
                return "Moderate risk: Implement proper stop-loss and position sizing"
            elif risk_level > 0.2:
                return "Low-moderate risk: Standard risk management practices recommended"
            else:
                return "Low risk: Standard position sizing appropriate"
        except Exception as e:
            logger.error(f"Error generating risk recommendation: {str(e)}")
            return "Unable to generate specific recommendation - use standard risk management"
    
    def _calculate_portfolio_risk_score(self, portfolio_data: Dict[str, Any]) -> float:
        """Calculate the overall portfolio risk score (0.0-1.0 scale)"""
        try:
            # Extract positions with proper fallbacks
            positions = portfolio_data.get("positions", [])
            if not positions:
                return 0.5  # Medium risk as fallback
                
            # Calculate weighted volatility
            total_value = sum(pos.get("value", 0) for pos in positions)
            if total_value == 0:
                return 0.5  # Medium risk as fallback
                
            # Calculate concentration and volatility factors
            largest_position = max((pos.get("value", 0) for pos in positions), default=0)
            concentration_factor = largest_position / total_value if total_value > 0 else 0.5
            
            # Calculate average volatility (weighted by position size)
            weighted_volatility = sum(
                pos.get("volatility", 0.2) * (pos.get("value", 0) / total_value) 
                for pos in positions
            ) if total_value > 0 else 0.2
            
            # Normalize volatility to 0-1 scale
            volatility_factor = min(1.0, weighted_volatility / 0.2)
            
            # Combine factors
            risk_score = (concentration_factor * 0.4) + (volatility_factor * 0.6)
            return min(1.0, max(0.0, risk_score))
        except Exception as e:
            logger.error(f"Error calculating portfolio risk score: {str(e)}")
            return 0.4  # 40% risk score as fallback
    
    def _calculate_diversification_score(self, portfolio_data: Dict[str, Any]) -> float:
        """Calculate the diversification score of a portfolio (0.0-1.0 scale, higher is better)"""
        try:
            # Extract positions with proper fallbacks
            positions = portfolio_data.get("positions", [])
            if not positions:
                return 0.5  # Medium diversification as fallback
                
            # Count asset classes, markets, and positions
            asset_classes = set(pos.get("asset_class", "unknown") for pos in positions)
            markets = set(pos.get("market", "unknown") for pos in positions)
            
            # Factor in number of positions
            position_count = len(positions)
            position_factor = min(1.0, position_count / 10)  # 10+ positions is optimal
            
            # Factor in asset classes and markets
            class_factor = min(1.0, len(asset_classes) / 5)  # 5+ asset classes is optimal
            market_factor = min(1.0, len(markets) / 3)  # 3+ markets is optimal
            
            # Calculate concentration (Herfindahl-Hirschman Index)
            total_value = sum(pos.get("value", 0) for pos in positions)
            if total_value > 0:
                hhi = sum((pos.get("value", 0) / total_value) ** 2 for pos in positions)
                concentration_factor = 1.0 - hhi  # Invert so higher is more diversified
            else:
                concentration_factor = 0.5
            
            # Combine factors
            diversification_score = (
                (position_factor * 0.2) + 
                (class_factor * 0.2) + 
                (market_factor * 0.2) + 
                (concentration_factor * 0.4)
            )
            
            return min(1.0, max(0.0, diversification_score))
        except Exception as e:
            logger.error(f"Error calculating diversification score: {str(e)}")
            return 0.65  # 65% diversification score as fallback
    
    def _calculate_correlation_risk(self, portfolio_data: Dict[str, Any]) -> float:
        """Calculate position-weighted correlation risk (0.0-1.0, higher = more risk)."""
        try:
            correlation_matrix = portfolio_data.get("correlation_matrix", {})
            positions = portfolio_data.get("positions", [])
            if not correlation_matrix:
                return 0.45

            total_value = sum(pos.get("value", 0) for pos in positions) if positions else 0
            asset_weights = {}
            if total_value > 0:
                for pos in positions:
                    sym = pos.get("symbol", pos.get("asset", ""))
                    asset_weights[sym] = pos.get("value", 0) / total_value

            weighted_sum = 0.0
            weight_total = 0.0
            for asset1, corrs in correlation_matrix.items():
                for asset2, corr in corrs.items():
                    if asset1 != asset2:
                        w1 = asset_weights.get(asset1, 1.0 / max(1, len(correlation_matrix)))
                        w2 = asset_weights.get(asset2, 1.0 / max(1, len(correlation_matrix)))
                        pair_weight = w1 * w2
                        weighted_sum += abs(corr) * pair_weight
                        weight_total += pair_weight

            if weight_total > 0:
                return min(1.0, weighted_sum / weight_total)
            return 0.45
        except Exception as e:
            logger.error(f"Error calculating correlation risk: {str(e)}")
            return 0.45
    
    def _calculate_market_exposure(self, portfolio_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate market exposure of a portfolio by market type"""
        try:
            # Extract positions with proper fallbacks
            positions = portfolio_data.get("positions", [])
            if not positions:
                return {
                    "crypto": 0.4,
                    "stock": 0.3,
                    "commodity": 0.2,
                    "forex": 0.1
                }
            
            # Calculate total value
            total_value = sum(pos.get("value", 0) for pos in positions)
            if total_value == 0:
                return {
                    "crypto": 0.4,
                    "stock": 0.3,
                    "commodity": 0.2,
                    "forex": 0.1
                }
            
            # Calculate exposure by market
            exposures = {}
            for pos in positions:
                market = pos.get("market", "other")
                value = pos.get("value", 0)
                if market in exposures:
                    exposures[market] += value
                else:
                    exposures[market] = value
            
            # Normalize to percentages
            for market in exposures:
                exposures[market] = exposures[market] / total_value
            
            return exposures
        except Exception as e:
            logger.error(f"Error calculating market exposure: {str(e)}")
            return {
                "crypto": 0.4,
                "stock": 0.3,
                "commodity": 0.2,
                "forex": 0.1
            }
    
    def _generate_portfolio_recommendations(self, portfolio_data: Dict[str, Any]) -> List[str]:
        """Generate risk recommendations for a portfolio"""
        try:
            recommendations = []
            
            # Calculate key metrics
            risk_score = self._calculate_portfolio_risk_score(portfolio_data)
            diversification = self._calculate_diversification_score(portfolio_data)
            correlation_risk = self._calculate_correlation_risk(portfolio_data)
            market_exposure = self._calculate_market_exposure(portfolio_data)
            
            # Check overall risk
            if risk_score > 0.7:
                recommendations.append("Portfolio has high risk - consider rebalancing to reduce exposure")
            
            # Check diversification
            if diversification < 0.5:
                recommendations.append("Low diversification - add uncorrelated assets across different markets")
            
            # Check correlation
            if correlation_risk > 0.6:
                recommendations.append("High correlation between assets - seek more uncorrelated investments")
            
            # Check market exposure
            for market, exposure in market_exposure.items():
                if exposure > 0.4:
                    recommendations.append(f"High exposure to {market} ({int(exposure*100)}%) - consider rebalancing")
            
            # Add standard recommendations if list is empty
            if not recommendations:
                recommendations = [
                    "Portfolio is well-balanced - maintain current diversification",
                    "Consider regular rebalancing to maintain target allocations",
                    "Implement stop-loss orders to manage downside risk"
                ]
            
            return recommendations
        except Exception as e:
            logger.error(f"Error generating portfolio recommendations: {str(e)}")
            return [
                "Unable to generate specific recommendations - please review portfolio manually",
                "Consider implementing standard risk management practices"
            ]
    
    # Event bus publishing methods
    
    async def _publish_status(self, status: str):
        """Publish component status to event bus"""
        if self.event_bus:
            try:
                await self.event_bus.publish("component.status", {
                    "component": self.name,
                    "status": status
                })
            except Exception as e:
                logger.error(f"Error publishing status: {str(e)}")
    
    async def _publish_risk_assessment(self, assessment: Dict[str, Any], request_id: Optional[str] = None):
        """Publish risk assessment results to event bus"""
        if self.event_bus:
            try:
                await self.event_bus.publish("risk.assessment.trade", {
                    "assessment": assessment,
                    "request_id": request_id
                })
            except Exception as e:
                logger.error(f"Error publishing risk assessment: {str(e)}")
    
    async def _publish_portfolio_risk_assessment(self, assessment: Dict[str, Any], request_id: Optional[str] = None):
        """Publish portfolio risk assessment results to event bus"""
        if self.event_bus:
            try:
                await self.event_bus.publish("risk.assessment.portfolio", {
                    "assessment": assessment,
                    "request_id": request_id
                })
            except Exception as e:
                logger.error(f"Error publishing portfolio risk assessment: {str(e)}")
    
    async def _publish_risk_warning(self, assessment: Dict[str, Any]):
        """Publish risk warning to event bus"""
        if self.event_bus:
            try:
                await self.event_bus.publish("risk.warning", {
                    "assessment": assessment,
                    "severity": "high" if assessment["risk_level"] > 0.8 else "medium",
                    "message": f"High risk trade detected: {assessment.get('recommendation', '')}"
                })
            except Exception as e:
                logger.error(f"Error publishing risk warning: {str(e)}")
    
    async def _request_portfolio_data(self):
        """Request portfolio data for reassessment"""
        if self.event_bus:
            try:
                await self.event_bus.publish("portfolio.data.request", {
                    "requester": self.name,
                    "request_id": f"risk-reassess-{asyncio.get_event_loop().time()}"
                })
            except Exception as e:
                logger.error(f"Error requesting portfolio data: {str(e)}")
