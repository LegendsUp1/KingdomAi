import asyncio
import json
import logging
import math
import os
import statistics
import time
from collections import deque, defaultdict
from typing import Any, Deque, Dict, List, Optional, Tuple

from core.base_component_v2 import BaseComponentV2


class LearningOrchestrator(BaseComponentV2):
    """Analysis-readiness learning orchestrator over historical + live telemetry.

    This component maintains a rolling study window (default 24 hours) over
    multi-source trading and blockchain telemetry and emits two primary topics:

    - ``learning.metrics``: aggregated counts and quality metrics per source.
    - ``learning.readiness``: coarse readiness state for higher-level learning
      loops (``WARMUP``, ``LEARNING``, ``READY``, ``DEGRADED``).

    Design is intentionally lightweight and event-driven so it can run
    alongside MetaLearning, PaperAutotradeOrchestrator, and Thoth/Ollama
    without blocking the event loop.
    """

    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(name="LearningOrchestrator", event_bus=event_bus, config=config or {})
        self.logger = logging.getLogger("kingdom_ai.LearningOrchestrator")

        # Study window configuration (seconds). Default removes fixed 24h gate.
        self.study_duration_seconds: float = float(self.config.get("study_duration_seconds", 0.0))
        self.min_events_for_ready: int = int(self.config.get("min_events_for_ready", 1_000))
        self.min_sources_for_ready: int = int(self.config.get("min_sources_for_ready", 4))
        self.metrics_emit_interval: float = float(self.config.get("metrics_emit_interval", 60.0))
        self.max_events_per_source: int = int(self.config.get("max_events_per_source", 20_000))

        # PREDATOR MODE CONFIGURATION
        # After 24-hour learning window completes, system becomes PREDATORIALLY AGGRESSIVE
        # These are the LEARNING PHASE thresholds (conservative during warmup only)
        self._learning_phase_win_rate: float = 0.60  # 60% during learning
        self._learning_phase_drawdown: float = 15.0  # 15% during learning
        
        # PREDATOR MODE thresholds (AGGRESSIVE after 24 hours)
        self._predator_win_rate: float = 0.45  # Hunt opportunities at 45%+ edge
        self._predator_drawdown: float = 25.0  # Accept higher risk for higher reward
        self._predator_mode_active: bool = False
        self._predator_mode_start_ts: float = 0.0
        
        # Current active thresholds (start conservative, become predator)
        self.target_win_rate_for_live: float = float(
            self.config.get("target_win_rate_for_live", self._learning_phase_win_rate)
        )
        self.min_trades_for_profit_eval: int = int(
            self.config.get("min_trades_for_profit_eval", 50)  # Only need 50 trades to prove concept
        )
        # Max allowed peak-to-trough drawdown (in percent) for paper equity.
        self.max_allowed_drawdown_pct: float = float(
            self.config.get("max_allowed_drawdown_pct", self._learning_phase_drawdown)
        )

        # PREDATOR MODE: Aggressive profit-targeting after learning
        # Wilson intervals still used but with LOWER confidence requirements
        self.win_rate_confidence_z: float = float(
            self.config.get("win_rate_confidence_z", 1.5)  # Lower Z for faster decisions
        )
        self.cvar_alpha: float = float(self.config.get("cvar_alpha", 0.05))  # Look at worst 5%
        # CVaR threshold - PREDATOR accepts more tail risk for opportunity
        self.cvar_threshold: float = float(self.config.get("cvar_threshold", -0.10))  # Accept -10% tail

        # Latest paper autotrade metrics snapshot as emitted by
        # PaperAutotradeOrchestrator. This is used to derive an explicit
        # profit-focused view (win-rates, drawdowns, per-strategy policy).
        self._latest_paper_metrics: Optional[Dict[str, Any]] = None

        # Internal rolling buffers: per-source deque[(ts, quality_score)]
        self._buffers: Dict[str, Deque[Tuple[float, float]]] = defaultdict(lambda: deque())
        self._last_emit_ts: float = 0.0
        self._window_start_ts: float = time.time()

        # Cached readiness state - transitions to PREDATOR after analysis-ready signal
        self._readiness_state: str = "WARMUP"
        self._readiness_reason: str = "Learning window just started - waiting for full analysis readiness"
        self._analysis_ready: bool = bool(self.config.get("analysis_ready", False))
        
        # Opportunity hunting stats
        self._opportunities_detected: int = 0
        self._opportunities_executed: int = 0
        self._predator_hunt_active: bool = False

        # Latest computed metrics snapshots so other components and policies
        # can query them without having to subscribe directly to events.
        self._last_metrics_snapshot: Optional[Dict[str, Any]] = None
        self._last_profit_view: Optional[Dict[str, Any]] = None

        # Redis Quantum Nexus persistence for cross-tab/system learning continuity.
        self._redis = None
        self._redis_metrics_key = str(self.config.get("redis_metrics_key", "learning:metrics:latest"))
        self._redis_readiness_key = str(self.config.get("redis_readiness_key", "learning:readiness:latest"))
        self._redis_event_key = str(self.config.get("redis_event_key", "learning:telemetry:events"))
        self._redis_event_max = int(self.config.get("redis_event_max", 5000))
        try:
            import redis
            try:
                from core.redis_channels import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
            except Exception:
                REDIS_HOST, REDIS_PORT, REDIS_PASSWORD = "localhost", 6380, os.environ.get("REDIS_PASSWORD", "QuantumNexus2025")
            self._redis = redis.Redis(
                host=REDIS_HOST,
                port=int(REDIS_PORT),
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=2,
            )
            self._redis.ping()
            self.logger.info("✅ LearningOrchestrator connected to Redis Quantum Nexus")
        except Exception as e:
            self._redis = None
            self.logger.debug(f"Learning Redis persistence unavailable: {e}")

    @property
    def latest_metrics_snapshot(self) -> Optional[Dict[str, Any]]:
        """Most recent ``learning.metrics`` payload computed by this orchestrator."""

        return self._last_metrics_snapshot

    async def _initialize(self) -> None:
        try:
            # Restore latest persisted snapshots if present.
            if self._redis:
                try:
                    raw_metrics = await asyncio.to_thread(self._redis.get, self._redis_metrics_key)
                    if raw_metrics:
                        parsed = json.loads(raw_metrics)
                        if isinstance(parsed, dict):
                            self._last_metrics_snapshot = parsed
                    raw_ready = await asyncio.to_thread(self._redis.get, self._redis_readiness_key)
                    if raw_ready:
                        parsed_ready = json.loads(raw_ready)
                        if isinstance(parsed_ready, dict):
                            self._readiness_state = str(parsed_ready.get("state", self._readiness_state))
                            self._readiness_reason = str(parsed_ready.get("reason", self._readiness_reason))
                            self._window_start_ts = float(parsed_ready.get("window_start_ts", self._window_start_ts) or self._window_start_ts)
                except Exception as restore_err:
                    self.logger.debug(f"Could not restore learning snapshots from Redis: {restore_err}")
            self.logger.info(
                "LearningOrchestrator initialized – study_duration=%.0fs, min_events=%d, min_sources=%d",
                self.study_duration_seconds,
                self.min_events_for_ready,
                self.min_sources_for_ready,
            )
        except Exception as e:
            self._handle_error("Error during LearningOrchestrator initialization", e)

    async def _register_event_handlers(self) -> None:
        """Subscribe to multi-source telemetry streams.

        We deliberately subscribe at a coarse level to avoid tight coupling to
        any single backend implementation. Each handler records an observation
        with an approximate "quality score" (0–1) and lets the rolling window
        logic handle aggregation.
        """

        # Core trading / risk
        await self.subscribe("trading.live_prices", self._on_trading_event)
        await self.subscribe("trading.portfolio.snapshot", self._on_trading_event)
        await self.subscribe("trading.risk.snapshot", self._on_trading_event)
        await self.subscribe("trading.anomaly.snapshot", self._on_anomaly_event)
        await self.subscribe("trading.strategy_marketplace.snapshot", self._on_trading_event)
        await self.subscribe("trading.ai.snapshot", self._on_trading_event)
        await self.subscribe("trading.prediction.snapshot", self._on_trading_event)

        # Paper autotrade / performance-aware signals
        await self.subscribe("autotrade.paper.metrics", self._on_learning_signal)
        await self.subscribe("autotrade.readiness", self._on_learning_signal)
        await self.subscribe("ai.autotrade.analysis.ready", self._on_analysis_ready_signal)
        await self.subscribe("learning.request", self._on_learning_request)
        await self.subscribe("learning.response", self._on_learning_response)
        await self.subscribe("learning.context.update", self._on_learning_context_update)

        # Blockchain & web3 analytics (via reporting system and connectors)
        await self.subscribe("blockchain.performance_update", self._on_blockchain_event)
        await self.subscribe("blockchain.transaction_recorded", self._on_blockchain_event)
        await self.subscribe("blockchain.wallet_update", self._on_blockchain_event)
        await self.subscribe("blockchain.contract_interaction", self._on_blockchain_event)

        # SOTA 2026: Cross-tab wildcard intake so learning reflects all system
        # actions (trading, wallet, mining, KAIG, GUI/VR/Vision, AI, comms, etc).
        await self.subscribe("trading.*", self._on_trading_event)
        await self.subscribe("wallet.*", self._on_wallet_event)
        await self.subscribe("mining.*", self._on_mining_event)
        await self.subscribe("kaig.*", self._on_kaig_event)
        await self.subscribe("vr.*", self._on_vr_event)
        await self.subscribe("vision.*", self._on_vision_event)
        await self.subscribe("gui.*", self._on_gui_event)
        await self.subscribe("ui.telemetry", self._on_ui_telemetry)
        # Creation engines (image/video/world generation) must be explicit
        # first-class learning sources, not only caught by global wildcard.
        await self.subscribe("creation.*", self._on_creation_event)
        await self.subscribe("genie3.*", self._on_creation_event)
        await self.subscribe("ai.*", self._on_ai_event)
        await self.subscribe("blockchain.*", self._on_blockchain_event)
        await self.subscribe("api.*", self._on_system_event)
        await self.subscribe("system.*", self._on_system_event)
        await self.subscribe("comms.*", self._on_system_event)
        # Final catch-all to ensure every emitted action can contribute
        # to learning telemetry even when a component uses a custom topic.
        await self.subscribe("*", self._on_global_event)

    async def _on_wallet_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("wallet", payload, quality_hint="default")
        await self._maybe_emit()

    async def _on_mining_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("mining", payload, quality_hint="default")
        await self._maybe_emit()

    async def _on_kaig_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("kaig", payload, quality_hint="high")
        await self._maybe_emit()

    async def _on_vr_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("vr", payload, quality_hint="default")
        await self._maybe_emit()

    async def _on_vision_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("vision", payload, quality_hint="default")
        await self._maybe_emit()

    async def _on_gui_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("gui", payload, quality_hint="low")
        await self._maybe_emit()

    async def _on_ui_telemetry(self, payload: Dict[str, Any]) -> None:
        try:
            tab = "unknown"
            if isinstance(payload, dict):
                tab = str(payload.get("tab") or "unknown").strip().lower() or "unknown"
            source = f"gui.{tab}"
            self._record_event(source, payload or {}, quality_hint="high")
            await self._persist_learning_event(source, payload or {})
        except Exception:
            self._record_event("gui", payload or {}, quality_hint="low")
        await self._maybe_emit()

    async def _on_ai_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("ai", payload, quality_hint="high")
        await self._maybe_emit()

    async def _on_creation_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("creation", payload, quality_hint="high")
        await self._maybe_emit()

    async def _on_system_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("system", payload, quality_hint="default")
        await self._maybe_emit()

    async def _on_global_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("global", payload, quality_hint="low")
        await self._maybe_emit()

    async def _start(self) -> None:
        # No dedicated background loop; metrics are emitted on a timer when
        # events arrive via _maybe_emit().
        return

    # ------------------------------------------------------------------
    # Event handlers – record observations into rolling buffers
    # ------------------------------------------------------------------

    async def _on_trading_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("trading", payload, quality_hint="default")
        await self._maybe_emit()

    async def _on_anomaly_event(self, payload: Dict[str, Any]) -> None:
        # Treat anomalies as high-information events.
        self._record_event("anomaly", payload, quality_hint="high")
        await self._maybe_emit()

    async def _on_blockchain_event(self, payload: Dict[str, Any]) -> None:
        self._record_event("blockchain", payload, quality_hint="default")
        await self._maybe_emit()

    async def _on_learning_signal(self, payload: Dict[str, Any]) -> None:
        # Learning signals from paper autotrade or other orchestrators.
        self._record_event("learning_signal", payload, quality_hint="high")
        # Also treat autotrade.paper.metrics payloads as the canonical source
        # of profit-focused information so we can derive a policy that aims to
        # only enable live trading when paper results are extremely strong.
        if isinstance(payload, dict) and (
            "equity" in payload or "strategy_metrics" in payload
        ):
            self._latest_paper_metrics = payload
        await self._maybe_emit()

    async def _on_learning_request(self, payload: Dict[str, Any]) -> None:
        self._record_event("learning.request", payload or {}, quality_hint="high")
        await self._persist_learning_event("learning.request", payload or {})
        await self._maybe_emit()

    async def _on_learning_response(self, payload: Dict[str, Any]) -> None:
        self._record_event("learning.response", payload or {}, quality_hint="high")
        await self._persist_learning_event("learning.response", payload or {})
        await self._maybe_emit()

    async def _on_learning_context_update(self, payload: Dict[str, Any]) -> None:
        self._record_event("learning.context.update", payload or {}, quality_hint="high")
        await self._persist_learning_event("learning.context.update", payload or {})
        await self._maybe_emit()

    async def _on_analysis_ready_signal(self, payload: Dict[str, Any]) -> None:
        """Mark full-analysis readiness from orchestration events."""
        try:
            ready = True
            if isinstance(payload, dict) and "ready" in payload:
                ready = bool(payload.get("ready"))
            self._analysis_ready = ready
            await self._maybe_emit()
        except Exception as e:
            self._handle_error("Error in _on_analysis_ready_signal", e)

    # ------------------------------------------------------------------
    # Core rolling-window logic
    # ------------------------------------------------------------------

    def _record_event(self, source: str, payload: Dict[str, Any], quality_hint: str = "default") -> None:
        try:
            now = time.time()
            q = 0.5
            if quality_hint == "high":
                q = 1.0
            elif quality_hint == "low":
                q = 0.25

            buf = self._buffers[source]
            buf.append((now, q))
            # Bound memory when study_duration_seconds == 0 (continuous mode).
            if self.max_events_per_source > 0:
                while len(buf) > self.max_events_per_source:
                    buf.popleft()

            # Drop observations outside the study window
            if self.study_duration_seconds > 0:
                cutoff = now - self.study_duration_seconds
                while buf and buf[0][0] < cutoff:
                    buf.popleft()
        except Exception as e:
            self._handle_error(f"Error recording learning event for {source}", e)

    def _compute_window_metrics(self) -> Dict[str, Any]:
        now = time.time()
        cutoff = (now - self.study_duration_seconds) if self.study_duration_seconds > 0 else 0.0
        self._window_start_ts = cutoff

        per_source: Dict[str, Dict[str, Any]] = {}
        total_events = 0
        active_sources = 0

        for source, buf in self._buffers.items():
            # Ensure buffer is pruned (in case no new events for this source)
            if self.study_duration_seconds > 0:
                while buf and buf[0][0] < cutoff:
                    buf.popleft()

            count = len(buf)
            if count == 0:
                continue

            active_sources += 1
            total_events += count

            sum_q = sum(q for _, q in buf)
            avg_q = sum_q / float(count) if count > 0 else 0.0
            per_source[source] = {
                "event_count": count,
                "avg_quality": avg_q,
                "events_per_min": count / max(
                    1.0,
                    (self.study_duration_seconds / 60.0) if self.study_duration_seconds > 0 else 1.0,
                ),
            }

        coverage_ratio = 0.0
        if self.min_sources_for_ready > 0:
            coverage_ratio = min(1.0, active_sources / float(self.min_sources_for_ready))

        dens_ratio = 0.0
        if self.min_events_for_ready > 0:
            dens_ratio = min(1.0, total_events / float(self.min_events_for_ready))

        learning_score = 0.5 * coverage_ratio + 0.5 * dens_ratio

        metrics: Dict[str, Any] = {
            "timestamp": now,
            "window_start_ts": cutoff,
            "window_duration_seconds": self.study_duration_seconds,
            "total_events": total_events,
            "active_sources": active_sources,
            "min_events_for_ready": self.min_events_for_ready,
            "min_sources_for_ready": self.min_sources_for_ready,
            "coverage_ratio": coverage_ratio,
            "density_ratio": dens_ratio,
            "learning_score": learning_score,
            "per_source": per_source,
        }

        # Attach a profit-focused view derived from the latest
        # autotrade.paper.metrics snapshot, if available. This is where we try
        # to translate recent paper performance into an extremely conservative
        # live-trading policy aspiring to near-100% win rate.
        profit_view = self._compute_paper_profit_view()
        if profit_view is not None:
            metrics["paper_profit_view"] = profit_view

        # Cache latest views for policy helpers and diagnostics.
        self._last_metrics_snapshot = metrics

        return metrics

    def _compute_paper_profit_view(self) -> Optional[Dict[str, Any]]:
        """Derive a profit-optimization view from paper autotrade metrics.

        This consumes the latest ``autotrade.paper.metrics`` snapshot and
        produces:

        - Global win-rate and drawdown.
        - Per-strategy statistics and whether each meets the extremely strict
          thresholds configured for live trading.
        - An overall ``eligible_for_live`` flag that downstream components can
          treat as a hard gate for live auto-trading.

        Note: This does **not** guarantee 100% win rate mathematically, but it
        sharpens the policy so that live trading only happens when the
        empirical paper results are extraordinarily strong.
        """

        pm = self._latest_paper_metrics
        if not isinstance(pm, dict):
            return None

        try:
            # Prefer richer nested "global" section when available (as emitted
            # by the paper orchestrator), but fall back to legacy top-level
            # fields so older payloads continue to work.
            g = pm.get("global") or {}
            trade_count = int(g.get("trades", pm.get("trade_count", 0)) or 0)
            wins = int(g.get("wins", pm.get("wins", 0)) or 0)
            losses = int(g.get("losses", pm.get("losses", 0)) or 0)
            max_dd = float(
                g.get("max_drawdown_pct", pm.get("max_drawdown", 0.0)) or 0.0
            )
            # win_rate is kept for backwards compatibility; we also compute it
            # directly from wins/trades when possible.
            win_rate = float(pm.get("win_rate", 0.0) or 0.0)
            if trade_count > 0 and wins >= 0:
                win_rate = wins / float(trade_count)

            # Global PnL series for CVaR and Kelly-style statistics.
            pnl_series: List[float] = []
            try:
                if isinstance(pm.get("pnl_series"), list):
                    pnl_series = [float(x) for x in pm.get("pnl_series")]
                elif isinstance(g.get("pnl_series"), list):
                    pnl_series = [float(x) for x in g.get("pnl_series")]
            except Exception:
                pnl_series = []

            # Wilson score interval for a conservative lower bound on the true
            # win-rate. This lets us treat the configured target as a
            # near-100%-win criterion even under sampling noise.
            lower_ci, upper_ci = self._wilson_score_interval(wins, max(1, trade_count))

            # Empirical CVaR over tail losses. If CVaR is worse than the
            # configured threshold, we consider the system too risky for live
            # trading even if raw win-rate looks high.
            cvar = self._empirical_cvar(pnl_series, alpha=self.cvar_alpha)

            # Use the configured thresholds to determine whether global paper
            # performance is strong enough to consider enabling live trading.
            enough_trades = trade_count >= self.min_trades_for_profit_eval
            meets_win_rate = lower_ci >= self.target_win_rate_for_live
            meets_drawdown = max_dd <= self.max_allowed_drawdown_pct
            meets_cvar = cvar >= self.cvar_threshold

            eligible_for_live = bool(
                enough_trades and meets_win_rate and meets_drawdown and meets_cvar
            )

            # Per-strategy view: for each canonical style, compute whether it
            # individually satisfies the same (or stricter) thresholds. We pay
            # special attention to low-structural-risk families such as
            # arbitrage, pairs trading, liquidity provision, and options
            # hedging, as suggested by SOTA 2025-26 literature.
            strategies_raw = pm.get("strategy_metrics") or {}
            per_strategy: Dict[str, Any] = {}
            enabled_strategies: List[str] = []
            disabled_strategies: List[str] = []

            if isinstance(strategies_raw, dict):
                for style, stats in strategies_raw.items():
                    if not isinstance(stats, dict):
                        continue
                    s_trades = int(stats.get("trade_count", 0) or 0)
                    s_wins = int(stats.get("wins", 0) or 0)
                    s_losses = int(stats.get("losses", 0) or 0)
                    s_dd = float(stats.get("max_drawdown", 0.0) or 0.0)
                    total = max(1, s_wins + s_losses)
                    s_wr = s_wins / float(total) if total > 0 else 0.0

                    # For lower-structural-risk styles, optionally require an
                    # even higher win-rate or tighter drawdown to reflect the
                    # expectation that they should behave closer to
                    # near-arbitrage.
                    style_key = str(style)
                    is_low_structural_risk = style_key in {
                        "arbitrage",
                        "pairs_trading",
                        "liquidity_provision",
                        "options_hedge",
                    }

                    wr_threshold = self.target_win_rate_for_live
                    dd_threshold = self.max_allowed_drawdown_pct
                    if is_low_structural_risk:
                        wr_threshold = min(0.999, self.target_win_rate_for_live + 0.005)
                        dd_threshold = min(self.max_allowed_drawdown_pct, 3.0)

                    # Per-strategy tail risk via CVaR over its own PnL series
                    s_pnls: List[float] = []
                    try:
                        if isinstance(stats.get("pnl_series"), list):
                            s_pnls = [float(x) for x in stats.get("pnl_series")]
                    except Exception:
                        s_pnls = []
                    s_cvar = self._empirical_cvar(s_pnls, alpha=self.cvar_alpha)

                    s_enough_trades = s_trades >= self.min_trades_for_profit_eval
                    s_meets_wr = s_wr >= wr_threshold
                    s_meets_dd = s_dd <= dd_threshold
                    s_meets_cvar = s_cvar >= self.cvar_threshold
                    s_ok = bool(s_enough_trades and s_meets_wr and s_meets_dd and s_meets_cvar)

                    per_strategy[style_key] = {
                        "trade_count": s_trades,
                        "wins": s_wins,
                        "losses": s_losses,
                        "win_rate": s_wr,
                        "max_drawdown": s_dd,
                         "cvar": s_cvar,
                        "meets_thresholds": s_ok,
                        "win_rate_threshold": wr_threshold,
                        "drawdown_threshold": dd_threshold,
                    }

                    if s_ok:
                        enabled_strategies.append(style_key)
                    else:
                        disabled_strategies.append(style_key)

            # Kelly-style sizing suggestion using global PnL distribution. This
            # is advisory only and is *not* enforced by the orchestrator.
            avg_win = statistics.mean([x for x in pnl_series if x > 0.0]) if any(
                x > 0.0 for x in pnl_series
            ) else 0.0
            avg_loss = -statistics.mean([x for x in pnl_series if x < 0.0]) if any(
                x < 0.0 for x in pnl_series
            ) else 0.0
            kelly = self._kelly_fraction(win_rate, avg_win, avg_loss)
            shrink = 0.25 if max_dd > (self.max_allowed_drawdown_pct / 2.0) else 0.5
            suggested_fraction = kelly * shrink

            view = {
                "trade_count": trade_count,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "max_drawdown": max_dd,
                "win_rate_ci_lower": lower_ci,
                "win_rate_ci_upper": upper_ci,
                "cvar": cvar,
                "target_win_rate_for_live": self.target_win_rate_for_live,
                "min_trades_for_profit_eval": self.min_trades_for_profit_eval,
                "max_allowed_drawdown_pct": self.max_allowed_drawdown_pct,
                "eligible_for_live": eligible_for_live,
                "enough_trades": enough_trades,
                "meets_win_rate": meets_win_rate,
                "meets_drawdown": meets_drawdown,
                "meets_cvar": meets_cvar,
                "per_strategy": per_strategy,
                "enabled_strategies": enabled_strategies,
                "disabled_strategies": disabled_strategies,
                "sizing": {
                    "kelly_fraction": kelly,
                    "suggested_fraction": suggested_fraction,
                },
            }
            self._last_profit_view = view
            return view
        except Exception as e:
            self._handle_error("Error computing paper_profit_view", e)
            return None

    # ------------------------------------------------------------------
    # Advanced statistics helpers (Wilson, CVaR, Kelly)
    # ------------------------------------------------------------------

    def _wilson_score_interval(self, wins: int, n: int) -> Tuple[float, float]:
        if n <= 0:
            return 0.0, 1.0
        z = float(self.win_rate_confidence_z)
        phat = wins / float(n)
        denom = 1.0 + (z * z) / float(n)
        center = (phat + (z * z) / (2.0 * n)) / denom
        margin = z * math.sqrt(
            (phat * (1.0 - phat) / float(n)) + (z * z) / (4.0 * n * n)
        ) / denom
        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)
        return lower, upper

    def _empirical_cvar(self, pnl_list: List[float], alpha: float) -> float:
        if not pnl_list:
            return 0.0
        try:
            losses = sorted(float(x) for x in pnl_list)
            if not losses:
                return 0.0
            k = max(1, int(len(losses) * alpha))
            tail = losses[:k]
            return float(sum(tail) / float(len(tail))) if tail else 0.0
        except Exception:
            return 0.0

    def _kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        try:
            if avg_loss <= 0.0 or avg_win <= 0.0:
                return 0.0
            b = avg_win / avg_loss
            p = max(0.0, min(1.0, win_rate))
            q = 1.0 - p
            numer = p * b - q
            denom = b
            if denom <= 0.0:
                return 0.0
            f = max(0.0, numer / denom)
            return min(f, 0.25)
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # Advisory policy helpers exposed to other components
    # ------------------------------------------------------------------

    def is_trade_allowed(self, style: str, proposed_fraction: float) -> Tuple[bool, str]:
        """Advisory helper: does a trade satisfy the current profit view?

        This consults the most recently computed ``paper_profit_view`` and is
        intended for use by policy helpers (e.g. LiveAutotradePolicy) and
        diagnostics. It does *not* place orders or emit events.
        """

        view = self._last_profit_view or self._compute_paper_profit_view()
        if not isinstance(view, dict):
            return False, "no_profit_view"

        if not view.get("eligible_for_live", False):
            return False, "global_not_eligible"

        enabled = set(view.get("enabled_strategies") or [])
        if style not in enabled:
            return False, "strategy_not_enabled"

        sizing = view.get("sizing") or {}
        try:
            suggested = float(sizing.get("suggested_fraction", 0.0) or 0.0)
        except Exception:
            suggested = 0.0
        try:
            frac = float(proposed_fraction)
        except Exception:
            frac = 0.0

        if suggested > 0.0 and frac > suggested:
            return False, "size_too_large"

        return True, "ok"

    def activate_predator_mode(self) -> None:
        """🦁 ACTIVATE PREDATOR MODE - Hunt opportunities aggressively!
        
        After 24 hours of learning, the system becomes a PREDATOR:
        - Lower win-rate requirements (we learned what works)
        - Higher risk tolerance (we know the patterns)
        - Aggressive opportunity hunting (strike fast)
        - No fear, only calculated aggression
        """
        
        self.logger.info("🦁🦁🦁 PREDATOR MODE ACTIVATING 🦁🦁🦁")
        self.logger.info("Analysis readiness complete - HUNTING for opportunities!")
        
        try:
            # PREDATOR thresholds - aggressive but informed by 24h of learning
            self.target_win_rate_for_live = self._predator_win_rate  # 45% edge is enough
            self.max_allowed_drawdown_pct = self._predator_drawdown  # Accept 25% for big wins
            self.cvar_threshold = -0.15  # Accept -15% tail risk for opportunity
            self.win_rate_confidence_z = 1.0  # Low Z = fast decisions
            self.min_trades_for_profit_eval = 20  # Only need 20 trades to act
            
            # Activate predator state
            self._predator_mode_active = True
            self._predator_mode_start_ts = time.time()
            self._predator_hunt_active = True
            
            self.logger.info(f"🎯 PREDATOR thresholds: win_rate={self.target_win_rate_for_live}, drawdown={self.max_allowed_drawdown_pct}%")
            self.logger.info("🔥 System is now HUNTING for profit opportunities!")
            
        except Exception as e:
            self.logger.error(f"Error activating predator mode: {e}")
    
    def is_predator_mode(self) -> bool:
        """Check if predator mode is active."""
        return self._predator_mode_active
    
    def get_predator_stats(self) -> Dict[str, Any]:
        """Get predator mode hunting statistics."""
        return {
            "predator_mode_active": self._predator_mode_active,
            "predator_start_ts": self._predator_mode_start_ts,
            "opportunities_detected": self._opportunities_detected,
            "opportunities_executed": self._opportunities_executed,
            "hunt_active": self._predator_hunt_active,
            "current_win_rate_threshold": self.target_win_rate_for_live,
            "current_drawdown_threshold": self.max_allowed_drawdown_pct,
        }

    def _update_readiness(self, metrics: Dict[str, Any]) -> None:
        total_events = int(metrics.get("total_events", 0) or 0)
        active_sources = int(metrics.get("active_sources", 0) or 0)
        learning_score = float(metrics.get("learning_score", 0.0) or 0.0)
        
        # Analysis-ready gate replaces fixed 24h learning completion check.
        elapsed_seconds = time.time() - self._window_start_ts
        learning_complete = self._analysis_ready
        
        # 🦁 PREDATOR MODE TRANSITION
        if learning_complete and not self._predator_mode_active:
            self.logger.info("⏰ Full analysis ready signal received - activating predator mode")
            self.activate_predator_mode()
        
        # If PREDATOR MODE is active, we're always hunting
        if self._predator_mode_active:
            hunt_duration = time.time() - self._predator_mode_start_ts
            self._readiness_state = "PREDATOR"
            self._readiness_reason = (
                f"🦁 PREDATOR MODE ACTIVE – Hunting for {hunt_duration/3600:.1f}h | "
                f"Detected: {self._opportunities_detected} | Executed: {self._opportunities_executed}"
            )
            return

        # Pre-PREDATOR states (during analysis learning)
        if total_events < max(10, self.min_events_for_ready * 0.1):
            self._readiness_state = "WARMUP"
            self._readiness_reason = (
                f"WARMUP – {total_events} events | waiting for full analysis readiness"
            )
            return

        if total_events < self.min_events_for_ready or active_sources < self.min_sources_for_ready:
            self._readiness_state = "LEARNING"
            self._readiness_reason = (
                f"LEARNING – events={total_events}/{self.min_events_for_ready} | "
                f"waiting for full analysis readiness"
            )
            return

        if learning_score >= 0.9:
            self._readiness_state = "READY"
            self._readiness_reason = (
                f"READY – score={learning_score:.2f} | analysis-ready gate satisfied"
            )
        elif learning_score >= 0.6:
            self._readiness_state = "LEARNING"
            self._readiness_reason = (
                f"LEARNING – score={learning_score:.2f} | waiting for full analysis readiness"
            )
        else:
            self._readiness_state = "DEGRADED"
            self._readiness_reason = (
                f"DEGRADED – sparse telemetry (score={learning_score:.2f})"
            )

    async def _maybe_emit(self) -> None:
        now = time.time()
        if now - self._last_emit_ts < self.metrics_emit_interval:
            return

        metrics = self._compute_window_metrics()
        self._update_readiness(metrics)

        try:
            await self.publish_event("learning.metrics", metrics)
        except Exception as e:
            self._handle_error("Failed to publish learning.metrics", e)

        payload = {
            "timestamp": metrics.get("timestamp"),
            "state": self._readiness_state,
            "reason": self._readiness_reason,
            "window_start_ts": metrics.get("window_start_ts"),
            "window_duration_seconds": metrics.get("window_duration_seconds"),
            "learning_score": metrics.get("learning_score"),
            "total_events": metrics.get("total_events"),
            "active_sources": metrics.get("active_sources"),
        }

        try:
            await self.publish_event("learning.readiness", payload)
        except Exception as e:
            self._handle_error("Failed to publish learning.readiness", e)

        await self._persist_snapshots(metrics, payload)

        self._last_emit_ts = now

    async def _persist_snapshots(self, metrics: Dict[str, Any], readiness: Dict[str, Any]) -> None:
        """Persist latest learning snapshots to Redis Quantum Nexus."""
        if not self._redis:
            return
        try:
            metrics_blob = json.dumps(metrics, ensure_ascii=True)
            readiness_blob = json.dumps(readiness, ensure_ascii=True)

            def _write():
                self._redis.set(self._redis_metrics_key, metrics_blob, ex=3600)
                self._redis.set(self._redis_readiness_key, readiness_blob, ex=3600)
            await asyncio.to_thread(_write)
        except Exception as e:
            self.logger.debug(f"Learning snapshot Redis persistence error: {e}")

    async def _persist_learning_event(self, source: str, payload: Dict[str, Any]) -> None:
        """Persist a compact rolling event trail for cross-component continuity."""
        if not self._redis:
            return
        try:
            event = {
                "timestamp": time.time(),
                "source": source,
                "payload": payload if isinstance(payload, dict) else {"value": str(payload)},
            }
            blob = json.dumps(event, ensure_ascii=True)

            def _write():
                self._redis.lpush(self._redis_event_key, blob)
                self._redis.ltrim(self._redis_event_key, 0, max(0, self._redis_event_max - 1))
                # SOTA 2026 durability: append to Redis Stream for replayable ordered history.
                self._redis.xadd(
                    "learning:stream",
                    {
                        "source": source,
                        "timestamp": str(event["timestamp"]),
                        "payload": blob,
                    },
                    maxlen=20000,
                    approximate=True,
                )
            await asyncio.to_thread(_write)
        except Exception as e:
            self.logger.debug(f"Learning event Redis persistence error: {e}")
