"""Abstract hardware interface for sensors, actuators, and peripherals."""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kingdom_ai.hardware_interface_layer")


class _DeviceRecord:
    __slots__ = ("device_id", "device_type", "config", "status", "last_value",
                 "registered_at", "last_read_at", "read_count", "error_count")

    def __init__(self, device_id: str, device_type: str, config: Dict[str, Any]) -> None:
        self.device_id = device_id
        self.device_type = device_type
        self.config = dict(config)
        self.status: str = "online"
        self.last_value: Any = None
        self.registered_at: str = datetime.now().isoformat()
        self.last_read_at: Optional[str] = None
        self.read_count: int = 0
        self.error_count: int = 0


class HardwareInterfaceLayer:
    """Device registry with read/write access and hot-plug detection."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self._devices: Dict[str, _DeviceRecord] = {}
        self._simulated: bool = True
        if event_bus:
            event_bus.subscribe("hardware.command.request", self._on_command_request)
        logger.info("HardwareInterfaceLayer initialised (simulated=%s)", self._simulated)

    def register_device(self, device_id: str, device_type: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = config or {}
        if device_id in self._devices:
            logger.warning("Device '%s' already registered — updating config", device_id)
            self._devices[device_id].config.update(config)
            return {"device_id": device_id, "action": "updated"}
        rec = _DeviceRecord(device_id, device_type, config)
        self._devices[device_id] = rec
        logger.info("Registered device '%s' (type=%s)", device_id, device_type)
        if self.event_bus:
            self.event_bus.publish("hardware.status.update", {
                "event": "device_registered", "device_id": device_id, "device_type": device_type,
            })
        return {"device_id": device_id, "action": "registered", "device_type": device_type}

    def unregister_device(self, device_id: str) -> Dict[str, Any]:
        if device_id not in self._devices:
            return {"device_id": device_id, "error": "Device not found"}
        del self._devices[device_id]
        logger.info("Unregistered device '%s'", device_id)
        return {"device_id": device_id, "action": "unregistered"}

    def read_sensor(self, device_id: str) -> Dict[str, Any]:
        rec = self._devices.get(device_id)
        if not rec:
            return {"device_id": device_id, "error": "Device not found"}
        if rec.status != "online":
            return {"device_id": device_id, "error": f"Device status: {rec.status}"}
        value = self._simulate_read(rec)
        rec.last_value = value
        rec.last_read_at = datetime.now().isoformat()
        rec.read_count += 1
        return {"device_id": device_id, "value": value, "timestamp": rec.last_read_at, "unit": rec.config.get("unit", "raw")}

    def write_actuator(self, device_id: str, value: Any) -> Dict[str, Any]:
        rec = self._devices.get(device_id)
        if not rec:
            return {"device_id": device_id, "error": "Device not found"}
        if rec.status != "online":
            return {"device_id": device_id, "error": f"Device status: {rec.status}"}
        if rec.device_type not in ("actuator", "motor", "relay", "led", "servo", "generic"):
            return {"device_id": device_id, "error": f"Device type '{rec.device_type}' is not writable"}
        rec.last_value = value
        rec.last_read_at = datetime.now().isoformat()
        logger.debug("Wrote value=%s to actuator '%s'", value, device_id)
        return {"device_id": device_id, "written": True, "value": value, "timestamp": rec.last_read_at}

    def list_devices(self) -> List[Dict[str, Any]]:
        return [
            {
                "device_id": rec.device_id,
                "device_type": rec.device_type,
                "status": rec.status,
                "last_value": rec.last_value,
                "last_read_at": rec.last_read_at,
                "read_count": rec.read_count,
                "error_count": rec.error_count,
                "registered_at": rec.registered_at,
            }
            for rec in self._devices.values()
        ]

    def set_device_status(self, device_id: str, status: str) -> Dict[str, Any]:
        rec = self._devices.get(device_id)
        if not rec:
            return {"device_id": device_id, "error": "Device not found"}
        old = rec.status
        rec.status = status
        logger.info("Device '%s' status: %s -> %s", device_id, old, status)
        return {"device_id": device_id, "old_status": old, "new_status": status}

    def scan_for_devices(self) -> List[Dict[str, Any]]:
        discovered: List[Dict[str, Any]] = []
        sim_types = ["temperature_sensor", "accelerometer", "gyroscope", "light_sensor"]
        for i in range(random.randint(0, 3)):
            dev_type = random.choice(sim_types)
            dev_id = f"hotplug_{dev_type}_{random.randint(1000, 9999)}"
            discovered.append({"device_id": dev_id, "device_type": dev_type, "rssi": random.randint(-90, -30)})
        logger.info("Hot-plug scan discovered %d device(s)", len(discovered))
        return discovered

    def _simulate_read(self, rec: _DeviceRecord) -> Any:
        dt = rec.device_type.lower()
        if "temp" in dt:
            return round(20.0 + random.gauss(0, 2), 2)
        if "accel" in dt:
            return [round(random.gauss(0, 1), 3) for _ in range(3)]
        if "gyro" in dt:
            return [round(random.gauss(0, 10), 2) for _ in range(3)]
        if "light" in dt or "lux" in dt:
            return round(random.uniform(10, 1000), 1)
        if "pressure" in dt:
            return round(1013.25 + random.gauss(0, 5), 2)
        return round(random.uniform(0, 100), 2)

    def _on_command_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("hardware command ignored — expected dict")
            return
        action = data.get("action", "list")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            if action == "register":
                result["data"] = self.register_device(data.get("device_id", ""), data.get("device_type", "generic"), data.get("config"))
            elif action == "read":
                result["data"] = self.read_sensor(data.get("device_id", ""))
            elif action == "write":
                result["data"] = self.write_actuator(data.get("device_id", ""), data.get("value"))
            elif action == "list":
                result["data"] = self.list_devices()
            elif action == "scan":
                result["data"] = self.scan_for_devices()
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("Hardware command failed")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("hardware.status.update", result)
