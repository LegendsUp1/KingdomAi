#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Cryptographic Utilities

This module provides cryptographic utilities for the Kingdom AI wallet
and blockchain integration.
"""

import os
import hashlib
import base64
import logging
from typing import Optional, Dict, Any, Tuple

# Set up logger
logger = logging.getLogger(__name__)

class WalletEncryption:
    """Handles wallet encryption and decryption operations."""
    
    @staticmethod
    def generate_key(passphrase: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Generate an encryption key from a passphrase.
        
        Args:
            passphrase: User passphrase for encryption
            salt: Optional salt for key derivation
            
        Returns:
            Tuple of (key, salt)
        """
        if salt is None:
            salt = os.urandom(32)  # 32 bytes of randomness for the salt
            
        # Use PBKDF2 for key derivation
        key = hashlib.pbkdf2_hmac(
            'sha256',  # Hash algorithm
            passphrase.encode('utf-8'),  # Convert passphrase to bytes
            salt,  # Salt
            100000,  # Number of iterations
            dklen=32  # Length of the derived key
        )
        
        return key, salt
    
    @staticmethod
    def encrypt_wallet_data(data: Dict[str, Any], key: bytes) -> bytes:
        """Encrypt wallet data with the given key using AES-256-GCM.
        
        Args:
            data: Wallet data to encrypt
            key: Encryption key (must be 32 bytes for AES-256)
            
        Returns:
            Encrypted data as bytes (nonce + ciphertext)
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from cryptography.hazmat.backends import default_backend
            import json
            import os
            
            # Ensure key is 32 bytes for AES-256
            if len(key) != 32:
                # Derive 32-byte key from provided key using SHA256
                key = hashlib.sha256(key).digest()
            
            # Serialize data to JSON
            serialized = json.dumps(data).encode('utf-8')
            
            # Create AESGCM cipher
            aesgcm = AESGCM(key)
            
            # Generate random nonce (12 bytes for GCM)
            nonce = os.urandom(12)
            
            # Encrypt data
            ciphertext = aesgcm.encrypt(nonce, serialized, None)
            
            # Return nonce + ciphertext (nonce needed for decryption)
            return nonce + ciphertext
        except ImportError:
            logger.error("cryptography library not available - encryption failed")
            raise RuntimeError("cryptography library required for encryption")
        except Exception as e:
            logger.error(f"Error encrypting wallet data: {e}")
            raise
    
    @staticmethod
    def decrypt_wallet_data(encrypted_data: bytes, key: bytes) -> Dict[str, Any]:
        """Decrypt wallet data with the given key using AES-256-GCM.
        
        Args:
            encrypted_data: Encrypted wallet data (nonce + ciphertext)
            key: Decryption key (must be 32 bytes for AES-256)
            
        Returns:
            Decrypted wallet data
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            import json
            
            # Ensure key is 32 bytes for AES-256
            if len(key) != 32:
                # Derive 32-byte key from provided key using SHA256
                key = hashlib.sha256(key).digest()
            
            # Extract nonce (first 12 bytes) and ciphertext
            if len(encrypted_data) < 12:
                raise ValueError("Invalid encrypted data format - too short")
            
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            # Create AESGCM cipher
            aesgcm = AESGCM(key)
            
            # Decrypt data
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            # Deserialize JSON
            return json.loads(plaintext.decode('utf-8'))
        except ImportError:
            logger.error("cryptography library not available - decryption failed")
            raise RuntimeError("cryptography library required for decryption")
        except Exception as e:
            logger.error(f"Error decrypting wallet data: {e}")
            raise

class AddressValidator:
    """Validates cryptocurrency addresses."""
    
    @staticmethod
    def is_valid_eth_address(address: str) -> bool:
        """Check if a string is a valid Ethereum address.
        
        Args:
            address: Ethereum address to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Basic validation (in production would use proper validation)
        if not address.startswith('0x'):
            return False
        if len(address) != 42:  # '0x' + 40 hex chars
            return False
        try:
            int(address[2:], 16)  # Should be valid hex
            return True
        except ValueError:
            return False
    
    _B58_ALPHABET = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    _BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

    @classmethod
    def _decode_base58(cls, addr: str) -> Optional[bytes]:
        """Decode a Base58Check-encoded address and verify its checksum."""
        try:
            n = 0
            for ch in addr.encode('ascii'):
                idx = cls._B58_ALPHABET.find(bytes([ch]))
                if idx < 0:
                    return None
                n = n * 58 + idx
            raw = n.to_bytes(25, byteorder='big')
            payload, checksum = raw[:-4], raw[-4:]
            if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
                return None
            return payload
        except Exception:
            return None

    @classmethod
    def _verify_bech32(cls, addr: str) -> bool:
        """Verify a Bech32/Bech32m encoded Bitcoin address (bc1...)."""
        try:
            addr_lower = addr.lower()
            if not addr_lower.startswith('bc1') or len(addr_lower) < 14 or len(addr_lower) > 90:
                return False
            if any(c not in cls._BECH32_CHARSET for c in addr_lower[3:]):
                return False
            hrp, data_part = 'bc', addr_lower[3:]
            values = [cls._BECH32_CHARSET.index(c) for c in data_part]

            def _bech32_polymod(vals):
                gen = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
                chk = 1
                for v in vals:
                    top = chk >> 25
                    chk = ((chk & 0x1ffffff) << 5) ^ v
                    for i in range(5):
                        chk ^= gen[i] if ((top >> i) & 1) else 0
                return chk

            hrp_expand = [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]
            polymod = _bech32_polymod(hrp_expand + values)
            if polymod not in (1, 0x2bc830a3):  # bech32 or bech32m
                return False
            witness_ver = values[0]
            if witness_ver < 0 or witness_ver > 16:
                return False
            decoded_len = len(values) - 7  # subtract witness version + 6 checksum chars
            if witness_ver == 0 and decoded_len not in (20, 32):
                return False
            return True
        except Exception:
            return False

    @classmethod
    def is_valid_btc_address(cls, address: str) -> bool:
        """Check if a string is a valid Bitcoin address.
        
        Validates P2PKH (1...), P2SH (3...), and Bech32/Bech32m (bc1...)
        addresses including Base58Check checksum and Bech32 polymod verification.
        
        Args:
            address: Bitcoin address to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not address or not isinstance(address, str):
            return False

        if address.startswith('bc1') or address.startswith('BC1'):
            return cls._verify_bech32(address)

        if address.startswith('1') or address.startswith('3'):
            payload = cls._decode_base58(address)
            if payload is None:
                return False
            version = payload[0]
            if address.startswith('1') and version != 0x00:
                return False
            if address.startswith('3') and version != 0x05:
                return False
            return True

        return False

# Utility functions for direct import
def encrypt_with_key(data: Dict[str, Any], key: bytes) -> bytes:
    """Encrypt data using the provided key.
    
    Args:
        data: Data to encrypt
        key: Encryption key
        
    Returns:
        Encrypted data as bytes
    """
    return WalletEncryption.encrypt_wallet_data(data, key)


def decrypt_with_key(encrypted_data: bytes, key: bytes) -> Dict[str, Any]:
    """Decrypt data using the provided key.
    
    Args:
        encrypted_data: Encrypted data
        key: Decryption key
        
    Returns:
        Decrypted data
    """
    return WalletEncryption.decrypt_wallet_data(encrypted_data, key)


# Export key classes and functions
__all__ = ['WalletEncryption', 'AddressValidator', 'encrypt_with_key', 'decrypt_with_key']
