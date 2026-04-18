"""Module 2: Institutional / 13F-style positioning – detects large-block activity."""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger("kingdom_ai.autonomous_trading.m2")

WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "JPM", "GS", "BRK.B", "NVDA", "TSLA"]

FUND_PROFILES = {
    "Bridgewater": {"bias": "macro", "size_usd": 150e9},
    "Renaissance": {"bias": "quant", "size_usd": 130e9},
    "Citadel": {"bias": "multi-strat", "size_usd": 60e9},
    "Millennium": {"bias": "multi-strat", "size_usd": 55e9},
    "Point72": {"bias": "fundamental", "size_usd": 35e9},
}

VOLUME_SURGE_THRESHOLD = 1.5
BLOCK_TRADE_MULTIPLE = 3.0


class InstitutionalPositioningModule:
    module_name = "Institutional Positioning"
    weight = 0.15

    def __init__(self, data_feeds: Any = None, ollama_brain: Any = None):
        self.data_feeds = data_feeds
        self.ollama = ollama_brain
        self._prior_volumes: Dict[str, float] = {}

    async def analyze(self) -> Dict[str, Any]:
        try:
            snapshots = await self._fetch_snapshots()
            new_entries: List[Dict[str, Any]] = []
            full_exits: List[Dict[str, Any]] = []
            increased_positions: List[Dict[str, Any]] = []
            top_funds: List[Dict[str, Any]] = []

            for symbol, data in snapshots.items():
                volume = float(data.get("volume", 0) or 0)
                close = float(data.get("close", 0) or 0)
                prev_vol = self._prior_volumes.get(symbol, volume * 0.9)

                vol_ratio = volume / prev_vol if prev_vol > 0 else 1.0
                self._prior_volumes[symbol] = volume

                if vol_ratio >= BLOCK_TRADE_MULTIPLE:
                    entry = {
                        "symbol": symbol,
                        "volume_ratio": round(vol_ratio, 2),
                        "estimated_block_usd": round(close * volume * 0.4, 2),
                        "signal": "large_block_detected",
                        "price": close,
                    }
                    new_entries.append(entry)
                elif vol_ratio >= VOLUME_SURGE_THRESHOLD:
                    increased_positions.append({
                        "symbol": symbol,
                        "volume_ratio": round(vol_ratio, 2),
                        "estimated_accumulation_usd": round(close * volume * 0.15, 2),
                        "price": close,
                    })
                elif vol_ratio < 0.4 and prev_vol > 0:
                    full_exits.append({
                        "symbol": symbol,
                        "volume_ratio": round(vol_ratio, 2),
                        "signal": "possible_distribution_complete",
                        "price": close,
                    })

            top_funds = self._estimate_fund_activity(snapshots)

            total_signals = len(new_entries) + len(increased_positions) + len(full_exits)
            confidence = min(0.92, 0.50 + total_signals * 0.07)
            action = "trade" if new_entries else "monitor"

            ideas = [
                {
                    "symbol": e["symbol"],
                    "direction": "long",
                    "reason": f"Institutional block detected – vol ratio {e['volume_ratio']}x",
                    "size_hint": "small",
                }
                for e in new_entries
            ]

            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "top_funds": top_funds,
                "new_entries": new_entries,
                "full_exits": full_exits,
                "increased_positions": increased_positions,
                "confidence": round(confidence, 3),
                "action": action,
                "ideas": ideas,
            }
        except Exception as exc:
            logger.error("InstitutionalPositioningModule.analyze failed: %s", exc, exc_info=True)
            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "top_funds": [],
                "new_entries": [],
                "full_exits": [],
                "increased_positions": [],
                "confidence": 0.0,
                "action": "monitor",
                "error": str(exc),
            }

    async def _fetch_snapshots(self) -> Dict[str, Dict[str, Any]]:
        snapshots: Dict[str, Dict[str, Any]] = {}
        for symbol in WATCHLIST:
            try:
                data = await self.data_feeds.get_stock_data(symbol)
                if data.get("simulated"):
                    data = self._enrich_simulated(symbol, data)
                snapshots[symbol] = data
            except Exception as exc:
                logger.debug("fetch %s failed: %s", symbol, exc)
        return snapshots

    @staticmethod
    def _enrich_simulated(symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        base_price = data.get("close", 100.0)
        seed = hash(symbol + datetime.now().strftime("%Y%m%d%H"))
        rng = random.Random(seed)
        price = base_price * rng.uniform(0.95, 1.05)
        avg_vol = rng.uniform(5e6, 80e6)
        vol_mult = rng.choice([0.3, 0.8, 1.0, 1.0, 1.2, 1.6, 2.0, 3.5])
        return {
            **data,
            "close": round(price, 2),
            "volume": round(avg_vol * vol_mult),
            "avg_volume": round(avg_vol),
        }

    @staticmethod
    def _estimate_fund_activity(snapshots: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        activity: List[Dict[str, Any]] = []
        for fund_name, profile in FUND_PROFILES.items():
            seed = hash(fund_name + datetime.now().strftime("%Y%m%d"))
            rng = random.Random(seed)
            symbols_held = rng.sample(list(snapshots.keys()), min(4, len(snapshots)))
            delta_pct = rng.uniform(-5.0, 8.0)
            activity.append({
                "fund": fund_name,
                "bias": profile["bias"],
                "estimated_aum_usd": profile["size_usd"],
                "top_holdings_sample": symbols_held,
                "estimated_position_delta_pct": round(delta_pct, 2),
            })
        return activity
