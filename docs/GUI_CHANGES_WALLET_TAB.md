# Wallet Tab — GUI Changes (Responsiveness)

## File
- **`gui/qt_frames/wallet_tab.py`**

## Summary of changes
### 1) Removed GUI-thread `asyncio.run(...)` from price update timer callback
- **What changed**
  - `_update_prices_sync` no longer calls `asyncio.run(self._fetch_and_update_prices())`.
  - If an event loop is running, it schedules with `asyncio.ensure_future(self._fetch_and_update_prices())`.
  - A fallback executor path exists for environments where no loop is running.
- **Why**
  - Prevents GUI freezes and avoids nested event-loop errors.

### 2) Infinite async loop continues to yield naturally
- **What changed**
  - `_stream_live_prices` uses `await asyncio.sleep(30)` between updates.
- **Why**
  - Ensures the async loop yields to the event loop and does not starve UI processing.

## Notes / thread-safety
- In normal GUI operation, the "loop running" branch is expected.
- If the fallback executor branch ever executes, ensure that `_fetch_and_update_prices()` does not update Qt widgets directly from a background thread.
