"""Canonical trading-venue funding & KYC knowledge matrix.

This module encodes **everything Kingdom AI needs to know at runtime** about
each of the 60+ trading venues it supports:

  * Category (crypto, equity, forex, prediction market)
  * KYC requirement (none / standard / strict / broker-level)
  * Funding rails available (crypto on-chain, fiat wire, ACH, card, SEPA, etc.)
  * Whether Kingdom AI can **autonomously move funds IN** via its internal
    crypto rails (i.e. send USDC/USDT from a Kingdom wallet to a deposit
    address controlled by that venue)
  * Whether Kingdom AI can **autonomously move funds OUT** via API
  * Whether user KYC+manual funding is required before any trading happens
  * The specific next step the user must take for any venue that is not yet
    live-trading ready

Published on EventBus topic ``trading.venues.funding_matrix`` after every
API-key reload so the GUI, Ollama brain, and dashboards always have a
current view.

Design notes
------------
The knowledge here is CURATED (not probed). Values reflect 2026-04 US retail
broker reality. If a venue changes its stance (e.g. Robinhood adding public
API, Alpaca launching fiat-to-crypto), this is the single file to edit.

Funding-rail codes used below::

  IN:   crypto_usdc, crypto_usdt, crypto_native, ach_push, ach_pull,
        wire_in, card, sepa, fpuk, faster_payments, internal_transfer,
        plaid_bridge, manual_portal, broker_deposit
  OUT:  crypto_withdraw, ach_withdraw, wire_out, internal_transfer,
        manual_portal, broker_withdraw

Values::

  kyc:          "none" | "light" | "standard" | "strict" | "broker"
  legal:        "us_ok" | "us_blocked" | "non_us_only" | "restricted" | "defunct"
  ai_fund_in:   bool  -- can Kingdom AI deposit funds to this venue via API?
  ai_fund_out:  bool  -- can Kingdom AI withdraw from this venue via API?
  primary_rail: human-readable string describing the preferred flow
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)


# Authoritative per-venue knowledge.
# "ai_fund_in" == True means Kingdom AI can autonomously route money INTO
# this venue from another connected venue (for example by withdrawing
# USDC/USDT from an exchange Kingdom AI controls and depositing to this one).
# "ai_fund_out" == True means Kingdom AI can call the venue's withdraw
# endpoint to pull money out.
VENUE_FUNDING: Dict[str, Dict[str, Any]] = {
    # =====================================================================
    # CRYPTO CEXs - All support on-chain USDC/USDT deposits + withdrawals,
    # which means Kingdom AI CAN move money in/out of them internally,
    # provided the user has completed the exchange's KYC.
    # =====================================================================
    "kraken":     {"category": "crypto", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto_usdc/usdt deposit + withdraw via ccxt"},
    "coinbase":   {"category": "crypto", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto_usdc deposit + withdraw via ccxt advanced trade"},
    "bitstamp":   {"category": "crypto", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto_usdc/usdt via ccxt"},
    "binance":    {"category": "crypto", "kyc": "standard", "legal": "us_blocked",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt (requires non-US IP)"},
    "binanceus":  {"category": "crypto", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto deposit + withdraw via ccxt (IP whitelist required)"},
    "htx":        {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt (US residents restricted)"},
    "btcc":       {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via BTCC WS API (needs private ws_url)"},
    "bybit":      {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "bybit_futures": {"category": "crypto_deriv", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "USDT margin via ccxt (bybit unified)"},
    "kucoin":     {"category": "crypto", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "kucoin_futures": {"category": "crypto_deriv", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "USDT margin via ccxt (kucoinfutures)"},
    "okx":        {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt (needs passphrase)"},
    "bitget":     {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt (needs passphrase)"},
    "mexc":       {"category": "crypto", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "gate_io":    {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "gemini":     {"category": "crypto", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto + ACH via ccxt + native fiat rails"},
    "bitfinex":   {"category": "crypto", "kyc": "standard", "legal": "restricted",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt (US requires ENTITY account)"},
    "bitflyer":   {"category": "crypto", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt (JPY pairs dominant)"},
    "crypto_com": {"category": "crypto", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "phemex":     {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "lbank":      {"category": "crypto", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "bitmart":    {"category": "crypto", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt (memo required for XRP/XLM)"},
    "ascendex":   {"category": "crypto", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "whitebit":   {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "poloniex":   {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "coinex":     {"category": "crypto", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "woo_x":      {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt (woo exchange)"},
    "probit":     {"category": "crypto", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt"},
    "hotbit":     {"category": "crypto", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "crypto via ccxt (CLOSED 2022 - verify if reopened)"},
    "bittrex":    {"category": "crypto", "kyc": "standard", "legal": "us_blocked",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "WOUND DOWN 2023 - remove or await relaunch"},
    "ftx_international": {"category": "crypto", "kyc": "n/a", "legal": "defunct",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "DEFUNCT (2022 collapse)"},
    "dydx":       {"category": "crypto_deriv", "kyc": "none", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "USDC on Ethereum L1 -> dYdX L2 (non-US)"},
    "binance_futures": {"category": "crypto_deriv", "kyc": "standard", "legal": "us_blocked",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "USDT margin via ccxt binance {'defaultType':'future'}"},
    "huobi":      {"category": "crypto", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "ALIAS for htx"},

    # =====================================================================
    # PREDICTION MARKETS - On-chain USDC rails (Polymarket) + regulated
    # DCM ACH-only (Kalshi).
    # =====================================================================
    "polymarket": {"category": "prediction", "kyc": "light", "legal": "non_us_only",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "USDC on Polygon -> CLOB deposit (non-US per CFTC 2022 settlement)"},
    "kalshi":     {"category": "prediction", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "ACH from verified bank (no crypto rail; user funds manually)"},

    # =====================================================================
    # FOREX - OANDA is primary. No crypto rails; ACH/wire only. Kingdom AI
    # can READ balances and EXECUTE trades but CANNOT deposit/withdraw
    # via API (ACH push/pull not exposed in OANDA REST).
    # =====================================================================
    "oanda":      {"category": "forex", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via oanda.com ACH/wire"},
    "forex_com":  {"category": "forex", "kyc": "standard", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via forex.com portal"},
    "fxcm":       {"category": "forex", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal (US residents restricted)"},
    "ig_markets": {"category": "forex", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal (UK/EU primary)"},
    "dukascopy":  {"category": "forex", "kyc": "strict", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - Swiss bank KYC"},
    "pepperstone":{"category": "forex", "kyc": "standard", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal"},
    "fxstreet":   {"category": "data", "kyc": "none", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "data-only (no trading)"},
    "fcsapi":     {"category": "data", "kyc": "none", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "data-only (no trading)"},
    "mt4_bridge": {"category": "forex", "kyc": "broker", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "funding depends on underlying broker"},
    "mt5_bridge": {"category": "forex", "kyc": "broker", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "funding depends on underlying broker"},
    "ctrader":    {"category": "forex", "kyc": "broker", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "funding depends on underlying broker"},
    "xm":         {"category": "forex", "kyc": "broker", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal (via MT4/5 broker)"},
    "icmarkets":  {"category": "forex", "kyc": "broker", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal (via MT4/5 broker)"},
    "tickmill":   {"category": "forex", "kyc": "broker", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal (via MT4/5 broker)"},
    "axi":        {"category": "forex", "kyc": "broker", "legal": "non_us_only",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal (via MT4/5 broker)"},

    # =====================================================================
    # US EQUITY / MULTI-ASSET BROKERS - regulated; most forbid API-driven
    # deposits. Alpaca is the EXCEPTION: it has crypto deposits + ACH
    # withdrawal APIs, so Kingdom AI can auto-fund Alpaca crypto from
    # Kingdom wallets, but stock equity funding still requires ACH push
    # from the user's verified bank (Plaid bridge can automate if enabled).
    # =====================================================================
    "alpaca":     {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": True, "ai_fund_out": True,
                   "primary_rail": "ACH via Plaid bridge (user) + Alpaca crypto deposit (AI)"},
    "tradestation": {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via tradestation.com ACH/wire"},
    "schwab":     {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via schwab.com ACH/wire"},
    "tradier":    {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via tradier.com ACH"},
    "tastytrade": {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via tastytrade.com ACH"},
    "interactive_brokers": {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": True,
                   "primary_rail": "manual_portal in; IBKR API can request withdraw OUT"},
    "moomoo":     {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via moomoo app"},
    "webull":     {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via webull app"},
    "robinhood":  {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - no public trading API"},
    "etrade":     {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via etrade.com"},
    "td_ameritrade": {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "DEPRECATED 2024 - migrated to Schwab"},
    "fidelity":   {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - no public retail API"},
    "ninjatrader":{"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal + local NT8 gateway"},
    "saxo":       {"category": "equity_broker", "kyc": "strict", "legal": "us_blocked",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via home.saxo (non-US)"},
    "lightspeed": {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - Lightspeed Trader (institutional)"},
    "firstrade":  {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - fund via firstrade.com"},
    "public_api": {"category": "equity_broker", "kyc": "strict", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "manual_portal - Public.com no public API"},
    "tradingview":{"category": "charting", "kyc": "none", "legal": "us_ok",
                   "ai_fund_in": False, "ai_fund_out": False,
                   "primary_rail": "charting/signals only (no direct trading)"},
}


def _current_public_ip() -> Optional[str]:
    """Best-effort probe of this machine's public IPv4 address.

    Used to include the exact IP in the IP-whitelist remediation hint
    for venues like binanceus. Short 2s timeout; returns None on failure.
    """
    try:
        import urllib.request
        for url in (
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com",
        ):
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    ip = (resp.read() or b"").decode("utf-8").strip()
                    if ip and ip.count(".") == 3:
                        return ip
            except Exception:
                continue
    except Exception:
        pass
    return None


HEALTH_SUGGESTION: Dict[str, str] = {
    "restricted_location":       "Use a non-US IP/VPN, or switch to the US variant if one exists (e.g. binanceus).",
    "time_skew":                 "System clock is drifting. Will auto-sync on next retry; if persistent run `sudo ntpdate pool.ntp.org`.",
    "key_invalid":               "Regenerate the API key/secret on the venue's portal and paste into config/api_keys.json.",
    "ip_not_allowed":            "Add this server's public IP to the API key's whitelist on the venue portal.",
    "account_not_authorized":    "Complete KYC / identity verification on the venue, and enable live trading for this key.",
    "permission_denied":         "Enable the missing scopes (read/trade/withdraw) for this API key on the portal.",
    "endpoint_unreachable":      "Endpoint down or changed. For BTCC, paste the private ws_url from your BTCC portal into config/api_keys.json.",
    "signature_invalid":         "Regenerate key+secret AND resync system clock.",
    "credentials_present_but_not_wired": "Credentials loaded but connector did not initialize; check logs for per-venue init error.",
    "alpaca_sdk_missing_or_key_invalid": "alpaca-py is installed; regenerate Alpaca key on alpaca.markets, or complete live-trading approval.",
    "alpaca_key_invalid":         "Alpaca rejected the API key. Regenerate on alpaca.markets (paper vs live must match the endpoint) and paste into config/api_keys.json.",
    "alpaca_sdk_missing":         "Install the SDK: `pip install alpaca-py` inside kingdom-venv.",
    "alpaca_client_error":        "Alpaca client error; check network/endpoint and that ALPACA_ENV=paper|live matches the key.",
    "scaffold_ready_paste_api_key_to_activate": "Generate an API key on the venue's portal, then paste into config/api_keys.json under _CRYPTO_EXCHANGES/_STOCK_EXCHANGES/_FOREX_TRADING.",
}


def _funding_info(venue: str) -> Dict[str, Any]:
    """Return VENUE_FUNDING[venue] or a sensible default."""
    return VENUE_FUNDING.get(
        venue,
        VENUE_FUNDING.get(
            venue.lower(),
            {
                "category": "unknown",
                "kyc": "unknown",
                "legal": "unknown",
                "ai_fund_in": False,
                "ai_fund_out": False,
                "primary_rail": "not classified - add entry to VENUE_FUNDING",
            },
        ),
    )


def build_venue_action_plan(status_report: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge the live status report with the curated funding knowledge.

    Produces, for every venue in the status report, a single action entry
    explaining:
      * Current runtime state (LIVE / DEGRADED / NEEDS_CREDENTIALS / NOT_CONFIGURED)
      * The specific reason it is not fully operational
      * The next action the user (or Kingdom AI) should take
      * Whether Kingdom AI can auto-move money in/out once it IS operational
      * KYC + funding legality notes

    Parameters
    ----------
    status_report
        Output of ``core.trading_venue_status.compute_trading_venue_status``.

    Returns
    -------
    dict
        {
            "timestamp": ...,
            "buckets": {
                "trade_now": [...],
                "ai_autofundable_crypto": [...],
                "user_fund_then_trade": [...],
                "needs_reconfig": [...],
                "needs_kyc": [...],
                "dormant": [...],
                "regulatory_blocked": [...],
            },
            "per_venue": {name: {...}}
        }
    """
    per_venue_status = status_report.get("per_venue", {})

    out: Dict[str, Dict[str, Any]] = {}
    buckets: Dict[str, List[str]] = {
        "trade_now":               [],  # LIVE and key valid
        "ai_autofundable_crypto":  [],  # Can receive crypto from Kingdom AI
        "user_fund_then_trade":    [],  # LIVE/DEGRADED - needs user deposit
        "needs_reconfig":          [],  # key/IP/endpoint issue (no KYC change)
        "needs_kyc":               [],  # account_not_authorized or KYC incomplete
        "dormant":                 [],  # scaffold exists; no creds
        "regulatory_blocked":      [],  # legally restricted in user's jurisdiction
    }

    for venue, s in per_venue_status.items():
        info = _funding_info(venue)
        health = str(s.get("health", "") or "")
        status = s.get("status", "UNKNOWN")
        credentials = s.get("credentials", "unset")

        entry: Dict[str, Any] = {
            "venue": venue,
            "status": status,
            "health": health,
            "credentials": credentials,
            "category": info["category"],
            "kyc": info["kyc"],
            "legal": info["legal"],
            "ai_fund_in": info["ai_fund_in"],
            "ai_fund_out": info["ai_fund_out"],
            "primary_rail": info["primary_rail"],
        }

        # --- Action classification -------------------------------------
        if status == "LIVE":
            entry["action"] = "READY - execute orders now"
            buckets["trade_now"].append(venue)
            if info["ai_fund_in"]:
                buckets["ai_autofundable_crypto"].append(venue)
            elif info["category"] in ("forex", "equity_broker", "prediction"):
                buckets["user_fund_then_trade"].append(venue)
        elif status == "DEGRADED":
            entry["action"] = HEALTH_SUGGESTION.get(
                health, "Inspect the error; re-verify credentials and endpoint."
            )
            if health == "ip_not_allowed":
                ip = _current_public_ip()
                if ip:
                    entry["action"] = (
                        f"Add this server's public IP `{ip}` to the API key's "
                        "whitelist on the venue portal."
                    )
                    entry["public_ip"] = ip
            if health == "account_not_authorized":
                buckets["needs_kyc"].append(venue)
            elif health in ("key_invalid", "ip_not_allowed",
                             "signature_invalid", "endpoint_unreachable",
                             "credentials_present_but_not_wired",
                             "alpaca_sdk_missing_or_key_invalid"):
                buckets["needs_reconfig"].append(venue)
            elif health == "restricted_location":
                buckets["regulatory_blocked"].append(venue)
            else:
                buckets["needs_reconfig"].append(venue)
        elif status == "NEEDS_CREDENTIALS":
            entry["action"] = (
                "Paste API credentials into config/api_keys.json "
                "(or config/api_keys.env) - scaffold is already in place; "
                "Kingdom AI will auto-detect on next 3s poll."
            )
            buckets["dormant"].append(venue)
        elif status == "NOT_CONFIGURED":
            entry["action"] = "Not yet scaffolded. Add to _CRYPTO_EXCHANGES/_STOCK_EXCHANGES/_FOREX_TRADING in config/api_keys.json."
            buckets["dormant"].append(venue)
        else:
            entry["action"] = "Unknown state; check logs."
            buckets["dormant"].append(venue)

        # Flag legally-restricted regardless of credential state
        if info["legal"] in ("us_blocked", "defunct", "restricted"):
            if venue not in buckets["regulatory_blocked"]:
                buckets["regulatory_blocked"].append(venue)

        out[venue] = entry

    # Also include any venues that appear in VENUE_FUNDING but NOT in
    # per_venue_status (edge case where status report doesn't see them)
    missing = set(VENUE_FUNDING) - set(out)
    for venue in sorted(missing):
        info = _funding_info(venue)
        out[venue] = {
            "venue": venue,
            "status": "UNKNOWN",
            "health": "not_in_status_report",
            "credentials": "unset",
            "category": info["category"],
            "kyc": info["kyc"],
            "legal": info["legal"],
            "ai_fund_in": info["ai_fund_in"],
            "ai_fund_out": info["ai_fund_out"],
            "primary_rail": info["primary_rail"],
            "action": "Check VENUE_FUNDING vs CATEGORIES alignment.",
        }

    return {
        "timestamp": time.time(),
        "buckets": {k: sorted(set(v)) for k, v in buckets.items()},
        "per_venue": out,
    }


def publish_funding_matrix(
    plan: Mapping[str, Any],
    event_bus,
    *,
    topic: str = "trading.venues.funding_matrix",
) -> None:
    """Broadcast the action plan on the EventBus."""
    if event_bus is None:
        return
    try:
        event_bus.publish(topic, dict(plan))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to publish %s: %s", topic, exc)


def format_human_readable(plan: Mapping[str, Any]) -> str:
    """Render the action plan as a compact, readable report."""
    lines: List[str] = []
    b = plan.get("buckets", {})
    lines.append("=" * 78)
    lines.append("KINGDOM AI - TRADING FUNDING & ACTION MATRIX")
    lines.append("=" * 78)
    lines.append(f"[1] TRADE NOW (live + authenticated):        {len(b.get('trade_now', []))}")
    for v in b.get("trade_now", []):
        entry = plan['per_venue'].get(v, {})
        lines.append(f"      - {v:<16} [{entry.get('category','?')}] rail: {entry.get('primary_rail','')}")

    lines.append(f"\n[2] AI CAN AUTO-FUND (crypto rail IN):       {len(b.get('ai_autofundable_crypto', []))}")
    for v in b.get("ai_autofundable_crypto", []):
        lines.append(f"      - {v}")

    lines.append(f"\n[3] USER FUND FIRST, AI TRADES AFTER:        {len(b.get('user_fund_then_trade', []))}")
    for v in b.get("user_fund_then_trade", []):
        entry = plan['per_venue'].get(v, {})
        lines.append(f"      - {v:<16} {entry.get('primary_rail','')}")

    lines.append(f"\n[4] NEEDS RECONFIG (key/IP/endpoint fix):    {len(b.get('needs_reconfig', []))}")
    for v in b.get("needs_reconfig", []):
        entry = plan['per_venue'].get(v, {})
        lines.append(f"      - {v:<16} health={entry.get('health','?')}")
        lines.append(f"        -> {entry.get('action','')}")

    lines.append(f"\n[5] NEEDS KYC / ACCOUNT VERIFICATION:        {len(b.get('needs_kyc', []))}")
    for v in b.get("needs_kyc", []):
        entry = plan['per_venue'].get(v, {})
        lines.append(f"      - {v:<16} {entry.get('action','')}")

    lines.append(f"\n[6] REGULATORY / GEO BLOCKED:                {len(b.get('regulatory_blocked', []))}")
    for v in b.get("regulatory_blocked", []):
        entry = plan['per_venue'].get(v, {})
        lines.append(f"      - {v:<16} [{entry.get('legal','?')}]")

    lines.append(f"\n[7] DORMANT (scaffold only, paste keys):     {len(b.get('dormant', []))}")
    dormant = b.get("dormant", [])
    if dormant:
        # chunked 5/line for readability
        for i in range(0, len(dormant), 5):
            lines.append("      " + ", ".join(dormant[i:i+5]))

    lines.append("=" * 78)
    return "\n".join(lines)


__all__ = [
    "VENUE_FUNDING",
    "HEALTH_SUGGESTION",
    "build_venue_action_plan",
    "publish_funding_matrix",
    "format_human_readable",
]
