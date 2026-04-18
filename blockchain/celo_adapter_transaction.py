#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Celo adapter transaction creation method implementation.
Will be merged with the main adapter file.
"""

@strict_blockchain_operation
def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
    """Create a Celo transaction.
    
    Args:
        transaction: Transaction parameters
            - to_address: Recipient address
            - amount: Amount in CELO/token
            - token_id: Optional token ID for token transfers
            - data: Optional contract data
            - gas_limit: Optional gas limit
            - gas_price: Optional gas price
            - fee_currency: Optional alternative fee currency (cUSD, cEUR)
        
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
    data = transaction.get('data', b'')
    gas_limit = transaction.get('gas_limit')
    gas_price = transaction.get('gas_price')
    fee_currency = transaction.get('fee_currency', self.fee_currency)
    
    # Validate recipient address
    if not to_address or not self.validate_address(to_address):
        raise ValidationError(f"Invalid recipient address: {to_address}")
        
    # Get the sender account
    if not self.address:
        raise ValidationError("No account connected. Cannot create transaction.")
        
    try:
        # Format the destination address
        to_addr = to_checksum_address(to_address)
        
        # Create transaction object based on type (native CELO or token)
        if token_id:
            # Get token contract
            token_contract = self.get_token_contract(token_id)
            
            # Get token decimals
            decimals = 18  # Default
            try:
                decimals = token_contract.call().decimals()
            except Exception:
                if token_id in self.CURRENCY:
                    decimals = self.CURRENCY[token_id]['decimals']
                    
            # Calculate token amount in smallest unit
            token_amount = int(Decimal(amount) * Decimal(10**decimals))
            
            # Create token transfer data
            tx_data = token_contract.encodeABI(fn_name='transfer', args=[to_addr, token_amount])
            
            # Set up transaction parameters
            tx_params = {
                'from': self.address,
                'to': token_contract.address,
                'value': 0,
                'data': tx_data
            }
            
            # Create transaction metadata
            tx_metadata = {
                'type': 'token_transfer',
                'sender': self.address,
                'recipient': to_address,
                'token_id': token_id,
                'token_address': token_contract.address,
                'token_decimals': decimals,
                'amount': amount,
                'amount_wei': token_amount
            }
            
        else:
            # Native CELO transfer
            # Calculate CELO amount in wei
            wei_amount = int(Decimal(amount) * Decimal(10**18))
            
            # Set up transaction parameters
            tx_params = {
                'from': self.address,
                'to': to_addr,
                'value': wei_amount
            }
            
            # Add data if provided
            if data:
                if isinstance(data, str) and data.startswith('0x'):
                    tx_params['data'] = data
                elif isinstance(data, bytes):
                    tx_params['data'] = data
                else:
                    tx_params['data'] = self.web3.to_hex(data) if data else '0x'
            
            # Create transaction metadata
            tx_metadata = {
                'type': 'celo_transfer',
                'sender': self.address,
                'recipient': to_address,
                'amount': amount,
                'amount_wei': wei_amount
            }
        
        # Add gas parameters
        if not gas_limit:
            # Estimate gas
            gas_limit = self.web3.eth.estimate_gas(tx_params)
            # Add safety margin (10%)
            gas_limit = int(gas_limit * 1.1)
            
        tx_params['gas'] = gas_limit
        
        # Set gas price if provided
        if gas_price:
            if isinstance(gas_price, (int, float, Decimal)):
                tx_params['gasPrice'] = int(gas_price)
            elif isinstance(gas_price, str) and gas_price.isdigit():
                tx_params['gasPrice'] = int(gas_price)
        else:
            # Get current gas price
            tx_params['gasPrice'] = self.web3.eth.gas_price
            
        # Add chain ID for EIP-155 replay protection
        tx_params['chainId'] = self.chain_id
        
        # Get current nonce
        tx_params['nonce'] = self.web3.eth.get_transaction_count(self.address, 'pending')
        
        # Handle Celo-specific fee currency if provided
        # This allows paying gas fees in stable tokens instead of CELO
        if fee_currency:
            try:
                # Get fee currency contract
                fee_currency_contract = self.get_token_contract(fee_currency)
                
                # Add fee currency address to tx params
                # Note: Celo custom extensions to the Ethereum JSON-RPC
                tx_params['feeCurrency'] = fee_currency_contract.address
                
                # Add to metadata
                tx_metadata['fee_currency'] = fee_currency
                tx_metadata['fee_currency_address'] = fee_currency_contract.address
            except Exception as e:
                logger.warning(f"Failed to set fee currency {fee_currency}: {str(e)}")
                
        # Add transaction parameters to metadata
        tx_metadata.update({
            'gas_limit': gas_limit,
            'gas_price': tx_params['gasPrice'],
            'nonce': tx_params['nonce'],
            'chain_id': self.chain_id,
            'tx_params': tx_params,
            'status': 'created'
        })
        
        logger.debug(f"Created {tx_metadata['type']} transaction: {tx_metadata}")
        return tx_metadata
        
    except Exception as e:
        error_msg = f"Failed to create transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e
