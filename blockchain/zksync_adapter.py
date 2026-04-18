#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
zkSync blockchain adapter implementation.
Native, no-fallback adapter for zkSync blockchain integration.
"""

import os
import json
import time
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
import requests

# Import blockchain base components
from blockchain.base_adapter import BlockchainAdapter, strict_blockchain_operation
from blockchain.exceptions import (
    BlockchainConnectionError,
    TransactionError,
    ValidationError,
    WalletError
)

# Import Ethereum components for compatibility
from blockchain.ethereum_adapter import EthereumAdapter

# Import zkSync specific libraries
try:
    from zksync2.core.types import EthBlockParams
    from zksync2.module.module_builder import ZkSyncBuilder
    from zksync2.provider.eth_provider import EthereumProvider
    from zksync2.signer.eth_signer import PrivateKeyEthSigner
    from zksync2.transaction.transaction712 import Transaction712
    from eth_account import Account
    from eth_account.signers.local import LocalAccount
    from eth_utils import to_checksum_address
    
    ZKSYNC_AVAILABLE = True
except ImportError:
    ZKSYNC_AVAILABLE = False
    
# Import logging
import logging
logger = logging.getLogger(__name__)


class ZkSyncAdapter(BlockchainAdapter):
    """Native zkSync blockchain adapter.
    
    Implements all required blockchain operations for zkSync
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'zkSync Era Mainnet',
            'rpc_url': 'https://mainnet.era.zksync.io',
            'chain_id': 324,
            'explorer_url': 'https://explorer.zksync.io',
            'eth_network': 'mainnet'
        },
        'testnet': {
            'name': 'zkSync Era Testnet',
            'rpc_url': 'https://testnet.era.zksync.dev',
            'chain_id': 280,
            'explorer_url': 'https://goerli.explorer.zksync.io',
            'eth_network': 'goerli'
        },
        'sepolia': {
            'name': 'zkSync Era Sepolia Testnet',
            'rpc_url': 'https://sepolia.era.zksync.dev',
            'chain_id': 300,
            'explorer_url': 'https://sepolia.explorer.zksync.io',
            'eth_network': 'sepolia'
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'ETH': {
            'name': 'Ethereum',
            'symbol': 'ETH',
            'decimals': 18,
            'is_native': True
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize zkSync adapter.
        
        Args:
            network: Network name ('mainnet', 'testnet', or 'sepolia')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid or zkSync SDK is unavailable
        """
        if not ZKSYNC_AVAILABLE:
            raise ValidationError("zkSync SDK is not available. "
                                 "Install with 'pip install zksync2'")
        
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid zkSync network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.rpc_url = self.NETWORKS[network]['rpc_url']
        self.chain_id = self.NETWORKS[network]['chain_id']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.eth_network = self.NETWORKS[network]['eth_network']
        
        # Set connection state
        self.is_connected = False
        self.provider = None
        self.eth_web3 = None
        
        # Account management
        self.account = None
        self.private_key = None
        self.address = None
        
        # Ethereum L1 provider
        self.eth_provider = None
        self.signer = None
        
        # Override config if provided
        if config:
            if 'rpc_url' in config:
                self.rpc_url = config['rpc_url']
                
            if 'private_key' in config:
                self.private_key = config['private_key']
                
            if 'eth_rpc_url' in config:
                self.eth_rpc_url = config['eth_rpc_url']
            else:
                self.eth_rpc_url = None
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        account_info = f", Account: {self.address}" if self.address else ""
        return f"zkSync Adapter ({self.network_name}) - {connection_status}{account_info}"
        
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/tx/{{txid}}"
        
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/address/{{address}}"
        
    def _verify_connection(self) -> bool:
        """Verify connection to zkSync network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.provider:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Check if provider is responsive
            block_number = self.provider.get_block_number()
            if block_number is None:
                raise BlockchainConnectionError(f"Invalid response from {self.network_name}")
                
            return True
        except Exception as e:
            self.is_connected = False
            error_msg = f"Connection to {self.network_name} failed: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to zkSync network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Create provider
            zk_builder = ZkSyncBuilder.build_from_rpc_url(
                network=self.eth_network,
                zksync_rpc_url=self.rpc_url,
                eth_rpc_url=self.eth_rpc_url
            )
            self.provider = zk_builder.zksync_provider
            self.eth_web3 = self.provider.eth_web3
            
            # Initialize account if private key is available
            if self.private_key:
                try:
                    # Create account from private key
                    self.account = Account.from_key(self.private_key)
                    self.address = self.account.address
                    
                    # Create signer
                    self.signer = PrivateKeyEthSigner(
                        self.account,
                        self.chain_id
                    )
                    
                    logger.info(f"Initialized account: {self.address}")
                except Exception as e:
                    logger.warning(f"Failed to initialize account: {str(e)}")
                    self.private_key = None
                    self.account = None
                    self.address = None
                    self.signer = None
            
            # Verify connection by getting chain ID
            chain_id = self.provider.chain_id
            
            if chain_id != self.chain_id:
                logger.warning(f"Chain ID mismatch: expected {self.chain_id}, got {chain_id}")
            
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}, chain ID: {chain_id}")
            return True
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from zkSync network.
        
        Returns:
            bool: True if disconnected successfully
        """
        try:
            # Reset connection state
            self.provider = None
            self.eth_web3 = None
            self.is_connected = False
            logger.info(f"Disconnected from {self.network_name}")
            return True
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            return False
            
    def validate_address(self, address: str) -> bool:
        """Validate Ethereum address format.
        
        Args:
            address: Ethereum address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        # We use Ethereum address validation since zkSync uses Ethereum addresses
        try:
            if not address.startswith('0x') or len(address) != 42:
                return False
                
            # Try to convert to checksum address
            to_checksum_address(address)
            return True
        except Exception:
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate private key format.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        try:
            # Try to create an account with the private key
            if private_key.startswith('0x'):
                Account.from_key(private_key)
            else:
                Account.from_key('0x' + private_key)
            return True
        except Exception:
            return False
