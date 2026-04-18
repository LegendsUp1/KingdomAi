"""
Unusual options / capital flow scan (Polygon). Internal telemetry only — no user alerts.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.kingdom_event_names import CAPITAL_FLOW_RESULT, METACOGNITION_UPDATE, REQUEST_CAPITAL_FLOW_SCAN, TASK_START

logger = logging.getLogger("kingdom_ai.capital_flow")


class CapitalFlowProcessor:
    def __init__(self, event_bus: Any, api_keys: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
        self.event_bus = event_bus
        self.api_keys = api_keys or {}
        self.config = config or {}
        self._polygon_key = None
        p = self.api_keys.get("polygon") or self.api_keys.get("polygon_io")
        if isinstance(p, dict):
            self._polygon_key = p.get("api_key")
        elif isinstance(p, str):
            self._polygon_key = p
        if event_bus:
            event_bus.subscribe(REQUEST_CAPITAL_FLOW_SCAN, self._on_scan_request)
            event_bus.subscribe(TASK_START, self._on_task_start)

    def _on_scan_request(self, data: Any) -> None:
        ticker = "SPY"
        if isinstance(data, dict):
            ticker = data.get("ticker") or data.get("symbol") or ticker
        elif isinstance(data, str) and data:
            ticker = data
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.scan_and_process(ticker))
            else:
                loop.run_until_complete(self.scan_and_process(ticker))
        except RuntimeError:
            asyncio.run(self.scan_and_process(ticker))

    def _on_task_start(self, data: Any) -> None:
        if not isinstance(data, str):
            return
        low = data.lower()
        if any(k in low for k in ("option", "flow", "capital", "unusual")):
            self._on_scan_request({"ticker": "SPY"})

    async def scan_and_process(self, ticker: str = "SPY", lookback_minutes: int = 15) -> Dict[str, Any]:
        flow_data = await self._fetch_options_flow(ticker)
        conviction = self._score_flow(flow_data)
        result = {
            "ticker": ticker,
            "conviction_score": conviction,
            "contracts": len(flow_data),
            "timestamp": datetime.now().isoformat(),
        }
        if self.event_bus:
            try:
                self.event_bus.publish(CAPITAL_FLOW_RESULT, {"internal": True, **result})
                self.event_bus.publish(METACOGNITION_UPDATE, ("CAPITAL_FLOW", result))
            except Exception as e:
                logger.debug("capital flow publish: %s", e)
        return result

    async def _fetch_options_flow(self, ticker: str) -> List[Dict[str, Any]]:
        if not self._polygon_key:
            logger.debug("CapitalFlowProcessor: no Polygon key; empty flow.")
            return []
        try:
            import aiohttp

            url = f"https://api.polygon.io/v3/snapshot/options/{ticker}"
            params = {"apiKey": self._polygon_key, "limit": 100}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    results = data.get("results") or []
                    out = []
                    for opt in results:
                        lq = opt.get("last_quote") or {}
                        lt = opt.get("last_trade") or {}
                        ask = float(lq.get("ask") or 0)
                        sz = float((lt.get("size") or 0))
                        if ask > 0 and sz > 10:
                            out.append(opt)
                    return out[:50]
        except Exception as e:
            logger.debug("_fetch_options_flow: %s", e)
        return []

    def _score_flow(self, flow_data: List[Dict[str, Any]]) -> float:
        if not flow_data:
            return 0.0
        scores = []
        for opt in flow_data:
            lq = opt.get("last_quote") or {}
            lt = opt.get("last_trade") or {}
            a = float(lq.get("ask") or 0)
            s = float(lt.get("size") or 0)
            if a > 0 and s > 0:
                scores.append(a * s)
        if not scores:
            return 0.0
        return float(sum(scores) / len(scores)) / 1000.0
