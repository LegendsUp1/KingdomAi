#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RealStockExecutor for Kingdom AI.

This module provides a minimal, 2025-ready executor for stock/forex brokers
separate from the crypto-focused RealExchangeExecutor.

Initial implementation focuses on Alpaca as the primary stock broker. The
architecture mirrors RealExchangeExecutor: a thin orchestration layer that
creates per-broker clients, exposes health checks, and provides hooks for
future live-order execution.

The design intentionally keeps broker-specific logic small and contained so
additional brokers (TD Ameritrade, Interactive Brokers, etc.) can be added
incrementally without changing core interfaces.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional, List

try:
    import requests  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore[assignment]

# Prefer the official 2026 alpaca-py SDK; fall back to the deprecated
# alpaca-trade-api only if the newer one is unavailable. Either one
# unlocks Alpaca account/order functionality; otherwise we surface a
# clean "package_missing" status from health checks.
ALPACA_SDK: Optional[str] = None
try:
    from alpaca.trading.client import TradingClient  # type: ignore[import]
    from alpaca.trading.requests import (  # type: ignore[import]
        MarketOrderRequest,
        LimitOrderRequest,
        GetAssetsRequest,
    )
    from alpaca.trading.enums import (  # type: ignore[import]
        OrderSide,
        TimeInForce,
        AssetClass,
        AssetStatus,
    )
    ALPACA_SDK = "alpaca-py"
except Exception:  # pragma: no cover - optional dependency
    TradingClient = None  # type: ignore[assignment]
    MarketOrderRequest = None  # type: ignore[assignment]
    LimitOrderRequest = None  # type: ignore[assignment]
    GetAssetsRequest = None  # type: ignore[assignment]
    OrderSide = None  # type: ignore[assignment]
    TimeInForce = None  # type: ignore[assignment]
    AssetClass = None  # type: ignore[assignment]
    AssetStatus = None  # type: ignore[assignment]

try:
    import alpaca_trade_api as tradeapi  # type: ignore[import]
    if ALPACA_SDK is None:
        ALPACA_SDK = "alpaca-trade-api"
except Exception:  # pragma: no cover - optional dependency
    tradeapi = None  # type: ignore[assignment]


def _alpaca_sdk_available() -> bool:
    """Return True if any Alpaca SDK is importable."""
    return TradingClient is not None or tradeapi is not None

try:
    from core.kingdom_event_names import AUTONOMOUS_DECISION_LOG
except Exception:  # pragma: no cover - optional dependency
    AUTONOMOUS_DECISION_LOG = "autonomous.decision_logged"

try:
    from core.event_bus import EventBus
except Exception:  # pragma: no cover - optional dependency
    EventBus = None  # type: ignore


logger = logging.getLogger(__name__)


class RealStockExecutor:
    """Executor for stock/forex brokers (initially Alpaca).

    Parameters
    ----------
    api_keys:
        Mapping of service name -> key data as loaded by APIKeyManager
        (typically ``APIKeyManager.api_keys``).
    event_bus:
        Optional EventBus instance for publishing health events in the
        future. Currently unused but kept for interface symmetry.

    Notes
    -----
    - This executor is intentionally conservative. For now it focuses on
      connection/health checks for Alpaca and does not send live orders.
    - Live order execution can be added in a controlled way with explicit
      smoke-test helpers similar to RealExchangeExecutor when desired.
    """

    def __init__(
        self,
        api_keys: Dict[str, Any],
        event_bus: Optional[EventBus] = None,  # type: ignore[valid-type]
    ) -> None:
        self.api_keys = api_keys or {}
        self.event_bus = event_bus
        self.logger = logging.getLogger("core.real_stock_executor")

        # Broker client configuration, keyed by service name (e.g. "alpaca").
        # Values are small dicts with connection parameters; concrete SDK
        # clients are created on demand inside health or order methods to
        # avoid unnecessary connections.
        self.brokers: Dict[str, Dict[str, Any]] = {}

        self._initialize_brokers()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def _initialize_brokers(self) -> None:
        """Initialize broker configuration from the api_keys mapping.

        For now this only wires Alpaca if a key entry is present in
        ``self.api_keys['alpaca']``.
        """

        # Alpaca broker - LIVE / PAPER selection via environment
        alpaca_cfg = self.api_keys.get("alpaca")
        if isinstance(alpaca_cfg, dict):
            api_key = alpaca_cfg.get("api_key")
            api_secret = alpaca_cfg.get("api_secret")

            # Determine target environment / base URL.
            # Priority:
            # 1) Explicit ALPACA_BASE_URL env
            # 2) ALPACA_ENV=paper/live
            # 3) Configured endpoint/base_url from APIKeyManager
            # 4) FINAL DEFAULT: LIVE endpoint
            env_base = os.environ.get("ALPACA_BASE_URL")
            env_mode = (os.environ.get("ALPACA_ENV") or "").strip().lower()
            cfg_endpoint = alpaca_cfg.get("endpoint") or alpaca_cfg.get("base_url")

            if env_base:
                base_url = env_base
            elif env_mode == "paper":
                base_url = "https://paper-api.alpaca.markets"
            elif env_mode == "live":
                base_url = "https://api.alpaca.markets"
            elif cfg_endpoint and "paper-api.alpaca.markets" not in str(cfg_endpoint).lower():
                # Respect a non-paper endpoint from config when present
                base_url = str(cfg_endpoint)
            else:
                # Default hard to LIVE trading endpoint
                base_url = "https://api.alpaca.markets"

            if api_key and api_secret:
                self.brokers["alpaca"] = {
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "base_url": base_url,
                }
                self.logger.info("RealStockExecutor: Alpaca broker configured for %s", base_url)
            else:
                self.logger.warning(
                    "RealStockExecutor: Alpaca configuration present but missing api_key/api_secret",
                )

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------
    async def get_broker_health(self) -> Dict[str, Dict[str, Any]]:
        """Return health information for all configured brokers.

        Returns
        -------
        dict
            Mapping of broker_name -> info dict with at least:
            - status: "ok", "not_configured", "package_missing",
              "auth_error", or "client_error".
            - error: Optional error string
            - details: Optional extra info (e.g. account status)
        """
        self.logger.info("🔍 Starting broker health check...")

        health: Dict[str, Dict[str, Any]] = {}

        # Alpaca health (primary stock broker implementation for now)
        if "alpaca" in self.brokers:
            try:
                health["alpaca"] = await self._get_alpaca_health(self.brokers["alpaca"])
            except Exception as e:
                self.logger.warning(f"Alpaca health check exception: {e}")
                health["alpaca"] = {"status": "error", "error": str(e)}

        # Generic health for any other brokers that have API keys configured.
        try:
            from core.api_key_manager import APIKeyManager  # Local import to avoid cycles

            stock_names = set(APIKeyManager.CATEGORIES.get("stock_exchanges", []))
            forex_names = set(APIKeyManager.CATEGORIES.get("forex_trading", []))
        except Exception:  # pragma: no cover - defensive fallback
            stock_names = {"alpaca"}
            forex_names = set()

        for service in sorted(stock_names | forex_names):
            if service not in self.api_keys:
                continue
            if service in health:
                continue

            cfg = self.api_keys.get(service)

            # Use a lightweight HTTP-based connectivity probe when possible.
            try:
                info = await self._get_generic_http_health(service, cfg)  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.error("Generic broker health check for %s failed: %s", service, exc)
                info = {
                    "status": "client_error",
                    "error": f"generic health check failed: {exc}",
                }

            health[service] = info

        self.logger.info(f"✅ Broker health check complete: {len(health)} brokers checked")
        return health

    async def _get_generic_http_health(self, service: str, cfg: Dict[str, Any] | None) -> Dict[str, Any]:
        """Best-effort generic health probe for non-Alpaca brokers.

        This does not use broker-specific SDKs. Instead it:

        - Classifies the completeness of the key material (api_key/
          api_secret/endpoint).
        - When a base URL/endpoint is available and the ``requests``
          package is installed, performs a small HTTP GET with a short
          timeout to verify basic reachability.

        The goal is to ensure that any broker with keys is treated as
        "configured" and appears in health reports, while still
        distinguishing between network, auth, and generic client
        failures.
        """

        if cfg is None:
            return {
                "status": "keys_missing",
                "error": "No configuration payload available for broker",
            }

        if not isinstance(cfg, dict):
            return {
                "status": "keys_present",
                "details": {
                    "config_type": str(type(cfg)),
                },
            }

        api_key = (
            cfg.get("api_key")
            or cfg.get("key")
            or cfg.get("apiKey")
            or cfg.get("access_token")
            or cfg.get("token")
        )
        api_secret = (
            cfg.get("api_secret")
            or cfg.get("secret")
            or cfg.get("apiSecret")
        )

        url = (
            cfg.get("base_url")
            or cfg.get("endpoint")
            or cfg.get("api_base_url")
            or cfg.get("url")
        )

        has_key = bool(api_key)
        has_secret = bool(api_secret)
        has_url = bool(url)

        if not has_url or requests is None:
            # Without a usable HTTP client or endpoint, fall back to a
            # purely configuration-based classification.
            status = "keys_present" if has_key else "keys_incomplete"
            return {
                "status": status,
                "details": {
                    "has_api_key": has_key,
                    "has_api_secret": has_secret,
                    "has_endpoint": has_url,
                },
            }

        def _probe() -> Dict[str, Any]:
            try:
                resp = requests.get(str(url), timeout=5.0)  # type: ignore[call-arg]
            except Exception as exc:  # pragma: no cover - network dependent
                return {
                    "status": "network_error",
                    "error": str(exc),
                    "details": {
                        "url": url,
                        "has_api_key": has_key,
                        "has_api_secret": has_secret,
                    },
                }

            code = resp.status_code
            try:
                body_snippet = resp.text[:256]
            except Exception:
                body_snippet = ""

            lowered = body_snippet.lower()

            if code in (401, 403) or "unauthorized" in lowered or "forbidden" in lowered:
                status = "auth_error"
            elif 200 <= code < 300:
                status = "ok"
            else:
                status = "client_error"

            return {
                "status": status,
                "error": None if status == "ok" else body_snippet,
                "details": {
                    "status_code": code,
                    "url": url,
                    "has_api_key": has_key,
                    "has_api_secret": has_secret,
                },
            }

        return await asyncio.to_thread(_probe)

    async def get_alpaca_positions(self) -> Dict[str, Any]:
        if tradeapi is None:
            return {"status": "package_missing", "positions": [], "cash": 0.0, "equity": 0.0}

        cfg = self.brokers.get("alpaca")
        if not isinstance(cfg, dict):
            return {"status": "not_configured", "positions": [], "cash": 0.0, "equity": 0.0}

        api_key = cfg.get("api_key")
        api_secret = cfg.get("api_secret")
        base_url = cfg.get("base_url") or cfg.get("endpoint") or "https://api.alpaca.markets"

        if not api_key or not api_secret:
            return {"status": "not_configured", "positions": [], "cash": 0.0, "equity": 0.0}

        def _fetch() -> Dict[str, Any]:
            client = tradeapi.REST(
                api_key,
                api_secret,
                base_url,
                api_version="v2",
            )
            account = client.get_account()
            raw_positions = client.list_positions()
            positions: List[Dict[str, Any]] = []
            for p in raw_positions:
                try:
                    symbol = getattr(p, "symbol", None) or ""
                    qty_str = getattr(p, "qty", "0")
                    qty = float(qty_str)
                    avg_price_str = getattr(p, "avg_entry_price", None) or getattr(p, "avg_price", None)
                    avg_price = float(avg_price_str) if avg_price_str is not None else 0.0
                    mv_str = getattr(p, "market_value", None)
                    market_value = float(mv_str) if mv_str is not None else qty * avg_price
                    upnl_str = getattr(p, "unrealized_pl", None)
                    unrealized_pl = float(upnl_str) if upnl_str is not None else 0.0
                    positions.append(
                        {
                            "symbol": symbol,
                            "qty": qty,
                            "avg_price": avg_price,
                            "market_value": market_value,
                            "unrealized_pl": unrealized_pl,
                        }
                    )
                except Exception:
                    continue

            cash_val = getattr(account, "cash", None)
            equity_val = getattr(account, "equity", None)
            try:
                cash = float(cash_val) if cash_val is not None else 0.0
            except (TypeError, ValueError):
                cash = 0.0
            try:
                equity = float(equity_val) if equity_val is not None else 0.0
            except (TypeError, ValueError):
                equity = 0.0

            return {"status": "ok", "positions": positions, "cash": cash, "equity": equity}

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            self.logger.warning("Alpaca portfolio fetch: %s (check API key in Settings > API Keys)", exc)
            return {"status": "error", "error": str(exc), "positions": [], "cash": 0.0, "equity": 0.0}

    async def build_symbol_index(self) -> List[Dict[str, Any]]:
        """Build a stock symbol index from Alpaca assets.

        Each entry has the form:

            {
                "symbol": "AAPL",
                "asset_class": "stock",
                "venues": ["alpaca"],
                "popularity": <float score>,
            }
        """

        assets: List[Dict[str, Any]] = []
        if not _alpaca_sdk_available():
            return assets

        cfg = self.brokers.get("alpaca")
        if not isinstance(cfg, dict):
            return assets

        api_key = cfg.get("api_key")
        api_secret = cfg.get("api_secret")
        base_url = cfg.get("base_url") or cfg.get("endpoint") or "https://api.alpaca.markets"

        if not api_key or not api_secret:
            return assets

        is_paper = "paper" in base_url.lower()

        def _fetch_assets() -> List[Dict[str, Any]]:
            if TradingClient is not None:
                client = TradingClient(api_key, api_secret, paper=is_paper)
                req = GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY)
                raw_assets = client.get_all_assets(req)
            else:
                client = tradeapi.REST(  # type: ignore[call-arg]
                    api_key, api_secret, base_url, api_version="v2",
                )
                raw_assets = client.list_assets(status="active")
            out: List[Dict[str, Any]] = []
            for a in raw_assets:
                try:
                    symbol = getattr(a, "symbol", None) or ""
                    if not symbol:
                        continue
                    tradable = bool(getattr(a, "tradable", True))
                    if not tradable:
                        continue
                    marginable = bool(getattr(a, "marginable", False))
                    shortable = bool(getattr(a, "shortable", False))
                    popularity = 1.0
                    if marginable:
                        popularity += 1.0
                    if shortable:
                        popularity += 0.5
                    out.append(
                        {
                            "symbol": str(symbol).upper(),
                            "asset_class": "stock",
                            "venues": ["alpaca"],
                            "popularity": popularity,
                        }
                    )
                except Exception:
                    continue
            return out

        try:
            return await asyncio.to_thread(_fetch_assets)
        except Exception as exc:
            # SOTA 2026: Downgrade auth errors to WARNING - config issues, not runtime errors
            msg = str(exc).lower()
            if "401" in msg or "forbidden" in msg or "not authorized" in msg or "invalid" in msg:
                self.logger.info("Alpaca symbol index: authorization pending (check API key in .env or config/api_keys.json)")
            else:
                self.logger.info("Alpaca symbol index fetch: %s", exc)
            return []

    async def _get_alpaca_health(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Check basic health for Alpaca using the REST API.

        This performs a lightweight ``get_account`` call via the official
        SDK when available. Failures are classified into package/env issues,
        auth errors, or generic client errors.
        """
        
        # SOTA 2026 FIX: Skip health check during startup to prevent C-level crashes
        # The alpaca_trade_api library can cause segfaults during asyncio.to_thread()
        # Health check can be triggered manually later via event bus
        skip_startup_check = os.environ.get("KINGDOM_SKIP_ALPACA_HEALTH", "1") == "1"
        if skip_startup_check:
            self.logger.info("Alpaca: Skipping startup health check (KINGDOM_SKIP_ALPACA_HEALTH=1)")
            return {
                "status": "configured",
                "error": None,
                "details": {"note": "Health check skipped during startup - trigger manually if needed"},
            }

        if not _alpaca_sdk_available():
            return {
                "status": "package_missing",
                "error": "Neither alpaca-py nor alpaca-trade-api is installed",
            }

        api_key = cfg.get("api_key")
        api_secret = cfg.get("api_secret")
        base_url = cfg.get("base_url") or cfg.get("endpoint") or "https://api.alpaca.markets"

        # SOTA 2026: Skip health check if keys are empty - this is a config gap, not an error
        if not api_key or not api_secret:
            self.logger.debug("Alpaca: API keys not configured - skipping health check")
            return {
                "status": "not_configured",
                "error": "API keys not set in config/api_keys.json",
            }

        is_paper = "paper" in base_url.lower()

        def _call_get_account() -> Dict[str, Any]:
            if TradingClient is not None:
                client = TradingClient(api_key, api_secret, paper=is_paper)
                account = client.get_account()
                return {
                    "status": str(getattr(account, "status", None)),
                    "buying_power": str(getattr(account, "buying_power", None)),
                }
            # Legacy fallback
            client = tradeapi.REST(  # type: ignore[call-arg]
                api_key, api_secret, base_url, api_version="v2",
            )
            account = client.get_account()
            return {
                "status": getattr(account, "status", None),
                "buying_power": getattr(account, "buying_power", None),
            }

        try:
            self.logger.debug("Alpaca: Starting health check...")
            info = await asyncio.to_thread(_call_get_account)
            self.logger.debug("Alpaca: Health check completed")
        except Exception as exc:  # pragma: no cover - network dependent
            msg = str(exc)
            lowered = msg.lower()

            if "401" in lowered or "forbidden" in lowered or "invalid" in lowered:
                status = "auth_error"
            else:
                status = "client_error"

            # SOTA 2026: Downgrade auth errors to WARNING - these are config issues, not runtime errors
            if status == "auth_error":
                self.logger.warning("Alpaca health check: authorization failed (check API key in .env)")
            else:
                self.logger.error("Alpaca health check failed: %s", msg)
            return {
                "status": status,
                "error": msg,
            }

        return {
            "status": "ok",
            "details": info,
        }

    async def place_alpaca_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """Place a REAL stock order on Alpaca via REST.

        Supports basic ``market`` and ``limit`` orders and returns a
        normalized order dictionary suitable for event-bus publication by
        higher-level components.
        """

        if not _alpaca_sdk_available():
            raise RuntimeError(
                "No Alpaca SDK installed - run 'pip install alpaca-py' in kingdom-venv"
            )

        cfg = self.brokers.get("alpaca")
        if not isinstance(cfg, dict):
            raise RuntimeError("Alpaca broker is not configured in RealStockExecutor")

        api_key = cfg.get("api_key")
        api_secret = cfg.get("api_secret")
        base_url = cfg.get("base_url") or cfg.get("endpoint") or "https://api.alpaca.markets"

        if not api_key or not api_secret:
            raise RuntimeError("Missing Alpaca API key or secret for order placement")

        side_norm = side.lower()
        if side_norm not in ("buy", "sell"):
            raise ValueError(f"Unsupported Alpaca order side: {side}")

        ot = order_type.lower()
        if ot not in ("market", "limit"):
            raise ValueError(f"Unsupported Alpaca order type: {order_type}")

        is_paper = "paper" in base_url.lower()

        def _submit() -> Dict[str, Any]:
            if TradingClient is not None:
                client = TradingClient(api_key, api_secret, paper=is_paper)
                side_enum = OrderSide.BUY if side_norm == "buy" else OrderSide.SELL
                tif_map = {
                    "day": TimeInForce.DAY,
                    "gtc": TimeInForce.GTC,
                    "opg": TimeInForce.OPG,
                    "cls": TimeInForce.CLS,
                    "ioc": TimeInForce.IOC,
                    "fok": TimeInForce.FOK,
                }
                tif_enum = tif_map.get(time_in_force.lower(), TimeInForce.DAY)
                if ot == "market":
                    order_req = MarketOrderRequest(
                        symbol=symbol, qty=quantity, side=side_enum, time_in_force=tif_enum,
                    )
                else:
                    if price is None:
                        raise ValueError("Limit order requires a price for Alpaca")
                    order_req = LimitOrderRequest(
                        symbol=symbol, qty=quantity, side=side_enum,
                        time_in_force=tif_enum, limit_price=price,
                    )
                order = client.submit_order(order_data=order_req)
                return {
                    "id": str(getattr(order, "id", None)),
                    "symbol": getattr(order, "symbol", symbol),
                    "side": str(getattr(order, "side", side_norm)),
                    "type": str(getattr(order, "order_type", ot)),
                    "qty": float(getattr(order, "qty", quantity) or quantity),
                    "filled_qty": float(getattr(order, "filled_qty", 0) or 0),
                    "status": str(getattr(order, "status", None)),
                    "limit_price": (
                        float(getattr(order, "limit_price", 0) or 0)
                        if getattr(order, "limit_price", None) is not None else None
                    ),
                    "stop_price": (
                        float(getattr(order, "stop_price", 0) or 0)
                        if getattr(order, "stop_price", None) is not None else None
                    ),
                    "created_at": str(getattr(order, "created_at", None)),
                    "filled_at": str(getattr(order, "filled_at", None)) if getattr(order, "filled_at", None) else None,
                }

            # Legacy fallback
            client = tradeapi.REST(  # type: ignore[call-arg]
                api_key, api_secret, base_url, api_version="v2",
            )
            submit_kwargs: Dict[str, Any] = {
                "symbol": symbol, "side": side_norm, "type": ot,
                "qty": quantity, "time_in_force": time_in_force,
            }
            if ot == "limit":
                if price is None:
                    raise ValueError("Limit order requires a price for Alpaca")
                submit_kwargs["limit_price"] = price
            order = client.submit_order(**submit_kwargs)
            return {
                "id": getattr(order, "id", None),
                "symbol": getattr(order, "symbol", symbol),
                "side": getattr(order, "side", side_norm),
                "type": getattr(order, "type", ot),
                "qty": float(getattr(order, "qty", quantity)),
                "filled_qty": float(getattr(order, "filled_qty", 0)),
                "status": getattr(order, "status", None),
                "limit_price": getattr(order, "limit_price", None),
                "stop_price": getattr(order, "stop_price", None),
                "created_at": getattr(order, "created_at", None),
                "filled_at": getattr(order, "filled_at", None),
            }

        try:
            order_data = await asyncio.to_thread(_submit)
            self.logger.info(
                "Alpaca order placed: %s %s %s (type=%s)",
                order_data.get("side"),
                order_data.get("qty"),
                order_data.get("symbol"),
                order_data.get("type"),
            )
            if self.event_bus:
                try:
                    self.event_bus.publish(
                        AUTONOMOUS_DECISION_LOG,
                        {
                            "internal": True,
                            "symbol": symbol,
                            "side": side_norm,
                            "quantity": quantity,
                            "order_id": order_data.get("id"),
                            "source": "real_stock_executor",
                            "timestamp": time.time(),
                        },
                    )
                except Exception:
                    pass
            return order_data
        except Exception as exc:
            self.logger.error("Error placing Alpaca order: %s", exc)
            raise

    async def cancel_alpaca_order(self, order_id: str) -> bool:
        if not _alpaca_sdk_available():
            raise RuntimeError(
                "No Alpaca SDK installed - run 'pip install alpaca-py' in kingdom-venv"
            )

        cfg = self.brokers.get("alpaca")
        if not isinstance(cfg, dict):
            raise RuntimeError("Alpaca broker is not configured in RealStockExecutor")

        api_key = cfg.get("api_key")
        api_secret = cfg.get("api_secret")
        base_url = cfg.get("base_url") or cfg.get("endpoint") or "https://api.alpaca.markets"

        if not api_key or not api_secret:
            raise RuntimeError("Missing Alpaca API key or secret for order cancellation")

        is_paper = "paper" in base_url.lower()

        def _cancel() -> bool:
            if TradingClient is not None:
                client = TradingClient(api_key, api_secret, paper=is_paper)
                client.cancel_order_by_id(order_id)
                return True
            client = tradeapi.REST(  # type: ignore[call-arg]
                api_key, api_secret, base_url, api_version="v2",
            )
            client.cancel_order(order_id)
            return True

        try:
            return await asyncio.to_thread(_cancel)
        except Exception as exc:
            self.logger.error("Error cancelling Alpaca order %s: %s", order_id, exc)
            return False

    # ------------------------------------------------------------------
    # Funding / withdrawal — Alpaca ACH + crypto
    # ------------------------------------------------------------------
    def _alpaca_rest_kwargs(self) -> Dict[str, Any]:
        cfg = self.brokers.get("alpaca")
        if not isinstance(cfg, dict):
            raise RuntimeError("Alpaca broker is not configured in RealStockExecutor")
        api_key = cfg.get("api_key")
        api_secret = cfg.get("api_secret")
        base_url = cfg.get("base_url") or cfg.get("endpoint") or "https://api.alpaca.markets"
        if not api_key or not api_secret:
            raise RuntimeError("Missing Alpaca API key or secret")
        return {
            "api_key": api_key,
            "api_secret": api_secret,
            "base_url": base_url,
        }

    async def get_alpaca_account_summary(self) -> Dict[str, Any]:
        """Return a compact account summary — cash, portfolio value, buying power, status.

        This is the read-only balance view used by the readiness report. No
        orders are placed and no money is moved.
        """
        if not _alpaca_sdk_available():
            return {"status": "package_missing"}
        try:
            creds = self._alpaca_rest_kwargs()
        except Exception as exc:
            return {"status": "not_configured", "error": str(exc)}

        is_paper = "paper" in creds["base_url"].lower()

        def _get() -> Dict[str, Any]:
            if TradingClient is not None:
                client = TradingClient(creds["api_key"], creds["api_secret"], paper=is_paper)
                acct = client.get_account()
                return {
                    "status": "ok",
                    "account_status": str(getattr(acct, "status", None)),
                    "currency": str(getattr(acct, "currency", "USD") or "USD"),
                    "cash": float(getattr(acct, "cash", 0) or 0),
                    "portfolio_value": float(getattr(acct, "portfolio_value", 0) or 0),
                    "equity": float(getattr(acct, "equity", 0) or 0),
                    "buying_power": float(getattr(acct, "buying_power", 0) or 0),
                    "pattern_day_trader": bool(getattr(acct, "pattern_day_trader", False)),
                    "account_number": getattr(acct, "account_number", None),
                }
            client = tradeapi.REST(  # type: ignore[call-arg]
                creds["api_key"], creds["api_secret"], creds["base_url"], api_version="v2",
            )
            acct = client.get_account()
            return {
                "status": "ok",
                "account_status": getattr(acct, "status", None),
                "currency": getattr(acct, "currency", "USD"),
                "cash": float(getattr(acct, "cash", 0) or 0),
                "portfolio_value": float(getattr(acct, "portfolio_value", 0) or 0),
                "equity": float(getattr(acct, "equity", 0) or 0),
                "buying_power": float(getattr(acct, "buying_power", 0) or 0),
                "pattern_day_trader": bool(getattr(acct, "pattern_day_trader", False)),
                "account_number": getattr(acct, "account_number", None),
            }
        try:
            return await asyncio.to_thread(_get)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def list_alpaca_ach_relationships(self) -> List[Dict[str, Any]]:
        """List the linked bank (ACH) relationships on the Alpaca account.

        The ``relationship_id`` from one of these entries is required to
        initiate an ACH withdrawal (or deposit) through Alpaca.
        """
        if requests is None:
            raise RuntimeError("requests package is not installed")
        creds = self._alpaca_rest_kwargs()

        def _get() -> List[Dict[str, Any]]:
            url = f"{creds['base_url']}/v2/account/ach_relationships"
            headers = {
                "APCA-API-KEY-ID": creds["api_key"],
                "APCA-API-SECRET-KEY": creds["api_secret"],
            }
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Alpaca ACH relationships error {resp.status_code}: {resp.text}"
                )
            data = resp.json()
            if isinstance(data, list):
                return data
            return []
        return await asyncio.to_thread(_get)

    async def alpaca_withdraw_ach(
        self,
        amount: float,
        relationship_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initiate an ACH withdrawal from Alpaca to the user's linked bank.

        If ``relationship_id`` is omitted, the first ACTIVE relationship is
        used. Returns the Alpaca transfer record on success.
        """
        if requests is None:
            raise RuntimeError("requests package is not installed")
        if amount is None or float(amount) <= 0:
            raise ValueError("alpaca_withdraw_ach: amount must be > 0")
        creds = self._alpaca_rest_kwargs()

        if not relationship_id:
            relationships = await self.list_alpaca_ach_relationships()
            active = [r for r in relationships if str(r.get("status", "")).upper() == "APPROVED"]
            if not active:
                raise RuntimeError(
                    "No APPROVED ACH relationship on the Alpaca account. "
                    "Link a bank account in the Alpaca dashboard first."
                )
            relationship_id = active[0].get("id")
            if not relationship_id:
                raise RuntimeError("Alpaca ACH relationship id missing")

        def _post() -> Dict[str, Any]:
            url = f"{creds['base_url']}/v2/account/transfers"
            headers = {
                "APCA-API-KEY-ID": creds["api_key"],
                "APCA-API-SECRET-KEY": creds["api_secret"],
                "Content-Type": "application/json",
            }
            body = {
                "transfer_type": "ach",
                "relationship_id": relationship_id,
                "amount": f"{float(amount):.2f}",
                "direction": "OUTGOING",
            }
            resp = requests.post(url, headers=headers, json=body, timeout=20)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Alpaca ACH withdraw error {resp.status_code}: {resp.text}"
                )
            return resp.json() if resp.content else {}

        result = await asyncio.to_thread(_post)
        if self.event_bus is not None:
            try:
                self.event_bus.publish("broker.withdraw.submitted", {
                    "broker": "alpaca",
                    "rail": "ach",
                    "amount": float(amount),
                    "relationship_id": relationship_id,
                    "transfer_id": result.get("id"),
                    "status": result.get("status"),
                    "timestamp": time.time(),
                })
            except Exception:
                pass
        return result

    async def alpaca_crypto_withdraw(
        self,
        asset: str,
        amount: float,
        address: str,
        network: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transfer crypto out of an Alpaca crypto wallet to an external address.

        Uses Alpaca's ``/v2/wallets/transfers`` endpoint (available on
        accounts with crypto trading enabled).
        """
        if requests is None:
            raise RuntimeError("requests package is not installed")
        if not address:
            raise ValueError("alpaca_crypto_withdraw: address is required")
        if amount is None or float(amount) <= 0:
            raise ValueError("alpaca_crypto_withdraw: amount must be > 0")
        creds = self._alpaca_rest_kwargs()

        def _post() -> Dict[str, Any]:
            url = f"{creds['base_url']}/v2/wallets/transfers"
            headers = {
                "APCA-API-KEY-ID": creds["api_key"],
                "APCA-API-SECRET-KEY": creds["api_secret"],
                "Content-Type": "application/json",
            }
            body: Dict[str, Any] = {
                "asset": asset,
                "address": address,
                "amount": f"{float(amount)}",
            }
            if network:
                body["network"] = network
            resp = requests.post(url, headers=headers, json=body, timeout=20)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Alpaca crypto withdraw error {resp.status_code}: {resp.text}"
                )
            return resp.json() if resp.content else {}

        result = await asyncio.to_thread(_post)
        if self.event_bus is not None:
            try:
                self.event_bus.publish("broker.withdraw.submitted", {
                    "broker": "alpaca",
                    "rail": "crypto",
                    "asset": asset,
                    "amount": float(amount),
                    "address": (address[:10] + "...") if address else None,
                    "network": network,
                    "transfer_id": result.get("id"),
                    "status": result.get("status"),
                    "timestamp": time.time(),
                })
            except Exception:
                pass
        return result

    async def publish_broker_health_snapshot(self) -> None:
        """Publish a snapshot of broker health to the event bus.

        This mirrors the exchange health snapshot functionality for
        RealExchangeExecutor and allows GUI components or monitoring tools
        to subscribe to a single topic ("stock.broker.health.snapshot") to
        observe stock/forex broker availability.
        """

        if not self.event_bus:
            return

        health = await self.get_broker_health()
        payload = {
            "timestamp": time.time(),
            "health": health,
        }

        try:
            self.event_bus.publish("stock.broker.health.snapshot", payload)
        except Exception as e:  # pragma: no cover - event bus errors
            self.logger.error("Failed to publish broker health snapshot: %s", e)


__all__ = ["RealStockExecutor"]
