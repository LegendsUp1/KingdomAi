#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Injective adapter transaction methods implementation.
Will be merged with the main adapter file.
"""

import asyncio

@strict_blockchain_operation
def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
    """Create an Injective transaction.
    
    Args:
        transaction: Transaction parameters
            - to_address: Recipient address
            - amount: Amount in INJ
            - token_id: Optional token ID for token transfers (denom)
            - memo: Optional memo for the transaction
        
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
    memo = transaction.get('memo', '')
    
    # Validate recipient address
    if not to_address or not self.validate_address(to_address):
        raise ValidationError(f"Invalid recipient address: {to_address}")
        
    # Get the sender account
    if not self.account or not self.address:
        raise ValidationError("No account connected. Cannot create transaction.")
        
    try:
        # Set up default denom if not specified
        denom = token_id or self.fee_denom
        
        # Convert amount from INJ to the smallest unit (10^18)
        decimals = self.CURRENCY.get(denom.upper(), {}).get('decimals', 18)
        amount_in_base = int(Decimal(amount) * Decimal(10**decimals))
        
        # Create async function to prepare transaction
        async def async_create_tx():
            # Get account details for proper sequence and account number
            account_details = await self.client.get_account(self.address)
            
            # Prepare the MsgSend transaction
            tx = self.composer.MsgSend(
                sender=self.address,
                recipient=to_address,
                amount=amount_in_base,
                denom=denom
            )
            
            # Estimate gas and fees
            fee_estimation = await self.client.simulate_transaction(
                msgs=[tx],
                memo=memo,
                public_key=self.public_key,
                address=self.address,
            )
            
            # Prepare the transaction structure
            tx_data = {
                'type': 'token_transfer',
                'sender': self.address,
                'recipient': to_address,
                'amount': amount,
                'amount_base': amount_in_base,
                'denom': denom,
                'memo': memo,
                'msgs': [tx],
                'sequence': int(account_details.account.base_account.sequence),
                'account_number': int(account_details.account.base_account.account_number),
                'chain_id': self.chain_id,
                'gas_price': fee_estimation.gas_price,
                'gas_limit': fee_estimation.gas_limit
            }
            
            return tx_data
        
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        tx_data = loop.run_until_complete(async_create_tx())
        loop.close()
        
        logger.debug(f"Created transaction: {tx_data}")
        return tx_data
        
    except Exception as e:
        error_msg = f"Failed to create transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e

@strict_blockchain_operation
def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
    """Sign an Injective transaction.
    
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
        account = InjectivePrivateKey.from_hex(private_key)
    else:
        if not self.account:
            raise WalletError("No account available for signing")
        account = self.account
        
    try:
        # Validate transaction
        required_fields = ['msgs', 'sequence', 'account_number', 'chain_id', 'gas_price', 'gas_limit']
        for field in required_fields:
            if field not in transaction:
                raise ValidationError(f"Invalid transaction: missing '{field}'")
        
        # Create async function to sign transaction
        async def async_sign_tx():
            # Create a transaction
            tx = InjectiveTransaction(
                msgs=transaction['msgs'],
                memo=transaction.get('memo', ''),
                sequence=transaction['sequence'],
                account_number=transaction['account_number'],
                chain_id=transaction['chain_id'],
                fee=self.composer.Fees(
                    gas_limit=transaction['gas_limit'],
                    gas_price=transaction['gas_price'],
                    fee_payer=self.address
                )
            )
            
            # Sign the transaction
            signed_tx = tx.sign(
                private_key=account,
                public_key=account.to_public_key()
            )
            
            # Get the signed transaction hash
            tx_hash = tx.txhash()
            
            # Return signed transaction data
            return {
                'signed_tx': signed_tx,
                'tx_hash': tx_hash
            }
        
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        signed_data = loop.run_until_complete(async_sign_tx())
        loop.close()
        
        # Add signature data to the transaction
        signed_tx = transaction.copy()
        signed_tx.update({
            'txid': signed_data['tx_hash'],
            'hash': signed_data['tx_hash'],
            'signed_tx': signed_data['signed_tx'],
            'status': 'signed'
        })
        
        logger.debug(f"Signed transaction: {signed_tx['txid']}")
        return signed_tx
        
    except Exception as e:
        error_msg = f"Failed to sign transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e
