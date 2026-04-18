#!/usr/bin/env python3
"""
Voice Processing System for Kingdom AI

This module provides advanced voice processing capabilities for Kingdom AI,
including speech-to-text, text-to-speech, and voice command recognition.
It integrates with the VoiceManager and ThothAI components.
"""

import logging
import asyncio
import time
import json
import traceback
from typing import Dict, Any

from core.base_component import BaseComponent

# Try to import voice dependencies
try:
    from core.voice_manager import VoiceManager
except ImportError:
    VoiceManager = None

try:
    from core.thoth import Thoth
except ImportError:
    try:
        from core.thothai import ThothAI as Thoth
    except ImportError:
        Thoth = None

logger = logging.getLogger("KingdomAI.VoiceProcessing")

class VoiceProcessingSystem(BaseComponent):
    """
    Voice Processing System for Kingdom AI
    
    Provides advanced voice processing capabilities including:
    - Speech recognition with noise filtering
    - Advanced text-to-speech with emotional inflection
    - Voice command recognition and processing
    - Integration with ThothAI for natural language understanding
    - Black Panther voice integration
    """
    
    def __init__(self, event_bus=None, config=None, name="VoiceProcessingSystem"):
        """Initialize the Voice Processing System"""
        super().__init__(name=name, event_bus=event_bus, config=config)
        self.config = config or {}
        self.voice_manager = None
        self.thoth_ai = None
        
        # Voice processing settings
        self.voice_enabled = self.config.get('voice_enabled', True)
        self.voice_language = self.config.get('voice_language', 'en-US')
        self.voice_model = self.config.get('voice_model', 'Black-Panther')
        self.wake_words = self.config.get('wake_words', ['kingdom', 'panther', 'wakanda'])
        self.command_confidence_threshold = self.config.get('command_confidence_threshold', 0.7)
        self.is_listening = False
        self.last_command_time = 0
        self.command_cooldown = 2.0  # seconds
        
        # Voice command mapping
        self.command_handlers = {}
        
        # Stats tracking
        self.stats = {
            'commands_received': 0,
            'commands_processed': 0,
            'tts_requests': 0,
            'stt_requests': 0,
            'errors': 0
        }
        
        logger.info(f"{name} initialized with voice model: {self.voice_model}")
    
    async def initialize(self) -> bool:
        """Initialize the Voice Processing System"""
        try:
            logger.info("Initializing Voice Processing System...")
            
            # Call parent initialization
            await super().initialize()
            
            # Initialize voice manager
            if self.event_bus is not None and hasattr(self.event_bus, "get_component"):
                try:
                    self.voice_manager = self.event_bus.get_component("voice_manager", silent=True)
                except TypeError:
                    try:
                        self.voice_manager = self.event_bus.get_component("voice_manager")
                    except Exception:
                        self.voice_manager = None
                except Exception:
                    self.voice_manager = None

            if self.voice_manager is None:
                if VoiceManager is not None:
                    self.voice_manager = VoiceManager(event_bus=self.event_bus, config=self.config)
                    await self.voice_manager.initialize()
                    if self.event_bus is not None and hasattr(self.event_bus, "register_component"):
                        try:
                            self.event_bus.register_component("voice_manager", self.voice_manager)
                        except Exception:
                            pass
                    logger.info("Voice manager initialized")
                else:
                    # SOTA 2026 FIX: Voice is optional - use debug not warning
                    logger.debug("ℹ️ VoiceManager not available (optional feature)")
            
            # Initialize ThothAI
            if Thoth is not None:
                self.thoth_ai = Thoth(event_bus=self.event_bus, config=self.config)
                await self.thoth_ai.initialize()
                logger.info("ThothAI initialized for voice processing")
            else:
                # SOTA 2026 FIX: ThothAI is optional - use debug not warning
                logger.debug("ℹ️ ThothAI not available for voice processing (optional)")
            
            # Subscribe to events
            if self.event_bus:
                self.event_bus.subscribe_sync("voice.command", self._handle_voice_command)
                # Any component (including OllamaAI) can emit a high-level
                # "voice.response" event with a text payload.  We convert that
                # into a concrete "voice.speak" request so it flows through the
                # standard TTS pipeline (Black Panther / GPT-SoVITS voice).
                self.event_bus.subscribe_sync("voice.response", self._handle_voice_response)
                # UNIFIED VOICE ROUTING: voice.listen is handled by core.voice_manager.VoiceManager only.
                # VoiceProcessingSystem handles higher-level voice.command and voice.response events.
                self.event_bus.subscribe_sync("voice.process", self._handle_process_voice)
                self.event_bus.subscribe_sync("system.shutdown", self._handle_shutdown)
                logger.info("Subscribed to voice events (command, response, process)")
            
            # Register command handlers
            self._register_command_handlers()
            
            # Publish initialization complete event
            if self.event_bus:
                self.event_bus.publish("voice.processing.initialized", {
                    "status": "initialized",
                    "timestamp": time.time()
                })
            
            self.is_initialized = True
            logger.info("Voice Processing System initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Voice Processing System: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def initialize_sync(self) -> bool:
        """Synchronous initialization for compatibility"""
        try:
            logger.info("Initializing Voice Processing System (sync)...")
            
            # Initialize voice manager
            if self.event_bus is not None and hasattr(self.event_bus, "get_component"):
                try:
                    self.voice_manager = self.event_bus.get_component("voice_manager", silent=True)
                except TypeError:
                    try:
                        self.voice_manager = self.event_bus.get_component("voice_manager")
                    except Exception:
                        self.voice_manager = None
                except Exception:
                    self.voice_manager = None

            if self.voice_manager is None:
                if VoiceManager is not None:
                    self.voice_manager = VoiceManager(event_bus=self.event_bus, config=self.config)
                    logger.info("Voice manager initialized (sync)")
                else:
                    logger.debug("ℹ️ VoiceManager not available (optional feature)")
            
            # Initialize ThothAI
            if Thoth is not None:
                self.thoth_ai = Thoth(event_bus=self.event_bus, config=self.config)
                if hasattr(self.thoth_ai, 'initialize_sync'):
                    self.thoth_ai.initialize_sync()
                logger.info("ThothAI initialized for voice processing (sync)")
            else:
                logger.debug("ℹ️ ThothAI not available for voice processing (optional)")
            
            # Register command handlers
            self._register_command_handlers()
            
            self.is_initialized = True
            logger.info("Voice Processing System initialization complete (sync)")
            return True
            
        except Exception as e:
            logger.error(f"Error in synchronous initialization: {e}")
            return False
    
    async def _handle_voice_response(self, event_data: Dict[str, Any]) -> None:
        """Bridge generic voice responses into the TTS pipeline.

        This is primarily used by OllamaAI and other brain components that
        publish a high-level ``voice.response`` event with a textual
        ``response`` field and an optional ``should_speak`` flag.  When
        ``should_speak`` is true (default), we emit a ``voice.speak`` event,
        which is handled by :meth:`_handle_speak_request` / VoiceManager and
        ultimately spoken using the configured Black Panther / GPT-SoVITS
        backend.
        """

        try:
            if not isinstance(event_data, dict):
                return

            # Respect explicit flag; default to speaking if not provided.
            should_speak = event_data.get("should_speak", True)
            if not should_speak:
                return

            text = event_data.get("response") or event_data.get("text")
            if not text:
                logger.warning("voice.response event without response/text payload")
                return

            priority = event_data.get("priority", "normal")
            voice = event_data.get("voice", self.voice_model)

            if self.event_bus:
                self.event_bus.publish("voice.speak", {
                    "text": text,
                    "priority": priority,
                    "voice": voice,
                    "source": event_data.get("source", "ollama"),
                })
        except Exception as e:
            logger.error(f"Error handling voice.response event: {e}")
            self.stats['errors'] += 1
    
    async def _handle_voice_command(self, event_data: Dict[str, Any]) -> None:
        """Handle voice command events"""
        try:
            if not event_data or 'command' not in event_data:
                logger.warning("Received voice.command event without command data")
                return
                
            command = event_data['command'].lower()
            params = event_data.get('parameters', {})
            confidence = event_data.get('confidence', 1.0)
            
            # Update stats
            self.stats['commands_received'] += 1
            
            # Check confidence threshold
            if confidence < self.command_confidence_threshold:
                logger.info(f"Command '{command}' rejected due to low confidence: {confidence}")
                
                # Provide feedback about low confidence
                if self.event_bus:
                    self.event_bus.publish("voice.speak", {
                        "text": "I'm not sure I understood that command correctly. Could you please repeat it?",
                        "priority": "high"
                    })
                return
            
            # Check command cooldown
            current_time = time.time()
            if current_time - self.last_command_time < self.command_cooldown:
                logger.info(f"Command '{command}' rejected due to cooldown")
                return
                
            self.last_command_time = current_time
            
            # Process command
            logger.info(f"Processing voice command: {command} with params: {params}")
            
            # Check if we have a handler for this command
            if command in self.command_handlers:
                handler = self.command_handlers[command]
                await handler(params)
                self.stats['commands_processed'] += 1
                
                # Provide feedback
                if self.event_bus:
                    self.event_bus.publish("gui.output", {
                        "message": f"Executed voice command: {command}",
                        "component": "voice_processing"
                    })
            else:
                # If no direct handler, try to process as natural language
                if self.thoth_ai:
                    # Formulate prompt for ThothAI to process the command
                    prompt = f"Process this voice command as if you are the Kingdom AI assistant: '{command}'"
                    
                    if hasattr(self.thoth_ai, 'process_voice_query') and callable(getattr(self.thoth_ai, 'process_voice_query')):
                        await self.thoth_ai.process_voice_query({
                            "query": command,
                            "params": params,
                            "source": "voice_command"
                        })
                    elif hasattr(self.thoth_ai, 'generate_response') and callable(getattr(self.thoth_ai, 'generate_response')):
                        response = await self.thoth_ai.generate_response(prompt)
                        if response and self.event_bus:
                            self.event_bus.publish("voice.speak", {
                                "text": response,
                                "priority": "normal"
                            })
                else:
                    # SOTA 2026 FIX: This is an expected fallback scenario - use debug
                    logger.debug(f"ℹ️ No handler for command '{command}' and ThothAI not available")
                    
                    if self.event_bus:
                        self.event_bus.publish("voice.speak", {
                            "text": f"I don't know how to handle the command: {command}",
                            "priority": "normal"
                        })
                
        except Exception as e:
            logger.error(f"Error handling voice command: {e}")
            self.stats['errors'] += 1
    
    async def _handle_speak_request(self, event_data: Dict[str, Any]) -> None:
        """Handle requests to speak text via TTS"""
        try:
            if not event_data or 'text' not in event_data:
                logger.warning("Received voice.speak event without text data")
                return
                
            text = event_data['text']
            priority = event_data.get('priority', 'normal')
            voice = event_data.get('voice', self.voice_model)
            
            # Update stats
            self.stats['tts_requests'] += 1
            
            logger.info(f"Speaking text with {voice} voice: {text[:50]}...")
            
            # Check if we have a voice manager
            if self.voice_manager:
                # Speak the text
                if hasattr(self.voice_manager, 'speak') and callable(getattr(self.voice_manager, 'speak')):
                    success = await self.voice_manager.speak(text)
                    if not success:
                        logger.warning("Failed to speak text using voice manager")
            else:
                logger.warning("Voice manager not available for speaking text")
                
                # Try to use the event bus to speak
                if self.event_bus:
                    self.event_bus.publish("gui.output", {
                        "message": f"[VOICE]: {text}",
                        "component": "voice_processing"
                    })
                
        except Exception as e:
            logger.error(f"Error handling speak request: {e}")
            self.stats['errors'] += 1
    
    async def _handle_listen_request(self, event_data: Dict[str, Any] = None) -> None:
        """Handle requests to listen for speech"""
        try:
            if self.is_listening:
                logger.info("Already listening, ignoring request")
                return
                
            self.is_listening = True
            timeout = event_data.get('timeout', 10.0) if event_data else 10.0
            
            # Update stats
            self.stats['stt_requests'] += 1
            
            logger.info(f"Listening for speech with timeout {timeout}s...")
            
            # Check if we have a voice manager
            if self.voice_manager and hasattr(self.voice_manager, 'listen') and callable(getattr(self.voice_manager, 'listen')):
                # Listen for speech
                recognized_text = await asyncio.to_thread(self.voice_manager.listen)
                
                if recognized_text:
                    logger.info(f"Recognized speech: {recognized_text}")
                    
                    # Process the recognized text as a command
                    if self.event_bus:
                        self.event_bus.publish("voice.process", {
                            "text": recognized_text,
                            "source": "voice_recognition"
                        })
                else:
                    logger.warning("Failed to recognize speech")
            else:
                logger.warning("Voice manager not available for listening")
                
            self.is_listening = False
                
        except Exception as e:
            logger.error(f"Error handling listen request: {e}")
            self.stats['errors'] += 1
            self.is_listening = False
    
    async def _handle_process_voice(self, event_data: Dict[str, Any]) -> None:
        """Process voice input text to extract commands and intent"""
        try:
            if not event_data or 'text' not in event_data:
                logger.warning("Received voice.process event without text data")
                return
                
            text = event_data['text'].lower()
            source = event_data.get('source', 'unknown')
            
            logger.info(f"Processing voice input from {source}: {text}")
            
            # Check for wake words if needed
            contains_wake_word = any(wake_word in text for wake_word in self.wake_words)
            
            # Process as command if wake word is present or if directly from voice recognition
            if contains_wake_word or source == 'voice_recognition':
                # Try to extract command intent
                if self.thoth_ai and hasattr(self.thoth_ai, 'process_voice_query'):
                    # Use ThothAI to process the voice query
                    await self.thoth_ai.process_voice_query({
                        "query": text,
                        "source": source
                    })
                else:
                    # Basic command extraction
                    # Remove wake words from the text
                    for wake_word in self.wake_words:
                        text = text.replace(wake_word, '').strip()
                    
                    # Split into command and args
                    parts = text.split(' ')
                    if len(parts) > 0:
                        command = parts[0]
                        args_text = ' '.join(parts[1:])
                        
                        # Try to parse args as JSON if possible
                        try:
                            args = json.loads(args_text)
                        except:
                            args = {"text": args_text}
                        
                        # Publish command
                        if self.event_bus:
                            self.event_bus.publish("voice.command", {
                                "command": command,
                                "parameters": args,
                                "confidence": 0.8,
                                "source": source
                            })
            else:
                logger.info(f"No wake word found in: {text}")
                
        except Exception as e:
            logger.error(f"Error processing voice input: {e}")
            self.stats['errors'] += 1
    
    async def _handle_shutdown(self, _: Dict[str, Any] = None) -> None:
        """Handle system shutdown event"""
        try:
            logger.info("Shutting down Voice Processing System")
            
            # Stop any ongoing voice processes
            self.is_listening = False
            
            # Clean up voice manager
            if self.voice_manager and hasattr(self.voice_manager, 'stop'):
                await self.voice_manager.stop()
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def _register_command_handlers(self) -> None:
        """Register command handlers for common voice commands"""
        
        # Define command handlers
        async def handle_status(params):
            """Handle status command"""
            status_text = (
                f"Voice Processing System Status: Active. "
                f"Commands received: {self.stats['commands_received']}. "
                f"Commands processed: {self.stats['commands_processed']}. "
                f"Text-to-speech requests: {self.stats['tts_requests']}. "
                f"Speech recognition requests: {self.stats['stt_requests']}."
            )
            
            if self.event_bus:
                self.event_bus.publish("voice.speak", {
                    "text": status_text,
                    "priority": "high"
                })
                
                # Also publish to GUI
                self.event_bus.publish("gui.output", {
                    "message": status_text,
                    "component": "voice_processing"
                })
        
        async def handle_help(params):
            """Handle help command"""
            help_text = (
                "Available voice commands include: status, help, mining status, "
                "market status, trading dashboard, portfolio status, and system status."
            )
            
            if self.event_bus:
                self.event_bus.publish("voice.speak", {
                    "text": help_text,
                    "priority": "high"
                })
        
        async def handle_mining_status(params):
            """Handle mining status command"""
            if self.event_bus:
                # Request mining status from mining system
                self.event_bus.publish("mining.status.request", {
                    "requestor": "voice_processing",
                    "request_id": f"voice_{time.time()}"
                })
                
                # Inform user that request was sent
                self.event_bus.publish("voice.speak", {
                    "text": "Requesting mining status...",
                    "priority": "normal"
                })
        
        async def handle_market_status(params):
            """Handle market status command"""
            if self.event_bus:
                # Request market status
                self.event_bus.publish("market.status.request", {
                    "requestor": "voice_processing",
                    "request_id": f"voice_{time.time()}"
                })
                
                # Inform user that request was sent
                self.event_bus.publish("voice.speak", {
                    "text": "Requesting market status...",
                    "priority": "normal"
                })
        
        async def handle_trading_dashboard(params):
            """Handle trading dashboard command"""
            if self.event_bus:
                self.event_bus.publish("gui.show.trading", {
                    "requestor": "voice_processing"
                })
                
                self.event_bus.publish("voice.speak", {
                    "text": "Opening trading dashboard.",
                    "priority": "normal"
                })
        
        async def handle_portfolio_status(params):
            """Handle portfolio status command"""
            if self.event_bus:
                self.event_bus.publish("portfolio.status.request", {
                    "requestor": "voice_processing",
                    "request_id": f"voice_{time.time()}"
                })
                
                self.event_bus.publish("voice.speak", {
                    "text": "Requesting portfolio status...",
                    "priority": "normal"
                })
        
        async def handle_system_status(params):
            """Handle system status command"""
            if self.event_bus:
                self.event_bus.publish("system.status.request", {
                    "requestor": "voice_processing",
                    "request_id": f"voice_{time.time()}"
                })
                
                self.event_bus.publish("voice.speak", {
                    "text": "Checking system status...",
                    "priority": "normal"
                })
        
        # Register handlers
        self.command_handlers = {
            "status": handle_status,
            "help": handle_help,
            "mining": handle_mining_status,
            "market": handle_market_status,
            "trading": handle_trading_dashboard,
            "portfolio": handle_portfolio_status,
            "system": handle_system_status
        }
        
        logger.info(f"Registered {len(self.command_handlers)} voice command handlers")
    
    async def process_text_command(self, text: str) -> bool:
        """Process a text command as if it were a voice command
        
        This allows testing voice commands via text input
        """
        try:
            if not text:
                return False
                
            # Process the text command
            await self._handle_process_voice({
                "text": text,
                "source": "text_input"
            })
            
            return True
        except Exception as e:
            logger.error(f"Error processing text command: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the Voice Processing System"""
        return {
            "initialized": self.is_initialized,
            "voice_enabled": self.voice_enabled,
            "voice_model": self.voice_model,
            "is_listening": self.is_listening,
            "stats": self.stats,
            "wake_words": self.wake_words,
            "voice_manager_available": self.voice_manager is not None,
            "thoth_ai_available": self.thoth_ai is not None
        }
