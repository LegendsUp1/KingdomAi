"""Bone conduction audio driver for non-invasive audio output."""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.bone_conduction_driver")

SUPPORTED_CHANNELS = ("left", "right", "both")


class _BCDevice:
    __slots__ = ("device_id", "connected", "battery_pct", "volume", "connected_at",
                 "firmware", "channel_mode", "samples_played", "last_activity")

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.connected: bool = False
        self.battery_pct: float = 100.0
        self.volume: float = 0.5
        self.connected_at: Optional[str] = None
        self.firmware: str = "1.4.2"
        self.channel_mode: str = "both"
        self.samples_played: int = 0
        self.last_activity: Optional[str] = None


class BoneConductionDriver:
    """Drives bone conduction devices for non-invasive audio and haptic output."""

    def __init__(self, event_bus: Any = None, max_devices: int = 4) -> None:
        self.event_bus = event_bus
        self._devices: Dict[str, _BCDevice] = {}
        self._max_devices = max_devices
        self._playback_log: Deque[Dict[str, Any]] = deque(maxlen=200)
        self._haptic_patterns: Dict[str, List[float]] = {
            "click": [0.8, 0.0],
            "double_click": [0.8, 0.0, 0.8, 0.0],
            "buzz": [0.5] * 8,
            "pulse": [0.3, 0.0, 0.6, 0.0, 1.0, 0.0],
            "alert": [1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
        }
        if event_bus:
            event_bus.subscribe("bone_conduction.command.request", self._on_command_request)
        logger.info("BoneConductionDriver initialised (max_devices=%d)", max_devices)

    def connect_device(self, device_id: str) -> Dict[str, Any]:
        if len(self._devices) >= self._max_devices and device_id not in self._devices:
            return {"device_id": device_id, "connected": False, "error": f"Max devices ({self._max_devices}) reached"}
        dev = self._devices.get(device_id, _BCDevice(device_id))
        dev.connected = True
        dev.connected_at = datetime.now().isoformat()
        dev.battery_pct = min(dev.battery_pct, 100.0)
        self._devices[device_id] = dev
        logger.info("Connected bone-conduction device '%s' (battery=%.1f%%)", device_id, dev.battery_pct)
        return {"device_id": device_id, "connected": True, "battery_pct": dev.battery_pct, "firmware": dev.firmware}

    def disconnect_device(self, device_id: str) -> Dict[str, Any]:
        dev = self._devices.get(device_id)
        if not dev:
            return {"device_id": device_id, "error": "Device not found"}
        dev.connected = False
        logger.info("Disconnected bone-conduction device '%s'", device_id)
        return {"device_id": device_id, "connected": False, "samples_played": dev.samples_played}

    def play_audio(self, audio_data: bytes, channel: str = "both", device_id: Optional[str] = None) -> Dict[str, Any]:
        dev = self._resolve_device(device_id)
        if not dev:
            return {"error": "No connected device available"}
        if not dev.connected:
            return {"device_id": dev.device_id, "error": "Device not connected"}
        if channel not in SUPPORTED_CHANNELS:
            channel = "both"
        sample_count = len(audio_data) // 2
        dev.samples_played += sample_count
        dev.battery_pct = max(dev.battery_pct - sample_count * 0.0001, 0.0)
        dev.last_activity = datetime.now().isoformat()
        entry = {
            "device_id": dev.device_id,
            "channel": channel,
            "samples": sample_count,
            "bytes": len(audio_data),
            "timestamp": dev.last_activity,
        }
        self._playback_log.append(entry)
        logger.debug("Played %d samples on '%s' channel=%s", sample_count, dev.device_id, channel)
        return {"device_id": dev.device_id, "played": True, "samples": sample_count, "channel": channel}

    def play_haptic(self, pattern_name: str, intensity: float = 1.0, device_id: Optional[str] = None) -> Dict[str, Any]:
        dev = self._resolve_device(device_id)
        if not dev:
            return {"error": "No connected device available"}
        if not dev.connected:
            return {"device_id": dev.device_id, "error": "Device not connected"}
        pattern = self._haptic_patterns.get(pattern_name)
        if pattern is None:
            return {"error": f"Unknown pattern '{pattern_name}'. Available: {list(self._haptic_patterns.keys())}"}
        intensity = max(0.0, min(1.0, intensity))
        scaled = [round(v * intensity, 2) for v in pattern]
        dev.last_activity = datetime.now().isoformat()
        logger.debug("Haptic '%s' on '%s' intensity=%.2f", pattern_name, dev.device_id, intensity)
        return {"device_id": dev.device_id, "pattern": pattern_name, "steps": scaled, "intensity": intensity}

    def set_volume(self, level: float, device_id: Optional[str] = None) -> Dict[str, Any]:
        dev = self._resolve_device(device_id)
        if not dev:
            return {"error": "No connected device available"}
        old = dev.volume
        dev.volume = max(0.0, min(1.0, level))
        logger.debug("Volume '%s': %.2f -> %.2f", dev.device_id, old, dev.volume)
        return {"device_id": dev.device_id, "old_volume": round(old, 2), "new_volume": round(dev.volume, 2)}

    def get_device_status(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        if device_id:
            dev = self._devices.get(device_id)
            if not dev:
                return {"device_id": device_id, "error": "Device not found"}
            return self._device_info(dev)
        return {
            "device_count": len(self._devices),
            "connected_count": sum(1 for d in self._devices.values() if d.connected),
            "devices": [self._device_info(d) for d in self._devices.values()],
        }

    def _resolve_device(self, device_id: Optional[str]) -> Optional[_BCDevice]:
        if device_id:
            return self._devices.get(device_id)
        for dev in self._devices.values():
            if dev.connected:
                return dev
        return None

    @staticmethod
    def _device_info(dev: _BCDevice) -> Dict[str, Any]:
        return {
            "device_id": dev.device_id,
            "connected": dev.connected,
            "battery_pct": round(dev.battery_pct, 1),
            "volume": round(dev.volume, 2),
            "firmware": dev.firmware,
            "channel_mode": dev.channel_mode,
            "samples_played": dev.samples_played,
            "connected_at": dev.connected_at,
            "last_activity": dev.last_activity,
        }

    def _on_command_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("bone_conduction command ignored — expected dict")
            return
        action = data.get("action", "status")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            if action == "connect":
                result["data"] = self.connect_device(data.get("device_id", "bc-001"))
            elif action == "disconnect":
                result["data"] = self.disconnect_device(data.get("device_id", ""))
            elif action == "play":
                result["data"] = self.play_audio(data.get("audio_data", b""), data.get("channel", "both"), data.get("device_id"))
            elif action == "haptic":
                result["data"] = self.play_haptic(data.get("pattern", "click"), data.get("intensity", 1.0), data.get("device_id"))
            elif action == "volume":
                result["data"] = self.set_volume(data.get("level", 0.5), data.get("device_id"))
            elif action == "status":
                result["data"] = self.get_device_status(data.get("device_id"))
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("Bone conduction command failed")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("bone_conduction.status.update", result)
