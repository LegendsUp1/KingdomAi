#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical exchange/market universe for Kingdom AI.

This module provides a single source of truth for:
- How APIKeyManager.api_keys are translated into the flat api_keys mapping
  expected by RealExchangeExecutor (build_real_exchange_api_keys).
- The canonical test/benchmark markets per exchange (EXCHANGE_TEST_CONFIG).
- Helper functions for deriving canonical symbols for any enabled exchange
  and for building a minimal exchange->symbol map used by market data
  components.

It is imported by both the real_exchange_smoke_test and live components
(e.g. MarketDataStreaming) so that **the same exchanges and symbols** are
used consistently across smoke tests, executors, and UI streaming.
"""

from __future__ import annotations

from typing import Any, Dict
import logging

from core.api_key_manager import APIKeyManager

logger = logging.getLogger(__name__)


def _clean_config_str(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = value.split("#", 1)[0].strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ('"', "'"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def build_real_exchange_api_keys(raw_keys: Dict[str, Any]) -> Dict[str, Any]:
    """Translate APIKeyManager.api_keys into the flat/nested structure
    expected by RealExchangeExecutor.

    This logic was originally implemented in real_exchange_smoke_test.py and
    is now centralized here so both smoke tests and live components can share
    the exact same mapping rules.
    """

    api_keys: Dict[str, Any] = {}
    mapped_services = set()

    def map_ccxt_exchange(
        service_name: str,
        ex_name: str,
        needs_password: bool = False,
        password_keys=("password", "passphrase", "api_password"),
    ) -> None:
        data = raw_keys.get(service_name)
        if not isinstance(data, dict):
            return
        # Allow api_keys.json to disable specific exchanges explicitly.
        if data.get("enabled") is False:
            return
        api_key = data.get("api_key") or data.get("key") or data.get("apiKey")
        api_secret = data.get("api_secret") or data.get("secret") or data.get("apiSecret")
        if not api_key or not api_secret:
            return
        api_keys[ex_name] = api_key
        api_keys[f"{ex_name}_secret"] = api_secret
        mapped_services.add(service_name)
        if needs_password:
            pwd = None
            for k in password_keys:
                if k in data and data[k]:
                    pwd = data[k]
                    break
            if pwd:
                api_keys[f"{ex_name}_password"] = pwd

    # Spot exchanges via ccxt - explicit mappings for known exchanges
    map_ccxt_exchange("binance", "binance")
    map_ccxt_exchange("binanceus", "binanceus")
    map_ccxt_exchange("coinbase", "coinbase", needs_password=True)
    map_ccxt_exchange("kraken", "kraken")
    map_ccxt_exchange("bitstamp", "bitstamp")

    # HTX / Huobi - allow either key name, but RealExchangeExecutor expects 'htx'
    if "htx" in raw_keys:
        map_ccxt_exchange("htx", "htx")
    elif "huobi" in raw_keys:
        map_ccxt_exchange("huobi", "htx")

    map_ccxt_exchange("kucoin", "kucoin", needs_password=True)

    # Additional spot exchanges via ccxt (keys may live either at the
    # top level or under _CRYPTO_EXCHANGES in api_keys.json and .env).
    map_ccxt_exchange("bybit", "bybit")
    map_ccxt_exchange(
        "bitget",
        "bitget",
        needs_password=True,
        password_keys=("passphrase", "password", "api_password"),
    )
    map_ccxt_exchange("mexc", "mexc")
    # gate_io service maps to ccxt "gate" / "gateio" id; we standardize on
    # connector name "gateio" for the executor.
    map_ccxt_exchange("gate_io", "gateio")
    # crypto_com service maps to ccxt "cryptocom" id; connector key is
    # "cryptocom".
    map_ccxt_exchange("crypto_com", "cryptocom")
    map_ccxt_exchange("phemex", "phemex")
    map_ccxt_exchange("bittrex", "bittrex")
    map_ccxt_exchange("lbank", "lbank")
    map_ccxt_exchange("bitmart", "bitmart")
    map_ccxt_exchange("whitebit", "whitebit")
    map_ccxt_exchange("poloniex", "poloniex")
    map_ccxt_exchange("coinex", "coinex")
    map_ccxt_exchange("bitflyer", "bitflyer")

    # Newly-added tier-1 venues (2026-04). OKX requires a passphrase; the
    # others are standard key+secret. Dynamic discovery below would also pick
    # these up (now that they're in CATEGORIES), but explicit mappings make
    # the wiring obvious at code-review time and let us attach per-venue
    # quirks (e.g. OKX passphrase, huobi -> htx alias).
    map_ccxt_exchange(
        "okx", "okx",
        needs_password=True,
        password_keys=("passphrase", "password", "api_password"),
    )
    map_ccxt_exchange("gemini", "gemini")
    map_ccxt_exchange("bitfinex", "bitfinex")
    # huobi is the legacy name for htx; if only 'huobi' is populated (and
    # 'htx' is not), remap it to the htx executor slot.
    if "htx" not in mapped_services and "huobi" in raw_keys:
        map_ccxt_exchange("huobi", "htx")

    # Oanda - pass through full nested config so RealExchangeExecutor's
    # native OandaConnector can interpret api_key/account/environment.
    if "oanda" in raw_keys and isinstance(raw_keys["oanda"], dict):
        data = raw_keys["oanda"]
        if data.get("enabled") is not False:
            api_keys["oanda"] = {
                **data,
                "api_key": _clean_config_str(data.get("api_key") or data.get("key") or data.get("access_token")),
                "account_id": _clean_config_str(data.get("account_id") or data.get("account")),
                "environment": _clean_config_str(data.get("environment") or data.get("env")),
                "endpoint": _clean_config_str(data.get("endpoint")),
            }

    # BTCC - pass through nested config for native BtccConnector.
    if "btcc" in raw_keys and isinstance(raw_keys["btcc"], dict):
        data = raw_keys["btcc"]
        if data.get("enabled") is not False:
            api_keys["btcc"] = data

    # Polymarket - pass through nested config for native PolymarketConnector.
    if "polymarket" in raw_keys and isinstance(raw_keys["polymarket"], dict):
        data = raw_keys["polymarket"]
        if data.get("enabled") is not False:
            api_keys["polymarket"] = data

    # Kalshi - pass through nested config for native KalshiConnector.
    if "kalshi" in raw_keys and isinstance(raw_keys["kalshi"], dict):
        data = raw_keys["kalshi"]
        if data.get("enabled") is not False:
            api_keys["kalshi"] = data

    # DYNAMIC DISCOVERY: Test ALL crypto exchanges in CATEGORIES that have valid keys
    crypto_names = set(APIKeyManager.CATEGORIES.get("crypto_exchanges", []))
    for service, data in raw_keys.items():
        if service in mapped_services:
            continue
        if service not in crypto_names:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("enabled") is False:
            continue
        api_key = data.get("api_key") or data.get("key") or data.get("apiKey")
        api_secret = data.get("api_secret") or data.get("secret") or data.get("apiSecret")
        if not api_key or not api_secret:
            continue
        if service in api_keys or f"{service}_secret" in api_keys:
            continue
        # Use service name as-is for ccxt (e.g., 'gate_io' -> 'gate_io')
        api_keys[service] = api_key
        api_keys[f"{service}_secret"] = api_secret
        # Propagate passphrase / memo for venues that require them
        # (OKX, KuCoin, Bitget, dYdX, BitMart, Crypto.com, etc.). The generic
        # CCXT initializer in RealExchangeExecutor looks for both
        # f"{name}_password" and f"{name}_passphrase".
        pwd = (
            data.get("passphrase")
            or data.get("password")
            or data.get("api_password")
            or data.get("memo")
        )
        if pwd:
            api_keys[f"{service}_password"] = pwd
        logger.info("✅ Dynamically discovered crypto exchange: %s", service)

    return api_keys


# Canonical test/config markets per exchange, originally defined in
# real_exchange_smoke_test.py. These are now shared across smoke tests and
# live components.
EXCHANGE_TEST_CONFIG: Dict[str, Dict[str, Any]] = {
    "binance": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "coinbase": {"symbol": "BTC/USD", "amount": 0.001, "limit_price": 50000.0},
    "kraken": {"symbol": "BTC/USD", "amount": 0.001, "limit_price": 50000.0},
    "bitstamp": {"symbol": "BTC/USD", "amount": 0.001, "limit_price": 50000.0},
    "htx": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "kucoin": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    # Extended CCXT spot exchanges
    "bybit": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "bitget": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "mexc": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "gateio": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "cryptocom": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "phemex": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "bittrex": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "lbank": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "bitmart": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "whitebit": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "poloniex": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    "coinex": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    # Bitflyer is primarily JPY-based; use BTC/JPY at a high dummy price
    # far from market to minimize fill probability.
    "bitflyer": {"symbol": "BTC/JPY", "amount": 0.001, "limit_price": 1000000.0},
    # Native connectors
    "btcc": {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0},
    # For Oanda we use a very small order (100 units) and a limit price far
    # below current market (0.01) to minimize fill probability.
    "oanda": {"symbol": "EUR/USD", "amount": 100, "limit_price": 0.01},
    # Prediction market connectors (native)
    "polymarket": {"symbol": "PM/USDC", "amount": 10, "limit_price": 0.50},
    "kalshi": {"symbol": "PM/USD", "amount": 1, "limit_price": 50},
}


def get_canonical_symbol_config(name: str) -> Dict[str, Any]:
    """Return the canonical symbol/amount/limit_price config for an exchange.

    This mirrors the fallback logic in real_exchange_smoke_test.run_smoke_for_exchange
    so that any newly enabled exchange with keys still gets a reasonable
    default symbol without code changes.
    """

    cfg = EXCHANGE_TEST_CONFIG.get(name)
    if cfg is not None:
        return cfg

    # Fallbacks copied from run_smoke_for_exchange
    if name == "oanda":
        return {"symbol": "EUR/USD", "amount": 100, "limit_price": 0.01}
    if name in ("coinbase", "kraken", "bitstamp"):
        return {"symbol": "BTC/USD", "amount": 0.001, "limit_price": 50000.0}
    if name == "bitflyer":
        return {"symbol": "BTC/JPY", "amount": 0.001, "limit_price": 1000000.0}

    # Generic crypto default for spot venues
    return {"symbol": "BTC/USDT", "amount": 0.001, "limit_price": 50000.0}


def build_canonical_exchange_markets(raw_keys: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build a minimal mapping of exchange -> {"symbol": canonical_symbol}.

    This is used by live components (e.g. MarketDataStreaming) to decide which
    markets to stream for each enabled exchange, ensuring they align exactly
    with the smoke tests and RealExchangeExecutor.
    """

    markets: Dict[str, Dict[str, Any]] = {}
    api_keys = build_real_exchange_api_keys(raw_keys)

    # Enabled exchanges are those that have a primary key entry (not *_secret
    # or *_password).
    enabled = set()
    for k in api_keys.keys():
        if k.endswith("_secret") or k.endswith("_password"):
            continue
        enabled.add(k)

    for name in sorted(enabled):
        cfg = get_canonical_symbol_config(name)
        symbol = cfg.get("symbol")
        if not symbol:
            continue
        markets[name] = {"symbol": symbol}

    return markets


__all__ = [
    "build_real_exchange_api_keys",
    "EXCHANGE_TEST_CONFIG",
    "get_canonical_symbol_config",
    "build_canonical_exchange_markets",
]
