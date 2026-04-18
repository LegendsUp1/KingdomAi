#!/usr/bin/env python3
"""
Kingdom AI - Web3 Connector

This module provides a robust Web3 connection with automatic fallbacks
and retry logic for the Kingdom AI system.
"""

import logging
import asyncio
import time
import os
import aiohttp

# Set up logging early
logger = logging.getLogger("KingdomAI.Web3Connector")

# Import Web3 - REQUIRED for Kingdom AI with no fallbacks
try:
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
    WEB3_AVAILABLE = True
    logger.info("Web3 module imported successfully")
except ImportError as e:
    # Kingdom AI requires Web3 with strict no-fallback policy
    error_msg = "Web3 module not available - Kingdom AI requires this component"
    logger.critical(error_msg)
    logger.critical(f"Import error details: {e}")
    # System halt - enforcing no-fallback policy for critical components
    raise RuntimeError(f"{error_msg} - system halting") from e

# Import required Web3 providers with no fallbacks
try:
    # Import HTTPProvider from web3.providers
    from web3.providers import HTTPProvider
    # Import native WebsocketProvider implementation
    from .kingdom_web3 import NativeWebsocketProvider as WebsocketProvider
    logger.info("Web3 providers imported successfully - using Kingdom AI native WebsocketProvider")
except ImportError as e:
    # Kingdom AI requires Web3 providers with strict no-fallback policy
    error_msg = "Web3 providers not available - Kingdom AI requires this component"
    logger.critical(error_msg)
    logger.critical(f"Import error details: {e}")
    # System halt - enforcing no-fallback policy for critical components
    raise RuntimeError(f"{error_msg} - system halting") from e

logger = logging.getLogger("KingdomAI.Web3Connector")

class CustomWebsocketProvider:
    """A wrapper around WebsocketProvider that handles reconnection."""
    
    def __init__(self, endpoint, **kwargs):
        self.endpoint = endpoint
        self.kwargs = kwargs
        self.provider = None
        self.connect()
    
    def connect(self):
        """Connect to the websocket provider."""
        try:
            if WebsocketProvider:
                self.provider = WebsocketProvider(self.endpoint, **self.kwargs)
                logger.info(f"Connected to WebsocketProvider at {self.endpoint}")
                return True
            else:
                logger.error("WebsocketProvider not available")
                return False
        except Exception as e:
            logger.error(f"Error connecting to WebsocketProvider: {e}")
            return False
    
    def is_connected(self):
        """Check if the provider is connected."""
        if not self.provider:
            return False
        
        try:
            # Try different connection check methods based on provider version
            if hasattr(self.provider, 'isConnected'):
                return self.provider.isConnected()
            elif hasattr(self.provider, 'is_connected'):
                return self.provider.is_connected()
            else:
                # If no method available, try a basic request
                return self.provider.make_request("net_version", []) is not None
        except Exception:
            return False
    
    def reconnect(self):
        """Reconnect to the websocket provider."""
        # Close existing connection if possible
        try:
            if hasattr(self.provider, 'close'):
                self.provider.close()
        except Exception:
            pass
        
        # Try to reconnect
        return self.connect()
    
    def make_request(self, method, params):
        """Make a request to the provider with automatic reconnection."""
        if not self.is_connected():
            if not self.reconnect():
                logger.error(f"Failed to reconnect to {self.endpoint}")
                return None
        
        try:
            return self.provider.make_request(method, params)
        except Exception as e:
            logger.error(f"Error making request: {e}")
            if not self.reconnect():
                logger.error("Failed to reconnect after request error")
            return None

class Web3Connector:
    """Robust Web3 connector with fallback options."""
    
    def __init__(self, event_bus=None):
        """Initialize the Web3 connector.
        
        Args:
            event_bus: The event bus for communication
        """
        self.event_bus = event_bus
        self.connections = {}
        self.fallback_connections = {}
        self.default_chain = "ethereum"
        self.connection_status = {}
        self.initialized = False
        self.last_block_heights = {}
        self.monitoring_task = None
        self.retry_attempts = {}
        self.max_retries = 5
        
        # Check if Web3 is available
        if not WEB3_AVAILABLE:
            logger.error("Web3 module not available")
    
    async def initialize(self, config=None):
        """Initialize Web3 connections.
        
        Args:
            config: Configuration dictionary with connection details
        """
        if not config:
            config = self._get_default_config()
        
        # Initialize connections
        for chain_id, chain_config in config.items():
            await self._initialize_chain_connection(chain_id, chain_config)
        
        # Set initialized flag
        self.initialized = True
        
        # Start monitoring task
        if not self.monitoring_task:
            self.monitoring_task = asyncio.create_task(self._monitor_connections())
        
        # Publish initial status
        if self.event_bus:
            self.event_bus.publish("blockchain.status", {
                "connected": any(status.get("connected", False) for status in self.connection_status.values()),
                "chains": self.connection_status
            })
    
    async def _initialize_chain_connection(self, chain_id, chain_config):
        """Initialize connection for a specific chain.
        
        Args:
            chain_id: Chain identifier
            chain_config: Configuration for the chain
        """
        # Extract connection details
        primary_endpoint = chain_config.get("endpoint", "")
        connection_type = chain_config.get("type", "http").lower()
        
        if not primary_endpoint:
            logger.error(f"No endpoint specified for {chain_id}")
            self.connection_status[chain_id] = {"connected": False, "error": "No endpoint specified"}
            return
        
        # Initialize connection status
        self.connection_status[chain_id] = {"connected": False, "endpoint": primary_endpoint}
        
        # Try to connect to primary endpoint using environment variable if available
        provider_url = os.getenv('WEB3_PROVIDER_URL', primary_endpoint)
        logger.info(f"Attempting Web3 connection to {provider_url}")
        success = await self._connect_to_endpoint(chain_id, provider_url, connection_type)
        
        # If primary connection failed, log error and continue
        if not success:
            logger.error(f"All Web3 connection attempts failed for chain ID {chain_id}")
        
        return success
    
    async def _connect_to_endpoint(self, chain_id, endpoint, conn_type, is_fallback=False):
        """Connect to a specific endpoint.
        
        Args:
            chain_id: Chain identifier
            endpoint: Endpoint URL
            conn_type: Connection type (http, ws)
            is_fallback: Whether this is a fallback connection
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Create Web3 instance based on connection type
            if conn_type == "ws" or conn_type == "websocket":
                provider = CustomWebsocketProvider(endpoint)
                if not provider.is_connected():
                    return False
            else:  # Default to HTTP
                provider = HTTPProvider(endpoint)
            
            # Try to create Web3 instance
            if ASYNC_AVAILABLE and not is_fallback:
                # Use AsyncWeb3 for primary connections if available
                web3 = AsyncWeb3(provider)
                # Test connection with chain ID request
                try:
                    chain_id_hex = await web3.eth.chain_id
                    is_connected = True
                except Exception as e:
                    logger.error(f"Error getting chain ID for {endpoint}: {e}")
                    is_connected = False
            else:
                # Use regular Web3
                web3 = Web3(provider)
                # Test connection with chain ID request
                try:
                    chain_id_hex = web3.eth.chain_id
                    is_connected = True
                except Exception as e:
                    logger.error(f"Error getting chain ID for {endpoint}: {e}")
                    is_connected = False
            
            if is_connected:
                if is_fallback:
                    self.fallback_connections[chain_id] = web3
                else:
                    self.connections[chain_id] = web3
                
                # Get current block height
                try:
                    if ASYNC_AVAILABLE and isinstance(web3, AsyncWeb3):
                        self.last_block_heights[chain_id] = await web3.eth.block_number
                    else:
                        self.last_block_heights[chain_id] = web3.eth.block_number
                except Exception as e:
                    logger.error(f"Error getting block height for {chain_id}: {e}")
                    self.last_block_heights[chain_id] = 0
                
                logger.info(f"Connected to {chain_id} via {endpoint}")
                return True
            else:
                logger.error(f"Failed to connect to {endpoint}")
                return False
        except aiohttp.ClientError as e:
            logger.error(f"Failed to connect to {endpoint}: {e}")
            return False
        except Exception as e:
            logger.error(f"Web3 connection failed to {endpoint}: {e}")
            return False
    
    async def _monitor_connections(self):
        """Monitor connections and attempt reconnection if needed."""
        while True:
            try:
                # Check all connections
                for chain_id in list(self.connections.keys()):
                    await self._check_connection(chain_id)
                
                # Publish status update
                if self.event_bus:
                    self.event_bus.publish("blockchain.status", {
                        "connected": any(status.get("connected", False) for status in self.connection_status.values()),
                        "chains": self.connection_status
                    })
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in connection monitoring: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _check_connection(self, chain_id):
        """Check a specific connection and attempt reconnection if needed.
        
        Args:
            chain_id: Chain identifier
        """
        web3 = self.connections.get(chain_id)
        if not web3:
            return
        
        try:
            # Check if connection is alive by requesting latest block
            if ASYNC_AVAILABLE and isinstance(web3, AsyncWeb3):
                current_block = await web3.eth.block_number
            else:
                current_block = web3.eth.block_number
            
            # Update block height
            prev_block = self.last_block_heights.get(chain_id, 0)
            self.last_block_heights[chain_id] = current_block
            
            # If block height hasn't changed in a while, connection might be stale
            if prev_block > 0 and current_block == prev_block:
                self.retry_attempts[chain_id] = self.retry_attempts.get(chain_id, 0) + 1
                logger.warning(f"Block height for {chain_id} hasn't changed, might be stale (retry {self.retry_attempts[chain_id]})")
                
                # If too many retries, try to reconnect
                if self.retry_attempts[chain_id] > self.max_retries:
                    logger.warning(f"Reconnecting to {chain_id} due to stale connection")
                    config = self._get_chain_config(chain_id)
                    if config:
                        await self._initialize_chain_connection(chain_id, config)
            else:
                # Reset retry counter on successful update
                self.retry_attempts[chain_id] = 0
                
                # Update connection status
                if chain_id in self.connection_status:
                    self.connection_status[chain_id]["connected"] = True
                    self.connection_status[chain_id]["last_block"] = current_block
                    self.connection_status[chain_id]["last_check"] = time.time()
        except Exception as e:
            logger.error(f"Error checking connection for {chain_id}: {e}")
            
            # Update connection status
            if chain_id in self.connection_status:
                self.connection_status[chain_id]["connected"] = False
                self.connection_status[chain_id]["error"] = str(e)
            
            # Try to reconnect
            self.retry_attempts[chain_id] = self.retry_attempts.get(chain_id, 0) + 1
            if self.retry_attempts[chain_id] <= self.max_retries:
                logger.warning(f"Attempting to reconnect to {chain_id} (retry {self.retry_attempts[chain_id]})")
                config = self._get_chain_config(chain_id)
                if config:
                    await self._initialize_chain_connection(chain_id, config)
    
    def _get_default_config(self):
        """Get default configuration for blockchain connections."""
        return {
            "ethereum": {
                "endpoint": "https://ethereum.publicnode.com",
                "type": "http"
            },
            "polygon": {
                "endpoint": "https://polygon-rpc.com",
                "type": "http"
            },
            "binance": {
                "endpoint": "https://bsc-dataseed.binance.org",
                "type": "http"
            }
        }
    
    def _get_chain_config(self, chain_id):
        """Get configuration for a specific chain."""
        return self._get_default_config().get(chain_id)
    
    async def get_web3(self, chain_id=None):
        """Get Web3 instance for a specific chain.
        
        Args:
            chain_id: Chain identifier, uses default if None
            
        Returns:
            Web3 instance or None if not available
        """
        if not chain_id:
            chain_id = self.default_chain
            
        # If not initialized, try to initialize
        if not self.initialized:
            await self.initialize()
            
        # Get connection
        web3 = self.connections.get(chain_id)
        if not web3:
            logger.error(f"No Web3 connection available for {chain_id}")
            return None
            
        return web3
    
    async def get_balance(self, address, chain_id=None):
        """Get balance for an address.
        
        Args:
            address: The address to check
            chain_id: Chain identifier, uses default if None
            
        Returns:
            Balance in native currency or None if error
        """
        web3 = await self.get_web3(chain_id)
        if not web3:
            logger.error(f"No Web3 connection available for {chain_id}")
            return None
            
        try:
            # Validate address
            if not web3.is_address(address):
                logger.error(f"Invalid address: {address}")
                return None
                
            # Convert to checksum address
            checksum_address = web3.to_checksum_address(address)
            
            # Get balance
            if ASYNC_AVAILABLE and isinstance(web3, AsyncWeb3):
                balance_wei = await web3.eth.get_balance(checksum_address)
            else:
                balance_wei = web3.eth.get_balance(checksum_address)
                
            # Convert to ETH
            balance_eth = web3.from_wei(balance_wei, 'ether')
            
            return float(balance_eth)
        except Exception as e:
            logger.error(f"Error getting balance for {address}: {e}")
            return None
    
    async def get_gas_price(self, chain_id=None):
        """Get current gas price.
        
        Args:
            chain_id: Chain identifier, uses default if None
            
        Returns:
            Gas price in Gwei or None if error
        """
        web3 = await self.get_web3(chain_id)
        if not web3:
            logger.error(f"No Web3 connection available for {chain_id}")
            return None
            
        try:
            # Get gas price
            if ASYNC_AVAILABLE and isinstance(web3, AsyncWeb3):
                gas_price_wei = await web3.eth.gas_price
            else:
                gas_price_wei = web3.eth.gas_price
                
            # Convert to Gwei
            gas_price_gwei = web3.from_wei(gas_price_wei, 'gwei')
            
            return float(gas_price_gwei)
        except Exception as e:
            logger.error(f"Error getting gas price: {e}")
            return None
    
    async def get_latest_block(self, chain_id=None):
        """Get latest block data.
        
        Args:
            chain_id: Chain identifier, uses default if None
            
        Returns:
            Block data or None if error
        """
        web3 = await self.get_web3(chain_id)
        if not web3:
            logger.error(f"No Web3 connection available for {chain_id}")
            return None
            
        try:
            # Get latest block
            if ASYNC_AVAILABLE and isinstance(web3, AsyncWeb3):
                block = await web3.eth.get_block('latest')
            else:
                block = web3.eth.get_block('latest')
                
            # Extract relevant data
            return {
                "number": block.number,
                "timestamp": block.timestamp,
                "transactions": len(block.transactions),
                "gas_used": block.gas_used,
                "gas_limit": block.gas_limit,
                "base_fee_per_gas": getattr(block, 'base_fee_per_gas', None),
                "difficulty": getattr(block, 'difficulty', None),
                "total_difficulty": getattr(block, 'total_difficulty', None),
                "miner": block.miner
            }
        except Exception as e:
            logger.error(f"Error getting latest block: {e}")
            return None
