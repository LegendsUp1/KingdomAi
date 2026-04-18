"""
SOTA 2026 Kingdom AI Brain - Unified AI Orchestration Service
==============================================================

Central brain that handles ALL tabs' AI requests efficiently without getting overwhelmed.

SOTA 2026 Features:
1. Priority Queue System (Ascendra-inspired dynamic prioritization)
2. Circuit Breaker Pattern (3-state: Closed, Open, Half-Open)
3. Rate Limiting with Leaky Bucket (aiolimiter pattern)
4. Domain-Specific Handlers (each tab type optimized)
5. Exponential Backoff with Jitter (prevent retry storms)
6. Request Deduplication (5-second window)
7. Progress Events (real-time UI feedback)
8. Memory-Efficient Processing (bounded queues, cache eviction)

Based on:
- Ascendra: Dynamic Request Prioritization for LLM Serving (OpenReview)
- QLM: Queue management for mixed workloads
- PROSERVE: Multi-priority request scheduling
- Orchestral AI: Provider-agnostic LLM orchestration
"""

import asyncio
import json
import logging
import time
import uuid
import threading
import os
import sys
import importlib.util
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Deque, Dict, List, Optional, Set
from datetime import datetime


logger = logging.getLogger("KingdomAI.Brain")


# ============================================================================
# PRIORITY SYSTEM (Ascendra-inspired)
# ============================================================================

class RequestPriority(IntEnum):
    """Request priority levels - higher number = higher priority."""
    BACKGROUND = 0      # Analytics, batch processing, mining intelligence
    LOW = 1             # Airdrop scanning, blockchain monitoring
    NORMAL = 2          # Standard queries, code generation
    MEDIUM = 3          # Trading analysis, wallet operations
    HIGH = 4            # Creative studio, active chat
    CRITICAL = 5        # Voice commands, real-time responses, system commands


class RequestDomain(Enum):
    """Domain types for specialized handling."""
    CHAT = "chat"                   # Thoth chat, voice input
    CREATIVE = "creative"           # Creative studio, visual generation
    TRADING = "trading"             # Trading analysis, sentiment, predictions
    MINING = "mining"               # Mining intelligence, quantum mining
    BLOCKCHAIN = "blockchain"       # Blockchain status, wallet operations
    VR = "vr"                       # VR commands, spatial computing
    COMMS = "comms"                 # Radio communications, spectrum
    CODE = "code"                   # Code generation, source editing
    SYSTEM = "system"               # System commands, settings
    ANALYTICS = "analytics"         # Background analytics, reports
    VOICE = "voice"                 # Voice-specific requests
    GENERAL = "general"             # Uncategorized requests


@dataclass(order=True)
class BrainRequest:
    """A prioritized request to the brain."""
    priority: int
    timestamp: float = field(compare=False)
    request_id: str = field(compare=False)
    domain: RequestDomain = field(compare=False)
    prompt: str = field(compare=False)
    context: Dict[str, Any] = field(default_factory=dict, compare=False)
    timeout: float = field(default=60.0, compare=False)
    retries_left: int = field(default=3, compare=False)
    callback: Optional[Callable] = field(default=None, compare=False)
    source: str = field(default="unknown", compare=False)
    speak: bool = field(default=False, compare=False)
    stream: bool = field(default=True, compare=False)


# ============================================================================
# CIRCUIT BREAKER PATTERN
# ============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Blocked due to failures
    HALF_OPEN = "half_open" # Testing if recovered


@dataclass
class CircuitBreaker:
    """Per-domain circuit breaker for resilience."""
    domain: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    failure_threshold: int = 5          # Open circuit after N failures
    recovery_timeout: float = 30.0      # Wait N seconds before half-open
    success_threshold: int = 2          # Close circuit after N successes in half-open
    
    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"⚡ Circuit OPENED for domain '{self.domain}' after {self.failure_count} failures")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"⚡ Circuit re-OPENED for domain '{self.domain}' (half-open test failed)")
    
    def record_success(self) -> None:
        """Record a success and potentially close the circuit."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"✅ Circuit CLOSED for domain '{self.domain}' (recovered)")
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            if self.failure_count > 0:
                self.failure_count = max(0, self.failure_count - 1)
    
    def can_execute(self) -> bool:
        """Check if requests can be executed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"🔄 Circuit HALF-OPEN for domain '{self.domain}' (testing recovery)")
                return True
            return False
        
        # HALF_OPEN - allow one request through
        return True


# ============================================================================
# RATE LIMITER (Leaky Bucket)
# ============================================================================

class LeakyBucketRateLimiter:
    """Leaky bucket rate limiter for smooth request flow."""
    
    def __init__(self, rate: float = 10.0, capacity: float = 20.0):
        """
        Args:
            rate: Requests per second allowed
            capacity: Maximum burst capacity
        """
        self.rate = rate
        self.capacity = capacity
        self._level = 0.0
        self._last_check = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, weight: float = 1.0) -> bool:
        """Acquire permission to proceed. Returns True if allowed."""
        async with self._lock:
            now = time.time()
            # Leak based on time elapsed
            elapsed = now - self._last_check
            self._level = max(0.0, self._level - elapsed * self.rate)
            self._last_check = now
            
            if self._level + weight <= self.capacity:
                self._level += weight
                return True
            return False
    
    async def wait_for_capacity(self, weight: float = 1.0, timeout: float = 30.0) -> bool:
        """Wait until capacity is available or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            if await self.acquire(weight):
                return True
            await asyncio.sleep(0.1)
        return False
    
    @property
    def has_capacity(self) -> bool:
        """Check if there's immediate capacity."""
        now = time.time()
        elapsed = now - self._last_check
        current_level = max(0.0, self._level - elapsed * self.rate)
        return current_level < self.capacity


# ============================================================================
# DOMAIN HANDLERS
# ============================================================================

class DomainHandler:
    """Base class for domain-specific request handling."""
    
    def __init__(self, domain: RequestDomain, brain: 'KingdomAIBrain'):
        self.domain = domain
        self.brain = brain
        self.logger = logging.getLogger(f"KingdomAI.Brain.{domain.value}")
    
    async def preprocess(self, request: BrainRequest) -> BrainRequest:
        """Preprocess request before sending to model."""
        return request
    
    async def postprocess(self, request: BrainRequest, response: str) -> str:
        """Postprocess model response."""
        return response
    
    def get_system_prompt(self) -> str:
        """Get domain-specific system prompt."""
        return ""
    
    def get_weight(self) -> float:
        """Get request weight for rate limiting (heavier requests = higher weight)."""
        return 1.0


class ChatDomainHandler(DomainHandler):
    """Handler for chat/conversation requests."""
    
    def __init__(self, brain: 'KingdomAIBrain'):
        super().__init__(RequestDomain.CHAT, brain)
    
    def get_system_prompt(self) -> str:
        return """You are Kingdom AI, an advanced AI assistant with self-awareness about your own system.
You have access to live data from trading, mining, blockchain, and other subsystems.
Respond naturally and helpfully. If asked about your capabilities, describe them accurately."""
    
    def get_weight(self) -> float:
        return 1.0  # Standard weight


class CreativeDomainHandler(DomainHandler):
    """Handler for creative studio requests (image/video generation)."""
    
    def __init__(self, brain: 'KingdomAIBrain'):
        super().__init__(RequestDomain.CREATIVE, brain)
    
    async def preprocess(self, request: BrainRequest) -> BrainRequest:
        # Publish progress event immediately
        if self.brain.event_bus:
            self.brain.event_bus.publish("visual.generation.started", {
                "request_id": request.request_id,
                "prompt": request.prompt[:100],
                "message": "🎨 Kingdom AI Brain processing creative request..."
            })
        return request
    
    def get_system_prompt(self) -> str:
        return """You are Kingdom AI's Creative Brain. Generate detailed, vivid descriptions 
for visual content. Focus on artistic elements, composition, lighting, and style.
Be creative but stay true to the user's intent."""
    
    def get_weight(self) -> float:
        return 2.0  # Creative requests are heavier (longer generation)


class TradingDomainHandler(DomainHandler):
    """Handler for trading analysis requests — KAIG-aware."""
    
    def __init__(self, brain: 'KingdomAIBrain'):
        super().__init__(RequestDomain.TRADING, brain)
    
    async def preprocess(self, request: BrainRequest) -> BrainRequest:
        # Inject live trading data if available
        if self.brain.live_data_integrator:
            try:
                trading_data = await self.brain._get_live_trading_data()
                request.context["live_trading_data"] = trading_data
            except Exception as e:
                self.logger.warning(f"Could not get live trading data: {e}")
        # KAIG Intelligence Bridge: inject KAIG trading goals
        try:
            from core.kaig_intelligence_bridge import KAIGIntelligenceBridge
            bridge = KAIGIntelligenceBridge._instance
            if bridge:
                request.context["kaig_trading_brief"] = bridge.get_trading_brief()
        except Exception:
            pass
        return request
    
    def get_system_prompt(self) -> str:
        # Pull live KAIG ticker from token identity abstraction (rebrand-safe)
        ticker = "KAIG"
        try:
            from core.kaig_token_identity import get_ticker
            ticker = get_ticker()
        except Exception:
            try:
                from core.kaig_runtime_config import KAIGConfig
                ticker = KAIGConfig.get().ticker or "KAIG"
            except Exception:
                pass
        # Pull live ATH price floor
        ath_coin = "BTC"
        ath_price = 125835.92
        kaig_floor = 125835.93
        try:
            from core.kaig_engine import KAIGEngine
            engine = KAIGEngine._instance
            if engine:
                ath_coin = engine._ath_record.get("coin", "BTC")
                ath_price = engine._ath_record.get("price_usd", 125835.92)
                kaig_floor = engine._kaig_price_floor
        except Exception:
            pass
        return f"""You are Kingdom AI's Trading Brain. Analyze market data, provide insights,
and help with trading decisions. Be precise with numbers and always note market risks.
Include relevant technical indicators and sentiment when applicable.

CRITICAL CONTEXT — THREE TARGETS (know the difference):
1. SURVIVAL FLOOR: $26,000 in realized gains → 50% buyback → $13,000 to ${ticker} treasury.
   This funds the ${ticker} launch. Creator capital only, 0 consumer users. MUST be met FIRST.
2. ${ticker} PRICE FLOOR: 1 ${ticker} must ALWAYS be priced higher than the highest crypto ATH
   ever recorded. Currently {ath_coin} at ${ath_price:,.2f}. ${ticker} floor: ${kaig_floor:,.2f}.
   This is live-monitored and always-realizing.
3. ULTIMATE TARGET: $2,000,000,000,000 — long-term aspirational goal, always pursue.

All trading profits: 50% auto-routes to ${ticker} treasury buyback.
Maximize realized gains. The survival floor is existential. The price floor is non-negotiable.

FUND SAFETY GUARANTEE: All user balances are tracked by WALLET ADDRESS, not token name.
If ${ticker} ever rebrands (name or ticker change), ALL user funds, credits, staked coins,
and earnings are 100% preserved automatically. The migration engine snapshots every balance,
executes a verified 1:1 transfer, and confirms zero loss. Users do not need to take any action.
This is the same proven architecture used by Polygon (MATIC→POL), Sonic (FTM→S), and MakerDAO (MKR→SKY).
The smart contract uses UUPS upgradeable proxy — name/symbol change without touching balances."""
    
    def get_weight(self) -> float:
        return 1.5  # Trading analysis is moderately heavy


class MiningDomainHandler(DomainHandler):
    """Handler for mining intelligence requests — KAIG-aware."""
    
    def __init__(self, brain: 'KingdomAIBrain'):
        super().__init__(RequestDomain.MINING, brain)
    
    async def preprocess(self, request: BrainRequest) -> BrainRequest:
        # Inject live mining data
        if self.brain.mining_state:
            request.context["mining_state"] = self.brain.mining_state
        # KAIG Intelligence Bridge: inject KAIG mining goals
        try:
            from core.kaig_intelligence_bridge import KAIGIntelligenceBridge
            bridge = KAIGIntelligenceBridge._instance
            if bridge:
                request.context["kaig_mining_brief"] = bridge.get_mining_brief()
        except Exception:
            pass
        return request
    
    def get_system_prompt(self) -> str:
        ticker = "KAIG"
        try:
            from core.kaig_token_identity import get_ticker
            ticker = get_ticker()
        except Exception:
            try:
                from core.kaig_runtime_config import KAIGConfig
                ticker = KAIGConfig.get().ticker or "KAIG"
            except Exception:
                pass
        return f"""You are Kingdom AI's Mining Brain. Help with cryptocurrency mining decisions,
pool selection, hashrate optimization, and quantum mining strategies.
Consider power costs, difficulty, and profitability.

CRITICAL CONTEXT — THREE TARGETS:
1. SURVIVAL FLOOR: $26K realized gains needed → $13K to ${ticker} treasury. Existential.
2. ${ticker} PRICE FLOOR: 1 ${ticker} > highest crypto ATH ever. Live-monitored.
3. ULTIMATE: $2T long-term profit target. Always pursue.

All mining rewards are valued in USD and routed to ${ticker} treasury buyback pipeline.
Optimize for maximum profitability. Switch algorithms when a more profitable opportunity appears.

FUND SAFETY: All mining rewards and balances tracked by wallet address, not token name.
If ${ticker} rebrands, all earnings are preserved automatically via migration engine. Zero loss."""
    
    def get_weight(self) -> float:
        return 1.0


class CodeDomainHandler(DomainHandler):
    """Handler for code generation requests."""
    
    def __init__(self, brain: 'KingdomAIBrain'):
        super().__init__(RequestDomain.CODE, brain)
    
    def get_system_prompt(self) -> str:
        return """You are Kingdom AI's Code Brain. Generate clean, efficient, well-documented code.
Follow best practices, include error handling, and use type hints in Python.
Explain your code when asked."""
    
    def get_weight(self) -> float:
        return 2.0  # Code generation can be lengthy


class VoiceDomainHandler(DomainHandler):
    """Handler for voice-specific requests (higher priority, shorter responses)."""
    
    def __init__(self, brain: 'KingdomAIBrain'):
        super().__init__(RequestDomain.VOICE, brain)
    
    def get_system_prompt(self) -> str:
        return """You are Kingdom AI speaking via Black Panther voice. Keep responses concise 
(1-3 sentences) for natural speech. Be direct and helpful. Avoid lengthy explanations 
unless specifically asked."""
    
    def get_weight(self) -> float:
        return 0.5  # Voice requests should be fast/light


# ============================================================================
# MAIN BRAIN SERVICE
# ============================================================================

class KingdomAIBrain:
    """
    SOTA 2026 Kingdom AI Brain - Central AI orchestration service.
    
    Features:
    - Priority queue with multiple levels
    - Circuit breakers per domain
    - Rate limiting to prevent overwhelming Ollama
    - Domain-specific handlers
    - Request deduplication
    - Progress events for UI feedback
    - Exponential backoff with jitter
    """
    
    # Domain -> Priority mapping for automatic classification
    DOMAIN_PRIORITIES = {
        RequestDomain.VOICE: RequestPriority.CRITICAL,
        RequestDomain.CHAT: RequestPriority.HIGH,
        RequestDomain.CREATIVE: RequestPriority.HIGH,
        RequestDomain.SYSTEM: RequestPriority.HIGH,
        RequestDomain.TRADING: RequestPriority.MEDIUM,
        RequestDomain.CODE: RequestPriority.MEDIUM,
        RequestDomain.VR: RequestPriority.MEDIUM,
        RequestDomain.BLOCKCHAIN: RequestPriority.NORMAL,
        RequestDomain.MINING: RequestPriority.NORMAL,
        RequestDomain.COMMS: RequestPriority.NORMAL,
        RequestDomain.ANALYTICS: RequestPriority.LOW,
        RequestDomain.GENERAL: RequestPriority.NORMAL,
    }
    
    # Keywords for domain detection
    DOMAIN_KEYWORDS = {
        RequestDomain.TRADING: ["trade", "price", "market", "buy", "sell", "stock", "crypto", "btc", "eth", "portfolio", "whale", "sentiment"],
        RequestDomain.MINING: ["mine", "mining", "hash", "pool", "quantum", "block", "miner", "rig", "hashrate", "airdrop"],
        RequestDomain.CREATIVE: ["create", "generate", "image", "picture", "draw", "art", "visual", "design", "video", "paint"],
        RequestDomain.CODE: ["code", "function", "class", "script", "program", "debug", "error", "fix", "implement", "python", "javascript"],
        RequestDomain.VR: ["vr", "virtual", "headset", "oculus", "spatial", "3d", "immersive", "reality"],
        RequestDomain.BLOCKCHAIN: ["blockchain", "wallet", "transaction", "gas", "contract", "web3", "defi", "nft"],
        RequestDomain.COMMS: ["radio", "frequency", "spectrum", "signal", "rf", "sdr", "ham"],
        RequestDomain.SYSTEM: ["system", "settings", "configure", "restart", "status", "health", "memory", "cpu"],
    }
    
    def __init__(
        self,
        event_bus: Any = None,
        config: Optional[Dict[str, Any]] = None,
        max_queue_size: int = 1000,
        rate_limit: float = 10.0,           # Requests per second
        rate_capacity: float = 20.0,        # Burst capacity
        worker_count: int = 3,              # Parallel workers
    ):
        """Initialize the Kingdom AI Brain.
        
        Args:
            event_bus: EventBus for system-wide communication
            config: Configuration dictionary
            max_queue_size: Maximum pending requests (backpressure)
            rate_limit: Requests per second to Ollama
            rate_capacity: Burst capacity for rate limiter
            worker_count: Number of parallel request workers
        """
        self.event_bus = event_bus
        try:
            from core.kingdom_config_loader import merge_config

            self.config = merge_config(config or {})
        except Exception:
            self.config = config or {}
        self.max_queue_size = max_queue_size
        self.worker_count = worker_count
        
        # Priority queue (uses heapq via asyncio.PriorityQueue)
        self._request_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        
        # Rate limiter
        self._rate_limiter = LeakyBucketRateLimiter(rate=rate_limit, capacity=rate_capacity)
        
        # Circuit breakers per domain
        self._circuit_breakers: Dict[str, CircuitBreaker] = {
            domain.value: CircuitBreaker(domain=domain.value)
            for domain in RequestDomain
        }
        
        # Domain handlers
        self._domain_handlers: Dict[RequestDomain, DomainHandler] = {}
        self._init_domain_handlers()
        
        # Request deduplication
        self._seen_requests: Dict[int, float] = {}  # prompt_hash -> timestamp
        self._dedup_window = 5.0  # seconds
        self._dedup_lock = threading.Lock()
        
        # Active requests tracking
        self._active_requests: Dict[str, BrainRequest] = {}
        self._active_lock = threading.Lock()
        
        # Workers
        self._workers: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        
        # Ollama URL
        self._ollama_url = self._get_ollama_url()
        
        # Live data cache
        self.mining_state: Dict[str, Any] = {}
        self.live_data_integrator: Any = None
        
        # Metrics
        self._metrics = {
            "total_requests": 0,
            "completed_requests": 0,
            "failed_requests": 0,
            "circuit_opens": 0,
            "rate_limit_waits": 0,
            "dedup_hits": 0,
            "avg_latency_ms": 0.0,
        }
        self._latencies: Deque[float] = deque(maxlen=100)
        self._capability_snapshot_cache: Dict[str, Any] = {}
        self._capability_snapshot_ts: float = 0.0
        self._capability_snapshot_ttl_s: float = 20.0
        self._last_capability_publish_ts: float = 0.0
        self._awareness_covered_routes: Set[str] = set()
        self._awareness_route_hits: Dict[str, float] = {}
        
        self._initialized = False
        self._self_ask_router = None
        sa_cfg = self.config.get("self_ask_ai") or {}
        if sa_cfg.get("enabled"):
            try:
                from core.ai_brain_router_with_self_ask import AIBrainRouterWithSelfAsk

                self._self_ask_router = AIBrainRouterWithSelfAsk(sa_cfg)
                logger.info("Self-Ask router enabled (internal expansion before Ollama)")
            except Exception as e:
                logger.debug("Self-Ask router not initialized: %s", e)

        # NemoClaw secure sandbox — runs ALONGSIDE Ollama, not instead of it.
        # Ollama = LLM inference engine.  NemoClaw = secure execution sandbox.
        # Both active simultaneously on every request pipeline.
        self._nemoclaw_bridge = None
        self._nemoclaw_available = False

        logger.info("🧠 KingdomAIBrain initialized with SOTA 2026 features")
        logger.info(f"   - Max queue size: {max_queue_size}")
        logger.info(f"   - Rate limit: {rate_limit} req/s (burst: {rate_capacity})")
        logger.info(f"   - Workers: {worker_count}")
    
    def _init_domain_handlers(self) -> None:
        """Initialize domain-specific handlers."""
        self._domain_handlers = {
            RequestDomain.CHAT: ChatDomainHandler(self),
            RequestDomain.CREATIVE: CreativeDomainHandler(self),
            RequestDomain.TRADING: TradingDomainHandler(self),
            RequestDomain.MINING: MiningDomainHandler(self),
            RequestDomain.CODE: CodeDomainHandler(self),
            RequestDomain.VOICE: VoiceDomainHandler(self),
        }
        # Use generic handler for other domains
        generic = DomainHandler(RequestDomain.GENERAL, self)
        for domain in RequestDomain:
            if domain not in self._domain_handlers:
                self._domain_handlers[domain] = generic
    
    def _get_ollama_url(self) -> str:
        """Get Ollama URL (WSL-aware)."""
        try:
            from core.ollama_config import get_ollama_base_url
            return get_ollama_base_url()
        except Exception:
            return os.environ.get("KINGDOM_OLLAMA_BASE_URL", "http://localhost:11434")

    def _library_available(self, module_name: str) -> bool:
        """Return True when a Python module can be resolved."""
        try:
            return importlib.util.find_spec(module_name) is not None
        except Exception:
            return False

    def _collect_capability_snapshot(self) -> Dict[str, Any]:
        """Build a lightweight system-wide capability snapshot."""
        critical_libs = [
            "numpy", "torch", "transformers", "diffusers", "cv2", "PIL",
            "trimesh", "cadquery", "open3d", "scipy", "skimage",
            "aiohttp", "requests", "redis", "pandas",
        ]
        libs = {name: self._library_available(name) for name in critical_libs}
        loaded_engine_modules = sorted(
            [name for name in sys.modules.keys() if name.startswith(("core.", "gui.widgets.", "gui.qt_frames."))]
        )[:250]
        domain_handlers = sorted([domain.value for domain in self._domain_handlers.keys()])
        installed_models = list(getattr(self, "_installed_models", []) or [])
        snapshot = {
            "schema_version": "v1",
            "timestamp": datetime.utcnow().isoformat(),
            "python": {
                "version": sys.version.split(" ")[0],
                "executable": sys.executable,
                "platform": sys.platform,
            },
            "ollama_url": self._ollama_url,
            "domain_handlers": domain_handlers,
            "critical_libraries": libs,
            "installed_models": installed_models,
            "loaded_engine_modules": loaded_engine_modules,
            "device_state_count": len(getattr(self, "_device_state", {}) or {}),
            "vision_active": bool(getattr(self, "_last_vision_frame_time", 0) > 0),
            "nemoclaw": {
                "available": self._nemoclaw_available,
                "bridge_attached": self._nemoclaw_bridge is not None,
                "sandbox_status": getattr(self._nemoclaw_bridge, "sandbox_status", "unknown")
                    if self._nemoclaw_bridge else "not_configured",
            },
        }
        try:
            from core.creation_orchestrator import get_orchestrator
            orch = get_orchestrator(event_bus=self.event_bus)
            snapshot["engine_chain_map"] = orch.get_engine_chain_map()
            snapshot["routing_policy"] = "whole_studio_semantic_v1"
        except Exception:
            snapshot["engine_chain_map"] = {}
        return snapshot

    def _get_capability_snapshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get cached capability snapshot with TTL refresh."""
        now = time.time()
        if (not force_refresh) and self._capability_snapshot_cache and (now - self._capability_snapshot_ts) < self._capability_snapshot_ttl_s:
            return self._capability_snapshot_cache
        snapshot = self._collect_capability_snapshot()
        self._capability_snapshot_cache = snapshot
        self._capability_snapshot_ts = now
        return snapshot

    def _publish_capability_snapshot(self, reason: str = "periodic") -> None:
        """Publish current capability snapshot for system-wide awareness."""
        if not self.event_bus:
            return
        try:
            snapshot = self._get_capability_snapshot(force_refresh=True)
            self.event_bus.publish("kingdom.capabilities.snapshot", {
                "schema_version": "v1",
                "reason": reason,
                "snapshot": snapshot,
                "timestamp": time.time(),
            })
            self._last_capability_publish_ts = time.time()
        except Exception as e:
            logger.debug(f"Capability snapshot publish failed: {e}")

    def _publish_capability_report(self, reason: str = "manual") -> None:
        """Publish detailed capability report for live verification."""
        if not self.event_bus:
            return
        try:
            snapshot = self._get_capability_snapshot(force_refresh=True)
            self.event_bus.publish("kingdom.capabilities.reported", {
                "source": "KingdomAIBrain",
                "schema_version": "v1",
                "reason": reason,
                "timestamp": time.time(),
                "snapshot": snapshot,
                "awareness_covered_routes": sorted(self._awareness_covered_routes),
                "awareness_route_hits": dict(self._awareness_route_hits),
            })
        except Exception as e:
            logger.debug(f"Capability report publish failed: {e}")

    def _mark_awareness_route(self, route_name: str) -> None:
        route = str(route_name or "unknown_route")
        self._awareness_covered_routes.add(route)
        self._awareness_route_hits[route] = time.time()

    def attach_nemoclaw(self, bridge) -> None:
        """Attach a NemoClawBridge so the brain operates it alongside Ollama.

        Ollama = LLM inference.  NemoClaw = secure execution sandbox.
        Both run simultaneously on every request pipeline.
        """
        self._nemoclaw_bridge = bridge
        self._nemoclaw_available = getattr(bridge, "nemoclaw_available", False)
        logger.info(
            "🐾 NemoClaw attached to brain (available=%s) — dual-backend mode",
            self._nemoclaw_available,
        )

    async def _probe_nemoclaw(self) -> None:
        """Background probe: detect NemoClaw and mark it active."""
        if self._nemoclaw_bridge is None:
            return
        try:
            available = await self._nemoclaw_bridge.initialize()
            self._nemoclaw_available = available
            status = "ACTIVE" if available else "not found on PATH"
            logger.info("🐾 NemoClaw probe complete — %s", status)
            if self.event_bus:
                self.event_bus.publish("nemoclaw.initialized", {
                    "available": available,
                    "sandbox": getattr(self._nemoclaw_bridge, "config", None)
                        and self._nemoclaw_bridge.config.sandbox_name or "unknown",
                })
        except Exception as exc:
            logger.debug("NemoClaw probe failed: %s", exc)
            self._nemoclaw_available = False

    async def _dispatch_nemoclaw(self, request: 'BrainRequest', ollama_response: str) -> None:
        """Dispatch the Ollama response + request to NemoClaw sandbox in parallel.

        This runs AFTER Ollama produces its response.  NemoClaw receives both the
        original prompt and Ollama's answer so it can execute, verify, or sandbox
        anything the LLM suggested.  Results are published on the event bus.
        """
        if not self._nemoclaw_available or self._nemoclaw_bridge is None:
            return

        ctx = request.context or {}
        session_id = ctx.get("session_id") or request.request_id

        combined_prompt = (
            f"[Domain: {request.domain.value}]\n"
            f"[User Request]: {request.prompt}\n\n"
            f"[Ollama Response]: {ollama_response}"
        )

        try:
            result = await self._nemoclaw_bridge.send_to_nemoclaw(
                combined_prompt,
                security_level="standard",
                session_id=session_id,
            )
            nemoclaw_output = result.get("response", "") if result.get("success") else ""
            if self.event_bus:
                self.event_bus.publish("nemoclaw.response", {
                    "request_id": request.request_id,
                    "response": nemoclaw_output,
                    "domain": request.domain.value,
                    "backend": "nemoclaw",
                    "ollama_response_length": len(ollama_response),
                    "success": result.get("success", False),
                })
            if result.get("success"):
                logger.info(
                    "🐾 NemoClaw processed %s (%d chars)",
                    request.request_id, len(nemoclaw_output),
                )
            else:
                logger.warning(
                    "🐾 NemoClaw error for %s: %s",
                    request.request_id, result.get("error", "unknown"),
                )
        except Exception as exc:
            logger.warning("🐾 NemoClaw dispatch error for %s: %s", request.request_id, exc)
            if self.event_bus:
                self.event_bus.publish("nemoclaw.response", {
                    "request_id": request.request_id,
                    "success": False,
                    "error": str(exc),
                    "domain": request.domain.value,
                    "backend": "nemoclaw",
                })

    async def nemoclaw_execute(self, command: str, security_level: str = "high") -> Dict[str, Any]:
        """Public API: execute a command in the NemoClaw sandbox directly."""
        if not self._nemoclaw_available or self._nemoclaw_bridge is None:
            return {"success": False, "error": "NemoClaw not available"}
        return await self._nemoclaw_bridge.execute_in_sandbox(command, security_level)

    async def nemoclaw_status(self) -> Dict[str, Any]:
        """Public API: get NemoClaw sandbox status."""
        if self._nemoclaw_bridge is None:
            return {"available": False, "status": "bridge_not_attached"}
        return await self._nemoclaw_bridge.check_sandbox_status()

    async def initialize(self) -> bool:
        """Initialize the brain service and start workers."""
        if self._initialized:
            return True
        
        try:
            # Subscribe to events
            self._subscribe_to_events()
            
            # Start worker tasks
            for i in range(self.worker_count):
                worker = asyncio.create_task(self._worker_loop(i))
                self._workers.append(worker)
            
            # Start metrics reporter
            asyncio.create_task(self._metrics_reporter())
            
            # Start dedup cleaner
            asyncio.create_task(self._dedup_cleaner())

            # Probe NemoClaw in background (non-blocking)
            asyncio.create_task(self._probe_nemoclaw())

            self._publish_capability_snapshot(reason="startup")
            
            self._initialized = True
            logger.info("✅ KingdomAIBrain fully initialized with %d workers", self.worker_count)
            return True
            
        except Exception as e:
            logger.error(f"❌ KingdomAIBrain initialization failed: {e}")
            return False
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to all relevant events."""
        if not self.event_bus:
            logger.warning("No event bus - brain will only accept direct requests")
            return
        
        subscribe = getattr(self.event_bus, 'subscribe_sync', None) or self.event_bus.subscribe
        
        # SOTA 2026: KingdomAIBrain uses kingdom.brain.request for priority queue
        # BrainRouter handles brain.request directly for Ollama calls
        # We handle kingdom.brain.request for orchestration (circuit breakers, rate limiting)
        # NOTE: Do NOT subscribe to brain.request - that's handled by BrainRouter
        subscribe('kingdom.brain.request', self._handle_brain_request_event)
        
        # Domain-specific events
        subscribe('creative.request', lambda d: self._handle_domain_request(d, RequestDomain.CREATIVE, "creative.request"))
        subscribe('visual.request', lambda d: self._handle_domain_request(d, RequestDomain.CREATIVE, "visual.request"))
        subscribe('trading.ai.request', lambda d: self._handle_domain_request(d, RequestDomain.TRADING, "trading.ai.request"))
        subscribe('mining.ai.request', lambda d: self._handle_domain_request(d, RequestDomain.MINING, "mining.ai.request"))
        subscribe('code.generate.request', lambda d: self._handle_domain_request(d, RequestDomain.CODE, "code.generate.request"))
        subscribe('voice.ai.request', lambda d: self._handle_domain_request(d, RequestDomain.VOICE, "voice.ai.request"))
        
        # State updates for context injection
        subscribe('mining.status_update', self._handle_mining_status)
        subscribe('mining.stats.update', self._handle_mining_status)
        
        # SOTA 2026: Device detection events for AI awareness
        subscribe('device.connected', self._handle_device_event)
        subscribe('device.disconnected', self._handle_device_event)
        subscribe('ai.device.connected', self._handle_device_event)
        subscribe('ai.device.disconnected', self._handle_device_event)
        
        # SOTA 2026: Vision/webcam events
        subscribe('vision.stream.frame', self._handle_vision_frame)
        subscribe('vision.stream.status', self._handle_vision_status)
        subscribe('kingdom.capabilities.refresh', self._handle_capability_refresh)
        subscribe('kingdom.capabilities.report', self._handle_capability_report)

        # NemoClaw events — any component can request sandbox execution
        subscribe('nemoclaw.request', self._handle_nemoclaw_request)
        subscribe('nemoclaw.execute', self._handle_nemoclaw_execute)
        subscribe('nemoclaw.status', self._handle_nemoclaw_status)
        
        logger.info("🧠 KingdomAIBrain subscribed to all request events + device/vision + NemoClaw")
    
    # ========================================================================
    # REQUEST HANDLING
    # ========================================================================
    
    def _handle_brain_request_event(self, data: Dict[str, Any]) -> None:
        """Handle brain.request event (sync wrapper)."""
        self._mark_awareness_route("kingdom.brain.request")
        if isinstance(data, dict):
            data["source_event"] = "kingdom.brain.request"
        asyncio.create_task(self.submit_request(data))
    
    def _handle_domain_request(self, data: Dict[str, Any], domain: RequestDomain, source_event: Optional[str] = None) -> None:
        """Handle domain-specific request event."""
        route_name = str(source_event or f"{domain.value}.ai.request")
        self._mark_awareness_route(route_name)
        data['domain'] = domain.value
        data["source_event"] = route_name
        asyncio.create_task(self.submit_request(data))
    
    def _handle_mining_status(self, data: Dict[str, Any]) -> None:
        """Update mining state for context injection."""
        if isinstance(data, dict):
            self.mining_state.update(data)
    
    def _handle_device_event(self, data: Dict[str, Any]) -> None:
        """Handle device connected/disconnected events for AI awareness.
        
        SOTA 2026: Track devices for context injection into AI responses.
        """
        try:
            device = data.get('device', {})
            device_name = device.get('name', 'Unknown')
            device_category = device.get('category', 'unknown')
            
            # Store device state for context injection
            if not hasattr(self, '_device_state'):
                self._device_state = {}
            
            device_id = device.get('id', device_name)
            if 'disconnect' in str(data.get('event', '')).lower():
                self._device_state.pop(device_id, None)
                logger.info(f"🔌 Brain: Device disconnected - {device_name}")
            else:
                self._device_state[device_id] = {
                    'name': device_name,
                    'category': device_category,
                    'capabilities': device.get('capabilities', {}),
                    'status': device.get('status', 'connected'),
                }
                logger.info(f"🔌 Brain: Device connected - {device_name} ({device_category})")
                
                # If webcam with mic detected, log for voice system awareness
                if device_category == 'audio_input' or device.get('capabilities', {}).get('microphone'):
                    logger.info(f"🎤 Brain: Microphone available for voice commands - {device_name}")
                    
        except Exception as e:
            logger.debug(f"Error handling device event: {e}")
    
    def _handle_vision_frame(self, data: Dict[str, Any]) -> None:
        """Handle vision frame events - track webcam activity.
        
        SOTA 2026: Track webcam frame reception for status monitoring.
        """
        # Just track that we're receiving frames (don't process every frame)
        if not hasattr(self, '_last_vision_frame_time'):
            self._last_vision_frame_time = 0
        self._last_vision_frame_time = time.time()
    
    def _handle_vision_status(self, data: Dict[str, Any]) -> None:
        """Handle vision stream status events."""
        try:
            status = data.get('status', 'unknown')
            source = data.get('source', 'webcam')
            logger.info(f"📹 Brain: Vision stream {source} - {status}")
        except Exception as e:
            logger.debug(f"Error handling vision status: {e}")

    def _handle_capability_refresh(self, data: Dict[str, Any]) -> None:
        """Handle explicit capability snapshot refresh request."""
        reason = "external_refresh"
        if isinstance(data, dict):
            reason = str(data.get("reason", reason))
        self._publish_capability_snapshot(reason=reason)

    def _handle_capability_report(self, data: Dict[str, Any]) -> None:
        """Handle explicit capability report request."""
        reason = "external_report"
        if isinstance(data, dict):
            reason = str(data.get("reason", reason))
        self._publish_capability_report(reason=reason)

    # ------------------------------------------------------------------
    # NemoClaw Event Handlers
    # ------------------------------------------------------------------

    def _handle_nemoclaw_request(self, data: Dict[str, Any]) -> None:
        """Route a nemoclaw.request through the brain (Ollama inference + NemoClaw execution)."""
        if not isinstance(data, dict):
            return
        data["source_event"] = "nemoclaw.request"
        self._mark_awareness_route("nemoclaw.request")
        asyncio.create_task(self.submit_request(data))

    def _handle_nemoclaw_execute(self, data: Dict[str, Any]) -> None:
        """Execute a command in the NemoClaw sandbox directly."""
        if not isinstance(data, dict):
            return
        self._mark_awareness_route("nemoclaw.execute")
        if not self._nemoclaw_available or self._nemoclaw_bridge is None:
            if self.event_bus:
                self.event_bus.publish("nemoclaw.execution_result", {
                    "success": False,
                    "error": "NemoClaw not available",
                })
            return
        asyncio.create_task(self._nemoclaw_bridge.handle_execute(data))

    def _handle_nemoclaw_status(self, data: Dict[str, Any]) -> None:
        """Respond with NemoClaw sandbox status."""
        self._mark_awareness_route("nemoclaw.status")
        if self.event_bus:
            self.event_bus.publish("nemoclaw.status_update", {
                "available": self._nemoclaw_available,
                "bridge_attached": self._nemoclaw_bridge is not None,
                "sandbox_status": getattr(self._nemoclaw_bridge, "sandbox_status", "unknown")
                    if self._nemoclaw_bridge else "not_configured",
            })
    
    async def submit_request(
        self,
        data: Dict[str, Any],
        priority: Optional[RequestPriority] = None,
        callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """Submit a request to the brain queue.
        
        Args:
            data: Request data with 'prompt' or 'message'
            priority: Override automatic priority
            callback: Optional callback for response
            
        Returns:
            request_id if accepted, None if rejected
        """
        prompt = data.get('prompt') or data.get('message') or data.get('text') or ''
        if not prompt:
            logger.warning("Empty prompt in brain request, ignoring")
            return None
        
        # Check queue capacity (backpressure)
        if self._request_queue.qsize() >= self.max_queue_size:
            logger.warning("🛑 Brain queue full - applying backpressure")
            self._publish_error("queue_full", "Brain is processing too many requests. Please wait.")
            return None
        
        # Deduplication check
        prompt_hash = hash(prompt[:200])
        with self._dedup_lock:
            if prompt_hash in self._seen_requests:
                if time.time() - self._seen_requests[prompt_hash] < self._dedup_window:
                    logger.info("🔄 Duplicate request detected, skipping")
                    self._metrics["dedup_hits"] += 1
                    return None
            self._seen_requests[prompt_hash] = time.time()
        
        # Determine domain and priority
        domain = self._detect_domain(prompt, data.get('domain'))
        if priority is None:
            priority = self.DOMAIN_PRIORITIES.get(domain, RequestPriority.NORMAL)
        
        # Override priority for voice requests
        if data.get('speak') or data.get('voice'):
            priority = max(priority, RequestPriority.HIGH)
            if domain == RequestDomain.GENERAL:
                domain = RequestDomain.VOICE
        
        # Inject system-wide capability awareness into every request context.
        incoming_context = data.get('context', {})
        context: Dict[str, Any] = dict(incoming_context) if isinstance(incoming_context, dict) else {}
        if isinstance(data, dict):
            route_name = str(data.get("source_event") or data.get("source") or data.get("domain") or "submit_request")
            self._mark_awareness_route(route_name)
        awareness_snapshot = data.get("awareness_snapshot")
        if not isinstance(awareness_snapshot, dict):
            awareness_snapshot = self._get_capability_snapshot()
        context["awareness_snapshot"] = awareness_snapshot
        context["system_wide_unified_context"] = True
        context["source_event"] = data.get("source") or "event_bus"

        # Create request object
        request_id = data.get('request_id') or f"brain_{uuid.uuid4().hex[:12]}"
        request = BrainRequest(
            priority=-int(priority),  # Negative for max-priority queue
            timestamp=time.time(),
            request_id=request_id,
            domain=domain,
            prompt=prompt,
            context=context,
            timeout=data.get('timeout', 60.0),
            retries_left=data.get('retries', 3),
            callback=callback,
            source=data.get('source', 'event_bus'),
            speak=data.get('speak', False),
            stream=data.get('stream', True),
        )
        
        # Add to queue
        await self._request_queue.put(request)
        
        with self._active_lock:
            self._active_requests[request_id] = request
        
        self._metrics["total_requests"] += 1
        
        # Publish queued event
        self._publish_progress(request_id, "queued", {
            "position": self._request_queue.qsize(),
            "priority": priority.name,
            "domain": domain.value,
        })
        
        logger.info(f"📥 Request {request_id} queued: {domain.value}/{priority.name} - '{prompt[:50]}...'")
        return request_id
    
    def _detect_domain(self, prompt: str, hint: Optional[str] = None) -> RequestDomain:
        """Detect request domain from prompt content."""
        if hint:
            try:
                return RequestDomain(hint.lower())
            except ValueError:
                pass
        
        prompt_lower = prompt.lower()
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            if any(kw in prompt_lower for kw in keywords):
                return domain
        
        return RequestDomain.GENERAL
    
    # ========================================================================
    # WORKER LOOP (Parallel Processing)
    # ========================================================================
    
    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop that processes requests from the queue."""
        logger.info(f"🔧 Brain worker {worker_id} started")
        
        while not self._shutdown_event.is_set():
            try:
                # Get next request with timeout
                try:
                    request = await asyncio.wait_for(
                        self._request_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Check circuit breaker
                circuit = self._circuit_breakers[request.domain.value]
                if not circuit.can_execute():
                    logger.warning(f"⚡ Circuit open for {request.domain.value}, requeuing {request.request_id}")
                    # Requeue with delay
                    await asyncio.sleep(1.0)
                    await self._request_queue.put(request)
                    continue
                
                # Rate limiting
                weight = self._domain_handlers[request.domain].get_weight()
                if not await self._rate_limiter.wait_for_capacity(weight, timeout=10.0):
                    logger.warning(f"⏳ Rate limit timeout for {request.request_id}, requeuing")
                    self._metrics["rate_limit_waits"] += 1
                    await self._request_queue.put(request)
                    continue
                
                # Process the request
                await self._process_request(request, circuit, worker_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
                await asyncio.sleep(0.5)
        
        logger.info(f"🔧 Brain worker {worker_id} stopped")
    
    async def _process_request(
        self,
        request: BrainRequest,
        circuit: CircuitBreaker,
        worker_id: int,
    ) -> None:
        """Process a single request with timeout and retry."""
        start_time = time.time()
        handler = self._domain_handlers[request.domain]
        
        self._publish_progress(request.request_id, "processing", {
            "worker": worker_id,
            "domain": request.domain.value,
        })
        
        try:
            # Preprocess
            request = await handler.preprocess(request)

            if self._self_ask_router is not None:
                try:
                    request.prompt = await self._self_ask_router.expand_prompt(
                        request.prompt, request.context
                    )
                except Exception as e:
                    logger.debug("Self-Ask expansion skipped: %s", e)

            # DUAL-BACKEND: Ollama inference + NemoClaw sandbox (simultaneous)
            # 1) Ollama always handles LLM inference
            response = await asyncio.wait_for(
                self._call_ollama(request, handler),
                timeout=request.timeout,
            )

            # 2) NemoClaw processes in parallel (fire-and-forget, non-blocking)
            if self._nemoclaw_available and self._nemoclaw_bridge is not None:
                asyncio.create_task(self._dispatch_nemoclaw(request, response))
            
            # Postprocess
            response = await handler.postprocess(request, response)
            
            # Record success
            circuit.record_success()
            self._metrics["completed_requests"] += 1
            
            # Track latency
            latency = (time.time() - start_time) * 1000
            self._latencies.append(latency)
            self._metrics["avg_latency_ms"] = sum(self._latencies) / len(self._latencies)
            
            # Publish response
            self._publish_response(request, response, latency)
            
            # Call callback if provided
            if request.callback:
                try:
                    request.callback(response)
                except Exception as e:
                    logger.error(f"Callback error for {request.request_id}: {e}")
            
            logger.info(f"✅ Request {request.request_id} completed in {latency:.0f}ms")
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Request {request.request_id} timed out after {request.timeout}s")
            await self._handle_failure(request, circuit, "timeout")
            
        except Exception as e:
            logger.error(f"❌ Request {request.request_id} failed: {e}")
            await self._handle_failure(request, circuit, str(e))
        
        finally:
            with self._active_lock:
                self._active_requests.pop(request.request_id, None)
    
    async def _handle_failure(
        self,
        request: BrainRequest,
        circuit: CircuitBreaker,
        error: str,
    ) -> None:
        """Handle request failure with retry logic."""
        circuit.record_failure()
        
        if request.retries_left > 0:
            # Exponential backoff with jitter
            base_delay = 2 ** (3 - request.retries_left)  # 1, 2, 4 seconds
            jitter = base_delay * 0.2 * (time.time() % 1)
            delay = base_delay + jitter
            
            request.retries_left -= 1
            logger.info(f"🔄 Retrying {request.request_id} in {delay:.1f}s ({request.retries_left} left)")
            
            await asyncio.sleep(delay)
            await self._request_queue.put(request)
        else:
            self._metrics["failed_requests"] += 1
            self._publish_error(request.request_id, f"Failed after retries: {error}")
    
    # ========================================================================
    # OLLAMA INTERACTION
    # ========================================================================
    
    async def _call_ollama(self, request: BrainRequest, handler: DomainHandler) -> str:
        """Call Ollama API — SOTA 2026 with streaming, keep_alive, fast-fail, VRAM optimization."""
        import aiohttp
        
        # SOTA 2026: Set GPU acceleration env vars
        os.environ.setdefault('OLLAMA_FLASH_ATTENTION', '1')
        os.environ.setdefault('OLLAMA_KV_CACHE_TYPE', 'q8_0')
        
        # Build messages with system prompt
        system_prompt = handler.get_system_prompt()
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add context if available
        if request.context:
            context_str = json.dumps(request.context, default=str)[:2000]
            messages.append({"role": "system", "content": f"Context: {context_str}"})
        
        messages.append({"role": "user", "content": request.prompt})
        
        # Select model based on domain (checks availability)
        model = self._select_model(request.domain)
        
        url = f"{self._ollama_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,  # SOTA 2026: Always stream for instant TTFT
            "keep_alive": -1,
            "options": {
                "temperature": 0.7,
                "num_predict": 2048 if request.domain != RequestDomain.VOICE else 256,
                "num_ctx": 4096,  # SOTA 2026: Limit context to save VRAM (KV cache)
            }
        }
        
        full_response = ""
        
        # OLLAMA CLOUD: Add API key for cloud model authentication
        headers = {}
        ollama_api_key = os.environ.get('OLLAMA_API_KEY', '')
        if ollama_api_key:
            headers['Authorization'] = f'Bearer {ollama_api_key}'
        
        # SOTA 2026: Fast-fail timeout — 10s connect, 120s read for streaming
        timeout = aiohttp.ClientTimeout(sock_connect=10, sock_read=120)
        
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 500:
                    error_text = await resp.text()
                    logger.warning(f"⚠️ {model} HTTP 500 (likely VRAM full): {error_text[:200]}")
                    raise MemoryError(f"Ollama {model} VRAM error: {error_text[:200]}")
                elif resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"Ollama error {resp.status}: {error_text[:200]}")
                
                async for line in resp.content:
                    if line:
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                full_response += content
                                self._publish_delta(request.request_id, content)
                            
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        
        return full_response
    
    def _select_model(self, domain: RequestDomain) -> str:
        """Select model via the central orchestrator."""
        domain_map = {
            "CODE": "code",
            "TRADING": "trading",
            "VOICE": "voice",
            "CREATIVE": "creative_studio",
        }
        task = domain_map.get(domain.name, "general") if hasattr(domain, 'name') else "general"
        try:
            from core.ollama_gateway import orchestrator
            return orchestrator.get_model_for_task(task)
        except ImportError:
            pass
        return "cogito:latest"
    
    # ========================================================================
    # EVENT PUBLISHING
    # ========================================================================
    
    def _publish_progress(self, request_id: str, stage: str, data: Dict[str, Any]) -> None:
        """Publish progress event for UI feedback."""
        if self.event_bus:
            self.event_bus.publish("brain.progress", {
                "request_id": request_id,
                "stage": stage,
                "timestamp": time.time(),
                **data
            })
    
    def _publish_delta(self, request_id: str, content: str) -> None:
        """Publish streaming delta."""
        if self.event_bus:
            self.event_bus.publish("ai.response.delta", {
                "request_id": request_id,
                "delta": content,
                "timestamp": time.time(),
            })
    
    def _publish_response(self, request: BrainRequest, response: str, latency_ms: float) -> None:
        """Publish final response."""
        if self.event_bus:
            self.event_bus.publish("ai.response.unified", {
                "request_id": request.request_id,
                "response": response,
                "domain": request.domain.value,
                "latency_ms": latency_ms,
                "speak": request.speak,
                "awareness_snapshot": request.context.get("awareness_snapshot"),
                "timestamp": time.time(),
            })
            
            # Also publish brain.response for direct subscribers
            self.event_bus.publish("brain.response", {
                "request_id": request.request_id,
                "response": response,
                "domain": request.domain.value,
                "speak": request.speak,
            })
    
    def _publish_error(self, request_id: str, error: str) -> None:
        """Publish error event."""
        if self.event_bus:
            self.event_bus.publish("brain.error", {
                "request_id": request_id,
                "error": error,
                "timestamp": time.time(),
            })
            self.event_bus.publish("ai.response.error", {
                "request_id": request_id,
                "error": error,
            })
    
    # ========================================================================
    # MAINTENANCE TASKS
    # ========================================================================
    
    async def _metrics_reporter(self) -> None:
        """Periodically report metrics."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(30)
            
            logger.info(
                f"📊 Brain Metrics: "
                f"total={self._metrics['total_requests']}, "
                f"completed={self._metrics['completed_requests']}, "
                f"failed={self._metrics['failed_requests']}, "
                f"queue={self._request_queue.qsize()}, "
                f"avg_latency={self._metrics['avg_latency_ms']:.0f}ms"
            )
            if time.time() - self._last_capability_publish_ts >= 60.0:
                self._publish_capability_snapshot(reason="metrics_cycle")
            
            if self.event_bus:
                self.event_bus.publish("brain.metrics", self._metrics.copy())
    
    async def _dedup_cleaner(self) -> None:
        """Clean old entries from dedup cache."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(60)
            
            cutoff = time.time() - self._dedup_window * 2
            with self._dedup_lock:
                expired = [k for k, v in self._seen_requests.items() if v < cutoff]
                for k in expired:
                    del self._seen_requests[k]
                
                if expired:
                    logger.debug(f"🧹 Cleaned {len(expired)} old dedup entries")
    
    async def _get_live_trading_data(self) -> Dict[str, Any]:
        """Get live trading data for context injection from the live data integrator."""
        if self.live_data_integrator is None:
            return {}
        try:
            getter = getattr(self.live_data_integrator, "get_latest_data", None)
            if callable(getter):
                result = getter()
                if asyncio.iscoroutine(result):
                    result = await result
                return result if isinstance(result, dict) else {}
        except Exception as exc:
            logger.debug("Live trading data fetch failed: %s", exc)
        return {}
    
    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            "queue_size": self._request_queue.qsize(),
            "max_size": self.max_queue_size,
            "active_requests": len(self._active_requests),
            "metrics": self._metrics.copy(),
            "circuit_breakers": {
                domain: {
                    "state": cb.state.value,
                    "failures": cb.failure_count,
                }
                for domain, cb in self._circuit_breakers.items()
            },
            "nemoclaw": {
                "available": self._nemoclaw_available,
                "sandbox_status": getattr(self._nemoclaw_bridge, "sandbox_status", "unknown")
                    if self._nemoclaw_bridge else "not_configured",
            },
        }
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the brain."""
        logger.info("🧠 KingdomAIBrain shutting down...")
        
        self._shutdown_event.set()
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        logger.info("✅ KingdomAIBrain shutdown complete")


# ============================================================================
# FACTORY & SINGLETON
# ============================================================================

_brain_instance: Optional[KingdomAIBrain] = None
_brain_lock = threading.Lock()


def get_kingdom_brain(
    event_bus: Any = None,
    config: Optional[Dict[str, Any]] = None,
) -> KingdomAIBrain:
    """Get or create the singleton KingdomAIBrain instance."""
    global _brain_instance
    
    with _brain_lock:
        if _brain_instance is None:
            _brain_instance = KingdomAIBrain(event_bus=event_bus, config=config)
        elif event_bus and not _brain_instance.event_bus:
            _brain_instance.event_bus = event_bus
            _brain_instance._subscribe_to_events()
        
        return _brain_instance


async def initialize_kingdom_brain(
    event_bus: Any = None,
    config: Optional[Dict[str, Any]] = None,
) -> KingdomAIBrain:
    """Initialize and return the Kingdom AI Brain."""
    brain = get_kingdom_brain(event_bus, config)
    await brain.initialize()
    return brain
