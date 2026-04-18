"""Module 3: High-yield dividend risk screen – flags unsustainable payouts."""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger("kingdom_ai.autonomous_trading.m3")

DIVIDEND_UNIVERSE = {
    "T": {"sector": "Telecom", "base_yield": 6.8, "payout_ratio": 0.92},
    "MO": {"sector": "Consumer Staples", "base_yield": 8.1, "payout_ratio": 0.80},
    "VZ": {"sector": "Telecom", "base_yield": 6.5, "payout_ratio": 0.55},
    "XOM": {"sector": "Energy", "base_yield": 3.4, "payout_ratio": 0.45},
    "KO": {"sector": "Consumer Staples", "base_yield": 3.0, "payout_ratio": 0.70},
    "PFE": {"sector": "Healthcare", "base_yield": 5.7, "payout_ratio": 0.65},
    "IBM": {"sector": "Technology", "base_yield": 4.5, "payout_ratio": 0.72},
    "CVX": {"sector": "Energy", "base_yield": 3.8, "payout_ratio": 0.50},
    "O": {"sector": "REIT", "base_yield": 5.2, "payout_ratio": 0.82},
    "ABBV": {"sector": "Healthcare", "base_yield": 3.9, "payout_ratio": 0.55},
}

YIELD_RISK_THRESHOLD = 5.0
PAYOUT_RISK_THRESHOLD = 0.75
PRICE_DROP_RISK_PCT = -8.0


class DividendRadarModule:
    module_name = "Dividend Radar"
    weight = 0.10

    def __init__(self, data_feeds: Any = None, ollama_brain: Any = None):
        self.data_feeds = data_feeds
        self.ollama = ollama_brain

    async def analyze(self) -> Dict[str, Any]:
        try:
            risky_stocks: List[Dict[str, Any]] = []
            safe_opportunities: List[Dict[str, Any]] = []
            all_screened: List[Dict[str, Any]] = []

            for symbol, profile in DIVIDEND_UNIVERSE.items():
                try:
                    data = await self.data_feeds.get_stock_data(symbol)
                    if data.get("simulated"):
                        data = self._enrich_simulated(symbol, data, profile)
                except Exception as exc:
                    logger.debug("dividend fetch %s: %s", symbol, exc)
                    continue

                close = float(data.get("close", 0) or 0)
                prev_close = float(data.get("prev_close", close) or close)
                price_change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0.0

                current_yield = profile["base_yield"] * (prev_close / close) if close > 0 else profile["base_yield"]
                payout_ratio = profile["payout_ratio"]

                risk_flags: List[str] = []
                risk_score = 0.0

                if current_yield >= YIELD_RISK_THRESHOLD:
                    risk_flags.append(f"high_yield_{current_yield:.1f}pct")
                    risk_score += 0.3
                if payout_ratio >= PAYOUT_RISK_THRESHOLD:
                    risk_flags.append(f"high_payout_ratio_{payout_ratio:.0%}")
                    risk_score += 0.3
                if price_change_pct <= PRICE_DROP_RISK_PCT:
                    risk_flags.append(f"sharp_price_decline_{price_change_pct:.1f}pct")
                    risk_score += 0.4

                entry = {
                    "symbol": symbol,
                    "sector": profile["sector"],
                    "current_yield_pct": round(current_yield, 2),
                    "payout_ratio": round(payout_ratio, 2),
                    "price": round(close, 2),
                    "price_change_pct": round(price_change_pct, 2),
                    "risk_score": round(min(risk_score, 1.0), 2),
                    "risk_flags": risk_flags,
                }
                all_screened.append(entry)

                if risk_score >= 0.5:
                    risky_stocks.append(entry)
                elif current_yield >= 3.0 and risk_score < 0.3:
                    safe_opportunities.append(entry)

            risky_stocks.sort(key=lambda x: x["risk_score"], reverse=True)
            safe_opportunities.sort(key=lambda x: x["current_yield_pct"], reverse=True)

            has_actionable = len(safe_opportunities) > 0
            confidence = min(0.88, 0.50 + len(all_screened) * 0.04)

            ideas = [
                {
                    "symbol": opp["symbol"],
                    "direction": "long",
                    "reason": f"Sustainable {opp['current_yield_pct']:.1f}% yield, low risk score {opp['risk_score']}",
                    "size_hint": "small",
                }
                for opp in safe_opportunities[:3]
            ]

            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "risky_stocks": risky_stocks,
                "safe_opportunities": safe_opportunities[:5],
                "total_screened": len(all_screened),
                "confidence": round(confidence, 3),
                "action": "trade" if has_actionable else "monitor",
                "ideas": ideas,
            }
        except Exception as exc:
            logger.error("DividendRadarModule.analyze failed: %s", exc, exc_info=True)
            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "risky_stocks": [],
                "safe_opportunities": [],
                "total_screened": 0,
                "confidence": 0.0,
                "action": "monitor",
                "error": str(exc),
            }

    @staticmethod
    def _enrich_simulated(symbol: str, data: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        base = data.get("close", 100.0)
        seed = hash(symbol + datetime.now().strftime("%Y%m%d%H"))
        rng = random.Random(seed)
        close = base * rng.uniform(0.88, 1.08)
        prev = close * rng.uniform(0.94, 1.06)
        return {
            **data,
            "close": round(close, 2),
            "prev_close": round(prev, 2),
        }
