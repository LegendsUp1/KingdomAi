"""Blockchain manager for coordinating all blockchain components in Kingdom AI."""

import logging
import time
import inspect
from typing import Dict, Any

# Setup logger
logger = logging.getLogger("kingdom_ai.blockchain.manager")

# Import base component
from core.base_component import BaseComponent

# Import blockchain components
from core.blockchain.connector import create_blockchain_connector
from core.blockchain.wallet import WalletManager
from core.blockchain.mining_dashboard import MiningDashboard

# Constants
DEFAULT_CHAINS = ["bitcoin", "ethereum"]

# Import all 228 networks from kingdomweb3_v2
try:
    from kingdomweb3_v2 import COMPLETE_BLOCKCHAIN_NETWORKS
    ALL_SUPPORTED_CHAINS = list(COMPLETE_BLOCKCHAIN_NETWORKS.keys())
    logger.info(f"✅ Loaded {len(ALL_SUPPORTED_CHAINS)} blockchain networks from kingdomweb3_v2")
except ImportError:
    ALL_SUPPORTED_CHAINS = DEFAULT_CHAINS
    logger.warning("⚠️ Could not import COMPLETE_BLOCKCHAIN_NETWORKS, using default chains")


class BlockchainError(Exception):
    """Base exception class for blockchain-related errors."""
    pass


class BlockchainManager(BaseComponent):
    """Central manager for all blockchain components."""
    
    def __init__(self, event_bus=None, config=None):
        """Initialize blockchain manager.
        
        Args:
            event_bus: Event bus instance
            config: Configuration dictionary
        """
        super().__init__(name="BlockchainManager", event_bus=event_bus)
        self.config = config or {}
        self.connectors = {}
        self.wallet_manager = None
        self.mining_dashboard = None
        self.is_initialized = False
        self.status = {}
        self.supported_chains = self.config.get("supported_chains", DEFAULT_CHAINS)
    
    async def initialize(self) -> bool:
        """Initialize blockchain manager and all components.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            logger.info("Initializing blockchain manager")
            
            # Register event handlers
            if self.event_bus:
                self.event_bus.subscribe_sync("blockchain.connect", self.handle_connect_request)
                self.event_bus.subscribe_sync("blockchain.disconnect", self.handle_disconnect_request)
                self.event_bus.subscribe_sync("blockchain.status", self.handle_status_request)
                self.event_bus.subscribe_sync("blockchain.transaction", self.handle_transaction_request)
                self.event_bus.subscribe_sync("blockchain.chains", self.handle_chains_request)
                self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
            
            # Initialize blockchain connectors
            for chain in self.supported_chains:
                try:
                    # Create connector
                    connector = create_blockchain_connector(chain, self.event_bus, self.config)
                    
                    # Initialize connector
                    success = await connector.initialize()
                    
                    if success:
                        # Add to connector list
                        self.connectors[chain] = connector
                        logger.info(f"Initialized {chain} connector")
                    else:
                        logger.error(f"Failed to initialize {chain} connector")
                except Exception as e:
                    logger.error(f"Error initializing {chain} connector: {e}")
            
            # Initialize wallet manager
            try:
                self.wallet_manager = WalletManager(self.event_bus, self.config)
                success = await self.wallet_manager.initialize()
                
                if success:
                    logger.info("Initialized wallet manager")
                else:
                    logger.error("Failed to initialize wallet manager")
                    self.wallet_manager = None
            except Exception as e:
                logger.error(f"Error initializing wallet manager: {e}")
                self.wallet_manager = None
            
            # Initialize mining dashboard
            try:
                self.mining_dashboard = MiningDashboard(self.event_bus, self.config)
                success = await self.mining_dashboard.initialize()
                
                if success:
                    logger.info("Initialized mining dashboard")
                else:
                    logger.error("Failed to initialize mining dashboard")
                    self.mining_dashboard = None
            except Exception as e:
                logger.error(f"Error initializing mining dashboard: {e}")
                self.mining_dashboard = None
            
            # Update status
            self.status = {
                "connectors": {chain: connector.connected for chain, connector in self.connectors.items()},
                "wallet_manager": self.wallet_manager is not None,
                "mining_dashboard": self.mining_dashboard is not None,
                "supported_chains": self.supported_chains,
                "all_available_chains": len(ALL_SUPPORTED_CHAINS),
                "last_updated": time.time()
            }
            
            logger.info(f"Blockchain manager initialized with {len(self.connectors)} connectors")
            logger.info(f"✅ Total available networks: {len(ALL_SUPPORTED_CHAINS)} from kingdomweb3_v2")
            self.is_initialized = True
            return True
        except Exception as e:
            logger.error(f"Error initializing blockchain manager: {e}")
            return False
    
    async def handle_connect_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle blockchain connect request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling blockchain connect request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            
            if chain:
                # Connect to specific blockchain
                if chain not in self.connectors:
                    raise ValueError(f"Unsupported blockchain: {chain}")
                
                # Connect to blockchain
                connector = self.connectors[chain]
                success = await connector.async_connect()
                
                # Build response
                response = {
                    "request_id": data.get("request_id"),
                    "status": "connected" if success else "error",
                    "chain": chain,
                    "message": f"Connected to {chain}" if success else f"Failed to connect to {chain}"
                }
            else:
                # Connect to all blockchains
                results = {}
                
                for chain, connector in self.connectors.items():
                    try:
                        success = await connector.async_connect()
                        results[chain] = {
                            "status": "connected" if success else "error",
                            "message": f"Connected to {chain}" if success else f"Failed to connect to {chain}"
                        }
                    except Exception as e:
                        results[chain] = {
                            "status": "error",
                            "message": f"Error connecting to {chain}: {str(e)}"
                        }
                
                # Build response
                response = {
                    "request_id": data.get("request_id"),
                    "status": "success",
                    "results": results
                }
            
            # Update status
            self.status = {
                "connectors": {chain: connector.connected for chain, connector in self.connectors.items()},
                "wallet_manager": self.wallet_manager is not None,
                "mining_dashboard": self.mining_dashboard is not None,
                "supported_chains": self.supported_chains,
                "last_updated": time.time()
            }
            
            # Publish response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.connect.response", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
        except Exception as e:
            logger.error(f"Error handling connect request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error connecting to blockchain: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.connect.error", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
    
    async def handle_disconnect_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle blockchain disconnect request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling blockchain disconnect request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            
            if chain:
                # Disconnect from specific blockchain
                if chain not in self.connectors:
                    raise ValueError(f"Unsupported blockchain: {chain}")
                
                # Disconnect from blockchain
                success = await self.connectors[chain].disconnect()
                
                # Build response
                response = {
                    "request_id": data.get("request_id"),
                    "status": "disconnected" if success else "error",
                    "chain": chain,
                    "message": f"Disconnected from {chain}" if success else f"Failed to disconnect from {chain}"
                }
            else:
                # Disconnect from all blockchains
                results = {}
                
                for chain, connector in self.connectors.items():
                    try:
                        success = await connector.disconnect()
                        results[chain] = {
                            "status": "disconnected" if success else "error",
                            "message": f"Disconnected from {chain}" if success else f"Failed to disconnect from {chain}"
                        }
                    except Exception as e:
                        results[chain] = {
                            "status": "error",
                            "message": f"Error disconnecting from {chain}: {str(e)}"
                        }
                
                # Build response
                response = {
                    "request_id": data.get("request_id"),
                    "status": "success",
                    "results": results
                }
            
            # Update status
            self.status = {
                "connectors": {chain: connector.connected for chain, connector in self.connectors.items()},
                "wallet_manager": self.wallet_manager is not None,
                "mining_dashboard": self.mining_dashboard is not None,
                "supported_chains": self.supported_chains,
                "last_updated": time.time()
            }
            
            # Publish response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.disconnect.response", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
        except Exception as e:
            logger.error(f"Error handling disconnect request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error disconnecting from blockchain: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.disconnect.error", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
    
    async def handle_status_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle blockchain status request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling blockchain status request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            
            if chain:
                # Get status for specific blockchain
                if chain not in self.connectors:
                    raise ValueError(f"Unsupported blockchain: {chain}")
                
                # Get connector status
                connector_status = await self.connectors[chain].handle_status("blockchain.status", data)
                
                # Build response
                response = {
                    "request_id": data.get("request_id"),
                    "status": "success",
                    "chain": chain,
                    "connector_status": connector_status
                }
            else:
                # Update status
                self.status = {
                    "connectors": {chain: connector.connected for chain, connector in self.connectors.items()},
                    "wallet_manager": self.wallet_manager is not None,
                    "mining_dashboard": self.mining_dashboard is not None,
                    "supported_chains": self.supported_chains,
                    "last_updated": time.time()
                }
                
                # Build response
                response = {
                    "request_id": data.get("request_id"),
                    "status": "success",
                    "blockchain_status": self.status
                }
            
            # Publish response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.status.response", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
        except Exception as e:
            logger.error(f"Error handling status request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error getting blockchain status: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.status.error", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
    
    async def handle_transaction_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle blockchain transaction request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling blockchain transaction request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            
            if not chain:
                raise ValueError("Chain is required for transaction requests")
            
            if chain not in self.connectors:
                raise ValueError(f"Unsupported blockchain: {chain}")
            
            # Check if connector is connected
            if not self.connectors[chain].connected:
                raise ValueError(f"Not connected to {chain}")
            
            # Forward transaction request to connector
            result = await self.connectors[chain].handle_transaction("blockchain.transaction", data)
            
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "chain": chain,
                "result": result
            }
            
            # Publish response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.transaction.response", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
        except Exception as e:
            logger.error(f"Error handling transaction request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error processing blockchain transaction: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.transaction.error", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
    
    async def handle_chains_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle supported chains request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling supported chains request: {data}")
        
        try:
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "supported_chains": self.supported_chains,
                "connected_chains": [chain for chain, connector in self.connectors.items() if connector.connected]
            }
            
            # Publish response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.chains.response", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
        except Exception as e:
            logger.error(f"Error handling chains request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error getting supported chains: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                result = self.event_bus.publish("blockchain.chains.error", response)
                if inspect.iscoroutine(result):
                    await result
            
            return response
    
    async def handle_shutdown(self, data: Dict[str, Any]) -> None:
        """Handle system shutdown event.
        
        Args:
            data: Shutdown event data
        """
        logger.info("Handling blockchain manager shutdown")
        
        try:
            # Disconnect from all blockchains
            for chain, connector in self.connectors.items():
                try:
                    if connector.connected:
                        await connector.disconnect()
                    logger.info(f"Disconnected from {chain}")
                except Exception as e:
                    logger.error(f"Error disconnecting from {chain}: {e}")
            
            logger.info("Blockchain manager shutdown completed")
        except Exception as e:
            logger.error(f"Error during blockchain manager shutdown: {e}")
    
    def get_all_available_networks(self) -> list:
        """Get list of all 228 available blockchain networks.
        
        Returns:
            List of all network names from kingdomweb3_v2
        """
        return ALL_SUPPORTED_CHAINS
    
    def get_network_config(self, network_name: str):
        """Get configuration for a specific network.
        
        Args:
            network_name: Name of the blockchain network
            
        Returns:
            Network configuration dictionary or None if not found
        """
        try:
            from kingdomweb3_v2 import get_network_config
            return get_network_config(network_name)
        except ImportError:
            logger.error("Could not import get_network_config from kingdomweb3_v2")
            return None
    
    def get_network_count(self) -> int:
        """Get total count of available networks.
        
        Returns:
            Total number of networks (should be 228)
        """
        return len(ALL_SUPPORTED_CHAINS)
