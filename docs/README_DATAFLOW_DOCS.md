# 🚀 KINGDOM AI DATA FLOW DOCUMENTATION

## 📖 OVERVIEW

This directory contains **complete front-end to back-end data flow documentation** for all 10 tabs of the Kingdom AI system. Each document traces user interactions from button clicks through the entire system architecture to real-world operations.

---

## ✅ COMPLETED DOCUMENTATION

### **1. Dashboard** (`TAB_01_DASHBOARD_DATAFLOW.md`)
- **Buttons:** 2 (Refresh Status, Reconnect Services)
- **Key Features:** Real-time monitoring, Redis integration, Event Bus subscriptions
- **External Systems:** Redis (port 6380), All system components
- **Signal Connections:** `refresh_btn.clicked` → `refresh_status`, `reconnect_btn.clicked` → `reconnect_services`
- **EventBus Topics:** `system.status.request`, `system.reconnect`, `system.status`, `system.performance`, `ui.telemetry`
- **Status:** ✅ COMPLETE - Full signal/EventBus enumeration (Dec 2025)

### **2. Trading** (`TAB_02_TRADING_DATAFLOW.md`)
- **Buttons:** 5 (Quick Buy, Quick Sell, Whale Tracking, Copy Trading, Moonshot Detection)
- **Key Features:** Real cryptocurrency trading, CCXT integration, Order execution
- **External Systems:** 10+ exchanges (Binance, KuCoin, etc.), Blockchain networks
- **Status:** ✅ COMPLETE - Real trading operations documented
- **⚠️ WARNING:** REAL MONEY operations

### **3. Thoth AI** (`TAB_06_THOTH_AI_DATAFLOW.md`)
- **Buttons:** 2 (TRANSMIT, NEURAL RESET)
- **Key Features:** Real AI responses via Ollama, Dynamic model loading, Voice synthesis
- **External Systems:** Ollama (localhost:11434), TTS engine
- **Status:** ✅ COMPLETE - Full AI integration mapped

---

## 🔄 REMAINING TABS (SUMMARY DOCS NEEDED)

### **4. Mining** (`TAB_03_MINING_DATAFLOW.md`)
- **Buttons:** 9+ (Start/Stop Mining, Quantum Mining, Circuit Update, GPU Detect/Optimize/Benchmark, AI Recommendations, Airdrop Scanning)
- **Key Features:** Traditional + quantum mining, 5 sub-tabs, per-coin configuration
- **External Systems:** Mining pools, Quantum devices, Redis (port 6380)
- **Signal Connections:** 18+ buttons/combos/checkboxes enumerated
- **EventBus Topics:** 25+ subscriptions (`mining.*`, `quantum.*`, `blockchain.*`, `market.*`, `airdrop.*`, `analytics.*`)
- **Status:** ✅ COMPLETE - Full signal/EventBus enumeration (Dec 2025)

### **5. Blockchain** (`TAB_04_BLOCKCHAIN_DATAFLOW.md`)
- **Buttons:** 6 (Check Balance, View Transactions, Deploy/Verify/Call Contract, Optimize Gas)
- **Key Features:** 467+ networks, smart contract interaction, real-time feeds
- **External Systems:** Web3 RPC (Infura, Alchemy, QuickNode, Ankr)
- **Signal Connections:** 6 button clicks enumerated
- **EventBus Topics:** 8 subscriptions, 6 publishes (`blockchain.*`, `market.*`, `api.key.*`)
- **Status:** ✅ COMPLETE - Full signal/EventBus enumeration (Dec 2025)

### **6. Wallet** (`TAB_05_WALLET_DATAFLOW.md`)
- **Buttons:** 10+ (Refresh, Send, Receive, Swap, Portfolio, Analyze, Rebalance, Security Audit, Performance, Accumulation)
- **Key Features:** Multi-chain, coin accumulation intelligence, portfolio management
- **External Systems:** Web3 RPC, DEX aggregators, Price APIs
- **Signal Connections:** 17 buttons/combos/timers enumerated
- **EventBus Topics:** 6 subscriptions, 6 publishes (`wallet.*`, `market.*`, `api.key.*`)
- **Status:** ✅ COMPLETE - Full signal/EventBus enumeration (Dec 2025)
- **⚠️ WARNING:** REAL MONEY operations

### **7. Code Generator** (`TAB_07_CODEGEN_DATAFLOW.md`)
- **Buttons:** 8+ (New, Open, Save, Generate, Execute, Clear, Hot Reload, Language Select)
- **Key Features:** AI code generation via Ollama, hot reload, thread-safe signals
- **External Systems:** Ollama (codellama), Redis health checks
- **Signal Connections:** 18 signals/buttons enumerated
- **EventBus Topics:** 6 subscriptions, 7 publishes (`codegen.*`, `brain.*`, `thoth.*`, `memory.*`)
- **Status:** ✅ COMPLETE - Full signal/EventBus enumeration (Dec 2025)

### **8. API Key Manager** (`TAB_08_APIKEYS_DATAFLOW.md`)
- **Buttons:** 5 (Add, Refresh, Test Connection, Toggle Secrets, Help) + Copy buttons in table
- **Key Features:** Centralized key management, encrypted storage, service distribution
- **External Systems:** CCXT exchanges, RPC providers, Redis (port 6380)
- **Signal Connections:** Toolbar buttons → handlers, `itemSelectionChanged` → `_on_service_selected`
- **EventBus Topics:** `api_keys.loaded`, `api.key.loaded.*`, `api.keys.all.loaded`, `exchange.health.snapshot`, `ui.telemetry`
- **Status:** ✅ COMPLETE - Full signal/EventBus enumeration (Dec 2025)

### **9. VR System** (`TAB_09_VR_DATAFLOW.md`)
- **Buttons:** 7+ (Connect, Calibrate, Reset View, Help, Refresh Env, Load Env, Settings toggles)
- **Key Features:** VR hardware integration, gesture recognition, voice commands, sentience monitoring
- **External Systems:** OpenVR/SteamVR, Meta Quest (ADB), Redis (port 6380)
- **Status:** ✅ COMPLETE - Full signal mappings, EventBus topics, threading documented (2025-12-24)

### **10. Settings** (`TAB_10_SETTINGS_DATAFLOW.md`)
- **Buttons:** 3 (Save Settings, Reset to Defaults, Browse Log Path)
- **Key Features:** System configuration, Redis persistence, theme management, sentience monitoring toggle
- **External Systems:** Redis Quantum Nexus (port 6380), config/settings.json
- **Signal Connections:** `save_btn.clicked` → `save_settings`, `reset_btn.clicked` → `reset_to_defaults`, all input widgets → `_on_setting_changed`
- **EventBus Topics:** `settings:updated`, `settings.save`, `settings:reset`, `settings.query.response`, `theme.changed`, `ui.telemetry`
- **Status:** ✅ COMPLETE - Full signal/EventBus enumeration (Dec 2025)

---

## 🎯 DOCUMENTATION STANDARD

Each documentation file follows this structure:

### **1. Overview**
- Tab name, purpose, files
- Event Bus topics
- External integrations

### **2. Button Mapping**
For every button:
- Frontend component code (`QPushButton`)
- Event listener (`clicked.connect()`)
- Event handler method (full implementation)
- Event Bus flow diagram
- Backend processing
- External API calls
- Response handling

### **3. Data Flow Diagrams**
Complete ASCII flow charts showing:
```
User Click
  ↓
Event Handler
  ↓
Event Bus Publish
  ↓
Backend Subscriber
  ↓
External API
  ↓
Response
  ↓
GUI Update
```

### **4. Event Bus Bindings**
Table of all events:
- Topic name
- Publisher
- Subscriber  
- Trigger condition
- Data payload

### **5. Verification**
- Testing commands
- Expected outputs
- Log monitoring
- Troubleshooting

---

## 🔧 HOW TO USE THESE DOCS

### **For Developers:**

1. **Understanding Button Click Flow:**
   ```bash
   # Example: Trading Quick Buy
   1. Open: docs/TAB_02_TRADING_DATAFLOW.md
   2. Find: "Button 1: QUICK BUY"
   3. Follow complete data flow diagram
   4. See exact code: Line numbers + file paths
   ```

2. **Debugging Issues:**
   ```bash
   # Example: Thoth AI not responding
   1. Open: docs/TAB_06_THOTH_AI_DATAFLOW.md
   2. Check: Event listener connection
   3. Verify: Ollama running (verification section)
   4. Monitor: logs/kingdom_error.log
   ```

3. **Adding New Features:**
   - Copy existing button pattern
   - Use Event Bus for communication
   - Follow naming conventions
   - Update documentation

### **For System Administrators:**

1. **Monitoring Operations:**
   ```bash
   # Check if all systems operational
   grep "✅" docs/TAB_*_DATAFLOW.md
   
   # Monitor specific tab
   tail -f logs/kingdom_error.log | grep trading
   ```

2. **Troubleshooting:**
   - Each doc has "Verification" section
   - Expected log outputs documented
   - Common errors listed

---

## 📊 SYSTEM ARCHITECTURE

### **Event-Driven Design:**

```
┌─────────────┐
│  Frontend   │ (PyQt6 GUI)
│   (Tabs)    │
└──────┬──────┘
       │ clicked.connect()
       ↓
┌─────────────┐
│Event Handler│ (Python methods)
└──────┬──────┘
       │ event_bus.publish()
       ↓
┌─────────────┐
│  Event Bus  │ (Pub/Sub)
│(core/event_bus.py)
└──┬───────┬──┘
   │       │ subscribe()
   ↓       ↓
┌──────┐ ┌──────┐
│Backend│ │Other │
│System │ │Tabs  │
└───┬───┘ └──────┘
    │ External API call
    ↓
┌──────────┐
│ External │ (Exchange, Ollama, RPC)
│  Service │
└─────┬────┘
      │ Response
      ↓
┌─────────────┐
│ event_bus   │
│  .publish() │
└──────┬──────┘
       │
       ↓
┌─────────────┐
│GUI Update   │
│QLabel.setText()
└─────────────┘
```

### **Key Components:**

1. **Frontend (gui/qt_frames/)**
   - 10 tab files
   - PyQt6 widgets
   - Event listeners

2. **Event Bus (core/event_bus.py)**
   - Pub/Sub messaging
   - Topic routing
   - Async handling

3. **Backend Systems (core/)**
   - trading_system.py (2183 lines)
   - mining_system.py (1492 lines)
   - wallet_manager.py
   - api_key_manager.py
   - thoth.py (250K+ lines)

4. **External Services**
   - CCXT (10+ exchanges)
   - Ollama (AI)
   - Web3 (Blockchain)
   - Redis (State)

---

## 🔍 QUICK REFERENCE

### **Button Count Summary:**

| Tab | Buttons | Status |
|-----|---------|--------|
| Dashboard | 2 | ✅ Documented (Dec 2025) |
| Trading | 5 | ✅ Documented |
| Mining | 18+ | ✅ Documented (Dec 2025) |
| Blockchain | 6 | ✅ Documented (Dec 2025) |
| Wallet | 17+ | ✅ Documented (Dec 2025) |
| Thoth AI | 2 | ✅ Documented |
| Code Gen | 18+ | ✅ Documented (Dec 2025) |
| API Keys | 5+ | ✅ Documented (Dec 2025) |
| VR | 7+ | ✅ Documented (Dec 2025) |
| Settings | 3 | ✅ Documented (Dec 2025) |
| **TOTAL** | **80+** | **100% Complete** |

### **External Integrations:**

- **Trading:** Binance, KuCoin, Bybit, Coinbase, Kraken, etc. (CCXT)
- **Blockchain:** 467+ networks via Web3 (Ethereum, BSC, Polygon, etc.)
- **AI:** Ollama (12+ models: llama3.1, mixtral, codellama, etc.)
- **State:** Redis Quantum Nexus (port 6380)
- **Voice:** pyttsx3 (Text-to-Speech)

---

## ⚠️ CRITICAL WARNINGS

### **Real Money Operations:**

**Trading Tab:**
- Market orders execute IMMEDIATELY
- No undo functionality
- Real money is spent
- Losses are permanent
- API keys need trading permissions

**Wallet Tab:**
- Transactions are IRREVERSIBLE
- Wrong address = Lost funds
- Gas fees apply
- Test with small amounts first

**Mining Tab:**
- Real CPU/GPU usage
- Pool fees may apply
- Electricity costs
- Hardware wear

### **Security:**

**API Keys Tab:**
- Store securely (encrypted)
- Never commit to git
- Use read-only keys when possible
- Enable IP whitelisting
- 2FA on all exchanges

---

## 🚀 GETTING STARTED

### **1. Read the Documentation:**
```bash
# Start with Dashboard to understand Event Bus
cat docs/TAB_01_DASHBOARD_DATAFLOW.md

# Then Trading for complex operations
cat docs/TAB_02_TRADING_DATAFLOW.md

# Finally Thoth AI for AI integration
cat docs/TAB_06_THOTH_AI_DATAFLOW.md
```

### **2. Verify System:**
```bash
# Run complete verification
python3 verify_complete_integration.py

# Expected output:
# ✅ PASS - Tab Files
# ✅ PASS - Ollama Brain
# ✅ PASS - Backend Systems
# 🔥 ALL SYSTEMS VERIFIED!
```

### **3. Test Individual Tabs:**
```bash
# Test Dashboard
python3 -B kingdom_ai_perfect.py
# Go to Dashboard tab → Click "Refresh Status"

# Test Thoth AI (requires Ollama)
ollama serve &
python3 -B kingdom_ai_perfect.py
# Go to Thoth AI → Type "Hello" → Click "TRANSMIT"
```

---

## 📝 CONTRIBUTING

### **Adding New Documentation:**

1. Follow existing format (use TAB_01 as template)
2. Include ALL buttons with complete data flow
3. Add Event Bus bindings table
4. Include verification commands
5. Update DATAFLOW_MASTER_INDEX.md

### **Updating Existing Docs:**

1. Maintain consistent structure
2. Update line numbers if code changes
3. Test all verification commands
4. Add date to "Last Updated" section

---

## 🔗 RELATED FILES

- `COMPLETE_SYSTEM_FILES_MAP.md` - All 300+ files
- `COMPLETE_CONNECTIONS_VERIFIED.md` - Integration verification
- `TAB_BY_TAB_CONFIG.md` - Configuration details
- `verify_complete_integration.py` - Automated verification

---

## 📞 SUPPORT

**For Issues:**
1. Check relevant tab documentation
2. Run verification commands
3. Monitor logs: `tail -f logs/kingdom_error.log`
4. Check Event Bus activity

**For Questions:**
- See DATAFLOW_MASTER_INDEX.md for overview
- Each tab doc has detailed explanations
- Code has inline comments with references

---

## ✅ STATUS

**Documentation Complete:** 10/10 tabs (100%)  
**Buttons Documented:** 80+/80+ (100%)  
**Lines of Documentation:** ~12,000+  
**Diagrams:** 30+ ASCII flow charts  
**Code Examples:** 120+ snippets  

**All tabs fully enumerated with:**
- Signal connections (line numbers, signals, handlers)
- EventBus subscriptions and publishes
- Backend integration points

---

**Created:** October 24, 2025  
**Last Updated:** December 24, 2025  
**Version:** 2.0  
**Status:** ✅ COMPLETE - 100% Documented

---

## 📋 CHANGELOG (Dec 2025 Session)

- **Dashboard Tab:** Updated with actual signal connections (`refresh_status`, `reconnect_services`) and EventBus topics (`system.status.request`, `system.reconnect`, `system.status`, `system.performance`, `dashboard.metrics_updated`, `ui.telemetry`)
- **API Keys Tab:** Updated with actual signal connections (toolbar buttons, tree selection, copy buttons) and EventBus topics (`api_keys.loaded`, `api.key.loaded.*`, `api.keys.all.loaded`, `api_key_manager.*`, `exchange.health.snapshot`, `ui.telemetry`)
- **Settings Tab:** Updated with actual signal connections (`save_settings`, `reset_to_defaults`, `_select_log_path`, `_on_sentience_monitoring_toggled`, all input widgets) and EventBus topics (`settings:updated`, `settings.save`, `settings:reset`, `settings.query.response`, `theme.changed`, `ui.telemetry`)
- **VR Tab:** Previously updated with complete enumeration (Dec 2025)
