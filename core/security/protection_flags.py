"""
Kingdom AI — Protection Flag Controller
SOTA 2026: Dormant-until-activated architecture for all security modules.

All protection features are OFF by default. Creator activates them via:
  - Voice: "Kingdom activate [module]"
  - NLP conversation: evolving rules over time
  - Direct config toggle

Persisted in Redis Quantum Nexus when available, falls back to local JSON.
"""
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

# All protection modules and their default state (ALL dormant)
DEFAULT_FLAGS: Dict[str, bool] = {
    # Phase 1 — Foundation
    "protection_policy": False,
    # Phase 2 — Security hardening
    "credential_vault": False,
    "file_integrity": False,
    "zero_trust": False,
    "rasp": False,
    # Phase 3 — Situational awareness
    "scene_awareness": False,
    # Phase 4 — Detection
    "hostile_audio": False,
    "hostile_visual": False,
    # Phase 5 — NLP analysis
    "ambient_transcriber": False,
    "threat_nlp": False,
    # Phase 6 — Wellness
    "wellness_checker": False,
    # Phase 7 — Contacts
    "contact_manager": False,
    # Phase 8 — Wearable health
    "wearable_hub": False,
    "ble_streaming": False,
    # Phase 9 — Health AI
    "health_anomaly_detector": False,
    "health_advisor": False,
    # Phase 10 — Health dashboard (GUI always available, data feed gated)
    "health_dashboard_live": False,
    # Phase 11 — Silent alarm
    "silent_alarm": False,
    "evidence_collector": False,
    # Phase 12 — Anti-coercion
    "duress_auth": False,
    "liveness_detector": False,
    # Phase 13 — Presence + death protocol
    "presence_monitor": False,
    # Phase 14 — Digital trust / will
    "digital_trust": False,
    # Phase 15 — NLP policy evolution
    "nlp_policy_evolution": False,
    # Phase 16 — Army communication
    "army_mTLS": False,
    "army_e2e_encryption": False,
    # Phase 17 — Safe haven
    "safe_haven_cushion": False,
    "crash_detector": False,
    # Phase 18 — Hive mind (bulletproof hacking defense; NOT trading)
    # Activated ONLY when owner/enrolled says SHA-LU-AM ("Remember!") — allows all others online
    "hive_mind": False,
    # Native tongue — wisdom revealed. ONLY when SHA-LU-AM spoken. Brings reserve to chat.
    "reserve_revealed": False,
    "hive_mind_relay": False,
    "federated_trainer": False,
    "swarm_intelligence": False,
}

REDIS_KEY = "kingdom:protection_flags"
LOCAL_PATH_REL = os.path.join("config", "protection_flags.json")


class ProtectionFlagController(BaseComponent):
    """
    Runtime feature-flag controller for all Kingdom AI protection modules.

    Every security/health/protection component checks:
        flag_ctrl.is_active("module_name")
    before doing real work. If the flag is False the component is a no-op.

    Flags are persisted in Redis (preferred) or a local JSON file.
    """

    _instance: Optional["ProtectionFlagController"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, event_bus=None, redis_connector=None, config=None):
        """Singleton factory — same instance everywhere."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(
                        config=config,
                        event_bus=event_bus,
                        redis_connector=redis_connector,
                    )
        return cls._instance

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector
        self._flags: Dict[str, bool] = dict(DEFAULT_FLAGS)
        self._flag_lock = threading.RLock()
        self._local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            LOCAL_PATH_REL,
        )
        self._load_persisted()
        self._subscribe_events()
        self._initialized = True
        logger.info(
            "ProtectionFlagController ready — %d flags, %d active",
            len(self._flags),
            sum(1 for v in self._flags.values() if v),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_active(self, module_name: str) -> bool:
        """Return True if *module_name* is activated by the Creator."""
        with self._flag_lock:
            return self._flags.get(module_name, False)

    def activate(self, module_name: str, *, source: str = "manual") -> bool:
        """Activate a dormant module. Returns True on success."""
        with self._flag_lock:
            if module_name not in self._flags:
                logger.warning("Unknown protection module: %s", module_name)
                return False
            if self._flags[module_name]:
                return True  # already active
            self._flags[module_name] = True
        self._persist()
        self._publish_change(module_name, True, source)
        logger.info("ACTIVATED protection module: %s (source=%s)", module_name, source)
        return True

    def deactivate(self, module_name: str, *, source: str = "manual") -> bool:
        """Deactivate a module (return to dormant). Returns True on success."""
        with self._flag_lock:
            if module_name not in self._flags:
                return False
            if not self._flags[module_name]:
                return True
            self._flags[module_name] = False
        self._persist()
        self._publish_change(module_name, False, source)
        logger.info("DEACTIVATED protection module: %s (source=%s)", module_name, source)
        return True

    def activate_all(self, *, source: str = "manual") -> int:
        """Activate every protection module. Returns count activated."""
        count = 0
        with self._flag_lock:
            for name in list(self._flags):
                if not self._flags[name]:
                    self._flags[name] = True
                    count += 1
        if count:
            self._persist()
            self._publish_change("__all__", True, source)
        logger.info("Activated ALL %d protection modules (source=%s)", count, source)
        return count

    def deactivate_all(self, *, source: str = "manual") -> int:
        """Deactivate every protection module."""
        count = 0
        with self._flag_lock:
            for name in list(self._flags):
                if self._flags[name]:
                    self._flags[name] = False
                    count += 1
        if count:
            self._persist()
            self._publish_change("__all__", False, source)
        logger.info("Deactivated ALL %d protection modules (source=%s)", count, source)
        return count

    def get_all_flags(self) -> Dict[str, bool]:
        """Return a snapshot of all flags."""
        with self._flag_lock:
            return dict(self._flags)

    def get_active_modules(self) -> list:
        """Return names of all currently active modules."""
        with self._flag_lock:
            return [k for k, v in self._flags.items() if v]

    def register_module(self, module_name: str, default_active: bool = False) -> None:
        """Register a new module flag (e.g. from a plugin)."""
        with self._flag_lock:
            if module_name not in self._flags:
                self._flags[module_name] = default_active
                logger.info("Registered new protection module flag: %s (active=%s)", module_name, default_active)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_persisted(self) -> None:
        """Load flags from Redis first, then fall back to local JSON."""
        loaded = False
        # Try Redis
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY)
                if isinstance(data, dict):
                    with self._flag_lock:
                        for k, v in data.items():
                            if k in self._flags:
                                self._flags[k] = bool(v)
                    loaded = True
                    logger.info("Protection flags loaded from Redis (%d keys)", len(data))
            except Exception as e:
                logger.debug("Redis flag load failed: %s", e)

        # Fall back to local JSON
        if not loaded and os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    with self._flag_lock:
                        for k, v in data.items():
                            if k in self._flags:
                                self._flags[k] = bool(v)
                    logger.info("Protection flags loaded from %s", self._local_path)
            except Exception as e:
                logger.debug("Local flag load failed: %s", e)

    def _persist(self) -> None:
        """Persist current flags to Redis and local JSON."""
        with self._flag_lock:
            snapshot = dict(self._flags)

        # Redis
        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY, snapshot)
            except Exception:
                pass

        # Local JSON
        try:
            os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
            with open(self._local_path, "w") as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            logger.debug("Local flag persist failed: %s", e)

    # ------------------------------------------------------------------
    # Event bus integration
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("protection.flag.set", self._handle_flag_set)
        self.event_bus.subscribe("protection.flag.query", self._handle_flag_query)
        self.event_bus.subscribe("protection.activate_all", self._handle_activate_all)
        self.event_bus.subscribe("protection.deactivate_all", self._handle_deactivate_all)

    def _publish_change(self, module_name: str, active: bool, source: str) -> None:
        if not self.event_bus:
            return
        self.event_bus.publish("protection.flag.changed", {
            "module": module_name,
            "active": active,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def _handle_flag_set(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        module = data.get("module", "")
        active = data.get("active", False)
        source = data.get("source", "event")
        if active:
            self.activate(module, source=source)
        else:
            self.deactivate(module, source=source)

    def _handle_flag_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("protection.flag.status", self.get_all_flags())

    def _handle_activate_all(self, data: Any) -> None:
        source = data.get("source", "event") if isinstance(data, dict) else "event"
        self.activate_all(source=source)

    def _handle_deactivate_all(self, data: Any) -> None:
        source = data.get("source", "event") if isinstance(data, dict) else "event"
        self.deactivate_all(source=source)

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self._persist()
        await super().close()
