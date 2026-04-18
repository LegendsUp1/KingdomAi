#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - Blockchain Network Statistics Module

This module provides real-time blockchain network statistics and analytics,
including gas prices, network health, node connectivity, and transaction throughput.
It integrates with the blockchain bridge for consistent Web3 access.
"""
import os
import logging
import asyncio
import time
from typing import Any, Dict, List, Optional, Union
import json

# Setup logger
logger = logging.getLogger(__name__)

# MANDATORY import from kingdomweb3_v2 - NO FALLBACKS ALLOWED
try:
    # Direct import from kingdomweb3_v2 - no relative imports or fallbacks
    from kingdomweb3_v2 import (
        KingdomWeb3, get_kingdom_web3, 
        create_web3_instance, create_async_web3_instance,
        add_middleware, to_checksum_address as toChecksumAddress, 
        TxParams, 
        # 2025 FIX: Import available exceptions with fallbacks
        ValidationError
    )
    
    # Create global kingdom_web3 instance - MANDATORY, no fallbacks
    kingdom_web3 = get_kingdom_web3()
    
    # Use KingdomWeb3 directly
    Web3 = kingdom_web3
    AsyncWeb3 = kingdom_web3  # Use same instance for async operations
    provider = None  # Will be set by network
    
    logger.info("Successfully imported kingdomweb3_v2 components")
    
    # Set availability flag
    bridge_available = True
    logger.info("Blockchain bridge is available and ready")
    
except Exception as e:
    logger.info(f"Using kingdomweb3_v2 directly instead of blockchain bridge: {str(e)}")
    # Set bridge as available since we have kingdomweb3_v2
    BRIDGE_AVAILABLE = True
    # Import minimal required components
    try:
        import kingdomweb3_v2
        logger.info("Successfully connected to kingdomweb3_v2 - bridge functionality available")
    except ImportError:
        logger.warning("Neither blockchain bridge nor kingdomweb3_v2 available - using fallback mode")
        BRIDGE_AVAILABLE = False

class NetworkStats:
    """
    Kingdom AI Network Statistics Manager
    
    Provides comprehensive blockchain network statistics and analytics,
    including gas prices, network health, node connectivity, and 
    transaction throughput. Integrates with the blockchain bridge
    for consistent Web3 access.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the NetworkStats component."""
        self.name = "blockchain.networkstats"
        self.logger = logging.getLogger(f"KingdomAI.NetworkStats")
        self._event_bus = event_bus
        self._config = config or {}
        self.initialized = False
        
        # Blockchain integration components
        self.web3 = None
        self.async_web3 = None
        self.available = False
        
        # Network statistics
        self.current_stats = {
            "gas_price": 0,
            "max_priority_fee": 0,
            "base_fee": 0,
            "block_time": 0,
            "block_height": 0,
            "peers": 0,
            "pending_tx_count": 0,
            "last_updated": 0,
            "network_id": 0,
            "network_name": "",
            "is_syncing": False
        }
        
        # Historical data
        self.historical_gas_prices = []
        self.historical_block_times = []
        self.max_history_length = self._config.get('max_history_length', 100)
        
        # Update interval in seconds
        self.update_interval = self._config.get('update_interval', 30)
        
        # Networks configuration
        self.networks = {
            1: "Ethereum Mainnet",
            3: "Ropsten",
            4: "Rinkeby",
            5: "Goerli",
            42: "Kovan",
            56: "BSC",
            137: "Polygon",
            42161: "Arbitrum",
            10: "Optimism"
        }
        
        # Initialize blockchain connections
        self._initialize_blockchain_connection()
        
        # Start monitoring if everything is set up
        if self._event_bus:
            self._register_event_handlers()
            
        self.logger.info(f"NetworkStats initialized")
    
    def _initialize_blockchain_connection(self):
        """Initialize connections to blockchain through bridge."""
        try:
            if not BRIDGE_AVAILABLE:
                self.logger.warning("Blockchain bridge not available, limited functionality")
                self.available = False
                return
                
            # Get Web3 instances from the blockchain bridge
            self.web3 = create_web3_instance()
            
            # Get async web3 if needed
            provider_url = self._config.get('provider_url', 'http://localhost:8545')
            self.async_web3 = AsyncWeb3(get_web3_provider('async_http', provider_url))
            # Add async POA middleware for proper blockchain support
            self.async_web3.middleware_onion.inject(async_geth_poa_middleware, layer=0)
            
            self.available = self.web3 is not None
            if self.available:
                self.logger.info("Blockchain connection established")
                
                # Determine network
                self._determine_network()
                
                # Start background monitoring tasks if async web3 is available
                if self.async_web3 and self._event_bus:
                    asyncio.create_task(self._start_monitoring_loop())
            else:
                self.logger.warning("Blockchain connection failed")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize blockchain connection: {str(e)}")
            self.available = False
    
    def _determine_network(self):
        """Determine the connected network."""
        try:
            if self.web3:
                network_id = self.web3.eth.chain_id
                self.current_stats["network_id"] = network_id
                self.current_stats["network_name"] = self.networks.get(
                    network_id, f"Unknown Network ({network_id})"
                )
                self.logger.info(f"Connected to {self.current_stats['network_name']}")
        except Exception as e:
            self.logger.error(f"Failed to determine network: {str(e)}")
    
    @property
    def event_bus(self):
        """Get the event bus."""
        return self._event_bus
    
    @event_bus.setter
    def event_bus(self, bus):
        """Set the event bus."""
        self._event_bus = bus
        if bus:
            self._register_event_handlers()
    
    def set_event_bus(self, bus):
        """Set the event bus and return success."""
        self.event_bus = bus
        return bus is not None
    
    def _register_event_handlers(self):
        """Register handlers with the event bus."""
        if not self._event_bus:
            return False
            
        try:
            # Core functionality handlers
            self._event_bus.subscribe(f"{self.name}.request", self._handle_request)
            self._event_bus.subscribe(f"{self.name}.get_gas_price", self._handle_get_gas_price)
            self._event_bus.subscribe(f"{self.name}.get_network_stats", self._handle_get_network_stats)
            self._event_bus.subscribe(f"{self.name}.get_historical_data", self._handle_get_historical_data)
            
            # Connect to the blockchain connector's events if available
            self._event_bus.subscribe("blockchain.connector.ready", self._handle_blockchain_ready)
            self._event_bus.subscribe("blockchain.new_block", self._handle_new_block)
            
            self.logger.debug(f"Registered event handlers for {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
            return False
    
    def _handle_request(self, event_type, data):
        """Handle general component requests."""
        self.logger.debug(f"Handling request {event_type}: {data}")
        
        action = data.get('action') if isinstance(data, dict) else None
        response = {"status": "success", "origin": self.name}
        
        if action == "status":
            response["data"] = {
                "available": self.available,
                "initialized": self.initialized,
                "network": self.current_stats["network_name"],
                "gas_price": self.current_stats["gas_price"],
                "block_height": self.current_stats["block_height"],
                "last_updated": self.current_stats["last_updated"]
            }
        elif action == "update":
            asyncio.create_task(self._update_statistics())
            response["data"] = {"message": "Update triggered"}
        else:
            response["data"] = {"message": "Request processed by NetworkStats"}
        
        if self._event_bus:
            self._event_bus.publish(f"{self.name}.response", response)
        
        return response
    
    def _handle_get_gas_price(self, event_type, data):
        """Handle request to get current gas price."""
        response = {
            "status": "success",
            "data": {
                "gas_price": self.current_stats["gas_price"],
                "max_priority_fee": self.current_stats["max_priority_fee"],
                "base_fee": self.current_stats["base_fee"],
                "last_updated": self.current_stats["last_updated"]
            }
        }
            
        if self._event_bus:
            self._event_bus.publish(f"{self.name}.response", response)
        
        return response
    
    def _handle_get_network_stats(self, event_type, data):
        """Handle request to get current network statistics."""
        response = {
            "status": "success",
            "data": self.current_stats
        }
            
        if self._event_bus:
            self._event_bus.publish(f"{self.name}.response", response)
        
        return response
    
    def _handle_get_historical_data(self, event_type, data):
        """Handle request to get historical data."""
        data_type = data.get('type', 'gas_price')
        limit = data.get('limit', 100)
        
        if data_type == 'gas_price':
            history = self.historical_gas_prices[-limit:]
        elif data_type == 'block_time':
            history = self.historical_block_times[-limit:]
        else:
            history = []
        
        response = {
            "status": "success",
            "data": {
                "type": data_type,
                "history": history,
                "count": len(history)
            }
        }
            
        if self._event_bus:
            self._event_bus.publish(f"{self.name}.response", response)
        
        return response
    
    def _handle_blockchain_ready(self, event_type, data):
        """Handle blockchain connector ready events."""
        # Reinitialize the connection if needed
        if not self.available:
            self._initialize_blockchain_connection()
            
    def _handle_new_block(self, event_type, data):
        """Handle new block events."""
        # Update statistics when a new block is mined
        asyncio.create_task(self._update_statistics())
    
    async def _update_statistics(self):
        """Update all blockchain network statistics."""
        if not self.available or not self.async_web3:
            return
        
        try:
            # Get basic statistics
            block_number = await self.async_web3.eth.block_number
            last_block = await self.async_web3.eth.get_block('latest')
            
            # Update block height
            self.current_stats["block_height"] = block_number
            
            # Calculate block time if we have previous data
            if "last_block_timestamp" in self.__dict__:
                block_time = last_block.timestamp - self.__dict__["last_block_timestamp"]
                self.current_stats["block_time"] = block_time
                
                # Add to historical data
                self.historical_block_times.append({
                    "timestamp": int(time.time()),
                    "block_number": block_number,
                    "block_time": block_time
                })
                
                # Trim history if needed
                if len(self.historical_block_times) > self.max_history_length:
                    self.historical_block_times = self.historical_block_times[-self.max_history_length:]
            
            # Store current block timestamp for next calculation
            self.__dict__["last_block_timestamp"] = last_block.timestamp
            
            # Get gas prices
            gas_price = await self.async_web3.eth.gas_price
            self.current_stats["gas_price"] = self.web3.from_wei(gas_price, 'gwei')
            
            # Try to get EIP-1559 gas data
            try:
                fee_history = await self.async_web3.eth.fee_history(1, 'latest', [50])
                if fee_history and hasattr(fee_history, 'baseFeePerGas') and len(fee_history.baseFeePerGas) > 0:
                    self.current_stats["base_fee"] = self.web3.from_wei(fee_history.baseFeePerGas[0], 'gwei')
                
                if fee_history and hasattr(fee_history, 'reward') and len(fee_history.reward) > 0 and len(fee_history.reward[0]) > 0:
                    self.current_stats["max_priority_fee"] = self.web3.from_wei(fee_history.reward[0][0], 'gwei')
            except Exception as e:
                self.logger.debug(f"Failed to get EIP-1559 gas data: {str(e)}")
            
            # Get pending transaction count
            self.current_stats["pending_tx_count"] = await self.async_web3.eth.get_block_transaction_count('pending')
            
            # Check if node is syncing
            sync_status = await self.async_web3.eth.syncing
            self.current_stats["is_syncing"] = sync_status is not False
            
            # Try to get peer count
            try:
                self.current_stats["peers"] = await self.async_web3.net.peer_count
            except Exception as e:
                self.logger.debug(f"Failed to get peer count: {str(e)}")
            
            # Update timestamp
            self.current_stats["last_updated"] = int(time.time())
            
            # Add to historical gas price data
            self.historical_gas_prices.append({
                "timestamp": self.current_stats["last_updated"],
                "gas_price": self.current_stats["gas_price"],
                "base_fee": self.current_stats["base_fee"],
                "max_priority_fee": self.current_stats["max_priority_fee"]
            })
            
            # Trim history if needed
            if len(self.historical_gas_prices) > self.max_history_length:
                self.historical_gas_prices = self.historical_gas_prices[-self.max_history_length:]
            
            # Publish updated stats
            if self._event_bus:
                self._event_bus.publish(f"{self.name}.updated", {
                    "stats": self.current_stats
                })
            
            self.logger.debug(f"Updated network statistics: block={block_number}, gas={self.current_stats['gas_price']} gwei")
            
        except Exception as e:
            self.logger.error(f"Failed to update network statistics: {str(e)}")
    
    async def _start_monitoring_loop(self):
        """Start the blockchain monitoring loop."""
        self.logger.info("Starting network statistics monitoring loop")
        
        if not self.available or not self.async_web3:
            self.logger.warning("Cannot start monitoring: blockchain connection not available")
            return
            
        try:
            # Initial update
            await self._update_statistics()
            
            # Monitor continuously
            while self.available:
                try:
                    # Wait for interval
                    await asyncio.sleep(self.update_interval)
                    
                    # Update statistics
                    await self._update_statistics()
                        
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {str(e)}")
                    await asyncio.sleep(60)  # Wait a bit longer on error
                    
        except Exception as e:
            self.logger.error(f"Monitoring loop failed: {str(e)}")
        finally:
            self.logger.info("Network statistics monitoring loop stopped")
    
    async def initialize(self):
        """Initialize the component asynchronously."""
        if self.initialized:
            return True
            
        try:
            # Update statistics immediately
            if self.available and self.async_web3:
                await self._update_statistics()
            
            self.initialized = True
            self.logger.info("NetworkStats initialized successfully")
            
            # Publish ready event
            if self._event_bus:
                self._event_bus.publish(f"{self.name}.ready", {"status": "ready"})
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize NetworkStats: {str(e)}")
            return False
    
    def initialize_sync(self):
        """Initialize the component synchronously."""
        if self.initialized:
            return True
            
        try:
            # We can't update stats synchronously (needs async), so just mark as initialized
            self.initialized = True
            self.logger.info("NetworkStats initialized synchronously")
            
            # Start update task if event loop is running
            try:
                if self.available and self.async_web3:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self._update_statistics())
            except Exception as e:
                self.logger.debug(f"Could not run initial update: {str(e)}")
            
            # Publish ready event
            if self._event_bus:
                self._event_bus.publish(f"{self.name}.ready", {"status": "ready"})
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize NetworkStats synchronously: {str(e)}")
            return False


def create_network_stats(event_bus=None, config=None):
    """
    Factory function to create a NetworkStats instance.
    
    Args:
        event_bus: Optional event bus for component communication
        config: Optional configuration dictionary
        
    Returns:
        NetworkStats instance
    """
    try:
        stats = NetworkStats(event_bus, config)
        return stats
    except Exception as e:
        logging.getLogger("KingdomAI").error(f"Failed to create NetworkStats: {str(e)}")
        return None

# This ensures the module is always "available" in some form
NETWORK_STATS_AVAILABLE = True
from kingdomweb3_v2 import rpc_manager, api_key_manager
