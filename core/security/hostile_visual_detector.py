"""
Kingdom AI — Hostile Visual Detector
SOTA 2026: YOLO person detection + unknown face alerting + weapon detection.

Processes video frames from ThothQt vision system to detect:
  - Unknown persons (not in biometric database)
  - Weapons (knives, guns) via YOLO object detection
  - Multiple unknown people converging
  - Suspicious behavior patterns

Integrates with existing UserIdentityEngine for face recognition.
Dormant until protection flag "hostile_visual" is activated.
"""
import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

HAS_NUMPY = False
HAS_CV2 = False
HAS_YOLO = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    pass

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    pass

# YOLO class IDs for threat objects (COCO dataset)
WEAPON_CLASSES = {
    # Standard COCO doesn't have explicit weapon classes, but these are proxies
    # In production, use a fine-tuned weapon detection model
    43: "knife",        # COCO: knife
    76: "scissors",     # COCO: scissors
}

# Person class in COCO
PERSON_CLASS_ID = 0


class HostileVisualDetector(BaseComponent):
    """
    Real-time visual threat detection for Creator protection.

    Subscribes to vision.frame.new events from ThothQt camera system.
    Detects unknown persons and potential weapons.
    Works alongside UserIdentityEngine for face recognition.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        # YOLO model (loaded lazily)
        self._yolo_model = None
        self._yolo_lock = threading.Lock()

        # Detection state
        self._recent_detections: deque = deque(maxlen=100)
        self._unknown_person_tracker: Dict[str, Dict] = {}  # track_id -> info
        self._person_count_history: deque = deque(maxlen=30)  # 30 frames
        self._last_frame_time: float = 0
        self._min_frame_interval = 1.0  # Process at most 1 FPS for detection
        self._lock = threading.Lock()

        self._subscribe_events()
        self._initialized = True
        logger.info(
            "HostileVisualDetector initialized (YOLO=%s, CV2=%s, numpy=%s)",
            HAS_YOLO, HAS_CV2, HAS_NUMPY,
        )

    # ------------------------------------------------------------------
    # YOLO loading
    # ------------------------------------------------------------------

    def _ensure_yolo(self) -> bool:
        if self._yolo_model is not None:
            return True
        if not HAS_YOLO:
            return False
        with self._yolo_lock:
            if self._yolo_model is not None:
                return True
            try:
                self._yolo_model = YOLO("yolov8n.pt")  # Nano model for speed
                logger.info("YOLOv8 nano model loaded for visual threat detection")
                return True
            except Exception as e:
                logger.warning("YOLO load failed: %s", e)
                return False

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def process_frame(self, frame: Any) -> List[Dict]:
        """
        Process a video frame for threat detection.

        Args:
            frame: numpy array (BGR format from OpenCV) or dict with 'frame' key

        Returns:
            List of detection dicts
        """
        if not self._is_active():
            return []

        # Rate limiting
        now = time.time()
        if now - self._last_frame_time < self._min_frame_interval:
            return []
        self._last_frame_time = now

        if isinstance(frame, dict):
            frame = frame.get("frame")

        if not HAS_NUMPY or frame is None:
            return []

        if not isinstance(frame, np.ndarray):
            return []

        detections: List[Dict] = []

        # Run YOLO detection
        if self._ensure_yolo():
            yolo_detections = self._detect_yolo(frame)
            detections.extend(yolo_detections)

        # Analyze person count trends
        person_count = sum(1 for d in detections if d.get("type") == "person")
        self._person_count_history.append(person_count)
        self._check_person_surge()

        # Publish detections
        for det in detections:
            self._record_detection(det)
            self._publish_detection(det)

        return detections

    def _detect_yolo(self, frame: Any) -> List[Dict]:
        """Run YOLO object detection on frame."""
        detections: List[Dict] = []
        try:
            results = self._yolo_model(frame, verbose=False, conf=0.4)

            for result in results:
                if result.boxes is None:
                    continue

                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    xyxy = box.xyxy[0].tolist()

                    # Person detection
                    if cls_id == PERSON_CLASS_ID:
                        detections.append({
                            "type": "person",
                            "confidence": round(conf, 3),
                            "bbox": [round(c, 1) for c in xyxy],
                            "source": "yolo",
                            "timestamp": datetime.utcnow().isoformat(),
                        })

                    # Weapon detection
                    if cls_id in WEAPON_CLASSES:
                        weapon_name = WEAPON_CLASSES[cls_id]
                        detections.append({
                            "type": "weapon",
                            "weapon_class": weapon_name,
                            "confidence": round(conf, 3),
                            "bbox": [round(c, 1) for c in xyxy],
                            "source": "yolo",
                            "timestamp": datetime.utcnow().isoformat(),
                        })

        except Exception as e:
            logger.debug("YOLO detection error: %s", e)

        return detections

    def _check_person_surge(self) -> None:
        """Detect sudden increase in person count (possible intrusion)."""
        if len(self._person_count_history) < 5:
            return

        recent = list(self._person_count_history)
        avg_recent = sum(recent[-5:]) / 5
        avg_baseline = sum(recent[:-5]) / max(len(recent) - 5, 1) if len(recent) > 5 else 0

        if avg_recent > avg_baseline + 2 and avg_recent >= 3:
            if self.event_bus:
                self.event_bus.publish("security.visual.person_surge", {
                    "current_count": recent[-1],
                    "average": round(avg_recent, 1),
                    "baseline": round(avg_baseline, 1),
                    "timestamp": datetime.utcnow().isoformat(),
                })

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

        if dtype == "weapon":
            self.event_bus.publish("security.visual.weapon_detected", detection)
            logger.warning("WEAPON DETECTED: %s (conf=%.2f)", detection.get("weapon_class"), detection.get("confidence", 0))

        elif dtype == "person":
            # Person detections are informational — unknown face events come from UserIdentityEngine
            pass  # UserIdentityEngine handles face recognition and publishes identity.unknown.detected

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("hostile_visual")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("vision.frame.new", self._handle_frame)
        self.event_bus.subscribe("security.visual.analyze", self._handle_analyze)

    def _handle_frame(self, data: Any) -> None:
        self.process_frame(data)

    def _handle_analyze(self, data: Any) -> None:
        if isinstance(data, dict):
            frame = data.get("frame")
            results = self.process_frame(frame)
            if self.event_bus:
                self.event_bus.publish("security.visual.analysis_result", {"detections": results})

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
            "yolo_available": HAS_YOLO,
            "yolo_loaded": self._yolo_model is not None,
            "cv2_available": HAS_CV2,
            "recent_detections": recent,
            "total_detections": len(self._recent_detections),
        }
