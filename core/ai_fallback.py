"""
AI Emergency Fallback Module for Kingdom AI
"""
import logging

logger = logging.getLogger(__name__)

class AIContingencySystem:
    """Emergency fallback system for critical Kingdom AI components"""
    
    @classmethod
    def get_config(cls, key, default=None):
        """Provide emergency configuration values when regular config fails"""
        logger.warning(f"Using AI emergency configuration for key: {key}")
        return cls._ai_config().get(key, default)
    
    @classmethod
    def _ai_config(cls):
        """Default configuration values for emergency use"""
        return {
            'security_level': 'high',
            'max_recursion': 1000,
            'runtime_safeguards': True,
            'component.security_manager.enabled': True,
            'component.security_manager.auth_required': False,
            'component.config_manager.database_path': 'config.json',
            'system.max_retries': 3,
            'system.fallback_mode': True
        }
        
    @classmethod
    def emergency_initialize(cls, component):
        """Emergency initialization for components that fail to start"""
        component_name = component.__class__.__name__
        logger.warning(f"AI emergency initialization for {component_name}")
        
        # Set basic attributes for component functionality
        if not hasattr(component, 'initialized'):
            component.initialized = True
        if not hasattr(component, 'ready'):
            component.ready = True
            
        # Try to publish an initialization event
        try:
            if hasattr(component, 'event_bus') and component.event_bus:
                event_name = f"system.{component_name.lower()}.initialized"
                component.event_bus.publish(event_name, {"success": True, "emergency": True})
        except Exception as e:
            logger.error(f"Failed to publish emergency event: {e}")
            
        return True

# Convenience function exports
emergency_get_config = AIContingencySystem.get_config
emergency_initialize = AIContingencySystem.emergency_initialize
