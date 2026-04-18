"""
Kingdom AI — Silent Alarm
SOTA 2026: Covert emergency notification system.

When triggered by CreatorShield, silently:
  1. Notifies emergency contacts (SMS, email, push)
  2. Notifies KAI army (other Kingdom AI instances)
  3. Shares Creator's GPS location
  4. Activates evidence collection
  5. Does NOT produce any visible/audible indicator on device

The entire point is that an attacker doesn't know KAI has raised the alarm.
Dormant until protection flag "silent_alarm" is activated.
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

REDIS_KEY = "kingdom:silent_alarm:log"


class SilentAlarm(BaseComponent):
    """
    Covert emergency alarm system.

    When triggered:
      - Sends notifications to emergency contacts via ContactManager
      - Sends alert to KAI army network (if connected)
      - Captures GPS coordinates
      - Starts evidence collection (audio/video/screenshots)
      - Logs all actions for later review

    NO visible UI changes. NO sounds. Completely silent.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._alarm_active = False
        self._alarm_history: List[Dict] = []
        self._lock = threading.Lock()

        self._subscribe_events()
        self._initialized = True
        logger.info("SilentAlarm initialized (dormant until activated)")

    # ------------------------------------------------------------------
    # Core trigger
    # ------------------------------------------------------------------

    def trigger(self, reason: str, threat_level: str = "critical",
                assessment: Optional[Dict] = None) -> bool:
        """
        Trigger the silent alarm. Returns True if triggered successfully.
        """
        if not self._is_active():
            return False

        with self._lock:
            if self._alarm_active:
                logger.info("Silent alarm already active, updating reason: %s", reason)

            self._alarm_active = True

        alarm_data = {
            "reason": reason,
            "threat_level": threat_level,
            "assessment": assessment or {},
            "triggered_at": datetime.utcnow().isoformat(),
            "actions_taken": [],
        }

        # 1. Notify emergency contacts (SILENT — no sound, no visible indicator)
        self._notify_contacts(alarm_data)

        # 2. Notify KAI army network
        self._notify_army(alarm_data)

        # 3. Capture GPS location
        self._capture_location(alarm_data)

        # 4. Start evidence collection
        self._start_evidence_capture(alarm_data)

        # 5. Log alarm
        self._log_alarm(alarm_data)

        logger.warning("SILENT ALARM TRIGGERED: %s (threat=%s)", reason, threat_level)
        return True

    def deactivate(self, reason: str = "manual") -> None:
        """Deactivate the silent alarm."""
        with self._lock:
            self._alarm_active = False

        if self.event_bus:
            self.event_bus.publish("security.silent_alarm.deactivated", {
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            })
        logger.info("Silent alarm deactivated: %s", reason)

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._alarm_active

    # ------------------------------------------------------------------
    # Alarm actions
    # ------------------------------------------------------------------

    def _notify_contacts(self, alarm_data: Dict) -> None:
        """Silently notify emergency contacts."""
        if not self.event_bus:
            return

        self.event_bus.publish("security.emergency.notify_contacts", {
            "reason": alarm_data["reason"],
            "urgency": "critical",
            "silent": True,  # No on-device notification sound
            "location": alarm_data.get("location"),
            "timestamp": alarm_data["triggered_at"],
        })
        alarm_data["actions_taken"].append("emergency_contacts_notified")

    def _notify_army(self, alarm_data: Dict) -> None:
        """Notify KAI army network."""
        if not self.event_bus:
            return

        self.event_bus.publish("army.alert.broadcast", {
            "alert_type": "creator_in_danger",
            "reason": alarm_data["reason"],
            "threat_level": alarm_data["threat_level"],
            "timestamp": alarm_data["triggered_at"],
            "silent": True,
        })
        alarm_data["actions_taken"].append("army_notified")

    def _capture_location(self, alarm_data: Dict) -> None:
        """Attempt to capture GPS coordinates."""
        location = {"lat": None, "lon": None, "source": "unavailable"}

        # Try to get location from wearable
        if self.event_bus:
            self.event_bus.publish("health.location.request", {
                "reason": "silent_alarm",
                "priority": "critical",
            })

        alarm_data["location"] = location
        alarm_data["actions_taken"].append("location_requested")

    def _start_evidence_capture(self, alarm_data: Dict) -> None:
        """Start evidence collection."""
        if not self.event_bus:
            return

        self.event_bus.publish("security.evidence.start_capture", {
            "reason": alarm_data["reason"],
            "duration_seconds": 600,  # 10 minutes
            "capture_audio": True,
            "capture_video": True,
            "capture_screenshots": True,
            "capture_logs": True,
            "silent": True,
        })
        alarm_data["actions_taken"].append("evidence_capture_started")

    def _log_alarm(self, alarm_data: Dict) -> None:
        """Log alarm event for forensic review."""
        self._alarm_history.append(alarm_data)

        # Persist to Redis
        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY, self._alarm_history[-100:])
            except Exception:
                pass

        # Also persist locally
        try:
            log_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "logs",
            )
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "silent_alarm_log.jsonl")
            with open(log_path, "a") as f:
                f.write(json.dumps(alarm_data) + "\n")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("silent_alarm")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("security.silent_alarm.trigger", self._handle_trigger)
        self.event_bus.subscribe("security.silent_alarm.deactivate", self._handle_deactivate)

    def _handle_trigger(self, data: Any) -> None:
        if isinstance(data, dict):
            self.trigger(
                reason=data.get("reason", "unknown"),
                threat_level=data.get("threat_level", "critical"),
                assessment=data.get("assessment"),
            )

    def _handle_deactivate(self, data: Any) -> None:
        reason = "event"
        if isinstance(data, dict):
            reason = data.get("reason", "event")
        self.deactivate(reason)

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "alarm_active": self._alarm_active,
            "alarm_history_count": len(self._alarm_history),
        }
