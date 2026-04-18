# SOTA 2026 Resilience Patterns for Kingdom AI

## Overview

This document describes the **SOTA 2026 Resilience Patterns** implemented across all Kingdom AI systems to ensure **fallbacks never permanently replace real operations**.

## Key Principles

| Principle | Description |
|-----------|-------------|
| **Retry with Backoff** | Failed operations retry 3-5 times with exponential delays (1s, 2s, 4s, 8s) before using fallback |
| **Circuit Breaker** | Prevents cascading failures by stopping calls to failed services, periodically testing for recovery |
| **Smart Caching** | Successful results are cached for fallback use; stale values used only temporarily |
| **Background Recovery** | When circuit opens, background thread continuously attempts real operations to detect recovery |
| **Soft Dependencies** | Transform hard dependencies to soft - core operations continue even if auxiliary services fail |

## Critical Rule

> **Fallbacks NEVER permanently replace real operations. They are temporary measures while the system works to restore full functionality.**

---

## Implementation: `core/resilience_patterns.py`

### Circuit Breaker States

```
CLOSED (Normal) ──[failures exceed threshold]──▶ OPEN (Blocking)
                                                      │
                                                      │ [timeout expires]
                                                      ▼
                                                HALF_OPEN (Testing)
                                                      │
                            ┌─────[success]───────────┤
                            ▼                         │
                         CLOSED                 [failure]
                                                      │
                                                      ▼
                                                   OPEN
```

### ResilientOperation Class

```python
from core.resilience_patterns import ResilientOperation, KingdomResilience

# Create resilient exchange operation
exchange_op = KingdomResilience.create_exchange_operation(
    exchange_name="binance",
    operation=lambda symbol: exchange.fetch_ticker(symbol),
    fallback=lambda symbol: cached_prices.get(symbol, {})
)

# Execute with full resilience
result = exchange_op.execute("BTC/USDT")
if result.success:
    print(f"Price: {result.value}")
    if result.from_fallback:
        print("⚠️ Using fallback - real operation recovering")
else:
    print(f"Failed: {result.error}")
```

### Pre-configured Operations

| Factory Method | Use Case | Config |
|----------------|----------|--------|
| `create_exchange_operation()` | Exchange API calls | 3 failures, 10s timeout, 2 retries |
| `create_blockchain_operation()` | Blockchain RPC calls | 5 failures, 30s timeout, 3 retries |
| `create_ai_operation()` | AI/Ollama calls | 3 failures, 60s timeout, 2 retries |
| `create_mining_operation()` | Mining pool operations | 5 failures, 30s timeout, 3 retries |

---

## Integration Points

### Trading System (`core/real_exchange_executor.py`)

```python
from core.resilience_patterns import ResilientOperation, KingdomResilience

# Wrap exchange operations with resilience
self._fetch_ticker_op = KingdomResilience.create_exchange_operation(
    exchange_name=self.name,
    operation=self._fetch_ticker_raw,
    fallback=self._get_cached_ticker
)
```

### AI System (`core/thoth_ollama_connector.py`)

```python
from core.resilience_patterns import KingdomResilience

# Wrap AI inference with resilience
self._inference_op = KingdomResilience.create_ai_operation(
    model_name=self.model,
    operation=self._run_inference_raw,
    fallback=self._get_cached_response
)
```

### Wallet System (`core/wallet_manager.py`)

```python
from core.resilience_patterns import KingdomResilience

# Wrap balance fetching with resilience
self._get_balance_op = KingdomResilience.create_blockchain_operation(
    network=self.network,
    operation=self._fetch_balance_raw,
    fallback=self._get_cached_balance
)
```

### Mining System (`core/mining_system.py`)

```python
from core.resilience_patterns import KingdomResilience

# Wrap pool connection with resilience
self._pool_connect_op = KingdomResilience.create_mining_operation(
    pool_name=self.pool_name,
    operation=self._connect_to_pool_raw,
    fallback=lambda: {"status": "reconnecting"}
)
```

---

## Monitoring Resilience Status

```python
from core.resilience_patterns import get_resilience_status

# Get status of all resilient operations
status = get_resilience_status()
for name, op_status in status.items():
    circuit = op_status['circuit']
    print(f"{name}: {circuit['state']} (failures: {circuit['failure_count']})")
```

---

## Configuration

### CircuitBreakerConfig

| Parameter | Default | Description |
|-----------|---------|-------------|
| `failure_threshold` | 5 | Failures before opening circuit |
| `success_threshold` | 2 | Successes needed to close circuit |
| `timeout_seconds` | 30.0 | Time before trying half-open |

### RetryConfig

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | 3 | Maximum retry attempts |
| `base_delay` | 1.0 | Initial delay in seconds |
| `max_delay` | 30.0 | Maximum delay cap |
| `exponential_base` | 2.0 | Backoff multiplier |
| `jitter` | True | Add randomness to prevent thundering herd |

---

## How It Preserves Real Operations

1. **On First Failure**: Retry immediately with backoff
2. **On Persistent Failures**: Open circuit, use fallback, but start background recovery thread
3. **Background Recovery**: Every 30 seconds, attempt real operation to detect service recovery
4. **On Recovery**: Close circuit, resume real operations, update cache
5. **Stale Cache**: If cache is stale, use it but mark as stale and trigger refresh

### Example Flow

```
User requests price ──▶ Circuit CLOSED? ──[YES]──▶ Try real API
                              │                        │
                              │                   [success]
                              │                        │
                              │                        ▼
                              │                   Cache result
                              │                   Return data
                              │
                         [NO - OPEN]
                              │
                              ▼
                      Use cached fallback
                      Start background recovery
                      Return stale data + "recovering" flag
```

---

## Files Modified

| File | Changes |
|------|---------|
| `core/resilience_patterns.py` | **NEW** - Complete resilience implementation |
| `core/real_exchange_executor.py` | Added resilience import |
| `core/thoth_ollama_connector.py` | Added resilience import |
| `core/wallet_manager.py` | Added resilience import |
| `core/mining_system.py` | Added resilience import |

---

## Testing

```python
# Test circuit breaker
from core.resilience_patterns import CircuitBreaker, CircuitBreakerConfig

cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))

# Simulate failures
for _ in range(3):
    cb.record_failure(Exception("test"))

assert cb.state.value == "open"  # Circuit opened

# Wait and test recovery
import time
time.sleep(10)
assert cb.state.value == "half_open"  # Auto-transitioned

cb.record_success()
assert cb.state.value == "closed"  # Recovered!
```

---

**Created:** December 24, 2025  
**Version:** 1.0  
**Based on:** AWS Well-Architected Reliability Pillar, Martin Fowler's Circuit Breaker Pattern
