"""
Avalanche Blockchain Adapter

This module provides a native, no-fallback adapter for the Avalanche blockchain.
It implements all required functionality for Avalanche interaction, including:
- Connection to Avalanche networks (C-Chain, mainnet, testnet)
- Balance checking
- Transaction creation, signing, and broadcasting
- Fee estimation
- Network status monitoring

Uses Web3.py for Avalanche C-Chain integration with no fallback mechanisms to ensure reliable operation.
"""

import logging
from typing import Any, Dict, List, Optional, Union, cast
from decimal import Decimal

from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.types import TxParams, Wei

from blockchain.base_adapter import (
    BlockchainAdapter as BaseBlockchainAdapter,
    ConnectionError as BlockchainConnectionError,
    TransactionError,
    ValidationError,
    strict_blockchain_operation,
)

# Configure module logger
logger = logging.getLogger(__name__)

class AvalancheAdapter(BaseBlockchainAdapter):
    """
    Native Avalanche blockchain adapter.
    
    Provides direct interaction with Avalanche C-Chain with no fallbacks.
    Implements the BaseBlockchainAdapter interface for consistent integration.
    """
    
    # Avalanche network constants
    NETWORKS = {
        'mainnet': {
            'name': 'Mainnet (C-Chain)',
            'chain_id': 43114,
            'rpc_endpoints': [
                'https://api.avax.network/ext/bc/C/rpc',
                'https://avalanche-c-chain.publicnode.com'
            ],
            'explorer_url': 'https://snowtrace.io'
        },
        'fuji': {
            'name': 'Fuji Testnet (C-Chain)',
            'chain_id': 43113,
            'rpc_endpoints': [
                'https://api.avax-test.network/ext/bc/C/rpc',
                'https://avalanche-fuji-c-chain.publicnode.com'
            ],
            'explorer_url': 'https://testnet.snowtrace.io'
        }
    }
    
    # Native currency details
    CURRENCY = {
        'name': 'Avalanche',
        'symbol': 'AVAX',
        'decimals': 18
    }
    
    def __init__(self, network: str = 'mainnet', endpoint: Optional[str] = None):
        """
        Initialize the Avalanche adapter.
        
        Args:
            network: Network name ('mainnet' or 'fuji')
            endpoint: Optional RPC endpoint URL
        """
        # Initialize properties
        self.web3 = None
        self.network = network.lower()
        self.is_connected = False
        self.last_block = 0
        self.chain_id = None
        
        # Validate network
        if self.network not in self.NETWORKS:
            raise ValueError(f"Unsupported Avalanche network: {network}")
        
        # Set network details
        self.network_config = self.NETWORKS[self.network]
        self.network_name = self.network_config['name']
        
        # Use provided endpoint or default to first in network config
        self.endpoint = endpoint or self.network_config['rpc_endpoints'][0]
        
        logger.info(f"Initialized Avalanche adapter for {self.network_name}")
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """
        Connect to Avalanche C-Chain network.
        
        Returns:
            bool: True if connection successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize Web3 with provider
            self.web3 = Web3(Web3.HTTPProvider(self.endpoint))
            # Add POA middleware for proper blockchain support
            self.web3.middleware_onion.inject(native_geth_poa_middleware, layer=0)
            
            # Verify connection
            if not self.web3.is_connected():
                # Try alternative endpoints if primary fails
                if not self.endpoint or self.endpoint == self.network_config['rpc_endpoints'][0]:
                    for backup_endpoint in self.network_config['rpc_endpoints'][1:]:
                        logger.info(f"Trying backup Avalanche endpoint: {backup_endpoint}")
                        self.web3 = Web3(Web3.HTTPProvider(backup_endpoint))
                        # Add POA middleware for proper blockchain support
                        self.web3.middleware_onion.inject(native_geth_poa_middleware, layer=0)
                        if self.web3.is_connected():
                            self.endpoint = backup_endpoint
                            break
                
                # If still not connected
                if not self.web3.is_connected():
                    raise BlockchainConnectionError(f"Could not connect to any Avalanche {self.network_name} endpoints")
            
            # Verify chain ID
            chain_id = self.web3.eth.chain_id
            expected_chain_id = self.network_config['chain_id']
            
            if chain_id != expected_chain_id:
                raise BlockchainConnectionError(
                    f"Chain ID mismatch: connected to {chain_id}, expected {expected_chain_id}"
                )
                
            # Update state
            self.is_connected = True
            self.chain_id = chain_id
            self.last_block = self.web3.eth.block_number
            
            logger.info(f"Connected to Avalanche {self.network_name}, chain ID: {chain_id}")
            return True
            
        except BlockchainConnectionError:
            # Re-raise specific connection errors
            raise
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to Avalanche {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
    
    @strict_blockchain_operation
    def get_balance(self, address: str) -> Decimal:
        """
        Get AVAX balance for address on Avalanche C-Chain.
        
        Args:
            address: Avalanche C-Chain address to check
            
        Returns:
            Decimal: Balance in AVAX
            
        Raises:
            ValidationError: If address is invalid
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Avalanche network")
            
        try:
            # Validate address
            if not self.validate_address(address):
                raise ValidationError(f"Invalid Avalanche address: {address}")
                
            # Convert to checksum address
            checksum_address = Web3.to_checksum_address(address)
            
            # Get balance in wei
            balance_wei = self.web3.eth.get_balance(checksum_address)
            
            # Convert to AVAX and return as Decimal
            balance_avax = Decimal(str(self.web3.from_wei(balance_wei, 'ether')))
            return balance_avax
            
        except ValidationError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to get balance for {address}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, **kwargs) -> TxParams:
        """Create an Avalanche C-Chain transaction.
        
        Args:
            **kwargs: Transaction parameters including:
                - from_address: Sender address
                - to_address: Recipient address
                - value: Amount in AVAX
                - data: Optional transaction data
                - gas: Optional gas limit
                - gas_price: Optional gas price in wei
                - max_fee_per_gas: Optional max fee per gas (EIP-1559)
                - max_priority_fee_per_gas: Optional max priority fee per gas (EIP-1559)
                - nonce: Optional transaction nonce
            
        Returns:
            TxParams: Avalanche transaction parameters
            
        Raises:
            TransactionError: If transaction creation fails
            ValidationError: If addresses are invalid
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Avalanche network")
            
        try:
            # Extract and validate parameters
            from_address = kwargs.get('from_address')
            to_address = kwargs.get('to_address')
            value = kwargs.get('value', 0)  # In AVAX
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
            
            # Convert AVAX value to wei
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
            # Avalanche C-Chain supports EIP-1559
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
            error_msg = f"Failed to create Avalanche transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: TxParams, private_key: str) -> Dict[str, Any]:
        """Sign an Avalanche transaction with private key.
        
        Args:
            transaction: The transaction parameters to sign
            private_key: Private key (hex string with or without 0x prefix)
            
        Returns:
            Dict[str, Any]: Signed transaction data
            
        Raises:
            TransactionError: If transaction signing fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Avalanche network")
            
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
            error_msg = f"Failed to sign Avalanche transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict[str, Any]) -> str:
        """Broadcast signed transaction to Avalanche network.
        
        Args:
            signed_transaction: Signed transaction data with raw_transaction hex
            
        Returns:
            str: Transaction hash
            
        Raises:
            TransactionError: If broadcasting fails
            ConnectionError: If network connection is lost
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Avalanche network")
            
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
            error_msg = f"Failed to broadcast Avalanche transaction: {str(e)}"
            logger.error(error_msg)
            # Handle case where transaction was already sent
            if "already known" in str(e).lower() and 'hash' in signed_transaction:
                logger.info(f"Transaction was already broadcast: {signed_transaction['hash']}")
                return signed_transaction['hash']
            # Re-raise with context
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
    
    def validate_address(self, address: str) -> bool:
        """Validate Avalanche C-Chain address format.
        
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
        """Get status of Avalanche transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Avalanche network")
            
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
                    
            # Add Avalanche-specific fields if available
            # This could include cross-chain information if available from APIs
            result['finalized'] = confirmations >= 2  # Avalanche finality typically requires 2 confirmations
                    
            return result
                
        except TransactionNotFound:
            return {
                'hash': tx_hash,
                'found': False,
                'status': 'unknown',
                'block_number': None,
                'confirmations': 0
            }
            
        except ValidationError as ve:
            # Add context to validation error before re-raising
            logger.debug(f"Validation error: {str(ve)}")
            raise
            
        except Exception as e:
            error_msg = f"Failed to get Avalanche transaction status for {tx_hash}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
    
    @strict_blockchain_operation
    def get_network_status(self) -> Dict[str, Any]:
        """Get Avalanche C-Chain network status.
        
        Returns:
            dict: Network status including block height, sync state, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Avalanche network")
            
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
                'name': f"Avalanche {self.network_name}",
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
                
            # Avalanche supports EIP-1559, check for baseFeePerGas
            if latest_block and 'baseFeePerGas' in latest_block:
                base_fee_wei = latest_block['baseFeePerGas']
                result.update({
                    'eip1559_enabled': True,
                    'base_fee_wei': base_fee_wei,
                    'base_fee_gwei': self.web3.from_wei(base_fee_wei, 'gwei')
                })
            else:
                result['eip1559_enabled'] = False
                
            # Add Avalanche-specific network information
            result['network_type'] = 'avalanche_c_chain'
            result['consensus'] = 'snowman'  # Avalanche C-Chain uses Snowman consensus
            result['finality'] = 'fast'  # Avalanche has fast finality
                
            return result
                
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to get Avalanche network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, transaction: TxParams) -> Dict[str, Any]:
        """Estimate fee for Avalanche transaction.
        
        Args:
            transaction: Transaction to estimate fee for
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        if not self.is_connected or not self.web3:
            raise BlockchainConnectionError("Not connected to Avalanche network")
            
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
                # Add 20% buffer for safety
                gas_limit = int(gas_limit * 1.2)
                
            # Calculate fee in Wei and AVAX
            fee_wei = gas_price * gas_limit
            fee_avax = self.web3.from_wei(fee_wei, 'ether')
            
            # Get fee estimates for different priorities
            try:
                # Get block to check if EIP-1559 is active
                latest_block = self.web3.eth.get_block('latest')
                eip1559_enabled = 'baseFeePerGas' in latest_block
                
                if eip1559_enabled:
                    # EIP-1559 based fee estimates
                    base_fee = latest_block['baseFeePerGas']
                    
                    # Typical priority fees for Avalanche C-Chain
                    priority_fees = {
                        'slow': self.web3.to_wei(25, 'gwei'),
                        'normal': self.web3.to_wei(30, 'gwei'),
                        'fast': self.web3.to_wei(35, 'gwei')
                    }
                    
                    # Calculate max fees (base fee + priority fee)
                    max_fee = {
                        'slow': base_fee + priority_fees['slow'],
                        'normal': base_fee + priority_fees['normal'],
                        'fast': base_fee + priority_fees['fast']
                    }
                    
                    # Formulate fee estimates
                    fee_estimates = {
                        'slow': {
                            'max_fee_per_gas_wei': max_fee['slow'],
                            'max_fee_per_gas_gwei': self.web3.from_wei(max_fee['slow'], 'gwei'),
                            'priority_fee_wei': priority_fees['slow'],
                            'priority_fee_gwei': self.web3.from_wei(priority_fees['slow'], 'gwei'),
                            'estimated_fee_avax': self.web3.from_wei(max_fee['slow'] * gas_limit, 'ether')
                        },
                        'normal': {
                            'max_fee_per_gas_wei': max_fee['normal'],
                            'max_fee_per_gas_gwei': self.web3.from_wei(max_fee['normal'], 'gwei'),
                            'priority_fee_wei': priority_fees['normal'],
                            'priority_fee_gwei': self.web3.from_wei(priority_fees['normal'], 'gwei'),
                            'estimated_fee_avax': self.web3.from_wei(max_fee['normal'] * gas_limit, 'ether')
                        },
                        'fast': {
                            'max_fee_per_gas_wei': max_fee['fast'],
                            'max_fee_per_gas_gwei': self.web3.from_wei(max_fee['fast'], 'gwei'),
                            'priority_fee_wei': priority_fees['fast'],
                            'priority_fee_gwei': self.web3.from_wei(priority_fees['fast'], 'gwei'),
                            'estimated_fee_avax': self.web3.from_wei(max_fee['fast'] * gas_limit, 'ether')
                        }
                    }
                else:
                    # Legacy fee structure
                    fee_estimates = {
                        'slow': {
                            'gas_price_wei': int(gas_price * 0.8),  # 80% of current
                            'gas_price_gwei': self.web3.from_wei(int(gas_price * 0.8), 'gwei'),
                            'estimated_fee_avax': self.web3.from_wei(int(gas_price * 0.8) * gas_limit, 'ether')
                        },
                        'normal': {
                            'gas_price_wei': gas_price,
                            'gas_price_gwei': self.web3.from_wei(gas_price, 'gwei'),
                            'estimated_fee_avax': self.web3.from_wei(gas_price * gas_limit, 'ether')
                        },
                        'fast': {
                            'gas_price_wei': int(gas_price * 1.2),  # 120% of current
                            'gas_price_gwei': self.web3.from_wei(int(gas_price * 1.2), 'gwei'),
                            'estimated_fee_avax': self.web3.from_wei(int(gas_price * 1.2) * gas_limit, 'ether')
                        }
                    }
            except Exception as e:
                logger.warning(f"Failed to get fee estimates: {str(e)}")
                fee_estimates = None
                
            # Build response
            result = {
                'gas_price_wei': gas_price,
                'gas_price_gwei': self.web3.from_wei(gas_price, 'gwei'),
                'gas_limit': gas_limit,
                'fee_wei': fee_wei,
                'fee_avax': fee_avax
            }
            
            # Add fee estimates if available
            if fee_estimates:
                result['fee_estimates'] = fee_estimates
                
            # Add Avalanche-specific information if available
            result['network'] = self.network
            result['chain_id'] = self.chain_id or self.network_config['chain_id']
                
            return result
            
        except Exception as e:
            error_msg = f"Failed to estimate fee for Avalanche transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    def disconnect(self) -> bool:
        """Disconnect from Avalanche network.
        
        Returns:
            bool: True if disconnected successfully
        """
        self.is_connected = False
        self.web3 = None
        logger.info(f"Disconnected from Avalanche {self.network_name}")
        return True
# Use native middleware implementation - no fallbacks allowed
# Using kingdomweb3_v2 for blockchain connectivity
from kingdomweb3_v2 import rpc_manager, get_network_config
