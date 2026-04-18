#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TON adapter transaction signing and broadcasting methods implementation.
Will be merged with the main adapter file.
"""

import asyncio

@strict_blockchain_operation
def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
    """Sign a TON transaction.
    
    Args:
        transaction: Transaction object from create_transaction
        private_key: Private key for signing (optional)
        
    Returns:
        Dict: Signed transaction object ready for broadcasting
        
    Raises:
        ValidationError: If transaction is invalid
        TransactionError: If signing fails
        WalletError: If private key is invalid
    """
    self._verify_connection()
    
    # Verify wallet is available
    if not self.wallet:
        raise WalletError("No wallet available for signing")
    
    # Verify transaction contains required fields
    if 'transfer_tx' not in transaction:
        raise ValidationError("Invalid transaction: missing transfer_tx")
    
    try:
        # The transaction was already signed during creation
        # In TON, signing is part of the message creation process
        # We just need to extract the signed message and package it
        
        # Extract the signed message from the transaction
        signed_message = transaction['transfer_tx'].message
        
        # Add signature data to the transaction
        signed_tx = transaction.copy()
        signed_tx.update({
            'signed': True,
            'signed_message': signed_message,
            'status': 'signed'
        })
        
        logger.debug(f"Transaction signed for {transaction['recipient']}")
        return signed_tx
        
    except Exception as e:
        error_msg = f"Failed to sign transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e

@strict_blockchain_operation
def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
    """Broadcast a signed TON transaction.
    
    Args:
        signed_transaction: Signed transaction from sign_transaction
        
    Returns:
        Dict: Transaction result with hash and status
        
    Raises:
        ValidationError: If signed transaction is invalid
        TransactionError: If broadcasting fails
    """
    self._verify_connection()
    
    # Validate the signed transaction
    if 'signed_message' not in signed_transaction:
        raise ValidationError("Invalid signed transaction: missing 'signed_message' field")
    
    try:
        # Extract the signed message
        signed_message = signed_transaction['signed_message']
        
        # Create async function to send the transaction
        async def async_broadcast():
            # Send the message to the network
            send_result = await self.client.raw_send_message(signed_message)
            
            # Extract transaction hash
            tx_hash = send_result.hash
            
            return tx_hash
        
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        tx_hash = loop.run_until_complete(async_broadcast())
        loop.close()
        
        # Create response with transaction details
        response = {
            'txid': tx_hash,
            'hash': tx_hash,
            'status': 'pending',
            'confirmed': False,
            'sender': signed_transaction['sender'],
            'recipient': signed_transaction['recipient'],
            'amount': signed_transaction['amount'],
            'explorer_url': self.explorer_tx_url().format(txid=tx_hash),
            'type': signed_transaction['type']
        }
        
        if 'token_id' in signed_transaction:
            response['token_id'] = signed_transaction['token_id']
            
        logger.info(f"Transaction broadcast: {response['txid']} ({response['type']})")
        return response
        
    except Exception as e:
        error_msg = f"Failed to broadcast transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e

@strict_blockchain_operation
def get_transaction_status(self, tx_id: str) -> Dict:
    """Get the status of a TON transaction.
    
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
        # Create async function to check transaction status
        async def async_get_status():
            try:
                # Try to get transaction information
                tx_info = await self.client.get_transaction_info(tx_id)
                
                # Check if transaction was found
                if not tx_info:
                    return {
                        'txid': tx_id,
                        'hash': tx_id,
                        'status': 'unknown',
                        'confirmed': False,
                        'explorer_url': self.explorer_tx_url().format(txid=tx_id)
                    }
                
                # Extract transaction details
                status = 'success' if not tx_info.aborted else 'failed'
                
                result = {
                    'txid': tx_id,
                    'hash': tx_id,
                    'status': status,
                    'confirmed': not tx_info.aborted,
                    'block': tx_info.block,
                    'lt': tx_info.lt,
                    'fee': str(tx_info.fee),
                    'explorer_url': self.explorer_tx_url().format(txid=tx_id)
                }
                
                return result
                
            except Exception:
                # Transaction not found or pending
                return {
                    'txid': tx_id,
                    'hash': tx_id,
                    'status': 'pending',
                    'confirmed': False,
                    'explorer_url': self.explorer_tx_url().format(txid=tx_id)
                }
        
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        status = loop.run_until_complete(async_get_status())
        loop.close()
        
        return status
        
    except Exception as e:
        error_msg = f"Failed to check transaction status: {str(e)}"
        logger.error(error_msg)
        
        # Return unknown status
        return {
            'txid': tx_id,
            'hash': tx_id,
            'status': 'unknown',
            'confirmed': False,
            'explorer_url': self.explorer_tx_url().format(txid=tx_id)
        }

@strict_blockchain_operation
def estimate_fee(self, transaction: Dict = None) -> Dict:
    """Estimate fees for a TON transaction.
    
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
        # Create async function to estimate fees
        async def async_estimate_fee():
            # Define standard fees (in nanoTON)
            # TON has fairly stable fees, but we'll provide options
            standard_fees = {
                'simple_transfer': {
                    'slow': int(0.01 * 10**9),  # 0.01 TON
                    'average': int(0.015 * 10**9),  # 0.015 TON
                    'fast': int(0.02 * 10**9)   # 0.02 TON
                },
                'complex_transfer': {
                    'slow': int(0.05 * 10**9),  # 0.05 TON
                    'average': int(0.07 * 10**9),  # 0.07 TON
                    'fast': int(0.1 * 10**9)    # 0.1 TON
                },
                'jetton_transfer': {
                    'slow': int(0.05 * 10**9),  # 0.05 TON
                    'average': int(0.08 * 10**9),  # 0.08 TON
                    'fast': int(0.12 * 10**9)   # 0.12 TON
                }
            }
            
            # If a specific transaction is provided, calculate its fee more precisely
            estimated_fee = None
            if transaction:
                tx_type = transaction.get('type', 'simple_transfer')
                if tx_type == 'jetton_transfer':
                    fee_category = 'jetton_transfer'
                elif 'payload' in transaction and transaction['payload']:
                    fee_category = 'complex_transfer'
                else:
                    fee_category = 'simple_transfer'
                    
                # Get the average fee for this category
                estimated_fee = standard_fees[fee_category]['average']
                
                # If we have a signed message, we can estimate more accurately
                if 'transfer_tx' in transaction:
                    try:
                        # Get message cell from transfer_tx
                        message = transaction['transfer_tx'].message
                        
                        # Estimate fee more accurately
                        fee_result = await self.client.estimate_fee(message)
                        if fee_result:
                            estimated_fee = fee_result.total_fee
                    except Exception as e:
                        logger.debug(f"Error in precise fee estimation: {str(e)}")
            
            # Convert nano to TON
            fee_structure = {}
            for category, fees in standard_fees.items():
                fee_structure[category] = {
                    speed: Decimal(fee) / Decimal(10**9)
                    for speed, fee in fees.items()
                }
            
            # Create the response
            result = {
                'slow': fee_structure['simple_transfer']['slow'],
                'average': fee_structure['simple_transfer']['average'],
                'fast': fee_structure['simple_transfer']['fast'],
                'slow_complex': fee_structure['complex_transfer']['slow'],
                'average_complex': fee_structure['complex_transfer']['average'],
                'fast_complex': fee_structure['complex_transfer']['fast'],
                'slow_token': fee_structure['jetton_transfer']['slow'],
                'average_token': fee_structure['jetton_transfer']['average'],
                'fast_token': fee_structure['jetton_transfer']['fast'],
                'unit': 'TON'
            }
            
            # Add estimated fee if available
            if estimated_fee:
                result['estimated_fee'] = Decimal(estimated_fee) / Decimal(10**9)
            
            return result
            
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        fees = loop.run_until_complete(async_estimate_fee())
        loop.close()
        
        return fees
        
    except Exception as e:
        error_msg = f"Failed to estimate fee: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e
