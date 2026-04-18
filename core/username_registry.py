#!/usr/bin/env python3
"""
Kingdom AI — Username Registry (SOTA 2026)

Globally unique, case-insensitive username system for payment routing.
Prevents any two users from having the same username.  Usernames are
normalised (lowered, stripped, NFC-normalised) before storage so
"Alice", "alice", and " ALICE " all resolve to the same canonical form.

Storage: data/users/username_registry.json
  {
    "alice": {
      "user_id": "device_abc123",
      "display_name": "Alice",
      "addresses": {"ETH": "0x...", "BTC": "bc1q..."},
      "registered_at": "2026-02-19T...",
      "referral_code": "KAIG-AB12CD",
      "referred_by": "KAIG-XY34ZW"
    }
  }

Rules (SOTA 2026 — RFC 8265 + ENSIP-15 inspired):
  - Min 3 chars, max 32 chars
  - Only a-z, 0-9, underscore, dot, dash (after normalisation)
  - No leading/trailing dots/dashes
  - No consecutive dots/dashes
  - Reserved words blocked (admin, system, kingdom, support, etc.)
  - Case-insensitive: stored lower, displayed as chosen
"""

import json
import logging
import os
import re
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("KingdomAI.UsernameRegistry")

REGISTRY_PATH = os.path.join("data", "users", "username_registry.json")
REVERSE_INDEX_PATH = os.path.join("data", "users", "userid_to_username.json")

RESERVED_WORDS = frozenset({
    "admin", "administrator", "system", "kingdom", "kingdomai",
    "support", "help", "root", "mod", "moderator", "staff",
    "kaig", "kaigold", "official", "bot", "null", "undefined",
    "test", "demo", "api", "wallet", "bank", "pay", "payment",
    "owner", "creator", "consumer", "god", "master",
})

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,30}[a-z0-9]$")
NO_CONSECUTIVE = re.compile(r"[.\-_]{2,}")

_lock = threading.Lock()


def _normalise(raw: str) -> str:
    """NFC-normalise, strip, lower a raw username string."""
    normalised = unicodedata.normalize("NFC", raw.strip()).lower()
    normalised = normalised.replace(" ", "")
    return normalised


def _validate(canonical: str) -> Optional[str]:
    """Return an error string if invalid, else None."""
    if len(canonical) < 3:
        return "Username must be at least 3 characters"
    if len(canonical) > 32:
        return "Username must be at most 32 characters"
    if not USERNAME_PATTERN.match(canonical):
        return "Username may only contain a-z, 0-9, dot, dash, underscore (must start/end with alphanumeric)"
    if NO_CONSECUTIVE.search(canonical):
        return "Username cannot have consecutive dots, dashes, or underscores"
    if canonical in RESERVED_WORDS:
        return f"'{canonical}' is a reserved word"
    return None


def _load_registry() -> Dict[str, Dict]:
    try:
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error("Failed to load username registry: %s", e)
    return {}


def _save_registry(data: Dict[str, Dict]):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_reverse() -> Dict[str, str]:
    try:
        if os.path.exists(REVERSE_INDEX_PATH):
            with open(REVERSE_INDEX_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_reverse(data: Dict[str, str]):
    os.makedirs(os.path.dirname(REVERSE_INDEX_PATH), exist_ok=True)
    with open(REVERSE_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def register_username(
    raw_username: str,
    user_id: str,
    addresses: Dict[str, str] = None,
    display_name: str = "",
    referral_code: str = "",
    referred_by: str = "",
) -> Dict[str, Any]:
    """Register a globally unique username for a user.

    Returns {"success": True, "username": canonical} or
            {"success": False, "error": "reason"}.
    """
    canonical = _normalise(raw_username)
    err = _validate(canonical)
    if err:
        return {"success": False, "error": err}

    with _lock:
        registry = _load_registry()
        reverse = _load_reverse()

        if canonical in registry:
            existing_uid = registry[canonical].get("user_id", "")
            if existing_uid == user_id:
                return {"success": True, "username": canonical, "already_registered": True}
            return {"success": False, "error": f"Username '{canonical}' is already taken"}

        if user_id in reverse:
            old_name = reverse[user_id]
            return {"success": False,
                    "error": f"You already have username '{old_name}'. Change it first."}

        entry = {
            "user_id": user_id,
            "display_name": display_name or raw_username,
            "addresses": addresses or {},
            "registered_at": datetime.utcnow().isoformat(),
            "referral_code": referral_code,
            "referred_by": referred_by,
        }
        registry[canonical] = entry
        reverse[user_id] = canonical

        _save_registry(registry)
        _save_reverse(reverse)

    logger.info("Username '%s' registered for user %s", canonical, user_id)
    return {"success": True, "username": canonical}


def change_username(user_id: str, new_raw: str) -> Dict[str, Any]:
    """Allow a user to change their username (old one freed)."""
    canonical = _normalise(new_raw)
    err = _validate(canonical)
    if err:
        return {"success": False, "error": err}

    with _lock:
        registry = _load_registry()
        reverse = _load_reverse()

        if canonical in registry and registry[canonical].get("user_id") != user_id:
            return {"success": False, "error": f"Username '{canonical}' is already taken"}

        old_name = reverse.get(user_id)
        old_entry = {}
        if old_name and old_name in registry:
            old_entry = registry.pop(old_name)

        entry = old_entry or {}
        entry["user_id"] = user_id
        entry["display_name"] = new_raw
        entry["changed_at"] = datetime.utcnow().isoformat()

        registry[canonical] = entry
        reverse[user_id] = canonical

        _save_registry(registry)
        _save_reverse(reverse)

    logger.info("Username changed to '%s' for user %s", canonical, user_id)
    return {"success": True, "username": canonical}


def resolve_username(raw: str) -> Optional[Dict[str, Any]]:
    """Resolve a username to its user entry (addresses, user_id, etc.).

    Input can be "@alice" or "alice" — the @ is stripped.
    Returns the entry dict or None if not found.
    """
    clean = raw.lstrip("@")
    canonical = _normalise(clean)
    registry = _load_registry()
    return registry.get(canonical)


def get_username_for_user(user_id: str) -> Optional[str]:
    """Get the registered username for a user_id."""
    reverse = _load_reverse()
    return reverse.get(user_id)


def update_addresses(user_id: str, addresses: Dict[str, str]):
    """Update wallet addresses for a user's username entry."""
    with _lock:
        registry = _load_registry()
        reverse = _load_reverse()
        uname = reverse.get(user_id)
        if uname and uname in registry:
            registry[uname]["addresses"] = addresses
            _save_registry(registry)


def is_username_available(raw: str) -> bool:
    canonical = _normalise(raw)
    err = _validate(canonical)
    if err:
        return False
    registry = _load_registry()
    return canonical not in registry


def list_all_usernames() -> List[str]:
    registry = _load_registry()
    return sorted(registry.keys())


def generate_payment_qr_payload(user_id: str) -> Dict[str, Any]:
    """Generate a QR payload for receiving payments.

    Includes username and addresses so the sender can resolve
    the correct chain address on scan.
    """
    reverse = _load_reverse()
    registry = _load_registry()
    uname = reverse.get(user_id)
    if not uname or uname not in registry:
        return {"error": "No username registered — register first"}
    entry = registry[uname]
    return {
        "type": "kingdom_pay",
        "version": 2,
        "username": uname,
        "display_name": entry.get("display_name", uname),
        "addresses": entry.get("addresses", {}),
        "timestamp": datetime.utcnow().isoformat(),
    }
