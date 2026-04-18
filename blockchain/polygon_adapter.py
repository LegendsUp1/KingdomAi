#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Kingdom AI - Polygon Blockchain Adapter

This module provides a native, no-fallback implementation for Polygon blockchain integration.
"""

import logging
import json
import time
from typing import Dict, Any, Optional, List, Union, cast
from decimal import Decimal
from web3 import Web3
from web3.exceptions import TransactionNotFound, BadFunctionCallOutput, InvalidAddress
# Use native middleware implementation - no fallbacks allowed
from kingdomweb3_v2 import rpc_manager, get_network_config
from web3.types import TxParams, Wei, ChecksumAddress

from blockchain.base_adapter import BlockchainAdapter, ConnectionError as BlockchainConnectionError, TransactionError, ValidationError, strict_blockchain_operation

# Set up logger
logger = logging.getLogger(__name__)

class PolygonAdapter(BlockchainAdapter[TxParams]):
    """Native Polygon blockchain adapter with no fallbacks."""
    
    def __init__(self, network_name: str = "mainnet", chain_id: Optional[int] = 137):
        """Initialize Polygon adapter.
        
        Args:
            network_name: Name of the Polygon network (mainnet, mumbai)
            chain_id: Chain ID for the network (137 for mainnet, 80001 for mumbai)
        """
        super().__init__(network_name, chain_id)
        self.web3 = None
        self.endpoint_uri = None
        self.gas_price_strategy = None
        self.config = {}
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the adapter with connection details.
        
        Args:
            config: Configuration dictionary with endpoint_uri and other settings
        """
        self.config = config
        self.endpoint_uri = config.get('endpoint_uri')
        
        if not self.endpoint_uri:
            raise BlockchainConnectionError("Polygon endpoint URI not provided in configuration")

    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Polygon network.
        
        Returns:
            bool: True if connected successfully, False otherwise
            
        Raises:
            ConnectionError: If connection fails (no fallbacks allowed)
        """
        try:
            # Connect to Polygon node
            self.web3 = Web3(Web3.HTTPProvider(self.endpoint_uri))
            
            # Add POA middleware for Polygon
            self.web3.middleware_onion.inject(native_geth_poa_middleware, layer=0)
            
            # Test connection
            if not self.web3.is_connected():
                raise BlockchainConnectionError(f"Failed to connect to Polygon node at {self.endpoint_uri}")
                
            # Get network status
            self.last_block = self.web3.eth.block_number
            self.is_connected = True
            
            logger.info(f"Connected to Polygon {self.network_name}, chain_id: {self.chain_id}, " 
                       f"latest block: {self.last_block}")
            return True
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to Polygon {self.network_name}: {str(e)}"
            logger.critical(error_msg)
            # No fallbacks - system must halt if connection fails
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_balance(self, address: str, token_address: Optional[str] = None) -> float:
        """Get balance for Polygon address.
        
        Args:
            address: Polygon address
            token_address: Optional ERC20 token address
            
        Returns:
            float: Balance in MATIC or token units
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Polygon network")
            
        try:
            # Validate address format
            if not self.validate_address(address):
                raise ValidationError(f"Invalid Polygon address: {address}")
                
            # Convert to checksum address
            checksum_address = Web3.to_checksum_address(address)
            
            # Get native MATIC balance
            if token_address is None:
                balance_wei = self.web3.eth.get_balance(checksum_address)
                balance = self.web3.from_wei(balance_wei, 'ether')
                return float(balance)
            
            # Get ERC20 token balance
            else:
                if not self.validate_address(token_address):
                    raise ValidationError(f"Invalid token address: {token_address}")
                    
                # Create token contract interface
                checksum_token = Web3.to_checksum_address(token_address)
                
                # ERC20 ABI - minimal for balanceOf
                erc20_abi = json.dumps([{
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function"
                }, {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                }])
                
                token_contract = self.web3.eth.contract(address=checksum_token, abi=erc20_abi)
                
                # Get token decimals
                try:
                    decimals = token_contract.functions.decimals().call()
                except Exception as e:
                    logger.warning(f"Failed to get decimals for token {token_address}: {str(e)}")
                    decimals = 18  # Default to 18 decimals
                    
                # Get token balance
                balance_wei = token_contract.functions.balanceOf(checksum_address).call()
                balance = balance_wei / (10 ** decimals)
                
                return float(balance)
                
        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            raise
            
        except Exception as e:
            error_msg = f"Failed to get balance for {address}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, **kwargs) -> TxParams:
        """Create a Polygon transaction.
        
        Args:
            **kwargs: Transaction parameters including:
                - from_address: Sender address
                - to_address: Recipient address
                - value: Amount in MATIC
                - data: Optional transaction data
                - gas: Optional gas limit
                - gas_price: Optional gas price in wei
                - max_fee_per_gas: Optional max fee per gas (EIP-1559)
                - max_priority_fee_per_gas: Optional max priority fee per gas (EIP-1559)
                - nonce: Optional transaction nonce
            
        Returns:
            TxParams: Polygon transaction parameters
            
        Raises:
            TransactionError: If transaction creation fails
            ValidationError: If addresses are invalid
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Polygon network")
            
        try:
            # Extract and validate parameters
            from_address = kwargs.get('from_address')
            to_address = kwargs.get('to_address')
            value = kwargs.get('value', 0)  # In MATIC
            data = kwargs.get('data', '')
            gas_limit = kwargs.get('gas')
            gas_price = kwargs.get('gas_price')
            max_fee_per_gas = kwargs.get('max_fee_per_gas')
            max_priority_fee_per_gas = kwargs.get('max_priority_fee_per_gas')
            nonce = kwargs.get('nonce')
            
            # Validate addresses
            if not from_address or not self.validate_address(from_address):
                raise ValidationError(f"Invalid from address: {from_address}")
                
            if to_address and not self.validate_address(to_address):
                raise ValidationError(f"Invalid to address: {to_address}")
            
            # Convert addresses to checksum format
            checksum_from = Web3.to_checksum_address(from_address)
            checksum_to = Web3.to_checksum_address(to_address) if to_address else None
            
            # Convert MATIC value to wei
            value_wei = self.web3.to_wei(value, 'ether') if value else 0
            
            # Get transaction nonce if not provided
            if nonce is None:
                nonce = self.web3.eth.get_transaction_count(checksum_from)
            
            # Initialize transaction parameters
            tx_params: TxParams = {
                'from': checksum_from,
                'nonce': nonce,
                'value': value_wei
            }
            
            # Add destination address if provided
            if checksum_to:
                tx_params['to'] = checksum_to
                
            # Add data if provided
            if data:
                tx_params['data'] = data
                
            # Handle gas limit
            if gas_limit is not None:
                tx_params['gas'] = gas_limit
            
            # Handle EIP-1559 vs legacy gas pricing
            if max_fee_per_gas is not None and max_priority_fee_per_gas is not None:
                # EIP-1559 transaction
                tx_params['maxFeePerGas'] = max_fee_per_gas
                tx_params['maxPriorityFeePerGas'] = max_priority_fee_per_gas
                tx_params['type'] = '0x2'  # EIP-1559 transaction type
            elif gas_price is not None:
                # Legacy transaction
                tx_params['gasPrice'] = gas_price
            else:
                # Default to getting current gas price
                tx_params['gasPrice'] = self.web3.eth.gas_price
                
            # Estimate gas if not provided
            if 'gas' not in tx_params:
                try:
                    # Make a copy without the 'from' field for estimation
                    estimate_params = dict(tx_params)
                    if 'from' in estimate_params:
                        del estimate_params['from']
                        
                    gas_estimate = self.web3.eth.estimate_gas({
                        **estimate_params,
                        'from': checksum_from
                    })
                    # Add 20% buffer for safety
                    tx_params['gas'] = int(gas_estimate * 1.2)
                except Exception as e:
                    logger.warning(f"Gas estimation failed: {str(e)}, using default gas limit")
                    tx_params['gas'] = 21000  # Default gas limit for simple transfers
            
            return tx_params
            
        except (ValidationError, BlockchainConnectionError):
            # Re-raise these specific exceptions
            raise
            
        except Exception as e:
            error_msg = f"Failed to create Polygon transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: TxParams, private_key: str) -> Dict[str, Any]:
        """Sign a Polygon transaction with private key.
        
        Args:
            transaction: The transaction parameters to sign
            private_key: Polygon private key (hex string with or without 0x prefix)
            
        Returns:
            Dict[str, Any]: Signed transaction data
            
        Raises:
            TransactionError: If transaction signing fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Polygon network")
            
        try:
            # Format private key
            if not private_key.startswith('0x'):
                private_key = f'0x{private_key}'
                
            # Sign transaction
            signed_tx = self.web3.eth.account.sign_transaction(transaction, private_key)
            
            # Return signed transaction data
            return {
                'hash': signed_tx.hash.hex(),
                'raw_transaction': signed_tx.rawTransaction.hex(),
                'r': signed_tx.r,
                's': signed_tx.s,
                'v': signed_tx.v
            }
            
        except Exception as e:
            error_msg = f"Failed to sign Polygon transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict[str, Any]) -> str:
        """Broadcast signed transaction to Polygon network.
        
        Args:
            signed_transaction: Signed transaction data with raw_transaction hex
            
        Returns:
            str: Transaction hash
            
        Raises:
            TransactionError: If broadcasting fails
            ConnectionError: If network connection is lost
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Polygon network")
            
        try:
            # Extract raw transaction
            raw_tx = signed_transaction.get('raw_transaction')
            if not raw_tx:
                raise TransactionError("No raw transaction data provided")
                
            # Add 0x prefix if missing
            if not raw_tx.startswith('0x'):
                raw_tx = f'0x{raw_tx}'
                
            # Send raw transaction
            tx_hash = self.web3.eth.send_raw_transaction(raw_tx)
            
            # Return hash as string
            return tx_hash.hex()
            
        except Exception as e:
            error_msg = f"Failed to broadcast Polygon transaction: {str(e)}"
            logger.error(error_msg)
            if "already known" in str(e).lower():
                # Transaction already submitted
                if 'hash' in signed_transaction:
                    return signed_transaction['hash']
            raise TransactionError(error_msg) from e
    
    def validate_address(self, address: str) -> bool:
        """Validate Polygon address format.
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid, False otherwise
        """
        if not address:
            return False
            
        try:
            # Attempt to convert to checksum address
            Web3.to_checksum_address(address)
            return True
        except Exception:
            return False
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get status of Polygon transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Polygon network")
            
        try:
            # Validate transaction hash format
            if not tx_hash or not tx_hash.startswith('0x') or len(tx_hash) != 66:
                raise ValidationError(f"Invalid transaction hash: {tx_hash}")
                
            # Get transaction data
            tx_data = self.web3.eth.get_transaction(tx_hash)
            if not tx_data:
                return {
                    'hash': tx_hash,
                    'found': False,
                    'status': 'unknown',
                    'block_number': None,
                    'confirmations': 0
                }
                
            # Get transaction receipt (may be None if pending)
            try:
                tx_receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            except TransactionNotFound:
                tx_receipt = None
                
            # Get current block for confirmation count
            current_block = self.web3.eth.block_number
            
            # Calculate confirmations
            block_number = tx_data.get('blockNumber')
            confirmations = 0
            if block_number is not None and block_number > 0:
                confirmations = current_block - block_number + 1
                
            # Determine status
            if tx_receipt is None:
                status = 'pending'  # Still pending
            elif tx_receipt.get('status') == 1:
                status = 'confirmed'  # Success
            else:
                status = 'failed'  # Failed
                
            # Format response
            result = {
                'hash': tx_hash,
                'found': True,
                'status': status,
                'block_number': block_number,
                'confirmations': confirmations,
                'from': tx_data.get('from'),
                'to': tx_data.get('to'),
                'value': self.web3.from_wei(tx_data.get('value', 0), 'ether'),
                'gas_price': self.web3.from_wei(tx_data.get('gasPrice', 0), 'gwei') if tx_data.get('gasPrice') else None,
                'gas': tx_data.get('gas')
            }
            
            # Add receipt data if available
            if tx_receipt:
                result.update({
                    'gas_used': tx_receipt.get('gasUsed'),
                    'effective_gas_price': self.web3.from_wei(tx_receipt.get('effectiveGasPrice', 0), 'gwei') 
                        if tx_receipt.get('effectiveGasPrice') else None,
                })
                
                # Calculate transaction fee if possible
                if tx_receipt.get('gasUsed') and tx_receipt.get('effectiveGasPrice'):
                    fee_wei = tx_receipt.get('gasUsed') * tx_receipt.get('effectiveGasPrice')
                    result['fee'] = self.web3.from_wei(fee_wei, 'ether')
                    
            return result
                
        except TransactionNotFound:
            return {
                'hash': tx_hash,
                'found': False,
                'status': 'unknown',
                'block_number': None,
                'confirmations': 0
            }
            
        except ValidationError:
            raise
            
        except Exception as e:
            error_msg = f"Failed to get Polygon transaction status for {tx_hash}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
    
    @strict_blockchain_operation
    def get_network_status(self) -> Dict[str, Any]:
        """Get Polygon network status.
        
        Returns:
            dict: Network status including block height, sync state, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Polygon network")
            
        try:
            # Get current block
            block_number = self.web3.eth.block_number
            self.last_block = block_number
            
            # Get latest block details
            latest_block = self.web3.eth.get_block('latest')
            
            # Get network sync status
            sync_status = self.web3.eth.syncing
            is_syncing = sync_status is not False
            
            # Get gas price
            gas_price_wei = self.web3.eth.gas_price
            gas_price_gwei = self.web3.from_wei(gas_price_wei, 'gwei')
            
            # Check node connectivity
            is_connected = self.web3.is_connected()
            self.is_connected = is_connected
            
            # Get peer count
            try:
                peer_count = self.web3.net.peer_count
            except Exception:
                peer_count = None
                
            # Get chain ID
            try:
                chain_id = self.web3.eth.chain_id
                if self.chain_id is None:
                    self.chain_id = chain_id
            except Exception:
                chain_id = self.chain_id
                
            # Build result
            result = {
                'name': f"Polygon {self.network_name}",
                'chain_id': chain_id,
                'connected': is_connected,
                'syncing': is_syncing,
                'block_height': block_number,
                'latest_block_hash': latest_block.get('hash').hex() if latest_block.get('hash') else None,
                'latest_block_time': latest_block.get('timestamp'),
                'gas_price_wei': gas_price_wei,
                'gas_price_gwei': gas_price_gwei,
                'peer_count': peer_count
            }
            
            # Add sync progress if syncing
            if isinstance(sync_status, dict):
                result.update({
                    'sync_starting_block': sync_status.get('startingBlock'),
                    'sync_current_block': sync_status.get('currentBlock'),
                    'sync_highest_block': sync_status.get('highestBlock'),
                    'sync_progress': (sync_status.get('currentBlock', 0) - sync_status.get('startingBlock', 0)) /
                                     max(1, (sync_status.get('highestBlock', 1) - sync_status.get('startingBlock', 0)))
                })
                
            # Add EIP-1559 base fee if available
            if latest_block and 'baseFeePerGas' in latest_block:
                base_fee_wei = latest_block['baseFeePerGas']
                result.update({
                    'eip1559_enabled': True,
                    'base_fee_wei': base_fee_wei,
                    'base_fee_gwei': self.web3.from_wei(base_fee_wei, 'gwei')
                })
            else:
                result['eip1559_enabled'] = False
                
            return result
                
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to get Polygon network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, transaction: TxParams) -> Dict[str, Any]:
        """Estimate fee for Polygon transaction.
        
        Args:
            transaction: Transaction to estimate fee for
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Polygon network")
            
        try:
            # Get current gas price
            gas_price = transaction.get('gasPrice')
            if gas_price is None:
                gas_price = self.web3.eth.gas_price
                
            # Get gas limit from transaction or estimate
            if 'gas' in transaction:
                gas_limit = transaction['gas']
            else:
                # Create a copy of transaction for estimation
                tx_for_estimate = dict(transaction)
                if 'from' not in tx_for_estimate and 'from' in transaction:
                    tx_for_estimate['from'] = transaction['from']
                gas_limit = self.web3.eth.estimate_gas(tx_for_estimate)
                # Add 20% buffer
                gas_limit = int(gas_limit * 1.2)
                
            # Calculate fee in Wei and MATIC
            fee_wei = gas_price * gas_limit
            fee_matic = self.web3.from_wei(fee_wei, 'ether')
            
            # Get fee estimates for different priorities
            try:
                # Get priority fee suggestions for next block
                base_fee = None
                priority_fees = None
                max_fee = None
                
                # Try to get next block base fee from current block
                try:
                    latest_block = self.web3.eth.get_block('latest')
                    if latest_block and 'baseFeePerGas' in latest_block:
                        # EIP-1559 is active
                        base_fee = latest_block['baseFeePerGas']
                        
                        # Calculate potential next block base fee (can increase by up to 12.5%)
                        next_base_fee = int(base_fee * 1.125)
                        
                        # Get max priority fee suggestions
                        # Polygon typically requires higher priority fees than Ethereum
                        priority_fees = {
                            'slow': self.web3.to_wei(30, 'gwei'),  # Conservative estimate
                            'normal': self.web3.to_wei(50, 'gwei'),
                            'fast': self.web3.to_wei(100, 'gwei')
                        }
                        
                        # Calculate max fees (base fee + priority fee)
                        max_fee = {
                            'slow': next_base_fee + priority_fees['slow'],
                            'normal': next_base_fee + priority_fees['normal'],
                            'fast': next_base_fee + priority_fees['fast']
                        }
                except Exception as e:
                    logger.warning(f"Failed to get base fee: {str(e)}")
            except Exception as e:
                logger.warning(f"Failed to get fee estimates: {str(e)}")
                
            # Build response
            result = {
                'gas_price_wei': gas_price,
                'gas_price_gwei': self.web3.from_wei(gas_price, 'gwei'),
                'gas_limit': gas_limit,
                'fee_wei': fee_wei,
                'fee_matic': fee_matic
            }
            
            # Add EIP-1559 data if available
            if base_fee is not None:
                result.update({
                    'eip1559_enabled': True,
                    'base_fee_wei': base_fee,
                    'base_fee_gwei': self.web3.from_wei(base_fee, 'gwei'),
                    'priority_fees_gwei': {
                        k: self.web3.from_wei(v, 'gwei') for k, v in priority_fees.items()
                    } if priority_fees else None,
                    'max_fee_gwei': {
                        k: self.web3.from_wei(v, 'gwei') for k, v in max_fee.items()
                    } if max_fee else None
                })
                
            return result
            
        except Exception as e:
            error_msg = f"Failed to estimate fee for Polygon transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    def disconnect(self) -> bool:
        """Disconnect from Polygon network.
        
        Returns:
            bool: True if disconnected successfully
        """
        self.is_connected = False
        self.web3 = None
        logger.info(f"Disconnected from Polygon {self.network_name}")
        return True
