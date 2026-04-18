"""Creator equipment templates + HUD mapping (event-driven)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.kingdom_event_names import CREATOR_EQUIPMENT_CREATE

logger = logging.getLogger("kingdom_ai.universal_equipment")


class UniversalEquipmentAbstraction:
    def __init__(self, event_bus: Any):
        self.event_bus = event_bus
        self.templates: Dict[str, Dict[str, Any]] = {}
        if event_bus:
            event_bus.subscribe(CREATOR_EQUIPMENT_CREATE, self._on_create)

    def _on_create(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        name = str(data.get("name", "item"))
        self.templates[name] = dict(data)
        logger.debug("Equipment template registered: %s", name)

    def list_templates(self) -> List[str]:
        return sorted(self.templates.keys())

    def map_to_hud(self, equipment_id: str) -> Dict[str, Any]:
        return {"id": equipment_id, "layer": "hud", "internal": True}
