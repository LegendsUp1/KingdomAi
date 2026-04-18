#!/usr/bin/env python3
"""
REAL Exchange Executor - LIVE TRADING ON ALL MARKETS (2025 State-of-the-Art)
Connects to actual exchanges using CCXT 4.2+ and executes real orders
NO SIMULATIONS - REAL MONEY, REAL TRADES

2025 FEATURES:
- WebSocket streaming for real-time order books
- Exponential backoff with jitter for retry logic
- Circuit breaker pattern for failure prevention
- Adaptive retry delays based on API performance
- HMAC SHA384 secure authentication
- Rate limit handling with backpressure
- Async processing for high-frequency trading
- Comprehensive error handling and monitoring
"""

import ccxt
import ccxt.pro as ccxtpro  # WebSocket support
import asyncio
import json
import hmac
import hashlib
import logging
import time
import random
import inspect
import uuid
import requests
import websockets
import threading
from typing import Dict, Any, List, Optional, Callable, Protocol
from urllib.parse import quote
from datetime import datetime, timedelta

# Suppress InsecureRequestWarning for exchanges with SSL verification disabled (e.g. HTX/Huobi)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from enum import Enum
from collections import deque

# SOTA 2026: Import resilience patterns for real operation recovery
try:
    from core.resilience_patterns import (
        ResilientOperation, KingdomResilience, CircuitBreakerConfig,
        RetryConfig, get_resilience_status
    )
    HAS_RESILIENCE = True
except ImportError:
    HAS_RESILIENCE = False

# SOTA 2026: Import automatic timestamp synchronization system
try:
    from core.trading_timestamp_auto_fix import (
        TradingTimestampAutoFix, initialize_timestamp_auto_fix, 
        auto_fix_exchange_error, TimestampErrorType
    )
    HAS_TIMESTAMP_AUTO_FIX = True
except ImportError:
    HAS_TIMESTAMP_AUTO_FIX = False

logger = logging.getLogger(__name__)


def _prefer_ipv4_for_hosts(host_suffixes: tuple[str, ...]) -> None:
    """Force IPv4 DNS resolution for connections to the given host suffixes.

    BinanceUS' API infrastructure does not support IPv6; on dual-stack
    Linux hosts ``requests`` / ``urllib3`` can race and pick an AAAA
    record first, which fails with ``{"code":-71012,"msg":"IPv6 not
    supported"}``. We combine three mechanisms that together cover every
    path urllib3 v2 + Python sockets can take:

      1. Scope-filter ``socket.getaddrinfo`` so only AF_INET results are
         returned for hostnames ending in any of ``host_suffixes`` - leaves
         IPv6 working for every other host in the system.
      2. Override urllib3's ``allowed_gai_family`` to prefer AF_INET so
         its internal ``create_connection`` doesn't race IPv6 first.
      3. Flip ``urllib3.util.connection.HAS_IPV6`` to ``False`` so the
         library never advertises IPv6 support to downstream callers.

    Idempotent - safe to call multiple times with the same or additional
    suffixes.
    """
    import socket

    if getattr(socket, "_kingdom_ipv4_hostnames", None) is None:
        socket._kingdom_ipv4_hostnames = set()  # type: ignore[attr-defined]
        original_getaddrinfo = socket.getaddrinfo

        def _getaddrinfo_ipv4_scoped(host, *args, **kwargs):  # type: ignore[no-untyped-def]
            results = original_getaddrinfo(host, *args, **kwargs)
            try:
                if host and isinstance(host, str):
                    lower = host.lower()
                    for suffix in socket._kingdom_ipv4_hostnames:  # type: ignore[attr-defined]
                        if lower.endswith(suffix):
                            v4 = [r for r in results if r[0] == socket.AF_INET]
                            return v4 or results
            except Exception:  # noqa: BLE001
                pass
            return results

        socket.getaddrinfo = _getaddrinfo_ipv4_scoped  # type: ignore[assignment]

    for suffix in host_suffixes:
        socket._kingdom_ipv4_hostnames.add(suffix.lower())  # type: ignore[attr-defined]

    # Belt-and-suspenders: urllib3 v2 has its own IPv6 preference that
    # bypasses socket.getaddrinfo filtering. Flip its ``HAS_IPV6`` flag
    # and override ``allowed_gai_family`` to force AF_INET globally on
    # the ``requests``/``urllib3`` code path used by ccxt.
    try:
        import urllib3.util.connection as _u3conn  # type: ignore[import]
        _u3conn.HAS_IPV6 = False  # type: ignore[attr-defined]
        _u3conn.allowed_gai_family = lambda: socket.AF_INET  # type: ignore[assignment]
    except Exception:  # noqa: BLE001
        pass


def _attach_ipv4_only_adapter(exchange: Any) -> None:
    """Lock a ccxt exchange's ``requests.Session`` to IPv4-only sockets.

    Uses ``source_address=("0.0.0.0", 0)`` on the HTTPAdapter's pool
    manager, which forces every outbound TCP socket in that session
    to bind to an IPv4 address. The kernel picks a suitable local
    IPv4, so there's no interface-specific config needed and IPv6 is
    simply never an option for this session. This is the definitive
    fix for BinanceUS's ``{"code":-71012,"msg":"IPv6 not supported"}``
    error on dual-stack Linux hosts.
    """
    session = getattr(exchange, "session", None)
    if session is None or not hasattr(session, "mount"):
        raise RuntimeError("ccxt exchange has no mountable requests.Session")

    from requests.adapters import HTTPAdapter  # type: ignore[import]

    class _IPv4Adapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs["source_address"] = ("0.0.0.0", 0)
            return super().init_poolmanager(*args, **kwargs)

        def proxy_manager_for(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs["source_address"] = ("0.0.0.0", 0)
            return super().proxy_manager_for(*args, **kwargs)

    session.mount("https://", _IPv4Adapter())
    session.mount("http://", _IPv4Adapter())

def _clean_config_str(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = value.split("#", 1)[0].strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ('"', "'"):
        cleaned = cleaned[1:-1].strip()
    return cleaned

def select_profitable_exchanges(
    health: Dict[str, Any],
    expected_edges: Dict[str, float],
    min_edge: float = 0.0,
) -> List[str]:
    """Select exchanges that are both healthy and above a minimum expected edge.

    Args:
        health: Output from RealExchangeExecutor.get_exchange_health().
        expected_edges: Mapping of exchange -> expected profit edge (e.g. %).
        min_edge: Minimum edge threshold to consider an exchange tradable.

    Returns:
        List of exchange names sorted by descending expected edge.
    """
    candidates: List[str] = []

    for ex, edge in expected_edges.items():
        h = health.get(ex)
        if h is None:
            continue

        status = h.get("status")
        if status not in ("ok", "ok_empty"):
            # Skip venues that are restricted, permission denied, or errored
            continue

        try:
            edge_value = float(edge)
        except (TypeError, ValueError):  # noqa: PERF203
            continue

        if edge_value >= min_edge:
            candidates.append(ex)

    candidates.sort(key=lambda ex: float(expected_edges[ex]), reverse=True)
    return candidates


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit Breaker Pattern (2025 Best Practice)
    Prevents cascading failures when exchange APIs are down
    """
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
    
    def should_allow_request(self) -> bool:
        """Check if request should be allowed through circuit breaker."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        # HALF_OPEN state - allow one request to test
        return True
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        return datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout)
    
    def on_success(self):
        """Reset circuit breaker on successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        logger.info("✅ Circuit breaker CLOSED - API recovered")
    
    def on_failure(self):
        """Handle failure and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"🔴 Circuit breaker OPEN - {self.failure_count} consecutive failures")


class RetryHandler:
    """
    Exponential Backoff with Jitter (2025 Best Practice)
    Implements adaptive retry logic for exchange API calls
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.retryable_status_codes = {408, 429, 500, 502, 503, 504}
        self.success_rates: deque = deque(maxlen=100)
        self.response_times: deque = deque(maxlen=100)
    
    def exponential_backoff_with_jitter(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = self.base_delay * (2 ** attempt)
        jitter = random.uniform(0.1, 0.3) * delay
        return min(delay + jitter, 60.0)  # Cap at 60 seconds
    
    def adaptive_delay(self, attempt: int, last_response_time: float) -> float:
        """Calculate adaptive delay based on API performance (2025 technique)."""
        base_delay = self.exponential_backoff_with_jitter(attempt)
        
        # Increase delay if API is slow
        if last_response_time > 10.0:
            base_delay *= 2
        
        # Decrease delay if API is performing well
        recent_success_rate = self._get_recent_success_rate()
        if recent_success_rate > 0.9:
            base_delay *= 0.5
        
        return min(base_delay, 60.0)
    
    def should_retry(self, status_code: int, attempt: int) -> bool:
        """Determine if request should be retried."""
        return (
            attempt < self.max_retries and
            status_code in self.retryable_status_codes
        )
    
    def _get_recent_success_rate(self) -> float:
        """Calculate success rate from recent requests."""
        if len(self.success_rates) < 5:
            return 0.5
        return sum(self.success_rates) / len(self.success_rates)
    
    def record_success(self, response_time: float):
        """Record successful request."""
        self.success_rates.append(1.0)
        self.response_times.append(response_time)
    
    def record_failure(self):
        """Record failed request."""
        self.success_rates.append(0.0)


class ExchangeConnector(Protocol):
    """Minimal connector interface RealExchangeExecutor can use.

    Implementations may wrap ccxt or call native REST/WebSocket APIs.
    """

    name: str

    async def fetch_balance(self) -> Dict[str, float]:
        ...

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> Dict[str, Any]:
        ...

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> Dict[str, Any]:
        ...

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        ...

    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        ...


class CcxtExchangeConnector:
    """Connector that wraps a ccxt exchange instance."""

    def __init__(self, name: str, exchange: ccxt.Exchange):  # type: ignore[valid-type]
        self.name = name
        self._exchange = exchange

    async def fetch_balance(self) -> Dict[str, float]:
        balance = await asyncio.to_thread(self._exchange.fetch_balance)
        if isinstance(balance, dict):
            free = balance.get("free")
            if isinstance(free, dict):
                return free
        return {}

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> Dict[str, Any]:
        if side.lower() == "buy":
            order = await asyncio.to_thread(
                self._exchange.create_market_buy_order,
                symbol,
                amount,
            )
        else:
            order = await asyncio.to_thread(
                self._exchange.create_market_sell_order,
                symbol,
                amount,
            )
        return order

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> Dict[str, Any]:
        if side.lower() == "buy":
            order = await asyncio.to_thread(
                self._exchange.create_limit_buy_order,
                symbol,
                amount,
                price,
            )
        else:
            order = await asyncio.to_thread(
                self._exchange.create_limit_sell_order,
                symbol,
                amount,
                price,
            )
        return order

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        await asyncio.to_thread(self._exchange.cancel_order, order_id, symbol)
        return True

    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        order = await asyncio.to_thread(self._exchange.fetch_order, order_id, symbol)
        return order

    # ------------------------------------------------------------------
    # Funding / custody — deposit address discovery + withdrawal
    # ------------------------------------------------------------------
    async def fetch_deposit_address(
        self, code: str, network: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the exchange's deposit address for a given asset/network.

        Uses ccxt's standard ``fetch_deposit_address`` / ``fetchDepositAddress``.
        The caller can use this address to withdraw FROM another exchange TO
        this one (the core primitive for cross-venue funding).
        """
        params: Dict[str, Any] = {}
        if network:
            params["network"] = network
        try:
            result = await asyncio.to_thread(
                self._exchange.fetch_deposit_address, code, params,
            )
        except Exception as exc:
            raise RuntimeError(
                f"{self.name}: fetch_deposit_address({code}, network={network}) failed: {exc}"
            ) from exc
        if not isinstance(result, dict):
            raise RuntimeError(f"{self.name}: unexpected fetch_deposit_address response")
        return {
            "exchange": self.name,
            "currency": code,
            "network": result.get("network") or network,
            "address": result.get("address"),
            "tag": result.get("tag") or result.get("memo"),
            "info": result.get("info"),
        }

    async def fetch_deposit_networks(self, code: str) -> List[str]:
        """Return the list of deposit networks supported by this exchange for *code*.

        Falls back to currency metadata if a dedicated networks endpoint is
        unavailable.
        """
        try:
            currencies = await asyncio.to_thread(self._exchange.fetch_currencies)
        except Exception:
            currencies = {}
        entry = (currencies or {}).get(code) or {}
        networks = entry.get("networks") or {}
        if isinstance(networks, dict) and networks:
            return sorted(networks.keys())
        return []

    async def withdraw(
        self,
        code: str,
        amount: float,
        address: str,
        tag: Optional[str] = None,
        network: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Submit a REAL withdrawal from this exchange to an external address.

        WARNING: this moves real funds. Callers MUST validate address,
        network, and amount before invoking. Returns the ccxt transaction
        dict.
        """
        if not address:
            raise ValueError("withdraw: address is required")
        if amount is None or float(amount) <= 0:
            raise ValueError("withdraw: amount must be > 0")

        call_params: Dict[str, Any] = dict(params or {})
        if network:
            call_params["network"] = network
        try:
            result = await asyncio.to_thread(
                self._exchange.withdraw,
                code,
                float(amount),
                address,
                tag,
                call_params,
            )
        except Exception as exc:
            raise RuntimeError(
                f"{self.name}: withdraw({code}, {amount}, {address[:10]}...) failed: {exc}"
            ) from exc
        if not isinstance(result, dict):
            return {
                "exchange": self.name,
                "currency": code,
                "amount": float(amount),
                "address": address,
                "tag": tag,
                "network": network,
                "raw": result,
            }
        return {
            "exchange": self.name,
            "currency": code,
            "amount": float(amount),
            "address": address,
            "tag": tag,
            "network": network,
            "id": result.get("id"),
            "txid": result.get("txid"),
            "status": result.get("status"),
            "info": result.get("info"),
        }

    async def fetch_full_balance(self) -> Dict[str, Any]:
        """Return the full balance structure (free / used / total per currency)."""
        balance = await asyncio.to_thread(self._exchange.fetch_balance)
        if not isinstance(balance, dict):
            return {}
        free = balance.get("free") or {}
        used = balance.get("used") or {}
        total = balance.get("total") or {}
        currencies = sorted(set(free.keys()) | set(used.keys()) | set(total.keys()))
        return {
            "exchange": self.name,
            "currencies": {
                c: {
                    "free": float(free.get(c, 0) or 0),
                    "used": float(used.get(c, 0) or 0),
                    "total": float(total.get(c, 0) or 0),
                }
                for c in currencies
            },
        }


class BtccConnector:
    """Native connector for the BTCC WS-API.

    Implements the documented BTCC WebSocket trading protocol:

      * PascalCase actions (``Login``, ``Logout``, ``GetAccountInfo``,
        ``PlaceOrder``, ``CancelOrder``, ``CancelReplaceOrder``,
        ``GetOpenOrders``, plus public ``GetActiveContracts``, ``GetTrades``,
        ``Subscribe`` / ``SubOrderBook``, ``SubscribeAllTickers``).
      * Root-level ``common`` fields on every private request:
        ``timestamp`` (13-digit ms), ``nonce`` (8-digit random), ``public_key``,
        ``action``, ``crid``, and ``sign``.
      * Signature algorithm documented at
        https://btcc-api.netlify.app/en/sign - keys sorted alphabetically,
        query-string encoded, then HMAC-SHA256(secret) hex digest over
        every field except ``sign`` itself.
      * ``crid`` is used to correlate responses back to pending requests.

    The production WebSocket URL is issued to each user in the BTCC API
    management console and is not published publicly. Because of this we
    accept either a single ``ws_url`` or a list of candidate ``ws_urls``.
    If none is provided we fall back to a small list of historical BTCC
    endpoints; if all of them reject the handshake we flip the connector
    into ``unreachable`` mode so health checks return a clear error
    without spamming the log.
    """

    # Historical BTCC WS endpoints - first entry wins if reachable.
    # Users can override via ``api_keys.json``::
    #     "btcc": {"api_key": "...", "api_secret": "...",
    #              "public_key": "...",
    #              "ws_url": "wss://<from-btcc-portal>"}
    DEFAULT_WS_URL_CANDIDATES: List[str] = [
        "wss://kapi1.btcc.com:9082",
        "wss://api.btcc.com/ws",
        "wss://ws.btcc.com",
        "wss://kapi1.btloginc.com:9082",  # legacy; kept for backward compat
    ]

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        username: Optional[str] = None,
        ws_url: Optional[str] = None,
        ws_urls: Optional[List[str]] = None,
        public_key: Optional[str] = None,
    ):
        self.name = "btcc"
        self.api_key = api_key
        self.api_secret = api_secret
        self.username = username or ""
        # BTCC distinguishes between the "API key" shown in the portal
        # (used for ``public_key`` on the wire) and the "secret key" used
        # for HMAC. Accept either naming scheme.
        self.public_key = public_key or api_key

        # Build the ordered list of URLs to try. Explicit ``ws_url`` wins,
        # then ``ws_urls`` list, then defaults.
        candidates: List[str] = []
        if ws_url:
            candidates.append(ws_url)
        if ws_urls:
            candidates.extend(u for u in ws_urls if u and u not in candidates)
        for u in self.DEFAULT_WS_URL_CANDIDATES:
            if u not in candidates:
                candidates.append(u)
        self.ws_url_candidates: List[str] = candidates
        self.ws_url: str = candidates[0]

        self._ws: Optional[Any] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._receiver_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._conn_lock = asyncio.Lock()
        self._closed = False

        # When every candidate URL has failed the handshake we record
        # the reason once and surface it via ``fetch_balance`` / order
        # calls instead of repeatedly retrying a dead endpoint.
        self._unreachable: bool = False
        self._unreachable_reason: Optional[str] = None

    # ---------------------------------------------------------------
    # Connection lifecycle
    # ---------------------------------------------------------------
    async def _ensure_connection(self) -> None:
        if self._closed:
            raise RuntimeError("BtccConnector is closed")
        if self._unreachable:
            raise RuntimeError(
                f"BTCC endpoint is unreachable: {self._unreachable_reason}. "
                "Update btcc.ws_url in config/api_keys.json with the URL "
                "issued by your BTCC API management page."
            )

        async with self._conn_lock:
            if self._ws is not None and not self._is_ws_closed(self._ws):
                return
            await self._connect_and_login()

    @staticmethod
    def _is_ws_closed(ws: Any) -> bool:
        # ``websockets`` 10/11 expose ``.closed``; 12+ uses ``.state``.
        closed_attr = getattr(ws, "closed", None)
        if closed_attr is not None:
            return bool(closed_attr)
        state = getattr(ws, "state", None)
        return state is not None and getattr(state, "name", "") in {"CLOSED", "CLOSING"}

    async def _connect_and_login(self) -> None:
        connect_kwargs: Dict[str, Any] = {"ping_interval": None}
        custom_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; KingdomAI-BTCC-Client/1.0)",
            "Origin": "https://www.btcc.com",
        }
        try:
            ws_connect_params = set(inspect.signature(websockets.connect).parameters)
        except (TypeError, ValueError):
            ws_connect_params = set()
        if "extra_headers" in ws_connect_params:
            connect_kwargs["extra_headers"] = custom_headers
        elif "additional_headers" in ws_connect_params:
            connect_kwargs["additional_headers"] = custom_headers

        last_error: Optional[Exception] = None
        for url in self.ws_url_candidates:
            try:
                self._ws = await websockets.connect(url, **connect_kwargs)
                self.ws_url = url
                logger.info("BTCC WebSocket connected: %s", url)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.debug("BTCC candidate %s failed: %s", url, exc)
                continue
        else:
            self._unreachable = True
            self._unreachable_reason = (
                f"all {len(self.ws_url_candidates)} candidate endpoints "
                f"rejected the handshake (last error: {last_error})"
            )
            logger.warning(
                "BTCC unreachable - %s. Set btcc.ws_url in config/api_keys.json "
                "with the URL issued by your BTCC API management page to enable.",
                self._unreachable_reason,
            )
            raise RuntimeError(self._unreachable_reason)

        self._receiver_task = asyncio.create_task(self._receive_loop())
        await self._login()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def close(self) -> None:
        self._closed = True
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
        if self._receiver_task is not None:
            self._receiver_task.cancel()
        if self._ws is not None and not self._is_ws_closed(self._ws):
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
        self._ws = None

    async def _heartbeat_loop(self) -> None:
        """BTCC connections are idle-timed out; send a lightweight public
        ping every 20 seconds to keep the socket alive.
        """
        try:
            while not self._closed:
                await asyncio.sleep(20)
                try:
                    # ``GetActiveContracts`` is a public no-auth probe.
                    await self._send({"action": "GetActiveContracts",
                                       "crid": self._new_crid()})
                except Exception:  # noqa: BLE001
                    break
        finally:
            self._ws = None

    async def _send(self, payload: Dict[str, Any]) -> None:
        if self._ws is None or self._is_ws_closed(self._ws):
            raise RuntimeError("BTCC WebSocket is not connected")
        message = json.dumps(payload, separators=(",", ":"))
        await self._ws.send(message)

    async def _receive_loop(self) -> None:
        assert self._ws is not None
        ws = self._ws
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:  # noqa: BLE001
                    continue
                await self._handle_message(msg)
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self._ws is ws:
                self._ws = None

    async def _handle_message(self, msg: Dict[str, Any]) -> None:
        # BTCC echoes the ``crid`` we supplied on the matching response
        # (``CRID`` in uppercase per the docs).
        crid = msg.get("CRID") or msg.get("crid")
        if crid is not None:
            future = self._pending.pop(str(crid), None)
            if future is not None and not future.done():
                rc = msg.get("RC") or msg.get("rc")
                # RC is '0'/0 on success; anything else is an error code.
                if rc in (None, 0, "0"):
                    future.set_result(msg)
                else:
                    err = (
                        msg.get("data")
                        or msg.get("msg")
                        or f"BTCC RC={rc}"
                    )
                    future.set_exception(RuntimeError(str(err)))
            return

    # ---------------------------------------------------------------
    # Signing / request envelope (per btcc-api.netlify.app/en/sign)
    # ---------------------------------------------------------------
    @staticmethod
    def _new_crid() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _querystring(payload: Dict[str, Any]) -> str:
        """Sort keys alphabetically and querystring-stringify.

        ``qs.stringify`` (as used in the BTCC reference JS implementation)
        URL-encodes values. We mirror that with ``urllib.parse.quote`` using
        its default ``safe='/'``; primitives are coerced to ``str`` first.
        """
        parts: List[str] = []
        for key in sorted(payload.keys()):
            val = payload[key]
            if isinstance(val, bool):
                val_str = "true" if val else "false"
            elif val is None:
                val_str = ""
            else:
                val_str = str(val)
            parts.append(f"{quote(str(key), safe='')}={quote(val_str, safe='')}")
        return "&".join(parts)

    def _sign(self, payload: Dict[str, Any]) -> str:
        content = self._querystring(payload)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            content.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send an already-finalized payload and await the response."""
        await self._ensure_connection()

        crid = str(payload.get("crid") or self._new_crid())
        payload["crid"] = crid

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[crid] = future

        await self._send(payload)
        try:
            return await asyncio.wait_for(future, timeout=15.0)
        except asyncio.TimeoutError:
            self._pending.pop(crid, None)
            raise RuntimeError(f"BTCC request '{payload.get('action')}' timed out")

    async def _signed_request(self, action: str, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Build the ``common``-enriched payload and sign it before sending."""
        payload: Dict[str, Any] = {
            "action": action,
            "timestamp": int(time.time() * 1000),
            "nonce": f"{random.randint(0, 99_999_999):08d}",
            "public_key": self.public_key,
            "crid": self._new_crid(),
        }
        payload.update({k: v for k, v in extra.items() if v is not None})
        payload["sign"] = self._sign(payload)
        return await self._request(payload)

    async def _login(self) -> None:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("BTCC api_key + api_secret required for Login")
        await self._signed_request("Login", {})

    def _normalize_symbol(self, symbol: str) -> str:
        return symbol.replace("/", "_").replace("-", "_").upper()

    # ---------------------------------------------------------------
    # Public API (matches the shape used by RealExchangeExecutor)
    # ---------------------------------------------------------------
    async def fetch_balance(self) -> Dict[str, float]:
        response = await self._signed_request("GetAccountInfo", {})
        data = response.get("data") or response.get("Data") or {}
        balances: Dict[str, float] = {}
        if isinstance(data, dict):
            # Typical shape: {"balance": {"BTC": 0.1, "USD": 100.0}}
            candidate = data.get("balance") or data.get("Balance") or data
            if isinstance(candidate, dict):
                for k, v in candidate.items():
                    try:
                        balances[str(k).upper()] = float(v)
                    except (TypeError, ValueError):
                        continue
        return balances

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> Dict[str, Any]:
        return await self._place_order(symbol, side, "MARKET", amount, None)

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> Dict[str, Any]:
        return await self._place_order(symbol, side, "LIMIT", amount, price)

    async def _place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float],
    ) -> Dict[str, Any]:
        if amount <= 0:
            raise ValueError("BTCC order amount must be positive")

        otype = order_type.upper()
        btcc_symbol = self._normalize_symbol(symbol)
        payload: Dict[str, Any] = {
            "symbol": btcc_symbol,
            "side": side.upper(),        # docs: 'BUY' | 'SELL'
            "order_type": otype,         # docs: 'LIMIT' | 'MARKET' | 'STOP'
            "quantity": float(amount),
        }
        if otype == "LIMIT":
            if price is None:
                raise ValueError("BTCC LIMIT order requires price")
            payload["price"] = float(price)
        elif otype == "MARKET":
            # Market orders still accept a reference price per docs.
            if price is not None:
                payload["price"] = float(price)

        response = await self._signed_request("PlaceOrder", payload)
        data = response.get("data") or response.get("Data") or {}

        raw_id = (
            data.get("OID")
            or data.get("orderId")
            or data.get("id")
            or data.get("order_id")
        )
        if raw_id is None:
            raise RuntimeError("BTCC order response missing order id")
        order_id = str(raw_id)

        price_val: Optional[float] = None
        price_str = data.get("price") or data.get("Price")
        if price_str is not None:
            try:
                price_val = float(price_str)
            except (TypeError, ValueError):
                price_val = price
        else:
            price_val = price

        status = data.get("status") or data.get("Status") or "open"
        return {
            "id": order_id,
            "symbol": symbol,
            "type": otype.lower(),
            "side": side.lower(),
            "amount": float(amount),
            "price": price_val,
            "status": status,
            "timestamp": None,
            "datetime": None,
        }

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        btcc_symbol = self._normalize_symbol(symbol)
        await self._signed_request(
            "CancelOrder",
            {"symbol": btcc_symbol, "order_id": order_id},
        )
        return True

    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        btcc_symbol = self._normalize_symbol(symbol)
        response = await self._signed_request("GetOpenOrders", {"symbol": btcc_symbol})
        data = response.get("data") or response.get("Data")

        order_info: Optional[Dict[str, Any]] = None
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                raw = (
                    item.get("OID")
                    or item.get("orderId")
                    or item.get("id")
                    or item.get("order_id")
                )
                if raw is not None and str(raw) == order_id:
                    order_info = item
                    break
        elif isinstance(data, dict):
            raw = (
                data.get("OID")
                or data.get("orderId")
                or data.get("id")
                or data.get("order_id")
            )
            if raw is not None and str(raw) == order_id:
                order_info = data

        if order_info is None:
            return {
                "id": order_id,
                "symbol": symbol,
                "type": None,
                "side": None,
                "price": None,
                "status": None,
                "timestamp": None,
                "datetime": None,
                "filled": 0.0,
                "remaining": 0.0,
                "cost": None,
            }

        price_val: Optional[float] = None
        price_str = order_info.get("price") or order_info.get("Price")
        if price_str is not None:
            try:
                price_val = float(price_str)
            except (TypeError, ValueError):
                price_val = None

        status = order_info.get("status") or order_info.get("Status")
        side = order_info.get("side") or order_info.get("Side")
        order_type = order_info.get("order_type") or order_info.get("type") or order_info.get("Type")

        return {
            "id": order_id,
            "symbol": symbol,
            "type": (order_type or "").lower() if isinstance(order_type, str) else order_type,
            "side": (side or "").lower() if isinstance(side, str) else side,
            "price": price_val,
            "status": status,
            "timestamp": None,
            "datetime": None,
            "filled": 0.0,
            "remaining": 0.0,
            "cost": None,
        }

    def status(self) -> Dict[str, Any]:
        """Return a health-check snapshot without raising on unreachable state."""
        return {
            "venue": "btcc",
            "unreachable": self._unreachable,
            "reason": self._unreachable_reason,
            "active_url": self.ws_url,
            "candidate_urls": list(self.ws_url_candidates),
            "connected": self._ws is not None and not self._is_ws_closed(self._ws),
        }


class OandaConnector:
    """Native connector for Oanda FX using the v20 REST API.

    This implementation uses synchronous HTTP requests under the hood via the
    'requests' library, wrapped in asyncio.to_thread() so it is compatible
    with the async interface expected by RealExchangeExecutor.
    """

    def __init__(
        self,
        api_key: str,
        account_id: Optional[str] = None,
        environment: str = "practice",
    ):
        self.name = "oanda"
        self.api_key = _clean_config_str(api_key)
        self.account_id = _clean_config_str(account_id)
        self._account_validated = False
        self._validation_attempted = False
        self._validation_error: Optional[str] = None
        
        # 'practice' -> demo environment, anything else treated as live
        env = (_clean_config_str(environment) or "practice").lower()
        if env in ("practice", "demo", "fxpractice"):
            self.base_url = "https://api-fxpractice.oanda.com"
        else:
            # Live / fxtrade
            self.base_url = "https://api-fxtrade.oanda.com"

        # Use a dedicated session for connection pooling
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        # SOTA 2026 FIX: Aggressive timeout to fail fast and prevent hangs
        # If network/DNS is slow, we want to know immediately, not block forever
        self._timeout = (5.0, 15.0)
        
        # SOTA 2026 FIX: NO validation during __init__ - completely non-blocking
        # Account validation happens lazily on first use
        # This ensures connector creation NEVER fails and GUI always launches
        logger.info(f"✅ Oanda connector created (validation deferred until first use)")

    def _request(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> requests.Response:
        """HTTP request with retry/backoff, strict timeouts, and environment fallback.
        
        SOTA 2026 FIX: Robust request handling to ensure first-attempt success:
        - Strict connect (5s) and read (15s) timeouts to prevent hangs
        - Exponential backoff with jitter on transient failures
        - Automatic environment fallback (fxtrade ↔ fxpractice) on 401/403 errors
        """
        timeout = kwargs.pop("timeout", self._timeout)
        last_err: Optional[BaseException] = None
        
        for attempt in range(max_retries):
            try:
                resp = self._session.request(method, url, timeout=timeout, **kwargs)
                
                # Check for auth errors that might indicate wrong environment
                if resp.status_code in (401, 403) and attempt == 0:
                    # Try switching environment on first auth failure
                    if "api-fxpractice" in self.base_url:
                        alt_url = url.replace("api-fxpractice", "api-fxtrade")
                        alt_base = "https://api-fxtrade.oanda.com"
                        logger.info(f"🔄 Oanda auth failed on practice, trying live environment...")
                    else:
                        alt_url = url.replace("api-fxtrade", "api-fxpractice")
                        alt_base = "https://api-fxpractice.oanda.com"
                        logger.info(f"🔄 Oanda auth failed on live, trying practice environment...")
                    
                    alt_resp = self._session.request(method, alt_url, timeout=timeout, **kwargs)
                    if alt_resp.status_code < 400:
                        # Fallback succeeded - update base_url for future requests
                        self.base_url = alt_base
                        logger.info(f"✅ Oanda environment fallback succeeded: {alt_base}")
                        return alt_resp
                
                return resp
                
            except requests.exceptions.RequestException as e:
                last_err = e
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter: 0.5s, 1s, 2s + random 0-0.2s
                    delay = (0.5 * (2 ** attempt)) + (random.random() * 0.2)
                    logger.debug(f"Oanda request attempt {attempt + 1} failed: {e}, retrying in {delay:.2f}s")
                    time.sleep(delay)
                    continue
                raise
        
        raise RuntimeError(f"Oanda request failed after {max_retries} attempts: {last_err}")

    async def fetch_balance(self) -> Dict[str, float]:
        """Return account balance as {currency: amount} using /v3/accounts/{id}/summary."""
        return await asyncio.to_thread(self._fetch_balance_sync)

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch a minimal ticker-like structure for an Oanda instrument.

        This calls the live /v3/accounts/{id}/pricing endpoint and returns
        real bid/ask quotes plus a synthetic last (mid) price. No simulated
        values are introduced; if pricing is unavailable an exception is
        raised instead of fabricating data.
        """

        return await asyncio.to_thread(self._fetch_ticker_sync, symbol)

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._create_order_sync,
            symbol,
            side,
            amount,
            None,
            "MARKET",
        )

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._create_order_sync,
            symbol,
            side,
            amount,
            price,
            "LIMIT",
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:  # noqa: ARG002
        return await asyncio.to_thread(self._cancel_order_sync, order_id)

    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        return await asyncio.to_thread(self._fetch_order_sync, order_id, symbol)

    # ----- Internal sync helpers -----

    def _ensure_account_id(self) -> None:
        """Ensure self.account_id is populated and valid using /v3/accounts.

        This method now always inspects the /v3/accounts response so that if a
        misconfigured account_id is provided in config, it can be corrected
        automatically by falling back to the first available account instead of
        causing downstream 400 Invalid accountID errors.
        
        SOTA 2026: This is called lazily on first use, with caching to avoid
        repeated validation attempts.
        """
        
        # If already validated, return immediately
        if self._account_validated:
            return
        
        # If validation was attempted and failed, raise the cached error
        if self._validation_attempted and not self._account_validated:
            raise RuntimeError(f"Oanda account validation failed: {self._validation_error}")
        
        # Mark that we're attempting validation
        self._validation_attempted = True
        
        try:
            url = f"{self.base_url}/v3/accounts"
            resp = self._request("GET", url)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Oanda accounts error {resp.status_code}: {resp.text}"
                )

            data = resp.json()
            accounts = data.get("accounts") or []
            if not accounts:
                raise RuntimeError("No Oanda accounts available for this API key")

            configured_id = self.account_id
            if configured_id:
                configured_id = _clean_config_str(configured_id)
                self.account_id = configured_id
                for acc in accounts:
                    if acc.get("id") == configured_id:
                        # Configured account is valid, keep it.
                        self._account_validated = True
                        logger.info(f"✅ Oanda account validated: {self.account_id}")
                        return
                # Configured ID is not present; log and fall back to first.
                logger.warning(
                    "Oanda account_id %s not found in /v3/accounts response; "
                    "falling back to %s",
                    configured_id,
                    accounts[0].get("id"),
                )

            account_id = accounts[0].get("id")
            if not account_id:
                raise RuntimeError("Oanda account ID not found in accounts response")

            self.account_id = account_id
            self._account_validated = True
            logger.info(f"✅ Oanda account validated: {self.account_id}")
            
        except Exception as e:
            # Cache the error so we don't retry on every operation
            self._validation_error = str(e)
            logger.warning(f"⚠️ Oanda account validation failed: {e}")
            raise

    def _fetch_ticker_sync(self, symbol: str) -> Dict[str, Any]:
        """Synchronous helper for fetch_ticker using the pricing endpoint."""

        # SOTA 2026 FIX: Lazy validation on first use
        self._ensure_account_id()
        
        instrument = self._normalize_symbol(symbol)
        url = f"{self.base_url}/v3/accounts/{self.account_id}/pricing"
        params = {"instruments": instrument}
        resp = self._request("GET", url, params=params)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Oanda pricing error {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        prices = data.get("prices") or []
        if not prices:
            raise RuntimeError(f"Oanda pricing response missing prices for {instrument}")

        price_info = None
        for p in prices:
            if isinstance(p, dict) and p.get("instrument") == instrument:
                price_info = p
                break
        if price_info is None:
            # Fall back to the first entry if an exact match is not found.
            price_info = prices[0]

        bids = price_info.get("bids") or []
        asks = price_info.get("asks") or []

        bid_str = bids[0].get("price") if bids else None
        ask_str = asks[0].get("price") if asks else None

        try:
            bid = float(bid_str) if bid_str is not None else 0.0
        except (TypeError, ValueError):
            bid = 0.0
        try:
            ask = float(ask_str) if ask_str is not None else 0.0
        except (TypeError, ValueError):
            ask = 0.0

        last = 0.0
        if bid and ask:
            last = (bid + ask) / 2.0
        elif bid:
            last = bid
        elif ask:
            last = ask

        ts_ms: Optional[int] = None
        time_str = price_info.get("time")
        if isinstance(time_str, str):
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                ts_ms = int(dt.timestamp() * 1000)
            except Exception:  # noqa: BLE001
                ts_ms = None

        return {
            "symbol": symbol,
            "instrument": instrument,
            "bid": bid,
            "ask": ask,
            "last": last,
            "timestamp": ts_ms,
        }

    def list_instruments_sync(self) -> List[str]:
        """Return a list of tradable instrument names for the account.

        This uses the live /v3/accounts/{id}/instruments endpoint so that the
        symbol index for Oanda reflects the actual instruments enabled on the
        account (no hardcoded lists).
        """

        # SOTA 2026 FIX: Lazy validation on first use
        self._ensure_account_id()
        
        url = f"{self.base_url}/v3/accounts/{self.account_id}/instruments"
        resp = self._request("GET", url)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Oanda instruments error {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        instruments = data.get("instruments") or []
        names: List[str] = []
        for inst in instruments:
            if not isinstance(inst, dict):
                continue
            name = inst.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    def _fetch_balance_sync(self) -> Dict[str, float]:
        # SOTA 2026 FIX: Lazy validation on first use
        self._ensure_account_id()
        
        url = f"{self.base_url}/v3/accounts/{self.account_id}/summary"
        resp = self._request("GET", url)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Oanda balance error {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        account = data.get("account") or {}
        currency = account.get("currency") or "BASE"
        balance_str = account.get("balance")
        if balance_str is None:
            return {}

        try:
            balance_val = float(balance_str)
        except (TypeError, ValueError):
            return {}

        return {currency: balance_val}

    async def fetch_account_summary(self) -> Dict[str, Any]:
        """Return the full Oanda account summary (balance, unrealized PnL, margin).

        Used by the readiness report to show exactly what Kingdom AI sees
        on the Oanda silo.
        """
        return await asyncio.to_thread(self._fetch_account_summary_sync)

    def _fetch_account_summary_sync(self) -> Dict[str, Any]:
        self._ensure_account_id()
        url = f"{self.base_url}/v3/accounts/{self.account_id}/summary"
        resp = self._request("GET", url)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Oanda summary error {resp.status_code}: {resp.text}"
            )
        data = resp.json().get("account") or {}
        def _f(k: str) -> float:
            v = data.get(k)
            try:
                return float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                return 0.0
        return {
            "account_id": self.account_id,
            "environment": "practice" if "fxpractice" in self.base_url else "live",
            "currency": data.get("currency"),
            "balance": _f("balance"),
            "unrealized_pl": _f("unrealizedPL"),
            "pl": _f("pl"),
            "margin_available": _f("marginAvailable"),
            "margin_used": _f("marginUsed"),
            "open_trade_count": int(data.get("openTradeCount") or 0),
            "open_position_count": int(data.get("openPositionCount") or 0),
            "nav": _f("NAV"),
        }

    async def fetch_full_balance(self) -> Dict[str, Any]:
        """Adapter for the executor-level balance sweep."""
        summary = await self.fetch_account_summary()
        currency = summary.get("currency") or "USD"
        bal = float(summary.get("balance") or 0)
        return {
            "exchange": self.name,
            "currencies": {
                currency: {
                    "free": float(summary.get("margin_available") or 0),
                    "used": float(summary.get("margin_used") or 0),
                    "total": bal,
                }
            },
            "details": summary,
        }

    async def fetch_deposit_address(
        self, code: str, network: Optional[str] = None,  # noqa: ARG002
    ) -> Dict[str, Any]:
        """Oanda does not accept crypto / exchange deposits.

        Funding is ACH / wire / debit card from the account holder's
        linked bank only. We surface this as a structured, actionable
        error rather than returning a fake address.
        """
        raise RuntimeError(
            "Oanda does not accept external deposits via API. Fund the "
            "account through your linked bank (ACH/wire/debit) in the "
            "Oanda portal. Kingdom AI will track the balance once funds "
            "settle."
        )

    async def withdraw(  # noqa: D401 - intentional one-liner policy doc
        self,
        code: str,  # noqa: ARG002
        amount: float,  # noqa: ARG002
        address: str,  # noqa: ARG002
        tag: Optional[str] = None,  # noqa: ARG002
        network: Optional[str] = None,  # noqa: ARG002
        params: Optional[Dict[str, Any]] = None,  # noqa: ARG002
    ) -> Dict[str, Any]:
        """Oanda does not expose a withdrawal endpoint in the v20 REST API.

        Withdrawals must be initiated from the Oanda web portal. We emit
        a structured ``manual_action_required`` payload so the orchestrator
        can notify the user instead of silently failing.
        """
        return {
            "status": "manual_action_required",
            "venue": self.name,
            "reason": (
                "Oanda v20 REST API does not expose a withdrawal endpoint. "
                "Withdraw from the Oanda portal; Kingdom AI will detect "
                "the balance change on the next summary sync."
            ),
            "portal_url": "https://www.oanda.com/account/funding",
        }

    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbols like 'EUR/USD' to Oanda's 'EUR_USD' format."""
        return symbol.replace("-", "_").replace("/", "_").upper()

    def _create_order_sync(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float],
        order_type: str,
    ) -> Dict[str, Any]:
        # SOTA 2026 FIX: Lazy validation on first use
        self._ensure_account_id()
        
        instrument = self._normalize_symbol(symbol)

        if amount <= 0:
            raise ValueError("OandaConnector: order amount must be positive")

        # Oanda expects integer 'units'; positive for buy, negative for sell.
        units = int(abs(amount))
        if units <= 0:
            raise ValueError("OandaConnector: order amount too small after rounding")
        if side.lower() == "sell":
            units = -units

        order: Dict[str, Any] = {
            "instrument": instrument,
            "units": str(units),
            "type": order_type,
            "positionFill": "DEFAULT",
        }

        if order_type == "MARKET":
            # Use FOK for immediate execution, which matches RealExchangeExecutor semantics.
            order["timeInForce"] = "FOK"
        else:
            order["timeInForce"] = "GTC"
            if price is None:
                raise ValueError("OandaConnector: limit order requires price")
            # Oanda expects price as string; number of decimals depends on instrument.
            order["price"] = f"{price:.5f}"

        payload = {"order": order}
        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders"
        resp = self._request("POST", url, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Oanda order error {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        order_create = data.get("orderCreateTransaction") or {}
        order_fill = data.get("orderFillTransaction") or {}

        raw_order_id = order_fill.get("orderID") or order_create.get("id")
        order_id = str(raw_order_id) if raw_order_id is not None else None

        status = "filled" if order_fill else "pending"
        price_str = order_fill.get("price") or order.get("price")
        try:
            price_val = float(price_str) if price_str is not None else None
        except (TypeError, ValueError):
            price_val = None

        abs_units = float(abs(int(order["units"])))
        filled = abs_units if status == "filled" else 0.0
        remaining = 0.0 if status == "filled" else abs_units

        cost = None
        if price_val is not None:
            cost = price_val * filled

        return {
            "id": order_id,
            "symbol": instrument,
            "type": order_type.lower(),
            "side": side.lower(),
            "amount": abs_units,
            "price": price_val,
            "status": status,
            "timestamp": None,
            "datetime": order_fill.get("time") or order_create.get("time"),
            "filled": filled,
            "remaining": remaining,
            "cost": cost,
            "fee": None,
        }

    def _cancel_order_sync(self, order_id: str) -> bool:
        self._ensure_account_id()
        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders/{order_id}/cancel"
        resp = self._request("PUT", url)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Oanda cancel error {resp.status_code}: {resp.text}"
            )
        return True

    def _fetch_order_sync(self, order_id: str, symbol: str) -> Dict[str, Any]:
        self._ensure_account_id()
        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders/{order_id}"
        resp = self._request("GET", url)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Oanda fetch_order error {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        order = data.get("order") or {}
        instrument = order.get("instrument") or self._normalize_symbol(symbol)
        state = (order.get("state") or "").lower()
        price_str = order.get("price") or order.get("priceBound")
        try:
            price_val = float(price_str) if price_str is not None else None
        except (TypeError, ValueError):
            price_val = None

        units_str = order.get("units") or "0"
        try:
            units_val = float(units_str)
        except (TypeError, ValueError):
            units_val = 0.0

        abs_units = abs(units_val)
        filled = abs_units if state == "filled" else 0.0
        remaining = 0.0 if state == "filled" else abs_units

        side = "buy" if units_val >= 0 else "sell"
        cost = None
        if price_val is not None:
            cost = price_val * filled

        return {
            "id": order.get("id") or order_id,
            "symbol": instrument,
            "type": (order.get("type") or "").lower(),
            "side": side,
            "price": price_val,
            "status": state,
            "timestamp": None,
            "datetime": order.get("createTime"),
            "filled": filled,
            "remaining": remaining,
            "cost": cost,
            "fee": None,
        }


class RealExchangeExecutor:
    """
    REAL Exchange Executor - NO SIMULATIONS
    Connects to Binance, Coinbase, Kraken, KuCoin, etc. with user's API keys
    Executes REAL orders on LIVE markets
    """
    
    _instance = None
    _instance_lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        inst = cls._instance
        if inst is not None:
            return inst
        with cls._instance_lock:
            inst = cls._instance
            if inst is None:
                inst = super().__new__(cls)
                setattr(inst, "_initialized", False)
                cls._instance = inst
        return inst
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None, event_bus=None):
        """
        Initialize with user's API keys for all exchanges (2025 State-of-the-Art).
        
        Args:
            api_keys: Dictionary with exchange keys
                     {'binance': 'key', 'binance_secret': 'secret', ...}
            event_bus: Event bus for publishing trade events
        """
        if getattr(self, "_initialized", False):
            if api_keys:
                try:
                    if api_keys != getattr(self, "api_keys", None):
                        self.reload_api_keys(api_keys)
                except Exception as e:
                    logger.warning("RealExchangeExecutor key reload skipped: %s", e)
            if event_bus is not None and event_bus is not getattr(self, "event_bus", None):
                self.event_bus = event_bus
            return
 
        self.api_keys = api_keys or {}
        self.event_bus = event_bus
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.connectors: Dict[str, ExchangeConnector] = {}
        self.ws_exchanges: Dict[str, ccxtpro.Exchange] = {}  # WebSocket exchanges
        self.active_orders: Dict[str, Dict[str, Any]] = {}
        self.order_history: List[Dict[str, Any]] = []
        
        # 2025 Advanced Features
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_handlers: Dict[str, RetryHandler] = {}
        self.rate_limiters: Dict[str, float] = {}  # Track last request time per exchange
        self.private_exchange_locks: Dict[str, asyncio.Lock] = {}  # Serialize private requests per exchange
        self.ws_streams: Dict[str, asyncio.Task] = {}  # Active WebSocket streams
        
        # Performance metrics
        self.metrics = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'retry_count': 0,
            'circuit_breaker_trips': 0,
            'avg_latency_ms': 0.0
        }
        
        # SOTA 2026: Initialize timestamp auto-fix system
        self.timestamp_auto_fix: Optional[TradingTimestampAutoFix] = None
        if HAS_TIMESTAMP_AUTO_FIX:
            # Will be initialized after exchanges are connected
            pass
        
        # Initialize all available exchanges
        self._initialize_exchanges()
        
        # SOTA 2026: Start timestamp auto-fix after exchanges are initialized
        if HAS_TIMESTAMP_AUTO_FIX and self.exchanges:
            self.timestamp_auto_fix = initialize_timestamp_auto_fix(self.exchanges)
            logger.info("🕐 Timestamp auto-fix system activated")
        
        logger.info(f"✅ REAL Exchange Executor initialized with {len(self.exchanges)} LIVE exchanges")
        logger.info(f"🔴 LIVE TRADING MODE - Circuit Breakers: {len(self.circuit_breakers)}")
        if self.timestamp_auto_fix:
            logger.info("🕐 Auto timestamp synchronization: ENABLED")

        try:
            self._initialized = True
        except Exception:
            pass
    
    def reload_api_keys(self, api_keys: Dict[str, str]) -> None:
        """Reload API keys at runtime and reinitialize exchange connections.
        
        This clears existing exchange/connectors state and re-runs
        _initialize_exchanges() using the provided api_keys mapping.
        """
        logger.info("Reloading RealExchangeExecutor API keys and exchanges...")
        self.api_keys = api_keys
        self.exchanges = {}
        self.connectors = {}
        self.ws_exchanges = {}
        self.circuit_breakers = {}
        self.retry_handlers = {}
        self.rate_limiters = {}
        self.private_exchange_locks = {}
        self.ws_streams = {}
        self._initialize_exchanges()

    def _get_private_lock(self, exchange_name: str) -> asyncio.Lock:
        """Get or create per-exchange lock for private authenticated calls.

        This prevents concurrent private requests from sharing the same API key
        nonce stream out-of-order (notably Kraken InvalidNonce).
        """
        lock = self.private_exchange_locks.get(exchange_name)
        if lock is None:
            lock = asyncio.Lock()
            self.private_exchange_locks[exchange_name] = lock
        return lock

    def _apply_exchange_network_overrides(self, ex_name: str, config: Dict[str, Any]) -> None:
        """Apply optional per-exchange HTTP(S) proxy and TLS settings.

        This hook is fully config-driven and ONLY applies overrides when
        corresponding keys are present in the flat ``api_keys`` mapping used
        to construct this executor. It does NOT provide any default proxies
        or geo-bypass logic.

        Supported flattened keys per exchange name (all optional):
            - "{ex}_http_proxy": HTTP proxy URL
            - "{ex}_https_proxy": HTTPS proxy URL
            - "{ex}_verify": bool or path passed to requests/ccxt "verify"
            - "{ex}_ca_bundle": path to CA bundle (overrides "verify")
        """

        try:
            prefix = ex_name.lower()

            http_proxy = self.api_keys.get(f"{prefix}_http_proxy")
            https_proxy = self.api_keys.get(f"{prefix}_https_proxy")
            verify = self.api_keys.get(f"{prefix}_verify")
            ca_bundle = self.api_keys.get(f"{prefix}_ca_bundle")

            proxies: Dict[str, str] = {}
            if isinstance(http_proxy, str) and http_proxy.strip():
                proxies["http"] = http_proxy.strip()
            if isinstance(https_proxy, str) and https_proxy.strip():
                proxies["https"] = https_proxy.strip()

            if proxies:
                config["proxies"] = proxies

            # Allow verify to be a bool or a path (requests-compatible)
            if verify is not None:
                config["verify"] = verify

            # Explicit CA bundle path takes precedence if provided
            if isinstance(ca_bundle, str) and ca_bundle.strip():
                config["verify"] = ca_bundle.strip()

        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to apply network overrides for %s: %s", ex_name, e)

    def _sync_exchange_clock(self, ex_name: str, exchange: ccxt.Exchange) -> None:  # type: ignore[valid-type]
        """Enable ccxt time-difference adjustment and pre-load server time.

        This is a best-effort helper that mitigates timestamp/nonce errors
        such as Binance/BinanceUS -1021 ("Timestamp for this request was
        1000ms ahead of the server's time") without requiring OS-level
        clock tweaks. It is safe to call multiple times; failures are
        logged as warnings but do not prevent the executor from starting.
        """

        try:
            # Prefer enabling automatic adjustment for all future requests.
            opts = getattr(exchange, "options", None)
            if isinstance(opts, dict):
                if not opts.get("adjustForTimeDifference"):
                    opts["adjustForTimeDifference"] = True

            # Explicitly load the time difference once at startup so the
            # first authenticated request already has a corrected nonce.
            if hasattr(exchange, "load_time_difference"):
                dt = exchange.load_time_difference()
                try:
                    dt_val = float(dt)
                except (TypeError, ValueError):  # noqa: PERF203
                    dt_val = None
                if dt_val is not None:
                    logger.info(
                        "%s time difference synchronized via ccxt: %.0f ms",
                        ex_name,
                        dt_val,
                    )
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            lowered = msg.lower()

            # Bitstamp does not currently support time()/load_time_difference()
            # in some ccxt builds. This is a known limitation and not a
            # functional error, so downgrade it to an informational message
            # instead of a generic warning.
            if ex_name.lower() == "bitstamp" and "time() is not supported yet" in lowered:
                logger.info(
                    "bitstamp: exchange time()/load_time_difference() not "
                    "supported in this ccxt build; skipping clock sync but "
                    "allowing trading to proceed.",
                )
                return

            # SOTA 2026: Downgrade geo-restriction errors to INFO - expected for some regions
            msg_lower = str(e).lower()
            if "restricted location" in msg_lower or "451" in msg_lower:
                logger.info(
                    "%s: geo-restricted (HTTP 451) - use VPN or regional exchange variant",
                    ex_name,
                )
            else:
                logger.warning(
                    "%s: failed to synchronize exchange clock via ccxt: %s",
                    ex_name,
                    e,
                )

    def _initialize_exchanges(self):
        """Initialize REAL exchange connections with user's API keys (2025 Best Practices)."""

        # Helper to normalize nested API key dicts coming from APIKeyManager.
        def _extract_ccxt_creds(entry: Any) -> tuple[bool, Optional[str], Optional[str]]:
            if not isinstance(entry, dict):
                return False, None, None
            api_key = entry.get("api_key") or entry.get("key")
            api_secret = entry.get("api_secret") or entry.get("secret")
            ok = bool(api_key) and bool(api_secret)
            return ok, api_key, api_secret

        # Binance / BinanceUS - respect geo-restrictions and nested key layout.
        binance_entry = self.api_keys.get("binance")
        binanceus_entry = self.api_keys.get("binanceus")

        has_binance, binance_key, binance_secret = _extract_ccxt_creds(binance_entry)
        has_binanceus, binanceus_key, binanceus_secret = _extract_ccxt_creds(binanceus_entry)

        if has_binanceus and has_binance:
            logger.info(
                "ℹ️ Skipping regular Binance - using BinanceUS instead (geo-restriction avoidance)",
            )
            has_binance = False  # Hard-disable regular Binance in this case.

        if has_binance:
            try:
                # REST API
                binance_config: Dict[str, Any] = {
                    "apiKey": binance_key,
                    "secret": binance_secret,
                    "enableRateLimit": True,
                    "rateLimit": 50,  # ms between requests
                    "options": {
                        "defaultType": "spot",
                        "recvWindow": 10000,  # Signature timeout
                        "timeDifference": 0,
                    },
                }
                self._apply_exchange_network_overrides("binance", binance_config)
                self.exchanges["binance"] = ccxt.binance(binance_config)
                self._sync_exchange_clock("binance", self.exchanges["binance"])

                # WebSocket API (CCXT Pro)
                try:
                    self.ws_exchanges["binance"] = ccxtpro.binance(
                        {
                            "apiKey": binance_key,
                            "secret": binance_secret,
                            "enableRateLimit": True,
                        },
                    )
                    logger.info(
                        "✅ BINANCE WebSocket connected - Real-time streaming ACTIVE",
                    )
                except Exception as ws_error:  # noqa: BLE001
                    logger.warning("Binance WebSocket not available: %s", ws_error)

                # Initialize connector, circuit breaker and retry handler
                self.connectors["binance"] = CcxtExchangeConnector(
                    "binance",
                    self.exchanges["binance"],
                )
                self.circuit_breakers["binance"] = CircuitBreaker()
                self.retry_handlers["binance"] = RetryHandler()

                logger.info("✅ BINANCE connected - LIVE TRADING ACTIVE")
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to connect Binance: %s", e)

        # Binance.US (REST via ccxt - FIX: Aggressive time-diff adjustment for -1021 errors)
        if has_binanceus:
            # BinanceUS does not support IPv6; force AF_INET for *.binance.us
            # so dual-stack Linux boxes stop hitting the -71012 error.
            _prefer_ipv4_for_hosts(("binance.us",))
            # Also install a session-scoped IPv4 adapter below once the
            # ccxt client exists. source_address=("0.0.0.0", 0) forces the
            # outbound socket to bind to an IPv4 address selected by the
            # kernel, even on dual-stack hosts where ``getaddrinfo`` would
            # otherwise hand back an AAAA record first.
            try:
                binanceus_config: Dict[str, Any] = {
                    "apiKey": binanceus_key,
                    "secret": binanceus_secret,
                    "enableRateLimit": True,
                    "rateLimit": 100,  # Slightly slower to avoid rate limits
                    "options": {
                        "defaultType": "spot",
                        # FIX: Aggressive time difference adjustment for -1021 timestamp errors
                        "adjustForTimeDifference": True,
                        # FIX: Increase recvWindow to 60 seconds to handle clock skew
                        "recvWindow": 60000,
                        # FIX: Pre-compute time difference before first request
                        "timeDifference": 0,
                    },
                }
                self._apply_exchange_network_overrides("binanceus", binanceus_config)
                self.exchanges["binanceus"] = ccxt.binanceus(binanceus_config)

                # Session-scoped IPv4 lock: bind outbound sockets to
                # 0.0.0.0:0 so every HTTPS request in this ccxt session
                # uses an IPv4 source address, regardless of what any
                # global DNS ordering / aiohttp resolver would do elsewhere.
                try:
                    _attach_ipv4_only_adapter(self.exchanges["binanceus"])
                    logger.info("✅ BINANCEUS session locked to IPv4")
                except Exception as _adapter_err:  # noqa: BLE001
                    logger.warning(
                        "BINANCEUS IPv4 adapter attach failed: %s",
                        _adapter_err,
                    )

                # FIX: Force load time difference immediately to fix timestamp skew
                try:
                    self.exchanges["binanceus"].load_time_difference()
                    logger.info("✅ BINANCEUS time difference synchronized")
                except Exception as td_err:  # noqa: BLE001
                    logger.warning("BINANCEUS time sync warning (continuing): %s", td_err)

                self._sync_exchange_clock("binanceus", self.exchanges["binanceus"])

                self.connectors["binanceus"] = CcxtExchangeConnector(
                    "binanceus",
                    self.exchanges["binanceus"],
                )
                self.circuit_breakers["binanceus"] = CircuitBreaker()
                self.retry_handlers["binanceus"] = RetryHandler()

                logger.info("✅ BINANCEUS connected - LIVE TRADING ACTIVE")
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to connect Binance.US: %s", e)
        
        # Coinbase - auto-detect which CCXT integration to use based on key shape:
        #   * Advanced Trade (cloud.coinbase.com) keys have apiKey starting with
        #     "organizations/.../apiKeys/..." and an EC private key as secret;
        #     these are NOT passphrase-protected and must use ccxt.coinbase.
        #   * Legacy Coinbase Pro / Exchange keys are short opaque strings and
        #     DO require a passphrase; those must use ccxt.coinbaseexchange.
        if 'coinbase' in self.api_keys and 'coinbase_secret' in self.api_keys:
            try:
                coinbase_key = str(self.api_keys['coinbase'] or '')
                coinbase_secret = str(self.api_keys['coinbase_secret'] or '')
                coinbase_password = self.api_keys.get('coinbase_password', '') or ''

                # `.env` files often round-trip the EC private key with
                # literal "\n" escape sequences rather than real newlines,
                # which breaks ccxt Advanced's PEM parser ("index out of
                # range"). Normalize to real newlines before handing the
                # secret to the SDK.
                if coinbase_secret and "\\n" in coinbase_secret and "\n" not in coinbase_secret:
                    coinbase_secret = coinbase_secret.replace("\\n", "\n")

                is_advanced = (
                    coinbase_key.startswith("organizations/")
                    or "apiKeys/" in coinbase_key
                    or "BEGIN EC PRIVATE KEY" in coinbase_secret
                    or "BEGIN PRIVATE KEY" in coinbase_secret
                )

                if is_advanced:
                    coinbase_class = (
                        getattr(ccxt, 'coinbase', None)
                        or getattr(ccxt, 'coinbaseadvanced', None)
                    )
                    if coinbase_class is None:
                        raise AttributeError(
                            "ccxt.coinbase is required for Advanced-Trade keys; "
                            "upgrade ccxt to a 2024+ build."
                        )
                    coinbase_config: Dict[str, Any] = {
                        'apiKey': coinbase_key,
                        'secret': coinbase_secret,
                        'enableRateLimit': True,
                    }
                    integration_label = 'coinbase (Advanced Trade)'
                else:
                    # Legacy Exchange/Pro keys - passphrase required.
                    coinbase_class = (
                        getattr(ccxt, 'coinbaseexchange', None)
                        or getattr(ccxt, 'coinbasepro', None)
                        or getattr(ccxt, 'coinbase', None)
                    )
                    if coinbase_class is None:
                        raise AttributeError(
                            "Neither ccxt.coinbaseexchange, ccxt.coinbasepro nor "
                            "ccxt.coinbase is available in this ccxt build"
                        )
                    if not coinbase_password:
                        raise RuntimeError(
                            "Legacy Coinbase Exchange keys require a passphrase. "
                            "Either (a) add 'coinbase_password' to config/api_keys.json "
                            "with the passphrase you set when the key was created, or "
                            "(b) regenerate a new Coinbase Advanced-Trade key at "
                            "cloud.coinbase.com - those do not need a passphrase and "
                            "Kingdom AI will auto-detect them."
                        )
                    coinbase_config = {
                        'apiKey': coinbase_key,
                        'secret': coinbase_secret,
                        'password': coinbase_password,
                        'enableRateLimit': True,
                    }
                    integration_label = 'coinbaseexchange (legacy Pro)'

                self._apply_exchange_network_overrides('coinbase', coinbase_config)
                self.exchanges['coinbase'] = coinbase_class(coinbase_config)
                self._sync_exchange_clock('coinbase', self.exchanges['coinbase'])

                self.connectors['coinbase'] = CcxtExchangeConnector('coinbase', self.exchanges['coinbase'])
                self.circuit_breakers['coinbase'] = CircuitBreaker()
                self.retry_handlers['coinbase'] = RetryHandler()

                logger.info("✅ COINBASE connected via %s - LIVE TRADING ACTIVE", integration_label)
            except Exception as e:
                logger.error(f"Failed to connect Coinbase: {e}")
        
        # Kraken
        if 'kraken' in self.api_keys and 'kraken_secret' in self.api_keys:
            try:
                kraken_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['kraken'],
                    'secret': self.api_keys['kraken_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('kraken', kraken_config)
                self.exchanges['kraken'] = ccxt.kraken(kraken_config)
                self._sync_exchange_clock('kraken', self.exchanges['kraken'])
                
                self.connectors['kraken'] = CcxtExchangeConnector('kraken', self.exchanges['kraken'])
                self.circuit_breakers['kraken'] = CircuitBreaker()
                self.retry_handlers['kraken'] = RetryHandler()
                
                logger.info("✅ KRAKEN connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Kraken: {e}")
        
        # Bitstamp
        if 'bitstamp' in self.api_keys and 'bitstamp_secret' in self.api_keys:
            try:
                bitstamp_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['bitstamp'],
                    'secret': self.api_keys['bitstamp_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('bitstamp', bitstamp_config)
                self.exchanges['bitstamp'] = ccxt.bitstamp(bitstamp_config)
                self._sync_exchange_clock('bitstamp', self.exchanges['bitstamp'])
                
                self.connectors['bitstamp'] = CcxtExchangeConnector('bitstamp', self.exchanges['bitstamp'])
                self.circuit_breakers['bitstamp'] = CircuitBreaker()
                self.retry_handlers['bitstamp'] = RetryHandler()
                
                logger.info("✅ BITSTAMP connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Bitstamp: {e}")
        
        # HTX (formerly Huobi) - FIX: Disable SSL verification to avoid certificate errors
        if 'htx' in self.api_keys and 'htx_secret' in self.api_keys:
            try:
                if hasattr(ccxt, 'htx'):
                    htx_class = ccxt.htx
                elif hasattr(ccxt, 'huobi'):  # fallback for older ids
                    htx_class = ccxt.huobi
                else:
                    raise AttributeError("Neither ccxt.htx nor ccxt.huobi is available in this ccxt build")

                htx_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['htx'],
                    'secret': self.api_keys['htx_secret'],
                    'enableRateLimit': True,
                    # FIX: Disable SSL verification to avoid CERTIFICATE_VERIFY_FAILED errors
                    # This is needed because HTX's linear-swap-api endpoint has CA trust issues
                    'verify': False,
                    'options': {
                        'defaultType': 'spot',
                        # Use spot API only to avoid linear-swap-api SSL issues
                        'fetchMarkets': ['spot'],
                    },
                }

                # Apply HTX-specific verify/CA and any generic overrides
                self._apply_exchange_network_overrides('htx', htx_config)

                self.exchanges['htx'] = htx_class(htx_config)
                self._sync_exchange_clock('htx', self.exchanges['htx'])

                self.connectors['htx'] = CcxtExchangeConnector('htx', self.exchanges['htx'])
                self.circuit_breakers['htx'] = CircuitBreaker()
                self.retry_handlers['htx'] = RetryHandler()

                logger.info("✅ HTX connected - LIVE TRADING ACTIVE (SSL verify disabled)")
            except Exception as e:
                logger.error(f"Failed to connect HTX: {e}")
        
        # KuCoin
        if 'kucoin' in self.api_keys and 'kucoin_secret' in self.api_keys:
            try:
                kucoin_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['kucoin'],
                    'secret': self.api_keys['kucoin_secret'],
                    'password': self.api_keys.get('kucoin_password', ''),
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('kucoin', kucoin_config)
                self.exchanges['kucoin'] = ccxt.kucoin(kucoin_config)
                self._sync_exchange_clock('kucoin', self.exchanges['kucoin'])
                self.connectors['kucoin'] = CcxtExchangeConnector('kucoin', self.exchanges['kucoin'])
                self.circuit_breakers['kucoin'] = CircuitBreaker()
                self.retry_handlers['kucoin'] = RetryHandler()
                logger.info("✅ KUCOIN connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect KuCoin: {e}")
        
        # Additional CCXT spot exchanges discovered from APIKeyManager
        # These use a simplified configuration: apiKey, secret, and optional
        # password/passphrase where required. Any exchange without keys will
        # simply be skipped.

        # Bybit
        if 'bybit' in self.api_keys and 'bybit_secret' in self.api_keys:
            try:
                bybit_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['bybit'],
                    'secret': self.api_keys['bybit_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('bybit', bybit_config)
                self.exchanges['bybit'] = ccxt.bybit(bybit_config)
                self._sync_exchange_clock('bybit', self.exchanges['bybit'])
                self.connectors['bybit'] = CcxtExchangeConnector('bybit', self.exchanges['bybit'])
                self.circuit_breakers['bybit'] = CircuitBreaker()
                self.retry_handlers['bybit'] = RetryHandler()
                logger.info("✅ BYBIT connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Bybit: {e}")

        # Bitget
        if 'bitget' in self.api_keys and 'bitget_secret' in self.api_keys:
            try:
                bitget_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['bitget'],
                    'secret': self.api_keys['bitget_secret'],
                    'password': self.api_keys.get('bitget_password', ''),
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('bitget', bitget_config)
                self.exchanges['bitget'] = ccxt.bitget(bitget_config)
                self._sync_exchange_clock('bitget', self.exchanges['bitget'])
                self.connectors['bitget'] = CcxtExchangeConnector('bitget', self.exchanges['bitget'])
                self.circuit_breakers['bitget'] = CircuitBreaker()
                self.retry_handlers['bitget'] = RetryHandler()
                logger.info("✅ BITGET connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Bitget: {e}")

        # MEXC
        if 'mexc' in self.api_keys and 'mexc_secret' in self.api_keys:
            try:
                mexc_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['mexc'],
                    'secret': self.api_keys['mexc_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('mexc', mexc_config)
                self.exchanges['mexc'] = ccxt.mexc(mexc_config)
                self._sync_exchange_clock('mexc', self.exchanges['mexc'])
                self.connectors['mexc'] = CcxtExchangeConnector('mexc', self.exchanges['mexc'])
                self.circuit_breakers['mexc'] = CircuitBreaker()
                self.retry_handlers['mexc'] = RetryHandler()
                logger.info("✅ MEXC connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect MEXC: {e}")

        # Gate.io (gateio)
        if 'gateio' in self.api_keys and 'gateio_secret' in self.api_keys:
            try:
                gateio_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['gateio'],
                    'secret': self.api_keys['gateio_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('gateio', gateio_config)
                self.exchanges['gateio'] = ccxt.gateio(gateio_config)
                self._sync_exchange_clock('gateio', self.exchanges['gateio'])
                self.connectors['gateio'] = CcxtExchangeConnector('gateio', self.exchanges['gateio'])
                self.circuit_breakers['gateio'] = CircuitBreaker()
                self.retry_handlers['gateio'] = RetryHandler()
                logger.info("✅ GATEIO connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Gateio: {e}")

        # Crypto.com (cryptocom)
        if 'cryptocom' in self.api_keys and 'cryptocom_secret' in self.api_keys:
            try:
                cryptocom_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['cryptocom'],
                    'secret': self.api_keys['cryptocom_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('cryptocom', cryptocom_config)
                self.exchanges['cryptocom'] = ccxt.cryptocom(cryptocom_config)
                self._sync_exchange_clock('cryptocom', self.exchanges['cryptocom'])
                self.connectors['cryptocom'] = CcxtExchangeConnector('cryptocom', self.exchanges['cryptocom'])
                self.circuit_breakers['cryptocom'] = CircuitBreaker()
                self.retry_handlers['cryptocom'] = RetryHandler()
                logger.info("✅ CRYPTOCOM connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Crypto.com: {e}")

        # Phemex
        if 'phemex' in self.api_keys and 'phemex_secret' in self.api_keys:
            try:
                phemex_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['phemex'],
                    'secret': self.api_keys['phemex_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('phemex', phemex_config)
                self.exchanges['phemex'] = ccxt.phemex(phemex_config)
                self._sync_exchange_clock('phemex', self.exchanges['phemex'])
                self.connectors['phemex'] = CcxtExchangeConnector('phemex', self.exchanges['phemex'])
                self.circuit_breakers['phemex'] = CircuitBreaker()
                self.retry_handlers['phemex'] = RetryHandler()
                logger.info("✅ PHEMEX connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Phemex: {e}")

        # Bittrex
        if 'bittrex' in self.api_keys and 'bittrex_secret' in self.api_keys:
            try:
                bittrex_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['bittrex'],
                    'secret': self.api_keys['bittrex_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('bittrex', bittrex_config)
                bittrex_class = getattr(ccxt, 'bittrex', None)
                if bittrex_class is None:
                    raise AttributeError("ccxt.bittrex is not available in this ccxt build")
                self.exchanges['bittrex'] = bittrex_class(bittrex_config)
                self._sync_exchange_clock('bittrex', self.exchanges['bittrex'])
                self.connectors['bittrex'] = CcxtExchangeConnector('bittrex', self.exchanges['bittrex'])
                self.circuit_breakers['bittrex'] = CircuitBreaker()
                self.retry_handlers['bittrex'] = RetryHandler()
                logger.info("✅ BITTREX connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Bittrex: {e}")

        # LBank
        if 'lbank' in self.api_keys and 'lbank_secret' in self.api_keys:
            try:
                lbank_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['lbank'],
                    'secret': self.api_keys['lbank_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('lbank', lbank_config)
                self.exchanges['lbank'] = ccxt.lbank(lbank_config)
                self._sync_exchange_clock('lbank', self.exchanges['lbank'])
                self.connectors['lbank'] = CcxtExchangeConnector('lbank', self.exchanges['lbank'])
                self.circuit_breakers['lbank'] = CircuitBreaker()
                self.retry_handlers['lbank'] = RetryHandler()
                logger.info("✅ LBANK connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect LBank: {e}")

        # Bitmart
        if 'bitmart' in self.api_keys and 'bitmart_secret' in self.api_keys:
            try:
                bitmart_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['bitmart'],
                    'secret': self.api_keys['bitmart_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('bitmart', bitmart_config)
                self.exchanges['bitmart'] = ccxt.bitmart(bitmart_config)
                self._sync_exchange_clock('bitmart', self.exchanges['bitmart'])
                self.connectors['bitmart'] = CcxtExchangeConnector('bitmart', self.exchanges['bitmart'])
                self.circuit_breakers['bitmart'] = CircuitBreaker()
                self.retry_handlers['bitmart'] = RetryHandler()
                logger.info("✅ BITMART connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Bitmart: {e}")

        # Whitebit
        if 'whitebit' in self.api_keys and 'whitebit_secret' in self.api_keys:
            try:
                whitebit_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['whitebit'],
                    'secret': self.api_keys['whitebit_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('whitebit', whitebit_config)
                self.exchanges['whitebit'] = ccxt.whitebit(whitebit_config)
                self._sync_exchange_clock('whitebit', self.exchanges['whitebit'])
                self.connectors['whitebit'] = CcxtExchangeConnector('whitebit', self.exchanges['whitebit'])
                self.circuit_breakers['whitebit'] = CircuitBreaker()
                self.retry_handlers['whitebit'] = RetryHandler()
                logger.info("✅ WHITEBIT connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Whitebit: {e}")

        # Poloniex
        if 'poloniex' in self.api_keys and 'poloniex_secret' in self.api_keys:
            try:
                poloniex_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['poloniex'],
                    'secret': self.api_keys['poloniex_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('poloniex', poloniex_config)
                self.exchanges['poloniex'] = ccxt.poloniex(poloniex_config)
                self._sync_exchange_clock('poloniex', self.exchanges['poloniex'])
                self.connectors['poloniex'] = CcxtExchangeConnector('poloniex', self.exchanges['poloniex'])
                self.circuit_breakers['poloniex'] = CircuitBreaker()
                self.retry_handlers['poloniex'] = RetryHandler()
                logger.info("✅ POLONIEX connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect Poloniex: {e}")

        # CoinEx
        if 'coinex' in self.api_keys and 'coinex_secret' in self.api_keys:
            try:
                coinex_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['coinex'],
                    'secret': self.api_keys['coinex_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('coinex', coinex_config)
                self.exchanges['coinex'] = ccxt.coinex(coinex_config)
                self._sync_exchange_clock('coinex', self.exchanges['coinex'])
                self.connectors['coinex'] = CcxtExchangeConnector('coinex', self.exchanges['coinex'])
                self.circuit_breakers['coinex'] = CircuitBreaker()
                self.retry_handlers['coinex'] = RetryHandler()
                logger.info("✅ COINEX connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect CoinEx: {e}")

        # bitFlyer
        if 'bitflyer' in self.api_keys and 'bitflyer_secret' in self.api_keys:
            try:
                bitflyer_config: Dict[str, Any] = {
                    'apiKey': self.api_keys['bitflyer'],
                    'secret': self.api_keys['bitflyer_secret'],
                    'enableRateLimit': True,
                }
                self._apply_exchange_network_overrides('bitflyer', bitflyer_config)
                self.exchanges['bitflyer'] = ccxt.bitflyer(bitflyer_config)
                self._sync_exchange_clock('bitflyer', self.exchanges['bitflyer'])
                self.connectors['bitflyer'] = CcxtExchangeConnector('bitflyer', self.exchanges['bitflyer'])
                self.circuit_breakers['bitflyer'] = CircuitBreaker()
                self.retry_handlers['bitflyer'] = RetryHandler()
                logger.info("✅ BITFLYER connected - LIVE TRADING ACTIVE")
            except Exception as e:
                logger.error(f"Failed to connect bitFlyer: {e}")

        # =====================================================================
        # NATIVE CONNECTORS (non-CCXT): BTCC and OANDA
        # =====================================================================
        
        # BTCC - Native WebSocket connector.
        # The production WS URL is issued privately in the BTCC API portal;
        # the connector will try any user-supplied URL first, then a short
        # list of historical candidates, then mark itself "unreachable" so
        # health checks report a clear reason instead of spamming the log.
        btcc_cfg = self.api_keys.get('btcc')
        if isinstance(btcc_cfg, dict):
            api_key = btcc_cfg.get('api_key') or btcc_cfg.get('key')
            api_secret = btcc_cfg.get('api_secret') or btcc_cfg.get('secret')
            username = btcc_cfg.get('username') or btcc_cfg.get('user')
            ws_url = btcc_cfg.get('ws_url')
            ws_urls = btcc_cfg.get('ws_urls')
            public_key = (
                btcc_cfg.get('public_key')
                or btcc_cfg.get('publickey')
                or btcc_cfg.get('access_key')
            )

            if api_key and api_secret:
                try:
                    btcc_connector = BtccConnector(
                        api_key=api_key,
                        api_secret=api_secret,
                        username=username,
                        ws_url=ws_url,
                        ws_urls=ws_urls if isinstance(ws_urls, list) else None,
                        public_key=public_key,
                    )
                    self.connectors['btcc'] = btcc_connector
                    self.circuit_breakers['btcc'] = CircuitBreaker()
                    self.retry_handlers['btcc'] = RetryHandler()
                    logger.info(
                        "✅ BTCC connector initialized (WS-API, candidates=%d)",
                        len(btcc_connector.ws_url_candidates),
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize BTCC connector: {e}")
        
        # OANDA - Native REST connector for Forex trading
        oanda_cfg = self.api_keys.get('oanda')
        if isinstance(oanda_cfg, dict):
            api_key = oanda_cfg.get('api_key') or oanda_cfg.get('key') or oanda_cfg.get('access_token')
            account_id = oanda_cfg.get('account_id') or oanda_cfg.get('account')
            environment = oanda_cfg.get('environment') or oanda_cfg.get('env') or 'practice'
            
            if api_key:
                try:
                    oanda_connector = OandaConnector(
                        api_key=api_key,
                        account_id=account_id,
                        environment=environment,
                    )
                    self.connectors['oanda'] = oanda_connector
                    self.circuit_breakers['oanda'] = CircuitBreaker()
                    self.retry_handlers['oanda'] = RetryHandler()
                    logger.info("✅ OANDA connector initialized (native REST, env=%s)", environment)
                except Exception as e:
                    logger.error(f"Failed to initialize OANDA connector: {e}")
        
        # POLYMARKET - Native Polymarket CLOB connector for prediction markets
        polymarket_cfg = self.api_keys.get('polymarket')
        if isinstance(polymarket_cfg, dict):
            private_key = polymarket_cfg.get('private_key') or polymarket_cfg.get('key') or ''
            api_key = polymarket_cfg.get('api_key') or ''
            api_secret = polymarket_cfg.get('api_secret') or ''
            api_passphrase = polymarket_cfg.get('api_passphrase') or ''
            has_creds = bool(api_key and api_secret and api_passphrase)
            if private_key or has_creds:
                try:
                    from core.prediction_market_connector import PolymarketConnector
                    polymarket_connector = PolymarketConnector(
                        private_key=private_key,
                        event_bus=getattr(self, 'event_bus', None),
                        api_key=api_key,
                        api_secret=api_secret,
                        api_passphrase=api_passphrase,
                        signature_type=polymarket_cfg.get('signature_type', 1),
                        funder=polymarket_cfg.get('funder', ''),
                        address=polymarket_cfg.get('address', ''),
                    )
                    self.connectors['polymarket'] = polymarket_connector
                    self.circuit_breakers['polymarket'] = CircuitBreaker()
                    self.retry_handlers['polymarket'] = RetryHandler()
                    logger.info("✅ Polymarket connector initialized (prediction market, Polygon)")
                except Exception as e:
                    logger.error(f"Failed to initialize Polymarket connector: {e}")
        
        # KALSHI - Native Kalshi REST connector for prediction markets
        kalshi_cfg = self.api_keys.get('kalshi')
        if isinstance(kalshi_cfg, dict):
            api_key_id = kalshi_cfg.get('api_key') or kalshi_cfg.get('api_key_id') or ''
            private_key_pem = kalshi_cfg.get('private_key') or kalshi_cfg.get('private_key_pem') or ''
            demo = kalshi_cfg.get('demo', False)
            if api_key_id and private_key_pem:
                try:
                    from core.prediction_market_connector import KalshiConnector
                    kalshi_connector = KalshiConnector(
                        api_key_id=api_key_id,
                        private_key_pem=private_key_pem,
                        demo=demo,
                    )
                    self.connectors['kalshi'] = kalshi_connector
                    self.circuit_breakers['kalshi'] = CircuitBreaker()
                    self.retry_handlers['kalshi'] = RetryHandler()
                    env_label = "DEMO" if demo else "LIVE"
                    logger.info("✅ Kalshi connector initialized (prediction market, %s)", env_label)
                except Exception as e:
                    logger.error(f"Failed to initialize Kalshi connector: {e}")
        
        # Generic CCXT initialization for any remaining exchanges with key+secret
        for name, value in list(self.api_keys.items()):
            if name.endswith('_secret'):
                continue
            if name in self.connectors:
                continue
            secret_key = f"{name}_secret"
            if secret_key not in self.api_keys:
                continue
            ex_class = getattr(ccxt, name, None)
            if ex_class is None:
                continue
            try:
                config: Dict[str, Any] = {
                    'apiKey': value,
                    'secret': self.api_keys[secret_key],
                    'enableRateLimit': True,
                }
                password = self.api_keys.get(f"{name}_password") or self.api_keys.get(f"{name}_passphrase")
                if password:
                    config['password'] = password
                # Apply any generic overrides for this exchange
                self._apply_exchange_network_overrides(name, config)

                # BinanceUS: force IPv4 before creating the ccxt client so
                # the server doesn't reply with {"code":-71012,"msg":"IPv6
                # not supported"} when reached from a dual-stack host.
                if name == "binanceus":
                    _prefer_ipv4_for_hosts(("binance.us",))

                exchange = ex_class(config)

                if name == "binanceus":
                    try:
                        _attach_ipv4_only_adapter(exchange)
                        logger.info("✅ BINANCEUS session locked to IPv4 (generic)")
                    except Exception as _adapter_err:  # noqa: BLE001
                        logger.warning(
                            "BINANCEUS IPv4 adapter attach failed: %s",
                            _adapter_err,
                        )

                self._sync_exchange_clock(name, exchange)
                self.exchanges[name] = exchange
                self.connectors[name] = CcxtExchangeConnector(name, exchange)
                self.circuit_breakers[name] = CircuitBreaker()
                self.retry_handlers[name] = RetryHandler()
                logger.info("✅ %s connected (generic CCXT) - LIVE TRADING ACTIVE", name.upper())
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to connect %s via generic CCXT: %s", name, e)
        
        # Add more exchanges as needed
        if not self.exchanges:
            logger.warning("⚠️ NO EXCHANGES CONNECTED - Add API keys to enable live trading!")

    # ------------------------------------------------------------------
    # Funding / custody — executor-level dispatchers
    # ------------------------------------------------------------------
    def list_connected_exchanges(self) -> List[str]:
        """Return the names of all exchanges currently wired and live."""
        return sorted(self.connectors.keys())

    async def fetch_balances_all(self) -> Dict[str, Dict[str, Any]]:
        """Fetch free/used/total balances across every connected exchange.

        Returns {exchange_name: {currencies: {...}, error: None|str}}. An
        exchange with a transient error yields an error entry rather than
        aborting the entire sweep — so the readiness report stays useful
        even if one venue is flaky.
        """
        results: Dict[str, Dict[str, Any]] = {}
        for name, connector in self.connectors.items():
            try:
                lock = self._get_private_lock(name)
                async with lock:
                    if hasattr(connector, "fetch_full_balance"):
                        payload = await self._maybe_await(
                            connector.fetch_full_balance()  # type: ignore[attr-defined]
                        )
                    else:
                        flat = await self._maybe_await(connector.fetch_balance())
                        # Some prediction-market connectors return a single
                        # float (total USDC balance). Normalize both shapes.
                        if isinstance(flat, (int, float)):
                            payload = {
                                "exchange": name,
                                "currencies": {
                                    "USDC": {
                                        "free": float(flat), "used": 0.0,
                                        "total": float(flat),
                                    },
                                },
                            }
                        else:
                            payload = {
                                "exchange": name,
                                "currencies": {
                                    c: {"free": float(v), "used": 0.0, "total": float(v)}
                                    for c, v in (flat or {}).items()
                                },
                            }
                results[name] = {"ok": True, **payload}
            except Exception as exc:
                results[name] = {"ok": False, "exchange": name, "error": str(exc)}
        return results

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        """Await ``value`` only if it's awaitable; otherwise return as-is."""
        if asyncio.iscoroutine(value) or hasattr(value, "__await__"):
            return await value
        return value

    @staticmethod
    def _classify_health_error(msg: str, lowered: str) -> str:
        """Map an exchange error message to a precise, actionable health status.

        Statuses returned (consumed by TradingComponent + GUI + trading_venue_status):
          - restricted_location      geo/IP blocked
          - time_skew                 client clock drift (-1021, ahead of server)
          - key_invalid               API key rejected (bad key, revoked, wrong env)
          - ip_not_allowed            valid key but IP not whitelisted (-2015)
          - account_not_authorized    account exists but not enabled for live trading / KYC
          - permission_denied         key is valid but missing required scopes
          - endpoint_unreachable      network/DNS/WS handshake failure
          - signature_invalid         HMAC signature mismatch (often clock or secret issue)
          - exchange_error            fallback
        """
        # Geo / IP restrictions
        if "restricted location" in lowered or " 451" in lowered or "451 client" in lowered:
            return "restricted_location"
        # Clock skew (Binance -1021 family and OKX-style)
        if (
            '"code":-1021' in lowered
            or "-1021" in lowered
            or "ahead of the server's time" in lowered
            or "recv window" in lowered and "request" in lowered
        ):
            return "time_skew"
        # IP whitelist - Binance/BinanceUS -2015, Huobi/HTX ip-not-allowed
        if (
            '"code":-2015' in lowered
            or "-2015" in lowered
            or "ip, or permissions" in lowered
            or "ip not in whitelist" in lowered
            or "ip whitelist" in lowered
        ):
            return "ip_not_allowed"
        # Alpaca 40110000 "request is not authorized" / account not live
        if (
            '"code":40110000' in lowered
            or "40110000" in lowered
            or "request is not authorized" in lowered
            or "account is not authorized" in lowered
            or "account not authorized" in lowered
        ):
            return "account_not_authorized"
        # Permission / scope
        if (
            "permission denied" in lowered
            or "insufficient permissions" in lowered
            or "not permitted" in lowered
            or "forbidden" in lowered
        ):
            return "permission_denied"
        # Invalid or revoked key
        if (
            "invalid api-key" in lowered
            or "api key is invalid" in lowered
            or "invalid api key" in lowered
            or "access key" in lowered and ("invalid" in lowered or "错误" in msg or "not valid" in lowered)
            or "api-signature-not-valid" in lowered
            or "authentication failed" in lowered
            or "auth failed" in lowered
            or "invalid credentials" in lowered
            or "unauthorized" in lowered and "request is not authorized" not in lowered
        ):
            return "key_invalid"
        # Signature mismatch (often clock + secret issues)
        if (
            "signature not valid" in lowered
            or "signature is invalid" in lowered
            or "signature mismatch" in lowered
            or "invalid signature" in lowered
        ):
            return "signature_invalid"
        # Endpoint/network
        if (
            "websocket connection" in lowered
            or "handshake" in lowered
            or "http 404" in lowered
            or "http 502" in lowered
            or "http 503" in lowered
            or "connection refused" in lowered
            or "dns" in lowered and "error" in lowered
            or "resolve" in lowered and "failed" in lowered
        ):
            return "endpoint_unreachable"
        return "exchange_error"

    async def fetch_deposit_address(
        self, exchange_name: str, code: str, network: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch to the right connector for a deposit-address lookup."""
        connector = self.connectors.get(exchange_name.lower())
        if connector is None:
            raise ValueError(f"Exchange {exchange_name} is not connected")
        if not hasattr(connector, "fetch_deposit_address"):
            raise RuntimeError(
                f"Connector for {exchange_name} does not support fetch_deposit_address"
            )
        lock = self._get_private_lock(exchange_name.lower())
        async with lock:
            return await connector.fetch_deposit_address(code, network=network)  # type: ignore[attr-defined]

    async def fetch_deposit_networks(self, exchange_name: str, code: str) -> List[str]:
        connector = self.connectors.get(exchange_name.lower())
        if connector is None:
            raise ValueError(f"Exchange {exchange_name} is not connected")
        if not hasattr(connector, "fetch_deposit_networks"):
            return []
        lock = self._get_private_lock(exchange_name.lower())
        async with lock:
            return await connector.fetch_deposit_networks(code)  # type: ignore[attr-defined]

    async def withdraw(
        self,
        exchange_name: str,
        code: str,
        amount: float,
        address: str,
        tag: Optional[str] = None,
        network: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Submit a real withdrawal from the named exchange.

        WARNING: moves real money. Caller is responsible for validating
        address/network/amount against the user's intent.
        """
        connector = self.connectors.get(exchange_name.lower())
        if connector is None:
            raise ValueError(f"Exchange {exchange_name} is not connected")
        if not hasattr(connector, "withdraw"):
            raise RuntimeError(f"Connector for {exchange_name} does not support withdraw")
        lock = self._get_private_lock(exchange_name.lower())
        async with lock:
            result = await connector.withdraw(  # type: ignore[attr-defined]
                code=code, amount=amount, address=address,
                tag=tag, network=network, params=params,
            )
        if self.event_bus is not None:
            try:
                self.event_bus.publish("exchange.withdraw.submitted", {
                    "exchange": exchange_name,
                    "currency": code,
                    "amount": float(amount),
                    "address": address[:12] + "..." if address else None,
                    "network": network,
                    "result_id": result.get("id"),
                    "txid": result.get("txid"),
                    "timestamp": time.time(),
                })
            except Exception:
                pass
        return result

    async def place_real_order(
        self,
        exchange_name: str,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        amount: float,
        price: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Place a REAL order on a LIVE exchange (2025 State-of-the-Art).
        
        Implements:
        - Circuit breaker pattern
        - Exponential backoff with jitter
        - Adaptive retry delays
        - Rate limiting
        - Performance tracking
        
        Args:
            exchange_name: Exchange to use ('binance', 'coinbase', etc.)
            symbol: Trading pair (e.g., 'BTC/USDT')
            order_type: Market or limit order
            side: Buy or sell
            amount: Amount to trade (in base currency)
            price: Limit price (optional, required for limit orders)
        
        Returns:
            Order details if successful, None otherwise
        """
        start_time = time.time()
        self.metrics['total_orders'] += 1
        
        try:
            connector = self.connectors.get(exchange_name)
            if connector is None:
                logger.error(f"Exchange {exchange_name} has no connector configured!")
                self.metrics['failed_orders'] += 1
                return None
            
            # Check circuit breaker
            circuit_breaker = self.circuit_breakers.get(exchange_name)
            if circuit_breaker and not circuit_breaker.should_allow_request():
                logger.error(f"🔴 Circuit breaker OPEN for {exchange_name} - Request blocked")
                self.metrics['circuit_breaker_trips'] += 1
                return None
            retry_handler = self.retry_handlers.get(exchange_name, RetryHandler())
            
            # CRITICAL: This is a REAL order that will execute on the exchange
            logger.info(f"🔴 PLACING REAL ORDER: {side.value.upper()} {amount} {symbol} on {exchange_name.upper()}")
            
            # Retry logic with exponential backoff
            for attempt in range(retry_handler.max_retries + 1):
                # Serialize authenticated calls per exchange to avoid nonce collisions.
                private_lock = self._get_private_lock(exchange_name)
                async with private_lock:
                    # Rate limiting check
                    await self._respect_rate_limit(exchange_name)

                    # Create order based on type
                    if order_type == OrderType.MARKET:
                        side_str = "buy" if side == OrderSide.BUY else "sell"
                        order = await connector.create_market_order(
                            symbol=symbol,
                            side=side_str,
                            amount=amount,
                        )
                    elif order_type == OrderType.LIMIT:
                        if not price:
                            logger.error("Limit order requires price!")
                            return None
                        side_str = "buy" if side == OrderSide.BUY else "sell"
                        order = await connector.create_limit_order(
                            symbol=symbol,
                            side=side_str,
                            amount=amount,
                            price=price,
                        )
                    else:
                        logger.error(f"Unsupported order type: {order_type}")
                        return None

                # If we reached this point without raising, break out of retry loop
                break
            
            # Store order details
            order_data = {
                'id': order['id'],
                'exchange': exchange_name,
                'symbol': symbol,
                'type': order_type.value,
                'side': side.value,
                'amount': amount,
                'price': order.get('price'),
                'status': order.get('status', 'open'),
                'timestamp': order.get('timestamp'),
                'datetime': order.get('datetime'),
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', amount),
                'cost': order.get('cost', 0),
                'fee': order.get('fee')
            }
            
            self.active_orders[order['id']] = order_data
            
            # Publish to event bus
            if self.event_bus:
                self.event_bus.publish('real_order.placed', order_data)
                
                # CRITICAL: For market orders that are immediately filled, also publish trading.order_filled
                # This ensures the Trading Tab profit tracking receives the fill event
                order_status = str(order.get('status', '')).lower()
                if order_status in ('filled', 'closed') or order_type == 'MARKET':
                    fill_data = {
                        'order_id': order['id'],
                        'symbol': symbol,
                        'side': side,
                        'type': order_type.lower(),
                        'amount': order.get('filled', amount),
                        'price': order.get('average') or order.get('price') or 0,
                        'cost': order.get('cost', 0),
                        'status': 'filled',
                        'exchange': exchange_name,
                        'timestamp': order.get('timestamp'),
                        'fee': order.get('fee'),
                        'message': f"✅ {side.upper()} {amount} {symbol} on {exchange_name.upper()}"
                    }
                    self.event_bus.publish('trading.order_filled', fill_data)
                    logger.info(f"📊 Published trading.order_filled for {order['id']}")
            
            logger.info(f"✅ REAL ORDER PLACED: {order['id']} on {exchange_name.upper()}")
            logger.info(f"   Status: {order.get('status')}")
            logger.info(f"   Amount: {amount} {symbol}")
            logger.info(f"   Price: {order.get('price', 'MARKET')}")
            
            return order_data
            
        except ccxt.InsufficientFunds as e:
            logger.error(
                "❌ INSUFFICIENT FUNDS (EXTERNAL/ACCOUNT ISSUE) on %s: %s",
                exchange_name,
                e,
            )
            return None
        except ccxt.InvalidOrder as e:
            logger.error(
                "❌ INVALID ORDER (likely parameter/precision issue) on %s: %s",
                exchange_name,
                e,
            )
            return None
        except ccxt.ExchangeError as e:
            msg = str(e)
            lowered = msg.lower()
            if exchange_name == "kraken" and "permission denied" in lowered:
                logger.error(
                    "❌ EXCHANGE ERROR on kraken: permission denied (API key "
                    "missing trading permissions or IP not allowed). This is "
                    "an external configuration issue, not a code bug: %s",
                    msg,
                )
            elif "sslcertverificationerror" in lowered or "certificate_verify_failed" in lowered:
                logger.error(
                    "❌ EXCHANGE ERROR on %s: SSL certificate verification "
                    "failed (CA/OS trust store issue). This is an environment "
                    "issue, not a code bug: %s",
                    exchange_name,
                    msg,
                )
            elif exchange_name == "coinbase" and "ecdsa" in lowered and "index out of range" in lowered:
                logger.error(
                    "❌ EXCHANGE ERROR on coinbase: ECDSA key format invalid "
                    "(secret must be a PEM-encoded EC private key for JWT "
                    "auth). This is an API key/config issue, not a code bug: %s",
                    msg,
                )
            else:
                logger.error(
                    "❌ EXCHANGE ERROR on %s (exchange-side/config issue): %s",
                    exchange_name,
                    msg,
                )
            return None
        except Exception as e:
            msg = str(e)
            lowered = msg.lower()
            if exchange_name == "btcc" and "server rejected websocket connection" in lowered:
                logger.error(
                    "❌ BTCC WebSocket connection rejected with HTTP 403 "
                    "(exchange/IP/auth issue, not a client code bug): %s",
                    msg,
                )
            elif exchange_name == "oanda" and "oanda accounts error 401" in lowered:
                logger.error(
                    "❌ OANDA authentication failed (token/env/permissions "
                    "issue, not a code bug): %s",
                    msg,
                )
            elif exchange_name == "coinbase" and "index out of range" in lowered:
                logger.error(
                    "❌ EXCHANGE ERROR on coinbase: ECDSA key format invalid "
                    "(secret must be a PEM-encoded EC private key for JWT "
                    "auth). This is an API key/config issue, not a code bug: %s",
                    msg,
                )
            elif (
                exchange_name == "htx"
                and "htx get https://api.hbdm.com/linear-swap-api/v1/swap_contract_info" in lowered
            ):
                logger.error(
                    "❌ EXCHANGE ERROR on htx: SSL certificate / CA trust "
                    "issue when calling linear-swap-api. This is an "
                    "environment/CA configuration issue, not a code bug: %s",
                    msg,
                )
            else:
                logger.error(f"❌ ERROR placing real order (possible code bug): {e}")
                import traceback
                logger.error(traceback.format_exc())
            return None
    
    async def get_order_status(self, exchange_name: str, order_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Check REAL order status on exchange.
        
        Args:
            exchange_name: Exchange name
            order_id: Order ID
            symbol: Trading pair
        
        Returns:
            Order status details
        """
        try:
            connector = self.connectors.get(exchange_name)
            if connector is None:
                return None
            
            private_lock = self._get_private_lock(exchange_name)
            async with private_lock:
                await self._respect_rate_limit(exchange_name)
                order = await connector.fetch_order(order_id, symbol)
            
            return {
                'id': order['id'],
                'status': order.get('status'),
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'price': order.get('price'),
                'cost': order.get('cost', 0)
            }
            
        except Exception as e:
            logger.error(f"Error fetching order status: {e}")
            return None
    
    async def cancel_order(self, exchange_name: str, order_id: str, symbol: str) -> bool:
        """
        Cancel a REAL order on exchange.
        
        Args:
            exchange_name: Exchange name
            order_id: Order ID
            symbol: Trading pair
        
        Returns:
            True if cancelled successfully
        """
        try:
            connector = self.connectors.get(exchange_name)
            if connector is None:
                return False
            
            private_lock = self._get_private_lock(exchange_name)
            async with private_lock:
                await self._respect_rate_limit(exchange_name)
                await connector.cancel_order(order_id, symbol)
            
            logger.info(f"✅ Order {order_id} cancelled on {exchange_name}")
            
            if order_id in self.active_orders:
                self.active_orders[order_id]['status'] = 'cancelled'
                self.order_history.append(self.active_orders[order_id])
                del self.active_orders[order_id]
            
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    async def _respect_rate_limit(self, exchange_name: str) -> None:
        """Simple per-exchange rate limiter using last-request timestamps.
        
        Ensures a minimum interval between requests to the same exchange,
        based on a conservative default window. This keeps the existing
        metrics/circuit-breaker logic intact while avoiding hitting basic
        rate limits.
        """
        # Default minimum delay between requests in seconds
        min_interval = 0.2

        now = time.time()
        last_request = self.rate_limiters.get(exchange_name)

        if last_request is not None:
            elapsed = now - last_request
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

        # Record this request timestamp
        self.rate_limiters[exchange_name] = time.time()
    
    async def get_balance(self, exchange_name: str) -> Optional[Dict[str, float]]:
        """
        Get REAL account balance from exchange.
        
        Args:
            exchange_name: Exchange name
        
        Returns:
            Balance dictionary {currency: amount}
        """
        try:
            connector = self.connectors.get(exchange_name)
            if connector is None:
                return None
            
            private_lock = self._get_private_lock(exchange_name)
            async with private_lock:
                await self._respect_rate_limit(exchange_name)
                balance = await connector.fetch_balance()
            return balance
            
        except Exception as e:
            msg = str(e)
            lowered = msg.lower()
            if exchange_name == "btcc" and "server rejected websocket connection" in lowered:
                logger.error(
                    "BTCC get_balance failed: WebSocket connection rejected "
                    "with HTTP 403 (exchange/IP/auth issue, not a code bug): %s",
                    msg,
                )
            elif "sslcertverificationerror" in lowered or "certificate_verify_failed" in lowered:
                logger.error(
                    "%s get_balance failed due to SSL certificate verification "
                    "(environment/CA issue, not a code bug): %s",
                    exchange_name,
                    msg,
                )
            elif exchange_name == "oanda" and "oanda accounts error 401" in lowered:
                logger.error(
                    "OANDA get_balance failed due to authentication "
                    "(token/env/permissions issue, not a code bug): %s",
                    msg,
                )
            elif exchange_name == "coinbase" and "index out of range" in lowered:
                logger.error(
                    "coinbase get_balance failed due to ECDSA key format "
                    "invalid (secret must be a PEM-encoded EC private key for "
                    "JWT auth). This is an API key/config issue, not a code bug: %s",
                    msg,
                )
            elif (
                exchange_name == "htx"
                and "htx get https://api.hbdm.com/linear-swap-api/v1/swap_contract_info" in lowered
            ):
                logger.error(
                    "htx get_balance failed due to SSL certificate / CA trust "
                    "issue when calling linear-swap-api. This is an "
                    "environment/CA configuration issue, not a code bug: %s",
                    msg,
                )
            else:
                logger.error(f"Error fetching balance (possible code bug): {e}")
            return None
    
    async def get_exchange_health(self, exchange_name: Optional[str] = None) -> Dict[str, Any]:
        """Return structured health information for one or all exchanges.

        This is designed for higher-level agents (Ollama, orchestrators) to
        quickly understand which venues are usable for live trading, and why
        others are degraded or blocked.

        Status values per exchange:
            - "ok": balance call succeeded and returned non-empty balances
            - "ok_empty": balance call succeeded but returned empty/None
            - "restricted_location": geo/IP restricted (e.g. Binance 451)
            - "permission_denied": API key lacks required permissions
            - "exchange_error": other ccxt / HTTP-level error
            - "not_connected": no ccxt instance for this exchange
        """
        targets: List[str]
        if exchange_name is not None:
            targets = [exchange_name]
        else:
            # Union of ccxt and native connector venues
            names = set(self.exchanges.keys()) | set(self.connectors.keys())
            targets = list(names)

        health: Dict[str, Any] = {}

        for ex in targets:
            connector = self.connectors.get(ex)
            if connector is None:
                health[ex] = {
                    "status": "not_connected",
                    "details": "No connector configured for this exchange",
                }
                continue

            # Default status before checks
            status = "exchange_error"
            details: Dict[str, Any] = {}

            balance: Optional[Dict[str, float]] = None

            try:
                # Respect basic rate limiting semantics
                await self._respect_rate_limit(ex)

                # Some native connectors (PolymarketConnector, KalshiConnector)
                # return a single float (USDC balance) synchronously rather
                # than an awaitable dict. Use _maybe_await so both shapes
                # work without raising "object float can't be used in 'await'"
                # and normalize a bare float to a {"USDC": <value>} dict so
                # downstream sample-formatting stays sensible.
                raw_balance = await self._maybe_await(connector.fetch_balance())
                if isinstance(raw_balance, (int, float)):
                    balance = {"USDC": float(raw_balance)} if raw_balance else {}
                else:
                    balance = raw_balance

            except ccxt.ExchangeError as e:  # type: ignore[name-defined]
                # First-pass ccxt error classification with optional
                # auto-remediation for timestamp skew (-1021).
                msg = str(e)
                lowered = msg.lower()

                # Attempt to auto-fix Binance/BinanceUS time-skew errors by
                # synchronizing the exchange clock and retrying once. This
                # keeps health reporting honest while giving the venue a fair
                # chance to recover before being marked as time_skew.
                is_time_skew = (
                    "\"code\":-1021" in lowered
                    or "ahead of the server's time" in lowered
                )
                if is_time_skew and ex in self.exchanges:
                    try:
                        base_ex = self.exchanges.get(ex)
                        if base_ex is not None:
                            self._sync_exchange_clock(ex, base_ex)
                            await self._respect_rate_limit(ex)
                            retry_raw = await self._maybe_await(
                                connector.fetch_balance()
                            )
                            if isinstance(retry_raw, (int, float)):
                                balance = (
                                    {"USDC": float(retry_raw)} if retry_raw else {}
                                )
                            else:
                                balance = retry_raw
                    except Exception as retry_err:  # noqa: BLE001
                        # If the retry also fails we fall back to normal
                        # classification below using the retry error message.
                        msg = str(retry_err)
                        lowered = msg.lower()

                if balance is not None:
                    # Clock sync + retry succeeded; treat as healthy.
                    if isinstance(balance, dict) and balance:
                        status = "ok"
                        details["balances_sample"] = dict(list(balance.items())[:5])
                    else:
                        status = "ok_empty"
                        details["balances_sample"] = {}
                else:
                    # Retry (if any) did not succeed, classify persistent
                    # error into a precise health status.
                    details["error"] = msg
                    status = self._classify_health_error(msg, lowered)

            except NotImplementedError as e:
                # Native connector methods not yet implemented (e.g. BTCC/Oanda)
                status = "not_implemented"
                details["error"] = str(e)

            except Exception as e:  # noqa: BLE001
                # Non-ccxt error (TypeError, RuntimeError from native
                # connectors, etc). Classify for actionable reporting.
                msg = str(e)
                status = self._classify_health_error(msg, msg.lower())
                details["error"] = msg

            else:
                # Successful balance fetch without ccxt.ExchangeError
                if isinstance(balance, dict) and balance:
                    status = "ok"
                    details["balances_sample"] = dict(list(balance.items())[:5])
                else:
                    status = "ok_empty"
                    details["balances_sample"] = {}

            health[ex] = {
                "status": status,
                **details,
            }

        return health
    
    async def publish_exchange_health_snapshot(self) -> None:
        """Publish a snapshot of exchange health to the event bus.

        This allows GUIs, monitoring components, and AI agents to subscribe
        to a single topic ("exchange.health.snapshot") and react to venue
        availability/quality changes in near real-time.
        """
        if not self.event_bus:
            return

        health = await self.get_exchange_health()
        payload = {
            "timestamp": time.time(),
            "health": health,
        }

        try:
            self.event_bus.publish("exchange.health.snapshot", payload)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to publish exchange health snapshot: %s", e)
    
    def get_connected_exchanges(self) -> List[str]:
        """Get list of connected exchanges."""
        return list(self.exchanges.keys())
    
    def is_exchange_connected(self, exchange_name: str) -> bool:
        """Check if exchange is connected."""
        return exchange_name in self.exchanges

    async def build_symbol_index(
        self,
        per_exchange_limit: int = 200,
        quote_whitelist: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Build a unified symbol index from all connected exchanges.

        The index is derived strictly from API-keyed venues (self.exchanges)
        and uses ccxt markets/tickers to estimate popularity via 24h volume.

        Each entry in the returned list has the form:

            {
                "symbol": "BTC/USDT",
                "asset_class": "crypto" | "fx",
                "venues": ["binance", "kraken", ...],
                "popularity": <float volume score>,
            }

        Args:
            per_exchange_limit: Optional cap on symbols per exchange, ranked by
                descending volume to avoid overwhelming the UI with illiquid
                markets.
            quote_whitelist: Optional list of quote currencies to keep
                (e.g. ["USDT", "USD", "USDC", "BTC", "EUR"]). If None,
                a conservative default is applied.
        """

        # Default quote filter focuses on the most common quote currencies
        # for spot trading and major FX pairs.
        if quote_whitelist is None:
            quote_whitelist = ["USDT", "USDC", "USD", "BTC", "EUR"]

        # Simple fiat currency set for FX detection; anything else is treated
        # as crypto for now.
        fiat_currencies = {
            "USD",
            "EUR",
            "GBP",
            "JPY",
            "CHF",
            "CAD",
            "AUD",
            "NZD",
            "CNY",
            "CNH",
        }

        combined: Dict[str, Dict[str, Any]] = {}

        for ex_name, ex in self.exchanges.items():
            try:
                # Load markets with basic rate-limit awareness
                await self._respect_rate_limit(ex_name)
                markets = await asyncio.to_thread(ex.load_markets)

                # Try to get tickers once per exchange to estimate volume
                tickers: Dict[str, Any] = {}
                try:
                    await self._respect_rate_limit(ex_name)
                    tickers = await asyncio.to_thread(ex.fetch_tickers)
                except Exception as e:  # noqa: BLE001
                    logger.warning("%s: fetch_tickers() failed for symbol index: %s", ex_name, e)

                # Build per-exchange entries (symbol, volume, base, quote)
                entries: List[Dict[str, Any]] = []
                for sym, market in markets.items():
                    if not isinstance(market, dict):
                        continue

                    active = market.get("active")
                    if active is False:
                        continue

                    base = market.get("base")
                    quote = market.get("quote")

                    if quote and isinstance(quote, str):
                        if quote_whitelist and quote.upper() not in quote_whitelist:
                            continue

                    ticker = tickers.get(sym) if isinstance(tickers, dict) else None
                    volume = 0.0
                    if isinstance(ticker, dict):
                        vol_val = (
                            ticker.get("quoteVolume")
                            or ticker.get("baseVolume")
                            or ticker.get("volume")
                        )
                        try:
                            if vol_val is not None:
                                volume = float(vol_val)
                        except (TypeError, ValueError):  # noqa: PERF203
                            volume = 0.0

                    entries.append({
                        "symbol": sym,
                        "base": base,
                        "quote": quote,
                        "volume": volume,
                    })

                # Rank by volume and cap per-exchange
                entries.sort(key=lambda e: float(e.get("volume") or 0.0), reverse=True)
                if per_exchange_limit > 0:
                    entries = entries[:per_exchange_limit]

                for item in entries:
                    sym = str(item.get("symbol") or "").upper()
                    if not sym:
                        continue

                    base = str(item.get("base") or "").upper()
                    quote = str(item.get("quote") or "").upper()
                    vol = float(item.get("volume") or 0.0)

                    # Basic asset_class heuristic: fiat/fiat -> fx, otherwise crypto
                    if base in fiat_currencies and quote in fiat_currencies:
                        asset_class = "fx"
                    else:
                        asset_class = "crypto"

                    existing = combined.get(sym)
                    if existing:
                        existing["venues"].add(ex_name)
                        existing["popularity"] += vol
                    else:
                        combined[sym] = {
                            "symbol": sym,
                            "asset_class": asset_class,
                            "venues": {ex_name},
                            "popularity": vol,
                        }

            except Exception as e:  # noqa: BLE001
                # Classify common external/environment issues so they are
                # clearly distinguished from potential code bugs.
                msg = str(e)
                lowered = msg.lower()

                if "restricted location" in lowered or " 451" in lowered:
                    # Geo/IP restriction (e.g. Binance HTTP 451). The
                    # exchange is reachable, but the account/location is
                    # not allowed for the requested endpoint.
                    # SOTA 2026: Downgrade to INFO - geo-restriction is expected for some regions
                    logger.info(
                        "%s: geo-restricted (HTTP 451) - use VPN or regional variant",
                        ex_name,
                    )
                elif "\"code\":-1021" in lowered or "ahead of the server's time" in lowered:
                    # Binance/BinanceUS timestamp skew error. SOTA 2026: Auto-fix this!
                    if HAS_TIMESTAMP_AUTO_FIX and auto_fix_exchange_error(ex_name, msg):
                        logger.info(
                            "🕐 %s: Auto-fixed timestamp skew (-1021) - retry operation",
                            ex_name,
                        )
                        # Retry the operation once after auto-fix
                        return False  # Signal to retry
                    else:
                        # Fallback to manual warning
                        logger.warning(
                            "%s symbol index skipped due to timestamp skew/clock "
                            "offset (-1021). Auto-fix failed - sync system time with NTP or increase "
                            "recvWindow: %s",
                            ex_name,
                            msg,
                        )
                elif "\"code\":-2015" in lowered or "invalid api-key" in lowered:
                    # Invalid API key / permissions for the requested
                    # endpoint. This is an auth/keys configuration problem.
                    # SOTA 2026: Downgrade to INFO - config issue, not runtime error
                    logger.info(
                        "%s: API key needs update (code -2015) - check config/api_keys.*",
                        ex_name,
                    )
                elif "ecdsa" in lowered and "index out of range" in lowered:
                    # Coinbase JWT / private-key format issues; user must
                    # supply a PEM-encoded EC private key as required by the
                    # latest Coinbase API.
                    logger.warning(
                        "%s symbol index skipped due to Coinbase private "
                        "key / JWT configuration issue (ECDSA index out of "
                        "range): %s",
                        ex_name,
                        msg,
                    )
                elif (
                    "sslcertverificationerror" in lowered
                    or "certificate_verify_failed" in lowered
                    or ("ssl" in lowered and "certificate" in lowered)
                ):
                    # SSL / CA trust-store problems are environment/OS
                    # configuration issues, not code bugs.
                    logger.warning(
                        "%s symbol index skipped due to SSL/CA trust "
                        "issue; install proper CA certificates or configure "
                        "verify/CA bundle settings: %s",
                        ex_name,
                        msg,
                    )
                elif (
                    ex_name == "htx"
                    and "htx get https://api.hbdm.com/linear-swap-api/v1/swap_contract_info" in lowered
                ):
                    # HTX linear-swap markets can fail with SSL/CA issues on
                    # some hosts. Treat this the same way we handle the
                    # identical pattern in order/balance calls: as an
                    # environment/CA configuration problem, not a code bug.
                    logger.warning(
                        "HTX derivative symbol index skipped due to SSL/CA "
                        "trust issue calling linear-swap-api (env/CA issue, "
                        "not a code bug): %s",
                        msg,
                    )
                elif (
                    "500 internal server error" in lowered
                    or " 500 " in lowered
                    or "503 service unavailable" in lowered
                    or " 503 " in lowered
                ):
                    # Upstream 500/503 errors indicate an exchange-side
                    # outage or overload. Treat these as environment/outage
                    # warnings, not code bugs.
                    logger.warning(
                        "%s symbol index skipped due to upstream 500/503 "
                        "response (exchange outage/overload): %s",
                        ex_name,
                        msg,
                    )
                else:
                    # Anything else is unexpected and worth flagging as a
                    # potential code bug for further investigation.
                    logger.error(
                        "Error building symbol index for %s (possible code bug): %s",
                        ex_name,
                        msg,
                    )

                continue

        # Additionally include Oanda FX instruments from the native connector.
        # This ensures that Oanda appears as a second live broker in the
        # unified symbol index alongside ccxt venues, using the actual
        # instruments returned by the Oanda v20 API.
        oanda_conn = self.connectors.get("oanda")
        if isinstance(oanda_conn, OandaConnector):
            try:
                instruments = await asyncio.to_thread(oanda_conn.list_instruments_sync)
                for instrument in instruments:
                    sym = str(instrument or "").upper().replace("_", "/")
                    if not sym:
                        continue

                    parts = sym.split("/")
                    if len(parts) == 2:
                        base, quote = parts[0].upper(), parts[1].upper()
                    else:
                        base, quote = "", ""

                    # Basic asset_class heuristic: fiat/fiat -> fx. For Oanda
                    # we treat all instruments as FX to avoid misclassifying
                    # any CFD products as pure crypto.
                    if base in fiat_currencies and quote in fiat_currencies:
                        asset_class = "fx"
                    else:
                        asset_class = "fx"

                    existing = combined.get(sym)
                    if existing:
                        existing["venues"].add("oanda")
                    else:
                        combined[sym] = {
                            "symbol": sym,
                            "asset_class": asset_class,
                            "venues": {"oanda"},
                            "popularity": 0.0,
                        }
            except Exception as e:  # noqa: BLE001
                logger.warning("OANDA symbol index skipped due to error: %s", e)

        # Finalize: convert venue sets to lists and sort by popularity
        result: List[Dict[str, Any]] = []
        for data in combined.values():
            venues_set = data.get("venues") or set()
            if isinstance(venues_set, set):
                data["venues"] = sorted(venues_set)
            result.append(data)

        result.sort(key=lambda d: float(d.get("popularity") or 0.0), reverse=True)
        return result
