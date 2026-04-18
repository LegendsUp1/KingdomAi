"""Configuration manager for Kingdom AI."""
from typing import Dict, Any, Optional

class Config:
    """Configuration manager for Kingdom AI."""
    
    def __init__(self, config_data: Optional[Dict[str, Any]] = None) -> None:
        """Initialize configuration with optional data."""
        self.config_data = config_data or {}
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        return self.config_data.get(key, default)
        
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self.config_data[key] = value
        
    def update(self, config_data: Dict[str, Any]) -> None:
        """Update configuration with new data."""
        self.config_data.update(config_data)
