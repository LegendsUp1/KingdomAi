#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
zkSync adapter transaction status and fee methods.
Will be merged with the main adapter file.
"""

@strict_blockchain_operation
def get_transaction_status(self, tx_id: str) -> Dict:
    """Get the status of a zkSync transaction.
    
    Args:
        tx_id: Transaction hash to check
        
    Returns:
        Dict: Transaction status and details
        
    Raises:
        ValidationError: If tx_id is invalid
        TransactionError: If status check fails
    """
    self._verify_connection()
    
    if not tx_id:
        raise ValidationError("Invalid transaction hash")
        
    try:
        # Query transaction receipt
        tx_receipt = self.provider.get_transaction_receipt(tx_id)
        
        if not tx_receipt:
            # Transaction not found or pending
            # Try to get the transaction
            tx = self.provider.get_transaction(tx_id)
            
            if not tx:
                # Transaction not found
                return {
                    'txid': tx_id,
                    'hash': tx_id,
                    'status': 'unknown',
                    'confirmed': False,
                    'explorer_url': self.explorer_tx_url().format(txid=tx_id)
                }
                
            # Transaction found but not yet mined
            return {
                'txid': tx_id,
                'hash': tx_id,
                'status': 'pending',
                'confirmed': False,
                'sender': tx.get('from', ''),
                'recipient': tx.get('to', ''),
                'explorer_url': self.explorer_tx_url().format(txid=tx_id)
            }
            
        # Transaction mined
        is_success = tx_receipt.status == 1
        status = 'success' if is_success else 'failed'
        
        # Get transaction details
        tx = self.provider.get_transaction(tx_id)
        
        # Extract useful information
        result = {
            'txid': tx_id,
            'hash': tx_id,
            'status': status,
            'confirmed': is_success,
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'explorer_url': self.explorer_tx_url().format(txid=tx_id)
        }
        
        if tx:
            # Add more details if available
            result.update({
                'sender': tx.get('from', ''),
                'recipient': tx.get('to', ''),
                'value': tx.get('value', 0),
                'gas_price': tx.get('gasPrice', 0),
                'nonce': tx.get('nonce', 0)
            })
            
        return result
        
    except Exception as e:
        # If transaction not found or other error
        logger.debug(f"Error checking transaction status: {str(e)}")
        
        # Return unknown status
        return {
            'txid': tx_id,
            'hash': tx_id,
            'status': 'unknown',
            'confirmed': False,
            'explorer_url': self.explorer_tx_url().format(txid=tx_id)
        }
        
@strict_blockchain_operation
def get_network_status(self) -> Dict:
    """Get zkSync network status.
    
    Returns:
        Dict: Network status information
        
    Raises:
        BlockchainConnectionError: If status check fails
    """
    self._verify_connection()
    
    try:
        # Get block number
        block_number = self.provider.get_block_number()
        
        # Get gas price
        gas_price = self.provider.gas_price
        
        # Get chain ID
        chain_id = self.provider.chain_id
        
        # Create network status
        result = {
            'network': self.network_name,
            'chain_id': chain_id,
            'block_number': block_number,
            'gas_price': gas_price,
            'active': True
        }
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to get network status: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e
        
@strict_blockchain_operation
def estimate_fee(self, transaction: Dict = None) -> Dict:
    """Estimate fees for a zkSync transaction.
    
    Args:
        transaction: Optional transaction to estimate fee for
        
    Returns:
        Dict: Fee estimation in different speeds
        
    Raises:
        ValidationError: If transaction is invalid
        TransactionError: If fee estimation fails
    """
    self._verify_connection()
    
    try:
        # Get current gas price
        gas_price = self.provider.gas_price
        
        # Define gas price adjustments for different speeds
        gas_prices = {
            'slow': int(gas_price * 0.8),
            'average': int(gas_price),
            'fast': int(gas_price * 1.2)
        }
        
        # Standard gas limits
        gas_limits = {
            'eth_transfer': 21000,  # Simple transfer
            'token_transfer': 100000,  # Token transfer
            'contract_call': 200000,  # Contract interaction
        }
        
        # Calculate costs in ETH
        costs = {}
        for speed, price in gas_prices.items():
            for tx_type, limit in gas_limits.items():
                # Cost = gas_limit * gas_price / 10^18
                cost = Decimal(limit * price) / Decimal(10**18)
                costs[f"{speed}_{tx_type}"] = cost
        
        # Create fee structure
        fee_structure = {
            'slow': costs['slow_eth_transfer'],
            'average': costs['average_eth_transfer'],
            'fast': costs['fast_eth_transfer'],
            'slow_token': costs['slow_token_transfer'],
            'average_token': costs['average_token_transfer'],
            'fast_token': costs['fast_token_transfer'],
            'gas_price': gas_price,
            'gas_price_slow': gas_prices['slow'],
            'gas_price_average': gas_prices['average'],
            'gas_price_fast': gas_prices['fast'],
            'gas_limit_eth_transfer': gas_limits['eth_transfer'],
            'gas_limit_token_transfer': gas_limits['token_transfer'],
            'gas_limit_contract_call': gas_limits['contract_call'],
            'unit': 'ETH'
        }
        
        # If a specific transaction is provided, estimate its fee
        if transaction and 'type' in transaction:
            tx_type = transaction['type']
            if tx_type == 'token_transfer':
                fee_structure['estimated_fee'] = costs['average_token_transfer']
                fee_structure['estimated_gas_limit'] = gas_limits['token_transfer']
            else:
                fee_structure['estimated_fee'] = costs['average_eth_transfer']
                fee_structure['estimated_gas_limit'] = gas_limits['eth_transfer']
                
        return fee_structure
        
    except Exception as e:
        error_msg = f"Failed to estimate fee: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e
