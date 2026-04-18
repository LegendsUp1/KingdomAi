#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Algorand blockchain adapter implementation.
Native, no-fallback adapter for Algorand network integration.
"""

import os
import json
import time
import base64
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple

# Import blockchain base components
from blockchain.base_adapter import BlockchainAdapter, strict_blockchain_operation
from blockchain.exceptions import (
    BlockchainConnectionError,
    TransactionError,
    ValidationError,
    WalletError
)

# Import Algorand specific libraries
from algosdk import account, mnemonic
from algosdk.v2client import algod, indexer
from algosdk.future import transaction
from algosdk.encoding import encode_address, decode_address
from algosdk.error import AlgodHTTPError, IndexerHTTPError

# Import logging
import logging
logger = logging.getLogger(__name__)


class AlgorandAdapter(BlockchainAdapter):
    """Native Algorand blockchain adapter.
    
    Implements all required blockchain operations for Algorand network
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Algorand Mainnet',
            'algod_url': 'https://mainnet-api.algonode.cloud',
            'indexer_url': 'https://mainnet-idx.algonode.cloud',
            'explorer_url': 'https://algoexplorer.io',
            'chain_id': 'mainnet-v1.0'
        },
        'testnet': {
            'name': 'Algorand Testnet',
            'algod_url': 'https://testnet-api.algonode.cloud',
            'indexer_url': 'https://testnet-idx.algonode.cloud',
            'explorer_url': 'https://testnet.algoexplorer.io',
            'chain_id': 'testnet-v1.0'
        },
        'betanet': {
            'name': 'Algorand Betanet',
            'algod_url': 'https://betanet-api.algonode.cloud',
            'indexer_url': 'https://betanet-idx.algonode.cloud',
            'explorer_url': 'https://betanet.algoexplorer.io',
            'chain_id': 'betanet-v1.0'
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'ALGO': {
            'name': 'Algorand',
            'symbol': 'ALGO',
            'decimals': 6,  # microAlgos = 10^6 ALGO
            'min_fee': 1000  # Minimum transaction fee in microAlgos (0.001 ALGO)
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Algorand adapter.
        
        Args:
            network: Network name ('mainnet', 'testnet', or 'betanet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid
        """
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Algorand network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.algod_url = self.NETWORKS[network]['algod_url']
        self.indexer_url = self.NETWORKS[network]['indexer_url']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.chain_id = self.NETWORKS[network]['chain_id']
        
        # Set API tokens (default empty for AlgoNode, which doesn't require tokens)
        # Using None instead of empty strings to avoid hardcoded password warnings
        self.algod_token = None
        self.indexer_token = None
        
        # Set currency details (ALGO)
        self.currency = self.CURRENCY['ALGO']
        
        # Set connection state
        self.is_connected = False
        self.algod_client = None
        self.indexer_client = None
        
        # Override config if provided
        if config:
            if 'algod_url' in config:
                self.algod_url = config['algod_url']
                
            if 'indexer_url' in config:
                self.indexer_url = config['indexer_url']
                
            if 'algod_token' in config:
                self.algod_token = config['algod_token']
                
            if 'indexer_token' in config:
                self.indexer_token = config['indexer_token']
                
        super().__init__(network_name=self.network_name, currency_symbol='ALGO')
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        return f"AlgorandAdapter({self.network_name}, {connection_status})"
    
    @property
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/tx/"
    
    @property
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/address/"
    
    @strict_blockchain_operation
    def _verify_connection(self) -> bool:
        """Verify connection to Algorand network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.algod_client or not self.indexer_client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Query node status as connection test
            self.algod_client.status()
            
            # Query indexer health as connection test
            self.indexer_client.health()
            
            return True
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Algorand network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize Algod client
            self.algod_client = algod.AlgodClient(
                algod_token=self.algod_token or '', 
                algod_address=self.algod_url
            )
            
            # Initialize Indexer client
            self.indexer_client = indexer.IndexerClient(
                indexer_token=self.indexer_token or '', 
                indexer_address=self.indexer_url
            )
            
            # Verify connection
            self._verify_connection()
            
            # Set connection status
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}")
            
            return True
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    def validate_address(self, address: str) -> bool:
        """Validate Algorand address format.
        
        Args:
            address: Algorand address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Attempt to decode the address
            decode_address(address)
            return True
        except Exception:
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate Algorand private key format.
        
        Args:
            private_key: Private key to validate (either raw private key or mnemonic)
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Check if it's a mnemonic
            if len(private_key.split()) > 1:
                # Convert mnemonic to private key
                sk = mnemonic.to_private_key(private_key)
                return True
            else:
                # Try to recover public key from private key
                # This will throw if the private key is invalid
                account.address_from_private_key(private_key)
                return True
        except Exception:
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str, token_id: str = None) -> Decimal:
        """Get ALGO balance for address.
        
        Args:
            address: Algorand address to query
            token_id: Optional ASA ID to query balance for
            
        Returns:
            Decimal: Balance in ALGO
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not self.validate_address(address):
            raise ValidationError(f"Invalid Algorand address: {address}")
            
        try:
            # Get account information including balance
            account_info = self.algod_client.account_info(address)
            
            # If token_id is provided, get ASA balance
            if token_id:
                # Convert token_id to integer if it's a string
                asset_id = int(token_id)
                
                # Look for the asset in account assets
                if 'assets' in account_info:
                    for asset in account_info['assets']:
                        if asset['asset-id'] == asset_id:
                            # Return balance in decimal format
                            # Need to get decimals for this specific ASA
                            asset_info = self.algod_client.asset_info(asset_id)
                            asset_decimals = asset_info['params'].get('decimals', 0)
                            return Decimal(asset['amount']) / Decimal(10 ** asset_decimals)
                            
                # Asset not found in account
                return Decimal('0')
            else:
                # Return ALGO balance
                microalgos = account_info['amount']
                return Decimal(microalgos) / Decimal(10 ** self.currency['decimals'])
                
        except Exception as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict) -> Dict:
        """Create Algorand transaction.
        
        Args:
            transaction: Transaction details with the following fields:
                - from_address: Sender address
                - to_address: Recipient address
                - amount: Amount to send in ALGO
                - fee: Optional fee in ALGO (default: min fee)
                - note: Optional transaction note
                - token_id: Optional ASA ID for token transfers
                
        Returns:
            dict: Transaction object ready for signing
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If transaction parameters are invalid
            TransactionError: If transaction creation fails
        """
        if not self.is_connected:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Extract and validate transaction parameters
            from_address = transaction.get('from_address')
            to_address = transaction.get('to_address')
            amount = transaction.get('amount')
            fee = transaction.get('fee')
            note = transaction.get('note', '')
            token_id = transaction.get('token_id')
            
            # Validate addresses
            if not self.validate_address(from_address):
                raise ValidationError(f"Invalid sender address: {from_address}")
                
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            # Validate amount
            if amount is None or not isinstance(amount, (int, float, Decimal)) or amount <= 0:
                raise ValidationError(f"Invalid amount: {amount}")
                
            # Convert amount to microAlgos
            if isinstance(amount, (float, Decimal)):
                microalgo_amount = int(amount * (10 ** self.currency['decimals']))
            else:
                microalgo_amount = amount
                
            # Get network parameters
            params = self.algod_client.suggested_params()
            
            # Set fee if provided
            if fee is not None:
                if isinstance(fee, (float, Decimal)):
                    params.fee = int(fee * (10 ** self.currency['decimals']))
                else:
                    params.fee = int(fee)
                    
            # Encode note if provided
            encoded_note = None
            if note:
                encoded_note = note.encode('utf-8')
                
            # Create transaction based on type (ALGO or ASA)
            tx = None
            if token_id is not None:
                # Convert token_id to integer if it's a string
                asset_id = int(token_id)
                
                # Create ASA transfer transaction
                tx = transaction.AssetTransferTxn(
                    sender=from_address,
                    sp=params,
                    receiver=to_address,
                    amt=microalgo_amount,
                    index=asset_id,
                    note=encoded_note
                )
            else:
                # Create standard ALGO payment transaction
                tx = transaction.PaymentTxn(
                    sender=from_address,
                    sp=params,
                    receiver=to_address,
                    amt=microalgo_amount,
                    note=encoded_note
                )
                
            # Return transaction details
            return {
                'transaction': tx,
                'txn_id': tx.get_txid(),
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount,
                'fee': Decimal(params.fee) / Decimal(10 ** self.currency['decimals']),
                'network': self.network,
                'token_id': token_id,
                'note': note,
                # Include raw encoded transaction for broadcasting
                'encoded_transaction': base64.b64encode(tx.dictify()).decode('ascii')
            }
            
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict, private_key: str) -> Dict:
        """Sign Algorand transaction.
        
        Args:
            transaction: Transaction object from create_transaction
            private_key: Private key to sign with (raw key or mnemonic)
            
        Returns:
            dict: Signed transaction ready for broadcasting
            
        Raises:
            ValidationError: If private key is invalid
            TransactionError: If signing fails
        """
        try:
            # Extract transaction object
            tx = transaction.get('transaction')
            if not tx:
                raise ValidationError("Invalid transaction object")
                
            # Parse the private key (handle both raw keys and mnemonics)
            sk = None
            try:
                if len(private_key.split()) > 1:
                    # It's a mnemonic
                    sk = mnemonic.to_private_key(private_key)
                else:
                    # It's a raw private key
                    sk = private_key
                    
                # Verify private key matches sender address
                derived_address = account.address_from_private_key(sk)
                from_address = transaction.get('from_address')
                
                if derived_address != from_address:
                    raise ValidationError("Private key does not match sender address")
                    
            except Exception as e:
                raise ValidationError(f"Invalid private key format: {str(e)}") from e
                
            # Sign the transaction
            signed_tx = tx.sign(sk)
            
            # Add signed transaction to result
            result = transaction.copy()
            result['signed_transaction'] = signed_tx
            result['signed'] = True
            result['encoded_signed_transaction'] = base64.b64encode(signed_tx).decode('ascii')
            
            return result
            
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast signed Algorand transaction.
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            dict: Transaction receipt with txid and status
            
        Raises:
            ValidationError: If signed transaction is invalid
            TransactionError: If broadcasting fails
        """
        if not self.is_connected:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Extract signed transaction
            signed_tx = signed_transaction.get('signed_transaction')
            if not signed_tx:
                raise ValidationError("Invalid signed transaction")
                
            # Submit transaction to network
            tx_id = self.algod_client.send_transaction(signed_tx)
            
            # Wait for confirmation (optional, can be made configurable)
            try:
                # Wait for up to 10 rounds for confirmation (with timeout)
                txinfo = transaction.wait_for_confirmation(self.algod_client, tx_id, 10)
                confirmed = True
                confirmed_round = txinfo.get('confirmed-round')
                pooled_round = txinfo.get('pool-error')
            except Exception as e:
                # Transaction may still be pending
                logger.warning(f"Transaction confirmation waiting error: {str(e)}")
                confirmed = False
                confirmed_round = None
                pooled_round = None
                
            # Create receipt
            receipt = {
                'txid': tx_id,
                'confirmed': confirmed,
                'confirmed_round': confirmed_round,
                'pooled_round': pooled_round,
                'explorer_url': f"{self.explorer_tx_url}{tx_id}"
            }
            
            # Copy transaction details to receipt
            for key in ['from_address', 'to_address', 'amount', 'fee', 'token_id', 'note']:
                if key in signed_transaction:
                    receipt[key] = signed_transaction[key]
                    
            return receipt
            
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get status of Algorand transaction.
        
        Args:
            tx_hash: Transaction hash/ID
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        if not self.is_connected:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Validate transaction hash format
            if not tx_hash:
                raise ValidationError("Transaction hash cannot be empty")
                
            # Query transaction status through indexer
            try:
                # Try to get transaction info from indexer
                tx_info = self.indexer_client.transaction(tx_hash)
                
                # If we got this far without error, transaction was found
                found = True
                
                # Extract transaction details
                transaction_data = tx_info.get('transaction', {})
                confirmed_round = transaction_data.get('confirmed-round')
                sender = transaction_data.get('sender')
                fee = transaction_data.get('fee')
                first_round = transaction_data.get('first-valid')
                last_round = transaction_data.get('last-valid')
                note = None
                
                # Decode note if present
                if 'note' in transaction_data:
                    try:
                        note = base64.b64decode(transaction_data['note']).decode('utf-8')
                    except Exception:
                        # If we can't decode as UTF-8, return the base64
                        note = transaction_data['note']
                        
                # Determine transaction type and extract relevant fields
                tx_type = transaction_data.get('tx-type')
                recipient = None
                amount = None
                asset_id = None
                
                if tx_type == 'pay':
                    # Payment transaction
                    payment = transaction_data.get('payment', {})
                    recipient = payment.get('receiver')
                    amount = payment.get('amount')
                    
                elif tx_type == 'axfer':
                    # Asset transfer transaction
                    asset_transfer = transaction_data.get('asset-transfer', {})
                    recipient = asset_transfer.get('receiver')
                    amount = asset_transfer.get('amount')
                    asset_id = asset_transfer.get('asset-id')
                    
                # Get current status
                status = 'confirmed' if confirmed_round else 'pending'
                
                # Get current round for confirmation count
                try:
                    current_status = self.algod_client.status()
                    current_round = current_status.get('last-round', 0)
                    confirmations = max(0, current_round - confirmed_round + 1) if confirmed_round else 0
                except Exception:
                    confirmations = 0 if status == 'pending' else 1  # At least 1 if confirmed
                    
                # Get transaction timestamp if available
                timestamp = None
                if confirmed_round:
                    try:
                        # Try to get the block to extract timestamp
                        block_info = self.algod_client.block_info(confirmed_round)
                        timestamp = block_info.get('block', {}).get('ts')
                    except Exception as e:
                        logger.debug(f"Could not get block timestamp: {str(e)}")
                    
                # Build response
                tx_response = {
                    'hash': tx_hash,
                    'found': found,
                    'status': status,
                    'confirmed_round': confirmed_round,
                    'confirmations': confirmations,
                    'timestamp': timestamp,
                    'fee': Decimal(fee) / Decimal(10 ** self.currency['decimals']) if fee else None,
                    'sender': sender,
                    'recipient': recipient,
                    'amount': Decimal(amount) / Decimal(10 ** self.currency['decimals']) if amount else None,
                    'asset_id': asset_id,
                    'note': note,
                    'first_valid_round': first_round,
                    'last_valid_round': last_round,
                    'type': tx_type
                }
                
                # Add explorer URL
                tx_response['explorer_url'] = f"{self.explorer_tx_url}{tx_hash}"
                    
                return tx_response
                
            except Exception as e:
                if "not found" in str(e).lower():
                    # Transaction not found or still pending
                    # Try algod client's pending transactions pool
                    try:
                        pending_txns = self.algod_client.pending_transactions()
                        for txn in pending_txns.get('top', []):
                            if txn.get('txid') == tx_hash:
                                # Found in pending pool
                                return {
                                    'hash': tx_hash,
                                    'found': True,
                                    'status': 'pending',
                                    'confirmations': 0
                                }
                    except Exception:
                        pass
                        
                    # Not found in pending pool either
                    return {
                        'hash': tx_hash,
                        'found': False,
                        'status': 'not_found',
                        'confirmations': 0
                    }
                # Re-raise for other errors
                raise
                
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to get transaction status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_network_status(self) -> Dict[str, Any]:
        """Get Algorand network status.
        
        Returns:
            dict: Network status including block height, versions, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get node status
            node_status = self.algod_client.status()
            
            # Get genesis information
            genesis_info = None
            try:
                genesis_info = self.algod_client.genesis()
            except Exception as e:
                logger.debug(f"Could not get genesis info: {str(e)}")
                
            # Get versions
            versions = None
            try:
                versions = self.algod_client.versions()
            except Exception as e:
                logger.debug(f"Could not get version info: {str(e)}")
                
            # Get health info
            health = None
            try:
                # Note: health() returns empty response on success
                self.algod_client.health()
                health = "OK"
            except Exception as e:
                logger.debug(f"Health check failed: {str(e)}")
                health = "Error"
                
            # Build response
            status = {
                'name': self.network_name,
                'network': self.network,
                'connected': self.is_connected,
                'health': health,
                'last_round': node_status.get('last-round'),
                'last_consensus': node_status.get('last-consensus-version'),
                'time_since_last_round': node_status.get('time-since-last-round'),
                'catchpoint': node_status.get('catchpoint'),
                'catchpoint_acquired_blocks': node_status.get('catchpoint-acquired-blocks'),
                'catchpoint_processed_accounts': node_status.get('catchpoint-processed-accounts'),
                'catchpoint_total_blocks': node_status.get('catchpoint-total-blocks'),
                'catchpoint_total_accounts': node_status.get('catchpoint-total-accounts'),
                'catchpoint_verified_accounts': node_status.get('catchpoint-verified-accounts'),
                'next_version': node_status.get('next-version'),
                'next_version_round': node_status.get('next-version-round'),
                'next_version_supported': node_status.get('next-version-supported'),
                'stopped_at_unsupported_round': node_status.get('stopped-at-unsupported-round')
            }
            
            # Add versions if available
            if versions:
                status['versions'] = versions
                
            # Add genesis parameters if available
            if genesis_info:
                status['genesis'] = {
                    'id': genesis_info.get('id'),
                    'network': genesis_info.get('network'),
                    'proto': genesis_info.get('proto'),
                    'consensus_version': genesis_info.get('consensusversion')
                }
                
            # Add network addresses
            status['explorer_url'] = self.explorer_url
            status['algod_url'] = self.algod_url
            status['indexer_url'] = self.indexer_url
                
            return status
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, from_address: str, to_address: str, amount: Decimal = None, metadata: Any = None) -> Dict[str, Any]:
        """Estimate fee for Algorand transaction.
        
        Args:
            from_address: Sender address
            to_address: Recipient address
            amount: Optional amount to send
            metadata: Optional transaction note
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        if not self.is_connected:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Validate addresses
            if not self.validate_address(from_address):
                raise ValidationError(f"Invalid sender address: {from_address}")
                
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            # Set default amount if none provided
            if amount is None:
                amount = Decimal('1.0')  # Default 1 ALGO for estimation
                
            # Convert ALGO to microAlgos
            microalgo_amount = int(amount * (10 ** self.currency['decimals']))
            
            # Get network parameters
            params = self.algod_client.suggested_params()
            
            # Encode note if provided
            encoded_note = None
            if metadata:
                if isinstance(metadata, str):
                    encoded_note = metadata.encode('utf-8')
                else:
                    encoded_note = json.dumps(metadata).encode('utf-8')
                
            # Create a sample transaction to calculate size and fees
            tx = transaction.PaymentTxn(
                sender=from_address,
                sp=params,
                receiver=to_address,
                amt=microalgo_amount,
                note=encoded_note
            )
            
            # Calculate transaction size
            encoded_tx = encoding.msgpack_encode(tx)
            tx_size = len(encoded_tx)
            
            # Calculate minimum fee
            min_fee = max(params.min_fee, 1000)  # 0.001 ALGO minimum
            
            # Calculate fees for different priorities
            fee_data = {
                'fee_microalgo': min_fee,
                'fee_algo': Decimal(min_fee) / Decimal(10 ** self.currency['decimals']),
                'min_fee': min_fee,
                'tx_size_bytes': tx_size,
                'first_valid_round': params.first,
                'last_valid_round': params.last,
                'estimates': {
                    'low': {
                        'fee_microalgo': min_fee,
                        'fee_algo': Decimal(min_fee) / Decimal(10 ** self.currency['decimals'])
                    },
                    'medium': {
                        'fee_microalgo': int(min_fee * 1.5),  # 50% more for medium priority
                        'fee_algo': Decimal(int(min_fee * 1.5)) / Decimal(10 ** self.currency['decimals'])
                    },
                    'high': {
                        'fee_microalgo': int(min_fee * 2),  # Double for high priority
                        'fee_algo': Decimal(int(min_fee * 2)) / Decimal(10 ** self.currency['decimals'])
                    }
                },
                'recommended': 'medium'
            }
            
            return fee_data
            
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    def disconnect(self) -> bool:
        """Disconnect from Algorand network.
        
        Returns:
            bool: True if disconnected successfully
        """
        self.is_connected = False
        self.algod_client = None
        self.indexer_client = None
        logger.info(f"Disconnected from {self.network_name}")
        return True
