"""Canonical version / URL loader.

Reads ``config/version.json`` once and caches the result. Every call site
that used to hardcode ``APP_VERSION = "2.1.0"`` or
``"https://kingdomai.network/..."`` should instead import from this module.

The file has sensible fall-back defaults so a partially-assembled consumer
bundle still boots even if the json is missing.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

_LOG = logging.getLogger(__name__)

_DEFAULTS: Dict[str, Any] = {
    "app_version": "2.2.0",
    "desktop_build": "2026.04",
    "flutter_build": "1.2.0+2",
    "protocol_version": 2,
    "recovery_protocol": 1,
    "landing_page_url": "https://kingdom-ai.netlify.app",
    "support_email": "",
    "pbkdf2_iters": 600000,
    "pbkdf2_iters_max": 1000000,
}


def _candidate_paths():
    here = Path(__file__).resolve()
    yield here.parents[1] / "config" / "version.json"
    yield Path.cwd() / "config" / "version.json"
    yield Path("/etc/kingdom_ai/version.json")


@lru_cache(maxsize=1)
def load() -> Dict[str, Any]:
    data = dict(_DEFAULTS)
    for path in _candidate_paths():
        try:
            if path.exists():
                data.update(json.loads(path.read_text(encoding="utf-8")))
                data["_source_path"] = str(path)
                return data
        except (OSError, json.JSONDecodeError) as exc:
            _LOG.warning("version_info: failed reading %s: %s", path, exc)
    data["_source_path"] = "<defaults>"
    return data


def app_version() -> str:
    return str(load().get("app_version") or _DEFAULTS["app_version"])


def desktop_build() -> str:
    return str(load().get("desktop_build") or _DEFAULTS["desktop_build"])


def flutter_build() -> str:
    return str(load().get("flutter_build") or _DEFAULTS["flutter_build"])


def landing_page_url() -> str:
    return str(load().get("landing_page_url") or _DEFAULTS["landing_page_url"])


def pbkdf2_iters() -> int:
    try:
        value = int(load().get("pbkdf2_iters", _DEFAULTS["pbkdf2_iters"]))
    except (TypeError, ValueError):
        value = _DEFAULTS["pbkdf2_iters"]
    cap = int(_DEFAULTS["pbkdf2_iters_max"])
    try:
        cap = int(load().get("pbkdf2_iters_max", cap))
    except (TypeError, ValueError):
        pass
    return max(100_000, min(value, cap))


__all__ = [
    "load",
    "app_version",
    "desktop_build",
    "flutter_build",
    "landing_page_url",
    "pbkdf2_iters",
]
