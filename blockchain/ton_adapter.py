#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TON (The Open Network) blockchain adapter implementation.
Native, no-fallback adapter for TON blockchain integration.
"""

import os
import json
import time
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
import base64
import requests

# Import blockchain base components
from blockchain.base_adapter import BlockchainAdapter, strict_blockchain_operation
from blockchain.exceptions import (
    BlockchainConnectionError,
    TransactionError,
    ValidationError,
    WalletError
)

# Import TON specific libraries
try:
    import pytoniq
    from pytoniq.address import Address as TonAddress
    from pytoniq.client import TonlibClient, LiteClient
    from pytoniq.wallet import WalletV4R2 as TonWallet
    from pytoniq.boc import Cell
    from pytoniq.utils.tlb import Coins
    
    TON_AVAILABLE = True
except ImportError:
    TON_AVAILABLE = False
    
# Import logging
import logging
logger = logging.getLogger(__name__)


class TonAdapter(BlockchainAdapter):
    """Native TON (The Open Network) blockchain adapter.
    
    Implements all required blockchain operations for TON
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'TON Mainnet',
            'endpoint': 'https://toncenter.com/api/v2/jsonRPC',
            'explorer_url': 'https://tonscan.org',
            'lite_servers': [
                {"ip": 1137658550, "port": 4924, "id": {"key": "peJTw/arlRfssgTuf9BMypJzqOi7SXEqSPSWiEw2U1M="}}
            ]
        },
        'testnet': {
            'name': 'TON Testnet',
            'endpoint': 'https://testnet.toncenter.com/api/v2/jsonRPC',
            'explorer_url': 'https://testnet.tonscan.org',
            'lite_servers': [
                {"ip": 1583033227, "port": 13833, "id": {"key": "6PGkPQSbyFp12esf1NqmDOaLoFA8j7P1bvnKaVzL6qI="}}
            ]
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'TON': {
            'name': 'Toncoin',
            'symbol': 'TON',
            'decimals': 9,
            'is_native': True
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize TON adapter.
        
        Args:
            network: Network name ('mainnet' or 'testnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid or TON SDK is unavailable
        """
        if not TON_AVAILABLE:
            raise ValidationError("TON SDK is not available. "
                                 "Install with 'pip install pytoniq'")
        
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid TON network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.endpoint = self.NETWORKS[network]['endpoint']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.lite_servers = self.NETWORKS[network]['lite_servers']
        
        # Set API key
        self.api_key = None
        
        # Set connection state
        self.is_connected = False
        self.client = None
        self.lite_client = None
        
        # Account management
        self.wallet = None
        self.private_key = None
        self.public_key = None
        self.address = None
        self.mnemonics = None
        
        # Override config if provided
        if config:
            if 'endpoint' in config:
                self.endpoint = config['endpoint']
                
            if 'api_key' in config:
                self.api_key = config['api_key']
                
            if 'private_key' in config:
                self.private_key = config['private_key']
                
            if 'mnemonics' in config:
                self.mnemonics = config['mnemonics']
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        account_info = f", Account: {self.address}" if self.address else ""
        return f"TON Adapter ({self.network_name}) - {connection_status}{account_info}"
        
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/tx/{{txid}}"
        
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/address/{{address}}"
