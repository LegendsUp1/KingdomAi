# Mining Tab — GUI Changes (Async Safety)

## File
- **`gui/qt_frames/mining/mining_frame.py`**

## Summary of changes
### 1) Removed `asyncio.run(...)` usage from coroutine-returning helpers
- **What changed**
  - Places where an API could return a coroutine were updated to avoid `asyncio.run(...)`.
  - Strategy:
    - If the GUI/qasync loop is already running: schedule via `asyncio.ensure_future(...)`.
    - Otherwise: run a short-lived event loop in a `ThreadPoolExecutor`.
- **Why**
  - Avoids nested event loops and prevents UI blocking.

### 2) Type checker stabilization for coroutine execution
- **What changed**
  - Captured the coroutine into a local variable (`coro = is_connected_result`) before passing it into an inner function.
- **Why**
  - Helps static analyzers reason about the coroutine type when used inside closures.

### 3) GPU device detection / benchmarking
- **What changed**
  - Coroutine-returning device detection and benchmark paths avoid `asyncio.run(...)`.
- **Why**
  - Prevents GUI stalls during GPU operations.
