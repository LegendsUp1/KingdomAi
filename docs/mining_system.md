# Mining System Architecture

## Overview
The Mining System is a core component of the Kingdom AI platform, providing cryptocurrency mining capabilities with advanced optimization features. The system is designed to be modular, efficient, and intelligent, leveraging ThothAI for optimization and real-time configuration.

## Components

### MiningManager
The central coordinator of the mining system, responsible for:
- Initializing and managing mining operations
- Processing mining commands (start, stop, status)
- Coordinating with GpuOptimizer and LiveConfigurator
- Handling mining state and worker management

### GpuOptimizer
Specialized component for GPU optimization:
- Detects and profiles GPU hardware
- Implements optimization algorithms for different mining scenarios
- Manages GPU settings (clock speeds, power limits, etc.)
- Integrates with ThothAI for intelligent optimization

### LiveConfigurator
Real-time configuration management:
- Manages mining configuration presets
- Provides parameter adjustment during mining
- Handles configuration persistence
- Enables quick switching between mining profiles

### MiningDashboard
Real-time visualization and monitoring:
- Displays mining statistics and performance metrics
- Provides alerts and notifications
- Visualizes historical mining data
- Offers interactive controls for mining operations

## Component Interactions

```
┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │
│  MiningManager  │◄────►│  GpuOptimizer   │
│                 │      │                 │
└────────┬────────┘      └─────────────────┘
         │
         │               ┌─────────────────┐
         │               │                 │
         ├──────────────►│LiveConfigurator │
         │               │                 │
         │               └─────────────────┘
         │
         │               ┌─────────────────┐
         └──────────────►│ MiningDashboard │
                         │                 │
                         └─────────────────┘
```

All components communicate through the EventBus system, which enables:
- Decoupled architecture
- Asynchronous operations
- Standardized event handling
- System-wide event logging

## Data Flow

1. **Configuration**: LiveConfigurator manages mining configurations and presets
2. **Initialization**: MiningManager initializes mining operations with selected configurations
3. **Optimization**: GpuOptimizer continuously tunes hardware parameters for optimal performance
4. **Monitoring**: MiningDashboard collects and displays real-time mining statistics
5. **Control**: Commands flow from user interface through MiningManager to underlying processes

## Integration with ThothAI

The mining system leverages ThothAI for intelligent optimization:
- Analyzing hardware profiles
- Recommending optimal mining settings
- Learning from performance data
- Adapting to changing mining conditions

## Event Handling

The mining system listens for and responds to these key events:

| Event               | Handler                | Description                            |
|---------------------|------------------------|----------------------------------------|
| mining.start        | _handle_start_mining   | Starts mining with specified config    |
| mining.stop         | _handle_stop_mining    | Stops mining operations                |
| mining.optimize     | _handle_optimize       | Triggers optimization process          |
| mining.status       | _handle_status         | Reports current mining status          |
| gpu.optimize        | _handle_gpu_optimize   | Optimizes GPU settings                 |
| config.load_preset  | _handle_load_preset    | Loads a configuration preset           |
| config.save_preset  | _handle_save_preset    | Saves current config as preset         |
| dashboard.update    | _handle_dashboard_update| Updates dashboard with latest data    |

## Mining Profiles

The system includes several predefined mining profiles:

1. **Balanced**: Optimized for balance between performance and power efficiency
2. **Performance**: Maximum mining performance, higher power consumption
3. **Efficiency**: Power-efficient mining, optimal for electricity costs
4. **Silent**: Reduced fan speeds and temperatures, minimal noise
5. **Custom**: User-defined profiles saved through LiveConfigurator

## File Structure

```
kingdom_ai/
├── mining/
│   ├── __init__.py
│   ├── mining_manager.py
│   ├── gpu_optimizer.py
│   ├── live_configurator.py
│   ├── dashboard/
│   │   ├── __init__.py
│   │   └── mining_dashboard.py
│   ├── profiles/
│   │   └── default_presets.json
│   └── configs/
│       └── mining_config.json
└── tests/
    └── mining/
        ├── __init__.py
        ├── test_mining_manager.py
        ├── test_gpu_optimizer.py
        ├── test_live_configurator.py
        └── test_mining_integration.py
```

## Configuration

The mining system uses JSON configuration files stored in `mining/configs/`:

```json
{
  "default_algorithm": "Ethash",
  "max_workers": 4,
  "auto_optimize": true,
  "dashboard": {
    "refresh_rate": 5,
    "metrics_to_show": ["hashrate", "temperature", "power_usage"]
  }
}
```

Presets are stored in `mining/profiles/default_presets.json`:

```json
{
  "balanced": {
    "algorithm": "Ethash",
    "power_limit": 150,
    "memory_clock": 7000,
    "core_clock": 1200,
    "fan_speed": 70
  },
  "efficiency": {
    "algorithm": "Ethash",
    "power_limit": 120,
    "memory_clock": 6500,
    "core_clock": 1100,
    "fan_speed": 65
  }
}
```

## Error Handling

The mining system implements robust error handling:
- Component-level error logging
- Graceful degradation on hardware issues
- Automatic recovery mechanisms
- Detailed error reporting to dashboard
