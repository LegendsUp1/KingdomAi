"""
Kingdom AI — Presence Monitor
SOTA 2026: Creator presence tracking + wearable-enhanced death protocol.

Monitors Creator's ongoing presence via multiple signals:
  - Wearable heart rate (primary — loss of pulse = EMERGENCY)
  - Voice interaction frequency (secondary)
  - System interaction (mouse/keyboard)
  - Camera face detection (tertiary)

Death Protocol:
  When Creator is confirmed unresponsive (no pulse + no wellness response):
  1. Wait configurable grace period
  2. Attempt escalating wellness checks
  3. Notify emergency contacts
  4. If death confirmed → activate Digital Trust (estate mode)
     - Transfer assets to beneficiaries per ContactManager shares
     - Grant beneficiary access to system
     - Preserve all data for designated family
     - AI guides beneficiaries through asset division

Dormant until protection flag "presence_monitor" is activated.
"""
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)


class PresenceState(str, Enum):
    PRESENT = "present"           # Creator is actively present
    IDLE = "idle"                 # No interaction but vitals OK
    AWAY = "away"                 # No signals for extended period
    UNRESPONSIVE = "unresponsive" # No wellness response
    EMERGENCY = "emergency"       # Pulse lost or critical health event
    DECEASED = "deceased"         # Confirmed death (triggers estate mode)


class PresenceMonitor(BaseComponent):
    """
    Tracks Creator's presence and manages the death protocol.

    Signal hierarchy (strongest to weakest):
    1. Wearable pulse → definitively present or emergency
    2. Voice interaction → present
    3. Face on camera → present
    4. System interaction → present
    5. No signals → idle/away based on duration
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._state = PresenceState.PRESENT
        self._state_lock = threading.RLock()
        self._last_state_change = time.time()

        # Signal timestamps
        self._last_pulse: float = 0
        self._last_voice: float = 0
        self._last_face: float = 0
        self._last_interaction: float = time.time()

        # Timeouts (seconds)
        self._idle_timeout = 300       # 5 min no interaction → idle
        self._away_timeout = 1800      # 30 min no interaction → away
        self._pulse_timeout = 120      # 2 min no pulse → concern
        self._emergency_timeout = 300  # 5 min no pulse + no response → emergency
        self._death_confirmation_timeout = 900  # 15 min emergency → deceased

        # Death protocol state
        self._wellness_checks_sent = 0
        self._max_wellness_checks = 3
        self._death_protocol_timer: Optional[threading.Timer] = None

        # Monitor thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

        self._subscribe_events()
        self._initialized = True
        logger.info("PresenceMonitor initialized (dormant until activated)")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> PresenceState:
        with self._state_lock:
            return self._state

    @property
    def state_duration(self) -> float:
        return time.time() - self._last_state_change

    # ------------------------------------------------------------------
    # Signal recording
    # ------------------------------------------------------------------

    def _record_presence_signal(self, signal_type: str) -> None:
        """Record a presence signal and update state."""
        now = time.time()

        if signal_type == "pulse":
            self._last_pulse = now
        elif signal_type == "voice":
            self._last_voice = now
        elif signal_type == "face":
            self._last_face = now
        elif signal_type == "interaction":
            self._last_interaction = now

        # Any presence signal resets to PRESENT
        with self._state_lock:
            if self._state in (PresenceState.IDLE, PresenceState.AWAY):
                self._transition(PresenceState.PRESENT, f"{signal_type} detected")
            elif self._state == PresenceState.UNRESPONSIVE:
                self._transition(PresenceState.PRESENT, f"Creator responded ({signal_type})")
                self._wellness_checks_sent = 0
            elif self._state == PresenceState.EMERGENCY:
                if signal_type == "pulse":
                    self._transition(PresenceState.PRESENT, "Pulse restored!")
                    self._cancel_death_protocol()

    def _transition(self, new_state: PresenceState, reason: str = "") -> None:
        """Transition to a new presence state."""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._last_state_change = time.time()

        logger.info("Presence: %s → %s (%s)", old_state.value, new_state.value, reason)

        if self.event_bus:
            self.event_bus.publish("presence.state.changed", {
                "old_state": old_state.value,
                "new_state": new_state.value,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            })

    # ------------------------------------------------------------------
    # Monitor loop
    # ------------------------------------------------------------------

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="PresenceMonitor",
        )
        self._monitor_thread.start()
        logger.info("Presence monitoring started")

    def stop_monitoring(self) -> None:
        self._running = False
        self._cancel_death_protocol()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                if self._is_active():
                    self._evaluate_presence()
            except Exception as e:
                logger.error("Presence monitor error: %s", e)
            time.sleep(10)  # Check every 10 seconds

    def _evaluate_presence(self) -> None:
        """Evaluate current presence based on signal freshness."""
        now = time.time()

        # Most recent signal
        latest_signal = max(self._last_pulse, self._last_voice,
                           self._last_face, self._last_interaction)
        time_since_signal = now - latest_signal if latest_signal > 0 else 0

        # Pulse-specific timing
        time_since_pulse = now - self._last_pulse if self._last_pulse > 0 else float("inf")
        has_wearable = self._last_pulse > 0  # Have we ever received pulse data?

        with self._state_lock:
            current = self._state

            # === PULSE LOST CHECK (highest priority) ===
            if has_wearable and time_since_pulse > self._pulse_timeout:
                if current == PresenceState.PRESENT or current == PresenceState.IDLE:
                    self._transition(PresenceState.UNRESPONSIVE, "Pulse signal lost")
                    self._initiate_wellness_check("pulse_lost")

                elif current == PresenceState.UNRESPONSIVE:
                    if time_since_pulse > self._emergency_timeout:
                        self._transition(PresenceState.EMERGENCY, "Extended pulse loss")
                        self._initiate_death_protocol()

                elif current == PresenceState.EMERGENCY:
                    if self.state_duration > self._death_confirmation_timeout:
                        self._transition(PresenceState.DECEASED, "No recovery after extended emergency")
                        self._activate_estate_mode()

            # === NO WEARABLE — use interaction signals ===
            elif not has_wearable:
                if time_since_signal > self._away_timeout and current != PresenceState.AWAY:
                    self._transition(PresenceState.AWAY, "No signals for extended period")
                elif time_since_signal > self._idle_timeout and current == PresenceState.PRESENT:
                    self._transition(PresenceState.IDLE, "No recent interaction")

    # ------------------------------------------------------------------
    # Wellness check escalation
    # ------------------------------------------------------------------

    def _initiate_wellness_check(self, reason: str) -> None:
        """Send wellness check to Creator."""
        self._wellness_checks_sent += 1

        if self._wellness_checks_sent <= self._max_wellness_checks:
            urgency = "moderate"
            if self._wellness_checks_sent == 2:
                urgency = "urgent"
            elif self._wellness_checks_sent >= 3:
                urgency = "critical"

            if self.event_bus:
                self.event_bus.publish("wellness.check.triggered", {
                    "reason": reason,
                    "urgency": urgency,
                    "attempt": self._wellness_checks_sent,
                })

    # ------------------------------------------------------------------
    # Death protocol
    # ------------------------------------------------------------------

    def _initiate_death_protocol(self) -> None:
        """Begin death protocol countdown."""
        logger.warning("DEATH PROTOCOL INITIATED — monitoring for recovery")

        if self.event_bus:
            # Notify emergency contacts immediately
            self.event_bus.publish("security.emergency.notify_contacts", {
                "reason": "Creator may be in medical emergency — no pulse detected",
                "urgency": "critical",
            })

            # Start evidence capture
            self.event_bus.publish("security.evidence.start_capture", {
                "reason": "death_protocol",
                "duration_seconds": 1800,
            })

    def _activate_estate_mode(self) -> None:
        """Activate digital trust / estate mode after confirmed death."""
        logger.warning("ESTATE MODE ACTIVATED — transferring control to beneficiaries")

        if self.event_bus:
            self.event_bus.publish("security.estate.activate", {
                "reason": "Creator presence lost — death protocol completed",
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Notify all contacts
            self.event_bus.publish("security.emergency.notify_contacts", {
                "reason": "Kingdom AI estate mode activated — Creator is unresponsive",
                "urgency": "critical",
                "estate_mode": True,
            })

    def _cancel_death_protocol(self) -> None:
        """Cancel death protocol (Creator recovered)."""
        self._wellness_checks_sent = 0
        if self._death_protocol_timer:
            self._death_protocol_timer.cancel()
            self._death_protocol_timer = None
        logger.info("Death protocol cancelled — Creator recovered")

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("presence_monitor")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        # Presence signals
        self.event_bus.subscribe("health.hr.realtime", self._on_heartrate)
        self.event_bus.subscribe("identity.voice.enrolled", self._on_voice)
        self.event_bus.subscribe("identity.face.verified", self._on_face)
        self.event_bus.subscribe("ai.request", self._on_voice_command)
        self.event_bus.subscribe("system.interaction", self._on_interaction)

        # Wellness response
        self.event_bus.subscribe("wellness.check.response", self._on_wellness_response)
        self.event_bus.subscribe("wellness.check.no_response", self._on_wellness_no_response)

        # Flag changes
        self.event_bus.subscribe("protection.flag.changed", self._on_flag_change)

    def _on_heartrate(self, data: Any) -> None:
        if isinstance(data, dict) and data.get("heart_rate", 0) > 0:
            self._record_presence_signal("pulse")

    def _on_voice(self, data: Any) -> None:
        self._record_presence_signal("voice")

    def _on_voice_command(self, data: Any) -> None:
        self._record_presence_signal("voice")

    def _on_face(self, data: Any) -> None:
        self._record_presence_signal("face")

    def _on_interaction(self, data: Any) -> None:
        self._record_presence_signal("interaction")

    def _on_wellness_response(self, data: Any) -> None:
        if isinstance(data, dict) and data.get("ok"):
            self._record_presence_signal("voice")

    def _on_wellness_no_response(self, data: Any) -> None:
        # Escalate if already unresponsive
        self._initiate_wellness_check("no_wellness_response")

    def _on_flag_change(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        if data.get("module") in ("presence_monitor", "__all__"):
            if data.get("active"):
                self.start_monitoring()
            else:
                self.stop_monitoring()

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self.stop_monitoring()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "state_duration_seconds": round(self.state_duration),
            "last_pulse_ago": round(time.time() - self._last_pulse) if self._last_pulse else None,
            "last_voice_ago": round(time.time() - self._last_voice) if self._last_voice else None,
            "wellness_checks_sent": self._wellness_checks_sent,
        }
