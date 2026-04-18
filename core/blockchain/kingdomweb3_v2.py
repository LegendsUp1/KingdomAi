#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
KingdomWeb3 v2 compatibility module.

This module provides a bridge between the old core.blockchain.kingdomweb3_v2 import path
and the new kingdomweb3_v2 module at the root level.
"""

import logging
import sys
import os

logger = logging.getLogger(__name__)

try:
    # Import from the actual kingdomweb3_v2 module at root level
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from kingdomweb3_v2 import (
        BLOCKCHAIN_NETWORKS,
        COMPLETE_BLOCKCHAIN_NETWORKS,
        get_network_config, 
        rpc_manager,
        api_key_manager
    )
    
    # Create TxParams and BlockData as fallback types
    try:
        from kingdomweb3_v2 import TxParams
    except ImportError:
        TxParams = dict  # Fallback to dict type
        
    try:
        from kingdomweb3_v2 import BlockData
    except ImportError:
        BlockData = dict  # Fallback to dict type
        
    try:
        from kingdomweb3_v2 import TxData
    except ImportError:
        TxData = dict  # Fallback to dict type
        
    try:
        from kingdomweb3_v2 import TxReceipt
    except ImportError:
        TxReceipt = dict  # Fallback to dict type
        
    # Add HexStr and Hash32 type imports
    try:
        from kingdomweb3_v2 import HexStr
    except ImportError:
        HexStr = str  # Fallback to str type
        
    try:
        from kingdomweb3_v2 import Hash32
    except ImportError:
        Hash32 = bytes  # Fallback to bytes type
        
    try:
        from kingdomweb3_v2 import Address
    except ImportError:
        Address = str  # Fallback to str type
    
    try:
        from kingdomweb3_v2 import Nonce
    except ImportError:
        Nonce = int  # Fallback to int type
        
    # Add ChecksumAddress type - this is what was missing
    try:
        from kingdomweb3_v2 import ChecksumAddress
    except ImportError:
        ChecksumAddress = str  # Fallback to str type
        
    # Add HexBytes type - Web3.py 7.x requirement
    try:
        from kingdomweb3_v2 import HexBytes
    except ImportError:
        HexBytes = bytes  # Fallback to bytes type
        
    try:
        from kingdomweb3_v2 import BlockNumber
    except ImportError:
        BlockNumber = int  # Fallback to int type
    
    # Import Web3 components with fallbacks
    try:
        from kingdomweb3_v2 import Web3, HTTPProvider, WebsocketProvider  # type: ignore
    except ImportError:
        Web3 = None  # type: ignore
        HTTPProvider = None  # type: ignore
        WebsocketProvider = None  # type: ignore
    
    # Create additional exports for compatibility
    KingdomWeb3 = Web3 if Web3 else object  # Alias for backward compatibility
    NativeWebsocketProvider = WebsocketProvider
    NativeAsyncWebsocketProvider = WebsocketProvider  # Alias
    KingdomWeb3Error = Exception  # Basic error class
    
    # Import AsyncWeb3 and other components if available from the root module
    try:
        import kingdomweb3_v2 as root_module
        AsyncWeb3 = getattr(root_module, 'AsyncWeb3', None)
        native_geth_poa_middleware = getattr(root_module, 'geth_poa_middleware', None)
        create_web3_instance = getattr(root_module, 'create_web3_instance', None)
        create_async_web3_instance = getattr(root_module, 'create_async_web3_instance', None)
        Wei = getattr(root_module, 'Wei', None)
        HAS_WEB3 = getattr(root_module, 'HAS_WEB3', True)
        web3_available = getattr(root_module, 'web3_available', True)
        async_web3_available = getattr(root_module, 'async_web3_available', True)
        
    except Exception as e:
        logger.warning(f"Could not import some components from root kingdomweb3_v2: {e}")
        # Provide availability flags and fallbacks if module import failed
        if BLOCKCHAIN_NETWORKS is None:
            BLOCKCHAIN_NETWORKS = {}  # type: ignore
        if COMPLETE_BLOCKCHAIN_NETWORKS is None:
            COMPLETE_BLOCKCHAIN_NETWORKS = {}  # type: ignore
        HAS_WEB3 = False  # type: ignore
        HAS_ASYNC_WEB3 = False  # type: ignore
        web3_available = False
        async_web3_available = False
    
    logger.info("✅ Successfully bridged core.blockchain.kingdomweb3_v2 to root kingdomweb3_v2 module")
    
except ImportError as e:
    logger.error(f"❌ Failed to import from root kingdomweb3_v2 module: {e}")
    # Create fallback implementations
    BLOCKCHAIN_NETWORKS = {}  # type: ignore
    COMPLETE_BLOCKCHAIN_NETWORKS = {}  # type: ignore
    get_network_config = lambda x: None
    rpc_manager = None
    api_key_manager = None
    Web3 = None
    HTTPProvider = None
    WebsocketProvider = None
    AsyncWeb3 = None
    KingdomWeb3 = object
    HAS_WEB3 = False  # type: ignore
    HAS_ASYNC_WEB3 = False  # type: ignore
    web3_available = False
    async_web3_available = False
    TxParams = dict
    BlockData = dict
    TxData = dict
    TxReceipt = dict
    Nonce = int
    BlockNumber = int
    HexStr = str
    Hash32 = bytes
    Address = str
    ChecksumAddress = str
    HexBytes = bytes

# Export all components for backward compatibility
__all__ = [
    'BLOCKCHAIN_NETWORKS', 'COMPLETE_BLOCKCHAIN_NETWORKS', 'get_network_config',
    'rpc_manager', 'api_key_manager', 'Web3', 'HTTPProvider', 'WebsocketProvider',
    'AsyncWeb3', 'KingdomWeb3', 'create_web3_instance', 'create_async_web3_instance',
    'HAS_WEB3', 'HAS_ASYNC_WEB3', 'web3_available', 'async_web3_available', 'TxParams', 'BlockData', 'TxData', 'TxReceipt', 'Nonce', 'BlockNumber', 'HexStr', 'Hash32', 'Address', 'ChecksumAddress', 'HexBytes'
]
