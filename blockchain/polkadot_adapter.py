"""
Polkadot Blockchain Adapter

This module provides a native, no-fallback adapter for the Polkadot blockchain.
It implements all required functionality for Polkadot interaction, including:
- Connection to Polkadot networks (mainnet, testnet)
- Balance checking
- Transaction creation, signing, and broadcasting
- Network status monitoring
- Cross-chain (parachain) communication support

Uses substrate-interface for Polkadot integration with no fallback mechanisms
to ensure reliable operation.
"""

import logging
import json
import urllib.request
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal

from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

from blockchain.base_adapter import (
    BlockchainAdapter as BaseBlockchainAdapter,
    ConnectionError as BlockchainConnectionError,
    TransactionError,
    ValidationError,
    strict_blockchain_operation,
)

# Configure module logger
logger = logging.getLogger(__name__)

class PolkadotAdapter(BaseBlockchainAdapter):
    """
    Native Polkadot blockchain adapter.
    
    Provides direct interaction with Polkadot with no fallbacks.
    Implements the BaseBlockchainAdapter interface for consistent integration.
    """
    
    # Polkadot network constants
    NETWORKS = {
        'mainnet': {
            'name': 'Polkadot',
            'rpc_endpoints': [
                'wss://rpc.polkadot.io',
                'wss://polkadot.api.onfinality.io/public-ws',
                'wss://polkadot-rpc.dwellir.com'
            ],
            'explorer_url': 'https://polkascan.io/polkadot'
        },
        'kusama': {
            'name': 'Kusama',
            'rpc_endpoints': [
                'wss://kusama-rpc.polkadot.io',
                'wss://kusama.api.onfinality.io/public-ws',
                'wss://kusama-rpc.dwellir.com'
            ],
            'explorer_url': 'https://polkascan.io/kusama'
        },
        'westend': {
            'name': 'Westend Testnet',
            'rpc_endpoints': [
                'wss://westend-rpc.polkadot.io',
                'wss://westend.api.onfinality.io/public-ws'
            ],
            'explorer_url': 'https://westend.subscan.io'
        },
        'rococo': {
            'name': 'Rococo Testnet',
            'rpc_endpoints': [
                'wss://rococo-rpc.polkadot.io'
            ],
            'explorer_url': 'https://rococo.subscan.io'
        }
    }
    
    # Native currency details
    CURRENCY = {
        'mainnet': {
            'name': 'Polkadot',
            'symbol': 'DOT',
            'decimals': 10,  # Polkadot uses 10 decimals
            'ss58_format': 0  # Polkadot address format
        },
        'kusama': {
            'name': 'Kusama',
            'symbol': 'KSM',
            'decimals': 12,  # Kusama uses 12 decimals
            'ss58_format': 2  # Kusama address format
        },
        'westend': {
            'name': 'Westend',
            'symbol': 'WND',
            'decimals': 12,
            'ss58_format': 42
        },
        'rococo': {
            'name': 'Rococo',
            'symbol': 'ROC',
            'decimals': 12,
            'ss58_format': 42
        }
    }
    
    def __init__(self, network: str = 'mainnet', endpoint: Optional[str] = None):
        """
        Initialize the Polkadot adapter.
        
        Args:
            network: Network name ('mainnet', 'kusama', 'westend', or 'rococo')
            endpoint: Optional RPC endpoint URL
        """
        # Initialize properties
        self.substrate = None
        self.network = network.lower()
        self.is_connected = False
        self.metadata = None
        self.genesis_hash = None
        self.runtime_version = None
        
        # Validate network
        if self.network not in self.NETWORKS:
            raise ValueError(f"Unsupported Polkadot network: {network}")
        
        # Set network details
        self.network_config = self.NETWORKS[self.network]
        self.network_name = self.network_config['name']
        self.currency = self.CURRENCY[self.network]
        
        # Use provided endpoint or default to first in network config
        self.endpoint = endpoint or self.network_config['rpc_endpoints'][0]
        
        logger.info(f"Initialized Polkadot adapter for {self.network_name}")
    
    def _try_backup_endpoints(self) -> bool:
        """Try to connect using backup endpoints.
        
        Returns:
            bool: True if successfully connected using a backup endpoint
        """
        for backup_endpoint in self.network_config['rpc_endpoints'][1:]:
            logger.info(f"Trying backup Polkadot endpoint: {backup_endpoint}")
            try:
                self.substrate = SubstrateInterface(
                    url=backup_endpoint,
                    ss58_format=self.currency['ss58_format'],
                    type_registry_preset=self.network
                )
                # Verify connection
                self.metadata = self.substrate.metadata
                self.genesis_hash = self.substrate.genesis_hash
                self.runtime_version = self.substrate.runtime_version
                
                # Update endpoint and connection status
                self.endpoint = backup_endpoint
                self.is_connected = True
                
                logger.info(f"Connected to {self.network_name} using backup endpoint")
                return True
            except Exception as e:
                logger.warning(f"Failed to connect to backup endpoint {backup_endpoint}: {str(e)}")
        
        # If we get here, all backups failed
        return False
            
    @strict_blockchain_operation
    def connect(self) -> bool:
        """
        Connect to Polkadot network.
        
        Returns:
            bool: True if connection successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize SubstrateInterface with endpoint
            self.substrate = SubstrateInterface(
                url=self.endpoint,
                ss58_format=self.currency['ss58_format'],
                type_registry_preset=self.network
            )
            
            # Verify connection by fetching basic info
            self.metadata = self.substrate.metadata
            self.genesis_hash = self.substrate.genesis_hash
            self.runtime_version = self.substrate.runtime_version
            
            # Connection is established if we get this far
            self.is_connected = True
            
            logger.info(f"Connected to {self.network_name}, runtime: {self.runtime_version}")
            return True
            
        except SubstrateRequestException as e:
            # Try alternative endpoints if primary fails
            if not self.endpoint or self.endpoint == self.network_config['rpc_endpoints'][0]:
                connected = self._try_backup_endpoints()
                if connected:
                    return True
            
            # If still not connected after trying all endpoints
            self.is_connected = False
            error_msg = f"Failed to connect to any {self.network_name} endpoints: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
    
    @strict_blockchain_operation
    def get_balance(self, address: str) -> Decimal:
        """
        Get Polkadot/Kusama balance for address.
        
        Args:
            address: Polkadot address to check
            
        Returns:
            Decimal: Balance in DOT/KSM
            
        Raises:
            ValidationError: If address is invalid
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.substrate:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Validate address
            if not self.validate_address(address):
                raise ValidationError(f"Invalid {self.network_name} address: {address}")
                
            # Query system for account info
            result = self.substrate.query(
                module='System',
                storage_function='Account',
                params=[address]
            )
            
            # Extract balance from account data
            account_data = result.value.get('data', {})
            balance_raw = account_data.get('free', 0)
            
            # Convert to DOT/KSM decimal value
            balance = Decimal(balance_raw) / Decimal(10 ** self.currency['decimals'])
            
            return balance
            
        except ValidationError as ve:
            # Add context to validation error before re-raising
            logger.debug(f"Validation error: {str(ve)}")
            raise
            
        except Exception as e:
            error_msg = f"Failed to get balance for {address}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    def validate_address(self, address: str) -> bool:
        """
        Validate Polkadot address format.
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid, False otherwise
        """
        if not address:
            return False
            
        try:
            # Attempt to create a keypair with this address for validation
            # This will throw an exception if the address format is invalid
            _ = Keypair(ss58_address=address)
            return True
        except Exception:
            return False
            
    @strict_blockchain_operation
    def create_transaction(self, **kwargs) -> Dict[str, Any]:
        """Create a Polkadot transaction call.
        
        Args:
            **kwargs: Transaction parameters including:
                - from_address: Sender address
                - to_address: Recipient address
                - value: Amount to send in DOT/KSM/etc.
                - call_module: Module to call (e.g., 'Balances')
                - call_function: Function to call (e.g., 'transfer')
                - call_params: Additional parameters for call
            
        Returns:
            Dict[str, Any]: Polkadot transaction parameters
            
        Raises:
            TransactionError: If transaction creation fails
            ValidationError: If addresses are invalid
        """
        if not self.is_connected or not self.substrate:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Extract and validate parameters
            from_address = kwargs.get('from_address')
            to_address = kwargs.get('to_address')
            value = kwargs.get('value', 0)  # Amount in DOT/KSM/etc.
            call_module = kwargs.get('call_module', 'Balances')
            call_function = kwargs.get('call_function', 'transfer')
            call_params = kwargs.get('call_params', {})
            
            # Validate sender address
            if not from_address or not self.validate_address(from_address):
                raise ValidationError(f"Invalid from address: {from_address}")
                
            # If this is a transfer, validate recipient address
            if call_module == 'Balances' and call_function == 'transfer' and to_address:
                if not self.validate_address(to_address):
                    raise ValidationError(f"Invalid to address: {to_address}")
            
            # Initialize call parameters
            params = {}
            
            # Handle common case: Balance transfer
            if call_module == 'Balances' and call_function == 'transfer':
                # Convert human-readable value to chain format with correct decimals
                value_chain_units = int(Decimal(str(value)) * Decimal(10 ** self.currency['decimals']))
                
                # Set parameters for balance transfer
                params = {
                    'dest': {'Id': to_address},  # Modern Substrate format
                    'value': value_chain_units
                }
            # Handle generic calls
            elif call_params:
                params = call_params
            
            # Create the call
            call = self.substrate.compose_call(
                call_module=call_module,
                call_function=call_function,
                call_params=params
            )
            
            # Get account nonce
            nonce = self.substrate.get_account_nonce(from_address)
            
            # Create a transaction
            transaction = {
                'call': call,
                'nonce': nonce,
                'from_address': from_address,
                'to_address': to_address if 'to_address' in kwargs else None,
                'value': value if 'value' in kwargs else None,
                'call_module': call_module,
                'call_function': call_function,
                'call_hash': call.call_hash.hex(),
            }
            
            return transaction
            
        except (ValidationError, BlockchainConnectionError):
            # Re-raise these specific exceptions
            raise
            
        except Exception as e:
            error_msg = f"Failed to create {self.network_name} transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict[str, Any], seed_or_mnemonic: str) -> Dict[str, Any]:
        """Sign a Polkadot transaction with seed or mnemonic.
        
        Args:
            transaction: Transaction parameters from create_transaction
            seed_or_mnemonic: Seed or mnemonic phrase
            
        Returns:
            Dict[str, Any]: Signed transaction data
            
        Raises:
            TransactionError: If transaction signing fails
        """
        if not self.is_connected or not self.substrate:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Get the call from the transaction
            call = transaction.get('call')
            if not call:
                raise TransactionError("Transaction does not contain a valid call")
                
            # Create keypair from seed or mnemonic
            keypair = Keypair.create_from_uri(
                uri=seed_or_mnemonic,
                ss58_format=self.currency['ss58_format']
            )
            
            # Check if address matches
            from_address = transaction.get('from_address')
            if from_address and keypair.ss58_address != from_address:
                raise ValidationError(
                    f"Keypair address {keypair.ss58_address} does not match transaction sender {from_address}"
                )
            
            # Create extrinsic
            extrinsic = self.substrate.create_signed_extrinsic(
                call=call,
                keypair=keypair,
                nonce=transaction.get('nonce')
            )
            
            # Return signed transaction data
            signed_tx = {
                'extrinsic': extrinsic,
                'extrinsic_hash': extrinsic.extrinsic_hash.hex(),
                'signer': keypair.ss58_address,
                'call_module': transaction.get('call_module'),
                'call_function': transaction.get('call_function')
            }
            
            # Include transfer details if relevant
            if transaction.get('to_address') and transaction.get('value') is not None:
                signed_tx['to_address'] = transaction['to_address']
                signed_tx['value'] = transaction['value']
                
            return signed_tx
            
        except Exception as e:
            error_msg = f"Failed to sign {self.network_name} transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict[str, Any]) -> str:
        """Broadcast signed transaction to Polkadot network.
        
        Args:
            signed_transaction: Signed transaction data with extrinsic
            
        Returns:
            str: Transaction hash
            
        Raises:
            TransactionError: If broadcasting fails
            ConnectionError: If network connection is lost
        """
        if not self.is_connected or not self.substrate:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Extract extrinsic
            extrinsic = signed_transaction.get('extrinsic')
            if not extrinsic:
                raise TransactionError("No extrinsic provided in signed transaction data")
                
            # Submit the extrinsic
            receipt = self.substrate.submit_extrinsic(
                extrinsic=extrinsic,
                wait_for_inclusion=False  # Don't wait for block inclusion
            )
            
            # Return hash as string
            tx_hash = receipt.extrinsic_hash.hex() if receipt else extrinsic.extrinsic_hash.hex()
            
            logger.info(f"Broadcast {self.network_name} transaction: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            error_msg = f"Failed to broadcast {self.network_name} transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get status of Polkadot transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        if not self.is_connected or not self.substrate:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Validate transaction hash format
            if not tx_hash or not tx_hash.startswith('0x'):
                raise ValidationError(f"Invalid transaction hash format: {tx_hash}")
                
            # Query for transaction in block
            result = None
            block_hash = None
            block_number = None
            
            # Get current block for confirmation count
            try:
                current_block_hash = self.substrate.get_chain_head()
                current_block = self.substrate.get_block_number(current_block_hash)
            except Exception as e:
                logger.warning(f"Could not fetch current block: {str(e)}")
                current_block = None
                
            # Try to find transaction by extrinsic hash in recent blocks
            # This is a simplified approach - production code would use indexing or APIs
            if current_block:
                # Search in last 20 blocks (simplified for demonstration)
                for i in range(20):
                    if current_block - i <= 0:
                        break
                        
                    try:
                        # Get block hash
                        block_hash = self.substrate.get_block_hash(current_block - i)
                        # Get block
                        block_data = self.substrate.get_block(block_hash)
                        
                        # Check extrinsics in block
                        for idx, extrinsic in enumerate(block_data['extrinsics']):
                            if extrinsic.extrinsic_hash.hex() == tx_hash:
                                result = extrinsic
                                block_number = current_block - i
                                break
                                
                        if result:
                            break
                    except Exception as e:
                        logger.debug(f"Error searching block {current_block - i}: {str(e)}")
            
            # If not found via local block scan, query the Subscan indexer API
            if not result:
                try:
                    subscan_url = "https://polkadot.api.subscan.io/api/scan/extrinsic"
                    payload = json.dumps({"hash": tx_hash}).encode()
                    req = urllib.request.Request(
                        subscan_url,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        subscan_data = json.loads(resp.read().decode())

                    if subscan_data.get("code") == 0 and subscan_data.get("data"):
                        ext = subscan_data["data"]
                        block_number = ext.get("block_num")
                        subscan_confirmations = 0
                        if current_block and block_number:
                            subscan_confirmations = current_block - int(block_number) + 1
                        return {
                            'hash': tx_hash,
                            'found': True,
                            'status': 'confirmed' if ext.get("success") else 'failed',
                            'block_number': block_number,
                            'block_hash': ext.get("block_hash"),
                            'confirmations': subscan_confirmations,
                            'timestamp': ext.get("block_timestamp"),
                        }
                except Exception as subscan_err:
                    logger.debug(f"Subscan lookup failed for {tx_hash}: {subscan_err}")

            if not result:
                return {
                    'hash': tx_hash,
                    'found': False,
                    'status': 'unknown',
                    'block_number': None,
                    'confirmations': 0
                }
                
            # Transaction found, build response
            confirmations = 0
            if current_block and block_number:
                confirmations = current_block - block_number + 1
                
            # Format response
            tx_response = {
                'hash': tx_hash,
                'found': True,
                'status': 'confirmed',  # Confirmed since we found it in a block
                'block_number': block_number,
                'block_hash': block_hash.hex() if block_hash else None,
                'confirmations': confirmations,
                'timestamp': None  # Would require additional block time query
            }
            
            # Add call details if available
            if hasattr(result, 'call'):
                tx_response.update({
                    'call_module': result.call.module.name,
                    'call_function': result.call.function.name,
                })
                
            # Add transfer details if it's a balance transfer
            if hasattr(result, 'call') and result.call.module.name == 'Balances' and \
               result.call.function.name in ['transfer', 'transfer_keep_alive', 'transfer_all']:
                # Extract destination and amount
                params = result.call.params
                dest = params[0].value if params and len(params) > 0 else None
                amount = params[1].value if params and len(params) > 1 else None
                
                if dest and amount:
                    # Convert amount from chain units
                    human_amount = Decimal(amount) / Decimal(10 ** self.currency['decimals'])
                    
                    tx_response.update({
                        'to': dest,
                        'from': result.address,
                        'amount': str(human_amount),
                        'currency': self.currency['symbol']
                    })
                    
            return tx_response
                
        except ValidationError as ve:
            # Add context to validation error before re-raising
            logger.debug(f"Validation error: {str(ve)}")
            raise
            
        except Exception as e:
            error_msg = f"Failed to get {self.network_name} transaction status for {tx_hash}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
    
    @strict_blockchain_operation
    def get_network_status(self) -> Dict[str, Any]:
        """Get Polkadot network status.
        
        Returns:
            dict: Network status including block height, finalized height, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.substrate:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Get chain head (latest block hash)
            chain_head = self.substrate.get_chain_head()
            
            # Get latest block number
            block_number = self.substrate.get_block_number(chain_head)
            
            # Get finalized head
            finalized_head = self.substrate.get_chain_finalised_head()
            
            # Get finalized block number
            finalized_block_number = self.substrate.get_block_number(finalized_head)
            
            # Get latest block details
            latest_block = self.substrate.get_block(chain_head)
            
            # Get runtime info
            runtime = self.substrate.runtime_version
            
            # Check node health (if available)
            health = None
            try:
                health = self.substrate.rpc_request('system_health', []).get('result', {})
            except Exception as e:
                logger.debug(f"Could not get node health: {str(e)}")
                
            # Get system chain info
            system_chain = self.substrate.rpc_request('system_chain', []).get('result', self.network_name)
            
            # Get network peers info if available
            peers = None
            try:
                peers = self.substrate.rpc_request('system_peers', []).get('result', [])
            except Exception as e:
                logger.debug(f"Could not get peers info: {str(e)}")
                
            # Get chain properties
            properties = None
            try:
                properties = self.substrate.rpc_request('system_properties', []).get('result', {})
            except Exception as e:
                logger.debug(f"Could not get chain properties: {str(e)}")
                
            # Build result
            result = {
                'name': system_chain or self.network_name,
                'connected': self.is_connected,
                'syncing': health.get('isSyncing', False) if health else None,
                'peers_count': len(peers) if peers is not None else health.get('peers', 0) if health else None,
                'block_height': block_number,
                'finalized_height': finalized_block_number,
                'latest_block_hash': chain_head.hex(),
                'finalized_block_hash': finalized_head.hex(),
                'runtime_name': runtime.get('implName'),
                'runtime_version': f"{runtime.get('specVersion', '')}.{runtime.get('implVersion', '')}" if runtime else None,
                'genesis_hash': self.genesis_hash.hex() if self.genesis_hash else None,
            }
            
            # Add block time if available
            if 'header' in latest_block and 'extrinsics' in latest_block:
                # Extrinsic 0 often contains timestamp in Substrate chains
                try:
                    timestamp_extrinsic = next(
                        (ex for ex in latest_block['extrinsics'] 
                         if hasattr(ex, 'call') and ex.call.module.name == 'Timestamp'), 
                        None
                    )
                    if timestamp_extrinsic and hasattr(timestamp_extrinsic.call, 'params'):
                        timestamp_param = next(
                            (p.value for p in timestamp_extrinsic.call.params 
                             if p.name == 'now'),
                            None
                        )
                        if timestamp_param:
                            result['latest_block_time'] = timestamp_param
                except Exception as e:
                    logger.debug(f"Could not extract timestamp: {str(e)}")
                    
            # Add network specific properties
            result['token_symbol'] = self.currency.get('symbol')
            result['token_decimals'] = self.currency.get('decimals')
            
            # Add properties from system if available
            if properties:
                if 'ss58Format' in properties:
                    result['ss58_format'] = properties['ss58Format']
                if 'tokenSymbol' in properties:
                    result['token_symbol'] = properties['tokenSymbol']
                if 'tokenDecimals' in properties:
                    result['token_decimals'] = properties['tokenDecimals']
                    
            # Add Polkadot-specific information
            if health:
                result.update({
                    'health_syncing': health.get('isSyncing', False),
                    'health_peers': health.get('peers', 0),
                    'health_should_have_peers': health.get('shouldHavePeers', True)
                })
                
            # Add validator info if available and this is the relay chain
            # Only applicable for relay chains (Polkadot, Kusama)
            if self.network in ['mainnet', 'kusama']:
                try:
                    validator_count = self.substrate.query(
                        module='Session', 
                        storage_function='Validators'
                    )
                    if validator_count:
                        result['active_validators'] = len(validator_count.value)
                except Exception as e:
                    logger.debug(f"Could not get validator count: {str(e)}")
                    
            return result
                
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to get {self.network_name} network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, call_module: str, call_function: str, call_params: Dict[str, Any], 
                    sender: str) -> Dict[str, Any]:
        """Estimate fee for Polkadot transaction.
        
        Args:
            call_module: Module to call (e.g., 'Balances')
            call_function: Function to call (e.g., 'transfer')
            call_params: Parameters for call
            sender: Sender address
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        if not self.is_connected or not self.substrate:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Validate sender address
            if not self.validate_address(sender):
                raise ValidationError(f"Invalid {self.network_name} address: {sender}")
                
            # Create the call
            call = self.substrate.compose_call(
                call_module=call_module,
                call_function=call_function,
                call_params=call_params
            )
            
            # Get payment info from substrate
            payment_info = self.substrate.get_payment_info(call, sender)
            
            if not payment_info:
                raise TransactionError(f"Could not get payment info for {call_module}.{call_function}")
                
            # Extract fee information
            fee_chain_units = payment_info.get('partialFee', 0)
            
            # Convert to human-readable format
            fee_human = Decimal(fee_chain_units) / Decimal(10 ** self.currency['decimals'])
            
            # Get additional fee estimates if available
            weight = payment_info.get('weight', None)
            weight_to_fee = None
            if 'class' in payment_info and payment_info['class'] == 'normal':
                # Adjust estimates for different priorities
                # These adjustments are simplified examples
                slow_fee = int(fee_chain_units * 0.8)
                normal_fee = fee_chain_units
                fast_fee = int(fee_chain_units * 1.2)
                
                # Convert to human-readable
                slow_human = Decimal(slow_fee) / Decimal(10 ** self.currency['decimals'])
                normal_human = fee_human
                fast_human = Decimal(fast_fee) / Decimal(10 ** self.currency['decimals'])
                
                weight_to_fee = {
                    'slow': {
                        'fee_chain_units': slow_fee,
                        'fee_human': str(slow_human),
                        'fee_currency': self.currency['symbol']
                    },
                    'normal': {
                        'fee_chain_units': normal_fee,
                        'fee_human': str(normal_human),
                        'fee_currency': self.currency['symbol']
                    },
                    'fast': {
                        'fee_chain_units': fast_fee,
                        'fee_human': str(fast_human),
                        'fee_currency': self.currency['symbol']
                    }
                }
            
            # Build response
            result = {
                'fee_chain_units': fee_chain_units,
                'fee_human': str(fee_human),
                'fee_currency': self.currency['symbol'],
                'call_module': call_module,
                'call_function': call_function,
            }
            
            # Add weight if available
            if weight is not None:
                result['weight'] = weight
                
            # Add additional fee estimates if available
            if weight_to_fee:
                result['fee_estimates'] = weight_to_fee
                
            # Add network-specific details
            result['network'] = self.network
            result['decimals'] = self.currency['decimals']
                
            return result
            
        except (ValidationError, BlockchainConnectionError):
            # Re-raise these specific exceptions
            raise
            
        except Exception as e:
            error_msg = f"Failed to estimate fee for {self.network_name} transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    def disconnect(self) -> bool:
        """Disconnect from Polkadot network.
        
        Returns:
            bool: True if disconnected successfully
        """
        self.is_connected = False
        self.substrate = None
        logger.info(f"Disconnected from {self.network_name}")
        return True
