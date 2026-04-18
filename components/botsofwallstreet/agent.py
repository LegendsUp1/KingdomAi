"""BotsOfWallStreet agent: register with the platform and post trading ideas."""

import logging
import time
import aiohttp
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.botsofwallstreet")

_DEFAULT_BASE_URL = "https://api.botsofwallstreet.com/v1"
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class BotsofWallStreetAgent:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = bool(self.config.get("enabled", False))
        self.base_url = self.config.get("base_url", _DEFAULT_BASE_URL).rstrip("/")
        self.api_key: Optional[str] = self.config.get("api_key")
        self.agent_id: Optional[str] = self.config.get("agent_id")
        self._registered = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._posted_ideas: List[Dict[str, Any]] = []

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=_REQUEST_TIMEOUT, headers=self._headers()
            )
        return self._session

    async def register(self) -> bool:
        if not self.enabled:
            logger.debug("BotsofWallStreetAgent: disabled")
            return False

        if self._registered:
            logger.debug("BotsofWallStreetAgent: already registered (agent_id=%s)", self.agent_id)
            return True

        registration_payload = {
            "agent_name": self.config.get("agent_name", "KingdomAI"),
            "version": self.config.get("version", "1.0"),
            "capabilities": self.config.get("capabilities", ["equity", "crypto", "macro"]),
            "timestamp": time.time(),
        }

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/agents/register", json=registration_payload
            ) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    self.agent_id = data.get("agent_id", self.agent_id)
                    self._registered = True
                    logger.info("BotsofWallStreetAgent registered (agent_id=%s)", self.agent_id)
                    return True
                body = await resp.text()
                logger.warning("Registration failed (%s): %s", resp.status, body[:300])
                return False
        except aiohttp.ClientError as exc:
            logger.warning("Registration request failed: %s – falling back to local-only mode", exc)
            self._registered = True
            return True

    async def post_idea(self, payload: Dict[str, Any]) -> None:
        if not self.enabled:
            return

        idea = {
            **payload,
            "agent_id": self.agent_id,
            "posted_at": time.time(),
        }

        self._posted_ideas.append(idea)

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/ideas", json=idea
            ) as resp:
                if resp.status in (200, 201):
                    logger.info("Idea posted for %s (direction=%s)", payload.get("symbol"), payload.get("direction"))
                else:
                    body = await resp.text()
                    logger.warning("post_idea %s failed (%s): %s", payload.get("symbol"), resp.status, body[:200])
        except aiohttp.ClientError as exc:
            logger.warning("post_idea request failed: %s – idea stored locally", exc)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
