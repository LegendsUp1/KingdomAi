import logging
import traceback

logger = logging.getLogger('KingdomAI')

class ErrorResolutionSystem:
    """System for resolving errors in the Kingdom AI system."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)

        self.registered_handlers = {}
        self.error_history = []
        logger.info("ErrorResolutionSystem initialized")
    
    async def initialize(self):
        """Initialize the error resolution system."""
        logger.info("Initializing error resolution system...")
        return True
    
    async def handle_error(self, error, context=None, severity="ERROR"):
        """Handle an error with appropriate resolution strategy."""
        error_type = type(error).__name__
        error_msg = str(error)
        stack_trace = traceback.format_exc()
        
        # Log the error
        log_method = getattr(logger, severity.lower(), logger.error)
        log_method(f"{error_type}: {error_msg}")
        
        # Record in history
        self.error_history.append({
            "type": error_type,
            "message": error_msg,
            "context": context,
            "severity": severity,
            "stack_trace": stack_trace
        })
        
        # Handle based on registered handlers
        if error_type in self.registered_handlers:
            handler = self.registered_handlers[error_type]
            return await handler(error, context)
        
        # Default resolution strategy
        return False  # Could not resolve
    
    def register_handler(self, error_type, handler):
        """Register a handler for a specific error type."""
        self.registered_handlers[error_type] = handler
        return True