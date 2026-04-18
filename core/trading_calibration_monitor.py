"""Calibration monitor for live trading.

Tracks prediction calibration via rolling Brier Score and can halt trading when
calibration breaks.

Integration points:
- Subscribes to `strategy.signal` to capture predicted probabilities (`confidence`).
- Subscribes to `trading.position.exit` to capture realized outcomes (profit/loss).
- Exposes `should_allow_trade()` for execution choke points.

Design goals:
- Safe defaults: if no data or missing metadata, never blocks trading.
- Event-bus friendly: handlers are synchronous (EventBus schedules async handlers).
- No hard dependency on any specific executor implementation.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class TradingCalibrationMonitor:
    _instance: Optional["TradingCalibrationMonitor"] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        event_bus: Any = None,
        *,
        rolling_window: int = 50,
        min_trades_before_gating: int = 30,
        brier_halt_threshold: float = 0.18,
        brier_resume_threshold: float = 0.15,
        brier_trend_spike: float = 0.05,
        trend_recent_n: int = 10,
        warn_cooldown_seconds: float = 30.0,
    ):
        self._event_bus = event_bus

        self.rolling_window = int(rolling_window)
        self.min_trades_before_gating = int(min_trades_before_gating)
        self.brier_halt_threshold = float(brier_halt_threshold)
        self.brier_resume_threshold = float(brier_resume_threshold)
        self.brier_trend_spike = float(brier_trend_spike)
        self.trend_recent_n = int(trend_recent_n)

        self._window: Deque[Tuple[float, float]] = deque(maxlen=max(1, self.rolling_window))

        # pending prediction_id -> p
        self._pending: Dict[str, float] = {}

        self.trading_halted = False
        self._last_warn_ts = 0.0
        self._warn_cooldown_seconds = float(warn_cooldown_seconds)

        self._lock = threading.RLock()

        if event_bus is not None:
            try:
                event_bus.subscribe("strategy.signal", self.on_strategy_signal)
                event_bus.subscribe("trading.position.exit", self.on_position_exit)
            except Exception as exc:
                logger.debug("TradingCalibrationMonitor: failed to subscribe to events: %s", exc)

    @classmethod
    def get_instance(cls, event_bus: Any = None) -> "TradingCalibrationMonitor":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(event_bus=event_bus)
            else:
                # Best-effort: if instance was created without event bus, attach it.
                if event_bus is not None and getattr(cls._instance, "_event_bus", None) is None:
                    cls._instance._event_bus = event_bus
                    try:
                        event_bus.subscribe("strategy.signal", cls._instance.on_strategy_signal)
                        event_bus.subscribe("trading.position.exit", cls._instance.on_position_exit)
                    except Exception:
                        pass
            return cls._instance

    # ------------------------------------------------------------------
    # Event handlers (must be sync; EventBus will schedule if async)
    # ------------------------------------------------------------------

    def on_strategy_signal(self, event: Any) -> None:
        """Capture predicted probability from a strategy signal.

        Expected shape: dict-like with optional keys:
        - confidence: float in [0,1] (if missing we ignore)
        - metadata: dict (optional)

        We do NOT rely on mutating the incoming payload (could be shared across
        subscribers). Instead, we only *read* from it and store a pending record.

        If callers want tighter linkage, they can pass a stable `prediction_id`
        inside metadata; otherwise we generate one.
        """

        if not isinstance(event, dict):
            return

        confidence: Any = event.get("confidence", None)
        if confidence is None:
            return
        try:
            p = float(confidence)
        except (TypeError, ValueError):
            return

        if p < 0.0 or p > 1.0:
            # Avoid poisoning calibration stats.
            return

        meta = event.get("metadata")
        prediction_id = None
        if isinstance(meta, dict):
            prediction_id = meta.get("prediction_id") or meta.get("calibration_id")

        if not prediction_id:
            prediction_id = str(uuid.uuid4())

        with self._lock:
            self._pending[prediction_id] = p

    def on_position_exit(self, event: Any) -> None:
        """Resolve an outcome for a previously recorded prediction.

        Expected event (dict-like) from PositionMonitor:
        - realized_pnl: float
        - metadata: dict (optional) containing prediction_id

        Outcome definition:
        - o = 1.0 if realized_pnl > 0 else 0.0

        If the position exit does not include a prediction_id, we ignore it.
        (Safe default: missing linkage should never block trading.)
        """

        if not isinstance(event, dict):
            return

        meta = event.get("metadata")
        if not isinstance(meta, dict):
            return

        prediction_id = meta.get("prediction_id") or meta.get("calibration_id")
        if not prediction_id:
            return

        with self._lock:
            p = self._pending.pop(str(prediction_id), None)

        if p is None:
            return

        realized_pnl = event.get("realized_pnl", 0.0)
        try:
            pnl_val = float(realized_pnl)
        except (TypeError, ValueError):
            pnl_val = 0.0

        o = 1.0 if pnl_val > 0.0 else 0.0

        with self._lock:
            self._window.append((float(p), float(o)))

        self._evaluate_and_maybe_toggle()

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _evaluate_and_maybe_toggle(self) -> None:
        with self._lock:
            n = len(self._window)
            if n < self.min_trades_before_gating:
                return

            scores = [(p - o) ** 2 for p, o in self._window]
            brier = sum(scores) / max(1, len(scores))

            recent_n = min(self.trend_recent_n, len(scores))
            recent = sum(scores[-recent_n:]) / max(1, recent_n)
            earlier_denom = max(1, len(scores) - recent_n)
            earlier = sum(scores[:-recent_n]) / earlier_denom if len(scores) > recent_n else brier
            trend_spike = (recent - earlier) > self.brier_trend_spike

            should_halt = (brier > self.brier_halt_threshold) or trend_spike

            prev = self.trading_halted
            if should_halt and not prev:
                self.trading_halted = True
                self._publish_state_change(
                    "trading.calibration.halt",
                    {
                        "brier": brier,
                        "window": n,
                        "trend_spike": trend_spike,
                        "recent": recent,
                        "earlier": earlier,
                        "ts": time.time(),
                    },
                )
                logger.warning(
                    "CALIBRATION HALT — Brier=%.4f threshold=%.2f trend_spike=%s",
                    brier,
                    self.brier_halt_threshold,
                    trend_spike,
                )
            elif prev and (brier < self.brier_resume_threshold):
                self.trading_halted = False
                self._publish_state_change(
                    "trading.calibration.resume",
                    {
                        "brier": brier,
                        "window": n,
                        "ts": time.time(),
                    },
                )
                logger.info(
                    "CALIBRATION RESUME — Brier=%.4f below %.2f",
                    brier,
                    self.brier_resume_threshold,
                )

            # Always publish rolling metric updates (best-effort, low volume)
            self._publish_state_change(
                "trading.calibration.update",
                {
                    "brier": brier,
                    "window": n,
                    "halted": bool(self.trading_halted),
                    "ts": time.time(),
                },
            )

    def _publish_state_change(self, event_name: str, payload: Dict[str, Any]) -> None:
        bus = getattr(self, "_event_bus", None)
        if bus is None:
            return
        try:
            bus.publish(event_name, payload)
        except Exception:
            return

    # ------------------------------------------------------------------
    # Public API for executors
    # ------------------------------------------------------------------

    def should_allow_trade(self) -> bool:
        if not self.trading_halted:
            return True

        now = time.time()
        if (now - self._last_warn_ts) >= self._warn_cooldown_seconds:
            self._last_warn_ts = now
            logger.warning("Order blocked — calibration halt active")
        return False

    def current_brier(self) -> Optional[float]:
        with self._lock:
            if len(self._window) < self.min_trades_before_gating:
                return None
            scores = [(p - o) ** 2 for p, o in self._window]
            return sum(scores) / max(1, len(scores))
