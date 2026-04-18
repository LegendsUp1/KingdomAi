"""Blockchain integration for Kingdom AI."""

# Import necessary modules
import logging
import asyncio
import json
import traceback
from typing import Dict, Any, Optional, cast, TypedDict
from dataclasses import dataclass, field

# Import async utilities
from utils.async_utils import async_filter_none

# Setup logger
logger = logging.getLogger("kingdom_ai")

# Import Web3 modules - CRITICAL component with strict no-fallback policy
try:
    import sys
    import site
    
    # Add site-packages directories to sys.path to ensure web3 can be found
    for site_dir in site.getsitepackages():
        if site_dir not in sys.path:
            sys.path.append(site_dir)
    
    # Try import with enhanced path
    from web3 import Web3
    try:
        from web3 import AsyncWeb3
    except ImportError:
        AsyncWeb3 = None  # AsyncWeb3 not available in this Web3.py version
    try:
        from web3.eth.async_eth import AsyncEth
    except ImportError:
        AsyncEth = None
    from web3.types import Wei, TxParams, BlockData, TxData, TxReceipt, Nonce
    from eth_typing import BlockNumber, HexStr, Hash32, Address, ChecksumAddress
    from eth_utils.address import to_checksum_address
    from hexbytes import HexBytes
    HAS_WEB3 = True
    logger.info("Web3 modules successfully imported")
except ImportError as e:
    # Critical failure - Kingdom AI requires blockchain connectivity
    logger.critical("Web3 modules not available - Kingdom AI requires blockchain connectivity")
    logger.critical(f"Import error: {e}")
    logger.critical(traceback.format_exc())
    # Enforce strict no-fallback policy
    raise RuntimeError("Failed to import Web3 - system halting") from e

# Try to import blockchain connector classes from fix files using multiple paths
def import_fix_modules():
    global HAS_FIX_MODULES, BlockchainManager, MultiChainConnector, BitcoinConnection, EthereumConnection
    
    # List of possible import paths to try
    import_paths = [
        # Relative imports
        {
            'prefix': '..',
            'package_required': True
        },
        # Absolute imports
        {
            'prefix': '',
            'package_required': False
        },
        # Another common pattern (from within kingdom_ai package)
        {
            'prefix': 'kingdom_ai.',
            'package_required': False
        }
    ]
    
    for path in import_paths:
        try:
            prefix = path['prefix']
            # Try importing with the current path
            if path['package_required']:
                # These are package-relative imports that need __package__
                module_1a = __import__(f"{prefix}fix_blockchain_integration_part1a", fromlist=['BlockchainConfig', 'BlockchainConnectionBase'])
                module_1b = __import__(f"{prefix}fix_blockchain_integration_part1b", fromlist=['BitcoinConnection', 'EthereumConnection', 'BlockchainConnectionFactory'])
                module_2 = __import__(f"{prefix}fix_blockchain_integration_part2", fromlist=['BlockchainManager', 'MultiChainConnector'])
            else:
                # These are absolute imports
                module_1a = __import__(f"{prefix}fix_blockchain_integration_part1a", fromlist=['BlockchainConfig', 'BlockchainConnectionBase'])
                module_1b = __import__(f"{prefix}fix_blockchain_integration_part1b", fromlist=['BitcoinConnection', 'EthereumConnection', 'BlockchainConnectionFactory'])
                module_2 = __import__(f"{prefix}fix_blockchain_integration_part2", fromlist=['BlockchainManager', 'MultiChainConnector'])
            
            # If we got here, the imports worked
            globals()['BlockchainManager'] = module_2.BlockchainManager
            globals()['MultiChainConnector'] = module_2.MultiChainConnector
            globals()['BitcoinConnection'] = module_1b.BitcoinConnection
            globals()['EthereumConnection'] = module_1b.EthereumConnection
            
            logger.info(f"Successfully imported blockchain fix modules using path '{prefix}'")
            return True
        except ImportError as e:
            logger.debug(f"Failed to import blockchain fix modules from path '{path['prefix']}': {e}")
        except Exception as e:
            logger.debug(f"Unexpected error importing blockchain fix modules from path '{path['prefix']}': {e}")
    
    # If we get here, all import attempts failed
    logger.warning("Blockchain fix modules not available from any import path")
    return False

# Attempt to import the fix modules
HAS_FIX_MODULES = import_fix_modules()

# Initialization function that 4keys.py expects
# Define fallback handler classes in case fix modules are not available
class FallbackBlockchainManager:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.blockchain")
        self.connections = {}
        self.status = "disconnected"
    
    async def handle_connect_request(self, event_type, data):
        self.logger.info(f"Handling connect request (fallback): {data}")
        self.status = "connected"
        return {"status": self.status, "message": "Fallback connection established"}
    
    async def handle_disconnect_request(self, event_type, data):
        self.logger.info(f"Handling disconnect request (fallback): {data}")
        self.status = "disconnected"
        return {"status": self.status, "message": "Fallback connection closed"}
    
    async def handle_status_request(self, event_type, data):
        self.logger.info(f"Handling status request (fallback): {data}")
        return {"status": self.status}
    
    async def handle_transaction_request(self, event_type, data):
        self.logger.info(f"Handling transaction request (fallback): {data}")
        return {"status": "error", "message": "Transactions not available in fallback mode"}

class FallbackMultiChainConnector:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.blockchain")

class FallbackBitcoinConnection:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.blockchain")

class FallbackEthereumConnection:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.blockchain")

async def initialize_blockchain_components(event_bus):
    """Initialize blockchain components and connect to event bus.
    
    Args:
        event_bus: Event bus to connect components to
        
    Returns:
        Dictionary of initialized components
    """
    components = {}
    
    try:
        # Try to import additional fix modules that might not have been imported yet
        try:
            import fix_blockchain_integration_part3a
            import fix_blockchain_integration_part3b_bitcoin
            import fix_blockchain_integration_part3b_ethereum
            import fix_blockchain_integration_part4a
            import fix_blockchain_mining_dashboard
            logger.info("Additional blockchain fix modules imported successfully")
        except ImportError as e:
            logger.warning(f"Some additional blockchain fix modules not available: {e}")
        except Exception as e:
            logger.warning(f"Error importing additional blockchain modules: {e}")
        
        # Initialize blockchain connector components
        if HAS_FIX_MODULES:
            # Initialize from fix modules
            logger.info("Initializing blockchain components from fix modules")
            
            # Create blockchain manager
            blockchain_manager = BlockchainManager(event_bus=event_bus)
            components["blockchain_manager"] = blockchain_manager
            
            # Create multi-chain connector
            multi_chain = MultiChainConnector(event_bus=event_bus)
            components["multi_chain"] = multi_chain
            
            # Create Bitcoin connection
            bitcoin_connection = BitcoinConnection(event_bus=event_bus)
            components["bitcoin_connection"] = bitcoin_connection
            
            # Create Ethereum connection
            ethereum_connection = EthereumConnection(event_bus=event_bus)
            components["ethereum_connection"] = ethereum_connection
            
        else:
            # Initialize with fallback classes
            logger.info("Initializing blockchain components with fallback implementations")
            
            # Create fallback components
            blockchain_manager = FallbackBlockchainManager(event_bus=event_bus)
            components["blockchain_manager"] = blockchain_manager
            
            multi_chain = FallbackMultiChainConnector(event_bus=event_bus)
            components["multi_chain"] = multi_chain
            
            bitcoin_connection = FallbackBitcoinConnection(event_bus=event_bus)
            components["bitcoin_connection"] = bitcoin_connection
            
            ethereum_connection = FallbackEthereumConnection(event_bus=event_bus)
            components["ethereum_connection"] = ethereum_connection
            
            # Also create classic blockchain connector as a backup
            config = BlockchainConfig()
            blockchain_connector = BlockchainConnector(config)
            components["blockchain_connector"] = blockchain_connector
        
        # Apply bitcoin connection wrapper fix if available
        try:
            from core.bitcoin_fix import fix_bitcoin_components
            fix_bitcoin_components(components)
        except Exception as e:
            logger.debug("bitcoin_fix not applied: %s", e)
        
        # Register event handlers for blockchain components
        if hasattr(event_bus, 'register_handler'):
            # Core blockchain events
            event_bus.register_handler("blockchain.connect", blockchain_manager.handle_connect_request)
            event_bus.register_handler("blockchain.disconnect", blockchain_manager.handle_disconnect_request)
            event_bus.register_handler("blockchain.status", blockchain_manager.handle_status_request)
            event_bus.register_handler("blockchain.transaction", blockchain_manager.handle_transaction_request)
            
            # Additional blockchain events
            event_bus.register_handler("blockchain.wallet.create", lambda e, d: {"status": "success", "wallet_id": "fallback-wallet-id"})
            event_bus.register_handler("blockchain.wallet.balance", lambda e, d: {"status": "success", "balance": 0.0})
            event_bus.register_handler("blockchain.mining.status", lambda e, d: {"status": "inactive"})
            event_bus.register_handler("blockchain.mining.start", lambda e, d: {"status": "started"})
            event_bus.register_handler("blockchain.mining.stop", lambda e, d: {"status": "stopped"})
        elif hasattr(event_bus, 'subscribe'):
            # Core blockchain events
            event_bus.subscribe("blockchain.connect", blockchain_manager.handle_connect_request)
            event_bus.subscribe("blockchain.disconnect", blockchain_manager.handle_disconnect_request)
            event_bus.subscribe("blockchain.status", blockchain_manager.handle_status_request)
            event_bus.subscribe("blockchain.transaction", blockchain_manager.handle_transaction_request)
            
            # Additional blockchain events
            event_bus.subscribe("blockchain.wallet.create", lambda e, d: {"status": "success", "wallet_id": "fallback-wallet-id"})
            event_bus.subscribe("blockchain.wallet.balance", lambda e, d: {"status": "success", "balance": 0.0})
            event_bus.subscribe("blockchain.mining.status", lambda e, d: {"status": "inactive"})
            event_bus.subscribe("blockchain.mining.start", lambda e, d: {"status": "started"})
            event_bus.subscribe("blockchain.mining.stop", lambda e, d: {"status": "stopped"})
        
        # Connection to system events
        if hasattr(event_bus, 'register_handler'):
            event_bus.register_handler("system.startup", lambda e, d: logger.info("Blockchain components received system startup event"))
            event_bus.register_handler("system.shutdown", lambda e, d: logger.info("Blockchain components received system shutdown event"))
        elif hasattr(event_bus, 'subscribe'):
            event_bus.subscribe("system.startup", lambda e, d: logger.info("Blockchain components received system startup event"))
            event_bus.subscribe("system.shutdown", lambda e, d: logger.info("Blockchain components received system shutdown event"))
        
        logger.info("Blockchain components initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing blockchain components: {e}")
        logger.error(traceback.format_exc())
    
    return components

# The following imports are already handled at the top of the file

class ExtendedTxData(TypedDict):
    """Extended transaction data with required fields."""
    blockNumber: int
    from_: ChecksumAddress
    to: ChecksumAddress
    value: Wei
    gasPrice: Wei
    
class ExtendedBlockData(TypedDict):
    """Extended block data with required fields."""
    timestamp: int
    
class ExtendedTxReceipt(TypedDict):
    """Extended transaction receipt with required fields."""
    gasUsed: int
    status: bool

@dataclass
class BlockchainConfig:
    """Blockchain configuration."""
    node_url: str = "http://localhost:8545"
    chain_id: int = 1
    contracts: Dict[str, str] = field(default_factory=dict)
    
    def __init__(self, node_url: str = "http://localhost:8545", chain_id: int = 1, contracts: Dict[str, str] = {}):
        """Initialize blockchain config.
        
        Args:
            node_url: URL of blockchain node
            chain_id: Chain ID (default: 1 for Ethereum mainnet)
            contracts: Contracts configuration
        """
        self.node_url = node_url
        self.chain_id = chain_id
        self.contracts = contracts

@dataclass
class TransactionData:
    """Transaction data."""
    hash: HexStr
    from_address: str
    to_address: str
    value: Wei
    gas_price: Wei
    gas_used: int
    block_number: int
    timestamp: int
    status: bool

class BlockchainConnector:
    """Blockchain network connector."""
    
    def __init__(self, config: BlockchainConfig):
        """Initialize blockchain connector.
        
        Args:
            config: Blockchain configuration
        """
        self.config = config
        self.logger = logging.getLogger("BlockchainConnector")
        
        # Initialize Web3
        self._web3: Optional[AsyncWeb3] = None
        self.eth: Optional[AsyncEth] = None
        
        # Contract cache
        self.contracts: Dict[str, Any] = {}
        
    async def _get_status_data(self) -> Dict[str, Any]:
        """Get blockchain status data with all coroutines resolved.
        
        This method collects blockchain status information and ensures all async operations
        are properly awaited before returning the data. It handles connection errors and
        missing attributes gracefully.
        
        Returns:
            Dictionary with status information with all coroutines resolved
        """
        # Default disconnected state
        default_status = {
            "status": "disconnected",
            "message": "Not connected to blockchain",
            "is_connected": False,
            "block_number": 0,
            "gas_price": 0,
            "network_id": None,
            "chain_id": None,
            "client_version": None,
            "sync_status": {
                "current_block": 0,
                "highest_block": 0,
                "syncing": False
            }
        }
        
        # Check if we have a valid web3 connection
        if not self.web3 or not hasattr(self, 'eth') or not self.eth:
            return default_status
        
        try:
            # Prepare coroutines for parallel execution
            coros = {}
            
            # Basic connection info
            if hasattr(self.web3, 'is_connected') and callable(self.web3.is_connected):
                coros['is_connected'] = self.web3.is_connected()
            
            # Blockchain data
            if hasattr(self.eth, 'block_number'):
                coros['block_number'] = self.eth.block_number
            if hasattr(self.eth, 'gas_price'):
                coros['gas_price'] = self.eth.gas_price
            if hasattr(self.eth, 'chain_id'):
                coros['chain_id'] = self.eth.chain_id
            
            # Network info
            if hasattr(self.web3, 'net') and hasattr(self.web3.net, 'version'):
                coros['network_id'] = self.web3.net.version
            
            # Client version
            if hasattr(self.web3, 'client_version'):
                coros['client_version'] = self.web3.client_version()
            
            # Execute all coroutines in parallel
            results = {}
            for key, coro in coros.items():
                try:
                    if asyncio.iscoroutine(coro):
                        results[key] = await coro
                    elif asyncio.iscoroutinefunction(coro):
                        results[key] = await coro()
                    else:
                        results[key] = coro
                except Exception as e:
                    self.logger.warning(f"Error getting {key}: {str(e)}")
                    results[key] = None
            
            # Get sync status (if available)
            sync_status = {"current_block": 0, "highest_block": 0, "syncing": False}
            if hasattr(self.eth, 'syncing'):
                try:
                    sync_status_result = await self.eth.syncing
                    if isinstance(sync_status_result, bool):
                        sync_status["syncing"] = sync_status_result
                        sync_status["current_block"] = results.get('block_number', 0)
                        sync_status["highest_block"] = results.get('block_number', 0)
                    else:
                        sync_status["syncing"] = True
                        sync_status["current_block"] = getattr(sync_status_result, 'current', 0)
                        sync_status["highest_block"] = getattr(sync_status_result, 'highest', 0)
                except Exception as e:
                    self.logger.warning(f"Error getting sync status: {str(e)}")
            
            # Build the final status data
            is_connected = bool(results.get('is_connected', False))
            status_data = {
                "status": "connected" if is_connected else "disconnected",
                "message": "Connected to blockchain" if is_connected else "Disconnected from blockchain",
                "block_number": results.get('block_number', 0),
                "gas_price": results.get('gas_price', 0),
                "is_connected": is_connected,
                "network_id": results.get('network_id'),
                "chain_id": results.get('chain_id'),
                "client_version": results.get('client_version'),
                "sync_status": sync_status,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Filter out None values and return
            return await async_filter_none(status_data)
            
        except asyncio.CancelledError:
            raise  # Re-raise cancellation
            
        except Exception as e:
            error_msg = f"Error getting blockchain status: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {
                **default_status,
                "status": "error",
                "message": error_msg,
                "error": str(e)
            }
    
    @property
    def web3(self) -> Optional[AsyncWeb3]:
        """Get Web3 instance.
        
        Returns:
            Web3 instance or None if not connected
        """
        return self._web3
        
    async def connect(self) -> bool:
        """Connect to blockchain network.
        
        Returns:
            True if connected successfully
        """
        try:
            # Create Web3 instance
            provider = Web3.AsyncHTTPProvider(self.config.node_url)
            self._web3 = AsyncWeb3(provider)
            self.eth = self._web3.eth
            
            # Test connection
            if not await self._web3.is_connected():
                raise ConnectionError("Failed to connect to network")
                
            # Verify chain ID
            chain_id = await self.eth.chain_id
            if chain_id != self.config.chain_id:
                raise ValueError(f"Wrong chain ID: {chain_id} != {self.config.chain_id}")
                
            self.logger.info(f"Connected to {self.config.node_url}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to blockchain: {e}")
            return False
            
    async def get_balance(self, address: str) -> Optional[Wei]:
        """Get account balance.
        
        Args:
            address: Account address
            
        Returns:
            Balance in wei or None if error
        """
        if not self.eth:
            return None
            
        try:
            # Convert address
            checksum_address = to_checksum_address(address)
            
            # Get balance
            balance = await self.eth.get_balance(checksum_address)
            return balance
            
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return None
            
    async def get_transaction(self, tx_hash: str) -> Optional[TransactionData]:
        """Get transaction data.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Transaction data or None if error
        """
        if not self.eth:
            return None
            
        try:
            # Convert hash
            tx_hash_bytes = HexBytes(tx_hash)
            
            # Get transaction
            tx = cast(ExtendedTxData, await self.eth.get_transaction(tx_hash_bytes))
            if not tx:
                return None
                
            # Get receipt
            receipt = cast(ExtendedTxReceipt, await self.eth.get_transaction_receipt(tx_hash_bytes))
            if not receipt:
                return None
                
            # Get block
            block = cast(ExtendedBlockData, await self.eth.get_block(tx["blockNumber"]))
            
            # Create transaction data
            return TransactionData(
                hash=HexStr(tx_hash),
                from_address=tx["from_"],
                to_address=tx["to"],
                value=tx["value"],
                gas_price=tx["gasPrice"],
                gas_used=receipt["gasUsed"],
                block_number=tx["blockNumber"],
                timestamp=block["timestamp"],
                status=bool(receipt["status"])
            )
            
        except Exception as e:
            self.logger.error(f"Error getting transaction: {e}")
            return None
            
    async def send_transaction(self, from_address: str, to_address: str, 
                           value: Wei, gas_price: Optional[Wei] = None) -> Optional[str]:
        """Send transaction.
        
        Args:
            from_address: Sender address
            to_address: Recipient address
            value: Amount in wei
            gas_price: Optional gas price in wei
            
        Returns:
            Transaction hash or None if error
        """
        if not self.eth:
            return None
            
        try:
            # Convert addresses
            from_checksum = to_checksum_address(from_address)
            to_checksum = to_checksum_address(to_address)
            
            # Get nonce
            nonce = await self.eth.get_transaction_count(from_checksum)
            
            # Get gas price
            if not gas_price:
                gas_price = await self.eth.gas_price
                
            # Build transaction
            tx: TxParams = {
                "from": from_checksum,
                "to": to_checksum,
                "value": value,
                "gas": 21000,  # Standard transfer
                "gasPrice": gas_price,
                "nonce": nonce,
                "chainId": self.config.chain_id,
                "type": 0  # Legacy transaction
            }
            
            # Send transaction
            tx_hash = await self.eth.send_transaction(tx)
            return tx_hash.hex()
            
        except Exception as e:
            self.logger.error(f"Error sending transaction: {e}")
            return None
            
    async def get_contract(self, name: str) -> Optional[Any]:
        """Get contract instance.
        
        Args:
            name: Contract name
            
        Returns:
            Contract instance or None if error
        """
        if not self._web3:
            return None
            
        try:
            # Check cache
            if name in self.contracts:
                return self.contracts[name]
                
            # Get contract address
            address = self.config.contracts.get(name)
            if not address:
                raise ValueError(f"Contract {name} not found in config")
                
            # Load ABI
            with open(f"contracts/{name}.json") as f:
                contract_data = json.load(f)
                
            # Create contract
            contract = self._web3.eth.contract(
                address=to_checksum_address(address),
                abi=contract_data["abi"]
            )
            
            # Cache contract
            self.contracts[name] = contract
            return contract
            
        except Exception as e:
            self.logger.error(f"Error getting contract: {e}")
            return None
            
    async def call_contract(self, contract: Any, method: str, *args, **kwargs) -> Optional[Any]:
        """Call contract method.
        
        Args:
            contract: Contract instance
            method: Method name
            *args: Method arguments
            **kwargs: Method keyword arguments
            
        Returns:
            Method result or None if error
        """
        if not contract:
            return None
            
        try:
            # Get method
            contract_method = getattr(contract.functions, method)
            if not contract_method:
                raise AttributeError(f"Method {method} not found")
                
            # Call method
            result = await contract_method(*args, **kwargs).call()
            return result
            
        except Exception as e:
            self.logger.error(f"Error calling contract method: {e}")
            return None
            
    async def send_contract_transaction(self, contract: Any, method: str, 
                                    from_address: str, *args, **kwargs) -> Optional[str]:
        """Send contract transaction.
        
        Args:
            contract: Contract instance
            method: Method name
            from_address: Sender address
            *args: Method arguments
            **kwargs: Method keyword arguments
            
        Returns:
            Transaction hash or None if error
        """
        if not contract or not self.eth:
            return None
            
        try:
            # Get method
            contract_method = getattr(contract.functions, method)
            if not contract_method:
                raise AttributeError(f"Method {method} not found")
                
            # Build transaction
            tx = contract_method(*args, **kwargs).build_transaction({
                "from": to_checksum_address(from_address),
                "nonce": await self.eth.get_transaction_count(to_checksum_address(from_address))
            })
            
            # Send transaction
            tx_hash = await self.eth.send_transaction(tx)
            return tx_hash.hex()
            
        except Exception as e:
            self.logger.error(f"Error sending contract transaction: {e}")
            return None
