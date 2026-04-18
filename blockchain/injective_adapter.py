#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Injective blockchain adapter implementation.
Native, no-fallback adapter for Injective blockchain integration.
"""

import os
import json
import time
import hashlib
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
import requests
import base64

# Import blockchain base components
from blockchain.base_adapter import BlockchainAdapter, strict_blockchain_operation
from blockchain.exceptions import (
    BlockchainConnectionError,
    TransactionError,
    ValidationError,
    WalletError
)

# Import Injective specific libraries
try:
    from pyinjective.composer import Composer as InjectiveComposer
    from pyinjective.async_client import AsyncClient as InjectiveClient
    from pyinjective.transaction import Transaction as InjectiveTransaction
    from pyinjective.wallet import PrivateKey as InjectivePrivateKey, PublicKey as InjectivePublicKey, Address as InjectiveAddress
except ImportError:
    InjectiveClient = None
    InjectiveTransaction = None
    InjectivePrivateKey = None
    InjectivePublicKey = None
    InjectiveAddress = None

INJECTIVE_AVAILABLE = InjectiveClient is not None
    
# Import logging
import logging
logger = logging.getLogger(__name__)


class InjectiveAdapter(BlockchainAdapter):
    """Native Injective blockchain adapter.
    
    Implements all required blockchain operations for Injective
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Injective Mainnet',
            'chain_id': 'injective-1',
            'lcd_endpoint': 'https://lcd.injective.network',
            'grpc_endpoint': 'grpc.injective.network:443',
            'explorer_url': 'https://explorer.injective.network',
            'fee_denom': 'inj'
        },
        'testnet': {
            'name': 'Injective Testnet',
            'chain_id': 'injective-888',
            'lcd_endpoint': 'https://lcd.testnet.injective.network',
            'grpc_endpoint': 'grpc.testnet.injective.network:443',
            'explorer_url': 'https://testnet.explorer.injective.network',
            'fee_denom': 'inj'
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'INJ': {
            'name': 'Injective',
            'symbol': 'INJ',
            'decimals': 18,
            'is_native': True
        }
    }
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Injective adapter.
        
        Args:
            network: Network name ('mainnet' or 'testnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid or Injective SDK is unavailable
        """
        if not INJECTIVE_AVAILABLE:
            raise ValidationError("Injective SDK is not available. "
                                 "Install with 'pip install pyinjective'")
        
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Injective network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.chain_id = self.NETWORKS[network]['chain_id']
        self.lcd_endpoint = self.NETWORKS[network]['lcd_endpoint']
        self.grpc_endpoint = self.NETWORKS[network]['grpc_endpoint']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        self.fee_denom = self.NETWORKS[network]['fee_denom']
        
        # Set connection state
        self.is_connected = False
        self.client = None
        self.composer = None
        
        # Account management
        self.account = None
        self.private_key = None
        self.address = None
        self.public_key = None
        
        # Override config if provided
        if config:
            if 'lcd_endpoint' in config:
                self.lcd_endpoint = config['lcd_endpoint']
                
            if 'grpc_endpoint' in config:
                self.grpc_endpoint = config['grpc_endpoint']
                
            if 'private_key' in config:
                self.private_key = config['private_key']
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        account_info = f", Account: {self.address}" if self.address else ""
        return f"Injective Adapter ({self.network_name}) - {connection_status}{account_info}"
        
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/transaction/{{txid}}"
        
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/account/{{address}}"
        
    def _verify_connection(self) -> bool:
        """Verify connection to Injective network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.client:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Check if client is responsive (will be implemented in async connect)
            return True
        except Exception as e:
            self.is_connected = False
            error_msg = f"Connection to {self.network_name} failed: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
