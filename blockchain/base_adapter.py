#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Kingdom AI - Blockchain Base Adapter

This module defines the base adapter interface that all blockchain implementations must follow.
Enforces strict, no-fallback native blockchain support across all supported chains.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, TypeVar, Generic

# Set up logger
logger = logging.getLogger(__name__)

T = TypeVar('T')  # Transaction type - varies by blockchain

class BlockchainError(Exception):
    """Base exception for all blockchain operations."""
    pass
    
class ConnectionError(BlockchainError):
    """Error indicating blockchain connection failure."""
    pass
    
class TransactionError(BlockchainError):
    """Error in transaction creation, signing, or broadcasting."""
    pass

class ValidationError(BlockchainError):
    """Error in data validation."""
    pass

class BlockchainAdapter(ABC, Generic[T]):
    """Base adapter class for all blockchain implementations.
    
    All blockchain implementations must inherit from this class and implement
    all abstract methods. This ensures consistent behavior and error handling
    across all blockchain integrations.
    
    IMPORTANT: Kingdom AI enforces strict no-fallback policy for all blockchain operations.
    If any critical operation fails, the system must halt or properly notify the user.
    """
    
    def __init__(self, network_name: str, chain_id: Optional[int] = None):
        """Initialize blockchain adapter.
        
        Args:
            network_name: Name of the blockchain network
            chain_id: Optional chain ID for networks that use it
        """
        self.network_name = network_name
        self.chain_id = chain_id
        self.is_connected = False
        self.last_block = None
        self.last_status = None
        
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to blockchain network.
        
        Returns:
            bool: True if connected successfully, False otherwise
        
        Raises:
            ConnectionError: If connection fails and no fallback is available
        """
        pass
        
    @abstractmethod
    def get_balance(self, address: str, token_address: Optional[str] = None) -> float:
        """Get balance for address.
        
        Args:
            address: The address to check
            token_address: Optional token address for token balances
            
        Returns:
            float: Balance amount
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        pass
        
    @abstractmethod
    def create_transaction(self, **kwargs) -> T:
        """Create a blockchain-specific transaction.
        
        Args:
            **kwargs: Transaction parameters (blockchain-specific)
            
        Returns:
            T: Blockchain-specific transaction object
            
        Raises:
            TransactionError: If transaction creation fails
        """
        pass
        
    @abstractmethod
    def sign_transaction(self, transaction: T, private_key: str) -> T:
        """Sign transaction with private key.
        
        Args:
            transaction: The transaction to sign
            private_key: Private key to sign with (format varies by blockchain)
            
        Returns:
            T: Signed transaction
            
        Raises:
            TransactionError: If transaction signing fails
        """
        pass
        
    @abstractmethod
    def broadcast_transaction(self, signed_transaction: T) -> str:
        """Broadcast signed transaction to network.
        
        Args:
            signed_transaction: Signed transaction to broadcast
            
        Returns:
            str: Transaction hash or ID
            
        Raises:
            TransactionError: If broadcasting fails
            ConnectionError: If network connection is lost
        """
        pass
        
    @abstractmethod
    def validate_address(self, address: str) -> bool:
        """Validate address format.
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid, False otherwise
        """
        pass
        
    @abstractmethod
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get status of transaction.
        
        Args:
            tx_hash: Transaction hash or ID
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        pass
    
    @abstractmethod
    def get_network_status(self) -> Dict[str, Any]:
        """Get network status.
        
        Returns:
            dict: Network status including block height, sync state, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        pass
    
    @abstractmethod
    def estimate_fee(self, transaction: T) -> Dict[str, Any]:
        """Estimate fee for transaction.
        
        Args:
            transaction: Transaction to estimate fee for
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        pass
    
    def disconnect(self) -> bool:
        """Disconnect from blockchain network.
        
        Returns:
            bool: True if disconnected successfully, False otherwise
        """
        self.is_connected = False
        return True

# Decorator for strict blockchain operations
def strict_blockchain_operation(func):
    """Decorator for enforcing strict blockchain operations with no fallbacks.
    
    SOTA 2026 FIX: Do NOT SystemExit on blockchain errors -- a single adapter
    failure (e.g. Solana) must not crash the entire Kingdom AI system.
    Re-raise the BlockchainError so the caller can handle it gracefully.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BlockchainError as e:
            logger.critical(f"Critical blockchain error: {str(e)}")
            # Re-raise so the caller can handle gracefully -- do NOT SystemExit
            raise
    return wrapper
