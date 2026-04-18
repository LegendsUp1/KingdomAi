#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Aptos blockchain adapter implementation.
Native, no-fallback adapter for Aptos blockchain integration.
"""

import os
import json
import time
import hashlib
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
import requests

# Import blockchain base components
from blockchain.base_adapter import BlockchainAdapter, strict_blockchain_operation
from blockchain.exceptions import (
    BlockchainConnectionError,
    TransactionError,
    ValidationError,
    WalletError
)

# Import Aptos specific libraries
try:
    from aptos_sdk.account import Account as AptosAccount
    from aptos_sdk.account_address import AccountAddress
    from aptos_sdk.bcs import Serializer
    from aptos_sdk.client import RestClient, FaucetClient
    from aptos_sdk.transactions import (
        EntryFunction, TransactionArgument, TransactionPayload,
        RawTransaction, SignedTransaction
    )
    APTOS_AVAILABLE = True
except ImportError:
    APTOS_AVAILABLE = False
    
# Import logging
import logging
logger = logging.getLogger(__name__)


class AptosAdapter(BlockchainAdapter):
    """Native Aptos blockchain adapter.
    
    Implements all required blockchain operations for Aptos
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Aptos Mainnet',
            'node_url': 'https://fullnode.mainnet.aptoslabs.com/v1',
            'faucet_url': None,  # No faucet for mainnet
            'explorer_url': 'https://explorer.aptoslabs.com',
            'chain_id': 1
        },
        'testnet': {
            'name': 'Aptos Testnet',
            'node_url': 'https://fullnode.testnet.aptoslabs.com/v1',
            'faucet_url': 'https://faucet.testnet.aptoslabs.com',
            'explorer_url': 'https://explorer.aptoslabs.com/testnet',
            'chain_id': 2
        },
        'devnet': {
            'name': 'Aptos Devnet',
            'node_url': 'https://fullnode.devnet.aptoslabs.com/v1',
            'faucet_url': 'https://faucet.devnet.aptoslabs.com',
            'explorer_url': 'https://explorer.aptoslabs.com/devnet',
            'chain_id': 36
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'APT': {
            'name': 'Aptos',
            'symbol': 'APT',
            'decimals': 8,
            'is_native': True
        }
    }
    
    # Contract addresses
    CORE_ADDRESSES = {
        'coin_type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
        'transfer_function': '0x1::coin::transfer',
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Aptos adapter.
        
        Args:
            network: Network name ('mainnet', 'testnet', or 'devnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid or Aptos SDK is unavailable
        """
        if not APTOS_AVAILABLE:
            raise ValidationError("Aptos SDK is not available. "
                                 "Install with 'pip install aptos-sdk'")
        
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Aptos network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.node_url = self.NETWORKS[network]['node_url']
        self.faucet_url = self.NETWORKS[network]['faucet_url']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.chain_id = self.NETWORKS[network]['chain_id']
        
        # Set connection state
        self.is_connected = False
        self.rest_client = None
        self.faucet_client = None
        
        # Account management
        self.account = None
        self.private_key = None
        self.address = None
        
        # Override config if provided
        if config:
            if 'node_url' in config:
                self.node_url = config['node_url']
                
            if 'private_key' in config:
                self.private_key = config['private_key']
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        account_info = f", Account: {self.address}" if self.address else ""
        return f"Aptos Adapter ({self.network_name}) - {connection_status}{account_info}"
        
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/txn/{{txid}}"
        
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/account/{{address}}"
        
    def _verify_connection(self) -> bool:
        """Verify connection to Aptos network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.rest_client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Check if client is responsive
            ledger_info = self.rest_client.get_ledger_information()
            if not ledger_info or 'chain_id' not in ledger_info:
                raise BlockchainConnectionError(f"Invalid response from {self.network_name}")
                
            return True
        except Exception as e:
            self.is_connected = False
            error_msg = f"Connection to {self.network_name} failed: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Aptos network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Create REST client
            self.rest_client = RestClient(self.node_url)
            
            # Create faucet client if available
            if self.faucet_url:
                self.faucet_client = FaucetClient(self.rest_client.url, self.faucet_url)
            
            # Verify connection by getting chain info
            ledger_info = self.rest_client.get_ledger_information()
            chain_id = ledger_info.get('chain_id', None)
            
            if chain_id != self.chain_id:
                logger.warning(f"Chain ID mismatch: expected {self.chain_id}, got {chain_id}")
            
            # Initialize account if private key is available
            if self.private_key:
                try:
                    # Create account from private key
                    self.account = AptosAccount.load_key(self.private_key)
                    self.address = str(self.account.address())
                    logger.info(f"Initialized account: {self.address}")
                except Exception as e:
                    logger.warning(f"Failed to initialize account: {str(e)}")
            
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}, chain ID: {chain_id}")
            return True
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from Aptos network.
        
        Returns:
            bool: True if disconnected successfully
        """
        try:
            # Reset connection state
            self.rest_client = None
            self.faucet_client = None
            self.is_connected = False
            logger.info(f"Disconnected from {self.network_name}")
            return True
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            return False
            
    def validate_address(self, address: str) -> bool:
        """Validate Aptos address format.
        
        Args:
            address: Aptos address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Clean up the address if it has a 0x prefix
            if address.startswith('0x'):
                address = address[2:]
                
            # Aptos addresses are 32 bytes (64 hex characters)
            if len(address) != 64:
                return False
                
            # Check if it's a valid hex string
            int(address, 16)
            
            # Create AccountAddress to validate format
            AccountAddress.from_hex(address)
            
            return True
        except Exception as e:
            logger.debug(f"Address validation error: {str(e)}")
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate Aptos private key format.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Try to create an account with the private key
            AptosAccount.load_key(private_key)
            return True
        except Exception as e:
            logger.debug(f"Invalid private key format: {str(e)}")
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str = None, token_id: str = None) -> Decimal:
        """Get APT balance for an account.
        
        Args:
            address: Aptos address to query, defaults to connected account
            token_id: Optional token ID for querying token balance
            
        Returns:
            Decimal: Balance in APT
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        self._verify_connection()
        
        # Use the provided address or the connected account
        addr = address or self.address
        
        if not addr:
            raise ValidationError("No address provided and no account connected")
            
        if not self.validate_address(addr):
            raise ValidationError(f"Invalid Aptos address: {addr}")
            
        try:
            # Normalize the address
            if addr.startswith('0x'):
                addr_obj = AccountAddress.from_hex(addr)
            else:
                addr_obj = AccountAddress.from_hex('0x' + addr)
                
            addr_str = str(addr_obj)
            
            if token_id:
                # Get token balance (custom token)
                # Format: 0x1::coin::CoinStore<${token_id}> 
                resource_type = f"0x1::coin::CoinStore<{token_id}>"
                try:
                    resource = self.rest_client.account_resource(addr_str, resource_type)
                    if resource and 'data' in resource and 'coin' in resource['data'] and 'value' in resource['data']['coin']:
                        balance_raw = int(resource['data']['coin']['value'])
                        # Assume 8 decimal places for tokens (can be adjusted based on token_id)
                        balance = Decimal(balance_raw) / Decimal(10**8)
                        return balance
                    else:
                        return Decimal(0)
                except Exception:
                    # Resource not found, return 0
                    return Decimal(0)
            else:
                # Get APT balance (native token)
                try:
                    resource = self.rest_client.account_resource(
                        addr_str,
                        self.CORE_ADDRESSES['coin_type']
                    )
                    
                    if resource and 'data' in resource and 'coin' in resource['data'] and 'value' in resource['data']['coin']:
                        balance_raw = int(resource['data']['coin']['value'])
                        # APT has 8 decimal places
                        balance_apt = Decimal(balance_raw) / Decimal(10**8)
                        logger.debug(f"Balance for {addr_str}: {balance_apt} APT")
                        return balance_apt
                    else:
                        return Decimal(0)
                except Exception as e:
                    # If account doesn't exist or doesn't have the resource
                    logger.debug(f"Error getting balance: {str(e)}")
                    return Decimal(0)
                
        except Exception as e:
            error_msg = f"Failed to get balance for {addr}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e

    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
        """Create an Aptos transaction.
        
        Args:
            transaction: Transaction parameters
                - to_address: Recipient address
                - amount: Amount in APT
                - token_id: Optional token ID for token transfers
                - data: Optional data for the transaction
            
        Returns:
            Dict: Prepared transaction object ready for signing
            
        Raises:
            ValidationError: If transaction parameters are invalid
            TransactionError: If transaction creation fails
        """
        self._verify_connection()
        
        # Validate the transaction parameters
        to_address = transaction.get('to_address')
        amount = transaction.get('amount')
        token_id = transaction.get('token_id')
        data = transaction.get('data', {})
        
        # Validate recipient address
        if not to_address or not self.validate_address(to_address):
            raise ValidationError(f"Invalid recipient address: {to_address}")
            
        # Get the sender account
        if not self.account or not self.address:
            raise ValidationError("No account connected. Cannot create transaction.")
        
        try:
            # Normalize the recipient address
            if to_address.startswith('0x'):
                recipient = AccountAddress.from_hex(to_address)
            else:
                recipient = AccountAddress.from_hex('0x' + to_address)
                
            # Convert amount from APT to octas (10^8)
            amount_octas = int(Decimal(amount) * Decimal(10**8))
            
            # Prepare transaction arguments
            if token_id:
                payload = TransactionPayload(
                    EntryFunction.natural(
                        "0x1::coin",
                        "transfer",
                        [TypeTag(StructTag.from_str(token_id))],
                        [
                            TransactionArgument(to_address, Serializer.struct),
                            TransactionArgument(amount_octas, Serializer.u64),
                        ],
                    )
                )
            else:
                # Native APT transfer
                # Create an entry function transaction
                payload = TransactionPayload(
                    EntryFunction.natural(
                        "0x1::coin",                         # Module address and name
                        "transfer",                          # Function name
                        ["0x1::aptos_coin::AptosCoin"],      # Type arguments
                        [                                    # Function arguments
                            TransactionArgument(recipient, Serializer.struct),
                            TransactionArgument(amount_octas, Serializer.u64)
                        ]
                    )
                )
                
                # Get the account sequence number (nonce)
                sender_account = self.rest_client.account(self.account.address())
                sequence_number = int(sender_account['sequence_number'])
                
                # Create the raw transaction
                expiration_timestamp_secs = int(time.time()) + 600  # 10 minutes
                
                raw_tx = RawTransaction(
                    self.account.address(),
                    sequence_number,
                    payload,
                    2000,  # max_gas_amount
                    100,   # gas_unit_price
                    expiration_timestamp_secs,
                    self.chain_id
                )
                
                # Return the transaction data
                tx_data = {
                    'type': 'apt_transfer',
                    'sender': str(self.account.address()),
                    'recipient': str(recipient),
                    'amount': amount,
                    'amount_octas': amount_octas,
                    'sequence_number': sequence_number,
                    'expiration_timestamp_secs': expiration_timestamp_secs,
                    'max_gas_amount': 2000,
                    'gas_unit_price': 100,
                    'chain_id': self.chain_id,
                    'raw_tx': raw_tx
                }
                
                if data:
                    tx_data['data'] = data
            
            logger.debug(f"Created transaction: {tx_data}")
            return tx_data
            
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
        """Sign an Aptos transaction.
        
        Args:
            transaction: Transaction object from create_transaction
            private_key: Private key for signing (optional)
            
        Returns:
            Dict: Signed transaction object ready for broadcasting
            
        Raises:
            ValidationError: If transaction is invalid
            TransactionError: If signing fails
            WalletError: If private key is invalid
        """
        self._verify_connection()
        
        # Use provided private key or the one from the connected account
        if private_key:
            if not self.validate_private_key(private_key):
                raise WalletError("Invalid private key")
            signer = AptosAccount.load_key(private_key)
        else:
            if not self.account:
                raise WalletError("No account available for signing")
            signer = self.account
            
        try:
            # Get the raw transaction
            if 'raw_tx' not in transaction:
                raise ValidationError("Invalid transaction: missing raw transaction")
                
            raw_tx = transaction['raw_tx']
            
            # Sign the transaction
            signed_tx = SignedTransaction(
                raw_tx,
                signer.public_key(),
                signer.sign(raw_tx.keyed())
            )
            
            # Convert to a hex string for transmission
            signed_tx_bytes = signed_tx.bytes()
            signed_tx_hex = signed_tx_bytes.hex()
            
            # Calculate the transaction hash
            tx_hash = hashlib.sha3_256(signed_tx_bytes).hexdigest()
            
            # Return the signed transaction
            result = {
                'txid': tx_hash,
                'hash': tx_hash,
                'sender': transaction['sender'],
                'recipient': transaction['recipient'],
                'amount': transaction['amount'],
                'type': transaction['type'],
                'signed_tx': signed_tx_hex,
                'sequence_number': transaction['sequence_number']
            }
            
            if 'data' in transaction:
                result['data'] = transaction['data']
            
            logger.debug(f"Signed transaction: {result['txid']}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast a signed Aptos transaction.
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            Dict: Transaction result with hash and status
            
        Raises:
            ValidationError: If signed transaction is invalid
            TransactionError: If broadcasting fails
        """
        self._verify_connection()
        
        # Validate the signed transaction
        if 'signed_tx' not in signed_transaction:
            raise ValidationError("Invalid signed transaction: missing 'signed_tx' field")
            
        try:
            # Convert hex to bytes
            signed_tx_bytes = bytes.fromhex(signed_transaction['signed_tx'])
            
            # Submit the transaction
            result = self.rest_client.submit_bcs_transaction(signed_tx_bytes)
            
            # Get the transaction hash
            tx_hash = signed_transaction['hash']
            
            # Wait for transaction confirmation
            tx_result = self.rest_client.wait_for_transaction(tx_hash)
            
            # Check if the transaction was successful
            is_success = True if 'success' in tx_result and tx_result['success'] else False
            
            # Extract useful information from the result
            status = 'success' if is_success else 'failed'
            vm_status = tx_result.get('vm_status', '')
            timestamp = tx_result.get('timestamp', '')
            gas_used = tx_result.get('gas_used', '0')
            
            tx_response = {
                'txid': tx_hash,
                'hash': tx_hash,
                'status': status,
                'confirmed': is_success,
                'sender': signed_transaction['sender'],
                'recipient': signed_transaction['recipient'],
                'amount': signed_transaction['amount'],
                'explorer_url': self.explorer_tx_url().format(txid=tx_hash),
                'vm_status': vm_status,
                'timestamp': timestamp,
                'gas_used': gas_used,
                'raw_data': tx_result
            }
            
            if 'data' in signed_transaction:
                tx_response['data'] = signed_transaction['data']
            
            logger.info(f"Broadcast transaction: {tx_response['txid']} - Status: {tx_response['status']}")
            return tx_response
            
        except Exception as e:
            error_msg = f"Failed to broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_id: str) -> Dict:
        """Get the status of an Aptos transaction.
        
        Args:
            tx_id: Transaction hash to check
            
        Returns:
            Dict: Transaction status and details
            
        Raises:
            ValidationError: If tx_id is invalid
            TransactionError: If status check fails
        """
        self._verify_connection()
        
        if not tx_id:
            raise ValidationError("Invalid transaction hash")
            
        try:
            # Query transaction
            tx_result = self.rest_client.transaction_by_hash(tx_id)
            
            # Check if the transaction was successful
            is_success = True if 'success' in tx_result and tx_result['success'] else False
            
            # Extract useful information from the result
            status = 'success' if is_success else 'failed'
            vm_status = tx_result.get('vm_status', '')
            timestamp = tx_result.get('timestamp', '')
            gas_used = tx_result.get('gas_used', '0')
            
            # Get transaction type and participants
            sender = tx_result.get('sender', '')
            
            # Try to extract recipient from payload
            recipient = ''
            try:
                if 'payload' in tx_result and 'arguments' in tx_result['payload']:
                    recipient = tx_result['payload']['arguments'][0]
            except Exception:
                pass
                
            # Try to extract amount from payload
            amount = 0
            try:
                if 'payload' in tx_result and 'arguments' in tx_result['payload']:
                    amount_octas = int(tx_result['payload']['arguments'][1])
                    amount = Decimal(amount_octas) / Decimal(10**8)
            except Exception:
                pass
                
            tx_status = {
                'txid': tx_id,
                'hash': tx_id,
                'status': status,
                'confirmed': is_success,
                'sender': sender,
                'recipient': recipient,
                'amount': amount,
                'explorer_url': self.explorer_tx_url().format(txid=tx_id),
                'vm_status': vm_status,
                'timestamp': timestamp,
                'gas_used': gas_used
            }
            
            return tx_status
            
        except Exception as e:
            # If transaction not found or other error
            logger.debug(f"Error checking transaction status: {str(e)}")
            
            # Return unknown status
            return {
                'txid': tx_id,
                'hash': tx_id,
                'status': 'unknown',
                'confirmed': False,
                'explorer_url': self.explorer_tx_url().format(txid=tx_id)
            }
            
    @strict_blockchain_operation
    def get_network_status(self) -> Dict:
        """Get Aptos network status.
        
        Returns:
            Dict: Network status information
            
        Raises:
            BlockchainConnectionError: If status check fails
        """
        self._verify_connection()
        
        try:
            # Get ledger information
            ledger_info = self.rest_client.get_ledger_information()
            
            # Extract useful information
            result = {
                'network': self.network_name,
                'chain_id': ledger_info.get('chain_id', self.chain_id),
                'epoch': ledger_info.get('epoch', '0'),
                'ledger_version': ledger_info.get('ledger_version', '0'),
                'ledger_timestamp': ledger_info.get('ledger_timestamp', '0'),
                'node_role': ledger_info.get('node_role', 'unknown'),
                'active': True
            }
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, transaction: Dict = None) -> Dict:
        """Estimate fees for an Aptos transaction.
        
        Args:
            transaction: Optional transaction to estimate fee for
            
        Returns:
            Dict: Fee estimation in different speeds
            
        Raises:
            ValidationError: If transaction is invalid
            TransactionError: If fee estimation fails
        """
        self._verify_connection()
        
        try:
            # Get gas price estimates
            gas_price_estimates = {
                'slow': 100,      # Gas unit price (GUP)
                'average': 150,
                'fast': 200
            }
            
            # Standard gas limits
            gas_limits = {
                'transfer': 2000,  # Simple transfer
                'token_transfer': 5000,  # Token transfer
                'contract_call': 10000,  # Contract interaction
            }
            
            # Calculate costs in APT
            costs = {}
            for speed, gas_price in gas_price_estimates.items():
                # Cost = gas_limit * gas_price / 10^8
                cost = Decimal(gas_limits['transfer'] * gas_price) / Decimal(10**8)
                costs[speed] = cost
                
            # Create fee structure
            fee_structure = {
                'slow': costs['slow'],
                'average': costs['average'],
                'fast': costs['fast'],
                'gas_limit_transfer': gas_limits['transfer'],
                'gas_limit_token_transfer': gas_limits['token_transfer'],
                'gas_limit_contract_call': gas_limits['contract_call'],
                'gas_price_slow': gas_price_estimates['slow'],
                'gas_price_average': gas_price_estimates['average'],
                'gas_price_fast': gas_price_estimates['fast'],
                'unit': 'APT'
            }
            
            # If a specific transaction is provided, estimate its fee
            if transaction and 'type' in transaction:
                tx_type = transaction.get('type')
                gas_limit = gas_limits.get(tx_type.replace('apt_', ''), gas_limits['transfer'])
                fee_structure['estimated_gas_limit'] = gas_limit
                fee_structure['estimated_fee'] = costs['average']
            
            return fee_structure
            
        except Exception as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
