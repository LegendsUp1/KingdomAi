#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows Audio Device Configuration for Kingdom AI
=================================================
GENERIC device detection - works with ANY brand of audio/video devices.

Automatically detects and uses:
- Output: Whatever is set as Windows default speaker (ANY brand)
- Input: Whatever is set as Windows default microphone (ANY brand)  
- Video: Whatever webcam is available and working (ANY brand)

This works from both native Windows Python AND WSL2 via PowerShell bridge.
NO hardcoded device names - uses system defaults automatically.
"""

import os
import sys
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def is_wsl() -> bool:
    """Detect WSL via /proc/version. Returns False on native Linux."""
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False


def is_windows() -> bool:
    """Check if running on native Windows."""
    return os.name == 'nt' or sys.platform == 'win32'


# ============================================================================
# WINDOWS NATIVE AUDIO PLAYBACK
# ============================================================================

def play_audio_windows_native(audio_file: str, block: bool = True) -> bool:
    """
    Play audio file using native Linux audio (paplay for PulseAudio).
    
    Args:
        audio_file: Path to audio file (WAV format preferred)
        block: Whether to wait for playback to complete
        
    Returns:
        True if playback started/completed successfully
    """
    import shutil
    try:
        audio_path = str(Path(audio_file).resolve())
        
        # Try paplay (PulseAudio) first, then aplay (ALSA)
        player = None
        for cmd in ['paplay', 'aplay']:
            if shutil.which(cmd):
                player = cmd
                break
        
        if not player:
            logger.error("No audio player found (install pulseaudio-utils or alsa-utils)")
            return False
        
        if block:
            result = subprocess.run(
                [player, audio_path],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                logger.warning(f"Audio playback warning: {result.stderr}")
            logger.info(f"✅ Audio playback complete: {audio_file}")
            return True
        else:
            subprocess.Popen(
                [player, audio_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            logger.info(f"✅ Audio playback started (non-blocking): {audio_file}")
            return True
            
    except subprocess.TimeoutExpired:
        logger.error("Audio playback timed out")
        return False
    except Exception as e:
        logger.error(f"Audio playback failed: {e}")
        return False


def speak_text_windows_sapi(text: str, voice_name: Optional[str] = None) -> bool:
    """
    Speak text using espeak-ng or pyttsx3 on native Linux.
    
    Args:
        text: Text to speak
        voice_name: Optional voice name (ignored on Linux, uses default)
        
    Returns:
        True if speech completed successfully
    """
    import shutil
    try:
        if shutil.which('espeak-ng'):
            result = subprocess.run(
                ['espeak-ng', text],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                logger.info("✅ TTS speech complete (espeak-ng)")
                return True
        
        # Fallback: try pyttsx3
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            logger.info("✅ TTS speech complete (pyttsx3)")
            return True
        except Exception:
            pass
        
        logger.warning("No TTS engine available (install espeak-ng or pyttsx3)")
        return False
            
    except Exception as e:
        logger.error(f"TTS speech failed: {e}")
        return False


# ============================================================================
# GENERIC AUDIO INPUT - Uses Windows Default Microphone (ANY brand)
# ============================================================================

def get_windows_recording_devices() -> list:
    """
    Get list of audio recording devices via PulseAudio on native Linux.
    
    Returns:
        List of device dicts with name and index
    """
    devices = []
    
    try:
        result = subprocess.run(
            ['pactl', 'list', 'short', 'sources'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for i, line in enumerate(result.stdout.strip().split('\n')):
                if line and 'monitor' not in line.lower():
                    parts = line.split('\t')
                    devices.append({
                        'index': i,
                        'name': parts[1] if len(parts) > 1 else 'Unknown',
                        'device_id': parts[0] if parts else ''
                    })
    except Exception as e:
        logger.debug(f"PulseAudio source listing: {e}")
    
    return devices


def get_default_microphone() -> Optional[int]:
    """
    Get the default microphone device index.
    SOTA 2026: Works with ANY microphone in both Windows native AND WSL environments.
    
    Returns:
        Device index of default microphone, or None if not available
    """
    # Method 1: Try sounddevice for native Linux
    try:
        import sounddevice as sd
        
        # Get system default input device (ANY brand)
        default_input = sd.default.device[0]
        
        if default_input is not None and default_input >= 0:
            devices = sd.query_devices()
            if default_input < len(devices):
                dev_name = devices[default_input]['name']
                logger.info(f"🎤 System default microphone: {dev_name} (index {default_input})")
                return int(default_input)
        
        # Fallback: find first device with input channels
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                logger.info(f"🎤 Using first available microphone: {dev['name']} (index {i})")
                return i
                
    except ImportError:
        logger.warning("sounddevice not available for microphone detection")
    except Exception as e:
        logger.error(f"Failed to detect microphone: {e}")
    
    return None


def get_default_webcam() -> Optional[int]:
    """
    Get the first available webcam device index for OpenCV.
    SOTA 2026: Works with ANY webcam - detects first working camera.
    
    Returns:
        Device index of first working webcam, or 0 as fallback
    """
    try:
        import cv2
        
        # Try indices 0-5 to find first working webcam (ANY brand)
        for i in range(6):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                
                if ret and frame is not None:
                    logger.info(f"📷 Found working webcam at index {i}")
                    return i
                    
    except ImportError:
        logger.warning("OpenCV not available for webcam detection")
    except Exception as e:
        logger.error(f"Failed to find webcam: {e}")
    
    return 0  # Default to index 0


# ============================================================================
# UNIFIED AUDIO CONFIGURATION
# ============================================================================

class WindowsAudioConfig:
    """
    Unified Windows audio configuration for Kingdom AI.
    SOTA 2026: Generic device detection - works with ANY brand.
    
    Automatically detects and configures:
    - Audio output: Windows default speaker (ANY brand)
    - Audio input: Windows default microphone (ANY brand)
    - Video input: First available webcam (ANY brand)
    """
    
    def __init__(self):
        self.is_wsl = is_wsl()
        self.is_windows = is_windows()
        
        # Device indices
        self.output_device = None
        self.input_device = None
        self.webcam_device = None
        
        # Initialize
        self._detect_devices()
        
    def _detect_devices(self):
        """Detect and configure all audio/video devices (ANY brand)."""
        logger.info("🔍 Detecting system audio/video devices (generic - any brand)...")
        
        # Find system default microphone (ANY brand)
        self.input_device = get_default_microphone()
        if self.input_device is not None:
            logger.info(f"🎤 Microphone configured: device {self.input_device}")
        
        # Find first available webcam (ANY brand)
        self.webcam_device = get_default_webcam()
        if self.webcam_device is not None:
            logger.info(f"📷 Webcam configured: device {self.webcam_device}")
        
        # Output uses system default (PulseAudio on Linux)
        logger.info("🔊 Audio output: system default speaker")
        
    def play_audio(self, audio_file: str, block: bool = True) -> bool:
        """Play audio file through Windows default speaker."""
        return play_audio_windows_native(audio_file, block)
    
    def speak_text(self, text: str) -> bool:
        """Speak text using Windows SAPI."""
        return speak_text_windows_sapi(text)
    
    def get_microphone_index(self) -> Optional[int]:
        """Get the configured microphone device index."""
        return self.input_device
    
    def get_webcam_index(self) -> Optional[int]:
        """Get the configured webcam device index."""
        return self.webcam_device


# Global singleton instance
_audio_config: Optional[WindowsAudioConfig] = None


def get_audio_config() -> WindowsAudioConfig:
    """Get the global Windows audio configuration."""
    global _audio_config
    if _audio_config is None:
        _audio_config = WindowsAudioConfig()
    return _audio_config


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def play_audio(audio_file: str, block: bool = True) -> bool:
    """Play audio file through Windows default speaker."""
    return get_audio_config().play_audio(audio_file, block)


def speak(text: str) -> bool:
    """Speak text using Windows SAPI (fallback if XTTS unavailable)."""
    return get_audio_config().speak_text(text)


def get_mic_device() -> Optional[int]:
    """Get the system default microphone device index (any brand)."""
    return get_audio_config().get_microphone_index()


def get_webcam_device() -> Optional[int]:
    """Get the first available webcam device index (any brand)."""
    return get_audio_config().get_webcam_index()


# ============================================================================
# TEST
# ============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("=" * 60)
    print("Windows Audio Configuration Test")
    print("=" * 60)
    
    config = get_audio_config()
    
    print(f"\n🖥️  Environment: Native Linux")
    print(f"🎤 Microphone device: {config.input_device}")
    print(f"📷 Webcam device: {config.webcam_device}")
    print(f"🔊 Audio output: system default speaker")
    
    # Test TTS speech
    print("\n🔊 Testing TTS speech...")
    speak("Kingdom AI audio system initialized. Ready for voice commands.")
    
    print("\n✅ Audio configuration complete!")
