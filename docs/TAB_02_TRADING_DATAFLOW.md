# TAB 2: TRADING - COMPLETE DATA FLOW MAPPING

## 🎯 OVERVIEW

**Tab Name:** Trading System  
**Purpose:** Real cryptocurrency trading on live exchanges  
**Frontend File:** `gui/qt_frames/trading/trading_tab.py`  
**Backend Files:** `core/trading_system.py` (2183 lines)  
**Event Bus Topics:** `trading.*`, `exchange.*`, `order.*`  
**External APIs:** CCXT (10+ exchanges)

**24h → PREDATOR Mode:** Implemented across core learning + monitoring components. After ~24 hours of continuous operation the system increases scan frequency, lowers confidence gating, and becomes opportunistic/aggressive.

---

## ⚠️ CRITICAL WARNING

**REAL MONEY OPERATIONS:**
- Every button executes REAL trades on REAL exchanges
- Market orders execute IMMEDIATELY at current price
- NO CONFIRMATION DIALOGS (by default)
- Losses are REAL and permanent
- API keys must have trading permissions

**Mode behavior:** This tab supports both an analysis/learning window and an aggressive live posture. When PREDATOR mode activates, opportunity generation and scanning become significantly more aggressive.

---

## 📊 BUTTON MAPPING

### Button 1: QUICK BUY

**Frontend Component:**

```python
# File: gui/qt_frames/trading/trading_tab.py (Line ~245)
self.quick_buy_button = QPushButton("💰 Quick Buy")
self.quick_buy_button.setStyleSheet("""
    background-color: #00AA00;
    color: white;
    font-weight: bold;
""")
```

**Event Listener Setup:**

```python
# Signal connection
self.quick_buy_button.clicked.connect(self._on_quick_buy_clicked)
```

**Event Handler Method:**

```python
def _on_quick_buy_clicked(self):
    """Execute REAL market buy order"""
    try:
        # 1. Get trading parameters from GUI
        symbol = self.symbol_combo.currentText()  # e.g., "BTC/USDT"
        amount = float(self.amount_input.text())
        exchange = self.exchange_combo.currentText()  # e.g., "binance"
        
        # 2. Validate inputs
        if not symbol or amount <= 0:
            self._show_error("Invalid trading parameters")
            return
        
        # 3. Confirm with user (optional safety)
        reply = QMessageBox.question(
            self, 
            'Confirm Trade',
            f'Buy {amount} {symbol} on {exchange}?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # 4. Disable button during execution
        self.quick_buy_button.setEnabled(False)
        self.quick_buy_button.setText("⏳ Buying...")
        
        # 5. Trigger REAL trade via Event Bus
        if self.event_bus:
            self.event_bus.publish('trading.execute_order', {
                'type': 'market',
                'side': 'buy',
                'symbol': symbol,
                'amount': amount,
                'exchange': exchange,
                'timestamp': time.time(),
                'source': 'quick_buy_button'
            })
        
        # 6. Log action
        logger.info(f"🔥 REAL BUY ORDER: {amount} {symbol} on {exchange}")
        
    except Exception as e:
        logger.error(f"Quick buy failed: {e}")
        self._show_error(f"Buy order failed: {str(e)}")
    finally:
        # Re-enable button
        QTimer.singleShot(2000, lambda: self.quick_buy_button.setEnabled(True))
        QTimer.singleShot(2000, lambda: self.quick_buy_button.setText("💰 Quick Buy"))
```

**Event Bus Flow:**

```
User Click "Quick Buy"
    ↓
clicked signal → _on_quick_buy_clicked()
    ↓
Gather: symbol, amount, exchange
    ↓
Validation checks
    ↓
event_bus.publish('trading.execute_order', {...})
    ↓
[Event Bus Routes to Trading System]
    ↓
Trading System receives event
    ↓
Load API keys from APIKeyManager
    ↓
Initialize CCXT exchange object
    ↓
exchange.create_market_order(symbol, 'buy', amount)
    ↓
[REAL API CALL TO EXCHANGE]
    ↓
Exchange executes order
    ↓
Order confirmation returned
    ↓
event_bus.publish('trading.order_filled', {...})
    ↓
GUI receives confirmation
    ↓
Update order history table
    ↓
Update balance display
    ↓
Show success notification
```

**Backend Processing:**

```python
# File: core/trading_system.py
class TradingSystem:
    def __init__(self, event_bus, api_key_manager):
        self.event_bus = event_bus
        self.api_keys = api_key_manager
        self.exchanges = {}
        
        # Subscribe to trading events
        self.event_bus.subscribe('trading.execute_order', self._handle_execute_order)
    
    async def _handle_execute_order(self, event_data):
        """Process REAL trade execution"""
        try:
            # 1. Extract order data
            symbol = event_data['symbol']
            side = event_data['side']
            amount = event_data['amount']
            exchange_name = event_data['exchange']
            
            # 2. Get REAL exchange connection
            exchange = await self._get_exchange(exchange_name)
            
            # 3. Execute REAL market order via CCXT
            logger.info(f"🔥 EXECUTING REAL ORDER: {side} {amount} {symbol}")
            order = await exchange.create_market_order(
                symbol=symbol,
                side=side,
                amount=amount
            )
            
            # 4. Log successful execution
            logger.info(f"✅ ORDER FILLED: {order['id']}")
            logger.info(f"   Price: {order['price']}")
            logger.info(f"   Amount: {order['amount']}")
            logger.info(f"   Cost: {order['cost']}")
            
            # 5. Save to database
            await self._save_order_to_db(order)
            
            # 6. Publish success event
            await self.event_bus.publish('trading.order_filled', {
                'order_id': order['id'],
                'symbol': symbol,
                'side': side,
                'amount': order['amount'],
                'price': order['price'],
                'cost': order['cost'],
                'timestamp': order['timestamp'],
                'status': 'filled'
            })
            
            # 7. Update positions
            await self._update_positions(exchange_name)
            
        except ccxt.InsufficientFunds as e:
            logger.error(f"❌ INSUFFICIENT FUNDS: {e}")
            await self.event_bus.publish('trading.order_failed', {
                'error': 'insufficient_funds',
                'message': str(e)
            })
        
        except ccxt.InvalidOrder as e:
            logger.error(f"❌ INVALID ORDER: {e}")
            await self.event_bus.publish('trading.order_failed', {
                'error': 'invalid_order',
                'message': str(e)
            })
        
        except Exception as e:
            logger.error(f"❌ ORDER FAILED: {e}")
            await self.event_bus.publish('trading.order_failed', {
                'error': 'execution_failed',
                'message': str(e)
            })
    
    async def _get_exchange(self, exchange_name):
        """Get authenticated exchange connection"""
        if exchange_name in self.exchanges:
            return self.exchanges[exchange_name]
        
        # Load API keys
        api_key_data = self.api_keys.get_api_key(exchange_name)
        
        # Initialize CCXT exchange
        exchange_class = getattr(ccxt, exchange_name)
        exchange = exchange_class({
            'apiKey': api_key_data['api_key'],
            'secret': api_key_data['api_secret'],
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        # Cache connection
        self.exchanges[exchange_name] = exchange
        return exchange
```

**API Key Integration:**

```python
# File: core/api_key_manager.py
# Trading System loads keys automatically

from core.api_key_manager import APIKeyManager

api_keys = APIKeyManager()
api_keys.load_api_keys()  # Loads from config/api_keys.json

# Get Binance keys
binance_keys = api_keys.get_api_key('binance')
# Returns: {'api_key': '...', 'api_secret': '...'}

# Initialize exchange with REAL credentials
import ccxt
exchange = ccxt.binance({
    'apiKey': binance_keys['api_key'],
    'secret': binance_keys['api_secret']
})

# Execute REAL trade
order = exchange.create_market_order('BTC/USDT', 'buy', 0.001)
```

**Data Flow Diagram:**

```
┌──────────────────────────────────────────────┐
│         TRADING TAB GUI                       │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐    │
│  │ Symbol  │  │ Amount  │  │ Exchange │    │
│  │Selector │  │  Input  │  │ Selector │    │
│  └────┬────┘  └────┬────┘  └─────┬────┘    │
│       │            │              │          │
│       └────────────┴──────────────┘          │
│                    │                          │
│         ┌──────────▼──────────┐              │
│         │  💰 Quick Buy Button│              │
│         └──────────┬──────────┘              │
└────────────────────┼──────────────────────────┘
                     │ clicked
                     ↓
┌────────────────────────────────────────────┐
│        _on_quick_buy_clicked()             │
│  1. Validate inputs                        │
│  2. Confirm with user                      │
│  3. Disable button                         │
│  4. event_bus.publish()                    │
└────────────────────┬───────────────────────┘
                     │
                     ↓
┌────────────────────────────────────────────┐
│            EVENT BUS                       │
│  Topic: 'trading.execute_order'            │
│  Payload: {symbol, side, amount, exchange} │
└────────────────────┬───────────────────────┘
                     │
                     ↓
┌────────────────────────────────────────────┐
│        TRADING SYSTEM BACKEND              │
│  _handle_execute_order()                   │
│  1. Extract order parameters               │
│  2. Load API keys from APIKeyManager       │
│  3. Initialize CCXT exchange               │
│  4. Execute: exchange.create_market_order()│
└────────────────────┬───────────────────────┘
                     │
                     ↓
┌────────────────────────────────────────────┐
│         CCXT LIBRARY                       │
│  Formats request for exchange API          │
│  Handles authentication                    │
│  Sends HTTP POST request                   │
└────────────────────┬───────────────────────┘
                     │ HTTPS POST
                     ↓
┌────────────────────────────────────────────┐
│     EXCHANGE API (e.g., Binance)           │
│  1. Validates API key signature            │
│  2. Checks account balance                 │
│  3. Matches order with orderbook           │
│  4. Executes trade                         │
│  5. Returns order confirmation             │
└────────────────────┬───────────────────────┘
                     │ HTTP 200 OK
                     ↓
┌────────────────────────────────────────────┐
│        TRADING SYSTEM BACKEND              │
│  1. Receives order confirmation            │
│  2. Saves to database                      │
│  3. Updates positions                      │
│  4. Publishes 'trading.order_filled'       │
└────────────────────┬───────────────────────┘
                     │
                     ↓
┌────────────────────────────────────────────┐
│            EVENT BUS                       │
│  Topic: 'trading.order_filled'             │
│  Payload: {order_id, price, amount, cost}  │
└────────────────────┬───────────────────────┘
                     │
                     ↓
┌────────────────────────────────────────────┐
│         TRADING TAB GUI                    │
│  1. Receives confirmation via Event Bus    │
│  2. Updates order history table            │
│  3. Updates balance display                │
│  4. Shows success notification             │
│  5. Re-enables Quick Buy button            │
└────────────────────────────────────────────┘
```

---

### Button 2: QUICK SELL

**Event Listener:**

```python
self.quick_sell_button.clicked.connect(self._on_quick_sell_clicked)
```

**Implementation:** Same as Quick Buy, but with `side='sell'`

---

### Button 3: ENABLE WHALE TRACKING

**Frontend Component:**

```python
self.whale_tracking_toggle = QPushButton("🐋 Enable Whale Tracking")
self.whale_tracking_toggle.setCheckable(True)
```

**Event Listener:**

```python
self.whale_tracking_toggle.clicked.connect(self._on_whale_tracking_toggled)
```

**Event Handler:**

```python
def _on_whale_tracking_toggled(self, checked):
    """Enable/disable whale tracking"""
    if checked:
        # Enable whale tracking
        self.whale_tracking_toggle.setText("🐋 Whale Tracking: ON")
        
        # Publish event to start monitoring
        self.event_bus.publish('trading.enable_whale_tracking', {
            'enabled': True,
            'threshold': 1000000,  # $1M+ transactions
            'symbols': ['BTC/USDT', 'ETH/USDT']
        })
    else:
        # Disable tracking
        self.whale_tracking_toggle.setText("🐋 Enable Whale Tracking")
        self.event_bus.publish('trading.disable_whale_tracking', {})
```

**Backend Implementation:**

```python
# File: core/trading_system.py
async def _handle_enable_whale_tracking(self, event_data):
    """Monitor large transactions on blockchain"""
    threshold = event_data['threshold']
    
    # Subscribe to mempool APIs
    async for tx in self._monitor_mempool():
        if tx['value_usd'] >= threshold:
            # Large transaction detected!
            await self.event_bus.publish('trading.whale_detected', {
                'tx_hash': tx['hash'],
                'value_usd': tx['value_usd'],
                'from': tx['from'],
                'to': tx['to'],
                'timestamp': tx['timestamp']
            })
```

---

### Button 4: ENABLE COPY TRADING

**Event Listener:**

```python
self.copy_trading_toggle.clicked.connect(self._on_copy_trading_toggled)
```

**Implementation:**

```python
def _on_copy_trading_toggled(self, checked):
    """Enable automated copy trading"""
    if checked:
        # Get target trader address/account
        trader_id = self.trader_input.text()
        
        # Enable copy trading
        self.event_bus.publish('trading.enable_copy_trading', {
            'enabled': True,
            'trader_id': trader_id,
            'copy_percentage': 100,  # Copy 100% of trades
            'max_trade_size': 1000  # Max $1000 per trade
        })
```

**Backend:**

```python
async def _handle_copy_trading(self, event_data):
    """Monitor and copy trader positions"""
    trader_id = event_data['trader_id']
    
    # Monitor target trader's positions
    async for position in self._monitor_trader(trader_id):
        # Replicate the trade
        await self._execute_copy_trade(position)
```

---

### Button 5: ENABLE MOONSHOT DETECTION

**Event Listener:**

```python
self.moonshot_detection_toggle.clicked.connect(self._on_moonshot_toggled)
```

**Implementation:**

```python
def _on_moonshot_toggled(self, checked):
    """Scan for new token launches"""
    if checked:
        self.event_bus.publish('trading.enable_moonshot_detection', {
            'enabled': True,
            'min_liquidity': 100000,  # Min $100K liquidity
            'max_age_hours': 24,  # Launched within 24h
            'networks': ['ethereum', 'bsc', 'polygon']
        })
```

**Backend:**

```python
async def _scan_new_tokens(self, criteria):
    """Scan DEX for new token launches"""
    # Query Uniswap, PancakeSwap, etc.
    new_tokens = await self._query_dex_aggregator(criteria)
    
    for token in new_tokens:
        # Analyze token
        analysis = await self._analyze_token(token)
        
        if analysis['score'] > 0.7:
            # High potential token found!
            await self.event_bus.publish('trading.moonshot_found', {
                'token_address': token['address'],
                'name': token['name'],
                'symbol': token['symbol'],
                'score': analysis['score']
            })
```

---

## 🔗 BLOCKCHAIN INTEGRATION

### On-Chain Verification

**After Trade Execution:**

```python
# File: core/trading_system.py
async def _verify_trade_on_chain(self, order):
    """Verify trade was executed on blockchain"""
    from core.blockchain.kingdomweb3_v2 import KingdomWeb3
    
    blockchain = KingdomWeb3()
    
    # Get transaction hash from order
    tx_hash = order.get('info', {}).get('txHash')
    
    if tx_hash:
        # Query blockchain for confirmation
        tx_receipt = await blockchain.get_transaction_receipt(tx_hash)
        
        if tx_receipt['status'] == 1:
            logger.info(f"✅ Trade verified on-chain: {tx_hash}")
            return True
    
    return False
```

---

## 📡 COMPLETE DATA FLOW

### Full Trading Execution Flow

```
USER ACTION
    ↓
GUI Button Click
    ↓
Event Handler (_on_quick_buy_clicked)
    ↓
Input Validation
    ↓
User Confirmation Dialog
    ↓
event_bus.publish('trading.execute_order')
    ↓
───────────── EVENT BUS ─────────────
    ↓
Trading System Subscriber
    ↓
Load API Keys (APIKeyManager)
    ↓
Initialize CCXT Exchange
    ↓
exchange.create_market_order()
    ↓
───────────── CCXT LIBRARY ─────────────
    ↓
Format API Request
    ↓
Sign Request (HMAC-SHA256)
    ↓
HTTPS POST to Exchange API
    ↓
───────────── EXCHANGE API ─────────────
    ↓
Validate Signature
    ↓
Check Balance
    ↓
Match Order (Orderbook)
    ↓
Execute Trade
    ↓
Return Confirmation (JSON)
    ↓
───────────── BACK TO TRADING SYSTEM ─────────────
    ↓
Parse Response
    ↓
Save to Database
    ↓
Verify on Blockchain (optional)
    ↓
Update Internal Positions
    ↓
event_bus.publish('trading.order_filled')
    ↓
───────────── EVENT BUS ─────────────
    ↓
GUI Subscriber Receives Event
    ↓
Update Order History Table
    ↓
Update Balance Display
    ↓
Show Notification
    ↓
Re-enable Button
    ↓
USER SEES CONFIRMATION
```

---

## 🦁 PREDATOR MODE (24-Hour Transition)

The trading stack contains multiple components that switch behavior after ~24 hours:

- **Learning / readiness**
  - `core/learning_orchestrator.py` emits:
    - `learning.metrics`
    - `learning.readiness` (state becomes `PREDATOR` after 24h)
- **Paper performance simulation (profit-plan evidence)**
  - `core/paper_autotrade_orchestrator.py` listens to:
    - `trading.signal` and `stock.order_submit` (paper-only)
    - `trading.live_prices`, `trading.portfolio.snapshot`, `trading.risk.snapshot`
  - emits:
    - `autotrade.paper.metrics`
    - `autotrade.readiness`
- **Policy layer (advisory profit gating)**
  - `core/live_autotrade_policy.py` queries `LearningOrchestrator.is_trade_allowed(style, size_fraction)`
- **Market monitoring (24/7 scans)**
  - `CONTINUOUS_MARKET_MONITORING_SYSTEM.py`:
    - increases scan frequency after 24h
    - lowers confidence gating used to forward opportunities
    - emits `system.predator_mode_activated`
    - publishes `ollama.live_opportunities`
- **Trading intelligence / anomaly + signals**
  - `core/trading_intelligence.py` (`CompetitiveEdgeAnalyzer`):
    - detects streaming anomalies
    - publishes `trading.anomaly.snapshot`
    - publishes `trading.signal` (confidence gating becomes ultra-low in predator mode)
- **AI strategy execution**
  - `core/ai_trading_system.py`:
    - increases position size and lowers thresholds after 24h

### Key behavioral change

- **Learning window (first ~24h):** higher confidence gating, slower scans.
- **PREDATOR mode (after ~24h):** lower confidence thresholds, faster scans, more opportunities pushed into Thoth/Ollama decision loops.

---

## 🔧 EVENT BUS BINDINGS

| Event Topic | Publisher | Subscriber | Trigger | Data Flow |
|-------------|-----------|------------|---------|-----------|
| `trading.execute_order` | Trading GUI | Trading System | Button Click | Order params → Backend |
| `trading.order_filled` | Trading System | Trading GUI | Order Execution | Order result → GUI |
| `trading.order_failed` | Trading System | Trading GUI | API Error | Error message → GUI |
| `trading.balance_updated` | Trading System | Trading GUI + Wallet | Trade Settlement | New balance → All |
| `trading.whale_detected` | Trading System | Trading GUI | Large TX | Whale alert → GUI |
| `trading.moonshot_found` | Trading System | Trading GUI | New Token | Token info → GUI |
| `exchange.connected` | Trading System | Trading GUI | API Init | Status → GUI |
| `exchange.disconnected` | Trading System | Trading GUI | Connection Lost | Alert → GUI |

---

## 📡 UI TELEMETRY & TELEMETRYCOLLECTOR

The Trading tab emits lightweight UI telemetry events whenever the user performs
key actions such as Quick Buy/Sell or enabling Intelligence Hub tools.

- **Channel:** `ui.telemetry`
- **Component:** `trading`
- **Representative event types:**
  - `trading.quick_buy_clicked` / `trading.quick_sell_clicked`
  - `trading.enable_whale_tracking_clicked`
  - `trading.enable_copy_trading_clicked`
  - `trading.enable_moonshot_detection_clicked`

Example payload shape:

```json
{
  "component": "trading",
  "channel": "ui.telemetry",
  "event_type": "trading.quick_buy_clicked",
  "timestamp": "2025-10-24T12:34:56Z",
  "success": true,
  "error": null,
  "metadata": {"side": "buy", "symbol": "BTC/USDT", "amount": 0.001}
}
```

These events are consumed by the shared **TelemetryCollector**, which aggregates
non-blocking UI telemetry across all tabs for centralized logging and metrics.

## ✅ VERIFICATION

**Test Real Trading (TESTNET RECOMMENDED):**

```bash
# 1. Configure testnet API keys
# Edit config/api_keys.json with testnet credentials

# 2. Launch Kingdom AI
python3 -B kingdom_ai_perfect.py

# 3. Go to Trading tab

# 4. Select:
#    - Exchange: Binance Testnet
#    - Symbol: BTC/USDT
#    - Amount: 0.001

# 5. Click "Quick Buy"

# 6. Monitor logs:
tail -f logs/kingdom_error.log | grep trading

# Expected output:
# 🔥 EXECUTING REAL ORDER: buy 0.001 BTC/USDT
# ✅ ORDER FILLED: order_12345
#    Price: 50000.00
#    Amount: 0.001
#    Cost: 50.00
```

---

**Status:** ✅ COMPLETE - Real trading operations fully mapped

---

## 📅 DECEMBER 2025 UPDATE

### Comprehensive Trading Tab Overhaul

**Date:** December 14, 2025

#### Summary of Changes

The Trading Tab received a comprehensive overhaul to ensure all 35 UI components are correctly wired to their backend data sources and telemetry events.

#### Component Audit Results

| Category | Count |
|----------|-------|
| Tables | 3 |
| Display Panels | 18 |
| Intelligence Hub Cards | 3 |
| Labels/Controls | 10 |
| Progress Bars | 1 |
| **TOTAL** | **35** |

#### Key Fixes Applied

1. **Availability Flags**: Fixed `AI_SECURITY_AVAILABLE`, `EXTENDED_COMPONENTS_AVAILABLE`, `ALL_QUANTUM_AVAILABLE` to use actual import values instead of `getattr()` defaults that returned `False`

2. **Component Initialization**: Made unconditional with try-except and null checks so components initialize even if some imports fail

3. **Stock Brokers Panel**: Fixed to check multiple sources (API key manager, exchange executor) before showing "Configure API keys" message

4. **Feeds Activation**: Complete trading system now initializes on startup via `__init__` instead of only when quick trade is executed

5. **Progress Bar**: Added proper styling (30px height, cyan border, gradient colors) and new analysis timer label

6. **Intelligence Hub Cards**: Added `_update_intelligence_hub_cards()` method for live updates to whale, copy, and moonshot cards

7. **Backend Services**: Added `_start_all_backend_services()` that starts 6 services on initialization:
   - Whale tracking service
   - Copy trading service
   - Moonshot detection service
   - Market data service
   - Risk monitoring service
   - Sentiment analysis service

8. **Periodic Refresh**: Added `_live_data_refresh_timer` (5 sec interval) that calls:
   - `_fetch_live_market_data()`
   - `_fetch_live_whale_data()`
   - `_fetch_live_risk_data()`
   - `_update_all_live_panels()`

#### Telemetry Event Subscriptions (31 Events)

All panels are now connected to their respective telemetry events:

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

#### Related Documentation

See `docs/TRADING_TAB_WIRING_MAP.md` for complete panel-by-panel wiring documentation.
