#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Blockchain Connector Component

Provides connectivity to blockchain networks with robust error handling,
fallback mechanisms, and connection retries.
"""

import logging
import asyncio
import secrets
from typing import Any, Dict

from web3 import Web3
try:
    from web3.eth.async_eth import AsyncEth
except ImportError:
    AsyncEth = None

try:
    from web3.main import AsyncWeb3
except ImportError:
    try:
        from web3 import AsyncWeb3
    except ImportError:
        AsyncWeb3 = None

try:
    from web3.middleware import ExtraDataToPOAMiddleware as geth_poa_middleware
except ImportError:
    try:
        from web3.middleware.geth_poa import geth_poa_middleware
    except ImportError:
        try:
            from web3.middleware import geth_poa_middleware
        except ImportError:
            geth_poa_middleware = None

try:
    from web3.providers.async_base import AsyncBaseProvider
except ImportError:
    AsyncBaseProvider = None

try:
    from web3.providers.rpc import HTTPProvider
except ImportError:
    try:
        from web3.providers.http import HTTPProvider
    except ImportError:
        HTTPProvider = None

try:
    from web3.providers.websocket import LegacyWebSocketProvider as WebsocketProvider
except ImportError:
    try:
        from web3.providers.websocket import WebsocketProvider
    except ImportError:
        try:
            from web3.providers.websocket.websocket import WebsocketProvider
        except ImportError:
            WebsocketProvider = None

try:
    from hexbytes import HexBytes
except ImportError:
    HexBytes = None

try:
    from web3.types import Wei, TxParams
except ImportError:
    Wei = None
    TxParams = dict

# Set up logger first
logger = logging.getLogger("BlockchainConnector")

# ======================================================================================
# WEBSOCKET PROVIDER IMPLEMENTATION
# This section provides a universal WebsocketProvider that works with all web3 versions
# and includes graceful fallback mechanisms for maximum reliability.
# ======================================================================================

# Custom WebsocketProvider that works with all web3 versions
class CustomWebsocketProvider:
    """Universal WebsocketProvider with fallback mechanisms"""
    def __init__(self, endpoint_uri, *args, **kwargs):
        """Initialize the WebsocketProvider.
        
        Args:
            endpoint_uri: WebSocket endpoint URI
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        self.endpoint_uri = endpoint_uri
        self.connected = False
        self._ws = None
        self._real_provider = None
        self.logger = logging.getLogger("KingdomAI.WebsocketProvider")
        
        # Only try to use real implementation if web3 is available
        if WebsocketProvider is not None:
            try:
                self._initialize_real_provider(endpoint_uri, *args, **kwargs)
            except Exception as e:
                self.logger.error(f"Failed to initialize real provider: {e}")
                self._real_provider = None
        else:
            logger.warning("Web3 WebsocketProvider not available, using mock mode")
            self._real_provider = None
    
    def _initialize_real_provider(self, endpoint_uri, *args, **kwargs):
        """Initialize the real WebsocketProvider if available.
        
        Args:
            endpoint_uri: WebSocket endpoint URI
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        try:
            self._real_provider = WebsocketProvider(endpoint_uri, *args, **kwargs)
            self.connected = True
        except Exception as e:
            self.logger.error(f"Error initializing websocket provider: {e}")
            self._real_provider = None
    
    def make_request(self, method, params):
        """Make a request to the websocket provider with fallback.
        
        Args:
            method: RPC method
            params: RPC parameters
            
        Returns:
            Response from provider or mock response
        """
        if self._real_provider:
            try:
                return self._real_provider.make_request(method, params)
            except Exception as e:
                self.logger.error(f"Error making request: {e}, using fallback")
                return self._fallback_result_for_method(method, params)
        else:
            return self._fallback_result_for_method(method, params)
    
    def _fallback_result_for_method(self, method, params):
        """Attempt a real RPC call as fallback, or return an honest error.
        
        Args:
            method: RPC method
            params: RPC parameters
            
        Returns:
            Real RPC response or error indicating data unavailable
        """
        import urllib.request
        import json
        
        rpc_url = getattr(self, 'endpoint_uri', None) or "https://rpc.ankr.com/eth"
        rpc_request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params if params else [],
            "id": 1
        }
        
        try:
            req_data = json.dumps(rpc_request).encode('utf-8')
            request = urllib.request.Request(
                rpc_url,
                data=req_data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if "error" in result:
                    self.logger.error(f"RPC error for {method}: {result['error']}")
                    return {"error": result["error"]}
                return result
        except Exception as e:
            self.logger.error(f"Fallback RPC call failed for {method}: {e}")
            return {"error": {"code": -32603, "message": f"Data unavailable: {e}"}}

    def is_connected(self):
        """Check if connected to WebSocket provider.
        
        Returns:
            bool: True if connected, False otherwise
        """
        if self._real_provider and hasattr(self._real_provider, "is_connected"):
            try:
                return self._real_provider.is_connected()
            except Exception:
                return False
        return self.connected

    def disconnect(self):
        """Disconnect from WebSocket provider."""
        if self._real_provider and hasattr(self._real_provider, "disconnect"):
            try:
                self._real_provider.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting: {e}")
        
        self.connected = False

# For compatibility with imported code
from core.base_component import BaseComponent
from core.session_manager import SessionManager

class BlockchainConnector(BaseComponent):
    """Blockchain connector with robust error handling and fallback mechanisms.
    
    Features:
    - Multiple endpoint fallback
    - Automatic retries
    - Mock mode for testing/development
    - Event-driven architecture integration
    """
    
    def __init__(self, event_bus=None, config=None, session_manager=None):
        """Initialize the blockchain connector.
        
        Args:
            event_bus: System event bus
            config: Configuration dictionary
            session_manager: Session manager for HTTP requests
        """
        super().__init__(name="BlockchainConnector", event_bus=event_bus)
        self.config = config or {}
        self.session_manager = session_manager or SessionManager()
        self._web3 = None
        self.endpoint = None
        self.network_name = "unknown"  # Default network name
        self._mock_mode = False
        self._mock_mode_allowed = self.config.get("allow_mock_mode", True)
        self._session = None
        self.is_initialized = False
        self.is_running = False
        
        # Reconnection parameters
        self.max_retries = self.config.get("max_retries", 5)
        self.retry_delay = self.config.get("retry_delay", 2.0)
        self.max_retry_delay = self.config.get("max_retry_delay", 30.0)
        
        # Event handlers
        self.handlers = {
            "blockchain.connect": self.handle_connect_request,
            "blockchain.disconnect": self.handle_disconnect_request,
            "blockchain.transaction": self.handle_transaction,
            "blockchain.balance": self.handle_balance_request,
            "blockchain.config": self.handle_config_update,
            "system.shutdown": self.handle_shutdown
        }

    async def _get_network_name(self) -> str:
        """Get the name of the connected network."""
        try:
            # Get the network ID
            if not self._web3:
                return "Not Connected"
                
            network_names = {
                1: "Ethereum Mainnet",
                3: "Ropsten Testnet",
                4: "Rinkeby Testnet",
                5: "Goerli Testnet",
                42: "Kovan Testnet",
                56: "Binance Smart Chain",
                97: "BSC Testnet",
                137: "Polygon Mainnet",
                80001: "Polygon Mumbai Testnet",
                43114: "Avalanche C-Chain",
                43113: "Avalanche Fuji Testnet"
            }
            
            network_id = await self._web3.eth.chain_id
            return network_names.get(network_id, f"Unknown Network (ID: {network_id})")
        except Exception as e:
            logger.error(f"Error getting network name: {e}")
            return "Unknown Network"

    async def initialize(self) -> bool:
        """Initialize the blockchain connector.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            # Publish initialization status
            await self.publish_event("blockchain.status", {
                "status": "initializing",
                "component": "blockchain_connector"
            })
            
            # Get endpoints from config
            endpoints = self.config.get("endpoints", [])
            if not endpoints and "endpoint" in self.config:
                endpoints = [self.config["endpoint"]]
                
            if not endpoints:
                logger.warning("No blockchain endpoints configured, using default")
                endpoints = ["https://mainnet.infura.io/v3/your-infura-key"]
                
            self.endpoints = endpoints
            self.endpoint = endpoints[0]  # Start with the first endpoint
            
            # Initialize the session
            if self.session_manager and not self._session:
                self._session = await self.session_manager.get_session()
            
            self.is_initialized = True
            
            # Publish initialization success status
            await self.publish_event("blockchain.status", {
                "status": "initialized",
                "component": "blockchain_connector"
            })
            
            return True
        except Exception as e:
            logger.error(f"Error initializing blockchain connector: {e}")
            
            # Publish initialization failure status
            await self.publish_event("blockchain.status", {
                "status": "initialization_failed",
                "component": "blockchain_connector",
                "error": str(e)
            })
            
            return False

    async def start(self) -> bool:
        """Start the blockchain connector.
        
        Returns:
            bool: True if started successfully
        """
        if not self.is_initialized:
            success = await self.initialize()
            if not success:
                return False
                
        # Connect to the blockchain network
        connected = await self.connect()
        if connected:
            self.is_running = True
            
            # Publish started status
            await self.publish_event("blockchain.status", {
                "status": "running",
                "component": "blockchain_connector",
                "network": await self._get_network_name()
            })
            
            return True
        else:
            await self.publish_event("blockchain.status", {
                "status": "start_failed",
                "component": "blockchain_connector",
                "error": "Failed to connect to blockchain"
            })
            
            return False
            
    async def connect(self) -> bool:
        """Connect to the blockchain network.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if self._web3 and not self._mock_mode:
            # Already connected
            return True
            
        # Start connection process
        await self.publish_event("blockchain.status", {
            "status": "connecting",
            "component": "blockchain_connector",
            "endpoint": self.endpoint
        })
        
        # Try to connect with retries
        retries = 0
        while retries <= self.max_retries:
            try:
                if self.endpoint.startswith("ws"):
                    # WebSocket connection
                    logger.info(f"Connecting to {self.endpoint} via WebSocket")
                    provider = CustomWebsocketProvider(self.endpoint)
                    self._web3 = AsyncWeb3(provider)
                else:
                    # HTTP connection
                    logger.info(f"Connecting to {self.endpoint} via HTTP")
                    provider = HTTPProvider(self.endpoint)
                    self._web3 = AsyncWeb3(provider)
                
                # Check connection
                block_number = await self._web3.eth.block_number
                logger.info(f"Connected to blockchain, current block: {block_number}")
                
                # Add middleware for PoA chains if available
                if geth_poa_middleware:
                    self._web3.middleware_onion.inject(geth_poa_middleware, layer=0)
                
                # Get network name
                self.network_name = await self._get_network_name()
                
                # Publish connected status
                await self.publish_event("blockchain.status", {
                    "status": "connected",
                    "component": "blockchain_connector",
                    "network": self.network_name,
                    "block_number": block_number
                })
                
                self._mock_mode = False
                return True
                
            except Exception as e:
                retries += 1
                logger.error(f"Connection attempt {retries} failed: {e}")
                
                if retries > self.max_retries:
                    if self._mock_mode_allowed:
                        logger.warning("All connection attempts failed, switching to mock mode")
                        self._mock_mode = True
                        self._web3 = Web3()  # Use a standard Web3 instance for mock mode
                        
                        # Publish mock mode status
                        await self.publish_event("blockchain.status", {
                            "status": "mock_mode",
                            "component": "blockchain_connector",
                            "network": "Mock Network"
                        })
                        
                        return True
                    else:
                        logger.error("All connection attempts failed and mock mode is not allowed")
                        
                        # Publish connection failure status
                        await self.publish_event("blockchain.status", {
                            "status": "connection_failed",
                            "component": "blockchain_connector",
                            "error": f"Failed to connect after {retries} attempts"
                        })
                        
                        return False
                
                # Try the next endpoint if available
                if len(self.endpoints) > 1:
                    current_index = self.endpoints.index(self.endpoint)
                    next_index = (current_index + 1) % len(self.endpoints)
                    self.endpoint = self.endpoints[next_index]
                    logger.info(f"Trying next endpoint: {self.endpoint}")
                
                # Exponential backoff
                delay = min(self.retry_delay * (2 ** (retries - 1)), self.max_retry_delay)
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
        
        return False

    async def disconnect(self) -> bool:
        """Disconnect from the blockchain network.
        
        Returns:
            bool: True if disconnected successfully
        """
        if not self._web3:
            # Already disconnected
            return True
            
        try:
            # If we have a WebSocket provider, we need to disconnect it
            if self.endpoint.startswith("ws") and hasattr(self._web3.provider, "disconnect"):
                await self._web3.provider.disconnect()
            
            self._web3 = None
            self._mock_mode = False
            self.is_running = False
            
            # Publish disconnected status
            await self.publish_event("blockchain.status", {
                "status": "disconnected",
                "component": "blockchain_connector"
            })
            
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from blockchain: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the blockchain connector.
        
        Returns:
            bool: True if stopped successfully
        """
        if not self.is_running:
            return True
            
        await self.disconnect()
        self.is_running = False
        
        # Publish stopped status
        await self.publish_event("blockchain.status", {
            "status": "stopped",
            "component": "blockchain_connector"
        })
        
        return True

    async def send_transaction_safely(self, web3_instance, tx_dict) -> str:
        """Send transaction with robust error handling for all web3 versions.
        
        Args:
            web3_instance: Web3 instance to use
            tx_dict: Transaction dictionary
            
        Returns:
            Transaction hash as string
            
        Raises:
            Exception: If transaction fails
        """
        if self._mock_mode:
            # Generate a random transaction hash for mock mode
            mock_tx_hash = "0x" + "".join([hex(secrets.randbelow(16))[2:] for _ in range(64)])
            logger.info(f"[MOCK] Sending transaction: {mock_tx_hash}")
            return mock_tx_hash
        
        try:
            # Convert to bytes if needed
            if "data" in tx_dict and isinstance(tx_dict["data"], str) and tx_dict["data"].startswith("0x"):
                tx_dict["data"] = bytes.fromhex(tx_dict["data"][2:])
                
            # Send the transaction
            tx_hash = await web3_instance.eth.send_transaction(tx_dict)
            
            # Different web3 versions return different types
            if isinstance(tx_hash, bytes):
                # Convert bytes to hex string
                return "0x" + tx_hash.hex()
            elif hasattr(tx_hash, "hex"):
                # HexBytes object
                return tx_hash.hex()
            else:
                # Already a string
                return tx_hash
        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            raise

    # Event Handlers
    
    async def handle_connect_request(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle a blockchain connection request.
        
        Args:
            event_type: Event type
            data: Event data
        """
        try:
            # Check if we need to update the endpoint
            if "endpoint" in data:
                self.endpoint = data["endpoint"]
                
            # Connect to the blockchain
            connected = await self.connect()
            
            # Publish result
            result_event = "blockchain.connect.success" if connected else "blockchain.connect.error"
            await self.publish_event(result_event, {
                "success": connected,
                "network": await self._get_network_name() if connected else None,
                "error": None if connected else "Failed to connect to blockchain"
            })
        except Exception as e:
            logger.error(f"Error handling connect request: {e}")
            await self.publish_event("blockchain.connect.error", {
                "success": False,
                "error": str(e)
            })

    async def handle_disconnect_request(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle a blockchain disconnection request.
        
        Args:
            event_type: Event type
            data: Event data
        """
        try:
            # Disconnect from the blockchain
            disconnected = await self.disconnect()
            
            # Publish result
            result_event = "blockchain.disconnect.success" if disconnected else "blockchain.disconnect.error"
            await self.publish_event(result_event, {
                "success": disconnected,
                "error": None if disconnected else "Failed to disconnect from blockchain"
            })
        except Exception as e:
            logger.error(f"Error handling disconnect request: {e}")
            await self.publish_event("blockchain.disconnect.error", {
                "success": False,
                "error": str(e)
            })

    async def handle_config_update(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle a configuration update request.
        
        Args:
            event_type: Event type
            data: Event data
        """
        try:
            # Update configuration
            if "config" in data:
                self.config.update(data["config"])
                
                # Check if we need to update endpoints
                if "endpoints" in data["config"]:
                    self.endpoints = data["config"]["endpoints"]
                    
                    # Use the first endpoint if current one is not in the list
                    if self.endpoint not in self.endpoints and self.endpoints:
                        self.endpoint = self.endpoints[0]
                        
                # Check if we need to update mock mode settings
                if "allow_mock_mode" in data["config"]:
                    self._mock_mode_allowed = data["config"]["allow_mock_mode"]
                    
                # Publish result
                await self.publish_event("blockchain.config.updated", {
                    "success": True
                })
        except Exception as e:
            logger.error(f"Error handling config update: {e}")
            await self.publish_event("blockchain.config.error", {
                "success": False,
                "error": str(e)
            })
            
    async def handle_transaction(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle a transaction request.
        
        Args:
            event_type: Event type
            data: Event data with transaction details
        """
        if not self._web3:
            await self.publish_event("blockchain.transaction.error", {
                "success": False,
                "error": "Not connected to blockchain"
            })
            return
            
        try:
            # Extract transaction data
            tx_dict = data.get("transaction", {})
            
            # Ensure we have the necessary fields
            if "from" not in tx_dict:
                raise ValueError("Transaction missing 'from' field")
                
            # Send the transaction
            tx_hash = await self.send_transaction_safely(self._web3, tx_dict)
            
            # Publish result
            await self.publish_event("blockchain.transaction.success", {
                "success": True,
                "tx_hash": tx_hash,
                "network": await self._get_network_name()
            })
        except Exception as e:
            logger.error(f"Error handling transaction: {e}")
            await self.publish_event("blockchain.transaction.error", {
                "success": False,
                "error": str(e)
            })

    async def handle_balance_request(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle a balance request.
        
        Args:
            event_type: Event type
            data: Event data with address to check
        """
        if not self._web3:
            await self.publish_event("blockchain.balance.error", {
                "success": False,
                "error": "Not connected to blockchain"
            })
            return
            
        try:
            # Extract the address
            address = data.get("address")
            if not address:
                raise ValueError("Missing address in balance request")
                
            # Convert to checksum address
            try:
                address = self._web3.to_checksum_address(address)
            except Exception as e:
                raise ValueError(f"Invalid Ethereum address: {e}")
                
            if self._mock_mode:
                # Generate a random balance for mock mode
                wei_balance = 1000000000000000000 * (1 + secrets.randbelow(100))  # 1-100 ETH
                eth_balance = wei_balance / 1000000000000000000
                
                await self.publish_event("blockchain.balance.success", {
                    "success": True,
                    "address": address,
                    "balance_wei": wei_balance,
                    "balance_eth": eth_balance,
                    "network": "Mock Network",
                    "mock": True
                })
                return
                
            # Get the balance
            wei_balance = await self._web3.eth.get_balance(address)
            
            # Convert to ETH
            eth_balance = wei_balance / 1000000000000000000
            
            # Publish result
            await self.publish_event("blockchain.balance.success", {
                "success": True,
                "address": address,
                "balance_wei": wei_balance,
                "balance_eth": eth_balance,
                "network": await self._get_network_name()
            })
        except Exception as e:
            logger.error(f"Error handling balance request: {e}")
            await self.publish_event("blockchain.balance.error", {
                "success": False,
                "error": str(e),
                "address": data.get("address")
            })
            
    async def handle_shutdown(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle a system shutdown event.
        
        Args:
            event_type: Event type
            data: Event data
        """
        logger.info("Received shutdown event, stopping blockchain connector")
        await self.stop()
    def __init__(self, endpoint_uri, *args, **kwargs):
        """Initialize the WebsocketProvider.
        
        Args:
            endpoint_uri: WebSocket endpoint URI
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        self.endpoint_uri = endpoint_uri
        self.connected = False
        self._ws = None
        self._real_provider = None
        self.logger = logging.getLogger("KingdomAI.WebsocketProvider")
        
        # Only try to use real implementation if web3 is available
        if _has_web3() and OriginalWebsocketProvider is not None:
            try:
                self._initialize_real_provider(endpoint_uri, *args, **kwargs)
            except Exception as e:
                self.logger.error(f"Failed to initialize real provider: {e}")
                self._real_provider = None
        else:
            logger.warning("Web3 WebsocketProvider not available, using mock mode")
            self._real_provider = None
    
    def _initialize_real_provider(self, endpoint_uri, *args, **kwargs):
        """Initialize the real WebsocketProvider if available.
        
        Args:
            endpoint_uri: WebSocket endpoint URI
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        """
        try:
            self._real_provider = OriginalWebsocketProvider(endpoint_uri, *args, **kwargs)
            self.connected = True
        except Exception as e:
            self.logger.error(f"Error initializing websocket provider: {e}")
            self._real_provider = None
    
    def make_request(self, method, params):
        """Make a request to the websocket provider with fallback.
        
        Args:
            method: RPC method
            params: RPC parameters
            
        Returns:
            Response from provider or mock response
        """
        if self._real_provider:
            try:
                return self._real_provider.make_request(method, params)
            except Exception as e:
                self.logger.error(f"Error making request: {e}, using fallback")
                return self._fallback_result_for_method(method, params)
        else:
            return self._fallback_result_for_method(method, params)
    
    def _fallback_result_for_method(self, method, params):
        """Attempt a real RPC call as fallback, or return an honest error.
        
        Args:
            method: RPC method
            params: RPC parameters
            
        Returns:
            Real RPC response or error indicating data unavailable
        """
        import urllib.request
        import json
        
        rpc_url = getattr(self, 'endpoint_uri', None) or "https://rpc.ankr.com/eth"
        rpc_request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params if params else [],
            "id": 1
        }
        
        try:
            req_data = json.dumps(rpc_request).encode('utf-8')
            request = urllib.request.Request(
                rpc_url,
                data=req_data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if "error" in result:
                    self.logger.error(f"RPC error for {method}: {result['error']}")
                    return {"error": result["error"]}
                return result
        except Exception as e:
            self.logger.error(f"Fallback RPC call failed for {method}: {e}")
            return {"error": {"code": -32603, "message": f"Data unavailable: {e}"}}

    def is_connected(self):
        """Check if connected to WebSocket provider.
        
        Returns:
            bool: True if connected, False otherwise
        """
        if self._real_provider and hasattr(self._real_provider, "is_connected"):
            try:
                return self._real_provider.is_connected()
            except Exception:
                return False
        return self.connected

    def disconnect(self):
        """Disconnect from WebSocket provider."""
        if self._real_provider and hasattr(self._real_provider, "disconnect"):
            try:
                self._real_provider.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting: {e}")
        
        self.connected = False

# Rename our universal WebsocketProvider to avoid conflicts
# This is the official provider that will be used throughout the system
_WebsocketProvider = WebsocketProvider
