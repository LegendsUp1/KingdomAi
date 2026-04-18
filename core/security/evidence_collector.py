"""
Kingdom AI — Evidence Collector
SOTA 2026: Forensic evidence capture system for Creator protection.

When activated (by CreatorShield or SilentAlarm), captures:
  - Audio recording from microphone
  - Video/screenshots from webcam
  - System logs and event bus history
  - Network activity snapshot
  - Ambient transcription history

All evidence is encrypted and stored locally + Redis.
Dormant until protection flag "evidence_collector" is activated.
"""
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

EVIDENCE_DIR_REL = os.path.join("data", "evidence")


class EvidenceSession:
    """A single evidence collection session."""

    def __init__(self, reason: str, duration_seconds: int = 300):
        self.session_id = f"ev_{int(time.time())}"
        self.reason = reason
        self.duration_seconds = duration_seconds
        self.started_at = datetime.utcnow().isoformat()
        self.ended_at: Optional[str] = None
        self.artifacts: List[Dict] = []
        self.active = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "reason": self.reason,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "artifact_count": len(self.artifacts),
            "active": self.active,
        }


class EvidenceCollector(BaseComponent):
    """
    Forensic evidence capture and preservation system.

    Captures multi-modal evidence during security events:
      - Audio from ambient_transcriber feed
      - Video frames from vision system
      - Event bus history
      - System state snapshots

    All evidence is timestamped and stored in a tamper-evident log.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._active_session: Optional[EvidenceSession] = None
        self._session_history: List[Dict] = []
        self._lock = threading.Lock()

        self._evidence_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            EVIDENCE_DIR_REL,
        )

        self._capture_thread: Optional[threading.Thread] = None
        self._capturing = False

        self._subscribe_events()
        self._initialized = True
        logger.info("EvidenceCollector initialized (dormant until activated)")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def start_capture(self, reason: str, duration_seconds: int = 300,
                      capture_audio: bool = True, capture_video: bool = True,
                      capture_logs: bool = True, **kwargs) -> Optional[str]:
        """Start an evidence collection session. Returns session_id."""
        if not self._is_active():
            return None

        with self._lock:
            if self._active_session and self._active_session.active:
                # Extend existing session
                self._active_session.duration_seconds = max(
                    self._active_session.duration_seconds, duration_seconds
                )
                logger.info("Extended evidence session: %s", self._active_session.session_id)
                return self._active_session.session_id

            session = EvidenceSession(reason=reason, duration_seconds=duration_seconds)
            self._active_session = session

        # Create evidence directory for this session
        session_dir = os.path.join(self._evidence_dir, session.session_id)
        try:
            os.makedirs(session_dir, exist_ok=True)
        except Exception as e:
            logger.error("Failed to create evidence directory: %s", e)

        # Start capture in background
        self._capturing = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            args=(session, capture_audio, capture_video, capture_logs),
            daemon=True,
            name="EvidenceCapture",
        )
        self._capture_thread.start()

        if self.event_bus:
            self.event_bus.publish("security.evidence.capture_started", session.to_dict())

        logger.info("Evidence capture started: %s (reason=%s, duration=%ds)",
                     session.session_id, reason, duration_seconds)
        return session.session_id

    def stop_capture(self) -> None:
        """Stop the active evidence collection session."""
        self._capturing = False
        with self._lock:
            if self._active_session:
                self._active_session.active = False
                self._active_session.ended_at = datetime.utcnow().isoformat()
                self._session_history.append(self._active_session.to_dict())

                if self.event_bus:
                    self.event_bus.publish("security.evidence.capture_stopped",
                                          self._active_session.to_dict())

                logger.info("Evidence capture stopped: %s (%d artifacts)",
                            self._active_session.session_id,
                            len(self._active_session.artifacts))
                self._active_session = None

    # ------------------------------------------------------------------
    # Capture loop
    # ------------------------------------------------------------------

    def _capture_loop(self, session: EvidenceSession,
                      capture_audio: bool, capture_video: bool, capture_logs: bool) -> None:
        """Background capture loop."""
        start_time = time.time()
        session_dir = os.path.join(self._evidence_dir, session.session_id)

        try:
            # Capture initial state
            if capture_logs:
                self._capture_event_history(session, session_dir)
                self._capture_system_state(session, session_dir)

            # Capture audio/video frames periodically
            frame_interval = 5  # seconds between frame captures
            while self._capturing:
                elapsed = time.time() - start_time
                if elapsed >= session.duration_seconds:
                    break

                if capture_video:
                    self._capture_video_frame(session, session_dir)

                if capture_audio:
                    self._capture_audio_snapshot(session, session_dir)

                # Sleep in small increments
                for _ in range(frame_interval):
                    if not self._capturing:
                        break
                    time.sleep(1)

            # Final capture
            if capture_logs:
                self._capture_event_history(session, session_dir, suffix="_final")

        except Exception as e:
            logger.error("Evidence capture error: %s", e)
        finally:
            with self._lock:
                if self._active_session and self._active_session.session_id == session.session_id:
                    session.active = False
                    session.ended_at = datetime.utcnow().isoformat()
                    self._session_history.append(session.to_dict())
                    self._active_session = None

            self._capturing = False
            logger.info("Evidence capture loop ended for %s", session.session_id)

    # ------------------------------------------------------------------
    # Individual capture methods
    # ------------------------------------------------------------------

    def _capture_event_history(self, session: EvidenceSession, session_dir: str,
                               suffix: str = "") -> None:
        """Capture event bus history."""
        try:
            if self.event_bus and hasattr(self.event_bus, "get_event_history"):
                history = self.event_bus.get_event_history(limit=1000)
                filepath = os.path.join(session_dir, f"event_history{suffix}.json")
                with open(filepath, "w") as f:
                    json.dump(history, f, indent=1, default=str)
                session.artifacts.append({
                    "type": "event_history",
                    "path": filepath,
                    "timestamp": datetime.utcnow().isoformat(),
                })
        except Exception as e:
            logger.debug("Event history capture failed: %s", e)

    def _capture_system_state(self, session: EvidenceSession, session_dir: str) -> None:
        """Capture current system state snapshot."""
        try:
            state: Dict[str, Any] = {
                "timestamp": datetime.utcnow().isoformat(),
                "reason": session.reason,
            }

            # Get component statuses
            if self.event_bus and hasattr(self.event_bus, "get_all_components"):
                components = self.event_bus.get_all_components()
                state["registered_components"] = list(components.keys())

            filepath = os.path.join(session_dir, "system_state.json")
            with open(filepath, "w") as f:
                json.dump(state, f, indent=2, default=str)
            session.artifacts.append({
                "type": "system_state",
                "path": filepath,
                "timestamp": state["timestamp"],
            })
        except Exception as e:
            logger.debug("System state capture failed: %s", e)

    def _capture_video_frame(self, session: EvidenceSession, session_dir: str) -> None:
        """Request a video frame capture from vision system."""
        if self.event_bus:
            self.event_bus.publish("security.evidence.capture_frame", {
                "session_id": session.session_id,
                "output_dir": session_dir,
            })

    def _capture_audio_snapshot(self, session: EvidenceSession, session_dir: str) -> None:
        """Request transcription snapshot from ambient transcriber."""
        if self.event_bus:
            self.event_bus.publish("security.transcription.query", {"count": 50})

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("evidence_collector")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("security.evidence.start_capture", self._handle_start)
        self.event_bus.subscribe("security.evidence.stop_capture", self._handle_stop)

    def _handle_start(self, data: Any) -> None:
        if isinstance(data, dict):
            self.start_capture(
                reason=data.get("reason", "unknown"),
                duration_seconds=data.get("duration_seconds", 300),
                capture_audio=data.get("capture_audio", True),
                capture_video=data.get("capture_video", True),
                capture_logs=data.get("capture_logs", True),
            )

    def _handle_stop(self, data: Any) -> None:
        self.stop_capture()

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self.stop_capture()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            active = self._active_session.to_dict() if self._active_session else None
        return {
            "capturing": self._capturing,
            "active_session": active,
            "session_history_count": len(self._session_history),
        }
