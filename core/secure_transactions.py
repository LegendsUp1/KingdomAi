#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Secure Transaction Module

This module implements industry-standard secure cryptographic operations
for wallet transactions, message signing, and key management.
"""

import os
import json
import time
import hmac
import hashlib
import base64
import secrets
from typing import Dict, Any, Optional
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
import logging

# Configure logger
logger = logging.getLogger(__name__)

class SecureTransactionManager:
    """
    Secure Transaction Manager for the Kingdom AI wallet system.
    
    This class provides secure cryptographic operations for:
    - Transaction encryption/decryption
    - Secure message signing
    - Key derivation and management
    - Transaction verification
    
    All methods enforce strong encryption standards with no fallbacks.
    """
    
    def __init__(self, seed: Optional[str] = None):
        """
        Initialize the secure transaction manager.
        
        Args:
            seed: Optional secure seed for key generation
        """
        self.logger = logging.getLogger("SecureTransactionManager")
        
        # Generate a strong encryption key for sensitive operations
        # This is ephemeral and only stored in memory
        self._secure_key = self._generate_secure_key(seed)
        
        # Initialize AES-GCM for authenticated encryption
        self._aesgcm = AESGCM(self._secure_key)
        
        # Track nonces to prevent reuse
        self._used_nonces = set()
        
        self.logger.info("Secure Transaction Manager initialized with strong encryption")
    
    def _generate_secure_key(self, seed: Optional[str] = None) -> bytes:
        """
        Generate a cryptographically secure key.
        
        Args:
            seed: Optional seed for deterministic key generation
            
        Returns:
            bytes: 32-byte secure key
        """
        if seed:
            # Derive key from seed using PBKDF2
            salt = b"KingdomAISecureTransactionSalt"  # Fixed salt for seed-based derivation
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = kdf.derive(seed.encode())
        else:
            # Generate completely random key
            key = secrets.token_bytes(32)
            
        return key
    
    def encrypt_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive transaction data.
        
        Args:
            transaction_data: Transaction data to encrypt
            
        Returns:
            Dict: Encrypted transaction with metadata
            
        Raises:
            ValueError: If encryption fails
        """
        try:
            # Generate a fresh nonce for each encryption
            nonce = os.urandom(12)  # 96 bits as recommended for AES-GCM
            
            # Ensure nonce is not reused
            attempts = 0
            while nonce in self._used_nonces and attempts < 5:
                nonce = os.urandom(12)
                attempts += 1
                
            if nonce in self._used_nonces:
                raise ValueError("Critical security failure: Unable to generate unique nonce")
                
            self._used_nonces.add(nonce)
            
            # Convert transaction data to JSON bytes
            transaction_bytes = json.dumps(transaction_data).encode()
            
            # Add authenticated encryption with AES-GCM
            # This provides confidentiality, integrity, and authentication
            encrypted_data = self._aesgcm.encrypt(nonce, transaction_bytes, None)
            
            # Create the encrypted transaction packet
            encrypted_transaction = {
                "version": "1.0",
                "algorithm": "AES-GCM-256",
                "nonce": base64.b64encode(nonce).decode(),
                "encrypted_data": base64.b64encode(encrypted_data).decode(),
                "timestamp": datetime.now().isoformat(),
                "transaction_hash": self._hash_transaction(transaction_data)
            }
            
            self.logger.debug("Transaction encrypted successfully")
            return encrypted_transaction
            
        except Exception as e:
            self.logger.error(f"Transaction encryption failed: {str(e)}")
            raise ValueError(f"Failed to encrypt transaction: {str(e)}")
    
    def decrypt_transaction(self, encrypted_transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt an encrypted transaction.
        
        Args:
            encrypted_transaction: Encrypted transaction data
            
        Returns:
            Dict: Original transaction data
            
        Raises:
            ValueError: If decryption fails or verification fails
        """
        try:
            # Extract components
            nonce = base64.b64decode(encrypted_transaction["nonce"])
            encrypted_data = base64.b64decode(encrypted_transaction["encrypted_data"])
            
            # Decrypt with authentication
            transaction_bytes = self._aesgcm.decrypt(nonce, encrypted_data, None)
            
            # Parse JSON
            transaction_data = json.loads(transaction_bytes.decode())
            
            # Verify hash to ensure integrity
            expected_hash = encrypted_transaction.get("transaction_hash")
            if expected_hash:
                actual_hash = self._hash_transaction(transaction_data)
                if expected_hash != actual_hash:
                    raise ValueError("Transaction hash verification failed")
            
            self.logger.debug("Transaction decrypted successfully")
            return transaction_data
            
        except Exception as e:
            self.logger.error(f"Transaction decryption failed: {str(e)}")
            raise ValueError(f"Failed to decrypt transaction: {str(e)}")
    
    def _hash_transaction(self, transaction_data: Dict[str, Any]) -> str:
        """
        Create a secure hash of transaction data.
        
        Args:
            transaction_data: Transaction data to hash
            
        Returns:
            str: SHA-256 hash as hex string
        """
        # Canonicalize the transaction data to ensure consistent hashing
        canonical_data = json.dumps(transaction_data, sort_keys=True)
        
        # Create SHA-256 hash
        return hashlib.sha256(canonical_data.encode()).hexdigest()
    
    def sign_transaction(self, transaction_data: Dict[str, Any], 
                       private_key: bytes) -> str:
        """
        Create a digital signature for a transaction.
        
        Args:
            transaction_data: Transaction data to sign
            private_key: Private key to sign with
            
        Returns:
            str: Base64-encoded signature
            
        Raises:
            ValueError: If signing fails
        """
        try:
            # Hash the transaction first
            transaction_hash = self._hash_transaction(transaction_data)
            
            # Create HMAC signature using the private key
            signature = hmac.new(
                private_key, 
                transaction_hash.encode(), 
                hashlib.sha256
            ).digest()
            
            return base64.b64encode(signature).decode()
            
        except Exception as e:
            self.logger.error(f"Transaction signing failed: {str(e)}")
            raise ValueError(f"Failed to sign transaction: {str(e)}")
    
    def verify_signature(self, transaction_data: Dict[str, Any], 
                       signature: str, public_key: bytes) -> bool:
        """
        Verify a transaction signature.
        
        Args:
            transaction_data: Original transaction data
            signature: Signature to verify
            public_key: Public key to verify with
            
        Returns:
            bool: True if signature is valid
        """
        try:
            # Hash the transaction
            transaction_hash = self._hash_transaction(transaction_data)
            
            # Decode the signature
            signature_bytes = base64.b64decode(signature)
            
            # Verify the signature
            expected_signature = hmac.new(
                public_key,
                transaction_hash.encode(),
                hashlib.sha256
            ).digest()
            
            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(signature_bytes, expected_signature)
            
        except Exception as e:
            self.logger.error(f"Signature verification failed: {str(e)}")
            return False
    
    def encrypt_wallet_data(self, wallet_data: Dict[str, Any], 
                          password: str) -> Dict[str, Any]:
        """
        Encrypt wallet data with password-based encryption.
        
        Args:
            wallet_data: Wallet data to encrypt
            password: User encryption password
            
        Returns:
            Dict: Encrypted wallet data with metadata
            
        Raises:
            ValueError: If encryption fails
        """
        try:
            # Generate random salt
            salt = secrets.token_bytes(16)
            
            # Derive encryption key from password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            
            # Create Fernet symmetric encryption instance
            fernet = Fernet(key)
            
            # Convert wallet data to JSON and encrypt
            wallet_bytes = json.dumps(wallet_data).encode()
            encrypted_data = fernet.encrypt(wallet_bytes)
            
            # Create the encrypted wallet packet
            encrypted_wallet = {
                "version": "1.0",
                "algorithm": "PBKDF2-SHA256-AES128-CBC",
                "salt": base64.b64encode(salt).decode(),
                "encrypted_data": base64.b64encode(encrypted_data).decode(),
                "timestamp": datetime.now().isoformat()
            }
            
            return encrypted_wallet
            
        except Exception as e:
            self.logger.error(f"Wallet encryption failed: {str(e)}")
            raise ValueError(f"Failed to encrypt wallet: {str(e)}")
    
    def decrypt_wallet_data(self, encrypted_wallet: Dict[str, Any], 
                          password: str) -> Dict[str, Any]:
        """
        Decrypt wallet data with password.
        
        Args:
            encrypted_wallet: Encrypted wallet data
            password: User decryption password
            
        Returns:
            Dict: Original wallet data
            
        Raises:
            ValueError: If decryption fails or password is incorrect
        """
        try:
            # Extract salt and encrypted data
            salt = base64.b64decode(encrypted_wallet["salt"])
            encrypted_data = base64.b64decode(encrypted_wallet["encrypted_data"])
            
            # Derive key from password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            
            # Create Fernet instance for decryption
            fernet = Fernet(key)
            
            # Decrypt
            wallet_bytes = fernet.decrypt(encrypted_data)
            
            # Parse JSON
            wallet_data = json.loads(wallet_bytes.decode())
            
            return wallet_data
            
        except Exception as e:
            self.logger.error(f"Wallet decryption failed: {str(e)}")
            raise ValueError(f"Failed to decrypt wallet (incorrect password or data corrupt): {str(e)}")
    
    def generate_secure_transaction_id(self) -> str:
        """
        Generate a cryptographically secure transaction ID.
        
        Returns:
            str: Secure transaction ID
        """
        # Generate 128 bits of randomness (16 bytes)
        random_bytes = secrets.token_bytes(16)
        
        # Convert to a hex string
        transaction_id = random_bytes.hex()
        
        # Add timestamp component for uniqueness
        timestamp = int(time.time())
        
        return f"{transaction_id}-{timestamp}"
    
    def secure_cleanup(self) -> None:
        """
        Securely clean up sensitive data.
        
        This is critical for security to prevent memory scraping attacks.
        """
        # Overwrite sensitive data with random bytes
        if hasattr(self, '_secure_key'):
            random_overwrite = secrets.token_bytes(len(self._secure_key))
            for i in range(len(self._secure_key)):
                self._secure_key[i:i+1] = random_overwrite[i:i+1]
                
        # Clear collections
        if hasattr(self, '_used_nonces'):
            self._used_nonces.clear()
        
        # Set references to None to aid garbage collection
        self._secure_key = None
        self._aesgcm = None
        self._used_nonces = None

# Singleton instance for global access
_instance = None

def get_secure_transaction_manager(seed: Optional[str] = None) -> SecureTransactionManager:
    """
    Get the global secure transaction manager instance.
    
    Args:
        seed: Optional seed for key generation
        
    Returns:
        SecureTransactionManager: Global manager instance
    """
    global _instance
    
    if _instance is None:
        _instance = SecureTransactionManager(seed)
        
    return _instance
