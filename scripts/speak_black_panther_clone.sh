#!/usr/bin/env bash
# Speak with the Black Panther **cloned** voice (Coqui XTTS v2) using the isolated voice stack
# (same policy as core/voice_runtime.py — not kingdom-venv unless KINGDOM_ALLOW_MAIN_VENV_XTTS=1).
#
# Usage:
#   ./scripts/speak_black_panther_clone.sh "Your line here"
#   echo "Your line" | ./scripts/speak_black_panther_clone.sh --stdin

set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
# shellcheck source=/dev/null
source "$REPO/scripts/resolve_voice_python.sh"
if ! resolve_kingdom_voice_python "$REPO"; then
  echo "No voice runtime — run scripts/bootstrap_voice_runtime_venv.sh or setup_voice_isolated_env.sh" >&2
  exit 1
fi

export PYTHONPATH="$REPO"
export COQUI_TOS_AGREED="${COQUI_TOS_AGREED:-1}"

if [[ "${1:-}" == "--stdin" ]]; then
  if [[ "${KINGDOM_VOICE_EXEC_MODE:-}" == conda ]]; then
    exec conda run -n kingdom-voice --no-capture-output python "$REPO/redis_voice_service.py" --speak-stdin
  else
    exec "$KINGDOM_VOICE_PY" "$REPO/redis_voice_service.py" --speak-stdin
  fi
fi

TEXT="${*:-This is the Kingdom AI Black Panther cloned voice test.}"
if [[ "${KINGDOM_VOICE_EXEC_MODE:-}" == conda ]]; then
  exec conda run -n kingdom-voice --no-capture-output python "$REPO/redis_voice_service.py" --speak "$TEXT"
else
  exec "$KINGDOM_VOICE_PY" "$REPO/redis_voice_service.py" --speak "$TEXT"
fi
