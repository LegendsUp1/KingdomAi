#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Blast blockchain adapter implementation.
Native, no-fallback adapter for Blast network integration.
"""

import os
import json
import time
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
from hexbytes import HexBytes

# Import blockchain base components
from blockchain.base_adapter import BlockchainAdapter, strict_blockchain_operation
from blockchain.exceptions import (
    BlockchainConnectionError,
    TransactionError, 
    ValidationError,
    WalletError
)

# Import Ethereum dependencies (Blast is EVM-compatible)
from web3 import Web3
# Use native middleware implementation - no fallbacks allowed
# Using kingdomweb3_v2 for blockchain connectivity
from kingdomweb3_v2 import rpc_manager, get_network_config
from web3.exceptions import (
    ContractLogicError,
    InvalidAddress,
    TimeExhausted,
    ValidationError as Web3ValidationError
)
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_typing import BlockIdentifier, ChecksumAddress

# Import cryptographic libraries
import eth_utils
from eth_utils import is_hex_address, to_checksum_address, to_hex

# Import logging
import logging
logger = logging.getLogger(__name__)


class BlastAdapter(BlockchainAdapter):
    """Native Blast blockchain adapter.
    
    Implements all required blockchain operations for Blast network
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Blast Mainnet',
            'chain_id': 81457,
            'rpc_endpoint': 'https://rpc.blast.io',
            'explorer_url': 'https://blastscan.io',
            'bridge_url': 'https://bridge.blast.io',
            'native_token': 'ETH',
            'gas_token': 'ETH',
        },
        'testnet': {
            'name': 'Blast Sepolia Testnet',
            'chain_id': 168587773,
            'rpc_endpoint': 'https://sepolia.blast.io',
            'explorer_url': 'https://sepolia.blastscan.io',
            'bridge_url': 'https://bridge.blast.io',
            'native_token': 'ETH',
            'gas_token': 'ETH',
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'ETH': {
            'name': 'Ether',
            'symbol': 'ETH',
            'decimals': 18,
            'min_fee': 0.000021  # Minimum transaction fee in ETH
        },
        'USDB': {
            'name': 'USDB',
            'symbol': 'USDB',
            'decimals': 18,
            'contract': {
                'mainnet': '0x4300000000000000000000000000000000000003',
                'testnet': '0x4200000000000000000000000000000000000022'
            }
        },
        'WETH': {
            'name': 'Wrapped ETH',
            'symbol': 'WETH',
            'decimals': 18,
            'contract': {
                'mainnet': '0x4300000000000000000000000000000000000004',
                'testnet': '0x4200000000000000000000000000000000000023'
            }
        },
        'BLAST': {
            'name': 'Blast Token',
            'symbol': 'BLAST',
            'decimals': 18,
            'contract': {
                'mainnet': '0x5F6AE08B8AeB7078cf2F96AFb089D7c9f51DA47d',
                'testnet': '0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed'
            }
        }
    }
    
    # Yield contracts
    YIELD_CONTRACTS = {
        'mainnet': {
            'eth_yield': '0x4300000000000000000000000000000000000002',
            'usdb_yield': '0x4300000000000000000000000000000000000001',
        },
        'testnet': {
            'eth_yield': '0x4200000000000000000000000000000000000023',
            'usdb_yield': '0x4200000000000000000000000000000000000022',
        }
    }
    
    # ABI fragments for common operations
    ERC20_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function"
        }
    ]
    
    # Yield contract ABIs
    YIELD_ABI = [
        {
            "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
            "name": "claimable",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "claim",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "address", "name": "to", "type": "address"}],
            "name": "claimTo",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "bool", "name": "enable", "type": "bool"}],
            "name": "configure",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Blast adapter.
        
        Args:
            network: Network name ('mainnet' or 'testnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid
        """
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Blast network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.chain_id = self.NETWORKS[network]['chain_id']
        self.rpc_endpoint = self.NETWORKS[network]['rpc_endpoint']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        
        # Set connection state
        self.is_connected = False
        self.web3 = None
        
        # Private key and account
        self.private_key = None
        self.account = None
        
        # Override config if provided
        if config:
            if 'rpc_endpoint' in config:
                self.rpc_endpoint = config['rpc_endpoint']
                
            if 'private_key' in config:
                self.private_key = config.get('private_key')
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        return f"BlastAdapter({self.network_name}, {connection_status})"
    
    @property
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/tx/"
    
    @property
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/address/"
    
    @property
    def explorer_block_url(self) -> str:
        """Get block explorer URL template."""
        return f"{self.explorer_url}/block/"
    
    @strict_blockchain_operation
    def _verify_connection(self) -> bool:
        """Verify connection to Blast network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.web3:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Check if web3 is connected
            if not self.web3.is_connected():
                raise BlockchainConnectionError(f"Web3 is not connected to {self.network_name}")
                
            # Get chain ID and verify it matches expected chain ID
            chain_id = self.web3.eth.chain_id
            if chain_id != self.chain_id:
                raise BlockchainConnectionError(
                    f"Connected to wrong chain ID: {chain_id}. "
                    f"Expected: {self.chain_id} ({self.network_name})"
                )
                
            return True
        except Exception as e:
            self.is_connected = False
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Blast network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize Web3 connection
            if self.rpc_endpoint.startswith(('http://', 'https://')):
                self.web3 = Web3(Web3.HTTPProvider(self.rpc_endpoint))
            elif self.rpc_endpoint.startswith(('ws://', 'wss://')):
                self.web3 = Web3(Web3.WebsocketProvider(self.rpc_endpoint))
            else:
                raise BlockchainConnectionError(f"Unsupported RPC endpoint: {self.rpc_endpoint}")
                
            # Apply POA middleware for compatibility with Blast's consensus mechanism
            self.web3.middleware_onion.inject(native_geth_poa_middleware, layer=0)
            
            # Initialize account if private key is provided
            if self.private_key:
                if not self.private_key.startswith('0x'):
                    self.private_key = f"0x{self.private_key}"
                self.account = Account.from_key(self.private_key)
            
            # Verify connection
            self._verify_connection()
            
            # Set connection status
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}")
            
            return True
            
        except Exception as e:
            self.is_connected = False
            self.web3 = None
            self.account = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    def validate_address(self, address: str) -> bool:
        """Validate Ethereum address format.
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Check if it's a valid Ethereum address
            return is_hex_address(address)
        except Exception:
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate private key format.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Ensure 0x prefix
            if not private_key.startswith('0x'):
                private_key = f"0x{private_key}"
                
            # Try to create an account with it
            Account.from_key(private_key)
            return True
        except Exception:
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str, token_id: str = None) -> Decimal:
        """Get ETH or token balance for address.
        
        Args:
            address: Address to query
            token_id: Optional token contract address
            
        Returns:
            Decimal: Balance in ETH or token
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not self.validate_address(address):
            raise ValidationError(f"Invalid address format: {address}")
            
        try:
            # Ensure address is in checksum format
            address = to_checksum_address(address)
            
            if not token_id:
                # Get native ETH balance
                balance_wei = self.web3.eth.get_balance(address)
                decimals = 18  # ETH has 18 decimals
                
                # Convert to ETH
                balance = Decimal(balance_wei) / Decimal(10 ** decimals)
                
                return balance
            else:
                # Get token balance
                if not self.validate_address(token_id):
                    # Check if it's a known token symbol
                    token_symbol = token_id.upper()
                    if token_symbol in self.CURRENCY and 'contract' in self.CURRENCY[token_symbol]:
                        token_address = self.CURRENCY[token_symbol]['contract'][self.network]
                        decimals = self.CURRENCY[token_symbol]['decimals']
                    else:
                        raise ValidationError(f"Invalid token ID or contract address: {token_id}")
                else:
                    # It's a contract address
                    token_address = to_checksum_address(token_id)
                    
                    # Create token contract
                    token_contract = self.web3.eth.contract(
                        address=token_address,
                        abi=self.ERC20_ABI
                    )
                    
                    # Get token decimals
                    try:
                        decimals = token_contract.functions.decimals().call()
                    except Exception:
                        # Default to 18 if decimals() call fails
                        decimals = 18
                
                # Create token contract
                token_contract = self.web3.eth.contract(
                    address=token_address,
                    abi=self.ERC20_ABI
                )
                
                # Get token balance
                balance_wei = token_contract.functions.balanceOf(address).call()
                
                # Convert to token units
                balance = Decimal(balance_wei) / Decimal(10 ** decimals)
                
                return balance
                
        except Exception as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_claimable_yield(self, address: str, yield_type: str = 'eth') -> Decimal:
        """Get claimable yield for an address.
        
        Args:
            address: Address to query
            yield_type: Type of yield ('eth' or 'usdb')
            
        Returns:
            Decimal: Claimable yield amount
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address or yield type is invalid
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not self.validate_address(address):
            raise ValidationError(f"Invalid address format: {address}")
            
        yield_type = yield_type.lower()
        if yield_type not in ['eth', 'usdb']:
            raise ValidationError(f"Invalid yield type: {yield_type}. Must be 'eth' or 'usdb'.")
            
        try:
            # Ensure address is in checksum format
            address = to_checksum_address(address)
            
            # Get yield contract address
            contract_key = f"{yield_type}_yield"
            yield_contract_address = self.YIELD_CONTRACTS[self.network][contract_key]
            
            # Create yield contract
            yield_contract = self.web3.eth.contract(
                address=yield_contract_address,
                abi=self.YIELD_ABI
            )
            
            # Get claimable yield
            claimable_wei = yield_contract.functions.claimable(address).call()
            
            # Convert to token units (both ETH and USDB use 18 decimals)
            claimable = Decimal(claimable_wei) / Decimal(10 ** 18)
            
            return claimable
            
        except Exception as e:
            error_msg = f"Failed to get claimable yield: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
        """Create Blast transaction.
        
        Args:
            transaction: Transaction details with the following fields:
                - to_address: Recipient address
                - from_address: Sender address (must match private key)
                - amount: Amount to send in ETH
                - gas_price: Optional gas price in wei
                - gas_limit: Optional gas limit
                - data: Optional transaction data
                - nonce: Optional nonce
                - token_address: Optional token contract address for token transfers
                
        Returns:
            dict: Transaction object ready for signing
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If transaction parameters are invalid
            TransactionError: If transaction creation fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Extract and validate transaction parameters
            to_address = transaction.get('to_address')
            from_address = transaction.get('from_address')
            amount = transaction.get('amount')
            gas_price = transaction.get('gas_price')
            gas_limit = transaction.get('gas_limit')
            data = transaction.get('data', '')
            nonce = transaction.get('nonce')
            token_address = transaction.get('token_address')
            
            # Validate addresses
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            if not self.validate_address(from_address):
                raise ValidationError(f"Invalid sender address: {from_address}")
                
            # Convert addresses to checksum format
            to_address = to_checksum_address(to_address)
            from_address = to_checksum_address(from_address)
            
            # Validate amount
            if amount is None or not isinstance(amount, (int, float, Decimal)) or amount < 0:
                raise ValidationError(f"Invalid amount: {amount}")
                
            # Check if we're sending ETH or tokens
            if token_address:
                # Token transfer
                if not self.validate_address(token_address):
                    raise ValidationError(f"Invalid token address: {token_address}")
                    
                token_address = to_checksum_address(token_address)
                
                # Create token contract
                token_contract = self.web3.eth.contract(
                    address=token_address,
                    abi=self.ERC20_ABI
                )
                
                # Get token decimals
                try:
                    decimals = token_contract.functions.decimals().call()
                except Exception:
                    # Default to 18 if decimals() call fails
                    decimals = 18
                    
                # Convert amount to token units
                amount_wei = int(Decimal(amount) * Decimal(10 ** decimals))
                
                # Create token transfer data
                data = token_contract.encodeABI(
                    fn_name='transfer',
                    args=[to_address, amount_wei]
                )
                
                # Set token contract as recipient for the actual transaction
                to_address_final = token_address
                amount_wei_final = 0  # We're not sending ETH, just the token transfer
            else:
                # ETH transfer
                decimals = 18  # ETH has 18 decimals
                amount_wei = int(Decimal(amount) * Decimal(10 ** decimals))
                to_address_final = to_address
                amount_wei_final = amount_wei
            
            # Get nonce if not provided
            if nonce is None:
                nonce = self.web3.eth.get_transaction_count(from_address)
                
            # Get gas price if not provided
            if gas_price is None:
                gas_price = self.web3.eth.gas_price
                
            # Create transaction object
            tx = {
                'chainId': self.chain_id,
                'from': from_address,
                'to': to_address_final,
                'value': amount_wei_final,
                'nonce': nonce,
                'data': data
            }
            
            # Try to estimate gas if not provided
            if gas_limit is None:
                try:
                    gas_limit = self.web3.eth.estimate_gas(tx)
                    # Add a 20% buffer to ensure transaction success
                    gas_limit = int(gas_limit * 1.2)
                except Exception as e:
                    logger.warning(f"Failed to estimate gas: {str(e)}. Using default gas limit.")
                    gas_limit = 250000  # Default gas limit
                    
            tx['gas'] = gas_limit
            
            # Handle EIP-1559 transaction if supported
            try:
                latest_block = self.web3.eth.get_block('latest')
                if hasattr(latest_block, 'baseFeePerGas'):
                    # EIP-1559 transaction
                    base_fee = latest_block.baseFeePerGas
                    priority_fee = min(2 * 10**9, gas_price - base_fee) if gas_price > base_fee else 1 * 10**9
                    max_fee_per_gas = 2 * base_fee + priority_fee
                    
                    tx['maxFeePerGas'] = max_fee_per_gas
                    tx['maxPriorityFeePerGas'] = priority_fee
                    
                    # Remove gasPrice for EIP-1559 transactions
                    if 'gasPrice' in tx:
                        del tx['gasPrice']
                else:
                    # Legacy transaction
                    tx['gasPrice'] = gas_price
            except Exception:
                # Fall back to legacy transaction
                tx['gasPrice'] = gas_price
                
            # Store transaction details
            transaction_details = {
                'chain_id': self.chain_id,
                'network': self.network,
                'from_address': from_address,
                'to_address': to_address,  # Original to_address
                'amount': amount,
                'amount_wei': amount_wei,  # Original amount in wei
                'nonce': nonce,
                'gas_limit': gas_limit,
                'gas_price': gas_price,
                'data': data,
                'transaction': tx,
                'signed': False
            }
            
            # Add token details if it's a token transfer
            if token_address:
                transaction_details['token_address'] = token_address
                transaction_details['token_decimals'] = decimals
                
            return transaction_details
            
        except Web3ValidationError as e:
            error_msg = f"Web3 validation error: {str(e)}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
        """Sign Blast transaction.
        
        Args:
            transaction: Transaction object from create_transaction
            private_key: Private key for signing
            
        Returns:
            dict: Signed transaction object ready for broadcasting
            
        Raises:
            ValidationError: If transaction is invalid
            TransactionError: If signing fails
            WalletError: If private key is invalid
        """
        # Validate transaction object
        if not transaction or 'transaction' not in transaction:
            raise ValidationError("Invalid transaction object")
            
        try:
            # Get the transaction object
            tx = transaction['transaction']
            
            # Determine the private key to use
            key = None
            if private_key:
                # Use provided private key
                if not self.validate_private_key(private_key):
                    raise WalletError("Invalid private key format")
                    
                if not private_key.startswith('0x'):
                    private_key = f"0x{private_key}"
                    
                key = private_key
            elif self.private_key:
                # Use instance private key
                key = self.private_key
            else:
                raise WalletError("No private key available for signing")
                
            # Create account from private key if needed
            account = self.account if self.private_key == key else Account.from_key(key)
            
            # Verify the account address matches the transaction from address
            from_address = to_checksum_address(transaction['from_address'])
            if account.address.lower() != from_address.lower():
                raise ValidationError(
                    f"Account address {account.address} does not match transaction from address {from_address}"
                )
                
            # Sign the transaction
            signed_tx = account.sign_transaction(tx)
            
            # Create signed transaction object
            signed_transaction = transaction.copy()
            signed_transaction['signed'] = True
            signed_transaction['raw_transaction'] = signed_tx.rawTransaction.hex()
            signed_transaction['tx_hash'] = signed_tx.hash.hex()
            signed_transaction['r'] = signed_tx.r
            signed_transaction['s'] = signed_tx.s
            signed_transaction['v'] = signed_tx.v
            
            return signed_transaction
            
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast signed Blast transaction.
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            dict: Transaction receipt with hash and status
            
        Raises:
            ValidationError: If signed transaction is invalid
            TransactionError: If broadcasting fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        # Validate signed transaction
        if not signed_transaction or not signed_transaction.get('signed', False) or 'raw_transaction' not in signed_transaction:
            raise ValidationError("Transaction is not signed")
            
        try:
            # Get the raw transaction
            raw_tx = signed_transaction['raw_transaction']
            if not raw_tx.startswith('0x'):
                raw_tx = f"0x{raw_tx}"
                
            # Send the raw transaction
            tx_hash = self.web3.eth.send_raw_transaction(raw_tx)
            tx_hash_hex = tx_hash.hex()
            
            # Create receipt
            receipt = {
                'txid': tx_hash_hex,
                'hash': tx_hash_hex,
                'confirmed': False,  # Not confirmed yet
                'explorer_url': f"{self.explorer_tx_url}{tx_hash_hex}",
                'from_address': signed_transaction['from_address'],
                'to_address': signed_transaction['to_address'],
                'amount': signed_transaction['amount'],
                'gas_limit': signed_transaction['gas_limit'],
                'gas_price': signed_transaction['gas_price'],
                'nonce': signed_transaction['nonce'],
                'status': 'pending'
            }
            
            # Add token details if it's a token transfer
            if 'token_address' in signed_transaction:
                receipt['token_address'] = signed_transaction['token_address']
                receipt['token_decimals'] = signed_transaction.get('token_decimals', 18)
            
            return receipt
            
        except ValueError as e:
            # Web3.py raises ValueError for RPC errors
            error_msg = f"Failed to broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_id: str) -> Dict:
        """Get status of a transaction.
        
        Args:
            tx_id: Transaction hash
            
        Returns:
            dict: Transaction status and details
            
        Raises:
            ValidationError: If tx_id is invalid
            TransactionError: If status check fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not tx_id:
            raise ValidationError("Invalid transaction ID")
            
        # Ensure tx_id has 0x prefix
        if not tx_id.startswith('0x'):
            tx_id = f"0x{tx_id}"
            
        try:
            # Check if transaction is in the blockchain
            try:
                # Try to get transaction receipt
                receipt = self.web3.eth.get_transaction_receipt(tx_id)
                transaction = self.web3.eth.get_transaction(tx_id)
                
                # If we get here, transaction exists and has been mined
                confirmed = True
                
                # Determine status
                if receipt.status == 1:
                    status = 'success'
                else:
                    status = 'failed'
                    
                # Create status object
                result = {
                    'txid': tx_id,
                    'hash': tx_id,
                    'confirmed': confirmed,
                    'status': status,
                    'explorer_url': f"{self.explorer_tx_url}{tx_id}",
                    'block_number': receipt.blockNumber,
                    'block_hash': receipt.blockHash.hex(),
                    'from_address': receipt.get('from', None),
                    'to_address': receipt.get('to', None),
                    'gas_used': receipt.gasUsed,
                    'gas_price': transaction.get('gasPrice', None),
                    'value': transaction.get('value', None),
                    'nonce': transaction.get('nonce', None)
                }
                
                # Add EIP-1559 fields if present
                if hasattr(transaction, 'maxFeePerGas'):
                    result['max_fee_per_gas'] = transaction.maxFeePerGas
                    result['max_priority_fee_per_gas'] = transaction.maxPriorityFeePerGas
                
                return result
                
            except Exception:
                # Transaction not found or not mined yet
                # Try to get transaction from mempool
                transaction = self.web3.eth.get_transaction(tx_id)
                
                if transaction:
                    # Transaction is in the mempool
                    return {
                        'txid': tx_id,
                        'hash': tx_id,
                        'confirmed': False,
                        'status': 'pending',
                        'explorer_url': f"{self.explorer_tx_url}{tx_id}",
                        'from_address': transaction.get('from', None),
                        'to_address': transaction.get('to', None),
                        'gas_price': transaction.get('gasPrice', None),
                        'value': transaction.get('value', None),
                        'nonce': transaction.get('nonce', None)
                    }
                else:
                    # Transaction not found
                    return {
                        'txid': tx_id,
                        'hash': tx_id,
                        'confirmed': False,
                        'status': 'unknown',
                        'explorer_url': f"{self.explorer_tx_url}{tx_id}"
                    }
                
        except Exception as e:
            error_msg = f"Failed to get transaction status: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
