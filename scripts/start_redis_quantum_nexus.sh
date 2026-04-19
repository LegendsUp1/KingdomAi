#!/usr/bin/env bash
# Start Redis Quantum Nexus on port 6380 (Kingdom AI's dedicated Redis instance).
# The system default Redis on 6379 is left alone.
# Run at boot or before launching Kingdom AI.
set -euo pipefail

PORT=6380
PASS="QuantumNexus2025"

if redis-cli -p "$PORT" -a "$PASS" ping 2>/dev/null | grep -qi pong; then
  echo "Redis Quantum Nexus already running on port $PORT"
  exit 0
fi

echo "Starting Redis Quantum Nexus on port $PORT..."
# --dbfilename "" and --save "" prevent loading/saving RDB (avoids version mismatch with system Redis).
# Data is ephemeral; persistent state lives in the app's SQLite/files.
redis-server --port "$PORT" --requirepass "$PASS" --daemonize yes \
  --dbfilename "" --save "" --appendonly no \
  --maxmemory 512mb --maxmemory-policy allkeys-lru

sleep 1
if redis-cli -p "$PORT" -a "$PASS" ping 2>/dev/null | grep -qi pong; then
  echo "Redis Quantum Nexus running on port $PORT"
else
  echo "Failed to start Redis on port $PORT" >&2
  exit 1
fi
