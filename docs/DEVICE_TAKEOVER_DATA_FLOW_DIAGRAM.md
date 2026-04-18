# Device Takeover Data Flow Diagrams

## 1. Serial/USB Takeover Flow (FULLY IMPLEMENTED)

```mermaid
flowchart TD
    A[Physical Device Connected] --> B[Windows Host Bridge]
    B --> C[Device Enumeration]
    C --> D{Known Device?}
    D -->|Yes| E[DeviceTakeoverManager]
    D -->|No| F[Log Unknown Device]
    E --> G[Create HostDevice Object]
    G --> H[Publish device.connected Event]
    H --> I[Takeover Worker Started]
    I --> J[Serial Connection Attempt]
    J --> K{Connected?}
    K -->|No| L[Try Different Baud Rates]
    L --> J
    K -->|Yes| M[Detect Device Type]
    M --> N{Particle Device?}
    N -->|Yes| O{Listening Mode?}
    N -->|No| P[Generic Serial Control]
    O -->|Yes| Q[Configure WiFi]
    O -->|No| R{Firmware Responding?}
    Q --> S[Exit Listening Mode]
    S --> R
    R -->|No| T[Trigger DFU Mode]
    T --> U[Compile Firmware Docker]
    U --> V[Flash via dfu-util]
    V --> W[Verify Firmware]
    W --> X[Takeover Complete]
    R -->|Yes| X
    P --> Y[Discover Capabilities]
    Y --> X
    X --> Z[Publish takeover.complete Event]
    Z --> AA[AI Brain Integration]
    AA --> AB[Natural Language Control]
```

## 2. Event Bus Data Flow

```mermaid
flowchart LR
    A[DeviceTakeoverManager] -->|device.connected| B[EventBus]
    C[WindowsHostBridge] -->|device.disconnected| B
    D[DeviceTakeoverSystem] -->|device.takeover.progress| B
    E[AI Brain] -->|device.command.sent| B
    F[UniversalFlasher] -->|device.flash.complete| B
    B --> G[Event History Buffer]
    B --> H[Component Subscribers]
    H --> I[GUI Updates]
    H --> J[Logbook Persistence]
    H --> K[AI Learning System]
```

## 3. Particle DFU Flashing Flow

```mermaid
flowchart TD
    A[Particle Device Detected] --> B{Firmware Ready?}
    B -->|No| C[Trigger DFU Mode]
    B -->|Yes| D[Normal Operation]
    C --> E[1200 Baud Touch]
    E --> F[DFU Device Detected?]
    F -->|No| G[Manual DFU Instructions]
    F -->|Yes| H[Determine Platform ID]
    H --> I[Select Flash Address]
    I --> J[Compile Firmware in Docker]
    J --> K[firmware/kingdom_firmware.bin]
    K --> L[Flash with dfu-util]
    L --> M{Flash Success?}
    M -->|No| N[Error Recovery]
    M -->|Yes| O[Verify via Serial]
    O --> P{Kingdom Firmware?}
    P -->|No| Q[Retry Flash]
    P -->|Yes| D
```

## 4. Windows Host Bridge Architecture

```mermaid
flowchart TB
    A[WSL2 Kingdom AI] --> B[WindowsHostBridge]
    B --> C[PowerShell Interface]
    C --> D[Windows Hardware APIs]
    D --> E[Serial Port Enumeration]
    D --> F[USB Device Enumeration]
    D --> G[Bluetooth Discovery]
    D --> H[Audio/Video Devices]
    E --> I[COM Port Access]
    F --> J[VID/PID Mapping]
    G --> K[BLE Scanning]
    H --> L[Device Capabilities]
    I --> M[Serial Communication]
    J --> N[Device Classification]
    K --> O[Bluetooth Services]
    L --> P[Multimedia Access]
```

## 5. AI Brain Integration Flow

```mermaid
flowchart TD
    A[User Natural Language] --> B[AI Brain Thoth/Ollama]
    B --> C[Parse Command Intent]
    C --> D{Device Type?}
    D -->|Particle| E[Particle Protocol]
    D -->|Arduino| F[Arduino Protocol]
    D -->|Generic| G[Generic Serial]
    E --> H[Generate Serial Command]
    F --> H
    G --> H
    H --> I[WindowsHostBridge]
    I --> J[Serial Transmission]
    J --> K[Device Response]
    K --> L[Parse Response]
    L --> M[Natural Language Feedback]
    M --> N[User Display]
```

## 6. Test Architecture Flow

```mermaid
flowchart TD
    A[Test Runner] --> B{Live Hardware?}
    B -->|Yes| C[WindowsHostBridge]
    B -->|No| D[Mock/Stubs]
    C --> E[Real Device Detection]
    E --> F[Actual Takeover]
    F --> G[Real Event Publishing]
    D --> H[Simulated Devices]
    H --> I[Mock Takeover]
    I --> J[Simulated Events]
    G --> K[Test Results]
    J --> K
    K --> L[Coverage Report]
```

## 7. Knowledge Base Learning Flow

```mermaid
flowchart LR
    A[Device Commands] --> B[Response Patterns]
    B --> C[Successful Operations]
    C --> D[Knowledge Store]
    D --> E[device_framework_library.json]
    E --> F[Future Takeovers]
    F --> G[Improved Recognition]
    G --> H[Faster Control]
    
    I[Failed Operations] --> J[Error Patterns]
    J --> K[Recovery Strategies]
    K --> D
```

## 8. Multi-Protocol Discovery Flow

```mermaid
flowchart TD
    A[Discovery Started] --> B[Serial/USB Scan]
    A --> C[Bluetooth Scan]
    A --> D[WiFi Scan]
    A --> E[RF Scan]
    
    B --> F[Known Devices]
    C --> G[BLE Services]
    D --> H[Network IDs]
    E --> I[Signal Patterns]
    
    F --> J[DeviceTakeoverManager]
    G --> K[SignalAnalyzer]
    H --> K
    I --> K
    
    J --> L[Control Implemented]
    K --> M[Discovery Only]
```

---

*All flows represent current implementation state as of 2026-01-21*
