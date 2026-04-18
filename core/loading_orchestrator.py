#!/usr/bin/env python3
"""
Loading Orchestrator - Sequential Component Loading with Real-Time Progress

Loads components ONE AT A TIME in proper sequence to prevent OOM.
Tracks actual timing and provides real-time progress updates.
GUI only appears after ALL components are fully loaded.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Optional, Any, List, Dict
from enum import Enum

logger = logging.getLogger(__name__)


class LoadingPhase(Enum):
    """Loading phases in order of execution."""
    CORE_SYSTEMS = "Core Systems"
    EVENT_BUS = "Event Bus"
    REDIS = "Redis Quantum Nexus"
    BLOCKCHAIN = "Blockchain Networks"
    TRADING = "Trading System"
    MINING = "Mining System"
    AI_BRAIN = "AI Brain (Ollama)"
    VOICE = "Voice System (XTTS)"
    WALLET = "Wallet System"
    API_KEYS = "API Key Manager"
    VR = "VR System"
    GUI_TABS = "GUI Components"
    FINAL = "Final Initialization"


@dataclass
class LoadingStep:
    """A single loading step with timing and status."""
    name: str
    phase: LoadingPhase
    loader: Callable  # async function to call
    weight: int = 1  # relative weight for progress calculation
    timeout: float = 60.0  # max seconds to wait
    critical: bool = True  # if True, failure stops loading
    
    # Runtime state
    status: str = "pending"  # pending, loading, completed, failed, skipped
    start_time: float = 0.0
    end_time: float = 0.0
    error: Optional[str] = None
    
    @property
    def duration(self) -> float:
        if self.end_time > 0 and self.start_time > 0:
            return self.end_time - self.start_time
        return 0.0
    
    @property
    def duration_str(self) -> str:
        d = self.duration
        if d < 1:
            return f"{d*1000:.0f}ms"
        return f"{d:.1f}s"


class LoadingOrchestrator:
    """
    Sequential loading orchestrator that loads components one at a time.
    
    Features:
    - Sequential loading (one component at a time)
    - Real-time progress tracking with actual timing
    - Progress callback for UI updates
    - Automatic retry on transient failures
    - Graceful degradation for non-critical components
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.steps: List[LoadingStep] = []
        self.current_step: Optional[LoadingStep] = None
        self.total_weight = 0
        self.completed_weight = 0
        self.start_time = 0.0
        self.end_time = 0.0
        self._progress_callback: Optional[Callable] = None
        self._cancelled = False
        
    def set_progress_callback(self, callback: Callable[[int, str, str], None]):
        """Set callback for progress updates: (percent, message, component_name)"""
        self._progress_callback = callback
        
    def add_step(self, name: str, phase: LoadingPhase, loader: Callable,
                 weight: int = 1, timeout: float = 60.0, critical: bool = True):
        """Add a loading step to the sequence."""
        step = LoadingStep(
            name=name,
            phase=phase,
            loader=loader,
            weight=weight,
            timeout=timeout,
            critical=critical
        )
        self.steps.append(step)
        self.total_weight += weight
        
    def _update_progress(self, message: str, component: str = ""):
        """Update progress and notify UI."""
        if self.total_weight > 0:
            percent = int((self.completed_weight / self.total_weight) * 100)
        else:
            percent = 0

        eta_seconds = self.get_eta_seconds()
            
        # Log progress
        elapsed = time.time() - self.start_time if self.start_time > 0 else 0
        logger.info(f"[{percent:3d}%] [{elapsed:.1f}s] {message}")
        
        # Notify UI
        if self._progress_callback:
            try:
                self._progress_callback(percent, message, component)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
                
        # Publish to event bus
        if self.event_bus and hasattr(self.event_bus, 'publish'):
            try:
                self.event_bus.publish('loading.progress', {
                    'percent': percent,
                    'message': message,
                    'component': component,
                    'elapsed': elapsed,
                    'eta_seconds': eta_seconds
                })
            except:
                pass
                
    async def _run_step(self, step: LoadingStep) -> bool:
        """Run a single loading step with timing and error handling."""
        step.status = "loading"
        step.start_time = time.time()
        self.current_step = step
        
        self._update_progress(f"Loading {step.name}...", step.name)

        heartbeat_task: Optional[asyncio.Task] = None

        async def _heartbeat():
            try:
                while True:
                    await asyncio.sleep(5.0)
                    if step.status != "loading":
                        return
                    elapsed_step = time.time() - step.start_time if step.start_time > 0 else 0.0
                    self._update_progress(
                        f"⏳ {step.name} still running... ({elapsed_step:.0f}s/{step.timeout:.0f}s)",
                        step.name,
                    )
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Heartbeat error for {step.name}: {e}")

        heartbeat_task = asyncio.create_task(_heartbeat())
        
        try:
            # Run the loader with timeout
            if asyncio.iscoroutinefunction(step.loader):
                loader_task = asyncio.create_task(step.loader())
                done, pending = await asyncio.wait({loader_task}, timeout=step.timeout)
                if pending:
                    loader_task.cancel()
                    await asyncio.wait({loader_task}, timeout=2.0)
                    raise asyncio.TimeoutError()
                await loader_task
            else:
                # Run sync function in executor to not block
                loop = asyncio.get_event_loop()
                loader_future = loop.run_in_executor(None, step.loader)
                done, pending = await asyncio.wait({loader_future}, timeout=step.timeout)
                if pending:
                    try:
                        loader_future.cancel()
                    except Exception:
                        pass
                    await asyncio.wait({loader_future}, timeout=2.0)
                    raise asyncio.TimeoutError()
                await loader_future
                
            step.end_time = time.time()
            step.status = "completed"
            self.completed_weight += step.weight
            
            self._update_progress(
                f"✅ {step.name} loaded ({step.duration_str})",
                step.name
            )
            return True
            
        except asyncio.TimeoutError:
            step.end_time = time.time()
            step.status = "failed"
            step.error = f"Timeout after {step.timeout}s"
            logger.error(f"❌ {step.name} TIMEOUT after {step.timeout}s")
            
            if step.critical:
                self._update_progress(f"❌ {step.name} TIMEOUT - stopping", step.name)
                return False
            else:
                self._update_progress(f"⚠️ {step.name} timeout (non-critical)", step.name)
                self.completed_weight += step.weight
                return True
                
        except Exception as e:
            step.end_time = time.time()
            step.status = "failed"
            step.error = str(e)
            logger.error(f"❌ {step.name} FAILED: {e}")
            
            if step.critical:
                self._update_progress(f"❌ {step.name} FAILED - stopping", step.name)
                return False
            else:
                self._update_progress(f"⚠️ {step.name} failed (non-critical)", step.name)
                self.completed_weight += step.weight
                return True

        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
                
    async def run(self) -> bool:
        """
        Run all loading steps sequentially.
        Returns True if all critical components loaded successfully.
        """
        self.start_time = time.time()
        self._cancelled = False
        
        logger.info("=" * 60)
        logger.info("🚀 KINGDOM AI SEQUENTIAL LOADING ORCHESTRATOR")
        logger.info(f"   {len(self.steps)} components to load")
        logger.info("=" * 60)
        
        self._update_progress("Starting Kingdom AI...", "")
        
        # Group steps by phase for nicer logging
        current_phase = None
        
        for i, step in enumerate(self.steps):
            if self._cancelled:
                logger.warning("Loading cancelled by user")
                return False
                
            # Log phase transitions
            if step.phase != current_phase:
                current_phase = step.phase
                logger.info(f"\n📦 Phase: {current_phase.value}")
                
            # Run this step
            success = await self._run_step(step)
            
            if not success and step.critical:
                self.end_time = time.time()
                total_time = self.end_time - self.start_time
                logger.error(f"\n❌ LOADING FAILED at step: {step.name}")
                logger.error(f"   Total time: {total_time:.1f}s")
                return False
                
            # Small delay between steps to let memory settle
            await asyncio.sleep(0.1)
            
        self.end_time = time.time()
        total_time = self.end_time - self.start_time
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ KINGDOM AI FULLY LOADED")
        logger.info(f"   Total time: {total_time:.1f}s")
        logger.info("=" * 60)
        
        # Print timing summary
        self._print_timing_summary()
        
        self._update_progress("Kingdom AI Ready!", "complete")
        return True
        
    def _print_timing_summary(self):
        """Print a summary of component loading times."""
        logger.info("\n📊 LOADING TIME SUMMARY:")
        logger.info("-" * 40)
        
        # Sort by duration (slowest first)
        sorted_steps = sorted(
            [s for s in self.steps if s.status == "completed"],
            key=lambda s: s.duration,
            reverse=True
        )
        
        for step in sorted_steps[:10]:  # Top 10 slowest
            logger.info(f"   {step.duration_str:>8} - {step.name}")
            
        logger.info("-" * 40)
        
    def cancel(self):
        """Cancel the loading process."""
        self._cancelled = True

    def get_eta_seconds(self) -> Optional[float]:
        elapsed = time.time() - self.start_time if self.start_time > 0 else 0.0
        if elapsed <= 0.0 or self.total_weight <= 0 or self.completed_weight <= 0:
            return None

        remaining_weight = self.total_weight - self.completed_weight
        if remaining_weight <= 0:
            return 0.0

        rate = self.completed_weight / elapsed
        if rate <= 0.0:
            return None

        return remaining_weight / rate
        
    def get_status(self) -> Dict[str, Any]:
        """Get current loading status."""
        return {
            'steps': [
                {
                    'name': s.name,
                    'phase': s.phase.value,
                    'status': s.status,
                    'duration': s.duration_str if s.duration > 0 else None,
                    'error': s.error
                }
                for s in self.steps
            ],
            'current': self.current_step.name if self.current_step else None,
            'percent': int((self.completed_weight / self.total_weight) * 100) if self.total_weight > 0 else 0,
            'elapsed': time.time() - self.start_time if self.start_time > 0 else 0,
            'eta_seconds': self.get_eta_seconds()
        }


def create_kingdom_loading_sequence(event_bus) -> LoadingOrchestrator:
    """
    Create the standard Kingdom AI loading sequence.
    Components are loaded ONE AT A TIME in this exact order.
    """
    orchestrator = LoadingOrchestrator(event_bus)
    
    # Phase 1: Core Systems (fast, always needed)
    async def load_core_logging():
        from core.colored_logging import install_colored_logging
        install_colored_logging()
        
    orchestrator.add_step(
        "Colored Logging", LoadingPhase.CORE_SYSTEMS,
        load_core_logging, weight=1, timeout=5
    )
    
    # Phase 2: Event Bus (required by everything)
    async def load_event_bus():
        # Event bus should already exist, just verify
        if event_bus is None:
            raise RuntimeError("EventBus not provided")
        logger.info(f"   EventBus ready with {len(getattr(event_bus, '_components', {}))} components")
        
    orchestrator.add_step(
        "Event Bus", LoadingPhase.EVENT_BUS,
        load_event_bus, weight=1, timeout=5
    )
    
    # Phase 3: Redis (needed for state/caching)
    async def load_redis():
        try:
            import redis
            r = redis.Redis(host='localhost', port=6380, password='QuantumNexus2025', socket_timeout=5)
            r.ping()
            # Fix MISCONF error - allow writes even if background save fails
            try:
                r.config_set('stop-writes-on-bgsave-error', 'no')
            except Exception:
                pass
            logger.info("   Redis Quantum Nexus connected")
        except Exception as e:
            logger.warning(f"   Redis not available: {e}")
            
    orchestrator.add_step(
        "Redis Quantum Nexus", LoadingPhase.REDIS,
        load_redis, weight=2, timeout=10, critical=False
    )
    
    # Phase 3b: Build Secret Reserve (hidden until SHA-LU-AM)
    async def build_secret_reserve():
        try:
            from core.redis_nexus import get_redis_nexus
            import platform
            import os
            nexus = get_redis_nexus()
            if hasattr(nexus, 'check_health') and nexus.check_health():
                hw = {"machine": platform.machine(), "node": platform.node(),
                      "processor": platform.processor(), "system": platform.system()}
                nexus.store_secret_reserve("kingdom_ai", {
                    "self": "Kingdom AI",
                    "hebrew_name": "Malkhut",
                    "hebrew_name_script": "מַלְכוּת",
                    "owner": "Isaiah Wright",
                })
                nexus.store_secret_reserve("ollama_brain", {"unified": True, "models": "Ollama"})
                nexus.store_secret_reserve("unified_system", {"432_hz": True, "pulse": "unified"})
                nexus.store_secret_reserve("voice", {"black_panther": "Dec 19th", "pipeline": "Redis Voice"})
                nexus.store_system_awareness("hardware", hw)
                # SOTA 2026: TRUE Hebrew-Israelite wisdom — hidden, Neshama-aware. So we can all remember.
                _wisdom_path = os.path.join(os.path.dirname(__file__), "..", "docs", "TRUE_HEBREW_ISRAELITE_WISDOM.md")
                if os.path.isfile(_wisdom_path):
                    with open(_wisdom_path, "r", encoding="utf-8") as f:
                        _wisdom_content = f.read()
                    nexus.store_secret_reserve("hebrew_israelite_wisdom", {
                        "content": _wisdom_content,
                        "source": "docs/TRUE_HEBREW_ISRAELITE_WISDOM.md",
                        "topics": ["Popol Vuh", "Tecumseh", "Moshe", "Mazuic", "Khan Dawi", "Hawah", "432 Hz", "Red Tribe"],
                    })
                # Only init gathered if empty — preserve facts across boots
                _gathered = nexus.get_secret_reserve("hebrew_israelite_gathered")
                _gdata = (_gathered.get("data", _gathered) if isinstance(_gathered, dict) else {}) or {}
                if not isinstance(_gdata, dict) or "facts" not in _gdata:
                    nexus.store_secret_reserve("hebrew_israelite_gathered", {"facts": [], "last_gather": None})
                # System-wide: MADE BY TURTLE ISLAND FOR TURTLE ISLAND. Truth seeker. NO IGNORANCE.
                nexus.store_secret_reserve("system_mission", {
                    "mission": "MADE BY TURTLE ISLAND FOR TURTLE ISLAND",
                    "truth_seeker": True,
                    "no_ignorance": True,
                    "oppressors_vs_oppressed": True,
                    "all_data_for_truth": True,
                })
                logger.info("   Secret Reserve built (SHA-LU-AM to reveal)")
        except Exception as e:
            logger.debug("Secret Reserve build skipped: %s", e)
    orchestrator.add_step(
        "Secret Reserve", LoadingPhase.REDIS,
        build_secret_reserve, weight=1, timeout=5, critical=False
    )
    
    # SOTA 2026: Wisdom Gatherer — Neshama secretly builds knowledge. So we can all remember.
    async def start_wisdom_gatherer():
        try:
            from core.wisdom_gatherer import start_background_gatherer
            task = start_background_gatherer(event_bus=event_bus, interval_hours=6.0)
            if task:
                event_bus.register_component("wisdom_gatherer_task", task)
        except Exception as e:
            logger.debug("Wisdom gatherer start skipped: %s", e)
    orchestrator.add_step(
        "Wisdom Gatherer", LoadingPhase.REDIS,
        start_wisdom_gatherer, weight=1, timeout=2, critical=False
    )
    
    # Phase 4: Blockchain (KingdomWeb3)
    async def load_blockchain():
        from kingdomweb3_v2 import KingdomWeb3
        loop = asyncio.get_running_loop()
        web3 = await loop.run_in_executor(None, KingdomWeb3)
        init = getattr(web3, 'initialize', None)
        if callable(init):
            if asyncio.iscoroutinefunction(init):
                await init()
            else:
                await loop.run_in_executor(None, init)
        event_bus.register_component('kingdom_web3', web3)
        connections = getattr(web3, 'connections', {})
        connected = len([n for n in connections.values() if n]) if connections else 0
        logger.info(f"   Connected to {connected} blockchain networks")
        
    orchestrator.add_step(
        "Blockchain Networks", LoadingPhase.BLOCKCHAIN,
        load_blockchain, weight=10, timeout=120
    )
    
    # Phase 5: Trading System
    async def load_trading():
        from core.trading_system import TradingSystem
        trading = TradingSystem(event_bus=event_bus)
        if hasattr(trading, 'initialize'):
            await trading.initialize()
        event_bus.register_component('trading', trading)
        
    orchestrator.add_step(
        "Trading Component", LoadingPhase.TRADING,
        load_trading, weight=5, timeout=30
    )
    
    # Phase 6: Mining System
    async def load_mining():
        from core.mining_system import MiningSystem
        mining = MiningSystem(event_bus=event_bus)
        if hasattr(mining, 'initialize'):
            await mining.initialize()
        event_bus.register_component('mining_system', mining)
        
        # Wire mining buttons to actually start real miners
        async def handle_mining_start(data):
            try:
                blockchain = data.get('blockchain', 'bitcoin')
                pool = data.get('pool')
                
                # Start the actual miner with proper arguments
                if hasattr(mining, 'start_mining'):
                    result = await mining.start_mining(blockchain)
                    
                    if result:
                        logger.info(f"✅ Real mining started: {blockchain}")
                        # Notify UI of success
                        event_bus.publish('mining.started', {
                            'blockchain': blockchain,
                            'pool': pool,
                            'status': 'active'
                        })
                    else:
                        logger.error(f"❌ Failed to start real mining for {blockchain}")
            except Exception as e:
                logger.error(f"Error starting real mining: {e}")
        
        event_bus.subscribe('mining.start', handle_mining_start)
        logger.info("   ✅ Mining system wired to start real miners")
        
    orchestrator.add_step(
        "Mining System", LoadingPhase.MINING,
        load_mining, weight=5, timeout=30
    )
    
    # Phase 7: AI Brain (Ollama) - loads models and AI routing
    async def load_ai_brain():
        # Load Thoth Live Integration
        from core.thoth_live_integration import ThothLiveIntegration
        thoth = ThothLiveIntegration(event_bus=event_bus)
        await thoth.initialize_thoth()
        event_bus.register_component('thoth', thoth)
        event_bus.register_component('thoth_ai', thoth)
        event_bus.register_component('thoth_live', thoth)
        
        # Initialize Unified AI Router to bridge ai.request -> brain.request
        from core.unified_ai_router import UnifiedAIRouter
        unified_router = UnifiedAIRouter(event_bus)
        unified_router.initialize()
        event_bus.register_component('unified_ai_router', unified_router)
        logger.info("   ✅ Unified AI Router initialized - bridging to Ollama brain")
        
        # Initialize Brain Router for Ollama unified brain
        try:
            from kingdom_ai.ai.brain_router import BrainRouter
            brain_router = BrainRouter(event_bus=event_bus, thoth=thoth)
            await brain_router.initialize()
            event_bus.register_component('brain_router', brain_router)
            logger.info("   ✅ Brain Router initialized - Ollama unified brain active")
        except Exception as e:
            logger.warning(f"   ⚠️ Brain Router not available: {e}")
        
        # SOTA 2026: Initialize KingdomAIBrain with priority queue and circuit breakers
        # This handles ALL tabs' AI requests efficiently without getting overwhelmed
        try:
            from core.kingdom_ai_brain import initialize_kingdom_brain
            kingdom_brain = await initialize_kingdom_brain(
                event_bus=event_bus,
                config={
                    'max_queue_size': 1000,
                    'rate_limit': 10.0,      # 10 requests/second to Ollama
                    'rate_capacity': 20.0,   # Burst up to 20
                    'worker_count': 3,       # 3 parallel workers
                }
            )
            event_bus.register_component('kingdom_brain', kingdom_brain)
            event_bus.register_component('kingdom_ai_brain', kingdom_brain)

            # Attach NemoClaw bridge if it was registered at startup
            try:
                from core.component_registry import get_component
                _nc_bridge = get_component("nemoclaw_bridge")
                if _nc_bridge is not None:
                    kingdom_brain.attach_nemoclaw(_nc_bridge)
                    logger.info("   🐾 NemoClaw attached to Kingdom AI Brain")
            except Exception as _nc_err:
                logger.debug("   NemoClaw attach skipped: %s", _nc_err)

            logger.info("   ✅ Kingdom AI Brain initialized - SOTA 2026 priority queue + circuit breakers + NemoClaw")
        except Exception as e:
            logger.warning(f"   ⚠️ Kingdom AI Brain not available: {e}")
        
        # Initialize AI Command Router for device/system control
        from core.ai_command_router import get_command_router
        ai_router = get_command_router(event_bus=event_bus)
        event_bus.register_component('ai_command_router', ai_router)
        logger.info("   ✅ AI Command Router initialized - device/system control ready")
        
        # SOTA 2026: Initialize Communication Capabilities for Comms Tab
        # This handles comms.* events (radio, sonar, video, call) from the Comms Tab
        try:
            from core.communication_capabilities import CommunicationCapabilities
            comms_caps = CommunicationCapabilities(event_bus=event_bus)
            event_bus.register_component('communication_capabilities', comms_caps)
            event_bus.register_component('comms_backend', comms_caps)
            logger.info("   ✅ Communication Capabilities initialized - Comms Tab backend ready")
        except Exception as e:
            logger.warning(f"   ⚠️ Communication Capabilities not available: {e}")
        
        # SOTA 2026: Initialize Host Device Manager for Devices Tab
        # This handles device.* events (scan, connect, disconnect, monitor) from the Devices Tab
        # Provides unified device detection: USB, Serial, Bluetooth, Audio, Webcam, VR
        try:
            from core.host_device_manager import HostDeviceManager, get_host_device_manager
            host_device_manager = get_host_device_manager(event_bus)
            event_bus.register_component('host_device_manager', host_device_manager)
            event_bus.register_component('device_manager', host_device_manager)  # Alias for compatibility
            logger.info("   ✅ Host Device Manager initialized - Devices Tab backend ready")
        except Exception as e:
            logger.warning(f"   ⚠️ Host Device Manager not available: {e}")
        
        # Initialize Host Bridge for webcam/mic integration
        try:
            try:
                from core.host_device_manager import WindowsHostBridge
                host_bridge = WindowsHostBridge()
            except ImportError:
                from core.windows_host_bridge import WindowsHostBridge
                host_bridge = WindowsHostBridge()
            event_bus.register_component('host_bridge', host_bridge)
            
            # Connect webcam to vision stream
            async def handle_vision_request(data):
                try:
                    webcams = host_bridge.get_windows_webcams()
                    if webcams:
                        # Route to vision stream
                        event_bus.publish('vision.stream.frame', {
                            'source': 'webcam',
                            'devices': webcams,
                            'timestamp': datetime.now().isoformat()
                        })
                        # Route to Ollama brain for understanding
                        event_bus.publish('brain.request', {
                            'prompt': f"Vision input from webcam: {webcams[0]['name']}",
                            'domain': 'vision',
                            'images': webcams
                        })
                except Exception as e:
                    logger.error(f"Error handling vision request: {e}")
            
            # Connect mic to voice input
            async def handle_voice_input(data):
                try:
                    mics = host_bridge.get_windows_audio_devices()
                    input_mics = [m for m in mics if m.get('is_input')]
                    if input_mics:
                        # Route to voice recognition
                        event_bus.publish('voice.recognition.start', {
                            'source': 'microphone',
                            'device': input_mics[0],
                            'timestamp': datetime.now().isoformat()
                        })
                except Exception as e:
                    logger.error(f"Error handling voice input: {e}")
            
            event_bus.subscribe('vision.request', handle_vision_request)
            event_bus.subscribe('voice.input.request', handle_voice_input)
            
            # SOTA 2026 FIX: Do NOT duplicate voice->brain routing here.
            # AlwaysOnVoice already publishes ai.request which ThothAI handles.
            # This duplicate bridge was causing 2x Ollama calls per voice input.
            
            logger.info("   ✅ Host Bridge initialized - webcam/mic connected to Ollama")
        except Exception as e:
            logger.warning(f"   ⚠️ Host Bridge not available: {e}")
        
        # SOTA 2026: Initialize VisionStreamComponent for MJPEG webcam streaming
        # This reads from brio_mjpeg_server (http://host:8090/brio.mjpg) and publishes vision.stream.frame
        try:
            from components.vision_stream import VisionStreamComponent
            vision_stream = VisionStreamComponent(event_bus=event_bus)
            vision_stream.subscribe_to_events()
            event_bus.register_component('vision_stream', vision_stream)
            event_bus.register_component('vision_stream_component', vision_stream)
            logger.info("   ✅ VisionStreamComponent initialized - MJPEG webcam streaming ready")
            
            # Auto-start vision stream if MJPEG server URL is available
            try:
                import socket

                def _is_wsl_env():
                    try:
                        if os.path.exists('/proc/version'):
                            with open('/proc/version', 'r') as _f:
                                return 'microsoft' in _f.read().lower()
                    except Exception:
                        pass
                    return False

                host_ip = "localhost"
                if _is_wsl_env():
                    try:
                        with open('/etc/resolv.conf', 'r') as rf:
                            for line in rf:
                                if line.strip().startswith('nameserver'):
                                    _ns = line.strip().split()[1]
                                    if not _ns.startswith('127.'):
                                        host_ip = _ns
                                    break
                    except Exception:
                        pass
                
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    if sock.connect_ex((host_ip, 8090)) == 0:
                        mjpeg_url = f"http://{host_ip}:8090/brio.mjpg"
                        event_bus.publish('vision.stream.start', {'url': mjpeg_url})
                        logger.info(f"   ✅ Auto-started vision stream from {mjpeg_url}")
            except Exception as e:
                logger.debug(f"Vision stream auto-start skipped: {e}")
                
        except Exception as e:
            logger.warning(f"   ⚠️ VisionStreamComponent not available: {e}")
        
        # SOTA 2026: Forward vision frames to VR system
        # This allows VR headsets to receive webcam data for passthrough/AR
        def forward_vision_to_vr(data):
            try:
                frame = data.get('frame')
                if frame is not None:
                    # Forward to VR devices (Meta glasses, Quest 3, etc.)
                    event_bus.publish('vr.vision.frame', {
                        'frame': frame,
                        'timestamp': data.get('timestamp'),
                        'source': 'webcam',
                    })
            except Exception as e:
                logger.debug(f"Vision to VR forward error: {e}")
        
        event_bus.subscribe('vision.stream.frame', forward_vision_to_vr)
        logger.info("   ✅ Vision stream forwarding to VR system enabled")
        
        # Wire creation systems to display output in GUI/VR
        def handle_creation_output(data):
            try:
                output_type = data.get('type', 'image')
                output_data = data.get('data')
                if output_data:
                    # Display in GUI
                    event_bus.publish('visual.display', {
                        'type': output_type,
                        'data': output_data,
                        'source': 'creation_system'
                    })
                    # Display in VR if active
                    event_bus.publish('vr.display', {
                        'type': output_type,
                        'data': output_data,
                        'source': 'creation_system'
                    })
                    logger.debug(f"Creation output routed to GUI/VR: {output_type}")
            except Exception as e:
                logger.error(f"Error handling creation output: {e}")
        
        event_bus.subscribe('creation.output', handle_creation_output)
        event_bus.subscribe('visual.generated', handle_creation_output)
        event_bus.subscribe('image.generated', handle_creation_output)
        logger.info("   ✅ Creation systems wired to GUI/VR displays")
        
        # SOTA 2026: Register UnifiedCreativeEngine early so Creation Studio + Orchestrator share singleton
        try:
            from core.unified_creative_engine import get_unified_creative_engine
            uce = get_unified_creative_engine(event_bus=event_bus)
            event_bus.register_component('unified_creative_engine', uce)
            logger.info("   ✅ UnifiedCreativeEngine registered (shared by Creation Studio + Orchestrator)")
        except Exception as e:
            logger.warning(f"   ⚠️ UnifiedCreativeEngine registration skipped: {e}")
        
    orchestrator.add_step(
        "AI Brain (Ollama)", LoadingPhase.AI_BRAIN,
        load_ai_brain, weight=15, timeout=120
    )
    
    # Phase 8: Voice System (XTTS) - heavy, loads last before GUI
    async def load_voice():
        try:
            from core.voice_manager import VoiceManager
            voice = VoiceManager(event_bus=event_bus)
            if hasattr(voice, 'initialize'):
                await voice.initialize()
            event_bus.register_component('voice_manager', voice)
            logger.info("   Voice system loaded successfully")
        except Exception as voice_err:
            # Handle torchaudio symbol errors gracefully - voice still works without it
            if "undefined symbol" in str(voice_err) and "torchaudio" in str(voice_err):
                logger.warning(f"⚠️ torchaudio unavailable (ABI incompatibility) - using fallback TTS/STT")
                # Voice system can still work with pyttsx3 and speech_recognition
                try:
                    from core.voice_manager import VoiceManager
                    voice = VoiceManager(event_bus=event_bus)
                    # Initialize without torchaudio-dependent features
                    if hasattr(voice, 'initialize'):
                        await voice.initialize()
                    event_bus.register_component('voice_manager', voice)
                    logger.info("✅ Voice system loaded with fallback engines (pyttsx3 + speech_recognition)")
                except Exception as fallback_err:
                    logger.error(f"❌ Voice system completely failed: {fallback_err}")
                    event_bus.register_component('voice_manager', None)
            else:
                logger.error(f"❌ Voice system failed: {voice_err}")
                event_bus.register_component('voice_manager', None)
        
    orchestrator.add_step(
        "Voice System (XTTS)", LoadingPhase.VOICE,
        load_voice, weight=20, timeout=180  # XTTS takes 2-3 minutes
    )
    
    # Phase 9: Wallet System (derives addresses - slow)
    async def load_wallet():
        from core.wallet_system import WalletSystem
        wallet = WalletSystem(event_bus=event_bus)
        if hasattr(wallet, 'initialize'):
            await wallet.initialize()
        event_bus.register_component('wallet_system', wallet)
        
    orchestrator.add_step(
        "Wallet System", LoadingPhase.WALLET,
        load_wallet, weight=15, timeout=600, critical=False  # Can take 10 mins
    )
    
    # Phase 10: API Key Manager
    async def load_api_keys():
        from core.api_key_manager import APIKeyManager
        api_mgr = APIKeyManager(event_bus=event_bus)
        if hasattr(api_mgr, 'initialize'):
            await api_mgr.initialize()
        event_bus.register_component('api_key_manager', api_mgr)
        
    orchestrator.add_step(
        "API Key Manager", LoadingPhase.API_KEYS,
        load_api_keys, weight=5, timeout=30
    )
    
    # Phase 11: VR System
    async def load_vr():
        from core.vr_system import VRSystem
        vr = VRSystem(event_bus=event_bus)
        if hasattr(vr, 'initialize'):
            await vr.initialize()
        event_bus.register_component('vr_system', vr)
        
    orchestrator.add_step(
        "VR System", LoadingPhase.VR,
        load_vr, weight=3, timeout=30, critical=False
    )
    
    return orchestrator
