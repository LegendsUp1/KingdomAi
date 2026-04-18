import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.base_component import BaseComponent
from core.comms_call_backend import UDPAudioCallBackend
from core.comms_rf_backend import SoapySDRRadioBackend

logger = logging.getLogger(__name__)


@dataclass
class SonarMetrics:
    distance_cm: float = -1.0
    rms: float = 0.0
    peak_hz: Optional[float] = None
    timestamp: float = 0.0
    device_id: Optional[str] = None
    backend: str = "none"


class CommunicationCapabilities(BaseComponent):
    def __init__(self, name: str = "CommunicationCapabilities", event_bus=None, config: Any = None):
        super().__init__(name=name, event_bus=event_bus, config=config)
        self._sonar_thread: Optional[threading.Thread] = None
        self._sonar_stop = threading.Event()
        self._sonar_metrics = SonarMetrics()
        self._sonar_backend = "none"
        self._sonar_device_id: Optional[str] = None
        self._sonar_device_port: Optional[str] = None

        self._radio_backend = SoapySDRRadioBackend(event_bus=self.event_bus, publish_chat=self._publish_chat)
        self._call_backend = UDPAudioCallBackend(event_bus=self.event_bus, publish_chat=self._publish_chat)

        try:
            if self.event_bus and hasattr(self.event_bus, "register_component"):
                self.event_bus.register_component("communication_capabilities", self)
        except Exception:
            self.logger.exception("Failed to register communication_capabilities")

    def subscribe_to_events(self) -> None:
        if not self.event_bus:
            return

        try:
            self._radio_backend.event_bus = self.event_bus
        except Exception:
            pass

        try:
            self._call_backend.event_bus = self.event_bus
        except Exception:
            pass

        self.subscribe_sync("comms.scan", self._on_scan)
        self.subscribe_sync("comms.status.request", self._on_status_request)
        self.subscribe_sync("comms.video.start", self._on_video_start)
        self.subscribe_sync("comms.video.stop", self._on_video_stop)
        self.subscribe_sync("comms.sonar.start", self._on_sonar_start)
        self.subscribe_sync("comms.sonar.stop", self._on_sonar_stop)
        self.subscribe_sync("comms.radio.transmit", self._on_radio_transmit)
        self.subscribe_sync("comms.radio.receive.start", self._on_radio_receive_start)
        self.subscribe_sync("comms.radio.receive.stop", self._on_radio_receive_stop)
        self.subscribe_sync("comms.call.start", self._on_call_start)
        self.subscribe_sync("comms.call.stop", self._on_call_stop)
        self.subscribe_sync("comms.call.status.request", self._on_call_status_request)

    def get_capabilities_summary(self) -> Dict[str, Any]:
        scan = self.scan_interfaces()
        return {
            "interfaces": scan,
            "radio": self._radio_backend.get_status() if self._radio_backend else {},
            "call": self._call_backend.get_status() if self._call_backend else {},
            "sonar": {
                "listening": bool(self._sonar_thread and self._sonar_thread.is_alive()),
                "backend": self._sonar_backend,
                "device_id": self._sonar_device_id,
                "last": {
                    "distance_cm": self._sonar_metrics.distance_cm,
                    "rms": self._sonar_metrics.rms,
                    "peak_hz": self._sonar_metrics.peak_hz,
                    "timestamp": self._sonar_metrics.timestamp,
                },
            },
        }

    def _publish_chat(self, text: str, role: str = "assistant") -> None:
        if not self.event_bus:
            return
        try:
            self.event_bus.publish(
                "chat.message.add",
                {"content": text, "role": role, "source": "CommunicationCapabilities"},
            )
        except Exception:
            return

    def _on_scan(self, _payload: Any = None) -> None:
        info = self.scan_interfaces()
        self._publish_chat(self._format_scan(info))
        try:
            if self.event_bus:
                self.event_bus.publish("comms.scan.response", {"success": True, "data": info})
        except Exception:
            pass

    def _on_status_request(self, _payload: Any = None) -> None:
        status = self.get_capabilities_summary()
        try:
            if self.event_bus:
                self.event_bus.publish("comms.status.response", {"success": True, "data": status})
        except Exception:
            pass
        self._publish_chat(self._format_status(status))

    def _on_video_start(self, payload: Any = None) -> None:
        url = None
        if isinstance(payload, dict):
            url = payload.get("url")
        if self.event_bus:
            self.event_bus.publish("vision.stream.start", {"url": url} if url else {})
        self._publish_chat(f"Video stream start requested{f' ({url})' if url else ''}.")

    def _on_video_stop(self, _payload: Any = None) -> None:
        if self.event_bus:
            self.event_bus.publish("vision.stream.stop", {})
        self._publish_chat("Video stream stop requested.")

    def _on_sonar_start(self, payload: Any = None) -> None:
        if self._sonar_thread and self._sonar_thread.is_alive():
            self._publish_chat("Sonar already active.")
            return

        device_id = None
        trigger_pin = "D2"
        echo_pin = "D3"
        interval_ms = 500
        
        if isinstance(payload, dict):
            device_id = payload.get("device_id") or payload.get("device")
            trigger_pin = payload.get("trigger_pin") or payload.get("trig") or trigger_pin
            echo_pin = payload.get("echo_pin") or payload.get("echo") or echo_pin
            interval_ms = int(payload.get("interval_ms") or payload.get("interval") or interval_ms)

        if not device_id:
            self._publish_chat("Sonar start failed: no device_id specified. Use comms.sonar.start with {device_id: 'your_device_id'}")
            if self.event_bus:
                self.event_bus.publish("comms.sonar.start.response", {
                    "success": False,
                    "error": "missing_device_id",
                    "hint": "Specify device_id in payload. Use list_taken_over_devices to see available devices."
                })
            return

        self._sonar_device_id = device_id
        self._sonar_stop.clear()
        self._sonar_thread = threading.Thread(
            target=self._sonar_device_loop,
            kwargs={
                "device_id": device_id,
                "trigger_pin": trigger_pin,
                "echo_pin": echo_pin,
                "interval_ms": interval_ms
            },
            daemon=True,
            name="CommsSonarDeviceThread",
        )
        self._sonar_thread.start()
        self._publish_chat(f"Sonar started on device {device_id} (hardware ultrasonic sensor).")
        if self.event_bus:
            self.event_bus.publish("comms.sonar.start.response", {
                "success": True,
                "device_id": device_id,
                "trigger_pin": trigger_pin,
                "echo_pin": echo_pin
            })

    def _on_sonar_stop(self, _payload: Any = None) -> None:
        self._sonar_stop.set()
        t = self._sonar_thread
        if t and t.is_alive():
            t.join(timeout=2.0)
        self._publish_chat("Sonar listen stopped.")

    def _sonar_device_loop(self, device_id: str, trigger_pin: str, echo_pin: str, interval_ms: int) -> None:
        """Device-driven sonar loop using DeviceTakeoverManager.
        
        SOTA 2026: Sends SONAR commands to a taken-over device (microcontroller with
        HC-SR04 or similar ultrasonic sensor) and publishes distance metrics.
        """
        self._sonar_backend = "device_takeover"
        
        host_device_manager = None
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                host_device_manager = self.event_bus.get_component('host_device_manager', silent=True)
            if not host_device_manager:
                from core.host_device_manager import get_host_device_manager
                host_device_manager = get_host_device_manager()
        except Exception as e:
            self._publish_chat(f"Sonar error: Could not get HostDeviceManager: {e}")
            self._sonar_backend = "none"
            return
        
        if not host_device_manager:
            self._publish_chat("Sonar error: HostDeviceManager not available.")
            self._sonar_backend = "none"
            return
        
        takeover_manager = getattr(host_device_manager, '_takeover_manager', None)
        if not takeover_manager:
            self._publish_chat("Sonar error: DeviceTakeoverManager not available.")
            self._sonar_backend = "none"
            return
        
        if not takeover_manager.is_device_taken_over(device_id):
            self._publish_chat(f"Device {device_id} not taken over. Initiating takeover...")
            try:
                takeover_manager.auto_takeover_device(device_id)
                time.sleep(2.0)
            except Exception as e:
                self._publish_chat(f"Sonar error: Could not takeover device {device_id}: {e}")
                self._sonar_backend = "none"
                return
        
        init_result = takeover_manager.send_device_command(
            device_id, f"SONAR_INIT:{trigger_pin},{echo_pin}"
        )
        if not init_result.get("success"):
            self._publish_chat(f"Sonar init failed on {device_id}: {init_result.get('error', 'unknown')}")
            self._sonar_backend = "none"
            return
        
        self._publish_chat(f"Sonar initialized on {device_id} (TRIG={trigger_pin}, ECHO={echo_pin})")
        
        interval_sec = max(0.1, interval_ms / 1000.0)
        last_publish = 0.0
        
        while not self._sonar_stop.is_set():
            try:
                result = takeover_manager.send_device_command(device_id, "SONAR")
                
                if result.get("success"):
                    response = result.get("response", "")
                    distance_cm = self._parse_sonar_response(response)
                    
                    self._sonar_metrics = SonarMetrics(
                        distance_cm=distance_cm,
                        rms=0.0,
                        peak_hz=None,
                        timestamp=time.time(),
                        device_id=device_id,
                        backend="device_takeover"
                    )
                    
                    now = time.time()
                    if self.event_bus and now - last_publish > 0.5:
                        last_publish = now
                        self.event_bus.publish(
                            "comms.sonar.metrics",
                            {
                                "distance_cm": distance_cm,
                                "device_id": device_id,
                                "timestamp": self._sonar_metrics.timestamp,
                                "backend": "device_takeover",
                                "raw_response": response,
                            },
                        )
                else:
                    logger.debug(f"Sonar read failed: {result.get('error')}")
                    
            except Exception as e:
                logger.debug(f"Sonar loop error: {e}")
            
            time.sleep(interval_sec)
        
        try:
            takeover_manager.send_device_command(device_id, "SONAR_DISABLE")
        except Exception:
            pass
        
        self._sonar_backend = "none"
        self._sonar_device_id = None

    def _parse_sonar_response(self, response: str) -> float:
        """Parse distance from SONAR command response.
        
        Expected formats:
          - "SONAR: 123.45 cm"
          - "SONAR: OUT_OF_RANGE"
          - "123.45"
        """
        if not response:
            return -1.0
        
        response = response.strip().upper()
        
        if "OUT_OF_RANGE" in response:
            return -1.0
        
        import re
        match = re.search(r'([\d.]+)\s*(?:CM)?', response)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        
        return -1.0

    def _on_radio_transmit(self, payload: Any = None) -> None:
        if not self.event_bus:
            return

        frequency_mhz = None
        sample_rate = 1_000_000
        symbol_rate = 1200
        deviation_hz = 5000
        gain = None
        bandwidth = None
        antenna = None
        channel = 0
        amplitude = 0.35

        payload_bytes = b""
        if isinstance(payload, dict):
            frequency_mhz = payload.get("frequency_mhz")
            if frequency_mhz is None:
                frequency_hz = payload.get("frequency_hz")
                if isinstance(frequency_hz, (int, float)):
                    frequency_mhz = float(frequency_hz) / 1_000_000.0

            sample_rate = int(payload.get("sample_rate") or sample_rate)
            symbol_rate = int(payload.get("symbol_rate") or symbol_rate)
            deviation_hz = int(payload.get("deviation_hz") or deviation_hz)
            gain = payload.get("gain")
            bandwidth = payload.get("bandwidth")
            antenna = payload.get("antenna")
            channel = int(payload.get("channel") or channel)
            amplitude = float(payload.get("amplitude") or amplitude)

            raw = payload.get("payload")
            if isinstance(raw, (bytes, bytearray)):
                payload_bytes = bytes(raw)
            elif raw is None:
                payload_bytes = b""
            else:
                payload_bytes = str(raw).encode("utf-8", errors="replace")
        elif payload is None:
            payload_bytes = b""
        else:
            payload_bytes = str(payload).encode("utf-8", errors="replace")

        if not isinstance(frequency_mhz, (int, float)):
            self.event_bus.publish(
                "comms.radio.transmit.response",
                {"success": False, "error": "missing_frequency_mhz"},
            )
            return

        frequency_hz = float(frequency_mhz) * 1_000_000.0

        ok, err, info = self._radio_backend.transmit_fsk(
            frequency_hz=frequency_hz,
            payload=payload_bytes,
            sample_rate=sample_rate,
            bandwidth=bandwidth,
            gain=gain,
            channel=channel,
            antenna=antenna,
            symbol_rate=symbol_rate,
            deviation_hz=deviation_hz,
            amplitude=amplitude,
        )

        if ok:
            self._publish_chat(f"Radio TX sent {len(payload_bytes)} bytes @ {float(frequency_mhz):.6f} MHz (FSK).")
            self.event_bus.publish("comms.radio.transmit.response", {"success": True, "info": info})
        else:
            self._publish_chat(f"Radio TX failed: {err}")
            self.event_bus.publish("comms.radio.transmit.response", {"success": False, "error": err, "info": info})

    def _on_radio_receive_start(self, payload: Any = None) -> None:
        if not self.event_bus:
            return

        frequency_mhz = None
        sample_rate = 1_000_000
        symbol_rate = 1200
        deviation_hz = 5000
        gain = None
        bandwidth = None
        antenna = None
        channel = 0

        if isinstance(payload, dict):
            frequency_mhz = payload.get("frequency_mhz")
            if frequency_mhz is None:
                frequency_hz = payload.get("frequency_hz")
                if isinstance(frequency_hz, (int, float)):
                    frequency_mhz = float(frequency_hz) / 1_000_000.0

            sample_rate = int(payload.get("sample_rate") or sample_rate)
            symbol_rate = int(payload.get("symbol_rate") or symbol_rate)
            deviation_hz = int(payload.get("deviation_hz") or deviation_hz)
            gain = payload.get("gain")
            bandwidth = payload.get("bandwidth")
            antenna = payload.get("antenna")
            channel = int(payload.get("channel") or channel)

        if not isinstance(frequency_mhz, (int, float)):
            self.event_bus.publish(
                "comms.radio.receive.start.response",
                {"success": False, "error": "missing_frequency_mhz"},
            )
            return

        frequency_hz = float(frequency_mhz) * 1_000_000.0

        ok, err, info = self._radio_backend.start_rx(
            frequency_hz=frequency_hz,
            sample_rate=sample_rate,
            bandwidth=bandwidth,
            gain=gain,
            channel=channel,
            antenna=antenna,
            symbol_rate=symbol_rate,
            deviation_hz=deviation_hz,
        )

        if ok:
            self._publish_chat(f"Radio RX started @ {float(frequency_mhz):.6f} MHz.")
            self.event_bus.publish("comms.radio.receive.start.response", {"success": True, "info": info})
        else:
            self._publish_chat(f"Radio RX failed: {err}")
            self.event_bus.publish("comms.radio.receive.start.response", {"success": False, "error": err, "info": info})

    def _on_radio_receive_stop(self, _payload: Any = None) -> None:
        if not self.event_bus:
            return

        try:
            self._radio_backend.stop_rx()
        except Exception as e:
            self._publish_chat(f"Radio RX stop error: {e}")
            self.event_bus.publish("comms.radio.receive.stop.response", {"success": False, "error": str(e)})
            return

        self._publish_chat("Radio RX stopped.")
        self.event_bus.publish("comms.radio.receive.stop.response", {"success": True})

    def _on_call_start(self, payload: Any = None) -> None:
        if not self.event_bus:
            return

        remote_host = None
        remote_port = None
        local_port = None
        sample_rate = 48000
        blocksize = 960
        channels = 1

        if isinstance(payload, dict):
            remote_host = payload.get("remote_host") or payload.get("host")
            remote_port = payload.get("remote_port") or payload.get("port")
            local_port = payload.get("local_port")
            sample_rate = int(payload.get("sample_rate") or sample_rate)
            blocksize = int(payload.get("blocksize") or blocksize)
            channels = int(payload.get("channels") or channels)

        if not remote_host or not isinstance(remote_port, (int, float, str)):
            self.event_bus.publish(
                "comms.call.start.response",
                {"success": False, "error": "missing_remote"},
            )
            return

        try:
            remote_port_i = int(remote_port)
        except Exception:
            self.event_bus.publish(
                "comms.call.start.response",
                {"success": False, "error": "invalid_remote_port"},
            )
            return

        if local_port is not None:
            try:
                local_port = int(local_port)
            except Exception:
                local_port = None

        ok, err = self._call_backend.start(
            remote_host=str(remote_host),
            remote_port=remote_port_i,
            local_port=local_port,
            sample_rate=sample_rate,
            blocksize=blocksize,
            channels=channels,
        )

        if ok:
            self._publish_chat(f"Call started (UDP voice) to {remote_host}:{remote_port_i}.")
            self.event_bus.publish(
                "comms.call.start.response",
                {"success": True, "data": self._call_backend.get_status()},
            )
        else:
            self._publish_chat(f"Call start failed: {err}")
            self.event_bus.publish(
                "comms.call.start.response",
                {"success": False, "error": err, "data": self._call_backend.get_status()},
            )

    def _on_call_stop(self, _payload: Any = None) -> None:
        if not self.event_bus:
            return

        try:
            self._call_backend.stop()
        except Exception as e:
            self._publish_chat(f"Call stop error: {e}")
            self.event_bus.publish("comms.call.stop.response", {"success": False, "error": str(e)})
            return

        self._publish_chat("Call stopped.")
        self.event_bus.publish(
            "comms.call.stop.response",
            {"success": True, "data": self._call_backend.get_status()},
        )

    def _on_call_status_request(self, _payload: Any = None) -> None:
        if not self.event_bus:
            return
        self.event_bus.publish(
            "comms.call.status.response",
            {"success": True, "data": self._call_backend.get_status()},
        )

    def scan_interfaces(self) -> Dict[str, Any]:
        """Scan all communication interfaces using HostDeviceManager unified detection.
        
        SOTA 2026: Integrates with HostDeviceManager for unified device inventory
        and includes 'devices needed' guidance for missing hardware.
        """
        mic = None
        webcam = None
        try:
            from config.windows_audio_devices import get_default_microphone, get_default_webcam

            mic = get_default_microphone()
            webcam = get_default_webcam()
        except Exception:
            pass

        mjpeg_url = os.environ.get("KINGDOM_VISION_URL")
        if not mjpeg_url:
            host = self._get_windows_host_ip_default()
            mjpeg_url = f"http://{host}:8090/brio.mjpg"

        sdr_tools = {
            "rtl_test": bool(shutil.which("rtl_test")),
            "rtl_sdr": bool(shutil.which("rtl_sdr")),
            "rtl_fm": bool(shutil.which("rtl_fm")),
            "hackrf_info": bool(shutil.which("hackrf_info")),
            "hackrf_transfer": bool(shutil.which("hackrf_transfer")),
            "uhd_find_devices": bool(shutil.which("uhd_find_devices")),
            "gnuradio-companion": bool(shutil.which("gnuradio-companion")),
        }

        python_sdr = {
            "pyrtlsdr": self._has_python_module("rtlsdr"),
            "SoapySDR": self._has_python_module("SoapySDR"),
            "gnuradio": self._has_python_module("gnuradio"),
        }

        soapy_devices: List[Dict[str, Any]] = []
        try:
            soapy_devices = self._radio_backend.enumerate_devices()
        except Exception:
            soapy_devices = []

        call_supported = self._has_python_module("sounddevice")

        # SOTA 2026: Get unified device inventory from HostDeviceManager
        device_inventory = {}
        devices_needed = {}
        try:
            host_device_manager = None
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                host_device_manager = self.event_bus.get_component('host_device_manager', silent=True)
            
            if not host_device_manager:
                try:
                    from core.host_device_manager import get_host_device_manager
                    host_device_manager = get_host_device_manager()
                except Exception:
                    pass
            
            if host_device_manager:
                # Get AI-friendly inventory summary
                device_inventory = host_device_manager.get_inventory_for_ai_context()
                # Get detailed devices needed guidance
                devices_needed = host_device_manager.get_devices_needed_guidance()
        except Exception as e:
            logger.debug(f"Could not get device inventory: {e}")

        return {
            "audio": {"default_mic_index": mic},
            "video": {"default_webcam_index": webcam, "mjpeg_url": mjpeg_url},
            "radio": {"sdr_tools": sdr_tools, "python_modules": python_sdr, "soapy_devices": soapy_devices},
            "call": {"udp_voice": {"supported": call_supported}},
            "device_inventory": device_inventory,
            "devices_needed": devices_needed,
        }

    def _has_python_module(self, module_name: str) -> bool:
        try:
            __import__(module_name)
            return True
        except Exception:
            return False

    def _get_windows_host_ip_default(self) -> str:
        try:
            with open("/proc/version", "r", encoding="utf-8") as f:
                v = f.read().lower()
                if "microsoft" not in v and "wsl" not in v:
                    return "127.0.0.1"
        except Exception:
            return "127.0.0.1"

        try:
            with open("/etc/resolv.conf", "r", encoding="utf-8") as rf:
                for line in rf:
                    if line.strip().startswith("nameserver"):
                        return line.strip().split()[1]
        except Exception:
            return "127.0.0.1"

        return "127.0.0.1"

    def _format_scan(self, info: Dict[str, Any]) -> str:
        audio = info.get("audio", {})
        video = info.get("video", {})
        radio = info.get("radio", {})
        call = info.get("call", {})

        sdr_tools = radio.get("sdr_tools", {})
        python_mods = radio.get("python_modules", {})

        tools_present = [k for k, v in sdr_tools.items() if v]
        mods_present = [k for k, v in python_mods.items() if v]

        lines = []
        lines.append("COMMUNICATION SCAN")
        lines.append("")
        lines.append(f"Audio: default mic index = {audio.get('default_mic_index')}")
        lines.append(f"Video: default webcam index = {video.get('default_webcam_index')}")
        lines.append(f"Video: MJPEG URL = {video.get('mjpeg_url')}")
        lines.append("")
        lines.append(f"Radio/SDR tools detected = {tools_present if tools_present else 'none'}")
        lines.append(f"Radio/SDR python modules detected = {mods_present if mods_present else 'none'}")
        try:
            soapy = radio.get("soapy_devices") if isinstance(radio, dict) else None
        except Exception:
            soapy = None
        if isinstance(soapy, list):
            lines.append(f"Radio/SoapySDR devices detected = {len(soapy)}")
            if soapy:
                lines.append(f"Radio/SoapySDR first device = {soapy[0]}")
        lines.append("")
        udp_voice = None
        if isinstance(call, dict):
            udp_voice = call.get("udp_voice")
        supported = None
        if isinstance(udp_voice, dict):
            supported = udp_voice.get("supported")
        lines.append(f"Call (UDP voice) supported = {supported}")
        lines.append("")
        
        # SOTA 2026: Device inventory and devices needed guidance
        device_inventory = info.get("device_inventory", {})
        devices_needed = info.get("devices_needed", {})
        
        if device_inventory:
            lines.append("DEVICE INVENTORY")
            lines.append(f"Total devices: {device_inventory.get('total_devices', 0)}")
            categories = device_inventory.get('categories', {})
            if categories:
                cat_list = [f"{k}={v}" for k, v in categories.items() if v > 0]
                lines.append(f"Categories: {', '.join(cat_list) if cat_list else 'none'}")
            if device_inventory.get('wsl2_mode'):
                lines.append("Mode: WSL2 (Windows host devices via PowerShell)")
            lines.append("")
        
        if devices_needed:
            available = devices_needed.get("available_features", [])
            unavailable = devices_needed.get("unavailable_features", [])
            recommendations = devices_needed.get("recommendations", [])
            
            if available:
                lines.append("AVAILABLE FEATURES (hardware present):")
                for feat in available[:5]:
                    lines.append(f"  ✓ {feat.get('feature', 'unknown')}: {feat.get('description', '')}")
            
            if unavailable:
                lines.append("")
                lines.append("UNAVAILABLE FEATURES (missing hardware):")
                for feat in unavailable[:5]:
                    missing = feat.get('missing_categories', [])
                    lines.append(f"  ✗ {feat.get('feature', 'unknown')}: needs {', '.join(missing)}")
            
            if recommendations:
                lines.append("")
                lines.append(f"RECOMMENDED HARDWARE: {', '.join(recommendations[:5])}")
            lines.append("")
        
        lines.append("Notes:")
        lines.append("- Video RX is supported via the existing MJPEG -> VisionStream pipeline.")
        lines.append("- Sonar uses hardware ultrasonic sensors (HC-SR04) via device takeover system.")
        lines.append("- Select a taken-over microcontroller device and configure trigger/echo pins.")
        lines.append("- RF TX/RX uses SoapySDR if available (real SDR devices).")
        lines.append("- Calls use LAN UDP voice (peer must run the same feature and ports must match).")
        return "\n".join(lines)

    def _format_status(self, status: Dict[str, Any]) -> str:
        sonar = status.get("sonar", {})
        last = sonar.get("last", {})
        radio = status.get("radio", {})
        call = status.get("call", {})
        return (
            "COMMUNICATION STATUS\n\n"
            f"Sonar listening: {sonar.get('listening')}\n"
            f"Sonar backend: {sonar.get('backend')}\n"
            f"Sonar device: {sonar.get('device_id', 'none')}\n"
            f"Last distance: {last.get('distance_cm', '--')} cm\n"
            f"Last RMS: {last.get('rms')}\n"
            f"Last peak Hz: {last.get('peak_hz')}\n"
            "\n"
            f"Radio available: {radio.get('available')}\n"
            f"Radio opened: {radio.get('opened')}\n"
            f"Radio RX active: {radio.get('rx_active')}\n"
            f"Radio RX error: {radio.get('rx_last_error')}\n"
            f"Radio TX error: {radio.get('tx_last_error')}\n"
            "\n"
            f"Call active: {call.get('active')}\n"
            f"Call remote: {call.get('remote')}\n"
            f"Call local port: {call.get('local_port')}\n"
        )
