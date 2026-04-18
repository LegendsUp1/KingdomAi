"""Blockchain explorer functionality for Kingdom AI blockchain integration."""

import logging
import aiohttp
from typing import Dict, Any, Optional, Union

# Setup logger
logger = logging.getLogger("core.blockchain.explorer_browser")

# Import base component
from core.base_component import BaseComponent


# Define fallback classes locally - NO imports from kingdomweb3_v2
class KingdomWeb3:
    """SOTA 2026: Fallback Web3 connector when main implementation unavailable.
    
    Provides minimal Web3 functionality for blockchain explorer operations.
    """
    
    def __init__(self, event_bus=None):
        """Initialize fallback Web3 connector."""
        self.event_bus = event_bus
        self._connected = False
        self._provider_url = None
        self._chain_id = 1  # Default to Ethereum mainnet
        
        # Supported chains
        self._chains = {
            1: {"name": "Ethereum", "rpc": "https://rpc.ankr.com/eth"},
            56: {"name": "BSC", "rpc": "https://bsc-dataseed.binance.org"},
            137: {"name": "Polygon", "rpc": "https://polygon-rpc.com"},
            42161: {"name": "Arbitrum", "rpc": "https://arb1.arbitrum.io/rpc"},
        }
    
    def connect(self, chain_id: int = 1) -> bool:
        """Connect to blockchain.
        
        Args:
            chain_id: Chain ID to connect to
            
        Returns:
            Connection success status
        """
        if chain_id in self._chains:
            self._chain_id = chain_id
            self._provider_url = self._chains[chain_id]["rpc"]
            self._connected = True
            
            if self.event_bus:
                self.event_bus.publish("blockchain.connected", {
                    "chain_id": chain_id,
                    "chain_name": self._chains[chain_id]["name"]
                })
            return True
        return False
    
    def disconnect(self) -> None:
        """Disconnect from blockchain."""
        self._connected = False
        
        if self.event_bus:
            self.event_bus.publish("blockchain.disconnected", {
                "chain_id": self._chain_id
            })
    
    def is_connected(self) -> bool:
        """Check if connected to blockchain."""
        return self._connected
    
    def get_chain_id(self) -> int:
        """Get current chain ID."""
        return self._chain_id
    
    def get_chain_name(self) -> str:
        """Get current chain name."""
        return self._chains.get(self._chain_id, {}).get("name", "Unknown")
    
    def get_balance(self, address: str) -> float:
        """Get address balance from blockchain explorer API."""
        import urllib.request
        import json
        
        try:
            chain_id = self.get_chain_id()
            
            # Use appropriate explorer API based on chain
            if chain_id == 1:  # Ethereum
                api_key = self.api_keys.get(1) or self.api_keys.get("ethereum") or ""
                api_url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
            elif chain_id == 56:  # BSC
                api_key = self.api_keys.get(56) or self.api_keys.get("bsc") or ""
                api_url = f"https://api.bscscan.com/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
            elif chain_id == 137:  # Polygon
                api_key = self.api_keys.get(137) or self.api_keys.get("polygon") or ""
                api_url = f"https://api.polygonscan.com/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
            else:
                # Fallback to RPC
                rpc_url = self._chains.get(chain_id, {}).get("rpc", "https://rpc.ankr.com/eth")
                rpc_request = {
                    "jsonrpc": "2.0",
                    "method": "eth_getBalance",
                    "params": [address, "latest"],
                    "id": 1
                }
                req_data = json.dumps(rpc_request).encode('utf-8')
                request = urllib.request.Request(
                    rpc_url,
                    data=req_data,
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    if "result" in result:
                        wei_balance = int(result["result"], 16)
                        return wei_balance / 1_000_000_000_000_000_000
                return 0.0
            
            request = urllib.request.Request(api_url)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data.get("status") == "1" and "result" in data:
                    wei_balance = int(data["result"])
                    return wei_balance / 1_000_000_000_000_000_000
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get balance from explorer: {e}")
            return 0.0
    
    def get_transaction(self, tx_hash: str) -> dict:
        """Get transaction details from blockchain explorer API."""
        import urllib.request
        import json
        
        try:
            chain_id = self.get_chain_id()
            
            if chain_id == 1:  # Ethereum
                api_key = self.api_keys.get(1) or self.api_keys.get("ethereum") or ""
                api_url = f"https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={api_key}"
            elif chain_id == 56:  # BSC
                api_key = self.api_keys.get(56) or self.api_keys.get("bsc") or ""
                api_url = f"https://api.bscscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={api_key}"
            elif chain_id == 137:  # Polygon
                api_key = self.api_keys.get(137) or self.api_keys.get("polygon") or ""
                api_url = f"https://api.polygonscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={api_key}"
            else:
                return {"hash": tx_hash, "status": "unknown", "error": "Chain not supported"}
            
            request = urllib.request.Request(api_url)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data.get("result"):
                    return data["result"]
            return {"hash": tx_hash, "status": "unknown"}
        except Exception as e:
            logger.error(f"Failed to get transaction from explorer: {e}")
            return {"hash": tx_hash, "status": "error", "error": str(e)}
    
    def get_block(self, block_number: int = None) -> dict:
        """Get block details from blockchain explorer API."""
        import urllib.request
        import json
        
        try:
            chain_id = self.get_chain_id()
            
            if chain_id == 1:  # Ethereum
                api_key = self.api_keys.get(1) or self.api_keys.get("ethereum") or ""
                block_param = hex(block_number) if block_number else "latest"
                api_url = f"https://api.etherscan.io/api?module=proxy&action=eth_getBlockByNumber&tag={block_param}&boolean=true&apikey={api_key}"
            elif chain_id == 56:  # BSC
                api_key = self.api_keys.get(56) or self.api_keys.get("bsc") or ""
                block_param = hex(block_number) if block_number else "latest"
                api_url = f"https://api.bscscan.com/api?module=proxy&action=eth_getBlockByNumber&tag={block_param}&boolean=true&apikey={api_key}"
            elif chain_id == 137:  # Polygon
                api_key = self.api_keys.get(137) or self.api_keys.get("polygon") or ""
                block_param = hex(block_number) if block_number else "latest"
                api_url = f"https://api.polygonscan.com/api?module=proxy&action=eth_getBlockByNumber&tag={block_param}&boolean=true&apikey={api_key}"
            else:
                return {"number": block_number or 0, "transactions": [], "error": "Chain not supported"}
            
            request = urllib.request.Request(api_url)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data.get("result"):
                    return data["result"]
            return {"number": block_number or 0, "transactions": []}
        except Exception as e:
            logger.error(f"Failed to get block from explorer: {e}")
            return {"number": block_number or 0, "transactions": [], "error": str(e)}


class KingdomWeb3Error(Exception):
    """Exception for KingdomWeb3 errors."""
    pass


def get_kingdom_web3(event_bus=None):
    """Get KingdomWeb3 instance."""
    return KingdomWeb3(event_bus)


# Create global kingdom_web3 instance
kingdom_web3 = KingdomWeb3()


class BlockchainExplorer(BaseComponent):
    """Blockchain explorer functionality."""
    
    # Map of chain IDs to explorer base URLs - MAINNET ONLY
    EXPLORERS = {
        1: "https://etherscan.io",
        56: "https://bscscan.com",
        137: "https://polygonscan.com",
        42161: "https://arbiscan.io",
        10: "https://optimistic.etherscan.io",
        # Add more mainnet explorers as needed
        "bitcoin": "https://www.blockchain.com/explorer"
    }
    
    def __init__(self, event_bus=None, config=None):
        """Initialize blockchain explorer.
        
        Args:
            event_bus: Event bus instance
            config: Configuration dictionary
        """
        super().__init__(name="BlockchainExplorer", event_bus=event_bus)
        self.config = config or {}
        
        # Override explorers from config if provided
        if "explorers" in self.config:
            self.EXPLORERS.update(self.config["explorers"])
            
        self.api_keys = self.config.get("explorer_api_keys", {})
        self.session = None
    
    async def initialize(self) -> bool:
        """Initialize blockchain explorer.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Create HTTP session
            self.session = aiohttp.ClientSession()
            
            # Register event handlers
            if self.event_bus:
                self.event_bus.subscribe_sync("blockchain.explorer.get_url", self.handle_get_url)
                self.event_bus.subscribe_sync("blockchain.explorer.get_transaction", self.handle_get_transaction)
                self.event_bus.subscribe_sync("blockchain.explorer.get_address", self.handle_get_address)
                self.event_bus.subscribe_sync("blockchain.explorer.get_block", self.handle_get_block)
                self.event_bus.subscribe_sync("blockchain.explorer.get_contract", self.handle_get_contract)
                self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
            
            logger.info("Blockchain explorer initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing blockchain explorer: {e}")
            return False
    
    def get_explorer_url(self, chain_id_or_name: Union[int, str]) -> Optional[str]:
        """Get explorer base URL for a specific chain.
        
        Args:
            chain_id_or_name: Chain ID or name
            
        Returns:
            Explorer base URL or None if not found
        """
        # Convert chain name to lowercase for consistency if it's a string
        if isinstance(chain_id_or_name, str):
            chain_id_or_name = chain_id_or_name.lower()
            
        return self.EXPLORERS.get(chain_id_or_name)
    
    def get_transaction_url(self, tx_hash: str, chain_id_or_name: Union[int, str]) -> Optional[str]:
        """Get transaction URL for a specific chain.
        
        Args:
            tx_hash: Transaction hash
            chain_id_or_name: Chain ID or name
            
        Returns:
            Transaction URL or None if explorer not found
        """
        explorer_url = self.get_explorer_url(chain_id_or_name)
        if not explorer_url:
            return None
            
        # Bitcoin explorer has a different URL format
        if chain_id_or_name == "bitcoin":
            return f"{explorer_url}/btc/tx/{tx_hash}"
        
        # Ethereum-compatible explorers
        return f"{explorer_url}/tx/{tx_hash}"
    
    def get_address_url(self, address: str, chain_id_or_name: Union[int, str]) -> Optional[str]:
        """Get address URL for a specific chain.
        
        Args:
            address: Address
            chain_id_or_name: Chain ID or name
            
        Returns:
            Address URL or None if explorer not found
        """
        explorer_url = self.get_explorer_url(chain_id_or_name)
        if not explorer_url:
            return None
            
        # Bitcoin explorer has a different URL format
        if chain_id_or_name == "bitcoin":
            return f"{explorer_url}/btc/address/{address}"
        
        # Ethereum-compatible explorers
        return f"{explorer_url}/address/{address}"
    
    def get_block_url(self, block_number: Union[int, str], chain_id_or_name: Union[int, str]) -> Optional[str]:
        """Get block URL for a specific chain.
        
        Args:
            block_number: Block number
            chain_id_or_name: Chain ID or name
            
        Returns:
            Block URL or None if explorer not found
        """
        explorer_url = self.get_explorer_url(chain_id_or_name)
        if not explorer_url:
            return None
            
        # Bitcoin explorer has a different URL format
        if chain_id_or_name == "bitcoin":
            return f"{explorer_url}/btc/block/{block_number}"
        
        # Ethereum-compatible explorers
        return f"{explorer_url}/block/{block_number}"
    
    def get_contract_url(self, address: str, chain_id_or_name: Union[int, str]) -> Optional[str]:
        """Get contract URL for a specific chain.
        
        Args:
            address: Contract address
            chain_id_or_name: Chain ID or name
            
        Returns:
            Contract URL or None if explorer not found
        """
        explorer_url = self.get_explorer_url(chain_id_or_name)
        if not explorer_url:
            return None
        
        # Ethereum-compatible explorers
        return f"{explorer_url}/address/{address}#code"
    
    async def get_transaction_api(self, tx_hash: str, chain_id_or_name: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get transaction information from explorer API.
        
        Args:
            tx_hash: Transaction hash
            chain_id_or_name: Chain ID or name
            
        Returns:
            Transaction information or None if not found
        """
        # Only supported for Ethereum-compatible chains
        if chain_id_or_name == "bitcoin":
            return None
            
        explorer_url = self.get_explorer_url(chain_id_or_name)
        if not explorer_url or not self.session:
            return None
            
        # Get API key if available
        api_key = None
        if isinstance(chain_id_or_name, int) and chain_id_or_name in self.api_keys:
            api_key = self.api_keys[chain_id_or_name]
        elif isinstance(chain_id_or_name, str) and chain_id_or_name in self.api_keys:
            api_key = self.api_keys[chain_id_or_name]
            
        # Construct API URL
        api_url = f"{explorer_url}/api"
        params = {
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash,
            "apikey": api_key
        }
        
        try:
            # Make API request
            async with self.session.get(api_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "1" or data.get("result"):
                        return data.get("result")
                return None
        except Exception as e:
            logger.error(f"Error getting transaction from API: {e}")
            return None
    
    async def handle_get_url(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get URL request.
        
        Args:
            event_type: Event type
            data: Event data
            
        Returns:
            Response data
        """
        logger.debug(f"Handling get URL request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            type_ = data.get("type", "transaction")
            value = data.get("value")
            
            if not chain:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Chain not provided"
                }
                
            if not value:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Value not provided"
                }
                
            # Get URL based on type
            url = None
            if type_ == "transaction":
                url = self.get_transaction_url(value, chain)
            elif type_ == "address":
                url = self.get_address_url(value, chain)
            elif type_ == "block":
                url = self.get_block_url(value, chain)
            elif type_ == "contract":
                url = self.get_contract_url(value, chain)
            else:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": f"Unsupported type: {type_}"
                }
                
            if not url:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": f"Explorer not found for chain: {chain}"
                }
                
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "url": url,
                "chain": chain,
                "type": type_,
                "value": value
            }
            
            return response
        except Exception as e:
            logger.error(f"Error handling get URL request: {e}")
            
            return {
                "request_id": data.get("request_id"),
                "status": "error",
                "error": str(e)
            }
    
    async def handle_get_transaction(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get transaction request.
        
        Args:
            event_type: Event type
            data: Event data
            
        Returns:
            Response data
        """
        logger.debug(f"Handling get transaction request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            tx_hash = data.get("tx_hash")
            
            if not chain:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Chain not provided"
                }
                
            if not tx_hash:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Transaction hash not provided"
                }
                
            # Get transaction from API
            tx_data = await self.get_transaction_api(tx_hash, chain)
            
            if not tx_data:
                self.logger.warning(f"⚠️ Transaction API failed for hash {tx_hash} on chain {chain}")
                return {
                    "request_id": data.get("request_id"),
                    "status": "partial",
                    "url": url,
                    "chain": chain,
                    "tx_hash": tx_hash
                }
                
            # Build response with data
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "url": self.get_transaction_url(tx_hash, chain),
                "chain": chain,
                "tx_hash": tx_hash,
                "tx_data": tx_data
            }
            
            return response
        except Exception as e:
            logger.error(f"Error handling get transaction request: {e}")
            
            return {
                "request_id": data.get("request_id"),
                "status": "error",
                "error": str(e)
            }
    
    async def handle_get_address(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get address request.
        
        Args:
            event_type: Event type
            data: Event data
            
        Returns:
            Response data
        """
        logger.debug(f"Handling get address request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            address = data.get("address")
            
            if not chain:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Chain not provided"
                }
                
            if not address:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Address not provided"
                }
                
            # Get address URL
            url = self.get_address_url(address, chain)
            
            if not url:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": f"Explorer not found for chain: {chain}"
                }
                
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "url": url,
                "chain": chain,
                "address": address
            }
            
            return response
        except Exception as e:
            logger.error(f"Error handling get address request: {e}")
            
            return {
                "request_id": data.get("request_id"),
                "status": "error",
                "error": str(e)
            }
    
    async def handle_get_block(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get block request.
        
        Args:
            event_type: Event type
            data: Event data
            
        Returns:
            Response data
        """
        logger.debug(f"Handling get block request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            block_number = data.get("block_number")
            
            if not chain:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Chain not provided"
                }
                
            if block_number is None:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Block number not provided"
                }
                
            # Get block URL
            url = self.get_block_url(block_number, chain)
            
            if not url:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": f"Explorer not found for chain: {chain}"
                }
                
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "url": url,
                "chain": chain,
                "block_number": block_number
            }
            
            return response
        except Exception as e:
            logger.error(f"Error handling get block request: {e}")
            
            return {
                "request_id": data.get("request_id"),
                "status": "error",
                "error": str(e)
            }
    
    async def handle_get_contract(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get contract request.
        
        Args:
            event_type: Event type
            data: Event data
            
        Returns:
            Response data
        """
        logger.debug(f"Handling get contract request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            address = data.get("address")
            
            if not chain:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Chain not provided"
                }
                
            if not address:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Address not provided"
                }
                
            # Get contract URL
            url = self.get_contract_url(address, chain)
            
            if not url:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": f"Explorer not found for chain: {chain}"
                }
                
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "url": url,
                "chain": chain,
                "address": address
            }
            
            return response
        except Exception as e:
            logger.error(f"Error handling get contract request: {e}")
            
            return {
                "request_id": data.get("request_id"),
                "status": "error",
                "error": str(e)
            }
    
    async def handle_shutdown(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle system shutdown.
        
        Args:
            event_type: Event type
            data: Event data
        """
        logger.info("Handling shutdown for blockchain explorer")
        
        try:
            # Close HTTP session
            if self.session:
                await self.session.close()
                self.session = None
        except Exception as e:
            logger.error(f"Error during blockchain explorer shutdown: {e}")
