"""
Master orchestrator v3 — coordinates subsystems via the event bus (telemetry only).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from core.kingdom_event_names import (
    BRAIN_QUERY,
    CREATOR_ELEMENT_ADD,
    CREATOR_RENDER,
    MEMORY_READ_REQUEST,
    MEMORY_WRITE_REQUEST,
    METACOGNITION_UPDATE,
    TASK_START,
)

logger = logging.getLogger("kingdom_ai.master_orchestrator_v3")


class MasterOrchestratorV3:
    def __init__(self, event_bus: Any, config: Optional[Dict[str, Any]] = None):
        self.event_bus = event_bus
        self.config = config or {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._channels: List[str] = [
            BRAIN_QUERY,
            TASK_START,
            METACOGNITION_UPDATE,
            CREATOR_RENDER,
            CREATOR_ELEMENT_ADD,
            MEMORY_WRITE_REQUEST,
            MEMORY_READ_REQUEST,
        ]

    async def initialize(self) -> None:
        if self.event_bus:
            for ch in self._channels:
                try:
                    self.event_bus.subscribe(ch, self._noop_handler)
                except Exception:
                    pass
        logger.info("MasterOrchestratorV3 initialized (passive subscriptions)")

    def _noop_handler(self, *args: Any, **kwargs: Any) -> None:
        return

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        interval = float(self.config.get("heartbeat_interval_seconds", 60))
        self._task = asyncio.create_task(self._heartbeat(interval))

    async def _heartbeat(self, interval: float) -> None:
        while self._running:
            try:
                if self.event_bus:
                    self.event_bus.publish(
                        METACOGNITION_UPDATE,
                        ("ORCHESTRATOR", {"version": 3, "internal": True}),
                    )
            except Exception:
                pass
            await asyncio.sleep(interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
