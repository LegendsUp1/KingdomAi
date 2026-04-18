"""Lightweight JSON-backed memory store (Chroma-compatible path optional)."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("kingdom_ai.memory_persistence")


class MemoryPersistenceLayer:
    def __init__(self, db_path: str = "~/.mempalace/db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.memory_store: Dict[str, Any] = {}
        self._file = self.db_path / "memories.json"
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                self.memory_store = json.loads(self._file.read_text(encoding="utf-8"))
            except Exception:
                self.memory_store = {}

    def _save(self) -> None:
        self._file.write_text(json.dumps(self.memory_store, indent=2, default=str), encoding="utf-8")

    def write_memory(self, key: str, value: str, metadata: Dict[str, Any] | None = None) -> str:
        mid = hashlib.md5(f"{key}:{datetime.now().isoformat()}".encode()).hexdigest()
        self.memory_store[mid] = {
            "key": key,
            "value": value,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._save()
        return mid

    def read_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        q = query.lower()
        hits = []
        for mid, entry in self.memory_store.items():
            blob = f"{entry.get('key','')} {entry.get('value','')}".lower()
            if q in blob or not q:
                hits.append({"id": mid, **entry})
        return hits[:top_k]
