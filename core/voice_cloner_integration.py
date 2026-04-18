"""
Voice Cloner Integration for Kingdom AI Voice Manager

This module provides a small abstraction layer so the rest of the Kingdom AI
codebase can use a single interface for high‑quality voice cloning while
allowing different backends:

- Existing XTTS‑based cloner (``kingdom_voice_cloner_xtts``)
- GPT‑SoVITS fine‑tuned model (preferred when configured)

Selection is controlled via environment variables so it can be switched
without code changes:

- ``KINGDOM_VOICE_CLONER_BACKEND``: ``gpt_sovits`` or ``xtts`` (default ``xtts``)
- ``KINGDOM_GPT_SOVITS_GPT_MODEL``: path to fine‑tuned GPT weights
- ``KINGDOM_GPT_SOVITS_SOVITS_MODEL``: path to fine‑tuned SoVITS weights
- ``KINGDOM_VOICE_REFERENCE_WAV``: optional explicit reference WAV
"""

import os
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GPTSoVITSVoiceCloner:
    """Thin adapter around GPT-SoVITS inference utilities.

    This class is intentionally self-contained and uses lazy imports so that
    Kingdom AI can start even if GPT‑SoVITS is not installed.  All heavy
    imports and model loading are deferred until the first call to
    :meth:`clone_voice`.
    """

    def __init__(
        self,
        gpt_model_path: str,
        sovits_model_path: str,
        reference_wav_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> None:
        self.gpt_model_path = gpt_model_path
        self.sovits_model_path = sovits_model_path
        self.reference_wav_path = reference_wav_path

        base_dir = Path(__file__).resolve().parents[1]
        default_out = base_dir / "data" / "voices" / "gpt_sovits_black_panther"
        self.output_dir = Path(output_dir) if output_dir else default_out
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Lazy-imported attributes
        self._change_gpt_weights = None
        self._change_sovits_weights = None
        self._get_tts_wav = None
        self._i18n = None
        self._sf = None
        self._initialized = False

    def _lazy_initialize(self) -> None:
        """Import GPT‑SoVITS helpers and load the fine‑tuned weights.

        Any ImportError or runtime failure is allowed to bubble up so the
        caller can fall back to another backend.
        """

        if self._initialized:
            return

        try:
            # These imports come from the GPT-SoVITS repository that lives
            # alongside the Kingdom AI project.
            from GPT_SoVITS.inference_webui import (
                change_gpt_weights,
                change_sovits_weights,
                get_tts_wav,
            )
            from tools.i18n.i18n import I18nAuto
            import soundfile as sf  # type: ignore[import]
        except Exception as exc:  # noqa: BLE001 - we want the full error
            logger.error("GPT-SoVITS imports failed: %s", exc)
            raise

        self._change_gpt_weights = change_gpt_weights
        self._change_sovits_weights = change_sovits_weights
        self._get_tts_wav = get_tts_wav
        self._i18n = I18nAuto()
        self._sf = sf

        # Load the fine-tuned weights once
        logger.info("Loading GPT-SoVITS weights for Black Panther voice")
        self._change_gpt_weights(gpt_path=self.gpt_model_path)
        self._change_sovits_weights(sovits_path=self.sovits_model_path)
        self._initialized = True

    def clone_voice(self, text: str, output_file: Optional[str] = None) -> Optional[str]:
        """Generate speech for *text* using the fine‑tuned GPT‑SoVITS model.

        Returns the path to the generated WAV file, or ``None`` if generation
        fails for any reason.
        """

        if not text:
            return None

        # Initialize models on first use
        self._lazy_initialize()

        # Ensure reference WAV exists – this should be your
        # processed_black_panther_CLEAN.wav path.
        ref_wav = self.reference_wav_path
        if not ref_wav or not os.path.exists(ref_wav):
            logger.warning(
                "GPT-SoVITS reference WAV not found (%s); generation will still run but quality may suffer",
                ref_wav,
            )
            # get_tts_wav expects a valid path; if it is missing, abort
            return None

        # Build default output path if none was provided
        if output_file is None:
            ts = int(time.time() * 1000)
            file_name = f"gpt_sovits_black_panther_{ts}.wav"
            output_path = self.output_dir / file_name
        else:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Use English for both prompt and target; lower temperature and
            # top_p give more deterministic articulation, closer to the
            # reference clip.
            synthesis_result = self._get_tts_wav(  # type: ignore[operator]
                ref_wav_path=ref_wav,
                prompt_text=text,
                prompt_language=self._i18n("英文"),
                text=text,
                text_language=self._i18n("英文"),
                top_p=0.7,
                temperature=0.6,
            )

            result_list = list(synthesis_result)
            if not result_list:
                logger.error("GPT-SoVITS returned no audio frames")
                return None

            sr, audio = result_list[-1]
            self._sf.write(str(output_path), audio, sr)  # type: ignore[arg-type]
            logger.info("GPT-SoVITS generated audio: %s", output_path)
            return str(output_path)
        except Exception as exc:  # noqa: BLE001 - propagate full error
            logger.error("GPT-SoVITS voice generation failed: %s", exc)
            return None


class VoiceClonerBridge:
    """Bridge between VoiceManager and KingdomVoiceCloner."""
    
    def __init__(self, reference_wav: str = None):
        """Initialize the voice cloner bridge.

        The ``reference_wav`` should normally point to your canonical
        ``processed_black_panther_CLEAN.wav`` file.  If it is ``None``, the
        bridge will look for ``KINGDOM_VOICE_REFERENCE_WAV`` in the
        environment and finally fall back to a best‑effort default.
        """

        self.cloner = None
        self.reference_wav = reference_wav
        self._initialized = False
        # Backend selection is controlled by an environment variable so it can
        # be changed without code edits.
        self.backend = os.environ.get("KINGDOM_VOICE_CLONER_BACKEND", "xtts").lower()
    
    def initialize(self) -> bool:
        """Initialize the voice cloner."""
        if self._initialized:
            return True

        # Resolve reference WAV with sensible defaults.
        if not self.reference_wav:
            env_ref = os.environ.get("KINGDOM_VOICE_REFERENCE_WAV")
            if env_ref:
                self.reference_wav = env_ref
            else:
                base_dir = Path(__file__).resolve().parents[1]
                default_ref = base_dir / "processed_black_panther_CLEAN.wav"
                self.reference_wav = str(default_ref)

        # First try GPT‑SoVITS backend if explicitly requested.
        if self.backend == "gpt_sovits":
            gpt_model = os.environ.get("KINGDOM_GPT_SOVITS_GPT_MODEL")
            sovits_model = os.environ.get("KINGDOM_GPT_SOVITS_SOVITS_MODEL")
            if not gpt_model or not sovits_model:
                logger.error(
                    "GPT-SoVITS backend selected but model paths are not set. "
                    "Please define KINGDOM_GPT_SOVITS_GPT_MODEL and "
                    "KINGDOM_GPT_SOVITS_SOVITS_MODEL. Falling back to XTTS.",
                )
            else:
                try:
                    self.cloner = GPTSoVITSVoiceCloner(
                        gpt_model_path=gpt_model,
                        sovits_model_path=sovits_model,
                        reference_wav_path=self.reference_wav,
                    )
                    # Lazy initialization happens on first use; we simply
                    # record that GPT‑SoVITS is the active backend.
                    self._initialized = True
                    logger.info("✅ GPT-SoVITS voice cloner selected as backend")
                    return True
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Failed to initialize GPT-SoVITS voice cloner: %s. "
                        "Falling back to XTTS backend.",
                        exc,
                    )

        # Default / fallback: use the existing XTTS-based cloner.
        try:
            from kingdom_voice_cloner_xtts import KingdomVoiceCloner

            self.cloner = KingdomVoiceCloner(reference_wav_path=self.reference_wav)

            if self.cloner.load_model():
                self.cloner.extract_voice_embedding()
                self._initialized = True
                logger.info("✅ Black Panther XTTS voice cloner initialized")
                return True
            logger.error("❌ Failed to load XTTS voice cloner model")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("❌ Voice cloner initialization failed: %s", exc)
            return False
    
    def speak(self, text: str, output_file: str = None) -> Optional[str]:
        """
        Generate speech using Black Panther voice.
        
        Args:
            text: Text to speak
            output_file: Optional output file path
            
        Returns:
            Path to generated audio file
        """
        if not self._initialized:
            if not self.initialize():
                logger.error("Cannot speak - voice cloner not initialized")
                return None
        
        try:
            return self.cloner.clone_voice(text, output_file)
        except Exception as e:
            logger.error(f"Error generating speech: {e}")
            return None
    
    async def speak_async(self, text: str, output_file: str = None) -> Optional[str]:
        """Async version of :meth:`speak`.

        If the underlying cloner exposes an ``async`` API (XTTS
        ``clone_voice_async``), it is awaited directly.  For GPT‑SoVITS (which
        only has a synchronous :meth:`clone_voice`), the work is offloaded to a
        background thread via :func:`asyncio.to_thread`.
        """

        if not self._initialized:
            if not self.initialize():
                return None

        try:
            # Native async path (XTTS backend)
            if hasattr(self.cloner, "clone_voice_async"):
                return await self.cloner.clone_voice_async(text, output_file)  # type: ignore[func-returns-value]

            # Fallback: run synchronous clone_voice in a worker thread so we
            # do not block the event loop (GPT‑SoVITS backend).
            import asyncio

            return await asyncio.to_thread(self.cloner.clone_voice, text, output_file)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error in async speech generation: {e}")
            return None


# Global instance
_voice_cloner_bridge = None

def get_voice_cloner_bridge(reference_wav: str = None) -> VoiceClonerBridge:
    """Get or create the global voice cloner bridge."""
    global _voice_cloner_bridge
    
    if _voice_cloner_bridge is None:
        _voice_cloner_bridge = VoiceClonerBridge(reference_wav)
    
    return _voice_cloner_bridge
