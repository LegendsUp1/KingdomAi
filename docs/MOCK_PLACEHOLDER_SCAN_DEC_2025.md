# Mock/Placeholder Logic Scan - Kingdom AI

> **Date:** 2025-12-24  
> **Scope:** Simulated data, placeholder returns, demo logic across core + GUI  

---

## Summary

| Category | Files | Severity | Notes |
|----------|-------|----------|-------|
| Simulated Market Data | 2 | HIGH | Trading intelligence uses random prices |
| Simulated Whale Txs | 1 | MEDIUM | Whale tracker has demo mode |
| Simulated AI Outputs | 1 | MEDIUM | Thoth AI tab uses fake predictions |
| Legitimate Random | 3+ | OK | Art generation, encryption salts |

---

## HIGH Priority - Simulated Market Data

### `core/trading_intelligence.py`

**Lines 384-402:** Market data generated with random values instead of real API calls:
```python
price = base_price * (1 + (random.random() - 0.5) * 0.05)  # ±2.5% variation
volume = base_price * 1000 * (0.8 + random.random() * 0.4)
change_24h = (random.random() - 0.4) * 10  # -4% to +6%
sentiment = random.choice(['bullish', 'neutral', 'bearish'])
```

**Lines 759-771:** Publication loop uses random chances instead of real events:
```python
if random.random() < 0.8:  # 80% chance of price updates
if random.random() < 0.3:  # 30% chance for trend updates
if random.random() < 0.2:  # 20% chance for trading opportunities
```

**Impact:** Trading decisions may be based on fake data.

**Fix:** Replace with real market data from CCXT exchanges or price feeds.

---

## MEDIUM Priority - Simulated Whale Transactions

### `core/whale_tracker.py`

**Lines 300-333:** Demo whale transaction generator:
```python
transaction = {
    "id": f"simulated_{current_time}_{i}",
    "from": {"address": f"0xsimulated{i}from"},
    "to": {"address": f"0xsimulated{i}to"},
}
await self.process_transactions(transactions, simulated=True)
```

**Mitigation:** Code already marks transactions as `simulated=True` (line 346), so downstream can filter.

**Fix:** Connect to real whale alert APIs (Whale Alert, Etherscan large tx monitoring).

---

## MEDIUM Priority - Simulated AI Predictions

### `gui/qt_frames/thoth_ai_tab.py`

**Multiple "Simulate" blocks with fake return data:**

| Line | Function | Fake Data |
|------|----------|-----------|
| 3256 | Memory recall | `memories_found: 5` hardcoded |
| 3307 | Meta learning train | `epochs_completed: 100` hardcoded |
| 3355 | Strategy prediction | `recommended_strategy: "Momentum Trading"` |
| 3408 | Price prediction | `predicted_price: 67500.00` hardcoded |
| 3458 | Trend prediction | `trend: "STRONG BULLISH"` hardcoded |
| 3522 | Sentiment analysis | `sentiment_score: 0.78` hardcoded |
| 5199 | Auto meta learning | `patterns_learned: cycles * 3` fake formula |
| 5361 | Continuous prediction | `base_price + random` |
| 5410 | Continuous sentiment | `random.choice(["POSITIVE", "NEUTRAL", "NEGATIVE"])` |

**Impact:** AI appears to function but returns fake data.

**Fix:** Wire to actual Ollama inference, real prediction models, or clearly label as "Demo Mode".

---

## OK - Legitimate Random Usage

### `core/ai_visual_engine.py`
- Random used for procedural art generation (stars, nebulas, abstract shapes)
- This is correct usage - art should be randomized

### `core/quantum.py`, `core/sentience/*`
- Random used for quantum simulation effects
- Legitimate for visualization purposes

### Encryption/Security
- Random used for salts, nonces, IVs
- Legitimate cryptographic usage

---

## Fallback Pattern Analysis

**900+ matches for "fallback" across 117 files** - most are legitimate error handling:

- `core/portfolio_analytics.py` (94 matches) - Default values for missing data
- `core/trading_system.py` (61 matches) - Exchange connection fallbacks
- `core/blockchain/network_stats.py` (26 matches) - RPC endpoint fallbacks

**These are generally OK** - fallback logic for network failures is expected.

---

## Recommendations

### Immediate Actions

1. **Trading Intelligence**: Replace random market data with real CCXT price feeds
2. **Thoth AI Tab**: Either connect to real AI backends or add "DEMO MODE" labels
3. **Whale Tracker**: Connect to Whale Alert API or clearly indicate simulation

### Long-term Actions

1. Add configuration flag: `DEMO_MODE = False` to disable all simulated data
2. Log when simulated data is used: `logger.warning("Using simulated data")`
3. UI indicator when data is not real-time

---

## Files Requiring Review

| File | Issue | Priority |
|------|-------|----------|
| `core/trading_intelligence.py:384-402` | Random market data | HIGH |
| `core/trading_intelligence.py:759-771` | Random publication triggers | HIGH |
| `core/whale_tracker.py:300-333` | Simulated whale txs | MEDIUM |
| `gui/qt_frames/thoth_ai_tab.py:3256-5410` | Multiple fake AI outputs | MEDIUM |
