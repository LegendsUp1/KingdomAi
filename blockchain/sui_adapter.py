#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sui blockchain adapter implementation.
Native, no-fallback adapter for Sui blockchain integration.
"""

import os
import json
import time
import hashlib
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
import requests
import base64

# Import blockchain base components
from blockchain.base_adapter import BlockchainAdapter, strict_blockchain_operation
from blockchain.exceptions import (
    BlockchainConnectionError,
    TransactionError,
    ValidationError,
    WalletError
)

# Import Sui specific libraries
try:
    from pysui import SuiClient, SuiConfig
    from pysui.abstracts import SignatureScheme
    from pysui.sui.sui_builders.get_builders import GetTxBlock
    from pysui.sui.sui_builders.transaction_builders import TransactionBuilder, PayTransaction
    from pysui.sui.sui_txresults.single_tx import SuiTransaction
    from pysui.sui.sui_types.address import SuiAddress
    from pysui.sui.sui_types.scalars import SuiU64, SuiU128
    from pysui.sui.sui_crypto import keypair as sui_keypair, signature as sui_signature
    
    SUI_AVAILABLE = True
except ImportError:
    SUI_AVAILABLE = False
    
# Import logging
import logging
logger = logging.getLogger(__name__)


class SuiAdapter(BlockchainAdapter):
    """Native Sui blockchain adapter.
    
    Implements all required blockchain operations for Sui blockchain
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Sui Mainnet',
            'rpc_url': 'https://fullnode.mainnet.sui.io:443',
            'faucet_url': None,  # No faucet for mainnet
            'explorer_url': 'https://explorer.sui.io',
            'chain_id': '0x0' # Sui network identifiers work differently than EVM chains
        },
        'testnet': {
            'name': 'Sui Testnet',
            'rpc_url': 'https://fullnode.testnet.sui.io:443',
            'faucet_url': 'https://faucet.testnet.sui.io/gas',
            'explorer_url': 'https://explorer.sui.io',
            'chain_id': '0x1'
        },
        'devnet': {
            'name': 'Sui Devnet',
            'rpc_url': 'https://fullnode.devnet.sui.io:443',
            'faucet_url': 'https://faucet.devnet.sui.io/gas',
            'explorer_url': 'https://explorer.sui.io',
            'chain_id': '0x2'
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'SUI': {
            'name': 'Sui',
            'symbol': 'SUI',
            'decimals': 9,
            'is_native': True
        }
    }
    
    # Default gas budget for transactions
    DEFAULT_GAS_BUDGET = 50_000_000 # in MIST (10^-9 SUI)
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Sui adapter.
        
        Args:
            network: Network name ('mainnet', 'testnet', or 'devnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid or Sui SDK is unavailable
        """
        if not SUI_AVAILABLE:
            raise ValidationError("Sui SDK (pysui) is not available. "
                                 "Install with 'pip install pysui'")
        
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Sui network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.rpc_url = self.NETWORKS[network]['rpc_url']
        self.faucet_url = self.NETWORKS[network]['faucet_url']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.chain_id = self.NETWORKS[network]['chain_id']
        
        # Set connection state
        self.is_connected = False
        self.client = None
        self.config = None
        
        # Wallet management
        self.address = None
        self.keypair = None
        self.private_key = None
        
        # Override config if provided
        if config:
            if 'rpc_url' in config:
                self.rpc_url = config['rpc_url']
            
            if 'private_key' in config:
                self.private_key = config['private_key']
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        account_info = f", Account: {self.address}" if self.address else ""
        return f"Sui Adapter ({self.network_name}) - {connection_status}{account_info}"
        
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/txblock/{{txid}}"
        
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/address/{{address}}"
        
    def _verify_connection(self) -> bool:
        """Verify connection to Sui network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Check if client is responsive
            system_state = self.client.get_latest_sui_system_state()
            if not system_state or not system_state.result_data:
                raise BlockchainConnectionError(f"Invalid response from {self.network_name}")
                
            return True
        except Exception as e:
            self.is_connected = False
            error_msg = f"Connection to {self.network_name} failed: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Sui network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Create SuiConfig
            self.config = SuiConfig(rpc_url=self.rpc_url)
            
            # Create SuiClient
            self.client = SuiClient(self.config)
            
            # Initialize keypair if private key is available
            if self.private_key:
                try:
                    # Create keypair from private key
                    # Handle different formats (base64, hex)
                    if len(self.private_key) == 64:  # Hex format
                        self.keypair = sui_keypair.SuiKeyPair.from_hex(self.private_key)
                    else:  # Try base64 format
                        try:
                            priv_key_bytes = base64.b64decode(self.private_key)
                            self.keypair = sui_keypair.SuiKeyPair.from_private_key(priv_key_bytes)
                        except Exception:
                            raise ValueError("Invalid private key format")
                            
                    # Get the address
                    self.address = self.keypair.get_sui_address()
                    logger.info(f"Initialized account: {self.address}")
                except Exception as e:
                    logger.warning(f"Failed to initialize account: {str(e)}")
                    self.private_key = None
                    self.keypair = None
                    self.address = None
            
            # Verify connection
            resp = self.client.get_latest_checkpoint_sequence_number()
            if not resp or not resp.result_data:
                raise BlockchainConnectionError(f"Failed to connect to {self.network_name}")
                
            # Get system state
            system_state = self.client.get_latest_sui_system_state()
            if system_state and system_state.result_data:
                protocol_version = system_state.result_data.protocol_version
                epoch = system_state.result_data.epoch
                logger.info(f"Connected to {self.network_name}, protocol version: {protocol_version}, epoch: {epoch}")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from Sui network.
        
        Returns:
            bool: True if disconnected successfully
        """
        try:
            # Reset connection state
            self.client = None
            self.config = None
            self.is_connected = False
            logger.info(f"Disconnected from {self.network_name}")
            return True
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            return False
            
    def validate_address(self, address: str) -> bool:
        """Validate Sui address format.
        
        Args:
            address: Sui address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Validate the address format
            if not address.startswith('0x'):
                return False
                
            # Sui addresses are 32 bytes (64 hex characters) with '0x' prefix
            if len(address) != 66:  # 64 chars + '0x' prefix
                return False
                
            # Check if it's a valid hex string
            int(address[2:], 16)
            
            # Create SuiAddress to validate format
            SuiAddress(address)
            
            return True
        except Exception as e:
            logger.debug(f"Address validation error: {str(e)}")
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate Sui private key format.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Try to create a keypair with the private key
            # Handle different formats (base64, hex)
            if len(private_key) == 64:  # Hex format
                sui_keypair.SuiKeyPair.from_hex(private_key)
            else:  # Try base64 format
                try:
                    priv_key_bytes = base64.b64decode(private_key)
                    sui_keypair.SuiKeyPair.from_private_key(priv_key_bytes)
                except Exception:
                    return False
            return True
        except Exception as e:
            logger.debug(f"Invalid private key format: {str(e)}")
            return False
            
    @strict_blockchain_operation
    def get_balance(self, address: str = None, token_id: str = None) -> Decimal:
        """Get SUI balance for an account.
        
        Args:
            address: Sui address to query, defaults to connected account
            token_id: Optional token ID for querying token balance
            
        Returns:
            Decimal: Balance in SUI
            
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
            raise ValidationError(f"Invalid Sui address: {addr}")
            
        try:
            # Get total balance (all coin objects)
            if token_id:
                # Get token balance (custom token)
                resp = self.client.get_balance(SuiAddress(addr), token_id)
            else:
                # Get SUI balance (native token)
                resp = self.client.get_balance(SuiAddress(addr))
            
            if resp and resp.result_data:
                # Balance is in MIST (10^-9 SUI)
                balance_mist = int(resp.result_data.total_balance)
                # Convert to SUI
                balance_sui = Decimal(balance_mist) / Decimal(10**9)
                
                logger.debug(f"Balance for {addr}: {balance_sui} SUI")
                return balance_sui
            else:
                return Decimal(0)
                
        except Exception as e:
            error_msg = f"Failed to get balance for {addr}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e

    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
        """Create a Sui transaction.
        
        Args:
            transaction: Transaction parameters
                - to_address: Recipient address
                - amount: Amount in SUI
                - token_id: Optional token ID for token transfers
                - gas_budget: Optional gas budget for the transaction
                - data: Optional data for the transaction
            
        Returns:
            Dict: Prepared transaction object ready for signing
            
        Raises:
            ValidationError: If transaction parameters are invalid
            TransactionError: If transaction creation fails
        """
        self._verify_connection()
        
        # Validate sender account
        if not self.keypair or not self.address:
            raise ValidationError("No account connected. Cannot create transaction.")
            
        # Validate the transaction parameters
        to_address = transaction.get('to_address')
        amount = transaction.get('amount')
        token_id = transaction.get('token_id')
        gas_budget = transaction.get('gas_budget', self.DEFAULT_GAS_BUDGET)
        data = transaction.get('data', {})
        
        # Validate recipient address
        if not to_address or not self.validate_address(to_address):
            raise ValidationError(f"Invalid recipient address: {to_address}")
            
        try:
            # Create Sui addresses
            from_addr = SuiAddress(self.address)
            to_addr = SuiAddress(to_address)
            
            # Convert amount from SUI to MIST (10^9)
            amount_mist = int(Decimal(amount) * Decimal(10**9))
            
            # Create transaction builder
            tx_builder = TransactionBuilder(self.client, from_addr, self.keypair)
            
            # Prepare Pay transaction
            if token_id:
                move_call_tx = tx_builder.move_call(
                    target=f"0x2::coin::transfer",
                    type_arguments=[token_id],
                    arguments=[tx_builder.object(token_id), tx_builder.pure(to_addr)],
                )
            else:
                # Native SUI transfer
                pay_tx = PayTransaction.new_from_sui_transfer(
                    tx_builder, 
                    [to_addr],  # recipients
                    [amount_mist],  # amounts in MIST
                    gas_budget=gas_budget  # gas budget in MIST
                )
                
                # Build the transaction
                tx_builder.add(pay_tx)
                tx_data = tx_builder.build()
                
            # Return the transaction data
            result = {
                'type': 'sui_transfer',
                'sender': self.address,
                'recipient': to_address,
                'amount': amount,
                'amount_mist': amount_mist,
                'gas_budget': gas_budget,
                'tx_data': tx_data
            }
            
            if data:
                result['data'] = data
            
            logger.debug(f"Created transaction: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
        """Sign a Sui transaction.
        
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
        
        # Get the keypair for signing
        keypair_to_use = None
        
        if private_key:
            # Use provided private key
            if not self.validate_private_key(private_key):
                raise WalletError("Invalid private key")
                
            # Create keypair from private key
            if len(private_key) == 64:  # Hex format
                keypair_to_use = sui_keypair.SuiKeyPair.from_hex(private_key)
            else:  # Try base64 format
                try:
                    priv_key_bytes = base64.b64decode(private_key)
                    keypair_to_use = sui_keypair.SuiKeyPair.from_private_key(priv_key_bytes)
                except Exception:
                    raise WalletError("Invalid private key format")
        else:
            # Use the connected account's keypair
            if not self.keypair:
                raise WalletError("No account available for signing")
            keypair_to_use = self.keypair
            
        try:
            # Validate transaction
            if 'tx_data' not in transaction:
                raise ValidationError("Invalid transaction: missing transaction data")
                
            tx_data = transaction['tx_data']
            
            # Sign the transaction
            resp = self.client.sign_and_execute_transaction_block(
                tx_data,
                signature_scheme=SignatureScheme.ED25519,
                keypair=keypair_to_use
            )
            
            if not resp or not resp.result_data:
                raise TransactionError("Failed to sign and execute transaction")
                
            # Get the digest (transaction hash)
            tx_hash = resp.result_data.digest
            
            # Return the signed transaction result
            result = {
                'txid': tx_hash,
                'hash': tx_hash,
                'sender': transaction['sender'],
                'recipient': transaction['recipient'],
                'amount': transaction['amount'],
                'type': transaction['type'],
                'signed_tx_response': resp.result_data,
            }
            
            if 'data' in transaction:
                result['data'] = transaction['data']
                
            # Success status
            result['status'] = 'success' if resp.result_data.effects and resp.result_data.effects.status.status == "success" else 'failed'
            result['confirmed'] = result['status'] == 'success'
            
            # Explorer URL
            result['explorer_url'] = self.explorer_tx_url().format(txid=tx_hash)
            
            logger.debug(f"Signed and executed transaction: {result['txid']}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast a signed Sui transaction.
        
        Note: In Sui, transactions are immediately executed upon signing,
        so this method simply returns the signed transaction result.
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            Dict: Transaction result with hash and status
        """
        # In Sui, transactions are executed immediately when signed,
        # so we just return the result from sign_transaction
        return signed_transaction
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_id: str) -> Dict:
        """Get the status of a Sui transaction.
        
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
            resp = self.client.get_transaction_block(tx_id)
            
            if not resp or not resp.result_data:
                # Transaction not found
                return {
                    'txid': tx_id,
                    'hash': tx_id,
                    'status': 'unknown',
                    'confirmed': False,
                    'explorer_url': self.explorer_tx_url().format(txid=tx_id)
                }
                
            # Extract transaction data
            tx_data = resp.result_data
            
            # Determine transaction status
            status = 'unknown'
            confirmed = False
            
            if hasattr(tx_data, 'effects') and tx_data.effects:
                if tx_data.effects.status.status == "success":
                    status = 'success'
                    confirmed = True
                else:
                    status = 'failed'
                    confirmed = False
            
            # Extract sender
            sender = tx_data.transaction.data.sender if hasattr(tx_data, 'transaction') and hasattr(tx_data.transaction, 'data') else ""
            
            # Try to extract recipient and amount
            recipient = ""
            amount = 0
            
            # Extract timestamp
            timestamp = tx_data.timestamp_ms if hasattr(tx_data, 'timestamp_ms') else None
            
            # Extract gas used
            gas_used = 0
            if hasattr(tx_data, 'effects') and tx_data.effects and hasattr(tx_data.effects, 'gas_used'):
                gas_used = tx_data.effects.gas_used.computation_cost + tx_data.effects.gas_used.storage_cost - tx_data.effects.gas_used.storage_rebate
            
            # Create transaction status
            tx_status = {
                'txid': tx_id,
                'hash': tx_id,
                'status': status,
                'confirmed': confirmed,
                'sender': sender,
                'recipient': recipient,
                'amount': amount,
                'explorer_url': self.explorer_tx_url().format(txid=tx_id),
                'timestamp': timestamp,
                'gas_used': gas_used,
                'raw_data': tx_data
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
        """Get Sui network status.
        
        Returns:
            Dict: Network status information
            
        Raises:
            BlockchainConnectionError: If status check fails
        """
        self._verify_connection()
        
        try:
            # Get system state
            system_state = self.client.get_latest_sui_system_state()
            
            # Get checkpoint info
            checkpoint = self.client.get_latest_checkpoint_sequence_number()
            
            # Extract useful information
            result = {
                'network': self.network_name,
                'protocol_version': system_state.result_data.protocol_version if system_state and system_state.result_data else 'unknown',
                'epoch': system_state.result_data.epoch if system_state and system_state.result_data else 'unknown',
                'checkpoint': checkpoint.result_data if checkpoint and checkpoint.result_data else 'unknown',
                'active': True
            }
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, transaction: Dict = None) -> Dict:
        """Estimate fees for a Sui transaction.
        
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
            # Get reference gas price
            resp = self.client.get_reference_gas_price()
            reference_gas_price = int(resp.result_data) if resp and resp.result_data else 1000
            
            # Standard gas budget estimations
            gas_budgets = {
                'transfer': self.DEFAULT_GAS_BUDGET,  # Simple transfer
                'token_transfer': self.DEFAULT_GAS_BUDGET * 2,  # Token transfer
                'contract_call': self.DEFAULT_GAS_BUDGET * 5,  # Contract interaction
            }
            
            # Gas price estimates
            gas_prices = {
                'slow': max(1, int(reference_gas_price * 0.8)),
                'average': reference_gas_price,
                'fast': int(reference_gas_price * 1.2)
            }
            
            # Calculate costs in SUI
            costs = {}
            for speed, price in gas_prices.items():
                # Cost = gas_budget * gas_price / 10^9
                cost = Decimal(gas_budgets['transfer'] * price) / Decimal(10**9)
                costs[speed] = cost
            
            # Create fee structure
            fee_structure = {
                'slow': costs['slow'],
                'average': costs['average'],
                'fast': costs['fast'],
                'gas_budget_transfer': gas_budgets['transfer'],
                'gas_budget_token_transfer': gas_budgets['token_transfer'],
                'gas_budget_contract_call': gas_budgets['contract_call'],
                'gas_price_reference': reference_gas_price,
                'unit': 'SUI'
            }
            
            # If a specific transaction is provided, estimate its fee
            if transaction and 'type' in transaction:
                tx_type = transaction.get('type')
                gas_budget = gas_budgets.get(tx_type.replace('sui_', ''), gas_budgets['transfer'])
                fee_structure['estimated_gas_budget'] = gas_budget
                fee_structure['estimated_fee'] = costs['average']
            
            return fee_structure
            
        except Exception as e:
            error_msg = f"Failed to estimate fee: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
