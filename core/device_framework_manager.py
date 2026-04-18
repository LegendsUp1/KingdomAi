#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import shutil
import logging
import subprocess
import threading
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


def _is_wsl() -> bool:
    try:
        if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
            return True
        if sys.platform.startswith("linux"):
            try:
                with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
                    return "microsoft" in f.read().lower()
            except Exception:
                return False
        return False
    except Exception:
        return False


class FrameworkType(Enum):
    PYTHON_PACKAGE = "python_package"
    SYSTEM_TOOL = "system_tool"
    NODE_PACKAGE = "node_package"


class InstallStatus(Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    INSTALL_FAILED = "install_failed"
    INSTALL_PENDING = "install_pending"


DEVICE_FRAMEWORK_REQUIREMENTS = {
    "particle": {
        "python": ["pyserial"],
        "system": ["dfu-util"],
        "node": ["particle-cli"],
        "description": "Particle Photon/Argon/Boron IoT devices"
    },
    "arduino": {
        "python": ["pyserial"],
        "system": ["arduino-cli"],
        "node": [],
        "description": "Arduino boards (Uno, Mega, Leonardo, etc.)"
    },
    "esp32": {
        "python": ["pyserial", "esptool"],
        "system": [],
        "node": [],
        "description": "ESP32/ESP8266 WiFi microcontrollers"
    },
    "stm32": {
        "python": ["pyserial"],
        "system": ["dfu-util", "stm32flash"],
        "node": [],
        "description": "STM32 ARM Cortex-M microcontrollers"
    },
    "teensy": {
        "python": ["pyserial"],
        "system": ["teensy_loader_cli"],
        "node": [],
        "description": "Teensy USB development boards"
    },
    "pico": {
        "python": ["pyserial"],
        "system": [],
        "node": [],
        "description": "Raspberry Pi Pico RP2040"
    },
    "generic_serial": {
        "python": ["pyserial"],
        "system": [],
        "node": [],
        "description": "Generic serial device"
    }
}


VID_PID_TO_FRAMEWORK = {
    (0x2B04, 0xC006): "particle",
    (0x2B04, 0xD006): "particle",
    (0x2341, 0x0043): "arduino",
    (0x2341, 0x0042): "arduino",
    (0x2341, 0x8036): "arduino",
    (0x2341, 0x8037): "arduino",
    (0x2A03, 0x0043): "arduino",
    (0x1A86, 0x7523): "arduino",
    (0x10C4, 0xEA60): "esp32",
    (0x1A86, 0x55D4): "esp32",
    (0x303A, 0x1001): "esp32",
    (0x303A, 0x80D1): "esp32",
    (0x0483, 0x5740): "stm32",
    (0x0483, 0xDF11): "stm32",
    (0x0483, 0x374B): "stm32",
    (0x16C0, 0x0483): "teensy",
    (0x16C0, 0x0486): "teensy",
    (0x16C0, 0x0478): "teensy",
    (0x2E8A, 0x0005): "pico",
    (0x2E8A, 0x000A): "pico",
}


class DeviceFrameworkLibrary:
    
    def __init__(self, library_path: str = "data/device_framework_library.json"):
        self._library_path = library_path
        self._library: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._load()
    
    def _load(self):
        try:
            if os.path.exists(self._library_path):
                with open(self._library_path, 'r', encoding='utf-8') as f:
                    self._library = json.load(f)
                logger.info(f"📚 Loaded device framework library: {len(self._library)} devices")
        except Exception as e:
            logger.warning(f"Could not load framework library: {e}")
            self._library = {}
    
    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._library_path), exist_ok=True)
            with open(self._library_path, 'w', encoding='utf-8') as f:
                json.dump(self._library, f, indent=2, default=str)
            logger.debug(f"💾 Saved device framework library: {len(self._library)} devices")
        except Exception as e:
            logger.error(f"Could not save framework library: {e}")
    
    def get_device_signature(self, device_info: Dict[str, Any]) -> str:
        vid = device_info.get("vid") or device_info.get("capabilities", {}).get("vid", 0)
        pid = device_info.get("pid") or device_info.get("capabilities", {}).get("pid", 0)
        if vid and pid:
            return f"vid_{vid:04x}_pid_{pid:04x}"
        name = device_info.get("name", "unknown")
        return f"name_{name.lower().replace(' ', '_')[:32]}"
    
    def get_device_entry(self, signature: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._library.get(signature)
    
    def update_device_entry(self, signature: str, entry: Dict[str, Any]):
        with self._lock:
            entry["last_updated"] = datetime.now().isoformat()
            self._library[signature] = entry
            self._save()
    
    def get_all_devices(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._library)
    
    def record_device_connection(self, device_info: Dict[str, Any], framework_type: str,
                                  frameworks_status: Dict[str, str]):
        signature = self.get_device_signature(device_info)
        entry = {
            "signature": signature,
            "device_name": device_info.get("name", "Unknown"),
            "device_category": device_info.get("category", "unknown"),
            "vid": device_info.get("vid") or device_info.get("capabilities", {}).get("vid"),
            "pid": device_info.get("pid") or device_info.get("capabilities", {}).get("pid"),
            "framework_type": framework_type,
            "frameworks": frameworks_status,
            "first_seen": self._library.get(signature, {}).get("first_seen", datetime.now().isoformat()),
            "last_seen": datetime.now().isoformat(),
            "connection_count": self._library.get(signature, {}).get("connection_count", 0) + 1
        }
        self.update_device_entry(signature, entry)
        logger.info(f"📝 Recorded device in framework library: {device_info.get('name')} ({framework_type})")


class DeviceFrameworkManager:
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.library = DeviceFrameworkLibrary()
        self._install_lock = threading.Lock()
        self._installed_cache: Set[str] = set()
        self._failed_cache: Set[str] = set()
        self._check_preinstalled()
    
    def _check_preinstalled(self):
        for pkg in ["pyserial", "esptool"]:
            if self._is_python_package_installed(pkg):
                self._installed_cache.add(f"python:{pkg}")
        
        for tool in ["dfu-util", "arduino-cli", "particle"]:
            if shutil.which(tool):
                self._installed_cache.add(f"system:{tool}")
    
    def _is_python_package_installed(self, package: str) -> bool:
        import_map = {"pyserial": "serial", "esptool": "esptool"}
        import_name = import_map.get(package, package)
        try:
            __import__(import_name)
            return True
        except ImportError:
            return False
    
    def _install_python_package(self, package: str) -> bool:
        cache_key = f"python:{package}"
        if cache_key in self._installed_cache:
            return True
        if cache_key in self._failed_cache:
            return False
        
        if self._is_python_package_installed(package):
            self._installed_cache.add(cache_key)
            return True
        
        logger.info(f"📦 Auto-installing Python package: {package}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package, "--quiet"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                self._installed_cache.add(cache_key)
                logger.info(f"✅ Installed Python package: {package}")
                self._publish_event("framework.installed", {"type": "python", "package": package})
                return True
            else:
                self._failed_cache.add(cache_key)
                logger.warning(f"❌ Failed to install {package}: {result.stderr}")
                return False
        except Exception as e:
            self._failed_cache.add(cache_key)
            logger.warning(f"❌ Exception installing {package}: {e}")
            return False
    
    def _install_system_tool(self, tool: str) -> bool:
        cache_key = f"system:{tool}"
        if cache_key in self._installed_cache:
            return True
        if cache_key in self._failed_cache:
            return False
        
        if shutil.which(tool):
            self._installed_cache.add(cache_key)
            return True
        
        logger.info(f"🔧 Attempting to install system tool: {tool}")
        
        if _is_wsl():
            success = self._install_via_apt(tool)
            if not success:
                success = self._install_via_winget(tool)
        elif sys.platform == "win32":
            success = self._install_via_winget(tool)
            if not success:
                success = self._install_via_choco(tool)
        else:
            success = self._install_via_apt(tool)
        
        if success:
            self._installed_cache.add(cache_key)
            self._publish_event("framework.installed", {"type": "system", "tool": tool})
        else:
            self._failed_cache.add(cache_key)
            logger.warning(f"⚠️ Could not auto-install {tool}. Manual install may be required.")
            self._publish_event("framework.install_failed", {
                "type": "system", 
                "tool": tool,
                "instructions": self._get_install_instructions(tool)
            })
        
        return success
    
    def _install_via_apt(self, tool: str) -> bool:
        apt_packages = {
            "dfu-util": "dfu-util",
            "arduino-cli": None,
            "stm32flash": "stm32flash",
            "teensy_loader_cli": None
        }
        
        apt_pkg = apt_packages.get(tool)
        if not apt_pkg:
            return False
        
        try:
            result = subprocess.run(
                ["sudo", "-n", "apt-get", "install", "-y", apt_pkg],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                logger.info(f"✅ Installed {tool} via apt-get")
                return True
        except Exception as e:
            logger.debug(f"apt-get install failed: {e}")
        return False
    
    def _install_via_winget(self, tool: str) -> bool:
        winget_packages = {
            "dfu-util": "dfu-util.dfu-util",
            "arduino-cli": "Arduino.ArduinoCLI"
        }
        
        winget_pkg = winget_packages.get(tool)
        if not winget_pkg:
            return False
        
        try:
            ps_cmd = f"winget install --id {winget_pkg} --silent --accept-package-agreements --accept-source-agreements"
            if _is_wsl():
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            if result.returncode == 0:
                logger.info(f"✅ Installed {tool} via winget")
                return True
        except Exception as e:
            logger.debug(f"winget install failed: {e}")
        return False
    
    def _install_via_choco(self, tool: str) -> bool:
        choco_packages = {
            "dfu-util": "dfu-util",
            "arduino-cli": "arduino-cli"
        }
        
        choco_pkg = choco_packages.get(tool)
        if not choco_pkg:
            return False
        
        try:
            result = subprocess.run(
                ["choco", "install", choco_pkg, "-y"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                logger.info(f"✅ Installed {tool} via chocolatey")
                return True
        except Exception as e:
            logger.debug(f"choco install failed: {e}")
        return False
    
    def _install_node_package(self, package: str) -> bool:
        cache_key = f"node:{package}"
        if cache_key in self._installed_cache:
            return True
        if cache_key in self._failed_cache:
            return False
        
        if package == "particle-cli":
            if shutil.which("particle"):
                self._installed_cache.add(cache_key)
                return True
        
        logger.info(f"📦 Attempting to install Node package: {package}")
        try:
            npm_cmd = "npm.cmd" if sys.platform == "win32" and not _is_wsl() else "npm"
            result = subprocess.run(
                [npm_cmd, "install", "-g", package],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                self._installed_cache.add(cache_key)
                logger.info(f"✅ Installed Node package: {package}")
                return True
        except Exception as e:
            logger.debug(f"npm install failed: {e}")
        
        self._failed_cache.add(cache_key)
        return False
    
    def _get_install_instructions(self, tool: str) -> str:
        instructions = {
            "dfu-util": "Windows: winget install dfu-util.dfu-util | Ubuntu/WSL: sudo apt-get install dfu-util",
            "arduino-cli": "Windows: winget install Arduino.ArduinoCLI | See https://arduino.github.io/arduino-cli/",
            "particle-cli": "npm install -g particle-cli | See https://docs.particle.io/getting-started/developer-tools/cli/",
            "stm32flash": "Ubuntu/WSL: sudo apt-get install stm32flash",
            "teensy_loader_cli": "See https://www.pjrc.com/teensy/loader_cli.html"
        }
        return instructions.get(tool, f"Please install {tool} manually")
    
    def _publish_event(self, event_type: str, data: Dict[str, Any]):
        if self.event_bus:
            try:
                if hasattr(self.event_bus, 'publish_sync'):
                    self.event_bus.publish_sync(event_type, data)
                elif hasattr(self.event_bus, 'publish'):
                    self.event_bus.publish(event_type, data)
            except Exception as e:
                logger.debug(f"Event publish error: {e}")
    
    def detect_framework_type(self, device_info: Dict[str, Any]) -> str:
        vid = device_info.get("vid") or device_info.get("capabilities", {}).get("vid", 0)
        pid = device_info.get("pid") or device_info.get("capabilities", {}).get("pid", 0)
        
        if vid and pid:
            framework = VID_PID_TO_FRAMEWORK.get((vid, pid))
            if framework:
                return framework
        
        name = (device_info.get("name", "") or "").lower()
        category_raw = device_info.get("category", "")
        try:
            category = category_raw.value.lower() if hasattr(category_raw, 'value') else str(category_raw).lower()
        except Exception:
            category = str(category_raw).lower()
        
        if "particle" in name or "photon" in name or "argon" in name or "boron" in name:
            return "particle"
        if "arduino" in name or category == "arduino":
            return "arduino"
        if "esp32" in name or "esp8266" in name or category == "esp32":
            return "esp32"
        if "stm32" in name or category == "stm32":
            return "stm32"
        if "teensy" in name or category == "teensy":
            return "teensy"
        if "pico" in name or "rp2040" in name or category == "pico":
            return "pico"
        
        return "generic_serial"
    
    def ensure_frameworks_for_device(self, device_info: Dict[str, Any]) -> Dict[str, Any]:
        with self._install_lock:
            framework_type = self.detect_framework_type(device_info)
            requirements = DEVICE_FRAMEWORK_REQUIREMENTS.get(framework_type, DEVICE_FRAMEWORK_REQUIREMENTS["generic_serial"])
            
            results = {
                "framework_type": framework_type,
                "python_packages": {},
                "system_tools": {},
                "node_packages": {},
                "all_installed": True
            }
            
            for pkg in requirements.get("python", []):
                success = self._install_python_package(pkg)
                results["python_packages"][pkg] = "installed" if success else "failed"
                if not success:
                    results["all_installed"] = False
            
            for tool in requirements.get("system", []):
                success = self._install_system_tool(tool)
                results["system_tools"][tool] = "installed" if success else "failed"
                if not success:
                    results["all_installed"] = False
            
            for pkg in requirements.get("node", []):
                success = self._install_node_package(pkg)
                results["node_packages"][pkg] = "installed" if success else "failed"
                if not success:
                    results["all_installed"] = False
            
            frameworks_status = {
                **results["python_packages"],
                **results["system_tools"],
                **results["node_packages"]
            }
            self.library.record_device_connection(device_info, framework_type, frameworks_status)
            
            self._publish_event("framework.ensured", {
                "device": device_info.get("name", "Unknown"),
                "framework_type": framework_type,
                "results": results
            })
            
            return results
    
    def get_device_history(self) -> Dict[str, Dict[str, Any]]:
        return self.library.get_all_devices()
    
    def get_frameworks_for_signature(self, signature: str) -> Optional[Dict[str, Any]]:
        return self.library.get_device_entry(signature)
    
    def query_ollama_for_frameworks(self, device_info: Dict[str, Any], ollama_connector=None) -> Optional[Dict[str, Any]]:
        if not ollama_connector:
            return None
        
        query = f"""I have a device with the following information:
- Name: {device_info.get('name', 'Unknown')}
- Category: {device_info.get('category', 'Unknown')}
- VID:PID: {device_info.get('vid', 'N/A')}:{device_info.get('pid', 'N/A')}
- Port: {device_info.get('port', 'N/A')}

What Python packages, system tools, and SDKs are needed to program/communicate with this device?
Respond with JSON: {{"python": ["pkg1"], "system": ["tool1"], "node": ["pkg1"], "notes": "..."}}"""
        
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(ollama_connector.generate_text(query))
                if response:
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', response)
                    if json_match:
                        return json.loads(json_match.group())
            finally:
                loop.close()
        except Exception as e:
            logger.debug(f"Ollama framework query failed: {e}")
        
        return None


_device_framework_manager: Optional[DeviceFrameworkManager] = None


def get_device_framework_manager(event_bus=None) -> DeviceFrameworkManager:
    global _device_framework_manager
    if _device_framework_manager is None:
        _device_framework_manager = DeviceFrameworkManager(event_bus)
    elif event_bus and not _device_framework_manager.event_bus:
        _device_framework_manager.event_bus = event_bus
    return _device_framework_manager
