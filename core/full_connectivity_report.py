#!/usr/bin/env python3
"""End-to-end connectivity report for Kingdom AI trading infrastructure.

This script performs REAL network connectivity checks across:

- All configured crypto/FX exchanges wired into RealExchangeExecutor
- All configured stock/forex brokers wired into RealStockExecutor
- All blockchains defined in kingdomweb3_v2 via MultiChainTradeExecutor

It is designed to answer, in one place:

    *Which venues and chains are fully wired for live trading / data,
    and which ones are not, and why?*

It does **not** simulate anything and it does not place trades.
Use the pytest executor smoke tests for tiny live orders.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional

# Ensure the project root (one level above ``core/``) is on sys.path so that
# ``import core.*`` works whether this file is executed as a module
# (``python -m core.full_connectivity_report``) or as a standalone script
# (``python core/full_connectivity_report.py``).
try:  # pragma: no cover - environment dependent
    from core.api_key_manager import APIKeyManager  # type: ignore[import]
    from core.real_exchange_executor import RealExchangeExecutor  # type: ignore[import]
    from core.real_stock_executor import RealStockExecutor  # type: ignore[import]
    from core.multichain_trade_executor import (  # type: ignore[import]
        MultiChainTradeExecutor,
        load_rpc_overrides_from_comprehensive_config,
    )
except ModuleNotFoundError:  # pragma: no cover - script-style execution
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    from core.api_key_manager import APIKeyManager  # type: ignore[no-redef]
    from core.real_exchange_executor import RealExchangeExecutor  # type: ignore[no-redef]
    from core.real_stock_executor import RealStockExecutor  # type: ignore[no-redef]
    from core.multichain_trade_executor import (  # type: ignore[no-redef]
        MultiChainTradeExecutor,
        load_rpc_overrides_from_comprehensive_config,
    )

# Reuse the same API key mapping as the exchange smoke test so the
# connectivity report sees the exact same executor wiring.
try:  # pragma: no cover - helper is environment-dependent
    from real_exchange_smoke_test import build_real_exchange_api_keys
except Exception:  # pragma: no cover - keep script import-safe
    build_real_exchange_api_keys = None  # type: ignore[assignment]


logger = logging.getLogger("full_connectivity_report")


def _build_real_exchange_executor(api_key_manager: APIKeyManager) -> Optional[RealExchangeExecutor]:
    """Construct a RealExchangeExecutor from APIKeyManager keys, if possible.

    Returns None when no compatible exchange keys exist or the helper
    mapping function is unavailable. This is not treated as an error; it
    simply means no CEXs are currently wired for live trading.
    """

    if build_real_exchange_api_keys is None:
        logger.warning(
            "real_exchange_smoke_test.build_real_exchange_api_keys not available; "
            "cannot build RealExchangeExecutor for connectivity report.",
        )
        return None

    raw_keys = api_key_manager.api_keys
    flat = build_real_exchange_api_keys(raw_keys)
    if not flat:
        logger.info("No crypto/FX exchange API keys mapped for RealExchangeExecutor.")
        return None

    executor = RealExchangeExecutor(api_keys=flat, event_bus=None)
    if not getattr(executor, "connectors", {}):
        logger.info("RealExchangeExecutor has no connectors after key mapping; nothing to report.")
        return None

    return executor


async def _gather_exchange_connectivity(api_key_manager: APIKeyManager) -> Dict[str, Any]:
    """Collect connectivity info for all exchanges known to RealExchangeExecutor.

    This is keyed by the internal connector/exchange name used by the
    executor (e.g. "binance", "coinbase", "kraken", etc.).
    """

    out: Dict[str, Any] = {"executor_wired": False, "venues": {}}

    executor = _build_real_exchange_executor(api_key_manager)
    if executor is None:
        return out

    out["executor_wired"] = True

    # Health snapshot for all connected venues.
    health = await executor.get_exchange_health()

    for name, info in sorted(health.items()):
        status = info.get("status")
        venue: Dict[str, Any] = {
            "status": status,
        }

        if status in {"ok", "ok_empty"}:
            venue["balances_sample"] = info.get("balances_sample", {})
        else:
            venue["error"] = info.get("error") or info.get("details")

        out["venues"][name] = venue

    return out


async def _gather_broker_connectivity(api_key_manager: APIKeyManager) -> Dict[str, Any]:
    """Collect connectivity info for all stock/forex brokers wired into RealStockExecutor."""

    out: Dict[str, Any] = {"executor_wired": False, "brokers": {}}

    raw_keys = api_key_manager.api_keys or {}
    if not raw_keys:
        return out

    executor = RealStockExecutor(api_keys=raw_keys, event_bus=None)
    out["executor_wired"] = True

    health = await executor.get_broker_health()

    for name, info in sorted(health.items()):
        out["brokers"][name] = info

    return out


async def _gather_blockchain_connectivity() -> Dict[str, Any]:
    """Collect connectivity info for all chains in kingdomweb3_v2."""

    rpc_overrides = load_rpc_overrides_from_comprehensive_config()
    executor = MultiChainTradeExecutor(rpc_overrides=rpc_overrides)

    chains = executor.get_supported_networks()
    results: Dict[str, Any] = {}

    # Probe chains sequentially to avoid overwhelming RPC providers.
    for chain in chains:
        try:
            status = await executor.get_chain_status(chain)
            results[chain] = {
                "rpc_url": status.rpc_url,
                "is_evm": status.is_evm,
                "reachable": status.reachable,
                "latest_block": status.latest_block,
                "error": status.error,
            }
        except Exception as exc:  # pragma: no cover - network dependent
            results[chain] = {
                "rpc_url": "",
                "is_evm": False,
                "reachable": False,
                "latest_block": None,
                "error": f"probe failed: {exc}",
            }

    return {"chains": results}


async def build_full_connectivity_report() -> Dict[str, Any]:
    """Build a unified connectivity report across CEX, brokers, and chains.

    This is safe to call from tests or scripts; it does not place orders.
    """

    mgr = APIKeyManager.get_instance()
    mgr.initialize_sync()

    exchange_info = await _gather_exchange_connectivity(mgr)
    broker_info = await _gather_broker_connectivity(mgr)
    chain_info = await _gather_blockchain_connectivity()

    crypto_with_keys: List[str] = [
        name
        for name in APIKeyManager.CATEGORIES.get("crypto_exchanges", [])
        if name in mgr.api_keys
    ]
    stock_with_keys: List[str] = [
        name
        for name in APIKeyManager.CATEGORIES.get("stock_exchanges", [])
        if name in mgr.api_keys
    ]
    forex_with_keys: List[str] = [
        name
        for name in APIKeyManager.CATEGORIES.get("forex_trading", [])
        if name in mgr.api_keys
    ]

    ex_health: Dict[str, Any] = exchange_info.get("venues", {}) or {}
    broker_health: Dict[str, Any] = broker_info.get("brokers", {}) or {}

    ex_status_counts: Counter[str] = Counter(
        str(info.get("status") or "unknown") for info in ex_health.values()
    )
    broker_status_counts: Counter[str] = Counter(
        str(info.get("status") or "unknown") for info in broker_health.values()
    )

    # Map crypto service names from APIKeyManager to the connector names used
    # by RealExchangeExecutor so we can see which keyed services are actually
    # wired and tested.
    service_to_connectors: Dict[str, set[str]] = {}
    for svc in crypto_with_keys:
        if svc in {"htx", "huobi"}:
            service_to_connectors.setdefault(svc, set()).add("htx")
        elif svc == "gate_io":
            service_to_connectors.setdefault(svc, set()).add("gateio")
        elif svc == "crypto_com":
            service_to_connectors.setdefault(svc, set()).add("cryptocom")
        else:
            service_to_connectors.setdefault(svc, set()).add(svc)

    connector_names = set(ex_health.keys())
    wired_crypto_services = {
        svc
        for svc, candidates in service_to_connectors.items()
        if connector_names.intersection(candidates)
    }
    unwired_crypto_services = sorted(set(crypto_with_keys) - wired_crypto_services)

    crypto_summary = {
        "total_with_keys": len(crypto_with_keys),
        "connected_venues": len(ex_health),
        "healthy_venues": sum(
            count for status, count in ex_status_counts.items() if status in {"ok", "ok_empty"}
        ),
        "degraded_venues": sum(
            count for status, count in ex_status_counts.items() if status not in {"ok", "ok_empty"}
        ),
        "status_counts": dict(sorted(ex_status_counts.items())),
        "services_with_keys_but_no_connector": unwired_crypto_services,
    }

    broker_keys = sorted(set(stock_with_keys) | set(forex_with_keys))
    brokers_with_health = set(broker_health.keys())
    missing_broker_health = sorted(
        name for name in broker_keys if name not in brokers_with_health
    )

    brokers_summary = {
        "total_stock_with_keys": len(stock_with_keys),
        "total_forex_with_keys": len(forex_with_keys),
        "unique_brokers_with_keys": len(broker_keys),
        "brokers_reported": len(broker_health),
        "status_counts": dict(sorted(broker_status_counts.items())),
        "brokers_with_keys_but_no_health_entry": missing_broker_health,
    }

    return {
        "exchanges": exchange_info,
        "brokers": broker_info,
        "blockchains": chain_info,
        "api_key_services": {
            "crypto_exchanges_with_keys": crypto_with_keys,
            "stock_exchanges_with_keys": stock_with_keys,
            "forex_with_keys": forex_with_keys,
        },
        "summary": {
            "crypto_exchanges": crypto_summary,
            "brokers": brokers_summary,
        },
    }


async def _async_main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    report = await build_full_connectivity_report()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover - manual invocation
    asyncio.run(_async_main())
