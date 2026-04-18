"""
Kingdom AI — BLE Health Manager
SOTA 2026: Real-time Bluetooth Low Energy heart rate streaming via Bleak.

Provides sub-second latency vitals from any BLE heart rate monitor or
compatible smartwatch within Bluetooth range. Works without internet.

Uses the standard Heart Rate Service (UUID 0x180D) GATT profile.
Dormant until protection flag "ble_streaming" is activated.
"""
import asyncio
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

HAS_BLEAK = False
try:
    from bleak import BleakClient, BleakScanner
    HAS_BLEAK = True
except ImportError:
    pass

# Standard BLE UUIDs
HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"


def _parse_heart_rate(data: bytearray) -> Dict[str, Any]:
    """Parse BLE Heart Rate Measurement characteristic value."""
    flags = data[0]
    hr_format_16bit = flags & 0x01
    sensor_contact = (flags >> 1) & 0x03
    energy_expended = (flags >> 3) & 0x01
    rr_interval_present = (flags >> 4) & 0x01

    offset = 1
    if hr_format_16bit:
        heart_rate = int.from_bytes(data[offset:offset + 2], byteorder="little")
        offset += 2
    else:
        heart_rate = data[offset]
        offset += 1

    result: Dict[str, Any] = {
        "heart_rate": heart_rate,
        "sensor_contact": sensor_contact == 3,
    }

    if energy_expended and offset + 2 <= len(data):
        result["energy_expended_kj"] = int.from_bytes(data[offset:offset + 2], byteorder="little")
        offset += 2

    if rr_interval_present:
        rr_intervals = []
        while offset + 2 <= len(data):
            rr_raw = int.from_bytes(data[offset:offset + 2], byteorder="little")
            rr_ms = round(rr_raw * 1000 / 1024)
            rr_intervals.append(rr_ms)
            offset += 2
        result["rr_intervals_ms"] = rr_intervals

    return result


class BLEHealthManager(BaseComponent):
    """
    Manages BLE connections to heart rate monitors and wearable devices.

    Scans for BLE HR devices, connects, and streams real-time heart rate
    data with sub-second latency directly to KAI's event bus.
    """

    def __init__(self, config=None, event_bus=None, on_heart_rate: Optional[Callable] = None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self._on_heart_rate_callback = on_heart_rate

        self._connected_device: Optional[str] = None
        self._client: Optional[Any] = None  # BleakClient
        self._streaming = False
        self._stream_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._discovered_devices: List[Dict] = []
        self._lock = threading.Lock()

        self._subscribe_events()
        self._initialized = True
        logger.info("BLEHealthManager initialized (bleak=%s)", HAS_BLEAK)

    # ------------------------------------------------------------------
    # Device scanning
    # ------------------------------------------------------------------

    async def scan_devices(self, timeout: float = 10.0) -> List[Dict]:
        """Scan for BLE heart rate monitors."""
        if not HAS_BLEAK:
            logger.warning("Bleak not installed — BLE scanning unavailable")
            return []

        devices: List[Dict] = []
        try:
            scanner = BleakScanner()
            discovered = await scanner.discover(timeout=timeout)

            for device in discovered:
                # Check if device advertises Heart Rate Service
                has_hr = False
                if device.metadata and "uuids" in device.metadata:
                    has_hr = HEART_RATE_SERVICE_UUID in device.metadata["uuids"]

                info = {
                    "address": device.address,
                    "name": device.name or "Unknown",
                    "rssi": device.rssi if hasattr(device, "rssi") else None,
                    "has_heart_rate": has_hr,
                }
                devices.append(info)

            # Sort: HR devices first, then by signal strength
            devices.sort(key=lambda d: (not d["has_heart_rate"], -(d.get("rssi") or -100)))

        except Exception as e:
            logger.error("BLE scan error: %s", e)

        with self._lock:
            self._discovered_devices = devices

        if self.event_bus:
            self.event_bus.publish("health.ble.scan_results", {"devices": devices})

        logger.info("BLE scan found %d devices (%d with HR)", len(devices), sum(1 for d in devices if d["has_heart_rate"]))
        return devices

    def scan_devices_sync(self, timeout: float = 10.0) -> List[Dict]:
        """Synchronous wrapper for scan_devices."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.scan_devices(timeout))
        finally:
            loop.close()

    # ------------------------------------------------------------------
    # Connection + streaming
    # ------------------------------------------------------------------

    async def connect_and_stream(self, address: str) -> bool:
        """Connect to a BLE HR device and start streaming heart rate."""
        if not HAS_BLEAK:
            return False

        try:
            client = BleakClient(address)
            await client.connect()

            if not client.is_connected:
                logger.error("Failed to connect to BLE device: %s", address)
                return False

            self._client = client
            self._connected_device = address
            self._streaming = True

            # Start notification for Heart Rate Measurement
            await client.start_notify(HEART_RATE_MEASUREMENT_UUID, self._hr_notification_handler)

            logger.info("BLE HR streaming started from %s", address)

            if self.event_bus:
                self.event_bus.publish("health.ble.connected", {"address": address})

            # Keep connection alive
            while self._streaming and client.is_connected:
                await asyncio.sleep(1)

            # Cleanup
            if client.is_connected:
                await client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
                await client.disconnect()

            self._connected_device = None
            self._client = None

            if self.event_bus:
                self.event_bus.publish("health.ble.disconnected", {"address": address})

            return True

        except Exception as e:
            logger.error("BLE connection error: %s", e)
            self._streaming = False
            self._connected_device = None
            self._client = None
            return False

    def start_streaming(self, address: str) -> bool:
        """Start BLE streaming in background thread."""
        if self._streaming:
            logger.warning("BLE streaming already active")
            return False

        def _run():
            loop = asyncio.new_event_loop()
            self._loop = loop
            try:
                loop.run_until_complete(self.connect_and_stream(address))
            finally:
                loop.close()
                self._loop = None

        self._stream_thread = threading.Thread(target=_run, daemon=True, name="BLEStream")
        self._stream_thread.start()
        return True

    def stop_streaming(self) -> None:
        """Stop BLE streaming."""
        self._streaming = False
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=5)
        logger.info("BLE streaming stopped")

    def _hr_notification_handler(self, sender: Any, data: bytearray) -> None:
        """Handle incoming BLE heart rate notification."""
        try:
            parsed = _parse_heart_rate(data)
            hr = parsed.get("heart_rate", 0)

            if hr > 0:
                # Callback to WearableHub
                if self._on_heart_rate_callback:
                    self._on_heart_rate_callback(hr)

                # Publish via event bus
                if self.event_bus:
                    self.event_bus.publish("health.hr.realtime", {
                        "heart_rate": hr,
                        "source": "ble",
                        "sensor_contact": parsed.get("sensor_contact", False),
                        "rr_intervals_ms": parsed.get("rr_intervals_ms", []),
                    })

        except Exception as e:
            logger.debug("BLE HR parse error: %s", e)

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("health.ble.scan", self._handle_scan)
        self.event_bus.subscribe("health.ble.connect", self._handle_connect)
        self.event_bus.subscribe("health.ble.disconnect", self._handle_disconnect)

    def _handle_scan(self, data: Any) -> None:
        timeout = 10.0
        if isinstance(data, dict):
            timeout = data.get("timeout", 10.0)
        threading.Thread(target=self.scan_devices_sync, args=(timeout,), daemon=True).start()

    def _handle_connect(self, data: Any) -> None:
        if isinstance(data, dict):
            address = data.get("address", "")
            if address:
                self.start_streaming(address)

    def _handle_disconnect(self, data: Any) -> None:
        self.stop_streaming()

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self.stop_streaming()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "bleak_available": HAS_BLEAK,
            "streaming": self._streaming,
            "connected_device": self._connected_device,
            "discovered_devices": len(self._discovered_devices),
        }
