#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Celo blockchain adapter implementation.
Native, no-fallback adapter for Celo blockchain integration.
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

# Import Celo specific libraries
try:
    from web3 import Web3
    # Use native middleware implementation - no fallbacks allowed
    # Using kingdomweb3_v2 for blockchain connectivity
    from kingdomweb3_v2 import rpc_manager, get_network_config
    from eth_account import Account
    from eth_utils import to_checksum_address
    
    # Import Celo specific components
    import celo_sdk
    from celo_sdk.kit import Kit
    from celo_sdk.celo_account.account import Account as CeloAccount
    from celo_sdk.contracts.base_wrapper import BaseWrapper
    
    CELO_AVAILABLE = True
except ImportError:
    CELO_AVAILABLE = False
    
# Import logging
import logging
logger = logging.getLogger(__name__)


class CeloAdapter(BlockchainAdapter):
    """Native Celo blockchain adapter.
    
    Implements all required blockchain operations for Celo
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Celo Mainnet',
            'rpc_url': 'https://forno.celo.org',
            'chain_id': 42220,
            'explorer_url': 'https://explorer.celo.org',
            'fee_currency': None  # Use native CELO
        },
        'alfajores': {
            'name': 'Celo Alfajores Testnet',
            'rpc_url': 'https://alfajores-forno.celo-testnet.org',
            'chain_id': 44787,
            'explorer_url': 'https://alfajores-blockscout.celo-testnet.org',
            'fee_currency': None  # Use native CELO
        },
        'baklava': {
            'name': 'Celo Baklava Testnet',
            'rpc_url': 'https://baklava-forno.celo-testnet.org',
            'chain_id': 62320,
            'explorer_url': 'https://baklava-blockscout.celo-testnet.org',
            'fee_currency': None  # Use native CELO
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'CELO': {
            'name': 'Celo',
            'symbol': 'CELO',
            'decimals': 18,
            'is_native': True
        },
        'cUSD': {
            'name': 'Celo Dollar',
            'symbol': 'cUSD',
            'decimals': 18,
            'is_native': False
        },
        'cEUR': {
            'name': 'Celo Euro',
            'symbol': 'cEUR',
            'decimals': 18,
            'is_native': False
        }
    }
    
    # Celo stable token addresses
    STABLE_TOKENS = {
        'mainnet': {
            'cUSD': '0x765DE816845861e75A25fCA122bb6898B8B1282a',
            'cEUR': '0xD8763CBa276a3738E6DE85b4b3bF5FDed6D6cA73',
            'cREAL': '0xe8537a3d056DA446677B9E9d6c5dB704EaAb4787'
        },
        'alfajores': {
            'cUSD': '0x874069Fa1Eb16D44d622F2e0Ca25eeA172369bC1',
            'cEUR': '0x10c892A6EC43a53E45D0B916B4b7D383B1b78C0F',
            'cREAL': '0xC5375c73a627105eb4DF00867717F6e301966C32'
        },
        'baklava': {
            'cUSD': '0x62492A644A588FD904270BeD06ad52B9abfEA1aE',
            'cEUR': '0xf9ecE301247aD2CE21894941830A2470f4E774ca',
            'cREAL': '0x4d8F2962F2cDF9e95993083B642c4bE15436f9C6'
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Celo adapter.
        
        Args:
            network: Network name ('mainnet', 'alfajores', or 'baklava')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid or Celo SDK is unavailable
        """
        if not CELO_AVAILABLE:
            raise ValidationError("Celo SDK is not available. "
                                 "Install with 'pip install celo-sdk'")
        
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Celo network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.rpc_url = self.NETWORKS[network]['rpc_url']
        self.chain_id = self.NETWORKS[network]['chain_id']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.fee_currency = self.NETWORKS[network]['fee_currency']
        
        # Set connection state
        self.is_connected = False
        self.kit = None
        self.web3 = None
        
        # Account management
        self.account = None
        self.private_key = None
        self.address = None
        
        # Token contracts
        self.stable_tokens = self.STABLE_TOKENS[network]
        self.token_contracts = {}
        
        # Override config if provided
        if config:
            if 'rpc_url' in config:
                self.rpc_url = config['rpc_url']
                
            if 'private_key' in config:
                self.private_key = config['private_key']
                
            if 'fee_currency' in config:
                self.fee_currency = config['fee_currency']
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        account_info = f", Account: {self.address}" if self.address else ""
        return f"Celo Adapter ({self.network_name}) - {connection_status}{account_info}"
        
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/tx/{{txid}}"
        
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/address/{{address}}"
        
    def _verify_connection(self) -> bool:
        """Verify connection to Celo network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.kit:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Check if web3 is responsive
            block_number = self.web3.eth.block_number
            return True
        except Exception as e:
            self.is_connected = False
            error_msg = f"Connection to {self.network_name} failed: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
