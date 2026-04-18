#!/usr/bin/env python3
"""
Risk Manager for Kingdom AI Trading System
Provides risk management, position sizing, and portfolio protection
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """Risk levels for trading"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

@dataclass
class RiskParameters:
    """Risk management parameters"""
    max_position_size: float = 0.1  # 10% of portfolio max
    max_daily_loss: float = 0.05    # 5% daily loss limit
    max_drawdown: float = 0.15     # 15% max drawdown
    stop_loss_pct: float = 0.02    # 2% stop loss
    take_profit_pct: float = 0.06  # 6% take profit
    max_leverage: float = 3.0      # 3x max leverage
    risk_per_trade: float = 0.01   # 1% risk per trade

@dataclass
class Position:
    """Trading position"""
    symbol: str
    side: str  # long, short
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    timestamp: datetime = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class RiskAlert:
    """Risk alert"""
    level: RiskLevel
    message: str
    symbol: Optional[str]
    timestamp: datetime
    action_required: str

class RiskManager:
    """Advanced risk management system"""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._running = False
        self._parameters = RiskParameters()
        self._positions: Dict[str, Position] = {}
        self._portfolio_value = 100000.0  # Starting portfolio value
        self._daily_pnl = 0.0
        self._max_portfolio_value = 100000.0
        self._alerts: List[RiskAlert] = []
        self._risk_metrics = {}
        
    async def initialize(self):
        """Initialize the risk manager"""
        logger.info("🔄 RiskManager initializing...")
        self._running = True
        
        if self.event_bus:
            self.event_bus.subscribe('position.open', self._handle_position_open)
            self.event_bus.subscribe('position.close', self._handle_position_close)
            self.event_bus.subscribe('position.update', self._handle_position_update)
            self.event_bus.subscribe('risk.parameters.update', self._handle_parameters_update)
            
        logger.info("✅ RiskManager initialized")
        return True
        
    async def start(self):
        """Start risk management"""
        if not self._running:
            await self.initialize()
            
        logger.info("🛡️ RiskManager started")
        return True
        
    async def stop(self):
        """Stop risk management"""
        self._running = False
        logger.info("⏹️ RiskManager stopped")
        
    def _handle_position_open(self, data):
        """Handle position opening"""
        symbol = data.get('symbol')
        side = data.get('side')
        size = data.get('size')
        price = data.get('price')
        
        if symbol and side and size and price:
            position = Position(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=price,
                current_price=price,
                unrealized_pnl=0.0
            )
            
            # Calculate stop loss and take profit
            if side == 'long':
                position.stop_loss = price * (1 - self._parameters.stop_loss_pct)
                position.take_profit = price * (1 + self._parameters.take_profit_pct)
            else:
                position.stop_loss = price * (1 + self._parameters.stop_loss_pct)
                position.take_profit = price * (1 - self._parameters.take_profit_pct)
            
            self._positions[symbol] = position
            logger.info(f"📊 Position opened: {symbol} {side} {size} @ {price}")
            
    def _handle_position_close(self, data):
        """Handle position closing"""
        symbol = data.get('symbol')
        if symbol in self._positions:
            position = self._positions[symbol]
            self._daily_pnl += position.realized_pnl
            del self._positions[symbol]
            logger.info(f"📊 Position closed: {symbol} PnL: {position.realized_pnl}")
            
    def _handle_position_update(self, data):
        """Handle position updates"""
        symbol = data.get('symbol')
        new_price = data.get('price')
        
        if symbol in self._positions and new_price:
            position = self._positions[symbol]
            position.current_price = new_price
            
            # Update unrealized PnL
            if position.side == 'long':
                position.unrealized_pnl = (new_price - position.entry_price) * position.size
            else:
                position.unrealized_pnl = (position.entry_price - new_price) * position.size
            
            # Check for stop loss or take profit
            self._check_exit_conditions(position)
            
    def _handle_parameters_update(self, data):
        """Handle risk parameters updates"""
        for key, value in data.items():
            if hasattr(self._parameters, key):
                setattr(self._parameters, key, value)
                logger.info(f"📊 Risk parameter updated: {key} = {value}")
                
    def _check_exit_conditions(self, position: Position):
        """Check if position should be closed"""
        if position.side == 'long':
            if position.current_price <= position.stop_loss:
                self._trigger_stop_loss(position)
            elif position.current_price >= position.take_profit:
                self._trigger_take_profit(position)
        else:
            if position.current_price >= position.stop_loss:
                self._trigger_stop_loss(position)
            elif position.current_price <= position.take_profit:
                self._trigger_take_profit(position)
                
    def _trigger_stop_loss(self, position: Position):
        """Trigger stop loss"""
        alert = RiskAlert(
            level=RiskLevel.HIGH,
            message=f"Stop loss triggered for {position.symbol}",
            symbol=position.symbol,
            timestamp=datetime.now(),
            action_required="close_position"
        )
        self._alerts.append(alert)
        
        if self.event_bus:
            self.event_bus.publish('risk.stop_loss', {
                'symbol': position.symbol,
                'price': position.current_price,
                'pnl': position.unrealized_pnl
            })
            
        logger.warning(f"⚠️ Stop loss triggered: {position.symbol} @ {position.current_price}")
        
    def _trigger_take_profit(self, position: Position):
        """Trigger take profit"""
        alert = RiskAlert(
            level=RiskLevel.LOW,
            message=f"Take profit triggered for {position.symbol}",
            symbol=position.symbol,
            timestamp=datetime.now(),
            action_required="close_position"
        )
        self._alerts.append(alert)
        
        if self.event_bus:
            self.event_bus.publish('risk.take_profit', {
                'symbol': position.symbol,
                'price': position.current_price,
                'pnl': position.unrealized_pnl
            })
            
        logger.info(f"✅ Take profit triggered: {position.symbol} @ {position.current_price}")
        
    def calculate_position_size(self, symbol: str, price: float, risk_amount: Optional[float] = None) -> float:
        """Calculate optimal position size based on risk parameters"""
        if risk_amount is None:
            risk_amount = self._portfolio_value * self._parameters.risk_per_trade
            
        # Calculate position size based on stop loss
        stop_loss_distance = price * self._parameters.stop_loss_pct
        position_size = risk_amount / stop_loss_distance
        
        # Apply maximum position size limit
        max_size = self._portfolio_value * self._parameters.max_position_size / price
        position_size = min(position_size, max_size)
        
        return position_size
        
    def assess_risk(self, symbol: str, order_type: OrderType, size: float, price: float) -> Tuple[bool, str]:
        """Assess risk for a potential trade"""
        # Check daily loss limit
        if self._daily_pnl < -self._portfolio_value * self._parameters.max_daily_loss:
            return False, "Daily loss limit exceeded"
            
        # Check maximum drawdown
        current_drawdown = (self._max_portfolio_value - self._portfolio_value) / self._max_portfolio_value
        if current_drawdown > self._parameters.max_drawdown:
            return False, "Maximum drawdown exceeded"
            
        # Check position size
        position_value = size * price
        if position_value > self._portfolio_value * self._parameters.max_position_size:
            return False, "Position size too large"
            
        # Check leverage
        leverage = position_value / self._portfolio_value
        if leverage > self._parameters.max_leverage:
            return False, "Leverage too high"
            
        return True, "Risk acceptable"
        
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics"""
        total_unrealized = sum(pos.unrealized_pnl for pos in self._positions.values())
        total_exposure = sum(pos.size * pos.current_price for pos in self._positions.values())
        
        current_drawdown = (self._max_portfolio_value - self._portfolio_value) / self._max_portfolio_value
        risk_score = min(100, (current_drawdown + abs(self._daily_pnl) / self._portfolio_value) * 100)
        
        return {
            'portfolio_value': self._portfolio_value,
            'daily_pnl': self._daily_pnl,
            'unrealized_pnl': total_unrealized,
            'total_exposure': total_exposure,
            'max_drawdown': current_drawdown,
            'risk_score': risk_score,
            'open_positions': len(self._positions),
            'recent_alerts': len([a for a in self._alerts if (datetime.now() - a.timestamp).seconds < 3600])
        }
        
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        return [
            {
                'symbol': pos.symbol,
                'side': pos.side,
                'size': pos.size,
                'entry_price': pos.entry_price,
                'current_price': pos.current_price,
                'unrealized_pnl': pos.unrealized_pnl,
                'stop_loss': pos.stop_loss,
                'take_profit': pos.take_profit,
                'timestamp': pos.timestamp.isoformat()
            }
            for pos in self._positions.values()
        ]
        
    def get_alerts(self, level: Optional[RiskLevel] = None) -> List[Dict[str, Any]]:
        """Get risk alerts"""
        alerts = self._alerts
        if level:
            alerts = [a for a in alerts if a.level == level]
            
        return [
            {
                'level': alert.level.value,
                'message': alert.message,
                'symbol': alert.symbol,
                'timestamp': alert.timestamp.isoformat(),
                'action_required': alert.action_required
            }
            for alert in alerts
        ]

logger.info("✅ RiskManager loaded")
