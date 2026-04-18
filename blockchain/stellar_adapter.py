#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Stellar blockchain adapter implementation.
Native, no-fallback adapter for Stellar network integration.
"""

import os
import json
import time
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

# Import Stellar specific libraries
from stellar_sdk import (
    Server, 
    Keypair, 
    Network, 
    TransactionBuilder, 
    Asset,
    TransactionEnvelope,
    Operation,
    Payment,
    AccountMerge,
    ChangeTrust,
    CreateAccount,
    SetOptions
)
from stellar_sdk.exceptions import (
    NotFoundError,
    BadRequestError,
    BadResponseError
)

# Import logging
import logging
logger = logging.getLogger(__name__)


class StellarAdapter(BlockchainAdapter):
    """Native Stellar blockchain adapter.
    
    Implements all required blockchain operations for Stellar network
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Stellar Mainnet',
            'server': 'https://horizon.stellar.org',
            'network_passphrase': Network.PUBLIC_NETWORK_PASSPHRASE,
            'explorer_url': 'https://stellar.expert/explorer/public',
        },
        'testnet': {
            'name': 'Stellar Testnet',
            'server': 'https://horizon-testnet.stellar.org',
            'network_passphrase': Network.TESTNET_NETWORK_PASSPHRASE,
            'explorer_url': 'https://stellar.expert/explorer/testnet',
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'XLM': {
            'name': 'Stellar Lumens',
            'symbol': 'XLM',
            'decimals': 7,  # 1 XLM = 10^7 stroops
            'min_fee': 0.00001  # Minimum transaction fee in XLM (100 stroops)
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Stellar adapter.
        
        Args:
            network: Network name ('mainnet' or 'testnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid
        """
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Stellar network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.server_url = self.NETWORKS[network]['server']
        self.network_passphrase = self.NETWORKS[network]['network_passphrase']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        
        # Set currency details (XLM)
        self.currency = self.CURRENCY['XLM']
        
        # Set connection state
        self.is_connected = False
        self.server = None
        
        # Private key and keypair
        self.private_key = None
        self.keypair = None
        
        # Override config if provided
        if config:
            if 'server_url' in config:
                self.server_url = config['server_url']
                
            if 'private_key' in config:
                self.private_key = config.get('private_key')
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        return f"StellarAdapter({self.network_name}, {connection_status})"
    
    @property
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/tx/"
    
    @property
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/account/"
    
    @property
    def explorer_block_url(self) -> str:
        """Get ledger explorer URL template."""
        return f"{self.explorer_url}/ledger/"
    
    @strict_blockchain_operation
    def _verify_connection(self) -> bool:
        """Verify connection to Stellar network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.server:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get root info from server to verify connection
            root_info = self.server.root()
            if not root_info:
                raise BlockchainConnectionError(f"Failed to get root info from {self.network_name}")
                
            return True
            
        except (BadResponseError, BadRequestError) as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Stellar network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize Stellar server
            self.server = Server(self.server_url)
            
            # Initialize keypair if private key is provided
            if self.private_key:
                self.keypair = Keypair.from_secret(self.private_key)
            
            # Verify connection
            self._verify_connection()
            
            # Set connection status
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}")
            
            return True
            
        except (BadResponseError, BadRequestError) as e:
            self.is_connected = False
            self.server = None
            self.keypair = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
        except Exception as e:
            self.is_connected = False
            self.server = None
            self.keypair = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    def validate_address(self, address: str) -> bool:
        """Validate Stellar address format.
        
        Args:
            address: Stellar address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Stellar addresses start with G and are 56 characters long
            if not address.startswith('G') or len(address) != 56:
                return False
                
            # Try to parse it as a Stellar public key
            Keypair.from_public_key(address)
            return True
        except Exception:
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate Stellar private key format.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Stellar secret keys start with S and are 56 characters long
            if not private_key.startswith('S') or len(private_key) != 56:
                return False
                
            # Try to parse it as a Stellar secret key
            Keypair.from_secret(private_key)
            return True
        except Exception:
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str, token_id: str = None) -> Decimal:
        """Get XLM balance for address.
        
        Args:
            address: Stellar address to query
            token_id: Optional asset code for other tokens
            
        Returns:
            Decimal: Balance in XLM or token
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected or not self.server:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not self.validate_address(address):
            raise ValidationError(f"Invalid address format: {address}")
            
        try:
            # Get account info from network
            account = self.server.accounts().account_id(address).call()
            
            # Find the balance
            for balance in account['balances']:
                asset_type = balance['asset_type']
                
                if not token_id and asset_type == 'native':
                    # Native XLM balance
                    return Decimal(balance['balance'])
                elif token_id and asset_type == 'credit_alphanum4' or asset_type == 'credit_alphanum12':
                    # Other token balance
                    if balance['asset_code'] == token_id:
                        return Decimal(balance['balance'])
            
            # If we get here and token_id is None, no native balance was found
            if not token_id:
                return Decimal('0')
                
            # If we get here and token_id is not None, the token was not found
            return Decimal('0')
                
        except NotFoundError:
            # Account does not exist on the ledger
            return Decimal('0')
        except (BadResponseError, BadRequestError) as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict) -> Dict:
        """Create Stellar transaction.
        
        Args:
            transaction: Transaction details with the following fields:
                - to_address: Recipient address
                - from_address: Sender address (must match private key)
                - amount: Amount to send in XLM
                - memo: Optional memo text
                - asset_code: Optional asset code (default is XLM)
                - asset_issuer: Optional asset issuer (required if asset_code is not XLM)
                - fee: Optional fee in XLM (default is minimum fee)
                
        Returns:
            dict: Transaction object ready for signing
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If transaction parameters are invalid
            TransactionError: If transaction creation fails
        """
        if not self.is_connected or not self.server:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Extract and validate transaction parameters
            to_address = transaction.get('to_address')
            from_address = transaction.get('from_address')
            amount = transaction.get('amount')
            memo = transaction.get('memo')
            asset_code = transaction.get('asset_code', 'XLM')
            asset_issuer = transaction.get('asset_issuer')
            fee = transaction.get('fee', self.currency['min_fee'])
            
            # Validate addresses
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            if not self.validate_address(from_address):
                raise ValidationError(f"Invalid sender address: {from_address}")
                
            # Validate amount
            if amount is None or not isinstance(amount, (int, float, Decimal)) or amount <= 0:
                raise ValidationError(f"Invalid amount: {amount}")
                
            # Convert fee from XLM to stroops
            fee_stroops = int(Decimal(fee) * (10 ** self.currency['decimals']))
            
            # Check if we need a keypair
            if not self.keypair:
                raise ValidationError("No keypair available for creating transaction")
            
            # Verify the sender address matches the keypair's public key
            if from_address != self.keypair.public_key:
                raise ValidationError(
                    f"Sender address {from_address} does not match keypair's public key {self.keypair.public_key}"
                )
            
            # Get source account details
            source_account = self.server.load_account(from_address)
            
            # Start building the transaction
            builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.network_passphrase,
                base_fee=fee_stroops
            )
            
            # Add memo if provided
            if memo:
                builder.add_text_memo(memo)
            
            # Determine asset
            if asset_code == 'XLM':
                # Native XLM payment
                asset = Asset.native()
            else:
                # Custom asset payment
                if not asset_issuer:
                    raise ValidationError(f"Asset issuer is required for non-XLM asset: {asset_code}")
                if not self.validate_address(asset_issuer):
                    raise ValidationError(f"Invalid asset issuer address: {asset_issuer}")
                
                # Create the asset
                if len(asset_code) <= 4:
                    asset = Asset(asset_code, asset_issuer)
                elif len(asset_code) <= 12:
                    asset = Asset(asset_code, asset_issuer)
                else:
                    raise ValidationError(f"Invalid asset code length: {asset_code}")
            
            # Add payment operation
            builder.append_payment_op(
                destination=to_address,
                asset=asset,
                amount=str(amount)
            )
            
            # Set timeout (5 minutes)
            builder.set_timeout(300)
            
            # Build the transaction
            transaction_xdr = builder.build()
            
            # Store the transaction details
            transaction_details = {
                'network': self.network,
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount,
                'fee': fee,
                'fee_stroops': fee_stroops,
                'transaction_xdr': transaction_xdr.to_xdr(),
                'transaction_obj': transaction_xdr,
                'signed': False
            }
            
            # Add optional parameters
            if memo:
                transaction_details['memo'] = memo
            if asset_code != 'XLM':
                transaction_details['asset_code'] = asset_code
                transaction_details['asset_issuer'] = asset_issuer
            
            return transaction_details
            
        except (BadResponseError, BadRequestError) as e:
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
        """Sign Stellar transaction.
        
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
        if not transaction or 'transaction_xdr' not in transaction:
            raise ValidationError("Invalid transaction object")
            
        try:
            # Get the transaction XDR
            transaction_xdr = transaction.get('transaction_xdr')
            
            # Parse the transaction
            tx_obj = TransactionEnvelope.from_xdr(transaction_xdr, self.network_passphrase)
            
            # Determine the keypair to use for signing
            keypair = None
            
            if private_key:
                # Use provided private key
                if not self.validate_private_key(private_key):
                    raise WalletError("Invalid private key format")
                keypair = Keypair.from_secret(private_key)
            elif self.keypair:
                # Use instance keypair
                keypair = self.keypair
            else:
                raise WalletError("No keypair available for signing")
            
            # Verify the keypair's public key matches the transaction source account
            source_account = tx_obj.transaction.source.account_id
            if keypair.public_key != source_account:
                raise ValidationError(
                    f"Keypair public key {keypair.public_key} does not match transaction source {source_account}"
                )
            
            # Sign the transaction
            tx_obj.sign(keypair)
            
            # Create signed transaction object
            signed_tx = transaction.copy()
            signed_tx['signed'] = True
            signed_tx['transaction_xdr'] = tx_obj.to_xdr()
            signed_tx['transaction_obj'] = tx_obj
            
            return signed_tx
            
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast signed Stellar transaction.
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            dict: Transaction receipt with hash and status
            
        Raises:
            ValidationError: If signed transaction is invalid
            TransactionError: If broadcasting fails
        """
        if not self.is_connected or not self.server:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        # Validate signed transaction
        if not signed_transaction or not signed_transaction.get('signed', False) or 'transaction_xdr' not in signed_transaction:
            raise ValidationError("Transaction is not signed")
            
        try:
            # Get the signed transaction XDR
            transaction_xdr = signed_transaction.get('transaction_xdr')
            
            # Submit the transaction to the network
            response = self.server.submit_transaction(transaction_xdr)
            
            # Get the transaction hash
            tx_hash = response['hash']
            
            # Create receipt
            receipt = {
                'txid': tx_hash,
                'hash': tx_hash,
                'confirmed': True,  # Stellar transactions are immediately confirmed
                'explorer_url': f"{self.explorer_tx_url}{tx_hash}",
                'from_address': signed_transaction['from_address'],
                'to_address': signed_transaction['to_address'],
                'amount': signed_transaction['amount'],
                'fee': signed_transaction['fee'],
                'status': 'success'
            }
            
            # Add memo if available
            if 'memo' in signed_transaction:
                receipt['memo'] = signed_transaction['memo']
            
            # Add asset details if not XLM
            if 'asset_code' in signed_transaction and signed_transaction['asset_code'] != 'XLM':
                receipt['asset_code'] = signed_transaction['asset_code']
                receipt['asset_issuer'] = signed_transaction['asset_issuer']
            
            # Add successful result details
            if 'successful' in response:
                receipt['successful'] = response['successful']
            
            if 'result_xdr' in response:
                receipt['result_xdr'] = response['result_xdr']
            
            return receipt
            
        except (BadResponseError, BadRequestError) as e:
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
        if not self.is_connected or not self.server:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not tx_id:
            raise ValidationError("Invalid transaction ID")
            
        try:
            # Get the transaction from the network
            tx = self.server.transactions().transaction(tx_id).call()
            
            # Build status object
            status = {
                'txid': tx_id,
                'hash': tx_id,
                'confirmed': True,  # If we can query it, it's confirmed on Stellar
                'status': 'success' if tx.get('successful', True) else 'failed',
                'explorer_url': f"{self.explorer_tx_url}{tx_id}",
                'ledger': tx.get('ledger'),
                'created_at': tx.get('created_at'),
                'fee_charged': tx.get('fee_charged'),
                'source_account': tx.get('source_account'),
                'memo': tx.get('memo'),
                'memo_type': tx.get('memo_type')
            }
            
            # Get operation details if available
            try:
                operations = self.server.operations().for_transaction(tx_id).call()
                if 'records' in operations and operations['records']:
                    ops_list = []
                    for op in operations['records']:
                        op_details = {
                            'id': op.get('id'),
                            'type': op.get('type')
                        }
                        
                        # Add payment-specific details
                        if op.get('type') == 'payment':
                            op_details['from'] = op.get('source_account')
                            op_details['to'] = op.get('to')
                            op_details['amount'] = op.get('amount')
                            op_details['asset_type'] = op.get('asset_type')
                            
                            if op.get('asset_type') != 'native':
                                op_details['asset_code'] = op.get('asset_code')
                                op_details['asset_issuer'] = op.get('asset_issuer')
                                
                        ops_list.append(op_details)
                        
                    status['operations'] = ops_list
            except Exception:
                # Ignore errors getting operations
                pass
                
            return status
                
        except NotFoundError:
            # Transaction not found
            return {
                'txid': tx_id,
                'hash': tx_id,
                'confirmed': False,
                'status': 'pending',
                'explorer_url': f"{self.explorer_tx_url}{tx_id}"
            }
        except (BadResponseError, BadRequestError) as e:
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
        if not self.is_connected or not self.server:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get network fee stats
            fee_stats = self.server.fee_stats().call()
            
            # Extract fee levels in stroops
            fee_charged = fee_stats.get('fee_charged')
            
            if not fee_charged:
                # Use default fee if no stats available
                min_fee_stroops = int(self.currency['min_fee'] * (10 ** self.currency['decimals']))
                avg_fee_stroops = min_fee_stroops * 2
                max_fee_stroops = min_fee_stroops * 5
            else:
                # Use network fee stats
                min_fee_stroops = int(fee_charged.get('min', self.currency['min_fee'] * (10 ** self.currency['decimals'])))
                avg_fee_stroops = int(fee_charged.get('mode', min_fee_stroops * 2))
                max_fee_stroops = int(fee_charged.get('max', min_fee_stroops * 5))
            
            # Calculate fees in XLM
            min_fee = Decimal(min_fee_stroops) / Decimal(10 ** self.currency['decimals'])
            avg_fee = Decimal(avg_fee_stroops) / Decimal(10 ** self.currency['decimals'])
            max_fee = Decimal(max_fee_stroops) / Decimal(10 ** self.currency['decimals'])
            
            # Always ensure minimum fee
            if min_fee < self.currency['min_fee']:
                min_fee = Decimal(self.currency['min_fee'])
            
            if avg_fee < self.currency['min_fee']:
                avg_fee = Decimal(self.currency['min_fee']) * Decimal('2')
                
            if max_fee < self.currency['min_fee']:
                max_fee = Decimal(self.currency['min_fee']) * Decimal('5')
            
            return {
                'slow': {
                    'fee': min_fee,
                    'fee_stroops': min_fee_stroops,
                    'time_estimate': 'up to 60 seconds'
                },
                'average': {
                    'fee': avg_fee,
                    'fee_stroops': avg_fee_stroops,
                    'time_estimate': '5-10 seconds'
                },
                'fast': {
                    'fee': max_fee,
                    'fee_stroops': max_fee_stroops,
                    'time_estimate': 'immediate'
                }
            }
                
        except (BadResponseError, BadRequestError) as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_network_status(self) -> Dict:
        """Get Stellar network status.
        
        Returns:
            dict: Network statistics and status
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.server:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get latest ledger information
            root_response = self.server.root().call()
            
            # Create network status object
            status = {
                'network_name': self.network_name,
                'core_version': root_response.get('core_version'),
                'horizon_version': root_response.get('horizon_version'),
                'history_elder_ledger': root_response.get('history_elder_ledger'),
                'history_latest_ledger': root_response.get('history_latest_ledger'),
                'network_passphrase': root_response.get('network_passphrase'),
                'protocol_version': root_response.get('protocol_version'),
            }
            
            # Try to get additional ledger info
            try:
                latest_ledger_num = root_response.get('history_latest_ledger')
                if latest_ledger_num:
                    ledger = self.server.ledgers().ledger(latest_ledger_num).call()
                    status['current_ledger'] = {
                        'hash': ledger.get('hash'),
                        'sequence': ledger.get('sequence'),
                        'closed_at': ledger.get('closed_at'),
                        'transaction_count': ledger.get('transaction_count'),
                        'operation_count': ledger.get('operation_count'),
                        'base_fee': ledger.get('base_fee'),
                    }
            except Exception:
                # Ignore errors when fetching additional info
                pass
                
            # Try to get fee stats
            try:
                fee_stats = self.server.fee_stats().call()
                if 'fee_charged' in fee_stats:
                    status['fee_stats'] = fee_stats['fee_charged']
            except Exception:
                # Ignore errors when fetching fee stats
                pass
                
            return status
                
        except (BadResponseError, BadRequestError) as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from Stellar network.
        
        Returns:
            bool: True if successfully disconnected
        """
        self.is_connected = False
        self.server = None
        self.keypair = None
        logger.info(f"Disconnected from {self.network_name}")
        return True
