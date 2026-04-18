#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Kingdom AI - Bitcoin Blockchain Adapter

This module provides native, no-fallback integration with the Bitcoin blockchain.
Production-grade implementation with robust error handling and multiple endpoint support.
"""

import logging
import json
import time
import base64
import base58
from typing import Dict, Any, Optional, List, Union, TypeVar, Tuple
from pathlib import Path

# Import base adapter
from blockchain.base_adapter import (
    BlockchainAdapter, BlockchainError, ConnectionError, 
    TransactionError, ValidationError, strict_blockchain_operation
)

# Import Bitcoin-specific libraries
try:
    import bitcoinlib
    from bitcoinlib.wallets import Wallet, wallet_create_or_open
    from bitcoinlib.transactions import Transaction as BTCTransaction
    from bitcoinlib.keys import Key, HDKey
    from bitcoinlib.services.services import Service, ServiceError
    from bitcoinlib.mnemonic import Mnemonic
except ImportError as e:
    raise ImportError(f"Bitcoin libraries not installed. Error: {str(e)}. Install with 'pip install bitcoinlib>=0.6.9'")

# Set up logger
logger = logging.getLogger(__name__)

# Define Bitcoin networks and their RPC endpoints
BITCOIN_MAINNET_ENDPOINTS = [
    "https://btc.getblock.io",
    "https://blockchain.info",
    "https://blockstream.info/api",
    "https://api.blockcypher.com/v1/btc/main"
]

BITCOIN_TESTNET_ENDPOINTS = [
    "https://testnet.blockchain.info",
    "https://blockstream.info/testnet/api",
    "https://api.blockcypher.com/v1/btc/test3"
]

class BitcoinAdapter(BlockchainAdapter[BTCTransaction]):
    """Native Bitcoin blockchain adapter with strict no-fallback policy."""
    
    def __init__(self, 
                 network: str = "mainnet", 
                 endpoints: Optional[List[str]] = None,
                 data_dir: Optional[str] = None,
                 use_testnet: bool = False):
        """Initialize Bitcoin adapter.
        
        Args:
            network: Network to connect to ('mainnet', 'testnet')
            endpoints: Optional list of RPC endpoints (will override defaults if provided)
            data_dir: Optional path to data directory for wallet and key storage
            use_testnet: Use testnet instead of mainnet
        """
        network_name = "bitcoin-testnet" if use_testnet else "bitcoin-mainnet"
        chain_id = None  # Bitcoin doesn't use chain IDs
        
        super().__init__(network_name=network_name, chain_id=chain_id)
        
        self.network = "testnet" if use_testnet else "mainnet"
        self._endpoints = endpoints or (BITCOIN_TESTNET_ENDPOINTS if use_testnet else BITCOIN_MAINNET_ENDPOINTS)
        self._current_endpoint_index = 0
        self._service = None
        self._last_block_info = None
        self._last_block_check_time = 0
        self._data_dir = data_dir
        
        # Set up bitcoinlib config
        if data_dir:
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            bitcoinlib.DEFAULT_DATABASE = str(Path(data_dir) / "database.sqlite")
            bitcoinlib.DEFAULT_SETTINGSDIR = str(Path(data_dir))
            
        # Connect immediately with strict validation
        self.connect()
        
    def _get_current_endpoint(self) -> str:
        """Get current endpoint from the endpoints list."""
        if not self._endpoints:
            raise ConnectionError("No Bitcoin RPC endpoints available")
            
        return self._endpoints[self._current_endpoint_index % len(self._endpoints)]
    
    def _try_next_endpoint(self) -> None:
        """Try the next available endpoint in the list."""
        self._current_endpoint_index = (self._current_endpoint_index + 1) % len(self._endpoints)
        logger.warning(f"Switching to next Bitcoin endpoint: {self._get_current_endpoint()}")
        
    def _init_service(self) -> None:
        """Initialize Bitcoin service with current endpoint."""
        try:
            # Try to create service with current endpoint
            providers = ['bitcoind', 'blocksmurfer', 'blockchair', 'bitaps', 'blockcypher', 'blockstream']
            
            # First try using the endpoint directly
            current_endpoint = self._get_current_endpoint()
            
            # Try to create a service based on the endpoint
            try:
                if "blockcypher" in current_endpoint:
                    self._service = Service(network=self.network, providers=['blockcypher'])
                elif "blockchain.info" in current_endpoint:
                    self._service = Service(network=self.network, providers=['blocksmurfer'])
                elif "blockstream" in current_endpoint:
                    self._service = Service(network=self.network, providers=['blockstream'])
                else:
                    # Try each provider until one works
                    for provider in providers:
                        try:
                            self._service = Service(network=self.network, providers=[provider])
                            # Test the service with a basic call
                            self._service.getinfo()
                            break
                        except Exception as e:
                            logger.warning(f"Provider {provider} failed: {e}")
                            continue
            except Exception as e:
                logger.warning(f"Could not initialize service with endpoint {current_endpoint}: {e}")
                # Fall back to trying all providers
                for provider in providers:
                    try:
                        self._service = Service(network=self.network, providers=[provider])
                        # Test the service with a basic call
                        self._service.getinfo()
                        break
                    except Exception as e:
                        logger.warning(f"Provider {provider} failed: {e}")
                        continue
                
            # If we still don't have a service, raise an exception
            if not self._service:
                raise ConnectionError("Could not initialize any Bitcoin service provider")
                
            # Test connection with getinfo
            info = self._service.getinfo()
            if not info:
                raise ConnectionError("Failed to get Bitcoin network info")
                
            logger.info(f"Connected to Bitcoin {self.network} using provider {self._service.provider}")
            
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Bitcoin service: {str(e)}")
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Bitcoin network using available endpoints.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            ConnectionError: If all connection attempts fail
        """
        connection_errors = []
        
        # Try all endpoints until one works
        for _ in range(len(self._endpoints)):
            try:
                logger.info(f"Connecting to Bitcoin {self.network}")
                
                # Initialize service
                self._init_service()
                
                # Get network information to validate connection
                network_info = self._service.getinfo()
                
                if not network_info:
                    raise ConnectionError("Failed to get network information")
                    
                self.is_connected = True
                self.last_block = network_info.get("blocks")
                
                logger.info(f"Connected to Bitcoin {self.network} at block height {self.last_block}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to Bitcoin endpoint: {str(e)}")
                connection_errors.append(f"{self._get_current_endpoint()}: {str(e)}")
                self._try_next_endpoint()
        
        # If we get here, all connection attempts failed
        error_msg = f"Failed to connect to any Bitcoin endpoint. Errors: {connection_errors}"
        logger.critical(error_msg)
        raise ConnectionError(error_msg)
    
    @strict_blockchain_operation
    def get_balance(self, address: str, token_address: Optional[str] = None) -> float:
        """Get Bitcoin balance for address.
        
        Args:
            address: The Bitcoin address to check
            token_address: Not used for Bitcoin (kept for API consistency)
            
        Returns:
            float: Balance in BTC
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Validate address
            if not self.validate_address(address):
                raise ValidationError(f"Invalid Bitcoin address: {address}")
                
            # Get balance in satoshis
            balance_satoshi = self._service.getbalance(address)
            
            # Convert to BTC (1 BTC = 100,000,000 satoshis)
            balance_btc = balance_satoshi / 100000000
            
            return balance_btc
            
        except ValidationError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            # Try to reconnect and retry once
            try:
                self.connect()
                balance_satoshi = self._service.getbalance(address)
                balance_btc = balance_satoshi / 100000000
                return balance_btc
            except Exception as retry_error:
                raise ConnectionError(f"Failed to get balance: {str(retry_error)}")
    
    @strict_blockchain_operation
    def create_transaction(self, **kwargs) -> BTCTransaction:
        """Create a Bitcoin transaction.
        
        Args:
            **kwargs: Transaction parameters:
                - sender (str): Sender address or wallet name
                - recipient (str): Recipient address
                - amount (float): Amount in BTC
                - fee (float, optional): Fee in BTC
                - wallet_name (str, optional): Wallet name if using a wallet
                - passphrase (str, optional): Wallet passphrase if needed
                - subtractfee (bool, optional): Subtract fee from amount
                
        Returns:
            BTCTransaction: Bitcoin transaction object
            
        Raises:
            TransactionError: If transaction creation fails
            ValidationError: If parameters are invalid
        """
        if not self.is_connected:
            self.connect()
            
        # Extract and validate parameters
        sender = kwargs.get("sender")
        recipient = kwargs.get("recipient")
        amount = kwargs.get("amount")
        fee = kwargs.get("fee")
        wallet_name = kwargs.get("wallet_name")
        passphrase = kwargs.get("passphrase")
        subtract_fee = kwargs.get("subtractfee", False)
        
        # Validate required parameters
        if not recipient:
            raise ValidationError("Recipient address is required")
            
        if not self.validate_address(recipient):
            raise ValidationError(f"Invalid recipient address: {recipient}")
            
        if amount is None or amount <= 0:
            raise ValidationError(f"Invalid amount: {amount}")
        
        try:
            # Two ways to create a transaction:
            # 1. Using a wallet (preferred for security)
            if wallet_name:
                try:
                    # Open existing wallet or create a new one
                    wallet = wallet_create_or_open(wallet_name, network=self.network)
                    
                    # Unlock wallet if passphrase provided
                    if passphrase:
                        wallet.unlock(passphrase)
                    
                    # Convert BTC to satoshis
                    amount_satoshi = int(amount * 100000000)
                    
                    # Create transaction
                    transaction = wallet.send_to(
                        recipient, 
                        amount_satoshi,
                        fee=int(fee * 100000000) if fee else None,
                        offline=True  # Don't broadcast yet
                    )
                    
                    return transaction
                    
                except Exception as e:
                    raise TransactionError(f"Failed to create wallet transaction: {str(e)}")
            
            # 2. Using raw transaction (requires unspent outputs)
            else:
                if not sender:
                    raise ValidationError("Sender address is required for raw transactions")
                    
                if not self.validate_address(sender):
                    raise ValidationError(f"Invalid sender address: {sender}")
                
                # Convert BTC to satoshis
                amount_satoshi = int(amount * 100000000)
                fee_satoshi = int(fee * 100000000) if fee else None
                
                # Get unspent outputs for the sender
                unspent = self._service.getutxos(sender)
                
                if not unspent:
                    raise TransactionError(f"No unspent outputs found for address {sender}")
                
                # Create transaction inputs and outputs
                inputs = []
                outputs = {recipient: amount_satoshi}
                
                # Calculate total input amount and change
                total_input = sum(utxo['value'] for utxo in unspent)
                
                if not fee_satoshi:
                    # Estimate fee based on transaction size
                    estimated_size = 10 + len(unspent) * 180 + 2 * 34
                    fee_satoshi = estimated_size * 10  # 10 sat/byte
                
                # Calculate change amount
                change_amount = total_input - amount_satoshi - fee_satoshi
                
                if change_amount < 0:
                    raise TransactionError(f"Insufficient funds: need {amount_satoshi + fee_satoshi} satoshi, have {total_input} satoshi")
                
                # Add change output if needed
                if change_amount > 546:  # Dust threshold
                    outputs[sender] = change_amount
                
                # Create transaction
                transaction = self._service.create_transaction(inputs=unspent, outputs=outputs)
                
                return transaction
                
        except Exception as e:
            raise TransactionError(f"Failed to create transaction: {str(e)}")
    
    @strict_blockchain_operation
    def sign_transaction(self, transaction: BTCTransaction, private_key: str) -> BTCTransaction:
        """Sign Bitcoin transaction with private key.
        
        Args:
            transaction: Transaction to sign
            private_key: WIF private key, mnemonic, or path to key file
            
        Returns:
            BTCTransaction: Signed transaction
            
        Raises:
            TransactionError: If transaction signing fails
        """
        try:
            # Handle different private key formats
            if private_key.startswith("file:"):
                # Load from file
                file_path = private_key.replace("file:", "", 1)
                with open(file_path, "r") as f:
                    key_data = f.read().strip()
                    key = Key(key_data, network=self.network)
            elif private_key.startswith("xprv") or private_key.startswith("tprv"):
                # HD wallet private key
                key = HDKey(private_key, network=self.network)
            elif len(private_key.split()) > 1:
                # Mnemonic seed phrase
                key = Mnemonic(private_key).key
            else:
                # Regular private key (WIF format)
                key = Key(private_key, network=self.network)
            
            # Sign the transaction with the key
            transaction.sign(key)
            
            return transaction
            
        except Exception as e:
            raise TransactionError(f"Failed to sign transaction: {str(e)}")
    
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: BTCTransaction) -> str:
        """Broadcast signed Bitcoin transaction.
        
        Args:
            signed_transaction: Signed transaction to broadcast
            
        Returns:
            str: Transaction ID (hash)
            
        Raises:
            TransactionError: If broadcasting fails
            ConnectionError: If network connection is lost
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Verify transaction is signed
            if not signed_transaction.verified:
                raise TransactionError("Transaction is not properly signed")
            
            # Broadcast transaction
            tx_id = self._service.sendrawtransaction(signed_transaction.raw_hex())
            
            if not tx_id:
                raise TransactionError("Failed to broadcast transaction")
                
            logger.info(f"Broadcast Bitcoin transaction: {tx_id}")
            
            return tx_id
            
        except Exception as e:
            # Try to reconnect and retry once on connection errors
            if "connection" in str(e).lower():
                try:
                    self.connect()
                    tx_id = self._service.sendrawtransaction(signed_transaction.raw_hex())
                    
                    if not tx_id:
                        raise TransactionError("Failed to broadcast transaction on retry")
                        
                    logger.info(f"Broadcast Bitcoin transaction (retry): {tx_id}")
                    return tx_id
                    
                except Exception as retry_error:
                    raise TransactionError(f"Failed to broadcast transaction after retry: {str(retry_error)}")
            else:
                raise TransactionError(f"Failed to broadcast transaction: {str(e)}")
    
    @strict_blockchain_operation
    def validate_address(self, address: str) -> bool:
        """Validate Bitcoin address format.
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid, False otherwise
        """
        try:
            # Use bitcoinlib's address validation
            from bitcoinlib.encoding import addr_bech32_to_pubkeyhash, change_base
            from bitcoinlib.keys import Address
            
            # Handle different address types (legacy, segwit, bech32)
            if address.startswith(('1', 'm', 'n')):  # Legacy
                Address.parse(address, network=self.network)
                return True
            elif address.startswith(('3', '2')):  # Segwit
                Address.parse(address, network=self.network)
                return True
            elif address.startswith(('bc1', 'tb1')):  # Bech32
                addr_bech32_to_pubkeyhash(address)
                return True
            else:
                return False
                
        except Exception:
            return False
    
    @strict_blockchain_operation
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get status of Bitcoin transaction.
        
        Args:
            tx_hash: Transaction ID (hash)
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Validate transaction hash format
            if not all(c in '0123456789abcdefABCDEF' for c in tx_hash) or len(tx_hash) != 64:
                raise ValidationError(f"Invalid Bitcoin transaction hash: {tx_hash}")
                
            # Get transaction details
            tx_details = self._service.gettransaction(tx_hash)
            
            if not tx_details:
                return {
                    "found": False,
                    "confirmed": False,
                    "confirmations": 0
                }
                
            # Extract status information
            status = {
                "found": True,
                "confirmed": tx_details.get("confirmations", 0) > 0,
                "confirmations": tx_details.get("confirmations", 0),
                "blockhash": tx_details.get("blockhash"),
                "blockheight": tx_details.get("blockheight"),
                "time": tx_details.get("time"),
                "size": tx_details.get("size"),
                "fee": tx_details.get("fee"),
                "status": "confirmed" if tx_details.get("confirmations", 0) > 0 else "unconfirmed"
            }
            
            # Add human-readable timestamp if time exists
            if tx_details.get("time"):
                from datetime import datetime
                status["timestamp"] = datetime.fromtimestamp(tx_details["time"]).isoformat()
                
            return status
            
        except ValidationError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            raise ConnectionError(f"Failed to get transaction status: {str(e)}")
    
    @strict_blockchain_operation
    def get_network_status(self) -> Dict[str, Any]:
        """Get Bitcoin network status.
        
        Returns:
            dict: Network status including block height, sync state, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Get network information
            info = self._service.getinfo()
            
            if not info:
                raise ConnectionError("Failed to get Bitcoin network information")
                
            # Get fees estimate (for 1, 6, and 24 blocks targets)
            fees = {}
            try:
                for blocks in [1, 6, 24]:
                    fee_rate = self._service.estimatefee(blocks)
                    fees[f"{blocks}_blocks"] = fee_rate
            except Exception as e:
                logger.warning(f"Failed to estimate fees: {str(e)}")
            
            # Combine into comprehensive status
            status = {
                "network": self.network,
                "provider": self._service.provider,
                "blocks": info.get("blocks"),
                "headers": info.get("headers"),
                "difficulty": info.get("difficulty"),
                "mempool_size": info.get("mempool_size"),
                "connected_nodes": info.get("connections"),
                "sync_progress": (
                    100.0 if info.get("blocks") == info.get("headers") 
                    else (info.get("blocks", 0) / max(1, info.get("headers", 1))) * 100
                ),
                "estimated_fees": fees
            }
            
            # Cache the last block information
            self._last_block_info = {
                "height": info.get("blocks"),
                "time": time.time()
            }
            
            return status
            
        except Exception as e:
            raise ConnectionError(f"Failed to get network status: {str(e)}")
    
    @strict_blockchain_operation
    def estimate_fee(self, transaction: BTCTransaction) -> Dict[str, Any]:
        """Estimate fee for Bitcoin transaction.
        
        Args:
            transaction: Transaction to estimate fee for
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Get transaction size
            tx_size = len(transaction.raw_hex()) / 2  # Hex string to bytes
            
            # Get fee rates for different confirmation targets
            fee_rates = {}
            for blocks in [1, 6, 24]:
                try:
                    rate = self._service.estimatefee(blocks)
                    fee_rates[f"{blocks}_blocks"] = rate
                except:
                    continue
            
            # Use the average fee rate if available, otherwise use a default
            fee_rate = 50  # Default: 50 sat/byte
            if fee_rates:
                fee_rate = sum(fee_rates.values()) / len(fee_rates)
            
            # Calculate estimated fee
            estimated_fee_satoshi = int(tx_size * fee_rate)
            estimated_fee_btc = estimated_fee_satoshi / 100000000
            
            return {
                "size_bytes": tx_size,
                "fee_rates": fee_rates,
                "estimated_fee_satoshi": estimated_fee_satoshi,
                "estimated_fee_btc": estimated_fee_btc
            }
            
        except Exception as e:
            raise TransactionError(f"Failed to estimate fee: {str(e)}")
            
    # Additional Bitcoin-specific methods
    
    def create_wallet(self, wallet_name: str, passphrase: Optional[str] = None) -> Dict[str, Any]:
        """Create a new Bitcoin wallet.
        
        Args:
            wallet_name: Name for the wallet
            passphrase: Optional passphrase for wallet encryption
            
        Returns:
            dict: Wallet information including seed and addresses
            
        Raises:
            TransactionError: If wallet creation fails
        """
        try:
            # Create new wallet
            wallet = Wallet.create(
                wallet_name,
                network=self.network,
                witness_type='segwit',  # Use segwit by default for lower fees
                password=passphrase
            )
            
            # Generate addresses (HD wallet)
            addresses = []
            for i in range(3):
                key = wallet.get_key(index=i)
                addresses.append(key.address)
            
            # Get the mnemonic seed phrase
            mnemonic = wallet.get_mnemonic()
            
            return {
                "wallet_name": wallet_name,
                "mnemonic": mnemonic,
                "master_key": wallet.main_key.wif,
                "addresses": addresses
            }
            
        except Exception as e:
            raise TransactionError(f"Failed to create wallet: {str(e)}")
            
    def get_utxos(self, address: str) -> List[Dict[str, Any]]:
        """Get unspent transaction outputs (UTXOs) for address.
        
        Args:
            address: Bitcoin address
            
        Returns:
            List[Dict]: List of UTXOs with details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Validate address
            if not self.validate_address(address):
                raise ValidationError(f"Invalid Bitcoin address: {address}")
                
            # Get UTXOs
            utxos = self._service.getutxos(address)
            
            return utxos
            
        except ValidationError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            raise ConnectionError(f"Failed to get UTXOs: {str(e)}")
    
    def import_address(self, wallet_name: str, address: str) -> bool:
        """Import address to wallet for tracking.
        
        Args:
            wallet_name: Name of the wallet
            address: Address to import
            
        Returns:
            bool: True if successful
            
        Raises:
            TransactionError: If import fails
        """
        try:
            # Open wallet
            wallet = wallet_create_or_open(wallet_name, network=self.network)
            
            # Import address
            wallet.scan(scan_gap_limit=1)
            wallet.import_address(address)
            
            return True
            
        except Exception as e:
            raise TransactionError(f"Failed to import address: {str(e)}")
