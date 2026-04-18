"""
State-of-the-art Funding Rate Arbitrage Module for Kingdom AI (2025)
Implements advanced funding rate arbitrage strategies for perpetual futures trading.
"""
import logging
import time
import numpy as np
import pandas as pd

from core.base_component import BaseComponent
from utils.redis_client import RedisClient
from utils.async_utils import AsyncSupport

class FundingRateArbitrage(BaseComponent):
    """
    Advanced funding rate arbitrage implementation based on 2025 trading research.
    Implements both cross-exchange and spot-perpetual arbitrage strategies.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the funding rate arbitrage component with event bus integration."""
        super().__init__("FundingRateArbitrage", event_bus, config)
        self.redis_client = None
        self.active_strategies = {}
        self.funding_rates_history = {}
        self.basis_tracking = {}
        self.current_positions = {}
        self.cross_exchange_opportunities = []
        self.spot_perp_opportunities = []
        
        # Advanced configuration
        self.config = config or {
            "min_funding_rate_threshold": 0.01,  # 1% daily equivalent
            "max_position_size": 10.0,  # BTC equivalent
            "position_sizing_volatility_factor": 0.5,
            "min_liquidity_threshold": 1000000,  # USD
            "max_slippage_bps": 10,  # basis points
            "funding_interval_hours": 8,
            "position_hold_intervals": 3,
            "open_interest_minimum_ratio": 0.1,
            "basis_control_threshold": 0.05,
            "delta_neutral_tolerance": 0.02,
            "exchanges": ["binance", "okx", "bybit", "deribit", "gate"],
            "trading_pairs": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "AVAX-USDT"]
        }
        
        # ML model settings
        self.volatility_prediction_enabled = True
        self.optimal_entry_exit_ml_enabled = True
        
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def initialize(self):
        """Initialize the component and connect to Redis Quantum Nexus."""
        self.logger.info("Initializing Funding Rate Arbitrage Component")
        
        # Connect to Redis Quantum Nexus
        try:
            self.redis_client = RedisClient(
                host="localhost", 
                port=6380,
                password="QuantumNexus2025",
                db=0,
                decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            self.logger.info("Successfully connected to Redis Quantum Nexus")
        except Exception as e:
            self.logger.critical(f"Failed to connect to Redis Quantum Nexus: {e}")
            # Enforcing no fallback policy
            raise SystemExit("Critical failure: Redis Quantum Nexus connection failed. Halting system.")
            
        # Register event handlers
        if self.event_bus:
            await self.event_bus.subscribe("market_data_update", self.on_market_data_update)
            await self.event_bus.subscribe("funding_rate_update", self.on_funding_rate_update)
            await self.event_bus.subscribe("trade_executed", self.on_trade_executed)
            await self.event_bus.subscribe("position_update", self.on_position_update)
            await self.event_bus.subscribe("system_shutdown", self.on_shutdown)
            
        # Initialize historical data
        await self.load_historical_funding_rates()
        await self.calculate_funding_statistics()
        
        # Start background tasks
        AsyncSupport.create_background_task(self.monitor_funding_opportunities())
        AsyncSupport.create_background_task(self.execute_arbitrage_strategies())
        AsyncSupport.create_background_task(self.risk_monitoring_task())
        
        self.logger.info("Funding Rate Arbitrage Component initialized successfully")
        return True
        
    async def load_historical_funding_rates(self):
        """Load and analyze historical funding rates from Redis Quantum Nexus."""
        self.logger.info("Loading historical funding rates data")
        
        try:
            # Get the last 30 days of funding rate data
            for exchange in self.config["exchanges"]:
                for pair in self.config["trading_pairs"]:
                    key = f"funding_rates:{exchange}:{pair}"
                    raw_data = await self.redis_client.hgetall(key)
                    
                    if not raw_data:
                        self.logger.warning(f"No historical funding rate data for {exchange}:{pair}")
                        continue
                    
                    # Convert to DataFrame for analysis
                    df = pd.DataFrame(
                        [(float(ts), float(rate)) for ts, rate in raw_data.items()],
                        columns=['timestamp', 'rate']
                    )
                    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
                    df.set_index('datetime', inplace=True)
                    
                    # Store data
                    self.funding_rates_history[(exchange, pair)] = df
                    
                    self.logger.debug(f"Loaded {len(df)} funding rate records for {exchange}:{pair}")
                    
            self.logger.info(f"Successfully loaded historical funding rates for {len(self.funding_rates_history)} pairs")
        except Exception as e:
            self.logger.error(f"Error loading historical funding rates: {e}")
            # Critical component, no fallback allowed
            raise
    
    async def calculate_funding_statistics(self):
        """Calculate statistical metrics for funding rates to identify arbitrage opportunities."""
        stats = {}
        
        for (exchange, pair), df in self.funding_rates_history.items():
            if df.empty:
                continue
                
            # Calculate key statistics
            stats[(exchange, pair)] = {
                "mean": df['rate'].mean(),
                "std": df['rate'].std(),
                "min": df['rate'].min(),
                "max": df['rate'].max(),
                "last": df['rate'].iloc[-1] if not df.empty else 0,
                "volatility": df['rate'].rolling(24).std().mean(),
                "trend": np.polyfit(range(len(df)), df['rate'].values, 1)[0] if len(df) > 1 else 0
            }
            
        # Store stats in Redis for other components to access
        for (exchange, pair), metrics in stats.items():
            key = f"funding_stats:{exchange}:{pair}"
            metric_payload = {k: str(v) for k, v in metrics.items()}
            if hasattr(self.redis_client, "hset"):
                await self.redis_client.hset(key, mapping=metric_payload)
            else:
                await self.redis_client.hmset(key, metric_payload)
            
        # Publish stats to event bus
        if self.event_bus:
            await self.event_bus.publish("funding_stats_updated", {
                "stats": stats,
                "timestamp": time.time()
            })
            
        return stats
        
    # Event handlers will be implemented in additional updates
    
    async def on_market_data_update(self, data):
        """Handle market data updates for arbitrage calculations."""
        if not isinstance(data, dict):
            return
        symbol = data.get('symbol', '')
        price = data.get('price', 0)
        exchange = data.get('exchange', '')
        if symbol and price and exchange:
            if not hasattr(self, '_market_prices'):
                self._market_prices = {}
            self._market_prices.setdefault(symbol, {})[exchange] = float(price)
            spreads = self._market_prices.get(symbol, {})
            if len(spreads) >= 2:
                prices = list(spreads.values())
                spread_pct = abs(max(prices) - min(prices)) / min(prices) * 100
                if spread_pct > self.config.get('min_spread_threshold', 0.1):
                    self.logger.info(f"Arbitrage opportunity: {symbol} spread={spread_pct:.3f}%")
                    if self.event_bus:
                        await self.event_bus.publish("arbitrage.opportunity", {
                            "symbol": symbol,
                            "spread_pct": spread_pct,
                            "prices": spreads
                        })
        
    async def on_funding_rate_update(self, data):
        """Process new funding rate information."""
        if not isinstance(data, dict):
            return
        exchange = data.get('exchange', '')
        pair = data.get('pair', '')
        rate = data.get('rate')
        timestamp = data.get('timestamp', time.time())
        if not all([exchange, pair, rate is not None]):
            return
        key = (exchange, pair)
        if key not in self.funding_rates_history:
            self.funding_rates_history[key] = pd.DataFrame(columns=['timestamp', 'rate'])
        new_row = pd.DataFrame([{'timestamp': timestamp, 'rate': float(rate)}])
        self.funding_rates_history[key] = pd.concat(
            [self.funding_rates_history[key], new_row], ignore_index=True
        )
        await self.redis_client.hset(
            f"funding_rates:{exchange}:{pair}",
            str(timestamp), str(rate)
        )
        self.logger.debug(f"Funding rate update: {exchange}:{pair} rate={rate}")
        
    async def on_trade_executed(self, data):
        """Update position tracking after trade execution."""
        if not isinstance(data, dict):
            return
        execution_id = data.get('execution_id', '')
        symbol = data.get('symbol', '')
        side = data.get('side', '')
        quantity = float(data.get('quantity', 0))
        price = float(data.get('price', 0))
        exchange = data.get('exchange', '')
        if not all([symbol, side, quantity, price, exchange]):
            return
        pos_key = f"{exchange}:{symbol}"
        if pos_key not in self.current_positions:
            self.current_positions[pos_key] = {
                'exchange': exchange, 'symbol': symbol,
                'net_quantity': 0.0, 'avg_price': 0.0,
                'realized_pnl': 0.0, 'trades': []
            }
        pos = self.current_positions[pos_key]
        signed_qty = quantity if side == 'buy' else -quantity
        old_qty = pos['net_quantity']
        new_qty = old_qty + signed_qty
        if abs(new_qty) > abs(old_qty):
            total_cost = pos['avg_price'] * abs(old_qty) + price * quantity
            pos['avg_price'] = total_cost / abs(new_qty) if new_qty != 0 else 0.0
        elif old_qty != 0 and abs(new_qty) < abs(old_qty):
            pnl = (price - pos['avg_price']) * quantity * (1 if old_qty > 0 else -1)
            pos['realized_pnl'] += pnl
        pos['net_quantity'] = new_qty
        pos['trades'].append({
            'execution_id': execution_id, 'side': side,
            'quantity': quantity, 'price': price,
            'timestamp': data.get('timestamp', time.time())
        })
        self.logger.info(f"Trade executed: {side} {quantity} {symbol}@{price} on {exchange}")
        
    async def on_position_update(self, data):
        """Track current positions for arbitrage strategies."""
        if not isinstance(data, dict):
            return
        exchange = data.get('exchange', '')
        symbol = data.get('symbol', '')
        if not exchange or not symbol:
            return
        pos_key = f"{exchange}:{symbol}"
        self.current_positions[pos_key] = {
            'exchange': exchange,
            'symbol': symbol,
            'net_quantity': float(data.get('quantity', 0)),
            'avg_price': float(data.get('entry_price', 0)),
            'unrealized_pnl': float(data.get('unrealized_pnl', 0)),
            'margin_used': float(data.get('margin_used', 0)),
            'liquidation_price': float(data.get('liquidation_price', 0)),
            'updated_at': data.get('timestamp', time.time())
        }
        self.logger.debug(f"Position update: {pos_key} qty={data.get('quantity')}")
        
    async def on_shutdown(self, data):
        """Clean up resources on system shutdown."""
        self.logger.info("Shutting down Funding Rate Arbitrage Component")
        # Close connections and clean up
        if self.redis_client:
            await self.redis_client.close()
            
    # Core arbitrage logic will be implemented in additional updates
    
    async def monitor_funding_opportunities(self):
        """Monitor for funding rate arbitrage opportunities."""
        import asyncio
        try:
            while True:
                for pair in self.config.get("trading_pairs", []):
                    rates_by_exchange = {}
                    for exchange in self.config.get("exchanges", []):
                        key = (exchange, pair)
                        df = self.funding_rates_history.get(key)
                        if df is not None and not df.empty:
                            rates_by_exchange[exchange] = float(df['rate'].iloc[-1])
                    if len(rates_by_exchange) >= 2:
                        max_ex = max(rates_by_exchange, key=rates_by_exchange.get)
                        min_ex = min(rates_by_exchange, key=rates_by_exchange.get)
                        diff = rates_by_exchange[max_ex] - rates_by_exchange[min_ex]
                        threshold = self.config.get("min_funding_rate_threshold", 0.01)
                        if abs(diff) >= threshold:
                            opp = {
                                "pair": pair,
                                "long_exchange": min_ex, "short_exchange": max_ex,
                                "rate_diff": diff,
                                "long_rate": rates_by_exchange[min_ex],
                                "short_rate": rates_by_exchange[max_ex],
                                "timestamp": time.time()
                            }
                            self.cross_exchange_opportunities.append(opp)
                            self.logger.info(
                                f"Funding arb opportunity: {pair} "
                                f"long@{min_ex}({rates_by_exchange[min_ex]:.4f}) "
                                f"short@{max_ex}({rates_by_exchange[max_ex]:.4f}) "
                                f"diff={diff:.4f}"
                            )
                            if self.event_bus:
                                await self.event_bus.publish("funding.opportunity", opp)
                interval = self.config.get("funding_interval_hours", 8) * 3600 / 10
                await asyncio.sleep(max(interval, 60))
        except asyncio.CancelledError:
            self.logger.info("Funding monitoring task cancelled")
        except Exception as e:
            self.logger.error(f"Error in monitor_funding_opportunities: {e}")
        
    async def execute_arbitrage_strategies(self):
        """Execute identified arbitrage opportunities."""
        import asyncio
        try:
            while True:
                while self.cross_exchange_opportunities:
                    opp = self.cross_exchange_opportunities.pop(0)
                    pair = opp["pair"]
                    long_ex = opp["long_exchange"]
                    short_ex = opp["short_exchange"]
                    rate_diff = opp["rate_diff"]
                    max_size = self.config.get("max_position_size", 10.0)
                    vol_factor = self.config.get("position_sizing_volatility_factor", 0.5)
                    position_size = max_size * vol_factor
                    strategy_id = f"arb_{pair}_{long_ex}_{short_ex}_{int(time.time())}"
                    self.active_strategies[strategy_id] = {
                        "pair": pair,
                        "long_exchange": long_ex, "short_exchange": short_ex,
                        "rate_diff": rate_diff, "position_size": position_size,
                        "status": "pending", "created_at": time.time(),
                        "target_hold_intervals": self.config.get("position_hold_intervals", 3)
                    }
                    self.logger.info(
                        f"Executing arb strategy {strategy_id}: "
                        f"long {position_size} {pair}@{long_ex}, short@{short_ex}"
                    )
                    if self.event_bus:
                        await self.event_bus.publish("arbitrage.execute", {
                            "strategy_id": strategy_id,
                            "orders": [
                                {"exchange": long_ex, "pair": pair, "side": "buy",
                                 "quantity": position_size, "type": "limit"},
                                {"exchange": short_ex, "pair": pair, "side": "sell",
                                 "quantity": position_size, "type": "limit"}
                            ]
                        })
                    self.active_strategies[strategy_id]["status"] = "submitted"
                while self.spot_perp_opportunities:
                    opp = self.spot_perp_opportunities.pop(0)
                    self.logger.info(f"Spot-perp arb opportunity: {opp.get('symbol')} spread={opp.get('spread_pct', 0):.3f}%")
                    if self.event_bus:
                        await self.event_bus.publish("arbitrage.spot_perp.execute", opp)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.logger.info("Arbitrage execution task cancelled")
        except Exception as e:
            self.logger.error(f"Error in execute_arbitrage_strategies: {e}")
        
    async def risk_monitoring_task(self):
        """Monitor risk parameters for active arbitrage positions."""
        import asyncio
        try:
            while True:
                strategies_to_close = []
                for strategy_id, strategy in list(self.active_strategies.items()):
                    if strategy["status"] not in ("submitted", "active"):
                        continue
                    pair = strategy["pair"]
                    long_ex = strategy["long_exchange"]
                    short_ex = strategy["short_exchange"]
                    long_key = f"{long_ex}:{pair}"
                    short_key = f"{short_ex}:{pair}"
                    long_pos = self.current_positions.get(long_key, {})
                    short_pos = self.current_positions.get(short_key, {})
                    net_exposure = abs(
                        long_pos.get('net_quantity', 0) + short_pos.get('net_quantity', 0)
                    )
                    tolerance = self.config.get("delta_neutral_tolerance", 0.02)
                    position_size = strategy.get("position_size", 1.0)
                    if position_size > 0 and net_exposure / position_size > tolerance:
                        self.logger.warning(
                            f"Strategy {strategy_id} delta imbalance: "
                            f"net_exposure={net_exposure:.4f}"
                        )
                        if self.event_bus:
                            await self.event_bus.publish("arbitrage.risk.delta_warning", {
                                "strategy_id": strategy_id,
                                "net_exposure": net_exposure
                            })
                    elapsed_hours = (time.time() - strategy["created_at"]) / 3600
                    funding_interval = self.config.get("funding_interval_hours", 8)
                    target_intervals = strategy.get("target_hold_intervals", 3)
                    if elapsed_hours >= funding_interval * target_intervals:
                        strategies_to_close.append(strategy_id)
                for strategy_id in strategies_to_close:
                    self.active_strategies[strategy_id]["status"] = "closing"
                    self.logger.info(f"Strategy {strategy_id} reached target hold period, closing")
                    if self.event_bus:
                        await self.event_bus.publish("arbitrage.close", {
                            "strategy_id": strategy_id,
                            "reason": "target_hold_reached"
                        })
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.logger.info("Risk monitoring task cancelled")
        except Exception as e:
            self.logger.error(f"Error in risk_monitoring_task: {e}")
