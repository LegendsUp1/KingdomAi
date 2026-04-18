#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Injective adapter balance method implementation.
Will be merged with the main adapter file.
"""

import asyncio

@strict_blockchain_operation
def get_balance(self, address: str = None, token_id: str = None) -> Decimal:
    """Get INJ balance for an account.
    
    Args:
        address: Injective address to query, defaults to connected account
        token_id: Optional token ID for querying token balance (denom)
        
    Returns:
        Decimal: Balance in INJ or specified token
        
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
        # Set up default denom
        denom = token_id or self.fee_denom
        
        # Create async function to get balance
        async def async_get_balance():
            # Query bank balances
            balances_response = await self.client.get_account_balances(addr)
            
            # Find the requested token balance
            balance = Decimal('0')
            for coin in balances_response.balances:
                if coin.denom == denom:
                    # Convert from smallest unit to main unit
                    decimals = self.CURRENCY.get(denom.upper(), {}).get('decimals', 18)
                    balance = Decimal(coin.amount) / Decimal(10**decimals)
                    break
                    
            return balance
        
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        balance = loop.run_until_complete(async_get_balance())
        loop.close()
        
        token_symbol = denom.upper() if denom == self.fee_denom else denom
        logger.debug(f"Balance for {addr}: {balance} {token_symbol}")
        return balance
        
    except Exception as e:
        error_msg = f"Failed to get balance for {addr}: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e

@strict_blockchain_operation
def get_token_balances(self, address: str = None) -> Dict:
    """Get all token balances for an account.
    
    Args:
        address: Injective address to query, defaults to connected account
        
    Returns:
        Dict: Mapping of token denominations to balances
        
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
        # Create async function to get balances
        async def async_get_token_balances():
            # Query bank balances
            balances_response = await self.client.get_account_balances(addr)
            
            # Process all token balances
            token_balances = {}
            for coin in balances_response.balances:
                denom = coin.denom
                amount = coin.amount
                
                # Convert from smallest unit to main unit
                # Default to 18 decimals if not specified
                decimals = self.CURRENCY.get(denom.upper(), {}).get('decimals', 18)
                balance = Decimal(amount) / Decimal(10**decimals)
                
                token_balances[denom] = balance
                
            return token_balances
        
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        token_balances = loop.run_until_complete(async_get_token_balances())
        loop.close()
        
        logger.debug(f"Retrieved {len(token_balances)} token balances for {addr}")
        return token_balances
        
    except Exception as e:
        error_msg = f"Failed to get token balances for {addr}: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e
