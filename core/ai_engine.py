"""
AI Engine module for Kingdom AI.

SOTA 2026 ARCHITECTURE:
This is a THIN WRAPPER that delegates to the unified AI systems:
- UnifiedAIRouter: Routes ai.request → brain.request
- BrainRouter: Main Ollama LLM processing with multi-model support
- ThothAI: Advanced AI with learning capabilities

DO NOT duplicate AI logic here - use the unified systems!
"""
import asyncio
import time
import logging
from typing import Optional
from core.base_component import BaseComponent
from core.event_bus import EventBus

logger = logging.getLogger("KingdomAI.AIEngine")


class AISystem(BaseComponent):
    """
    AI system thin wrapper - delegates to UnifiedAIRouter and BrainRouter.
    
    SOTA 2026: This component exists for backwards compatibility.
    All actual AI processing goes through:
    1. ai.request event → UnifiedAIRouter → brain.request → BrainRouter → Ollama
    2. Response comes back via ai.response.unified event
    """
    
    def __init__(self, event_bus: EventBus) -> None:
        """Initialize AI system.
        
        Args:
            event_bus: Event bus instance
        """
        super().__init__("AISystem", event_bus)
        self._initialized = False
        self._unified_router = None
        self._brain_router = None
        self._pending_requests = {}  # request_id -> asyncio.Future
        
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize the AI system by connecting to unified AI architecture.
        
        Args:
            event_bus: Optional EventBus instance to use for initialization
            config: Optional configuration to use for initialization
            
        Returns:
            bool: Success status
        """
        try:
            if event_bus is not None:
                self.event_bus = event_bus
                
            if config is not None:
                self.config = config
            
            # SOTA 2026: Connect to unified AI systems instead of creating own implementation
            await self._connect_to_unified_ai()
            
            self._initialized = True
            
            if self.event_bus is not None:
                self.event_bus.publish("ai.status", {"status": "initialized"})
                
            logger.info("✅ AISystem initialized - delegating to UnifiedAIRouter/BrainRouter")
            return True
            
        except Exception as e:
            if self.event_bus is not None:
                self.event_bus.publish("ai.error", {
                    "error": str(e),
                    "source": "AISystem.initialize"
                })
            logger.error(f"Failed to initialize AI system: {e}")
            return False
    
    async def _connect_to_unified_ai(self) -> None:
        """Connect to the unified AI architecture (UnifiedAIRouter, BrainRouter)."""
        if not self.event_bus:
            return
            
        # Get references to unified AI components
        self._unified_router = self.event_bus.get_component("unified_ai_router")
        self._brain_router = self.event_bus.get_component("brain_router")
        
        # Subscribe to responses
        if hasattr(self.event_bus, 'subscribe_sync'):
            self.event_bus.subscribe_sync("ai.response.unified", self._handle_unified_response)
        elif hasattr(self.event_bus, 'subscribe'):
            self.event_bus.subscribe("ai.response.unified", self._handle_unified_response)
            
        logger.info(f"Connected to unified AI: router={self._unified_router is not None}, brain={self._brain_router is not None}")
        
    def _handle_unified_response(self, data):
        """Handle responses from the unified AI system."""
        if not isinstance(data, dict):
            return
        request_id = data.get("request_id")
        if request_id and request_id in self._pending_requests:
            future = self._pending_requests.pop(request_id)
            if not future.done():
                future.set_result(data.get("response", ""))
        
    async def process_message(self, message: str) -> Optional[str]:
        """Process a message by routing through the unified AI architecture.
        
        SOTA 2026: Routes to UnifiedAIRouter → BrainRouter → Ollama
        
        Args:
            message: Input message to process
            
        Returns:
            Generated response if successful, None otherwise
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self.event_bus:
                logger.error("No event bus available for AI processing")
                return None
            
            # Create request for unified AI system
            request_id = f"ai_engine_{int(time.time() * 1000)}"
            
            # Create future to wait for response
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            self._pending_requests[request_id] = future
            
            # SOTA 2026: Route through ai.request → UnifiedAIRouter → BrainRouter
            request_data = {
                "request_id": request_id,
                "prompt": message,
                "message": message,
                "domain": "general",
                "source": "ai_engine",
                "timestamp": time.time()
            }
            
            # Publish to ai.request - UnifiedAIRouter will bridge to brain.request
            self.event_bus.publish("ai.request", request_data)
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(future, timeout=60.0)
                return response
            except asyncio.TimeoutError:
                self._pending_requests.pop(request_id, None)
                logger.warning(f"AI request {request_id} timed out")
                return None
            
        except Exception as e:
            if self.event_bus is not None:
                self.event_bus.publish("ai.error", {
                    "error": str(e),
                    "source": "AISystem.process_message",
                    "message": message
                })
            logger.error(f"Error processing message: {e}")
            return None
            
    async def cleanup(self) -> bool:
        """Release resources.
        
        Returns:
            bool: Success status
        """
        try:
            # Cancel pending requests
            for request_id, future in list(self._pending_requests.items()):
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()
            
            self._initialized = False
            
            if self.event_bus is not None:
                self.event_bus.publish("ai.status", {"status": "cleanup"})
            return True
            
        except Exception as e:
            if self.event_bus is not None:
                self.event_bus.publish("ai.error", {
                    "error": str(e),
                    "source": "AISystem.cleanup"
                })
            logger.error(f"Failed to cleanup AI system: {e}")
            return False
