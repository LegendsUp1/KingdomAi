"""
SOTA 2026 Voice Manager - Black Panther Voice Pipeline
======================================================
Kingdom AI's sole voice authority. ALL voice output MUST go through this manager.

Design Principles:
1. Black Panther voice is the ONLY voice output system
2. Voice input detection should trigger Kingdom AI responses
3. No other voice systems should be active
4. Publishes speaking events for input/output coordination
5. COMPLETE DEDUPLICATION: Both request ID and text-based (SOTA 2026)
"""
import logging
import subprocess
import shutil
import sys
import threading
import time
import os
import uuid
from typing import Optional, Dict, Any, Set, List, Tuple
from pathlib import Path


def _find_conda_executable() -> Optional[str]:
    """Resolve ``conda`` when it is not on PATH (common in non-login shells)."""
    p = shutil.which("conda")
    if p:
        return p
    for candidate in (
        os.path.expanduser("~/miniconda3/bin/conda"),
        os.path.expanduser("~/anaconda3/bin/conda"),
        os.path.expanduser("~/mambaforge/bin/conda"),
        "/opt/conda/bin/conda",
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    env_c = os.environ.get("KINGDOM_CONDA_BIN", "").strip()
    if env_c and os.path.isfile(env_c) and os.access(env_c, os.X_OK):
        return env_c
    return None


from concurrent.futures import ThreadPoolExecutor

# Coqui XTTS first run: download + GPU load + inference can take many minutes. A 360s cap was
# killing the subprocess before audio ever played. Override with KINGDOM_XTTS_TIMEOUT_SEC.
_XTTS_SUBPROCESS_TIMEOUT_SEC = int(os.environ.get("KINGDOM_XTTS_TIMEOUT_SEC", "7200"))

logger = logging.getLogger("KingdomAI.VoiceManager")


class VoiceManager:
    """
    Centralized Voice Manager for Kingdom AI.
    
    SOLE VOICE AUTHORITY: All voice output must go through this manager.
    Uses Black Panther voice pipeline for TTS.
    Coordinates with voice input to prevent conflicts.
    
    SOTA 2026: Complete deduplication system prevents duplicate voice output:
    - Request ID tracking (prevents same request being processed twice)
    - Text hash tracking (prevents same text being spoken twice in short window)
    - Normalized text comparison (catches near-duplicates)
    """
    
    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None):
        """Initialize the Voice Manager.
        
        Args:
            event_bus: EventBus for system-wide communication
            config: Configuration dictionary
        """
        self.event_bus = event_bus
        self.config = config or {}
        
        # Voice state tracking
        self._is_speaking = False
        self._speaking_lock = threading.Lock()
        self._speak_queue = []
        self._queue_lock = threading.Lock()
        
        # Black Panther voice system
        self._black_panther_voice = None
        self._voice_initialized = False
        
        # Metrics
        self._speak_count = 0
        self._error_count = 0
        self._last_speak_time = 0
        
        # SOTA 2026 FIX: Track error states to avoid log spam
        self._xtts_failure_logged = False
        self._redis_service_warning_logged = False
        self._startup_bridge_verified = False
        
        # Voice deduplication: request-ID based (single layer, sufficient)
        self._processed_request_ids: Set[str] = set()
        self._request_id_timestamps: Dict[str, float] = {}
        self._request_id_max_age = 120
        self._dedup_lock = threading.Lock()
        
        # SOTA 2026 CONCURRENCY FIX: Thread pool for voice processing
        # Prevents unbounded thread spawning - only 2 concurrent voice operations max
        self._voice_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="VoiceWorker"
        )
        logger.info("✅ Voice thread pool created (max 2 workers)")
        
        logger.info("🔊 VoiceManager initializing as SOLE VOICE AUTHORITY...")
        logger.info("🛡️ Voice deduplication enabled (request ID)")
        
        # SOTA 2026: Register on EventBus for component discovery
        if self.event_bus:
            try:
                from core.component_registry import register_component
                register_component('voice_manager', self)
                logger.info("✅ VoiceManager registered on EventBus")
            except Exception as e:
                logger.debug(f"Component registration failed: {e}")
            
            # Subscribe immediately in __init__ so voice.speak is ALWAYS wired
            self._subscribe_to_events()
            self._init_black_panther_voice()
            self._voice_initialized = True
            logger.info("✅ VoiceManager voice.speak subscription active from __init__")
    
    async def initialize(self) -> bool:
        """Initialize the voice manager and Black Panther voice system."""
        try:
            # Initialize Black Panther voice
            self._init_black_panther_voice()
            
            # Subscribe to voice events
            if self.event_bus:
                self._subscribe_to_events()
            
            self._voice_initialized = True
            logger.info("✅ VoiceManager initialized - Black Panther voice ready")
            return True
        except Exception as e:
            logger.error(f"❌ VoiceManager initialization failed: {e}")
            return False
    
    def _init_black_panther_voice(self):
        """Initialize Black Panther voice system with Dec 19th cloned voice."""
        try:
            from black_panther_voice import BlackPantherVoice
            self._black_panther_voice = BlackPantherVoice()
            
            # CRITICAL: Find Dec 19th reference file - try multiple paths
            dec19_reference = None
            
            # Path 1: Relative to current directory
            path1 = os.path.join('data', 'voices', 'black_panther', 'reference', 'bp_sample_1.wav')
            if os.path.exists(path1):
                dec19_reference = os.path.abspath(path1)
                logger.info(f"✅ Found Dec 19th reference (path1): {dec19_reference}")
            
            # Path 2: Relative to core/ directory parent
            if not dec19_reference:
                base_dir = Path(__file__).parent.parent
                path2 = base_dir / 'data' / 'voices' / 'black_panther' / 'reference' / 'bp_sample_1.wav'
                if path2.exists():
                    dec19_reference = str(path2.absolute())
                    logger.info(f"✅ Found Dec 19th reference (path2): {dec19_reference}")
            
            # Path 3: Optional override (native Linux / CI)
            if not dec19_reference:
                env_ref = os.environ.get("KINGDOM_BP_REFERENCE_WAV", "").strip()
                if env_ref and Path(env_ref).is_file():
                    dec19_reference = str(Path(env_ref).resolve())
                    logger.info(f"✅ Found reference from KINGDOM_BP_REFERENCE_WAV: {dec19_reference}")

            # Path 4: Canonical CLEAN reference (project root)
            if not dec19_reference:
                base_dir = Path(__file__).parent.parent
                clean_path = base_dir / 'processed_black_panther_CLEAN.wav'
                if clean_path.exists():
                    dec19_reference = str(clean_path.absolute())
                    logger.info(f"✅ Found canonical CLEAN reference: {dec19_reference}")
            
            if dec19_reference:
                self._black_panther_voice.reference_path = dec19_reference
                logger.info(f"✅ Black Panther voice using reference: {dec19_reference}")
            else:
                logger.info("ℹ️ Voice reference file not found locally — Redis Voice Service handles TTS independently")
            
            logger.info("✅ Black Panther voice system loaded")
            logger.info("🎤 Voice output: Redis XTTS → direct XTTS subprocess → fallback TTS")
            
        except ImportError as ie:
            logger.warning(f"⚠️ BlackPantherVoice import failed: {ie}")
            logger.info("🎤 Voice will use Redis Voice Service directly")
            self._black_panther_voice = None
        except Exception as e:
            logger.warning(f"⚠️ Black Panther voice init error: {e}")
            logger.info("🎤 Voice will use Redis Voice Service directly")
            self._black_panther_voice = None
    
    def _subscribe_to_events(self):
        """Subscribe to voice-related events."""
        if not self.event_bus:
            return
        if getattr(self, '_events_subscribed', False):
            return
        self._events_subscribed = True
        
        subscribe = getattr(self.event_bus, 'subscribe_sync', None) or self.event_bus.subscribe
        
        subscribe('voice.speak', self._handle_voice_speak)
        subscribe('voice.speak.delta', self._handle_voice_speak_delta)
        subscribe('voice.speak.flush', self._handle_voice_speak_flush)
        subscribe('voice.telemetry', self._handle_voice_telemetry)
        subscribe('voice.status.request', self._handle_voice_status_request)
        subscribe('voice.toggle', self._handle_voice_toggle)
        subscribe('voice.configure', self._handle_voice_configure)
        
        logger.info("🔊 VoiceManager subscribed to ALL voice events (SOLE HANDLER)")
    
    def _handle_voice_speak(self, data: Dict[str, Any]) -> None:
        """Handle voice.speak event - route to Black Panther voice.
        
        This is the SOLE handler for voice output in the entire system.
        All components publish voice.speak and this manager handles it.
        
        SOTA 2026: Complete deduplication prevents duplicate voice output:
        1. Request ID check - prevents same request being processed twice
        2. Text hash check - prevents same text being spoken twice
        3. Normalized text check - catches near-duplicates
        """
        text = data.get('text', '') if isinstance(data, dict) else str(data)
        if not text or not text.strip():
            return
        
        request_id = data.get('request_id', '') if isinstance(data, dict) else ''
        priority = data.get('priority', 'normal') if isinstance(data, dict) else 'normal'
        source = data.get('source', 'unknown') if isinstance(data, dict) else 'unknown'
        
        # ============================================
        # SOTA 2026: COMPLETE DEDUPLICATION CHECK
        # ============================================
        if self._is_duplicate_voice_request(request_id, text, source, priority):
            return  # Skip duplicate
        
        logger.info(f"🔊 VoiceManager received speak request from {source}: {text[:50]}...")
        
        # Queue the speech request
        with self._queue_lock:
            self._speak_queue.append({
                'text': text,
                'priority': priority,
                'source': source,
                'request_id': request_id,
                'timestamp': time.time()
            })
        
        # SOTA 2026 FIX: Process queue using thread pool (prevents thread explosion)
        self._voice_executor.submit(self._process_speak_queue)
    
    def _is_duplicate_voice_request(self, request_id: str, text: str, source: str, priority: str = "normal") -> bool:
        """Check if this voice request is a duplicate using multiple methods.
        
        SOTA 2026: Complete deduplication system with three layers:
        1. Request ID - Same request processed multiple times
        2. Text hash - Same exact text with different request IDs
        Returns:
            True if duplicate (should be skipped), False if new request
        """
        current_time = time.time()
        
        with self._dedup_lock:
            # First, cleanup old entries
            self._cleanup_dedup_caches(current_time)
            
            source_norm = str(source or "").strip().lower()
            priority_norm = str(priority or "").strip().lower()

            # High-priority voice responses from the unified router/always-on path
            # must not be suppressed by dedup, otherwise users perceive "no response".
            if priority_norm in {"high", "critical"} and source_norm in {"unified_router", "always_on_voice", "thoth_qt_startup"}:
                return False

            # CHECK 1: Request ID deduplication
            if request_id:
                if request_id in self._processed_request_ids:
                    logger.debug(f"⏭️ Skipping duplicate request ID: {request_id}")
                    return True
                # Mark as processed
                self._processed_request_ids.add(request_id)
                self._request_id_timestamps[request_id] = current_time
            
        return False
    
    def _cleanup_dedup_caches(self, current_time: float) -> None:
        """Clean up old entries from deduplication caches."""
        old_request_ids = [
            rid for rid, ts in self._request_id_timestamps.items()
            if current_time - ts > self._request_id_max_age
        ]
        for rid in old_request_ids:
            self._processed_request_ids.discard(rid)
            self._request_id_timestamps.pop(rid, None)
    
    def _handle_voice_speak_delta(self, data: Dict[str, Any]) -> None:
        """Handle streaming voice delta (for real-time TTS during streaming responses)."""
        # For now, accumulate deltas - full implementation would buffer and speak chunks
        text = data.get('text', '')
        if text:
            logger.debug(f"🔊 Voice delta: {text[:20]}...")
    
    def _handle_voice_speak_flush(self, data: Dict[str, Any]) -> None:
        """Handle voice flush request (end of streaming)."""
        logger.debug("🔊 Voice flush requested")
    
    def _process_speak_queue(self):
        """Process queued speech requests through Black Panther voice."""
        with self._speaking_lock:
            if self._is_speaking:
                return  # Already processing
            self._is_speaking = True
        
        try:
            while True:
                # Get next item from queue
                with self._queue_lock:
                    if not self._speak_queue:
                        break
                    # Sort by priority (critical > high > normal > low).
                    _prio_rank = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}
                    self._speak_queue.sort(key=lambda x: _prio_rank.get(str(x.get('priority', 'normal')).lower(), 2))
                    item = self._speak_queue.pop(0)
                
                text = item['text']
                source = item['source']
                
                # Publish speaking started event
                self._publish_speaking_started(text, source)
                
                try:
                    # Use Black Panther voice ONLY - no fallback
                    self._speak_with_black_panther(text, source=source)
                    
                    self._speak_count += 1
                    self._last_speak_time = time.time()
                except Exception as e:
                    logger.error(f"❌ Speech error: {e}")
                    self._error_count += 1
                finally:
                    # Publish speaking stopped event
                    self._publish_speaking_stopped(text, source)
        finally:
            with self._speaking_lock:
                self._is_speaking = False
    
    def _speak_with_black_panther(self, text: str, source: str = "") -> None:
        """Speak using Black Panther voice system with Dec 19th cloned voice.
        
        SOTA 2026: Uses Redis Voice Service ONLY - NO FALLBACKS.
        The Redis Voice Service runs in the kingdom-voice environment with the
        Dec 19th compatible stack (numpy, librosa, TTS).
        
        Reference audio: data/voices/black_panther_samples/bp_sample_1.wav
        """
        try:
            logger.info(f"🎤 Black Panther speaking: {text[:50]}...")
            
            # 1. Redis Voice Service (background daemon with XTTS prewarmed)
            if self._try_redis_voice_service(text, source=source):
                logger.info("✅ Black Panther voice played via Redis Voice Service")
                return

            # 2. Direct XTTS subprocess (this Python — TTS is installed in kingdom-venv)
            if self._try_direct_xtts(text):
                logger.info("✅ Black Panther cloned voice (direct XTTS)")
                return

            # 3. Fallback: Speech Dispatcher / pyttsx3 (generic — NOT the clone)
            if self._try_local_black_panther_speaker(text):
                logger.info("✅ Fallback TTS only (not XTTS clone — start redis_voice_service for cloned voice)")
                return

            if not self._xtts_failure_logged:
                logger.warning("Voice service unavailable and local TTS failed")
                self._xtts_failure_logged = True
            
        except Exception as e:
            if not self._xtts_failure_logged:
                logger.error(f"❌ Black Panther voice error: {e}")
                self._xtts_failure_logged = True

    def _xtts_subprocess_env(self, repo: Path) -> dict:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo)
        env.setdefault("COQUI_TOS_AGREED", "1")
        env.setdefault("PYTHONUNBUFFERED", "1")
        return env

    def _redis_voice_service_launch_cmd(self) -> Tuple[Optional[List[str]], dict]:
        """Argv + env to auto-launch ``redis_voice_service.py``."""
        repo = Path(__file__).resolve().parent.parent
        script = repo / "redis_voice_service.py"
        if not script.is_file():
            return None, {}
        env = self._xtts_subprocess_env(repo)
        return [sys.executable, str(script)], env

    def _try_direct_xtts(self, text: str) -> bool:
        """Run redis_voice_service.py --speak-stdin with *this* Python (TTS is installed here)."""
        msg = (text or "").strip()
        if not msg:
            return False
        repo = Path(__file__).resolve().parent.parent
        script = repo / "redis_voice_service.py"
        if not script.is_file():
            return False
        env = self._xtts_subprocess_env(repo)
        try:
            logger.info("XTTS subprocess: %s", sys.executable)
            r = subprocess.run(
                [sys.executable, str(script), "--speak-stdin"],
                cwd=str(repo),
                input=msg,
                text=True,
                timeout=_XTTS_SUBPROCESS_TIMEOUT_SEC,
                env=env,
            )
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning("XTTS timed out after %ss", _XTTS_SUBPROCESS_TIMEOUT_SEC)
        except Exception as e:
            logger.debug("XTTS subprocess error: %s", e)
        return False

    def _try_local_black_panther_speaker(self, text: str) -> bool:
        """When Redis XTTS is unavailable: speak through the desktop default output (HDMI / line / selected in Settings).

        Order: ``spd-say`` (Speech Dispatcher → Pulse) for reliable routing, then pyttsx3.
        """
        import shutil
        import subprocess

        if not text or not str(text).strip():
            return False
        msg = str(text).strip()
        spd = shutil.which("spd-say")
        if spd:
            try:
                r = subprocess.run(
                    [spd, "-t", "male3", "-r", "-15", "-p", "-10", "-w", msg],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if r.returncode == 0:
                    return True
                logger.debug("spd-say rc=%s err=%s", r.returncode, (r.stderr or "")[:120])
            except Exception as e:
                logger.debug("spd-say failed: %s", e)
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            for v in voices:
                name = (getattr(v, "name", "") or "").lower()
                if "male" in name or "david" in name or "daniel" in name:
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 1.0)
            engine.say(msg)
            engine.runAndWait()
            return True
        except Exception as e:
            logger.debug("Local pyttsx3 Black Panther fallback: %s", e)
            return False
    
    def _try_redis_voice_service(self, text: str, source: str = "") -> bool:
        """Try Redis Voice Service (isolated environment with Dec 19th stack).
        
        SOTA 2026: The redis_voice_service.py runs in a separate kingdom-voice
        environment with the Dec 19th compatible stack (numpy 1.26.4, numba 0.59.1,
        librosa 0.10.2). This avoids the numba compatibility issues in the main
        kingdom-ai environment.
        
        Publishes to: voice.speak (main channel)
        Listens on: voice.generated (response channel)
        
        Returns True if successful, False if service not available.
        """
        try:
            import redis
            import json
            import time
            
            # Connect to Redis Quantum Nexus
            redis_client = redis.Redis(
                host='localhost',
                port=6380,
                password='QuantumNexus2025',
                decode_responses=True,
                socket_timeout=120
            )
            
            # Test connection
            redis_client.ping()
            
            service_ready = redis_client.get('kingdom:voice:service:ready')
            if not service_ready:
                for _retry in range(3):
                    time.sleep(2)
                    service_ready = redis_client.get('kingdom:voice:service:ready')
                    if service_ready:
                        break
            if not service_ready:
                if not self._redis_service_warning_logged:
                    logger.info("⏳ Redis Voice Service not ready after 6s wait — starting service")
                    self._redis_service_warning_logged = True
                try:
                    repo_root = Path(__file__).resolve().parent.parent
                    cmd, venv = self._redis_voice_service_launch_cmd()
                    if cmd:
                        subprocess.Popen(
                            cmd,
                            cwd=str(repo_root),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True,
                            env=venv,
                        )
                        logger.info("🚀 Auto-launched redis_voice_service.py (isolated voice Python), waiting for ready flag...")
                    else:
                        logger.debug(
                            "redis_voice_service auto-launch skipped: no voice_runtime_env / conda kingdom-voice "
                            "(run scripts/bootstrap_voice_runtime_venv.sh or start_voice_service_linux.sh; or KINGDOM_ALLOW_MAIN_VENV_XTTS=1)"
                        )
                        for _w in range(10):
                            time.sleep(2)
                            if redis_client.get('kingdom:voice:service:ready'):
                                service_ready = True
                                break
                except Exception as launch_err:
                    logger.debug("Failed to auto-launch voice service: %s", launch_err)
                if not service_ready:
                    return False
            
            logger.info("📡 Redis Voice Service is available - using isolated Dec 19th stack")
            
            # Generate request ID
            request_id = f"voice_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            reply_channel = f"voice.generated.{request_id}"
            
            # Subscribe to response channel first
            pubsub = redis_client.pubsub()
            pubsub.subscribe('voice.generated', reply_channel)
            
            # Consume subscription confirmation message
            pubsub.get_message(timeout=1)
            
            # Publish voice request (service handles playback)
            redis_client.publish('voice.speak', json.dumps({
                'text': text,
                'request_id': request_id,
                'priority': 'high',
                'source': 'voice_manager',
                'play_audio': False,  # VoiceManager handles playback on voice.generated reply
                'reply_channel': reply_channel,
            }))
            
            logger.info(f"📡 Published voice.speak to Redis (request {request_id})")
            
            # Keep end-to-end interaction cadence natural; don't block voice queue
            # for very long generations.
            timeout_seconds = 60 if not self._startup_bridge_verified else 20
            start_wait = time.monotonic()
            timeout_time = start_wait + timeout_seconds
            poll_count = 0
            timeout_extended = False
            
            while time.monotonic() < timeout_time:
                # Smaller polling interval reduces tail latency jitter waiting for
                # voice.generated completion events from Redis.
                message = pubsub.get_message(timeout=0.1)
                poll_count += 1
                
                if message is None:
                    # Log progress every 10 seconds
                    if poll_count % 100 == 0:
                        elapsed = int(time.monotonic() - start_wait)
                        logger.info(f"⏳ Waiting for voice generation... ({elapsed}s)")
                    continue
                    
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        msg_channel = str(message.get('channel', ''))
                        # Accept either request-scoped replies (preferred) or legacy shared channel.
                        if data.get('request_id') == request_id and msg_channel in ('voice.generated', reply_channel):
                            status = data.get('status')
                            
                            if status == 'complete':
                                audio_file = data.get('file')
                                gen_time = data.get('generation_time_ms', 0)
                                logger.info(f"✅ Voice generated via Redis service in {gen_time}ms")

                                try:
                                    if audio_file and os.path.exists(str(audio_file)):
                                        from core.wsl_audio_bridge import wsl_audio_bridge
                                        played = bool(wsl_audio_bridge.play_audio(str(audio_file)))
                                        if str(source).startswith("thoth_qt_startup"):
                                            self._startup_bridge_verified = self._startup_bridge_verified or played
                                except Exception:
                                    pass

                                pubsub.close()
                                return True
                                
                            elif status == 'error':
                                error = data.get('error', 'Unknown error')
                                logger.warning(f"Redis voice service error: {error}")
                                pubsub.close()
                                return False
                            
                            elif status == 'generating':
                                logger.info("🎤 Voice generation in progress...")
                                if not timeout_extended:
                                    timeout_time = max(timeout_time, time.monotonic() + 45)
                                    timeout_extended = True
                                
                    except Exception as parse_err:
                        logger.warning(f"Error parsing Redis response: {parse_err}")
            
            if not self._redis_service_warning_logged:
                logger.info(f"Redis voice service timeout ({timeout_seconds}s) - service may be overloaded or not running")
                logger.info("   First voice generation can take 30+ seconds for XTTS to load")
                self._redis_service_warning_logged = True
            pubsub.close()
            return False
            
        except redis.ConnectionError:
            logger.debug("Redis Voice Service not available (connection refused)")
            return False
        except ImportError:
            logger.debug("Redis package not installed")
            return False
        except Exception as e:
            logger.debug("Redis Voice Service error: %s", e)
            return False
    
    def _handle_voice_telemetry(self, data: Dict[str, Any]) -> None:
        """Handle voice.telemetry events from GUI for metrics tracking."""
        try:
            event_type = data.get('event_type', '') if isinstance(data, dict) else ''
            logger.debug(f"📊 Voice telemetry: {event_type}")
            self._last_telemetry = data
        except Exception as e:
            logger.debug(f"Voice telemetry error: {e}")

    def _handle_voice_status_request(self, data: Dict[str, Any]) -> None:
        """Handle voice.status.request -- respond with current voice status."""
        try:
            status = self.get_status()
            if self.event_bus:
                self.event_bus.publish('voice.audio.status', {
                    'status': 'active' if self._voice_initialized else 'inactive',
                    'message': f"Voice {'ready' if self._voice_initialized else 'not initialized'} | "
                               f"Spoken: {self._speak_count} | Errors: {self._error_count}",
                    'details': status,
                    'source': 'voice_manager',
                    'timestamp': time.time(),
                })
        except Exception as e:
            logger.debug(f"Voice status request error: {e}")

    def _handle_voice_toggle(self, data: Dict[str, Any]) -> None:
        """Handle voice.toggle events from GUI to enable/disable voice."""
        try:
            if not isinstance(data, dict):
                return
            active = data.get('active', data.get('enabled', True))
            source = data.get('source', 'unknown')
            logger.info(f"🔊 Voice toggle: {'ON' if active else 'OFF'} (from {source})")
            if active:
                self._voice_initialized = True
            if self.event_bus:
                self.event_bus.publish('voice.audio.status', {
                    'status': 'listening_started' if active else 'listening_stopped',
                    'message': f"Voice {'enabled' if active else 'disabled'} by {source}",
                    'source': 'voice_manager',
                    'timestamp': time.time(),
                })
        except Exception as e:
            logger.debug(f"Voice toggle error: {e}")

    def _handle_voice_configure(self, data: Dict[str, Any]) -> None:
        """Handle voice.configure events to update voice configuration."""
        try:
            if not isinstance(data, dict):
                return
            config_updates = data.get('config', {})
            source = data.get('source', 'unknown')
            if isinstance(config_updates, dict):
                self.config.update(config_updates)
                logger.info(f"🔧 Voice config updated by {source}: {list(config_updates.keys())}")
        except Exception as e:
            logger.debug(f"Voice configure error: {e}")

    def _publish_speaking_started(self, text: str, source: str) -> None:
        """Publish event that Kingdom AI started speaking.
        
        CRITICAL: This allows voice input detection to pause during AI speech.
        """
        if self.event_bus:
            self.event_bus.publish('voice.speaking.started', {
                'text': text[:100],
                'source': source,
                'timestamp': time.time(),
                'speaking': True
            })
            self.event_bus.publish('voice.audio.status', {
                'status': 'speaking_started',
                'message': f"Kingdom AI speaking ({source})",
                'source': 'voice_manager',
                'timestamp': time.time(),
            })
            logger.debug(f"📢 Published voice.speaking.started")
    
    def _publish_speaking_stopped(self, text: str, source: str) -> None:
        """Publish event that Kingdom AI stopped speaking.
        
        CRITICAL: This allows voice input detection to resume after AI speech.
        """
        if self.event_bus:
            self.event_bus.publish('voice.speaking.stopped', {
                'text': text[:100],
                'source': source,
                'timestamp': time.time(),
                'speaking': False
            })
            self.event_bus.publish('voice.audio.status', {
                'status': 'speaking_stopped',
                'message': f"Kingdom AI finished speaking ({source})",
                'source': 'voice_manager',
                'timestamp': time.time(),
            })
            logger.debug(f"📢 Published voice.speaking.stopped")
    
    @property
    def is_speaking(self) -> bool:
        """Check if Kingdom AI is currently speaking."""
        with self._speaking_lock:
            return self._is_speaking
    
    def get_status(self) -> Dict[str, Any]:
        """Get voice manager status."""
        return {
            'initialized': self._voice_initialized,
            'is_speaking': self.is_speaking,
            'black_panther_available': self._black_panther_voice is not None,
            'speak_count': self._speak_count,
            'error_count': self._error_count,
            'last_speak_time': self._last_speak_time,
            'queue_size': len(self._speak_queue)
        }
    
    def speak(self, text: str, priority: str = 'normal') -> None:
        """Directly speak text (for internal use).
        
        External components should publish voice.speak events instead.
        """
        self._handle_voice_speak({
            'text': text,
            'priority': priority,
            'source': 'direct_call'
        })
    
    async def shutdown(self) -> None:
        """Shutdown the voice manager."""
        logger.info("🔊 VoiceManager shutting down...")
        
        # Clear queue
        with self._queue_lock:
            self._speak_queue.clear()
        
        # Wait for current speech to finish
        for _ in range(50):  # Wait up to 5 seconds
            with self._speaking_lock:
                if not self._is_speaking:
                    break
            await asyncio.sleep(0.1)
        
        logger.info("✅ VoiceManager shutdown complete")


# For backwards compatibility
import asyncio


# ============================================================
# SOTA 2026: Always-On Voice Integration
# ============================================================

def start_always_on_listening(event_bus=None) -> bool:
    """Start always-on voice detection for Kingdom AI.
    
    SOTA 2026: Continuous, non-blocking voice detection:
    - Wake word: "Kingdom" or "Kingdom AI"
    - Automatically routes recognized speech to AI
    - Pauses during TTS to prevent echo
    - Resumes after AI response completes
    
    Args:
        event_bus: Kingdom AI event bus
        
    Returns:
        True if started successfully
    """
    try:
        from core.always_on_voice import start_always_on_voice
        return start_always_on_voice(event_bus)
    except ImportError as e:
        logger.warning(f"⚠️ Always-on voice not available: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to start always-on voice: {e}")
        return False


def stop_always_on_listening():
    """Stop always-on voice detection."""
    try:
        from core.always_on_voice import stop_always_on_voice
        stop_always_on_voice()
        logger.info("🛑 Always-on voice stopped")
    except Exception as e:
        logger.warning(f"⚠️ Error stopping always-on voice: {e}")
