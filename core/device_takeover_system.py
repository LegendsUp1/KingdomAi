"""
KINGDOM AI - Autonomous Device Takeover System
SOTA 2026 - FULL CONTROL OF ANY DEVICE

This system:
1. Finds ANY connected device automatically
2. Bypasses all manual steps - no prior data needed
3. Takes full control and notifies user
4. Auto-discovers how to operate device
5. Auto-generates firmware if needed
6. Natural language control - device does what user says

Usage:
    from core.device_takeover_system import DeviceTakeover
    takeover = DeviceTakeover()
    takeover.run()  # Fully automatic
"""

import subprocess
import sys
import os
import time
import json
import asyncio
import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("KingdomAI.DeviceTakeover")

_orch = None
_ORCH_AVAILABLE = False

def _ensure_orch():
    global _orch, _ORCH_AVAILABLE
    if _ORCH_AVAILABLE:
        return True
    try:
        from core.ollama_gateway import orchestrator as _o, get_ollama_url as _gou
        _orch = _o
        globals()["get_ollama_url"] = _gou
        _ORCH_AVAILABLE = True
        return True
    except Exception:
        return False

def get_ollama_url():
    return "http://localhost:11434"

_ensure_orch()

# All known device signatures
KNOWN_DEVICES = {
    # Particle - Normal mode
    (0x2B04, 0xC006): {"name": "Particle Photon", "type": "particle", "baud": 115200, "platform_id": 6},
    (0x2B04, 0xC00C): {"name": "Particle Argon", "type": "particle", "baud": 115200, "platform_id": 12},
    (0x2B04, 0xC00D): {"name": "Particle Boron", "type": "particle", "baud": 115200, "platform_id": 13},
    (0x2B04, 0xC00E): {"name": "Particle Xenon", "type": "particle", "baud": 115200, "platform_id": 14},
    # Particle - DFU mode
    (0x2B04, 0xD006): {"name": "Particle Photon DFU", "type": "particle_dfu", "baud": 115200, "platform_id": 6},
    (0x2B04, 0xD00C): {"name": "Particle Argon DFU", "type": "particle_dfu", "baud": 115200, "platform_id": 12},
    (0x2B04, 0xD00D): {"name": "Particle Boron DFU", "type": "particle_dfu", "baud": 115200, "platform_id": 13},
    (0x2B04, 0xD00E): {"name": "Particle Xenon DFU", "type": "particle_dfu", "baud": 115200, "platform_id": 14},
    # Arduino
    (0x2341, 0x0043): {"name": "Arduino Uno", "type": "arduino", "baud": 9600},
    (0x2341, 0x0001): {"name": "Arduino Uno", "type": "arduino", "baud": 9600},
    (0x2341, 0x0010): {"name": "Arduino Mega", "type": "arduino", "baud": 9600},
    (0x1A86, 0x7523): {"name": "CH340 Serial", "type": "generic", "baud": 9600},
    # ESP
    (0x10C4, 0xEA60): {"name": "ESP32 CP2102", "type": "esp32", "baud": 115200},
    (0x0403, 0x6001): {"name": "FTDI Serial", "type": "generic", "baud": 115200},
    # STM32
    (0x0483, 0xDF11): {"name": "STM32 DFU", "type": "stm32_dfu", "baud": 115200},
    (0x0483, 0x5740): {"name": "STM32 VCP", "type": "stm32", "baud": 115200},
    # Teensy
    (0x16C0, 0x0483): {"name": "Teensy", "type": "teensy", "baud": 9600},
    # Pico
    (0x2E8A, 0x0003): {"name": "Pi Pico", "type": "pico", "baud": 115200},
}

# Command discovery patterns - try these to learn device
PROBE_COMMANDS = [
    "help", "?", "h",
    "status", "STATUS", 
    "info", "INFO", "i",
    "version", "VERSION", "v", "ver",
    "commands", "COMMANDS",
    "list", "LIST",
    "", "\r\n",  # Empty/newline might trigger prompt
]

# Particle Listening Mode (Blue LED) Serial Commands
# These work when Particle is flashing blue
PARTICLE_WIFI_COMMANDS = {
    "w": "Start WiFi setup",
    "i": "Get device ID", 
    "v": "Get firmware version",
    "m": "Get MAC address",
    "f": "Get system firmware version",
    "s": "Get serial number",
    "c": "Clear WiFi credentials",
    "x": "Exit listening mode",
}

# WiFi security types for Particle
WIFI_SECURITY = {
    "open": 0,
    "wep": 1,
    "wpa": 2,
    "wpa2": 3,
    "wpa_enterprise": 4,
    "wpa2_enterprise": 5,
}

# Particle DFU flash addresses by platform ID
PARTICLE_FLASH_ADDRESSES = {
    6: "0x080A0000",   # Photon/P1 (Gen2)
    12: "0x000D4000",  # Argon (Gen3)
    13: "0x000D4000",  # Boron (Gen3)
    14: "0x000D4000",  # Xenon (Gen3)
}

# Particle DFU PIDs
PARTICLE_DFU_PIDS = {
    'D006': {'name': 'Photon', 'platform_id': 6},
    'D00C': {'name': 'Argon', 'platform_id': 12},
    'D00D': {'name': 'Boron', 'platform_id': 13},
    'D00E': {'name': 'Xenon', 'platform_id': 14},
}

# Particle Normal PIDs
PARTICLE_NORMAL_PIDS = {
    'C006': {'name': 'Photon', 'platform_id': 6},
    'C00C': {'name': 'Argon', 'platform_id': 12},
    'C00D': {'name': 'Boron', 'platform_id': 13},
    'C00E': {'name': 'Xenon', 'platform_id': 14},
}

# Common action patterns
ACTION_PATTERNS = {
    "led_on": ["LED_ON", "led on", "ON", "1", "HIGH", "D7:1", "digitalWrite(13,HIGH)", "led 1", "light on"],
    "led_off": ["LED_OFF", "led off", "OFF", "0", "LOW", "D7:0", "digitalWrite(13,LOW)", "led 0", "light off"],
    "blink": ["BLINK", "blink", "LED_BLINK", "flash", "FLASH"],
    "red": ["RED", "red", "RGB:255,0,0", "color red"],
    "green": ["GREEN", "green", "RGB:0,255,0", "color green"],
    "blue": ["BLUE", "blue", "RGB:0,0,255", "color blue"],
    "status": ["STATUS", "status", "?", "INFO", "info"],
    "reset": ["RESET", "reset", "REBOOT", "reboot", "restart"],
}


class DeviceTakeover:
    """
    Autonomous Device Takeover System
    Takes full control of ANY connected device with zero manual intervention
    
    Integrates:
    - Signal Analyzer for RF/frequency control
    - WiFi configuration for Particle listening mode
    - Universal comms for full communication
    """
    
    def __init__(self):
        self.device = None
        self.port = None
        self.baudrate = 115200
        self.in_control = False
        self.learned_commands: Dict[str, str] = {}
        self.device_capabilities: List[str] = []
        self.ollama = None
        self.bridge = None  # type: Any  # WindowsHostBridge instance set after init
        self.signal_analyzer = None
        self.is_particle_listening = False  # Particle flashing blue
        self.knowledge_file = Path(__file__).parent.parent / "data" / "device_takeover_knowledge.json"
        self._load_knowledge()
        self._init_signal_analyzer()
        self._orch_available = _ensure_orch()
        
    def _init_signal_analyzer(self):
        """Initialize signal analyzer for RF/frequency control"""
        try:
            from core.signal_analyzer import UniversalSignalAnalyzer
            self.signal_analyzer = UniversalSignalAnalyzer()
            logger.info("📡 Signal Analyzer integrated")
        except ImportError:
            logger.debug("Signal analyzer not available")
        except Exception as e:
            logger.debug(f"Signal analyzer init: {e}")
    
    def _get_dfu_util_path(self) -> str:
        """Get path to bundled dfu-util-static.exe or system dfu-util"""
        firmware_dir = Path(__file__).parent.parent / "firmware"
        
        # Check for bundled dfu-util (prefer win64 static)
        bundled_paths = [
            firmware_dir / "tools" / "dfu-util-0.11-binaries" / "win64" / "dfu-util-static.exe",
            firmware_dir / "tools" / "dfu-util-0.11-binaries" / "win32" / "dfu-util-static.exe",
            firmware_dir / "tools" / "dfu-util-0.11-binaries" / "win64" / "dfu-util.exe",
        ]
        
        for path in bundled_paths:
            if path.exists():
                logger.info(f"🔧 Using bundled dfu-util: {path}")
                return str(path)
        
        # Fall back to system dfu-util
        return "dfu-util"

    def _compile_particle_firmware_local(self, platform_id: int, output_path: Path) -> Optional[Path]:
        firmware_dir = Path(__file__).parent.parent / "firmware"
        device_os_dir = firmware_dir / "device-os"
        ino_file = firmware_dir / "particle_kingdom_controller.ino"

        platform_map = {
            6: "photon",
            12: "argon",
            13: "boron",
        }
        platform = platform_map.get(int(platform_id) if platform_id else 12, "argon")

        if not ino_file.exists():
            print(f"❌ Firmware source not found: {ino_file}")
            return None

        if not device_os_dir.exists():
            print(f"❌ device-os not found: {device_os_dir}")
            return None

        user_part_dir = device_os_dir / "modules" / platform / "user-part"
        if not user_part_dir.exists():
            print(f"❌ device-os platform not available: {platform}")
            return None

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        user_src_dir = device_os_dir / "user" / "src"
        user_src_dir.mkdir(parents=True, exist_ok=True)
        app_cpp = user_src_dir / "application.cpp"
        app_cpp.write_text(
            '#include "Particle.h"\n' + ino_file.read_text(encoding="utf-8", errors="ignore"),
            encoding="utf-8",
            errors="ignore",
        )

        docker_ok = False
        try:
            docker_ver = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=10)
            docker_ok = docker_ver.returncode == 0
        except Exception:
            docker_ok = False

        if not docker_ok:
            print("❌ Docker not available - cannot compile firmware locally")
            return None

        print(f"🔨 Compiling firmware locally (platform={platform}, platform_id={platform_id})...")
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{device_os_dir}:/firmware",
            "-v",
            f"{device_os_dir / 'user'}:/user",
            "akospasztor/docker-gcc-arm:10-2020-q4-linux-latest",
            "bash",
            "-c",
            "apt-get update -qq && apt-get install -y -qq libarchive-zip-perl xxd && "
            f"cd /firmware/modules/{platform}/user-part && make all APPDIR=/user PLATFORM={platform}",
        ]

        try:
            result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            print("❌ Firmware compile timed out")
            return None
        except Exception as e:
            print(f"❌ Firmware compile error: {e}")
            return None

        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "")[-600:]
            print(f"❌ Firmware compile failed: {tail}")
            return None

        build_root = device_os_dir / "build" / "target" / "user-part"
        candidates = list(build_root.rglob("user-part.bin")) if build_root.exists() else []
        if not candidates:
            print("❌ Firmware compile finished but no user-part.bin was found")
            return None

        preferred = [p for p in candidates if f"platform-{platform_id}" in p.as_posix()] if platform_id else []
        selected = max(preferred or candidates, key=lambda p: p.stat().st_mtime)

        try:
            output_path.write_bytes(selected.read_bytes())
        except Exception as e:
            print(f"❌ Could not write firmware binary: {e}")
            return None

        if output_path.exists():
            print(f"✅ Compiled firmware: {output_path} ({output_path.stat().st_size} bytes)")
            return output_path
        return None
    
    def detect_dfu_devices(self) -> List[Dict[str, Any]]:
        """Detect devices in DFU mode using dfu-util -l"""
        devices = []
        dfu_util = self._get_dfu_util_path()
        
        print("🔍 Checking for devices in DFU mode...")
        
        try:
            result = subprocess.run(
                [dfu_util, '-l'],
                capture_output=True, text=True, timeout=10
            )
            
            for line in result.stdout.split('\n'):
                if 'Found DFU' in line and '2b04' in line.lower():
                    # Parse: Found DFU: [2b04:d00c] ver=0250, devnum=X, cfg=1, intf=0, path="X-X", alt=0, name="@Internal Flash   /0x00000000/1*004Ka,47*004Kg,192*004Kg,4*004Kg,4*004Ka,8*004Kg", serial="XXXXXXXX"
                    match = re.search(r'\[2b04:([0-9a-fA-F]+)\]', line)
                    if match:
                        pid = match.group(1).upper()
                        if pid in PARTICLE_DFU_PIDS:
                            info = PARTICLE_DFU_PIDS[pid]
                            device = {
                                'mode': 'dfu',
                                'name': f"Particle {info['name']} (DFU)",
                                'type': 'particle_dfu',
                                'platform_id': info['platform_id'],
                                'pid': pid,
                                'vid': '2B04',
                            }
                            devices.append(device)
                            print(f"   ✅ Found {info['name']} in DFU mode (PID={pid})")
        except FileNotFoundError:
            print(f"   ⚠️ dfu-util not found at: {dfu_util}")
        except subprocess.TimeoutExpired:
            print("   ⚠️ dfu-util timed out")
        except Exception as e:
            print(f"   ⚠️ DFU detection error: {e}")
        
        return devices
    
    def trigger_dfu_mode(self, port: str) -> bool:
        """Trigger DFU mode via 14400 baud serial touch"""
        print(f"\n🔧 Triggering DFU mode on {port}...")
        
        # Try pyserial first (native Linux)
        try:
            import serial as _serial
            ser = _serial.Serial(port, 14400)
            ser.dtr = True
            ser.rts = True
            time.sleep(0.3)
            ser.close()
            stdout = "SUCCESS"
            success = True
        except ImportError:
            success = False
            stdout = ""
        except Exception as e:
            success = False
            stdout = f"FAILED: {e}"

        if not success:
            script = f'''
$port = New-Object System.IO.Ports.SerialPort("{port}", 14400)
$port.DtrEnable = $true
$port.RtsEnable = $true
try {{
    $port.Open()
    Start-Sleep -Milliseconds 300
    $port.Close()
    Write-Output "SUCCESS"
}} catch {{
    Write-Output "FAILED: $_"
}}
'''
            success, stdout, stderr = self._run_powershell(script)
        
        if 'SUCCESS' in stdout:
            print("   ✅ 14400 baud touch sent")
            print("   ⏳ Waiting for device to enter DFU mode...")
            time.sleep(4)
            
            # Verify DFU mode
            dfu_devices = self.detect_dfu_devices()
            if dfu_devices:
                print("   ✅ Device entered DFU mode!")
                return True
            else:
                print("   ⚠️ Device may not have entered DFU mode")
                # Try fallback methods
                return self._trigger_dfu_fallback(port)
        else:
            print(f"   ❌ 14400 baud trigger failed: {stdout}")
            return self._trigger_dfu_fallback(port)
    
    def _trigger_dfu_fallback(self, port: str) -> bool:
        """Fallback DFU trigger methods"""
        print("   🔄 Trying fallback DFU triggers...")
        
        # Method 2: 1200 baud touch (Arduino-style bootloader reset)
        script = f'''
$port = New-Object System.IO.Ports.SerialPort("{port}", 1200)
$port.DtrEnable = $true
$port.RtsEnable = $true
try {{
    $port.Open()
    Start-Sleep -Milliseconds 300
    $port.Close()
    Write-Output "SUCCESS"
}} catch {{
    Write-Output "FAILED: $_"
}}
'''
        success, stdout, _ = self._run_powershell(script)
        if 'SUCCESS' in stdout:
            print("   ✅ 1200 baud touch sent")
            time.sleep(3)
            if self.detect_dfu_devices():
                return True
        
        # Method 3: Send "DFU" command at 115200
        print("   🔄 Trying DFU serial command...")
        result = self._send_raw("DFU")
        time.sleep(3)
        if self.detect_dfu_devices():
            return True
        
        print("   ❌ All DFU trigger methods failed")
        return False
    
    def flash_particle_firmware(self, platform_id: int = 12, firmware_path: str = None) -> bool:
        """Flash Particle firmware via DFU"""
        firmware_dir = Path(__file__).parent.parent / "firmware"
        dfu_util = self._get_dfu_util_path()
        
        # Get firmware path
        if not firmware_path:
            firmware_path = str(firmware_dir / "kingdom_firmware.bin")

        firmware_p = Path(firmware_path)
        source_ino = firmware_dir / "particle_kingdom_controller.ino"
        needs_build = not firmware_p.exists()
        if not needs_build and source_ino.exists():
            try:
                needs_build = firmware_p.stat().st_mtime < source_ino.stat().st_mtime
            except Exception:
                needs_build = False

        if needs_build:
            built = self._compile_particle_firmware_local(platform_id=platform_id, output_path=firmware_p)
            if not built:
                print(f"❌ Firmware not found: {firmware_p}")
                return False

        if not firmware_p.exists():
            print(f"❌ Firmware not found: {firmware_p}")
            return False
        
        print(f"\n🚀 FLASHING PARTICLE FIRMWARE")
        print(f"   📦 Firmware: {firmware_p.name} ({firmware_p.stat().st_size} bytes)")
        
        # Get flash address for platform
        flash_addr = PARTICLE_FLASH_ADDRESSES.get(platform_id, "0x000D4000")
        
        # Detect DFU device to get exact PID
        dfu_devices = self.detect_dfu_devices()
        if not dfu_devices:
            print("   ❌ No device in DFU mode")
            return False
        
        device = dfu_devices[0]
        pid = device.get('pid', 'D00C').lower()
        
        print(f"   🎯 Target: 2b04:{pid} at {flash_addr}")
        
        cmd = [
            dfu_util,
            '-d', f'2b04:{pid}',
            '-a', '0',
            '-s', f'{flash_addr}:leave',
            '-D', str(firmware_p)
        ]
        
        print(f"   ⚡ Executing: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if 'Download done' in result.stdout or 'File downloaded successfully' in result.stdout:
                print("   ✅ Firmware flashed successfully!")
                return True
            else:
                print(f"   ❌ Flash may have failed")
                print(f"      stdout: {result.stdout[-300:] if result.stdout else 'none'}")
                print(f"      stderr: {result.stderr[-300:] if result.stderr else 'none'}")
                
                # Check if it mentions WinUSB driver
                if 'Cannot open DFU device' in (result.stderr or ''):
                    print("\n   ⚠️ DRIVER ISSUE: Install WinUSB driver with Zadig:")
                    print("      1. Download: https://zadig.akeo.ie/")
                    print("      2. Put device in DFU mode")
                    print("      3. Select device, install WinUSB")
                
                return False
        except subprocess.TimeoutExpired:
            print("   ❌ Flash timed out")
            return False
        except Exception as e:
            print(f"   ❌ Flash error: {e}")
            return False
    
    def verify_firmware(self, port: str = None, timeout_sec: int = 10) -> bool:
        """Verify device is running Kingdom AI firmware after flash"""
        print("\n🔍 VERIFYING FIRMWARE...")
        print("   ⏳ Waiting for device to reboot...")
        time.sleep(5)
        
        # Re-detect devices
        devices = self.find_all_devices()
        
        # Find Particle device
        particle_dev = None
        for d in devices:
            if 'particle' in d.get('type', '').lower() or 'particle' in d.get('name', '').lower():
                particle_dev = d
                break
        
        if not particle_dev:
            print("   ⚠️ Device not found after reboot")
            return False
        
        port = particle_dev.get('port')
        if not port:
            print("   ⚠️ No COM port for device")
            return False
        
        print(f"   📡 Testing serial on {port}...")
        
        # Try to connect and send STATUS command
        self.port = port
        self.baudrate = 115200
        
        for attempt in range(3):
            result = self._send_raw("STATUS")
            response = (result.get("response") or "").upper()
            
            if 'KINGDOM' in response or 'READY' in response or 'LED' in response or 'STATUS' in response:
                print(f"   ✅ Kingdom AI firmware responding!")
                print(f"      Response: {response[:100]}")
                return True
            
            time.sleep(1)
        
        print("   ⚠️ Firmware verification inconclusive")
        return False
    
    def full_particle_takeover(self, firmware_path: str = None) -> bool:
        """Complete automatic Particle device takeover: detect → DFU → flash → verify"""
        print("\n" + "=" * 60)
        print("  🎯 KINGDOM AI - FULL PARTICLE TAKEOVER")
        print("  Zero Manual Intervention System")
        print("=" * 60)
        
        # Step 1: Check for device already in DFU
        print("\n📍 STEP 1: Device Detection")
        dfu_devices = self.detect_dfu_devices()
        
        if dfu_devices:
            print("   ✅ Device already in DFU mode")
            device = dfu_devices[0]
            platform_id = device.get('platform_id', 12)
        else:
            # Find normal Particle device
            devices = self.find_all_devices()
            particle_dev = None
            
            for d in devices:
                dtype = d.get('type', '').lower()
                dname = d.get('name', '').lower()
                if 'particle' in dtype or 'particle' in dname:
                    particle_dev = d
                    break
            
            if not particle_dev:
                print("\n❌ No Particle device found")
                print("   Ensure device is plugged in and drivers are working")
                return False
            
            print(f"   ✅ Found: {particle_dev.get('name')} on {particle_dev.get('port')}")
            
            # Get platform ID from VID/PID
            vid = particle_dev.get('vid', 0)
            pid = particle_dev.get('pid', 0)
            pid_hex = f"{pid:04X}" if pid else ""
            
            if pid_hex in PARTICLE_NORMAL_PIDS:
                platform_id = PARTICLE_NORMAL_PIDS[pid_hex]['platform_id']
            else:
                platform_id = 12  # Default to Argon
            
            # Step 2: Trigger DFU mode
            print("\n📍 STEP 2: Enter DFU Mode")
            port = particle_dev.get('port')
            if not port:
                print("   ❌ No COM port available")
                return False
            
            if not self.trigger_dfu_mode(port):
                print("\n❌ Failed to enter DFU mode")
                return False
        
        # Step 3: Flash firmware
        print("\n📍 STEP 3: Flash Firmware")
        if not self.flash_particle_firmware(platform_id, firmware_path):
            print("\n❌ Flash failed")
            return False
        
        # Step 4: Verify
        print("\n📍 STEP 4: Verify Operation")
        verified = self.verify_firmware()
        
        if verified:
            print("\n" + "=" * 60)
            print("  🎉 TAKEOVER COMPLETE!")
            print("  Device is running Kingdom AI firmware")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("  ⚠️ Flash succeeded but verification pending")
            print("  Device may need WiFi config or manual check")
            print("=" * 60)
        
        return True
    
    def _load_knowledge(self):
        """Load learned device knowledge"""
        try:
            if self.knowledge_file.exists():
                data = json.loads(self.knowledge_file.read_text())
                self.learned_commands = data.get("commands", {})
                self.device_capabilities = data.get("capabilities", [])
        except:
            pass
    
    def _save_knowledge(self):
        """Save learned knowledge"""
        try:
            self.knowledge_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "commands": self.learned_commands,
                "capabilities": self.device_capabilities,
                "device": self.device,
                "updated": datetime.now().isoformat()
            }
            self.knowledge_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Could not save knowledge: {e}")
    
    def _run_powershell(self, script: str, timeout: int = 30) -> Tuple[bool, str, str]:
        """Run PowerShell command (Windows/WSL only)"""
        import shutil
        ps = shutil.which("powershell.exe") or shutil.which("powershell")
        if not ps:
            return False, "", "PowerShell not available on this platform"
        try:
            result = subprocess.run(
                [ps, '-Command', script],
                capture_output=True, text=True, timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def _find_linux_serial_devices(self) -> List[Dict]:
        """Find serial devices on native Linux using /sys and pyserial."""
        devices = []
        try:
            from serial.tools import list_ports
            for port_info in list_ports.comports():
                vid = port_info.vid or 0
                pid = port_info.pid or 0
                name = port_info.description or port_info.device
                device_info = KNOWN_DEVICES.get((vid, pid))
                if device_info is None and _ensure_orch():
                    device_info = self._ai_classify_unknown_device(vid, pid, name)
                if device_info is None:
                    device_info = {"name": name, "type": "unknown", "baud": 9600}
                devices.append({
                    "port": port_info.device,
                    "vid": vid,
                    "pid": pid,
                    "vid_hex": f"0x{vid:04X}" if vid else "",
                    "pid_hex": f"0x{pid:04X}" if pid else "",
                    "name": device_info.get("name", name),
                    "type": device_info.get("type", "unknown"),
                    "baud": device_info.get("baud", 9600),
                    "raw_name": name,
                    "ai_classified": device_info.get("ai_classified", False),
                })
        except ImportError:
            import glob
            for dev in sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")):
                devices.append({
                    "port": dev, "vid": 0, "pid": 0,
                    "vid_hex": "", "pid_hex": "",
                    "name": os.path.basename(dev), "type": "unknown",
                    "baud": 9600, "raw_name": dev, "ai_classified": False,
                })
        return devices

    def find_all_devices(self) -> List[Dict]:
        """Find ALL connected devices - no filtering"""
        print("\n🔍 SCANNING FOR ALL DEVICES...")
        devices = []

        import shutil
        if not shutil.which("powershell.exe") and not shutil.which("powershell"):
            devices = self._find_linux_serial_devices()
        else:
            script = r'''
Get-WmiObject Win32_PnPEntity | Where-Object { $_.Name -match "COM\d+" } | ForEach-Object {
    $name = $_.Name
    $deviceId = $_.DeviceID
    $vidHex = ""; $pidHex = ""
    if ($deviceId -match "VID_([0-9A-F]{4})") { $vidHex = $Matches[1] }
    if ($deviceId -match "PID_([0-9A-F]{4})") { $pidHex = $Matches[1] }
    $port = ""
    if ($name -match "COM(\d+)") { $port = "COM$($Matches[1])" }
    Write-Output "$port|$vidHex|$pidHex|$name"
}
'''
            success, stdout, _ = self._run_powershell(script)

            if success:
                for line in stdout.strip().split('\n'):
                    if '|' in line:
                        parts = line.strip().split('|')
                        if len(parts) >= 4:
                            port, vid_str, pid_str, name = parts[0], parts[1], parts[2], parts[3]
                            if port:
                                vid = int(vid_str, 16) if vid_str else 0
                                pid = int(pid_str, 16) if pid_str else 0

                                device_info = KNOWN_DEVICES.get((vid, pid))

                                if device_info is None and _ensure_orch():
                                    device_info = self._ai_classify_unknown_device(vid, pid, name)
                                if device_info is None:
                                    device_info = {"name": name, "type": "unknown", "baud": 9600}

                                devices.append({
                                    "port": port,
                                    "vid": vid,
                                    "pid": pid,
                                    "vid_hex": f"0x{vid:04X}" if vid else "",
                                    "pid_hex": f"0x{pid:04X}" if pid else "",
                                    "name": device_info.get("name", name),
                                    "type": device_info.get("type", "unknown"),
                                    "baud": device_info.get("baud", 9600),
                                    "raw_name": name,
                                    "ai_classified": device_info.get("ai_classified", False),
                                })
        
        if devices:
            print(f"✅ Found {len(devices)} device(s):")
            for d in devices:
                print(f"   • {d['name']} on {d['port']} [{d.get('vid_hex', '')}:{d.get('pid_hex', '')}]")
        else:
            print("⚠️ No serial devices found")
        
        return devices
    
    def connect_device(self, device: Dict) -> bool:
        """Connect to device - bypasses all checks, just connects"""
        self.device = device
        self.port = device.get("port", "")
        raw_baud = device.get("baud", device.get("baud_rate", 9600))
        try:
            self.baudrate = int(raw_baud) if raw_baud else 9600
        except Exception:
            self.baudrate = 9600
        self.is_particle_listening = False
        
        print(f"\n🔌 CONNECTING TO {device.get('name', 'Unknown')} on {self.port}...")
        
        if not self.port:
            self.in_control = False
            print(f"❌ CONNECTION FAILED to {device.get('name')}: No port")
            return False

        device_type = (device.get("type") or "")
        device_name = (device.get("name") or "")
        is_particle = "particle" in device_type.lower() or "particle" in device_name.lower()

        if is_particle:
            print("📶 Particle detected - waiting for firmware/listening response...")

        baud_candidates: List[int] = []
        preferred_bauds: List[Any]
        if is_particle:
            preferred_bauds = [115200, self.baudrate, 9600, 57600, 38400, 19200]
        else:
            preferred_bauds = [self.baudrate, 115200, 9600, 57600, 38400, 19200]

        for b in preferred_bauds:
            try:
                b_int = int(b)
            except Exception:
                continue
            if b_int > 0 and b_int not in baud_candidates:
                baud_candidates.append(b_int)

        probe_commands = ["help", "?", "status"]
        if is_particle:
            probe_commands = ["i", "INFO", "STATUS"]

        last_result: Dict[str, Any] = {}
        for baud in baud_candidates:
            self.baudrate = baud
            for probe in probe_commands:
                try:
                    result = self._send_raw(probe)
                except Exception as e:
                    result = {"success": False, "error": str(e)}

                if isinstance(result, dict):
                    last_result = result
                else:
                    last_result = {}

                response = (last_result.get("response") or "")
                response_s = response.strip() if isinstance(response, str) else ""

                if response_s:
                    self.in_control = True
                    device["baud"] = baud

                    if is_particle:
                        resp_l = response_s.lower()
                        resp_u = response_s.upper()
                        firmware_markers = ("READY", "INFO:", "CMD:", "OK:")
                        setup_markers = (
                            "security cipher",
                            "ssid",
                            "security",
                            "password",
                            "wpa",
                            "wpa2",
                            "wep",
                            "open",
                            "listening mode",
                        )

                        if any(m in resp_u for m in firmware_markers):
                            self.is_particle_listening = False
                        elif ("device id" in resp_l or "your device id" in resp_l) or any(m in resp_l for m in setup_markers):
                            self.is_particle_listening = True
                        else:
                            self.is_particle_listening = False

                    if is_particle and self.is_particle_listening:
                        print(f"✅ CONNECTED at {baud} baud (Particle in LISTENING/SETUP mode).")
                    else:
                        print(f"✅ CONNECTED at {baud} baud! FULL CONTROL acquired.")
                    return True
        
        # Connection failed - do not assume connected
        self.in_control = False
        error_msg = last_result.get("error", "") if isinstance(last_result, dict) else ""
        if not error_msg:
            error_msg = "No valid response from device (check COM port / baud / listening mode)"
        print(f"❌ CONNECTION FAILED to {device.get('name')}: {error_msg}")
        return False
    
    def configure_wifi(self, ssid: str, password: str, security: str = "wpa2", cipher: int = 1) -> bool:
        """Configure WiFi on Particle device in listening mode (blue LED)
        
        Args:
            ssid: WiFi network name
            password: WiFi password
            security: Security type (open, wep, wpa, wpa2, wpa_enterprise, wpa2_enterprise)
            cipher: Security cipher for WPA/WPA2 (1=AES, 2=TKIP, 3=AES+TKIP). Default AES.
        """
        if not self.in_control or not self.port:
            print("❌ Not connected to device")
            return False
        
        print(f"\n📶 Configuring WiFi: {ssid}")

        prompt_resp = ""
        try:
            prompt_probe = self._send_raw("i")
            prompt_resp = (prompt_probe.get("response") or "").strip()
        except Exception:
            prompt_resp = ""

        if "security cipher" in prompt_resp.lower():
            sec_type = WIFI_SECURITY.get(security.lower(), 3)
            if sec_type in (2, 3):
                cipher_val = max(1, min(3, cipher))
                result = self._send_raw(str(cipher_val))
                time.sleep(0.3)
                print(f"   Cipher: {'AES' if cipher_val == 1 else 'TKIP' if cipher_val == 2 else 'AES+TKIP'}")

            result = self._send_raw(password)
            time.sleep(0.5)

            print(f"✅ WiFi credentials sent for '{ssid}'")
            print("   Device should connect and LED will breathe cyan")
            time.sleep(1.0)
            return True
        
        # Send 'w' to start WiFi setup
        result = self._send_raw("w")
        time.sleep(0.5)
        
        # Send SSID
        result = self._send_raw(ssid)
        time.sleep(0.3)
        
        # Send security type (0=open, 1=wep, 2=wpa, 3=wpa2, etc.)
        sec_type = WIFI_SECURITY.get(security.lower(), 3)
        result = self._send_raw(str(sec_type))
        time.sleep(0.3)
        
        # For WPA/WPA2, Particle prompts for Security Cipher: 1=AES, 2=TKIP, 3=AES+TKIP
        if sec_type in (2, 3):  # WPA or WPA2
            cipher_val = max(1, min(3, cipher))  # Clamp to valid range
            result = self._send_raw(str(cipher_val))
            time.sleep(0.3)
            print(f"   Cipher: {'AES' if cipher_val == 1 else 'TKIP' if cipher_val == 2 else 'AES+TKIP'}")
        
        # Send password
        result = self._send_raw(password)
        time.sleep(0.5)
        
        print(f"✅ WiFi credentials sent for '{ssid}'")
        print("   Device should connect and LED will breathe cyan")
        
        # Give device time to process and attempt connection
        time.sleep(1.0)
        return True
    
    def get_device_id(self) -> str:
        """Get device ID (works in Particle listening mode)"""
        result = self._send_raw("i")
        if result.get("success") and result.get("response"):
            return result["response"].strip()
        return ""
    
    def get_mac_address(self) -> str:
        """Get MAC address (works in Particle listening mode)"""
        result = self._send_raw("m")
        if result.get("success") and result.get("response"):
            return result["response"].strip()
        return ""
    
    def exit_listening_mode(self) -> bool:
        """Exit listening mode and run user firmware"""
        result = self._send_raw("x")
        return result.get("success", False)
    
    def _send_raw(self, command: str) -> Dict[str, Any]:
        """Send raw command to device"""
        if not self.port:
            return {"success": False, "error": "No port"}

        if self.bridge and hasattr(self.bridge, "send_serial_command"):
            try:
                result = self.bridge.send_serial_command(
                    self.port,
                    command,
                    baudrate=int(self.baudrate) if self.baudrate else 115200,
                    wait_response=True,
                    timeout_ms=2000,
                )
                if isinstance(result, dict):
                    response = (result.get("response") or "").strip()
                    if result.get("success"):
                        return {"success": True, "response": response}
                    return {
                        "success": False,
                        "error": (result.get("error") or "").strip() or "No response received from device",
                        "response": response,
                    }
            except Exception:
                pass

        # Try pyserial first (works on native Linux)
        try:
            import serial as _serial
            ser = _serial.Serial(self.port, int(self.baudrate) if self.baudrate else 115200,
                                 timeout=2, write_timeout=2)
            ser.dtr = True
            ser.rts = True
            time.sleep(0.1)
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            if command:
                ser.write((command + "\r\n").encode("utf-8", errors="replace"))
            response = b""
            deadline = time.time() + 2.0
            had_data = False
            last_read = time.time()
            while time.time() < deadline:
                waiting = ser.in_waiting
                if waiting > 0:
                    chunk = ser.read(waiting)
                    response += chunk
                    last_read = time.time()
                    had_data = True
                else:
                    if had_data and (time.time() - last_read) >= 0.2:
                        break
                    time.sleep(0.025)
            ser.close()
            decoded = response.decode("utf-8", errors="replace").strip()
            return {"success": True, "response": decoded}
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"pyserial send_raw failed: {e}")

        import shutil
        if not shutil.which("powershell.exe") and not shutil.which("powershell"):
            return {"success": False, "error": "pyserial not installed and PowerShell not available"}

        escaped_cmd = (command or "").replace('`', '``').replace('"', '`"').replace("'", "''")
        
        script = f'''
$port = New-Object System.IO.Ports.SerialPort("{self.port}", {self.baudrate})
$port.Handshake = [System.IO.Ports.Handshake]::None
$port.DtrEnable = $true
$port.RtsEnable = $true
$port.ReadTimeout = 2000
$port.WriteTimeout = 2000

try {{
    $port.Open()
    Start-Sleep -Milliseconds 100
    $port.DiscardInBuffer()
    $port.DiscardOutBuffer()

    if ("{escaped_cmd}") {{
        $port.Write("{escaped_cmd}`r`n")
    }}

    $response = ""
    $deadline = [DateTime]::UtcNow.AddMilliseconds(2000)
    $lastRead = [DateTime]::UtcNow
    $hadData = $false
    while ([DateTime]::UtcNow -lt $deadline) {{
        Start-Sleep -Milliseconds 25
        if ($port.BytesToRead -gt 0) {{
            $chunk = $port.ReadExisting()
            if ($chunk) {{
                $response += $chunk
                $lastRead = [DateTime]::UtcNow
                $hadData = $true
            }}
        }} else {{
            if ($hadData) {{
                $idleMs = ([DateTime]::UtcNow - $lastRead).TotalMilliseconds
                if ($idleMs -ge 200) {{ break }}
            }}
        }}
    }}
    
    $port.Close()
    Write-Output "SUCCESS|$response"
}} catch {{
    Write-Output "ERROR|$($_.Exception.Message)"
}} finally {{
    try {{ if ($port.IsOpen) {{ $port.Close() }} }} catch {{ }}
}}
'''
        success, stdout, stderr = self._run_powershell(script)
        
        if "SUCCESS|" in stdout:
            response = stdout.split("SUCCESS|", 1)[1].strip()
            return {"success": True, "response": response}
        elif "ERROR|" in stdout:
            error = stdout.split("ERROR|", 1)[1].strip()
            return {"success": False, "error": error}
        
        return {"success": False, "error": stderr or "Unknown error"}
    
    def _ai_classify_unknown_device(self, vid: int, pid: int, name: str) -> Optional[Dict]:
        """Use the Ollama brain to classify an unknown USB device from its VID/PID and name."""
        if not _ensure_orch():
            return None
        try:
            import requests
            model = _orch.get_model_for_task("devices")
            url = get_ollama_url()
            prompt = (
                f"Classify this USB device:\n"
                f"VID: 0x{vid:04X}, PID: 0x{pid:04X}\n"
                f"Windows name: \"{name}\"\n\n"
                f"Respond with ONLY valid JSON:\n"
                f'{{"name": "human readable name", "type": "arduino/esp32/stm32/particle/teensy/pico/generic/sensor/printer/hid", '
                f'"baud": recommended_baud_rate_integer, "protocol": "serial/usb_hid/spi"}}'
            )
            resp = requests.post(
                f"{url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 80, "temperature": 0.1},
                      "keep_alive": -1},
                timeout=15,
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "")
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(raw[start:end])
                    parsed["ai_classified"] = True
                    baud = parsed.get("baud", 9600)
                    if isinstance(baud, str):
                        baud = int(baud)
                    parsed["baud"] = max(300, min(921600, baud))
                    logger.info("AI classified device VID=0x%04X PID=0x%04X → %s (%s, baud=%d)",
                                vid, pid, parsed.get("name", "?"), parsed.get("type", "?"), parsed["baud"])
                    return parsed
        except Exception as e:
            logger.debug("AI device classification failed: %s", e)
        return None

    def _ai_interpret_command(self, user_input: str) -> Optional[str]:
        """Use the Ollama brain to interpret a natural language device command."""
        if not _ensure_orch():
            return None
        try:
            import requests
            model = _orch.get_model_for_task("devices")
            url = get_ollama_url()
            caps = ", ".join(self.device_capabilities[:20]) if self.device_capabilities else "LED_ON, LED_OFF, BLINK, STATUS, HELP"
            prompt = (
                f"You are controlling a {self.device.get('name', 'microcontroller') if self.device else 'microcontroller'}.\n"
                f"Known commands: {caps}\n"
                f"User says: \"{user_input}\"\n"
                f"Respond with ONLY the device command. No explanation. One line."
            )
            resp = requests.post(
                f"{url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 30, "temperature": 0.1},
                      "keep_alive": -1},
                timeout=15,
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "").strip().split('\n')[0].strip()
                if raw and len(raw) < 60:
                    logger.info("AI device command: '%s' → '%s'", user_input, raw)
                    return raw
        except Exception as e:
            logger.debug("AI device command interpretation failed: %s", e)
        return None

    def _ai_analyze_discovery(self, responses: Dict[str, str]) -> List[str]:
        """Use the Ollama brain to analyze probe responses and extract capabilities."""
        if not _ensure_orch() or not responses:
            return []
        try:
            import requests
            model = _orch.get_model_for_task("devices")
            url = get_ollama_url()
            probe_summary = "\n".join(f"'{k}' → '{v[:100]}'" for k, v in responses.items())
            prompt = (
                f"Analyze these device probe responses and list the available commands:\n"
                f"{probe_summary}\n\n"
                f"Respond with ONLY a comma-separated list of device command names. No explanation."
            )
            resp = requests.post(
                f"{url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 100, "temperature": 0.2},
                      "keep_alive": -1},
                timeout=20,
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "").strip()
                cmds = [c.strip().upper() for c in raw.split(",") if c.strip() and len(c.strip()) < 30]
                if cmds:
                    logger.info("AI discovered %d capabilities: %s", len(cmds), ", ".join(cmds[:10]))
                    return cmds
        except Exception as e:
            logger.debug("AI discovery analysis failed: %s", e)
        return []

    def discover_capabilities(self):
        """Auto-discover what this device can do"""
        print("\n🔬 DISCOVERING DEVICE CAPABILITIES...")
        
        responses = {}
        
        for cmd in PROBE_COMMANDS:
            result = self._send_raw(cmd)
            if result.get("success") and result.get("response"):
                resp = result["response"].strip()
                if resp and len(resp) > 1:
                    responses[cmd] = resp
                    print(f"   ✓ '{cmd}' → {resp[:60]}{'...' if len(resp) > 60 else ''}")
        
        # Parse responses to find available commands
        all_text = " ".join(responses.values())
        
        # Find command-like patterns
        found_commands = set()
        
        # Look for UPPERCASE_COMMANDS
        found_commands.update(re.findall(r'\b[A-Z][A-Z_]{2,}\b', all_text))
        
        # Look for listed commands
        for word in re.findall(r'\b\w+\b', all_text):
            if word.lower() in ['led', 'blink', 'on', 'off', 'status', 'help', 'reset', 'rgb']:
                found_commands.add(word.upper())
        
        # SOTA 2026: Use Ollama brain to analyze probe responses for deeper insight
        ai_capabilities = self._ai_analyze_discovery(responses)
        for cap in ai_capabilities:
            found_commands.add(cap)

        self.device_capabilities = list(found_commands)
        
        if self.device_capabilities:
            print(f"\n📋 DISCOVERED CAPABILITIES: {', '.join(self.device_capabilities[:15])}")
        
        self._save_knowledge()
        return responses
    
    def learn_action(self, action: str) -> Optional[str]:
        """Learn which command works for an action"""
        if action in self.learned_commands:
            return self.learned_commands[action]
        
        # Get patterns to try
        patterns = ACTION_PATTERNS.get(action.lower(), [action])
        
        print(f"\n🧠 Learning how to: {action}")
        
        for cmd in patterns:
            result = self._send_raw(cmd)
            if result.get("success"):
                resp = (result.get("response") or "").strip()
                if not resp:
                    continue
                resp_l = resp.lower()
                # Check if command was accepted (no error in response)
                if "error" not in resp_l and "unknown" not in resp_l and "invalid" not in resp_l:
                    self.learned_commands[action] = cmd
                    self._save_knowledge()
                    print(f"   ✅ Learned: '{action}' → '{cmd}'")
                    return cmd
        
        return None
    
    def execute_command(self, user_input: str) -> Dict[str, Any]:
        """Execute a natural language command"""
        if not self.in_control:
            return {"success": False, "error": "Not connected to any device"}
        
        # Normalize input
        text = user_input.lower().strip()
        
        # Check for direct action matches
        for action, patterns in ACTION_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in text or action in text:
                    # Check if we already know the command
                    if action in self.learned_commands:
                        cmd = self.learned_commands[action]
                    else:
                        cmd = self.learn_action(action)
                    
                    if cmd:
                        result = self._send_raw(cmd)
                        return {
                            "success": result.get("success", False),
                            "action": action,
                            "command": cmd,
                            "response": result.get("response", ""),
                            "user_input": user_input
                        }
        
        # SOTA 2026: Use Ollama brain to interpret the command before raw send
        if _ensure_orch():
            ai_cmd = self._ai_interpret_command(user_input)
            if ai_cmd and ai_cmd != user_input:
                result = self._send_raw(ai_cmd)
                if result.get("success"):
                    return {
                        "success": True,
                        "action": "ai_interpreted",
                        "command": ai_cmd,
                        "response": result.get("response", ""),
                        "user_input": user_input
                    }

        # Try sending as-is
        result = self._send_raw(user_input)
        return {
            "success": result.get("success", False),
            "command": user_input,
            "response": result.get("response", ""),
            "user_input": user_input
        }
    
    def natural_language_control(self, text: str) -> str:
        """Process natural language and control device"""
        result = self.execute_command(text)
        
        if result.get("success"):
            response = (result.get("response") or "").strip()
            cmd = result.get("command", "")
            if response:
                return f"✅ Executed: {cmd}\n📥 Response: {response}"
            return f"⚠️ Sent: {cmd}\n📥 No response (check COM port / baud / listening mode)"
        else:
            return f"⚠️ Command sent: {result.get('command', text)}\n📥 {result.get('response', result.get('error', 'No response'))}"
    
    def interactive_control(self):
        """Interactive control loop - user talks, device does"""
        print("\n" + "=" * 60)
        print("  🎮 KINGDOM AI - DEVICE CONTROL ACTIVE")
        print("  Speak naturally - your device obeys")
        print("=" * 60)
        print("\nCommands:")
        print("  • Just type what you want (e.g., 'turn on the light')")
        print("  • 'discover' - Find what device can do")
        print("  • 'status' - Check device status")
        if self.is_particle_listening:
            print("\n  📶 PARTICLE WIFI COMMANDS (Blue LED mode):")
            print("  • 'wifi SSID PASSWORD' - Configure WiFi")
            print("  • 'id' - Get device ID")
            print("  • 'mac' - Get MAC address")
            print("  • 'exit' - Exit listening mode")
        print("  • 'quit' - Exit")
        print("=" * 60 + "\n")
        
        while True:
            try:
                user_input = input("You> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == 'discover':
                self.discover_capabilities()
                continue
            
            # Particle WiFi commands
            if user_input.lower().startswith('wifi '):
                parts = user_input.split(' ', 2)
                if len(parts) >= 3:
                    ssid, password = parts[1], parts[2]
                    self.configure_wifi(ssid, password)
                else:
                    print("Usage: wifi SSID PASSWORD")
                continue
            
            if user_input.lower() == 'id':
                device_id = self.get_device_id()
                print(f"📱 Device ID: {device_id if device_id else '(no response)'}")
                continue
            
            if user_input.lower() == 'mac':
                mac = self.get_mac_address()
                print(f"📱 MAC Address: {mac if mac else '(no response)'}")
                continue
            
            if user_input.lower() == 'exit':
                self.exit_listening_mode()
                print("📱 Exit command sent - device should run user firmware")
                continue
            
            # Execute command
            response = self.natural_language_control(user_input)
            print(f"\n{response}\n")
    
    def run(self):
        """FULLY AUTOMATIC - finds device, connects, gives control"""
        print("=" * 60)
        print("  KINGDOM AI - AUTONOMOUS DEVICE TAKEOVER")
        print("  Zero Manual Intervention Required")
        print("=" * 60)
        
        # Step 1: Find all devices
        devices = self.find_all_devices()
        
        if not devices:
            print("\n❌ No devices found. Connect a device and try again.")
            return False
        
        # Step 2: Auto-select best device (prefer known types)
        selected = None
        for d in devices:
            if d.get("type") != "unknown":
                selected = d
                break
        if not selected:
            selected = devices[0]
        
        print(f"\n🎯 AUTO-SELECTED: {selected.get('name')} on {selected.get('port')}")
        
        # Step 3: Connect
        if not self.connect_device(selected):
            print("\n❌ Could not connect to device")
            return False
        
        # Step 4: Discover capabilities
        self.discover_capabilities()
        
        # Step 5: Ready for control
        print("\n" + "=" * 60)
        print("  ✅ FULL CONTROL ACQUIRED!")
        print(f"  Device: {selected.get('name')}")
        print(f"  Port: {selected.get('port')}")
        print(f"  Baudrate: {self.baudrate}")
        print("=" * 60)
        
        # Step 6: Interactive control
        self.interactive_control()
        
        return True


def takeover():
    """Quick function to run device takeover"""
    system = DeviceTakeover()
    return system.run()


if __name__ == "__main__":
    takeover()
