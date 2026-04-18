"""
Kingdom AI repository root and platform detection.

Use this instead of hard-coded ``/mnt/c/...`` or WSL-only paths so native Linux works.
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional


@lru_cache(maxsize=1)
def get_repo_root() -> Path:
    """Return the repository root (directory containing ``core/`` and ``redis_voice_service.py``)."""
    return Path(__file__).resolve().parent.parent


def resolve_repo_path(*parts: str) -> Path:
    """Path under the repo root."""
    return get_repo_root().joinpath(*parts)


def is_wsl() -> bool:
    """True when running under Windows Subsystem for Linux."""
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", encoding="utf-8", errors="ignore") as f:
                v = f.read().lower()
            return "microsoft" in v or "wsl" in v
    except OSError:
        pass
    return False


def is_native_linux() -> bool:
    """True for Linux kernel and not WSL (e.g. bare-metal Ubuntu)."""
    return sys.platform.startswith("linux") and not is_wsl()


def wsl_windows_path_if_exists(win_path: str) -> Optional[Path]:
    """If ``win_path`` exists under ``/mnt/<drive>/``, return that Path; else None."""
    if not win_path or len(win_path) < 3 or win_path[1] != ":":
        return None
    drive = win_path[0].lower()
    rest = win_path[2:].lstrip("\\/").replace("\\", "/")
    candidate = Path(f"/mnt/{drive}") / rest
    if candidate.is_file():
        return candidate
    return None
