# Redis Quantum Nexus - Global Configuration

## Overview

**Date:** December 24, 2025

Redis Quantum Nexus is the **ONLY** Redis instance used by Kingdom AI. All components must connect to this single Redis server.

## Configuration

| Setting | Value |
|---------|-------|
| **Host** | `127.0.0.1` |
| **Port** | `6380` |
| **Password** | `QuantumNexus2025` |
| **Database** | `0` |

## Files Updated

The following files have been updated to use Redis Quantum Nexus exclusively:

### Core Files
1. **`core/redis_connector.py`** - Primary Redis connector with auto-start capabilities
2. **`core/redis_connection.py`** - Async Redis connection class
3. **`core/connection_manager.py`** - Connection pool manager

### GUI Files
4. **`gui/frames/settings_frame.py`** - Settings with redis_port 6380

### Infrastructure Files
5. **`infrastructure/redis_connector.py`** - Infrastructure-level Redis connector

## Usage

All Redis connections in Kingdom AI should use these defaults:

```python
# REDIS QUANTUM NEXUS - Global Configuration
host = "127.0.0.1"
port = 6380  # Quantum Nexus port
password = "QuantumNexus2025"
db = 0
```

## Auto-Start Capabilities

The Redis connector (`core/redis_connector.py`) includes auto-start functionality:

### Windows
- Searches for `redis-server.exe` in common paths
- Tries Docker: `docker run -d -p 6380:6379 redis:alpine --requirepass QuantumNexus2025`
- Attempts installation via `winget install Redis.Redis`
- Attempts installation via `choco install redis-64`

### Linux/Mac
- Uses `redis-server --port 6380 --requirepass QuantumNexus2025 --daemonize yes`
- Falls back to Docker if native not available

## Commands

### Start Redis (Docker)
```bash
docker run -d --name kingdom-redis -p 6380:6379 redis:alpine --requirepass QuantumNexus2025
```

### Start Redis (Native Windows)
```bash
redis-server --port 6380 --requirepass QuantumNexus2025
```

### Test Connection
```python
import redis
r = redis.Redis(host='127.0.0.1', port=6380, password='QuantumNexus2025')
print(r.ping())  # Should return True
```

## Important Notes

1. **Port 6379 is NOT used** - Only port 6380 (Quantum Nexus)
2. **Password is REQUIRED** - All connections must use `QuantumNexus2025`
3. **No fallback to other Redis** - Only Quantum Nexus is supported
4. **Auto-install on failure** - System attempts to install Redis if not found
