#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.device_onboarding
──────────────────────
Zero-config first-run device onboarding.

What this solves
----------------
When a fresh Kingdom AI install boots up for the first time, the user
should be able to turn on their headset, plug in their webcam, pair
their Bluetooth earbuds, and have Kingdom AI find them without ever
touching code or config. This module is the engine that does that.

It binds three things together:

1. ``HostDeviceManager.scan_all_devices()`` — the existing, cross-
   platform detector for USB / serial / Bluetooth / audio / webcam /
   VR / SDR / network / microcontrollers / automotive / LiDAR / lab /
   imaging / drones / Kingdom-native devices.
2. ``install_identity`` — so every discovered device is stamped with
   the current install's ``user_id``. A consumer never sees devices
   from any other install, and their devices never bleed out.
3. The event bus — so the Devices tab, the VR streamer, the Silent
   Alarm, the Health dashboard and everything else that cares about
   devices can react to the onboarding results the moment they land.

Public API
----------
``DeviceOnboardingEngine(event_bus).run_initial_scan()`` — returns an
``OnboardingResult`` dataclass with a per-category list of newly
discovered devices.

``DeviceOnboardingEngine(event_bus).list_inventory()`` — returns the
current install's device inventory (cached on disk under
``config/device_inventory.json``), so the UI can fill the Devices tab
instantly on every subsequent boot.

``pair_device(device_id)`` / ``forget_device(device_id)`` — approve or
drop a discovered device. Pairing emits ``device.paired`` on the bus
with the install's ``user_id`` attached, which is what lets the VR
streamer automatically route that headset's content to the correct
``VRClientSession``.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.install_identity import get_install_identity

logger = logging.getLogger("KingdomAI.DeviceOnboarding")

_INVENTORY_FILE = "device_inventory.json"
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass
class DiscoveredDevice:
    """A device Kingdom AI found during a scan.

    We keep the shape small and JSON-serialisable so it can flow
    through the event bus, the UI, and the on-disk inventory without
    translation.
    """

    device_id: str
    category: str  # usb, bluetooth, audio, webcam, vr, serial, ...
    name: str
    vendor: str = ""
    status: str = "discovered"  # discovered | paired | ignored
    user_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OnboardingResult:
    """Outcome of a single scan pass."""

    scan_started_at: float
    scan_completed_at: float
    categories: Dict[str, List[DiscoveredDevice]] = field(default_factory=dict)
    total_devices: int = 0
    user_id: str = ""
    installation_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan_started_at": self.scan_started_at,
            "scan_completed_at": self.scan_completed_at,
            "total_devices": self.total_devices,
            "user_id": self.user_id,
            "installation_id": self.installation_id,
            "categories": {
                cat: [d.to_dict() for d in devs] for cat, devs in self.categories.items()
            },
        }


class DeviceOnboardingEngine:
    """Headless engine that drives first-run device discovery.

    A GUI wizard can hold an instance of this and call
    ``run_initial_scan()`` when the user clicks "Find my devices".
    A headless consumer can call the same method at boot and we'll
    auto-populate the Devices tab without any user interaction.
    """

    def __init__(
        self,
        event_bus: Any = None,
        config_dir: Optional[Path] = None,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.event_bus = event_bus
        self.config_dir = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._progress_cb = progress_cb or (lambda msg: None)
        self._lock = threading.Lock()
        self._host_mgr = None  # lazy

    # ───────────────────────────────────────────────────────────────────
    # Inventory persistence (per-install, NEVER shared)
    # ───────────────────────────────────────────────────────────────────

    @property
    def _inventory_path(self) -> Path:
        return self.config_dir / _INVENTORY_FILE

    def _load_inventory(self) -> Dict[str, DiscoveredDevice]:
        p = self._inventory_path
        if not p.exists():
            return {}
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Inventory unreadable (%s); starting fresh.", e)
            return {}
        out: Dict[str, DiscoveredDevice] = {}
        for entry in raw.get("devices", []):
            try:
                out[entry["device_id"]] = DiscoveredDevice(**entry)
            except Exception:
                continue
        return out

    def _save_inventory(self, inv: Dict[str, DiscoveredDevice]) -> None:
        identity = get_install_identity(self.config_dir)
        payload = {
            "installation_id": identity.installation_id,
            "user_id": identity.user_id,
            "saved_at": time.time(),
            "devices": [d.to_dict() for d in inv.values()],
        }
        tmp = self._inventory_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self._inventory_path)

    def list_inventory(self) -> List[DiscoveredDevice]:
        with self._lock:
            return list(self._load_inventory().values())

    # ───────────────────────────────────────────────────────────────────
    # Host device manager (lazy so imports don't fire on module load)
    # ───────────────────────────────────────────────────────────────────

    def _get_host_manager(self) -> Any:
        if self._host_mgr is None:
            try:
                from core.host_device_manager import get_host_device_manager

                self._host_mgr = get_host_device_manager(event_bus=self.event_bus)
            except Exception as e:
                logger.warning("HostDeviceManager unavailable (%s); scans will be empty.", e)
                self._host_mgr = False
        return self._host_mgr

    # ───────────────────────────────────────────────────────────────────
    # Public scan API
    # ───────────────────────────────────────────────────────────────────

    def run_initial_scan(self, *, force: bool = False) -> OnboardingResult:
        """Scan every supported device category on THIS machine.

        ``force=True`` re-runs even if an inventory already exists.
        Otherwise, if the user already saw the first-run wizard, we
        return the cached inventory and skip the heavy scan.
        """
        identity = get_install_identity(self.config_dir)
        started = time.time()

        with self._lock:
            existing = self._load_inventory()
        if existing and not force:
            logger.info(
                "📦 Using cached device inventory (%d devices). Use force=True to rescan.",
                len(existing),
            )
            return OnboardingResult(
                scan_started_at=started,
                scan_completed_at=time.time(),
                categories={
                    "cached": list(existing.values()),
                },
                total_devices=len(existing),
                user_id=identity.user_id,
                installation_id=identity.installation_id,
            )

        self._progress_cb("Turn on your headset, webcam, and Bluetooth devices…")
        self._publish_event("device.onboarding.started", {
            "user_id": identity.user_id,
            "installation_id": identity.installation_id,
            "started_at": started,
        })

        host = self._get_host_manager()
        categories: Dict[str, List[DiscoveredDevice]] = {}
        total = 0

        if host:
            try:
                raw = host.scan_all_devices()
            except Exception as e:
                logger.exception("scan_all_devices() failed: %s", e)
                raw = {}
        else:
            raw = {}

        self._progress_cb("Reading connected devices…")

        for cat, devices in (raw or {}).items():
            bucket: List[DiscoveredDevice] = []
            for dev in devices or []:
                dd = self._normalise(dev, cat, identity.user_id)
                if dd is None:
                    continue
                bucket.append(dd)
                total += 1
                self._publish_event("device.discovered", dd.to_dict())
            if bucket:
                categories[cat] = bucket

        # Persist
        new_inv: Dict[str, DiscoveredDevice] = {}
        for bucket in categories.values():
            for d in bucket:
                new_inv[d.device_id] = d
        with self._lock:
            self._save_inventory(new_inv)

        completed = time.time()
        self._progress_cb(f"Found {total} devices across {len(categories)} categories.")

        result = OnboardingResult(
            scan_started_at=started,
            scan_completed_at=completed,
            categories=categories,
            total_devices=total,
            user_id=identity.user_id,
            installation_id=identity.installation_id,
        )

        self._publish_event("device.onboarding.completed", result.to_dict())
        logger.info(
            "📦 Device onboarding complete: %d devices in %d categories (user_id=%s)",
            total,
            len(categories),
            identity.user_id,
        )
        return result

    def _normalise(self, raw: Any, category: str, user_id: str) -> Optional[DiscoveredDevice]:
        """Turn whatever HostDeviceManager returned into a DiscoveredDevice."""
        try:
            if hasattr(raw, "to_dict"):
                data = raw.to_dict()
            elif isinstance(raw, dict):
                data = dict(raw)
            else:
                # unknown shape — use repr as name, synth id
                return DiscoveredDevice(
                    device_id=f"{category}:{abs(hash(repr(raw))) & 0xFFFFFFFF:x}",
                    category=category,
                    name=str(raw)[:80],
                    user_id=user_id,
                )

            device_id = str(
                data.get("device_id")
                or data.get("id")
                or f"{category}:{abs(hash(json.dumps(data, sort_keys=True, default=str))) & 0xFFFFFFFF:x}"
            )
            name = str(data.get("name") or data.get("product") or data.get("model") or "Unknown device")
            vendor = str(data.get("vendor") or data.get("manufacturer") or "")
            return DiscoveredDevice(
                device_id=device_id,
                category=category,
                name=name,
                vendor=vendor,
                status="discovered",
                user_id=user_id,
                metadata={k: v for k, v in data.items() if k not in {"device_id", "id", "name", "vendor", "manufacturer"}},
            )
        except Exception as e:
            logger.debug("Could not normalise raw device (%s): %s", category, e)
            return None

    # ───────────────────────────────────────────────────────────────────
    # Pair / forget / rescan — the three user verbs
    # ───────────────────────────────────────────────────────────────────

    def pair_device(self, device_id: str) -> bool:
        """Mark a discovered device as paired to this install's user.

        Emits ``device.paired`` with ``user_id`` attached so every
        downstream service (VRHeadsetStreamer, Silent Alarm, Health
        dashboard) automatically binds that device to the correct
        user session.
        """
        identity = get_install_identity(self.config_dir)
        with self._lock:
            inv = self._load_inventory()
            if device_id not in inv:
                logger.warning("pair_device: unknown device_id=%s", device_id)
                return False
            dev = inv[device_id]
            dev.status = "paired"
            dev.user_id = identity.user_id
            self._save_inventory(inv)

        self._publish_event("device.paired", {
            **dev.to_dict(),
            "installation_id": identity.installation_id,
        })
        logger.info("🔗 Paired %s (%s) to user %s", dev.name, dev.category, identity.user_id)
        return True

    def forget_device(self, device_id: str) -> bool:
        """Drop a device from the inventory entirely."""
        with self._lock:
            inv = self._load_inventory()
            if device_id not in inv:
                return False
            removed = inv.pop(device_id)
            self._save_inventory(inv)
        self._publish_event("device.forgotten", removed.to_dict())
        logger.info("🗑  Forgot %s (%s)", removed.name, removed.category)
        return True

    def rescan(self) -> OnboardingResult:
        """Force a fresh scan, merging any new devices into the existing
        inventory (keeps previously-paired devices)."""
        with self._lock:
            existing = self._load_inventory()
        fresh = self.run_initial_scan(force=True)
        # Merge: preserve 'paired' status on known devices
        with self._lock:
            inv = self._load_inventory()
            for dev_id, prev in existing.items():
                if dev_id in inv and prev.status == "paired":
                    inv[dev_id].status = "paired"
                    inv[dev_id].user_id = prev.user_id
            self._save_inventory(inv)
        return fresh

    # ───────────────────────────────────────────────────────────────────
    # Event bus publishing
    # ───────────────────────────────────────────────────────────────────

    def _publish_event(self, name: str, data: Dict[str, Any]) -> None:
        if not self.event_bus:
            return
        try:
            self.event_bus.publish(name, data)
        except Exception as e:
            logger.debug("Event publish %s failed (non-fatal): %s", name, e)


_engine: Optional[DeviceOnboardingEngine] = None
_engine_lock = threading.Lock()


def get_device_onboarding_engine(event_bus: Any = None) -> DeviceOnboardingEngine:
    """Process-wide singleton accessor. Safe to call from anywhere."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = DeviceOnboardingEngine(event_bus=event_bus)
    return _engine


__all__ = [
    "DeviceOnboardingEngine",
    "DiscoveredDevice",
    "OnboardingResult",
    "get_device_onboarding_engine",
]
