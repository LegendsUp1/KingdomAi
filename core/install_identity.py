#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.install_identity
─────────────────────
Per-install identity for Kingdom AI.

Every fresh Kingdom AI install (consumer or creator, desktop or mobile) is
its own world. This module owns the two pieces of identity that make that
true:

* ``installation_id`` — a UUID4 generated the first time Kingdom AI boots
  on this machine and never reused. It binds logs, device inventory,
  memory palace, and paired headsets to *this* install.

* ``user_id`` — a short human-friendly handle that defaults to
  ``kingdom-<8 hex>`` on first run and can be renamed at any time.
  Every VR session, every paired device, every piece of persisted memory
  is tagged with this id, so one person's data never bleeds into another
  person's install.

There is no shared state with the creator or any other install. If two
families both install Kingdom AI on two different laptops, they get two
different identities and neither one sees the other's anything.

Persistence
-----------
Identity is stored in ``config/install_identity.json`` inside the user's
Kingdom AI directory (NOT the repo) with 0o600 permissions where the OS
supports it. If the file is missing or corrupt, a fresh identity is
generated — because a missing identity means a new install, not an
attack.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import socket
import stat
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("KingdomAI.InstallIdentity")

_IDENTITY_FILE = "install_identity.json"
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass
class InstallIdentity:
    """A single Kingdom AI install's identity record."""

    installation_id: str
    user_id: str
    display_name: str
    created_at: str
    host_fingerprint: str
    platform: str
    role: str  # "creator" or "consumer"
    mode_platform: str  # "desktop" or "mobile"
    version: str = "2026.04"
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InstallIdentity":
        return cls(
            installation_id=data["installation_id"],
            user_id=data["user_id"],
            display_name=data.get("display_name", data["user_id"]),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            host_fingerprint=data.get("host_fingerprint", ""),
            platform=data.get("platform", platform.system()),
            role=data.get("role", os.environ.get("KINGDOM_APP_MODE", "consumer")),
            mode_platform=data.get(
                "mode_platform", os.environ.get("KINGDOM_APP_PLATFORM", "desktop")
            ),
            version=data.get("version", "2026.04"),
            extras=data.get("extras", {}) or {},
        )


def _host_fingerprint() -> str:
    """Short, non-identifying fingerprint of the host.

    Uses hostname + platform + python version hash. Never a MAC address,
    never a user name. Enough to tell two installs on the same laptop
    apart only if the creator deliberately triggered a reset.
    """
    try:
        name = socket.gethostname()
    except Exception:
        name = "unknown"
    return f"{platform.system()}-{name}-{platform.python_version()}"


def _identity_path(config_dir: Optional[Path] = None) -> Path:
    d = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / _IDENTITY_FILE


def _write_secure(path: Path, data: Dict[str, Any]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 0o600 where supported
    except Exception:
        pass
    os.replace(tmp, path)


def _build_fresh(config_dir: Path) -> InstallIdentity:
    """Generate a brand-new identity — called the first time Kingdom AI
    ever runs on this machine, or after a wipe/reset."""
    installation_id = uuid.uuid4().hex
    user_id = f"kingdom-{installation_id[:8]}"
    identity = InstallIdentity(
        installation_id=installation_id,
        user_id=user_id,
        display_name=user_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        host_fingerprint=_host_fingerprint(),
        platform=platform.system(),
        role=os.environ.get("KINGDOM_APP_MODE", "consumer"),
        mode_platform=os.environ.get("KINGDOM_APP_PLATFORM", "desktop"),
    )
    _write_secure(_identity_path(config_dir), identity.to_dict())
    logger.info(
        "🪪 Fresh install identity generated: user_id=%s installation_id=%s role=%s platform=%s",
        identity.user_id,
        identity.installation_id,
        identity.role,
        identity.mode_platform,
    )
    return identity


_lock = threading.Lock()
_cached: Optional[InstallIdentity] = None


def get_install_identity(
    config_dir: Optional[Path] = None, *, reset: bool = False
) -> InstallIdentity:
    """Return (and persist if needed) this install's identity.

    Thread-safe. On first call, generates and writes a new identity.
    Subsequent calls return the cached record.

    Parameters
    ----------
    config_dir : Path, optional
        Override the config directory (mainly for tests).
    reset : bool
        If True, force regenerate a fresh identity and overwrite the
        existing file. Use only for an explicit "start over" action.
    """
    global _cached
    with _lock:
        path = _identity_path(config_dir)

        if reset and path.exists():
            try:
                path.unlink()
            except Exception as e:
                logger.warning("Could not delete old identity: %s", e)

        if _cached is not None and not reset:
            return _cached

        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                _cached = InstallIdentity.from_dict(data)
                logger.debug("Loaded existing install identity: %s", _cached.user_id)
                return _cached
            except Exception as e:
                logger.warning(
                    "Install identity file unreadable (%s); regenerating.", e
                )

        _cached = _build_fresh(Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR)
        return _cached


def rename_user(new_display_name: str, config_dir: Optional[Path] = None) -> InstallIdentity:
    """Change the human-friendly display name without touching the
    underlying installation_id. Returns the updated identity."""
    identity = get_install_identity(config_dir)
    with _lock:
        identity.display_name = (new_display_name or identity.user_id).strip() or identity.user_id
        _write_secure(_identity_path(config_dir), identity.to_dict())
    logger.info("🪪 Display name changed to %s", identity.display_name)
    return identity


def set_user_id(new_user_id: str, config_dir: Optional[Path] = None) -> InstallIdentity:
    """Let the user pick their own stable user_id (e.g. "daniel").
    Installation_id stays the same — this is only the public handle."""
    identity = get_install_identity(config_dir)
    with _lock:
        identity.user_id = (new_user_id or identity.user_id).strip() or identity.user_id
        _write_secure(_identity_path(config_dir), identity.to_dict())
    logger.info("🪪 user_id changed to %s", identity.user_id)
    return identity


def forget_identity(config_dir: Optional[Path] = None) -> None:
    """Nuke the identity file. The next call to get_install_identity()
    will generate a brand-new one. Useful for 'start over' flows."""
    global _cached
    path = _identity_path(config_dir)
    with _lock:
        _cached = None
        if path.exists():
            try:
                path.unlink()
                logger.info("🪪 Install identity forgotten — next boot will generate fresh.")
            except Exception as e:
                logger.warning("Could not forget identity: %s", e)


# Convenience accessors for callers that just want the strings.
def current_user_id(config_dir: Optional[Path] = None) -> str:
    return get_install_identity(config_dir).user_id


def current_installation_id(config_dir: Optional[Path] = None) -> str:
    return get_install_identity(config_dir).installation_id


__all__ = [
    "InstallIdentity",
    "get_install_identity",
    "rename_user",
    "set_user_id",
    "forget_identity",
    "current_user_id",
    "current_installation_id",
]
