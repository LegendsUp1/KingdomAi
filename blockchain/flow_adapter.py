#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Flow blockchain adapter implementation.
Native, no-fallback adapter for Flow network integration.
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

# Import Flow specific libraries
from flow_py_sdk import flow_client
from flow_py_sdk.cadence import Address
from flow_py_sdk.signer import InMemorySigner, HashAlgo, SignAlgo
from flow_py_sdk.client import AccessAPI
from flow_py_sdk.exceptions import FlowException
from flow_py_sdk.tx import Tx, ProposalKey, TransactionStatus

# Import cryptographic libraries
import hashlib
import ecdsa

# Import networking libraries for API calls
import requests
from requests.exceptions import RequestException

# Import logging
import logging
logger = logging.getLogger(__name__)


class FlowAdapter(BlockchainAdapter):
    """Native Flow blockchain adapter.
    
    Implements all required blockchain operations for Flow network
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Flow Mainnet',
            'access_node_api': 'access.mainnet.nodes.onflow.org:9000',
            'explorer_url': 'https://flowscan.org',
            'chain_id': 'flow-mainnet',
            'service_account': '0xe467b9dd11fa00df',
        },
        'testnet': {
            'name': 'Flow Testnet',
            'access_node_api': 'access.devnet.nodes.onflow.org:9000',
            'explorer_url': 'https://testnet.flowscan.org',
            'chain_id': 'flow-testnet',
            'service_account': '0x7e60df042a9c0868',
        },
        'emulator': {
            'name': 'Flow Emulator',
            'access_node_api': 'localhost:3569',
            'explorer_url': 'http://localhost:8080',
            'chain_id': 'flow-emulator',
            'service_account': '0xf8d6e0586b0a20c7',
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'FLOW': {
            'name': 'Flow',
            'symbol': 'FLOW',
            'decimals': 8,  # 1 FLOW = 10^8 smallest unit
            'min_fee': 0.00001  # Minimum transaction fee
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Flow adapter.
        
        Args:
            network: Network name ('mainnet', 'testnet', or 'emulator')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid
        """
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Flow network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.access_node_api = self.NETWORKS[network]['access_node_api']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.chain_id = self.NETWORKS[network]['chain_id']
        self.service_account = self.NETWORKS[network]['service_account']
        
        # Set currency details (FLOW)
        self.currency = self.CURRENCY['FLOW']
        
        # Set connection state
        self.is_connected = False
        self.client = None
        
        # Private key and account info
        self.private_key = None
        self.account_address = None
        self.account_key_index = 0  # Default key index
        self.signer = None
        
        # Override config if provided
        if config:
            if 'access_node_api' in config:
                self.access_node_api = config['access_node_api']
                
            if 'private_key' in config:
                self.private_key = config.get('private_key')
                
            if 'account_address' in config:
                self.account_address = config.get('account_address')
                
            if 'account_key_index' in config:
                self.account_key_index = config.get('account_key_index')
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        return f"FlowAdapter({self.network_name}, {connection_status})"
    
    @property
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/transaction/"
    
    @property
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/account/"
    
    @property
    def explorer_block_url(self) -> str:
        """Get block explorer URL template."""
        return f"{self.explorer_url}/block/"
    
    @strict_blockchain_operation
    def _verify_connection(self) -> bool:
        """Verify connection to Flow network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get latest block to verify connection
            latest_block = self.client.get_latest_block(is_sealed=True)
            if not latest_block:
                raise BlockchainConnectionError("Failed to get latest block")
                
            return True
        except FlowException as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Flow network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize Flow client
            self.client = flow_client.connect(
                host=self.access_node_api.split(':')[0],
                port=int(self.access_node_api.split(':')[1])
            )
            
            # Initialize signer if private key is provided
            if self.private_key and self.account_address:
                # Clean up address format if needed
                if self.account_address.startswith('0x'):
                    hex_address = self.account_address[2:]
                else:
                    hex_address = self.account_address
                    
                # Create signer
                self.signer = InMemorySigner(
                    hash_algo=HashAlgo.SHA3_256,
                    sign_algo=SignAlgo.ECDSA_P256,
                    private_key_hex=self.private_key
                )
                
                # Store formatted address
                self.account_address = f"0x{hex_address}"
            
            # Verify connection
            self._verify_connection()
            
            # Set connection status
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}")
            
            return True
            
        except FlowException as e:
            self.is_connected = False
            self.client = None
            self.signer = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
        except Exception as e:
            self.is_connected = False
            self.client = None
            self.signer = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    def validate_address(self, address: str) -> bool:
        """Validate Flow address format.
        
        Args:
            address: Flow address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Flow addresses are hexadecimal and start with '0x'
            if not address.startswith('0x'):
                return False
                
            # Remove '0x' prefix and check if it's valid hex
            hex_part = address[2:]
            if not all(c in '0123456789abcdefABCDEF' for c in hex_part):
                return False
                
            # Flow addresses are 16 characters after the '0x' prefix
            if len(hex_part) != 16:
                return False
                
            return True
            
        except Exception:
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate Flow private key format.
        
        Args:
            private_key: Private key to validate (hex string)
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Flow private keys are 64 character hex strings
            if len(private_key) != 64:
                return False
                
            # Check if it's valid hex
            if not all(c in '0123456789abcdefABCDEF' for c in private_key):
                return False
                
            # Try to create a signer with it
            test_signer = InMemorySigner(
                hash_algo=HashAlgo.SHA3_256,
                sign_algo=SignAlgo.ECDSA_P256,
                private_key_hex=private_key
            )
            
            # If we got here, it's valid
            return True
            
        except Exception:
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str, token_id: str = None) -> Decimal:
        """Get FLOW balance for address.
        
        Args:
            address: Flow address to query
            token_id: Optional token ID for other tokens
            
        Returns:
            Decimal: Balance in FLOW
            
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
            account = self.client.get_account(address=Address.from_hex(address))
            
            if not account:
                raise BlockchainConnectionError(f"Failed to get account for address {address}")
                
            # Get balance in smallest unit
            balance_smallest_unit = account.balance
            
            # Convert to FLOW
            balance_flow = Decimal(balance_smallest_unit) / Decimal(10 ** self.currency['decimals'])
            
            return balance_flow
                
        except FlowException as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict) -> Dict:
        """Create Flow transaction.
        
        Args:
            transaction: Transaction details with the following fields:
                - to_address: Recipient address
                - from_address: Sender address
                - amount: Amount to send in FLOW
                - gas_limit: Optional gas limit (default 1000)
                - reference_block_id: Optional reference block ID
                - proposal_key_address: Optional proposal key address
                - proposal_key_index: Optional proposal key index
                - proposal_key_sequence: Optional proposal key sequence number
                - payer: Optional payer address (defaults to sender)
                - script: Optional Cadence script for advanced transactions
                - args: Optional args for the script
                
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
            gas_limit = transaction.get('gas_limit', 1000)  # Default gas limit
            
            # Optional parameters
            reference_block_id = transaction.get('reference_block_id')
            proposal_key_address = transaction.get('proposal_key_address', from_address)
            proposal_key_index = transaction.get('proposal_key_index', self.account_key_index)
            proposal_key_sequence = transaction.get('proposal_key_sequence')  # Will fetch if not provided
            payer = transaction.get('payer', from_address)
            script = transaction.get('script')  # Optional custom script
            args = transaction.get('args', [])  # Arguments for the script
            
            # Validate addresses
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            if not self.validate_address(from_address):
                raise ValidationError(f"Invalid sender address: {from_address}")
                
            # Validate amount
            if amount is None or not isinstance(amount, (int, float, Decimal)) or amount < 0:
                raise ValidationError(f"Invalid amount: {amount}")
            
            # Convert FLOW amount to the smallest unit
            if isinstance(amount, (float, Decimal)):
                amount_smallest_unit = int(amount * (10 ** self.currency['decimals']))
            else:
                amount_smallest_unit = amount
            
            # Get the latest block if reference block not provided
            if not reference_block_id:
                latest_block = self.client.get_latest_block(is_sealed=True)
                reference_block_id = latest_block.id
            
            # Get the sequence number if not provided
            if proposal_key_sequence is None:
                # Convert address format if needed
                if proposal_key_address.startswith('0x'):
                    pk_address_hex = proposal_key_address[2:]
                else:
                    pk_address_hex = proposal_key_address
                    
                account = self.client.get_account(Address.from_hex(pk_address_hex))
                proposal_key_sequence = account.keys[proposal_key_index].sequence_number
            
            # Create the transaction
            tx = None
            
            # Use custom script if provided, otherwise build a transfer script
            if script:
                tx = Tx(
                    code=script,
                    reference_block_id=reference_block_id,
                    gas_limit=gas_limit,
                    payer=Address.from_hex(payer[2:] if payer.startswith('0x') else payer),
                    proposal_key=ProposalKey(
                        address=Address.from_hex(proposal_key_address[2:] if proposal_key_address.startswith('0x') else proposal_key_address),
                        key_id=proposal_key_index,
                        sequence_number=proposal_key_sequence
                    )
                )
                
                # Add arguments to the script
                for arg in args:
                    tx.add_argument(arg)
            else:
                # Build standard transfer transaction script
                transfer_script = """
                import FungibleToken from 0x9a0766d93b6608b7
                import FlowToken from 0x7e60df042a9c0868
                
                transaction(amount: UFix64, to: Address) {
                    let sentVault: @FungibleToken.Vault
                    prepare(signer: AuthAccount) {
                        let vaultRef = signer.borrow<&FlowToken.Vault>(from: /storage/flowTokenVault)
                            ?? panic("Could not borrow reference to the owner's vault")
                        self.sentVault <- vaultRef.withdraw(amount: amount)
                    }
                    
                    execute {
                        let receiverRef = getAccount(to)
                            .getCapability(/public/flowTokenReceiver)
                            .borrow<&{FungibleToken.Receiver}>()
                            ?? panic("Could not borrow receiver reference to the recipient's vault")
                        receiverRef.deposit(from: <-self.sentVault)
                    }
                }
                """
                
                # For mainnet, use the correct imports
                if self.network == 'mainnet':
                    transfer_script = transfer_script.replace(
                        "0x9a0766d93b6608b7", "0xf233dcee88fe0abe")
                    transfer_script = transfer_script.replace(
                        "0x7e60df042a9c0868", "0x1654653399040a61")
                
                # Create Flow transaction
                tx = Tx(
                    code=transfer_script,
                    reference_block_id=reference_block_id,
                    gas_limit=gas_limit,
                    payer=Address.from_hex(payer[2:] if payer.startswith('0x') else payer),
                    proposal_key=ProposalKey(
                        address=Address.from_hex(proposal_key_address[2:] if proposal_key_address.startswith('0x') else proposal_key_address),
                        key_id=proposal_key_index,
                        sequence_number=proposal_key_sequence
                    )
                )
                
                # Add standard transfer args
                # Convert amount to UFix64 string format
                amount_str = f"{amount_smallest_unit / (10 ** self.currency['decimals']):.8f}"
                tx.add_argument(amount_str)
                tx.add_argument(Address.from_hex(to_address[2:] if to_address.startswith('0x') else to_address))
            
            # Add authorization (this will be signed later)
            tx.add_authorizer(Address.from_hex(from_address[2:] if from_address.startswith('0x') else from_address))
            
            # Return transaction object with additional metadata
            return {
                'network': self.network,
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount,
                'amount_smallest_unit': amount_smallest_unit,
                'gas_limit': gas_limit,
                'reference_block_id': reference_block_id,
                'proposal_key_address': proposal_key_address,
                'proposal_key_index': proposal_key_index,
                'proposal_key_sequence': proposal_key_sequence,
                'payer': payer,
                'tx_object': tx,  # The actual Flow SDK transaction object
                'signed': False
            }
            
        except FlowException as e:
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
        """Sign Flow transaction.
        
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
        if not transaction or 'tx_object' not in transaction:
            raise ValidationError("Invalid transaction object")
            
        try:
            # Get the transaction object
            tx = transaction['tx_object']
            
            # Get signing key
            signing_key = None
            
            # Use provided private key if available
            if private_key:
                if not self.validate_private_key(private_key):
                    raise WalletError("Invalid private key format")
                signing_key = InMemorySigner(
                    hash_algo=HashAlgo.SHA3_256,
                    sign_algo=SignAlgo.ECDSA_P256,
                    private_key_hex=private_key
                )
                
            # Otherwise use adapter's key if available
            elif self.private_key and self.signer:
                signing_key = self.signer
                
            # If no key is available, raise error
            if not signing_key:
                raise WalletError("No private key available for signing")
                
            # Sign the transaction
            # First, sign the envelope with proposer
            from_address = transaction['from_address']
            proposal_key_address = transaction['proposal_key_address']
            
            # Clean address format if needed
            if from_address.startswith('0x'):
                from_hex = from_address[2:]
            else:
                from_hex = from_address
                
            if proposal_key_address.startswith('0x'):
                proposal_hex = proposal_key_address[2:]
            else:
                proposal_hex = proposal_key_address
            
            # Sign as proposal key account
            tx.sign(signer=signing_key)
            
            # Sign as payer if different
            payer = transaction['payer']
            if payer.startswith('0x'):
                payer_hex = payer[2:]
            else:
                payer_hex = payer
                
            if payer_hex != proposal_hex:
                tx.sign(signer=signing_key, address=Address.from_hex(payer_hex))
            
            # Sign as authorizer if different from proposer and payer
            if from_hex != proposal_hex and from_hex != payer_hex:
                tx.sign(signer=signing_key, address=Address.from_hex(from_hex))
            
            # Return signed transaction
            signed_tx = transaction.copy()
            signed_tx['signed'] = True
            signed_tx['tx_object'] = tx
            
            # Add signature info
            signed_tx['tx_id'] = tx.id
            signed_tx['signed_payload_hex'] = tx.build_payload().hex()
            
            return signed_tx
            
        except FlowException as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast signed Flow transaction.
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            dict: Transaction receipt with id and status
            
        Raises:
            ValidationError: If signed transaction is invalid
            TransactionError: If broadcasting fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        # Validate signed transaction
        if not signed_transaction or not signed_transaction.get('signed', False) or 'tx_object' not in signed_transaction:
            raise ValidationError("Transaction is not signed")
            
        try:
            # Get the signed transaction object
            tx = signed_transaction['tx_object']
            
            # Send the transaction to the network
            self.client.send_transaction(tx)
            
            # Create receipt
            receipt = {
                'txid': tx.id.hex(),
                'confirmed': False,  # Just sent, not confirmed yet
                'explorer_url': f"{self.explorer_tx_url}{tx.id.hex()}",
                'from_address': signed_transaction['from_address'],
                'to_address': signed_transaction['to_address'],
                'amount': signed_transaction['amount'],
                'status': 'pending'
            }
            
            return receipt
            
        except FlowException as e:
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
            tx_id: Transaction ID (hex string)
            
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
            # Clean up transaction ID if needed
            if tx_id.startswith('0x'):
                tx_id = tx_id[2:]
                
            # Get transaction result from the network
            tx_result = self.client.get_transaction(tx_id)
            
            if not tx_result:
                return {
                    'txid': tx_id,
                    'confirmed': False,
                    'status': 'not_found',
                    'explorer_url': f"{self.explorer_tx_url}{tx_id}"
                }
            
            # Map Flow status to our standard status
            status_map = {
                TransactionStatus.UNKNOWN: 'unknown',
                TransactionStatus.PENDING: 'pending',
                TransactionStatus.FINALIZED: 'finalized',  # Block is sealed
                TransactionStatus.EXECUTED: 'executed',     # Executed but block not yet sealed
                TransactionStatus.SEALED: 'success',        # Fully confirmed
                TransactionStatus.EXPIRED: 'failed'         # Expired
            }
            
            status = status_map.get(tx_result.status, 'unknown')
            confirmed = status in ('success', 'failed', 'finalized', 'sealed')
            
            # Get transaction result if available
            tx_details = {}
            if tx_result.status in (TransactionStatus.SEALED, TransactionStatus.EXECUTED):
                try:
                    # Get execution result
                    tx_details = self.client.get_transaction_result(tx_id)
                except Exception:
                    # Ignore errors getting details
                    pass
            
            # Build result object
            result = {
                'txid': tx_id,
                'confirmed': confirmed,
                'status': status,
                'explorer_url': f"{self.explorer_tx_url}{tx_id}",
                'block_id': getattr(tx_result, 'block_id', None),
                'block_height': getattr(tx_result, 'block_height', None),
            }
            
            # Add execution details if available
            if tx_details:
                result.update({
                    'events': tx_details.events,
                    'status_code': tx_details.status_code,
                    'error_message': tx_details.error_message if hasattr(tx_details, 'error_message') else None,
                })
                
            return result
                
        except FlowException as e:
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
            dict: Fee estimates (standard fee in Flow)
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Flow has fixed fees based on computation units used
            # For a simple transfer, this is around 0.00001 FLOW
            standard_fee = self.currency['min_fee']
            
            # Return fee estimate
            return {
                'fee': standard_fee,
                'time_estimate': '< 10 seconds'
            }
                
        except FlowException as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_network_status(self) -> Dict:
        """Get Flow network status.
        
        Returns:
            dict: Network statistics and status
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Get latest sealed block
            latest_block = self.client.get_latest_block(is_sealed=True)
            height = latest_block.height
            
            # Get chain ID
            chain_id = self.chain_id
            
            # Get protocol state
            protocol_state = self.client.get_network_parameters()
            
            # Get network stats
            stats = {
                'network_name': self.network_name,
                'chain_id': chain_id,
                'chain_height': height,
                'protocol_state': protocol_state,
                'timestamp': int(time.time())
            }
            
            return stats
                
        except FlowException as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from Flow network.
        
        Returns:
            bool: True if successfully disconnected
        """
        self.is_connected = False
        self.client = None
        self.signer = None
        logger.info(f"Disconnected from {self.network_name}")
        return True
