"""
Voice System module for Kingdom AI.

SOTA 2026 ARCHITECTURE:
This is a THIN WRAPPER that delegates to the unified voice system:
- VoiceManager: SOLE VOICE AUTHORITY - Black Panther voice pipeline

DO NOT duplicate voice logic here - use VoiceManager!
"""
import logging
from core.base_component import BaseComponent
from core.event_bus import EventBus

logger = logging.getLogger("KingdomAI.VoiceSystem")


class VoiceSystem(BaseComponent):
    """
    Voice system thin wrapper - delegates to VoiceManager (SOLE VOICE AUTHORITY).
    
    SOTA 2026: This component exists for backwards compatibility.
    All actual voice processing goes through VoiceManager which uses:
    - Black Panther voice (GPT-SoVITS with Dec 19th cloned voice)
    - Whisper for speech recognition
    """
    
    def __init__(self, event_bus: EventBus) -> None:
        """Initialize voice system.
        
        Args:
            event_bus: Event bus instance
        """
        super().__init__("VoiceSystem", event_bus)
        self.volume = 100
        self.rate = 150
        self.voice_type = "black_panther"
        self._initialized = False
        self._voice_manager = None
        
    @property
    def initialized(self) -> bool:
        return self._initialized
        
    @initialized.setter
    def initialized(self, value: bool) -> None:
        self._initialized = value
        
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize the voice system by connecting to VoiceManager.
        
        Args:
            event_bus: Optional EventBus instance to use for initialization
            config: Optional configuration to use for initialization
            
        Returns:
            bool: Success status
        """
        if event_bus is not None:
            self.event_bus = event_bus
            
        try:
            # SOTA 2026: Connect to VoiceManager (SOLE VOICE AUTHORITY)
            await self._connect_to_voice_manager()
            
            self.initialized = True
            if self.event_bus:
                self.event_bus.publish("voice.status", {"status": "initialized"})
                
            logger.info("✅ VoiceSystem initialized - delegating to VoiceManager")
            return True
            
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("voice.error", {
                    "error": str(e),
                    "source": "VoiceSystem.initialize"
                })
            logger.error(f"Failed to initialize voice system: {e}")
            return False
    
    async def _connect_to_voice_manager(self) -> None:
        """Connect to VoiceManager (SOLE VOICE AUTHORITY)."""
        if not self.event_bus:
            return
            
        # Get reference to VoiceManager
        self._voice_manager = self.event_bus.get_component("voice_manager")
        
        if self._voice_manager:
            logger.info("✅ Connected to VoiceManager (Black Panther voice)")
        else:
            # Try to import and create VoiceManager if not registered
            try:
                from core.voice_manager import VoiceManager
                self._voice_manager = VoiceManager(event_bus=self.event_bus)
                await self._voice_manager.initialize()
                logger.info("✅ Created and initialized VoiceManager")
            except Exception as e:
                logger.warning(f"Could not connect to VoiceManager: {e}")
        
    async def speak(self, text: str) -> None:
        """Convert text to speech via VoiceManager (Black Panther voice).
        
        Args:
            text: Text to speak
        """
        try:
            if not self.initialized:
                await self.initialize()
            
            # SOTA 2026: ALWAYS delegate to VoiceManager
            if self._voice_manager and hasattr(self._voice_manager, "speak"):
                # VoiceManager.speak may be sync or async
                result = self._voice_manager.speak(text)
                if hasattr(result, '__await__'):
                    await result
                logger.debug(f"Delegated speak to VoiceManager: {text[:50]}...")
            elif self.event_bus:
                # Fallback: Publish voice.speak event for VoiceManager to handle
                self.event_bus.publish("voice.speak.request", {
                    "text": text,
                    "voice": self.voice_type,
                    "source": "VoiceSystem"
                })
                logger.debug(f"Published voice.speak.request: {text[:50]}...")
            
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("voice.error", {
                    "error": str(e),
                    "source": "VoiceSystem.speak",
                    "text": text[:100]
                })
            logger.error(f"Error in speak: {e}")
    
    async def listen(self) -> str:
        """Listen for voice input via VoiceManager."""
        try:
            if not self.initialized:
                await self.initialize()
            
            # SOTA 2026: Delegate to VoiceManager
            if self._voice_manager and hasattr(self._voice_manager, "listen"):
                result = self._voice_manager.listen()
                if hasattr(result, '__await__'):
                    return await result
                return result
            
            # Fallback: Publish listen request event
            if self.event_bus:
                self.event_bus.publish("voice.listen.request", {
                    "source": "VoiceSystem"
                })
            
            return ""
            
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("voice.error", {
                    "error": str(e),
                    "source": "VoiceSystem.listen"
                })
            return ""
    
    def is_speaking(self) -> bool:
        """Check if TTS is currently speaking via VoiceManager."""
        if self._voice_manager and hasattr(self._voice_manager, "is_speaking"):
            return self._voice_manager.is_speaking()
        if self._voice_manager and hasattr(self._voice_manager, "_is_speaking"):
            return self._voice_manager._is_speaking
        return False
    
    def is_listening(self) -> bool:
        """Check if voice recognition is active via VoiceManager."""
        if self._voice_manager and hasattr(self._voice_manager, "is_listening"):
            return self._voice_manager.is_listening()
        if self._voice_manager and hasattr(self._voice_manager, "_is_listening"):
            return self._voice_manager._is_listening
        return False
            
    async def cleanup(self) -> bool:
        """Clean up voice resources.
        
        Returns:
            bool: Success status
        """
        try:
            self.initialized = False
            if self.event_bus:
                self.event_bus.publish("voice.status", {"status": "shutdown"})
            logger.info("VoiceSystem cleaned up")
            return True
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("voice.error", {
                    "error": str(e),
                    "source": "VoiceSystem.cleanup"
                })
            return False
