#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cardano blockchain adapter implementation.
Native, no-fallback adapter for Cardano network integration.
"""

import json
import os
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

# Import Cardano specific libraries
from pycardano import (
    Network, 
    BlockFrostChainContext, 
    Address, 
    Transaction,
    TransactionBody,
    TransactionInput,
    TransactionOutput,
    Value,
    TransactionWitnessSet,
    AuxiliaryData,
    VerificationKeyWitness,
    PlutusData,
    RedeemerTag,
    Redeemer,
    Ed25519KeyHash,
    PublicKey,
    PrivateKey,
    PaymentSigningKey,
    PaymentVerificationKey,
    HDWallet,
    TransactionBuilder,
    MultiAsset,
    AssetName,
    ScriptHash,
    min_ada_required
)

# Import logging
import logging
logger = logging.getLogger(__name__)


class CardanoAdapter(BlockchainAdapter):
    """Native Cardano blockchain adapter.
    
    Implements all required blockchain operations for Cardano network
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Cardano Mainnet',
            'network_id': Network.MAINNET,
            'blockfrost_project_id': os.environ.get('CARDANO_MAINNET_BLOCKFROST_KEY', ''),
            'blockfrost_url': 'https://cardano-mainnet.blockfrost.io/api/v0',
            'explorer_url': 'https://cardanoscan.io'
        },
        'testnet': {
            'name': 'Cardano Testnet',
            'network_id': Network.TESTNET,
            'blockfrost_project_id': os.environ.get('CARDANO_TESTNET_BLOCKFROST_KEY', ''),
            'blockfrost_url': 'https://cardano-testnet.blockfrost.io/api/v0',
            'explorer_url': 'https://testnet.cardanoscan.io'
        },
        'preview': {
            'name': 'Cardano Preview',
            'network_id': Network.TESTNET,
            'blockfrost_project_id': os.environ.get('CARDANO_PREVIEW_BLOCKFROST_KEY', ''),
            'blockfrost_url': 'https://cardano-preview.blockfrost.io/api/v0',
            'explorer_url': 'https://preview.cardanoscan.io'
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'ADA': {
            'name': 'Cardano',
            'symbol': 'ADA',
            'decimals': 6,  # Lovelace = 10^6 ADA
            'min_fee': 44  # Minimum transaction fee in lovelace (0.000044 ADA)
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Cardano adapter.
        
        Args:
            network: Network name ('mainnet', 'testnet', or 'preview')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid
        """
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Cardano network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.network_id = self.NETWORKS[network]['network_id']
        self.blockfrost_project_id = self.NETWORKS[network]['blockfrost_project_id']
        self.blockfrost_url = self.NETWORKS[network]['blockfrost_url']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        
        # Set currency details (ADA)
        self.currency = self.CURRENCY['ADA']
        
        # Set connection state
        self.is_connected = False
        self.context = None
        
        # Override config if provided
        if config:
            if 'blockfrost_project_id' in config:
                self.blockfrost_project_id = config['blockfrost_project_id']
                
            if 'blockfrost_url' in config:
                self.blockfrost_url = config['blockfrost_url']
                
        # Validate BlockFrost project ID
        if not self.blockfrost_project_id:
            logger.warning(f"No BlockFrost project ID provided for {self.network_name}. "
                          f"Set CARDANO_{network.upper()}_BLOCKFROST_KEY environment variable "
                          f"or provide in config.")
            
        super().__init__(network_name=self.network_name, currency_symbol='ADA')
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        return f"CardanoAdapter({self.network_name}, {connection_status})"
    
    @property
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/transaction/"
    
    @property
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/address/"
    
    @strict_blockchain_operation
    def _verify_connection(self) -> bool:
        """Verify connection to Cardano network via BlockFrost.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.context:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Query network parameters as connection test
            self.context.get_protocol_parameters()
            return True
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Cardano network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Check if we have a valid BlockFrost project ID
            if not self.blockfrost_project_id:
                raise BlockchainConnectionError(
                    f"Missing BlockFrost project ID for {self.network_name}. "
                    f"Set CARDANO_{self.network.upper()}_BLOCKFROST_KEY environment variable "
                    f"or provide in config."
                )
            
            # Create BlockFrost context
            self.context = BlockFrostChainContext(
                project_id=self.blockfrost_project_id,
                base_url=self.blockfrost_url,
                network=self.network_id
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
            
    @strict_blockchain_operation
    def get_balance(self, address: str, token_id: str = None) -> Decimal:
        """Get ADA balance for address.
        
        Args:
            address: Cardano address (Bech32 or Byron format)
            
        Returns:
            Decimal: ADA balance in ADA units (not lovelace)
            
        Raises:
            ValidationError: If address is invalid
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.context:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Validate address
            if not self.validate_address(address):
                raise ValidationError(f"Invalid Cardano address: {address}")
                
            # Query address on chain through BlockFrost
            addr_details = self.context.api.addresses(address)
            
            # Extract balance info
            if not addr_details:
                # Address exists but has no transactions/balance
                return Decimal('0')
                
            # BlockFrost returns amount in lovelace
            lovelace_amount = int(addr_details.amount[0].quantity)
            
            # Convert lovelace to ADA (1 ADA = 1,000,000 lovelace)
            ada_balance = Decimal(lovelace_amount) / Decimal(10 ** self.currency['decimals'])
            
            return ada_balance
            
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to get balance for address {address}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    def validate_address(self, address: str) -> bool:
        """Validate Cardano address format.
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid, False otherwise
        """
        if not address:
            return False
            
        try:
            # Convert string to Address object
            # This will raise an error if the address is invalid
            addr = Address.from_primitive(address)
            
            # For extra validation, check network compatibility
            # For enterprise addresses, staking addresses, etc., network validation is different
            # This is a simple validation that works for most cases
            try:
                network = addr.network
                # Check if address network matches the adapter's network
                # Note: Some addresses may not have network info, so we're lenient here
                if hasattr(addr, 'network') and network != self.network_id:
                    logger.warning(f"Address {address} is for a different network")
                    # Still return True as the address is technically valid
                    # Application logic can enforce stricter network matching if needed
            except Exception as e:
                logger.debug(f"Could not validate address network: {str(e)}")
                # Still proceed - address format is valid even if network can't be determined
                
            return True
            
        except Exception as e:
            logger.debug(f"Invalid Cardano address {address}: {str(e)}")
            return False
            
    @strict_blockchain_operation
    def create_transaction(self, **kwargs) -> Dict[str, Any]:
        """Create a Cardano transaction.
        
        Args:
            **kwargs: Transaction parameters including:
                - from_address: Sender address
                - to_address: Recipient address
                - amount: Amount to send (in ADA)
                - metadata: Optional transaction metadata
                - ttl: Optional transaction time-to-live in slots
            
        Returns:
            Dict[str, Any]: Unsigned transaction parameters
            
        Raises:
            TransactionError: If transaction creation fails
            ValidationError: If parameters are invalid
        """
        if not self.is_connected or not self.context:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Extract and validate parameters
            from_address = kwargs.get('from_address')
            to_address = kwargs.get('to_address')
            amount_ada = kwargs.get('amount', 0)  # Amount in ADA
            metadata = kwargs.get('metadata', None)
            ttl = kwargs.get('ttl', None)  # Optional TTL in slots
            
            # Validate addresses
            if not from_address or not self.validate_address(from_address):
                raise ValidationError(f"Invalid from address: {from_address}")
                
            if not to_address or not self.validate_address(to_address):
                raise ValidationError(f"Invalid to address: {to_address}")
                
            # Convert ADA amount to lovelace
            lovelace_amount = int(Decimal(str(amount_ada)) * Decimal(10 ** self.currency['decimals']))
            
            # Parse addresses
            sender_address = Address.from_primitive(from_address)
            recipient_address = Address.from_primitive(to_address)
            
            # Create a Value object for the amount
            amount_value = Value(lovelace_amount)
            
            # Get the protocol parameters
            protocol_params = self.context.get_protocol_parameters()
            
            # Create a transaction builder
            builder = TransactionBuilder(self.context)
            
            # Add output to recipient
            builder.add_output(
                TransactionOutput(recipient_address, amount_value)
            )
            
            # Set TTL if provided
            if ttl is not None:
                builder.ttl = ttl
                
            # Add metadata if provided
            if metadata is not None:
                aux_data = AuxiliaryData(metadata=metadata)
                builder.auxiliary_data = aux_data
                
            # Store transaction info for later use
            tx_info = {
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount_ada,
                'amount_lovelace': lovelace_amount,
                'builder': builder,  # Transaction builder
                'network': self.network,
                'network_id': self.network_id
            }
            
            # If TTL is set, include it
            if ttl is not None:
                tx_info['ttl'] = ttl
                
            # If metadata is set, include it
            if metadata is not None:
                tx_info['metadata'] = metadata
                
            return tx_info
            
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict[str, Any], private_key: str) -> Dict[str, Any]:
        """Sign a Cardano transaction with private key.
        
        Args:
            transaction: Transaction object from create_transaction
            private_key: Private key in bech32 or hex format
            
        Returns:
            Dict[str, Any]: Signed transaction data
            
        Raises:
            TransactionError: If signing fails
            ValidationError: If private key is invalid
        """
        if not self.is_connected or not self.context:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Extract transaction builder
            builder = transaction.get('builder')
            if not builder:
                raise TransactionError("Transaction builder not found in transaction object")
                
            # Parse the private key
            try:
                if private_key.startswith('ed25519'):
                    # Bech32 encoded signing key
                    signing_key = PaymentSigningKey.from_primitive(private_key)
                else:
                    # Hex encoded signing key
                    signing_key = PaymentSigningKey.from_cbor(bytes.fromhex(private_key))
            except Exception as e:
                raise ValidationError(f"Invalid private key format: {str(e)}") from e
                
            # Get the corresponding verification key
            verification_key = PaymentVerificationKey.from_signing_key(signing_key)
            
            # Derive address from public key to verify key ownership
            derived_address = Address(payment_part=verification_key.hash(), network=self.network_id)
            
            # Verify the derived address matches the sender address
            from_address = transaction.get('from_address')
            sender_address = Address.from_primitive(from_address)
            
            # Note: This is a simplified check, full address validation is more complex
            # Especially for staking addresses with delegation components
            if derived_address.payment_part != sender_address.payment_part:
                raise ValidationError(
                    "Private key does not correspond to sender address"
                )
            
            # Add inputs and change output
            # This automatically queries UTXOs and calculates change
            builder.add_input_address(sender_address)
            
            # Build and sign the transaction
            signed_tx = builder.build_and_sign([signing_key], change_address=sender_address)
            
            # Create response with signed transaction details
            signed_tx_data = {
                'transaction': signed_tx,
                'tx_hash': str(signed_tx.id),
                'tx_bytes': bytes(signed_tx).hex(),
                'from_address': transaction.get('from_address'),
                'to_address': transaction.get('to_address'),
                'amount': transaction.get('amount'),
                'amount_lovelace': transaction.get('amount_lovelace'),
                'network': transaction.get('network'),
                'signed': True
            }
            
            # Copy optional fields from original transaction
            for field in ['metadata', 'ttl']:
                if field in transaction:
                    signed_tx_data[field] = transaction[field]
                    
            return signed_tx_data
            
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict[str, Any]) -> str:
        """Broadcast signed transaction to the Cardano network.
        
        Args:
            signed_transaction: Signed transaction data from sign_transaction
            
        Returns:
            str: Transaction hash
            
        Raises:
            TransactionError: If broadcasting fails
            ValidationError: If transaction data is invalid
        """
        if not self.is_connected or not self.context:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Extract the signed transaction
            tx = signed_transaction.get('transaction')
            if not tx:
                raise ValidationError("No transaction object in signed transaction data")
                
            # Submit the transaction to the network
            tx_hash = self.context.submit_tx(tx)
            
            # Log the transaction hash
            logger.info(f"Broadcast transaction to {self.network_name}: {tx_hash}")
            
            # Return the transaction hash
            return str(tx_hash)
            
        except Exception as e:
            error_msg = f"Failed to broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get status of Cardano transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        if not self.is_connected or not self.context:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Validate transaction hash format
            if not tx_hash:
                raise ValidationError("Transaction hash cannot be empty")
                
            # Query transaction status through BlockFrost
            try:
                tx_info = self.context.api.transaction(tx_hash)
                
                # If we got this far without error, transaction was found
                found = True
                
                # Get block information for this transaction
                block_info = self.context.api.transaction_blocks(tx_hash)
                
                # Extract timestamp if available
                timestamp = None
                if block_info and hasattr(block_info, 'time'):
                    timestamp = block_info.time
                    
                # Get current block height for confirmation count
                latest_block_height = self.context.api.block_latest().height
                tx_block_height = block_info.height if block_info else None
                confirmations = 0
                
                # Calculate confirmations if block height is available
                if tx_block_height:
                    confirmations = max(0, latest_block_height - tx_block_height + 1)
                    
                # Get transaction UTXOs
                tx_utxos = self.context.api.transaction_utxos(tx_hash)
                
                # Extract input and output details
                inputs = []
                outputs = []
                total_input_lovelace = 0
                total_output_lovelace = 0
                
                # Process inputs if available
                if hasattr(tx_utxos, 'inputs'):
                    for inp in tx_utxos.inputs:
                        # Add up ADA values
                        for amount in inp.amount:
                            if amount.unit == 'lovelace':
                                total_input_lovelace += int(amount.quantity)
                                
                        inputs.append({
                            'address': inp.address,
                            'amount': [{
                                'unit': amt.unit,
                                'quantity': amt.quantity
                            } for amt in inp.amount]
                        })
                        
                # Process outputs if available
                if hasattr(tx_utxos, 'outputs'):
                    for out in tx_utxos.outputs:
                        # Add up ADA values
                        for amount in out.amount:
                            if amount.unit == 'lovelace':
                                total_output_lovelace += int(amount.quantity)
                                
                        outputs.append({
                            'address': out.address,
                            'amount': [{
                                'unit': amt.unit,
                                'quantity': amt.quantity
                            } for amt in out.amount]
                        })
                        
                # Calculate fee
                fee = total_input_lovelace - total_output_lovelace if total_input_lovelace >= total_output_lovelace else None
                
                # Get metadata if available
                metadata = None
                try:
                    metadata = self.context.api.transaction_metadata(tx_hash)
                except Exception as e:
                    logger.debug(f"Could not get transaction metadata: {str(e)}")
                    
                # Build response
                tx_response = {
                    'hash': tx_hash,
                    'found': found,
                    'status': 'confirmed' if confirmations > 0 else 'pending',
                    'block_height': tx_block_height,
                    'confirmations': confirmations,
                    'timestamp': timestamp,
                    'fee': fee,
                    'inputs': inputs,
                    'outputs': outputs,
                    'total_input_lovelace': total_input_lovelace,
                    'total_output_lovelace': total_output_lovelace,
                    'total_input_ada': Decimal(total_input_lovelace) / Decimal(10 ** self.currency['decimals']),
                    'total_output_ada': Decimal(total_output_lovelace) / Decimal(10 ** self.currency['decimals'])
                }
                
                # Add metadata if available
                if metadata:
                    tx_response['metadata'] = metadata
                    
                # Add explorer URL
                tx_response['explorer_url'] = f"{self.explorer_url}/transaction/{tx_hash}"
                    
                return tx_response
                
            except Exception as e:
                if "not found" in str(e).lower():
                    # Transaction not found or still pending
                    return {
                        'hash': tx_hash,
                        'found': False,
                        'status': 'not_found',
                        'confirmations': 0
                    }
                # Re-raise for other errors
                raise
                
        except ValidationError as ve:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to get transaction status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_network_status(self) -> Dict[str, Any]:
        """Get Cardano network status.
        
        Returns:
            dict: Network status including block height, epoch, slot info, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.context:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Get latest block
            latest_block = self.context.api.block_latest()
            
            # Get current epoch
            latest_epoch = self.context.api.epoch_latest()
            
            # Get protocol parameters
            protocol_params = self.context.get_protocol_parameters()
            
            # Get genesis parameters
            genesis_params = None
            try:
                genesis_params = self.context.api.genesis()
            except Exception as e:
                logger.debug(f"Could not get genesis parameters: {str(e)}")
                
            # Build response
            status = {
                'name': self.network_name,
                'network': self.network,
                'connected': self.is_connected,
                'block_height': latest_block.height if latest_block else None,
                'epoch': latest_epoch.epoch if latest_epoch else None,
                'slot': latest_block.slot if latest_block else None,
                'hash': latest_block.hash if latest_block else None
            }
            
            # Add protocol parameters if available
            if protocol_params:
                status['protocol'] = {
                    'min_fee_a': protocol_params.min_fee_a,
                    'min_fee_b': protocol_params.min_fee_b,
                    'max_tx_size': protocol_params.max_tx_size,
                    'pool_deposit': protocol_params.pool_deposit,
                    'key_deposit': protocol_params.key_deposit
                }
                
            # Add genesis parameters if available
            if genesis_params:
                status['genesis'] = {
                    'active_slots_coefficient': genesis_params.active_slots_coefficient if hasattr(genesis_params, 'active_slots_coefficient') else None,
                    'network_id': genesis_params.network_id if hasattr(genesis_params, 'network_id') else None,
                    'network_magic': genesis_params.network_magic if hasattr(genesis_params, 'network_magic') else None,
                    'epoch_length': genesis_params.epoch_length if hasattr(genesis_params, 'epoch_length') else None,
                    'slot_length': genesis_params.slot_length if hasattr(genesis_params, 'slot_length') else None,
                    'max_lovelace_supply': genesis_params.max_lovelace_supply if hasattr(genesis_params, 'max_lovelace_supply') else None
                }
                
            # Add network addresses
            status['explorer_url'] = self.explorer_url
            status['blockfrost_url'] = self.blockfrost_url
                
            return status
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to get network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, from_address: str, to_address: str, amount: Decimal = None, metadata: Any = None) -> Dict[str, Any]:
        """Estimate fee for Cardano transaction.
        
        Args:
            from_address: Sender address
            to_address: Recipient address
            amount: Optional amount to send
            metadata: Optional transaction metadata
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        if not self.is_connected or not self.context:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Validate addresses
            if not self.validate_address(from_address):
                raise ValidationError(f"Invalid sender address: {from_address}")
                
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            # Set default amount if none provided
            if amount is None:
                amount = Decimal('1.0')  # Default 1 ADA for estimation
                
            # Convert ADA to lovelace
            lovelace_amount = int(amount * Decimal(10 ** self.currency['decimals']))
            
            # Get protocol parameters
            protocol_params = self.context.get_protocol_parameters()
            
            # Parse addresses
            sender_address = Address.from_primitive(from_address)
            recipient_address = Address.from_primitive(to_address)
            
            # Create a Value object for the amount
            amount_value = Value(lovelace_amount)
            
            # Create a transaction builder
            builder = TransactionBuilder(self.context)
            
            # Add output to recipient
            builder.add_output(
                TransactionOutput(recipient_address, amount_value)
            )
            
            # Add metadata if provided
            if metadata is not None:
                aux_data = AuxiliaryData(metadata=metadata)
                builder.auxiliary_data = aux_data
                
            # Add inputs and change output
            # This automatically queries UTXOs
            builder.add_input_address(sender_address)
            
            # Build transaction draft (unsigned) to calculate fee
            tx_draft = builder.build_tx(change_address=sender_address)
            
            # Calculate fee for transaction
            fee = tx_draft.transaction_body.fee
            
            # Calculate sizes
            tx_size = len(bytes(tx_draft))
            
            # Create response
            fee_data = {
                'fee_lovelace': fee,
                'fee_ada': Decimal(fee) / Decimal(10 ** self.currency['decimals']),
                'tx_size_bytes': tx_size,
                'min_fee_a': protocol_params.min_fee_a,  # Per byte fee
                'min_fee_b': protocol_params.min_fee_b,  # Constant fee
                'max_tx_size': protocol_params.max_tx_size,
                'estimates': {
                    'low': {
                        'fee_lovelace': fee,
                        'fee_ada': Decimal(fee) / Decimal(10 ** self.currency['decimals'])
                    },
                    'medium': {
                        'fee_lovelace': int(fee * 1.2),  # 20% more for medium priority
                        'fee_ada': Decimal(int(fee * 1.2)) / Decimal(10 ** self.currency['decimals'])
                    },
                    'high': {
                        'fee_lovelace': int(fee * 1.5),  # 50% more for high priority
                        'fee_ada': Decimal(int(fee * 1.5)) / Decimal(10 ** self.currency['decimals'])
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
        """Disconnect from Cardano network.
        
        Returns:
            bool: True if disconnected successfully
        """
        self.is_connected = False
        self.context = None
        logger.info(f"Disconnected from {self.network_name}")
        return True
