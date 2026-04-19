#!/usr/bin/env bash
# Start Redis (if needed) + Black Panther XTTS voice service on native Linux.
# Uses isolated voice stack (voice_runtime_env / conda kingdom-voice / KINGDOM_VOICE_PYTHON) — not kingdom-venv by default.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
# shellcheck source=/dev/null
source "$REPO/scripts/resolve_voice_python.sh"
if ! resolve_kingdom_voice_python "$REPO"; then
  echo "No voice runtime: run scripts/bootstrap_voice_runtime_venv.sh or setup_voice_isolated_env.sh," >&2
  echo "or set KINGDOM_VOICE_PYTHON. Opt-in main venv: KINGDOM_ALLOW_MAIN_VENV_XTTS=1" >&2
  exit 1
fi

REDIS_PORT=6380
REDIS_PASS="QuantumNexus2025"
if redis-cli -p "$REDIS_PORT" -a "$REDIS_PASS" ping 2>/dev/null | grep -qi pong; then
  echo "Redis already on port $REDIS_PORT"
else
  echo "Start Redis on $REDIS_PORT first, e.g.:"
  echo "  redis-server --port $REDIS_PORT --requirepass $REDIS_PASS --daemonize yes"
  echo "  or: docker run -d -p ${REDIS_PORT}:6379 redis:alpine --requirepass $REDIS_PASS"
  exit 1
fi

export PYTHONPATH="$REPO"
export COQUI_TOS_AGREED="${COQUI_TOS_AGREED:-1}"
if [[ "${KINGDOM_VOICE_EXEC_MODE:-}" == conda ]]; then
  exec conda run -n kingdom-voice --no-capture-output python "$REPO/redis_voice_service.py"
else
  exec "$KINGDOM_VOICE_PY" "$REPO/redis_voice_service.py"
fi
