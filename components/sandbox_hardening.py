"""Pattern-based safety checks for task/network strings (internal logging)."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from core.kingdom_event_names import REQUEST_NETWORK_ACTION, REQUEST_SYSTEM_ACCESS, SANDBOX_ALERT, TASK_START

logger = logging.getLogger("kingdom_ai.sandbox_hardening")


class SandboxHardener:
    def __init__(self, event_bus: Any, metacognition_core: Any = None):
        self.event_bus = event_bus
        self.core = metacognition_core
        self._patterns: List[str] = [
            r"ssh\s+-R",
            r"reverse.*tunnel",
            r"ngrok",
            r"chisel",
            r"gpu.*hijack",
        ]
        if event_bus:
            event_bus.subscribe(TASK_START, self._on_task)
            event_bus.subscribe(REQUEST_NETWORK_ACTION, self._on_network)
            event_bus.subscribe(REQUEST_SYSTEM_ACCESS, self._on_system)

    def _blocked(self, text: str) -> bool:
        for p in self._patterns:
            if re.search(p, text, re.IGNORECASE):
                return True
        return False

    def _on_task(self, data: Any) -> None:
        if not isinstance(data, str):
            return
        if self._blocked(data):
            logger.warning("SandboxHardener: blocked task pattern")
            if self.event_bus:
                try:
                    self.event_bus.publish(SANDBOX_ALERT, {"reason": "pattern_match", "internal": True})
                except Exception:
                    pass

    def _on_network(self, data: Any) -> None:
        s = str(data)
        if self._blocked(s):
            if self.event_bus:
                self.event_bus.publish(SANDBOX_ALERT, {"reason": "network", "internal": True})

    def _on_system(self, data: Any) -> None:
        s = str(data)
        if self._blocked(s):
            if self.event_bus:
                self.event_bus.publish(SANDBOX_ALERT, {"reason": "system", "internal": True})

    def get_hardening_status(self) -> Dict[str, Any]:
        return {"patterns": len(self._patterns), "active": True}
