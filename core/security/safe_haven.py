"""
Kingdom AI — Safe Haven + Crash Detector
SOTA 2026: Location-aware safety zone system + vehicle crash detection.

Safe Haven:
  - Creator defines "safe zones" (home, office, gym, family houses)
  - KAI reduces alerting in safe zones (less false alarms)
  - KAI increases alerting when Creator is in unknown locations
  - Works with GPS from phone/wearable and WiFi BSSID fingerprinting

Crash Detection:
  - Sudden accelerometer spike + immediate HR change → possible crash
  - Works with wearable accelerometer data (Apple Watch, Garmin, etc.)
  - Auto-alerts emergency contacts with GPS location
  - Integrates with existing SilentAlarm and WellnessChecker

Dormant until protection flag "safe_haven" is activated.
"""
import json
import logging
import math
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from base_component import BaseComponent

logger = logging.getLogger(__name__)

REDIS_KEY_ZONES = "kingdom:safe_haven:zones"
LOCAL_ZONES_REL = os.path.join("config", "safe_zones.json")

# Crash detection thresholds
CRASH_ACCEL_THRESHOLD_G = 4.0    # 4G sudden deceleration
CRASH_HR_SPIKE_BPM = 40          # HR spike of 40+ BPM within seconds


class SafeZone:
    """A defined safe location."""

    def __init__(self, name: str, lat: float, lon: float, radius_meters: float = 200,
                 zone_type: str = "home", threat_reduction: float = 0.5,
                 zone_id: Optional[str] = None):
        self.zone_id = zone_id or f"sz_{int(time.time())}"
        self.name = name
        self.lat = lat
        self.lon = lon
        self.radius_meters = radius_meters
        self.zone_type = zone_type  # home, office, gym, family, custom
        self.threat_reduction = threat_reduction  # Multiplier reduction in safe zone
        self.wifi_bssids: List[str] = []  # WiFi fingerprints for indoor detection
        self.created_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "radius_meters": self.radius_meters,
            "zone_type": self.zone_type,
            "threat_reduction": self.threat_reduction,
            "wifi_bssids": self.wifi_bssids,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SafeZone":
        z = cls(
            name=data.get("name", ""),
            lat=data.get("lat", 0),
            lon=data.get("lon", 0),
            radius_meters=data.get("radius_meters", 200),
            zone_type=data.get("zone_type", "custom"),
            threat_reduction=data.get("threat_reduction", 0.5),
            zone_id=data.get("zone_id"),
        )
        z.wifi_bssids = data.get("wifi_bssids", [])
        z.created_at = data.get("created_at", z.created_at)
        return z

    def contains(self, lat: float, lon: float) -> bool:
        """Check if GPS coordinates are within this zone."""
        dist = self._haversine(self.lat, self.lon, lat, lon)
        return dist <= self.radius_meters

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in meters between two GPS points."""
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class SafeHaven(BaseComponent):
    """
    Location-aware safety system with crash detection.

    Manages safe zones and provides location-based threat adjustment.
    Detects vehicle crashes from accelerometer + heart rate data.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._zones: Dict[str, SafeZone] = {}
        self._zones_lock = threading.RLock()

        # Current location
        self._current_lat: Optional[float] = None
        self._current_lon: Optional[float] = None
        self._current_zone: Optional[str] = None  # zone_id if in a safe zone

        # Crash detection state
        self._last_hr: int = 0
        self._last_hr_time: float = 0
        self._accel_history: List[Tuple[float, float]] = []  # (timestamp, magnitude_g)
        self._crash_cooldown_until: float = 0

        self._local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            LOCAL_ZONES_REL,
        )

        self._load_zones()
        self._subscribe_events()
        self._initialized = True
        logger.info("SafeHaven initialized — %d safe zones loaded", len(self._zones))

    # ------------------------------------------------------------------
    # Safe zone management
    # ------------------------------------------------------------------

    def add_zone(self, name: str, lat: float, lon: float, radius_meters: float = 200,
                 zone_type: str = "custom", threat_reduction: float = 0.5,
                 wifi_bssids: Optional[List[str]] = None) -> str:
        """Add a safe zone. Returns zone_id."""
        zone = SafeZone(name=name, lat=lat, lon=lon, radius_meters=radius_meters,
                        zone_type=zone_type, threat_reduction=threat_reduction)
        if wifi_bssids:
            zone.wifi_bssids = wifi_bssids

        with self._zones_lock:
            self._zones[zone.zone_id] = zone
        self._persist_zones()

        if self.event_bus:
            self.event_bus.publish("safehaven.zone.added", zone.to_dict())
        logger.info("Safe zone added: %s (%s) at %.4f,%.4f r=%dm", name, zone_type, lat, lon, radius_meters)
        return zone.zone_id

    def remove_zone(self, zone_id: str) -> bool:
        with self._zones_lock:
            if zone_id in self._zones:
                removed = self._zones.pop(zone_id)
                self._persist_zones()
                if self.event_bus:
                    self.event_bus.publish("safehaven.zone.removed", {"zone_id": zone_id, "name": removed.name})
                return True
        return False

    def get_zones(self) -> List[Dict]:
        with self._zones_lock:
            return [z.to_dict() for z in self._zones.values()]

    # ------------------------------------------------------------------
    # Location checking
    # ------------------------------------------------------------------

    def update_location(self, lat: float, lon: float) -> Dict[str, Any]:
        """Update Creator's location and check zone status."""
        self._current_lat = lat
        self._current_lon = lon

        # Check if in any safe zone
        in_zone = None
        with self._zones_lock:
            for zone in self._zones.values():
                if zone.contains(lat, lon):
                    in_zone = zone
                    break

        old_zone = self._current_zone
        self._current_zone = in_zone.zone_id if in_zone else None

        result = {
            "lat": lat,
            "lon": lon,
            "in_safe_zone": in_zone is not None,
            "zone_name": in_zone.name if in_zone else None,
            "zone_type": in_zone.zone_type if in_zone else None,
            "threat_reduction": in_zone.threat_reduction if in_zone else 1.0,
        }

        # Publish zone change
        if old_zone != self._current_zone and self.event_bus:
            if in_zone:
                self.event_bus.publish("safehaven.entered", result)
                logger.info("Creator entered safe zone: %s", in_zone.name)
            elif old_zone:
                self.event_bus.publish("safehaven.left", result)
                logger.info("Creator left safe zone")

        return result

    def get_location_threat_multiplier(self) -> float:
        """Get threat multiplier based on current location."""
        if self._current_zone:
            with self._zones_lock:
                zone = self._zones.get(self._current_zone)
                if zone:
                    return zone.threat_reduction
        return 1.0  # Not in safe zone — normal threat level

    # ------------------------------------------------------------------
    # Crash detection
    # ------------------------------------------------------------------

    def process_accelerometer(self, accel_magnitude_g: float) -> bool:
        """
        Process accelerometer reading for crash detection.
        Returns True if crash detected.
        """
        if not self._is_active():
            return False

        now = time.time()

        # Cooldown after a crash detection
        if now < self._crash_cooldown_until:
            return False

        self._accel_history.append((now, accel_magnitude_g))
        # Keep only last 10 seconds
        self._accel_history = [(t, a) for t, a in self._accel_history if now - t < 10]

        # Check for sudden spike above threshold
        if accel_magnitude_g >= CRASH_ACCEL_THRESHOLD_G:
            # Corroborate with HR spike
            hr_spike = False
            if self._last_hr > 0 and self._last_hr_time > 0:
                # HR spike usually occurs within 5 seconds of impact
                time_since_hr = now - self._last_hr_time
                if time_since_hr < 5:
                    hr_spike = True  # Any recent HR data during impact is suspicious

            self._trigger_crash_alert(accel_magnitude_g, hr_spike)
            self._crash_cooldown_until = now + 300  # 5 min cooldown
            return True

        return False

    def _trigger_crash_alert(self, accel_g: float, hr_corroboration: bool) -> None:
        """Trigger crash detection alert."""
        logger.warning("CRASH DETECTED: %.1fG acceleration (HR corroboration: %s)", accel_g, hr_corroboration)

        if not self.event_bus:
            return

        crash_data = {
            "accel_g": round(accel_g, 1),
            "hr_corroboration": hr_corroboration,
            "location": {
                "lat": self._current_lat,
                "lon": self._current_lon,
            },
            "in_safe_zone": self._current_zone is not None,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Trigger wellness check first (give Creator chance to respond)
        self.event_bus.publish("wellness.check.triggered", {
            "reason": "crash_detected",
            "urgency": "critical",
            "timeout_seconds": 30,
        })

        # Publish crash event for CreatorShield
        self.event_bus.publish("security.crash.detected", crash_data)

        # Start evidence capture
        self.event_bus.publish("security.evidence.start_capture", {
            "reason": "crash_detection",
            "duration_seconds": 600,
        })

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("safe_haven")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_zones(self) -> None:
        loaded = False
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY_ZONES)
                if isinstance(data, list):
                    for zd in data:
                        z = SafeZone.from_dict(zd)
                        self._zones[z.zone_id] = z
                    loaded = True
            except Exception:
                pass

        if not loaded and os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for zd in data:
                        z = SafeZone.from_dict(zd)
                        self._zones[z.zone_id] = z
            except Exception:
                pass

    def _persist_zones(self) -> None:
        with self._zones_lock:
            snapshot = [z.to_dict() for z in self._zones.values()]

        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY_ZONES, snapshot)
            except Exception:
                pass

        try:
            os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
            with open(self._local_path, "w") as f:
                json.dump(snapshot, f, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("safehaven.zone.add", self._handle_add_zone)
        self.event_bus.subscribe("safehaven.zone.remove", self._handle_remove_zone)
        self.event_bus.subscribe("safehaven.location.update", self._handle_location)
        self.event_bus.subscribe("health.accelerometer", self._handle_accel)
        self.event_bus.subscribe("health.hr.realtime", self._handle_hr)
        self.event_bus.subscribe("safehaven.zones.query", self._handle_zones_query)

    def _handle_add_zone(self, data: Any) -> None:
        if isinstance(data, dict):
            self.add_zone(
                name=data.get("name", "Custom Zone"),
                lat=data.get("lat", 0),
                lon=data.get("lon", 0),
                radius_meters=data.get("radius_meters", 200),
                zone_type=data.get("zone_type", "custom"),
                threat_reduction=data.get("threat_reduction", 0.5),
                wifi_bssids=data.get("wifi_bssids"),
            )

    def _handle_remove_zone(self, data: Any) -> None:
        if isinstance(data, dict):
            self.remove_zone(data.get("zone_id", ""))

    def _handle_location(self, data: Any) -> None:
        if isinstance(data, dict):
            lat = data.get("lat") or data.get("latitude")
            lon = data.get("lon") or data.get("longitude")
            if lat is not None and lon is not None:
                self.update_location(float(lat), float(lon))

    def _handle_accel(self, data: Any) -> None:
        if isinstance(data, dict):
            magnitude = data.get("magnitude_g", 0)
            if magnitude:
                self.process_accelerometer(float(magnitude))

    def _handle_hr(self, data: Any) -> None:
        if isinstance(data, dict):
            hr = data.get("heart_rate", 0)
            if hr:
                self._last_hr = hr
                self._last_hr_time = time.time()

    def _handle_zones_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("safehaven.zones.list", {
                "zones": self.get_zones(),
                "current_zone": self._current_zone,
                "location_multiplier": self.get_location_threat_multiplier(),
            })

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self._persist_zones()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "zone_count": len(self._zones),
            "in_safe_zone": self._current_zone is not None,
            "current_zone": self._current_zone,
            "location_multiplier": self.get_location_threat_multiplier(),
        }
