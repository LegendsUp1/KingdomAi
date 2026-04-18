"""
Kingdom AI System Profile — Native Linux
==========================================
Single source of truth for the hardware, OS, paths, and capabilities
of this machine. Every module should import from here instead of
doing its own WSL detection, path guessing, or hardware probing.

Machine: Kingdom-Ai
OS:      Ubuntu 22.04.5 LTS (jammy), kernel 6.8.x, x86_64
GPUs:    NVIDIA RTX 4060 (8 GB) + RTX 3050 (6 GB), driver 580.x
Audio:   PulseAudio → HDMI (default), Brio 100 mic
Webcam:  Logitech Brio 100 @ /dev/video0
Storage: NVMe ext4 (~2 TB)
"""
from __future__ import annotations

import functools
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
HOSTNAME = "Kingdom-Ai"


# ---------------------------------------------------------------------------
# OS / Environment detection
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def is_wsl() -> bool:
    """True only inside Windows Subsystem for Linux."""
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False


def is_native_linux() -> bool:
    return platform.system() == "Linux" and not is_wsl()


def is_windows() -> bool:
    return os.name == "nt"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def home_dir() -> Path:
    return Path.home()


def kingdom_data_dir() -> Path:
    """~/.kingdom_ai — user-level data/cache outside the repo."""
    d = home_dir() / ".kingdom_ai"
    d.mkdir(parents=True, exist_ok=True)
    return d


def repo_root() -> Path:
    return REPO_ROOT


# ---------------------------------------------------------------------------
# Python environments
# ---------------------------------------------------------------------------

def main_python() -> str:
    """The kingdom-venv Python interpreter."""
    p = REPO_ROOT / "kingdom-venv" / "bin" / "python"
    if p.is_file():
        return str(p)
    return "python3"


def creation_python() -> Optional[str]:
    """The creation_env Python interpreter (for creative/3D pipelines)."""
    p = REPO_ROOT / "creation_env" / "bin" / "python"
    return str(p) if p.is_file() else None


# ---------------------------------------------------------------------------
# GPU / CUDA
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def cuda_available() -> bool:
    try:
        r = subprocess.run(
            ["nvidia-smi"], capture_output=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def cuda_lib_path() -> Optional[str]:
    """LD_LIBRARY_PATH addition for CUDA. Returns None if not needed."""
    for candidate in (
        "/usr/local/cuda/lib64",
        "/usr/lib/x86_64-linux-gnu",
    ):
        if os.path.isdir(candidate):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

def audio_player() -> Optional[str]:
    """Best available audio player binary."""
    for cmd in ("paplay", "aplay", "ffplay"):
        if shutil.which(cmd):
            return cmd
    return None


def tts_command() -> Optional[str]:
    """Best available TTS binary for fallback speech."""
    for cmd in ("espeak-ng", "espeak", "spd-say"):
        if shutil.which(cmd):
            return cmd
    return None


def needs_resample_for_hdmi() -> bool:
    """HDMI sinks typically need >= 44.1 kHz stereo."""
    try:
        r = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True, text=True, timeout=3,
        )
        return "hdmi" in r.stdout.lower()
    except Exception:
        return False


def resample_wav(src: str, dst: Optional[str] = None) -> str:
    """Resample a WAV to 44.1 kHz stereo for HDMI. Returns path to play."""
    if not needs_resample_for_hdmi():
        return src
    if not shutil.which("ffmpeg"):
        return src
    if dst is None:
        dst = src.rsplit(".", 1)[0] + "_44k.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ar", "44100", "-ac", "2", dst],
            capture_output=True, timeout=30,
        )
        if os.path.exists(dst):
            return dst
    except Exception:
        pass
    return src


def play_wav(path: str) -> bool:
    """Play a WAV file through the system default output."""
    if not os.path.isfile(path):
        return False
    playable = resample_wav(path)
    player = audio_player()
    if not player:
        return False
    try:
        r = subprocess.run([player, playable], capture_output=True, timeout=120)
        return r.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Webcam
# ---------------------------------------------------------------------------

def webcam_device() -> Optional[str]:
    """Default V4L2 webcam device."""
    if os.path.exists("/dev/video0"):
        return "/dev/video0"
    return None


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

def ollama_base_url() -> str:
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if host and host.startswith("http"):
        return host.rstrip("/")
    return "http://localhost:11434"


def redis_config() -> dict:
    return {
        "host": "localhost",
        "port": int(os.environ.get("KINGDOM_REDIS_PORT", "6380")),
        "password": os.environ.get("KINGDOM_REDIS_PASSWORD", "QuantumNexus2025"),
    }
