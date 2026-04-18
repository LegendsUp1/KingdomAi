#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
zkSync adapter balance method implementation.
Will be merged with the main adapter file.
"""

@strict_blockchain_operation
def get_balance(self, address: str = None, token_id: str = None) -> Decimal:
    """Get ETH balance for an account.
    
    Args:
        address: Ethereum address to query, defaults to connected account
        token_id: Optional token ID for querying token balance
        
    Returns:
        Decimal: Balance in ETH
        
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
            # Get token balance (ERC20)
            # Note: This requires the token contract ABI and address
            # Simplified implementation for common ERC20 interface
            from web3 import Web3
            
            # Basic ERC20 ABI for balanceOf method
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function"
                }
            ]
            
            # Create contract instance
            w3 = self.eth_web3
            contract_addr = Web3.to_checksum_address(token_id)
            contract = w3.eth.contract(address=contract_addr, abi=erc20_abi)
            
            # Get token decimals
            try:
                decimals = contract.functions.decimals().call()
            except Exception:
                decimals = 18  # Default for most ERC20 tokens
                
            # Get token balance
            balance_wei = contract.functions.balanceOf(Web3.to_checksum_address(addr)).call()
            balance = Decimal(balance_wei) / Decimal(10**decimals)
            
            return balance
        else:
            # Get ETH balance
            balance_wei = self.provider.get_balance(addr)
            balance_eth = Decimal(balance_wei) / Decimal(10**18)  # Convert from wei to ETH
            
            logger.debug(f"Balance for {addr}: {balance_eth} ETH")
            return balance_eth
            
    except Exception as e:
        error_msg = f"Failed to get balance for {addr}: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e
