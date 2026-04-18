#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Celo adapter balance method implementation.
Will be merged with the main adapter file.
"""

@strict_blockchain_operation
def get_balance(self, address: str = None, token_id: str = None) -> Decimal:
    """Get Celo balance for an account.
    
    Args:
        address: Celo address to query, defaults to connected account
        token_id: Optional token ID for querying token balance
        
    Returns:
        Decimal: Balance in CELO or specified token
        
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
        if token_id:
            # Check if token_id is a known currency symbol
            decimals = 18  # Default for most tokens
            
            if token_id in self.CURRENCY:
                decimals = self.CURRENCY[token_id]['decimals']
            
            # Get token contract
            token_contract = self.get_token_contract(token_id)
            
            # Get token balance
            balance_wei = token_contract.call().balanceOf(addr)
            
            # Convert from wei to token units
            balance = Decimal(balance_wei) / Decimal(10**decimals)
            
            # Get token symbol
            try:
                token_symbol = token_contract.call().symbol()
            except Exception:
                token_symbol = token_id
                
        else:
            # Get native CELO balance
            balance_wei = self.web3.eth.get_balance(addr)
            
            # Convert from wei to CELO
            balance = Decimal(balance_wei) / Decimal(10**18)
            token_symbol = "CELO"
            
        logger.debug(f"Balance for {addr}: {balance} {token_symbol}")
        return balance
        
    except Exception as e:
        error_msg = f"Failed to get balance for {addr}: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e

@strict_blockchain_operation
def get_token_metadata(self, token_id: str) -> Dict:
    """Get token metadata.
    
    Args:
        token_id: Token ID (address or symbol)
        
    Returns:
        Dict: Token metadata
        
    Raises:
        ConnectionError: If network connection fails
        ValidationError: If token_id is invalid
    """
    self._verify_connection()
    
    try:
        # Get token contract
        token_contract = self.get_token_contract(token_id)
        
        # Query token details
        metadata = {}
        
        # Get basic token information
        try:
            metadata['name'] = token_contract.call().name()
        except Exception:
            metadata['name'] = token_id
            
        try:
            metadata['symbol'] = token_contract.call().symbol()
        except Exception:
            metadata['symbol'] = token_id
            
        try:
            metadata['decimals'] = token_contract.call().decimals()
        except Exception:
            metadata['decimals'] = 18  # Default decimals
            
        try:
            metadata['total_supply'] = str(token_contract.call().totalSupply())
        except Exception:
            pass
        
        # Add token address
        metadata['address'] = token_contract.address
        
        # Add contract address
        metadata['contract_address'] = token_contract.address
        
        # Check if token is a stable token
        for symbol, address in self.stable_tokens.items():
            if token_id == symbol or token_id == address:
                metadata['is_stable_token'] = True
                metadata['token_type'] = 'stable'
                break
        else:
            metadata['is_stable_token'] = False
            metadata['token_type'] = 'erc20'
        
        # Additional Celo-specific information if available
        try:
            if token_id == 'cUSD' or token_id == 'cEUR' or token_id == 'cREAL':
                exchange_rate = self.kit.contracts.exchange.get_exchange_rate(token_id, 'CELO')
                metadata['exchange_rate_to_celo'] = exchange_rate
        except Exception:
            pass
            
        return metadata
        
    except Exception as e:
        error_msg = f"Failed to get token metadata: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e

@strict_blockchain_operation
def list_tokens(self) -> List[Dict]:
    """List common tokens on the Celo network.
    
    Returns:
        List[Dict]: List of common tokens
        
    Raises:
        ConnectionError: If network connection fails
    """
    self._verify_connection()
    
    token_list = []
    
    # Add native CELO
    token_list.append({
        'name': 'Celo',
        'symbol': 'CELO',
        'decimals': 18,
        'is_native': True,
        'token_type': 'native'
    })
    
    # Add stable tokens
    for symbol, address in self.stable_tokens.items():
        try:
            token_contract = self.get_token_contract(symbol)
            token = {
                'name': token_contract.call().name(),
                'symbol': symbol,
                'decimals': token_contract.call().decimals(),
                'address': address,
                'is_native': False,
                'token_type': 'stable',
                'is_stable_token': True
            }
            token_list.append(token)
        except Exception as e:
            logger.debug(f"Error fetching token data for {symbol}: {str(e)}")
    
    # Return the token list
    return token_list
