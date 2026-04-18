# 🎛️ SOTA 2026: MCP Tools, Voice Commands & AI Command Router

## Overview

Kingdom AI now supports **system-wide control via voice and text commands** from the Thoth AI chat. Users can control devices, automate software, execute trading/mining/wallet actions, and navigate the entire UI using natural language.

---

## 🚀 How to Use

### Text Commands (Chat)
Simply type commands in the Thoth AI chat:
```
"list all windows"
"connect to FL Studio"
"scan devices"
"show my portfolio"
"go to trading tab"
```

### Voice Commands
Speak commands when voice mode is active:
```
"Thoth, open trading"
"scroll down"
"show wallet balance"
"start mining ethereum"
```

---

## 📋 Complete Command Reference

### 🔌 Device Control
| Command | Action | Example |
|---------|--------|---------|
| `scan devices` | Scan all host devices (USB, Bluetooth, Audio, Webcams) | "scan all devices" |
| `list devices` | Show connected devices | "show connected devices" |
| `enable device [name]` | Enable/connect a device | "enable bluetooth speaker" |
| `disable device [name]` | Disable/disconnect a device | "disable webcam" |

### 💻 Software Automation
| Command | Action | Example |
|---------|--------|---------|
| `list windows` | List all open windows | "list all windows" |
| `connect to [software]` | Set active software target | "connect to Chrome" |
| `disconnect` | Disconnect from software | "disconnect from software" |
| `click at X, Y` | Click at screen coordinates | "click at 500, 300" |
| `send keys [text]` | Send keystrokes to connected software | "send keys CTRL+S" |
| `type [text]` | Type text in connected software | "type Hello World" |
| `find control [name]` | Find UI element by name | "find button Save" |
| `invoke control [name]` | Click a UI control | "invoke button Submit" |
| `open [program]` | Launch a program | "open notepad" |

### 💹 Trading
| Command | Action | Example |
|---------|--------|---------|
| `buy [amount] [symbol]` | Place buy order | "buy 0.5 ETH" |
| `sell [amount] [symbol]` | Place sell order | "sell 100 DOGE" |
| `show portfolio` | Get portfolio/holdings | "show my holdings" |
| `check price [symbol]` | Get current price | "check price of BTC" |
| `cancel orders` | Cancel all pending orders | "cancel all orders" |
| `start auto trading` | Enable auto trading | "start auto trading" |
| `stop auto trading` | Disable auto trading | "stop auto trading" |

### ⛏️ Mining
| Command | Action | Example |
|---------|--------|---------|
| `start mining [coin]` | Start mining a coin | "start mining ethereum" |
| `stop mining` | Stop all mining | "stop mining" |
| `show hashrate` | Get mining stats | "show mining stats" |
| `switch pool [pool]` | Change mining pool | "switch pool to ethermine" |

### ⚛️ Quantum Computing
| Command | Action | Example |
|---------|--------|---------|
| `show quantum status` | Check quantum provider status | "show quantum status" |
| `detect quantum hardware` | Scan for available QPUs | "detect quantum hardware" |
| `start quantum mining` | Start quantum-enhanced mining | "start quantum mining" |
| `stop quantum mining` | Stop quantum mining | "stop quantum mining" |
| `list quantum backends` | Show IBM Quantum backends | "list quantum backends" |
| `is quantum hardware available` | Check real QPU availability | "is quantum available" |
| `show quantum capabilities` | Explain quantum features | "show quantum capabilities" |
| `submit quantum job to IBM` | Run circuit on IBM Quantum | "submit quantum job to IBM" |
| `submit quantum job to OpenQuantum` | Run on OpenQuantum SDK | "submit job to OpenQuantum" |
| `configure quantum key` | Set up IBM Quantum API key | "configure quantum key" |
| `configure openquantum key` | Set up OpenQuantum SDK key | "configure openquantum key" |

**Supported Quantum Providers:**
- **IBM Quantum** - Real IBM quantum hardware via qiskit-ibm-provider
- **OpenQuantum SDK** - Multi-provider quantum access (scheduler.openquantum.com)

### ⚛️💹 Quantum Trading (Real-Time)
| Command | Action | Example |
|---------|--------|---------|
| `optimize portfolio` | QAOA portfolio optimization on real QPU | "quantum optimize portfolio" |
| `find arbitrage` | Quantum Grover search for arbitrage | "find quantum arbitrage" |
| `risk analysis` | Quantum-enhanced VaR calculation | "quantum risk analysis" |
| `enable quantum trading` | Enable quantum for all trading | "use quantum for trading" |

**Quantum Trading Capabilities:**
- **Portfolio Optimization** - Uses QAOA algorithm on real quantum hardware
- **Arbitrage Detection** - Grover's algorithm for rapid opportunity scanning
- **Risk Analysis** - Quantum random sampling for VaR estimation

### 💰 Wallet
| Command | Action | Example |
|---------|--------|---------|
| `show balance` | Get wallet balances | "show my balance" |
| `send [amount] [token] to [address]` | Send transaction | "send 0.1 ETH to 0x..." |
| `show addresses` | List wallet addresses | "show my addresses" |

### 📍 Navigation
| Command | Action | Example |
|---------|--------|---------|
| `go to [tab]` | Navigate to tab | "go to trading" |
| `open [tab]` | Navigate to tab | "open wallet" |
| `show [tab]` | Navigate to tab | "show mining" |
| `switch to [tab]` | Navigate to tab | "switch to settings" |

Available tabs: dashboard, trading, blockchain, mining, thoth, code generator, api keys, vr, wallet, settings

### 🖱️ UI Control
| Command | Action | Example |
|---------|--------|---------|
| `scroll up` | Scroll current view up | "scroll up" |
| `scroll down` | Scroll current view down | "scroll down" |
| `fullscreen` | Toggle fullscreen mode | "go fullscreen" |
| `minimize` | Minimize window | "minimize" |
| `refresh` | Refresh current tab | "refresh" |

### 🤖 System
| Command | Action | Example |
|---------|--------|---------|
| `help` | Show command help | "help" |
| `status` | Show system status | "system status" |

---

## 🏗️ Architecture

### Files Created/Modified

#### New Files:
1. **`core/ai_command_router.py`** - AI Command Router
   - Parses natural language into commands
   - Routes to MCP tools or EventBus events
   - Supports 6 command categories

2. **`core/voice_command_manager.py`** - Voice Command Manager
   - System-wide voice command handling
   - Tab navigation callbacks
   - UI control functions

#### Modified Files:
1. **`gui/qt_frames/thoth_qt.py`**
   - Wired AI Command Router into `_handle_message_sent()`
   - Commands execute immediately from chat
   - Results shown in chat with success/failure

2. **`gui/qt_frames/thoth_ai_tab.py`**
   - MCP Tools section now **collapsible** (click to expand)
   - Starts collapsed to keep chat visible
   - Software automation controls
   - Device scanning controls

3. **`gui/kingdom_main_window_qt.py`**
   - Voice Command Manager initialization
   - Tab navigation via voice
   - UI control callbacks (scroll, fullscreen, refresh)

4. **`core/software_automation_manager.py`**
   - Active window target storage
   - Auto-inject connected software into MCP tool calls
   - New tools: `connect_software`, `disconnect_software`, `get_connected_software`

5. **`ai/thoth_mcp.py`**
   - Extended MCP tool dispatch for software automation

---

## 🔄 Data Flow

### Text Command Flow:
```
User types command in Thoth AI chat
    ↓
ChatWidget.message_sent signal
    ↓
ThothQtWidget._handle_message_sent()
    ↓
AICommandRouter.process_and_route()
    ↓
Command detected? → Execute via MCP or EventBus
    ↓
Result shown in chat
    ↓
Message also sent to AI for contextual response
```

### Voice Command Flow:
```
User speaks command
    ↓
VoiceManager transcribes speech
    ↓
Event: voice.recognition published
    ↓
VoiceCommandManager.process_voice_input()
    ↓
Command matched → Callback executed or EventBus published
    ↓
Result spoken back via TTS
```

---

## 📡 EventBus Topics

### Navigation Events:
- `navigate.tab.dashboard`
- `navigate.tab.trading`
- `navigate.tab.blockchain`
- `navigate.tab.mining`
- `navigate.tab.thoth`
- `navigate.tab.code_generator`
- `navigate.tab.api_keys`
- `navigate.tab.vr`
- `navigate.tab.wallet`
- `navigate.tab.settings`

### UI Control Events:
- `ui.scroll.up`
- `ui.scroll.down`
- `ui.fullscreen`
- `ui.minimize`
- `ui.refresh`

### System Events:
- `system.help`
- `system.status`
- `system.tab.switch`
- `system.tab.refresh`
- `system.status.request`

### Trading Events:
- `trading.order.place`
- `trading.portfolio.request`
- `trading.price.request`
- `trading.orders.cancel`
- `trading.auto.start`
- `trading.auto.stop`

### Mining Events:
- `mining.start`
- `mining.stop`
- `mining.stats.request`
- `mining.pool.switch`

### Wallet Events:
- `wallet.balance.request`
- `wallet.transaction.send`
- `wallet.addresses.request`

### MCP Events:
- `mcp.software.connected`
- `mcp.software.disconnected`
- `mcp.devices.scanned`
- `ai.command.execute`
- `ai.command.executed`
- `ai.command.result.*`

---

## 🎛️ MCP Tools Panel (GUI)

The Thoth AI tab has a **collapsible** MCP Tools panel:

### Software Automation Section:
- **Status indicator**: Shows connected software
- **Window dropdown**: Lists all open windows
- **Refresh button**: Rescan available windows
- **Connect button**: Connect to selected window
- **Disconnect button**: Disconnect from software

### Device Control Section:
- **Scan button**: Detect all host devices
- **Status label**: Shows device count

### How to Use:
1. Click "🎛️ MCP TOOLS" to expand the panel
2. Click "🔄" to refresh the window list
3. Select a window from the dropdown
4. Click "🔗 Connect" to set it as the active target
5. Now commands like "send keys" will target that software

---

## 🔧 Technical Details

### AICommandRouter Class
```python
from core.ai_command_router import get_command_router

router = get_command_router(event_bus)
was_command, result = router.process_and_route("list windows")
```

### VoiceCommandManager Class
```python
from core.voice_command_manager import get_voice_command_manager

vcm = get_voice_command_manager(event_bus)
vcm.register_callback('navigate.tab.trading', lambda c, p: switch_to_trading())
```

### Command Pattern Matching
Commands are matched using regex patterns:
```python
COMMAND_PATTERNS = {
    CommandCategory.SOFTWARE: [
        (r"(?:list|show|get)\s+(?:all\s+)?(?:open\s+)?windows?", "list_windows", {}),
        (r"(?:connect|attach)\s+(?:to\s+)?(?:the\s+)?(?:software|window)\s+(.+)", "connect_software", {"name_contains": 1}),
    ],
    # ... more patterns
}
```

---

## ✅ Telemetry & Architecture Preserved

All existing architecture is maintained:
- ✅ EventBus integration intact
- ✅ Telemetry events (`ai.telemetry`, `voice.telemetry`, `ui.telemetry`)
- ✅ Redis Quantum Nexus connectivity
- ✅ Neural Multi-Model Orchestration (ThothLiveIntegration)
- ✅ Voice input/output flow
- ✅ Chat widget functionality
- ✅ Sentience meter integration

---

## 🚀 Quick Start

1. **Launch Kingdom AI** via `kingdom_ai_perfect.py`
2. **Navigate to Thoth AI tab**
3. **Try a command**: Type "list windows" in the chat
4. **Expand MCP Tools**: Click the collapsible panel header
5. **Connect to software**: Select a window and click Connect
6. **Automate**: Use "send keys" or "click at" commands
7. **Voice mode**: Enable voice and speak commands

---

## 📝 Examples

### Automate FL Studio:
```
"list windows"
"connect to FL Studio"
"send keys SPACE"  # Play/pause
"send keys CTRL+S" # Save project
```

### Trading Workflow:
```
"go to trading"
"show portfolio"
"check price of ETH"
"buy 0.1 ETH"
```

### Mining Workflow:
```
"go to mining"
"start mining ethereum"
"show hashrate"
```

### Wallet Workflow:
```
"show my balance"
"show wallet addresses"
```

---

*Last Updated: December 2024*
*Kingdom AI - SOTA 2026 Implementation*
