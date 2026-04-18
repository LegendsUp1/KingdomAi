"""Module 1: Portfolio hedging signals (options / inverse ETF heuristics)."""

import logging
from datetime import datetime
from typing import Any, Dict

from .data_feeds import DataFeedManager

logger = logging.getLogger("kingdom_ai.autonomous_trading.m1")


class PortfolioHedgingModule:
    module_name = "Portfolio Hedging"
    weight = 0.15

    def __init__(self, data_feeds: DataFeedManager, ollama_brain: Any = None):
        self.data_feeds = data_feeds
        self.ollama = ollama_brain

    async def analyze(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        sector_exposure = self._sector_exposure(portfolio_data)
        largest = max(sector_exposure.items(), key=lambda x: x[1]) if sector_exposure else ("Other", 0.0)
        hedge_symbol = {"Technology": "QQQ", "Financials": "XLF", "Energy": "XLE"}.get(largest[0], "SPY")
        options_data = await self.data_feeds.get_options_data(hedge_symbol)
        return {
            "module": self.module_name,
            "timestamp": datetime.now().isoformat(),
            "sector_exposure": sector_exposure,
            "recommended_hedge": f"inverse or puts on {hedge_symbol}",
            "hedge_size_pct": min(0.5, largest[1] / 200.0),
            "confidence": 0.72 if options_data else 0.55,
            "action": "monitor",
        }

    def _sector_exposure(self, portfolio: Dict[str, Any]) -> Dict[str, float]:
        sector_map = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "JPM": "Financials",
            "XOM": "Energy",
        }
        totals: Dict[str, float] = {}
        total_v = 0.0
        for sym, pos in (portfolio or {}).items():
            if not isinstance(pos, dict):
                continue
            sec = sector_map.get(str(sym).upper(), "Other")
            v = float(pos.get("value", 0) or 0)
            totals[sec] = totals.get(sec, 0.0) + v
            total_v += v
        if total_v <= 0:
            return {"Other": 100.0}
        return {k: (v / total_v) * 100.0 for k, v in totals.items()}
