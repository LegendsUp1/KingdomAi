#!/usr/bin/env bash
# Full Black Panther XTTS clone test with live stderr progress + hard time limit (no infinite hang).
# Uses the same interpreter policy as core/voice_runtime.py (isolated voice stack, not kingdom-venv by default).
# Usage: ./scripts/run_voice_clone_with_progress.sh "Your words here"
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
# shellcheck source=/dev/null
source "$REPO/scripts/resolve_voice_python.sh"
if ! resolve_kingdom_voice_python "$REPO"; then
  echo "No isolated voice runtime found. Do one of:" >&2
  echo "  ./scripts/bootstrap_voice_runtime_venv.sh" >&2
  echo "  ./setup_voice_isolated_env.sh   # conda kingdom-voice" >&2
  echo "  export KINGDOM_VOICE_PYTHON=/path/to/voice/python" >&2
  echo "Or opt-in (not recommended): export KINGDOM_ALLOW_MAIN_VENV_XTTS=1" >&2
  exit 1
fi
TEXT="${*:-Full pipeline voice test with live progress.}"
# Max wall time — first XTTS run can exceed 30–60+ minutes on slow links; default 2h, override freely.
MAX_SEC="${KINGDOM_VOICE_TEST_MAX_SEC:-7200}"

export PYTHONUNBUFFERED=1
export COQUI_TOS_AGREED="${COQUI_TOS_AGREED:-1}"
if [[ "${KINGDOM_VOICE_EXEC_MODE:-}" == conda ]]; then
  echo "Using: conda run -n kingdom-voice python" >&2
else
  echo "Using: $KINGDOM_VOICE_PY" >&2
fi
echo "COQUI_TOS_AGREED=$COQUI_TOS_AGREED (required so Coqui does not block on [y/n])" >&2
echo "Max runtime: ${MAX_SEC}s (then SIGTERM — set KINGDOM_VOICE_TEST_MAX_SEC to override)" >&2

if [[ "${KINGDOM_VOICE_EXEC_MODE:-}" == conda ]]; then
  exec timeout --foreground -s TERM "${MAX_SEC}" \
    env PYTHONUNBUFFERED=1 PYTHONPATH="$REPO" COQUI_TOS_AGREED="${COQUI_TOS_AGREED}" \
    conda run -n kingdom-voice --no-capture-output \
    python -u "$REPO/redis_voice_service.py" --speak "$TEXT" 2>&1
else
  exec timeout --foreground -s TERM "${MAX_SEC}" \
    env PYTHONUNBUFFERED=1 PYTHONPATH="$REPO" COQUI_TOS_AGREED="${COQUI_TOS_AGREED}" \
    "$KINGDOM_VOICE_PY" -u "$REPO/redis_voice_service.py" --speak "$TEXT" 2>&1
fi
