"""ThothAI Adapter for Kingdom AI

This adapter ensures compatibility between the ThothAI system and Kingdom AI.
"""

from .thoth_ai import ThothAI

class ThothAdapter(ThothAI):
    """Adapter for ThothAI integration with Kingdom AI."""
    
    def __init__(self, event_bus=None, config=None):
        super().__init__(event_bus=event_bus, config=config)
        self.name = "ThothAdapter"
        
    # Add any legacy compatibility methods here if needed
    def get_adapter_info(self):
        return {
            "name": self.name,
            "initialized": self.initialized,
            "ollama_url": self.ollama_base_url,
            "default_model": self.default_model
        }

    async def initialize(self):
        """Initialize the adapter."""
        await super().initialize()
        import logging
        logger = logging.getLogger("ThothAdapter")
        logger.info(f"{self.name} adapter initialized")
        return True
    
    async def connect_event_bus(self, event_bus):
        """Connect to the event bus."""
        self.event_bus = event_bus
        return True
    
    async def send_message(self, message):
        """Send a message to ThothAI."""
        if self.event_bus:
            await self.event_bus.publish("ai.chat.request", {"message": message})
            return True
        return False
