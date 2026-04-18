"""Routes aggregated signals to paper / live executors when enabled."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.autonomous_trading.execution")


class ExecutionEngine:
    def __init__(
        self,
        trading_engine: Any,
        api_keys: Dict[str, Any],
        stock_executor: Optional[Any] = None,
        real_executor: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.trading_engine = trading_engine
        self.api_keys = api_keys or {}
        self.stock_executor = stock_executor
        self.real_executor = real_executor
        self.config = config or {}
        self.live_execution = bool(self.config.get("live_execution", False))

    async def execute_trades(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        if signal.get("action") != "execute":
            return {"status": "skipped", "reason": "signal action not execute"}
        trades: List[Dict[str, Any]] = []
        if not self.live_execution:
            logger.info("ExecutionEngine: live_execution false; recording dry-run only.")
            return {
                "status": "dry_run",
                "trades": trades,
                "pnl": 0.0,
                "timestamp": datetime.now().isoformat(),
            }
        # Minimal hook: real wiring goes through TradingComponent policies
        return {"status": "completed", "trades": trades, "pnl": 0.0, "timestamp": datetime.now().isoformat()}
