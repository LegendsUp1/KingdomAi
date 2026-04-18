#!/usr/bin/env python3
"""
Kingdom AI Audio Bridge — Native Linux
=======================================
Plays audio via PulseAudio (paplay) on the system default output.
No WSL, no Windows, no PowerShell.
"""

import os
import logging
import subprocess
import shutil
from typing import Optional

logger = logging.getLogger("KingdomAI.AudioBridge")


class WSLAudioBridge:
    """Audio playback on native Linux (PulseAudio / ALSA)."""

    def __init__(self):
        self.in_wsl = False
        self.audio_enabled = True

    @staticmethod
    def _resample_for_hdmi(file_path: str) -> str:
        """HDMI sinks need 44.1kHz+ stereo. Resample XTTS 24kHz mono via ffmpeg."""
        if not shutil.which("ffmpeg"):
            return file_path
        try:
            import wave
            with wave.open(file_path) as w:
                if w.getframerate() >= 44100 and w.getnchannels() >= 2:
                    return file_path
        except Exception:
            return file_path
        out = file_path.rsplit(".", 1)[0] + "_44k.wav"
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", file_path, "-ar", "44100", "-ac", "2", out],
                capture_output=True, timeout=30,
            )
            if r.returncode == 0 and os.path.exists(out):
                return out
        except Exception:
            pass
        return file_path

    def play_audio(self, file_path: str) -> bool:
        if not self.audio_enabled:
            logger.warning("Audio disabled")
            return False
        if not os.path.exists(file_path):
            logger.warning("Audio file not found: %s", file_path)
            return False

        playable = self._resample_for_hdmi(file_path)

        if self._play_paplay(playable):
            return True
        if self._play_aplay(playable):
            return True
        if self._play_ffplay(playable):
            return True

        logger.error("No working audio player found (tried paplay, aplay, ffplay)")
        return False

    @staticmethod
    def _play_paplay(path: str) -> bool:
        if not shutil.which("paplay"):
            return False
        try:
            r = subprocess.run(["paplay", path], capture_output=True, timeout=120)
            if r.returncode == 0:
                logger.info("Audio played via paplay (Pulse default sink)")
                return True
            logger.debug("paplay rc=%s: %s", r.returncode, (r.stderr or b"").decode("utf-8", "ignore")[:200])
        except Exception as e:
            logger.debug("paplay error: %s", e)
        return False

    @staticmethod
    def _play_aplay(path: str) -> bool:
        if not shutil.which("aplay"):
            return False
        try:
            r = subprocess.run(["aplay", path], capture_output=True, timeout=120)
            if r.returncode == 0:
                logger.info("Audio played via aplay (ALSA)")
                return True
        except Exception as e:
            logger.debug("aplay error: %s", e)
        return False

    @staticmethod
    def _play_ffplay(path: str) -> bool:
        if not shutil.which("ffplay"):
            return False
        try:
            r = subprocess.run(["ffplay", "-nodisp", "-autoexit", path], capture_output=True, timeout=120)
            if r.returncode == 0:
                logger.info("Audio played via ffplay")
                return True
        except Exception as e:
            logger.debug("ffplay error: %s", e)
        return False

    def capture_audio(self, duration: float = 5.0, output_file: Optional[str] = None) -> str:
        """Record from default mic via arecord (ALSA)."""
        import tempfile
        if output_file is None:
            f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_file = f.name
            f.close()
        try:
            subprocess.run(
                ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(int(duration)), output_file],
                check=True, capture_output=True, timeout=duration + 5,
            )
            return output_file
        except Exception as e:
            logger.error("Audio capture failed: %s", e)
            return ""


wsl_audio_bridge = WSLAudioBridge()
__all__ = ["WSLAudioBridge", "wsl_audio_bridge"]
