# Shutdown & Async Flow Audit - Kingdom AI

> **Date:** 2025-12-24  
> **Scope:** QTimer/QThread cleanup, EventBus unsubscribe patterns, closeEvent handlers  

---

## Summary Table

| Tab/Component | cleanup() | closeEvent() | Timers | EventBus Unsub | Status |
|---------------|-----------|--------------|--------|----------------|--------|
| Trading Tab | ✅ | ✅ | ✅ | ✅ | OK |
| VR Tab | ✅ | ✅ | ✅ | ⚠️ | WARN |
| Wallet Tab | ✅ | ✅ | ✅ | ✅ | OK |
| Thoth AI Tab | ❌ | ❌ | ❌ | ❌ | CRITICAL |
| Dashboard Qt | ❌ | ❌ | ❌ | ❌ | CRITICAL |
| Blockchain Tab | ❌ | ❌ | N/A | ❌ | CRITICAL |
| Code Generator | ✅ | ✅ | ✅ | ⚠️ | OK |

---

## CRITICAL: Thoth AI Tab

**File:** `gui/qt_frames/thoth_ai_tab.py`

**Timers never stopped:**
- `self.meta_learning_timer` (line 5113, 60s interval)
- `self.prediction_timer` (line 5120, 30s interval)

**Missing:** cleanup(), closeEvent()

---

## CRITICAL: Dashboard Qt

**File:** `gui/qt_frames/dashboard_qt.py`

**Timers never stopped:**
- `self.status_timer` (line 161, 2s interval)
- `self.health_check_timer` (line 169, 5s interval)

**EventBus subscriptions never unsubscribed (lines 189-194):**
- system.status, system.performance, system.status.response
- dashboard.metrics_updated, mining.dashboard.stats_updated, trading.portfolio_update

**Missing:** cleanup(), closeEvent()

---

## CRITICAL: Blockchain Tab

**File:** `gui/qt_frames/blockchain_tab.py`

**EventBus subscriptions never unsubscribed:**
- api.key.available.*, api.key.list (lines 132-136)
- blockchain.api_keys_ready (line 282)
- blockchain.balance_updated, blockchain.tx_list, blockchain.block_update (lines 467-469)
- market.prices, market:price_update (lines 552-553)

**Missing:** cleanup(), closeEvent()

---

## OK Components

**Trading Tab** (`gui/qt_frames/trading/trading_tab.py`):
- closeEvent() line 1023 calls _cleanup_trading_tab()
- cleanup() line 1038

**Wallet Tab** (`gui/qt_frames/wallet_tab.py`):
- cleanup() line 2334 with timer stops + EventBus unsubscribe
- closeEvent() line 2425

**VR Tab** (`gui/qt_frames/vr_qt_tab.py`):
- cleanup() line 2305 stops timers
- closeEvent() line 2363
- Warning: EventBus unsubscribe calls missing

---

## Core Infrastructure

**ResourceCleanupManager** (`core/resource_cleanup_manager.py`):
- Singleton cleanup tracker
- cleanup_all() stops all registered timers/threads

**EventBus** (`core/event_bus.py`):
- cleanup_pending_tasks() at line 598

**Main Window** (`gui/kingdom_main_window_qt.py`):
- closeEvent() line 1346 closes tabs but relies on their cleanup()

---

## Recommended Fix Pattern

```python
def cleanup(self):
    # Stop timers
    for name in ['timer1', 'timer2']:
        t = getattr(self, name, None)
        if t and t.isActive():
            t.stop()
    
    # Unsubscribe EventBus
    if self.event_bus:
        self.event_bus.unsubscribe('event.type', self.handler)

def closeEvent(self, event):
    self.cleanup()
    super().closeEvent(event)
```

---

## Files Requiring Fixes

1. `gui/qt_frames/thoth_ai_tab.py` - Add cleanup() + closeEvent()
2. `gui/qt_frames/dashboard_qt.py` - Add cleanup() + closeEvent()
3. `gui/qt_frames/blockchain_tab.py` - Add cleanup() + closeEvent()
4. `gui/qt_frames/vr_qt_tab.py` - Add EventBus unsubscribe to cleanup()
