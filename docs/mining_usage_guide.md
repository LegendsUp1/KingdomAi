# Mining System Usage Guide

This guide provides instructions for using the Kingdom AI Mining System components, including how to start and manage mining operations, optimize GPU settings, configure mining parameters, and monitor performance.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Starting and Stopping Mining](#starting-and-stopping-mining)
3. [GPU Optimization](#gpu-optimization)
4. [Configuration Presets](#configuration-presets)
5. [Mining Dashboard](#mining-dashboard)
6. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites
- Kingdom AI system properly installed
- Updated GPU drivers (NVIDIA recommended)
- System with sufficient cooling

### Initialization
The mining system initializes automatically when the Kingdom AI system starts. You can verify the mining system is ready by checking the logs:

```bash
tail -f logs/kingdom_info.log | grep mining
```

You should see initialization messages for:
- MiningManager
- GpuOptimizer
- LiveConfigurator
- MiningDashboard

## Starting and Stopping Mining

### Starting Mining Operations

You can start mining through:

1. **Command Line:**
```python
from kingdom_ai.core.event_bus import EventBus

async def start_mining():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("mining.start", {
        "config": {
            "algorithm": "Ethash",
            "worker_threads": 2,
            "intensity": 20
        }
    })
    print(f"Mining started: {response}")
```

2. **GUI Interface:**
   - Open the Mining tab in the Kingdom AI interface
   - Select the desired algorithm from the dropdown
   - Configure parameters if needed
   - Click the "Start Mining" button

### Stopping Mining Operations

1. **Command Line:**
```python
from kingdom_ai.core.event_bus import EventBus

async def stop_mining():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("mining.stop", {
        "worker_id": "all"  # Stop all workers, or specify a worker ID
    })
    print(f"Mining stopped: {response}")
```

2. **GUI Interface:**
   - Click the "Stop Mining" button in the Mining tab

### Checking Mining Status

```python
from kingdom_ai.core.event_bus import EventBus

async def check_status():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("mining.get_status", {})
    print(f"Mining status: {response}")
```

## GPU Optimization

### Manual Optimization

You can manually optimize GPU settings:

```python
from kingdom_ai.core.event_bus import EventBus

async def optimize_gpu():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("mining.optimize", {
        "target": "gpu",
        "params": {
            "power_limit": 150,      # In watts
            "memory_offset": 500,    # Memory clock offset
            "core_offset": 50,       # Core clock offset
            "fan_speed": 70          # Fan speed percentage
        }
    })
    print(f"Optimization result: {response}")
```

### Auto-Optimization

The system can automatically optimize settings based on your mining algorithm:

```python
from kingdom_ai.core.event_bus import EventBus

async def auto_optimize():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("mining.optimize", {
        "target": "gpu",
        "auto": True,
        "algorithm": "Ethash"
    })
    print(f"Auto-optimization result: {response}")
```

### GPU Status

Check current GPU status:

```python
from kingdom_ai.core.event_bus import EventBus

async def check_gpu_status():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("gpu.get_status", {
        "gpu_indices": [0, 1]  # Specify which GPUs to check, or omit for all
    })
    print(f"GPU status: {response}")
```

## Configuration Presets

### Available Presets

The system comes with several predefined mining presets:
- **balanced**: Balanced performance and efficiency
- **performance**: Maximum mining performance
- **efficiency**: Optimal power efficiency
- **silent**: Reduced noise operation

### Listing Presets

```python
from kingdom_ai.core.event_bus import EventBus

async def list_presets():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("config.list_presets", {})
    print(f"Available presets: {response['presets']}")
```

### Loading a Preset

```python
from kingdom_ai.core.event_bus import EventBus

async def load_preset(preset_name="balanced"):
    event_bus = EventBus.get_instance()
    response = await event_bus.request("config.load_preset", {
        "preset_name": preset_name
    })
    print(f"Loaded preset: {response}")
```

### Creating a Custom Preset

```python
from kingdom_ai.core.event_bus import EventBus

async def save_preset():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("config.save_preset", {
        "preset_name": "my_custom_preset",
        "preset_data": {
            "algorithm": "Ethash",
            "power_limit": 160,
            "memory_clock": 7200,
            "core_clock": 1250,
            "fan_speed": 75
        }
    })
    print(f"Preset saved: {response}")
```

## Mining Dashboard

### Accessing the Dashboard

1. Through the Kingdom AI interface:
   - Navigate to the Mining tab
   - Select "Dashboard" from the submenu

2. Direct URL access (when using the web interface):
   - Open your browser to `http://localhost:8080/mining/dashboard`

### Dashboard Features

The mining dashboard provides:
- Real-time hashrate monitoring
- Temperature and power usage graphs
- Mining efficiency metrics
- Share acceptance rates
- Alerts and notifications
- Historical performance data

### Getting Dashboard Data

```python
from kingdom_ai.core.event_bus import EventBus

async def get_stats():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("dashboard.get_stats", {
        "worker_id": "all"  # Get stats for all workers
    })
    print(f"Current mining stats: {response}")

async def get_history():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("dashboard.get_history", {
        "limit": 100,  # Get last 100 data points
        "worker_id": "worker1"  # Optional: filter by worker
    })
    print(f"Historical data: {response}")
```

### Resetting Dashboard

```python
from kingdom_ai.core.event_bus import EventBus

async def reset_dashboard():
    event_bus = EventBus.get_instance()
    response = await event_bus.request("dashboard.reset", {})
    print(f"Dashboard reset: {response}")
```

## Troubleshooting

### Common Issues

1. **Mining Won't Start**
   - Check GPU drivers are up to date
   - Verify CUDA is installed (for NVIDIA GPUs)
   - Check system permissions
   - Review logs for specific errors: `tail -f logs/kingdom_error.log`

2. **Low Hashrate**
   - Try a different optimization preset
   - Check if other processes are using the GPU
   - Verify GPU temperature is within normal range
   - Consider updating GPU firmware

3. **System Crashes During Mining**
   - Reduce intensity or power limit
   - Improve system cooling
   - Check power supply capacity
   - Update GPU drivers

### Diagnostic Commands

Check mining component status:
```bash
python -c "
from kingdom_system import KingdomSystem
system = KingdomSystem()
print('Mining components:', system.components.get('MiningManager', None) is not None)
print('GPU Optimizer:', system.components.get('GpuOptimizer', None) is not None)
print('Live Configurator:', system.components.get('LiveConfigurator', None) is not None)
"
```

Run mining tests to verify functionality:
```bash
cd kingdom_ai
python tests/run_mining_tests.py --verbose
```

### Log Analysis

Important log files:
- `logs/kingdom_info.log` - General system information
- `logs/kingdom_error.log` - Error messages
- `data/mining/dashboard/stats_history.json` - Mining statistics history

### Getting Help

If you encounter persistent issues:
1. Check the Kingdom AI documentation
2. Review mining configuration settings
3. Try running with default settings
4. Check for system resource constraints
5. Contact support with relevant log files
