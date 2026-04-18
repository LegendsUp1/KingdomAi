# 🤖 Kingdom AI Live Trading System Documentation

## Overview

The Kingdom AI trading system implements a **two-phase approach** to profitable automated trading:

1. **24-Hour Analysis Phase** - Collects comprehensive market intelligence without executing trades
2. **PREDATOR Live Auto-Trading Phase** - Executes real trades using Thoth/Ollama AI brain with all accumulated intelligence (aggressive hunting after the learning window)

---

## UI Buttons

### 🧠 "START 24H ANALYSIS" Button

**Purpose:** Initiates a 24-hour market analysis and learning window.

**Behavior:**
- Publishes `ai.analysis.start_24h` event
- ThothLiveIntegration runs `_analysis_24h_loop()` 
- Continuously analyzes crypto and stock symbols
- Publishes `ai.autotrade.plan.generated` with `analysis_only=True`
- **NO live trades are executed**
- Timer displays countdown: `🔄 24H ANALYSIS RUNNING... HH:MM:SS remaining`
- Auto-Trade button is **disabled** until analysis completes

**PREDATOR Mode Note (implemented in core systems):**
- Independent of the UI buttons, multiple backend components switch into **PREDATOR MODE** after ~24 hours of continuous operation:
  - `LearningOrchestrator` readiness becomes `PREDATOR`
  - `ContinuousMarketMonitor` increases scan frequency and lowers confidence gating
  - `CompetitiveEdgeAnalyzer` (trading intelligence) reduces confidence thresholds
  - `AITradingSystem` increases position size and lowers thresholds

**Event Published:**
```python
event_bus.publish("ai.analysis.start_24h", {
    "duration_seconds": 86400,
    "max_trade_size_usd": 1000.0,
    "risk_tolerance": "medium"  # low/medium/high
})
```

### 🚀 "START AUTO-TRADING" Button

**Purpose:** Starts live automated trading using Thoth/Ollama AI.

**Prerequisites:**
- Must complete 24H analysis first (`_analysis_verified = True`)
- If clicked before analysis completes, shows warning message

**Behavior:**
- Publishes `ai.autotrade.analyze_and_start` event
- ThothLiveIntegration starts full auto-trade loops
- Executes **real trades** on live exchanges
- Uses all accumulated intelligence for profitable decisions

**PREDATOR Mode Behavior (after the 24h learning window):**
- The system is designed to become more aggressive after the learning window by:
  - Sending more opportunities to Thoth (lower confidence thresholds)
  - Scanning faster
  - Allowing more frequent signals

**Event Published:**
```python
event_bus.publish("ai.autotrade.analyze_and_start", {
    "max_trade_size_usd": 1000.0,
    "risk_tolerance": "medium"
})
```

---

## Intelligence Data Sources

### ThothLiveIntegration `thoth_analyze_market()` includes:

| Data Source | Key | Description |
|-------------|-----|-------------|
| Order Book | `order_book` | Best bid/ask, spread |
| Recent Trades | `recent_trades` | Last price, 24h volume |
| Technical Indicators | `technical_indicators` | RSI, MACD, Bollinger, etc. |
| Sentiment | `sentiment` | News/social sentiment score |
| AI Prediction | `ai_prediction` | ML signal + confidence |
| Quantum Analysis | `quantum` | Quantum entanglement signals |
| Arbitrage | `arbitrage` | Cross-exchange opportunities |
| Risk Metrics | `risk` | Portfolio risk score |
| Learning Metrics | `learning_metrics` | Win-rate, drawdown, CVaR, Kelly |
| RL Online Metrics | `rl_online_metrics` | Q-learning trainer status |
| Policy Diagnostics | `policy_diagnostics` | Why trades fail profit gate |
| Profit Goal | `profit_goal` | Target, current, progress % |
| GUI Intelligence | `gui_complete_intelligence` | Complete TradingTab analysis |
| Live Opportunities | `continuous_monitor_opportunities` | 24/7 monitor findings |

---

## Event Bus Topics

### Analysis Events
| Topic | Publisher | Subscriber | Description |
|-------|-----------|------------|-------------|
| `ai.analysis.start_24h` | TradingTab | ThothLiveIntegration | Start 24h analysis-only mode |
| `ai.analysis.complete` | ThothLiveIntegration | TradingTab | Analysis window completed |
| `ai.autotrade.plan.generated` | ThothLiveIntegration | TradingTab | Updated trading plan |

### Trading Events
| Topic | Publisher | Subscriber | Description |
|-------|-----------|------------|-------------|
| `ai.autotrade.analyze_and_start` | TradingTab | ThothLiveIntegration | Start live auto-trading |
| `ai.autotrade.crypto.enable` | ThothLiveIntegration | Internal | Enable crypto trading loop |
| `ai.autotrade.stocks.enable` | ThothLiveIntegration | Internal | Enable stocks trading loop |
| `ai.autotrade.crypto.disable` | TradingTab | ThothLiveIntegration | Stop crypto trading |
| `ai.autotrade.stocks.disable` | TradingTab | ThothLiveIntegration | Stop stocks trading |

### Live Data Events
| Topic | Publisher | Subscriber | Description |
|-------|-----------|------------|-------------|
| `ollama.live_opportunities` | ContinuousMarketMonitor | ThothLiveIntegration | Real-time opportunities |
| `ollama.analyze_markets` | TradingTab | ThothLiveIntegration | Complete analysis results |
| `trading.market_data_update` | Backend | TradingTab | Live market prices |
| `trading.arbitrage.snapshot` | Backend | TradingTab | Arbitrage opportunities |
| `trading.anomaly.snapshot` | Backend | TradingTab | Market anomalies |
| `strategy.signal` | Strategies | TradingTab | Strategy signals |

### Mode Transition Events
| Topic | Publisher | Subscriber | Description |
|-------|-----------|------------|-------------|
| `system.predator_mode_activated` | ContinuousMarketMonitor | Any | Emitted when monitor switches to PREDATOR mode (scan intervals + confidence threshold change) |

### Learning Events
| Topic | Publisher | Subscriber | Description |
|-------|-----------|------------|-------------|
| `learning.metrics` | LearningOrchestrator | ThothLiveIntegration | Win-rate, drawdown, Kelly |
| `learning.readiness` | LearningOrchestrator | ThothLiveIntegration | Readiness state (transitions to `PREDATOR` after 24h) |
| `learning.rl_online.metrics` | OnlineRLTrainer | ThothLiveIntegration | Q-learning status |
| `autotrade.policy.diagnostics` | OrderRouter | ThothLiveIntegration | Trade rejection reasons |

---

## Trade Execution Flow

```
ThothLiveIntegration._on_ai_analyze_and_start()
    ↓
_discover_crypto_symbols() + _discover_stock_symbols()
    ↓
_build_global_autotrade_plan(crypto_symbols, stock_symbols)
    ↓
Publish "ai.autotrade.plan.generated"
    ↓
_on_ai_crypto_enable() + _on_ai_stocks_enable()
    ↓
Auto-trade loops start (continuous)
    ↓
For each symbol: thoth_analyze_market(symbol)
    ↓
Uses ALL data sources including:
  - latest_gui_market_analysis
  - latest_live_opportunities
  - latest_learning_metrics
  - latest_rl_online_metrics
    ↓
Makes BUY/SELL decision based on signals + profit gate
    ↓
thoth_execute_trade(symbol, side, amount, exchange)
    ↓
RealExchangeExecutor.place_real_order(
    exchange_name="binance",
    symbol="BTC/USDT",
    order_type=OrderType.MARKET,
    side=OrderSide.BUY,
    amount=0.001
)
    ↓
REAL order placed on exchange
    ↓
Publish "thoth.trade.executed"
```

---

## Profit-Focused Learning

### Paper Profit View (`learning.metrics.paper_profit_view`)
- **Global Win Rate**: Used as a performance signal for policy + sizing
- **Max Drawdown**: Used as a regime / risk signal
- **CVaR (Conditional Value at Risk)**: Risk management metric
- **Kelly Fraction**: Optimal position sizing
- **Eligible for Live**: A boolean signal used by policy helpers (can be treated as a gate or as advisory)

### PREDATOR Mode Threshold Changes (implemented)

The following components switch behavior after ~24 hours:

- **LearningOrchestrator** (`core/learning_orchestrator.py`)
  - readiness state becomes `PREDATOR`
  - win-rate/drawdown thresholds become aggressive
- **ContinuousMarketMonitor** (`CONTINUOUS_MARKET_MONITORING_SYSTEM.py`)
  - scan intervals increase in frequency
  - confidence threshold lowered dynamically via `self.confidence_threshold`
- **Trading Intelligence** (`core/trading_intelligence.py`)
  - confidence gating threshold becomes ultra-low in predator mode
- **AITradingSystem** (`core/ai_trading_system.py`)
  - position sizing and thresholding become more aggressive

### RL Online Metrics (`learning.rl_online.metrics`)
- **Total Transitions**: Data points seen by Q-learning
- **Total Updates**: Training iterations
- **Buffer Size**: Experience replay buffer
- **Loss EMA**: Training loss (exponential moving average)
- **Avg Reward EMA**: Average reward achieved
- **Ready**: Boolean indicating model maturity

---

## Chat Widget Integration

The ChatWidget can access live trading data via:

```python
# Get live trading context for AI conversations
context = chat_widget.get_live_trading_context()

# Returns:
{
    "analysis_status": "running" | "complete" | "not_started",
    "analysis_remaining_seconds": 43200,
    "auto_trading_active": True/False,
    "markets_analyzed": [...],
    "live_opportunities": [...],
    "latest_signals": [...],
    "profit_goal": {
        "target_usd": 2000000000000,
        "current_profit_usd": 1234.56,
        "progress_percent": 0.0001
    }
}
```

---

## Files Modified

| File | Changes |
|------|---------|
| `gui/qt_frames/trading/trading_tab.py` | Added `_start_24h_analysis()`, fixed `_start_auto_trading()`, button rewiring |
| `core/thoth_live_integration.py` | Added `ai.analysis.start_24h` handler, `_analysis_24h_loop()`, GUI intelligence in analysis |
| `gui/qt_frames/chat_widget.py` | Added `get_live_trading_context()` method |
| `core/learning_orchestrator.py` | PREDATOR mode state + aggressive thresholds after learning window |
| `CONTINUOUS_MARKET_MONITORING_SYSTEM.py` | PREDATOR mode scan frequency + confidence threshold routing |
| `core/trading_intelligence.py` | PREDATOR mode confidence thresholding for signal generation |
| `core/ai_trading_system.py` | PREDATOR mode sizing + execution thresholding after learning window |

---

## Verification Commands

**Check Analysis Status:**
```python
# In TradingTab
print(f"Analysis verified: {self._analysis_verified}")
print(f"Auto-trading enabled: {self.auto_trading_enabled}")
```

**Check ThothLiveIntegration Data:**
```python
# In ThothLiveIntegration
print(f"GUI Analysis: {self.latest_gui_market_analysis}")
print(f"Live Opportunities: {len(self.latest_live_opportunities or [])}")
print(f"Learning Metrics: {self.latest_learning_metrics}")
```

---

## Expected Log Messages

**24H Analysis Start:**
```
🧠 Status: ANALYZING (24H STUDY WINDOW)
🔄 24H ANALYSIS RUNNING... 23:59:59 remaining
```

**Analysis Complete:**
```
✅ ANALYSIS COMPLETE | Ready for LIVE AUTO-TRADING
```

**Live Trading Start:**
```
🚀 Starting LIVE AUTO-TRADING via Thoth/Ollama AI...
Published ai.autotrade.analyze_and_start
🟢 Status: LIVE AUTO-TRADING ACTIVE (Thoth AI)
🤖 LIVE AUTO-TRADING | Thoth AI Brain Active
```

**Trade Execution:**
```
🤖 Thoth executing REAL BUY order: 0.001 BTC/USDT on binance
🔴 PLACING REAL ORDER: BUY 0.001 BTC/USDT on BINANCE
✅ Thoth trade executed: {...}
```
