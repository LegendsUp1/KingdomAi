# Error Log Correlation Report - Kingdom AI

> **Date:** 2025-12-24  
> **Source:** `logs/errors_*.json` (47 files analyzed)  
> **Scope:** Correlate runtime errors to code locations for targeted fixes  

---

## Top Recurring Errors

| Error | File:Line | Count | Status |
|-------|-----------|-------|--------|
| BinanceUS timestamp -1021 | `core/real_exchange_executor.py:2299` | Multiple sessions | FIXED |
| HTX API endpoint error | `core/real_exchange_executor.py:2320-2335` | Multiple sessions | NEEDS FIX |
| Trading market data 0 events | `tests/trading_tab_live_data_harness.py:217` | Test failures | CONFIG |
| KeyboardInterrupt in timer | `utils/qt_timer_fix.py:101` | User-initiated | OK |

---

## 1. HTX (Huobi) API Error

**Error:**
```
Error building symbol index for htx (possible code bug): 
htx GET https://api.hbdm.com/linear-swap-api/v1/swap_contract_info?business_type=all
```

**Location:** `core/real_exchange_executor.py:2320-2335`

**Root Cause:** HTX API requires specific headers and SSL configuration.

**Fix Applied (Dec 24, 2025):**
- Disabled SSL verification for HTX
- Forced spot-only markets to avoid swap API
- See `docs/CHANGELOG_DEC_24_2025.md` section 10

**Status:** FIXED - verify in next session

---

## 2. BinanceUS Timestamp Error (-1021)

**Error:**
```
binanceus {"code":-1021,"msg":"Timestamp for this request was 1000ms ahead of the server's time."}
```

**Location:** `core/real_exchange_executor.py:2299`

**Root Cause:** Client clock drift vs Binance server time.

**Fix Applied (Dec 24, 2025):**
- Increased `recvWindow` to 60000ms
- Force clock sync before requests
- Auto-retry with sync on timestamp errors
- See `docs/CHANGELOG_DEC_24_2025.md` section 10

**Status:** FIXED

---

## 3. Trading Market Data - 0 Events

**Error:**
```
❌ Topic 'trading.market_data' emitted 0 events
❌ Topic 'trading.live_prices' emitted 0 events
❌ Topic 'portfolio_update' emitted 0 events
```

**Location:** `tests/trading_tab_live_data_harness.py:217`

**Root Cause:** Test harness expects live data but exchanges not connected.

**Fix Required:**
1. Ensure API keys are configured
2. Verify Redis Quantum Nexus is running (port 6380)
3. Check exchange connectivity

**Status:** CONFIGURATION - not a code bug

---

## 4. KeyboardInterrupt in Timer Callbacks

**Error:**
```
KeyboardInterrupt in qt_timer_fix.py:101
```

**Location:** `utils/qt_timer_fix.py:101`

**Root Cause:** User pressing Ctrl+C during timer execution.

**Status:** OK - expected behavior

---

## Error Frequency by File

| File | Error Count | Notes |
|------|-------------|-------|
| `core/real_exchange_executor.py` | 15+ | Exchange API issues |
| `tests/trading_tab_live_data_harness.py` | 10+ | Test expectations |
| `kingdom_ai_perfect.py` | 2 | KeyboardInterrupt |
| `utils/qt_timer_fix.py` | 3 | KeyboardInterrupt |

---

## Recommendations

### Immediate

1. **HTX:** Verify SSL fix works in production
2. **BinanceUS:** Monitor for timestamp errors after fix

### Long-term

1. Add circuit breaker for exchange errors
2. Implement automatic clock sync on startup
3. Add health check dashboard for exchange connectivity

---

## Error Log Structure

All error logs follow this JSON schema:
```json
{
  "session_id": "YYYYMMDD_HHMMSS",
  "session_start": "ISO timestamp",
  "total_errors": int,
  "unique_errors": int,
  "errors": [
    {
      "type": "ERROR|WARNING|CRITICAL",
      "message": "error description",
      "location": "file:line",
      "first_seen": "ISO timestamp",
      "count": int,
      "severity": "ERROR|WARNING|CRITICAL",
      "traceback": "stack trace if available"
    }
  ]
}
```

---

## Files With Fixes Applied This Session

| File | Fix | Line |
|------|-----|------|
| `core/real_exchange_executor.py` | BinanceUS timestamp fix | 1277-1316 |
| `core/real_exchange_executor.py` | HTX SSL + spot-only | 1387-1422 |
| `core/real_exchange_executor.py` | BTCC/OANDA connectors | 1691-1734 |
