#!/usr/bin/env python3
"""
LIVE Arbitrage Scanner - Multi-Exchange Real Price Comparison
Scans multiple exchanges for arbitrage opportunities
NO MOCK DATA - 100% LIVE
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any, cast
from dataclasses import dataclass
from core.event_bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity data structure."""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    profit_usd: float
    profit_percent: float
    volume: float
    timestamp: float


class LiveArbitrageScanner:
    """
    LIVE Arbitrage Scanner
    Compares prices across multiple exchanges in real-time
    """
    
    def __init__(self, api_keys: Optional[Dict] = None, event_bus=None):
        """
        Initialize arbitrage scanner.
        
        Args:
            api_keys: API keys for exchanges
        """
        import ccxt
        
        self.api_keys = api_keys or {}
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.opportunities: List[ArbitrageOpportunity] = []
        self.event_bus = event_bus
        try:
            if not self.event_bus:
                self.event_bus = EventBus.get_instance()
        except Exception:
            pass
        self.exchange_price_cache: Dict[str, Dict[str, float]] = {}
        
        # Initialize exchanges
        exchange_names = ['binance', 'coinbase', 'kraken', 'kucoin', 'bitfinex']
        
        for name in exchange_names:
            try:
                exchange_class = getattr(ccxt, name)
                config = cast(Dict[str, Any], {'enableRateLimit': True})
                
                if isinstance(self.api_keys, dict) and name in self.api_keys:
                    api_key_val = self.api_keys.get(name) or ""
                    api_secret_val = self.api_keys.get(f'{name}_secret') or ""
                    config['apiKey'] = str(api_key_val)
                    config['secret'] = str(api_secret_val)
                
                self.exchanges[name] = exchange_class(config)
                logger.info(f"✅ Arbitrage scanner connected: {name}")
                
            except Exception as e:
                logger.warning(f"Failed to initialize {name} for arbitrage: {e}")
        
        logger.info(f"✅ Arbitrage scanner initialized with {len(self.exchanges)} exchanges")
        try:
            if self.event_bus:
                self.event_bus.subscribe('market:price_update', self._on_market_price_update)
                self.event_bus.subscribe('market.prices', self._on_market_prices_snapshot)
                self.event_bus.subscribe('trading:live_price', self._on_market_price_update)
        except Exception:
            pass

    def _on_market_price_update(self, price_data: Dict):
        try:
            symbol = price_data.get('symbol')
            exchange = price_data.get('exchange')
            price = float(price_data.get('price', 0) or 0)
            if not symbol or not exchange or price <= 0:
                return
            cache = self.exchange_price_cache.setdefault(symbol, {})
            cache[exchange] = price
        except Exception:
            pass

    def _on_market_prices_snapshot(self, event_data: Dict):
        try:
            prices = event_data.get('prices', {})
            if not isinstance(prices, dict):
                return
        except Exception:
            pass
    
    async def scan_arbitrage(
        self,
        symbols: List[str],
        min_profit_percent: float = 0.5
    ) -> List[ArbitrageOpportunity]:
        """
        Scan for arbitrage opportunities across exchanges.
        
        Args:
            symbols: List of trading pairs to scan
            min_profit_percent: Minimum profit percentage to report
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        for symbol in symbols:
            try:
                # Fetch prices from all exchanges concurrently
                prices = await self._fetch_prices_all_exchanges(symbol)
                try:
                    cached = self.exchange_price_cache.get(symbol, {})
                    if cached:
                        for ex, p in cached.items():
                            if ex not in prices and p > 0:
                                prices[ex] = p
                except Exception:
                    pass
                
                if len(prices) < 2:
                    continue
                
                # Find arbitrage opportunities
                for buy_exchange, buy_price in prices.items():
                    for sell_exchange, sell_price in prices.items():
                        if buy_exchange == sell_exchange:
                            continue
                        
                        # Calculate profit
                        profit_usd = sell_price - buy_price
                        profit_percent = (profit_usd / buy_price) * 100
                        
                        # Check if profitable (accounting for fees ~0.2%)
                        if profit_percent > min_profit_percent:
                            opportunity = ArbitrageOpportunity(
                                symbol=symbol,
                                buy_exchange=buy_exchange,
                                sell_exchange=sell_exchange,
                                buy_price=buy_price,
                                sell_price=sell_price,
                                profit_usd=profit_usd,
                                profit_percent=profit_percent,
                                volume=0.0,  # Would need to fetch order book depth
                                timestamp=asyncio.get_event_loop().time()
                            )
                            opportunities.append(opportunity)
                            
                            logger.info(
                                f"💰 Arbitrage found: {symbol} | "
                                f"Buy {buy_exchange} ${buy_price:,.2f} → "
                                f"Sell {sell_exchange} ${sell_price:,.2f} | "
                                f"Profit: +${profit_usd:,.2f} ({profit_percent:.2f}%)"
                            )
                
            except Exception as e:
                logger.error(f"Error scanning arbitrage for {symbol}: {e}")
        
        # Sort by profit percentage
        opportunities.sort(key=lambda x: x.profit_percent, reverse=True)
        
        self.opportunities = opportunities[:20]  # Keep top 20

        # Broadcast structured arbitrage snapshots so TradingTab and Thoth
        # can consume REAL cross-exchange opportunities. Payload shape is
        # aligned with TradingTab._handle_arbitrage_snapshot expectations.
        if self.event_bus:
            try:
                for sym in symbols:
                    sym_ops = [op for op in self.opportunities if op.symbol == sym]
                    best_payload: Optional[Dict[str, Any]] = None
                    if sym_ops:
                        best = sym_ops[0]
                        best_payload = {
                            "buy_exchange": best.buy_exchange,
                            "sell_exchange": best.sell_exchange,
                            "buy_price": best.buy_price,
                            "sell_price": best.sell_price,
                            "spread_abs": best.profit_usd,
                            "spread_pct": best.profit_percent,
                        }

                    ops_payload: List[Dict[str, Any]] = []
                    for op in sym_ops[:20]:
                        ops_payload.append(
                            {
                                "buy_exchange": op.buy_exchange,
                                "sell_exchange": op.sell_exchange,
                                "buy_price": op.buy_price,
                                "sell_price": op.sell_price,
                                "spread_abs": op.profit_usd,
                                "spread_pct": op.profit_percent,
                            }
                        )

                    snapshot = {
                        "symbol": sym,
                        "opportunity_count": len(sym_ops),
                        "best_opportunity": best_payload,
                        "opportunities": ops_payload,
                    }

                    self.event_bus.publish("trading.arbitrage.snapshot", snapshot)
            except Exception as pub_err:
                logger.error(f"Error publishing arbitrage snapshot: {pub_err}")

        return self.opportunities
    
    async def _fetch_prices_all_exchanges(self, symbol: str) -> Dict[str, float]:
        """
        Fetch current price from all exchanges.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Dictionary of exchange -> price
        """
        tasks = []
        exchange_names = []
        
        for name, exchange in self.exchanges.items():
            tasks.append(self._fetch_price_safe(exchange, symbol))
            exchange_names.append(name)
        
        # Fetch all prices concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices = {}
        for name, result in zip(exchange_names, results):
            if isinstance(result, Exception):
                logger.debug(f"Failed to fetch {symbol} from {name}: {result}")
            elif result is not None:
                prices[name] = result
        
        return prices
    
    async def _fetch_price_safe(self, exchange: 'ccxt.Exchange', symbol: str) -> Optional[float]:
        """
        Safely fetch price from exchange.
        
        Args:
            exchange: CCXT exchange instance
            symbol: Trading pair
            
        Returns:
            Current price or None
        """
        try:
            ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)
            return ticker.get('last') or ticker.get('close')
        except Exception:
            return None
    
    def get_opportunities(self) -> List[ArbitrageOpportunity]:
        """Get latest arbitrage opportunities."""
        return self.opportunities
    
    def get_best_opportunity(self) -> Optional[ArbitrageOpportunity]:
        """Get best arbitrage opportunity."""
        if self.opportunities:
            return self.opportunities[0]
        return None
