# GUI Responsiveness & Async Refactor — Change Log

## Goal
Improve GUI responsiveness and stability in the PyQt6 + qasync application by removing blocking async patterns from the UI thread, reducing timer overhead, and enforcing Qt thread-safety.

## Scope (files changed)
- **`gui/qt_frames/trading/trading_tab.py`**
- **`gui/qt_frames/blockchain_tab.py`**
- **`gui/qt_frames/wallet_tab.py`**
- **`gui/qt_frames/mining/mining_frame.py`**

## Core constraints (non-negotiable)
- **Qt thread-safety**
  - Qt widgets / `QObject` children must be created and mutated on the **main Qt thread**.
  - Violations can crash the process (observed: `QObject: Cannot create children for a parent that is in a different thread` → segfault).
- **qasync integration**
  - Prefer scheduling coroutines on the running qasync loop via `asyncio.ensure_future(...)`.
  - Avoid `asyncio.run(...)` from within GUI code (nested event loops / UI blocking).

## High-level changes
- **Blocking async removal**
  - Replaced GUI-thread `asyncio.run(...)` usages with qasync-safe scheduling (`asyncio.ensure_future(...)`) and/or safe fallback execution paths.
- **Async task containment**
  - Introduced/expanded safe scheduling patterns to prevent qasync re-entrancy issues ("Cannot enter into task").
- **Timer overhead reduction**
  - Reduced high-frequency UI timers where possible (e.g., profit bar pulse from 100ms to 250ms).
  - Ensured periodic refresh timers that publish/emit Qt events run on the main thread.
- **Type-checker stabilization (Pyright)**
  - Addressed false-positive lint errors related to dynamically imported connectors by using a `**kwargs` constructor call.

## Incident: segfault from cross-thread Qt object creation
- **Symptom**
  - Crash on startup with `QObject: Cannot create children for a parent that is in a different thread` (parent: `QTextDocument`), followed by a segmentation fault.
- **Root cause**
  - Background-thread execution paths were able to trigger Qt object creation / callbacks.
- **Final fix**
  - Removed the background-thread module import system in `trading_tab.py`.
  - Updated the `TradingTab._run_async_in_thread` implementation to schedule on the qasync loop rather than running coroutines in a background thread.

## Testing checklist
- **Startup**
  - Launch the app and verify no `QObject ... different thread` warnings.
- **Trading tab**
  - Open Trading tab, trigger actions (auto-trading toggles, scans), confirm UI stays responsive.
- **Wallet tab**
  - Confirm periodic price updates occur without freezing.
- **Blockchain tab**
  - Trigger network stats refresh; confirm it does not block the UI.
- **Mining tab**
  - Trigger blockchain connectivity checks and GPU detection/benchmark; confirm UI stability.

## Related per-file docs
- **Trading tab details:** `docs/GUI_CHANGES_TRADING_TAB.md`
- **Blockchain tab details:** `docs/GUI_CHANGES_BLOCKCHAIN_TAB.md`
- **Wallet tab details:** `docs/GUI_CHANGES_WALLET_TAB.md`
- **Mining tab details:** `docs/GUI_CHANGES_MINING_TAB.md`
