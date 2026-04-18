"""Initialize MemPalace subsystems."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("kingdom_ai.mempalace_setup")


def initialize_mempalace(event_bus: Any) -> Dict[str, Any]:
    from components.memory_persistence_layer import MemoryPersistenceLayer
    from components.memory_palace_manager import MemoryPalaceManager
    from components.mempalace_bridge import MemPalaceBridge

    persistence = MemoryPersistenceLayer()
    palace = MemoryPalaceManager()
    bridge = MemPalaceBridge(event_bus, persistence, palace)
    return {"persistence": persistence, "palace": palace, "bridge": bridge}
