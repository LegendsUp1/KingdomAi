#!/usr/bin/env bash
# Resolve which Python runs Coqui / redis_voice_service — must match core/voice_runtime.py policy.
# Source from scripts after REPO is set:  source "$REPO/scripts/resolve_voice_python.sh"
# Sets: KINGDOM_VOICE_EXEC_MODE=direct|conda  and  KINGDOM_VOICE_PY (path when direct)
# Exit 0 if a runtime was found, 1 otherwise.

resolve_kingdom_voice_python() {
  local REPO="$1"
  KINGDOM_VOICE_EXEC_MODE=""
  KINGDOM_VOICE_PY=""

  # Do NOT prefer generic PYTHON here — it often points at kingdom-venv and breaks isolation.
  # Opt-in: KINGDOM_VOICE_USE_PYTHON_ENV=1 uses PYTHON as the voice interpreter (explicit).
  if [[ "${KINGDOM_VOICE_USE_PYTHON_ENV:-}" =~ ^(1|true|yes|on)$ ]] && [[ -n "${PYTHON:-}" && -x "${PYTHON}" ]]; then
    KINGDOM_VOICE_EXEC_MODE=direct
    KINGDOM_VOICE_PY="${PYTHON}"
    return 0
  fi
  if [[ -n "${KINGDOM_VOICE_PYTHON:-}" && -x "${KINGDOM_VOICE_PYTHON}" ]]; then
    KINGDOM_VOICE_EXEC_MODE=direct
    KINGDOM_VOICE_PY="${KINGDOM_VOICE_PYTHON}"
    return 0
  fi
  if [[ -x "$REPO/voice_runtime_env/bin/python" ]]; then
    KINGDOM_VOICE_EXEC_MODE=direct
    KINGDOM_VOICE_PY="$REPO/voice_runtime_env/bin/python"
    return 0
  fi
  if [[ -x "$REPO/voice_runtime_env/bin/python3" ]]; then
    KINGDOM_VOICE_EXEC_MODE=direct
    KINGDOM_VOICE_PY="$REPO/voice_runtime_env/bin/python3"
    return 0
  fi
  if command -v conda &>/dev/null && conda env list 2>/dev/null | grep -qE '^kingdom-voice[[:space:]]'; then
    KINGDOM_VOICE_EXEC_MODE=conda
    return 0
  fi
  if [[ "${KINGDOM_ALLOW_MAIN_VENV_XTTS:-}" =~ ^(1|true|yes|on)$ ]] && [[ -x "$REPO/kingdom-venv/bin/python" ]]; then
    KINGDOM_VOICE_EXEC_MODE=direct
    KINGDOM_VOICE_PY="$REPO/kingdom-venv/bin/python"
    return 0
  fi
  return 1
}
