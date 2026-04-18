#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Audio Configuration

This module configures the audio subsystem for Kingdom AI, suppressing ALSA warnings
while maintaining voice system functionality via native PulseAudio.
"""

import os
import sys
import logging

logger = logging.getLogger("KingdomAI.AudioConfig")

# Set environment variables to suppress ALSA warnings
os.environ['AUDIODEV'] = 'null'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['ALSA_CONFIG_PATH'] = '/dev/null'

def configure_audio():
    """
    Configure audio settings for Kingdom AI.
    Uses native PulseAudio on Linux.
    
    Returns:
        bool: True if configuration successful
    """
    try:
        if sys.platform.startswith('linux'):
            # Native Linux: use PulseAudio directly
            if not os.environ.get('PULSE_SERVER'):
                # Default PulseAudio uses the user session automatically
                logger.info("Native Linux detected, using system PulseAudio")
            
            # Suppress ALSA warnings
            try:
                import ctypes
                from ctypes import util
                asound = util.find_library('asound')
                if asound:
                    alsa_lib = ctypes.CDLL(asound)
                    if hasattr(alsa_lib, 'snd_lib_error_set_handler'):
                        alsa_lib.snd_lib_error_set_handler(None)
                        logger.info("ALSA error handler configured to suppress warnings")
            except Exception as e:
                logger.warning(f"Could not configure ALSA error handler: {e}")

        return True
    except Exception as e:
        logger.error(f"Error configuring audio: {e}")
        return False

# Configure OS-level audio settings
wsl_audio_configured = configure_audio()

# Dummy audio IO for environments without audio hardware
class DummyAudioIO:
    """Dummy audio IO class for environments without audio hardware."""
    
    def __init__(self):
        self.available = False
        logger.info("Initializing dummy audio I/O")
    
    def speak(self, text, voice="default", **kwargs):
        """Dummy speak method that logs but doesn't try to produce audio"""
        logger.info(f"[DUMMY AUDIO] Would speak: '{text}' with voice '{voice}'")
        return True
    
    def listen(self, timeout=5, **kwargs):
        """Dummy listen method that returns empty text"""
        logger.info(f"[DUMMY AUDIO] Would listen for {timeout} seconds")
        return ""

# Create dummy audio provider for fallback
dummy_audio = DummyAudioIO()

def get_audio_provider():
    """Get the appropriate audio provider based on environment
    
    Returns:
        object: Audio provider object or dummy implementation if not available
    """
    try:
        # Try to import real audio provider
        from core.voice_manager import VoiceManager
        audio_provider = VoiceManager()
        logger.info("Using real voice manager")
        return audio_provider
    except ImportError:
        logger.warning("Voice manager not available, using dummy audio")
        return dummy_audio
    except Exception as e:
        logger.error(f"Error initializing voice manager: {e}")
        return dummy_audio
