# Universal Data Display Orchestrator - SOTA 2026

## Overview

The Universal Data Display Orchestrator provides Kingdom AI with the ability to display **ANY data** from **ANY system component** in **ANY format** - including 2D vision stream, 3D VR environment, charts, gauges, tables, maps, and animations.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User Request (Chat)                           │
│              "show me trading data in VR"                            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                    ThothMCPBridge                                    │
│  handle_display_message() → resolve data source → route to display  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│              UniversalDataDisplayOrchestrator                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Data Sources:                                                │  │
│  │  • Sensors: vision, lidar, sonar, gps, imu, thermal          │  │
│  │  • Trading: prices, predictions, portfolio, orders           │  │
│  │  • Blockchain: chain, wallet, transactions, contracts        │  │
│  │  • Mining: hashrate, pools, earnings                         │  │
│  │  • Signals: RF, Bluetooth, WiFi, RC devices                  │  │
│  │  • System: devices, analytics, AI responses                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Vision Stream  │  │    VR System    │  │  Event Bus      │
│  (2D Display)   │  │  (3D Immersive) │  │  (Broadcasts)   │
│  • Video feed   │  │  • Point clouds │  │  • Real-time    │
│  • Charts       │  │  • 3D surfaces  │  │  • Updates      │
│  • Gauges       │  │  • 3D maps      │  │  • Animations   │
│  • Tables       │  │  • Animated     │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Data Sources

### Sensors & Hardware
| Source | Event Topics | Display Modes |
|--------|--------------|---------------|
| `vision` | vision.stream.frame | Video, VR |
| `lidar` | lidar.scan, lidar.pointcloud | Point Cloud, VR |
| `sonar` | sonar.ping, sonar.scan | 3D Surface, VR |
| `gps` | gps.position, gps.track | Map, VR |
| `imu` | imu.orientation | Gauge, VR |
| `thermal` | thermal.frame | Video, VR |
| `signals` | signals.scan.complete | Table, Chart, VR |

### Trading & Finance
| Source | Event Topics | Display Modes |
|--------|--------------|---------------|
| `trading` | trading.price.update | Chart, Table, VR |
| `predictions` | trading.prediction | Chart, Animation, VR |
| `portfolio` | portfolio.update | Chart, Table, Gauge |
| `orders` | orderbook.update | Table |

### Blockchain
| Source | Event Topics | Display Modes |
|--------|--------------|---------------|
| `blockchain` | blockchain.block | Table, VR |
| `wallet` | wallet.balance | Table, Gauge |
| `transactions` | transaction.new | Table, Animation |

### Mining
| Source | Event Topics | Display Modes |
|--------|--------------|---------------|
| `mining` | mining.stats | Chart, Gauge, VR |

### System
| Source | Event Topics | Display Modes |
|--------|--------------|---------------|
| `devices` | device.connected | Table, VR |
| `analytics` | analytics.result | Chart, Table, VR |
| `ai` | ai.response | Text, Animation |

## Display Modes

| Mode | Description | Output |
|------|-------------|--------|
| `vision_2d` | 2D video/image display | Vision Stream |
| `vr_3d` | 3D immersive environment | VR Headset |
| `chart` | Line, bar, candlestick charts | Vision Stream |
| `gauge` | Circular gauges (RPM, speed, etc.) | Vision Stream |
| `table` | Data tables | Vision Stream |
| `map` | Geographic map overlay | Vision Stream / VR |
| `point_cloud` | 3D point cloud scatter | VR |
| `surface_3d` | 3D mesh surface | VR |
| `animation` | Animated visualization | Vision Stream / VR |
| `text` | Plain text/numbers | Vision Stream |

## Chat Commands

### Basic Display
```
show me trading data
display signals
visualize mining stats
get blockchain data
```

### Specific Format
```
show trading as chart
display devices in table
show predictions as 3d
visualize portfolio as gauge
```

### VR Display
```
show trading in vr
display lidar in vr
show blockchain in vr
visualize signals in vr
```

### Animation
```
animate trading data
animation of predictions
animate blockchain transactions
```

### List Sources
```
list data sources
what data sources are available
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `show_data` | Display any data in any format |
| `list_data_sources` | List all available sources |
| `show_in_vr` | Display in VR environment |
| `show_on_vision` | Display on vision stream |
| `stop_display` | Stop displaying a source |
| `convert_to_3d` | Convert to 3D visualization |
| `animate_data` | Create animated visualization |

## Python API

```python
from core.universal_data_display import get_data_display_orchestrator

# Get orchestrator
display = get_data_display_orchestrator(event_bus)

# Show trading data as chart
response = display.display_data("trading", display_mode="chart")

# Show in VR
response = display.display_data("lidar", vr_enabled=True)

# Animate predictions
response = display.display_data("predictions", animation=True)

# List available sources
sources = display.get_available_sources()

# Stop display
display.stop_display("trading")
```

## Event Bus Integration

### Published Events
- `visualization.update` - New visualization data ready
- `vision.display.update` - Update vision stream display
- `vr.scene.update` - Update VR scene

### Subscribed Events
All data source events are automatically subscribed when the orchestrator initializes.

## Files

| File | Purpose |
|------|---------|
| `core/universal_data_display.py` | Main orchestrator |
| `core/universal_data_visualizer.py` | Data type converters |
| `ai/thoth_mcp.py` | Chat integration |
| `components/vision_stream.py` | 2D display output |
| `core/vr_integration.py` | VR display output |

## Testing

### CLI Test
```bash
cd "c:\Users\Yeyian PC\Documents\Python Scripts\New folder"
python core/universal_data_display.py
```

### Chat Test
In ThothAI chat:
```
list data sources
show trading data
show signals in vr
animate predictions
```

## Version History

- **v1.0.0** (Jan 2026): Initial implementation
  - 15+ data source categories
  - 10 display modes
  - VR and Vision Stream output
  - Real-time updates
  - Animation support
  - Chat command integration
  - 7 MCP tools
