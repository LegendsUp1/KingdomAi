"""Coordinates seven modules, aggregates signals, risk, execution (asyncio, no Ray requirement)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.kingdom_event_names import AUTONOMOUS_CYCLE_COMPLETE

from .data_feeds import DataFeedManager
from .execution_engine import ExecutionEngine
from .module_1_portfolio_hedging import PortfolioHedgingModule
from .module_2_institutional_positioning import InstitutionalPositioningModule
from .module_3_dividend_radar import DividendRadarModule
from .module_4_correlation_map import CorrelationMapModule
from .module_5_sentiment_arbitrage import SentimentArbitrageModule
from .module_6_macro_analysis import MacroAnalysisModule
from .module_7_short_squeeze import ShortSqueezeModule
from .risk_manager import AutonomousRiskManager

logger = logging.getLogger("kingdom_ai.autonomous_trading.orchestrator")


class AutonomousOrchestrator:
    def __init__(
        self,
        event_bus: Any,
        trading_engine: Any,
        risk_manager: Any,
        api_keys: Dict[str, Any],
        stock_executor: Optional[Any] = None,
        real_executor: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.event_bus = event_bus
        self.trading_engine = trading_engine
        self.risk_manager = risk_manager
        self.api_keys = api_keys or {}
        self.stock_executor = stock_executor
        self.real_executor = real_executor
        self.config = config or {}
        self.data_feeds = DataFeedManager(
            api_keys,
            simulation_mode=bool(self.config.get("simulation_mode", True)),
        )
        self.execution_engine = ExecutionEngine(
            trading_engine,
            api_keys,
            stock_executor=stock_executor,
            real_executor=real_executor,
            config=self.config,
        )
        self.autonomous_risk = AutonomousRiskManager(risk_manager, self.config)
        self.modules: Dict[str, Any] = {}
        self.cycle_count = 0
        self.decisions_log: List[Dict[str, Any]] = []
        self._external_signals: List[Dict[str, Any]] = []

    async def initialize(self) -> None:
        await self.data_feeds.initialize()
        mods = self.config.get("modules") or {}
        self.modules = {
            "portfolio_hedging": PortfolioHedgingModule(self.data_feeds),
            "institutional_positioning": InstitutionalPositioningModule(self.data_feeds),
            "dividend_radar": DividendRadarModule(self.data_feeds),
            "correlation_map": CorrelationMapModule(self.data_feeds),
            "sentiment_arbitrage": SentimentArbitrageModule(self.data_feeds),
            "macro_analysis": MacroAnalysisModule(self.data_feeds),
            "short_squeeze": ShortSqueezeModule(self.data_feeds),
        }
        for name in list(self.modules.keys()):
            mc = mods.get(name) if isinstance(mods.get(name), dict) else {}
            if mc.get("enabled") is False:
                del self.modules[name]
        logger.info("AutonomousOrchestrator: %s modules active", len(self.modules))

    def _portfolio_snapshot(self) -> Dict[str, Any]:
        return self.config.get("portfolio_snapshot") or {}

    async def process_external_signal(self, kind: str, payload: Dict[str, Any]) -> None:
        self._external_signals.append({"kind": kind, "payload": payload, "ts": datetime.now().isoformat()})

    async def run_trading_cycle(self) -> Dict[str, Any]:
        self.cycle_count += 1
        t0 = datetime.now()
        try:
            results = await self._run_all_modules()
            aggregated = self._aggregate_signals(results)
            risk = await self.autonomous_risk.validate_trades(aggregated)
            if not risk.get("approved"):
                out = {"cycle": self.cycle_count, "status": "rejected", "reason": risk.get("reason")}
            else:
                execution = await self.execution_engine.execute_trades(aggregated)
                out = {
                    "cycle": self.cycle_count,
                    "status": "completed",
                    "execution": execution,
                }
            log_entry = {
                "cycle": self.cycle_count,
                "module_results": results,
                "aggregated": aggregated,
                "duration_s": (datetime.now() - t0).total_seconds(),
            }
            self.decisions_log.append(log_entry)
            if self.event_bus:
                try:
                    self.event_bus.publish(
                        AUTONOMOUS_CYCLE_COMPLETE,
                        {"internal": True, "summary": out, "log": log_entry},
                    )
                except Exception as e:
                    logger.debug("event publish: %s", e)
            return out
        except Exception as e:
            logger.error("run_trading_cycle: %s", e)
            return {"cycle": self.cycle_count, "status": "error", "error": str(e)}

    async def _run_all_modules(self) -> Dict[str, Dict[str, Any]]:
        tasks = []
        keys: List[str] = []
        for name, mod in self.modules.items():
            if name == "portfolio_hedging":
                tasks.append(mod.analyze(self._portfolio_snapshot()))
            else:
                tasks.append(mod.analyze())
            keys.append(name)
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        out: Dict[str, Dict[str, Any]] = {}
        for name, result in zip(keys, raw):
            if isinstance(result, Exception):
                out[name] = {"error": str(result), "confidence": 0.0}
            else:
                out[name] = result
        return out

    def _aggregate_signals(self, module_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        weights = {n: getattr(m, "weight", 0.1) for n, m in self.modules.items()}
        wsum = sum(weights.values()) or 1.0
        conf = sum(
            float(module_results.get(n, {}).get("confidence") or 0.0) * weights.get(n, 0.0) for n in weights
        ) / wsum
        trade_ideas: List[Dict[str, Any]] = []
        for name, result in module_results.items():
            if result.get("action") == "trade":
                trade_ideas.append(
                    {
                        "module": name,
                        "ideas": result.get("ideas") or result.get("candidates") or [],
                        "confidence": result.get("confidence", 0.0),
                    }
                )
        cfg_edge = float(self.config.get("edge_threshold", 0.7))
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_confidence": conf,
            "trade_ideas": trade_ideas,
            "module_results": module_results,
            "action": "execute" if conf >= cfg_edge and trade_ideas else "monitor",
        }
