"""
core/prediction_market_connector.py

Native connectors for Polymarket (py-clob-client v0.34.6) and Kalshi
(kalshi-python-sync v3.2.0) implementing the ExchangeConnector protocol.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class _AddressOnlySigner:
    """Lightweight signer shim for L2 read operations (balance, allowances).

    py-clob-client L2 HMAC headers only need signer.address() — the actual
    request signature is HMAC-SHA256 from the API secret, NOT the private key.
    This lets us query balances/allowances when we have API creds + wallet
    address but no private key.  Order *signing* still requires a real key.
    """

    def __init__(self, address: str, chain_id: int = 137):
        self._address = address
        self.chain_id = chain_id

    def address(self):
        return self._address

    def get_chain_id(self):
        return self.chain_id

    def sign(self, message_hash):
        raise RuntimeError(
            "Order signing requires a private key — "
            "add 'private_key' to your Polymarket config to place orders"
        )


# ---------------------------------------------------------------------------
# PolymarketConnector
# ---------------------------------------------------------------------------

class PolymarketConnector:
    """
    Wraps py-clob-client v0.34.6 for Polymarket CLOB API (Polygon chain_id=137).

    Implements the ExchangeConnector protocol used by RealExchangeExecutor:
        fetch_balance()          -> float (USDC)
        create_limit_order(...)  -> dict  (order result)
        fetch_markets(...)       -> list  (market dicts via Gamma API)
        get_orderbook(token_id)  -> dict
        get_midpoint_price(...)  -> float

    Also starts a WebSocket daemon thread that publishes
    `predictionmarket.price_change` events to the event bus.
    """

    GAMMA_API = "https://gamma-api.polymarket.com"
    WS_URL    = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    HOST      = "https://clob.polymarket.com"

    def __init__(
        self,
        private_key: str = "",
        event_bus=None,
        chain_id: int = 137,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
        signature_type: int = 1,
        funder: str = "",
        address: str = "",
    ):
        self.private_key     = private_key
        self.event_bus       = event_bus
        self.chain_id        = chain_id
        self.api_key         = api_key
        self.api_secret      = api_secret
        self.api_passphrase  = api_passphrase
        self.signature_type  = signature_type
        self.funder          = funder
        self.address         = address
        self._client         = None
        self._ws_thread      = None
        self._connected      = False
        self._read_only_l2   = False

        has_creds = bool(api_key and api_secret and api_passphrase)
        if not private_key and not has_creds:
            logger.info("PolymarketConnector: no private_key or API creds — running in read-only mode (market data only)")
            return

        self._init_client()
        if has_creds or private_key:
            self._check_allowances()
        self._start_websocket()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_client(self):
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
            from py_clob_client.constants import L2

            has_preconfigured_creds = bool(self.api_key and self.api_secret and self.api_passphrase)

            if self.private_key:
                if has_preconfigured_creds:
                    creds = ApiCreds(
                        api_key=self.api_key,
                        api_secret=self.api_secret,
                        api_passphrase=self.api_passphrase,
                    )
                    self._client = ClobClient(
                        host=self.HOST,
                        chain_id=self.chain_id,
                        key=self.private_key,
                        creds=creds,
                        signature_type=self.signature_type,
                        funder=self.funder or None,
                    )
                    mode = "L2 full auth (private key + stored API creds)"

                    if not self._verify_l2_auth():
                        logger.info("PolymarketConnector: stored API creds rejected, re-deriving from L1 auth…")
                        creds = self._derive_fresh_creds()
                        if creds:
                            self._client.set_api_creds(creds)
                            mode = "L2 full auth (private key + freshly derived API creds)"
                        else:
                            mode = "L1 only (cred derivation failed)"
                else:
                    tmp = ClobClient(self.HOST, key=self.private_key, chain_id=self.chain_id)
                    creds = tmp.create_or_derive_api_creds()
                    self._client = ClobClient(
                        self.HOST,
                        key=self.private_key,
                        chain_id=self.chain_id,
                        creds=creds,
                        signature_type=self.signature_type,
                        funder=self.funder or None,
                    )
                    mode = "L2 full auth (derived creds from private key)"

            elif has_preconfigured_creds and (self.address or self.funder):
                wallet_addr = self.address or self.funder
                creds = ApiCreds(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    api_passphrase=self.api_passphrase,
                )
                self._client = ClobClient(
                    host=self.HOST,
                    chain_id=self.chain_id,
                    creds=creds,
                )
                self._client.signer = _AddressOnlySigner(wallet_addr, self.chain_id)
                self._client.mode = L2

                class _SigTypeStub:
                    sig_type = self.signature_type
                self._client.builder = _SigTypeStub()

                self._read_only_l2 = True

                if not self._verify_l2_auth():
                    logger.warning(
                        "PolymarketConnector: L2 auth failed — the 'address' field (%s) "
                        "may be the proxy/funder address, not the signer EOA that generated "
                        "the API key.  Add 'private_key' to your Polymarket config to "
                        "auto-derive the correct signer address and fresh credentials.",
                        wallet_addr[:10] + "…",
                    )
                    self._balance_auth_failed = True
                    mode = "L2 read-only (address-based, auth rejected by server)"
                else:
                    mode = "L2 read-only (address + API creds, no private key)"
            else:
                self._client = ClobClient(host=self.HOST, chain_id=self.chain_id)
                mode = "L0 (no private key, no usable creds)"

            self._connected = True
            logger.info("PolymarketConnector: CLOB client initialised (%s, chain_id=%d)", mode, self.chain_id)
        except Exception as exc:
            logger.error("PolymarketConnector: client init failed — %s", exc)

    def _verify_l2_auth(self) -> bool:
        """Quick probe to check if the current L2 credentials are accepted by the server."""
        try:
            self._client.get_api_keys()
            return True
        except Exception:
            return False

    def _derive_fresh_creds(self):
        """Derive fresh API credentials using L1 private-key auth."""
        try:
            from py_clob_client.client import ClobClient
            tmp = ClobClient(self.HOST, key=self.private_key, chain_id=self.chain_id)
            creds = tmp.create_or_derive_api_creds()
            logger.info("PolymarketConnector: successfully derived fresh L2 API credentials "
                        "(api_key=%s…)", creds.api_key[:8])
            return creds
        except Exception as exc:
            logger.error("PolymarketConnector: failed to derive fresh API creds — %s", exc)
            return None

    def _check_allowances(self):
        """Check USDC/CTF allowances. If auth fails, switch to read-only mode gracefully."""
        if getattr(self, '_balance_auth_failed', False):
            return
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
            result = self._client.get_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            )
            allowance = float(result.get("allowance", 0))
            balance = float(result.get("balance", 0)) / 1e6
            if allowance == 0 and balance == 0:
                logger.info("PolymarketConnector: USDC balance $0.00, allowance 0 — "
                            "deposit USDC on Polygon to start trading")
            else:
                logger.info("PolymarketConnector: USDC balance $%.2f, allowance %.0f", balance, allowance)
        except Exception as exc:
            msg = str(exc)
            if "401" in msg or "Unauthorized" in msg or "Credentials" in msg:
                logger.warning("PolymarketConnector: L2 balance auth rejected by server — "
                               "add 'private_key' to your Polymarket config so fresh credentials "
                               "can be auto-derived. Market data streaming still active.")
                self._balance_auth_failed = True
            else:
                logger.warning("PolymarketConnector: allowance check failed — %s", exc)

    def set_allowances(self):
        """One-time setup: approve USDC + CTF contract."""
        try:
            self._client.set_allowances()
            logger.info("PolymarketConnector: allowances set successfully")
        except Exception as exc:
            logger.error("PolymarketConnector: set_allowances failed — %s", exc)

    # ------------------------------------------------------------------
    # WebSocket streaming
    # ------------------------------------------------------------------

    def _start_websocket(self):
        """Start daemon thread that streams real-time price changes to the event bus."""
        self._ws_thread = threading.Thread(
            target=self._ws_loop,
            daemon=True,
            name="polymarket-ws",
        )
        self._ws_thread.start()
        logger.info("PolymarketConnector: WebSocket daemon thread started")

    def _ws_loop(self):
        try:
            import websocket
            import json

            def on_message(ws, raw):
                try:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        for event in data:
                            self._handle_ws_event(event)
                    else:
                        self._handle_ws_event(data)
                except Exception as exc:
                    logger.debug("Polymarket WS parse error: %s", exc)

            def on_error(ws, error):
                logger.warning("Polymarket WS error: %s", error)

            def on_close(ws, *args):
                logger.info("Polymarket WS closed — reconnecting in 5s")
                time.sleep(5)
                self._ws_loop()

            def on_open(ws):
                logger.info("Polymarket WS connected")
                ws.send(json.dumps({"assets_ids": [], "type": "market"}))

            while True:
                ws = websocket.WebSocketApp(
                    self.WS_URL,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                    on_open=on_open,
                )
                ws.run_forever(ping_interval=10, ping_timeout=5)
                time.sleep(5)

        except ImportError:
            logger.warning("PolymarketConnector: websocket-client not installed — streaming disabled")
        except Exception as exc:
            logger.error("PolymarketConnector: WS loop crashed — %s", exc)

    def _handle_ws_event(self, event: dict):
        """Publish price_change events to the event bus."""
        if not self.event_bus:
            return
        event_type = event.get("event_type") or event.get("type")
        if event_type in ("price_change", "book"):
            try:
                self.event_bus.publish("predictionmarket.price_change", {
                    "exchange": "polymarket",
                    "token_id": event.get("asset_id") or event.get("market"),
                    "event": event,
                    "timestamp": time.time(),
                })
            except Exception as exc:
                logger.debug("PolymarketConnector: event bus publish failed — %s", exc)

    # ------------------------------------------------------------------
    # ExchangeConnector protocol methods
    # ------------------------------------------------------------------

    def fetch_balance(self) -> float:
        """Return available USDC balance (in dollars).

        The Polymarket CLOB API requires valid L2 credentials (api_key +
        api_secret + api_passphrase) *and* the correct signer address
        (derived from the wallet private key).  If the server returns 401
        we log once and cache the failure to avoid log spam.
        """
        if not self._client:
            return 0.0
        if getattr(self, '_balance_auth_failed', False):
            return 0.0
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
            result = self._client.get_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            )
            return float(result.get("balance", 0)) / 1e6
        except Exception as exc:
            msg = str(exc)
            if "401" in msg or "Unauthorized" in msg or "Credentials" in msg or "credentials" in msg:
                logger.warning("PolymarketConnector: balance query returned 401 — "
                               "add 'private_key' to Polymarket config for auto-derivation "
                               "of valid L2 credentials. Market data + WS streaming still active.")
                self._balance_auth_failed = True
            else:
                logger.error("PolymarketConnector.fetch_balance: %s", exc)
            return 0.0

    def create_limit_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        price: float,
    ) -> dict:
        """Place a GTC limit order on Polymarket CLOB."""
        if not self._client:
            return {"error": "client not initialised"}
        if self._read_only_l2:
            return {"error": "order placement requires a private key — "
                    "add 'private_key' to your Polymarket config"}
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.constants import BUY, SELL
            clob_side = BUY if side.upper() == "BUY" else SELL
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=amount,
                side=clob_side,
            )
            signed_order = self._client.create_and_sign_order(order_args)
            result = self._client.post_order(signed_order, OrderType.GTC)
            logger.info("PolymarketConnector: order placed — %s", result)
            return result
        except Exception as exc:
            logger.error("PolymarketConnector.create_limit_order: %s", exc)
            return {"error": str(exc)}

    def fetch_markets(
        self,
        category: Optional[str] = None,
        status: str = "open",
        limit: int = 100,
    ) -> List[dict]:
        """Discover open markets via Gamma API (returns token_ids for CLOB orders)."""
        try:
            params: Dict[str, Any] = {"active": True, "closed": False, "limit": limit}
            if category:
                params["category"] = category
            resp = requests.get(f"{self.GAMMA_API}/markets", params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("PolymarketConnector.fetch_markets: %s", exc)
            return []

    def get_orderbook(self, token_id: str) -> dict:
        """Return CLOB orderbook for a token."""
        if not self._client:
            return {}
        try:
            return self._client.get_order_book(token_id)
        except Exception as exc:
            logger.error("PolymarketConnector.get_orderbook: %s", exc)
            return {}

    def get_midpoint_price(self, token_id: str) -> Optional[float]:
        """Return (best_bid + best_ask) / 2 from CLOB."""
        if not self._client:
            return None
        try:
            book = self.get_orderbook(token_id)
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            if not bids or not asks:
                return None
            best_bid = float(bids[0]["price"])
            best_ask = float(asks[0]["price"])
            return (best_bid + best_ask) / 2.0
        except Exception as exc:
            logger.error("PolymarketConnector.get_midpoint_price: %s", exc)
            return None

    def get_price(self, token_id: str) -> Optional[float]:
        """Alias for get_midpoint_price (satisfies ExchangeConnector protocol)."""
        return self.get_midpoint_price(token_id)

    @property
    def is_connected(self) -> bool:
        return self._connected


# ---------------------------------------------------------------------------
# KalshiConnector
# ---------------------------------------------------------------------------

class KalshiConnector:
    """
    Wraps kalshi-python-sync v3.2.0 for Kalshi REST API v2.

    Implements the ExchangeConnector protocol:
        fetch_balance()          -> float (USD cents -> dollars)
        create_limit_order(...)  -> dict
        fetch_markets(query)     -> list
        get_orderbook(ticker)    -> dict

    Auth: RSA-PSS via api_key_id + private_key_pem (from
    trading.kalshi.com/portfolio/settings/api-keys)
    """

    LIVE_HOST = "https://api.elections.kalshi.com/trade-api/v2"
    DEMO_HOST = "https://demo-api.kalshi.com/trade-api/v2"

    def __init__(
        self,
        api_key_id: str,
        private_key_pem: str,
        demo: bool = False,
    ):
        self.api_key_id      = api_key_id
        self.private_key_pem = private_key_pem
        self.host            = self.DEMO_HOST if demo else self.LIVE_HOST
        self._client         = None
        self._connected      = False

        if not api_key_id or not private_key_pem:
            logger.warning("KalshiConnector: credentials missing — running in read-only mode")
            return

        self._init_client()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_client(self):
        try:
            from kalshi_python_sync import Configuration, KalshiClient
            config                  = Configuration(host=self.host)
            config.api_key_id       = self.api_key_id
            config.private_key_pem  = self.private_key_pem
            self._client            = KalshiClient(config)
            self._connected         = True
            env = "DEMO" if self.host == self.DEMO_HOST else "LIVE"
            logger.info("KalshiConnector: client initialised (%s)", env)
        except Exception as exc:
            logger.error("KalshiConnector: client init failed — %s", exc)

    # ------------------------------------------------------------------
    # ExchangeConnector protocol methods
    # ------------------------------------------------------------------

    def fetch_balance(self) -> float:
        """Return available USD balance (converted from cents)."""
        if not self._client:
            return 0.0
        try:
            result = self._client.get_balance()
            return float(result.balance) / 100.0
        except Exception as exc:
            logger.error("KalshiConnector.fetch_balance: %s", exc)
            return 0.0

    def create_limit_order(
        self,
        ticker: str,
        side: str,
        count: int,
        price: int,
    ) -> dict:
        """Place a limit order on Kalshi."""
        if not self._client:
            return {"error": "client not initialised"}
        try:
            import uuid
            from kalshi_python_sync.models import CreateOrderRequest
            order_req = CreateOrderRequest(
                ticker=ticker,
                action="buy",
                type="limit",
                side=side.lower(),
                count=count,
                yes_price=price if side.lower() == "yes" else (100 - price),
                no_price=price if side.lower() == "no" else (100 - price),
                client_order_id=str(uuid.uuid4()),
            )
            result = self._client.create_order(order_req)
            logger.info("KalshiConnector: order placed — %s", result)
            return result.dict() if hasattr(result, "dict") else vars(result)
        except Exception as exc:
            logger.error("KalshiConnector.create_limit_order: %s", exc)
            return {"error": str(exc)}

    def fetch_markets(self, query: Optional[str] = None, limit: int = 100) -> List[dict]:
        """Return open Kalshi events/markets matching an optional query."""
        if not self._client:
            return []
        try:
            kwargs: Dict[str, Any] = {"limit": limit, "status": "open"}
            if query:
                kwargs["series_ticker"] = query
            result = self._client.get_events(**kwargs)
            events = result.events if hasattr(result, "events") else []
            return [e.dict() if hasattr(e, "dict") else vars(e) for e in events]
        except Exception as exc:
            logger.error("KalshiConnector.fetch_markets: %s", exc)
            return []

    def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        """Return Kalshi orderbook for a market ticker."""
        if not self._client:
            return {}
        try:
            result = self._client.get_order_book(ticker, depth=depth)
            return result.dict() if hasattr(result, "dict") else vars(result)
        except Exception as exc:
            logger.error("KalshiConnector.get_orderbook: %s", exc)
            return {}

    def get_midpoint_price(self, ticker: str) -> Optional[float]:
        """Return midpoint price (in cents) from Kalshi orderbook."""
        try:
            book = self.get_orderbook(ticker, depth=1)
            yes_bids = book.get("yes_bid") or 0
            yes_asks = book.get("yes_ask") or 0
            if yes_bids and yes_asks:
                return (float(yes_bids) + float(yes_asks)) / 2.0
            return None
        except Exception as exc:
            logger.error("KalshiConnector.get_midpoint_price: %s", exc)
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected
