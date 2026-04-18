"""
SOTA 2025-2026 Coin Accumulation Intelligence

This module implements a three-tier wallet strategy focused on accumulating
more COINS rather than just USD value. The philosophy is "Stack Sats" -
the goal is to own MORE cryptocurrency, not just have more dollars.

Three-Tier Strategy:
1. Stablecoin Treasury (Safety Buffer) - USDT/USDC/RLUSD hold trading profits
2. Utility Coin Compounding (Accumulation Targets) - BTC/XRP/XLM auto-accumulation
3. Mining Rewards Reinvestment - Trade mined coins, compound profits back

Author: Kingdom AI System
Version: 1.0.0
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class AccumulationTier(Enum):
    """Three-tier wallet strategy classification."""
    STABLECOIN_TREASURY = "stablecoin_treasury"      # Tier 1: Safety buffer
    UTILITY_ACCUMULATION = "utility_accumulation"    # Tier 2: Stack coins
    MINING_COMPOUND = "mining_compound"              # Tier 3: Mining reinvestment


class AccumulationAction(Enum):
    """Actions the intelligence can take."""
    HOLD = "hold"
    BUY_DIP = "buy_dip"
    TAKE_PROFIT_TO_STABLE = "take_profit_to_stable"
    COMPOUND_MINING_REWARD = "compound_mining_reward"
    REBALANCE = "rebalance"


@dataclass
class CoinConfig:
    """Configuration for a tracked coin."""
    symbol: str
    tier: AccumulationTier
    target_allocation_pct: float = 0.0  # Target % of portfolio
    min_accumulation_amount: float = 0.0  # Min amount to trigger accumulation
    dip_threshold_pct: float = 5.0  # % drop to trigger buy
    take_profit_pct: float = 15.0  # % gain to take some profit
    is_mined: bool = False  # Is this coin mined?
    compound_pct: float = 100.0  # % of mining profits to compound back


@dataclass
class CoinHolding:
    """Tracks holdings for a specific coin with accumulation metrics."""
    symbol: str
    tier: AccumulationTier
    quantity: float = 0.0  # Total coins owned
    avg_cost_basis: float = 0.0  # Average cost per coin in USD
    total_accumulated: float = 0.0  # Total coins accumulated via intelligence
    total_mined: float = 0.0  # Total coins from mining
    total_compounded: float = 0.0  # Coins gained from compound reinvestment
    last_price: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def usd_value(self) -> float:
        """Current USD value of holdings."""
        return self.quantity * self.last_price if self.last_price > 0 else 0.0
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L in USD."""
        if self.avg_cost_basis <= 0 or self.quantity <= 0:
            return 0.0
        return (self.last_price - self.avg_cost_basis) * self.quantity
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as percentage."""
        if self.avg_cost_basis <= 0:
            return 0.0
        return ((self.last_price / self.avg_cost_basis) - 1.0) * 100.0


@dataclass
class AccumulationOpportunity:
    """Represents a detected accumulation opportunity."""
    id: str
    symbol: str
    action: AccumulationAction
    tier: AccumulationTier
    current_price: float
    suggested_amount_usd: float
    suggested_quantity: float
    reason: str
    confidence: float  # 0-100
    detected_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    executed: bool = False
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass 
class AccumulationMetrics:
    """Overall accumulation performance metrics."""
    total_coins_accumulated: Dict[str, float] = field(default_factory=dict)
    total_stablecoin_reserve_usd: float = 0.0
    total_mining_rewards_compounded: Dict[str, float] = field(default_factory=dict)
    dip_buys_executed: int = 0
    profit_takes_executed: int = 0
    compound_events: int = 0
    total_value_accumulated_usd: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)


class CoinAccumulationIntelligence:
    """
    SOTA 2025-2026 Coin Accumulation Intelligence System
    
    Implements intelligent wallet management focused on accumulating more COINS
    rather than just USD value. Uses a three-tier strategy:
    
    Tier 1 - Stablecoin Treasury: Safety buffer for trading profits
    Tier 2 - Utility Coin Accumulation: Auto-buy BTC/XRP/XLM on dips  
    Tier 3 - Mining Rewards Compounding: Reinvest mining profits
    """
    
    # Default stablecoins (Tier 1)
    STABLECOINS: Set[str] = {
        'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP', 'GUSD',
        'RLUSD', 'FRAX', 'LUSD', 'sUSD', 'USDD', 'cUSD', 'UST'
    }
    
    # Default utility coins for accumulation (Tier 2)
    DEFAULT_ACCUMULATION_TARGETS: Dict[str, CoinConfig] = {
        'BTC': CoinConfig(
            symbol='BTC',
            tier=AccumulationTier.UTILITY_ACCUMULATION,
            target_allocation_pct=30.0,
            dip_threshold_pct=5.0,
            take_profit_pct=20.0,
        ),
        'XRP': CoinConfig(
            symbol='XRP',
            tier=AccumulationTier.UTILITY_ACCUMULATION,
            target_allocation_pct=15.0,
            dip_threshold_pct=7.0,
            take_profit_pct=25.0,
        ),
        'XLM': CoinConfig(
            symbol='XLM',
            tier=AccumulationTier.UTILITY_ACCUMULATION,
            target_allocation_pct=10.0,
            dip_threshold_pct=8.0,
            take_profit_pct=30.0,
        ),
        'ETH': CoinConfig(
            symbol='ETH',
            tier=AccumulationTier.UTILITY_ACCUMULATION,
            target_allocation_pct=20.0,
            dip_threshold_pct=6.0,
            take_profit_pct=20.0,
        ),
        'SOL': CoinConfig(
            symbol='SOL',
            tier=AccumulationTier.UTILITY_ACCUMULATION,
            target_allocation_pct=10.0,
            dip_threshold_pct=10.0,
            take_profit_pct=30.0,
        ),
    }
    
    def __init__(
        self,
        event_bus: Optional[Any] = None,
        order_executor: Optional[Callable] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.event_bus = event_bus
        self.order_executor = order_executor
        self.config = config or {}
        
        # Coin configurations
        self.coin_configs: Dict[str, CoinConfig] = {}
        self._init_default_configs()
        
        # Holdings tracking (coins owned)
        self.holdings: Dict[str, CoinHolding] = {}
        
        # Price history for dip detection
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.price_history_window = timedelta(hours=24)
        
        # Accumulation opportunities queue
        self.opportunities: List[AccumulationOpportunity] = []
        self.executed_opportunities: List[AccumulationOpportunity] = []
        
        # Metrics
        self.metrics = AccumulationMetrics()
        
        # Mining rewards tracking
        self.mining_rewards_pending: Dict[str, float] = {}  # symbol -> amount
        self.mining_trade_profits: Dict[str, float] = {}  # symbol -> USD profit
        
        # Control flags
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._accumulation_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.stablecoin_reserve_target_pct = self.config.get('stablecoin_reserve_pct', 40.0)
        self.min_stablecoin_for_accumulation = self.config.get('min_stable_usd', 100.0)
        self.max_single_accumulation_pct = self.config.get('max_single_buy_pct', 10.0)
        self.dip_detection_window_hours = self.config.get('dip_window_hours', 24)
        self.accumulation_cooldown_minutes = self.config.get('cooldown_minutes', 30)
        self.auto_execute = self.config.get('auto_execute', False)
        
        # Last accumulation timestamps per coin
        self._last_accumulation: Dict[str, datetime] = {}
        
        # Subscribe to events
        if self.event_bus:
            self._setup_subscriptions()
        
        logger.info("🪙 CoinAccumulationIntelligence initialized - Stack Sats Mode Active")
    
    def _init_default_configs(self) -> None:
        """Initialize default coin configurations."""
        # Add default accumulation targets
        for symbol, config in self.DEFAULT_ACCUMULATION_TARGETS.items():
            self.coin_configs[symbol] = config
        
        # Add common stablecoins
        for stable in self.STABLECOINS:
            self.coin_configs[stable] = CoinConfig(
                symbol=stable,
                tier=AccumulationTier.STABLECOIN_TREASURY,
                target_allocation_pct=0.0,  # Stables float based on profits
            )
    
    def _setup_subscriptions(self) -> None:
        """Setup event bus subscriptions."""
        if not self.event_bus:
            return
        
        # Price updates for dip detection
        self.event_bus.subscribe('trading.price_update', self._on_price_update)
        self.event_bus.subscribe('market.price', self._on_price_update)
        self.event_bus.subscribe('trading.ticker', self._on_ticker_update)
        
        # Trading events for profit tracking
        self.event_bus.subscribe('trading.order_filled', self._on_order_filled)
        self.event_bus.subscribe('trading.profit.update', self._on_profit_update)
        
        # Mining events
        self.event_bus.subscribe('mining.reward.received', self._on_mining_reward)
        self.event_bus.subscribe('mining.payout', self._on_mining_reward)
        
        # Wallet balance updates
        self.event_bus.subscribe('wallet.balance.update', self._on_wallet_update)
        self.event_bus.subscribe('wallet.snapshot', self._on_wallet_snapshot)
        
        # SOTA 2025: Profit goal and trading profit events for closed loop
        self.event_bus.subscribe('trading.profit.report', self._on_profit_report)
        self.event_bus.subscribe('trading.intelligence.goal_progress', self._on_goal_progress)
        self.event_bus.subscribe('trading.position.exit', self._on_position_exit)
        
        # Thoth brain response for accumulation decisions
        self.event_bus.subscribe('thoth.accumulation.response', self._on_thoth_response)
        
        logger.info("📡 CoinAccumulationIntelligence subscribed to events")
    
    # -------------------------------------------------------------------------
    # TIER 1: Stablecoin Treasury Management
    # -------------------------------------------------------------------------
    
    def get_stablecoin_reserves(self) -> Dict[str, float]:
        """Get current stablecoin holdings."""
        reserves = {}
        for symbol, holding in self.holdings.items():
            if holding.tier == AccumulationTier.STABLECOIN_TREASURY:
                reserves[symbol] = holding.quantity
        return reserves
    
    def get_total_stablecoin_usd(self) -> float:
        """Get total USD value in stablecoins."""
        total = 0.0
        for symbol, holding in self.holdings.items():
            if holding.tier == AccumulationTier.STABLECOIN_TREASURY:
                # Stablecoins are ~$1 each
                total += holding.quantity
        return total
    
    def get_available_for_accumulation(self) -> float:
        """Calculate USD available for accumulation buys."""
        total_stable = self.get_total_stablecoin_usd()
        
        # Keep minimum reserve
        min_reserve = total_stable * (self.stablecoin_reserve_target_pct / 100.0)
        available = total_stable - min_reserve
        
        if available < self.min_stablecoin_for_accumulation:
            return 0.0
        
        # Cap single accumulation at max percentage
        max_single = total_stable * (self.max_single_accumulation_pct / 100.0)
        return min(available, max_single)
    
    def allocate_profit_to_treasury(self, profit_usd: float, source: str = 'trading') -> None:
        """Allocate trading profit to stablecoin treasury."""
        if profit_usd <= 0:
            return
        
        # Default to USDT for simplicity
        stable_symbol = 'USDT'
        
        if stable_symbol not in self.holdings:
            self.holdings[stable_symbol] = CoinHolding(
                symbol=stable_symbol,
                tier=AccumulationTier.STABLECOIN_TREASURY,
            )
        
        self.holdings[stable_symbol].quantity += profit_usd
        self.holdings[stable_symbol].last_price = 1.0
        self.holdings[stable_symbol].last_updated = datetime.now()
        
        self.metrics.total_stablecoin_reserve_usd = self.get_total_stablecoin_usd()
        
        logger.info(f"💵 Allocated ${profit_usd:.2f} profit to treasury from {source}")
        
        if self.event_bus:
            self.event_bus.publish('accumulation.treasury.updated', {
                'profit_added': profit_usd,
                'source': source,
                'total_reserve': self.metrics.total_stablecoin_reserve_usd,
                'timestamp': datetime.now().isoformat(),
            })
        
        # SOTA 2025: Publish telemetry and profit contribution
        self._publish_telemetry('treasury_allocation', {
            'profit_added': profit_usd,
            'source': source,
            'total_reserve': self.metrics.total_stablecoin_reserve_usd,
        })
        self._publish_profit_contribution('USDT', profit_usd, 'treasury')
    
    # -------------------------------------------------------------------------
    # TIER 2: Utility Coin Accumulation (Dip Buying)
    # -------------------------------------------------------------------------
    
    def add_accumulation_target(
        self,
        symbol: str,
        target_allocation_pct: float = 10.0,
        dip_threshold_pct: float = 5.0,
        take_profit_pct: float = 20.0,
    ) -> None:
        """Add a coin to accumulation targets."""
        self.coin_configs[symbol] = CoinConfig(
            symbol=symbol,
            tier=AccumulationTier.UTILITY_ACCUMULATION,
            target_allocation_pct=target_allocation_pct,
            dip_threshold_pct=dip_threshold_pct,
            take_profit_pct=take_profit_pct,
        )
        logger.info(f"🎯 Added {symbol} to accumulation targets (dip: {dip_threshold_pct}%, TP: {take_profit_pct}%)")
    
    def detect_dip(self, symbol: str, current_price: float) -> Optional[float]:
        """
        Detect if a coin has dipped from recent highs.
        Returns the dip percentage if detected, None otherwise.
        """
        if symbol not in self.price_history:
            return None
        
        history = self.price_history[symbol]
        if len(history) < 2:
            return None
        
        # Find highest price in window
        cutoff = datetime.now() - timedelta(hours=self.dip_detection_window_hours)
        recent_prices = [p for ts, p in history if ts > cutoff]
        
        if not recent_prices:
            return None
        
        high_price = max(recent_prices)
        if high_price <= 0:
            return None
        
        dip_pct = ((high_price - current_price) / high_price) * 100.0
        return dip_pct if dip_pct > 0 else None
    
    def evaluate_accumulation_opportunity(
        self, symbol: str, current_price: float
    ) -> Optional[AccumulationOpportunity]:
        """Evaluate if there's an accumulation opportunity for a coin."""
        config = self.coin_configs.get(symbol)
        if not config or config.tier != AccumulationTier.UTILITY_ACCUMULATION:
            return None
        
        # Check cooldown
        last_accum = self._last_accumulation.get(symbol)
        if last_accum:
            cooldown = timedelta(minutes=self.accumulation_cooldown_minutes)
            if datetime.now() - last_accum < cooldown:
                return None
        
        # Detect dip
        dip_pct = self.detect_dip(symbol, current_price)
        if dip_pct is None or dip_pct < config.dip_threshold_pct:
            return None
        
        # Check available funds
        available_usd = self.get_available_for_accumulation()
        if available_usd <= 0:
            return None
        
        # Calculate buy amount
        suggested_usd = min(available_usd, available_usd * (dip_pct / 20.0))  # Scale with dip size
        suggested_qty = suggested_usd / current_price if current_price > 0 else 0
        
        # Confidence based on dip magnitude
        confidence = min(95.0, 50.0 + (dip_pct * 3))
        
        opportunity = AccumulationOpportunity(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            action=AccumulationAction.BUY_DIP,
            tier=AccumulationTier.UTILITY_ACCUMULATION,
            current_price=current_price,
            suggested_amount_usd=suggested_usd,
            suggested_quantity=suggested_qty,
            reason=f"{symbol} dipped {dip_pct:.1f}% from 24h high - accumulation opportunity",
            confidence=confidence,
            expires_at=datetime.now() + timedelta(hours=1),
        )
        
        return opportunity
    
    async def execute_accumulation(self, opportunity: AccumulationOpportunity) -> bool:
        """Execute an accumulation buy order."""
        if opportunity.executed or opportunity.is_expired():
            return False
        
        symbol = opportunity.symbol
        amount_usd = opportunity.suggested_amount_usd
        quantity = opportunity.suggested_quantity
        
        logger.info(
            f"🪙 ACCUMULATING: Buying {quantity:.8f} {symbol} "
            f"(${amount_usd:.2f}) - {opportunity.reason}"
        )
        
        # Execute via order executor if available
        if self.order_executor:
            try:
                result = await self.order_executor(
                    symbol=f"{symbol}/USDT",
                    side='buy',
                    amount=quantity,
                    order_type='market',
                    source='accumulation_intelligence',
                )
                if not result:
                    return False
            except Exception as e:
                logger.error(f"Failed to execute accumulation order: {e}")
                return False
        
        # Update holdings
        if symbol not in self.holdings:
            self.holdings[symbol] = CoinHolding(
                symbol=symbol,
                tier=AccumulationTier.UTILITY_ACCUMULATION,
            )
        
        holding = self.holdings[symbol]
        old_qty = holding.quantity
        old_cost = holding.avg_cost_basis * old_qty
        
        new_qty = old_qty + quantity
        new_cost = old_cost + amount_usd
        
        holding.quantity = new_qty
        holding.avg_cost_basis = new_cost / new_qty if new_qty > 0 else 0
        holding.total_accumulated += quantity
        holding.last_price = opportunity.current_price
        holding.last_updated = datetime.now()
        
        # Deduct from stablecoin reserve
        self._deduct_from_treasury(amount_usd)
        
        # Update metrics
        self.metrics.dip_buys_executed += 1
        if symbol not in self.metrics.total_coins_accumulated:
            self.metrics.total_coins_accumulated[symbol] = 0.0
        self.metrics.total_coins_accumulated[symbol] += quantity
        
        # Mark as executed
        opportunity.executed = True
        self.executed_opportunities.append(opportunity)
        self._last_accumulation[symbol] = datetime.now()
        
        # Publish event
        if self.event_bus:
            self.event_bus.publish('accumulation.executed', {
                'symbol': symbol,
                'action': 'buy_dip',
                'quantity': quantity,
                'price': opportunity.current_price,
                'amount_usd': amount_usd,
                'reason': opportunity.reason,
                'total_coins_owned': holding.quantity,
                'timestamp': datetime.now().isoformat(),
            })
        
        # SOTA 2025: Publish telemetry for AI tracking and profit progress
        self._publish_telemetry('dip_buy_executed', {
            'symbol': symbol,
            'quantity': quantity,
            'price': opportunity.current_price,
            'amount_usd': amount_usd,
            'total_coins': holding.quantity,
            'total_accumulated': holding.total_accumulated,
            'dip_buys_count': self.metrics.dip_buys_executed,
        })
        
        logger.info(
            f"✅ ACCUMULATED: Now own {holding.quantity:.8f} {symbol} "
            f"(+{quantity:.8f} coins)"
        )
        
        return True
    
    def _deduct_from_treasury(self, amount_usd: float) -> None:
        """Deduct amount from stablecoin treasury."""
        remaining = amount_usd
        for symbol in ['USDT', 'USDC', 'BUSD', 'DAI']:
            if remaining <= 0:
                break
            if symbol in self.holdings:
                available = self.holdings[symbol].quantity
                deduct = min(available, remaining)
                self.holdings[symbol].quantity -= deduct
                remaining -= deduct
        
        self.metrics.total_stablecoin_reserve_usd = self.get_total_stablecoin_usd()
    
    # -------------------------------------------------------------------------
    # TIER 3: Mining Rewards Compounding
    # -------------------------------------------------------------------------
    
    def register_mined_coin(
        self,
        symbol: str,
        compound_pct: float = 100.0,
    ) -> None:
        """Register a coin that is being mined for compound tracking."""
        if symbol not in self.coin_configs:
            self.coin_configs[symbol] = CoinConfig(
                symbol=symbol,
                tier=AccumulationTier.MINING_COMPOUND,
                is_mined=True,
                compound_pct=compound_pct,
            )
        else:
            self.coin_configs[symbol].is_mined = True
            self.coin_configs[symbol].compound_pct = compound_pct
            self.coin_configs[symbol].tier = AccumulationTier.MINING_COMPOUND
        
        logger.info(f"⛏️ Registered {symbol} for mining compound ({compound_pct}% reinvestment)")
    
    def record_mining_reward(self, symbol: str, amount: float, usd_value: float = 0.0) -> None:
        """Record a mining reward for tracking."""
        if symbol not in self.mining_rewards_pending:
            self.mining_rewards_pending[symbol] = 0.0
        
        self.mining_rewards_pending[symbol] += amount
        
        # Update holdings
        if symbol not in self.holdings:
            self.holdings[symbol] = CoinHolding(
                symbol=symbol,
                tier=AccumulationTier.MINING_COMPOUND,
            )
        
        self.holdings[symbol].quantity += amount
        self.holdings[symbol].total_mined += amount
        self.holdings[symbol].last_updated = datetime.now()
        
        logger.info(f"⛏️ Mining reward recorded: +{amount:.8f} {symbol} (Total mined: {self.holdings[symbol].total_mined:.8f})")
        
        if self.event_bus:
            self.event_bus.publish('accumulation.mining.received', {
                'symbol': symbol,
                'amount': amount,
                'total_mined': self.holdings[symbol].total_mined,
                'timestamp': datetime.now().isoformat(),
            })
    
    def record_mining_trade_profit(self, symbol: str, profit_usd: float) -> None:
        """Record profit from trading mined coins."""
        if symbol not in self.mining_trade_profits:
            self.mining_trade_profits[symbol] = 0.0
        
        self.mining_trade_profits[symbol] += profit_usd
        
        config = self.coin_configs.get(symbol)
        if config and config.is_mined and config.compound_pct > 0:
            compound_amount = profit_usd * (config.compound_pct / 100.0)
            self._queue_compound_rebuy(symbol, compound_amount)
    
    def _queue_compound_rebuy(self, symbol: str, usd_amount: float) -> None:
        """Queue a compound rebuy for a mined coin."""
        if usd_amount < 10.0:  # Min threshold
            return
        
        current_price = self.holdings.get(symbol, CoinHolding(symbol=symbol, tier=AccumulationTier.MINING_COMPOUND)).last_price
        if current_price <= 0:
            return
        
        quantity = usd_amount / current_price
        
        opportunity = AccumulationOpportunity(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            action=AccumulationAction.COMPOUND_MINING_REWARD,
            tier=AccumulationTier.MINING_COMPOUND,
            current_price=current_price,
            suggested_amount_usd=usd_amount,
            suggested_quantity=quantity,
            reason=f"Compounding {symbol} mining profit - reinvesting ${usd_amount:.2f}",
            confidence=90.0,
            expires_at=datetime.now() + timedelta(hours=4),
        )
        
        self.opportunities.append(opportunity)
        logger.info(f"🔄 Queued compound rebuy: {quantity:.8f} {symbol} (${usd_amount:.2f})")
    
    async def execute_compound(self, opportunity: AccumulationOpportunity) -> bool:
        """Execute a compound rebuy for mined coins."""
        if opportunity.executed or opportunity.is_expired():
            return False
        
        symbol = opportunity.symbol
        quantity = opportunity.suggested_quantity
        
        logger.info(f"🔄 COMPOUNDING: Rebuying {quantity:.8f} {symbol}")
        
        # Execute via order executor if available
        if self.order_executor:
            try:
                result = await self.order_executor(
                    symbol=f"{symbol}/USDT",
                    side='buy',
                    amount=quantity,
                    order_type='market',
                    source='mining_compound',
                )
                if not result:
                    return False
            except Exception as e:
                logger.error(f"Failed to execute compound order: {e}")
                return False
        
        # Update holdings
        if symbol in self.holdings:
            self.holdings[symbol].quantity += quantity
            self.holdings[symbol].total_compounded += quantity
            self.holdings[symbol].last_updated = datetime.now()
        
        # Update metrics
        self.metrics.compound_events += 1
        if symbol not in self.metrics.total_mining_rewards_compounded:
            self.metrics.total_mining_rewards_compounded[symbol] = 0.0
        self.metrics.total_mining_rewards_compounded[symbol] += quantity
        
        opportunity.executed = True
        self.executed_opportunities.append(opportunity)
        
        if self.event_bus:
            self.event_bus.publish('accumulation.compound.executed', {
                'symbol': symbol,
                'quantity': quantity,
                'total_compounded': self.holdings[symbol].total_compounded,
                'timestamp': datetime.now().isoformat(),
            })
        
        # SOTA 2025: Publish telemetry for AI tracking
        self._publish_telemetry('compound_executed', {
            'symbol': symbol,
            'quantity': quantity,
            'total_compounded': self.holdings[symbol].total_compounded,
            'total_quantity': self.holdings[symbol].quantity,
            'compound_events': self.metrics.compound_events,
        })
        
        logger.info(
            f"✅ COMPOUNDED: Now own {self.holdings[symbol].quantity:.8f} {symbol} "
            f"(+{quantity:.8f} from compound)"
        )
        
        return True
    
    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------
    
    async def _on_price_update(self, data: Dict[str, Any]) -> None:
        """Handle price updates for dip detection."""
        symbol = data.get('symbol', '').replace('/USDT', '').replace('/USD', '').upper()
        if not symbol:
            return
        
        price = float(data.get('price') or data.get('last') or 0)
        if price <= 0:
            return
        
        # Update price history
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append((datetime.now(), price))
        
        # Trim old history
        cutoff = datetime.now() - self.price_history_window
        self.price_history[symbol] = [
            (ts, p) for ts, p in self.price_history[symbol] if ts > cutoff
        ]
        
        # Update holding price
        if symbol in self.holdings:
            self.holdings[symbol].last_price = price
            self.holdings[symbol].last_updated = datetime.now()
        
        # Check for accumulation opportunity
        config = self.coin_configs.get(symbol)
        if config and config.tier == AccumulationTier.UTILITY_ACCUMULATION:
            opp = self.evaluate_accumulation_opportunity(symbol, price)
            if opp:
                self.opportunities.append(opp)
                logger.info(f"🎯 Accumulation opportunity detected: {opp.reason}")
                
                if self.auto_execute:
                    await self.execute_accumulation(opp)
    
    async def _on_ticker_update(self, data: Dict[str, Any]) -> None:
        """Handle ticker updates."""
        await self._on_price_update(data)
    
    async def _on_order_filled(self, data: Dict[str, Any]) -> None:
        """Handle order fills to track profits."""
        symbol = str(data.get('symbol') or '').replace('/USDT', '').replace('/USD', '').upper()
        side = str(data.get('side') or '').lower()
        pnl = float(data.get('pnl') or data.get('profit') or data.get('realized_pnl') or 0)
        
        if pnl > 0:
            # Check if this is a mined coin
            config = self.coin_configs.get(symbol)
            if config and config.is_mined:
                self.record_mining_trade_profit(symbol, pnl)
            else:
                # Regular profit goes to treasury
                self.allocate_profit_to_treasury(pnl, source=f'trade_{symbol}')
    
    async def _on_profit_update(self, data: Dict[str, Any]) -> None:
        """Handle profit updates from trading system."""
        realized_pnl = float(data.get('realized_pnl') or data.get('profit') or 0)
        if realized_pnl > 0:
            self.allocate_profit_to_treasury(realized_pnl, source='trading_system')
    
    async def _on_mining_reward(self, data: Dict[str, Any]) -> None:
        """Handle mining reward events."""
        symbol = str(data.get('coin') or data.get('symbol') or '').upper()
        amount = float(data.get('amount') or data.get('reward') or 0)
        usd_value = float(data.get('usd_value') or 0)
        
        if symbol and amount > 0:
            self.record_mining_reward(symbol, amount, usd_value)
    
    async def _on_wallet_update(self, data: Dict[str, Any]) -> None:
        """Handle wallet balance updates."""
        balances = data.get('balances') or data.get('holdings') or {}
        
        for symbol, balance_data in balances.items():
            symbol = symbol.upper()
            
            if isinstance(balance_data, (int, float)):
                quantity = float(balance_data)
            elif isinstance(balance_data, dict):
                quantity = float(balance_data.get('free', 0) + balance_data.get('locked', 0))
            else:
                continue
            
            config = self.coin_configs.get(symbol)
            tier = config.tier if config else (
                AccumulationTier.STABLECOIN_TREASURY if symbol in self.STABLECOINS
                else AccumulationTier.UTILITY_ACCUMULATION
            )
            
            if symbol not in self.holdings:
                self.holdings[symbol] = CoinHolding(symbol=symbol, tier=tier)
            
            self.holdings[symbol].quantity = quantity
            self.holdings[symbol].last_updated = datetime.now()
    
    async def _on_wallet_snapshot(self, data: Dict[str, Any]) -> None:
        """Handle wallet snapshot events."""
        await self._on_wallet_update(data)
    
    async def _on_profit_report(self, data: Dict[str, Any]) -> None:
        """Handle trading.profit.report for profit goal tracking."""
        try:
            # Extract realized profit from report
            perf = data.get('performance') or data.get('metrics') or {}
            realized_pnl = float(perf.get('realized_pnl') or data.get('realized_pnl') or 0)
            
            if realized_pnl > 0:
                # Allocate portion to treasury
                self.allocate_profit_to_treasury(realized_pnl, source='profit_report')
                
            # Publish telemetry for tracking
            self._publish_telemetry('profit_report_received', {
                'realized_pnl': realized_pnl,
                'treasury_total': self.get_total_stablecoin_usd(),
            })
        except Exception as e:
            logger.debug(f"Error handling profit report: {e}")
    
    async def _on_goal_progress(self, data: Dict[str, Any]) -> None:
        """Handle trading.intelligence.goal_progress for profit goal tracking."""
        try:
            current = float(data.get('current') or data.get('current_profit') or 0)
            target = float(data.get('target') or data.get('goal') or 0)
            progress_pct = float(data.get('progress_pct') or 0)
            
            # Log goal progress
            if target > 0:
                logger.debug(f"🎯 Profit Goal Progress: ${current:,.2f} / ${target:,.2f} ({progress_pct:.2f}%)")
            
            # Publish telemetry
            self._publish_telemetry('goal_progress', {
                'current': current,
                'target': target,
                'progress_pct': progress_pct,
                'treasury_contribution': self.get_total_stablecoin_usd(),
            })
        except Exception as e:
            logger.debug(f"Error handling goal progress: {e}")
    
    async def _on_position_exit(self, data: Dict[str, Any]) -> None:
        """Handle trading.position.exit for profit allocation."""
        try:
            symbol = str(data.get('symbol') or '').replace('/USDT', '').replace('/USD', '').upper()
            pnl = float(data.get('pnl') or data.get('realized_pnl') or data.get('profit') or 0)
            exit_reason = str(data.get('exit_reason') or data.get('reason') or 'unknown')
            
            if pnl > 0:
                # Check if this is a mined coin
                config = self.coin_configs.get(symbol)
                if config and config.is_mined:
                    self.record_mining_trade_profit(symbol, pnl)
                    logger.info(f"⛏️ Mining trade profit: ${pnl:.2f} from {symbol} ({exit_reason})")
                else:
                    # Regular profit goes to treasury
                    self.allocate_profit_to_treasury(pnl, source=f'position_exit_{symbol}')
                    logger.info(f"💵 Position exit profit: ${pnl:.2f} from {symbol} ({exit_reason})")
            
            # Publish telemetry
            self._publish_telemetry('position_exit', {
                'symbol': symbol,
                'pnl': pnl,
                'exit_reason': exit_reason,
                'is_mined': config.is_mined if config else False,
            })
        except Exception as e:
            logger.debug(f"Error handling position exit: {e}")
    
    async def _on_thoth_response(self, data: Dict[str, Any]) -> None:
        """Handle Thoth brain response for accumulation decisions."""
        try:
            query_type = data.get('query_type') or data.get('type')
            if query_type != 'accumulation_decision':
                return
            
            symbol = str(data.get('symbol') or '').upper()
            recommendation = str(data.get('recommendation') or data.get('decision') or '').lower()
            confidence = float(data.get('confidence') or 0)
            reasoning = data.get('reasoning') or data.get('explanation') or ''
            
            logger.info(f"🧠 Thoth accumulation advice for {symbol}: {recommendation} (conf: {confidence:.1f}%)")
            logger.debug(f"   Reasoning: {reasoning}")
            
            # If Thoth recommends buying and we have an opportunity
            if recommendation in ('buy', 'accumulate', 'yes') and confidence >= 70:
                # Find matching opportunity
                for opp in self.opportunities:
                    if opp.symbol == symbol and not opp.executed:
                        opp.confidence = max(opp.confidence, confidence)
                        logger.info(f"🎯 Thoth boosted {symbol} accumulation confidence to {opp.confidence:.1f}%")
                        break
            
            # Publish telemetry
            self._publish_telemetry('thoth_response', {
                'symbol': symbol,
                'recommendation': recommendation,
                'confidence': confidence,
            })
        except Exception as e:
            logger.debug(f"Error handling Thoth response: {e}")
    
    # -------------------------------------------------------------------------
    # Monitoring Loop
    # -------------------------------------------------------------------------
    
    async def start(self) -> None:
        """Start the accumulation intelligence system."""
        if self.is_running:
            return
        
        self.is_running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        self._accumulation_task = asyncio.create_task(self._accumulation_loop())
        
        logger.info("🚀 CoinAccumulationIntelligence started - Stack Sats Mode ACTIVE")
        
        if self.event_bus:
            self.event_bus.publish('accumulation.started', {
                'mode': 'stack_sats',
                'accumulation_targets': list(self.get_accumulation_targets().keys()),
                'timestamp': datetime.now().isoformat(),
            })
    
    async def stop(self) -> None:
        """Stop the accumulation intelligence system."""
        self.is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self._accumulation_task:
            self._accumulation_task.cancel()
            try:
                await self._accumulation_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 CoinAccumulationIntelligence stopped")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for price tracking."""
        while self.is_running:
            try:
                # Clean up expired opportunities
                self.opportunities = [
                    o for o in self.opportunities
                    if not o.is_expired() and not o.executed
                ]
                
                # Publish status update
                status = self.get_status()
                if self.event_bus:
                    self.event_bus.publish('accumulation.status', status)
                
                # SOTA 2025: Publish periodic telemetry for AI tracking
                self._publish_telemetry('status_update', {
                    'is_running': status.get('is_running'),
                    'stablecoin_reserve': status.get('stablecoin_reserve_usd'),
                    'available_funds': status.get('available_for_accumulation'),
                    'pending_opportunities': status.get('pending_opportunities'),
                    'metrics': status.get('metrics'),
                })
                
                # Calculate and publish total portfolio value for profit goal
                total_value = self._calculate_total_portfolio_value()
                if total_value > 0 and self.event_bus:
                    self.event_bus.publish('wallet.intelligence.portfolio_value', {
                        'total_usd': total_value,
                        'stablecoin_reserve': status.get('stablecoin_reserve_usd', 0),
                        'utility_coins_value': total_value - status.get('stablecoin_reserve_usd', 0),
                        'coins_owned': status.get('coins_owned', {}),
                        'timestamp': datetime.now().isoformat(),
                    })
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
    
    def _calculate_total_portfolio_value(self) -> float:
        """Calculate total portfolio value in USD."""
        total = 0.0
        for symbol, holding in self.holdings.items():
            total += holding.usd_value
        return total
    
    async def _accumulation_loop(self) -> None:
        """Loop to process accumulation opportunities."""
        while self.is_running:
            try:
                if not self.auto_execute:
                    await asyncio.sleep(30)
                    continue
                
                # Process pending opportunities
                for opp in list(self.opportunities):
                    if opp.executed or opp.is_expired():
                        continue
                    
                    if opp.action == AccumulationAction.BUY_DIP:
                        await self.execute_accumulation(opp)
                    elif opp.action == AccumulationAction.COMPOUND_MINING_REWARD:
                        await self.execute_compound(opp)
                    
                    await asyncio.sleep(5)  # Rate limit
                
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in accumulation loop: {e}")
                await asyncio.sleep(10)
    
    # -------------------------------------------------------------------------
    # Status & Reporting
    # -------------------------------------------------------------------------
    
    def get_accumulation_targets(self) -> Dict[str, CoinConfig]:
        """Get configured accumulation targets."""
        return {
            s: c for s, c in self.coin_configs.items()
            if c.tier == AccumulationTier.UTILITY_ACCUMULATION
        }
    
    def get_mined_coins(self) -> Dict[str, CoinConfig]:
        """Get configured mined coins."""
        return {
            s: c for s, c in self.coin_configs.items()
            if c.is_mined
        }
    
    def get_coin_count_summary(self) -> Dict[str, Dict[str, float]]:
        """Get summary of coins owned (the main metric!)."""
        summary = {}
        for symbol, holding in self.holdings.items():
            if holding.quantity > 0:
                summary[symbol] = {
                    'quantity': holding.quantity,
                    'accumulated': holding.total_accumulated,
                    'mined': holding.total_mined,
                    'compounded': holding.total_compounded,
                    'usd_value': holding.usd_value,
                    'avg_cost': holding.avg_cost_basis,
                    'unrealized_pnl': holding.unrealized_pnl,
                    'unrealized_pnl_pct': holding.unrealized_pnl_pct,
                }
        return summary
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the accumulation system."""
        return {
            'is_running': self.is_running,
            'stablecoin_reserve_usd': self.get_total_stablecoin_usd(),
            'available_for_accumulation': self.get_available_for_accumulation(),
            'accumulation_targets': list(self.get_accumulation_targets().keys()),
            'mined_coins': list(self.get_mined_coins().keys()),
            'pending_opportunities': len([o for o in self.opportunities if not o.executed]),
            'coins_owned': self.get_coin_count_summary(),
            'metrics': {
                'dip_buys_executed': self.metrics.dip_buys_executed,
                'compound_events': self.metrics.compound_events,
                'total_coins_accumulated': self.metrics.total_coins_accumulated,
                'total_compounded': self.metrics.total_mining_rewards_compounded,
            },
            'timestamp': datetime.now().isoformat(),
        }
    
    def _publish_telemetry(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish telemetry event for AI tracking and observability."""
        if not self.event_bus:
            return
        
        try:
            # Publish to ai.telemetry for Thoth brain and observability
            self.event_bus.publish('ai.telemetry', {
                'event_type': f'accumulation.{event_type}',
                'success': True,
                'data': data,
                'timestamp': datetime.now().isoformat(),
            })
            
            # Also publish to wallet.telemetry for wallet-specific tracking
            self.event_bus.publish('wallet.telemetry', {
                'event_type': f'accumulation.{event_type}',
                'data': data,
                'timestamp': datetime.now().isoformat(),
            })
        except Exception as e:
            logger.debug(f"Error publishing telemetry: {e}")
    
    def _publish_profit_contribution(self, symbol: str, profit_usd: float, source: str) -> None:
        """Publish profit contribution to profit goal tracking system."""
        if not self.event_bus:
            return
        
        try:
            # Contribute to trading.profit.update for progress bar
            self.event_bus.publish('trading.profit.update', {
                'symbol': symbol,
                'realized_pnl': profit_usd,
                'source': f'accumulation_{source}',
                'timestamp': datetime.now().isoformat(),
            })
            
            # Publish to wallet intelligence telemetry
            self._publish_telemetry('profit_contribution', {
                'symbol': symbol,
                'profit_usd': profit_usd,
                'source': source,
                'total_treasury': self.get_total_stablecoin_usd(),
            })
        except Exception as e:
            logger.debug(f"Error publishing profit contribution: {e}")
    
    async def consult_ollama_for_accumulation(
        self, symbol: str, current_price: float, dip_pct: float
    ) -> Optional[Dict[str, Any]]:
        """Consult Ollama/Thoth brain for smart accumulation decision."""
        if not self.event_bus:
            return None
        
        try:
            # Create accumulation query for Thoth brain
            query = {
                'type': 'accumulation_decision',
                'symbol': symbol,
                'current_price': current_price,
                'dip_percentage': dip_pct,
                'available_funds': self.get_available_for_accumulation(),
                'current_holdings': self.holdings.get(symbol, CoinHolding(symbol=symbol, tier=AccumulationTier.UTILITY_ACCUMULATION)).quantity,
                'question': f"Should I accumulate more {symbol} now that it has dipped {dip_pct:.1f}%? "
                           f"Current price: ${current_price:,.2f}. Available funds: ${self.get_available_for_accumulation():,.2f}",
            }
            
            # Publish query to Thoth brain
            self.event_bus.publish('thoth.accumulation.query', query)
            
            # Also publish as ai.telemetry for tracking
            self._publish_telemetry('ollama_query', {
                'symbol': symbol,
                'dip_pct': dip_pct,
                'query_type': 'accumulation_decision',
            })
            
            return query
        except Exception as e:
            logger.error(f"Error consulting Ollama for accumulation: {e}")
            return None
    
    def get_accumulation_report(self) -> str:
        """Generate a human-readable accumulation report."""
        lines = [
            "=" * 60,
            "🪙 COIN ACCUMULATION INTELLIGENCE REPORT",
            "=" * 60,
            f"Mode: Stack Sats (Accumulate COINS, not USD)",
            f"Running: {'✅ Active' if self.is_running else '❌ Stopped'}",
            "",
            "📊 STABLECOIN TREASURY (Tier 1):",
            f"  Total Reserve: ${self.get_total_stablecoin_usd():,.2f}",
            f"  Available for Buys: ${self.get_available_for_accumulation():,.2f}",
            "",
            "🎯 UTILITY COIN HOLDINGS (Tier 2):",
        ]
        
        for symbol, holding in self.holdings.items():
            if holding.tier == AccumulationTier.UTILITY_ACCUMULATION and holding.quantity > 0:
                lines.append(
                    f"  {symbol}: {holding.quantity:.8f} coins "
                    f"(+{holding.total_accumulated:.8f} accumulated) "
                    f"| ${holding.usd_value:,.2f}"
                )
        
        lines.extend([
            "",
            "⛏️ MINING COMPOUND (Tier 3):",
        ])
        
        for symbol, holding in self.holdings.items():
            if holding.tier == AccumulationTier.MINING_COMPOUND and holding.quantity > 0:
                lines.append(
                    f"  {symbol}: {holding.quantity:.8f} coins "
                    f"(mined: {holding.total_mined:.8f}, compounded: {holding.total_compounded:.8f})"
                )
        
        lines.extend([
            "",
            "📈 METRICS:",
            f"  Dip Buys Executed: {self.metrics.dip_buys_executed}",
            f"  Compound Events: {self.metrics.compound_events}",
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)


# -----------------------------------------------------------------------------
# Factory and Singleton
# -----------------------------------------------------------------------------

_accumulation_instance: Optional[CoinAccumulationIntelligence] = None


def get_coin_accumulation_intelligence(
    event_bus: Optional[Any] = None,
    order_executor: Optional[Callable] = None,
    config: Optional[Dict[str, Any]] = None,
) -> CoinAccumulationIntelligence:
    """Get or create the singleton CoinAccumulationIntelligence instance."""
    global _accumulation_instance
    
    if _accumulation_instance is None:
        _accumulation_instance = CoinAccumulationIntelligence(
            event_bus=event_bus,
            order_executor=order_executor,
            config=config,
        )
    elif event_bus and _accumulation_instance.event_bus is None:
        _accumulation_instance.event_bus = event_bus
        _accumulation_instance._setup_subscriptions()
    
    return _accumulation_instance
