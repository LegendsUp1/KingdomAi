#!/usr/bin/env python3
"""
LIVE Portfolio Analytics - Real Wallet Balance Aggregation
Aggregates balances from exchanges and blockchains
NO MOCK DATA - 100% LIVE
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from core.event_bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class PortfolioAsset:
    """Portfolio asset data."""
    symbol: str
    amount: float
    usd_value: float
    source: str  # 'exchange' or 'blockchain'
    source_name: str  # e.g., 'binance' or 'ethereum'
    allocation_percent: float
    price: float
    cost_basis: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics."""
    total_value: float
    total_pnl: float
    total_pnl_percent: float
    day_change: float
    day_change_percent: float
    week_change: float
    week_change_percent: float
    best_performer: Optional[PortfolioAsset]
    worst_performer: Optional[PortfolioAsset]
    asset_count: int
    timestamp: float


class LivePortfolioAnalytics:
    """
    LIVE Portfolio Analytics
    Aggregates real wallet balances from exchanges and blockchains
    """
    
    def __init__(self, real_exchange_executor=None, kingdom_web3=None, event_bus=None, stock_executor=None):
        """
        Initialize portfolio analytics.
        
        Args:
            real_exchange_executor: RealExchangeExecutor for exchange balances
            kingdom_web3: KingdomWeb3 for blockchain wallet balances
        """
        self.exchange_executor = real_exchange_executor
        self.kingdom_web3 = kingdom_web3
        self.stock_executor = stock_executor
        self.portfolio_assets: List[PortfolioAsset] = []
        self.portfolio_metrics: Optional[PortfolioMetrics] = None
        self.price_cache: Dict[str, float] = {}
        self.event_bus = event_bus
        try:
            if not self.event_bus:
                self.event_bus = EventBus.get_instance()
        except Exception:
            pass
        try:
            if self.event_bus:
                self.event_bus.subscribe('market:price_update', self._on_market_price_update)
                self.event_bus.subscribe('market.prices', self._on_market_prices_snapshot)
                self.event_bus.subscribe('trading:live_price', self._on_trading_live_price)
        except Exception:
            pass
        
        logger.info("✅ Live Portfolio Analytics initialized")
    
    async def analyze_portfolio(self) -> Tuple[List[PortfolioAsset], PortfolioMetrics]:
        """
        Analyze complete portfolio from all sources.
        
        Returns:
            Tuple of (assets list, metrics)
        """
        try:
            assets = []
            
            exchange_assets = await self._fetch_exchange_balances()
            assets.extend(exchange_assets)

            blockchain_assets = await self._fetch_blockchain_balances()
            assets.extend(blockchain_assets)

            stock_assets = await self._fetch_stock_balances()
            assets.extend(stock_assets)

            metrics = await self._calculate_portfolio_metrics(assets)
            
            self.portfolio_assets = assets
            self.portfolio_metrics = metrics
            
            logger.info(f"📊 Portfolio Analysis Complete:")
            logger.info(f"   Total Value: ${metrics.total_value:,.2f}")
            logger.info(f"   Assets: {metrics.asset_count}")
            logger.info(f"   P&L: ${metrics.total_pnl:,.2f} ({metrics.total_pnl_percent:+.2f}%)")
            
            # Publish a real-data portfolio analytics snapshot for GUI/Thoth consumers
            if self.event_bus:
                try:
                    snapshot_assets = [
                        {
                            'symbol': a.symbol,
                            'amount': a.amount,
                            'usd_value': a.usd_value,
                            'source': a.source,
                            'source_name': a.source_name,
                            'allocation_percent': a.allocation_percent,
                            'price': a.price,
                            'cost_basis': a.cost_basis,
                            'pnl': a.pnl,
                            'pnl_percent': a.pnl_percent,
                        }
                        for a in assets
                    ]
                    snapshot_metrics = {
                        'total_value': metrics.total_value,
                        'total_pnl': metrics.total_pnl,
                        'total_pnl_percent': metrics.total_pnl_percent,
                        'day_change': metrics.day_change,
                        'day_change_percent': metrics.day_change_percent,
                        'week_change': metrics.week_change,
                        'week_change_percent': metrics.week_change_percent,
                        'asset_count': metrics.asset_count,
                        'timestamp': metrics.timestamp,
                    }
                    payload = {
                        'assets': snapshot_assets,
                        'metrics': snapshot_metrics,
                        'timestamp': metrics.timestamp,
                    }
                    self.event_bus.publish("trading.portfolio.analytics.snapshot", payload)
                except Exception as pub_err:
                    logger.error(f"Error publishing portfolio analytics snapshot: {pub_err}")
            
            return assets, metrics
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio: {e}")
            return [], PortfolioMetrics(
                total_value=0.0,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                day_change=0.0,
                day_change_percent=0.0,
                week_change=0.0,
                week_change_percent=0.0,
                best_performer=None,
                worst_performer=None,
                asset_count=0,
                timestamp=datetime.now().timestamp()
            )
    
    async def _fetch_exchange_balances(self) -> List[PortfolioAsset]:
        """
        Fetch real balances from all connected exchanges.
        
        Returns:
            List of portfolio assets from exchanges
        """
        assets = []
        
        if not self.exchange_executor:
            logger.warning("Exchange executor not available")
            return assets
        
        try:
            # Get balances from all connected exchanges
            exchanges = self.exchange_executor.get_connected_exchanges()
            
            for exchange_name in exchanges:
                try:
                    balance = await self.exchange_executor.get_balance(exchange_name)
                    
                    if not balance:
                        continue
                    
                    for currency, amount in balance.items():
                        if amount > 0.00001:  # Filter dust
                            # Get USD price
                            price = await self._get_price(currency, exchange_name)
                            usd_value = amount * price
                            
                            if usd_value > 0.01:  # Filter very small amounts
                                asset = PortfolioAsset(
                                    symbol=currency,
                                    amount=amount,
                                    usd_value=usd_value,
                                    source='exchange',
                                    source_name=exchange_name,
                                    allocation_percent=0.0,  # Calculated later
                                    price=price
                                )
                                assets.append(asset)
                                
                                logger.debug(f"   {exchange_name.upper()}: {amount:.6f} {currency} = ${usd_value:,.2f}")
                    
                except Exception as e:
                    logger.error(f"Error fetching balance from {exchange_name}: {e}")
            
            logger.info(f"✅ Fetched {len(assets)} assets from {len(exchanges)} exchanges")
            
        except Exception as e:
            logger.error(f"Error fetching exchange balances: {e}")
        
        return assets
    
    async def _fetch_blockchain_balances(self) -> List[PortfolioAsset]:
        """
        Fetch real balances from blockchain wallets.
        
        Returns:
            List of portfolio assets from blockchains
        """
        assets = []
        
        if not self.kingdom_web3:
            logger.warning("KingdomWeb3 not available")
            return assets
        
        try:
            # Integrate with a real KingdomWeb3 wallet registry when available.
            wallets_method = getattr(self.kingdom_web3, 'get_tracked_wallets', None)
            if not callable(wallets_method):
                logger.info("KingdomWeb3 does not expose tracked wallets; skipping blockchain portfolio aggregation")
                return assets

            wallets = wallets_method()
            if not isinstance(wallets, list):
                logger.info("KingdomWeb3 wallet registry returned non-list payload; skipping blockchain balances")
                return assets

            import inspect  # Local import to avoid polluting module namespace

            for entry in wallets:
                try:
                    if not isinstance(entry, dict):
                        continue
                    address = entry.get('address')
                    network = entry.get('network', 'ethereum')
                    symbol = str(entry.get('symbol', 'ETH')).upper()
                    if not address:
                        continue

                    balance_method = getattr(self.kingdom_web3, 'get_balance', None)
                    if not callable(balance_method):
                        continue

                    # Support both async and sync get_balance implementations
                    if inspect.iscoroutinefunction(balance_method):
                        balance = await balance_method(address, network)
                    else:
                        balance = balance_method(address, network)

                    # Only accept numeric or string balances; ignore exotic types
                    if not isinstance(balance, (int, float, str)):
                        continue
                    try:
                        balance_val = float(balance)
                    except (TypeError, ValueError):
                        continue

                    if balance_val <= 0:
                        continue

                    # Best-effort USD valuation using existing price infrastructure
                    price = await self._get_price(symbol, network)
                    try:
                        usd_value = balance_val * float(price or 0.0)
                    except (TypeError, ValueError):
                        usd_value = 0.0

                    if usd_value <= 0:
                        # If we cannot price the asset, do not fabricate a USD value
                        continue

                    assets.append(
                        PortfolioAsset(
                            symbol=symbol,
                            amount=balance_val,
                            usd_value=usd_value,
                            source='blockchain',
                            source_name=network,
                            allocation_percent=0.0,
                            price=float(price or 0.0),
                        )
                    )
                except Exception as e:
                    logger.error(f"Error fetching blockchain balance for wallet entry: {e}")
                    continue

            logger.info(f"✅ Fetched {len(assets)} assets from blockchains")
            
        except Exception as e:
            logger.error(f"Error fetching blockchain balances: {e}")
        
        return assets
    
    async def _fetch_stock_balances(self) -> List[PortfolioAsset]:
        assets: List[PortfolioAsset] = []
        executor = getattr(self, "stock_executor", None)
        if not executor:
            return assets
        try:
            if not hasattr(executor, "get_alpaca_positions"):
                return assets
            data = await executor.get_alpaca_positions()
            if not isinstance(data, dict):
                return assets
            positions = data.get("positions") or []
            cash_val = data.get("cash")
            if isinstance(cash_val, (int, float)):
                cash = float(cash_val)
                if cash > 0:
                    assets.append(
                        PortfolioAsset(
                            symbol="CASH_USD",
                            amount=cash,
                            usd_value=cash,
                            source="stock_broker",
                            source_name="alpaca",
                            allocation_percent=0.0,
                            price=1.0,
                        )
                    )
            for pos in positions:
                if not isinstance(pos, dict):
                    continue
                symbol = str(pos.get("symbol") or "").upper()
                try:
                    qty = float(pos.get("qty") or 0.0)
                except (TypeError, ValueError):
                    qty = 0.0
                if qty == 0:
                    continue
                mv_val = pos.get("market_value")
                try:
                    usd_value = float(mv_val) if mv_val is not None else 0.0
                except (TypeError, ValueError):
                    usd_value = 0.0
                if usd_value <= 0:
                    continue
                avg_val = pos.get("avg_price")
                try:
                    price = float(avg_val) if avg_val is not None else 0.0
                except (TypeError, ValueError):
                    price = 0.0
                upnl_val = pos.get("unrealized_pl")
                try:
                    pnl_val = float(upnl_val) if upnl_val is not None else None
                except (TypeError, ValueError):
                    pnl_val = None
                pnl_pct_val = None
                if pnl_val is not None and usd_value > 0:
                    cost = usd_value - pnl_val
                    if cost > 0:
                        pnl_pct_val = pnl_val / cost * 100.0
                assets.append(
                    PortfolioAsset(
                        symbol=symbol,
                        amount=qty,
                        usd_value=usd_value,
                        source="stock_broker",
                        source_name="alpaca",
                        allocation_percent=0.0,
                        price=price,
                        pnl=pnl_val,
                        pnl_percent=pnl_pct_val,
                    )
                )
        except Exception as e:
            logger.error(f"Error fetching stock balances: {e}")
        return assets
    
    async def _get_price(self, currency: str, exchange_name: str) -> float:
        """
        Get current USD price for currency.
        
        Args:
            currency: Currency symbol
            exchange_name: Exchange name
            
        Returns:
            USD price
        """
        # Check cache (currency -> USD)
        cur = (currency or '').upper()
        if cur in self.price_cache:
            return float(self.price_cache[cur])
        
        # Stablecoins
        if currency in ['USDT', 'USDC', 'DAI', 'BUSD', 'USD']:
            return 1.0
        
        try:
            import ccxt
            
            if hasattr(self.exchange_executor, 'exchanges'):
                exchange = self.exchange_executor.exchanges.get(exchange_name)
                
                if exchange:
                    # Try common pairs
                    for quote in ['USDT', 'USD', 'USDC']:
                        symbol = f"{currency}/{quote}"
                        try:
                            ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)
                            price = ticker.get('last') or ticker.get('close', 0)
                            
                            if price > 0:
                                self.price_cache[currency] = price
                                return price
                        except:
                            continue
            
            return 0.0
            
        except Exception as e:
            logger.debug(f"Error getting price for {currency}: {e}")
            return 0.0

    def _on_market_price_update(self, price_data: Dict):
        try:
            symbol = price_data.get('symbol')
            price = float(price_data.get('price', 0) or 0)
            if not symbol or price <= 0:
                return
            base = symbol.split('/')[0].upper()
            self.price_cache[base] = price
        except Exception:
            pass

    def _on_market_prices_snapshot(self, event_data: Dict):
        try:
            prices = event_data.get('prices', {})
            if not isinstance(prices, dict):
                return
            for sym, pdata in prices.items():
                try:
                    base = str(sym).split('/')[0].upper()
                    p = 0.0
                    if isinstance(pdata, dict):
                        p = float(pdata.get('price', 0) or 0)
                    elif isinstance(pdata, (int, float)):
                        p = float(pdata)
                    if p > 0:
                        self.price_cache[base] = p
                except Exception:
                    continue
        except Exception:
            pass
    
    def _on_trading_live_price(self, event_data: Dict):
        try:
            symbol = event_data.get('symbol')
            price = float(event_data.get('price', 0) or 0)
            if not symbol or price <= 0:
                return
            base = symbol.split('/')[0].upper()
            self.price_cache[base] = price
        except Exception:
            pass
    
    async def _calculate_portfolio_metrics(self, assets: List[PortfolioAsset]) -> PortfolioMetrics:
        """
        Calculate portfolio metrics from assets.
        
        Args:
            assets: List of portfolio assets
            
        Returns:
            Portfolio metrics
        """
        if not assets:
            return PortfolioMetrics(
                total_value=0.0,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                day_change=0.0,
                day_change_percent=0.0,
                week_change=0.0,
                week_change_percent=0.0,
                best_performer=None,
                worst_performer=None,
                asset_count=0,
                timestamp=datetime.now().timestamp()
            )
        
        # Calculate total value
        total_value = sum(asset.usd_value for asset in assets)
        
        # Calculate allocation percentages
        for asset in assets:
            asset.allocation_percent = (asset.usd_value / total_value * 100) if total_value > 0 else 0.0
        
        # Get historical data for P&L (simplified - would use actual historical data)
        # Only use real per-asset pnl values when available
        total_pnl = sum((asset.pnl or 0.0) for asset in assets if asset.pnl is not None)
        day_change = 0.0
        week_change = 0.0
        
        # Find best/worst performers
        best_performer = max(assets, key=lambda a: a.usd_value) if assets else None
        worst_performer = min(assets, key=lambda a: a.usd_value) if assets else None
        
        metrics = PortfolioMetrics(
            total_value=total_value,
            total_pnl=total_pnl,
            total_pnl_percent=(total_pnl / total_value * 100) if total_value > 0 else 0.0,
            day_change=day_change,
            day_change_percent=0.0,
            week_change=week_change,
            week_change_percent=0.0,
            best_performer=best_performer,
            worst_performer=worst_performer,
            asset_count=len(assets),
            timestamp=datetime.now().timestamp()
        )
        
        return metrics
    
    def get_portfolio_summary(self) -> str:
        """
        Get formatted portfolio summary.
        
        Returns:
            Summary string
        """
        if not self.portfolio_metrics:
            return "Portfolio not analyzed yet"
        
        metrics = self.portfolio_metrics
        # Determine if any asset has real P&L data
        has_pnl_assets = any(
            getattr(asset, "pnl", None) is not None for asset in self.portfolio_assets
        )

        if has_pnl_assets and metrics.total_value > 0:
            pnl_line = f"📈 Total P&L: ${metrics.total_pnl:,.2f} ({metrics.total_pnl_percent:+.2f}%)"
        elif has_pnl_assets:
            pnl_line = f"📈 Total P&L: ${metrics.total_pnl:,.2f}"
        else:
            pnl_line = "📈 Total P&L: N/A (no P&L data available)"
        
        summary = f"""
📊 PORTFOLIO SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 Total Value: ${metrics.total_value:,.2f}
{pnl_line}
📊 Assets: {metrics.asset_count}

📅 Day Change: N/A
📅 Week Change: N/A

🏆 Best Performer: {metrics.best_performer.symbol if metrics.best_performer else 'N/A'}
📉 Worst Performer: {metrics.worst_performer.symbol if metrics.worst_performer else 'N/A'}
"""
        
        return summary.strip()
    
    def get_asset_allocation(self) -> Dict[str, float]:
        """
        Get asset allocation breakdown.
        
        Returns:
            Dictionary of symbol -> allocation percentage
        """
        if not self.portfolio_assets:
            return {}
        
        allocation = {}
        for asset in self.portfolio_assets:
            if asset.symbol in allocation:
                allocation[asset.symbol] += asset.allocation_percent
            else:
                allocation[asset.symbol] = asset.allocation_percent
        
        return allocation
    
    def get_source_allocation(self) -> Dict[str, float]:
        """
        Get allocation by source (exchange vs blockchain).
        
        Returns:
            Dictionary of source -> total value
        """
        if not self.portfolio_assets:
            return {}
        
        source_totals = {}
        for asset in self.portfolio_assets:
            source = f"{asset.source}:{asset.source_name}"
            if source in source_totals:
                source_totals[source] += asset.usd_value
            else:
                source_totals[source] = asset.usd_value
        
        return source_totals
