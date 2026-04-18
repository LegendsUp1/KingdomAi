#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Kingdom AI - Ethereum Blockchain Adapter

This module provides a native, no-fallback implementation for Ethereum blockchain integration.
"""

import logging
import json
import time
import os
from typing import Dict, Any, Optional, List, Union, cast
from decimal import Decimal
from web3 import Web3
from web3.exceptions import TransactionNotFound, BadFunctionCallOutput, InvalidAddress
# Use native middleware implementation - no fallbacks allowed
# Using kingdomweb3_v2 for blockchain connectivity
from kingdomweb3_v2 import rpc_manager, get_network_config
from web3.types import TxParams, Wei, ChecksumAddress

from blockchain.base_adapter import BlockchainAdapter, ConnectionError as BlockchainConnectionError, TransactionError, ValidationError, strict_blockchain_operation

# Set up logger
logger = logging.getLogger(__name__)

class EthereumAdapter(BlockchainAdapter[TxParams]):
    """Native Ethereum blockchain adapter with no fallbacks."""
    
    def __init__(self, network_name: str, chain_id: Optional[int] = None):
        """Initialize Ethereum adapter.
        
        Args:
            network_name: Name of the Ethereum network (mainnet, goerli, etc.)
            chain_id: Chain ID for the network
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
            raise ConnectionError("Ethereum endpoint URI not provided in configuration")

    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Ethereum network.
        
        Returns:
            bool: True if connected successfully, False otherwise
            
        Raises:
            ConnectionError: If connection fails (no fallbacks allowed)
        """
        try:
            # Connect to Ethereum node
            self.web3 = Web3(Web3.HTTPProvider(self.endpoint_uri))
            
            # Add POA middleware for networks like Polygon, BSC, etc.
            self.web3.middleware_onion.inject(native_geth_poa_middleware, layer=0)
            
            # Test connection
            if not self.web3.is_connected():
                raise ConnectionError(f"Failed to connect to Ethereum node at {self.endpoint_uri}")
                
            # Get network status
            self.last_block = self.web3.eth.block_number
            self.is_connected = True
            
            logger.info(f"Connected to Ethereum {self.network_name}, chain_id: {self.chain_id}, " 
                       f"latest block: {self.last_block}")
            return True
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to Ethereum {self.network_name}: {str(e)}"
            logger.critical(error_msg)
            # No fallbacks - system must halt if connection fails
            raise BlockchainConnectionError(error_msg) from e

    @strict_blockchain_operation
    def get_balance(self, address: str, token_address: Optional[str] = None) -> float:
        """Get balance for Ethereum address.
        
        Args:
            address: Ethereum address
            token_address: Optional ERC20 token address
            
        Returns:
            float: Balance in ETH or token units
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected or not self.web3:
            raise ConnectionError("Not connected to Ethereum network")
            
        try:
            # Validate address format
            if not self.validate_address(address):
                raise ValidationError(f"Invalid Ethereum address: {address}")
                
            if token_address:
                # Get ERC20 token balance
                if not self.validate_address(token_address):
                    raise ValidationError(f"Invalid token address: {token_address}")
                    
                # ERC20 contract ABI for balanceOf method
                abi = [
                    {
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function"
                    }
                ]
                
                # Create contract instance
                token_contract = self.web3.eth.contract(address=self.web3.to_checksum_address(token_address), abi=abi)
                
                # Get token balance
                raw_balance = token_contract.functions.balanceOf(
                    self.web3.to_checksum_address(address)
                ).call()
                
                # Get token decimals
                try:
                    decimals_abi = [
                        {
                            "constant": True,
                            "inputs": [],
                            "name": "decimals",
                            "outputs": [{"name": "", "type": "uint8"}],
                            "type": "function"
                        }
                    ]
                    decimals = token_contract.functions.decimals().call()
                except Exception:
                    # Default to 18 decimals if decimals() method is not available
                    decimals = 18
                    
                # Convert to token units
                balance = float(Decimal(raw_balance) / Decimal(10 ** decimals))
                
            else:
                # Get ETH balance
                raw_balance = self.web3.eth.get_balance(self.web3.to_checksum_address(address))
                balance = float(self.web3.from_wei(raw_balance, 'ether'))
                
            return balance
            
        except InvalidAddress as e:
            raise ValidationError(f"Invalid Ethereum address: {str(e)}")
        except ConnectionError as e:
            # Re-raise connection errors
            raise e
        except Exception as e:
            error_msg = f"Failed to get balance for {address}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, **kwargs) -> TxParams:
        """Create an Ethereum transaction.
        
        Args:
            **kwargs: Transaction parameters including:
                - from_address: Sender address
                - to_address: Recipient address
                - value: Amount in ETH
                - data: Optional transaction data
                - gas: Optional gas limit
                - gas_price: Optional gas price in Wei
                - nonce: Optional nonce
            
        Returns:
            TxParams: Ethereum transaction parameters
            
        Raises:
            TransactionError: If transaction creation fails
            ValidationError: If addresses are invalid
        """
        if not self.is_connected or not self.web3:
            raise ConnectionError("Not connected to Ethereum network")
            
        try:
            from_address = kwargs.get('from_address')
            to_address = kwargs.get('to_address')
            value = kwargs.get('value', 0)
            data = kwargs.get('data', '')
            
            # Validate addresses
            if not from_address or not self.validate_address(from_address):
                raise ValidationError(f"Invalid from_address: {from_address}")
            
            if to_address and not self.validate_address(to_address):
                raise ValidationError(f"Invalid to_address: {to_address}")
                
            # Convert to checksum addresses
            from_checksum = self.web3.to_checksum_address(from_address)
            to_checksum = self.web3.to_checksum_address(to_address) if to_address else None
            
            # Convert ETH value to Wei
            value_wei = self.web3.to_wei(value, 'ether') if value else 0
            
            # Get nonce if not provided
            nonce = kwargs.get('nonce')
            if nonce is None:
                nonce = self.web3.eth.get_transaction_count(from_checksum)
                
            # Set gas price and limit if not provided
            gas_price = kwargs.get('gas_price')
            if gas_price is None:
                gas_price = self.web3.eth.gas_price
                
            gas_limit = kwargs.get('gas')
            if gas_limit is None:
                # Estimate gas if we have a to_address
                if to_checksum:
                    tx_params = {
                        'from': from_checksum,
                        'to': to_checksum,
                        'value': value_wei,
                        'data': self.web3.to_hex(data) if data else '0x'
                    }
                    try:
                        gas_limit = self.web3.eth.estimate_gas(tx_params)
                        # Add 20% buffer to gas estimate
                        gas_limit = int(gas_limit * 1.2)
                    except Exception as e:
                        logger.warning(f"Gas estimation failed, using default: {str(e)}")
                        gas_limit = 21000  # Default gas limit for basic transactions
                else:
                    # Default gas limit for contract deployments
                    gas_limit = 2000000
            
            # Create transaction parameters
            tx_params: TxParams = {
                'from': from_checksum,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': gas_limit,
                'value': value_wei
            }
            
            # Add to_address if provided (otherwise it's a contract creation)
            if to_checksum:
                tx_params['to'] = to_checksum
                
            # Add data if provided
            if data:
                tx_params['data'] = self.web3.to_hex(data) if isinstance(data, bytes) else data
                
            # Add chain ID if available
            if self.chain_id:
                tx_params['chainId'] = self.chain_id
                
            return tx_params
            
        except ValidationError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            error_msg = f"Failed to create Ethereum transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg)
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: TxParams, private_key: str) -> Dict[str, Any]:
        """Sign an Ethereum transaction with private key.
        
        Args:
            transaction: The transaction parameters to sign
            private_key: Ethereum private key (hex string with or without 0x prefix)
            
        Returns:
            Dict[str, Any]: Signed transaction data
            
        Raises:
            TransactionError: If transaction signing fails
        """
        if not self.is_connected or not self.web3:
            raise ConnectionError("Not connected to Ethereum network")
            
        try:
            # Ensure private key has 0x prefix
            if not private_key.startswith('0x'):
                private_key = f'0x{private_key}'
                
            # Sign the transaction
            signed_tx = self.web3.eth.account.sign_transaction(transaction, private_key)
            
            return {
                'raw_transaction': signed_tx.rawTransaction.hex(),
                'hash': signed_tx.hash.hex(),
                'r': signed_tx.r,
                's': signed_tx.s,
                'v': signed_tx.v
            }
            
        except Exception as e:
            error_msg = f"Failed to sign Ethereum transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict[str, Any]) -> str:
        """Broadcast signed transaction to Ethereum network.
        
        Args:
            signed_transaction: Signed transaction data with raw_transaction hex
            
        Returns:
            str: Transaction hash
            
        Raises:
            TransactionError: If broadcasting fails
            ConnectionError: If network connection is lost
        """
        if not self.is_connected or not self.web3:
            raise ConnectionError("Not connected to Ethereum network")
            
        try:
            # Get raw transaction bytes from hex
            raw_tx_hex = signed_transaction.get('raw_transaction')
            if not raw_tx_hex:
                raise TransactionError("No raw_transaction found in signed transaction data")
                
            raw_tx_bytes = bytes.fromhex(raw_tx_hex.replace('0x', ''))
            
            # Send raw transaction
            tx_hash = self.web3.eth.send_raw_transaction(raw_tx_bytes)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"Transaction broadcast successful: {tx_hash_hex}")
            return tx_hash_hex
            
        except Exception as e:
            error_msg = f"Failed to broadcast Ethereum transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def validate_address(self, address: str) -> bool:
        """Validate Ethereum address format.
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid, False otherwise
        """
        try:
            # Basic length and format check
            if not address or not isinstance(address, str):
                return False
                
            # Try to convert to checksum address
            self.web3.to_checksum_address(address)
            return True
            
        except Exception:
            return False
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get status of Ethereum transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        if not self.is_connected or not self.web3:
            raise ConnectionError("Not connected to Ethereum network")
            
        try:
            # Validate transaction hash format
            if not tx_hash or not isinstance(tx_hash, str) or not tx_hash.startswith('0x'):
                raise ValidationError(f"Invalid transaction hash format: {tx_hash}")
                
            # Get transaction receipt
            tx_receipt = None
            try:
                tx_receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            except TransactionNotFound:
                # Transaction not yet mined
                pass
                
            # Get transaction data
            try:
                tx_data = self.web3.eth.get_transaction(tx_hash)
            except TransactionNotFound:
                # Transaction not found
                return {
                    'hash': tx_hash,
                    'found': False,
                    'status': 'not_found',
                    'confirmed': False,
                    'block_number': None,
                    'block_hash': None
                }
                
            # Determine status
            if tx_receipt is None:
                status = 'pending'
                confirmed = False
            else:
                # Check if transaction succeeded (status 1) or failed (status 0)
                if tx_receipt.get('status') == 1:
                    status = 'success'
                else:
                    status = 'failed'
                    
                # Get current block for confirmations
                current_block = self.web3.eth.block_number
                confirmations = current_block - tx_receipt.get('blockNumber', 0) if tx_receipt.get('blockNumber') else 0
                confirmed = confirmations >= 12  # 12 confirmations is typically considered safe
                
            # Build response
            result = {
                'hash': tx_hash,
                'found': True,
                'status': status,
                'confirmed': confirmed,
                'from': tx_data.get('from'),
                'to': tx_data.get('to'),
                'value': self.web3.from_wei(tx_data.get('value', 0), 'ether'),
                'gas_price': self.web3.from_wei(tx_data.get('gasPrice', 0), 'gwei'),
                'gas': tx_data.get('gas')
            }
            
            # Add receipt data if available
            if tx_receipt:
                result.update({
                    'block_number': tx_receipt.get('blockNumber'),
                    'block_hash': tx_receipt.get('blockHash', '').hex() if tx_receipt.get('blockHash') else None,
                    'gas_used': tx_receipt.get('gasUsed'),
                    'effective_gas_price': self.web3.from_wei(tx_receipt.get('effectiveGasPrice', 0), 'gwei') if tx_receipt.get('effectiveGasPrice') else None,
                    'confirmations': confirmations if 'confirmations' in locals() else 0
                })
                
            return result
            
        except ValidationError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            error_msg = f"Failed to get transaction status for {tx_hash}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_network_status(self) -> Dict[str, Any]:
        """Get Ethereum network status.
        
        Returns:
            dict: Network status including block height, sync state, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.web3:
            raise ConnectionError("Not connected to Ethereum network")
            
        try:
            # Get basic network information
            block_number = self.web3.eth.block_number
            gas_price = self.web3.eth.gas_price
            syncing = self.web3.eth.syncing
            
            # Get latest block details
            latest_block = self.web3.eth.get_block('latest')
            
            # Update last block
            self.last_block = block_number
            
            # Calculate network TPS (transactions per second)
            tps = None
            if latest_block and 'transactions' in latest_block:
                # Get block 100 blocks ago for TPS calculation if available
                try:
                    old_block_number = max(0, block_number - 100)
                    old_block = self.web3.eth.get_block(old_block_number)
                    if old_block and 'timestamp' in old_block and 'timestamp' in latest_block:
                        time_diff = latest_block['timestamp'] - old_block['timestamp']
                        tx_count = 0
                        for i in range(old_block_number, block_number + 1):
                            block = self.web3.eth.get_block(i, False)
                            if block and 'transactions' in block:
                                tx_count += len(block['transactions'])
                        if time_diff > 0:
                            tps = tx_count / time_diff
                except Exception as e:
                    logger.warning(f"Failed to calculate TPS: {str(e)}")
                    
            # Build response
            result = {
                'network_name': self.network_name,
                'chain_id': self.chain_id,
                'block_height': block_number,
                'gas_price': self.web3.from_wei(gas_price, 'gwei'),
                'syncing': syncing is not False,  # syncing can be False or an object with sync info
                'connected': True,
                'latest_block_timestamp': latest_block.get('timestamp') if latest_block else None,
                'latest_block_hash': latest_block.get('hash', '').hex() if latest_block and latest_block.get('hash') else None,
                'transactions_per_second': tps
            }
            
            # Add sync data if available
            if isinstance(syncing, dict):
                result.update({
                    'sync_current_block': syncing.get('currentBlock'),
                    'sync_highest_block': syncing.get('highestBlock'),
                    'sync_starting_block': syncing.get('startingBlock'),
                    'sync_progress': (syncing.get('currentBlock', 0) - syncing.get('startingBlock', 0)) / 
                                    (syncing.get('highestBlock', 0) - syncing.get('startingBlock', 0) + 0.0001) * 100
                                    if syncing.get('highestBlock', 0) > syncing.get('startingBlock', 0) else 0
                })
                
            # Update last status
            self.last_status = result
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to get Ethereum network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, transaction: TxParams) -> Dict[str, Any]:
        """Estimate fee for Ethereum transaction.
        
        Args:
            transaction: Transaction to estimate fee for
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        if not self.is_connected or not self.web3:
            raise ConnectionError("Not connected to Ethereum network")
            
        try:
            # Get current gas price if not in transaction
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
                
            # Calculate fee in Wei and ETH
            fee_wei = gas_price * gas_limit
            fee_eth = self.web3.from_wei(fee_wei, 'ether')
            
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
                        priority_fees = {
                            'slow': self.web3.to_wei(1, 'gwei'),  # Conservative estimate
                            'normal': self.web3.to_wei(2, 'gwei'),
                            'fast': self.web3.to_wei(3, 'gwei')
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
                'fee_eth': fee_eth
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
            error_msg = f"Failed to estimate fee for Ethereum transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    def disconnect(self) -> bool:
        """Disconnect from Ethereum network.
        
        Returns:
            bool: True if disconnected successfully
        """
        self.is_connected = False
        self.web3 = None
        logger.info(f"Disconnected from Ethereum {self.network_name}")
        return True
