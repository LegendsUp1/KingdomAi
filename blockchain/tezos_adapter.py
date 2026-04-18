#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tezos blockchain adapter implementation.
Native, no-fallback adapter for Tezos network integration.
"""

import os
import json
import time
import base64
import binascii
import urllib.request
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
from urllib.parse import urljoin

# Import blockchain base components
from blockchain.base_adapter import BlockchainAdapter, strict_blockchain_operation
from blockchain.exceptions import (
    BlockchainConnectionError,
    TransactionError, 
    ValidationError,
    WalletError
)

# Import Tezos specific libraries
from pytezos import pytezos, Key
from pytezos.operation.result import OperationResult
from pytezos.rpc.errors import RpcError, MichelsonError

# Import cryptographic libraries
import hashlib
import base58

# Import networking libraries for API calls
import requests
from requests.exceptions import RequestException

# Import logging
import logging
logger = logging.getLogger(__name__)


class TezosAdapter(BlockchainAdapter):
    """Native Tezos blockchain adapter.
    
    Implements all required blockchain operations for Tezos network
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Tezos Mainnet',
            'rpc_endpoint': 'https://mainnet.api.tez.ie',
            'explorer_url': 'https://tzstats.com',
            'chain_id': 'NetXdQprcVkpaWU',
        },
        'ghostnet': {
            'name': 'Tezos Ghostnet',
            'rpc_endpoint': 'https://rpc.ghostnet.teztnets.xyz',
            'explorer_url': 'https://ghostnet.tzstats.com',
            'chain_id': 'NetXnHfVqm9iesp',
        },
        'sandbox': {
            'name': 'Tezos Sandbox',
            'rpc_endpoint': 'http://localhost:8732',
            'explorer_url': 'http://localhost:8732',
            'chain_id': 'NetXynUjJNZm7wi',
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'XTZ': {
            'name': 'Tezos',
            'symbol': 'XTZ',
            'decimals': 6,  # 1 XTZ = 10^6 mutez
            'min_fee': 0.001  # Minimum transaction fee in XTZ
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Tezos adapter.
        
        Args:
            network: Network name ('mainnet', 'ghostnet', or 'sandbox')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid
        """
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Tezos network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.rpc_endpoint = self.NETWORKS[network]['rpc_endpoint']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.chain_id = self.NETWORKS[network]['chain_id']
        
        # Set currency details (XTZ)
        self.currency = self.CURRENCY['XTZ']
        
        # Set connection state
        self.is_connected = False
        self.client = None
        
        # Private key and wallet
        self.private_key = None
        self.key = None
        
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
        return f"TezosAdapter({self.network_name}, {connection_status})"
    
    @property
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/opg/"
    
    @property
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/tz/"
    
    @property
    def explorer_block_url(self) -> str:
        """Get block explorer URL template."""
        return f"{self.explorer_url}/block/"
    
    @strict_blockchain_operation
    def _verify_connection(self) -> bool:
        """Verify connection to Tezos network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get chain ID to verify connection
            chain_id = self.client.shell.block.chain_id()
            if not chain_id:
                raise BlockchainConnectionError("Failed to get chain ID")
                
            return True
        except RpcError as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Tezos network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize Tezos client with the RPC endpoint
            self.client = pytezos.using(shell=self.rpc_endpoint)
            
            # Initialize key if private key is provided
            if self.private_key:
                self.key = Key.from_secret_key(self.private_key)
                self.client = self.client.using(key=self.key)
            
            # Verify connection
            self._verify_connection()
            
            # Set connection status
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}")
            
            return True
            
        except RpcError as e:
            self.is_connected = False
            self.client = None
            self.key = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
        except Exception as e:
            self.is_connected = False
            self.client = None
            self.key = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    def validate_address(self, address: str) -> bool:
        """Validate Tezos address format.
        
        Args:
            address: Tezos address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Tezos addresses start with tz1, tz2, tz3, or KT1
            valid_prefixes = ['tz1', 'tz2', 'tz3', 'KT1']
            if not any(address.startswith(prefix) for prefix in valid_prefixes):
                return False
                
            # Implicit accounts (tz1, tz2, tz3) are 36 characters
            # Contract accounts (KT1) are 36 characters
            if len(address) != 36:
                return False
                
            # Try to decode the address as base58
            try:
                base58.b58decode_check(address)
                return True
            except Exception:
                return False
                
        except Exception:
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate Tezos private key format.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Tezos private keys can be in edsk, spsk, or p2sk format
            valid_prefixes = ['edsk', 'spsk', 'p2sk']
            if not any(private_key.startswith(prefix) for prefix in valid_prefixes):
                return False
                
            # Try to create a key with it
            test_key = Key.from_secret_key(private_key)
            
            # If we got here, it's valid
            return True
            
        except Exception:
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str, token_id: str = None) -> Decimal:
        """Get XTZ balance for address.
        
        Args:
            address: Tezos address to query
            token_id: Optional token ID for other tokens
            
        Returns:
            Decimal: Balance in XTZ
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not self.validate_address(address):
            raise ValidationError(f"Invalid address format: {address}")
            
        try:
            # Get account info from network
            account = self.client.account(address)
            
            if token_id:
                # Query FA1.2 / FA2 token balance via TzKT indexer API
                tzkt_url = (
                    f"https://api.tzkt.io/v1/tokens/balances"
                    f"?account={address}&token.id={token_id}"
                )
                try:
                    req = urllib.request.Request(tzkt_url)
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        balances = json.loads(resp.read().decode())
                    if balances:
                        raw_balance = balances[0].get('balance', '0')
                        token_decimals = (
                            balances[0].get('token', {})
                            .get('metadata', {})
                            .get('decimals')
                        )
                        if token_decimals is not None:
                            return Decimal(raw_balance) / Decimal(10 ** int(token_decimals))
                        return Decimal(raw_balance)
                    return Decimal(0)
                except Exception as tzkt_err:
                    error_msg = f"TzKT token balance query failed: {tzkt_err}"
                    logger.error(error_msg)
                    raise BlockchainConnectionError(error_msg) from tzkt_err
            else:
                # Get native XTZ balance in mutez
                balance_mutez = account['balance']
                
                # Convert to XTZ
                balance_xtz = Decimal(balance_mutez) / Decimal(10 ** self.currency['decimals'])
                
                return balance_xtz
                
        except RpcError as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict) -> Dict:
        """Create Tezos transaction.
        
        Args:
            transaction: Transaction details with the following fields:
                - to_address: Recipient address
                - from_address: Sender address (must match private key)
                - amount: Amount to send in XTZ
                - fee: Optional fee in XTZ
                - gas_limit: Optional gas limit
                - storage_limit: Optional storage limit
                - parameters: Optional parameters for smart contract calls
                - entrypoint: Optional entrypoint for smart contract calls
                
        Returns:
            dict: Transaction object ready for signing
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If transaction parameters are invalid
            TransactionError: If transaction creation fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Extract and validate transaction parameters
            to_address = transaction.get('to_address')
            from_address = transaction.get('from_address')
            amount = transaction.get('amount')
            fee = transaction.get('fee')
            gas_limit = transaction.get('gas_limit')  
            storage_limit = transaction.get('storage_limit')
            parameters = transaction.get('parameters')
            entrypoint = transaction.get('entrypoint')
            
            # Validate addresses
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            if not self.validate_address(from_address):
                raise ValidationError(f"Invalid sender address: {from_address}")
                
            # Validate amount
            if amount is None or not isinstance(amount, (int, float, Decimal)) or amount < 0:
                raise ValidationError(f"Invalid amount: {amount}")
                
            # Convert XTZ amount to mutez (smallest unit)
            if isinstance(amount, (float, Decimal)):
                amount_mutez = int(amount * (10 ** self.currency['decimals']))
            else:
                amount_mutez = amount
            
            # Check if we need to add a key to the client
            if not hasattr(self.client, 'key') or not self.client.key:
                if not self.key:
                    raise ValidationError("No key available for creating transaction")
                self.client = self.client.using(key=self.key)
            
            # Verify the sender address matches the key's address
            if from_address != self.client.key.public_key_hash():
                raise ValidationError(
                    f"Sender address {from_address} does not match key's address {self.client.key.public_key_hash()}"
                )
            
            # Build transaction parameters
            tx_params = {}
            
            if fee is not None:
                tx_params['fee'] = int(fee * (10 ** self.currency['decimals'])) if isinstance(fee, (float, Decimal)) else fee
                
            if gas_limit is not None:
                tx_params['gas_limit'] = gas_limit
                
            if storage_limit is not None:
                tx_params['storage_limit'] = storage_limit
                
            # Create the transaction object
            operation = None
            
            # Check if it's a contract call or simple transfer
            if parameters is not None and entrypoint is not None:
                # Contract call
                contract = self.client.contract(to_address)
                operation = contract.using(**tx_params).call(
                    entrypoint,
                    parameters
                ).with_amount(amount_mutez)
            else:
                # Simple transfer
                operation = self.client.transaction(
                    destination=to_address,
                    amount=amount_mutez,
                    **tx_params
                )
            
            # Store the transaction details
            transaction_details = {
                'network': self.network,
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount,
                'amount_mutez': amount_mutez,
                'operation': operation,
                'signed': False
            }
            
            # Add optional parameters
            if fee is not None:
                transaction_details['fee'] = fee
            if gas_limit is not None:
                transaction_details['gas_limit'] = gas_limit
            if storage_limit is not None:
                transaction_details['storage_limit'] = storage_limit
            if parameters is not None:
                transaction_details['parameters'] = parameters
            if entrypoint is not None:
                transaction_details['entrypoint'] = entrypoint
            
            return transaction_details
            
        except RpcError as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
        """Sign Tezos transaction.
        
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
        if not transaction or 'operation' not in transaction:
            raise ValidationError("Invalid transaction object")
            
        try:
            # Get the operation object
            operation = transaction['operation']
            
            # Check if we need to add a key
            if private_key:
                if not self.validate_private_key(private_key):
                    raise WalletError("Invalid private key format")
                key = Key.from_secret_key(private_key)
                operation = operation.using(key=key)
            elif not hasattr(operation, 'key') or not operation.key:
                if not self.key:
                    raise WalletError("No key available for signing")
                operation = operation.using(key=self.key)
            
            # Prepare the operation for signing
            # This simulates the operation to get accurate gas and storage estimates
            prepared_operation = operation.autofill()
            
            # Sign the operation
            signed_op = prepared_operation.sign()
            
            # Return signed transaction
            signed_tx = transaction.copy()
            signed_tx['signed'] = True
            signed_tx['operation'] = signed_op
            signed_tx['hash'] = signed_op.hash()
            
            # Update gas and storage estimates if available
            if hasattr(prepared_operation, 'gas_limit'):
                signed_tx['gas_limit'] = prepared_operation.gas_limit
                
            if hasattr(prepared_operation, 'storage_limit'):
                signed_tx['storage_limit'] = prepared_operation.storage_limit
                
            if hasattr(prepared_operation, 'fee'):
                signed_tx['fee'] = prepared_operation.fee / (10 ** self.currency['decimals'])
            
            return signed_tx
            
        except RpcError as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast signed Tezos transaction.
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            dict: Transaction receipt with hash and status
            
        Raises:
            ValidationError: If signed transaction is invalid
            TransactionError: If broadcasting fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        # Validate signed transaction
        if not signed_transaction or not signed_transaction.get('signed', False) or 'operation' not in signed_transaction:
            raise ValidationError("Transaction is not signed")
            
        try:
            # Get the signed operation
            signed_op = signed_transaction['operation']
            
            # Inject the operation into the network
            inject_result = signed_op.inject()
            
            # Get the operation hash
            op_hash = inject_result['hash'] if isinstance(inject_result, dict) else inject_result
            
            # Create receipt
            receipt = {
                'txid': op_hash,
                'confirmed': False,  # Just sent, not confirmed yet
                'explorer_url': f"{self.explorer_tx_url}{op_hash}",
                'from_address': signed_transaction['from_address'],
                'to_address': signed_transaction['to_address'],
                'amount': signed_transaction['amount'],
                'status': 'pending'
            }
            
            # Add fee if available
            if 'fee' in signed_transaction:
                receipt['fee'] = signed_transaction['fee']
            
            return receipt
            
        except RpcError as e:
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
            tx_id: Transaction ID (operation hash)
            
        Returns:
            dict: Transaction status and details
            
        Raises:
            ValidationError: If tx_id is invalid
            TransactionError: If status check fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not tx_id:
            raise ValidationError("Invalid transaction ID")
            
        try:
            # Check if the operation has been included in a block
            op_result = None
            status = 'pending'
            confirmed = False
            
            try:
                # First try to get the operation directly
                op_result = self.client.shell.blocks.head.operations.applied[3][tx_id]
                if op_result:
                    status = 'success'
                    confirmed = True
            except Exception:
                # Operation not found directly, try to search by hash
                try:
                    # Need to search block by block, starting from the latest
                    head_block = self.client.shell.head.header()
                    block_level = head_block['level']
                    
                    # Search up to 10 recent blocks
                    for i in range(10):
                        if block_level - i < 0:
                            break
                        
                        block = self.client.shell.blocks[block_level - i]
                        for ops_list in block.operations():
                            for op in ops_list:
                                if op['hash'] == tx_id:
                                    op_result = op
                                    # Check for operation status
                                    for contents in op['contents']:
                                        if 'metadata' in contents and 'operation_result' in contents['metadata']:
                                            op_status = contents['metadata']['operation_result']['status']
                                            if op_status == 'applied':
                                                status = 'success'
                                                confirmed = True
                                            else:
                                                status = 'failed'
                                                confirmed = True
                except Exception:
                    # Operation not found in recent blocks
                    pass
            
            # Build result object
            result = {
                'txid': tx_id,
                'confirmed': confirmed,
                'status': status,
                'explorer_url': f"{self.explorer_tx_url}{tx_id}"
            }
            
            # Add operation details if available
            if op_result:
                # Extract basic operation details
                if isinstance(op_result, dict):
                    # Extract information like block level, fees, etc.
                    if 'branch' in op_result:
                        result['branch'] = op_result['branch']
                    
                    if 'contents' in op_result and len(op_result['contents']) > 0:
                        content = op_result['contents'][0]
                        result['type'] = content.get('kind')
                        
                        # For transfers
                        if content.get('kind') == 'transaction':
                            result['from_address'] = content.get('source')
                            result['to_address'] = content.get('destination')
                            result['amount'] = Decimal(content.get('amount', 0)) / Decimal(10 ** self.currency['decimals'])
                            
                            # Get fees and gas
                            result['fee'] = Decimal(content.get('fee', 0)) / Decimal(10 ** self.currency['decimals'])
                            result['gas_limit'] = content.get('gas_limit')
                            result['storage_limit'] = content.get('storage_limit')
                            
                            # Get operation result if available
                            if 'metadata' in content and 'operation_result' in content['metadata']:
                                op_result = content['metadata']['operation_result']
                                result['consumed_gas'] = op_result.get('consumed_gas')
                                result['paid_storage_size_diff'] = op_result.get('paid_storage_size_diff')
                
            return result
                
        except RpcError as e:
            error_msg = f"Failed to get transaction status: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to get transaction status: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, transaction: Dict = None) -> Dict:
        """Estimate transaction fee.
        
        Args:
            transaction: Optional transaction details
            
        Returns:
            dict: Fee estimates (slow, average, fast)
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get network constants
            constants = self.client.shell.head.context.constants()
            
            # Get minimal fees
            min_fee = Decimal(constants['minimal_fees']) / Decimal(10 ** self.currency['decimals'])
            gas_price = Decimal(constants['minimal_nanotez_per_gas_unit']) / Decimal(10 ** 9)  # nanotez to tez
            storage_price = Decimal(constants['cost_per_byte']) / Decimal(10 ** self.currency['decimals'])
            
            # Default operation parameters for simple transfers
            default_gas = 10200
            default_storage = 0
            
            # Use provided transaction to get more accurate estimates if available
            if transaction and isinstance(transaction, dict) and 'operation' in transaction:
                try:
                    # Try to simulate the operation to get better estimates
                    simulated = transaction['operation'].autofill()
                    default_gas = simulated.gas_limit
                    default_storage = simulated.storage_limit
                except Exception:
                    # Fallback to defaults if simulation fails
                    pass
            
            # Calculate base fee
            base_fee = min_fee + (gas_price * default_gas) + (storage_price * default_storage)
            
            # Calculate fee tiers
            slow_fee = base_fee
            avg_fee = base_fee * Decimal('1.5')
            fast_fee = base_fee * Decimal('2.0')
            
            return {
                'slow': {
                    'fee': slow_fee,
                    'gas_limit': default_gas,
                    'storage_limit': default_storage,
                    'time_estimate': '30 minutes'
                },
                'average': {
                    'fee': avg_fee,
                    'gas_limit': default_gas,
                    'storage_limit': default_storage,
                    'time_estimate': '5 minutes'
                },
                'fast': {
                    'fee': fast_fee,
                    'gas_limit': default_gas,
                    'storage_limit': default_storage,
                    'time_estimate': '1 minute'
                }
            }
                
        except RpcError as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_network_status(self) -> Dict:
        """Get Tezos network status.
        
        Returns:
            dict: Network statistics and status
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get latest block header
            head = self.client.shell.head.header()
            
            # Get chain ID
            chain_id = self.client.shell.chain_id()
            
            # Get protocol hash
            protocol = head['protocol']
            
            # Get network constants
            constants = self.client.shell.head.context.constants()
            
            # Build status object
            stats = {
                'network_name': self.network_name,
                'chain_id': chain_id,
                'protocol': protocol,
                'level': head['level'],
                'timestamp': head['timestamp'],
                'voting_period': constants.get('voting_period', {}),
                'blocks_per_cycle': constants.get('blocks_per_cycle'),
                'blocks_per_voting_period': constants.get('blocks_per_voting_period'),
                'time_between_blocks': constants.get('time_between_blocks')
            }
            
            return stats
                
        except RpcError as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from Tezos network.
        
        Returns:
            bool: True if successfully disconnected
        """
        self.is_connected = False
        self.client = None
        self.key = None
        logger.info(f"Disconnected from {self.network_name}")
        return True
