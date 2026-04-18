import logging
import base64
from core.config_manager import ConfigManager

logger = logging.getLogger('KingdomAI')

class SecurityManager:
    """Security manager for KingdomAI system."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)

        # Singleton pattern - initialize only once
        if hasattr(self, 'initialized') and self.initialized:
            return
            
        self.config_manager = ConfigManager.get_instance()
        self.initialized = False
        logger.info("SecurityManager created")
    
    async def initialize(self):
        """Initialize the security manager."""
        logger.info("Initializing security manager...")
        
        try:
            # Set default security configuration if not exists
            if not self.config_manager.get('security'):
                self.config_manager.set('security', {
                    'encryption_enabled': True,
                    'authentication_required': False
                })
                await self.config_manager.save_config()
            
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SecurityManager: {str(e)}")
            return False
    
    def encrypt(self, data):
        """Encrypt data (simplified implementation)."""
        if not self.config_manager.get('security.encryption_enabled', True):
            return data
        
        # Simple encryption for demo (not secure for production)
        return base64.b64encode(data.encode()).decode()
    
    def decrypt(self, data):
        """Decrypt data (simplified implementation)."""
        if not self.config_manager.get('security.encryption_enabled', True):
            return data
        
        try:
            # Simple decryption for demo (not secure for production)
            return base64.b64decode(data.encode()).decode()
        except:
            return data
            
    async def authenticate(self, credentials):
        """Authenticate user credentials.
        
        Args:
            credentials: Dict containing username and password
            
        Returns:
            Dict with authentication status and user details if successful
        """
        self.logger.info(f"Authenticating user: {credentials.get('username', 'unknown')}")
        try:
            # For testing purposes, accept a hardcoded credential
            if (credentials.get('username') == 'kingdom_admin' and 
                credentials.get('password') == 'kingdom_admin'):
                return {
                    "status": "success",
                    "message": "Authentication successful",
                    "user_id": "admin",
                    "permissions": ["admin", "user", "developer"]
                }
            else:
                return {
                    "status": "error",
                    "message": "Invalid credentials"
                }
        except Exception as e:
            logger.error(f"Authentication error for user: {credentials.get('username', 'unknown')}: {str(e)}")
            return {
                "status": "error",
                "message": "Authentication system error"
            }