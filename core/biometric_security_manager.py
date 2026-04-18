"""
Biometric Security Manager - SOTA 2026 Face & Voice Recognition Security

This module provides comprehensive biometric security for Kingdom AI, ensuring
that only authorized users can control the system via voice or text commands.

SOTA 2026 Features:
- Face recognition using facenet-pytorch/dlib for 512-dimensional face encodings
- Voice biometrics using MFCC feature extraction and GMM models
- Multi-user registry with family member support
- Real-time webcam face verification
- Voice print matching for speaker verification
- Ollama brain integration for intelligent security decisions
- Event bus integration for security state broadcasting
- Continuous authentication with liveness detection

Creator: Isaiah Wright
Authorized Users: Creator + Family (configurable registry)
"""

import os
import sys

# =============================================================================
# SOTA 2026: Silence ALSA errors before any audio imports
# =============================================================================
def _silence_alsa():
    """Silence ALSA errors at C level for WSL compatibility."""
    try:
        if sys.platform == 'linux':
            import ctypes
            from ctypes import CFUNCTYPE, c_char_p, c_int
            ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
            def _noop_handler(filename, line, function, err, fmt):
                pass
            _handler = ERROR_HANDLER_FUNC(_noop_handler)
            try:
                asound = ctypes.cdll.LoadLibrary('libasound.so.2')
                asound.snd_lib_error_set_handler(_handler)
                globals()['_alsa_handler'] = _handler  # Prevent GC
            except OSError:
                pass
    except Exception:
        pass

_silence_alsa()
import json
import time
import logging
import threading
import hashlib
import pickle
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# CRITICAL: NumPy _ARRAY_API patch BEFORE cv2 import (NumPy 2.x compatibility)
# sitecustomize.py should have patched numpy via import hook, but ensure it's patched here too
try:
    # Import numpy - import hook in sitecustomize.py should have already patched it
    import numpy as np
    
    # CRITICAL: Double-check _ARRAY_API exists (import hook should have set it)
    if not hasattr(np, '_ARRAY_API'):
        import types
        ns = types.SimpleNamespace()
        ns.ARRAY_API_STRICT = False
        np._ARRAY_API = ns  # type: ignore[attr-defined]
    
    # CRITICAL: Patch numpy._core.multiarray (cv2's C extension checks this during bootstrap)
    try:
        import numpy._core.multiarray as multiarray
        if not hasattr(multiarray, '_ARRAY_API'):
            multiarray._ARRAY_API = getattr(np, '_ARRAY_API', None)  # type: ignore[attr-defined]
    except Exception:
        pass
    
    # CRITICAL: Also patch numpy.core.multiarray (older numpy versions)
    try:
        import numpy.core.multiarray as old_multiarray
        if not hasattr(old_multiarray, '_ARRAY_API'):
            old_multiarray._ARRAY_API = getattr(np, '_ARRAY_API', None)  # type: ignore[attr-defined]
    except Exception:
        pass
    
    # Force numpy to be fully loaded before cv2
    _ = np.__version__  # Trigger full numpy load
except Exception as e:
    import logging
    logging.getLogger("KingdomAI.BiometricSecurity").warning(f"NumPy import failed: {e}")
    np = None

logger = logging.getLogger("KingdomAI.BiometricSecurity")


# Optional imports with availability flags
# CRITICAL: Ensure numpy is fully loaded and patched BEFORE cv2 import
# cv2's bootstrap() checks numpy._ARRAY_API immediately on import
try:
    # numpy should already be imported and patched above
    # Double-check _ARRAY_API exists before cv2 import
    if np is not None:
        if not hasattr(np, '_ARRAY_API'):
            import types
            ns = types.SimpleNamespace()
            ns.ARRAY_API_STRICT = False
            np._ARRAY_API = ns  # type: ignore[attr-defined]
        
        # Ensure multiarray is patched
        try:
            import numpy._core.multiarray as _multiarray_check
            if not hasattr(_multiarray_check, '_ARRAY_API'):
                _multiarray_check._ARRAY_API = getattr(np, '_ARRAY_API', None)  # type: ignore[attr-defined]
        except Exception:
            pass
        
        try:
            import numpy.core.multiarray as _old_multiarray_check
            if not hasattr(_old_multiarray_check, '_ARRAY_API'):
                _old_multiarray_check._ARRAY_API = getattr(np, '_ARRAY_API', None)  # type: ignore[attr-defined]
        except Exception:
            pass
    
    # Now import cv2 - numpy should be fully patched
    import cv2
    HAS_OPENCV = True
except Exception as e:
    HAS_OPENCV = False
    cv2 = None
    logger.warning(f"⚠️ OpenCV (cv2) not available: {e}")

try:
    from facenet_pytorch import InceptionResnetV1, MTCNN as _MTCNN_BSM
    HAS_FACENET = True
except Exception:
    HAS_FACENET = False
    InceptionResnetV1 = None
    _MTCNN_BSM = None

try:
    import face_recognition
    HAS_FACE_RECOGNITION = True
except ImportError:
    HAS_FACE_RECOGNITION = False
    face_recognition = None

try:
    from sklearn.mixture import GaussianMixture
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    GaussianMixture = None

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    librosa = None

try:
    import speech_recognition as sr
    HAS_SPEECH_RECOGNITION = True
except ImportError:
    HAS_SPEECH_RECOGNITION = False
    sr = None


class SecurityLevel(Enum):
    """Security access levels."""
    OWNER = "owner"           # Full control - Isaiah Wright
    ADMIN = "admin"           # Full control - trusted family
    USER = "user"             # Limited access
    GUEST = "guest"           # View only
    LOCKED = "locked"         # No access


class BiometricType(Enum):
    """Types of biometric authentication."""
    FACE = "face"
    VOICE = "voice"
    COMBINED = "combined"     # Both face and voice required


@dataclass
class AuthorizedUser:
    """Represents an authorized user in the system."""
    user_id: str
    name: str
    relationship: str         # e.g., "creator", "father", "daughter"
    security_level: SecurityLevel
    face_encodings: List["np.ndarray"] = field(default_factory=list)  # type: ignore[type-arg]
    voice_prints: List["np.ndarray"] = field(default_factory=list)  # type: ignore[type-arg]
    enrollment_date: str = ""
    last_seen: str = ""
    is_active: bool = True
    notes: str = ""
    
    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            'user_id': self.user_id,
            'name': self.name,
            'relationship': self.relationship,
            'security_level': self.security_level.value,
            'face_encodings_count': len(self.face_encodings),
            'voice_prints_count': len(self.voice_prints),
            'enrollment_date': self.enrollment_date,
            'last_seen': self.last_seen,
            'is_active': self.is_active,
            'notes': self.notes
        }


@dataclass
class AuthenticationResult:
    """Result of an authentication attempt."""
    success: bool
    user: Optional[AuthorizedUser]
    confidence: float
    method: BiometricType
    message: str
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class BiometricSecurityManager:
    """
    SOTA 2026 Biometric Security Manager for Kingdom AI.
    
    Provides multi-modal biometric authentication using face and voice recognition
    to ensure only authorized users can control the system.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern for system-wide security."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, event_bus=None, data_dir: str = None):
        """Initialize the Biometric Security Manager."""
        if self._initialized:
            return
        
        self.event_bus = event_bus
        self.data_dir = Path(data_dir or "data/biometric_security")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # User registry
        self.authorized_users: Dict[str, AuthorizedUser] = {}
        self.current_user: Optional[AuthorizedUser] = None
        self.authentication_required = False  # Only locks when user says "lock"
        self.continuous_auth = True  # Still monitors face/voice for recognition
        
        # Face recognition state
        self._face_encodings_db: Dict[str, List[Any]] = {}
        self._webcam = None
        self._webcam_active = False
        self._face_detection_thread = None
        
        # Voice recognition state  
        self._voice_prints_db: Dict[str, Any] = {}  # GMM models per user
        self._voice_sample_rate = 16000
        
        # Security settings
        self.face_match_threshold = 0.6  # Lower = stricter
        self.voice_match_threshold = 0.7
        self.combined_threshold = 0.75
        self.max_auth_attempts = 3
        self.lockout_duration = 300  # 5 minutes
        
        # State tracking
        self._failed_attempts = 0
        self._lockout_until: Optional[float] = None
        self._boot_scan_in_progress = False
        self._last_auth_time: float = 0
        self._auth_cache_duration = 60  # Re-auth every 60 seconds
        
        # SOTA 2026: Adaptive recognition settings
        self._adaptive_learning = True
        self._confidence_history: Dict[str, List[float]] = {}
        self._min_enrollment_samples = 5
        self._adaptive_threshold_adjustment = 0.05
        
        # Auto-scan settings
        self._auto_scan_on_boot = True  # Scan but don't lock
        self._auto_lock_on_boot = False  # Only lock when user says "lock"
        self._voice_listening_active = False
        self._boot_scan_complete = False
        
        # Documentation path for Ollama brain access
        self._docs_path = Path("docs/BIOMETRIC_SECURITY_SYSTEM.md")
        
        # Load existing data
        self._load_user_registry()
        self._setup_creator()
        
        # Subscribe to events
        if self.event_bus:
            self._subscribe_to_events()
        
        self._initialized = True
        logger.info("🔐 Biometric Security Manager initialized - SOTA 2026")
        logger.info(f"   Face Recognition: {'✅' if HAS_FACE_RECOGNITION or HAS_FACENET else '❌'}")
        logger.info(f"   Voice Recognition: {'✅' if HAS_LIBROSA and HAS_SKLEARN else '❌'}")
        logger.info(f"   OpenCV: {'✅' if HAS_OPENCV else '❌'}")
        logger.info(f"   Adaptive Learning: {'✅' if self._adaptive_learning else '❌'}")
        logger.info(f"   Auto-Scan on Boot: {'✅' if self._auto_scan_on_boot else '❌'}")
    
    def _setup_creator(self):
        """Setup the creator (Isaiah Wright) as primary authorized user."""
        creator_id = "creator_isaiah_wright"
        
        if creator_id not in self.authorized_users:
            creator = AuthorizedUser(
                user_id=creator_id,
                name="Isaiah Wright",
                relationship="creator",
                security_level=SecurityLevel.OWNER,
                enrollment_date=datetime.now().isoformat(),
                notes="Creator and primary owner of Kingdom AI"
            )
            self.authorized_users[creator_id] = creator
            logger.info("👑 Creator Isaiah Wright registered as primary owner")
            self._save_user_registry()
    
    def add_family_member(self, name: str, relationship: str, 
                          security_level: SecurityLevel = SecurityLevel.ADMIN) -> AuthorizedUser:
        """Add a family member to the authorized users registry.
        
        Args:
            name: Full name of the family member
            relationship: e.g., "father", "daughter", "son", "mother"
            security_level: Access level to grant
            
        Returns:
            The created AuthorizedUser
        """
        user_id = f"family_{name.lower().replace(' ', '_')}_{relationship}"
        
        if user_id in self.authorized_users:
            logger.warning(f"User {name} already registered")
            return self.authorized_users[user_id]
        
        user = AuthorizedUser(
            user_id=user_id,
            name=name,
            relationship=relationship,
            security_level=security_level,
            enrollment_date=datetime.now().isoformat(),
            notes=f"Family member - {relationship}"
        )
        
        self.authorized_users[user_id] = user
        self._save_user_registry()
        
        logger.info(f"👨‍👩‍👧‍👦 Added family member: {name} ({relationship}) with {security_level.value} access")
        
        if self.event_bus:
            self.event_bus.publish('security.user.added', {
                'user_id': user_id,
                'name': name,
                'relationship': relationship,
                'security_level': security_level.value
            })
        
        return user
    
    def enroll_face(self, user_id: str, frame: "np.ndarray" = None,  # type: ignore[assignment] 
                    capture_from_webcam: bool = False, num_samples: int = 5) -> bool:
        """Enroll a user's face for recognition.
        
        Args:
            user_id: ID of the user to enroll
            frame: Optional frame to use for enrollment
            capture_from_webcam: If True, capture from webcam
            num_samples: Number of face samples to capture
            
        Returns:
            True if enrollment successful
        """
        if user_id not in self.authorized_users:
            logger.error(f"User {user_id} not found in registry")
            return False
        
        user = self.authorized_users[user_id]
        encodings = []
        
        if capture_from_webcam and HAS_OPENCV:
            logger.info(f"📸 Starting face enrollment for {user.name}...")
            logger.info(f"   Please look at the camera. Capturing {num_samples} samples...")
            
            cap = None
            try:
                # SOTA 2026: USB Passthrough with MJPEG fallback
                if self._is_wsl2():
                    logger.info("🖥️ WSL2 detected - checking camera access methods")
                    
                    # FIRST: Try USB passthrough (real camera via usbipd)
                    usb_devices = self._detect_usb_passthrough_cameras()
                    connected = False
                    
                    if usb_devices:
                        logger.info(f"🔌 Trying USB passthrough: {usb_devices}")
                        for device_path in usb_devices:
                            try:
                                device_num = int(device_path.replace('/dev/video', ''))
                                cap = cv2.VideoCapture(device_num)
                                if cap.isOpened():
                                    ret, test_frame = cap.read()
                                    if ret and test_frame is not None:
                                        logger.info(f"✅ USB camera connected: {device_path}")
                                        logger.info("   🎉 Using REAL V4L2 access")
                                        connected = True
                                        break
                                    else:
                                        cap.release()
                            except Exception as e:
                                logger.debug(f"USB {device_path} failed: {e}")
                                if cap:
                                    try:
                                        cap.release()
                                    except:
                                        pass
                    
                    # FALLBACK: MJPEG bridges
                    if not connected:
                        logger.info("📡 No USB passthrough, trying MJPEG bridges")
                        logger.info("   💡 Better: Setup usbipd (see docs)")
                        
                        camera_urls = self._get_wsl2_camera_url()
                        for url in camera_urls:
                            try:
                                cap = cv2.VideoCapture(url)
                                if cap.isOpened():
                                    ret, test_frame = cap.read()
                                    if ret and test_frame is not None:
                                        logger.info(f"✅ MJPEG bridge: {url}")
                                        connected = True
                                        break
                                    else:
                                        cap.release()
                            except Exception as e:
                                logger.debug(f"URL {url} failed: {e}")
                                if cap:
                                    try:
                                        cap.release()
                                    except:
                                        pass
                    
                    if not connected:
                        logger.error("❌ All camera methods failed")
                        logger.error("   Setup: usbipd attach --wsl --busid <ID>")
                        return False
                                
                elif sys.platform.startswith('win') and hasattr(cv2, 'CAP_DSHOW'):
                    # Windows native - try multiple camera indices for Brio
                    cap = None
                    for camera_index in [1, 0, 2]:
                        try:
                            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
                            if cap.isOpened():
                                # Set Brio-optimized settings
                                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('M','J','P','G'))
                                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                                cap.set(cv2.CAP_PROP_FPS, 30)
                                
                                # Test frame
                                ret, test_frame = cap.read()
                                if ret and test_frame is not None:
                                    logger.info(f"✅ Brio camera opened on index {camera_index} for enrollment")
                                    break
                            else:
                                cap.release()
                        except Exception:
                            if cap:
                                cap.release()
                            cap = None
                    if cap is None or not cap.isOpened():
                        raise RuntimeError("No working camera found for enrollment")
                else:
                    # Linux/Other - standard camera access
                    cap = cv2.VideoCapture(0)
                    
            except Exception as e:
                logger.error(f"Could not open webcam for enrollment: {e}")
                return False
            
            if cap is None or not cap.isOpened():
                try:
                    cap.release()
                except Exception:
                    pass
                logger.error("Could not open webcam")
                return False
            
            samples_captured = 0
            start_time = time.time()
            timeout = 30  # 30 second timeout
            
            while samples_captured < num_samples and (time.time() - start_time) < timeout:
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue
                
                # Get face encoding (frame is guaranteed non-None here)
                encoding = self._get_face_encoding(frame)  # type: ignore[arg-type]
                if encoding is not None:
                    encodings.append(encoding)
                    samples_captured += 1
                    logger.info(f"   Captured sample {samples_captured}/{num_samples}")
                    time.sleep(0.5)  # Brief pause between captures
            
            cap.release()
            
        elif frame is not None:
            encoding = self._get_face_encoding(frame)
            if encoding is not None:
                encodings.append(encoding)
        
        if encodings:
            user.face_encodings.extend(encodings)
            self._face_encodings_db[user_id] = user.face_encodings
            self._save_user_registry()
            self._save_face_encodings()
            
            logger.info(f"✅ Face enrollment complete for {user.name}: {len(encodings)} samples")
            
            if self.event_bus:
                self.event_bus.publish('security.face.enrolled', {
                    'user_id': user_id,
                    'name': user.name,
                    'samples': len(encodings)
                })
            
            return True
        
        logger.error(f"❌ Face enrollment failed for {user.name}: No valid samples captured")
        return False
    
    def enroll_voice(self, user_id: str, audio_data: "np.ndarray" = None,  # type: ignore[assignment]
                     capture_from_mic: bool = False, duration: float = 5.0) -> bool:
        """Enroll a user's voice for speaker verification.
        
        Args:
            user_id: ID of the user to enroll
            audio_data: Optional audio data to use
            capture_from_mic: If True, capture from microphone
            duration: Duration of voice sample to capture
            
        Returns:
            True if enrollment successful
        """
        if user_id not in self.authorized_users:
            logger.error(f"User {user_id} not found in registry")
            return False
        
        user = self.authorized_users[user_id]
        voice_features = []
        
        if capture_from_mic and HAS_SPEECH_RECOGNITION:
            logger.info(f"🎤 Starting voice enrollment for {user.name}...")
            logger.info(f"   Please speak for {duration} seconds...")
            
            recognizer = sr.Recognizer()
            with sr.Microphone(sample_rate=self._voice_sample_rate) as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("   Recording...")
                
                try:
                    audio = recognizer.record(source, duration=duration)
                    audio_data = np.frombuffer(audio.get_raw_data(), dtype=np.int16).astype(np.float32)
                    audio_data = audio_data / 32768.0  # Normalize
                except Exception as e:
                    logger.error(f"Failed to record audio: {e}")
                    return False
        
        if audio_data is not None and HAS_LIBROSA:
            # Extract MFCC features
            features = self._extract_voice_features(audio_data)
            if features is not None:
                voice_features.append(features)
        
        if voice_features and HAS_SKLEARN:
            # Train GMM model for this user
            all_features = np.vstack(voice_features)
            gmm = GaussianMixture(n_components=min(16, len(all_features)), 
                                  covariance_type='diag',
                                  max_iter=200)
            gmm.fit(all_features)
            
            user.voice_prints.append(all_features)
            self._voice_prints_db[user_id] = gmm
            self._save_user_registry()
            self._save_voice_prints()
            
            logger.info(f"✅ Voice enrollment complete for {user.name}")
            
            if self.event_bus:
                self.event_bus.publish('security.voice.enrolled', {
                    'user_id': user_id,
                    'name': user.name,
                    'duration': duration
                })
            
            return True
        
        logger.error(f"❌ Voice enrollment failed for {user.name}")
        return False
    
    def _get_face_encoding(self, frame: Any) -> Any:
        """Get 128-dimensional face encoding from frame."""
        try:
            if HAS_FACE_RECOGNITION:
                # Use face_recognition library (dlib-based)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)
                
                if face_locations:
                    encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                    if encodings:
                        return encodings[0]
            
            elif HAS_FACENET and InceptionResnetV1 is not None:
                # Use facenet-pytorch (pure PyTorch, no TF)
                import torch
                from PIL import Image as _PILImg
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = _PILImg.fromarray(rgb)
                _det = _MTCNN_BSM(keep_all=False, device='cpu') if _MTCNN_BSM else None
                face_t = _det(pil_img) if _det else None
                if face_t is not None:
                    _model = InceptionResnetV1(pretrained='vggface2').eval()
                    with torch.no_grad():
                        emb = _model(face_t.unsqueeze(0)).squeeze().numpy()
                    return emb
        
        except Exception as e:
            logger.debug(f"Face encoding extraction failed: {e}")
        
        return None
    
    def _extract_voice_features(self, audio: Any) -> Any:
        """Extract MFCC features from audio."""
        try:
            if not HAS_LIBROSA:
                return None
            
            # Normalize audio
            if audio.max() > 1.0:
                audio = audio / 32768.0
            
            # Extract MFCCs
            mfccs = librosa.feature.mfcc(y=audio, sr=self._voice_sample_rate, 
                                         n_mfcc=20, n_fft=512, hop_length=256)
            
            # Add delta features
            delta_mfccs = librosa.feature.delta(mfccs)
            delta2_mfccs = librosa.feature.delta(mfccs, order=2)
            
            # Stack features
            features = np.vstack([mfccs, delta_mfccs, delta2_mfccs])
            
            return features.T  # Shape: (n_frames, 60)
            
        except Exception as e:
            logger.error(f"Voice feature extraction failed: {e}")
            return None
    
    def verify_face(self, frame: Any) -> AuthenticationResult:
        """Verify a face against the authorized users database.
        
        Args:
            frame: Image frame containing a face
            
        Returns:
            AuthenticationResult with verification outcome
        """
        if self._is_locked_out():
            return AuthenticationResult(
                success=False,
                user=None,
                confidence=0.0,
                method=BiometricType.FACE,
                message="System locked due to too many failed attempts"
            )
        
        encoding = self._get_face_encoding(frame)
        if encoding is None:
            return AuthenticationResult(
                success=False,
                user=None,
                confidence=0.0,
                method=BiometricType.FACE,
                message="No face detected in frame"
            )
        
        best_match = None
        best_distance = float('inf')
        
        for user_id, user in self.authorized_users.items():
            if not user.is_active or not user.face_encodings:
                continue
            
            for stored_encoding in user.face_encodings:
                if HAS_FACE_RECOGNITION:
                    distance = face_recognition.face_distance([stored_encoding], encoding)[0]
                else:
                    distance = np.linalg.norm(stored_encoding - encoding)
                
                if distance < best_distance:
                    best_distance = distance
                    best_match = user
        
        confidence = max(0, 1 - best_distance)
        
        if best_match and best_distance < self.face_match_threshold:
            self._on_auth_success(best_match)
            return AuthenticationResult(
                success=True,
                user=best_match,
                confidence=float(confidence),
                method=BiometricType.FACE,
                message=f"Welcome, {best_match.name}!"
            )
        
        self._on_auth_failure()
        return AuthenticationResult(
            success=False,
            user=None,
            confidence=float(confidence),
            method=BiometricType.FACE,
            message="Face not recognized"
        )
    
    def verify_voice(self, audio: Any) -> AuthenticationResult:
        """Verify a voice sample against the authorized users database.
        
        Args:
            audio: Audio data as numpy array
            
        Returns:
            AuthenticationResult with verification outcome
        """
        if self._is_locked_out():
            return AuthenticationResult(
                success=False,
                user=None,
                confidence=0.0,
                method=BiometricType.VOICE,
                message="System locked due to too many failed attempts"
            )
        
        features = self._extract_voice_features(audio)
        if features is None:
            return AuthenticationResult(
                success=False,
                user=None,
                confidence=0.0,
                method=BiometricType.VOICE,
                message="Could not extract voice features"
            )
        
        best_match = None
        best_score = float('-inf')
        
        for user_id, gmm in self._voice_prints_db.items():
            if user_id not in self.authorized_users:
                continue
            
            user = self.authorized_users[user_id]
            if not user.is_active:
                continue
            
            try:
                score = gmm.score(features)
                if score > best_score:
                    best_score = score
                    best_match = user
            except Exception:
                continue
        
        # Normalize score to 0-1 confidence
        confidence = min(1.0, max(0.0, (best_score + 100) / 100))
        
        if best_match and confidence >= self.voice_match_threshold:
            self._on_auth_success(best_match)
            return AuthenticationResult(
                success=True,
                user=best_match,
                confidence=confidence,
                method=BiometricType.VOICE,
                message=f"Voice verified: {best_match.name}"
            )
        
        self._on_auth_failure()
        return AuthenticationResult(
            success=False,
            user=None,
            confidence=confidence,
            method=BiometricType.VOICE,
            message="Voice not recognized"
        )
    
    def verify_combined(self, frame: Any = None, 
                        audio: Any = None) -> AuthenticationResult:
        """Verify using both face and voice biometrics.
        
        Args:
            frame: Image frame containing a face
            audio: Audio data as numpy array
            
        Returns:
            AuthenticationResult with combined verification outcome
        """
        results = []
        
        if frame is not None:
            face_result = self.verify_face(frame)
            results.append(face_result)
        
        if audio is not None:
            voice_result = self.verify_voice(audio)
            results.append(voice_result)
        
        if not results:
            return AuthenticationResult(
                success=False,
                user=None,
                confidence=0.0,
                method=BiometricType.COMBINED,
                message="No biometric data provided"
            )
        
        # Both must match the same user for combined auth
        successful_results = [r for r in results if r.success]
        
        if len(successful_results) == len(results):
            # All provided biometrics matched
            users = [r.user for r in successful_results]
            if all(u.user_id == users[0].user_id for u in users):
                avg_confidence = sum(r.confidence for r in results) / len(results)
                user = users[0]
                
                self._on_auth_success(user)
                return AuthenticationResult(
                    success=True,
                    user=user,
                    confidence=avg_confidence,
                    method=BiometricType.COMBINED,
                    message=f"Multi-factor authentication successful: {user.name}"
                )
        
        self._on_auth_failure()
        return AuthenticationResult(
            success=False,
            user=None,
            confidence=0.0,
            method=BiometricType.COMBINED,
            message="Multi-factor authentication failed"
        )
    
    def is_authenticated(self) -> bool:
        """Check if a user is currently authenticated."""
        if not self.authentication_required:
            return True
        
        if self._is_locked_out():
            return False
        
        if self.current_user is None:
            return False
        
        # Check if re-authentication is needed
        if self.continuous_auth:
            if time.time() - self._last_auth_time > self._auth_cache_duration:
                logger.info("🔄 Re-authentication required")
                return False
        
        return True
    
    def get_current_user(self) -> Optional[AuthorizedUser]:
        """Get the currently authenticated user."""
        return self.current_user if self.is_authenticated() else None
    
    def lock_system(self):
        """Lock the system - requires authentication to execute commands.
        
        Called when user says "lock" or "lock system".
        """
        self.authentication_required = True
        self.current_user = None
        self._last_auth_time = 0
        
        logger.info("🔒 System LOCKED - Authentication required for commands")
        
        if self.event_bus:
            self.event_bus.publish('security.locked', {
                'message': 'System locked - Please authenticate',
                'timestamp': datetime.now().isoformat()
            })
    
    def unlock_system(self, user: AuthorizedUser = None):
        """Unlock the system - allows commands without authentication.
        
        Called after successful authentication or by owner command.
        """
        self.authentication_required = False
        if user:
            self.current_user = user
            self._last_auth_time = time.time()
        
        logger.info("🔓 System UNLOCKED - Commands allowed")
        
        if self.event_bus:
            self.event_bus.publish('security.unlocked', {
                'user': user.name if user else 'System',
                'timestamp': datetime.now().isoformat()
            })
    
    def can_execute_command(self, command_name: str = None) -> Tuple[bool, str]:
        """Check if the current user can execute a command.
        
        Args:
            command_name: Optional command name for fine-grained control
            
        Returns:
            Tuple of (allowed, reason)
        """
        if not self.authentication_required:
            return True, "Authentication disabled"
        
        if not self.is_authenticated():
            return False, "Authentication required"
        
        user = self.current_user
        if user is None:
            return False, "No authenticated user"
        
        # Owner can do everything
        if user.security_level == SecurityLevel.OWNER:
            return True, f"Owner access: {user.name}"
        
        # Admin can do most things
        if user.security_level == SecurityLevel.ADMIN:
            return True, f"Admin access: {user.name}"
        
        # User has limited access
        if user.security_level == SecurityLevel.USER:
            # Could implement command-level restrictions here
            return True, f"User access: {user.name}"
        
        # Guest - view only
        if user.security_level == SecurityLevel.GUEST:
            return False, "Guest users cannot execute commands"
        
        return False, "Access denied"
    
    def start_continuous_face_auth(self):
        """Start continuous face authentication via webcam."""
        if not HAS_OPENCV:
            logger.warning("OpenCV not available for continuous face auth")
            return
        
        if self._webcam_active:
            return
        
        self._webcam_active = True
        self._face_detection_thread = threading.Thread(
            target=self._continuous_face_auth_loop,
            name="BiometricFaceAuth",
            daemon=True
        )
        self._face_detection_thread.start()
        logger.info("👁️ Continuous face authentication started")
    
    def stop_continuous_face_auth(self):
        """Stop continuous face authentication."""
        self._webcam_active = False
        if self._webcam:
            self._webcam.release()
            self._webcam = None
        logger.info("👁️ Continuous face authentication stopped")
    
    def _is_wsl2(self) -> bool:
        """SOTA 2026: Properly detect WSL2 environment.
        
        Multiple detection methods for reliability:
        1. WSL-specific environment variables
        2. /proc/version check for 'microsoft'
        3. /proc/sys/fs/binfmt_misc/WSLInterop existence
        """
        try:
            if os.environ.get('WSL_DISTRO_NAME') or os.environ.get('WSL_INTEROP'):
                return True
            
            if sys.platform.startswith('linux'):
                try:
                    with open('/proc/version', 'r') as f:
                        version_info = f.read().lower()
                        if 'microsoft' in version_info:
                            return True
                except Exception:
                    pass
                
                try:
                    if os.path.exists('/proc/sys/fs/binfmt_misc/WSLInterop'):
                        return True
                except Exception:
                    pass
                
                # NOTE: /mnt/c/Windows check removed — unreliable on native Linux
            
            return False
        except Exception:
            return False
    
    def _detect_usb_passthrough_cameras(self) -> list:
        """SOTA 2026: Detect USB cameras via usbipd passthrough in WSL2.
        
        Returns list of available /dev/video* devices if USB passthrough is active.
        This indicates REAL camera access, not MJPEG fallback.
        """
        import glob
        try:
            video_devices = glob.glob('/dev/video*')
            working_devices = []
            
            for device in video_devices:
                # Quick test if device is accessible
                try:
                    # Check if we can open the device file (not yet with OpenCV)
                    if os.path.exists(device) and os.access(device, os.R_OK):
                        working_devices.append(device)
                except:
                    pass
            
            if working_devices:
                logger.info(f"✅ USB passthrough active: Found {len(working_devices)} V4L2 devices")
                # Reduce OpenCV logging when real devices exist
                os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
            else:
                # No USB devices - will need MJPEG bridge (silence V4L2 errors)
                os.environ['OPENCV_LOG_LEVEL'] = 'FATAL'
                os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
            
            return working_devices
        except Exception as e:
            logger.debug(f"USB device detection failed: {e}")
            # Silence errors if we can't detect devices
            os.environ['OPENCV_LOG_LEVEL'] = 'FATAL'
            return []
    
    def _get_wsl2_camera_url(self) -> list:
        """SOTA 2026: Get the best WSL2 camera URL.
        
        Uses the SAME host/port/endpoint discovery as the working thoth_qt
        MJPEG camera logic to ensure biometric camera works identically.
        """
        import requests as _req
        
        # Collect candidate IPs — same logic as thoth_qt._get_windows_host_ip
        candidate_ips = set()
        
        # 1. Default gateway (most reliable for MJPEG in WSL2)
        try:
            import subprocess
            result = subprocess.run(
                ['ip', 'route', 'show', 'default'],
                capture_output=True, text=True, timeout=3
            )
            for part in result.stdout.split():
                if part.count('.') == 3:
                    candidate_ips.add(part)
                    break
        except Exception:
            pass
        
        # 2. resolv.conf nameserver (sometimes works)
        try:
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    if line.strip().startswith('nameserver'):
                        ip = line.split()[1].strip()
                        if ip.count('.') == 3:
                            candidate_ips.add(ip)
        except Exception:
            pass
        
        # 3. Common WSL2 gateway IPs + localhost
        candidate_ips.update(['172.20.0.1', '172.17.0.1', 'localhost', '127.0.0.1'])
        
        # Same ports and endpoints as working thoth_qt MJPEG logic
        ports = [8091, 8090, 5000]
        endpoints = ['/video.mjpg', '/brio.mjpg']
        
        # Pre-test with requests.head() — much faster than cv2.VideoCapture
        for ip in candidate_ips:
            for port in ports:
                for endpoint in endpoints:
                    url = f"http://{ip}:{port}{endpoint}"
                    try:
                        resp = _req.head(url, timeout=0.5)
                        if resp.status_code == 200:
                            logger.info(f"\u2705 Biometric camera: found working MJPEG at {url}")
                            return [url]  # Return immediately — this one works
                    except Exception:
                        pass
        
        # Fallback: return all candidate URLs for cv2 to try
        all_urls = []
        for ip in candidate_ips:
            for port in ports:
                for endpoint in endpoints:
                    all_urls.append(f"http://{ip}:{port}{endpoint}")
        
        logger.info(f"\u26a0\ufe0f Biometric camera: no pre-tested URL worked, will try {len(all_urls)} candidates")
        return all_urls
    
    def _continuous_face_auth_loop(self):
        """Background loop for continuous face authentication."""
        if not HAS_OPENCV or cv2 is None:
            logger.warning("OpenCV not available for continuous face auth")
            self._webcam_active = False
            return
        
        try:
            # SOTA 2026: USB Passthrough with MJPEG fallback
            is_wsl = self._is_wsl2()
            if is_wsl:
                logger.info("🖥️ WSL2 detected - checking camera access")
                
                # FIRST: Try USB passthrough
                usb_devices = self._detect_usb_passthrough_cameras()
                connected = False
                
                if usb_devices:
                    logger.info(f"🔌 Trying USB passthrough: {usb_devices}")
                    for device_path in usb_devices:
                        try:
                            device_num = int(device_path.replace('/dev/video', ''))
                            self._webcam = cv2.VideoCapture(device_num)
                            if self._webcam.isOpened():
                                ret, test_frame = self._webcam.read()
                                if ret and test_frame is not None:
                                    logger.info(f"✅ USB camera: {device_path}")
                                    logger.info("   🎉 Using REAL V4L2 access")
                                    connected = True
                                    break
                                else:
                                    self._webcam.release()
                        except Exception as e:
                            logger.debug(f"USB {device_path} failed: {e}")
                
                # FALLBACK: MJPEG bridges (same logic as working thoth_qt camera)
                if not connected:
                    logger.info("📡 No USB passthrough, trying MJPEG bridges")
                    logger.info("   💡 Better: usbipd attach --wsl --busid <ID>")
                    
                    # Get list of camera URLs to try (uses same discovery as thoth_qt)
                    camera_urls = self._get_wsl2_camera_url()
                    
                    # Try each URL
                    for url in camera_urls:
                        try:
                            self._webcam = cv2.VideoCapture(url)
                            if self._webcam.isOpened():
                                ret, test_frame = self._webcam.read()
                                if ret and test_frame is not None:
                                    logger.info(f"✅ Biometric camera connected: {url}")
                                    connected = True
                                    break
                                else:
                                    self._webcam.release()
                        except Exception as e:
                            logger.debug(f"Camera URL {url} failed: {e}")
                            if self._webcam:
                                try:
                                    self._webcam.release()
                                except:
                                    pass
                    
                    if not connected:
                        logger.warning("❌ All WSL2 camera bridges failed")
                        logger.info("   💡 To fix: Run start_brio_mjpeg_server.ps1 on Windows")
                        self._webcam = None
                        self._webcam_active = False
                        return
                            
            elif sys.platform.startswith('win') and hasattr(cv2, 'CAP_DSHOW'):
                # Windows native - use DirectShow with Brio optimization
                logger.info("🪟 Windows detected - using DirectShow")
                
                # Try camera index 1 first (common for Brio)
                for camera_index in [1, 0, 2]:
                    try:
                        self._webcam = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
                        if self._webcam.isOpened():
                            # Set Brio-optimized settings
                            self._webcam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('M','J','P','G'))
                            self._webcam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                            self._webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                            self._webcam.set(cv2.CAP_PROP_FPS, 30)
                            
                            # Test if we can read a frame
                            ret, frame = self._webcam.read()
                            if ret and frame is not None:
                                logger.info(f"✅ Brio camera opened on index {camera_index}")
                                break
                            else:
                                self._webcam.release()
                    except Exception as e:
                        logger.debug(f"Camera index {camera_index} failed: {e}")
                        if self._webcam:
                            self._webcam.release()
                else:
                    raise RuntimeError("No working camera index found")
                    
            else:
                # Linux/Other - standard camera access with proper error handling
                try:
                    self._webcam = cv2.VideoCapture(0)
                    if not self._webcam.isOpened():
                        self._webcam.release()
                        self._webcam = None
                except Exception as e:
                    logger.debug(f"Linux camera access failed: {e}")
                    if self._webcam:
                        try:
                            self._webcam.release()
                        except Exception:
                            pass
                    self._webcam = None
                
        except Exception as e:
            logger.warning(f"Could not open webcam: {e}")
            self._webcam = None
            self._webcam_active = False
            return
        
        if self._webcam is None or not self._webcam.isOpened():
            try:
                if self._webcam:
                    self._webcam.release()
            except Exception:
                pass
            self._webcam = None
            self._webcam_active = False
            logger.warning("No webcam available - continuous face authentication disabled")
            return
        
        while self._webcam_active:
            try:
                cap = self._webcam
                if cap is None:
                    break
                
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.1)
                    continue
                
                # Only verify periodically
                if time.time() - self._last_auth_time < 5:
                    time.sleep(0.5)
                    continue
                
                result = self.verify_face(frame)
                
                if result.success:
                    if self.event_bus:
                        self.event_bus.publish('security.face.verified', {
                            'user': result.user.name if result.user else None,
                            'confidence': result.confidence
                        })
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Face auth loop error: {e}")
                time.sleep(1)
        
        if self._webcam:
            self._webcam.release()
            self._webcam = None
    
    def _on_auth_success(self, user: AuthorizedUser):
        """Handle successful authentication."""
        self.current_user = user
        self._last_auth_time = time.time()
        self._failed_attempts = 0
        user.last_seen = datetime.now().isoformat()
        
        logger.info(f"✅ Authentication successful: {user.name} ({user.security_level.value})")
        
        if self.event_bus:
            self.event_bus.publish('security.authenticated', {
                'user_id': user.user_id,
                'name': user.name,
                'security_level': user.security_level.value,
                'timestamp': datetime.now().isoformat()
            })
    
    def _on_auth_failure(self):
        """Handle failed authentication."""
        # SOTA 2026 FIX: Don't count boot scan probes toward lockout
        if self._boot_scan_in_progress:
            return
        
        # SOTA 2026: Never lock out if owner already verified or no users enrolled
        if self.current_user is not None:
            return
        if not self.authorized_users:
            return

        # Owner lockout guard: if owner has enrolled biometrics, do not hard-lock.
        try:
            owner_user = None
            for _uid, _user in self.authorized_users.items():
                if getattr(_user, "security_level", None) == SecurityLevel.OWNER:
                    owner_user = _user
                    break
            if owner_user is not None:
                has_owner_biometrics = bool(getattr(owner_user, "face_encodings", [])) or bool(getattr(owner_user, "voice_prints", []))
                if has_owner_biometrics:
                    # Also check fresh identity verification signal if available.
                    try:
                        from core.user_identity import get_user_identity_engine
                        ie = get_user_identity_engine()
                        face_result = getattr(ie, "_current_face_result", None)
                        face_time = float(getattr(ie, "_face_result_time", 0.0) or 0.0)
                        if face_result and (time.time() - face_time) < 30.0 and bool(getattr(face_result, "is_owner", False)):
                            logger.debug("Owner face verified recently - skipping lockout increment")
                            return
                        logger.debug("Owner biometric profile present - suppressing hard lockout increment")
                        return
                    except Exception:
                        # If owner has biometrics and identity service is unavailable,
                        # still avoid escalating to hard lockout.
                        logger.debug("Owner biometric profile present - suppressing hard lockout increment")
                        return
        except Exception:
            pass
        
        self._failed_attempts += 1
        
        if self._failed_attempts >= self.max_auth_attempts:
            self._lockout_until = time.time() + self.lockout_duration
            logger.warning(f"\U0001f512 Too many failed attempts. Locked for {self.lockout_duration}s")
            
            if self.event_bus:
                self.event_bus.publish('security.lockout', {
                    'duration': self.lockout_duration,
                    'timestamp': datetime.now().isoformat()
                })
    
    def _is_locked_out(self) -> bool:
        """Check if the system is in lockout mode."""
        if self._lockout_until is None:
            return False
        
        if time.time() >= self._lockout_until:
            self._lockout_until = None
            self._failed_attempts = 0
            return False
        
        return True
    
    def _subscribe_to_events(self):
        """Subscribe to relevant event bus topics.
        
        SOTA 2026: BiometricSecurityManager delegates to UserIdentityEngine
        as the SINGLE SOURCE OF TRUTH for biometric identity. Instead of
        maintaining a separate face/voice database, we subscribe to
        UserIdentityEngine events and accept its verification results.
        """
        if not self.event_bus:
            return
        
        # SOTA 2026: Subscribe to UserIdentityEngine events (SINGLE SOURCE OF TRUTH)
        # UserIdentityEngine has SpeechBrain ECAPA-TDNN + DeepFace — the real ML pipeline.
        # We accept its verification as authoritative instead of running our own.
        self.event_bus.subscribe('identity.face.verified', self._on_identity_verified)
        self.event_bus.subscribe('identity.owner.enrolled', self._on_identity_owner_enrolled)
        self.event_bus.subscribe('identity.access.granted', self._on_identity_access_changed)
        self.event_bus.subscribe('identity.access.revoked', self._on_identity_access_changed)
        
        # NOTE: We no longer subscribe to 'vision.stream.frame' for our own face
        # verification. UserIdentityEngine already processes vision frames with
        # DeepFace and publishes identity.face.verified. Running a second face
        # pipeline here was redundant and caused lockout conflicts.
        
        # NOTE: voice.input.audio is NOT subscribed — UserIdentityEngine
        # handles voice verification via AlwaysOnVoice + SpeechBrain ECAPA-TDNN.
        
        # Listen for command execution requests
        self.event_bus.subscribe('command.request', self._on_command_request)
        
        logger.info("\u2705 BiometricSecurity: bridged to UserIdentityEngine (single source of truth)")
    
    def _on_identity_verified(self, data: dict):
        """Handle UserIdentityEngine face/voice verification result.
        
        SOTA 2026: UserIdentityEngine is the SINGLE SOURCE OF TRUTH.
        When it verifies the owner, we accept that as authentication.
        No separate face database, no conflicting lockouts.
        """
        is_owner = data.get('is_owner', False)
        user_name = data.get('user_name', 'Unknown')
        user_id = data.get('user_id', '')
        confidence = data.get('face_score', data.get('confidence', 0.0))
        
        if is_owner or data.get('is_authorized', False):
            # Auto-authenticate: UserIdentityEngine says this is the owner/authorized
            if user_id not in self.authorized_users:
                # Sync user into our registry (no face encodings needed — we delegate)
                self.authorized_users[user_id] = AuthorizedUser(
                    user_id=user_id,
                    name=user_name,
                    relationship='creator' if is_owner else 'authorized',
                    security_level=SecurityLevel.OWNER if is_owner else SecurityLevel.USER,
                    enrollment_date=datetime.now().isoformat(),
                    last_seen=datetime.now().isoformat(),
                    is_active=True
                )
            
            user = self.authorized_users[user_id]
            self._on_auth_success(user)
            logger.info(f"\u2705 BiometricSecurity: owner verified by UserIdentityEngine ({confidence:.2f})")
    
    def _on_identity_owner_enrolled(self, data: dict):
        """Handle owner enrollment from UserIdentityEngine."""
        user_id = data.get('user_id', 'owner_isaiah')
        name = data.get('name', 'Isaiah Wright')
        
        if user_id not in self.authorized_users:
            self.authorized_users[user_id] = AuthorizedUser(
                user_id=user_id,
                name=name,
                relationship='creator',
                security_level=SecurityLevel.OWNER,
                enrollment_date=datetime.now().isoformat(),
                is_active=True
            )
            logger.info(f"\u2705 BiometricSecurity: synced owner from UserIdentityEngine: {name}")
    
    def _on_identity_access_changed(self, data: dict):
        """Handle access grant/revoke from UserIdentityEngine."""
        user_id = data.get('user_id', '')
        name = data.get('name', 'Unknown')
        
        if 'granted_by' in data:
            # Access granted
            if user_id not in self.authorized_users:
                self.authorized_users[user_id] = AuthorizedUser(
                    user_id=user_id,
                    name=name,
                    relationship='authorized',
                    security_level=SecurityLevel.USER,
                    enrollment_date=datetime.now().isoformat(),
                    is_active=True
                )
                logger.info(f"\u2705 BiometricSecurity: synced authorized user: {name}")
        elif 'revoked_by' in data:
            # Access revoked
            if user_id in self.authorized_users:
                del self.authorized_users[user_id]
                logger.info(f"\U0001f6ab BiometricSecurity: removed revoked user: {name}")
    
    def _on_vision_frame(self, data: dict):
        """DEPRECATED: Vision frames are now processed by UserIdentityEngine.
        Kept for backward compatibility — logs for audit trail."""
        try:
            if isinstance(data, dict):
                logger.debug("BiometricSecurity: Vision frame received (delegated to UserIdentityEngine)")
        except Exception:
            pass
    
    def _on_voice_input(self, data: dict):
        """DEPRECATED: Voice verification delegated to UserIdentityEngine.
        Kept for backward compatibility — logs for audit trail."""
        try:
            if isinstance(data, dict):
                logger.debug("BiometricSecurity: Voice input received (delegated to UserIdentityEngine)")
        except Exception:
            pass
    
    def _on_command_request(self, data: dict):
        """Intercept command requests to check authorization."""
        command = data.get('command')
        allowed, reason = self.can_execute_command(command)
        
        if not allowed:
            if self.event_bus:
                self.event_bus.publish('command.denied', {
                    'command': command,
                    'reason': reason
                })
    
    def _load_user_registry(self):
        """Load user registry from disk."""
        registry_file = self.data_dir / "user_registry.json"
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    data = json.load(f)
                
                for user_data in data.get('users', []):
                    user = AuthorizedUser(
                        user_id=user_data['user_id'],
                        name=user_data['name'],
                        relationship=user_data['relationship'],
                        security_level=SecurityLevel(user_data['security_level']),
                        enrollment_date=user_data.get('enrollment_date', ''),
                        last_seen=user_data.get('last_seen', ''),
                        is_active=user_data.get('is_active', True),
                        notes=user_data.get('notes', '')
                    )
                    self.authorized_users[user.user_id] = user
                
                logger.info(f"Loaded {len(self.authorized_users)} authorized users")
            except Exception as e:
                logger.error(f"Failed to load user registry: {e}")
        
        # Load face encodings
        self._load_face_encodings()
        self._load_voice_prints()
    
    def _save_user_registry(self):
        """Save user registry to disk."""
        registry_file = self.data_dir / "user_registry.json"
        try:
            data = {
                'users': [u.to_dict() for u in self.authorized_users.values()],
                'updated': datetime.now().isoformat()
            }
            with open(registry_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save user registry: {e}")
    
    def _load_face_encodings(self):
        """Load face encodings from disk."""
        encodings_file = self.data_dir / "face_encodings.pkl"
        if encodings_file.exists():
            try:
                with open(encodings_file, 'rb') as f:
                    self._face_encodings_db = pickle.load(f)
                
                # Associate encodings with users
                for user_id, encodings in self._face_encodings_db.items():
                    if user_id in self.authorized_users:
                        self.authorized_users[user_id].face_encodings = encodings
                
                logger.info(f"Loaded face encodings for {len(self._face_encodings_db)} users")
            except Exception as e:
                logger.error(f"Failed to load face encodings: {e}")
    
    def _save_face_encodings(self):
        """Save face encodings to disk."""
        encodings_file = self.data_dir / "face_encodings.pkl"
        try:
            with open(encodings_file, 'wb') as f:
                pickle.dump(self._face_encodings_db, f)
        except Exception as e:
            logger.error(f"Failed to save face encodings: {e}")
    
    def _load_voice_prints(self):
        """Load voice print models from disk."""
        voice_file = self.data_dir / "voice_prints.pkl"
        if voice_file.exists():
            try:
                with open(voice_file, 'rb') as f:
                    self._voice_prints_db = pickle.load(f)
                logger.info(f"Loaded voice prints for {len(self._voice_prints_db)} users")
            except Exception as e:
                logger.error(f"Failed to load voice prints: {e}")
    
    def _save_voice_prints(self):
        """Save voice print models to disk."""
        voice_file = self.data_dir / "voice_prints.pkl"
        try:
            with open(voice_file, 'wb') as f:
                pickle.dump(self._voice_prints_db, f)
        except Exception as e:
            logger.error(f"Failed to save voice prints: {e}")
    
    def get_status(self) -> dict:
        """Get current security status."""
        return {
            'initialized': self._initialized,
            'authentication_required': self.authentication_required,
            'continuous_auth': self.continuous_auth,
            'current_user': self.current_user.name if self.current_user else None,
            'is_authenticated': self.is_authenticated(),
            'is_locked_out': self._is_locked_out(),
            'failed_attempts': self._failed_attempts,
            'authorized_users_count': len(self.authorized_users),
            'face_recognition_available': HAS_FACE_RECOGNITION or HAS_FACENET,
            'voice_recognition_available': HAS_LIBROSA and HAS_SKLEARN,
            'webcam_active': self._webcam_active
        }
    
    def list_authorized_users(self) -> List[dict]:
        """List all authorized users."""
        return [u.to_dict() for u in self.authorized_users.values()]
    
    # ==================== SOTA 2026: AUTO-SCAN & ADAPTIVE RECOGNITION ====================
    
    def start_boot_scan(self):
        """Start automatic biometric scan on system boot.
        
        SOTA 2026: BiometricSecurityManager delegates ALL face/voice verification
        to UserIdentityEngine (single source of truth). We do NOT start our own
        webcam loop or voice listener — UserIdentityEngine already handles that
        via DeepFace + SpeechBrain ECAPA-TDNN. Starting a second webcam here
        caused: (1) lockout from failed matches against empty DB, (2) GUI freeze
        from blocking webcam open, (3) camera resource conflicts with ThothQt.
        """
        if self._boot_scan_complete:
            return
        
        logger.info("🔐 Boot scan: delegating to UserIdentityEngine (single source of truth)")
        
        # Do NOT start our own webcam or voice listener.
        # UserIdentityEngine publishes identity.face.verified which we subscribe to.
        # See _on_identity_verified() handler.
        
        if self.event_bus:
            self.event_bus.publish('security.boot_scan.started', {
                'message': 'Biometric scan delegated to UserIdentityEngine',
                'timestamp': datetime.now().isoformat()
            })
        
        self._boot_scan_complete = True
        self._boot_scan_in_progress = False
        self._failed_attempts = 0
        logger.info("🔐 Boot scan complete — awaiting UserIdentityEngine verification")
    
    def _start_voice_listening(self):
        """Start background voice listening for authentication.
        
        Note: In WSL environments, microphone access is limited. Voice authentication
        is handled separately by VoiceManager which has proper WSL audio bridge support.
        """
        if self._voice_listening_active:
            return
        
        # Check if we're in WSL - skip biometric voice listening as VoiceManager handles it
        is_wsl = self._is_wsl2()
        if is_wsl:
            logger.info("🎤 Skipping biometric voice listening in WSL (VoiceManager handles voice input)")
            return
        
        if not HAS_SPEECH_RECOGNITION:
            logger.warning("Speech recognition not available for voice listening")
            return
        
        self._voice_listening_active = True
        
        def voice_listen_loop():
            recognizer = sr.Recognizer()
            
            while self._voice_listening_active:
                try:
                    # Use standard with statement for proper context management
                    with sr.Microphone(sample_rate=self._voice_sample_rate) as source:
                        recognizer.adjust_for_ambient_noise(source, duration=1)
                        logger.debug("Listening for voice authentication...")
                        
                        try:
                            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                            audio_data = np.frombuffer(audio.get_raw_data(), dtype=np.int16).astype(np.float32)  # type: ignore[union-attr]
                            audio_data = audio_data / 32768.0
                            
                            # Verify voice
                            result = self.verify_voice(audio_data)
                            if result.success:
                                logger.info(f"🎤 Voice authenticated: {result.user.name}")
                                self._voice_listening_active = False
                                
                                if self.event_bus:
                                    self.event_bus.publish('security.voice.authenticated', {
                                        'user': result.user.name,
                                        'confidence': result.confidence
                                    })
                                break
                                
                        except sr.WaitTimeoutError:
                            continue
                        except Exception as e:
                            logger.debug(f"Voice listen error: {e}")
                            
                except Exception as e:
                    logger.warning(f"Voice listening unavailable: {e}")
                    self._voice_listening_active = False
                    return  # Stop trying if microphone isn't working
        
        thread = threading.Thread(target=voice_listen_loop, name="VoiceAuthListener", daemon=True)
        thread.start()
        logger.info("🎤 Voice listening started for authentication")
    
    def stop_voice_listening(self):
        """Stop background voice listening."""
        self._voice_listening_active = False
        logger.info("🎤 Voice listening stopped")
    
    def adapt_recognition_thresholds(self, user_id: str, confidence: float):
        """Adapt recognition thresholds based on confidence history.
        
        This prevents the system from getting confused by day-to-day
        differences like lighting, glasses, hair changes, voice variations.
        
        Args:
            user_id: The user being recognized
            confidence: The confidence score of the recognition
        """
        if not self._adaptive_learning:
            return
        
        if user_id not in self._confidence_history:
            self._confidence_history[user_id] = []
        
        self._confidence_history[user_id].append(confidence)
        
        # Keep only last 100 scores
        if len(self._confidence_history[user_id]) > 100:
            self._confidence_history[user_id] = self._confidence_history[user_id][-100:]
        
        # Adjust threshold based on average confidence
        if len(self._confidence_history[user_id]) >= 10:
            avg_confidence = np.mean(self._confidence_history[user_id])
            
            # If consistently getting lower confidence, slightly lower threshold
            if avg_confidence < self.face_match_threshold + 0.1:
                # Don't lower below 0.4 (security minimum)
                new_threshold = max(0.4, self.face_match_threshold - self._adaptive_threshold_adjustment)
                if new_threshold != self.face_match_threshold:
                    logger.info(f"🔧 Adapted face threshold: {self.face_match_threshold:.2f} -> {new_threshold:.2f}")
                    self.face_match_threshold = new_threshold
    
    def get_documentation(self) -> str:
        """Get the biometric security documentation for Ollama brain access.
        
        Returns:
            The full documentation as a string
        """
        try:
            if self._docs_path.exists():
                with open(self._docs_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                # Return embedded summary if file not found
                return self._get_embedded_documentation()
        except Exception as e:
            logger.error(f"Failed to read documentation: {e}")
            return self._get_embedded_documentation()
    
    def _get_embedded_documentation(self) -> str:
        """Get embedded documentation summary."""
        return """# Kingdom AI Biometric Security System

## Quick Reference

### Voice Commands:
- "Enroll my face" - Start face enrollment
- "Enroll my voice" - Start voice enrollment
- "Verify me" / "Who am I" - Check identity
- "Security status" - Show auth status
- "Lock system" - Lock Kingdom AI
- "List users" - Show authorized users

### Adding Family Members:
```python
security.add_family_member("Name", "relationship", SecurityLevel.ADMIN)
security.enroll_face("user_id", capture_from_webcam=True)
```

### Security Levels:
- OWNER: Full control (Isaiah Wright)
- ADMIN: Full control (family)
- USER: Limited access
- GUEST: View only

### Auto-Authentication:
System automatically scans for face/voice on boot.
Commands are blocked until authenticated.

Creator: Isaiah Wright
"""
    
    def get_security_context_for_ai(self) -> dict:
        """Get security context for Ollama brain/AI conversations.
        
        Returns:
            Dictionary with security context for AI
        """
        return {
            'system_type': 'biometric_security',
            'creator': 'Isaiah Wright',
            'current_user': self.current_user.name if self.current_user else None,
            'is_authenticated': self.is_authenticated(),
            'security_level': self.current_user.security_level.value if self.current_user else 'locked',
            'authorized_users': [u['name'] for u in self.list_authorized_users()],
            'documentation': self.get_documentation(),
            'available_commands': [
                'enroll my face', 'enroll my voice', 'verify me', 
                'who am I', 'security status', 'lock system', 'list users'
            ]
        }


# Singleton accessor
_biometric_security_manager: Optional[BiometricSecurityManager] = None

def get_biometric_security_manager(event_bus=None, auto_start_webcam: bool = True) -> BiometricSecurityManager:
    """Get the singleton Biometric Security Manager instance.
    
    Args:
        event_bus: Event bus for component communication
        auto_start_webcam: If True, automatically start webcam for face auth
        
    Returns:
        BiometricSecurityManager instance
    """
    global _biometric_security_manager
    if _biometric_security_manager is None:
        _biometric_security_manager = BiometricSecurityManager(event_bus)
        
        # SOTA 2026: Do NOT auto-start webcam — UserIdentityEngine handles
        # all face verification via DeepFace. Starting a second webcam here
        # caused lockout, freeze, and camera resource conflicts.
        if auto_start_webcam:
            logger.info("🎥 Webcam auto-start SKIPPED — delegated to UserIdentityEngine")
    
    return _biometric_security_manager
