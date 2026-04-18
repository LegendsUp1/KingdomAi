# Host Device MCP Integration for Kingdom AI

## Overview

This document describes the Host Device Detection & MCP Integration system that allows Kingdom AI to detect and control host system devices (USB, Bluetooth, Audio, Webcams, VR) through both GUI controls and AI chat commands.

## Components

### 1. Core Service: `core/host_device_manager.py`

**Purpose:** Unified service for detecting and managing all host system devices.

**Device Categories:**
- USB devices (hubs, peripherals)
- Serial/COM ports (Arduino, microcontrollers)
- Bluetooth devices (speakers, headphones, controllers)
- Audio input (microphones)
- Audio output (speakers, headphones)
- Webcams/video capture
- VR headsets (Meta Quest via ADB, OpenXR)

**Key Classes:**
- `HostDevice`: Normalized device data model
- `DeviceCategory`, `DeviceStatus`: Enums for categorization
- `HostDeviceManager`: Main service with scanning, monitoring, enable/disable
- `HostDeviceMCPTools`: MCP tool definitions for AI integration

**Usage:**
```python
from core.host_device_manager import get_host_device_manager

# Get singleton instance
manager = get_host_device_manager(event_bus)

# Scan all devices
results = manager.scan_all_devices()

# Get devices by category
bluetooth_devices = manager.get_devices_by_category(DeviceCategory.BLUETOOTH)

# Find device by name
webcams = manager.find_devices("webcam")

# Enable/disable
manager.enable_device(device_id)
manager.disable_device(device_id)
```

### 2. GUI Tab: `gui/qt_frames/device_manager_tab.py`

**Purpose:** PyQt6 tab with cyberpunk styling for device management.

**Features:**
- Device tree organized by category
- Real-time status indicators (✅ Connected, ⚪ Disconnected, etc.)
- Search and filter controls
- Connect/Disconnect buttons
- Auto-refresh monitoring toggle
- Detailed device info panel

### 3. AI Integration: `ai/thoth_mcp.py` (extended)

**Purpose:** ThothMCPBridge now includes device detection tools.

**Natural Language Commands:**
- "list devices" / "show all devices"
- "scan for devices"
- "what devices are connected?"
- "connect the [device name]"
- "disconnect the [device name]"
- "show info about [device]"
- "is my [device] connected?"
- "list bluetooth devices" / "show webcams"

**MCP Tools:**
- `list_devices` - List all or filtered devices
- `scan_devices` - Scan for new devices
- `find_device` - Search by query
- `enable_device` - Connect/enable device
- `disable_device` - Disconnect/disable device
- `get_device_info` - Get detailed device info

## Dependencies

### Required (Windows)
- PowerShell (for WMI queries)
- PyQt6 (GUI)

### Optional (enhanced detection)
- `pyserial` - Better serial port detection
- `sounddevice` - Detailed audio device info
- `opencv-python` - Webcam capability detection
- `adb` - Meta Quest detection (ADB in PATH)

### Install optional dependencies:
```bash
pip install pyserial sounddevice opencv-python
```

## Event Bus Integration

The system publishes events on device changes:
- `device.connected` - New device connected
- `device.disconnected` - Device disconnected
- `device.enabled` - Device enabled by user
- `device.disabled` - Device disabled by user

Subscribe example:
```python
event_bus.subscribe('device.connected', handle_device_connected)
```

## Configuration

No configuration file required. The system auto-detects devices using platform-specific APIs.

For VR/Quest detection, ensure:
1. ADB is installed and in PATH
2. Quest device is in developer mode
3. USB debugging is enabled on Quest

## Testing

### Quick CLI test:
```bash
cd "c:\Users\Yeyian PC\Documents\Python Scripts\New folder"
python -c "from core.host_device_manager import get_host_device_manager; m = get_host_device_manager(); print(m.scan_all_devices())"
```

### GUI test:
Launch Kingdom AI and navigate to the "🔌 Devices" tab.

### AI test:
In the Thoth AI chat, type: "list devices" or "scan for devices"

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Kingdom AI GUI                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  DeviceManagerTab (gui/qt_frames/device_manager_tab.py) │
│  │  - Device tree view                                     │
│  │  - Controls (scan, connect, disconnect)                 │
│  │  - Status display                                       │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│  ┌────────────────────────▼────────────────────────────┐    │
│  │  ThothAITab (chat integration)                      │    │
│  │  - Natural language device commands                 │    │
│  │  - Routed through ThothMCPBridge                    │    │
│  └────────────────────────┬────────────────────────────┘    │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│               ThothMCPBridge (ai/thoth_mcp.py)              │
│  - Device command pattern matching                          │
│  - MCP tool execution                                       │
│  - Response formatting                                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│           HostDeviceManager (core/host_device_manager.py)   │
│  - Platform-specific detection (Windows WMI/PowerShell)     │
│  - Normalized device model                                  │
│  - Event bus publishing                                     │
│  - Device enable/disable                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  HostDeviceMCPTools                                 │    │
│  │  - Tool definitions for AI                          │    │
│  │  - Tool execution                                   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

**No devices detected:**
- Ensure PowerShell is available
- Run as administrator for full device access
- Check Windows Device Manager for comparison

**Bluetooth devices not showing:**
- Ensure Bluetooth is enabled in Windows
- Pair devices through Windows Settings first

**VR/Quest not detected:**
- Install ADB: `scoop install adb` or from Android SDK
- Enable USB debugging on Quest
- Accept RSA key prompt on Quest

**Audio devices missing:**
- Install `sounddevice`: `pip install sounddevice`
- Check Windows Sound settings

## Version History

- **v1.0.0** (2025): Initial implementation with Windows support
  - USB, Serial, Bluetooth, Audio, Webcam, VR detection
  - GUI tab with cyberpunk styling
  - AI integration via ThothMCPBridge
  - MCP tool exposure
