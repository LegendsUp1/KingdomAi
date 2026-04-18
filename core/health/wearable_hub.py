"""
Kingdom AI — Wearable Hub (Central Health Data Aggregator)
SOTA 2026: 3-layer wearable connectivity architecture.

Layer 1: Terra API — unified cloud aggregator for 150+ wearable brands
Layer 2: Direct device APIs — deep integration for Garmin, Oura, Fitbit, Withings, Whoop
Layer 3: BLE (Bleak) — real-time local Bluetooth streaming for instant vitals

All health data flows through event bus to:
  - HealthAnomalyDetector (baseline learning + anomaly detection)
  - CreatorShield (duress corroboration, death protocol)
  - HealthAdvisor (proactive health intelligence)
  - Health Dashboard GUI tab

Dormant until protection flag "wearable_hub" is activated.
"""
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

REDIS_KEY_VITALS = "kingdom:health:latest_vitals"
REDIS_KEY_DEVICES = "kingdom:health:connected_devices"
LOCAL_DEVICES_REL = os.path.join("config", "wearable_devices.json")

# Optional imports for device connectors
HAS_GARMIN = False
HAS_OURA = False
HAS_FITBIT = False
HAS_BLEAK = False
HAS_REQUESTS = False

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    pass

try:
    from garminconnect import Garmin
    HAS_GARMIN = True
except ImportError:
    pass

try:
    from oura import OuraClient
    HAS_OURA = True
except ImportError:
    try:
        from oura_ring import OuraClient
        HAS_OURA = True
    except ImportError:
        pass

try:
    import bleak
    HAS_BLEAK = True
except ImportError:
    pass


class DeviceInfo:
    """Represents a connected wearable device."""

    def __init__(self, device_id: str, name: str, brand: str,
                 connection_type: str = "api", status: str = "disconnected"):
        self.device_id = device_id
        self.name = name
        self.brand = brand
        self.connection_type = connection_type  # "api", "ble", "terra"
        self.status = status  # "connected", "disconnected", "syncing"
        self.last_sync: Optional[str] = None
        self.battery_pct: Optional[int] = None
        self.credentials: Dict[str, str] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "brand": self.brand,
            "connection_type": self.connection_type,
            "status": self.status,
            "last_sync": self.last_sync,
            "battery_pct": self.battery_pct,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceInfo":
        d = cls(
            device_id=data.get("device_id", ""),
            name=data.get("name", ""),
            brand=data.get("brand", ""),
            connection_type=data.get("connection_type", "api"),
            status=data.get("status", "disconnected"),
        )
        d.last_sync = data.get("last_sync")
        d.battery_pct = data.get("battery_pct")
        d.credentials = data.get("credentials", {})
        return d


class HealthVitals:
    """Snapshot of current health vitals."""

    def __init__(self):
        self.heart_rate: Optional[int] = None
        self.hrv_rmssd: Optional[float] = None
        self.spo2: Optional[int] = None
        self.stress_level: Optional[int] = None
        self.body_temperature: Optional[float] = None
        self.respiratory_rate: Optional[float] = None
        self.steps_today: Optional[int] = None
        self.active_calories: Optional[int] = None
        self.sleep_score: Optional[int] = None
        self.sleep_duration_hours: Optional[float] = None
        self.readiness_score: Optional[int] = None
        self.blood_glucose: Optional[float] = None
        self.body_battery: Optional[int] = None
        self.vo2_max: Optional[float] = None
        self.training_readiness: Optional[int] = None
        self.timestamp: str = datetime.utcnow().isoformat()
        self.source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {}
        for attr in (
            "heart_rate", "hrv_rmssd", "spo2", "stress_level", "body_temperature",
            "respiratory_rate", "steps_today", "active_calories", "sleep_score",
            "sleep_duration_hours", "readiness_score", "blood_glucose", "body_battery",
            "vo2_max", "training_readiness", "timestamp", "source",
        ):
            val = getattr(self, attr, None)
            if val is not None:
                d[attr] = val
        return d


class WearableHub(BaseComponent):
    """
    Central wearable health data aggregator.

    Connects to Creator's wearable devices via 3 layers:
    1. Terra API (webhook receiver for 150+ brands)
    2. Direct device APIs (Garmin, Oura, Fitbit, Withings, Whoop)
    3. BLE real-time streaming (Bleak)

    Publishes health data to event bus.
    Stores latest vitals + history in Redis.
    """

    _instance: Optional["WearableHub"] = None
    _lock_cls = threading.Lock()

    @classmethod
    def get_instance(cls, event_bus=None, redis_connector=None, config=None):
        if cls._instance is None:
            with cls._lock_cls:
                if cls._instance is None:
                    cls._instance = cls(config=config, event_bus=event_bus, redis_connector=redis_connector)
        return cls._instance

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._devices: Dict[str, DeviceInfo] = {}
        self._devices_lock = threading.RLock()
        self._latest_vitals = HealthVitals()
        self._vitals_lock = threading.RLock()
        self._vitals_history: deque = deque(maxlen=1440)  # 24h at 1/min

        # Polling workers
        self._polling_thread: Optional[threading.Thread] = None
        self._polling_running = False
        self._poll_interval = int(self.config.get("poll_interval_seconds", 60))

        # BLE manager reference
        self._ble_manager = None

        # Device API clients
        self._garmin_client = None
        self._oura_client = None

        # Terra API config
        self._terra_dev_id = os.environ.get("TERRA_DEV_ID", "")
        self._terra_api_key = os.environ.get("TERRA_API_KEY", "")

        self._local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            LOCAL_DEVICES_REL,
        )

        self._load_devices()
        self._subscribe_events()
        self._initialized = True
        logger.info(
            "WearableHub initialized — devices=%d, garmin=%s, oura=%s, ble=%s, terra=%s",
            len(self._devices), HAS_GARMIN, HAS_OURA, HAS_BLEAK,
            bool(self._terra_dev_id),
        )

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def add_device(self, name: str, brand: str, connection_type: str = "api",
                   credentials: Optional[Dict] = None) -> str:
        """Register a new wearable device. Returns device_id."""
        import hashlib
        device_id = hashlib.md5(f"{brand}:{name}".encode()).hexdigest()[:12]
        device = DeviceInfo(device_id=device_id, name=name, brand=brand, connection_type=connection_type)
        if credentials:
            device.credentials = credentials
        with self._devices_lock:
            self._devices[device_id] = device
        self._persist_devices()

        if self.event_bus:
            self.event_bus.publish("health.device.connected", device.to_dict())
        logger.info("Wearable device added: %s (%s) via %s", name, brand, connection_type)
        return device_id

    def remove_device(self, device_id: str) -> bool:
        with self._devices_lock:
            if device_id in self._devices:
                removed = self._devices.pop(device_id)
                self._persist_devices()
                if self.event_bus:
                    self.event_bus.publish("health.device.disconnected", {"device_id": device_id, "name": removed.name})
                return True
        return False

    def get_devices(self) -> List[Dict]:
        with self._devices_lock:
            return [d.to_dict() for d in self._devices.values()]

    # ------------------------------------------------------------------
    # Vitals update (called by device connectors)
    # ------------------------------------------------------------------

    def update_vitals(self, vitals_data: Dict[str, Any], source: str = "") -> None:
        """Update latest vitals from any source."""
        with self._vitals_lock:
            for key, value in vitals_data.items():
                if hasattr(self._latest_vitals, key) and value is not None:
                    setattr(self._latest_vitals, key, value)
            self._latest_vitals.timestamp = datetime.utcnow().isoformat()
            self._latest_vitals.source = source
            snapshot = self._latest_vitals.to_dict()

        # Store in history
        self._vitals_history.append(snapshot)

        # Persist to Redis
        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY_VITALS, snapshot)
            except Exception:
                pass

        # Publish to event bus
        if self.event_bus:
            self.event_bus.publish("health.vitals.updated", snapshot)

            # Real-time HR event for CreatorShield
            hr = vitals_data.get("heart_rate")
            if hr is not None:
                self.event_bus.publish("health.hr.realtime", {"heart_rate": hr, "source": source})

            # Activity event for SceneContextEngine
            activity = vitals_data.get("activity_type") or vitals_data.get("activity")
            steps = vitals_data.get("steps_per_minute", 0)
            if activity or steps:
                self.event_bus.publish("health.activity.detected", {
                    "activity": activity or "unknown",
                    "steps_per_minute": steps,
                    "heart_rate": hr or 0,
                    "source": source,
                })

            # Fall detection from accelerometer data
            accel = vitals_data.get("accelerometer_magnitude_g", 0)
            if accel and accel >= 4.0:
                self.event_bus.publish("health.fall.detected", {
                    "accel_g": accel,
                    "heart_rate": hr,
                    "source": source,
                    "timestamp": snapshot.get("timestamp", ""),
                })

    def get_latest_vitals(self) -> Dict[str, Any]:
        with self._vitals_lock:
            return self._latest_vitals.to_dict()

    def get_vitals_history(self, count: int = 60) -> List[Dict]:
        return list(self._vitals_history)[-count:]

    # ------------------------------------------------------------------
    # Garmin Connect integration
    # ------------------------------------------------------------------

    def connect_garmin(self, email: str, password: str) -> bool:
        """Connect to Garmin Connect API."""
        if not HAS_GARMIN:
            logger.warning("garminconnect package not installed")
            return False
        try:
            self._garmin_client = Garmin(email, password)
            self._garmin_client.login()
            self.add_device("Garmin Watch", "garmin", "api", {"email": email})
            logger.info("Connected to Garmin Connect")
            return True
        except Exception as e:
            logger.error("Garmin Connect login failed: %s", e)
            return False

    def _poll_garmin(self) -> None:
        if not self._garmin_client:
            return
        try:
            # Get today's stats
            today = datetime.now().strftime("%Y-%m-%d")

            vitals: Dict[str, Any] = {}

            # Heart rate
            try:
                hr_data = self._garmin_client.get_heart_rates(today)
                if hr_data and "restingHeartRate" in hr_data:
                    vitals["heart_rate"] = hr_data["restingHeartRate"]
            except Exception:
                pass

            # Stress
            try:
                stress_data = self._garmin_client.get_stress_data(today)
                if stress_data and "overallStressLevel" in stress_data:
                    vitals["stress_level"] = stress_data["overallStressLevel"]
            except Exception:
                pass

            # Steps
            try:
                steps_data = self._garmin_client.get_steps_data(today)
                if steps_data:
                    total_steps = sum(s.get("steps", 0) for s in steps_data if isinstance(s, dict))
                    vitals["steps_today"] = total_steps
            except Exception:
                pass

            # SpO2
            try:
                spo2_data = self._garmin_client.get_spo2_data(today)
                if spo2_data and "averageSpO2" in spo2_data:
                    vitals["spo2"] = spo2_data["averageSpO2"]
            except Exception:
                pass

            # HRV
            try:
                hrv_data = self._garmin_client.get_hrv_data(today)
                if hrv_data and "hrvSummary" in hrv_data:
                    summary = hrv_data["hrvSummary"]
                    if "lastNightAvg" in summary:
                        vitals["hrv_rmssd"] = summary["lastNightAvg"]
            except Exception:
                pass

            # Body Battery
            try:
                bb_data = self._garmin_client.get_body_battery(today)
                if bb_data and isinstance(bb_data, list) and bb_data:
                    latest = bb_data[-1]
                    if isinstance(latest, dict) and "bodyBatteryLevel" in latest:
                        vitals["body_battery"] = latest["bodyBatteryLevel"]
            except Exception:
                pass

            # Sleep
            try:
                sleep_data = self._garmin_client.get_sleep_data(today)
                if sleep_data and "dailySleepDTO" in sleep_data:
                    sleep = sleep_data["dailySleepDTO"]
                    duration_ms = sleep.get("sleepTimeSeconds", 0)
                    if duration_ms:
                        vitals["sleep_duration_hours"] = round(duration_ms / 3600, 2)
                    if "overallScore" in sleep.get("sleepScores", {}):
                        vitals["sleep_score"] = sleep["sleepScores"]["overallScore"]
            except Exception:
                pass

            if vitals:
                self.update_vitals(vitals, source="garmin")

        except Exception as e:
            logger.debug("Garmin poll error: %s", e)

    # ------------------------------------------------------------------
    # Oura Ring integration
    # ------------------------------------------------------------------

    def connect_oura(self, access_token: str) -> bool:
        """Connect to Oura Ring API v2."""
        if not HAS_OURA:
            logger.warning("oura-ring package not installed")
            return False
        try:
            self._oura_client = OuraClient(personal_access_token=access_token)
            self.add_device("Oura Ring", "oura", "api")
            logger.info("Connected to Oura Ring API")
            return True
        except Exception as e:
            logger.error("Oura connection failed: %s", e)
            return False

    def _poll_oura(self) -> None:
        if not self._oura_client:
            return
        try:
            vitals: Dict[str, Any] = {}

            # Sleep
            try:
                sleep = self._oura_client.get_daily_sleep()
                if sleep and isinstance(sleep, list) and sleep:
                    latest = sleep[-1]
                    if "score" in latest:
                        vitals["sleep_score"] = latest["score"]
                    if "total_sleep_duration" in latest:
                        vitals["sleep_duration_hours"] = round(latest["total_sleep_duration"] / 3600, 2)
            except Exception:
                pass

            # Readiness
            try:
                readiness = self._oura_client.get_daily_readiness()
                if readiness and isinstance(readiness, list) and readiness:
                    latest = readiness[-1]
                    if "score" in latest:
                        vitals["readiness_score"] = latest["score"]
            except Exception:
                pass

            # Heart rate
            try:
                hr = self._oura_client.get_heartrate()
                if hr and isinstance(hr, list) and hr:
                    latest = hr[-1]
                    if "bpm" in latest:
                        vitals["heart_rate"] = latest["bpm"]
            except Exception:
                pass

            if vitals:
                self.update_vitals(vitals, source="oura")

        except Exception as e:
            logger.debug("Oura poll error: %s", e)

    # ------------------------------------------------------------------
    # Terra API integration (universal)
    # ------------------------------------------------------------------

    def process_terra_webhook(self, webhook_data: Dict[str, Any]) -> None:
        """Process incoming Terra API webhook data."""
        if not isinstance(webhook_data, dict):
            return

        event_type = webhook_data.get("type", "")
        user = webhook_data.get("user", {})
        data = webhook_data.get("data", [])

        if not data:
            return

        vitals: Dict[str, Any] = {}

        for entry in (data if isinstance(data, list) else [data]):
            if not isinstance(entry, dict):
                continue

            # Heart rate
            hr_data = entry.get("heart_rate_data", {})
            if hr_data:
                summary = hr_data.get("summary", {})
                if "avg_hr_bpm" in summary:
                    vitals["heart_rate"] = int(summary["avg_hr_bpm"])

            # HRV
            hrv_data = entry.get("heart_rate_variability_data", {})
            if hrv_data:
                summary = hrv_data.get("summary", {})
                if "rmssd" in summary:
                    vitals["hrv_rmssd"] = round(summary["rmssd"], 1)

            # Sleep
            sleep_data = entry.get("sleep_data", {})
            if sleep_data:
                summary = sleep_data.get("summary", {})
                if "sleep_score" in summary:
                    vitals["sleep_score"] = int(summary["sleep_score"])

            # SpO2
            oxygen_data = entry.get("oxygen_data", {})
            if oxygen_data:
                summary = oxygen_data.get("summary", {})
                if "avg_saturation_percentage" in summary:
                    vitals["spo2"] = int(summary["avg_saturation_percentage"])

            # Steps
            activity_data = entry.get("activity_data", {})
            if activity_data:
                summary = activity_data.get("summary", {})
                if "steps" in summary:
                    vitals["steps_today"] = int(summary["steps"])

            # Body temperature
            temp_data = entry.get("temperature_data", {})
            if temp_data:
                summary = temp_data.get("summary", {})
                if "avg_temperature_celsius" in summary:
                    vitals["body_temperature"] = round(summary["avg_temperature_celsius"], 1)

        if vitals:
            provider = user.get("provider", "terra")
            self.update_vitals(vitals, source=f"terra_{provider}")

    # ------------------------------------------------------------------
    # BLE real-time heart rate streaming
    # ------------------------------------------------------------------

    def _init_ble_manager(self) -> None:
        """Initialize BLE manager for real-time streaming."""
        if not HAS_BLEAK:
            return
        try:
            from core.health.ble_manager import BLEHealthManager
            self._ble_manager = BLEHealthManager(
                event_bus=self.event_bus,
                on_heart_rate=self._on_ble_heart_rate,
            )
            logger.info("BLE health manager initialized")
        except Exception as e:
            logger.debug("BLE manager init failed: %s", e)

    def _on_ble_heart_rate(self, hr: int) -> None:
        """Callback from BLE heart rate streaming."""
        self.update_vitals({"heart_rate": hr}, source="ble")

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    def start_polling(self) -> None:
        if self._polling_running:
            return
        self._polling_running = True
        self._polling_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="WearablePoller",
        )
        self._polling_thread.start()
        logger.info("Wearable polling started (interval=%ds)", self._poll_interval)

    def stop_polling(self) -> None:
        self._polling_running = False
        if self._polling_thread and self._polling_thread.is_alive():
            self._polling_thread.join(timeout=5)

    def _poll_loop(self) -> None:
        while self._polling_running:
            try:
                if not self._is_active():
                    time.sleep(10)
                    continue

                self._poll_garmin()
                self._poll_oura()

            except Exception as e:
                logger.error("Wearable poll error: %s", e)

            for _ in range(self._poll_interval):
                if not self._polling_running:
                    return
                time.sleep(1)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("wearable_hub")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_devices(self) -> None:
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY_DEVICES)
                if isinstance(data, list):
                    for dd in data:
                        d = DeviceInfo.from_dict(dd)
                        self._devices[d.device_id] = d
                    return
            except Exception:
                pass

        if os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for dd in data:
                        d = DeviceInfo.from_dict(dd)
                        self._devices[d.device_id] = d
            except Exception:
                pass

    def _persist_devices(self) -> None:
        with self._devices_lock:
            snapshot = [d.to_dict() for d in self._devices.values()]

        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY_DEVICES, snapshot)
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
        self.event_bus.subscribe("health.device.add", self._handle_add_device)
        self.event_bus.subscribe("health.device.remove", self._handle_remove_device)
        self.event_bus.subscribe("health.terra.webhook", self._handle_terra_webhook)
        self.event_bus.subscribe("health.vitals.query", self._handle_vitals_query)
        self.event_bus.subscribe("health.devices.query", self._handle_devices_query)
        self.event_bus.subscribe("protection.flag.changed", self._handle_flag_change)

    def _handle_add_device(self, data: Any) -> None:
        if isinstance(data, dict):
            brand = data.get("brand", "unknown")
            name = data.get("name", brand)
            conn = data.get("connection_type", "api")
            creds = data.get("credentials")

            if brand == "garmin" and creds:
                self.connect_garmin(creds.get("email", ""), creds.get("password", ""))
            elif brand == "oura" and creds:
                self.connect_oura(creds.get("access_token", ""))
            else:
                self.add_device(name, brand, conn, creds)

    def _handle_remove_device(self, data: Any) -> None:
        if isinstance(data, dict):
            self.remove_device(data.get("device_id", ""))

    def _handle_terra_webhook(self, data: Any) -> None:
        if isinstance(data, dict):
            self.process_terra_webhook(data)

    def _handle_vitals_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("health.vitals.current", self.get_latest_vitals())

    def _handle_devices_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("health.devices.list", {"devices": self.get_devices()})

    def _handle_flag_change(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        if data.get("module") in ("wearable_hub", "__all__"):
            if data.get("active"):
                self.start_polling()
                self._init_ble_manager()
            else:
                self.stop_polling()

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self.stop_polling()
        self._persist_devices()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "devices": self.get_devices(),
            "latest_vitals": self.get_latest_vitals(),
            "polling": self._polling_running,
            "garmin_connected": self._garmin_client is not None,
            "oura_connected": self._oura_client is not None,
            "ble_available": HAS_BLEAK,
            "terra_configured": bool(self._terra_dev_id),
        }
