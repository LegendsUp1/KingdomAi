"""
API Key Distribution System - Ensures ALL tabs get API keys
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TabAPIKeyDistributor:
    """Ensures every tab that needs API keys receives them"""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.api_key_manager = None
        self.tabs_needing_keys = [
            'trading',
            'mining',
            'thoth_ai',
            'blockchain',
            'code_generator',
            'wallet'
        ]
    
    def initialize(self):
        """Distribute API keys to ALL tabs - MUST be called AFTER APIKeyManager loads keys."""
        try:
            from core.api_key_manager import APIKeyManager
            
            # CRITICAL FIX: Get the EXISTING instance that was already initialized
            api_key_manager = APIKeyManager.get_instance(event_bus=self.event_bus)
            
            # Verify keys are actually loaded
            all_keys = api_key_manager.get_all_api_keys()
            
            # If keys are empty, force reload
            if not all_keys or len(all_keys) == 0:
                logger.warning("⚠️ API Key Manager instance has no keys - forcing reload...")
                api_key_manager.load_api_keys()
                all_keys = api_key_manager.get_all_api_keys()
            
            logger.info(f"📊 API Key Manager has {len(all_keys)} total keys from existing instance")
            
            # Distribute to each tab
            for tab_name in self.tabs_needing_keys:
                self._distribute_to_tab(tab_name, all_keys)
            
            logger.info(f"✅ API keys distributed to {len(self.tabs_needing_keys)} tabs")
            
        except Exception as e:
            logger.error(f"❌ Failed to distribute API keys: {e}")
    
    def _distribute_to_tab(self, tab_name: str, all_keys: Dict[str, Any]):
        """Distribute ALL API keys to specific tab - handle ALL formats"""
        try:
            # Convert ALL keys to flat accessible format
            flat_keys = {}
            for service, key_data in all_keys.items():
                if key_data:
                    if isinstance(key_data, dict):
                        # Extract all sub-keys
                        for k, v in key_data.items():
                            if v and isinstance(v, str):
                                flat_keys[f"{service}_{k}"] = v
                                flat_keys[service] = v  # Also store primary
                    elif isinstance(key_data, str):
                        flat_keys[service] = key_data
                    elif isinstance(key_data, list) and key_data:
                        flat_keys[service] = key_data[0]
                        for idx, val in enumerate(key_data):
                            if val:
                                flat_keys[f"{service}_{idx}"] = val
            
            # Publish tab-specific API key event with FLATTENED keys
            self.event_bus.publish(f'{tab_name}.api_keys_ready', {
                'tab': tab_name,
                'keys': flat_keys,
                'raw_keys': all_keys,
                'count': len(flat_keys)
            })
            logger.info(f"📤 Sent ALL {len(flat_keys)} API keys to {tab_name} tab (from {len(all_keys)} services)")
        except Exception as e:
            logger.error(f"Error distributing keys to {tab_name}: {e}")
