# KingdomBrainOrchestrator - Unified AI Brain & Subsystem Orchestrator

## Overview

The `KingdomBrainOrchestrator` is a singleton runtime orchestrator that centralizes the management of Kingdom AI's brain components (Thoth AI, Ollama Brain, BrainRouter) and all major subsystems (trading, mining, wallet, blockchain, voice, code generation, VR, visual canvas).

**Location:** `core/kingdom_brain_orchestrator.py`

## Key Features

### 1. Single Shared EventBus
- Owns and manages the shared `EventBus` instance
- All components communicate through this unified event system
- Prevents fragmented event routing

### 2. Unified AI Request Flow
```
User Input → ai.request → UnifiedAIRouter → brain.request → BrainRouter → ai.response → ai.response.unified
```

- **No duplicate responses** - ThothAIWorker operates in "features-only" mode
- Legacy events are bridged to canonical handlers
- Deduplication window prevents response spam

### 3. Integrated Components

| Component | Role | Event Subscriptions |
|-----------|------|---------------------|
| **BrainRouter** | Multi-LLM orchestrator | `brain.request`, `visual.request` |
| **UnifiedAIRouter** | Request bridging & deduplication | `ai.request` → `brain.request` |
| **SystemContextProvider** | Self-awareness context | Provides tabs, components, file structure |
| **LiveDataIntegrator** | Real-time operational data | Trading, mining, blockchain, wallet data |
| **AICommandRouter** | Natural language → system events | Parses commands, publishes actions |
| **VoiceCommandManager** | Voice/text command processing | `voice.command`, `text.command` |
| **ThothAIWorker** | SOTA 2025 features | Vision, sensor, voice, memory (no ai.request) |

### 4. ThothAIWorker Features (Active Without Duplicates)

| Feature | Description |
|---------|-------------|
| **Vision Context** | Face/emotion analysis, object detection, pose estimation |
| **Sensor State** | Hardware sensors, motion, orientation tracking |
| **Voice Context** | Speech recognition, audio awareness, last transcript |
| **Conversation Memory** | JSONL persistence, long-range history summary |
| **Tab-Specific Prompts** | Safety prompts for trading/wallet/mining/blockchain |
| **Biometric Safety** | Stress/emotion-aware response adaptation |
| **GUI Actions** | ACTION: JSON block extraction for UI automation |
| **Telemetry** | Latency, prompt/response character metrics |

### 5. Event Aliases (Legacy → Canonical)

| Legacy Event | Canonical Event |
|-------------|-----------------|
| `thoth:code:generate` | `code.generate` |
| `thoth:request:generate_code` | `code.generate` |
| `codegen.request` | `code.generate` |
| `visual.generate` | `brain.visual.request` |
| `visual.request` | `brain.visual.request` |
| `thoth:request` | `ai.request` |
| `voice.command.text` | `text.command` |

## Usage

### Basic Initialization (via launch_kingdom.py)

```python
from core.kingdom_brain_orchestrator import initialize_brain_orchestrator

# During app startup
orchestrator = await initialize_brain_orchestrator(event_bus=event_bus)
```

### Accessing Components

```python
from core.kingdom_brain_orchestrator import get_brain_orchestrator

orchestrator = get_brain_orchestrator()

# Access individual components
brain_router = orchestrator.brain_router
trading_system = orchestrator.get_component('trading_system')
thoth_worker = orchestrator.get_component('thoth_ai_worker')

# Get all registered components
all_components = orchestrator.get_all_components()
```

### Getting Stats

```python
stats = orchestrator.get_stats()
# Returns:
# {
#     "initialized": True,
#     "components_count": 12,
#     "components": ["brain_router", "unified_ai_router", ...],
#     "event_aliases_count": 7,
#     "brain_router_active": True,
#     "unified_router_active": True
# }
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KingdomBrainOrchestrator                         │
│                         (Singleton)                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐    │
│  │  EventBus   │◄───│ UnifiedAIRouter  │◄───│   ai.request    │    │
│  │  (Shared)   │    │                  │    │   (from GUI)    │    │
│  └──────┬──────┘    └────────┬─────────┘    └─────────────────┘    │
│         │                    │                                       │
│         │                    ▼                                       │
│         │           ┌──────────────────┐                            │
│         │           │   BrainRouter    │◄─── SystemContextProvider  │
│         │           │  (Multi-LLM)     │◄─── LiveDataIntegrator     │
│         │           └────────┬─────────┘                            │
│         │                    │                                       │
│         │                    ▼                                       │
│         │           ┌──────────────────┐                            │
│         │           │   ai.response    │───► ai.response.unified    │
│         │           └──────────────────┘                            │
│         │                                                            │
│  ┌──────┴─────────────────────────────────────────────────────┐    │
│  │                    Registered Subsystems                     │    │
│  ├─────────────┬─────────────┬─────────────┬─────────────────┤    │
│  │ Trading     │ Mining      │ Wallet      │ Code Generator  │    │
│  │ System      │ System      │ Manager     │                 │    │
│  └─────────────┴─────────────┴─────────────┴─────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              ThothAIWorker (Features-Only Mode)               │  │
│  ├─────────────┬─────────────┬─────────────┬────────────────────┤  │
│  │ Vision      │ Sensor      │ Voice       │ Conversation       │  │
│  │ Context     │ State       │ Context     │ Memory             │  │
│  └─────────────┴─────────────┴─────────────┴────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Why This Design?

### Problem: Duplicate AI Responses
Previously, multiple components (ThothAI, ThothAIWorker, BrainRouter) all subscribed to `ai.request`, causing duplicate or conflicting responses.

### Solution: Unified Routing
1. **UnifiedAIRouter** is the ONLY subscriber to `ai.request`
2. It bridges to `brain.request` for **BrainRouter** to handle
3. **ThothAIWorker** runs in "features-only" mode (`subscribe_to_ai_request=False`)
4. All responses go through `ai.response.unified` for deduplication

### Benefits
- ✅ Single response per user request
- ✅ All ThothAIWorker features (vision, memory, etc.) still active
- ✅ Legacy event names still work via aliases
- ✅ Easy to extend with new components
- ✅ Centralized stats and debugging

## Configuration

### Disabling ThothAIWorker AI Request Subscription

```python
from kingdom_ai.core.ai_engine.ai_worker import initialize_thoth_ai_worker

# Features-only mode (default in orchestrator)
worker = initialize_thoth_ai_worker(
    event_bus=event_bus,
    memory_manager=None,
    subscribe_to_ai_request=False  # No ai.request handling
)

# Full mode (legacy, causes duplicate responses if BrainRouter is active)
worker = initialize_thoth_ai_worker(
    event_bus=event_bus,
    subscribe_to_ai_request=True  # Handles ai.request directly
)
```

## Files Modified

| File | Changes |
|------|---------|
| `core/kingdom_brain_orchestrator.py` | **NEW** - Main orchestrator implementation |
| `launch_kingdom.py` | Uses orchestrator instead of scattered init |
| `kingdom_ai/core/ai_engine/ai_worker.py` | Added `subscribe_to_ai_request` param |

## Troubleshooting

### "Duplicate AI responses"
- Ensure only ONE of these is active:
  - BrainRouter + UnifiedAIRouter (recommended)
  - ThothAIWorker with `subscribe_to_ai_request=True` (legacy)

### "ThothAIWorker features not working"
- Check orchestrator initialized ThothAIWorker
- Verify vision/sensor/voice events are being published

### "Legacy events not working"
- Check event aliases are set up in `_setup_event_aliases()`
- Verify `orchestrator.ready` event was published

## SOTA 2026 Reliability Patterns

Based on extensive web research of SOTA 2026 AI orchestration patterns (Microsoft Azure Architecture, Vellum AI, LangGraph), the following patterns are implemented:

### 1. Circuit Breaker Pattern
```python
# Get circuit breaker status for all components
status = orchestrator._get_circuit_breaker_status()
# Returns: {"brain_router": "closed", "trading_system": "not_monitored", ...}
```

### 2. Health Monitoring
```python
# Get health status across all components
health = orchestrator._get_health_status()
# Returns: {"healthy": 10, "degraded": 0, "failed": 0, "total": 10}
```

### 3. Timeout/Retry with Exponential Backoff
```python
# Execute with automatic retry and timeout
result = await orchestrator.execute_with_retry(
    func=some_async_function,
    max_retries=3,
    timeout_seconds=30.0,
    backoff_factor=1.5
)
```

### 4. Graceful Degradation
```python
# Execute with automatic fallback on failure
result = await orchestrator.execute_with_fallback(
    primary_func=expensive_ai_call,
    fallback_func=cached_response,
    timeout_seconds=10.0
)
```

### SOTA 2026 Agent Patterns Applied

| Pattern | Implementation | Source |
|---------|----------------|--------|
| **Single Agent, Multitool** | BrainRouter with access to all subsystems | Microsoft Azure |
| **Handoff Orchestration** | UnifiedAIRouter → BrainRouter delegation | Microsoft Azure |
| **Deterministic Routing** | Event aliases for predictable flow | Vellum AI |
| **Agentic RAG** | SystemContextProvider for codebase awareness | IBM/Armand Ruiz |
| **Graph-based Agents** | EventBus provides graph-like message routing | BabyAGI/Yohei |
| **ReAct Pattern** | ThothAIWorker with vision/sensor context | Vellum AI |

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-24 | Initial implementation |
| 1.1 | 2025-12-24 | Added SOTA 2026 reliability patterns (circuit breaker, timeout/retry, graceful degradation) |

---

*Part of Kingdom AI - SOTA 2026 Architecture*
