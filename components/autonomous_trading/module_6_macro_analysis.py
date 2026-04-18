"""Module 6: Macro regime analysis – cross-asset signals to determine economic regime and sector rotation."""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger("kingdom_ai.autonomous_trading.m6")

SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

MACRO_PROXIES = {
    "SPY": "broad_equity",
    "TLT": "long_bonds",
    "GLD": "gold",
    "UUP": "usd_strength",
    "USO": "crude_oil",
}

REGIME_RULES = {
    "risk_on": {"equities": "up", "bonds": "down", "gold": "down", "usd": "flat"},
    "risk_off": {"equities": "down", "bonds": "up", "gold": "up", "usd": "up"},
    "inflationary": {"equities": "flat", "bonds": "down", "gold": "up", "usd": "down"},
    "deflationary": {"equities": "down", "bonds": "up", "gold": "flat", "usd": "up"},
    "stagflation": {"equities": "down", "bonds": "down", "gold": "up", "usd": "flat"},
}


class MacroAnalysisModule:
    module_name = "Macro Analysis"
    weight = 0.15

    def __init__(self, data_feeds: Any = None, ollama_brain: Any = None):
        self.data_feeds = data_feeds
        self.ollama = ollama_brain

    async def analyze(self) -> Dict[str, Any]:
        try:
            proxy_data = await self._fetch_proxies()
            sector_data = await self._fetch_sectors()

            macro_signals = self._compute_macro_signals(proxy_data)
            regime = self._determine_regime(macro_signals)
            sector_rankings = self._rank_sectors(sector_data)
            outperforming = [s for s in sector_rankings if s["relative_strength"] > 0]
            underperforming = [s for s in sector_rankings if s["relative_strength"] <= 0]
            rotation_ideas = self._generate_rotation_ideas(regime, sector_rankings)

            confidence = min(0.88, 0.50 + len(proxy_data) * 0.04 + len(sector_data) * 0.02)
            has_conviction = regime["confidence"] > 0.6 and len(rotation_ideas) > 0

            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "macro_context": {
                    "regime": regime["name"],
                    "regime_confidence": regime["confidence"],
                    "signals": macro_signals,
                },
                "outperforming_sectors": outperforming[:5],
                "underperforming_sectors": underperforming[:5],
                "sector_rankings": sector_rankings,
                "rotation_ideas": rotation_ideas,
                "confidence": round(confidence, 3),
                "action": "trade" if has_conviction else "monitor",
                "ideas": rotation_ideas,
            }
        except Exception as exc:
            logger.error("MacroAnalysisModule.analyze failed: %s", exc, exc_info=True)
            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "macro_context": {"regime": "unknown", "error": str(exc)},
                "outperforming_sectors": [],
                "confidence": 0.0,
                "action": "monitor",
                "error": str(exc),
            }

    async def _fetch_proxies(self) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        for symbol, role in MACRO_PROXIES.items():
            try:
                data = await self.data_feeds.get_stock_data(symbol)
                if data.get("simulated"):
                    data = self._enrich_simulated(symbol, data)
                data["role"] = role
                results[symbol] = data
            except Exception as exc:
                logger.debug("macro proxy %s: %s", symbol, exc)
        return results

    async def _fetch_sectors(self) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        for symbol, sector in SECTOR_ETFS.items():
            try:
                data = await self.data_feeds.get_stock_data(symbol)
                if data.get("simulated"):
                    data = self._enrich_simulated(symbol, data)
                data["sector_name"] = sector
                results[symbol] = data
            except Exception as exc:
                logger.debug("sector %s: %s", symbol, exc)
        return results

    @staticmethod
    def _compute_macro_signals(proxy_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        signals: Dict[str, Any] = {}
        for symbol, data in proxy_data.items():
            close = float(data.get("close", 0) or 0)
            prev = float(data.get("prev_close", close) or close)
            ret = ((close - prev) / prev * 100) if prev else 0.0
            role = data.get("role", symbol)

            if ret > 0.5:
                direction = "up"
            elif ret < -0.5:
                direction = "down"
            else:
                direction = "flat"

            signals[role] = {
                "symbol": symbol,
                "return_pct": round(ret, 3),
                "direction": direction,
                "price": round(close, 2),
            }
        return signals

    @staticmethod
    def _determine_regime(signals: Dict[str, Any]) -> Dict[str, Any]:
        current = {
            "equities": signals.get("broad_equity", {}).get("direction", "flat"),
            "bonds": signals.get("long_bonds", {}).get("direction", "flat"),
            "gold": signals.get("gold", {}).get("direction", "flat"),
            "usd": signals.get("usd_strength", {}).get("direction", "flat"),
        }

        best_regime = "uncertain"
        best_score = 0
        for regime_name, expected in REGIME_RULES.items():
            score = sum(1 for k, v in expected.items() if current.get(k) == v)
            if score > best_score:
                best_score = score
                best_regime = regime_name

        confidence = round(best_score / max(len(current), 1), 2)
        return {"name": best_regime, "confidence": confidence, "observed": current}

    @staticmethod
    def _rank_sectors(sector_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        rankings: List[Dict[str, Any]] = []
        returns = []
        for symbol, data in sector_data.items():
            close = float(data.get("close", 0) or 0)
            prev = float(data.get("prev_close", close) or close)
            ret = ((close - prev) / prev * 100) if prev else 0.0
            returns.append(ret)

        avg_ret = sum(returns) / len(returns) if returns else 0.0

        for (symbol, data), ret in zip(sector_data.items(), returns):
            rankings.append({
                "symbol": symbol,
                "sector": data.get("sector_name", symbol),
                "return_pct": round(ret, 3),
                "relative_strength": round(ret - avg_ret, 3),
                "price": round(float(data.get("close", 0) or 0), 2),
            })

        rankings.sort(key=lambda x: x["relative_strength"], reverse=True)
        return rankings

    @staticmethod
    def _generate_rotation_ideas(
        regime: Dict[str, Any], rankings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        ideas: List[Dict[str, Any]] = []
        regime_name = regime.get("name", "uncertain")

        regime_sector_bias = {
            "risk_on": ["Technology", "Consumer Discretionary"],
            "risk_off": ["Utilities", "Consumer Staples", "Healthcare"],
            "inflationary": ["Energy", "Industrials"],
            "deflationary": ["Utilities", "Healthcare"],
            "stagflation": ["Energy", "Consumer Staples"],
        }
        favored = regime_sector_bias.get(regime_name, [])

        for sector_info in rankings[:3]:
            if sector_info["relative_strength"] > 0.5:
                in_favor = sector_info["sector"] in favored
                ideas.append({
                    "symbol": sector_info["symbol"],
                    "direction": "long",
                    "reason": (
                        f"Sector rotation into {sector_info['sector']} "
                        f"(RS: {sector_info['relative_strength']:+.2f}%, "
                        f"regime: {regime_name}"
                        f"{', regime-aligned' if in_favor else ''})"
                    ),
                    "size_hint": "medium" if in_favor else "small",
                })

        for sector_info in rankings[-2:]:
            if sector_info["relative_strength"] < -1.0:
                ideas.append({
                    "symbol": sector_info["symbol"],
                    "direction": "short",
                    "reason": (
                        f"Sector weakness in {sector_info['sector']} "
                        f"(RS: {sector_info['relative_strength']:+.2f}%, regime: {regime_name})"
                    ),
                    "size_hint": "small",
                })

        return ideas

    @staticmethod
    def _enrich_simulated(symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        base = data.get("close", 100.0)
        seed = hash(symbol + datetime.now().strftime("%Y%m%d%H"))
        rng = random.Random(seed)
        close = base * rng.uniform(0.95, 1.05)
        prev = close * rng.uniform(0.97, 1.03)
        return {**data, "close": round(close, 2), "prev_close": round(prev, 2)}
