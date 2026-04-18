#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Kingdom Audio Adapter
--------------------
This module provides a unified interface for audio playback and recording,
using alternative libraries (sounddevice, playsound, pydub) while maintaining
compatibility with the existing system that expects PyAudio and SimpleAudio.
"""

import os
import logging
import numpy as np
import tempfile
import threading
import platform
import sys

# Configure logging
logger = logging.getLogger(__name__)

# Check for WSL environment and configure audio fallbacks
def is_wsl():
    """Detect if running in Windows Subsystem for Linux"""
    try:
        return "microsoft" in platform.uname().release.lower() or \
               os.path.exists("/proc/version") and "microsoft" in open("/proc/version", "r").read().lower()
    except:
        return False

def configure_audio_fallbacks():
    """Configure audio fallbacks for WSL or environments with missing audio libraries"""
    try:
        if is_wsl():
            logger.info("WSL environment detected, configuring audio fallbacks")
            # SOTA 2026: Use WSLg PulseAudio if available (Brio mic, headsets, etc.)
            # Do NOT override PULSE_SERVER if already set (e.g. by sitecustomize.py)
            _wslg_pulse = '/mnt/wslg/PulseServer'
            if not os.environ.get('PULSE_SERVER') and os.path.exists(_wslg_pulse):
                os.environ['PULSE_SERVER'] = f'unix:{_wslg_pulse}'
            elif not os.environ.get('PULSE_SERVER'):
                os.environ['PULSE_SERVER'] = 'tcp:127.0.0.1:4713'
            
            # Check for ALSA libraries and handle missing ones gracefully
            try:
                # Try to import ALSA-related libraries (this is just a check)
                import ctypes
                alsa = ctypes.cdll.LoadLibrary('libasound.so')
                logger.info("ALSA libraries found")
            except Exception as e:
                logger.warning(f"ALSA libraries not available or incomplete: {e}")
                logger.warning("Audio will use mock implementations where needed")
    except Exception as e:
        logger.warning(f"Failed to configure audio fallbacks: {e}")

# Run audio fallback configuration
configure_audio_fallbacks()

class KingdomAudioAdapter:
    """
    Universal audio adapter that provides a consistent interface
    using alternative audio libraries.
    """
    
    def __init__(self):
        """Initialize the audio adapter with available libraries"""
        self.logger = logging.getLogger(__name__)
        self.available_libraries = self._check_available_libraries()
        self.recording = False
        self.playback_devices = []
        self.recording_devices = []
        
        self.logger.info(f"Audio adapter initialized with libraries: {', '.join(self.available_libraries)}")
        self._scan_devices()
    
    def _check_available_libraries(self):
        """Check which audio libraries are available."""
        available = []
        
        # Check for sounddevice (preferred for recording) - AUTO-INSTALL
        try:
            import sounddevice
            available.append('sounddevice')
            self.logger.info("✅ Found sounddevice library")
        except ImportError:
            self.logger.warning("sounddevice not available")
        
        # Check for playsound (simple audio playback) - AUTO-INSTALL
        try:
            import playsound
            available.append('playsound')
            self.logger.info("✅ Found playsound library")
        except ImportError:
            self.logger.warning("playsound not available")
        
        # Check for pydub (audio processing) - AUTO-INSTALL
        try:
            import pydub
            available.append('pydub')
            self.logger.info("✅ Found pydub library")
        except ImportError:
            self.logger.warning("pydub not available")
        
        # Ensure at least one audio library is available
        if not available:
            self.logger.error("❌ No audio libraries available - audio features will be limited")
        
        return available
    
    def _scan_devices(self):
        """Scan for available audio devices"""
        self.playback_devices = []
        self.recording_devices = []
        
        if 'sounddevice' in self.available_libraries:
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                
                for i, device in enumerate(devices):
                    if device['max_output_channels'] > 0:
                        self.playback_devices.append({
                            'index': i,
                            'name': device['name'],
                            'channels': device['max_output_channels'],
                            'default_samplerate': device['default_samplerate']
                        })
                    
                    if device['max_input_channels'] > 0:
                        self.recording_devices.append({
                            'index': i,
                            'name': device['name'],
                            'channels': device['max_input_channels'],
                            'default_samplerate': device['default_samplerate']
                        })
                
                self.logger.info(f"Found {len(self.playback_devices)} playback devices and {len(self.recording_devices)} recording devices")
            
            except Exception as e:
                self.logger.error(f"Error scanning audio devices with sounddevice: {e}")
        
        # NO MOCK DEVICES - report actual device availability
        if not self.playback_devices:
            self.logger.warning("⚠️ NO AUDIO PLAYBACK DEVICES FOUND - audio playback unavailable")
        
        if not self.recording_devices:
            self.logger.warning("⚠️ NO AUDIO RECORDING DEVICES FOUND - audio recording unavailable")
    
    def get_playback_devices(self):
        """Get list of audio playback devices"""
        return self.playback_devices
    
    def get_recording_devices(self):
        """Get list of audio recording devices"""
        return self.recording_devices
    
    def play_audio(self, audio_file, block=False):
        """
        Play audio from a file
        
        Args:
            audio_file (str): Path to audio file
            block (bool): Whether to block until playback completes
            
        Returns:
            PlaybackControl: Object with stop() method
        """
        if not os.path.exists(audio_file):
            self.logger.error(f"Audio file not found: {audio_file}")
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
        
        self.logger.info(f"Playing audio file: {audio_file}")
        
        # Try playsound first
        if 'playsound' in self.available_libraries:
            try:
                import playsound
                
                if block:
                    playsound.playsound(audio_file, block=True)
                    return CompletedPlaybackControl()  # Already finished playing
                else:
                    # Create a thread for non-blocking playback
                    play_thread = threading.Thread(
                        target=playsound.playsound,
                        args=(audio_file, True)
                    )
                    play_thread.daemon = True
                    play_thread.start()
                    
                    return ThreadPlaybackControl(play_thread)
            
            except Exception as e:
                self.logger.error(f"Error playing with playsound: {e}")
        
        # Fall back to pydub
        if 'pydub' in self.available_libraries:
            try:
                from pydub import AudioSegment
                from pydub.playback import play
                
                sound = AudioSegment.from_file(audio_file)
                
                if block:
                    play(sound)
                    return CompletedPlaybackControl()  # Already finished playing
                else:
                    # Create a thread for non-blocking playback
                    play_thread = threading.Thread(target=play, args=(sound,))
                    play_thread.daemon = True
                    play_thread.start()
                    
                    return ThreadPlaybackControl(play_thread)
            
            except Exception as e:
                self.logger.error(f"Error playing with pydub: {e}")
        
        # Fall back to sounddevice if others failed
        if 'sounddevice' in self.available_libraries:
            try:
                import sounddevice as sd
                import soundfile as sf
                
                data, fs = sf.read(audio_file)
                
                if block:
                    sd.play(data, fs)
                    sd.wait()
                    return CompletedPlaybackControl()  # Already finished playing
                else:
                    sd.play(data, fs)
                    return SoundDevicePlaybackControl()
            
            except Exception as e:
                self.logger.error(f"Error playing with sounddevice: {e}")
        
        # Native Linux fallback: ffmpeg resample to 44.1kHz stereo + paplay
        if sys.platform.startswith('linux'):
            try:
                import subprocess, shutil
                if shutil.which('paplay') and shutil.which('ffmpeg'):
                    resampled = audio_file + '.play.wav'
                    subprocess.run(
                        ['ffmpeg', '-y', '-i', audio_file,
                         '-ar', '44100', '-ac', '2', '-f', 'wav', resampled],
                        capture_output=True, timeout=30,
                    )
                    if os.path.exists(resampled):
                        if block:
                            subprocess.run(['paplay', resampled], timeout=120)
                            try:
                                os.unlink(resampled)
                            except OSError:
                                pass
                            return CompletedPlaybackControl()
                        else:
                            def _paplay_bg():
                                subprocess.run(['paplay', resampled], timeout=120)
                                try:
                                    os.unlink(resampled)
                                except OSError:
                                    pass
                            t = threading.Thread(target=_paplay_bg, daemon=True)
                            t.start()
                            return ThreadPlaybackControl(t)
            except Exception as e:
                self.logger.warning(f"paplay fallback failed: {e}")

        self.logger.error("❌ AUDIO REQUIRES: pip install playsound==1.2.2 sounddevice pydub")
        self.logger.error("❌ Also ensure audio device drivers are installed on your system")
        return CompletedPlaybackControl()
    
    def play_buffer(self, audio_data, sample_rate=44100, block=False):
        """
        Play audio from a buffer
        
        Args:
            audio_data (numpy.ndarray): Audio data as numpy array
            sample_rate (int): Sample rate in Hz
            block (bool): Whether to block until playback completes
            
        Returns:
            PlaybackControl: Object with stop() method
        """
        self.logger.info(f"Playing audio buffer at {sample_rate}Hz")
        
        # Try sounddevice first as it's best for buffer playback
        if 'sounddevice' in self.available_libraries:
            try:
                import sounddevice as sd
                
                if block:
                    sd.play(audio_data, sample_rate)
                    sd.wait()
                    return CompletedPlaybackControl()  # Already finished playing
                else:
                    sd.play(audio_data, sample_rate)
                    return SoundDevicePlaybackControl()
            
            except Exception as e:
                self.logger.error(f"Error playing buffer with sounddevice: {e}")
        
        # Fall back to pydub via temporary file
        if 'pydub' in self.available_libraries:
            try:
                from pydub import AudioSegment
                from pydub.playback import play
                import wave
                
                # Convert numpy array to WAV file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                with wave.open(temp_path, 'wb') as wf:
                    wf.setnchannels(1)  # Mono
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_data.tobytes())
                
                # Now play the temporary file
                sound = AudioSegment.from_file(temp_path)
                
                if block:
                    play(sound)
                    os.unlink(temp_path)  # Clean up temp file
                    return CompletedPlaybackControl()
                else:
                    def play_and_cleanup():
                        play(sound)
                        os.unlink(temp_path)  # Clean up temp file
                    
                    play_thread = threading.Thread(target=play_and_cleanup)
                    play_thread.daemon = True
                    play_thread.start()
                    
                    return ThreadPlaybackControl(play_thread)
            
            except Exception as e:
                self.logger.error(f"Error playing buffer with pydub: {e}")
        
        self.logger.error("❌ Buffer playback requires sounddevice")
        return CompletedPlaybackControl()
    
    def record_audio(self, duration, sample_rate=44100, channels=1):
        """
        Record audio for a specified duration
        
        Args:
            duration (float): Recording duration in seconds
            sample_rate (int): Sample rate in Hz
            channels (int): Number of channels (1=mono, 2=stereo)
            
        Returns:
            numpy.ndarray: Recorded audio data
        """
        self.logger.info(f"Recording audio for {duration}s at {sample_rate}Hz with {channels} channels")
        
        if 'sounddevice' in self.available_libraries:
            try:
                import sounddevice as sd
                
                self.recording = True
                recording = sd.rec(
                    int(duration * sample_rate),
                    samplerate=sample_rate,
                    channels=channels,
                    blocking=True
                )
                self.recording = False
                
                self.logger.info(f"Recorded {len(recording)/sample_rate:.2f}s of audio")
                return recording
            
            except Exception as e:
                self.logger.error(f"Error recording with sounddevice: {e}")
        
        self.logger.error("❌ Recording requires sounddevice")
        return np.zeros((int(duration * sample_rate), channels))
    
    def stop_recording(self):
        """Stop any ongoing recording"""
        if self.recording:
            self.logger.info("Stopping recording")
            if 'sounddevice' in self.available_libraries:
                try:
                    import sounddevice as sd
                    sd.stop()
                except Exception as e:
                    self.logger.error(f"Error stopping sounddevice: {e}")
            
            self.recording = False
    
    def save_audio(self, audio_data, filename, sample_rate=44100):
        """
        Save audio data to a file
        
        Args:
            audio_data (numpy.ndarray): Audio data to save
            filename (str): Output filename
            sample_rate (int): Sample rate in Hz
            
        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.info(f"Saving audio to file: {filename}")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Determine file format from extension
        ext = os.path.splitext(filename)[1].lower()
        
        # Save using soundfile if available
        try:
            import soundfile as sf
            sf.write(filename, audio_data, sample_rate)
            self.logger.info(f"Audio saved to {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving with soundfile: {e}")
        
        # Fall back to wave module for .wav files
        if ext == '.wav':
            try:
                import wave
                with wave.open(filename, 'wb') as wf:
                    wf.setnchannels(audio_data.shape[1] if len(audio_data.shape) > 1 else 1)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_data.tobytes())
                self.logger.info(f"Audio saved to {filename}")
                return True
            except Exception as e:
                self.logger.error(f"Error saving with wave module: {e}")
        
        self.logger.error(f"Could not save audio to {filename}")
        return False


class CompletedPlaybackControl:
    """Playback control for completed/blocking playback - no mock."""
    
    def stop(self):
        """Stop playback - no-op since playback already completed."""
        pass  # Playback already finished


class ThreadPlaybackControl:
    """Thread-based playback control"""
    
    def __init__(self, thread):
        self.thread = thread
        self.logger = logging.getLogger(__name__)
    
    def stop(self):
        """Stop playback by terminating thread"""
        # Thread playback cannot be interrupted - log warning
        self.logger.warning("Thread-based playback cannot be stopped mid-stream")


class SoundDevicePlaybackControl:
    """SoundDevice playback control"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def stop(self):
        """Stop sounddevice playback"""
        try:
            import sounddevice as sd
            sd.stop()
            self.logger.info("Stopped sounddevice playback")
        except Exception as e:
            self.logger.error(f"Error stopping sounddevice: {e}")


# SimpleAudio compatibility layer
class WaveObject:
    """Compatibility class for SimpleAudio WaveObject"""
    
    def __init__(self, audio_data=None, filename=None):
        self.logger = logging.getLogger(__name__)
        self.audio_data = audio_data
        self.filename = filename
        self.adapter = KingdomAudioAdapter()
    
    @classmethod
    def from_wave_file(cls, filename):
        """Create a WaveObject from a wave file"""
        return cls(filename=filename)
    
    @classmethod
    def from_wave_data(cls, audio_data, num_channels=1, bytes_per_sample=2, sample_rate=44100):
        """Create a WaveObject from wave data"""
        # Convert bytes to numpy array if needed
        if isinstance(audio_data, bytes):
            import numpy as np
            audio_data = np.frombuffer(audio_data, dtype=np.int16)
            audio_data = audio_data.reshape(-1, num_channels)
        
        return cls(audio_data=audio_data)
    
    def play(self):
        """Play the audio"""
        if self.filename:
            return self.adapter.play_audio(self.filename, block=False)
        elif self.audio_data is not None:
            return self.adapter.play_buffer(self.audio_data, block=False)
        else:
            self.logger.error("Nothing to play (no filename or audio data provided)")
            return MockPlaybackControl()


# Compatibility functions for simpleaudio
def play_buffer(audio_data, num_channels=1, bytes_per_sample=2, sample_rate=44100):
    """Play an audio buffer (compatibility function for simpleaudio)"""
    adapter = KingdomAudioAdapter()
    return adapter.play_buffer(audio_data, sample_rate, False)

def stop_all():
    """Stop all playback (compatibility function for simpleaudio)"""
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass


# PyAudio compatibility class
class PyAudio:
    """Compatibility class for PyAudio"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.adapter = KingdomAudioAdapter()
    
    def get_device_count(self):
        """Get the number of audio devices"""
        return len(self.adapter.get_playback_devices()) + len(self.adapter.get_recording_devices())
    
    def get_device_info_by_index(self, index):
        """Get information about an audio device by index"""
        playback_devices = self.adapter.get_playback_devices()
        recording_devices = self.adapter.get_recording_devices()
        
        all_devices = playback_devices + recording_devices
        
        if 0 <= index < len(all_devices):
            device = all_devices[index]
            return {
                'index': device['index'],
                'name': device['name'],
                'maxInputChannels': device.get('channels', 0) if index >= len(playback_devices) else 0,
                'maxOutputChannels': device.get('channels', 0) if index < len(playback_devices) else 0,
                'defaultSampleRate': device.get('default_samplerate', 44100)
            }
        
        # Return honest "no device detected" instead of fake device
        logger.warning("No audio device detected at index %d", index)
        return None  # Honest: no device available
    
    def get_default_input_device_info(self):
        """Get default input device info"""
        recording_devices = self.adapter.get_recording_devices()
        if recording_devices:
            device = recording_devices[0]
            return {
                'index': device['index'],
                'name': device['name'],
                'maxInputChannels': device.get('channels', 1),
                'maxOutputChannels': 0,
                'defaultSampleRate': device.get('default_samplerate', 44100)
            }
        
        # Return honest "no device detected" instead of fake device
        logger.warning("No recording audio device detected")
        return None  # Honest: no recording device available
    
    def get_default_output_device_info(self):
        """Get default output device info"""
        playback_devices = self.adapter.get_playback_devices()
        if playback_devices:
            device = playback_devices[0]
            return {
                'index': device['index'],
                'name': device['name'],
                'maxInputChannels': 0,
                'maxOutputChannels': device.get('channels', 2),
                'defaultSampleRate': device.get('default_samplerate', 44100)
            }
        
        # Return honest "no device detected" instead of fake device
        logger.warning("No playback audio device detected")
        return None  # Honest: no playback device available
    
    def open(self, *args, **kwargs):
        """Open an audio stream"""
        return MockStream()
    
    def terminate(self):
        """Terminate PyAudio"""
        pass


class MockStream:
    """Mock audio stream for PyAudio compatibility"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active = False
    
    def start_stream(self):
        """Start the audio stream"""
        self.active = True
        self.logger.info("Started mock audio stream")
    
    def stop_stream(self):
        """Stop the audio stream"""
        self.active = False
        self.logger.info("Stopped mock audio stream")
    
    def close(self):
        """Close the audio stream"""
        self.active = False
        self.logger.info("Closed mock audio stream")
    
    def is_active(self):
        """Check if the audio stream is active"""
        return self.active
    
    def write(self, data, *args, **kwargs):
        """Write data to the audio stream"""
        self.logger.info(f"Mock write: {len(data)} bytes")
        return len(data)
    
    def read(self, frames, *args, **kwargs):
        """Read data from the audio stream"""
        # Generate random audio data for mocking
        self.logger.info(f"Mock read: {frames} frames")
        import numpy as np
        return np.random.randint(-32768, 32767, frames, dtype=np.int16).tobytes()
