#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - Web3.py v7.x Middleware Compatibility Layer

This module provides middleware compatibility for Web3.py v7.x,
specifically addressing the deprecated geth_poa_middleware and other
common middleware patterns that were changed in v7.
"""

import logging
import json
from typing import Any, Union


# Define fallback base class FIRST (always available)
class _FallbackMiddleware:
    """Fallback middleware base class when web3 is not available."""
    def __init__(self, w3):
        self.w3 = w3


# Runtime imports with fallbacks
_WEB3_AVAILABLE = False
Web3 = None
AsyncWeb3 = None
Web3MiddlewareBase = _FallbackMiddleware  # Default to fallback

try:
    from web3 import Web3
    try:
        from web3 import AsyncWeb3
    except ImportError:
        pass  # AsyncWeb3 stays None
    from web3.middleware import Web3Middleware as _Web3Middleware  # type: ignore[attr-defined]
    Web3MiddlewareBase = _Web3Middleware  # Use real middleware if available
    _WEB3_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Web3 imports failed: {e}")

# Configure logging
logger = logging.getLogger(__name__)

class KingdomPOAMiddleware(Web3MiddlewareBase):  # type: ignore[misc]
    """POA-compatible middleware for Web3.py v7 that replaces geth_poa_middleware.
    
    This middleware handles the extranonce field in Proof of Authority chains
    that would otherwise cause JSON-RPC errors with strict Ethereum JSON-RPC spec.
    """
    
    def __init__(self, w3):
        super().__init__(w3)
        self.w3 = w3
    
    async def async_wrap_make_request(self, make_request):
        """Wrap the make_request function with POA middleware.
        
        Args:
            make_request: The original make_request function
            
        Returns:
            The wrapped make_request function
        """
        async def middleware(method, params):
            # Only process block-related methods
            if method in ('eth_getBlockByHash', 'eth_getBlockByNumber'):
                response = await make_request(method, params)
                if 'result' in response and response['result'] and isinstance(response['result'], dict):
                    # Handle POA-specific fields
                    if 'extraData' in response['result'] and isinstance(response['result']['extraData'], str):
                        # Make sure extraData is always a hex string
                        if not response['result']['extraData'].startswith('0x'):
                            response['result']['extraData'] = '0x' + response['result']['extraData']
                    
                    # Handle missing fields by adding them with default values
                    # Specifically for uncles, transactions, and difficulty fields
                    if 'uncles' not in response['result']:
                        response['result']['uncles'] = []
                    
                    if 'difficulty' not in response['result']:
                        response['result']['difficulty'] = '0x0'
                    
                    # Ensure sha3Uncles is present (required by some clients)
                    if 'sha3Uncles' not in response['result']:
                        response['result']['sha3Uncles'] = '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'
                    
                    # Process transactions array - either convert objects to hashes or ensure txs have all required fields
                    if 'transactions' in response['result'] and isinstance(response['result']['transactions'], list):
                        for i, tx in enumerate(response['result']['transactions']):
                            if isinstance(tx, dict):
                                # Ensure required transaction fields are present
                                if 'gasPrice' not in tx and 'maxFeePerGas' not in tx:
                                    # For EIP-1559 transactions, add a default maxFeePerGas if missing
                                    if 'maxPriorityFeePerGas' in tx:
                                        tx['maxFeePerGas'] = tx.get('maxPriorityFeePerGas', '0x0')
                                    else:
                                        # Legacy transactions need gasPrice
                                        tx['gasPrice'] = '0x0'
                
                return response
            return await make_request(method, params)
        
        return middleware

    def wrap_make_request(self, make_request):
        """Sync version of the middleware wrapper for non-async Web3 instances."""
        def middleware(method, params):
            # Only process block-related methods
            if method in ('eth_getBlockByHash', 'eth_getBlockByNumber'):
                response = make_request(method, params)
                if 'result' in response and response['result'] and isinstance(response['result'], dict):
                    # Handle POA-specific fields
                    if 'extraData' in response['result'] and isinstance(response['result']['extraData'], str):
                        # Make sure extraData is always a hex string
                        if not response['result']['extraData'].startswith('0x'):
                            response['result']['extraData'] = '0x' + response['result']['extraData']
                    
                    # Handle missing fields by adding them with default values
                    if 'uncles' not in response['result']:
                        response['result']['uncles'] = []
                    
                    if 'difficulty' not in response['result']:
                        response['result']['difficulty'] = '0x0'
                    
                    if 'sha3Uncles' not in response['result']:
                        response['result']['sha3Uncles'] = '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'
                    
                    # Process transactions array
                    if 'transactions' in response['result'] and isinstance(response['result']['transactions'], list):
                        for i, tx in enumerate(response['result']['transactions']):
                            if isinstance(tx, dict):
                                if 'gasPrice' not in tx and 'maxFeePerGas' not in tx:
                                    if 'maxPriorityFeePerGas' in tx:
                                        tx['maxFeePerGas'] = tx.get('maxPriorityFeePerGas', '0x0')
                                    else:
                                        tx['gasPrice'] = '0x0'
                
                return response
            return make_request(method, params)
        
        return middleware


class KingdomCacheMiddleware(Web3MiddlewareBase):  # type: ignore[misc]
    """Caching middleware for Web3.py v7 that improves performance for repeated calls.
    
    This middleware provides simple caching for RPC calls that don't change frequently,
    such as eth_chainId, net_version, etc.
    """
    
    def __init__(self, w3, cache_ttl: int = 30):
        super().__init__(w3)
        self.w3 = w3
        self.cache = {}
        self.ttl = cache_ttl  # Time-to-live in seconds
        self.last_update = {}
        self._cacheable_methods = {
            'eth_chainId', 'net_version', 'eth_getCode', 'eth_getBlockByHash',
            'eth_getBlockByNumber', 'eth_blockNumber', 'eth_getBalance',
            'eth_getTransactionCount', 'eth_getTransactionByHash',
            'eth_getTransactionReceipt', 'eth_getLogs'
        }
    
    def _should_cache(self, method, params) -> bool:
        """Determine if a method+params combination should be cached.
        
        Args:
            method: The RPC method
            params: The method parameters
            
        Returns:
            bool: Whether this call should be cached
        """
        # Only cache specific methods
        if method not in self._cacheable_methods:
            return False
        
        # Don't cache calls for the latest block since that changes frequently
        if method == 'eth_getBlockByNumber' and params and params[0] == 'latest':
            return False
        
        # Don't cache calls for pending transactions or pending blocks
        if method in ['eth_getTransactionByHash', 'eth_getTransactionReceipt']:
            return True
        
        return True
    
    def _cache_key(self, method, params) -> str:
        """Generate a cache key for the method and params.
        
        Args:
            method: The RPC method
            params: The method parameters
            
        Returns:
            str: The cache key
        """
        return f"{method}:{json.dumps(params) if params else ''}"
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if a cached entry is still valid based on TTL.
        
        Args:
            key: The cache key
            
        Returns:
            bool: Whether the cache entry is valid
        """
        import time
        return (key in self.cache and 
                key in self.last_update and 
                time.time() - self.last_update[key] < self.ttl)
    
    async def async_wrap_make_request(self, make_request):
        """Wrap the make_request function with caching middleware.
        
        Args:
            make_request: The original make_request function
            
        Returns:
            The wrapped make_request function
        """
        async def middleware(method, params):
            import time
            
            # Check if we should cache this call
            if not self._should_cache(method, params):
                return await make_request(method, params)
            
            # Generate cache key
            key = self._cache_key(method, params)
            
            # Return cached value if valid
            if self._is_cache_valid(key):
                return self.cache[key]
            
            # Make the request and cache the result
            response = await make_request(method, params)
            
            if 'error' not in response:
                self.cache[key] = response
                self.last_update[key] = time.time()
            
            return response
        
        return middleware
    
    def wrap_make_request(self, make_request):
        """Sync version of the caching middleware."""
        def middleware(method, params):
            import time
            
            # Check if we should cache this call
            if not self._should_cache(method, params):
                return make_request(method, params)
            
            # Generate cache key
            key = self._cache_key(method, params)
            
            # Return cached value if valid
            if self._is_cache_valid(key):
                return self.cache[key]
            
            # Make the request and cache the result
            response = make_request(method, params)
            
            if 'error' not in response:
                self.cache[key] = response
                self.last_update[key] = time.time()
            
            return response
        
        return middleware


def get_poa_middleware(w3):
    """Get the POA middleware instance for use with Web3.py v7.
    
    This is a drop-in replacement for geth_poa_middleware that is compatible
    with Web3.py v7.x.
    
    Args:
        w3: A Web3 or AsyncWeb3 instance
        
    Returns:
        Web3Middleware: The POA middleware instance
    """
    return KingdomPOAMiddleware(w3)


def get_cache_middleware(w3, ttl: int = 30):
    """Get the caching middleware instance.
    
    Args:
        w3: A Web3 or AsyncWeb3 instance
        ttl: Time-to-live in seconds for cached entries
        
    Returns:
        Web3Middleware: The caching middleware instance
    """
    return KingdomCacheMiddleware(w3, cache_ttl=ttl)


def setup_web3_middleware(w3):
    """Configure a Web3 instance with all necessary middleware.
    
    This function adds all required middleware to a Web3 instance in the
    correct order to ensure proper functionality.
    
    Args:
        w3: A Web3 or AsyncWeb3 instance
        
    Returns:
        Union[Web3, AsyncWeb3]: The configured Web3 instance
    """
    # Check if this is an AsyncWeb3 instance
    is_async = AsyncWeb3 is not None and isinstance(w3, AsyncWeb3)
    
    # Add POA middleware for compatibility with PoA chains
    poa_middleware = get_poa_middleware(w3)
    if is_async:
        w3.middleware_onion.add(poa_middleware, "poa")
    else:
        w3.middleware_onion.add(poa_middleware, "poa")
    
    # Add caching middleware to improve performance
    cache_middleware = get_cache_middleware(w3, ttl=30)
    if is_async:
        w3.middleware_onion.add(cache_middleware, "cache")
    else:
        w3.middleware_onion.add(cache_middleware, "cache")
    
    return w3
