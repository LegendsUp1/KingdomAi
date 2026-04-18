#!/usr/bin/env python3
"""
🎤 SOTA 2026 Always-On Voice Detection for Kingdom AI
======================================================

This module provides continuous, non-blocking voice detection with wake word
activation. When the user says "Kingdom", the system activates and listens
for the full command, routes it to the AI, and then resumes listening.

Architecture:
- Runs entirely in background threads (never blocks Qt/main thread)
- Uses Vosk for offline speech recognition (privacy-preserving)
- Wake word detection: "Kingdom" or "Kingdom AI"
- Automatic pause during TTS output (no echo)
- Resumes listening after AI response completes

Event Flow:
1. [Always-On Thread] Continuously monitors microphone
2. [Wake Word Detection] Detects "Kingdom" -> publishes voice.wake
3. [Active Listening] Full speech recognition for user query
4. [Publishes] voice.input.recognized -> triggers ai.request
5. [Pauses] During voice.speaking.started event
6. [Resumes] After voice.speaking.stopped event
"""

import os
import sys
import time
import queue
import logging
import threading
import json
import re
from typing import Optional, Callable, Dict, Any, List, Set
from dataclasses import dataclass
from enum import Enum

import numpy as np

# Disable numba JIT before any audio imports
os.environ['NUMBA_DISABLE_JIT'] = '1'

# SOTA 2026: Ensure PulseAudio is accessible in WSL2 via WSLg
# Must be set before any audio library tries to connect
_pulse_socket_path = '/mnt/wslg/PulseServer'
if not os.environ.get('PULSE_SERVER') and os.path.exists(_pulse_socket_path):
    os.environ['PULSE_SERVER'] = f'unix:{_pulse_socket_path}'

logger = logging.getLogger("KingdomAI.AlwaysOnVoice")


def _is_wsl() -> bool:
    try:
        if os.environ.get("WSL_DISTRO_NAME"):
            return True
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False


def _wsl_resolve_exe(name: str) -> str:
    """Resolve Windows executables to full path when running as root in WSL2."""
    import shutil, platform
    if shutil.which(name):
        return name
    if 'microsoft' in platform.uname().release.lower():
        candidates = {
            'powershell.exe': '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
            'cmd.exe': '/mnt/c/Windows/System32/cmd.exe',
        }
        full = candidates.get(name, f'/mnt/c/Windows/System32/{name}')
        if os.path.exists(full):
            return full
    return name


class VoiceState(Enum):
    """States for the always-on voice system."""
    IDLE = "idle"                       # Not initialized
    LISTENING_WAKE = "listening_wake"   # Listening for wake word only
    LISTENING_ACTIVE = "listening_active"  # Actively listening for full command
    PROCESSING = "processing"           # Processing recognized speech
    PAUSED = "paused"                   # Paused (during TTS output)
    STOPPED = "stopped"                 # Stopped completely


def _detect_audio_devices() -> Dict[str, Any]:
    """Auto-detect ALL available audio input devices across all backends.

    Scans PulseAudio (WSL2/Linux native), sounddevice/PortAudio, and PyAudio
    to find every available microphone: Brio webcam mic, VR headsets, USB mics,
    headsets, built-in mics, etc.

    Returns:
        Dict with keys:
            'devices': list of dicts with name, index, backend, priority
            'best': the best device dict (highest priority) or None
            'backend': preferred audio backend ('pulse', 'sounddevice', 'pyaudio')
    """
    devices = []
    best_backend = None

    # --- Priority keywords: higher-priority devices get selected first ---
    vr_keywords = (
        'oculus', 'quest', 'rift', 'meta quest',
        'vive', 'htc vive', 'cosmos',
        'index', 'valve index',
        'wmr', 'mixed reality', 'hololens',
        'psvr', 'pimax', 'reverb', 'varjo',
        'bigscreen', 'nreal', 'xreal',
    )
    usb_mic_keywords = (
        'brio', 'logitech', 'c920', 'c922', 'c930',
        'blue yeti', 'snowball', 'at2020', 'hyperx',
        'rode', 'elgato', 'fifine', 'samson', 'shure',
        'usb mic', 'usb audio', 'webcam',
    )

    def _priority(name: str) -> int:
        """Higher = more preferred.  VR > USB mic > generic > RDP."""
        nl = name.lower()
        if any(kw in nl for kw in vr_keywords):
            return 100
        if any(kw in nl for kw in usb_mic_keywords):
            return 80
        if 'headset' in nl or 'headphone' in nl:
            return 70
        if 'microphone' in nl or 'mic' in nl:
            return 60
        if 'default' in nl:
            return 40
        if 'rdp' in nl or 'monitor' in nl:
            return 20
        return 30

    # ── 1. PulseAudio (works in WSL2 via WSLg) ──────────────────────────
    try:
        import pulsectl
        with pulsectl.Pulse('kingdom-ai-detect') as pulse:
            sources = pulse.source_list()
            for src in sources:
                # Skip monitor sources (they record output, not input)
                if '.monitor' in (src.name or ''):
                    continue
                desc = src.description or src.name or 'Unknown PulseAudio source'
                dev_info = {
                    'name': desc,
                    'pulse_name': src.name,
                    'index': src.index,
                    'backend': 'pulse',
                    'channels': src.channel_count,
                    'sample_rate': src.sample_spec.rate if src.sample_spec else 16000,
                    'priority': _priority(desc),
                }
                devices.append(dev_info)
                logger.info(f"🎤 PulseAudio source: [{src.index}] {desc} (priority={dev_info['priority']})")
            if sources:
                best_backend = best_backend or 'pulse'
    except ImportError:
        logger.debug("pulsectl not installed - skipping PulseAudio device scan")
    except Exception as e:
        logger.debug(f"PulseAudio device scan failed: {e}")

    # ── 2. sounddevice / PortAudio ──────────────────────────────────────
    # Allow sounddevice fallback in WSL when PulseAudio found no devices (e.g. Brio mic)
    if not _is_wsl() or not devices:
        try:
            import sounddevice as _sd
            sd_devices = _sd.query_devices()
            for idx, dev in enumerate(sd_devices):
                if dev.get('max_input_channels', 0) < 1:
                    continue
                dev_info = {
                    'name': dev['name'],
                    'index': idx,
                    'backend': 'sounddevice',
                    'channels': dev['max_input_channels'],
                    'sample_rate': int(dev.get('default_samplerate', 16000)),
                    'priority': _priority(dev['name']),
                }
                devices.append(dev_info)
                logger.info(f"🎤 sounddevice input: [{idx}] {dev['name']} (priority={dev_info['priority']})")
                best_backend = best_backend or 'sounddevice'
        except Exception as e:
            logger.debug(f"sounddevice device scan failed: {e}")

        # ── 3. PyAudio / PortAudio (separate binding) ──────────────────────
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            for idx in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(idx)
                if info.get('maxInputChannels', 0) < 1:
                    continue
                dev_info = {
                    'name': info['name'],
                    'index': idx,
                    'backend': 'pyaudio',
                    'channels': info['maxInputChannels'],
                    'sample_rate': int(info.get('defaultSampleRate', 16000)),
                    'priority': _priority(info['name']),
                }
                devices.append(dev_info)
                logger.info(f"🎤 PyAudio input: [{idx}] {info['name']} (priority={dev_info['priority']})")
                best_backend = best_backend or 'pyaudio'
            pa.terminate()
        except Exception as e:
            logger.debug(f"PyAudio device scan failed: {e}")

    # ── Pick the best device ────────────────────────────────────────────
    best = None
    if devices:
        devices.sort(key=lambda d: d['priority'], reverse=True)
        best = devices[0]
        logger.info(f"🏆 Best audio input: [{best['index']}] {best['name']} via {best['backend']}")

    return {'devices': devices, 'best': best, 'backend': best_backend}


@dataclass
class VoiceConfig:
    """Configuration for always-on voice detection."""
    wake_words: List[str] = None
    sample_rate: int = 16000
    chunk_size: int = 4000  # ~250ms of audio at 16kHz
    silence_timeout: float = 2.0  # Seconds of silence to end active listening
    max_listen_duration: float = 30.0  # Max seconds to listen for a command
    vosk_model_path: str = None  # Path to Vosk model (auto-download if None)
    audio_device: Optional[int] = None  # Explicit input device index (None = auto-detect)
    audio_backend: Optional[str] = None  # 'pulse', 'sounddevice', 'pyaudio' or None for auto
    pulse_source: Optional[str] = None  # PulseAudio source name for recording
    device_rescan_interval: float = 60.0  # Seconds between device hot-plug re-scans (was 10s, too frequent)
    
    def __post_init__(self):
        if self.wake_words is None:
            self.wake_words = ["kingdom", "kingdom ai", "hey kingdom", "ok kingdom"]
        # Attempt device detection but don't treat failure as permanent —
        # PulseAudio may start later. _listen_loop has its own retry logic.
        if self.audio_device is None and self.audio_backend is None:
            try:
                detection = _detect_audio_devices()
                best = detection.get('best')
                if best:
                    self.audio_device = best['index']
                    self.audio_backend = best['backend']
                    if best['backend'] == 'pulse':
                        self.pulse_source = best.get('pulse_name')
                    logger.info(f"🎤 Auto-selected: [{best['index']}] {best['name']} via {best['backend']}")
                else:
                    logger.info(
                        "ℹ️ No audio input devices detected yet — "
                        "_listen_loop will retry with PulseAudio recovery"
                    )
            except Exception as _det_err:
                logger.info("ℹ️ Audio device detection deferred: %s", _det_err)


class AlwaysOnVoice:
    """
    SOTA 2026 Always-On Voice Detection System
    
    Non-blocking, continuous voice detection with wake word activation.
    Uses Vosk for offline, privacy-preserving speech recognition.
    """
    
    def __init__(self, event_bus=None, config: Optional[VoiceConfig] = None):
        """Initialize the always-on voice system.
        
        Args:
            event_bus: Kingdom AI event bus for publishing/subscribing
            config: Voice configuration
        """
        self.event_bus = event_bus
        self.config = config or VoiceConfig()
        
        # State management
        self._state = VoiceState.IDLE
        self._state_lock = threading.Lock()
        
        # Thread management
        self._listen_thread: Optional[threading.Thread] = None
        self._should_run = False
        
        # Audio/Recognition
        self._recognizer = None
        self._audio_queue = queue.Queue()
        self._microphone = None
        
        # Wake word detection
        self._wake_detected_callback: Optional[Callable] = None
        self._command_recognized_callback: Optional[Callable] = None
        
        # Deduplication
        self._last_recognized_time = 0
        self._last_recognized_text = ""
        self._dedup_window = 3.0  # Seconds
        
        # Voice responsiveness tuning:
        # old values (10s/3s) made dialogue feel delayed.
        # keep small guardrails for echo prevention while enabling natural back-and-forth.
        self._last_command_routed_time = 0.0
        self._COMMAND_COOLDOWN = float(os.environ.get("KINGDOM_VOICE_COMMAND_COOLDOWN", "1.5"))
        
        # TTS coordination (pause during AI speech)
        self._is_ai_speaking = False
        self._ai_speaking_lock = threading.Lock()
        self._ai_speaking_stopped_time = 0.0
        self._POST_SPEECH_COOLDOWN = float(os.environ.get("KINGDOM_VOICE_POST_SPEECH_COOLDOWN", "0.6"))
        
        # SOTA 2026: User Identity Engine — voice biometrics + VAD + echo rejection
        self._identity_engine = None
        self._require_owner_verification = True  # Only accept commands from verified owner
        self._identity_grace_period = 120.0  # Seconds to accept commands without enrollment
        self._identity_extended_grace_period = float(os.environ.get("KINGDOM_IDENTITY_EXTENDED_GRACE", "300.0"))
        self._owner_soft_match_threshold = float(os.environ.get("KINGDOM_OWNER_SOFT_MATCH_THRESHOLD", "0.35"))
        self._identity_init_time = time.time()
        # If owner has just been authenticated by BiometricSecurityManager,
        # avoid hard denies from transient face/voice drift.
        self._last_owner_auth_time = 0.0
        self._owner_auth_bypass_window = float(os.environ.get("KINGDOM_OWNER_AUTH_BYPASS_WINDOW", "90.0"))
        self._owner_auth_lock = threading.Lock()
        # SOTA 2026 anti-noise:
        # partial ASR wake checks are noisy around games/movies, so disabled by default.
        self._allow_partial_wake = os.environ.get("KINGDOM_ALLOW_PARTIAL_WAKE", "0").strip().lower() in {"1", "true", "yes"}
        self._owner_face_presence_window = float(os.environ.get("KINGDOM_OWNER_FACE_WINDOW", "20.0"))
        # Latest vision frames (webcam/VR/meta) so voice ai.request can include images.
        self._vision_frame_lock = threading.Lock()
        self._vision_last_frame = None
        self._vision_last_frame_ts = 0.0
        self._vision_vr_last_frame = None
        self._vision_vr_last_frame_ts = 0.0
        self._vision_meta_last_frame = None
        self._vision_meta_last_frame_ts = 0.0
        
        # Device hot-plug tracking
        self._device_changed = False
        self._pulse_proc = None
        
        # SOTA 2026: "ALL PRAISE TO THE MOST HIGH" — family enrollment flow (owner confirms)
        # When someone says it: AI asks "Who are you?" → owner confirms enroll or do not enroll
        self._pending_family_enrollment: Optional[Dict[str, Any]] = None
        self._pending_enrollment_timeout = 120.0  # Seconds to wait for owner confirmation
        
        # SOTA 2026 FIX: Subscribe to voice.listen IMMEDIATELY in __init__
        # so the GUI can trigger listening even if Vosk init fails later.
        if self.event_bus:
            self._subscribe_to_events()
        
        logger.info("🎤 AlwaysOnVoice initialized - SOTA 2026")
    
    def initialize(self) -> bool:
        """Initialize the voice recognition system.
        
        Returns:
            True if initialization successful
        """
        try:
            # Events already subscribed in __init__, but re-subscribe if event_bus was set later
            if self.event_bus and not hasattr(self, '_events_subscribed'):
                self._subscribe_to_events()
            
            # SOTA 2026: Initialize User Identity Engine (lazy — won't block)
            try:
                from core.user_identity import get_user_identity_engine
                self._identity_engine = get_user_identity_engine(event_bus=self.event_bus)
                # Ensure owner profile exists
                self._identity_engine.enroll_owner("Isaiah Wright")
                # Living trust defaults (normal operation, non-estate mode).
                self._ensure_default_family_profiles()
                logger.info("🆔 UserIdentityEngine connected to AlwaysOnVoice")
                status = self._identity_engine.get_status()
                if status.get('owner_voice_samples', 0) == 0:
                    logger.info("   ⚠️ No voice enrollment yet — say 'Kingdom enroll voice' to enroll")
                    logger.info(f"   Grace period: {self._identity_grace_period}s (accepting all commands)")
            except Exception as e:
                logger.warning(f"⚠️ UserIdentityEngine not available: {e} — accepting all commands")
                self._identity_engine = None
            
            # SOTA 2026: Subscribe to identity events from AI command router
            if self.event_bus:
                try:
                    self.event_bus.subscribe('identity.verify', self._handle_identity_verify)
                    self.event_bus.subscribe('identity.enroll.voice', lambda d: self._handle_voice_enrollment())
                    self.event_bus.subscribe('identity.enroll.face', lambda d: self._handle_face_enrollment())
                    self.event_bus.subscribe('identity.status', self._handle_identity_status)
                    logger.info("✅ Subscribed to identity.* events from AI command router")
                except Exception as sub_err:
                    logger.debug(f"Identity event subscription: {sub_err}")
            
            # Initialize Vosk recognizer
            if not self._init_vosk():
                logger.warning("⚠️ Vosk initialization failed, trying SpeechRecognition fallback")
                if not self._init_speech_recognition():
                    logger.error("❌ All voice recognition backends failed")
                    return False
            
            with self._state_lock:
                self._state = VoiceState.LISTENING_WAKE
            
            logger.info("✅ AlwaysOnVoice initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ AlwaysOnVoice initialization failed: {e}")
            return False
    
    def _subscribe_to_events(self):
        """Subscribe to event bus for TTS coordination and voice.listen control."""
        if not self.event_bus:
            return
        if getattr(self, '_events_subscribed', False):
            return
        self._events_subscribed = True
        
        subscribe = getattr(self.event_bus, 'subscribe_sync', None) or self.event_bus.subscribe
        
        # SOTA 2026 FIX: Subscribe to voice.listen so GUI auto-listen and mic button work
        subscribe('voice.listen', self._handle_voice_listen_event)
        
        # Pause during AI speech (canonical event only)
        subscribe('voice.speaking.started', self._on_ai_speaking_started)
        
        # Resume after AI speech (canonical event only)
        subscribe('voice.speaking.stopped', self._on_ai_speaking_stopped)
        # Track successful biometric auth so voice flow stays responsive for owner.
        subscribe('security.authenticated', self._on_security_authenticated)
        subscribe('vision.stream.frame', self._on_vision_stream_frame)
        subscribe('vision.stream.vr.frame', self._on_vision_stream_vr_frame)
        subscribe('vision.stream.meta_glasses.frame', self._on_vision_stream_meta_frame)
        subscribe('vision.frame.new', self._on_vision_stream_frame)
        
        # Self-subscribe to wake-word event so detection activates listening
        subscribe('voice.wake', self._handle_voice_wake)
        
        logger.info("🔗 Subscribed to TTS coordination + voice.listen events")
    
    def _handle_voice_listen_event(self, data: Any):
        """Handle voice.listen event from GUI (auto-listen at boot, mic button press).
        
        This is the critical bridge: ThothQt publishes voice.listen at boot+6s
        and on every mic button press. Without this handler, the AlwaysOnVoice
        audio capture loop never starts.
        """
        try:
            action = 'start'
            if isinstance(data, dict):
                action = data.get('action', 'start').lower()
            
            if action == 'start':
                if self._listen_thread and self._listen_thread.is_alive():
                    logger.debug("voice.listen start: already running")
                    return
                logger.info("🎤 voice.listen event received — starting AlwaysOnVoice")
                self.start()
            elif action == 'stop':
                logger.info("🛑 voice.listen stop event — stopping AlwaysOnVoice")
                self.stop()
        except Exception as e:
            logger.error(f"Error handling voice.listen event: {e}")

    def _get_voice_model(self) -> str:
        try:
            from core.ollama_gateway import OllamaOrchestrator
            return OllamaOrchestrator().get_model_for_task("voice") or "cogito:latest"
        except Exception:
            return os.environ.get('KINGDOM_DEFAULT_MODEL', 'cogito:latest')

    def _handle_voice_wake(self, data: dict):
        """Handle wake word detection — activate active listening."""
        logger.info("Wake word detected — activating listener")
        if hasattr(self, '_active_listening'):
            self._active_listening = True

    def _on_vision_stream_frame(self, data: Any):
        try:
            frame = (data or {}).get("frame") if isinstance(data, dict) else None
            if frame is None:
                return
            with self._vision_frame_lock:
                self._vision_last_frame = frame
                self._vision_last_frame_ts = time.time()
        except Exception:
            pass

    def _on_vision_stream_vr_frame(self, data: Any):
        try:
            frame = (data or {}).get("frame") if isinstance(data, dict) else None
            if frame is None:
                return
            with self._vision_frame_lock:
                self._vision_vr_last_frame = frame
                self._vision_vr_last_frame_ts = time.time()
        except Exception:
            pass

    def _on_vision_stream_meta_frame(self, data: Any):
        try:
            frame = (data or {}).get("frame") if isinstance(data, dict) else None
            if frame is None:
                return
            with self._vision_frame_lock:
                self._vision_meta_last_frame = frame
                self._vision_meta_last_frame_ts = time.time()
        except Exception:
            pass

    def _build_voice_vision_payload(self, command: str) -> Dict[str, Any]:
        """Build image payload from latest webcam/VR/meta frame for ai.request."""
        payload: Dict[str, Any] = {}
        try:
            cmd = (command or "").lower()
            preferred = "camera"
            if "meta" in cmd or "glasses" in cmd:
                preferred = "meta"
            elif "vr" in cmd:
                preferred = "vr"

            with self._vision_frame_lock:
                frames = {
                    "camera": (self._vision_last_frame, float(self._vision_last_frame_ts or 0.0)),
                    "vr": (self._vision_vr_last_frame, float(self._vision_vr_last_frame_ts or 0.0)),
                    "meta": (self._vision_meta_last_frame, float(self._vision_meta_last_frame_ts or 0.0)),
                }

            now = time.time()
            candidates = []
            for src, (frame, ts) in frames.items():
                if frame is None:
                    continue
                age = (now - ts) if ts > 0.0 else 9999.0
                candidates.append((src, frame, age))
            if not candidates:
                return payload

            chosen = sorted(candidates, key=lambda x: (x[0] != preferred, x[2]))[0]
            source, frame, age_s = chosen

            import base64
            import cv2
            arr = np.asarray(frame)
            if arr is None or arr.size == 0:
                return payload
            ok, buffer = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                return payload
            payload["images"] = [base64.b64encode(buffer).decode("utf-8")]
            payload["vision_source"] = source
            payload["vision_frame_age_s"] = float(age_s)
        except Exception:
            return payload
        return payload

    def _detect_vision_user_intent(self, command: str) -> str:
        """Return `creative`, `research`, or empty string for non-vision commands."""
        raw = (command or "").strip().lower()
        if not raw:
            return ""
        creative_markers = (
            "send this image", "send image to creative studio", "to creative studio",
            "create from this image", "use this frame in creative studio",
        )
        research_markers = (
            "research this image", "research this frame", "analyze this image",
            "analyze this frame", "search the web with this image",
            "what do you see in this image", "describe this image",
        )
        if any(m in raw for m in creative_markers):
            return "creative"
        if any(m in raw for m in research_markers):
            return "research"
        return ""

    def _on_security_authenticated(self, data: Any):
        """Track owner/session auth events to soften transient verification failures."""
        try:
            user_id = str((data or {}).get('user_id', '')).strip().lower()
            security_level = str((data or {}).get('security_level', '')).strip().lower()
            if user_id.startswith("owner") or security_level == "owner":
                self._mark_owner_authenticated()
                logger.debug("🔐 Owner authenticated event received - enabling short voice bypass window")
                self._emit_auth_trace("owner_authenticated_event", "security.authenticated")
        except Exception:
            # Do not break event handling for malformed payloads
            pass

    def _mark_owner_authenticated(self):
        """Atomically mark owner auth time for cross-thread auth checks."""
        now = time.time()
        try:
            with self._owner_auth_lock:
                self._last_owner_auth_time = now
        except Exception:
            self._last_owner_auth_time = now

    def _owner_auth_window_active(self, now: Optional[float] = None) -> bool:
        """Thread-safe check for owner bypass window activity."""
        ts_now = now if now is not None else time.time()
        try:
            with self._owner_auth_lock:
                last_auth = float(self._last_owner_auth_time or 0.0)
        except Exception:
            last_auth = float(self._last_owner_auth_time or 0.0)
        return last_auth > 0.0 and (ts_now - last_auth) <= self._owner_auth_bypass_window

    def _emit_auth_trace(self, decision: str, reason: str, request_id: str = "", command: str = "", extra: Optional[Dict[str, Any]] = None):
        """Emit deterministic auth decision traces for end-to-end debugging."""
        if not self.event_bus:
            return
        try:
            payload = {
                "stage": "always_on_voice.auth",
                "decision": str(decision),
                "reason": str(reason),
                "request_id": request_id or "",
                "command": (command or "")[:180],
                "timestamp": time.time(),
            }
            if isinstance(extra, dict):
                payload.update(extra)
            self.event_bus.publish("voice.auth.trace", payload)
        except Exception:
            pass
    
    def _on_ai_speaking_started(self, data: Any):
        """Handle AI started speaking - pause listening."""
        with self._ai_speaking_lock:
            self._is_ai_speaking = True
        logger.debug("🔇 AI speaking - pausing voice detection")
    
    def _on_ai_speaking_stopped(self, data: Any):
        """Handle AI stopped speaking - resume listening after cooldown."""
        with self._ai_speaking_lock:
            self._is_ai_speaking = False
            self._ai_speaking_stopped_time = time.time()
        logger.debug("🔊 AI stopped speaking - resuming voice detection after cooldown")
    
    def _init_vosk(self) -> bool:
        """Initialize Vosk speech recognition.
        
        Returns:
            True if Vosk initialized successfully
        """
        try:
            import vosk
            
            # Try to find or download model
            model_path = self.config.vosk_model_path
            
            if not model_path:
                # Try common paths
                possible_paths = [
                    os.path.expanduser("~/.vosk/vosk-model-small-en-us-0.15"),
                    "/tmp/vosk-model-small-en-us-0.15",
                    "vosk-model-small-en-us-0.15",
                    os.path.join(os.path.dirname(__file__), "..", "models", "vosk-model-small-en-us-0.15"),
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        model_path = path
                        break
                
                if not model_path:
                    # Auto-download small model
                    logger.info("📥 Downloading Vosk model (this may take a moment)...")
                    model_path = self._download_vosk_model()
            
            if not model_path or not os.path.exists(model_path):
                logger.warning("⚠️ Vosk model not found")
                return False
            
            # Suppress Vosk logging
            vosk.SetLogLevel(-1)
            
            # Load model
            logger.info(f"📦 Loading Vosk model from: {model_path}")
            model = vosk.Model(model_path)
            self._recognizer = vosk.KaldiRecognizer(model, self.config.sample_rate)
            self._recognizer.SetWords(True)
            
            logger.info("✅ Vosk speech recognition initialized")
            return True
            
        except ImportError:
            logger.warning("⚠️ Vosk not installed. Install with: pip install vosk")
            return False
        except Exception as e:
            logger.error(f"❌ Vosk initialization error: {e}")
            return False
    
    def _download_vosk_model(self) -> Optional[str]:
        """Download Vosk model if not present.
        
        Returns:
            Path to downloaded model or None
        """
        try:
            import urllib.request
            import zipfile
            
            model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
            model_dir = os.path.expanduser("~/.vosk")
            model_path = os.path.join(model_dir, "vosk-model-small-en-us-0.15")
            zip_path = os.path.join(model_dir, "model.zip")
            
            if os.path.exists(model_path):
                return model_path
            
            os.makedirs(model_dir, exist_ok=True)
            
            logger.info(f"📥 Downloading Vosk model from {model_url}...")
            urllib.request.urlretrieve(model_url, zip_path)
            
            logger.info("📦 Extracting model...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(model_dir)
            
            os.remove(zip_path)
            
            logger.info(f"✅ Model downloaded to: {model_path}")
            return model_path
            
        except Exception as e:
            logger.error(f"❌ Failed to download Vosk model: {e}")
            return None
    
    def _init_speech_recognition(self) -> bool:
        """Initialize SpeechRecognition library as fallback.
        
        Returns:
            True if initialized successfully
        """
        try:
            import speech_recognition as sr
            
            self._sr_recognizer = sr.Recognizer()
            self._sr_recognizer.dynamic_energy_threshold = True
            self._sr_recognizer.energy_threshold = 300
            
            # Test microphone access
            with sr.Microphone() as source:
                self._sr_recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            logger.info("✅ SpeechRecognition fallback initialized")
            return True
            
        except ImportError:
            logger.warning("⚠️ SpeechRecognition not installed")
            return False
        except Exception as e:
            logger.error(f"❌ SpeechRecognition initialization error: {e}")
            return False
    
    def start(self) -> bool:
        """Start always-on voice detection in background thread.
        
        Returns:
            True if started successfully
        """
        if self._listen_thread and self._listen_thread.is_alive():
            logger.warning("⚠️ Voice detection already running")
            return True
        
        if not self._recognizer and not hasattr(self, '_sr_recognizer'):
            if not self.initialize():
                return False
        
        self._should_run = True
        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            name="AlwaysOnVoice",
            daemon=True
        )
        self._listen_thread.start()
        
        logger.info("🎤 Always-on voice detection STARTED")
        
        # Publish started event
        if self.event_bus:
            self.event_bus.publish('voice.always_on.started', {
                'timestamp': time.time(),
                'wake_words': self.config.wake_words
            })
            self.event_bus.publish('voice.audio.status', {
                'status': 'listening_started',
                'message': 'Always-on voice detection active',
                'source': 'always_on_voice',
                'timestamp': time.time(),
            })
        
        return True
    
    def stop(self):
        """Stop always-on voice detection."""
        self._should_run = False
        
        # Kill PulseAudio recording subprocess if running
        if self._pulse_proc and self._pulse_proc.poll() is None:
            try:
                self._pulse_proc.terminate()
                self._pulse_proc.wait(timeout=2)
            except Exception:
                pass
            self._pulse_proc = None
        
        with self._state_lock:
            self._state = VoiceState.STOPPED
        
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=2.0)
        
        logger.info("🛑 Always-on voice detection STOPPED")
        
        if self.event_bus:
            self.event_bus.publish('voice.always_on.stopped', {
                'timestamp': time.time()
            })
            self.event_bus.publish('voice.audio.status', {
                'status': 'listening_stopped',
                'message': 'Always-on voice detection stopped',
                'source': 'always_on_voice',
                'timestamp': time.time(),
            })

    def _listen_loop(self):
        max_attempts = 3
        retry_delay = 10

        for attempt in range(1, max_attempts + 1):
            if not self._should_run:
                return

            if attempt > 1:
                logger.info(
                    f"🔄 Audio backend retry {attempt}/{max_attempts} "
                    f"(waited {retry_delay}s for PulseAudio / devices)..."
                )

            if _is_wsl():
                self._ensure_pulseaudio_running()

            # Re-detect devices on retries (PulseAudio may now be available)
            if attempt > 1 and self.config.audio_backend is None:
                detection = _detect_audio_devices()
                best = detection.get('best')
                if best:
                    self.config.audio_device = best['index']
                    self.config.audio_backend = best['backend']
                    if best['backend'] == 'pulse':
                        self.config.pulse_source = best.get('pulse_name')
                    logger.info(
                        f"🎤 Re-detected audio: [{best['index']}] {best['name']} "
                        f"via {best['backend']}"
                    )

            backend = (self.config.audio_backend or '').strip().lower() or None

            if backend in (None, 'pulse'):
                try:
                    if _is_wsl() and not self._has_real_mic_sources():
                        raise RuntimeError("PulseAudio only has RDP virtual sources — no physical mic available")
                    self._listen_loop_pulse()
                    return
                except Exception as e:
                    if _is_wsl():
                        logger.warning(f"⚠️ PulseAudio backend failed in WSL: {e}")
                        logger.info("🎤 Trying Windows host mic capture (PowerShell WASAPI)...")
                        backend = 'windows_mic'
                    else:
                        logger.warning(f"⚠️ PulseAudio backend failed: {e}, trying sounddevice...")
                        backend = 'sounddevice'

            if backend == 'windows_mic':
                try:
                    self._listen_loop_windows_mic()
                    return
                except Exception as e:
                    logger.warning(f"⚠️ Windows mic capture failed: {e} -- trying Windows ffmpeg mic...")
                    backend = 'windows_ffmpeg'

            if backend == 'windows_ffmpeg':
                try:
                    self._listen_loop_windows_ffmpeg()
                    return
                except Exception as e:
                    logger.warning(f"⚠️ Windows ffmpeg mic capture failed: {e} -- trying sounddevice...")
                    backend = 'sounddevice'

            if backend == 'sounddevice':
                try:
                    import sounddevice as sd
                    self._listen_loop_sounddevice(sd)
                    return
                except ImportError:
                    if _is_wsl():
                        logger.error("❌ sounddevice unavailable in WSL fallback path; skipping PyAudio to avoid host audio crash")
                        # Don't return yet — let retry loop try again
                        pass
                    else:
                        logger.warning("⚠️ sounddevice not available, trying PyAudio...")
                        backend = 'pyaudio'
                except Exception as e:
                    if _is_wsl():
                        logger.warning(f"⚠️ sounddevice failed in WSL fallback path: {e}")
                        pass
                    else:
                        logger.warning(f"⚠️ sounddevice failed: {e}, trying PyAudio...")
                        backend = 'pyaudio'

            if backend == 'pyaudio':
                try:
                    self._listen_loop_pyaudio()
                    return
                except Exception as e:
                    logger.warning(f"⚠️ PyAudio backend failed: {e}")

            if attempt < max_attempts:
                logger.info(
                    f"⏳ All audio backends failed (attempt {attempt}/{max_attempts}). "
                    f"Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                logger.error(
                    "❌ All audio backends failed after %d attempts. "
                    "Voice input is unavailable.", max_attempts
                )

    def _listen_loop_windows_ffmpeg(self):
        """Listen loop using Windows ffmpeg DirectShow capture piped into WSL."""
        import subprocess as _sp
        import re

        sample_rate = self.config.sample_rate
        chunk_samples = self.config.chunk_size
        bytes_per_chunk = chunk_samples * 2  # 16-bit mono

        def _detect_windows_mic_name() -> str:
            probe = _sp.run(
                [_wsl_resolve_exe('cmd.exe'), '/c', 'ffmpeg', '-hide_banner', '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy'],
                capture_output=True,
                text=True,
                timeout=20,
            )
            blob = f"{probe.stdout}\n{probe.stderr}"
            names = re.findall(r'"([^"]+)"\s+\(audio\)', blob, flags=re.IGNORECASE)
            if not names:
                raise RuntimeError("No DirectShow audio devices found via ffmpeg")

            for name in names:
                if re.search(r'brio|webcam', name, re.IGNORECASE):
                    return name
            for name in names:
                if re.search(r'microphone|mic', name, re.IGNORECASE):
                    return name
            return names[0]

        mic_name = _detect_windows_mic_name()
        logger.info(f"🎤 Windows ffmpeg mic selected: {mic_name}")

        cmd = [
            _wsl_resolve_exe('cmd.exe'), '/c', 'ffmpeg',
            '-f', 'dshow',
            '-i', f'audio={mic_name}',
            '-ac', '1',
            '-ar', str(sample_rate),
            '-f', 's16le',
            '-loglevel', 'error',
            '-nostdin',
            '-',
        ]

        proc = _sp.Popen(
            cmd,
            stdout=_sp.PIPE,
            stderr=_sp.PIPE,
            bufsize=0,
        )
        self._pulse_proc = proc  # reuse cleanup path

        try:
            while self._should_run:
                audio_data = proc.stdout.read(bytes_per_chunk)
                if not audio_data:
                    if proc.poll() is not None:
                        err = proc.stderr.read().decode('utf-8', errors='replace')
                        raise RuntimeError(f"ffmpeg DirectShow capture exited: {err[:400]}")
                    continue

                with self._ai_speaking_lock:
                    if self._is_ai_speaking:
                        continue

                self._process_audio_chunk(audio_data)
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self._pulse_proc = None
    
    def _listen_loop_pulse(self):
        """Listen loop using PulseAudio native recording (parec subprocess).
        
        This is the PRIMARY backend for WSL2 where PulseAudio/WSLg provides
        access to Windows audio devices (Brio webcam mic, headsets, etc.).
        """
        import subprocess
        
        source = self.config.pulse_source  # e.g. 'RDPSource' or specific device
        # In WSL/WSLg, hard-pin to RDPSource can miss live mic on some setups.
        # If RDP source was auto-selected, prefer PulseAudio default input device.
        if isinstance(source, str) and "rdp" in source.lower():
            logger.info("🎤 RDPSource detected - using PulseAudio default input for better mic compatibility")
            source = None
        
        # Build parec command
        cmd = [
            'parec',
            '--format=s16le',
            f'--rate={self.config.sample_rate}',
            '--channels=1',
            '--raw',
            '--latency-msec=100',
        ]
        if source:
            cmd.extend(['-d', source])
        
        # Ensure PULSE_SERVER is set for WSLg (socket at /mnt/wslg/PulseServer)
        env = os.environ.copy()
        pulse_socket = '/mnt/wslg/PulseServer'
        if not env.get('PULSE_SERVER') and os.path.exists(pulse_socket):
            env['PULSE_SERVER'] = f'unix:{pulse_socket}'
            logger.info(f"🔊 Set PULSE_SERVER=unix:{pulse_socket}")
        
        logger.info(f"🎤 Starting PulseAudio recording: {' '.join(cmd)}")

        try:
            # SOTA 2026: Auto-start PulseAudio daemon if not already running.
            # In WSL2/WSLg the socket usually exists at /mnt/wslg/PulseServer,
            # but pactl will fail if the daemon isn't up. Start it quietly.
            try:
                daemon_check = subprocess.run(
                    ['pactl', 'info'], capture_output=True, timeout=3, env=env)
                if daemon_check.returncode != 0:
                    logger.info("🔊 PulseAudio daemon not running - starting automatically...")
                    subprocess.run(
                        ['pulseaudio', '--start', '-D'],
                        capture_output=True, timeout=5, env=env)
                    time.sleep(1.0)  # give daemon a moment to init
            except FileNotFoundError:
                # pulseaudio/pactl not installed; will be handled by main check below
                pass
            except subprocess.TimeoutExpired:
                logger.warning("🔊 PulseAudio start check timed out; continuing to main check")

            check = subprocess.run(
                ['pactl', 'info'], capture_output=True, timeout=3, env=env)
            if check.returncode != 0:
                stderr_txt = (check.stderr or b'').decode('utf-8', errors='replace').strip()
                raise RuntimeError(f"pactl info failed (rc={check.returncode}): {stderr_txt}")
            logger.info("🔊 PulseAudio reachable (pactl info OK)")
        except FileNotFoundError:
            raise RuntimeError("pactl not installed — install pulseaudio-utils")
        except subprocess.TimeoutExpired:
            raise RuntimeError("pactl info timed out — PulseAudio not responding")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,
        )
        
        self._pulse_proc = proc  # Store for cleanup
        
        try:
            bytes_per_chunk = self.config.chunk_size * 2  # 16-bit = 2 bytes/sample
            last_rescan = time.time()
            
            logger.info("🎤 PulseAudio microphone stream opened - listening for 'Kingdom'...")
            
            while self._should_run:
                # Check if process died
                if proc.poll() is not None:
                    stderr_out = proc.stderr.read().decode('utf-8', errors='replace')
                    logger.error(f"❌ parec process exited: {stderr_out}")
                    raise RuntimeError(f"parec exited with code {proc.returncode}: {stderr_out}")
                
                # Skip if AI is speaking
                with self._ai_speaking_lock:
                    if self._is_ai_speaking:
                        # Drain audio to prevent buffer buildup
                        proc.stdout.read(bytes_per_chunk)
                        continue
                
                # Read audio chunk
                audio_data = proc.stdout.read(bytes_per_chunk)
                if not audio_data:
                    time.sleep(0.01)
                    continue
                
                # Process through Vosk
                self._process_audio_chunk(audio_data)
                
                # Periodic device re-scan for hot-plug / takeover
                now = time.time()
                if now - last_rescan > self.config.device_rescan_interval:
                    last_rescan = now
                    self._check_device_changes()
        
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.communicate(timeout=3)
                except Exception:
                    proc.kill()
                    proc.communicate()
            else:
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
            self._pulse_proc = None

    def _ensure_pulseaudio_running(self) -> bool:
        """Ensure PulseAudio is reachable in WSL/WSLg before attempting mic capture.

        Sets PULSE_SERVER if the WSLg socket exists and tests with ``pactl info``.
        Retries for up to 5 seconds to handle delayed WSLg startup.

        Returns True if PulseAudio is reachable after this call.
        """
        import subprocess as _sp

        _sock = '/mnt/wslg/PulseServer'
        if os.path.exists(_sock) and not os.environ.get('PULSE_SERVER'):
            os.environ['PULSE_SERVER'] = f'unix:{_sock}'
            logger.info("🔊 Set PULSE_SERVER=unix:%s", _sock)

        env = os.environ.copy()

        for wait in (0, 1, 2, 2):
            if wait:
                time.sleep(wait)
            try:
                res = _sp.run(
                    ['pactl', 'info'],
                    capture_output=True, text=True, timeout=5, env=env,
                )
                if res.returncode == 0:
                    logger.info("✅ PulseAudio is reachable")
                    return True
            except Exception:
                pass

        logger.warning("⚠️ PulseAudio not reachable after 5 s — will try fallback backends")
        return False

    def _has_real_mic_sources(self) -> bool:
        """Check if PulseAudio has a real (non-RDP, non-monitor) mic source."""
        try:
            import subprocess as _sp
            env = os.environ.copy()
            _sock = '/mnt/wslg/PulseServer'
            if not env.get('PULSE_SERVER') and os.path.exists(_sock):
                env['PULSE_SERVER'] = f'unix:{_sock}'
            res = _sp.run(['pactl', 'list', 'sources', 'short'],
                          capture_output=True, text=True, timeout=5, env=env)
            if res.returncode != 0:
                return False
            for line in res.stdout.strip().splitlines():
                name = line.split('\t')[1] if '\t' in line else ''
                nl = name.lower()
                if '.monitor' in nl or 'rdp' in nl:
                    continue
                return True
        except Exception:
            pass
        return False

    def _listen_loop_windows_mic(self):
        """Listen loop using PowerShell WASAPI capture from Windows host mic.

        Captures raw s16le PCM from the Brio webcam mic (or any Windows mic)
        via PowerShell and pipes it to WSL for Vosk speech recognition.
        """
        import subprocess as _sp

        sample_rate = self.config.sample_rate
        chunk_samples = self.config.chunk_size
        bytes_per_chunk = chunk_samples * 2  # 16-bit mono

        ps_script = f'''
Add-Type -AssemblyName System.Core
Add-Type @"
using System;
using System.IO;
using System.Runtime.InteropServices;

public class WasapiCapture {{
    [DllImport("winmm.dll")]
    public static extern int waveInGetNumDevs();
    [DllImport("winmm.dll", CharSet=CharSet.Auto)]
    public static extern int waveInGetDevCaps(int id, ref WAVEINCAPS caps, int size);
    [DllImport("winmm.dll")]
    public static extern int waveInOpen(ref IntPtr h, int id, ref WAVEFORMAT fmt, IntPtr cb, IntPtr inst, int flags);
    [DllImport("winmm.dll")]
    public static extern int waveInPrepareHeader(IntPtr h, ref WAVEHDR hdr, int size);
    [DllImport("winmm.dll")]
    public static extern int waveInAddBuffer(IntPtr h, ref WAVEHDR hdr, int size);
    [DllImport("winmm.dll")]
    public static extern int waveInStart(IntPtr h);
    [DllImport("winmm.dll")]
    public static extern int waveInStop(IntPtr h);
    [DllImport("winmm.dll")]
    public static extern int waveInClose(IntPtr h);
    [DllImport("winmm.dll")]
    public static extern int waveInReset(IntPtr h);

    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Auto)]
    public struct WAVEINCAPS {{
        public ushort wMid; public ushort wPid; public uint vDriverVersion;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string szPname;
        public uint dwFormats; public ushort wChannels; public ushort wReserved1;
    }}

    [StructLayout(LayoutKind.Sequential)]
    public struct WAVEFORMAT {{
        public ushort wFormatTag; public ushort nChannels; public uint nSamplesPerSec;
        public uint nAvgBytesPerSec; public ushort nBlockAlign; public ushort wBitsPerSample;
        public ushort cbSize;
    }}

    [StructLayout(LayoutKind.Sequential)]
    public struct WAVEHDR {{
        public IntPtr lpData; public uint dwBufferLength; public uint dwBytesRecorded;
        public IntPtr dwUser; public uint dwFlags; public uint dwLoops;
        public IntPtr lpNext; public IntPtr reserved;
    }}
}}
"@

$numDevs = [WasapiCapture]::waveInGetNumDevs()
$brioIdx = -1
for ($i = 0; $i -lt $numDevs; $i++) {{
    $caps = New-Object WasapiCapture+WAVEINCAPS
    [WasapiCapture]::waveInGetDevCaps($i, [ref]$caps, [System.Runtime.InteropServices.Marshal]::SizeOf($caps)) | Out-Null
    if ($caps.szPname -match "Brio") {{ $brioIdx = $i; break }}
}}
if ($brioIdx -lt 0) {{
    for ($i = 0; $i -lt $numDevs; $i++) {{
        $caps = New-Object WasapiCapture+WAVEINCAPS
        [WasapiCapture]::waveInGetDevCaps($i, [ref]$caps, [System.Runtime.InteropServices.Marshal]::SizeOf($caps)) | Out-Null
        if ($caps.szPname -match "USB|Mic|Webcam") {{ $brioIdx = $i; break }}
    }}
}}
if ($brioIdx -lt 0 -and $numDevs -gt 0) {{ $brioIdx = 0 }}
if ($brioIdx -lt 0) {{ [Console]::Error.WriteLine("NO_MIC"); exit 1 }}

$fmt = New-Object WasapiCapture+WAVEFORMAT
$fmt.wFormatTag = 1
$fmt.nChannels = 1
$fmt.nSamplesPerSec = {sample_rate}
$fmt.wBitsPerSample = 16
$fmt.nBlockAlign = 2
$fmt.nAvgBytesPerSec = {sample_rate} * 2
$fmt.cbSize = 0

$hWaveIn = [IntPtr]::Zero
$res = [WasapiCapture]::waveInOpen([ref]$hWaveIn, $brioIdx, [ref]$fmt, [IntPtr]::Zero, [IntPtr]::Zero, 0)
if ($res -ne 0) {{ [Console]::Error.WriteLine("OPEN_FAIL:$res"); exit 1 }}

$bufSize = {bytes_per_chunk}
$numBuf = 4
$buffers = @()
$headers = @()
for ($i = 0; $i -lt $numBuf; $i++) {{
    $buf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal($bufSize)
    $hdr = New-Object WasapiCapture+WAVEHDR
    $hdr.lpData = $buf; $hdr.dwBufferLength = $bufSize; $hdr.dwFlags = 0
    [WasapiCapture]::waveInPrepareHeader($hWaveIn, [ref]$hdr, [System.Runtime.InteropServices.Marshal]::SizeOf($hdr)) | Out-Null
    [WasapiCapture]::waveInAddBuffer($hWaveIn, [ref]$hdr, [System.Runtime.InteropServices.Marshal]::SizeOf($hdr)) | Out-Null
    $buffers += $buf; $headers += $hdr
}}

[WasapiCapture]::waveInStart($hWaveIn) | Out-Null
[Console]::Error.WriteLine("MIC_READY:$brioIdx")

$stdout = [Console]::OpenStandardOutput()
$raw = New-Object byte[] $bufSize
try {{
    while ($true) {{
        for ($i = 0; $i -lt $numBuf; $i++) {{
            while (($headers[$i].dwFlags -band 1) -eq 0) {{
                Start-Sleep -Milliseconds 5
            }}
            [System.Runtime.InteropServices.Marshal]::Copy($headers[$i].lpData, $raw, 0, $bufSize)
            $stdout.Write($raw, 0, $bufSize)
            $stdout.Flush()
            $headers[$i].dwFlags = 0
            [WasapiCapture]::waveInAddBuffer($hWaveIn, [ref]$headers[$i], [System.Runtime.InteropServices.Marshal]::SizeOf($headers[$i])) | Out-Null
        }}
    }}
}} finally {{
    [WasapiCapture]::waveInReset($hWaveIn) | Out-Null
    [WasapiCapture]::waveInClose($hWaveIn) | Out-Null
    foreach ($b in $buffers) {{ [System.Runtime.InteropServices.Marshal]::FreeHGlobal($b) }}
}}
'''

        logger.info("🎤 Starting Windows host mic capture via PowerShell (waveIn API)...")

        proc = _sp.Popen(
            [_wsl_resolve_exe('powershell.exe'), '-NoProfile', '-ExecutionPolicy', 'Bypass',
             '-Command', ps_script],
            stdout=_sp.PIPE,
            stderr=_sp.PIPE,
            bufsize=0,
        )
        self._pulse_proc = proc  # reuse cleanup path

        unexpected_exit = False
        try:
            ready_line = proc.stderr.readline().decode('utf-8', errors='replace').strip()
            if ready_line.startswith('NO_MIC') or ready_line.startswith('OPEN_FAIL'):
                raise RuntimeError(f"Windows mic capture failed: {ready_line}")
            if ready_line.startswith('MIC_READY'):
                dev_idx = ready_line.split(':')[1] if ':' in ready_line else '?'
                logger.info(f"🎤 Windows mic stream opened (device {dev_idx}) — listening for 'Kingdom'...")
            else:
                logger.warning(f"🎤 Unexpected stderr from mic capture: {ready_line}")

            while self._should_run:
                try:
                    audio_data = proc.stdout.read(bytes_per_chunk)
                    if not audio_data:
                        if proc.poll() is not None:
                            stderr_out = proc.stderr.read().decode('utf-8', errors='replace')
                            logger.error(f"PowerShell mic capture process died: {stderr_out[:500]}")
                            if self._should_run:
                                unexpected_exit = True
                            break
                        continue

                    with self._ai_speaking_lock:
                        if self._is_ai_speaking:
                            continue

                    self._process_audio_chunk(audio_data)
                except Exception as e:
                    if not self._should_run:
                        break
                    logger.error(f"Error in Windows mic listen loop: {e}")
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self._pulse_proc = None

        if unexpected_exit:
            raise RuntimeError("PowerShell mic capture process died unexpectedly")

    def _listen_loop_sounddevice(self, sd):
        """Listen loop using sounddevice/PortAudio."""
        logger.info("🎧 Starting audio capture with sounddevice")
        
        def audio_callback(indata, frames, time_info, status):
            """Non-blocking audio callback."""
            if status:
                logger.warning(f"Audio status: {status}")
            with self._ai_speaking_lock:
                if self._is_ai_speaking:
                    return
            self._audio_queue.put(bytes(indata))
        
        device_kwargs = {}
        if self.config.audio_device is not None:
            try:
                sd.query_devices(self.config.audio_device)
                device_kwargs['device'] = self.config.audio_device
                logger.info(f"🎤 Using audio device index {self.config.audio_device}")
            except Exception as dev_err:
                logger.warning(f"⚠️ Configured device {self.config.audio_device} invalid ({dev_err}), using default")

        with sd.RawInputStream(
            samplerate=self.config.sample_rate,
            blocksize=self.config.chunk_size,
            dtype='int16',
            channels=1,
            callback=audio_callback,
            **device_kwargs
        ):
            logger.info("🎤 Microphone stream opened (sounddevice) - listening for 'Kingdom'...")
            last_rescan = time.time()
            
            while self._should_run:
                try:
                    try:
                        audio_data = self._audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    
                    with self._ai_speaking_lock:
                        if self._is_ai_speaking:
                            continue
                    
                    self._process_audio_chunk(audio_data)
                    
                    # Periodic device re-scan
                    now = time.time()
                    if now - last_rescan > self.config.device_rescan_interval:
                        last_rescan = now
                        self._check_device_changes()
                
                except Exception as e:
                    logger.error(f"Error in listen loop: {e}")
                    time.sleep(0.01)

    def _process_audio_chunk(self, audio_data: bytes):
        """Process an audio chunk through speech recognition.
        
        Shared by all backends (PulseAudio, sounddevice, PyAudio).
        SOTA 2026: Caches raw audio as float32 for speaker verification.
        """
        # Cache raw audio for speaker verification (convert int16 bytes → float32)
        try:
            raw = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            # Accumulate ~2 seconds of audio for verification (16kHz × 2s = 32000 samples)
            prev = getattr(self, '_last_audio_chunk', None)
            if prev is not None and len(prev) < 32000:
                self._last_audio_chunk = np.concatenate([prev, raw])
            else:
                self._last_audio_chunk = raw
        except Exception:
            pass
        
        if self._recognizer:
            if self._recognizer.AcceptWaveform(audio_data):
                result = json.loads(self._recognizer.Result())
                text = result.get('text', '').strip()
                if text:
                    self._handle_recognized_text(text)
            else:
                if self._allow_partial_wake:
                    partial = json.loads(self._recognizer.PartialResult())
                    partial_text = partial.get('partial', '').strip()
                    if partial_text:
                        self._check_wake_word(partial_text)
    
    def _check_device_changes(self):
        """Periodic device re-scan for hot-plug / device takeover.
        
        If a higher-priority device appears (e.g., user plugs in a headset 
        or VR mic), log the change. Full takeover requires restarting the
        audio stream, which is signaled via event bus.
        """
        try:
            detection = _detect_audio_devices()
            new_best = detection.get('best')
            if not new_best:
                return
            
            current_backend = self.config.audio_backend
            current_device = self.config.audio_device
            
            # Check if a better device appeared
            if (new_best['backend'] != current_backend or
                    new_best['index'] != current_device):
                logger.info(
                    f"🔄 New audio device detected: [{new_best['index']}] "
                    f"{new_best['name']} via {new_best['backend']} "
                    f"(priority={new_best['priority']})"
                )
                
                # Update config for next restart
                self.config.audio_device = new_best['index']
                self.config.audio_backend = new_best['backend']
                if new_best['backend'] == 'pulse':
                    self.config.pulse_source = new_best.get('pulse_name')
                
                # Publish device change event
                if self.event_bus:
                    self.event_bus.publish('voice.device.changed', {
                        'new_device': new_best['name'],
                        'new_backend': new_best['backend'],
                        'new_index': new_best['index'],
                        'timestamp': time.time(),
                    })
                
                # Signal the listen loop to restart with new device
                self._device_changed = True
        except Exception as e:
            logger.debug(f"Device rescan error: {e}")
    
    def _listen_loop_pyaudio(self):
        """Alternative listen loop using PyAudio."""
        import pyaudio
        
        p = pyaudio.PyAudio()
        stream = None
        
        try:
            pyaudio_kwargs = {}
            if self.config.audio_device is not None:
                pyaudio_kwargs['input_device_index'] = self.config.audio_device
                logger.info(f"🎤 PyAudio using device index {self.config.audio_device}")

            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size,
                **pyaudio_kwargs
            )
            
            logger.info("🎤 Microphone stream opened (PyAudio) - listening for 'Kingdom'...")
            last_rescan = time.time()
            
            while self._should_run:
                try:
                    with self._ai_speaking_lock:
                        if self._is_ai_speaking:
                            time.sleep(0.01)
                            continue
                    
                    audio_data = stream.read(self.config.chunk_size, exception_on_overflow=False)
                    self._process_audio_chunk(audio_data)
                    
                    # Periodic device re-scan
                    now = time.time()
                    if now - last_rescan > self.config.device_rescan_interval:
                        last_rescan = now
                        self._check_device_changes()
                
                except Exception as e:
                    logger.error(f"Error in listen loop: {e}")
                    time.sleep(0.01)
        
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            p.terminate()
    
    def _check_wake_word(self, text: str) -> bool:
        """Check if text contains wake word.
        
        Args:
            text: Recognized text to check
            
        Returns:
            True if wake word detected
        """
        wake_word, _ = self._extract_wake_command(text)
        if wake_word:
            if not self._is_owner_present_for_voice():
                logger.debug(f"🔇 Wake ignored (owner not verified present): '{text}'")
                return False
            logger.info(f"🎯 WAKE WORD DETECTED: '{wake_word}' in '{text}'")

            # Publish wake event
            if self.event_bus:
                self.event_bus.publish('voice.wake', {
                    'wake_word': wake_word,
                    'full_text': text,
                    'timestamp': time.time()
                })

            # Call callback if set
            if self._wake_detected_callback:
                try:
                    self._wake_detected_callback(wake_word, text)
                except Exception as e:
                    logger.error(f"Wake callback error: {e}")

            return True

        return False

    def _extract_wake_command(self, text: str) -> tuple[Optional[str], str]:
        """Extract wake word + trailing command with strict anti-noise matching.

        Wake phrase must occur at phrase start (or with at most one leading token).
        This avoids random in-sentence media dialogue from triggering Kingdom.
        """
        raw = (text or "").strip()
        text_lower = raw.lower()
        for wake_word in self.config.wake_words:
            idx = text_lower.find(wake_word)
            if idx < 0:
                continue
            prefix = text_lower[:idx].strip()
            if prefix and len(prefix.split()) > 1:
                continue
            command = raw[idx + len(wake_word):].strip()
            return wake_word, command
        return None, raw

    def _is_owner_present_for_voice(self) -> bool:
        """True when owner is recently authenticated or currently face-verified."""
        if not self._identity_engine:
            return True

        now = time.time()
        # Startup/auth grace: allow wake while camera/face pipeline is still settling.
        try:
            status = self._identity_engine.get_status()  # type: ignore[attr-defined]
        except Exception:
            status = {}
        has_enrollment = int(status.get('owner_voice_samples', 0) or 0) >= 3
        grace_window = self._identity_grace_period if has_enrollment else self._identity_extended_grace_period
        if (now - self._identity_init_time) <= grace_window:
            return True

        if self._owner_auth_window_active(now):
            return True

        face_result = getattr(self._identity_engine, '_current_face_result', None)
        face_time = float(getattr(self._identity_engine, '_face_result_time', 0.0) or 0.0)
        if face_result and (now - face_time) <= self._owner_face_presence_window:
            return bool(getattr(face_result, 'is_owner', False))

        return False
    
    def _handle_recognized_text(self, text: str):
        """Handle fully recognized text (complete phrase).
        
        Args:
            text: Recognized text
        """
        if not text:
            return
        
        current_time = time.time()
        
        # Deduplication
        if (text == self._last_recognized_text and 
            current_time - self._last_recognized_time < self._dedup_window):
            logger.debug(f"⏭️ Skipping duplicate: '{text}'")
            return
        
        self._last_recognized_text = text
        self._last_recognized_time = current_time
        
        # SOTA 2026: SHA-LU-AM (שלום) — "Remember!" Owner/enrolled ONLY. Bulletproof hacking defense.
        # NOT for trading. Shadow background — never noticed. Activates Hive Mind so all others come online.
        _text_norm = self._normalize_spoken_command(text) if hasattr(self, '_normalize_spoken_command') else text.lower().strip()
        _text_compact = _text_norm.replace(" ", "").replace("-", "")
        _is_sha_lu_am = (
            "shaluam" in _text_compact or "shalom" in _text_norm or
            "sha lu am" in _text_norm or "sha-lu-am" in text or
            "\u05e9\u05dc\u05d5\u05dd" in text  # Hebrew שלום
        )
        if _is_sha_lu_am:
            # CRITICAL: Only owner or enrolled may activate. Others: silent ignore (shadow, no trace).
            if not self._is_owner_present_for_voice():
                return  # Unverified — do nothing, no log, no publish. Runtime unaffected.
            if self.event_bus:
                self.event_bus.publish("secret.reserve.reveal", {
                    "trigger": "SHA-LU-AM",
                    "text": text,
                    "timestamp": current_time,
                    "source": "always_on_voice",
                    "owner_verified": True,
                    "hive_mind_activate": True,  # Allow all others to come online
                })
            logger.debug("SHA-LU-AM (owner verified) — reserve + hive")
        
        # DISABLED: Auto-enrollment from name introduction was falsely triggering
        # on ambient sounds (e.g. speaker "turning on" → enrolled as "On")
        # Owner enrollment is handled by auto-enroll first face/voice in user_identity.py
        # self._check_auto_enrollment(text_lower, current_time)
        
        # Check for wake word
        wake_word, command_text = self._extract_wake_command(text)
        is_wake_word = bool(wake_word)
        
        if is_wake_word:
            owner_present = self._is_owner_present_for_voice()
            if not owner_present:
                if command_text and self._is_seeking_owner_location(command_text):
                    logger.info("📍 Seeking owner — allowing basic access")
                elif command_text and self._allow_basic_when_owner_absent(command_text, text):
                    pass
                else:
                    logger.info(f"🔇 Ignoring wake phrase while owner not verified present: '{text}'")
                    if self.event_bus:
                        self.event_bus.publish('voice.input.recognized', {
                            'text': command_text or text, 'full_text': text,
                            'request_id': f"voice_gated_{int(current_time * 1000)}",
                            'source': 'always_on_voice', 'already_routed': True,
                            'timestamp': current_time, 'gated': True,
                            'reason': 'owner_not_verified',
                        })
                    return
            logger.info(f"🎤 KINGDOM ACTIVATED: '{text}'")
            
            # Publish wake event
            if self.event_bus:
                self.event_bus.publish('voice.wake', {
                    'wake_word': wake_word,
                    'full_text': text,
                    'command': command_text,
                    'timestamp': current_time
                })
            
            # If there's a command after wake word, process it
            if command_text:
                # SOTA 2026: Intercept enrollment and access control commands
                cmd_lower = command_text.lower().strip()
                normalized = self._normalize_spoken_command(command_text)
                wants_voice_enroll = any(k in normalized for k in (
                    "enroll voice", "enroll my voice", "learn my voice",
                    "register voice", "voice enrollment",
                ))
                wants_face_enroll = any(k in normalized for k in (
                    "enroll face", "enroll my face", "learn my face",
                    "register face", "face enrollment",
                ))

                if wants_voice_enroll or wants_face_enroll:
                    # Ensure spoken enrollment commands always appear in chat.
                    request_id = f"voice_enroll_{int(current_time * 1000)}"
                    if self.event_bus:
                        self.event_bus.publish('voice.input.recognized', {
                            'text': command_text,
                            'full_text': text,
                            'request_id': request_id,
                            'source': 'always_on_voice',
                            'already_routed': True,
                            'timestamp': current_time
                        })

                if wants_face_enroll and wants_voice_enroll:
                    self._handle_face_enrollment()
                    self._handle_voice_enrollment()
                    return
                if wants_voice_enroll:
                    self._handle_voice_enrollment()
                    return
                elif wants_face_enroll:
                    self._handle_face_enrollment()
                    return
                # SOTA 2026: "ALL PRAISE TO THE MOST HIGH" — family enrollment (owner confirms)
                if self._check_all_praise_trigger(normalized, command_text, current_time):
                    return
                # Access control commands (owner-only)
                elif cmd_lower.startswith('grant access to '):
                    target = command_text[len('grant access to '):].strip()
                    self._handle_grant_access(target)
                    return
                elif cmd_lower.startswith('do not enroll '):
                    target = command_text[len('do not enroll '):].strip()
                    if target:
                        self._handle_do_not_enroll(target)
                        return
                elif cmd_lower.startswith("don't enroll "):
                    target = command_text[len("don't enroll "):].strip()
                    if target:
                        self._handle_do_not_enroll(target)
                        return
                elif cmd_lower.startswith('deny enroll '):
                    target = command_text[len('deny enroll '):].strip()
                    if target:
                        self._handle_do_not_enroll(target)
                        return
                elif cmd_lower.startswith('enroll ') and not cmd_lower.startswith('enroll voice') and not cmd_lower.startswith('enroll face'):
                    target = command_text[len('enroll '):].strip()
                    if target and len(target.split()) >= 1:
                        self._handle_owner_confirm_enroll(target)
                        return
                elif cmd_lower.startswith('grant financial access to '):
                    target = command_text[len('grant financial access to '):].strip()
                    self._handle_grant_financial_access(target)
                    return
                elif cmd_lower.startswith('revoke access from '):
                    target = command_text[len('revoke access from '):].strip()
                    self._handle_revoke_access(target)
                    return
                elif cmd_lower.startswith('revoke financial access from '):
                    target = command_text[len('revoke financial access from '):].strip()
                    self._handle_revoke_financial_access(target)
                    return
                elif cmd_lower in ('who has access', 'list access', 'show access',
                                   'authorized users', 'who is authorized'):
                    self._handle_list_access()
                    return
                elif (
                    normalized.startswith('introduce my daughter') or
                    normalized.startswith('introduce you to my daughter') or
                    normalized.startswith('introduce to my daughter') or
                    normalized.startswith('enroll my daughter') or
                    normalized.startswith('register my daughter') or
                    normalized.startswith('enroll daughter') or
                    normalized.startswith('register daughter')
                ):
                    parsed = self._extract_named_family_member(command_text, relationship='daughter')
                    if parsed:
                        self._handle_family_member_introduced(parsed['name'], parsed['relationship'])
                        return
                    if self.event_bus:
                        self.event_bus.publish('voice.speak', {
                            'text': "Please say your daughter's full name, for example: introduce my daughter Aryah Wright.",
                            'priority': 'high',
                            'source': 'always_on_voice',
                        })
                        return
                elif (
                    normalized.startswith('introduce my son') or
                    normalized.startswith('introduce you to my son') or
                    normalized.startswith('introduce to my son') or
                    normalized.startswith('enroll my son') or
                    normalized.startswith('register my son') or
                    normalized.startswith('enroll son') or
                    normalized.startswith('register son')
                ):
                    parsed = self._extract_named_family_member(command_text, relationship='son')
                    if parsed:
                        self._handle_family_member_introduced(parsed['name'], parsed['relationship'])
                        return
                    if self.event_bus:
                        self.event_bus.publish('voice.speak', {
                            'text': "Please say your son's full name, for example: introduce my son First Last.",
                            'priority': 'high',
                            'source': 'always_on_voice',
                        })
                        return
                elif (
                    normalized.startswith('introduce my child') or
                    normalized.startswith('introduce my children') or
                    normalized.startswith('introduce you to my child') or
                    normalized.startswith('introduce you to my children') or
                    normalized.startswith('enroll my child') or
                    normalized.startswith('enroll my children') or
                    normalized.startswith('register my child') or
                    normalized.startswith('register my children')
                ):
                    parsed = self._extract_named_family_member(command_text, relationship='child')
                    if parsed:
                        self._handle_family_member_introduced(parsed['name'], parsed['relationship'])
                        return
                    if self.event_bus:
                        self.event_bus.publish('voice.speak', {
                            'text': "Please say your child's full name, for example: introduce my child First Last.",
                            'priority': 'high',
                            'source': 'always_on_voice',
                        })
                        return
                elif (
                    normalized.startswith('introduce my father') or
                    normalized.startswith('introduce you to my father') or
                    normalized.startswith('introduce to my father') or
                    normalized.startswith('enroll my father') or
                    normalized.startswith('register my father') or
                    normalized.startswith('enroll father') or
                    normalized.startswith('register father') or
                    normalized.startswith('introduce my dad') or
                    normalized.startswith('introduce you to my dad') or
                    normalized.startswith('enroll my dad') or
                    normalized.startswith('register my dad') or
                    normalized.startswith('enroll dad') or
                    normalized.startswith('register dad')
                ):
                    parsed = self._extract_named_family_member(command_text, relationship='father')
                    if parsed:
                        self._handle_family_member_introduced(parsed['name'], parsed['relationship'])
                        return
                    if self.event_bus:
                        self.event_bus.publish('voice.speak', {
                            'text': "Please say your father's full name, for example: introduce my father First Last.",
                            'priority': 'high',
                            'source': 'always_on_voice',
                        })
                        return
                self._route_command_to_ai(command_text, text)
            else:
                # Just acknowledged, wait for command
                logger.info("🎧 Listening for command...")
                
                # Play acknowledgment
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': "Yes?",
                        'priority': 'high',
                        'source': 'always_on_voice',
                        'request_id': f"wake_{int(current_time * 1000)}"
                    })
        else:
            # Require wake word for routing to prevent stale/echo conversations.
            # This avoids AI/TTS audio or ambient speech being treated as new user input.
            if self._looks_like_command(text):
                logger.debug(f"Ignoring command-like speech without wake word: '{text}'")
    
    def _looks_like_command(self, text: str) -> bool:
        """Check if text looks like a deliberate command or question.
        
        CRITICAL FIX: Previously returned True for ANY text with 3+ words,
        causing the AI's own speech output (picked up by mic) to be routed
        back as new requests, creating a feedback loop of multiple responses.
        
        Now requires explicit command indicators — wake word detection is the
        primary path for user interaction.
        
        Args:
            text: Text to check
            
        Returns:
            True if it looks like a deliberate command
        """
        text_lower = text.lower().strip()
        
        # Too short to be a real command
        if len(text_lower.split()) < 4:
            return False
        
        # Command starters (must be explicit)
        command_starters = [
            "go to", "open", "show me", "start", "stop",
            "tell me", "help me", "can you", "please",
            "navigate to", "switch to", "analyze", "check"
        ]
        
        for starter in command_starters:
            if text_lower.startswith(starter):
                return True
        
        # Direct spoken question.
        # ASR output often omits punctuation, so do not require a trailing "?".
        question_words = ["what", "how", "why", "where", "when", "who", "which", "is", "are", "can", "do", "does"]
        words = text_lower.split()
        first_word = words[0] if words else ""
        if first_word in question_words and len(words) >= 4:
            return True
        
        # REMOVED: "len(text.split()) >= 3" catch-all that matched EVERYTHING
        # This was the root cause of the feedback loop
        return False

    def _normalize_spoken_command(self, text: str) -> str:
        """Normalize ASR text for robust intent detection."""
        normalized = text.lower().strip()
        normalized = (
            normalized.replace("and roll", "enroll")
            .replace("in roll", "enroll")
            .replace("en roll", "enroll")
            .replace("daughter's", "daughters")
            .replace("son's", "sons")
            .replace("child's", "children")
        )
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        return " ".join(normalized.split())

    def _is_family_enrollment_intent(self, text: str) -> bool:
        """Detect family enrollment intents, tolerant to ASR phrasing."""
        normalized = self._normalize_spoken_command(text)
        words = set(normalized.split())
        has_family_target = bool(words.intersection({
            "daughter", "daughters", "son", "sons",
            "child", "children", "father", "dad"
        }))
        has_enroll_action = bool(words.intersection({"enroll", "introduce", "register"}))
        return has_family_target and has_enroll_action
    
    def _route_command_to_ai(self, command: str, full_text: str):
        """Route recognized command to AI for processing.
        
        CRITICAL FIX: Enforces cooldown to prevent multiple simultaneous responses.
        Only publishes ai.request (the sole event ThothAI handles).
        Removed redundant voice.command and voice.input.recognized publishes
        since VoiceProcessingSystem is not loaded at runtime.
        
        Args:
            command: The command text (wake word removed if present)
            full_text: The full recognized text
        """
        now = time.time()
        
        # CRITICAL: Command cooldown - prevent rapid-fire requests
        elapsed_since_last = now - self._last_command_routed_time
        if elapsed_since_last < self._COMMAND_COOLDOWN:
            logger.debug(f"⏭️ Command cooldown active ({elapsed_since_last:.1f}s < {self._COMMAND_COOLDOWN}s) - skipping")
            return
        
        # CRITICAL: Post-speech echo prevention
        with self._ai_speaking_lock:
            elapsed_since_speech = now - self._ai_speaking_stopped_time
            if elapsed_since_speech < self._POST_SPEECH_COOLDOWN:
                logger.debug(f"⏭️ Post-speech cooldown ({elapsed_since_speech:.1f}s < {self._POST_SPEECH_COOLDOWN}s) - skipping echo")
                return
        
        logger.info(f"📤 Routing to AI: '{command}'")
        self._last_command_routed_time = now
        
        request_id = f"voice_{int(now * 1000)}"
        
        # SOTA 2026: Speaker verification gate — only route if verified owner
        if self._identity_engine and self._require_owner_verification:
            # CRITICAL FIX: Enrollment commands ALWAYS pass — prevents lockout deadlock
            _cmd_lower = self._normalize_spoken_command(command)
            _always_allow = (
                self._is_family_enrollment_intent(command)
                or (_cmd_lower.startswith('enroll ') and 'voice' not in _cmd_lower and 'face' not in _cmd_lower)
                or any(kw in _cmd_lower for kw in [
                'enroll voice', 'enroll face', 'kingdom enroll',
                'and roll voice', 'and roll face',
                'in roll voice', 'in roll face',
                'en roll voice', 'en roll face',
                'grant access', 'revoke access', 'who has access',
                'do not enroll', "don't enroll", 'deny enroll',
                'who am i', 'identify me',
                'authorize me', 're-authenticate me', 'reauthenticate me',
                'authentication status', 'verify me',
            ])
            )
            if _always_allow:
                logger.info(f"🔓 Enrollment/identity command — bypassing verification: '{command[:50]}'")
                self._emit_auth_trace("allow", "identity_or_enrollment_bypass", request_id=request_id, command=command)
                # Fall through to publish without verification
            else:
                status = self._identity_engine.get_status()
                has_enrollment = status.get('owner_voice_samples', 0) >= 3
                if has_enrollment:
                    in_grace = (now - self._identity_init_time) < self._identity_grace_period
                else:
                    in_grace = (now - self._identity_init_time) < self._identity_extended_grace_period
                
                if has_enrollment:
                    # We have 3+ samples — verify speaker in background then route
                    threading.Thread(
                        target=self._verify_then_route,
                        args=(command, request_id, now),
                        daemon=True,
                        name="SpeakerVerify"
                    ).start()
                    return  # _verify_then_route will publish ai.request if verified
                else:
                    # < 3 voice samples — NEVER reject, still learning owner's voice
                    samples = status.get('owner_voice_samples', 0)
                    logger.info(f"🔓 Owner has {samples}/3 voice samples — accepting all commands (still learning)")
                    # Fall through to publish
        
        # Publish ai.request - the sole event ThothAI handles for processing
        self._publish_ai_request(command, request_id, now, full_text=full_text)
        
        # Call callback if set
        if self._command_recognized_callback:
            try:
                self._command_recognized_callback(command, full_text, request_id)
            except Exception as e:
                logger.error(f"Command callback error: {e}")
    
    def _verify_then_route(self, command: str, request_id: str, timestamp: float):
        """Background thread: verify speaker identity, then route if authorized.
        
        SOTA 2026: FACE-PRIMARY authentication.
        - Voice verification is for LEARNING the owner's voice, not for denying access
        - Only FACE mismatch can deny access (different person on camera)
        - If voice doesn't match but face does → accept command, keep learning voice
        - Echo rejection still applies (ignore AI's own voice from speakers)
        """
        try:
            status = self._identity_engine.get_status() if self._identity_engine else {}
            has_enrollment = int(status.get('owner_voice_samples', 0) or 0) >= 3
            grace_window = self._identity_grace_period if has_enrollment else self._identity_extended_grace_period
            in_grace = (time.time() - self._identity_init_time) < grace_window
            if not self._identity_engine:
                self._publish_ai_request(command, request_id, timestamp, full_text=command)
                return
            
            # Get recent audio for verification (last ~2 seconds from the audio queue)
            audio_data = getattr(self, '_last_audio_chunk', None)
            if audio_data is None:
                logger.debug("No cached audio for speaker verification — accepting command")
                self._publish_ai_request(command, request_id, timestamp, full_text=command)
                return
            
            # Run voice pipeline: VAD → echo rejection → speaker embedding
            result = self._identity_engine.verify_voice(audio_data, sample_rate=16000)
            
            if result.is_echo:
                logger.info(f"🔇 ECHO REJECTED: '{command[:40]}...' — AI's own voice detected")
                return
            
            if not result.is_speech:
                logger.debug(f"🔇 Not speech (VAD) — ignoring")
                return
            
            # FACE-PRIMARY: Check if owner face is currently on camera
            face_result = getattr(self._identity_engine, '_current_face_result', None)
            face_time = getattr(self._identity_engine, '_face_result_time', 0)
            face_is_owner = False
            face_is_recent = (time.time() - face_time) < self._owner_face_presence_window
            
            if face_result and face_is_recent:
                face_is_owner = getattr(face_result, 'is_owner', False)
            
            # Voice match → allow, but enforce living financial permissions.
            if result.is_authorized:
                who = result.user_name or result.role
                if result.is_owner or str(result.user_id) == "owner_primary":
                    self._mark_owner_authenticated()
                if (result.user_id and not result.is_owner and self._is_financial_intent(command)
                        and self._identity_engine and not self._identity_engine.has_financial_access(result.user_id)):
                    logger.info(f"🔒 Financial intent blocked for non-financial user {who}")
                    self._emit_auth_trace(
                        "deny",
                        "authorized_non_owner_financial_block",
                        request_id=request_id,
                        command=command,
                        extra={"voice_score": float(result.voice_score or 0.0), "speaker": str(who)},
                    )
                    if self.event_bus:
                        self.event_bus.publish('voice.input.recognized', {
                            'text': command,
                            'full_text': command,
                            'request_id': request_id,
                            'source': 'always_on_voice',
                            'already_routed': True,
                            'timestamp': time.time()
                        })
                        self.event_bus.publish('voice.speak', {
                            'text': "You are recognized, but financial actions require owner financial approval.",
                            'priority': 'high', 'source': 'always_on_voice'
                        })
                    return
                logger.info(f"✅ VOICE MATCH ({who}, {result.voice_score:.2f}): routing '{command[:40]}...'")
                self._emit_auth_trace(
                    "allow",
                    "voice_match_authorized",
                    request_id=request_id,
                    command=command,
                    extra={"voice_score": float(result.voice_score or 0.0), "speaker": str(who)},
                )
                self._publish_ai_request(command, request_id, timestamp,
                                         speaker_name=who,
                                         voice_score=result.voice_score,
                                         speaker_role=result.role,
                                         full_text=command)
                return
            
            # Voice didn't match — but check FACE before denying
            if face_is_owner and face_is_recent:
                # Face is owner → accept command, voice is still learning
                logger.info(f"🔓 FACE-VERIFIED owner on camera — accepting despite voice mismatch ({result.voice_score:.2f})")
                self._mark_owner_authenticated()
                self._emit_auth_trace(
                    "allow",
                    "face_verified_owner",
                    request_id=request_id,
                    command=command,
                    extra={"voice_score": float(result.voice_score or 0.0)},
                )
                self._publish_ai_request(command, request_id, timestamp,
                                         speaker_name="Isaiah Wright",
                                         voice_score=result.voice_score,
                                         speaker_role="owner",
                                         full_text=command)
                return

            # If owner was just authenticated, allow short-session continuity even if
            # this specific verification sample is weak (camera occlusion/noise bursts).
            owner_recently_authenticated = self._owner_auth_window_active()
            if owner_recently_authenticated:
                logger.info(
                    "🔓 Recent owner auth window active - accepting command despite transient verification mismatch"
                )
                self._emit_auth_trace(
                    "allow",
                    "recent_owner_auth_window",
                    request_id=request_id,
                    command=command,
                    extra={"voice_score": float(result.voice_score or 0.0)},
                )
                self._publish_ai_request(
                    command,
                    request_id,
                    timestamp,
                    speaker_name="Isaiah Wright",
                    voice_score=result.voice_score,
                    speaker_role="owner",
                    full_text=command,
                )
                return
            
            # Enrollment/household onboarding intents must never lock out owner workflow.
            _family_enroll_intent = self._is_family_enrollment_intent(command)
            if _family_enroll_intent:
                logger.info("🔓 Enrollment intent detected — bypassing face mismatch deny")
                self._emit_auth_trace("allow", "family_enrollment_bypass", request_id=request_id, command=command)
                self._publish_ai_request(command, request_id, timestamp, full_text=command)
                return

            # Owner soft-match fallback (dark-room / face unavailable):
            # when no recent face exists, allow likely-owner voice and keep learning.
            if (not face_is_recent and result.user_id == "owner_primary"
                    and float(result.voice_score) >= float(self._owner_soft_match_threshold)):
                logger.info(
                    f"🔓 OWNER SOFT-MATCH accepted without recent face (score={result.voice_score:.2f})"
                )
                self._mark_owner_authenticated()
                self._emit_auth_trace(
                    "allow",
                    "owner_soft_match_without_face",
                    request_id=request_id,
                    command=command,
                    extra={"voice_score": float(result.voice_score or 0.0)},
                )
                self._publish_ai_request(command, request_id, timestamp,
                                         speaker_name="Isaiah Wright",
                                         voice_score=result.voice_score,
                                         speaker_role="owner",
                                         full_text=command)
                return

            # No face data or face too old:
            # enter restricted mode and require re-authentication. Enrollment and
            # identity intents are already bypassed earlier to prevent lockout.
            if not face_is_recent:
                logger.info(f"🔒 Restricted mode (no recent face + unknown voice): denied '{command[:40]}...'")
                self._emit_auth_trace(
                    "restricted",
                    "no_recent_face_unknown_voice",
                    request_id=request_id,
                    command=command,
                    extra={"voice_score": float(result.voice_score or 0.0)},
                )
                if self.event_bus:
                    self.event_bus.publish('voice.input.recognized', {
                        'text': command,
                        'full_text': command,
                        'request_id': request_id,
                        'source': 'always_on_voice',
                        'already_routed': True,
                        'timestamp': time.time()
                    })
                    self.event_bus.publish('identity.command.rejected', {
                        'text': command,
                        'user_name': "Unknown person",
                        'voice_score': result.voice_score,
                        'role': result.role,
                        'message': 'Re-authentication required: no recent trusted face and voice is not authorized',
                        'timestamp': time.time()
                    })
                    self.event_bus.publish('voice.speak', {
                        'text': "Authentication required. Look at the camera and say Kingdom authorize me.",
                        'priority': 'high', 'source': 'always_on_voice'
                    })
                return
            
            # Face is recent AND face is NOT owner → DENY (different person on camera)
            who = result.user_name or "Unknown person"
            self._emit_auth_trace(
                "deny",
                "face_mismatch_unknown_voice",
                request_id=request_id,
                command=command,
                extra={"voice_score": float(result.voice_score or 0.0), "speaker": str(who)},
            )
            logger.info(f"🔒 FACE MISMATCH + voice unknown ({who}, {result.voice_score:.2f}): '{command[:40]}...' — DENIED")
            if self.event_bus:
                # Always transcribe denied speech to chat so user sees what was heard.
                self.event_bus.publish('voice.input.recognized', {
                    'text': command,
                    'full_text': command,
                    'request_id': request_id,
                    'source': 'always_on_voice',
                    'already_routed': True,
                    'timestamp': time.time()
                })
                self.event_bus.publish('identity.command.rejected', {
                    'text': command,
                    'user_name': who,
                    'voice_score': result.voice_score,
                    'role': result.role,
                    'message': 'Face does not match owner',
                    'timestamp': time.time()
                })
                # Startup calibration guard:
                # do not speak hard denial during initial warmup window,
                # which can fire before the owner can speak.
                if in_grace:
                    logger.info("🔕 Suppressing spoken access denial during startup grace window")
                else:
                    self.event_bus.publish('voice.speak', {
                        'text': "Access denied until re-authentication. Look at the camera and say Kingdom authorize me.",
                        'priority': 'low', 'source': 'always_on_voice'
                    })
        except Exception as e:
            logger.error(f"Speaker verification error: {e} — accepting command as fallback")
            self._publish_ai_request(command, request_id, timestamp, full_text=command)
    
    def _check_auto_enrollment(self, text_lower: str, current_time: float):
        """Auto-detect name introduction and build biometric profile automatically.
        
        SOTA 2026: When user says "I'm Isaiah", "my name is Isaiah", "this is Isaiah",
        "hey it's Isaiah", "call me Isaiah", etc., the system automatically:
        1. Extracts the user's name
        2. Enrolls their voice embedding from cached audio
        3. Enrolls their face from the latest webcam frame
        4. Updates the owner profile name
        
        Also passively enrolls voice on every interaction when < 10 samples,
        to continuously improve the profile without explicit enrollment.
        """
        if not self._identity_engine:
            return
        
        import re
        
        # Name introduction patterns
        intro_patterns = [
            r"(?:i'?m|i am|this is|it'?s|hey it'?s|call me|they call me|name is|name'?s)\s+([a-z]+)",
            r"(?:my name is|my name'?s)\s+([a-z]+(?:\s+[a-z]+)?)",
        ]
        
        detected_name = None
        for pattern in intro_patterns:
            match = re.search(pattern, text_lower)
            if match:
                name_candidate = match.group(1).strip()
                # Filter out common false positives
                false_positives = {'the', 'a', 'an', 'your', 'here', 'there', 'that', 'this',
                                   'it', 'not', 'so', 'just', 'going', 'gonna', 'doing',
                                   'fine', 'good', 'okay', 'ok', 'sure', 'ready', 'done',
                                   'sorry', 'happy', 'back', 'home', 'looking', 'trying'}
                if name_candidate and name_candidate not in false_positives and len(name_candidate) >= 2:
                    detected_name = name_candidate.title()
                    break
        
        if detected_name:
            logger.info(f"🆔 AUTO-ENROLLMENT: Detected name introduction — '{detected_name}'")
            self._auto_enroll_biometrics(detected_name)
            return
        
        # Passive enrollment: on every voice interaction, if owner has < 10 voice samples,
        # silently add the current audio as another sample (continuous profile improvement)
        status = self._identity_engine.get_status()
        voice_samples = status.get('owner_voice_samples', 0)
        if 0 < voice_samples < 10:
            audio = getattr(self, '_last_audio_chunk', None)
            if audio is not None and len(audio) > 16000:  # At least 1 second
                owner_id = self._identity_engine._owner_id or 'owner_primary'
                try:
                    self._identity_engine.enroll_voice_sample(owner_id, audio, 16000)
                    logger.debug(f"🎤 Passive voice enrollment (sample {voice_samples + 1})")
                except Exception:
                    pass
    
    def _auto_enroll_biometrics(self, name: str):
        """Auto-enroll voice + face when name introduction detected.
        
        Runs in background thread to avoid blocking audio processing.
        """
        import threading
        
        def _do_auto_enroll():
            try:
                engine = self._identity_engine
                if not engine:
                    return
                
                # Create/update owner profile with detected name
                owner_id = engine.enroll_owner(name)
                profile = engine.profiles.get(owner_id)
                if profile:
                    profile.name = name
                    engine._save_profiles()
                
                enrolled_voice = False
                enrolled_face = False
                
                # 1. Enroll voice from cached audio
                audio = getattr(self, '_last_audio_chunk', None)
                if audio is not None and len(audio) > 8000:  # At least 0.5 seconds
                    enrolled_voice = engine.enroll_voice_sample(owner_id, audio, 16000)
                
                # 2. Enroll face from latest webcam frame
                with engine._latest_frame_lock:
                    frame = engine._latest_frame
                    frame_age = time.time() - engine._latest_frame_time
                if frame is not None and frame_age < 5.0:  # Frame less than 5 seconds old
                    enrolled_face = engine.enroll_face_sample(owner_id, frame)
                
                # Report results
                status = engine.get_status()
                v_count = status.get('owner_voice_samples', 0)
                f_count = status.get('owner_face_samples', 0)
                
                parts = []
                if enrolled_voice:
                    parts.append(f"voice ({v_count} samples)")
                if enrolled_face:
                    parts.append(f"face ({f_count} samples)")
                
                if parts:
                    logger.info(f"✅ AUTO-ENROLLED {name}: {', '.join(parts)}")
                    if self.event_bus:
                        msg = f"Hello {name}. I've started learning your identity."
                        if enrolled_voice:
                            msg += f" Voice profile: {v_count} samples."
                        if enrolled_face:
                            msg += f" Face profile: {f_count} samples."
                        if v_count < 3 or f_count < 5:
                            msg += " I'll keep learning as we talk."
                        self.event_bus.publish('voice.speak', {
                            'text': msg,
                            'priority': 'high',
                            'source': 'always_on_voice'
                        })
                        self.event_bus.publish('identity.owner.enrolled', {
                            'name': name,
                            'voice_samples': v_count,
                            'face_samples': f_count,
                            'timestamp': time.time()
                        })
                else:
                    logger.warning(f"⚠️ Auto-enrollment for {name}: no data captured (need mic + camera)")
                    
            except Exception as e:
                logger.error(f"Auto-enrollment error: {e}")
        
        threading.Thread(target=_do_auto_enroll, daemon=True, name="AutoEnroll").start()
    
    def _handle_identity_verify(self, data: dict = None):
        """Handle 'who am I' / 'identify me' command via SpeechBrain ECAPA-TDNN.
        
        SOTA 2026: Uses last cached audio to verify speaker identity and respond.
        """
        try:
            if not self._identity_engine:
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': "Identity engine is not loaded. Cannot verify your identity.",
                        'priority': 'high', 'source': 'always_on_voice'
                    })
                return
            
            audio_data = getattr(self, '_last_audio_chunk', None)
            if audio_data is None:
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': "No recent audio available for speaker verification. Please speak first.",
                        'priority': 'high', 'source': 'always_on_voice'
                    })
                return
            
            result = self._identity_engine.verify_voice(audio_data, sample_rate=16000)
            status = self._identity_engine.get_status()
            
            if result.is_authorized:
                who = result.user_name or "Owner"
                msg = f"You are {who}. Voice confidence: {result.voice_score:.0%}. Role: {result.role or 'owner'}."
            else:
                msg = f"I don't recognize your voice. Confidence: {result.voice_score:.0%}. Say 'enroll my voice' to register."
            
            logger.info(f"🆔 Identity verify: {msg}")
            if self.event_bus:
                self.event_bus.publish('voice.speak', {
                    'text': msg, 'priority': 'high', 'source': 'always_on_voice'
                })
                self.event_bus.publish('identity.verify.result', {
                    'user_name': result.user_name,
                    'voice_score': result.voice_score,
                    'role': result.role,
                    'is_authorized': result.is_authorized,
                    'voice_samples': status.get('owner_voice_samples', 0),
                    'face_samples': status.get('owner_face_samples', 0),
                    'speechbrain_active': status.get('speechbrain_available', False),
                })
        except Exception as e:
            logger.error(f"Identity verify error: {e}")
    
    def _handle_identity_status(self, data: dict = None):
        """Handle 'identity status' command — report SpeechBrain + facenet-pytorch status."""
        try:
            if not self._identity_engine:
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': "Identity engine is not loaded.",
                        'priority': 'high', 'source': 'always_on_voice'
                    })
                return
            
            status = self._identity_engine.get_status()
            sb = "active" if status.get('speechbrain_available') else "not available"
            fn = "active" if status.get('facenet_available') else "not available"
            voice_n = status.get('owner_voice_samples', 0)
            face_n = status.get('owner_face_samples', 0)
            profiles = status.get('profiles_count', 0)
            
            msg = (f"Identity status: SpeechBrain ECAPA is {sb}. "
                   f"Facenet-pytorch is {fn}. "
                   f"{voice_n} voice samples, {face_n} face samples, {profiles} profiles enrolled.")
            
            logger.info(f"🆔 {msg}")
            if self.event_bus:
                self.event_bus.publish('voice.speak', {
                    'text': msg, 'priority': 'high', 'source': 'always_on_voice'
                })
                self.event_bus.publish('identity.status.result', status)
        except Exception as e:
            logger.error(f"Identity status error: {e}")
    
    def _handle_voice_enrollment(self):
        """Handle 'Kingdom enroll voice' command — collect voice samples for speaker verification.
        
        SOTA 2026: Records 5 seconds of speech, extracts ECAPA-TDNN embedding,
        and enrolls it in the UserIdentityEngine. Needs 3+ samples for reliable verification.
        """
        if not self._identity_engine:
            logger.warning("UserIdentityEngine not available — cannot enroll voice")
            if self.event_bus:
                self.event_bus.publish('voice.speak', {
                    'text': "Voice enrollment is not available. The identity engine is not loaded.",
                    'priority': 'high', 'source': 'always_on_voice'
                })
            return
        
        import threading
        def _enroll_bg():
            try:
                logger.info("🎤 VOICE ENROLLMENT: Recording 5 seconds of speech...")
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': "Starting voice enrollment. Please speak naturally for five seconds.",
                        'priority': 'high', 'source': 'always_on_voice'
                    })

                # Wait for TTS to finish before recording (in background thread only).
                time.sleep(4)

                # Collect audio for 5 seconds from the audio queue
                chunks = []
                start = time.time()
                while time.time() - start < 5.0:
                    try:
                        data = self._audio_queue.get(timeout=0.5)
                        raw = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                        chunks.append(raw)
                    except Exception:
                        continue
                
                if not chunks:
                    logger.error("No audio captured for enrollment")
                    return
                
                audio = np.concatenate(chunks)
                owner_id = self._identity_engine.enroll_owner("Isaiah Wright")
                success = self._identity_engine.enroll_voice_sample(owner_id, audio, 16000)
                
                if success:
                    status = self._identity_engine.get_status()
                    count = status.get('owner_voice_samples', 0)
                    msg = f"Voice sample enrolled successfully. You now have {count} voice samples."
                    if count < 3:
                        msg += f" Please enroll {3 - count} more samples for reliable verification."
                    else:
                        msg += " Speaker verification is now active."
                    logger.info(f"✅ Voice enrollment success ({count} samples)")
                else:
                    msg = "Voice enrollment failed. Please try again in a quiet environment."
                    logger.warning("❌ Voice enrollment failed")
                
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': msg, 'priority': 'high', 'source': 'always_on_voice'
                    })
            except Exception as e:
                logger.error(f"Voice enrollment error: {e}")
        
        threading.Thread(target=_enroll_bg, daemon=True, name="VoiceEnroll").start()
    
    def _handle_face_enrollment(self):
        """Handle 'Kingdom enroll face' command — capture face from webcam for recognition.
        
        SOTA 2026: Grabs the latest webcam frame and enrolls it via InsightFace ArcFace.
        Needs 5+ samples from different angles for reliable verification.
        """
        if not self._identity_engine:
            logger.warning("UserIdentityEngine not available — cannot enroll face")
            if self.event_bus:
                self.event_bus.publish('voice.speak', {
                    'text': "Face enrollment is not available. The identity engine is not loaded.",
                    'priority': 'high', 'source': 'always_on_voice'
                })
            return
        
        logger.info("📸 FACE ENROLLMENT: Capturing face from webcam...")
        if self.event_bus:
            self.event_bus.publish('voice.speak', {
                'text': "Starting face enrollment. Please look at the camera.",
                'priority': 'high', 'source': 'always_on_voice'
            })
        
        # Request a frame from vision pipeline
        import threading
        def _enroll_face_bg():
            try:
                time.sleep(3)  # Wait for TTS + user to look at camera
                
                # Try to get frame from the identity engine's cached face result
                # or request one via event bus
                if self.event_bus:
                    # Publish request for a face enrollment frame
                    self.event_bus.publish('vision.face.enroll.request', {
                        'user_id': 'owner_primary',
                        'timestamp': time.time()
                    })
                
                # Wait a moment for frame to be processed
                time.sleep(2)
                
                # Check if face was enrolled via the event
                status = self._identity_engine.get_status()
                count = status.get('owner_face_samples', 0)
                
                if count > 0:
                    msg = f"Face sample captured. You now have {count} face samples."
                    if count < 5:
                        msg += f" Please enroll {5 - count} more from different angles."
                    else:
                        msg += " Face recognition is now active."
                    logger.info(f"✅ Face enrollment ({count} samples)")
                else:
                    msg = "Face enrollment failed. Make sure your camera is on and your face is visible."
                    logger.warning("❌ Face enrollment — no samples captured")
                
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': msg, 'priority': 'high', 'source': 'always_on_voice'
                    })
            except Exception as e:
                logger.error(f"Face enrollment error: {e}")
        
        threading.Thread(target=_enroll_face_bg, daemon=True, name="FaceEnroll").start()

    def _ensure_default_family_profiles(self):
        """Ensure living-trust family profiles exist with safe defaults."""
        if not self._identity_engine:
            return
        defaults = [
            ("Aryah Wright", "daughter"),
            ("Amani Wright", "daughter"),
            ("Alaia Wright", "daughter"),
        ]
        try:
            for name, relationship in defaults:
                self._identity_engine.ensure_family_member(name, relationship=relationship)
            logger.info("👨‍👩‍👧‍👧 Living trust defaults loaded for family profiles")
        except Exception as e:
            logger.warning(f"Could not ensure default family profiles: {e}")

    def _check_all_praise_trigger(self, normalized: str, command_text: str, current_time: float) -> bool:
        """ALL PRAISE TO THE MOST HIGH — family enrollment. Owner confirms. Emergency exception."""
        _all_praise = (
            "all praise to the most high" in normalized or
            "all praise the most high" in normalized or
            "praise the most high" in normalized
        )
        if self._pending_family_enrollment:
            pending = self._pending_family_enrollment
            if current_time - pending.get("timestamp", 0) > self._pending_enrollment_timeout:
                self._pending_family_enrollment = None
                return False
            if pending.get("awaiting") == "name":
                name = self._extract_name_from_response(command_text)
                if name:
                    self._pending_family_enrollment = {"name": name, "awaiting": "owner_confirm", "timestamp": current_time}
                    if self._is_emergency_contact(name):
                        self._handle_family_member_introduced(name, "emergency_contact")
                        self._pending_family_enrollment = None
                        if self.event_bus:
                            self.event_bus.publish('voice.speak', {
                                'text': f"Emergency contact {name} enrolled.",
                                'priority': 'high', 'source': 'always_on_voice'
                            })
                        return True
                    if self.event_bus:
                        self.event_bus.publish('voice.speak', {
                            'text': f"Owner, please confirm: {name} is here. Say 'Kingdom enroll {name}' to enroll, or 'Kingdom do not enroll {name}' for basic access only when you are absent.",
                            'priority': 'high', 'source': 'always_on_voice'
                        })
                    return True
        if _all_praise:
            self._pending_family_enrollment = {"awaiting": "name", "timestamp": current_time}
            if self.event_bus:
                self.event_bus.publish('voice.speak', {
                    'text': "Who are you?",
                    'priority': 'high', 'source': 'always_on_voice'
                })
            return True
        return False

    def _extract_name_from_response(self, text: str) -> Optional[str]:
        """Extract name from 'I am X', 'I'm X', 'My name is X', or plain 'X Y'."""
        t = text.strip()
        for prefix in ("i am ", "i'm ", "my name is ", "this is ", "it's ", "call me "):
            if t.lower().startswith(prefix):
                return t[len(prefix):].strip().title()
        words = t.split()
        if 1 <= len(words) <= 4 and all(w.replace("-", "").isalpha() for w in words):
            return t.title()
        return None

    def _is_seeking_owner_location(self, command: str) -> bool:
        """Detect queries for owner location — allow basic when owner absent."""
        n = self._normalize_spoken_command(command) if hasattr(self, '_normalize_spoken_command') else command.lower()
        return any(k in n for k in (
            "where is", "find ", "locate ", "where's the owner",
            "where is isaiah", "find isaiah", "where is the owner",
            "owner location", "seek owner", "looking for owner",
        ))

    def _allow_basic_when_owner_absent(self, command: str, full_text: str) -> bool:
        """Allow basic (non-financial) when owner absent for guests or seeking-owner."""
        if self._is_seeking_owner_location(command):
            return True
        if "all praise" in (self._normalize_spoken_command(command) if hasattr(self, '_normalize_spoken_command') else command.lower()):
            return True
        if self._is_financial_intent(command):
            return False
        # Default to allow non-financial voice requests when owner presence is unknown.
        # This preserves command usability while still blocking financial operations.
        return True

    def _is_emergency_contact(self, name: str) -> bool:
        """Check if name is in emergency contacts (emergency exception — auto-enroll)."""
        try:
            from core.security.contact_manager import ContactManager
            cm = ContactManager.get_instance()
            c = cm.find_contact_by_name(name)
            return c is not None and c.get("role") in ("emergency_contact", "both")
        except Exception:
            return False

    def _handle_owner_confirm_enroll(self, name: str):
        """Owner confirms enrollment: 'Kingdom enroll [Name]'."""
        if not self._identity_engine:
            return
        if not self._is_owner_present_for_voice():
            if self.event_bus:
                self.event_bus.publish('voice.speak', {
                    'text': "Only the owner can confirm enrollment.",
                    'priority': 'high', 'source': 'always_on_voice'
                })
            return
        self._pending_family_enrollment = None
        self._handle_family_member_introduced(name, "family")

    def _handle_do_not_enroll(self, name: str):
        """Owner denies enrollment: basic (non-financial) only when owner absent."""
        if not self._identity_engine:
            return
        if not self._is_owner_present_for_voice():
            if self.event_bus:
                self.event_bus.publish('voice.speak', {
                    'text': "Only the owner can deny enrollment.",
                    'priority': 'high', 'source': 'always_on_voice'
                })
            return
        self._pending_family_enrollment = None
        try:
            self._identity_engine.ensure_guest_basic_only(name)
            msg = f"{name} will have basic access only when you are absent. No financial access."
        except Exception as e:
            msg = f"Could not set basic-only access for {name}."
            logger.warning("do_not_enroll failed: %s", e)
        if self.event_bus:
            self.event_bus.publish('voice.speak', {
                'text': msg, 'priority': 'high', 'source': 'always_on_voice'
            })

    def _extract_named_family_member(self, command_text: str, relationship: str) -> Optional[Dict[str, str]]:
        """Extract 'First Last' from spoken family introduction commands."""
        text = " ".join(command_text.strip().split())
        rel_map = {
            "daughter": r"(?:daughter|daughters)",
            "son": r"(?:son|sons)",
            "child": r"(?:child|children|kid|kids)",
            "father": r"(?:father|dad)",
        }
        rel_group = rel_map.get(relationship, re.escape(relationship))
        pattern = re.compile(
            rf"(?:introduce|enroll|register)\s+(?:you\s+to\s+)?(?:my\s+)?{rel_group}\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){{0,2}})",
            re.IGNORECASE,
        )
        m = pattern.search(text)
        if not m:
            return None
        raw_name = " ".join(m.group(1).split())
        if not raw_name:
            return None
        return {"name": raw_name.title(), "relationship": relationship}

    def _handle_family_member_introduced(self, name: str, relationship: str):
        """Owner-introduced family member onboarding (normal/living operation)."""
        if not self._identity_engine:
            return
        try:
            existing = None
            for profile in self._identity_engine.profiles.values():
                if profile.name.lower() == name.lower():
                    existing = profile
                    break
            was_created = existing is None

            # Living policy:
            # - authorize non-financial system usage
            # - keep financial access disabled until explicit owner grant
            user_id = self._identity_engine.ensure_family_member(name, relationship=relationship)
            profile = self._identity_engine.profiles.get(user_id)
            display_name = (profile.name if profile else name).strip()
            display_relationship = (profile.relationship if profile and profile.relationship else relationship).strip()
            action_word = "Created" if was_created else "Updated"
            msg = (
                f"{action_word} {display_relationship} profile: {display_name}. "
                f"Profile ID: {user_id}. Financial access remains disabled until you explicitly grant it."
            )
            logger.info(
                f"✅ Family member ensured: action={action_word.lower()} name={display_name} "
                f"relationship={display_relationship} id={user_id}"
            )
        except Exception as e:
            msg = f"I couldn't register {name} right now."
            logger.error(f"Family introduction failed for {name}: {e}")
        if self.event_bus:
            self.event_bus.publish('voice.speak', {
                'text': msg, 'priority': 'high', 'source': 'always_on_voice'
            })
    
    def _handle_grant_access(self, target_name: str):
        """Owner grants system control access to another person by name.
        
        SOTA 2026: Only the verified owner can grant access.
        The target user gets a profile and can issue commands.
        """
        if not self._identity_engine:
            return
        
        # Verify the speaker IS the owner before allowing grant
        audio = getattr(self, '_last_audio_chunk', None)
        if audio is not None and len(audio) > 8000:
            result = self._identity_engine.verify_voice(audio, 16000)
            if not result.is_owner:
                logger.warning(f"🔒 Non-owner tried to grant access to '{target_name}' — DENIED")
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': "Only the owner can grant system access.",
                        'priority': 'high', 'source': 'always_on_voice'
                    })
                return
        
        user_id = self._identity_engine.grant_access(target_name)
        if user_id:
            msg = f"Access granted to {target_name}. They can now control Kingdom AI."
            logger.info(f"✅ Owner granted access to {target_name} (id={user_id})")
        else:
            msg = f"Failed to grant access to {target_name}."
        
        if self.event_bus:
            self.event_bus.publish('voice.speak', {
                'text': msg, 'priority': 'high', 'source': 'always_on_voice'
            })

    def _handle_grant_financial_access(self, target_name: str):
        """Owner grants financial access (trading/wallet execution)."""
        if not self._identity_engine:
            return

        audio = getattr(self, '_last_audio_chunk', None)
        if audio is not None and len(audio) > 8000:
            result = self._identity_engine.verify_voice(audio, 16000)
            if not result.is_owner:
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': "Only the owner can grant financial access.",
                        'priority': 'high', 'source': 'always_on_voice'
                    })
                return

        granted = self._identity_engine.set_financial_access(target_name, True)
        msg = (
            f"Financial access granted to {target_name}."
            if granted else f"No user named {target_name} found for financial access."
        )
        if self.event_bus:
            self.event_bus.publish('voice.speak', {
                'text': msg, 'priority': 'high', 'source': 'always_on_voice'
            })

    def _handle_revoke_financial_access(self, target_name: str):
        """Owner revokes financial access (trading/wallet execution)."""
        if not self._identity_engine:
            return

        audio = getattr(self, '_last_audio_chunk', None)
        if audio is not None and len(audio) > 8000:
            result = self._identity_engine.verify_voice(audio, 16000)
            if not result.is_owner:
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': "Only the owner can revoke financial access.",
                        'priority': 'high', 'source': 'always_on_voice'
                    })
                return

        revoked = self._identity_engine.set_financial_access(target_name, False)
        msg = (
            f"Financial access revoked from {target_name}."
            if revoked else f"No user named {target_name} found for financial access."
        )
        if self.event_bus:
            self.event_bus.publish('voice.speak', {
                'text': msg, 'priority': 'high', 'source': 'always_on_voice'
            })
    
    def _handle_revoke_access(self, target_name: str):
        """Owner revokes system control access from a person.
        
        SOTA 2026: Only the verified owner can revoke access.
        """
        if not self._identity_engine:
            return
        
        # Verify the speaker IS the owner
        audio = getattr(self, '_last_audio_chunk', None)
        if audio is not None and len(audio) > 8000:
            result = self._identity_engine.verify_voice(audio, 16000)
            if not result.is_owner:
                logger.warning(f"🔒 Non-owner tried to revoke access from '{target_name}' — DENIED")
                if self.event_bus:
                    self.event_bus.publish('voice.speak', {
                        'text': "Only the owner can revoke system access.",
                        'priority': 'high', 'source': 'always_on_voice'
                    })
                return
        
        success = self._identity_engine.revoke_access(target_name)
        if success:
            msg = f"Access revoked from {target_name}. They can no longer control Kingdom AI."
        else:
            msg = f"No user named {target_name} found in the system."
        
        if self.event_bus:
            self.event_bus.publish('voice.speak', {
                'text': msg, 'priority': 'high', 'source': 'always_on_voice'
            })
    
    def _handle_list_access(self):
        """List all users with system access."""
        if not self._identity_engine:
            return
        
        users = self._identity_engine.list_authorized_users()
        if not users:
            msg = "No users have system access."
        else:
            names = [u['name'] for u in users]
            if len(names) == 1:
                msg = f"Only {names[0]} has system access."
            else:
                msg = f"The following users have system access: {', '.join(names)}."
        
        if self.event_bus:
            self.event_bus.publish('voice.speak', {
                'text': msg, 'priority': 'high', 'source': 'always_on_voice'
            })

    def _is_financial_intent(self, command: str) -> bool:
        """Detect commands that can execute financial/trading/wallet actions.

        ROOT FIX: Conversational questions that mention trading terms
        (e.g. "are you ready to start trading?") are NOT financial intents.
        Only imperative commands that would execute an action are flagged.
        Previous behavior: "trade" substring-matched inside "trading"
        in conversational questions, blocking the startup grace fallback
        and leaving the user with no AI response.
        """
        cmd = (command or "").strip().lower()
        if not cmd:
            return False

        # Questions are never execution intents — they cannot trigger trades.
        _question_starters = (
            "are ", "is ", "do ", "does ", "what ", "how ", "why ", "when ",
            "where ", "can ", "could ", "would ", "should ", "will ",
            "who ", "which ", "tell me", "explain",
        )
        if any(cmd.startswith(q) for q in _question_starters) or cmd.rstrip().endswith("?"):
            return False

        keywords = (
            "trade", "buy", "sell", "swap", "order", "market order", "limit order",
            "execute trade", "place order", "cancel order", "portfolio rebalance",
            "withdraw", "send crypto", "transfer funds", "wallet transfer",
            "connect exchange", "autotrade", "auto trade", "start trading",
            "run trading", "liquidate", "leverage", "futures",
        )
        return any(k in cmd for k in keywords)
    
    def _publish_ai_request(self, command: str, request_id: str, timestamp: float,
                            speaker_name: str = None, voice_score: float = None,
                            speaker_role: str = None, full_text: str = None):
        """Publish ai.request event. Extracted for reuse by _verify_then_route.
        
        SOTA 2026: Includes speaker identity context when SpeechBrain verification is active.
        """
        if self.event_bus:
            # Ensure every routed voice command is transcribed in chat UI.
            self.event_bus.publish('voice.input.recognized', {
                'text': command,
                'full_text': full_text or command,
                'request_id': request_id,
                'source': 'always_on_voice',
                'already_routed': True,
                'timestamp': timestamp
            })
            # Wire voice.recognition for ThothQtWidget subscribers
            self.event_bus.publish('voice.recognition', {
                'text': command,
                'full_text': full_text or command,
                'request_id': request_id,
                'source': 'always_on_voice',
                'timestamp': timestamp,
            })
            # Wire voice.command for ThothQtWidget command handlers
            self.event_bus.publish('voice.command', {
                'text': command,
                'full_text': full_text or command,
                'request_id': request_id,
                'source': 'always_on_voice',
                'timestamp': timestamp,
            })
            # Compatibility event for widgets listening on legacy transcription topic.
            self.event_bus.publish('voice.transcription', {
                'text': command,
                'full_text': full_text or command,
                'request_id': request_id,
                'source': 'always_on_voice',
                'timestamp': timestamp,
            })
            payload = {
                'prompt': command,
                'message': command,
                'request_id': request_id,
                'source_tab': 'voice',
                'source': 'always_on_voice',
                'sender': 'user',
                'model': self._get_voice_model(),
                'speak': True,
                'timestamp': timestamp
            }
            # SOTA 2026: Attach speaker identity from SpeechBrain ECAPA-TDNN verification
            if speaker_name:
                payload['speaker_name'] = speaker_name
            if voice_score is not None:
                payload['voice_score'] = voice_score
            if speaker_role:
                payload['speaker_role'] = speaker_role
            vision_payload = self._build_voice_vision_payload(command)
            if vision_payload:
                payload.update(vision_payload)

            vision_intent = self._detect_vision_user_intent(command)
            if vision_intent == "creative":
                self.event_bus.publish("vision.action.creative.active_frame", {
                    "prompt": command,
                    "source": "always_on_voice",
                    "vision_source": payload.get("vision_source", "camera"),
                })
                return
            if vision_intent == "research":
                self.event_bus.publish("vision.action.research.active_frame", {
                    "prompt": command,
                    "source": "always_on_voice",
                    "vision_source": payload.get("vision_source", "camera"),
                })
                return

            self.event_bus.publish('ai.request', payload)
    
    def set_wake_callback(self, callback: Callable[[str, str], None]):
        """Set callback for wake word detection.
        
        Args:
            callback: Function(wake_word, full_text)
        """
        self._wake_detected_callback = callback
    
    def set_command_callback(self, callback: Callable[[str, str, str], None]):
        """Set callback for command recognition.
        
        Args:
            callback: Function(command, full_text, request_id)
        """
        self._command_recognized_callback = callback
    
    @property
    def state(self) -> VoiceState:
        """Get current voice state."""
        with self._state_lock:
            return self._state
    
    @property
    def is_running(self) -> bool:
        """Check if voice detection is running."""
        return bool(self._should_run and self._listen_thread and self._listen_thread.is_alive())
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of always-on voice system.
        
        Returns:
            Status dictionary
        """
        return {
            'running': self.is_running,
            'state': self.state.value,
            'wake_words': self.config.wake_words,
            'is_ai_speaking': self._is_ai_speaking,
            'has_vosk': self._recognizer is not None,
            'has_sr': hasattr(self, '_sr_recognizer'),
            'audio_backend': self.config.audio_backend,
            'audio_device': self.config.audio_device,
            'pulse_source': self.config.pulse_source,
        }


# ============================================================
# Singleton accessor
# ============================================================

_always_on_voice: Optional[AlwaysOnVoice] = None


def get_always_on_voice(event_bus=None) -> AlwaysOnVoice:
    """Get the singleton AlwaysOnVoice instance.
    
    Args:
        event_bus: Optional event bus to use
        
    Returns:
        AlwaysOnVoice instance
    """
    global _always_on_voice
    
    if _always_on_voice is None:
        _always_on_voice = AlwaysOnVoice(event_bus)
    elif event_bus and not _always_on_voice.event_bus:
        _always_on_voice.event_bus = event_bus
        _always_on_voice._subscribe_to_events()
    
    return _always_on_voice


def start_always_on_voice(event_bus=None) -> bool:
    """Start always-on voice detection.
    
    Args:
        event_bus: Optional event bus
        
    Returns:
        True if started successfully
    """
    voice = get_always_on_voice(event_bus)
    return voice.start()


def stop_always_on_voice():
    """Stop always-on voice detection."""
    global _always_on_voice
    
    if _always_on_voice:
        _always_on_voice.stop()
