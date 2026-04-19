#!/usr/bin/env bash
# Create repo-local voice_runtime_env/ (stdlib venv + requirements-voice.txt only).
# Use when conda kingdom-voice is not available; keeps Coqui off kingdom-venv.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
VENV="$REPO/voice_runtime_env"
REQ="$REPO/requirements-voice.txt"

if [[ ! -f "$REQ" ]]; then
  echo "Missing $REQ" >&2
  exit 1
fi

if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck source=/dev/null
source "$VENV/bin/activate"
python -m pip install --upgrade pip
pip install -r "$REQ"
echo "Voice runtime ready: $VENV/bin/python"
echo "Export KINGDOM_VOICE_PYTHON=$VENV/bin/python or add to shell profile."
