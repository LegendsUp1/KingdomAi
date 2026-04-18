#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hedera blockchain adapter implementation.
Native, no-fallback adapter for Hedera Hashgraph integration.
"""

import os
import json
import time
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

# Import Hedera specific libraries
try:
    from hedera import (
        Client, AccountId, PrivateKey, PublicKey,
        TransactionId, Hbar, HbarUnit, 
        AccountBalanceQuery, TransactionReceiptQuery,
        TransferTransaction, AccountCreateTransaction,
        TokenCreateTransaction, TokenAssociateTransaction,
        TokenTransferTransaction, TokenId,
        Status, AccountInfoQuery, NetworkName
    )
    HEDERA_AVAILABLE = True
except ImportError:
    HEDERA_AVAILABLE = False
    
# Import logging
import logging
logger = logging.getLogger(__name__)


class HederaAdapter(BlockchainAdapter):
    """Native Hedera blockchain adapter.
    
    Implements all required blockchain operations for Hedera Hashgraph
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Hedera Mainnet',
            'network': NetworkName.MAINNET,
            'explorer_url': 'https://hashscan.io/mainnet',
            'mirror_node': 'https://mainnet-public.mirrornode.hedera.com/api/v1'
        },
        'testnet': {
            'name': 'Hedera Testnet',
            'network': NetworkName.TESTNET,
            'explorer_url': 'https://hashscan.io/testnet',
            'mirror_node': 'https://testnet.mirrornode.hedera.com/api/v1'
        },
        'previewnet': {
            'name': 'Hedera Previewnet',
            'network': NetworkName.PREVIEWNET,
            'explorer_url': 'https://hashscan.io/previewnet',
            'mirror_node': 'https://previewnet.mirrornode.hedera.com/api/v1'
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'HBAR': {
            'name': 'Hedera Hashgraph',
            'symbol': 'HBAR',
            'decimals': 8,
            'is_native': True
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Hedera adapter.
        
        Args:
            network: Network name ('mainnet', 'testnet', or 'previewnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid or Hedera SDK is unavailable
        """
        if not HEDERA_AVAILABLE:
            raise ValidationError("Hedera SDK is not available. "
                                 "Install with 'pip install hedera-sdk-py'")
        
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Hedera network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.hedera_network = self.NETWORKS[network]['network']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.mirror_node = self.NETWORKS[network]['mirror_node']
        
        # Set connection state
        self.is_connected = False
        self.client = None
        
        # Account and key management
        self.account_id = None
        self.private_key = None
        self.operator_id = None
        self.operator_key = None
        
        # Override config if provided
        if config:
            if 'operator_id' in config:
                self.operator_id = config['operator_id']
                
            if 'operator_key' in config:
                self.operator_key = config['operator_key']
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        account_info = f", Account: {self.account_id}" if self.account_id else ""
        return f"Hedera Adapter ({self.network_name}) - {connection_status}{account_info}"
        
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/transaction/{{txid}}"
        
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/account/{{address}}"
        
    def _verify_connection(self) -> bool:
        """Verify connection to Hedera network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Check if client is responsive by calling a simple query
            # Hedera requires an operator account for all operations
            if not self.operator_id:
                raise BlockchainConnectionError("No operator account configured")
                
            # Query operator account info to verify connection
            query = AccountInfoQuery().setAccountId(self.operator_id)
            query.execute(self.client)
            
            return True
        except Exception as e:
            self.is_connected = False
            error_msg = f"Connection to {self.network_name} failed: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Hedera network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Create client for the selected network
            if self.operator_id and self.operator_key:
                # Convert string representations to Hedera types
                operator_id = AccountId.fromString(self.operator_id)
                operator_key = PrivateKey.fromString(self.operator_key)
                
                # Create client with operator
                self.client = Client.forName(self.hedera_network)
                self.client.setOperator(operator_id, operator_key)
                
                # Set account_id to operator_id
                self.account_id = self.operator_id
                
                logger.info(f"Connected to {self.network_name} with operator {self.operator_id}")
            else:
                # Create client without operator
                self.client = Client.forName(self.hedera_network)
                logger.info(f"Connected to {self.network_name} without operator")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from Hedera network.
        
        Returns:
            bool: True if disconnected successfully
        """
        try:
            if self.client:
                self.client.close()
                
            # Reset connection state
            self.client = None
            self.is_connected = False
            logger.info(f"Disconnected from {self.network_name}")
            return True
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            return False
            
    def validate_address(self, address: str) -> bool:
        """Validate Hedera account ID format.
        
        Args:
            address: Hedera account ID to validate
            
        Returns:
            bool: True if account ID is valid
        """
        if not address:
            return False
            
        try:
            # Parse the account ID string
            AccountId.fromString(address)
            return True
        except Exception as e:
            logger.debug(f"Address validation error: {str(e)}")
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate Hedera private key format.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Attempt to create a private key object from the string
            PrivateKey.fromString(private_key)
            return True
        except Exception as e:
            logger.debug(f"Invalid private key format: {str(e)}")
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str = None, token_id: str = None) -> Decimal:
        """Get HBAR balance for an account.
        
        Args:
            address: Hedera account ID to query, defaults to operator account
            token_id: Optional token ID for querying token balance
            
        Returns:
            Decimal: Balance in HBAR or token units
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        self._verify_connection()
        
        # Use the provided address or the account_id from the connection
        account_id_str = address or self.account_id
        
        if not account_id_str:
            raise ValidationError("No account ID provided and no operator account configured")
            
        if not self.validate_address(account_id_str):
            raise ValidationError(f"Invalid Hedera account ID: {account_id_str}")
            
        try:
            # Parse the account ID
            account_id = AccountId.fromString(account_id_str)
            
            if token_id:
                # Query token balance
                token = TokenId.fromString(token_id)
                
                # We need to use the mirror node API for token balances
                url = f"{self.mirror_node}/accounts/{account_id_str}/tokens?token.id={token_id}"
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                
                if "tokens" in data and len(data["tokens"]) > 0:
                    balance = Decimal(data["tokens"][0]["balance"]) / Decimal(10 ** self.CURRENCY["HBAR"]["decimals"])
                    return balance
                else:
                    return Decimal(0)
            else:
                # Query HBAR balance
                balance_query = AccountBalanceQuery().setAccountId(account_id)
                balance = balance_query.execute(self.client)
                
                # Convert to Decimal
                balance_hbar = Decimal(balance.hbars.toTinybars()) / Decimal(100_000_000)  # 1 HBAR = 100,000,000 tinybars
                
                logger.debug(f"Balance for {account_id_str}: {balance_hbar} HBAR")
                return balance_hbar
                
        except Exception as e:
            error_msg = f"Failed to get balance for {account_id_str}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e

    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
        """Create a Hedera transaction.
        
        Args:
            transaction: Transaction parameters
                - to_address: Recipient account ID
                - amount: Amount in HBAR
                - token_id: Optional token ID for token transfers
                - memo: Optional memo/reference for the transaction
            
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
        memo = transaction.get('memo', '')
        
        # Validate recipient address
        if not to_address or not self.validate_address(to_address):
            raise ValidationError(f"Invalid recipient account ID: {to_address}")
            
        # Get the sender account ID
        from_address = self.account_id
        if not from_address:
            raise ValidationError("No operator account configured. Cannot create transaction.")
        
        try:
            # Parse account IDs
            sender_id = AccountId.fromString(from_address)
            recipient_id = AccountId.fromString(to_address)
            
            if token_id:
                # Token transfer transaction
                token = TokenId.fromString(token_id)
                
                # Convert amount from token units to lowest denomination
                decimals = self.CURRENCY["HBAR"]["decimals"]  # Use token decimals if available
                amount_lowest = int(Decimal(amount) * Decimal(10 ** decimals))
                
                # Create the token transfer transaction
                tx = TokenTransferTransaction()
                tx.setTokenId(token)
                tx.addSender(sender_id, amount_lowest)
                tx.addRecipient(recipient_id, amount_lowest)
                
                if memo:
                    tx.setTransactionMemo(memo)
                    
                # Freeze the transaction for signing
                tx_bytes = tx.freezeWith(self.client).toBytes()
                
                tx_data = {
                    'type': 'token_transfer',
                    'sender': from_address,
                    'recipient': to_address,
                    'amount': amount,
                    'token_id': token_id,
                    'memo': memo,
                    'tx_bytes': tx_bytes.hex()
                }
            else:
                # HBAR transfer transaction
                # Convert amount from HBAR to tinybars
                amount_hbar = Hbar.fromTinybars(int(Decimal(amount) * Decimal(100_000_000)))
                
                # Create the transfer transaction
                tx = TransferTransaction()
                tx.addHbarTransfer(sender_id, amount_hbar.negated())
                tx.addHbarTransfer(recipient_id, amount_hbar)
                
                if memo:
                    tx.setTransactionMemo(memo)
                    
                # Freeze the transaction for signing
                tx_bytes = tx.freezeWith(self.client).toBytes()
                
                tx_data = {
                    'type': 'hbar_transfer',
                    'sender': from_address,
                    'recipient': to_address,
                    'amount': amount,
                    'memo': memo,
                    'tx_bytes': tx_bytes.hex()
                }
            
            logger.debug(f"Created transaction: {tx_data}")
            return tx_data
            
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
        """Sign a Hedera transaction.
        
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
        
        # Use provided private key or the operator key
        key_to_use = private_key or self.operator_key
        if not key_to_use:
            raise WalletError("No private key available for signing")
            
        if not self.validate_private_key(key_to_use):
            raise WalletError("Invalid private key")
            
        try:
            # Convert the private key string to a PrivateKey object
            signer_key = PrivateKey.fromString(key_to_use)
            
            # Get the transaction bytes
            tx_bytes = bytes.fromhex(transaction['tx_bytes'])
            
            # Deserialize the transaction
            tx = Transaction.fromBytes(tx_bytes)
            
            # Sign the transaction
            signed_tx = tx.sign(signer_key)
            
            # Get the transaction ID
            tx_id = signed_tx.getTransactionId().toString()
            
            # Convert the signed transaction to bytes
            signed_tx_bytes = signed_tx.toBytes()
            
            # Return the signed transaction
            result = {
                'txid': tx_id,
                'sender': transaction['sender'],
                'recipient': transaction['recipient'],
                'amount': transaction['amount'],
                'type': transaction['type'],
                'signed_tx': signed_tx_bytes.hex()
            }
            
            if 'token_id' in transaction:
                result['token_id'] = transaction['token_id']
                
            if 'memo' in transaction:
                result['memo'] = transaction['memo']
            
            logger.debug(f"Signed transaction: {result['txid']}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast a signed Hedera transaction.
        
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
            # Convert the signed transaction bytes to a Transaction object
            signed_tx_bytes = bytes.fromhex(signed_transaction['signed_tx'])
            signed_tx = Transaction.fromBytes(signed_tx_bytes)
            
            # Submit the transaction
            tx_response = signed_tx.execute(self.client)
            
            # Get the transaction ID
            tx_id = signed_tx.getTransactionId().toString()
            
            # Get the receipt
            receipt = tx_response.getReceipt(self.client)
            status = receipt.status.toString()
            
            tx_result = {
                'txid': tx_id,
                'hash': tx_id,
                'status': 'success' if status == 'SUCCESS' else 'failed',
                'confirmed': status == 'SUCCESS',
                'sender': signed_transaction['sender'],
                'recipient': signed_transaction['recipient'],
                'amount': signed_transaction['amount'],
                'type': signed_transaction['type'],
                'explorer_url': self.explorer_tx_url().format(txid=tx_id),
                'hedera_status': status
            }
            
            if 'token_id' in signed_transaction:
                tx_result['token_id'] = signed_transaction['token_id']
                
            if 'memo' in signed_transaction:
                tx_result['memo'] = signed_transaction['memo']
            
            logger.info(f"Broadcast transaction: {tx_result['txid']} - Status: {tx_result['status']}")
            return tx_result
            
        except Exception as e:
            error_msg = f"Failed to broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_id: str) -> Dict:
        """Get the status of a Hedera transaction.
        
        Args:
            tx_id: Transaction ID to check
            
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
            # Parse the transaction ID
            transaction_id = TransactionId.fromString(tx_id)
            
            # Query the receipt
            receipt_query = TransactionReceiptQuery()
            receipt_query.setTransactionId(transaction_id)
            receipt = receipt_query.execute(self.client)
            
            # Get the status
            status = receipt.status.toString()
            
            # Try to get more details from the mirror node
            try:
                url = f"{self.mirror_node}/transactions/{tx_id}"
                response = requests.get(url)
                response.raise_for_status()
                tx_data = response.json()
                
                sender = tx_data.get('from', '')
                recipient = tx_data.get('to', '')
                amount = Decimal(tx_data.get('amount', 0)) / Decimal(100_000_000)
                timestamp = tx_data.get('consensus_timestamp', '')
                
                tx_type = tx_data.get('name', 'CRYPTOCURRENCYTRANSFER')
                
            except Exception:
                # If mirror node query fails, use basic information
                sender = ''
                recipient = ''
                amount = Decimal(0)
                timestamp = ''
                tx_type = 'unknown'
            
            tx_status = {
                'txid': tx_id,
                'hash': tx_id,
                'status': 'success' if status == 'SUCCESS' else 'failed',
                'confirmed': True,
                'sender': sender,
                'recipient': recipient,
                'amount': amount,
                'timestamp': timestamp,
                'type': tx_type,
                'explorer_url': self.explorer_tx_url().format(txid=tx_id),
                'hedera_status': status
            }
            
            return tx_status
            
        except Exception as e:
            # If transaction not found or other error
            error_msg = f"Failed to get transaction status: {str(e)}"
            logger.error(error_msg)
            
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
        """Get Hedera network status.
        
        Returns:
            Dict: Network status information
            
        Raises:
            BlockchainConnectionError: If status check fails
        """
        self._verify_connection()
        
        try:
            # Get network status from mirror node
            url = f"{self.mirror_node}/network"
            response = requests.get(url)
            response.raise_for_status()
            network_data = response.json()
            
            # Extract useful information
            result = {
                'network': self.network_name,
                'node_count': network_data.get('node_count', 0),
                'staking_period_start': network_data.get('staking_period_start', ''),
                'staking_period_end': network_data.get('staking_period_end', ''),
                'active': True
            }
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, transaction: Dict = None) -> Dict:
        """Estimate fees for a Hedera transaction.
        
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
            # Hedera uses a fixed fee schedule
            # These are approximate values as of July 2025
            fee_structure = {
                'slow': Decimal('0.0001'),      # 0.0001 HBAR
                'average': Decimal('0.0005'),   # 0.0005 HBAR
                'fast': Decimal('0.001'),       # 0.001 HBAR
                'crypto_transfer': Decimal('0.0001'),
                'token_transfer': Decimal('0.0005'),
                'contract_call': Decimal('0.05'),
                'contract_create': Decimal('0.10'),
                'unit': 'HBAR'
            }
            
            # If a specific transaction is provided, estimate its fee
            if transaction:
                tx_type = transaction.get('type', '')
                
                if tx_type == 'token_transfer':
                    return {
                        'estimated': fee_structure['token_transfer'],
                        'slow': fee_structure['slow'],
                        'average': fee_structure['average'],
                        'fast': fee_structure['fast'],
                        'unit': 'HBAR'
                    }
                elif tx_type == 'hbar_transfer':
                    return {
                        'estimated': fee_structure['crypto_transfer'],
                        'slow': fee_structure['slow'],
                        'average': fee_structure['average'],
                        'fast': fee_structure['fast'],
                        'unit': 'HBAR'
                    }
            
            # Default fee structure
            return fee_structure
            
        except Exception as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
