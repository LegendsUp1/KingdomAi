"""
Voice Assistant Component for Kingdom AI.

This module provides voice interaction capabilities for the Kingdom AI system.
"""

import logging
import asyncio
import os
import sys
import subprocess
import threading
from typing import Dict, Any, Optional, List

# Import base component
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_component import BaseComponent

logger = logging.getLogger(__name__)

class VoiceAssistant(BaseComponent):
    """
    Voice Assistant for the Kingdom AI system.
    
    Handles text-to-speech, voice recognition, and Black Panther voice integration.
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the Voice Assistant component.
        
        Args:
            event_bus: Event bus for component communication
            config: Configuration manager
        """
        super().__init__()
        self.event_bus = event_bus
        self.config = config
        self.status = "initializing"
        self.voice_model = "black_panther"
        self.is_speaking = False
        self.speak_queue = asyncio.Queue()
        self.speech_lock = threading.Lock()
        
    async def initialize(self) -> bool:
        """Initialize the Voice Assistant component."""
        logger.info("Initializing Voice Assistant...")
        
        try:
            # Register with event bus
            if self.event_bus:
                enable_legacy = os.environ.get("ENABLE_LEGACY_VOICE", "").lower() in ("1", "true", "yes", "on")
                if enable_legacy:
                    self.event_bus.subscribe("voice.speak", self._handle_speak_event)
                    logger.info("VoiceAssistant legacy TTS handler enabled by config")
                else:
                    logger.info("VoiceAssistant legacy TTS handler disabled; VoiceManager will handle voice.speak")

                self.event_bus.subscribe("voice.listen", self._handle_listen_event)
                
                # Publish ready status
                self.event_bus.publish("component.ready", {
                    "component": "VoiceAssistant",
                    "status": "ready"
                })
            
            # Set component as ready
            self.status = "ready"
            logger.info("Voice Assistant initialized successfully")
            
            # Start background speech processor
            self._start_speech_processor()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Voice Assistant: {e}")
            self.status = "failed"
            
            # Publish failed status
            if self.event_bus:
                self.event_bus.publish("component.failed", {
                    "component": "VoiceAssistant",
                    "error": str(e)
                })
            return False
    
    def _start_speech_processor(self):
        """Start the background speech processor."""
        threading.Thread(target=self._process_speech_queue, daemon=True).start()
        
    def initialize_sync(self):
        """Synchronous version of initialize"""
        return True
        
    def _process_speech_queue(self):
        """Process speech queue in background."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self._speech_processor())
        
    async def _speech_processor(self):
        """Process speech queue."""
        while True:
            text = await self.speak_queue.get()
            with self.speech_lock:
                self.is_speaking = True
                try:
                    # Try to use Black Panther voice if available
                    try:
                        result = await self._use_black_panther_voice(text)
                        if not result:
                            await self._use_fallback_voice(text)
                    except Exception:
                        await self._use_fallback_voice(text)
                finally:
                    self.is_speaking = False
                    self.speak_queue.task_done()
    
    async def _use_black_panther_voice(self, text):
        """Use Black Panther voice for speech."""
        try:
            # Check if black_panther_voice.py exists
            bp_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                   "black_panther_voice.py")
            
            if os.path.exists(bp_script):
                # Call the black panther voice script
                cmd = [sys.executable, bp_script, text]
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    logger.info(f"Black Panther voice used successfully: {text}")
                    return True
                else:
                    logger.error(f"Black Panther voice failed: {stderr.decode()}")
                    return False
            else:
                logger.warning("Black Panther voice script not found")
                return False
        except Exception as e:
            logger.error(f"Error using Black Panther voice: {e}")
            return False
    
    async def _use_fallback_voice(self, text):
        """Use fallback voice for speech."""
        try:
            # Try using system TTS if available
            if sys.platform == 'win32':
                # Windows
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                    logger.info(f"Fallback voice used: {text}")
                    return True
                except Exception as e:
                    logger.error(f"Fallback voice error: {e}")
                    return False
            elif sys.platform == 'darwin':
                # macOS
                cmd = ['say', text]
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                return True
            else:
                # Linux
                try:
                    cmd = ['espeak', text]
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await process.communicate()
                    return True
                except Exception:
                    logger.warning("espeak not found, trying festival")
                    try:
                        cmd = ['festival', '--tts']
                        process = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        process.stdin.write(text.encode())
                        await process.stdin.drain()
                        process.stdin.close()
                        await process.wait()
                        return True
                    except Exception as e:
                        logger.error(f"All fallback voices failed: {e}")
                        return False
        except Exception as e:
            logger.error(f"Error in fallback voice: {e}")
            return False
    
    async def speak(self, text):
        """
        Speak the given text.
        
        Args:
            text (str): Text to speak
        """
        logger.info(f"Adding to speech queue: {text}")
        await self.speak_queue.put(text)
        
        # Also publish to event bus
        if self.event_bus:
            self.event_bus.publish("voice.speaking", {
                "text": text
            })
    
    def get_status(self):
        """Get the current status of the Voice Assistant."""
        return self.status
    
    async def _handle_speak_event(self, data):
        """Handle speak events from the event bus."""
        if isinstance(data, dict) and 'text' in data:
            await self.speak(data['text'])
        elif isinstance(data, str):
            await self.speak(data)
    
    async def _handle_listen_event(self, data):
        """Handle listen events from the event bus: capture audio and run speech recognition."""
        if self.status != "ready":
            logger.warning("VoiceAssistant not ready, ignoring listen event")
            return

        try:
            timeout = 5
            if isinstance(data, dict):
                timeout = data.get('timeout', data.get('duration', 5))

            recognized_text = await asyncio.get_event_loop().run_in_executor(
                None, self._recognize_speech, timeout
            )

            if recognized_text and self.event_bus:
                self.event_bus.publish("voice.recognized", {
                    "text": recognized_text,
                    "confidence": 1.0,
                    "source": "voice_assistant",
                })
                logger.info(f"Speech recognised: {recognized_text[:80]}")
            elif not recognized_text:
                if self.event_bus:
                    self.event_bus.publish("voice.recognized", {
                        "text": "",
                        "confidence": 0.0,
                        "error": "No speech detected",
                        "source": "voice_assistant",
                    })
        except Exception as e:
            logger.error(f"Error in listen event handler: {e}")
            if self.event_bus:
                self.event_bus.publish("voice.error", {
                    "error": str(e),
                    "event": "listen",
                })

    def _recognize_speech(self, timeout: int = 5) -> str:
        """Blocking speech recognition via the speech_recognition library."""
        try:
            import speech_recognition as sr
        except ImportError:
            logger.warning("speech_recognition not installed – returning empty")
            return ""

        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                logger.debug("Listening for speech (timeout=%ds)...", timeout)
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=15)

            text = recognizer.recognize_google(audio)
            return str(text)
        except sr.WaitTimeoutError:
            logger.debug("No speech detected within timeout")
            return ""
        except sr.UnknownValueError:
            logger.debug("Speech was unintelligible")
            return ""
        except sr.RequestError as e:
            logger.warning(f"Speech recognition service error: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected speech recognition error: {e}")
            return ""
    
    async def close(self):
        """Close the Voice Assistant component."""
        logger.info("Closing Voice Assistant...")
        with self.speech_lock:
            self.status = "closed"
            
            # Unsubscribe from events
            if self.event_bus:
                self.event_bus.unsubscribe("voice.speak", self._handle_speak_event)
                self.event_bus.unsubscribe("voice.listen", self._handle_listen_event)
            
        await super().close()
