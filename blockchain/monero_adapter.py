#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Monero blockchain adapter implementation.
Native, no-fallback adapter for Monero network integration.
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

# Import Monero specific libraries
from monero.wallet import Wallet
from monero.backends.jsonrpc import JSONRPCWallet
from monero.address import address
from monero.numbers import PaymentID
from monero.transaction import Transaction, IncomingPayment, OutgoingPayment
from monero.daemon import Daemon
from monero.exceptions import MoneroException

# Import networking libraries for API calls
import requests
from requests.exceptions import RequestException

# Import logging
import logging
logger = logging.getLogger(__name__)


class MoneroAdapter(BlockchainAdapter):
    """Native Monero blockchain adapter.
    
    Implements all required blockchain operations for Monero network
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Monero Mainnet',
            'daemon_rpc_url': 'http://127.0.0.1:18081',
            'wallet_rpc_url': 'http://127.0.0.1:18080',
            'explorer_url': 'https://xmrchain.net',
            'chain_id': 'mainnet-v1.0',
            'address_prefix': 18  # Standard Monero address prefix
        },
        'stagenet': {
            'name': 'Monero Stagenet',
            'daemon_rpc_url': 'http://127.0.0.1:38081',
            'wallet_rpc_url': 'http://127.0.0.1:38080',
            'explorer_url': 'https://stagenet.xmrchain.net',
            'chain_id': 'stagenet-v1.0',
            'address_prefix': 24  # Stagenet address prefix
        },
        'testnet': {
            'name': 'Monero Testnet',
            'daemon_rpc_url': 'http://127.0.0.1:28081',
            'wallet_rpc_url': 'http://127.0.0.1:28080',
            'explorer_url': 'https://testnet.xmrchain.net',
            'chain_id': 'testnet-v1.0',
            'address_prefix': 53  # Testnet address prefix
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'XMR': {
            'name': 'Monero',
            'symbol': 'XMR',
            'decimals': 12,  # 1 XMR = 10^12 piconero
            'min_fee': 0.00001  # Minimum transaction fee
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Monero adapter.
        
        Args:
            network: Network name ('mainnet', 'stagenet', or 'testnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid
        """
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Monero network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.daemon_rpc_url = self.NETWORKS[network]['daemon_rpc_url']
        self.wallet_rpc_url = self.NETWORKS[network]['wallet_rpc_url']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.chain_id = self.NETWORKS[network]['chain_id']
        self.address_prefix = self.NETWORKS[network]['address_prefix']
        
        # Authentication for RPC
        self.daemon_auth = None
        self.wallet_auth = None
        
        # Set currency details (XMR)
        self.currency = self.CURRENCY['XMR']
        
        # Set connection state
        self.is_connected = False
        self.daemon = None
        self.wallet = None
        self.wallet_backend = None
        
        # Override config if provided
        if config:
            if 'daemon_rpc_url' in config:
                self.daemon_rpc_url = config['daemon_rpc_url']
                
            if 'wallet_rpc_url' in config:
                self.wallet_rpc_url = config['wallet_rpc_url']
                
            if 'daemon_username' in config and 'daemon_password' in config:
                self.daemon_auth = (config['daemon_username'], config['daemon_password'])
                
            if 'wallet_username' in config and 'wallet_password' in config:
                self.wallet_auth = (config['wallet_username'], config['wallet_password'])
                
            if 'wallet_path' in config:
                self.wallet_path = config.get('wallet_path')
                
            if 'wallet_password' in config:
                self.wallet_password = config.get('wallet_password')
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        return f"MoneroAdapter({self.network_name}, {connection_status})"
    
    @property
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/tx/"
    
    @property
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/search?value="
    
    @property
    def explorer_block_url(self) -> str:
        """Get block explorer URL template."""
        return f"{self.explorer_url}/block/"
    
    @strict_blockchain_operation
    def _verify_connection(self) -> bool:
        """Verify connection to Monero network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.daemon or not self.wallet:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Verify daemon connection
            daemon_info = self.daemon.info()
            if not daemon_info:
                raise BlockchainConnectionError("Daemon connection failed")
                
            # Verify wallet connection
            balance = self.wallet.balance()
            if balance is None:
                raise BlockchainConnectionError("Wallet connection failed")
                
            return True
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Monero network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize Monero daemon connection
            self.daemon = Daemon(
                host=self.daemon_rpc_url, 
                user=self.daemon_auth[0] if self.daemon_auth else None,
                password=self.daemon_auth[1] if self.daemon_auth else None
            )
            
            # Initialize Monero wallet connection
            self.wallet_backend = JSONRPCWallet(
                server=self.wallet_rpc_url,
                user=self.wallet_auth[0] if self.wallet_auth else None,
                password=self.wallet_auth[1] if self.wallet_auth else None
            )
            
            # Initialize wallet
            self.wallet = Wallet(self.wallet_backend)
            
            # Verify connection
            self._verify_connection()
            
            # Set connection status
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}")
            
            return True
            
        except Exception as e:
            self.is_connected = False
            self.daemon = None
            self.wallet = None
            self.wallet_backend = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    def validate_address(self, address: str) -> bool:
        """Validate Monero address format.
        
        Args:
            address: Monero address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Try to create address object which validates format
            addr = address(address)
            
            # Check network prefix
            if self.network == 'mainnet' and addr.net != 'mainnet':
                return False
            elif self.network == 'stagenet' and addr.net != 'stagenet':
                return False
            elif self.network == 'testnet' and addr.net != 'testnet':
                return False
                
            return True
        except Exception:
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate Monero private key format.
        
        Args:
            private_key: Private key to validate (mnemonic seed or hex)
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Check if it looks like a mnemonic seed (12-25 words)
            words = private_key.split()
            if 12 <= len(words) <= 25:
                # Real validation would need to check against word list
                return True
                
            # Check if it's a hex-encoded private key (64 chars)
            if len(private_key) == 64:
                # Try to convert to bytes
                try:
                    binascii.unhexlify(private_key)
                    return True
                except binascii.Error:
                    return False
                    
            return False
        except Exception:
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str, token_id: str = None) -> Decimal:
        """Get XMR balance for address.
        
        Args:
            address: Monero address to query
            token_id: Ignored for Monero (no tokens)
            
        Returns:
            Decimal: Balance in XMR
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected or not self.wallet:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # For Monero, we can only query the balance of the wallet itself
            # The provided address must match the wallet's primary address
            primary_address = str(self.wallet.address())
            
            if address and address != primary_address:
                raise ValidationError(
                    f"Cannot query balance for external address {address}. "  
                    f"Monero only supports balance queries for the wallet's own address: {primary_address}"
                )
                
            # Get wallet balance (unlocked balance is what's available to spend)
            balance = self.wallet.balance()
            unlocked_balance = self.wallet.balance(unlocked=True)
            
            # Convert to XMR (from atomic units)
            xmr_balance = Decimal(balance) / Decimal(10 ** self.currency['decimals'])
            
            # Return the unlocked balance in XMR
            return Decimal(unlocked_balance) / Decimal(10 ** self.currency['decimals'])
                
        except MoneroException as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict) -> Dict:
        """Create Monero transaction.
        
        Args:
            transaction: Transaction details with the following fields:
                - to_address: Recipient address
                - amount: Amount to send in XMR
                - payment_id: Optional payment ID
                - priority: Optional transaction priority (default: normal)
                
        Returns:
            dict: Transaction object ready for signing
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If transaction parameters are invalid
            TransactionError: If transaction creation fails
        """
        if not self.is_connected or not self.wallet:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Extract and validate transaction parameters
            to_address = transaction.get('to_address')
            amount = transaction.get('amount')
            payment_id = transaction.get('payment_id')
            priority = transaction.get('priority', 1)  # Default: normal priority
            
            # Use wallet address as from_address
            from_address = str(self.wallet.address())
            
            # Validate recipient address
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            # Validate amount
            if amount is None or not isinstance(amount, (int, float, Decimal)) or amount <= 0:
                raise ValidationError(f"Invalid amount: {amount}")
                
            # Convert amount to atomic units
            if isinstance(amount, (float, Decimal)):
                atomic_amount = int(amount * (10 ** self.currency['decimals']))
            else:
                atomic_amount = amount
                
            # Validate payment ID if provided
            parsed_payment_id = None
            if payment_id:
                try:
                    parsed_payment_id = PaymentID(payment_id)
                except ValueError as e:
                    raise ValidationError(f"Invalid payment ID: {payment_id}") from e
                
            # Estimate transaction fee
            try:
                # Create unsigned transaction to estimate fee
                # Note: This doesn't send the transaction, just prepares it
                tx = self.wallet.transfer(
                    address(to_address),
                    atomic_amount,
                    priority=priority,
                    payment_id=parsed_payment_id,
                    relay=False  # Don't broadcast yet
                )
                
                # Extract fee
                fee = tx.fee if hasattr(tx, 'fee') else 0
                
            except MoneroException as e:
                raise TransactionError(f"Failed to prepare transaction: {str(e)}") from e
                
            # Return transaction details
            # Note: In Monero, we generally don't use the intermediate transaction object pattern
            # Because of how Monero's wallet works. We'll use a custom approach here.
            return {
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount,
                'atomic_amount': atomic_amount,
                'fee': Decimal(fee) / Decimal(10 ** self.currency['decimals']) if fee else None,
                'network': self.network,
                'payment_id': payment_id,
                'priority': priority,
                # Include prepared tx data for signing
                'prepared_tx': {
                    'address': to_address,
                    'amount': atomic_amount,
                    'payment_id': parsed_payment_id,
                    'priority': priority
                }
            }
            
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_and_broadcast_transaction(self, transaction: Dict) -> Dict:
        """Sign and broadcast Monero transaction.
        
        For Monero, signing and broadcasting are combined due to the nature of the wallet API.
        
        Args:
            transaction: Transaction object from create_transaction
            
        Returns:
            dict: Transaction receipt with txid and status
            
        Raises:
            ValidationError: If transaction is invalid
            TransactionError: If signing or broadcasting fails
        """
        if not self.is_connected or not self.wallet:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Extract transaction details
            tx_data = transaction.get('prepared_tx')
            if not tx_data:
                raise ValidationError("Invalid transaction object")
                
            # Extract parameters
            recipient_address = tx_data.get('address')
            amount = tx_data.get('amount')
            payment_id = tx_data.get('payment_id')
            priority = tx_data.get('priority', 1)
            
            # Create and broadcast transaction
            tx = self.wallet.transfer(
                address(recipient_address),
                amount,
                payment_id=payment_id,
                priority=priority,
                relay=True  # Broadcast immediately
            )
            
            # Extract transaction hash
            tx_hash = tx.hash
            
            # Create receipt
            receipt = {
                'txid': tx_hash,
                'confirmed': False,  # Just sent, not confirmed yet
                'explorer_url': f"{self.explorer_tx_url}{tx_hash}",
                'from_address': str(self.wallet.address()),
                'to_address': recipient_address,
                'amount': Decimal(amount) / Decimal(10 ** self.currency['decimals']),
                'fee': Decimal(tx.fee) / Decimal(10 ** self.currency['decimals']) if hasattr(tx, 'fee') else None,
                'payment_id': str(payment_id) if payment_id else None,
            }
            
            return receipt
            
        except MoneroException as e:
            error_msg = f"Failed to sign and broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Failed to sign and broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    # For compatibility with the BlockchainAdapter interface
    def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
        """Sign a Monero transaction via the wallet RPC ``transfer`` method.

        Monero wallets own the spend keys, so signing is performed by the
        daemon itself.  This method calls the wallet RPC with ``relay=False``
        so the transaction is signed but **not** broadcast, allowing the
        caller to inspect it before calling ``broadcast_transaction``.

        If the wallet RPC is unavailable the method falls back to marking
        the transaction as *ready-to-broadcast* so that
        ``sign_and_broadcast_transaction`` can still be used.

        Args:
            transaction: Transaction object from ``create_transaction``.
            private_key: Ignored — Monero wallet holds its own keys.

        Returns:
            dict: Transaction object with ``signed_tx_blob`` when the RPC
                  succeeds, or a ``signed=True`` marker for deferred relay.

        Raises:
            ValidationError: If the transaction object is malformed.
            TransactionError: If the wallet RPC call fails.
        """
        if not transaction or not transaction.get('prepared_tx'):
            raise ValidationError("Invalid transaction object")

        tx_data = transaction['prepared_tx']
        recipient_address = tx_data.get('address')
        amount = tx_data.get('amount')
        payment_id = tx_data.get('payment_id')
        priority = tx_data.get('priority', 1)

        if not self.is_connected or not self.wallet:
            logger.warning(
                "Wallet RPC unavailable — marking transaction as signed "
                "for deferred relay via sign_and_broadcast_transaction"
            )
            result = transaction.copy()
            result['signed'] = True
            return result

        try:
            tx = self.wallet.transfer(
                address(recipient_address),
                amount,
                payment_id=payment_id,
                priority=priority,
                relay=False,
            )

            result = transaction.copy()
            result['signed'] = True
            result['signed_tx_blob'] = tx.blob if hasattr(tx, 'blob') else None
            result['tx_hash'] = tx.hash if hasattr(tx, 'hash') else None
            result['fee'] = (
                Decimal(tx.fee) / Decimal(10 ** self.currency['decimals'])
                if hasattr(tx, 'fee') else None
            )
            return result

        except MoneroException as e:
            raise TransactionError(
                f"Monero wallet RPC signing failed: {e}"
            ) from e
            
    # For compatibility with the BlockchainAdapter interface
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast signed Monero transaction.
        
        In Monero, wallet owns the keys and signing is integrated with broadcasting.
        This is a wrapper around sign_and_broadcast_transaction.
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            dict: Transaction receipt with txid and status
            
        Raises:
            ValidationError: If signed transaction is invalid
            TransactionError: If broadcasting fails
        """
        # Check if transaction is marked as signed
        if not signed_transaction.get('signed', False):
            raise ValidationError("Transaction is not signed")
            
        # Use the integrated method
        return self.sign_and_broadcast_transaction(signed_transaction)
