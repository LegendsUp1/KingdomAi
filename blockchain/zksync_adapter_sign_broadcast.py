#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
zkSync adapter transaction signing and broadcasting methods.
Will be merged with the main adapter file.
"""

@strict_blockchain_operation
def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
    """Sign a zkSync transaction.
    
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
    
    # Use provided private key or the one from the connected account
    if private_key:
        if not self.validate_private_key(private_key):
            raise WalletError("Invalid private key")
        account = Account.from_key(private_key)
        signer = PrivateKeyEthSigner(account, self.chain_id)
    else:
        if not self.account or not self.signer:
            raise WalletError("No account available for signing")
        account = self.account
        signer = self.signer
        
    try:
        # Validate transaction
        if 'params' not in transaction:
            raise ValidationError("Invalid transaction: missing parameters")
            
        tx_params = transaction['params']
        
        # Sign the transaction
        signed_tx = self.eth_web3.eth.account.sign_transaction(
            tx_params,
            private_key=account.key.hex()
        )
        
        # Extract useful information
        tx_hash = signed_tx.hash.hex()
        raw_tx = signed_tx.rawTransaction.hex()
        
        # Return the signed transaction
        result = {
            'txid': tx_hash,
            'hash': tx_hash,
            'sender': transaction['sender'],
            'recipient': transaction['recipient'],
            'amount': transaction['amount'],
            'type': transaction['type'],
            'signed_tx': raw_tx
        }
        
        if 'data' in transaction:
            result['data'] = transaction['data']
        
        logger.debug(f"Signed transaction: {result['txid']}")
        return result
        
    except Exception as e:
        error_msg = f"Failed to sign transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e
        
@strict_blockchain_operation
def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
    """Broadcast a signed zkSync transaction.
    
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
    if 'signed_tx' not in signed_transaction:
        raise ValidationError("Invalid signed transaction: missing 'signed_tx' field")
        
    try:
        # Convert hex to bytes
        raw_tx = signed_transaction['signed_tx']
        
        # Submit the transaction
        tx_hash = self.provider.send_raw_transaction(raw_tx)
        
        # Wait for transaction receipt
        tx_receipt = self.provider.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        # Check if the transaction was successful
        is_success = tx_receipt and tx_receipt.status == 1
        
        # Extract useful information from the receipt
        status = 'success' if is_success else 'failed'
        gas_used = tx_receipt.gasUsed if tx_receipt else 0
        block_number = tx_receipt.blockNumber if tx_receipt else None
        
        tx_response = {
            'txid': tx_hash,
            'hash': tx_hash,
            'status': status,
            'confirmed': is_success,
            'sender': signed_transaction['sender'],
            'recipient': signed_transaction['recipient'],
            'amount': signed_transaction['amount'],
            'explorer_url': self.explorer_tx_url().format(txid=tx_hash),
            'gas_used': gas_used,
            'block_number': block_number,
            'receipt': tx_receipt
        }
        
        if 'data' in signed_transaction:
            tx_response['data'] = signed_transaction['data']
        
        logger.info(f"Broadcast transaction: {tx_response['txid']} - Status: {tx_response['status']}")
        return tx_response
        
    except Exception as e:
        error_msg = f"Failed to broadcast transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e
