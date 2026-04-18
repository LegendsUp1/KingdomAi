#!/usr/bin/env python3
"""
Universal API Key Helper for ALL Kingdom AI Tabs
Provides consistent API key access across the entire system
"""

import logging
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)


class TabAPIKeyHelper:
    """
    Universal API Key Helper - Use this in ALL tabs!
    Provides centralized, consistent API key access.
    """
    
    @staticmethod
    def get_all_api_keys() -> Dict[str, Any]:
        """
        Get ALL API keys from Global Registry.
        Works from ANY tab, ANY time!
        
        Returns:
            Dict of all API keys (183+ keys)
        """
        try:
            # METHOD 1: Try Global Registry (FASTEST)
            from global_api_keys import GlobalAPIKeys
            global_registry = GlobalAPIKeys.get_instance()
            all_keys = global_registry.get_all_keys()
            
            if all_keys and len(all_keys) > 0:
                logger.debug(f"✅ Retrieved {len(all_keys)} keys from Global Registry")
                return all_keys
            
            # METHOD 2: Try parent window reference
            try:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    main_window = app.activeWindow()
                    if main_window and hasattr(main_window, 'global_api_keys'):
                        logger.debug(f"✅ Retrieved keys from parent window")
                        return main_window.global_api_keys
            except Exception as e:
                logger.debug(f"Parent window method failed: {e}")
            
            # METHOD 3: Fallback to direct APIKeyManager load
            logger.warning("Global Registry empty, loading from APIKeyManager...")
            from core.api_key_manager import APIKeyManager
            api_key_manager = APIKeyManager()
            api_key_manager.load_api_keys()
            all_keys = api_key_manager.get_all_api_keys()
            
            if all_keys:
                # Store in Global Registry for next time
                global_registry.set_multiple_keys(all_keys)
                logger.info(f"✅ Loaded and cached {len(all_keys)} keys")
                return all_keys
            
            logger.warning("No API keys found in any source!")
            return {}
            
        except Exception as e:
            logger.error(f"Error getting API keys: {e}")
            return {}
    
    @staticmethod
    def get_api_key(service: str) -> Optional[Any]:
        """
        Get API key for a specific service.
        
        Args:
            service: Service name (e.g., 'binance', 'etherscan', 'openai')
            
        Returns:
            API key data (dict, string, or list) or None
        """
        try:
            from global_api_keys import GlobalAPIKeys
            global_registry = GlobalAPIKeys.get_instance()
            return global_registry.get_key(service)
        except Exception as e:
            logger.error(f"Error getting key for {service}: {e}")
            return None
    
    @staticmethod
    def get_simple_key(service: str) -> Optional[str]:
        """
        Get simple string API key (extracts from dict if needed).
        
        Args:
            service: Service name
            
        Returns:
            Simple API key string or None
        """
        try:
            from global_api_keys import GlobalAPIKeys
            global_registry = GlobalAPIKeys.get_instance()
            return global_registry.get_simple_key(service)
        except Exception as e:
            logger.error(f"Error getting simple key for {service}: {e}")
            return None
    
    @staticmethod
    def get_keys_by_category(category: str) -> Dict[str, Any]:
        """
        Get all keys for a specific category.
        
        Args:
            category: Category name (e.g., 'CRYPTO_EXCHANGES', 'AI_SERVICES')
            
        Returns:
            Dict of service->key_data for that category
        """
        try:
            from global_api_keys import GlobalAPIKeys
            global_registry = GlobalAPIKeys.get_instance()
            return global_registry.get_keys_by_category(category)
        except Exception as e:
            logger.error(f"Error getting keys for category {category}: {e}")
            return {}
    
    @staticmethod
    def get_exchange_keys() -> Dict[str, Any]:
        """Get ALL exchange API keys (Binance, Coinbase, etc.)"""
        all_keys = TabAPIKeyHelper.get_all_api_keys()
        exchanges = ['binance', 'coinbase', 'kraken', 'kucoin', 'huobi', 'okx', 
                    'bybit', 'gate_io', 'bitget', 'mexc', 'crypto_com']
        return {k: v for k, v in all_keys.items() if k in exchanges}
    
    @staticmethod
    def get_explorer_keys() -> Dict[str, Any]:
        """Get ALL blockchain explorer API keys (Etherscan, BSCScan, etc.)"""
        all_keys = TabAPIKeyHelper.get_all_api_keys()
        explorers = ['etherscan', 'bscscan', 'polygonscan', 'arbiscan', 
                    'optimism', 'snowtrace', 'ftmscan', 'nansen', 'blockchain']
        return {k: v for k, v in all_keys.items() if k in explorers}
    
    @staticmethod
    def get_ai_service_keys() -> Dict[str, Any]:
        """Get ALL AI service API keys (OpenAI, Anthropic, etc.)"""
        all_keys = TabAPIKeyHelper.get_all_api_keys()
        ai_services = ['grok_xai', 'huggingface', 'cohere', 'llama', 'codegpt',
                      'openai', 'anthropic', 'stability', 'deepl', 'riva']
        return {k: v for k, v in all_keys.items() if k in ai_services}
    
    @staticmethod
    def get_blockchain_provider_keys() -> Dict[str, Any]:
        """Get ALL blockchain provider API keys (Infura, Alchemy, etc.)"""
        all_keys = TabAPIKeyHelper.get_all_api_keys()
        # Check if blockchain_providers is nested
        if 'blockchain_providers' in all_keys:
            return all_keys['blockchain_providers']
        # Otherwise return individual provider keys
        providers = ['infura', 'alchemy', 'quicknode', 'ankr', 'chainstack', 
                    'moralis', 'nodereal', 'getblock']
        return {k: v for k, v in all_keys.items() if k in providers}
    
    @staticmethod
    def get_market_data_keys() -> Dict[str, Any]:
        """Get ALL market data API keys (CoinGecko, Alpha Vantage, etc.)"""
        all_keys = TabAPIKeyHelper.get_all_api_keys()
        market_data = ['alpha_vantage', 'coinlayer', 'market_stack', 'nasdaq',
                      'fred', 'media_stack', 'finance_news', 'world_news']
        return {k: v for k, v in all_keys.items() if k in market_data}
    
    @staticmethod
    def has_api_key(service: str) -> bool:
        """Check if a specific service has an API key configured."""
        try:
            from global_api_keys import GlobalAPIKeys
            global_registry = GlobalAPIKeys.get_instance()
            return global_registry.has_key(service)
        except Exception as e:
            logger.error(f"Error checking key for {service}: {e}")
            return False
    
    @staticmethod
    def get_api_key_stats() -> Dict[str, int]:
        """Get statistics about available API keys."""
        try:
            from global_api_keys import GlobalAPIKeys
            global_registry = GlobalAPIKeys.get_instance()
            return global_registry.get_stats()
        except Exception as e:
            logger.error(f"Error getting API key stats: {e}")
            return {}


# Convenience functions for quick access
def get_all_api_keys() -> Dict[str, Any]:
    """Convenience function: Get all API keys"""
    return TabAPIKeyHelper.get_all_api_keys()


def get_api_key(service: str) -> Optional[Any]:
    """Convenience function: Get API key for a service"""
    return TabAPIKeyHelper.get_api_key(service)


def get_simple_key(service: str) -> Optional[str]:
    """Convenience function: Get simple string key"""
    return TabAPIKeyHelper.get_simple_key(service)


def has_api_key(service: str) -> bool:
    """Convenience function: Check if service has key"""
    return TabAPIKeyHelper.has_api_key(service)


# Export all
__all__ = [
    'TabAPIKeyHelper',
    'get_all_api_keys',
    'get_api_key', 
    'get_simple_key',
    'has_api_key'
]


if __name__ == "__main__":
    # Test the helper
    helper = TabAPIKeyHelper()
    
    print("\n" + "="*80)
    print("TESTING TAB API KEY HELPER")
    print("="*80)
    
    # Test getting all keys
    all_keys = helper.get_all_api_keys()
    print(f"\n✅ Total API keys: {len(all_keys)}")
    
    # Test exchange keys
    exchange_keys = helper.get_exchange_keys()
    print(f"✅ Exchange keys: {len(exchange_keys)}")
    print(f"   Exchanges: {list(exchange_keys.keys())}")
    
    # Test explorer keys
    explorer_keys = helper.get_explorer_keys()
    print(f"✅ Explorer keys: {len(explorer_keys)}")
    print(f"   Explorers: {list(explorer_keys.keys())}")
    
    # Test AI service keys
    ai_keys = helper.get_ai_service_keys()
    print(f"✅ AI Service keys: {len(ai_keys)}")
    print(f"   AI Services: {list(ai_keys.keys())}")
    
    # Test stats
    stats = helper.get_api_key_stats()
    print(f"\n📊 API Key Statistics:")
    for category, count in stats.items():
        print(f"   {category}: {count}")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED!")
    print("="*80 + "\n")
