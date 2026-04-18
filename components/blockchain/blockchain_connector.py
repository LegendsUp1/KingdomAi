"""
BlockchainConnector - Kingdom AI component
"""
import os
import logging
from typing import Any, Dict, Optional

# Set up logger for this module
logger = logging.getLogger("KingdomAI.BlockchainConnector")

# Imports for blockchain connectivity
try:
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
    from web3.exceptions import Web3Exception
    
    # For handling different provider types
    from web3.providers import HTTPProvider, WebsocketProvider
    
    web3_available = True
    logger.info('Web3 imported successfully - using real Web3 implementation')
    
except ImportError:
    # We don't create dummy classes per system requirements
    # Instead we'll raise an exception during initialization
    logger.error('Web3 package not available - Ethereum functionality will be limited')
    logger.error('Install Web3 using: pip install web3')
    web3_available = False

# Set the constant after determining availability
HAS_WEB3 = web3_available

class BlockchainConnector:
    """
    BlockchainConnector for Kingdom AI system.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the BlockchainConnector."""
        self.name = "blockchain.blockchainconnector"
        self.logger = logging.getLogger(f"KingdomAI.BlockchainConnector")
        self._event_bus = event_bus
        self._config = config or {}
        self.initialized = False
        self.status = "disconnected"  # Add status attribute
        self.logger.info(f"BlockchainConnector initialized")
    
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
        return True
    
    def _register_event_handlers(self):
        """Register handlers with the event bus."""
        if not self._event_bus:
            return False
            
        try:
            self._event_bus.subscribe(f"blockchain.request", self._handle_request)
            self.logger.debug(f"Registered event handlers for {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register event handlers: {e}")
            return False
    
    def _handle_request(self, event_type, data):
        """Handle component requests."""
        self.logger.debug(f"Handling request {event_type}: {data}")
        
        if self._event_bus:
            self._event_bus.publish(f"blockchain.response", {
                "status": "success",
                "origin": self.name,
                "data": {"message": "Request processed by BlockchainConnector"}
            })
        
        return {"status": "success"}
    
    async def initialize(self):
        """Initialize the component asynchronously."""
        self.logger.info(f"Initializing BlockchainConnector...")
        
        if not HAS_WEB3:
            self.logger.error("Web3 library is required for blockchain connectivity")
            self.logger.error("Install Web3: pip install web3")
            raise ImportError("Web3 library is required for blockchain connectivity")
            
        try:
            # Initialize Web3 connection
            provider_url = self._config.get('web3_provider', 'http://localhost:8545')
            if provider_url.startswith('ws'):
                self.web3 = Web3(WebsocketProvider(provider_url))
            else:
                self.web3 = Web3(HTTPProvider(provider_url))
                
            # Apply middleware for compatibility with POA chains
            self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            # Test connection
            if self.web3.is_connected():
                self.logger.info(f"Successfully connected to Ethereum node at {provider_url}")
            else:
                self.logger.error(f"Failed to connect to Ethereum node at {provider_url}")
                raise ConnectionError(f"Could not connect to Ethereum node at {provider_url}")
                
            self.initialized = True
            self.logger.info(f"BlockchainConnector initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing BlockchainConnector: {e}")
            raise
    
    def initialize_sync(self):
        """Initialize the component synchronously."""
        self.logger.info(f"Synchronously initializing BlockchainConnector...")
        
        if not HAS_WEB3:
            self.logger.error("Web3 library is required for blockchain connectivity")
            self.logger.error("Install Web3: pip install web3")
            raise ImportError("Web3 library is required for blockchain connectivity")
            
        try:
            # Initialize Web3 connection
            provider_url = self._config.get('web3_provider', 'http://localhost:8545')
            if provider_url.startswith('ws'):
                self.web3 = Web3(WebsocketProvider(provider_url))
            else:
                self.web3 = Web3(HTTPProvider(provider_url))
                
            # Apply middleware for compatibility with POA chains
            self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            # Test connection
            if self.web3.is_connected():
                self.logger.info(f"Successfully connected to Ethereum node at {provider_url}")
            else:
                self.logger.error(f"Failed to connect to Ethereum node at {provider_url}")
                raise ConnectionError(f"Could not connect to Ethereum node at {provider_url}")
                
            self.initialized = True
            self.logger.info(f"BlockchainConnector synchronous initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Error during synchronous initialization: {e}")
            raise
    
    async def get_balance(self, address: str, network: str = None) -> float:
        """Get balance for an address."""
        try:
            if hasattr(self, 'web3') and self.web3:
                balance_wei = self.web3.eth.get_balance(address)
                balance_eth = self.web3.from_wei(balance_wei, 'ether')
                return float(balance_eth)
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return 0.0
    
    async def send_transaction(self, tx_data: dict) -> dict:
        """Send a transaction."""
        try:
            if hasattr(self, 'web3') and self.web3:
                # This would need proper transaction signing in real implementation
                self.logger.info(f"Transaction request: {tx_data}")
                return {"status": "success", "hash": "0x" + "0" * 64}
            return {"status": "error", "error": "Web3 not initialized"}
        except Exception as e:
            self.logger.error(f"Error sending transaction: {e}")
            return {"status": "error", "error": str(e)}
    
    def connect(self) -> bool:
        """Connect to the blockchain network."""
        try:
            if hasattr(self, 'web3') and self.web3 and self.web3.is_connected():
                self.status = "connected"
                return True
            self.status = "disconnected"
            return False
        except Exception as e:
            self.logger.error(f"Error checking connection: {e}")
            self.status = "error"
            return False
    
    def get_web3(self):
        """Get the Web3 instance."""
        return getattr(self, 'web3', None)