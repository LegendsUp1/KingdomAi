#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

Host Device Manager for Kingdom AI - SOTA 2025/2026



Unified service for detecting and managing all host system devices:

- USB/Serial devices (microcontrollers, Arduino, etc.)

- Bluetooth devices (speakers, headphones, controllers)

- Audio devices (microphones, speakers, sound cards)

- Webcams and video capture devices

- VR headsets (Meta Quest, OpenXR devices)



Provides normalized device model, event bus publishing, and MCP tool exposure.

"""



import os

import sys

import json

import time

import logging

import threading

import subprocess

import re

from enum import Enum

from dataclasses import dataclass, field, asdict

from typing import Dict, List, Optional, Any, Callable, Set

from datetime import datetime





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





def _wsl_resolve_exe(name: str) -> str:
    """Resolve Windows executables to full path when running as root in WSL2."""
    import shutil, platform
    if shutil.which(name):
        return name
    if 'microsoft' in platform.uname().release.lower():
        candidates = {
            'powershell.exe': '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
            'cmd.exe': '/mnt/c/Windows/System32/cmd.exe',
        }
        full = candidates.get(name, f'/mnt/c/Windows/System32/{name}')
        if os.path.exists(full):
            return full
    return name

_POWERSHELL = _wsl_resolve_exe("powershell.exe") if _is_wsl() else "powershell"

_CMD = _wsl_resolve_exe("cmd.exe") if _is_wsl() else "cmd"





def _run_powershell(script: str, timeout: float, capture_output: bool = True) -> subprocess.CompletedProcess:

    return subprocess.run(

        [_POWERSHELL, "-NoProfile", "-Command", script],

        capture_output=capture_output,

        text=True,

        timeout=timeout,

    )





def _open_windows_uri(uri: str) -> subprocess.CompletedProcess:

    return subprocess.run(

        [_CMD, "/c", "start", "", uri],

        capture_output=True,

        text=True,

        timeout=5,

    )





def _query_sounddevice_devices_subprocess(timeout: float = 8) -> List[Dict[str, Any]]:

    try:

        code = (

            "import json, sys\n"

            "try:\n"

            "    import sounddevice as sd\n"

            "    devices = [dict(d) for d in sd.query_devices()]\n"

            "    sys.stdout.write(json.dumps(devices))\n"

            "except Exception:\n"

            "    import traceback\n"

            "    traceback.print_exc()\n"

            "    sys.exit(1)\n"

        )



        result = subprocess.run(

            [sys.executable, "-c", code],

            capture_output=True,

            text=True,

            timeout=timeout,

            env={

                **os.environ,

                "PYTHONNOUSERSITE": "1",

                "PYTHONUNBUFFERED": "1",

            },

        )

        if result.returncode != 0:

            stderr = (result.stderr or "").strip()

            stdout = (result.stdout or "").strip()

            logging.getLogger(__name__).debug(

                f"sounddevice subprocess device query failed: rc={result.returncode} stderr={stderr[:4000]} stdout={stdout[:4000]}"

            )

            return []



        out = (result.stdout or "").strip()

        if not out:

            return []



        data = json.loads(out)

        if isinstance(data, list):

            return data

        return []

    except subprocess.TimeoutExpired:

        logging.getLogger(__name__).debug("sounddevice subprocess device query timed out")

        return []

    except Exception as e:

        logging.getLogger(__name__).debug(f"sounddevice subprocess device query error: {e}")

        return []





def _detect_bluetooth_nearby_winrt(timeout: float = 20) -> List[Dict[str, Any]]:

    try:

        script = r'''

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

$DeviceInformation = [Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType = WindowsRuntime]

$DeviceInformationKind = [Windows.Devices.Enumeration.DeviceInformationKind, Windows.Devices.Enumeration, ContentType = WindowsRuntime]

$aqs = 'System.Devices.DevObjectType:=5 AND System.Devices.Aep.ProtocolId:="{E0CBF06C-CD8B-4647-BB8A-263B43F0F974}"'

$props = @(

  'System.Devices.Aep.DeviceAddress',

  'System.Devices.Aep.IsConnected',

  'System.Devices.Aep.IsPaired'

)

$op = $DeviceInformation::FindAllAsync($aqs, $props, $DeviceInformationKind::AssociationEndpoint)

$task = [System.WindowsRuntimeSystemExtensions]::AsTask($op)

$task.Wait()

$coll = $task.Result

$items = @()

foreach ($d in $coll) {

  $isPaired = $false

  try { $isPaired = [bool]$d.Pairing.IsPaired } catch {}

  $isConnected = $false

  try { $isConnected = [bool]$d.Properties['System.Devices.Aep.IsConnected'] } catch {}

  $addr = ''

  try { $addr = [string]$d.Properties['System.Devices.Aep.DeviceAddress'] } catch {}

  $items += [pscustomobject]@{

    id = [string]$d.Id

    name = [string]$d.Name

    is_paired = $isPaired

    is_connected = $isConnected

    address = $addr

  }

}

$items | ConvertTo-Json -Depth 4

'''

        result = _run_powershell(script, timeout=timeout)

        if result.returncode != 0:

            return []

        out = (result.stdout or "").strip()

        if not out:

            return []

        data = json.loads(out)

        if isinstance(data, dict):

            return [data]

        if isinstance(data, list):

            return data

        return []

    except Exception:

        return []





def _pair_bluetooth_winrt_powershell(device_id: str, timeout: float = 90) -> Dict[str, Any]:

    try:

        if not device_id:

            return {"success": False, "error": "missing_device_id"}



        safe_id = device_id.replace("`", "``").replace('"', '`"')

        script = rf'''

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

$DeviceInformation = [Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType = WindowsRuntime]

$id = "{safe_id}"

$op = $DeviceInformation::CreateFromIdAsync($id)

$task = [System.WindowsRuntimeSystemExtensions]::AsTask($op)

$task.Wait()

$info = $task.Result

if (-not $info) {{ throw 'DeviceInformation not found' }}

$pairing = $info.Pairing

if ($pairing.IsPaired) {{

  [pscustomobject]@{{ success = $true; status = 'already_paired' }} | ConvertTo-Json -Depth 4

  exit 0

}}

$op2 = $pairing.PairAsync()

$task2 = [System.WindowsRuntimeSystemExtensions]::AsTask($op2)

$task2.Wait()

$res = $task2.Result

[pscustomobject]@{{ success = $true; status = [string]$res.Status }} | ConvertTo-Json -Depth 4

'''

        result = _run_powershell(script, timeout=timeout)

        out = (result.stdout or "").strip()

        if result.returncode != 0:

            return {"success": False, "error": (result.stderr or "").strip() or "pair_failed", "raw": out}

        if not out:

            return {"success": False, "error": "no_output"}

        data = json.loads(out)

        if isinstance(data, dict):

            return data

        return {"success": True, "raw": data}

    except Exception as e:

        return {"success": False, "error": str(e)}



logger = logging.getLogger("KingdomAI.HostDeviceManager")



# SOTA 2026: Universal Data Visualizer integration

try:

    from core.universal_data_visualizer import get_universal_visualizer, DataType as VisDataType

    HAS_VISUALIZER = True

except ImportError:

    HAS_VISUALIZER = False

    VisDataType = None



# ============================================================================

# DEVICE ENUMS AND DATA MODELS

# ============================================================================



class DeviceCategory(Enum):

    """Categories of host devices - SOTA 2026 Universal Device Support"""

    # Basic I/O

    USB = "usb"

    SERIAL = "serial"

    BLUETOOTH = "bluetooth"

    AUDIO_INPUT = "audio_input"

    AUDIO_OUTPUT = "audio_output"

    WEBCAM = "webcam"

    VR_HEADSET = "vr_headset"

    CONTROLLER = "controller"

    SDR = "sdr"  # Software Defined Radio devices

    NETWORK = "network"  # Network interfaces

    

    # LiDAR & Sensors - SOTA 2026

    LIDAR = "lidar"                      # LiDAR sensors (Velodyne, SICK, Livox, Ouster)

    RADAR = "radar"                      # RADAR sensors

    DEPTH_CAMERA = "depth_camera"        # Intel RealSense, Kinect

    THERMAL_CAMERA = "thermal_camera"    # FLIR, thermal imaging

    IMU = "imu"                          # Inertial measurement units

    GPS_RECEIVER = "gps_receiver"        # GPS/GNSS receivers

    

    # Automotive - SOTA 2026

    CAN_INTERFACE = "can_interface"      # CAN bus adapters

    OBD2_ADAPTER = "obd2_adapter"        # OBD-II diagnostic adapters

    J1939_INTERFACE = "j1939_interface"  # Heavy vehicle J1939

    

    # Microcontrollers - SOTA 2026

    ARDUINO = "arduino"                  # Arduino boards

    ESP32 = "esp32"                      # ESP32/ESP8266

    STM32 = "stm32"                      # STM32 boards

    RASPBERRY_PI = "raspberry_pi"        # Raspberry Pi

    TEENSY = "teensy"                    # PJRC Teensy

    PICO = "pico"                        # RP2040/Pico

    FPGA = "fpga"                        # FPGA dev boards

    

    # Lab Equipment - SOTA 2026

    OSCILLOSCOPE = "oscilloscope"        # Digital oscilloscopes

    SIGNAL_GEN = "signal_generator"      # Signal generators

    DMM = "dmm"                          # Digital multimeters

    POWER_SUPPLY = "power_supply"        # Programmable PSUs

    LOGIC_ANALYZER = "logic_analyzer"    # Logic analyzers

    SPECTRUM_ANALYZER = "spectrum_analyzer"  # RF spectrum analyzers

    

    # Robotics/Drones - SOTA 2026

    DRONE = "drone"                      # UAVs/drones (MAVLink)

    ROBOT_ARM = "robot_arm"              # Robotic arms

    SERVO_CONTROLLER = "servo_controller"  # Servo/motor controllers

    RANGE_SENSOR = "range_sensor"        # Ultrasonic/sonar/distance sensors (HC-SR04, TFmini, VL53L0X)

    

    # Military/Industrial - SOTA 2026

    RADIO_MILITARY = "radio_military"    # MIL-STD radios

    MODBUS_DEVICE = "modbus_device"      # Modbus devices

    PLC = "plc"                          # PLCs

    

    # Imaging Devices - SOTA 2026 (microscopes, telescopes, special cameras)

    USB_MICROSCOPE = "usb_microscope"    # Digital USB microscopes

    TELESCOPE_CAMERA = "telescope_camera"  # Telescope cameras / astrophotography

    ENDOSCOPE = "endoscope"              # USB endoscopes / borescopes

    DOCUMENT_CAMERA = "document_camera"  # Document cameras / visualizers

    PI_CAMERA = "pi_camera"              # Raspberry Pi cameras

    # THERMAL_CAMERA already defined in sensors section

    NIGHT_VISION = "night_vision"        # Night vision / IR cameras

    ACTION_CAMERA = "action_camera"      # GoPro / action cameras

    

    # Bluetooth/Wireless Devices - SOTA 2026

    BT_WEBCAM = "bt_webcam"              # Bluetooth webcams

    BT_SPEAKER = "bt_speaker"            # Bluetooth speakers

    BT_HEADPHONES = "bt_headphones"      # Bluetooth headphones/earbuds

    BT_KEYBOARD = "bt_keyboard"          # Bluetooth keyboards

    BT_MOUSE = "bt_mouse"                # Bluetooth mice

    BT_GAMEPAD = "bt_gamepad"            # Bluetooth game controllers

    WIFI_CAMERA = "wifi_camera"          # WiFi IP cameras

    WIFI_DOORBELL = "wifi_doorbell"      # Smart doorbells (Ring, Nest)

    

    # RC Toys & Drones - SOTA 2026

    RC_CAR = "rc_car"                    # RC cars (27/49/2.4 GHz)

    RC_PLANE = "rc_plane"                # RC planes

    RC_BOAT = "rc_boat"                  # RC boats

    RC_HELICOPTER = "rc_helicopter"      # RC helicopters

    FPV_DRONE = "fpv_drone"              # FPV racing drones

    TOY_DRONE = "toy_drone"              # Consumer toy drones

    

    # Smart Home - SOTA 2026

    SMART_BULB = "smart_bulb"            # Zigbee/WiFi smart bulbs

    SMART_PLUG = "smart_plug"            # Smart plugs/switches

    SMART_LOCK = "smart_lock"            # Smart locks

    SMART_THERMOSTAT = "smart_thermostat"  # Smart thermostats

    

    UNKNOWN = "unknown"





# ============================================================================

# DEVICES NEEDED PER FEATURE - SOTA 2026 Hardware Guidance

# ============================================================================



# ============================================================================

# CHAMELEON UI PANEL DEFINITIONS - Adaptive UI for each device type

# ============================================================================



CHAMELEON_CONTROL_PANELS = {

    DeviceCategory.LIDAR: {

        "name": "LiDAR Scanner Control", "icon": "📡", "color": "#00ff88",

        "os_style": "industrial",

        "controls": [

            {"id": "rpm", "label": "Rotation Speed (RPM)", "type": "slider", "min": 300, "max": 1200},

            {"id": "return_mode", "label": "Return Mode", "type": "dropdown", "options": ["Strongest", "Last", "Dual"]},

            {"id": "range_min", "label": "Min Range (m)", "type": "number", "default": 0.1},

            {"id": "range_max", "label": "Max Range (m)", "type": "number", "default": 100},

            {"id": "stream", "label": "Stream Point Cloud", "type": "toggle"},

        ],

        "displays": ["3d_pointcloud", "rpm_gauge", "temperature_gauge"]

    },

    DeviceCategory.CAN_INTERFACE: {

        "name": "CAN Bus Controller", "icon": "🚗", "color": "#ff9900",

        "os_style": "automotive",

        "controls": [

            {"id": "bitrate", "label": "Bitrate", "type": "dropdown", "options": ["125 kbps", "250 kbps", "500 kbps", "1 Mbps"]},

            {"id": "fd_mode", "label": "CAN-FD Mode", "type": "toggle"},

            {"id": "termination", "label": "120Ω Termination", "type": "toggle"},

            {"id": "tx_id", "label": "TX CAN ID", "type": "hex_input"},

            {"id": "tx_data", "label": "TX Data", "type": "hex_input"},

            {"id": "send", "label": "Send Frame", "type": "button", "action": "transmit"},

        ],

        "displays": ["message_log", "bus_load_gauge", "error_counter"]

    },

    DeviceCategory.OBD2_ADAPTER: {

        "name": "OBD-II Diagnostics", "icon": "🔧", "color": "#ff6600",

        "os_style": "automotive",

        "controls": [

            {"id": "protocol", "label": "Protocol", "type": "dropdown", "options": ["Auto", "CAN", "KWP", "ISO 9141"]},

            {"id": "scan_dtc", "label": "Scan DTCs", "type": "button", "action": "scan_dtc"},

            {"id": "clear_dtc", "label": "Clear DTCs", "type": "button", "action": "clear_dtc"},

            {"id": "pids", "label": "Live PIDs", "type": "pid_selector"},

            {"id": "stream", "label": "Stream Data", "type": "toggle"},

        ],

        "displays": ["gauge_cluster", "dtc_list", "freeze_frame"]

    },

    DeviceCategory.ARDUINO: {

        "name": "Arduino Controller", "icon": "🔌", "color": "#00979d",

        "os_style": "arduino_ide",

        "controls": [

            {"id": "baudrate", "label": "Baudrate", "type": "dropdown", "options": ["9600", "115200", "921600"]},

            {"id": "connect", "label": "Connect", "type": "button", "action": "connect"},

            {"id": "reset", "label": "Reset Board", "type": "button", "action": "reset"},

            {"id": "pins", "label": "GPIO Pins", "type": "pin_grid", "modes": ["INPUT", "OUTPUT", "PWM"]},

            {"id": "serial_send", "label": "Send", "type": "text_input"},

        ],

        "displays": ["serial_monitor", "pin_states", "analog_chart"]

    },

    DeviceCategory.ESP32: {

        "name": "ESP32 Controller", "icon": "📶", "color": "#e7352c",

        "os_style": "espressif",

        "controls": [

            {"id": "wifi_mode", "label": "WiFi Mode", "type": "dropdown", "options": ["Station", "AP", "Station+AP"]},

            {"id": "ssid", "label": "SSID", "type": "text_input"},

            {"id": "wifi_connect", "label": "Connect WiFi", "type": "button", "action": "wifi_connect"},

            {"id": "ble_enabled", "label": "BLE Enabled", "type": "toggle"},

            {"id": "gpio", "label": "GPIO", "type": "pin_grid", "pins": 34},

        ],

        "displays": ["serial_monitor", "wifi_status", "memory_usage"]

    },

    DeviceCategory.SDR: {

        "name": "Software Defined Radio", "icon": "📻", "color": "#7aa2f7",

        "os_style": "sdr_console",

        "controls": [

            {"id": "freq", "label": "Center Frequency (MHz)", "type": "frequency_input"},

            {"id": "gain", "label": "RF Gain (dB)", "type": "slider", "min": 0, "max": 60},

            {"id": "bandwidth", "label": "Bandwidth (kHz)", "type": "slider", "min": 200, "max": 28000},

            {"id": "modulation", "label": "Modulation", "type": "dropdown", "options": ["AM", "FM", "USB", "LSB", "CW"]},

            {"id": "agc", "label": "AGC", "type": "toggle"},

            {"id": "squelch", "label": "Squelch (dB)", "type": "slider", "min": -100, "max": 0},

        ],

        "displays": ["spectrum_fft", "waterfall", "signal_meter"]

    },

    DeviceCategory.DRONE: {

        "name": "UAV Flight Controller", "icon": "🚁", "color": "#ff4444",

        "os_style": "mavlink",

        "controls": [

            {"id": "flight_mode", "label": "Flight Mode", "type": "dropdown", "options": ["STABILIZE", "ALT_HOLD", "LOITER", "AUTO", "RTL"]},

            {"id": "arm", "label": "ARM", "type": "button", "action": "arm"},

            {"id": "disarm", "label": "DISARM", "type": "button", "action": "disarm"},

            {"id": "rtl", "label": "RETURN TO LAUNCH", "type": "button", "action": "rtl", "danger": True},

            {"id": "max_alt", "label": "Max Altitude (m)", "type": "number", "default": 120},

            {"id": "geofence", "label": "Geofence", "type": "toggle"},

        ],

        "displays": ["attitude_indicator", "map_view", "telemetry_panel", "battery_status"]

    },

    DeviceCategory.OSCILLOSCOPE: {

        "name": "Digital Oscilloscope", "icon": "📈", "color": "#00ff00",

        "os_style": "lab_equipment",

        "controls": [

            {"id": "timebase", "label": "Time/Div", "type": "dropdown", "options": ["1µs", "10µs", "100µs", "1ms", "10ms"]},

            {"id": "ch1_scale", "label": "CH1 V/Div", "type": "dropdown", "options": ["10mV", "100mV", "1V", "10V"]},

            {"id": "ch1_coupling", "label": "CH1 Coupling", "type": "dropdown", "options": ["DC", "AC", "GND"]},

            {"id": "trig_mode", "label": "Trigger Mode", "type": "dropdown", "options": ["Auto", "Normal", "Single"]},

            {"id": "trig_level", "label": "Trigger Level", "type": "slider", "min": -100, "max": 100},

        ],

        "displays": ["waveform_display", "measurements", "fft"]

    },

    DeviceCategory.RADIO_MILITARY: {

        "name": "Tactical Radio (MIL-STD)", "icon": "🎖️", "color": "#556b2f",

        "os_style": "military",

        "controls": [

            {"id": "freq", "label": "Frequency", "type": "frequency_input"},

            {"id": "band", "label": "Band", "type": "dropdown", "options": ["VHF", "UHF", "SATCOM"]},

            {"id": "power", "label": "TX Power (W)", "type": "slider", "min": 0, "max": 50},

            {"id": "waveform", "label": "Waveform", "type": "dropdown", "options": ["SINCGARS", "HAVEQUICK", "Link-16"]},

            {"id": "comsec", "label": "COMSEC", "type": "toggle"},

            {"id": "freq_hop", "label": "Freq Hop", "type": "toggle"},

        ],

        "displays": ["signal_meter", "net_roster", "position_display"]

    },

    DeviceCategory.USB_MICROSCOPE: {

        "name": "Digital Microscope", "icon": "🔬", "color": "#00ffcc",

        "os_style": "imaging",

        "controls": [

            {"id": "zoom", "label": "Digital Zoom", "type": "slider", "min": 1, "max": 10},

            {"id": "brightness", "label": "LED Brightness", "type": "slider", "min": 0, "max": 100},

            {"id": "focus", "label": "Auto Focus", "type": "toggle"},

            {"id": "snapshot", "label": "Capture Image", "type": "button", "action": "capture"},

            {"id": "record", "label": "Record Video", "type": "toggle"},

            {"id": "measure", "label": "Measure Mode", "type": "toggle"},

        ],

        "displays": ["video_feed", "histogram", "measurement_overlay"]

    },

    DeviceCategory.TELESCOPE_CAMERA: {

        "name": "Telescope Camera", "icon": "🔭", "color": "#4169e1",

        "os_style": "astrophotography",

        "controls": [

            {"id": "exposure", "label": "Exposure (s)", "type": "slider", "min": 0.001, "max": 300},

            {"id": "gain", "label": "Gain/ISO", "type": "slider", "min": 0, "max": 100},

            {"id": "cooler", "label": "Sensor Cooling", "type": "toggle"},

            {"id": "temp_target", "label": "Target Temp (°C)", "type": "number", "default": -10},

            {"id": "capture", "label": "Capture Frame", "type": "button", "action": "capture"},

            {"id": "stack", "label": "Auto Stack", "type": "toggle"},

        ],

        "displays": ["video_feed", "histogram", "star_detection", "guiding"]

    },

    DeviceCategory.ENDOSCOPE: {

        "name": "USB Endoscope", "icon": "🔍", "color": "#ff6b6b",

        "os_style": "inspection",

        "controls": [

            {"id": "led", "label": "LED Light", "type": "slider", "min": 0, "max": 100},

            {"id": "mirror", "label": "Mirror Image", "type": "toggle"},

            {"id": "snapshot", "label": "Capture", "type": "button", "action": "capture"},

            {"id": "record", "label": "Record", "type": "toggle"},

        ],

        "displays": ["video_feed", "snapshot_gallery"]

    },

    DeviceCategory.PI_CAMERA: {

        "name": "Raspberry Pi Camera", "icon": "🍓", "color": "#c51a4a",

        "os_style": "raspberry_pi",

        "controls": [

            {"id": "resolution", "label": "Resolution", "type": "dropdown", "options": ["640x480", "1280x720", "1920x1080", "4056x3040"]},

            {"id": "fps", "label": "Frame Rate", "type": "dropdown", "options": ["15", "30", "60", "90"]},

            {"id": "exposure", "label": "Exposure Mode", "type": "dropdown", "options": ["auto", "night", "sports", "verylong"]},

            {"id": "awb", "label": "White Balance", "type": "dropdown", "options": ["auto", "sun", "cloud", "tungsten"]},

            {"id": "hflip", "label": "H-Flip", "type": "toggle"},

            {"id": "vflip", "label": "V-Flip", "type": "toggle"},

            {"id": "stream", "label": "Start Stream", "type": "button", "action": "stream"},

        ],

        "displays": ["video_feed", "histogram"]

    },

    DeviceCategory.THERMAL_CAMERA: {

        "name": "Thermal Camera", "icon": "🌡️", "color": "#ff4500",

        "os_style": "thermal",

        "controls": [

            {"id": "palette", "label": "Color Palette", "type": "dropdown", "options": ["Iron", "Rainbow", "Grayscale", "Lava", "Arctic"]},

            {"id": "range_min", "label": "Min Temp (°C)", "type": "number", "default": -20},

            {"id": "range_max", "label": "Max Temp (°C)", "type": "number", "default": 150},

            {"id": "spot_meter", "label": "Spot Meter", "type": "toggle"},

            {"id": "capture", "label": "Capture", "type": "button", "action": "capture"},

        ],

        "displays": ["thermal_view", "temperature_scale", "histogram"]

    },

    DeviceCategory.NIGHT_VISION: {

        "name": "Night Vision Camera", "icon": "🌙", "color": "#32cd32",

        "os_style": "night_vision",

        "controls": [

            {"id": "ir_led", "label": "IR LED", "type": "toggle"},

            {"id": "gain", "label": "Image Gain", "type": "slider", "min": 0, "max": 100},

            {"id": "mode", "label": "Mode", "type": "dropdown", "options": ["Green", "White", "Color"]},

            {"id": "capture", "label": "Capture", "type": "button", "action": "capture"},

        ],

        "displays": ["video_feed", "light_meter"]

    },

    # Bluetooth/Wireless Devices

    DeviceCategory.BT_WEBCAM: {

        "name": "Bluetooth Webcam", "icon": "📹", "color": "#0082fc",

        "os_style": "bluetooth",

        "controls": [

            {"id": "stream", "label": "Start Stream", "type": "button", "action": "stream"},

            {"id": "resolution", "label": "Resolution", "type": "dropdown", "options": ["720p", "1080p", "4K"]},

            {"id": "capture", "label": "Capture", "type": "button", "action": "capture"},

            {"id": "pair", "label": "Pair Device", "type": "button", "action": "pair"},

        ],

        "displays": ["video_feed", "connection_status"]

    },

    DeviceCategory.WIFI_CAMERA: {

        "name": "WiFi IP Camera", "icon": "📷", "color": "#ff9500",

        "os_style": "ip_camera",

        "controls": [

            {"id": "stream_url", "label": "Stream URL", "type": "text_input"},

            {"id": "connect", "label": "Connect", "type": "button", "action": "connect"},

            {"id": "ptz_up", "label": "Pan Up", "type": "button", "action": "ptz_up"},

            {"id": "ptz_down", "label": "Pan Down", "type": "button", "action": "ptz_down"},

            {"id": "ptz_left", "label": "Pan Left", "type": "button", "action": "ptz_left"},

            {"id": "ptz_right", "label": "Pan Right", "type": "button", "action": "ptz_right"},

            {"id": "ir_mode", "label": "Night Vision", "type": "toggle"},

        ],

        "displays": ["video_feed", "ptz_controls"]

    },

    # RC Toys & Drones

    DeviceCategory.RC_CAR: {

        "name": "RC Car Controller", "icon": "🚗", "color": "#ff4444",

        "os_style": "rc_controller",

        "controls": [

            {"id": "throttle", "label": "Throttle", "type": "slider", "min": -100, "max": 100},

            {"id": "steering", "label": "Steering", "type": "slider", "min": -100, "max": 100},

            {"id": "forward", "label": "Forward", "type": "button", "action": "forward"},

            {"id": "backward", "label": "Backward", "type": "button", "action": "backward"},

            {"id": "left", "label": "Left", "type": "button", "action": "left"},

            {"id": "right", "label": "Right", "type": "button", "action": "right"},

            {"id": "stop", "label": "STOP", "type": "button", "action": "stop"},

            {"id": "learn", "label": "Learn Controls", "type": "button", "action": "learn"},

        ],

        "displays": ["signal_strength", "battery_level"]

    },

    DeviceCategory.RC_PLANE: {

        "name": "RC Plane Controller", "icon": "✈️", "color": "#00aaff",

        "os_style": "rc_controller",

        "controls": [

            {"id": "throttle", "label": "Throttle", "type": "slider", "min": 0, "max": 100},

            {"id": "aileron", "label": "Aileron (Roll)", "type": "slider", "min": -100, "max": 100},

            {"id": "elevator", "label": "Elevator (Pitch)", "type": "slider", "min": -100, "max": 100},

            {"id": "rudder", "label": "Rudder (Yaw)", "type": "slider", "min": -100, "max": 100},

            {"id": "learn", "label": "Learn Controls", "type": "button", "action": "learn"},

        ],

        "displays": ["signal_strength", "attitude_indicator"]

    },

    DeviceCategory.RC_BOAT: {

        "name": "RC Boat Controller", "icon": "🚤", "color": "#00ffff",

        "os_style": "rc_controller",

        "controls": [

            {"id": "throttle", "label": "Throttle", "type": "slider", "min": -100, "max": 100},

            {"id": "rudder", "label": "Rudder", "type": "slider", "min": -100, "max": 100},

            {"id": "learn", "label": "Learn Controls", "type": "button", "action": "learn"},

        ],

        "displays": ["signal_strength"]

    },

    DeviceCategory.FPV_DRONE: {

        "name": "FPV Drone Controller", "icon": "🚁", "color": "#ff00ff",

        "os_style": "drone_fpv",

        "controls": [

            {"id": "arm", "label": "ARM", "type": "toggle"},

            {"id": "throttle", "label": "Throttle", "type": "slider", "min": 0, "max": 100},

            {"id": "yaw", "label": "Yaw", "type": "slider", "min": -100, "max": 100},

            {"id": "pitch", "label": "Pitch", "type": "slider", "min": -100, "max": 100},

            {"id": "roll", "label": "Roll", "type": "slider", "min": -100, "max": 100},

            {"id": "mode", "label": "Flight Mode", "type": "dropdown", "options": ["Acro", "Angle", "Horizon"]},

            {"id": "record", "label": "Record DVR", "type": "toggle"},

        ],

        "displays": ["video_feed", "osd_overlay", "signal_strength", "battery_voltage"]

    },

    # Smart Home

    DeviceCategory.SMART_BULB: {

        "name": "Smart Bulb", "icon": "💡", "color": "#ffff00",

        "os_style": "smart_home",

        "controls": [

            {"id": "power", "label": "Power", "type": "toggle"},

            {"id": "brightness", "label": "Brightness", "type": "slider", "min": 0, "max": 100},

            {"id": "color_temp", "label": "Color Temp", "type": "slider", "min": 2700, "max": 6500},

            {"id": "color", "label": "Color", "type": "color_picker"},

        ],

        "displays": ["status", "energy_usage"]

    },

    DeviceCategory.SMART_PLUG: {

        "name": "Smart Plug", "icon": "🔌", "color": "#00ff00",

        "os_style": "smart_home",

        "controls": [

            {"id": "power", "label": "Power", "type": "toggle"},

            {"id": "schedule", "label": "Schedule", "type": "button", "action": "schedule"},

        ],

        "displays": ["status", "power_consumption", "energy_today"]

    },

}



# Add default panels for unconfigured categories

for _cat in DeviceCategory:

    if _cat not in CHAMELEON_CONTROL_PANELS:

        CHAMELEON_CONTROL_PANELS[_cat] = {

            "name": f"{_cat.value.replace('_', ' ').title()} Control",

            "icon": "⚙️", "color": "#888888", "os_style": "default",

            "controls": [

                {"id": "connect", "label": "Connect", "type": "button", "action": "connect"},

                {"id": "disconnect", "label": "Disconnect", "type": "button", "action": "disconnect"},

            ],

            "displays": ["status", "log"]

        }



# ============================================================================

# DEVICES NEEDED PER FEATURE - SOTA 2026 Hardware Guidance

# ============================================================================



DEVICES_NEEDED_PER_FEATURE = {

    "voice_commands": {

        "description": "Voice recognition and speech-to-text",

        "required": [DeviceCategory.AUDIO_INPUT],

        "recommended": ["USB microphone", "Webcam with mic", "Headset"],

        "notes": "Webcam mic (Logitech Brio, C920) or headset recommended for best quality"

    },

    "voice_output": {

        "description": "Text-to-speech and audio playback",

        "required": [DeviceCategory.AUDIO_OUTPUT],

        "recommended": ["Speakers", "Headphones", "Audio interface"],

        "notes": "Any audio output device works; XTTS uses default speaker"

    },

    "video_stream": {

        "description": "MJPEG video capture and streaming",

        "required": [DeviceCategory.WEBCAM],

        "recommended": ["Logitech Brio 4K", "Any USB webcam"],

        "notes": "Requires MJPEG server running on Windows host for WSL2"

    },

    "rf_transmit": {

        "description": "RF/SDR radio transmission",

        "required": [DeviceCategory.SDR],

        "recommended": ["HackRF One", "LimeSDR", "USRP B200"],

        "notes": "TX-capable SDR required; RTL-SDR is RX-only"

    },

    "rf_receive": {

        "description": "RF/SDR radio reception",

        "required": [DeviceCategory.SDR],

        "recommended": ["RTL-SDR V3", "HackRF One", "Airspy"],

        "notes": "RTL-SDR is cheapest RX option; SoapySDR driver required"

    },

    "sonar": {

        "description": "Passive acoustic monitoring (RMS + peak frequency)",

        "required": [DeviceCategory.AUDIO_INPUT],

        "recommended": ["USB microphone", "Audio interface"],

        "notes": "Uses microphone for passive acoustic analysis"

    },

    "udp_voice_call": {

        "description": "LAN UDP voice calls",

        "required": [DeviceCategory.AUDIO_INPUT, DeviceCategory.AUDIO_OUTPUT],

        "recommended": ["Headset with mic", "Webcam + speakers"],

        "notes": "Full-duplex audio; peer must run same feature"

    },

    "vr_trading": {

        "description": "VR immersive trading interface",

        "required": [DeviceCategory.VR_HEADSET],

        "recommended": ["Meta Quest 2/3/Pro", "Valve Index"],

        "notes": "OpenXR-compatible headset with controllers"

    },

    "bluetooth_devices": {

        "description": "Bluetooth peripherals (speakers, controllers)",

        "required": [DeviceCategory.BLUETOOTH],

        "recommended": ["Bluetooth adapter", "Built-in Bluetooth"],

        "notes": "Windows Bluetooth stack required"

    },

    "lidar_scanning": {

        "description": "3D LiDAR point cloud scanning",

        "required": [DeviceCategory.LIDAR],

        "recommended": ["Velodyne VLP-16", "SICK TiM", "RPLidar A1/A2", "Livox Mid-40"],

        "notes": "Serial or Ethernet connection required"

    },

    "vehicle_diagnostics": {

        "description": "OBD-II vehicle diagnostics and CAN bus",

        "required": [DeviceCategory.OBD2_ADAPTER],

        "recommended": ["ELM327", "OBDLink MX+", "CANable", "PCAN-USB"],

        "notes": "Vehicle OBD-II port access required"

    },

    "microcontroller_control": {

        "description": "Arduino/ESP32/STM32 programming and control",

        "required": [DeviceCategory.ARDUINO],

        "recommended": ["Arduino Uno/Mega", "ESP32 DevKit", "STM32 Nucleo", "Teensy 4.1"],

        "notes": "USB serial connection, may need drivers"

    },

    "drone_control": {

        "description": "UAV/drone flight control via MAVLink",

        "required": [DeviceCategory.DRONE],

        "recommended": ["Pixhawk", "ArduPilot", "PX4", "DJI flight controller"],

        "notes": "Telemetry radio or USB connection required"

    },

    "lab_measurements": {

        "description": "Oscilloscope and lab equipment control",

        "required": [DeviceCategory.OSCILLOSCOPE],

        "recommended": ["Rigol DS1054Z", "Siglent SDS1104", "Keysight"],

        "notes": "USB-TMC or LAN/VISA connection"

    }

}





class DeviceStatus(Enum):

    """Device connection status"""

    CONNECTED = "connected"

    DISCONNECTED = "disconnected"

    PAIRED = "paired"          # Bluetooth paired but not connected

    AVAILABLE = "available"    # Detected but not active

    ACTIVE = "active"          # Currently in use

    ERROR = "error"





@dataclass

class HostDevice:

    """Normalized device model for all device types"""

    id: str                           # Unique identifier

    name: str                         # Human-readable name

    category: DeviceCategory          # Device category

    status: DeviceStatus              # Current status

    vendor: str = ""                  # Vendor/Manufacturer

    product: str = ""                 # Product name/model

    serial: str = ""                  # Serial number if available

    port: str = ""                    # COM port / device path

    address: str = ""                 # MAC address for Bluetooth

    driver: str = ""                  # Driver name

    capabilities: Dict[str, Any] = field(default_factory=dict)

    metadata: Dict[str, Any] = field(default_factory=dict)

    last_seen: float = field(default_factory=time.time)

    

    def to_dict(self) -> Dict[str, Any]:

        """Convert to dictionary for JSON serialization"""

        return {

            "id": self.id,

            "name": self.name,

            "category": self.category.value,

            "status": self.status.value,

            "vendor": self.vendor,

            "product": self.product,

            "serial": self.serial,

            "port": self.port,

            "address": self.address,

            "driver": self.driver,

            "capabilities": self.capabilities,

            "metadata": self.metadata,

            "last_seen": self.last_seen

        }

    

    @classmethod

    def from_dict(cls, data: Dict[str, Any]) -> 'HostDevice':

        """Create from dictionary"""

        return cls(

            id=data.get("id", ""),

            name=data.get("name", "Unknown"),

            category=DeviceCategory(data.get("category", "unknown")),

            status=DeviceStatus(data.get("status", "disconnected")),

            vendor=data.get("vendor", ""),

            product=data.get("product", ""),

            serial=data.get("serial", ""),

            port=data.get("port", ""),

            address=data.get("address", ""),

            driver=data.get("driver", ""),

            capabilities=data.get("capabilities", {}),

            metadata=data.get("metadata", {}),

            last_seen=data.get("last_seen", time.time())

        )





# ============================================================================

# KINGDOM AI EXISTING SYSTEM INTEGRATIONS

# ============================================================================



class KingdomDeviceIntegration:

    """Integrates with existing Kingdom AI device systems"""

    

    @staticmethod

    def detect_vr_from_vr_manager() -> List[HostDevice]:

        """Detect VR devices using existing VRManager system.

        

        CRITICAL: VR headset has BUILT-IN MICROPHONE for voice commands!

        """

        devices = []

        try:

            from vr.vr_manager import VRManager

            vr_mgr = VRManager()

            

            # Check VR connection state

            vr_connected = hasattr(vr_mgr, 'vr_headset_connected') and vr_mgr.vr_headset_connected

            

            if vr_connected:

                device = HostDevice(

                    id="vr_kingdom_headset",

                    name="Meta Quest (Kingdom VR)",

                    category=DeviceCategory.VR_HEADSET,

                    status=DeviceStatus.CONNECTED,

                    vendor="Meta",

                    capabilities={

                        "connection_mode": getattr(vr_mgr, 'vr_connection_mode', 'unknown'),

                        "transport": getattr(vr_mgr, 'vr_connection_transport', 'unknown'),

                        "controllers": getattr(vr_mgr, 'vr_controllers_connected', False),

                        "tracking": getattr(vr_mgr, 'vr_tracking_status', 'unknown'),

                        "has_microphone": True,  # Quest has built-in mic!

                        "has_speakers": True     # Quest has built-in speakers!

                    },

                    metadata={"source": "vr_manager"}

                )

                devices.append(device)

                logger.info("✅ VR headset detected via VRManager")

                

                # CRITICAL: Add VR headset's built-in microphone as audio input for voice commands!

                vr_mic = HostDevice(

                    id="vr_headset_mic",

                    name="Meta Quest (Built-in Microphone)",

                    category=DeviceCategory.AUDIO_INPUT,

                    status=DeviceStatus.CONNECTED,

                    vendor="Meta",

                    capabilities={

                        "microphone": True,

                        "voice_commands": True,  # Can be used for voice commands!

                        "speech_recognition": True,

                        "vr_input": True,

                        "parent_device": "vr_kingdom_headset"

                    },

                    metadata={"source": "vr_headset_builtin", "parent": "Meta Quest"}

                )

                devices.append(vr_mic)

                logger.info("✅ VR headset microphone detected (voice commands enabled)")

                

                # Add VR headset speakers as audio output

                vr_speakers = HostDevice(

                    id="vr_headset_speakers",

                    name="Meta Quest (Built-in Speakers)",

                    category=DeviceCategory.AUDIO_OUTPUT,

                    status=DeviceStatus.CONNECTED,

                    vendor="Meta",

                    capabilities={

                        "speakers": True,

                        "spatial_audio": True,

                        "parent_device": "vr_kingdom_headset"

                    },

                    metadata={"source": "vr_headset_builtin", "parent": "Meta Quest"}

                )

                devices.append(vr_speakers)

            else:

                # VR system available but not connected

                device = HostDevice(

                    id="vr_kingdom_system",

                    name="Kingdom VR System",

                    category=DeviceCategory.VR_HEADSET,

                    status=DeviceStatus.AVAILABLE,

                    vendor="Meta",

                    capabilities={

                        "has_microphone": True,  # Will have mic when connected

                        "has_speakers": True

                    },

                    metadata={"source": "vr_manager", "note": "VR system available, headset not connected"}

                )

                devices.append(device)

        except ImportError:

            logger.debug("VRManager not available")

        except Exception as e:

            logger.debug(f"VR detection via VRManager error: {e}")

        return devices

    

    @staticmethod

    def detect_webcam_from_mjpeg_server() -> List[HostDevice]:

        """Detect webcam from MJPEG server AND direct ffmpeg detection.

        SOTA 2026: Generic detection - works with ANY webcam brand.

        

        CRITICAL: Webcam may have BUILT-IN MICROPHONE that can be used for voice commands!

        """

        devices = []

        camera_name = None

        server_running = False

        

        # Step 1: Always try to detect camera via ffmpeg/dshow first (ANY brand)

        try:

            from brio_mjpeg_server import _detect_camera_name

            camera_name = _detect_camera_name()

            logger.info(f"📷 FFmpeg detected camera: {camera_name}")

        except Exception as e:

            logger.debug(f"FFmpeg camera detection: {e}")

        

        # Step 2: Get Windows host IP for WSL and check if MJPEG server is running

        host_ip = "localhost"

        try:

            # Check if in WSL and get Windows host IP

            with open('/proc/version', 'r', encoding='utf-8') as f:

                version_info = f.read().lower()

                if 'microsoft' in version_info or 'wsl' in version_info:

                    with open('/etc/resolv.conf', 'r', encoding='utf-8') as rf:

                        for line in rf:

                            if line.strip().startswith('nameserver'):

                                host_ip = line.strip().split()[1]

                                logger.info(f"🖥️ Windows host IP: {host_ip}")

                                break

        except Exception:

            pass

        

        try:
            import socket
            # Use context manager for guaranteed socket cleanup
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host_ip, 8090))
                server_running = (result == 0)
        except Exception:
            pass

        

        mjpeg_url = f"http://{host_ip}:8090/brio.mjpg" if server_running else None

        

        # Step 3: Create webcam device if detected

        if camera_name:

            status = DeviceStatus.ACTIVE if server_running else DeviceStatus.CONNECTED

            device = HostDevice(

                id="webcam_primary",

                name=camera_name,

                category=DeviceCategory.WEBCAM,

                status=status,

                vendor="",  # Generic - detected from camera_name if needed

                port=mjpeg_url or "",

                capabilities={

                    "video": True,

                    "streaming": server_running,

                    "mjpeg_url": mjpeg_url,

                    "has_microphone": True,  # Most webcams have built-in mic

                    "resolution": "auto"

                },

                metadata={"source": "mjpeg_server", "server_running": server_running, "host_ip": host_ip}

            )

            devices.append(device)

            logger.info(f"✅ Webcam detected: {camera_name} (server: {'running' if server_running else 'not running'})")

            

            # Step 4: CRITICAL - Add webcam's built-in microphone as separate audio input!

            mic_device = HostDevice(

                id="webcam_primary_mic",

                name=f"{camera_name} (Built-in Microphone)",

                category=DeviceCategory.AUDIO_INPUT,

                status=DeviceStatus.CONNECTED,

                vendor="",  # Generic - any brand

                capabilities={

                    "microphone": True,

                    "voice_commands": True,  # Can be used for voice commands!

                    "speech_recognition": True,

                    "parent_device": "webcam_primary"

                },

                metadata={"source": "webcam_builtin", "parent": camera_name}

            )

            devices.append(mic_device)

            logger.info(f"✅ Webcam microphone detected: {camera_name} mic (voice commands enabled)")

                    

        return devices

    

    @staticmethod

    def detect_bluetooth_from_black_panther() -> List[HostDevice]:

        """Detect Bluetooth speakers using Black Panther Bluetooth system"""

        devices = []

        try:

            from black_panther_bluetooth import BluetoothManager

            bt_mgr = BluetoothManager()

            

            if bt_mgr.is_bluetooth_connected:

                speaker_name = bt_mgr.config.get("bluetooth_speaker", {}).get("name", "Bluetooth Speaker")

                device = HostDevice(

                    id="bt_black_panther_speaker",

                    name=speaker_name,

                    category=DeviceCategory.AUDIO_OUTPUT,

                    status=DeviceStatus.CONNECTED,

                    vendor="",  # Generic - any brand Bluetooth speaker,

                    capabilities={

                        "bluetooth": True,

                        "volume_boost": bt_mgr.config.get("bluetooth_speaker", {}).get("volume_boost", 1.0),

                        "compression": bt_mgr.config.get("bluetooth_speaker", {}).get("compression", False)

                    },

                    metadata={"source": "black_panther_bluetooth"}

                )

                devices.append(device)

                logger.info(f"✅ Bluetooth speaker detected via Black Panther: {speaker_name}")

        except ImportError:

            logger.debug("Black Panther Bluetooth not available")

        except Exception as e:

            logger.debug(f"Bluetooth detection via Black Panther error: {e}")

        return devices

    

    @staticmethod

    def detect_voice_audio_devices() -> List[HostDevice]:

        """Detect audio devices used by VoiceManager"""

        devices = []

        try:

            from core.voice_manager import VoiceManager, _has_sr, _has_pyaudio

            

            # Voice system microphone

            if _has_sr:

                device = HostDevice(

                    id="voice_microphone",

                    name="Kingdom Voice Microphone",

                    category=DeviceCategory.AUDIO_INPUT,

                    status=DeviceStatus.CONNECTED,

                    capabilities={

                        "speech_recognition": True,

                        "pyaudio": _has_pyaudio

                    },

                    metadata={"source": "voice_manager"}

                )

                devices.append(device)

                logger.info("✅ Voice microphone detected via VoiceManager")

            

            # TTS output device

            device = HostDevice(

                id="voice_tts_output",

                name="Kingdom TTS Output (Black Panther Voice)",

                category=DeviceCategory.AUDIO_OUTPUT,

                status=DeviceStatus.CONNECTED,

                capabilities={

                    "tts": True,

                    "black_panther_voice": True

                },

                metadata={"source": "voice_manager"}

            )

            devices.append(device)

            

        except ImportError:

            logger.debug("VoiceManager not available")

        except Exception as e:

            logger.debug(f"Voice audio detection error: {e}")

        return devices

    

    @staticmethod

    def detect_wsl_audio_bridge() -> List[HostDevice]:

        """Detect WSL Audio Bridge status"""

        devices = []

        try:

            from core.wsl_audio_bridge import WSLAudioBridge

            bridge = WSLAudioBridge()

            

            if bridge.in_wsl:

                status = DeviceStatus.CONNECTED if bridge.pulse_configured else DeviceStatus.AVAILABLE

                device = HostDevice(

                    id="wsl_audio_bridge",

                    name="WSL-Windows Audio Bridge",

                    category=DeviceCategory.AUDIO_OUTPUT,

                    status=status,

                    capabilities={

                        "wsl": True,

                        "pulse_server": bridge.pulse_server,

                        "windows_host_ip": bridge.windows_host_ip

                    },

                    metadata={"source": "wsl_audio_bridge"}

                )

                devices.append(device)

                logger.info(f"✅ WSL Audio Bridge detected: {status.value}")

        except ImportError:

            logger.debug("WSL Audio Bridge not available")

        except Exception as e:

            logger.debug(f"WSL Audio Bridge detection error: {e}")

        return devices

# DEVICE DETECTORS - Platform-specific detection

# ============================================================================



class WindowsDeviceDetector:

    """Windows-specific device detection using WMI and PowerShell"""

    

    @staticmethod

    def detect_usb_devices() -> List[HostDevice]:

        """Detect USB devices via WMI"""

        devices = []

        try:

            # Use PowerShell to query WMI for USB devices

            cmd = '''

            Get-WmiObject Win32_USBHub | Select-Object DeviceID, Description, Name, Status | ConvertTo-Json

            '''

            result = _run_powershell(cmd, timeout=10)

            if result.returncode == 0 and result.stdout.strip():

                data = json.loads(result.stdout)

                if isinstance(data, dict):

                    data = [data]

                for item in data:

                    device = HostDevice(

                        id=f"usb_{item.get('DeviceID', 'unknown')}".replace("\\", "_"),

                        name=item.get('Name', 'USB Device'),

                        category=DeviceCategory.USB,

                        status=DeviceStatus.CONNECTED if item.get('Status') == 'OK' else DeviceStatus.ERROR,

                        product=item.get('Description', ''),

                        metadata={"raw": item}

                    )

                    devices.append(device)

        except Exception as e:

            logger.debug(f"USB detection error: {e}")

        return devices

    

    @staticmethod

    def detect_serial_ports() -> List[HostDevice]:

        """Detect serial/COM ports"""

        devices = []

        try:

            cmd = '''

            Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Name, Description, Status, PNPDeviceID | ConvertTo-Json

            '''

            result = _run_powershell(cmd, timeout=10)

            if result.returncode == 0 and result.stdout.strip():

                data = json.loads(result.stdout)

                if isinstance(data, dict):

                    data = [data]

                for item in data:

                    pnp_device_id = item.get('PNPDeviceID') or item.get('PnpDeviceID') or item.get('pnp_device_id') or ''

                    vid = 0

                    pid = 0

                    try:

                        if isinstance(pnp_device_id, str) and pnp_device_id:

                            vid_match = re.search(r"VID_([0-9A-Fa-f]{4})", pnp_device_id)

                            pid_match = re.search(r"PID_([0-9A-Fa-f]{4})", pnp_device_id)

                            if vid_match:

                                vid = int(vid_match.group(1), 16)

                            if pid_match:

                                pid = int(pid_match.group(1), 16)

                    except Exception:

                        vid = 0

                        pid = 0



                    capabilities = {}

                    if vid:

                        capabilities["vid"] = vid

                    if pid:

                        capabilities["pid"] = pid

                    if pnp_device_id:

                        capabilities["pnp_device_id"] = pnp_device_id



                    device = HostDevice(

                        id=f"serial_{item.get('DeviceID', 'unknown')}",

                        name=item.get('Name', 'Serial Port'),

                        category=DeviceCategory.SERIAL,

                        status=DeviceStatus.CONNECTED,

                        port=item.get('DeviceID', ''),

                        product=item.get('Description', ''),

                        capabilities=capabilities,

                        metadata={"raw": item}

                    )

                    if pnp_device_id:

                        device.metadata["pnp_device_id"] = pnp_device_id

                    if vid:

                        device.metadata["vid"] = vid

                    if pid:

                        device.metadata["pid"] = pid

                    devices.append(device)

        except Exception as e:

            logger.debug(f"Serial port detection error: {e}")

        

        # Also try pyserial if available

        try:

            from serial.tools import list_ports

            for port in list_ports.comports():

                existing = [d for d in devices if d.port == port.device]

                if not existing:

                    device = HostDevice(

                        id=f"serial_{port.device}",

                        name=port.description or port.device,

                        category=DeviceCategory.SERIAL,

                        status=DeviceStatus.CONNECTED,

                        port=port.device,

                        vendor=port.manufacturer or "",

                        serial=port.serial_number or "",

                        product=port.product or "",

                        capabilities={"vid": port.vid or 0, "pid": port.pid or 0},

                        metadata={"hwid": port.hwid, "vid": port.vid, "pid": port.pid}

                    )

                    devices.append(device)

        except ImportError:

            pass

        except Exception as e:

            logger.debug(f"pyserial detection error: {e}")

        

        return devices

    

    @staticmethod

    def detect_bluetooth_devices() -> List[HostDevice]:

        """Detect Bluetooth devices"""

        devices = []

        try:

            # Query paired Bluetooth devices

            cmd = '''

            Get-PnpDevice -Class Bluetooth | Select-Object InstanceId, FriendlyName, Status, Class | ConvertTo-Json

            '''

            result = _run_powershell(cmd, timeout=15)

            if result.returncode == 0 and result.stdout.strip():

                data = json.loads(result.stdout)

                if isinstance(data, dict):

                    data = [data]

                for item in data:

                    friendly_name = item.get('FriendlyName', 'Bluetooth Device')

                    status_str = item.get('Status', 'Unknown')

                    instance_id = item.get('InstanceId', '')

                    

                    if status_str == 'OK':

                        status = DeviceStatus.CONNECTED

                    elif status_str == 'Degraded':

                        status = DeviceStatus.PAIRED

                    else:

                        status = DeviceStatus.DISCONNECTED

                    

                    device = HostDevice(

                        id=f"bt_{item.get('InstanceId', 'unknown')}".replace("\\", "_"),

                        name=friendly_name,

                        category=DeviceCategory.BLUETOOTH,

                        status=status,

                        driver=item.get('Class', ''),

                        metadata={

                            "raw": item,

                            "instance_id": instance_id,

                            "pnp_status": status_str,

                        }

                    )

                    devices.append(device)

        except Exception as e:

            logger.debug(f"Bluetooth detection error: {e}")

        return devices



    @staticmethod

    def detect_bluetooth_nearby_unpaired() -> List[HostDevice]:

        devices: List[HostDevice] = []

        try:

            items = _detect_bluetooth_nearby_winrt(timeout=20)

            for item in items:

                is_paired = bool(item.get("is_paired"))

                if is_paired:

                    continue

                name = (item.get("name") or "Bluetooth Device").strip() or "Bluetooth Device"

                winrt_id = (item.get("id") or "").strip()

                addr = (item.get("address") or "").strip()

                devices.append(

                    HostDevice(

                        id=f"bt_winrt_{re.sub(r'[^a-zA-Z0-9_]+', '_', winrt_id)[:120]}" if winrt_id else f"bt_winrt_{re.sub(r'[^a-zA-Z0-9_]+', '_', name)[:80]}",

                        name=name,

                        category=DeviceCategory.BLUETOOTH,

                        status=DeviceStatus.AVAILABLE,

                        address=addr,

                        metadata={

                            "winrt_id": winrt_id,

                            "winrt_is_paired": False,

                            "winrt_is_connected": bool(item.get("is_connected")),

                            "source": "winrt_nearby",

                        },

                    )

                )

        except Exception as e:

            logger.debug(f"Bluetooth nearby detection error: {e}")

        return devices

    

    @staticmethod

    def detect_audio_devices() -> List[HostDevice]:

        """Detect audio input/output devices"""

        devices = []

        try:

            # Audio output devices (speakers, headphones)

            cmd = '''

            Get-WmiObject Win32_SoundDevice | Select-Object DeviceID, Name, Manufacturer, Status | ConvertTo-Json

            '''

            result = _run_powershell(cmd, timeout=10)

            if result.returncode == 0 and result.stdout.strip():

                data = json.loads(result.stdout)

                if isinstance(data, dict):

                    data = [data]

                for item in data:

                    device = HostDevice(

                        id=f"audio_{item.get('DeviceID', 'unknown')}".replace("\\", "_"),

                        name=item.get('Name', 'Audio Device'),

                        category=DeviceCategory.AUDIO_OUTPUT,

                        status=DeviceStatus.CONNECTED if item.get('Status') == 'OK' else DeviceStatus.ERROR,

                        vendor=item.get('Manufacturer', ''),

                        metadata={"raw": item}

                    )

                    devices.append(device)

        except Exception as e:

            logger.debug(f"Audio device detection error: {e}")

        

        # Try sounddevice for more detailed info (skip in WSL2 to avoid ALSA crashes)

        _in_wsl = False

        try:

            with open("/proc/version", "r") as f:

                _pv = f.read().lower()

                _in_wsl = "microsoft" in _pv or "wsl" in _pv

        except Exception:

            pass

        

        if _in_wsl:

            logger.debug("WSL2 detected - skipping sounddevice audio device enumeration to avoid ALSA crash")

            return devices

        

        try:

            sd_devices = _query_sounddevice_devices_subprocess(timeout=8)

            for idx, dev in enumerate(sd_devices):

                is_input = dev.get('max_input_channels', 0) > 0

                is_output = dev.get('max_output_channels', 0) > 0

                

                if is_input:

                    device = HostDevice(

                        id=f"audio_in_{idx}",

                        name=dev.get('name', f'Audio Input {idx}'),

                        category=DeviceCategory.AUDIO_INPUT,

                        status=DeviceStatus.CONNECTED,

                        capabilities={

                            "channels": dev.get('max_input_channels', 0),

                            "sample_rate": dev.get('default_samplerate')

                        },

                        metadata={"index": idx, "hostapi": dev.get('hostapi')}

                    )

                    devices.append(device)

                

                if is_output:

                    existing = [d for d in devices if d.name == dev.get('name') and d.category == DeviceCategory.AUDIO_OUTPUT]

                    if not existing:

                        device = HostDevice(

                            id=f"audio_out_{idx}",

                            name=dev.get('name', f'Audio Output {idx}'),

                            category=DeviceCategory.AUDIO_OUTPUT,

                            status=DeviceStatus.CONNECTED,

                            capabilities={

                                "channels": dev.get('max_output_channels', 0),

                                "sample_rate": dev.get('default_samplerate')

                            },

                            metadata={"index": idx, "hostapi": dev.get('hostapi')}

                        )

                        devices.append(device)

        except Exception as e:

            logger.debug(f"sounddevice detection error: {e}")

        

        return devices

    

    @staticmethod

    def detect_webcams() -> List[HostDevice]:

        """Detect webcam/video capture devices"""

        devices = []

        try:

            # Query video capture devices

            cmd = '''

            Get-PnpDevice -Class Camera,Image | Select-Object InstanceId, FriendlyName, Status, Manufacturer | ConvertTo-Json

            '''

            result = _run_powershell(cmd, timeout=10)

            if result.returncode == 0 and result.stdout.strip():

                data = json.loads(result.stdout)

                if isinstance(data, dict):

                    data = [data]

                for item in data:

                    device = HostDevice(

                        id=f"cam_{item.get('InstanceId', 'unknown')}".replace("\\", "_"),

                        name=item.get('FriendlyName', 'Webcam'),

                        category=DeviceCategory.WEBCAM,

                        status=DeviceStatus.CONNECTED if item.get('Status') == 'OK' else DeviceStatus.ERROR,

                        vendor=item.get('Manufacturer', ''),

                        metadata={"raw": item}

                    )

                    devices.append(device)

        except Exception as e:

            logger.debug(f"Webcam detection error: {e}")

        

        # Try OpenCV for more detailed webcam info

        try:

            import cv2

            for idx in range(5):  # Check first 5 indices
                cap = None
                try:
                    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    
                    if cap.isOpened():
                        existing = [d for d in devices if f"cam_cv_{idx}" == d.id]
                        
                        if not existing:
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            
                            device = HostDevice(
                                id=f"cam_cv_{idx}",
                                name=f"Camera {idx}",
                                category=DeviceCategory.WEBCAM,
                                status=DeviceStatus.CONNECTED,
                                capabilities={
                                    "resolution": f"{width}x{height}",
                                    "fps": fps
                                },
                                metadata={"cv_index": idx}
                            )
                            devices.append(device)
                    else:
                        break
                except Exception as e:
                    logger.debug(f"Camera index {idx} check failed: {e}")
                finally:
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass

        except ImportError:

            pass

        except Exception as e:

            logger.debug(f"OpenCV webcam detection error: {e}")

        

        return devices

    

    @staticmethod

    def detect_vr_devices() -> List[HostDevice]:

        """Detect VR headsets via ADB (Quest) and OpenXR"""

        devices = []

        

        # Check for Quest devices via ADB

        try:

            result = subprocess.run(

                ["adb", "devices"],

                capture_output=True, text=True, timeout=5

            )

            if result.returncode == 0:

                lines = result.stdout.strip().split('\n')[1:]

                for line in lines:

                    if line.strip() and 'device' in line:

                        device_id = line.split('\t')[0]

                        # Get model name

                        model_result = subprocess.run(

                            ["adb", "-s", device_id, "shell", "getprop", "ro.product.model"],

                            capture_output=True, text=True, timeout=5

                        )

                        model = model_result.stdout.strip() if model_result.returncode == 0 else "Meta Quest"

                        

                        device = HostDevice(

                            id=f"vr_quest_{device_id}",

                            name=model,

                            category=DeviceCategory.VR_HEADSET,

                            status=DeviceStatus.CONNECTED,

                            serial=device_id,

                            vendor="Meta",

                            capabilities={

                                "hand_tracking": "Quest 3" in model,

                                "eye_tracking": "Quest Pro" in model or "Quest 3" in model,

                                "passthrough": True

                            },

                            metadata={"connection": "usb_link"}

                        )

                        devices.append(device)

        except FileNotFoundError:

            logger.debug("ADB not found - Quest detection skipped")

        except Exception as e:

            logger.debug(f"VR/ADB detection error: {e}")

        

        # Check Oculus registry for installed headsets

        try:

            import winreg

            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Oculus VR, LLC\Oculus", 0, winreg.KEY_READ)

            device = HostDevice(

                id="vr_oculus_installed",

                name="Oculus Runtime",

                category=DeviceCategory.VR_HEADSET,

                status=DeviceStatus.AVAILABLE,

                vendor="Meta/Oculus",

                metadata={"type": "runtime"}

            )

            devices.append(device)

            winreg.CloseKey(key)

        except (FileNotFoundError, OSError):

            pass

        

        return devices


class UnixDeviceDetector:
    """Cross-platform (Linux / macOS) device detection using /dev and system tools."""

    @staticmethod
    def detect_usb_devices() -> List[HostDevice]:
        devices = []
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["system_profiler", "SPUSBDataType", "-json"],
                    capture_output=True, text=True, timeout=10
                )
            else:
                result = subprocess.run(
                    ["lsusb"], capture_output=True, text=True, timeout=10
                )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    device = HostDevice(
                        device_id=f"usb_{hash(line) & 0xFFFFFF:06x}",
                        name=line.strip()[:80],
                        device_type="USB",
                        category=DeviceCategory.PERIPHERAL,
                        status="connected"
                    )
                    devices.append(device)
        except Exception as e:
            logger.debug(f"Unix USB detection error: {e}")
        return devices

    @staticmethod
    def detect_serial_ports() -> List[HostDevice]:
        import glob as _glob
        devices = []
        patterns = ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/tty.usbserial*", "/dev/tty.usbmodem*"]
        for pattern in patterns:
            for port in _glob.glob(pattern):
                device = HostDevice(
                    device_id=f"serial_{os.path.basename(port)}",
                    name=os.path.basename(port),
                    device_type="Serial",
                    category=DeviceCategory.PERIPHERAL,
                    status="connected",
                    metadata={"path": port}
                )
                devices.append(device)
        return devices

    @staticmethod
    def detect_bluetooth_devices() -> List[HostDevice]:
        devices = []
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    parts = line.split(maxsplit=2)
                    if len(parts) >= 3:
                        device = HostDevice(
                            device_id=f"bt_{parts[1].replace(':', '')}",
                            name=parts[2],
                            device_type="Bluetooth",
                            category=DeviceCategory.PERIPHERAL,
                            status="connected",
                            metadata={"mac": parts[1]}
                        )
                        devices.append(device)
        except Exception as e:
            logger.debug(f"Unix Bluetooth detection error: {e}")
        return devices

    @staticmethod
    def detect_bluetooth_nearby_unpaired() -> List[HostDevice]:
        return []

    @staticmethod
    def detect_audio_devices() -> List[HostDevice]:
        devices = []
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["system_profiler", "SPAudioDataType", "-json"],
                    capture_output=True, text=True, timeout=10
                )
            else:
                result = subprocess.run(
                    ["aplay", "-l"], capture_output=True, text=True, timeout=10
                )
            if result.returncode == 0:
                for i, line in enumerate(result.stdout.strip().splitlines()):
                    if line.strip():
                        device = HostDevice(
                            device_id=f"audio_{i}",
                            name=line.strip()[:80],
                            device_type="Audio",
                            category=DeviceCategory.PERIPHERAL,
                            status="connected"
                        )
                        devices.append(device)
        except Exception as e:
            logger.debug(f"Unix audio detection error: {e}")
        return devices

    @staticmethod
    def detect_webcams() -> List[HostDevice]:
        import glob as _glob
        devices = []
        for video_dev in sorted(_glob.glob("/dev/video*")):
            device = HostDevice(
                device_id=f"webcam_{os.path.basename(video_dev)}",
                name=os.path.basename(video_dev),
                device_type="Webcam",
                category=DeviceCategory.PERIPHERAL,
                status="connected",
                metadata={"path": video_dev}
            )
            devices.append(device)
        return devices

    @staticmethod
    def detect_vr_devices() -> List[HostDevice]:
        return []



# ============================================================================

# DEVICE TAKEOVER MANAGER - Auto-control of connected devices

# ============================================================================



class DeviceTakeoverManager:

    """

    SOTA 2026 Device Takeover Manager

    

    Automatically takes control of newly connected devices:

    - Hooks into device.connected events

    - Runs takeover asynchronously in background threads

    - Tracks devices to avoid repeated takeover attempts

    - Publishes takeover status events for GUI/AI visibility

    """

    

    def __init__(self, event_bus=None):

        self.event_bus = event_bus

        self._taken_over_devices: Dict[str, Dict[str, Any]] = {}  # device_id -> takeover_info

        self._takeover_in_progress: Set[str] = set()  # device_ids currently being taken over

        self._lock = threading.Lock()

        self._takeover_system = None

        self._windows_bridge = None

        

        # SOTA 2026: Universal Device Registry for identification

        self._device_registry = None

        try:

            from core.device_registry import get_device_registry

            self._device_registry = get_device_registry()

            logger.info("✅ Universal Device Registry integrated")

        except Exception as e:

            logger.warning(f"Device Registry not available: {e}")

        

        # SOTA 2026: Persistent Device Logbook

        self._device_logbook = None

        try:

            from core.device_logbook import get_device_logbook

            self._device_logbook = get_device_logbook()

            logger.info("✅ Persistent Device Logbook integrated")

        except Exception as e:

            logger.warning(f"Device Logbook not available: {e}")

        

        # Initialize takeover system

        self._init_takeover_system()

        

        logger.info("🎯 DeviceTakeoverManager initialized")

    

    def _init_takeover_system(self):

        """Initialize the device takeover system."""

        try:

            from core.device_takeover_system import DeviceTakeover

            self._takeover_system = DeviceTakeover()

            logger.info("✅ DeviceTakeover system loaded")

            

            # CRITICAL FIX: Initialize WindowsHostBridge for serial communication

            try:

                from core.windows_host_bridge import get_windows_host_bridge

                self._windows_bridge = get_windows_host_bridge()

                self._takeover_system.bridge = self._windows_bridge

                logger.info("✅ WindowsHostBridge connected to DeviceTakeover system")

            except Exception as bridge_err:

                logger.error(f"WindowsHostBridge init failed: {bridge_err}")

            

            # CRITICAL FIX: Subscribe to device.connected events for auto-takeover

            if self.event_bus:

                self.event_bus.subscribe('device.connected', self._on_device_connected)

                logger.info("✅ DeviceTakeoverManager subscribed to device.connected events")

            

        except ImportError as e:

            logger.warning(f"DeviceTakeover system not available: {e}")

        except Exception as e:

            logger.error(f"DeviceTakeover init error: {e}")

    

    def _on_device_connected(self, event_data):

        """Handle device.connected events and trigger auto-takeover."""

        try:

            device_dict = event_data.get('device', {})

            if not device_dict:

                return

            

            # Reconstruct HostDevice from dict

            device = HostDevice.from_dict(device_dict)

            

            # SOTA 2026: Enhance device identification using registry

            if self._device_registry:

                vid = device.capabilities.get("vid", 0) or device.metadata.get("vid", 0)

                pid = device.capabilities.get("pid", 0) or device.metadata.get("pid", 0)

                

                if vid and pid:

                    identity = self._device_registry.identify_usb_device(vid, pid)

                    if identity.confidence > 0.5:

                        logger.info(f"🔍 Device identified: {identity.vendor_name} {identity.product_name} (confidence: {identity.confidence:.2f})")

                        # Enhance device info with registry data

                        if identity.vendor_name and not device.vendor:

                            device.vendor = identity.vendor_name

                        if identity.product_name and not device.product:

                            device.product = identity.product_name

            

            # SOTA 2026: Log device connection

            if self._device_logbook:

                from core.device_logbook import DeviceLogEntry, DeviceEventType

                entry = DeviceLogEntry(

                    timestamp=time.time(),

                    event_type=DeviceEventType.CONNECTED.value,

                    device_id=device.id,

                    device_name=device.name,

                    device_category=device.category.value,

                    port=device.port,

                    vid=device.capabilities.get("vid", 0) or device.metadata.get("vid", 0),

                    pid=device.capabilities.get("pid", 0) or device.metadata.get("pid", 0),

                    vendor=device.vendor,

                    product=device.product,

                    serial=device.serial,

                    success=True

                )

                self._device_logbook.log_event(entry)

            

            # Trigger auto-takeover

            logger.info(f"📡 Device connected event received: {device.name}")

            self.auto_takeover_device(device)

            

        except Exception as e:

            logger.error(f"Error handling device.connected event: {e}")

    

    def set_windows_bridge(self, bridge):

        """Set the Windows host bridge for serial communication."""

        self._windows_bridge = bridge

        if self._takeover_system:

            self._takeover_system.bridge = bridge

    

    def is_device_taken_over(self, device_id: str) -> bool:

        """Check if a device has already been taken over."""

        with self._lock:

            return device_id in self._taken_over_devices

    

    def is_takeover_in_progress(self, device_id: str) -> bool:

        """Check if takeover is currently in progress for a device."""

        with self._lock:

            return device_id in self._takeover_in_progress

    

    def get_takeover_info(self, device_id: str) -> Optional[Dict[str, Any]]:

        """Get takeover information for a device."""

        with self._lock:

            return self._taken_over_devices.get(device_id)

    

    def list_taken_over_devices(self) -> Dict[str, Dict[str, Any]]:

        """List all devices that have been taken over.

        

        Returns:

            Dict mapping device_id to takeover info

        """

        with self._lock:

            return self._taken_over_devices.copy()

    

    def auto_takeover_device(self, device: HostDevice) -> bool:

        """

        Automatically take over a newly connected device.

        Runs asynchronously in a background thread.

        

        Args:

            device: The HostDevice to take over

            

        Returns:

            True if takeover was initiated, False if skipped

        """

        # Check if device is suitable for takeover

        if not self._should_takeover_device(device):

            return False

        

        # Check if already taken over or in progress

        with self._lock:

            if device.id in self._taken_over_devices:

                logger.debug(f"Device {device.name} already taken over, skipping")

                return False

            if device.id in self._takeover_in_progress:

                logger.debug(f"Takeover already in progress for {device.name}")

                return False

            self._takeover_in_progress.add(device.id)

        

        # Publish takeover started event

        self._publish_takeover_event("device.takeover.started", device, {

            "status": "started",

            "message": f"Initiating takeover of {device.name}"

        })

        

        # Log takeover start

        if self._device_logbook:

            from core.device_logbook import DeviceLogEntry, DeviceEventType

            entry = DeviceLogEntry(

                timestamp=time.time(),

                event_type=DeviceEventType.TAKEOVER_STARTED.value,

                device_id=device.id,

                device_name=device.name,

                device_category=device.category.value,

                port=device.port,

                vid=device.capabilities.get("vid", 0) or device.metadata.get("vid", 0),

                pid=device.capabilities.get("pid", 0) or device.metadata.get("pid", 0),

                vendor=device.vendor,

                product=device.product,

                serial=device.serial,

                success=True

            )

            self._device_logbook.log_event(entry)

        

        # Run takeover in background thread

        thread = threading.Thread(

            target=self._takeover_worker,

            args=(device,),

            daemon=True,

            name=f"Takeover-{device.id[:20]}"

        )

        thread.start()

        

        logger.info(f"🎯 Initiated takeover of {device.name}")

        return True

    

    def _should_takeover_device(self, device: HostDevice) -> bool:

        """Determine if a device should be automatically taken over.

        

        CRITICAL: Only takeover devices with proper identification.

        DO NOT attempt takeover on generic COM ports without VID/PID.

        """

        # ONLY takeover microcontroller categories (not generic SERIAL)

        takeover_categories = {

            DeviceCategory.ARDUINO,

            DeviceCategory.ESP32,

            DeviceCategory.STM32,

            DeviceCategory.TEENSY,

            DeviceCategory.PICO,

        }

        

        if device.category in takeover_categories:

            return True

        

        # For SERIAL category, require VID/PID identification

        if device.category == DeviceCategory.SERIAL:

            vid = device.capabilities.get("vid", 0) or device.metadata.get("vid", 0)

            pid = device.capabilities.get("pid", 0) or device.metadata.get("pid", 0)

            

            # CRITICAL: Ignore COM1 (system port)

            if device.port and "COM1" in device.port.upper():

                logger.debug(f"Skipping takeover of system port: {device.port}")

                return False

            

            # Only takeover if we have valid VID/PID

            if vid and pid:

                # Check if it's a known takeover-capable device

                from core.device_takeover_system import KNOWN_DEVICES

                if (vid, pid) in KNOWN_DEVICES:

                    return True

                

                # Check if it's a Particle device (VID 0x2B04)

                if vid == 0x2B04:

                    return True

            

            logger.debug(f"Skipping takeover of unidentified serial device: {device.name} (VID={vid:04X}, PID={pid:04X})")

            return False

        

        return False

    

    def _send_led_indicator(self, device: HostDevice, rgb: str, event_prefix: str) -> bool:

        """Send LED indicator with fallback commands for firmware compatibility.

        

        Args:

            device: Target device

            rgb: RGB values as "R,G,B" string (e.g., "255,0,0" for red)

            event_prefix: Event status prefix (e.g., "takeover_indicator")

        

        Returns:

            True if any LED command succeeded

        """

        if not self._takeover_system:

            return False

        

        # Try multiple LED command formats for compatibility

        led_commands = [

            f"RGB_BLINK:{rgb}",      # Kingdom firmware format

            f"RGB:{rgb}",            # Static RGB set

            f"LED_BLINK",            # Basic D7 blink

        ]

        

        self._publish_takeover_event("device.takeover.progress", device, {

            "status": event_prefix,

            "message": f"Attempting LED indicator ({led_commands[0]})...",

        })

        

        for cmd in led_commands:

            try:

                result = self._takeover_system._send_raw(cmd)

                if isinstance(result, dict) and result.get("success"):

                    resp = (result.get("response") or "").upper()

                    # Check for positive response (OK, ACK, or echo of command)

                    if "OK" in resp or "ACK" in resp or cmd.split(":")[0] in resp:

                        self._publish_takeover_event("device.takeover.progress", device, {

                            "status": f"{event_prefix}_ok",

                            "message": f"LED indicator sent ({cmd}).",

                        })

                        return True

            except Exception as e:

                logger.debug(f"LED command {cmd} failed: {e}")

        

        self._publish_takeover_event("device.takeover.progress", device, {

            "status": f"{event_prefix}_failed",

            "message": "LED indicator not confirmed (firmware may not support RGB commands).",

        })

        return False

    

    def _takeover_worker(self, device: HostDevice):

        """Background worker that performs the actual device takeover."""

        try:

            if not self._takeover_system:

                raise RuntimeError("Takeover system not initialized")

            

            device_metadata = getattr(device, "metadata", None) or {}

            vid = device.capabilities.get("vid") or device_metadata.get("vid") or 0

            pid = device.capabilities.get("pid") or device_metadata.get("pid") or 0

            device_name = device.name or ""

            lower_name = device_name.lower()



            device_type = device.category.value

            if vid == 0x2B04 or any(k in lower_name for k in ["particle", "photon", "argon", "boron"]):

                device_type = "particle"



            # Build device info dict for takeover system

            device_info = {

                "port": device.port,

                "name": device_name,

                "type": device_type,

                "vid": vid,

                "pid": pid,

                "baud": device.capabilities.get("baud_rate", 115200)

            }



            dfu_attempted = False

            

            # Attempt connection

            self._publish_takeover_event("device.takeover.progress", device, {

                "status": "connecting",

                "message": f"Connecting to {device.name} on {device.port}..."

            })

            

            connected = self._takeover_system.connect_device(device_info)



            if (not connected) and device_info.get("type") == "particle" and not dfu_attempted:

                dfu_attempted = True

                self._publish_takeover_event("device.takeover.progress", device, {

                    "status": "particle_unresponsive",

                    "message": "Particle did not respond over serial - initiating full DFU takeover (compile + flash)..."

                })



                dfu_result = self.full_particle_dfu_takeover()

                if not dfu_result.get("success"):

                    raise RuntimeError(dfu_result.get("error") or "Particle DFU takeover failed")



                time.sleep(2.0)

                try:

                    devices = self._takeover_system.find_all_devices()

                    for d in devices:

                        dtype = (d.get("type") or "").lower()

                        dname = (d.get("name") or "").lower()

                        if "particle" in dtype or "particle" in dname:

                            if d.get("port"):

                                device_info["port"] = d.get("port")

                                port_val = device_info["port"]

                                if port_val:

                                    device.port = port_val

                            if d.get("vid"):

                                device_info["vid"] = d.get("vid")

                            if d.get("pid"):

                                device_info["pid"] = d.get("pid")

                            if d.get("baud"):

                                device_info["baud"] = d.get("baud")

                            break

                except Exception as e:

                    logger.debug(f"Post-DFU device rescan failed: {e}")



                connected = self._takeover_system.connect_device(device_info)

            

            if connected:

                particle_listening_mode = bool(getattr(self._takeover_system, "is_particle_listening", False))

                wifi_ssid = ""

                firmware_ready = False

                wifi_configured = False



                if device_info.get("type") == "particle":

                    self._publish_takeover_event("device.takeover.progress", device, {

                        "status": "particle_detected",

                        "message": f"Particle detected on {device.port} - checking listening mode..."

                    })



                    try:

                        probe = self._takeover_system._send_raw("i")

                        probe_resp = (probe.get("response") or "").strip()

                        probe_lower = probe_resp.lower()

                        probe_upper = probe_resp.upper()

                        firmware_markers = ("INFO:", "READY", "KINGDOM", "CMD:", "OK:")

                        setup_markers = (

                            "device id",

                            "your device id",

                            "security cipher",

                            "ssid",

                            "security",

                            "password",

                            "listening mode",

                        )



                        if probe_resp and any(m in probe_upper for m in firmware_markers):

                            firmware_ready = True

                            particle_listening_mode = False

                        elif probe_resp and any(m in probe_lower for m in setup_markers) and "info:" not in probe_lower:

                            particle_listening_mode = True

                    except Exception as e:

                        logger.debug(f"Particle listening probe failed: {e}")



                    if firmware_ready and not particle_listening_mode:

                        self._publish_takeover_event("device.takeover.progress", device, {

                            "status": "firmware_ready",

                            "message": "Firmware responding - full control available."

                        })

                        # Send initial takeover indicator (red blink) now that firmware is ready

                        self._send_led_indicator(device, "255,0,0", "takeover_indicator")



                    if particle_listening_mode:

                        self._publish_takeover_event("device.takeover.progress", device, {

                            "status": "particle_listening",

                            "message": "Particle is in LISTENING MODE (blue) - preparing to exit listening mode..."

                        })



                        auto_wifi_enabled = str(os.environ.get("KINGDOM_PARTICLE_AUTO_WIFI", "")).strip().lower() in ("1", "true", "yes", "on")



                        wifi_config = None

                        if auto_wifi_enabled:

                            try:

                                from auto_device_control import load_wifi_config

                                wifi_config = load_wifi_config()

                            except Exception as e:

                                logger.debug(f"Auto WiFi config load failed: {e}")

                        else:

                            self._publish_takeover_event("device.takeover.progress", device, {

                                "status": "wifi_skipped",

                                "message": "WiFi auto-configuration disabled - no credentials required."

                            })



                        if wifi_config and wifi_config.get("ssid") and wifi_config.get("password"):

                            wifi_ssid = str(wifi_config.get("ssid"))

                            wifi_password = str(wifi_config.get("password"))

                            wifi_security = str(wifi_config.get("security") or "wpa2")



                            self._publish_takeover_event("device.takeover.progress", device, {

                                "status": "wifi_configuring",

                                "message": f"Sending WiFi credentials for '{wifi_ssid}'..."

                            })



                            try:

                                wifi_configured = bool(self._takeover_system.configure_wifi(wifi_ssid, wifi_password, wifi_security))

                            except Exception as e:

                                logger.debug(f"WiFi configure failed: {e}")

                                wifi_configured = False



                            if wifi_configured:

                                self._publish_takeover_event("device.takeover.progress", device, {

                                    "status": "wifi_configured",

                                    "message": f"WiFi credentials sent for '{wifi_ssid}' - exiting listening mode..."

                                })

                            else:

                                self._publish_takeover_event("device.takeover.progress", device, {

                                    "status": "wifi_failed",

                                    "message": "Auto WiFi configuration failed (no confirmation from device)."

                                })

                        else:

                            if auto_wifi_enabled:

                                self._publish_takeover_event("device.takeover.progress", device, {

                                    "status": "wifi_missing",

                                    "message": "Particle is in listening mode but no WiFi credentials were found automatically."

                                })



                        self._publish_takeover_event("device.takeover.progress", device, {

                            "status": "exiting_listening",

                            "message": "Exiting listening mode to start firmware..."

                        })



                        try:

                            self._takeover_system.exit_listening_mode()

                        except Exception:

                            pass



                        time.sleep(2.0)

                        for _ in range(4):

                            try:

                                fw_probe = self._takeover_system._send_raw("INFO")

                                fw_resp = (fw_probe.get("response") or "")

                                fw_lower = fw_resp.lower()

                                fw_upper = fw_resp.upper()

                                if fw_resp and ("security cipher" in fw_lower or "device id" in fw_lower or "ssid" in fw_lower or "password" in fw_lower or "listening mode" in fw_lower):

                                    try:

                                        self._takeover_system.exit_listening_mode()

                                    except Exception:

                                        pass

                                    time.sleep(0.5)

                                    continue

                                if fw_resp and ("INFO:" in fw_upper or "READY" in fw_upper or "KINGDOM" in fw_upper or "CMD:" in fw_upper):

                                    firmware_ready = True

                                    break

                            except Exception:

                                pass

                            time.sleep(0.5)



                        if firmware_ready:

                            self._publish_takeover_event("device.takeover.progress", device, {

                                "status": "firmware_ready",

                                "message": "Firmware responding - full control available."

                            })

                            # Send initial takeover indicator (red) now that firmware is ready

                            self._send_led_indicator(device, "255,0,0", "takeover_indicator")

                        else:

                            self._publish_takeover_event("device.takeover.progress", device, {

                                "status": "firmware_not_ready",

                                "message": "Firmware not responding yet. Try again in a few seconds."

                            })



                    if (not firmware_ready) and (not dfu_attempted):

                        dfu_attempted = True

                        self._publish_takeover_event("device.takeover.progress", device, {

                            "status": "dfu_takeover_starting",

                            "message": "Firmware not responding - initiating full DFU takeover (compile + flash)..."

                        })



                        dfu_result = self.full_particle_dfu_takeover()

                        if not dfu_result.get("success"):

                            raise RuntimeError(dfu_result.get("error") or "Particle DFU takeover failed")



                        time.sleep(2.0)

                        try:

                            devices = self._takeover_system.find_all_devices()

                            for d in devices:

                                dtype = (d.get("type") or "").lower()

                                dname = (d.get("name") or "").lower()

                                if "particle" in dtype or "particle" in dname:

                                    if d.get("port"):

                                        port_val = d.get("port")

                                        device_info["port"] = port_val

                                        if port_val:

                                            device.port = port_val

                                    if d.get("vid"):

                                        device_info["vid"] = d.get("vid")

                                    if d.get("pid"):

                                        device_info["pid"] = d.get("pid")

                                    if d.get("baud"):

                                        device_info["baud"] = d.get("baud")

                                    break

                        except Exception as e:

                            logger.debug(f"Post-DFU device rescan failed: {e}")



                        if not self._takeover_system.connect_device(device_info):

                            raise RuntimeError("Device did not reconnect after DFU flash")



                        time.sleep(1.5)

                        try:

                            probe = self._takeover_system._send_raw("i")

                            probe_resp = (probe.get("response") or "").strip()

                            probe_lower = probe_resp.lower()

                            probe_upper = probe_resp.upper()

                            firmware_markers = ("INFO:", "READY", "KINGDOM", "CMD:", "OK:")

                            setup_markers = (

                                "device id",

                                "your device id",

                                "security cipher",

                                "ssid",

                                "security",

                                "password",

                                "listening mode",

                            )

                            if probe_resp and any(m in probe_upper for m in firmware_markers):

                                firmware_ready = True

                                particle_listening_mode = False

                            elif probe_resp and any(m in probe_lower for m in setup_markers) and "info:" not in probe_lower:

                                particle_listening_mode = True

                                firmware_ready = False

                        except Exception as e:

                            logger.debug(f"Post-DFU firmware probe failed: {e}")



                        if firmware_ready:

                            self._publish_takeover_event("device.takeover.progress", device, {

                                "status": "firmware_ready",

                                "message": "Firmware responding after DFU flash - full control available."

                            })

                            self._send_led_indicator(device, "255,0,0", "takeover_indicator")

                        else:

                            raise RuntimeError("Firmware still not responding after DFU flash")



                # Discover device capabilities

                self._publish_takeover_event("device.takeover.progress", device, {

                    "status": "discovering",

                    "message": f"Discovering capabilities of {device.name}..."

                })

                

                capabilities = self._takeover_system.discover_capabilities()



                if isinstance(capabilities, dict):

                    capabilities.setdefault("device_type", device_info.get("type", ""))

                    capabilities.setdefault("vid", device_info.get("vid", 0))

                    capabilities.setdefault("pid", device_info.get("pid", 0))

                    capabilities.setdefault("baud_rate", device_info.get("baud", 115200))

                    capabilities.setdefault("particle_listening_mode", particle_listening_mode)

                    capabilities.setdefault("firmware_ready", firmware_ready)

                    if wifi_ssid:

                        capabilities.setdefault("wifi_ssid", wifi_ssid)

                

                # Record successful takeover

                takeover_info = {

                    "device_id": device.id,

                    "device_name": device.name,

                    "port": device.port,

                    "connected": True,

                    "capabilities": capabilities,

                    "learned_commands": self._takeover_system.learned_commands.copy(),

                    "timestamp": datetime.now().isoformat(),

                    "in_control": True,

                    "particle_listening_mode": particle_listening_mode,

                    "wifi_ssid": wifi_ssid,

                    "wifi_configured": wifi_configured,

                    "firmware_ready": firmware_ready,

                }

                

                with self._lock:

                    self._taken_over_devices[device.id] = takeover_info

                    self._takeover_in_progress.discard(device.id)



                if device_info.get("type") == "particle" and firmware_ready:

                    # Send green LED indicator to confirm full control

                    self._send_led_indicator(device, "0,255,0", "takeover_indicator_confirm")

                

                complete_message = f"✅ FULL CONTROL of {device.name} acquired!"

                if device_info.get("type") == "particle" and particle_listening_mode and not firmware_ready:

                    complete_message = f"⚠️ Connected to {device.name} but it is still in LISTENING MODE"



                # Publish success event

                self._publish_takeover_event("device.takeover.complete", device, {

                    "status": "complete",

                    "success": True,

                    "message": complete_message,

                    "capabilities": capabilities,

                    "commands": list(self._takeover_system.learned_commands.keys())

                })

                

                logger.info(f"✅ Takeover complete: {device.name} - FULL CONTROL")

            else:

                raise RuntimeError(f"Could not connect to {device.name}")

                

        except Exception as e:

            logger.error(f"Takeover failed for {device.name}: {e}")

            

            with self._lock:

                self._takeover_in_progress.discard(device.id)

            

            self._publish_takeover_event("device.takeover.failed", device, {

                "status": "failed",

                "success": False,

                "message": f"❌ Takeover failed: {str(e)}",

                "error": str(e)

            })

    

    def send_device_command(self, device_id: str, command: str) -> Dict[str, Any]:

        """Send a command to a taken-over device using DeviceBrainController + WindowsHostBridge."""

        with self._lock:

            if not device_id and self._taken_over_devices:

                device_id = next(iter(self._taken_over_devices.keys()))

            

            if device_id not in self._taken_over_devices:

                return {"success": False, "error": f"Device {device_id} not taken over", "command": command}

            

            takeover_info = self._taken_over_devices[device_id]

        

        port = takeover_info.get("port", "")

        baud = takeover_info.get("capabilities", {}).get("baud_rate", 115200)

        if isinstance(baud, dict):

            baud = 115200

        try:

            baud = int(baud) if baud else 115200

        except Exception:

            baud = 115200

        

        try:

            from core.device_framework_manager import get_device_framework_manager

            framework_mgr = get_device_framework_manager(self.event_bus)

            framework_mgr.ensure_frameworks_for_device(takeover_info)

        except Exception as e:

            logger.debug(f"Framework check skipped: {e}")

        

        try:

            from core.device_brain_controller import get_device_brain, setup_device_brain

            from core.windows_host_bridge import get_windows_host_bridge

            

            bridge = get_windows_host_bridge()

            brain = get_device_brain()

            

            if brain is None:

                try:

                    from core.thoth_ollama_connector import get_ollama_connector

                    import asyncio

                    loop = asyncio.new_event_loop()

                    asyncio.set_event_loop(loop)

                    try:

                        ollama = loop.run_until_complete(get_ollama_connector(self.event_bus))

                        brain = setup_device_brain(ollama, bridge)

                    finally:

                        loop.close()

                except Exception as e:

                    logger.debug(f"Could not setup brain with Ollama: {e}")

            

            if brain and port:

                if not brain.device_port or brain.device_port != port:

                    brain.connect_device(port, baud, takeover_info)

                

                result = brain.process_sync(command)

                success = bool(result.get("success", False))

                response_text = ""

                combined_raw = result.get("combined_response")

                if isinstance(combined_raw, str):

                    combined_s = combined_raw.strip()

                    if combined_s and combined_s != "(no response)":

                        response_text = combined_s



                if not response_text:

                    response_raw = result.get("response")

                    if isinstance(response_raw, str):

                        response_text = response_raw.strip()



                if not response_text:

                    responses_raw = result.get("responses")

                    if isinstance(responses_raw, list):

                        parts = [r.strip() for r in responses_raw if isinstance(r, str) and r.strip()]

                        if parts:

                            response_text = "\n".join(parts)



                error_raw = result.get("error")

                error_text = error_raw.strip() if isinstance(error_raw, str) else ""



                if success and command.strip() and not response_text:

                    success = False

                    if not error_text:

                        error_text = "No response (check COM port / baud / listening mode)"

                elif not success and command.strip() and not response_text and not error_text:

                    error_text = "Command failed (check COM port / baud / listening mode)"

                message = response_text or error_text or "Command sent via brain"

                return {

                    "success": success,

                    "result": result,

                    "command": command,

                    "device_id": device_id,

                    "port": port,

                    "message": message,

                    "response": response_text,

                    "error": error_text,

                }

        except Exception as e:

            logger.debug(f"Brain command path failed, falling back: {e}")

        

        if not self._takeover_system:

            return {"success": False, "error": "Takeover system not initialized", "command": command, "device_id": device_id, "port": port}



        if not self._takeover_system.in_control:

            return {"success": False, "error": "Takeover system not in control", "command": command, "device_id": device_id, "port": port}

        

        try:

            if port and getattr(self._takeover_system, "port", None) != port:

                device_info = {

                    "port": port,

                    "name": takeover_info.get("device_name", ""),

                    "type": takeover_info.get("capabilities", {}).get("device_type", takeover_info.get("capabilities", {}).get("type", "")),

                    "vid": takeover_info.get("capabilities", {}).get("vid", 0),

                    "pid": takeover_info.get("capabilities", {}).get("pid", 0),

                    "baud": baud,

                }

                connected = self._takeover_system.connect_device(device_info)

                if not connected:

                    return {

                        "success": False,

                        "error": "Takeover system could not connect to device port",

                        "command": command,

                        "device_id": device_id,

                        "port": port,

                    }



            result = self._takeover_system.execute_command(command)

            success = result.get("success", False) if isinstance(result, dict) else bool(result)

            response = result.get("response", "") if isinstance(result, dict) else ""

            error = result.get("error", "") if isinstance(result, dict) else ""



            response_s = response.strip() if isinstance(response, str) else ""

            error_s = error.strip() if isinstance(error, str) else ""

            if success and command.strip() and not response_s:

                success = False

                if not error_s:

                    error_s = "No response (check COM port / baud / listening mode)"



            payload = {

                "success": success,

                "result": result,

                "command": command,

                "device_id": device_id,

                "port": port,

                "message": response_s or (error_s if not success else "Command executed via takeover system"),

            }



            if isinstance(result, dict):

                if "response" in result:

                    payload["response"] = response_s

                if error_s:

                    payload["error"] = error_s

            return payload

        except Exception as e:

            return {"success": False, "error": str(e), "command": command, "device_id": device_id, "port": port}

    

    def configure_device_wifi(self, device_id: str, ssid: str, password: str, security: str = "wpa2") -> Dict[str, Any]:

        """Configure WiFi on a taken-over device (e.g., Particle in listening mode)."""

        with self._lock:

            if device_id not in self._taken_over_devices:

                return {"success": False, "error": f"Device {device_id} not taken over"}

        

        if not self._takeover_system:

            return {"success": False, "error": "Takeover system not initialized"}

        

        try:

            result = self._takeover_system.configure_wifi(ssid, password, security)

            return {"success": result, "ssid": ssid, "message": f"WiFi configured for {ssid}"}

        except Exception as e:

            return {"success": False, "error": str(e)}

    

    def get_all_taken_over_devices(self) -> List[Dict[str, Any]]:

        """Get list of all devices currently under control."""

        with self._lock:

            return list(self._taken_over_devices.values())

    

    def release_device(self, device_id: str) -> bool:

        """Release control of a device."""

        with self._lock:

            if device_id in self._taken_over_devices:

                del self._taken_over_devices[device_id]

                logger.info(f"🔓 Released control of device: {device_id}")

                return True

        return False

    

    def _publish_takeover_event(self, event_type: str, device: HostDevice, data: Dict[str, Any]):

        """Publish a takeover event to the event bus."""

        if self.event_bus:

            try:

                payload = {

                    "event": event_type,

                    "device_id": device.id,

                    "device_name": device.name,

                    "device_port": device.port,

                    "timestamp": datetime.now().isoformat(),

                    **data

                }

                

                if hasattr(self.event_bus, 'publish_sync'):

                    self.event_bus.publish_sync(event_type, payload)

                elif hasattr(self.event_bus, 'publish'):

                    self.event_bus.publish(event_type, payload)

                

                # Publish to ai.response (UnifiedAIRouter will deduplicate → ai.response.unified)

                if hasattr(self.event_bus, 'publish'):

                    self.event_bus.publish('ai.response', {

                        'request_id': f"device_{device.id}_{int(time.time()*1000)}",

                        'response': data.get('message', ''),

                        'sender': 'device_takeover',

                        'device_id': device.id,

                        'timestamp': datetime.now().isoformat()

                    })

                    

                logger.debug(f"📡 Published {event_type}: {device.name}")

            except Exception as e:

                logger.debug(f"Takeover event publish error: {e}")

    

    def full_particle_dfu_takeover(self, firmware_path: str = None) -> Dict[str, Any]:

        """

        Complete automatic Particle DFU takeover with detailed event publishing.

        

        Steps:

        1. Detect device (DFU mode or normal)

        2. Trigger DFU mode if needed (14400 baud touch)

        3. Flash firmware via dfu-util

        4. Verify firmware operation

        

        Args:

            firmware_path: Optional path to firmware binary

            

        Returns:

            Dict with success status and details

        """

        if not self._takeover_system:

            return {"success": False, "error": "Takeover system not initialized"}

        

        # Create a virtual HostDevice for event publishing

        virtual_device = HostDevice(

            id="particle_dfu_takeover",

            name="Particle DFU Takeover",

            category=DeviceCategory.SERIAL,

            status=DeviceStatus.CONNECTED

        )

        

        self._publish_takeover_event("device.takeover.dfu.started", virtual_device, {

            "status": "dfu_started",

            "message": "🎯 Starting full Particle DFU takeover..."

        })

        

        try:

            # Step 1: Detect DFU devices

            self._publish_takeover_event("device.takeover.dfu.progress", virtual_device, {

                "status": "dfu_detecting",

                "step": 1,

                "message": "📍 STEP 1: Checking for devices in DFU mode..."

            })

            

            dfu_devices = self._takeover_system.detect_dfu_devices()

            

            if dfu_devices:

                device = dfu_devices[0]

                platform_id = device.get('platform_id', 12)

                virtual_device.name = device.get('name', 'Particle DFU')

                

                self._publish_takeover_event("device.takeover.dfu.progress", virtual_device, {

                    "status": "dfu_detected",

                    "step": 1,

                    "message": f"✅ Device already in DFU mode: {device.get('name')}"

                })

            else:

                # Find normal Particle device

                self._publish_takeover_event("device.takeover.dfu.progress", virtual_device, {

                    "status": "scanning_serial",

                    "step": 1,

                    "message": "🔍 No DFU device found, scanning for normal Particle devices..."

                })

                

                devices = self._takeover_system.find_all_devices()

                particle_dev = None

                

                for d in devices:

                    dtype = d.get('type', '').lower()

                    dname = d.get('name', '').lower()

                    if 'particle' in dtype or 'particle' in dname:

                        particle_dev = d

                        break

                

                if not particle_dev:

                    self._publish_takeover_event("device.takeover.dfu.failed", virtual_device, {

                        "status": "no_device",

                        "message": "❌ No Particle device found. Ensure device is plugged in."

                    })

                    return {"success": False, "error": "No Particle device found"}

                

                virtual_device.name = particle_dev.get('name', 'Particle')

                virtual_device.port = particle_dev.get('port', '')

                

                self._publish_takeover_event("device.takeover.dfu.progress", virtual_device, {

                    "status": "device_found",

                    "step": 1,

                    "message": f"✅ Found: {particle_dev.get('name')} on {particle_dev.get('port')}"

                })

                

                # Get platform ID

                pid = particle_dev.get('pid', 0)

                pid_hex = f"{pid:04X}" if pid else ""

                from core.device_takeover_system import PARTICLE_NORMAL_PIDS

                platform_id = PARTICLE_NORMAL_PIDS.get(pid_hex, {}).get('platform_id', 12)

                

                # Step 2: Trigger DFU mode

                self._publish_takeover_event("device.takeover.dfu.progress", virtual_device, {

                    "status": "dfu_triggering",

                    "step": 2,

                    "message": f"📍 STEP 2: Triggering DFU mode on {particle_dev.get('port')}..."

                })

                

                port = particle_dev.get('port')

                if not port:

                    self._publish_takeover_event("device.takeover.dfu.failed", virtual_device, {

                        "status": "no_port",

                        "message": "❌ No COM port available for DFU trigger"

                    })

                    return {"success": False, "error": "No COM port available"}

                

                if not self._takeover_system.trigger_dfu_mode(port):

                    self._publish_takeover_event("device.takeover.dfu.failed", virtual_device, {

                        "status": "dfu_trigger_failed",

                        "message": "❌ Failed to enter DFU mode"

                    })

                    return {"success": False, "error": "Failed to enter DFU mode"}

                

                self._publish_takeover_event("device.takeover.dfu.progress", virtual_device, {

                    "status": "dfu_entered",

                    "step": 2,

                    "message": "✅ Device entered DFU mode successfully"

                })

            

            # Step 3: Flash firmware

            self._publish_takeover_event("device.takeover.dfu.progress", virtual_device, {

                "status": "flashing",

                "step": 3,

                "message": "📍 STEP 3: Flashing Kingdom AI firmware..."

            })

            

            if not self._takeover_system.flash_particle_firmware(platform_id, firmware_path):

                self._publish_takeover_event("device.takeover.dfu.failed", virtual_device, {

                    "status": "flash_failed",

                    "message": "❌ Firmware flash failed"

                })

                return {"success": False, "error": "Firmware flash failed"}

            

            self._publish_takeover_event("device.takeover.dfu.progress", virtual_device, {

                "status": "flash_complete",

                "step": 3,

                "message": "✅ Firmware flashed successfully"

            })

            

            # Step 4: Verify

            self._publish_takeover_event("device.takeover.dfu.progress", virtual_device, {

                "status": "verifying",

                "step": 4,

                "message": "📍 STEP 4: Verifying firmware operation..."

            })

            

            verified = self._takeover_system.verify_firmware()

            

            if verified:

                self._publish_takeover_event("device.takeover.dfu.complete", virtual_device, {

                    "status": "complete",

                    "success": True,

                    "message": "🎉 TAKEOVER COMPLETE! Device is running Kingdom AI firmware."

                })

                return {"success": True, "message": "Full DFU takeover complete", "verified": True}

            else:

                self._publish_takeover_event("device.takeover.dfu.complete", virtual_device, {

                    "status": "complete_unverified",

                    "success": True,

                    "message": "⚠️ Flash succeeded but verification pending. Device may need manual check."

                })

                return {"success": True, "message": "Flash complete, verification pending", "verified": False}

                

        except Exception as e:

            logger.error(f"DFU takeover error: {e}")

            self._publish_takeover_event("device.takeover.dfu.failed", virtual_device, {

                "status": "error",

                "message": f"❌ DFU takeover error: {str(e)}"

            })

            return {"success": False, "error": str(e)}





# Global takeover manager instance

_device_takeover_manager: Optional[DeviceTakeoverManager] = None



def get_device_takeover_manager(event_bus=None) -> DeviceTakeoverManager:

    """Get or create the global DeviceTakeoverManager instance."""

    global _device_takeover_manager

    if _device_takeover_manager is None:

        _device_takeover_manager = DeviceTakeoverManager(event_bus)

    return _device_takeover_manager





# ============================================================================

# HOST DEVICE MANAGER - Main service class

# ============================================================================



class HostDeviceManager:

    """

    Unified Host Device Manager for Kingdom AI

    

    Provides centralized device detection, monitoring, and control

    with event bus integration and MCP tool exposure.

    

    CRITICAL: Integrates with existing Kingdom AI systems:

    - VR: vr/vr_manager.py (VRManager)

    - Webcam: Generic MJPEG server (any brand)

    - Bluetooth: black_panther_bluetooth.py (BluetoothManager)

    - Voice: core/voice_manager.py (VoiceManager)

    - Audio Bridge: core/wsl_audio_bridge.py (WSLAudioBridge)

    """

    

    def __init__(self, event_bus=None):

        """Initialize the Host Device Manager.

        

        Args:

            event_bus: Optional event bus for publishing device events

        """

        self.event_bus = event_bus

        self.devices: Dict[str, HostDevice] = {}

        self._lock = threading.Lock()

        self._monitoring = False

        self._monitor_thread: Optional[threading.Thread] = None

        self._scan_interval = 5.0  # seconds

        self._callbacks: List[Callable[[str, HostDevice], None]] = []

        

        # Kingdom AI device integration

        self._kingdom_integration = KingdomDeviceIntegration()

        

        # SOTA 2026: Universal Data Visualizer for auto-display of device data

        self._visualizer = None

        if HAS_VISUALIZER:

            try:

                self._visualizer = get_universal_visualizer(event_bus)

                logger.info("🎨 UniversalDataVisualizer connected to HostDeviceManager")

            except Exception as e:

                logger.debug(f"Visualizer not available: {e}")

        

        # Platform-specific detector

        if sys.platform == "win32":

            self._detector = WindowsDeviceDetector()

        else:

            self._detector = UnixDeviceDetector()

        

        # SOTA 2026: Unified Windows Host Bridge for WSL2 access to Windows hardware

        self._windows_bridge = None

        if _is_wsl():

            try:

                from core.windows_host_bridge import get_windows_host_bridge

                self._windows_bridge = get_windows_host_bridge(event_bus=self.event_bus)

                logger.info("🌉 WindowsHostBridge initialized for WSL2 hardware access")

            except Exception as e:

                logger.debug(f"WindowsHostBridge not available: {e}")

        

        # SOTA 2026: Device Takeover Manager for automatic device control

        self._takeover_manager = get_device_takeover_manager(event_bus)

        if self._windows_bridge:

            self._takeover_manager.set_windows_bridge(self._windows_bridge)

        

        # SOTA 2026: Network Device Control for Xbox, PlayStation, PCs

        self._network_controller = None

        try:

            from core.network_device_control import get_network_device_controller

            self._network_controller = get_network_device_controller(event_bus)

            logger.info("✅ Network Device Controller integrated (Xbox, PlayStation, PCs)")

        except Exception as e:

            logger.debug(f"Network Device Controller not available: {e}")

        

        logger.info("🔌 HostDeviceManager initialized with Kingdom AI integrations + Auto-Takeover + Network Control")

    

    def _ai_enrich_device(self, device: 'HostDevice') -> None:
        """Use Ollama brain to classify/enrich devices with vague or unknown info."""
        if not _ensure_orch():
            return
        name_lower = (device.name or "").lower()
        if device.capabilities and len(device.capabilities) > 1:
            return
        try:
            import requests as _req
            model = _orch.get_model_for_task("devices")
            url = get_ollama_url()
            prompt = (
                f"Identify this device and list its capabilities.\n"
                f"Name: {device.name}\nCategory: {device.category}\n"
                f"Status: {device.status}\nDriver: {device.driver}\n"
                f"Respond ONLY valid JSON: "
                f'{{"capabilities": ["cap1", "cap2"], "friendly_name": "...", "recommended_use": "..."}}'
            )
            resp = _req.post(
                f"{url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 120, "temperature": 0.1},
                      "keep_alive": -1},
                timeout=12,
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "")
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    import json as _j
                    parsed = _j.loads(raw[start:end])
                    caps = parsed.get("capabilities", [])
                    if isinstance(caps, list):
                        device.capabilities = {c: True for c in caps[:10]}
                    fname = parsed.get("friendly_name")
                    if fname and isinstance(fname, str) and len(fname) < 80:
                        device.ai_friendly_name = fname
                    device.ai_enriched = True
                    logger.debug("AI enriched device '%s' → %d caps", device.name, len(device.capabilities))
        except Exception as e:
            logger.debug("AI device enrichment failed for %s: %s", device.name, e)

    def scan_all_devices(self) -> Dict[str, List[HostDevice]]:

        """Scan for all device types.

        

        CRITICAL: First checks Kingdom AI existing systems, then falls back to OS detection.

        

        Returns:

            Dictionary of device lists by category

        """

        logger.info("🔍 Scanning all host devices (Kingdom AI + OS + SDR + MCU + Automotive)...")

        results = {

            "usb": [],

            "serial": [],

            "bluetooth": [],

            "audio": [],

            "webcam": [],

            "vr": [],

            "sdr": [],  # Software Defined Radio devices

            "network": [],  # Network interfaces

            "microcontrollers": [],  # Arduino, ESP32, STM32, etc. - SOTA 2026

            "automotive": [],  # CAN, OBD-II - SOTA 2026

            "lidar": [],  # LiDAR sensors - SOTA 2026

            "lab_equipment": [],  # Oscilloscopes, DMMs - SOTA 2026

            "imaging": [],  # Microscopes, telescopes, Pi cameras - SOTA 2026

            "drones": [],  # UAV/MAVLink - SOTA 2026

            "kingdom_devices": []  # Devices from Kingdom AI systems

        }

        

        # =====================================================================

        # PRIORITY 1: Kingdom AI existing device systems

        # =====================================================================

        try:

            # VR from VRManager

            vr_devices = self._kingdom_integration.detect_vr_from_vr_manager()

            results["vr"].extend(vr_devices)

            results["kingdom_devices"].extend(vr_devices)

            

            # Webcam from MJPEG server (generic - any brand)

            webcam_devices = self._kingdom_integration.detect_webcam_from_mjpeg_server()

            results["webcam"].extend(webcam_devices)

            results["kingdom_devices"].extend(webcam_devices)

            

            # Bluetooth from Black Panther

            bt_devices = self._kingdom_integration.detect_bluetooth_from_black_panther()

            results["bluetooth"].extend(bt_devices)

            results["kingdom_devices"].extend(bt_devices)

            

            # Voice/Audio from VoiceManager

            voice_devices = self._kingdom_integration.detect_voice_audio_devices()

            results["audio"].extend(voice_devices)

            results["kingdom_devices"].extend(voice_devices)

            

            # WSL Audio Bridge

            bridge_devices = self._kingdom_integration.detect_wsl_audio_bridge()

            results["audio"].extend(bridge_devices)

            results["kingdom_devices"].extend(bridge_devices)

            

            logger.info(f"✅ Kingdom AI devices: {len(results['kingdom_devices'])} found")

        except Exception as e:

            logger.warning(f"Kingdom AI device scan error: {e}")

        

        # =====================================================================

        # PRIORITY 2: OS-level device detection (supplements Kingdom AI)

        # =====================================================================

        try:

            results["usb"] = self._detector.detect_usb_devices()

            results["serial"] = self._detector.detect_serial_ports()

            

            # Only add OS bluetooth if not already found via Kingdom AI

            if not results["bluetooth"]:

                results["bluetooth"] = self._detector.detect_bluetooth_devices()



            try:

                nearby_unpaired = self._detector.detect_bluetooth_nearby_unpaired()

                existing_names = {d.name.lower().strip() for d in results["bluetooth"] if d.name}

                for dev in nearby_unpaired:

                    if dev.name.lower().strip() not in existing_names:

                        results["bluetooth"].append(dev)

            except Exception:

                pass

            

            # Add OS audio devices (may include more than just voice system)

            os_audio = self._detector.detect_audio_devices()

            # Avoid duplicates by checking IDs

            existing_ids = {d.id for d in results["audio"]}

            for dev in os_audio:

                if dev.id not in existing_ids:

                    results["audio"].append(dev)

            

            # Only add OS webcams if not already found via Kingdom AI

            if not results["webcam"]:

                results["webcam"] = self._detector.detect_webcams()

            

            # Only add OS VR if not already found via Kingdom AI

            if not results["vr"]:

                results["vr"] = self._detector.detect_vr_devices()

        except Exception as e:

            logger.error(f"OS device scan error: {e}")

        

        # =====================================================================

        # PRIORITY 3: SDR device detection via SoapySDR

        # =====================================================================

        try:

            sdr_devices = self._detect_sdr_devices()

            results["sdr"].extend(sdr_devices)

            results["kingdom_devices"].extend(sdr_devices)

            if sdr_devices:

                logger.info(f"📻 SDR devices: {len(sdr_devices)} found")

        except Exception as e:

            logger.debug(f"SDR device scan error: {e}")

        

        # =====================================================================

        # PRIORITY 4: Network interface detection

        # =====================================================================

        try:

            network_devices = self._detect_network_interfaces()

            results["network"].extend(network_devices)

            if network_devices:

                logger.info(f"🌐 Network interfaces: {len(network_devices)} found")

        except Exception as e:

            logger.debug(f"Network interface scan error: {e}")

        

        # =====================================================================

        # PRIORITY 5: Microcontroller detection (Arduino, ESP32, STM32) - SOTA 2026

        # =====================================================================

        try:

            mcu_devices = self._detect_microcontrollers()

            results["microcontrollers"].extend(mcu_devices)

            if mcu_devices:

                logger.info(f"🔌 Microcontrollers: {len(mcu_devices)} found")

        except Exception as e:

            logger.debug(f"Microcontroller scan error: {e}")

        

        # =====================================================================

        # PRIORITY 6: Automotive devices (CAN, OBD-II) - SOTA 2026

        # =====================================================================

        try:

            auto_devices = self._detect_automotive_devices()

            results["automotive"].extend(auto_devices)

            if auto_devices:

                logger.info(f"🚗 Automotive devices: {len(auto_devices)} found")

        except Exception as e:

            logger.debug(f"Automotive device scan error: {e}")

        

        # =====================================================================

        # PRIORITY 7: LiDAR sensors - SOTA 2026

        # =====================================================================

        try:

            lidar_devices = self._detect_lidar_devices()

            results["lidar"].extend(lidar_devices)

            if lidar_devices:

                logger.info(f"📡 LiDAR sensors: {len(lidar_devices)} found")

        except Exception as e:

            logger.debug(f"LiDAR scan error: {e}")

        

        # =====================================================================

        # PRIORITY 8: Lab equipment (VISA/SCPI) - SOTA 2026

        # =====================================================================

        try:

            lab_devices = self._detect_lab_equipment()

            results["lab_equipment"].extend(lab_devices)

            if lab_devices:

                logger.info(f"📈 Lab equipment: {len(lab_devices)} found")

        except Exception as e:

            logger.debug(f"Lab equipment scan error: {e}")

        

        # =====================================================================

        # PRIORITY 9: Imaging devices (microscopes, telescopes, Pi cameras)

        # =====================================================================

        try:

            imaging_devices = self._detect_imaging_devices()

            results["imaging"].extend(imaging_devices)

            if imaging_devices:

                logger.info(f"🔬 Imaging devices: {len(imaging_devices)} found")

                # Auto-wire imaging devices to vision display

                for dev in imaging_devices:

                    self.wire_device_to_visualization(dev.id)

        except Exception as e:

            logger.debug(f"Imaging device scan error: {e}")

        

        # =====================================================================

        # PRIORITY 10: Windows Host Bridge devices (WSL2 → Windows hardware)

        # =====================================================================

        if self._windows_bridge:

            try:

                bridge_devices = self._detect_windows_bridge_devices()

                for dev in bridge_devices:

                    # Add to appropriate category

                    if dev.category == DeviceCategory.AUDIO_INPUT:

                        results["audio"].append(dev)

                    elif dev.category == DeviceCategory.AUDIO_OUTPUT:

                        results["audio"].append(dev)

                    elif dev.category == DeviceCategory.WEBCAM:

                        results["webcam"].append(dev)

                results["kingdom_devices"].extend(bridge_devices)

                if bridge_devices:

                    logger.info(f"🌉 Windows bridge devices: {len(bridge_devices)} found")

            except Exception as e:

                logger.debug(f"Windows bridge scan error: {e}")

        

        if _ensure_orch():
            for _cat, _devlist in results.items():
                for _dev in _devlist:
                    if not getattr(_dev, 'ai_enriched', False):
                        self._ai_enrich_device(_dev)

        # Update internal device registry

        with self._lock:

            old_devices = set(self.devices.keys())

            new_devices: Set[str] = set()

            

            for category, device_list in results.items():

                for device in device_list:

                    self.devices[device.id] = device

                    new_devices.add(device.id)

            

            # Detect newly connected devices

            for device_id in new_devices - old_devices:

                self._publish_event("device.connected", self.devices[device_id])

            

            # Detect disconnected devices

            for device_id in old_devices - new_devices:

                if device_id in self.devices:

                    device = self.devices[device_id]

                    device.status = DeviceStatus.DISCONNECTED

                    self._publish_event("device.disconnected", device)

        

        total = sum(len(v) for v in results.values())

        logger.info(f"✅ Device scan complete: {total} devices found")

        

        return results

    

    def get_all_devices(self) -> List[HostDevice]:

        """Get all known devices.

        

        Returns:

            List of all HostDevice objects

        """

        with self._lock:

            return list(self.devices.values())

    

    def get_devices_by_category(self, category: DeviceCategory) -> List[HostDevice]:

        """Get devices by category.

        

        Args:

            category: DeviceCategory to filter by

            

        Returns:

            List of matching devices

        """

        with self._lock:

            return [d for d in self.devices.values() if d.category == category]

    

    def get_device_by_id(self, device_id: str) -> Optional[HostDevice]:

        """Get a device by its ID.

        

        Args:

            device_id: Device identifier

            

        Returns:

            HostDevice or None

        """

        with self._lock:

            return self.devices.get(device_id)

    

    def find_devices(self, query: str) -> List[HostDevice]:

        """Search for devices by name or type.

        

        Args:

            query: Search query (matches name, vendor, product)

            

        Returns:

            List of matching devices

        """

        query_lower = query.lower()

        with self._lock:

            return [

                d for d in self.devices.values()

                if query_lower in d.name.lower()

                or query_lower in d.vendor.lower()

                or query_lower in d.product.lower()

                or query_lower in d.category.value

            ]

    

    def _detect_sdr_devices(self) -> List[HostDevice]:

        """Detect SDR (Software Defined Radio) devices via SoapySDR.

        

        SOTA 2026: Uses SoapySDRRadioBackend.enumerate_devices() for unified detection.

        Gracefully handles missing SoapySDR library.

        

        Returns:

            List of detected SDR devices

        """

        devices = []

        try:

            from core.comms_rf_backend import SoapySDRRadioBackend

            backend = SoapySDRRadioBackend(event_bus=self.event_bus, publish_chat=lambda x: None)

            

            if not backend.is_available():

                logger.debug("SoapySDR not available - no SDR devices detected")

                return devices

            

            soapy_devices = backend.enumerate_devices()

            for i, dev_info in enumerate(soapy_devices):

                driver = dev_info.get("driver", "unknown")

                label = dev_info.get("label", f"SDR Device {i}")

                serial = dev_info.get("serial", "")

                

                device = HostDevice(

                    id=f"sdr_{driver}_{serial or i}",

                    name=label or f"{driver.upper()} SDR",

                    category=DeviceCategory.SDR,

                    status=DeviceStatus.CONNECTED,

                    vendor=driver.upper(),

                    product=label,

                    serial=serial,

                    capabilities={

                        "driver": driver,

                        "tx_capable": driver.lower() in ["hackrf", "limesdr", "plutosdr", "usrp", "bladerf"],

                        "rx_capable": True,

                        "raw_info": dev_info

                    },

                    metadata={"source": "soapysdr", "raw": dev_info}

                )

                devices.append(device)

                logger.info(f"📻 SDR device detected: {device.name} (driver={driver})")

        except ImportError:

            logger.debug("comms_rf_backend not available for SDR detection")

        except Exception as e:

            logger.debug(f"SDR device detection error: {e}")

        

        return devices

    

    def _detect_windows_bridge_devices(self) -> List[HostDevice]:

        """Detect devices available through Windows Host Bridge (WSL2 → Windows).

        

        SOTA 2026: Uses PowerShell to enumerate Windows audio/video devices

        and makes them available in WSL2.

        

        Returns:

            List of devices accessible via Windows bridge

        """

        devices = []

        if not self._windows_bridge:

            return devices

        

        try:

            # Get Windows audio devices via bridge

            audio_devices = self._windows_bridge.get_windows_audio_devices()

            

            for i, dev in enumerate(audio_devices.get('input', [])):

                device = HostDevice(

                    id=f"win_bridge_audio_in_{i}",

                    name=dev.get('name', f"Windows Microphone {i}"),

                    category=DeviceCategory.AUDIO_INPUT,

                    status=DeviceStatus.CONNECTED,

                    vendor="Windows",

                    capabilities={

                        "bridge": "windows_host",

                        "type": "input",

                        "speech_recognition": True

                    },

                    metadata={"source": "windows_bridge"}

                )

                devices.append(device)

            

            for i, dev in enumerate(audio_devices.get('output', [])):

                device = HostDevice(

                    id=f"win_bridge_audio_out_{i}",

                    name=dev.get('name', f"Windows Speaker {i}"),

                    category=DeviceCategory.AUDIO_OUTPUT,

                    status=DeviceStatus.CONNECTED,

                    vendor="Windows",

                    capabilities={

                        "bridge": "windows_host",

                        "type": "output",

                        "tts": True

                    },

                    metadata={"source": "windows_bridge"}

                )

                devices.append(device)

            

            # Get Windows webcams via bridge

            webcams = self._windows_bridge.get_windows_webcams()

            for i, cam in enumerate(webcams):

                device = HostDevice(

                    id=f"win_bridge_webcam_{i}",

                    name=cam.get('name', f"Windows Camera {i}"),

                    category=DeviceCategory.WEBCAM,

                    status=DeviceStatus.CONNECTED,

                    vendor="Windows",

                    capabilities={

                        "bridge": "windows_host",

                        "mjpeg": True

                    },

                    metadata={"source": "windows_bridge"}

                )

                devices.append(device)

            

            if devices:

                logger.info(f"🌉 Windows bridge: {len(devices)} devices via PowerShell")

        except Exception as e:

            logger.debug(f"Windows bridge device detection error: {e}")

        

        return devices

    

    def _detect_network_interfaces(self) -> List[HostDevice]:

        """Detect network interfaces for UDP voice calls and network comms.

        

        Returns:

            List of network interface devices

        """

        devices = []

        try:

            import psutil

            interfaces = psutil.net_if_addrs()

            stats = psutil.net_if_stats()

            

            for iface_name, addrs in interfaces.items():

                iface_stats = stats.get(iface_name)

                # Check if interface is up using getattr for type safety

                if iface_stats is not None:

                    is_up = getattr(iface_stats, 'isup', True)

                    if not is_up:

                        continue

                

                ipv4_addr = None

                for addr in addrs:

                    family_name = getattr(getattr(addr, 'family', None), 'name', '')

                    if family_name == 'AF_INET':

                        ipv4_addr = getattr(addr, 'address', None)

                        break

                

                if not ipv4_addr or ipv4_addr.startswith("127."):

                    continue

                

                device = HostDevice(

                    id=f"network_{iface_name}",

                    name=f"Network: {iface_name}",

                    category=DeviceCategory.NETWORK,

                    status=DeviceStatus.CONNECTED,

                    address=ipv4_addr,

                    capabilities={

                        "ipv4": ipv4_addr,

                        "interface": iface_name,

                        "udp_capable": True,

                        "tcp_capable": True

                    },

                    metadata={"source": "psutil"}

                )

                devices.append(device)

        except ImportError:

            logger.debug("psutil not available for network detection")

        except Exception as e:

            logger.debug(f"Network interface detection error: {e}")

        

        return devices

    

    def _detect_microcontrollers(self) -> List[HostDevice]:

        """Detect microcontroller boards (Arduino, ESP32, STM32, Teensy, etc.) - SOTA 2026.

        

        Uses VID:PID signatures to identify specific microcontroller types.

        """

        devices = []

        

        # Known VID:PID mappings for microcontrollers

        MCU_SIGNATURES = {

            # Arduino

            (0x2341, 0x0043): (DeviceCategory.ARDUINO, "Arduino Uno"),

            (0x2341, 0x0042): (DeviceCategory.ARDUINO, "Arduino Mega 2560"),

            (0x2341, 0x8036): (DeviceCategory.ARDUINO, "Arduino Leonardo"),

            (0x2341, 0x8037): (DeviceCategory.ARDUINO, "Arduino Micro"),

            (0x2A03, 0x0043): (DeviceCategory.ARDUINO, "Arduino Uno (clone)"),

            (0x1A86, 0x7523): (DeviceCategory.ARDUINO, "CH340 Arduino Clone"),

            (0x10C4, 0xEA60): (DeviceCategory.ESP32, "CP210x (ESP/Arduino)"),

            # ESP32/ESP8266

            (0x10C4, 0xEA60): (DeviceCategory.ESP32, "ESP32/ESP8266 CP210x"),

            (0x1A86, 0x55D4): (DeviceCategory.ESP32, "ESP32-S2 Native"),

            (0x303A, 0x1001): (DeviceCategory.ESP32, "ESP32-S2"),

            (0x303A, 0x80D1): (DeviceCategory.ESP32, "ESP32-C3"),

            # STM32

            (0x0483, 0x5740): (DeviceCategory.STM32, "STM32 VCP"),

            (0x0483, 0xDF11): (DeviceCategory.STM32, "STM32 DFU"),

            (0x0483, 0x374B): (DeviceCategory.STM32, "ST-Link V2.1"),

            # Teensy

            (0x16C0, 0x0483): (DeviceCategory.TEENSY, "Teensy"),

            (0x16C0, 0x0486): (DeviceCategory.TEENSY, "Teensy MIDI"),

            (0x16C0, 0x0478): (DeviceCategory.TEENSY, "Teensy 4.x"),

            # Raspberry Pi Pico

            (0x2E8A, 0x0005): (DeviceCategory.PICO, "Raspberry Pi Pico"),

            (0x2E8A, 0x000A): (DeviceCategory.PICO, "Raspberry Pi Pico W"),

        }

        

        try:

            from serial.tools import list_ports

            for port in list_ports.comports():

                vid = port.vid

                pid = port.pid

                

                if (vid, pid) in MCU_SIGNATURES:

                    category, name = MCU_SIGNATURES[(vid, pid)]

                    port_id = port.device.replace('/', '_').replace('\\', '_')

                    device = HostDevice(

                        id=f"mcu_{port_id}",

                        name=f"{name} @ {port.device}",

                        category=category,

                        status=DeviceStatus.CONNECTED,

                        vendor=port.manufacturer or "",

                        product=name,

                        serial=port.serial_number or "",

                        port=port.device,

                        capabilities={

                            "vid": vid, "pid": pid,

                            "serial_port": port.device,

                            "programmable": True,

                            "gpio": True,

                        },

                        metadata={"source": "pyserial", "hwid": port.hwid}

                    )

                    devices.append(device)

                    logger.debug(f"🔌 MCU detected: {name} on {port.device}")

                else:

                    # Check description for MCU keywords

                    desc = (port.description or "").lower()

                    if any(kw in desc for kw in ["arduino", "esp32", "esp8266", "stm32", "teensy", "pico"]):

                        category = DeviceCategory.ARDUINO

                        if "esp" in desc:

                            category = DeviceCategory.ESP32

                        elif "stm" in desc:

                            category = DeviceCategory.STM32

                        elif "teensy" in desc:

                            category = DeviceCategory.TEENSY

                        elif "pico" in desc:

                            category = DeviceCategory.PICO

                        

                        port_id = port.device.replace('/', '_').replace('\\', '_')

                        device = HostDevice(

                            id=f"mcu_{port_id}",

                            name=f"{port.description} @ {port.device}",

                            category=category,

                            status=DeviceStatus.CONNECTED,

                            vendor=port.manufacturer or "",

                            port=port.device,

                            capabilities={"serial_port": port.device, "programmable": True},

                            metadata={"source": "pyserial_keyword"}

                        )

                        devices.append(device)

        except ImportError:

            logger.debug("pyserial not available for MCU detection")

        except Exception as e:

            logger.debug(f"MCU detection error: {e}")

        

        return devices

    

    def _detect_automotive_devices(self) -> List[HostDevice]:

        """Detect automotive devices (CAN adapters, OBD-II) - SOTA 2026."""

        devices = []

        

        # Known VID:PID for CAN/OBD adapters

        AUTO_SIGNATURES = {

            (0x1D50, 0x606F): (DeviceCategory.CAN_INTERFACE, "CANable"),

            (0x1D50, 0x6070): (DeviceCategory.CAN_INTERFACE, "CANable Pro"),

            (0x16D0, 0x0E80): (DeviceCategory.CAN_INTERFACE, "USB2CAN"),

            (0x0403, 0x6015): (DeviceCategory.CAN_INTERFACE, "FTDI CAN Adapter"),

            (0x1FFF, 0x0004): (DeviceCategory.OBD2_ADAPTER, "OBDLink"),

        }

        

        try:

            from serial.tools import list_ports

            for port in list_ports.comports():

                vid = port.vid

                pid = port.pid

                desc = (port.description or "").lower()

                

                if (vid, pid) in AUTO_SIGNATURES:

                    category, name = AUTO_SIGNATURES[(vid, pid)]

                    port_id = port.device.replace('/', '_').replace('\\', '_')

                    device = HostDevice(

                        id=f"auto_{port_id}",

                        name=f"{name} @ {port.device}",

                        category=category,

                        status=DeviceStatus.CONNECTED,

                        port=port.device,

                        capabilities={"can_bus": True, "serial_port": port.device},

                        metadata={"source": "pyserial"}

                    )

                    devices.append(device)

                elif any(kw in desc for kw in ["can", "obd", "elm327", "slcan", "pcan"]):

                    category = DeviceCategory.OBD2_ADAPTER if "obd" in desc or "elm" in desc else DeviceCategory.CAN_INTERFACE

                    port_id = port.device.replace('/', '_').replace('\\', '_')

                    device = HostDevice(

                        id=f"auto_{port_id}",

                        name=f"{port.description} @ {port.device}",

                        category=category,

                        status=DeviceStatus.CONNECTED,

                        port=port.device,

                        capabilities={"can_bus": "can" in desc, "obd2": "obd" in desc or "elm" in desc},

                        metadata={"source": "pyserial_keyword"}

                    )

                    devices.append(device)

        except ImportError:

            pass

        except Exception as e:

            logger.debug(f"Automotive device detection error: {e}")

        

        return devices

    

    def _detect_lidar_devices(self) -> List[HostDevice]:

        """Detect LiDAR sensors - SOTA 2026."""

        devices = []

        

        try:

            from serial.tools import list_ports

            for port in list_ports.comports():

                desc = (port.description or "").lower()

                if any(kw in desc for kw in ["lidar", "rplidar", "velodyne", "sick", "livox", "ouster", "hokuyo"]):

                    port_id = port.device.replace('/', '_').replace('\\', '_')

                    device = HostDevice(

                        id=f"lidar_{port_id}",

                        name=f"LiDAR: {port.description} @ {port.device}",

                        category=DeviceCategory.LIDAR,

                        status=DeviceStatus.CONNECTED,

                        vendor=port.manufacturer or "",

                        port=port.device,

                        capabilities={

                            "serial_port": port.device,

                            "scan_type": "2D" if "rplidar" in desc else "3D",

                        },

                        metadata={"source": "pyserial"}

                    )

                    devices.append(device)

        except ImportError:

            pass

        except Exception as e:

            logger.debug(f"LiDAR detection error: {e}")

        

        return devices

    

    def _detect_imaging_devices(self) -> List[HostDevice]:

        """Detect USB microscopes, telescopes, endoscopes, Pi cameras - SOTA 2026.

        

        Uses VID:PID signatures and OpenCV to identify imaging devices.

        """

        devices = []

        

        # Known VID:PID for imaging devices

        IMAGING_SIGNATURES = {

            # USB Microscopes

            (0x1908, 0x0102): (DeviceCategory.USB_MICROSCOPE, "AmScope USB Microscope"),

            (0x0547, 0x1002): (DeviceCategory.USB_MICROSCOPE, "USB Microscope (Generic)"),

            (0x05a3, 0x9230): (DeviceCategory.USB_MICROSCOPE, "Digital Microscope 1000X"),

            (0x1871, 0x0101): (DeviceCategory.USB_MICROSCOPE, "Andonstar Microscope"),

            (0x0c45, 0x6366): (DeviceCategory.USB_MICROSCOPE, "Sonix USB Microscope"),

            # Endoscopes

            (0x05a3, 0x9520): (DeviceCategory.ENDOSCOPE, "USB Endoscope 5.5mm"),

            (0x1b71, 0x3002): (DeviceCategory.ENDOSCOPE, "USB Borescope"),

            # Telescope cameras / Astrophotography

            (0x1856, 0x0011): (DeviceCategory.TELESCOPE_CAMERA, "ZWO ASI Camera"),

            (0x03c3, 0x120b): (DeviceCategory.TELESCOPE_CAMERA, "QHY CCD Camera"),

            (0x0547, 0x4d88): (DeviceCategory.TELESCOPE_CAMERA, "Celestron Camera"),

            # Thermal cameras

            (0x09cb, 0x1996): (DeviceCategory.THERMAL_CAMERA, "FLIR Lepton"),

            (0x09cb, 0x1001): (DeviceCategory.THERMAL_CAMERA, "FLIR One"),

            (0x1e4e, 0x0100): (DeviceCategory.THERMAL_CAMERA, "Seek Thermal"),

            # Action cameras

            (0x2672, 0x0001): (DeviceCategory.ACTION_CAMERA, "GoPro"),

            (0x2970, 0x0001): (DeviceCategory.ACTION_CAMERA, "DJI Osmo"),

        }

        

        # Check USB devices

        try:

            from serial.tools import list_ports

            for port in list_ports.comports():

                vid = port.vid

                pid = port.pid

                

                if (vid, pid) in IMAGING_SIGNATURES:

                    category, name = IMAGING_SIGNATURES[(vid, pid)]

                    port_id = port.device.replace('/', '_').replace('\\', '_')

                    device = HostDevice(

                        id=f"imaging_{port_id}",

                        name=f"{name} @ {port.device}",

                        category=category,

                        status=DeviceStatus.CONNECTED,

                        vendor=port.manufacturer or "",

                        port=port.device,

                        capabilities={

                            "vid": vid, "pid": pid,

                            "imaging": True,

                            "stream_capable": True

                        },

                        metadata={"source": "pyserial"}

                    )

                    devices.append(device)

                    logger.debug(f"🔬 Imaging device: {name}")

        except ImportError:

            pass

        except Exception as e:

            logger.debug(f"Imaging device serial detection error: {e}")

        

        # Check video capture devices with OpenCV

        try:

            import cv2

            for idx in range(5):  # Check first 5 video devices
                cap = None
                try:
                    cap = cv2.VideoCapture(idx)
                    
                    if cap.isOpened():
                        # Get device info
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        
                        # Try to get backend name
                        backend = cap.getBackendName() if hasattr(cap, 'getBackendName') else "unknown"
                        
                        # Determine category based on resolution/name
                        category = DeviceCategory.WEBCAM
                        name = f"Video Device {idx}"
                        
                        # High-res devices are likely microscopes or special cameras
                        if width >= 2048 or height >= 2048:
                            category = DeviceCategory.USB_MICROSCOPE
                            name = f"High-Res Camera {idx} ({width}x{height})"
                        
                        device = HostDevice(
                            id=f"video_{idx}",
                            name=name,
                            category=category,
                            status=DeviceStatus.CONNECTED,
                            capabilities={
                                "video_index": idx,
                                "width": width,
                                "height": height,
                                "fps": fps,
                                "backend": backend,
                                "stream_capable": True
                            },
                            metadata={"source": "opencv"}
                        )
                        devices.append(device)
                except Exception as e:
                    logger.debug(f"Video device index {idx} check failed: {e}")
                finally:
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass

        except ImportError:

            logger.debug("OpenCV not available for video device detection")

        except Exception as e:

            logger.debug(f"OpenCV video detection error: {e}")

        

        # Check for Raspberry Pi camera (via picamera2 or raspistill)

        try:

            # Check if we're on a Pi with camera

            if os.path.exists("/dev/video0") or os.path.exists("/boot/config.txt"):

                # Try picamera2

                try:

                    from picamera2 import Picamera2

                    pi_cam = Picamera2()

                    cam_info = pi_cam.camera_properties

                    pi_cam.close()

                    

                    device = HostDevice(

                        id="pi_camera_0",

                        name=f"Raspberry Pi Camera ({cam_info.get('Model', 'Unknown')})",

                        category=DeviceCategory.PI_CAMERA,

                        status=DeviceStatus.CONNECTED,

                        capabilities={

                            "model": cam_info.get("Model", "Unknown"),

                            "max_resolution": cam_info.get("PixelArraySize", [0, 0]),

                            "stream_capable": True

                        },

                        metadata={"source": "picamera2"}

                    )

                    devices.append(device)

                    logger.debug("🍓 Raspberry Pi Camera detected")

                except ImportError:

                    pass

        except Exception as e:

            logger.debug(f"Pi camera detection error: {e}")

        

        return devices

    

    def _detect_lab_equipment(self) -> List[HostDevice]:

        """Detect lab equipment via VISA/SCPI - SOTA 2026."""

        devices = []

        

        try:

            import pyvisa

            rm = pyvisa.ResourceManager()

            resources = rm.list_resources()

            

            for resource in resources:

                try:

                    inst = rm.open_resource(resource)

                    inst.timeout = 2000

                    idn = inst.query("*IDN?").strip()

                    inst.close()

                    

                    parts = idn.split(",")

                    vendor = parts[0] if len(parts) > 0 else "Unknown"

                    model = parts[1] if len(parts) > 1 else "Unknown"

                    serial = parts[2] if len(parts) > 2 else ""

                    

                    # Classify by model keywords

                    model_lower = model.lower()

                    if any(x in model_lower for x in ["scope", "dso", "mso"]):

                        category = DeviceCategory.OSCILLOSCOPE

                    elif any(x in model_lower for x in ["gen", "awg", "afg"]):

                        category = DeviceCategory.SIGNAL_GEN

                    elif any(x in model_lower for x in ["dmm", "34", "multi"]):

                        category = DeviceCategory.DMM

                    elif any(x in model_lower for x in ["supply", "psu", "power"]):

                        category = DeviceCategory.POWER_SUPPLY

                    elif any(x in model_lower for x in ["spectrum", "fsa", "rsa"]):

                        category = DeviceCategory.SPECTRUM_ANALYZER

                    else:

                        category = DeviceCategory.OSCILLOSCOPE  # Default

                    

                    device = HostDevice(

                        id=f"lab_{resource.replace('::', '_').replace('/', '_')}",

                        name=f"{vendor} {model}",

                        category=category,

                        status=DeviceStatus.CONNECTED,

                        vendor=vendor,

                        product=model,

                        serial=serial,

                        address=resource,

                        capabilities={"scpi": True, "idn": idn, "visa_resource": resource},

                        metadata={"source": "pyvisa"}

                    )

                    devices.append(device)

                    logger.debug(f"📈 Lab equipment: {vendor} {model}")

                except Exception:

                    pass

        except ImportError:

            logger.debug("PyVISA not available for lab equipment detection")

        except Exception as e:

            logger.debug(f"Lab equipment detection error: {e}")

        

        return devices

    

    def get_devices_needed_guidance(self) -> Dict[str, Any]:

        """Get guidance on which devices are needed for each feature.

        

        SOTA 2026: Analyzes current device inventory and returns:

        - Which features are fully supported

        - Which features are missing required devices

        - Recommendations for hardware to enable more features

        

        Returns:

            Dict with feature availability and recommendations

        """

        # Scan current devices if not already done

        if not self.devices:

            self.scan_all_devices()

        

        # Get current device categories

        current_categories = set()

        with self._lock:

            for device in self.devices.values():

                if device.status in [DeviceStatus.CONNECTED, DeviceStatus.ACTIVE]:

                    current_categories.add(device.category)

        

        guidance = {

            "available_features": [],

            "unavailable_features": [],

            "recommendations": [],

            "device_summary": {}

        }

        

        for feature_name, feature_info in DEVICES_NEEDED_PER_FEATURE.items():

            required = feature_info.get("required", [])

            has_all_required = all(cat in current_categories for cat in required)

            

            feature_status = {

                "feature": feature_name,

                "description": feature_info.get("description", ""),

                "available": has_all_required,

                "required_categories": [cat.value for cat in required],

                "notes": feature_info.get("notes", "")

            }

            

            if has_all_required:

                guidance["available_features"].append(feature_status)

            else:

                missing = [cat.value for cat in required if cat not in current_categories]

                feature_status["missing_categories"] = missing

                feature_status["recommended_devices"] = feature_info.get("recommended", [])

                guidance["unavailable_features"].append(feature_status)

                

                # Add recommendations

                for rec in feature_info.get("recommended", []):

                    if rec not in guidance["recommendations"]:

                        guidance["recommendations"].append(rec)

        

        # Device summary by category

        with self._lock:

            for device in self.devices.values():

                cat = device.category.value

                if cat not in guidance["device_summary"]:

                    guidance["device_summary"][cat] = []

                guidance["device_summary"][cat].append({

                    "name": device.name,

                    "status": device.status.value

                })

        

        return guidance

    

    def get_inventory_for_ai_context(self) -> Dict[str, Any]:

        """Get a concise device inventory summary for AI context injection.

        

        SOTA 2026: Returns a compact summary suitable for including in AI prompts

        so the Ollama brain knows what hardware is available.

        

        Returns:

            Dict with device inventory for AI context

        """

        guidance = self.get_devices_needed_guidance()

        summary = self.get_summary()

        

        return {

            "total_devices": summary.get("total_devices", 0),

            "categories": summary.get("categories", {}),

            "available_features": [f["feature"] for f in guidance.get("available_features", [])],

            "unavailable_features": [

                {"feature": f["feature"], "missing": f.get("missing_categories", [])}

                for f in guidance.get("unavailable_features", [])

            ],

            "recommendations": guidance.get("recommendations", [])[:5],  # Top 5 recommendations

            "wsl2_mode": _is_wsl(),

            "timestamp": time.time()

        }

    

    def get_device_controls_for_ai(self, device_id: str = None) -> Dict[str, Any]:

        """Get all controllable parts of device(s) for AI/Ollama brain awareness.

        

        SOTA 2026 CHAMELEON: Exposes full device control schema so AI can:

        - See all available controls (sliders, buttons, toggles, inputs)

        - Understand what each control does via labels

        - Know the valid ranges/options for each control

        - Generate appropriate control commands

        

        Args:

            device_id: Optional specific device ID, or None for all devices

            

        Returns:

            Dict with complete device control schema for AI context

        """

        if not self.devices:

            self.scan_all_devices()

        

        result = {

            "devices": [],

            "total_controls": 0,

            "ai_instructions": "You can control these devices by referencing their control IDs and setting values within the specified ranges/options."

        }

        

        with self._lock:

            devices_to_process = []

            if device_id:

                device = self.devices.get(device_id)

                if device:

                    devices_to_process = [device]

            else:

                devices_to_process = list(self.devices.values())

            

            for device in devices_to_process:

                # Get chameleon panel for this device category

                panel = CHAMELEON_CONTROL_PANELS.get(device.category, CHAMELEON_CONTROL_PANELS.get(DeviceCategory.UNKNOWN))

                

                device_info = {

                    "device_id": device.id,

                    "name": device.name,

                    "category": device.category.value,

                    "status": device.status.value,

                    "vendor": device.vendor,

                    "port": device.port,

                    "panel_name": panel.get("name", "Device Control"),

                    "panel_icon": panel.get("icon", "⚙️"),

                    "panel_color": panel.get("color", "#888888"),

                    "os_style": panel.get("os_style", "default"),

                    "controls": [],

                    "displays": panel.get("displays", []),

                    "capabilities": device.capabilities

                }

                

                # Add all controls with full details for AI

                for control in panel.get("controls", []):

                    control_info = {

                        "id": control.get("id"),

                        "label": control.get("label"),

                        "type": control.get("type"),

                        "description": f"Control for {control.get('label', 'unknown')}"

                    }

                    

                    # Add type-specific details

                    ctrl_type = control.get("type", "")

                    if ctrl_type == "slider":

                        control_info["min"] = control.get("min", 0)

                        control_info["max"] = control.get("max", 100)

                        control_info["description"] = f"Slider: {control.get('label')} (range {control.get('min', 0)}-{control.get('max', 100)})"

                    elif ctrl_type == "dropdown":

                        control_info["options"] = control.get("options", [])

                        control_info["description"] = f"Dropdown: {control.get('label')} (options: {', '.join(control.get('options', []))})"

                    elif ctrl_type == "toggle":

                        control_info["default"] = control.get("default", False)

                        control_info["description"] = f"Toggle: {control.get('label')} (on/off)"

                    elif ctrl_type == "button":

                        control_info["action"] = control.get("action", "")

                        control_info["danger"] = control.get("danger", False)

                        control_info["description"] = f"Button: {control.get('label')} (action: {control.get('action', 'click')})"

                    elif ctrl_type == "number":

                        control_info["default"] = control.get("default", 0)

                        control_info["description"] = f"Number input: {control.get('label')}"

                    elif ctrl_type in ["text_input", "hex_input"]:

                        control_info["description"] = f"Text input: {control.get('label')}"

                    elif ctrl_type == "frequency_input":

                        control_info["description"] = f"Frequency input: {control.get('label')} (in Hz/MHz)"

                    elif ctrl_type == "pin_grid":

                        control_info["pins"] = control.get("pins", 14)

                        control_info["modes"] = control.get("modes", ["INPUT", "OUTPUT"])

                        control_info["description"] = f"Pin grid: {control.get('pins', 14)} pins with modes {control.get('modes', [])}"

                    

                    device_info["controls"].append(control_info)

                    result["total_controls"] += 1

                

                result["devices"].append(device_info)

        

        return result

    

    def wire_device_to_visualization(self, device_id: str) -> bool:

        """Wire a device's data stream to the universal visualizer for auto-display.

        

        SOTA 2026: Automatically routes device data to appropriate visualization:

        - LiDAR → 3D Point Cloud

        - Sonar/Audio → 3D Surface

        - GPS → 3D Map

        - IMU → Attitude Indicator

        - Webcam → Video Feed

        - CAN/OBD → Vehicle Gauges

        

        Args:

            device_id: Device to wire to visualization

            

        Returns:

            True if successfully wired

        """

        device = self.get_device_by_id(device_id)

        if not device:

            logger.warning(f"Cannot wire device {device_id} - not found")

            return False

        

        if not self._visualizer:

            logger.debug("Visualizer not available for device wiring")

            return False

        

        # Map device category to visualization data type

        CATEGORY_TO_VIS_TYPE = {

            DeviceCategory.LIDAR: "lidar",

            DeviceCategory.DEPTH_CAMERA: "lidar",

            DeviceCategory.RADAR: "lidar",

            DeviceCategory.WEBCAM: "image",

            DeviceCategory.THERMAL_CAMERA: "image",

            DeviceCategory.GPS_RECEIVER: "gps",

            DeviceCategory.IMU: "imu",

            DeviceCategory.AUDIO_INPUT: "audio",

            DeviceCategory.CAN_INTERFACE: "can",

            DeviceCategory.OBD2_ADAPTER: "obd",

            DeviceCategory.SDR: "spectrum",

        }

        

        vis_type = CATEGORY_TO_VIS_TYPE.get(device.category, "generic")

        

        # Register device with visualizer

        self._visualizer.active_streams[device_id] = {

            "category": device.category.value,

            "vis_type": vis_type,

            "device": device.to_dict(),

            "wired_at": datetime.now().isoformat()

        }

        

        # Publish wiring event

        if self.event_bus:

            self.event_bus.publish("device.visualization.wired", {

                "device_id": device_id,

                "device_name": device.name,

                "category": device.category.value,

                "vis_type": vis_type

            })

        

        logger.info(f"🎨 Device {device.name} wired to {vis_type} visualization")

        return True

    

    def get_visualization_for_device(self, device_id: str) -> Dict[str, Any]:

        """Get the appropriate visualization configuration for a device.

        

        Returns visualization type and display parameters based on device category.

        """

        device = self.get_device_by_id(device_id)

        if not device:

            return {"error": "Device not found"}

        

        # Visualization configurations per device category

        VIS_CONFIGS = {

            DeviceCategory.LIDAR: {

                "type": "point_cloud_3d",

                "display": "3d_pointcloud",

                "color_by": "distance",

                "point_size": 2,

                "render_mode": "scatter"

            },

            DeviceCategory.DEPTH_CAMERA: {

                "type": "point_cloud_3d",

                "display": "3d_pointcloud",

                "color_by": "depth",

                "point_size": 1,

                "render_mode": "dense"

            },

            DeviceCategory.GPS_RECEIVER: {

                "type": "map_3d",

                "display": "map_view",

                "show_trail": True,

                "trail_length": 100,

                "marker_type": "aircraft"

            },

            DeviceCategory.IMU: {

                "type": "attitude",

                "display": "attitude_indicator",

                "show_heading": True,

                "show_horizon": True

            },

            DeviceCategory.WEBCAM: {

                "type": "video_feed",

                "display": "video_panel",

                "mirror": True,

                "enhance": False

            },

            DeviceCategory.THERMAL_CAMERA: {

                "type": "heatmap",

                "display": "thermal_view",

                "colormap": "inferno",

                "show_temp_scale": True

            },

            DeviceCategory.SDR: {

                "type": "spectrum",

                "display": "waterfall",

                "fft_size": 2048,

                "show_waterfall": True

            },

            DeviceCategory.CAN_INTERFACE: {

                "type": "gauge",

                "display": "gauge_cluster",

                "show_message_log": True

            },

            DeviceCategory.OBD2_ADAPTER: {

                "type": "gauge",

                "display": "vehicle_dashboard",

                "gauges": ["rpm", "speed", "coolant", "fuel"]

            },

            DeviceCategory.AUDIO_INPUT: {

                "type": "waveform",

                "display": "audio_scope",

                "show_fft": True,

                "show_waveform": True

            },

        }

        

        config = VIS_CONFIGS.get(device.category, {

            "type": "generic",

            "display": "data_table"

        })

        

        return {

            "device_id": device_id,

            "device_name": device.name,

            "category": device.category.value,

            "visualization": config

        }

    

    def get_chameleon_panel_for_device(self, device_id: str) -> Dict[str, Any]:

        """Get the chameleon UI panel configuration for a specific device.

        

        SOTA 2026: Returns the adaptive UI panel that morphs to match

        the device's operating system style and control requirements.

        

        Args:

            device_id: Device identifier

            

        Returns:

            Chameleon panel configuration dict

        """

        device = self.get_device_by_id(device_id)

        if not device:

            return CHAMELEON_CONTROL_PANELS.get(DeviceCategory.UNKNOWN, {})

        

        panel = CHAMELEON_CONTROL_PANELS.get(device.category) or CHAMELEON_CONTROL_PANELS.get(DeviceCategory.UNKNOWN) or {}

        

        # Add device-specific info to panel

        result = dict(panel)

        result.update({

            "device_id": device.id,

            "device_name": device.name,

            "device_status": device.status.value,

            "device_vendor": device.vendor,

            "device_port": device.port,

            "device_capabilities": device.capabilities

        })

        return result

    

    def enable_device(self, device_id: str) -> bool:

        """Enable/connect a device.

        

        Args:

            device_id: Device identifier

            

        Returns:

            True if successful

        """

        device = self.get_device_by_id(device_id)

        if not device:

            logger.warning(f"Device not found: {device_id}")

            return False

        

        try:

            if device.category == DeviceCategory.BLUETOOTH:

                # IMPORTANT REALITY (Windows): true Bluetooth pairing often requires user confirmation (PIN / consent).

                # We will:

                # 1) Try WinRT pairing if 'winrt' is installed AND we can run an event loop safely.

                # 2) Enable the PnP device (works for already-paired devices).

                # 3) Always provide a reliable fallback: open Bluetooth settings UI for pairing/connecting.



                def _open_bluetooth_settings() -> bool:

                    try:

                        _open_windows_uri("ms-settings:bluetooth")

                        return True

                    except Exception as e:

                        device.metadata["settings_open_error"] = str(e)

                        return False



                def _enable_pnp(instance_id: str) -> bool:

                    if not instance_id:

                        return False

                    cmd = f'''

                    $d = Get-PnpDevice | Where-Object {{ $_.InstanceId -eq "{instance_id}" }}

                    if ($d) {{ Enable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false | Out-Null; exit 0 }}

                    exit 1

                    '''

                    result = _run_powershell(cmd, timeout=15)

                    if result.returncode == 0:

                        return True

                    device.metadata["pnp_enable_error"] = (result.stderr or "").strip()

                    return False



                def _try_winrt_pair_by_name(target_name: str) -> bool:

                    try:

                        import asyncio

                        from winrt.windows.devices.enumeration import DeviceInformation  # type: ignore

                        from winrt.windows.devices.enumeration import DevicePairingProtectionLevel  # type: ignore



                        async def _pair() -> bool:

                            infos = await DeviceInformation.find_all_async()  # type: ignore[attr-defined]

                            for info in infos:

                                try:

                                    name = (getattr(info, "name", "") or "").lower()

                                    if not name:

                                        continue

                                    if target_name.lower() not in name:

                                        continue

                                    pairing = getattr(info, "pairing", None)

                                    if not pairing:

                                        continue

                                    if getattr(pairing, "is_paired", False):

                                        device.metadata["pair_result"] = "already_paired"

                                        return True

                                    res = await pairing.pair_async(DevicePairingProtectionLevel.default)  # type: ignore[attr-defined]

                                    device.metadata["pair_result"] = str(getattr(res, "status", "unknown"))

                                    return True

                                except Exception:

                                    continue

                            return False



                        return bool(asyncio.run(_pair()))

                    except Exception:

                        return False



                instance_id = (device.metadata or {}).get("instance_id", "") if isinstance(device.metadata, dict) else ""

                winrt_id = (device.metadata or {}).get("winrt_id", "") if isinstance(device.metadata, dict) else ""

                paired_or_initiated = False



                if winrt_id:

                    res = _pair_bluetooth_winrt_powershell(winrt_id, timeout=90)

                    device.metadata["winrt_pair_ps"] = res

                    status_val = str(res.get("status", "")) if isinstance(res, dict) else ""

                    status_norm = status_val.strip().lower()

                    if res.get("success") and status_norm in {"paired", "alreadypaired", "already_paired"}:

                        device.status = DeviceStatus.PAIRED

                        paired_or_initiated = True

                    elif res.get("success"):

                        # PairAsync returned a status but not paired; user interaction may be required.

                        device.status = DeviceStatus.AVAILABLE

                        device.metadata["action_required"] = f"Pairing result: {status_val}. Complete pairing in Windows Bluetooth Settings."

                        _open_bluetooth_settings()

                        paired_or_initiated = True

                    else:

                        device.status = DeviceStatus.AVAILABLE

                        device.metadata["action_required"] = "Complete pairing in Windows Bluetooth Settings"

                        _open_bluetooth_settings()

                        paired_or_initiated = True



                # 1) WinRT pairing attempt (optional)

                if device.name:

                    try:

                        # Run pairing in a background thread so we never block the GUI/event loop.

                        def _pair_worker():

                            try:

                                ok = _try_winrt_pair_by_name(device.name)

                                device.metadata["winrt_pair_attempted"] = True

                                device.metadata["winrt_pair_ok"] = bool(ok)

                            except Exception as e:

                                device.metadata["winrt_pair_attempted"] = True

                                device.metadata["winrt_pair_error"] = str(e)



                        t = threading.Thread(target=_pair_worker, daemon=True)

                        t.start()

                        device.metadata["winrt_pairing_started"] = True

                    except Exception:

                        pass



                # 2) Enable PnP (useful for already paired devices)

                if _enable_pnp(instance_id):

                    paired_or_initiated = True

                    device.status = DeviceStatus.CONNECTED



                # 3) Fallback: open Settings to complete pairing/connecting

                if not paired_or_initiated:

                    if _open_bluetooth_settings():

                        device.status = DeviceStatus.AVAILABLE

                        device.metadata["action_required"] = "Finish pairing/connecting in Windows Bluetooth Settings"

                        paired_or_initiated = True

                    else:

                        return False



            else:

                device.status = DeviceStatus.ACTIVE

            self._publish_event("device.enabled", device)

            logger.info(f"✅ Enabled device: {device.name}")

            return True

        except Exception as e:

            logger.error(f"Failed to enable device {device_id}: {e}")

            return False

    

    def disable_device(self, device_id: str) -> bool:

        """Disable/disconnect a device.

        

        Args:

            device_id: Device identifier

            

        Returns:

            True if successful

        """

        device = self.get_device_by_id(device_id)

        if not device:

            logger.warning(f"Device not found: {device_id}")

            return False

        

        try:

            if device.category == DeviceCategory.BLUETOOTH:

                instance_id = ""

                try:

                    instance_id = (device.metadata or {}).get("instance_id", "")

                except Exception:

                    instance_id = ""



                if instance_id:

                    cmd = f'''

                    $d = Get-PnpDevice | Where-Object {{ $_.InstanceId -eq "{instance_id}" }}

                    if ($d) {{ Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false | Out-Null; exit 0 }}

                    exit 1

                    '''

                    result = _run_powershell(cmd, timeout=15)

                    if result.returncode != 0:

                        device.metadata["pnp_disable_error"] = (result.stderr or "").strip()

                else:

                    # If we don't have a stable InstanceId, use Settings so user can disconnect/remove.

                    _open_windows_uri("ms-settings:bluetooth")



            device.status = DeviceStatus.DISCONNECTED

            self._publish_event("device.disabled", device)

            logger.info(f"🔌 Disabled device: {device.name}")

            return True

        except Exception as e:

            logger.error(f"Failed to disable device {device_id}: {e}")

            return False

    

    def start_monitoring(self, interval: float = 5.0):

        """Start background device monitoring.

        

        Args:

            interval: Scan interval in seconds

        """

        if self._monitoring:

            return

        

        self._scan_interval = interval

        self._monitoring = True

        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)

        self._monitor_thread.start()

        logger.info(f"🔄 Device monitoring started (interval: {interval}s)")

    

    def stop_monitoring(self):

        """Stop background device monitoring."""

        self._monitoring = False

        if self._monitor_thread:

            self._monitor_thread.join(timeout=2.0)

        logger.info("⏹️ Device monitoring stopped")

    

    def _monitor_loop(self):

        """Background monitoring loop."""

        while self._monitoring:

            try:

                self.scan_all_devices()

            except Exception as e:

                logger.error(f"Monitor loop error: {e}")

            time.sleep(self._scan_interval)

    

    def _publish_event(self, event_type: str, device: HostDevice):

        """Publish device event to event bus.

        

        Args:

            event_type: Event type string

            device: HostDevice that triggered the event

        """

        if self.event_bus:

            try:

                payload = {

                    "event": event_type,

                    "device": device.to_dict(),

                    "timestamp": datetime.now().isoformat()

                }

                

                # Handle both sync and async event bus

                if hasattr(self.event_bus, 'publish_sync'):

                    self.event_bus.publish_sync(event_type, payload)

                elif hasattr(self.event_bus, 'publish'):

                    self.event_bus.publish(event_type, payload)

                    

                logger.debug(f"📡 Published {event_type}: {device.name}")

            except Exception as e:

                logger.debug(f"Event publish error: {e}")

        

        # SOTA 2026: Auto-trigger device takeover on new device connection

        if event_type == "device.connected" and self._takeover_manager:

            try:

                if self._takeover_manager.auto_takeover_device(device):

                    logger.info(f"🎯 Auto-takeover initiated for: {device.name}")

            except Exception as e:

                logger.debug(f"Auto-takeover trigger error: {e}")

        

        # SOTA 2026: Auto-install frameworks for newly connected devices

        if event_type == "device.connected":

            try:

                from core.device_framework_manager import get_device_framework_manager

                framework_mgr = get_device_framework_manager(self.event_bus)

                device_info = device.to_dict()

                threading.Thread(

                    target=framework_mgr.ensure_frameworks_for_device,

                    args=(device_info,),

                    daemon=True

                ).start()

                logger.debug(f"🔧 Framework installation triggered for: {device.name}")

            except Exception as e:

                logger.debug(f"Framework manager trigger error: {e}")

        

        # Call registered callbacks

        for callback in self._callbacks:

            try:

                callback(event_type, device)

            except Exception as e:

                logger.error(f"Callback error: {e}")

    

    def register_callback(self, callback: Callable[[str, HostDevice], None]):

        """Register a callback for device events.

        

        Args:

            callback: Function(event_type, device) to call on events

        """

        self._callbacks.append(callback)

    

    def get_summary(self) -> Dict[str, Any]:

        """Get a summary of all devices for display.

        

        Returns:

            Summary dictionary

        """

        with self._lock:

            by_category = {}

            for device in self.devices.values():

                cat = device.category.value

                if cat not in by_category:

                    by_category[cat] = []

                by_category[cat].append(device.to_dict())

            

            return {

                "total_devices": len(self.devices),

                "by_category": by_category,

                "categories": {

                    "usb": len([d for d in self.devices.values() if d.category == DeviceCategory.USB]),

                    "serial": len([d for d in self.devices.values() if d.category == DeviceCategory.SERIAL]),

                    "bluetooth": len([d for d in self.devices.values() if d.category == DeviceCategory.BLUETOOTH]),

                    "audio_input": len([d for d in self.devices.values() if d.category == DeviceCategory.AUDIO_INPUT]),

                    "audio_output": len([d for d in self.devices.values() if d.category == DeviceCategory.AUDIO_OUTPUT]),

                    "webcam": len([d for d in self.devices.values() if d.category == DeviceCategory.WEBCAM]),

                    "vr_headset": len([d for d in self.devices.values() if d.category == DeviceCategory.VR_HEADSET])

                },

                "monitoring": self._monitoring,

                "scan_interval": self._scan_interval

            }





# ============================================================================

# SINGLETON INSTANCE

# ============================================================================



_host_device_manager: Optional[HostDeviceManager] = None

_device_learning_system: Optional["DeviceLearningSystem"] = None



def get_host_device_manager(event_bus=None) -> HostDeviceManager:

    """Get or create the global HostDeviceManager instance.

    

    Args:

        event_bus: Optional event bus (only used on first call)

        

    Returns:

        HostDeviceManager singleton

    """

    global _host_device_manager

    if _host_device_manager is None:

        _host_device_manager = HostDeviceManager(event_bus)

    return _host_device_manager





def get_device_learning_system(event_bus=None) -> "DeviceLearningSystem":

    """Get or create the global DeviceLearningSystem instance.

    

    SOTA 2026: Provides AI-powered unknown device learning capabilities.

    When an unknown device is plugged in, call learn_unknown_device to:

    1. Generate an AI query for Ollama to discover device info

    2. Parse the AI response to create control panel config

    3. Auto-generate MCP tools for the device

    4. Persist learned config for future use

    

    Args:

        event_bus: Optional event bus (only used on first call)

        

    Returns:

        DeviceLearningSystem singleton

    """

    global _device_learning_system

    if _device_learning_system is None:

        _device_learning_system = DeviceLearningSystem(event_bus)

    return _device_learning_system





# ============================================================================

# UNKNOWN DEVICE LEARNING SYSTEM - AI Auto-Discovery

# ============================================================================



class DeviceLearningSystem:

    """

    SOTA 2026: AI-powered unknown device learning system.

    

    When an unknown device is detected:

    1. AI searches for device info using VID:PID and description

    2. Generates control panel configuration

    3. Creates MCP tools for the device

    4. Persists learned config for future use

    """

    

    def __init__(self, event_bus=None):

        self.event_bus = event_bus

        self.learned_devices: Dict[str, Dict[str, Any]] = {}

        self._config_path = "config/learned_devices.json"

        self._load_learned_devices()

    

    def _load_learned_devices(self):

        """Load previously learned device configurations."""

        try:

            import os

            if os.path.exists(self._config_path):

                with open(self._config_path, 'r', encoding='utf-8') as f:

                    self.learned_devices = json.load(f)

                logger.info(f"📚 Loaded {len(self.learned_devices)} learned device configs")

        except Exception as e:

            logger.debug(f"Could not load learned devices: {e}")

            self.learned_devices = {}

    

    def _save_learned_devices(self):

        """Persist learned device configurations."""

        try:

            import os

            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)

            with open(self._config_path, 'w', encoding='utf-8') as f:

                json.dump(self.learned_devices, f, indent=2)

            logger.info(f"💾 Saved {len(self.learned_devices)} learned device configs")

        except Exception as e:

            logger.error(f"Could not save learned devices: {e}")

    

    def get_device_signature(self, device: HostDevice) -> str:

        """Generate unique signature for device identification."""

        vid = device.capabilities.get("vid", 0)

        pid = device.capabilities.get("pid", 0)

        if vid and pid:

            return f"vid_{vid:04x}_pid_{pid:04x}"

        return f"name_{device.name.lower().replace(' ', '_')[:32]}"

    

    def is_device_learned(self, device: HostDevice) -> bool:

        """Check if we have learned about this device."""

        sig = self.get_device_signature(device)

        return sig in self.learned_devices

    

    def get_learned_config(self, device: HostDevice) -> Optional[Dict[str, Any]]:

        """Get learned configuration for a device."""

        sig = self.get_device_signature(device)

        return self.learned_devices.get(sig)

    

    def generate_ai_query_for_device(self, device: HostDevice) -> str:

        """Generate a query for Ollama to learn about unknown device."""

        vid = device.capabilities.get("vid", 0)

        pid = device.capabilities.get("pid", 0)

        

        query = f"""I have connected an unknown device to my computer. Please help me understand how to control it.



Device Information:

- Name: {device.name}

- Category: {device.category.value}

- Vendor: {device.vendor or 'Unknown'}

- Product: {device.product or 'Unknown'}

- Port: {device.port or 'N/A'}

- VID:PID: {f'0x{vid:04X}:0x{pid:04X}' if vid and pid else 'N/A'}

- Description from system: {device.metadata.get('description', 'N/A')}



Please provide:

1. What type of device this is (e.g., microcontroller, sensor, instrument, etc.)

2. Common protocols/interfaces it uses (Serial, USB-HID, SCPI, etc.)

3. Typical baud rate if serial

4. List of controls/commands I can use with it

5. What data/readings it can provide



Format your response as JSON with this structure:

{{

    "device_type": "string",

    "protocol": "string", 

    "baud_rate": number or null,

    "controls": [

        {{"id": "string", "label": "string", "type": "slider|button|toggle|dropdown|number", "options": [], "min": 0, "max": 100}}

    ],

    "data_outputs": ["list of data types this device outputs"],

    "setup_instructions": "brief setup instructions",

    "common_commands": ["list of common commands if applicable"]

}}"""

        return query

    

    def parse_ai_response(self, response: str) -> Optional[Dict[str, Any]]:

        """Parse AI response to extract device configuration."""

        try:

            # Try to extract JSON from response

            import re

            json_match = re.search(r'\{[\s\S]*\}', response)

            if json_match:

                config = json.loads(json_match.group())

                return config

        except json.JSONDecodeError:

            pass

        except Exception as e:

            logger.debug(f"Could not parse AI response: {e}")

        return None

    

    def learn_device(self, device: HostDevice, ai_config: Dict[str, Any]) -> Dict[str, Any]:

        """Learn about a device from AI-provided configuration."""

        sig = self.get_device_signature(device)

        

        # Create chameleon panel from AI config

        panel_config = {

            "name": f"{ai_config.get('device_type', device.name)} Control",

            "icon": self._get_icon_for_type(ai_config.get('device_type', '')),

            "color": "#00d4ff",

            "os_style": "learned",

            "controls": ai_config.get("controls", []),

            "displays": self._generate_displays(ai_config),

            "protocol": ai_config.get("protocol", "unknown"),

            "baud_rate": ai_config.get("baud_rate"),

            "setup_instructions": ai_config.get("setup_instructions", ""),

            "common_commands": ai_config.get("common_commands", []),

            "learned_at": datetime.now().isoformat(),

            "device_info": {

                "name": device.name,

                "vendor": device.vendor,

                "vid": device.capabilities.get("vid"),

                "pid": device.capabilities.get("pid"),

            }

        }

        

        self.learned_devices[sig] = panel_config

        self._save_learned_devices()

        

        # Publish event for UI to update

        if self.event_bus:

            try:

                self.event_bus.publish("device.learned", {

                    "device_id": device.id,

                    "signature": sig,

                    "config": panel_config

                })

            except:

                pass

        

        logger.info(f"🎓 Learned new device: {device.name} -> {ai_config.get('device_type', 'Unknown')}")

        return panel_config

    

    def _get_icon_for_type(self, device_type: str) -> str:

        """Get appropriate icon for device type."""

        type_lower = device_type.lower()

        icons = {

            "microcontroller": "🔌", "arduino": "🔌", "esp": "📶",

            "sensor": "📡", "lidar": "📡", "radar": "📡",

            "oscilloscope": "📈", "multimeter": "🔢", "dmm": "🔢",

            "power supply": "⚡", "signal generator": "📊",

            "motor": "⚙️", "servo": "⚙️", "actuator": "⚙️",

            "camera": "📷", "gps": "🛰️", "radio": "📻",

            "can": "🚗", "obd": "🔧", "vehicle": "🚗",

            "drone": "🚁", "robot": "🤖", "arm": "🦾",

        }

        for key, icon in icons.items():

            if key in type_lower:

                return icon

        return "⚙️"

    

    def _generate_displays(self, ai_config: Dict[str, Any]) -> List[str]:

        """Generate display types based on device capabilities."""

        displays = ["status", "log"]

        outputs = ai_config.get("data_outputs", [])

        

        for output in outputs:

            output_lower = output.lower()

            if any(x in output_lower for x in ["voltage", "current", "temperature", "pressure", "speed"]):

                displays.append("gauge")

            if any(x in output_lower for x in ["waveform", "signal", "wave"]):

                displays.append("waveform_display")

            if any(x in output_lower for x in ["position", "gps", "location", "coordinate"]):

                displays.append("map_view")

            if any(x in output_lower for x in ["spectrum", "frequency", "fft"]):

                displays.append("spectrum_fft")

            if any(x in output_lower for x in ["point", "3d", "scan"]):

                displays.append("3d_pointcloud")

        

        return list(set(displays))

    

    def generate_mcp_tools_for_device(self, device: HostDevice, config: Dict[str, Any]) -> List[Dict[str, Any]]:

        """Generate MCP tools dynamically for a learned device."""

        tools = []

        device_name = config.get("name", device.name).lower().replace(" ", "_")

        

        # Add control tools

        for control in config.get("controls", []):

            ctrl_id = control.get("id", "unknown")

            ctrl_label = control.get("label", ctrl_id)

            ctrl_type = control.get("type", "button")

            

            tool = {

                "name": f"{device_name}_{ctrl_id}",

                "description": f"Control {ctrl_label} on {device.name}",

                "parameters": {"type": "object", "properties": {}}

            }

            

            if ctrl_type == "slider":

                tool["parameters"]["properties"]["value"] = {

                    "type": "number",

                    "description": f"Value for {ctrl_label}",

                    "minimum": control.get("min", 0),

                    "maximum": control.get("max", 100)

                }

            elif ctrl_type == "toggle":

                tool["parameters"]["properties"]["enabled"] = {

                    "type": "boolean",

                    "description": f"Enable/disable {ctrl_label}"

                }

            elif ctrl_type == "dropdown":

                tool["parameters"]["properties"]["option"] = {

                    "type": "string",

                    "description": f"Select option for {ctrl_label}",

                    "enum": control.get("options", [])

                }

            elif ctrl_type == "number":

                tool["parameters"]["properties"]["value"] = {

                    "type": "number",

                    "description": f"Value for {ctrl_label}"

                }

            

            tools.append(tool)

        

        # Add common command tools

        for cmd in config.get("common_commands", []):

            tools.append({

                "name": f"{device_name}_cmd_{cmd.lower().replace(' ', '_')[:20]}",

                "description": f"Execute '{cmd}' on {device.name}",

                "parameters": {"type": "object", "properties": {}}

            })

        

        return tools





# ============================================================================

# MCP TOOL DEFINITIONS - For AI integration

# ============================================================================



class HostDeviceMCPTools:

    """MCP-style tools for AI to interact with host devices"""

    

    def __init__(self, device_manager: HostDeviceManager):

        self.device_manager = device_manager

    

    def get_tools(self) -> List[Dict[str, Any]]:

        """Get list of available MCP tools.

        

        Returns:

            List of tool definitions

        """

        return [

            {

                "name": "list_devices",

                "description": "List all devices connected to the host system (USB, Bluetooth, audio, webcams, VR, LiDAR, CAN/OBD-II, microcontrollers, lab equipment, drones)",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "category": {

                            "type": "string",

                            "description": "Optional filter by category",

                            "enum": ["usb", "serial", "bluetooth", "audio_input", "audio_output", "webcam", "vr_headset", "sdr", "lidar", "can_interface", "obd2_adapter", "arduino", "esp32", "stm32", "teensy", "pico", "oscilloscope", "signal_generator", "dmm", "power_supply", "drone", "gps_receiver", "imu"]

                        }

                    }

                }

            },

            {

                "name": "scan_devices",

                "description": "Scan for newly connected devices on the host system",

                "parameters": {"type": "object", "properties": {}}

            },

            {

                "name": "find_device",

                "description": "Search for a device by name, vendor, or type",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "query": {

                            "type": "string",

                            "description": "Search term (device name, vendor, or type)"

                        }

                    },

                    "required": ["query"]

                }

            },

            {

                "name": "enable_device",

                "description": "Enable or connect a device",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID to enable"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "disable_device",

                "description": "Disable or disconnect a device",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID to disable"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "pair_device",

                "description": "Pair/connect a Bluetooth device (WinRT on Windows host when available)",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID to pair"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "get_device_info",

                "description": "Get detailed information about a specific device",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "learn_unknown_device",

                "description": "AI learns about an unknown device - generates query for Ollama to discover device info, creates control panel and MCP tools automatically",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The ID of the unknown device to learn about"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "get_device_controls",

                "description": "Get all controllable parts of a device for AI awareness - returns control IDs, types, ranges, and descriptions",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "Optional device ID, or empty for all devices"

                        }

                    }

                }

            },

            {

                "name": "get_chameleon_panel",

                "description": "Get the adaptive UI panel configuration for a device - returns controls, displays, colors styled for the device type",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID to get panel for"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "teach_device",

                "description": "Teach the system about a device by providing configuration - AI provides device info and system learns it",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID to teach about"

                        },

                        "device_type": {

                            "type": "string",

                            "description": "Type of device (e.g., 'microcontroller', 'sensor', 'oscilloscope')"

                        },

                        "protocol": {

                            "type": "string",

                            "description": "Communication protocol (e.g., 'Serial', 'USB-HID', 'SCPI')"

                        },

                        "baud_rate": {

                            "type": "number",

                            "description": "Baud rate for serial devices (optional)"

                        },

                        "controls": {

                            "type": "array",

                            "description": "List of controls for the device"

                        },

                        "commands": {

                            "type": "array",

                            "description": "List of common commands for the device"

                        }

                    },

                    "required": ["device_id", "device_type"]

                }

            },

            # SOTA 2026: Device Takeover MCP Tools

            {

                "name": "takeover_device",

                "description": "Take full control of a connected device - auto-connects, discovers capabilities, and enables command execution",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID to take over"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "send_device_command",

                "description": "Send a command to a taken-over device - use natural language and the system will translate to device commands",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID to send command to"

                        },

                        "command": {

                            "type": "string",

                            "description": "The command to send (natural language or device-specific)"

                        }

                    },

                    "required": ["device_id", "command"]

                }

            },

            {

                "name": "configure_device_wifi",

                "description": "Configure WiFi on a device (e.g., Particle in listening mode) - sets SSID and password",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID"

                        },

                        "ssid": {

                            "type": "string",

                            "description": "WiFi network name"

                        },

                        "password": {

                            "type": "string",

                            "description": "WiFi password"

                        },

                        "security": {

                            "type": "string",

                            "description": "Security type: open, wep, wpa, wpa2",

                            "default": "wpa2"

                        }

                    },

                    "required": ["device_id", "ssid", "password"]

                }

            },

            {

                "name": "list_taken_over_devices",

                "description": "List all devices currently under takeover control",

                "parameters": {"type": "object", "properties": {}}

            },

            {

                "name": "release_device",

                "description": "Release control of a taken-over device",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID to release"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "get_takeover_status",

                "description": "Get the takeover status and capabilities of a device",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            # SOTA 2026: Network Device Control MCP Tools (Xbox, PlayStation, PCs)

            {

                "name": "discover_network_devices",

                "description": "Discover network devices (Xbox, PlayStation, Windows PCs) on the local network",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_type": {

                            "type": "string",

                            "description": "Optional filter by device type",

                            "enum": ["xbox", "playstation", "windows_pc", "all"]

                        }

                    }

                }

            },

            {

                "name": "list_network_devices",

                "description": "List all discovered network devices (Xbox, PlayStation, PCs)",

                "parameters": {"type": "object", "properties": {}}

            },

            {

                "name": "connect_xbox",

                "description": "Connect to an Xbox console via SmartGlass protocol for controller-like control",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The Xbox device ID or IP address"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "xbox_send_input",

                "description": "Send controller input to Xbox (button press, joystick movement, etc.)",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The Xbox device ID"

                        },

                        "input_type": {

                            "type": "string",

                            "description": "Type of input",

                            "enum": ["button", "joystick", "trigger", "dpad"]

                        },

                        "input_value": {

                            "type": "string",

                            "description": "Input value (e.g., 'A', 'B', 'left_stick_up', 'dpad_right')"

                        }

                    },

                    "required": ["device_id", "input_type", "input_value"]

                }

            },

            {

                "name": "xbox_power_control",

                "description": "Control Xbox power state (power on/off)",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The Xbox device ID"

                        },

                        "action": {

                            "type": "string",

                            "description": "Power action",

                            "enum": ["power_on", "power_off"]

                        }

                    },

                    "required": ["device_id", "action"]

                }

            },

            {

                "name": "connect_playstation",

                "description": "Connect to a PlayStation console (PS4/PS5) via Remote Play for controller-like control",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The PlayStation device ID or IP address"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "playstation_send_input",

                "description": "Send controller input to PlayStation (button press, joystick movement, etc.)",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The PlayStation device ID"

                        },

                        "input_type": {

                            "type": "string",

                            "description": "Type of input",

                            "enum": ["button", "joystick", "trigger", "dpad"]

                        },

                        "input_value": {

                            "type": "string",

                            "description": "Input value (e.g., 'cross', 'circle', 'left_stick_up', 'dpad_down')"

                        }

                    },

                    "required": ["device_id", "input_type", "input_value"]

                }

            },

            {

                "name": "playstation_power_control",

                "description": "Control PlayStation power state (power on/off, standby)",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The PlayStation device ID"

                        },

                        "action": {

                            "type": "string",

                            "description": "Power action",

                            "enum": ["power_on", "power_off", "standby"]

                        }

                    },

                    "required": ["device_id", "action"]

                }

            },

            {

                "name": "connect_windows_pc",

                "description": "Connect to a Windows PC via WinRM/PowerShell for remote control",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The PC device ID or IP address"

                        },

                        "username": {

                            "type": "string",

                            "description": "Windows username"

                        },

                        "password": {

                            "type": "string",

                            "description": "Windows password"

                        }

                    },

                    "required": ["device_id", "username", "password"]

                }

            },

            {

                "name": "windows_pc_execute_command",

                "description": "Execute a PowerShell command on a remote Windows PC",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The PC device ID"

                        },

                        "command": {

                            "type": "string",

                            "description": "PowerShell command to execute"

                        }

                    },

                    "required": ["device_id", "command"]

                }

            },

            {

                "name": "create_virtual_gamepad",

                "description": "Create a virtual gamepad for injecting controller input into games/applications",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "gamepad_type": {

                            "type": "string",

                            "description": "Type of virtual gamepad",

                            "enum": ["xbox360", "dualshock4"]

                        }

                    },

                    "required": ["gamepad_type"]

                }

            },

            {

                "name": "virtual_gamepad_input",

                "description": "Send input to a virtual gamepad",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "gamepad_id": {

                            "type": "string",

                            "description": "The virtual gamepad ID"

                        },

                        "input_type": {

                            "type": "string",

                            "description": "Type of input",

                            "enum": ["button", "joystick", "trigger", "dpad"]

                        },

                        "input_value": {

                            "type": "string",

                            "description": "Input value"

                        }

                    },

                    "required": ["gamepad_id", "input_type", "input_value"]

                }

            },

            {

                "name": "disconnect_network_device",

                "description": "Disconnect from a network device (Xbox, PlayStation, PC)",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID to disconnect"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "get_network_device_status",

                "description": "Get the connection status and capabilities of a network device",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_id": {

                            "type": "string",

                            "description": "The device ID"

                        }

                    },

                    "required": ["device_id"]

                }

            },

            {

                "name": "auto_setup_network_devices",

                "description": "Automatically install missing dependencies and setup network device control",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "device_types": {

                            "type": "array",

                            "description": "Device types to setup (xbox, playstation, windows_pc, virtual_gamepad)",

                            "items": {

                                "type": "string",

                                "enum": ["xbox", "playstation", "windows_pc", "virtual_gamepad"]

                            }

                        },

                        "auto_install": {

                            "type": "boolean",

                            "description": "Automatically install missing dependencies",

                            "default": true

                        }

                    }

                }

            },

            {

                "name": "setup_pc_winrm",

                "description": "Setup WinRM on a Windows PC for remote control",

                "parameters": {

                    "type": "object",

                    "properties": {

                        "pc_ip": {

                            "type": "string",

                            "description": "IP address of the Windows PC"

                        },

                        "username": {

                            "type": "string",

                            "description": "Windows username"

                        },

                        "password": {

                            "type": "string",

                            "description": "Windows password"

                        }

                    },

                    "required": ["pc_ip", "username", "password"]

                }

            }

        ]

    

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:

        """Execute an MCP tool.

        

        Args:

            tool_name: Name of the tool

            parameters: Tool parameters

            

        Returns:

            Tool result

        """

        try:

            if tool_name == "list_devices":

                category = parameters.get("category")

                if category:

                    devices = self.device_manager.get_devices_by_category(DeviceCategory(category))

                else:

                    devices = self.device_manager.get_all_devices()

                return {

                    "success": True,

                    "devices": [d.to_dict() for d in devices],

                    "count": len(devices)

                }

            

            elif tool_name == "scan_devices":

                results = self.device_manager.scan_all_devices()

                return {

                    "success": True,

                    "summary": self.device_manager.get_summary()

                }

            

            elif tool_name == "find_device":

                query = parameters.get("query", "")

                devices = self.device_manager.find_devices(query)

                return {

                    "success": True,

                    "devices": [d.to_dict() for d in devices],

                    "count": len(devices)

                }

            

            elif tool_name == "enable_device":

                device_id = parameters.get("device_id", "")

                success = self.device_manager.enable_device(device_id)

                return {"success": success, "device_id": device_id}

            

            elif tool_name == "disable_device":

                device_id = parameters.get("device_id", "")

                success = self.device_manager.disable_device(device_id)

                return {"success": success, "device_id": device_id}



            elif tool_name == "pair_device":

                device_id = parameters.get("device_id", "")

                success = self.device_manager.enable_device(device_id)

                return {"success": success, "device_id": device_id}

            

            elif tool_name == "get_device_info":

                device_id = parameters.get("device_id", "")

                device = self.device_manager.get_device_by_id(device_id)

                if device:

                    return {"success": True, "device": device.to_dict()}

                else:

                    return {"success": False, "error": f"Device not found: {device_id}"}

            

            elif tool_name == "learn_unknown_device":

                device_id = parameters.get("device_id", "")

                device = self.device_manager.get_device_by_id(device_id)

                if not device:

                    return {"success": False, "error": f"Device not found: {device_id}"}

                

                # Initialize learning system

                learner = DeviceLearningSystem(self.device_manager.event_bus)

                

                # Check if already learned

                if learner.is_device_learned(device):

                    config = learner.get_learned_config(device)

                    return {

                        "success": True,

                        "already_learned": True,

                        "config": config,

                        "message": f"Device '{device.name}' was previously learned"

                    }

                

                # Generate AI query for Ollama to learn about this device

                ai_query = learner.generate_ai_query_for_device(device)

                

                return {

                    "success": True,

                    "action_required": "ai_query",

                    "device_id": device_id,

                    "device_info": device.to_dict(),

                    "ai_query": ai_query,

                    "instructions": "Send this query to Ollama, then call 'teach_device' with the response to complete learning"

                }

            

            elif tool_name == "get_device_controls":

                device_id = parameters.get("device_id", "")

                controls = self.device_manager.get_device_controls_for_ai(device_id if device_id else None)

                return {"success": True, **controls}

            

            elif tool_name == "get_chameleon_panel":

                device_id = parameters.get("device_id", "")

                panel = self.device_manager.get_chameleon_panel_for_device(device_id)

                return {"success": True, "panel": panel}

            

            elif tool_name == "teach_device":

                device_id = parameters.get("device_id", "")

                device = self.device_manager.get_device_by_id(device_id)

                if not device:

                    return {"success": False, "error": f"Device not found: {device_id}"}

                

                # Build AI config from parameters

                ai_config = {

                    "device_type": parameters.get("device_type", "Unknown"),

                    "protocol": parameters.get("protocol", "Unknown"),

                    "baud_rate": parameters.get("baud_rate"),

                    "controls": parameters.get("controls", []),

                    "data_outputs": parameters.get("data_outputs", []),

                    "setup_instructions": parameters.get("setup_instructions", ""),

                    "common_commands": parameters.get("commands", [])

                }

                

                # Learn the device

                learner = DeviceLearningSystem(self.device_manager.event_bus)

                panel_config = learner.learn_device(device, ai_config)

                

                # Generate MCP tools for this device

                new_tools = learner.generate_mcp_tools_for_device(device, panel_config)

                

                return {

                    "success": True,

                    "message": f"Successfully learned device: {device.name}",

                    "panel_config": panel_config,

                    "new_mcp_tools": new_tools,

                    "tools_count": len(new_tools)

                }

            

            # SOTA 2026: Device Takeover Tool Handlers

            elif tool_name == "takeover_device":

                device_id = parameters.get("device_id", "")

                device = self.device_manager.get_device_by_id(device_id)

                if not device:

                    return {"success": False, "error": f"Device not found: {device_id}"}

                

                takeover_mgr = self.device_manager._takeover_manager

                if takeover_mgr.is_device_taken_over(device_id):

                    info = takeover_mgr.get_takeover_info(device_id)

                    return {

                        "success": True,

                        "already_taken_over": True,

                        "message": f"Device '{device.name}' is already under control",

                        "takeover_info": info

                    }

                

                initiated = takeover_mgr.auto_takeover_device(device)

                return {

                    "success": initiated,

                    "message": f"Takeover {'initiated' if initiated else 'skipped'} for {device.name}",

                    "device_id": device_id

                }

            

            elif tool_name == "send_device_command":

                device_id = parameters.get("device_id", "")

                command = parameters.get("command", "")

                

                takeover_mgr = self.device_manager._takeover_manager

                result = takeover_mgr.send_device_command(device_id, command)

                return result

            

            elif tool_name == "configure_device_wifi":

                device_id = parameters.get("device_id", "")

                ssid = parameters.get("ssid", "")

                password = parameters.get("password", "")

                security = parameters.get("security", "wpa2")

                

                takeover_mgr = self.device_manager._takeover_manager

                result = takeover_mgr.configure_device_wifi(device_id, ssid, password, security)

                return result

            

            elif tool_name == "list_taken_over_devices":

                takeover_mgr = self.device_manager._takeover_manager

                devices = takeover_mgr.get_all_taken_over_devices()

                return {

                    "success": True,

                    "devices": devices,

                    "count": len(devices)

                }

            

            elif tool_name == "release_device":

                device_id = parameters.get("device_id", "")

                takeover_mgr = self.device_manager._takeover_manager

                released = takeover_mgr.release_device(device_id)

                return {

                    "success": released,

                    "message": f"Device {'released' if released else 'not found'}: {device_id}"

                }

            

            elif tool_name == "get_takeover_status":

                device_id = parameters.get("device_id", "")

                takeover_mgr = self.device_manager._takeover_manager

                

                is_taken_over = takeover_mgr.is_device_taken_over(device_id)

                in_progress = takeover_mgr.is_takeover_in_progress(device_id)

                info = takeover_mgr.get_takeover_info(device_id)

                

                return {

                    "success": True,

                    "device_id": device_id,

                    "is_taken_over": is_taken_over,

                    "takeover_in_progress": in_progress,

                    "takeover_info": info

                }

            

            # SOTA 2026: Network Device Control Tool Handlers

            elif tool_name == "discover_network_devices":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_type = parameters.get("device_type", "all")

                discovered = self.device_manager._network_controller.discover_devices(device_type)

                return {

                    "success": True,

                    "discovered_devices": discovered,

                    "count": len(discovered)

                }

            

            elif tool_name == "list_network_devices":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                devices = self.device_manager._network_controller.get_all_devices()

                return {

                    "success": True,

                    "devices": devices,

                    "count": len(devices)

                }

            

            elif tool_name == "connect_xbox":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                result = self.device_manager._network_controller.connect_xbox(device_id)

                return result

            

            elif tool_name == "xbox_send_input":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                input_type = parameters.get("input_type", "")

                input_value = parameters.get("input_value", "")

                

                result = self.device_manager._network_controller.xbox_send_input(

                    device_id, input_type, input_value

                )

                return result

            

            elif tool_name == "xbox_power_control":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                action = parameters.get("action", "")

                

                result = self.device_manager._network_controller.xbox_power_control(

                    device_id, action

                )

                return result

            

            elif tool_name == "connect_playstation":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                result = self.device_manager._network_controller.connect_playstation(device_id)

                return result

            

            elif tool_name == "playstation_send_input":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                input_type = parameters.get("input_type", "")

                input_value = parameters.get("input_value", "")

                

                result = self.device_manager._network_controller.playstation_send_input(

                    device_id, input_type, input_value

                )

                return result

            

            elif tool_name == "playstation_power_control":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                action = parameters.get("action", "")

                

                result = self.device_manager._network_controller.playstation_power_control(

                    device_id, action

                )

                return result

            

            elif tool_name == "connect_windows_pc":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                username = parameters.get("username", "")

                password = parameters.get("password", "")

                

                # First try to setup WinRM if needed

                setup_result = self.device_manager._network_controller.windows_controller.setup_winrm_on_pc(

                    device_id, username, password

                )

                

                if setup_result.get("setup_needed"):

                    return setup_result

                

                # If setup not needed, try to connect

                result = self.device_manager._network_controller.connect_windows_pc(

                    device_id, username, password

                )

                return result

            

            elif tool_name == "windows_pc_execute_command":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                command = parameters.get("command", "")

                

                result = self.device_manager._network_controller.windows_pc_execute_command(

                    device_id, command

                )

                return result

            

            elif tool_name == "create_virtual_gamepad":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                gamepad_type = parameters.get("gamepad_type", "xbox360")

                result = self.device_manager._network_controller.create_virtual_gamepad(gamepad_type)

                return result

            

            elif tool_name == "virtual_gamepad_input":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                gamepad_id = parameters.get("gamepad_id", "")

                input_type = parameters.get("input_type", "")

                input_value = parameters.get("input_value", "")

                

                result = self.device_manager._network_controller.virtual_gamepad_input(

                    gamepad_id, input_type, input_value

                )

                return result

            

            elif tool_name == "disconnect_network_device":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                result = self.device_manager._network_controller.disconnect_device(device_id)

                return result

            

            elif tool_name == "get_network_device_status":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_id = parameters.get("device_id", "")

                result = self.device_manager._network_controller.get_device_status(device_id)

                return result

            

            elif tool_name == "auto_setup_network_devices":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                device_types = parameters.get("device_types", ["xbox", "playstation", "windows_pc", "virtual_gamepad"])

                auto_install = parameters.get("auto_install", True)

                

                setup_results = {}

                

                # Setup Xbox SmartGlass

                if "xbox" in device_types:

                    if not self.device_manager._network_controller.xbox_controller.smartglass_available:

                        if auto_install:

                            logger.info("🔄 Auto-installing Xbox SmartGlass...")

                            self.device_manager._network_controller.xbox_controller._auto_install_xbox_smartglass()

                        setup_results["xbox"] = {

                            "available": self.device_manager._network_controller.xbox_controller.smartglass_available,

                            "message": "Xbox SmartGlass setup completed" if self.device_manager._network_controller.xbox_controller.smartglass_available else "Xbox SmartGlass setup failed"

                        }

                    else:

                        setup_results["xbox"] = {"available": True, "message": "Xbox SmartGlass already available"}

                

                # Setup PlayStation Remote Play

                if "playstation" in device_types:

                    if not self.device_manager._network_controller.playstation_controller.remoteplay_available:

                        if auto_install:

                            logger.info("🔄 Auto-installing PlayStation Remote Play...")

                            self.device_manager._network_controller.playstation_controller._auto_install_pyremoteplay()

                        setup_results["playstation"] = {

                            "available": self.device_manager._network_controller.playstation_controller.remoteplay_available,

                            "message": "PlayStation Remote Play setup completed" if self.device_manager._network_controller.playstation_controller.remoteplay_available else "PlayStation Remote Play setup failed"

                        }

                    else:

                        setup_results["playstation"] = {"available": True, "message": "PlayStation Remote Play already available"}

                

                # Setup Windows PC Control

                if "windows_pc" in device_types:

                    if not self.device_manager._network_controller.windows_controller.winrm_available:

                        if auto_install:

                            logger.info("🔄 Auto-installing Windows Remote Management...")

                            self.device_manager._network_controller.windows_controller._auto_install_pywinrm()

                        setup_results["windows_pc"] = {

                            "available": self.device_manager._network_controller.windows_controller.winrm_available,

                            "message": "Windows Remote Management setup completed" if self.device_manager._network_controller.windows_controller.winrm_available else "Windows Remote Management setup failed"

                        }

                    else:

                        setup_results["windows_pc"] = {"available": True, "message": "Windows Remote Management already available"}

                

                # Setup Virtual Gamepad

                if "virtual_gamepad" in device_types:

                    if not self.device_manager._network_controller.gamepad_controller.vigem_available:

                        if auto_install:

                            logger.info("🔄 Auto-installing Virtual Gamepad...")

                            self.device_manager._network_controller.gamepad_controller._auto_install_vgamepad()

                        setup_results["virtual_gamepad"] = {

                            "available": self.device_manager._network_controller.gamepad_controller.vigem_available,

                            "message": "Virtual Gamepad setup completed" if self.device_manager._network_controller.gamepad_controller.vigem_available else "Virtual Gamepad setup failed"

                        }

                    else:

                        setup_results["virtual_gamepad"] = {"available": True, "message": "Virtual Gamepad already available"}

                

                return {

                    "success": True,

                    "setup_results": setup_results,

                    "message": "Network device setup completed"

                }

            

            elif tool_name == "setup_pc_winrm":

                if not self.device_manager._network_controller:

                    return {"success": False, "error": "Network device controller not available"}

                

                pc_ip = parameters.get("pc_ip", "")

                username = parameters.get("username", "")

                password = parameters.get("password", "")

                

                result = self.device_manager._network_controller.windows_controller.setup_winrm_on_pc(

                    pc_ip, username, password

                )

                return result

            

            else:

                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        

        except Exception as e:

            logger.error(f"Tool execution error: {e}")

            return {"success": False, "error": str(e)}





# ============================================================================

# CLI TEST

# ============================================================================



if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    

    print("\n" + "="*70)

    print(" HOST DEVICE MANAGER TEST ".center(70))

    print("="*70 + "\n")

    

    manager = get_host_device_manager()

    results = manager.scan_all_devices()

    

    summary = manager.get_summary()

    print(f"\n📊 Device Summary:")

    print(f"   Total devices: {summary['total_devices']}")

    for cat, count in summary['categories'].items():

        if count > 0:

            print(f"   {cat}: {count}")

    

    print("\n📋 All Devices:")

    for device in manager.get_all_devices():

        status_icon = "✅" if device.status == DeviceStatus.CONNECTED else "⚪"

        print(f"   {status_icon} [{device.category.value}] {device.name}")

    

    print("\n" + "="*70 + "\n")

