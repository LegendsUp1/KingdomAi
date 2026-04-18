"""Module 5: Sentiment vs price-action arbitrage – finds mismatches between market mood and fundamentals."""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger("kingdom_ai.autonomous_trading.m5")

SENTIMENT_UNIVERSE = {
    "AAPL": {"sector": "Technology", "base_sentiment": 0.65},
    "TSLA": {"sector": "Consumer Discretionary", "base_sentiment": 0.45},
    "NVDA": {"sector": "Technology", "base_sentiment": 0.75},
    "META": {"sector": "Technology", "base_sentiment": 0.50},
    "AMZN": {"sector": "Consumer Discretionary", "base_sentiment": 0.60},
    "GOOGL": {"sector": "Technology", "base_sentiment": 0.62},
    "JPM": {"sector": "Financials", "base_sentiment": 0.55},
    "XOM": {"sector": "Energy", "base_sentiment": 0.48},
    "DIS": {"sector": "Communication", "base_sentiment": 0.42},
    "BA": {"sector": "Industrials", "base_sentiment": 0.38},
}

MISMATCH_THRESHOLD = 0.25
STRONG_MISMATCH_THRESHOLD = 0.45


class SentimentArbitrageModule:
    module_name = "Sentiment Arbitrage"
    weight = 0.20

    def __init__(self, data_feeds: Any = None, ollama_brain: Any = None):
        self.data_feeds = data_feeds
        self.ollama = ollama_brain

    async def analyze(self) -> Dict[str, Any]:
        try:
            ideas: List[Dict[str, Any]] = []
            all_signals: List[Dict[str, Any]] = []

            for symbol, profile in SENTIMENT_UNIVERSE.items():
                try:
                    data = await self.data_feeds.get_stock_data(symbol)
                    if data.get("simulated"):
                        data = self._enrich_simulated(symbol, data)
                except Exception as exc:
                    logger.debug("sentiment fetch %s: %s", symbol, exc)
                    continue

                close = float(data.get("close", 0) or 0)
                prev_close = float(data.get("prev_close", close) or close)
                volume = float(data.get("volume", 0) or 0)
                avg_volume = float(data.get("avg_volume", volume) or volume)

                price_return = ((close - prev_close) / prev_close) if prev_close else 0.0
                price_signal = max(-1.0, min(1.0, price_return * 10))

                sentiment_score = await self._compute_sentiment(symbol, profile, data)

                mismatch = sentiment_score - price_signal
                abs_mismatch = abs(mismatch)

                vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0
                vol_confirms = vol_ratio > 1.3

                signal = {
                    "symbol": symbol,
                    "sector": profile["sector"],
                    "price": round(close, 2),
                    "price_return_pct": round(price_return * 100, 2),
                    "price_signal": round(price_signal, 3),
                    "sentiment_score": round(sentiment_score, 3),
                    "mismatch": round(mismatch, 3),
                    "volume_ratio": round(vol_ratio, 2),
                    "volume_confirms": vol_confirms,
                }
                all_signals.append(signal)

                if abs_mismatch >= MISMATCH_THRESHOLD:
                    severity = "strong" if abs_mismatch >= STRONG_MISMATCH_THRESHOLD else "moderate"
                    direction = "long" if mismatch > 0 else "short"
                    reason = (
                        f"Sentiment {'bullish' if mismatch > 0 else 'bearish'} "
                        f"({sentiment_score:+.2f}) vs price action ({price_signal:+.2f}) – "
                        f"mismatch {abs_mismatch:.2f}"
                    )
                    if vol_confirms:
                        reason += " [volume confirms]"

                    ideas.append({
                        "symbol": symbol,
                        "direction": direction,
                        "reason": reason,
                        "mismatch_magnitude": round(abs_mismatch, 3),
                        "severity": severity,
                        "size_hint": "medium" if severity == "strong" and vol_confirms else "small",
                    })

            ideas.sort(key=lambda x: x["mismatch_magnitude"], reverse=True)
            strong_ideas = [i for i in ideas if i["severity"] == "strong"]
            confidence = min(0.90, 0.45 + len(ideas) * 0.08 + len(strong_ideas) * 0.05)

            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "signals_scanned": len(all_signals),
                "all_signals": all_signals,
                "ideas": ideas,
                "confidence": round(confidence, 3),
                "action": "trade" if strong_ideas else "monitor",
            }
        except Exception as exc:
            logger.error("SentimentArbitrageModule.analyze failed: %s", exc, exc_info=True)
            return {
                "module": self.module_name,
                "timestamp": datetime.now().isoformat(),
                "signals_scanned": 0,
                "ideas": [],
                "confidence": 0.0,
                "action": "monitor",
                "error": str(exc),
            }

    async def _compute_sentiment(
        self, symbol: str, profile: Dict[str, Any], market_data: Dict[str, Any]
    ) -> float:
        if self.ollama:
            try:
                prompt = (
                    f"Rate the current market sentiment for {symbol} on a scale of -1 (very bearish) "
                    f"to +1 (very bullish). Consider that the stock is in the {profile['sector']} sector "
                    f"and is trading at ${market_data.get('close', 'N/A')}. "
                    f"Reply with ONLY a decimal number."
                )
                response = await self.ollama.generate(prompt)
                text = str(response).strip()
                for token in text.split():
                    try:
                        val = float(token)
                        return max(-1.0, min(1.0, val))
                    except ValueError:
                        continue
            except Exception as exc:
                logger.debug("ollama sentiment for %s: %s", symbol, exc)

        return self._heuristic_sentiment(symbol, profile, market_data)

    @staticmethod
    def _heuristic_sentiment(symbol: str, profile: Dict[str, Any], data: Dict[str, Any]) -> float:
        base = profile["base_sentiment"]
        close = float(data.get("close", 100) or 100)
        prev = float(data.get("prev_close", close) or close)
        price_move = ((close - prev) / prev) if prev else 0.0
        volume = float(data.get("volume", 0) or 0)
        avg_vol = float(data.get("avg_volume", volume) or volume)
        vol_factor = 0.1 if avg_vol > 0 and volume / avg_vol > 1.5 else 0.0

        sentiment = (base - 0.5) * 2
        sentiment += price_move * 3
        sentiment += vol_factor if price_move > 0 else -vol_factor

        seed = hash(symbol + datetime.now().strftime("%Y%m%d%H"))
        noise = random.Random(seed).uniform(-0.15, 0.15)
        return max(-1.0, min(1.0, sentiment + noise))

    @staticmethod
    def _enrich_simulated(symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        base = data.get("close", 100.0)
        seed = hash(symbol + datetime.now().strftime("%Y%m%d%H"))
        rng = random.Random(seed)
        close = base * rng.uniform(0.90, 1.10)
        prev = close * rng.uniform(0.94, 1.06)
        avg_vol = rng.uniform(8e6, 60e6)
        vol = avg_vol * rng.uniform(0.5, 2.5)
        return {
            **data,
            "close": round(close, 2),
            "prev_close": round(prev, 2),
            "volume": round(vol),
            "avg_volume": round(avg_vol),
        }
