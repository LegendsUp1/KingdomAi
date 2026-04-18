# Trading Tab Wiring Map (SOTA 2025)

## Overview

- **Frontend**: `gui/qt_frames/trading/trading_tab.py`
- **Key Live Data Sources**:
  - `TradingComponent` (RealExchangeExecutor + RealStockExecutor)
  - `TradingDataFetcher` (whales / top traders / moonshots / market data)
  - `LivePriceFetcher` (HTTP live prices: CryptoCompare / CoinGecko)
  - `WebSocketPriceFeed` + `PriceFeedManager` (Coinbase / Kraken / Bitstamp / Gemini)
  - `LiveTradesFeed` (per-symbol real-time trades via ccxt.pro or REST)

**24h → PREDATOR Mode (implemented):**
- `LearningOrchestrator` transitions readiness to `PREDATOR` after ~24h.
- `ContinuousMarketMonitor` increases scan frequency and lowers confidence gating after ~24h and emits `system.predator_mode_activated`.
- `CompetitiveEdgeAnalyzer` (trading intelligence) reduces confidence gating after ~24h.
- `AITradingSystem` increases position sizing and lowers thresholds after ~24h.

---

## Core Event Bus Topics

- **Market & Orderbook**
  - `trading.order_book_update` → GUI `TradingTab._handle_order_book_update`
  - `trading.market_data_update` → GUI `TradingTab._handle_market_data_update`
  - `trading.market_data` → GUI `TradingTab._handle_real_market_data`

- **Prices**
  - `trading:live_price` → GUI `TradingTab._on_websocket_price_update`
  - `trading.live_prices` → GUI `TradingTab._handle_live_prices`

- **Anomalies & Signals**
  - `trading.anomaly.snapshot` → consumed by learning/analysis (published by `CompetitiveEdgeAnalyzer`)
  - `trading.signal` → consumed by paper autotrade + any live routing logic

- **Portfolio & Brokers**
  - `trading.portfolio.snapshot` → GUI `TradingTab._handle_portfolio_snapshot`
  - `stock.broker.health.snapshot` → GUI `TradingTab._handle_stock_broker_health_snapshot`

- **Trades & Orders**
  - `stock.order_submit` (GUI → TradingComponent)
  - `trading.order_filled` (TradingComponent → GUI)
  - `trading.recent_trades_updated` (TradingActions → GUI)

- **Learning / Autotrade Readiness**
  - `autotrade.paper.metrics` → published by `PaperAutotradeOrchestrator`
  - `autotrade.readiness` → published by `PaperAutotradeOrchestrator`
  - `learning.metrics` → published by `LearningOrchestrator`
  - `learning.readiness` → published by `LearningOrchestrator`

- **PREDATOR Mode Transition**
  - `system.predator_mode_activated` → published by `ContinuousMarketMonitor`

- **Intelligence Hub Data**
  - `trading.whale_data` → GUI `TradingTab._handle_real_whale_data`
  - `trading.top_traders` → GUI `TradingTab._handle_real_trader_data`
  - `trading.moonshots` → GUI `TradingTab._handle_real_moonshot_data`
  - Status topics: `trading.whale.status`, `trading.copy.status`, `trading.moonshot.status`

---

## Thoth AI Overlay → Trading Integration (2025+)

- **Purpose**: Allow the global Thoth AI chat overlay or Thoth AI tab to reason about Trading state and optionally propose UI actions, while keeping the GUI thread non-blocking.
- **Worker**: `ThothAIWorker` in `kingdom_ai/core/ai_engine/ai_worker.py`.

**Event Topics:**

- `ai.request`  
  - Published by ThothQt / ThothAITab and global chat overlay.  
  - Includes `request_id`, `prompt`, `model`, and `source_tab` (e.g., `"trading"`).
- `ai.response`  
  - Published by `ThothAIWorker` after calling Ollama.  
  - Consumed by Thoth UI and voice system.
- `gui.action`  
  - Optional JSON action block at end of the AI response triggers this topic.  
  - `TradingTab` can subscribe or be wired to map specific actions (e.g., toggling auto-trading panels) to existing methods like `_start_auto_trade` / `_stop_auto_trade`.

All of these flows are real, event-driven, and run in background threads on the worker side so the Trading UI remains fully responsive.

---

## UI Panels → Events → Data Sources

### 1. Order Book Panel (Left)

- **Widget**: `_create_order_book_widget()`
  - Header: `"Order Book"`
  - Body: `self.order_book_label` (QLabel, initialized with static sample).

- **Logic**:
  - In-memory model: `OrderBook` class (`self.order_book`).
  - Subscriptions:
    - `order_book_update` (legacy) → `OrderBook.update`
    - `trading.order_book_update` → `TradingTab._handle_order_book_update`
  - Handler:
    - `_handle_order_book_update(event_data)`:
      - Calls `self.order_book.update(event_data)` (if available).
      - Calls `_update_order_book_widget(event_data)`.
  - `_update_order_book_widget`:
    - Extracts `bids` and `asks` from `event_data`.
    - Sorts asks ascending, bids descending.
    - Renders top 10 levels for each side to `self.order_book_label` as text.

- **Backend Producers**:
  - Trading engine / connectors publish `trading.order_book_update` with normalized depth arrays.

---

### 2. Recent Trades Panel (Left)

- **Widget**: `_create_recent_trades_widget()`
  - Header: `"Recent Trades"`
  - Body: `self.recent_trades_label` (QLabel, initialized with static table).

- **Logic**:
  - Subscription:
    - `trading.recent_trades_updated` → `TradingTab._handle_recent_trades_updated`.
  - Handler `_handle_recent_trades_updated(data)`:
    - Expects `{"symbol": str, "trades": [ {timestamp, datetime, price, amount, side, ...}, ... ]}`.
    - Builds a formatted table:
      - Header row: `Time  Side  Price  Size`.
      - Up to 10 latest trades, using ms timestamp or `datetime` to build `HH:MM:SS`.
    - Updates `self.recent_trades_label` with live text.

- **Backend Producers**:
  - `TradingActions.update_recent_trades(symbol, trades)` in `gui/components/trading/trading_actions.py`:
    - Stores into `self.recent_trades`.
    - Publishes `trading.recent_trades_updated` with `symbol` + `trades`.
  - `LiveTradesFeed` (`live_trades_feed.py`):
    - Streams raw trades via WebSocket and records into `trades_history`.
    - Can be wired to call `TradingActions.update_recent_trades` per-symbol.

---

### 3. Price Chart Panel (Center)

- **Widgets**:
  - `self.price_label` (headline price)
  - `self.change_label` (headline 24h change)
  - `self.chart_figure`, `self.chart_ax`, `self.chart_canvas` (Matplotlib chart)

- **Internal State**:
  - `self._price_history: Dict[str, List[Tuple[timestamp, price]]]`.

- **Data Inputs**:
  - `TradingTab._handle_live_prices(data)` (HTTP polling via `LivePriceFetcher` or `PriceFeedManager` snapshots):
    - `data = {"prices": {symbol: {price, change_24h, volume, exchange}}}`.
    - Updates mapped `price_labels` / `change_labels` per symbol when present.
    - Fallback: Sets `self.price_label` from the first symbol.
    - Calls `_append_price_point(symbol, price)` for every symbol.
  - `TradingTab._on_websocket_price_update(price_data)` (WebSocket streaming via `WebSocketPriceFeed`):
    - `price_data = {symbol, price, change_24h?, volume, exchange, ...}`.
    - Updates mapped `price_labels` / `change_labels` when present.
    - Caches into `self.latest_prices[symbol]`.
    - Calls `_append_price_point(symbol, price)`.

- **Chart Update Logic**:
  - `_append_price_point(symbol, price)`:
    - Validates numeric price > 0.
    - Appends `(time.time(), price)` to `self._price_history[symbol]` (max 300 points).
    - Calls `_redraw_price_chart(symbol)`.
  - `_redraw_price_chart(symbol)`:
    - Uses `xs` (timestamps) and `ys` (prices) from `self._price_history[symbol]`.
    - Clears `self.chart_ax`, plots line in `#00FF00`, restyles axes/grid/spines.
    - Calls `self.chart_canvas.draw_idle()`.

- **Net Effect**:
  - Chart and headline price follow the same live prices as the rest of the UI, with both HTTP and WebSocket sources feeding the same history buffer.

---

### 4. Market Data Panel (Intelligence Hub section)

- **Widget**:
  - `self.market_data_display` (QTextEdit in "📡 REAL-TIME MARKET DATA FEEDS" QGroupBox).

- **Data Inputs**:
  - `TradingTab._handle_real_market_data(data)` subscribed to `trading.market_data`:
    - Expects data similar to `TradingDataFetcher.fetch_market_data()` output:
      - `symbol`, `price`, `volume`, `high_24h`, `low_24h`, `change_24h`, `exchange`.
    - Formats into multi-line summary:
      - `Symbol`, `Exchange`, `Price`, `24h Change`, `24h High/Low`, `Volume`.
    - Writes to `self.market_data_display`.

- **Backend Producers**:
  - `TradingDataFetcher.fetch_market_data()` using ccxt.
  - Whichever orchestrator publishes `trading.market_data` events (e.g., `TradingDataFetcher` or RealExchange-based updaters).

---

### 5. Portfolio Card & Stock Brokers Table (Right)

- **Portfolio Card**:
  - Widget: `self.portfolio_label`.
  - Event: `trading.portfolio.snapshot` → `TradingTab._handle_portfolio_snapshot(payload)`.
  - Data Source: `TradingComponent._publish_portfolio_snapshot()`:
    - Aggregates balances from `RealExchangeExecutor.get_exchange_health()` and `RealStockExecutor.get_alpaca_positions()`.
  - Behavior:
    - Shows top N asset balances and approximate stablecoin balance.

- **Stock Brokers Table**:
  - Widget: `self.stock_broker_table` (`QTableWidget`).
  - Event: `stock.broker.health.snapshot` → `TradingTab._handle_stock_broker_health_snapshot(payload)`.
  - Data Source: `RealStockExecutor.get_broker_health()` invoked periodically by `TradingComponent`.

---

### 6. Stock Order Entry (Right)

- **Widgets**:
  - `self.stock_symbol_edit`, `self.stock_side_combo`, `self.stock_type_combo`,
    `self.stock_qty_spin`, `self.stock_price_spin`, `self.stock_submit_btn`.

- **Event Flow**:
  - Click `self.stock_submit_btn` → `_submit_stock_order()`
    - Builds order dict: `{symbol, side, type, quantity, price}`.
    - Publishes `"stock.order_submit"` on `event_bus`.
  - `TradingComponent._register_event_handlers()` subscribes `"stock.order_submit"` and routes to `RealStockExecutor` (Alpaca) for live execution.
  - Fill events publish `trading.order_filled`, handled by `TradingTab._handle_order_filled()` for user feedback.

---

### 7. Intelligence Hub Cards (Whales / Copy / Moonshot)

- **Widgets**:
  - Card content labels stored in `self.intelligence_card_labels['whale'|'copy'|'moonshot']`.

- **Event Flow**:
  - Data topics:
    - `trading.whale_data` → `_handle_real_whale_data`
    - `trading.top_traders` → `_handle_real_trader_data`
    - `trading.moonshots` → `_handle_real_moonshot_data`
  - Producers:
    - `TradingDataFetcher` via:
      - `fetch_whale_transactions()`
      - `fetch_top_traders()`
      - `fetch_moonshot_tokens()`
    - These functions publish their respective events.

---

## Price & Trade Feeds: Backends

### LivePriceFetcher (HTTP)

- File: `gui/qt_frames/trading/trading_live_price_fetcher.py`.
- Publishes `trading.live_prices` every ~10s.
- Primary API: CryptoCompare (with optional API key); fallback: CoinGecko.

### WebSocketPriceFeed + PriceFeedManager

- File: `gui/qt_frames/trading/trading_websocket_price_feed.py`.
- Per-exchange WebSocket connectors (Coinbase, Kraken, Bitstamp, Gemini).
- `WebSocketPriceFeed.price_updated` → `PriceFeedManager._on_price_update` → publishes:
  - `trading:live_price`
  - `market:price_update`
  - `market.price.update`
- Periodic snapshots via `_broadcast_snapshot()` → `trading.live_prices`.

### LiveTradesFeed

- File: `gui/qt_frames/trading/live_trades_feed.py`.
- Maintains `trades_history[symbol]` via ccxt.pro `watch_trades` loop.
- `get_recent_trades(symbol, limit)` for synchronous dereferencing.
- Intended integration:
  - Use new or existing orchestrator to call `TradingActions.update_recent_trades(symbol, recent_trades)`.
  - This publishes `trading.recent_trades_updated` for the GUI.

---

## High-Level Flow Diagram

```mermaid
graph TD
  subgraph Backend
    A[TradingComponent\n(RealExchangeExecutor + RealStockExecutor)]
    B[TradingDataFetcher]
    C[LivePriceFetcher]
    D[WebSocketPriceFeed + PriceFeedManager]
    E[LiveTradesFeed]
    F[TradingActions]
  end

  subgraph EventBus
    EB((Event Bus))
  end

  subgraph GUI
    T[TradingTab]
  end

  %% Portfolio & Brokers
  A -->|trading.portfolio.snapshot| EB
  A -->|stock.broker.health.snapshot| EB

  %% Whales / Traders / Moonshots / Market Data
  B -->|trading.whale_data| EB
  B -->|trading.top_traders| EB
  B -->|trading.moonshots| EB
  B -->|trading.market_data| EB

  %% Prices
  C -->|trading.live_prices| EB
  D -->|trading:live_price| EB
  D -->|trading.live_prices| EB

  %% Recent Trades
  E -->|recent trades per symbol| F
  F -->|trading.recent_trades_updated| EB

  %% Orders
  T -->|stock.order_submit| EB
  EB -->|trading.order_filled| T

  %% GUI subscriptions
  EB --> T
```

---

## Implementation Status (GUI)

- **Order Book Panel**: ✅ live from `trading.order_book_update` (label now reflects live depth).
- **Recent Trades Panel**: ✅ live from `trading.recent_trades_updated` (label shows last trades).
- **Price Chart**: ✅ updated from `_handle_live_prices` + `_on_websocket_price_update` via `_price_history` buffer.
- **Market Data Panel**: ✅ updated from `trading.market_data` via `_handle_real_market_data`.
- **Portfolio/Brokers**: ✅ live from TradingComponent snapshots.
- **Stock Order Entry**: ✅ live via `stock.order_submit` → `TradingComponent` → Alpaca.
- **Intelligence Hub Cards**: ✅ live via `TradingDataFetcher` events.

This document should be kept in sync with any future changes to `trading_tab.py`, `TradingComponent`, `TradingDataFetcher`, `LivePriceFetcher`, `WebSocketPriceFeed`, and `LiveTradesFeed`.

---

## 🔧 DECEMBER 2025 COMPREHENSIVE UPDATE

### Complete Panel Audit (35 UI Components)

#### Tables (3)
| Table | Widget | Backend Source | Telemetry Event | Update Method |
|-------|--------|----------------|-----------------|---------------|
| Exchange Status | `exchange_status_table` | `real_exchange_executor.exchanges` | `exchange.health.snapshot` | `_update_exchange_status_panel()` |
| Venue Stats | `venue_stats_table` | `real_exchange_executor` | `exchange.health.snapshot` | `_update_exchange_status_panel()` |
| Stock Brokers | `stock_broker_table` | `real_stock_executor`, `api_key_manager` | `stock.broker.health.snapshot` | `_update_stock_broker_panel()` |

#### Display Panels (18)
| Panel | Widget | Backend Source | Telemetry Event | Update Method |
|-------|--------|----------------|-----------------|---------------|
| AI Market Analysis | `ai_data_label` | `crypto_prices`, `stock_prices` | `trading.live_prices` | `_update_ai_market_analysis_panel()` |
| AI Prediction | `ai_prediction_display` | `_latest_ai_snapshot`, AI models | `trading.ai.snapshot` | `_update_ai_prediction_panel()` |
| Arbitrage | `arbitrage_display` | `real_exchange_executor`, prices | `trading.arbitrage.snapshot` | `_update_arbitrage_panel()` |
| Sentiment | `sentiment_display` | `sentiment_analyzer`, prices | `trading.sentiment.snapshot` | `_update_sentiment_panel()` |
| Risk | `risk_display` | `drawdown_monitor`, `risk_manager` | `trading.risk.snapshot` | `_update_risk_panel()` |
| Risk Metrics | `risk_metrics_display` | `risk_assessment_core` | `trading.risk.snapshot` | `_update_risk_metrics_panel()` |
| Meme Coins | `meme_display` | `meme_coin_analyzer`, `rug_sniffer` | `meme_coin.scan.complete` | `_update_meme_panel()` |
| Time Series | `timeseries_display` | `time_series_transformer` | `timeseries.prediction.complete` | `_update_timeseries_panel()` |
| Strategy | `strategy_display` | `strategy_coordinator` | `trading.strategy_marketplace.snapshot` | `_update_strategy_panel()` |
| Strategy Status | `strategy_status_display` | `strategy_manager` | `trading.strategy_marketplace.snapshot` | `_update_strategy_status_panel()` |
| ML Pipeline | `ml_display` | Feature extractors, prices | - | `_update_ml_panel()` |
| Prediction | `prediction_display` | ML models, prices | `trading.prediction.snapshot` | `_update_prediction_panel()` |
| Market Data | `market_data_display` | `data_fetcher`, exchanges | `trading.market_data_update` | `_update_market_data_panel()` |
| Copy/Whale | `copy_whale_display` | `whale_tracker`, `copy_trader` | `trading.whale.status`, `trading.copy.status` | `_update_copy_whale_panel()` |
| AI Security | `ai_security_display` | Security components | - | `_update_ai_security_panel()` |
| Quantum | `quantum_display` | Quantum components | - | `_update_quantum_panel()` |
| Extended | `extended_display` | Extended components | - | `_update_extended_panel()` |
| VR Trading | `vr_display` | VR components | - | `_update_vr_panel()` |

#### Intelligence Hub Cards (3)
| Card | Widget | Backend Source | Telemetry Event |
|------|--------|----------------|-----------------|
| Whale Tracking | `intelligence_card_labels['whale']` | `whale_tracker`, `whale_detector` | `trading.whale.status`, `trading.whale_data` |
| Copy Trading | `intelligence_card_labels['copy']` | `copy_trader`, `copy_trading_orchestrator` | `trading.copy.status`, `trading.top_traders` |
| Moonshot Detection | `intelligence_card_labels['moonshot']` | Moonshot detector | `trading.moonshot.status`, `trading.moonshots` |

#### Labels & Controls (10)
| Label | Widget | Backend Source | Telemetry Event |
|-------|--------|----------------|-----------------|
| Price | `price_label` | Exchange tickers | `trading.live_prices`, `trading:live_price` |
| Change | `change_label` | Exchange tickers | `trading.live_prices` |
| Symbol | `symbol_label` | User selection | - |
| Order Book | `order_book_label` | Order book data | `trading.order_book_update` |
| Recent Trades | `recent_trades_label` | Trade history | `trading.recent_trades_updated` |
| Buy Section | `buy_section_label` | Live prices | `trading.live_prices` |
| Sell Section | `sell_section_label` | Live prices | `trading.live_prices` |
| Portfolio | `portfolio_label` | Portfolio manager | `trading.portfolio.snapshot` |
| Auto Trade Status | `auto_trade_status_label` | Auto-trade system | `ai.autotrade.plan.generated` |
| Analysis Timer | `analysis_timer_label` | System clock | Timer (1 sec) |

#### Progress Bars (1)
| Widget | Backend Source | Telemetry Event | Update Method |
|--------|----------------|-----------------|---------------|
| `profit_goal_bar` | Portfolio snapshots | `trading.portfolio.snapshot`, `trading.profit.report` | `_update_profit_goal_from_portfolio_snapshot()` |

---

### Backend Services Started on Init

```python
# Called from setup_trading_intelligence_hub() → _start_all_backend_services()
_start_whale_tracking_service()    # whale_tracker, whale_detector
_start_copy_trading_service()      # copy_trader, copy_trading_orchestrator
_start_moonshot_service()          # moonshot_detector
_start_market_data_service()       # data_fetcher, price_aggregator
_start_risk_monitoring_service()   # drawdown_monitor, risk_assessment_core
_start_sentiment_service()         # sentiment_analyzer, live_sentiment_analyzer
```

---

### Periodic Timers (3)

| Timer | Interval | Purpose | Method |
|-------|----------|---------|--------|
| `_live_data_refresh_timer` | 5 sec | Refresh all live data | `_refresh_all_live_data()` |
| `_analysis_timer` | 1 sec | Update analysis timer label | `_update_analysis_timer()` |
| `auto_trade_timer` | 5 sec | Update auto-trade info | `_update_auto_trade_info()` |

---

### Complete Telemetry Event Subscriptions (31 Events)

```
trading.order_book_update          → _handle_order_book_update()
trading.market_data_update         → _handle_market_data_update()
trading.order_filled               → _handle_order_filled()
trading.whale.status               → _handle_whale_status()
trading.copy.status                → _handle_copy_status()
trading.moonshot.status            → _handle_moonshot_status()
trading:live_price                 → _on_websocket_price_update()
trading.recent_trades_updated      → _handle_recent_trades_updated()
stock.broker.health.snapshot       → _handle_stock_broker_health_snapshot()
trading.portfolio.snapshot         → _handle_portfolio_snapshot()
trading.risk.snapshot              → _handle_risk_snapshot()
trading.sentiment.snapshot         → _handle_sentiment_snapshot()
trading.strategy_marketplace.snapshot → _handle_strategy_marketplace_snapshot()
trading.arbitrage.snapshot         → _handle_arbitrage_snapshot()
trading.ai.snapshot                → _handle_ai_snapshot()
trading.prediction.snapshot        → _handle_prediction_snapshot()
exchange.health.snapshot           → _handle_exchange_health_snapshot()
ai.autotrade.plan.generated        → _handle_autotrade_plan_generated()
meme_coin.scan.complete            → _handle_meme_scan_complete()
rug_check.complete                 → _handle_rug_check_complete()
timeseries.prediction.complete     → _handle_timeseries_prediction_complete()
trading.profit.report              → _handle_profit_report()
trading.intelligence.goal_progress → _handle_goal_progress()
accumulation.status                → _handle_accumulation_status()
accumulation.executed              → _handle_accumulation_executed()
trading.whale_data                 → _handle_real_whale_data()
trading.top_traders                → _handle_real_trader_data()
trading.moonshots                  → _handle_real_moonshot_data()
trading.market_data                → _handle_real_market_data()
trading.live_prices                → _handle_live_prices()
api.key.available.*                → _on_api_key_available()
```

---

### Key Fixes Applied (December 2025)

1. **Availability Flags Fixed**: `AI_SECURITY_AVAILABLE`, `EXTENDED_COMPONENTS_AVAILABLE`, `ALL_QUANTUM_AVAILABLE` now use actual import success values instead of `getattr()` defaults
2. **Component Initialization**: Made unconditional with try-except and null checks
3. **Stock Brokers Panel**: Fixed to check multiple sources (API key manager, exchange executor) before showing "Configure API keys"
4. **Feeds Activation**: Complete trading system now initializes on startup via `__init__` call
5. **Progress Bar**: Added proper styling (30px height, cyan border, gradient) and analysis timer label
6. **Intelligence Hub Cards**: Added `_update_intelligence_hub_cards()` method for live updates
7. **All Panels**: Now fetch from actual backends via `_start_all_backend_services()` and periodic `_refresh_all_live_data()`
