"""
KINGDOM AI - Universal Device Flasher
SOTA 2026 - Flash firmware to ANY microcontroller automatically

Supports:
- Particle (Photon, Argon, Boron) - DFU mode
- Arduino (Uno, Mega, Nano, etc.) - avrdude
- ESP32/ESP8266 - esptool
- STM32 - dfu-util or stm32flash
- Teensy - teensy_loader_cli
- Raspberry Pi Pico - UF2 copy

NO LOGIN REQUIRED - Direct hardware flashing
"""

import subprocess
import sys
import os
import time
import shutil
import platform
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger("KingdomAI.UniversalFlasher")

# Device signatures for auto-detection
DEVICE_SIGNATURES = {
    # Particle - Normal mode
    (0x2B04, 0xC006): {"type": "particle_photon", "name": "Particle Photon", "method": "dfu", "platform_id": 6},
    (0x2B04, 0xC00C): {"type": "particle_argon", "name": "Particle Argon", "method": "dfu", "platform_id": 12},
    (0x2B04, 0xC00D): {"type": "particle_boron", "name": "Particle Boron", "method": "dfu", "platform_id": 13},
    (0x2B04, 0xC00E): {"type": "particle_xenon", "name": "Particle Xenon", "method": "dfu", "platform_id": 14},
    # Particle - DFU mode
    (0x2B04, 0xD006): {"type": "particle_photon_dfu", "name": "Particle Photon (DFU)", "method": "dfu", "platform_id": 6},
    (0x2B04, 0xD00C): {"type": "particle_argon_dfu", "name": "Particle Argon (DFU)", "method": "dfu", "platform_id": 12},
    (0x2B04, 0xD00D): {"type": "particle_boron_dfu", "name": "Particle Boron (DFU)", "method": "dfu", "platform_id": 13},
    (0x2B04, 0xD00E): {"type": "particle_xenon_dfu", "name": "Particle Xenon (DFU)", "method": "dfu", "platform_id": 14},
    
    # Arduino
    (0x2341, 0x0043): {"type": "arduino_uno", "name": "Arduino Uno", "method": "avrdude"},
    (0x2341, 0x0001): {"type": "arduino_uno", "name": "Arduino Uno", "method": "avrdude"},
    (0x2341, 0x0010): {"type": "arduino_mega", "name": "Arduino Mega", "method": "avrdude"},
    (0x2341, 0x003D): {"type": "arduino_due", "name": "Arduino Due", "method": "bossac"},
    (0x1A86, 0x7523): {"type": "arduino_nano_ch340", "name": "Arduino Nano (CH340)", "method": "avrdude"},
    
    # ESP32/ESP8266
    (0x10C4, 0xEA60): {"type": "esp32_cp2102", "name": "ESP32 (CP2102)", "method": "esptool"},
    (0x1A86, 0x7523): {"type": "esp8266_ch340", "name": "ESP8266 (CH340)", "method": "esptool"},
    (0x0403, 0x6001): {"type": "esp_ftdi", "name": "ESP (FTDI)", "method": "esptool"},
    
    # STM32
    (0x0483, 0xDF11): {"type": "stm32_dfu", "name": "STM32 (DFU)", "method": "dfu"},
    (0x0483, 0x5740): {"type": "stm32_vcp", "name": "STM32 (VCP)", "method": "stm32flash"},
    
    # Teensy
    (0x16C0, 0x0478): {"type": "teensy_hid", "name": "Teensy (HID)", "method": "teensy"},
    (0x16C0, 0x0483): {"type": "teensy_serial", "name": "Teensy (Serial)", "method": "teensy"},
    
    # Raspberry Pi Pico
    (0x2E8A, 0x0003): {"type": "pico_bootsel", "name": "Pi Pico (BOOTSEL)", "method": "uf2"},
    (0x2E8A, 0x000A): {"type": "pico_cdc", "name": "Pi Pico (CDC)", "method": "uf2"},
}


class UniversalDeviceFlasher:
    """Universal firmware flasher for any microcontroller"""
    
    def __init__(self):
        self.firmware_dir = Path(__file__).parent.parent / "firmware"
        self.tools_dir = self.firmware_dir / "tools"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.is_windows = platform.system() == "Windows"
        self.in_wsl = self._check_wsl()
        
    def _check_wsl(self) -> bool:
        """Check if running in WSL"""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def _run_cmd(self, cmd: List[str], timeout: int = 60) -> Dict[str, Any]:
        """Run a command and return result"""
        try:
            if self.in_wsl and cmd[0].endswith('.exe'):
                # Already a Windows command
                pass
            elif self.in_wsl:
                # Try with .exe suffix for Windows tools
                cmd[0] = cmd[0] + '.exe' if not cmd[0].endswith('.exe') else cmd[0]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except FileNotFoundError:
            return {"success": False, "error": f"Command not found: {cmd[0]}"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _run_powershell(self, script: str, timeout: int = 30) -> Dict[str, Any]:
        """Run PowerShell command from WSL or Windows"""
        ps = shutil.which("powershell.exe") if self.in_wsl else shutil.which("powershell")
        if not ps:
            return {"success": False, "error": "PowerShell not available on this platform"}
        try:
            result = subprocess.run(
                [ps, '-Command', script],
                capture_output=True, text=True, timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _install_via_apt(self, package: str) -> bool:
        """Install a package via apt (native Linux)."""
        try:
            result = subprocess.run(
                ['sudo', 'apt-get', 'install', '-y', package],
                capture_output=True, text=True, timeout=120
            )
            return result.returncode == 0
        except Exception:
            return False

    def install_tool(self, tool: str) -> bool:
        """Install a flashing tool automatically"""
        print(f"📥 Installing {tool}...")
        use_apt = (sys.platform.startswith("linux") and not self.in_wsl
                   and shutil.which("apt-get"))

        if tool == "dfu-util":
            if use_apt and self._install_via_apt("dfu-util"):
                print(f"✅ {tool} installed via apt")
                return True
            result = self._run_powershell("winget install dfu-util -e --accept-source-agreements --accept-package-agreements")
            if result.get("success"):
                print(f"✅ {tool} installed via winget")
                return True
            result = self._run_powershell("choco install dfu-util -y")
            if result.get("success"):
                print(f"✅ {tool} installed via chocolatey")
                return True
                
        elif tool == "esptool":
            result = self._run_cmd(['pip', 'install', 'esptool'])
            if result.get("success"):
                print(f"✅ {tool} installed via pip")
                return True
                
        elif tool == "avrdude":
            if use_apt and self._install_via_apt("avrdude"):
                print(f"✅ {tool} installed via apt")
                return True
            result = self._run_powershell("winget install avrdude -e --accept-source-agreements")
            if not result.get("success"):
                result = self._run_powershell("choco install avrdude -y")
            if result.get("success"):
                print(f"✅ {tool} installed")
                return True
                
        elif tool == "arduino-cli":
            if use_apt and self._install_via_apt("arduino-cli"):
                print(f"✅ {tool} installed via apt")
                return True
            result = self._run_powershell("winget install Arduino.Arduino-CLI -e --accept-source-agreements")
            if result.get("success"):
                print(f"✅ {tool} installed")
                return True
        
        print(f"⚠️ Could not auto-install {tool}")
        return False
    
    def detect_device(self) -> Optional[Dict[str, Any]]:
        """Auto-detect connected device"""
        print("\n🔍 Detecting connected devices...")
        
        try:
            from core.windows_host_bridge import get_windows_host_bridge
            bridge = get_windows_host_bridge()
            
            # Check USB devices
            usb_devices = bridge.get_windows_usb_devices()
            for dev in usb_devices:
                vid = dev.get('vid')
                pid = dev.get('pid')
                if vid and pid:
                    sig = (vid, pid)
                    if sig in DEVICE_SIGNATURES:
                        info = DEVICE_SIGNATURES[sig].copy()
                        info['vid'] = vid
                        info['pid'] = pid
                        info['port'] = dev.get('port', '')
                        info['device_id'] = dev.get('device_id', '')
                        print(f"✅ Detected: {info['name']}")
                        return info
            
            # Check serial ports
            serial_ports = bridge.get_windows_serial_ports()
            for port in serial_ports:
                vid = port.get('vid_int')
                pid = port.get('pid_int')
                if vid and pid:
                    sig = (vid, pid)
                    if sig in DEVICE_SIGNATURES:
                        info = DEVICE_SIGNATURES[sig].copy()
                        info['vid'] = vid
                        info['pid'] = pid
                        info['port'] = port.get('port', '')
                        print(f"✅ Detected: {info['name']} on {info['port']}")
                        return info
                        
        except ImportError:
            logger.warning("Windows bridge not available")
        
        print("⚠️ No known device detected")
        return None
    
    def create_firmware(self, device_type: str) -> Optional[str]:
        """Create/get firmware for device type"""
        # Check for existing firmware
        firmware_files = {
            "particle": self.firmware_dir / "kingdom_firmware.bin",
            "arduino": self.firmware_dir / "kingdom_arduino.hex",
            "esp32": self.firmware_dir / "kingdom_esp32.bin",
            "stm32": self.firmware_dir / "kingdom_stm32.bin",
        }
        
        for key, path in firmware_files.items():
            if key in device_type.lower() and path.exists():
                return str(path)
        
        # Generate firmware source
        if "particle" in device_type.lower():
            return self._compile_particle_firmware()
        elif "arduino" in device_type.lower():
            return self._compile_arduino_firmware()
        elif "esp" in device_type.lower():
            return self._compile_esp_firmware()
        
        return None
    
    def _compile_particle_firmware(self) -> Optional[str]:
        """Compile Particle firmware"""
        ino_file = self.firmware_dir / "particle_kingdom_controller.ino"
        bin_file = self.firmware_dir / "kingdom_firmware.bin"
        
        if bin_file.exists():
            return str(bin_file)
        
        if not ino_file.exists():
            print(f"⚠️ Source not found: {ino_file}")
            return None
        
        # Try particle compile (doesn't need login for compile)
        result = self._run_cmd([
            'particle', 'compile', 'photon', str(ino_file),
            '--saveTo', str(bin_file)
        ], timeout=120)
        
        if result.get("success") and bin_file.exists():
            print(f"✅ Compiled: {bin_file}")
            return str(bin_file)
        
        print("⚠️ Compilation failed. Use Particle Web IDE:")
        print("   https://build.particle.io/")
        return None
    
    def _compile_arduino_firmware(self) -> Optional[str]:
        """Compile Arduino firmware"""
        # Create Arduino sketch if not exists
        sketch_dir = self.firmware_dir / "kingdom_arduino"
        sketch_file = sketch_dir / "kingdom_arduino.ino"
        hex_file = self.firmware_dir / "kingdom_arduino.hex"
        
        if hex_file.exists():
            return str(hex_file)
        
        if not sketch_file.exists():
            sketch_dir.mkdir(exist_ok=True)
            self._create_arduino_sketch(sketch_file)
        
        # Try arduino-cli
        result = self._run_cmd([
            'arduino-cli', 'compile', '--fqbn', 'arduino:avr:uno',
            '--output-dir', str(self.firmware_dir),
            str(sketch_dir)
        ], timeout=120)
        
        if result.get("success"):
            print(f"✅ Arduino firmware compiled")
            return str(hex_file)
        
        return None
    
    def _compile_esp_firmware(self) -> Optional[str]:
        """Compile ESP32 firmware using Arduino or ESP-IDF"""
        # For now, create a MicroPython-compatible firmware
        bin_file = self.firmware_dir / "kingdom_esp32.bin"
        if bin_file.exists():
            return str(bin_file)
        
        print("⚠️ ESP32 firmware not available. Download from:")
        print("   https://micropython.org/download/esp32/")
        return None
    
    def _create_arduino_sketch(self, path: Path):
        """Create Arduino sketch for Kingdom AI control"""
        sketch = '''/*
 * KINGDOM AI - Arduino Controller
 * SOTA 2026 - Serial command interface
 */

const int LED_PIN = 13;
bool ledState = false;

void setup() {
    Serial.begin(9600);
    pinMode(LED_PIN, OUTPUT);
    Serial.println("KINGDOM AI READY");
}

void loop() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\\n');
        cmd.trim();
        cmd.toUpperCase();
        processCommand(cmd);
    }
}

void processCommand(String cmd) {
    if (cmd == "LED_ON" || cmd == "ON") {
        digitalWrite(LED_PIN, HIGH);
        ledState = true;
        Serial.println("OK: LED ON");
    }
    else if (cmd == "LED_OFF" || cmd == "OFF") {
        digitalWrite(LED_PIN, LOW);
        ledState = false;
        Serial.println("OK: LED OFF");
    }
    else if (cmd == "BLINK") {
        for (int i = 0; i < 3; i++) {
            digitalWrite(LED_PIN, HIGH);
            delay(200);
            digitalWrite(LED_PIN, LOW);
            delay(200);
        }
        Serial.println("OK: BLINK DONE");
    }
    else if (cmd == "STATUS") {
        Serial.print("STATUS: LED=");
        Serial.println(ledState ? "ON" : "OFF");
    }
    else if (cmd == "HELP") {
        Serial.println("Commands: LED_ON, LED_OFF, BLINK, STATUS, HELP");
    }
    else {
        Serial.print("ERROR: Unknown command: ");
        Serial.println(cmd);
    }
}
'''
        path.write_text(sketch)
        print(f"✅ Created Arduino sketch: {path}")
    
    def flash_device(self, device_info: Dict, firmware_path: str) -> bool:
        """Flash firmware to device"""
        method = device_info.get("method", "unknown")
        port = device_info.get("port", "")
        
        print(f"\n🚀 Flashing via {method}...")
        
        if method == "dfu":
            return self._flash_dfu(device_info, firmware_path)
        elif method == "avrdude":
            return self._flash_avrdude(device_info, firmware_path)
        elif method == "esptool":
            return self._flash_esptool(device_info, firmware_path)
        elif method == "uf2":
            return self._flash_uf2(device_info, firmware_path)
        else:
            print(f"⚠️ Unknown flash method: {method}")
            return False
    
    def _get_dfu_util_path(self) -> str:
        """Get path to bundled dfu-util-static.exe or system dfu-util"""
        # Check for bundled dfu-util (prefer win64 static)
        bundled_paths = [
            self.firmware_dir / "tools" / "dfu-util-0.11-binaries" / "win64" / "dfu-util-static.exe",
            self.firmware_dir / "tools" / "dfu-util-0.11-binaries" / "win32" / "dfu-util-static.exe",
            self.firmware_dir / "tools" / "dfu-util-0.11-binaries" / "win64" / "dfu-util.exe",
            self.firmware_dir / "tools" / "dfu-util-0.11-binaries" / "linux-amd64" / "dfu-util-static",
        ]
        
        for path in bundled_paths:
            if path.exists():
                logger.info(f"🔧 Using bundled dfu-util: {path}")
                return str(path)
        
        # Fall back to system dfu-util
        return "dfu-util"
    
    def _flash_dfu(self, device_info: Dict, firmware_path: str) -> bool:
        """Flash via DFU (Particle, STM32)"""
        vid = device_info.get('vid', 0x2B04)
        pid = device_info.get('pid', 0xD006)
        platform_id = device_info.get('platform_id', 12)
        
        # Get correct flash address based on platform
        # Gen2 (Photon/P1): 0x080A0000
        # Gen3 (Argon/Boron/Xenon): 0x000D4000
        PARTICLE_FLASH_ADDRESSES = {
            6: "0x080A0000",   # Photon/P1 (Gen2)
            12: "0x000D4000",  # Argon (Gen3)
            13: "0x000D4000",  # Boron (Gen3)
            14: "0x000D4000",  # Xenon (Gen3)
        }
        
        if "particle" in device_info.get("type", "").lower():
            address = PARTICLE_FLASH_ADDRESSES.get(platform_id, "0x000D4000") + ":leave"
        elif "stm32" in device_info.get("type", "").lower():
            address = "0x08000000:leave"
        else:
            address = "0x08000000:leave"
        
        # Use bundled dfu-util
        dfu_util = self._get_dfu_util_path()
        
        cmd = [
            dfu_util,
            '-d', f'{vid:04x}:{pid:04x}',
            '-a', '0',
            '-s', address,
            '-D', firmware_path
        ]
        
        print(f"🔧 Using dfu-util: {dfu_util}")
        print(f"🎯 Target: {vid:04x}:{pid:04x} at {address}")
        print(f"⚡ Command: {' '.join(cmd)}")
        
        result = self._run_cmd(cmd, timeout=60)
        
        if result.get("success"):
            print("✅ DFU flash successful!")
            return True
        
        # Check for success markers in output even if return code is non-zero
        stdout = result.get("stdout", "")
        if "Download done" in stdout or "File downloaded successfully" in stdout:
            print("✅ DFU flash successful!")
            return True
        
        error = result.get("stderr", "") + result.get("error", "")
        print(f"❌ Flash failed")
        print(f"   stdout: {stdout[-200:] if stdout else 'none'}")
        print(f"   stderr: {error[-200:] if error else 'none'}")
        
        if "Cannot open DFU device" in error:
            print("\n⚠️ Need WinUSB driver. Install with Zadig:")
            print("   1. Download: https://zadig.akeo.ie/")
            print("   2. Put device in DFU mode")
            print("   3. Select device, install WinUSB")
        
        return False
    
    def _flash_avrdude(self, device_info: Dict, firmware_path: str) -> bool:
        """Flash via avrdude (Arduino)"""
        port = device_info.get("port", "COM3")
        
        cmd = [
            'avrdude',
            '-p', 'atmega328p',
            '-c', 'arduino',
            '-P', port,
            '-b', '115200',
            '-U', f'flash:w:{firmware_path}:i'
        ]
        
        result = self._run_cmd(cmd, timeout=60)
        return result.get("success", False)
    
    def _flash_esptool(self, device_info: Dict, firmware_path: str) -> bool:
        """Flash via esptool (ESP32/ESP8266)"""
        port = device_info.get("port", "COM3")
        
        cmd = [
            'esptool.py', '--chip', 'esp32',
            '--port', port,
            '--baud', '460800',
            'write_flash', '-z', '0x1000', firmware_path
        ]
        
        result = self._run_cmd(cmd, timeout=120)
        return result.get("success", False)
    
    def _flash_uf2(self, device_info: Dict, firmware_path: str) -> bool:
        """Flash via UF2 copy (Raspberry Pi Pico)"""
        # Native Linux: check /media and /run/media mount points
        if sys.platform.startswith("linux") and not self.in_wsl:
            import glob
            search_dirs = (
                glob.glob("/media/*/RPI-RP2") +
                glob.glob(f"/media/{os.environ.get('USER', '*')}/RPI-RP2") +
                glob.glob("/run/media/*/RPI-RP2")
            )
            for mount in search_dirs:
                info_file = Path(mount) / "INFO_UF2.TXT"
                if info_file.exists():
                    dest = Path(mount) / Path(firmware_path).name
                    shutil.copy(firmware_path, dest)
                    print(f"✅ Copied to {dest}")
                    return True

        if self.is_windows or self.in_wsl:
            for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:"
                if self.in_wsl:
                    drive = f"/mnt/{letter.lower()}"
                info_file = Path(drive) / "INFO_UF2.TXT"
                if info_file.exists():
                    dest = Path(drive) / Path(firmware_path).name
                    shutil.copy(firmware_path, dest)
                    print(f"✅ Copied to {dest}")
                    return True
        
        print("⚠️ Pico not found in BOOTSEL mode")
        return False
    
    def auto_flash(self) -> bool:
        """Fully automatic: detect device, create firmware, flash"""
        print("=" * 60)
        print("  KINGDOM AI - UNIVERSAL DEVICE FLASHER")
        print("  Supports: Particle, Arduino, ESP32, STM32, Pico, Teensy")
        print("=" * 60)
        
        # Detect device
        device = self.detect_device()
        if not device:
            print("\n❌ No compatible device detected")
            print("   Make sure device is connected and in bootloader mode")
            return False
        
        # Get/create firmware
        firmware = self.create_firmware(device.get("type", ""))
        if not firmware:
            print(f"\n❌ No firmware available for {device.get('name')}")
            return False
        
        # Flash it
        return self.flash_device(device, firmware)


def auto_flash():
    """Quick function to auto-flash connected device"""
    flasher = UniversalDeviceFlasher()
    return flasher.auto_flash()


if __name__ == "__main__":
    auto_flash()
