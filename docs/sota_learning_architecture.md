# SOTA Learning Architecture for Kingdom AI (2025–2026)

## 1. Purpose

This document describes the **state-of-the-art (SOTA) Learning Architecture** used in Kingdom AI, focusing on the `LearningOrchestrator` and how it:

- Learns from **all trading data**:
  - Historical data from the **trading-historical** subsystem.
  - Live data from exchanges, brokers, and blockchains via **real API keys**.
- Provides a **24-hour rolling learning window** with coverage/density metrics and readiness states.
- Surfaces learning telemetry to **Thoth/Ollama** and **ai.telemetry**.


## 2. Core Component: `LearningOrchestrator`

**Location:** `core/learning_orchestrator.py`

The `LearningOrchestrator` is an event-driven backend component built on `BaseComponentV2`. It maintains a 24h rolling window of observations from multiple telemetry sources and emits two key topics:

- `learning.metrics` – aggregated window metrics.
- `learning.readiness` – readiness state for higher-level learning/decision loops.

### 2.1 Responsibilities

- **Ingest** multi-source telemetry from the event bus (trading, risk, strategies, anomaly, blockchain, paper trading, etc.).
- **Maintain** rolling buffers of recent observations per source over a configurable study window (default 24h).
- **Compute**:
  - Per-source metrics: `event_count`, `avg_quality`, `events_per_min`.
  - Global metrics: `total_events`, `active_sources`, `coverage_ratio`, `density_ratio`, `learning_score`.
- **Emit** readiness state reflecting how well the system has observed the environment.

### 2.2 Configuration

Key configuration options (with defaults):

- `study_duration_seconds`: `24 * 3600` (24 hours).
- `min_events_for_ready`: `1000` (minimum events for full readiness).
- `min_sources_for_ready`: `4` (minimum distinct active sources).
- `metrics_emit_interval`: `60` seconds (min interval between emissions).

These are provided via the component `config` and can be tuned per deployment.


## 3. Data Sources: Historical + Live

The Learning Architecture is designed so that **all relevant data flows through the event bus using canonical topics**. As long as both historical and live systems publish to these topics, the `LearningOrchestrator` treats them uniformly.

### 3.1 Live Data (API-Key Powered)

Once the user configures and activates API keys (via the API Key Manager), real-time connectors for exchanges, stock brokers, and web3/RPC nodes start streaming data into the bus. The orchestrator subscribes to these topics:

- **Trading / risk / strategies**:
  - `trading.live_prices`
  - `trading.portfolio.snapshot`
  - `trading.risk.snapshot`
  - `trading.strategy_marketplace.snapshot`
  - `trading.ai.snapshot`
  - `trading.prediction.snapshot`
  - `trading.anomaly.snapshot`

- **Paper autotrade + learning signals**:
  - `autotrade.paper.metrics`
  - `autotrade.readiness`

- **Blockchain / web3 analytics**:
  - `blockchain.performance_update`
  - `blockchain.transaction_recorded`
  - `blockchain.wallet_update`
  - `blockchain.contract_interaction`

These streams are driven entirely by **real API keys**; the orchestrator itself is agnostic to where the data comes from, as long as it arrives on the bus.

### 3.2 Historical Data (`trading-historical`)

The **trading-historical** subsystem stores long-horizon market and trading data (prices, orders, fills, positions, risk snapshots, etc.). It integrates with the Learning Architecture through the same event bus in two primary patterns:

#### Pattern A – Canonical Replay

A historical replay component reads from the historical store and publishes events to the same topics used by live systems. Example:

- Replay last 24h of prices to `trading.live_prices`.
- Replay portfolio/risk snapshots to `trading.portfolio.snapshot` and `trading.risk.snapshot`.

To the `LearningOrchestrator`, these events are indistinguishable from live ones. This allows the learning window to:

- **Bootstrap** quickly by replaying the last 24 hours before or during startup.
- **Learn from the full recent data context**, not just data arriving after the orchestrator starts.

#### Pattern B – Dedicated `trading.historical.*` Topics (Optional)

Alternatively, the historical subsystem may use dedicated topics such as:

- `trading.historical.snapshot`
- `trading.historical.order_flow`

The orchestrator can subscribe to these topics as well and map them into its internal sources (e.g., treating them as `"trading"` or `"learning_signal"`) with appropriate quality hints.

Either way, **the 24h learning window is filled from both historical and live data**, provided that all relevant events are published to the bus.


## 4. Internal Mechanics

### 4.1 Rolling Buffers

The orchestrator maintains per-source deques:

```python
self._buffers: Dict[str, Deque[Tuple[float, float]]]  # (timestamp, quality_score)
```

For each event:

1. Determine `source` (e.g., `"trading"`, `"anomaly"`, `"blockchain"`, `"learning_signal"`).
2. Compute a `quality_score` based on `quality_hint` (`high`, `default`, `low`).
3. Append `(now, quality_score)` to `self._buffers[source]`.
4. Prune entries older than `now - study_duration_seconds` to maintain a rolling window.

### 4.2 Metrics Computation

At most every `metrics_emit_interval` seconds, the orchestrator computes:

- Per source:
  - `event_count = len(buffer)`
  - `avg_quality = sum(quality_scores) / event_count`
  - `events_per_min = event_count / (study_duration_seconds / 60)`

- Global:
  - `total_events = sum(event_count)` across sources.
  - `active_sources = number of sources with event_count > 0`.
  - `coverage_ratio = min(1.0, active_sources / min_sources_for_ready)`.
  - `density_ratio = min(1.0, total_events / min_events_for_ready)`.
  - `learning_score = 0.5 * coverage_ratio + 0.5 * density_ratio`.

The result is published as a `learning.metrics` payload.

### 4.3 Readiness States

Given metrics, readiness is determined as:

- **WARMUP**:
  - Very small `total_events` (e.g., `< max(10, 0.1 * min_events_for_ready)`).
  - Not enough data to draw meaningful conclusions.

- **LEARNING**:
  - Some data, but below `min_events_for_ready` or `min_sources_for_ready`.
  - Or moderate `learning_score` (e.g., between 0.6 and 0.9).

- **READY**:
  - Adequate coverage and density (`learning_score >= 0.9`).

- **DEGRADED**:
  - Data present but coverage/density are poor (`learning_score` low) – e.g., skewed to a single exchange or missing key risk/strategy signals.

A `learning.readiness` event is published with:

- `state`, `reason` (human-readable string), `learning_score`.
- `total_events`, `active_sources`.
- `window_start_ts`, `window_duration_seconds`.


## 5. Wiring into Kingdom AI Main

**File:** `kingdom_ai_perfect.py`

`LearningOrchestrator` is initialized as a first-class component alongside trading, risk management, and paper autotrading:

1. Constructed with `event_bus` and config.
2. `initialize()` and `start()` are awaited.
3. Registered on the event bus under the name `"learning_orchestrator"`.

This ensures it starts consuming events as soon as other components begin publishing live and/or historical data.


## 6. Integration with Thoth/Ollama

**File:** `core/thoth_live_integration.py`

### 6.1 Subscriptions and Caching

Thoth Live Integration subscribes to:

- `learning.metrics  -> _on_learning_metrics`
- `learning.readiness -> _on_learning_readiness`

It caches the latest payloads as:

- `latest_learning_metrics`
- `latest_learning_readiness`

### 6.2 Inclusion in Thoth Analysis Context

When Thoth/Ollama is invoked (e.g., `thoth_analyze_market`), the analysis context includes:

```python
analysis['data_sources']['learning_metrics'] = latest_learning_metrics
analysis['data_sources']['learning_readiness'] = latest_learning_readiness
```

Alongside many other data sources (order book, recent trades, risk snapshots, paper metrics, profit goal telemetry, etc.).

This gives the AI a **direct view of how well the system has learned from the last 24h of data**, sourced from both trading-historical and live API-key streams.

### 6.3 ai.telemetry for Observability

Thoth Live Integration also mirrors learning state into `ai.telemetry`:

- `thoth_ai.learning.metrics` – compact metrics snapshot.
- `thoth_ai.learning.readiness` – current readiness level and rationale.

These events can be consumed by:

- Thoth AI Tab widgets.
- External observability tools (e.g., Grafana, ELK) that subscribe to the bus.


## 7. Ensuring Learning from *All* Data

To guarantee the orchestrator learns from **all trading data**:

1. **Historical Integration**:
   - Ensure the trading-historical system can **replay** or **backfill** at least the last 24 hours of data.
   - Publish replay data onto **canonical topics** (or dedicated `trading.historical.*` topics that the orchestrator subscribes to).

2. **Live Integration via API Keys**:
   - Load and validate exchange/broker/web3 API keys using the API Key Manager.
   - Confirm live connectors are publishing to the expected event-bus topics.

3. **Unified Abstraction**:
   - The orchestrator does **not** distinguish whether a given event is historical replay or live.
   - As long as the event has a timestamp within the last 24 hours and is on a subscribed topic, it contributes to the rolling window and readiness state.

This design means that by the time Thoth/Ollama makes critical decisions, it has:

- A **rich, statistically meaningful** view of the recent environment.
- A clear indicator of **how complete and balanced** that view is.
- Coverage from **trading-historical** + **live API-key telemetry** across trading, risk, anomaly, and blockchain domains.


## 8. Future Extensions

Potential future enhancements include:

- Per-symbol or per-market learning windows (in addition to the global one).
- Explicit tagging of events as `historical` vs `live` in metrics for deeper analysis.
- Integration with MetaLearning for **adaptive threshold tuning** based on performance.
- Additional sources (e.g., on-chain order book or L2 data) wired into the same pattern.
