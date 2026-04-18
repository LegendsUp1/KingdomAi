import os
import json
import logging
from typing import Any

logger = logging.getLogger('KingdomAI')

class ConfigManager:
    """Configuration manager for KingdomAI system."""
    
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
            
        self.config = {}
        self.config_file = os.path.join('config', 'system_config.json')
        self.initialized = False
        logger.info("ConfigManager created")
    
    async def initialize_async(self):
        """Initialize the configuration manager asynchronously."""
        logger.info("Initializing configuration manager...")
        
        try:
            # Create config directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # Load configuration if file exists
            if os.path.exists(self.config_file):
                await self.load_config()
                logger.info(f"Loaded configuration from {self.config_file}")
            else:
                # Create default configuration
                self.config = {
                    "system": {
                        "name": "KingdomAI",
                        "version": "1.0.0",
                        "debug": True
                    },
                    "components": {
                        "gui_manager": {
                            "enabled": True
                        },
                        "voice_system": {
                            "enabled": True,
                            "voice": "en-US-Guy24kRUS",
                            "speed": 1.0
                        },
                        "thoth_ai": {
                            "enabled": True,
                            "model": "mistral-nemo:latest",
                            "ollama_url": "http://localhost:11434"
                        }
                    }
                }
                
                # Save default configuration
                await self.save_config()
                logger.info("Created default configuration")
            
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ConfigManager: {str(e)}")
            return False
    
    def initialize_sync(self):
        """Initialize the configuration manager synchronously."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded configuration from {self.config_file}")
            else:
                logger.warning(f"Configuration file {self.config_file} not found. Using defaults.")
                self._set_default_config()
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2)
                logger.info(f"Saved default configuration to {self.config_file}")
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize configuration manager: {str(e)}")
            return False
            
    async def initialize(self):
        """Initialize the configuration manager asynchronously."""
        # For now, just call the sync version
        return self.initialize_sync()
    
    async def load_config(self):
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded configuration from {self.config_file}")
                return True
            else:
                logger.warning(f"Configuration file {self.config_file} not found")
                return False
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            return False
    
    def _set_default_config(self):
        """Set default configuration values."""
        self.config = {
            "system": {
                "debug": False,
                "log_level": "INFO",
                "theme": "dark"
            },
            "thoth": {
                "model": "mistral-nemo:latest",
                "ollama_url": "http://localhost:11434",
                "max_tokens": 2048,
                "temperature": 0.7
            },
            "voice": {
                "voice_enabled": True,
                "voice": "en-US-Guy24kRUS",
                "speech_speed": 1.0
            },
            "mining": {
                "solo_mining": False,
                "mining_pool": "http://pool.example.com:8008",
                "worker_threads": 2
            },
            "wallet": {
                "default_network": "ethereum",
                "auto_backup": True
            },
            "market": {
                "default_exchange": "binance",
                "update_interval": 30
            }
        }
        logger.info("Default configuration set")
    
    def get(self, key, default=None):
        """Get a configuration value."""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def get_config(self, path: str, default: Any = None) -> Any:
        """
        Alias for get() method to maintain compatibility.
        
        Args:
            path: Dot-separated path to the configuration value
            default: Default value to return if path doesn't exist
            
        Returns:
            Configuration value or default
        """
        return self.get(path, default)
        
    async def get_config_async(self, path: str, default: Any = None) -> Any:
        """
        Asynchronous version of get_config method.
        
        Args:
            path: Dot-separated path to the configuration value or a file path
            default: Default value to return if path doesn't exist
            
        Returns:
            Configuration value or default
        """
        # If the path looks like a file path, try to load it
        if path.endswith('.json') and os.path.sep in path:
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    return config_data
                else:
                    if default is None:
                        # Return empty dict as default for JSON files
                        return {}
                    return default
            except Exception as e:
                logger.error(f"Error loading config file {path}: {e}")
                return default
        # Otherwise use the regular get method
        return self.get(path, default)
    
    def set(self, key, value):
        """Set a configuration value."""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the last level
        for i, k in enumerate(keys[:-1]):
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        return True
    
    async def save_config(self):
        """Save the configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Saved configuration to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            return False
    
    def get_component_config(self, component_name):
        """
        Get the configuration for a specific component.
        
        Args:
            component_name: The name of the component
            
        Returns:
            Dictionary with component configuration or empty dict if not found
        """
        try:
            # First try to get from components section
            if 'components' in self.config and component_name in self.config['components']:
                return self.config['components'][component_name]
                
            # If not found, try direct component name (for backward compatibility)
            elif component_name.lower() in self.config:
                return self.config[component_name.lower()]
                
            # Then try with first letter lowercase (to handle camelCase/PascalCase differences)
            elif component_name[0].lower() + component_name[1:] in self.config:
                return self.config[component_name[0].lower() + component_name[1:]]
                
            # Finally, for components like ThothAI, try looking for thoth
            elif component_name.lower().replace('ai', '') in self.config:
                return self.config[component_name.lower().replace('ai', '')]
            
            # Not found anywhere
            logger.debug(f"No configuration found for component: {component_name}")
            return {}
        except Exception as e:
            logger.error(f"Error getting component config for {component_name}: {e}")
            return {}