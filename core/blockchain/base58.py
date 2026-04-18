#!/usr/bin/env python3
"""
Base58 implementation for Solana and other blockchain systems
Runtime-compatible implementation for Kingdom AI
"""

import hashlib
import logging
from typing import Union

logger = logging.getLogger(__name__)

# Base58 alphabet used by Bitcoin and many other cryptocurrencies
BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def b58encode(data: bytes) -> str:
    """Encode bytes to base58 string"""
    if not data:
        return ''
    
    # Convert to integer
    num = int.from_bytes(data, 'big')
    
    # Count leading zeros
    n_zeros = 0
    for byte in data:
        if byte == 0:
            n_zeros += 1
        else:
            break
    
    # Encode
    alphabet = BASE58_ALPHABET
    encoded = ''
    while num > 0:
        num, remainder = divmod(num, 58)
        encoded = alphabet[remainder] + encoded
    
    # Add leading zeros
    return alphabet[0] * n_zeros + encoded

def b58decode(encoded: str) -> bytes:
    """Decode base58 string to bytes"""
    if not encoded:
        return b''
    
    alphabet = BASE58_ALPHABET
    alphabet_map = {char: index for index, char in enumerate(alphabet)}
    
    # Count leading zeros
    n_zeros = 0
    for char in encoded:
        if char == alphabet[0]:
            n_zeros += 1
        else:
            break
    
    # Convert to integer
    num = 0
    for char in encoded:
        if char not in alphabet_map:
            raise ValueError(f'Invalid character {char} in base58 string')
        num = num * 58 + alphabet_map[char]
    
    # Convert to bytes
    byte_length = (num.bit_length() + 7) // 8
    decoded = num.to_bytes(byte_length, 'big')
    
    # Add leading zeros
    return b'\x00' * n_zeros + decoded

def b58encode_check(data: bytes) -> str:
    """Encode bytes to base58 with checksum"""
    checksum = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    return b58encode(data + checksum)

def b58decode_check(encoded: str) -> bytes:
    """Decode base58 string with checksum verification"""
    decoded = b58decode(encoded)
    if len(decoded) < 4:
        raise ValueError('Invalid base58 checksum')
    
    data, checksum = decoded[:-4], decoded[-4:]
    calculated_checksum = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    
    if checksum != calculated_checksum:
        raise ValueError('Invalid base58 checksum')
    
    return data

# Compatibility aliases for common usage
encode = b58encode
decode = b58decode
encode_check = b58encode_check
decode_check = b58decode_check

logger.info("✅ Base58 implementation loaded")
