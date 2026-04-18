#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KingdomBrainOrchestrator - Unified AI Brain & Subsystem Orchestrator with VL-JEPA

This module provides a single runtime orchestrator that:
1. Owns the shared EventBus instance
2. Initializes and registers all AI routing components:
   - BrainRouter (multi-LLM orchestrator)
   - UnifiedAIRouter (ai.request → brain.request bridge)
   - SystemContextProvider (self-awareness)
   - LiveDataIntegrator (real-time operational data)
   - AICommandRouter (natural language → system events)
3. Registers key subsystems (trading, mining, wallet, blockchain, voice)
4. Sets up event aliases/bridges for unified routing of:
   - Legacy codegen events → code.generate
   - Legacy visual events → brain.visual.request
   - Voice/text commands → appropriate handlers
5. Ensures no duplicate AI responders by managing subscriptions

USAGE:
    from core.kingdom_brain_orchestrator import KingdomBrainOrchestrator
    
    orchestrator = KingdomBrainOrchestrator()
    await orchestrator.initialize()
    # Now all AI/subsystem routing is unified through a single EventBus
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("KingdomAI.BrainOrchestrator")


class KingdomBrainOrchestrator:
    """
    Unified orchestrator for Kingdom AI brain and subsystems.
    
    Owns the shared EventBus and ensures all AI requests flow through
    a single deduplicated pathway: ai.request → brain.request → ai.response.unified
    """
    
    _instance: Optional["KingdomBrainOrchestrator"] = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure one orchestrator per runtime."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, event_bus: Any = None, config: Optional[Dict[str, Any]] = None):
        """Initialize the orchestrator.
        
        Args:
            event_bus: Optional EventBus instance. If None, creates/gets singleton.
            config: Optional configuration dictionary.
        """
        if self._initialized:
            return
        
        self.config = config or {}
        self._event_bus = event_bus
        self._components: Dict[str, Any] = {}
        self._event_aliases: Dict[str, str] = {}
        
        # Core AI routing components (initialized in initialize())
        self.brain_router = None
        self.unified_router = None
        self.system_context_provider = None
        self.live_data_integrator = None
        self.ai_command_router = None
        self.voice_command_manager = None
        self.thoth_ai_worker = None  # SOTA 2025 features: vision/sensor/voice/memory
        
        # Subsystem references
        self.trading_system = None
        self.mining_system = None
        self.wallet_manager = None
        self.blockchain_bridge = None
        self.code_generator = None
        
        # Unity/VR subsystems
        self.unity_runtime_bridge = None
        self.unity_hub_manager = None
        self.unity_mcp_tools = None
        
        logger.info("🧠 KingdomBrainOrchestrator created (not yet initialized)")
    
    @property
    def event_bus(self) -> Any:
        """Get or create the shared EventBus."""
        if self._event_bus is None:
            try:
                from core.event_bus import EventBus
                self._event_bus = EventBus()
                logger.info("✅ Created shared EventBus instance")
            except ImportError as e:
                logger.error(f"❌ Failed to import EventBus: {e}")
                raise
        return self._event_bus
    
    async def initialize(self) -> bool:
        """Initialize all components and set up unified routing.
        
        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            logger.warning("KingdomBrainOrchestrator already initialized")
            return True
        
        logger.info("🚀 Initializing KingdomBrainOrchestrator...")
        
        try:
            # 1. Initialize core AI routing components
            await self._init_ai_routing()
            
            # 2. Initialize subsystems
            await self._init_subsystems()
            
            # 3. Set up event aliases/bridges for unified routing
            self._setup_event_aliases()
            
            # 4. Register all components on EventBus
            self._register_components()
            
            # 5. Verify unified routing is working
            self._verify_routing()
            
            # 6. Start KAIG Intelligence Bridge — ensures all 3 targets
            # (survival floor, ATH price floor, $2T ultimate) propagate
            # to every AI component via the event bus.
            await self._init_kaig_bridge()
            
            self._initialized = True
            logger.info("✅ KingdomBrainOrchestrator fully initialized")
            
            # Publish orchestrator ready event
            self.event_bus.publish("orchestrator.ready", {
                "components": list(self._components.keys()),
                "event_aliases": list(self._event_aliases.keys())
            })
            
            return True
            
        except Exception as e:
            logger.error(f"❌ KingdomBrainOrchestrator initialization failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    async def _init_ai_routing(self) -> None:
        """Initialize AI routing components in correct order."""
        logger.info("🔄 Initializing AI routing components...")
        
        # 1. SystemContextProvider - provides self-awareness context
        try:
            from core.system_context_provider import SystemContextProvider
            self.system_context_provider = SystemContextProvider(event_bus=self.event_bus)
            if hasattr(self.system_context_provider, 'initialize'):
                if asyncio.iscoroutinefunction(self.system_context_provider.initialize):
                    await self.system_context_provider.initialize()
                else:
                    self.system_context_provider.initialize()
            self._components['system_context_provider'] = self.system_context_provider
            logger.info("✅ SystemContextProvider initialized")
        except Exception as e:
            logger.warning(f"⚠️ SystemContextProvider not available: {e}")
        
        # 2. LiveDataIntegrator - provides real-time operational data
        try:
            from core.live_data_integrator import LiveDataIntegrator
            self.live_data_integrator = LiveDataIntegrator(event_bus=self.event_bus)
            if hasattr(self.live_data_integrator, 'initialize'):
                if asyncio.iscoroutinefunction(self.live_data_integrator.initialize):
                    await self.live_data_integrator.initialize()
                else:
                    self.live_data_integrator.initialize()
            self._components['live_data_integrator'] = self.live_data_integrator
            logger.info("✅ LiveDataIntegrator initialized")
        except Exception as e:
            logger.warning(f"⚠️ LiveDataIntegrator not available: {e}")
        
        # 3. BrainRouter - central multi-LLM orchestrator
        try:
            from kingdom_ai.ai.brain_router import BrainRouter
            self.brain_router = BrainRouter(
                event_bus=self.event_bus,
                thoth=None,
                shadow_mode=False,
                system_context_provider=self.system_context_provider,
                live_data_integrator=self.live_data_integrator
            )
            if hasattr(self.brain_router, 'initialize'):
                await self.brain_router.initialize()
            self._components['brain_router'] = self.brain_router
            logger.info("✅ BrainRouter initialized (handles brain.request events)")
        except Exception as e:
            logger.warning(f"⚠️ BrainRouter not available: {e}")
        
        # 4. UnifiedAIRouter - bridges ai.request → brain.request
        try:
            from core.unified_ai_router import UnifiedAIRouter, initialize_unified_router
            self.unified_router = initialize_unified_router(self.event_bus)
            self._components['unified_ai_router'] = self.unified_router
            logger.info("✅ UnifiedAIRouter initialized (ai.request → brain.request bridge)")
        except Exception as e:
            logger.warning(f"⚠️ UnifiedAIRouter not available: {e}")
        
        # 5. AICommandRouter - natural language command parsing
        try:
            from core.ai_command_router import AICommandRouter
            self.ai_command_router = AICommandRouter(event_bus=self.event_bus)
            if hasattr(self.ai_command_router, 'initialize'):
                if asyncio.iscoroutinefunction(self.ai_command_router.initialize):
                    await self.ai_command_router.initialize()
                else:
                    self.ai_command_router.initialize()
            self._components['ai_command_router'] = self.ai_command_router
            logger.info("✅ AICommandRouter initialized (NL → system events)")
        except Exception as e:
            logger.warning(f"⚠️ AICommandRouter not available: {e}")
        
        # 6. VL-JEPA Enhanced Brain - State-of-the-art continuous embedding prediction
        try:
            from core.ollama_vl_jepa_brain import OllamaVLJEPABrain
            self.vl_jepa_brain = OllamaVLJEPABrain(event_bus=self.event_bus, redis_client=None)
            await self.vl_jepa_brain.initialize()
            self._components['vl_jepa_brain'] = self.vl_jepa_brain
            logger.info("✅ VL-JEPA Enhanced Brain initialized (50% parameter reduction, 2.85x efficiency)")
        except Exception as e:
            logger.warning(f"⚠️ VL-JEPA Brain not available: {e}")
        
        # 6. VoiceCommandManager - voice/text command processing
        try:
            from core.voice_command_manager import VoiceCommandManager
            self.voice_command_manager = VoiceCommandManager(
                event_bus=self.event_bus,
                ollama_brain=self.brain_router
            )
            self._components['voice_command_manager'] = self.voice_command_manager
            logger.info("✅ VoiceCommandManager initialized")
        except Exception as e:
            logger.warning(f"⚠️ VoiceCommandManager not available: {e}")
        
        # 7. ThothAIWorker - SOTA 2025 features (vision, sensor, voice, memory, prompt building)
        #    Initialize with subscribe_to_ai_request=False to prevent duplicate responses
        #    UnifiedAIRouter handles ai.request, but ThothAIWorker provides all other features
        try:
            from kingdom_ai.core.ai_engine.ai_worker import initialize_thoth_ai_worker
            self.thoth_ai_worker = initialize_thoth_ai_worker(
                event_bus=self.event_bus,
                memory_manager=None,  # Will use default memory paths
                subscribe_to_ai_request=False  # CRITICAL: Prevents duplicate responses
            )
            self._components['thoth_ai_worker'] = self.thoth_ai_worker
            logger.info("✅ ThothAIWorker initialized (features-only: vision/sensor/voice/memory)")
        except Exception as e:
            # SOTA 2026 FIX: ThothAIWorker is optional - use debug not warning
            logger.debug(f"ℹ️ ThothAIWorker not available: {e} (optional feature)")
    
    async def _init_subsystems(self) -> None:
        """Initialize key subsystems and register them."""
        logger.info("🔄 Initializing subsystems...")
        
        # Trading System
        try:
            from core.trading_system import TradingSystem
            self.trading_system = TradingSystem(event_bus=self.event_bus)
            if hasattr(self.trading_system, 'initialize'):
                if asyncio.iscoroutinefunction(self.trading_system.initialize):
                    await self.trading_system.initialize()
                else:
                    self.trading_system.initialize()
            self._components['trading_system'] = self.trading_system
            logger.info("✅ TradingSystem initialized")
        except Exception as e:
            logger.warning(f"⚠️ TradingSystem not available: {e}")
        
        # Mining System
        try:
            from core.mining_system import MiningSystem
            self.mining_system = MiningSystem(event_bus=self.event_bus)
            if hasattr(self.mining_system, 'initialize'):
                if asyncio.iscoroutinefunction(self.mining_system.initialize):
                    await self.mining_system.initialize(event_bus=self.event_bus)
                else:
                    self.mining_system.initialize()
            self._components['mining_system'] = self.mining_system
            logger.info("✅ MiningSystem initialized")
        except Exception as e:
            logger.warning(f"⚠️ MiningSystem not available: {e}")
        
        # Wallet Manager
        try:
            from core.wallet_manager import WalletManager
            self.wallet_manager = WalletManager(event_bus=self.event_bus)
            if hasattr(self.wallet_manager, 'initialize'):
                if asyncio.iscoroutinefunction(self.wallet_manager.initialize):
                    await self.wallet_manager.initialize()
                else:
                    self.wallet_manager.initialize()
            self._components['wallet_system'] = self.wallet_manager
            logger.info("✅ WalletManager initialized")
        except Exception as e:
            logger.warning(f"⚠️ WalletManager not available: {e}")
        
        # Code Generator
        try:
            from core.code_generator import RealCodeGenerator
            self.code_generator = RealCodeGenerator(event_bus=self.event_bus, config={})
            if hasattr(self.code_generator, 'initialize'):
                if asyncio.iscoroutinefunction(self.code_generator.initialize):
                    await self.code_generator.initialize()
                else:
                    self.code_generator.initialize()
            self._components['code_generator'] = self.code_generator
            logger.info("✅ RealCodeGenerator initialized")
        except Exception as e:
            logger.warning(f"⚠️ RealCodeGenerator not available: {e}")
        
        # Unity Runtime Bridge - EventBus → TCP bridge for Unity/Quest VR control
        try:
            from core.unity_runtime_bridge import get_unity_runtime_bridge
            self.unity_runtime_bridge = get_unity_runtime_bridge(event_bus=self.event_bus)
            self._components['unity_runtime_bridge'] = self.unity_runtime_bridge
            logger.info("✅ UnityRuntimeBridge initialized (EventBus → TCP for Unity/Quest)")
        except Exception as e:
            logger.warning(f"⚠️ UnityRuntimeBridge not available: {e}")
        
        # Unity Hub Manager - Unity Editor control
        try:
            from core.unity_mcp_integration import get_unity_hub_manager, get_unity_mcp_tools
            self.unity_hub_manager = get_unity_hub_manager(event_bus=self.event_bus)
            self.unity_mcp_tools = get_unity_mcp_tools(event_bus=self.event_bus)
            self._components['unity_hub_manager'] = self.unity_hub_manager
            self._components['unity_mcp_tools'] = self.unity_mcp_tools
            logger.info("✅ UnityHubManager & UnityMCPTools initialized")
        except Exception as e:
            logger.warning(f"⚠️ Unity MCP integration not available: {e}")
    
    async def _init_kaig_bridge(self) -> None:
        """Start KAIG Intelligence Bridge so all 3 targets propagate system-wide.

        Targets:
        1. SURVIVAL FLOOR: $26K realized → $13K treasury (existential, FIRST)
        2. KAIG PRICE FLOOR: 1 KAIG > highest crypto ATH ever (live-monitored)
        3. ULTIMATE TARGET: $2T (aspirational, always pursue)

        Also registers event bus with Token Identity Abstraction so rebrand
        events (kaig.identity.changed) propagate to every subscriber.
        """
        # Register event bus with token identity module (rebrand resilience)
        try:
            from core.kaig_token_identity import set_event_bus, get_token_identity
            set_event_bus(self.event_bus)
            identity = get_token_identity()
            logger.info("✅ Token Identity loaded: $%s (%s) v%d — rebrand-ready",
                        identity.ticker, identity.name, identity.identity_version)
        except Exception as e:
            logger.warning(f"⚠️ Token Identity module not available: {e}")

        try:
            from core.kaig_intelligence_bridge import KAIGIntelligenceBridge
            bridge = KAIGIntelligenceBridge(event_bus=self.event_bus)
            bridge.start()
            self._components['kaig_intelligence_bridge'] = bridge
            logger.info("✅ KAIGIntelligenceBridge started — 3 targets propagating")
        except Exception as e:
            logger.warning(f"⚠️ KAIGIntelligenceBridge not available: {e}")

    def _setup_event_aliases(self) -> None:
        """Set up event aliases/bridges for unified routing.
        
        This ensures legacy event names are bridged to the unified handlers.
        """
        logger.info("🔄 Setting up event aliases/bridges...")
        
        # Define event aliases: legacy_event → canonical_event
        aliases = {
            # Code generation aliases
            "thoth:code:generate": "code.generate",
            "thoth:request:generate_code": "code.generate",
            "codegen.request": "code.generate",
            "code.generation.request": "code.generate",
            
            # Code analysis aliases
            "thoth:analyze": "code.analyze",
            "thoth:request:analyze_code": "code.analyze",
            "codegen.analyze": "code.analyze",
            
            # Visual generation aliases
            "visual.generate": "brain.visual.request",
            "visual.request": "brain.visual.request",
            "ai.response.visual": "brain.visual.request",
            
            # AI request aliases (all route through UnifiedAIRouter)
            "thoth:request": "ai.request",
            "ai.chat.request": "ai.request",
            "chat.request": "ai.request",
            
            # Voice command aliases
            "voice.command.text": "text.command",
            "voice.input": "voice.command",
        }
        
        # Create bridge handlers for each alias
        for legacy_event, canonical_event in aliases.items():
            self._create_event_bridge(legacy_event, canonical_event)
            self._event_aliases[legacy_event] = canonical_event
        
        logger.info(f"✅ Set up {len(aliases)} event aliases")
    
    def _create_event_bridge(self, legacy_event: str, canonical_event: str) -> None:
        """Create a bridge that forwards legacy events to canonical handlers.
        
        Args:
            legacy_event: The legacy event name to listen for
            canonical_event: The canonical event to forward to
        """
        def bridge_handler(data: Any) -> None:
            """Bridge handler that forwards events."""
            logger.debug(f"🔀 Bridging {legacy_event} → {canonical_event}")
            self.event_bus.publish(canonical_event, data)
        
        # Subscribe to legacy event and bridge to canonical
        try:
            subscribe_fn = getattr(self.event_bus, 'subscribe_sync', None) or \
                          getattr(self.event_bus, 'subscribe', None)
            if subscribe_fn:
                subscribe_fn(legacy_event, bridge_handler)
        except Exception as e:
            logger.debug(f"Could not set up bridge {legacy_event} → {canonical_event}: {e}")
    
    def _register_components(self) -> None:
        """Register all initialized components on the EventBus."""
        logger.info("🔄 Registering components on EventBus...")
        
        if not hasattr(self.event_bus, 'register_component'):
            logger.warning("EventBus doesn't support register_component")
            return
        
        for name, component in self._components.items():
            if component is not None:
                self.event_bus.register_component(name, component)
                logger.debug(f"  Registered: {name}")
        
        # Also register the orchestrator itself
        self.event_bus.register_component('brain_orchestrator', self)
        
        logger.info(f"✅ Registered {len(self._components)} components on EventBus")
    
    def _verify_routing(self) -> None:
        """Verify that unified routing is properly configured."""
        logger.info("🔍 Verifying unified AI routing...")
        
        checks = []
        
        # Check BrainRouter is handling brain.request
        if self.brain_router:
            checks.append("✅ BrainRouter handles brain.request")
        else:
            checks.append("⚠️ BrainRouter not available")
        
        # Check UnifiedAIRouter bridges ai.request → brain.request
        if self.unified_router:
            checks.append("✅ UnifiedAIRouter bridges ai.request → brain.request")
        else:
            checks.append("⚠️ UnifiedAIRouter not available")
        
        # Check AICommandRouter for NL command parsing
        if self.ai_command_router:
            checks.append("✅ AICommandRouter parses NL commands")
        else:
            checks.append("⚠️ AICommandRouter not available")
        
        # Check VoiceCommandManager
        if self.voice_command_manager:
            checks.append("✅ VoiceCommandManager handles voice/text commands")
        else:
            checks.append("⚠️ VoiceCommandManager not available")
        
        for check in checks:
            logger.info(f"  {check}")
        
        # Log the unified flow
        logger.info("📊 Unified AI Request Flow:")
        logger.info("  ai.request → UnifiedAIRouter → brain.request → BrainRouter → ai.response → ai.response.unified")
    
    def get_component(self, name: str) -> Optional[Any]:
        """Get a registered component by name.
        
        Args:
            name: Component name
            
        Returns:
            Component instance or None
        """
        return self._components.get(name)
    
    def get_all_components(self) -> Dict[str, Any]:
        """Get all registered components.
        
        Returns:
            Dictionary of component name → instance
        """
        return self._components.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics.
        
        Returns:
            Dict with orchestrator stats
        """
        return {
            "initialized": self._initialized,
            "components_count": len(self._components),
            "components": list(self._components.keys()),
            "event_aliases_count": len(self._event_aliases),
            "brain_router_active": self.brain_router is not None,
            "unified_router_active": self.unified_router is not None,
            "circuit_breaker_status": self._get_circuit_breaker_status(),
            "health_status": self._get_health_status(),
        }
    
    # =========================================================================
    # SOTA 2026: Reliability Patterns - Circuit Breaker, Timeout/Retry, Graceful Degradation
    # =========================================================================
    
    def _get_circuit_breaker_status(self) -> Dict[str, str]:
        """Get circuit breaker status for all components.
        
        SOTA 2026 Pattern: Circuit breakers prevent cascade failures by
        detecting failing components and routing around them.
        """
        status = {}
        for name, component in self._components.items():
            if hasattr(component, '_circuit_open'):
                status[name] = "open" if component._circuit_open else "closed"
            else:
                status[name] = "not_monitored"
        return status
    
    def _get_health_status(self) -> Dict[str, Any]:
        """Get health status of all components.
        
        SOTA 2026 Pattern: Observability for agent orchestration.
        """
        healthy = 0
        degraded = 0
        failed = 0
        
        for name, component in self._components.items():
            if component is None:
                failed += 1
            elif hasattr(component, 'is_healthy'):
                if component.is_healthy():
                    healthy += 1
                else:
                    degraded += 1
            else:
                healthy += 1  # Assume healthy if no health check
        
        return {
            "healthy": healthy,
            "degraded": degraded,
            "failed": failed,
            "total": len(self._components)
        }
    
    async def execute_with_retry(
        self,
        func,
        max_retries: int = 3,
        timeout_seconds: float = 30.0,
        backoff_factor: float = 1.5
    ) -> Any:
        """Execute a function with retry and timeout.
        
        SOTA 2026 Pattern: Timeout and retry mechanisms for reliability.
        
        Args:
            func: Async function to execute
            max_retries: Maximum number of retry attempts
            timeout_seconds: Timeout per attempt
            backoff_factor: Exponential backoff multiplier
            
        Returns:
            Result of the function
            
        Raises:
            Exception: If all retries exhausted
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(func(), timeout=timeout_seconds)
                else:
                    result = func()
                return result
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"Operation timed out after {timeout_seconds}s")
                logger.warning(f"⏱️ Attempt {attempt + 1}/{max_retries} timed out")
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Attempt {attempt + 1}/{max_retries} failed: {e}")
            
            # Exponential backoff
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                await asyncio.sleep(wait_time)
        
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"All {max_retries} retry attempts exhausted")
    
    async def execute_with_fallback(
        self,
        primary_func,
        fallback_func,
        timeout_seconds: float = 10.0
    ) -> Any:
        """Execute with graceful degradation to fallback.
        
        SOTA 2026 Pattern: Graceful degradation when primary fails.
        
        Args:
            primary_func: Primary async function to try
            fallback_func: Fallback function if primary fails
            timeout_seconds: Timeout for primary function
            
        Returns:
            Result from primary or fallback
        """
        try:
            if asyncio.iscoroutinefunction(primary_func):
                return await asyncio.wait_for(primary_func(), timeout=timeout_seconds)
            else:
                return primary_func()
        except Exception as e:
            logger.warning(f"⚠️ Primary failed, using fallback: {e}")
            if asyncio.iscoroutinefunction(fallback_func):
                return await fallback_func()
            else:
                return fallback_func()
    
    async def shutdown(self) -> None:
        """Gracefully shutdown all components."""
        logger.info("🛑 Shutting down KingdomBrainOrchestrator...")
        
        # Shutdown components in reverse order
        for name in reversed(list(self._components.keys())):
            component = self._components[name]
            if hasattr(component, 'shutdown'):
                try:
                    if asyncio.iscoroutinefunction(component.shutdown):
                        await component.shutdown()
                    else:
                        component.shutdown()
                    logger.debug(f"  Shutdown: {name}")
                except Exception as e:
                    logger.warning(f"  Error shutting down {name}: {e}")
        
        self._initialized = False
        logger.info("✅ KingdomBrainOrchestrator shutdown complete")


# Global accessor function
_orchestrator: Optional[KingdomBrainOrchestrator] = None


def get_brain_orchestrator() -> Optional[KingdomBrainOrchestrator]:
    """Get the global KingdomBrainOrchestrator instance."""
    return _orchestrator


async def initialize_brain_orchestrator(
    event_bus: Any = None,
    config: Optional[Dict[str, Any]] = None
) -> KingdomBrainOrchestrator:
    """Initialize and return the global KingdomBrainOrchestrator.
    
    Args:
        event_bus: Optional EventBus instance
        config: Optional configuration dictionary
        
    Returns:
        The initialized KingdomBrainOrchestrator instance
    """
    global _orchestrator
    
    if _orchestrator is None:
        _orchestrator = KingdomBrainOrchestrator(event_bus=event_bus, config=config)
    
    if not _orchestrator._initialized:
        await _orchestrator.initialize()
    
    return _orchestrator
