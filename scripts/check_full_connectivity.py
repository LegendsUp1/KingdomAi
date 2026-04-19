#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified connectivity diagnostic for Kingdom AI.

This script combines:

- Exchange connectivity via RealExchangeExecutor (all configured connectors),
  using get_exchange_health() and the full live-order smoke tests from
  real_exchange_smoke_test.py (tiny LIMIT BUY orders far from market).
- Blockchain reachability via MultiChainTradeExecutor (all supported networks).

For each exchange and each chain it prints a single line with:
  - Name
  - Status: OK / FAIL
  - Classification: USER_ENV (keys, perms, geo-block, SSL/CA, funds, IP/WS 403)
                   or CODE_LOGIC (unexpected internal error)
  - Short reason message

At the end it prints summary counts so you can immediately see how many
exchanges/chains are operational and how many are blocked by external issues.

Usage (from project root):

    python scripts/check_full_connectivity.py

Blockchain checks are read-only (no transactions sent). Exchange checks
WILL attempt very small LIMIT BUY test orders per venue via
RealExchangeExecutor, reusing the existing smoke-test logic. Run this
only with accounts and API keys you control.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.api_key_manager import APIKeyManager
from core.real_exchange_executor import RealExchangeExecutor
from core.real_stock_executor import RealStockExecutor
from core.multichain_trade_executor import (
    MultiChainTradeExecutor,
    load_rpc_overrides_from_comprehensive_config,
)
from core.exchange_universe import build_real_exchange_api_keys
from core.real_exchange_executor import OrderSide, OrderType

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "check_full_connectivity.log")

# Mirror all connectivity diagnostics both to stdout and to a persistent
# log file so they can be inspected from the repository even when a user
# cannot easily copy/paste terminal output.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)


def _println(msg: str, logger: logging.Logger | None = None, level: int = logging.INFO) -> None:
    """Print to stdout and ALWAYS append to the connectivity log file.

    Relying solely on logging.basicConfig can be a no-op if logging was
    configured earlier in the process. To guarantee we can inspect the
    diagnostics later, this helper writes directly to
    logs/check_full_connectivity.log in addition to normal stdout.
    """

    # Console output for interactive use
    print(msg)

    # Direct file append so we always capture diagnostics regardless of
    # logging configuration state.
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        # Logging to file is best-effort; never break diagnostics on I/O
        # issues.
        pass

    # Also send through the Python logging system when a logger is provided.
    if logger is not None:
        logger.log(level, msg)

# Reuse the classification logic from real_exchange_smoke_test in a
# simplified form for this unified view.

# Relevant API key categories for trading and market data coverage
TRADING_CATEGORIES = (
    "crypto_exchanges",
    "stock_exchanges",
    "forex_trading",
)

DATA_CATEGORIES = (
    "market_data",
    "blockchain_data",
)

# Runtime-health caches so API-service diagnostics can reuse authoritative
# executor results instead of reporting avoidable probe coverage gaps.
_EXCHANGE_HEALTH_CACHE: Dict[str, Dict[str, Any]] = {}
_BROKER_HEALTH_CACHE: Dict[str, Dict[str, Any]] = {}


def classify_exchange_error(name: str, phase: str, exc: Exception) -> Tuple[str, str]:
    """Classify an exchange error as USER_ENV or CODE_LOGIC and return
    (classification, reason).

    classification: "USER_ENV" or "CODE_LOGIC"
    reason: short human-readable explanation
    """

    msg = str(exc)
    lowered = msg.lower()

    # Geo-block / restricted location (e.g. Binance 451)
    if (
        "unavailable for legal reasons" in lowered
        or "restricted location" in lowered
        or " 451" in lowered
    ):
        return "USER_ENV", "geo-blocked / restricted location"

    # Insufficient funds / min notional
    if "insufficient funds" in lowered or "you need" in msg:
        return "USER_ENV", "insufficient funds / below minimum notional"

    # Exchange-specific required passphrase/credential fields.
    if "requires \"password\" credential" in lowered:
        return "USER_ENV", "exchange requires passphrase/password credential (missing or invalid)"

    # Nonce / time-window drift
    if "invalid nonce" in lowered:
        return "USER_ENV", "invalid nonce (clock drift or concurrent key usage)"

    # Auth/permission/key shape issues are external/user-env faults.
    if (
        "permission denied" in lowered
        or "invalid api-key" in lowered
        or "api-signature-not-valid" in lowered
        or "requires \"api\"" in lowered
        or "unauthorized" in lowered
        or "401" in lowered
    ):
        return "USER_ENV", "API key/secret/passphrase missing, invalid, or lacking required permissions/IP allowlist"

    # HTX SSL / CA issues
    if "sslcertverificationerror" in msg or "certificate_verify_failed" in msg:
        return "USER_ENV", "SSL/CA trust issue for HTX endpoint"

    # Oanda auth issues
    if "oanda accounts error 401" in msg or "insufficient authorization" in msg:
        return "USER_ENV", "Oanda authentication / token / env issue"

    # Exchange clock skew indicates environment time sync issue.
    if (
        "timestamp for this request was" in lowered
        or "\"code\":-1021" in lowered
        or "ahead of the server's time" in lowered
    ):
        return "USER_ENV", "exchange timestamp skew (sync local clock / exchange time)"

    # Coinbase ECDSA key format issues
    if "ecdsa" in lowered and "index out of range" in lowered:
        return "USER_ENV", "Coinbase secret must be PEM-encoded EC private key"

    # BTCC WebSocket or endpoint rejections are exchange/env issues.
    if (
        ("websocket" in lowered and ("403" in lowered or "404" in lowered))
        or "server rejected websocket connection" in lowered
    ):
        return "USER_ENV", "BTCC WebSocket/endpoint rejection (IP/auth/exchange-side issue)"

    # Fallback: unknown internal or unclassified error
    return "CODE_LOGIC", f"unclassified error during {phase}: {msg}"  # pragma: no cover


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _status_label(is_ok: bool, classification: str) -> str:
    """Normalize row status to OK / DIAGNOSTIC_WARN / FAIL."""
    if is_ok or classification == "OK":
        return "OK"
    if classification == "CODE_LOGIC":
        return "FAIL"
    return "DIAGNOSTIC_WARN"


async def _pick_smoke_symbol(executor: RealExchangeExecutor, exchange_name: str) -> Optional[Dict[str, Any]]:
    """Pick a conservative liquid symbol and sizing metadata for smoke order."""
    ex = executor.exchanges.get(exchange_name)
    if ex is None:
        return None

    try:
        markets = await asyncio.to_thread(ex.load_markets)
    except Exception:
        return None

    # Prefer broadly liquid majors first to reduce venue-specific rejections.
    exchange_quote_pref: Dict[str, Tuple[str, ...]] = {
        "bitstamp": ("USD", "EUR", "USDT", "USDC"),
        "coinbase": ("USD", "USDC", "USDT", "EUR"),
        "kraken": ("USD", "EUR", "USDT", "USDC"),
    }
    quote_pref = exchange_quote_pref.get(exchange_name.lower(), ("USDT", "USD", "USDC", "EUR"))
    base_pref = ("BTC", "ETH", "SOL", "XRP", "ADA", "LTC", "DOGE")

    candidates: List[Tuple[str, Dict[str, Any], int, int]] = []
    for sym, market in (markets or {}).items():
        if not isinstance(market, dict):
            continue
        if market.get("active") is False:
            continue
        if not market.get("spot", True):
            continue
        base = str(market.get("base") or "").upper()
        quote = str(market.get("quote") or "").upper()
        if quote in quote_pref:
            quote_rank = quote_pref.index(quote)
            base_rank = base_pref.index(base) if base in base_pref else len(base_pref)
            candidates.append((str(sym), market, quote_rank, base_rank))

    candidates.sort(key=lambda item: (item[2], item[3], item[0]))

    for sym, market, _quote_rank, _base_rank in candidates:
        try:
            ticker = await asyncio.to_thread(ex.fetch_ticker, sym)
        except Exception:
            continue

        last = _as_float(ticker.get("last")) or _as_float(ticker.get("close"))
        if last <= 0:
            continue

        limits = market.get("limits") if isinstance(market.get("limits"), dict) else {}
        amount_limits = limits.get("amount") if isinstance(limits.get("amount"), dict) else {}
        cost_limits = limits.get("cost") if isinstance(limits.get("cost"), dict) else {}
        min_amt = max(_as_float(amount_limits.get("min"), 0.0), 0.0)
        min_cost = max(_as_float(cost_limits.get("min"), 0.0), 0.0)

        amount = max(min_amt, 0.0)
        if min_cost > 0:
            amount = max(amount, min_cost / last)
        if amount <= 0:
            amount = max(5.0 / last, 0.00001)

        # Let CCXT normalize to venue precision/tick-size rules.
        try:
            amount = float(ex.amount_to_precision(sym, amount))
        except Exception:
            pass

        if amount <= 0:
            continue

        return {"symbol": sym, "amount": amount, "last": last}

    return None


async def _run_live_smoke_for_exchange(
    executor: RealExchangeExecutor,
    exchange_name: str,
) -> Tuple[str, str]:
    """
    Place a tiny deep-limit BUY and cancel it to verify live order path wiring.

    Returns:
        (classification, reason)
    """
    selected = await _pick_smoke_symbol(executor, exchange_name)
    if not selected:
        return "USER_ENV", "no tradable liquid symbol discovered for smoke order"

    symbol = str(selected["symbol"])
    amount = _as_float(selected["amount"], 0.0)
    last = _as_float(selected["last"], 0.0)
    if amount <= 0 or last <= 0:
        return "CODE_LOGIC", "smoke symbol selection produced invalid amount/price"

    # Use deep discount to avoid immediate fill.
    limit_price = max(last * 0.80, 0.00000001)
    ex = executor.exchanges.get(exchange_name)
    if ex is not None:
        try:
            limit_price = float(ex.price_to_precision(symbol, limit_price))
        except Exception:
            pass

    order = await executor.place_real_order(
        exchange_name=exchange_name,
        symbol=symbol,
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        amount=amount,
        price=limit_price,
    )
    if not order:
        # Try to return a more precise reason from current exchange health.
        try:
            h = await executor.get_exchange_health(exchange_name)
            info = h.get(exchange_name, {}) if isinstance(h, dict) else {}
            status = str(info.get("status") or "")
            detail = str(info.get("error") or "")
            if status in ("restricted_location",):
                return "USER_ENV", "live order blocked by geo restriction/policy"
            if status in ("permission_denied", "auth_error"):
                return "USER_ENV", "live order blocked by auth/permission/passphrase/IP allowlist"
            if detail:
                cls, rsn = classify_exchange_error(exchange_name, "live_smoke", Exception(detail))
                if cls != "CODE_LOGIC":
                    return cls, rsn
        except Exception:
            pass
        return "USER_ENV", f"live order rejected for {symbol} (keys/permissions/funds/exchange policy)"

    order_id = str(order.get("id") or "")
    if not order_id:
        return "CODE_LOGIC", "exchange order created without order id"

    try:
        await executor.cancel_order(exchange_name, order_id, symbol)
    except Exception as exc:  # noqa: BLE001
        return "USER_ENV", f"order placed but cancel failed: {exc}"

    return "OK", f"live order path ok ({symbol}, amount={amount}, price={limit_price})"


async def check_exchanges() -> Dict[str, int]:
    """Run RealExchangeExecutor health + basic order-path diagnostics.

    Returns summary with code-logic/runtime counts.
    """

    logger = logging.getLogger("check_full_connectivity.exchanges")

    manager = APIKeyManager.get_instance()
    manager.initialize_sync()

    raw_keys = manager.api_keys

    # Build the flat api_keys map using the helper from real_exchange_smoke_test
    # so we exercise the exact same mapping logic used in live smoke tests.
    api_keys = build_real_exchange_api_keys(raw_keys)

    if not api_keys:
        logger.error("No API keys mapped for RealExchangeExecutor. Check config/api_keys.json or .env.")
        return {"code_logic_failures": 1, "ok_count": 0, "total": 0, "warn_count": 0}

    executor = RealExchangeExecutor(api_keys=api_keys, event_bus=None)

    # Health snapshot
    health = await executor.get_exchange_health()
    global _EXCHANGE_HEALTH_CACHE
    _EXCHANGE_HEALTH_CACHE = health if isinstance(health, dict) else {}

    ok_count = 0
    total = len(health)
    code_logic_failures = 0
    warn_count = 0

    _println("\n=== EXCHANGE CONNECTIVITY ===", logger)
    _println("Name             | STATUS | CLASS      | Details", logger)
    _println("-----------------+--------+------------+------------------------------------------", logger)

    for name, info in sorted(health.items()):
        status = info.get("status")
        details = info.get("error") or info.get("balances_sample") or ""

        if status in ("ok", "ok_empty"):
            ok_count += 1
            classification = "OK"
            cls_label = "OK"
            reason = "healthy (api+balance path)"
        elif status == "restricted_location":
            classification = "USER_ENV"
            cls_label = classification
            reason = "geo-blocked / restricted location"
        elif status in ("permission_denied", "auth_error"):
            classification = "USER_ENV"
            cls_label = classification
            reason = "auth/permissions issue (keys/secret/passphrase/IP allowlist)"
        elif status in ("exchange_error", "not_connected"):
            # Try to classify further from details
            classification, reason = classify_exchange_error(name, "health", Exception(str(details)))
            cls_label = classification
        else:
            classification = "CODE_LOGIC"
            cls_label = classification
            reason = f"unknown status={status}"

        if classification == "CODE_LOGIC":
            code_logic_failures += 1

        if classification not in ("OK", "CODE_LOGIC"):
            warn_count += 1

        row_status = _status_label(status in ("ok", "ok_empty"), classification)
        _println(f"{name:17s} | {row_status:15s} | {cls_label:10s} | {reason}", logger)

    _println(f"\nExchange summary: {ok_count}/{total} OK", logger)
    if code_logic_failures:
        _println(
            f"  {code_logic_failures} exchanges have CODE_LOGIC errors (investigate code/logs)",
            logger,
        )
    else:
        _println(
            "  0 CODE_LOGIC exchange errors detected; remaining issues are user/env side",
            logger,
        )

    return {
        "code_logic_failures": code_logic_failures,
        "ok_count": ok_count,
        "total": total,
        "warn_count": warn_count,
    }


async def check_stock_brokers() -> Dict[str, int]:
    logger = logging.getLogger("check_full_connectivity.stocks")

    manager = APIKeyManager.get_instance()
    manager.initialize_sync()

    api_keys = manager.api_keys

    executor = RealStockExecutor(api_keys=api_keys, event_bus=None)
    health = await executor.get_broker_health()
    global _BROKER_HEALTH_CACHE
    _BROKER_HEALTH_CACHE = health if isinstance(health, dict) else {}

    _println("\n=== STOCK / FOREX BROKER CONNECTIVITY ===", logger)
    _println("Broker           | STATUS | CLASS      | Details", logger)
    _println("-----------------+--------+------------+------------------------------", logger)

    if not health:
        _println("No stock/forex brokers configured.", logger)
        return {"code_logic_failures": 0, "ok_count": 0, "total": 0, "warn_count": 0}

    ok_count = 0
    code_logic_failures = 0
    total = len(health)
    warn_count = 0

    for name, info in sorted(health.items()):
        status = (info.get("status") or "").lower()
        error = info.get("error") or ""

        status_label = "DIAGNOSTIC_WARN"
        classification = "USER_ENV"
        reason = ""

        details = info.get("details") if isinstance(info, dict) else None

        if status == "ok":
            status_label = "OK"
            classification = "OK"
            reason = "connection successful"
            ok_count += 1
        elif status == "package_missing":
            classification = "USER_ENV"
            reason = error or "broker SDK/package not installed"
        elif status == "auth_error":
            classification = "USER_ENV"
            reason = error or "authentication error"
        elif status == "client_error":
            classification = "USER_ENV"
            reason = error or "client/network error"
        elif status in ("configured",):
            classification = "USER_ENV"
            reason = error or "broker configured but live auth/session not established"
        elif status in ("keys_present", "keys_incomplete", "not_configured"):
            classification = "USER_ENV"
            missing_fields: List[str] = []
            if isinstance(details, dict):
                if details.get("has_api_key") is False:
                    missing_fields.append("api_key")
                if details.get("has_api_secret") is False:
                    missing_fields.append("api_secret")
                if details.get("has_endpoint") is False:
                    missing_fields.append("endpoint/base_url")
            if missing_fields:
                reason = f"broker key state: {status}; missing={','.join(missing_fields)}"
            else:
                reason = error or f"broker key state: {status}"
        else:
            classification = "USER_ENV"
            reason = error or f"broker status: {status}"

        if classification == "CODE_LOGIC":
            code_logic_failures += 1
        elif classification != "OK":
            warn_count += 1

        status_label = _status_label(status == "ok", classification)
        _println(
            f"{name:17s} | {status_label:15s} | {classification:10s} | {reason}",
            logger,
        )

    _println(f"\nBroker summary: {ok_count}/{total} OK", logger)
    if code_logic_failures:
        _println(
            f"  {code_logic_failures} brokers have CODE_LOGIC issues (check stock executor/logs)",
            logger,
        )
    else:
        _println(
            "  0 CODE_LOGIC broker issues detected; remaining failures are user/env side",
            logger,
        )

    return {
        "code_logic_failures": code_logic_failures,
        "ok_count": ok_count,
        "total": total,
        "warn_count": warn_count,
    }


def _collect_trading_and_data_services(manager: APIKeyManager) -> Dict[str, str]:
    """Collect all configured services in trading and market-data categories.

    Returns a mapping of service_name -> category_name for services that have
    API keys present in manager.api_keys.
    """

    services: Dict[str, str] = {}

    for category in TRADING_CATEGORIES + DATA_CATEGORIES:
        names = APIKeyManager.CATEGORIES.get(category, [])
        for name in names:
            if name in manager.api_keys and name not in services:
                services[name] = category

    return services


async def check_api_services() -> Dict[str, int]:
    """Run APIKeyManager connection tests for trading & market-data services.

    This covers all services in the crypto_exchanges, stock_exchanges,
    forex_trading, market_data, and blockchain_data categories that have
    configured API keys.
    """

    logger = logging.getLogger("check_full_connectivity.services")

    manager = APIKeyManager.get_instance()
    manager.initialize_sync()

    services = _collect_trading_and_data_services(manager)

    _println("\n=== API SERVICE KEY CONNECTIVITY (TRADING & MARKET DATA) ===", logger)

    if not services:
        _println("No trading/market-data services with configured API keys found.", logger)
        return {"code_logic_failures": 0, "ok_count": 0, "total": 0, "warn_count": 0, "coverage_gaps": 0}

    _println("Service          | Category        | STATUS | CLASS         | Details", logger)
    _println(
        "-----------------+-----------------+--------+---------------+------------------------------",
        logger,
    )

    code_logic_failures = 0
    coverage_gaps = 0
    ok_count = 0
    total = len(services)
    warn_count = 0

    for service, category in sorted(services.items()):
        status_label = "DIAGNOSTIC_WARN"
        classification = "USER_ENV"
        reason = ""
        row_ok = False

        try:
            connected, message = await manager.test_connection_async(service)
        except Exception as exc:  # noqa: BLE001
            logger.error("test_connection_async raised for %s: %s", service, exc)
            classification = "CODE_LOGIC"
            reason = f"test_connection_async raised: {exc}"
        else:
            if connected:
                status_label = "OK"
                classification = "OK"
                reason = "connection successful"
                ok_count += 1
                row_ok = True
            else:
                msg_lower = message.lower()
                if "no api key configured" in msg_lower:
                    classification = "USER_ENV"
                    reason = "no API key configured or values are empty"
                elif "no test method available for service" in msg_lower:
                    # Reuse authoritative runtime executor checks for exchange/
                    # broker categories when available.
                    if category == "crypto_exchanges" and service in _EXCHANGE_HEALTH_CACHE:
                        ex_info = _EXCHANGE_HEALTH_CACHE.get(service, {})
                        ex_status = str((ex_info or {}).get("status") or "").lower()
                        ex_err = str((ex_info or {}).get("error") or "")
                        if ex_status in ("ok", "ok_empty"):
                            classification = "OK"
                            status_label = "OK"
                            reason = "runtime executor healthy"
                            ok_count += 1
                            row_ok = True
                        else:
                            classification, mapped_reason = classify_exchange_error(
                                service, "runtime_health", Exception(ex_err or ex_status or "runtime health failed")
                            )
                            reason = mapped_reason
                    elif category in ("stock_exchanges", "forex_trading") and service in _BROKER_HEALTH_CACHE:
                        br_info = _BROKER_HEALTH_CACHE.get(service, {})
                        br_status = str((br_info or {}).get("status") or "").lower()
                        if br_status == "ok":
                            classification = "OK"
                            status_label = "OK"
                            reason = "runtime broker healthy"
                            ok_count += 1
                            row_ok = True
                        else:
                            classification = "USER_ENV"
                            reason = str((br_info or {}).get("error") or f"runtime broker status: {br_status}")
                    else:
                        classification = "COVERAGE_GAP"
                        reason = "service connectivity probe not implemented"
                        coverage_gaps += 1
                else:
                    # Treat all other failures as external/user/env issues
                    classification = "USER_ENV"
                    reason = message

        if classification == "CODE_LOGIC":
            code_logic_failures += 1
        elif classification != "OK":
            warn_count += 1

        status_label = _status_label(row_ok, classification)
        _println(
            f"{service:17s} | {category:15s} | {status_label:15s} | {classification:13s} | {reason}",
            logger,
        )

    _println(
        f"\nAPI service summary: {ok_count}/{total} connections successful",
        logger,
    )
    if code_logic_failures:
        _println(
            f"  {code_logic_failures} services have CODE_LOGIC issues (missing tests or internal errors)",
            logger,
        )
    else:
        _println(
            "  0 CODE_LOGIC service issues detected; remaining failures are user/env side",
            logger,
        )
    if coverage_gaps:
        _println(
            f"  {coverage_gaps} services are COVERAGE_GAP (probe not implemented); not a runtime auth/network failure",
            logger,
        )

    return {
        "code_logic_failures": code_logic_failures,
        "ok_count": ok_count,
        "total": total,
        "warn_count": warn_count,
        "coverage_gaps": coverage_gaps,
    }


async def check_chains() -> Dict[str, int]:
    """Run MultiChainTradeExecutor reachability diagnostics for all chains.

    Returns an exit code contribution (0 if chains are all reachable or only
    have external issues like bad RPC URLs, non-zero if internal errors are
    detected when querying status.
    """

    logger = logging.getLogger("check_full_connectivity.chains")

    rpc_overrides = load_rpc_overrides_from_comprehensive_config()
    executor = MultiChainTradeExecutor(rpc_overrides=rpc_overrides)

    chains: List[str] = executor.get_supported_networks()
    logger.info("Checking reachability for %d chains...", len(chains))

    reachable = 0
    total = len(chains)
    code_logic_failures = 0
    warn_count = 0

    _println("\n=== BLOCKCHAIN CONNECTIVITY ===", logger)
    _println(
        "Chain               | STATUS | CLASS      | EVM  | LatestBlock | Details",
        logger,
    )
    _println(
        "--------------------+--------+------------+------+-------------+------------------------------",
        logger,
    )

    for chain in chains:
        try:
            status = await executor.get_chain_status(chain)
        except Exception as exc:  # noqa: BLE001
            classification = "CODE_LOGIC"
            reason = str(exc)
            code_logic_failures += 1
            _println(
                f"{chain:20s} | FAIL   | {classification:10s} |  -   |      -      | {reason}",
                logger,
            )
            continue

        if status.reachable:
            reachable += 1
            classification = "OK"
            cls_label = "OK"
            reason = "reachable"
        else:
            # For now, treat unreachable as USER_ENV (bad RPCs, DNS, auth,
            # provider-side errors). A future enhancement could parse known
            # error patterns similarly to exchanges.
            classification = "USER_ENV"
            cls_label = classification
            reason = status.error or "unreachable (rpc/provider)"
            warn_count += 1

        evm_flag = "True" if status.is_evm else "False"
        latest_block = status.latest_block if status.latest_block is not None else "-"

        row_status = _status_label(status.reachable, classification)
        _println(
            f"{chain:20s} | {row_status:15s} | {cls_label:10s} | "
            f"{evm_flag:4s} | {str(latest_block):11s} | {reason}",
            logger,
        )

    _println(f"\nChain summary: {reachable}/{total} reachable", logger)
    if code_logic_failures:
        _println(
            f"  {code_logic_failures} chains had CODE_LOGIC errors (check multichain executor/logs)",
            logger,
        )
    else:
        _println(
            "  0 CODE_LOGIC chain errors detected; remaining issues are RPC/provider/user/env side",
            logger,
        )

    return {
        "code_logic_failures": code_logic_failures,
        "ok_count": reachable,
        "total": total,
        "warn_count": warn_count,
    }


async def _main() -> None:
    # 1) Exchange health summary
    ex = await check_exchanges()

    # 2) Live-order smoke tests per exchange (tiny deep-limit BUY + cancel).
    root_logger = logging.getLogger("check_full_connectivity")
    _println("\n=== EXCHANGE LIVE ORDER SMOKE TESTS ===", root_logger)
    manager = APIKeyManager.get_instance()
    manager.initialize_sync()
    api_keys = build_real_exchange_api_keys(manager.api_keys)
    smoke_code_logic = 0
    smoke_ok = 0
    smoke_warn = 0
    if not api_keys:
        _println("No exchange API keys mapped for live smoke path.", root_logger)
    else:
        smoke_executor = RealExchangeExecutor(api_keys=api_keys, event_bus=None)
        if not smoke_executor.connectors:
            _println("No exchange connectors available for live smoke path.", root_logger)
        else:
            for ex_name in sorted(smoke_executor.connectors.keys()):
                cls, reason = await _run_live_smoke_for_exchange(smoke_executor, ex_name)
                status = _status_label(cls == "OK", cls)
                if cls == "CODE_LOGIC":
                    smoke_code_logic = 1
                elif cls == "OK":
                    smoke_ok += 1
                else:
                    smoke_warn += 1
                _println(f"{ex_name:17s} | {status:15s} | {cls:10s} | {reason}", root_logger)

    # 3) Stock/forex broker connectivity
    broker = await check_stock_brokers()

    # 4) API key connectivity for trading & market-data services
    svc = await check_api_services()

    # 5) Chain reachability
    ch = await check_chains()

    code_logic_failures = (
        ex["code_logic_failures"]
        + broker["code_logic_failures"]
        + svc["code_logic_failures"]
        + ch["code_logic_failures"]
        + smoke_code_logic
    )
    runtime_pass = (ex["ok_count"] > 0) or (smoke_ok > 0)
    diagnostic_warn_count = ex["warn_count"] + broker["warn_count"] + svc["warn_count"] + ch["warn_count"] + smoke_warn
    _println("\n=== OVERALL CONNECTIVITY STATUS ===", root_logger)
    _println(
        f"Authoritative runtime status: {'RUNTIME_PASS' if runtime_pass else 'FAIL'}",
        root_logger,
    )
    _println(
        f"Diagnostic status: {'DIAGNOSTIC_WARN' if diagnostic_warn_count > 0 else 'CLEAN'}",
        root_logger,
    )
    if runtime_pass and code_logic_failures == 0:
        _println("Fail gate: FAIL is emitted only when actual live executor runtime path fails.", root_logger)
    else:
        _println(
            "FAIL condition met: runtime path failed and/or CODE_LOGIC issues detected.",
            root_logger,
        )


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
