#!/usr/bin/env python3
"""Central, lightweight telemetry collector for Kingdom AI.

This component listens on the core EventBus for structured telemetry topics
(e.g. ai.telemetry, trading.telemetry, mining.telemetry, blockchain.telemetry,
wallet.telemetry) and keeps an in-memory ring buffer of recent events plus
simple counters.

Design constraints:
- Purely in-process, no external network or disk I/O in the hot path.
- Handlers are synchronous and extremely cheap to avoid adding latency.
- Uses the existing core.event_bus.EventBus instance; no new buses.
- Compatible with both GUI and headless runs.
"""

from __future__ import annotations

import logging
from datetime import datetime
from threading import RLock
from typing import Any, Dict, List, Optional

from core.event_bus import EventBus

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """Lightweight, centralized telemetry sink.

    This class is intentionally minimal: it only stores recent events and
    maintains basic counters. It does *not* perform any heavy aggregation,
    disk writes, or network calls in the event handlers.
    """

    def __init__(self, event_bus: Optional[EventBus] = None, max_events: int = 2000) -> None:
        self._event_bus: EventBus = event_bus or EventBus.get_instance()
        self._max_events: int = max(100, int(max_events))
        self._events: List[Dict[str, Any]] = []
        self._lock = RLock()

        # Very small counter set for quick health checks
        self._counters: Dict[str, int] = {
            "ai": 0,
            "trading": 0,
            "mining": 0,
            "blockchain": 0,
            "wallet": 0,
            "analytics": 0,
            "ui": 0,
            "voice": 0,
            "sentience": 0,
        }

        self._register_subscriptions()
        logger.info("TelemetryCollector initialized and subscribed to telemetry topics")

    # ------------------------------------------------------------------
    # EventBus wiring
    # ------------------------------------------------------------------
    def _register_subscriptions(self) -> None:
        """Subscribe to the core telemetry topics on the EventBus.

        Uses subscribe_sync so that we do not depend on an event loop here.
        """
        try:
            bus = self._event_bus
            if hasattr(bus, "subscribe_sync"):
                bus.subscribe_sync("ai.telemetry", self._on_ai_telemetry)
                bus.subscribe_sync("trading.telemetry", self._on_trading_telemetry)
                bus.subscribe_sync("mining.telemetry", self._on_mining_telemetry)
                bus.subscribe_sync("blockchain.telemetry", self._on_blockchain_telemetry)
                bus.subscribe_sync("wallet.telemetry", self._on_wallet_telemetry)
                bus.subscribe_sync("analytics.telemetry", self._on_analytics_telemetry)
                bus.subscribe_sync("ui.telemetry", self._on_ui_telemetry)
                bus.subscribe_sync("voice.telemetry", self._on_voice_telemetry)
                bus.subscribe_sync("sentience.telemetry", self._on_sentience_telemetry)
            else:
                # Fallback to plain subscribe if sync helper is unavailable
                bus.subscribe("ai.telemetry", self._on_ai_telemetry)
                bus.subscribe("trading.telemetry", self._on_trading_telemetry)
                bus.subscribe("mining.telemetry", self._on_mining_telemetry)
                bus.subscribe("blockchain.telemetry", self._on_blockchain_telemetry)
                bus.subscribe("wallet.telemetry", self._on_wallet_telemetry)
                bus.subscribe("analytics.telemetry", self._on_analytics_telemetry)
                bus.subscribe("ui.telemetry", self._on_ui_telemetry)
                bus.subscribe("voice.telemetry", self._on_voice_telemetry)
                bus.subscribe("sentience.telemetry", self._on_sentience_telemetry)
        except Exception as e:
            logger.error(f"Failed to register TelemetryCollector subscriptions: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the last N telemetry events (most recent last)."""
        with self._lock:
            if limit <= 0:
                return []
            return list(self._events[-limit:])

    def get_counters(self) -> Dict[str, int]:
        """Return a shallow copy of per-domain counters."""
        with self._lock:
            return dict(self._counters)

    def get_recent_domain_events(self, domain: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent events for a given logical domain (e.g. "trading")."""
        with self._lock:
            if limit <= 0:
                return []
            domain_key = str(domain).lower()
            filtered: List[Dict[str, Any]] = []
            for event in self._events:
                if not isinstance(event, dict):
                    continue
                component = str(event.get("component", "")).lower()
                if component == domain_key:
                    filtered.append(event)
            if not filtered:
                return []
            return filtered[-limit:]

    def get_recent_symbol_events(
        self,
        domain: str,
        symbol: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return recent events for a given domain filtered by symbol in metadata."""
        with self._lock:
            if limit <= 0:
                return []
            domain_key = str(domain).lower()
            target_symbol = str(symbol).upper()
            filtered: List[Dict[str, Any]] = []
            for event in self._events:
                if not isinstance(event, dict):
                    continue
                component = str(event.get("component", "")).lower()
                if component != domain_key:
                    continue
                metadata = event.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                sym = str(metadata.get("symbol", "")).upper()
                if sym != target_symbol:
                    continue
                filtered.append(event)
            if not filtered:
                return []
            return filtered[-limit:]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _record_event(self, domain: str, channel: str, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        try:
            event: Dict[str, Any] = dict(payload)
            event.setdefault("channel", channel)
            event.setdefault("component", domain)
            event.setdefault("timestamp", datetime.utcnow().isoformat())

            with self._lock:
                self._events.append(event)
                if len(self._events) > self._max_events:
                    # Keep only the most recent events
                    self._events = self._events[-self._max_events :]

                if domain in self._counters:
                    self._counters[domain] += 1
        except Exception as e:
            # Never raise from telemetry path; just log at debug level
            logger.debug(f"Error recording telemetry event on {channel}: {e}")

    # ------------------------------------------------------------------
    # Event handlers (must stay extremely lightweight)
    # ------------------------------------------------------------------
    def _on_ai_telemetry(self, payload: Any) -> None:
        self._record_event("ai", "ai.telemetry", payload)

    def _on_trading_telemetry(self, payload: Any) -> None:
        self._record_event("trading", "trading.telemetry", payload)

    def _on_mining_telemetry(self, payload: Any) -> None:
        self._record_event("mining", "mining.telemetry", payload)

    def _on_blockchain_telemetry(self, payload: Any) -> None:
        self._record_event("blockchain", "blockchain.telemetry", payload)

    def _on_wallet_telemetry(self, payload: Any) -> None:
        self._record_event("wallet", "wallet.telemetry", payload)

    def _on_analytics_telemetry(self, payload: Any) -> None:
        self._record_event("analytics", "analytics.telemetry", payload)

    def _on_ui_telemetry(self, payload: Any) -> None:
        self._record_event("ui", "ui.telemetry", payload)

    def _on_voice_telemetry(self, payload: Any) -> None:
        self._record_event("voice", "voice.telemetry", payload)

    def _on_sentience_telemetry(self, payload: Any) -> None:
        self._record_event("sentience", "sentience.telemetry", payload)
