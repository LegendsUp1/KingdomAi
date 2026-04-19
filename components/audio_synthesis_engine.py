"""Audio waveform synthesis engine using pure Python PCM generation."""

from __future__ import annotations

import logging
import math
import struct
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kingdom_ai.audio_synthesis_engine")

SAMPLE_RATE = 44100
BIT_DEPTH = 16
MAX_AMP = (1 << (BIT_DEPTH - 1)) - 1

NOTE_FREQUENCIES: Dict[str, float] = {
    "C4": 261.63, "C#4": 277.18, "D4": 293.66, "D#4": 311.13,
    "E4": 329.63, "F4": 349.23, "F#4": 369.99, "G4": 392.00,
    "G#4": 415.30, "A4": 440.00, "A#4": 466.16, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "G5": 783.99, "A5": 880.00,
}


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


class AudioSynthesisEngine:
    """Generates PCM audio waveforms — sine, square, sawtooth, noise, and chords."""

    def __init__(self, event_bus: Any = None, sample_rate: int = SAMPLE_RATE) -> None:
        self.event_bus = event_bus
        self.sample_rate = sample_rate
        if event_bus:
            event_bus.subscribe("audio.synthesize.request", self._on_synth_request)
        logger.info("AudioSynthesisEngine initialised (rate=%dHz)", sample_rate)

    def generate_tone(self, frequency: float, duration: float = 1.0, waveform: str = "sine", amplitude: float = 0.8) -> bytes:
        num_samples = int(self.sample_rate * duration)
        amp = _clamp(amplitude, 0.0, 1.0) * MAX_AMP
        samples: List[int] = []
        for i in range(num_samples):
            t = i / self.sample_rate
            phase = 2.0 * math.pi * frequency * t
            if waveform == "sine":
                val = math.sin(phase)
            elif waveform == "square":
                val = 1.0 if math.sin(phase) >= 0 else -1.0
            elif waveform == "sawtooth":
                val = 2.0 * ((frequency * t) % 1.0) - 1.0
            elif waveform == "triangle":
                val = 2.0 * abs(2.0 * ((frequency * t) % 1.0) - 1.0) - 1.0
            elif waveform == "noise":
                import random
                val = random.uniform(-1.0, 1.0)
            else:
                val = math.sin(phase)
            samples.append(int(_clamp(val * amp, -MAX_AMP, MAX_AMP)))
        return struct.pack(f"<{len(samples)}h", *samples)

    def generate_chord(self, notes: List[str], duration: float = 1.0, waveform: str = "sine") -> bytes:
        freqs = [NOTE_FREQUENCIES.get(n, 440.0) for n in notes]
        if not freqs:
            return self.generate_tone(440.0, duration, waveform)
        num_samples = int(self.sample_rate * duration)
        scale = 0.7 / len(freqs)
        samples: List[int] = []
        for i in range(num_samples):
            t = i / self.sample_rate
            mixed = sum(math.sin(2.0 * math.pi * f * t) for f in freqs) * scale
            samples.append(int(_clamp(mixed * MAX_AMP, -MAX_AMP, MAX_AMP)))
        return struct.pack(f"<{len(samples)}h", *samples)

    def text_to_speech_placeholder(self, text: str) -> Dict[str, Any]:
        word_count = len(text.split())
        estimated_duration = word_count * 0.4
        meta = {
            "text": text,
            "word_count": word_count,
            "estimated_duration_sec": round(estimated_duration, 2),
            "status": "pending_tts_engine",
            "format": "pcm_s16le",
            "sample_rate": self.sample_rate,
        }
        if self.event_bus:
            self.event_bus.publish("audio.tts.request", {"text": text, "metadata": meta})
        return meta

    def apply_envelope(self, pcm_data: bytes, attack: float = 0.05, decay: float = 0.1,
                       sustain: float = 0.7, release: float = 0.15) -> bytes:
        num_samples = len(pcm_data) // 2
        if num_samples == 0:
            return pcm_data
        samples = list(struct.unpack(f"<{num_samples}h", pcm_data))
        total_sec = num_samples / self.sample_rate
        env_total = attack + decay + release
        sustain_sec = max(total_sec - env_total, 0.0)
        result: List[int] = []
        for i, s in enumerate(samples):
            t = i / self.sample_rate
            if t < attack:
                gain = t / attack if attack > 0 else 1.0
            elif t < attack + decay:
                elapsed = t - attack
                gain = 1.0 - (1.0 - sustain) * (elapsed / decay) if decay > 0 else sustain
            elif t < attack + decay + sustain_sec:
                gain = sustain
            else:
                elapsed = t - (attack + decay + sustain_sec)
                gain = sustain * (1.0 - elapsed / release) if release > 0 else 0.0
            gain = _clamp(gain, 0.0, 1.0)
            result.append(int(_clamp(s * gain, -MAX_AMP, MAX_AMP)))
        return struct.pack(f"<{len(result)}h", *result)

    def generate_wav_header(self, pcm_data: bytes, channels: int = 1) -> bytes:
        data_size = len(pcm_data)
        byte_rate = self.sample_rate * channels * 2
        block_align = channels * 2
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + data_size, b"WAVE",
            b"fmt ", 16, 1, channels,
            self.sample_rate, byte_rate, block_align, BIT_DEPTH,
            b"data", data_size,
        )
        return header

    def _on_synth_request(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("synth request ignored — expected dict")
            return
        action = data.get("action", "tone")
        result: Dict[str, Any] = {"action": action, "success": True}
        try:
            if action == "tone":
                pcm = self.generate_tone(
                    data.get("frequency", 440.0),
                    data.get("duration", 1.0),
                    data.get("waveform", "sine"),
                )
                result["pcm_bytes"] = len(pcm)
                result["duration"] = data.get("duration", 1.0)
            elif action == "chord":
                pcm = self.generate_chord(data.get("notes", ["C4", "E4", "G4"]), data.get("duration", 1.0))
                result["pcm_bytes"] = len(pcm)
            elif action == "tts":
                result["metadata"] = self.text_to_speech_placeholder(data.get("text", ""))
            else:
                result = {"action": action, "success": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.exception("Audio synthesis failed")
            result = {"action": action, "success": False, "error": str(exc)}
        if self.event_bus:
            self.event_bus.publish("audio.synthesize.result", result)
