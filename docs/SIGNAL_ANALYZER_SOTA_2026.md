# Universal Signal Analyzer & Device Control - SOTA 2026

## Overview

The Universal Signal Analyzer provides comprehensive wireless signal scanning, protocol analysis, and device takeover capabilities for Kingdom AI. This system allows you to detect, analyze, and control wireless devices you own.

## Components

### 1. Core Service: `core/signal_analyzer.py`

**Purpose:** Universal wireless signal detection, analysis, and device control.

**Signal Types Supported:**
- **Bluetooth**: Classic (2.4 GHz), BLE
- **WiFi**: 2.4/5/6 GHz bands
- **IoT**: Zigbee, Z-Wave, LoRa, Thread, Matter
- **Short Range**: NFC, RFID (LF/HF/UHF), Infrared
- **RC Toys**: 27 MHz, 49 MHz, 72 MHz, 75 MHz, 2.4 GHz, 5.8 GHz FPV
- **Industrial**: 400-470 MHz crane/hoist, gate openers
- **Agricultural**: 900 MHz, LoRa-based equipment
- **Marine**: VHF (156-162 MHz), AIS
- **Automotive**: TPMS, key fobs, garage doors
- **Aviation**: GPS (L1/L2), ADS-B

**Key Classes:**
- `UniversalSignalAnalyzer`: Main orchestrator
- `BluetoothScanner`: BT Classic + BLE scanning
- `WiFiScanner`: WiFi network detection
- `RFSignalScanner`: SDR-based RF scanning
- `NFCRFIDScanner`: NFC/RFID tag detection
- `IRScanner`: IR remote learning/replay
- `StealthMode`: Anti-detection capabilities
- `DeviceTakeoverSystem`: Device control learning
- `SignalAnalyzerMCPTools`: AI tool integration

### 2. Secure Communications: `core/secure_comms.py`

**Purpose:** Military-grade encrypted radio communications.

**Encryption:**
- AES-256-GCM (FIPS 140-2 compliant)
- ChaCha20-Poly1305 (modern, fast)
- Automatic IV rotation (5-minute intervals)
- HKDF key derivation

**Voice Compression:**
- Codec2 (1.6 kbps for narrow-band radio)
- AFSK modulation for analog radio

## Usage

### Python API

```python
from core.signal_analyzer import get_signal_analyzer

# Get singleton instance
analyzer = get_signal_analyzer(event_bus)

# Scan for all signals
import asyncio
results = asyncio.run(analyzer.full_scan())

# Enable stealth mode
analyzer.stealth.enable("paranoid")

# Discover RC toys
signals = analyzer.takeover.discover_device("rc_car")

# Learn controls from original controller
profile = analyzer.takeover.learn_controls(signal, ["forward", "back", "left", "right"])

# Take over device
analyzer.takeover.takeover(device_id)

# Send command
analyzer.takeover.send_command(device_id, "forward")
```

### Chat Commands (via ThothAI)

**Signal Scanning:**
- "scan for signals" / "scan bluetooth"
- "scan for wifi networks"
- "scan for RC toys"
- "scan industrial equipment"
- "scan marine equipment"

**Device Discovery:**
- "discover rc car"
- "discover bluetooth devices"
- "find my rc plane"

**Stealth Mode:**
- "enable stealth mode"
- "set stealth to paranoid"
- "disable stealth"

**Device Control:**
- "learn controls for my rc car"
- "takeover device [id]"
- "send forward to rc car"

**Secure Communications:**
- "encrypt message [text]"
- "create encryption key"
- "emergency broadcast"

## MCP Tools

### Signal Analyzer Tools

| Tool | Description |
|------|-------------|
| `scan_signals` | Scan for wireless signals (BT/WiFi/RF/NFC/RC) |
| `discover_devices` | Discover devices of specific type |
| `analyze_protocol` | Analyze modulation, encoding, timing |
| `learn_device_controls` | Capture commands from original controller |
| `takeover_device` | Enable control of owned device |
| `send_device_command` | Send learned command |
| `set_stealth_mode` | Enable/disable anti-detection |
| `scan_industrial_equipment` | Scan cranes, hoists, gates |
| `scan_agricultural_equipment` | Scan tractors, harvesters |
| `scan_marine_equipment` | Scan boats, AIS |
| `capture_signal` | Capture raw RF signal |
| `replay_signal` | Replay captured signal (TX SDR required) |
| `get_detected_devices` | List all detected signals |
| `get_takeover_profiles` | List learned device profiles |
| `learn_ir_remote` | Learn IR remote buttons |
| `send_ir_command` | Transmit IR code |

### Secure Communications Tools

| Tool | Description |
|------|-------------|
| `encrypt_broadcast` | Encrypt message with AES-256-GCM |
| `decrypt_broadcast` | Decrypt received message |
| `create_broadcast_key` | Generate new encryption key |
| `emergency_broadcast` | Encrypted emergency with GPS |
| `share_encryption_key` | Export key for trusted contacts |

## Hardware Requirements

### Minimum (Basic Scanning)
- Built-in WiFi adapter
- Built-in Bluetooth adapter

### Recommended (Full Capabilities)
- **RTL-SDR** ($25-40): Receive-only, 24 MHz - 1.7 GHz
- **HackRF One** ($300): TX/RX, 1 MHz - 6 GHz
- **PN532 NFC Reader** ($15): NFC/RFID
- **IR Receiver/Transmitter** ($5): IR remote control

### Optional
- **BladeRF**: Higher quality SDR
- **YARD Stick One**: Sub-GHz attacks
- **Proxmark3**: Advanced RFID

## Stealth Mode Levels

| Level | Features |
|-------|----------|
| `passive` | Listen-only, no transmissions |
| `standard` | + Randomized timing, low power |
| `paranoid` | + MAC spoofing, longer delays (0.5-2s) |

## Frequency Reference

### Consumer RC Toys
| Band | Frequency | Notes |
|------|-----------|-------|
| 27 MHz | 26.995-27.255 MHz | Classic RC cars |
| 49 MHz | 49.830-49.890 MHz | Older toys |
| 72 MHz | 72.01-72.99 MHz | RC aircraft (USA) |
| 75 MHz | 75.41-75.99 MHz | RC surface (USA) |
| 2.4 GHz | 2.400-2.483 GHz | Modern FHSS/DSSS |
| 5.8 GHz | 5.65-5.925 GHz | FPV video |

### Industrial/Agricultural
| Type | Frequency |
|------|-----------|
| Crane/Hoist | 400-470 MHz |
| Gate Openers | 300-400 MHz |
| Agricultural | 902-928 MHz |
| European Industrial | 868 MHz |

### Automotive
| Device | Frequency |
|--------|-----------|
| US Key Fobs | 315 MHz |
| EU Key Fobs | 433.92 MHz |
| TPMS | 315/433 MHz |
| Garage Doors | 300-400 MHz |

## Event Bus Integration

The system publishes events:
- `signals.scan.complete` - Scan finished
- `signals.device.discovered` - New device found
- `signals.takeover.ready` - Device ready to control
- `signals.command.sent` - Command transmitted

Subscribe example:
```python
event_bus.subscribe('signals.scan.complete', handle_scan_complete)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Kingdom AI GUI                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ThothAI Chat (natural language commands)           │    │
│  └────────────────────────┬────────────────────────────┘    │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│               ThothMCPBridge (ai/thoth_mcp.py)              │
│  - Signal command pattern matching                          │
│  - MCP tool execution                                       │
│  - Response formatting                                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│        UniversalSignalAnalyzer (core/signal_analyzer.py)    │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐  │
│  │ BluetoothScanner│ │  WiFiScanner   │ │ RFSignalScanner│  │
│  └────────────────┘ └────────────────┘ └────────────────┘  │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐  │
│  │  NFCRFIDScanner │ │   IRScanner    │ │  StealthMode   │  │
│  └────────────────┘ └────────────────┘ └────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         DeviceTakeoverSystem                        │   │
│  │  - discover_device()  - analyze_protocol()          │   │
│  │  - learn_controls()   - takeover()                  │   │
│  │  - send_command()     - save/load_profiles()        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│           SecureBroadcast (core/secure_comms.py)            │
│  - AES-256-GCM / ChaCha20-Poly1305 encryption              │
│  - Codec2 voice compression                                 │
│  - Key management with HKDF                                 │
│  - Emergency broadcast with GPS                             │
└─────────────────────────────────────────────────────────────┘
```

## Testing

### Quick CLI test:
```bash
cd "c:\Users\Yeyian PC\Documents\Python Scripts\New folder"
python -c "from core.signal_analyzer import get_signal_analyzer; a = get_signal_analyzer(); print(a.wifi.scan())"
```

### Full test:
```bash
python core/signal_analyzer.py
```

### AI test:
In the Thoth AI chat, type: "scan for signals" or "discover rc car"

## Legal Notice

**IMPORTANT:** The device takeover features are intended ONLY for devices you legally own. Using these capabilities on devices you do not own may violate local laws. Always ensure you have proper authorization before analyzing or controlling any wireless device.

## Version History

- **v1.0.0** (Jan 2026): Initial implementation
  - Universal signal scanning (BT, WiFi, RF, NFC, IR)
  - RC toy protocol analysis (27/49/72/75 MHz, 2.4/5.8 GHz)
  - Industrial/Agricultural/Marine equipment scanning
  - Anti-detection stealth mode
  - Device takeover for owned devices
  - AES-256-GCM/ChaCha20 secure communications
  - MCP tool integration
  - Chat command support
