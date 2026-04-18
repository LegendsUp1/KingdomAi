"""Load project `config/config.json` and merge with runtime overrides (overrides win)."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("kingdom_ai.config_loader")

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_PATH = _ROOT / "config" / "config.json"


def load_project_config(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or _DEFAULT_PATH
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("config load skipped: %s", e)
    return {}


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        out = copy.deepcopy(base)
        for k, v in override.items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = copy.deepcopy(v)
        return out
    return copy.deepcopy(override)


def merge_config(overrides: Optional[Dict[str, Any]] = None, path: Optional[Path] = None) -> Dict[str, Any]:
    base = load_project_config(path)
    if not overrides:
        return base
    return _deep_merge(base, overrides)
