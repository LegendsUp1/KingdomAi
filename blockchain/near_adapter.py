#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NEAR Protocol blockchain adapter implementation.
Native, no-fallback adapter for NEAR Protocol integration.
"""

import os
import json
import time
import base64
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

# Import NEAR specific libraries
try:
    import near_api_py
    from near_api_py.account import Account
    from near_api_py.transaction import (
        Transaction, SignedTransaction,
        CreateAccountAction, DeleteAccountAction,
        DeployContractAction, FunctionCallAction,
        TransferAction, StakeAction,
        AddKeyAction, DeleteKeyAction
    )
    from near_api_py.signer import KeyPair, Signer
    from near_api_py.providers import JsonProvider
    from near_api_py.exceptions import (
        TransactionReject, TransactionTimeout,
        InvalidAccountId, InvalidPrivateKey
    )
    
    NEAR_AVAILABLE = True
except ImportError:
    NEAR_AVAILABLE = False
    
# Import logging
import logging
logger = logging.getLogger(__name__)


class NearAdapter(BlockchainAdapter):
    """Native NEAR Protocol blockchain adapter.
    
    Implements all required blockchain operations for NEAR Protocol
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'NEAR Mainnet',
            'node_url': 'https://rpc.mainnet.near.org',
            'wallet_url': 'https://wallet.near.org',
            'helper_url': 'https://helper.mainnet.near.org',
            'explorer_url': 'https://explorer.mainnet.near.org'
        },
        'testnet': {
            'name': 'NEAR Testnet',
            'node_url': 'https://rpc.testnet.near.org',
            'wallet_url': 'https://wallet.testnet.near.org',
            'helper_url': 'https://helper.testnet.near.org',
            'explorer_url': 'https://explorer.testnet.near.org'
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'NEAR': {
            'name': 'NEAR',
            'symbol': 'NEAR',
            'decimals': 24,
            'is_native': True
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize NEAR Protocol adapter.
        
        Args:
            network: Network name ('mainnet' or 'testnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid or NEAR API is unavailable
        """
        if not NEAR_AVAILABLE:
            raise ValidationError("NEAR API Python package is not available. "
                                 "Install with 'pip install near-api-py'")
        
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid NEAR network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.node_url = self.NETWORKS[network]['node_url']
        self.wallet_url = self.NETWORKS[network]['wallet_url']
        self.helper_url = self.NETWORKS[network]['helper_url']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        
        # Set connection state
        self.is_connected = False
        self.provider = None
        
        # Account and key management
        self.account_id = None
        self.private_key = None
        self.public_key = None
        self.key_pair = None
        self.signer = None
        self.account = None
        
        # Override config if provided
        if config:
            if 'node_url' in config:
                self.node_url = config['node_url']
            
            if 'account_id' in config:
                self.account_id = config['account_id']
                
            if 'private_key' in config:
                self.private_key = config['private_key']
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        account_info = f", Account: {self.account_id}" if self.account_id else ""
        return f"NEAR Adapter ({self.network_name}) - {connection_status}{account_info}"
        
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/transactions/{{txid}}"
        
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/accounts/{{address}}"
        
    def _verify_connection(self) -> bool:
        """Verify connection to NEAR network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.provider:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Check if provider is responsive by calling a simple method
            status = self.provider.get_status()
            return True
        except Exception as e:
            self.is_connected = False
            error_msg = f"Connection to {self.network_name} failed: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to NEAR Protocol network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Create JSON RPC provider
            self.provider = JsonProvider(self.node_url)
            
            # Test the connection
            status = self.provider.get_status()
            logger.info(f"Connected to {self.network_name}, chain ID: {status['chain_id']}")
            
            # If account_id and private_key are provided, initialize the account
            if self.account_id and self.private_key:
                # Create KeyPair and Signer
                self.key_pair = KeyPair.from_string(self.private_key)
                self.signer = Signer(self.account_id, self.key_pair)
                
                # Initialize the account
                self.account = Account(self.provider, self.signer, self.account_id)
                logger.info(f"Initialized account: {self.account_id}")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from NEAR Protocol network.
        
        Returns:
            bool: True if disconnected successfully
        """
        try:
            # Reset connection state
            self.provider = None
            self.account = None
            self.is_connected = False
            logger.info(f"Disconnected from {self.network_name}")
            return True
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            return False
            
    def validate_address(self, address: str) -> bool:
        """Validate NEAR account ID format.
        
        Args:
            address: NEAR account ID to validate
            
        Returns:
            bool: True if account ID is valid
        """
        if not address:
            return False
            
        try:
            # NEAR account IDs follow specific rules:
            # 1. Must consist of lowercase alphanumeric characters, '-' or '_'
            # 2. Must be between 2-64 characters
            # 3. Accounts with '.' must be subaccounts of a top-level account
            
            # Basic validation
            if len(address) < 2 or len(address) > 64:
                return False
                
            # Check valid characters
            valid_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-_.")
            if not all(c in valid_chars for c in address):
                return False
                
            # Additional rules for account IDs with '.'
            if '.' in address:
                parts = address.split('.')
                if len(parts) < 2:
                    return False
                    
            return True
            
        except Exception as e:
            logger.debug(f"Address validation error: {str(e)}")
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate NEAR private key format.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Attempt to create a key pair with the private key
            key_pair = KeyPair.from_string(private_key)
            return True
        except Exception as e:
            logger.debug(f"Invalid private key format: {str(e)}")
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str = None, token_id: str = None) -> Decimal:
        """Get NEAR balance for an account.
        
        Args:
            address: NEAR account ID to query, defaults to connected account
            token_id: Optional token ID (not used for native NEAR)
            
        Returns:
            Decimal: Balance in NEAR
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        self._verify_connection()
        
        # Use the provided address or the account_id from the connection
        account_id = address or self.account_id
        
        if not account_id:
            raise ValidationError("No account ID provided and no account connected")
            
        if not self.validate_address(account_id):
            raise ValidationError(f"Invalid NEAR account ID: {account_id}")
            
        try:
            # Query account balance
            account_info = self.provider.get_account(account_id)
            
            # Convert from yoctoNEAR (10^-24) to NEAR
            balance_yocto = Decimal(account_info['amount'])
            balance_near = balance_yocto / Decimal(10**24)
            
            logger.debug(f"Balance for {account_id}: {balance_near} NEAR")
            return balance_near
            
        except Exception as e:
            error_msg = f"Failed to get balance for {account_id}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e

    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
        """Create a NEAR Protocol transaction.
        
        Args:
            transaction: Transaction parameters
                - to_address: Recipient account ID
                - amount: Amount in NEAR
                - method_name: Optional function name to call (for contract calls)
                - args: Optional arguments for function call (for contract calls)
                - gas: Optional gas limit
            
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
        method_name = transaction.get('method_name')
        args = transaction.get('args', {})
        gas = transaction.get('gas', 100_000_000_000_000)  # Default 100 TGas
        
        # Validate recipient address
        if not to_address or not self.validate_address(to_address):
            raise ValidationError(f"Invalid recipient account ID: {to_address}")
            
        # Get the sender account ID
        from_address = self.account_id
        if not from_address:
            raise ValidationError("No account connected. Cannot create transaction.")
        
        try:
            # Create the transaction object
            if method_name:
                # This is a function call
                tx_data = {
                    'sender_id': from_address,
                    'receiver_id': to_address,
                    'method': method_name,
                    'args': args,
                    'amount': amount,
                    'gas': gas
                }
            else:
                # This is a simple transfer
                tx_data = {
                    'sender_id': from_address,
                    'receiver_id': to_address,
                    'amount': amount,
                    'gas': gas
                }
            
            logger.debug(f"Created transaction: {tx_data}")
            return tx_data
            
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
        """Sign a NEAR Protocol transaction.
        
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
        
        # Use provided private key or the one from the connection
        if private_key:
            if not self.validate_private_key(private_key):
                raise WalletError("Invalid private key")
            key_pair = KeyPair.from_string(private_key)
            signer = Signer(self.account_id, key_pair)
        else:
            if not self.signer or not self.key_pair:
                raise WalletError("No private key available for signing")
            signer = self.signer
            
        try:
            # Extract transaction data
            sender_id = transaction.get('sender_id')
            receiver_id = transaction.get('receiver_id')
            amount = transaction.get('amount', 0)
            gas = transaction.get('gas', 100_000_000_000_000)
            method = transaction.get('method')
            args = transaction.get('args', {})
            
            # Convert amount from NEAR to yoctoNEAR (10^24)
            amount_yocto = int(Decimal(amount) * Decimal(10**24))
            
            # Get account details for nonce and block hash
            sender_account = self.provider.get_account(sender_id)
            current_block = self.provider.get_block({'finality': 'final'})
            block_hash = base64.b64decode(current_block['header']['hash'])
            
            # Create actions based on transaction type
            if method:
                # Function call action
                actions = [
                    FunctionCallAction(
                        method_name=method,
                        args=json.dumps(args).encode('utf-8'),
                        gas=gas,
                        deposit=amount_yocto
                    )
                ]
            else:
                # Transfer action
                actions = [
                    TransferAction(amount=amount_yocto)
                ]
            
            # Create and sign the transaction
            nonce = sender_account['nonce'] + 1
            
            tx = Transaction(
                sender_id=sender_id,
                receiver_id=receiver_id,
                nonce=nonce,
                block_hash=block_hash,
                actions=actions
            )
            
            signed_tx = tx.sign(signer)
            encoded_tx = signed_tx.to_base64()
            
            # Return the signed transaction
            result = {
                'txid': signed_tx.hash,
                'sender': sender_id,
                'receiver': receiver_id,
                'signed_tx': encoded_tx,
                'raw_tx': {
                    'hash': signed_tx.hash,
                    'sender_id': sender_id,
                    'receiver_id': receiver_id,
                    'nonce': nonce,
                    'actions': [str(a) for a in actions],
                    'signature': signed_tx.signature
                }
            }
            
            logger.debug(f"Signed transaction: {result['txid']}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast a signed NEAR transaction.
        
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
            # Send the transaction
            encoded_tx = signed_transaction['signed_tx']
            result = self.provider.send_tx_and_wait(encoded_tx)
            
            # Extract the transaction status
            status = result.get('status', {})
            is_success = 'SuccessValue' in status
            
            tx_result = {
                'txid': signed_transaction['txid'],
                'hash': signed_transaction['txid'],
                'status': 'success' if is_success else 'failed',
                'confirmed': True,
                'sender': signed_transaction['sender'],
                'receiver': signed_transaction['receiver'],
                'explorer_url': self.explorer_tx_url().format(txid=signed_transaction['txid']),
                'raw_data': result
            }
            
            logger.info(f"Broadcast transaction: {tx_result['txid']} - Status: {tx_result['status']}")
            return tx_result
            
        except Exception as e:
            error_msg = f"Failed to broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_id: str) -> Dict:
        """Get the status of a NEAR transaction.
        
        Args:
            tx_id: Transaction ID/hash to check
            
        Returns:
            Dict: Transaction status and details
            
        Raises:
            ValidationError: If tx_id is invalid
            TransactionError: If status check fails
        """
        self._verify_connection()
        
        if not tx_id:
            raise ValidationError("Invalid transaction ID")
            
        try:
            # Query transaction status
            result = self.provider.get_transaction(tx_id)
            
            # Extract status
            status = result.get('status', {})
            is_success = 'SuccessValue' in status
            
            # Extract transaction details
            sender = result.get('transaction', {}).get('signer_id', '')
            receiver = result.get('transaction', {}).get('receiver_id', '')
            
            tx_status = {
                'txid': tx_id,
                'hash': tx_id,
                'status': 'success' if is_success else 'failed',
                'confirmed': True if result.get('status') else False,
                'sender': sender,
                'receiver': receiver,
                'explorer_url': self.explorer_tx_url().format(txid=tx_id),
                'raw_data': result
            }
            
            return tx_status
            
        except Exception as e:
            # If transaction not found, return unknown status
            if "does not exist" in str(e):
                return {
                    'txid': tx_id,
                    'hash': tx_id,
                    'status': 'unknown',
                    'confirmed': False,
                    'explorer_url': self.explorer_tx_url().format(txid=tx_id)
                }
                
            error_msg = f"Failed to get transaction status: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_network_status(self) -> Dict:
        """Get NEAR network status.
        
        Returns:
            Dict: Network status information
            
        Raises:
            BlockchainConnectionError: If status check fails
        """
        self._verify_connection()
        
        try:
            # Get network status
            status = self.provider.get_status()
            
            # Get validator information
            validators = self.provider.get_validators()
            
            # Extract useful information
            result = {
                'network': self.network_name,
                'chain_id': status['chain_id'],
                'protocol_version': status['protocol_version'],
                'latest_block_height': status['sync_info']['latest_block_height'],
                'latest_block_time': status['sync_info']['latest_block_time'],
                'syncing': status['sync_info']['syncing'],
                'validator_count': len(validators['current_validators']),
                'active': True
            }
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, transaction: Dict = None) -> Dict:
        """Estimate fees for a NEAR transaction.
        
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
            # NEAR uses a constant gas price model
            # The gas price is fixed by the protocol and doesn't fluctuate based on network congestion
            gas_price = self.provider.get_gas_price(None)
            
            # Default gas limits for common operations
            gas_limits = {
                'transfer': 100_000_000_000_000,  # 100 TGas
                'function_call': 300_000_000_000_000,  # 300 TGas
                'create_account': 200_000_000_000_000,  # 200 TGas
                'add_key': 100_000_000_000_000,  # 100 TGas
                'delete_key': 100_000_000_000_000,  # 100 TGas
                'delete_account': 100_000_000_000_000,  # 100 TGas
            }
            
            # Calculate costs in yoctoNEAR
            costs = {}
            for operation, gas in gas_limits.items():
                cost_yocto = int(gas) * int(gas_price['gas_price'])
                # Convert from yoctoNEAR to NEAR
                cost_near = Decimal(cost_yocto) / Decimal(10**24)
                costs[operation] = cost_near
                
            # Standard fee structure (NEAR doesn't have variable fee speeds)
            fee_structure = {
                'slow': costs['transfer'],
                'average': costs['transfer'],
                'fast': costs['transfer'],
                'function_call': costs['function_call'],
                'create_account': costs['create_account'],
                'gas_price': Decimal(gas_price['gas_price']) / Decimal(10**24),
                'unit': 'NEAR'
            }
            
            return fee_structure
            
        except Exception as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
