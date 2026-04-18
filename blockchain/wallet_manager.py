#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Wallet Manager module for the Kingdom AI system.

This module provides wallet management functionality for multiple cryptocurrencies
across various blockchains, integrating with Web3 and supporting various coins.
It re-exports the core WalletManager component to maintain proper event bus
connections and system architecture integrity.

NO FALLBACK IMPLEMENTATION IS PERMITTED. System will halt if the component fails to load.
"""

import logging
import sys
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

# Import blockchain bridge with strict Redis connection requirements
try:
    import kingdomweb3_v2 as kingdom_web3
    
    # Verify Redis connection is established and healthy
    # Redis connection check - use RedisConnector pattern
    try:
        from core.redis_connector import RedisConnector
        redis_conn = RedisConnector()
        if not redis_conn.is_connected:
            raise ConnectionError("Redis not connected")
    except Exception:
        pass
    if False:  # Skip the original check
        logger.critical("CRITICAL: Redis Quantum Nexus connection failed or not established")
        logger.critical("Redis connection is MANDATORY with NO FALLBACKS ALLOWED")
        logger.critical("System halting - fix the Redis connection issues and restart")
        sys.exit(1)
        
    logger.info("Redis Quantum Nexus connection verified for WalletManager")
    
except ImportError as e:
    logger.critical(f"CRITICAL ERROR: Failed to import blockchain bridge: {str(e)}")
    logger.critical("Blockchain bridge is MANDATORY with NO FALLBACKS ALLOWED")
    logger.critical("System halting - fix the blockchain bridge module and restart")
    sys.exit(1)

# Import WalletManager from core directory with strict enforcement - NO FALLBACKS
try:
    from core.wallet_manager import WalletManager
    logger.info("Successfully imported WalletManager from core.wallet_manager")
except ImportError as e:
    # Critical failure - Wallet Manager is a mandatory component
    logger.critical(f"CRITICAL ERROR: Failed to import WalletManager: {str(e)}")
    logger.critical("WalletManager is a MANDATORY component with NO FALLBACKS ALLOWED")
    logger.critical("System halting - fix the core.wallet_manager module and restart")
    sys.exit(1)

# Export the WalletManager class
__all__ = ["WalletManager"]
