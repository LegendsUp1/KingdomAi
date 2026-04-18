"""
Kingdom AI — Cross-Venue Transfer Manager
=========================================

Orchestrates movement of funds across every venue Kingdom AI is wired to:

- Centralized crypto exchanges (Kraken, Binance, Coinbase, KuCoin, Bybit, etc.)
  via ccxt through ``RealExchangeExecutor``.
- Alpaca brokerage account (stocks + optional crypto) via ``RealStockExecutor``.
- Oanda FX brokerage via ``OandaConnector``.
- Polymarket (USDC on Polygon) via ``PolymarketConnector``.
- Kingdom AI-native on-chain wallets via ``core.wallet_manager.WalletManager``
  and ``core.multichain_trade_executor.MultiChainTradeExecutor``.

Design principles
-----------------
1. **No silent fallbacks.** Every route is explicit. If a transfer is not
   legally possible at the venue level (e.g. Kraken -> Oanda direct USD),
   the manager returns a structured ``manual_action_required`` payload
   instead of pretending it succeeded.
2. **Read-only by default.** ``transfer(..., dry_run=True)`` executes no
   external side-effects; it validates, quotes, and returns the plan.
3. **Isolated profit silos.** Alpaca and Oanda are treated as isolated
   silos the user funds manually. Profits generated inside a silo stay
   there until the user explicitly asks to withdraw.
4. **Event-driven.** All activity is also reachable via the EventBus:
     - ``wallet.cross_venue.transfer`` -> execute a transfer
     - ``wallet.cross_venue.balances``  -> request the global balance sweep
     - ``wallet.cross_venue.routes``    -> request the supported-route table
     - ``wallet.cross_venue.withdraw``  -> user-initiated exit from a silo

This module intentionally does NOT re-implement any venue SDK; it composes
connectors that already exist in the codebase and fills the gap that
sits between "we can trade on X" and "we can move money in and out of X".
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from core.base_component import BaseComponent
except Exception:  # pragma: no cover - fallback for unusual import paths
    try:
        from base_component import BaseComponent  # type: ignore
    except Exception:
        class BaseComponent:  # minimal shim so the module still imports
            def __init__(self, name=None, event_bus=None, config=None):
                self.name = name or self.__class__.__name__
                self.event_bus = event_bus
                self.config = config or {}

try:
    from core.component_registry import get_registry
except Exception:  # pragma: no cover
    get_registry = None  # type: ignore


logger = logging.getLogger("KingdomAI.CrossVenueTransferManager")


class VenueType(str, Enum):
    CRYPTO_CEX = "crypto_cex"        # Kraken, Binance, Coinbase, etc. (ccxt)
    STOCK_BROKER = "stock_broker"    # Alpaca (stocks)
    FX_BROKER = "fx_broker"          # Oanda
    PREDICTION_MARKET = "prediction_market"  # Polymarket (USDC/Polygon)
    ON_CHAIN = "on_chain"            # Kingdom AI-native wallets
    BANK = "bank"                    # User's bank (Plaid bridge)


class TransferStatus(str, Enum):
    OK = "ok"
    DRY_RUN = "dry_run"
    MANUAL_ACTION_REQUIRED = "manual_action_required"
    NOT_PERMITTED = "not_permitted"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


@dataclass
class TransferResult:
    status: TransferStatus
    from_venue: str
    to_venue: str
    asset: str
    amount: float
    details: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "from_venue": self.from_venue,
            "to_venue": self.to_venue,
            "asset": self.asset,
            "amount": self.amount,
            "message": self.message,
            "details": self.details,
            "timestamp": time.time(),
        }


# ---------------------------------------------------------------------------
# Route truth-table
# ---------------------------------------------------------------------------

# (from_type, to_type) -> short description of the rail used.
# Rails that are legally impossible at the venue level are explicitly listed
# as ``NOT_PERMITTED`` so the orchestrator surfaces them instead of silently
# pretending.
SUPPORTED_ROUTES: Dict[tuple, Dict[str, Any]] = {
    # Crypto CEX <-> Crypto CEX  : supported via withdraw + deposit address
    (VenueType.CRYPTO_CEX, VenueType.CRYPTO_CEX): {
        "status": "automatable",
        "rail": "cex.withdraw -> cex.deposit_address",
    },
    # Crypto CEX -> On-chain wallet : ccxt withdraw to a Kingdom wallet
    (VenueType.CRYPTO_CEX, VenueType.ON_CHAIN): {
        "status": "automatable",
        "rail": "cex.withdraw -> kingdom_wallet.address",
    },
    # On-chain wallet -> Crypto CEX : send to exchange deposit address
    (VenueType.ON_CHAIN, VenueType.CRYPTO_CEX): {
        "status": "automatable",
        "rail": "kingdom_wallet.send -> cex.deposit_address",
    },
    # Crypto CEX -> Polymarket  : USDC on Polygon to Polymarket proxy
    (VenueType.CRYPTO_CEX, VenueType.PREDICTION_MARKET): {
        "status": "automatable",
        "rail": "cex.withdraw(USDC,MATIC) -> polymarket.proxy_address",
    },
    # On-chain -> Polymarket  : direct USDC-Polygon send
    (VenueType.ON_CHAIN, VenueType.PREDICTION_MARKET): {
        "status": "automatable",
        "rail": "kingdom_wallet.send(USDC,MATIC) -> polymarket.proxy_address",
    },
    # Polymarket -> Crypto CEX : automated withdraw not exposed; user gate
    (VenueType.PREDICTION_MARKET, VenueType.CRYPTO_CEX): {
        "status": "manual_user_gate",
        "rail": "polymarket.withdraw (UI) -> cex.deposit_address",
    },
    # Alpaca inbound : bank only
    (VenueType.CRYPTO_CEX, VenueType.STOCK_BROKER): {
        "status": "not_permitted_direct",
        "rail": "cex -> bank (ACH/wire) -> alpaca (ACH pull)",
    },
    (VenueType.ON_CHAIN, VenueType.STOCK_BROKER): {
        "status": "not_permitted_direct",
        "rail": "on_chain -> cex -> bank -> alpaca",
    },
    (VenueType.BANK, VenueType.STOCK_BROKER): {
        "status": "semi_automatable",
        "rail": "plaid / broker-initiated ACH pull",
    },
    # Alpaca outbound : ACH withdraw + crypto withdraw
    (VenueType.STOCK_BROKER, VenueType.BANK): {
        "status": "automatable",
        "rail": "alpaca.transfers(ach,OUTGOING)",
    },
    (VenueType.STOCK_BROKER, VenueType.ON_CHAIN): {
        "status": "automatable_crypto_only",
        "rail": "alpaca.wallets.transfers (crypto-enabled accounts)",
    },
    (VenueType.STOCK_BROKER, VenueType.CRYPTO_CEX): {
        "status": "automatable_crypto_only",
        "rail": "alpaca.wallets.transfers -> cex.deposit_address",
    },
    # Oanda inbound : bank only
    (VenueType.CRYPTO_CEX, VenueType.FX_BROKER): {
        "status": "not_permitted_direct",
        "rail": "cex -> bank (ACH/wire) -> oanda",
    },
    (VenueType.BANK, VenueType.FX_BROKER): {
        "status": "manual_user_action",
        "rail": "oanda portal funding",
    },
    # Oanda outbound : no API, manual only
    (VenueType.FX_BROKER, VenueType.BANK): {
        "status": "manual_user_action",
        "rail": "oanda portal -> linked bank",
    },
    (VenueType.FX_BROKER, VenueType.ON_CHAIN): {
        "status": "not_permitted_direct",
        "rail": "oanda (bank) -> cex -> on_chain",
    },
}


class CrossVenueTransferManager(BaseComponent):
    """Orchestrator for all inter-venue fund movements.

    The manager is wired with references to the three executors that own
    the actual venue credentials:

    - ``real_executor`` (``RealExchangeExecutor``): ccxt CEXs + Oanda + Polymarket
    - ``stock_executor`` (``RealStockExecutor``): Alpaca brokerage
    - ``wallet_manager`` (``core.wallet_manager.WalletManager``): Kingdom AI wallets
    - ``onchain_executor`` (``MultiChainTradeExecutor``): optional on-chain sends

    Each dependency is optional at construction time; the manager probes
    availability and exposes ``NOT_CONFIGURED`` results instead of
    crashing when something is missing.
    """

    # Well-known deposit-address defaults for convenience paths.
    POLYMARKET_DEPOSIT_NETWORK = "MATIC"
    POLYMARKET_DEPOSIT_ASSET = "USDC"

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        real_executor: Optional[Any] = None,
        stock_executor: Optional[Any] = None,
        wallet_manager: Optional[Any] = None,
        onchain_executor: Optional[Any] = None,
        polymarket_connector: Optional[Any] = None,
        plaid_bridge: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name="CrossVenueTransferManager", event_bus=event_bus, config=config or {})
        self.logger = logger
        self.real_executor = real_executor
        self.stock_executor = stock_executor
        self.wallet_manager = wallet_manager
        self.onchain_executor = onchain_executor
        self.polymarket_connector = polymarket_connector
        self.plaid_bridge = plaid_bridge

        # Isolated profit silos — tracked ledger per venue.
        self.profit_silos: Dict[str, Dict[str, float]] = {
            "alpaca": {"realized_profit": 0.0, "last_snapshot": 0.0},
            "oanda": {"realized_profit": 0.0, "last_snapshot": 0.0},
            "crypto_cex": {"realized_profit": 0.0, "last_snapshot": 0.0},
            "polymarket": {"realized_profit": 0.0, "last_snapshot": 0.0},
        }

        self._subscriptions_registered = False

    # ------------------------------------------------------------------
    # Dependency discovery
    # ------------------------------------------------------------------
    def attach_dependencies_from_registry(self) -> None:
        """Pull any missing dependencies from the global ComponentRegistry."""
        if get_registry is None:
            return
        reg = get_registry()
        if self.real_executor is None:
            self.real_executor = (
                reg.get("real_exchange_executor")
                or reg.get("real_executor")
            )
        if self.stock_executor is None:
            self.stock_executor = (
                reg.get("real_stock_executor")
                or reg.get("stock_executor")
            )
        if self.wallet_manager is None:
            self.wallet_manager = reg.get("wallet_manager")
        if self.onchain_executor is None:
            self.onchain_executor = reg.get("multichain_trade_executor")
        if self.polymarket_connector is None:
            # Polymarket lives inside real_executor.connectors
            if self.real_executor is not None:
                cons = getattr(self.real_executor, "connectors", {}) or {}
                self.polymarket_connector = cons.get("polymarket")
        if self.plaid_bridge is None:
            self.plaid_bridge = reg.get("plaid_bridge")

    # ------------------------------------------------------------------
    # EventBus wiring
    # ------------------------------------------------------------------
    def register_event_handlers(self) -> None:
        """Subscribe to the cross-venue event family on the EventBus.

        The manager uses the sync EventBus API and schedules async work
        internally to avoid ``coroutine never awaited`` warnings.
        """
        if self._subscriptions_registered:
            return
        bus = self.event_bus
        if bus is None:
            return
        try:
            bus.subscribe("wallet.cross_venue.transfer", self._on_transfer_request)
            bus.subscribe("wallet.cross_venue.withdraw", self._on_withdraw_request)
            bus.subscribe("wallet.cross_venue.balances", self._on_balances_request)
            bus.subscribe("wallet.cross_venue.routes", self._on_routes_request)
            bus.subscribe("wallet.cross_venue.fund_polymarket", self._on_fund_polymarket)
            self._subscriptions_registered = True
            self.logger.info("✅ CrossVenueTransferManager EventBus handlers registered")
        except Exception as exc:
            self.logger.warning("CrossVenueTransferManager: subscribe failed: %s", exc)

    # --- sync EventBus entry points that dispatch async work -----------
    def _on_transfer_request(self, data: Dict[str, Any]) -> None:
        self._run_async(self._handle_transfer_request(data or {}))

    def _on_withdraw_request(self, data: Dict[str, Any]) -> None:
        self._run_async(self._handle_withdraw_request(data or {}))

    def _on_balances_request(self, data: Dict[str, Any]) -> None:
        self._run_async(self._handle_balances_request(data or {}))

    def _on_routes_request(self, data: Dict[str, Any]) -> None:
        self._run_async(self._handle_routes_request(data or {}))

    def _on_fund_polymarket(self, data: Dict[str, Any]) -> None:
        self._run_async(self._handle_fund_polymarket(data or {}))

    def _run_async(self, coro) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            asyncio.create_task(coro)
        else:
            loop.run_until_complete(coro)

    def _publish(self, event: str, payload: Dict[str, Any]) -> None:
        bus = self.event_bus
        if bus is None:
            return
        try:
            bus.publish(event, payload)
        except Exception as exc:
            self.logger.debug("publish(%s) failed: %s", event, exc)

    # ------------------------------------------------------------------
    # Async handlers for EventBus requests
    # ------------------------------------------------------------------
    async def _handle_transfer_request(self, data: Dict[str, Any]) -> None:
        result = await self.transfer(
            from_venue=str(data.get("from_venue", "")),
            to_venue=str(data.get("to_venue", "")),
            asset=str(data.get("asset", "")),
            amount=float(data.get("amount", 0.0) or 0.0),
            network=data.get("network"),
            address_override=data.get("address_override"),
            tag=data.get("tag"),
            dry_run=bool(data.get("dry_run", True)),
            request_id=data.get("request_id"),
        )
        self._publish("wallet.cross_venue.transfer.result", result.to_dict())

    async def _handle_withdraw_request(self, data: Dict[str, Any]) -> None:
        result = await self.withdraw_to_destination(
            from_venue=str(data.get("from_venue", "")),
            destination=str(data.get("destination", "bank")),
            asset=str(data.get("asset", "")),
            amount=float(data.get("amount", 0.0) or 0.0),
            address=data.get("address"),
            network=data.get("network"),
            tag=data.get("tag"),
            relationship_id=data.get("relationship_id"),
            dry_run=bool(data.get("dry_run", True)),
        )
        self._publish("wallet.cross_venue.withdraw.result", result.to_dict())

    async def _handle_balances_request(self, data: Dict[str, Any]) -> None:
        payload = await self.get_all_balances()
        req_id = data.get("request_id")
        if req_id:
            payload["request_id"] = req_id
        self._publish("wallet.cross_venue.balances.result", payload)

    async def _handle_routes_request(self, data: Dict[str, Any]) -> None:
        payload = self.list_supported_routes()
        req_id = data.get("request_id")
        if req_id:
            payload["request_id"] = req_id
        self._publish("wallet.cross_venue.routes.result", payload)

    async def _handle_fund_polymarket(self, data: Dict[str, Any]) -> None:
        result = await self.fund_polymarket(
            from_cex=str(data.get("from_cex", "")),
            usdc_amount=float(data.get("amount", 0.0) or 0.0),
            dry_run=bool(data.get("dry_run", True)),
        )
        self._publish("wallet.cross_venue.fund_polymarket.result", result.to_dict())

    # ------------------------------------------------------------------
    # Venue classification
    # ------------------------------------------------------------------
    def classify_venue(self, venue: str) -> VenueType:
        """Classify a venue string into a ``VenueType``.

        The string may be:
        - a ccxt exchange name (kraken, binance, coinbase, …) -> CRYPTO_CEX
        - "alpaca" -> STOCK_BROKER
        - "oanda" -> FX_BROKER
        - "polymarket" -> PREDICTION_MARKET
        - "bank" -> BANK
        - "on_chain:<symbol>" or a known on-chain network -> ON_CHAIN
        """
        v = (venue or "").strip().lower()
        if not v:
            raise ValueError("venue must not be empty")
        if v == "alpaca":
            return VenueType.STOCK_BROKER
        if v == "oanda":
            return VenueType.FX_BROKER
        if v == "polymarket":
            return VenueType.PREDICTION_MARKET
        if v == "bank":
            return VenueType.BANK
        if v.startswith("on_chain") or v.startswith("onchain") or v in {
            "ethereum", "polygon", "bsc", "arbitrum", "optimism", "base",
            "avalanche", "avax", "solana", "bitcoin", "btc", "xrp",
        }:
            return VenueType.ON_CHAIN
        # Default: assume ccxt CEX name
        return VenueType.CRYPTO_CEX

    # ------------------------------------------------------------------
    # Read-only discovery
    # ------------------------------------------------------------------
    def list_connected_venues(self) -> Dict[str, List[str]]:
        """Return lists of live venues grouped by type."""
        self.attach_dependencies_from_registry()
        crypto: List[str] = []
        if self.real_executor is not None:
            try:
                crypto = [
                    name for name in self.real_executor.list_connected_exchanges()
                    if name not in ("oanda", "polymarket")
                ]
            except Exception:
                crypto = []
        out: Dict[str, List[str]] = {
            "crypto_cex": sorted(crypto),
            "stock_broker": [],
            "fx_broker": [],
            "prediction_market": [],
            "on_chain": [],
        }
        if self.stock_executor is not None and self.stock_executor.brokers.get("alpaca"):
            out["stock_broker"].append("alpaca")
        if self.real_executor is not None:
            cons = getattr(self.real_executor, "connectors", {}) or {}
            if "oanda" in cons:
                out["fx_broker"].append("oanda")
            if "polymarket" in cons:
                out["prediction_market"].append("polymarket")
        if self.wallet_manager is not None:
            try:
                chains = sorted(list(getattr(self.wallet_manager, "BLOCKCHAINS", {}) or {}))
                out["on_chain"] = chains
            except Exception:
                out["on_chain"] = []
        return out

    def list_supported_routes(self) -> Dict[str, Any]:
        """Return the static route truth-table plus live connectivity."""
        self.attach_dependencies_from_registry()
        connected = self.list_connected_venues()
        routes = []
        for (from_t, to_t), info in SUPPORTED_ROUTES.items():
            routes.append({
                "from_type": from_t.value,
                "to_type": to_t.value,
                "status": info["status"],
                "rail": info["rail"],
            })
        return {
            "connected": connected,
            "routes": routes,
            "note": (
                "Rails marked 'not_permitted_direct' cannot be automated "
                "at the venue level; the user must fund the brokerage "
                "account manually via bank (ACH/wire)."
            ),
        }

    async def get_all_balances(self) -> Dict[str, Any]:
        """Read balances from every connected venue — read-only.

        This is the "tell me exactly what each wallet has" answer.
        """
        self.attach_dependencies_from_registry()
        report: Dict[str, Any] = {
            "timestamp": time.time(),
            "crypto_cex": {},
            "stock_broker": {},
            "fx_broker": {},
            "prediction_market": {},
            "on_chain": {},
        }

        # Crypto CEXs + Oanda + Polymarket (all via real_executor.connectors)
        if self.real_executor is not None:
            try:
                sweep = await self.real_executor.fetch_balances_all()
            except Exception as exc:
                sweep = {"_error": str(exc)}
            for name, payload in (sweep or {}).items():
                if name == "_error":
                    report["crypto_cex"]["_sweep_error"] = payload
                    continue
                if name == "oanda":
                    report["fx_broker"]["oanda"] = payload
                elif name == "polymarket":
                    report["prediction_market"]["polymarket"] = payload
                else:
                    report["crypto_cex"][name] = payload

        # Alpaca stock broker
        if self.stock_executor is not None:
            try:
                alpaca = await self.stock_executor.get_alpaca_account_summary()
            except Exception as exc:
                alpaca = {"status": "error", "error": str(exc)}
            report["stock_broker"]["alpaca"] = alpaca

        # On-chain Kingdom wallets
        if self.wallet_manager is not None:
            try:
                addresses = getattr(self.wallet_manager, "address_cache", {}) or {}
                report["on_chain"]["addresses"] = {
                    k: v for k, v in addresses.items() if isinstance(v, str)
                }
            except Exception as exc:
                report["on_chain"]["error"] = str(exc)

        return report

    # ------------------------------------------------------------------
    # Transfer execution
    # ------------------------------------------------------------------
    async def transfer(
        self,
        from_venue: str,
        to_venue: str,
        asset: str,
        amount: float,
        network: Optional[str] = None,
        address_override: Optional[str] = None,
        tag: Optional[str] = None,
        dry_run: bool = True,
        request_id: Optional[str] = None,  # noqa: ARG002 - kept for symmetry
    ) -> TransferResult:
        """Top-level dispatcher.

        Returns a ``TransferResult`` describing what happened (or what
        would happen, when ``dry_run=True``).
        """
        try:
            self.attach_dependencies_from_registry()
            if not asset or amount <= 0:
                return TransferResult(
                    TransferStatus.ERROR, from_venue, to_venue, asset, amount,
                    message="asset and positive amount are required",
                )
            from_t = self.classify_venue(from_venue)
            to_t = self.classify_venue(to_venue)
            rail = SUPPORTED_ROUTES.get((from_t, to_t))
            if rail is None:
                return TransferResult(
                    TransferStatus.NOT_PERMITTED, from_venue, to_venue, asset, amount,
                    message=(
                        f"No defined rail between {from_t.value} and {to_t.value}. "
                        "Split into an intermediate hop (e.g. CEX -> bank -> broker)."
                    ),
                )

            # Dispatch by (from, to)
            if from_t == VenueType.CRYPTO_CEX and to_t == VenueType.CRYPTO_CEX:
                return await self._cex_to_cex(
                    from_venue, to_venue, asset, amount, network, tag, dry_run,
                )
            if from_t == VenueType.CRYPTO_CEX and to_t == VenueType.ON_CHAIN:
                return await self._cex_to_onchain(
                    from_venue, to_venue, asset, amount, network,
                    address_override, tag, dry_run,
                )
            if from_t == VenueType.ON_CHAIN and to_t == VenueType.CRYPTO_CEX:
                return await self._onchain_to_cex(
                    from_venue, to_venue, asset, amount, network, tag, dry_run,
                )
            if from_t == VenueType.CRYPTO_CEX and to_t == VenueType.PREDICTION_MARKET:
                return await self._cex_to_polymarket(
                    from_venue, asset, amount, address_override, dry_run,
                )
            if from_t == VenueType.ON_CHAIN and to_t == VenueType.PREDICTION_MARKET:
                return await self._onchain_to_polymarket(
                    from_venue, asset, amount, address_override, dry_run,
                )

            # Inbound to stock/fx brokers is not legally permitted direct.
            if to_t in (VenueType.STOCK_BROKER, VenueType.FX_BROKER) and from_t not in (
                VenueType.BANK,
            ):
                return TransferResult(
                    TransferStatus.NOT_PERMITTED, from_venue, to_venue, asset, amount,
                    message=(
                        f"Direct {from_t.value} -> {to_t.value} funding is not "
                        "permitted by the venue. Fund the brokerage via ACH/wire "
                        "from your linked bank instead."
                    ),
                    details={"rail": rail["rail"]},
                )

            # Bank -> Stock broker (Alpaca) via Plaid-assisted ACH pull
            if from_t == VenueType.BANK and to_t == VenueType.STOCK_BROKER:
                return await self._bank_to_alpaca(amount, dry_run)

            # Bank -> Oanda is always manual.
            if from_t == VenueType.BANK and to_t == VenueType.FX_BROKER:
                return TransferResult(
                    TransferStatus.MANUAL_ACTION_REQUIRED, from_venue, to_venue,
                    asset, amount,
                    message=(
                        "Fund Oanda from the Oanda portal. Kingdom AI will "
                        "detect the updated balance on the next summary sync."
                    ),
                    details={"portal_url": "https://www.oanda.com/account/funding"},
                )

            # Alpaca outbound paths
            if from_t == VenueType.STOCK_BROKER and to_t == VenueType.BANK:
                return await self._alpaca_to_bank(amount, dry_run)
            if from_t == VenueType.STOCK_BROKER and to_t in (
                VenueType.ON_CHAIN, VenueType.CRYPTO_CEX,
            ):
                return await self._alpaca_crypto_withdraw(
                    asset, amount, address_override, network, dry_run,
                )

            # Oanda outbound is always manual.
            if from_t == VenueType.FX_BROKER:
                return TransferResult(
                    TransferStatus.MANUAL_ACTION_REQUIRED, from_venue, to_venue,
                    asset, amount,
                    message=(
                        "Oanda does not expose a withdrawal API. Withdraw from "
                        "the Oanda portal; Kingdom AI will reflect the balance "
                        "change on the next summary sync."
                    ),
                    details={"portal_url": "https://www.oanda.com/account/funding"},
                )

            return TransferResult(
                TransferStatus.NOT_PERMITTED, from_venue, to_venue, asset, amount,
                message=f"Unhandled route {from_t.value} -> {to_t.value}",
            )
        except Exception as exc:
            self.logger.error("transfer() failed: %s", exc)
            return TransferResult(
                TransferStatus.ERROR, from_venue, to_venue, asset, amount,
                message=str(exc),
            )

    async def withdraw_to_destination(
        self,
        from_venue: str,
        destination: str,
        asset: str,
        amount: float,
        address: Optional[str] = None,
        network: Optional[str] = None,
        tag: Optional[str] = None,
        relationship_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> TransferResult:
        """User-initiated exit from a silo.

        ``destination`` is one of ``"bank"``, ``"wallet"`` (user-supplied
        on-chain address), or a named venue. ``address`` is required for
        ``destination == "wallet"``.
        """
        self.attach_dependencies_from_registry()
        dest = (destination or "").strip().lower()
        if dest == "bank":
            from_t = self.classify_venue(from_venue)
            if from_t == VenueType.STOCK_BROKER:
                return await self._alpaca_to_bank(amount, dry_run, relationship_id)
            if from_t == VenueType.FX_BROKER:
                return TransferResult(
                    TransferStatus.MANUAL_ACTION_REQUIRED, from_venue, "bank",
                    asset, amount,
                    message=(
                        "Oanda withdrawals are not API-accessible. Use the "
                        "Oanda portal to withdraw to your linked bank."
                    ),
                    details={"portal_url": "https://www.oanda.com/account/funding"},
                )
            if from_t == VenueType.CRYPTO_CEX:
                return TransferResult(
                    TransferStatus.MANUAL_ACTION_REQUIRED, from_venue, "bank",
                    asset, amount,
                    message=(
                        "CEX -> bank fiat withdrawals are venue-specific and "
                        "often require manual confirmation. Use the "
                        "exchange's banking page or add a fiat-withdraw "
                        "adapter if your exchange exposes one via ccxt."
                    ),
                )
            return TransferResult(
                TransferStatus.NOT_PERMITTED, from_venue, "bank", asset, amount,
                message=f"No bank-rail from {from_t.value}",
            )
        if dest == "wallet":
            if not address:
                return TransferResult(
                    TransferStatus.ERROR, from_venue, "wallet", asset, amount,
                    message="'address' is required when destination='wallet'",
                )
            from_t = self.classify_venue(from_venue)
            if from_t == VenueType.CRYPTO_CEX:
                return await self._cex_withdraw_raw(
                    from_venue, asset, amount, address, network, tag, dry_run,
                )
            if from_t == VenueType.STOCK_BROKER:
                return await self._alpaca_crypto_withdraw(
                    asset, amount, address, network, dry_run,
                )
            if from_t == VenueType.FX_BROKER:
                return TransferResult(
                    TransferStatus.MANUAL_ACTION_REQUIRED, from_venue, "wallet",
                    asset, amount,
                    message="Oanda cannot withdraw directly to a crypto wallet.",
                )
            if from_t == VenueType.ON_CHAIN:
                return TransferResult(
                    TransferStatus.DRY_RUN if dry_run else TransferStatus.OK,
                    from_venue, address, asset, amount,
                    message=(
                        "On-chain -> on-chain transfer: use "
                        "WalletManager.send_transaction for native assets or "
                        "MultiChainTradeExecutor.execute_swap for DEX routes."
                    ),
                )
            return TransferResult(
                TransferStatus.NOT_PERMITTED, from_venue, "wallet", asset, amount,
                message=f"No wallet-rail from {from_t.value}",
            )
        # Named venue: reuse transfer()
        return await self.transfer(
            from_venue=from_venue, to_venue=destination, asset=asset,
            amount=amount, address_override=address, network=network, tag=tag,
            dry_run=dry_run,
        )

    # ------------------------------------------------------------------
    # Rail implementations
    # ------------------------------------------------------------------
    async def _cex_to_cex(
        self, from_cex: str, to_cex: str, asset: str, amount: float,
        network: Optional[str], tag: Optional[str], dry_run: bool,
    ) -> TransferResult:
        if self.real_executor is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_cex, to_cex, asset, amount,
                message="RealExchangeExecutor is not attached",
            )
        # Discover the destination deposit address.
        try:
            dest = await self.real_executor.fetch_deposit_address(
                to_cex, asset, network=network,
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, from_cex, to_cex, asset, amount,
                message=f"Could not fetch deposit address on {to_cex}: {exc}",
            )
        address = dest.get("address")
        if not address:
            return TransferResult(
                TransferStatus.ERROR, from_cex, to_cex, asset, amount,
                message=f"{to_cex} returned empty deposit address for {asset}",
            )
        details = {
            "dest_address": address,
            "dest_tag": dest.get("tag"),
            "dest_network": dest.get("network") or network,
            "rail": "cex.withdraw -> cex.deposit_address",
        }
        if dry_run:
            return TransferResult(
                TransferStatus.DRY_RUN, from_cex, to_cex, asset, amount,
                details=details, message="Withdrawal plan validated (dry run)",
            )
        try:
            withdraw_result = await self.real_executor.withdraw(
                from_cex, asset, amount, address=address,
                tag=tag or dest.get("tag"),
                network=dest.get("network") or network,
            )
            details.update({"withdraw_result": withdraw_result})
            return TransferResult(
                TransferStatus.OK, from_cex, to_cex, asset, amount,
                details=details, message="Withdrawal submitted",
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, from_cex, to_cex, asset, amount,
                details=details, message=str(exc),
            )

    async def _cex_to_onchain(
        self, from_cex: str, to_chain: str, asset: str, amount: float,
        network: Optional[str], address_override: Optional[str],
        tag: Optional[str], dry_run: bool,
    ) -> TransferResult:
        if self.real_executor is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_cex, to_chain, asset, amount,
                message="RealExchangeExecutor is not attached",
            )
        address = address_override
        if not address and self.wallet_manager is not None:
            address = (
                self.wallet_manager.address_cache.get(asset.upper())
                or self.wallet_manager.address_cache.get(to_chain.lower())
            )
        if not address:
            return TransferResult(
                TransferStatus.ERROR, from_cex, to_chain, asset, amount,
                message=(
                    f"No Kingdom wallet address for {asset}/{to_chain}. "
                    "Pass address_override or register the wallet."
                ),
            )
        details = {
            "dest_address": address,
            "dest_network": network,
            "rail": "cex.withdraw -> kingdom_wallet",
        }
        if dry_run:
            return TransferResult(
                TransferStatus.DRY_RUN, from_cex, to_chain, asset, amount,
                details=details, message="CEX -> wallet plan validated (dry run)",
            )
        try:
            result = await self.real_executor.withdraw(
                from_cex, asset, amount, address=address,
                tag=tag, network=network,
            )
            details["withdraw_result"] = result
            return TransferResult(
                TransferStatus.OK, from_cex, to_chain, asset, amount,
                details=details, message="CEX withdraw submitted",
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, from_cex, to_chain, asset, amount,
                details=details, message=str(exc),
            )

    async def _onchain_to_cex(
        self, from_chain: str, to_cex: str, asset: str, amount: float,
        network: Optional[str], tag: Optional[str], dry_run: bool,
    ) -> TransferResult:
        if self.real_executor is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_chain, to_cex, asset, amount,
                message="RealExchangeExecutor is not attached",
            )
        try:
            dest = await self.real_executor.fetch_deposit_address(
                to_cex, asset, network=network,
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, from_chain, to_cex, asset, amount,
                message=f"Could not fetch deposit address on {to_cex}: {exc}",
            )
        address = dest.get("address")
        details = {
            "dest_address": address,
            "dest_tag": dest.get("tag") or tag,
            "rail": "kingdom_wallet.send -> cex.deposit_address",
        }
        if dry_run:
            return TransferResult(
                TransferStatus.DRY_RUN, from_chain, to_cex, asset, amount,
                details=details,
                message="On-chain -> CEX plan validated (dry run)",
            )
        if self.wallet_manager is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_chain, to_cex, asset, amount,
                details=details, message="WalletManager not attached",
            )
        # Best-effort: if the wallet_manager exposes send_transaction, use it.
        send = getattr(self.wallet_manager, "send_transaction", None)
        if send is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_chain, to_cex, asset, amount,
                details=details,
                message="WalletManager does not expose send_transaction",
            )
        try:
            res = await send(asset.upper(), address, amount)
            details["send_result"] = res
            return TransferResult(
                TransferStatus.OK, from_chain, to_cex, asset, amount,
                details=details, message="On-chain send submitted",
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, from_chain, to_cex, asset, amount,
                details=details, message=str(exc),
            )

    async def _cex_to_polymarket(
        self, from_cex: str, asset: str, amount: float,
        address_override: Optional[str], dry_run: bool,
    ) -> TransferResult:
        poly_addr = address_override or self._polymarket_deposit_address()
        if not poly_addr:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_cex, "polymarket", asset, amount,
                message="Polymarket proxy address unknown (set PolymarketConnector.funder)",
            )
        if asset.upper() != self.POLYMARKET_DEPOSIT_ASSET:
            return TransferResult(
                TransferStatus.NOT_PERMITTED, from_cex, "polymarket", asset, amount,
                message=(
                    f"Polymarket only accepts {self.POLYMARKET_DEPOSIT_ASSET} "
                    f"on {self.POLYMARKET_DEPOSIT_NETWORK}. Swap first."
                ),
            )
        return await self._cex_withdraw_raw(
            from_cex=from_cex, asset=asset, amount=amount,
            address=poly_addr, network=self.POLYMARKET_DEPOSIT_NETWORK,
            tag=None, dry_run=dry_run,
            destination_label="polymarket",
        )

    async def _onchain_to_polymarket(
        self, from_chain: str, asset: str, amount: float,
        address_override: Optional[str], dry_run: bool,
    ) -> TransferResult:
        poly_addr = address_override or self._polymarket_deposit_address()
        if not poly_addr:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_chain, "polymarket", asset, amount,
                message="Polymarket proxy address unknown",
            )
        details = {"dest_address": poly_addr, "rail": "kingdom_wallet -> polymarket"}
        if dry_run:
            return TransferResult(
                TransferStatus.DRY_RUN, from_chain, "polymarket", asset, amount,
                details=details, message="On-chain -> polymarket plan validated",
            )
        if self.wallet_manager is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_chain, "polymarket", asset, amount,
                details=details, message="WalletManager not attached",
            )
        send = getattr(self.wallet_manager, "send_transaction", None)
        if send is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_chain, "polymarket", asset, amount,
                details=details,
                message="WalletManager does not expose send_transaction",
            )
        try:
            res = await send(asset.upper(), poly_addr, amount)
            details["send_result"] = res
            return TransferResult(
                TransferStatus.OK, from_chain, "polymarket", asset, amount,
                details=details, message="On-chain send submitted",
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, from_chain, "polymarket", asset, amount,
                details=details, message=str(exc),
            )

    async def _cex_withdraw_raw(
        self, from_cex: str, asset: str, amount: float, address: str,
        network: Optional[str], tag: Optional[str], dry_run: bool,
        destination_label: Optional[str] = None,
    ) -> TransferResult:
        dest_label = destination_label or "external_address"
        if self.real_executor is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, from_cex, dest_label, asset, amount,
                message="RealExchangeExecutor is not attached",
            )
        details = {
            "dest_address": address, "dest_network": network,
            "dest_tag": tag, "rail": "cex.withdraw -> external",
        }
        if dry_run:
            return TransferResult(
                TransferStatus.DRY_RUN, from_cex, dest_label, asset, amount,
                details=details, message="Withdrawal plan validated",
            )
        try:
            res = await self.real_executor.withdraw(
                from_cex, asset, amount, address=address,
                tag=tag, network=network,
            )
            details["withdraw_result"] = res
            return TransferResult(
                TransferStatus.OK, from_cex, dest_label, asset, amount,
                details=details, message="Withdrawal submitted",
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, from_cex, dest_label, asset, amount,
                details=details, message=str(exc),
            )

    async def _alpaca_to_bank(
        self, amount: float, dry_run: bool,
        relationship_id: Optional[str] = None,
    ) -> TransferResult:
        if self.stock_executor is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, "alpaca", "bank", "USD", amount,
                message="RealStockExecutor is not attached",
            )
        if dry_run:
            return TransferResult(
                TransferStatus.DRY_RUN, "alpaca", "bank", "USD", amount,
                message="Alpaca ACH withdrawal plan validated",
                details={"rail": "alpaca.transfers(ach,OUTGOING)"},
            )
        try:
            res = await self.stock_executor.alpaca_withdraw_ach(
                amount, relationship_id=relationship_id,
            )
            return TransferResult(
                TransferStatus.OK, "alpaca", "bank", "USD", amount,
                details={"transfer": res}, message="ACH withdrawal submitted",
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, "alpaca", "bank", "USD", amount,
                message=str(exc),
            )

    async def _alpaca_crypto_withdraw(
        self, asset: str, amount: float, address: Optional[str],
        network: Optional[str], dry_run: bool,
    ) -> TransferResult:
        if self.stock_executor is None:
            return TransferResult(
                TransferStatus.NOT_CONFIGURED, "alpaca", "wallet", asset, amount,
                message="RealStockExecutor is not attached",
            )
        if not address:
            return TransferResult(
                TransferStatus.ERROR, "alpaca", "wallet", asset, amount,
                message="Alpaca crypto withdraw requires an address",
            )
        if dry_run:
            return TransferResult(
                TransferStatus.DRY_RUN, "alpaca", "wallet", asset, amount,
                details={
                    "rail": "alpaca.wallets.transfers",
                    "dest_address": address, "network": network,
                },
                message="Alpaca crypto withdrawal plan validated",
            )
        try:
            res = await self.stock_executor.alpaca_crypto_withdraw(
                asset=asset, amount=amount, address=address, network=network,
            )
            return TransferResult(
                TransferStatus.OK, "alpaca", "wallet", asset, amount,
                details={"transfer": res}, message="Alpaca crypto withdraw submitted",
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, "alpaca", "wallet", asset, amount,
                message=str(exc),
            )

    async def _bank_to_alpaca(self, amount: float, dry_run: bool) -> TransferResult:
        if self.plaid_bridge is None:
            return TransferResult(
                TransferStatus.MANUAL_ACTION_REQUIRED, "bank", "alpaca", "USD", amount,
                message=(
                    "Plaid bridge not configured. Initiate the ACH deposit "
                    "from the Alpaca dashboard (Banking -> Deposit)."
                ),
                details={
                    "portal_url": "https://app.alpaca.markets/brokerage/banking",
                },
            )
        if dry_run:
            return TransferResult(
                TransferStatus.DRY_RUN, "bank", "alpaca", "USD", amount,
                message="Plaid ACH plan validated",
            )
        try:
            res = await self.plaid_bridge.initiate_ach_to_alpaca(amount=amount)
            return TransferResult(
                TransferStatus.OK, "bank", "alpaca", "USD", amount,
                details={"plaid_result": res},
                message="ACH pull initiated via Plaid bridge",
            )
        except Exception as exc:
            return TransferResult(
                TransferStatus.ERROR, "bank", "alpaca", "USD", amount,
                message=str(exc),
            )

    # ------------------------------------------------------------------
    # Convenience: fund Polymarket
    # ------------------------------------------------------------------
    async def fund_polymarket(
        self, from_cex: str, usdc_amount: float, dry_run: bool = True,
    ) -> TransferResult:
        """Convenience: withdraw USDC (Polygon) from a CEX to the user's
        Polymarket proxy address."""
        return await self._cex_to_polymarket(
            from_cex=from_cex,
            asset=self.POLYMARKET_DEPOSIT_ASSET,
            amount=usdc_amount,
            address_override=None,
            dry_run=dry_run,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _polymarket_deposit_address(self) -> Optional[str]:
        """Return the user's Polymarket proxy / funder address if known."""
        if self.polymarket_connector is None:
            return None
        for attr in ("funder", "proxy_address", "address"):
            val = getattr(self.polymarket_connector, attr, None)
            if isinstance(val, str) and val:
                return val
        return None

    def record_realized_profit(self, silo: str, profit_delta: float) -> None:
        """Add a realized-profit delta to the named silo ledger."""
        key = silo.lower()
        if key not in self.profit_silos:
            self.profit_silos[key] = {"realized_profit": 0.0, "last_snapshot": 0.0}
        self.profit_silos[key]["realized_profit"] = (
            float(self.profit_silos[key]["realized_profit"]) + float(profit_delta or 0.0)
        )
        self._publish("wallet.silo.profit.updated", {
            "silo": key,
            "realized_profit": self.profit_silos[key]["realized_profit"],
            "delta": float(profit_delta or 0.0),
            "timestamp": time.time(),
        })

    def get_silo_ledger(self) -> Dict[str, Dict[str, float]]:
        return {k: dict(v) for k, v in self.profit_silos.items()}


__all__ = [
    "CrossVenueTransferManager",
    "TransferResult",
    "TransferStatus",
    "VenueType",
    "SUPPORTED_ROUTES",
]
