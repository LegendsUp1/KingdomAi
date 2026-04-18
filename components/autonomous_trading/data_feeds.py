"""REST/WebSocket data feeds: Polygon, Binance, OANDA; degrades without API keys."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.autonomous_trading.data_feeds")


class DataFeedManager:
    def __init__(self, api_keys: Dict[str, Any], simulation_mode: bool = True):
        self.api_keys = api_keys or {}
        self.simulation_mode = simulation_mode
        self._cache: Dict[str, Any] = {}
        self._polygon_key = self._extract_key("polygon", "polygon_io")
        self._oanda_key = self._extract_key("oanda", "oanda")
        self._oanda_account = None
        o = self.api_keys.get("oanda")
        if isinstance(o, dict):
            self._oanda_account = o.get("account_id")

    def _extract_key(self, *names: str) -> Optional[str]:
        for n in names:
            v = self.api_keys.get(n)
            if isinstance(v, dict) and v.get("api_key"):
                return str(v["api_key"])
            if isinstance(v, str) and v:
                return v
        return None

    async def initialize(self) -> None:
        if not self._polygon_key:
            logger.info("DataFeedManager: Polygon key absent; simulation mode friendly.")

    async def get_stock_data(self, symbol: str, timeframe: str = "1min") -> Dict[str, Any]:
        if self.simulation_mode or not self._polygon_key:
            return {"symbol": symbol, "simulated": True, "close": 100.0}
        try:
            import aiohttp

            url = f"https://api.polygon.io/v1/open-close/{symbol}/{date.today().isoformat()}"
            params = {"apiKey": self._polygon_key}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._cache[f"stock_{symbol}"] = data
                        return data
        except Exception as e:
            logger.debug("get_stock_data: %s", e)
        return {"symbol": symbol, "simulated": True, "close": 100.0}

    async def get_options_data(self, symbol: str) -> Any:
        if self.simulation_mode or not self._polygon_key:
            return []
        try:
            import aiohttp

            url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
            params = {"apiKey": self._polygon_key, "limit": 50}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("results") or []
        except Exception as e:
            logger.debug("get_options_data: %s", e)
        return []

    async def get_crypto_data(self, symbol: str) -> Dict[str, Any]:
        try:
            import aiohttp

            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.debug("get_crypto_data: %s", e)
        return {"symbol": symbol, "simulated": True, "lastPrice": "0"}

    async def get_forex_data(self, pair: str) -> Any:
        if not self._oanda_key or not self._oanda_account:
            return []
        try:
            import aiohttp

            url = (
                f"https://api-fxtrade.oanda.com/v3/accounts/{self._oanda_account}/instruments/"
                f"{pair}/candles"
            )
            headers = {"Authorization": f"Bearer {self._oanda_key}"}
            params = {"count": 50, "granularity": "M1"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("candles") or []
        except Exception as e:
            logger.debug("get_forex_data: %s", e)
        return []

    async def stream_market_data(self, symbol: str, callback: Callable[..., Any]) -> None:
        if self.simulation_mode or not self._polygon_key:
            return
        try:
            import websockets

            uri = "wss://socket.polygon.io/stocks"
            async with websockets.connect(uri, ping_interval=20) as ws:
                await ws.send(json.dumps({"action": "auth", "params": self._polygon_key}))
                await ws.send(json.dumps({"action": "subscribe", "params": f"A.{symbol}"}))
                async for message in ws:
                    data = json.loads(message)
                    if __import__("asyncio").iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
        except Exception as e:
            logger.debug("stream_market_data: %s", e)
