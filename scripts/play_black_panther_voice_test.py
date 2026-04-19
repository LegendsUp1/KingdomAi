#!/usr/bin/env python3
"""Play a Black Panther voice line through your default output (Settings → Sound).

Uses the same path as the running app: VoiceManager → Redis XTTS if available,
else local Speech Dispatcher (spd-say) / pyttsx3.

Usage (from repo root — needs app deps for VoiceManager; XTTS itself uses isolated env inside VoiceManager):
  kingdom-venv/bin/python scripts/play_black_panther_voice_test.py
  kingdom-venv/bin/python scripts/play_black_panther_voice_test.py "Custom line here"
"""
from __future__ import annotations

import os
import sys

# Repo root on path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import logging
import time

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> int:
    text = (
        " ".join(sys.argv[1:]).strip()
        if len(sys.argv) > 1
        else "Kingdom AI. Black Panther voice test. Your speakers are live."
    )
    from core.event_bus import EventBus
    from core.voice_manager import VoiceManager

    vm = VoiceManager(event_bus=EventBus())
    vm.speak(text, priority="high")
    # XTTS clone runs in a worker thread for up to KINGDOM_XTTS_TIMEOUT_SEC (default 2h); old 60s wait aborted before playback.
    wait_sec = int(os.environ.get("KINGDOM_VOICE_TEST_WAIT_SEC", "7200"))
    deadline = time.monotonic() + wait_sec
    for _ in range(200):
        if vm.is_speaking:
            break
        time.sleep(0.05)
    while vm.is_speaking and time.monotonic() < deadline:
        time.sleep(0.5)
    time.sleep(0.3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
