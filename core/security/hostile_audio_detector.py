"""
Kingdom AI — Hostile Audio Detector
SOTA 2026: YAMNet sound event classification + threat keyword spotting + voice emotion.

Processes ambient audio to detect:
  - Gunshots, glass breaking, screams, explosions
  - Aggressive speech patterns
  - Unusual sounds in context (via SceneContextEngine)

Uses Google YAMNet (TF Hub) when available, falls back to spectral heuristics.
Dormant until protection flag "hostile_audio" is activated.
"""
import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from base_component import BaseComponent

logger = logging.getLogger(__name__)

# Try importing audio processing libraries
HAS_NUMPY = False
HAS_LIBROSA = False
HAS_YAMNET = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    pass

try:
    import tensorflow_hub as hub
    HAS_YAMNET = True
except ImportError:
    pass

# YAMNet threat class labels (subset of 521 AudioSet classes)
THREAT_SOUND_CLASSES = {
    "Gunshot, gunfire": ("gunshot", 0.95),
    "Machine gun": ("gunshot", 0.95),
    "Explosion": ("explosion", 0.90),
    "Glass": ("glass_break", 0.70),
    "Shatter": ("glass_break", 0.85),
    "Breaking": ("glass_break", 0.70),
    "Scream": ("scream", 0.80),
    "Screaming": ("scream", 0.80),
    "Yell": ("aggression", 0.60),
    "Shout": ("aggression", 0.55),
    "Crying, sobbing": ("distress", 0.50),
    "Alarm": ("alarm", 0.70),
    "Siren": ("siren", 0.60),
    "Dog": ("dog_bark", 0.30),
    "Knock": ("knock", 0.25),
    "Door": ("door", 0.20),
}

# Spectral feature thresholds for heuristic detection
GUNSHOT_ENERGY_THRESHOLD_DB = -10   # Sudden loud impulse
GLASS_BREAK_CENTROID_HZ = 6000     # High-frequency content
SCREAM_PITCH_HZ = 1500             # High fundamental frequency


class HostileAudioDetector(BaseComponent):
    """
    Real-time audio threat detection for Creator protection.

    Subscribes to raw audio chunks from AlwaysOnVoice or dedicated mic feed.
    Classifies sounds and publishes threat events to CreatorShield.

    Sound events are context-weighted by SceneContextEngine:
      - Gunshot at shooting_range → suppressed
      - Gunshot at home_quiet → CRITICAL
      - Glass break at party → suppressed
      - Glass break at home at 3am → ELEVATED
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        # YAMNet model (loaded lazily)
        self._yamnet_model = None
        self._yamnet_class_names: List[str] = []

        # Detection state
        self._recent_detections: deque = deque(maxlen=100)
        self._lock = threading.Lock()

        # Audio buffer for processing
        self._audio_buffer: deque = deque(maxlen=16000 * 5)  # 5 seconds at 16kHz
        self._sample_rate = 16000

        self._subscribe_events()
        self._initialized = True
        logger.info(
            "HostileAudioDetector initialized (YAMNet=%s, librosa=%s, numpy=%s)",
            HAS_YAMNET, HAS_LIBROSA, HAS_NUMPY,
        )

    # ------------------------------------------------------------------
    # YAMNet loading
    # ------------------------------------------------------------------

    def _ensure_yamnet(self) -> bool:
        """Lazily load YAMNet model."""
        if self._yamnet_model is not None:
            return True
        if not HAS_YAMNET:
            return False
        try:
            self._yamnet_model = hub.load("https://tfhub.dev/google/yamnet/1")
            # Load class names
            import csv
            import io
            class_map_path = self._yamnet_model.class_map_path().numpy().decode("utf-8")
            with open(class_map_path) as f:
                reader = csv.DictReader(f)
                self._yamnet_class_names = [row["display_name"] for row in reader]
            logger.info("YAMNet loaded: %d sound classes", len(self._yamnet_class_names))
            return True
        except Exception as e:
            logger.warning("YAMNet load failed: %s — using heuristic detection", e)
            return False

    # ------------------------------------------------------------------
    # Audio processing
    # ------------------------------------------------------------------

    def process_audio_chunk(self, audio_data: Any, sample_rate: int = 16000) -> List[Dict]:
        """
        Process an audio chunk and return list of detected threats.
        
        Args:
            audio_data: numpy array of float32 audio samples
            sample_rate: sample rate in Hz
            
        Returns:
            List of detection dicts: {type, confidence, timestamp}
        """
        if not self._is_active():
            return []

        if not HAS_NUMPY or audio_data is None:
            return []

        detections: List[Dict] = []

        # Ensure float32 numpy array
        if not isinstance(audio_data, np.ndarray):
            try:
                audio_data = np.array(audio_data, dtype=np.float32)
            except Exception:
                return []

        # Try YAMNet classification first
        if self._ensure_yamnet():
            yamnet_detections = self._classify_yamnet(audio_data, sample_rate)
            detections.extend(yamnet_detections)

        # Always run heuristic detection as supplementary
        heuristic_detections = self._classify_heuristic(audio_data, sample_rate)
        detections.extend(heuristic_detections)

        # Deduplicate by type (keep highest confidence)
        unique: Dict[str, Dict] = {}
        for d in detections:
            dtype = d["type"]
            if dtype not in unique or d["confidence"] > unique[dtype]["confidence"]:
                unique[dtype] = d
        detections = list(unique.values())

        # Record and publish
        for det in detections:
            self._record_detection(det)
            self._publish_detection(det)

        return detections

    def _classify_yamnet(self, audio: Any, sr: int) -> List[Dict]:
        """Classify audio using YAMNet."""
        detections: List[Dict] = []
        try:
            # Resample to 16kHz if needed
            if sr != 16000 and HAS_LIBROSA:
                audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)

            # Run YAMNet
            scores, embeddings, spectrogram = self._yamnet_model(audio)
            scores_np = scores.numpy()

            # Check each frame's top predictions against threat classes
            for frame_scores in scores_np:
                top_indices = frame_scores.argsort()[-5:][::-1]
                for idx in top_indices:
                    if idx < len(self._yamnet_class_names):
                        class_name = self._yamnet_class_names[idx]
                        score = float(frame_scores[idx])
                        if class_name in THREAT_SOUND_CLASSES and score > 0.3:
                            threat_type, base_weight = THREAT_SOUND_CLASSES[class_name]
                            confidence = score * base_weight
                            if confidence > 0.25:
                                detections.append({
                                    "type": threat_type,
                                    "confidence": round(confidence, 3),
                                    "source": "yamnet",
                                    "class_name": class_name,
                                    "raw_score": round(score, 3),
                                    "timestamp": datetime.utcnow().isoformat(),
                                })
        except Exception as e:
            logger.debug("YAMNet classification error: %s", e)

        return detections

    def _classify_heuristic(self, audio: Any, sr: int) -> List[Dict]:
        """Heuristic threat detection using spectral features."""
        detections: List[Dict] = []
        if not HAS_NUMPY:
            return detections

        try:
            # RMS energy in dB
            rms = float(np.sqrt(np.mean(audio ** 2)))
            energy_db = 20 * np.log10(max(rms, 1e-10))

            # Sudden loud impulse → possible gunshot
            if energy_db > GUNSHOT_ENERGY_THRESHOLD_DB:
                # Check if it's a sharp transient (short attack time)
                abs_audio = np.abs(audio)
                peak_idx = int(np.argmax(abs_audio))
                # Check rise time: if peak is in first 10% of chunk
                if peak_idx < len(audio) * 0.1 and energy_db > -5:
                    detections.append({
                        "type": "gunshot",
                        "confidence": min(0.6, (energy_db + 15) / 20),
                        "source": "heuristic_impulse",
                        "energy_db": round(energy_db, 1),
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            # Spectral centroid → high = glass breaking
            if HAS_LIBROSA:
                centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)
                mean_centroid = float(np.mean(centroid))
                if mean_centroid > GLASS_BREAK_CENTROID_HZ and energy_db > -25:
                    detections.append({
                        "type": "glass_break",
                        "confidence": min(0.5, (mean_centroid - GLASS_BREAK_CENTROID_HZ) / 4000),
                        "source": "heuristic_spectral",
                        "centroid_hz": round(mean_centroid, 0),
                        "timestamp": datetime.utcnow().isoformat(),
                    })

                # Pitch detection for screams
                pitches, magnitudes = librosa.piptrack(y=audio, sr=sr)
                pitch_mask = magnitudes > np.median(magnitudes) * 2
                if pitch_mask.any():
                    high_pitches = pitches[pitch_mask]
                    high_pitches = high_pitches[high_pitches > 0]
                    if len(high_pitches) > 0:
                        mean_pitch = float(np.mean(high_pitches))
                        if mean_pitch > SCREAM_PITCH_HZ and energy_db > -20:
                            detections.append({
                                "type": "scream",
                                "confidence": min(0.5, (mean_pitch - SCREAM_PITCH_HZ) / 2000),
                                "source": "heuristic_pitch",
                                "pitch_hz": round(mean_pitch, 0),
                                "timestamp": datetime.utcnow().isoformat(),
                            })

        except Exception as e:
            logger.debug("Heuristic audio classification error: %s", e)

        return detections

    # ------------------------------------------------------------------
    # Detection management
    # ------------------------------------------------------------------

    def _record_detection(self, detection: Dict) -> None:
        with self._lock:
            self._recent_detections.append(detection)

    def _publish_detection(self, detection: Dict) -> None:
        if not self.event_bus:
            return

        dtype = detection.get("type", "unknown")
        event_map = {
            "gunshot": "security.audio.gunshot",
            "glass_break": "security.audio.glass_break",
            "scream": "security.audio.scream",
            "explosion": "security.audio.gunshot",
            "aggression": "security.audio.aggression",
            "distress": "security.audio.threat_detected",
            "alarm": "security.audio.threat_detected",
        }
        event_type = event_map.get(dtype, "security.audio.threat_detected")
        detection["severity"] = self._get_severity(dtype)

        self.event_bus.publish(event_type, detection)

        # Also publish generic audio classification for scene engine
        self.event_bus.publish("audio.classification", {
            "label": dtype,
            "confidence": detection.get("confidence", 0),
        })

        logger.info(
            "Audio threat detected: %s (conf=%.2f, source=%s)",
            dtype, detection.get("confidence", 0), detection.get("source", "?"),
        )

    def _get_severity(self, threat_type: str) -> int:
        severity_map = {
            "gunshot": 40,
            "explosion": 40,
            "scream": 30,
            "aggression": 30,
            "glass_break": 20,
            "distress": 20,
            "alarm": 15,
            "siren": 10,
        }
        return severity_map.get(threat_type, 15)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("hostile_audio")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("audio.raw.chunk", self._handle_raw_audio)
        self.event_bus.subscribe("security.audio.analyze", self._handle_analyze_request)

    def _handle_raw_audio(self, data: Any) -> None:
        if isinstance(data, dict):
            audio = data.get("audio")
            sr = data.get("sample_rate", 16000)
            self.process_audio_chunk(audio, sr)
        elif HAS_NUMPY and isinstance(data, np.ndarray):
            self.process_audio_chunk(data)

    def _handle_analyze_request(self, data: Any) -> None:
        if isinstance(data, dict):
            audio = data.get("audio")
            sr = data.get("sample_rate", 16000)
            results = self.process_audio_chunk(audio, sr)
            if self.event_bus:
                self.event_bus.publish("security.audio.analysis_result", {"detections": results})

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            recent = list(self._recent_detections)[-10:]
        return {
            "yamnet_available": HAS_YAMNET,
            "yamnet_loaded": self._yamnet_model is not None,
            "librosa_available": HAS_LIBROSA,
            "recent_detections": recent,
            "total_detections": len(self._recent_detections),
        }
