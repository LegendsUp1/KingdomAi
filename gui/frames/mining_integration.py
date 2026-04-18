#!/usr/bin/env python3
"""
Mining Integration for Kingdom AI.
Integrates blockchain data sources, API keys, and event bus robustness for the Mining tab.
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
from gui.frames.blockchain_data_sources import BlockchainDataSourcesMixin

logger = logging.getLogger(__name__)

class MiningIntegration(EventBusRetryMixin, APIKeyIntegrationMixin, BlockchainDataSourcesMixin):
    """
    Integration class for Mining Frame providing blockchain data access, 
    API key integration, and event bus robustness.
    """
    
    def __init__(self):
        """Initialize the mining integration."""
        EventBusRetryMixin.__init__(self)
        APIKeyIntegrationMixin.__init__(self)
        BlockchainDataSourcesMixin.__init__(self)
        
        # Mining state tracking
        self.blockchain_initialized = False
        self.blockchain_retry_count = 0
        self.max_blockchain_retries = 5
        
        # Mining intelligence
        self.mining_intelligence_initialized = False
        self.mining_pools = {}
        self.mining_stats = {}
        
    async def initialize_mining_integration(self, parent_frame):
        """
        Initialize mining integration with the parent frame.
        
        Args:
            parent_frame: The parent mining frame to integrate with
        
        Returns:
            bool: Success status
        """
        try:
            logger.info("Initializing mining integration")
            self.parent = parent_frame
            
            # 1. Load API keys immediately
            mining_services = [
                "ethereum_node", "mining_pools", "ethermine", "f2pool", 
                "poolin", "ezil", "nicehash", "mining_intelligence"
            ]
            api_keys = await self.load_api_keys_immediate(mining_services)
            
            # 2. Initialize blockchain data sources
            try:
                success = await self.initialize_blockchain_data_sources()
                self.blockchain_initialized = success
                if not success:
                    # Schedule retry
                    self._retry_blockchain_initialization()
            except Exception as e:
                logger.error(f"Error initializing blockchain data sources: {e}")
                logger.error(traceback.format_exc())
                # Schedule retry
                self._retry_blockchain_initialization()
            
            # 3. Set up robust event bus subscriptions
            if hasattr(self.parent, 'event_bus') and self.parent.event_bus:
                self._setup_mining_event_subscriptions()
            
            # 4. Initialize mining intelligence if available
            await self._initialize_mining_intelligence()
            
            # 5. Update UI with initial data
            if hasattr(self.parent, 'after') and self.parent.after:
                self.parent.after(0, self._update_mining_ui)
            
            logger.info("Mining integration initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing mining integration: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _retry_blockchain_initialization(self):
        """
        Retry blockchain data source initialization with exponential backoff.
        """
        if self.blockchain_retry_count >= self.max_blockchain_retries:
            logger.error(f"Failed to initialize blockchain data sources after {self.max_blockchain_retries} attempts")
            return
            
        delay = 2 ** self.blockchain_retry_count
        logger.info(f"Retrying blockchain initialization in {delay} seconds (attempt {self.blockchain_retry_count+1}/{self.max_blockchain_retries})")
        
        async def delayed_retry():
            await asyncio.sleep(delay)
            try:
                success = await self.initialize_blockchain_data_sources()
                self.blockchain_initialized = success
                if success:
                    logger.info("Blockchain data sources initialization successful on retry")
                    # Update UI
                    if hasattr(self.parent, 'after') and self.parent.after:
                        self.parent.after(0, self._update_mining_ui)
                else:
                    self.blockchain_retry_count += 1
                    self._retry_blockchain_initialization()
            except Exception as e:
                logger.error(f"Error in blockchain initialization retry: {e}")
                self.blockchain_retry_count += 1
                self._retry_blockchain_initialization()
        
        # Schedule the retry
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(delayed_retry())
            else:
                loop.run_until_complete(delayed_retry())
        except Exception as e:
            logger.error(f"Error scheduling blockchain initialization retry: {e}")
    
    def _setup_mining_event_subscriptions(self):
        """
        Set up robust event subscriptions for mining events.
        """
        # Core mining events
        mining_events = [
            "mining.status", "mining.hashrate", "mining.shares", "mining.rewards",
            "mining.devices", "mining.temperature", "mining.efficiency", "mining.log"
        ]
        
        # Blockchain events
        blockchain_events = [
            "blockchain.status", "blockchain.block", "blockchain.difficulty",
            "blockchain.gas", "blockchain.network", "blockchain.error"
        ]
        
        # API events
        api_events = [
            "api.key.update", "api.connection.status", "api.error"
        ]
        
        # Subscribe to all events with retry logic
        for event in mining_events:
            handler_name = f"handle_{event.replace('.', '_')}"
            if hasattr(self.parent, handler_name) and callable(getattr(self.parent, handler_name)):
                self._subscribe_with_retry(event, getattr(self.parent, handler_name))
        
        for event in blockchain_events:
            handler_name = f"handle_{event.replace('.', '_')}"
            if hasattr(self.parent, handler_name) and callable(getattr(self.parent, handler_name)):
                self._subscribe_with_retry(event, getattr(self.parent, handler_name))
        
        for event in api_events:
            handler_name = f"handle_{event.replace('.', '_')}"
            if hasattr(self.parent, handler_name) and callable(getattr(self.parent, handler_name)):
                self._subscribe_with_retry(event, getattr(self.parent, handler_name))
                
        logger.info("Mining event subscriptions set up with retry logic")
    
    async def _initialize_mining_intelligence(self):
        """
        Initialize mining intelligence components for profitability and optimization.
        
        Returns:
            bool: Success status
        """
        try:
            logger.info("Initializing mining intelligence")
            
            # Check if mining_intelligence is available in sys.modules
            if 'core.mining_intelligence' in sys.modules:
                try:
                    # Get reference to MiningIntelligence class
                    from core.mining_intelligence import MiningIntelligence
                    
                    # Try to get mining intelligence instance from component manager
                    if hasattr(self.parent, 'component_manager') and self.parent.component_manager:
                        mining_intelligence = self.parent.component_manager.get_component('MiningIntelligence')
                        if mining_intelligence:
                            logger.info("Found existing MiningIntelligence instance from component manager")
                            self.mining_intelligence = mining_intelligence
                            self.mining_intelligence_initialized = True
                            return True
                    
                    # If not found, try to create a new instance
                    # This is not ideal but provides a fallback if component manager is not available
                    logger.warning("MiningIntelligence not found in component manager, creating new instance")
                    self.mining_intelligence = MiningIntelligence(event_bus=self.parent.event_bus)
                    await self.mining_intelligence.initialize()
                    self.mining_intelligence_initialized = True
                    
                    return True
                    
                except Exception as e:
                    logger.error(f"Error initializing mining intelligence: {e}")
                    logger.error(traceback.format_exc())
            else:
                logger.warning("Mining intelligence module not available")
            
            return False
            
        except Exception as e:
            logger.error(f"Error initializing mining intelligence: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _update_mining_ui(self):
        """
        Update the mining UI with latest data from blockchain and mining intelligence.
        """
        try:
            # Update data source status indicators
            if hasattr(self.parent, 'update_data_source_status') and callable(self.parent.update_data_source_status):
                for source_id, status in self.data_source_status.items():
                    self.parent.update_data_source_status(source_id, status)
            
            # Update farming opportunities if available
            if hasattr(self.parent, 'update_farming_opportunities') and callable(self.parent.update_farming_opportunities):
                self.parent.update_farming_opportunities(self.farming_opportunities)
            
            # Update blockchain connection status
            if hasattr(self.parent, 'update_blockchain_status') and callable(self.parent.update_blockchain_status):
                status = {
                    "connected": self.blockchain_initialized,
                    "sources": len(self.blockchain_data_sources),
                    "connected_sources": sum(1 for s in self.blockchain_data_sources.values() if s.get("connected", False)),
                    "last_update": time.time()
                }
                self.parent.update_blockchain_status(status)
            
        except Exception as e:
            logger.error(f"Error updating mining UI: {e}")
    
    async def detect_farming_opportunities(self):
        """
        Scan for and detect farming opportunities across blockchains.
        
        Returns:
            List[Dict]: List of detected farming opportunities
        """
        try:
            logger.info("Scanning for farming opportunities")
            
            # Use previously implemented scan method from BlockchainDataSourcesMixin
            opportunities = await self.scan_farming_opportunities()
            
            # If mining intelligence is available, use it for additional analysis
            if self.mining_intelligence_initialized and hasattr(self, 'mining_intelligence'):
                try:
                    # Get additional opportunities from mining intelligence
                    intelligence_opps = await self.mining_intelligence.detect_farming_opportunities()
                    
                    # Merge opportunities, avoiding duplicates
                    existing_ids = [opp.get("id") for opp in opportunities]
                    for opp in intelligence_opps:
                        if opp.get("id") not in existing_ids:
                            opportunities.append(opp)
                            
                except Exception as e:
                    logger.warning(f"Error getting opportunities from mining intelligence: {e}")
            
            # Publish opportunities
            if hasattr(self, 'safe_publish'):
                self.safe_publish("mining.farming.opportunities", {
                    "opportunities": opportunities,
                    "count": len(opportunities),
                    "timestamp": time.time()
                })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error detecting farming opportunities: {e}")
            return []
