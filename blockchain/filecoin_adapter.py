#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Filecoin blockchain adapter implementation.
Native, no-fallback adapter for Filecoin network integration.
"""

import os
import json
import time
import base64
import binascii
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

# Import Filecoin specific libraries
import filecoin
from filecoin.wallet import LocalWallet
from filecoin.client import FilecoinClient
from filecoin.exceptions import FilecoinException
from filecoin.encoding import to_base32 
from filecoin.utils import verify_signature

# Import networking libraries for API calls
import requests
from requests.exceptions import RequestException

# Import bip keys handling
from mnemonic import Mnemonic
import bip32utils

# Import cryptographic libraries
import hashlib
import ecdsa

# Import logging
import logging
logger = logging.getLogger(__name__)


class FilecoinAdapter(BlockchainAdapter):
    """Native Filecoin blockchain adapter.
    
    Implements all required blockchain operations for Filecoin network
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Filecoin Mainnet',
            'api_url': 'https://api.node.glif.io/rpc/v0',
            'explorer_url': 'https://filfox.info',
            'chain_id': 'mainnet',
            'network_prefix': 'f',
        },
        'testnet': {
            'name': 'Filecoin Testnet',
            'api_url': 'https://api.calibration.node.glif.io/rpc/v0',
            'explorer_url': 'https://calibration.filfox.info',
            'chain_id': 'calibrationnet',
            'network_prefix': 't',
        },
        'devnet': {
            'name': 'Filecoin Devnet',
            'api_url': 'http://localhost:1234/rpc/v0',
            'explorer_url': 'http://localhost:8080',
            'chain_id': 'devnet',
            'network_prefix': 'd',
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'FIL': {
            'name': 'Filecoin',
            'symbol': 'FIL',
            'decimals': 18,  # 1 FIL = 10^18 attoFIL
            'min_fee': 0.00001  # Minimum transaction fee
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Filecoin adapter.
        
        Args:
            network: Network name ('mainnet', 'testnet', or 'devnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid
        """
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Filecoin network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.api_url = self.NETWORKS[network]['api_url']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.chain_id = self.NETWORKS[network]['chain_id']
        self.network_prefix = self.NETWORKS[network]['network_prefix']
        
        # Authentication for API
        self.api_token = None
        
        # Set currency details (FIL)
        self.currency = self.CURRENCY['FIL']
        
        # Set connection state
        self.is_connected = False
        self.client = None
        self.wallet = None
        
        # Override config if provided
        if config:
            if 'api_url' in config:
                self.api_url = config['api_url']
                
            if 'api_token' in config:
                self.api_token = config['api_token']
                
            if 'private_key' in config:
                self.private_key = config.get('private_key')
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        return f"FilecoinAdapter({self.network_name}, {connection_status})"
    
    @property
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/message/"
    
    @property
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/address/"
    
    @property
    def explorer_block_url(self) -> str:
        """Get block explorer URL template."""
        return f"{self.explorer_url}/tipset/"
    
    @strict_blockchain_operation
    def _verify_connection(self) -> bool:
        """Verify connection to Filecoin network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Verify client connection by getting chain head
            chain_head = self.client.get_chain_head()
            if not chain_head:
                raise BlockchainConnectionError("Failed to get chain head")
                
            return True
        except FilecoinException as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Filecoin network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize Filecoin client with API URL and authentication if provided
            headers = {}
            if self.api_token:
                headers['Authorization'] = f"Bearer {self.api_token}"
                
            self.client = FilecoinClient(
                api_url=self.api_url,
                headers=headers
            )
            
            # Initialize wallet if private key is provided
            if hasattr(self, 'private_key') and self.private_key:
                self.wallet = LocalWallet.from_private_key(self.private_key)
            
            # Verify connection
            self._verify_connection()
            
            # Set connection status
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}")
            
            return True
            
        except FilecoinException as e:
            self.is_connected = False
            self.client = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            self.is_connected = False
            self.client = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    def validate_address(self, address: str) -> bool:
        """Validate Filecoin address format.
        
        Args:
            address: Filecoin address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Check address format (should start with network prefix followed by type and payload)
            if not address.startswith(self.network_prefix):
                return False
                
            # Check length
            if len(address) < 3:
                return False
                
            # Check address type (should be 0, 1, 2, or 3)
            addr_type = address[1]
            if addr_type not in ['0', '1', '2', '3']:
                return False
                
            # For secp256k1 addresses (type 1), additional validation
            if addr_type == '1':
                # Expected length for secp256k1 addresses
                if len(address) != 41:
                    return False
            
            # For actor addresses (type 2), additional validation
            if addr_type == '2':
                # Expected length for actor addresses
                if len(address) != 41:
                    return False
                    
            return True
        except Exception:
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate Filecoin private key format.
        
        Args:
            private_key: Private key to validate (hex string)
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Check if it's a hex-encoded private key (64 chars)
            if len(private_key) == 64:
                # Try to convert to bytes
                try:
                    key_bytes = binascii.unhexlify(private_key)
                    if len(key_bytes) == 32:  # Should be 32 bytes
                        return True
                except binascii.Error:
                    return False
            
            # Check if it's a seed phrase (12-24 words)
            words = private_key.split()
            if 12 <= len(words) <= 24:
                try:
                    # Check if valid BIP39 mnemonic
                    mnemonic = Mnemonic("english")
                    if mnemonic.check(private_key):
                        return True
                except Exception:
                    pass
                    
            return False
        except Exception:
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str, token_id: str = None) -> Decimal:
        """Get FIL balance for address.
        
        Args:
            address: Filecoin address to query
            token_id: Ignored for Filecoin (no tokens)
            
        Returns:
            Decimal: Balance in FIL
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not self.validate_address(address):
            raise ValidationError(f"Invalid address format: {address}")
            
        try:
            # Get balance from the network
            balance_result = self.client.get_balance(address)
            
            if balance_result is None:
                raise BlockchainConnectionError(f"Failed to get balance for address {address}")
                
            # Convert balance from attoFIL to FIL
            balance_fil = Decimal(balance_result) / Decimal(10 ** self.currency['decimals'])
            
            return balance_fil
                
        except FilecoinException as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict) -> Dict:
        """Create Filecoin transaction.
        
        Args:
            transaction: Transaction details with the following fields:
                - to_address: Recipient address
                - from_address: Sender address
                - amount: Amount to send in FIL
                - gas_fee_cap: Optional gas fee cap
                - gas_premium: Optional gas premium
                - gas_limit: Optional gas limit
                - nonce: Optional nonce (will be auto-populated if not provided)
                - method: Optional method ID (0 for simple value transfer)
                - params: Optional parameters for the method call
                
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
            gas_fee_cap = transaction.get('gas_fee_cap')
            gas_premium = transaction.get('gas_premium')
            gas_limit = transaction.get('gas_limit')
            nonce = transaction.get('nonce')
            method = transaction.get('method', 0)  # Default: simple value transfer
            params = transaction.get('params', '')
            
            # Validate addresses
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            if not self.validate_address(from_address):
                raise ValidationError(f"Invalid sender address: {from_address}")
                
            # Validate amount
            if amount is None or not isinstance(amount, (int, float, Decimal)) or amount < 0:
                raise ValidationError(f"Invalid amount: {amount}")
                
            # Convert amount to attoFIL
            if isinstance(amount, (float, Decimal)):
                atto_fil_amount = int(amount * (10 ** self.currency['decimals']))
            else:
                atto_fil_amount = amount
                
            # If no nonce provided, get it from the network
            if nonce is None:
                nonce = self.client.get_nonce(from_address)
                
            # Estimate gas if not provided
            if gas_limit is None:
                # Create message for gas estimation
                msg = {
                    "Version": 0,
                    "To": to_address,
                    "From": from_address,
                    "Nonce": nonce,
                    "Value": str(atto_fil_amount),
                    "GasLimit": 0,  # Will be estimated
                    "GasFeeCap": "0",
                    "GasPremium": "0",
                    "Method": method,
                    "Params": params
                }
                
                # Estimate gas
                gas_estimate = self.client.estimate_gas(msg)
                gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
                
            # Get fee cap and premium if not provided
            if gas_fee_cap is None or gas_premium is None:
                # Get base fee from the latest block
                chain_head = self.client.get_chain_head()
                base_fee = self.client.get_base_fee(chain_head['/'])
                
                if gas_fee_cap is None:
                    # Set fee cap to base fee + premium
                    gas_fee_cap = str(int(base_fee * 1.5))  # 1.5x base fee
                    
                if gas_premium is None:
                    # Set gas premium
                    gas_premium = str(int(base_fee * 0.5))  # 0.5x base fee
                    
            # Create the message
            msg = {
                "Version": 0,
                "To": to_address,
                "From": from_address,
                "Nonce": nonce,
                "Value": str(atto_fil_amount),
                "GasLimit": gas_limit,
                "GasFeeCap": str(gas_fee_cap),
                "GasPremium": str(gas_premium),
                "Method": method,
                "Params": params
            }
            
            # Compute CID (Content Identifier) for the message
            cid = self.client.compute_message_cid(msg)
            
            # Return transaction object with additional metadata
            return {
                'network': self.network,
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount,
                'amount_in_atto': str(atto_fil_amount),
                'nonce': nonce,
                'gas_limit': gas_limit,
                'gas_fee_cap': gas_fee_cap,
                'gas_premium': gas_premium,
                'method': method,
                'params': params,
                'message': msg,
                'cid': cid,
                'signed': False
            }
            
        except FilecoinException as e:
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
        """Sign Filecoin transaction.
        
        Args:
            transaction: Transaction object from create_transaction
            private_key: Private key for signing (hex string)
            
        Returns:
            dict: Signed transaction object ready for broadcasting
            
        Raises:
            ValidationError: If transaction is invalid
            TransactionError: If signing fails
            WalletError: If private key is invalid
        """
        # Validate transaction object
        if not transaction or 'message' not in transaction:
            raise ValidationError("Invalid transaction object")
            
        try:
            # Get wallet for signing
            signing_wallet = None
            
            # Use provided private key if available
            if private_key:
                if not self.validate_private_key(private_key):
                    raise WalletError("Invalid private key format")
                signing_wallet = LocalWallet.from_private_key(private_key)
                
            # Otherwise use wallet from adapter if available
            elif self.wallet:
                signing_wallet = self.wallet
                
            # If no wallet is available, raise error
            if not signing_wallet:
                raise WalletError("No wallet available for signing")
                
            # Verify sender address
            wallet_address = signing_wallet.address
            if wallet_address != transaction['from_address']:
                raise ValidationError(
                    f"Private key does not match sender address. Expected {transaction['from_address']}, got {wallet_address}"
                )
                
            # Get the message to sign
            msg = transaction['message']
            
            # Sign the message
            signature = signing_wallet.sign_message(msg)
            
            # Create the signed message
            signed_message = {
                "Message": msg,
                "Signature": {
                    "Type": 1,  # secp256k1 signature type
                    "Data": signature
                }
            }
            
            # Return signed transaction
            signed_tx = transaction.copy()
            signed_tx['signed'] = True
            signed_tx['signed_message'] = signed_message
            
            return signed_tx
            
        except FilecoinException as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast signed Filecoin transaction.
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            dict: Transaction receipt with cid and status
            
        Raises:
            ValidationError: If signed transaction is invalid
            TransactionError: If broadcasting fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        # Validate signed transaction
        if not signed_transaction or not signed_transaction.get('signed', False) or 'signed_message' not in signed_transaction:
            raise ValidationError("Transaction is not signed")
            
        try:
            # Get the signed message
            signed_message = signed_transaction['signed_message']
            
            # Submit the message to the network
            cid = self.client.mpool_push(signed_message)
            
            if not cid:
                raise TransactionError("Failed to broadcast transaction")
                
            # Create receipt
            receipt = {
                'txid': cid,
                'confirmed': False,  # Just sent, not confirmed yet
                'explorer_url': f"{self.explorer_tx_url}{cid}",
                'from_address': signed_transaction['from_address'],
                'to_address': signed_transaction['to_address'],
                'amount': signed_transaction['amount'],
                'gas_used': None,  # Will be available after confirmation
                'gas_fee': None,  # Will be available after confirmation
                'status': 'pending'
            }
            
            return receipt
            
        except FilecoinException as e:
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
            tx_id: Transaction ID (CID)
            
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
            # Get message receipt from the network
            receipt = self.client.get_message_receipt(tx_id)
            
            if not receipt:
                # Message not found in the blockchain yet
                pending = self.client.check_pending(tx_id)
                
                if pending:
                    # Message is still in mempool
                    return {
                        'txid': tx_id,
                        'confirmed': False,
                        'status': 'pending',
                        'explorer_url': f"{self.explorer_tx_url}{tx_id}"
                    }
                else:
                    # Message not found anywhere
                    return {
                        'txid': tx_id,
                        'confirmed': False,
                        'status': 'not_found',
                        'explorer_url': f"{self.explorer_tx_url}{tx_id}"
                    }
            
            # Get message details
            message = self.client.get_message(tx_id)
            
            # Process receipt and message
            status = 'success' if receipt.get('ExitCode', 0) == 0 else 'failed'
            confirmed = status != 'pending'
            
            result = {
                'txid': tx_id,
                'confirmed': confirmed,
                'status': status,
                'explorer_url': f"{self.explorer_tx_url}{tx_id}",
                'block_height': receipt.get('Height'),
                'exit_code': receipt.get('ExitCode'),
                'gas_used': receipt.get('GasUsed'),
            }
            
            # Add message details if available
            if message:
                result.update({
                    'from_address': message.get('From'),
                    'to_address': message.get('To'),
                    'amount': Decimal(message.get('Value', '0')) / Decimal(10 ** self.currency['decimals']),
                    'nonce': message.get('Nonce'),
                    'method': message.get('Method')
                })
                
            return result
                
        except FilecoinException as e:
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
            # Get chain head to access latest base fee
            chain_head = self.client.get_chain_head()
            base_fee = self.client.get_base_fee(chain_head['/'])
            
            # Standard gas limit for a simple transfer
            standard_gas_limit = 2000000
            
            # Calculate fee estimates
            slow_premium = int(base_fee * 0.5)
            avg_premium = int(base_fee * 1.0)
            fast_premium = int(base_fee * 2.0)
            
            # Calculate total fees (base_fee + premium) * gas_limit
            slow_total = ((int(base_fee) + slow_premium) * standard_gas_limit) 
            avg_total = ((int(base_fee) + avg_premium) * standard_gas_limit)
            fast_total = ((int(base_fee) + fast_premium) * standard_gas_limit)
            
            # Convert to FIL
            slow_fil = Decimal(slow_total) / Decimal(10 ** self.currency['decimals'])
            avg_fil = Decimal(avg_total) / Decimal(10 ** self.currency['decimals'])
            fast_fil = Decimal(fast_total) / Decimal(10 ** self.currency['decimals'])
            
            return {
                'slow': {
                    'fee': slow_fil,
                    'fee_cap': str(int(base_fee) + slow_premium),
                    'gas_premium': str(slow_premium),
                    'time_estimate': '60 minutes'
                },
                'average': {
                    'fee': avg_fil,
                    'fee_cap': str(int(base_fee) + avg_premium),
                    'gas_premium': str(avg_premium),
                    'time_estimate': '15 minutes'
                },
                'fast': {
                    'fee': fast_fil,
                    'fee_cap': str(int(base_fee) + fast_premium),
                    'gas_premium': str(fast_premium),
                    'time_estimate': '1 minute'
                }
            }
                
        except FilecoinException as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_network_status(self) -> Dict:
        """Get Filecoin network status.
        
        Returns:
            dict: Network statistics and status
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get chain head
            chain_head = self.client.get_chain_head()
            height = chain_head.get('Height')
            
            # Get network version
            network_version = self.client.get_network_version()
            
            # Get base fee
            base_fee = self.client.get_base_fee(chain_head['/'])
            base_fee_fil = Decimal(base_fee) / Decimal(10 ** self.currency['decimals'])
            
            # Get network stats
            stats = {
                'network_name': self.network_name,
                'network_version': network_version,
                'chain_height': height,
                'base_fee': base_fee_fil,
                'timestamp': int(time.time())
            }
            
            return stats
                
        except FilecoinException as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from Filecoin network.
        
        Returns:
            bool: True if successfully disconnected
        """
        self.is_connected = False
        self.client = None
        logger.info(f"Disconnected from {self.network_name}")
        return True
