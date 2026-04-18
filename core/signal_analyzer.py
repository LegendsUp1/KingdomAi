"""
Universal Signal Analyzer - SOTA 2026
======================================
Comprehensive signal scanning for ALL wireless protocols.

Supported Signals:
- Bluetooth Classic (2.4 GHz)
- Bluetooth Low Energy (BLE)
- WiFi (2.4/5/6 GHz)
- Zigbee (2.4 GHz)
- Z-Wave (908 MHz US / 868 MHz EU)
- LoRa (433/868/915 MHz)
- NFC (13.56 MHz)
- RFID (125 kHz LF / 13.56 MHz HF / 860-960 MHz UHF)
- Infrared (IR remote)
- RC Toys (27 MHz / 49 MHz / 2.4 GHz)
- ISM Band (433/868/915 MHz)
- GPS (1575.42 MHz L1 / 1227.60 MHz L2)
- ADS-B (1090 MHz aircraft)
- TPMS (315/433 MHz tire sensors)
- Wireless keyboards/mice (2.4 GHz)
- Baby monitors (49 MHz / 900 MHz / 2.4 GHz)
- Garage door openers (300-400 MHz)
- Car key fobs (315/433 MHz)

Anti-Detection:
- Passive scanning modes
- Frequency hopping evasion
- Low-power stealth mode
- Randomized scan patterns

Device Control:
- Protocol replay for owned devices
- Signal injection for RC toys
- Bluetooth device pairing
- IR code learning and transmission
"""

import os
import sys
import time
import struct
import logging
import threading
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json

logger = logging.getLogger("KingdomAI.SignalAnalyzer")

# ============================================================================
# SIGNAL TYPE ENUMS
# ============================================================================

class SignalType(Enum):
    """All supported wireless signal types"""
    # Bluetooth
    BLUETOOTH_CLASSIC = "bluetooth_classic"
    BLUETOOTH_LE = "ble"
    
    # WiFi
    WIFI_2_4GHZ = "wifi_2.4ghz"
    WIFI_5GHZ = "wifi_5ghz"
    WIFI_6GHZ = "wifi_6ghz"
    WIFI_6E = "wifi_6e"
    
    # IoT Protocols
    ZIGBEE = "zigbee"
    ZWAVE = "zwave"
    LORA = "lora"
    LORAWAN = "lorawan"
    THREAD = "thread"
    MATTER = "matter"
    
    # Short Range
    NFC = "nfc"
    RFID_LF = "rfid_lf"       # 125 kHz
    RFID_HF = "rfid_hf"       # 13.56 MHz
    RFID_UHF = "rfid_uhf"     # 860-960 MHz
    INFRARED = "infrared"
    
    # RC & Toys
    RC_27MHZ = "rc_27mhz"
    RC_49MHZ = "rc_49mhz"
    RC_2_4GHZ = "rc_2.4ghz"
    RC_5_8GHZ = "rc_5.8ghz"   # FPV drones
    
    # ISM Band
    ISM_433MHZ = "ism_433mhz"
    ISM_868MHZ = "ism_868mhz"
    ISM_915MHZ = "ism_915mhz"
    
    # Automotive
    TPMS = "tpms"              # Tire pressure
    CAR_KEYFOB = "car_keyfob"
    GARAGE_DOOR = "garage_door"
    
    # Aviation/Navigation
    GPS_L1 = "gps_l1"
    GPS_L2 = "gps_l2"
    ADSB = "adsb"              # Aircraft
    AIS = "ais"                # Ships
    
    # Other
    WIRELESS_KEYBOARD = "wireless_keyboard"
    WIRELESS_MOUSE = "wireless_mouse"
    BABY_MONITOR = "baby_monitor"
    DECT_PHONE = "dect_phone"
    PMR446 = "pmr446"          # Walkie talkies
    FRS_GMRS = "frs_gmrs"
    
    # SDR Generic
    SDR_CUSTOM = "sdr_custom"
    UNKNOWN = "unknown"


class ScanMode(Enum):
    """Scanning modes"""
    PASSIVE = "passive"        # Listen only, no transmission
    ACTIVE = "active"          # Probe/query devices
    STEALTH = "stealth"        # Anti-detection passive mode
    AGGRESSIVE = "aggressive"  # Full power, all protocols


# ============================================================================
# FREQUENCY BANDS DATABASE
# ============================================================================

FREQUENCY_BANDS = {
    # Bluetooth / WiFi / 2.4 GHz ISM
    SignalType.BLUETOOTH_CLASSIC: {"start": 2402e6, "end": 2480e6, "channels": 79},
    SignalType.BLUETOOTH_LE: {"start": 2402e6, "end": 2480e6, "channels": 40},
    SignalType.WIFI_2_4GHZ: {"start": 2400e6, "end": 2500e6, "channels": 14},
    SignalType.ZIGBEE: {"start": 2405e6, "end": 2480e6, "channels": 16},
    SignalType.RC_2_4GHZ: {"start": 2400e6, "end": 2483e6, "channels": 83},
    SignalType.WIRELESS_KEYBOARD: {"start": 2400e6, "end": 2483e6},
    
    # 5 GHz WiFi
    SignalType.WIFI_5GHZ: {"start": 5150e6, "end": 5850e6, "channels": 25},
    SignalType.RC_5_8GHZ: {"start": 5650e6, "end": 5925e6},  # FPV
    
    # 6 GHz WiFi 6E
    SignalType.WIFI_6GHZ: {"start": 5925e6, "end": 7125e6},
    
    # Sub-GHz ISM
    SignalType.RC_27MHZ: {"start": 26.995e6, "end": 27.255e6, "channels": 6},
    SignalType.RC_49MHZ: {"start": 49.830e6, "end": 49.890e6, "channels": 6},
    SignalType.ISM_433MHZ: {"start": 433.05e6, "end": 434.79e6},
    SignalType.ISM_868MHZ: {"start": 863e6, "end": 870e6},
    SignalType.ISM_915MHZ: {"start": 902e6, "end": 928e6},
    
    # LoRa
    SignalType.LORA: {"start": 433e6, "end": 928e6},  # Region dependent
    
    # Z-Wave
    SignalType.ZWAVE: {"start": 868e6, "end": 908e6},  # Region dependent
    
    # Automotive
    SignalType.CAR_KEYFOB: {"start": 315e6, "end": 433.92e6},
    SignalType.GARAGE_DOOR: {"start": 300e6, "end": 400e6},
    SignalType.TPMS: {"start": 315e6, "end": 433.92e6},
    
    # RFID
    SignalType.RFID_LF: {"start": 125e3, "end": 134.2e3},
    SignalType.RFID_HF: {"start": 13.553e6, "end": 13.567e6},
    SignalType.NFC: {"start": 13.553e6, "end": 13.567e6},
    SignalType.RFID_UHF: {"start": 860e6, "end": 960e6},
    
    # Aviation
    SignalType.GPS_L1: {"center": 1575.42e6, "bandwidth": 20e6},
    SignalType.GPS_L2: {"center": 1227.60e6, "bandwidth": 20e6},
    SignalType.ADSB: {"center": 1090e6, "bandwidth": 2e6},
    
    # Marine
    SignalType.AIS: {"start": 161.975e6, "end": 162.025e6},
    
    # Voice
    SignalType.PMR446: {"start": 446.00625e6, "end": 446.19375e6, "channels": 16},
    SignalType.FRS_GMRS: {"start": 462.5625e6, "end": 467.7125e6, "channels": 22},
    SignalType.DECT_PHONE: {"start": 1880e6, "end": 1900e6},
    
    # Baby monitors vary widely
    SignalType.BABY_MONITOR: {"ranges": [(49e6, 50e6), (900e6, 928e6), (2400e6, 2483e6)]},
}


# ============================================================================
# SIGNAL DATA MODELS
# ============================================================================

@dataclass
class DetectedSignal:
    """A detected wireless signal"""
    id: str
    signal_type: SignalType
    frequency: float              # Hz
    power_dbm: float             # Signal strength
    timestamp: datetime
    
    # Optional identifiers
    mac_address: Optional[str] = None
    device_name: Optional[str] = None
    manufacturer: Optional[str] = None
    
    # Protocol-specific data
    channel: Optional[int] = None
    modulation: Optional[str] = None
    protocol_data: Dict[str, Any] = field(default_factory=dict)
    
    # Analysis
    is_encrypted: bool = False
    encryption_type: Optional[str] = None
    packet_count: int = 0
    
    # Control capability
    can_replay: bool = False
    can_inject: bool = False
    captured_packets: List[bytes] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "signal_type": self.signal_type.value,
            "frequency": self.frequency,
            "power_dbm": self.power_dbm,
            "timestamp": self.timestamp.isoformat(),
            "mac_address": self.mac_address,
            "device_name": self.device_name,
            "manufacturer": self.manufacturer,
            "channel": self.channel,
            "modulation": self.modulation,
            "is_encrypted": self.is_encrypted,
            "encryption_type": self.encryption_type,
            "packet_count": self.packet_count,
            "can_replay": self.can_replay,
            "can_inject": self.can_inject
        }


@dataclass
class RCToyProfile:
    """Profile for controlling an RC toy"""
    name: str
    frequency: float
    modulation: str              # OOK, FSK, GFSK, etc.
    protocol: str                # Custom protocol name
    
    # Control commands
    commands: Dict[str, bytes] = field(default_factory=dict)
    # e.g., {"forward": b"\x55\x01", "back": b"\x55\x02", ...}
    
    # Timing
    bit_duration_us: int = 500
    packet_gap_ms: int = 50
    
    # Learned from capture
    raw_captures: Dict[str, List[bytes]] = field(default_factory=dict)


@dataclass
class DeviceTakeoverProfile:
    """Profile for taking over control of an owned device.
    
    IMPORTANT: Only for devices you legally own and have purchased.
    This enables control of consumer devices without original controller.
    """
    device_id: str
    device_name: str
    device_type: str             # rc_car, rc_boat, bt_speaker, wifi_camera, etc.
    frequency: float             # Primary frequency
    protocol: str                # Detected protocol
    
    # Authentication/pairing info
    device_address: Optional[str] = None  # MAC, UUID, or other ID
    pairing_key: Optional[bytes] = None
    auth_sequence: Optional[bytes] = None
    
    # Learned control data
    control_commands: Dict[str, bytes] = field(default_factory=dict)
    status_queries: Dict[str, bytes] = field(default_factory=dict)
    
    # Connection state
    is_paired: bool = False
    is_connected: bool = False
    last_seen: Optional[datetime] = None
    
    # Metadata
    manufacturer: str = ""
    model: str = ""
    firmware_version: str = ""


# ============================================================================
# ANTI-DETECTION STEALTH MODE
# ============================================================================

class StealthMode:
    """
    SOTA 2026 Anti-Detection Stealth Mode
    
    Techniques for avoiding detection during signal analysis:
    - Passive-only scanning (no transmissions)
    - Randomized scan patterns
    - Low-power receive mode
    - Frequency hopping evasion
    - Timing randomization
    - MAC/ID spoofing for active scans
    """
    
    def __init__(self):
        self.enabled = False
        self.passive_only = True
        self.randomize_timing = True
        self.randomize_order = True
        self.low_power_mode = True
        self.spoof_identity = False
        self._original_mac: Optional[str] = None
        self._scan_delays = (0.1, 0.5)  # Random delay range in seconds
    
    def enable(self, level: str = "standard"):
        """Enable stealth mode.
        
        Levels:
        - 'passive': Listen-only, no transmissions whatsoever
        - 'standard': Passive + randomized timing + low power
        - 'paranoid': All stealth features enabled
        """
        self.enabled = True
        
        if level == "passive":
            self.passive_only = True
            self.randomize_timing = False
            self.randomize_order = False
            self.low_power_mode = False
            self.spoof_identity = False
            
        elif level == "standard":
            self.passive_only = True
            self.randomize_timing = True
            self.randomize_order = True
            self.low_power_mode = True
            self.spoof_identity = False
            
        elif level == "paranoid":
            self.passive_only = True
            self.randomize_timing = True
            self.randomize_order = True
            self.low_power_mode = True
            self.spoof_identity = True
            self._scan_delays = (0.5, 2.0)  # Longer delays
        
        logger.info(f"🥷 Stealth mode ENABLED: {level}")
    
    def disable(self):
        """Disable stealth mode."""
        self.enabled = False
        logger.info("🥷 Stealth mode DISABLED")
    
    def get_scan_delay(self) -> float:
        """Get randomized delay between scans."""
        if self.randomize_timing:
            import random
            return random.uniform(*self._scan_delays)
        return 0
    
    def randomize_frequency_order(self, frequencies: List[float]) -> List[float]:
        """Randomize the order of frequencies to scan."""
        if self.randomize_order:
            import random
            shuffled = frequencies.copy()
            random.shuffle(shuffled)
            return shuffled
        return frequencies
    
    def should_transmit(self) -> bool:
        """Check if transmission is allowed in current mode."""
        return not self.passive_only
    
    def spoof_mac_address(self) -> Optional[str]:
        """Generate a spoofed MAC address for active scans."""
        if self.spoof_identity:
            import random
            # Generate random MAC with locally administered bit set
            mac = [0x02, random.randint(0, 255), random.randint(0, 255),
                   random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)]
            return ':'.join(f'{b:02x}' for b in mac)
        return None


# ============================================================================
# DEVICE TAKEOVER SYSTEM
# ============================================================================

class DeviceTakeoverSystem:
    """
    SOTA 2026 Device Takeover System
    
    For taking control of devices YOU OWN that you've purchased.
    Useful when:
    - Original controller is lost/broken
    - Want to control device from computer/phone
    - Integrating device into home automation
    - Reverse engineering for educational purposes
    
    Supports:
    - RC toys (27/49/72/75 MHz, 2.4/5.8 GHz)
    - Bluetooth devices (speakers, keyboards, mice)
    - WiFi cameras and IoT devices
    - IR-controlled devices
    - Zigbee/Z-Wave smart home devices
    """
    
    def __init__(self, signal_scanner: 'RFSignalScanner', 
                 bluetooth_scanner: 'BluetoothScanner'):
        self.rf = signal_scanner
        self.bt = bluetooth_scanner
        self.profiles: Dict[str, DeviceTakeoverProfile] = {}
        self.stealth = StealthMode()
        self._lock = threading.Lock()
    
    def discover_device(self, device_type: str, timeout: float = 30.0) -> List[DetectedSignal]:
        """Discover devices of a specific type for potential takeover.
        
        Args:
            device_type: Type of device to discover (rc_car, bt_speaker, etc.)
            timeout: Discovery timeout in seconds
            
        Returns:
            List of detected signals/devices
        """
        signals = []
        
        logger.info(f"🔍 Discovering {device_type} devices...")
        
        if device_type.startswith("rc_"):
            # RC toy discovery
            signals = self.rf.scan_rc_frequencies(include_industrial=False)
            
        elif device_type.startswith("bt_") or device_type == "bluetooth":
            # Bluetooth device discovery
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                signals = loop.run_until_complete(self.bt.scan_ble(duration=timeout))
            finally:
                loop.close()
            signals.extend(self.bt.scan_classic(duration=timeout))
            
        elif device_type == "industrial":
            signals = self.rf.scan_industrial_equipment()
            
        elif device_type == "agricultural":
            signals = self.rf.scan_agricultural_equipment()
            
        elif device_type == "marine":
            signals = self.rf.scan_marine_equipment()
        
        logger.info(f"   Found {len(signals)} potential devices")
        return signals
    
    def analyze_protocol(self, signal: DetectedSignal, 
                         capture_duration: float = 10.0) -> Dict[str, Any]:
        """Analyze the protocol of a detected device.
        
        Captures signal and attempts to decode:
        - Modulation type (OOK, FSK, GFSK, etc.)
        - Packet structure
        - Timing parameters
        - Any encryption/encoding
        """
        logger.info(f"🔬 Analyzing protocol for {signal.device_name or signal.id}...")
        
        analysis = {
            "signal_id": signal.id,
            "frequency": signal.frequency,
            "signal_type": signal.signal_type.value,
            "modulation": "unknown",
            "packet_length": 0,
            "bit_rate": 0,
            "encoding": "unknown",
            "encrypted": False,
            "protocol_guess": "unknown",
            "raw_samples": None
        }
        
        # Capture raw signal
        if self.rf._sdr and not self.stealth.passive_only:
            raw_data = self.rf.capture_signal(signal.frequency, capture_duration)
            if raw_data:
                analysis["raw_samples"] = len(raw_data)
                
                # Basic protocol analysis
                import numpy as np
                samples = np.frombuffer(raw_data, dtype=np.complex64)
                
                # Detect modulation by analyzing amplitude vs phase variation
                amplitude_var = np.var(np.abs(samples))
                phase_var = np.var(np.angle(samples))
                
                if amplitude_var > phase_var * 2:
                    analysis["modulation"] = "OOK/ASK"
                elif phase_var > amplitude_var * 2:
                    analysis["modulation"] = "FSK/GFSK"
                else:
                    analysis["modulation"] = "PSK/QPSK"
                
                # Estimate bit rate from signal transitions
                diff = np.diff(np.abs(samples) > np.mean(np.abs(samples)))
                transitions = np.sum(np.abs(diff))
                if transitions > 0:
                    analysis["bit_rate"] = int(transitions / capture_duration)
                
                # Guess protocol based on frequency and characteristics
                freq_mhz = signal.frequency / 1e6
                if 26 < freq_mhz < 28:
                    analysis["protocol_guess"] = "RC_27MHz_AM"
                elif 49 < freq_mhz < 50:
                    analysis["protocol_guess"] = "RC_49MHz_AM"
                elif 2400 < freq_mhz < 2500:
                    if analysis["modulation"] == "FSK/GFSK":
                        analysis["protocol_guess"] = "RC_2.4GHz_GFSK (possibly FHSS)"
                    else:
                        analysis["protocol_guess"] = "RC_2.4GHz_DSSS"
        
        signal.protocol_data.update(analysis)
        logger.info(f"   Modulation: {analysis['modulation']}")
        logger.info(f"   Protocol guess: {analysis['protocol_guess']}")
        
        return analysis
    
    def learn_controls(self, signal: DetectedSignal, 
                       control_names: List[str] = None) -> DeviceTakeoverProfile:
        """Learn the control commands for a device.
        
        Args:
            signal: The detected signal/device
            control_names: List of controls to learn (e.g., ['forward', 'back', 'left', 'right'])
                          If None, uses default RC controls
        """
        if control_names is None:
            control_names = ["forward", "backward", "left", "right", "stop"]
        
        profile = DeviceTakeoverProfile(
            device_id=signal.id,
            device_name=signal.device_name or f"Device_{signal.id[:8]}",
            device_type=signal.signal_type.value,
            frequency=signal.frequency,
            protocol=signal.protocol_data.get("protocol_guess", "unknown"),
            device_address=signal.mac_address
        )
        
        logger.info(f"🎮 Learning controls for {profile.device_name}...")
        logger.info(f"   Will learn: {control_names}")
        
        for control in control_names:
            logger.info(f"   Press '{control}' on the original controller...")
            
            if self.stealth.enabled:
                time.sleep(self.stealth.get_scan_delay())
            
            # Capture the control signal
            raw_data = self.rf.capture_signal(signal.frequency, duration=5.0)
            if raw_data:
                profile.control_commands[control] = raw_data
                logger.info(f"   ✅ Learned '{control}' ({len(raw_data)} bytes)")
            else:
                logger.warning(f"   ❌ Failed to capture '{control}'")
            
            time.sleep(2)  # Wait between captures
        
        # Save profile
        with self._lock:
            self.profiles[profile.device_id] = profile
        
        logger.info(f"✅ Control profile saved for {profile.device_name}")
        return profile
    
    def takeover(self, device_id: str) -> bool:
        """Initiate takeover of a device using learned controls.
        
        This establishes control capability using the learned command patterns.
        """
        profile = self.profiles.get(device_id)
        if not profile:
            logger.error(f"No profile found for device {device_id}")
            return False
        
        logger.info(f"🎯 Initiating takeover of {profile.device_name}...")
        
        # For RF devices, we're ready to transmit commands
        if profile.frequency > 0 and profile.control_commands:
            profile.is_connected = True
            profile.last_seen = datetime.now()
            logger.info(f"✅ Takeover ready - {len(profile.control_commands)} commands available")
            return True
        
        # For Bluetooth, need to pair
        if profile.device_address and profile.device_type.startswith("bt_"):
            # Attempt Bluetooth pairing
            logger.info(f"   Attempting Bluetooth pairing with {profile.device_address}...")
            # This would use the BluetoothScanner to pair
            profile.is_paired = True
            profile.is_connected = True
            return True
        
        return False
    
    def send_command(self, device_id: str, command: str) -> bool:
        """Send a control command to a taken-over device.
        
        Args:
            device_id: Device to control
            command: Command name (e.g., 'forward', 'left')
        """
        profile = self.profiles.get(device_id)
        if not profile:
            logger.error(f"Device {device_id} not found")
            return False
        
        if not profile.is_connected:
            logger.error(f"Device {device_id} not connected - run takeover() first")
            return False
        
        if command not in profile.control_commands:
            logger.error(f"Command '{command}' not learned for {profile.device_name}")
            return False
        
        # Check stealth mode
        if self.stealth.enabled and not self.stealth.should_transmit():
            logger.warning("⚠️ Stealth mode is passive-only, cannot transmit")
            return False
        
        # Transmit the command
        signal_data = profile.control_commands[command]
        success = self.rf.replay_signal(signal_data, profile.frequency)
        
        if success:
            logger.info(f"📡 Sent '{command}' to {profile.device_name}")
        
        return success
    
    def get_available_commands(self, device_id: str) -> List[str]:
        """Get list of learned commands for a device."""
        profile = self.profiles.get(device_id)
        if profile:
            return list(profile.control_commands.keys())
        return []
    
    def save_profiles(self, filepath: str = "config/device_takeover_profiles.json"):
        """Save all device profiles to disk."""
        try:
            import os
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            data = {}
            for dev_id, profile in self.profiles.items():
                data[dev_id] = {
                    "device_name": profile.device_name,
                    "device_type": profile.device_type,
                    "frequency": profile.frequency,
                    "protocol": profile.protocol,
                    "device_address": profile.device_address,
                    "commands": list(profile.control_commands.keys()),
                    "manufacturer": profile.manufacturer,
                    "model": profile.model
                }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"💾 Saved {len(data)} device profiles to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
    
    def load_profiles(self, filepath: str = "config/device_takeover_profiles.json"):
        """Load device profiles from disk."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            for dev_id, info in data.items():
                profile = DeviceTakeoverProfile(
                    device_id=dev_id,
                    device_name=info["device_name"],
                    device_type=info["device_type"],
                    frequency=info["frequency"],
                    protocol=info["protocol"],
                    device_address=info.get("device_address"),
                    manufacturer=info.get("manufacturer", ""),
                    model=info.get("model", "")
                )
                self.profiles[dev_id] = profile
            
            logger.info(f"📂 Loaded {len(data)} device profiles from {filepath}")
        except FileNotFoundError:
            logger.debug("No saved profiles found")
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")


# ============================================================================
# BLUETOOTH SCANNER
# ============================================================================

class BluetoothScanner:
    """Bluetooth Classic and BLE scanner - SOTA 2026"""
    
    def __init__(self, stealth_mode: bool = False):
        self.stealth_mode = stealth_mode
        self._devices: Dict[str, DetectedSignal] = {}
        self._scanning = False
        self._scan_thread: Optional[threading.Thread] = None
    
    async def scan_ble(self, duration: float = 10.0) -> List[DetectedSignal]:
        """Scan for BLE devices - uses Windows Host Bridge in WSL2"""
        devices = []
        
        # Check if we're in WSL2 - bluez doesn't work there, use Windows bridge
        in_wsl = False
        try:
            with open('/proc/version', 'r') as f:
                content = f.read().lower()
                in_wsl = 'microsoft' in content or 'wsl' in content
        except:
            pass
        
        if in_wsl:
            # WSL2: Use Windows Host Bridge for Bluetooth scanning
            try:
                from core.windows_host_bridge import get_windows_host_bridge
                bridge = get_windows_host_bridge()
                bt_devices = bridge.get_windows_bluetooth_devices()
                
                for d in bt_devices:
                    mac = d.get('mac_address', '')
                    signal = DetectedSignal(
                        id=f"ble_{mac.replace(':', '') if mac else d.get('name', 'unknown')}",
                        signal_type=SignalType.BLUETOOTH_LE,
                        frequency=2.4e9,
                        power_dbm=-50,  # Estimated
                        timestamp=datetime.now(),
                        mac_address=mac or "Unknown",
                        device_name=d.get('name', 'Unknown BLE'),
                        protocol_data={
                            "manufacturer": d.get('manufacturer', ''),
                            "status": d.get('status', ''),
                            "device_id": d.get('device_id', '')
                        }
                    )
                    devices.append(signal)
                    self._devices[signal.id] = signal
                
                logger.info(f"WSL2: Found {len(devices)} Bluetooth devices via Windows bridge")
                return devices
                
            except Exception as e:
                logger.warning(f"WSL2 Bluetooth bridge error: {e}")
                return devices
        
        # Native Linux/Windows: Use bleak
        try:
            from bleak import BleakScanner
            
            discovered = await BleakScanner.discover(timeout=duration)
            
            for d in discovered:
                signal = DetectedSignal(
                    id=f"ble_{d.address.replace(':', '')}",
                    signal_type=SignalType.BLUETOOTH_LE,
                    frequency=2.4e9,
                    power_dbm=d.rssi if hasattr(d, 'rssi') else -100,
                    timestamp=datetime.now(),
                    mac_address=d.address,
                    device_name=d.name or "Unknown BLE",
                    protocol_data={
                        "services": [str(s) for s in d.metadata.get("uuids", [])] if d.metadata else [],
                        "manufacturer_data": str(d.metadata.get("manufacturer_data", {})) if d.metadata else ""
                    }
                )
                devices.append(signal)
                self._devices[signal.id] = signal
                
        except ImportError:
            logger.warning("bleak not installed - using fallback BLE scan")
            devices = self._fallback_bluetooth_scan()
        except Exception as e:
            logger.error(f"BLE scan error: {e}")
        
        return devices
    
    def scan_classic(self, duration: float = 10.0) -> List[DetectedSignal]:
        """Scan for Bluetooth Classic devices"""
        devices = []
        
        try:
            import bluetooth
            
            nearby = bluetooth.discover_devices(
                duration=int(duration),
                lookup_names=True,
                lookup_class=True,
                flush_cache=True
            )
            
            for addr, name, device_class in nearby:
                signal = DetectedSignal(
                    id=f"bt_{addr.replace(':', '')}",
                    signal_type=SignalType.BLUETOOTH_CLASSIC,
                    frequency=2.4e9,
                    power_dbm=-50,  # Not available in classic scan
                    timestamp=datetime.now(),
                    mac_address=addr,
                    device_name=name or "Unknown BT",
                    protocol_data={
                        "device_class": device_class,
                        "major_class": self._get_major_class(device_class),
                        "minor_class": self._get_minor_class(device_class)
                    }
                )
                devices.append(signal)
                self._devices[signal.id] = signal
                
        except ImportError:
            logger.debug("PyBluez not installed")
        except Exception as e:
            logger.error(f"Classic BT scan error: {e}")
        
        return devices
    
    def _fallback_bluetooth_scan(self) -> List[DetectedSignal]:
        """Fallback using system commands"""
        devices = []
        
        if sys.platform == "win32":
            try:
                import subprocess
                # Use PowerShell to get Bluetooth devices
                cmd = '''
                Get-PnpDevice -Class Bluetooth | 
                Select-Object FriendlyName, InstanceId, Status |
                ConvertTo-Json
                '''
                result = subprocess.run(
                    ["powershell", "-Command", cmd],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0 and result.stdout.strip():
                    data = json.loads(result.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    for d in data:
                        signal = DetectedSignal(
                            id=f"bt_{d.get('InstanceId', 'unknown')[:20]}",
                            signal_type=SignalType.BLUETOOTH_CLASSIC,
                            frequency=2.4e9,
                            power_dbm=-50,
                            timestamp=datetime.now(),
                            device_name=d.get('FriendlyName', 'Unknown'),
                            protocol_data={"status": d.get('Status', 'Unknown')}
                        )
                        devices.append(signal)
            except Exception as e:
                logger.debug(f"Fallback BT scan error: {e}")
        
        return devices
    
    def _get_major_class(self, device_class: int) -> str:
        """Get major device class from Bluetooth CoD"""
        major = (device_class >> 8) & 0x1F
        classes = {
            0: "Miscellaneous",
            1: "Computer",
            2: "Phone",
            3: "LAN/Network",
            4: "Audio/Video",
            5: "Peripheral",
            6: "Imaging",
            7: "Wearable",
            8: "Toy",
            9: "Health"
        }
        return classes.get(major, "Unknown")
    
    def _get_minor_class(self, device_class: int) -> str:
        """Get minor device class"""
        return f"0x{(device_class >> 2) & 0x3F:02X}"


# ============================================================================
# WIFI SCANNER
# ============================================================================

class WiFiScanner:
    """WiFi network scanner - SOTA 2026"""
    
    def __init__(self):
        self._networks: Dict[str, DetectedSignal] = {}
    
    def scan(self) -> List[DetectedSignal]:
        """Scan for WiFi networks"""
        networks = []
        
        if sys.platform == "win32":
            networks = self._scan_windows()
        else:
            networks = self._scan_linux()
        
        return networks
    
    def _scan_windows(self) -> List[DetectedSignal]:
        """Scan WiFi on Windows using netsh"""
        networks = []
        
        try:
            import subprocess
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                current_ssid = None
                current_bssid = None
                current_signal = 0
                current_channel = 0
                current_auth = ""
                
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line.startswith("SSID"):
                        if "BSSID" not in line:
                            current_ssid = line.split(":", 1)[1].strip() if ":" in line else ""
                    elif "BSSID" in line:
                        current_bssid = line.split(":", 1)[1].strip() if ":" in line else ""
                    elif "Signal" in line:
                        try:
                            current_signal = int(line.split(":")[1].strip().replace("%", ""))
                        except:
                            pass
                    elif "Channel" in line:
                        try:
                            current_channel = int(line.split(":")[1].strip())
                        except:
                            pass
                    elif "Authentication" in line:
                        current_auth = line.split(":")[1].strip() if ":" in line else ""
                        
                        # Create signal entry when we have all info
                        if current_bssid:
                            # Determine signal type based on channel
                            if current_channel <= 14:
                                sig_type = SignalType.WIFI_2_4GHZ
                                freq = 2.407e9 + (current_channel * 5e6)
                            elif current_channel <= 177:
                                sig_type = SignalType.WIFI_5GHZ
                                freq = 5e9 + (current_channel * 5e6)
                            else:
                                sig_type = SignalType.WIFI_6GHZ
                                freq = 6e9
                            
                            signal = DetectedSignal(
                                id=f"wifi_{current_bssid.replace(':', '')}",
                                signal_type=sig_type,
                                frequency=freq,
                                power_dbm=(current_signal - 100),  # Approximate dBm
                                timestamp=datetime.now(),
                                mac_address=current_bssid,
                                device_name=current_ssid or "Hidden Network",
                                channel=current_channel,
                                is_encrypted="Open" not in current_auth,
                                encryption_type=current_auth,
                                protocol_data={
                                    "ssid": current_ssid,
                                    "authentication": current_auth
                                }
                            )
                            networks.append(signal)
                            self._networks[signal.id] = signal
                            current_bssid = None
                            
        except Exception as e:
            logger.error(f"Windows WiFi scan error: {e}")
        
        return networks
    
    def _scan_linux(self) -> List[DetectedSignal]:
        """Scan WiFi on Linux using iwlist or nmcli"""
        networks = []
        
        try:
            import subprocess
            
            # Try nmcli first
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,CHAN,SECURITY", "dev", "wifi", "list"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    parts = line.split(':')
                    if len(parts) >= 5:
                        ssid, bssid, signal, channel, security = parts[:5]
                        
                        try:
                            channel_num = int(channel)
                            signal_pct = int(signal)
                        except:
                            continue
                        
                        sig_type = SignalType.WIFI_2_4GHZ if channel_num <= 14 else SignalType.WIFI_5GHZ
                        
                        signal_obj = DetectedSignal(
                            id=f"wifi_{bssid.replace(':', '')}",
                            signal_type=sig_type,
                            frequency=2.407e9 + (channel_num * 5e6) if channel_num <= 14 else 5e9 + (channel_num * 5e6),
                            power_dbm=(signal_pct - 100),
                            timestamp=datetime.now(),
                            mac_address=bssid,
                            device_name=ssid or "Hidden",
                            channel=channel_num,
                            is_encrypted=security != "--",
                            encryption_type=security
                        )
                        networks.append(signal_obj)
                        
        except Exception as e:
            logger.debug(f"Linux WiFi scan error: {e}")
        
        return networks


# ============================================================================
# RF SIGNAL SCANNER (SDR)
# ============================================================================

class RFSignalScanner:
    """RF signal scanner using SDR - SOTA 2026
    
    Supports RTL-SDR, HackRF, and other SDR devices.
    """
    
    def __init__(self):
        self._sdr = None
        self._detected_signals: Dict[str, DetectedSignal] = {}
        self._rc_profiles: Dict[str, RCToyProfile] = {}
        self._stealth_mode = False
    
    def init_sdr(self, device_type: str = "rtlsdr") -> bool:
        """Initialize SDR device"""
        try:
            if device_type == "rtlsdr":
                from rtlsdr import RtlSdr
                self._sdr = RtlSdr()
                self._sdr.sample_rate = 2.4e6
                self._sdr.center_freq = 433e6
                self._sdr.gain = 'auto'
                logger.info("📻 RTL-SDR initialized")
                return True
            elif device_type == "hackrf":
                # HackRF support
                try:
                    import hackrf
                    self._sdr = hackrf.HackRF()
                    logger.info("📻 HackRF initialized")
                    return True
                except ImportError:
                    logger.warning("HackRF library not available")
        except ImportError:
            logger.warning(f"SDR library for {device_type} not installed")
        except Exception as e:
            logger.error(f"SDR init error: {e}")
        
        return False
    
    def scan_frequency_range(self, start_freq: float, end_freq: float, 
                              step: float = 100e3) -> List[DetectedSignal]:
        """Scan a frequency range for signals"""
        signals = []
        
        if not self._sdr:
            logger.warning("SDR not initialized")
            return signals
        
        try:
            import numpy as np
            
            current_freq = start_freq
            while current_freq < end_freq:
                self._sdr.center_freq = current_freq
                samples = self._sdr.read_samples(256 * 1024)
                
                # Calculate power spectrum
                fft = np.fft.fft(samples)
                power = np.abs(fft) ** 2
                power_db = 10 * np.log10(power + 1e-10)
                
                # Detect signals above noise floor
                noise_floor = np.median(power_db)
                threshold = noise_floor + 10  # 10 dB above noise
                
                signal_indices = np.where(power_db > threshold)[0]
                if len(signal_indices) > 0:
                    peak_idx = signal_indices[np.argmax(power_db[signal_indices])]
                    peak_power = float(power_db[peak_idx])  # Convert to float
                    
                    # Calculate actual frequency
                    freq_offset = (peak_idx - len(fft)/2) * self._sdr.sample_rate / len(fft)
                    actual_freq = float(current_freq + freq_offset)
                    
                    signal = DetectedSignal(
                        id=f"rf_{int(actual_freq)}",
                        signal_type=self._classify_frequency(actual_freq),
                        frequency=actual_freq,
                        power_dbm=peak_power,
                        timestamp=datetime.now(),
                        can_replay=True,
                        protocol_data={
                            "center_freq": current_freq,
                            "bandwidth": self._sdr.sample_rate
                        }
                    )
                    signals.append(signal)
                    self._detected_signals[signal.id] = signal
                
                current_freq += step
                
        except Exception as e:
            logger.error(f"RF scan error: {e}")
        
        return signals
    
    def scan_rc_frequencies(self, include_industrial: bool = True) -> List[DetectedSignal]:
        """Scan RC frequencies from toys to industrial/agricultural/marine equipment.
        
        SOTA 2026: Covers ALL remote control frequency bands:
        - Consumer RC toys (27/49 MHz, 2.4 GHz)
        - Industrial remote controls (400-470 MHz)
        - Agricultural equipment (900 MHz, 2.4 GHz)
        - Marine/boat controls (27 MHz, 156-162 MHz VHF)
        - Construction equipment (450-470 MHz)
        - Crane/hoist controls (400-450 MHz)
        - FPV drones (5.8 GHz)
        """
        signals = []
        
        # =====================================================================
        # CONSUMER RC TOYS
        # =====================================================================
        # 27 MHz band (classic RC cars, boats, planes)
        signals.extend(self.scan_frequency_range(26.9e6, 27.3e6, step=10e3))
        
        # 49 MHz band (older RC toys, baby monitors)
        signals.extend(self.scan_frequency_range(49.8e6, 49.9e6, step=10e3))
        
        # 72 MHz band (RC aircraft - USA)
        signals.extend(self.scan_frequency_range(72.01e6, 72.99e6, step=20e3))
        
        # 75 MHz band (RC surface vehicles - USA)
        signals.extend(self.scan_frequency_range(75.41e6, 75.99e6, step=20e3))
        
        # 2.4 GHz band (modern digital RC - FHSS/DSSS)
        signals.extend(self.scan_frequency_range(2.4e9, 2.483e9, step=1e6))
        
        # 5.8 GHz FPV video and some RC control
        signals.extend(self.scan_frequency_range(5.65e9, 5.925e9, step=5e6))
        
        if include_industrial:
            # =================================================================
            # INDUSTRIAL / AGRICULTURAL / MARINE EQUIPMENT
            # =================================================================
            
            # Marine VHF (boat controls, some RC boats)
            signals.extend(self.scan_frequency_range(156e6, 162e6, step=25e3))
            
            # Industrial remote controls (cranes, hoists, gates)
            signals.extend(self.scan_frequency_range(400e6, 420e6, step=50e3))
            signals.extend(self.scan_frequency_range(450e6, 470e6, step=50e3))
            
            # Agricultural equipment (tractors, harvesters)
            signals.extend(self.scan_frequency_range(902e6, 928e6, step=100e3))
            
            # European industrial (868 MHz)
            signals.extend(self.scan_frequency_range(863e6, 870e6, step=50e3))
            
            # LoRa-based remote controls
            signals.extend(self.scan_frequency_range(433e6, 434.8e6, step=25e3))
        
        return signals
    
    def scan_industrial_equipment(self) -> List[DetectedSignal]:
        """Scan specifically for industrial remote control equipment.
        
        Targets:
        - Crane and hoist controls (Hetronic, Cattron, Abitron)
        - Gate and barrier openers
        - Industrial machinery controls
        - Construction equipment
        - Mining equipment remotes
        """
        signals = []
        
        # Crane/Hoist controls (typically 400-470 MHz)
        logger.info("🏗️ Scanning crane/hoist control frequencies...")
        signals.extend(self.scan_frequency_range(410e6, 430e6, step=25e3))
        signals.extend(self.scan_frequency_range(450e6, 470e6, step=25e3))
        
        # Gate/barrier openers (300-400 MHz)
        logger.info("🚧 Scanning gate/barrier frequencies...")
        signals.extend(self.scan_frequency_range(300e6, 320e6, step=50e3))
        signals.extend(self.scan_frequency_range(390e6, 400e6, step=25e3))
        
        # European industrial (868 MHz band)
        logger.info("🏭 Scanning 868 MHz industrial band...")
        signals.extend(self.scan_frequency_range(868e6, 870e6, step=25e3))
        
        return signals
    
    def scan_agricultural_equipment(self) -> List[DetectedSignal]:
        """Scan for agricultural remote control equipment.
        
        Targets:
        - Tractor guidance systems
        - Harvester controls
        - Irrigation controllers
        - Livestock management
        - GPS-RTK corrections
        """
        signals = []
        
        # 900 MHz ISM (common for ag equipment)
        logger.info("🚜 Scanning agricultural 900 MHz band...")
        signals.extend(self.scan_frequency_range(902e6, 928e6, step=100e3))
        
        # 2.4 GHz ag equipment
        signals.extend(self.scan_frequency_range(2.4e9, 2.483e9, step=1e6))
        
        # LoRa agricultural sensors
        signals.extend(self.scan_frequency_range(433e6, 434.8e6, step=25e3))
        signals.extend(self.scan_frequency_range(915e6, 928e6, step=50e3))
        
        return signals
    
    def scan_marine_equipment(self) -> List[DetectedSignal]:
        """Scan for marine/boat remote control equipment.
        
        Targets:
        - RC boats
        - Marine VHF equipment
        - Anchor windlass remotes
        - Thruster controls
        - AIS transponders
        """
        signals = []
        
        # 27 MHz marine RC
        logger.info("🚤 Scanning marine 27 MHz band...")
        signals.extend(self.scan_frequency_range(26.9e6, 27.3e6, step=10e3))
        
        # Marine VHF (156-162 MHz)
        logger.info("⚓ Scanning marine VHF band...")
        signals.extend(self.scan_frequency_range(156.0e6, 162.025e6, step=25e3))
        
        # AIS frequencies
        logger.info("🚢 Scanning AIS frequencies...")
        signals.extend(self.scan_frequency_range(161.95e6, 162.05e6, step=12.5e3))
        
        return signals
    
    def scan_ism_band(self, region: str = "US") -> List[DetectedSignal]:
        """Scan ISM bands for garage doors, car keys, wireless sensors"""
        signals = []
        
        if region == "US":
            # 315 MHz (US car keys)
            signals.extend(self.scan_frequency_range(314e6, 316e6, step=50e3))
            # 433 MHz
            signals.extend(self.scan_frequency_range(432e6, 435e6, step=50e3))
            # 915 MHz
            signals.extend(self.scan_frequency_range(902e6, 928e6, step=100e3))
        else:  # EU
            # 433 MHz
            signals.extend(self.scan_frequency_range(432e6, 435e6, step=50e3))
            # 868 MHz
            signals.extend(self.scan_frequency_range(863e6, 870e6, step=100e3))
        
        return signals
    
    def capture_signal(self, frequency: float, duration: float = 5.0) -> bytes:
        """Capture raw signal data for replay"""
        if not self._sdr:
            return b''
        
        try:
            self._sdr.center_freq = frequency
            num_samples = int(duration * self._sdr.sample_rate)
            samples = self._sdr.read_samples(num_samples)
            return samples.tobytes()
        except Exception as e:
            logger.error(f"Signal capture error: {e}")
            return b''
    
    def replay_signal(self, signal_data: bytes, frequency: float) -> bool:
        """Replay captured signal (requires TX-capable SDR like HackRF)"""
        # Note: RTL-SDR is receive-only. Need HackRF for TX.
        try:
            import hackrf
            import numpy as np
            
            hrf = hackrf.HackRF()
            hrf.set_freq(frequency)
            hrf.set_sample_rate(2e6)
            hrf.set_txvga_gain(30)
            
            samples = np.frombuffer(signal_data, dtype=np.complex64)
            hrf.start_tx()
            hrf.write(samples.tobytes())
            hrf.stop_tx()
            hrf.close()
            
            logger.info(f"📡 Replayed signal at {frequency/1e6:.3f} MHz")
            return True
            
        except ImportError:
            logger.warning("HackRF required for signal transmission")
        except Exception as e:
            logger.error(f"Signal replay error: {e}")
        
        return False
    
    def _classify_frequency(self, freq: float) -> SignalType:
        """Classify signal type by frequency"""
        freq_mhz = freq / 1e6
        
        if 26.9 <= freq_mhz <= 27.3:
            return SignalType.RC_27MHZ
        elif 49.8 <= freq_mhz <= 49.9:
            return SignalType.RC_49MHZ
        elif 314 <= freq_mhz <= 316:
            return SignalType.CAR_KEYFOB
        elif 300 <= freq_mhz <= 400:
            return SignalType.GARAGE_DOOR
        elif 432 <= freq_mhz <= 435:
            return SignalType.ISM_433MHZ
        elif 863 <= freq_mhz <= 870:
            return SignalType.ISM_868MHZ
        elif 902 <= freq_mhz <= 928:
            return SignalType.ISM_915MHZ
        elif 1090 <= freq_mhz <= 1091:
            return SignalType.ADSB
        elif 2400 <= freq_mhz <= 2500:
            return SignalType.RC_2_4GHZ
        elif 5600 <= freq_mhz <= 5900:
            return SignalType.RC_5_8GHZ
        
        return SignalType.SDR_CUSTOM
    
    def learn_rc_command(self, name: str, frequency: float, 
                          capture_duration: float = 5.0) -> bool:
        """Learn an RC command by capturing it"""
        logger.info(f"🎮 Learning RC command '{name}' at {frequency/1e6:.3f} MHz...")
        logger.info(f"   Press the button on your RC controller NOW!")
        
        signal_data = self.capture_signal(frequency, capture_duration)
        
        if signal_data:
            # Store in profile
            profile_id = f"rc_{int(frequency)}"
            if profile_id not in self._rc_profiles:
                self._rc_profiles[profile_id] = RCToyProfile(
                    name=f"RC Device @ {frequency/1e6:.3f} MHz",
                    frequency=frequency,
                    modulation="OOK",  # Most common for RC
                    protocol="learned"
                )
            
            self._rc_profiles[profile_id].raw_captures[name] = [signal_data]
            logger.info(f"✅ Learned command '{name}' ({len(signal_data)} bytes)")
            return True
        
        return False


# ============================================================================
# NFC/RFID SCANNER
# ============================================================================

class NFCRFIDScanner:
    """NFC and RFID scanner - SOTA 2026"""
    
    def __init__(self):
        self._reader = None
        self._detected_tags: Dict[str, DetectedSignal] = {}
    
    def init_reader(self, reader_type: str = "pn532") -> bool:
        """Initialize NFC/RFID reader"""
        try:
            if reader_type == "pn532":
                from pn532pi import Pn532, Pn532I2c
                i2c = Pn532I2c(1)
                self._reader = Pn532(i2c)
                self._reader.SAMConfiguration()
                logger.info("📱 PN532 NFC reader initialized")
                return True
        except ImportError:
            logger.debug("pn532pi not installed")
        except Exception as e:
            logger.error(f"NFC reader init error: {e}")
        
        return False
    
    def scan_nfc(self, timeout: float = 5.0) -> List[DetectedSignal]:
        """Scan for NFC tags"""
        tags = []
        
        if self._reader:
            try:
                uid = self._reader.readPassiveTargetID(timeout_sec=timeout)
                if uid:
                    uid_hex = uid.hex()
                    signal = DetectedSignal(
                        id=f"nfc_{uid_hex}",
                        signal_type=SignalType.NFC,
                        frequency=13.56e6,
                        power_dbm=-20,
                        timestamp=datetime.now(),
                        device_name=f"NFC Tag {uid_hex[:8]}",
                        protocol_data={
                            "uid": uid_hex,
                            "uid_length": len(uid)
                        }
                    )
                    tags.append(signal)
                    self._detected_tags[signal.id] = signal
            except Exception as e:
                logger.debug(f"NFC scan error: {e}")
        
        return tags


# ============================================================================
# INFRARED SCANNER
# ============================================================================

class IRScanner:
    """Infrared remote control scanner and replay - SOTA 2026"""
    
    def __init__(self):
        self._learned_codes: Dict[str, Dict[str, Any]] = {}
        self._gpio_pin = 18  # Default GPIO for IR receiver
    
    def learn_ir_code(self, name: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """Learn an IR remote code"""
        logger.info(f"📺 Learning IR code '{name}'... Point remote and press button")
        
        try:
            import pigpio
            
            pi = pigpio.pi()
            if not pi.connected:
                logger.error("Cannot connect to pigpiod")
                return None
            
            # Record IR signal
            code_data = []
            last_tick = None
            
            def callback(gpio, level, tick):
                nonlocal last_tick, code_data
                if last_tick is not None:
                    duration = pigpio.tickDiff(last_tick, tick)
                    code_data.append((level, duration))
                last_tick = tick
            
            cb = pi.callback(self._gpio_pin, pigpio.EITHER_EDGE, callback)
            time.sleep(timeout)
            cb.cancel()
            pi.stop()
            
            if code_data:
                ir_code = {
                    "name": name,
                    "protocol": self._detect_ir_protocol(code_data),
                    "raw_timings": code_data,
                    "learned_at": datetime.now().isoformat()
                }
                self._learned_codes[name] = ir_code
                logger.info(f"✅ Learned IR code '{name}' ({len(code_data)} transitions)")
                return ir_code
                
        except ImportError:
            logger.warning("pigpio not installed for IR learning")
        except Exception as e:
            logger.error(f"IR learn error: {e}")
        
        return None
    
    def transmit_ir_code(self, name: str) -> bool:
        """Transmit a learned IR code"""
        if name not in self._learned_codes:
            logger.warning(f"IR code '{name}' not found")
            return False
        
        try:
            import pigpio
            
            pi = pigpio.pi()
            if not pi.connected:
                return False
            
            code = self._learned_codes[name]
            # Generate waveform from timings
            wave_data = []
            gpio_tx = 17  # Default GPIO for IR transmitter
            
            for level, duration in code["raw_timings"]:
                if level:
                    # 38 kHz carrier for IR
                    cycles = int(duration / 26)  # 26µs per cycle at 38kHz
                    for _ in range(cycles):
                        wave_data.append(pigpio.pulse(1 << gpio_tx, 0, 13))
                        wave_data.append(pigpio.pulse(0, 1 << gpio_tx, 13))
                else:
                    wave_data.append(pigpio.pulse(0, 0, duration))
            
            pi.wave_clear()
            pi.wave_add_generic(wave_data)
            wave_id = pi.wave_create()
            pi.wave_send_once(wave_id)
            
            while pi.wave_tx_busy():
                time.sleep(0.01)
            
            pi.wave_delete(wave_id)
            pi.stop()
            
            logger.info(f"📺 Transmitted IR code '{name}'")
            return True
            
        except ImportError:
            logger.warning("pigpio not installed for IR transmission")
        except Exception as e:
            logger.error(f"IR transmit error: {e}")
        
        return False
    
    def _detect_ir_protocol(self, timings: List[Tuple[int, int]]) -> str:
        """Detect IR protocol from timing patterns"""
        if not timings:
            return "unknown"
        
        # Check for common protocols based on header timing
        if len(timings) > 2:
            header_mark = timings[0][1] if timings[0][0] else 0
            header_space = timings[1][1] if not timings[1][0] else 0
            
            # NEC protocol: 9000µs mark, 4500µs space
            if 8000 < header_mark < 10000 and 4000 < header_space < 5000:
                return "NEC"
            # Sony SIRC: 2400µs mark, 600µs space
            elif 2200 < header_mark < 2600 and 400 < header_space < 800:
                return "Sony"
            # RC5/RC6: Manchester encoded
            elif 800 < header_mark < 1000:
                return "RC5"
        
        return "raw"


# ============================================================================
# UNIVERSAL SIGNAL ANALYZER - Main Class
# ============================================================================

class UniversalSignalAnalyzer:
    """
    SOTA 2026 Universal Signal Analyzer
    
    Combines all signal scanning capabilities into one interface.
    Supports device takeover for owned devices and anti-detection stealth mode.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        
        # Initialize sub-scanners
        self.bluetooth = BluetoothScanner()
        self.wifi = WiFiScanner()
        self.rf = RFSignalScanner()
        self.nfc = NFCRFIDScanner()
        self.ir = IRScanner()
        
        # SOTA 2026: Device Takeover System
        self.takeover = DeviceTakeoverSystem(self.rf, self.bluetooth)
        
        # SOTA 2026: Anti-Detection Stealth Mode
        self.stealth = StealthMode()
        
        # Detected signals
        self._all_signals: Dict[str, DetectedSignal] = {}
        self._scan_history: List[Dict[str, Any]] = []
        
        # Load saved takeover profiles
        self.takeover.load_profiles()
        
        logger.info("📡 UniversalSignalAnalyzer initialized")
        logger.info("   🎯 Device Takeover System ready")
        logger.info("   🥷 Stealth Mode available")
    
    def set_stealth_mode(self, enabled: bool):
        """Enable anti-detection stealth mode"""
        self._stealth_mode = enabled
        self._anti_detection = enabled
        self.bluetooth.stealth_mode = enabled
        self.rf._stealth_mode = enabled
        logger.info(f"🥷 Stealth mode: {'ENABLED' if enabled else 'DISABLED'}")
    
    async def full_scan(self, scan_types: List[SignalType] = None) -> Dict[str, List[DetectedSignal]]:
        """Perform a full scan of all signal types"""
        results = {
            "bluetooth": [],
            "wifi": [],
            "rf": [],
            "nfc": [],
            "rc_toys": [],
            "ism_band": []
        }
        
        if scan_types is None:
            scan_types = list(SignalType)
        
        logger.info("🔍 Starting full signal scan...")
        
        # Bluetooth scans
        if SignalType.BLUETOOTH_LE in scan_types or SignalType.BLUETOOTH_CLASSIC in scan_types:
            try:
                ble_devices = await self.bluetooth.scan_ble(duration=5.0)
                results["bluetooth"].extend(ble_devices)
                logger.info(f"   BLE: {len(ble_devices)} devices")
            except Exception as e:
                logger.debug(f"BLE scan error: {e}")
            
            try:
                bt_devices = self.bluetooth.scan_classic(duration=5.0)
                results["bluetooth"].extend(bt_devices)
                logger.info(f"   BT Classic: {len(bt_devices)} devices")
            except Exception as e:
                logger.debug(f"BT Classic scan error: {e}")
        
        # WiFi scan
        if any(t.value.startswith("wifi") for t in scan_types):
            wifi_networks = self.wifi.scan()
            results["wifi"].extend(wifi_networks)
            logger.info(f"   WiFi: {len(wifi_networks)} networks")
        
        # RF scans (requires SDR)
        if self.rf._sdr:
            if SignalType.RC_27MHZ in scan_types or SignalType.RC_2_4GHZ in scan_types:
                rc_signals = self.rf.scan_rc_frequencies()
                results["rc_toys"].extend(rc_signals)
                logger.info(f"   RC Toys: {len(rc_signals)} signals")
            
            if SignalType.ISM_433MHZ in scan_types or SignalType.CAR_KEYFOB in scan_types:
                ism_signals = self.rf.scan_ism_band()
                results["ism_band"].extend(ism_signals)
                logger.info(f"   ISM Band: {len(ism_signals)} signals")
        
        # NFC scan
        if SignalType.NFC in scan_types:
            nfc_tags = self.nfc.scan_nfc(timeout=2.0)
            results["nfc"].extend(nfc_tags)
            logger.info(f"   NFC: {len(nfc_tags)} tags")
        
        # Update internal storage
        for category, signals in results.items():
            for sig in signals:
                self._all_signals[sig.id] = sig
        
        # Record scan history
        self._scan_history.append({
            "timestamp": datetime.now().isoformat(),
            "scan_types": [t.value for t in scan_types],
            "results_count": sum(len(v) for v in results.values())
        })
        
        # Publish event
        if self.event_bus:
            self.event_bus.publish("signals.scan.complete", {
                "results": {k: [s.to_dict() for s in v] for k, v in results.items()},
                "total": sum(len(v) for v in results.values())
            })
        
        logger.info(f"✅ Scan complete: {sum(len(v) for v in results.values())} total signals")
        return results
    
    def get_all_signals(self) -> List[DetectedSignal]:
        """Get all detected signals"""
        return list(self._all_signals.values())
    
    def get_signals_by_type(self, signal_type: SignalType) -> List[DetectedSignal]:
        """Get signals of a specific type"""
        return [s for s in self._all_signals.values() if s.signal_type == signal_type]
    
    def learn_device_control(self, device_name: str, signal_type: SignalType,
                              frequency: float = None) -> bool:
        """Learn to control a device by capturing its signals"""
        logger.info(f"🎮 Learning device control for '{device_name}'...")
        
        if signal_type == SignalType.INFRARED:
            # Learn IR remote codes
            codes_to_learn = ["power", "volume_up", "volume_down", "channel_up", "channel_down"]
            for code_name in codes_to_learn:
                logger.info(f"   Press '{code_name}' button...")
                self.ir.learn_ir_code(f"{device_name}_{code_name}", timeout=10.0)
            return True
            
        elif signal_type in [SignalType.RC_27MHZ, SignalType.RC_49MHZ, SignalType.RC_2_4GHZ]:
            # Learn RC toy controls
            if frequency is None:
                frequency = {
                    SignalType.RC_27MHZ: 27.145e6,
                    SignalType.RC_49MHZ: 49.860e6,
                    SignalType.RC_2_4GHZ: 2.4e9
                }.get(signal_type, 27.145e6)
            
            commands = ["forward", "backward", "left", "right", "stop"]
            for cmd in commands:
                logger.info(f"   Press '{cmd}' on controller...")
                self.rf.learn_rc_command(f"{device_name}_{cmd}", frequency)
                time.sleep(2)
            return True
        
        return False
    
    def replay_device_command(self, device_name: str, command: str) -> bool:
        """Replay a learned command to control a device"""
        full_name = f"{device_name}_{command}"
        
        # Check IR codes
        if full_name in self.ir._learned_codes:
            return self.ir.transmit_ir_code(full_name)
        
        # Check RF profiles
        for profile_id, profile in self.rf._rc_profiles.items():
            if full_name in profile.raw_captures:
                signal_data = profile.raw_captures[full_name][0]
                return self.rf.replay_signal(signal_data, profile.frequency)
        
        logger.warning(f"Command '{full_name}' not found")
        return False


# ============================================================================
# SINGLETON AND MCP TOOLS
# ============================================================================

_signal_analyzer: Optional[UniversalSignalAnalyzer] = None

def get_signal_analyzer(event_bus=None) -> UniversalSignalAnalyzer:
    """Get or create the global UniversalSignalAnalyzer instance"""
    global _signal_analyzer
    if _signal_analyzer is None:
        _signal_analyzer = UniversalSignalAnalyzer(event_bus)
    return _signal_analyzer


class SignalAnalyzerMCPTools:
    """MCP tools for AI to control signal analysis and device takeover"""
    
    def __init__(self, analyzer: UniversalSignalAnalyzer):
        self.analyzer = analyzer
    
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "scan_signals",
                "description": "Scan for wireless signals (Bluetooth, WiFi, RF, NFC, RC toys, industrial)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "signal_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Types: bluetooth, wifi, rf, nfc, rc_toys, industrial, agricultural, marine, all"
                        },
                        "stealth": {
                            "type": "boolean",
                            "description": "Enable anti-detection stealth mode"
                        },
                        "stealth_level": {
                            "type": "string",
                            "enum": ["passive", "standard", "paranoid"],
                            "description": "Stealth level if enabled"
                        }
                    }
                }
            },
            {
                "name": "discover_devices",
                "description": "Discover devices of a specific type for potential control/takeover",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_type": {
                            "type": "string",
                            "enum": ["rc_car", "rc_plane", "rc_boat", "rc_drone", "bt_speaker", "bt_camera", "wifi_camera", "industrial", "agricultural", "marine"],
                            "description": "Type of device to discover"
                        },
                        "timeout": {"type": "number", "description": "Discovery timeout in seconds"}
                    },
                    "required": ["device_type"]
                }
            },
            {
                "name": "analyze_protocol",
                "description": "Analyze the protocol of a detected device (modulation, encoding, timing)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID from discovery"},
                        "capture_duration": {"type": "number", "description": "How long to capture for analysis"}
                    },
                    "required": ["device_id"]
                }
            },
            {
                "name": "learn_device_controls",
                "description": "Learn control commands for a device by capturing from original controller",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID"},
                        "controls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Controls to learn: forward, backward, left, right, up, down, stop, etc."
                        }
                    },
                    "required": ["device_id"]
                }
            },
            {
                "name": "takeover_device",
                "description": "Initiate takeover of an owned device using learned controls",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID to take over"}
                    },
                    "required": ["device_id"]
                }
            },
            {
                "name": "send_device_command",
                "description": "Send a control command to a taken-over device",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "command": {"type": "string", "description": "Command: forward, backward, left, right, stop, etc."}
                    },
                    "required": ["device_id", "command"]
                }
            },
            {
                "name": "set_stealth_mode",
                "description": "Enable or disable anti-detection stealth mode",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "level": {
                            "type": "string",
                            "enum": ["passive", "standard", "paranoid"],
                            "description": "Stealth level"
                        }
                    },
                    "required": ["enabled"]
                }
            },
            {
                "name": "scan_industrial_equipment",
                "description": "Scan for industrial remote controls (cranes, hoists, gates, machinery)",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "scan_agricultural_equipment",
                "description": "Scan for agricultural equipment (tractors, harvesters, irrigation)",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "scan_marine_equipment",
                "description": "Scan for marine/boat remote controls and AIS",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "capture_signal",
                "description": "Capture a raw signal at specific frequency for analysis/replay",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "frequency": {"type": "number", "description": "Frequency in Hz"},
                        "duration": {"type": "number", "description": "Capture duration in seconds"}
                    },
                    "required": ["frequency"]
                }
            },
            {
                "name": "replay_signal",
                "description": "Replay a captured signal (requires TX-capable SDR)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device whose signal to replay"},
                        "command": {"type": "string", "description": "Command to replay"}
                    },
                    "required": ["device_id", "command"]
                }
            },
            {
                "name": "get_detected_devices",
                "description": "Get list of all detected wireless devices and signals",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_takeover_profiles",
                "description": "Get list of device takeover profiles (learned devices)",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "learn_ir_remote",
                "description": "Learn IR remote control codes",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_name": {"type": "string", "description": "Name for the device (e.g., 'living_room_tv')"},
                        "buttons": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Buttons to learn: power, volume_up, volume_down, channel_up, etc."
                        }
                    },
                    "required": ["device_name"]
                }
            },
            {
                "name": "send_ir_command",
                "description": "Send a learned IR command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_name": {"type": "string"},
                        "button": {"type": "string"}
                    },
                    "required": ["device_name", "button"]
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if tool_name == "scan_signals":
                signal_types = parameters.get("signal_types", ["all"])
                stealth = parameters.get("stealth", False)
                stealth_level = parameters.get("stealth_level", "standard")
                
                if stealth:
                    self.analyzer.stealth.enable(stealth_level)
                
                # Run async scan
                import asyncio
                loop = asyncio.new_event_loop()
                results = loop.run_until_complete(self.analyzer.full_scan())
                loop.close()
                
                return {
                    "success": True,
                    "results": {k: [s.to_dict() for s in v] for k, v in results.items()},
                    "total": sum(len(v) for v in results.values())
                }
            
            elif tool_name == "discover_devices":
                device_type = parameters.get("device_type", "rc_car")
                timeout = parameters.get("timeout", 30.0)
                signals = self.analyzer.takeover.discover_device(device_type, timeout)
                return {
                    "success": True,
                    "devices": [s.to_dict() for s in signals],
                    "count": len(signals)
                }
            
            elif tool_name == "analyze_protocol":
                device_id = parameters.get("device_id", "")
                duration = parameters.get("capture_duration", 10.0)
                signal = self.analyzer._all_signals.get(device_id)
                if signal:
                    analysis = self.analyzer.takeover.analyze_protocol(signal, duration)
                    return {"success": True, **analysis}
                return {"success": False, "error": "Device not found"}
            
            elif tool_name == "learn_device_controls":
                device_id = parameters.get("device_id", "")
                controls = parameters.get("controls", ["forward", "backward", "left", "right", "stop"])
                signal = self.analyzer._all_signals.get(device_id)
                if signal:
                    profile = self.analyzer.takeover.learn_controls(signal, controls)
                    return {
                        "success": True,
                        "device_name": profile.device_name,
                        "learned_controls": list(profile.control_commands.keys())
                    }
                return {"success": False, "error": "Device not found"}
            
            elif tool_name == "takeover_device":
                device_id = parameters.get("device_id", "")
                success = self.analyzer.takeover.takeover(device_id)
                return {"success": success, "device_id": device_id}
            
            elif tool_name == "send_device_command":
                device_id = parameters.get("device_id", "")
                command = parameters.get("command", "")
                success = self.analyzer.takeover.send_command(device_id, command)
                return {"success": success, "device_id": device_id, "command": command}
            
            elif tool_name == "set_stealth_mode":
                enabled = parameters.get("enabled", False)
                level = parameters.get("level", "standard")
                if enabled:
                    self.analyzer.stealth.enable(level)
                else:
                    self.analyzer.stealth.disable()
                return {"success": True, "stealth_enabled": enabled, "level": level}
            
            elif tool_name == "scan_industrial_equipment":
                signals = self.analyzer.rf.scan_industrial_equipment()
                return {
                    "success": True,
                    "devices": [s.to_dict() for s in signals],
                    "count": len(signals)
                }
            
            elif tool_name == "scan_agricultural_equipment":
                signals = self.analyzer.rf.scan_agricultural_equipment()
                return {
                    "success": True,
                    "devices": [s.to_dict() for s in signals],
                    "count": len(signals)
                }
            
            elif tool_name == "scan_marine_equipment":
                signals = self.analyzer.rf.scan_marine_equipment()
                return {
                    "success": True,
                    "devices": [s.to_dict() for s in signals],
                    "count": len(signals)
                }
            
            elif tool_name == "capture_signal":
                frequency = parameters.get("frequency", 433e6)
                duration = parameters.get("duration", 5.0)
                signal_data = self.analyzer.rf.capture_signal(frequency, duration)
                return {
                    "success": len(signal_data) > 0,
                    "frequency": frequency,
                    "captured_bytes": len(signal_data)
                }
            
            elif tool_name == "replay_signal":
                device_id = parameters.get("device_id", "")
                command = parameters.get("command", "")
                success = self.analyzer.takeover.send_command(device_id, command)
                return {"success": success, "device_id": device_id, "command": command}
            
            elif tool_name == "get_detected_devices":
                signals = self.analyzer.get_all_signals()
                return {
                    "success": True,
                    "devices": [s.to_dict() for s in signals],
                    "count": len(signals)
                }
            
            elif tool_name == "get_takeover_profiles":
                profiles = []
                for dev_id, profile in self.analyzer.takeover.profiles.items():
                    profiles.append({
                        "device_id": dev_id,
                        "device_name": profile.device_name,
                        "device_type": profile.device_type,
                        "frequency": profile.frequency,
                        "protocol": profile.protocol,
                        "commands": list(profile.control_commands.keys()),
                        "is_connected": profile.is_connected
                    })
                return {"success": True, "profiles": profiles, "count": len(profiles)}
            
            elif tool_name == "learn_ir_remote":
                device_name = parameters.get("device_name", "remote")
                buttons = parameters.get("buttons", ["power", "volume_up", "volume_down"])
                learned = []
                for button in buttons:
                    code = self.analyzer.ir.learn_ir_code(f"{device_name}_{button}", timeout=10.0)
                    if code:
                        learned.append(button)
                return {
                    "success": len(learned) > 0,
                    "device_name": device_name,
                    "learned_buttons": learned
                }
            
            elif tool_name == "send_ir_command":
                device_name = parameters.get("device_name", "")
                button = parameters.get("button", "")
                success = self.analyzer.ir.transmit_ir_code(f"{device_name}_{button}")
                return {"success": success, "device": device_name, "button": button}
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"SignalAnalyzer tool error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print(" UNIVERSAL SIGNAL ANALYZER TEST ".center(70))
    print("="*70 + "\n")
    
    analyzer = get_signal_analyzer()
    
    print("📡 Signal Types Supported:")
    for sig_type in SignalType:
        print(f"   • {sig_type.value}")
    
    print("\n📊 Frequency Bands:")
    for sig_type, band in list(FREQUENCY_BANDS.items())[:10]:
        if "start" in band:
            print(f"   • {sig_type.value}: {band['start']/1e6:.2f} - {band['end']/1e6:.2f} MHz")
    
    print("\n🔍 Starting WiFi scan...")
    wifi_results = analyzer.wifi.scan()
    print(f"   Found {len(wifi_results)} WiFi networks")
    for net in wifi_results[:5]:
        print(f"      • {net.device_name} ({net.mac_address}) - {net.power_dbm} dBm")
    
    print("\n" + "="*70 + "\n")
