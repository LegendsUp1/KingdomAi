"""
Kingdom AI — NLP Policy Evolver
SOTA 2026: Creator discusses security policies with KAI in natural language,
and the system generates/updates PolicyRule objects via LLM code generation.

Flow:
  1. Creator says: "Kingdom, if someone I don't know enters my house at night,
     I want you to activate the cameras and alert my brother"
  2. NLP Evolver parses intent via Ollama/ThothAI
  3. Generates a PolicyRule JSON from the natural language
  4. Adds rule to ProtectionPolicyStore
  5. Confirms to Creator: "Got it. I'll watch for unknown persons at home
     after 10pm and alert [brother] with camera evidence."

Dormant until protection flag "nlp_policy_evolution" is activated.
"""
import json
import logging
import re
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

# Intent patterns for policy creation
POLICY_INTENT_PATTERNS = [
    r"(?:if|when|whenever)\s+(.+?)(?:,?\s*(?:then\s+)?(?:i\s+want|please|you\s+should|activate|alert|notify|call|start|begin))\s+(.+)",
    r"(?:alert|notify|call|contact)\s+(.+?)\s+(?:if|when|whenever)\s+(.+)",
    r"(?:activate|start|enable)\s+(.+?)\s+(?:if|when|whenever)\s+(.+)",
    r"(?:add|create)\s+(?:a\s+)?(?:rule|policy)\s+(?:that|to|for)\s+(.+)",
]

# Condition keyword to module mapping
CONDITION_KEYWORDS = {
    "unknown person": ("hostile_visual", "identity.unknown.detected"),
    "stranger": ("hostile_visual", "identity.unknown.detected"),
    "intruder": ("hostile_visual", "identity.unknown.detected"),
    "gunshot": ("hostile_audio", "security.audio.gunshot"),
    "glass break": ("hostile_audio", "security.audio.glass_break"),
    "scream": ("hostile_audio", "security.audio.scream"),
    "threat": ("threat_nlp", "security.nlp.hostile_intent"),
    "coercion": ("threat_nlp", "security.nlp.coercion"),
    "fall": ("wellness_checker", "health.fall.detected"),
    "pulse lost": ("presence_monitor", "health.pulse.lost"),
    "heart rate": ("health_anomaly_detector", "health.anomaly.detected"),
    "stress": ("health_anomaly_detector", "health.anomaly.detected"),
    "night": ("scene_awareness", "scene.context.changed"),
    "home": ("scene_awareness", "scene.context.changed"),
}

# Action keyword mapping
ACTION_KEYWORDS = {
    "alert": "escalate",
    "notify": "escalate",
    "call": "escalate",
    "contact": "escalate",
    "camera": "evidence",
    "record": "evidence",
    "evidence": "evidence",
    "capture": "evidence",
    "alarm": "silent_alarm",
    "silent alarm": "silent_alarm",
    "lockdown": "lockout",
    "lock": "lockout",
    "wellness": "wellness_check",
    "check on me": "wellness_check",
    "ask if ok": "wellness_check",
}


class NLPPolicyEvolver(BaseComponent):
    """
    Translates Creator's natural language policy descriptions into
    formal PolicyRule objects for the ProtectionPolicyStore.

    Two modes:
    1. Pattern-based (always available): Regex + keyword matching
    2. LLM-powered (when Ollama available): Full natural language understanding
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in POLICY_INTENT_PATTERNS]
        self._pending_confirmations: Dict[str, Dict] = {}
        self._lock = threading.Lock()

        self._subscribe_events()
        self._initialized = True
        logger.info("NLPPolicyEvolver initialized (dormant until activated)")

    # ------------------------------------------------------------------
    # Natural language → PolicyRule
    # ------------------------------------------------------------------

    def process_policy_request(self, text: str, source: str = "voice") -> Optional[Dict]:
        """
        Parse natural language policy request and generate a PolicyRule.
        
        Returns the generated rule dict or None if parsing fails.
        """
        if not self._is_active():
            return None

        # Try pattern-based parsing first
        rule_data = self._pattern_parse(text)

        if rule_data:
            # Add to policy store
            self._add_to_policy_store(rule_data)

            # Confirm to Creator
            self._confirm_policy(rule_data, text)

            return rule_data

        # If pattern parsing fails, try LLM
        if self.event_bus:
            self._request_llm_parse(text, source)

        return None

    def _pattern_parse(self, text: str) -> Optional[Dict]:
        """Parse policy from text using regex patterns and keyword matching."""
        text_lower = text.lower()

        # Detect condition
        condition_module = ""
        condition_event = ""
        condition_desc = ""
        for keyword, (module, event) in CONDITION_KEYWORDS.items():
            if keyword in text_lower:
                condition_module = module
                condition_event = event
                condition_desc = keyword
                break

        if not condition_event:
            return None

        # Detect action
        action_type = "log"
        action_desc = ""
        for keyword, atype in ACTION_KEYWORDS.items():
            if keyword in text_lower:
                action_type = atype
                action_desc = keyword
                break

        # Detect contact name for notification actions
        contact_name = ""
        contact_match = re.search(r"(?:alert|notify|call|contact)\s+(?:my\s+)?(\w+)", text_lower)
        if contact_match:
            contact_name = contact_match.group(1)

        # Build rule
        rule_data = {
            "name": f"Custom: {condition_desc} → {action_desc or action_type}",
            "description": text[:200],
            "module": condition_module,
            "condition_type": "event_match",
            "condition_params": {"event": condition_event},
            "action_type": action_type,
            "action_params": {},
            "priority": 75,
            "active": True,
            "created_by": "nlp_evolver",
        }

        if contact_name:
            rule_data["action_params"]["notify_contact"] = contact_name
        if action_type == "evidence":
            rule_data["action_params"]["capture_video"] = True
            rule_data["action_params"]["duration_seconds"] = 300

        return rule_data

    def _request_llm_parse(self, text: str, source: str) -> None:
        """Request LLM to parse the policy from natural language."""
        if not self.event_bus:
            return

        prompt = (
            "Parse this security policy request into a JSON rule:\n"
            f"'{text}'\n\n"
            "Output ONLY valid JSON with these fields:\n"
            '{"name": "...", "description": "...", "module": "...", '
            '"condition_type": "event_match", "condition_params": {"event": "..."}, '
            '"action_type": "escalate|evidence|silent_alarm|lockout|wellness_check|log", '
            '"action_params": {}, "priority": 50-100, "active": true}\n\n'
            "Available modules: hostile_audio, hostile_visual, threat_nlp, "
            "scene_awareness, wellness_checker, presence_monitor, health_anomaly_detector\n"
            "Available events: security.audio.gunshot, security.audio.glass_break, "
            "security.audio.scream, identity.unknown.detected, security.nlp.hostile_intent, "
            "health.fall.detected, health.pulse.lost, health.anomaly.detected"
        )

        self.event_bus.publish("ai.request", {
            "text": prompt,
            "source": "nlp_policy_evolver",
            "priority": "normal",
            "context": {"original_text": text, "parse_type": "policy_rule"},
        })

    # ------------------------------------------------------------------
    # Policy store integration
    # ------------------------------------------------------------------

    def _add_to_policy_store(self, rule_data: Dict) -> None:
        """Add generated rule to ProtectionPolicyStore via event bus."""
        if self.event_bus:
            self.event_bus.publish("protection.policy.add", rule_data)

    def _confirm_policy(self, rule_data: Dict, original_text: str) -> None:
        """Confirm the policy back to Creator."""
        name = rule_data.get("name", "")
        action = rule_data.get("action_type", "")

        confirmation = f"Policy added: {name}. Action: {action}."

        if self.event_bus:
            self.event_bus.publish("voice.speak", {
                "text": confirmation,
                "priority": "normal",
                "source": "nlp_policy_evolver",
            })
            self.event_bus.publish("security.policy.nlp_created", {
                "rule": rule_data,
                "original_text": original_text,
                "confirmation": confirmation,
            })

    # ------------------------------------------------------------------
    # LLM response handling
    # ------------------------------------------------------------------

    def _handle_llm_response(self, data: Any) -> None:
        """Handle LLM response for policy parsing."""
        if not isinstance(data, dict):
            return

        source = data.get("source", "")
        if source != "nlp_policy_evolver":
            return

        response_text = data.get("text", data.get("response", ""))
        context = data.get("context", {})
        original_text = context.get("original_text", "")

        if not response_text:
            return

        # Try to extract JSON from LLM response
        try:
            json_match = re.search(r'\{[^{}]+\}', response_text, re.DOTALL)
            if json_match:
                rule_data = json.loads(json_match.group())
                rule_data["created_by"] = "nlp_evolver_llm"

                self._add_to_policy_store(rule_data)
                self._confirm_policy(rule_data, original_text)
                logger.info("LLM-generated policy rule added: %s", rule_data.get("name", ""))
        except (json.JSONDecodeError, Exception) as e:
            logger.debug("LLM policy parse failed: %s", e)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("nlp_policy_evolution")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("security.policy.nlp_request", self._handle_nlp_request)
        self.event_bus.subscribe("ai.response", self._handle_llm_response)

    def _handle_nlp_request(self, data: Any) -> None:
        if isinstance(data, dict):
            text = data.get("text", "")
            source = data.get("source", "event")
            if text:
                self.process_policy_request(text, source)

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "pending_confirmations": len(self._pending_confirmations),
        }
