# Blockchain Tab — GUI Changes (Responsiveness & Type Safety)

## File
- **`gui/qt_frames/blockchain_tab.py`**

## Summary of changes
### 1) Removed GUI-thread `asyncio.run(...)` usage for network stats refresh
- **What changed**
  - `_refresh_network_stats_sync` no longer calls `asyncio.run(self._refresh_network_stats())`.
  - If a loop is already running, it schedules via `asyncio.ensure_future(...)`.
  - Fallback path uses a short-lived event loop in a background executor when needed.
- **Why**
  - Prevents blocking the GUI thread and avoids nested event-loop errors under qasync.

### 2) Resolved Pyright false-positives for connector constructor args
- **What changed**
  - `BlockchainConnector` instantiation uses a dictionary + `**connector_kwargs`:
    - `network`
    - `config`
    - `event_bus`
- **Why**
  - Pyright could not reliably infer the imported connector type due to dynamic/aliased imports and incorrectly flagged `config`/`event_bus` as invalid parameters.
  - The runtime connector (`BlockchainConnectorBase`) does accept those parameters.

## Notes
- **Logic unchanged**
  - The connector still receives the same values; only the call form changed to improve editor/type-checker stability.
