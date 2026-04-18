#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Injective adapter connection methods implementation.
Will be merged with the main adapter file.
"""

import asyncio

@strict_blockchain_operation
def connect(self) -> bool:
    """Connect to Injective network.
    
    Returns:
        bool: True if connected successfully
        
    Raises:
        BlockchainConnectionError: If connection fails
    """
    try:
        # Create client and composer synchronously by using asyncio
        async def async_connect():
            # Create async client
            client = InjectiveClient(
                network=self.network,
                insecure=self.grpc_endpoint.endswith(':9090'),  # True if using insecure local endpoint
                chain_id=self.chain_id
            )
            
            # Create composer
            composer = InjectiveComposer(
                network=self.network,
                chain_id=self.chain_id
            )
            
            # Initialize account if private key is available
            account = None
            public_key = None
            address = None
            
            if self.private_key:
                try:
                    # Create account from private key
                    account = InjectivePrivateKey.from_hex(self.private_key)
                    public_key = account.to_public_key()
                    address = public_key.to_address()
                    
                    logger.info(f"Initialized account: {address.to_acc_bech32()}")
                except Exception as e:
                    logger.warning(f"Failed to initialize account: {str(e)}")
                    account = None
                    public_key = None
                    address = None
            
            return client, composer, account, public_key, address
        
        # Run async initialization in a synchronous context
        loop = asyncio.new_event_loop()
        client, composer, account, public_key, address = loop.run_until_complete(async_connect())
        loop.close()
        
        # Store connection data
        self.client = client
        self.composer = composer
        self.account = account
        self.public_key = public_key
        self.address = address.to_acc_bech32() if address else None
        
        self.is_connected = True
        logger.info(f"Connected to {self.network_name}")
        return True
            
    except Exception as e:
        self.is_connected = False
        error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e
        
@strict_blockchain_operation
def disconnect(self) -> bool:
    """Disconnect from Injective network.
    
    Returns:
        bool: True if disconnected successfully
    """
    try:
        # Close client if available
        if self.client:
            # Close the client connection
            # Note: AsyncClient doesn't have a specific close method,
            # so we'll just set it to None
            self.client = None
        
        # Reset connection state
        self.composer = None
        self.is_connected = False
        logger.info(f"Disconnected from {self.network_name}")
        return True
    except Exception as e:
        logger.error(f"Error during disconnect: {str(e)}")
        return False

def validate_address(self, address: str) -> bool:
    """Validate Injective address format.
    
    Args:
        address: Injective address to validate
        
    Returns:
        bool: True if address is valid
    """
    if not address:
        return False
        
    # Validate Injective bech32 address
    try:
        # Check if it starts with "inj"
        if not address.startswith('inj'):
            return False
            
        # Try to decode the address
        InjectiveAddress.from_acc_bech32(address)
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
        # Try to create a private key from the hex string
        InjectivePrivateKey.from_hex(private_key)
        return True
    except Exception:
        return False
