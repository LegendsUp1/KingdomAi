#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - Unified Portfolio Manager

SOTA 2026: Cross-system portfolio aggregation for Trading, Mining, and Wallet systems.
Provides unified view of all assets and automated profit routing.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger('KingdomAI.UnifiedPortfolio')


@dataclass
class PortfolioAsset:
    """Single asset in the unified portfolio."""
    symbol: str
    total_balance: float = 0.0
    wallet_balance: float = 0.0
    exchange_balance: float = 0.0
    mining_pending: float = 0.0
    usd_value: float = 0.0
    usd_price: float = 0.0
    sources: List[str] = field(default_factory=list)
    last_update: float = field(default_factory=time.time)


@dataclass  
class PortfolioMetrics:
    """Portfolio-wide metrics."""
    total_usd_value: float = 0.0
    total_assets: int = 0
    trading_pnl_24h: float = 0.0
    mining_rewards_24h: float = 0.0
    wallet_change_24h: float = 0.0
    top_performers: List[Dict] = field(default_factory=list)
    risk_score: float = 0.0
    diversification_score: float = 0.0
    last_sync: float = field(default_factory=time.time)


class UnifiedPortfolioManager:
    """
    Cross-system portfolio manager for Kingdom AI.
    
    Aggregates and synchronizes data from:
    - WalletManager (on-chain balances)
    - Trading System (exchange balances, positions)
    - Mining System (pending rewards, hashrate value)
    
    Features:
    - Real-time portfolio aggregation
    - Automated profit routing
    - Risk assessment across systems
    - Performance tracking
    """
    
    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None):
        """Initialize unified portfolio manager.
        
        Args:
            event_bus: Event bus for cross-system communication
            config: Configuration options
        """
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Portfolio state
        self.assets: Dict[str, PortfolioAsset] = {}
        self.metrics = PortfolioMetrics()
        self.price_cache: Dict[str, float] = {}
        
        # Component references (populated on initialize)
        self.wallet_manager = None
        self.trading_system = None
        self.mining_system = None
        
        # Sync state
        self._initialized = False
        self._last_sync = 0
        self._sync_interval = config.get('sync_interval', 30)  # seconds
        self._sync_task = None
        
        # Profit routing configuration
        self.auto_reinvest = config.get('auto_reinvest', False)
        self.reinvest_threshold = config.get('reinvest_threshold', 100.0)  # USD
        self.reinvest_targets = config.get('reinvest_targets', {})  # symbol -> percentage
        
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize the unified portfolio manager.
        
        Args:
            event_bus: Event bus for communication
            config: Additional configuration
            
        Returns:
            bool: True if initialization successful
        """
        try:
            if event_bus:
                self.event_bus = event_bus
            if config:
                self.config.update(config)
            
            if self._initialized:
                return True
            
            # Get component references from EventBus
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                self.wallet_manager = self.event_bus.get_component('wallet_system')
                self.trading_system = (
                    self.event_bus.get_component('trading_system')
                    or self.event_bus.get_component('trading_component')
                )
                self.mining_system = self.event_bus.get_component('mining_system')
                
                if self.wallet_manager:
                    self.logger.info("✅ Connected to WalletManager")
                if self.trading_system:
                    self.logger.info("✅ Connected to TradingSystem")
                if self.mining_system:
                    self.logger.info("✅ Connected to MiningSystem")
            
            # Subscribe to cross-system events
            self._setup_event_handlers()
            
            # Register self with EventBus
            if self.event_bus and hasattr(self.event_bus, 'register_component'):
                self.event_bus.register_component('unified_portfolio', self)
            
            # Initial sync
            await self.sync_portfolio()
            
            # Start periodic sync
            self._start_sync_loop()
            
            self._initialized = True
            self.logger.info("✅ UnifiedPortfolioManager initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize UnifiedPortfolioManager: {e}")
            return False
    
    def _setup_event_handlers(self):
        """Set up event handlers for cross-system integration."""
        if not self.event_bus:
            return
        
        try:
            # Wallet events
            self.event_bus.subscribe('wallet.balance.updated', self._handle_wallet_update)
            self.event_bus.subscribe('wallet.trading_profit.deposited', self._handle_profit_deposited)
            self.event_bus.subscribe('wallet.mining_payout.received', self._handle_mining_payout)
            
            # Trading events
            self.event_bus.subscribe('trading.position.closed', self._handle_position_closed)
            self.event_bus.subscribe('trading.profit.realized', self._handle_trading_profit)
            self.event_bus.subscribe('trading.balance.update', self._handle_exchange_balance)
            
            # Mining events
            self.event_bus.subscribe('mining.reward_update', self._handle_mining_reward)
            self.event_bus.subscribe('mining.hashrate_update', self._handle_hashrate_update)
            
            # Market events
            self.event_bus.subscribe('market.prices', self._handle_price_update)
            
            # Portfolio requests
            self.event_bus.subscribe('portfolio.unified.request', self._handle_portfolio_request)
            
            self.logger.info("✅ Event handlers configured for unified portfolio")
            
        except Exception as e:
            self.logger.error(f"Error setting up event handlers: {e}")
    
    def _start_sync_loop(self):
        """Start periodic portfolio sync in background."""
        import threading
        
        def sync_loop():
            while True:
                try:
                    time.sleep(self._sync_interval)
                    # Run sync in a new event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.sync_portfolio())
                    loop.close()
                except Exception as e:
                    self.logger.debug(f"Sync loop iteration: {e}")
        
        self._sync_task = threading.Thread(target=sync_loop, daemon=True, name="UnifiedPortfolioSync")
        self._sync_task.start()
        self.logger.info("✅ Portfolio sync loop started")
    
    async def sync_portfolio(self) -> Dict[str, Any]:
        """Synchronize portfolio data from all systems.
        
        Returns:
            dict: Unified portfolio data
        """
        try:
            start_time = time.time()
            
            # Reset aggregation
            aggregated: Dict[str, PortfolioAsset] = {}
            
            # 1. Get wallet balances
            wallet_data = await self._get_wallet_data()
            for symbol, balance in wallet_data.items():
                if symbol not in aggregated:
                    aggregated[symbol] = PortfolioAsset(symbol=symbol)
                aggregated[symbol].wallet_balance = balance
                aggregated[symbol].total_balance += balance
                if 'wallet' not in aggregated[symbol].sources:
                    aggregated[symbol].sources.append('wallet')
            
            # 2. Get exchange balances
            exchange_data = await self._get_exchange_data()
            for symbol, balance in exchange_data.items():
                if symbol not in aggregated:
                    aggregated[symbol] = PortfolioAsset(symbol=symbol)
                aggregated[symbol].exchange_balance = balance
                aggregated[symbol].total_balance += balance
                if 'exchange' not in aggregated[symbol].sources:
                    aggregated[symbol].sources.append('exchange')
            
            # 3. Get pending mining rewards
            mining_data = await self._get_mining_data()
            for symbol, pending in mining_data.items():
                if symbol not in aggregated:
                    aggregated[symbol] = PortfolioAsset(symbol=symbol)
                aggregated[symbol].mining_pending = pending
                # Don't add to total until confirmed
                if 'mining' not in aggregated[symbol].sources:
                    aggregated[symbol].sources.append('mining')
            
            # 4. Calculate USD values
            total_usd = 0.0
            for symbol, asset in aggregated.items():
                price = self.price_cache.get(symbol.upper(), 0.0)
                if symbol.upper() in ('USDT', 'USDC', 'DAI', 'BUSD', 'USD'):
                    price = 1.0
                
                asset.usd_price = price
                asset.usd_value = asset.total_balance * price
                asset.last_update = time.time()
                total_usd += asset.usd_value
            
            # Update state
            self.assets = aggregated
            self.metrics.total_usd_value = total_usd
            self.metrics.total_assets = len([a for a in aggregated.values() if a.total_balance > 0])
            self.metrics.last_sync = time.time()
            self._last_sync = time.time()
            
            # Calculate diversification score
            if total_usd > 0:
                weights = [a.usd_value / total_usd for a in aggregated.values() if a.usd_value > 0]
                # Herfindahl-Hirschman Index (lower = more diversified)
                hhi = sum(w**2 for w in weights)
                self.metrics.diversification_score = max(0, min(100, (1 - hhi) * 100))
            
            # Publish update
            if self.event_bus:
                self.event_bus.publish('portfolio.unified.update', {
                    'total_usd': total_usd,
                    'assets_count': self.metrics.total_assets,
                    'diversification': self.metrics.diversification_score,
                    'sync_time': time.time() - start_time,
                    'timestamp': time.time()
                })
            
            self.logger.info(f"📊 Portfolio synced: ${total_usd:,.2f} across {self.metrics.total_assets} assets")
            
            return self.get_portfolio_summary()
            
        except Exception as e:
            self.logger.error(f"Error syncing portfolio: {e}")
            return {}
    
    async def _get_wallet_data(self) -> Dict[str, float]:
        """Get balances from wallet system."""
        try:
            if self.wallet_manager and hasattr(self.wallet_manager, 'get_all_balances'):
                balances = self.wallet_manager.get_all_balances()
                return {k.upper(): v for k, v in balances.items() if v > 0}
            return {}
        except Exception as e:
            self.logger.debug(f"Error getting wallet data: {e}")
            return {}
    
    async def _get_exchange_data(self) -> Dict[str, float]:
        """Get balances from trading/exchange system."""
        try:
            if self.trading_system and hasattr(self.trading_system, 'get_real_portfolio_balances'):
                portfolio = self.trading_system.get_real_portfolio_balances()
                if isinstance(portfolio, dict):
                    result: Dict[str, float] = {}
                    for k, v in portfolio.items():
                        symbol = str(k).upper()
                        total = 0.0
                        if isinstance(v, dict):
                            total_raw = v.get('total', 0)
                            try:
                                total = float(total_raw)
                            except (TypeError, ValueError):
                                total = 0.0
                        elif isinstance(v, (int, float)):
                            total = float(v)
                        if total > 0:
                            result[symbol] = total
                    if result:
                        return result

            # Fallback for trading component position snapshots.
            if self.trading_system and hasattr(self.trading_system, 'positions'):
                positions = getattr(self.trading_system, 'positions', {})
                if isinstance(positions, dict):
                    aggregated: Dict[str, float] = {}
                    for pos in positions.values():
                        if not isinstance(pos, dict):
                            continue
                        symbol = str(pos.get('asset') or pos.get('symbol') or '').upper()
                        qty_raw = pos.get('quantity', 0)
                        try:
                            qty = float(qty_raw)
                        except (TypeError, ValueError):
                            qty = 0.0
                        if symbol and qty > 0:
                            aggregated[symbol] = aggregated.get(symbol, 0.0) + qty
                    if aggregated:
                        return aggregated
            return {}
        except Exception as e:
            self.logger.debug(f"Error getting exchange data: {e}")
            return {}
    
    async def _get_mining_data(self) -> Dict[str, float]:
        """Get pending mining rewards."""
        try:
            if self.mining_system and hasattr(self.mining_system, 'get_mining_rewards'):
                rewards = self.mining_system.get_mining_rewards()
                return {k.upper(): v for k, v in rewards.items() if v > 0}
            return {}
        except Exception as e:
            self.logger.debug(f"Error getting mining data: {e}")
            return {}
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio summary.
        
        Returns:
            dict: Portfolio summary with all metrics
        """
        try:
            # Top assets by value
            sorted_assets = sorted(
                [(s, a) for s, a in self.assets.items() if a.usd_value > 0],
                key=lambda x: x[1].usd_value,
                reverse=True
            )
            
            top_assets = [
                {
                    'symbol': s,
                    'balance': a.total_balance,
                    'usd_value': a.usd_value,
                    'sources': a.sources
                }
                for s, a in sorted_assets[:10]
            ]
            
            return {
                'total_usd': self.metrics.total_usd_value,
                'assets_count': self.metrics.total_assets,
                'top_assets': top_assets,
                'trading_pnl_24h': self.metrics.trading_pnl_24h,
                'mining_rewards_24h': self.metrics.mining_rewards_24h,
                'diversification_score': self.metrics.diversification_score,
                'risk_score': self.metrics.risk_score,
                'last_sync': self.metrics.last_sync,
                'sources': {
                    'wallet': sum(1 for a in self.assets.values() if 'wallet' in a.sources),
                    'exchange': sum(1 for a in self.assets.values() if 'exchange' in a.sources),
                    'mining': sum(1 for a in self.assets.values() if 'mining' in a.sources)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio summary: {e}")
            return {}
    
    def get_total_value(self) -> float:
        """Get total portfolio value in USD.
        
        Returns:
            float: Total USD value
        """
        return self.metrics.total_usd_value
    
    # Event Handlers
    
    def _handle_wallet_update(self, event_data):
        """Handle wallet balance update."""
        try:
            if not event_data:
                return
            
            coin = event_data.get('coin', '').upper()
            new_balance = event_data.get('new_balance', 0)
            
            if coin in self.assets:
                self.assets[coin].wallet_balance = new_balance
                self.assets[coin].total_balance = (
                    self.assets[coin].wallet_balance + 
                    self.assets[coin].exchange_balance
                )
                self.assets[coin].last_update = time.time()
                
                # Recalculate USD value
                price = self.price_cache.get(coin, 0)
                self.assets[coin].usd_value = self.assets[coin].total_balance * price
                
        except Exception as e:
            self.logger.debug(f"Error handling wallet update: {e}")
    
    def _handle_profit_deposited(self, event_data):
        """Handle trading profit deposited."""
        try:
            profit = event_data.get('profit', 0)
            self.metrics.trading_pnl_24h += profit
            
            # Check auto-reinvest threshold
            if self.auto_reinvest and profit >= self.reinvest_threshold:
                self._process_reinvestment(profit)
                
        except Exception as e:
            self.logger.debug(f"Error handling profit deposit: {e}")
    
    def _handle_mining_payout(self, event_data):
        """Handle mining payout received."""
        try:
            amount = event_data.get('amount', 0)
            coin = event_data.get('coin', 'BTC').upper()
            
            # Add to 24h mining rewards
            price = self.price_cache.get(coin, 0)
            usd_value = amount * price
            self.metrics.mining_rewards_24h += usd_value
            
        except Exception as e:
            self.logger.debug(f"Error handling mining payout: {e}")
    
    def _handle_position_closed(self, event_data):
        """Handle trading position closed."""
        try:
            pnl = event_data.get('pnl', 0)
            self.metrics.trading_pnl_24h += pnl
        except Exception as e:
            self.logger.debug(f"Error handling position closed: {e}")
    
    def _handle_trading_profit(self, event_data):
        """Handle realized trading profit."""
        try:
            profit = event_data.get('profit', 0)
            self.metrics.trading_pnl_24h += profit
        except Exception as e:
            self.logger.debug(f"Error handling trading profit: {e}")
    
    def _handle_exchange_balance(self, event_data):
        """Handle exchange balance update."""
        try:
            coin = event_data.get('coin', '').upper()
            balance = event_data.get('balance', 0)
            
            if coin in self.assets:
                self.assets[coin].exchange_balance = balance
                self.assets[coin].total_balance = (
                    self.assets[coin].wallet_balance + 
                    self.assets[coin].exchange_balance
                )
                
        except Exception as e:
            self.logger.debug(f"Error handling exchange balance: {e}")
    
    def _handle_mining_reward(self, event_data):
        """Handle mining reward update."""
        try:
            estimated_reward = event_data.get('estimated_reward', 0)
            coin = event_data.get('coin', 'BTC').upper()
            
            price = self.price_cache.get(coin, 0)
            usd_value = estimated_reward * price
            self.metrics.mining_rewards_24h += usd_value
            
        except Exception as e:
            self.logger.debug(f"Error handling mining reward: {e}")
    
    def _handle_hashrate_update(self, event_data):
        """Handle hashrate update - can affect portfolio value via mining potential."""
        try:
            if not isinstance(event_data, dict):
                return
            hashrate = event_data.get('hashrate', 0)
            algorithm = event_data.get('algorithm', 'unknown')
            estimated_daily = event_data.get('estimated_daily_reward', 0)

            if not hasattr(self, '_mining_stats'):
                self._mining_stats = {}
            self._mining_stats['hashrate'] = hashrate
            self._mining_stats['algorithm'] = algorithm
            self._mining_stats['last_update'] = time.time()

            if estimated_daily:
                btc_price = self.price_cache.get('BTC', 0)
                if btc_price > 0:
                    daily_usd = float(estimated_daily) * btc_price
                    self._mining_stats['estimated_daily_usd'] = daily_usd
                    self.logger.debug(
                        "Hashrate update: %s H/s (%s), est. daily: $%.2f",
                        hashrate, algorithm, daily_usd
                    )
        except Exception as e:
            self.logger.debug("Error handling hashrate update: %s", e)
    
    def _handle_price_update(self, event_data):
        """Handle market price update."""
        try:
            prices = event_data.get('prices', {})
            self.price_cache.update({k.upper(): v for k, v in prices.items()})
            
            # Also update wallet manager's price cache
            if self.wallet_manager and hasattr(self.wallet_manager, 'update_price_cache'):
                self.wallet_manager.update_price_cache(prices)
                
        except Exception as e:
            self.logger.debug(f"Error handling price update: {e}")
    
    def _handle_portfolio_request(self, event_data):
        """Handle portfolio data request."""
        try:
            summary = self.get_portfolio_summary()
            
            if self.event_bus:
                self.event_bus.publish('portfolio.unified.response', summary)
                
        except Exception as e:
            self.logger.error(f"Error handling portfolio request: {e}")
    
    def _process_reinvestment(self, amount: float):
        """Process automatic profit reinvestment.
        
        Args:
            amount: Amount to reinvest in USD
        """
        try:
            if not self.reinvest_targets:
                return
            
            self.logger.info(f"🔄 Processing auto-reinvestment: ${amount:.2f}")
            
            for symbol, percentage in self.reinvest_targets.items():
                invest_amount = amount * (percentage / 100)
                
                # Publish reinvestment order
                if self.event_bus:
                    self.event_bus.publish('trading.order.create', {
                        'symbol': f"{symbol}/USDT",
                        'side': 'buy',
                        'amount_usd': invest_amount,
                        'type': 'market',
                        'source': 'auto_reinvest'
                    })
                
                self.logger.info(f"📈 Reinvesting ${invest_amount:.2f} in {symbol}")
                
        except Exception as e:
            self.logger.error(f"Error processing reinvestment: {e}")
    
    async def stop(self) -> bool:
        """Stop the portfolio manager."""
        try:
            self._initialized = False
            self.logger.info("UnifiedPortfolioManager stopped")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping UnifiedPortfolioManager: {e}")
            return False
