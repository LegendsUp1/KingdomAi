"""
Kingdom AI — Plaid ACH Bridge (thin)
====================================

A deliberately small adapter that gives Kingdom AI the *option* of
pushing ACH transfers from the user's bank into Alpaca (and, when the
venue permits it, surfacing ACH pulls from CEX fiat rails).

Design intent
-------------
- This module does NOT ship credentials or hard-code a public tenant.
- If Plaid is not configured (no ``PLAID_CLIENT_ID`` / ``PLAID_SECRET``),
  every method returns a structured ``manual_action_required`` payload
  with the correct user-facing portal URL instead of crashing.
- When Plaid *is* configured, the bridge performs the minimum dance:
  ``/transfer/authorization/create`` -> ``/transfer/create``. We do NOT
  attempt to implement Plaid Link token exchange here; the user links
  their bank in the GUI and persists ``plaid_access_token`` +
  ``plaid_account_id`` via ``global_api_keys``.
- The bridge is also registered on the EventBus so the
  ``CrossVenueTransferManager`` can discover it via the component
  registry.

This module has no hard runtime dependency on the ``plaid`` Python SDK;
it talks to the REST endpoints directly with ``requests`` (which is
already a project dependency) so the bridge can ship even on machines
that don't have the SDK installed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

try:
    from global_api_keys import get_api_key_manager
except Exception:  # pragma: no cover
    get_api_key_manager = None  # type: ignore


logger = logging.getLogger("KingdomAI.PlaidACHBridge")


PLAID_ENVIRONMENTS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}


class PlaidACHBridge:
    """Minimal Plaid Transfer adapter.

    Configuration precedence (first non-empty wins):
    1. constructor kwargs
    2. ``global_api_keys.get_api_key('plaid', …)``
    3. environment variables (``PLAID_CLIENT_ID``, ``PLAID_SECRET``,
       ``PLAID_ENV``, ``PLAID_ACCESS_TOKEN``, ``PLAID_ACCOUNT_ID``)
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        secret: Optional[str] = None,
        env: Optional[str] = None,
        access_token: Optional[str] = None,
        account_id: Optional[str] = None,
        event_bus: Optional[Any] = None,
    ) -> None:
        self.event_bus = event_bus
        self.client_id = client_id or self._read_key("client_id", "PLAID_CLIENT_ID")
        self.secret = secret or self._read_key("secret", "PLAID_SECRET")
        self.env = (env or self._read_key("env", "PLAID_ENV") or "sandbox").lower()
        self.access_token = (
            access_token or self._read_key("access_token", "PLAID_ACCESS_TOKEN")
        )
        self.account_id = (
            account_id or self._read_key("account_id", "PLAID_ACCOUNT_ID")
        )
        self.base_url = PLAID_ENVIRONMENTS.get(self.env, PLAID_ENVIRONMENTS["sandbox"])
        self._configured = bool(
            self.client_id and self.secret and self.access_token
            and self.account_id and requests is not None
        )
        if not self._configured:
            logger.info(
                "PlaidACHBridge running in manual-action mode "
                "(client_id=%s, secret=%s, access_token=%s, account_id=%s, requests=%s)",
                bool(self.client_id), bool(self.secret),
                bool(self.access_token), bool(self.account_id),
                requests is not None,
            )

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------
    def _read_key(self, subkey: str, env_name: str) -> Optional[str]:
        val = os.environ.get(env_name)
        if val:
            return val
        if get_api_key_manager is None:
            return None
        try:
            mgr = get_api_key_manager()
            if mgr is None:
                return None
            getter = getattr(mgr, "get_api_key", None) or getattr(mgr, "get_key", None)
            if getter is None:
                return None
            val = getter("plaid", subkey)
            return str(val) if val else None
        except Exception:
            return None

    @property
    def configured(self) -> bool:
        return self._configured

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self._configured,
            "environment": self.env,
            "has_client_id": bool(self.client_id),
            "has_secret": bool(self.secret),
            "has_access_token": bool(self.access_token),
            "has_account_id": bool(self.account_id),
            "requests_available": requests is not None,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def initiate_ach_to_alpaca(
        self,
        amount: float,
        description: str = "Kingdom AI funding",
    ) -> Dict[str, Any]:
        """Originate an ACH debit from the user's linked bank.

        This is the user-initiated "move money from my bank into Alpaca"
        rail. When Plaid is not configured, we return the Alpaca funding
        URL so the caller can surface a manual-action prompt.
        """
        if amount <= 0:
            return {"status": "error", "reason": "amount must be positive"}
        if not self._configured:
            return {
                "status": "manual_action_required",
                "reason": (
                    "Plaid is not configured. Fund Alpaca directly via the "
                    "dashboard (ACH, wire, or debit card)."
                ),
                "portal_url": "https://app.alpaca.markets/brokerage/banking",
            }
        try:
            auth = await asyncio.to_thread(self._authorize_debit, amount, description)
            if auth.get("status") != "ok":
                return auth
            transfer = await asyncio.to_thread(
                self._create_transfer, auth["authorization_id"], amount, description,
            )
            self._publish_event("plaid.ach.initiated", {
                "amount": float(amount),
                "transfer_id": transfer.get("transfer_id"),
                "status": transfer.get("status"),
                "timestamp": time.time(),
            })
            return transfer
        except Exception as exc:
            logger.error("Plaid ACH initiate failed: %s", exc)
            return {"status": "error", "reason": str(exc)}

    async def get_bank_snapshot(self) -> Dict[str, Any]:
        """Return a read-only snapshot of the linked bank account."""
        if not self._configured:
            return {
                "status": "manual_action_required",
                "reason": "Plaid not configured",
                "details": self.status(),
            }
        try:
            payload = {
                "client_id": self.client_id,
                "secret": self.secret,
                "access_token": self.access_token,
                "options": {"account_ids": [self.account_id]},
            }
            r = await asyncio.to_thread(
                requests.post,  # type: ignore[union-attr]
                f"{self.base_url}/accounts/balance/get",
                json=payload, timeout=15,
            )
            if r.status_code >= 400:
                return {"status": "error", "reason": r.text, "http": r.status_code}
            data = r.json() or {}
            accounts = data.get("accounts") or []
            target = next(
                (a for a in accounts if a.get("account_id") == self.account_id),
                accounts[0] if accounts else None,
            )
            if not target:
                return {"status": "error", "reason": "No accounts returned"}
            bal = target.get("balances", {})
            return {
                "status": "ok",
                "account_id": target.get("account_id"),
                "name": target.get("name"),
                "mask": target.get("mask"),
                "subtype": target.get("subtype"),
                "currency": bal.get("iso_currency_code"),
                "available": bal.get("available"),
                "current": bal.get("current"),
            }
        except Exception as exc:
            return {"status": "error", "reason": str(exc)}

    # ------------------------------------------------------------------
    # Internal Plaid calls
    # ------------------------------------------------------------------
    def _authorize_debit(self, amount: float, description: str) -> Dict[str, Any]:
        payload = {
            "client_id": self.client_id,
            "secret": self.secret,
            "access_token": self.access_token,
            "account_id": self.account_id,
            "type": "debit",
            "network": "ach",
            "amount": f"{amount:.2f}",
            "ach_class": "ppd",
            "user": {"legal_name": "Kingdom AI User"},
            "description": description[:15],  # Plaid 15-char cap
        }
        r = requests.post(  # type: ignore[union-attr]
            f"{self.base_url}/transfer/authorization/create",
            json=payload, timeout=20,
        )
        if r.status_code >= 400:
            return {"status": "error", "reason": r.text, "http": r.status_code}
        data = r.json() or {}
        auth = data.get("authorization") or {}
        if auth.get("decision") != "approved":
            return {
                "status": "declined",
                "reason": auth.get("decision_rationale") or "Plaid did not approve",
                "raw": auth,
            }
        return {"status": "ok", "authorization_id": auth.get("id")}

    def _create_transfer(
        self, authorization_id: str, amount: float, description: str,
    ) -> Dict[str, Any]:
        payload = {
            "client_id": self.client_id,
            "secret": self.secret,
            "access_token": self.access_token,
            "account_id": self.account_id,
            "authorization_id": authorization_id,
            "description": description[:15],
        }
        r = requests.post(  # type: ignore[union-attr]
            f"{self.base_url}/transfer/create",
            json=payload, timeout=20,
        )
        if r.status_code >= 400:
            return {"status": "error", "reason": r.text, "http": r.status_code}
        data = r.json() or {}
        t = data.get("transfer") or {}
        return {
            "status": "ok",
            "transfer_id": t.get("id"),
            "transfer_status": t.get("status"),
            "amount": t.get("amount"),
            "network": t.get("network"),
        }

    # ------------------------------------------------------------------
    # EventBus helpers
    # ------------------------------------------------------------------
    def _publish_event(self, event: str, data: Dict[str, Any]) -> None:
        if self.event_bus is None:
            return
        try:
            self.event_bus.publish(event, data)
        except Exception as exc:
            logger.debug("publish(%s) failed: %s", event, exc)


__all__ = ["PlaidACHBridge"]
