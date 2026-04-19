#!/usr/bin/env bash
# Kingdom AI — dependency install (project-grounded; no stdlib pip packages).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-trading.txt
python3 -m pip install -r requirements-extras.txt

echo "Optional extras (only if you use those subsystems): pip install chromadb brainflow pylsl mne librosa opencv-python"
