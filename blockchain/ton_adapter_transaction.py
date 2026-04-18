#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TON adapter transaction creation method implementation.
Will be merged with the main adapter file.
"""

import asyncio

@strict_blockchain_operation
def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
    """Create a TON transaction.
    
    Args:
        transaction: Transaction parameters
            - to_address: Recipient address
            - amount: Amount in TON
            - token_id: Optional jetton ID for token transfers
            - payload: Optional payload for the transaction (comment or data)
            - bounce: Optional flag to enable bounce on transaction failure
        
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
    payload = transaction.get('payload', '')
    bounce = transaction.get('bounce', True)
    
    # Validate recipient address
    if not to_address or not self.validate_address(to_address):
        raise ValidationError(f"Invalid recipient address: {to_address}")
        
    # Get the sender account
    if not self.wallet:
        raise ValidationError("No wallet connected. Cannot create transaction.")
        
    try:
        # Convert amount from TON to nanoTON
        amount_nano = int(Decimal(amount) * Decimal(10**9))
        
        # Create async function to prepare transaction
        async def async_create_tx():
            # Process destination address
            destination = TonAddress(to_address)
            
            # Check if we're transferring a jetton (token) or native TON
            if token_id:
                # Jetton transfer
                # First, we need to get the user's jetton wallet address
                jetton_master = TonAddress(token_id)
                
                jetton_wallet_addr = await self.client.get_jetton_wallet_address(
                    owner_address=self.wallet.address,
                    jetton_master_address=jetton_master
                )
                
                # Create a jetton transfer message
                # This requires a specific message structure for the jetton contract
                transfer_body = await self.client.create_jetton_transfer_body(
                    to_address=destination,
                    amount=amount_nano,
                    response_address=self.wallet.address,
                    forward_amount=int(0.01 * 10**9)  # 0.01 TON for fees
                )
                
                # Build the transaction to the jetton wallet
                seqno = await self.client.get_seqno(self.wallet.address)
                
                transfer_tx = await self.wallet.create_transfer_message(
                    destination=jetton_wallet_addr,
                    amount=int(0.05 * 10**9),  # Gas for the jetton transfer (0.05 TON)
                    seqno=seqno,
                    payload=transfer_body
                )
                
                # Prepare transaction data for signing
                tx_data = {
                    'type': 'jetton_transfer',
                    'sender': self.wallet.address.to_str(is_user_friendly=True),
                    'recipient': to_address,
                    'token_id': token_id,
                    'amount': amount,
                    'amount_nano': amount_nano,
                    'seqno': seqno,
                    'transfer_tx': transfer_tx,
                    'transfer_cell': transfer_tx.message
                }
            else:
                # Native TON transfer
                # Get current seqno (sequence number)
                seqno = await self.client.get_seqno(self.wallet.address)
                
                # Prepare comment if provided
                message_body = None
                if payload:
                    if isinstance(payload, str):
                        # Text comment
                        message_body = await self.client.create_comment_cell(payload)
                    elif isinstance(payload, (bytes, Cell)):
                        # Binary payload
                        if isinstance(payload, bytes):
                            cell = Cell()
                            cell.bits.write_bytes(payload)
                            message_body = cell
                        else:
                            message_body = payload
                
                # Create transfer message
                transfer_tx = await self.wallet.create_transfer_message(
                    destination=destination,
                    amount=amount_nano,
                    seqno=seqno,
                    payload=message_body,
                    bounce=bounce
                )
                
                # Prepare transaction data for signing
                tx_data = {
                    'type': 'ton_transfer',
                    'sender': self.wallet.address.to_str(is_user_friendly=True),
                    'recipient': to_address,
                    'amount': amount,
                    'amount_nano': amount_nano,
                    'seqno': seqno,
                    'bounce': bounce,
                    'payload': payload,
                    'transfer_tx': transfer_tx,
                    'transfer_cell': transfer_tx.message
                }
            
            return tx_data
        
        # Run async function in a synchronous context
        loop = asyncio.new_event_loop()
        tx_data = loop.run_until_complete(async_create_tx())
        loop.close()
        
        logger.debug(f"Created {'jetton' if token_id else 'TON'} transaction: {tx_data}")
        return tx_data
        
    except Exception as e:
        error_msg = f"Failed to create transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e
