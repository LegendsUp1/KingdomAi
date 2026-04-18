"""
Kingdom AI — Creator Shield (Master Orchestrator)
SOTA 2026: Fuses ALL security signals, decides threat level, dispatches actions.

This is the central hub that:
  1. Subscribes to ALL security-related events
  2. Consults ProtectionFlagController (dormant check)
  3. Consults ProtectionPolicyStore (rule evaluation)
  4. Consults SceneContextEngine (context-aware threat multiplier)
  5. Aggregates multi-signal threat assessment
  6. Dispatches appropriate actions (wellness check, silent alarm, evidence capture, etc.)

All logic is gated behind protection flags — if flags are off, this is a no-op.
"""
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple

from base_component import BaseComponent

logger = logging.getLogger(__name__)


class ThreatLevel(IntEnum):
    """Graduated threat levels."""
    NORMAL = 0
    NOTICE = 10
    ELEVATED = 20
    HIGH = 30
    CRITICAL = 40
    EMERGENCY = 50


# Human-readable labels
THREAT_LABELS = {
    ThreatLevel.NORMAL: "NORMAL",
    ThreatLevel.NOTICE: "NOTICE",
    ThreatLevel.ELEVATED: "ELEVATED",
    ThreatLevel.HIGH: "HIGH",
    ThreatLevel.CRITICAL: "CRITICAL",
    ThreatLevel.EMERGENCY: "EMERGENCY",
}


class SignalAccumulator:
    """
    Tracks incoming security signals within a rolling time window.
    Used for multi-signal convergence detection (e.g. voice stress + facial fear
    within 30 seconds = duress).
    """

    def __init__(self, window_seconds: int = 60):
        self._window = window_seconds
        self._signals: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._lock = threading.Lock()

    def record(self, signal_name: str, value: Any = None) -> None:
        with self._lock:
            self._signals[signal_name].append((time.time(), value))

    def count_recent(self, signal_name: str, window: Optional[int] = None) -> int:
        cutoff = time.time() - (window or self._window)
        with self._lock:
            q = self._signals.get(signal_name, deque())
            return sum(1 for ts, _ in q if ts >= cutoff)

    def has_signal(self, signal_name: str, window: Optional[int] = None) -> bool:
        return self.count_recent(signal_name, window) > 0

    def converging(self, signal_names: List[str], min_count: int = 1, window: Optional[int] = None) -> bool:
        """Return True if at least `min_count` distinct signals fired within `window`."""
        present = sum(1 for s in signal_names if self.has_signal(s, window))
        return present >= min_count

    def clear(self, signal_name: Optional[str] = None) -> None:
        with self._lock:
            if signal_name:
                self._signals.pop(signal_name, None)
            else:
                self._signals.clear()


class CreatorShield(BaseComponent):
    """
    Master security orchestrator for Kingdom AI Creator version.

    Subscribes to events from:
      - hostile_audio_detector, hostile_visual_detector
      - ambient_transcriber, threat_nlp_analyzer
      - voice_stress_analyzer, facial_stress_analyzer
      - scene_context_engine
      - wellness_checker
      - wearable_hub (health vitals)
      - user_identity (biometric events)
      - presence_monitor

    Dispatches actions to:
      - wellness_checker ("Are you OK?")
      - silent_alarm (notify army / emergency contacts)
      - evidence_collector (capture audio/video/logs)
      - duress_auth (lockout, duress PIN)
      - contact_manager (notify emergency contacts)
    """

    _instance: Optional["CreatorShield"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, event_bus=None, redis_connector=None, config=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config=config, event_bus=event_bus, redis_connector=redis_connector)
        return cls._instance

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        # Current threat assessment
        self._threat_level = ThreatLevel.NORMAL
        self._threat_lock = threading.RLock()
        self._last_assessment: Optional[Dict] = None

        # Signal accumulator for multi-signal convergence
        self.signals = SignalAccumulator(window_seconds=60)

        # Lazy references to sibling modules (set during initialization)
        self._flag_ctrl = None
        self._policy_store = None
        self._scene_engine = None

        self._subscribe_events()
        self._initialized = True
        logger.info("CreatorShield master orchestrator initialized (dormant until flags activated)")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def threat_level(self) -> ThreatLevel:
        with self._threat_lock:
            return self._threat_level

    @property
    def threat_label(self) -> str:
        return THREAT_LABELS.get(self.threat_level, "UNKNOWN")

    # ------------------------------------------------------------------
    # Lazy module references
    # ------------------------------------------------------------------

    def _get_flag_ctrl(self):
        if self._flag_ctrl is None:
            try:
                from core.security.protection_flags import ProtectionFlagController
                self._flag_ctrl = ProtectionFlagController.get_instance()
            except Exception:
                pass
        return self._flag_ctrl

    def _get_policy_store(self):
        if self._policy_store is None:
            try:
                from core.security.protection_policy import ProtectionPolicyStore
                self._policy_store = ProtectionPolicyStore.get_instance()
            except Exception:
                pass
        return self._policy_store

    def _get_scene_engine(self):
        if self._scene_engine is None:
            if self.event_bus and hasattr(self.event_bus, "get_component"):
                self._scene_engine = self.event_bus.get_component("scene_context_engine", silent=True)
        return self._scene_engine

    # ------------------------------------------------------------------
    # Core: assess threat from incoming signal
    # ------------------------------------------------------------------

    def _assess(self, signal_name: str, base_severity: ThreatLevel, event_data: Any = None) -> None:
        """
        Record a signal, apply context multiplier, evaluate policies,
        compute new aggregate threat level, and dispatch actions if needed.
        """
        # Gate: check if any protection is active
        fc = self._get_flag_ctrl()
        if fc and not any(fc.is_active(m) for m in fc.get_all_flags()):
            return  # ALL dormant — no-op

        # 1. Record signal
        self.signals.record(signal_name, event_data)

        # 2. Context multiplier from scene engine
        multiplier = 1.0
        scene = self._get_scene_engine()
        if scene and hasattr(scene, "threat_multiplier"):
            try:
                multiplier = scene.threat_multiplier()
            except Exception:
                multiplier = 1.0

        adjusted_severity = min(ThreatLevel.EMERGENCY, int(base_severity * multiplier))

        # 3. Multi-signal convergence boost
        duress_signals = ["voice_stress_high", "facial_fear", "hostile_nlp", "hr_spike", "hrv_crash"]
        if self.signals.converging(duress_signals, min_count=2, window=30):
            adjusted_severity = max(adjusted_severity, ThreatLevel.HIGH)
        if self.signals.converging(duress_signals, min_count=3, window=30):
            adjusted_severity = max(adjusted_severity, ThreatLevel.CRITICAL)

        # 4. Update aggregate threat level (max of current and new)
        new_level = ThreatLevel(adjusted_severity)
        with self._threat_lock:
            previous = self._threat_level
            self._threat_level = max(self._threat_level, new_level)

        # 5. Evaluate policy rules
        ps = self._get_policy_store()
        if ps:
            context = {"threat_level": int(self._threat_level), "scene_multiplier": multiplier}
            ps.evaluate_event(signal_name, event_data, context)

        # 6. Publish threat update
        assessment = {
            "threat_level": int(self._threat_level),
            "threat_label": THREAT_LABELS.get(self._threat_level, "UNKNOWN"),
            "signal": signal_name,
            "adjusted_severity": adjusted_severity,
            "multiplier": multiplier,
            "previous_level": int(previous),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._last_assessment = assessment
        if self.event_bus:
            self.event_bus.publish("security.threat.updated", assessment)

        # 7. Dispatch actions based on threat level
        if self._threat_level >= ThreatLevel.CRITICAL and previous < ThreatLevel.CRITICAL:
            self._dispatch_critical(assessment)
        elif self._threat_level >= ThreatLevel.HIGH and previous < ThreatLevel.HIGH:
            self._dispatch_high(assessment)
        elif self._threat_level >= ThreatLevel.ELEVATED and previous < ThreatLevel.ELEVATED:
            self._dispatch_elevated(assessment)

        logger.info(
            "CreatorShield: signal=%s severity=%d→%d (×%.1f) threat=%s",
            signal_name, int(base_severity), adjusted_severity, multiplier,
            THREAT_LABELS.get(self._threat_level, "?"),
        )

    def reduce_threat(self, to_level: ThreatLevel = ThreatLevel.NORMAL, reason: str = "") -> None:
        """Manually or automatically reduce threat level (e.g. Creator confirmed OK)."""
        with self._threat_lock:
            prev = self._threat_level
            self._threat_level = to_level
        if self.event_bus:
            self.event_bus.publish("security.threat.reduced", {
                "from": int(prev),
                "to": int(to_level),
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            })
        logger.info("Threat reduced: %s → %s (%s)", THREAT_LABELS.get(prev), THREAT_LABELS.get(to_level), reason)

    # ------------------------------------------------------------------
    # Action dispatchers
    # ------------------------------------------------------------------

    def _dispatch_elevated(self, assessment: Dict) -> None:
        """ELEVATED: heighten monitoring, no direct action yet."""
        if self.event_bus:
            self.event_bus.publish("security.action.heighten_monitoring", assessment)

    def _dispatch_high(self, assessment: Dict) -> None:
        """HIGH: ask Creator if OK, start background evidence capture."""
        if self.event_bus:
            self.event_bus.publish("wellness.check.triggered", {
                "reason": assessment.get("signal", "unknown"),
                "urgency": "high",
                "timestamp": assessment.get("timestamp"),
            })
            self.event_bus.publish("security.evidence.start_capture", {
                "reason": assessment.get("signal", "unknown"),
                "duration_seconds": 300,
            })

    def _dispatch_critical(self, assessment: Dict) -> None:
        """CRITICAL: silent alarm + evidence capture + notify emergency contacts."""
        if self.event_bus:
            self.event_bus.publish("security.silent_alarm.trigger", {
                "threat_level": "critical",
                "assessment": assessment,
            })
            self.event_bus.publish("security.evidence.start_capture", {
                "reason": "critical_threat",
                "duration_seconds": 600,
            })
            self.event_bus.publish("security.emergency.notify_contacts", {
                "threat_level": "critical",
                "assessment": assessment,
            })

    # ------------------------------------------------------------------
    # Event subscriptions — each handler records a signal + assesses
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return

        # Audio threats
        self.event_bus.subscribe("security.audio.threat_detected", self._on_audio_threat)
        self.event_bus.subscribe("security.audio.gunshot", self._on_gunshot)
        self.event_bus.subscribe("security.audio.glass_break", self._on_glass_break)
        self.event_bus.subscribe("security.audio.scream", self._on_scream)
        self.event_bus.subscribe("security.audio.aggression", self._on_aggression)

        # Visual threats
        self.event_bus.subscribe("security.visual.weapon_detected", self._on_weapon)
        self.event_bus.subscribe("security.visual.unknown_person", self._on_unknown_person)
        self.event_bus.subscribe("identity.unknown.detected", self._on_unknown_person)
        self.event_bus.subscribe("security.visual.person_surge", self._on_person_surge)

        # Crash detection
        self.event_bus.subscribe("security.crash.detected", self._on_crash)

        # NLP threats
        self.event_bus.subscribe("security.nlp.hostile_intent", self._on_hostile_nlp)
        self.event_bus.subscribe("security.nlp.coercion", self._on_coercion)

        # Voice / facial stress
        self.event_bus.subscribe("security.voice.stress_high", self._on_voice_stress)
        self.event_bus.subscribe("security.face.fear_detected", self._on_facial_fear)

        # Wearable health
        self.event_bus.subscribe("health.anomaly.detected", self._on_health_anomaly)
        self.event_bus.subscribe("health.pulse.lost", self._on_pulse_lost)
        self.event_bus.subscribe("health.fall.detected", self._on_fall)
        self.event_bus.subscribe("health.hr.realtime", self._on_hr_realtime)

        # Wellness response
        self.event_bus.subscribe("wellness.check.response", self._on_wellness_response)

        # Scene context changes
        self.event_bus.subscribe("scene.context.changed", self._on_scene_changed)

        # Identity events
        self.event_bus.subscribe("identity.command.rejected", self._on_auth_rejected)

        # File integrity
        self.event_bus.subscribe("security.file_integrity.violation", self._on_file_tamper)

    # --- Audio handlers ---
    def _on_audio_threat(self, data: Any) -> None:
        severity = ThreatLevel.ELEVATED
        if isinstance(data, dict):
            severity = ThreatLevel(min(50, data.get("severity", 20)))
        self._assess("audio_threat", severity, data)

    def _on_gunshot(self, data: Any) -> None:
        self._assess("gunshot", ThreatLevel.CRITICAL, data)

    def _on_glass_break(self, data: Any) -> None:
        self._assess("glass_break", ThreatLevel.ELEVATED, data)

    def _on_scream(self, data: Any) -> None:
        self._assess("scream", ThreatLevel.HIGH, data)

    def _on_aggression(self, data: Any) -> None:
        self._assess("aggression", ThreatLevel.HIGH, data)

    # --- Visual handlers ---
    def _on_weapon(self, data: Any) -> None:
        self._assess("weapon_detected", ThreatLevel.EMERGENCY, data)

    def _on_unknown_person(self, data: Any) -> None:
        self._assess("unknown_person", ThreatLevel.NOTICE, data)

    def _on_person_surge(self, data: Any) -> None:
        self._assess("person_surge", ThreatLevel.ELEVATED, data)

    # --- Crash handler ---
    def _on_crash(self, data: Any) -> None:
        self._assess("crash_detected", ThreatLevel.CRITICAL, data)

    # --- NLP handlers ---
    def _on_hostile_nlp(self, data: Any) -> None:
        self.signals.record("hostile_nlp", data)
        self._assess("hostile_nlp", ThreatLevel.HIGH, data)

    def _on_coercion(self, data: Any) -> None:
        self.signals.record("hostile_nlp", data)
        self._assess("coercion", ThreatLevel.CRITICAL, data)

    # --- Stress handlers ---
    def _on_voice_stress(self, data: Any) -> None:
        self.signals.record("voice_stress_high", data)
        self._assess("voice_stress_high", ThreatLevel.ELEVATED, data)

    def _on_facial_fear(self, data: Any) -> None:
        self.signals.record("facial_fear", data)
        self._assess("facial_fear", ThreatLevel.ELEVATED, data)

    # --- Health handlers ---
    def _on_health_anomaly(self, data: Any) -> None:
        severity = ThreatLevel.NOTICE
        if isinstance(data, dict) and data.get("severity") == "high":
            severity = ThreatLevel.HIGH
        self._assess("health_anomaly", severity, data)

    def _on_pulse_lost(self, data: Any) -> None:
        self._assess("pulse_lost", ThreatLevel.EMERGENCY, data)

    def _on_fall(self, data: Any) -> None:
        self._assess("fall_detected", ThreatLevel.HIGH, data)

    def _on_hr_realtime(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        hr = data.get("heart_rate", 0)
        if hr > 0 and (hr < 40 or hr > 160):
            self.signals.record("hr_spike", data)
            self._assess("hr_anomaly", ThreatLevel.ELEVATED, data)

    # --- Wellness response ---
    def _on_wellness_response(self, data: Any) -> None:
        if isinstance(data, dict):
            if data.get("ok") and data.get("genuine"):
                self.reduce_threat(ThreatLevel.NORMAL, reason="Creator confirmed OK (genuine)")
            elif data.get("ok") and not data.get("genuine"):
                # Said "I'm fine" but voice/face says otherwise — possible duress
                self.signals.record("suspicious_ok", data)
                self._assess("suspicious_wellness_response", ThreatLevel.HIGH, data)

    # --- Scene changes ---
    def _on_scene_changed(self, data: Any) -> None:
        # When scene changes, re-evaluate: if moving to safe context, allow threat reduction
        if isinstance(data, dict):
            new_scene = data.get("scene_type", "")
            if new_scene in ("party", "social_gathering", "shooting_range"):
                # Don't auto-reduce, but clear some signal counters
                self.signals.clear("glass_break")
                self.signals.clear("unknown_person")
                logger.info("Scene changed to %s — cleared contextual signals", new_scene)

    # --- File integrity ---
    def _on_file_tamper(self, data: Any) -> None:
        self._assess("file_tampered", ThreatLevel.HIGH, data)

    # --- Auth rejected ---
    def _on_auth_rejected(self, data: Any) -> None:
        self.signals.record("auth_rejected", data)
        count = self.signals.count_recent("auth_rejected", window=600)
        if count >= 5:
            self._assess("repeated_auth_failure", ThreatLevel.CRITICAL, data)
        elif count >= 3:
            self._assess("auth_failure_cluster", ThreatLevel.HIGH, data)

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self.signals.clear()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "threat_level": int(self.threat_level),
            "threat_label": self.threat_label,
            "last_assessment": self._last_assessment,
            "active_signals": {
                name: len(q) for name, q in self.signals._signals.items() if q
            },
        }
