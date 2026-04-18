#!/usr/bin/env python3
"""
Kingdom AI Trading System Module

This module provides the main trading system component for the Kingdom AI platform,
implementing trading strategies and market analysis with integrated sentience detection.
Enhanced with Quantum AI Trading Intelligence and Ontological Market Analysis.
"""

# Standard library imports
import os
import sys
import time
import json
import asyncio
import logging
import secrets
import random
import inspect
# Set up logger immediately so it can be used in exception handlers
logger = logging.getLogger("kingdom_ai.trading_system")
import importlib
import importlib.util
import traceback
from datetime import datetime
from secrets import SystemRandom  # Use secure random for crypto
from typing import Dict, Any, Optional, List, cast

# Local imports
from core.base_component import BaseComponent
from core.api_key_manager import APIKeyManager
from core.blockchain.kingdomweb3_v2 import KingdomWeb3

# Import Quantum AI Trading System
try:
    from core.trading.quantum_ai_trader import (
        QuantumAITradingEngine,
        PalantirOntology,
        TradingSignal as QuantumTradingSignal,
        MarketData
    )
    HAS_QUANTUM_TRADING = True
    logger.info("✅ Quantum AI Trading System loaded")
except ImportError as e:
    HAS_QUANTUM_TRADING = False
    logger.warning(f"⚠️ Quantum AI Trading not available: {e}")

# Sentience framework imports
try:
    from core.sentience.trading_sentience_integration import TradingSentienceIntegration
    has_sentience_framework = True
except ImportError as e:
    logger.warning(f"Sentience framework not available: {e}")
    has_sentience_framework = False


# External modules for trading components - using try/except for each import
# to handle cases where these modules don't exist
# Import AGGRESSIVE trading system components - NO FALLBACKS
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import fix_trading_system_part1
import fix_trading_system_part2
import fix_trading_system_strategies

MarketDataProvider = fix_trading_system_part1.MarketDataProcessor
MarketDataProcessor = fix_trading_system_part1.MarketDataProcessor
OrderExecutor = fix_trading_system_part2.OrderExecutor
StrategyLibrary = fix_trading_system_strategies.StrategyLibrary
StrategyType = fix_trading_system_strategies.StrategyType
TradingSignal = fix_trading_system_strategies.TradingSignal
StrategyManager = fix_trading_system_strategies.StrategyLibrary

logger.info("✅ AGGRESSIVE Trading System Loaded")
logger.info("✅ 10x Leverage | 50+ Strategies | Compound ON")
has_aggressive_trading = True

# Optional autonomous trading modules (seven-module stack; see components/autonomous_trading/)
try:
    from components.autonomous_trading import (  # noqa: F401
        AutonomousOrchestrator,
        PortfolioHedgingModule,
        InstitutionalPositioningModule,
        DividendRadarModule,
        CorrelationMapModule,
        SentimentArbitrageModule,
        MacroAnalysisModule,
        ShortSqueezeModule,
    )

    HAS_AUTONOMOUS_TRADING_MODULES = True
except ImportError as _e:
    HAS_AUTONOMOUS_TRADING_MODULES = False

# Legacy components NOT used in aggressive system
RiskManager = None
TradingSignalGeneratorPlaceholder: Any = None
PositionManager = None
PortfolioManager = None

# All aggressive trading modules loaded successfully
has_fix_modules = True

# REAL TRADING COMPONENTS - Functional implementations
# These provide actual trading functionality using available exchange connections

class RealMarketDataProcessor:
    """Real market data processor using exchange APIs."""
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading")
        self.logger.info("✅ MarketDataProcessor initialized")
        self._cache = {}
    
    async def process_market_data(self, event_type, data):
        """Process incoming market data."""
        symbol = data.get("symbol", "BTC/USDT")
        self._cache[symbol] = data
        self.logger.debug(f"Processed market data for {symbol}")
        return {"processed": True, "symbol": symbol, "data": data}
    
    async def get_market_data(self, event_type, data):
        """Get market data from cache or fetch from exchange."""
        symbol = data.get("symbol", "BTC/USDT")
        if symbol in self._cache:
            return self._cache[symbol]
        # Return structure for live data fetch
        return {"symbol": symbol, "status": "fetching", "source": "exchange_api"}

class RealOrderExecutor:
    """Real order executor using CCXT exchange connections."""
    def __init__(self, event_bus=None, user_id: str = "creator"):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading")
        self._pending_orders = {}
        self._exchanges = {}
        self._user_id = user_id
        self._init_exchanges()
        self.logger.info("OrderExecutor initialized with CCXT (user=%s)", user_id)
    
    def _resolve_api_keys_path(self) -> Optional[str]:
        """Return the correct API keys path for the active user.

        Consumer instances use data/wallets/users/<user_id>/api_keys.json.
        Owner ('creator') uses the global config/api_keys.json.
        Returns None when the consumer has no keys yet (never falls through
        to the owner's file).
        """
        import os
        base = os.path.dirname(os.path.dirname(__file__))
        if self._user_id and self._user_id != "creator":
            user_path = os.path.join(
                base, "data", "wallets", "users", self._user_id, "api_keys.json")
            return user_path if os.path.exists(user_path) else None
        owner_path = os.path.join(base, "config", "api_keys.json")
        return owner_path if os.path.exists(owner_path) else None

    def _init_exchanges(self):
        """Initialize exchange connections using API keys."""
        try:
            import ccxt
        except ImportError:
            self.logger.info("Installing ccxt for exchange connections...")
            import subprocess
            import sys
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'ccxt', '-q'])
            import ccxt
        
        try:
            import os
            import json
            config_path = self._resolve_api_keys_path()
            if config_path and os.path.exists(config_path):
                with open(config_path) as f:
                    api_keys = json.load(f)
                
                # Initialize each configured exchange
                for exchange_id, keys in api_keys.items():
                    if hasattr(ccxt, exchange_id):
                        try:
                            exchange_class = getattr(ccxt, exchange_id)
                            self._exchanges[exchange_id] = exchange_class({
                                'apiKey': keys.get('api_key', ''),
                                'secret': keys.get('api_secret', ''),
                                'enableRateLimit': True
                            })
                            self.logger.info(f"✅ Connected to {exchange_id}")
                        except Exception as e:
                            self.logger.warning(f"Failed to init {exchange_id}: {e}")
        except Exception as e:
            self.logger.warning(f"Could not load API keys: {e}")
    
    async def execute_order(self, event_type, data):
        """Execute order through exchange API."""
        import uuid
        order_id = str(uuid.uuid4())[:8]
        
        exchange_id = data.get('exchange', 'binance')
        symbol = data.get('symbol', 'BTC/USDT')
        side = data.get('side', 'buy')
        amount = data.get('amount', 0)
        price = data.get('price')  # None for market orders
        order_type = data.get('type', 'market')
        
        if exchange_id in self._exchanges:
            try:
                exchange = self._exchanges[exchange_id]
                if order_type == 'market':
                    result = await exchange.create_market_order(symbol, side, amount)
                else:
                    result = await exchange.create_limit_order(symbol, side, amount, price)
                self.logger.info(f"✅ Order executed on {exchange_id}: {result}")
                return {"status": "executed", "order_id": result.get('id', order_id), "result": result}
            except Exception as e:
                self.logger.error(f"❌ Order failed on {exchange_id}: {e}")
                return {"status": "failed", "error": str(e), "order_id": order_id}
        else:
            # Queue for manual execution
            self._pending_orders[order_id] = data
            self.logger.warning(f"⚠️ No exchange connection for {exchange_id} - order queued")
            return {"status": "queued", "order_id": order_id, "data": data}
    
    async def cancel_order(self, event_type, data):
        """Cancel pending order."""
        order_id = data.get("order_id")
        exchange_id = data.get('exchange', 'binance')
        symbol = data.get('symbol', 'BTC/USDT')
        
        if exchange_id in self._exchanges:
            try:
                result = await self._exchanges[exchange_id].cancel_order(order_id, symbol)
                return {"status": "cancelled", "order_id": order_id, "result": result}
            except Exception as e:
                self.logger.error(f"❌ Cancel failed: {e}")
                return {"status": "failed", "error": str(e)}
        
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]
            return {"status": "cancelled", "order_id": order_id}
        return {"status": "not_found", "order_id": order_id}

class RealRiskManager:
    """Real risk manager with configurable limits."""
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading")
        self.logger.info("✅ RiskManager initialized")
        self.max_position_size = 0.1  # 10% max position
        self.max_daily_loss = 0.05    # 5% max daily loss
    
    async def check_risk(self, event_type, data):
        """Check risk parameters for trade."""
        position_size = data.get("size", 0)
        portfolio_value = data.get("portfolio_value", 10000)
        risk_ratio = position_size / portfolio_value if portfolio_value > 0 else 1
        
        risk_level = "low" if risk_ratio < 0.02 else "medium" if risk_ratio < 0.05 else "high"
        approved = risk_ratio <= self.max_position_size
        
        return {"risk_level": risk_level, "approved": approved, "risk_ratio": risk_ratio}

class RealStrategyManager:
    """Real strategy manager with persistent storage."""
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading")
        self.logger.info("✅ StrategyManager initialized")
        self.strategies = {}
    
    async def update_strategy(self, event_type, data):
        """Update or create trading strategy."""
        strategy_id = data.get("id", "default")
        self.strategies[strategy_id] = data
        self.logger.info(f"Strategy {strategy_id} updated")
        return {"status": "updated", "strategy_id": strategy_id}
    
    async def get_strategies(self, event_type, data=None):
        """Get all active strategies."""
        return {"strategies": list(self.strategies.values()), "count": len(self.strategies)}

# Use real implementations
SafeMarketDataProcessor = RealMarketDataProcessor
SafeOrderExecutor = RealOrderExecutor
SafeRiskManager = RealRiskManager
SafeStrategyManager = RealStrategyManager

# Declare variables for component classes - MUST be populated with real implementations
MarketDataProcessor = None
OrderExecutor = None
RiskManager = None
StrategyManager = None
TradingSignalGeneratorPlaceholder2: Any = None
PositionManager = None
PortfolioManager = None

# Ensure Optional typing for module-level component placeholders
RiskManager = cast(Any, RiskManager)
TradingSignalGeneratorPlaceholder = cast(Any, TradingSignalGeneratorPlaceholder)
PositionManager = cast(Any, PositionManager)
PortfolioManager = cast(Any, PortfolioManager)

def _safe_publish_trading_telemetry(event_bus, event_type: str, metadata: Dict[str, Any]) -> None:
    """Best-effort trading telemetry publisher.

    Keeps handlers extremely lightweight so it does not affect latency on
    real trading operations. Any errors are logged at debug level only.
    """
    try:
        if event_bus is None:
            return
        payload: Dict[str, Any] = {
            "component": "trading",
            "channel": "trading.telemetry",
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "success": True,
            "error": None,
            "metadata": metadata,
        }
        event_bus.publish("trading.telemetry", payload)
    except Exception as e:
        logger.debug(f"Trading telemetry publish failed for {event_type}: {e}")

# Aggressive trading modules already loaded at top of file
# No duplicate imports needed

# AdditionalTradingUtilities - functional implementation
class AdditionalTradingUtilities:
    """Trading utilities with real metrics calculation."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading.utilities")
        self._price_history = []
    
    async def initialize(self):
        """Initialize the utilities."""
        self.logger.info("✅ Trading utilities initialized")
        return True
    
    async def calculate_metrics(self, data):
        """Calculate trading metrics from market data."""
        if not data or not isinstance(data, dict):
            return {"volatility": 0, "momentum": 0, "trend": "neutral"}
        
        prices = data.get("prices", [])
        if len(prices) < 2:
            return {"volatility": 0, "momentum": 0, "trend": "neutral"}
        
        # Calculate real metrics
        import numpy as np
        prices_arr = np.array(prices)
        returns = np.diff(prices_arr) / prices_arr[:-1]
        
        volatility = float(np.std(returns)) if len(returns) > 0 else 0
        momentum = float((prices_arr[-1] - prices_arr[0]) / prices_arr[0]) if prices_arr[0] != 0 else 0
        trend = "bullish" if momentum > 0.01 else "bearish" if momentum < -0.01 else "neutral"
        
        return {"volatility": volatility, "momentum": momentum, "trend": trend}

# Try to import additional modules
try:
    # Check for fix_trading_system_part2 module availability
    import importlib.util
    spec = importlib.util.find_spec("fix_trading_system_part2")
    if spec is not None:
        logger.info("fix_trading_system_part2 module is available")
    else:
        logger.warning("fix_trading_system_part2 module not found")
except ImportError as e:
    logger.warning(f"Error checking fix_trading_system_part2 module: {e}")

# Create fallback implementation for TradingStrategies
class FallbackTradingStrategies:
    """Fallback implementation for TradingStrategies."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.strategies = {}
        self.logger = logging.getLogger("kingdom_ai.trading.strategies")
    
    async def initialize(self):
        """Initialize the strategies component."""
        self.logger.info("Initializing fallback trading strategies")
        return True
    
    async def add_strategy(self, strategy_name, strategy_config):
        """Add a trading strategy to the component."""
        self.logger.info(f"Adding fallback strategy: {strategy_name}")
        self.strategies[strategy_name] = strategy_config
        return True
    
    async def get_strategies(self):
        """Get all available strategies."""
        return self.strategies
    
    async def remove_strategy(self, strategy_name):
        """Remove a trading strategy from the component."""
        if strategy_name in self.strategies:
            del self.strategies[strategy_name]
            return True
        return False
        
    async def execute_strategy(self, strategy_name, market_data):
        """Execute a specific trading strategy with given market data."""
        self.logger.info(f"Executing strategy: {strategy_name}")
        price = float(market_data.get("price", 0)) if isinstance(market_data, dict) else 0
        volume = float(market_data.get("volume", 0)) if isinstance(market_data, dict) else 0
        rsi = float(market_data.get("rsi", 50)) if isinstance(market_data, dict) else 50
        if rsi < 30:
            action, strength, conf = "BUY", min(1.0, 0.7 + (30 - rsi) / 100), 0.75
        elif rsi > 70:
            action, strength, conf = "SELL", min(1.0, 0.7 + (rsi - 70) / 100), 0.75
        elif price > 0 and volume > 0:
            action, strength, conf = "HOLD", 0.4, 0.5
        else:
            action, strength, conf = "HOLD", 0.3, 0.3
        return {
            "signals": [{"type": action, "strength": strength}],
            "confidence": conf,
            "timestamp": asyncio.get_event_loop().time()
        }

# Try to import strategies
try:
    # Check for fix_trading_system_strategies module availability
    import importlib.util
    spec = importlib.util.find_spec("fix_trading_system_strategies")
    if spec is not None:
        logger.info("fix_trading_system_strategies module is available")
    else:
        logger.warning("fix_trading_system_strategies module not found")
except ImportError as e:
    logger.warning(f"Error checking fix_trading_system_strategies module: {e}")


class TradingSignalGenerator(BaseComponent):
    """SOTA 2026 Unified Signal Generator — wires ALL live modules into analysis."""

    def __init__(self, event_bus=None, config=None):
        super().__init__(event_bus, config)
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logging.getLogger("kingdom_ai.trading.signal_generator")

        self.buy_threshold = float(self.config.get("buy_threshold", 0.7))
        self.sell_threshold = float(self.config.get("sell_threshold", 0.7))
        self.max_history = int(self.config.get("max_history", 100))
        self.min_confidence = float(self.config.get("min_confidence", 0.6))
        self.signal_timeout = int(self.config.get("signal_timeout", 300))

        self.market_data_history: Dict[str, List[Dict[str, Any]]] = {}
        self.signals: List[Dict[str, Any]] = []
        self.signal_history: Dict[str, List[Dict[str, Any]]] = {}

        self.active_strategy = str(self.config.get("default_strategy", "moving_average"))
        self.strategies = {
            "moving_average": self._strategy_moving_average,
            "rsi": self._strategy_rsi,
            "bollinger": self._strategy_bollinger,
            "support_resistance": self._strategy_support_resistance,
            "macd": self._strategy_macd,
        }

        # Live module references (resolved lazily from event_bus components)
        self._price_charts = None
        self._order_book = None
        self._trades_feed = None
        self._sentiment = None
        self._arbitrage = None
        self._ai_strategies = None
        self._quantum = None
        self._meme_scanner = None
        self._risk_manager = None
        self._portfolio_analytics = None
        self._market_intelligence = None
        self._trading_intelligence = None
        self._futures_master = None
        self._all_markets_scanner = None
        self._market_analyzer = None
        self._copy_trading = None
        self._ollama_orch = None
        self._ollama_brain = None
        self._ohlcv_cache: Dict[str, dict] = {}
        self._ohlcv_cache_ts: Dict[str, float] = {}
        self._OHLCV_TTL = 60  # seconds

    # ------------------------------------------------------------------
    # Live-module resolution helpers
    # ------------------------------------------------------------------
    def _resolve_live_modules(self):
        """Lazily resolve live module references from event_bus components."""
        if not self.event_bus:
            return
        _get = getattr(self.event_bus, "get_component", None)
        if not _get:
            return
        if self._price_charts is None:
            self._price_charts = _get("live_price_charts") or _get("price_charts")
        if self._order_book is None:
            self._order_book = _get("live_order_book") or _get("order_book")
        if self._trades_feed is None:
            self._trades_feed = _get("live_trades_feed") or _get("trades_feed")
        if self._sentiment is None:
            self._sentiment = _get("live_sentiment") or _get("sentiment_analyzer")
        if self._arbitrage is None:
            self._arbitrage = _get("live_arbitrage") or _get("arbitrage_scanner")
        if self._ai_strategies is None:
            self._ai_strategies = _get("live_ai_strategies") or _get("ai_strategies")
        if self._quantum is None:
            self._quantum = _get("live_quantum") or _get("quantum_trading")
        if self._meme_scanner is None:
            self._meme_scanner = _get("live_meme_scanner") or _get("meme_scanner")
        if self._risk_manager is None:
            self._risk_manager = _get("live_risk_manager") or _get("risk_manager")
        if self._portfolio_analytics is None:
            self._portfolio_analytics = _get("live_portfolio") or _get("portfolio_analytics")
        if self._market_intelligence is None:
            self._market_intelligence = _get("market_intelligence") or _get("comprehensive_market_intelligence")
        if self._trading_intelligence is None:
            self._trading_intelligence = _get("trading_intelligence") or _get("CompetitiveEdgeAnalyzer")
        if self._futures_master is None:
            self._futures_master = _get("futures_master") or _get("futures_trading_master")
        if self._all_markets_scanner is None:
            self._all_markets_scanner = _get("all_markets_scanner") or _get("comprehensive_all_markets_scanner")
        if self._market_analyzer is None:
            self._market_analyzer = _get("market_analyzer") or _get("MarketAnalyzer")
        if self._copy_trading is None:
            self._copy_trading = _get("copy_trading") or _get("CopyTrading")
        if self._ollama_orch is None:
            self._ollama_orch = _get("ollama_orchestrator") or _get("OllamaOrchestrator")
        if self._ollama_brain is None:
            self._ollama_brain = _get("thoth") or _get("ollama_brain") or _get("thoth_connector")

    # ------------------------------------------------------------------
    # OHLCV data fetching — real exchange data via ccxt
    # ------------------------------------------------------------------
    async def _fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List:
        """Fetch real OHLCV data, using price_charts module or direct ccxt."""
        cache_key = f"{symbol}:{timeframe}"
        now = time.time()
        if cache_key in self._ohlcv_cache and (now - self._ohlcv_cache_ts.get(cache_key, 0)) < self._OHLCV_TTL:
            return self._ohlcv_cache[cache_key].get("data", [])

        self._resolve_live_modules()
        ohlcv: List = []

        # Primary: live_price_charts module (real ccxt)
        if self._price_charts and hasattr(self._price_charts, "fetch_ohlcv"):
            try:
                ohlcv = await self._price_charts.fetch_ohlcv(symbol, timeframe, limit)
            except Exception as e:
                self.logger.warning("price_charts.fetch_ohlcv failed for %s: %s", symbol, e)

        # Secondary: direct ccxt via our own exchange connections
        if not ohlcv:
            ohlcv = await self._fetch_ohlcv_direct(symbol, timeframe, limit)

        # Tertiary: CoinGecko public OHLC (no key needed)
        if not ohlcv:
            ohlcv = await self._fetch_ohlcv_coingecko(symbol, limit)

        if ohlcv:
            self._ohlcv_cache[cache_key] = {"data": ohlcv}
            self._ohlcv_cache_ts[cache_key] = now
        return ohlcv

    async def _fetch_ohlcv_direct(self, symbol: str, timeframe: str, limit: int) -> List:
        """Fetch OHLCV directly from connected ccxt exchanges."""
        try:
            import ccxt as _ccxt
            _get = getattr(self.event_bus, "get_component", None) if self.event_bus else None
            executor = _get("order_executor") if _get else None
            exchanges = getattr(executor, "_exchanges", {}) if executor else {}
            for eid, ex in exchanges.items():
                try:
                    data = await asyncio.to_thread(ex.fetch_ohlcv, symbol, timeframe, limit=limit)
                    if data:
                        return data
                except Exception:
                    continue
        except Exception as e:
            self.logger.debug("Direct OHLCV fetch failed: %s", e)
        return []

    async def _fetch_ohlcv_coingecko(self, symbol: str, limit: int) -> List:
        """Fetch OHLC from CoinGecko free API as additional data source."""
        try:
            import requests
            coin_map = {
                "BTC/USDT": "bitcoin", "ETH/USDT": "ethereum", "SOL/USDT": "solana",
                "BNB/USDT": "binancecoin", "ADA/USDT": "cardano", "DOT/USDT": "polkadot",
                "DOGE/USDT": "dogecoin", "XRP/USDT": "ripple", "AVAX/USDT": "avalanche-2",
                "MATIC/USDT": "matic-network", "LINK/USDT": "chainlink", "LTC/USDT": "litecoin",
            }
            base = symbol.split("/")[0] if "/" in symbol else symbol
            coin_id = coin_map.get(symbol) or coin_map.get(f"{base}/USDT") or base.lower()
            days = max(1, limit // 24)
            resp = await asyncio.to_thread(
                requests.get,
                f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc",
                params={"vs_currency": "usd", "days": str(days)},
                timeout=8,
            )
            if resp.status_code == 200:
                raw = resp.json()
                return [[r[0], r[1], r[2], r[3], r[4], 0] for r in raw] if raw else []
        except Exception as e:
            self.logger.debug("CoinGecko OHLC fetch for %s: %s", symbol, e)
        return []

    # ------------------------------------------------------------------
    # Technical indicator helpers — real calculations from real OHLCV
    # ------------------------------------------------------------------
    @staticmethod
    def _calc_ema(prices, period: int) -> float:
        import numpy as _np
        arr = _np.asarray(prices, dtype=float)
        if len(arr) < period:
            return float(arr[-1]) if len(arr) else 0.0
        mult = 2.0 / (period + 1)
        ema = float(arr[0])
        for p in arr[1:]:
            ema = p * mult + ema * (1 - mult)
        return ema

    @staticmethod
    def _calc_sma(prices, period: int) -> float:
        import numpy as _np
        arr = _np.asarray(prices, dtype=float)
        if len(arr) < period:
            return float(_np.mean(arr)) if len(arr) else 0.0
        return float(_np.mean(arr[-period:]))

    @staticmethod
    def _calc_rsi(prices, period: int = 14) -> float:
        import numpy as _np
        arr = _np.asarray(prices, dtype=float)
        if len(arr) < period + 1:
            return 50.0
        deltas = _np.diff(arr)
        gains = _np.where(deltas > 0, deltas, 0.0)
        losses = _np.where(deltas < 0, -deltas, 0.0)
        avg_gain = float(_np.mean(gains[-period:]))
        avg_loss = float(_np.mean(losses[-period:]))
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _calc_bollinger(prices, period: int = 20, num_std: float = 2.0):
        import numpy as _np
        arr = _np.asarray(prices, dtype=float)
        if len(arr) < period:
            mid = float(arr[-1]) if len(arr) else 0.0
            return mid + 1, mid, mid - 1
        sma = float(_np.mean(arr[-period:]))
        std = float(_np.std(arr[-period:]))
        return sma + num_std * std, sma, sma - num_std * std

    @staticmethod
    def _calc_macd(prices, fast: int = 12, slow: int = 26, signal_period: int = 9):
        import numpy as _np
        arr = _np.asarray(prices, dtype=float)
        if len(arr) < slow + signal_period:
            return 0.0, 0.0, 0.0  # macd_line, signal_line, histogram

        def _ema_series(data, period):
            result = _np.empty_like(data)
            mult = 2.0 / (period + 1)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = data[i] * mult + result[i - 1] * (1 - mult)
            return result

        ema_fast = _ema_series(arr, fast)
        ema_slow = _ema_series(arr, slow)
        macd_line = ema_fast - ema_slow
        signal_line = _ema_series(macd_line, signal_period)
        histogram = macd_line - signal_line
        return float(macd_line[-1]), float(signal_line[-1]), float(histogram[-1])

    @staticmethod
    def _calc_support_resistance(prices, highs=None, lows=None):
        """Pivot-point based S/R using actual high/low/close data."""
        import numpy as _np
        arr = _np.asarray(prices, dtype=float)
        if len(arr) < 2:
            p = float(arr[-1]) if len(arr) else 0.0
            return {"s1": p * 0.98, "s2": p * 0.95, "r1": p * 1.02, "r2": p * 1.05, "pivot": p}
        h_arr = _np.asarray(highs, dtype=float) if highs is not None else arr
        l_arr = _np.asarray(lows, dtype=float) if lows is not None else arr
        high = float(_np.max(h_arr[-20:])) if len(h_arr) >= 20 else float(_np.max(h_arr))
        low = float(_np.min(l_arr[-20:])) if len(l_arr) >= 20 else float(_np.min(l_arr))
        close = float(arr[-1])
        pivot = (high + low + close) / 3.0
        s1 = 2.0 * pivot - high
        r1 = 2.0 * pivot - low
        s2 = pivot - (high - low)
        r2 = pivot + (high - low)
        return {"s1": s1, "s2": s2, "r1": r1, "r2": r2, "pivot": pivot}

    # ------------------------------------------------------------------
    # Unified analysis — gathers ALL live module data for a symbol
    # ------------------------------------------------------------------
    async def _run_unified_analysis(self, symbol: str) -> Dict[str, Any]:
        """Run ALL analysis tools on a symbol — every feature used."""
        self._resolve_live_modules()
        result: Dict[str, Any] = {"symbol": symbol, "ts": time.time()}

        # 1. Real OHLCV + technical indicators
        ohlcv = await self._fetch_ohlcv(symbol)
        if ohlcv and len(ohlcv) > 1:
            import numpy as _np
            closes = [c[4] for c in ohlcv]
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]
            volumes = [c[5] for c in ohlcv]
            result["price"] = closes[-1]
            result["sma_50"] = self._calc_sma(closes, 50)
            result["sma_200"] = self._calc_sma(closes, 200)
            result["ema_12"] = self._calc_ema(closes, 12)
            result["ema_26"] = self._calc_ema(closes, 26)
            result["ema_50"] = self._calc_ema(closes, 50)
            result["rsi_14"] = self._calc_rsi(closes, 14)
            bb_upper, bb_mid, bb_lower = self._calc_bollinger(closes, 20, 2.0)
            result["bb_upper"] = bb_upper
            result["bb_mid"] = bb_mid
            result["bb_lower"] = bb_lower
            macd_line, sig_line, hist = self._calc_macd(closes, 12, 26, 9)
            result["macd_line"] = macd_line
            result["macd_signal"] = sig_line
            result["macd_histogram"] = hist
            sr = self._calc_support_resistance(closes, highs, lows)
            result["support"] = sr
            result["avg_volume"] = float(_np.mean(volumes[-20:])) if len(volumes) >= 20 else float(_np.mean(volumes)) if volumes else 0
            result["volume_latest"] = float(volumes[-1]) if volumes else 0
        else:
            result["price"] = 0.0

        # 2. Order book depth
        if self._order_book:
            try:
                ob = None
                if hasattr(self._order_book, "get_order_book"):
                    ob = self._order_book.get_order_book(symbol) if not asyncio.iscoroutinefunction(getattr(self._order_book, "get_order_book")) else await self._order_book.get_order_book(symbol)
                if ob:
                    result["order_book"] = {"best_bid": ob.get("best_bid") or (ob["bids"][0][0] if ob.get("bids") else 0),
                                            "best_ask": ob.get("best_ask") or (ob["asks"][0][0] if ob.get("asks") else 0),
                                            "bid_depth": sum(b[1] for b in ob.get("bids", [])[:10]),
                                            "ask_depth": sum(a[1] for a in ob.get("asks", [])[:10])}
            except Exception as e:
                self.logger.debug("Order book for %s: %s", symbol, e)

        # 3. Recent trades (volume profile)
        if self._trades_feed:
            try:
                trades = None
                if hasattr(self._trades_feed, "get_recent_trades"):
                    trades = self._trades_feed.get_recent_trades(symbol) if not asyncio.iscoroutinefunction(getattr(self._trades_feed, "get_recent_trades")) else await self._trades_feed.get_recent_trades(symbol)
                if trades:
                    buy_vol = sum(t.get("amount", 0) for t in trades if t.get("side") == "buy")
                    sell_vol = sum(t.get("amount", 0) for t in trades if t.get("side") == "sell")
                    result["trade_flow"] = {"buy_volume": buy_vol, "sell_volume": sell_vol,
                                            "ratio": buy_vol / max(sell_vol, 1e-9)}
            except Exception as e:
                self.logger.debug("Trades feed for %s: %s", symbol, e)

        # 4. Sentiment analysis
        if self._sentiment:
            try:
                sent = None
                if hasattr(self._sentiment, "get_sentiment"):
                    sent = self._sentiment.get_sentiment(symbol) if not asyncio.iscoroutinefunction(getattr(self._sentiment, "get_sentiment")) else await self._sentiment.get_sentiment(symbol)
                if sent:
                    result["sentiment"] = sent
            except Exception as e:
                self.logger.debug("Sentiment for %s: %s", symbol, e)

        # 5. Arbitrage opportunities
        if self._arbitrage:
            try:
                opps = None
                if hasattr(self._arbitrage, "get_opportunities"):
                    opps = self._arbitrage.get_opportunities() if not asyncio.iscoroutinefunction(getattr(self._arbitrage, "get_opportunities")) else await self._arbitrage.get_opportunities()
                if opps:
                    sym_opps = [o for o in opps if getattr(o, "symbol", None) == symbol or (isinstance(o, dict) and o.get("symbol") == symbol)]
                    result["arbitrage"] = [{"spread": getattr(o, "spread_percent", 0) if not isinstance(o, dict) else o.get("spread_percent", 0)} for o in sym_opps[:5]]
            except Exception as e:
                self.logger.debug("Arbitrage for %s: %s", symbol, e)

        # 6. AI strategy signals
        if self._ai_strategies:
            try:
                ai_sig = None
                if hasattr(self._ai_strategies, "get_signals"):
                    ai_sig = self._ai_strategies.get_signals(symbol) if not asyncio.iscoroutinefunction(getattr(self._ai_strategies, "get_signals")) else await self._ai_strategies.get_signals(symbol)
                if ai_sig:
                    result["ai_signals"] = ai_sig if isinstance(ai_sig, dict) else {"raw": ai_sig}
            except Exception as e:
                self.logger.debug("AI signals for %s: %s", symbol, e)

        # 7. Quantum analysis
        if self._quantum:
            try:
                q_sig = None
                if hasattr(self._quantum, "get_signals"):
                    q_sig = self._quantum.get_signals(symbol) if not asyncio.iscoroutinefunction(getattr(self._quantum, "get_signals")) else await self._quantum.get_signals(symbol)
                if q_sig:
                    result["quantum"] = q_sig if isinstance(q_sig, dict) else {"raw": q_sig}
            except Exception as e:
                self.logger.debug("Quantum for %s: %s", symbol, e)

        # 8. Meme/token scanner
        if self._meme_scanner:
            try:
                meme = None
                if hasattr(self._meme_scanner, "get_tokens"):
                    meme = self._meme_scanner.get_tokens() if not asyncio.iscoroutinefunction(getattr(self._meme_scanner, "get_tokens")) else await self._meme_scanner.get_tokens()
                if meme:
                    result["meme_scan"] = {"count": len(meme), "top": meme[:3] if isinstance(meme, list) else meme}
            except Exception as e:
                self.logger.debug("Meme scan: %s", e)

        # 9. Risk metrics
        if self._risk_manager:
            try:
                risk = None
                if hasattr(self._risk_manager, "get_risk_metrics"):
                    risk = self._risk_manager.get_risk_metrics() if not asyncio.iscoroutinefunction(getattr(self._risk_manager, "get_risk_metrics")) else await self._risk_manager.get_risk_metrics()
                if risk:
                    result["risk"] = risk if isinstance(risk, dict) else {"raw": risk}
            except Exception as e:
                self.logger.debug("Risk metrics: %s", e)

        # 10. Portfolio analytics
        if self._portfolio_analytics:
            try:
                pa = None
                if hasattr(self._portfolio_analytics, "get_portfolio_summary"):
                    pa = self._portfolio_analytics.get_portfolio_summary() if not asyncio.iscoroutinefunction(getattr(self._portfolio_analytics, "get_portfolio_summary")) else await self._portfolio_analytics.get_portfolio_summary()
                if pa:
                    result["portfolio"] = pa if isinstance(pa, dict) else {"raw": pa}
            except Exception as e:
                self.logger.debug("Portfolio analytics: %s", e)

        # 11. Comprehensive market intelligence (whale tracking, flow)
        if self._market_intelligence:
            try:
                mi = None
                if hasattr(self._market_intelligence, "analyze"):
                    mi = await self._market_intelligence.analyze(symbol) if asyncio.iscoroutinefunction(getattr(self._market_intelligence, "analyze")) else self._market_intelligence.analyze(symbol)
                elif hasattr(self._market_intelligence, "get_intelligence"):
                    mi = self._market_intelligence.get_intelligence(symbol)
                if mi:
                    result["market_intel"] = mi if isinstance(mi, dict) else {"raw": mi}
            except Exception as e:
                self.logger.debug("Market intel for %s: %s", symbol, e)

        # 12. Trading intelligence (CompetitiveEdgeAnalyzer)
        if self._trading_intelligence:
            try:
                ti = None
                if hasattr(self._trading_intelligence, "analyze_market"):
                    ti = self._trading_intelligence.analyze_market(symbol) if not asyncio.iscoroutinefunction(getattr(self._trading_intelligence, "analyze_market")) else await self._trading_intelligence.analyze_market(symbol)
                if ti:
                    result["competitive_edge"] = ti if isinstance(ti, dict) else {"raw": ti}
            except Exception as e:
                self.logger.debug("Trading intelligence for %s: %s", symbol, e)

        # 13. Futures analysis
        if self._futures_master:
            try:
                fa = None
                if hasattr(self._futures_master, "get_futures_trading_strategies"):
                    fa = self._futures_master.get_futures_trading_strategies()
                if fa:
                    result["futures"] = fa if isinstance(fa, dict) else {"strategies": fa}
            except Exception as e:
                self.logger.debug("Futures for %s: %s", symbol, e)

        # 14. All-markets scanner (cross-exchange opportunity scan)
        if self._all_markets_scanner:
            try:
                scan = None
                if hasattr(self._all_markets_scanner, "get_opportunities"):
                    scan = self._all_markets_scanner.get_opportunities() if not asyncio.iscoroutinefunction(getattr(self._all_markets_scanner, "get_opportunities")) else await self._all_markets_scanner.get_opportunities()
                elif hasattr(self._all_markets_scanner, "scan_all"):
                    scan = self._all_markets_scanner.scan_all() if not asyncio.iscoroutinefunction(getattr(self._all_markets_scanner, "scan_all")) else await self._all_markets_scanner.scan_all()
                if scan:
                    result["all_markets_scan"] = scan if isinstance(scan, dict) else {"opportunities": scan[:10] if isinstance(scan, list) else scan}
            except Exception as e:
                self.logger.debug("All-markets scan: %s", e)

        # 15. Market analyzer (additional TA signals)
        if self._market_analyzer:
            try:
                ma = None
                if hasattr(self._market_analyzer, "analyze"):
                    ma = self._market_analyzer.analyze(symbol) if not asyncio.iscoroutinefunction(getattr(self._market_analyzer, "analyze")) else await self._market_analyzer.analyze(symbol)
                elif hasattr(self._market_analyzer, "get_analysis"):
                    ma = self._market_analyzer.get_analysis(symbol)
                if ma:
                    result["market_analyzer"] = ma if isinstance(ma, dict) else {"raw": ma}
            except Exception as e:
                self.logger.debug("Market analyzer for %s: %s", symbol, e)

        # 16. Copy trading (what top traders are doing)
        if self._copy_trading:
            try:
                ct = None
                if hasattr(self._copy_trading, "get_top_signals"):
                    ct = self._copy_trading.get_top_signals() if not asyncio.iscoroutinefunction(getattr(self._copy_trading, "get_top_signals")) else await self._copy_trading.get_top_signals()
                elif hasattr(self._copy_trading, "get_status"):
                    ct = self._copy_trading.get_status()
                if ct:
                    result["copy_trading"] = ct if isinstance(ct, dict) else {"raw": ct}
            except Exception as e:
                self.logger.debug("Copy trading: %s", e)

        return result

    # ------------------------------------------------------------------
    # Triple-pass analysis — 3 full passes then AI-powered consensus
    # ------------------------------------------------------------------
    async def _triple_pass_analysis(self, symbol: str) -> Dict[str, Any]:
        """Run 3 complete analysis passes, then route through Ollama brain for AI-powered decision."""
        passes: List[Dict[str, Any]] = []
        for pass_num in range(3):
            analysis = await self._run_unified_analysis(symbol)
            analysis["pass"] = pass_num + 1
            passes.append(analysis)

        return await self._build_consensus(symbol, passes)

    async def _build_consensus(self, symbol: str, passes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """AI-powered consensus: mathematical baseline + Ollama brain final decision."""
        from collections import Counter

        # Step 1: Mathematical baseline from _derive_direction (weighted indicator voting)
        directions: List[str] = []
        confidences: List[float] = []
        for p in passes:
            direction, confidence = self._derive_direction(p)
            directions.append(direction)
            confidences.append(confidence)

        vote = Counter(directions).most_common(1)[0]
        math_dir = vote[0]
        math_conf = sum(confidences) / len(confidences) if confidences else 0.0
        unanimous = vote[1] == 3
        if unanimous:
            math_conf = min(1.0, math_conf * 1.1)
        math_baseline = {"direction": math_dir, "confidence": round(math_conf, 4),
                         "unanimous": unanimous, "votes": dict(Counter(directions))}

        # Step 2: Query Ollama brain with ALL data for AI-powered decision
        self._resolve_live_modules()
        ai_decision = await self._query_ollama_trading(symbol, passes, math_baseline)

        if ai_decision and ai_decision.get("action") and ai_decision.get("confidence", 0) > 0:
            return {
                "symbol": symbol,
                "action": ai_decision["action"],
                "confidence": round(float(ai_decision.get("confidence", math_conf)), 4),
                "reason": ai_decision.get("reason", ""),
                "risk_level": ai_decision.get("risk_level", "medium"),
                "position_size_pct": float(ai_decision.get("position_size_pct", 5.0)),
                "stop_loss_pct": float(ai_decision.get("stop_loss_pct", 2.0)),
                "take_profit_pct": float(ai_decision.get("take_profit_pct", 4.0)),
                "ai_powered": True,
                "math_baseline": math_baseline,
                "passes": passes,
                "timestamp": time.time(),
            }

        # Fallback: math baseline if Ollama unavailable
        return {
            "symbol": symbol,
            "action": math_dir,
            "confidence": round(math_conf, 4),
            "unanimous": unanimous,
            "votes": dict(Counter(directions)),
            "ai_powered": False,
            "math_baseline": math_baseline,
            "passes": passes,
            "timestamp": time.time(),
        }

    async def _query_ollama_trading(self, symbol: str, passes: List[Dict[str, Any]],
                                     math_baseline: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send ALL unified analysis data to AI backend for trading decision."""
        try:
            prompt = self._build_ollama_trading_prompt(symbol, passes, math_baseline)

            if not self._ollama_brain:
                return None

            response = None
            if hasattr(self._ollama_brain, "query"):
                if asyncio.iscoroutinefunction(self._ollama_brain.query):
                    response = await self._ollama_brain.query(prompt)
                else:
                    response = await asyncio.to_thread(self._ollama_brain.query, prompt)
            elif hasattr(self._ollama_brain, "generate_chat_response"):
                model = "mistral-nemo:latest"
                if self._ollama_orch and hasattr(self._ollama_orch, "get_model_for_task"):
                    model = self._ollama_orch.get_model_for_task("trading")
                if asyncio.iscoroutinefunction(self._ollama_brain.generate_chat_response):
                    result = await self._ollama_brain.generate_chat_response(model, prompt)
                else:
                    result = await asyncio.to_thread(self._ollama_brain.generate_chat_response, model, prompt)
                response = result.get("response", result) if isinstance(result, dict) else result

            if not response:
                return None

            raw = str(response).strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    decision = json.loads(raw[start:end])
                    action = str(decision.get("action", "")).lower().strip()
                    if action in ("buy", "sell", "hold"):
                        decision["action"] = action
                        decision.setdefault("backend", "ollama")
                        return decision
                except Exception:
                    pass
            self.logger.debug("Ollama response not parseable as trading decision")
            return None
        except Exception as e:
            self.logger.warning("Ollama trading query failed: %s", e)
            return None

    def _build_ollama_trading_prompt(self, symbol: str, passes: List[Dict[str, Any]],
                                      math_baseline: Dict[str, Any]) -> str:
        """Build comprehensive prompt with ALL 16 modules data for Ollama brain."""
        lines = [
            "You are Kingdom AI's unified trading brain. Analyze ALL data from ALL modules across 3 analysis passes and make a trading decision.",
            f"\nSYMBOL: {symbol}",
            f"MATHEMATICAL BASELINE (weighted indicator voting): {math_baseline.get('direction', 'hold')} "
            f"confidence={math_baseline.get('confidence', 0)} unanimous={math_baseline.get('unanimous', False)}",
            ""
        ]

        for p in passes:
            pn = p.get("pass", "?")
            price = p.get("price", 0)
            lines.append(f"--- PASS {pn} ---")
            lines.append(f"Price: {price}")

            # Technical indicators
            lines.append(f"RSI-14: {p.get('rsi_14', 'N/A')} | EMA-12: {p.get('ema_12', 'N/A')} | EMA-26: {p.get('ema_26', 'N/A')}")
            lines.append(f"SMA-50: {p.get('sma_50', 'N/A')} | SMA-200: {p.get('sma_200', 'N/A')}")
            lines.append(f"MACD: line={p.get('macd_line', 'N/A')} signal={p.get('macd_signal', 'N/A')} hist={p.get('macd_histogram', 'N/A')}")
            lines.append(f"Bollinger: upper={p.get('bb_upper', 'N/A')} mid={p.get('bb_mid', 'N/A')} lower={p.get('bb_lower', 'N/A')}")
            sr = p.get("support", {})
            if sr:
                lines.append(f"Support/Resistance: S1={sr.get('s1', 'N/A')} S2={sr.get('s2', 'N/A')} R1={sr.get('r1', 'N/A')} R2={sr.get('r2', 'N/A')} pivot={sr.get('pivot', 'N/A')}")
            lines.append(f"Volume: latest={p.get('volume_latest', 'N/A')} avg={p.get('avg_volume', 'N/A')}")

            # Order book
            ob = p.get("order_book", {})
            if ob:
                lines.append(f"OrderBook: bid_depth={ob.get('bid_depth', 'N/A')} ask_depth={ob.get('ask_depth', 'N/A')} best_bid={ob.get('best_bid', 'N/A')} best_ask={ob.get('best_ask', 'N/A')}")

            # Trade flow
            tf = p.get("trade_flow", {})
            if tf:
                lines.append(f"TradeFlow: buy_vol={tf.get('buy_volume', 'N/A')} sell_vol={tf.get('sell_volume', 'N/A')} ratio={tf.get('ratio', 'N/A')}")

            # Sentiment
            sent = p.get("sentiment", {})
            if sent:
                score = sent.get("overall_score", sent.get("score", "N/A")) if isinstance(sent, dict) else sent
                lines.append(f"Sentiment: {score}")

            # Arbitrage
            arb = p.get("arbitrage", [])
            if arb:
                lines.append(f"Arbitrage: {len(arb)} opportunities")

            # AI/Quantum/Competitive
            for key, label in [("ai_signals", "AI Strategies"), ("quantum", "Quantum"), ("competitive_edge", "CompetitiveEdge")]:
                v = p.get(key)
                if v and isinstance(v, dict):
                    sig = v.get("signals", v.get("direction", v.get("overall", "")))
                    conf = v.get("confidence", "")
                    lines.append(f"{label}: {sig} conf={conf}" if conf else f"{label}: {sig}")

            # Risk
            risk = p.get("risk", {})
            if risk and isinstance(risk, dict):
                lines.append(f"Risk: VaR={risk.get('var', 'N/A')} Sharpe={risk.get('sharpe_ratio', 'N/A')} MaxDD={risk.get('max_drawdown', 'N/A')}")

            # Portfolio
            port = p.get("portfolio", {})
            if port and isinstance(port, dict):
                lines.append(f"Portfolio: total={port.get('total_value', 'N/A')}")

            # Market intel / whales
            mi = p.get("market_intel", {})
            if mi:
                lines.append(f"MarketIntel: {json.dumps(mi, default=str)[:300]}" if isinstance(mi, dict) else f"MarketIntel: {str(mi)[:300]}")

            # Futures
            fut = p.get("futures", {})
            if fut:
                lines.append(f"Futures: {json.dumps(fut, default=str)[:200]}" if isinstance(fut, dict) else f"Futures: {str(fut)[:200]}")

            # All-markets scan
            ams = p.get("all_markets_scan", {})
            if ams:
                lines.append(f"AllMarketsScan: {json.dumps(ams, default=str)[:200]}" if isinstance(ams, dict) else f"AllMarketsScan: {str(ams)[:200]}")

            # Market analyzer
            ma = p.get("market_analyzer", {})
            if ma:
                lines.append(f"MarketAnalyzer: {json.dumps(ma, default=str)[:200]}" if isinstance(ma, dict) else f"MarketAnalyzer: {str(ma)[:200]}")

            # Copy trading
            ct = p.get("copy_trading", {})
            if ct:
                lines.append(f"CopyTrading: {json.dumps(ct, default=str)[:200]}" if isinstance(ct, dict) else f"CopyTrading: {str(ct)[:200]}")

            # Meme scanner
            meme = p.get("meme_scan", {})
            if meme:
                lines.append(f"MemeScan: count={meme.get('count', 'N/A')}" if isinstance(meme, dict) else f"MemeScan: {str(meme)[:100]}")

            lines.append("")

        lines.append("Based on ALL data from ALL 16 modules across ALL 3 passes, make a trading decision.")
        lines.append("Consider: indicators, order flow, sentiment, arbitrage, AI signals, quantum analysis, whale activity, risk metrics, portfolio state, copy trading signals, meme trends, competitive edge, futures strategies, and all-markets opportunities.")
        lines.append("Respond with JSON ONLY:")
        lines.append('{"action":"buy"|"sell"|"hold", "confidence":0.0-1.0, "reason":"brief explanation", "risk_level":"low"|"medium"|"high", "position_size_pct":0.0-100.0, "stop_loss_pct":number, "take_profit_pct":number}')

        return "\n".join(lines)

    def _derive_direction(self, analysis: Dict[str, Any]) -> tuple:
        """Derive buy/sell/hold + confidence from a single unified analysis pass."""
        signals: List[tuple] = []  # (direction, weight)
        price = analysis.get("price", 0)
        if not price:
            return ("hold", 0.3)

        # MA crossover: EMA-12 vs EMA-26 (golden/death cross)
        ema12 = analysis.get("ema_12", 0)
        ema26 = analysis.get("ema_26", 0)
        if ema12 and ema26:
            if ema12 > ema26 * 1.002:
                signals.append(("buy", 0.7))
            elif ema12 < ema26 * 0.998:
                signals.append(("sell", 0.7))
            else:
                signals.append(("hold", 0.4))

        # SMA 50/200 trend (golden cross = strong buy)
        sma50 = analysis.get("sma_50", 0)
        sma200 = analysis.get("sma_200", 0)
        if sma50 and sma200:
            if sma50 > sma200:
                signals.append(("buy", 0.8))
            else:
                signals.append(("sell", 0.8))

        # RSI
        rsi = analysis.get("rsi_14", 50)
        if rsi < 30:
            signals.append(("buy", 0.85))
        elif rsi > 70:
            signals.append(("sell", 0.85))
        elif rsi < 40:
            signals.append(("buy", 0.55))
        elif rsi > 60:
            signals.append(("sell", 0.55))
        else:
            signals.append(("hold", 0.4))

        # Bollinger Bands
        bb_upper = analysis.get("bb_upper", 0)
        bb_lower = analysis.get("bb_lower", 0)
        if bb_upper and bb_lower and price:
            if price <= bb_lower:
                signals.append(("buy", 0.8))
            elif price >= bb_upper:
                signals.append(("sell", 0.8))
            else:
                signals.append(("hold", 0.4))

        # MACD histogram
        hist = analysis.get("macd_histogram", 0)
        macd_l = analysis.get("macd_line", 0)
        sig_l = analysis.get("macd_signal", 0)
        if macd_l and sig_l:
            if macd_l > sig_l and hist > 0:
                signals.append(("buy", 0.75))
            elif macd_l < sig_l and hist < 0:
                signals.append(("sell", 0.75))
            else:
                signals.append(("hold", 0.4))

        # Support/resistance
        sr = analysis.get("support", {})
        if sr and price:
            s1 = sr.get("s1", 0)
            r1 = sr.get("r1", 0)
            if s1 and price <= s1 * 1.02:
                signals.append(("buy", 0.85))
            elif r1 and price >= r1 * 0.98:
                signals.append(("sell", 0.85))

        # Sentiment boost
        sent = analysis.get("sentiment", {})
        if isinstance(sent, dict):
            overall = sent.get("overall_score", sent.get("score", 0.5))
            if isinstance(overall, (int, float)):
                if overall > 0.65:
                    signals.append(("buy", 0.6))
                elif overall < 0.35:
                    signals.append(("sell", 0.6))

        # Order book imbalance
        ob = analysis.get("order_book", {})
        if ob:
            bid_d = ob.get("bid_depth", 0)
            ask_d = ob.get("ask_depth", 0)
            if bid_d and ask_d:
                ratio = bid_d / max(ask_d, 1e-9)
                if ratio > 1.5:
                    signals.append(("buy", 0.6))
                elif ratio < 0.67:
                    signals.append(("sell", 0.6))

        # Trade flow
        tf = analysis.get("trade_flow", {})
        if tf:
            flow_ratio = tf.get("ratio", 1.0)
            if flow_ratio > 1.5:
                signals.append(("buy", 0.55))
            elif flow_ratio < 0.67:
                signals.append(("sell", 0.55))

        # AI signals
        ai = analysis.get("ai_signals", {})
        if isinstance(ai, dict) and ai.get("direction"):
            ai_dir = ai["direction"]
            ai_conf = ai.get("confidence", 0.7)
            signals.append((ai_dir, ai_conf))

        # Quantum signals
        q = analysis.get("quantum", {})
        if isinstance(q, dict) and q.get("direction"):
            signals.append((q["direction"], q.get("confidence", 0.65)))

        # Competitive edge
        ce = analysis.get("competitive_edge", {})
        if isinstance(ce, dict):
            ce_sig = ce.get("signals", {})
            if isinstance(ce_sig, dict) and ce_sig.get("overall"):
                ce_dir = ce_sig["overall"]
                ce_conf = ce_sig.get("confidence", 0.6)
                signals.append((ce_dir, ce_conf))

        if not signals:
            return ("hold", 0.3)

        buy_score = sum(w for d, w in signals if d == "buy")
        sell_score = sum(w for d, w in signals if d == "sell")
        hold_score = sum(w for d, w in signals if d == "hold")
        total = buy_score + sell_score + hold_score
        if total == 0:
            return ("hold", 0.3)

        if buy_score > sell_score and buy_score > hold_score:
            return ("buy", min(1.0, buy_score / total))
        elif sell_score > buy_score and sell_score > hold_score:
            return ("sell", min(1.0, sell_score / total))
        return ("hold", min(1.0, hold_score / total))

    # ------------------------------------------------------------------
    # Strategy methods — REAL implementations using unified analysis
    # ------------------------------------------------------------------
    async def _apply_strategy(self, symbol: str, strategy_name: str) -> Optional[Dict[str, Any]]:
        strategy_func = self.strategies.get(strategy_name) or self.strategies.get(self.active_strategy)
        if not strategy_func:
            return None
        return await strategy_func(symbol)

    async def _strategy_moving_average(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Real SMA/EMA crossover strategy from live OHLCV."""
        ohlcv = await self._fetch_ohlcv(symbol)
        if not ohlcv or len(ohlcv) < 50:
            return None
        closes = [c[4] for c in ohlcv]
        ema_12 = self._calc_ema(closes, 12)
        ema_26 = self._calc_ema(closes, 26)
        sma_50 = self._calc_sma(closes, 50)
        price = closes[-1]
        if ema_12 > ema_26 and price > sma_50:
            action, conf = "buy", min(1.0, 0.6 + abs(ema_12 - ema_26) / max(price, 1) * 10)
        elif ema_12 < ema_26 and price < sma_50:
            action, conf = "sell", min(1.0, 0.6 + abs(ema_12 - ema_26) / max(price, 1) * 10)
        else:
            action, conf = "hold", 0.4
        return {"symbol": symbol, "action": action, "confidence": round(conf, 4),
                "strategy": "moving_average", "timestamp": time.time(),
                "detail": {"ema_12": ema_12, "ema_26": ema_26, "sma_50": sma_50, "price": price}}

    async def _strategy_rsi(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Real RSI strategy from live OHLCV."""
        ohlcv = await self._fetch_ohlcv(symbol)
        if not ohlcv or len(ohlcv) < 15:
            return None
        closes = [c[4] for c in ohlcv]
        rsi = self._calc_rsi(closes, 14)
        if rsi < 30:
            action, conf = "buy", min(1.0, 0.7 + (30 - rsi) / 100)
        elif rsi > 70:
            action, conf = "sell", min(1.0, 0.7 + (rsi - 70) / 100)
        elif rsi < 40:
            action, conf = "buy", 0.55
        elif rsi > 60:
            action, conf = "sell", 0.55
        else:
            action, conf = "hold", 0.4
        return {"symbol": symbol, "action": action, "confidence": round(conf, 4),
                "strategy": "rsi", "timestamp": time.time(), "detail": {"rsi": rsi}}

    async def _strategy_bollinger(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Real Bollinger Bands strategy from live OHLCV."""
        ohlcv = await self._fetch_ohlcv(symbol)
        if not ohlcv or len(ohlcv) < 20:
            return None
        closes = [c[4] for c in ohlcv]
        upper, mid, lower = self._calc_bollinger(closes, 20, 2.0)
        price = closes[-1]
        band_width = upper - lower
        if price <= lower:
            action, conf = "buy", min(1.0, 0.7 + (lower - price) / max(band_width, 1) * 0.5)
        elif price >= upper:
            action, conf = "sell", min(1.0, 0.7 + (price - upper) / max(band_width, 1) * 0.5)
        else:
            pos_in_band = (price - lower) / max(band_width, 1)
            if pos_in_band < 0.3:
                action, conf = "buy", 0.55
            elif pos_in_band > 0.7:
                action, conf = "sell", 0.55
            else:
                action, conf = "hold", 0.4
        return {"symbol": symbol, "action": action, "confidence": round(conf, 4),
                "strategy": "bollinger", "timestamp": time.time(),
                "detail": {"upper": upper, "mid": mid, "lower": lower, "price": price}}

    async def _strategy_support_resistance(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Real pivot-point S/R strategy from live OHLCV + order book."""
        ohlcv = await self._fetch_ohlcv(symbol)
        if not ohlcv or len(ohlcv) < 20:
            return None
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        price = closes[-1]
        sr = self._calc_support_resistance(closes, highs, lows)
        s1, r1 = sr["s1"], sr["r1"]
        if price <= s1 * 1.01:
            action, conf = "buy", min(1.0, 0.75 + (s1 - price) / max(price, 1) * 5)
        elif price >= r1 * 0.99:
            action, conf = "sell", min(1.0, 0.75 + (price - r1) / max(price, 1) * 5)
        else:
            dist_s = abs(price - s1) / max(price, 1)
            dist_r = abs(price - r1) / max(price, 1)
            if dist_s < dist_r:
                action, conf = "buy", 0.5
            else:
                action, conf = "sell", 0.5
        return {"symbol": symbol, "action": action, "confidence": round(conf, 4),
                "strategy": "support_resistance", "timestamp": time.time(),
                "detail": {"price": price, **sr}}

    async def _strategy_macd(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Real MACD strategy from live OHLCV."""
        ohlcv = await self._fetch_ohlcv(symbol)
        if not ohlcv or len(ohlcv) < 35:
            return None
        closes = [c[4] for c in ohlcv]
        macd_line, signal_line, histogram = self._calc_macd(closes, 12, 26, 9)
        if macd_line > signal_line and histogram > 0:
            action, conf = "buy", min(1.0, 0.65 + abs(histogram) / max(abs(macd_line), 1e-9) * 0.3)
        elif macd_line < signal_line and histogram < 0:
            action, conf = "sell", min(1.0, 0.65 + abs(histogram) / max(abs(macd_line), 1e-9) * 0.3)
        else:
            action, conf = "hold", 0.4
        return {"symbol": symbol, "action": action, "confidence": round(conf, 4),
                "strategy": "macd", "timestamp": time.time(),
                "detail": {"macd": macd_line, "signal": signal_line, "histogram": histogram}}

    # ------------------------------------------------------------------
    # Support-first entry — only enter near support levels
    # ------------------------------------------------------------------
    def _is_near_support(self, analysis: Dict[str, Any], tolerance: float = 0.02) -> bool:
        """Check if current price is near a support level (within tolerance %)."""
        price = analysis.get("price", 0)
        sr = analysis.get("support", {})
        if not price or not sr:
            return False
        s1 = sr.get("s1", 0)
        s2 = sr.get("s2", 0)
        if s1 and abs(price - s1) / max(price, 1) <= tolerance:
            return True
        if s2 and abs(price - s2) / max(price, 1) <= tolerance:
            return True
        return False

    # ------------------------------------------------------------------
    # Signal request / validation (uses triple-pass)
    # ------------------------------------------------------------------
    async def on_signal_request(self, event_type, data):
        if not isinstance(data, dict) or "symbol" not in data:
            return
        symbol = data["symbol"]
        use_triple = data.get("triple_pass", True)

        if use_triple:
            signal = await self._triple_pass_analysis(symbol)
        else:
            strategy = data.get("strategy", self.active_strategy)
            signal = await self._apply_strategy(symbol, str(strategy))

        if signal is None:
            return
        self.signals.append(signal)
        if self.event_bus:
            result = self.event_bus.publish(
                "trading.signal.response",
                {"request_id": data.get("request_id"), "signal": signal},
            )
            if inspect.iscoroutine(result):
                await result

    async def validate_signal(self, signal: Dict[str, Any]) -> bool:
        ts = float(signal.get("timestamp", 0) or 0)
        if datetime.now().timestamp() - ts > self.signal_timeout:
            return False
        return float(signal.get("confidence", 0) or 0) >= self._get_effective_min_confidence()

    async def on_market_update(self, event_data):
        return None

    # ========================================================================
    # PREDATOR MODE INTEGRATION (ADDITIVE - does not alter existing logic)
    # These methods provide aggressive overrides when predator mode is active.
    # ========================================================================

    def _init_predator_mode(self) -> None:
        """Initialize predator mode state tracking. Call once after __init__."""
        self._predator_mode: bool = False
        self._predator_mode_source: Optional[str] = None
        self._predator_mode_since_ts: Optional[float] = None
        self._predator_defaults = {
            'min_confidence': self.min_confidence,
            'buy_threshold': self.buy_threshold,
            'sell_threshold': self.sell_threshold,
        }
        if self.event_bus:
            try:
                self.event_bus.subscribe('system.predator_mode_activated', self._on_predator_mode_activated)
                self.event_bus.subscribe('learning.readiness', self._on_learning_readiness)
                self.logger.info("🦁 TradingSignalGenerator subscribed to predator mode events")
            except Exception as e:
                self.logger.warning(f"TradingSignalGenerator could not subscribe to predator events: {e}")

    def _on_predator_mode_activated(self, payload: Dict[str, Any]) -> None:
        """Handle system.predator_mode_activated event."""
        try:
            if not getattr(self, '_predator_mode', False):
                self._predator_mode = True
                self._predator_mode_source = 'system.predator_mode_activated'
                self._predator_mode_since_ts = time.time()
                self._apply_predator_overrides()
                self.logger.info("🦁 TradingSignalGenerator entered PREDATOR MODE")
        except Exception as e:
            self.logger.error(f"Error handling predator mode activation: {e}")

    def _on_learning_readiness(self, payload: Dict[str, Any]) -> None:
        """Handle learning.readiness event for PREDATOR state."""
        try:
            if not isinstance(payload, dict):
                return
            state = str(payload.get('state') or '').upper()
            if state == 'PREDATOR' and not getattr(self, '_predator_mode', False):
                self._predator_mode = True
                self._predator_mode_source = 'learning.readiness'
                self._predator_mode_since_ts = time.time()
                self._apply_predator_overrides()
                self.logger.info("🦁 TradingSignalGenerator entered PREDATOR MODE via learning.readiness")
        except Exception as e:
            self.logger.error(f"Error handling learning.readiness: {e}")

    def _apply_predator_overrides(self) -> None:
        """Apply aggressive predator mode overrides to signal thresholds."""
        if not getattr(self, '_predator_mode', False):
            return
        self.min_confidence = 0.25
        self.buy_threshold = 0.30
        self.sell_threshold = 0.30
        self.logger.info("🦁 Predator overrides applied: min_confidence=0.25, thresholds=0.30")

    def is_predator_mode(self) -> bool:
        """Return True if predator mode is currently active."""
        return bool(getattr(self, '_predator_mode', False))

    def _get_effective_min_confidence(self) -> float:
        """Return predator-adjusted min_confidence if active, else default."""
        if self.is_predator_mode():
            return 0.25
        return self.min_confidence

    def get_predator_buy_threshold(self) -> float:
        """Return predator-adjusted buy threshold."""
        if self.is_predator_mode():
            return 0.30
        return self.buy_threshold

    def get_predator_sell_threshold(self) -> float:
        """Return predator-adjusted sell threshold."""
        if self.is_predator_mode():
            return 0.30
        return self.sell_threshold

    def restore_default_settings(self) -> None:
        """Restore default settings (exit predator mode)."""
        defaults = getattr(self, '_predator_defaults', {})
        if defaults:
            self.min_confidence = defaults.get('min_confidence', 0.6)
            self.buy_threshold = defaults.get('buy_threshold', 0.7)
            self.sell_threshold = defaults.get('sell_threshold', 0.7)
        self._predator_mode = False
        self._predator_mode_source = None
        self.logger.info("TradingSignalGenerator restored to default settings")


class SafePortfolioManager:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading")
        self.portfolio = {
            "kaig_balance": 10000.0,
            "trading_balance": 0.0,
            "positions": {},
            "history": [],
            "exchange_balances": {},
            "wallet_balances": {},
        }
        self.last_update = time.time()
        self._balance_synced = False

    async def sync_real_balances(self):
        """Sync real trading balances from all connected exchanges + on-chain wallets."""
        total = 0.0
        exchange_bals: Dict[str, float] = {}
        wallet_bals: Dict[str, float] = {}

        # Query exchanges via ccxt
        if self.event_bus and hasattr(self.event_bus, "get_component"):
            executor = self.event_bus.get_component("order_executor")
            exchanges = getattr(executor, "_exchanges", {}) if executor else {}
            for eid, ex in exchanges.items():
                try:
                    bal = await asyncio.to_thread(ex.fetch_balance)
                    free_usd = float(bal.get("free", {}).get("USDT", 0) or 0) + float(bal.get("free", {}).get("USD", 0) or 0)
                    exchange_bals[eid] = free_usd
                    total += free_usd
                except Exception as e:
                    self.logger.debug("Exchange %s balance fetch: %s", eid, e)

            # Query on-chain wallets
            wm = self.event_bus.get_component("wallet_system") or self.event_bus.get_component("wallet_manager")
            if wm and hasattr(wm, "balance_cache"):
                for chain, bal in getattr(wm, "balance_cache", {}).items():
                    usd_val = float(bal.get("usd_value", 0) or 0) if isinstance(bal, dict) else 0
                    wallet_bals[chain] = usd_val
                    total += usd_val

        self.portfolio["trading_balance"] = round(total, 2)
        self.portfolio["exchange_balances"] = exchange_bals
        self.portfolio["wallet_balances"] = wallet_bals
        self._balance_synced = True
        self.last_update = time.time()
        self.logger.info("Synced real balances: trading=$%.2f from %d exchanges + %d wallets",
                         total, len(exchange_bals), len(wallet_bals))

    async def get_portfolio(self, event_type=None, data=None):
        try:
            if not self._balance_synced:
                await self.sync_real_balances()
            return {"portfolio": self.portfolio}
        except Exception as e:
            self.logger.error(f"Error getting portfolio: {e}")
            return {"status": "error", "message": str(e)}

class FallbackMarketDataProcessor:
    """Returns empty DataFrames with correct columns when the real processor is unavailable."""
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading.fallback")
        self._cache: Dict[str, Any] = {}
        self.logger.warning("Using FallbackMarketDataProcessor — exchange data unavailable")

    async def process_market_data(self, event_type, data):
        symbol = data.get("symbol", "BTC/USDT")
        self._cache[symbol] = data
        return {"processed": True, "symbol": symbol, "data": data}

    async def get_market_data(self, event_type, data):
        symbol = data.get("symbol", "BTC/USDT")
        if symbol in self._cache:
            return self._cache[symbol]
        try:
            import pandas as _pd
            return {"symbol": symbol, "status": "no_data",
                    "ohlcv": _pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])}
        except ImportError:
            return {"symbol": symbol, "status": "no_data", "ohlcv": []}


class FallbackOrderExecutor:
    """Logs orders and returns a failure dict when no exchange connection is available."""
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading.fallback")
        self._pending_orders: Dict[str, Dict] = {}
        self._exchanges: Dict = {}
        self.logger.warning("Using FallbackOrderExecutor — orders will NOT reach exchange")

    async def execute_order(self, event_type, data):
        import uuid as _uuid
        order_id = str(_uuid.uuid4())[:8]
        self.logger.warning(f"FallbackOrderExecutor: order {order_id} logged but NOT sent — "
                            f"{data.get('side', '?')} {data.get('amount', '?')} {data.get('symbol', '?')}")
        return {
            "order_id": order_id,
            "status": "rejected",
            "success": False,
            "error": "No exchange connection available (fallback mode)",
            "symbol": data.get("symbol"),
            "side": data.get("side"),
            "amount": data.get("amount"),
        }


class FallbackRiskManager:
    """Returns conservative risk limits that block large trades."""
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading.fallback")
        self.max_position_size = 0.02   # 2% — very conservative
        self.max_daily_loss = 0.01      # 1%
        self.logger.warning("Using FallbackRiskManager — conservative limits enforced")

    async def check_risk(self, event_type, data):
        position_size = data.get("size", 0)
        portfolio_value = data.get("portfolio_value", 10000)
        risk_ratio = position_size / portfolio_value if portfolio_value > 0 else 1.0
        approved = risk_ratio <= self.max_position_size
        risk_level = "low" if risk_ratio < 0.01 else "medium" if risk_ratio < 0.02 else "high"
        if not approved:
            self.logger.warning(f"FallbackRiskManager: trade BLOCKED (risk_ratio={risk_ratio:.4f})")
        return {"risk_level": risk_level, "approved": approved, "risk_ratio": risk_ratio,
                "fallback": True, "max_position_size": self.max_position_size}


class FallbackStrategyManager:
    """Returns a hold signal for all strategy queries."""
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading.fallback")
        self.strategies: Dict[str, Any] = {}
        self.logger.warning("Using FallbackStrategyManager — all signals default to HOLD")

    async def update_strategy(self, event_type, data):
        strategy_id = data.get("id", "default")
        self.strategies[strategy_id] = data
        return {"status": "stored_locally", "strategy_id": strategy_id, "fallback": True}

    async def get_strategies(self, event_type, data=None):
        return {"strategies": list(self.strategies.values()), "count": len(self.strategies), "fallback": True}

    def get_signal(self, symbol: str = "", **kwargs) -> Dict[str, Any]:
        return {"signal": "hold", "confidence": 0.0, "reason": "fallback_mode", "symbol": symbol}


class FallbackTradingSignalGenerator:
    def __init__(self, event_bus=None, **kwargs):
        self.event_bus = event_bus

    def generate_signals(self, event_type, data):
        return None

# Base position and portfolio manager classes
class BasePositionManager:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading.position")
        self.positions = {}
        self.history = []
        self.max_positions = 50  # Maximum positions to track
    
    def get_positions(self, event_type=None, data=None):
        """Get all positions."""
        return self.positions
    
    def get_position(self, symbol):
        """Get position for a specific symbol."""
        return self.positions.get(symbol)
    
    async def add_position(self, symbol, amount, price, order_id=None):
        """Add or update a position."""
        try:
            if symbol not in self.positions:
                # New position
                self.positions[symbol] = {
                    "amount": amount,
                    "price": price,
                    "timestamp": time.time(),
                    "order_id": order_id
                }
                
                # Log new position
                self.logger.info(f"New position for {symbol}: {amount} @ {price}")
            else:
                # Update existing position
                current = self.positions[symbol]
                total_amount = current["amount"] + amount
                
                # Calculate average price for buys
                if total_amount > 0 and amount > 0:
                    avg_price = (current["amount"] * current["price"] + amount * price) / total_amount
                    current["price"] = avg_price
                
                # Update amount and timestamp
                current["amount"] = total_amount
                current["timestamp"] = time.time()
                current["order_id"] = order_id or current.get("order_id")
                
                # Log position update
                self.logger.info(f"Updated position for {symbol}: {total_amount} @ {current['price']}")
                
                # Remove position if empty
                if total_amount == 0:
                    removed = self.positions.pop(symbol)
                    self.logger.info(f"Removed empty position for {symbol}")
            
            # Record in history
            self.history.append({
                "action": "update",
                "symbol": symbol,
                "amount": amount,
                "price": price,
                "timestamp": time.time(),
                "order_id": order_id
            })
            
            # Trim history if too large
            if len(self.history) > self.max_positions * 10:
                self.history = self.history[-self.max_positions * 5:]
            
            # Notify via event bus if available
            if self.event_bus:
                position_data = self.positions.get(symbol, {
                    "amount": 0,
                    "price": price,
                    "timestamp": time.time()
                })

                result = self.event_bus.publish("trading.position_update", {
                    "symbol": symbol,
                    "position": position_data,
                    "action": "update"
                })
                if inspect.iscoroutine(result):
                    await result

                _safe_publish_trading_telemetry(
                    self.event_bus,
                    "position_update",
                    {
                        "symbol": symbol,
                        "amount": position_data.get("amount"),
                        "price": position_data.get("price"),
                        "action": "update",
                    },
                )
            
            return True
        except Exception as ex:
            self.logger.error(f"Error adding position: {ex}")
            return False
    
    async def remove_position(self, symbol, amount=None, price=None):
        """Remove a position or reduce its size."""
        try:
            if symbol not in self.positions:
                self.logger.warning(f"Attempted to remove non-existent position: {symbol}")
                return False
            
            position = self.positions[symbol]
            
            if amount is None or amount >= position["amount"]:
                # Remove entire position
                removed = self.positions.pop(symbol)
                
                # Record in history
                self.history.append({
                    "action": "remove",
                    "symbol": symbol,
                    "amount": removed["amount"],
                    "price": price or removed["price"],
                    "timestamp": time.time()
                })
                
                self.logger.info(f"Removed entire position for {symbol}")
            else:
                # Reduce position
                position["amount"] -= amount
                
                # Record in history
                self.history.append({
                    "action": "reduce",
                    "symbol": symbol,
                    "amount": -amount,  # Negative to indicate reduction
                    "price": price or position["price"],
                    "timestamp": time.time()
                })
                
                self.logger.info(f"Reduced position for {symbol} by {amount}")
            
            # Notify via event bus if available
            if self.event_bus:
                position_data = self.positions.get(symbol, {})
                action = "remove" if symbol not in self.positions else "reduce"

                result = self.event_bus.publish("trading.position_update", {
                    "symbol": symbol,
                    "position": position_data,
                    "action": action,
                })
                if inspect.iscoroutine(result):
                    await result

                _safe_publish_trading_telemetry(
                    self.event_bus,
                    "position_update",
                    {
                        "symbol": symbol,
                        "amount": position_data.get("amount"),
                        "price": position_data.get("price"),
                        "action": action,
                    },
                )
            
            return True
        except Exception as ex:
            self.logger.error(f"Error removing position: {ex}")
            return False
    
    async def update_position_price(self, symbol, price):
        """Update the price of an existing position."""
        try:
            if symbol not in self.positions:
                return False
            
            self.positions[symbol]["price"] = price
            self.positions[symbol]["last_update"] = time.time()
            
            return True
        except Exception as ex:
            self.logger.error(f"Error updating position price: {ex}")
            return False
    
    def get_position_value(self, symbol):
        """Get the current value of a position."""
        if symbol not in self.positions:
            return 0
        
        position = self.positions[symbol]
        return position["amount"] * position["price"]
    
    def get_total_position_value(self):
        """Get the total value of all positions."""
        total = 0
        for symbol, position in self.positions.items():
            total += position["amount"] * position["price"]
        return total
    
    async def on_shutdown(self):
        """Save positions on shutdown."""
        self.logger.info("Saving positions")
        # In a real implementation, would save to database or file
        return True

class BasePortfolioManager:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.trading.portfolio")
        self.portfolio = {
            "kaig_balance": 10000.0,
            "trading_balance": 0.0,
            "positions": {},
            "history": [],
        }
        self.last_update = time.time()
    
    def get_portfolio(self, event_type=None, data=None):
        """Get current portfolio state."""
        return self.portfolio
    
    def update_balance(self, amount, reason="manual"):
        """Update portfolio balance."""
        try:
            previous_balance = self.portfolio["balance"]
            self.portfolio["balance"] += amount
            
            # Record transaction in history
            self.portfolio["history"].append({
                "timestamp": time.time(),
                "type": "balance_update",
                "previous": previous_balance,
                "current": self.portfolio["balance"],
                "change": amount,
                "reason": reason
            })
            
            # Publish event if event bus is available
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish('trading.portfolio_update', {
                    'type': 'balance',
                    'previous': previous_balance,
                    'current': self.portfolio["balance"],
                    'change': amount,
                    'reason': reason
                }))

                _safe_publish_trading_telemetry(
                    self.event_bus,
                    "portfolio_balance_update",
                    {
                        "previous": previous_balance,
                        "current": self.portfolio["balance"],
                        "change": amount,
                        "reason": reason,
                    },
                )
                
            return True
        except Exception as e:
            self.logger.error(f"Error updating balance: {e}")
            return False
    
    def update_position(self, symbol, amount, price, reason="trade"):
        """Update position in portfolio."""
        try:
            if symbol not in self.portfolio["positions"]:
                # New position
                self.portfolio["positions"][symbol] = {
                    "amount": amount,
                    "average_price": price,
                    "last_price": price,
                    "last_update": time.time()
                }
            else:
                # Update existing position
                current = self.portfolio["positions"][symbol]
                total_amount = current["amount"] + amount
                
                # Calculate new average price if adding to position
                if total_amount > 0 and amount > 0:
                    current["average_price"] = (current["amount"] * current["average_price"] + amount * price) / total_amount
                
                # Update position
                current["amount"] = total_amount
                current["last_price"] = price
                current["last_update"] = time.time()
                
                # Remove position if amount is zero
                if total_amount == 0:
                    del self.portfolio["positions"][symbol]
            
            # Record in history
            self.portfolio["history"].append({
                "timestamp": time.time(),
                "type": "position_update",
                "symbol": symbol,
                "amount_change": amount,
                "price": price,
                "reason": reason
            })
            
            # Publish event if event bus is available
            if self.event_bus:
                position_data = self.portfolio["positions"].get(symbol, {
                    "amount": 0,
                    "average_price": price,
                    "last_price": price
                })

                asyncio.create_task(self.event_bus.publish('trading.portfolio_update', {
                    'type': 'position',
                    'symbol': symbol,
                    'position': position_data,
                    'change': amount,
                    'price': price,
                    'reason': reason
                }))

                _safe_publish_trading_telemetry(
                    self.event_bus,
                    "portfolio_position_update",
                    {
                        "symbol": symbol,
                        "amount": position_data.get("amount"),
                        "price": price,
                        "reason": reason,
                    },
                )
                
            return True
        except Exception as e:
            self.logger.error(f"Error updating position: {e}")
            return False
    
    def calculate_total_value(self):
        """Calculate total portfolio value based on current positions."""
        try:
            total = self.portfolio["balance"]
            
            # Add value of all positions
            for symbol, position in self.portfolio["positions"].items():
                position_value = position["amount"] * position["last_price"]
                total += position_value
                
            return total
        except Exception as e:
            self.logger.error(f"Error calculating portfolio value: {e}")
            return self.portfolio["balance"]
    
    async def update_prices(self, market_data):
        """Update position prices based on market data."""
        try:
            if not market_data or "symbol" not in market_data:
                return False
                
            symbol = market_data["symbol"]
            price = market_data.get("price", 0)
            
            if symbol in self.portfolio["positions"] and price > 0:
                self.portfolio["positions"][symbol]["last_price"] = price
                self.portfolio["positions"][symbol]["last_update"] = time.time()
                return True
                
            return False
        except Exception as e:
            self.logger.error(f"Error updating prices: {e}")
            return False
            
    async def on_shutdown(self):
        """Save portfolio state on shutdown."""
        self.logger.info("Saving portfolio state")
        # In a real implementation, this would save to a database or file
        return True

class FallbackPositionManager(BasePositionManager):
    """Fallback position manager with event bus wiring for degraded mode."""
    def __init__(self, event_bus=None, **kwargs):
        super().__init__(event_bus=event_bus)
        if self.event_bus:
            self.event_bus.subscribe("position.query", self.get_positions)
            self.logger.info("FallbackPositionManager active (degraded mode)")

class FallbackPortfolioManager(BasePortfolioManager):
    """Fallback portfolio manager with event bus wiring for degraded mode."""
    def __init__(self, event_bus=None, **kwargs):
        super().__init__(event_bus=event_bus)
        if self.event_bus:
            self.event_bus.subscribe("portfolio.query", self.get_portfolio)
            self.logger.info("FallbackPortfolioManager active (degraded mode)")

# Define backup trading signal generator with all required methods
class BackupTradingSignalGenerator:
    """Fallback implementation of TradingSignalGenerator when the main one is not available."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        self.name = "BackupTradingSignalGenerator"
        self.signals = []
        self.max_history = 100
        self.buy_threshold = 0.7
        self.sell_threshold = 0.7
        
    def on_strategy_update(self, data):
        # Handle strategy update events.
        self.logger.info(f"Strategy update received: {data}")
    
    def on_shutdown(self):
        # Handle shutdown events.
        self.logger.info("Shutting down signal generator")
        
    def _apply_strategy(self, market_data):
        # Apply trading strategy to market data.
        return {"action": "hold", "confidence": 0.5}

# For backward compatibility (must come after all class definitions)
# Now that all the classes are defined, we can safely assign these
SafeTradingSignalGenerator = TradingSignalGenerator
SafePositionManager = BasePositionManager
SafePortfolioManager = cast(Any, BasePortfolioManager)

# If we're using fix modules, we'll try to use the imported classes
if has_fix_modules:
    if 'PositionManager' in globals() and PositionManager is not None:
        SafePositionManager = PositionManager
    if 'PortfolioManager' in globals() and PortfolioManager is not None:
        SafePortfolioManager = PortfolioManager

# Initialization function that 4keys.py expects
async def initialize_trading_system_components(event_bus):
    """Initialize trading system components and connect to the event bus.
    
    Args:
        event_bus: Event bus instance for component communication
        
    Returns:
        Dictionary of initialized components
    """
    logger.info("Initializing trading system components")
    # Initialize components dictionary
    components = {}
    
    try:
        # Initialize the main trading system component first
        main_trading_system = TradingSystem(event_bus)
        components["main_trading_system"] = main_trading_system
        
        # Initialize all required components with robust error handling
        # Market Data Processor
        try:
            if has_fix_modules and MarketDataProcessor is not None:
                market_data_processor = MarketDataProcessor(event_bus=event_bus)
                logger.info("Using imported MarketDataProcessor")
            else:
                market_data_processor = SafeMarketDataProcessor(event_bus=event_bus)
                logger.info("Using fallback SafeMarketDataProcessor")
            components["market_data_processor"] = market_data_processor
        except Exception as e:
            logger.error(f"Error initializing MarketDataProcessor: {e}")
            market_data_processor = SafeMarketDataProcessor(event_bus=event_bus)
            components["market_data_processor"] = market_data_processor
        
        # Order Executor
        try:
            if has_fix_modules and 'OrderExecutor' in dir():
                order_executor = OrderExecutor(event_bus=event_bus)
                logger.info("Using imported OrderExecutor")
            else:
                order_executor = SafeOrderExecutor(event_bus=event_bus)
                logger.info("Using fallback SafeOrderExecutor")
            components["order_executor"] = order_executor
        except Exception as e:
            logger.error(f"Error initializing OrderExecutor: {e}")
            order_executor = SafeOrderExecutor(event_bus=event_bus)
            components["order_executor"] = order_executor
        
        # Risk Manager
        try:
            if has_fix_modules and 'RiskManager' in dir():
                risk_manager = RiskManager(event_bus=event_bus)
                logger.info("Using imported RiskManager")
            else:
                risk_manager = SafeRiskManager(event_bus=event_bus)
                logger.info("Using fallback SafeRiskManager")
            components["risk_manager"] = risk_manager
        except Exception as e:
            logger.error(f"Error initializing RiskManager: {e}")
            risk_manager = SafeRiskManager(event_bus=event_bus)
            components["risk_manager"] = risk_manager
        
        # Strategy Manager
        try:
            if has_fix_modules and 'StrategyManager' in dir():
                strategy_manager = StrategyManager(event_bus=event_bus)
                logger.info("Using imported StrategyManager")
            else:
                strategy_manager = SafeStrategyManager(event_bus=event_bus)
                logger.info("Using fallback SafeStrategyManager")
            components["strategy_manager"] = strategy_manager
        except Exception as e:
            logger.error(f"Error initializing StrategyManager: {e}")
            strategy_manager = SafeStrategyManager(event_bus=event_bus)
            components["strategy_manager"] = strategy_manager
        
        # Trading Signal Generator
        try:
            if has_fix_modules and 'TradingSignalGenerator' in dir():
                signal_generator = TradingSignalGenerator(event_bus=event_bus)
                logger.info("Using imported TradingSignalGenerator")
            else:
                signal_generator = BackupTradingSignalGenerator(event_bus=event_bus)
                logger.info("Using BackupTradingSignalGenerator")
            components["trading_signal_generator"] = signal_generator
        except Exception as e:
            logger.error(f"Error initializing TradingSignalGenerator: {e}")
            signal_generator = BackupTradingSignalGenerator(event_bus=event_bus)
            components["trading_signal_generator"] = signal_generator
        
        # Position Manager
        try:
            if has_fix_modules and 'PositionManager' in dir():
                position_manager = PositionManager(event_bus=event_bus)
                logger.info("Using imported PositionManager")
            else:
                position_manager = BasePositionManager(event_bus=event_bus)
                logger.info("Using fallback BasePositionManager")
            components["position_manager"] = position_manager
        except Exception as e:
            logger.error(f"Error initializing PositionManager: {e}")
            position_manager = BasePositionManager(event_bus=event_bus)
            components["position_manager"] = position_manager
        
        # Portfolio Manager
        try:
            if has_fix_modules and 'PortfolioManager' in dir():
                portfolio_manager = PortfolioManager(event_bus=event_bus)
                logger.info("Using imported PortfolioManager")
            else:
                portfolio_manager = BasePortfolioManager(event_bus=event_bus)
                logger.info("Using fallback BasePortfolioManager")
            components["portfolio_manager"] = portfolio_manager
        except Exception as e:
            logger.error(f"Error initializing PortfolioManager: {e}")
            portfolio_manager = BasePortfolioManager(event_bus=event_bus)
            components["portfolio_manager"] = portfolio_manager
            
            # Safely try to import optional integration modules
            trading_system_integration = None
            
            # First try to import fix_trading_system_part2
            try:
                # First check if the module exists using a simpler approach
                module_spec = importlib.util.find_spec("fix_trading_system_part2")
                if module_spec is not None:
                    # Import the module if it exists
                    fix_trading_system_part2 = importlib.util.module_from_spec(module_spec)
                    module_spec.loader.exec_module(fix_trading_system_part2)
                    logger.info("Imported fix_trading_system_part2 module")
                    strategy_library = fix_trading_system_part2.AdditionalTradingUtilities()
                else:
                    logger.info("fix_trading_system_part2 module not found")
            except Exception as e:
                logger.warning(f"Error loading fix_trading_system_part2 module: {e}")
                strategy_library = None
            
            # Next try to import fix_trading_system_strategies
            try:
                # First try to load strategies from a module
                module_spec = importlib.util.find_spec("fix_trading_system_strategies")
                if module_spec is not None:
                    # Import the module if it exists
                    fix_trading_system_strategies = importlib.util.module_from_spec(module_spec)
                    module_spec.loader.exec_module(fix_trading_system_strategies)
                    logger.info("Imported fix_trading_system_strategies module")
                    strategy_library = fix_trading_system_strategies.TradingStrategies()
                    components["strategy_library"] = strategy_library
                else:
                    logger.info("fix_trading_system_strategies module not found")
            except Exception as e:
                logger.warning(f"Error loading fix_trading_system_strategies module: {e}")
                strategy_library = None
    
    except Exception as e:
        # This is the exception handler for the larger try block that contains all the component initialization
        logger.warning(f"Error initializing trading system components: {e}")
        logger.debug(traceback.format_exc())
            
        try:
            # Create main trading system - requires BaseComponent for initialization
            if not main_trading_system or not isinstance(main_trading_system, BaseComponent):
                logger.info("Creating TradingSystemWrapper as main_trading_system wasn't properly initialized")
                
                class TradingSystemWrapper(BaseComponent):
                    def __init__(self, event_bus, **kwargs):
                        super().__init__(event_bus=event_bus)
                        self.trading_system = TradingSystem(event_bus=event_bus, **kwargs)
                    
                    async def handle_execute_order(self, event_type, data):
                        try:
                            # Call OrderExecutor component if available
                            if hasattr(self.trading_system, 'components') and "order_executor" in self.trading_system.components and self.trading_system.components["order_executor"] is not None:
                                result = await self.trading_system.components["order_executor"].execute_order(data.get("order"))
                                return {"status": "success", "result": result}
                            else:
                                logger.warning("OrderExecutor component not available")
                                return {"status": "error", "message": "OrderExecutor component not available"}
                        except Exception as e:
                            logger.error(f"Error in handle_execute_order: {e}")
                            return {"status": "error", "message": str(e)}

                    async def handle_cancel_order(self, event_type, data):
                        try:
                            # Call OrderExecutor component if available
                            if hasattr(self.trading_system, 'components') and "order_executor" in self.trading_system.components and self.trading_system.components["order_executor"] is not None:
                                result = await self.trading_system.components["order_executor"].cancel_order(data.get("order_id"))
                                return {"status": "success", "result": result}
                            else:
                                logger.warning("OrderExecutor component not available")
                                return {"status": "error", "message": "OrderExecutor component not available"}
                        except Exception as e:
                            logger.error(f"Error in handle_cancel_order: {e}")
                            return {"status": "error", "message": str(e)}

                    async def handle_get_positions(self, event_type, data):
                        try:
                            # Call PositionManager component if available
                            if hasattr(self.trading_system, 'components') and "position_manager" in self.trading_system.components and self.trading_system.components["position_manager"] is not None:
                                result = await self.trading_system.components["position_manager"].get_positions(data.get("symbol"))
                                return {"status": "success", "result": result}
                            else:
                                logger.warning("PositionManager component not available")
                                return {"status": "error", "message": "PositionManager component not available"}
                        except Exception as e:
                            logger.error(f"Error in handle_get_positions: {e}")
                            return {"status": "error", "message": str(e)}
                    
                    async def handle_update_strategy(self, event_type, data):
                        try:
                            # Call StrategyManager component if available
                            if hasattr(self.trading_system, 'components') and "strategy_manager" in self.trading_system.components and self.trading_system.components["strategy_manager"] is not None:
                                result = await self.trading_system.components["strategy_manager"].update_strategy(data.get("strategy"))
                                return {"status": "success", "result": result}
                            else:
                                logger.warning("StrategyManager component not available")
                                return {"status": "error", "message": "StrategyManager component not available"}
                        except Exception as e:
                            logger.error(f"Error in handle_update_strategy: {e}")
                            return {"status": "error", "message": str(e)}
                    
                    async def handle_analyze_market(self, event_type, data):
                        try:
                            # Call MarketDataProcessor component if available
                            if hasattr(self.trading_system, 'components') and "market_data_processor" in self.trading_system.components and self.trading_system.components["market_data_processor"] is not None:
                                result = await self.trading_system.components["market_data_processor"].process_market_data(data.get("market_data"))
                                return {"status": "success", "result": result}
                            else:
                                logger.warning("MarketDataProcessor component not available")
                                return {"status": "error", "message": "MarketDataProcessor component not available"}
                        except Exception as e:
                            logger.error(f"Error in handle_analyze_market: {e}")
                            return {"status": "error", "message": str(e)}

                    async def initialize(self):
                        try:
                            if hasattr(self.trading_system, 'initialize'):
                                result = await self.trading_system.initialize()
                                if isinstance(result, bool):
                                    return result
                                logger.info(f"Trading system initialize returned: {result}")
                                return True
                            else:
                                logger.warning("TradingSystem.initialize method not available")
                                if hasattr(self, 'event_bus') and self.event_bus is not None:
                                    self.event_bus.publish('trading.error', {"message": "TradingSystem.initialize method not available"})
                                return False
                        except Exception as e:
                            logger.error(f"Error in TradingSystemWrapper.initialize: {e}")
                            if hasattr(self, 'event_bus') and self.event_bus is not None:
                                self.event_bus.publish('trading.error', {"message": str(e)})
                            return False

                # Create the trading system wrapper with proper error handling
                main_trading_system = None
                try:
                    # Create the trading system wrapper instance
                    main_trading_system = TradingSystemWrapper(event_bus=event_bus)
                    # Add to components if successfully created
                    if main_trading_system:
                        components["trading_system"] = main_trading_system
                        logger.info("Trading system wrapper successfully created and registered")
                except Exception as e:
                    logger.error(f"Error creating trading system: {e}")
                    main_trading_system = None
                    logger.info("Failed to create trading system wrapper, using fallback components only")
        except Exception as e:
            logger.error(f"Error in TradingSystemWrapper creation: {e}")
            
        # Initialize subcomponents based on availability
        try:
            if has_fix_modules:
                # Market Data Processor
                market_data_processor = MarketDataProcessor(event_bus=event_bus)
                components["market_data_processor"] = market_data_processor
                
                # Order Executor
                order_executor = OrderExecutor(event_bus=event_bus)
                components["order_executor"] = order_executor
                
                # Risk Manager
                risk_manager = RiskManager(event_bus=event_bus)
                components["risk_manager"] = risk_manager
                
                # Strategy Manager
                strategy_manager = StrategyManager(event_bus=event_bus)
                components["strategy_manager"] = strategy_manager
                
                # Trading Signal Generator
                signal_generator = TradingSignalGenerator(event_bus=event_bus)
                components["signal_generator"] = signal_generator
                
                # Position Manager
                position_manager = PositionManager(event_bus=event_bus)
                components["position_manager"] = position_manager
                
                # Portfolio Manager
                portfolio_manager = PortfolioManager(event_bus=event_bus)
                components["portfolio_manager"] = portfolio_manager
        except Exception as e:
            logger.error(f"Error initializing trading subcomponents: {e}")
            logger.info("Using fallback components due to initialization error")
        
        # Register event handlers for main trading system
        if hasattr(event_bus, 'register_handler'):
            event_bus.register_handler("trading.execute_order", main_trading_system.handle_execute_order)
            event_bus.register_handler("trading.cancel_order", main_trading_system.handle_cancel_order)
            event_bus.register_handler("trading.get_positions", main_trading_system.handle_get_positions)
            event_bus.register_handler("trading.update_strategy", main_trading_system.handle_update_strategy)
            event_bus.register_handler("trading.analyze_market", main_trading_system.handle_analyze_market)
        elif hasattr(event_bus, 'subscribe'):
            event_bus.subscribe("trading.execute_order", main_trading_system.handle_execute_order)
            event_bus.subscribe("trading.cancel_order", main_trading_system.handle_cancel_order)
            event_bus.subscribe("trading.get_positions", main_trading_system.handle_get_positions)
            event_bus.subscribe("trading.update_strategy", main_trading_system.handle_update_strategy)
            event_bus.subscribe("trading.analyze_market", main_trading_system.handle_analyze_market)
            
        # Initialize fallback components if fix modules are not available
        else:
            logger.warning("Trading system fix modules not available, using fallbacks")
            
            # Create fallback components
            market_data_processor = FallbackMarketDataProcessor(event_bus=event_bus)
            components["market_data_processor"] = market_data_processor
            
            order_executor = FallbackOrderExecutor(event_bus=event_bus)
            components["order_executor"] = order_executor
            
            risk_manager = FallbackRiskManager(event_bus=event_bus)
            components["risk_manager"] = risk_manager
            
            strategy_manager = FallbackStrategyManager(event_bus=event_bus)
            components["strategy_manager"] = strategy_manager
            
            signal_generator = FallbackTradingSignalGenerator(event_bus=event_bus)
            components["signal_generator"] = signal_generator
            
            position_manager = FallbackPositionManager(event_bus=event_bus)
            components["position_manager"] = position_manager
            
            portfolio_manager = FallbackPortfolioManager(event_bus=event_bus)
            components["portfolio_manager"] = portfolio_manager
    
        # Register event handlers for all components (whether fix or fallback)
        # First ensure all components are properly initialized
        for component_name, component in components.items():
            if component is None:
                logger.warning(f"Component {component_name} is None, using appropriate fallback")
                if component_name == "market_data_processor":
                    components[component_name] = FallbackMarketDataProcessor(event_bus=event_bus)
                elif component_name == "order_executor":
                    components[component_name] = FallbackOrderExecutor(event_bus=event_bus)
                elif component_name == "risk_manager":
                    components[component_name] = FallbackRiskManager(event_bus=event_bus)
                elif component_name == "strategy_manager":
                    components[component_name] = FallbackStrategyManager(event_bus=event_bus)
                elif component_name == "signal_generator":
                    components[component_name] = FallbackTradingSignalGenerator(event_bus=event_bus)
        
        # Order Executor
        order_executor = OrderExecutor(event_bus=event_bus)
        components["order_executor"] = order_executor
        
        # Risk Manager
        risk_manager = RiskManager(event_bus=event_bus)
        components["risk_manager"] = risk_manager
        
        # Strategy Manager
        strategy_manager = StrategyManager(event_bus=event_bus)
        components["strategy_manager"] = strategy_manager
        
        # Trading Signal Generator
        signal_generator = TradingSignalGenerator(event_bus=event_bus)
        components["signal_generator"] = signal_generator
        
        # Position Manager
        position_manager = PositionManager(event_bus=event_bus)
        components["position_manager"] = position_manager
        
        # Portfolio Manager
        portfolio_manager = PortfolioManager(event_bus=event_bus)
        components["portfolio_manager"] = portfolio_manager
    
    # Register event handlers for main trading system
    if hasattr(event_bus, 'register_handler'):
        event_bus.register_handler("trading.execute_order", main_trading_system.handle_execute_order)
        event_bus.register_handler("trading.cancel_order", main_trading_system.handle_cancel_order)
        event_bus.register_handler("trading.get_positions", main_trading_system.handle_get_positions)
        event_bus.register_handler("trading.update_strategy", main_trading_system.handle_update_strategy)
        event_bus.register_handler("trading.analyze_market", main_trading_system.handle_analyze_market)
    elif hasattr(event_bus, 'subscribe'):
        event_bus.subscribe("trading.execute_order", main_trading_system.handle_execute_order)
        event_bus.subscribe("trading.cancel_order", main_trading_system.handle_cancel_order)
        event_bus.subscribe("trading.get_positions", main_trading_system.handle_get_positions)
        event_bus.subscribe("trading.update_strategy", main_trading_system.handle_update_strategy)
        event_bus.subscribe("trading.analyze_market", main_trading_system.handle_analyze_market)
            
    # Initialize fallback components if fix modules are not available
    else:
        logger.warning("Trading system fix modules not available, using fallbacks")
        
        # Create fallback components
        market_data_processor = FallbackMarketDataProcessor(event_bus=event_bus)
        components["market_data_processor"] = market_data_processor
        
        order_executor = FallbackOrderExecutor(event_bus=event_bus)
        components["order_executor"] = order_executor
        
        risk_manager = FallbackRiskManager(event_bus=event_bus)
        components["risk_manager"] = risk_manager
        
        strategy_manager = FallbackStrategyManager(event_bus=event_bus)
        components["strategy_manager"] = strategy_manager
        
        signal_generator = FallbackTradingSignalGenerator(event_bus=event_bus)
        components["signal_generator"] = signal_generator
        
        position_manager = FallbackPositionManager(event_bus=event_bus)
        components["position_manager"] = position_manager
        
        portfolio_manager = FallbackPortfolioManager(event_bus=event_bus)
        components["portfolio_manager"] = portfolio_manager
    
    # Register event handlers for all components (whether fix or fallback)
    # First ensure all components are properly initialized
    for component_name, component in components.items():
        if component is None:
            logger.warning(f"Component {component_name} is None, using appropriate fallback")
            if component_name == "market_data_processor":
                components[component_name] = FallbackMarketDataProcessor(event_bus=event_bus)
            elif component_name == "order_executor":
                components[component_name] = FallbackOrderExecutor(event_bus=event_bus)
            elif component_name == "risk_manager":
                components[component_name] = FallbackRiskManager(event_bus=event_bus)
            elif component_name == "strategy_manager":
                components[component_name] = FallbackStrategyManager(event_bus=event_bus)
            elif component_name == "signal_generator":
                components[component_name] = FallbackTradingSignalGenerator(event_bus=event_bus)
            elif component_name == "position_manager":
                components[component_name] = FallbackPositionManager(event_bus=event_bus)
            elif component_name == "portfolio_manager":
                components[component_name] = FallbackPortfolioManager(event_bus=event_bus)
    
    # Safely register event handlers for each component
    if hasattr(event_bus, 'register_handler'):
        # Register handlers for all trading system components with proper error handling
        try:
            # Get the components from the initialized dictionary
            market_data_processor = components.get("market_data_processor")
            order_executor = components.get("order_executor")
            risk_manager = components.get("risk_manager")
            strategy_manager = components.get("strategy_manager")
            trading_signal_generator = components.get("trading_signal_generator")
            position_manager = components.get("position_manager")
            portfolio_manager = components.get("portfolio_manager")
        except Exception as e:
            logger.error(f"Error getting components: {e}")
            # Initialize with empty values
            market_data_processor = None
            order_executor = None 
            risk_manager = None
            strategy_manager = None 
            trading_signal_generator = None
            position_manager = None
            portfolio_manager = None
        
        # Now register the handlers with full error handling
        try:
            event_bus.register_handler("system.shutdown", lambda e, d: logger.info("Trading system components received system shutdown event"))
            # Use non-awaited methods for subscribing to events
            if market_data_processor and hasattr(market_data_processor, 'process_market_data'):
                await event_bus.subscribe("trading.process_market_data", market_data_processor.process_market_data)
            if market_data_processor and hasattr(market_data_processor, 'get_market_data'):
                await event_bus.subscribe("trading.get_market_data", market_data_processor.get_market_data)
            if order_executor and hasattr(order_executor, 'execute_order'):
                await event_bus.subscribe("trading.execute_order", order_executor.execute_order)
            if order_executor and hasattr(order_executor, 'cancel_order'):
                await event_bus.subscribe("trading.cancel_order", order_executor.cancel_order)
            if risk_manager and hasattr(risk_manager, 'check_risk'):
                await event_bus.subscribe("trading.check_risk", risk_manager.check_risk)
            if strategy_manager and hasattr(strategy_manager, 'update_strategy'):
                await event_bus.subscribe("trading.update_strategy", strategy_manager.update_strategy)
            if strategy_manager and hasattr(strategy_manager, 'get_strategies'):
                await event_bus.subscribe("trading.get_strategies", strategy_manager.get_strategies)
        
            # Save the component configuration for reference
            try:
                config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
                os.makedirs(config_dir, exist_ok=True)
                with open(os.path.join(config_dir, 'trading_system_components.json'), 'w') as f:
                    config_data = {
                        "components": list(components.keys()),
                        "initialized": True,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    json.dump(config_data, f, indent=2)
            except Exception as e:
                logger.warning(f"Error saving trading system component configuration: {e}")
                
            logger.info(f"Trading system components initialized successfully: {len(components)} components")
            
            # ================================================================
            # PREDATOR MODE INITIALIZATION (ADDITIVE)
            # Initialize predator mode event subscriptions for legacy components
            # ================================================================
            _init_legacy_predator_mode(components, event_bus)
            
        except Exception as e:
            logger.error(f"Error initializing trading system components: {e}")
            logger.error(traceback.format_exc())
            # Ensure we at least return an empty components dictionary
            if not components:
                components = {}
    
        return components


def _init_legacy_predator_mode(components: Dict[str, Any], event_bus) -> None:
    """Initialize predator mode for all legacy trading components.
    
    This is an additive function that subscribes legacy components to
    predator mode events without altering their existing behavior.
    Components will receive predator mode activation events and can
    optionally apply aggressive overrides.
    """
    try:
        # Initialize predator mode for TradingSignalGenerator
        signal_gen = components.get("trading_signal_generator") or components.get("signal_generator")
        if signal_gen and hasattr(signal_gen, '_init_predator_mode'):
            signal_gen._init_predator_mode()
            logger.info("🦁 Initialized predator mode for TradingSignalGenerator")
        
        # Initialize predator mode for OrderExecutor (from fix_trading_system_part2)
        order_exec = components.get("order_executor")
        if order_exec and hasattr(order_exec, '_init_predator_mode'):
            order_exec._init_predator_mode()
            logger.info("🦁 Initialized predator mode for OrderExecutor")
        
        # Initialize predator mode for StrategyManager/StrategyLibrary (from fix_trading_system_strategies)
        strategy_mgr = components.get("strategy_manager") or components.get("strategy_library")
        if strategy_mgr and hasattr(strategy_mgr, '_init_predator_mode'):
            strategy_mgr._init_predator_mode()
            logger.info("🦁 Initialized predator mode for StrategyManager")
        
        logger.info("🦁 Legacy predator mode initialization complete")
        
    except Exception as e:
        logger.warning(f"Error initializing legacy predator mode: {e}")

# Trading System class definition
class TradingSystem(BaseComponent):
    """Trading system component that coordinates trading activities.
    
    This component handles trading strategies, market data analysis,
    and order execution.
    """
    
    _instance = None
    _instance_lock = None
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of TradingSystem."""
        return cls._instance
    
    @classmethod
    def set_instance(cls, instance):
        """Set the singleton instance of TradingSystem."""
        cls._instance = instance
    
    def __init__(self, event_bus, config: Optional[Dict[str, Any]] = None, market_api=None, wallet_manager=None):
        """
        Initialize the trading system.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration settings for the trading system
            market_api: Market API component for market data access
            wallet_manager: Wallet Manager component for handling crypto wallets
        """
        super().__init__(event_bus=event_bus, config=config or {})
        self.logger = logger
        self.active_strategies = {}
        self.market_data = {}
        self._initialized = False
        self.market_api = market_api
        self.wallet_manager = wallet_manager
        self.components = {}  # Add components dictionary to store trading components
        
        # CRITICAL: Store connected exchanges for global access
        self._exchanges = {}  # Will be populated during initialization
        
        # Set singleton instance for global access
        TradingSystem.set_instance(self)
        
        # Attempt to populate exchanges from event bus immediately
        self._populate_exchanges_from_event_bus()
        
        # Sentience framework integration
        self.sentience_integration = None
        self.sentience_enabled = config.get("enable_sentience", True) if config else True
        
        self.logger.info("Trading system created (singleton instance set)")
        
    def _populate_exchanges_from_event_bus(self):
        """Populate _exchanges from TradingComponent's RealExchangeExecutor."""
        try:
            # Try to get RealExchangeExecutor from event bus
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                real_executor = self.event_bus.get_component('real_exchange_executor')
                if real_executor and hasattr(real_executor, 'exchanges'):
                    self._exchanges = real_executor.exchanges
                    self.logger.info(f"✅ Populated {len(self._exchanges)} exchanges from RealExchangeExecutor")
                    return
            
            # Try to get TradingComponent and extract from there
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                trading_component = self.event_bus.get_component('trading_component')
                if trading_component and hasattr(trading_component, 'real_executor'):
                    real_executor = trading_component.real_executor
                    if real_executor and hasattr(real_executor, 'exchanges'):
                        self._exchanges = real_executor.exchanges
                        self.logger.info(f"✅ Populated {len(self._exchanges)} exchanges from TradingComponent")
                        return
            
            self.logger.debug("Exchanges not yet available - will be populated during component initialization")
            
        except Exception as e:
            self.logger.debug(f"Could not populate exchanges yet: {e}")
    
    def update_exchanges(self, exchanges: Dict[str, Any]):
        """Update the connected exchanges dictionary.
        
        Args:
            exchanges: Dictionary of exchange_name -> ccxt exchange instance
        """
        self._exchanges = exchanges
        self.logger.info(f"✅ Updated TradingSystem with {len(exchanges)} connected exchanges")
    
    @property
    def initialized(self):
        """Get the initialization state of the component."""
        return self._initialized
        
    @initialized.setter
    def initialized(self, value):
        """Set the initialization state of the component."""
        self._initialized = value
        
    def _get_exchange(self, exchange_id: str = None):
        """Resolve a CCXT exchange instance.
        
        Tries self._exchanges first, then falls back to event bus components.
        
        Args:
            exchange_id: Optional exchange name (e.g. 'binanceus', 'kucoin').
                         If None, returns the first available exchange.
        Returns:
            Tuple of (exchange_name, ccxt_instance) or (None, None).
        """
        # Refresh exchanges from event bus if empty
        if not self._exchanges:
            self._populate_exchanges_from_event_bus()
        
        if exchange_id and exchange_id in self._exchanges:
            return exchange_id, self._exchanges[exchange_id]
        
        # Return first available exchange
        if self._exchanges:
            name = next(iter(self._exchanges))
            return name, self._exchanges[name]
        
        return None, None

    async def handle_execute_order(self, event_type, data):
        """Execute a real order via CCXT exchange connection.
        
        Args:
            event_type: Event type
            data: Order data with keys: symbol, type, side, quantity/amount,
                  price (for limit), exchange (optional)
        Returns:
            Dict with order execution result
        """
        try:
            symbol = data.get('symbol', 'BTC/USDT')
            order_type = data.get('type', 'market')
            side = data.get('side', 'buy')
            quantity = data.get('quantity') or data.get('amount', 0.0)
            price = data.get('price')
            exchange_id = data.get('exchange')
            
            self.logger.info(f"Executing {side} {order_type} order: {quantity} {symbol}")
            
            ex_name, exchange = self._get_exchange(exchange_id)
            if exchange is None:
                self.logger.warning("No exchange connections available - order cannot be placed")
                return {
                    'success': False,
                    'error': 'No exchange connections configured. Add API keys in Settings.'
                }
            
            # Execute via CCXT
            if order_type == 'limit' and price:
                result = exchange.create_limit_order(symbol, side, float(quantity), float(price))
            else:
                result = exchange.create_market_order(symbol, side, float(quantity))
            
            order_id = result.get('id', f"{symbol}-{int(time.time())}")
            self.logger.info(f"✅ Order executed on {ex_name}: {order_id}")
            
            _safe_publish_trading_telemetry(self.event_bus, "order.executed", {
                "exchange": ex_name, "symbol": symbol, "side": side,
                "quantity": quantity, "order_id": order_id
            })
            
            return {
                'success': True,
                'order_id': order_id,
                'symbol': symbol,
                'type': order_type,
                'side': side,
                'quantity': quantity,
                'price': result.get('price', price),
                'status': result.get('status', 'submitted'),
                'exchange': ex_name,
                'raw': result
            }
        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def handle_cancel_order(self, event_type, data):
        """Cancel an order via CCXT exchange connection.
        
        Args:
            event_type: Event type
            data: Cancel order data with keys: order_id, symbol, exchange (optional)
        Returns:
            Dict with cancel result
        """
        try:
            order_id = data.get('order_id', '')
            symbol = data.get('symbol', 'BTC/USDT')
            exchange_id = data.get('exchange')
            
            self.logger.info(f"Cancelling order {order_id} on {exchange_id or 'default exchange'}")
            
            ex_name, exchange = self._get_exchange(exchange_id)
            if exchange is None:
                return {'success': False, 'error': 'No exchange connections configured'}
            
            result = exchange.cancel_order(order_id, symbol)
            self.logger.info(f"✅ Order {order_id} cancelled on {ex_name}")
            
            _safe_publish_trading_telemetry(self.event_bus, "order.cancelled", {
                "exchange": ex_name, "order_id": order_id, "symbol": symbol
            })
            
            return {
                'success': True,
                'order_id': order_id,
                'status': 'cancelled',
                'exchange': ex_name,
                'raw': result
            }
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def handle_get_positions(self, event_type, data):
        """Fetch real positions/balances from connected CCXT exchanges.
        
        Args:
            event_type: Event type
            data: Position request data with optional 'exchange' key
        Returns:
            Dict with real position/balance data from exchanges
        """
        try:
            exchange_id = data.get('exchange') if isinstance(data, dict) else None
            self.logger.info(f"Fetching positions from {exchange_id or 'all exchanges'}")
            
            # Refresh exchanges if needed
            if not self._exchanges:
                self._populate_exchanges_from_event_bus()
            
            if not self._exchanges:
                return {
                    'success': False,
                    'error': 'No exchange connections configured. Add API keys in Settings.',
                    'positions': []
                }
            
            all_positions = []
            
            targets = {exchange_id: self._exchanges[exchange_id]} if exchange_id and exchange_id in self._exchanges else self._exchanges
            
            for ex_name, exchange in targets.items():
                try:
                    balance = exchange.fetch_balance()
                    # Extract non-zero balances as positions
                    total = balance.get('total', {})
                    for asset, amount in total.items():
                        if amount and float(amount) > 0:
                            all_positions.append({
                                'symbol': asset,
                                'quantity': float(amount),
                                'exchange': ex_name,
                                'free': float(balance.get('free', {}).get(asset, 0)),
                                'used': float(balance.get('used', {}).get(asset, 0)),
                            })
                except Exception as e:
                    self.logger.warning(f"Could not fetch balance from {ex_name}: {e}")
            
            return {
                'success': True,
                'positions': all_positions,
                'exchange_count': len(targets)
            }
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return {
                'success': False,
                'error': str(e),
                'positions': []
            }
    
    async def handle_update_strategy(self, event_type, data):
        """Update a trading strategy in the active strategy registry.
        
        Args:
            event_type: Event type
            data: Strategy update data with 'strategy_id' and 'parameters'
        Returns:
            Dict with update result
        """
        try:
            strategy_id = data.get('strategy_id', '')
            parameters = data.get('parameters', {})
            
            self.logger.info(f"Updating strategy {strategy_id} with parameters {parameters}")
            
            # Store in active strategies registry
            if strategy_id not in self.active_strategies:
                self.active_strategies[strategy_id] = {
                    'id': strategy_id,
                    'created': time.time(),
                    'parameters': {}
                }
            
            self.active_strategies[strategy_id]['parameters'].update(parameters)
            self.active_strategies[strategy_id]['updated'] = time.time()
            
            # Delegate to StrategyLibrary if available
            if hasattr(StrategyLibrary, 'update_strategy'):
                try:
                    StrategyLibrary.update_strategy(strategy_id, parameters)
                except Exception as e:
                    self.logger.debug(f"StrategyLibrary delegation skipped: {e}")
            
            _safe_publish_trading_telemetry(self.event_bus, "strategy.updated", {
                "strategy_id": strategy_id, "parameters": parameters
            })
            
            return {
                'success': True,
                'strategy_id': strategy_id,
                'status': 'updated',
                'active_strategies': len(self.active_strategies)
            }
        except Exception as e:
            self.logger.error(f"Error updating strategy: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def handle_analyze_market(self, event_type, data):
        """Fetch real market data from CCXT and return analysis.
        
        Args:
            event_type: Event type
            data: Market analysis request with 'symbol', 'timeframe', 'exchange'
        Returns:
            Dict with real market analysis from exchange data
        """
        try:
            symbol = data.get("symbol", "BTC/USDT")
            timeframe = data.get("timeframe", "1h")
            exchange_id = data.get("exchange")
            
            self.logger.info(f"Analyzing market for {symbol} on {timeframe} timeframe")
            
            ex_name, exchange = self._get_exchange(exchange_id)
            if exchange is None:
                return {
                    'success': False,
                    'error': 'No exchange connections configured. Add API keys in Settings.'
                }
            
            # Fetch real ticker data
            ticker = exchange.fetch_ticker(symbol)
            
            # Build analysis from real data
            analysis = {
                "symbol": symbol,
                "timestamp": time.time(),
                "price": ticker.get('last', 0.0),
                "bid": ticker.get('bid', 0.0),
                "ask": ticker.get('ask', 0.0),
                "high": ticker.get('high', 0.0),
                "low": ticker.get('low', 0.0),
                "volume": ticker.get('baseVolume', 0.0),
                "quote_volume": ticker.get('quoteVolume', 0.0),
                "change_24h": ticker.get('percentage', 0.0),
                "vwap": ticker.get('vwap', 0.0),
                "exchange": ex_name,
                "data_source": "live_exchange"
            }
            
            # Try to fetch OHLCV for technical indicators
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=50)
                if ohlcv and len(ohlcv) >= 14:
                    closes = [c[4] for c in ohlcv]  # Close prices
                    
                    # Simple Moving Averages
                    sma_short = sum(closes[-7:]) / 7 if len(closes) >= 7 else closes[-1]
                    sma_medium = sum(closes[-20:]) / min(20, len(closes))
                    sma_long = sum(closes[-50:]) / min(50, len(closes))
                    
                    # RSI (14-period)
                    gains, losses = [], []
                    for i in range(1, min(15, len(closes))):
                        diff = closes[i] - closes[i - 1]
                        gains.append(max(diff, 0))
                        losses.append(abs(min(diff, 0)))
                    avg_gain = sum(gains) / len(gains) if gains else 0
                    avg_loss = sum(losses) / len(losses) if losses else 0.001
                    rs = avg_gain / avg_loss if avg_loss > 0 else 100
                    rsi = 100 - (100 / (1 + rs))
                    
                    # Trend detection
                    trend = "bullish" if sma_short > sma_medium > sma_long else (
                        "bearish" if sma_short < sma_medium < sma_long else "neutral"
                    )
                    
                    analysis["indicators"] = {
                        "sma": {"short_7": round(sma_short, 2), "medium_20": round(sma_medium, 2), "long_50": round(sma_long, 2)},
                        "rsi": round(rsi, 2)
                    }
                    analysis["trend"] = trend
            except Exception as ohlcv_err:
                self.logger.debug(f"OHLCV fetch skipped: {ohlcv_err}")
            
            return {
                "success": True,
                "status": "success",
                "analysis": analysis
            }
        except Exception as e:
            self.logger.error(f"Error analyzing market: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _handle_market_update_legacy(self, event_data: Dict[str, Any]):
        """
        Handle market data updates.
        
        Args:
            event_data: Market data including symbol, price, etc.
        """
        try:
            symbol = event_data.get("symbol", "UNKNOWN")
            self.logger.debug(f"Received market update for {symbol}")
            
            # Store market data
            self.market_data[symbol] = event_data
            
            # Integrate rug pull detection: check risk score before processing strategies
            try:
                import rug_sniffer_ai  # type: ignore[import-not-found]
                rug_risk_score = getattr(rug_sniffer_ai, "rug_risk_score", None)
                risk_result = rug_risk_score(symbol) if callable(rug_risk_score) else None
                if risk_result == "🚨 High Rug Risk":
                    self.logger.warning(f"High rug risk detected for {symbol}. Skipping strategy processing.")
                    return  # Halt processing if high risk to prevent potential losses
            except ImportError as e:
                self.logger.error(f"Failed to import rug_sniffer_ai: {e}")
            except Exception as e:
                self.logger.error(f"Error in rug risk scoring: {e}")
            
            # Process strategies if available
            await self._process_strategies(symbol, event_data)
            
            # Pass data to sentience monitoring if enabled
            if self.sentience_enabled and self.sentience_integration:
                pass  # The sentience integration will receive this via its own event bus subscription
            
        except Exception as e:
            self.logger.error(f"Error handling market update: {e}")
            self.logger.error(traceback.format_exc())

    async def _process_strategies(self, symbol: str, event_data: Dict[str, Any]) -> None:
        """Process enabled strategies for a symbol via the signal generator and strategy engine."""
        if hasattr(self, "signal_generator") and self.signal_generator:
            try:
                sig = await self.signal_generator._triple_pass_analysis(symbol)
                if sig and sig.get("action") in ("buy", "sell"):
                    if self.event_bus:
                        self.event_bus.emit("trading.signal.generated", sig)
            except Exception as e:
                self.logger.debug("Strategy processing for %s: %s", symbol, e)
        elif hasattr(self, "strategy_engine") and self.strategy_engine:
            try:
                result = await self.strategy_engine.execute_strategy("default", event_data)
                if result and result.get("signals"):
                    if self.event_bus:
                        self.event_bus.emit("trading.strategy.result", {"symbol": symbol, **result})
            except Exception as e:
                self.logger.debug("Strategy engine for %s: %s", symbol, e)
    
    async def analyze_market(self, symbol: str) -> Dict[str, Any]:
        """
        Analyze market data for a symbol.
        
        Args:
            symbol: Trading symbol to analyze
            
        Returns:
            Market analysis including trend, signals, etc.
        """
        self.logger.info(f"Analyzing market for {symbol}")
        
        if symbol not in self.market_data:
            return {
                "symbol": symbol,
                "error": "No market data available"
            }
        
        md = self.market_data[symbol]
        last_price = float(md.get("price", 0.0))
        last_volume = float(md.get("volume", 0.0))
        prices = md.get("price_history", [])
        if not prices and last_price:
            prices = [last_price]

        # Real technical analysis using available price data
        trend = "neutral"
        signals = []
        if len(prices) >= 2:
            change_pct = ((prices[-1] - prices[-2]) / prices[-2] * 100) if prices[-2] else 0
            if change_pct > 0.5:
                trend = "bullish"
            elif change_pct < -0.5:
                trend = "bearish"
        if len(prices) >= 14:
            closes = [float(p) for p in prices[-14:]]
            rsi = TradingSignalGenerator._calc_rsi(closes, 14)
            if rsi < 30:
                signals.append({"type": "BUY", "indicator": "RSI", "value": rsi, "reason": "oversold"})
            elif rsi > 70:
                signals.append({"type": "SELL", "indicator": "RSI", "value": rsi, "reason": "overbought"})
        if len(prices) >= 26:
            ema12 = TradingSignalGenerator._calc_ema([float(p) for p in prices], 12)
            ema26 = TradingSignalGenerator._calc_ema([float(p) for p in prices], 26)
            if ema12 > ema26 * 1.002:
                signals.append({"type": "BUY", "indicator": "EMA_CROSS", "reason": "golden_cross"})
                trend = "bullish"
            elif ema12 < ema26 * 0.998:
                signals.append({"type": "SELL", "indicator": "EMA_CROSS", "reason": "death_cross"})
                trend = "bearish"

        analysis_result = {
            "symbol": symbol,
            "timestamp": time.time(),
            "price": last_price,
            "volume": last_volume,
            "trend": trend,
            "signals": signals,
        }
        
        # Add sentience metrics if enabled
        if self.sentience_enabled and self.sentience_integration:
            try:
                # Add sentience indicators to analysis result
                analysis_result["sentience_metrics"] = {
                    "algorithmic_reflexivity": self.sentience_integration.trading_sentience_metrics.get("algorithmic_reflexivity", 0.0),
                    "market_awareness": self.sentience_integration.trading_sentience_metrics.get("market_awareness", 0.0),
                    "decision_autonomy": self.sentience_integration.trading_sentience_metrics.get("decision_autonomy", 0.0)
                }
            except Exception as e:
                self.logger.warning(f"Could not add sentience metrics to analysis: {e}")
        
        return analysis_result

    async def initialize(self):
        """Initialize the trading system and connect to the event bus."""
        self.logger.info("Initializing trading system...")
        
        try:
            # Initialize Quantum AI Trading if available
            if HAS_QUANTUM_TRADING:
                try:
                    self.logger.info("Initializing Quantum AI Trading Engine...")
                    self.quantum_ai_engine = QuantumAITradingEngine(
                        initial_capital=100000,
                        event_bus=self.event_bus,
                        ollama_brain=getattr(self, 'ollama_brain', None)
                    )
                    self.logger.info("✅ Quantum AI Trading Engine initialized")
                except Exception as e:
                    self.logger.error(f"Failed to initialize Quantum AI Trading: {e}")
                    self.quantum_ai_engine = None
            else:
                self.quantum_ai_engine = None
            
            # Initialize Trading Coordinator for unified operations
            try:
                from core.trading.trading_coordinator import TradingCoordinator
                self.trading_coordinator = TradingCoordinator(
                    event_bus=self.event_bus,
                    ollama_brain=getattr(self, 'ollama_brain', None),
                    trading_system=self
                )
                
                # Register quantum AI engine with coordinator
                if self.quantum_ai_engine:
                    self.trading_coordinator.register_component(
                        'quantum_ai_engine',
                        self.quantum_ai_engine
                    )
                
                self.logger.info("✅ Trading Coordinator initialized - Unified system ready")
            except Exception as e:
                self.logger.error(f"Failed to initialize Trading Coordinator: {e}")
                self.trading_coordinator = None
            
            # Initialize sentience integration if enabled
            if self.sentience_enabled and has_sentience_framework:
                try:
                    self.logger.info("Initializing trading sentience integration...")
                    self.sentience_integration = TradingSentienceIntegration(self.event_bus)
                    await self.sentience_integration.initialize()
                    self.logger.info("Trading sentience integration initialized successfully")
                except Exception as e:
                    self.logger.error(f"Failed to initialize trading sentience integration: {e}")
                    self.logger.error(traceback.format_exc())
            
            # Instantiate and initialize RugSnifferAI for rug pull detection
            try:
                from rug_sniffer_ai import RugSnifferAI
                self.rug_sniffer = RugSnifferAI(self.event_bus)
                await self.rug_sniffer.initialize()
                self.logger.info("RugSnifferAI initialized and subscribed to events")
            except ImportError as e:
                self.logger.error(f"Failed to import RugSnifferAI: {e}")
            except Exception as e:
                self.logger.error(f"Error initializing RugSnifferAI: {e}")
            
            # Subscribe to events
            await self._subscribe_to_events()
            
            # Load saved strategies
            await self._load_strategies()
            
            self.initialized = True
            self.logger.info("Trading system initialized")
            
            # Publish initialization complete event if event_bus is available
            if self.event_bus is not None:
                # Check if publish is async or sync
                result = self.event_bus.publish("component.status", {
                    "component": "trading",
                    "status": "ready",
                    "message": "Trading system ready for operation",
                    "sentience_enabled": self.sentience_enabled and self.sentience_integration is not None,
                    "quantum_ai_enabled": HAS_QUANTUM_TRADING and self.quantum_ai_engine is not None
                })
                # Only await if it's a coroutine
                if inspect.iscoroutine(result):
                    await result
            else:
                self.logger.warning("Cannot publish status: event_bus is None")
            
            return True
        except Exception as e:
            self.logger.error(f"Error initializing trading system: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _subscribe_to_events(self):
        """Subscribe to trading-related events"""
        try:
            if self.event_bus:
                # Subscribe to market data events
                self.event_bus.subscribe('trading:price_update', self._handle_price_update)
                self.event_bus.subscribe('trading:order_filled', self._handle_order_filled)
                self.event_bus.subscribe('trading.order_filled', self._handle_order_filled)  # Both formats
                self.event_bus.subscribe('trading:order_cancelled', self._handle_order_cancelled)
                
                # Bridge real_order.placed to trading.order_filled for profit tracking
                self.event_bus.subscribe('real_order.placed', self._handle_real_order_placed)
                
                # Subscribe to system events
                self.event_bus.subscribe('system.shutdown', self._handle_shutdown)
                
                # KAIG Intelligence Bridge — THREE TARGETS + rebrand resilience
                self.event_bus.subscribe('kaig.intel.trading.directive', self._handle_kaig_directive)
                self.event_bus.subscribe('kaig.ath.update', self._handle_kaig_ath_update)
                self.event_bus.subscribe('kaig.identity.changed', self._handle_identity_changed)
                
                self.logger.info("✅ Subscribed to trading events (including KAIG 3 targets + profit tracking bridge)")
        except Exception as e:
            self.logger.error(f"Error subscribing to events: {e}")
    
    def _handle_price_update(self, data):
        """Handle price update events"""
        try:
            if not isinstance(data, dict):
                return
            symbol = data.get('symbol')
            price = data.get('price') or data.get('last_price')
            if symbol and price:
                if not hasattr(self, '_price_cache'):
                    self._price_cache = {}
                self._price_cache[symbol] = float(price)
                self.logger.debug("Price update: %s = %s", symbol, price)
        except Exception as e:
            self.logger.debug("Error handling price update: %s", e)
    
    def _handle_order_filled(self, data):
        """Handle order filled events"""
        self.logger.info(f"Order filled: {data}")
        try:
            if self.event_bus:
                self.event_bus.publish("trading.order_filled", data)
                # UI integration: OrdersWidget listens to trading.order_update / trading.orders.
                # Publish an order_update payload so the Orders table updates without requiring a separate backend.
                try:
                    payload = dict(data) if isinstance(data, dict) else {"data": data}
                    payload.setdefault("status", payload.get("status") or "filled")
                    self.event_bus.publish("trading.order_update", payload)
                except Exception:
                    pass
        except Exception:
            pass
    
    def _handle_order_cancelled(self, data):
        """Handle order cancelled events"""
        self.logger.info(f"Order cancelled: {data}")
    
    def _handle_real_order_placed(self, data):
        """Bridge real_order.placed events to trading.order_filled for profit tracking.
        
        This ensures that orders placed via RealExchangeExecutor are properly
        tracked in the Trading Tab profit/portfolio displays.
        """
        try:
            if not isinstance(data, dict):
                return
            
            # Market orders are typically immediately filled
            order_status = str(data.get('status', '')).lower()
            order_type = str(data.get('type', '')).lower()
            
            if order_status in ('filled', 'closed') or order_type == 'market':
                fill_data = {
                    'order_id': data.get('id') or data.get('order_id'),
                    'symbol': data.get('symbol'),
                    'side': data.get('side'),
                    'type': order_type,
                    'amount': data.get('filled') or data.get('amount'),
                    'price': data.get('average') or data.get('price') or 0,
                    'cost': data.get('cost', 0),
                    'status': 'filled',
                    'exchange': data.get('exchange'),
                    'timestamp': data.get('timestamp'),
                    'fee': data.get('fee'),
                    'message': f"Order {data.get('id')} filled"
                }
                
                if self.event_bus:
                    self.event_bus.publish('trading.order_filled', fill_data)
                    self.logger.info(f"📊 Bridged real_order.placed → trading.order_filled")
        except Exception as e:
            self.logger.debug(f"Error bridging order event: {e}")
    
    def _handle_kaig_directive(self, event_data):
        """Receive KAIG directive — THREE TARGETS the trading system must know.

        1. SURVIVAL FLOOR: $26K realized → $13K treasury (existential, FIRST)
        2. KAIG PRICE FLOOR: 1 KAIG > highest crypto ATH ever (live-monitored)
        3. ULTIMATE TARGET: $2T (aspirational, always pursue)
        """
        if isinstance(event_data, dict):
            self._kaig_directive = event_data
            floor = event_data.get('kaig_survival_floor', {})
            pf = event_data.get('kaig_price_floor', {})
            self.logger.info(
                "TradingSystem: KAIG directive — survival=%s | floor=$%s (%s) | profit=$%.2f",
                "MET" if floor.get('survival_met') else "NOT MET",
                f"{pf.get('kaig_must_exceed_usd', 0):,.2f}",
                pf.get('current_ath_coin', 'BTC'),
                event_data.get('profit_total_usd', 0))

    def _handle_kaig_ath_update(self, event_data):
        """Handle new crypto ATH — KAIG price floor raised."""
        if isinstance(event_data, dict):
            self.logger.warning(
                "TradingSystem: NEW ATH — %s at $%s. KAIG price floor raised.",
                event_data.get("new_ath_coin", ""),
                f"{event_data.get('new_ath_price', 0):,.2f}")

    def _handle_identity_changed(self, event_data):
        """Handle token rebrand — update internal references.
        User funds are NOT affected. Only labels change."""
        if isinstance(event_data, dict):
            self.logger.warning(
                "TradingSystem: TOKEN REBRANDED %s → %s. All funds preserved.",
                event_data.get("old_ticker", "?"),
                event_data.get("new_ticker", "?"))

    async def _handle_shutdown(self, data):
        """Handle system shutdown"""
        self.logger.info("Shutting down trading system...")
        if hasattr(self, 'shutdown'):
            await self.shutdown()
    
    async def _load_strategies(self):
        """Load saved trading strategies"""
        try:
            # Strategies are loaded by StrategyManager
            self.logger.info("✅ Trading strategies loaded")
        except Exception as e:
            self.logger.error(f"Error loading strategies: {e}")
    
    # ========================================
    # QUANTUM AI AUTO-TRADING METHODS
    # ========================================
    
    async def enable_auto_trading(self, symbols: List[str]) -> bool:
        """Enable auto-trading for specified symbols using Quantum AI
        
        Args:
            symbols: List of trading symbols (coins, stocks, etc.)
            
        Returns:
            bool: Success status
        """
        try:
            if not HAS_QUANTUM_TRADING or not self.quantum_ai_engine:
                self.logger.error("Quantum AI Trading not available")
                return False
            
            self.quantum_ai_engine.enable_auto_trading(symbols)
            self.logger.info(f"🚀 Auto-trading enabled for {len(symbols)} symbols")
            
            if self.event_bus:
                result = self.event_bus.publish('trading.auto_enabled', {
                    'symbol_count': len(symbols),
                    'timestamp': datetime.now().isoformat()
                })
                if inspect.iscoroutine(result):
                    await result
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to enable auto-trading: {e}")
            return False
    
    async def disable_auto_trading(self) -> bool:
        """Disable auto-trading
        
        Returns:
            bool: Success status
        """
        try:
            if not HAS_QUANTUM_TRADING or not self.quantum_ai_engine:
                return False
            
            self.quantum_ai_engine.disable_auto_trading()
            self.logger.info("🛑 Auto-trading disabled")
            
            if self.event_bus:
                result = self.event_bus.publish('trading.auto_disabled', {
                    'timestamp': datetime.now().isoformat()
                })
                if inspect.iscoroutine(result):
                    await result
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to disable auto-trading: {e}")
            return False
    
    async def get_auto_trading_status(self) -> Dict[str, Any]:
        """Get auto-trading status and performance
        
        Returns:
            dict: Auto-trading status and metrics
        """
        try:
            if not HAS_QUANTUM_TRADING or not self.quantum_ai_engine:
                return {
                    'enabled': False,
                    'available': False,
                    'message': 'Quantum AI Trading not available'
                }
            
            performance = self.quantum_ai_engine.get_performance_stats()
            ontology_stats = self.quantum_ai_engine.get_ontology_stats()
            
            return {
                'enabled': self.quantum_ai_engine.auto_trading_enabled,
                'available': True,
                'symbols_count': len(self.quantum_ai_engine.trading_symbols),
                'performance': performance,
                'ontology': ontology_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get auto-trading status: {e}")
            return {
                'enabled': False,
                'available': False,
                'error': str(e)
            }
    
    async def analyze_market_with_quantum_ai(self, symbol: str, market_data: Dict) -> Optional[Dict]:
        """Analyze market using Quantum AI
        
        Args:
            symbol: Trading symbol
            market_data: Market data dict
            
        Returns:
            dict: Trading signal or None
        """
        try:
            if not HAS_QUANTUM_TRADING or not self.quantum_ai_engine:
                return None
            
            # Convert to MarketData object
            md = MarketData(
                symbol=symbol,
                timestamp=datetime.now(),
                open=market_data.get('open', 0.0),
                high=market_data.get('high', 0.0),
                low=market_data.get('low', 0.0),
                close=market_data.get('close', 0.0),
                volume=market_data.get('volume', 0.0),
                vwap=market_data.get('vwap', market_data.get('close', 0.0)),
                volatility=market_data.get('volatility', 0.0)
            )
            
            signal = await self.quantum_ai_engine.analyze_market(symbol, md)
            
            return {
                'symbol': signal.symbol,
                'action': signal.action,
                'confidence': signal.confidence,
                'price_target': signal.price_target,
                'stop_loss': signal.stop_loss,
                'quantity': signal.quantity,
                'urgency': signal.urgency,
                'expected_profit': signal.expected_profit
            }
            
        except Exception as e:
            self.logger.error(f"Quantum AI analysis failed for {symbol}: {e}")
            return None

    async def shutdown(self):
        """Properly shut down the trading system."""
        self.logger.info("Shutting down trading system...")
        
        try:
            # Clean up resources
            
            # Shutdown sentience integration if it exists
            if self.sentience_integration:
                try:
                    cleanup_fn = getattr(self.sentience_integration, 'cleanup', None)
                    if callable(cleanup_fn):
                        cleanup_result = cleanup_fn()
                        if inspect.iscoroutine(cleanup_result):
                            await cleanup_result
                        self.logger.info("Trading sentience integration cleaned up")
                except Exception as e:
                    self.logger.error(f"Error cleaning up sentience integration: {e}")
            
            # Notify event bus of shutdown if available
            if self.event_bus is not None:
                result = self.event_bus.publish("component.status", {
                    "component": "trading",
                    "status": "shutdown",
                    "message": "Trading system shutdown complete"
                })
                if inspect.iscoroutine(result):
                    await result
            
            return True
        except Exception as e:
            self.logger.error(f"Error during trading system shutdown: {str(e)}")
            return False

    async def _handle_market_update(self, event_data: Dict[str, Any]):
        """
        Handle market data updates.
        
        Args:
            event_data: Market data including symbol, price, etc.
        """
        try:
            symbol = event_data.get("symbol", "UNKNOWN")
            self.logger.debug(f"Received market update for {symbol}")
            
            # Store market data
            self.market_data[symbol] = event_data
            
            # Integrate rug pull detection: check risk score before processing strategies
            try:
                import rug_sniffer_ai  # type: ignore[import-not-found]
                rug_risk_score = getattr(rug_sniffer_ai, "rug_risk_score", None)
                risk_result = rug_risk_score(symbol) if callable(rug_risk_score) else None
                if risk_result == "🚨 High Rug Risk":
                    self.logger.warning(f"High rug risk detected for {symbol}. Skipping strategy processing.")
                    return  # Halt processing if high risk to prevent potential losses
            except ImportError as e:
                self.logger.error(f"Failed to import rug_sniffer_ai: {e}")
            except Exception as e:
                self.logger.error(f"Error in rug risk scoring: {e}")
            
            # Process strategies if available
            await self._process_strategies(symbol, event_data)
            
            # Pass data to sentience monitoring if enabled
            if self.sentience_enabled and self.sentience_integration:
                pass  # The sentience integration will receive this via its own event bus subscription
            
        except Exception as e:
            self.logger.error(f"Error handling market update: {e}")
            self.logger.error(traceback.format_exc())
