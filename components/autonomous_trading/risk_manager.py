"""Autonomous risk checks (VaR-style thresholds, position caps) — separate from root RiskManager."""

import logging
from typing import Any, Dict

logger = logging.getLogger("kingdom_ai.autonomous_trading.risk_manager")


class AutonomousRiskManager:
    def __init__(self, base_risk_manager: Any, config: Dict[str, Any]):
        self.base = base_risk_manager
        self.config = config or {}
        rm = self.config.get("risk_management") or {}
        self.max_position_size_pct = float(rm.get("max_position_size_pct", 5)) / 100.0
        self.daily_loss_limit = float(rm.get("daily_loss_limit", 2000))
        self.var_threshold = float(rm.get("var_threshold", 0.05))
        self.max_trades_per_cycle = int(self.config.get("max_trades_per_cycle", 5))

    async def validate_trades(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        conf = float(signal.get("overall_confidence") or 0.0)
        min_conf = float(self.config.get("edge_threshold", 0.7))
        if conf < min_conf:
            return {"approved": False, "reason": f"confidence {conf:.2f} < {min_conf}"}
        n = len(signal.get("trade_ideas") or [])
        if n > self.max_trades_per_cycle:
            return {"approved": False, "reason": f"too many trade groups {n}"}
        return {"approved": True, "reason": "ok"}
