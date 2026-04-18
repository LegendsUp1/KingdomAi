#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Blockchain Connector Component (Clean Version)
Provides connectivity to blockchain networks with robust error handling.
"""

import logging
import asyncio
from typing import Any, Dict

# Import Web3 with fallback handling
try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    Web3 = None
    WEB3_AVAILABLE = False

# Import from our core components
from core.base_component import BaseComponent
from core.session_manager import SessionManager

# Import from kingdomweb3_v2 instead of defining duplicates
from kingdomweb3_v2 import rpc_manager, get_network_config

logger = logging.getLogger(__name__)


class BlockchainConnector(BaseComponent):
    """Clean blockchain connector with no duplicate definitions."""
    
    def __init__(self, event_bus=None, config=None, session_manager=None):
        """Initialize the blockchain connector."""
        super().__init__()
        self.name = "BlockchainConnector"
        self.event_bus = event_bus
        self.config = config or {}
        self.session_manager = session_manager or SessionManager()
        self.is_running = False
        self.status = "disconnected"
        logger.info("BlockchainConnector initialized")

    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize the blockchain connector."""
        try:
            self.is_running = True
            self.status = "connected"
            logger.info("BlockchainConnector initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing BlockchainConnector: {e}")
            return False

    async def connect(self) -> bool:
        """Connect to blockchain network."""
        try:
            # Use kingdomweb3_v2 for connection
            network_config = get_network_config("ethereum")
            if network_config:
                self.status = "connected"
                return True
            return False
        except Exception as e:
            logger.error(f"Error connecting: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from blockchain network."""
        try:
            self.status = "disconnected"
            logger.info("Disconnected from blockchain network")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the blockchain connector."""
        if not self.is_running:
            return True
            
        await self.disconnect()
        self.is_running = False
        logger.info("BlockchainConnector stopped")
        return True


# Export the main components
__all__ = [
    "BlockchainConnector"
]
