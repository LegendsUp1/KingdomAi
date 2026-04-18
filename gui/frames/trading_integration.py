#!/usr/bin/env python3
"""
Trading Integration for Kingdom AI.
Integrates Web3, API keys, and event bus robustness for the Trading tab.
"""

import os
import sys
import logging
import asyncio
import traceback
import time
from typing import Dict, List, Any, Optional, Tuple, Union

# Ensure parent directory is in path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from gui.frames.event_bus_retry import EventBusRetryMixin
from gui.frames.api_key_integration import APIKeyIntegrationMixin

logger = logging.getLogger(__name__)

class TradingIntegration(EventBusRetryMixin, APIKeyIntegrationMixin):
    """
    Integration class for Trading Frame providing Web3 connection, 
    API key access, and event bus robustness.
    """
    
    def __init__(self):
        """Initialize the trading integration."""
        EventBusRetryMixin.__init__(self)
        APIKeyIntegrationMixin.__init__(self)
        
        # Web3 connection tracking
        self.web3_initialized = False
        self.web3_retry_count = 0
        self.max_web3_retries = 5
        self.web3_connections = {}
        self.web3_status = {}
        
    async def initialize_trading_integration(self, parent_frame):
        """
        Initialize trading integration with the parent frame.
        
        Args:
            parent_frame: The parent trading frame to integrate with
        
        Returns:
            bool: Success status
        """
        try:
            logger.info("Initializing trading integration")
            self.parent = parent_frame
            
            # 1. Load API keys immediately
            trading_services = [
                "binance", "coinbase", "kraken", "kucoin", 
                "ethereum_provider", "bsc_provider", "polygon_provider",
                "infura", "alchemy", "etherscan"
            ]
            api_keys = await self.load_api_keys_immediate(trading_services)
            
            # 2. Initialize Web3 connections with API keys
            if hasattr(self.parent, '_initialize_web3') and callable(self.parent._initialize_web3):
                try:
                    await self.parent._initialize_web3()
                    self.web3_initialized = True
                except Exception as e:
                    logger.error(f"Error initializing Web3: {e}")
                    logger.error(traceback.format_exc())
                    # Retry Web3 initialization with backoff
                    self._retry_web3_initialization()
            
            # 3. Set up robust event bus subscriptions
            if hasattr(self.parent, 'event_bus') and self.parent.event_bus:
                self._setup_trading_event_subscriptions()
            
            logger.info("Trading integration initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing trading integration: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _retry_web3_initialization(self):
        """
        Retry Web3 initialization with exponential backoff.
        """
        if self.web3_retry_count >= self.max_web3_retries:
            logger.error(f"Failed to initialize Web3 after {self.max_web3_retries} attempts")
            return
            
        delay = 2 ** self.web3_retry_count
        logger.info(f"Retrying Web3 initialization in {delay} seconds (attempt {self.web3_retry_count+1}/{self.max_web3_retries})")
        
        async def delayed_retry():
            await asyncio.sleep(delay)
            try:
                await self.parent._initialize_web3()
                self.web3_initialized = True
                logger.info("Web3 initialization successful on retry")
            except Exception as e:
                logger.error(f"Error in Web3 initialization retry: {e}")
                self.web3_retry_count += 1
                self._retry_web3_initialization()
        
        # Schedule the retry
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(delayed_retry())
            else:
                loop.run_until_complete(delayed_retry())
        except Exception as e:
            logger.error(f"Error scheduling Web3 initialization retry: {e}")
    
    def _setup_trading_event_subscriptions(self):
        """
        Set up robust event subscriptions for trading events.
        """
        # Core trading events
        trading_events = [
            "market.price", "market.depth", "market.ticker", "market.candlestick",
            "trading.order", "trading.position", "trading.error",
            "market.data.update", "market.list.update", 
        ]
        
        # Web3 events
        web3_events = [
            "blockchain.status", "blockchain.transaction", "blockchain.balance",
            "blockchain.gas", "blockchain.contract", "blockchain.error"
        ]
        
        # API events
        api_events = [
            "api.key.update", "api.connection.status", "api.error"
        ]
        
        # Subscribe to all events with retry logic
        for event in trading_events:
            handler_name = f"_handle_{event.replace('.', '_')}"
            if hasattr(self.parent, handler_name) and callable(getattr(self.parent, handler_name)):
                self._subscribe_with_retry(event, getattr(self.parent, handler_name))
        
        for event in web3_events:
            handler_name = f"_handle_{event.replace('.', '_')}"
            if hasattr(self.parent, handler_name) and callable(getattr(self.parent, handler_name)):
                self._subscribe_with_retry(event, getattr(self.parent, handler_name))
        
        for event in api_events:
            handler_name = f"_handle_{event.replace('.', '_')}"
            if hasattr(self.parent, handler_name) and callable(getattr(self.parent, handler_name)):
                self._subscribe_with_retry(event, getattr(self.parent, handler_name))
                
        logger.info("Trading event subscriptions set up with retry logic")
