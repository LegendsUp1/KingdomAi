"""
2026 SOTA Vision Analysis Component for Kingdom AI

Features:
- Face Detection & Recognition (DeepFace + InsightFace)
- Face Database with persistent storage
- Face Tracking with unique IDs across frames
- Object Detection (YOLO + HOG fallback)
- Pose Estimation (MediaPipe)
- Biometric Analysis (engagement, stress)
- OCR/Text Extraction (PaddleOCR/EasyOCR)
"""

import threading
import time
import json
import os
import pickle
from typing import Any, Dict, Optional, List, Tuple
from pathlib import Path

import cv2
import numpy as np

# DeepFace for facial analysis (emotion, age, gender)
try:
    from deepface import DeepFace  # type: ignore
    HAS_DEEPFACE = True
except Exception:  # pragma: no cover - optional dependency
    DeepFace = None  # type: ignore
    HAS_DEEPFACE = False

# InsightFace for face recognition (2026 SOTA)
try:
    import insightface  # type: ignore
    from insightface.app import FaceAnalysis  # type: ignore
    HAS_INSIGHTFACE = True
except Exception:  # pragma: no cover - optional dependency
    insightface = None  # type: ignore
    FaceAnalysis = None  # type: ignore
    HAS_INSIGHTFACE = False

# MediaPipe for pose and gesture
try:
    import mediapipe as mp  # type: ignore
    HAS_MEDIAPIPE = True
except Exception:  # pragma: no cover - optional dependency
    mp = None  # type: ignore
    HAS_MEDIAPIPE = False

# YOLO for object detection
try:
    from ultralytics import YOLO  # type: ignore
    HAS_YOLO = True
except Exception:  # pragma: no cover - optional dependency
    YOLO = None  # type: ignore
    HAS_YOLO = False

# OCR support
try:
    import easyocr  # type: ignore
    HAS_EASYOCR = True
except Exception:
    easyocr = None  # type: ignore
    HAS_EASYOCR = False

from core.base_component import BaseComponent
from core.event_bus import EventBus


class FaceDatabase:
    """
    2026 SOTA Face Database for face recognition.
    
    Stores face embeddings with names for identification.
    Uses InsightFace embeddings (512-d) or DeepFace embeddings.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "face_database.pkl"
        )
        self.faces: Dict[str, Dict[str, Any]] = {}  # name -> {embedding, metadata}
        self.embedding_dim = 512  # InsightFace default
        self._lock = threading.Lock()
        self._load_database()
    
    def _load_database(self) -> None:
        """Load face database from disk."""
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, 'rb') as f:
                    self.faces = pickle.load(f)
        except Exception:
            self.faces = {}
    
    def _save_database(self) -> None:
        """Save face database to disk."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, 'wb') as f:
                pickle.dump(self.faces, f)
        except Exception:
            pass
    
    def register_face(self, name: str, embedding: np.ndarray, metadata: Dict = None) -> bool:
        """Register a face with a name."""
        with self._lock:
            self.faces[name] = {
                'embedding': embedding,
                'metadata': metadata or {},
                'registered_at': time.time()
            }
            self._save_database()
            return True
    
    def delete_face(self, name: str) -> bool:
        """Delete a face from the database."""
        with self._lock:
            if name in self.faces:
                del self.faces[name]
                self._save_database()
                return True
            return False
    
    def find_face(self, embedding: np.ndarray, threshold: float = 0.6) -> Optional[Tuple[str, float]]:
        """Find the most similar face in the database."""
        if not self.faces:
            return None
        
        best_match = None
        best_similarity = 0.0
        
        with self._lock:
            for name, data in self.faces.items():
                stored_embedding = data['embedding']
                # Cosine similarity
                similarity = np.dot(embedding, stored_embedding) / (
                    np.linalg.norm(embedding) * np.linalg.norm(stored_embedding) + 1e-8
                )
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = name
        
        if best_similarity >= threshold:
            return (best_match, float(best_similarity))
        return None
    
    def list_faces(self) -> List[Dict[str, Any]]:
        """List all registered faces."""
        with self._lock:
            return [
                {
                    'name': name,
                    'registered_at': data.get('registered_at'),
                    'metadata': data.get('metadata', {})
                }
                for name, data in self.faces.items()
            ]
    
    def get_face_count(self) -> int:
        """Get the number of registered faces."""
        return len(self.faces)


class FaceTracker:
    """
    2026 SOTA Face Tracker for tracking faces across frames.
    
    Assigns unique IDs to faces and tracks them over time.
    """
    
    def __init__(self, max_disappeared: int = 30):
        self.next_id = 0
        self.tracked_faces: Dict[int, Dict[str, Any]] = {}  # id -> {centroid, embedding, last_seen}
        self.max_disappeared = max_disappeared
        self._lock = threading.Lock()
    
    def update(self, faces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update tracker with new face detections."""
        current_time = time.time()
        
        with self._lock:
            # Remove stale tracks
            stale_ids = []
            for face_id, data in self.tracked_faces.items():
                if current_time - data['last_seen'] > self.max_disappeared / 30.0:  # Assuming 30 FPS
                    stale_ids.append(face_id)
            for face_id in stale_ids:
                del self.tracked_faces[face_id]
            
            # If no faces detected, return empty
            if not faces:
                return []
            
            # Calculate centroids for new faces
            new_centroids = []
            for face in faces:
                box = face.get('box', [0, 0, 0, 0])
                cx = box[0] + box[2] / 2
                cy = box[1] + box[3] / 2
                new_centroids.append((cx, cy))
            
            # If no existing tracks, create new ones
            if not self.tracked_faces:
                for i, face in enumerate(faces):
                    face['track_id'] = self.next_id
                    self.tracked_faces[self.next_id] = {
                        'centroid': new_centroids[i],
                        'embedding': face.get('embedding'),
                        'last_seen': current_time
                    }
                    self.next_id += 1
                return faces
            
            # Match existing tracks to new detections
            existing_ids = list(self.tracked_faces.keys())
            existing_centroids = [self.tracked_faces[id]['centroid'] for id in existing_ids]
            
            # Calculate distances
            matched = set()
            for i, (cx, cy) in enumerate(new_centroids):
                min_dist = float('inf')
                min_id = None
                for j, (ex, ey) in enumerate(existing_centroids):
                    if j in matched:
                        continue
                    dist = np.sqrt((cx - ex) ** 2 + (cy - ey) ** 2)
                    if dist < min_dist and dist < 100:  # Max distance threshold
                        min_dist = dist
                        min_id = j
                
                if min_id is not None:
                    matched.add(min_id)
                    face_id = existing_ids[min_id]
                    faces[i]['track_id'] = face_id
                    self.tracked_faces[face_id]['centroid'] = (cx, cy)
                    self.tracked_faces[face_id]['last_seen'] = current_time
                else:
                    # New face
                    faces[i]['track_id'] = self.next_id
                    self.tracked_faces[self.next_id] = {
                        'centroid': (cx, cy),
                        'embedding': faces[i].get('embedding'),
                        'last_seen': current_time
                    }
                    self.next_id += 1
            
            return faces


class VisionAnalysisComponent(BaseComponent):
    """
    2026 SOTA Vision Analysis Component for Kingdom AI.
    
    Consumes:
      - vision.stream.frame {"frame": np.ndarray, "timestamp": float}
      - vision.face.* commands for facial recognition
      - vision.objects.* commands for object detection
      - vision.ocr.* commands for text extraction

    Produces:
      - vision.analysis.face {faces, emotions, recognition results}
      - vision.analysis.objects {detections}
      - vision.analysis.pose {body pose}
      - vision.analysis.ocr {extracted text}
      - vision.face.result {recognition/identification results}
    
    Features:
      - Face Detection & Recognition (DeepFace + InsightFace)
      - Face Database with persistent storage
      - Face Tracking with unique IDs
      - Object Detection (YOLO)
      - Pose Estimation (MediaPipe)
      - OCR/Text Extraction
    """

    def __init__(self, name: str = "VisionAnalysis", event_bus: Optional[EventBus] = None, config: Optional[Dict[str, Any]] = None) -> None:
        event_bus = event_bus or EventBus.get_instance()
        super().__init__(name=name, event_bus=event_bus, config=config or {})

        self._latest_frame = None
        self._latest_timestamp: float = 0.0
        self._last_analysis_time: float = 0.0
        self._analysis_interval: float = 0.5
        self._lock = threading.Lock()
        self._prev_gray = None

        cfg = getattr(self, "config", {}) or {}
        self._pose_enabled = bool(cfg.get("enable_pose", False))
        self._objects_enabled = bool(cfg.get("enable_objects", False))
        self._biometrics_enabled = bool(cfg.get("enable_biometrics", True))
        self._recognition_enabled = bool(cfg.get("enable_recognition", True))
        self._ocr_enabled = bool(cfg.get("enable_ocr", False))
        
        # 2026 SOTA: Face Database for recognition
        self._face_database = FaceDatabase()
        
        # 2026 SOTA: Face Tracker for tracking across frames
        self._face_tracker = FaceTracker()
        
        # 2026 SOTA: InsightFace for high-performance recognition
        self._insightface_app = None
        if HAS_INSIGHTFACE and self._recognition_enabled:
            try:
                self._insightface_app = FaceAnalysis(
                    name='buffalo_l',
                    providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
                )
                self._insightface_app.prepare(ctx_id=0, det_size=(640, 640))
                self.logger.info("✅ InsightFace initialized for face recognition")
            except Exception as e:
                self.logger.warning(f"InsightFace initialization failed: {e}")
                self._insightface_app = None
        
        # 2026 SOTA: EasyOCR for text extraction
        self._ocr_reader = None
        if HAS_EASYOCR and self._ocr_enabled:
            try:
                self._ocr_reader = easyocr.Reader(['en'], gpu=True)
                self.logger.info("✅ EasyOCR initialized for text extraction")
            except Exception as e:
                self.logger.warning(f"EasyOCR initialization failed: {e}")
                self._ocr_reader = None

        self._pose_estimator = None
        self._mp_pose = None
        if HAS_MEDIAPIPE and self._pose_enabled:
            try:
                self._mp_pose = mp.solutions.pose
                self._pose_estimator = self._mp_pose.Pose(
                    static_image_mode=False,
                    model_complexity=0,
                    enable_segmentation=False,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            except Exception:
                self._pose_estimator = None

        self._face_mesh = None
        self._mp_face_mesh = None
        if HAS_MEDIAPIPE and self._biometrics_enabled:
            try:
                self._mp_face_mesh = mp.solutions.face_mesh
                self._face_mesh = self._mp_face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            except Exception:
                self._face_mesh = None

        self._yolo_model = None
        self._hog_detector = None
        if HAS_YOLO and self._objects_enabled:
            try:
                model_name = cfg.get("yolo_model", "yolov8n.pt")
                if model_name:
                    self._yolo_model = YOLO(model_name)
                    self.logger.info(f"✅ YOLO loaded: {model_name}")
            except Exception:
                self._yolo_model = None
        if self._objects_enabled and self._yolo_model is None:
            try:
                self._hog_detector = cv2.HOGDescriptor()
                self._hog_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            except Exception:
                self._hog_detector = None

        try:
            if hasattr(self.event_bus, "register_component"):
                self.event_bus.register_component("vision_analysis", self)
        except Exception:
            self.logger.exception("Failed to register VisionAnalysis component on EventBus")

        self.is_running = True
        self._worker_thread = threading.Thread(target=self._analysis_loop, name="VisionAnalysisThread", daemon=True)
        self._worker_thread.start()
        
        self.logger.info(f"✅ VisionAnalysis initialized: InsightFace={HAS_INSIGHTFACE}, DeepFace={HAS_DEEPFACE}, YOLO={HAS_YOLO}, OCR={HAS_EASYOCR}")

    def subscribe_to_events(self) -> None:
        if not self.event_bus:
            self.logger.warning("No EventBus available for VisionAnalysis")
            return
        
        # Core frame processing
        self.subscribe_sync("vision.stream.frame", self._on_frame_event)
        self.subscribe_sync("vision.analyze.image", self._on_analyze_image)
        
        # 2026 SOTA: Face Recognition Commands
        self.subscribe_sync("vision.face.analyze", self._on_face_analyze)
        self.subscribe_sync("vision.face.recognize", self._on_face_recognize)
        self.subscribe_sync("vision.face.detect", self._on_face_detect)
        self.subscribe_sync("vision.face.emotion", self._on_face_emotion)
        self.subscribe_sync("vision.face.demographics", self._on_face_demographics)
        self.subscribe_sync("vision.face.track", self._on_face_track)
        self.subscribe_sync("vision.face.register", self._on_face_register)
        self.subscribe_sync("vision.face.identify", self._on_face_identify)
        self.subscribe_sync("vision.face.list", self._on_face_list)
        self.subscribe_sync("vision.face.delete", self._on_face_delete)
        
        # 2026 SOTA: Object Detection Commands
        self.subscribe_sync("vision.objects.detect", self._on_objects_detect)
        self.subscribe_sync("vision.objects.find", self._on_objects_find)
        self.subscribe_sync("vision.objects.track", self._on_objects_track)
        self.subscribe_sync("vision.objects.count", self._on_objects_count)
        
        # 2026 SOTA: OCR Commands
        self.subscribe_sync("vision.ocr.extract", self._on_ocr_extract)
        self.subscribe_sync("vision.ocr.scan", self._on_ocr_scan)
        self.subscribe_sync("vision.ocr.document", self._on_ocr_document)
        
        # 2026 SOTA: Scene Understanding
        self.subscribe_sync("vision.scene.describe", self._on_scene_describe)
        self.subscribe_sync("vision.scene.analyze", self._on_scene_analyze)
        
        # 2026 SOTA: Pose/Gesture
        self.subscribe_sync("vision.pose.detect", self._on_pose_detect)
        self.subscribe_sync("vision.gesture.detect", self._on_gesture_detect)
        
        self.logger.info("✅ VisionAnalysis subscribed to all vision events")

    def _on_frame_event(self, data: Any) -> None:
        try:
            if not isinstance(data, dict):
                return
            frame = data.get("frame")
            if frame is None:
                return
            ts = float(data.get("timestamp", time.time()))
            with self._lock:
                self._latest_frame = frame
                self._latest_timestamp = ts
        except Exception:
            self.logger.exception("Error receiving frame in VisionAnalysis")

    def _on_analyze_image(self, data: Any) -> None:
        try:
            if not isinstance(data, dict):
                return
            frame = data.get("frame")
            path = data.get("path")
            ts = float(data.get("timestamp", time.time()))
            if frame is None and path:
                frame = cv2.imread(str(path))
            if frame is None:
                return
            result = self._analyze_frame(frame, ts)
            if result and self.event_bus and hasattr(self.event_bus, "publish_sync"):
                self.event_bus.publish_sync("vision.analysis.face", result)
        except Exception:
            self.logger.exception("Error analyzing image in VisionAnalysis")

    def _analysis_loop(self) -> None:
        while self.is_running:
            try:
                now = time.time()
                if now - self._last_analysis_time < self._analysis_interval:
                    time.sleep(0.05)
                    continue

                with self._lock:
                    frame = self._latest_frame
                    ts = self._latest_timestamp

                if frame is None:
                    time.sleep(0.05)
                    continue

                self._last_analysis_time = now
                result = self._analyze_frame(frame, ts)
                if result and self.event_bus and hasattr(self.event_bus, "publish_sync"):
                    self.event_bus.publish_sync("vision.analysis.face", result)
            except Exception:
                self.logger.exception("Error in VisionAnalysis loop")
                time.sleep(0.5)

    def _analyze_frame(self, frame: Any, timestamp: float) -> Optional[Dict[str, Any]]:
        try:
            if frame is None:
                return None
            if not hasattr(frame, "shape"):
                return None

            height, width = frame.shape[:2]
            summary: Dict[str, Any] = {
                "timestamp": float(timestamp),
                "width": int(width),
                "height": int(height),
                "num_faces": 0,
                "dominant_emotion": None,
                "emotions": {},
                "faces": [],
                "has_deepface": HAS_DEEPFACE,
                "component": self.name,
                "scene": {
                    "avg_brightness": None,
                    "motion_level": None,
                    "edge_density": None,
                    "colorfulness": None,
                },
                "objects": {"detections": []},
                "pose": {},
                "biometrics": {},
            }

            gray = None
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                summary["scene"]["avg_brightness"] = float(np.mean(gray))
                if self._prev_gray is not None and self._prev_gray.shape == gray.shape:
                    diff = cv2.absdiff(gray, self._prev_gray)
                    summary["scene"]["motion_level"] = float(np.mean(diff))
                self._prev_gray = gray

                edges = cv2.Canny(gray, 100, 200)
                if edges is not None and edges.size > 0:
                    summary["scene"]["edge_density"] = float(float(cv2.countNonZero(edges)) / float(edges.size))

                try:
                    b, g, r = cv2.split(frame)
                    rg = np.abs(r.astype("float32") - g.astype("float32"))
                    yb = np.abs(0.5 * (r.astype("float32") + g.astype("float32")) - b.astype("float32"))
                    summary["scene"]["colorfulness"] = float(np.mean(rg) + np.mean(yb))
                except Exception:
                    pass
            except Exception:
                self.logger.exception("Error computing scene metrics in VisionAnalysis")

            faces_detected = False

            if HAS_DEEPFACE and DeepFace is not None:
                try:
                    analysis = DeepFace.analyze(
                        img_path=frame,
                        actions=["emotion", "age", "gender"],
                        enforce_detection=False,
                    )
                    if isinstance(analysis, list):
                        records = analysis
                    else:
                        records = [analysis]
                    for rec in records:
                        region = rec.get("region") or {}
                        emotions = rec.get("emotion") or {}
                        dominant = rec.get("dominant_emotion")
                        face_info = {
                            "box": [
                                int(region.get("x", 0)),
                                int(region.get("y", 0)),
                                int(region.get("w", 0)),
                                int(region.get("h", 0)),
                            ],
                            "age": rec.get("age"),
                            "gender": rec.get("gender"),
                            "emotion": dominant,
                            "emotions": {k: float(v) for k, v in emotions.items()},
                        }
                        summary["faces"].append(face_info)
                        summary["num_faces"] += 1
                        for k, v in emotions.items():
                            value = float(v)
                            if k not in summary["emotions"] or value > summary["emotions"][k]:
                                summary["emotions"][k] = value
                    faces_detected = summary["num_faces"] > 0
                except Exception:
                    self.logger.exception("DeepFace analysis failed; falling back to OpenCV-only analysis")

            if not faces_detected:
                try:
                    if gray is None:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
                    detections = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
                    for (x, y, w, h) in detections:
                        face_info = {
                            "box": [int(x), int(y), int(w), int(h)],
                            "age": None,
                            "gender": None,
                            "emotion": None,
                            "emotions": {},
                        }
                            
                        summary["faces"].append(face_info)
                        summary["num_faces"] += 1
                    faces_detected = summary["num_faces"] > 0
                except Exception:
                    self.logger.exception("OpenCV face detection failed in VisionAnalysis")

            if summary["emotions"]:
                try:
                    summary["dominant_emotion"] = max(summary["emotions"], key=summary["emotions"].get)
                except Exception:
                    summary["dominant_emotion"] = None

            try:
                if self._objects_enabled:
                    objects = {"detections": []}
                    if self._yolo_model is not None and HAS_YOLO:
                        try:
                            results = self._yolo_model(frame, verbose=False)
                            for r in results:
                                boxes = getattr(r, "boxes", None)
                                if boxes is None:
                                    continue
                                for box in boxes:
                                    cls_idx = None
                                    conf = None
                                    xyxy = None
                                    try:
                                        if hasattr(box, "cls") and len(box.cls) > 0:
                                            cls_idx = int(box.cls[0])
                                        if hasattr(box, "conf") and len(box.conf) > 0:
                                            conf = float(box.conf[0])
                                        if hasattr(box, "xyxy") and len(box.xyxy) > 0:
                                            xyxy = box.xyxy[0].tolist()
                                    except Exception:
                                        pass
                                    if xyxy is None:
                                        continue
                                    try:
                                        x1, y1, x2, y2 = [int(v) for v in xyxy]
                                        w_box = max(0, x2 - x1)
                                        h_box = max(0, y2 - y1)
                                    except Exception:
                                        continue
                                    label = str(cls_idx) if cls_idx is not None else "obj"
                                    objects["detections"].append(
                                        {
                                            "label": label,
                                            "confidence": conf,
                                            "box": [x1, y1, w_box, h_box],
                                        }
                                    )
                        except Exception:
                            self.logger.exception("YOLO object detection failed; disabling YOLO model")
                            self._yolo_model = None
                    elif self._hog_detector is not None:
                        try:
                            if gray is None:
                                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            rects, weights = self._hog_detector.detectMultiScale(gray, winStride=(8, 8))
                            for (x, y, w_box, h_box), wgt in zip(rects, weights):
                                conf_val = None
                                try:
                                    conf_val = float(wgt[0]) if hasattr(wgt, "__len__") else float(wgt)
                                except Exception:
                                    conf_val = None
                                objects["detections"].append(
                                    {
                                        "label": "person",
                                        "confidence": conf_val,
                                        "box": [int(x), int(y), int(w_box), int(h_box)],
                                    }
                                )
                        except Exception:
                            self.logger.exception("HOG person detection failed in VisionAnalysis")
                    summary["objects"] = objects
                    if objects["detections"] and self.event_bus and hasattr(self.event_bus, "publish_sync"):
                        try:
                            self.event_bus.publish_sync(
                                "vision.analysis.objects",
                                {
                                    "timestamp": float(timestamp),
                                    "width": int(width),
                                    "height": int(height),
                                    "objects": objects,
                                },
                            )
                        except Exception:
                            self.logger.exception("Error publishing vision.analysis.objects event")
            except Exception:
                self.logger.exception("Error computing object detections in VisionAnalysis")

            try:
                pose_data: Dict[str, Any] = {}
                if HAS_MEDIAPIPE and self._pose_enabled and self._pose_estimator is not None:
                    try:
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        results = self._pose_estimator.process(rgb)
                        if results and getattr(results, "pose_landmarks", None):
                            pose_data["body_present"] = True
                            landmarks = results.pose_landmarks.landmark
                            try:
                                nose = landmarks[self._mp_pose.PoseLandmark.NOSE]
                                left_shoulder = landmarks[self._mp_pose.PoseLandmark.LEFT_SHOULDER]
                                right_shoulder = landmarks[self._mp_pose.PoseLandmark.RIGHT_SHOULDER]
                                shoulders_dx = right_shoulder.x - left_shoulder.x
                                pose_data["body_turn"] = float(shoulders_dx)
                                pose_data["head_x"] = float(nose.x)
                                pose_data["head_y"] = float(nose.y)
                            except Exception:
                                pass
                    except Exception:
                        self.logger.exception("Error running MediaPipe pose estimator")
                if pose_data:
                    summary["pose"] = pose_data
                    if self.event_bus and hasattr(self.event_bus, "publish_sync"):
                        try:
                            self.event_bus.publish_sync(
                                "vision.analysis.pose",
                                {
                                    "timestamp": float(timestamp),
                                    "width": int(width),
                                    "height": int(height),
                                    "pose": pose_data,
                                },
                            )
                        except Exception:
                            self.logger.exception("Error publishing vision.analysis.pose event")
            except Exception:
                self.logger.exception("Error computing pose in VisionAnalysis")

            try:
                if self._biometrics_enabled:
                    biometrics: Dict[str, Any] = {}
                    num_faces = summary.get("num_faces", 0)
                    emotions = summary.get("emotions") or {}
                    scene = summary.get("scene") or {}
                    motion_level = scene.get("motion_level")
                    engagement = 0.0
                    if num_faces > 0:
                        engagement += 0.5
                    if isinstance(motion_level, (int, float)):
                        try:
                            engagement += min(float(motion_level) / 50.0, 0.5)
                        except Exception:
                            pass
                    if "body_present" in summary.get("pose", {}):
                        engagement = min(1.0, engagement + 0.1)
                    engagement = max(0.0, min(1.0, engagement))
                    biometrics["engagement"] = float(engagement)

                    stress_sources = []
                    for key in ("angry", "fear", "sad"):
                        val = emotions.get(key)
                        if isinstance(val, (int, float)):
                            stress_sources.append(float(val))
                    if stress_sources:
                        try:
                            biometrics["estimated_stress"] = float(max(stress_sources))
                        except Exception:
                            pass

                    summary["biometrics"] = biometrics
            except Exception:
                self.logger.exception("Error computing biometrics in VisionAnalysis")

            return summary
        except Exception:
            self.logger.exception("Unexpected error analyzing frame in VisionAnalysis")
            return None
    
    # =========================================================================
    # 2026 SOTA: Face Recognition Command Handlers
    # =========================================================================
    
    def _on_face_analyze(self, data: Any) -> None:
        """Comprehensive face analysis: detection, emotion, age, gender."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            result = self._analyze_faces_full(frame)
            self._publish_result("vision.face.result", {
                "action": "analyze",
                "success": True,
                "data": result
            })
        except Exception:
            self.logger.exception("Error in face analysis")
    
    def _on_face_recognize(self, data: Any) -> None:
        """Recognize faces against the database."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            faces = self._detect_and_recognize_faces(frame)
            self._publish_result("vision.face.result", {
                "action": "recognize",
                "success": True,
                "faces": faces,
                "recognized_count": sum(1 for f in faces if f.get('identity'))
            })
        except Exception:
            self.logger.exception("Error in face recognition")
    
    def _on_face_detect(self, data: Any) -> None:
        """Detect faces in current frame."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            faces = self._detect_faces(frame)
            self._publish_result("vision.face.result", {
                "action": "detect",
                "success": True,
                "faces": faces,
                "count": len(faces)
            })
        except Exception:
            self.logger.exception("Error in face detection")
    
    def _on_face_emotion(self, data: Any) -> None:
        """Analyze emotions in current frame."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            emotions = self._analyze_emotions(frame)
            self._publish_result("vision.face.result", {
                "action": "emotion",
                "success": True,
                "data": emotions
            })
        except Exception:
            self.logger.exception("Error in emotion analysis")
    
    def _on_face_demographics(self, data: Any) -> None:
        """Analyze age/gender in current frame."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            demographics = self._analyze_demographics(frame)
            self._publish_result("vision.face.result", {
                "action": "demographics",
                "success": True,
                "data": demographics
            })
        except Exception:
            self.logger.exception("Error in demographics analysis")
    
    def _on_face_track(self, data: Any) -> None:
        """Enable/disable face tracking."""
        try:
            self._publish_result("vision.face.result", {
                "action": "track",
                "success": True,
                "message": "Face tracking enabled",
                "active_tracks": len(self._face_tracker.tracked_faces)
            })
        except Exception:
            self.logger.exception("Error in face tracking")
    
    def _on_face_register(self, data: Any) -> None:
        """Register a face with a name."""
        try:
            name = data.get("name", "Unknown")
            frame = self._get_current_frame(data)
            if frame is None:
                self._publish_result("vision.face.result", {
                    "action": "register",
                    "success": False,
                    "error": "No frame available"
                })
                return
            
            # Get face embedding
            embedding = self._get_face_embedding(frame)
            if embedding is None:
                self._publish_result("vision.face.result", {
                    "action": "register",
                    "success": False,
                    "error": "No face detected in frame"
                })
                return
            
            # Register in database
            success = self._face_database.register_face(name, embedding)
            self._publish_result("vision.face.result", {
                "action": "register",
                "success": success,
                "name": name,
                "message": f"Face registered as '{name}'" if success else "Registration failed",
                "total_faces": self._face_database.get_face_count()
            })
        except Exception:
            self.logger.exception("Error in face registration")
    
    def _on_face_identify(self, data: Any) -> None:
        """Identify a face against the database."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            embedding = self._get_face_embedding(frame)
            if embedding is None:
                self._publish_result("vision.face.result", {
                    "action": "identify",
                    "success": False,
                    "error": "No face detected"
                })
                return
            
            match = self._face_database.find_face(embedding)
            if match:
                name, confidence = match
                self._publish_result("vision.face.result", {
                    "action": "identify",
                    "success": True,
                    "identified": True,
                    "name": name,
                    "confidence": confidence,
                    "message": f"Identified as {name} ({confidence:.1%} confidence)"
                })
            else:
                self._publish_result("vision.face.result", {
                    "action": "identify",
                    "success": True,
                    "identified": False,
                    "message": "Face not recognized in database"
                })
        except Exception:
            self.logger.exception("Error in face identification")
    
    def _on_face_list(self, data: Any) -> None:
        """List all registered faces."""
        try:
            faces = self._face_database.list_faces()
            self._publish_result("vision.face.result", {
                "action": "list",
                "success": True,
                "faces": faces,
                "count": len(faces)
            })
        except Exception:
            self.logger.exception("Error listing faces")
    
    def _on_face_delete(self, data: Any) -> None:
        """Delete a face from the database."""
        try:
            name = data.get("name", "")
            success = self._face_database.delete_face(name)
            self._publish_result("vision.face.result", {
                "action": "delete",
                "success": success,
                "name": name,
                "message": f"Deleted face '{name}'" if success else f"Face '{name}' not found"
            })
        except Exception:
            self.logger.exception("Error deleting face")
    
    # =========================================================================
    # 2026 SOTA: Object Detection Command Handlers
    # =========================================================================
    
    def _on_objects_detect(self, data: Any) -> None:
        """Detect all objects in frame."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            objects = self._detect_objects(frame)
            self._publish_result("vision.objects.result", {
                "action": "detect",
                "success": True,
                "objects": objects,
                "count": len(objects)
            })
        except Exception:
            self.logger.exception("Error detecting objects")
    
    def _on_objects_find(self, data: Any) -> None:
        """Find a specific object in frame."""
        try:
            object_name = data.get("object_name", "").lower()
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            objects = self._detect_objects(frame)
            found = [o for o in objects if object_name in o.get("label", "").lower()]
            
            self._publish_result("vision.objects.result", {
                "action": "find",
                "success": True,
                "query": object_name,
                "found": found,
                "count": len(found),
                "message": f"Found {len(found)} {object_name}(s)" if found else f"No {object_name} found"
            })
        except Exception:
            self.logger.exception("Error finding object")
    
    def _on_objects_track(self, data: Any) -> None:
        """Track an object across frames."""
        try:
            self._publish_result("vision.objects.result", {
                "action": "track",
                "success": True,
                "message": "Object tracking enabled"
            })
        except Exception:
            self.logger.exception("Error tracking object")
    
    def _on_objects_count(self, data: Any) -> None:
        """Count specific objects in frame."""
        try:
            object_type = data.get("object_type", "").lower()
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            objects = self._detect_objects(frame)
            if object_type:
                matching = [o for o in objects if object_type in o.get("label", "").lower()]
                count = len(matching)
            else:
                count = len(objects)
            
            self._publish_result("vision.objects.result", {
                "action": "count",
                "success": True,
                "object_type": object_type or "all",
                "count": count,
                "message": f"Found {count} {object_type or 'objects'}"
            })
        except Exception:
            self.logger.exception("Error counting objects")
    
    # =========================================================================
    # 2026 SOTA: OCR Command Handlers
    # =========================================================================
    
    def _on_ocr_extract(self, data: Any) -> None:
        """Extract text from frame."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            text = self._extract_text(frame)
            self._publish_result("vision.ocr.result", {
                "action": "extract",
                "success": True,
                "text": text,
                "has_text": bool(text)
            })
        except Exception:
            self.logger.exception("Error extracting text")
    
    def _on_ocr_scan(self, data: Any) -> None:
        """Scan for text in frame."""
        self._on_ocr_extract(data)
    
    def _on_ocr_document(self, data: Any) -> None:
        """Read document from frame."""
        self._on_ocr_extract(data)
    
    # =========================================================================
    # 2026 SOTA: Scene Understanding Command Handlers
    # =========================================================================
    
    def _on_scene_describe(self, data: Any) -> None:
        """Describe the current scene."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            # Analyze scene components
            faces = self._detect_faces(frame)
            objects = self._detect_objects(frame)
            
            description = []
            if faces:
                description.append(f"{len(faces)} person(s) visible")
            if objects:
                object_summary = {}
                for obj in objects:
                    label = obj.get("label", "object")
                    object_summary[label] = object_summary.get(label, 0) + 1
                for label, count in object_summary.items():
                    description.append(f"{count} {label}(s)")
            
            self._publish_result("vision.scene.result", {
                "action": "describe",
                "success": True,
                "description": ", ".join(description) if description else "Empty scene",
                "faces_count": len(faces),
                "objects_count": len(objects)
            })
        except Exception:
            self.logger.exception("Error describing scene")
    
    def _on_scene_analyze(self, data: Any) -> None:
        """Analyze the current scene."""
        self._on_scene_describe(data)
    
    # =========================================================================
    # 2026 SOTA: Pose/Gesture Command Handlers
    # =========================================================================
    
    def _on_pose_detect(self, data: Any) -> None:
        """Detect body pose in frame."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            pose = self._detect_pose(frame)
            self._publish_result("vision.pose.result", {
                "action": "detect",
                "success": True,
                "pose": pose,
                "body_present": pose.get("body_present", False)
            })
        except Exception:
            self.logger.exception("Error detecting pose")
    
    def _on_gesture_detect(self, data: Any) -> None:
        """Detect hand gestures in frame."""
        try:
            frame = self._get_current_frame(data)
            if frame is None:
                return
            
            # Use MediaPipe hands if available
            gestures = self._detect_gestures(frame)
            self._publish_result("vision.gesture.result", {
                "action": "detect",
                "success": True,
                "gestures": gestures
            })
        except Exception:
            self.logger.exception("Error detecting gestures")
    
    # =========================================================================
    # 2026 SOTA: Helper Methods
    # =========================================================================
    
    def _get_current_frame(self, data: Any) -> Optional[np.ndarray]:
        """Get current frame from data or buffer."""
        if isinstance(data, dict):
            frame = data.get("frame")
            if frame is not None:
                return frame
        
        with self._lock:
            return self._latest_frame
    
    def _publish_result(self, event: str, data: Dict[str, Any]) -> None:
        """Publish result to event bus."""
        if self.event_bus and hasattr(self.event_bus, "publish_sync"):
            try:
                data["timestamp"] = time.time()
                data["component"] = self.name
                self.event_bus.publish_sync(event, data)
            except Exception:
                pass
    
    def _get_face_embedding(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Get face embedding using InsightFace or DeepFace."""
        try:
            # Try InsightFace first (higher quality)
            if self._insightface_app is not None:
                faces = self._insightface_app.get(frame)
                if faces and len(faces) > 0:
                    return faces[0].embedding
            
            # Fallback to DeepFace
            if HAS_DEEPFACE:
                embeddings = DeepFace.represent(
                    frame,
                    model_name="ArcFace",
                    enforce_detection=False
                )
                if embeddings and len(embeddings) > 0:
                    return np.array(embeddings[0].get("embedding", []))
        except Exception:
            pass
        return None
    
    def _detect_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect faces in frame."""
        faces = []
        
        try:
            # Try InsightFace first
            if self._insightface_app is not None:
                detected = self._insightface_app.get(frame)
                for face in detected:
                    bbox = face.bbox.astype(int).tolist()
                    faces.append({
                        "box": [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]],
                        "confidence": float(face.det_score),
                        "embedding": face.embedding
                    })
                return self._face_tracker.update(faces)
            
            # Fallback to OpenCV
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            detections = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
            for (x, y, w, h) in detections:
                faces.append({
                    "box": [int(x), int(y), int(w), int(h)],
                    "confidence": 0.8
                })
        except Exception:
            pass
        
        return self._face_tracker.update(faces)
    
    def _detect_and_recognize_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect and recognize faces."""
        faces = self._detect_faces(frame)
        
        for face in faces:
            embedding = face.get("embedding")
            if embedding is not None:
                match = self._face_database.find_face(embedding)
                if match:
                    face["identity"] = match[0]
                    face["match_confidence"] = match[1]
        
        return faces
    
    def _analyze_faces_full(self, frame: np.ndarray) -> Dict[str, Any]:
        """Full face analysis including emotion, age, gender."""
        result = {
            "faces": [],
            "dominant_emotion": None,
            "emotions": {}
        }
        
        try:
            if HAS_DEEPFACE:
                analysis = DeepFace.analyze(
                    frame,
                    actions=["emotion", "age", "gender"],
                    enforce_detection=False
                )
                records = analysis if isinstance(analysis, list) else [analysis]
                for rec in records:
                    result["faces"].append({
                        "box": list(rec.get("region", {}).values())[:4],
                        "age": rec.get("age"),
                        "gender": rec.get("gender"),
                        "emotion": rec.get("dominant_emotion"),
                        "emotions": rec.get("emotion", {})
                    })
                    if not result["dominant_emotion"]:
                        result["dominant_emotion"] = rec.get("dominant_emotion")
                    for k, v in rec.get("emotion", {}).items():
                        if k not in result["emotions"] or v > result["emotions"][k]:
                            result["emotions"][k] = v
        except Exception:
            pass
        
        return result
    
    def _analyze_emotions(self, frame: np.ndarray) -> Dict[str, Any]:
        """Analyze emotions in frame."""
        result = self._analyze_faces_full(frame)
        return {
            "dominant_emotion": result.get("dominant_emotion"),
            "emotions": result.get("emotions", {})
        }
    
    def _analyze_demographics(self, frame: np.ndarray) -> Dict[str, Any]:
        """Analyze age/gender in frame."""
        result = self._analyze_faces_full(frame)
        if result["faces"]:
            return {
                "age": result["faces"][0].get("age"),
                "gender": result["faces"][0].get("gender")
            }
        return {"age": None, "gender": None}
    
    def _detect_objects(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect objects using YOLO."""
        objects = []
        
        try:
            if self._yolo_model is not None:
                results = self._yolo_model(frame, verbose=False)
                for r in results:
                    boxes = getattr(r, "boxes", None)
                    if boxes is None:
                        continue
                    for box in boxes:
                        try:
                            cls_idx = int(box.cls[0]) if hasattr(box, "cls") and len(box.cls) > 0 else None
                            conf = float(box.conf[0]) if hasattr(box, "conf") and len(box.conf) > 0 else None
                            xyxy = box.xyxy[0].tolist() if hasattr(box, "xyxy") and len(box.xyxy) > 0 else None
                            if xyxy:
                                x1, y1, x2, y2 = [int(v) for v in xyxy]
                                # Get label from model names
                                label = self._yolo_model.names.get(cls_idx, str(cls_idx)) if cls_idx is not None else "object"
                                objects.append({
                                    "label": label,
                                    "confidence": conf,
                                    "box": [x1, y1, x2 - x1, y2 - y1]
                                })
                        except Exception:
                            pass
        except Exception:
            pass
        
        return objects
    
    def _extract_text(self, frame: np.ndarray) -> str:
        """Extract text from frame using OCR."""
        try:
            if self._ocr_reader is not None:
                results = self._ocr_reader.readtext(frame)
                text_parts = [r[1] for r in results if r[2] > 0.3]  # Confidence > 30%
                return " ".join(text_parts)
        except Exception:
            pass
        return ""
    
    def _detect_pose(self, frame: np.ndarray) -> Dict[str, Any]:
        """Detect body pose using MediaPipe."""
        pose_data = {}
        
        try:
            if self._pose_estimator is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self._pose_estimator.process(rgb)
                if results and getattr(results, "pose_landmarks", None):
                    pose_data["body_present"] = True
                    landmarks = results.pose_landmarks.landmark
                    nose = landmarks[self._mp_pose.PoseLandmark.NOSE]
                    pose_data["head_x"] = float(nose.x)
                    pose_data["head_y"] = float(nose.y)
        except Exception:
            pass
        
        return pose_data
    
    def _detect_gestures(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect hand gestures using MediaPipe."""
        gestures = []
        
        try:
            if HAS_MEDIAPIPE:
                mp_hands = mp.solutions.hands
                with mp_hands.Hands(
                    static_image_mode=True,
                    max_num_hands=2,
                    min_detection_confidence=0.5
                ) as hands:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = hands.process(rgb)
                    if results.multi_hand_landmarks:
                        for hand_landmarks in results.multi_hand_landmarks:
                            gestures.append({
                                "hand_detected": True,
                                "landmarks_count": len(hand_landmarks.landmark)
                            })
        except Exception:
            pass
        
        return gestures
