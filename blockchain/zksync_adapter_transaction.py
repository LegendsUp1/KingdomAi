#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
zkSync adapter transaction creation method implementation.
Will be merged with the main adapter file.
"""

@strict_blockchain_operation
def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
    """Create a zkSync transaction.
    
    Args:
        transaction: Transaction parameters
            - to_address: Recipient address
            - amount: Amount in ETH
            - token_id: Optional token ID for token transfers
            - gas_limit: Optional gas limit for the transaction
            - gas_price: Optional gas price for the transaction
            - data: Optional data for the transaction
        
    Returns:
        Dict: Prepared transaction object ready for signing
        
    Raises:
        ValidationError: If transaction parameters are invalid
        TransactionError: If transaction creation fails
    """
    self._verify_connection()
    
    # Validate the transaction parameters
    to_address = transaction.get('to_address')
    amount = transaction.get('amount')
    token_id = transaction.get('token_id')
    gas_limit = transaction.get('gas_limit')
    gas_price = transaction.get('gas_price')
    data = transaction.get('data', '0x')
    
    # Validate recipient address
    if not to_address or not self.validate_address(to_address):
        raise ValidationError(f"Invalid recipient address: {to_address}")
        
    # Get the sender account
    if not self.account or not self.address:
        raise ValidationError("No account connected. Cannot create transaction.")
        
    # Normalize addresses
    from_addr = to_checksum_address(self.address)
    to_addr = to_checksum_address(to_address)
    
    try:
        from web3 import Web3
        
        # Convert amount from ETH to wei
        amount_wei = Web3.to_wei(amount, 'ether')
        
        # Get nonce
        nonce = self.provider.get_transaction_count(from_addr)
        
        # Get current gas price if not provided
        if not gas_price:
            gas_price = self.provider.gas_price
            
        # Prepare transaction parameters
        if token_id:
            # Token transfer (ERC20)
            # Basic ERC20 ABI for transfer method
            erc20_abi = [
                {
                    "constant": False,
                    "inputs": [
                        {"name": "_to", "type": "address"},
                        {"name": "_value", "type": "uint256"}
                    ],
                    "name": "transfer",
                    "outputs": [{"name": "", "type": "bool"}],
                    "payable": False,
                    "stateMutability": "nonpayable",
                    "type": "function"
                }
            ]
            
            # Create contract instance
            contract_addr = Web3.to_checksum_address(token_id)
            contract = self.eth_web3.eth.contract(address=contract_addr, abi=erc20_abi)
            
            # Create transaction data
            data = contract.encodeABI(
                fn_name="transfer",
                args=[to_addr, amount_wei]
            )
            
            # Create token transaction
            tx_params = {
                'from': from_addr,
                'to': contract_addr,
                'data': data,
                'value': 0,
                'nonce': nonce,
                'chainId': self.chain_id
            }
            
            if gas_price:
                tx_params['gasPrice'] = gas_price
                
            # Estimate gas limit if not provided
            if not gas_limit:
                try:
                    gas_limit = self.eth_web3.eth.estimate_gas(tx_params)
                    # Add some buffer for token transactions
                    gas_limit = int(gas_limit * 1.2)
                except Exception as e:
                    logger.warning(f"Failed to estimate gas: {str(e)}")
                    gas_limit = 100000  # Default for token transfers
                    
            tx_params['gas'] = gas_limit
        else:
            # Native ETH transfer
            tx_params = {
                'from': from_addr,
                'to': to_addr,
                'value': amount_wei,
                'nonce': nonce,
                'data': data,
                'chainId': self.chain_id
            }
            
            if gas_price:
                tx_params['gasPrice'] = gas_price
                
            # Estimate gas limit if not provided
            if not gas_limit:
                try:
                    gas_limit = self.eth_web3.eth.estimate_gas(tx_params)
                except Exception as e:
                    logger.warning(f"Failed to estimate gas: {str(e)}")
                    gas_limit = 21000  # Default for ETH transfers
                    
            tx_params['gas'] = gas_limit
            
        # Create the transaction object
        tx_type = 'token_transfer' if token_id else 'eth_transfer'
        
        tx_data = {
            'type': tx_type,
            'sender': from_addr,
            'recipient': to_addr if not token_id else token_id,
            'amount': amount,
            'amount_wei': amount_wei,
            'nonce': nonce,
            'gas_limit': tx_params['gas'],
            'gas_price': tx_params.get('gasPrice', None),
            'chain_id': self.chain_id,
            'params': tx_params,
            'token_id': token_id
        }
        
        if 'data' in transaction:
            tx_data['data'] = transaction['data']
        
        logger.debug(f"Created transaction: {tx_data}")
        return tx_data
        
    except Exception as e:
        error_msg = f"Failed to create transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e
