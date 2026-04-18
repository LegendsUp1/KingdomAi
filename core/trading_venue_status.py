"""Canonical trading-venue readiness status.

Single source of truth for answering the question:
  "What trading venues can Kingdom AI execute against RIGHT NOW, and
   which ones are dormant scaffolds waiting for credentials?"

The report bridges three systems:
  1. APIKeyManager.CATEGORIES - declares every venue Kingdom AI knows about
     (crypto_exchanges, stock_exchanges, forex_trading, prediction markets)
  2. APIKeyManager.api_keys - populated credentials loaded from disk
  3. RealExchangeExecutor.get_exchange_health() + RealStockExecutor -
     runtime health of every connected venue

Produced bucket states (per venue):
  - LIVE: connected AND last balance call succeeded
  - DEGRADED: connected but currently errored (geo-block, perm, time-skew)
  - NEEDS_CREDENTIALS: declared in CATEGORIES, scaffold exists, no key filled
  - NOT_CONFIGURED: declared in CATEGORIES, no scaffold at all

A summary block tells the caller (and the user, via EventBus) exactly
which markets trade live right now.

Public API:
  await compute_trading_venue_status(api_key_manager, real_exchange_executor=None,
                                     real_stock_executor=None) -> dict
  publish_trading_venue_status(report, event_bus) -> None

Consumers:
  - GUI trading tab ("Live Venues" badge)
  - tests/test_trading_readiness.py
  - Ollama brain ("what can I trade right now?")
  - Kingdom AI headless boot (prints summary on startup)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# Native / special-case venue names that live outside the CCXT id space but
# are first-class trading destinations in Kingdom AI.
NATIVE_VENUES: Tuple[str, ...] = (
    "oanda", "btcc", "polymarket", "kalshi", "alpaca",
)

# Category -> label mapping for report grouping
CATEGORY_LABELS: Dict[str, str] = {
    "crypto_exchanges": "Crypto CEXs",
    "stock_exchanges":  "Stock / Equities Brokers",
    "forex_trading":    "Forex Brokers",
    "prediction_markets": "Prediction Markets",
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
# PRIMARY auth fields - at least one must be non-empty for a venue to be
# considered "populated" (i.e. the user has pasted real credentials in).
# Account numbers, memos, and PINs alone are NOT sufficient - a broker
# session always needs a primary bearer (api_key/token/login/client_id).
_PRIMARY_AUTH_FIELDS: Tuple[str, ...] = (
    "api_key", "apiKey", "key", "access_key", "public_key", "api_key_id",
    "access_token", "refresh_token", "session_token", "private_key",
    "client_id", "app_key", "consumer_key",
    "username", "login",
)


def _populated(entry: Any) -> bool:
    """Return True when the api-keys entry has a non-empty *primary* auth field.

    Metadata fields (endpoint, demo, sandbox, _NOTE, environment, memo,
    account_number alone) do NOT count - a venue is only "populated" once
    a real bearer token / key / session username has been provided.
    """
    if not isinstance(entry, dict):
        return False
    for field in _PRIMARY_AUTH_FIELDS:
        v = entry.get(field)
        if isinstance(v, str) and v.strip():
            return True
    return False


def _declared_trading_venues(api_key_manager) -> Dict[str, str]:
    """Return {venue_name: category} for every declared trading venue."""
    out: Dict[str, str] = {}
    categories = getattr(api_key_manager, "CATEGORIES", {})
    if not isinstance(categories, dict):
        return out

    for cat in ("crypto_exchanges", "stock_exchanges", "forex_trading"):
        for name in categories.get(cat, []) or []:
            out[name.lower()] = cat

    # Add prediction-market and native venues that aren't always in CATEGORIES.
    for native in ("polymarket", "kalshi"):
        out.setdefault(native, "prediction_markets")
    for native in NATIVE_VENUES:
        out.setdefault(native, out.get(native) or _infer_category(native))

    return out


def _infer_category(name: str) -> str:
    if name in ("alpaca",):
        return "stock_exchanges"
    if name in ("oanda",):
        return "forex_trading"
    if name in ("polymarket", "kalshi"):
        return "prediction_markets"
    return "crypto_exchanges"


def _alpaca_is_live(stock_executor) -> bool:
    """Treat Alpaca as LIVE if RealStockExecutor has alpaca broker config.

    The real executor stores Alpaca creds in ``self.brokers["alpaca"]``
    once :meth:`_setup_alpaca` accepts them; that is the authoritative
    signal that the broker can take orders. We also accept legacy client
    attribute names for backward compatibility.
    """
    if stock_executor is None:
        return False
    brokers = getattr(stock_executor, "brokers", None)
    if isinstance(brokers, dict) and brokers.get("alpaca"):
        cfg = brokers["alpaca"]
        if isinstance(cfg, dict) and cfg.get("api_key") and cfg.get("api_secret"):
            return True
    for attr in ("alpaca_client", "alpaca", "alpaca_trading_client",
                 "alpaca_rest", "alpaca_api"):
        if getattr(stock_executor, attr, None):
            return True
    return False


async def _alpaca_probe_health(stock_executor) -> Optional[Dict[str, Any]]:
    """Run the live Alpaca health probe and return a normalized dict.

    Returns ``None`` if the executor or the probe method isn't available.
    """
    if stock_executor is None:
        return None
    brokers = getattr(stock_executor, "brokers", {}) or {}
    cfg = brokers.get("alpaca")
    if not isinstance(cfg, dict):
        return None
    probe = getattr(stock_executor, "_get_alpaca_health", None)
    if probe is None:
        return None
    try:
        # Force the probe to actually run even if the startup-skip env var is set;
        # callers of trading_venue_status explicitly want a live picture.
        import os as _os
        prev = _os.environ.get("KINGDOM_SKIP_ALPACA_HEALTH")
        _os.environ["KINGDOM_SKIP_ALPACA_HEALTH"] = "0"
        try:
            return await probe(cfg)
        finally:
            if prev is None:
                _os.environ.pop("KINGDOM_SKIP_ALPACA_HEALTH", None)
            else:
                _os.environ["KINGDOM_SKIP_ALPACA_HEALTH"] = prev
    except Exception as exc:  # noqa: BLE001
        logger.debug("alpaca probe failed: %s", exc)
        return {"status": "client_error", "error": str(exc)}


# --------------------------------------------------------------------------
# Core computation
# --------------------------------------------------------------------------
async def compute_trading_venue_status(
    api_key_manager,
    real_exchange_executor=None,
    real_stock_executor=None,
    *,
    include_health_probe: bool = True,
) -> Dict[str, Any]:
    """Produce the canonical live-vs-dormant trading venue status report.

    The report structure::

        {
            "timestamp": 1713311245.1,
            "summary": {
                "live": ["kraken", "coinbase", ...],
                "degraded": {"binance": "restricted_location", ...},
                "needs_credentials": ["bybit", "kucoin", ...],
                "not_configured": ["some_venue", ...],
                "counts": {"live": 6, "degraded": 1, ...}
            },
            "by_category": {
                "Crypto CEXs":      {...},
                "Stock Brokers":    {...},
                "Forex Brokers":    {...},
                "Prediction Markets": {...}
            },
            "per_venue": {
                "kraken":   {"status": "LIVE", "category": "crypto_exchanges",
                             "health": "ok", "credentials": "set"},
                "bybit":    {"status": "NEEDS_CREDENTIALS", ...},
                ...
            }
        }
    """
    declared = _declared_trading_venues(api_key_manager)
    raw_keys = getattr(api_key_manager, "api_keys", {}) or {}

    # Optional live health probe on the exchange executor
    health: Dict[str, Dict[str, Any]] = {}
    if include_health_probe and real_exchange_executor is not None:
        try:
            health = await real_exchange_executor.get_exchange_health()
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_exchange_health() failed for venue report: %s", exc)
            health = {}

    connected: Set[str] = set()
    if real_exchange_executor is not None:
        connected = set(
            getattr(real_exchange_executor, "connectors", {}).keys()
        ) | set(
            getattr(real_exchange_executor, "exchanges", {}).keys()
        )

    per_venue: Dict[str, Dict[str, Any]] = {}
    live: List[str] = []
    degraded: Dict[str, str] = {}
    needs_creds: List[str] = []
    not_configured: List[str] = []

    for venue, category in sorted(declared.items()):
        entry: Dict[str, Any] = {
            "venue": venue,
            "category": category,
            "credentials": "set" if _populated(raw_keys.get(venue)) else "unset",
        }

        # 1) Alpaca is handled by RealStockExecutor, not the CCXT executor
        if venue == "alpaca":
            if _alpaca_is_live(real_stock_executor):
                probe = await _alpaca_probe_health(real_stock_executor)
                if probe is None:
                    entry["status"] = "LIVE"
                    entry["health"] = "stock_broker_wired"
                    live.append(venue)
                else:
                    pstatus = (probe.get("status") or "").lower()
                    if pstatus in ("ok", "configured"):
                        entry["status"] = "LIVE"
                        entry["health"] = "ok"
                        entry["health_details"] = probe
                        live.append(venue)
                    elif pstatus == "auth_error":
                        entry["status"] = "DEGRADED"
                        entry["health"] = "alpaca_key_invalid"
                        entry["health_details"] = probe
                        degraded[venue] = entry["health"]
                    elif pstatus == "package_missing":
                        entry["status"] = "DEGRADED"
                        entry["health"] = "alpaca_sdk_missing"
                        entry["health_details"] = probe
                        degraded[venue] = entry["health"]
                    else:
                        entry["status"] = "DEGRADED"
                        entry["health"] = f"alpaca_{pstatus or 'unknown'}"
                        entry["health_details"] = probe
                        degraded[venue] = entry["health"]
            elif entry["credentials"] == "set":
                entry["status"] = "DEGRADED"
                entry["health"] = "alpaca_sdk_missing_or_key_invalid"
                degraded[venue] = entry["health"]
            else:
                entry["status"] = "NEEDS_CREDENTIALS"
                needs_creds.append(venue)
            per_venue[venue] = entry
            continue

        # 2) OANDA / BTCC / Polymarket / Kalshi / any CCXT venue with a
        #    connector is considered connected
        if venue in connected:
            h = health.get(venue) or {}
            status_raw = h.get("status", "ok")
            entry["health"] = status_raw
            entry["health_details"] = {
                k: v for k, v in h.items() if k != "status"
            }

            if status_raw in ("ok", "ok_empty"):
                entry["status"] = "LIVE"
                live.append(venue)
            else:
                entry["status"] = "DEGRADED"
                degraded[venue] = status_raw

            per_venue[venue] = entry
            continue

        # 3) Scaffold exists & has credentials but not connected -> degraded
        if entry["credentials"] == "set":
            entry["status"] = "DEGRADED"
            entry["health"] = "credentials_present_but_not_wired"
            degraded[venue] = entry["health"]
            per_venue[venue] = entry
            continue

        # 4) Scaffold exists in raw_keys but all fields empty ->
        #    ready to fill
        if isinstance(raw_keys.get(venue), dict):
            entry["status"] = "NEEDS_CREDENTIALS"
            entry["health"] = "scaffold_ready_paste_api_key_to_activate"
            needs_creds.append(venue)
            per_venue[venue] = entry
            continue

        # 5) Declared in CATEGORIES but no scaffold anywhere
        entry["status"] = "NOT_CONFIGURED"
        entry["health"] = "no_scaffold_declare_in_config/api_keys.json"
        not_configured.append(venue)
        per_venue[venue] = entry

    # Group by category for user-friendly display
    by_category: Dict[str, Dict[str, List[str]]] = {}
    for venue, entry in per_venue.items():
        label = CATEGORY_LABELS.get(entry["category"], entry["category"])
        bucket = by_category.setdefault(label, {
            "live": [], "degraded": [], "needs_credentials": [], "not_configured": []
        })
        bucket[entry["status"].lower()].append(venue)

    report = {
        "timestamp": time.time(),
        "summary": {
            "live": sorted(live),
            "degraded": dict(sorted(degraded.items())),
            "needs_credentials": sorted(needs_creds),
            "not_configured": sorted(not_configured),
            "counts": {
                "live":              len(live),
                "degraded":          len(degraded),
                "needs_credentials": len(needs_creds),
                "not_configured":    len(not_configured),
                "total_declared":    len(declared),
            },
        },
        "by_category": by_category,
        "per_venue": per_venue,
    }
    return report


def publish_trading_venue_status(
    report: Mapping[str, Any],
    event_bus,
    *,
    topic: str = "trading.venues.status",
) -> None:
    """Emit the report to the EventBus.

    Subscribers (GUI, Ollama brain, dashboards) can listen on
    ``trading.venues.status`` to learn what's live and what's waiting.
    """
    if event_bus is None:
        return
    try:
        event_bus.publish(topic, dict(report))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to publish %s: %s", topic, exc)


def format_human_readable(report: Mapping[str, Any]) -> str:
    """Turn the report into a compact, human-readable one-screen summary."""
    s = report.get("summary", {})
    counts = s.get("counts", {})
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("KINGDOM AI - TRADING VENUE READINESS")
    lines.append("=" * 70)
    lines.append(
        f"LIVE (trading now):      {counts.get('live', 0):>3}  "
        f"- {', '.join(s.get('live', [])) or '(none)'}"
    )
    deg = s.get("degraded", {}) or {}
    lines.append(f"DEGRADED (fix needed):   {counts.get('degraded', 0):>3}")
    for v, reason in deg.items():
        lines.append(f"  - {v:<18} reason: {reason}")
    lines.append(
        f"NEEDS CREDENTIALS:       {counts.get('needs_credentials', 0):>3}  "
        f"- {', '.join(s.get('needs_credentials', [])) or '(none)'}"
    )
    lines.append(
        f"NOT CONFIGURED:          {counts.get('not_configured', 0):>3}  "
        f"- {', '.join(s.get('not_configured', [])) or '(none)'}"
    )
    lines.append("=" * 70)
    return "\n".join(lines)


__all__ = [
    "compute_trading_venue_status",
    "publish_trading_venue_status",
    "format_human_readable",
    "NATIVE_VENUES",
    "CATEGORY_LABELS",
]
