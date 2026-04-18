"""
SOTA 2026 User Identity Engine - Multi-Modal Biometric Recognition

Provides real-time user identification using:
1. Voice Biometrics: SpeechBrain ECAPA-TDNN (192-dim speaker embeddings, cosine similarity)
2. Face Biometrics: InsightFace ArcFace (512-dim face embeddings, cosine similarity)
3. Voice Activity Detection: Silero VAD (distinguish speech from noise)
4. Echo Rejection: Spectral fingerprint of AI's own TTS output to ignore self-voice

Architecture:
- Enrollment: Collect voice samples + face images → compute mean embeddings → persist
- Verification: Compare incoming embedding vs stored mean → cosine similarity > threshold
- Fusion: Weighted combination of voice + face confidence scores
- Echo Gate: Compare incoming audio spectrogram against last TTS output fingerprint

Integration:
- AlwaysOnVoice: VAD filters noise → speaker verification gates commands → echo rejection
- Vision Pipeline: Face detection on webcam frames → face verification → user ID broadcast
- EventBus: Publishes identity.verified / identity.unknown / identity.echo_rejected

Creator: Isaiah Wright (primary owner)
"""

import os
import sys
import json
import time
import logging
import threading
import hashlib
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger("KingdomAI.UserIdentity")

# ─── Optional SOTA imports with availability flags ───────────────────────────

# Suppress TF/protobuf warnings that conflict with SpeechBrain imports
import os as _os
_os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
# CRITICAL: Force pure Python protobuf to avoid C++ DType conflict with TensorFlow
_os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')
import warnings as _warnings
_warnings.filterwarnings('ignore', message='.*SerializedDType.*')
_warnings.filterwarnings('ignore', message='.*DType.*proto.*')
_warnings.filterwarnings('ignore', message='.*numpy.*ABI.*')
_warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf')

# 1. SpeechBrain ECAPA-TDNN for speaker embeddings
HAS_SPEECHBRAIN = False
_speaker_model = None
try:
    from speechbrain.inference.speaker import EncoderClassifier
    HAS_SPEECHBRAIN = True
except Exception:
    EncoderClassifier = None

# 2. Face embeddings: facenet-pytorch (pure PyTorch — no TensorFlow/protobuf conflicts)
HAS_FACENET = False
_facenet_model = None
_mtcnn_detector = None
try:
    from facenet_pytorch import InceptionResnetV1, MTCNN
    HAS_FACENET = True
except Exception:
    InceptionResnetV1 = None
    MTCNN = None

# 3. Silero VAD for voice activity detection
HAS_SILERO_VAD = False
_vad_model = None
try:
    import torch
    HAS_TORCH = True
except Exception:
    HAS_TORCH = False
    torch = None

# 4. OpenCV for face processing
try:
    import cv2
    HAS_OPENCV = True
except Exception:
    HAS_OPENCV = False
    cv2 = None


# ─── Data classes ────────────────────────────────────────────────────────────

@dataclass
class IdentityProfile:
    """Stored biometric profile for a recognized user."""
    user_id: str
    name: str
    role: str = "unknown"  # "owner", "authorized", "unknown"
    is_authorized: bool = False  # Can this user control the system?
    voice_embeddings: List[np.ndarray] = field(default_factory=list)
    voice_mean_embedding: Optional[np.ndarray] = None
    face_embeddings: List[np.ndarray] = field(default_factory=list)
    face_mean_embedding: Optional[np.ndarray] = None
    enrollment_count_voice: int = 0
    enrollment_count_face: int = 0
    created_at: float = 0.0
    last_verified_at: float = 0.0
    last_seen_at: float = 0.0  # When was this person last detected
    authorized_by: Optional[str] = None  # Who granted access (user_id)
    authorized_at: float = 0.0  # When access was granted
    relationship: str = ""  # e.g. daughter, son, spouse
    financial_access: bool = False  # Living-trust runtime permission for trading/wallet actions
    non_financial_access: bool = True  # Runtime permission for non-financial tools

    def recompute_means(self):
        """Recompute mean embeddings from all enrollment samples."""
        if self.voice_embeddings:
            self.voice_mean_embedding = np.mean(
                np.stack(self.voice_embeddings), axis=0
            )
            self.enrollment_count_voice = len(self.voice_embeddings)
        if self.face_embeddings:
            # L2-normalize each before averaging for ArcFace
            normed = [e / (np.linalg.norm(e) + 1e-10) for e in self.face_embeddings]
            mean_emb = np.mean(np.stack(normed), axis=0)
            mean_emb = mean_emb / (np.linalg.norm(mean_emb) + 1e-10)
            self.face_mean_embedding = mean_emb
            self.enrollment_count_face = len(self.face_embeddings)


@dataclass
class VerificationResult:
    """Result of a verification attempt."""
    is_owner: bool
    user_id: Optional[str]
    user_name: Optional[str]
    voice_score: float = 0.0
    face_score: float = 0.0
    fused_score: float = 0.0
    method: str = "none"  # "voice", "face", "fused"
    is_echo: bool = False
    is_speech: bool = True
    is_authorized: bool = False  # Does this person have system control access?
    role: str = "unknown"  # "owner", "authorized", "unknown"
    message: str = ""


# ─── Core Engine ─────────────────────────────────────────────────────────────

class UserIdentityEngine:
    """
    SOTA 2026 multi-modal user identification engine.

    Voice:  SpeechBrain ECAPA-TDNN → 192-dim embedding → cosine similarity
    Face:   facenet-pytorch InceptionResnetV1 → 512-dim embedding → cosine similarity
    VAD:    Silero VAD → speech probability per frame
    Echo:   Spectral fingerprint of last TTS output → reject if match > threshold
    ACL:    Owner-controlled access — only owner + authorized users can control system
    """

    _instance: Optional["UserIdentityEngine"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, event_bus: Any = None, data_dir: str = None):
        if self._initialized:
            if event_bus and not self.event_bus:
                self.event_bus = event_bus
            return

        self.event_bus = event_bus
        self.data_dir = Path(data_dir or "data/user_identity")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ── Profiles ──
        self.profiles: Dict[str, IdentityProfile] = {}
        self._owner_id: Optional[str] = None

        # ── Thresholds ──
        self.voice_threshold = 0.25    # ECAPA-TDNN EER standard — low for few-shot, adapts up with more samples
        self.face_threshold = 0.30     # Low for few-shot enrollment, adapts up
        self.fused_threshold = 0.30    # Weighted fusion threshold — permissive for owner
        self.voice_weight = 0.5        # Weight for voice in fusion
        self.face_weight = 0.5         # Weight for face in fusion
        self.vad_threshold = 0.5       # Silero VAD speech probability threshold
        self.echo_threshold = 0.85     # Spectral correlation for echo detection

        # ── Echo rejection state ──
        self._echo_lock = threading.Lock()
        self._last_tts_spectrogram: Optional[np.ndarray] = None
        self._last_tts_time: float = 0.0
        self._echo_window = 5.0  # Seconds after TTS to check for echo

        # ── Model loading state ──
        self._models_loaded = False
        self._model_load_lock = threading.Lock()

        # ── Current verification cache ──
        self._current_face_result: Optional[VerificationResult] = None
        self._face_result_time: float = 0.0
        self._face_cache_duration = 2.0  # Seconds

        # ── Auto-enrollment: latest webcam frame cache ──
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_frame_time: float = 0.0
        self._latest_frame_lock = threading.Lock()
        
        # ── Rate limit for face verification ──
        self._last_face_verify_time: float = 0.0

        # ── EMA smoothing for confidence scores ──
        self._ema_alpha = 0.4
        self._ema_voice_score: Optional[float] = None
        self._ema_face_score: Optional[float] = None

        # ── Load persisted profiles ──
        self._load_profiles()

        # ── Subscribe to events ──
        if self.event_bus:
            self._subscribe_events()

        self._initialized = True
        logger.info("🆔 UserIdentityEngine initialized — SOTA 2026")
        logger.info(f"   SpeechBrain ECAPA-TDNN: {'✅' if HAS_SPEECHBRAIN else '❌ pip install speechbrain'}")
        _fn_status = '✅' if HAS_FACENET else '❌ pip install facenet-pytorch'
        logger.info(f"   facenet-pytorch:        {_fn_status}")
        logger.info(f"   Silero VAD:             {'✅' if HAS_TORCH else '❌ pip install torch'}")
        logger.info(f"   Profiles loaded:        {len(self.profiles)}")

    # ─── Event wiring ────────────────────────────────────────────────────────

    def _subscribe_events(self):
        sub = getattr(self.event_bus, 'subscribe_sync', None) or self.event_bus.subscribe
        # Echo fingerprinting: capture TTS output audio
        sub('voice.speaking.started', self._on_tts_started)
        sub('voice.tts.audio', self._on_tts_audio)
        # Vision pipeline: face frames (VisionService/VisionStream publish vision.stream.frame)
        sub('vision.stream.frame', self._on_vision_frame)
        # Face enrollment request (from AlwaysOnVoice commands)
        sub('vision.face.enroll.request', self._on_face_enroll_request)
        logger.info("🔗 UserIdentity subscribed to voice + vision events")

    def _on_tts_started(self, data: Any):
        """Mark that TTS is about to play — prepare echo window."""
        with self._echo_lock:
            self._last_tts_time = time.time()

    def _on_tts_audio(self, data: Any):
        """Receive TTS audio waveform and compute spectral fingerprint for echo rejection."""
        try:
            audio = data.get('audio') if isinstance(data, dict) else None
            if audio is None:
                return
            if isinstance(audio, (list, tuple)):
                audio = np.array(audio, dtype=np.float32)
            fp = self._compute_spectrogram_fingerprint(audio)
            with self._echo_lock:
                self._last_tts_spectrogram = fp
                self._last_tts_time = time.time()
        except Exception as e:
            logger.debug(f"Echo fingerprint capture failed: {e}")

    def _on_face_enroll_request(self, data: Any):
        """Handle explicit face enrollment request — use latest cached frame."""
        user_id = data.get('user_id', 'owner_primary') if isinstance(data, dict) else 'owner_primary'
        with self._latest_frame_lock:
            frame = self._latest_frame
        if frame is not None:
            self.enroll_owner()  # Ensure profile exists
            success = self.enroll_face_sample(user_id, frame)
            if success:
                logger.info(f"📸 Face enrolled from vision.face.enroll.request")
        else:
            logger.warning("No webcam frame available for face enrollment")

    def _on_vision_frame(self, data: Any):
        """Process a webcam frame for face recognition — rate-limited to 1 per 2 seconds."""
        frame = data.get('frame') if isinstance(data, dict) else None
        if frame is None:
            return
        # Cache latest frame for auto-enrollment
        with self._latest_frame_lock:
            self._latest_frame = frame
            self._latest_frame_time = time.time()
        # RATE LIMIT: face verification every 2 seconds (fast enough for startup auth)
        now = time.time()
        if now - getattr(self, '_last_face_verify_time', 0) < 2.0:
            return
        self._last_face_verify_time = now
        threading.Thread(
            target=self._verify_face_background,
            args=(frame,),
            daemon=True,
            name="FaceVerify"
        ).start()

    # ─── Lazy model loading ──────────────────────────────────────────────────

    def _ensure_models(self):
        """Load SOTA models on first use (lazy — avoids blocking startup)."""
        if self._models_loaded:
            return
        with self._model_load_lock:
            if self._models_loaded:
                return
            self._load_speaker_model()
            self._load_face_model()
            self._load_vad_model()
            self._models_loaded = True

    def _load_speaker_model(self):
        global _speaker_model
        if not HAS_SPEECHBRAIN:
            logger.warning("⚠️ SpeechBrain not installed — voice biometrics disabled")
            return
        try:
            save_dir = str(self.data_dir / "models" / "ecapa_tdnn")
            _speaker_model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=save_dir,
                run_opts={"device": "cpu"}  # CPU for low-latency verification
            )
            logger.info("✅ SpeechBrain ECAPA-TDNN loaded (192-dim speaker embeddings)")
        except Exception as e:
            logger.error(f"❌ Failed to load ECAPA-TDNN: {e}")

    def _load_face_model(self):
        global _facenet_model, _mtcnn_detector
        if not HAS_FACENET:
            logger.warning("\u26a0\ufe0f facenet-pytorch not installed \u2014 face biometrics disabled")
            return
        try:
            logger.info("Loading facenet-pytorch InceptionResnetV1 (vggface2, 512-dim)...")
            _facenet_model = InceptionResnetV1(pretrained='vggface2').eval()
            _mtcnn_detector = MTCNN(keep_all=False, device='cpu')
            logger.info("\u2705 facenet-pytorch ready (512-dim face embeddings, pure PyTorch)")
        except Exception as e:
            logger.error(f"\u274c Failed to init facenet-pytorch: {e}")

    def _load_vad_model(self):
        global _vad_model
        if not HAS_TORCH:
            logger.warning("⚠️ PyTorch not installed — Silero VAD disabled")
            return
        try:
            # SOTA 2026: Try local cached .jit model first to avoid [Errno 32] Broken pipe
            # torch.hub.load triggers GitHub API calls that fail in some WSL2/network configs
            import os
            _loaded = False
            
            # Check common cache locations for the pre-downloaded .jit model
            cache_paths = [
                os.path.expanduser("~/.cache/torch/hub/snakers4_silero-vad_master/src/silero_vad/data/silero_vad.jit"),
                os.path.expanduser("~/.cache/torch/hub/snakers4_silero-vad_master/files/silero_vad.jit"),
                os.path.join(os.path.dirname(__file__), "..", "data", "models", "silero_vad.jit"),
            ]
            
            for jit_path in cache_paths:
                if os.path.isfile(jit_path):
                    try:
                        _vad_model = torch.jit.load(jit_path)
                        _vad_model.eval()
                        logger.info(f"✅ Silero VAD loaded from local cache: {jit_path}")
                        _loaded = True
                        break
                    except Exception as jit_err:
                        logger.debug(f"Local .jit load failed ({jit_path}): {jit_err}")
            
            # Fallback to torch.hub.load if no local cache found
            if not _loaded:
                result = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False,
                    trust_repo=True
                )
                # torch.hub.load returns (model, utils) tuple for silero-vad
                if isinstance(result, tuple):
                    _vad_model = result[0]
                else:
                    _vad_model = result
                _vad_model.eval()
                logger.info("✅ Silero VAD loaded via torch.hub (real-time voice activity detection)")
        except Exception as e:
            logger.error(f"❌ Failed to load Silero VAD: {e}")

    # ─── Voice Activity Detection ────────────────────────────────────────────

    def is_speech(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> float:
        """
        Determine if audio chunk contains speech using Silero VAD.

        Args:
            audio_chunk: Raw audio as float32 numpy array (normalized -1..1)
            sample_rate: Sample rate (must be 8000 or 16000)

        Returns:
            Speech probability 0.0–1.0
        """
        self._ensure_models()
        if _vad_model is None:
            return 1.0  # Assume speech if VAD unavailable

        try:
            if audio_chunk.dtype != np.float32:
                audio_chunk = audio_chunk.astype(np.float32)
            if np.abs(audio_chunk).max() > 1.0:
                audio_chunk = audio_chunk / 32768.0

            tensor = torch.from_numpy(audio_chunk)
            if tensor.dim() > 1:
                tensor = tensor.mean(dim=0)

            # Silero VAD expects 512 samples at 16kHz (32ms) or multiples
            speech_prob = _vad_model(tensor, sample_rate).item()
            return speech_prob
        except Exception as e:
            logger.debug(f"VAD error: {e}")
            return 1.0

    def is_speech_bool(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> bool:
        """Boolean convenience: True if speech detected above threshold."""
        return self.is_speech(audio_chunk, sample_rate) >= self.vad_threshold

    # ─── Echo Rejection ──────────────────────────────────────────────────────

    def is_echo(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> bool:
        """
        Determine if audio chunk is an echo of the AI's own TTS output.

        Uses spectral fingerprint correlation. If the system recently spoke
        and the incoming audio's spectrogram highly correlates with the TTS
        output, it's classified as echo.

        Args:
            audio_chunk: Raw audio as float32 numpy array
            sample_rate: Sample rate

        Returns:
            True if this is likely an echo of AI's own speech
        """
        with self._echo_lock:
            if self._last_tts_spectrogram is None:
                return False
            if time.time() - self._last_tts_time > self._echo_window:
                return False
            tts_fp = self._last_tts_spectrogram

        try:
            incoming_fp = self._compute_spectrogram_fingerprint(audio_chunk, sample_rate)
            if incoming_fp is None or tts_fp is None:
                return False

            # Truncate to same length for correlation
            min_len = min(len(incoming_fp), len(tts_fp))
            if min_len < 10:
                return False

            a = incoming_fp[:min_len]
            b = tts_fp[:min_len]

            # Normalized cross-correlation
            a_norm = a - np.mean(a)
            b_norm = b - np.mean(b)
            denom = (np.linalg.norm(a_norm) * np.linalg.norm(b_norm))
            if denom < 1e-10:
                return False

            correlation = np.dot(a_norm, b_norm) / denom
            is_echo = correlation > self.echo_threshold
            if is_echo:
                logger.debug(f"🔇 Echo detected (correlation={correlation:.3f})")
            return is_echo
        except Exception as e:
            logger.debug(f"Echo detection error: {e}")
            return False

    def _compute_spectrogram_fingerprint(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> Optional[np.ndarray]:
        """Compute a compact spectral fingerprint for echo comparison."""
        try:
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            if np.abs(audio).max() > 1.0:
                audio = audio / 32768.0

            # Short-time energy in frequency bands (lightweight fingerprint)
            n_fft = 512
            hop = 256
            # Manual STFT using numpy for minimal dependencies
            n_frames = max(1, (len(audio) - n_fft) // hop + 1)
            window = np.hanning(n_fft)
            fingerprint = np.zeros(n_frames)
            for i in range(n_frames):
                start = i * hop
                frame = audio[start:start + n_fft]
                if len(frame) < n_fft:
                    frame = np.pad(frame, (0, n_fft - len(frame)))
                spectrum = np.abs(np.fft.rfft(frame * window))
                # Use energy in 300-3000 Hz band (speech range)
                freq_bin_low = int(300 * n_fft / sample_rate)
                freq_bin_high = int(3000 * n_fft / sample_rate)
                fingerprint[i] = np.mean(spectrum[freq_bin_low:freq_bin_high + 1])
            return fingerprint
        except Exception:
            return None

    # ─── Speaker Embedding Extraction ────────────────────────────────────────

    def extract_voice_embedding(self, audio: np.ndarray, sample_rate: int = 16000) -> Optional[np.ndarray]:
        """
        Extract 192-dim speaker embedding using ECAPA-TDNN.

        Args:
            audio: Audio waveform as float32 numpy array
            sample_rate: Sample rate (will resample to 16kHz if needed)

        Returns:
            192-dim numpy embedding or None
        """
        self._ensure_models()
        if _speaker_model is None:
            return None

        try:
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            if np.abs(audio).max() > 1.0:
                audio = audio / 32768.0

            tensor = torch.tensor(audio).unsqueeze(0)  # (1, T)
            embedding = _speaker_model.encode_batch(tensor)
            return embedding.squeeze().cpu().numpy()
        except Exception as e:
            logger.error(f"Voice embedding extraction failed: {e}")
            return None

    # ─── Face Embedding Extraction ───────────────────────────────────────────

    def extract_face_embedding(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract 512-dim face embedding using facenet-pytorch InceptionResnetV1.

        Args:
            frame: BGR image (OpenCV format)

        Returns:
            512-dim L2-normalized numpy embedding or None
        """
        self._ensure_models()
        if not HAS_FACENET or _facenet_model is None:
            return None

        try:
            import torch
            from PIL import Image
            # Convert BGR (OpenCV) -> RGB (PIL)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            # Detect + align face using MTCNN (returns 160x160 tensor or None)
            face_tensor = _mtcnn_detector(pil_img)
            if face_tensor is None:
                return None
            # face_tensor shape: (3, 160, 160) — add batch dim
            face_batch = face_tensor.unsqueeze(0)
            with torch.no_grad():
                emb = _facenet_model(face_batch).squeeze().numpy()
            # L2-normalize
            emb = emb / (np.linalg.norm(emb) + 1e-10)
            return emb.astype(np.float32)
        except Exception as e:
            logger.debug(f"Face embedding extraction failed: {e}")
            return None

    # ─── Enrollment ──────────────────────────────────────────────────────────

    def enroll_owner(self, name: str = "Owner") -> str:
        """Create or update the owner profile. Returns user_id."""
        user_id = "owner_primary"
        if user_id not in self.profiles:
            self.profiles[user_id] = IdentityProfile(
                user_id=user_id,
                name=name,
                role="owner",
                is_authorized=True,
                financial_access=True,
                non_financial_access=True,
                created_at=time.time()
            )
            self._save_profiles()
        else:
            # Ensure existing owner profile has correct role/auth/name
            p = self.profiles[user_id]
            p.role = "owner"
            p.is_authorized = True
            p.financial_access = True
            p.non_financial_access = True
            if name != "Owner":
                p.name = name  # Update name if explicitly provided
        self._owner_id = user_id
        return user_id

    def enroll_owner_from_files(self, name: str = "Isaiah Wright") -> Dict[str, int]:
        """
        SOTA 2026: Pre-enroll owner from uploaded image + voice files.
        
        Reads face images (.jpg/.png) from data/owner_enrollment/face/
        and voice recordings (.wav/.mp3/.flac) from data/owner_enrollment/voice/
        
        This allows Kingdom AI to recognize the owner immediately on startup
        without requiring live enrollment. The user uploads their photo(s) and
        voice recording(s) once, and the system uses them to build biometric
        templates via ECAPA-TDNN (voice) and facenet-pytorch (face).
        
        Returns:
            Dict with 'voice_samples' and 'face_samples' counts enrolled
        """
        result = {'voice_samples': 0, 'face_samples': 0}
        
        # Ensure owner profile exists
        user_id = self.enroll_owner(name)
        profile = self.profiles[user_id]
        
        enrollment_dir = Path(self.data_dir).parent / "owner_enrollment"
        voice_dir = enrollment_dir / "voice"
        face_dir = enrollment_dir / "face"
        
        if not enrollment_dir.exists():
            enrollment_dir.mkdir(parents=True, exist_ok=True)
            voice_dir.mkdir(exist_ok=True)
            face_dir.mkdir(exist_ok=True)
            # Create README for the user
            readme = enrollment_dir / "README.txt"
            readme.write_text(
                "KINGDOM AI — Owner Biometric Pre-Enrollment\n"
                "============================================\n\n"
                "Place your files here so Kingdom AI recognizes you on startup:\n\n"
                "  voice/  — WAV/MP3/FLAC recordings of your voice (3-10 seconds each)\n"
                "            At least 3 recordings recommended for reliable verification.\n"
                "            Speak naturally — read a sentence, say your name, etc.\n\n"
                "  face/   — JPG/PNG photos of your face\n"
                "            At least 3 photos from different angles recommended.\n"
                "            Good lighting, face clearly visible.\n\n"
                "These files are processed once at startup to build biometric templates.\n"
                "The original files stay here for re-enrollment if needed.\n"
            )
            logger.info(f"📁 Created owner enrollment directory: {enrollment_dir}")
            logger.info("   Place face images in face/ and voice recordings in voice/")
            return result
        
        self._ensure_models()
        
        # Check if enrollment files exist before resetting
        voice_files_exist = voice_dir.exists() and any(
            f.suffix.lower() in ('.wav', '.mp3', '.flac', '.ogg', '.m4a')
            for f in voice_dir.iterdir() if f.is_file()
        ) if voice_dir.exists() else False
        face_files_exist = face_dir.exists() and any(
            f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
            for f in face_dir.iterdir() if f.is_file()
        ) if face_dir.exists() else False
        
        # SOTA 2026 persistence hardening:
        # preserve learned embeddings across runs; append file enrollments.
        if voice_files_exist and len(profile.voice_embeddings) > 0:
            logger.info(
                f"🧠 Preserving {len(profile.voice_embeddings)} existing owner voice embeddings; appending file enrollments"
            )
        if face_files_exist and len(profile.face_embeddings) > 0:
            logger.info(
                f"🧠 Preserving {len(profile.face_embeddings)} existing owner face embeddings; appending file enrollments"
            )
        
        # ── Voice enrollment from files ──
        if voice_dir.exists():
            voice_files = sorted(
                [f for f in voice_dir.iterdir()
                 if f.suffix.lower() in ('.wav', '.mp3', '.flac', '.ogg', '.m4a')]
            )
            for vf in voice_files:
                try:
                    import torchaudio
                    waveform, sr = torchaudio.load(str(vf))
                    # Convert to mono float32 numpy
                    if waveform.shape[0] > 1:
                        waveform = waveform.mean(dim=0, keepdim=True)
                    audio_np = waveform.squeeze().numpy().astype(np.float32)
                    # Resample to 16kHz if needed
                    if sr != 16000:
                        resampler = torchaudio.transforms.Resample(sr, 16000)
                        audio_np = resampler(torch.tensor(audio_np)).numpy()
                    
                    embedding = self.extract_voice_embedding(audio_np, 16000)
                    if embedding is not None:
                        duplicate = any(
                            isinstance(prev, np.ndarray) and prev.shape == embedding.shape and np.allclose(prev, embedding, atol=1e-5)
                            for prev in profile.voice_embeddings
                        )
                        if duplicate:
                            logger.info(f"⏭️ Skipping duplicate voice embedding from file: {vf.name}")
                        else:
                            profile.voice_embeddings.append(embedding)
                            result['voice_samples'] += 1
                            logger.info(f"🎤 Voice enrolled from file: {vf.name}")
                    else:
                        logger.warning(f"⚠️ Could not extract voice embedding from: {vf.name}")
                except Exception as e:
                    logger.error(f"❌ Failed to process voice file {vf.name}: {e}")
        
        # ── Face enrollment from files ──
        if face_dir.exists():
            face_files = sorted(
                [f for f in face_dir.iterdir()
                 if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp', '.webp')]
            )
            for ff in face_files:
                try:
                    img = cv2.imread(str(ff))
                    if img is None:
                        logger.warning(f"⚠️ Could not read image: {ff.name}")
                        continue
                    embedding = self.extract_face_embedding(img)
                    if embedding is not None:
                        duplicate = any(
                            isinstance(prev, np.ndarray) and prev.shape == embedding.shape and np.allclose(prev, embedding, atol=1e-5)
                            for prev in profile.face_embeddings
                        )
                        if duplicate:
                            logger.info(f"⏭️ Skipping duplicate face embedding from file: {ff.name}")
                        else:
                            profile.face_embeddings.append(embedding)
                            result['face_samples'] += 1
                            logger.info(f"📸 Face enrolled from file: {ff.name}")
                    else:
                        logger.warning(f"⚠️ No face detected in: {ff.name}")
                except Exception as e:
                    logger.error(f"❌ Failed to process face image {ff.name}: {e}")
        
        # Recompute mean embeddings and save (always keep persisted profile consistent).
        profile.recompute_means()
        self._save_profiles()
        if result['voice_samples'] > 0 or result['face_samples'] > 0:
            logger.info(
                f"✅ Owner pre-enrolled: {name} — "
                f"{result['voice_samples']} voice samples, "
                f"{result['face_samples']} face samples"
            )
        else:
            logger.info(
                f"ℹ️ No new enrollment files added in {enrollment_dir}. "
                f"Existing owner biometrics were preserved."
            )
        
        if self.event_bus:
            self.event_bus.publish('identity.owner.enrolled', {
                'user_id': user_id, 'name': name,
                'voice_samples': result['voice_samples'],
                'face_samples': result['face_samples'],
                'method': 'file_pre_enrollment'
            })
        
        return result

    def enroll_user(self, name: str, authorize: bool = False,
                    relationship: str = "",
                    financial_access: bool = False,
                    non_financial_access: bool = True) -> str:
        """Create a new user profile. Returns user_id.
        
        New users start as 'unknown' role. The owner must explicitly
        grant access for them to control the system.
        """
        # Generate a unique user_id from name
        base_id = name.lower().replace(' ', '_')
        user_id = base_id
        counter = 1
        while user_id in self.profiles:
            user_id = f"{base_id}_{counter}"
            counter += 1
        
        self.profiles[user_id] = IdentityProfile(
            user_id=user_id,
            name=name,
            role="authorized" if authorize else "unknown",
            is_authorized=authorize,
            authorized_by=self._owner_id if authorize else None,
            authorized_at=time.time() if authorize else 0.0,
            relationship=relationship or "",
            financial_access=bool(financial_access) if authorize else False,
            non_financial_access=bool(non_financial_access),
            created_at=time.time()
        )
        self._save_profiles()
        logger.info(f"\U0001f464 New user profile created: {name} (id={user_id}, authorized={authorize})")
        
        if self.event_bus:
            self.event_bus.publish('identity.user.created', {
                'user_id': user_id, 'name': name,
                'authorized': authorize, 'timestamp': time.time()
            })
        return user_id

    def grant_access(self, target_name: str, financial_access: bool = False,
                     relationship: str = "") -> Optional[str]:
        """Grant system control access to a user by name. Owner-only action.
        
        If the user doesn't have a profile yet, one is created.
        Returns user_id of the granted user, or None on failure.
        """
        # Find existing profile by name (case-insensitive)
        target_profile = None
        for uid, profile in self.profiles.items():
            if profile.name.lower() == target_name.lower() and uid != self._owner_id:
                target_profile = profile
                break
        
        if target_profile is None:
            # Create a new authorized profile
            user_id = self.enroll_user(
                target_name,
                authorize=True,
                relationship=relationship,
                financial_access=financial_access,
                non_financial_access=True,
            )
            logger.info(f"\u2705 ACCESS GRANTED to new user: {target_name} (id={user_id})")
        else:
            target_profile.role = "authorized"
            target_profile.is_authorized = True
            target_profile.authorized_by = self._owner_id
            target_profile.authorized_at = time.time()
            if relationship:
                target_profile.relationship = relationship
            target_profile.non_financial_access = True
            target_profile.financial_access = bool(financial_access)
            self._save_profiles()
            user_id = target_profile.user_id
            logger.info(f"\u2705 ACCESS GRANTED to existing user: {target_name} (id={user_id})")
        
        if self.event_bus:
            self.event_bus.publish('identity.access.granted', {
                'user_id': user_id, 'name': target_name,
                'granted_by': self._owner_id, 'timestamp': time.time()
            })
        return user_id

    def set_financial_access(self, target_name: str, allowed: bool) -> bool:
        """Enable/disable financial access for an existing non-owner user."""
        for uid, profile in self.profiles.items():
            if uid == self._owner_id:
                continue
            if profile.name.lower() == target_name.lower():
                profile.financial_access = bool(allowed)
                if profile.is_authorized:
                    profile.non_financial_access = True
                self._save_profiles()
                logger.info(
                    "💼 Financial access %s for %s (id=%s)",
                    "ENABLED" if allowed else "DISABLED",
                    profile.name,
                    uid,
                )
                return True
        logger.warning(f"Cannot set financial access: no profile found for '{target_name}'")
        return False

    def has_financial_access(self, user_id: Optional[str]) -> bool:
        """Check whether a user can perform financial/trading/wallet actions."""
        if not user_id:
            return False
        profile = self.profiles.get(user_id)
        if not profile:
            return False
        if user_id == self._owner_id:
            return True
        return bool(profile.is_authorized and profile.financial_access)

    def ensure_guest_basic_only(self, name: str) -> str:
        """Create/update guest profile: basic (non-financial) access when owner absent.
        Owner said 'do not enroll' — no full enrollment, but basic access when seeking owner."""
        existing = None
        for profile in self.profiles.values():
            if profile.name.lower() == name.lower():
                existing = profile
                break
        if existing:
            existing.role = "guest"
            existing.is_authorized = False
            existing.non_financial_access = True
            existing.financial_access = False
            self._save_profiles()
            return existing.user_id
        return self.enroll_user(
            name=name,
            authorize=False,
            relationship="guest",
            financial_access=False,
            non_financial_access=True,
        )

    def ensure_family_member(self, name: str, relationship: str = "family") -> str:
        """Ensure family member exists with living-trust defaults.

        Defaults:
        - Authorized for non-financial system tools
        - Financial access remains disabled until owner grants it
        """
        existing = None
        for profile in self.profiles.values():
            if profile.name.lower() == name.lower():
                existing = profile
                break

        if existing is None:
            return self.enroll_user(
                name=name,
                authorize=True,
                relationship=relationship,
                financial_access=False,
                non_financial_access=True,
            )

        existing.role = "authorized"
        existing.is_authorized = True
        existing.relationship = relationship or existing.relationship
        existing.non_financial_access = True
        if existing.user_id != self._owner_id:
            existing.financial_access = bool(existing.financial_access)
        self._save_profiles()
        return existing.user_id

    def revoke_access(self, target_name: str) -> bool:
        """Revoke system control access from a user by name. Owner-only action.
        
        Returns True if access was revoked.
        """
        for uid, profile in self.profiles.items():
            if profile.name.lower() == target_name.lower() and uid != self._owner_id:
                profile.role = "unknown"
                profile.is_authorized = False
                self._save_profiles()
                logger.info(f"\U0001f6ab ACCESS REVOKED from: {target_name} (id={uid})")
                if self.event_bus:
                    self.event_bus.publish('identity.access.revoked', {
                        'user_id': uid, 'name': target_name,
                        'revoked_by': self._owner_id, 'timestamp': time.time()
                    })
                return True
        logger.warning(f"Cannot revoke access: no profile found for '{target_name}'")
        return False

    def list_authorized_users(self) -> List[Dict[str, Any]]:
        """List all users with system access."""
        result = []
        for uid, profile in self.profiles.items():
            if profile.is_authorized:
                result.append({
                    'user_id': uid, 'name': profile.name,
                    'role': profile.role,
                    'relationship': profile.relationship,
                    'financial_access': bool(profile.financial_access or uid == self._owner_id),
                    'non_financial_access': bool(profile.non_financial_access),
                    'voice_samples': profile.enrollment_count_voice,
                    'face_samples': profile.enrollment_count_face,
                    'last_seen': profile.last_seen_at,
                })
        return result

    def auto_enroll_unknown_speaker(self, audio: np.ndarray,
                                    sample_rate: int = 16000,
                                    frame: Optional[np.ndarray] = None) -> Optional[str]:
        """Auto-enroll an unknown speaker detected by the system.
        
        Creates an 'unknown_N' profile so the system can recognize them
        again later. They do NOT get system access until the owner grants it.
        
        Returns user_id of the new/matched unknown profile.
        """
        # First check if this voice matches any existing unknown profile
        embedding = self.extract_voice_embedding(audio, sample_rate)
        if embedding is None:
            return None
        
        best_score = -1.0
        best_unknown: Optional[IdentityProfile] = None
        for profile in self.profiles.values():
            if profile.role == "unknown" and profile.voice_mean_embedding is not None:
                score = self._cosine_similarity(embedding, profile.voice_mean_embedding)
                if score > best_score:
                    best_score = score
                    best_unknown = profile
        
        if best_unknown and best_score >= self.voice_threshold:
            # Known unknown — add more samples to their profile
            best_unknown.voice_embeddings.append(embedding)
            best_unknown.recompute_means()
            best_unknown.last_seen_at = time.time()
            if frame is not None:
                face_emb = self.extract_face_embedding(frame)
                if face_emb is not None:
                    best_unknown.face_embeddings.append(face_emb)
                    best_unknown.recompute_means()
            self._save_profiles()
            logger.info(f"\U0001f464 Recognized returning unknown: {best_unknown.name} ({best_score:.2f})")
            return best_unknown.user_id
        
        # Brand new unknown — create profile
        unknown_count = sum(1 for p in self.profiles.values() if p.role == "unknown")
        name = f"Unknown Person {unknown_count + 1}"
        user_id = self.enroll_user(name, authorize=False)
        profile = self.profiles[user_id]
        profile.voice_embeddings.append(embedding)
        profile.recompute_means()
        profile.last_seen_at = time.time()
        
        if frame is not None:
            face_emb = self.extract_face_embedding(frame)
            if face_emb is not None:
                profile.face_embeddings.append(face_emb)
                profile.recompute_means()
        
        self._save_profiles()
        logger.info(f"\U0001f464 NEW unknown speaker enrolled: {name} (id={user_id})")
        
        if self.event_bus:
            self.event_bus.publish('identity.unknown.detected', {
                'user_id': user_id, 'name': name,
                'voice_score': best_score, 'timestamp': time.time()
            })
        return user_id

    def enroll_voice_sample(self, user_id: str, audio: np.ndarray,
                            sample_rate: int = 16000) -> bool:
        """
        Add a voice enrollment sample for a user.

        Requires 3+ samples for reliable verification. Each sample should
        be 3-10 seconds of clear speech.

        Returns:
            True if sample was enrolled successfully
        """
        if user_id not in self.profiles:
            logger.error(f"Profile {user_id} not found")
            return False

        embedding = self.extract_voice_embedding(audio, sample_rate)
        if embedding is None:
            logger.warning("Could not extract voice embedding from sample")
            return False

        profile = self.profiles[user_id]
        profile.voice_embeddings.append(embedding)
        profile.recompute_means()
        self._save_profiles()

        count = profile.enrollment_count_voice
        logger.info(f"🎤 Voice sample enrolled for {profile.name} ({count} total)")

        if self.event_bus:
            self.event_bus.publish('identity.voice.enrolled', {
                'user_id': user_id,
                'name': profile.name,
                'sample_count': count
            })
        return True

    def enroll_face_sample(self, user_id: str, frame: np.ndarray) -> bool:
        """
        Add a face enrollment sample for a user.

        Requires 5+ samples from different angles for reliable verification.

        Returns:
            True if sample was enrolled successfully
        """
        if user_id not in self.profiles:
            logger.error(f"Profile {user_id} not found")
            return False

        embedding = self.extract_face_embedding(frame)
        if embedding is None:
            logger.warning("Could not extract face embedding from frame")
            return False

        profile = self.profiles[user_id]
        profile.face_embeddings.append(embedding)
        profile.recompute_means()
        self._save_profiles()

        count = profile.enrollment_count_face
        logger.info(f"📸 Face sample enrolled for {profile.name} ({count} total)")

        if self.event_bus:
            self.event_bus.publish('identity.face.enrolled', {
                'user_id': user_id,
                'name': profile.name,
                'sample_count': count
            })
        return True

    # ─── Verification ────────────────────────────────────────────────────────

    def verify_voice(self, audio: np.ndarray, sample_rate: int = 16000) -> VerificationResult:
        """
        Verify speaker identity from audio.

        Pipeline:
        1. Silero VAD → is this speech?
        2. Echo rejection → is this the AI's own voice?
        3. ECAPA-TDNN → extract embedding
        4. Cosine similarity against all enrolled profiles
        5. Return best match or unknown

        Args:
            audio: Audio waveform
            sample_rate: Sample rate

        Returns:
            VerificationResult
        """
        # Step 1: VAD — is this speech?
        speech_prob = self.is_speech(audio, sample_rate)
        if speech_prob < self.vad_threshold:
            return VerificationResult(
                is_owner=False, user_id=None, user_name=None,
                is_speech=False,
                message=f"Not speech (VAD={speech_prob:.2f})"
            )

        # Step 2: Echo rejection
        if self.is_echo(audio, sample_rate):
            return VerificationResult(
                is_owner=False, user_id=None, user_name=None,
                is_echo=True, is_speech=True,
                message="Echo of AI's own voice detected"
            )

        # Step 3: Extract embedding
        embedding = self.extract_voice_embedding(audio, sample_rate)
        if embedding is None:
            return VerificationResult(
                is_owner=False, user_id=None, user_name=None,
                message="Could not extract voice embedding"
            )

        # SOTA 2026: Auto-enroll first non-echo voice as owner when zero voice samples exist
        owner_id = self._owner_id or self.enroll_owner()
        owner_profile = self.profiles.get(owner_id) if owner_id else None
        owner_has_voice = owner_profile and len(owner_profile.voice_embeddings) > 0 if owner_profile else False
        if not owner_has_voice:
            if not owner_id:
                owner_id = self.enroll_owner()
            success = self.enroll_voice_sample(owner_id or '', audio, sample_rate)
            if success:
                status = self.get_status()
                count = status.get('owner_voice_samples', 0)
                logger.info(f"🎤 AUTO-ENROLLED first voice as owner Isaiah Wright ({count} samples)")
                return VerificationResult(
                    is_owner=True, user_id=owner_id, user_name='Isaiah Wright',
                    voice_score=1.0, method="voice",
                    is_authorized=True, role="owner",
                    message=f"Auto-enrolled owner voice ({count} samples)"
                )

        # Step 4: Match against profiles
        best_score = -1.0
        best_profile: Optional[IdentityProfile] = None

        for profile in self.profiles.values():
            if profile.voice_mean_embedding is None:
                continue
            score = self._cosine_similarity(embedding, profile.voice_mean_embedding)
            if score > best_score:
                best_score = score
                best_profile = profile

        # Step 5: Decision
        if best_profile and best_score >= self.voice_threshold:
            is_owner = (best_profile.user_id == self._owner_id)
            best_profile.last_verified_at = time.time()
            best_profile.last_seen_at = time.time()
            # ADAPTIVE LEARNING: Keep adding samples to learn how owner actually talks
            if is_owner and embedding is not None and len(best_profile.voice_embeddings) < 50:
                best_profile.voice_embeddings.append(embedding)
                best_profile.recompute_means()
                if len(best_profile.voice_embeddings) % 10 == 0:
                    logger.info(f"🧠 Adaptive voice learning: {len(best_profile.voice_embeddings)} samples for {best_profile.name}")
                    self._save_profiles()
            smoothed_score = self._ema_smooth(best_score, "voice")
            return VerificationResult(
                is_owner=is_owner,
                user_id=best_profile.user_id,
                user_name=best_profile.name,
                voice_score=smoothed_score,
                method="voice",
                is_authorized=best_profile.is_authorized,
                role=best_profile.role,
                message=f"Voice verified: {best_profile.name} ({smoothed_score:.2f})"
            )

        # Unknown speaker — auto-enroll so we can recognize them later
        # They get NO system access until owner grants it
        unknown_id = None
        if embedding is not None:
            with self._latest_frame_lock:
                frame = self._latest_frame
            unknown_id = self.auto_enroll_unknown_speaker(
                audio, sample_rate, frame=frame
            )

        return VerificationResult(
            is_owner=False, user_id=unknown_id, user_name=None,
            voice_score=best_score,
            method="voice",
            is_authorized=False,
            role="unknown",
            message=f"Voice not recognized (best={best_score:.2f})"
        )

    def verify_face(self, frame: np.ndarray) -> VerificationResult:
        """
        Verify user identity from a webcam frame.

        Args:
            frame: BGR image (OpenCV format)

        Returns:
            VerificationResult
        """
        embedding = self.extract_face_embedding(frame)
        if embedding is None:
            return VerificationResult(
                is_owner=False, user_id=None, user_name=None,
                method="face",
                message="No face detected"
            )

        best_score = -1.0
        best_profile: Optional[IdentityProfile] = None

        for profile in self.profiles.values():
            if profile.face_mean_embedding is None:
                continue
            score = self._cosine_similarity(embedding, profile.face_mean_embedding)
            if score > best_score:
                best_score = score
                best_profile = profile

        if best_profile and best_score >= self.face_threshold:
            is_owner = (best_profile.user_id == self._owner_id)
            best_profile.last_verified_at = time.time()
            best_profile.last_seen_at = time.time()
            # ADAPTIVE LEARNING: Keep adding face samples from different angles/lighting
            if is_owner and embedding is not None and len(best_profile.face_embeddings) < 50:
                best_profile.face_embeddings.append(embedding)
                best_profile.recompute_means()
                if len(best_profile.face_embeddings) % 10 == 0:
                    logger.info(f"🧠 Adaptive face learning: {len(best_profile.face_embeddings)} samples for {best_profile.name}")
                    self._save_profiles()
            smoothed_face = self._ema_smooth(best_score, "face")
            return VerificationResult(
                is_owner=is_owner,
                user_id=best_profile.user_id,
                user_name=best_profile.name,
                face_score=smoothed_face,
                method="face",
                is_authorized=best_profile.is_authorized,
                role=best_profile.role,
                message=f"Face verified: {best_profile.name} ({smoothed_face:.2f})"
            )

        return VerificationResult(
            is_owner=False, user_id=None, user_name=None,
            face_score=best_score,
            method="face",
            is_authorized=False,
            role="unknown",
            message=f"Face not recognized (best={best_score:.2f})"
        )

    def verify_fused(self, audio: np.ndarray = None, frame: np.ndarray = None,
                     sample_rate: int = 16000) -> VerificationResult:
        """
        Multi-modal verification using both voice and face.

        Weighted fusion: score = w_voice * voice_score + w_face * face_score

        Args:
            audio: Audio waveform (optional)
            frame: BGR image (optional)
            sample_rate: Audio sample rate

        Returns:
            VerificationResult with fused score
        """
        voice_result = None
        face_result = None

        if audio is not None:
            voice_result = self.verify_voice(audio, sample_rate)
            if voice_result.is_echo:
                return voice_result  # Echo — reject immediately

        if frame is not None:
            face_result = self.verify_face(frame)
        else:
            # Use cached face result if recent
            now = time.time()
            if (self._current_face_result and
                    now - self._face_result_time < self._face_cache_duration):
                face_result = self._current_face_result

        # Fuse scores
        voice_score = voice_result.voice_score if voice_result else 0.0
        face_score = face_result.face_score if face_result else 0.0

        # Adjust weights based on what's available
        if voice_result and face_result:
            fused = self.voice_weight * voice_score + self.face_weight * face_score
        elif voice_result:
            fused = voice_score
        elif face_result:
            fused = face_score
        else:
            return VerificationResult(
                is_owner=False, user_id=None, user_name=None,
                method="fused",
                message="No biometric data available"
            )

        # Find the best matching user from either result
        best_user_id = None
        best_user_name = None
        best_role = "unknown"
        best_authorized = False
        if voice_result and voice_result.user_id:
            best_user_id = voice_result.user_id
            best_user_name = voice_result.user_name
            best_role = voice_result.role
            best_authorized = voice_result.is_authorized
        elif face_result and face_result.user_id:
            best_user_id = face_result.user_id
            best_user_name = face_result.user_name
            best_role = face_result.role
            best_authorized = face_result.is_authorized

        is_owner = (best_user_id == self._owner_id) if best_user_id else False

        if fused >= self.fused_threshold and best_user_id:
            return VerificationResult(
                is_owner=is_owner,
                user_id=best_user_id,
                user_name=best_user_name,
                voice_score=voice_score,
                face_score=face_score,
                fused_score=fused,
                method="fused",
                is_authorized=best_authorized,
                role=best_role,
                message=f"Identity verified: {best_user_name} (fused={fused:.2f})"
            )

        return VerificationResult(
            is_owner=False, user_id=None, user_name=None,
            voice_score=voice_score,
            face_score=face_score,
            fused_score=fused,
            method="fused",
            is_authorized=False,
            role="unknown",
            message=f"Identity not verified (fused={fused:.2f})"
        )

    # ─── Background face verification ────────────────────────────────────────

    def _verify_face_background(self, frame: np.ndarray):
        """Run face verification in background and cache + publish result.
        
        SOTA 2026: If zero face samples are enrolled, auto-enroll the first
        detected face as the owner (Isaiah Wright). The person setting up the
        system IS the owner — no chicken-and-egg lockout.
        """
        try:
            # Auto-enroll first face as owner when zero enrollments exist
            owner_id = self._owner_id or self.enroll_owner()
            owner_profile = self.profiles.get(owner_id) if owner_id else None
            owner_has_face = owner_profile and len(owner_profile.face_embeddings) > 0 if owner_profile else False
            if not owner_has_face:
                embedding = self.extract_face_embedding(frame)
                if embedding is not None:
                    if not owner_id:
                        owner_id = self.enroll_owner()
                    success = self.enroll_face_sample(owner_id or '', frame)
                    if success:
                        status = self.get_status()
                        count = status.get('owner_face_samples', 0)
                        logger.info(f"📸 AUTO-ENROLLED first face as owner Isaiah Wright ({count} samples)")
                        if self.event_bus:
                            self.event_bus.publish('identity.face.verified', {
                                'user_id': self._owner_id,
                                'user_name': 'Isaiah Wright',
                                'is_owner': True,
                                'confidence': 1.0,
                                'auto_enrolled': True,
                                'timestamp': time.time()
                            })
                    return
                return  # No face detected yet, skip

            result = self.verify_face(frame)
            self._current_face_result = result
            self._face_result_time = time.time()

            if self.event_bus:
                if result.user_id:
                    self.event_bus.publish('identity.face.verified', {
                        'user_id': result.user_id,
                        'user_name': result.user_name,
                        'is_owner': result.is_owner,
                        'confidence': result.face_score,
                        'timestamp': time.time()
                    })
                else:
                    self.event_bus.publish('identity.face.unknown', {
                        'confidence': result.face_score,
                        'message': result.message,
                        'timestamp': time.time()
                    })
        except Exception as e:
            logger.debug(f"Background face verification error: {e}")

    # ─── Utility ─────────────────────────────────────────────────────────────

    def _ema_smooth(self, new_val: float, kind: str) -> float:
        """Apply EMA smoothing to stabilize confidence scores across frames."""
        alpha = self._ema_alpha
        if kind == "voice":
            prev = self._ema_voice_score
            smoothed = new_val if prev is None else alpha * new_val + (1 - alpha) * prev
            self._ema_voice_score = smoothed
        else:
            prev = self._ema_face_score
            smoothed = new_val if prev is None else alpha * new_val + (1 - alpha) * prev
            self._ema_face_score = smoothed
        return smoothed

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        if norm < 1e-10:
            return 0.0
        return float(dot / norm)

    # ─── Persistence ─────────────────────────────────────────────────────────

    def _save_profiles(self):
        """Save all profiles to disk."""
        save_path = self.data_dir / "profiles.pkl"
        try:
            data = {}
            for uid, profile in self.profiles.items():
                data[uid] = {
                    'user_id': profile.user_id,
                    'name': profile.name,
                    'role': profile.role,
                    'is_authorized': profile.is_authorized,
                    'voice_embeddings': [e.tolist() for e in profile.voice_embeddings],
                    'face_embeddings': [e.tolist() for e in profile.face_embeddings],
                    'created_at': profile.created_at,
                    'last_verified_at': profile.last_verified_at,
                    'last_seen_at': profile.last_seen_at,
                    'authorized_by': profile.authorized_by,
                    'authorized_at': profile.authorized_at,
                    'relationship': profile.relationship,
                    'financial_access': profile.financial_access,
                    'non_financial_access': profile.non_financial_access,
                }
            with open(save_path, 'wb') as f:
                pickle.dump(data, f)
            logger.debug(f"Saved {len(data)} profiles to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")

    def _load_profiles(self):
        """Load profiles from disk."""
        save_path = self.data_dir / "profiles.pkl"
        if not save_path.exists():
            return
        try:
            with open(save_path, 'rb') as f:
                data = pickle.load(f)
            for uid, pdata in data.items():
                profile = IdentityProfile(
                    user_id=pdata['user_id'],
                    name=pdata['name'],
                    role=pdata.get('role', 'owner' if uid == 'owner_primary' else 'unknown'),
                    is_authorized=pdata.get('is_authorized', uid == 'owner_primary'),
                    voice_embeddings=[np.array(e) for e in pdata.get('voice_embeddings', [])],
                    face_embeddings=[np.array(e) for e in pdata.get('face_embeddings', [])],
                    created_at=pdata.get('created_at', 0),
                    last_verified_at=pdata.get('last_verified_at', 0),
                    last_seen_at=pdata.get('last_seen_at', 0),
                    authorized_by=pdata.get('authorized_by'),
                    authorized_at=pdata.get('authorized_at', 0),
                    relationship=pdata.get('relationship', ''),
                    financial_access=pdata.get('financial_access', uid == 'owner_primary'),
                    non_financial_access=pdata.get('non_financial_access', True),
                )
                profile.recompute_means()
                self.profiles[uid] = profile
                if uid == "owner_primary":
                    self._owner_id = uid
            logger.info(f"Loaded {len(self.profiles)} identity profiles")
        except Exception as e:
            logger.warning(f"Could not load profiles: {e}")

    # ─── Status ──────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        owner = self.profiles.get(self._owner_id) if self._owner_id else None
        authorized = [p.name for p in self.profiles.values() if p.is_authorized and p.role != 'owner']
        unknowns = [p.name for p in self.profiles.values() if p.role == 'unknown']
        return {
            'initialized': self._initialized,
            'models_loaded': self._models_loaded,
            'speechbrain_available': HAS_SPEECHBRAIN,
            'facenet_available': HAS_FACENET,
            'silero_vad_available': HAS_TORCH,
            'profiles_count': len(self.profiles),
            'owner_enrolled': self._owner_id is not None,
            'owner_name': owner.name if owner else None,
            'owner_voice_samples': owner.enrollment_count_voice if owner else 0,
            'owner_face_samples': owner.enrollment_count_face if owner else 0,
            'authorized_users': authorized,
            'unknown_users': unknowns,
            'voice_threshold': self.voice_threshold,
            'face_threshold': self.face_threshold,
        }


# ─── Module-level convenience ────────────────────────────────────────────────

def get_user_identity_engine(event_bus: Any = None) -> UserIdentityEngine:
    """Get or create the singleton UserIdentityEngine."""
    return UserIdentityEngine(event_bus=event_bus)
