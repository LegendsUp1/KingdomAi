"""Structured halls for memory (wings)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger("kingdom_ai.memory_palace")


class MemoryWing(Enum):
    KNOWLEDGE = "knowledge"
    TRADING = "trading"
    CODING = "coding"


@dataclass
class MemoryHall:
    name: str
    wing: MemoryWing
    memories: List[Dict[str, Any]] = field(default_factory=list)


class MemoryPalaceManager:
    def __init__(self) -> None:
        self.halls: Dict[str, MemoryHall] = {}
        for w in MemoryWing:
            hid = f"{w.value}_main"
            self.halls[hid] = MemoryHall(name="main", wing=w)

    def store_in_hall(self, wing: MemoryWing, hall_name: str, memory: Dict[str, Any]) -> bool:
        hid = f"{wing.value}_{hall_name}"
        if hid not in self.halls:
            self.halls[hid] = MemoryHall(name=hall_name, wing=wing)
        memory["stored_at"] = datetime.now().isoformat()
        self.halls[hid].memories.append(memory)
        return True

    def search_palace(self, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        out = []
        for hall in self.halls.values():
            for m in hall.memories:
                if q in str(m).lower():
                    out.append({"hall": hall.name, "wing": hall.wing.value, "memory": m})
        return out

    def get_palace_structure(self) -> Dict[str, Any]:
        return {
            w.value: [{"name": h.name, "count": len(h.memories)} for h in self.halls.values() if h.wing == w]
            for w in MemoryWing
        }
