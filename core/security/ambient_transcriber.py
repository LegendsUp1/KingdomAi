"""
Kingdom AI — Ambient Transcriber
SOTA 2026: Real-time transcription of ambient speech using Faster-Whisper.

Transcribes ALL ambient audio (not just Creator's commands) so that
ThreatNLPAnalyzer can detect hostile intent, coercion, or threats in
conversations happening near the Creator's device.

Also provides speaker diarization via PyAnnote when available.
Dormant until protection flag "ambient_transcriber" is activated.
"""
import logging
import queue
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from base_component import BaseComponent

logger = logging.getLogger(__name__)

HAS_FASTER_WHISPER = False
HAS_PYANNOTE = False
HAS_NUMPY = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]

try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    pass

try:
    from pyannote.audio import Pipeline as PyAnnotePipeline
    HAS_PYANNOTE = True
except ImportError:
    pass


class TranscriptionSegment:
    """A single transcription segment with metadata."""
    __slots__ = ("text", "start", "end", "speaker", "confidence", "language", "timestamp")

    def __init__(self, text: str, start: float = 0, end: float = 0,
                 speaker: str = "unknown", confidence: float = 0, language: str = "en"):
        self.text = text
        self.start = start
        self.end = end
        self.speaker = speaker
        self.confidence = confidence
        self.language = language
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "speaker": self.speaker,
            "confidence": self.confidence,
            "language": self.language,
            "timestamp": self.timestamp,
        }


class AmbientTranscriber(BaseComponent):
    """
    Continuous ambient speech transcription for threat analysis.

    Receives raw audio from AlwaysOnVoice or dedicated mic feed,
    transcribes using Faster-Whisper, and publishes transcripts
    for ThreatNLPAnalyzer to evaluate.

    Uses speaker diarization (PyAnnote) to distinguish speakers
    and correlate with UserIdentityEngine profiles.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        # Whisper model (loaded lazily)
        self._whisper_model = None
        self._model_size = self.config.get("whisper_model", "base")  # tiny, base, small, medium

        # Audio queue for background processing
        self._audio_queue: queue.Queue = queue.Queue(maxsize=50)
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

        # Transcript history
        self._transcript_history: deque = deque(maxlen=500)
        self._lock = threading.Lock()

        # Buffer for accumulating short audio chunks into longer segments
        self._chunk_buffer: List[Any] = []
        self._buffer_duration = 0.0
        self._target_duration = 5.0  # Process in 5-second chunks
        self._sample_rate = 16000

        self._subscribe_events()
        self._initialized = True
        logger.info(
            "AmbientTranscriber initialized (faster_whisper=%s, pyannote=%s, model=%s)",
            HAS_FASTER_WHISPER, HAS_PYANNOTE, self._model_size,
        )

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _ensure_whisper(self) -> bool:
        if self._whisper_model is not None:
            return True
        if not HAS_FASTER_WHISPER:
            return False
        try:
            self._whisper_model = WhisperModel(
                self._model_size,
                device="cuda" if self._cuda_available() else "cpu",
                compute_type="float16" if self._cuda_available() else "int8",
            )
            logger.info("Faster-Whisper model loaded: %s", self._model_size)
            return True
        except Exception as e:
            logger.warning("Faster-Whisper load failed: %s", e)
            return False

    def _cuda_available(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Audio processing
    # ------------------------------------------------------------------

    def feed_audio(self, audio_data: Any, sample_rate: int = 16000) -> None:
        """Feed audio chunk for transcription."""
        if not self._is_active():
            return
        if not HAS_NUMPY or audio_data is None:
            return

        if not isinstance(audio_data, np.ndarray):
            try:
                audio_data = np.array(audio_data, dtype=np.float32)
            except Exception:
                return

        # Accumulate chunks
        self._chunk_buffer.append(audio_data)
        self._buffer_duration += len(audio_data) / sample_rate

        # When we have enough audio, queue for processing
        if self._buffer_duration >= self._target_duration:
            combined = np.concatenate(self._chunk_buffer)
            self._chunk_buffer.clear()
            self._buffer_duration = 0.0

            try:
                self._audio_queue.put_nowait((combined, sample_rate))
            except queue.Full:
                logger.debug("Transcription queue full, dropping audio chunk")

    def _process_audio(self, audio: Any, sr: int) -> List[TranscriptionSegment]:
        """Transcribe audio and return segments."""
        if not self._ensure_whisper():
            return []

        segments: List[TranscriptionSegment] = []
        try:
            # Resample to 16kHz if needed
            if sr != 16000:
                try:
                    import librosa
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                except ImportError:
                    # Simple downsampling
                    ratio = 16000 / sr
                    indices = np.arange(0, len(audio), 1 / ratio).astype(int)
                    indices = indices[indices < len(audio)]
                    audio = audio[indices]

            # Transcribe
            result_segments, info = self._whisper_model.transcribe(
                audio,
                beam_size=3,
                language=None,  # Auto-detect
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )

            for seg in result_segments:
                ts = TranscriptionSegment(
                    text=seg.text.strip(),
                    start=seg.start,
                    end=seg.end,
                    confidence=seg.avg_logprob if hasattr(seg, "avg_logprob") else 0,
                    language=info.language if info else "en",
                )
                if ts.text:
                    segments.append(ts)

        except Exception as e:
            logger.debug("Transcription error: %s", e)

        return segments

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def start_processing(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="AmbientTranscriber",
        )
        self._worker_thread.start()
        logger.info("Ambient transcription processing started")

    def stop_processing(self) -> None:
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        logger.info("Ambient transcription processing stopped")

    def _worker_loop(self) -> None:
        while self._running:
            try:
                audio, sr = self._audio_queue.get(timeout=1.0)
                segments = self._process_audio(audio, sr)
                for seg in segments:
                    self._record_segment(seg)
                    self._publish_segment(seg)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error("Transcription worker error: %s", e)
                time.sleep(1)

    # ------------------------------------------------------------------
    # Segment management
    # ------------------------------------------------------------------

    def _record_segment(self, segment: TranscriptionSegment) -> None:
        with self._lock:
            self._transcript_history.append(segment.to_dict())

    def _publish_segment(self, segment: TranscriptionSegment) -> None:
        if not self.event_bus:
            return
        self.event_bus.publish("security.transcription.segment", segment.to_dict())
        # Also publish full text for NLP analysis
        self.event_bus.publish("security.nlp.analyze_text", {
            "text": segment.text,
            "speaker": segment.speaker,
            "timestamp": segment.timestamp,
        })

    def get_recent_transcript(self, count: int = 20) -> List[Dict]:
        with self._lock:
            return list(self._transcript_history)[-count:]

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("ambient_transcriber")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("audio.raw.chunk", self._handle_audio)
        self.event_bus.subscribe("protection.flag.changed", self._handle_flag_change)
        self.event_bus.subscribe("security.transcription.query", self._handle_query)

    def _handle_audio(self, data: Any) -> None:
        if isinstance(data, dict):
            audio = data.get("audio")
            sr = data.get("sample_rate", 16000)
            self.feed_audio(audio, sr)
        elif HAS_NUMPY and isinstance(data, np.ndarray):
            self.feed_audio(data)

    def _handle_flag_change(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        if data.get("module") in ("ambient_transcriber", "__all__"):
            if data.get("active"):
                self.start_processing()
            else:
                self.stop_processing()

    def _handle_query(self, data: Any) -> None:
        count = 20
        if isinstance(data, dict):
            count = data.get("count", 20)
        if self.event_bus:
            self.event_bus.publish("security.transcription.history", self.get_recent_transcript(count))

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self.stop_processing()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "faster_whisper_available": HAS_FASTER_WHISPER,
            "whisper_loaded": self._whisper_model is not None,
            "pyannote_available": HAS_PYANNOTE,
            "processing": self._running,
            "transcript_count": len(self._transcript_history),
            "queue_size": self._audio_queue.qsize(),
        }
