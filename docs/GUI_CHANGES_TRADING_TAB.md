# Trading Tab — GUI Changes (Responsiveness & Async Safety)

## File
- **`gui/qt_frames/trading/trading_tab.py`**

## Summary of changes
### 1) Safe async scheduling (removal of `asyncio.run`)
- **What changed**
  - Removed/avoided GUI-thread `asyncio.run(...)` call sites across Trading tab actions.
  - Standardized on scheduling coroutines on the running qasync loop.
- **Why**
  - `asyncio.run(...)` blocks the UI thread and can conflict with qasync’s running event loop.

### 2) Async task queueing / re-entrancy protection
- **What changed**
  - Implemented/used a queued scheduler pattern to serialize async work and reduce qasync re-entrancy errors.
  - Key methods involved:
    - `TradingTab._schedule_async_task(...)`
    - `TradingTab._isolated_task_wrapper(...)`
    - `TradingTab._safe_create_task(...)`
    - `TradingTab._process_async_queue(...)`
- **Why**
  - Prevents bursts of UI-triggered coroutines from causing "Cannot enter into task" or event-loop contention.

### 3) `_run_async_in_thread` redesigned to be qasync-safe (thread execution removed)
- **What changed**
  - `TradingTab._run_async_in_thread(...)` no longer runs coroutines in a background thread.
  - It now schedules on the running loop using `asyncio.ensure_future(...)`.
- **Why**
  - Background-thread coroutine execution could indirectly trigger Qt object creation or widget updates and caused a hard crash (QObject thread violation → segfault).

### 4) Periodic refresh timer kept on main thread
- **What changed**
  - Live data refresh timer runs `_refresh_all_live_data` on the main thread.
- **Why**
  - The refresh path publishes events / may touch Qt objects; these must remain on the main thread.

### 5) Timer overhead reduction
- **What changed**
  - Profit bar pulse timer interval reduced from 100ms to 250ms.
- **Why**
  - Reduces UI thread work and smooths responsiveness under load.

### 6) Import strategy adjusted for Qt thread safety
- **What changed**
  - Removed background-thread module loading introduced for heavy imports.
  - `advanced_ai_strategies` is imported on the main thread (with a lazy re-attempt helper `_lazy_import_advanced_ai`).
- **Why**
  - Importing modules in a background thread can execute module-level code that initializes Qt objects (unsafe).

## Affected feature areas (where `asyncio.run` style calls were removed)
- **Auto-trading controls**
  - Enable/disable flows and status checks are scheduled rather than run synchronously.
- **Meme coin tooling**
  - Scan, rug-pull checks, and prediction generation now schedule tasks safely.
- **Sentiment analysis**
  - Startup runner is scheduled safely.
- **Arbitrage panels / HTTP polling paths**
  - Async runners are scheduled without blocking.

## Notes / follow-ups
- **Thread-only work rule**
  - Any future background-thread work must not create/modify Qt widgets directly.
  - If heavy work is required, return pure data from the thread and update UI on the main thread.
