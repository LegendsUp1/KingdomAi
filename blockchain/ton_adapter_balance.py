#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TON adapter balance method implementation.
Will be merged with the main adapter file.
"""

import asyncio

@strict_blockchain_operation
def get_balance(self, address: str = None, token_id: str = None) -> Decimal:
    """Get TON balance for an account.
    
    Args:
        address: TON address to query, defaults to connected account
        token_id: Optional token ID for querying token balance (jetton address)
        
    Returns:
        Decimal: Balance in TON or specified token
        
    Raises:
        ConnectionError: If network connection fails
        ValidationError: If address is invalid
    """
    self._verify_connection()
    
    # Use the provided address or the connected account
    addr = address or self.address
    
    if not addr:
        raise ValidationError("No address provided and no account connected")
        
    if not self.validate_address(addr):
        raise ValidationError(f"Invalid address: {addr}")
        
    try:
        # Create async function to get balance
        async def async_get_balance():
            if token_id:
                # Get jetton (token) balance
                # This requires querying the jetton contract
                try:
                    # Parse token address
                    token_addr = TonAddress(token_id)
                    
                    # Query jetton wallet address for the user
                    jetton_wallet_addr = await self.client.get_jetton_wallet_address(
                        owner_address=TonAddress(addr),
                        jetton_master_address=token_addr
                    )
                    
                    # Get jetton wallet data
                    jetton_data = await self.client.get_jetton_wallet_data(jetton_wallet_addr)
                    
                    # Convert from nanojettons to jettons
                    # Most TON jettons use 9 decimals like TON itself
                    decimals = 9
                    balance = Decimal(jetton_data.balance) / Decimal(10**decimals)
                    
                    return balance
                except Exception as e:
                    logger.error(f"Failed to get jetton balance: {str(e)}")
                    return Decimal('0')
            else:
                # Get native TON balance
                if self.lite_client:
                    # Use lite client for faster queries
                    account_info = await self.lite_client.get_account_state(TonAddress(addr))
                    balance_nano = account_info.balance
                else:
                    # Fallback to HTTP client
                    account_info = await self.client.get_account_info(TonAddress(addr))
                    balance_nano = account_info.balance
                
                # Convert from nanoTON to TON (1 TON = 10^9 nanoTON)
                balance = Decimal(balance_nano) / Decimal(10**9)
                
                return balance
        
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        balance = loop.run_until_complete(async_get_balance())
        loop.close()
        
        token_symbol = "Jetton" if token_id else "TON"
        logger.debug(f"Balance for {addr}: {balance} {token_symbol}")
        return balance
        
    except Exception as e:
        error_msg = f"Failed to get balance for {addr}: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e
        
@strict_blockchain_operation
def get_jetton_data(self, token_id: str) -> Dict:
    """Get jetton (token) metadata.
    
    Args:
        token_id: Jetton master contract address
        
    Returns:
        Dict: Jetton metadata
        
    Raises:
        ConnectionError: If network connection fails
        ValidationError: If token_id is invalid
    """
    self._verify_connection()
    
    if not token_id or not self.validate_address(token_id):
        raise ValidationError(f"Invalid jetton address: {token_id}")
        
    try:
        # Create async function to get jetton data
        async def async_get_jetton_data():
            # Parse token address
            token_addr = TonAddress(token_id)
            
            # Get jetton data
            jetton_data = await self.client.get_jetton_master_data(token_addr)
            
            # Process metadata
            metadata = {}
            
            # Extract basic information
            metadata['total_supply'] = str(jetton_data.total_supply)
            metadata['mintable'] = jetton_data.mintable
            
            # Extract jetton content
            content = jetton_data.content
            
            # Try to decode content
            if content.uri:
                metadata['uri'] = content.uri
                
                # Try to fetch metadata from URI if it's a URL
                if content.uri.startswith(('http://', 'https://')):
                    try:
                        response = requests.get(content.uri, timeout=5)
                        if response.status_code == 200:
                            metadata['external_content'] = response.json()
                    except Exception as e:
                        logger.debug(f"Failed to fetch external content: {str(e)}")
            
            # Extract on-chain metadata
            if content.metadata:
                for key, value in content.metadata.items():
                    metadata[key] = value
            
            return metadata
            
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        jetton_data = loop.run_until_complete(async_get_jetton_data())
        loop.close()
        
        logger.debug(f"Retrieved jetton data for {token_id}")
        return jetton_data
        
    except Exception as e:
        error_msg = f"Failed to get jetton data for {token_id}: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e
