"""Head-Mounted Display integration for VR/AR capabilities."""

from __future__ import annotations

import logging
import math
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kingdom_ai.hmd_integration")

SUPPORTED_HMDS = ("oculus", "vive", "index", "pico", "generic")


class _TrackingState:
    __slots__ = ("position", "rotation", "velocity", "timestamp")

    def __init__(self) -> None:
        self.position: List[float] = [0.0, 1.7, 0.0]
        self.rotation: List[float] = [0.0, 0.0, 0.0, 1.0]
        self.velocity: List[float] = [0.0, 0.0, 0.0]
        self.timestamp: float = time.monotonic()

    def update_simulated(self) -> None:
        dt = time.monotonic() - self.timestamp
        self.timestamp = time.monotonic()
        for i in range(3):
            self.position[i] += random.gauss(0, 0.001)
        angle = random.gauss(0, 0.01)
        axis = random.choice([0, 1, 2])
        half = angle / 2.0
        s = math.sin(half)
        q = [0.0, 0.0, 0.0, math.cos(half)]
        q[axis] = s
        self.rotation = self._quat_mul(self.rotation, q)
        norm = math.sqrt(sum(c * c for c in self.rotation))
        if norm > 0:
            self.rotation = [c / norm for c in self.rotation]

    @staticmethod
    def _quat_mul(a: List[float], b: List[float]) -> List[float]:
        return [
            a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
            a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
            a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
            a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2],
        ]


class HMDIntegration:
    """Manages HMD tracking, rendering pipeline, and scene management."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._connected: bool = False
        self._device_type: str = "none"
        self._tracking = _TrackingState()
        self._frame_count: int = 0
        self._connected_at: Optional[str] = None
        self._ipd_mm: float = 63.0
        self._refresh_rate: int = 90
        self._resolution: Tuple[int, int] = (2160, 2160)
        self._fov_deg: float = 110.0
        if event_bus:
            event_bus.subscribe("hmd.command.request", self._on_command_request)
        logger.info("HMDIntegration initialised")

    def connect_hmd(self, device_type: str = "generic") -> Dict[str, Any]:
        dt = device_type.lower()
        if dt not in SUPPORTED_HMDS:
            return {"connected": False, "error": f"Unsupported HMD: {device_type}. Supported: {SUPPORTED_HMDS}"}
        self._device_type = dt
        self._connected = True
        self._connected_at = datetime.now().isoformat()
        self._tracking = _TrackingState()
        self._frame_count = 0
        specs = self._get_device_specs(dt)
        self._refresh_rate = specs["refresh_rate"]
        self._resolution = tuple(specs["resolution"])
        self._fov_deg = specs["fov_deg"]
        logger.info("Connected HMD: %s (refresh=%dHz, res=%s)", dt, self._refresh_rate, self._resolution)
        return {"connected": True, "device_type": dt, "specs": specs}

    def disconnect_hmd(self) -> Dict[str, Any]:
        if not self._connected:
            return {"connected": False, "error": "No HMD connected"}
        old = self._device_type
        self._connected = False
        self._device_type = "none"
        logger.info("Disconnected HMD: %s (frames=%d)", old, self._frame_count)
        return {"disconnected": True, "device_type": old, "total_frames": self._frame_count}

    def get_tracking_data(self) -> Dict[str, Any]:
        if not self._connected:
            return {"error": "No HMD connected"}
        self._tracking.update_simulated()
        return {
            "position": [round(v, 4) for v in self._tracking.position],
            "rotation": [round(v, 6) for v in self._tracking.rotation],
            "velocity": [round(v, 4) for v in self._tracking.velocity],
            "timestamp": self._tracking.timestamp,
            "device_type": self._device_type,
        }

    def submit_frame(self, frame_data: Any = None) -> Dict[str, Any]:
        if not self._connected:
            return {"error": "No HMD connected"}
        self._frame_count += 1
        self._tracking.update_simulated()
        return {
            "frame_number": self._frame_count,
            "timestamp": time.monotonic(),
            "resolution": list(self._resolution),
            "accepted": True,
        }

    def get_hmd_status(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "device_type": self._device_type,
            "connected_at": self._connected_at,
            "frame_count": self._frame_count,
            "refresh_rate": self._refresh_rate,
            "resolution": list(self._resolution),
            "fov_deg": self._fov_deg,
            "ipd_mm": self._ipd_mm,
            "tracking_active": self._connected,
        }

    def set_ipd(self, ipd_mm: float) -> Dict[str, Any]:
        old = self._ipd_mm
        self._ipd_mm = max(55.0, min(75.0, ipd_mm))
        logger.debug("IPD adjusted: %.1f -> %.1f mm", old, self._ipd_mm)
        return {"old_ipd": old, "new_ipd": self._ipd_mm}

    @staticmethod
    def _get_device_specs(device_type: str) -> Dict[str, Any]:
        specs: Dict[str, Dict[str, Any]] = {
            "oculus": {"refresh_rate": 90, "resolution": [2160, 2160], "fov_deg": 110.0, "tracking": "inside-out"},
            "vive": {"refresh_rate": 90, "resolution": [2160, 2160], "fov_deg": 120.0, "tracking": "lighthouse"},
            "index": {"refresh_rate": 144, "resolution": [2880, 2880], "fov_deg": 130.0, "tracking": "lighthouse"},
            "pico": {"refresh_rate": 90, "resolution": [2160, 2160], "fov_deg": 105.0, "tracking": "inside-out"},
            "generic": {"refresh_rate": 72, "resolution": [1920, 1920], "fov_deg": 100.0, "tracking": "3dof"},
        }
        return specs.get(device_type, specs["generic"])

    def _on_command_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("HMD command ignored — expected dict")
            return
        action = data.get("action", "status")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            if action == "connect":
                result["data"] = self.connect_hmd(data.get("device_type", "generic"))
            elif action == "disconnect":
                result["data"] = self.disconnect_hmd()
            elif action == "tracking":
                result["data"] = self.get_tracking_data()
            elif action == "submit_frame":
                result["data"] = self.submit_frame(data.get("frame_data"))
            elif action == "status":
                result["data"] = self.get_hmd_status()
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("HMD command failed")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("hmd.tracking.update", result)
