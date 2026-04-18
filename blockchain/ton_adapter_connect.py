#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TON adapter connection methods implementation.
Will be merged with the main adapter file.
"""

import asyncio

async def _init_client(self):
    """Initialize TON client asynchronously."""
    # Create TONLib client for API queries
    if self.api_key:
        headers = {'X-API-Key': self.api_key}
    else:
        headers = None
        
    client = TonlibClient(
        endpoint=self.endpoint,
        headers=headers
    )
    
    # Create Lite client for direct blockchain interaction
    lite_client = None
    try:
        lite_client = await LiteClient.create(self.lite_servers)
    except Exception as e:
        logger.warning(f"Failed to initialize LiteClient: {str(e)}")
        
    return client, lite_client

def _verify_connection(self) -> bool:
    """Verify connection to TON network.
    
    Returns:
        bool: True if connection is successful
        
    Raises:
        BlockchainConnectionError: If connection fails
    """
    if not self.is_connected or not self.client:
        raise BlockchainConnectionError(f"Not connected to {self.network_name}")
        
    try:
        # Ping the server (this will be implemented in connect())
        return True
    except Exception as e:
        self.is_connected = False
        error_msg = f"Connection to {self.network_name} failed: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e

@strict_blockchain_operation
def connect(self) -> bool:
    """Connect to TON network.
    
    Returns:
        bool: True if connected successfully
        
    Raises:
        BlockchainConnectionError: If connection fails
    """
    try:
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Initialize client
        client, lite_client = loop.run_until_complete(self._init_client())
        
        # Test connection by fetching network info
        info = loop.run_until_complete(client.get_masterchain_info())
        
        # Store clients
        self.client = client
        self.lite_client = lite_client
        
        # Initialize wallet if private key or mnemonics are available
        if self.private_key or self.mnemonics:
            try:
                wallet = None
                
                if self.mnemonics:
                    # Create wallet from mnemonics
                    seed = " ".join(self.mnemonics)
                    wallet = TonWallet.from_mnemonics(seed)
                elif self.private_key:
                    # Create wallet from private key
                    wallet = TonWallet(private_key=self.private_key)
                
                if wallet:
                    self.wallet = wallet
                    self.private_key = wallet.private_key.hex()
                    self.public_key = wallet.public_key.hex()
                    
                    # Get wallet address
                    address = wallet.address
                    self.address = address.to_str(is_user_friendly=True)
                    
                    logger.info(f"Initialized wallet: {self.address}")
            except Exception as e:
                logger.warning(f"Failed to initialize wallet: {str(e)}")
                self.wallet = None
                self.address = None
        
        self.is_connected = True
        logger.info(f"Connected to {self.network_name}, block: {info.last.workchain}")
        return True
            
    except Exception as e:
        self.is_connected = False
        error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e
        
@strict_blockchain_operation
def disconnect(self) -> bool:
    """Disconnect from TON network.
    
    Returns:
        bool: True if disconnected successfully
    """
    try:
        # Close clients if available
        if self.client:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_until_complete(self.client.close())
            else:
                asyncio.run(self.client.close())
        
        # Reset connection state
        self.client = None
        self.lite_client = None
        self.is_connected = False
        logger.info(f"Disconnected from {self.network_name}")
        return True
    except Exception as e:
        logger.error(f"Error during disconnect: {str(e)}")
        return False

def validate_address(self, address: str) -> bool:
    """Validate TON address format.
    
    Args:
        address: TON address to validate
        
    Returns:
        bool: True if address is valid
    """
    if not address:
        return False
        
    # Validate TON address
    try:
        # Try to parse the address
        TonAddress(address)
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
        # Check if it's a valid hex string
        if not all(c in '0123456789abcdefABCDEF' for c in private_key.strip()):
            return False
        
        # Check if it has the correct length (64 hex characters for a 32-byte key)
        if len(private_key.strip()) != 64:
            return False
            
        # Try to create a wallet with this private key
        TonWallet(private_key=bytes.fromhex(private_key.strip()))
        return True
    except Exception:
        return False
