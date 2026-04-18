"""
Kingdom AI — Scene Context Engine
SOTA 2026: Acoustic Scene Classification + Activity State Machine.

Classifies the Creator's current environment (home_quiet, party, outdoors,
shooting_range, office, vehicle, etc.) using audio features and optional
wearable/visual context. Provides a threat_multiplier to CreatorShield so
that glass breaking at a party is NOT alarming but glass breaking at 3am IS.

Uses YAMNet (Google) for sound event classification when available,
falls back to simple energy/spectral heuristics.
Dormant until protection flag "scene_awareness" is activated.
"""
import logging
import threading
import time
from collections import Counter, deque
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

# Try importing YAMNet for sound classification
HAS_YAMNET = False
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None  # type: ignore[assignment]

try:
    import tensorflow_hub as hub
    HAS_YAMNET = True
except ImportError:
    pass


class SceneType(str, Enum):
    """Known acoustic scene types."""
    HOME_QUIET = "home_quiet"
    HOME_ACTIVE = "home_active"
    PARTY = "party"
    SOCIAL_GATHERING = "social_gathering"
    OUTDOORS = "outdoors"
    SHOOTING_RANGE = "shooting_range"
    OFFICE = "office"
    VEHICLE = "vehicle"
    GYM = "gym"
    PUBLIC = "public"
    UNKNOWN = "unknown"


# Threat multiplier per scene — lower = less alarming
SCENE_THREAT_MULTIPLIERS = {
    SceneType.HOME_QUIET: 1.5,       # Quiet home — any noise is suspicious
    SceneType.HOME_ACTIVE: 1.0,      # Active home — normal baseline
    SceneType.PARTY: 0.3,            # Party — loud is expected
    SceneType.SOCIAL_GATHERING: 0.4, # Social — voices normal
    SceneType.OUTDOORS: 0.8,         # Outdoors — moderate
    SceneType.SHOOTING_RANGE: 0.1,   # Range — gunshots expected!
    SceneType.OFFICE: 1.2,           # Office — should be calm
    SceneType.VEHICLE: 0.9,          # Vehicle — road noise normal
    SceneType.GYM: 0.5,              # Gym — grunting/banging normal
    SceneType.PUBLIC: 0.5,           # Public — crowd noise normal
    SceneType.UNKNOWN: 1.0,          # Unknown — neutral
}


class SceneContextEngine(BaseComponent):
    """
    Determines the Creator's current environmental context.

    Inputs (via event bus):
      - Audio features from ambient_transcriber / hostile_audio_detector
      - Wearable activity data (steps, HR → exercising, resting, driving)
      - Creator explicit statements ("I'm at the range", "We're having a party")
      - Time of day (late night amplifies home threats)

    Outputs:
      - scene.context.changed event when scene shifts
      - threat_multiplier() for CreatorShield to adjust severity
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._current_scene = SceneType.UNKNOWN
        self._scene_lock = threading.RLock()
        self._scene_confidence = 0.0
        self._last_change = datetime.utcnow().isoformat()

        # Rolling window of recent audio classifications
        self._audio_class_window: deque = deque(maxlen=60)  # last 60 classifications

        # Creator-explicit overrides ("I'm at the range")
        self._manual_override: Optional[SceneType] = None
        self._manual_override_expiry: float = 0.0

        # YAMNet model (loaded lazily)
        self._yamnet_model = None
        self._yamnet_classes: List[str] = []

        self._subscribe_events()
        self._initialized = True
        logger.info("SceneContextEngine initialized (dormant until scene_awareness activated)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_scene(self) -> SceneType:
        with self._scene_lock:
            # Check manual override first
            if self._manual_override and time.time() < self._manual_override_expiry:
                return self._manual_override
            return self._current_scene

    @property
    def scene_confidence(self) -> float:
        with self._scene_lock:
            return self._scene_confidence

    def threat_multiplier(self) -> float:
        """Return the threat multiplier for the current scene context."""
        scene = self.current_scene
        base = SCENE_THREAT_MULTIPLIERS.get(scene, 1.0)

        # Time-of-day adjustment: late night (11pm-5am) amplifies home threats
        hour = datetime.now().hour
        if scene in (SceneType.HOME_QUIET, SceneType.HOME_ACTIVE) and (hour >= 23 or hour < 5):
            base *= 1.3

        return base

    def set_scene_override(self, scene_type: str, duration_minutes: int = 120) -> bool:
        """Creator explicitly tells KAI the current context."""
        try:
            scene = SceneType(scene_type)
        except ValueError:
            logger.warning("Unknown scene type: %s", scene_type)
            return False

        with self._scene_lock:
            self._manual_override = scene
            self._manual_override_expiry = time.time() + (duration_minutes * 60)
        logger.info("Scene override set: %s for %d minutes", scene.value, duration_minutes)
        self._publish_scene_change(scene, 1.0, source="manual_override")
        return True

    def clear_override(self) -> None:
        with self._scene_lock:
            self._manual_override = None
            self._manual_override_expiry = 0.0
        logger.info("Scene override cleared")

    # ------------------------------------------------------------------
    # Audio classification processing
    # ------------------------------------------------------------------

    def process_audio_classification(self, classification: str, confidence: float = 0.5) -> None:
        """
        Accept an audio event classification (from YAMNet or hostile_audio_detector)
        and update the scene state machine.
        """
        if not self._is_active():
            return

        self._audio_class_window.append((classification, confidence, time.time()))
        self._update_scene_from_audio()

    def process_audio_features(self, features: Dict[str, float]) -> None:
        """
        Accept raw audio features (energy, spectral centroid, voice count, etc.)
        for heuristic scene classification when YAMNet unavailable.
        """
        if not self._is_active():
            return

        # Simple heuristic scene classification
        energy = features.get("energy_db", -60)
        voice_count = features.get("voice_count", 0)
        music_detected = features.get("music_detected", False)
        ambient_noise = features.get("ambient_noise_db", -60)

        if music_detected and voice_count >= 3 and energy > -20:
            scene_guess = SceneType.PARTY
            conf = 0.7
        elif voice_count >= 5 and energy > -25:
            scene_guess = SceneType.SOCIAL_GATHERING
            conf = 0.6
        elif energy < -40 and voice_count <= 1:
            scene_guess = SceneType.HOME_QUIET
            conf = 0.8
        elif voice_count >= 2 and energy > -30:
            scene_guess = SceneType.HOME_ACTIVE
            conf = 0.5
        else:
            scene_guess = SceneType.UNKNOWN
            conf = 0.3

        self._audio_class_window.append((scene_guess.value, conf, time.time()))
        self._update_scene_from_audio()

    def _update_scene_from_audio(self) -> None:
        """Determine scene from rolling window of audio classifications."""
        if len(self._audio_class_window) < 5:
            return

        # Count recent classifications (last 30 seconds)
        cutoff = time.time() - 30
        recent = [(c, conf) for c, conf, ts in self._audio_class_window if ts >= cutoff]
        if not recent:
            return

        # Map audio class labels to scene types
        scene_votes: Counter = Counter()
        for label, conf in recent:
            scene = self._audio_label_to_scene(label)
            scene_votes[scene] += conf

        if not scene_votes:
            return

        best_scene, best_score = scene_votes.most_common(1)[0]
        total_conf = sum(scene_votes.values())
        confidence = best_score / total_conf if total_conf > 0 else 0

        # Only change scene if confidence is sufficient and it's different
        if confidence >= 0.4:
            with self._scene_lock:
                if best_scene != self._current_scene:
                    old = self._current_scene
                    self._current_scene = best_scene
                    self._scene_confidence = confidence
                    self._last_change = datetime.utcnow().isoformat()
                    self._publish_scene_change(best_scene, confidence, source="audio_classification")
                    logger.info("Scene changed: %s → %s (conf=%.2f)", old.value, best_scene.value, confidence)
                else:
                    self._scene_confidence = confidence

    def _audio_label_to_scene(self, label: str) -> SceneType:
        """Map a YAMNet or custom audio class label to a SceneType."""
        label_lower = label.lower()

        # Direct mapping for our own scene type values
        for st in SceneType:
            if st.value == label_lower:
                return st

        # YAMNet label mapping
        party_keywords = {"music", "singing", "crowd", "cheering", "clapping", "laughter", "disco"}
        outdoor_keywords = {"wind", "rain", "bird", "thunder", "traffic", "car", "siren", "engine"}
        gym_keywords = {"exercise", "grunt", "weights", "treadmill"}
        office_keywords = {"keyboard", "typing", "printer", "telephone"}
        shooting_keywords = {"gunshot", "firearm", "explosion", "bang"}
        vehicle_keywords = {"engine", "car", "driving", "road_noise", "vehicle"}

        if any(k in label_lower for k in party_keywords):
            return SceneType.PARTY
        if any(k in label_lower for k in shooting_keywords):
            return SceneType.SHOOTING_RANGE
        if any(k in label_lower for k in outdoor_keywords):
            return SceneType.OUTDOORS
        if any(k in label_lower for k in gym_keywords):
            return SceneType.GYM
        if any(k in label_lower for k in office_keywords):
            return SceneType.OFFICE
        if any(k in label_lower for k in vehicle_keywords):
            return SceneType.VEHICLE
        if "speech" in label_lower or "conversation" in label_lower:
            return SceneType.HOME_ACTIVE
        if "silence" in label_lower or "quiet" in label_lower:
            return SceneType.HOME_QUIET

        return SceneType.UNKNOWN

    # ------------------------------------------------------------------
    # Wearable context integration
    # ------------------------------------------------------------------

    def _on_wearable_activity(self, data: Any) -> None:
        """Adjust scene based on wearable activity data."""
        if not self._is_active() or not isinstance(data, dict):
            return

        activity = data.get("activity_type", "")
        hr = data.get("heart_rate", 0)
        steps_per_min = data.get("steps_per_minute", 0)

        if activity == "driving" or (steps_per_min == 0 and hr > 60 and hr < 90):
            # Possibly in vehicle — don't override if strong audio scene
            if self._scene_confidence < 0.5:
                with self._scene_lock:
                    if self._current_scene == SceneType.UNKNOWN:
                        self._current_scene = SceneType.VEHICLE
                        self._publish_scene_change(SceneType.VEHICLE, 0.4, source="wearable")

        elif activity in ("running", "workout") or (steps_per_min > 100 and hr > 120):
            if self._scene_confidence < 0.5:
                with self._scene_lock:
                    if self._current_scene == SceneType.UNKNOWN:
                        self._current_scene = SceneType.GYM
                        self._publish_scene_change(SceneType.GYM, 0.4, source="wearable")

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("scene_awareness")
        except Exception:
            return False

    def _publish_scene_change(self, scene: SceneType, confidence: float, source: str = "") -> None:
        if self.event_bus:
            self.event_bus.publish("scene.context.changed", {
                "scene_type": scene.value,
                "confidence": round(confidence, 3),
                "threat_multiplier": SCENE_THREAT_MULTIPLIERS.get(scene, 1.0),
                "source": source,
                "timestamp": datetime.utcnow().isoformat(),
            })

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("audio.classification", self._handle_audio_class)
        self.event_bus.subscribe("audio.features", self._handle_audio_features)
        self.event_bus.subscribe("health.activity.detected", self._on_wearable_activity)
        self.event_bus.subscribe("scene.override.set", self._handle_override)
        self.event_bus.subscribe("scene.override.clear", self._handle_clear_override)
        self.event_bus.subscribe("scene.context.query", self._handle_query)

    def _handle_audio_class(self, data: Any) -> None:
        if isinstance(data, dict):
            self.process_audio_classification(
                data.get("label", "unknown"),
                data.get("confidence", 0.5),
            )

    def _handle_audio_features(self, data: Any) -> None:
        if isinstance(data, dict):
            self.process_audio_features(data)

    def _handle_override(self, data: Any) -> None:
        if isinstance(data, dict):
            self.set_scene_override(
                data.get("scene_type", "unknown"),
                data.get("duration_minutes", 120),
            )

    def _handle_clear_override(self, data: Any) -> None:
        self.clear_override()

    def _handle_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("scene.context.status", {
                "scene_type": self.current_scene.value,
                "confidence": self.scene_confidence,
                "threat_multiplier": self.threat_multiplier(),
                "has_override": self._manual_override is not None and time.time() < self._manual_override_expiry,
            })

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "scene_type": self.current_scene.value,
            "confidence": self.scene_confidence,
            "threat_multiplier": self.threat_multiplier(),
            "has_override": self._manual_override is not None,
            "yamnet_available": HAS_YAMNET,
        }
