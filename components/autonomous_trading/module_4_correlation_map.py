"""Module 4: Correlation anomaly detection – flags divergences between normally correlated assets."""

import logging
import math
import random
from datetime import datetime
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("kingdom_ai.autonomous_trading.m4")

CORRELATED_PAIRS: List[Tuple[str, str, float]] = [
    ("AAPL", "MSFT", 0.85),
    ("GOOGL", "META", 0.78),
    ("XOM", "CVX", 0.92),
    ("JPM", "GS", 0.88),
    ("AMZN", "GOOGL", 0.72),
    ("NVDA", "AMD", 0.80),
    ("KO", "PEP", 0.90),
    ("V", "MA", 0.93),
]

DIVERGENCE_THRESHOLD_PCT = 3.0
STRONG_DIVERGENCE_PCT = 6.0


class CorrelationMapModule:
    module_name = "Correlation Map"
    weight = 0.15

    def __init__(self, data_feeds: Any = None, ollama_brain: Any = None):
        self.data_feeds = data_feeds
        self.ollama = ollama_brain
        self._price_history: Dict[str, List[float]] = {}

    async def analyze(self) -> Dict[str, Any]:
        try:
            symbols = set()
            for a, b, _ in CORRELATED_PAIRS:
                symbols.add(a)
                symbols.add(b)

            prices: Dict[str, Dict[str, Any]] = {}
            for sym in symbols:
                try:
                    data = await self.data_feeds.get_stock_data(sym)
                    if data.get("simulated"):
                        data = self._enrich_simulated(sym, data)
                    prices[sym] = data
                except Exception as exc:
                    logger.debug("correlation fetch %s: %s", sym, exc)

            anomalies: List[Dict[str, Any]] = []
            normalization_trades: List[Dict[str, Any]] = []
            pair_statuses: List[Dict[str, Any]] = []

            for sym_a, sym_b, expected_corr in CORRELATED_PAIRS:
                if sym_a not in prices or sym_b not in prices:
                    continue

                close_a = float(prices[sym_a].get("close", 0) or 0)
                close_b = float(prices[sym_b].get("close", 0) or 0)
                prev_a = float(prices[sym_a].get("prev_close", close_a) or close_a)
                prev_b = float(prices[sym_b].get("prev_close", close_b) or close_b)

                ret_a = ((close_a - prev_a) / prev_a * 100) if prev_a else 0.0
                ret_b = ((close_b - prev_b) / prev_b * 100) if prev_b else 0.0
                divergence = abs(ret_a - ret_b)

                self._update_history(sym_a, close_a)
                self._update_history(sym_b, close_b)
                rolling_corr = self._rolling_correlation(sym_a, sym_b)
                corr_decay = expected_corr - rolling_corr if rolling_corr is not None else 0.0

                pair_status = {
                    "pair": f"{sym_a}/{sym_b}",
                    "expected_corr": expected_corr,
                    "rolling_corr": round(rolling_corr, 3) if rolling_corr is not None else None,
                    "return_a_pct": round(ret_a, 3),
                    "return_b_pct": round(ret_b, 3),
                    "divergence_pct": round(divergence, 3),
                    "corr_decay": round(corr_decay, 3),
                }
                pair_statuses.append(pair_status)

                is_anomaly = divergence >= DIVERGENCE_THRESHOLD_PCT or corr_decay > 0.20

                if is_anomaly:
                    severity = "strong" if divergence >= STRONG_DIVERGENCE_PCT or corr_decay > 0.35 else "moderate"
                    anomalies.append({
                        **pair_status,
                        "severity": severity,
                        "signal": "correlation_breakdown",
                    })

                    if ret_a > ret_b:
                        long_sym, short_sym = sym_b, sym_a
                    else:
                        long_sym, short_sym = sym_a, sym_b

                    normalization_trades.append({
                        "long": long_sym,
                        "short": short_sym,
                        "divergence_pct": round(divergence, 3),
                        "expected_normalization_pct": round(divergence * 0.6, 3),
                        "severity": severity,
                    })

            confidence = min(0.90, 0.45 + len(anomalies) * 0.12 + len(pair_statuses) * 0.02)
            has_strong = any(a["severity"] == "strong" for a in anomalies)

            ideas = [
                {
                    "symbol": t["long"],
                    "direction": "long",
                    "reason": f"Pair trade: long {t['long']}/short {t['short']} – {t['divergence_pct']}% divergence",
                    "size_hint": "small" if t["severity"] == "moderate" else "medium",
                }
                for t in normalization_trades
            ]

            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "pairs_analyzed": len(pair_statuses),
                "pair_statuses": pair_statuses,
                "anomalies": anomalies,
                "normalization_trades": normalization_trades,
                "confidence": round(confidence, 3),
                "action": "trade" if has_strong else "monitor",
                "ideas": ideas,
            }
        except Exception as exc:
            logger.error("CorrelationMapModule.analyze failed: %s", exc, exc_info=True)
            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "pairs_analyzed": 0,
                "anomalies": [],
                "normalization_trades": [],
                "confidence": 0.0,
                "action": "monitor",
                "error": str(exc),
            }

    def _update_history(self, symbol: str, price: float) -> None:
        hist = self._price_history.setdefault(symbol, [])
        hist.append(price)
        if len(hist) > 30:
            self._price_history[symbol] = hist[-30:]

    def _rolling_correlation(self, sym_a: str, sym_b: str) -> float | None:
        ha = self._price_history.get(sym_a, [])
        hb = self._price_history.get(sym_b, [])
        n = min(len(ha), len(hb))
        if n < 3:
            return None
        a_slice = ha[-n:]
        b_slice = hb[-n:]
        mean_a = sum(a_slice) / n
        mean_b = sum(b_slice) / n
        cov = sum((a_slice[i] - mean_a) * (b_slice[i] - mean_b) for i in range(n)) / n
        std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a_slice) / n)
        std_b = math.sqrt(sum((x - mean_b) ** 2 for x in b_slice) / n)
        if std_a == 0 or std_b == 0:
            return 0.0
        return max(-1.0, min(1.0, cov / (std_a * std_b)))

    @staticmethod
    def _enrich_simulated(symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        base = data.get("close", 100.0)
        seed = hash(symbol + datetime.now().strftime("%Y%m%d%H"))
        rng = random.Random(seed)
        close = base * rng.uniform(0.93, 1.07)
        prev = close * rng.uniform(0.95, 1.05)
        return {**data, "close": round(close, 2), "prev_close": round(prev, 2)}
