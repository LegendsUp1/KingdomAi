"""Chemistry / manufacturing orchestration (creator events)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from core.kingdom_event_names import CREATOR_CHEMISTRY_ANALYZE, CREATOR_CHEMISTRY_VISUALIZE

logger = logging.getLogger("kingdom_ai.chemistry_manufacturing")


class ChemistryManufacturingOrchestrator:
    def __init__(self, event_bus: Any):
        self.event_bus = event_bus
        if event_bus:
            event_bus.subscribe(CREATOR_CHEMISTRY_ANALYZE, self._on_analyze)
            event_bus.subscribe(CREATOR_CHEMISTRY_VISUALIZE, self._on_visualize)

    def _on_analyze(self, data: Any) -> None:
        logger.debug("Chemistry analyze (internal): %s", str(data)[:200])

    def _on_visualize(self, data: Any) -> None:
        logger.debug("Chemistry visualize (internal): %s", str(data)[:200])

    def run_pipeline(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "spec_keys": list(spec.keys()), "internal": True}
