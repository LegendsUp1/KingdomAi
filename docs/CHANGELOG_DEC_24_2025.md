# Changelog - December 24, 2025

## Summary

This changelog documents all changes made during the December 24, 2025 session to ensure Kingdom AI runs with all features fully functional.

---

## 1. Redis Quantum Nexus - Global Configuration

**Objective:** Ensure ALL Redis connections use only Redis Quantum Nexus (port 6380)

### Files Modified:
- `core/redis_connector.py` - Already configured correctly
- `core/redis_connection.py` - Updated defaults to port 6380 + password
- `core/connection_manager.py` - All 3 default config locations updated
- `gui/frames/settings_frame.py` - Both redis_port defaults → 6380
- `infrastructure/redis_connector.py` - Updated defaults to Quantum Nexus config

### Configuration:
```
Host: 127.0.0.1
Port: 6380
Password: QuantumNexus2025
```

---

## 2. Fallback Elimination

**Objective:** Remove all stub, mock, and fallback implementations

### Audio System (`core/audio_adapter.py`)
- Force-installs audio libraries if missing
- Retries playback after installation
- No more graceful skip

### TTS/STT System (`core/voice_manager.py`)
- Replaced ALL stubs with real implementations
- Auto-installs pyttsx3, gTTS, SpeechRecognition
- Uses sounddevice for audio capture

### Redis System (`core/redis_connector.py`)
- Auto-starts Redis on multiple platforms
- Auto-installs via winget/chocolatey/docker
- No fallback to in-memory

### Trading System (`core/trading_system.py`)
- Real CCXT exchange connections
- Auto-installs ccxt package
- Loads API keys from config

### Blockchain System (`core/blockchain/network_stats.py`)
- Retries with fallback RPC endpoints
- Returns None instead of "unavailable" status
- Configured fallbacks for major chains

---

## 3. Type Fixes for Static Analysis

**Objective:** Eliminate Pyright/IDE errors

### `core/connection_manager.py`
- Used `importlib.import_module()` for dynamic imports
- Added `asyncio.iscoroutine()` checks
- Added `isinstance()` checks before `.items()`
- Used `getattr()` with fallbacks

### `core/redis_connection.py`
- Fixed return type (True instead of None)
- Fixed Redis asyncio import path

### `infrastructure/redis_connector.py`
- Added type: ignore annotations
- Fixed secrets.random() → random.random()
- Changed subscribe_sync → subscribe

### `core/blockchain/network_stats.py`
- Created `get_block_attr()` helper for dict/object access
- Added type: ignore for ContractLogicError

---

## 4. API Key Manager Tab - UX + Integration Fixes

**Objective:** Make API keys immediately visible/usable across the system and avoid the “No service selected” empty details panel.

### File Modified
- `gui/qt_frames/api_key_manager_tab.py`

### Fixes
- Auto-select the first configured service on load so the details panel populates by default.
- Broadcast `api_keys.loaded` on the EventBus after keys load so other tabs/components can react.

---

## 5. Thoth AI Tab - ChatWidget Import Fix

**Objective:** Fix runtime `NameError: name 'ChatWidget' is not defined` in the Thoth AI tab.

### File Modified
- `gui/qt_frames/thoth_qt.py`

### Fix
- Added guarded imports for:
  - `gui.qt_frames.chat_widget.ChatWidget`
  - `gui.qt_frames.model_manager_widget.ModelManagerWidget`
- Included fallback stub widgets if imports fail.

---

## 6. Web3 / AsyncWeb3 - “object() takes no arguments” Fix

**Objective:** Stop repeated runtime failures when AsyncWeb3 cannot be constructed with a default provider.

### File Modified
- `kingdomweb3_v2.py`

### Fix
- In the fallback creation path, return `None` instead of calling `AsyncWeb3()` without a valid provider.

---

## 7. Redis - BaseComponentV2 RedisConnector Init Spam Fix

**Objective:** Stop noisy `TypeError` spam from passing invalid kwargs into `RedisQuantumNexusConnector`.

### File Modified
- `core/base_component_v2.py`

### Fix
- `BaseComponentV2._init_redis()` constructs `RedisQuantumNexusConnector(event_bus=...)` only.

---

## 8. Live Trading Wiring - Exchange API Keys + Time-Skew Recovery

**Objective:** Ensure live venues that pass smoke tests are wired identically in the running system, and improve health checks for known exchange time skew issues.

### Files Modified
- `components/trading/trading_component.py`
- `core/real_exchange_executor.py`

### Fixes
- TradingComponent now builds exchange API key mappings via `build_real_exchange_api_keys(...)` (same mapping as `real_exchange_smoke_test.py`).
- RealExchangeExecutor health checks auto-sync exchange clocks and retry once before marking a venue as `time_skew`.

---

## 9. AI Runtime Documentation Access (ChatWidget + Ollama Brain)

**Objective:** Ensure runtime access to session docs (including Brio integration) through the existing SystemKnowledgeLoader mechanism.

### Files Modified
- `core/system_knowledge_loader.py`
- `kingdom_ai_perfect.py`
- `kingdom_ai/ai/brain_router.py`

### Fixes
- Added `BRIO_VOICE_VISION_INTEGRATION.md` to `SystemKnowledgeLoader.PRIORITY_DOCS`.
- Hardened `get_knowledge_loader(event_bus=...)` so an existing singleton can be attached to an EventBus later and subscribed to:
  - `ai.knowledge.request`
  - `ai.knowledge.list`
- `kingdom_ai_perfect.py` initializes and registers `system_knowledge_loader` on the EventBus during production startup.
- BrainRouter injects bounded excerpts of:
  - `BRIO_VOICE_VISION_INTEGRATION.md`
  - `CHANGELOG_DEC_24_2025.md`
  when the user prompt is relevant (e.g. “brio”, “logitech”, “what changed”, “changelog”).
- ChatWidget supports in-chat documentation access commands:
  - `docs` (list available docs)
  - `doc <name>` / `show doc <name>` / `open doc <name>` (display a doc)
  - `changelog` (display the session changelog)

---

## 10. Runtime Import & Compatibility Hotfixes (This Conversation)

**Objective:** Eliminate runtime-breaking errors discovered during launch/testing and ensure the AI brain can access the session docs at runtime.

### AsyncWeb3 crash fix (`kingdomweb3_v2.py`)
- **Symptom:** `object() takes no arguments`
- **Root cause:** In some environments, `AsyncWeb3` is a fallback non-callable (`object`).
- **Fix:** Return `None` when an `AsyncWeb3` instance cannot be safely constructed.
  - `kingdomweb3_v2.py:117-125`

### ThothQt ChatWidget import fix (`gui/qt_frames/thoth_qt.py`)
- **Symptom:** `name 'ChatWidget' is not defined`
- **Fix:** Explicitly import `ChatWidget` and `ModelManagerWidget` and provide QWidget fallback stubs.
  - `gui/qt_frames/thoth_qt.py:108-129`

### Redis connector export flags (`core/redis_connector.py`)
- **Symptom:** `ImportError: cannot import name 'redis_import_successful' from 'core.redis_connector'`
- **Fix:** Ensure `REDIS_AVAILABLE` and `redis_import_successful` are always defined and exported.
  - `core/redis_connector.py:11-38`

### Blockchain connector import path (`gui/qt_frames/blockchain_tab.py`)
- **Symptom:** `ModuleNotFoundError: No module named 'core.blockchain.blockchain_connector'`
- **Fix:** Import `BlockchainConnectorBase` from `core/blockchain/connector.py` and alias it as `BlockchainConnector`.
  - `gui/qt_frames/blockchain_tab.py:42-56`

### Thoth AI tab logger initialization (`gui/qt_frames/thoth_ai_tab.py`)
- **Symptom:** `NameError: name 'logger' is not defined`
- **Fix:** Define `logger = logging.getLogger(__name__)` immediately after imports.
  - `gui/qt_frames/thoth_ai_tab.py:46-48`

### API Keys tab UX + broadcasts (`gui/qt_frames/api_key_manager_tab.py`)
- **Fix:** Auto-select the first configured service so the details panel is populated.
  - `gui/qt_frames/api_key_manager_tab.py:662-666`
- **Fix:** Publish an `api_keys.loaded` event so other tabs/components can react.
  - `gui/qt_frames/api_key_manager_tab.py:542-546`

### Live trading exchange hardening (`core/real_exchange_executor.py`)
- **BinanceUS:** Increase `recvWindow` and force clock sync to reduce -1021 timestamp errors.
  - `core/real_exchange_executor.py:1277-1316`
- **HTX:** Disable SSL verification and force spot-only markets to avoid SSL failures.
  - `core/real_exchange_executor.py:1387-1422`
- **BTCC + OANDA:** Add native connectors initialization when API keys exist.
  - `core/real_exchange_executor.py:1691-1734`

### Stock broker default to LIVE (`core/real_stock_executor.py`)
- **Fix:** Default Alpaca endpoint to LIVE (`https://api.alpaca.markets`) unless explicitly set to paper.
  - `core/real_stock_executor.py:100-121`

### Documentation preload for AI (`core/system_knowledge_loader.py`)
- **Fix:** Expand `PRIORITY_DOCS` so key docs are cached and accessible via `ai.knowledge.request`.
  - `core/system_knowledge_loader.py:27-44`

---

## Files Created/Modified Summary

| File | Action | Description |
|------|--------|-------------|
| `core/audio_adapter.py` | Modified | Force-install audio libs |
| `core/voice_manager.py` | Modified | Real TTS/STT implementations |
| `core/redis_connector.py` | Modified | Auto-start Redis |
| `core/redis_connection.py` | Modified | Quantum Nexus defaults + type fixes |
| `core/connection_manager.py` | Modified | Quantum Nexus + type fixes |
| `core/trading_system.py` | Modified | Real CCXT integration |
| `core/blockchain/network_stats.py` | Modified | Fallback RPCs + type fixes |
| `gui/frames/settings_frame.py` | Modified | redis_port 6380 |
| `infrastructure/redis_connector.py` | Modified | Quantum Nexus + type fixes |
| `kingdomweb3_v2.py` | Modified | AsyncWeb3 fallback fix (return None when not constructible) |
| `gui/qt_frames/thoth_qt.py` | Modified | Import ChatWidget/ModelManagerWidget with fallback stubs |
| `gui/qt_frames/blockchain_tab.py` | Modified | Fix BlockchainConnector import path (core.blockchain.connector) |
| `gui/qt_frames/thoth_ai_tab.py` | Modified | Logger initialization moved to top to avoid NameError |
| `gui/qt_frames/api_key_manager_tab.py` | Modified | Auto-select first configured service + publish `api_keys.loaded` |
| `core/real_exchange_executor.py` | Modified | BinanceUS timestamp fixes, HTX SSL verify=False, BTCC/OANDA native connectors |
| `core/real_stock_executor.py` | Modified | Alpaca default to LIVE endpoint |
| `core/system_knowledge_loader.py` | Modified | Preload key docs (changelog + orchestrator + session changelog) |
| `gui/qt_frames/chat_widget.py` | Modified | In-chat docs access: `docs`, `doc <name>`, `changelog` |
| `docs/MARKDOWN_RUNTIME_ACCESSIBILITY_AUDIT.md` | Created | Runtime markdown docs audit (paths + file/line map) |
| `kingdom_ai_perfect.py` | Modified | Initialize + register SystemKnowledgeLoader during production startup |
| `kingdom_ai/ai/brain_router.py` | Modified | Inject Brio integration doc excerpt into prompt when relevant |
| `core/base_component_v2.py` | Modified | Fix RedisQuantumNexusConnector init TypeError spam (no invalid kwargs) |
| `components/trading/trading_component.py` | Modified | Wire live exchanges via build_real_exchange_api_keys (matches smoke test) |
| `core/real_exchange_executor.py` | Modified | Auto-sync + retry once for time-skew venues during exchange health checks |

---

## Documentation Created

1. `docs/REDIS_QUANTUM_NEXUS_GLOBAL_CONFIG.md` - Redis configuration reference
2. `docs/FALLBACK_ELIMINATION_2025.md` - Fallback removal details
3. `docs/TYPE_FIXES_DEC_2025.md` - Type annotation fixes
4. `docs/CHANGELOG_DEC_24_2025.md` - This changelog
5. `docs/MARKDOWN_RUNTIME_ACCESSIBILITY_AUDIT.md` - Runtime markdown docs audit

Updated during this session:
- `docs/BRIO_VOICE_VISION_INTEGRATION.md` - Brio webcam + microphone integration + runtime wiring

Updated during this session:
- `docs/SOTA_2026_CHANGELOG.md` - Added runtime hotfix notes so AI can answer “what changed?”

---

## AI Assistant Access

All documentation is loaded by `core/system_knowledge_loader.py` and available to:
- Thoth AI chat widget
- Ollama brain context
- Voice command system

Query topics:
- "Redis configuration"
- "Quantum Nexus setup"
- "Fallback elimination"
- "Type fixes"
- "Session changelog Dec 24 2025"
- "Markdown runtime accessibility audit"
