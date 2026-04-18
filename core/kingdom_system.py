"""
KingdomSystem - Kingdom AI component
"""
import logging

class KingdomSystem:
    """
    KingdomSystem for Kingdom AI system.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the KingdomSystem."""
        self.name = "core.kingdomsystem"
        self.logger = logging.getLogger("KingdomAI.KingdomSystem")
        self._event_bus = event_bus
        self._config = config or {}
        self.initialized = False
        self.logger.info("KingdomSystem initialized")
    
    @property
    def event_bus(self):
        """Get the event bus."""
        return self._event_bus
    
    @event_bus.setter
    def event_bus(self, bus):
        """Set the event bus."""
        self._event_bus = bus
        if bus:
            self._register_event_handlers()
    
    def set_event_bus(self, bus):
        """Set the event bus and return success."""
        self.event_bus = bus
        return True
    
    def _register_event_handlers(self):
        """Register handlers with the event bus."""
        if not self._event_bus:
            return False
            
        try:
            self._event_bus.subscribe("core.request", self._handle_request)
            self.logger.debug(f"Registered event handlers for {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
            return False
    
    def _handle_request(self, event_type, data):
        """Handle component requests."""
        self.logger.debug(f"Handling request {event_type}: {data}")
        
        if self._event_bus:
            self._event_bus.publish("core.response", {
                "status": "success",
                "origin": self.name,
                "data": {"message": "Request processed by KingdomSystem"}
            })
        
        return {"status": "success"}
    
    async def initialize(self):
        """Initialize the component asynchronously."""
        self.logger.info("Initializing KingdomSystem...")
        try:
            # Perform component-specific initialization here
            self.initialized = True
            self.logger.info("KingdomSystem initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing KingdomSystem: {e}")
            return False
    
    def initialize_sync(self):
        """Initialize the component synchronously."""
        self.logger.info("Synchronously initializing KingdomSystem...")
        try:
            # Perform component-specific initialization here
            self.initialized = True
            self.logger.info("KingdomSystem synchronous initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error during synchronous initialization: {e}")
            return False