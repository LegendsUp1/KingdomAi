#!/usr/bin/env python3
"""
KAIG Token Identity Abstraction Layer
======================================
THE SINGLE SOURCE OF TRUTH for the token's name, ticker, contract addresses,
and all identity metadata. Every system in Kingdom AI reads from HERE.

WHY THIS EXISTS:
- Creator cannot afford trademark protection right now.
- If the name "KAIG" is ever stolen, challenged, or must change, this module
  ensures that ONE config change propagates to every subsystem.
- User balances are tracked by WALLET ADDRESS, never by token name.
- A name/ticker change does NOT affect anyone's funds.

ARCHITECTURE:
- Reads from config/kaig/runtime_config.json (hot-reloadable)
- Publishes 'kaig.identity.changed' event on any change
- All systems import get_token_identity() instead of hardcoding "KAIG"
- Migration history is append-only — full audit trail

USAGE:
    from core.kaig_token_identity import get_token_identity, get_ticker, get_name

    identity = get_token_identity()
    print(identity.ticker)   # "KAIG"
    print(identity.name)     # "KAI Gold"
    print(identity.full)     # "$KAIG (KAI Gold)"
"""

import json
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("KingdomAI.TokenIdentity")

# ── Paths ────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_RUNTIME_CONFIG = _BASE_DIR / "config" / "kaig" / "runtime_config.json"
_MIGRATION_LOG = _BASE_DIR / "config" / "kaig" / "migration_history.json"
_IDENTITY_LOCK = threading.Lock()


# ── Data Classes ─────────────────────────────────────────────────────
@dataclass
class TokenIdentity:
    """Immutable snapshot of the current token identity."""
    ticker: str = "KAIG"
    name: str = "KAI Gold"
    full_name: str = "$KAIG (KAI Gold)"
    description: str = "AI-managed cryptocurrency with revenue-backed buyback mechanism"
    contract_addresses: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "ethereum": None, "solana": None, "base": None, "bsc": None
    })
    identity_version: int = 1
    created_at: str = ""
    previous_ticker: Optional[str] = None
    previous_name: Optional[str] = None


@dataclass
class MigrationRecord:
    """One entry in the append-only migration history."""
    migration_id: str = ""
    timestamp: str = ""
    old_ticker: str = ""
    old_name: str = ""
    new_ticker: str = ""
    new_name: str = ""
    reason: str = ""
    balances_snapshot_path: str = ""
    identity_version: int = 0
    executed_by: str = "system"
    status: str = "completed"


# ── Singleton State ──────────────────────────────────────────────────
_current_identity: Optional[TokenIdentity] = None
_event_bus = None  # Set via set_event_bus()


def set_event_bus(eb: Any) -> None:
    """Register the global event bus so identity changes propagate."""
    global _event_bus
    _event_bus = eb


def _load_identity_from_config() -> TokenIdentity:
    """Read token identity from runtime_config.json."""
    try:
        if _RUNTIME_CONFIG.exists():
            with open(_RUNTIME_CONFIG, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            token = cfg.get("token", {})
            deploy = cfg.get("deployment", {})
            contracts = deploy.get("contract_addresses", {})

            return TokenIdentity(
                ticker=token.get("ticker", "KAIG"),
                name=token.get("name", "KAI Gold"),
                full_name=token.get("full_name", "$KAIG (KAI Gold)"),
                description=token.get("description", ""),
                contract_addresses=contracts,
                identity_version=cfg.get("_identity_version", 1),
                created_at=cfg.get("_last_updated", ""),
                previous_ticker=token.get("previous_ticker"),
                previous_name=token.get("previous_name"),
            )
    except Exception as e:
        logger.error(f"Failed to load token identity from config: {e}")

    return TokenIdentity()  # Safe defaults


def get_token_identity() -> TokenIdentity:
    """Get the current token identity (cached singleton, thread-safe)."""
    global _current_identity
    if _current_identity is None:
        with _IDENTITY_LOCK:
            if _current_identity is None:
                _current_identity = _load_identity_from_config()
                logger.info(
                    "Token identity loaded: %s (%s) v%d",
                    _current_identity.ticker,
                    _current_identity.name,
                    _current_identity.identity_version,
                )
    return _current_identity


def get_ticker() -> str:
    """Convenience: get current ticker symbol."""
    return get_token_identity().ticker


def get_name() -> str:
    """Convenience: get current token name."""
    return get_token_identity().name


def get_full_name() -> str:
    """Convenience: get display name like '$KAIG (KAI Gold)'."""
    return get_token_identity().full_name


def reload_identity() -> TokenIdentity:
    """Force-reload identity from config (e.g., after hot config change)."""
    global _current_identity
    with _IDENTITY_LOCK:
        _current_identity = _load_identity_from_config()
        logger.info("Token identity reloaded: %s", _current_identity.ticker)
    return _current_identity


# ── Migration Execution ──────────────────────────────────────────────

def execute_rebrand(
    new_ticker: str,
    new_name: str,
    reason: str = "name_change",
    executed_by: str = "creator",
    balances_snapshot_path: str = "",
) -> MigrationRecord:
    """
    Execute a full token rebrand.

    This is the ATOMIC operation that:
    1. Snapshots current identity
    2. Updates runtime_config.json with new name/ticker
    3. Appends to migration_history.json (append-only audit trail)
    4. Reloads the singleton identity
    5. Publishes 'kaig.identity.changed' event so ALL systems update

    USER FUNDS ARE NEVER AFFECTED because:
    - Internal ledger tracks by wallet address, not token name
    - All balances, credits, and history remain intact
    - Only display labels change

    Args:
        new_ticker: New ticker symbol (e.g., "KDOM")
        new_name: New token name (e.g., "Kingdom Dollar")
        reason: Why the rebrand is happening
        executed_by: Who initiated it
        balances_snapshot_path: Path to the balances snapshot file

    Returns:
        MigrationRecord documenting the change
    """
    global _current_identity

    with _IDENTITY_LOCK:
        old = get_token_identity()

        if old.ticker == new_ticker and old.name == new_name:
            logger.warning("Rebrand called but ticker/name unchanged — skipping")
            return MigrationRecord(status="skipped")

        new_version = old.identity_version + 1
        now = datetime.utcnow().isoformat() + "Z"

        # ── 1. Build migration record ────────────────────────────
        import uuid
        record = MigrationRecord(
            migration_id=f"MIG-{uuid.uuid4().hex[:12].upper()}",
            timestamp=now,
            old_ticker=old.ticker,
            old_name=old.name,
            new_ticker=new_ticker,
            new_name=new_name,
            reason=reason,
            balances_snapshot_path=balances_snapshot_path,
            identity_version=new_version,
            executed_by=executed_by,
            status="completed",
        )

        # ── 2. Backup current config ─────────────────────────────
        backup_dir = _BASE_DIR / "config" / "kaig" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_name = f"runtime_config_v{old.identity_version}_{old.ticker}_{int(time.time())}.json"
        if _RUNTIME_CONFIG.exists():
            shutil.copy2(_RUNTIME_CONFIG, backup_dir / backup_name)
            logger.info("Config backed up to %s", backup_name)

        # ── 3. Update runtime_config.json ────────────────────────
        try:
            with open(_RUNTIME_CONFIG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

        # Preserve previous identity in the token section
        cfg.setdefault("token", {})
        cfg["token"]["previous_ticker"] = old.ticker
        cfg["token"]["previous_name"] = old.name
        cfg["token"]["ticker"] = new_ticker
        cfg["token"]["name"] = new_name
        cfg["token"]["full_name"] = f"${new_ticker} ({new_name})"
        cfg["_identity_version"] = new_version
        cfg["_last_updated"] = now

        with open(_RUNTIME_CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)

        logger.warning(
            "TOKEN REBRAND EXECUTED: %s (%s) → %s (%s) | version %d | reason: %s",
            old.ticker, old.name, new_ticker, new_name, new_version, reason,
        )

        # ── 4. Append to migration history ───────────────────────
        _append_migration_record(record)

        # ── 5. Reload singleton ──────────────────────────────────
        _current_identity = _load_identity_from_config()

        # ── 6. Publish identity change event ─────────────────────
        if _event_bus is not None:
            try:
                _event_bus.publish("kaig.identity.changed", {
                    "migration_id": record.migration_id,
                    "old_ticker": old.ticker,
                    "old_name": old.name,
                    "new_ticker": new_ticker,
                    "new_name": new_name,
                    "identity_version": new_version,
                    "reason": reason,
                    "timestamp": now,
                })
            except Exception as e:
                logger.error(f"Failed to publish identity change event: {e}")

        return record


def _append_migration_record(record: MigrationRecord) -> None:
    """Append a migration record to the append-only history file."""
    try:
        _MIGRATION_LOG.parent.mkdir(parents=True, exist_ok=True)

        history: List[Dict] = []
        if _MIGRATION_LOG.exists():
            with open(_MIGRATION_LOG, "r", encoding="utf-8") as f:
                history = json.load(f)

        history.append(asdict(record))

        with open(_MIGRATION_LOG, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)

        logger.info("Migration record %s appended to history", record.migration_id)
    except Exception as e:
        logger.error(f"Failed to write migration record: {e}")


def get_migration_history() -> List[Dict]:
    """Return the full append-only migration history."""
    try:
        if _MIGRATION_LOG.exists():
            with open(_MIGRATION_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read migration history: {e}")
    return []


def get_previous_identities() -> List[Dict[str, str]]:
    """Return list of all previous ticker/name pairs from migration history."""
    history = get_migration_history()
    return [
        {"ticker": r["old_ticker"], "name": r["old_name"], "version": r["identity_version"] - 1}
        for r in history
    ]
