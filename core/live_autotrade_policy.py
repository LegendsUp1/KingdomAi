"""LiveAutotradePolicy helper.

This module provides a thin policy wrapper around LearningOrchestrator so that
other components (routers, RL systems, Thoth prompts) can ask
"would this trade satisfy the current profit-focused constraints?" without
hard-blocking execution.

It is intentionally side-effect free: callers decide whether to enforce the
policy or treat it as diagnostic/training signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.learning_orchestrator import LearningOrchestrator


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str


class LiveAutotradePolicy:
    """Advisory live auto-trade policy driven by LearningOrchestrator.

    The policy borrows its logic from LearningOrchestrator.paper_profit_view and
    the helper method ``is_trade_allowed(style, proposed_fraction)``.

    Nothing in this class performs I/O or places orders; it only provides a
    uniform interface so higher-level components can log or learn from the
    "would we allow this?" signal.
    """

    def __init__(
        self,
        orchestrator: Optional[LearningOrchestrator] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        cfg = config or {}
        # When no orchestrator is provided we create a detached one that can be
        # fed metrics manually. In the main app we expect to reuse the global
        # LearningOrchestrator instance that already listens to the event bus.
        self.orch: LearningOrchestrator = orchestrator or LearningOrchestrator(
            event_bus=None,
            config=cfg.get("learning_orchestrator", {}),
        )
        self.max_violations_before_kill: int = int(
            cfg.get("max_violations_before_kill", 3)
        )
        self.hard_kill: bool = False
        self.violation_count: int = 0

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def pre_trade_check(self, order: Dict[str, Any]) -> PolicyDecision:
        """Return an advisory decision for a proposed order.

        The order dict is expected to carry at least:

        - ``strategy_style`` or ``strategy``: canonical style name
        - ``size_fraction``: fraction of equity or capital to risk

        The decision's ``allowed`` field is an advisory signal. Callers are
        free to ignore it for exploration / training; the important thing is
        that the reasoning string is logged and/or stored for learning.
        """

        if self.hard_kill:
            return PolicyDecision(False, "hard_kill_active")

        style = str(
            order.get("strategy_style")
            or order.get("strategy")
            or "unknown"
        )
        try:
            size_fraction = float(order.get("size_fraction", 0.0) or 0.0)
        except Exception:
            size_fraction = 0.0

        allowed, reason = self.orch.is_trade_allowed(style, size_fraction)
        if not allowed:
            self.violation_count += 1
            if self.violation_count >= self.max_violations_before_kill:
                # Note: this flag is *not* wired into any global kill-switch by
                # default; it is up to callers to respect it.
                self.hard_kill = True
                return PolicyDecision(False, "escalated_hard_kill_after_violations")
            return PolicyDecision(False, f"blocked_by_policy:{reason}")

        # On success, reset soft violation counter
        self.violation_count = 0
        return PolicyDecision(True, "ok")

    def reset(self) -> None:
        """Clear internal violation counters and hard_kill flag."""

        self.violation_count = 0
        self.hard_kill = False

    def snapshot(self) -> Dict[str, Any]:
        """Return a small debug snapshot of policy state."""

        return {
            "hard_kill": self.hard_kill,
            "violation_count": self.violation_count,
            "max_violations_before_kill": self.max_violations_before_kill,
        }
