"""Wearable biometric data streamer with BLE simulation and buffering."""

from __future__ import annotations

import logging
import random
import time
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, Generator, List, Optional

logger = logging.getLogger("kingdom_ai.wearable_biometric_streamer")


class _DeviceState:
    __slots__ = ("device_id", "connected", "device_type", "last_seen", "battery_pct")

    def __init__(self, device_id: str, device_type: str = "generic") -> None:
        self.device_id = device_id
        self.device_type = device_type
        self.connected: bool = False
        self.last_seen: Optional[str] = None
        self.battery_pct: float = 100.0


class WearableBiometricStreamer:
    """Streams biometric data from wearable devices (simulated BLE protocol)."""

    def __init__(self, event_bus: Any = None, buffer_size: int = 500) -> None:
        self.event_bus = event_bus
        self._devices: Dict[str, _DeviceState] = {}
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=buffer_size)
        self._latest: Dict[str, Any] = {}
        self._baseline: Dict[str, float] = {
            "heart_rate": 72.0,
            "spo2": 97.5,
            "steps": 0.0,
            "skin_temp": 36.6,
            "hrv_ms": 45.0,
            "respiration_rate": 15.0,
        }
        if event_bus:
            event_bus.subscribe("biometric.stream.request", self._on_stream_request)
        logger.info("WearableBiometricStreamer initialised (buffer=%d)", buffer_size)

    def connect_device(self, device_id: str, device_type: str = "generic") -> Dict[str, Any]:
        dev = _DeviceState(device_id, device_type)
        dev.connected = True
        dev.last_seen = datetime.now().isoformat()
        dev.battery_pct = round(random.uniform(40.0, 100.0), 1)
        self._devices[device_id] = dev
        logger.info("Connected device '%s' (type=%s, battery=%.1f%%)", device_id, device_type, dev.battery_pct)
        return {"device_id": device_id, "connected": True, "battery_pct": dev.battery_pct}

    def disconnect_device(self, device_id: str) -> Dict[str, Any]:
        dev = self._devices.get(device_id)
        if not dev:
            return {"device_id": device_id, "error": "Device not found"}
        dev.connected = False
        logger.info("Disconnected device '%s'", device_id)
        return {"device_id": device_id, "connected": False}

    def stream_data(self, device_id: Optional[str] = None, count: int = 10) -> Generator[Dict[str, Any], None, None]:
        connected = [d for d in self._devices.values() if d.connected]
        if device_id:
            connected = [d for d in connected if d.device_id == device_id]
        if not connected:
            yield {"error": "No connected devices"}
            return
        for _ in range(count):
            for dev in connected:
                sample = self._generate_sample(dev)
                self._buffer.append(sample)
                self._latest.update(sample["metrics"])
                dev.last_seen = sample["timestamp"]
                dev.battery_pct = max(dev.battery_pct - 0.01, 0.0)
                yield sample

    def get_latest_metrics(self) -> Dict[str, Any]:
        if not self._latest:
            return {"error": "No data available — connect a device and stream first"}
        return {
            "metrics": dict(self._latest),
            "timestamp": datetime.now().isoformat(),
            "connected_devices": sum(1 for d in self._devices.values() if d.connected),
        }

    def analyze_trends(self, window_minutes: float = 5.0) -> Dict[str, Any]:
        cutoff = time.time() - (window_minutes * 60)
        window: List[Dict[str, Any]] = []
        for sample in self._buffer:
            try:
                ts = datetime.fromisoformat(sample["timestamp"]).timestamp()
                if ts >= cutoff:
                    window.append(sample)
            except (ValueError, KeyError):
                continue
        if not window:
            return {"window_minutes": window_minutes, "samples": 0, "trends": {}}
        metrics_keys = list(self._baseline.keys())
        trends: Dict[str, Dict[str, float]] = {}
        for key in metrics_keys:
            values = [s["metrics"].get(key) for s in window if key in s.get("metrics", {})]
            values = [v for v in values if v is not None]
            if values:
                trends[key] = {
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                    "avg": round(sum(values) / len(values), 2),
                    "latest": round(values[-1], 2),
                }
        return {"window_minutes": window_minutes, "samples": len(window), "trends": trends}

    def _generate_sample(self, dev: _DeviceState) -> Dict[str, Any]:
        now = datetime.now()
        metrics: Dict[str, float] = {}
        for key, base in self._baseline.items():
            jitter = base * 0.05
            metrics[key] = round(base + random.uniform(-jitter, jitter), 2)
        metrics["steps"] = round(self._baseline["steps"] + random.randint(0, 3))
        self._baseline["steps"] = metrics["steps"]
        return {
            "device_id": dev.device_id,
            "device_type": dev.device_type,
            "timestamp": now.isoformat(),
            "metrics": metrics,
        }

    def _on_stream_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("stream request ignored — expected dict")
            return
        action = data.get("action", "latest")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            if action == "connect":
                result["data"] = self.connect_device(data.get("device_id", "sim-001"), data.get("device_type", "generic"))
            elif action == "latest":
                result["data"] = self.get_latest_metrics()
            elif action == "trends":
                result["data"] = self.analyze_trends(data.get("window_minutes", 5.0))
            elif action == "stream":
                samples = list(self.stream_data(data.get("device_id"), data.get("count", 10)))
                result["data"] = samples
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("Biometric stream request failed")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("biometric.data.update", result)
