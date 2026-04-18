"""Routes brain prompts through optional Self-Ask expansion (no GUI)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("kingdom_ai.brain_router_self_ask")


class AIBrainRouterWithSelfAsk:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._self_ask = None
        try:
            from utils.self_ask_ai_master import SelfAskAI

            self._self_ask = SelfAskAI(
                model=str(self.config.get("model", "grok-2-latest")),
                api_key=self.config.get("api_key"),
            )
        except Exception as e:
            logger.debug("SelfAsk not loaded: %s", e)

    async def expand_prompt(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        if not self._self_ask or not self.config.get("enabled", False):
            return prompt
        try:
            import asyncio

            return await asyncio.to_thread(self._self_ask.expand, prompt, context)
        except Exception as e:
            logger.debug("expand_prompt: %s", e)
            return prompt
