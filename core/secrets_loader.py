"""Creator-mode-only secrets loader.

Reads config/.secrets.env (gitignored) and seeds os.environ with the
live values. In any mode other than creator this module refuses to do
anything, so a mis-built consumer bundle can never pull creator values.

The tracked companion files (config/api_keys.env, .env, config/api_keys.json,
config/COMPLETE_SYSTEM_CONFIG.json) contain REDACTED-PLACEHOLDER. Whenever
this loader runs we overwrite those placeholders with the real values
from .secrets.env in-process only (nothing is written back to disk).

Import early, before any module that reads API keys from os.environ.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Iterable

_LOG = logging.getLogger(__name__)

PLACEHOLDER = "REDACTED-PLACEHOLDER"
_SECRETS_FILENAME = ".secrets.env"
_DEFAULT_SECRETS_PATH = Path(__file__).resolve().parents[1] / "config" / _SECRETS_FILENAME


def _is_creator_mode() -> bool:
    mode = os.environ.get("KINGDOM_APP_MODE", "").strip().lower()
    return mode == "creator"


def _parse_env(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            # preserve the first occurrence; later duplicates are ignored
            out.setdefault(key, value)
    except OSError as exc:
        _LOG.warning("secrets_loader: cannot read %s: %s", path, exc)
    return out


def load_secrets(
    secrets_path: Path | str | None = None,
    *,
    override_placeholders: bool = True,
    override_missing: bool = True,
    silent_if_consumer: bool = True,
) -> int:
    """Load creator secrets into os.environ if running in creator mode.

    Returns the number of keys applied. In consumer or unknown modes this
    is a no-op (returns 0).
    """
    if not _is_creator_mode():
        if not silent_if_consumer:
            _LOG.debug("secrets_loader: skipped (mode=%s)", os.environ.get("KINGDOM_APP_MODE"))
        return 0

    path = Path(secrets_path) if secrets_path else _DEFAULT_SECRETS_PATH
    if not path.exists():
        _LOG.warning(
            "secrets_loader: %s missing; creator mode is active but no live "
            "secrets were loaded. Paste your values into config/.secrets.env.",
            path,
        )
        return 0

    secrets = _parse_env(path)
    applied = 0
    for key, value in secrets.items():
        current = os.environ.get(key)
        if current is None and override_missing:
            os.environ[key] = value
            applied += 1
            continue
        if current == PLACEHOLDER and override_placeholders:
            os.environ[key] = value
            applied += 1
            continue
    _LOG.info("secrets_loader: loaded %d creator secret(s) from %s", applied, path.name)
    return applied


def assert_consumer_clean(forbidden_keys: Iterable[str] | None = None) -> None:
    """Assert that we are not about to ship a creator value in consumer mode.

    Raises RuntimeError if consumer mode sees a non-placeholder value for any
    forbidden key. Intended as a defence-in-depth startup check; called by the
    consumer launcher before any network IO.
    """
    if _is_creator_mode():
        return
    forbidden_keys = list(forbidden_keys or [])
    hits: list[str] = []
    for key in forbidden_keys:
        value = os.environ.get(key)
        if value and value != PLACEHOLDER:
            hits.append(key)
    if hits:
        raise RuntimeError(
            "Consumer-mode startup refused: creator-shaped values present in "
            f"environment for: {', '.join(hits)}. A consumer bundle must never "
            "contain live creator secrets."
        )


__all__ = ["load_secrets", "assert_consumer_clean", "PLACEHOLDER"]
