"""
Kingdom AI — Protection Policy Store
SOTA 2026: Evolving rule store for security policies.

Rules can be:
  - Static (hardcoded defaults)
  - NLP-generated (Creator discusses policy with KAI, code generator produces rule)
  - Time-based (activate after certain conditions)

Each rule has: id, name, description, condition, action, priority, active, created_at.
Persisted in Redis / local JSON. Integrates with ProtectionFlagController.
"""
import json
import logging
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

REDIS_KEY = "kingdom:protection_policies"
LOCAL_PATH_REL = os.path.join("config", "protection_policies.json")


class PolicyRule:
    """A single security policy rule."""

    __slots__ = (
        "rule_id", "name", "description", "module", "condition_type",
        "condition_params", "action_type", "action_params", "priority",
        "active", "created_at", "created_by", "last_triggered",
        "trigger_count",
    )

    def __init__(
        self,
        name: str,
        description: str = "",
        module: str = "",
        condition_type: str = "always",
        condition_params: Optional[Dict] = None,
        action_type: str = "log",
        action_params: Optional[Dict] = None,
        priority: int = 50,
        active: bool = True,
        rule_id: Optional[str] = None,
        created_by: str = "system",
    ):
        self.rule_id = rule_id or str(uuid.uuid4())[:12]
        self.name = name
        self.description = description
        self.module = module
        self.condition_type = condition_type
        self.condition_params = condition_params or {}
        self.action_type = action_type
        self.action_params = action_params or {}
        self.priority = priority
        self.active = active
        self.created_at = datetime.utcnow().isoformat()
        self.created_by = created_by
        self.last_triggered: Optional[str] = None
        self.trigger_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "module": self.module,
            "condition_type": self.condition_type,
            "condition_params": self.condition_params,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "priority": self.priority,
            "active": self.active,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyRule":
        rule = cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            module=data.get("module", ""),
            condition_type=data.get("condition_type", "always"),
            condition_params=data.get("condition_params", {}),
            action_type=data.get("action_type", "log"),
            action_params=data.get("action_params", {}),
            priority=data.get("priority", 50),
            active=data.get("active", True),
            rule_id=data.get("rule_id"),
            created_by=data.get("created_by", "system"),
        )
        rule.created_at = data.get("created_at", rule.created_at)
        rule.last_triggered = data.get("last_triggered")
        rule.trigger_count = data.get("trigger_count", 0)
        return rule


# Built-in default policies (always present, can be deactivated)
_DEFAULT_POLICIES: List[Dict[str, Any]] = [
    {
        "rule_id": "default_lockout",
        "name": "Failed Auth Lockout",
        "description": "Lock system after 5 failed biometric attempts in 10 minutes",
        "module": "duress_auth",
        "condition_type": "threshold",
        "condition_params": {"event": "identity.command.rejected", "count": 5, "window_seconds": 600},
        "action_type": "lockout",
        "action_params": {"duration_seconds": 300, "notify_silent_alarm": True},
        "priority": 90,
        "active": True,
        "created_by": "system",
    },
    {
        "rule_id": "default_unknown_person",
        "name": "Unknown Person Alert",
        "description": "Alert when unknown person detected and scene is not social gathering",
        "module": "hostile_visual",
        "condition_type": "compound",
        "condition_params": {
            "all": [
                {"event": "identity.unknown.detected"},
                {"not": {"scene_context": ["party", "social_gathering", "public"]}},
            ]
        },
        "action_type": "escalate",
        "action_params": {"level": "elevated", "check_creator_ok": True},
        "priority": 70,
        "active": True,
        "created_by": "system",
    },
    {
        "rule_id": "default_pulse_lost",
        "name": "Pulse Lost Emergency",
        "description": "Immediate emergency escalation when wearable detects loss of pulse",
        "module": "presence_monitor",
        "condition_type": "event_match",
        "condition_params": {"event": "health.pulse.lost"},
        "action_type": "emergency",
        "action_params": {"contact_emergency_list": True, "preserve_evidence": True},
        "priority": 100,
        "active": True,
        "created_by": "system",
    },
    {
        "rule_id": "default_duress_voice",
        "name": "Voice Duress Detection",
        "description": "Trigger silent alarm when voice stress + facial fear + hostile NLP converge",
        "module": "duress_auth",
        "condition_type": "multi_signal",
        "condition_params": {
            "signals": ["voice_stress_high", "facial_fear", "hostile_nlp"],
            "min_signals": 2,
            "window_seconds": 30,
        },
        "action_type": "silent_alarm",
        "action_params": {"capture_evidence": True, "notify_army": True},
        "priority": 95,
        "active": True,
        "created_by": "system",
    },
    {
        "rule_id": "default_fall_detect",
        "name": "Fall Detection Response",
        "description": "Ask Creator if OK after fall detected; escalate if no response in 60s",
        "module": "wellness_checker",
        "condition_type": "event_match",
        "condition_params": {"event": "health.fall.detected"},
        "action_type": "wellness_check",
        "action_params": {"timeout_seconds": 60, "escalate_on_no_response": True},
        "priority": 85,
        "active": True,
        "created_by": "system",
    },
]


class ProtectionPolicyStore(BaseComponent):
    """
    Manages evolving security policy rules for Kingdom AI.

    Rules can be added/modified/removed at runtime via:
      - Event bus commands
      - NLP code generator (Creator discusses → LLM produces rule JSON)
      - Direct API

    Evaluation of rules is done by the CreatorShield orchestrator,
    which calls evaluate_event() on each incoming security event.
    """

    _instance: Optional["ProtectionPolicyStore"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, event_bus=None, redis_connector=None, config=None):
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
        self._rules: Dict[str, PolicyRule] = {}
        self._rules_lock = threading.RLock()
        self._action_handlers: Dict[str, Callable] = {}
        self._local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            LOCAL_PATH_REL,
        )
        self._load_defaults()
        self._load_persisted()
        self._subscribe_events()
        self._initialized = True
        logger.info(
            "ProtectionPolicyStore ready — %d rules (%d active)",
            len(self._rules),
            sum(1 for r in self._rules.values() if r.active),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_rule(self, rule: PolicyRule, *, persist: bool = True) -> str:
        """Add or update a policy rule. Returns rule_id."""
        with self._rules_lock:
            self._rules[rule.rule_id] = rule
        if persist:
            self._persist()
        if self.event_bus:
            self.event_bus.publish("protection.policy.added", rule.to_dict())
        logger.info("Policy rule added: %s (%s)", rule.name, rule.rule_id)
        return rule.rule_id

    def remove_rule(self, rule_id: str) -> bool:
        with self._rules_lock:
            if rule_id in self._rules:
                removed = self._rules.pop(rule_id)
                self._persist()
                if self.event_bus:
                    self.event_bus.publish("protection.policy.removed", {"rule_id": rule_id, "name": removed.name})
                logger.info("Policy rule removed: %s", rule_id)
                return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        with self._rules_lock:
            rule = self._rules.get(rule_id)
            if rule:
                rule.active = True
                self._persist()
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        with self._rules_lock:
            rule = self._rules.get(rule_id)
            if rule:
                rule.active = False
                self._persist()
                return True
        return False

    def get_rule(self, rule_id: str) -> Optional[PolicyRule]:
        with self._rules_lock:
            return self._rules.get(rule_id)

    def get_all_rules(self) -> List[Dict[str, Any]]:
        with self._rules_lock:
            return [r.to_dict() for r in sorted(self._rules.values(), key=lambda r: -r.priority)]

    def get_active_rules(self, module: Optional[str] = None) -> List[PolicyRule]:
        """Return active rules, optionally filtered by module."""
        with self._rules_lock:
            rules = [r for r in self._rules.values() if r.active]
            if module:
                rules = [r for r in rules if r.module == module or r.module == ""]
            return sorted(rules, key=lambda r: -r.priority)

    def register_action_handler(self, action_type: str, handler: Callable) -> None:
        """Register a callable that executes a specific action_type."""
        self._action_handlers[action_type] = handler
        logger.debug("Registered action handler for: %s", action_type)

    def evaluate_event(self, event_type: str, event_data: Any, context: Optional[Dict] = None) -> List[Dict]:
        """
        Evaluate all active rules against an incoming event.
        Returns list of triggered actions.

        Called by CreatorShield or other orchestrators when security events arrive.
        """
        triggered: List[Dict] = []
        active_rules = self.get_active_rules()

        for rule in active_rules:
            if self._matches_condition(rule, event_type, event_data, context):
                rule.trigger_count += 1
                rule.last_triggered = datetime.utcnow().isoformat()
                action = {
                    "rule_id": rule.rule_id,
                    "rule_name": rule.name,
                    "action_type": rule.action_type,
                    "action_params": rule.action_params,
                    "priority": rule.priority,
                    "timestamp": rule.last_triggered,
                }
                triggered.append(action)
                # Execute registered handler if present
                handler = self._action_handlers.get(rule.action_type)
                if handler:
                    try:
                        handler(action, event_data, context)
                    except Exception as e:
                        logger.error("Action handler %s failed: %s", rule.action_type, e)
                # Publish action event
                if self.event_bus:
                    self.event_bus.publish("protection.policy.triggered", action)

        return triggered

    # ------------------------------------------------------------------
    # Condition matching
    # ------------------------------------------------------------------

    def _matches_condition(self, rule: PolicyRule, event_type: str, event_data: Any, context: Optional[Dict]) -> bool:
        """Check if a rule's condition matches the current event + context."""
        ct = rule.condition_type
        cp = rule.condition_params

        if ct == "always":
            return True

        if ct == "event_match":
            return cp.get("event", "") == event_type

        if ct == "threshold":
            # Threshold conditions are evaluated externally (signal accumulator)
            # Here we just check if the event matches
            return cp.get("event", "") == event_type

        if ct == "compound":
            # Compound conditions are complex — simplified match here
            all_conds = cp.get("all", [])
            for cond in all_conds:
                if isinstance(cond, dict):
                    if "event" in cond and cond["event"] != event_type:
                        return False
            return True

        if ct == "multi_signal":
            # Multi-signal matching is handled by signal accumulator
            return False  # Don't match directly, need accumulator

        return False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_defaults(self) -> None:
        """Load hardcoded default policies."""
        for pdata in _DEFAULT_POLICIES:
            rule = PolicyRule.from_dict(pdata)
            self._rules[rule.rule_id] = rule

    def _load_persisted(self) -> None:
        loaded = False
        # Try Redis
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY)
                if isinstance(data, list):
                    for rd in data:
                        rule = PolicyRule.from_dict(rd)
                        self._rules[rule.rule_id] = rule
                    loaded = True
                    logger.info("Protection policies loaded from Redis (%d)", len(data))
            except Exception as e:
                logger.debug("Redis policy load failed: %s", e)

        # Fall back to local JSON
        if not loaded and os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for rd in data:
                        rule = PolicyRule.from_dict(rd)
                        self._rules[rule.rule_id] = rule
                    logger.info("Protection policies loaded from %s (%d)", self._local_path, len(data))
            except Exception as e:
                logger.debug("Local policy load failed: %s", e)

    def _persist(self) -> None:
        with self._rules_lock:
            snapshot = [r.to_dict() for r in self._rules.values()]

        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY, snapshot)
            except Exception:
                pass

        try:
            os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
            with open(self._local_path, "w") as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            logger.debug("Local policy persist failed: %s", e)

    # ------------------------------------------------------------------
    # Event bus integration
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("protection.policy.add", self._handle_add_rule)
        self.event_bus.subscribe("protection.policy.remove", self._handle_remove_rule)
        self.event_bus.subscribe("protection.policy.enable", self._handle_enable_rule)
        self.event_bus.subscribe("protection.policy.disable", self._handle_disable_rule)
        self.event_bus.subscribe("protection.policy.query", self._handle_query)
        self.event_bus.subscribe("protection.policy.evaluate", self._handle_evaluate)

    def _handle_add_rule(self, data: Any) -> None:
        if isinstance(data, dict):
            rule = PolicyRule.from_dict(data)
            self.add_rule(rule)

    def _handle_remove_rule(self, data: Any) -> None:
        if isinstance(data, dict):
            self.remove_rule(data.get("rule_id", ""))

    def _handle_enable_rule(self, data: Any) -> None:
        if isinstance(data, dict):
            self.enable_rule(data.get("rule_id", ""))

    def _handle_disable_rule(self, data: Any) -> None:
        if isinstance(data, dict):
            self.disable_rule(data.get("rule_id", ""))

    def _handle_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("protection.policy.list", self.get_all_rules())

    def _handle_evaluate(self, data: Any) -> None:
        if isinstance(data, dict):
            event_type = data.get("event_type", "")
            event_data = data.get("event_data")
            context = data.get("context")
            self.evaluate_event(event_type, event_data, context)

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self._persist()
        await super().close()
