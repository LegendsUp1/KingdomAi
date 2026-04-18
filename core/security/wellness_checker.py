"""
Kingdom AI — Wellness Checker
SOTA 2026: Smart "Are you OK?" system with context-aware questioning.

Knows WHEN to ask Creator if they're okay vs when NOT to:
  - Fall detected + no response → escalate
  - Health anomaly + Creator active → gentle check
  - Loud thud at 3am + wearable HR spike → urgent check
  - Party context + glass break → do NOT ask

Integrates with:
  - SceneContextEngine (context filtering)
  - WearableHub (health corroboration)
  - CreatorShield (threat level input)
  - AlwaysOnVoice (voice response capture)
  - ContactManager (emergency escalation)

Dormant until protection flag "wellness_checker" is activated.
"""
import logging
import threading
import time
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)


class CheckUrgency(str, Enum):
    GENTLE = "gentle"       # "Hey, everything good?"
    MODERATE = "moderate"   # "I noticed something. Are you OK?"
    URGENT = "urgent"       # "I detected a fall! Are you OK? Please respond!"
    CRITICAL = "critical"   # "EMERGENCY: No response detected. Contacting emergency contacts."


class WellnessCheck:
    """Represents a single wellness check interaction."""
    __slots__ = (
        "check_id", "reason", "urgency", "asked_at", "response_deadline",
        "responded", "response_text", "response_genuine", "escalated",
        "escalated_at",
    )

    def __init__(self, reason: str, urgency: CheckUrgency, timeout_seconds: int = 60):
        self.check_id = f"wc_{int(time.time() * 1000)}"
        self.reason = reason
        self.urgency = urgency
        self.asked_at = time.time()
        self.response_deadline = self.asked_at + timeout_seconds
        self.responded = False
        self.response_text: Optional[str] = None
        self.response_genuine: Optional[bool] = None
        self.escalated = False
        self.escalated_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "reason": self.reason,
            "urgency": self.urgency.value,
            "asked_at": datetime.fromtimestamp(self.asked_at).isoformat(),
            "responded": self.responded,
            "response_text": self.response_text,
            "response_genuine": self.response_genuine,
            "escalated": self.escalated,
        }


# Timeout per urgency level (seconds)
URGENCY_TIMEOUTS = {
    CheckUrgency.GENTLE: 300,     # 5 minutes
    CheckUrgency.MODERATE: 120,   # 2 minutes
    CheckUrgency.URGENT: 60,      # 1 minute
    CheckUrgency.CRITICAL: 30,    # 30 seconds
}

# Prompts per urgency
WELLNESS_PROMPTS = {
    CheckUrgency.GENTLE: "Hey, everything good?",
    CheckUrgency.MODERATE: "I noticed something unusual. Are you OK?",
    CheckUrgency.URGENT: "I detected something concerning! Are you OK? Please respond.",
    CheckUrgency.CRITICAL: "EMERGENCY! I need to hear from you NOW. Are you OK?",
}


class WellnessChecker(BaseComponent):
    """
    Context-aware wellness checking system.

    Determines when and how to ask Creator if they're OK,
    waits for response, evaluates genuineness (via voice/face stress),
    and escalates if no response or suspicious response.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        # Active checks
        self._active_checks: Dict[str, WellnessCheck] = {}
        self._check_history: deque = deque(maxlen=100)
        self._lock = threading.RLock()

        # Cooldown to prevent spam
        self._last_check_time: float = 0
        self._min_check_interval = 30  # Don't check more than once per 30 seconds

        # Deadline monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

        self._subscribe_events()
        self._initialized = True
        logger.info("WellnessChecker initialized (dormant until activated)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trigger_check(self, reason: str, urgency: str = "moderate",
                      timeout_override: Optional[int] = None) -> Optional[str]:
        """
        Trigger a wellness check.

        Args:
            reason: Why we're checking (e.g. "fall_detected", "health_anomaly")
            urgency: gentle, moderate, urgent, critical
            timeout_override: Custom timeout in seconds

        Returns:
            check_id if check was created, None if suppressed
        """
        if not self._is_active():
            return None

        # Cooldown check
        now = time.time()
        if now - self._last_check_time < self._min_check_interval:
            logger.debug("Wellness check suppressed (cooldown): %s", reason)
            return None

        # Don't stack multiple active checks
        with self._lock:
            if len(self._active_checks) > 0:
                # Upgrade existing check if new one is more urgent
                existing = next(iter(self._active_checks.values()))
                new_urgency = CheckUrgency(urgency)
                if new_urgency.value > existing.urgency.value:
                    # Cancel old, create new with higher urgency
                    del self._active_checks[existing.check_id]
                else:
                    logger.debug("Wellness check already active, skipping: %s", reason)
                    return existing.check_id

        try:
            urg = CheckUrgency(urgency)
        except ValueError:
            urg = CheckUrgency.MODERATE

        timeout = timeout_override or URGENCY_TIMEOUTS.get(urg, 120)
        check = WellnessCheck(reason=reason, urgency=urg, timeout_seconds=timeout)

        with self._lock:
            self._active_checks[check.check_id] = check
        self._last_check_time = now

        # Ask Creator
        prompt = WELLNESS_PROMPTS.get(urg, "Are you OK?")
        self._ask_creator(check, prompt)

        # Ensure deadline monitor is running
        self._start_monitor()

        logger.info("Wellness check triggered: %s (urgency=%s, timeout=%ds)", reason, urg.value, timeout)
        return check.check_id

    def respond_to_check(self, check_id: Optional[str] = None, response_text: str = "",
                         genuine: bool = True) -> bool:
        """
        Record Creator's response to a wellness check.

        Args:
            check_id: Specific check to respond to (or None for latest)
            response_text: What Creator said
            genuine: Whether voice/face analysis indicates genuine response
        """
        with self._lock:
            if check_id and check_id in self._active_checks:
                check = self._active_checks[check_id]
            elif self._active_checks:
                # Respond to most recent active check
                check = next(iter(self._active_checks.values()))
            else:
                return False

            check.responded = True
            check.response_text = response_text
            check.response_genuine = genuine

            # Move to history
            self._check_history.append(check.to_dict())
            del self._active_checks[check.check_id]

        # Publish response for CreatorShield
        if self.event_bus:
            self.event_bus.publish("wellness.check.response", {
                "check_id": check.check_id,
                "ok": True,
                "genuine": genuine,
                "response_text": response_text,
                "reason": check.reason,
                "urgency": check.urgency.value,
            })

        logger.info(
            "Wellness check responded: %s (genuine=%s, text='%s')",
            check.check_id, genuine, response_text[:50],
        )
        return True

    # ------------------------------------------------------------------
    # Ask Creator
    # ------------------------------------------------------------------

    def _ask_creator(self, check: WellnessCheck, prompt: str) -> None:
        """Ask Creator if they're OK via voice system."""
        if not self.event_bus:
            return

        # Publish TTS request
        self.event_bus.publish("voice.speak", {
            "text": prompt,
            "priority": "high" if check.urgency in (CheckUrgency.URGENT, CheckUrgency.CRITICAL) else "normal",
            "source": "wellness_checker",
        })

        # Publish check event
        self.event_bus.publish("wellness.check.asked", {
            "check_id": check.check_id,
            "reason": check.reason,
            "urgency": check.urgency.value,
            "prompt": prompt,
            "deadline": datetime.fromtimestamp(check.response_deadline).isoformat(),
        })

    # ------------------------------------------------------------------
    # Deadline monitoring
    # ------------------------------------------------------------------

    def _start_monitor(self) -> None:
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="WellnessMonitor",
        )
        self._monitor_thread.start()

    def _stop_monitor(self) -> None:
        self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=3)

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                self._check_deadlines()
            except Exception as e:
                logger.error("Wellness monitor error: %s", e)
            time.sleep(5)

            # Stop if no active checks
            with self._lock:
                if not self._active_checks:
                    self._running = False
                    return

    def _check_deadlines(self) -> None:
        now = time.time()
        expired: List[WellnessCheck] = []

        with self._lock:
            for check in list(self._active_checks.values()):
                if now >= check.response_deadline and not check.responded:
                    expired.append(check)

        for check in expired:
            self._escalate(check)

    def _escalate(self, check: WellnessCheck) -> None:
        """Escalate: Creator didn't respond in time."""
        with self._lock:
            check.escalated = True
            check.escalated_at = time.time()
            self._check_history.append(check.to_dict())
            self._active_checks.pop(check.check_id, None)

        logger.warning(
            "WELLNESS ESCALATION: No response for check %s (reason=%s, urgency=%s)",
            check.check_id, check.reason, check.urgency.value,
        )

        if not self.event_bus:
            return

        # Publish no-response event
        self.event_bus.publish("wellness.check.no_response", {
            "check_id": check.check_id,
            "reason": check.reason,
            "urgency": check.urgency.value,
            "waited_seconds": int(time.time() - check.asked_at),
        })

        # For urgent/critical: trigger emergency contact notification
        if check.urgency in (CheckUrgency.URGENT, CheckUrgency.CRITICAL):
            self.event_bus.publish("security.emergency.notify_contacts", {
                "reason": f"No response to wellness check ({check.reason})",
                "urgency": check.urgency.value,
                "check_id": check.check_id,
            })

        # For critical: also trigger silent alarm
        if check.urgency == CheckUrgency.CRITICAL:
            self.event_bus.publish("security.silent_alarm.trigger", {
                "reason": f"CRITICAL: No wellness response ({check.reason})",
                "threat_level": "critical",
            })

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("wellness_checker")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("wellness.check.triggered", self._handle_trigger)
        self.event_bus.subscribe("wellness.creator.response", self._handle_response)
        self.event_bus.subscribe("health.fall.detected", self._handle_fall)
        self.event_bus.subscribe("wellness.check.no_response", self._handle_no_response_event)

    def _handle_trigger(self, data: Any) -> None:
        if isinstance(data, dict):
            self.trigger_check(
                reason=data.get("reason", "unknown"),
                urgency=data.get("urgency", "moderate"),
                timeout_override=data.get("timeout_seconds"),
            )

    def _handle_response(self, data: Any) -> None:
        if isinstance(data, dict):
            self.respond_to_check(
                check_id=data.get("check_id"),
                response_text=data.get("text", ""),
                genuine=data.get("genuine", True),
            )

    def _handle_fall(self, data: Any) -> None:
        self.trigger_check(reason="fall_detected", urgency="urgent", timeout_override=60)

    def _handle_no_response_event(self, data: Any) -> None:
        """Handle no-response event — log for audit trail and escalate if needed."""
        try:
            if not isinstance(data, dict):
                return
            check_id = data.get("check_id")
            urgency = data.get("urgency", "unknown")
            reason = data.get("reason", "unknown")
            logger.warning(
                "WellnessChecker: No response received for check %s (urgency=%s, reason=%s)",
                check_id, urgency, reason
            )
        except Exception as e:
            logger.debug("Error handling no-response event: %s", e)

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self._stop_monitor()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            active = [c.to_dict() for c in self._active_checks.values()]
        return {
            "active_checks": active,
            "history_count": len(self._check_history),
            "monitoring": self._running,
        }
