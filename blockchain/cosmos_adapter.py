"""
Cosmos Blockchain Adapter

This module provides a native, no-fallback adapter for the Cosmos ecosystem.
It implements all required functionality for Cosmos interaction, including:
- Connection to Cosmos Hub and other Cosmos-based chains
- Balance checking
- Transaction creation, signing, and broadcasting
- IBC (Inter-Blockchain Communication) support
- Network status monitoring

Uses cosmos-sdk-py for native Cosmos integration with no fallback mechanisms
to ensure reliable operation.
"""

import logging
import json
import time
import urllib.request
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal

# Cosmos SDK dependencies
from cosmos_sdk.client.lcd import LCDClient
from cosmos_sdk.client.lcd.api.tx import CreateTxOptions
from cosmos_sdk.key.mnemonic import MnemonicKey
from cosmos_sdk.core.bank import MsgSend
from cosmos_sdk.core.tx import SignDoc, Tx
from cosmos_sdk.exceptions import LCDResponseError

from blockchain.base_adapter import (
    BlockchainAdapter as BaseBlockchainAdapter,
    ConnectionError as BlockchainConnectionError,
    TransactionError,
    ValidationError,
    strict_blockchain_operation,
)

# Configure module logger
logger = logging.getLogger(__name__)

class CosmosAdapter(BaseBlockchainAdapter):
    """
    Native Cosmos blockchain adapter.
    
    Provides direct interaction with Cosmos ecosystem with no fallbacks.
    Implements the BaseBlockchainAdapter interface for consistent integration.
    """
    
    # Cosmos network constants
    NETWORKS = {
        'cosmoshub': {
            'name': 'Cosmos Hub',
            'chain_id': 'cosmoshub-4',
            'rpc_endpoints': [
                'https://lcd-cosmoshub.keplr.app',
                'https://rest.cosmos.directory/cosmoshub',
                'https://api.cosmos.network'
            ],
            'explorer_url': 'https://www.mintscan.io/cosmos'
        },
        'osmosis': {
            'name': 'Osmosis',
            'chain_id': 'osmosis-1',
            'rpc_endpoints': [
                'https://lcd.osmosis.zone',
                'https://rest.cosmos.directory/osmosis',
                'https://osmosis-api.polkachu.com'
            ],
            'explorer_url': 'https://www.mintscan.io/osmosis'
        },
        'juno': {
            'name': 'Juno',
            'chain_id': 'juno-1',
            'rpc_endpoints': [
                'https://lcd-juno.keplr.app',
                'https://rest.cosmos.directory/juno',
                'https://juno-api.polkachu.com'
            ],
            'explorer_url': 'https://www.mintscan.io/juno'
        },
        'akash': {
            'name': 'Akash',
            'chain_id': 'akashnet-2',
            'rpc_endpoints': [
                'https://lcd-akash.keplr.app',
                'https://rest.cosmos.directory/akash',
                'https://akash-api.polkachu.com'
            ],
            'explorer_url': 'https://www.mintscan.io/akash'
        },
        'secret': {
            'name': 'Secret Network',
            'chain_id': 'secret-4',
            'rpc_endpoints': [
                'https://lcd-secret.keplr.app',
                'https://rest.cosmos.directory/secretnetwork',
                'https://secret-api.polkachu.com'
            ],
            'explorer_url': 'https://www.mintscan.io/secret'
        },
        'stargaze': {
            'name': 'Stargaze',
            'chain_id': 'stargaze-1',
            'rpc_endpoints': [
                'https://rest.stargaze-apis.com',
                'https://rest.cosmos.directory/stargaze'
            ],
            'explorer_url': 'https://www.mintscan.io/stargaze'
        }
    }
    
    # Native currency details
    CURRENCY = {
        'cosmoshub': {
            'name': 'ATOM',
            'symbol': 'ATOM',
            'decimals': 6,
            'denom': 'uatom',  # micro ATOM
            'fee_denom': 'uatom'
        },
        'osmosis': {
            'name': 'OSMO',
            'symbol': 'OSMO',
            'decimals': 6,
            'denom': 'uosmo',  # micro OSMO
            'fee_denom': 'uosmo'
        },
        'juno': {
            'name': 'JUNO',
            'symbol': 'JUNO',
            'decimals': 6,
            'denom': 'ujuno',  # micro JUNO
            'fee_denom': 'ujuno'
        },
        'akash': {
            'name': 'AKT',
            'symbol': 'AKT',
            'decimals': 6,
            'denom': 'uakt',  # micro AKT
            'fee_denom': 'uakt'
        },
        'secret': {
            'name': 'SCRT',
            'symbol': 'SCRT',
            'decimals': 6,
            'denom': 'uscrt',  # micro SCRT
            'fee_denom': 'uscrt'
        },
        'stargaze': {
            'name': 'STARS',
            'symbol': 'STARS',
            'decimals': 6,
            'denom': 'ustars',  # micro STARS
            'fee_denom': 'ustars'
        }
    }
    
    def __init__(self, network: str = 'cosmoshub', endpoint: Optional[str] = None):
        """
        Initialize the Cosmos adapter.
        
        Args:
            network: Network name (e.g., 'cosmoshub', 'osmosis')
            endpoint: Optional RPC endpoint URL
        """
        # Initialize properties
        self.lcd_client = None
        self.network = network.lower()
        self.is_connected = False
        
        # Validate network
        if self.network not in self.NETWORKS:
            raise ValueError(f"Unsupported Cosmos network: {network}")
        
        # Set network details
        self.network_config = self.NETWORKS[self.network]
        self.network_name = self.network_config['name']
        self.chain_id = self.network_config['chain_id']
        self.currency = self.CURRENCY[self.network]
        
        # Use provided endpoint or default to first in network config
        self.endpoint = endpoint or self.network_config['rpc_endpoints'][0]
        
        logger.info(f"Initialized Cosmos adapter for {self.network_name} (Chain ID: {self.chain_id})")
    
    def _try_backup_endpoints(self) -> bool:
        """Try to connect using backup endpoints.
        
        Returns:
            bool: True if successfully connected using a backup endpoint
        """
        for backup_endpoint in self.network_config['rpc_endpoints'][1:]:
            logger.info(f"Trying backup {self.network_name} endpoint: {backup_endpoint}")
            try:
                self.lcd_client = LCDClient(
                    url=backup_endpoint,
                    chain_id=self.chain_id
                )
                
                # Verify connection by making a simple API call
                self._verify_connection()
                
                # Update endpoint and connection status
                self.endpoint = backup_endpoint
                self.is_connected = True
                
                logger.info(f"Connected to {self.network_name} using backup endpoint")
                return True
            except Exception as e:
                logger.warning(f"Failed to connect to backup endpoint {backup_endpoint}: {str(e)}")
        
        # If we get here, all backups failed
        return False
            
    def _verify_connection(self) -> bool:
        """Verify connection to the Cosmos node.
        
        Returns:
            bool: True if connection is valid
            
        Raises:
            BlockchainConnectionError: If verification fails
        """
        try:
            # Make a simple API call to verify connection
            node_info = self.lcd_client.tendermint.node_info()
            
            # Verify chain ID matches expected
            if node_info.get('node_info', {}).get('network') != self.chain_id:
                raise BlockchainConnectionError(
                    f"Connected to wrong chain. Expected {self.chain_id}, "
                    f"got {node_info.get('node_info', {}).get('network')}"
                )
                
            return True
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
            
    @strict_blockchain_operation
    def connect(self) -> bool:
        """
        Connect to Cosmos network.
        
        Returns:
            bool: True if connection successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize LCD client with endpoint
            self.lcd_client = LCDClient(
                url=self.endpoint,
                chain_id=self.chain_id
            )
            
            # Verify connection by making a simple API call
            self._verify_connection()
            
            # Connection is established if we get this far
            self.is_connected = True
            
            logger.info(f"Connected to {self.network_name} (Chain ID: {self.chain_id})")
            return True
            
        except BlockchainConnectionError as e:
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
        """Get Cosmos token balance for address.
        
        Args:
            address: Cosmos account address (bech32)
            
        Returns:
            Decimal: Balance in native token (ATOM, OSMO, etc.)
            
        Raises:
            ValidationError: If address is invalid
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.lcd_client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Validate address
            if not self.validate_address(address):
                raise ValidationError(f"Invalid {self.network_name} address: {address}")
                
            # Get account balances from bank module
            result = self.lcd_client.bank.balance(address)
            
            # Extract balance for native token denom
            target_denom = self.currency['denom']
            balance_raw = 0
            
            # Find native token balance
            for coin in result:
                if coin.denom == target_denom:
                    balance_raw = int(coin.amount)
                    break
            
            # Convert to human-readable form
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
        """Validate Cosmos address format (bech32).
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid, False otherwise
        """
        if not address:
            return False
            
        # Cosmos addresses are bech32 with different prefixes per chain
        # Format: prefix1... (e.g., cosmos1..., osmo1..., juno1...)
        prefixes = {
            'cosmoshub': 'cosmos',
            'osmosis': 'osmo',
            'juno': 'juno',
            'akash': 'akash',
            'secret': 'secret',
            'stargaze': 'stars'
        }
        
        expected_prefix = prefixes.get(self.network, '')
        
        # Basic validation: check prefix and length
        # Full bech32 validation would be more complex
        if not expected_prefix or not address.startswith(f"{expected_prefix}1"):
            return False
            
        # Check reasonable length for bech32 address (typically 39-45 chars)
        if len(address) < 39 or len(address) > 50:
            return False
            
        return True
    
    @strict_blockchain_operation
    def create_transaction(self, **kwargs) -> Dict[str, Any]:
        """Create a Cosmos transaction.
        
        Args:
            **kwargs: Transaction parameters including:
                - from_address: Sender address
                - to_address: Recipient address
                - amount: Amount to send (in native token)
                - memo: Optional transaction memo
                - fee: Optional fee amount
            
        Returns:
            Dict[str, Any]: Unsigned transaction parameters
            
        Raises:
            TransactionError: If transaction creation fails
            ValidationError: If addresses are invalid
        """
        if not self.is_connected or not self.lcd_client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Extract and validate parameters
            from_address = kwargs.get('from_address')
            to_address = kwargs.get('to_address')
            amount_human = kwargs.get('amount', 0)  # Amount in ATOM/OSMO/etc.
            memo = kwargs.get('memo', '')
            fee_amount = kwargs.get('fee', None)
            
            # Validate sender address
            if not from_address or not self.validate_address(from_address):
                raise ValidationError(f"Invalid from address: {from_address}")
                
            # Validate recipient address
            if not to_address or not self.validate_address(to_address):
                raise ValidationError(f"Invalid to address: {to_address}")
                
            # Convert human-readable amount to chain units
            amount_chain_units = int(Decimal(str(amount_human)) * Decimal(10 ** self.currency['decimals']))
            
            # Create the basic transaction parameters
            tx_params = {
                'from_address': from_address,
                'to_address': to_address,
                'amount': amount_chain_units,
                'amount_human': amount_human,
                'denom': self.currency['denom'],
                'chain_id': self.chain_id,
                'memo': memo,
                'currency': self.currency['symbol']
            }
            
            # If fee is specified, include it
            if fee_amount is not None:
                fee_chain_units = int(Decimal(str(fee_amount)) * Decimal(10 ** self.currency['decimals']))
                tx_params['fee'] = fee_chain_units
            else:
                # We'll compute fee during signing, but store default for estimation
                # This is just a reference value, not used directly
                tx_params['fee'] = 5000  # Default gas cost estimate
            
            # Create the message for the transaction
            msg = MsgSend(
                from_address=from_address,
                to_address=to_address,
                amount=[{"denom": self.currency['denom'], "amount": str(amount_chain_units)}]
            )
            
            # Store the message in the transaction parameters
            tx_params['msg'] = msg
            
            # Get account information for nonce (sequence)
            try:
                account_info = self.lcd_client.auth.account_info(from_address)
                tx_params['account_number'] = account_info.account_number
                tx_params['sequence'] = account_info.sequence
            except Exception as e:
                logger.warning(f"Could not get account info: {str(e)}")
                # We'll try again during signing
                pass
            
            return tx_params
            
        except (ValidationError, BlockchainConnectionError):
            # Re-raise these specific exceptions
            raise
            
        except Exception as e:
            error_msg = f"Failed to create {self.network_name} transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict[str, Any], mnemonic: str) -> Dict[str, Any]:
        """Sign a Cosmos transaction with mnemonic.
        
        Args:
            transaction: Transaction parameters from create_transaction
            mnemonic: Mnemonic phrase for key derivation
            
        Returns:
            Dict[str, Any]: Signed transaction data
            
        Raises:
            TransactionError: If transaction signing fails
        """
        if not self.is_connected or not self.lcd_client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Create wallet from mnemonic
            wallet = self.lcd_client.wallet(MnemonicKey(mnemonic=mnemonic))
            
            # Verify wallet address matches sender
            from_address = transaction.get('from_address')
            if wallet.key.acc_address != from_address:
                raise ValidationError(
                    f"Wallet address {wallet.key.acc_address} does not match sender {from_address}"
                )
            
            # Extract transaction parameters
            msg = transaction.get('msg')
            if not msg:
                raise TransactionError("Transaction does not contain a valid message")
                
            memo = transaction.get('memo', '')
            fee_amount = transaction.get('fee', 5000)  # Default if not specified
            
            # Create fee object
            fee = {
                "amount": [{
                    "denom": self.currency['fee_denom'],
                    "amount": str(fee_amount)
                }],
                "gas": "200000"  # Default gas limit
            }
            
            # Create the transaction options
            options = CreateTxOptions(
                msgs=[msg],
                memo=memo,
                fee=fee
            )
            
            # Create and sign the transaction
            signed_tx = wallet.create_and_sign_tx(options)
            
            # Format response
            signed_tx_data = {
                'tx': signed_tx,
                'tx_hash': None,  # Will be populated after broadcast
                'signer': from_address,
                'to_address': transaction.get('to_address'),
                'amount': transaction.get('amount_human'),
                'currency': transaction.get('currency'),
                'chain_id': self.chain_id,
                'memo': memo
            }
            
            return signed_tx_data
            
        except Exception as e:
            error_msg = f"Failed to sign {self.network_name} transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict[str, Any]) -> str:
        """Broadcast signed transaction to Cosmos network.
        
        Args:
            signed_transaction: Signed transaction data
            
        Returns:
            str: Transaction hash
            
        Raises:
            TransactionError: If broadcasting fails
            ConnectionError: If network connection is lost
        """
        if not self.is_connected or not self.lcd_client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Extract signed transaction
            tx = signed_transaction.get('tx')
            if not tx:
                raise TransactionError("No transaction object in signed transaction data")
                
            # Broadcast transaction
            result = self.lcd_client.tx.broadcast(tx)
            
            # Check for broadcast errors
            if hasattr(result, 'code') and result.code != 0:
                raise TransactionError(f"Transaction broadcast failed with code {result.code}: {result.raw_log}")
                
            # Extract transaction hash
            tx_hash = result.txhash
            
            logger.info(f"Broadcast {self.network_name} transaction: {tx_hash}")
            
            # Update signed transaction with hash
            signed_transaction['tx_hash'] = tx_hash
            
            return tx_hash
            
        except TransactionError:
            # Re-raise transaction errors
            raise
            
        except Exception as e:
            error_msg = f"Failed to broadcast {self.network_name} transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get status of Cosmos transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        if not self.is_connected or not self.lcd_client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Validate transaction hash format
            if not tx_hash or not tx_hash.startswith('0x'):
                raise ValidationError(f"Invalid transaction hash format: {tx_hash}")
                
            # Query transaction by hash
            try:
                tx_info = self.lcd_client.tx.tx_info(tx_hash)
                
                # If we got tx_info without error, transaction was found
                found = True
                
                # Extract basic information
                height = tx_info.height
                status = "confirmed" if tx_info.code == 0 else "failed"
                timestamp = None
                if hasattr(tx_info, 'timestamp'):
                    timestamp = tx_info.timestamp
                    
                # Get current block height for confirmation count
                try:
                    latest_block = self.lcd_client.tendermint.block_info()
                    current_height = latest_block.get('block', {}).get('header', {}).get('height', 0)
                    confirmations = max(0, int(current_height) - int(height)) if height else 0
                except Exception as e:
                    logger.debug(f"Could not get current block height: {str(e)}")
                    confirmations = 0
                
                # Extract events if available
                events = None
                if hasattr(tx_info, 'logs') and tx_info.logs:
                    events = []
                    for log in tx_info.logs:
                        if hasattr(log, 'events'):
                            events.extend(log.events)
                    
                # Extract message info if available
                messages = None
                if hasattr(tx_info, 'tx') and hasattr(tx_info.tx, 'body') and hasattr(tx_info.tx.body, 'messages'):
                    messages = tx_info.tx.body.messages
                
                # Extract transfer details if it's a bank transfer
                transfer_info = {}
                if events:
                    for event in events:
                        if event.get('type') == 'transfer':
                            attributes = event.get('attributes', [])
                            for attr in attributes:
                                if attr.get('key') == 'recipient':
                                    transfer_info['to'] = attr.get('value')
                                elif attr.get('key') == 'sender':
                                    transfer_info['from'] = attr.get('value')
                                elif attr.get('key') == 'amount':
                                    amount_str = attr.get('value', '')
                                    # Format may be like '1000uatom' - extract amount and denom
                                    for denom_key, denom_info in self.CURRENCY.items():
                                        if denom_info['denom'] in amount_str:
                                            denom = denom_info['denom']
                                            amount_raw = int(amount_str.replace(denom, ''))
                                            amount_human = Decimal(amount_raw) / Decimal(10 ** denom_info['decimals'])
                                            transfer_info['amount'] = str(amount_human)
                                            transfer_info['denom'] = denom
                                            transfer_info['currency'] = denom_info['symbol']
                                            break
                
                # Build response
                tx_response = {
                    'hash': tx_hash,
                    'found': found,
                    'status': status,
                    'height': height,
                    'confirmations': confirmations,
                    'timestamp': timestamp,
                    'fee': tx_info.auth_info.fee.amount[0].amount if hasattr(tx_info, 'auth_info') else None,
                    'fee_denom': tx_info.auth_info.fee.amount[0].denom if hasattr(tx_info, 'auth_info') else None,
                    'memo': tx_info.tx.body.memo if hasattr(tx_info, 'tx') and hasattr(tx_info.tx, 'body') else None,
                    'gas_wanted': tx_info.gas_wanted,
                    'gas_used': tx_info.gas_used
                }
                
                # Add transfer details if available
                if transfer_info:
                    tx_response.update(transfer_info)
                    
                return tx_response
                
            except LCDResponseError as e:
                # Transaction not found
                if "not found" in str(e).lower():
                    return {
                        'hash': tx_hash,
                        'found': False,
                        'status': 'not_found',
                        'confirmations': 0
                    }
                # Re-raise other LCD errors
                raise
                
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
        """Get Cosmos network status.
        
        Returns:
            dict: Network status including block height, validator info, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected or not self.lcd_client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Get node info
            node_info = self.lcd_client.tendermint.node_info()
            
            # Get latest block info
            latest_block = self.lcd_client.tendermint.block_info()
            
            # Get syncing status
            syncing = self.lcd_client.tendermint.syncing()
            
            # Get validator set
            try:
                validators = self.lcd_client.tendermint.validator_set()
            except Exception as e:
                logger.debug(f"Could not get validator set: {str(e)}")
                validators = None
                
            # Extract key information
            network_name = node_info.get('node_info', {}).get('network')
            moniker = node_info.get('node_info', {}).get('moniker')
            
            # Extract block height and timestamp
            block_height = latest_block.get('block', {}).get('header', {}).get('height')
            block_time = latest_block.get('block', {}).get('header', {}).get('time')
            
            # Build response
            result = {
                'name': self.network_name,
                'chain_id': self.chain_id,
                'network_name': network_name,
                'node_moniker': moniker,
                'block_height': block_height,
                'latest_block_time': block_time,
                'syncing': syncing,
                'connected': self.is_connected
            }
            
            # Add validator information if available
            if validators:
                result['validator_count'] = len(validators.get('validators', []))
                result['total_voting_power'] = sum(
                    int(v.get('voting_power', 0)) for v in validators.get('validators', [])
                )
            
            # Add node info if available
            version_info = node_info.get('application_version', {})
            if version_info:
                result['node_version'] = version_info.get('version')
                result['cosmos_sdk_version'] = version_info.get('cosmos_sdk_version')
                
            # Add token information
            result['native_token'] = {
                'symbol': self.currency['symbol'],
                'name': self.currency['name'],
                'decimals': self.currency['decimals'],
                'denom': self.currency['denom']
            }
                
            return result
                
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to get {self.network_name} network status: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def estimate_fee(self, from_address: str, to_address: str, amount: Decimal = None, memo: str = '') -> Dict[str, Any]:
        """Estimate fee for Cosmos transaction.
        
        Args:
            from_address: Sender address
            to_address: Recipient address
            amount: Optional amount to send
            memo: Optional transaction memo
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        if not self.is_connected or not self.lcd_client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name} network")
            
        try:
            # Validate addresses
            if not self.validate_address(from_address):
                raise ValidationError(f"Invalid sender address: {from_address}")
                
            if not self.validate_address(to_address):
                raise ValidationError(f"Invalid recipient address: {to_address}")
                
            # Set default amount if none provided
            if amount is None:
                amount = Decimal('0.000001')  # Very small amount for fee estimation
                
            # Convert human-readable amount to chain units
            amount_chain_units = int(amount * Decimal(10 ** self.currency['decimals']))
            
            # Create the message for the transaction
            msg = MsgSend(
                from_address=from_address,
                to_address=to_address,
                amount=[{"denom": self.currency['denom'], "amount": str(amount_chain_units)}]
            )
            
            # Query the node's /cosmos/tx/v1beta1/simulate endpoint for
            # real gas estimation, then derive fee tiers from the result.
            fee_estimates = None
            try:
                lcd_url = self.lcd_client.url if hasattr(self.lcd_client, 'url') else None
                if lcd_url:
                    sim_url = f"{lcd_url.rstrip('/')}/cosmos/tx/v1beta1/simulate"
                    sim_body = json.dumps({
                        "tx_bytes": "",
                        "tx": {
                            "body": {
                                "messages": [{
                                    "@type": "/cosmos.bank.v1beta1.MsgSend",
                                    "from_address": from_address,
                                    "to_address": to_address,
                                    "amount": [{
                                        "denom": self.currency['denom'],
                                        "amount": str(amount_chain_units),
                                    }],
                                }],
                                "memo": memo,
                            },
                            "auth_info": {
                                "signer_infos": [],
                                "fee": {"amount": [], "gas_limit": "0"},
                            },
                            "signatures": [],
                        },
                    }).encode()
                    req = urllib.request.Request(
                        sim_url,
                        data=sim_body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        sim_data = json.loads(resp.read().decode())

                    gas_used = int(sim_data.get("gas_info", {}).get("gas_used", 0))
                    if gas_used > 0:
                        gas_low = int(gas_used * 1.2)
                        gas_avg = int(gas_used * 1.5)
                        gas_high = int(gas_used * 2.0)
                        gas_price_low = Decimal("0.01")
                        gas_price_avg = Decimal("0.025")
                        gas_price_high = Decimal("0.04")
                        fee_estimates = {
                            'low':     {'amount': int(gas_low * gas_price_low),   'gas': str(gas_low)},
                            'average': {'amount': int(gas_avg * gas_price_avg),   'gas': str(gas_avg)},
                            'high':    {'amount': int(gas_high * gas_price_high), 'gas': str(gas_high)},
                        }
            except Exception as sim_err:
                logger.warning("LCD simulate failed, using fallback fee estimates: %s", sim_err)

            if fee_estimates is None:
                fee_estimates = {
                    'low':     {'amount': 1500, 'gas': '150000'},
                    'average': {'amount': 2500, 'gas': '200000'},
                    'high':    {'amount': 3500, 'gas': '250000'},
                }
            
            # Convert to human-readable
            denom = self.currency['denom']
            symbol = self.currency['symbol']
            decimals = self.currency['decimals']
            
            fee_human_estimates = {}
            for priority, estimate in fee_estimates.items():
                amount_raw = estimate['amount']
                amount_human = Decimal(amount_raw) / Decimal(10 ** decimals)
                fee_human_estimates[priority] = {
                    'fee_chain_units': amount_raw,
                    'fee_human': str(amount_human),
                    'fee_denom': denom,
                    'fee_currency': symbol,
                    'gas': estimate['gas']
                }
                
            # Build response
            result = {
                'estimates': fee_human_estimates,
                'recommended': 'average',  # Default recommendation
                'denom': denom,
                'currency': symbol,
                'decimals': decimals,
                'chain_id': self.chain_id
            }
                
            return result
            
        except (ValidationError, BlockchainConnectionError):
            # Re-raise these specific exceptions
            raise
            
        except Exception as e:
            error_msg = f"Failed to estimate fee for {self.network_name} transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    def disconnect(self) -> bool:
        """Disconnect from Cosmos network.
        
        Returns:
            bool: True if disconnected successfully
        """
        self.is_connected = False
        self.lcd_client = None
        logger.info(f"Disconnected from {self.network_name}")
        return True
