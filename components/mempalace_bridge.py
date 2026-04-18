"""MemPalace bridge — event-driven read/write."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from core.kingdom_event_names import MEMORY_READ_REQUEST, MEMORY_WRITE_REQUEST

logger = logging.getLogger("kingdom_ai.mempalace_bridge")


class MemPalaceBridge:
    def __init__(self, event_bus: Any, persistence: Any, palace: Any):
        self.event_bus = event_bus
        self.persistence = persistence
        self.palace = palace
        if event_bus:
            event_bus.subscribe(MEMORY_WRITE_REQUEST, self._on_write)
            event_bus.subscribe(MEMORY_READ_REQUEST, self._on_read)

    def _on_write(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        self.persistence.write_memory(
            str(data.get("key", "")), str(data.get("value", "")), data.get("metadata")
        )

    def _on_read(self, data: Any) -> None:
        q = data.get("query", "") if isinstance(data, dict) else str(data)
        self.persistence.read_memory(q)

    def write_memory(self, key: str, value: str) -> str:
        return self.persistence.write_memory(key, value)

    def read_memory(self, query: str, top_k: int = 5):
        return self.persistence.read_memory(query, top_k)
