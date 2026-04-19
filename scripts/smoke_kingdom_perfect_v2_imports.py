#!/usr/bin/env python3
"""
Headless smoke: import kingdom_ai_perfect_v2, KingdomMainWindow, EventBus.
Does not open the full GUI (no main()). Use before backup/sync or in CI.

  cd /path/to/kingdom_ai
  PYTHONPATH=. QT_QPA_PLATFORM=offscreen python3 scripts/smoke_kingdom_perfect_v2_imports.py
"""
from __future__ import annotations

import os
import sys

def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import kingdom_ai_perfect_v2  # noqa: F401
    from gui.kingdom_main_window_qt import KingdomMainWindow  # noqa: F401
    from core.event_bus import EventBus

    eb = EventBus.get_instance()
    assert eb is not None
    print("smoke_kingdom_perfect_v2_imports: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
