"""Module 7: Short squeeze detection – screens for stocks with squeeze potential."""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger("kingdom_ai.autonomous_trading.m7")

SQUEEZE_WATCHLIST = {
    "GME": {"avg_short_interest_pct": 22.0, "float_shares_m": 305},
    "AMC": {"avg_short_interest_pct": 18.0, "float_shares_m": 516},
    "BBBY": {"avg_short_interest_pct": 35.0, "float_shares_m": 80},
    "CVNA": {"avg_short_interest_pct": 28.0, "float_shares_m": 105},
    "BYND": {"avg_short_interest_pct": 32.0, "float_shares_m": 63},
    "SPCE": {"avg_short_interest_pct": 25.0, "float_shares_m": 260},
    "PLTR": {"avg_short_interest_pct": 8.0, "float_shares_m": 2060},
    "RIVN": {"avg_short_interest_pct": 14.0, "float_shares_m": 900},
    "LCID": {"avg_short_interest_pct": 12.0, "float_shares_m": 1800},
    "SOFI": {"avg_short_interest_pct": 10.0, "float_shares_m": 900},
}

HIGH_SI_THRESHOLD = 20.0
VOLUME_SPIKE_THRESHOLD = 2.0
DAYS_TO_COVER_THRESHOLD = 3.0
SQUEEZE_SCORE_THRESHOLD = 0.6


class ShortSqueezeModule:
    module_name = "Short Squeeze"
    weight = 0.10

    def __init__(self, data_feeds: Any = None, ollama_brain: Any = None):
        self.data_feeds = data_feeds
        self.ollama = ollama_brain
        self._prior_prices: Dict[str, float] = {}

    async def analyze(self) -> Dict[str, Any]:
        try:
            candidates: List[Dict[str, Any]] = []
            all_screened: List[Dict[str, Any]] = []

            for symbol, profile in SQUEEZE_WATCHLIST.items():
                try:
                    data = await self.data_feeds.get_stock_data(symbol)
                    if data.get("simulated"):
                        data = self._enrich_simulated(symbol, data, profile)
                except Exception as exc:
                    logger.debug("squeeze fetch %s: %s", symbol, exc)
                    continue

                close = float(data.get("close", 0) or 0)
                prev_close = float(data.get("prev_close", close) or close)
                volume = float(data.get("volume", 0) or 0)
                avg_volume = float(data.get("avg_volume", volume) or volume)

                price_change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0.0
                vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0

                short_interest = self._estimate_short_interest(symbol, profile, data)
                days_to_cover = self._calc_days_to_cover(profile, avg_volume, close)

                squeeze_score = self._compute_squeeze_score(
                    short_interest, vol_ratio, price_change_pct, days_to_cover
                )

                prior = self._prior_prices.get(symbol)
                momentum_building = (
                    prior is not None and close > prior and price_change_pct > 0
                )
                self._prior_prices[symbol] = close

                entry = {
                    "symbol": symbol,
                    "price": round(close, 2),
                    "price_change_pct": round(price_change_pct, 2),
                    "volume": round(volume),
                    "volume_ratio": round(vol_ratio, 2),
                    "short_interest_pct": round(short_interest, 2),
                    "days_to_cover": round(days_to_cover, 2),
                    "squeeze_score": round(squeeze_score, 3),
                    "momentum_building": momentum_building,
                }
                all_screened.append(entry)

                if squeeze_score >= SQUEEZE_SCORE_THRESHOLD:
                    entry["signal"] = "squeeze_candidate"
                    candidates.append(entry)

            candidates.sort(key=lambda x: x["squeeze_score"], reverse=True)
            all_screened.sort(key=lambda x: x["squeeze_score"], reverse=True)

            hot_candidates = [c for c in candidates if c["squeeze_score"] >= 0.8]
            confidence = min(0.90, 0.40 + len(candidates) * 0.10 + len(hot_candidates) * 0.08)

            ideas = [
                {
                    "symbol": c["symbol"],
                    "direction": "long",
                    "reason": (
                        f"Squeeze score {c['squeeze_score']:.2f} – "
                        f"SI {c['short_interest_pct']:.1f}%, "
                        f"DTC {c['days_to_cover']:.1f}, "
                        f"vol spike {c['volume_ratio']:.1f}x"
                        f"{' [momentum building]' if c.get('momentum_building') else ''}"
                    ),
                    "size_hint": "small",
                }
                for c in candidates[:5]
            ]

            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "candidates": candidates,
                "total_screened": len(all_screened),
                "all_screened": all_screened,
                "confidence": round(confidence, 3),
                "action": "trade" if hot_candidates else "monitor",
                "ideas": ideas,
            }
        except Exception as exc:
            logger.error("ShortSqueezeModule.analyze failed: %s", exc, exc_info=True)
            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "candidates": [],
                "total_screened": 0,
                "confidence": 0.0,
                "action": "monitor",
                "error": str(exc),
            }

    @staticmethod
    def _estimate_short_interest(
        symbol: str, profile: Dict[str, Any], data: Dict[str, Any]
    ) -> float:
        base_si = profile["avg_short_interest_pct"]
        close = float(data.get("close", 100) or 100)
        prev = float(data.get("prev_close", close) or close)
        price_drop = ((prev - close) / prev * 100) if prev else 0.0
        si_adjustment = price_drop * 0.3
        seed = hash(symbol + datetime.now().strftime("%Y%m%d"))
        noise = random.Random(seed).uniform(-2.0, 2.0)
        return max(1.0, base_si + si_adjustment + noise)

    @staticmethod
    def _calc_days_to_cover(
        profile: Dict[str, Any], avg_volume: float, price: float
    ) -> float:
        float_shares = profile["float_shares_m"] * 1e6
        si_ratio = profile["avg_short_interest_pct"] / 100.0
        shares_short = float_shares * si_ratio
        if avg_volume <= 0:
            return 99.0
        return shares_short / avg_volume

    @staticmethod
    def _compute_squeeze_score(
        short_interest: float,
        vol_ratio: float,
        price_change_pct: float,
        days_to_cover: float,
    ) -> float:
        si_score = min(1.0, short_interest / 40.0)
        vol_score = min(1.0, max(0.0, (vol_ratio - 1.0) / 3.0))
        price_score = min(1.0, max(0.0, price_change_pct / 15.0))
        dtc_score = min(1.0, days_to_cover / 8.0)

        score = (si_score * 0.35) + (vol_score * 0.25) + (price_score * 0.20) + (dtc_score * 0.20)
        return min(1.0, score)

    @staticmethod
    def _enrich_simulated(
        symbol: str, data: Dict[str, Any], profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        base = data.get("close", 100.0)
        seed = hash(symbol + datetime.now().strftime("%Y%m%d%H"))
        rng = random.Random(seed)
        close = base * rng.uniform(0.85, 1.15)
        prev = close * rng.uniform(0.92, 1.08)
        avg_vol = profile["float_shares_m"] * 1e6 * rng.uniform(0.005, 0.02)
        vol_mult = rng.choice([0.5, 0.8, 1.0, 1.0, 1.3, 1.8, 2.5, 4.0])
        return {
            **data,
            "close": round(close, 2),
            "prev_close": round(prev, 2),
            "volume": round(avg_vol * vol_mult),
            "avg_volume": round(avg_vol),
        }
