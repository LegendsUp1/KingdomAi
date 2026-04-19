"""
Trading Component for Kingdom AI

This module provides a Redis-integrated trading component that wraps the existing
trading engine with strict Redis connection requirements.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
import time
import json
import uuid

from core.base_component_v2 import BaseComponentV2
from core.redis_connector import RedisQuantumNexusConnector
from core.api_key_manager import APIKeyManager
from core.real_exchange_executor import (
    RealExchangeExecutor,
    OrderType as RealOrderType,
    OrderSide as RealOrderSide,
    select_profitable_exchanges,
)
from core.real_stock_executor import RealStockExecutor as StockExecutor
from core.exchange_universe import build_canonical_exchange_markets, build_real_exchange_api_keys
from core.trading_system import _safe_publish_trading_telemetry
from risk_manager import RiskManager

from core.kingdom_event_names import METACOGNITION_UPDATE

# Import existing trading engine components
from kingdom_trading_engine_core import (
    TradingEngineCore,
    OrderType,
    OrderSide,
    OrderStatus,
    Order,
)
from kingdom_integration_part1 import EventBus as LegacyEventBus, ComponentRegistry as LegacyComponentRegistry

class TradingComponent(BaseComponentV2):
    """
    Trading Component for Kingdom AI.
    
    This component integrates with the existing TradingEngineCore and enforces
    strict Redis connection requirements.
    """
    
    # Event types
    EVENT_ORDER_UPDATE = "trading.order_update"
    EVENT_POSITION_UPDATE = "trading.position_update"
    EVENT_MARKET_DATA = "trading.market_data"
    EVENT_TRADING_SIGNAL = "trading.signal"
    EVENT_TRADING_ERROR = "trading.error"
    
    def __init__(self, 
                 name: str = "TradingComponent",
                 event_bus: Optional[Any] = None,
                 config: Optional[Dict[str, Any]] = None):
        """Initialize the trading component.
        
        Args:
            name: Component name
            event_bus: Event bus for inter-component communication
            config: Configuration dictionary
        """
        try:
            from core.kingdom_config_loader import merge_config

            merged = merge_config(config or {})
        except Exception:
            merged = config or {}
        super().__init__(name=name, event_bus=event_bus, config=merged)
        
        # Initialize Redis connector
        self.redis = None
        
        # Initialize trading engine
        self.trading_engine = None

        # Live trading executor and API key manager
        self.api_key_manager: Optional[APIKeyManager] = None
        self.real_executor: Optional[RealExchangeExecutor] = None
        self.exchange_health: Dict[str, Any] = {}
        self.stock_executor: Optional[StockExecutor] = None
        self.broker_health: Dict[str, Any] = {}
        
        # Trading state
        self.positions = {}
        self.orders = {}
        self.market_data = {}
        self.canonical_markets: Dict[str, Dict[str, Any]] = {}
        self.market_data_interval_seconds = float(
            self.config.get(
                "market_data_interval_seconds",
                self.config.get("market_data_interval", 2.0),
            )
        )
        self.portfolio_update_interval_seconds = float(
            self.config.get(
                "portfolio_update_interval_seconds",
                self.config.get("portfolio_update_interval", 5.0),
            )
        )
        self._last_market_data_ts: float = 0.0
        self._last_portfolio_update_ts: float = 0.0
        
        # Trading parameters
        self.symbols = self.config.get('symbols', ['BTC/USD', 'ETH/USD', 'SOL/USD'])
        self.max_position_size = float(self.config.get('max_position_size', 10000.0))
        self.max_leverage = float(self.config.get('max_leverage', 10.0))
        self._last_health_snapshot_ts: float = 0.0
        self._last_broker_health_ts: float = 0.0
        self.risk_manager: Optional[RiskManager] = None
        self.enable_deterministic_risk_gate = bool(self.config.get("enable_deterministic_risk_gate", True))
        self.risk_gate_config = {
            "min_signal_confidence": float(self.config.get("min_signal_confidence", 0.55)),
            "max_position_notional": float(self.config.get("max_position_notional", self.max_position_size)),
            "max_market_data_age_seconds": float(self.config.get("max_market_data_age_seconds", 15.0)),
            "require_stop_loss": bool(self.config.get("require_stop_loss", False)),
            "require_take_profit": bool(self.config.get("require_take_profit", False)),
        }
        self.market_circuit_config = {
            "max_spread_pct": float(self.config.get("max_spread_pct", 1.25)),
            "max_abs_change_pct": float(self.config.get("max_abs_change_pct", 12.0)),
            "min_volume_24h": float(self.config.get("min_volume_24h", 1.0)),
            "halt_on_stale_data": bool(self.config.get("halt_on_stale_data", True)),
        }
        self.regime_thresholds = {
            "trend_change_pct": float(self.config.get("regime_trend_change_pct", 1.0)),
            "high_vol_change_pct": float(self.config.get("regime_high_vol_change_pct", 3.5)),
        }
        self.strategy_profiles = {
            "momentum": {"allowed_regimes": {"TRENDING_UP", "HIGH_VOLATILITY"}, "qty_mult": 1.0, "min_conf": 0.6},
            "trend": {"allowed_regimes": {"TRENDING_UP", "TRENDING_DOWN"}, "qty_mult": 0.9, "min_conf": 0.58},
            "mean_reversion": {"allowed_regimes": {"RANGE", "LOW_VOLATILITY"}, "qty_mult": 0.75, "min_conf": 0.57},
            "grid": {"allowed_regimes": {"RANGE", "LOW_VOLATILITY"}, "qty_mult": 0.6, "min_conf": 0.55},
            "arbitrage": {"allowed_regimes": {"RANGE", "LOW_VOLATILITY", "TRENDING_UP", "TRENDING_DOWN"}, "qty_mult": 0.8, "min_conf": 0.55},
            "default": {"allowed_regimes": {"TRENDING_UP", "TRENDING_DOWN", "RANGE", "LOW_VOLATILITY"}, "qty_mult": 0.8, "min_conf": 0.56},
        }
        self.rollout_stage = str(self.config.get("rollout_stage", "full")).lower()
        self.canary_symbols = {str(s).upper() for s in self.config.get("canary_symbols", [])}
        self._auto_trading_active = bool(self.config.get("auto_trading_enabled", True))
        self._latest_trading_system_readiness: Dict[str, Any] = {"state": "UNKNOWN", "analysis_ready": False}
        self._active_strategies = set()
        self._last_canary_result: Dict[str, Any] = {}
        self._autonomous_orchestrator: Optional[Any] = None
        self._capital_flow_processor: Optional[Any] = None
        self._botsofwallstreet: Optional[Any] = None
        self._autonomous_task: Optional[asyncio.Task] = None

    async def _initialize(self) -> None:
        """Initialize the trading component."""
        self.logger.info("Initializing Trading Component...")
        
        # Initialize Redis connection
        if not await self._init_redis():
            error_msg = "Failed to initialize Redis connection for Trading Component"
            self.logger.critical(error_msg)
            await self._shutdown_on_redis_failure()
            return
        
        # Initialize trading engine
        legacy_event_bus = LegacyEventBus()
        legacy_registry = LegacyComponentRegistry(legacy_event_bus)
        self.trading_engine = TradingEngineCore(
            event_bus=legacy_event_bus,
            registry=legacy_registry,
        )
        
        # Initialize trading engine
        if hasattr(self.trading_engine, 'initialize'):
            if asyncio.iscoroutinefunction(self.trading_engine.initialize):
                await self.trading_engine.initialize()
            else:
                self.trading_engine.initialize()
        
        # Initialize API key manager and real exchange executor for live trading
        try:
            self.api_key_manager = APIKeyManager.get_instance(
                event_bus=self.event_bus,
                config={}
            )
            self.api_key_manager.initialize_sync()

            # CRITICAL: Use the same mapping logic as real_exchange_smoke_test
            # so that any exchange/broker which passes the smoke test is wired
            # into RealExchangeExecutor with IDENTICAL api_keys.
            raw_keys = self.api_key_manager.api_keys
            api_keys = build_real_exchange_api_keys(raw_keys)

            if api_keys:
                self.real_executor = RealExchangeExecutor(api_keys, event_bus=self.event_bus)
                try:
                    if self.event_bus is not None and hasattr(self.event_bus, "register_component"):
                        self.event_bus.register_component("real_exchange_executor", self.real_executor)
                except Exception:
                    pass
                # Initial health snapshot
                self.exchange_health = await self.real_executor.get_exchange_health()
                await self.real_executor.publish_exchange_health_snapshot()
                
                # CRITICAL: Update TradingSystem singleton with connected exchanges
                try:
                    from core.trading_system import TradingSystem
                    trading_system = TradingSystem.get_instance()
                    if trading_system and hasattr(self.real_executor, 'exchanges'):
                        trading_system.update_exchanges(self.real_executor.exchanges)
                        self.logger.info(f"✅ Updated TradingSystem singleton with {len(self.real_executor.exchanges)} exchanges")
                except Exception as e:
                    self.logger.warning(f"Could not update TradingSystem with exchanges: {e}")
            else:
                self.logger.warning(
                    "RealExchangeExecutor not initialized: no API keys available for live exchanges",
                )
        except Exception as e:
            self.logger.error(f"Failed to initialize RealExchangeExecutor: {e}")

        # Initialize stock/forex broker executor for live stock trading
        try:
            if self.api_key_manager is not None:
                raw_keys = self.api_key_manager.api_keys
            else:
                raw_keys = {}
            if raw_keys:
                self.stock_executor = StockExecutor(raw_keys, event_bus=self.event_bus)
                try:
                    if self.event_bus is not None and hasattr(self.event_bus, "register_component"):
                        self.event_bus.register_component("real_stock_executor", self.stock_executor)
                except Exception:
                    pass
                self.broker_health = await self.stock_executor.get_broker_health()
                await self.stock_executor.publish_broker_health_snapshot()
        except Exception as e:
            self.logger.error(f"Failed to initialize RealStockExecutor: {e}")

        # Build canonical markets used by live loops
        try:
            if self.api_key_manager is not None:
                km_keys = self.api_key_manager.api_keys
            else:
                km_keys = {}
            if km_keys:
                self.canonical_markets = build_canonical_exchange_markets(km_keys)
        except Exception as e:
            self.logger.error("Failed to build canonical exchange markets: %s", e)
        
        # Load initial state
        await self._load_state()

        # Initialize deterministic risk gate helper
        try:
            self.risk_manager = RiskManager(event_bus=self.event_bus)
            await self.risk_manager.initialize()
        except Exception as e:
            self.logger.warning(f"RiskManager gate unavailable, continuing without strict gate: {e}")

        # Autonomous trading + capital flow (additive, config-gated; internal telemetry only)
        at_cfg = self.config.get("autonomous_trading") or {}
        if at_cfg.get("enabled"):
            try:
                from components.autonomous_trading import AutonomousOrchestrator
                from components.capital_flow_processor import CapitalFlowProcessor

                raw_keys = self.api_key_manager.api_keys if self.api_key_manager else {}
                api_keys = dict(raw_keys) if isinstance(raw_keys, dict) else {}
                self._autonomous_orchestrator = AutonomousOrchestrator(
                    event_bus=self.event_bus,
                    trading_engine=self.trading_engine,
                    risk_manager=self.risk_manager,
                    api_keys=api_keys,
                    stock_executor=self.stock_executor,
                    real_executor=self.real_executor,
                    config=at_cfg,
                )
                await self._autonomous_orchestrator.initialize()
                self._capital_flow_processor = CapitalFlowProcessor(
                    event_bus=self.event_bus,
                    api_keys=api_keys,
                    config=at_cfg.get("capital_flow") or {},
                )
                bots_cfg = at_cfg.get("botsofwallstreet") or {}
                if bots_cfg.get("enabled"):
                    try:
                        from components.botsofwallstreet import BotsofWallStreetAgent
                        self._botsofwallstreet = BotsofWallStreetAgent(config=bots_cfg)
                        if bots_cfg.get("auto_register"):
                            asyncio.ensure_future(self._botsofwallstreet.register())
                        self.logger.info("BotsofWallStreetAgent initialized (auto_post=%s)", bots_cfg.get("auto_post_ideas"))
                    except Exception as bots_err:
                        self.logger.debug("BotsofWallStreetAgent skipped: %s", bots_err)
                if self.event_bus:
                    self.event_bus.subscribe(METACOGNITION_UPDATE, self._on_metacognition_capital_flow)
                self._autonomous_task = asyncio.create_task(self._run_autonomous_cycles())
                self.logger.info("Autonomous trading stack enabled (config: autonomous_trading.enabled).")
            except Exception as e:
                self.logger.warning("Autonomous trading init skipped: %s", e)

        # Build and publish unified symbol index derived from API-keyed venues
        try:
            await self._publish_symbol_index()
        except Exception as e:
            self.logger.error(f"Failed to publish initial symbol index: {e}")

        # Publish an explicit API-usage audit snapshot for UI/AI visibility.
        try:
            self._publish_api_key_usage_audit()
        except Exception as e:
            self.logger.debug(f"Failed to publish API key usage audit: {e}")
        
        self.logger.info("Trading Component initialized")

    async def _run_autonomous_cycles(self) -> None:
        at_cfg = self.config.get("autonomous_trading") or {}
        interval = float(at_cfg.get("cycle_interval_seconds", 300))
        bots_cfg = at_cfg.get("botsofwallstreet") or {}
        auto_post = bots_cfg.get("auto_post_ideas", False)
        while True:
            try:
                if self._autonomous_orchestrator is not None:
                    result = await self._autonomous_orchestrator.run_trading_cycle()
                    if (
                        auto_post
                        and self._botsofwallstreet is not None
                        and isinstance(result, dict)
                        and result.get("status") == "completed"
                    ):
                        exec_data = result.get("execution") or {}
                        for trade in exec_data.get("trades") or []:
                            try:
                                await self._botsofwallstreet.post_idea(trade)
                            except Exception as bots_err:
                                self.logger.debug("BotsofWallStreet post_idea: %s", bots_err)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Autonomous cycle error: %s", e)
            await asyncio.sleep(interval)

    def _on_metacognition_capital_flow(self, data: Any) -> None:
        try:
            if not isinstance(data, tuple) or len(data) < 2:
                return
            kind, payload = data[0], data[1]
            if kind == "CAPITAL_FLOW" and self._autonomous_orchestrator is not None:
                asyncio.ensure_future(
                    self._autonomous_orchestrator.process_external_signal("capital_flow", payload)
                )
        except Exception as e:
            self.logger.debug("metacognition capital flow hook: %s", e)

    def _emit_pipeline_telemetry(self, stage: str, correlation_id: str, extra: Optional[Dict[str, Any]] = None) -> None:
        if not self.event_bus:
            return
        payload: Dict[str, Any] = {
            "stage": stage,
            "component": "TradingComponent",
            "correlation_id": correlation_id,
            "timestamp": time.time(),
        }
        if isinstance(extra, dict):
            payload.update(extra)
        try:
            self.event_bus.publish("ai.pipeline.telemetry", payload)
        except Exception as e:
            self.logger.debug(f"Telemetry publish failed (non-critical): {e}")

    def _lookup_market_data_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not symbol:
            return None
        target = str(symbol).upper().strip()
        target_base = target.split("/")[0]
        # Direct key lookup first
        direct = self.market_data.get(symbol) or self.market_data.get(target)
        if isinstance(direct, dict):
            return direct
        # Fallback search in cached payloads using exact base-symbol match.
        for key, payload in self.market_data.items():
            if not isinstance(payload, dict):
                continue
            p_symbol = str(payload.get("symbol") or payload.get("market") or key).upper().strip()
            p_base = p_symbol.split("/")[0]
            if target_base == p_base:
                return payload
        return None

    def _is_live_routing_allowed(self, symbol: str) -> bool:
        """Gate live execution by rollout stage without breaking internal book flow."""
        stage = self.rollout_stage
        symbol_u = str(symbol or "").upper()
        if stage in ("shadow", "paper"):
            return False
        if stage == "canary":
            return not self.canary_symbols or symbol_u in self.canary_symbols
        # full or unknown values default to enabled to preserve legacy behavior
        return True

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _infer_market_regime(self, market_ctx: Optional[Dict[str, Any]]) -> str:
        if not isinstance(market_ctx, dict):
            return "UNKNOWN"
        change_pct = self._as_float(market_ctx.get("change_percent_24h"), 0.0)
        abs_change = abs(change_pct)
        trend_thresh = float(self.regime_thresholds.get("trend_change_pct", 1.0))
        high_vol_thresh = float(self.regime_thresholds.get("high_vol_change_pct", 3.5))
        if abs_change >= high_vol_thresh:
            return "HIGH_VOLATILITY"
        if change_pct >= trend_thresh:
            return "TRENDING_UP"
        if change_pct <= -trend_thresh:
            return "TRENDING_DOWN"
        if abs_change <= 0.35:
            return "LOW_VOLATILITY"
        return "RANGE"

    def _market_circuit_breaker(self, market_ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        checks = {
            "market_ctx_present": isinstance(market_ctx, dict),
            "data_fresh": True,
            "spread_ok": True,
            "volatility_ok": True,
            "liquidity_ok": True,
        }
        if not isinstance(market_ctx, dict):
            return {"halt": False, "reason": "no_market_ctx", "checks": checks}

        if bool(self.market_circuit_config.get("halt_on_stale_data", True)):
            checks["data_fresh"] = not bool(market_ctx.get("is_stale", False))

        bid = self._as_float(market_ctx.get("bid"), 0.0)
        ask = self._as_float(market_ctx.get("ask"), 0.0)
        mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else 0.0
        spread_pct = ((ask - bid) / mid * 100.0) if mid > 0 and ask >= bid else 0.0
        checks["spread_ok"] = spread_pct <= float(self.market_circuit_config.get("max_spread_pct", 1.25))

        abs_change = abs(self._as_float(market_ctx.get("change_percent_24h"), 0.0))
        checks["volatility_ok"] = abs_change <= float(self.market_circuit_config.get("max_abs_change_pct", 12.0))

        vol24 = self._as_float(market_ctx.get("volume_24h"), 0.0)
        checks["liquidity_ok"] = vol24 >= float(self.market_circuit_config.get("min_volume_24h", 1.0))

        failed = [k for k, ok in checks.items() if not bool(ok)]
        return {
            "halt": len(failed) > 0,
            "reason": "market_circuit_breaker:" + ",".join(failed) if failed else "ok",
            "checks": checks,
            "spread_pct": spread_pct,
            "abs_change_pct_24h": abs_change,
        }

    def _resolve_strategy_profile(self, strategy_name: str, regime: str) -> Dict[str, Any]:
        key = str(strategy_name or "").strip().lower()
        if key.startswith("mean"):
            key = "mean_reversion"
        elif key.startswith("trend"):
            key = "trend"
        elif key.startswith("mom"):
            key = "momentum"
        profile = self.strategy_profiles.get(key) or self.strategy_profiles.get("default", {})
        allowed = profile.get("allowed_regimes", set())
        if regime == "HIGH_VOLATILITY" and key not in ("momentum", "default"):
            # During shock regimes, tighten risk by default for non-momentum styles.
            return {
                **profile,
                "allowed_regimes": allowed,
                "qty_mult": min(float(profile.get("qty_mult", 0.8)), 0.5),
                "min_conf": max(float(profile.get("min_conf", 0.56)), 0.62),
            }
        return profile

    async def _on_trading_system_readiness(self, payload: Dict[str, Any]) -> None:
        """Align live execution with global analysis-readiness state."""
        try:
            if isinstance(payload, dict):
                self._latest_trading_system_readiness = {
                    "state": str(payload.get("state", "UNKNOWN")).upper(),
                    "analysis_ready": bool(payload.get("analysis_ready", False)),
                    "auto_trade_started": bool(payload.get("auto_trade_started", False)),
                    "reason": payload.get("reason", ""),
                    "timestamp": payload.get("timestamp"),
                }
        except Exception as e:
            self.logger.debug(f"Error updating trading.system.readiness cache: {e}")
    
    async def _start(self) -> None:
        """Start the trading component."""
        self.logger.info("Starting Trading Component...")
        
        # Start trading engine if it has a start method
        if hasattr(self.trading_engine, 'start'):
            if asyncio.iscoroutinefunction(self.trading_engine.start):
                await self.trading_engine.start()
            else:
                self.trading_engine.start()
        
        # Start market data updates
        self._start_market_data_updates()

        # Default auto-trading to ON unless explicitly disabled.
        if self._auto_trading_active:
            await self.publish_event("trading.auto_trade.confirmed", {
                "status": "started",
                "timestamp": time.time(),
                "source": "startup_default",
            })
        
        self.logger.info("Trading Component started")
    
    async def _stop(self) -> None:
        """Stop the trading component."""
        self.logger.info("Stopping Trading Component...")
        if self._autonomous_task is not None:
            self._autonomous_task.cancel()
            try:
                await self._autonomous_task
            except asyncio.CancelledError:
                pass
            self._autonomous_task = None

        # Stop trading engine if it has a stop method
        if hasattr(self.trading_engine, 'stop'):
            if asyncio.iscoroutinefunction(self.trading_engine.stop):
                await self.trading_engine.stop()
            else:
                self.trading_engine.stop()
        
        # Save state
        await self._save_state()
        
        # Clean up Redis connection
        await self._cleanup_redis()
        
        self.logger.info("Trading Component stopped")

    async def _publish_symbol_index(self) -> None:
        """Build and publish a unified symbol index for all venues.

        This pulls crypto/FX symbols from RealExchangeExecutor and stock
        symbols from RealStockExecutor (when configured), tags each entry
        with asset_class and venues, and publishes a single
        'trading.symbol_index' event for the GUI and other components.
        """

        if not self.event_bus:
            return

        symbols: List[Dict[str, Any]] = []

        try:
            if self.real_executor is not None:
                crypto_index = await self.real_executor.build_symbol_index()
                if isinstance(crypto_index, list):
                    symbols.extend(crypto_index)
        except Exception as e:
            self.logger.error(f"Failed to build crypto/FX symbol index: {e}")

        try:
            if self.stock_executor is not None and hasattr(self.stock_executor, "build_symbol_index"):
                stock_index = await self.stock_executor.build_symbol_index()  # type: ignore[attr-defined]
                if isinstance(stock_index, list):
                    symbols.extend(stock_index)
        except Exception as e:
            self.logger.error(f"Failed to build stock symbol index: {e}")

        if not symbols:
            return

        payload = {"symbols": symbols}

        try:
            await self.publish_event("trading.symbol_index", payload)
        except Exception as e:
            self.logger.error(f"Failed to publish symbol index: {e}")
    
    async def _init_redis(self) -> bool:
        """Initialize Redis connection.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if self.redis_connected:
            return True
            
        try:
            # RedisQuantumNexusConnector is an alias for RedisConnector and
            # accepts only an optional event_bus argument.
            self.redis = RedisQuantumNexusConnector(self.event_bus)
            
            # Test connection
            if not self.redis.health_check():
                raise ConnectionError("Redis health check failed")
            
            self._redis_connected = True
            self.logger.info("Redis connection established successfully")
            return True
            
        except Exception as e:
            self._handle_error("Failed to connect to Redis", e)
            return False
    
    async def _load_state(self) -> None:
        """Load trading state from Redis."""
        if not self.redis_connected:
            self.logger.warning("Cannot load state: Redis not connected")
            return
        
        try:
            # Load positions
            positions_key = f"{self.name}:positions"
            positions_data = await asyncio.to_thread(self.redis.get, positions_key)
            if positions_data:
                self.positions = json.loads(positions_data)
                self.logger.info(f"Loaded {len(self.positions)} positions from Redis")
            
            # Load orders
            orders_key = f"{self.name}:orders"
            orders_data = await asyncio.to_thread(self.redis.get, orders_key)
            if orders_data:
                self.orders = json.loads(orders_data)
                self.logger.info(f"Loaded {len(self.orders)} orders from Redis")
                
        except Exception as e:
            self._handle_error("Failed to load state from Redis", e)
    
    async def _save_state(self) -> None:
        """Save trading state to Redis."""
        if not self.redis_connected:
            self.logger.warning("Cannot save state: Redis not connected")
            return
        
        try:
            # Save positions
            positions_key = f"{self.name}:positions"
            await asyncio.to_thread(self.redis.set, positions_key, json.dumps(self.positions))
            
            # Save orders
            orders_key = f"{self.name}:orders"
            await asyncio.to_thread(self.redis.set, orders_key, json.dumps(self.orders))
            self.logger.debug("Trading state saved to Redis")
            
        except Exception as e:
            self._handle_error("Failed to save state to Redis", e)
    
    def _start_market_data_updates(self) -> None:
        """Start the market data update loop using thread to avoid qasync conflicts."""
        import threading
        
        def _update_loop_sync():
            """Synchronous update loop running in background thread."""
            import time as time_module
            while getattr(self, '_running', False):
                try:
                    # Process market data in sync manner
                    self._process_market_data_sync()
                    time_module.sleep(1)  # 1 second interval
                except Exception as e:
                    self._handle_error("Error in market data update loop", e)
                    time_module.sleep(2)
        
        # Start in background thread instead of asyncio task
        self._update_thread = threading.Thread(target=_update_loop_sync, daemon=True)
        self._update_thread.start()
        self.logger.info("✅ Market data updates started (thread-based, qasync compatible)")
    
    def _process_market_data_sync(self) -> None:
        """Synchronous market data processing."""
        try:
            # Run the async market pipeline from the dedicated worker thread.
            asyncio.run(self._process_market_data())
        except RuntimeError:
            # Fallback for rare loop state issues in thread context.
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._process_market_data())
            finally:
                loop.close()
    
    async def _process_market_data(self) -> None:
        """Process market data updates and publish TradingTab topics."""
        if not self.real_executor or not self.event_bus:
            return

        now = time.time()
        interval = float(getattr(self, "market_data_interval_seconds", 0.0) or 0.0)
        if interval <= 0.0:
            interval = 1.0
        if now - getattr(self, "_last_market_data_ts", 0.0) < interval:
            return
        self._last_market_data_ts = now

        try:
            health = await self.real_executor.get_exchange_health()
        except Exception as e:
            self.logger.error("Failed to fetch exchange health for market data: %s", e)
            health = {}

        healthy_exchanges: List[str] = [
            name
            for name, info in health.items()
            if isinstance(info, dict) and info.get("status") in ("ok", "ok_empty")
        ]
        if not healthy_exchanges:
            healthy_exchanges = list(self.real_executor.get_connected_exchanges())

        if not healthy_exchanges:
            return

        if not self.canonical_markets and self.api_key_manager is not None:
            try:
                km_keys = self.api_key_manager.api_keys
                if km_keys:
                    self.canonical_markets = build_canonical_exchange_markets(km_keys)
            except Exception as e:
                self.logger.error("Failed to refresh canonical exchange markets: %s", e)

        prices: Dict[str, Dict[str, Any]] = {}

        for ex_name in healthy_exchanges:
            symbol_cfg = self.canonical_markets.get(ex_name) or {}
            symbol = symbol_cfg.get("symbol")
            if not symbol:
                continue

            ticker: Dict[str, Any] = {}
            try:
                ex = self.real_executor.exchanges.get(ex_name)
                if ex is not None:
                    ticker = await asyncio.to_thread(ex.fetch_ticker, symbol)
                else:
                    connector = self.real_executor.connectors.get(ex_name)
                    if connector is None or not hasattr(connector, "fetch_ticker"):
                        continue
                    fetch = getattr(connector, "fetch_ticker")
                    if asyncio.iscoroutinefunction(fetch):
                        ticker = await fetch(symbol)  # type: ignore[misc]
                    else:
                        ticker = await asyncio.to_thread(fetch, symbol)  # type: ignore[misc]
            except Exception as e:
                self.logger.warning(
                    "Market data fetch failed for %s %s: %s",
                    ex_name,
                    symbol,
                    e,
                )
                continue

            if not isinstance(ticker, dict):
                continue

            raw_price = (
                ticker.get("last")
                or ticker.get("close")
                or ticker.get("bid")
                or ticker.get("ask")
                or ticker.get("mid")
            )

            price: float = 0.0
            if isinstance(raw_price, (int, float, str)):
                try:
                    price = float(raw_price)
                except (TypeError, ValueError):
                    price = 0.0

            if price <= 0.0:
                continue

            ts_val = ticker.get("timestamp")
            ts_f: float
            if isinstance(ts_val, (int, float, str)):
                try:
                    ts_f = float(ts_val)
                    # Many exchange adapters return epoch in milliseconds.
                    if ts_f > 1e12:
                        ts_f /= 1000.0
                except (TypeError, ValueError):
                    ts_f = time.time()
            else:
                ts_f = time.time()
            if ts_f <= 0:
                ts_f = time.time()
            data_age_seconds = max(0.0, time.time() - ts_f)

            payload: Dict[str, Any] = {
                "timestamp": ts_f,
                "exchange": ex_name,
                "symbol": symbol,
                "price": price,
                "ticker": ticker,
                "data_age_seconds": data_age_seconds,
                "is_stale": data_age_seconds > float(self.risk_gate_config.get("max_market_data_age_seconds", 15.0)),
            }
            self.market_data[f"{ex_name}:{symbol}"] = payload

            try:
                await self.publish_event("market_data_update", payload)
                await self.publish_event("trading.market_data", payload)
                await self.publish_event("trading.market_data_update", payload)
            except Exception as e:
                self.logger.error(
                    "Failed to publish market data event for %s %s: %s",
                    ex_name,
                    symbol,
                    e,
                )

            base = symbol.split("/")[0] if isinstance(symbol, str) else ""
            if not base:
                continue

            existing = prices.get(base)
            if not existing or price > float(existing.get("price") or 0.0):
                prices[base] = {
                    "symbol": symbol,
                    "price": price,
                    "exchange": ex_name,
                }

        if not prices:
            return

        live_payload: Dict[str, Any] = {
            "timestamp": time.time(),
            "prices": prices,
        }

        try:
            await self.publish_event("trading.live_prices", live_payload)
        except Exception as e:
            self.logger.error("Failed to publish trading.live_prices: %s", e)

        # Keep portfolio/positions snapshots current for wallet and UI.
        await self._update_positions_and_orders()
    
    async def _update_positions_and_orders(self) -> None:
        """Update positions and orders based on current market state."""
        if not self.event_bus:
            return

        now = time.time()
        interval = float(
            getattr(self, "portfolio_update_interval_seconds", 0.0) or 0.0
        )
        if interval <= 0.0:
            interval = 5.0
        if now - getattr(self, "_last_portfolio_update_ts", 0.0) < interval:
            return
        self._last_portfolio_update_ts = now

        price_by_asset: Dict[str, float] = {}
        max_data_age = float(self.risk_gate_config.get("max_market_data_age_seconds", 15.0))
        for entry in self.market_data.values():
            if not isinstance(entry, dict):
                continue
            symbol = entry.get("symbol")
            raw_price = entry.get("price")
            ts_val = entry.get("timestamp")
            if not symbol:
                continue
            if not isinstance(raw_price, (int, float, str)):
                continue
            try:
                price = float(raw_price)
            except (TypeError, ValueError):
                continue
            if price <= 0.0:
                continue
            ts_f = 0.0
            if isinstance(ts_val, (int, float, str)):
                try:
                    ts_f = float(ts_val)
                    if ts_f > 1e12:
                        ts_f /= 1000.0
                except (TypeError, ValueError):
                    ts_f = 0.0
            data_age = (now - ts_f) if ts_f > 0 else float("inf")
            if data_age > max_data_age:
                continue
            base = symbol.split("/")[0] if isinstance(symbol, str) else ""
            if not base:
                continue
            prev = price_by_asset.get(base)
            if prev is None or price > prev:
                price_by_asset[base] = price

        positions: Dict[str, Dict[str, Any]] = {}
        total_value = 0.0

        if self.real_executor:
            try:
                health = await self.real_executor.get_exchange_health()
            except Exception as e:
                self.logger.error(
                    "Failed to fetch exchange health for portfolio: %s",
                    e,
                )
                health = {}

            healthy_exchanges = [
                name
                for name, info in health.items()
                if isinstance(info, dict)
                and info.get("status") in ("ok", "ok_empty")
            ]
            if not healthy_exchanges:
                healthy_exchanges = list(self.real_executor.get_connected_exchanges())

            for ex_name in healthy_exchanges:
                try:
                    balance = await self.real_executor.get_balance(ex_name)
                except Exception as e:
                    self.logger.error(
                        "Failed to fetch balance for %s: %s",
                        ex_name,
                        e,
                    )
                    continue

                if not isinstance(balance, dict):
                    continue

                for asset, amount in balance.items():
                    if not isinstance(amount, (int, float, str)):
                        continue
                    try:
                        qty = float(amount)
                    except (TypeError, ValueError):
                        continue
                    if qty <= 0.0:
                        continue

                    asset_code = str(asset).upper()
                    price = price_by_asset.get(asset_code, 0.0)
                    notional = qty * price if price > 0.0 else 0.0

                    key = f"{ex_name}:{asset_code}"
                    positions[key] = {
                        "exchange": ex_name,
                        "symbol": asset_code,
                        "asset": asset_code,
                        "quantity": qty,
                        "price": price if price > 0.0 else None,
                        "notional_value": notional,
                    }
                    total_value += max(notional, 0.0)

        alpaca_state: Optional[Dict[str, Any]] = None
        if self.stock_executor is not None:
            try:
                alpaca_state = await self.stock_executor.get_alpaca_positions()
            except Exception as e:
                self.logger.error("Failed to fetch Alpaca portfolio: %s", e)
                alpaca_state = None

        if isinstance(alpaca_state, dict) and alpaca_state.get("positions") is not None:
            for pos in alpaca_state.get("positions", []):
                if not isinstance(pos, dict):
                    continue
                symbol = str(pos.get("symbol") or "")
                if not symbol:
                    continue
                qty_val = pos.get("qty")
                if not isinstance(qty_val, (int, float, str)):
                    continue
                try:
                    qty = float(qty_val)
                except (TypeError, ValueError):
                    qty = 0.0
                if qty == 0.0:
                    continue

                mv_val = pos.get("market_value")
                if isinstance(mv_val, (int, float, str)):
                    try:
                        market_value = float(mv_val)
                    except (TypeError, ValueError):
                        market_value = 0.0
                else:
                    market_value = 0.0

                price = market_value / qty if qty and market_value else None

                key = f"alpaca:{symbol}"
                positions[key] = {
                    "exchange": "alpaca",
                    "symbol": symbol,
                    "asset": symbol,
                    "quantity": qty,
                    "price": price,
                    "notional_value": market_value,
                }
                total_value += max(market_value, 0.0)

            cash_val = alpaca_state.get("cash")
            cash: float
            if isinstance(cash_val, (int, float, str)):
                try:
                    cash = float(cash_val)
                except (TypeError, ValueError):
                    cash = 0.0
            else:
                cash = 0.0
            if cash:
                key = "alpaca:CASH:USD"
                positions[key] = {
                    "exchange": "alpaca",
                    "symbol": "USD",
                    "asset": "USD",
                    "quantity": cash,
                    "price": 1.0,
                    "notional_value": cash,
                }
                total_value += max(cash, 0.0)

        self.positions = positions

        payload: Dict[str, Any] = {
            "timestamp": time.time(),
            "total_value": total_value,
            "positions": positions,
        }

        try:
            await self.publish_event("portfolio_update", payload)
        except Exception as e:
            self.logger.error("Failed to publish portfolio_update: %s", e)

        # KAIG Integration: Track portfolio value changes → publish profit events
        # When portfolio value increases, the difference is realized profit
        prev_value = getattr(self, '_prev_portfolio_value', 0.0)
        if prev_value > 0 and total_value > prev_value:
            gain = total_value - prev_value
            # Only publish significant gains (> $1) to avoid noise
            if gain > 1.0 and self.event_bus:
                try:
                    self.event_bus.publish('trading.profit', {
                        'profit_usd': gain,
                        'profit': gain,
                        'total_value': total_value,
                        'previous_value': prev_value,
                        'source': 'portfolio_gain',
                    })
                    self.logger.info(
                        "KAIG: Portfolio gain $%.2f detected → buyback pipeline",
                        gain,
                    )
                except Exception:
                    pass
        self._prev_portfolio_value = total_value

    def _merge_executor_overrides(
        self,
        service: str,
        ex_name: str,
        data: Dict[str, Any],
        flat: Dict[str, Any],
    ) -> None:
        """Merge optional per-exchange connection overrides into flat map.

        This allows RealExchangeExecutor to pick up config-driven network
        settings such as HTTP(S) proxies and TLS verify/CA bundle options
        for each exchange without changing the core trading logic.
        """

        try:
            for key in ("http_proxy", "https_proxy", "verify", "ca_bundle"):
                if key not in data:
                    continue
                value = data.get(key)
                # Preserve False (e.g. verify=False) but skip pure empty strings
                if isinstance(value, str) and not value.strip():
                    continue
                flat[f"{ex_name}_{key}"] = value
        except Exception as e:
            self.logger.warning(
                "Failed to merge executor overrides for service %s (%s): %s",
                service,
                ex_name,
                e,
            )

    def _build_executor_keymap(self, km: APIKeyManager) -> Dict[str, str]:
        """Build exchange key map for RealExchangeExecutor from APIKeyManager.

        Primary path uses the canonical shared mapper from exchange_universe
        so init/reload behavior is identical across smoke tests and runtime.
        """
        api = km.api_keys
        try:
            mapped = build_real_exchange_api_keys(api)
            if isinstance(mapped, dict) and mapped:
                return mapped  # type: ignore[return-value]
        except Exception as e:
            self.logger.debug(f"Canonical API key mapping failed, using legacy mapper: {e}")

        # Legacy fallback mapping path (kept for backward compatibility).
        flat: Dict[str, Any] = {}
        mapped_services: set[str] = set()

        # Kraken
        if 'kraken' in api:
            data = api['kraken'] or {}
            flat['kraken'] = data.get('api_key')
            flat['kraken_secret'] = data.get('api_secret')
            self._merge_executor_overrides('kraken', 'kraken', data, flat)
            mapped_services.add('kraken')

        # Binance
        if 'binance' in api:
            data = api['binance'] or {}
            flat['binance'] = data.get('api_key')
            flat['binance_secret'] = data.get('api_secret')
            self._merge_executor_overrides('binance', 'binance', data, flat)
            mapped_services.add('binance')

        # Coinbase
        if 'coinbase' in api:
            data = api['coinbase'] or {}
            flat['coinbase'] = data.get('api_key')
            flat['coinbase_secret'] = data.get('api_secret')
            if 'coinbase_password' in data:
                flat['coinbase_password'] = data.get('coinbase_password')
            self._merge_executor_overrides('coinbase', 'coinbase', data, flat)
            mapped_services.add('coinbase')

        # Bitstamp
        if 'bitstamp' in api:
            data = api['bitstamp'] or {}
            flat['bitstamp'] = data.get('api_key')
            flat['bitstamp_secret'] = data.get('api_secret')
            self._merge_executor_overrides('bitstamp', 'bitstamp', data, flat)
            mapped_services.add('bitstamp')

        # HTX
        if 'htx' in api:
            data = api['htx'] or {}
            flat['htx'] = data.get('api_key')
            flat['htx_secret'] = data.get('api_secret')
            self._merge_executor_overrides('htx', 'htx', data, flat)
            mapped_services.add('htx')

        # BTCC
        if 'btcc' in api:
            data = api['btcc'] or {}
            flat['btcc'] = data.get('api_key')
            flat['btcc_secret'] = data.get('api_secret')
            self._merge_executor_overrides('btcc', 'btcc', data, flat)
            mapped_services.add('btcc')

        # Oanda
        if 'oanda' in api:
            data = api['oanda'] or {}
            flat['oanda'] = data.get('api_key') or data.get('access_token')
            self._merge_executor_overrides('oanda', 'oanda', data, flat)
            mapped_services.add('oanda')

        # Dynamically map all configured crypto exchanges using APIKeyManager categories
        try:
            crypto_names = set(km.CATEGORIES.get('crypto_exchanges', []))
        except Exception:
            crypto_names = set()

        # Skip known futures/derivatives entries that do not yet have dedicated
        # connectors in RealExchangeExecutor.
        skip_services = {
            'binance_futures',
            'kucoin_futures',
            'bybit_futures',
            'ftx_international',
            'dydx',
            'woo_x',
            'ascendex',
            'probit',
            'hotbit',
        }

        for service, data in api.items():
            if service in mapped_services:
                continue
            if service not in crypto_names:
                continue
            if service in skip_services:
                continue
            if not isinstance(data, dict):
                continue

            # Map service names to ccxt/connector ids where they differ
            if service == 'gate_io':
                ex_name = 'gateio'
            elif service == 'crypto_com':
                ex_name = 'cryptocom'
            else:
                ex_name = service

            api_key_val = (
                data.get('api_key')
                or data.get('key')
                or data.get('apiKey')
            )
            api_secret_val = (
                data.get('api_secret')
                or data.get('secret')
                or data.get('apiSecret')
            )

            if not api_key_val or not api_secret_val:
                continue
            if ex_name in flat or f"{ex_name}_secret" in flat:
                continue

            flat[ex_name] = api_key_val
            flat[f"{ex_name}_secret"] = api_secret_val

            # Merge any optional overrides present on this service entry
            self._merge_executor_overrides(service, ex_name, data, flat)

        # Preserve False bools but drop None/empty-string values
        cleaned: Dict[str, str] = {}
        for k, v in flat.items():
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            cleaned[k] = v  # type: ignore[assignment]

        return cleaned

    async def _reload_stock_executor(self, raw_keys: Dict[str, Any]) -> None:
        """Reload stock/FX broker executor from latest API keys."""
        try:
            if not isinstance(raw_keys, dict):
                return
            self.stock_executor = StockExecutor(raw_keys, event_bus=self.event_bus)
            self.broker_health = await self.stock_executor.get_broker_health()
            await self.stock_executor.publish_broker_health_snapshot()
        except Exception as e:
            self.logger.warning(f"Failed to reload RealStockExecutor after key update: {e}")

    def _publish_api_key_usage_audit(self) -> None:
        """Publish runtime API usage snapshot for all intelligence systems."""
        if not self.event_bus:
            return
        try:
            raw_keys = self.api_key_manager.api_keys if self.api_key_manager else {}
            configured_services = sorted(list(raw_keys.keys())) if isinstance(raw_keys, dict) else []
            exchange_services = sorted(list(self.real_executor.exchanges.keys())) if self.real_executor else []
            broker_services = sorted(list(self.broker_health.keys())) if isinstance(self.broker_health, dict) else []
            payload = {
                "timestamp": time.time(),
                "configured_service_count": len(configured_services),
                "configured_services": configured_services,
                "active_exchange_count": len(exchange_services),
                "active_exchanges": exchange_services,
                "active_broker_count": len(broker_services),
                "active_brokers": broker_services,
                "exchange_health": self.exchange_health,
                "broker_health": self.broker_health,
            }
            self.event_bus.publish("trading.api_key.usage.audit", payload)
        except Exception as e:
            self.logger.debug(f"API usage audit publish failed: {e}")

    async def _compute_expected_edges(self, symbol: str, side: OrderSide) -> Dict[str, float]:
        """Compute expected profit edge per exchange for a given symbol/side.

        This is a strategy hook. For now, it returns 0.0 for all
        exchanges that are currently healthy, so any venue with funds
        is considered acceptable. Replace this with real models.
        """
        edges: Dict[str, float] = {}
        if self.real_executor:
            health = self.exchange_health or await self.real_executor.get_exchange_health()
            for ex, info in health.items():
                if info.get("status") in ("ok", "ok_empty"):
                    edges[ex] = 0.0
        return edges
    
    async def place_order(self, symbol: str, order_type: Union[OrderType, str], 
                         side: Union[OrderSide, str], quantity: float, 
                         price: Optional[float] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Place a new order.
        
        Args:
            symbol: Trading symbol (e.g., "BTC/USD")
            order_type: Type of order (market, limit, etc.)
            side: Order side (buy/sell)
            quantity: Order quantity
            price: Order price (for limit orders)
            **kwargs: Additional order parameters
            
        Returns:
            Order information if successful, None otherwise
        """
        try:
            correlation_id = str(kwargs.pop("correlation_id", "") or f"order-{uuid.uuid4().hex}")
            decision_started = time.time()
            # Convert string order types/sides to enums if needed
            if isinstance(order_type, str):
                order_type = OrderType(order_type.lower())
            if isinstance(side, str):
                side = OrderSide(side.lower())
            pre_market = self._lookup_market_data_for_symbol(symbol) or {}
            pre_ref_price = self._as_float(
                pre_market.get("price")
                or pre_market.get("last")
                or pre_market.get("close")
            )
            
            # Place order through trading engine (internal book)
            order_id = await self.trading_engine.create_order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price,
                **kwargs
            )
            
            if not order_id:
                raise ValueError("Failed to place order")
            
            # Get order details
            order = await self.trading_engine.get_order(order_id)
            if not order:
                raise ValueError(f"Failed to retrieve order {order_id}")
            
            # Publish order update for internal engine
            await self.publish_event(
                self.EVENT_ORDER_UPDATE,
                {
                    'order_id': order_id,
                    'correlation_id': correlation_id,
                    'symbol': symbol,
                    'side': side.value,
                    'type': order_type.value,
                    'quantity': quantity,
                    'price': price,
                    'status': order.get('status'),
                    'timestamp': time.time()
                }
            )

            if self.event_bus:
                _safe_publish_trading_telemetry(
                    self.event_bus,
                    "strategy.order_placed",
                    {
                        "order_id": order_id,
                        "symbol": symbol,
                        "side": getattr(side, "value", str(side)),
                        "type": getattr(order_type, "value", str(order_type)),
                        "quantity": float(quantity),
                        "price": float(price) if price is not None else None,
                        "status": order.get("status"),
                        "correlation_id": correlation_id,
                    },
                )

            # Route to live exchanges if executor is available and rollout allows it
            if self.real_executor and self._is_live_routing_allowed(symbol):
                # Ensure we have up-to-date health
                self.exchange_health = await self.real_executor.get_exchange_health()

                # Compute expected edges per exchange (strategy hook)
                expected_edges = await self._compute_expected_edges(symbol, side)

                # Select profitable and healthy exchanges
                candidates = select_profitable_exchanges(
                    self.exchange_health,
                    expected_edges,
                    min_edge=0.0,
                )

                # Prefer venues where balances are present and adequate for this order side.
                quote_asset = "USD"
                base_asset = ""
                if "/" in symbol:
                    base_asset, quote_asset = symbol.split("/", 1)
                balance_asset = quote_asset if side == OrderSide.BUY else base_asset
                required_amount = float(quantity)
                if side == OrderSide.BUY and price is not None and float(price) > 0:
                    required_amount = float(quantity) * float(price)

                venues_with_funds = []
                for ex in candidates:
                    ex_info = self.exchange_health.get(ex, {})
                    if not ex_info.get("balances_sample"):
                        continue
                    has_funds = False
                    try:
                        bal = await self.real_executor.get_balance(ex)
                        if isinstance(bal, dict):
                            raw_amt = bal.get(balance_asset) or bal.get(balance_asset.upper()) or 0.0
                            avail = float(raw_amt)
                            has_funds = avail >= required_amount
                    except Exception:
                        has_funds = False
                    if has_funds:
                        venues_with_funds.append(ex)
                target_exchanges = venues_with_funds or candidates

                if target_exchanges:
                    best_venue = target_exchanges[0]

                    real_side = RealOrderSide.SELL if side == OrderSide.SELL else RealOrderSide.BUY
                    real_type = RealOrderType.MARKET if order_type == OrderType.MARKET else RealOrderType.LIMIT

                    try:
                        route_started = time.time()
                        await self.real_executor.place_real_order(
                            exchange_name=best_venue,
                            symbol=symbol,
                            order_type=real_type,
                            side=real_side,
                            amount=quantity,
                            price=price if real_type == RealOrderType.LIMIT else None,
                        )

                        if self.event_bus:
                            post_market = self._lookup_market_data_for_symbol(symbol) or {}
                            post_ref_price = self._as_float(
                                post_market.get("price")
                                or post_market.get("last")
                                or post_market.get("close")
                            )
                            slippage_bps = 0.0
                            if pre_ref_price > 0.0 and post_ref_price > 0.0:
                                slippage_bps = abs((post_ref_price - pre_ref_price) / pre_ref_price) * 10000.0
                            _safe_publish_trading_telemetry(
                                self.event_bus,
                                "strategy.order_routed",
                                {
                                    "order_id": order_id,
                                    "symbol": symbol,
                                    "side": getattr(side, "value", str(side)),
                                    "type": getattr(order_type, "value", str(order_type)),
                                    "quantity": float(quantity),
                                    "price": float(price) if price is not None else None,
                                    "venue": best_venue,
                                    "candidate_venues": list(target_exchanges),
                                    "expected_edge": float(expected_edges.get(best_venue, 0.0)),
                                    "pre_ref_price": pre_ref_price,
                                    "post_ref_price": post_ref_price,
                                    "slippage_bps": slippage_bps,
                                    "routing_latency_ms": int((time.time() - route_started) * 1000),
                                    "decision_latency_ms": int((time.time() - decision_started) * 1000),
                                    "correlation_id": correlation_id,
                                },
                            )
                            self.event_bus.publish("trading.execution.quality", {
                                "order_id": order_id,
                                "symbol": symbol,
                                "venue": best_venue,
                                "pre_ref_price": pre_ref_price,
                                "post_ref_price": post_ref_price,
                                "slippage_bps": slippage_bps,
                                "routing_latency_ms": int((time.time() - route_started) * 1000),
                                "decision_latency_ms": int((time.time() - decision_started) * 1000),
                                "timestamp": time.time(),
                                "correlation_id": correlation_id,
                            })
                        self._emit_pipeline_telemetry(
                            stage="live_order_routed",
                            correlation_id=correlation_id,
                            extra={"symbol": symbol, "venue": best_venue},
                        )
                    except Exception as live_err:
                        self._handle_error(
                            f"Failed to place live order on {best_venue}: {live_err}",
                            live_err,
                        )
            else:
                self._emit_pipeline_telemetry(
                    stage="live_order_skipped_by_rollout",
                    correlation_id=correlation_id,
                    extra={"symbol": symbol, "rollout_stage": self.rollout_stage},
                )
            
            return order
            
        except Exception as e:
            self._handle_error(f"Failed to place order: {str(e)}", e)
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order.
        
        Args:
            order_id: ID of the order to cancel
            
        Returns:
            bool: True if cancellation was successful, False otherwise
        """
        try:
            # Cancel order through trading engine
            success = await self.trading_engine.cancel_order(order_id)
            
            if success:
                # Publish order update
                order = await self.trading_engine.get_order(order_id)
                if order:
                    await self.publish_event(
                        self.EVENT_ORDER_UPDATE,
                        {
                            'order_id': order_id,
                            'status': 'cancelled',
                            'timestamp': time.time()
                        }
                    )

                if self.event_bus:
                    symbol = None
                    if isinstance(order, dict):
                        symbol = order.get('symbol')
                    _safe_publish_trading_telemetry(
                        self.event_bus,
                        "strategy.order_cancelled",
                        {
                            "order_id": order_id,
                            "symbol": symbol,
                            "status": "cancelled",
                        },
                    )
            
            return success
            
        except Exception as e:
            self._handle_error(f"Failed to cancel order {order_id}: {str(e)}", e)
            return False
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get current positions.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of position dictionaries
        """
        try:
            if hasattr(self.trading_engine, 'get_all_positions'):
                positions = self.trading_engine.get_all_positions()
                if symbol:
                    return [p for p in positions if p.get('symbol') == symbol]
                return positions
            return []
            
        except Exception as e:
            self._handle_error(f"Failed to get positions: {str(e)}", e)
            return []
    
    async def get_orders(self, symbol: Optional[str] = None, 
                        status: Optional[Union[OrderStatus, str]] = None) -> List[Dict[str, Any]]:
        """Get current orders.
        
        Args:
            symbol: Optional symbol filter
            status: Optional status filter
            
        Returns:
            List of order dictionaries
        """
        try:
            if hasattr(self.trading_engine, 'get_all_orders'):
                orders = await self.trading_engine.get_all_orders()
                if symbol or status:
                    filtered = []
                    for order in orders:
                        if symbol and order.get('symbol') != symbol:
                            continue
                        if status and order.get('status') != status:
                            continue
                        filtered.append(order)
                    return filtered
                return orders
            return []
            
        except Exception as e:
            self._handle_error(f"Failed to get orders: {str(e)}", e)
            return []
    
    async def _on_trading_signal(self, signal_data: Dict[str, Any]) -> None:
        """Handle trading signals."""
        try:
            self.logger.info(f"Received trading signal: {signal_data}")
            correlation_id = str(signal_data.get("correlation_id") or signal_data.get("request_id") or f"trade-{uuid.uuid4().hex}")
            
            # Extract signal parameters
            symbol = signal_data.get('symbol')
            signal_type = signal_data.get('signal_type', '').lower()
            quantity = float(signal_data.get('quantity', 0.0))
            price = float(signal_data.get('price', 0.0)) if 'price' in signal_data else None
            confidence = self._as_float(signal_data.get("confidence"), 0.0)
            strategy_name = str(
                signal_data.get("strategy")
                or signal_data.get("strategy_type")
                or signal_data.get("source")
                or "default"
            )
            
            if not symbol or not signal_type or quantity <= 0:
                self.logger.warning(f"Invalid trading signal: {signal_data}")
                return
            
            # Map signal type to order side
            side = None
            if signal_type in ['buy', 'long']:
                side = OrderSide.BUY
            elif signal_type in ['sell', 'short']:
                side = OrderSide.SELL
            else:
                self.logger.warning(f"Unsupported signal type: {signal_type}")
                return

            # Always-active adaptive protection:
            # keep the trading brain online while dynamically tightening posture.
            market_ctx = self._lookup_market_data_for_symbol(str(symbol))
            regime = self._infer_market_regime(market_ctx)
            profile = self._resolve_strategy_profile(strategy_name, regime)
            qty_mult = 1.0
            min_conf = max(
                self._as_float(self.risk_gate_config.get("min_signal_confidence"), 0.55),
                self._as_float(profile.get("min_conf"), 0.56),
            )

            if self._active_strategies:
                active_lower = {s.lower() for s in self._active_strategies}
                if strategy_name.lower() not in active_lower:
                    # Re-map to active strategy instead of stalling the trade engine.
                    strategy_name = sorted(list(self._active_strategies))[0]
                    profile = self._resolve_strategy_profile(strategy_name, regime)
                    min_conf = max(
                        self._as_float(self.risk_gate_config.get("min_signal_confidence"), 0.55),
                        self._as_float(profile.get("min_conf"), 0.56),
                    )

            readiness_state = str(self._latest_trading_system_readiness.get("state", "UNKNOWN")).upper()
            if readiness_state not in ("READY", "UNKNOWN"):
                qty_mult *= 0.40

            allowed_regimes = set(profile.get("allowed_regimes", set()))
            if allowed_regimes and regime not in allowed_regimes:
                qty_mult *= 0.50
                min_conf = max(min_conf, 0.64)

            breaker = self._market_circuit_breaker(market_ctx)
            if breaker.get("halt", False):
                qty_mult *= 0.30
                min_conf = max(min_conf, 0.68)

            if confidence > 0.0 and confidence < min_conf:
                await self.publish_event("trading.signal.abstained", {
                    "correlation_id": correlation_id,
                    "symbol": symbol,
                    "signal_type": signal_type,
                    "strategy": strategy_name,
                    "regime": regime,
                    "reason": f"opportunity_filter:confidence<{min_conf:.2f}",
                    "confidence": confidence,
                    "timestamp": time.time(),
                })
                return

            adjusted_qty = max(quantity * max(qty_mult, 0.05), 0.0)
            if adjusted_qty <= 0.0:
                return
            if adjusted_qty != quantity:
                await self.publish_event("trading.signal.adjusted", {
                    "correlation_id": correlation_id,
                    "symbol": symbol,
                    "signal_type": signal_type,
                    "strategy": strategy_name,
                    "regime": regime,
                    "original_quantity": quantity,
                    "adjusted_quantity": adjusted_qty,
                    "multiplier": qty_mult,
                    "readiness_state": readiness_state,
                    "circuit_reason": breaker.get("reason"),
                    "timestamp": time.time(),
                })
            quantity = adjusted_qty
            signal_data = dict(signal_data)
            signal_data["quantity"] = quantity
            signal_data["strategy"] = strategy_name
            signal_data["regime"] = regime

            # Deterministic gate before any order placement
            if self.enable_deterministic_risk_gate and self.risk_manager is not None:
                gate = await self.risk_manager.evaluate_signal_gate(
                    signal_data=signal_data,
                    market_data=market_ctx,
                    config=self.risk_gate_config,
                )
                self._emit_pipeline_telemetry(
                    stage="pre_trade_risk_gate",
                    correlation_id=correlation_id,
                    extra={
                        "approved": gate.get("approved", False),
                        "reason": gate.get("reason"),
                        "symbol": symbol,
                        "signal_type": signal_type,
                    },
                )
                await self.publish_event("trading.risk_gate.result", {
                    "correlation_id": correlation_id,
                    "symbol": symbol,
                    "signal_type": signal_type,
                    "result": gate,
                    "timestamp": time.time(),
                })
                if not gate.get("approved", False):
                    self.logger.warning(f"Risk gate rejected signal for {symbol}: {gate.get('reason')}")
                    await self.publish_event("trading.signal.abstained", {
                        "correlation_id": correlation_id,
                        "symbol": symbol,
                        "signal_type": signal_type,
                        "reason": gate.get("reason"),
                        "checks": gate.get("checks", {}),
                        "timestamp": time.time(),
                    })
                    return
            
            # Place market order by default
            order_type = OrderType.MARKET
            
            # Place the order
            await self.place_order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price,
                correlation_id=correlation_id,
            )
            
        except Exception as e:
            self._handle_error("Error processing trading signal", e)

    async def _on_thoth_trading_decision(self, event_data: Dict[str, Any]) -> None:
        """Bridge Thoth verifier-loop decisions into trading.signal contract."""
        try:
            decision = event_data.get("decision") if isinstance(event_data, dict) else None
            if not isinstance(decision, dict):
                return
            action = str(decision.get("action", "")).lower()
            if action not in ("buy", "sell", "hold", "exit"):
                return
            # Only actionable orders become trading signals.
            if action in ("hold", "exit"):
                await self.publish_event("trading.signal.abstained", {
                    "correlation_id": decision.get("correlation_id"),
                    "reason": decision.get("abstain_reason") or action,
                    "decision": decision,
                    "timestamp": time.time(),
                })
                return
            signal_payload = {
                "symbol": decision.get("symbol"),
                "signal_type": action,
                "quantity": decision.get("quantity", decision.get("amount", 0.0)),
                "price": decision.get("entry_price"),
                "confidence": decision.get("confidence", 0.0),
                "stop_loss": decision.get("stop_loss"),
                "take_profit": decision.get("take_profit"),
                "correlation_id": decision.get("correlation_id"),
                "source": "thoth_verifier_loop",
            }
            await self._on_trading_signal(signal_payload)
        except Exception as e:
            self._handle_error("Error bridging thoth trading decision", e)

    async def _on_stock_order_submit(self, order_data: Dict[str, Any]) -> None:
        """Handle stock order submissions from the GUI.

        This routes basic stock orders to Alpaca via RealStockExecutor when
        configured. It does not touch the internal crypto trading engine.
        """

        try:
            if not self.stock_executor:
                self.logger.warning("Stock executor not initialized; cannot route stock order")
                return

            symbol = str(order_data.get("symbol") or "").strip()
            side = str(order_data.get("side") or "").lower()
            order_type = str(order_data.get("type") or "").lower()

            try:
                quantity = float(order_data.get("quantity", 0.0))
            except (TypeError, ValueError):
                quantity = 0.0

            price_val = order_data.get("price")
            price: Optional[float]
            try:
                price = float(price_val) if price_val is not None else None
            except (TypeError, ValueError):
                price = None

            if not symbol or quantity <= 0:
                self.logger.warning("Invalid stock order payload (symbol/quantity): %s", order_data)
                return
            if side not in ("buy", "sell"):
                self.logger.warning("Invalid stock order side: %s", side)
                return
            if order_type not in ("market", "limit"):
                self.logger.warning("Invalid stock order type: %s", order_type)
                return

            alpaca_order = await self.stock_executor.place_alpaca_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price if order_type == "limit" else None,
            )

            order_id = alpaca_order.get("id") or f"alpaca-{symbol}-{time.time()}"

            await self.publish_event(
                self.EVENT_ORDER_UPDATE,
                {
                    "id": order_id,
                    "order_id": order_id,
                    "symbol": alpaca_order.get("symbol", symbol),
                    "side": alpaca_order.get("side", side),
                    "type": alpaca_order.get("type", order_type),
                    "quantity": alpaca_order.get("qty", quantity),
                    "price": alpaca_order.get("limit_price") or price,
                    "status": alpaca_order.get("status"),
                    "timestamp": time.time(),
                    "source": "stock_alpaca",
                },
            )

        except Exception as e:
            self._handle_error("Error handling stock order submit", e)

    async def _on_fx_order_submit(self, order_data: Dict[str, Any]) -> None:
        """Route FX order submissions to Oanda via RealExchangeExecutor.

        The GUI emits ``fx.order_submit`` with ``{symbol, side, type,
        quantity, price?}``; this handler dispatches to Oanda and
        republishes a normalized order-update event.
        """
        try:
            executor = getattr(self, "real_executor", None)
            if executor is None:
                self.logger.warning("Real executor not initialized; cannot route FX order")
                return

            symbol = str(order_data.get("symbol") or "").strip()
            side = str(order_data.get("side") or "").lower()
            order_type = str(order_data.get("type") or "").lower() or "market"

            try:
                quantity = float(order_data.get("quantity", 0.0))
            except (TypeError, ValueError):
                quantity = 0.0

            price_val = order_data.get("price")
            try:
                price = float(price_val) if price_val is not None else None
            except (TypeError, ValueError):
                price = None

            if not symbol or quantity <= 0:
                self.logger.warning("Invalid FX order payload: %s", order_data)
                return
            if side not in ("buy", "sell"):
                self.logger.warning("Invalid FX order side: %s", side)
                return
            if order_type not in ("market", "limit"):
                self.logger.warning("Invalid FX order type: %s", order_type)
                return

            connector = getattr(executor, "connectors", {}).get("oanda")
            if connector is None:
                self.logger.warning("Oanda connector not available for FX order")
                return

            if order_type == "limit" and price is not None:
                result = await connector.create_limit_order(symbol, side, quantity, price)
            else:
                result = await connector.create_market_order(symbol, side, quantity)

            order_id = (
                result.get("id") if isinstance(result, dict) else None
            ) or f"oanda-{symbol}-{time.time()}"

            await self.publish_event(
                self.EVENT_ORDER_UPDATE,
                {
                    "id": order_id,
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": side,
                    "type": order_type,
                    "quantity": quantity,
                    "price": price,
                    "status": result.get("status") if isinstance(result, dict) else None,
                    "timestamp": time.time(),
                    "source": "fx_oanda",
                    "raw": result,
                },
            )
        except Exception as e:
            self._handle_error("Error handling FX order submit", e)

    def _on_market_data(self, market_data: Dict[str, Any]) -> None:
        """Handle market data updates (sync handler to avoid task nesting issues)."""
        try:
            if not isinstance(market_data, dict):
                return

            nested = market_data.get("data") if isinstance(market_data.get("data"), dict) else {}
            symbol = (
                market_data.get("symbol")
                or market_data.get("market")
                or nested.get("symbol")
                or nested.get("market")
            )
            if not symbol:
                return

            payload = dict(market_data)
            if nested:
                if "price" not in payload and "price" in nested:
                    payload["price"] = nested.get("price")
                if "timestamp" not in payload and "timestamp" in nested:
                    payload["timestamp"] = nested.get("timestamp")
                if "exchange" not in payload and "exchange" in nested:
                    payload["exchange"] = nested.get("exchange")
            payload["symbol"] = symbol

            # Update market data cache with both canonical and venue key.
            self.market_data[str(symbol)] = payload
            ex_name = payload.get("exchange")
            if ex_name:
                self.market_data[f"{ex_name}:{symbol}"] = payload

        except Exception as e:
            self._handle_error("Error processing market data", e)
    
    async def _register_event_handlers(self) -> None:
        """Register event handlers."""
        # BaseComponentV2._init_event_handlers already registers core
        # system handlers and calls this hook, so we only need to
        # register TradingComponent-specific handlers here.

        # Register for trading signals
        await self.subscribe(self.EVENT_TRADING_SIGNAL, self._on_trading_signal)
        await self.subscribe("thoth.trading.decision", self._on_thoth_trading_decision)

        # Register for market data
        await self.subscribe(self.EVENT_MARKET_DATA, self._on_market_data)
        await self.subscribe("trading.market_data_update", self._on_market_data)
        await self.subscribe("market.data.update", self._on_market_data)
        await self.subscribe("trading.system.readiness", self._on_trading_system_readiness)

        # Register for stock order submissions from GUI
        await self.subscribe("stock.order_submit", self._on_stock_order_submit)

        # Register for FX order submissions from GUI (OANDA)
        await self.subscribe("fx.order_submit", self._on_fx_order_submit)

        # Natural-language transfer requests from voice/chat/GUI
        try:
            await self.subscribe("user.nl.transfer", self._on_nl_transfer_request)
            await self.subscribe("user.voice.transfer_request", self._on_nl_transfer_request)
            await self.subscribe("transfer.nl.request", self._on_nl_transfer_request)
        except Exception as e:
            self.logger.warning(f"Failed to subscribe to NL transfer events: {e}")

        # Register for system events
        await self.subscribe(f"{self.EVENT_SYSTEM}.shutdown", self._on_shutdown)

        # React to API key updates so RealExchangeExecutor picks up changes at runtime
        try:
            await self.subscribe("api.keys.all.loaded", self._on_api_keys_reloaded)
            await self.subscribe("api.key.added", self._on_api_keys_reloaded)
            await self.subscribe("api.key.updated", self._on_api_keys_reloaded)
            await self.subscribe("api.key.removed", self._on_api_keys_reloaded)
            await self.subscribe("api.keys.reloaded", self._on_api_keys_reloaded)
        except Exception as e:
            self.logger.warning(f"Failed to subscribe to API key update events: {e}")

        # SOTA 2026 FIX: Subscribe to all frontend trading events for full integration
        try:
            # Auto-trading events
            await self.subscribe("trading.auto_trade.started", self._on_auto_trade_started)
            await self.subscribe("trading.auto_trade.stopped", self._on_auto_trade_stopped)
            
            # Strategy events
            await self.subscribe("trading.strategy.started", self._on_strategy_started)
            await self.subscribe("trading.strategy.stopped", self._on_strategy_stopped)
            
            # Hedge requests
            await self.subscribe("trading.hedge.request", self._on_hedge_request)
            
            # Exchange configuration
            await self.subscribe("trading.exchanges.set_allowed", self._on_exchanges_set)
            
            # Arbitrage and advanced trading events
            await self.subscribe("trading.arbitrage.executed", self._on_arbitrage_executed)
            await self.subscribe("trading.grid.started", self._on_grid_started)
            await self.subscribe("trading.meanreversion.executed", self._on_meanreversion_executed)
            await self.subscribe("trading.momentum.executed", self._on_momentum_executed)
            await self.subscribe("trading.trend.executed", self._on_trend_executed)
            
            # ML/AI trading events
            await self.subscribe("trading.ml.features_extracted", self._on_ml_features_extracted)
            await self.subscribe("trading.ml.model_trained", self._on_ml_model_trained)
            await self.subscribe("trading.canary.readiness_drill", self._on_canary_readiness_drill)
            await self.subscribe("system.trading.canary.readiness_drill", self._on_canary_readiness_drill)
            
            self.logger.info("✅ Registered all frontend trading event handlers")
        except Exception as e:
            self.logger.warning(f"Failed to subscribe to some trading events: {e}")

    async def run_canary_readiness_drill(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a strict canary readiness drill (dry-run default).

        SOTA 2026 canary policy:
        - Never place blind live orders by default
        - Validate venue health, balances, data freshness, and latency first
        - Emit a detailed trace with weighted score (0-110)
        """
        data = payload or {}
        started = time.time()
        test_symbol = str(data.get("symbol") or "BTC/USD")
        dry_run = bool(data.get("dry_run", True))
        min_balance_quote = float(data.get("min_balance_quote", 25.0) or 25.0)
        max_allowed_staleness = float(data.get("max_market_staleness_sec", 15.0) or 15.0)

        trace: Dict[str, Any] = {
            "request_id": str(data.get("request_id") or f"canary_{int(started * 1000)}"),
            "timestamp": started,
            "symbol": test_symbol,
            "dry_run": dry_run,
            "checks": {},
            "gaps": [],
            "action_plan": [],
            "score_110": 0,
            "status": "BLOCKED",
        }

        # 1) Basic runtime prerequisites
        redis_ok = bool(self.redis_connected)
        executor_ok = self.real_executor is not None
        trace["checks"]["runtime"] = {
            "redis_connected": redis_ok,
            "real_executor_present": executor_ok,
        }
        if not redis_ok:
            trace["gaps"].append("Redis Quantum Nexus not connected")
            trace["action_plan"].append("Restore Redis connection before canary execution")
        if not executor_ok:
            trace["gaps"].append("Real exchange executor not available")
            trace["action_plan"].append("Load API keys and initialize exchange executors")

        health_latency_ms = None
        health: Dict[str, Any] = {}
        if self.real_executor:
            # Prefer cached health when fresh to avoid unnecessary latency spikes.
            now_ts = time.time()
            cached_fresh = bool(self.exchange_health) and (now_ts - float(self._last_health_snapshot_ts or 0.0)) < 45.0
            if cached_fresh:
                health = dict(self.exchange_health)
                health_latency_ms = 0
            else:
                t0 = time.time()
                try:
                    health = await self.real_executor.get_exchange_health()
                    self._last_health_snapshot_ts = time.time()
                except Exception as e:
                    self._handle_error("Canary drill health fetch failed", e)
                    health = {}
                health_latency_ms = int((time.time() - t0) * 1000)
        self.exchange_health = health or self.exchange_health

        healthy_exchanges: List[str] = []
        unhealthy_exchanges: List[str] = []
        for ex, info in (health or {}).items():
            if isinstance(info, dict) and info.get("status") in ("ok", "ok_empty"):
                healthy_exchanges.append(ex)
            else:
                unhealthy_exchanges.append(ex)

        trace["checks"]["exchange_health"] = {
            "latency_ms": health_latency_ms,
            "healthy_count": len(healthy_exchanges),
            "total_count": len(health or {}),
            "healthy_exchanges": healthy_exchanges,
            "unhealthy_exchanges": unhealthy_exchanges[:20],
        }
        if len(healthy_exchanges) == 0:
            trace["gaps"].append("No healthy exchange venues available")
            trace["action_plan"].append("Repair API credentials/network for at least one venue")

        # 2) Market data freshness
        md = self._lookup_market_data_for_symbol(test_symbol) or {}
        # On-demand hydration: fetch a single live ticker if cache is empty.
        if not md and self.real_executor and healthy_exchanges:
            ticker_symbol_candidates = [test_symbol]
            base = test_symbol.split("/")[0].upper()
            if "/" in test_symbol:
                q = test_symbol.split("/", 1)[1].upper()
                ticker_symbol_candidates.extend([
                    f"{base}/{q}",
                    f"{base}/USDT",
                    f"{base}/USD",
                ])
            for ex in healthy_exchanges[:3]:
                conn = self.real_executor.connectors.get(ex) if hasattr(self.real_executor, "connectors") else None
                if conn is None or not hasattr(conn, "fetch_ticker"):
                    continue
                hydrated = None
                for sym in ticker_symbol_candidates:
                    try:
                        ticker = await conn.fetch_ticker(sym)  # type: ignore[attr-defined]
                        if isinstance(ticker, dict):
                            price = self._as_float(
                                ticker.get("last") or ticker.get("close") or ticker.get("ask") or ticker.get("bid")
                            )
                            if price > 0.0:
                                hydrated = {
                                    "exchange": ex,
                                    "symbol": sym,
                                    "market": sym,
                                    "price": price,
                                    "bid": self._as_float(ticker.get("bid")),
                                    "ask": self._as_float(ticker.get("ask")),
                                    "volume_24h": self._as_float(ticker.get("baseVolume")),
                                    "change_percent_24h": self._as_float(ticker.get("percentage")),
                                    "timestamp": time.time(),
                                }
                                break
                    except Exception:
                        continue
                if hydrated:
                    self.market_data[str(hydrated.get("symbol", test_symbol))] = hydrated
                    self.market_data[f"{ex}:{hydrated.get('symbol', test_symbol)}"] = hydrated
                    self._last_market_data_ts = time.time()
                    md = hydrated
                    break
        last_mkt_ts = float(self._last_market_data_ts or 0.0)
        staleness = (time.time() - last_mkt_ts) if last_mkt_ts > 0 else None
        trace["checks"]["market_data"] = {
            "symbol_found": bool(md),
            "last_market_data_ts": last_mkt_ts,
            "staleness_sec": staleness,
        }
        if not md:
            trace["gaps"].append(f"No cached market data for {test_symbol}")
            trace["action_plan"].append("Wait for market stream to populate symbol cache before canary")
        elif staleness is not None and staleness > max_allowed_staleness:
            trace["gaps"].append(f"Market data stale for {test_symbol}: {staleness:.2f}s")
            trace["action_plan"].append("Reduce feed latency or confirm websocket/polling health")

        # 3) Funding check on best candidate venues
        funded_venues: List[str] = []
        micro_funded_venues: List[str] = []
        target_asset = "USD"
        if "/" in test_symbol:
            _, q = test_symbol.split("/", 1)
            target_asset = q
        if self.real_executor:
            for ex in healthy_exchanges:
                try:
                    bal = await self.real_executor.get_balance(ex)
                    if isinstance(bal, dict):
                        amt = float(bal.get(target_asset) or bal.get(target_asset.upper()) or 0.0)
                        if amt >= min_balance_quote:
                            funded_venues.append(ex)
                        # Goal-aware fallback: start from any available dollar amount.
                        # If any positive free balance exists, mark as micro-funded for canary.
                        any_positive = False
                        for _k, _v in bal.items():
                            try:
                                if float(_v or 0.0) > 0.0:
                                    any_positive = True
                                    break
                            except Exception:
                                continue
                        if any_positive:
                            micro_funded_venues.append(ex)
                except Exception:
                    continue
        trace["checks"]["funding"] = {
            "target_asset": target_asset,
            "min_balance_required": min_balance_quote,
            "funded_venues": funded_venues,
            "micro_funded_venues": micro_funded_venues,
        }
        if len(funded_venues) == 0 and not (dry_run and len(micro_funded_venues) > 0):
            trace["gaps"].append(f"No venue has >= {min_balance_quote} {target_asset} for canary")
            trace["action_plan"].append("Fund at least one healthy venue for controlled canary routing")

        # 4) Route simulation (no live execution unless explicitly requested)
        expected_edges = await self._compute_expected_edges(test_symbol, OrderSide.BUY)
        candidates = select_profitable_exchanges(health or {}, expected_edges, min_edge=0.0)
        effective_funded = funded_venues or (micro_funded_venues if dry_run else [])
        chosen = (effective_funded[0] if effective_funded else (candidates[0] if candidates else None))
        trace["checks"]["routing_simulation"] = {
            "candidate_venues": candidates,
            "chosen_venue": chosen,
            "expected_edge": float(expected_edges.get(chosen, 0.0)) if chosen else None,
            "live_execution_attempted": False,
        }

        # 5) 110-scale score
        score = 110
        score -= 20 if not redis_ok else 0
        score -= 20 if not executor_ok else 0
        score -= 25 if len(healthy_exchanges) == 0 else 0
        score -= 20 if len(funded_venues) == 0 and not (dry_run and len(micro_funded_venues) > 0) else 0
        if staleness is not None and staleness > max_allowed_staleness:
            score -= 10
        if not md:
            score -= 10
        # Do not downgrade readiness on a single cold-start health probe if venues are healthy.
        if health_latency_ms is not None and health_latency_ms > 1500 and len(healthy_exchanges) == 0:
            score -= 5
        score = max(0, min(110, score))
        trace["score_110"] = score
        trace["status"] = "READY" if score >= 110 else ("PARTIAL" if score >= 70 else "BLOCKED")
        trace["duration_ms"] = int((time.time() - started) * 1000)
        self._last_canary_result = dict(trace)
        return trace

    async def _on_canary_readiness_drill(self, event_data: Dict[str, Any]) -> None:
        """Handle on-demand canary drill events."""
        try:
            result = await self.run_canary_readiness_drill(event_data or {})
            await self.publish_event("trading.canary.readiness.result", result)
            if self.event_bus:
                self.event_bus.publish("system.trading.canary.readiness.result", result)
        except Exception as e:
            self._handle_error("Canary readiness drill failed", e)

    async def _on_nl_transfer_request(self, event_data: Dict[str, Any]) -> None:
        """Natural-language transfer/movement request handler.

        Accepts any of these payloads:

          * ``{"text": "move $500 from kraken to polymarket"}``
          * ``{"command": "..."}``
          * ``{"utterance": "..."}`` (voice path)
          * full intent: ``{"intent": {...}}``

        Optional flags::

          * ``dry_run`` (default True)
          * ``confirmed`` (default False - first call returns a plan,
            second call with ``confirmed=True`` executes it)
          * ``reply_topic`` - custom topic to publish the result to
            instead of the default ``transfer.nl.plan`` /
            ``transfer.nl.executed``.
        """
        try:
            text = (
                (event_data or {}).get("text")
                or (event_data or {}).get("command")
                or (event_data or {}).get("utterance")
                or ""
            )
            intent_payload = (event_data or {}).get("intent")
            dry_run = bool((event_data or {}).get("dry_run", True))
            confirmed = bool((event_data or {}).get("confirmed", False))
            reply_topic = (event_data or {}).get("reply_topic")

            if not text and not intent_payload:
                return

            from core.natural_language_transfer_router import (
                NaturalLanguageTransferRouter,
                IntentParseResult,
            )

            # Resolve cross-venue manager from the registry if available.
            cvm = None
            try:
                from core.component_registry import get_component
                cvm = get_component("cross_venue_transfer_manager")
            except Exception:
                cvm = None

            router = NaturalLanguageTransferRouter(
                cross_venue_manager=cvm,
                real_stock_executor=getattr(self, "real_stock_executor", None),
                event_bus=self.event_bus,
            )

            if intent_payload is not None:
                intent = IntentParseResult(
                    raw_text=intent_payload.get("raw_text", ""),
                    action=intent_payload.get("action", "move"),
                    amount=intent_payload.get("amount"),
                    amount_kind=intent_payload.get("amount_kind"),
                    asset=intent_payload.get("asset"),
                    from_venue=intent_payload.get("from_venue"),
                    to_venue=intent_payload.get("to_venue"),
                    confidence=float(intent_payload.get("confidence", 0.9)),
                )
                plan = router.build_plan(intent)
            else:
                plan = router.build_plan(text)

            if not confirmed:
                self.logger.info(
                    "📩 NL transfer plan built (id=%s, status=%s): %s",
                    plan.plan_id, plan.status.value, plan.intent.raw_text,
                )
                payload = {"plan": plan.to_dict(),
                           "needs_confirmation": True,
                           "message": plan.narrative}
                topic = reply_topic or "transfer.nl.plan"
                await self.publish_event(topic, payload)
                return

            result = await router.execute(plan, dry_run=dry_run, confirmed=True)
            self.logger.info(
                "💸 NL transfer executed (id=%s, dry_run=%s): %s legs",
                plan.plan_id, dry_run, len(plan.legs),
            )
            topic = reply_topic or "transfer.nl.executed"
            await self.publish_event(topic, result)
        except Exception as e:
            self._handle_error("Error handling natural-language transfer request", e)

    async def _on_api_keys_reloaded(self, event_data: Dict[str, Any]) -> None:
        """Handle API key updates and reload RealExchangeExecutor.

        This is called when the APIKeyManager broadcasts that keys have been
        reloaded or a specific key has been added/updated. It rebuilds the
        flat key map and calls reload_api_keys() so live trading reflects
        runtime GUI edits without restart.
        """
        try:
            if not self.api_key_manager:
                return

            # Ensure the manager has the latest view of keys
            try:
                if hasattr(self.api_key_manager, "reload_from_disk"):
                    self.api_key_manager.reload_from_disk()
            except Exception:
                # Best-effort; event may already reflect in-memory state
                pass

            raw_keys = self.api_key_manager.api_keys if isinstance(self.api_key_manager.api_keys, dict) else {}
            flat_keys = self._build_executor_keymap(self.api_key_manager)

            # Rebuild canonical markets from latest key set.
            try:
                self.canonical_markets = build_canonical_exchange_markets(raw_keys)
            except Exception as cm_err:
                self.logger.warning(f"Failed to rebuild canonical exchange markets: {cm_err}")

            if not self.real_executor and flat_keys:
                self.real_executor = RealExchangeExecutor(flat_keys, event_bus=self.event_bus)
            elif self.real_executor and flat_keys:
                self.logger.info("Reloading RealExchangeExecutor API keys after update event...")
                self.real_executor.reload_api_keys(flat_keys)
            else:
                self.logger.warning("API key reload event received but no exchange keys are available")

            # Refresh and publish a fresh exchange health snapshot
            try:
                if self.real_executor:
                    self.exchange_health = await self.real_executor.get_exchange_health()
                    await self.real_executor.publish_exchange_health_snapshot()
            except Exception as health_err:
                self.logger.warning(f"Failed to refresh exchange health after API key reload: {health_err}")

            # Reload stock/FX broker executor health from latest keys.
            await self._reload_stock_executor(raw_keys)

            # Refresh symbol index and publish key-usage audit.
            try:
                await self._publish_symbol_index()
            except Exception as idx_err:
                self.logger.warning(f"Failed to publish symbol index after API key reload: {idx_err}")
            self._publish_api_key_usage_audit()

            # Publish the canonical live-vs-dormant trading venue status so
            # the GUI "Live Venues" badge, Ollama brain, and any dashboard
            # subscriber refreshes automatically after every reload.
            try:
                from core.trading_venue_status import (
                    compute_trading_venue_status,
                    publish_trading_venue_status,
                )
                stock_exec = getattr(self, "real_stock_executor", None)
                report = await compute_trading_venue_status(
                    self.api_key_manager,
                    real_exchange_executor=self.real_executor,
                    real_stock_executor=stock_exec,
                )
                publish_trading_venue_status(report, self.event_bus)
                counts = report.get("summary", {}).get("counts", {})
                self.logger.info(
                    "🎯 Trading venue status: %d LIVE, %d degraded, %d need-creds, %d not-configured (of %d declared)",
                    counts.get("live", 0),
                    counts.get("degraded", 0),
                    counts.get("needs_credentials", 0),
                    counts.get("not_configured", 0),
                    counts.get("total_declared", 0),
                )

                # Layer the funding/KYC knowledge matrix on top of the live
                # status so the GUI/Ollama brain can answer "what can I
                # trade right now", "what does Kingdom AI need from me", and
                # "what can AI auto-fund via crypto rails" without
                # re-deriving the logic in multiple places.
                try:
                    from core.trading_funding_matrix import (
                        build_venue_action_plan,
                        publish_funding_matrix,
                    )
                    plan = build_venue_action_plan(report)
                    publish_funding_matrix(plan, self.event_bus)
                    b = plan.get("buckets", {})
                    self.logger.info(
                        "💰 Funding matrix: trade_now=%d, ai_autofund=%d, "
                        "user_fund=%d, reconfig=%d, kyc=%d, dormant=%d, "
                        "geo_blocked=%d",
                        len(b.get("trade_now", [])),
                        len(b.get("ai_autofundable_crypto", [])),
                        len(b.get("user_fund_then_trade", [])),
                        len(b.get("needs_reconfig", [])),
                        len(b.get("needs_kyc", [])),
                        len(b.get("dormant", [])),
                        len(b.get("regulatory_blocked", [])),
                    )
                except Exception as plan_err:
                    self.logger.warning(
                        f"Failed to publish trading_funding_matrix: {plan_err}"
                    )
            except Exception as status_err:
                self.logger.warning(
                    f"Failed to publish trading_venue_status: {status_err}"
                )

        except Exception as e:
            self._handle_error("Error handling API key reload event", e)

    # =========================================================================
    # SOTA 2026 FIX: New event handlers for full frontend-backend integration
    # =========================================================================

    def is_ready(self) -> bool:
        """Check if trading component is fully initialized and ready.
        
        Returns:
            bool: True if component is ready for trading, False otherwise
        """
        return (
            getattr(self, '_running', False) and
            self.redis_connected and
            self.real_executor is not None and
            bool(self.exchange_health)
        )

    async def _on_auto_trade_started(self, event_data: Dict[str, Any]) -> None:
        """Handle auto-trading started event from frontend."""
        try:
            self.logger.info(f"Auto-trading started: {event_data}")
            self._auto_trading_active = True
            
            # Publish confirmation event
            await self.publish_event("trading.auto_trade.confirmed", {
                "status": "started",
                "timestamp": time.time(),
                "data": event_data
            })
        except Exception as e:
            self._handle_error("Error handling auto-trade started event", e)

    async def _on_auto_trade_stopped(self, event_data: Dict[str, Any]) -> None:
        """Handle auto-trading stopped event from frontend."""
        try:
            self.logger.info(f"Auto-trading stopped: {event_data}")
            self._auto_trading_active = False
            
            # Publish confirmation event
            await self.publish_event("trading.auto_trade.confirmed", {
                "status": "stopped",
                "timestamp": time.time(),
                "data": event_data
            })
        except Exception as e:
            self._handle_error("Error handling auto-trade stopped event", e)

    async def _on_strategy_started(self, event_data: Dict[str, Any]) -> None:
        """Handle strategy started event from frontend."""
        try:
            strategy_name = event_data.get('strategy', 'unknown')
            self.logger.info(f"Strategy started: {strategy_name}")
            
            # Track active strategies
            if not hasattr(self, '_active_strategies'):
                self._active_strategies = set()
            self._active_strategies.add(strategy_name)
            
            # Publish confirmation
            await self.publish_event("trading.strategy.confirmed", {
                "status": "started",
                "strategy": strategy_name,
                "timestamp": time.time()
            })
        except Exception as e:
            self._handle_error("Error handling strategy started event", e)

    async def _on_strategy_stopped(self, event_data: Dict[str, Any]) -> None:
        """Handle strategy stopped event from frontend."""
        try:
            strategy_name = event_data.get('strategy', 'unknown')
            self.logger.info(f"Strategy stopped: {strategy_name}")
            
            # Remove from active strategies
            if hasattr(self, '_active_strategies'):
                self._active_strategies.discard(strategy_name)
            
            # Publish confirmation
            await self.publish_event("trading.strategy.confirmed", {
                "status": "stopped",
                "strategy": strategy_name,
                "timestamp": time.time()
            })
        except Exception as e:
            self._handle_error("Error handling strategy stopped event", e)

    def get_real_portfolio_balances(self) -> Dict[str, Dict[str, float]]:
        """Return aggregated asset balances for unified portfolio sync."""
        aggregated: Dict[str, float] = {}
        try:
            positions = self.positions if isinstance(self.positions, dict) else {}
            for pos in positions.values():
                if not isinstance(pos, dict):
                    continue
                asset = str(pos.get("asset") or pos.get("symbol") or "").upper()
                if not asset:
                    continue
                qty_raw = pos.get("quantity", 0.0)
                try:
                    qty = float(qty_raw)
                except (TypeError, ValueError):
                    qty = 0.0
                if qty <= 0:
                    continue
                aggregated[asset] = aggregated.get(asset, 0.0) + qty
        except Exception as e:
            self.logger.debug(f"Error aggregating real portfolio balances: {e}")
        return {k: {"total": v} for k, v in aggregated.items()}

    async def _on_hedge_request(self, event_data: Dict[str, Any]) -> None:
        """Handle hedge request from frontend positions widget."""
        try:
            symbol = event_data.get('symbol')
            size = event_data.get('size', 0)
            hedge_type = event_data.get('type', 'full')
            
            self.logger.info(f"Hedge request received: {symbol} size={size} type={hedge_type}")
            
            if not symbol:
                self.logger.warning("Hedge request missing symbol")
                return
                
            if not size or size == 0:
                self.logger.warning("Hedge request has zero size")
                return
            
            if not self.real_executor:
                self.logger.error("Cannot execute hedge: RealExchangeExecutor not available")
                await self.publish_event("trading.hedge.failed", {
                    "symbol": symbol,
                    "reason": "Executor not available"
                })
                return
            
            # Execute hedge order - opposite direction of current position
            side = 'sell' if size > 0 else 'buy'
            quantity = abs(size)
            
            order_result = await self.place_order(
                symbol=symbol,
                order_type='market',
                side=side,
                quantity=quantity
            )
            
            if order_result:
                await self.publish_event("trading.hedge.executed", {
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "order": order_result,
                    "timestamp": time.time()
                })
            else:
                await self.publish_event("trading.hedge.failed", {
                    "symbol": symbol,
                    "reason": "Order placement failed"
                })
                
        except Exception as e:
            self._handle_error("Error handling hedge request", e)

    async def _on_exchanges_set(self, event_data: Dict[str, Any]) -> None:
        """Handle exchange configuration event from frontend."""
        try:
            exchanges = event_data.get('exchanges', [])
            self.logger.info(f"Exchanges set allowed: {exchanges}")
            
            # Store allowed exchanges for filtering
            self._allowed_exchanges = set(exchanges) if exchanges else None
            
            # Publish confirmation
            await self.publish_event("trading.exchanges.configured", {
                "exchanges": exchanges,
                "timestamp": time.time()
            })
        except Exception as e:
            self._handle_error("Error handling exchanges set event", e)

    async def _on_arbitrage_executed(self, event_data: Dict[str, Any]) -> None:
        """Handle arbitrage execution event from frontend."""
        try:
            self.logger.info(f"Arbitrage executed: {event_data}")
            # Log for analytics/tracking
            if self.redis and self.redis_connected:
                try:
                    key = f"{self.name}:arbitrage_history"
                    entry = json.dumps({**event_data, "timestamp": time.time()})
                    await asyncio.to_thread(self.redis.lpush, key, entry)
                    await asyncio.to_thread(self.redis.ltrim, key, 0, 999)  # Keep last 1000
                except Exception:
                    pass
        except Exception as e:
            self._handle_error("Error handling arbitrage executed event", e)

    async def _on_grid_started(self, event_data: Dict[str, Any]) -> None:
        """Handle grid trading started event from frontend."""
        try:
            self.logger.info(f"Grid trading started: {event_data}")
            self._grid_trading_active = True
        except Exception as e:
            self._handle_error("Error handling grid started event", e)

    async def _on_meanreversion_executed(self, event_data: Dict[str, Any]) -> None:
        """Handle mean reversion strategy execution event."""
        try:
            self.logger.info(f"Mean reversion executed: {event_data}")
        except Exception as e:
            self._handle_error("Error handling mean reversion event", e)

    async def _on_momentum_executed(self, event_data: Dict[str, Any]) -> None:
        """Handle momentum strategy execution event."""
        try:
            self.logger.info(f"Momentum executed: {event_data}")
        except Exception as e:
            self._handle_error("Error handling momentum event", e)

    async def _on_trend_executed(self, event_data: Dict[str, Any]) -> None:
        """Handle trend following strategy execution event."""
        try:
            self.logger.info(f"Trend executed: {event_data}")
        except Exception as e:
            self._handle_error("Error handling trend event", e)

    async def _on_ml_features_extracted(self, event_data: Dict[str, Any]) -> None:
        """Handle ML features extraction event."""
        try:
            self.logger.debug(f"ML features extracted: {len(event_data.get('features', []))} features")
            # Store for ML model training
            self._last_ml_features = event_data
        except Exception as e:
            self._handle_error("Error handling ML features event", e)

    async def _on_ml_model_trained(self, event_data: Dict[str, Any]) -> None:
        """Handle ML model training complete event."""
        try:
            model_name = event_data.get('model', 'unknown')
            accuracy = event_data.get('accuracy', 0)
            self.logger.info(f"ML model trained: {model_name} accuracy={accuracy}")
            self._ml_model_ready = True
        except Exception as e:
            self._handle_error("Error handling ML model trained event", e)

    # =========================================================================
    # End of new event handlers
    # =========================================================================
    
    async def _on_shutdown(self, event_data: Dict[str, Any]) -> None:
        """Handle system shutdown."""
        self.logger.info("Received system shutdown request")
        await self.stop()
    
    async def _cleanup_redis(self) -> None:
        """Clean up Redis connection."""
        if self.redis:
            try:
                if hasattr(self.redis, 'close'):
                    if asyncio.iscoroutinefunction(self.redis.close):
                        await self.redis.close()
                    else:
                        self.redis.close()
            except Exception as e:
                self._handle_error("Error cleaning up Redis connection", e)
            finally:
                self.redis = None
                self._redis_connected = False
    
    async def _shutdown_on_redis_failure(self) -> None:
        """Handle Redis connection failure with adaptive continuity mode.
        
        SOTA 2026 FIX: Instead of calling sys.exit(1) which crashes the entire
        application, we now enter an adaptive continuity mode where:
        - Trading component continues to run under tighter constraints
        - RealExchangeExecutor may still work for exchanges that don't require Redis
        - Frontend can check is_ready() to know component is not fully operational
        """
        error_msg = "CRITICAL: Redis connection failed - Trading in adaptive continuity mode"
        self.logger.critical(error_msg)
        
        # Set continuity flags instead of exiting.
        self._degraded_mode = True
        self._adaptive_continuity_mode = True
        self._redis_connected = False
        
        # Try to publish error event for UI notification
        try:
            if self.event_bus:
                await self.publish_event(
                    f"{self.EVENT_SYSTEM}.error",
                    {
                        "error": "redis_connection_failed",
                        "message": error_msg,
                        "degraded": True,
                        "adaptive_continuity_mode": True,
                        "component": self.name
                    }
                )
                # Also publish specific trading error for frontend
                await self.publish_event(
                    self.EVENT_TRADING_ERROR,
                    {
                        "error": "redis_unavailable",
                        "message": "Redis unavailable - some trading features may be limited",
                        "recoverable": True
                    }
                )
        except Exception as e:
            self.logger.error(f"Failed to publish Redis failure event: {e}")
        
        # Continue with initialization of non-Redis components.
        self.logger.warning("Attempting to continue trading with adaptive continuity without Redis...")
        
        # Try to initialize RealExchangeExecutor even without Redis
        try:
            if self.api_key_manager is None:
                self.api_key_manager = APIKeyManager.get_instance(
                    event_bus=self.event_bus,
                    config={}
                )
                self.api_key_manager.initialize_sync()
            
            raw_keys = self.api_key_manager.api_keys if self.api_key_manager else {}
            api_keys = build_real_exchange_api_keys(raw_keys)
            
            if api_keys:
                self.real_executor = RealExchangeExecutor(api_keys, event_bus=self.event_bus)
                self.exchange_health = await self.real_executor.get_exchange_health()
                self.logger.info("✅ RealExchangeExecutor initialized in adaptive continuity mode (no Redis)")
        except Exception as exec_err:
            self.logger.error(f"Failed to initialize RealExchangeExecutor in adaptive continuity mode: {exec_err}")
